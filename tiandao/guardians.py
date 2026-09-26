# -*- coding: utf-8 -*-
"""ผู้ปกครองเด็ก — เด็กทุกคนต้องมีผู้ใหญ่ที่รับผิดชอบ และความรับผิดชอบนั้นส่งต่อเมื่อผู้ใหญ่ตาย

    from tiandao import guardians as GUARD

ก่อนมีไฟล์นี้ เด็กมีแค่รายชื่อพ่อแม่ (`parents`) พ่อแม่ตายหรืออยู่คนละที่ก็ไม่มีใครดูแลแทน และเด็กที่ระบบสร้าง
ขึ้นโดยไม่มีพ่อแม่ (repopulate, ประชากรตั้งต้น) ไม่เคยมีผู้ดูแลเลย วัดตอนเปิดยุ้งฉางกับค่าแรง: เด็กกำพร้าอดตาย
1,516 จาก 2,238 ราย ทั้งที่ยุ้งฉางมีข้าวค้างสองล้านสำรับ จึงต้องให้หมู่บ้านเลี้ยงแทนไปก่อน
(SIM_DAO_AUTONOMOUS_WORLD_DESIGN_TH.md §7.2 ข้อ 5, §7.4 ข้อ 6, §13.2 "ผู้ดูแลเสียชีวิต")

กติกา (เปิดด้วย GUARDIANS_ENABLED)
---------------------------------
- เด็กอายุต่ำกว่า 14 ปีทุกคนมีผู้ปกครองหนึ่งคน (`Character.guardian`) อยู่แดนเดียวกัน ผู้ปกครองถือรายชื่อ `wards`
- ลำดับที่เลือก: พ่อแม่ → พี่น้องที่เป็นผู้ใหญ่ ปู่ย่าตายาย และคู่ครองของพ่อแม่ → คนในตระกูลเดียวกัน → ผู้ใหญ่ที่อยู่
  ที่เดียวกันซึ่งเลี้ยงไหว ในลำดับเดียวกัน คนที่อยู่ที่เดียวกับเด็กก่อน แล้วคนที่มีเงินมากกว่า ไม่ใช่ cid ต่ำก่อน
- คนที่ไม่ใช่พ่อแม่รับเลี้ยงได้ไม่เกิน GUARDIAN_MAX_WARDS คน ผู้ปกครองต้องเป็นผู้ใหญ่ มีจิต และไม่ได้ปิดด่านหรือติดคุก
- ผู้ปกครองอยู่คนละที่ในแดนเดียวกัน เด็กย้ายไปอยู่กับผู้ปกครอง ผู้ปกครองเดินทางไปถึงที่ใหม่ เด็กที่อยู่ด้วยย้ายตาม
  (ย้ายทันทีตอนรับเลี้ยงหรือตอนผู้ปกครองมาถึง — ยังไม่ได้จำลองการเดินทางของเด็กเป็นวัน)
- เปิดระบบอาหารอยู่ เด็กย้ายไปหาผู้ปกครองเฉพาะเมื่อที่นั้นมีข้าวในระยะส่ง (`food_near`) หรือที่เดิมก็ไม่มีเหมือนกัน
  เด็กที่แยกกับผู้ปกครองกลับไปอยู่ด้วยเมื่อที่ของผู้ปกครองมีข้าวแล้ว และในลำดับเดียวกันเลือกคนที่อยู่ใกล้ข้าวก่อน
  วัดแล้ว ถ้าย้ายตามผู้ปกครองโดยไม่ดู เด็กอดตายต่อ seed ผันผวนระหว่าง 35 ถึง 131 คน
- ผู้ปกครองตาย เด็กได้ผู้ปกครองใหม่ทันทีในธุรกรรมความตายเดียวกัน ไม่มีใครรับได้ เด็กเป็นเด็กไร้ผู้ดูแล
- ครบ 14 ปี หมดความเป็นผู้ปกครอง
- ค่าข้าวของเด็ก (tiandao/food.py) ผู้ปกครองที่อยู่ที่เดียวกันจ่าย หมู่บ้านเลี้ยงเฉพาะเด็กที่ไม่มีใครอยู่ด้วย
"""
from . import config as C
from . import travel as TR
from . import wages as WAGES

STAT_KEYS = ("assigned", "reassigned", "unplaced", "moved", "released")
# "unplaced" เป็นจำนวน ณ รอบล่าสุด (เด็กที่ตอนนี้ไม่มีผู้ปกครอง) ไม่ใช่ยอดสะสม ตัวอื่นเป็นยอดสะสม
ADULT_AGE = 18


def new_stats() -> dict:
    return {k: 0 for k in STAT_KEYS}


def is_child(ch, day) -> bool:
    return ch.alive and ch.age(day) < 14


def _can_care(ch, day) -> bool:
    return (ch.alive and ch.age(day) >= ADULT_AGE and getattr(ch, "sentient", True)
            and not getattr(ch, "is_beast", False) and not getattr(ch, "is_lord", False)
            and getattr(ch, "seclude_until", 0) <= day and getattr(ch, "jail_until", 0) <= day)


def food_near(sim, wid, place) -> bool:
    """ที่นี้มีข้าวพอเลี้ยงเด็กหนึ่งคนหนึ่งเดือนในยุ้งฉางของตัวเองหรือยุ้งฉางในระยะส่งไหม — ปิดระบบอาหาร = มีเสมอ"""
    if not C.FOOD_ENABLED:
        return True
    if place is None or place < 0:
        return False
    enough = C.FOOD_PACK_DAYS * C.FOOD_RATION_CHILD
    granary = getattr(sim, "granary", {})
    if granary.get((wid, place), 0.0) >= enough:
        return True
    return any(granary.get((wid, other), 0.0) >= enough
               for other, _hops in TR.places_within(sim, place, C.FOOD_REACH_HOPS))


def _safe_to_move(sim, child, place) -> bool:
    """ย้ายเด็กไปที่ `place` ได้ไหม: ที่นั้นมีข้าวใกล้ๆ หรือที่เดิมก็ไม่มีข้าวอยู่แล้ว (ย้ายไม่ทำให้แย่ลง)"""
    return food_near(sim, child.world_id, place) or not food_near(sim, child.world_id, child.place)


def _move_child(sim, child, place) -> bool:
    if place is None or place < 0 or place == child.place or not _safe_to_move(sim, child, place):
        return False
    child.place = place
    child.building = -1
    child.travel_dest = -1
    sim.guardian_stats["moved"] += 1
    return True


def _people(sim, cids):
    return [sim.cast[c] for c in cids or () if isinstance(c, int) and 0 <= c < len(sim.cast)]


def _family(sim, child):
    """(พ่อแม่, ญาติใกล้) ของเด็ก — ญาติใกล้คือพี่น้อง ปู่ย่าตายาย และคู่ครองของพ่อแม่"""
    parents = _people(sim, child.parents)
    kin = []
    for parent in parents:
        kin += [c for c in _people(sim, parent.children) if c.cid != child.cid]
        kin += _people(sim, parent.parents)
        if parent.spouse is not None:
            kin += _people(sim, [parent.spouse])
    seen, unique = {child.cid} | {p.cid for p in parents}, []
    for c in kin:
        if c.cid not in seen:
            seen.add(c.cid)
            unique.append(c)
    return parents, unique


def _rank(sim, child, people):
    """เรียงคนที่อยู่ใกล้ข้าวก่อน แล้วคนที่อยู่ที่เดียวกับเด็ก แล้วคนที่มีเงินมากกว่า — ไม่ใช่ cid ต่ำก่อน"""
    return sorted(people, key=lambda c: (not food_near(sim, c.world_id, c.place), c.place != child.place,
                                         -WAGES.gold(sim, c), c.cid))


def choose(sim, child, locals_by_spot=None):
    """ผู้ปกครองที่ควรดูแลเด็กคนนี้ หรือ None ถ้าไม่มีใครในแดนเดียวกันรับได้"""
    day = sim.day

    def fit(c, parent=False):
        return (_can_care(c, day) and c.world_id == child.world_id
                and (parent or len(c.wards) < C.GUARDIAN_MAX_WARDS))

    parents, kin = _family(sim, child)
    for group, parent in ((parents, True), (kin, False)):
        ranked = _rank(sim, child, [c for c in group if fit(c, parent)])
        if ranked:
            return ranked[0]
    if child.clan >= 0:
        clan = [c for c in sim.living_in(child.world_id) if c.clan == child.clan and fit(c)]
        if clan:
            return _rank(sim, child, clan)[0]
    if locals_by_spot is not None:
        here = locals_by_spot.get((child.world_id, child.place), ())
    else:
        here = [c for c in sim.living_in(child.world_id) if c.place == child.place]
    here = [c for c in here if c.cid != child.cid and fit(c)]
    return _rank(sim, child, here)[0] if here else None


def _release(sim, child):
    if child.guardian >= 0 and child.guardian < len(sim.cast):
        old = sim.cast[child.guardian]
        if child.cid in old.wards:
            old.wards.remove(child.cid)
    child.guardian = -1


def assign(sim, child, guardian, reason):
    """ให้ `guardian` ดูแล `child` — เด็กย้ายไปอยู่ที่เดียวกับผู้ปกครองถ้าอยู่คนละที่"""
    _release(sim, child)
    child.guardian = guardian.cid
    guardian.wards.append(child.cid)
    is_parent = guardian.cid in (child.parents or ())
    sim.guardian_stats["reassigned" if reason == "สืบต่อ" else "assigned"] += 1
    _move_child(sim, child, guardian.place)
    if not is_parent:
        sim.emit(sim.world(child.world_id), "รับเลี้ยง", guardian, child, ["ครอบครัว"], reason,
                 f"{guardian.name}รับ{child.name}มาเลี้ยงดูที่{sim.place_name(guardian)}", 0,
                 {"เหตุ": "ผู้ปกครองเดิมสิ้นชีวิต" if reason == "สืบต่อ" else "ไม่มีผู้ใดดูแล"})


def tick(sim) -> None:
    """ทุกรอบนาฬิกาโลก: เด็กที่ครบ 14 ปีพ้นการดูแล เด็กที่ยังไม่มีผู้ปกครองที่ใช้ได้ได้ผู้ปกครอง"""
    day = sim.day
    locals_by_spot = {}
    children = []
    for cid in sorted(sim.alive_cids):
        ch = sim.cast[cid]
        if is_child(ch, day):
            children.append(ch)
        elif ch.guardian >= 0:
            _release(sim, ch)
            sim.guardian_stats["released"] += 1
        else:
            locals_by_spot.setdefault((ch.world_id, ch.place), []).append(ch)
    sim.guardian_stats["unplaced"] = 0
    for child in children:
        current = sim.cast[child.guardian] if 0 <= child.guardian < len(sim.cast) else None
        if current is not None and current.alive and current.world_id == child.world_id:
            if current.place != child.place and current.travel_dest < 0:
                _move_child(sim, child, current.place)     # กลับไปอยู่กับผู้ปกครองเมื่อที่นั้นปลอดภัยแล้ว
            continue
        guardian = choose(sim, child, locals_by_spot)
        if guardian is None:
            if child.guardian >= 0:
                _release(sim, child)
            sim.guardian_stats["unplaced"] += 1
            continue
        assign(sim, child, guardian, "รับเลี้ยง")


def on_death(sim, ch) -> None:
    """ผู้ปกครองตาย — เด็กทุกคนในความดูแลได้ผู้ปกครองใหม่ในธุรกรรมความตายเดียวกัน"""
    if ch.guardian >= 0:
        _release(sim, ch)
    for cid in list(ch.wards):
        child = sim.cast[cid]
        child.guardian = -1
        ch.wards.remove(cid)
        if not is_child(child, sim.day):
            continue
        heir = choose(sim, child)
        if heir is not None:
            assign(sim, child, heir, "สืบต่อ")


def on_arrival(sim, guardian, old_place) -> None:
    """ผู้ปกครองเดินทางถึงที่ใหม่ — เด็กที่อยู่ด้วยที่เดิมย้ายตามมา"""
    for cid in guardian.wards:
        child = sim.cast[cid]
        if child.alive and child.world_id == guardian.world_id and child.place == old_place:
            _move_child(sim, child, guardian.place)


def payer(sim, child):
    """ผู้ปกครองที่อยู่ที่เดียวกับเด็กตอนนี้ — ผู้ที่จ่ายค่าข้าวให้ หรือ None"""
    if 0 <= child.guardian < len(sim.cast):
        g = sim.cast[child.guardian]
        if (_can_care(g, sim.day) and (g.world_id, g.place) == (child.world_id, child.place)
                and g.travel_dest < 0):
            return g
    return None
