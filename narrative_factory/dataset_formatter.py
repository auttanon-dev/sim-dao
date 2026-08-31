# -*- coding: utf-8 -*-
"""Phase H — Dataset Formatter: แปลง Dataset A-E (.jsonl จาก exporter.py) เป็น ChatML messages

รวมทั้ง 5 dataset เป็นรูปแบบเดียว (Multi-Task Training ตาม ROLE (2).MD Pillar 1) — ทุก record กลาย
เป็น `{"messages": [{"role": "system"/"user"/"assistant", "content": ...}]}` ส่งให้
`tokenizer.apply_chat_template()` ได้ตรงๆ (Qwen/ChatML รองรับ format นี้เป็นมาตรฐานอยู่แล้ว)

**ข้อจำกัดที่ต้องรู้ (ตรวจสอบจริงแล้วจาก CULTIVATOR_BRAIN_STATUS.md)**: Dataset B (Dialogue) และ
C (Monologue) จะว่างเปล่าถ้าไม่เคยรันซิมด้วย `--llm` — ฟังก์ชันด้านล่างแค่ไม่ผลิตตัวอย่างจากไฟล์ที่
ไม่มี/ว่าง ไม่ error — Multi-Task Training จะกลายเป็น "Task A+D+E เท่านั้น" โดยอัตโนมัติจนกว่าจะมี B/C

**Phase K7 (Narrative Teacher & Style Distillation)**: เพิ่ม `story_lesson.jsonl`/`arc_lesson.jsonl`/
`style_lesson.jsonl` จาก `lesson_exporter.py` (`datasets/lessons_v1/`) — ไฟล์เหล่านี้ export มาเป็น
ChatML อยู่แล้ว ใช้แค่ `_fmt_passthrough()` ไม่แปลงซ้ำ (คนละแบบกับ Dataset A-E ที่เก็บ field ดิบแล้ว
มาแปลงตรงนี้ทีเดียว) `autotrain.py` เพิ่ม `lessons_v1` เข้า version list เองถ้าโฟลเดอร์นี้มีอยู่จริง

**เก็บ `_meta` ไว้ทุก formatter (ข้อ 3 — held-out split)**: raw record ทุกไฟล์มี `_meta` (อย่างน้อย
`scene_id` สำหรับ scene_sft/dialogue/monologue/planning/story_lesson, `scene_ids` สำหรับ arc_lesson)
อยู่แล้วจาก `exporter.py`/`lesson_exporter.py` แต่ของเดิมทุก `_fmt_*` ทิ้งไปตอนแปลงเป็น
`{"messages": [...]}` — ทำให้ `train_lora.py` ไม่มีทางรู้เลยว่า record ไหนในชุดที่กันไว้เป็น held-out
validation คือฉากไหนบ้าง (ต้องเขียนสคริปต์ ad-hoc reverse-engineer ทีหลังแทน — ดู
CULTIVATOR_BRAIN_STATUS.md ข้อ 3 เดิม) แก้โดยให้ทุก formatter คืน `_meta` ต่อจาก raw record ไปด้วย"""
import json
from pathlib import Path
from typing import Dict, Iterator, List, Optional

SYSTEM_SCENE = "คุณคือนักเขียนนิยายกำลังภายในสไตล์จีน เขียนตามเหตุการณ์จริงที่ให้มาเท่านั้น ห้ามแต่งเติม"
SYSTEM_CHRONICLE = "คุณคือนักบันทึกพงศาวดารของโลกกำลังภายใน สรุปเหตุการณ์ระดับโลกให้กระชับ"
SYSTEM_PLANNER = "คุณคือนักวางแผนของนักบำเพ็ญเต๋า วางแผนขั้นตอนให้บรรลุเป้าหมายจากสถานะปัจจุบัน"


def build_scene_messages(instruction: str, input_payload: Dict) -> List[Dict]:
    """สร้าง [system, user] ของงาน Dataset A/Scene SFT ตัวเดียวที่ใช้ทั้งตอนเทรน (`_fmt_scene_sft`)
    และตอน Shadow Evaluation Gate (Phase J — `narrative_factory/shadow_eval.py`) เพื่อให้ prompt ที่
    ประเมินตรงกับ prompt ที่โมเดลเรียนรู้จริงเป๊ะ ไม่ใช้ prompt คนละแบบระหว่างเทรน/ประเมิน"""
    participants = ", ".join(input_payload.get("participants") or [])
    events = "\n".join(f"- {e}" for e in input_payload.get("events") or [])
    user = (f"{instruction}\n[สถานที่] {input_payload.get('location') or 'ไม่ทราบ'}\n"
            f"[ผู้เกี่ยวข้อง] {participants}\n[เหตุการณ์]\n{events}")
    return [{"role": "system", "content": SYSTEM_SCENE}, {"role": "user", "content": user}]


def _fmt_scene_sft(rec: Dict) -> Dict:
    messages = build_scene_messages(rec["instruction"], rec["input"])
    messages.append({"role": "assistant", "content": rec["output"]})
    return {"messages": messages, "_meta": rec.get("_meta")}


def _fmt_dialogue(rec: Dict) -> Dict:
    system = (f"คุณคือ {rec['speaker']} ตัวละครในนิยายกำลังภายใน "
              f"นิสัย: {', '.join(rec.get('traits') or [])} อารมณ์ปัจจุบัน: {rec.get('emotion', '')}")
    history = "\n".join(f"- {h}" for h in rec.get("history") or []) or "- ยังไม่มีความทรงจำ"
    event = rec.get("event") or "(ไม่ทราบ)"
    user = f"[เหตุการณ์ที่เพิ่งเกิด] {event}\nความทรงจำล่าสุด:\n{history}\nจงพูดสิ่งที่อยู่ในใจตอนนี้"
    return {"messages": [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
        {"role": "assistant", "content": rec["response"]},
    ], "_meta": rec.get("_meta")}


def _fmt_monologue(rec: Dict) -> Dict:
    system = f"คุณคือ {rec['character']} กำลังคิดอยู่ในใจ เป้าหมายตอนนี้: {rec.get('goal', '')}"
    memory = "\n".join(f"- {m}" for m in rec.get("memory") or []) or "- ยังไม่มีความทรงจำ"
    event = rec.get("event") or "(ไม่ทราบ)"
    user = f"[เหตุการณ์ที่เพิ่งเกิด] {event}\nความทรงจำ:\n{memory}\nคุณคิดอะไรอยู่ตอนนี้?"
    return {"messages": [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
        {"role": "assistant", "content": rec["thought"]},
    ], "_meta": rec.get("_meta")}


def _fmt_chronicle(rec: Dict) -> Dict:
    events = "\n".join(f"- {e}" for e in rec.get("events") or [])
    user = f"[ยุค] {rec['era']}\n[เหตุการณ์]\n{events}\nจงเขียนพงศาวดารสรุปยุคนี้"
    return {"messages": [
        {"role": "system", "content": SYSTEM_CHRONICLE},
        {"role": "user", "content": user},
        {"role": "assistant", "content": rec["chronicle"]},
    ], "_meta": rec.get("_meta")}


def _fmt_planning(rec: Dict) -> Dict:
    user = (f"[เป้าหมาย] {rec['goal']}\n[สถานะปัจจุบัน] {json.dumps(rec['state'], ensure_ascii=False)}\n"
            "จงวางแผนขั้นตอน")
    plan_text = " -> ".join(rec.get("plan") or [])
    return {"messages": [
        {"role": "system", "content": SYSTEM_PLANNER},
        {"role": "user", "content": user},
        {"role": "assistant", "content": plan_text},
    ], "_meta": rec.get("_meta")}


def _fmt_passthrough(rec: Dict) -> Dict:
    """Phase K7 — สำหรับไฟล์ที่ `lesson_exporter.py` export มาเป็น ChatML `{"messages": [...]}`
    อยู่แล้ว (story_lesson/arc_lesson/style_lesson จาก `datasets/lessons_v1/`) ไม่ต้องแปลงซ้ำ"""
    return {"messages": rec["messages"], "_meta": rec.get("_meta")}


_FORMATTERS = {
    "scene_sft.jsonl": _fmt_scene_sft,
    "dialogue.jsonl": _fmt_dialogue,
    "monologue.jsonl": _fmt_monologue,
    "chronicle.jsonl": _fmt_chronicle,
    "planning.jsonl": _fmt_planning,
    "story_lesson.jsonl": _fmt_passthrough,
    "arc_lesson.jsonl": _fmt_passthrough,
    "style_lesson.jsonl": _fmt_passthrough,
}


def iter_version_dir(version_dir: Path) -> Iterator[Dict]:
    """แปลงทุก record ในโฟลเดอร์เวอร์ชันหนึ่ง (v{N}/) เป็น ChatML message list"""
    for filename, fmt in _FORMATTERS.items():
        path = version_dir / filename
        if not path.exists():
            continue
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                try:
                    yield fmt(rec)
                except (KeyError, TypeError):
                    continue   # record ผิดรูปแบบ ข้ามไปแทนที่จะล้มทั้งก้อน


def load_dataset_dirs(datasets_root: Path, versions: List[str]) -> List[Dict]:
    """รวมหลายเวอร์ชัน (เช่น v1..vN จาก Phase F) เป็น list เดียวสำหรับเทรน"""
    examples: List[Dict] = []
    for v in versions:
        examples.extend(iter_version_dir(Path(datasets_root) / v))
    return examples
