"""วัยเด็ก (อายุ 0–13) เป็นกิจวัตรรายปีที่ถูกขัดจังหวะได้ — แบบ §7.2

เด็กไม่เข้าเมนูของผู้ใหญ่เลย (Sim._step ส่งทุกคนที่อายุต่ำกว่า 14 มาที่ `turn` ที่เดียว) ในเทิร์นวันเกิด
เด็กเลือกกิจวัตรหนึ่งอย่างตามช่วงวัย แล้วทำไปจนวันเกิดถัดไปเป็น ActionProcess("upbringing") ผลคิดตามวันที่ทำจริง
(`accrue` ผ่าน Sim.accrue_process) ถูกขัดจังหวะเมื่อผู้ปกครองเปลี่ยน หิว หรือหมดสติ แล้วเลือกใหม่วันนั้น

ช่วงวัยและกิจวัตร (ขั้น A: ความผูกพันและเรื่องเล่า ยังไม่แตะเศรษฐกิจ):
- 0–2 ได้รับการเลี้ยงดู — ผูกพันกับผู้ดูแล ไม่มีตัวเลือก
- 3–13 เล่นกับเด็กที่อยู่ที่เดียวกัน (ผูกพันกันสองทาง) / เรียนรู้ที่บ้านกับผู้ดูแล / พัก

การสุ่มใช้สตรีมที่ผูกกับ (seed, cid, วันเริ่ม) ไม่ดึงจาก rng หลักของโลก การเพิ่มระบบนี้จึงไม่เลื่อนลำดับสุ่มของโลก
"""
import random

from . import config as C

CARE, PLAY, HOME, REST = "ได้รับการเลี้ยงดู", "เล่นกับเพื่อน", "เรียนรู้ที่บ้าน", "พักผ่อน"
BAND_OUTCOME = ((2, "ได้รับการเลี้ยงดู"), (6, "เรียนรู้โลก"), (10, "ช่วยครอบครัว"), (13, "เตรียมเติบใหญ่"))
MAX_PLAYMATES = 3


def _rng(sim, child):
    return random.Random((getattr(sim, "seed", 0) << 32) ^ (child.cid << 20) ^ sim.day ^ 0xC41D)


def carer(sim, child):
    """ผู้ดูแลที่อยู่ด้วยจริง: ผู้ปกครอง ไม่มีก็พ่อแม่ที่ยังมีชีวิตและอยู่แดนเดียวกัน"""
    cast = sim.cast
    cids = ([child.guardian] if getattr(child, "guardian", -1) >= 0 else []) + list(child.parents or ())
    for cid in cids:
        if 0 <= cid < len(cast) and cast[cid].alive and cast[cid].world_id == child.world_id:
            return cast[cid]
    return None


def playmates(sim, child):
    day = sim.day
    return [c for c in sim.living_in(child.world_id)
            if c.cid != child.cid and c.place == child.place and 3 <= c.age(day) < 14]


def choose(sim, child, rng):
    """(กิจวัตร, คนที่ทำด้วย) — น้ำหนักตามสิ่งที่มีอยู่รอบตัวจริง ไม่มีเพื่อนก็เล่นไม่ได้ ไม่มีผู้ดูแลก็เรียนที่บ้านไม่ได้"""
    age = child.age(sim.day)
    home = carer(sim, child)
    if age <= 2:
        return CARE, [home.cid] if home is not None else []
    friends = playmates(sim, child)
    options = [(REST, 0.5, [])]
    if friends:
        pick = sorted(friends, key=lambda c: (-child.bonds.get(c.cid, 0), c.cid))[:MAX_PLAYMATES]
        options.append((PLAY, 2.0, [c.cid for c in pick]))
    if home is not None:
        options.append((HOME, 2.0 if home.place == child.place else 0.5, [home.cid]))
    roll = rng.random() * sum(w for _, w, _ in options)
    for routine, w, with_ in options:
        roll -= w
        if roll < 0:
            return routine, with_
    return options[-1][0], options[-1][2]


def start(sim, child, end_day, rng):
    routine, with_ = choose(sim, child, rng)
    p = sim.start_process(child, "upbringing", end_day - sim.day,
                          {"routine": routine, "with": with_, "guardian": getattr(child, "guardian", -1),
                           "carry": {}}, C.CHILD_BOND_PER_YEAR)
    return p


def accrue(sim, child, p, days):
    """ผูกพันตามวันที่ทำจริง — สะสมเศษไว้ใน payload แล้วเพิ่มเป็นจำนวนเต็ม (bonds เป็นจำนวนเต็มทั้งเอนจิน)"""
    if p.payload["routine"] == REST:
        return
    carry = p.payload["carry"]
    gain = days / 365.0 * p.yield_rate
    for cid in p.payload["with"]:
        other = sim.cast[cid]
        if not other.alive:
            continue
        total = carry.get(cid, 0.0) + gain
        whole = int(total)
        carry[cid] = total - whole
        if whole:
            child.bonds[cid] = child.bonds.get(cid, 0) + whole
            other.bonds[child.cid] = other.bonds.get(child.cid, 0) + whole


def broken(sim, child, p):
    """เหตุที่กิจวัตรนี้ไปต่อไม่ได้ (None = ไปต่อได้) — ตรวจทุกรอบนาฬิกาโลก"""
    if getattr(child, "guardian", -1) != p.payload.get("guardian", -1):
        return "ผู้ปกครองเปลี่ยน"
    if p.payload["routine"] in (CARE, HOME) and any(not sim.cast[c].alive for c in p.payload["with"]):
        return "ผู้ดูแลจากไป"
    return None


def turn(sim, child, world, elapsed, rng):
    """เทิร์นของเด็ก: เลือกกิจวัตรถึงวันเกิดถัดไป บันทึกหนึ่งเรื่องต่อปีของอายุ แล้วนัดเทิร์นถัดไปใกล้วันเกิด"""
    age = max(0, child.age(sim.day))
    next_birthday = child.born_day + (age + 1) * 365
    p = start(sim, child, next_birthday, _rng(sim, child))
    routine, with_ = p.payload["routine"], p.payload["with"]
    names = "และ".join(sim.cast[c].name for c in with_[:2])
    outcome = next(o for top, o in BAND_OUTCOME if age <= top)
    if routine == CARE:
        text = f"{child.name}เติบโตในอ้อมอกของ{names}" if names else f"{child.name}วัย {age} ปี เติบโตโดยไม่มีผู้ดูแลอยู่ใกล้"
    elif routine == PLAY:
        text = f"{child.name}วัย {age} ปี เล่นซนกับ{names}จนสนิทกัน"
    elif routine == HOME:
        text = f"{child.name}วัย {age} ปี เรียนรู้ผู้คนและวิถีชีวิตจาก{names}"
    else:
        text = f"{child.name}วัย {age} ปี ใช้เวลาเงียบๆ เติบโตตามวัย"
    if carer(sim, child) is None and age > 2:
        outcome = "เติบโตโดยไร้ผู้ปกครอง"
    event = sim.emit(world, "เติบโต", child, None, ["วัยเด็ก"], outcome, text, elapsed,
                     {"อายุ": f"{age} ปี", "กิจวัตร": routine})
    history = getattr(child, "childhood", None)
    if not isinstance(history, list):
        history = child.childhood = []
    if not any(h.get("age") == age for h in history if isinstance(h, dict)):
        history.append({"day": sim.day, "age": age, "text": text, "place": child.place,
                        "outcome": outcome, "routine": routine, "seq": event.seq})
        del history[:-14]
    # กลับมาอีกครั้งใกล้วันเกิดถัดไป (ตัวคลาดเคลื่อนจาก rng ของโลกเหมือนเดิม) — ถูกขัดจังหวะก็ได้เทิร์นเร็วกว่านี้
    sim.schedule(child, max(30, next_birthday - sim.day + rng.randint(0, 30)))
    return event
