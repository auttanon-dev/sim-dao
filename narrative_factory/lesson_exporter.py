# -*- coding: utf-8 -*-
"""Phase K7 — Lesson Export: ส่งออก `StoryLesson` (K1) / `StoryArc` (K5) / `StyleLesson` (K6) เป็น
ChatML ลง `datasets/lessons_v1/` (ชื่อ fixed ตามที่ `ROLE` Phase K กำหนดตรงๆ — ไม่ใช้
`versioning.next_version_dir()` แบบ Dataset A-E ปกติ เพราะ Lesson dataset เป็นก้อนใหม่แยกต่างหาก
ไม่ผูกกับ incremental versioning เดิมของ Phase F)

รูปแบบ record ตาม `dataset_formatter.py` เดิม (`{"messages": [system, user, assistant]}`) เพื่อให้
Multi-Task Training (`autotrain.py`) โหลดรวมกับ Dataset A-E ได้ตรงๆ ผ่าน `dataset_formatter.py` ที่
ขยายเพิ่ม formatter ใหม่ 3 ตัว

**ไม่ต้องผ่าน Phase D Validator ซ้ำ**: K1/K5 กราวด์กับ log จริง 100% อยู่แล้ว (rule-based ล้วน ไม่มี
ความเสี่ยงหลอน) ส่วน K6 ผ่าน `contains_verbatim_copy()` กรองไปแล้วตอน `distill_style()` (คนละความเสี่ยง
กับ Phase D ที่เช็คความถูกต้องกับ sim log — K6 เช็คลิขสิทธิ์กับต้นฉบับนิยายแทน)

**แก้ spurious correlation (สำคัญ — พบตอนตรวจตามปัญหาข้อ 12 เดิม)**: เดิม `_story_lesson_record`/
`_arc_lesson_record` ใส่แค่ `scene_id`/`arc_id`/ชื่อตัวละครใน **input** แต่ **output** (`lesson.lesson`/
goal-obstacle-climax-resolution) เป็นการวิเคราะห์จากเนื้อหาฉากจริงทั้งหมด — โมเดลไม่มีทางเรียน mapping
จาก ID เปล่าๆ ไปเป็นการวิเคราะห์เนื้อหาได้จริง (แย่กว่าปัญหาข้อ 12 เดิมของ Dataset A ด้วยซ้ำ เพราะ
Dataset A อย่างน้อยยังมี event text ให้ทั้งหมด แค่ขาดเลขวันที่ — อันนี้ไม่มีเนื้อหาอะไรเลยในฝั่ง input)
แก้โดยใส่เนื้อหาฉากจริงกลับเข้า input: story_lesson reuse `exporter.build_scene_input_payload()` ตัว
เดียวกับ Dataset A ตรงๆ (ไม่ duplicate logic), arc_lesson ใช้ `StoryArc.scene_summaries` ใหม่ (Phase K5 —
วันที่/scene_type/conflict_level/payoff จริงของทุกฉากในอาร์ค) ทำให้ทั้งสองกลายเป็นงาน "สรุปจากข้อมูลที่
ให้มา" ที่เรียนรู้ได้จริง แทนที่จะเป็นงาน "จำ ID" ที่เป็นไปไม่ได้

`_style_lesson_record` มีปัญหาเดียวกัน (แก้แล้วเช่นกัน — เดิมมีแค่ `source_label` เปล่าๆ ในฝั่ง input)
แก้โดยเก็บ `episode_text` จริงไว้ใน `StyleLesson` ตอน `distill_style()` (`style_distill.py`) แล้วใส่เข้า
input ตรงๆ (episode เดียวกับที่ LLM เห็นตอน generate จริง ไม่ใช่ excerpt/สรุปใหม่) — record นี้จะยาวกว่า
record อื่นมาก (episode เต็ม ~9,000+ ตัวอักษร) ถ้าเกิน `train_lora.py --max-length` (ดีฟอลต์ 1024 token)
`ChatDataset` จะตัด prompt ให้สั้นลงอัตโนมัติ (กลไกเดิมที่มีอยู่แล้วจากตอนแก้บั๊ก chronicle NaN — ดู
`train_lora.py:MIN_COMPLETION_TOKENS`) ไม่ error ไม่ crash แค่เห็นเนื้อหาไม่ครบทั้งตอน ยังดีกว่าเดิมที่ไม่
เห็นอะไรเลย

**พบเพิ่มอีกจุด (ปัญหาข้อ 13 ต่อ — ยืนยันจริงจาก spot-check `loras/v5`)**: แก้ scene content เข้า input
แล้วแต่ `lesson.escalation`/`emotional_shift` ยังเรียนไม่ได้เต็มที่ เพราะมาจาก
`genome.compute_conflict_level()` ต่อเหตุการณ์ ซึ่งอ่านเลข `event.deltas["margin"]` ดิบๆ (เช่น 16.514)
ที่**ไม่ปรากฏในข้อความเหตุการณ์เลย** (`e.text` เป็นแค่คำบรรยาย ไม่มีตัวเลข) ต่างจาก `arc_lesson` ที่ใส่
`conflict_level` เป็นตัวเลขตรงๆ ใน `scene_summaries` อยู่แล้ว (Phase K5) จึงเรียนได้ดีกว่า (arc_lesson
spot-check 4/4 ตรง vs story_lesson 4/6) — แก้โดยใส่ `[ความเข้มข้น=N]` (ผลลัพธ์ `compute_conflict_level()`
ตัวเดียวกับที่ตัดสิน escalation) ต่อท้ายแต่ละเหตุการณ์ใน input ของ story_lesson โดยเฉพาะ (ไม่แตะ
`build_scene_input_payload()` ที่ Dataset A/Shadow Eval ใช้ร่วมกัน เพราะ field นี้ไม่เกี่ยวกับงานเขียน
ร้อยแก้วของ Dataset A เลย ใส่แค่ในจุดที่ต้องใช้จริง)"""
import json
import os
from typing import List, Optional

from . import genome as G
from .exporter import build_scene_input_payload

SYSTEM_STORY_LESSON = ("คุณคือนักวิเคราะห์วรรณกรรมนิยายกำลังภายในสไตล์จีน อธิบายโครงสร้างการเล่าเรื่อง"
                        "ของฉากที่ให้มา")
SYSTEM_STYLE_LESSON = ("คุณคือนักวิจารณ์วรรณกรรมนิยายกำลังภายในสไตล์จีน สรุปรูปแบบการเล่าเรื่อง"
                       "เชิงเทคนิค")
SYSTEM_ARC_LESSON = "คุณคือนักวิเคราะห์โครงเรื่องนิยายกำลังภายในสไตล์จีน สรุปเส้นทางเรื่องราวของตัวละคร"


def _format_scene_input(payload: dict) -> str:
    events = "\n".join(f"- {e}" for e in payload["events"]) or "- (ไม่มีเหตุการณ์)"
    return (f"[สถานที่] {payload['location']}\n"
            f"[ผู้เกี่ยวข้อง] {', '.join(payload['participants']) or '(ไม่มี)'}\n"
            f"[เหตุการณ์ตามลำดับ]\n{events}")


def _story_lesson_record(lesson, scene, sim, config: Optional[dict] = None) -> dict:
    payload = build_scene_input_payload(scene, sim)
    payload["events"] = [
        f"{ev_text} [ความเข้มข้น={G.compute_conflict_level(e, config)}]"
        for ev_text, e in zip(payload["events"], scene.events)
    ]
    scene_input = _format_scene_input(payload)
    user = f"วิเคราะห์โครงสร้างการเล่าเรื่องของฉากนี้ (scene_id={lesson.scene_id}):\n{scene_input}"
    return {"messages": [
        {"role": "system", "content": SYSTEM_STORY_LESSON},
        {"role": "user", "content": user},
        {"role": "assistant", "content": lesson.lesson},
    ], "_meta": {"scene_id": lesson.scene_id}}


def _style_lesson_record(lesson) -> dict:
    user = f"สรุปรูปแบบการเล่าเรื่องของตอนนี้ (source={lesson.source_label}):\n[ตอนนิยาย]\n{lesson.episode_text}"
    assistant = (f"Hook: {lesson.hook_pattern}\nDialogue: {lesson.dialogue_pattern}\n"
                 f"Pacing: {lesson.pacing_pattern}\nCliffhanger: {lesson.cliffhanger_pattern}\n"
                 f"Narration: {lesson.narration_pattern}")
    return {"messages": [
        {"role": "system", "content": SYSTEM_STYLE_LESSON},
        {"role": "user", "content": user},
        {"role": "assistant", "content": assistant},
    ], "_meta": {"source_label": lesson.source_label}}


def _arc_lesson_record(arc) -> dict:
    scenes_block = "\n".join(f"- {s}" for s in arc.scene_summaries) or "- (ไม่มีฉาก)"
    user = (f"สรุปเส้นทางเรื่องราวของ {arc.protagonist} (arc_id={arc.arc_id}, "
            f"วันที่ {arc.start_day}-{arc.end_day}):\n[ฉากในอาร์คตามลำดับ]\n{scenes_block}")
    assistant = (f"เป้าหมาย: {arc.goal}\nอุปสรรค: {arc.obstacle}\nจุดพีค: {arc.climax}\n"
                 f"บทสรุป: {arc.resolution}")
    return {"messages": [
        {"role": "system", "content": SYSTEM_ARC_LESSON},
        {"role": "user", "content": user},
        {"role": "assistant", "content": assistant},
    ], "_meta": {"arc_id": arc.arc_id, "scene_ids": arc.scene_ids}}


def export_lessons(story_lessons: List, scenes: List, story_arcs: List, style_lessons: List,
                    sim, base_dir: str = ".", config: Optional[dict] = None) -> str:
    """เขียน `datasets/lessons_v1/{story_lesson,arc_lesson,style_lesson}.jsonl` — เอนทรีพอยต์หลัก
    คืน path ของโฟลเดอร์ที่เขียน

    `scenes`/`sim`: เพิ่มใหม่เพื่อกราวด์ input ของ story_lesson (ดูหัวไฟล์ — แก้ spurious correlation)
    ต้องเรียงตำแหน่งตรงกับ `story_lessons` เป๊ะ (คือกรณีใช้จริงเสมอ — `build_lessons.py` สร้าง
    `story_lessons` จาก `[T.build_story_lesson(s, cfg) for s in scenes]` อยู่แล้ว) — `config`: ส่งต่อ
    ให้ `compute_conflict_level()` ต้องเป็น `cfg` เดียวกับที่ใช้สร้าง `story_lessons` เอง ไม่งั้นเลข
    `[ความเข้มข้น=N]` ใน input จะไม่ตรงกับ escalation ที่ `teacher.py` คำนวณไว้ใน output"""
    out_dir = os.path.join(base_dir, "datasets", "lessons_v1")
    os.makedirs(out_dir, exist_ok=True)
    files = {
        "story_lesson.jsonl": [_story_lesson_record(l, s, sim, config)
                                for l, s in zip(story_lessons, scenes)],
        "arc_lesson.jsonl": [_arc_lesson_record(a) for a in story_arcs],
        "style_lesson.jsonl": [_style_lesson_record(s) for s in style_lessons],
    }
    for filename, records in files.items():
        with open(os.path.join(out_dir, filename), "w", encoding="utf-8") as f:
            for rec in records:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return out_dir
