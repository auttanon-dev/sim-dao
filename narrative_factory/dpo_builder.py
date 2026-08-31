# -*- coding: utf-8 -*-
"""Phase I — DPO Pair Builder: แปลงผลตรวจ Phase D (Pass/Fail) เป็นคู่ (prompt, chosen, rejected)
สำหรับเทรนด้วย DPO/RLAIF ต่อไป (ตาม `ROLE (2).MD` Pillar 2 — "เรียนรู้จากความผิดพลาดของตัวเอง")

**Chosen** = candidate ที่ผ่าน Phase D Validator (`narrative_factory/validator.py`) 100% และคะแนน >=
`dpo_chosen_threshold` (ค่าคงที่ใหม่ใน `config.yaml`, ดีฟอลต์ 85 — แยกต่างหากจาก
`scoring.PASS_THRESHOLD = 80` ที่ใช้ตัดสิน Dataset A-E ปกติ ตามที่ตรวจสอบไว้ใน `ROLE (2).MD` ว่าห้าม
แก้ค่าเดิมตรงๆ เพราะกระทบ export ที่ใช้งานอยู่ทุกวันนี้)

**Rejected** = candidate ที่ Phase D ปฏิเสธจริง (ละเมิดกฎข้อใดข้อหนึ่งใน 6 ข้อ) — มาจาก
`rejected_candidates.jsonl` ที่ `exporter.py` เขียนไว้ (เพิ่มเป็นส่วนหนึ่งของ Phase I นี้เอง ตามช่องว่าง
ที่ระบุไว้ใน `ROLE (2).MD` ก่อนเริ่ม — เดิม `_validated_or_fallback()` ทิ้ง candidate ที่ reject ไปเฉยๆ)

**ข้อจำกัดสำคัญที่ต้องรู้ก่อนใช้**: หนึ่งฉากได้ candidate จาก LLM แค่ตัวเดียวต่อการ export หนึ่งครั้ง
(`exporter.py` เรียก `agent.complete()` ครั้งเดียว ไม่ sample ซ้ำ) คู่ Chosen/Rejected ของ "scene_id
เดียวกัน" จะเกิดขึ้นได้จริงก็ต่อเมื่อมีการ export ด้วย `--llm --full` มากกว่าหนึ่งครั้ง (Ollama เป็น
stochastic ตอบไม่เหมือนเดิมทุกครั้ง แม้ scene/prompt เดียวกัน) — ตัว builder นี้จึงสแกน**ทุกเวอร์ชัน**ใน
`datasets/` (v1, v2, ...) สะสม chosen/rejected ต่อ scene_id ข้ามเวอร์ชัน แล้วจับคู่เฉพาะ scene_id ที่มี
ทั้งสองฝั่งจริงเท่านั้น — ไม่ปั้นคู่ปลอมขึ้นมาโดยเทียบ chosen ของฉากหนึ่งกับ rejected ของอีกฉากที่ไม่
เกี่ยวข้องกัน

ถ้าไม่เคยรัน `--llm --full` ซ้ำมากกว่าหนึ่งครั้ง (หรือไม่มี scene ไหนถูกทั้ง accept-คะแนนสูงและ reject
ในคนละรอบ) ผลลัพธ์จะเป็นไฟล์ `dpo_pairs.jsonl` ว่างเปล่า — ถูกต้องแล้ว ไม่ใช่ error (หลักการเดียวกับ
Dataset B/C ที่ว่างเปล่าถ้าไม่เคยรันซิมด้วย --llm)
"""
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .parser import load_config


@dataclass
class Candidate:
    text: str
    score: Optional[int]
    prompt: str
    version: str
    violations: Optional[List[str]] = None


def _prompt_repr(instruction: str, input_payload: dict) -> str:
    """สร้าง prompt เดียวกันเป๊ะจากทั้งฝั่ง chosen/rejected — มาจาก `input` เดียวกันของ `exporter.py`
    เสมอเพราะเป็น scene เดียวกัน ใช้เทียบยืนยันว่าไม่ได้จับคู่ scene ที่เปลี่ยน input ไประหว่างเวอร์ชัน"""
    participants = ", ".join(input_payload.get("participants") or [])
    events = "\n".join(f"- {e}" for e in input_payload.get("events") or [])
    return (f"{instruction}\n[สถานที่] {input_payload.get('location') or 'ไม่ทราบ'}\n"
            f"[ผู้เกี่ยวข้อง] {participants}\n[เหตุการณ์]\n{events}")


def _iter_version_dirs(datasets_dir: Path) -> List[Path]:
    if not datasets_dir.exists():
        return []
    dirs = [p for p in datasets_dir.iterdir() if p.is_dir() and p.name.startswith("v") and p.name[1:].isdigit()]
    return sorted(dirs, key=lambda p: int(p.name[1:]))


def _read_jsonl(path: Path):
    if not path.exists():
        return
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def collect_candidates(datasets_dir: Path, chosen_threshold: int
                        ) -> Tuple[Dict[int, List[Candidate]], Dict[int, List[Candidate]]]:
    """สแกนทุกเวอร์ชันใน datasets_dir คืน (chosen_by_scene, rejected_by_scene)"""
    chosen: Dict[int, List[Candidate]] = {}
    rejected: Dict[int, List[Candidate]] = {}

    for version_dir in _iter_version_dirs(datasets_dir):
        for rec in _read_jsonl(version_dir / "scene_sft.jsonl"):
            meta = rec.get("_meta", {})
            score = meta.get("score")
            if not meta.get("used_llm") or score is None or score < chosen_threshold:
                continue
            scene_id = meta["scene_id"]
            chosen.setdefault(scene_id, []).append(Candidate(
                text=rec["output"], score=score,
                prompt=_prompt_repr(rec["instruction"], rec["input"]), version=version_dir.name,
            ))

        for rec in _read_jsonl(version_dir / "rejected_candidates.jsonl"):
            scene_id = rec["_meta"]["scene_id"]
            rejected.setdefault(scene_id, []).append(Candidate(
                text=rec["rejected_output"], score=rec.get("score"),
                prompt=_prompt_repr(rec["instruction"], rec["input"]), version=version_dir.name,
                violations=rec.get("violations"),
            ))

    return chosen, rejected


def build_pairs(chosen_by_scene: Dict[int, List[Candidate]],
                 rejected_by_scene: Dict[int, List[Candidate]]) -> List[dict]:
    """จับคู่เฉพาะ scene_id ที่มีทั้ง chosen และ rejected จริง — คู่ละหนึ่งต่อฉาก (chosen คะแนนสูงสุด,
    rejected คะแนนต่ำสุด) ไม่จับคู่ไขว้ทุกคู่ที่เป็นไปได้ ป้องกัน near-duplicate pair ท่วม dataset"""
    pairs = []
    for scene_id in sorted(set(chosen_by_scene) & set(rejected_by_scene)):
        best_chosen = max(chosen_by_scene[scene_id], key=lambda c: c.score)
        worst_rejected = min(rejected_by_scene[scene_id],
                              key=lambda c: c.score if c.score is not None else -1)
        if best_chosen.prompt != worst_rejected.prompt:
            continue  # scene เปลี่ยน input ไประหว่างเวอร์ชัน (ไม่ควรเกิด) — ข้ามแทนจับคู่ผิด prompt
        pairs.append({
            "prompt": best_chosen.prompt,
            "chosen": best_chosen.text,
            "rejected": worst_rejected.text,
            "_meta": {
                "scene_id": scene_id,
                "chosen_score": best_chosen.score, "chosen_version": best_chosen.version,
                "rejected_score": worst_rejected.score, "rejected_version": worst_rejected.version,
                "rejected_violations": worst_rejected.violations,
            },
        })
    return pairs


def write_pairs(datasets_dir: Path, pairs: List[dict]) -> Path:
    out_path = datasets_dir / "dpo_pairs.jsonl"
    with open(out_path, "w", encoding="utf-8") as f:
        for p in pairs:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")
    return out_path


def run(datasets_dir: str = "datasets", chosen_threshold: Optional[int] = None) -> List[dict]:
    """เอนทรีพอยต์หลัก — ไม่เรียก Ollama เลย (แค่ประกอบข้อมูลที่ export ไว้แล้ว) รันซ้ำได้ตลอดเวลา
    (overwrite dpo_pairs.jsonl ทุกครั้ง ไม่ใช่ incremental แบบ Phase F เพราะข้อมูลตั้งต้นน้อยกว่ามาก)"""
    cfg = load_config()
    threshold = chosen_threshold if chosen_threshold is not None else cfg.get("dpo_chosen_threshold", 85)
    d = Path(datasets_dir)
    chosen, rejected = collect_candidates(d, threshold)
    pairs = build_pairs(chosen, rejected)
    write_pairs(d, pairs)
    return pairs
