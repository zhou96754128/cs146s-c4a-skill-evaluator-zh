#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""c4_eval.py — 评审编排层：把 L1→L2→L3→L4 串成一次可复现的评审。

流水线（对应 CHALLENGE.md 的四段 pipeline）：
  ① 采集 scan_folder  → ② 完整性 completeness → ③ 质量 evaluate_quality
  → ④ 汇总/排名/班级建议 → 报告由 c4_report.py 渲染
本层不做任何 IO 决策，只产出可 JSON 序列化的结果对象，便于自检断言。
"""
import os

from c4_lib import human_size, now_iso, package_structure, read_package
from c4_quality import evaluate_quality, red_flags, score
from c4_scan import completeness, scan_folder


def _attach_structure(bundle):
    """把「包解析结果」附加到文件记录上：structure（结构判定）+ pkg_entries（包内条目）。

    质量层的 frontmatter / 入口脚本两类规则需要读包内条目，故在此一次性附加，
    避免评审过程中对同一个 .skill 反复解压。
    """
    for f in bundle["files"]:
        if f["package"] and f["package"]["ok"]:
            pkg = read_package(f["path"])
            verdict, detail = package_structure(pkg)
            f["structure"] = (verdict, detail)
            f["pkg_entries"] = pkg["entries"]
        else:
            f["structure"] = None
            f["pkg_entries"] = []


def evaluate_bundle(bundle, rubric):
    _attach_structure(bundle)
    comp = completeness(bundle, rubric)
    quality = evaluate_quality(bundle, comp, rubric)
    flags = red_flags(bundle, comp, quality, rubric)
    sc = score(comp, quality, rubric)
    suggestions = []
    for cid, crit in quality["criteria"].items():
        for it in crit["items"]:
            if it["verdict"] != "✅" and it["suggestion"]:
                suggestions.append({"criterion": cid, "check_item": it["id"],
                                    "verdict": it["verdict"], "text": it["suggestion"]})
    return {"author": bundle["author"], "challenge": bundle["challenge"],
            "challenge_method": bundle.get("challenge_method", "unknown"),
            "in_scope": bundle.get("in_scope", True),
            "student_id": bundle["student_id"], "file_count": bundle["file_count"],
            "total_size": bundle["total_size"],
            "total_size_h": bundle["total_size_h"], "manual_review": bundle["manual_review"],
            "completeness": comp, "quality": quality, "red_flags": flags,
            "score": sc, "suggestions": suggestions,
            "missing": comp["missing"]}


def evaluate_folder(folder, rubric):
    res = scan_folder(folder, rubric)
    every = [evaluate_bundle(b, rubric) for b in res["bundles"]]
    # 范围隔离：只有落在 challenge_filter 目标家族内的提交参与排名/统计；
    # 其余（跨挑战、或挑战号无法判定）只登记不排名，避免把 C2A 的分排进 C4 榜单。
    bundles = [b for b in every if b["in_scope"]]
    excluded = [b for b in every if not b["in_scope"]]
    rank = sorted(bundles, key=lambda b: (-b["score"]["composite"],
                                          -b["completeness"]["files_present"],
                                          b["author"].lower()))
    for i, b in enumerate(rank, 1):
        b["rank"] = i
    fail_counter = {}
    for b in bundles:
        for cid, crit in b["quality"]["criteria"].items():
            for it in crit["items"]:
                if it["verdict"] != "✅":
                    key = (cid, it["id"], it["label"])
                    fail_counter.setdefault(key, []).append(b["author"])
    class_suggestions = [
        {"criterion": k[0], "check_item": k[1], "label": k[2],
         "affected": len(v), "authors": v[:8]}
        for k, v in sorted(fail_counter.items(), key=lambda kv: -len(kv[1]))
    ]
    levels = {}
    for b in bundles:
        levels[b["score"]["level"]] = levels.get(b["score"]["level"], 0) + 1
    avg = round(sum(b["score"]["composite"] for b in bundles) / len(bundles), 4) if bundles else 0.0
    flt = rubric["selector"].get("challenge_filter") or "（未设置）"
    for b in excluded:
        b["reason"] = ("挑战号无法判定（文件名与内容都没有可判定信号）" if b["challenge"] == "unknown"
                       else "挑战 %s 不在过滤范围 %s 内" % (b["challenge"], flt))
    excluded = sorted(excluded, key=lambda b: (b["author"].lower(), b["challenge"]))
    out = {"scanned_at": now_iso(), "folder": os.path.abspath(folder),
           "rubric_version": rubric.get("version"), "rubric_challenge": rubric.get("challenge"),
           "challenge_filter": rubric["selector"].get("challenge_filter") or "",
           "record_count": len(res["records"]),
           "package_count": sum(1 for r in res["records"] if r["package"] and r["package"]["ok"]),
           "bundles": rank, "excluded": excluded, "warnings": res["warnings"],
           "class_suggestions": class_suggestions,
           "summary": {"submissions": len(bundles), "excluded": len(excluded),
                       "average_composite": avg, "levels": levels,
                       "total_size_h": human_size(sum(b.get("total_size") or 0 for b in bundles))}}
    return out


def rubric_selfcheck(rubric):
    """对 rubric 本体做一致性检查：每个 check_item 的 rule 都必须有实现。"""
    from c4_quality import RULES
    problems = []
    for cid, crit in (rubric.get("quality_criteria") or {}).items():
        for it in crit.get("check_items") or []:
            if it.get("rule") not in RULES:
                problems.append("%s/%s rule 未实现" % (cid, it["rule"]))
        if abs(sum(c.get("weight", 0) for c in [crit]) - crit.get("weight", 0)) > 1e-9:
            problems.append("%s 权重异常" % cid)
    w = sum(c.get("weight", 0) for c in (rubric.get("quality_criteria") or {}).values())
    if abs(w - 1.0) > 1e-9:
        problems.append("四条质量判据权重合计 = %s（应为 1.0）" % w)
    if not (rubric.get("required_deliverables")):
        problems.append("required_deliverables 为空")
    return problems
