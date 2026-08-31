# -*- coding: utf-8 -*-
"""Phase J — Shadow Evaluation Gate: ให้คะแนน LoRA ที่เพิ่งเทรนเทียบกับ baseline (โมเดลฐานเปล่า หรือ
LoRA เวอร์ชันที่ deploy อยู่ก่อนหน้า) ผ่าน Phase D Validator/Scoring ตัวจริง (`validator.py`/
`scoring.py`) ก่อนอนุมัติให้ hot-swap เข้า Ollama จริง (ตาม `ROLE (2).MD` — "Shadow Evaluation Gate")

**ใช้ prompt เดียวกับตอนเทรนเป๊ะ**: `dataset_formatter.build_scene_messages()` ตัวเดียวกับที่แปลง
Dataset A เป็น ChatML ตอน Phase H — ไม่ใช้ prompt ที่ `exporter.py` ใช้ตอนสร้าง candidate ตั้งต้น
(prompt คนละรูปแบบกัน) เพื่อให้ผลประเมินสะท้อนพฤติกรรมจริงตอน inference

**ข้อจำกัดเดิม — แก้แล้ว (ข้อ 3)**: `narrative_factory/exporter.py`/`build_dataset.py` (Phase F) ยัง
export ทุกฉากที่ผ่านเกณฑ์เข้า dataset หมดเหมือนเดิม ไม่ได้กันฉากไว้เทสตั้งแต่ export — แต่ตอนนี้
`train_lora.py` เขียน `{lora_dir}/held_out_scene_ids.json` ไว้ทุกครั้งที่เทรน (scene_id ทุกอันที่ตกอยู่
ในฝั่ง validation split ของ`eval_ratio`) ให้ `evaluate_model.py` โหลดมาใช้กรอง `scenes` อัตโนมัติก่อน
เรียก `run_eval()` ในนี้ — ฟังก์ชันด้านล่างเองไม่รู้เรื่อง held-out (รับแค่ `scenes` ที่ caller กรองมา
แล้ว) ก็ยังทำงานถูกต้อง ไม่ต้องแก้อะไรในไฟล์นี้ ผลคือถ้า `evaluate_model.py` เจอไฟล์ split จริง ฉากที่
ประเมินจะเป็นฉากที่โมเดลไม่เคยเห็นตอนเทรนแน่นอน ไม่ใช่ความเอนเอียงเชิงบวกที่ปนกับ "จำได้" อีกต่อไป — LoRA
เก่าที่เทรนก่อนมีกลไกนี้ (v1-v4) ไม่มีไฟล์นี้ ยังต้องระวังแบบเดิม
"""
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class SceneScore:
    scene_id: str
    score: int
    passed: bool
    violations: List[str] = field(default_factory=list)
    output_preview: str = ""


@dataclass
class EvalResult:
    label: str
    n: int
    mean_score: float
    pass_rate: float
    per_scene: List[SceneScore] = field(default_factory=list)


def load_model_for_eval(base_model_name: str, adapter_path: Optional[str] = None,
                         four_bit: bool = True):
    """โหลดโมเดลสำหรับ **ประเมิน** เท่านั้น (ไม่ใช่สำหรับ merge/deploy) — ดีฟอลต์โหลดแบบ 4-bit เหมือน
    ตอนเทรน (Phase H) เพื่อประหยัด VRAM/เวลา ไม่ต้องแม่นยำระดับ merge เพราะแค่ประเมินคุณภาพ output"""
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(base_model_name)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    kwargs = {"torch_dtype": torch.bfloat16, "device_map": "auto"}
    if four_bit:
        from transformers import BitsAndBytesConfig
        kwargs["quantization_config"] = BitsAndBytesConfig(
            load_in_4bit=True, bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.bfloat16, bnb_4bit_use_double_quant=True,
        )
    model = AutoModelForCausalLM.from_pretrained(base_model_name, **kwargs)

    if adapter_path:
        from peft import PeftModel
        model = PeftModel.from_pretrained(model, adapter_path)

    model.eval()
    return model, tokenizer


def unload_model(model) -> None:
    """คืน VRAM ก่อนโหลดโมเดลตัวถัดไป — จำเป็นเพราะ baseline/candidate โหลดทีละตัวไม่พร้อมกัน
    (GPU เครื่องนี้ VRAM ไม่พอโหลด 7B สองตัวพร้อมกันแบบ full/bf16)"""
    import gc

    import torch
    del model
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


def _scene_input_payload(scene, sim):
    """delegate ไป exporter.py:build_scene_input_payload() ตรงๆ (ไม่ duplicate logic) — ต้องเป็น
    prompt shape เดียวกับตอนเทรนเป๊ะ ไม่งั้น Shadow Evaluation Gate จะวัดโมเดลด้วยโจทย์คนละแบบกับที่
    เทรนมา"""
    from . import exporter as EX
    return EX.build_scene_input_payload(scene, sim)


def generate_for_scenes(model, tokenizer, scenes: List, sim, config: dict,
                         max_new_tokens: int = 300, temperature: float = 0.7) -> Dict[str, str]:
    """สร้างข้อความจริงจากโมเดลที่โหลดไว้ ต่อฉากที่ให้มา — ใช้ chat template + prompt เดียวกับตอนเทรน"""
    import torch

    from .dataset_formatter import build_scene_messages

    outputs: Dict[str, str] = {}
    for scene in scenes:
        scene_type_th = config.get("scene_type_th", {}).get(
            scene.scene_type, config.get("default_scene_type_th", "ฉาก"))
        instruction = f"เขียน{scene_type_th}"
        input_payload = _scene_input_payload(scene, sim)
        messages = build_scene_messages(instruction, input_payload)
        prompt_text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = tokenizer(prompt_text, return_tensors="pt").to(model.device)
        with torch.no_grad():
            out_ids = model.generate(
                **inputs, max_new_tokens=max_new_tokens, do_sample=True,
                temperature=temperature, top_p=0.9,
                pad_token_id=tokenizer.pad_token_id or tokenizer.eos_token_id,
            )
        text = tokenizer.decode(out_ids[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True)
        outputs[scene.scene_id] = text.strip()
        logger.info("shadow_eval: generated scene %s (%d chars)", scene.scene_id, len(text))
    return outputs


def score_outputs(outputs: Dict[str, str], scenes_by_id: Dict[str, object], sim,
                   by_cid: Dict, config: dict, label: str = "") -> EvalResult:
    """ให้คะแนนผ่าน Phase D Validator/Scoring ตัวจริง (ตัวเดียวกับที่ exporter.py/Phase I ใช้)"""
    from . import scoring as SC
    from . import validator as V
    from .context_builder import build_scene_context

    per_scene: List[SceneScore] = []
    for scene_id, text in outputs.items():
        scene = scenes_by_id[scene_id]
        char_log = by_cid.get(scene.focal_cid, [])
        ctx_map = build_scene_context(scene, sim, by_cid, config)
        result = V.validate_candidate(text, scene, ctx_map, sim, char_log)
        score = SC.score_candidate(text, result, scene=scene)
        per_scene.append(SceneScore(
            scene_id=scene_id, score=score.total, passed=score.passed,
            violations=[f"{v.rule}: {v.detail}" for v in result.violations],
            output_preview=text[:120],
        ))

    n = len(per_scene)
    mean_score = sum(p.score for p in per_scene) / n if n else 0.0
    pass_rate = sum(1 for p in per_scene if p.passed) / n if n else 0.0
    return EvalResult(label=label, n=n, mean_score=mean_score, pass_rate=pass_rate, per_scene=per_scene)


def run_eval(base_model_name: str, scenes: List, sim, by_cid: Dict, config: dict,
             adapter_path: Optional[str] = None, label: str = "", max_new_tokens: int = 300,
             four_bit: bool = True) -> EvalResult:
    """เอนทรีพอยต์รวม: โหลดโมเดล (+adapter ถ้ามี) -> generate -> score -> unload คืน VRAM"""
    model, tokenizer = load_model_for_eval(base_model_name, adapter_path, four_bit=four_bit)
    try:
        scenes_by_id = {s.scene_id: s for s in scenes}
        outputs = generate_for_scenes(model, tokenizer, scenes, sim, config, max_new_tokens=max_new_tokens)
        return score_outputs(outputs, scenes_by_id, sim, by_cid, config, label=label)
    finally:
        unload_model(model)
