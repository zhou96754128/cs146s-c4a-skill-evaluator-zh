#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""c4_scan.py — Level 1 采集器 + Level 2 完整性检查器。

职责（对应 方案设计 §3.1 / §3.2）：
  L1  scan_folder()   递归扫描群文件夹 → 识别作者/挑战/用途 → 按 (作者,挑战) 归并为提交包
  L2  completeness()  对每个提交包检查 C4 五个必交物是否齐全
输入：一个文件夹路径 + rubric。输出：纯 dict/list，可 JSON 序列化。
"""
import os
import re

from c4_lib import (PACKAGE_EXT, first_heading, human_size, read_package,
                    read_text, sha256_of)

GENERIC_DIRS = {"c4", "c4a", "c4b", "c4c", "c4d", "materials", "submissions",
                "提交", "群文件", "downloads", "download", "files", "wechat",
                "attachments", "src", "docs"}
NAME_RE = re.compile(r"(?:作者|Author|姓名)\s*[:：]\s*([A-Za-z\u4e00-\u9fa5][\w\u4e00-\u9fa5\-]{1,20})")
ID_RE = re.compile(r"\b(2025[0-9]{9}|20[0-9]{8,11})\b")


def parse_filename(stem, rubric):
    rx = re.compile(rubric["selector"]["filename_regex"])
    m = rx.match(stem)
    if not m:
        return None
    return {"author": m.group("author"), "challenge": m.group("challenge"),
            "part": m.group("part")}


def resolve_author(rel, text, inner_names, rubric):
    """返回 (author, method)。四级回退，最终落 Unknown Author 并标人工复核。"""
    stem = os.path.splitext(os.path.basename(rel))[0]
    hit = parse_filename(stem, rubric)
    if hit:
        return hit["author"], "filename"
    parts = rel.split(os.sep)[:-1]
    for seg in reversed(parts):
        if seg.lower() in GENERIC_DIRS:
            continue
        # 目录名只有当它长得像「姓名拼音」或「姓名拼音_C4_描述」时才当作者；
        # 形如 mystery_submission 这类主题词目录一律不猜，落 Unknown Author 交人工复核。
        hitdir = parse_filename(seg, rubric)
        if hitdir:
            return hitdir["author"], "subfolder"
        if re.fullmatch(r"[A-Za-z\u4e00-\u9fa5][A-Za-z\u4e00-\u9fa5\-]{1,19}", seg):
            return seg, "subfolder"
    m = NAME_RE.search(text[:4000])
    if m:
        return m.group(1), "content"
    for n in inner_names:
        m = NAME_RE.search(n)
        if m:
            return m.group(1), "package-name"
    return rubric["selector"]["unknown_author_label"], "unknown"


def scan_folder(folder, rubric):
    """扫描文件夹，返回 {records, bundles, warnings}。"""
    if not os.path.isdir(folder):
        raise NotADirectoryError(folder)
    want = (rubric["selector"].get("challenge_filter") or "").upper()
    records, warnings = [], []
    for root, dirs, files in os.walk(folder):
        dirs[:] = [d for d in dirs if not d.startswith(".") and d != "__pycache__"]
        for name in sorted(files):
            if name.startswith(".") or name.endswith((".pyc", ".DS_Store")):
                continue
            path = os.path.join(root, name)
            rel = os.path.relpath(path, folder)
            stem, ext = os.path.splitext(name)
            ext = ext.lower()
            rec = {"path": path, "rel": rel, "name": name, "ext": ext,
                   "size": os.path.getsize(path), "author": None, "author_method": None,
                   "challenge": None, "challenge_method": None, "part": stem,
                   "text": "", "note": "",
                   "package": None, "structure": None, "student_id": None,
                   "needs_manual_review": False}
            hit = parse_filename(stem, rubric)
            if hit:
                rec["author"], rec["author_method"] = hit["author"], "filename"
                rec["challenge"], rec["part"] = hit["challenge"].upper(), hit["part"]
                rec["challenge_method"] = "filename"
            if ext in PACKAGE_EXT:
                pkg = read_package(path)
                rec["package"] = {k: pkg[k] for k in ("ok", "reason", "rejected")}
                rec["package"]["entry_names"] = [e["name"] for e in pkg["entries"]]
                if pkg["ok"]:
                    rec["text"] = "\n".join(e["text"] for e in pkg["entries"] if e["text"])
                    rec["note"] = "package"
                else:
                    rec["note"] = "package-invalid:%s" % pkg["reason"]
                    warnings.append("技能包无法解析：%s（%s）" % (rel, pkg["reason"]))
                if pkg["rejected"]:
                    warnings.append("技能包内有条目被安全策略拒绝：%s → %s"
                                    % (rel, pkg["rejected"]))
            else:
                rec["text"], rec["note"] = read_text(path)
            if not rec["author"]:
                rec["author"], rec["author_method"] = resolve_author(
                    rel, rec["text"], rec["package"]["entry_names"] if rec["package"] else [], rubric)
            if rec["author"] == rubric["selector"]["unknown_author_label"]:
                rec["needs_manual_review"] = True
                warnings.append("无法确定作者，已标人工复核：%s" % rel)
            if not rec["challenge"]:
                rec["challenge"], rec["challenge_method"] = infer_challenge(rec, want)
            m = ID_RE.search(rec["text"][:4000]) or ID_RE.search(rel)
            if m:
                rec["student_id"] = m.group(1)
            rec["sha256"] = sha256_of(path) if rec["size"] <= 20_000_000 else ""
            rec["size_h"] = human_size(rec["size"])
            rec["title"] = first_heading(rec["text"])
            records.append(rec)
    bundles = group_bundles(records, want)
    return {"records": records, "bundles": bundles, "warnings": warnings}


CHAL_TOKEN_RE = re.compile(r"C\d+(?:[A-H]\d*)?", re.IGNORECASE)
C4_FAMILY = ("C4", "C4A", "C4B", "C4C", "C4D")


def chal_tokens(s):
    """抽出文本里的挑战号标记（C4 / C4A / C2G / C10H…），统一大写。"""
    return [m.group(0).upper() for m in CHAL_TOKEN_RE.finditer(s or "")]


def infer_challenge(rec, want):
    """文件名没写挑战号时，按文件名/内容推断，返回 (challenge, "inferred")。

    优先级：① 文件名里出现 C4 家族标记 → 归该标记；② 文件名里写的是别的挑战号
    （如 c2a-…、cs146s-c2g-…）→ 如实登记该挑战号，该提交会落到「不在目标挑战范围内」
    清单，只登记不排名；③ 才用内容/扩展名启发式。
    推断值一律带 method 标记，报告里会写成「C4B（推断）」，绝不冒充实测到的挑战号。
    """
    text = rec["text"]
    toks = chal_tokens(rec["name"])
    for t in toks:
        if t in C4_FAMILY:
            return t, "inferred"
    if toks:
        return toks[0], "inferred"
    if re.search(r"C4A", text[:2000]) or "评审" in text[:2000]:
        return "C4A", "inferred"
    if "wechat" in rec["name"].lower() or "公众号" in text[:2000]:
        return "C4B", "inferred"
    if rec["ext"] in PACKAGE_EXT or "skill" in rec["name"].lower():
        return (want or "unknown"), "inferred"
    return "unknown", "inferred"


def group_bundles(records, want):
    """按 (作者, 挑战) 归并，并判定该提交是否落在 challenge_filter 的目标范围内。

    范围判定用「前缀家族」语义：filter=C4 时 C4 / C4A / C4B / C4C / C4D 都算命中；
    C2A / C5 这类不属于 C4 家族的提交判为 out-of-scope，只登记不参与排名与班级统计。
    挑战号来源一并登记（filename=文件名实测 / inferred=推断 / unknown=无法判定）。
    """
    bundles = {}
    for rec in records:
        chal = rec["challenge"] or "unknown"
        key = (rec["author"], chal)
        b = bundles.setdefault(key, {"author": rec["author"], "challenge": chal,
                                     "challenge_method": rec["challenge_method"] or "unknown",
                                     "files": [], "manual_review": False,
                                     "student_id": None})
        if rec["challenge_method"] == "filename":
            b["challenge_method"] = "filename"
        b["files"].append(rec)
        b["manual_review"] = b["manual_review"] or rec["needs_manual_review"]
        b["student_id"] = b["student_id"] or rec["student_id"]
    out = []
    for key in sorted(bundles):
        b = bundles[key]
        b["file_count"] = len(b["files"])
        b["total_size"] = sum(f["size"] for f in b["files"])
        b["total_size_h"] = human_size(b["total_size"])
        b["in_scope"] = bool(b["challenge"] != "unknown" and
                             (not want or b["challenge"].startswith(want)))
        out.append(b)
    return out


def completeness(bundle, rubric):
    """L2：五个必交物逐项检测 + 唯一分配（一个文件不重复顶两个槽位）。"""
    slots = rubric["required_deliverables"]
    files = [f for f in bundle["files"] if not f["name"].startswith("_")]
    cands = {sid: [] for sid in slots}
    for f in files:
        low = f["name"].lower()
        inner = " ".join(f["package"]["entry_names"]) if f["package"] else ""
        haystack = (low + " " + inner.lower())
        for sid, spec in slots.items():
            why = None
            for p in spec.get("filename_patterns") or []:
                if p.lower() in haystack:
                    why = ("filename", p)
                    break
            if not why and f["ext"] in (spec.get("extensions") or []):
                for s in spec.get("content_signals") or []:
                    if s.lower() in f["text"].lower():
                        why = ("content", s)
                        break
            if not why and f["ext"] == ".png" and sid == "demo":
                why = ("extension", ".png")
            if why:
                cands[sid].append((0 if why[0] == "filename" else 1, f, why))
    for sid in cands:
        cands[sid].sort(key=lambda t: t[0])
    taken, result = set(), {}
    for sid in slots:
        pick = None
        for _, f, why in cands[sid]:
            if id(f) not in taken:
                pick = (f, why)
                break
        if pick:
            taken.add(id(pick[0]))
            result[sid] = {"present": True, "file": pick[0]["rel"],
                           "matched_by": pick[1][0], "signal": pick[1][1]}
        else:
            result[sid] = {"present": False, "file": None,
                           "matched_by": None, "signal": None}
    present = sum(1 for v in result.values() if v["present"])
    return {"slots": result, "files_present": present, "files_total": len(slots),
            "completeness_score": round(present / float(len(slots)), 4),
            "missing": [k for k, v in result.items() if not v["present"]]}
