# -*- coding: utf-8 -*-
"""Phase K1 — Narrative Teacher: วิเคราะห์ "ศิลปะการเล่าเรื่อง" ของแต่ละฉากจากข้อมูลจริงเท่านั้น
(rule-based ล้วน ไม่ใช้ LLM, deterministic) ต่อยอดจาก `Scene`/`NarrativeGenome` ที่มีอยู่แล้ว
(`scene_extractor.py`/`genome.py` — Phase B) ตาม `ROLE` Phase K: "ต้องวิเคราะห์จากข้อมูลจริงเท่านั้น
ห้ามแต่งเหตุการณ์ใหม่"

รับ `Scene` หนึ่งฉาก คืน `StoryLesson` — ไม่มีฟิลด์ไหนแต่งขึ้นลอยๆ ทุกการวิเคราะห์ย่อยกระจายออกไปเป็น
โมดูลของตัวเอง (K2-K4) แล้ว `teacher.py` เป็นแค่ตัวประกอบร่างรวม ไม่ duplicate logic:
- **hook**: เรียก `hook_detector.py` (Phase K3) — map จาก `event.kind` จริงของเหตุการณ์แรกก่อน
  fallback ไปที่ `scene_type`
- **conflict**: map จาก `scene_type` ผ่านตาราง `config.yaml:conflict_type_by_scene_type` — ตาม
  pattern เดียวกับ `goal_by_scene_type`/`style_tags_by_scene_type` เดิม ไม่ hardcode ใน Python
- **escalation**: เรียก `genome.compute_conflict_level()` ตัวเดียวกับที่ `genome.py` ใช้คำนวณ
  `NarrativeGenome.conflict_level` — แต่คำนวณ**ทุกเหตุการณ์ในฉาก**ไม่ใช่แค่ anchor แล้ว bucket เป็น
  Low/Medium/High/Peak ให้เห็นการไต่ระดับจริงตามลำดับเวลา
- **payoff**: เรียก `payoff_detector.py` (Phase K4) — reuse `scene.genome.foreshadowing`/
  `scene.genome.payoff` ตรงๆ (Expectation -> Result) ไม่คำนวณซ้ำ
- **emotional_shift**: แปลง escalation (ที่กราวด์กับ log จริงแล้ว) เป็นคำอารมณ์ — คำที่ Peak ขึ้นกับ
  ผลแพ้ชนะจริงของเหตุการณ์สุดท้าย (`ev.deltas["winner"]` ผ่าน `scene_extractor._is_win_for()`) ไม่ใช่
  การเดา
- **pacing**: เรียก `pacing.py` (Phase K2) — สรุป Beat chain ของฉาก (เช่น "Rising -> Peak")
- **lesson**: ประโยคสรุปที่ประกอบจาก field อื่นทั้งหมดล้วนๆ (string formatting ไม่ใช้ LLM)
"""
from dataclasses import dataclass, field
from typing import List, Optional

from .parser import load_config
from .scene_extractor import Scene, _is_win_for


@dataclass
class StoryLesson:
    scene_id: str
    hook: str
    conflict: str
    escalation: List[str] = field(default_factory=list)
    payoff: str = ""
    emotional_shift: List[str] = field(default_factory=list)
    pacing: str = ""
    lesson: str = ""


_TENSION_BUCKETS = [(25, "Low"), (50, "Medium"), (75, "High"), (101, "Peak")]

_EMOTION_WORD_BY_BUCKET = {"Low": "Hope", "Medium": "Fear", "High": "Despair"}
_PEAK_WORD_WIN = "Resolve"
_PEAK_WORD_LOSS = "Despair"
_PEAK_WORD_UNKNOWN = "Reckoning"


def _tension_bucket(level: int) -> str:
    for ceiling, label in _TENSION_BUCKETS:
        if level < ceiling:
            return label
    return "Peak"


def analyze_hook(scene: Scene, config: dict) -> str:
    """เรียก `hook_detector.py` (Phase K3) จริง แทน logic เดิมของ K1 (ไม่ duplicate) — ละเอียดกว่าเดิม
    เพราะ K3 ตรวจ `event.kind` จริงก่อนจะ fallback มาที่ `scene_type`"""
    from . import hook_detector as HD
    return HD.detect_hook(scene.events, config)


def analyze_conflict(scene: Scene, config: dict) -> str:
    """ประเภทความขัดแย้งหลัก — map จาก `scene_type` ของฉาก (= scene_type ของ anchor)"""
    table = config.get("conflict_type_by_scene_type", {})
    return table.get(scene.scene_type, config.get("default_conflict_type", "External"))


def analyze_escalation(scene: Scene, config: dict) -> List[str]:
    """ไต่ระดับความตึงเครียดจริงต่อเหตุการณ์ในฉาก — เรียก `genome.compute_conflict_level()` ตัวเดียวกับ
    `genome.py` ต่อ**ทุกเหตุการณ์**ในฉาก (ไม่ใช่แค่ anchor แบบที่ `NarrativeGenome.conflict_level` ทำ)
    คืน list ของ label เรียงตามเวลาจริง"""
    from . import genome as G
    return [_tension_bucket(G.compute_conflict_level(e, config)) for e in scene.events]


def analyze_payoff(scene: Scene) -> str:
    """เรียก `payoff_detector.py` (Phase K4) จริง แทน logic เดิมของ K1 (ไม่ duplicate)"""
    from . import payoff_detector as PD
    return PD.detect_payoff(scene)


def analyze_emotional_shift(scene: Scene, escalation: List[str]) -> List[str]:
    """แปลง escalation (ที่กราวด์กับ log จริงแล้วจาก `analyze_escalation`) เป็นคำอารมณ์ — คำที่ระดับ
    Peak ขึ้นกับผลแพ้ชนะ**จริง**ของเหตุการณ์สุดท้ายในฉาก (`ev.deltas["winner"]`) ไม่ใช่การเดา ถ้าไม่มี
    ข้อมูลผลแพ้ชนะ (ไม่ใช่เหตุการณ์ต่อสู้/log เก่า) ใช้คำกลางๆ ที่ไม่ฟันธงว่าแพ้หรือชนะแทน"""
    is_win = _is_win_for(scene.focal_cid, scene.events[-1]) if scene.events else None
    if is_win is True:
        peak_word = _PEAK_WORD_WIN
    elif is_win is False:
        peak_word = _PEAK_WORD_LOSS
    else:
        peak_word = _PEAK_WORD_UNKNOWN
    return [peak_word if label == "Peak" else _EMOTION_WORD_BY_BUCKET.get(label, peak_word)
            for label in escalation]


def analyze_pacing(scene: Scene) -> str:
    """เรียก `pacing.py` (Phase K2) จริง — คืน Beat chain สรุป เช่น "Rising -> Peak" (แทนฮิวริสติก
    เร็ว/ปานกลาง/ช้า แบบเดิมที่ K1 ทำไว้ชั่วคราวก่อน K2 จะเสร็จ — ไม่ duplicate logic)"""
    from . import pacing as PC
    return PC.pacing_summary(PC.assign_beats(len(scene.events)))


def build_lesson_text(hook: str, conflict: str, escalation: List[str], payoff: str,
                       emotional_shift: List[str], pacing: str) -> str:
    """ประกอบ "lesson" เป็นประโยคสรุปเดียว — เรียงต่อจาก field อื่นทั้งหมดล้วนๆ ไม่ใช้ LLM (เหมือนแนวทาง
    `exporter.py:_template_scene_prose()` ที่กราวด์ 100% เป็นค่าเริ่มต้น)"""
    esc_text = " -> ".join(escalation) if escalation else "(ไม่มีเหตุการณ์)"
    emo_text = " -> ".join(emotional_shift) if emotional_shift else "(ไม่มีเหตุการณ์)"
    return (f"เปิดฉากด้วย Hook แบบ {hook} เป็นความขัดแย้งประเภท {conflict} "
            f"ความตึงเครียดไต่ระดับ {esc_text} จังหวะ (Beat): {pacing} "
            f"อารมณ์ของฉากขยับจาก {emo_text} จบด้วย {payoff}")


def build_story_lesson(scene: Scene, config: Optional[dict] = None) -> StoryLesson:
    """เอนทรีพอยต์หลักของ Phase K1 — รับ Scene หนึ่งฉาก คืน StoryLesson (rule-based ล้วน)"""
    cfg = config or load_config()
    hook = analyze_hook(scene, cfg)
    conflict = analyze_conflict(scene, cfg)
    escalation = analyze_escalation(scene, cfg)
    payoff = analyze_payoff(scene)
    emotional_shift = analyze_emotional_shift(scene, escalation)
    pacing = analyze_pacing(scene)
    lesson = build_lesson_text(hook, conflict, escalation, payoff, emotional_shift, pacing)
    return StoryLesson(scene_id=scene.scene_id, hook=hook, conflict=conflict,
                        escalation=escalation, payoff=payoff, emotional_shift=emotional_shift,
                        pacing=pacing, lesson=lesson)
