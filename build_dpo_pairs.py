# -*- coding: utf-8 -*-
"""Phase I — DPO Pair Builder CLI: อ่าน datasets/v*/ ที่ `build_dataset.py` export ไว้แล้ว จับคู่
Chosen/Rejected ที่ scene_id ตรงกันจริง เขียนรวมเป็น datasets/dpo_pairs.jsonl

ไม่เรียก Ollama เอง (แค่ประกอบข้อมูลที่มีอยู่แล้วจากการ export ที่ผ่านมา) เร็วมาก รันซ้ำได้ตลอดเวลา —
ต้องมี `rejected_candidates.jsonl` และ `scene_sft.jsonl` ที่มี candidate คะแนนสูง (>= dpo_chosen_threshold)
ของ scene_id เดียวกันจากคนละเวอร์ชัน ถึงจะได้คู่จริง (ดู docstring `narrative_factory/dpo_builder.py`)

    python build_dataset.py --llm --llm-limit 20 --full   # export รอบแรก มีทั้ง chosen/rejected ปนกัน
    python build_dataset.py --llm --llm-limit 20 --full   # export รอบสอง (Ollama สุ่มคำตอบใหม่ต่อฉากเดิม)
    python build_dpo_pairs.py                              # จับคู่ scene_id ที่มีทั้งสองฝั่งจริง
"""
import argparse
import sys

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from narrative_factory import dpo_builder as DPO


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--datasets-dir", default="datasets")
    ap.add_argument("--threshold", type=int, default=None,
                     help="เกณฑ์คะแนนขั้นต่ำของฝั่ง chosen (ดีฟอลต์ dpo_chosen_threshold ใน config.yaml)")
    a = ap.parse_args()

    pairs = DPO.run(a.datasets_dir, chosen_threshold=a.threshold)
    print(f"[build_dpo_pairs] จับคู่ Chosen/Rejected ได้ {len(pairs)} คู่ -> "
          f"{a.datasets_dir}/dpo_pairs.jsonl")
    if not pairs:
        print("[build_dpo_pairs] ว่างเปล่า — ต้อง `build_dataset.py --llm --full` มากกว่า 1 ครั้ง "
              "ให้ scene_id เดียวกันครั้งหนึ่งผ่าน Phase D (คะแนนสูง) อีกครั้งไม่ผ่านจริง")


if __name__ == "__main__":
    main()
