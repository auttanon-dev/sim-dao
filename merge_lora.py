# -*- coding: utf-8 -*-
"""Phase J — Merge LoRA เข้า base model เต็มรูปแบบ: ขั้นตอนก่อนแปลง GGUF (`hotswap.py` เรียกไฟล์นี้)

**ทำไมต้องโหลดใหม่แบบ bf16 เต็ม ไม่ใช้ 4-bit เหมือนตอนเทรน**: `peft.merge_and_unload()` ต้องรวม
น้ำหนัก LoRA (BA*scale) เข้ากับน้ำหนักจริงของโมเดลตรงๆ — ถ้าฐานเป็น 4-bit (ค่าถูกบีบอัด/ดีควอนไทซ์
คร่าวๆ ตอนคำนวณ) ผลรวมจะไม่ตรงกับที่ควรเป็นจริง (ไม่ใช่การ merge น้ำหนักที่ถูกต้องสมบูรณ์) ต้องโหลด
ฐานแบบเต็มความละเอียด (bf16) แยกต่างหากจากตอนเทรน

**ทำไมโหลดบน CPU ไม่ใช่ GPU**: 7.65B พารามิเตอร์ x 2 ไบต์ (bf16) ≈ 15.3GB ซึ่งเบียดกับ VRAM ของ
RTX 5060 Ti (16311 MiB รวม, ว่างจริงไม่ถึงพอสำหรับทั้งน้ำหนักฐาน+overhead ของ merge) — merge เป็นแค่
การบวกเมทริกซ์ (ไม่ต้องเทรน ไม่ต้องมี gradient/activation buffer ขนาดใหญ่) ทำบน CPU ได้ปลอดภัยกว่า
แค่ช้ากว่า (นาทีไม่ใช่วินาที) ยอมรับได้ตามหลัก "ช้าได้แต่ต้องดีที่สุด"

    python merge_lora.py --adapter loras/v1 --output-dir merged/v1
"""
import argparse
import sys

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def merge(base_model_name: str, adapter_path: str, output_dir: str) -> str:
    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    print(f"[merge_lora] โหลด base model {base_model_name} แบบ bf16 เต็ม บน CPU (ใช้เวลาสักครู่)...")
    tokenizer = AutoTokenizer.from_pretrained(base_model_name)
    model = AutoModelForCausalLM.from_pretrained(base_model_name, torch_dtype=torch.bfloat16,
                                                  device_map="cpu")

    print(f"[merge_lora] ติด adapter จาก {adapter_path} แล้ว merge เข้าน้ำหนักจริง...")
    model = PeftModel.from_pretrained(model, adapter_path)
    model = model.merge_and_unload()

    print(f"[merge_lora] บันทึกโมเดลที่ merge แล้วไปที่ {output_dir} (safetensors, ~15GB)...")
    model.save_pretrained(output_dir, safe_serialization=True)
    tokenizer.save_pretrained(output_dir)
    return output_dir


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-model", default="Qwen/Qwen2.5-7B-Instruct")
    ap.add_argument("--adapter", required=True, help="เช่น loras/v1")
    ap.add_argument("--output-dir", required=True, help="เช่น merged/v1")
    a = ap.parse_args()

    out = merge(a.base_model, a.adapter, a.output_dir)
    print(f"[merge_lora] เสร็จ — merged model เต็มอยู่ที่ {out}")


if __name__ == "__main__":
    main()
