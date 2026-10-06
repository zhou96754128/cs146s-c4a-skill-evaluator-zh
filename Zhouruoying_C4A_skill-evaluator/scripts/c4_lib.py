#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""c4_lib.py — 零依赖基础层：最小 YAML 读取器 + 文本/包读取 + 通用工具。

设计约束（见 方案设计 §2.2）：
  1) 只用 Python 标准库。若运行环境恰好装了 PyYAML，则优先用 PyYAML，
     否则退回到本文件自带的 mini_yaml_load()。
  2) 读取任何文件都必须带上限与异常兜底：评审器遇到的输入是别人交上来的
     东西，坏了也不能把评审器本身弄崩。
  3) 包内条目一律做路径安全校验（拒绝 '..' 与绝对路径），并限制单条目/总读取量。
"""
import hashlib
import io
import os
import re
import zipfile

TEXT_EXT = {".md", ".txt", ".py", ".yaml", ".yml", ".json", ".csv", ".sh",
            ".mjs", ".js", ".tex", ".html", ".rst", ".ini", ".cfg", ".log"}
PACKAGE_EXT = {".skill", ".zip"}
MAX_FILE_CHARS = 400_000
MAX_ENTRY_BYTES = 2_000_000
MAX_PACKAGE_BYTES = 8_000_000
SAFE_ENTRY = re.compile(r"^[^/\\][^\\]*$")


# --------------------------------------------------------------------------
# 最小 YAML 子集读取器（只覆盖本 rubric 用到的语法）
# --------------------------------------------------------------------------
def _unescape_double(s):
    out, i = [], 0
    while i < len(s):
        c = s[i]
        if c == "\\" and i + 1 < len(s):
            nxt = s[i + 1]
            out.append({"n": "\n", "t": "\t", '"': '"', "\\": "\\"}.get(nxt, nxt))
            i += 2
            continue
        out.append(c)
        i += 1
    return "".join(out)


def _split_inline(s):
    """把 [a, b, "c,d"] 切成元素列表，逗号在引号内不切。"""
    items, buf, quote, depth = [], [], None, 0
    for c in s:
        if quote:
            buf.append(c)
            if c == quote:
                quote = None
            continue
        if c in "\"'":
            quote = c
            buf.append(c)
        elif c == "[":
            depth += 1
            buf.append(c)
        elif c == "]":
            depth -= 1
            buf.append(c)
        elif c == "," and depth == 0:
            items.append("".join(buf))
            buf = []
        else:
            buf.append(c)
    if buf:
        items.append("".join(buf))
    return [x.strip() for x in items if x.strip()]


def _scalar(v):
    v = v.strip()
    if v == "":
        return None
    if len(v) >= 2 and v[0] == "'" and v[-1] == "'":
        return v[1:-1]
    if len(v) >= 2 and v[0] == '"' and v[-1] == '"':
        return _unescape_double(v[1:-1])
    if v.startswith("[") and v.endswith("]"):
        return [_scalar(x) for x in _split_inline(v[1:-1])]
    low = v.lower()
    if low in ("true", "yes"):
        return True
    if low in ("false", "no"):
        return False
    if low in ("null", "~"):
        return None
    if re.fullmatch(r"-?[0-9]+", v):
        return int(v)
    if re.fullmatch(r"-?[0-9]*\.[0-9]+", v):
        return float(v)
    return v


def _tokens(text):
    toks = []
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        toks.append((len(line) - len(line.lstrip(" ")), line.strip()))
    return toks


def _kv(content):
    idx = content.find(":")
    if idx < 0:
        return None
    return content[:idx].strip(), content[idx + 1:].strip()


def mini_yaml_load(text):
    """解析本 rubric 用到的 YAML 子集，返回 dict/list。"""
    toks = _tokens(text)

    def parse_block(i, indent):
        if i >= len(toks) or toks[i][0] < indent:
            return None, i
        is_list = toks[i][1].startswith("- ")
        node = [] if is_list else {}
        while i < len(toks) and toks[i][0] == indent:
            cur = toks[i][1]
            if is_list:
                if not cur.startswith("- "):
                    break
                item = cur[2:].strip()
                pair = _kv(item)
                if pair is None:
                    node.append(_scalar(item))
                    i += 1
                    continue
                key, val = pair
                entry = {}
                if val:
                    entry[key] = _scalar(val)
                    i += 1
                else:
                    nxt, j = parse_block(i + 1, indent + 2)
                    entry[key] = nxt if nxt is not None else {}
                    i = j
                # 继续吃掉属于同一 list item 的更深层 key: value
                while i < len(toks) and toks[i][0] > indent:
                    d = toks[i][0]
                    p = _kv(toks[i][1])
                    if p is None:
                        i += 1
                        continue
                    k2, v2 = p
                    if v2:
                        entry[k2] = _scalar(v2)
                        i += 1
                    else:
                        nxt, j = parse_block(i + 1, d + 2)
                        entry[k2] = nxt if nxt is not None else {}
                        i = j
                node.append(entry)
                continue
            pair = _kv(cur)
            if pair is None:
                i += 1
                continue
            key, val = pair
            if val:
                node[key] = _scalar(val)
                i += 1
            else:
                nxt, j = parse_block(i + 1, indent + 2)
                node[key] = nxt if nxt is not None else {}
                i = j
        return node, i

    data, _ = parse_block(0, toks[0][0] if toks else 0)
    return data if data is not None else {}


def load_yaml(path):
    with open(path, "r", encoding="utf-8") as fh:
        text = fh.read()
    try:
        import yaml  # 环境里有就优先用（本机没有，属可选增强）
        return yaml.safe_load(text), "pyyaml"
    except Exception:
        return mini_yaml_load(text), "mini"


def load_rubric(path):
    """加载 rubric → 语义完整的 dict（本技能唯一的 rubric 入口）。

    与 load_yaml 的分工：load_yaml 是通用读取器，返回 (data, engine)，供
    自检脚本直接点名要看解析引擎；而调用方（CLI / 编排层）只需要一个键齐全、
    形状正确的 dict，所以这里负责三件事：
      ① 解包——把 (data, engine) 收成一个对象；
      ② 兜底——缺省键补默认值，让下游不必到处写 .get(x) or {}；
      ③ 校验——坏 rubric 必须在这里就抛异常（上层转成退出码 3），
         而不是评审到一半才崩，那样错误会出现在学生作品上而不是 rubric 上。
    """
    data, engine = load_yaml(path)
    if not isinstance(data, dict):
        raise ValueError("rubric 顶层不是映射：%s" % type(data).__name__)
    rubric = dict(data)
    rubric.setdefault("version", "unknown")
    rubric.setdefault("challenge", "")
    sel = rubric.get("selector")
    sel = dict(sel) if isinstance(sel, dict) else {}
    sel.setdefault("filename_regex",
                   r"^(?P<author>[A-Za-z][A-Za-z0-9_\-]*)_"
                   r"(?P<challenge>C[0-9]+[A-Z]?[0-9]*)_(?P<part>.+)$")
    sel.setdefault("package_extensions", [".skill", ".zip"])
    sel.setdefault("unknown_author_label", "Unknown Author")
    sel.setdefault("challenge_filter", "")
    rubric["selector"] = sel
    rubric.setdefault("required_deliverables", {})
    rubric.setdefault("quality_criteria", {})
    rubric.setdefault("scoring", {})
    rubric.setdefault("suggestion_templates", {})
    if not isinstance(rubric["required_deliverables"], dict):
        raise ValueError("required_deliverables 不是映射")
    if not isinstance(rubric["quality_criteria"], dict) or not rubric["quality_criteria"]:
        raise ValueError("quality_criteria 为空或不是映射")
    try:
        re.compile(sel["filename_regex"])
    except re.error as exc:
        raise ValueError("filename_regex 非法：%s" % exc)
    rubric["_engine"] = engine
    return rubric


# --------------------------------------------------------------------------
# 文本读取
# --------------------------------------------------------------------------
def read_text(path):
    """返回 (text, note)。二进制/超大/不支持格式一律返回空串并给出原因。"""
    ext = os.path.splitext(path)[1].lower()
    if ext in PACKAGE_EXT:
        return "", "package"
    if ext == ".pdf":
        return "", "pdf-not-extracted"
    try:
        if ext == ".docx":
            with zipfile.ZipFile(path) as z:
                xml = z.read("word/document.xml").decode("utf-8", "replace")
            txt = re.sub(r"<[^>]+>", " ", xml)
            return re.sub(r"\s+", " ", txt)[:MAX_FILE_CHARS], "docx"
        if ext in TEXT_EXT or ext == "":
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                return fh.read(MAX_FILE_CHARS), "text"
        return "", "binary-skipped"
    except Exception as exc:  # 坏文件 / 无权限 / 编码异常
        return "", "read-error:%s" % type(exc).__name__


def sha256_of(path, limit=None):
    h = hashlib.sha256()
    total = 0
    with open(path, "rb") as fh:
        while True:
            chunk = fh.read(65536)
            if not chunk:
                break
            h.update(chunk)
            total += len(chunk)
            if limit and total >= limit:
                break
    return h.hexdigest()


def human_size(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return "%.0f %s" % (n, unit) if unit == "B" else "%.1f %s" % (n, unit)
        n /= 1024.0


# --------------------------------------------------------------------------
# 技能包读取（.skill / .zip）
# --------------------------------------------------------------------------
def read_package(path):
    """读取技能包。返回 dict：ok / reason / entries / rejected / root_files / dirs。"""
    out = {"ok": False, "reason": "", "entries": [], "rejected": [],
           "root_files": [], "dirs": []}
    if not zipfile.is_zipfile(path):
        out["reason"] = "not_a_zip"
        return out
    try:
        with zipfile.ZipFile(path) as z:
            total = 0
            for info in z.infolist():
                name = info.filename
                if name.endswith("/"):
                    out["dirs"].append(name.rstrip("/"))
                    continue
                if ".." in name.split("/") or not SAFE_ENTRY.match(name):
                    out["rejected"].append({"name": name, "reason": "unsafe-path"})
                    continue
                if info.file_size > MAX_ENTRY_BYTES:
                    out["rejected"].append({"name": name, "reason": "entry-too-large",
                                            "size": info.file_size})
                    continue
                if total + info.file_size > MAX_PACKAGE_BYTES:
                    out["rejected"].append({"name": name, "reason": "package-budget-exceeded"})
                    continue
                total += info.file_size
                ext = os.path.splitext(name)[1].lower()
                text = ""
                if ext in TEXT_EXT:
                    try:
                        text = z.read(info).decode("utf-8", "replace")
                    except Exception:
                        text = ""
                out["entries"].append({"name": name, "size": info.file_size,
                                       "text": text[:MAX_FILE_CHARS]})
        out["ok"] = True
        return out
    except Exception as exc:
        out["reason"] = "zip-error:%s" % type(exc).__name__
        return out


def package_structure(pkg):
    """判定包结构：SKILL.md 位置 + 顶层布局。返回 (verdict, detail)。"""
    names = [e["name"] for e in pkg["entries"]]
    if not names:
        return "empty", "包内没有可读文件"
    root_skill = "SKILL.md" in names
    tops = sorted({n.split("/")[0] for n in names})
    wrapped = None
    if not root_skill and len(tops) == 1 and (tops[0] + "/SKILL.md") in names:
        wrapped = tops[0]
    if not root_skill and wrapped is None:
        return "invalid", "未找到 SKILL.md（根目录或唯一顶层目录内都没有）"
    base = "" if root_skill else (wrapped or "") + "/"
    stray = []
    for n in names:
        rest = n[len(base):] if base and n.startswith(base) else n
        top = rest.split("/")[0]
        if "/" not in rest:
            if rest != "SKILL.md":
                stray.append(n)
        elif top not in ("scripts", "references"):
            stray.append(n)
    detail = ("SKILL.md 位于%s；顶层：%s" %
              ("根目录" if root_skill else "唯一子目录 %s/" % wrapped, ", ".join(tops)))
    if stray:
        return "loose", detail + "；越界文件：" + ", ".join(stray[:5])
    return "valid", detail


def first_heading(text):
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("#"):
            return s.lstrip("#").strip()
        if s:
            return s[:80]
    return ""


def now_iso():
    import datetime
    return datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def iter_submissions(folder, exts=None):
    """递归列出候选提交文件（跳过隐藏文件与临时产物）。"""
    for root, dirs, files in os.walk(folder):
        dirs[:] = [d for d in dirs if not d.startswith(".") and d != "__pycache__"]
        for name in sorted(files):
            if name.startswith("."):
                continue
            if name.endswith((".pyc", ".DS_Store")):
                continue
            path = os.path.join(root, name)
            if exts and os.path.splitext(name)[1].lower() not in exts:
                continue
            yield path
