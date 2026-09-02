# -*- coding: utf-8 -*-
"""Phase J — Model Evaluator & Hot-Swap CLI: ต่อจาก `evaluate_model.py` อนุมัติแล้ว — merge LoRA เข้า
base model เต็ม -> แปลง GGUF จริง (`vendor_llama_cpp_convert/convert_hf_to_gguf.py` — vendor มาจาก
https://github.com/ggml-org/llama.cpp เพราะ Ollama เวอร์ชันนี้ (0.33.2) รองรับ native safetensors
FROM/ADAPTER แค่ Llama/Mistral/Gemma/Phi3 **ไม่รวม Qwen2** ที่โปรเจกต์นี้ใช้จริงตาม ROLE.md) ->
`ollama create`/`ollama cp` จริงเข้า `cultivator-brain:latest`

**ต้องผ่าน Shadow Evaluation Gate ก่อนเสมอ** (ตาม `ROLE (2).MD`) — ต้องมี `--eval-result` ชี้ไปที่ผล
JSON จาก `evaluate_model.py` ที่ `approved: true` เท่านั้น ถึงจะ deploy ได้ (ข้ามได้ด้วย `--force`
แต่ log ไว้ชัดเจนว่าข้าม gate)

    python evaluate_model.py --candidate-lora loras/v1 --n-scenes 15
    python hotswap.py --adapter loras/v1 --version v1 --eval-result datasets/eval_results/eval_xxx.json
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

REPO_ROOT = Path(__file__).parent
CONVERT_SCRIPT = REPO_ROOT / "vendor_llama_cpp_convert" / "convert_hf_to_gguf.py"
MODEL_FAMILY_NAME = "cultivator-brain"


def _check_eval_gate(eval_result_path: str, force: bool) -> None:
    if force:
        print("[hotswap] --force: ข้าม Shadow Evaluation Gate ตามที่สั่ง (ไม่แนะนำนอกจากทดสอบ pipeline)")
        return
    if not eval_result_path:
        print("[hotswap] ต้องระบุ --eval-result (ผลจาก evaluate_model.py) หรือ --force เพื่อข้าม gate "
              "โดยตั้งใจ — ปฏิเสธการ deploy")
        sys.exit(1)
    data = json.loads(Path(eval_result_path).read_text(encoding="utf-8"))
    if not data.get("approved"):
        print(f"[hotswap] {eval_result_path} บอกว่า approved=False — Shadow Evaluation Gate ไม่อนุมัติ "
              "ปฏิเสธการ deploy (ใช้ --force ถ้าต้องการข้ามโดยตั้งใจ)")
        sys.exit(1)
    print(f"[hotswap] Shadow Evaluation Gate อนุมัติแล้ว (จาก {eval_result_path}) — ไปต่อ")


def _run(cmd, **kwargs):
    print(f"[hotswap] $ {' '.join(str(c) for c in cmd)}")
    subprocess.run(cmd, check=True, **kwargs)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-model", default="scb10x/typhoon2.5-qwen3-4b")
    ap.add_argument("--adapter", required=True, help="เช่น loras/v1")
    ap.add_argument("--version", required=True, help="ชื่อเวอร์ชันโมเดล เช่น v1 -> cultivator-brain:v1")
    ap.add_argument("--eval-result", default=None, help="path ผล JSON จาก evaluate_model.py")
    ap.add_argument("--force", action="store_true", help="ข้าม Shadow Evaluation Gate (ไม่แนะนำ)")
    ap.add_argument("--merged-dir", default=None, help="ดีฟอลต์ merged/{version}")
    ap.add_argument("--gguf-outtype", default="bf16", choices=["f32", "f16", "bf16"])
    ap.add_argument("--quantize", default="q4_K_M", help="ระดับบีบอัดตอน ollama create (-q)")
    ap.add_argument("--skip-merge", action="store_true",
                     help="ข้าม merge_lora.py ถ้า merged-dir มีโมเดลอยู่แล้วจากรอบก่อน")
    ap.add_argument("--skip-convert", action="store_true",
                     help="ข้ามแปลง GGUF ถ้ามีไฟล์ .gguf อยู่แล้ว")
    ap.add_argument("--no-latest", action="store_true",
                     help="สร้าง cultivator-brain:{version} แต่ไม่ ollama cp ทับ :latest — ใช้ตอน "
                          "ทดสอบท่อ merge->GGUF->ollama create เฉยๆ (เช่นกับโมเดลที่ --force ข้าม gate "
                          "มา ไม่ควรให้กลายเป็นตัวที่ระบบใช้งานจริง)")
    a = ap.parse_args()

    _check_eval_gate(a.eval_result, a.force)

    merged_dir = Path(a.merged_dir or f"merged/{a.version}")
    gguf_path = merged_dir.parent / f"{MODEL_FAMILY_NAME}-{a.version}-{a.gguf_outtype}.gguf"

    if a.skip_merge and merged_dir.exists():
        print(f"[hotswap] --skip-merge: ใช้ merged model เดิมที่ {merged_dir}")
    else:
        import merge_lora
        merge_lora.merge(a.base_model, a.adapter, str(merged_dir))

    if a.skip_convert and gguf_path.exists():
        print(f"[hotswap] --skip-convert: ใช้ GGUF เดิมที่ {gguf_path}")
    else:
        if not CONVERT_SCRIPT.exists():
            print(f"[hotswap] ไม่พบ {CONVERT_SCRIPT} — vendor เครื่องมือ llama.cpp ก่อน "
                  "(ดู CULTIVATOR_BRAIN_STATUS.md ส่วน Phase J)")
            sys.exit(1)
        _run([sys.executable, str(CONVERT_SCRIPT), str(merged_dir),
              "--outfile", str(gguf_path), "--outtype", a.gguf_outtype])

    modelfile_path = merged_dir.parent / f"Modelfile.{a.version}"
    modelfile_path.write_text(f"FROM {gguf_path.resolve()}\n", encoding="utf-8")
    print(f"[hotswap] เขียน {modelfile_path}")

    model_tag = f"{MODEL_FAMILY_NAME}:{a.version}"
    _run(["ollama", "create", model_tag, "-f", str(modelfile_path), "-q", a.quantize])

    if a.no_latest:
        print(f"[hotswap] === เสร็จ (--no-latest) === {model_tag} สร้างแล้วใน Ollama แต่ไม่ได้ตั้งเป็น "
              f"{MODEL_FAMILY_NAME}:latest — ทดสอบด้วย: ollama run {model_tag}")
    else:
        _run(["ollama", "cp", model_tag, f"{MODEL_FAMILY_NAME}:latest"])
        print(f"[hotswap] === เสร็จ === {model_tag} และ {MODEL_FAMILY_NAME}:latest พร้อมใช้งานใน Ollama แล้ว")
        print(f"[hotswap] ทดสอบเรียกจริง: ollama run {MODEL_FAMILY_NAME}:latest")
        print("[hotswap] ให้ Cultivator Brain v2 ใช้โมเดลนี้จริง: แก้ tiandao/ai/config_ai.py "
              f'OLLAMA_MODEL = "{MODEL_FAMILY_NAME}:latest" (หรือ generate_episode.py --model '
              f"{MODEL_FAMILY_NAME}:latest ต่อครั้งไป) — ดูคำเตือนเรื่อง Dataset B/C ว่างใน "
              "CULTIVATOR_BRAIN_STATUS.md ก่อนเปลี่ยนดีฟอลต์ที่ใช้ตอนรันซิมสด")


if __name__ == "__main__":
    main()
