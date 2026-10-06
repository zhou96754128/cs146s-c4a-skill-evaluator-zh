#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""c4_quality.py — Level 3 质量评审器（本挑战的「学生创新」所在）。

把 rubric 的 4 条质量判据（reusable / executable / verifiable / clear_io）
落成 16 条可机器判定的 rule，每条 rule 输出 ✅/⚠️/❌ + 证据串 + 改进建议。
判据级评分严格按 rubric.scoring：✅≥2 → PASS(1.0)；✅=1 → PARTIAL(0.5)；✅=0 → FAIL(0.0)。

设计要点（方案设计 §2.4）：
  * 否定信号带「自指豁免」：若命中行本身是规则/示例/占位说明文字，
    不计为违规。这是 C4 实跑时踩过的真实假阳性（评审词表命中了记录里
    引用词表的行），在此固化为可解释规则而不是关掉检查。
  * 边界绝不静默：任何 rule 读不到证据时给 ❌ 并写明原因，不做乐观假设。
"""
import re

PASS, PARTIAL, FAIL = "✅", "⚠️", "❌"
EXEMPT_MARKERS = ["检测", "规则", "pattern", "rubric", "示例", "占位",
                  "preflight:allow", "exempt", "模板", "词表"]
ITER_RE = re.compile(r"(第\s*[0-9一二三四五六七八九十]+\s*(轮|版|次)|迭代|修正|驳回|采纳|v[0-9]+)")
NEG_CASE_RE = re.compile(r"(负例|负向|异常输入|坏文件|失败用例|拒绝|拒绝原因|反例|negative case)")


def hits(text, signals):
    low = text.lower()
    return [s for s in signals or [] if s.lower() in low]


def neg_hits(text, signals):
    """否定信号命中，按行做自指豁免；返回 (真实命中, 被豁免)."""
    real, exempted = [], []
    lines = text.splitlines()
    for sig in signals or []:
        for ln in lines:
            if sig.lower() in ln.lower():
                bucket = exempted if any(m.lower() in ln.lower() for m in EXEMPT_MARKERS) else real
                bucket.append({"signal": sig, "line": ln.strip()[:100]})
                break
    return real, exempted


def bundle_text(bundle, slots, include_ai_log=False):
    """技能本体文本 = 技能说明 + 可执行内容 + 教学说明 + demo 文字；AI 日志单列。"""
    keep = {"skill_doc", "executable_content", "teaching_doc"}
    if include_ai_log:
        keep.add("ai_log")
    names = set()
    for sid, info in slots.items():
        if info["present"] and (sid in keep or (sid == "demo" and info["file"].endswith((".md", ".txt")))):
            names.add(info["file"])
    return "\n".join(f["text"] for f in bundle["files"] if f["rel"] in names), sorted(names)


def ai_log_text(bundle, slots):
    info = slots.get("ai_log", {})
    if not info.get("present"):
        return "", None
    for f in bundle["files"]:
        if f["rel"] == info["file"]:
            return f["text"], f["rel"]
    return "", None


def _packages(ctx):
    """返回该提交包里「解析成功」的技能包文件记录（ctx 由 evaluate_quality 构造）。

    说明：返回的是 c4_scan 的文件记录，其 structure / pkg_entries 已由
    c4_eval._attach_structure 附加，故上层规则可直接读 p["structure"]、
    p["package"]["entry_names"] 与 p["pkg_entries"]。
    """
    return [f for f in ctx["bundle"]["files"] if f["package"] and f["package"]["ok"]]


# ---------------------------------------------------------------- 16 条 rule
def r_install_or_env_mention(ctx, it, crit):
    h = hits(ctx["text"], crit.get("positive_signals"))
    return (PASS, "命中环境/安装词：%s" % "、".join(h[:5])) if h else (FAIL, "全文未出现安装或环境要求说明")


def r_no_hardcoded_paths(ctx, it, crit):
    real, exempted = neg_hits(ctx["text"], crit.get("negative_signals"))
    if not real:
        note = "未发现硬编码路径"
        if exempted:
            note += "；%d 处命中已按自指豁免（规则/示例文本）" % len(exempted)
        return PASS, note
    return FAIL, "硬编码嫌疑 %d 处：%s" % (len(real), "; ".join(x["line"] for x in real[:3]))


def r_deps_declared(ctx, it, crit):
    if re.search(r"(requirements\.txt|dependencies|依赖|零依赖|standard library|标准库|pip install|npm install)", ctx["text"], re.I):
        return PASS, "已声明依赖或明确零依赖"
    return FAIL, "未见依赖声明，也未声明零依赖"


def r_platform_scope_noted(ctx, it, crit):
    m = re.search(r"(跨平台|macOS|Windows|Linux|Ubuntu|platform)", ctx["text"], re.I)
    return (PASS, "已标注平台范围：%s" % m.group(1)) if m else (FAIL, "未说明适用平台")


def r_runnable_code_present(ctx, it, crit):
    code = [f["rel"] for f in ctx["bundle"]["files"] if f["ext"] in (".py", ".sh", ".mjs", ".js") and f["size"] > 0]
    fenced = re.search(r"```(python|bash|sh|console)", ctx["text"])
    if code:
        return PASS, "可执行脚本 %d 个：%s" % (len(code), ", ".join(code[:3]))
    if fenced:
        return PARTIAL, "无独立脚本文件，仅有代码块示例"
    return FAIL, "未发现可运行代码/脚本/工作流"


def r_package_structure_valid(ctx, it, crit):
    pkgs = _packages(ctx)
    if not pkgs:
        return FAIL, "未以 .skill/.zip 包形式提交（无法校验包结构）"
    verdicts = ["%s=%s" % (p["name"], p["structure"][0]) for p in pkgs]
    if any(p["structure"][0] == "valid" for p in pkgs):
        return PASS, "包结构合规（%s）" % "; ".join(verdicts)
    if all(p["structure"][0] == "invalid" for p in pkgs):
        return FAIL, "包结构无效（%s）" % "; ".join(verdicts)
    return PARTIAL, "包结构不规范（%s）" % "; ".join(verdicts)


def r_entry_script_nonempty(ctx, it, crit):
    got = []
    for p in _packages(ctx):
        for e in p["package"]["entry_names"]:
            base = e.split("/")[-1]
            if e.startswith(("scripts/", "references/")) or "/scripts/" in e or "/references/" in e or base.endswith((".py", ".sh", ".mjs", ".js")):
                got.append((e, None))
    big = [f["rel"] for f in ctx["bundle"]["files"] if f["ext"] in (".py", ".sh", ".mjs") and f["size"] > 200]
    if got or big:
        return PASS, "入口内容存在：%d 个包内条目 / %d 个独立脚本（>200B）" % (len(got), len(big))
    return FAIL, "入口脚本缺失或过小（<=200 字节）"


def r_frontmatter_present(ctx, it, crit):
    found = False
    for p in _packages(ctx):
        for e in (p.get("pkg_entries") or []):
            if e["name"].endswith("SKILL.md"):
                found = True
                head = e["text"].lstrip()
                if head.startswith("---") and re.search(r"^name\s*:", head, re.M):
                    return PASS, "SKILL.md frontmatter 完整（%s）" % p["name"]
    if found:
        return FAIL, "SKILL.md 存在但缺 YAML frontmatter"
    return FAIL, "无 SKILL.md，无法判定 frontmatter"


def r_tests_present(ctx, it, crit):
    h = hits(ctx["text"], crit.get("positive_signals"))
    cmd = re.search(r"(```(bash|sh|console)|`python3?\s|python3\s+\S+\.py)", ctx["text"], re.I)
    if h and cmd:
        return PASS, "有自检/用例词（%s）且给出可运行命令" % "、".join(h[:3])
    if h or cmd:
        return PARTIAL, "只命中其一（用例词=%s，命令=%s）" % (bool(h), bool(cmd))
    return FAIL, "未见测试/自检与可运行命令"


def r_expected_output_stated(ctx, it, crit):
    m = re.search(r"(预期|expected|输出示例|样例输出|should print|PASS\s*[0-9]|全绿)", ctx["text"], re.I)
    return (PASS, "写明预期输出：%s" % m.group(1)) if m else (FAIL, "未写明预期输出")


def r_demo_evidence_present(ctx, it, crit):
    info = ctx["slots"].get("demo", {})
    return (PASS, "有 demo 证据：%s" % info["file"]) if info.get("present") else (FAIL, "无 demo 截图/录屏/运行记录")


def r_success_criteria_present(ctx, it, crit):
    m = re.search(r"(退出码|exit code|rc\s*=|returncode|PASS\s*计数|全绿|VERDICT)", ctx["text"], re.I)
    return (PASS, "成功/失败判据明确：%s" % m.group(1)) if m else (FAIL, "未给出退出码或 PASS 计数式判据")


def r_io_oneliner(ctx, it, crit):
    m = re.search(r"(输入.{0,12}输出|input.{0,12}output|接受.{0,10}返回|给定.{0,10}得到|输入[:：].{0,40}输出)", ctx["text"], re.I)
    return (PASS, "有一句 IO 说明：%s" % m.group(1)[:40]) if m else (FAIL, "未见「输入X→输出Y」式说明")


def r_input_formats_specified(ctx, it, crit):
    m = re.search(r"(输入|input|接受)[^\n]{0,60}?(文件夹|目录|路径|folder|path|\.md|\.jsonl|\.csv|\.skill|\.zip|文本|JSON)", ctx["text"], re.I)
    return (PASS, "输入格式已说明：%s" % m.group(0)[:60]) if m else (FAIL, "未说明输入格式/类型")


def r_output_formats_specified(ctx, it, crit):
    m = re.search(r"(输出|产出|生成|output|report)[^\n]{0,60}?(\.md|\.json|\.xlsx|表格|报告|Markdown|CSV|图表|dashboard|stdout)", ctx["text"], re.I)
    return (PASS, "输出格式已说明：%s" % m.group(0)[:60]) if m else (FAIL, "未说明输出格式/类型")


def r_edge_cases_noted(ctx, it, crit):
    m = re.search(r"(边界|异常|缺失|空文件|坏文件|超大|无法解析|不支持|fixture)", ctx["text"], re.I)
    return (PASS, "边界/异常已说明：%s" % m.group(1)) if m else (FAIL, "未说明边界或异常输入")


RULES = {
    "install_or_env_mention": r_install_or_env_mention,
    "no_hardcoded_paths": r_no_hardcoded_paths,
    "deps_declared": r_deps_declared,
    "platform_scope_noted": r_platform_scope_noted,
    "runnable_code_present": r_runnable_code_present,
    "package_structure_valid": r_package_structure_valid,
    "entry_script_nonempty": r_entry_script_nonempty,
    "frontmatter_present": r_frontmatter_present,
    "tests_present": r_tests_present,
    "expected_output_stated": r_expected_output_stated,
    "demo_evidence_present": r_demo_evidence_present,
    "success_criteria_present": r_success_criteria_present,
    "io_oneliner": r_io_oneliner,
    "input_formats_specified": r_input_formats_specified,
    "output_formats_specified": r_output_formats_specified,
    "edge_cases_noted": r_edge_cases_noted,
}


def _rating_from(passed, items):
    """把「满足条数」翻成判据评级；disqualifying 条目失败时封顶为 PARTIAL。

    为什么要有封顶：rubric 的通用门槛是「≥2 条即 PASS」，但像「无硬编码绝对路径」这类
    条目失败，意味着换台机器根本跑不起来——属可复现性硬伤。若只按条数算，其余条目全过
    就会把「跑不起来」判成 PASS，等于用「文档写得像能跑」冒充「真的能跑」。
    故：命中 disqualifying 的条目失败时，该判据最高只能到 PARTIAL。
    """
    disq = any(it.get("disqualifying") and it["verdict"] != PASS for it in items)
    if passed >= 2 and not disq:
        return PASS, 1.0
    if passed >= 1:
        return PARTIAL, 0.5
    return FAIL, 0.0


def evaluate_quality(bundle, comp, rubric):
    slots = comp["slots"]
    text, used = bundle_text(bundle, slots)
    ctx = {"text": text, "bundle": bundle, "slots": slots, "used_files": used}
    tpl = rubric.get("suggestion_templates") or {}
    criteria, quality_score, unknown = {}, 0.0, []
    for cid, crit in rubric["quality_criteria"].items():
        items, passed = [], 0
        for it in crit["check_items"]:
            fn = RULES.get(it["rule"])
            if fn is None:
                unknown.append(it["rule"])
                verdict, ev = FAIL, "规则未实现（rubric 与实现不同步）"
            else:
                verdict, ev = fn(ctx, it, crit)
            if verdict == PASS:
                passed += 1
            items.append({"id": it["id"], "rule": it["rule"], "label": it["label"],
                          "verdict": verdict, "evidence": ev,
                          "disqualifying": bool(it.get("disqualifying")),
                          "suggestion": None if verdict == PASS else tpl.get(it["id"]) or tpl.get(it["rule"])})
        rating, score = _rating_from(passed, items)
        criteria[cid] = {"label_cn": crit["label_cn"], "weight": crit["weight"],
                         "passed": passed, "items_total": len(crit["check_items"]),
                         "rating": rating, "score": score, "items": items}
        quality_score += score
    quality_score = round(quality_score / 4.0, 4)
    return {"criteria": criteria, "quality_score": quality_score,
            "scope_files": used, "unknown_rules": sorted(set(unknown))}


def red_flags(bundle, comp, quality, rubric):
    """按 rubric.red_flags 逐条判定，并机械执行 no_negative_case 的扣减。"""
    flags, slots = [], comp["slots"]
    text = quality and "\n".join(
        it["evidence"] for c in quality["criteria"].values() for it in c["items"]) or ""
    if comp["files_present"] < 5:
        flags.append({"id": "missing_artifacts", "detail": "缺 %s" % ", ".join(comp["missing"]),
                      "effect": "artifactCompleteness 上限压低"})
    if slots["skill_doc"]["present"] and not slots["ai_log"]["present"]:
        flags.append({"id": "no_ai_log", "detail": "有技能说明但无 AI 日志",
                      "effect": "reflectionQuality 上限 5"})
    log_text, log_rel = ai_log_text(bundle, slots)
    n_iter = len(set(m.group(0) for m in ITER_RE.finditer(log_text))) if log_text else 0
    if slots["ai_log"]["present"] and n_iter < 2:
        flags.append({"id": "one_shot_ai", "detail": "AI 日志迭代标记仅 %d 个（%s）" % (n_iter, log_rel),
                      "effect": "aiUsage 上限 5"})
    v1 = [it for it in quality["criteria"]["verifiable"]["items"] if it["rule"] == "tests_present"]
    if v1 and v1[0]["verdict"] == PASS and not NEG_CASE_RE.search(bundle_text(bundle, slots)[0]):
        flags.append({"id": "no_negative_case", "detail": "有自检但缺负例/异常用例",
                      "effect": "verifiable 扣 1 条 check item"})
        crit = quality["criteria"]["verifiable"]
        crit["passed"] = max(0, crit["passed"] - 1)
        crit["rating"], crit["score"] = _rating_from(crit["passed"], crit["items"])
        crit["penalized_by"] = "no_negative_case"
        quality["quality_score"] = round(sum(c["score"] for c in quality["criteria"].values()) / 4.0, 4)
    return flags


def score(comp, quality, rubric):
    sc = rubric["scoring"]
    composite = round(comp["completeness_score"] * 0.4 + quality["quality_score"] * 0.6, 4)
    lv = sc.get("level_thresholds") or {}
    level = "L0"
    for name in ("L1", "L2", "L3", "L4"):
        if composite >= float(lv.get(name, 2)):
            level = name
    raw_level = level
    # 材料层不成立者不进 L2：必交物不足 3/5（rubric 的 insufficient 档）时，
    # 即便仅存的两份文档写得很漂亮、把加权分抬过门槛，也不得判入 L2 及以上。
    # 保留 raw_level 与 capped_by，让报告能自解释「为什么分数够了却没进档」。
    capped_by = None
    if comp.get("files_present", 5) < 3 and level not in ("L0", "L1"):
        level, capped_by = "L1", "missing_artifacts"
    return {"completeness_score": comp["completeness_score"],
            "quality_score": quality["quality_score"],
            "composite": composite, "level": level, "raw_level": raw_level,
            "capped_by": capped_by,
            "formula": sc.get("composite", "")}
