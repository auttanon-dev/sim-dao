# -*- coding: utf-8 -*-
"""Dataset Versioning — โฟลเดอร์ datasets/v{N}/ ใหม่ทุกครั้งที่ export ตามโครงสร้างที่ ROLE.md กำหนด

Phase E นี้: export ทุกอย่างที่พบเป็นเวอร์ชันใหม่เสมอ — "ไม่ประมวลผลซ้ำของเดิม" (incremental จริง)
เป็นหน้าที่ของ Phase F ที่จะตามมา (ต้องเก็บ high-water-mark ของ event seq/day ที่เคย export ไปแล้ว)
"""
import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Dict


@dataclass
class DatasetMetadata:
    world_seed: int
    generated_at: str
    event_count: int
    character_count: int
    generator_version: str
    counts: Dict[str, int] = field(default_factory=dict)


def next_version_dir(base_dir: str) -> str:
    os.makedirs(base_dir, exist_ok=True)
    existing = [d for d in os.listdir(base_dir) if d.startswith("v") and d[1:].isdigit()]
    nums = [int(d[1:]) for d in existing] or [0]
    version_dir = os.path.join(base_dir, f"v{max(nums) + 1}")
    os.makedirs(version_dir, exist_ok=True)
    return version_dir


def make_metadata(world_seed: int, event_count: int, character_count: int,
                   counts: Dict[str, int], generator_version: str = "0.1.0") -> DatasetMetadata:
    return DatasetMetadata(
        world_seed=world_seed,
        generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        event_count=event_count, character_count=character_count,
        generator_version=generator_version, counts=counts,
    )


def write_metadata(version_dir: str, meta: DatasetMetadata) -> None:
    with open(os.path.join(version_dir, "metadata.json"), "w", encoding="utf-8") as f:
        json.dump(asdict(meta), f, ensure_ascii=False, indent=2)
