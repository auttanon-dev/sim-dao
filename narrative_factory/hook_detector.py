# -*- coding: utf-8 -*-
"""Phase K3 — Hook Detector: จำแนกฉากเปิดเรื่องด้วยอะไร (Danger/Mystery/Desire/Opportunity/
World Event) จาก **event.kind จริง** ของเหตุการณ์แรกในฉาก — rule-based ล้วน ไม่ใช้ LLM ตามที่ `ROLE`
Phase K กำหนดตรงๆ ("ใช้ Rule-based ไม่ใช้ LLM")

ละเอียดกว่า `teacher.py` เดิมของ K1 (ที่ map จาก `scene_type` ระดับหมวดใหญ่เท่านั้น) — ไฟล์นี้ map จาก
`event.kind` ตรงๆ ก่อน (ตาราง `hook_by_kind` ใน `config.yaml`) ถ้าไม่รู้จัก kind นั้นเลยค่อย fallback
ไปที่ `hook_by_scene_type` เดิมของ K1 (ไม่สร้างตาราง fallback ซ้ำซ้อน — reuse ของเดิม) — `teacher.py`
แก้ให้เรียกไฟล์นี้แทนที่จะมี logic ของตัวเองซ้ำ (K1 ทำ hook ไว้ในตัวชั่วคราวก่อน K3 จะเสร็จ)
"""
from typing import List, Optional

from .parser import ParsedEvent, load_config


def detect_hook(events: List[ParsedEvent], config: Optional[dict] = None) -> str:
    """รับ list เหตุการณ์ของฉาก (ต้องเรียงตามเวลาแล้ว — ดู `scene_extractor.py`) คืน Hook category ของ
    **เหตุการณ์แรก** เท่านั้น เพราะ Hook คือสิ่งที่ผู้อ่านเจอก่อนเสมอ ไม่ใช่ผลลัพธ์ท้ายฉาก"""
    cfg = config or load_config()
    if not events:
        return cfg.get("default_hook", "Mystery")
    first = events[0]
    by_kind = cfg.get("hook_by_kind", {})
    if first.kind in by_kind:
        return by_kind[first.kind]
    by_scene_type = cfg.get("hook_by_scene_type", {})
    return by_scene_type.get(first.scene_type, cfg.get("default_hook", "Mystery"))
