#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""c4_report.py — Level 4 报告生成器：逐人评审段 + 排名表 + 班级级建议 + 仪表板数据。

输出三种形态，全部由 c4_eval 的结果对象生成，不含二次判定：
  1) Markdown 评审报告（直接作为 C4A 必交物 `Zhouruoying_C4A_评审报告.md` 的机器生成部分）
  2) dashboard JSON（喂给可视化看板：等级分布 / 排名 / 高频失分点 / 趋势）
  3) history.jsonl 追加一行，多次运行可看趋势（评审漂移早发现）
"""
import json
import os

from c4_lib import now_iso

SLOT_LABEL = {"skill_doc": "技能说明", "executable_content": "可执行内容", "demo": "Demo",
              "teaching_doc": "教学说明", "ai_log": "AI 日志"}
CRIT_ORDER = ["reusable", "executable", "verifiable", "clear_io"]
CRIT_CN = {"reusable": "可复用", "executable": "可执行", "verifiable": "可验证", "clear_io": "IO 明确"}
FLAG_CN = {"missing_artifacts": "必交物缺失", "no_ai_log": "无 AI 日志",
           "one_shot_ai": "AI 日志疑一次性生成", "no_negative_case": "缺负例/异常用例"}


def _chal(b):
    """挑战号带来源标记：文件名实测的照写，推断出来的加「（推断）」。"""
    return b["challenge"] + ("（推断）" if b.get("challenge_method") == "inferred" else "")


def md_report(result, title="C4A 技能提交自动评审报告"):
    L = []
    s = result["summary"]
    L.append("# %s" % title)
    L.append("")
    L.append("- 扫描目录：`%s`" % result["folder"])
    L.append("- 扫描时间：%s（rubric v%s / challenge %s）"
             % (result["scanned_at"], result["rubric_version"], result["rubric_challenge"]))
    L.append("- 采集文件 %d 个 → 归并提交 %d 份（其中技能包 %d 个）"
             % (result["record_count"], s["submissions"], result["package_count"]))
    if result.get("excluded"):
        L.append("- 另有 %d 份提交的挑战号不在过滤范围（`%s`）内 → 只登记不排名（见第六节）"
                 % (len(result["excluded"]), result.get("challenge_filter") or "未设置"))
    L.append("- 平均综合分 %.2f；等级分布 %s"
             % (s["average_composite"], "、".join("%s=%d" % kv for kv in sorted(s["levels"].items())) or "—"))
    L.append("")
    L.append("## 一、排名总表")
    L.append("")
    L.append("| 排名 | 作者 | 挑战 | 文件数 | 完整性 | 质量 | 综合 | 等级 | 风险标记 |")
    L.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for b in result["bundles"]:
        flags = "、".join(FLAG_CN.get(f["id"], f["id"]) for f in b["red_flags"]) or "—"
        L.append("| %d | %s | %s | %d | %.2f | %.2f | **%.2f** | %s | %s |"
                 % (b["rank"], b["author"], _chal(b), b["file_count"],
                    b["completeness"]["completeness_score"], b["quality"]["quality_score"],
                    b["score"]["composite"], b["score"]["level"], flags))
    L.append("")
    if result["warnings"]:
        L.append("## 二、采集告警（需人工过一眼）")
        L.append("")
        for w in result["warnings"]:
            L.append("- %s" % w)
        L.append("")
    L.append("## 三、逐人评审")
    L.append("")
    for b in result["bundles"]:
        L.append("### %d. %s（%s，%s）" % (b["rank"], b["author"], _chal(b), b["score"]["level"]))
        L.append("")
        L.append("综合分 **%.2f** = 完整性 %.2f×0.4 + 质量 %.2f×0.6；文件 %d 个，合计 %s。"
                 % (b["score"]["composite"], b["completeness"]["completeness_score"],
                    b["quality"]["quality_score"], b["file_count"], b["total_size_h"]))
        if b["student_id"]:
            L.append("")
            L.append("学号（从文本识别）：`%s`" % b["student_id"])
        L.append("")
        L.append("**必交物**：" + "；".join(
            "%s %s%s" % (SLOT_LABEL[k], "✅" if v["present"] else "❌",
                         "（%s）" % v["file"] if v["present"] else "")
            for k, v in b["completeness"]["slots"].items()))
        L.append("")
        for cid in CRIT_ORDER:
            c = b["quality"]["criteria"][cid]
            L.append("**%s %s（%s，命中 %d/%d）**" % (CRIT_CN[cid], c["rating"],
                                                    c["label_cn"], c["passed"], c["items_total"]))
            L.append("")
            for it in c["items"]:
                line = "- %s %s — %s" % (it["verdict"], it["label"], it["evidence"])
                if it["suggestion"]:
                    line += " → 建议：%s" % it["suggestion"]
                L.append(line)
            L.append("")
        if b["red_flags"]:
            L.append("**风险标记**：" + "；".join(
                "%s（%s → %s）" % (FLAG_CN.get(f["id"], f["id"]), f["detail"], f["effect"])
                for f in b["red_flags"]))
            L.append("")
        L.append("**结论**：%s" % _conclusion(b))
        L.append("")
    L.append("## 四、班级级改进建议（按受影响人数排序）")
    L.append("")
    L.append("| 判据 | 失分项 | 受影响 | 作者 |")
    L.append("| --- | --- | --- | --- |")
    for c in result["class_suggestions"]:
        L.append("| %s | %s | %d | %s |" % (CRIT_CN.get(c["criterion"], c["criterion"]),
                                            c["label"], c["affected"], "、".join(c["authors"])))
    L.append("")
    mr = [b for b in result["bundles"] if b["manual_review"]]
    if mr:
        L.append("## 五、人工复核队列")
        L.append("")
        for b in mr:
            L.append("- %s：作者无法自动解析（已标 Unknown Author），请人工指定后重跑。" % b["author"])
        L.append("")
    if result.get("excluded"):
        L.append("## 六、不在目标挑战范围内的提交（只登记，不排名）")
        L.append("")
        L.append("| 作者 | 挑战 | 文件数 | 综合分（参考） | 处置 |")
        L.append("| --- | --- | --- | --- | --- |")
        for b in result["excluded"]:
            L.append("| %s | %s | %d | %.2f | %s |"
                     % (b["author"], _chal(b), b["file_count"],
                        b["score"]["composite"], b["reason"]))
        L.append("")
        L.append("> 这些提交的挑战号不在 `challenge_filter` 指定范围内（或无法判定）；"
                 "分数仅作登记，不参与排名、平均分与班级建议。")
        L.append("")
    L.append("---")
    L.append("")
    L.append("> 本报告由 `c4_evaluator.py review` 生成；所有结论都带 rule 级证据，"
             "可用同一输入复跑复现（脚本零第三方依赖）。")
    return "\n".join(L)


def _conclusion(b):
    lv = b["score"]["level"]
    if lv in ("L3", "L4"):
        return "达到提交级（%s）：五个必交物齐全、四条质量判据均达标，可进入人工终审。" % lv
    if lv == "L2":
        return "达基础级（L2）：结构完整但质量判据仍有缺口，按上方建议补齐后可升到 L3。"
    if b["completeness"]["files_present"] < 5:
        return "未达基础级：缺 %s，先补齐必交物再评质量。" % "、".join(
            SLOT_LABEL.get(m, m) for m in b["completeness"]["missing"])
    return "未达基础级：必交物在但质量证据薄弱，优先补「可验证」与「IO 明确」两项。"


def dashboard(result):
    return {
        "schema_version": 1,
        "title": "C4A 技能提交评审看板",
        "metrics": [
            {"label": "提交份数", "value": str(result["summary"]["submissions"])},
            {"label": "平均综合分", "value": "%.2f" % result["summary"]["average_composite"]},
            {"label": "技能包数", "value": str(result["package_count"])},
            {"label": "告警条数", "value": str(len(result["warnings"]))},
            {"label": "范围外登记", "value": str(len(result.get("excluded", [])))},
        ],
        "level_distribution": result["summary"]["levels"],
        "ranking": [{"rank": b["rank"], "author": b["author"], "composite": b["score"]["composite"],
                     "level": b["score"]["level"], "missing": ", ".join(b["missing"]) or "-"}
                    for b in result["bundles"]],
        "excluded": [{"author": b["author"], "challenge": _chal(b),
                      "composite": b["score"]["composite"], "reason": b["reason"]}
                     for b in result.get("excluded", [])],
        "top_gaps": [{"check_item": c["label"], "affected": c["affected"]}
                     for c in result["class_suggestions"][:5]],
        "generated_at": result["scanned_at"],
    }


def append_history(result, path):
    row = {"at": result["scanned_at"], "folder": result["folder"],
           "submissions": result["summary"]["submissions"],
           "average_composite": result["summary"]["average_composite"],
           "levels": result["summary"]["levels"],
           "per_author": {b["author"]: b["score"]["composite"] for b in result["bundles"]}}
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return path


def trend(history_path):
    if not os.path.exists(history_path):
        return []
    rows = []
    with open(history_path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except ValueError:
                    continue
    return rows
