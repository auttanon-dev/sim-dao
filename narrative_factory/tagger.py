# -*- coding: utf-8 -*-
"""Automatic Style Tagging — ติด tag ตามที่ ROLE.md กำหนด (รองรับหลาย tag ต่อฉาก)

ข้อจำกัดตรงไปตรงมา: เอนจินนี้ไม่มีกลไก Romance/Comedy เลย (ไม่มีระบบความรักหรืออารมณ์ขันที่เป็น
เหตุการณ์แยกให้ตรวจจับ) จึงไม่มีทางติด tag สองอันนี้ได้อย่างมีมูล — ไม่ติดแบบเดามั่วดีกว่าติดผิด
"""
from typing import List, Optional

from .parser import load_config
from .scene_extractor import Scene


def tag_scene(scene: Scene, config: Optional[dict] = None) -> List[str]:
    cfg = config or load_config()
    tags = list(cfg.get("style_tags_by_scene_type", {}).get(scene.scene_type, []))
    threshold = cfg.get("style_tag_conflict_threshold", 60)
    if scene.genome.conflict_level >= threshold and "Action" not in tags:
        tags.append("Action")
    return tags or ["Other"]
