# -*- coding: utf-8 -*-
"""Phase A — Event Parser: sim.log ดิบ -> ParsedEvent ที่มี scene_type มาตรฐานติดมาแล้ว

หน้าที่เดียวของไฟล์นี้: แปลง Event ของเอนจิน (tiandao/models.py) ให้เป็นรูปแบบที่โมดูลถัดไปในสาย
(scene_extractor.py — Phase B) ใช้ต่อได้ทันที ไม่ทำอะไรเกินนี้ (ไม่ดึง context ตัวละคร ไม่คำนวณ
Narrative Genome — นั่นคือหน้าที่ของ genome.py)
"""
import logging
import os
from dataclasses import dataclass
from functools import lru_cache
from typing import TYPE_CHECKING, Dict, List, Optional, Set

import yaml

if TYPE_CHECKING:
    from tiandao.models import Event
    from tiandao.sim import Sim

logger = logging.getLogger(__name__)

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.yaml")


@lru_cache(maxsize=1)
def load_config(path: str = CONFIG_PATH) -> dict:
    """โหลด config.yaml ครั้งเดียวแล้ว cache ไว้ — ทุกตารางแก้ได้โดยไม่ต้องแตะโค้ดไฟล์นี้เลย"""
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


@dataclass
class ParsedEvent:
    """Event ดิบจาก tiandao/models.py + scene_type มาตรฐาน — เก็บ field เดิมไว้ครบ ไม่ทิ้งอะไร
    เพื่อให้ Phase B-F ย้อนกลับไปอ้างอิงต้นฉบับได้เสมอ (Quality Validator Phase D ต้องใช้)"""
    seq: int
    day: int
    world_id: int
    era: int
    kind: str
    scene_type: str
    actor: int
    target: Optional[int]
    tags: List[str]
    outcome: str
    text: str
    deltas: Dict[str, str]
    place: int = -1
    realm: int = -1


def participants_of(ev: ParsedEvent) -> Set[int]:
    """cid ทั้งหมดที่เกี่ยวข้องกับเหตุการณ์นี้ (actor + target ถ้ามี) — ใช้ร่วมกันทั้ง
    scene_extractor.py และ memory_retriever.py กันไม่ให้ต้องเขียนตรรกะเดียวกันซ้ำสองที่"""
    ids = {ev.actor}
    if ev.target is not None:
        ids.add(ev.target)
    return ids


def classify_scene_type(kind: str, outcome: str, config: Optional[dict] = None) -> str:
    """แมป kind ของเอนจิน -> scene_type มาตรฐาน (Breakthrough/Duel/Betrayal/...)

    kind ใหม่ที่ไม่รู้จัก (เพิ่ม event ใหม่ในเอนจินทีหลัง) จะตกไปที่ default_scene_type เสมอ ไม่ throw
    error — ตรงตามที่ ROLE.md สั่งว่า "ต้องรองรับ Event ใหม่ในอนาคต ห้าม Hardcode มากเกินไป"
    outcome ที่ตายเสมอ override เป็น "Death" ไม่ว่า kind จะเป็นอะไร (ตายจากประลอง/ปล้น/บุก ก็คือ
    Death ในทางเล่าเรื่อง)"""
    cfg = config or load_config()
    if outcome in cfg.get("death_outcomes", ()):
        return "Death"
    return cfg.get("scene_type_map", {}).get(kind, cfg.get("default_scene_type", "Other"))


def parse_event(ev: "Event", config: Optional[dict] = None) -> ParsedEvent:
    cfg = config or load_config()
    return ParsedEvent(
        seq=ev.seq, day=ev.day, world_id=ev.world_id, era=ev.era, kind=ev.kind,
        scene_type=classify_scene_type(ev.kind, ev.outcome, cfg),
        actor=ev.actor, target=ev.target, tags=list(ev.tags),
        outcome=ev.outcome, text=ev.text, deltas=dict(ev.deltas),
        place=getattr(ev, "place", -1), realm=getattr(ev, "realm", -1),
    )


def parse_log(sim: "Sim", event_log_path: Optional[str] = None) -> List[ParsedEvent]:
    """แปลงประวัติทั้งหมดเป็น List[ParsedEvent] — เรียกครั้งเดียวต่อโลกที่โหลดมา

    ถ้า daemon.py เคย flush+trim log แล้ว (Phase G — ดู tiandao/event_log.py) ประวัติเก่าบางส่วนจะไม่
    อยู่ใน sim.log อีกต่อไป (ถูกย้ายไปไฟล์ .events.jsonl แทนเพื่อกัน world.save โตไม่มีเพดาน) —
    ต้องส่ง event_log_path มาด้วยเสมอถ้าอยากได้ประวัติเต็ม ไม่งั้นจะเห็นแค่ส่วนที่เหลือใน sim.log
    (เหตุการณ์ล่าสุด ไม่ใช่ทั้งชีวิตของตัวละคร — Scene Extraction/foreshadowing จะพลาดของเก่าไป)"""
    from tiandao import event_log as EL

    cfg = load_config()
    events = EL.full_log(sim, event_log_path)
    parsed = [parse_event(ev, cfg) for ev in events]
    logger.info("parser: แปลง %d เหตุการณ์สำเร็จ (event_log_path=%s)", len(parsed), event_log_path)
    return parsed
