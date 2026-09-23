# -*- coding: utf-8 -*-
"""ตัวอ่าน YAML ชุดย่อย — ใช้เมื่อเครื่องไม่มี PyYAML เท่านั้น (มีก็ใช้ yaml.safe_load ก่อนเสมอ)

รองรับเฉพาะสิ่งที่ไฟล์ config ของ Decision Engine ใช้จริง:
  mapping ซ้อนด้วยการย่อหน้า · list แบบ "- item" · inline list [a, b] · inline map {a: 1, b: 2}
  · scalar (int/float/bool/null/สตริงมีหรือไม่มีเครื่องหมายคำพูด) · คอมเมนต์ "#"
ไม่รองรับ anchor/alias/multi-line string — ไฟล์ config ของเราไม่ใช้ของพวกนั้น
"""


def _strip_comment(line):
    out, q = [], None
    for ch in line:
        if q:
            out.append(ch)
            if ch == q:
                q = None
            continue
        if ch in ("'", '"'):
            q = ch
        elif ch == "#":
            break
        out.append(ch)
    return "".join(out).rstrip()


def _split_top(s, sep=","):
    parts, depth, q, cur = [], 0, None, []
    for ch in s:
        if q:
            cur.append(ch)
            if ch == q:
                q = None
            continue
        if ch in ("'", '"'):
            q = ch
        elif ch in "[{":
            depth += 1
        elif ch in "]}":
            depth -= 1
        if ch == sep and depth == 0:
            parts.append("".join(cur).strip())
            cur = []
            continue
        cur.append(ch)
    tail = "".join(cur).strip()
    if tail:
        parts.append(tail)
    return parts


def _depth(s):
    q, depth = None, 0
    for ch in s:
        if q:
            if ch == q:
                q = None
            continue
        if ch in ("'", '"'):
            q = ch
        elif ch in "[{":
            depth += 1
        elif ch in "]}":
            depth -= 1
    return depth


def _find_colon(s):
    q, depth = None, 0
    for i, ch in enumerate(s):
        if q:
            if ch == q:
                q = None
            continue
        if ch in ("'", '"'):
            q = ch
        elif ch in "[{":
            depth += 1
        elif ch in "]}":
            depth -= 1
        elif ch == ":" and depth == 0 and (i + 1 == len(s) or s[i + 1] == " "):
            return i
    return -1


def scalar(s):
    s = s.strip()
    if not s:
        return None
    if s[0] == "[" and s[-1] == "]":
        return [scalar(p) for p in _split_top(s[1:-1])]
    if s[0] == "{" and s[-1] == "}":
        out = {}
        for p in _split_top(s[1:-1]):
            i = _find_colon(p)
            out[_key(p[:i])] = scalar(p[i + 1:])
        return out
    if s[0] in ("'", '"') and s[-1] == s[0]:
        return s[1:-1]
    low = s.lower()
    if low in ("true", "yes", "on"):
        return True
    if low in ("false", "no", "off"):
        return False
    if low in ("null", "none", "~"):
        return None
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        return s


def _key(s):
    s = s.strip()
    if s and s[0] in ("'", '"') and s[-1] == s[0]:
        return s[1:-1]
    if s.lstrip("-").isdigit():
        return int(s)
    return s


def loads(text):
    lines = []
    pending, depth = None, 0
    for raw in text.splitlines():
        line = _strip_comment(raw)
        if not line.strip():
            continue
        if pending is not None:
            # inline [..] / {..} ที่ขึ้นบรรทัดใหม่ — ต่อจนวงเล็บปิดครบ
            pending = (pending[0], pending[1] + " " + line.strip())
        else:
            pending = (len(line) - len(line.lstrip(" ")), line.strip())
        depth = _depth(pending[1])
        if depth <= 0:
            lines.append(pending)
            pending = None
    if pending is not None:
        lines.append(pending)
    value, _ = _block(lines, 0, lines[0][0] if lines else 0)
    return value if value is not None else {}


def _block(lines, i, indent):
    if i >= len(lines):
        return None, i
    if lines[i][1].startswith("- ") or lines[i][1] == "-":
        return _list(lines, i, indent)
    return _map(lines, i, indent)


def _map(lines, i, indent):
    out = {}
    while i < len(lines) and lines[i][0] == indent and not lines[i][1].startswith("- "):
        text = lines[i][1]
        c = _find_colon(text)
        if c < 0:
            raise ValueError(f"yamlish: บรรทัดไม่มี ':' → {text!r}")
        key, rest = _key(text[:c]), text[c + 1:].strip()
        i += 1
        if rest:
            out[key] = scalar(rest)
        elif i < len(lines) and lines[i][0] > indent:
            out[key], i = _block(lines, i, lines[i][0])
        elif i < len(lines) and lines[i][0] == indent and lines[i][1].startswith("- "):
            out[key], i = _list(lines, i, indent)
        else:
            out[key] = None
    return out, i


def _list(lines, i, indent):
    out = []
    while i < len(lines) and lines[i][0] == indent and lines[i][1].startswith("-"):
        rest = lines[i][1][1:].strip()
        i += 1
        if not rest:
            val, i = _block(lines, i, lines[i][0]) if i < len(lines) and lines[i][0] > indent \
                else (None, i)
            out.append(val)
        elif _find_colon(rest) > 0 and rest[0] not in "[{'\"":
            # "- key: v" ตามด้วย key อื่นที่ย่อหน้าลึกกว่า = map หนึ่งก้อน
            sub = [(indent + 2, rest)]
            while i < len(lines) and lines[i][0] > indent:
                sub.append(lines[i])
                i += 1
            val, _ = _map(sub, 0, indent + 2)
            out.append(val)
        else:
            out.append(scalar(rest))
    return out, i
