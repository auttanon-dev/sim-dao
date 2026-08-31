# -*- coding: utf-8 -*-
"""Phase K2 — Pacing Engine: แบ่ง Scene เป็น Beat (Opening/Inciting/Rising/Peak/Aftermath) จาก
ตำแหน่งเวลาจริงของเหตุการณ์ในฉาก — rule-based ล้วน deterministic ไม่ใช้ LLM ตาม `ROLE` Phase K

**ข้อจำกัดที่ต้องรู้ก่อนใช้งานจริง**: `Peak` คือเหตุการณ์สุดท้ายของฉากเสมอ (= anchor ตามนิยามเดิมของ
ทั้งระบบใน `genome.py`/`scene_extractor.py` ที่ใช้ `scene.events[-1]` ตัดสิน outcome/payoff ของฉาก
มาตั้งแต่ Phase B) ทำให้โครงสร้างข้อมูลนี้ไม่มีที่ว่างให้ `Aftermath` จริงที่ระดับฉากเดียว — เหตุการณ์
หลัง climax จริงๆ จะกลายเป็น**ฉากถัดไป**แยกต่างหาก (ไม่ใช่ event ในฉากเดียวกันนี้) จึง**ไม่มีทาง
เกิด `Aftermath` ในผลลัพธ์ของไฟล์นี้เลย** จนกว่าจะมี Arc Builder (Phase K5) ที่ดูข้ามหลายฉากต่อเนื่องกัน
"""
from dataclasses import dataclass
from typing import List

from .scene_extractor import Scene

BEAT_STAGES = ["Opening", "Inciting", "Rising", "Peak", "Aftermath"]

# Beat 3 ตัวแรกที่เหตุการณ์ก่อน Peak จะถูกกระจายลงไป (Peak ต่อท้ายเสมอแยกต่างหาก — ดู docstring หัวไฟล์)
_LEAD_STAGES = BEAT_STAGES[:3]


@dataclass
class SceneBeats:
    scene_id: str
    beats: List[str]  # 1 label ต่อ 1 เหตุการณ์ใน scene.events เรียงตามเวลาจริง


def assign_beats(n_events: int) -> List[str]:
    """แบ่ง n เหตุการณ์จริงของฉากลง Beat — deterministic ล้วน (ไม่มีการสุ่ม)

    - 0 เหตุการณ์: คืน list ว่าง
    - 1 เหตุการณ์: เหตุการณ์เดียวคือ Peak เสมอ (ฉากสั้นสุด ไม่มี Beat อื่นให้ลด)
    - >=2 เหตุการณ์: เหตุการณ์สุดท้าย = Peak เสมอ ส่วนที่เหลือกระจายลง Opening/Inciting/Rising ตาม
      สัดส่วนตำแหน่งเวลา (ยิ่งฉากสั้น ยิ่งตัด Beat ต้นๆ ออกก่อน ไม่ใช่ตัด Peak)
    """
    if n_events <= 0:
        return []
    if n_events == 1:
        return ["Peak"]
    lead_count = n_events - 1
    lead = [_LEAD_STAGES[min(len(_LEAD_STAGES) - 1, i * len(_LEAD_STAGES) // lead_count)]
            for i in range(lead_count)]
    return lead + ["Peak"]


def build_scene_beats(scene: Scene) -> SceneBeats:
    """เอนทรีพอยต์หลัก — รับ Scene หนึ่งฉาก คืน SceneBeats (1 label ต่อ 1 เหตุการณ์จริง)"""
    return SceneBeats(scene_id=scene.scene_id, beats=assign_beats(len(scene.events)))


def pacing_summary(beats: List[str]) -> str:
    """สรุป Beat list เป็นข้อความสั้นๆ อ่านง่าย เช่น 'Opening -> Rising -> Peak'"""
    return " -> ".join(beats) if beats else "(ไม่มีเหตุการณ์)"
