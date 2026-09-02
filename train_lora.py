# -*- coding: utf-8 -*-
"""Phase H — Self-Fine-Tuning Worker: เทรน LoRA (QLoRA 4-bit) จาก dataset ที่ narrative_factory export ไว้

**เลือกใช้ transformers + peft + bitsandbytes ตรงๆ แทน Unsloth ที่ ROLE (2).MD แนะนำ** — เครื่องนี้ใช้
torch nightly build (`2.12.0.dev...+cu128`) ซึ่ง Unsloth/TRL ยังไม่ประกาศรองรับอย่างเป็นทางการ (ไม่มี
ทั้งคู่ติดตั้งอยู่แล้วด้วย) ในขณะที่ transformers/peft/bitsandbytes/torch+CUDA ยืนยันแล้วว่าทำงานได้จริง
ในเครื่องนี้ — ได้ผลลัพธ์ QLoRA แบบเดียวกัน แค่ไม่ใช้ library ที่ยังไม่ผ่านการตรวจสอบความเข้ากันได้

    python train_lora.py --examples-file /tmp/examples.jsonl --output-dir loras/v1 --max-steps 20

โดยปกติไม่ได้เรียกตรงๆ — autotrain.py (Phase H trigger) เป็นตัวเรียกฟังก์ชัน train() ในนี้อีกที
"""
import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional

import torch


MIN_COMPLETION_TOKENS = 64  # กันที่ว่างขั้นต่ำไว้ให้ token คำตอบเสมอ (ดู docstring ChatDataset)
HELD_OUT_FILENAME = "held_out_scene_ids.json"


def _collect_scene_ids(examples: List[Dict]) -> List[str]:
    """เก็บ scene_id ทุกอันที่ปรากฏใน `_meta` ของชุด example ที่ให้มา (ข้อ 3 — held-out split)

    ครอบคลุมทั้ง `_meta.scene_id` เดี่ยว (scene_sft/dialogue/monologue/planning/story_lesson) และ
    `_meta.scene_ids` แบบ list (arc_lesson — หนึ่ง record อาจอ้างถึงหลายฉาก) — record ที่ไม่มี scene_id
    เลย (เช่น chronicle ที่สรุประดับโลก ไม่ใช่ฉากเดียว) ถูกข้ามไปเฉยๆ ไม่ error"""
    ids = set()
    for ex in examples:
        meta = ex.get("_meta")
        if not isinstance(meta, dict):
            continue
        sid = meta.get("scene_id")
        if sid:
            ids.add(sid)
        for sid in meta.get("scene_ids") or []:
            ids.add(sid)
    return sorted(ids)


class ChatDataset(torch.utils.data.Dataset):
    """เทรนเฉพาะส่วนคำตอบ (assistant) เท่านั้น — mask ส่วน system+user ด้วย label=-100 ไม่ให้เข้า loss

    **บั๊กจริงที่เจอและแก้ (สำคัญ)**: ถ้า prompt (system+user) เพียวๆ ยาวเกิน `max_length` อยู่แล้ว
    (เจอจริงกับ record ประเภท chronicle ที่มี event list ยาวมาก) การ truncate ทั้ง `full_text` และ
    `prompt_text` ด้วย `max_length` เดียวกันจะทำให้ label ทั้งก้อนโดน mask หมด (ไม่เหลือ token คำตอบ
    เลยสักตัว) → loss เป็น `NaN` ทันทีสำหรับ example นั้น — ยืนยันเจอจริงตอนเทรนจนลู่เข้าครั้งแรก:
    5/4,753 ใน training set + 1/250 ใน eval set ทำให้ `eval_loss` ท้าย epoch 1 เป็น `NaN` (poison
    ค่าเฉลี่ยทั้ง epoch เพราะ `per_device_eval_batch_size=1` แต่ละ batch มีแค่ 1 ตัวอย่าง) ซึ่งจะทำให้
    `load_best_model_at_end`/`EarlyStoppingCallback` ตัดสินใจผิดพลาดหรือพังได้ — แก้โดยกันที่ว่างขั้นต่ำ
    `MIN_COMPLETION_TOKENS` ไว้ให้คำตอบเสมอ (ตัด prompt ให้สั้นลงแทนถ้าจำเป็น ไม่ตัดคำตอบทิ้งทั้งหมด)"""

    def __init__(self, examples: List[Dict], tokenizer, max_length: int = 1024):
        self.examples = examples
        self.tokenizer = tokenizer
        self.max_length = max_length

    def __len__(self) -> int:
        return len(self.examples)

    def __getitem__(self, idx: int) -> Dict[str, torch.Tensor]:
        messages = self.examples[idx]["messages"]
        prompt_msgs = messages[:-1]   # system+user (ไม่รวมคำตอบ assistant)
        full_text = self.tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=False)
        prompt_text = self.tokenizer.apply_chat_template(prompt_msgs, tokenize=False, add_generation_prompt=True)

        prompt_max = max(1, self.max_length - MIN_COMPLETION_TOKENS)
        full = self.tokenizer(full_text, truncation=True, max_length=self.max_length, return_tensors="pt")
        prompt_ids = self.tokenizer(prompt_text, truncation=True, max_length=prompt_max)["input_ids"]

        input_ids = full["input_ids"][0]
        labels = input_ids.clone()
        mask_len = min(len(prompt_ids), len(input_ids))
        labels[:mask_len] = -100
        return {"input_ids": input_ids, "attention_mask": full["attention_mask"][0], "labels": labels}


def _collate(batch: List[Dict[str, torch.Tensor]], pad_id: int) -> Dict[str, torch.Tensor]:
    max_len = max(len(b["input_ids"]) for b in batch)
    input_ids, attn, labels = [], [], []
    for b in batch:
        pad = max_len - len(b["input_ids"])
        input_ids.append(torch.cat([b["input_ids"], torch.full((pad,), pad_id, dtype=torch.long)]))
        attn.append(torch.cat([b["attention_mask"], torch.zeros(pad, dtype=torch.long)]))
        labels.append(torch.cat([b["labels"], torch.full((pad,), -100, dtype=torch.long)]))
    return {"input_ids": torch.stack(input_ids), "attention_mask": torch.stack(attn),
            "labels": torch.stack(labels)}


def train(model_name: str, examples: List[Dict], output_dir: str, epochs: int = 1,
          batch_size: int = 1, grad_accum: int = 8, lr: float = 2e-4, max_length: int = 1024,
          max_steps: Optional[int] = None, eval_ratio: float = 0.05,
          early_stopping_patience: Optional[int] = 2) -> str:
    """เทรน QLoRA (4-bit) — คืน output_dir ที่บันทึก adapter ไว้

    **เทรนจนลู่เข้าจริง (ไม่ใช่ smoke test)**: กันตัวอย่างส่วนหนึ่ง (`eval_ratio`, สุ่มด้วย seed คงที่)
    ไว้เป็น held-out validation เพื่อดู `eval_loss` จริงทุกจบ epoch — ใช้ตัดสินว่าลู่เข้าจริงหรือเริ่ม
    overfit (แค่ดู train_loss ต่อ step อย่างเดียวจะ noisy เกินไปกับ dataset ที่หลากหลายหลาย task แบบนี้)
    เปิด `early_stopping_patience` (ดีฟอลต์ 2 epoch ไม่ดีขึ้นแล้วหยุด) คู่กับ
    `load_best_model_at_end=True` — คืน adapter ของ epoch ที่ eval_loss ต่ำสุดจริง ไม่ใช่ epoch สุดท้าย
    เสมอไป (ป้องกัน overfit เข้าโมเดลที่ deploy จริง) — ปิดได้ด้วย `early_stopping_patience=None`
    (เทรนครบ `epochs` เต็มไม่มีเงื่อนไขหยุดก่อน) หรือ `eval_ratio=0` (ปิด eval ทั้งหมด กลับไปพฤติกรรม
    เดิมแบบ Phase H)

    **บันทึก held-out split จริง (ข้อ 3)**: เดิม `evaluate_model.py` ไม่มีทางรู้เลยว่าฉากไหนถูกกันไว้
    เป็น validation ตอนเทรน (ต้อง reverse-engineer ด้วยสคริปต์ ad-hoc — เอา seed/shuffle เดียวกันมารัน
    ซ้ำ จับคู่กับ `_meta.scene_id` ของ raw record เอง — ทำตอนประเมิน `loras/v4` มาแล้วครั้งหนึ่ง) แก้โดย
    เขียน `{output_dir}/held_out_scene_ids.json` ไว้ตรงๆ ตอนเทรนจบ (scene_id ทุกอันที่ปรากฏใน
    `eval_examples` — ดู `_collect_scene_ids()`) ให้ `evaluate_model.py` โหลดมาใช้ต่อได้เลย ไม่ต้องรื้อ
    RNG state ทีหลังอีก

    **warmup**: transformers เวอร์ชันนี้ (5.15.0) ตัด `warmup_ratio` ออกแล้ว เหลือแค่ `warmup_steps`
    (ตรวจสอบจริงกับ `TrainingArguments.__dataclass_fields__`) เลยคำนวณ warmup_steps เองจาก 3% ของ
    total step แทน"""
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
    from transformers import (AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig,
                               EarlyStoppingCallback, Trainer, TrainingArguments)

    tokenizer = AutoTokenizer.from_pretrained(model_name)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True, bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16, bnb_4bit_use_double_quant=True,
    )
    model = AutoModelForCausalLM.from_pretrained(
        model_name, quantization_config=bnb_config, device_map="auto", torch_dtype=torch.bfloat16,
    )
    model = prepare_model_for_kbit_training(model)
    lora_config = LoraConfig(
        r=16, lora_alpha=32, lora_dropout=0.05, bias="none", task_type="CAUSAL_LM",
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
    )
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    import random as _random
    SPLIT_SEED = 20260830
    shuffled = list(examples)
    _random.Random(SPLIT_SEED).shuffle(shuffled)
    n_eval = max(1, int(len(shuffled) * eval_ratio)) if eval_ratio > 0 else 0
    eval_examples, train_examples = shuffled[:n_eval], shuffled[n_eval:]
    print(f"[train_lora] แบ่งข้อมูล: เทรน {len(train_examples)} / validation {len(eval_examples)} "
          f"(eval_ratio={eval_ratio})")

    held_out_scene_ids = _collect_scene_ids(eval_examples)

    train_dataset = ChatDataset(train_examples, tokenizer, max_length=max_length)
    eval_dataset = ChatDataset(eval_examples, tokenizer, max_length=max_length) if eval_examples else None

    steps_per_epoch = max(1, -(-len(train_dataset) // (batch_size * grad_accum)))  # ceil div
    total_steps = max_steps if max_steps else steps_per_epoch * epochs
    warmup_steps = max(1, int(total_steps * 0.03))
    print(f"[train_lora] steps_per_epoch={steps_per_epoch}, total_steps(ประมาณ)={total_steps}, "
          f"warmup_steps={warmup_steps}")

    use_eval = eval_dataset is not None
    args = TrainingArguments(
        output_dir=output_dir, per_device_train_batch_size=batch_size,
        per_device_eval_batch_size=batch_size,
        gradient_accumulation_steps=grad_accum, num_train_epochs=epochs,
        learning_rate=lr, warmup_steps=warmup_steps, lr_scheduler_type="cosine",
        logging_steps=10, report_to=[], bf16=True,
        max_steps=max_steps if max_steps else -1,
        eval_strategy="epoch" if use_eval else "no",
        save_strategy="epoch" if use_eval else "no",
        save_total_limit=3 if use_eval else None,
        load_best_model_at_end=use_eval,
        metric_for_best_model="eval_loss" if use_eval else None,
        greater_is_better=False if use_eval else None,
    )
    callbacks = []
    if use_eval and early_stopping_patience:
        callbacks.append(EarlyStoppingCallback(early_stopping_patience=early_stopping_patience))

    trainer = Trainer(
        model=model, args=args, train_dataset=train_dataset, eval_dataset=eval_dataset,
        data_collator=lambda batch: _collate(batch, tokenizer.pad_token_id),
        callbacks=callbacks or None,
    )
    trainer.train()

    if use_eval:
        final_eval = trainer.evaluate()
        print(f"[train_lora] eval_loss ของโมเดลที่ดีที่สุด (load_best_model_at_end): "
              f"{final_eval.get('eval_loss')}")

    model.save_pretrained(output_dir)
    tokenizer.save_pretrained(output_dir)

    held_out_path = Path(output_dir) / HELD_OUT_FILENAME
    held_out_path.write_text(json.dumps({
        "enabled": use_eval, "seed": SPLIT_SEED, "eval_ratio": eval_ratio,
        "n_eval_examples": len(eval_examples), "n_train_examples": len(train_examples),
        "scene_ids": held_out_scene_ids,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[train_lora] บันทึก held-out scene_id {len(held_out_scene_ids)} ฉากไว้ที่ {held_out_path} "
          f"(evaluate_model.py ใช้ประเมิน generalization จริงได้ต่อ)")

    return output_dir


def main() -> None:
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    ap = argparse.ArgumentParser()
    ap.add_argument("--examples-file", required=True, help="jsonl ของ {'messages': [...]} (ดู narrative_factory/dataset_formatter.py)")
    ap.add_argument("--model", default="scb10x/typhoon2.5-qwen3-4b")
    ap.add_argument("--output-dir", required=True)
    ap.add_argument("--epochs", type=int, default=1)
    ap.add_argument("--batch-size", type=int, default=1)
    ap.add_argument("--grad-accum", type=int, default=8)
    ap.add_argument("--lr", type=float, default=2e-4)
    ap.add_argument("--max-length", type=int, default=1024)
    ap.add_argument("--max-steps", type=int, default=None, help="จำกัดจำนวน step (สำหรับ smoke test)")
    ap.add_argument("--eval-ratio", type=float, default=0.05,
                     help="สัดส่วนกันไว้เป็น validation (0 = ปิด eval ทั้งหมด)")
    ap.add_argument("--early-stopping-patience", type=int, default=2,
                     help="หยุดถ้า eval_loss ไม่ดีขึ้นกี่ epoch ติดกัน (0/ไม่ใส่ค่า = ปิด ใส่ empty string เพื่อปิด)")
    a = ap.parse_args()

    examples = [json.loads(line) for line in Path(a.examples_file).read_text(encoding="utf-8").splitlines() if line.strip()]
    print(f"[train_lora] โหลด {len(examples)} ตัวอย่างจาก {a.examples_file}")
    patience = a.early_stopping_patience if a.early_stopping_patience > 0 else None
    out = train(a.model, examples, a.output_dir, epochs=a.epochs, batch_size=a.batch_size,
                grad_accum=a.grad_accum, lr=a.lr, max_length=a.max_length, max_steps=a.max_steps,
                eval_ratio=a.eval_ratio, early_stopping_patience=patience)
    print(f"[train_lora] เทรนเสร็จ บันทึก LoRA adapter ไว้ที่ {out}")


if __name__ == "__main__":
    main()
