# -*- coding: utf-8 -*-
"""Phase K2 — Pacing Engine: กางหนึ่งจุดเปลี่ยนออกเป็นฉากเต็มที่เขียนเป็นหนังได้

**เขียนใหม่ทั้งแนวคิด** — ของเดิม `assign_beats(n_events)` แจก 1 บีตต่อ 1 เหตุการณ์ ซึ่งเมื่อรวมกับ
บั๊กของ scene_extractor ที่ทำให้ทุกฉากมีเหตุการณ์เดียว (วัดจริง 100%) ผลคือทุกฉากได้บีตเดียวคือ Peak
แล้ว `scoring._pacing_score` ก็ไปลงโทษร้อยแก้วที่ยาวเกินหนึ่งย่อหน้า — ระบบทั้งระบบจึงบังคับให้เขียน
ฉากละหนึ่งย่อหน้าโดยไม่มีใครตั้งใจ ซึ่งขัดกับเป้าหมาย "นิยายยาว มีบทสนทนาละเอียด เหมือนดูหนัง" ตรงๆ

แนวคิดใหม่: **หนึ่งจุดเปลี่ยน = หนึ่งฉากเต็ม 5 บีตเสมอ** ไม่ขึ้นกับว่ามีเหตุการณ์ดิบกี่อัน
เหตุการณ์ดิบเป็น "วัตถุดิบ" ของบีต ไม่ใช่ตัวกำหนดจำนวนบีต

  Opening    ที่ไหน เมื่อไหร่ ใครอยู่ตรงนั้น อากาศเป็นยังไง — ปูภาพ ไม่มีบทพูด
  Inciting   อะไรพาเขามาถึงจุดนี้ (เหตุการณ์นำ) — เริ่มมีบทพูดสั้นๆ
  Rising     การเผชิญหน้า — **บทสนทนาหลักอยู่ตรงนี้** ยาวที่สุดในฉาก
  Peak       จุดที่สถานะเปลี่ยนจริง (anchor) — การกระทำและคำพูดที่ตัดสิน
  Aftermath  ผลที่ตามมาทันที ใครเห็น ใครจำ — ปิดฉาก
"""
from dataclasses import dataclass, field
from typing import Dict, List

from .scene_extractor import Scene

BEAT_STAGES = ["Opening", "Inciting", "Rising", "Peak", "Aftermath"]

# สัดส่วนความยาวที่คาดหวังของแต่ละบีต — ใช้บอกคนเขียนว่าควรลงน้ำหนักตรงไหน
BEAT_WEIGHT = {"Opening": 0.15, "Inciting": 0.15, "Rising": 0.35,
               "Peak": 0.25, "Aftermath": 0.10}

# บีตที่ต้องมีบทพูดจริง — ฉากที่ไม่มีบทพูดใน Rising/Peak ไม่นับว่าเป็นฉากหนัง
DIALOGUE_BEATS = ("Inciting", "Rising", "Peak")

# ช่วงจำนวนย่อหน้าที่ถือว่าเป็น "ฉากเต็ม" (ต่ำกว่านี้คือสรุป สูงกว่านี้คือเยิ่นเย้อ)
PARAGRAPH_RANGE = (8, 22)


@dataclass
class Beat:
    stage: str
    weight: float
    wants_dialogue: bool
    material: List[str] = field(default_factory=list)   # เหตุการณ์ดิบที่บีตนี้ใช้เป็นวัตถุดิบ


@dataclass
class SceneBeats:
    scene_id: str
    beats: List[Beat]

    @property
    def stages(self) -> List[str]:
        return [b.stage for b in self.beats]


def assign_beats(n_events: int = 0) -> List[str]:
    """คงชื่อเดิมไว้เพื่อความเข้ากันได้ — แต่คืนโครง 5 บีตเสมอ ไม่ขึ้นกับจำนวนเหตุการณ์

    โครงของฉากเป็นเรื่องของการเล่า ไม่ใช่ของจำนวนแถวใน log
    """
    return list(BEAT_STAGES)


def build_scene_beats(scene: Scene) -> SceneBeats:
    """กางฉากเป็น 5 บีต พร้อมแจกเหตุการณ์ดิบให้บีตที่ควรใช้มัน

    anchor (เหตุการณ์สุดท้าย = จุดเปลี่ยน) เป็นวัตถุดิบของ Peak เสมอ ส่วนเหตุการณ์นำกระจายลง
    Inciting/Rising — นั่นคือ "เขาทำอะไรมาก่อนจะถึงจุดนี้"
    """
    events = list(scene.events or [])
    anchor = events[-1] if events else None
    lead = events[:-1]
    half = (len(lead) + 1) // 2
    material: Dict[str, List[str]] = {s: [] for s in BEAT_STAGES}
    for e in lead[:half]:
        material["Inciting"].append(f"วันที่ {e.day}: {e.text}")
    for e in lead[half:]:
        material["Rising"].append(f"วันที่ {e.day}: {e.text}")
    if anchor is not None:
        material["Peak"].append(f"วันที่ {anchor.day}: {anchor.text}")
    return SceneBeats(
        scene_id=scene.scene_id,
        beats=[Beat(stage=s, weight=BEAT_WEIGHT[s],
                    wants_dialogue=s in DIALOGUE_BEATS,
                    material=material[s]) for s in BEAT_STAGES],
    )


def pacing_summary(beats) -> str:
    """สรุปโครงฉากสั้นๆ — รับได้ทั้ง List[str] แบบเดิม และ List[Beat] แบบใหม่"""
    if not beats:
        return "(ไม่มีเหตุการณ์)"
    return " -> ".join(b if isinstance(b, str) else b.stage for b in beats)
