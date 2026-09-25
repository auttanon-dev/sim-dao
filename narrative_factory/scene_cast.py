# -*- coding: utf-8 -*-
"""ประกอบ "สำนวนฉาก" สำหรับเขียนเป็นหนัง — ใครอยู่ตรงนั้น เกิดอะไรจริง ที่ไหน อากาศยังไง

สองอย่างที่ไฟล์นี้ทำ และเหตุผลที่ต้องทำตรงนี้ ไม่ใช่ในเอนจิน:

1. **จุดเปลี่ยนจริง** — หาโดย diff `Event.snap` (ลายนิ้วมือสถานะของ actor) กับเหตุการณ์ก่อนหน้าของ
   คนเดียวกัน ไม่ใช่เดาจากสตริง outcome ซึ่งวัดแล้วว่าเชื่อไม่ได้: ลองใช้ outcome คัดดู 7 จาก 16
   "จุดเปลี่ยน" ของชีวิตหนึ่งกลายเป็น "ทำนาได้ผลผลิต" เพราะ outcome ของมันคือ "สำเร็จ" เหมือนกับ
   การหลอมยาสำเร็จ

2. **ใครอยู่ตรงนั้นด้วย** — ประกอบย้อนหลังจาก log แทนที่จะให้เอนจินบันทึกทุกเหตุการณ์ ตำแหน่งของ
   ตัวละครเปลี่ยนเฉพาะตอนเดินทางถึงที่หมาย ระหว่างนั้นอยู่กับที่ ตำแหน่งล่าสุดที่ log ไว้จึงเป็น
   ตำแหน่งจริง ณ วันใดก็ได้หลังจากนั้น — ประกอบย้อนหลังได้แม่นเท่ากับบันทึกสด แต่ไม่ทำให้ซิมช้าลง
   60% เพื่อข้อมูลที่ใช้จริงแค่ราว 20 ฉากต่อนิยายหนึ่งเรื่อง
"""
import bisect
import collections
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from tiandao import places as PL
from tiandao import seasons as SEASONS
from tiandao import settlement as SETTLE
from tiandao import weather as WEATHER

MIN_TURNING_POINTS = 12   # ชีวิตที่มีจุดเปลี่ยนน้อยกว่านี้ ไม่พอเป็นนิยายหนึ่งเรื่อง
HARD_SNAP_FIELDS = 12     # นับเฉพาะฟิลด์ที่เป็น "จุดพลิกของเรื่อง" — ความเสื่อม/จิตมารเป็นสภาพ
                          # ของตัวละคร ใช้บรรยายได้ แต่ไม่ควรสร้างฉากขึ้นมาเอง


# ---------------------------------------------------------------- จุดเปลี่ยนจริง
def events_by_actor(log) -> Dict[int, List]:
    by: Dict[int, List] = collections.defaultdict(list)
    for e in log:
        if e.actor is not None and e.actor >= 0:
            by[e.actor].append(e)
    for lst in by.values():
        lst.sort(key=lambda e: (e.day, e.seq))
    return by


def turning_points(events: List) -> List:
    """เหตุการณ์ที่ทำให้สถานะของตัวละครเปลี่ยนจริง (snap ต่างจากครั้งก่อน)

    เหตุการณ์แรกที่มี snap นับเป็นจุดตั้งต้นเสมอ — ไม่มีอะไรให้เทียบ แต่เป็นจุดที่เรารู้จักเขาครั้งแรก
    """
    out, prev = [], None
    for e in events:
        snap = tuple((getattr(e, "snap", ()) or ())[:HARD_SNAP_FIELDS])
        if not snap:
            continue
        if prev is None or snap != prev:
            out.append(e)
        prev = snap
    return out


def snap_diff(before: tuple, after: tuple, field_names: Tuple[str, ...]) -> Dict[str, Tuple[int, int]]:
    """อะไรเปลี่ยนไปบ้างระหว่างสองลายนิ้วมือ — ใช้บอกคนเขียนว่าฉากนี้ 'ได้อะไร เสียอะไร'"""
    if not before or not after:
        return {}
    return {field_names[i]: (before[i], after[i])
            for i in range(min(len(before), len(after), len(field_names)))
            if before[i] != after[i]}


# ---------------------------------------------------------------- ใครอยู่ตรงนั้น
class Presence:
    """ตำแหน่งของทุกคนตามเวลา ประกอบจาก log ครั้งเดียวแล้วถามซ้ำได้เร็ว"""

    def __init__(self, log):
        tl: Dict[int, List[Tuple[int, int]]] = collections.defaultdict(list)
        for e in log:
            place = getattr(e, "place", None)
            if e.actor is not None and e.actor >= 0 and place is not None and place >= 0:
                tl[e.actor].append((e.day, e.place))
        self.days: Dict[int, List[int]] = {}
        self.places: Dict[int, List[int]] = {}
        for cid, pts in tl.items():
            pts.sort()
            self.days[cid] = [d for d, _ in pts]
            self.places[cid] = [p for _, p in pts]

    def place_of(self, cid: int, day: int) -> Optional[int]:
        """ตำแหน่งล่าสุดที่รู้ของคนนี้ ณ วันนั้น — None ถ้ายังไม่เคยมีเหตุการณ์ก่อนวันนั้นเลย"""
        ds = self.days.get(cid)
        if not ds:
            return None
        i = bisect.bisect_right(ds, day) - 1
        return self.places[cid][i] if i >= 0 else None

    def who_at(self, place: int, day: int, exclude=(), limit: int = 8) -> List[int]:
        """คนที่อยู่ที่นั่น ณ วันนั้น (เรียง cid ให้ผลคงที่)"""
        out = []
        for cid in sorted(self.days):
            if cid in exclude:
                continue
            if self.place_of(cid, day) == place:
                out.append(cid)
                if len(out) >= limit:
                    break
        return out


# ---------------------------------------------------------------- สำนวนฉาก
@dataclass
class SceneDossier:
    day: int
    year: int
    place_name: str
    place_kind: str
    building: str
    season: str
    weather: str
    kind: str
    outcome: str
    text: str
    changed: Dict[str, Tuple[int, int]]
    focal: int
    others: List[int]
    bystanders: List[int]
    deltas: Dict[str, str] = field(default_factory=dict)


def _place_bits(place: int, building: int):
    if place is None or place < 0 or place >= len(PL.PLACES):
        return "ที่ใดสักแห่ง", "-", "-"
    p = PL.PLACES[place]
    b = "-"
    if building is not None and building >= 0:
        try:
            b = SETTLE.building_type_of(place, building) or "-"
        except Exception:
            b = "-"
    return p[0], p[3], b


def build_dossier(ev, prev_snap, sim, presence: Presence, field_names) -> SceneDossier:
    pname, pkind, bname = _place_bits(getattr(ev, "place", -1), getattr(ev, "building", -1))
    world = sim.worlds[ev.world_id] if ev.world_id < len(sim.worlds) else None
    wkey = getattr(world, "place_key", 0) if world else 0
    try:
        w = WEATHER.get_current_weather(ev.day, wkey)
        wdesc = w.get("name", "-")
    except Exception:
        wdesc = "-"
    others = [c for c in ([ev.target] if ev.target is not None else []) if c is not None]
    by = [c for c in presence.who_at(getattr(ev, "place", -1), ev.day,
                                    exclude=set([ev.actor] + others))]
    return SceneDossier(
        day=ev.day, year=ev.day // 365, place_name=pname, place_kind=pkind, building=bname,
        season=SEASONS.season_of(ev.day)[0], weather=str(wdesc),
        kind=ev.kind, outcome=ev.outcome, text=ev.text,
        changed=snap_diff(prev_snap, getattr(ev, "snap", ()), field_names),
        focal=ev.actor, others=others, bystanders=by,
        deltas=dict(ev.deltas or {}),
    )


def can_carry_a_novel(ch) -> bool:
    """คนที่ "เป็นตัวเอกได้" — ไม่ใช่ทุกสิ่งที่เอนจินเก็บไว้ใน sim.cast เป็นตัวละครในความหมายของนิยาย

    สัตว์อสูรป่าที่โผล่มาระหว่างการล่าถูก spawn เป็นตัวละครเต็มตัว (เข้าคิว มีนิสัย เข้าสำนักได้)
    ตามที่เอนจินตั้งใจ เพราะบางตัวต้องบำเพ็ญจนกลายเป็นราชันย์อสูรที่ยกทัพบุกเมืองได้จริง — แต่ตัวที่
    ยังไม่จำแลงกายเป็นมนุษย์ยังเป็นสัตว์อยู่ ไม่มีบทพูด ไม่มีเรื่องให้เล่าจากมุมของมัน
    วัดจริงก่อนใส่ข้อนี้: 30 จาก 149 ชีวิตที่ผ่านเกณฑ์จุดเปลี่ยนเป็นอสูรป่า และตัวที่ได้อันดับหนึ่ง
    (26 จุดเปลี่ยน) ก็เป็นอสูรป่าที่ไปเข้าสังกัดสำนักและมีอาชีพช่างหลอม

    มันยังอยู่ในฉากของคนอื่นได้ตามปกติ — ข้อนี้กันแค่ไม่ให้มันเป็น "คนที่เราเล่าเรื่องของเขา"
    """
    return (not getattr(ch, "is_beast", False)) or getattr(ch, "has_human_form", False)


def novel_candidates(log, sim, min_points: int = MIN_TURNING_POINTS):
    """ชีวิตที่มีจุดเปลี่ยนพอจะเป็นนิยายหนึ่งเรื่อง — คืน [(cid, จุดเปลี่ยนทั้งหมด)] เรียงจากมากไปน้อย"""
    out = []
    for cid, evs in events_by_actor(log).items():
        if cid >= len(sim.cast):
            continue
        if not can_carry_a_novel(sim.cast[cid]):
            continue
        tp = turning_points(evs)
        if len(tp) >= min_points:
            out.append((cid, tp))
    out.sort(key=lambda x: -len(x[1]))
    return out
