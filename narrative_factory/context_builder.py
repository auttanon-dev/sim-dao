# -*- coding: utf-8 -*-
"""Phase C — Character Context Builder

หน้าที่เดียว: ประกอบ context ของผู้เกี่ยวข้องแต่ละคนในฉาก (Realm/Dao/Personality/Relationship/
Reputation/Current Goal/Emotion) — Recent Memory มอบให้ memory_retriever.py ทำ (แยกไฟล์ตาม ROLE.md)

Reuse เต็มที่จาก Cultivator Brain v2 (tiandao/ai/) ตามที่ ROLE (1).md ระบุไว้ใน PROJECT CONTEXT ว่า
โปรเจกต์มี Memory อยู่แล้ว: tiandao/ai/memory.py (relationship/reputation), tiandao/ai/llm_agent.py
(infer_emotion) — ไม่เขียนตรรกะพวกนี้ซ้ำ

**ข้อจำกัดที่ต้องรู้ก่อนใช้งานจริง (สำคัญ — ROLE.md ตั้ง "Realm ต้องตรง"/"Relationship ต้องตรง" เป็น
กฎ validator ตรงๆ ใน Phase D):**

- **Realm**: เอนจินไม่เคยบันทึกขั้นที่แน่นอน ณ เวลาของแต่ละเหตุการณ์มาก่อนรอบนี้ (การถอยขั้นจาก decay
  สูงไม่ถูก log เป็น event เลย) — แก้ `tiandao/models.py`+`sim.py` ให้บันทึก `Event.realm` จริงแล้ว
  (เหมือน margin/winner/place ก่อนหน้า) เหตุการณ์ที่เกิด**หลัง**การแก้นี้จะมี realm ตรงเป๊ะ
  (`realm_source="logged"`) เหตุการณ์เก่าก่อนหน้า fallback ไปใช้ `ch.realm` ปัจจุบัน
  (`realm_source="estimated_current"` — บอก validator ว่าต้องตรวจเข้มกว่าปกติ หรือไม่เอาไปใช้เลยก็ได้)
- **Current Goal**: **ไม่ใช้** `brain.current_goal` (Phase 2 ของ Cultivator Brain v2) ตรงๆ เพราะนั่น
  คือ snapshot ปัจจุบัน (ท้ายซิม) ไม่ใช่ ณ เวลาของฉากในอดีต — ใช้ตาราง `goal_by_scene_type` ใน
  config.yaml แทน (ฉาก Breakthrough ก็คือกำลังไล่ Breakthrough อยู่จริงตอนนั้น) กราวด์กับฉาก 100%
- **Reputation**: reconstruct จริงด้วยการ replay `tiandao/ai/memory.py:update_reputation()` ย้อนหลัง
  เฉพาะเหตุการณ์ก่อน `scene.day_start` ในภูมิภาคของฉากนั้นเท่านั้น — ไม่ใช้ live `brain.reputation`
  ที่เป็นยอดสะสมท้ายซิม
- **Relationship**: ยังใช้ end-state จริงของ `ch.rivals`/`ch.bonds` (ปัจจุบัน) เพราะเอนจินไม่ได้เก็บ
  ตัวเลขที่บวกแต่ละครั้งไว้เป็น field ให้ replay ได้แบบเดียวกับ reputation — ทำเครื่องหมาย
  `relationship_source="current"` ไว้เสมอให้ Phase D รู้ข้อจำกัดนี้
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from tiandao import config as C
from tiandao.ai import llm_agent as CB_LLM
from tiandao.ai import memory as CB_MEM

from . import memory_retriever as MR
from .parser import ParsedEvent, load_config
from .scene_extractor import Scene


@dataclass
class CharacterContext:
    cid: int
    name: str
    dao: str
    realm_name: str
    realm_source: str            # "logged" | "estimated_current"
    traits: List[str]
    fear: float
    greed: float
    compassion: float
    archetype: str
    relationship: List[Dict]     # [{"cid":.., "name":.., "score":..}] เรียงตามความเข้มข้น
    relationship_source: str     # "current" เสมอ (ดู docstring หัวไฟล์)
    reputation: Dict[str, int]   # {"fame":.., "notoriety":..} ของภูมิภาคของฉาก ณ วันที่ของฉาก
    current_goal: str
    emotion: str
    recent_memory: List[str] = field(default_factory=list)


def _realm_name_for(ch, scene_realm: int) -> Tuple[str, str]:
    """คืน (ชื่อขั้น, source) — ใช้ realm ที่ log ไว้จริงถ้ามี (>=0) ไม่งั้น fallback เป็นปัจจุบัน"""
    if scene_realm is not None and scene_realm >= 0:
        return C.realm_name(ch.tier, scene_realm), "logged"
    return ch.realm_name(), "estimated_current"


def _reputation_as_of(region: str, character_log: List[ParsedEvent], cutoff_day: int) -> Dict[str, int]:
    """replay tiandao/ai/memory.py:update_reputation() ย้อนหลังเฉพาะเหตุการณ์ก่อน cutoff_day ที่เกิด
    ในภูมิภาคของฉากนี้เท่านั้น — ไม่ใช้ live brain.reputation ที่เป็นยอดสะสมท้ายซิม (ดู docstring หัวไฟล์)"""
    rep: Dict[str, Dict[str, int]] = {}
    for e in character_log:
        if e.day >= cutoff_day:
            continue
        CB_MEM.update_reputation(rep, region, e)
    return rep.get(region, {"fame": 0, "notoriety": 0})


def build_context(scene: Scene, sim, character_log: List[ParsedEvent], cid: int,
                   full: bool = True, config: Optional[dict] = None) -> CharacterContext:
    """ประกอบ context ของตัวละคร cid หนึ่งคนสำหรับฉากนี้ — full=False ให้แค่ field พื้นฐาน (สำหรับ
    ผู้ร่วมฉากที่ไม่ใช่ตัวโฟกัส กัน "ยัดทั้งชีวิต" ตามที่ ROLE.md สั่ง)"""
    cfg = config or load_config()
    ch = next((c for c in sim.cast if c.cid == cid), None)
    if ch is None:
        raise ValueError(f"ไม่พบตัวละคร cid={cid}")

    anchor = scene.events[-1] if scene.events else None
    # หา realm ที่ log จริงจาก "เหตุการณ์ล่าสุดในฉากนี้ที่ cid คนนี้เป็น actor" ไม่ใช่แค่ anchor
    # (เหตุการณ์สุดท้ายของฉาก) เพราะฉากหนึ่งมีได้หลายผู้ร่วม แต่ละคนอาจเป็น actor ของคนละเหตุการณ์
    # ภายในฉากเดียวกัน (พบเป็นบั๊กจริงตอนทดสอบ Phase E — ผู้ร่วมฉากที่ไม่ใช่ actor ของ anchor เคย
    # ได้ realm ปัจจุบัน (ผิด) แทนที่จะเป็น realm ที่ log ไว้จริงตอนเหตุการณ์ของตัวเอง)
    own_event = next((e for e in reversed(scene.events) if e.actor == cid), None)
    scene_realm = own_event.realm if own_event is not None else -1
    realm_name, realm_source = _realm_name_for(ch, scene_realm)

    if not full:
        return CharacterContext(
            cid=cid, name=ch.name, dao=ch.dao, realm_name=realm_name, realm_source=realm_source,
            traits=[], fear=ch.fear, greed=ch.greed, compassion=ch.compassion, archetype=ch.archetype,
            relationship=[], relationship_source="current", reputation={},
            current_goal="", emotion="", recent_memory=[],
        )

    region = sim.world(scene.world_id).name
    rel = [{"cid": rcid, "name": next((c.name for c in sim.cast if c.cid == rcid), str(rcid)),
            "score": score} for rcid, score in CB_MEM.top_relationships(ch, n=5)]
    rival_cids = set(ch.rivals.keys())
    reputation = _reputation_as_of(region, character_log, scene.day_start)
    goal = cfg.get("goal_by_scene_type", {}).get(scene.scene_type, cfg.get("default_goal", ""))
    emotion = CB_LLM.infer_emotion(ch, anchor) if anchor is not None else ""
    recent_memory = MR.retrieve_relevant_memory(scene, character_log, rival_cids, cfg)

    return CharacterContext(
        cid=cid, name=ch.name, dao=ch.dao, realm_name=realm_name, realm_source=realm_source,
        traits=list(ch.traits), fear=ch.fear, greed=ch.greed, compassion=ch.compassion,
        archetype=ch.archetype, relationship=rel, relationship_source="current",
        reputation=reputation, current_goal=goal, emotion=emotion, recent_memory=recent_memory,
    )


def build_scene_context(scene: Scene, sim, by_cid: Dict[int, List[ParsedEvent]],
                         config: Optional[dict] = None) -> Dict[int, "CharacterContext"]:
    """context ของผู้เกี่ยวข้องทุกคนในฉาก — เต็มเฉพาะตัวโฟกัส คนอื่นได้แค่พื้นฐาน (ห้ามยัดทั้งชีวิต)"""
    cfg = config or load_config()
    result: Dict[int, CharacterContext] = {}
    for cid in scene.participants:
        full = (cid == scene.focal_cid)
        result[cid] = build_context(scene, sim, by_cid.get(cid, []), cid, full=full, config=cfg)
    return result
