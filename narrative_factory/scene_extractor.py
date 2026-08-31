# -*- coding: utf-8 -*-
"""Phase B — Scene Extractor: จัดกลุ่ม ParsedEvent ที่เกี่ยวข้องกัน -> Scene พร้อม Narrative Genome

หน้าที่เดียวของไฟล์นี้: ตัดสินว่าเหตุการณ์ไหนควรรวมเป็น "ฉากเดียวกัน" (เช่น ไล่ล่า→ต่อสู้→จบ ที่เกิด
ห่างกันไม่กี่วันติดกันของคู่ตัวละครเดียวกัน ควรเป็นฉากเดียว ไม่ใช่คนละฉาก) แล้วเรียก genome.py คำนวณ
Narrative Genome ให้แต่ละฉาก — **ไม่** ดึง context ตัวละครแบบเต็ม (Realm/Personality/Relationship/
Memory ฯลฯ เป็นหน้าที่ของ context_builder.py ที่จะตามมา)

อัลกอริทึม (greedy, ไล่ตามเวลา — ดู scene_merge_window_days ใน config.yaml):
  ไล่ ParsedEvent ที่ไม่ถูก exclude (excluded_scene_types) ตามวัน ถ้าเหตุการณ์นี้มีผู้เล่นร่วมกับฉาก
  ที่ "ยังเปิดอยู่" (เหตุการณ์ล่าสุดในฉากนั้นห่างไม่เกิน window) ให้รวมเข้าฉากนั้น ไม่งั้นเปิดฉากใหม่
  ฉากที่ห่างเกิน window ถือว่า "ปิด" (ยังอยู่ในผลลัพธ์ แต่รับเหตุการณ์ใหม่เข้าไปอีกไม่ได้)
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


def extract_scenes(parsed_events: List[ParsedEvent], sim, config: Optional[dict] = None) -> List[Scene]:
    """List[ParsedEvent] (จาก parser.py — Phase A) -> List[Scene] พร้อม Narrative Genome ต่อฉาก"""
    cfg = config or load_config()
    excluded = set(cfg.get("excluded_scene_types", []))
    window = cfg.get("scene_merge_window_days", 3)

    candidates = sorted(
        (e for e in parsed_events if e.scene_type not in excluded),
        key=lambda e: (e.day, e.seq),
    )
    if not candidates:
        logger.warning("scene_extractor: ไม่มี ParsedEvent ที่ผ่าน excluded_scene_types filter เลย")
        return []

    by_cid = index_by_character(parsed_events)
    cid_to_dao = {c.cid: c.dao for c in sim.cast}

    scenes: List[Scene] = []
    for sc in _cluster(candidates, window):
        events = sorted(sc.events, key=lambda e: (e.day, e.seq))
        anchor = events[-1]
        focal = anchor.actor
        dao = cid_to_dao.get(focal, "")
        char_log = by_cid.get(focal, [])
        other_participants = sc.participants - {focal}
        genome = G.build_genome(anchor, dao, char_log, other_participants,
                                 is_win=_is_win_for(focal, anchor), config=cfg)
        scenes.append(Scene(
            scene_id=f"{sc.world_id}-{events[0].seq}",
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
    logger.info("scene_extractor: รวม %d เหตุการณ์เป็น %d ฉาก", len(candidates), len(scenes))
    return scenes
