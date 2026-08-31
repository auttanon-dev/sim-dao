# -*- coding: utf-8 -*-
"""Phase H — Auto-Trainer trigger: ตรวจ datasets/export_state.json (Phase F) ว่าฉากใหม่สะสมครบโควต้า
หรือยัง แล้วค่อยสั่งเทรน LoRA — ไม่เทรนซ้ำข้อมูลเดิมที่เคยเทรนไปแล้ว (เก็บ high-water-mark ของตัวเอง
แยกจาก export_state.json คนละหน้าที่กัน — Phase F track "export ไปถึงไหน", ไฟล์นี้ track "เทรนไปถึงไหน")

    python autotrain.py --check                          # เช็คว่าสะสมครบโควต้าหรือยัง ไม่เทรนจริง
    python autotrain.py --threshold 500 --max-steps 20     # เทรนถ้าครบ 500 ฉากใหม่ (smoke test สั้นๆ)
    python autotrain.py --force --max-steps 5              # เทรนทันทีไม่สนโควต้า (ทดสอบ pipeline)
"""
import argparse
import json
import sys
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

TRAIN_STATE_FILENAME = "train_state.json"


def load_train_state(datasets_dir: Path) -> dict:
    p = datasets_dir / TRAIN_STATE_FILENAME
    if not p.exists():
        return {"last_trained_scene_count": 0, "history": []}
    return json.loads(p.read_text(encoding="utf-8"))


def save_train_state(datasets_dir: Path, state: dict) -> None:
    (datasets_dir / TRAIN_STATE_FILENAME).write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def accumulated_scene_count(export_state: dict) -> int:
    return sum(h["scene_count"] for h in export_state.get("history", []))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--datasets-dir", default="datasets")
    ap.add_argument("--loras-dir", default="loras")
    ap.add_argument("--threshold", type=int, default=2000,
                     help="จำนวนฉากสะสมใหม่ (ตั้งแต่เทรนครั้งล่าสุด) ที่ต้องครบก่อนเทรน (ตาม ROLE (2).MD)")
    ap.add_argument("--model", default="Qwen/Qwen2.5-7B-Instruct")
    ap.add_argument("--check", action="store_true", help="แค่เช็คว่าครบโควต้าหรือยัง ไม่เทรนจริง")
    ap.add_argument("--force", action="store_true", help="เทรนทันทีไม่สนโควต้า (ใช้ทดสอบ pipeline)")
    ap.add_argument("--max-steps", type=int, default=None, help="จำกัด step ต่อรอบ (สำหรับ smoke test)")
    ap.add_argument("--epochs", type=int, default=1)
    a = ap.parse_args()

    datasets_dir = Path(a.datasets_dir)
    export_state_path = datasets_dir / "export_state.json"
    if not export_state_path.exists():
        print(f"[autotrain] ไม่พบ {export_state_path} — รัน build_dataset.py ก่อน")
        return
    export_state = json.loads(export_state_path.read_text(encoding="utf-8"))
    total_scenes = accumulated_scene_count(export_state)

    train_state = load_train_state(datasets_dir)
    new_scenes = total_scenes - train_state["last_trained_scene_count"]

    print(f"[autotrain] ฉากสะสมทั้งหมด {total_scenes} | เทรนไปแล้วถึง "
          f"{train_state['last_trained_scene_count']} | ใหม่ {new_scenes} (เกณฑ์ {a.threshold})")

    if a.check:
        return
    if not a.force and new_scenes < a.threshold:
        print("[autotrain] ยังไม่ครบโควต้า ไม่เทรน")
        return

    versions = [h["version"] for h in export_state["history"]]
    if (datasets_dir / "lessons_v1").is_dir():
        # Phase K7 — lessons_v1/ ไม่ได้อยู่ใน export_state.json (คนละ versioning กับ Phase F ตั้งใจ
        # ดู lesson_exporter.py) เพิ่มเข้า version list ตรงๆ ถ้ามีอยู่จริง — load_dataset_dirs() ต่อ
        # path เป็น datasets_dir/{v} อยู่แล้วรองรับ pseudo-version นี้ได้โดยไม่ต้องแก้อะไรเพิ่ม
        versions = versions + ["lessons_v1"]
    from narrative_factory import dataset_formatter as FMT
    examples = FMT.load_dataset_dirs(datasets_dir, versions)
    print(f"[autotrain] โหลด {len(examples)} ตัวอย่างจาก {len(versions)} เวอร์ชัน ({versions})")
    if not examples:
        print("[autotrain] ไม่มีตัวอย่างให้เทรน (dataset ว่างเปล่า?)")
        return

    import train_lora
    version_n = len(train_state["history"]) + 1
    loras_dir = Path(a.loras_dir)
    loras_dir.mkdir(parents=True, exist_ok=True)
    output_dir = str(loras_dir / f"v{version_n}")

    print(f"[autotrain] เริ่มเทรน {a.model} -> {output_dir} "
          f"({'max_steps=' + str(a.max_steps) if a.max_steps else f'epochs={a.epochs}'})")
    train_lora.train(a.model, examples, output_dir, epochs=a.epochs, max_steps=a.max_steps)

    train_state["last_trained_scene_count"] = total_scenes
    train_state["history"].append({
        "lora_version": f"v{version_n}", "n_examples": len(examples),
        "model": a.model, "source_dataset_versions": versions,
    })
    save_train_state(datasets_dir, train_state)
    print(f"[autotrain] เทรนเสร็จ บันทึก LoRA ไว้ที่ {output_dir}")


if __name__ == "__main__":
    main()
