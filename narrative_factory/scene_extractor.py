# -*- coding: utf-8 -*-
"""Phase B — Scene Extractor: จับกลุ่มเหตุการณ์เป็น "ฉาก" ที่เขียนเป็นหนังได้

**เขียนใหม่ทั้งวิธีคัด** — ของเดิมคัดด้วยสองอย่างที่วัดแล้วว่าใช้ไม่ได้ทั้งคู่:

1. `scene_merge_window_days: 3` — ตั้งไว้สำหรับซิมที่ tick = วัน แต่ซิมนี้ tick = เหตุการณ์ ซึ่ง
   ห่างกันมัธยฐาน 766 วัน วัดจริงแล้วมีคู่เหตุการณ์ติดกันของคนเดียวกันที่ห่างกัน <= 3 วัน อยู่แค่
   **15 คู่จาก 17,658 (0.1%)** ผลคือ 21,227 เหตุการณ์กลายเป็น 21,132 ฉาก — ทุกฉากมีเหตุการณ์เดียว
   เครื่องรวมฉากไม่เคยรวมอะไรเลยสักครั้ง

2. `excluded_scene_types` + `scene_type_map` — คัดด้วย "ชนิดเหตุการณ์" ทำให้ทิ้งการข้ามฟ้าและการ
   กำเนิดทายาท ขณะที่เก็บ "ค้าขาย/ค้าขาย" 3,852 ฉาก กับ "ซ่อนตัว/เก็บตัว" 3,085 ฉากไว้เป็นฉากหลัก

วิธีใหม่: **หนึ่งฉาก = หนึ่งจุดเปลี่ยนจริง + เหตุการณ์นำก่อนหน้า**
  - จุดเปลี่ยน = `Event.snap` ต่างจากเหตุการณ์ก่อนของคนเดียวกัน (ดู scene_cast.turning_points)
    ไม่ใช่เดาจากสตริง outcome ซึ่งทำให้ "ทำนา/สำเร็จ" ถูกนับเท่ากับ "หลอมยา/สำเร็จ"
  - เหตุการณ์นำ = สิ่งที่เขาทำระหว่างทางมาถึงจุดนี้ ใช้เป็นวัตถุดิบของบีต Opening/Inciting
    (ดู pacing.py) ไม่ใช่ฉากแยกของตัวเอง
"""
import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Set

from . import genome as G
from .parser import ParsedEvent, load_config, participants_of

logger = logging.getLogger(__name__)


@dataclass
class Scene:
    scene_id: str
    scene_type: str
    world_id: int
    day_start: int
    day_end: int
    location: Optional[int]      # place_idx ของเหตุการณ์ anchor (climax/เหตุการณ์สุดท้ายของฉาก)
    participants: List[int]
    focal_cid: int                # ตัวละครหลักของฉาก = actor ของเหตุการณ์ anchor
    events: List[ParsedEvent]
    genome: G.NarrativeGenome


class _OpenScene:
    """สถานะฉากระหว่าง cluster — ไม่ใช่ผลลัพธ์สุดท้าย (ดู Scene ด้านบน)"""

    def __init__(self, seed: ParsedEvent):
        self.world_id = seed.world_id
        self.participants: Set[int] = participants_of(seed)
        self.events: List[ParsedEvent] = [seed]
        self.last_day = seed.day

    def matches(self, ev: ParsedEvent, window: int) -> bool:
        return (ev.world_id == self.world_id
                and (ev.day - self.last_day) <= window
                and bool(participants_of(ev) & self.participants))

    def absorb(self, ev: ParsedEvent) -> None:
        self.participants |= participants_of(ev)
        self.events.append(ev)
        self.last_day = ev.day


def _cluster(candidates: List[ParsedEvent], window: int) -> List[_OpenScene]:
    open_scenes: List[_OpenScene] = []
    closed: List[_OpenScene] = []
    for ev in candidates:
        still_open = []
        for sc in open_scenes:
            if (ev.day - sc.last_day) > window:
                closed.append(sc)
            else:
                still_open.append(sc)
        open_scenes = still_open

        target = next((sc for sc in open_scenes if sc.matches(ev, window)), None)
        if target is not None:
            target.absorb(ev)
        else:
            open_scenes.append(_OpenScene(ev))
    return closed + open_scenes


def _is_win_for(cid: int, ev: ParsedEvent) -> Optional[bool]:
    """None ถ้าไม่ใช่เหตุการณ์ต่อสู้ (ไม่มี "winner" ใน deltas — ดู tiandao/sim.py) หรือ log เก่า"""
    winner = ev.deltas.get("winner")
    return None if winner is None else int(winner) == cid


def index_by_character(parsed_events: List[ParsedEvent]) -> Dict[int, List[ParsedEvent]]:
    """ดัชนีเหตุการณ์ **ทั้งหมด** (รวม scene_type ที่ถูก exclude ด้วย) ต่อตัวละคร — ให้
    genome.compute_foreshadowing ค้นย้อนหลังได้ครบ ไม่ใช่แค่เหตุการณ์ที่กลายเป็นฉากแล้ว"""
    by_cid: Dict[int, List[ParsedEvent]] = {}
    for e in parsed_events:
        by_cid.setdefault(e.actor, []).append(e)
        if e.target is not None:
            by_cid.setdefault(e.target, []).append(e)
    for lst in by_cid.values():
        lst.sort(key=lambda e: (e.day, e.seq))
    return by_cid


# ฟิลด์ท้ายๆ ของ snap (ความเสื่อม/จิตมาร) ขยับเรื่อยๆ ตามอายุและการต่อสู้ — เป็นสภาพของตัวละคร
# ไม่ใช่จุดพลิกของเรื่อง ถ้านับมันเป็นจุดเปลี่ยนด้วยจะได้ฉากที่ไคลแมกซ์คือ "เก็บตัวเงียบไปพักหนึ่ง"
# (พบจริงตอนทดสอบ: ฉากหลบหนีที่ Peak คือการพักฟื้น ส่วนการปล้นที่ล้มเหลวไปอยู่ใน Rising)
HARD_SNAP_FIELDS = 12   # นับเฉพาะ 12 ฟิลด์แรก: ของ/สำนัก/ตระกูล/วิชา/มิตร/ศัตรู/ศิษย์/อาจารย์/โลก/
                        # เป็น-ตาย/ขั้นนักปรุงยา/ขั้นช่างตีเหล็ก


def _turning_points(events: List[ParsedEvent]) -> List[int]:
    """ดัชนีของเหตุการณ์ที่ทำให้สถานะ "เชิงเรื่อง" เปลี่ยนจริง — ดู scene_cast.py"""
    out, prev = [], None
    for i, e in enumerate(events):
        snap = tuple((getattr(e, "snap", ()) or ())[:HARD_SNAP_FIELDS])
        if not snap:
            continue
        if prev is None or snap != prev:
            out.append(i)
        prev = snap
    return out


def extract_scenes(parsed_events: List[ParsedEvent], sim, config: Optional[dict] = None) -> List[Scene]:
    """List[ParsedEvent] -> List[Scene] โดยหนึ่งฉาก = หนึ่งจุดเปลี่ยน + เหตุการณ์นำก่อนหน้า"""
    cfg = config or load_config()
    lead_max = cfg.get("scene_lead_events", 5)
    lead_days = cfg.get("scene_lead_window_days", 730)

    by_actor: Dict[int, List[ParsedEvent]] = {}
    for e in parsed_events:
        by_actor.setdefault(e.actor, []).append(e)
    for lst in by_actor.values():
        lst.sort(key=lambda e: (e.day, e.seq))

    groups: List[List[ParsedEvent]] = []
    for cid, evs in by_actor.items():
        tps = _turning_points(evs)
        if not tps:
            continue
        prev_tp = -1
        for idx in tps:
            lead = evs[max(prev_tp + 1, idx - lead_max):idx]
            lead = [e for e in lead if evs[idx].day - e.day <= lead_days]
            groups.append(lead + [evs[idx]])
            prev_tp = idx
    if not groups:
        logger.warning("scene_extractor: ไม่มีจุดเปลี่ยนเลย — log นี้อาจเก่ากว่าการเพิ่ม Event.snap")
        return []

    by_cid = index_by_character(parsed_events)
    cid_to_dao = {c.cid: c.dao for c in sim.cast}

    scenes: List[Scene] = []
    for events in groups:
        anchor = events[-1]
        focal = anchor.actor
        sc_participants = set()
        for e in events:
            sc_participants |= participants_of(e)
        sc = _OpenScene(anchor)
        sc.participants = sc_participants
        sc.world_id = anchor.world_id
        dao = cid_to_dao.get(focal, "")
        char_log = by_cid.get(focal, [])
        other_participants = sc.participants - {focal}
        genome = G.build_genome(anchor, dao, char_log, other_participants,
                                 is_win=_is_win_for(focal, anchor), config=cfg)
        scenes.append(Scene(
            scene_id=f"{sc.world_id}-{anchor.seq}",
            scene_type=anchor.scene_type,
            world_id=sc.world_id,
            day_start=events[0].day,
            day_end=events[-1].day,
            location=anchor.place if anchor.place >= 0 else None,
            participants=sorted(sc.participants),
            focal_cid=focal,
            events=events,
            genome=genome,
        ))
    scenes.sort(key=lambda s: (s.day_start, s.scene_id))
    logger.info("scene_extractor: %d เหตุการณ์ -> %d ฉาก (จุดเปลี่ยนจริง)",
                len(parsed_events), len(scenes))
    return scenes
