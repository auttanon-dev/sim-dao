# -*- coding: utf-8 -*-
"""Narrative Genome — "DNA ของฉาก" ต่อยอดจาก Parser (parser.py)

หน้าที่เดียวของไฟล์นี้: คำนวณ field ของ NarrativeGenome จากข้อมูลที่ "มีจริง" เท่านั้น (ParsedEvent /
sim.log ของตัวละครเดียวกัน / ch.dao) — ไม่มีฟิลด์ไหนแต่งขึ้นลอยๆ ที่มาของแต่ละ field ระบุไว้ในคอมเมนต์
ของฟังก์ชันนั้นๆ ทั้งหมด

**ข้อจำกัดที่ยืนยันกับผู้ใช้แล้วก่อนเขียนไฟล์นี้ (อ่านก่อนใช้งานจริง):**

- **conflict_level**: `tiandao/sim.py` เพิ่งถูกแก้ให้บันทึก `d["margin"]` จริงจากการต่อสู้ลง
  `event.deltas` แล้ว (7 จุดที่มีการชนกัน) — log ที่สร้าง**หลัง**การแก้นี้จะมี conflict_level แม่นจาก
  margin จริง ส่วน log/save **เก่า**ที่สร้างก่อนหน้านี้จะไม่มี field นี้ เลย fallback ไปที่ตาราง
  `outcome_fallback` ใน config.yaml แทนโดยอัตโนมัติ (แม่นน้อยกว่า แต่ยังกราวด์กับ outcome จริง)
- **emotion_curve**: เป็น **"narrative pacing template"** เลือกจาก (scene_type, win/loss) **ไม่ใช่
  ค่าที่วัดจริงจากซิม** เพราะเอนจินเป็น discrete-event (1 เทิร์น = 1 เหตุการณ์) ไม่มี sub-beat ให้วัด
  ความรู้สึกระหว่างเหตุการณ์จริง — ตัดสินใจร่วมกับผู้ใช้แล้วว่ายอมรับแนวทางนี้ (บอกไว้ใน metadata
  เสมอว่าเป็น template ไม่ใช่ telemetry)
- **foreshadowing**: ค้นย้อนหลังใน `character_log` ของ "ตัวละครโฟกัส" เดียวกันเท่านั้น (คนละคนกัน
  ไม่ปนกัน) คืน**ข้อความจริงจาก log ที่พบเท่านั้น** ไม่เจอ = list ว่างเสมอ ไม่เคยแต่งขึ้นมาเอง
  (validator.py — Phase D จะเช็คซ้ำอีกชั้นว่าทุกข้อความอ้างอิงได้จริงใน log ต้นทาง) — **เพิ่ม
  participant-overlap filter แล้ว** (พบจริงตอน spot-check `loras/v5`: ฉาก `1-2945` ได้ foreshadowing
  ที่อ้างถึง "เย่เฟย" ทั้งที่ไม่ใช่ผู้เกี่ยวข้องในฉากนั้นเลย — เหตุการณ์ precursor เป็นของจริง กราวด์กับ
  log จริง แต่คู่กรณีในเหตุการณ์นั้นเป็นคนละคนกับฉากปัจจุบัน ทำให้ "การปูเรื่อง" ไม่เชื่อมโยงกับฉากจริง
  แม้จะไม่ใช่การแต่งข้อมูลก็ตาม) ตอนนี้ precursor event ที่มีคู่กรณี (ไม่ใช่เหตุการณ์เดี่ยว) ต้องมีคู่กรณี
  นั้นอยู่ในกลุ่มผู้เกี่ยวข้องของฉากปัจจุบันด้วย ถึงจะนับเป็น foreshadowing ได้ — เหตุการณ์เดี่ยว (ไม่มี
  target เช่น บำเพ็ญคนเดียว) ยังผ่านได้เหมือนเดิมเสมอ (ไม่มีคู่กรณีให้ขัดแย้ง)
"""
from dataclasses import dataclass, field
from typing import List, Optional, Set

from .parser import ParsedEvent, load_config


@dataclass
class NarrativeGenome:
    scene_type: str
    emotion_curve: List[int]
    conflict_level: int
    dao_theme: str
    foreshadowing: List[str] = field(default_factory=list)
    payoff: str = ""


def compute_conflict_level(ev: ParsedEvent, config: Optional[dict] = None) -> int:
    """0-100 — ใช้ margin จริงจาก event.deltas["margin"] ถ้ามี (ต่อสู้จริง คำนวณจากพลังสองฝ่าย)
    ไม่มี (log เก่า/ไม่ใช่เหตุการณ์ต่อสู้) ใช้ outcome_fallback table ตาม outcome ที่มีอยู่ใน log แทน"""
    cfg = config or load_config()
    ccfg = cfg["conflict_level"]
    margin = ev.deltas.get("margin")
    if margin is not None:
        try:
            scaled = float(margin) / float(ccfg["margin_scale"]) * 100.0
            return int(max(0, min(100, round(scaled))))
        except (TypeError, ValueError):
            pass
    table = ccfg["outcome_fallback"]
    return int(table.get(ev.outcome, table["default"]))


def compute_emotion_curve(scene_type: str, is_win: Optional[bool] = None,
                           config: Optional[dict] = None) -> List[int]:
    """narrative pacing template — ดู docstring หัวไฟล์เรื่องข้อจำกัด เลือก win/loss variant ถ้ามีให้
    (Phase B ต้องรู้แล้วว่าตัวละครโฟกัสของฉากนี้ชนะหรือแพ้ ถึงจะส่ง is_win มาได้)"""
    cfg = config or load_config()
    templates = cfg["emotion_curve_templates"]
    bucket = templates.get(scene_type, templates["default"])
    if is_win is True and "win" in bucket:
        return list(bucket["win"])
    if is_win is False and "loss" in bucket:
        return list(bucket["loss"])
    return list(bucket.get("default", next(iter(bucket.values()))))


def compute_dao_theme(dao: str) -> str:
    """ch.dao ตรงๆ ไม่แปลง/ไม่เดา — กราวด์กับข้อมูลจริง 100%"""
    return dao


def compute_foreshadowing(scene: ParsedEvent, character_log: List[ParsedEvent],
                           other_participants: Set[int],
                           config: Optional[dict] = None) -> List[str]:
    """ค้นย้อนหลังใน character_log (เหตุการณ์ทั้งหมดของตัวละครโฟกัสคนเดียวกัน) หา event kind ที่
    รู้จักว่าเป็นตัวปูเรื่องของ scene_type (payoff) นี้ตาม foreshadowing_precursors ใน config.yaml

    `other_participants` = ผู้เกี่ยวข้องอื่นในฉากปัจจุบัน (ไม่รวมตัวละครโฟกัส) — precursor event ที่มี
    คู่กรณี (actor/target อีกฝ่ายไม่ใช่ตัวละครโฟกัส) ต้องมีคู่กรณีนั้นอยู่ในกลุ่มนี้ด้วย ไม่งั้นจะได้
    foreshadowing ที่กราวด์กับ log จริง แต่พูดถึงคนละคนกับฉากปัจจุบัน (พบจริงจาก spot-check loras/v5 —
    ดู docstring หัวไฟล์) เหตุการณ์เดี่ยวที่ไม่มีคู่กรณี (target=None) ผ่านได้เสมอ ไม่มีอะไรให้ขัดแย้ง"""
    cfg = config or load_config()
    precursor_kinds = cfg.get("foreshadowing_precursors", {}).get(scene.scene_type)
    if not precursor_kinds:
        return []
    lookback = cfg.get("foreshadowing_lookback_days", 3650)
    max_items = cfg.get("foreshadowing_max_items", 2)
    found = [
        e.text for e in character_log
        if e.kind in precursor_kinds and e.day < scene.day and (scene.day - e.day) <= lookback
        and (e.target is None or {e.actor, e.target} & other_participants)
    ]
    return found[-max_items:]


def compute_payoff(scene: ParsedEvent) -> str:
    """ผลลัพธ์ของฉากนี้ตรงๆ จาก log — ไม่แต่งเพิ่ม"""
    return f"{scene.outcome}: {scene.text}" if scene.outcome else scene.text


def build_genome(scene: ParsedEvent, dao: str, character_log: List[ParsedEvent],
                  other_participants: Set[int],
                  is_win: Optional[bool] = None, config: Optional[dict] = None) -> NarrativeGenome:
    """ประกอบ NarrativeGenome ครบทุก field — เรียกจาก scene_extractor.py (Phase B) ที่รู้แล้วว่า
    ฉากนี้เป็นของตัวละครไหน (dao/character_log/is_win/other_participants มาจากตรงนั้น ไม่ใช่หน้าที่ของ
    ไฟล์นี้ที่จะไปหาเอง)"""
    cfg = config or load_config()
    return NarrativeGenome(
        scene_type=scene.scene_type,
        emotion_curve=compute_emotion_curve(scene.scene_type, is_win, cfg),
        conflict_level=compute_conflict_level(scene, cfg),
        dao_theme=compute_dao_theme(dao),
        foreshadowing=compute_foreshadowing(scene, character_log, other_participants, cfg),
        payoff=compute_payoff(scene),
    )
