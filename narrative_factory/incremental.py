# -*- coding: utf-8 -*-
"""Phase F — Incremental Learning: อย่าประมวลผล/export ซ้ำทุกครั้งที่โลกโตขึ้น

เก็บ high-water-mark (seq เหตุการณ์ล่าสุดที่เคย export ไปแล้ว) ไว้ใน datasets/export_state.json —
รันครั้งถัดไปจะ export "เฉพาะฉากใหม่" เท่านั้น (ที่มีอย่างน้อยหนึ่งเหตุการณ์ seq สูงกว่า mark เดิม)
ไม่ใช่ประมวลผลทุกฉากในซิมใหม่หมดทุกครั้ง — v{N} แต่ละโฟลเดอร์จึงเป็น "ส่วนเพิ่ม" (delta) ต้องเอา
v1..vN มารวมกันถึงจะได้ dataset เต็ม สอดคล้องกับที่ ROLE.md ตั้งใจไว้ ("Day 1 -> 2,000 scenes,
Day 10 -> 20,000 scenes" — สะสมไปเรื่อยๆ ไม่ใช่นับใหม่ทุกครั้ง)

ฉากหนึ่งถือว่า "ใหม่" ถ้ามีอย่างน้อยหนึ่งเหตุการณ์ seq > last_exported_seq — ครอบคลุมทั้งฉากที่เพิ่ง
เกิดทั้งฉากเลย และฉากเก่าที่ถูกเหตุการณ์ใหม่มา "ต่อ" เข้าไปอีก (ยังอยู่ใน scene_merge_window_days
เดิม) เพราะ seq เป็น ID ไม่ซ้ำจริงต่อเหตุการณ์แล้ว (แก้ที่ tiandao/sim.py ตอน Phase E)
"""
import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Dict, List

from .scene_extractor import Scene

STATE_FILENAME = "export_state.json"


@dataclass
class ExportState:
    last_exported_seq: int = -1
    history: List[Dict] = field(default_factory=list)


def load_state(datasets_dir: str) -> ExportState:
    path = os.path.join(datasets_dir, STATE_FILENAME)
    if not os.path.exists(path):
        return ExportState()
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return ExportState(last_exported_seq=data.get("last_exported_seq", -1),
                        history=data.get("history", []))


def save_state(datasets_dir: str, state: ExportState) -> None:
    os.makedirs(datasets_dir, exist_ok=True)
    with open(os.path.join(datasets_dir, STATE_FILENAME), "w", encoding="utf-8") as f:
        json.dump(asdict(state), f, ensure_ascii=False, indent=2)


def select_new_scenes(scenes: List[Scene], last_exported_seq: int) -> List[Scene]:
    """คัดเฉพาะฉากที่มีเหตุการณ์ใหม่อย่างน้อยหนึ่งอัน (seq > last_exported_seq)"""
    return [s for s in scenes if any(e.seq > last_exported_seq for e in s.events)]


def record_export(state: ExportState, version_dir: str, scenes: List[Scene]) -> None:
    """อัปเดต state หลัง export สำเร็จ — เรียกเฉพาะตอนมีฉากใหม่จริงเท่านั้น"""
    if not scenes:
        return
    max_seq = max(e.seq for s in scenes for e in s.events)
    state.last_exported_seq = max(state.last_exported_seq, max_seq)
    state.history.append({
        "version": os.path.basename(version_dir),
        "exported_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "scene_count": len(scenes),
        "max_seq": max_seq,
    })
