# Cultivator Brain — Phase K: Narrative Teacher & Style Distillation — สถานะสุดท้าย

เอกสารสรุปนี้สร้างตามที่ `ROLE (3).MD` (เวอร์ชัน "MASTER PROMPT — Cultivator Brain Phase K") กำหนดไว้
ตรงๆ ในหัวข้อ "รูปแบบรายงาน (บังคับ)" — รายละเอียดการทำงานทีละ Phase (ไฟล์ที่แก้, การตัดสินใจ, ปัญหาที่
เจอ, ผลทดสอบจริง, คำสั่งที่ใช้ได้) บันทึกไว้ครบใน `CULTIVATOR_BRAIN_STATUS.md` ส่วนที่ 5 อยู่แล้ว
เอกสารนี้เป็น**บทสรุปรวบยอด**เท่านั้น ไม่ซ้ำรายละเอียดทั้งหมด

**Audit ก่อนเริ่ม** (ตามที่ ROLE Phase K กำหนดเป็นขั้นตอนแรก): ตรวจสอบกับโค้ดจริงแล้วว่าระบบเดิมที่
เอกสารอ้างว่า "เสร็จแล้ว" (Persistence ถึง Hot Swap, Phase 1-6/A-J ทั้งหมด) มีอยู่จริงครบ ไม่มีชื่อไฟล์
ใหม่ชนกับของเดิม พบจุดขัดแย้งเดียวคือ Shadow Evaluation weights (แก้ไว้ที่ Shadow Evaluation V2
ด้านล่าง) — รายละเอียดเต็มอยู่ที่จุดเริ่มต้นส่วนที่ 5 ของ `CULTIVATOR_BRAIN_STATUS.md`

---

## สิ่งที่เพิ่มทั้งหมด (K1-K7 + Multi-Task Training + Shadow Evaluation V2)

| Phase | ไฟล์ใหม่ | หน้าที่ |
|---|---|---|
| K1 — Narrative Teacher | `narrative_factory/teacher.py` | `StoryLesson` (hook/conflict/escalation/payoff/emotional_shift/pacing/lesson) rule-based ล้วนจาก Scene จริง |
| K2 — Pacing Engine | `narrative_factory/pacing.py` | แบ่ง Beat (Opening/Inciting/Rising/Peak/Aftermath) จากจำนวนเหตุการณ์จริง |
| K3 — Hook Detector | `narrative_factory/hook_detector.py` | จำแนก Hook จาก `event.kind` จริง (ละเอียดกว่า K1 เดิม) |
| K4 — Payoff Detector | `narrative_factory/payoff_detector.py` | Expectation -> Result จาก foreshadowing/payoff จริง |
| K5 — Arc Builder | `narrative_factory/arc_builder.py` | `StoryArc` รวมหลายฉากของตัวละครเดียวกันข้ามเวลา |
| K6 — Style Distillation | `narrative_factory/style_distill.py` | `StyleLesson` จาก Novel_Episodes จริงผ่าน LLM + กันคัดลอกข้อความ |
| K7 — Lesson Export | `narrative_factory/lesson_exporter.py`, `build_lessons.py` | Export ChatML ลง `datasets/lessons_v1/` |

**Multi-Task Training**: `dataset_formatter.py` (+3 formatter ใหม่), `autotrain.py` (auto-include
`lessons_v1`) — ขยายให้ autotrain โหลด Story/Arc/Style Lesson รวมกับ Dataset A-E เดิมได้

**Shadow Evaluation V2**: `scoring.py` — แทนที่ `WEIGHTS`/`PASS_THRESHOLD` ทั้งชุดตามที่ผู้ใช้เลือก
(Timeline 20/Character 20/Event 15/Memory 10/Style 20/**Pacing 15** ใหม่, ผ่านที่ 85) `hotswap.py`/
`evaluate_model.py` ไม่ต้องแก้เลยตามที่ ROLE Phase K ระบุไว้ตรงๆ

---

## สิ่งที่แก้ทั้งหมด (นอกเหนือจากไฟล์ใหม่)

- `tiandao/ai/llm_agent.py` — เพิ่ม `num_ctx` (optional) แก้บั๊กจริง Ollama ตัด context เหลือ 4096
  token เป็นดีฟอลต์เสมอไม่ว่าโมเดลรองรับยาวแค่ไหนจริง
- `narrative_factory/exporter.py`, `shadow_eval.py`, `pipeline.py` — ส่ง `scene=scene` ให้
  `score_candidate()` ใหม่
- `narrative_factory/config.yaml` — เพิ่ม `hook_by_scene_type`/`conflict_type_by_scene_type` (K1),
  `hook_by_kind` (K3), `arc_merge_window_days` (K5); `dpo_chosen_threshold` 85→90 (กันชนกับ
  `PASS_THRESHOLD` ใหม่)

รายละเอียดครบทุกไฟล์ (รวม Phase G-J เดิม) อยู่ที่ `CULTIVATOR_BRAIN_STATUS.md` หัวข้อ
"ไฟล์ทั้งหมดที่เพิ่ม/แก้"

---

## ผลทดสอบจริงสรุปรวม (ทุกอย่างทดสอบบนโลกจริง `tiandao/world.save`, 1,731 ฉาก, 864 ตัวละคร — ไม่มี
การ mock ใดๆ ทั้งสิ้น)

| Phase | ทดสอบ | ผล |
|---|---|---|
| K1 | `build_story_lesson()` ทุกฉากจริง | 1,731/1,731 — error 0 |
| K2 | `assign_beats()` unit + ทุกฉากจริง | ผ่านครบ, Peak เสมออยู่ท้าย, ไม่มี Aftermath โผล่เลย (ตามที่ออกแบบ) |
| K3+K4 | Hook/Payoff detector ทุกฉากจริง | 1,731/1,731 — error 0, 94% ได้ hook จากตาราง kind ละเอียด |
| K5 | `build_all_arcs()` ทุกฉากจริง | 1,731 ฉาก -> 1,314 อาร์ค, ฉากรวมตรงเป๊ะ ไม่มีตกหล่น/ซ้ำ |
| K6 | `distill_style()` กับ episode จริงผ่าน Ollama | ได้ StyleLesson จริง (หลังแก้บั๊ก `num_ctx`), `contains_verbatim_copy()` จับการคัดลอกจริงได้ (เจอเคสจริง 1 ครั้งตอน K7) |
| K7 | `build_lessons.py` เต็มรูปแบบ | 1,731 StoryLesson + 1,314 StoryArc + 1 StyleLesson (อีก 1 ถูก reject เพราะคัดลอกจริง) export ChatML ถูกต้อง |
| Multi-Task | โหลด v1+lessons_v1 รวมกัน | 5,003 ตัวอย่างเป๊ะ (1,957 เดิม + 3,046 ใหม่) — Dataset A-E เดิมไม่เสีย |
| Shadow Eval V2 | template ทุกฉากจริงผ่านเกณฑ์ใหม่ | 1,731/1,731 ผ่าน 100% (ไม่ regression) |
| เทรน smoke test | `autotrain.py --force --max-steps 5` บน 5,003 ตัวอย่าง → evaluate | REJECT (76.6 vs 87.7) — คาดว่า step ไม่พอ |
| เทรนจนลู่เข้าจริง (ไม่จำกัด step) | `loras/v3`, 5 epoch เต็ม, eval_loss 0.160→**0.131**→0.132 | REJECT อีกครั้ง (84.0 vs 89.0) — พบสาเหตุจริง: spurious correlation ในข้อมูล ไม่ใช่ปัญหาปริมาณการเทรน |
| **แก้ spurious correlation + เทรนใหม่** | `loras/v4`, 5 epoch, eval_loss 0.092→**0.0635** (ต่ำกว่า v3 เกือบครึ่ง) | **✅ APPROVE จริง — ยืนยันด้วย held-out set 79 ฉากที่ไม่เคยเห็นตอนเทรน** (candidate 99.9 vs baseline 88.1) |

**อัปเดตสำคัญหลังคุยกับผู้ใช้เพิ่ม (2 รอบ)**:

**รอบ 1 — "เทรน LoRA จริงจนลู่เข้า ไม่ต้องจำกัด step"**: ระหว่างทางเจอบั๊กจริงร้ายแรงใน
`train_lora.py:ChatDataset` (record ประเภท chronicle ที่ prompt ยาวเกิน `max_length` ทำให้ label
คำตอบโดน mask หมดจนเป็น `NaN` — พบ 6/5,003 ตัวอย่าง) **หยุดการเทรนที่กำลังรันอยู่ทันทีเพื่อแก้ก่อน**
แก้แล้วเพิ่ม held-out eval split + `EarlyStoppingCallback` + `load_best_model_at_end` เทรนใหม่จนครบ
5 epoch จริง (`loras/v3`, eval_loss ลู่เข้าสวยงามไม่มี NaN เลย) — **แต่ Shadow Evaluation Gate ยัง
reject 100%** ตรวจ output จริงพบรูปแบบ `"วันที่ {เลขที่แต่งขึ้นเอง}: ..."` ทุกครั้ง ละเมิด
`Rule2_NoFabricatedEvents` เสมอ — **สาเหตุคือ spurious correlation ที่เรียนไม่ได้จริงตั้งแต่ต้น**:
`exporter.py:118` ไม่ส่งเลข `day` เข้า training input เลย แต่ output template ใส่
`"วันที่ {e.day}: ..."` นำหน้าเสมอ

**รอบ 2 — "แก้ spurious correlation แล้วเทรนใหม่เลย"**: เพิ่ม
`exporter.py:build_scene_input_payload()` ใส่เลข `day` เข้า input ตรงๆ (`shadow_eval.py` แก้ให้ reuse
ฟังก์ชันเดียวกัน ไม่ duplicate) re-export เป็น `datasets/v2/` (ลบ `v1` เดิมที่มีบั๊กทิ้ง) เทรนใหม่
(`loras/v4`) — **eval_loss ลดลงเหลือ 0.0635 (ต่ำกว่า v3 เกือบครึ่ง — ยืนยันว่างานนี้เรียนรู้ได้ง่าย
ขึ้นจริงหลังมีสัญญาณที่ถูกต้อง)** ประเมินครั้งแรกด้วยฉากสุ่ม 15 ฉากได้ 100/100 **แต่ตรวจสอบเพิ่มพบว่า
ฉากทั้งหมดเคยอยู่ในชุดเทรน (อาจเป็นแค่ "จำได้")** จึงทดสอบซ้ำด้วย**ฉาก held-out จริง 79 ฉากที่ไม่เคยเห็น
เลยระหว่างเทรน** — **ได้ mean_score=99.9 pass_rate=100% เทียบ baseline 88.1/86% จริง** พิสูจน์ว่าเป็น
generalization จริง ไม่ใช่การท่องจำ — `loras/v4` คือ LoRA เวอร์ชันแรกของโปรเจกต์ที่ผ่าน Shadow
Evaluation Gate ด้วยหลักฐานที่น่าเชื่อถือจริง

---

## ปัญหาที่ยังเหลือ (สำคัญที่สุด — อ่านก่อนใช้งานจริง)

1. **✅ (แก้แล้ว) Dataset A (Scene SFT) template เคยมี spurious correlation** — แก้แล้วด้วย
   `build_scene_input_payload()` (ใส่เลข `day` เข้า input) `loras/v4` ผ่าน Gate จริงพร้อมหลักฐาน
   generalization จาก held-out set 79 ฉาก — ดูรายละเอียดเต็มที่ `CULTIVATOR_BRAIN_STATUS.md` ปัญหาข้อ 12
2. **✅ (deploy แล้ว) `cultivator-brain:latest`/`v4` สร้างจริงและรันได้จริงใน Ollama แล้ว** ผ่าน
   `hotswap.py` (merge → GGUF → ollama create/cp สำเร็จใน 11m48s) — **แต่ Cultivator Brain v2
   (Phase 5/Layer 3 — บทพูด/ความคิดตัวละครสด) ยังไม่ได้ใช้** `config_ai.OLLAMA_MODEL` ยังชี้
   `qwen2.5vl:7b` เดิม (เป็นการตัดสินใจแยกต่างหากที่ยังไม่ได้ทำ เพราะ `loras/v4` ไม่ได้เทรนบน
   Dataset B/C เลย ยังไม่พิสูจน์ว่าเหมาะกับงาน dialogue/thought JSON ของ Layer 3)
3. **การประเมินแบบสุ่มฉาก benchmark เดิมของ `evaluate_model.py` เสี่ยงวัด "ความจำ" ไม่ใช่ "ความสามารถ"
   ถ้าไม่ระวัง** — พิสูจน์แล้วว่า 15 ฉากที่สุ่มด้วย seed คงที่ทับซ้อนกับชุดเทรน 100% (0/15 เป็น held-out
   จริง) ต้องใช้วิธีพิเศษ (จำลอง shuffle เดียวกับตอนเทรนหาฉาก held-out จริง) ถึงจะได้ผลที่น่าเชื่อถือ —
   `evaluate_model.py`/`shadow_eval.py` เองยังไม่มีกลไก built-in ป้องกันเรื่องนี้อัตโนมัติ (ยังต้องทำ
   manual แบบที่ทำตอนตรวจ `loras/v4`)
4. **Ollama `num_ctx` fix ยังไม่ครอบคลุมทุกจุด** — แก้เฉพาะ `style_distill.py` (K6) เท่านั้น
5. **Hook/Payoff Detector (K3/K4) ยังไม่ได้ทดสอบกับฉากที่มีข้อมูลซับซ้อนกว่านี้** — โลกทดสอบมีฉากเดียว
   1,719/1,731 ฉาก (99%) ทำให้ escalation/Beat progression หลายขั้นตอนยังเห็นตัวอย่างจริงน้อย
6. **K6 ทดสอบแค่ 2 ตอนจาก Novel_Episodes ทั้งหมด 170 ตอน** — ยังไม่รู้ว่า `contains_verbatim_copy()`
   จะ false-positive/false-negative บ่อยแค่ไหนในสเกลใหญ่ (170 ตอน) และ `distill_style()` ยังไม่มี retry
   mechanism ถ้า reject (แค่ log แล้วข้าม — ตั้งใจ แต่ K7 ต้องรู้ว่าอาจได้ StyleLesson น้อยกว่าที่ป้อนเข้า)
7. รายการเดิมจาก Phase A-J ทั้งหมด (Event.seq, Phase 6 quality, Ollama model choice, Dataset B/C ว่าง,
   ฯลฯ) ยังเปิดอยู่เหมือนเดิม — ดูรายละเอียดที่ `CULTIVATOR_BRAIN_STATUS.md` หัวข้อ "ปัญหาที่เจอจริงและ
   ยังไม่แก้"

---

## สิ่งที่พร้อมสำหรับ Phase L

- **`cultivator-brain:latest` deploy จริงแล้วใน Ollama** (`loras/v4`, ผ่าน Shadow Evaluation Gate
  ด้วยหลักฐาน generalization ที่แท้จริง ไม่ใช่แค่คะแนนสูงเพราะจำได้) — ใช้งานได้ทันทีด้วย
  `ollama run cultivator-brain:latest` — ที่เหลือคือตัดสินใจว่าจะให้ Cultivator Brain v2 Layer 3
  (`config_ai.OLLAMA_MODEL`) เปลี่ยนมาใช้ด้วยหรือไม่ (ยังไม่ได้ทำ — ดูปัญหาข้อ 2 ด้านบน)
- โครงสร้าง Narrative Teacher ครบทั้ง 5 มิติ (Hook/Conflict/Escalation/Payoff/Emotional Shift/Pacing)
  พร้อม reuse เป็น building block ให้ Phase ถัดไปได้ทันที
- Multi-Task Training รองรับ 8 dataset type แล้ว (Scene SFT/Dialogue/Monologue/Chronicle/Planning/
  Story Lesson/Style Lesson/Arc Lesson) — เพิ่ม dataset ใหม่ในอนาคตทำตาม pattern
  `_fmt_*`/`_FORMATTERS` เดิมได้เลย
- Shadow Evaluation Gate มี metric ครบ 6 ตัวจริงแล้ว (ไม่ใช่แค่ 5 ตัวเดิม) พร้อมใช้ตัดสิน LoRA เวอร์ชัน
  ถัดไปได้ทันทีที่เทรนจริงจบ (ไม่ต้องแก้โค้ดเพิ่ม)
- `train_lora.py` พร้อม eval split + early stopping + cosine LR จริงแล้ว (ไม่ใช่ smoke-test-only
  อีกต่อไป) พิสูจน์แล้วว่าใช้งานได้จริงสองรอบติด (`v3`/`v4`)
- `num_ctx` fix ใน `llm_agent.py` พร้อมให้ Phase ถัดไปที่มี prompt ยาว reuse ได้ทันที (แค่เรียก
  `agent.complete(..., num_ctx=...)`)
- **ช่องว่างที่ชัดเจนที่สุดสำหรับ Phase L**: ตอนนี้ไม่ใช่ "จะเทรนให้ผ่าน Gate ได้ยังไง" อีกต่อไป (มี
  `loras/v4` ที่ผ่านแล้วจริง) — กลายเป็น (1) สั่ง `hotswap.py` deploy `loras/v4` เข้า Ollama จริง
  เมื่อพร้อม — **ทำแล้ว** (ดู "Hot-Swap Deploy จริง" ใน `CULTIVATOR_BRAIN_STATUS.md`) แต่ภายหลังพบว่า
  `cultivator-brain:latest` ไม่เหมาะกับงาน Layer 3 สด เปลี่ยน `OLLAMA_MODEL` กลับเป็น `qwen2.5vl:7b`
  แล้ว (2) ~~เพิ่มกลไก train/held-out split แบบถาวรใน `evaluate_model.py`/`shadow_eval.py` เอง (ตอนนี้
  ต้องทำ manual แบบที่ทำตอนตรวจ v4)~~ — **ทำแล้ว**: `train_lora.py` เขียน `held_out_scene_ids.json`
  ทุกครั้งที่เทรน, `evaluate_model.py` โหลดมาใช้กรอง benchmark อัตโนมัติ (รายละเอียดเต็มใน
  `CULTIVATOR_BRAIN_STATUS.md` ข้อ 3) — ใช้ได้กับ LoRA ที่เทรนใหม่นับจากนี้เท่านั้น `v1`-`v4` เดิมยังไม่มี
  ไฟล์นี้ (3) พิจารณาว่า Dataset A
  ที่เป็น flat template ล้วน (ไม่มี --llm) เหมาะจะเป็น "สไตล์การเขียน" ที่อยากให้โมเดลเลียนแบบจริงหรือไม่
  — ตอนนี้ `loras/v4` เก่งเรื่อง "คัดลอกข้อมูลจริงแม่นยำ" แต่ยังไม่ได้พิสูจน์ว่าเขียนร้อยแก้วสร้างสรรค์
  ได้ดีขึ้นจริง (ต้องมี Dataset A ที่ผ่าน --llm+Phase D validator จริงมากพอถึงจะทดสอบมิตินี้ได้)
