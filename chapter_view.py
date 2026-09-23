# -*- coding: utf-8 -*-
"""หน้าอ่านนิยายแบบ "ลูป" — แปลงสมุดชีวิตของตัวละครหนึ่งคนเป็นบทที่อ่านเรียงได้

    python chapter_view.py out/minds-compare-6/journal.jsonl --cid 5 --loops 1

ทำไมต้องมีไฟล์นี้: บันทึก (journal.jsonl) เป็นข้อมูลดิบเรียงตามเวลาของทุกคนปนกัน อ่านเอาเรื่อง
ไม่ได้ ส่วนโครงที่อ่านเป็นเรื่องได้คือ **ลูปสามช่วงเวลา** ที่โลกเดินอยู่จริงแล้ว (ดู events.SCALE_OF):
    รายวัน (ปะทะ/สังคม) → รายเดือน (เดินทาง/แดนลับ/อาชีพรอง) → รายปี (ปิดด่าน/ทะลวงขั้น)
ไฟล์นี้จึงตัดบันทึกเป็นลูปตามจังหวะนั้น โดย **ไม่แต่งอะไรเพิ่มเลย** ทุกบรรทัดมาจากเหตุการณ์จริง
ในโลก — ที่เพิ่มให้คือหัวข้อ วันที่ และการสรุปผลท้ายลูป
"""
import argparse
import json
from collections import Counter

YEAR_KINDS = {"ปิดด่าน", "บำเพ็ญ", "ข้ามขั้น", "ข้ามฟ้า", "ซ่อนตัว", "ขัดเกลาสายเลือด",
              "สงครามเบิกฟ้า", "ออกจากด่าน"}
MONTH_KINDS = {"เดินทาง", "ค้นแดนลับ", "เก็บวัตถุดิบ", "ล่าอสูร", "หลอมยา", "หลอมอาวุธ",
               "หลอมค่ายกล", "ฝึกวิชา", "เข้าสำนัก", "ตั้งสำนัก", "ลงโลกล่าง",
               "สงครามสำนัก", "สะสมบุญบารมี", "กำเนิดทายาท"}


def scale_of(row):
    if row.get("type") == "story":
        return "ปี" if (row.get("action") or "") in YEAR_KINDS else "วัน"
    if row.get("scale"):
        return row["scale"]
    k = row.get("action") or ""
    if k in YEAR_KINDS:
        return "ปี"
    if k in MONTH_KINDS:
        return "เดือน"
    return "วัน"


def date_words(day):
    y, doy = divmod(max(0, int(day or 0)), 365)
    m = min(12, doy // 30 + 1)
    return y, m, doy - (m - 1) * 30 + 1


def load(path, cid=None, name=None):
    rows = [json.loads(l) for l in open(path, encoding="utf-8")]
    if cid is None and name is None:
        # เลือกคนที่มีบรรทัดมากที่สุด = ชีวิตที่มีเนื้อให้เล่าที่สุด
        who = Counter(r["cid"] for r in rows if r.get("cid") is not None)
        cid = who.most_common(1)[0][0]
    mine = [r for r in rows
            if (cid is not None and r.get("cid") == cid) or (name and r.get("name") == name)]
    mine.sort(key=lambda r: (r.get("day") or 0, r.get("seq") or 0))
    return rows, mine


# ความประหลาดใจขั้นต่ำที่จะถือว่าเป็น "จุดพลิก" — 4 บิต = เหตุการณ์ที่โอกาสเกิดราว 6%
# ต่ำกว่านี้คือเรื่องที่เกิดได้เป็นปกติ ไม่ควรถูกยกขึ้นมาเป็นไคลแมกซ์ของบท
SURPRISE_BAR = 4.0


def collapse(rows, cap=12):
    """ยุบบรรทัดซ้ำ — บันทึกดิบมีทั้งภัยพิบัติตามฤดูที่วนทุกปีและการให้สัญญากับคนเดิมซ้ำๆ
    อ่านเป็นเรื่องแล้วมันกลบเนื้อเรื่องจริง จึงยุบให้เหลือครั้งเดียวพร้อมจำนวนครั้ง"""
    seen, out = {}, []
    for r in rows:
        key = (r.get("action"), r.get("outcome"), r.get("target") or r.get("by"))
        if key in seen:
            seen[key]["n"] += 1
            continue
        seen[key] = {"row": r, "n": 1}
        out.append(seen[key])
    lines = []
    for item in out[:cap]:
        line = line_of(item["row"])
        if item["n"] > 1:
            line += f"  (เกิดซ้ำอีก {item['n'] - 1} ครั้งในช่วงนี้)"
        lines.append(line)
    if len(out) > cap:
        lines.append(f"  · …และอีก {len(out) - cap} เรื่องย่อยในช่วงเดียวกัน")
    return lines


def split_loops(mine):
    """ตัดเป็นลูป — ลูปหนึ่งจบเมื่อเจอจังหวะรายปี (ปิดด่าน/ทะลวงขั้น/ข้ามฟ้า) แล้วเริ่มลูปใหม่"""
    loops, cur = [], []
    for r in mine:
        cur.append(r)
        if scale_of(r) != "ปี" or r["type"] not in ("decision", "event"):
            continue
        # การปิดด่านยังไม่จบลูป — ลูปจบตอน "ออกจากด่าน" เพราะรายงานโลกที่เปลี่ยนไปคือผลของลูปนี้
        if r.get("action") == "ปิดด่าน":
            continue
        loops.append(cur)
        cur = []
    if cur:
        loops.append(cur)
    return loops


def line_of(r):
    y, m, dd = date_words(r.get("day"))
    when = f"วันที่ {dd} เดือน {m}"
    who = r.get("by") or r.get("target") or ""
    text = (r.get("text") or "").strip()
    if r["type"] == "decision":
        why = (r.get("why") or "").strip()
        head = f"{r.get('action')}" + (f" กับ{who}" if who else "")
        tail = f" — {r.get('outcome')}: {text}" if text else f" — {r.get('outcome')}"
        return f"  · {when}: [{head}]{tail}" + (f"\n      เหตุผลในใจ: {why}" if why else "")
    if r["type"] == "received":
        return f"  · {when}: {who} {r.get('action')} ข้า — {r.get('outcome')}: {text}"
    if r["type"] == "event":
        return f"  · {when}: {r.get('action')} — {r.get('outcome')}: {text}"
    if r["type"] == "death":
        return f"  · {when}: **{text}**"
    return f"  · {when}: {text}"


def render(path, cid=None, name=None, loops=1, start=1):
    rows, mine = load(path, cid, name)
    if not mine:
        return "ไม่พบตัวละครนี้ในบันทึก"
    who = mine[0]["name"]
    out = [f"# ชีวิตของ{who} — อ่านจากบันทึกโลกจริง ({path})", ""]
    all_loops = split_loops(mine)
    pick = all_loops[start - 1: start - 1 + loops]
    for i, loop in enumerate(pick, start):
        body = [r for r in loop if r["type"] != "story"]
        days = [r for r in body if scale_of(r) == "วัน"]
        months = [r for r in body if scale_of(r) == "เดือน"]
        years = [r for r in body if scale_of(r) == "ปี"]
        y0 = date_words(loop[0].get("day"))[0]
        y1 = date_words(loop[-1].get("day"))[0]
        out += [f"**[ระบบเริ่มการจำลองลูปที่ {i}]** (ปีที่ {y0} – {y1})", ""]
        if days:
            out.append(f"*   **ช่วงเวลารายวัน** ({len(days)} เหตุการณ์)")
            out += collapse(days)
        if months:
            out.append(f"*   **ช่วงเวลารายเดือน** ({len(months)} เหตุการณ์)")
            out += collapse(months, cap=8)
        if years:
            out.append("*   **ช่วงเวลารายปี**")
            out += collapse(years, cap=6)
        # ไคลแมกซ์ของบท — เลือกจากความประหลาดใจ ไม่ใช่จากลำดับเวลา
        # ก่อนหน้านี้หน้าอ่านตัดตอนด้วย "ช่วงเวลารายปี" ซึ่งเป็นเกณฑ์เชิงเวลาล้วนๆ
        # เหตุการณ์ที่โอกาสเกิด 4% กับ 90% จึงถูกเล่าด้วยน้ำหนักเท่ากัน
        # ตอนนี้เอนจินพกค่า -log2(p) มาให้ทุกบรรทัดแล้ว (ดู physics.surprisal)
        peak = max(body, key=lambda r: float(r.get("surprise") or 0.0), default=None)
        if peak is not None and float(peak.get("surprise") or 0) >= SURPRISE_BAR:
            out += ["*   **จุดพลิกของลูปนี้** "
                    f"(ความประหลาดใจ {float(peak['surprise']):.1f} บิต — "
                    f"สิ่งที่แทบไม่น่าเกิดขึ้นได้)",
                    f"    *   {peak.get('text') or peak.get('action') or ''}"]
        last = loop[-1]
        det = last.get("details") or {}
        # บรรทัดสุดท้ายอาจเป็นเหตุการณ์ที่ไม่มีข้อมูลตัวละครติดมา (เช่น "ออกจากด่าน") จึงถอย
        # ไปหาบรรทัดล่าสุดที่มีขั้นพลัง/ใจ/เป้าหมายจริง เพื่อไม่ให้สรุปท้ายลูปว่างเป็นขีด
        def latest(key):
            for r in reversed(loop):
                if r.get(key):
                    return r[key]
            return "-"
        out += ["*   **ผลลัพธ์เมื่อจบลูป:**",
                f"    *   ระดับพลังปัจจุบัน: {latest('realm')}"
                + (f" · {det.get('ขั้นของข้าตอนนี้')}" if det.get("ขั้นของข้าตอนนี้") else ""),
                f"    *   ใจตอนนี้: {latest('heart')}",
                f"    *   เป้าหมายชีวิต: {latest('long_goal')}"]
        got = [f"{k}: {v}" for k, v in det.items()
               if k in ("ที่ได้จากด่าน", "วิชา", "ของที่ประมูล", "ที่ได้ไป", "สิ่งที่เพิ่งรู้")]
        if got:
            out.append("    *   ไอเทม/วิชา/ความรู้ที่ได้รับ: " + " · ".join(got))
        if det.get("โลกที่เปลี่ยนไป"):
            out.append(f"    *   สถานการณ์ภายนอกที่เปลี่ยนไป: {det['โลกที่เปลี่ยนไป']}")
        if det.get("คนที่ไม่ได้อยู่รอเขา"):
            out.append(f"    *   คนที่ไม่ได้อยู่รอเขา: {det['คนที่ไม่ได้อยู่รอเขา']}")
        if det.get("คนที่ไต่แซงไปแล้ว"):
            out.append(f"    *   คนที่ไต่แซงไปแล้ว: {det['คนที่ไต่แซงไปแล้ว']}")
        story = next((r for r in reversed(loop) if r["type"] == "story"), None)
        if story and (story.get("story") or story.get("text")):
            out += ["", "    *   **ฉากที่ถูกเขียนเป็นเรื่องเล่าในลูปนี้:**", "",
                    "        " + (story.get("story") or story["text"]).replace("\n", "\n        ")]
        out += ["", "---", ""]
    out.append(f"(ตัวละครนี้มีทั้งหมด {len(all_loops)} ลูปในบันทึก)")
    return "\n".join(out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("journal")
    ap.add_argument("--cid", type=int, default=None)
    ap.add_argument("--name", default=None)
    ap.add_argument("--loops", type=int, default=1)
    ap.add_argument("--start", type=int, default=1)
    args = ap.parse_args()
    print(render(args.journal, args.cid, args.name, args.loops, args.start))
