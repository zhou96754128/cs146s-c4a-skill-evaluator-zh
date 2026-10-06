#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""c4_evaluator.py — C4A 技能提交自动评审器 CLI（零第三方依赖）。

用法：
  python3 scripts/c4_evaluator.py review   <文件夹> [--out 报告.md] [--dashboard d.json] [--history h.jsonl]
  python3 scripts/c4_evaluator.py scan     <文件夹> [--json out.json]
  python3 scripts/c4_evaluator.py rubric-check
  python3 scripts/c4_evaluator.py selfcheck
  python3 scripts/c4_evaluator.py version

退出码（可被 CI / 脚本判定，是本技能「可执行」的硬证据）：
  0 成功；1 参数用法错误；2 输入目录不存在或不是目录；3 rubric 读取失败；
  4 rubric 与实现不一致（有 rule 未实现 / 权重异常）；5 目录内没找到任何可评审提交（空跑不算成功）
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import c4_eval  # noqa: E402
import c4_report  # noqa: E402
from c4_lib import load_rubric  # noqa: E402

DEFAULT_RUBRIC = os.path.join(os.path.dirname(HERE), "references", "c4_rubric.yaml")


def _load(rubric_path):
    try:
        return load_rubric(rubric_path)
    except Exception as exc:  # noqa: BLE001 — 兜底：rubric 坏了不能让评审器崩
        print("[E3] rubric 读取失败：%s（%s）" % (rubric_path, exc), file=sys.stderr)
        sys.exit(3)


def _check_folder(folder):
    if not folder or not os.path.isdir(folder):
        print("[E2] 输入目录不存在或不是目录：%s" % folder, file=sys.stderr)
        sys.exit(2)


def cmd_scan(args):
    _check_folder(args.folder)
    rubric = _load(args.rubric)
    res = c4_eval.evaluate_folder(args.folder, rubric)
    if res["summary"]["submissions"] == 0:
        print("[E5] 未在 %s 找到可评审提交（无 姓名_挑战ID_部件 命名或必需文件）" % args.folder,
              file=sys.stderr)
        sys.exit(5)
    payload = json.dumps(res, ensure_ascii=False, indent=2)
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            fh.write(payload + "\n")
    print(payload)
    return 0


def cmd_review(args):
    _check_folder(args.folder)
    rubric = _load(args.rubric)
    problems = c4_eval.rubric_selfcheck(rubric)
    if problems:
        for p in problems:
            print("[E4] rubric 自检失败：%s" % p, file=sys.stderr)
        sys.exit(4)
    res = c4_eval.evaluate_folder(args.folder, rubric)
    if res["summary"]["submissions"] == 0:
        print("[E5] 未在 %s 找到可评审提交" % args.folder, file=sys.stderr)
        sys.exit(5)
    md = c4_report.md_report(res, title=args.title)
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(md + "\n")
        print("[OK] 评审报告 → %s（%d 份提交，平均分 %.2f）"
              % (args.out, res["summary"]["submissions"], res["summary"]["average_composite"]))
    else:
        print(md)
    if args.dashboard:
        os.makedirs(os.path.dirname(os.path.abspath(args.dashboard)), exist_ok=True)
        with open(args.dashboard, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(c4_report.dashboard(res), ensure_ascii=False, indent=2) + "\n")
        print("[OK] 看板数据 → %s" % args.dashboard)
    if args.history:
        c4_report.append_history(res, args.history)
        rows = c4_report.trend(args.history)
        print("[OK] 历史 → %s（累计 %d 次运行）" % (args.history, len(rows)))
    return 0


def cmd_rubric_check(args):
    rubric = _load(args.rubric)
    problems = c4_eval.rubric_selfcheck(rubric)
    if problems:
        for p in problems:
            print("[E4] %s" % p, file=sys.stderr)
        sys.exit(4)
    print("[OK] rubric v%s（challenge %s）自检通过：必交物 %d 项、质量判据 %d 条，rule 全部有实现。"
          % (rubric.get("version"), rubric.get("challenge"),
             len(rubric.get("required_deliverables") or {}),
             len(rubric.get("quality_criteria") or {})))
    return 0


def cmd_selfcheck(args):
    sys.path.insert(0, HERE)
    import c4_selfcheck
    return c4_selfcheck.main([])


def cmd_version(args):
    print("c4-skill-evaluator 1.0.0 (challenge C4A / ch-20260717031432-5jvqje)")
    print("python %s" % sys.version.split()[0])
    print("rubric default: %s" % DEFAULT_RUBRIC)
    return 0


def build_parser():
    p = argparse.ArgumentParser(prog="c4_evaluator.py",
                                description="C4A 技能提交自动评审器（零依赖）")
    p.add_argument("--rubric", default=DEFAULT_RUBRIC, help="rubric YAML 路径")
    sub = p.add_subparsers(dest="cmd")

    s = sub.add_parser("scan", help="只做采集+评分，输出 JSON")
    s.add_argument("folder")
    s.add_argument("--json", help="把 JSON 也写一份到该路径")
    s.set_defaults(func=cmd_scan)

    r = sub.add_parser("review", help="完整评审：Markdown 报告 + 可选看板/历史")
    r.add_argument("folder")
    r.add_argument("--out", help="Markdown 报告输出路径（缺省打印到 stdout）")
    r.add_argument("--dashboard", help="看板 JSON 输出路径")
    r.add_argument("--history", help="历史 JSONL 追加路径（多次运行看趋势）")
    r.add_argument("--title", default="C4A 技能提交自动评审报告")
    r.set_defaults(func=cmd_review)

    sub.add_parser("rubric-check", help="校验 rubric 与实现是否一致").set_defaults(func=cmd_rubric_check)
    sub.add_parser("selfcheck", help="跑内置用例自检（含负例）").set_defaults(func=cmd_selfcheck)
    sub.add_parser("version", help="打印版本与环境").set_defaults(func=cmd_version)
    return p


def main(argv=None):
    p = build_parser()
    args = p.parse_args(argv)
    if not getattr(args, "func", None):
        p.print_help()
        return 1
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
