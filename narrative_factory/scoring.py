# -*- coding: utf-8 -*-
"""Phase D — Quality Scoring: แปลงผล validator.py เป็นคะแนน 0-100
ต่ำกว่า PASS_THRESHOLD = ไม่ผ่าน (reject)

หักคะแนนตามจำนวน violation ที่เกี่ยวข้องกับแต่ละ metric — ไม่ใช่ all-or-nothing (ผิด 1 จุดไม่ทำให้
metric นั้นเป็น 0 ทันที ยกเว้นผิดหลายจุดสะสมจนคะแนนหมด)

**Shadow Evaluation V2 (Phase K)**: แทนที่ `WEIGHTS`/`PASS_THRESHOLD` เดิม (Timeline 25/Character 25/
Event 20/Memory 15/Style 15, ผ่านที่ 80) ทั้งชุดตามที่ผู้ใช้เลือกไว้ตรงๆ ("แทนที่ของเดิมทั้งหมด" —
ต่างจาก Phase I ที่แยกค่าใหม่ต่างหากไม่แตะ `PASS_THRESHOLD` เดิม) — ผลคือ Dataset A-E export เดิมก็ใช้
เกณฑ์ใหม่นี้ด้วยตั้งแต่นี้ไป **ไม่ใช่แค่ Phase J's Shadow Evaluation Gate เท่านั้น** เพิ่ม metric ใหม่
`pacing` (15 คะแนน) ที่ต้องใช้ `Scene` จริงประกอบ (เทียบกับ `pacing.py:assign_beats()` — Phase K2) —
`scene` เป็น optional parameter เพื่อไม่ให้ caller เก่าที่ไม่มี Scene พร้อมใช้พังทันที (ถ้าไม่ส่งมา
ให้คะแนนเต็ม 15 แบบเป็นกลาง ไม่ลงโทษ/ให้รางวัล)
"""
from dataclasses import dataclass
from typing import TYPE_CHECKING, Dict, Optional

from .validator import _CJK_PATTERN, ValidationResult

if TYPE_CHECKING:
    from .scene_extractor import Scene

WEIGHTS = {
    "timeline": 20,
    "character_consistency": 20,
    "event_accuracy": 15,
    "memory_accuracy": 10,
    "style_quality": 20,
    "pacing": 15,
}
PASS_THRESHOLD = 85


@dataclass
class ScoreResult:
    total: int
    breakdown: Dict[str, int]
    passed: bool


def _rule_count(result: ValidationResult, rule_prefix: str) -> int:
    return sum(1 for v in result.violations if v.rule.startswith(rule_prefix))


def _pacing_score(text: str, scene: Optional["Scene"]) -> int:
    """Pacing (15 คะแนน, Shadow Evaluation V2 — Phase K2/K6): เทียบจำนวน paragraph ของ candidate
    กับจำนวน Beat จริงของฉาก (`pacing.assign_beats()`) — คร่าวๆ แต่กราวด์กับโครงสร้างจริงของฉาก
    (คนละมุมกับ `style_quality` ที่วัดคุณภาพร้อยแก้วเชิงภาษา ไม่ใช่โครงสร้าง) ไม่มี Scene ให้เทียบ
    (caller เก่าที่ยังไม่ได้ส่งมา) คืนคะแนนเต็มแบบเป็นกลาง"""
    if scene is None:
        return WEIGHTS["pacing"]
    from .pacing import assign_beats
    n_beats = len(assign_beats(len(scene.events)))
    if n_beats == 0:
        return WEIGHTS["pacing"]
    paragraphs = [p for p in text.split("\n\n") if p.strip()] or [text]
    diff = abs(len(paragraphs) - n_beats)
    return max(0, WEIGHTS["pacing"] - diff * 5)


def score_candidate(text: str, result: ValidationResult, scene: Optional["Scene"] = None) -> ScoreResult:
    """0-100 ตาม `WEIGHTS` (Shadow Evaluation V2) — **แต่ Rule 1-6 (validator.py) เป็นประตูแข็งก่อนเสมอ**:
    ผิดกฎไหนก็ตามแม้แต่ข้อเดียว ต้อง passed=False ทันที ไม่ว่าคะแนนรวมจะยังถึง `PASS_THRESHOLD` หรือไม่
    ก็ตาม (คะแนน 0-100 เป็นมาตรวัดคุณภาพเพิ่มเติมสำหรับ candidate ที่ผ่านประตูแข็งแล้วเท่านั้น ไม่ใช่
    ตัวเฉลี่ยกลบล้างการผิดกฎ)"""
    breakdown: Dict[str, int] = {}

    # Timeline: Rule2 (วันที่ปลอม) + Rule3 (ลำดับสลับ)
    n = _rule_count(result, "Rule2") + _rule_count(result, "Rule3")
    breakdown["timeline"] = max(0, WEIGHTS["timeline"] - n * 8)

    # Character Consistency: Rule1 (ตัวละครใหม่) + Rule4 (สะกดชื่อผิด)
    n = _rule_count(result, "Rule1") + _rule_count(result, "Rule4")
    breakdown["character_consistency"] = max(0, WEIGHTS["character_consistency"] - n * 8)

    # Event Accuracy: Rule2 อีกครั้ง — คนละมุมกับ timeline (เหตุการณ์ตรง log จริงไหม ไม่ใช่แค่ลำดับ)
    n = _rule_count(result, "Rule2")
    breakdown["event_accuracy"] = max(0, WEIGHTS["event_accuracy"] - n * 8)

    # Memory Accuracy: Rule5 (realm) + Rule6 (relationship) — ความถูกต้องของ context ที่ป้อนเข้าไป
    n = _rule_count(result, "Rule5") + _rule_count(result, "Rule6")
    breakdown["memory_accuracy"] = max(0, WEIGHTS["memory_accuracy"] - n * 5)

    # Style Quality: heuristic เบาๆ — CJK หลุดปน (บั๊กจริงที่เจอจาก qwen2.5vl ตอน Phase 6) + ความยาว
    style = WEIGHTS["style_quality"]
    if _CJK_PATTERN.search(text):
        style -= 13
    if len(text) < 30:
        style -= 7
    breakdown["style_quality"] = max(0, style)

    # Pacing (Phase K2/K6 — ใหม่): เทียบโครงสร้างจริงของฉากกับจำนวน paragraph ของ candidate
    breakdown["pacing"] = _pacing_score(text, scene)

    total = sum(breakdown.values())
    passed = result.passed and total >= PASS_THRESHOLD
    return ScoreResult(total=total, breakdown=breakdown, passed=passed)
