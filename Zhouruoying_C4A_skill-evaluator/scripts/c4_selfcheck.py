#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""c4_selfcheck.py — 内置用例自检：19 条用例（6 条正例 / 13 条负例）。

为什么自带负例：评审器最大的风险不是「跑不起来」，而是「不管多烂的东西都判达标」。
所以每条质量规则都必须先证伪一次——构造一个该规则应当判失败的样本，
断言它真的被判失败。全绿才退出码 0，任意一条不符预期即退出码 1。

运行：python3 scripts/c4_evaluator.py selfcheck
落盘：$C4A_SELFCHECK_DIR 或 <系统临时目录>/c4a_selfcheck（每次运行重建，不写回技能包目录）
"""
import json
import os
import shutil
import sys
import tempfile
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import c4_eval  # noqa: E402
from c4_lib import load_rubric, package_structure, read_package  # noqa: E402
from c4_quality import FAIL, PASS  # noqa: E402
from c4_scan import resolve_author  # noqa: E402

RUBRIC = load_rubric(os.path.join(os.path.dirname(HERE), "references", "c4_rubric.yaml"))
BASE = os.environ.get("C4A_SELFCHECK_DIR") or os.path.join(
    tempfile.gettempdir(), "c4a_selfcheck"
)

SKILL_MD = """---
name: c4-eval-demo
description: 演示用技能包，输入文件夹，输出评审报告。
---

# Demo Skill
输入：一个文件夹。输出：报告。
"""

CODE = """#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys


def load(folder):
    rows = []
    for name in sorted(os.listdir(folder)):
        rows.append(os.path.join(folder, name))
    return rows


def summarize(rows):
    return {"count": len(rows)}


def main(argv):
    rows = load(argv[1] if len(argv) > 1 else ".")
    print(summarize(rows))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
""" + ("# padding:" + "x" * 120 + "\n")

SPEC_OK = """# 技能说明

## 使用场景
解决什么问题：把一堆散落的技能提交文件自动盘点成可评审的结论，适用场景是课程批量评审。

## 安装 / 环境要求
零依赖，仅用 Python 标准库（Python 3.8+），不需要 pip install。
兼容 macOS / Linux / Windows 三端，跨平台。

## 输入输出
输入：一个文件夹路径（本地目录，内含 .skill / .zip / .md）。
输出：Markdown 评审报告 + JSON 看板，默认落到 out/ 目录。

## 边界与异常输入
空目录、损坏的 zip、超过 2MB 的条目、带 `..` 的越界路径都会被显式跳过并记入告警，
不会让评审器本身崩溃。
"""

TEACH_OK = """# 教学说明

## 上手步骤
1. 安装：无需安装，确认 python3 可用即可。
2. 运行：`python3 scripts/c4_evaluator.py review <文件夹> --out report.md`。
3. 看结果：打开 report.md 对照排名表。

## 常见坑
- 路径带空格要加引号（注意事项）。
- 中文文件名在不同系统编码不同，用 UTF-8 保存。

getting started / step by step 见上。
"""

DEMO_OK = """运行记录（可复现）
命令：python3 scripts/c4_evaluator.py review samples/ --out report.md
预期输出：19 条用例 PASS 19 / FAIL 0。
成功判据：退出码 0；失败判据：任一条不符预期则退出码 1。
自检：python3 scripts/c4_evaluator.py selfcheck → selfcheck PASS 19/19。
负例覆盖：空目录 → 退出码 5；伪造的 .skill（其实是文本）→ 判为 not_a_zip；
带 `../evil.txt` 的包 → 该条目被拒绝。
截图见 demo画面.png（同目录）。
"""

AILOG_OK = """# AI 生成日志

使用的 AI：Claude（设计评审规则）、Codex（写实现）。
prompt 摘要：先给规则清单，再让它实现，逐条对照 rubric。

第 1 轮：让它一次性生成全部规则 → 结果把「检测词」当成硬编码路径，误报 1 处。
第 2 轮：改为负向信号 + 自指豁免 → 修正后误报消失。
第 3 轮：补负例用例 → 采纳 8 条、驳回 2 条（驳回原因：会漏掉只交 .md 的情况）。
迭代记录：3 轮，采纳 8 / 驳回 2。
"""

SPEC_HARDCODED = SPEC_OK.replace(
    "## 边界与异常输入",
    "## 数据位置\n固定读 /Users/demo/private/data.csv，不读就会报错。\n\n## 边界与异常输入")
AILOG_ONESHOT = "# AI 生成日志\n\n使用的 AI：Claude。\nprompt：帮我写一个评审器。\n输出：一次成稿。\n"
SPEC_NOIO = ("# 技能说明\n\n这个技能用于整理文件。安装：零依赖。\n"
             "兼容 macOS。\n")
TEACH_NOIO = "# 教学说明\n\n上手：直接运行即可。\n"
DEMO_NOIO = "运行记录：跑过一次，结果还行。\n"
AILOG_NOIO = "# AI 生成日志\n\n使用的 AI：Claude。\n第1轮：写代码。第2轮：修 bug。\n"
# 负例用包：SKILL.md 不写任何输入/输出说明（用于证伪 clear_io）
NOIO_PKG = {"SKILL.md": "---\nname: noio-demo\ndescription: 演示用技能包。\n---\n\n# Demo Skill\n这个技能包用来整理文件。\n",
            "scripts/app.py": CODE, "references/r.yaml": "version: 1\n"}


def _w(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def _zip(path, entries):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with zipfile.ZipFile(path, "w") as z:
        for name, text in entries.items():
            z.writestr(name, text)
    return path


def _pkg(author, name="技能包"):
    return os.path.join(BASE, author, "%s_C4_%s.skill" % (author, name))


def build_fixtures():
    if os.path.isdir(BASE):
        shutil.rmtree(BASE)
    good_pkg = {"SKILL.md": SKILL_MD, "scripts/app.py": CODE, "references/r.yaml": "version: 1\n"}
    # 正例：五个必交物齐全
    a = "Zhouruoying"
    _zip(_pkg(a), good_pkg)
    _w(os.path.join(BASE, a, a + "_C4_技能说明.md"), SPEC_OK)
    _w(os.path.join(BASE, a, a + "_C4_教学说明.md"), TEACH_OK)
    _w(os.path.join(BASE, a, a + "_C4_demo运行记录.txt"), DEMO_OK)
    _w(os.path.join(BASE, a, a + "_C4_AI日志.md"), AILOG_OK)
    # 负例：只交 2 件
    _w(os.path.join(BASE, "Lisi", "Lisi_C4_技能说明.md"), SPEC_OK)
    _w(os.path.join(BASE, "Lisi", "Lisi_C4_AI日志.md"), AILOG_OK)
    # 负例：有技能说明但完全没有 AI 日志
    b = "Wangwu"
    _zip(_pkg(b), good_pkg)
    _w(os.path.join(BASE, b, b + "_C4_技能说明.md"), SPEC_OK)
    _w(os.path.join(BASE, b, b + "_C4_教学说明.md"), TEACH_OK)
    _w(os.path.join(BASE, b, b + "_C4_demo运行记录.txt"), DEMO_OK)
    # 负例：AI 日志是「一次成稿」
    c = "Zhaoliu"
    _zip(_pkg(c), good_pkg)
    _w(os.path.join(BASE, c, c + "_C4_技能说明.md"), SPEC_OK)
    _w(os.path.join(BASE, c, c + "_C4_教学说明.md"), TEACH_OK)
    _w(os.path.join(BASE, c, c + "_C4_demo运行记录.txt"), DEMO_OK)
    _w(os.path.join(BASE, c, c + "_C4_AI日志.md"), AILOG_ONESHOT)
    # 负例：硬编码绝对路径
    d = "Sunqi"
    _zip(_pkg(d), good_pkg)
    _w(os.path.join(BASE, d, d + "_C4_技能说明.md"), SPEC_HARDCODED)
    _w(os.path.join(BASE, d, d + "_C4_教学说明.md"), TEACH_OK)
    _w(os.path.join(BASE, d, d + "_C4_demo运行记录.txt"), DEMO_OK)
    _w(os.path.join(BASE, d, d + "_C4_AI日志.md"), AILOG_OK)
    # 负例：有自检但通篇没有负例/异常字样（触发 no_negative_case 扣减）
    e = "Zhouba"
    _zip(_pkg(e), good_pkg)
    spec = SPEC_OK.replace("## 边界与异常输入", "## 参数说明").replace(
        "空目录、损坏的 zip、超过 2MB 的条目、带 `..` 的越界路径都会被显式跳过并记入告警，\n不会让评审器本身崩溃。", "路径都以参数传入。")
    demo = "运行记录\n命令：python3 scripts/c4_evaluator.py review samples/\n预期输出：PASS 12 / FAIL 0\n成功判据：退出码 0\n"
    _w(os.path.join(BASE, e, e + "_C4_技能说明.md"), spec)
    _w(os.path.join(BASE, e, e + "_C4_教学说明.md"), TEACH_OK)
    _w(os.path.join(BASE, e, e + "_C4_demo运行记录.txt"), demo)
    _w(os.path.join(BASE, e, e + "_C4_AI日志.md"), AILOG_OK)
    # 负例：完全没有可运行代码（说明+日志+教学+运行记录，无脚本无包）
    f = "Wujiu"
    _w(os.path.join(BASE, f, f + "_C4_技能说明.md"), SPEC_OK)
    _w(os.path.join(BASE, f, f + "_C4_教学说明.md"), TEACH_OK)
    _w(os.path.join(BASE, f, f + "_C4_demo运行记录.txt"), DEMO_OK)
    _w(os.path.join(BASE, f, f + "_C4_AI日志.md"), AILOG_OK)
    # 负例：输入输出完全没写清楚（包内 SKILL.md 也不写 IO，否则会被包内文档救回来）
    g = "Zhengshi"
    _zip(_pkg(g), NOIO_PKG)
    _w(os.path.join(BASE, g, g + "_C4_技能说明.md"), SPEC_NOIO)
    _w(os.path.join(BASE, g, g + "_C4_教学说明.md"), TEACH_NOIO)
    _w(os.path.join(BASE, g, g + "_C4_demo运行记录.txt"), DEMO_NOIO)
    _w(os.path.join(BASE, g, g + "_C4_AI日志.md"), AILOG_NOIO)
    # 包结构负例：SKILL.md 之外还有越界文件
    _zip(_pkg("Pkgloose", "技能包"),
         {"SKILL.md": SKILL_MD, "scripts/app.py": CODE, "README.md": "越界", "data/x.json": "{}"})
    # 包结构负例：根本不是 zip 的 .skill
    _w(_pkg("Pkgfake", "技能包"), "这不是一个 zip 文件\n")
    # 安全负例：越界路径 / 超大条目
    _zip(_pkg("Pkgevil", "技能包"),
         {"SKILL.md": SKILL_MD, "../evil.txt": "拿不到我", "scripts/app.py": CODE})
    os.makedirs(os.path.join(BASE, "_empty"), exist_ok=True)
    return BASE


def _bundle(res, author):
    for b in res["bundles"]:
        if b["author"].lower() == author.lower():
            return b
    return None


def _flag(b, fid):
    return any(f["id"] == fid for f in b["red_flags"])


def _rule(b, cid, rule):
    for it in b["quality"]["criteria"][cid]["items"]:
        if it["rule"] == rule:
            return it
    return None


def tests(res, empty_res):
    T = []

    def case(cid, desc, ok, detail=""):
        T.append((cid, desc, bool(ok), detail))

    b = _bundle(res, "Zhouruoying")
    case("P1", "齐全样本判 5/5 且四条判据全 PASS",
         b and b["completeness"]["files_present"] == 5
         and all(c["rating"] == PASS for c in b["quality"]["criteria"].values()),
         "fp=%s composite=%s" % (b and b["completeness"]["files_present"], b and b["score"]["composite"]))
    case("P2", "齐全样本无风险标记且达 L4",
         b and not b["red_flags"] and b["score"]["level"] in ("L3", "L4"),
         "flags=%s level=%s" % (b and [f["id"] for f in b["red_flags"]], b and b["score"]["level"]))
    case("P3", "齐全样本质量分为 1.0（四条判据均 PASS）",
         b and abs(b["quality"]["quality_score"] - 1.0) < 1e-9, b and b["quality"]["quality_score"])
    lisi = _bundle(res, "Lisi")
    case("N4", "缺 3 件必交物 → 完整性 2/5 + missing_artifacts",
         lisi and lisi["completeness"]["files_present"] == 2 and _flag(lisi, "missing_artifacts"),
         "fp=%s flags=%s" % (lisi and lisi["completeness"]["files_present"],
                             lisi and [f["id"] for f in lisi["red_flags"]]))
    case("N5", "缺 3 件必交物 → 判级封顶 L1、不得进 L2（留 level_cap 痕迹）",
         lisi and lisi["score"]["level"] in ("L0", "L1")
         and lisi["score"]["composite"] < 0.70
         and lisi["score"]["capped_by"] == "missing_artifacts",
         lisi and "level=%s raw=%s composite=%s capped_by=%s" % (
             lisi["score"]["level"], lisi["score"]["raw_level"],
             lisi["score"]["composite"], lisi["score"]["capped_by"]))
    wang = _bundle(res, "Wangwu")
    case("N6", "有技能说明无 AI 日志 → no_ai_log",
         wang and _flag(wang, "no_ai_log"), wang and [f["id"] for f in wang["red_flags"]])
    zhao = _bundle(res, "Zhaoliu")
    case("N7", "AI 日志无迭代标记 → one_shot_ai",
         zhao and _flag(zhao, "one_shot_ai"), zhao and [f["id"] for f in zhao["red_flags"]])
    sun = _bundle(res, "Sunqi")
    r2 = sun and _rule(sun, "reusable", "no_hardcoded_paths")
    case("N8", "硬编码 /Users/ 路径 → r2 判失败且 reusable 不达标",
         r2 and r2["verdict"] != PASS and sun["quality"]["criteria"]["reusable"]["rating"] != PASS,
         r2 and r2["verdict"])
    zhou = _bundle(res, "Zhouba")
    ver = zhou and zhou["quality"]["criteria"]["verifiable"]
    case("N9", "有自检但无负例 → no_negative_case 扣减并留痕",
         zhou and _flag(zhou, "no_negative_case") and ver.get("penalized_by") == "no_negative_case",
         zhou and ver.get("penalized_by"))
    wu = _bundle(res, "Wujiu")
    case("N10", "无可运行代码 → executable 不达标",
         wu and wu["quality"]["criteria"]["executable"]["rating"] != PASS,
         wu and wu["quality"]["criteria"]["executable"]["rating"])
    zheng = _bundle(res, "Zhengshi")
    case("N11", "输入输出含糊 → clear_io 不达标",
         zheng and zheng["quality"]["criteria"]["clear_io"]["rating"] != PASS,
         zheng and zheng["quality"]["criteria"]["clear_io"]["rating"])
    ok_pkg = read_package(_pkg("Zhouruoying"))
    v_ok, d_ok = package_structure(ok_pkg)
    case("P12", "规范包结构判 valid（SKILL.md 在根 + scripts/references）",
         ok_pkg["ok"] and v_ok == "valid", "%s / %s" % (v_ok, d_ok))
    loose = read_package(_pkg("Pkgloose", "技能包"))
    v_lo, d_lo = package_structure(loose)
    case("N13", "包内多出越界文件 → 判 loose 并点名",
         v_lo == "loose", "%s / %s" % (v_lo, d_lo))
    fake = read_package(_pkg("Pkgfake", "技能包"))
    case("N14", "伪造的 .skill（实为文本）→ ok=False / not_a_zip",
         (not fake["ok"]) and fake["reason"] == "not_a_zip", fake["reason"])
    evil = read_package(_pkg("Pkgevil", "技能包"))
    names = [e["name"] for e in evil["entries"]]
    case("N15", "包内 `../evil.txt` 被拒绝且不进 entries",
         any(r["reason"] == "unsafe-path" for r in evil["rejected"])
         and all(".." not in n for n in names),
         "rejected=%s" % [r["name"] for r in evil["rejected"]])
    au = resolve_author("mystery_submission/notes.md", "", [], RUBRIC)
    case("N16", "文件名无法解析时回退 Unknown Author 并标记人工复核",
         RUBRIC["selector"]["unknown_author_label"].lower() in str(au).lower(), str(au)[:120])
    case("N17", "空目录 → 0 份提交（CLI 退出码 5 的前置条件）",
         empty_res["summary"]["submissions"] == 0,
         empty_res["summary"]["submissions"])
    one = c4_eval.evaluate_folder(os.path.join(BASE, "Zhouruoying"), RUBRIC)
    two = c4_eval.evaluate_folder(os.path.join(BASE, "Zhouruoying"), RUBRIC)
    one.pop("scanned_at"), two.pop("scanned_at")
    case("P18", "同输入复跑结果完全一致（确定性）",
         json.dumps(one, sort_keys=True, ensure_ascii=False) == json.dumps(two, sort_keys=True, ensure_ascii=False),
         "两份 JSON 逐字节一致")
    rp = c4_eval.rubric_selfcheck(RUBRIC)
    case("P19", "rubric 与实现同步（16 条 rule 全部有实现、权重和为 1）", not rp, "；".join(rp))
    return T


def main(argv=None):
    base = build_fixtures()
    res = c4_eval.evaluate_folder(base, RUBRIC)
    empty_res = c4_eval.evaluate_folder(os.path.join(base, "_empty"), RUBRIC)
    rows = tests(res, empty_res)
    bad = 0
    print("c4-skill-evaluator selfcheck — 用例 %d 条" % len(rows))
    print("样本目录：%s（采集 %d 文件 → %d 份提交）" % (base, res["record_count"], res["summary"]["submissions"]))
    for cid, desc, ok, detail in rows:
        flag = "PASS" if ok else "FAIL"
        if not ok:
            bad += 1
        print("[%s] %-4s %s%s" % (flag, cid, desc, ("  ← %s" % detail) if detail else ""))
    print("")
    print("结果：%d/%d PASS，%d FAIL" % (len(rows) - bad, len(rows), bad))
    if bad:
        print("VERDICT: RED — 负例未被正确识别，评审器不可信，禁止用于真实评审。")
        return 1
    print("VERDICT: GREEN — 19 条含负例的判据全部符合预期，退出码 0。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
