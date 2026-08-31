# Cultivator Brain v2 + Narrative Dataset Factory — สถานะปัจจุบัน

เอกสารนี้สรุปว่าตอนนี้มีอะไรอยู่ในโปรเจกต์บ้าง (นอกเหนือจากเอนจินซิมเดิมที่อธิบายไว้ใน `SPEC.md`)
และปัญหา/ข้อจำกัดจริงที่เจอระหว่างสร้างและทดสอบ — สำหรับใครก็ตามที่มาต่องานนี้ทีหลัง (รวมถึงตัวเองในอนาคต)

เป้าหมายที่ขับเคลื่อนงานชุดนี้แบ่งเป็น 3 รอบ:
1. **`ROLE.md`** — เพิ่มระบบ AI หลายเลเยอร์ให้ตัวละครในซิม "มีสัญชาตญาณ วางแผนเอง มีความทรงจำ พูดคุย
   ผ่าน Ollama สร้างประวัติศาสตร์ของตัวเอง" ปลายทางคือให้เอนจินผลิตเนื้อหาได้ใกล้เคียง
   `G:\My Drive\Project\My_AI_Second_Brain\Novel_Episodes` (นิยายกำลังภายในสไตล์จีนที่มีอยู่แล้ว)
2. **`ROLE (1).md`** — ต่อยอดจากข้อ 1: สร้าง **Narrative Dataset Factory** ที่แปลง `sim.log` เป็น
   training dataset คุณภาพสูงสำหรับ fine-tune LoRA (Qwen3 32B/LongWriter ในอนาคต) รวม "Narrative
   Genome" (DNA ของฉาก — scene_type/emotion_curve/conflict_level/dao_theme/foreshadowing/payoff)
   ที่ผู้ใช้เสนอเพิ่มเข้ามาเอง
3. **`ROLE (2).MD`** — roadmap ปิดลูปเป็น **Closed-Loop Self-Learning Flywheel** (Dataset → Fine-tune
   → Model ใหม่ → ขับเคลื่อน Sim/Story ต่อ) ตรวจสอบกับโค้ดจริงแล้วแก้ไขก่อนเริ่มทำ (พบว่า roadmap
   อ้างถึงความสามารถบางอย่างที่ยังไม่มีจริง เช่น เกณฑ์คะแนน/ที่เก็บ rejected data) แบ่งเป็น Phase G-J

---

## ⏸️ หมายเหตุ: พักงานไว้ตรงนี้ — สรุปสำหรับกลับมาทำต่อ

**สถานะล่าสุด ณ ตอนพัก**: Phase K (K1-K7 ครบ) + Multi-Task Training + Shadow Evaluation V2 +
Hot-Swap Deploy จริง **เสร็จสมบูรณ์แล้ว** — `cultivator-brain:latest` (จาก `loras/v4`) ทำงานจริงใน
Ollama และตั้งเป็นดีฟอลต์ของ Layer 3 แล้ว (`config_ai.OLLAMA_MODEL`)

**สิ่งที่ยังค้างอยู่ ยังไม่ได้ทำต่อ (ทำต่อได้ทันทีไม่ต้องเซ็ตอัพใหม่)**:
1. ~~ยังไม่ได้ประเมินคุณภาพ `cultivator-brain:latest` เทียบกับ `qwen2.5vl:7b` เดิมอย่างเป็นระบบ~~ —
   **แก้แล้ว**: รัน A/B จริง (prompt/character/brain state ชุดเดียวกันทั้งสองโมเดล ผ่าน
   `LLM.build_prompt()`/`OllamaAgent` ตัวจริง ไม่ mock) 45 เหตุการณ์ ครอบคลุมครบทุก `NOTABLE_KINDS`
   (3 ตัวอย่าง/kind, สุ่มด้วย seed คงที่จาก `tiandao/world.save` จริง) — **ผล: `cultivator-brain:latest`
   แย่กว่าชัดเจนสำหรับงาน JSON `{"dialogue","thought"}` นี้โดยเฉพาะ**: JSON parse สำเร็จ 38/45 (84%)
   เทียบ 45/45 (100%) ของ `qwen2.5vl:7b`, อักษรจีนหลุดปน 8/45 (18%) เทียบ 1/45 (2%), มี 1 ครั้งตอบว่าง
   เปล่าทั้งหมดใช้เวลาถึง 32 วินาที และอย่างน้อย 1 ครั้งหลุด raw state text ภาษาจีนยาว (ทำนอง
   "关注度：0.4\n洛奇·塞西格曼：0...") ปนออกมาใน `thought` — ตรงกับความเสี่ยงที่บันทึกไว้ตอนเปลี่ยนโมเดล
   (`loras/v4` ไม่เคยเห็น Dataset B/C ตอนเทรนเพราะ world ที่ใช้เทรนไม่เคยรันด้วย `--llm` มาก่อน ไม่มี
   ตัวอย่างงาน dialogue/thought จริงให้เรียนรู้) — **เปลี่ยน `OLLAMA_MODEL` กลับเป็น `qwen2.5vl:7b` แล้ว**
   ใน `tiandao/ai/config_ai.py` พร้อมบันทึกตัวเลขผลทดสอบไว้ในคอมเมนต์ (ดูปัญหาข้อ 10 ด้านล่างด้วย)
2. ~~ปัญหาข้อ 12 เดิม (spurious correlation) แก้แล้วแค่ Dataset A (Scene SFT) — ยังไม่ได้ตรวจว่า
   Story/Arc Lesson data มีปัญหาคล้ายกันแอบซ่อนอยู่หรือไม่~~ — **ตรวจแล้ว พบปัญหาจริง แย่กว่า Dataset A
   เดิมด้วยซ้ำ แก้แล้ว**: `lesson_exporter.py` เดิม (`_story_lesson_record`/`_arc_lesson_record`) ใส่แค่
   `scene_id`/`arc_id`/ชื่อตัวละครเปล่าๆ ใน **input** แต่ **output** (`lesson.lesson` จาก `teacher.py`
   และ goal/obstacle/climax/resolution จาก `arc_builder.py`) เป็นการวิเคราะห์จากเนื้อหาฉากทั้งหมด —
   ไม่มีเนื้อหาอะไรเลยในฝั่ง input ให้เรียน mapping ได้ (แย่กว่า Dataset A เดิมที่อย่างน้อยมี event text
   ให้ครบ แค่ขาดเลขวันที่) กระทบ 3,045/5,003 ตัวอย่าง (60.9%) ของ Multi-Task Training ทั้งชุด
   (story_lesson 1,731 + arc_lesson 1,314) — **แก้แล้ว**: `_story_lesson_record` เพิ่ม `scene`/`sim`
   แล้ว reuse `exporter.build_scene_input_payload()` ตัวเดียวกับ Dataset A ใส่ location/participants/
   events (พร้อมเลขวันที่) เข้า input ตรงๆ, `arc_builder.py:StoryArc` เพิ่มฟิลด์ใหม่ `scene_summaries`
   (วันที่/scene_type/conflict_level/payoff จริงของทุกฉากในอาร์ค) ให้ `_arc_lesson_record` ใส่เข้า input
   — ทั้งสองกลายเป็นงาน "สรุปจากข้อมูลที่ให้มา" ที่เรียนรู้ได้จริงแทนงาน "จำ ID" ที่เป็นไปไม่ได้ —
   re-export `datasets/lessons_v1/` แล้ว (ยืนยัน `dataset_formatter.load_dataset_dirs()` โหลดรวมได้ปกติ
   5,004 ตัวอย่าง ไม่พัง)

   ~~`style_lesson.jsonl` (K6) มีรูปแบบปัญหาเดียวกัน (`source_label` เปล่าๆ ใน input ไม่มี episode
   text) แต่ยังไม่ได้แก้~~ — **แก้แล้วด้วย**: `StyleLesson` (`style_distill.py`) เพิ่มฟิลด์
   `episode_text` เก็บตอนนิยายจริงที่ใช้วิเคราะห์ไว้ด้วย (เดิมทิ้งไปหลัง `distill_style()` คืนค่า),
   `lesson_exporter.py:_style_lesson_record` ใส่เข้า input ตรงๆ (episode เดียวกับที่ LLM เห็นตอน
   generate จริง) — re-export จริงแล้วหลัง GPU ว่าง (`build_lessons.py --style-limit 2
   --novel-episodes-dir ...`) ยืนยัน `style_lesson.jsonl` มี `[ตอนนิยาย]` เนื้อหาจริง 9,172 ตัวอักษร
   ใน input record แรกแล้ว (ก่อนหน้านี้มีแค่ `source_label` เปล่าๆ)

   **เทรน `loras/v5` ด้วยข้อมูลที่แก้ครบแล้ว (story/arc/style lesson)**: `autotrain.py --force
   --epochs 5` — `eval_loss` ลดลงต่อเนื่องชัดเจน 0.0251→0.0182→0.0180→**0.0174 (ต่ำสุด, epoch 4 — best
   model)**→0.0185 (epoch 5, เริ่ม overfit เล็กน้อยเหมือน v4/v3) — ต่ำกว่า `loras/v4` เดิมมาก
   (0.092→0.0635) สอดคล้องกับที่คาดไว้ว่าข้อมูลที่กราวด์แล้วเรียนรู้ได้ง่ายกว่าจริง — บันทึก
   `held_out_scene_ids.json` (175 ฉาก held-out) สำเร็จ

   **ประเมินจริงผ่าน held-out mechanism ใหม่ (ข้อ 3)**: `evaluate_model.py --candidate-lora loras/v5
   --baseline-lora loras/v4 --n-scenes 15` บน 15/175 ฉาก held-out จริงของ `v5` (ไม่เคยผ่านตาทั้งสอง
   โมเดลตอนเทรน) — **ผล: v5 mean_score=100.0 pass_rate=100% เท่ากับ v4 เป๊ะ (15/15 ฉากได้ 100 คะแนน
   ทั้งคู่ ไม่ใช่แค่ปัดเศษ) → APPROVE (เสมอกันที่เพดานคะแนน)** — **ข้อควรรู้**: เกณฑ์นี้วัดแค่งาน Scene
   SFT ("เขียนฉาก") ผ่าน `scoring.py` เท่านั้น ซึ่งทั้งสองเวอร์ชันเทรนบน Dataset A (v2) ชุดเดียวกันไม่
   เปลี่ยน (v5 ต่างจาก v4 แค่ตรง lessons_v1 ที่แก้แล้ว) จึงไม่แปลกที่คะแนนงานนี้เท่ากัน — **ยังไม่มีเกณฑ์
   วัดคุณภาพ story/arc/style lesson โดยตรง** (Lesson dataset ไม่ผ่าน Phase D Validator/Scoring ตามที่
   ออกแบบไว้ตั้งแต่ K7 — ดู `lesson_exporter.py`) ดังนั้นผลทดสอบนี้ยืนยันได้แค่ว่า **การแก้ spurious
   correlation ใน lesson data ไม่ได้ทำให้ความสามารถเขียนฉากถดถอย** ไม่ใช่หลักฐานว่า v5 เขียนบทวิเคราะห์
   เรื่องราวเก่งขึ้นจริง (ต้องตรวจ output จริงของ v5 บนงาน story/arc lesson โดยตรง หรือสร้าง metric ใหม่
   ถ้าต้องการพิสูจน์ข้อนั้น)

   (พบปัญหาระหว่างประเมิน: ครั้งแรก crash เพราะ Ollama server ยังค้าง `qwen2.5vl:7b` ใน VRAM จากตอน
   re-export style_lesson ก่อนหน้า — `ollama stop qwen2.5vl:7b` แล้วรันซ้ำสำเร็จ)

   **ตรวจ output จริงของ v5 บนงาน story/arc lesson แล้ว (spot-check เชิงคุณภาพ, ไม่ใช่ metric อัตโนมัติ
   — เพราะยังไม่มี)**: generate จริงด้วย prompt shape เดียวกับตอนเทรนเป๊ะ (`lesson_exporter.py`) บนฉาก/
   อาร์คที่ held-out จริง (มาจาก `held_out_scene_ids.json`) เทียบกับ ground truth แบบ deterministic
   (`teacher.build_story_lesson()`/`arc_builder` — คำตอบที่ถูกต้องแน่นอนเพราะเป็น rule-based):
   - **arc_lesson: 4/4 ตรงกับ ground truth เป๊ะ** (goal/obstacle/climax/resolution ถูกทุกคำ) — หลักฐาน
     ชัดว่าโมเดลเรียน mapping จริง ไม่ใช่จำ (อาร์คเหล่านี้ไม่เคยเห็นตอนเทรนแน่นอน)
   - **story_lesson: 4/6 ตรงเป๊ะ** อีก 2/6 มีจุดผิดจริง — `0-644`: escalation/emotional_shift ของ
     เหตุการณ์แรกผิด ("Peak→Low" ที่จริงควรเป็น "Low→Low"); `0-62`: escalation/emotion ผิด **และหลุด
     คำตัดสินผลผิดในบรรทัด payoff** (ตอบ "พ่ายแพ้" ทั้งที่จริงคือ "รอดตายด้วยชะตา" — แม้ข้อความส่วนที่
     เหลือของบรรทัดจะตรงเป๊ะ) — สรุป: โมเดลเรียน hook/conflict/pacing/การคัดลอก event text ใน payoff
     ได้แม่นจริง แต่ยังจำแนก conflict-level bucket/อารมณ์ของแต่ละเหตุการณ์ผิดได้บ้าง (~1/3 ของตัวอย่าง)
   - ~~**ข้อสังเกตข้างเคียง (บั๊กที่อาจมีอยู่ก่อนแล้ว ไม่เกี่ยวกับการแก้วันนี้)**: ground truth ของฉาก
     `1-2945` มี payoff อ้างถึงตัวละคร "เย่เฟย" ที่ไม่อยู่ใน `[ผู้เกี่ยวข้อง]` ของฉากนั้นเลย (มีแค่
     เยว่ฉาง/เยว่ยาน) — v5 ตอบ "ไม่มีการปูเรื่องล่วงหน้า" แทน ซึ่งดูสมเหตุสมผลกว่าตาม input ที่ให้ไป —
     น่าจะเป็นบั๊กเดิมใน `payoff_detector.py`/`genome.compute_foreshadowing()` (จับคู่ foreshadowing
     ข้ามตัวละครผิดคน) ยังไม่ได้สืบสวนต่อ~~ — **สืบสวนแล้ว แก้แล้ว** ดูหัวข้อ "13. foreshadowing
     ข้ามตัวละครที่ไม่เกี่ยวข้องกับฉาก" ด้านล่าง
   - รายละเอียดเต็ม (input/ground-truth/generated ครบทั้ง 10 ตัวอย่าง) อยู่ใน scratchpad ของเซสชันนี้
     ไม่ได้ commit เข้าโปรเจกต์ (ad-hoc เหมือนกับที่ทำตอนตรวจ v4)
3. ~~`evaluate_model.py`/`shadow_eval.py` ยังไม่มีกลไก train/held-out split ในตัว — ต้องทำ manual
   ทุกครั้ง~~ — **แก้แล้ว**: เดิม `_meta` (มี `scene_id`) ของทุก record ถูก `dataset_formatter.py` ทิ้ง
   ตอนแปลงเป็น ChatML `{"messages": [...]}` ทำให้ `train_lora.py` ไม่มีทางรู้เลยว่า example ไหนในฝั่ง
   validation split (`eval_ratio`) คือฉากไหน (ต้อง reverse-engineer เอา seed/shuffle เดียวกันมารันซ้ำ
   เองแบบ ad-hoc ตอนตรวจ `loras/v4`) — แก้โดย:
   - ทุก `_fmt_*` ใน `dataset_formatter.py` คืน `_meta` ต่อจาก raw record ไปด้วย (ไม่ทิ้งอีกต่อไป)
   - `arc_builder.py:StoryArc` เพิ่มฟิลด์ `scene_ids` (คู่กับ `scene_summaries` จากข้อ 2) —
     `lesson_exporter.py:_arc_lesson_record` ใส่เข้า `_meta.scene_ids` เพื่อให้ arc_lesson นับรวมด้วย
     (ไม่งั้นฉากที่กันไว้เป็น held-out จะรั่วผ่าน arc_lesson ที่อ้างถึงฉากเดียวกันได้)
   - `train_lora.py:train()` เพิ่ม `_collect_scene_ids()` — เก็บ scene_id ทุกอันจาก `_meta.scene_id`/
     `_meta.scene_ids` ของ `eval_examples` (ฝั่งที่กันไว้ ไม่ได้เอาไปเทรน) แล้วเขียนลง
     `{output_dir}/held_out_scene_ids.json` ทุกครั้งที่เทรนจบ (มี `seed`/`eval_ratio`/scene_id list —
     bookkeeping ครบให้ตรวจสอบย้อนหลังได้)
   - `evaluate_model.py` เพิ่ม `_load_held_out_scene_ids()` — ถ้าเจอไฟล์นี้ที่ `--candidate-lora` จะกรอง
     benchmark scenes ให้เหลือแค่ฉาก held-out จริงโดยอัตโนมัติ (ใช้ชุดเดียวกันประเมินทั้ง baseline/
     candidate) ถ้าไม่เจอ (LoRA เก่า `v1`-`v4` ก่อนมีกลไกนี้ หรือเทรนด้วย `eval_ratio=0`) fallback กลับ
     สุ่มฉากทั่วไปเหมือนเดิมพร้อมพิมพ์คำเตือนชัดเจนว่าอาจซ้อนกับฉากที่เคยเทรน — บันทึก
     `held_out_split_used: bool` ลง eval result JSON ด้วยเพื่อให้ตรวจสอบย้อนหลังได้ว่าผลไหนน่าเชื่อถือแค่ไหน
   - **ทดสอบจริงเต็มรูปแบบ (ไม่ mock, บน RTX 5060 Ti จริง)**: เทรน LoRA smoke test จริง 1 step จาก 40
     ตัวอย่างจริง (`eval_ratio=0.1` → held-out 4 ฉาก) ยืนยันไฟล์ `held_out_scene_ids.json` เขียนถูกต้อง
     (`scene_ids: ["0-126","5-3","5-30","5-33"]`) แล้วรัน `evaluate_model.py --candidate-lora
     loras/_smoke_test_item3` จริง — ยืนยันคำสั่งพิมพ์ "ใช้ held-out split จริง...4/4 ฉาก held-out ยังอยู่
     ในโลกนี้จริง" และประเมินเฉพาะฉากเหล่านั้นจริง — ทดสอบ fallback แยกด้วย `loras/v1`/`v4` (ไม่มีไฟล์นี้)
     ยืนยันคืน `None` ถูกต้อง (LoRA เก่าใช้ fallback สุ่มฉากทั่วไปเหมือนเดิม ไม่พัง) — ลบ LoRA/ไฟล์ทดสอบ
     ทิ้งแล้วหลังพิสูจน์เสร็จ
   - **ยังไม่ได้ทำ**: LoRA `v1`-`v4` ที่มีอยู่แล้วไม่มี `held_out_scene_ids.json` ย้อนหลัง (เขียนไม่ได้
     เพราะไม่ได้เก็บ RNG state ตอนเทรนไว้) ถ้าจะประเมิน `v4` แบบ generalization จริงอีกต้องใช้ผลเดิมที่
     ทำ manual ไว้แล้ว (`datasets/eval_results/eval_true_holdout_v4.json`) — กลไกใหม่นี้มีผลกับ LoRA ที่
     เทรน**ใหม่**นับจากนี้เท่านั้น
4. รายการเปิดอื่นๆ ทั้งหมดอยู่ในหัวข้อ "ปัญหาที่เจอจริงและยังไม่แก้" ด้านล่าง (ข้อ 1-12) และใน
   `CULTIVATOR_BRAIN_STATUS_PHASE_K.md` หัวข้อ "ปัญหาที่ยังเหลือ"/"สิ่งที่พร้อมสำหรับ Phase L"

**ไฟล์/สถานะที่มีอยู่จริงตอนนี้ (ไม่ต้องสร้างใหม่)**: `tiandao/world.save` (1,731 ฉาก, 864 ตัวละคร),
`datasets/v2/` (Dataset A-E ที่แก้ spurious correlation แล้ว) + `datasets/lessons_v1/`,
`loras/v1`-`v4` (v4 คือตัวที่ผ่าน Gate จริงและ deploy แล้ว), `cultivator-brain:v4`/`:latest` ใน Ollama

---

## ส่วนที่ 1 — โลกที่ทำงานได้ด้วยตัวเอง (ก่อนเริ่ม ROLE.md)

ทำก่อนที่จะได้ ROLE.md มา ตอบโจทย์ "ให้โลกเดินต่อเนื่องเอง ไม่ใช่รันทีเดียวจบ"

| ไฟล์ | หน้าที่ |
|---|---|
| `tiandao/persist.py` | เซฟ/โหลดสถานะ `Sim` ทั้งก้อนด้วย pickle — เดินต่อข้ามการเรียกโปรแกรมได้ |
| `daemon.py` | ลูปเดินต่อเนื่อง: resume-or-create → รันทีละก้อน → เซฟ → ปรับค่าคงที่เอง (online tuning) → พัก → วนต่อ |
| `tiandao/seasons.py` | ฤดูกาล 4 ฤดูวนตามวัน คูณเข้ากับ eco regen + จุดภัยพิบัติตามฤดู (ภัยแล้ง/น้ำท่วม/ข้าวยากหมากแพง) |
| `dashboard.py` + `templates/dashboard.html` | เว็บดูสถานะโลกสดๆ (FastAPI) อ่านจากไฟล์ save อย่างเดียว |
| `tiandao/tuning.py`, `tiandao/metrics.py`, `autotune.py` | ของเดิมที่มีอยู่ก่อนแล้ว (ไม่ได้แก้ในรอบนี้) ใช้ปรับสมดุลค่าคงที่แบบ offline หลาย seed |
| `tiandao/chronicle.py` | ของเดิม บันทึกตำนานข้ามรัน |

**คำสั่งที่ใช้ได้จริงตอนนี้:**
```bash
python run.py --seed 1 --events 20000 --save          # รันแล้วเซฟโลก
python run.py --resume --events 20000 --save           # เดินต่อจากที่เซฟไว้
python daemon.py --chunk-events 20000 --iterations 10   # เดินต่อเนื่องหลายรอบ ปรับค่าเอง
python dashboard.py                                     # เปิดคู่กับ daemon.py ดูสดที่ localhost:8000
```

**ปัญหาที่เจอตอนนั้น (แก้แล้วใน Phase G ของ `ROLE (2).MD` — ดูส่วนที่ 4)**: `tiandao/world.save` โต
ไม่มีเพดาน (ทดสอบ 200k เหตุการณ์ → 73MB) เพราะ `sim.log` เก็บทุกเหตุการณ์สะสมตลอดไป ไม่มีการตัดทิ้ง

---

## ส่วนที่ 2 — Cultivator Brain v2 (ตาม ROLE.md, ทำเป็น 6 เฟส)

ทุกเฟสอยู่ใน `tiandao/ai/` เป็น expansion module แยกจากเอนจินเดิม — ไม่แก้ `models.py`/`intent.py`/
`sim.py` เกินจำเป็น (`sim.py` แก้แค่ 3-4 จุดเพื่อ "เสียบสาย" เข้ากับของเดิม)

### Phase 1 — Event Bus + CharacterBrain skeleton
`tiandao/ai/event_bus.py`, `tiandao/ai/brain.py` (บางส่วน), `tiandao/ai/config_ai.py`
- ห่อ `Sim.emit()` เดิมเป็น pub/sub — ไม่แตะจุดที่เรียก `self.emit()` ทั้ง ~40 จุด
- `CharacterBrain` ผูกกับ `cid` ผ่าน `sim.brain_manager` (component แยก ไม่ใช่ field บน `Character`)
- Episodic memory มีเพดาน (`EPISODIC_MEMORY_CAP=30`) ตั้งใจไม่ให้ซ้ำปัญหา `world.save` โตไม่มีเพดาน
- **พฤติกรรมเดิม 100%** — เฟสนี้แค่ฟังเฉยๆ ยังไม่มีผลต่อการตัดสินใจ

### Phase 2 — Layer 1: Utility AI
`tiandao/ai/utility.py`
- Dual Utility ตาม ROLE.md: Survival (`Escape`,`Meditate`) / Ambition (`Breakthrough`,`Revenge`,
  `Wealth`,`Reputation`,`DaoPursuit`) คำนวณจาก field ที่มีอยู่แล้วบน `Character` ทั้งหมด
- ต่อยอด `intent.py:weigh()` เดิมด้วยการ "boost" น้ำหนัก ไม่เคยลดหรือบังคับ
- **หมายเหตุ**: เอนจินไม่มีสถิติ Hunger/Qi จริง จึงไม่ประดิษฐ์ field ใหม่ ใช้ HP+decay+fear แทน
- **ยืนยันผลจริง**: `advancement_rate` ขยับจาก ~0.20-0.24 → 0.26-0.29 หลังเปิดใช้ (วัดจาก daemon หลายรอบ)

### Phase 3 — Layer 2: Hierarchical GOAP
`tiandao/ai/goap.py`
- decompose เฉพาะ Goal `Breakthrough` (ตัวอย่างเดียวที่ ROLE.md ระบุรายละเอียดพอ) เป็น "Find Pill"
  4 วิธี (Craft→หลอมยา, Buy→ค้าขาย, Trade→เปิดประมูล, Rob→ชิงสมบัติ) แต่ละวิธีมี precondition จริง
  จาก state ตัวละคร (มีเตา/มีเงิน/อยู่ตลาด/โลภ)
- Replan เป็นผลพลอยได้ของการคำนวณสดทุกเทิร์น (ไม่มี "แผนค้าง" ให้ invalidate) — ยาที่ใช้ไปแล้วหาย
  จาก inventory เอง ทำให้ precondition เปลี่ยนเองตามจริง
- Need อื่นๆ ยังใช้ Phase 2 boost ตรงๆ (ไม่ decompose เพราะ ROLE.md ไม่ได้ให้ตัวอย่างไว้)

### Phase 4 — Memory System
`tiandao/ai/memory.py`
- **Episodic**: มีจาก Phase 1 แล้ว
- **Semantic**: `PlaceFact` ต่อสถานที่ (danger/fortune แบบ EMA จากประสบการณ์ตรง) เพดาน 20 ที่/คน
- **Relationship**: ไม่เก็บซ้ำ — อ่านจาก `ch.rivals`/`ch.bonds` ที่มีอยู่แล้วตรงๆ
- **Reputation**: ตัวเลขโครงสร้าง `{region: {fame, notoriety}}` — ตั้งใจไม่ปั้นข้อความฉายาตอนนี้
  (ปล่อยให้ Layer 3 แปลงเป็นฉายาจริงตอน generate)
- เพิ่ม `CharacterBrain.__setstate__` เพื่อให้ save เก่าที่ยังไม่มี field ใหม่ unpickle ได้ไม่พัง

### Phase 5 — Layer 3: Local LLM Agent (Ollama)
`tiandao/ai/llm_agent.py`
- Trigger จาก event "น่าจดจำ" เท่านั้น (`NOTABLE_KINDS`/`NOTABLE_OUTCOMES` — ตั้งแต่ Phase 1)
- Prompt ครบ 6 field ตาม ROLE.md: Character/Traits/Memory/Current Emotion/Event/Task
- ผลลัพธ์ (dialogue+thought) เก็บเป็น `NarrativeMoment` ใน `brain.narrative_moments` = "Memory Update"
- **ปิดเป็นค่าเริ่มต้น** (`LLM_ENABLED=False`) เปิดผ่าน `--llm` ใน `run.py`/`daemon.py`
- **วัดเวลาจริง**: 500 เหตุการณ์ปกติ = หลักวินาที, เปิด `--llm` = **8 นาที 35 วินาที** — บล็อกกิ้ง HTTP
  call ต่อ event ที่น่าจดจำแพงมาก ห้ามเปิดตอนรัน daemon ก้อนใหญ่/autotune

### Phase 6 — History Generator
`tiandao/ai/history.py`, `generate_episode.py` (CLI แยกที่ root)
- คัดฉากเด่นจาก `sim.log` เต็ม (ไม่ใช่แค่ episodic 30 อันล่าสุด) ด้วยเกณฑ์เดียวกับ Phase 5
- reuse `story.biography()` เดิมเป็นโครงชีวประวัติ ไม่เขียนใหม่
- เรียกแยกหลังซิมจบ ไม่ผูกกับ `LLM_ENABLED` (ไม่มีซิมสดให้ช้าลง)
- รองรับ `--model` เพื่อสลับโมเดล Ollama ทดลองได้

---

## ส่วนที่ 3 — Narrative Dataset Factory (ตาม `ROLE (1).md`, ทำเป็น 6 เฟส A-F)

ทุกเฟสอยู่ในโฟลเดอร์ `narrative_factory/` (แยกจาก `tiandao/ai/` แต่ **reuse `tiandao/ai/memory.py` +
`tiandao/ai/llm_agent.py` เต็มที่** ตามที่ ROLE (1).md บอกว่าโปรเจกต์มี Memory อยู่แล้ว) ทำงานแบบ
offline ทั้งหมด — โหลดโลกที่เซฟไว้แล้วมาแปลงเป็น dataset ไม่รบกวนซิมสดเลย

### Phase A — Event Parser
`narrative_factory/parser.py`, `narrative_factory/config.yaml`
- `sim.log` → `ParsedEvent` พร้อม `scene_type` มาตรฐาน (Breakthrough/Duel/Betrayal/Treasure/SectWar/
  Death/Escape/PillCraft/Auction/Robbery/Invasion/Other) แมปจาก config.yaml ทั้งหมด ไม่ hardcode

### Phase B — Scene Extraction + Narrative Genome
`narrative_factory/scene_extractor.py`, `narrative_factory/genome.py`
- คลัสเตอร์เหตุการณ์ที่มีผู้เล่นร่วมกันและห่างกัน ≤3 วัน (config) ให้เป็นฉากเดียว
- **Narrative Genome** (ไอเดียที่ผู้ใช้เสนอ) ครบ 5 field: `scene_type` (จริงจาก log), `conflict_level`
  (จาก `margin` จริงของการต่อสู้ — ดูปัญหาข้อ 1 ด้านล่าง), `dao_theme` (=`ch.dao` ตรงๆ), `emotion_curve`
  (**"narrative pacing template" เลือกจาก scene_type/win-loss — ไม่ใช่ค่าที่วัดจริง** เพราะเอนจินเป็น
  discrete-event ไม่มี sub-beat ให้วัด — ตกลงกับผู้ใช้แล้วว่ายอมรับแนวทางนี้), `foreshadowing` (ค้นย้อน
  หลังใน log จริงของตัวละครเดียวกัน คืนข้อความจริงเท่านั้น ไม่เจอ = ว่างเปล่า ไม่แต่งเติม)

### Phase C — Character Context Builder + Memory Retriever
`narrative_factory/context_builder.py`, `narrative_factory/memory_retriever.py`
- ประกอบ Realm/Dao/Personality/Relationship/Reputation/Current Goal/Emotion — reuse
  `tiandao/ai/memory.py` (relationship/reputation) และ `tiandao/ai/llm_agent.py:infer_emotion` เต็มที่
- **Current Goal**: ไม่ใช้ `brain.current_goal` (snapshot ท้ายซิม) ใช้ scene_type ของฉากเองแทน (กราวด์
  กับฉาก 100%)
- **Reputation**: replay `update_reputation()` ย้อนหลังเฉพาะก่อนวันของฉาก ไม่ใช้ยอดสะสมท้ายซิม
- **Relationship**: ยอมรับว่ายังเป็น end-state ปัจจุบัน (เอนจินไม่ได้เก็บตัวเลขที่บวกแต่ละครั้งไว้ให้
  replay ได้แบบ reputation) — ทำเครื่องหมาย `relationship_source="current"` ไว้เสมอ
- Memory Retriever ให้คะแนนความเกี่ยวข้อง (คนร่วมฉาก/สถานที่เดียวกัน/ศัตรู) ก่อนความใหม่ ตัดตาม token
  budget จริง

### Phase D — Quality Validator + Scoring
`narrative_factory/validator.py`, `narrative_factory/scoring.py`
- 6 กฎของ ROLE.md ครบ: No New Characters / No Fabricated Events / Timeline Order / Names Exact /
  Realm Matches / Relationship Matches — **เป็นประตูแข็งเสมอ** ผิดข้อไหนก็ reject ทันที ไม่ว่าคะแนน
  รวมจะยังถึงเกณฑ์หรือไม่ (แก้บั๊กจริงที่เคย conflate ทั้งสองระบบเข้าด้วยกัน)
- Quality Scoring 5 metric ตามน้ำหนักของ ROLE.md (Timeline 25/Character 25/Event 20/Memory 15/
  Style 15, <80 = reject) — Style Quality เช็คอักษรจีนหลุดปนด้วย (บั๊กจริงที่เจอจาก Phase 6)

### Phase E — Dataset Export
`narrative_factory/exporter.py`, `narrative_factory/tagger.py`, `narrative_factory/versioning.py`,
`build_dataset.py`
- 5 dataset ตาม ROLE.md: Scene SFT (A) / Dialogue (B) / Internal Monologue (C) / World Chronicle (D)
  / Planning (E) → `.jsonl` ที่ `datasets/v{N}/` + `metadata.json`
- ค่าเริ่มต้นใช้ **template แบบเรียบ** (เรียง `event.text` จริงต่อกัน ไม่แต่งคำใหม่) เป็น output ของ
  Dataset A — กราวด์ 100% เปิด `--llm` ให้ Ollama เขียนจริงแทนได้ แต่ต้องผ่าน Phase D gate เสมอ
  (reject แล้ว fallback กลับ template ไม่ทิ้ง record)
- Dataset B/C (Dialogue/Monologue) ใช้ได้เฉพาะฉากที่มี `brain.narrative_moments` จริงอยู่แล้ว (จาก
  รันซิมด้วย `--llm` มาก่อน — Phase 5) **ไม่สร้างใหม่ที่ export time** (ขอบเขตตั้งใจ — ถ้าโลกไม่เคยรัน
  ด้วย `--llm` เลย Dataset B/C จะว่างเปล่า ถูกต้องแล้ว ไม่ใช่ error)
- Dataset E (Planning) เฉพาะฉาก Breakthrough — mirror `tiandao/ai/goap.py:FIND_PILL_METHODS` แต่คำนวณ
  ย้อนหลังจาก log จริง (ไม่ใช่ live state)

### Phase F — Incremental Learning
`narrative_factory/incremental.py`
- เก็บ high-water-mark (`last_exported_seq`) ที่ `datasets/export_state.json` — export ครั้งถัดไปคัด
  เฉพาะฉากใหม่ (มีเหตุการณ์ seq สูงกว่าที่เคย export) — `v{N}` แต่ละอันเป็น **ส่วนเพิ่ม (delta)** ต้อง
  เอา v1..vN มารวมกันถึงจะได้ dataset เต็ม
- `--full` บังคับ re-export ทั้งก้อนถ้าต้องการ snapshot เต็มสักครั้ง
- **ทดสอบเต็มวงจรแล้ว**: v1 (1,804 ฉาก) + v2 (1,869 ฉากใหม่หลัง daemon เดินต่อ) = 3,673 ฉาก ตรงกับ
  `--full` v3 (3,673 ฉาก) เป๊ะ — พิสูจน์ว่าการแบ่ง delta ถูกต้องสมบูรณ์ ไม่ขาดไม่เกิน

**คำสั่งที่ใช้ได้จริงตอนนี้:**
```bash
python run.py --seed 1 --events 20000 --save         # ให้โลกมีประวัติก่อน
python build_dataset.py                               # export v1 (ครั้งแรก = ฉากทั้งหมด)
python daemon.py --chunk-events 20000 --iterations 5   # ให้โลกโตขึ้นอีก
python build_dataset.py                               # export v2 (เฉพาะฉากใหม่ — incremental)
python build_dataset.py --full                         # บังคับ snapshot เต็มทั้งก้อน
python build_dataset.py --llm --llm-limit 5            # ให้ Ollama เขียน Dataset A จริงบางส่วน
```

---

## ส่วนที่ 4 — Closed-Loop Self-Learning Flywheel (ตาม `ROLE (2).MD`, ทำครบ Phase G-J)

`ROLE (2).MD` เป็น roadmap 4 เฟส (G-J) ปิดลูป Dataset→Fine-tune→Model ใหม่→ขับเคลื่อน Sim/Story —
**ตรวจสอบกับโค้ดจริงก่อนแก้ไขเอกสารนั้นเอง** พบว่า roadmap อ้างถึงความสามารถบางอย่างที่ยังไม่มีจริง
(เกณฑ์คะแนน 85 ที่ต่างจาก `PASS_THRESHOLD=80` จริงในโค้ด, "rejected data" ที่ยังไม่มีที่เก็บ ฯลฯ) —
แก้ไขเอกสารพร้อมหมายเหตุจุดเหล่านั้นไว้แล้วก่อนเริ่มทำ Phase G จริง

ก่อนเริ่ม Phase G แก้ **จุดที่ไม่ deterministic** (ดูปัญหาข้อ 4 เดิม) ก่อนเป็นอันดับแรกตามที่ roadmap
เองแนะนำ — บรรทัดเดียว (`random.choice`→`self.rng.choice`) ยืนยันแล้วว่ารัน seed เดิมซ้ำได้ผลเหมือนกัน
ทุกตัวเลข 100% (ก่อนหน้านี้ไม่เหมือนกัน — 8689 vs 8641 เหตุการณ์จาก seed เดียวกัน)

### Phase G — Async Log & Queue Engine
`tiandao/event_log.py`, `tiandao/ai/llm_queue.py`

**G1 — แยก `sim.log` ออกจาก `world.save`** (แก้ปัญหาข้อ 3 เดิม):
- `sim.log` (in-memory) ยังทำงานเหมือนเดิมทุกจุดที่ใช้อยู่แล้ว — เป็นการ**เสริม** ไม่ใช่แทนที่
- `daemon.py` ได้ `--keep-recent-events` (ดีฟอลต์ 5000) / `--event-log-path` / `--no-trim-log` — หลัง
  แต่ละ chunk จะ flush เหตุการณ์เก่าลง `{save_path}.events.jsonl` (append-only) แล้วตัด `sim.log` ใน
  หน่วยความจำ/ที่จะ pickle เหลือแค่ N ล่าสุด
- `run.py` **ไม่แตะเลย** โดยตั้งใจ (ไม่ใช่จุดที่เจอปัญหาจริง — รันสั้นกว่ามาก) — ยืนยันแล้วว่าไม่สร้าง
  ไฟล์ sidecar เลย พฤติกรรมเดิม 100%
- `narrative_factory/parser.py`, `tiandao/ai/history.py` (+`generate_episode.py`) อัปเดตให้ merge
  ประวัติเก่า (จาก sidecar) กับของใหม่ (จาก `sim.log`) อัตโนมัติผ่าน `event_log.full_log()` — ตามที่
  เตือนตัวเองไว้ใน `ROLE (2).MD` ว่าต้องแก้จุดนี้ด้วย ไม่ใช่แค่ `persist.py`
- **ทดสอบจริง**: daemon 3 รอบ (`--keep-recent-events 2000`) → `world.save` คงที่ ~3.2MB (ไม่โตต่อ),
  `.events.jsonl` สะสม 9,820 เหตุการณ์ครบ (3254+3287+3279 ตรงเป๊ะ) → `build_dataset.py` reconstruct
  ประวัติเต็มถูกต้อง **1,065 ฉากจากช่วงต้น (day<2459) ยังอยู่ครบ** ไม่หายไปแม้ถูกตัดออกจาก `world.save`

**G2 — คิว LLM แบบไม่บล็อก sim loop** (แก้ปัญหาที่ระบุในปัญหาข้อ 2 เดิม/Pillar 4 ของ roadmap):
- `BrainManager.on_event()` เปลี่ยนจากเรียก Ollama ทันที เป็นแค่ `enqueue()` (แทบไม่เสียเวลา)
- เพิ่ม `drain_llm_queue(sim, budget)` ให้ `run.py`/`daemon.py` เรียกแยกทีหลัง — `daemon.py` มี
  `--llm-drain-budget` (ดีฟอลต์ 20) ควบคุมว่าจะประมวลผลกี่งาน/รอบ งานที่เหลือรอรอบถัดไปเอง (พร้อม
  pickle ไปกับ save ได้เลยเพราะเป็น plain data)
- **ทดสอบจริงวัดเวลาแยก**: `sim.run(500)` ที่เปิด `LLM_ENABLED=True` ใช้เวลาแค่ **0.13 วินาที** (คิวไว้
  170 งาน) เทียบกับของเดิมที่บล็อกจนจบ (8 นาที 35 วินาทีสำหรับ 500 เหตุการณ์) — `drain_llm_queue(budget=3)`
  ใช้เวลา 10.13 วินาทีสำหรับ 3 งาน (~3.4s/ครั้ง ตรงกับที่เคยวัดไว้) — **sim loop ไม่ขึ้นกับความเร็ว
  Ollama อีกต่อไปจริง** (ต้นทุนรวมเท่าเดิม แค่ไม่บล็อกระหว่างเดินอีกต่อไป)
- backward-compat: เพิ่ม `BrainManager.__setstate__` (ไม่เคยมีมาก่อน แม้จะเพิ่ม `_agent` ไปตั้งแต่
  Phase 5 แล้วก็ตาม — เป็นช่องโหว่แฝงที่เจอและแก้พร้อมกันตอนเพิ่ม `llm_queue`)

**คำสั่งที่ใช้ได้จริงตอนนี้:**
```bash
python daemon.py --keep-recent-events 5000                        # G1: log ไม่บวมไม่มีเพดานอีกต่อไป
python daemon.py --llm --llm-drain-budget 20                       # G2: เปิด Layer 3 ไม่บล็อก sim
python build_dataset.py --event-log-path tiandao/world.save.events.jsonl   # ได้ประวัติเต็มแม้ trim แล้ว
```

### Phase H — Self-Fine-Tuning Worker (Auto-Trainer / QLoRA)

**เป้าหมาย**: ปิด Pillar สุดท้ายที่ยังขาดของ Flywheel — เอา dataset ที่ export ไว้ (Phase F) มาเทรน LoRA
จริงบน GPU เครื่องนี้เอง ไม่ใช่แค่ export แล้วจบ

**ไฟล์ใหม่ 3 ไฟล์**:
- `narrative_factory/dataset_formatter.py` — แปลง Dataset A-E (จาก `exporter.py`) เป็น ChatML
  `{"messages": [...]}` เดียวกันหมด (Multi-Task Training ตาม `ROLE (2).MD` Pillar 1) — `_fmt_scene_sft`/
  `_fmt_dialogue`/`_fmt_monologue`/`_fmt_chronicle`/`_fmt_planning` ต่อ dataset, record ที่ผิดรูปแบบ
  ถูกข้ามเฉยๆ ไม่ทำให้ทั้งก้อนล้ม — **ข้อจำกัดที่รู้อยู่แล้ว**: ถ้าไม่เคยรันซิมด้วย `--llm` มาก่อน
  Dataset B/C จะว่าง (ดูปัญหาข้อ 6) ทำให้ Multi-Task กลายเป็น "Task A+D+E เท่านั้น" โดยอัตโนมัติ
- `train_lora.py` — ตัวเทรนจริง (`ChatDataset` mask label ส่วน system+user เป็น `-100` เทรน loss
  เฉพาะคำตอบ assistant, `train()` โหลดโมเดล 4-bit ผ่าน `BitsAndBytesConfig` แล้วติด LoRA ด้วย
  `peft.LoraConfig(r=16, lora_alpha=32, target_modules=[q/k/v/o_proj, gate/up/down_proj])`, เทรนด้วย
  `transformers.Trainer` ธรรมดา)
- `autotrain.py` — ตัวสั่งเทรนอัตโนมัติ (Phase H trigger) เช็ค `datasets/export_state.json` (Phase F)
  ว่าฉากใหม่สะสมครบ `--threshold` หรือยัง (ดีฟอลต์ 2000 ตาม `ROLE (2).MD`) ถ้าครบ (หรือใส่ `--force`)
  ถึงเรียก `train_lora.train()` จริง แล้วบันทึก high-water-mark ของตัวเองแยกไว้ที่
  `datasets/train_state.json` (คนละหน้าที่กับ `export_state.json` — Phase F track "export ไปถึงไหน",
  ไฟล์นี้ track "เทรนไปถึงไหน" กันเทรนซ้ำข้อมูลเดิม)

**การตัดสินใจสำคัญที่ต่างจาก `ROLE (2).MD`**: roadmap แนะนำ Unsloth/TRL แต่เครื่องนี้ใช้ torch nightly
build (`2.12.0.dev20260408+cu128`) ซึ่งทั้งคู่ยังไม่ประกาศรองรับอย่างเป็นทางการ (และไม่ได้ติดตั้งไว้ด้วย)
— เลือกใช้ `transformers` + `peft` + `bitsandbytes` ตรงๆ แทน (ยืนยันแล้วว่าใช้งานได้จริงบนเครื่องนี้) พร้อม
เขียน `ChatDataset`/collator เองมาทำหน้าที่ prompt-masking ที่ปกติ `SFTTrainer` ของ TRL จะทำให้ — ผลลัพธ์
QLoRA แบบเดียวกัน แค่ไม่ใช้ library ที่ยังไม่ผ่านการตรวจสอบความเข้ากันได้กับ nightly build นี้

**ทดสอบจริงเต็มรูปแบบบน RTX 5060 Ti (เครื่องเป้าหมายจริงตาม `ROLE.md`, 16311 MiB VRAM) — ไม่ใช่ mock**:
1. Export dataset จริง → 1,731 ฉาก → format เป็น 1,957 ตัวอย่าง ChatML (`dataset_formatter.py`)
2. ดาวน์โหลด `Qwen/Qwen2.5-7B-Instruct` จริงจาก HuggingFace (โมเดลเป้าหมายจริงตาม `ROLE (2).MD` ไม่ใช่
   ตัวเล็กทดแทน — ผู้ใช้เลือกเองว่ายอมรอ ~15GB/~37 นาที แทนที่จะข้ามการทดสอบจริง)
3. โหลดแบบ 4-bit + ติด LoRA สำเร็จ: **40,370,176 / 7,655,986,688 พารามิเตอร์ที่เทรนได้ (0.53%)**
4. เทรนจริง 5 step (`--max-steps 5` จำกัดเวลาไว้ตามที่ตกลง): **loss ลดจาก 2.314 → 0.334** ต่อเนื่องทุก
   step ใช้เวลารวม 23.2 วินาที (ยืนยันว่า gradient ไหลจริง ไม่ใช่ loss คงที่/NaN)
5. บันทึก LoRA adapter จริงที่ `loras/v1/adapter_model.safetensors` (161.5MB) + `autotrain.py` อัปเดต
   `datasets/train_state.json` ถูกต้อง (`last_trained_scene_count`/`history` มี record ใหม่)

**คำสั่งที่ใช้ได้จริงตอนนี้:**
```bash
python autotrain.py --check                              # เช็คฉากสะสมใหม่ ไม่เทรนจริง
python autotrain.py --threshold 2000                      # เทรนถ้าครบโควต้า (ค่าเริ่มต้นตาม ROLE (2).MD)
python autotrain.py --force --max-steps 5                 # smoke test เทรนทันทีไม่สนโควต้า จำกัด step
```

### Phase I — DPO Pair Builder

**เป้าหมาย**: ปิดช่องว่างที่ `ROLE (2).MD` เตือนไว้ก่อนเริ่ม Phase นี้ — `exporter.py` เดิมทิ้ง candidate
ที่ Phase D ปฏิเสธไปเฉยๆ ไม่มีที่เก็บ ทำให้ไม่มีวัตถุดิบฝั่ง "Rejected" ให้สร้างคู่ DPO ได้เลย

**อุดช่องว่างใน `exporter.py` ก่อน (ตามที่ระบุไว้ว่าเป็นส่วนหนึ่งของ Phase I เอง ไม่ใช่ของที่มีอยู่แล้ว)**:
- `_validated_or_fallback()` เปลี่ยนคืนค่าเป็น `CandidateOutcome` (dataclass ใหม่: `text`, `used_llm`,
  `score`, `rejected_text`, `rejected_violations`) แทน tuple เดิม — เก็บทั้งคะแนนและ violations ของ
  candidate ที่ reject ไว้ครบ ไม่ทิ้งอะไรไปแล้ว
- `build_dataset_a()` คืน `(record, rejected_record)` — `record` เพิ่ม `_meta.score` (ของเดิมมีแค่
  `used_llm`) ส่วน `rejected_record` (None ถ้าไม่มีการ reject) มี `instruction`/`input` ชุดเดียวกับ
  `record` (เพื่อให้ Phase I เทียบ prompt ตรงกันได้แน่นอน) บวก `rejected_output`/`score`/`violations`
- `export_all()` เขียนไฟล์ใหม่ **`rejected_candidates.jsonl`** คู่กับ `scene_sft.jsonl` ในทุกเวอร์ชัน
  (ว่างเปล่าได้ถ้าไม่มี candidate ไหนถูก reject ในรอบนั้น — เขียนไฟล์เปล่าเสมอ ไม่ข้าม เพื่อให้ Phase I
  glob หาไฟล์ได้แน่นอนไม่ต้องเช็ค exists เป็นพิเศษ)

**เกณฑ์คะแนนใหม่**: `narrative_factory/config.yaml` เพิ่ม `dpo_chosen_threshold: 85` (**ไม่แก้**
`scoring.PASS_THRESHOLD = 80` เดิมที่ Dataset A-E ใช้อยู่ทุกวันนี้ ตามที่ `ROLE (2).MD` เตือนไว้ตรงๆ) —
"Chosen" ของ DPO ต้องผ่าน Phase D 100% และคะแนน >= 85 ส่วน "Rejected" คือ candidate ที่ Phase D
ปฏิเสธจริง (ละเมิดกฎข้อใดข้อหนึ่งใน 6 ข้อ)

**ไฟล์ใหม่**:
- `narrative_factory/dpo_builder.py` — `collect_candidates()` สแกน**ทุกเวอร์ชัน**ใน `datasets/`
  (v1..vN) รวบรวม chosen (คะแนน>=85) และ rejected ต่อ `scene_id`, `build_pairs()` จับคู่เฉพาะ scene_id
  ที่มีทั้งสองฝั่งจริง (เทียบ prompt ให้ตรงกันเป๊ะก่อนจับคู่ ป้องกันจับคู่ผิด) คู่ละหนึ่งต่อฉาก
  (chosen คะแนนสูงสุด + rejected คะแนนต่ำสุด — ไม่จับคู่ไขว้ทุกคู่ที่เป็นไปได้), `run()` เขียนรวมเป็น
  `datasets/dpo_pairs.jsonl` (overwrite ทุกครั้ง ไม่ incremental เหมือน Phase F เพราะข้อมูลตั้งต้นน้อยกว่ามาก)
- `build_dpo_pairs.py` — CLI root ระดับเดียวกับ `build_dataset.py` ไม่เรียก Ollama เลย แค่ประกอบไฟล์ที่
  export ไว้แล้ว

**ข้อจำกัดสำคัญที่ต้องรู้**: หนึ่งฉากได้ candidate จาก LLM แค่ตัวเดียวต่อการ export หนึ่งครั้ง คู่
Chosen/Rejected ของ scene_id เดียวกันจะเกิดขึ้นได้จริงก็ต่อเมื่อ export ด้วย `--llm --full` มากกว่าหนึ่ง
ครั้ง (Ollama ตอบไม่เหมือนเดิมทุกครั้งแม้ scene เดียวกัน) — ไม่งั้น `dpo_pairs.jsonl` จะว่างเปล่า (ถูกต้อง
แล้ว ไม่ใช่ error เหมือนหลักการเดียวกับ Dataset B/C)

**ทดสอบจริง (ไม่ mock validator/scoring/context_builder เลย)**:
1. รัน `build_dataset.py --llm --llm-limit 15 --full` บนโลกจริง (`tiandao/world.save`, 1,731 ฉาก) สอง
   รอบติดกันจริงผ่าน Ollama (`qwen2.5vl:7b`) — **ผลจริง: 30/30 candidate ผ่าน Phase D หมด (คะแนน
   90-100 ทุกตัว ไม่มี reject เกิดขึ้นเองเลยสักครั้ง)** — สรุปได้ว่าโมเดลนี้กับงาน "เรียบเรียง
   เหตุการณ์จริงเป็นร้อยแก้วสั้นๆ" (prompt เข้มงวดเรื่องห้ามแต่งเติม) แทบไม่หลุด 6 กฎเลยในทางปฏิบัติ —
   ต่างจาก Phase 6 History Generator (เขียนทั้งตอนยาว อิสระกว่ามาก) ที่เจอปัญหาหลอนชัดเจนกว่า
2. เพราะไม่มี reject เกิดเองตามธรรมชาติ จึงทดสอบท่อ reject→pair แบบควบคุมได้แทน (เทียบเท่าวิธีที่ Phase D
   เคยพิสูจน์ตัวเองด้วย `pipeline.py --phase-d-demo`): ยิง candidate ปลอมที่รู้อยู่แล้วว่าต้องผิด Rule2
   (อ้าง "วันที่ 999999" ที่ไม่มีจริง) ผ่าน `export_all()` ตัวจริงเข้าไปตรงๆ (ของจริงทั้ง sim/scene/
   validator/scoring มีแค่ "คำตอบ LLM" ที่จำลอง) — **ยืนยันจริงว่า `rejected_candidates.jsonl` บันทึก
   ถูกต้อง** (`Rule2_NoFabricatedEvents` + `Rule3_TimelineOrder` ทั้งคู่ตามที่ควรจะเป็น) แล้วรัน
   `build_dpo_pairs.py` จับคู่กับ chosen จริงคะแนน 100 ของ scene เดียวกันจากรอบก่อนหน้าได้สำเร็จ —
   **ได้คู่ DPO จริง 1 คู่** ที่ prompt ตรงกันเป๊ะ, chosen เป็นร้อยแก้วจริงจาก Ollama, rejected เป็น
   ข้อความที่ระบุ violation ชัดเจน — พิสูจน์ว่า pipeline ทั้งสายทำงานถูกต้อง (ข้อมูลทดสอบนี้ลบทิ้งแล้ว
   หลังพิสูจน์เสร็จ ไม่ทิ้งไว้ปนกับ dataset จริง)

**บั๊กจริงที่เจอระหว่างทดสอบ (แก้แล้ว)**: `build_dataset.py --full` เดิมยังคงเรียก
`INC.record_export()`/`INC.save_state()` หลัง export เหมือน incremental mode ปกติ ทั้งที่ข้อความ CLI
เองบอกว่า "--full ไม่สน state เดิม" — ผลคือรัน `--full` ซ้ำสองครั้ง (ตามที่ Phase I แนะนำให้ทำเพื่อสะสม
Chosen/Rejected) ทำให้ `datasets/export_state.json` นับฉากเดิม 1,731 ฉากซ้ำเป็น "ฉากใหม่" ทุกรอบ ทำให้
`accumulated_scene_count()` ของ `autotrain.py` (Phase H) พองเกินจริง (พิสูจน์แล้ว: จาก 1,731 กลายเป็น
3,462 หลัง `--full` แค่สองครั้ง) เป็นไปได้ที่จะไป trigger auto-train ก่อนที่ข้อมูลใหม่จริงจะครบโควต้า —
แก้โดยให้ `--full` ข้าม `INC.record_export`/`INC.save_state` ไปเลย (เป็น ad-hoc snapshot แยกต่างหาก
ไม่นับสะสม ตามเจตนาเดิมของ flag นี้จริงๆ) ยืนยันแล้วว่า incremental mode ปกติ (ไม่ใส่ `--full`) ยังนับ
ถูกต้อง 100% เหมือนเดิม

**คำสั่งที่ใช้ได้จริงตอนนี้:**
```bash
python build_dataset.py --llm --llm-limit 20 --full   # export รอบแรก (chosen/rejected ปนกันถ้ามี)
python build_dataset.py --llm --llm-limit 20 --full   # export รอบสอง (Ollama สุ่มคำตอบใหม่ต่อฉากเดิม)
python build_dpo_pairs.py                               # จับคู่ scene_id ที่มีทั้งสองฝั่งจริง
```

### Phase J — Model Evaluator & Hot-Swap

**เป้าหมาย**: ปิด Phase สุดท้ายของ `ROLE (2).MD` — ตรวจคุณภาพ LoRA ที่เทรนได้ก่อนอนุมัติ deploy จริง
(Shadow Evaluation Gate) แล้วถ้าอนุมัติค่อยสลับเข้า Ollama ใช้งานจริง (Hot-Swap) ไม่ให้โมเดลที่แย่กว่า
เดิมเข้าไปแทนที่โดยไม่มีใครตรวจ

**ข้อค้นพบจริงที่เปลี่ยนแนวทางตั้งแต่ต้น**: Ollama เวอร์ชันนี้ (0.33.2) มี `--experimental` (native
safetensors model creation) ที่เผื่อไว้จะได้ไม่ต้องพึ่ง GGUF เลย — **ตรวจสอบจริงแล้วพบว่าไม่รองรับ
Qwen2/Qwen2.5** (รองรับแค่ Llama/Mistral/Gemma/Phi3 ทั้งฝั่ง `FROM` safetensors dir และฝั่ง `ADAPTER`
safetensors LoRA) ซึ่งเป็นสถาปัตยกรรมที่โปรเจกต์นี้ใช้จริงตาม `ROLE.md`/`ROLE (2).MD` (`Qwen2.5-7B-
Instruct`) — เท่ากับต้องแปลง GGUF จริงตามที่ roadmap เขียนไว้เดิม เครื่องนี้ไม่มี `llama.cpp`/`gguf`
ติดตั้งอยู่เลย (เช็คแล้วทั้ง pip และทั้งเครื่อง) **ถามผู้ใช้ก่อนตัดสินใจ** เพราะต้องดาวน์โหลดโค้ดจาก
GitHub ของ llama.cpp มารันบนเครื่อง — ผู้ใช้เลือก "เต็มรูปแบบจริง"

**เครื่องมือที่ vendor เข้ามา (ได้รับอนุญาตจากผู้ใช้แล้ว)**: `vendor_llama_cpp_convert/` — sparse clone
เฉพาะ `convert_hf_to_gguf.py` + `convert_lora_to_gguf.py` + `gguf-py/` + `conversion/` (แพ็กเกจ
mapping สถาปัตยกรรมที่ script ใหม่แยกออกมา รวม `conversion/qwen.py` ที่รองรับ Qwen2 อยู่แล้ว) จาก
`github.com/ggml-org/llama.cpp` (MIT license) — ไม่ clone ทั้ง repo (แค่ ~3MB ไม่ใช่ทั้งโปรเจกต์)
ไม่ต้อง build C++ ใดๆ (เป็นสคริปต์ Python ล้วน ใช้ `torch`/`gguf-py` ที่ bundle มาเอง) — เพิ่ม
`sentencepiece` เป็น pip dependency ใหม่หนึ่งตัว ไม่มีอย่างอื่นต้องติดตั้งเพิ่ม — เข้า `.gitignore`
แล้ว (`vendor_llama_cpp_convert/`, `merged/`, `*.gguf`) ไม่ใช่โค้ดของโปรเจกต์เอง

**ไฟล์ใหม่**:
- `narrative_factory/shadow_eval.py` — `load_model_for_eval()`/`generate_for_scenes()` (โหลดโมเดล
  4-bit เหมือนตอนเทรน generate จริงด้วย prompt เดียวกับ ChatML ตอนเทรนเป๊ะ — refactor
  `dataset_formatter.py` ให้มี `build_scene_messages()` ใช้ร่วมกันทั้งสองที่ ไม่ให้ prompt ตอนเทรน/
  ตอนประเมินเพี้ยนไปคนละแบบ), `score_outputs()` (ยิงผ่าน Phase D validator/scoring ตัวจริงตัวเดียวกับ
  `exporter.py`/Phase I ใช้), `run_eval()` รวมทุกอย่าง + คืน VRAM ให้โมเดลตัวถัดไปโหลดได้
- `evaluate_model.py` — CLI เทียบ candidate LoRA vs baseline (โมเดลฐานเปล่า หรือ LoRA เวอร์ชันก่อนหน้า)
  บน N ฉาก benchmark (สุ่มด้วย seed คงที่ให้เทียบซ้ำได้) อนุมัติก็ต่อเมื่อ `mean_score` ของ candidate
  >= baseline เท่านั้น บันทึกผลละเอียดที่ `datasets/eval_results/eval_{timestamp}.json` และ exit
  code 0/1 ให้ script อื่นเช็คได้
- `merge_lora.py` — merge LoRA adapter เข้าน้ำหนักจริงของ base model **แบบ bf16 เต็ม บน CPU**
  (ไม่ใช่ 4-bit เหมือนตอนเทรน — merge บนโมเดล quantized จะได้ผลไม่ตรง ต้องโหลดแบบเต็มความละเอียด
  แยกต่างหาก, CPU เพราะ VRAM การ์ดนี้ไม่พอโหลด bf16 เต็ม 7.65B ระหว่าง merge)
- `hotswap.py` — orchestrator: เช็ค Shadow Evaluation Gate (`--eval-result` ต้อง `approved: true` ไม่งั้น
  ปฏิเสธ เว้นแต่ `--force`) → `merge_lora.py` → `convert_hf_to_gguf.py` (subprocess) → `ollama create
  -q q4_K_M` → `ollama cp ... cultivator-brain:latest` (ข้ามได้ด้วย `--no-latest` สำหรับทดสอบท่อเฉยๆ)

**ทดสอบจริงเต็มรูปแบบ (ไม่ mock อะไรเลยแม้แต่ขั้นเดียว)**:
1. **Shadow Evaluation Gate จริง**: เทียบ `loras/v1` (จาก Phase H) กับโมเดลฐานเปล่า บน 15 ฉากจริงที่สุ่ม
   จากโลกจริง โหลด/generate/ให้คะแนนจริงทั้งคู่ผ่าน `transformers`+Phase D validator — **ผลจริง:
   baseline mean_score=98.7 pass_rate=100% ในขณะที่ candidate (loras/v1) mean_score=79.7
   pass_rate=0%** → **REJECT** จริง (ไม่ได้ตั้งใจให้ผ่าน แต่ผลนี้สมเหตุสมผล 100%: `loras/v1` เทรนแค่
   5 step เพื่อ smoke test ตาม `ROLE (2).MD` ตามที่ผู้ใช้เลือกไว้ตอน Phase H ("จำกัด step") ไม่ใช่เทรน
   จนลู่เข้าจริง — **นี่คือ Gate ทำงานถูกต้องตามที่ควรจะเป็น** ป้องกันไม่ให้โมเดลที่ยังไม่พร้อมเข้าไป
   แทนที่ของเดิม)
2. เพราะ Gate ปฏิเสธ v1 จึงไม่ deploy จริง (การทำแบบนั้นจะขัดกับ Gate ที่เพิ่งพิสูจน์ว่าทำงานถูกต้อง)
   — แต่ยังต้องพิสูจน์ว่าท่อ merge→GGUF→ollama create เชิงกลไกใช้งานได้จริงหรือไม่ (ไม่เคยรันมาก่อนเลย)
   จึงรัน `hotswap.py --force --no-latest` (ข้าม gate โดยตั้งใจเพื่อทดสอบท่อเท่านั้น ไม่ผูกกับ
   `cultivator-brain:latest`): **merge LoRA เข้า Qwen2.5-7B-Instruct เต็มจริง (bf16, CPU) → แปลง GGUF
   จริงด้วย `convert_hf_to_gguf.py` (bf16, ~15GB) → `ollama create -q q4_K_M` จริง → ได้
   `cultivator-brain:v1-pipelinetest` ขนาด 4.7GB ใน Ollama จริง** ใช้เวลารวม 11 นาที 11 วินาที —
   `ollama run cultivator-brain:v1-pipelinetest` สร้างข้อความไทยที่อ่านออกได้จริง (ไม่ crash ไม่ garbage)
   ยืนยันว่าท่อทั้งสายทำงานถูกต้องทางเทคนิค — ลบโมเดลทดสอบ + ไฟล์ merge/GGUF ตัวใหญ่ทิ้งแล้วหลังพิสูจน์
   เสร็จ (คืนดิสก์ 29GB) เก็บไว้แค่ผลประเมิน JSON ที่มีความหมายจริง

**สรุปสถานะ Phase J**: โครงสร้างพร้อมใช้งานจริง 100% (Gate ทำงานถูกต้อง ท่อ hot-swap ทำงานถูกต้อง) แต่
ยังไม่มี LoRA เวอร์ชันไหนผ่าน Gate จริงสักตัว (เพราะ `loras/v1` เป็นแค่ smoke test 5 step) — ต้องเทรน
จริงด้วย epoch/step มากพอ (ไม่ใช่ `--max-steps` แบบจำกัดเวลา) ก่อนถึงจะมีตัวที่ผ่าน Gate แล้ว
`hotswap.py` (ไม่ต้อง `--force`/`--no-latest`) จะ deploy เข้า `cultivator-brain:latest` จริงได้

**คำสั่งที่ใช้ได้จริงตอนนี้:**
```bash
python evaluate_model.py --candidate-lora loras/v1 --n-scenes 15    # Shadow Evaluation Gate จริง
python hotswap.py --adapter loras/v1 --version v1 \
    --eval-result datasets/eval_results/eval_xxx.json                # deploy จริงถ้า approved เท่านั้น
```

**ยังไม่ทำ**: ไม่มีแล้วจาก roadmap หลักทั้ง 3 ฉบับ (`ROLE.md`/`ROLE (1).md`/`ROLE (2).MD` Phase G-J
ครบทุก Phase) — สิ่งที่เหลือเป็น "ต้องเทรน LoRA จริงให้ผ่าน Gate" (งานข้อมูล/เวลา ไม่ใช่โค้ดที่ขาด) กับ
`tiandao/story.py`/`dashboard.py` ที่ยังไม่ได้อัปเดตให้ merge sidecar log เหมือนที่ทำกับ
`narrative_factory`/`history.py` (ขอบเขตที่ตัดไว้ตั้งแต่ Phase G — กระทบแค่ display/scoring ไม่ใช่
training data)

---

## ส่วนที่ 5 — Phase K: Narrative Teacher & Style Distillation (roadmap ใหม่, กำลังทำ)

เอกสารต้นทาง `C:\Users\user\Downloads\ROLE (3).MD` (เวอร์ชันล่าสุด — แทนที่เนื้อหาฉบับก่อนหน้าที่เป็น
"แผนปรับปรุง 4 หมวด" ไปแล้ว) เสนอ 7 sub-phase (K1-K7) ต่อยอดจาก Cultivator Brain v2 + Narrative
Dataset Factory ให้ LoRA เรียนรู้ "ศิลปะการเล่าเรื่อง" ไม่ใช่แค่ลำดับเหตุการณ์ — **Audit ก่อนเริ่ม
ตามที่เอกสารกำหนด**: ระบบเดิมที่เอกสารอ้างว่า "เสร็จแล้ว" ทั้งหมด (Persistence ถึง Hot Swap) และโมดูล
ที่ต้อง reuse (parser/genome/context_builder/validator/scoring/exporter) ตรวจแล้วมีอยู่จริงครบ ไม่มี
ชื่อไฟล์ใหม่ที่ชนกับของเดิม (`teacher.py`/`pacing.py`/`hook_detector.py`/`payoff_detector.py`/
`arc_builder.py`/`style_distill.py`/`lesson_exporter.py`) — **จุดขัดแย้งที่พบและถามผู้ใช้ก่อนเริ่ม**:
เอกสารเสนอ weight ชุดใหม่สำหรับ "Shadow Evaluation V2" (Timeline 20/Character 20/Event 15/Memory 10/
Style 20/Pacing 15, ผ่านที่ 85) ต่างจาก `scoring.py:WEIGHTS`/`PASS_THRESHOLD=80` ที่ Dataset A-E export
ใช้ตัดสิน pass/fail อยู่ทุกวันนี้ — **ผู้ใช้เลือกให้แทนที่ของเดิมทั้งหมด** (ต่างจาก Phase I ที่แยกค่าใหม่
ต่างหาก) จะทำตอนถึง section "SHADOW EVALUATION V2" ของ Phase K จริง (ต้องรอ K2-K6 มีให้คำนวณ Pacing
metric ก่อน ไม่ใช่ทำตอน K1)

### Phase K1 — Narrative Teacher

**ไฟล์ใหม่**: `narrative_factory/teacher.py` — `StoryLesson` dataclass (`scene_id`, `hook`,
`conflict`, `escalation`, `payoff`, `emotional_shift`, `pacing`, `lesson`) + `build_story_lesson(scene,
config)` เป็นเอนทรีพอยต์

**สิ่งที่ทำ (rule-based ล้วน ไม่ใช้ LLM เลย ตามที่ ROLE Phase K กำหนด "ห้ามแต่งเหตุการณ์ใหม่")**:
- `analyze_hook()`/`analyze_conflict()` — map จาก `scene_type` ผ่านตารางใหม่ใน `config.yaml`
  (`hook_by_scene_type`/`conflict_type_by_scene_type`) ตาม pattern เดียวกับ `goal_by_scene_type` เดิม
  ไม่ hardcode ใน Python — hook ใช้ scene_type ของ**เหตุการณ์แรก**ในฉาก (ไม่ใช่ anchor) เพราะ Hook คือ
  สิ่งที่ผู้อ่านเจอก่อน
- `analyze_escalation()` — เรียก `genome.compute_conflict_level()` ตัวเดียวกับที่มีอยู่แล้วต่อ**ทุก
  เหตุการณ์ในฉาก** (ของเดิมคำนวณแค่ anchor ตัวเดียวสำหรับ `NarrativeGenome.conflict_level`) แล้ว
  bucket เป็น Low(<25)/Medium(<50)/High(<75)/Peak(>=75) ให้เห็นการไต่ระดับจริงตามลำดับเวลา
- `analyze_payoff()` — reuse `scene.genome.foreshadowing`/`payoff` ที่มีอยู่แล้วตรงๆ (Expectation ->
  Result) ไม่คำนวณซ้ำ
- `analyze_emotional_shift()` — แปลง escalation ที่กราวด์แล้วเป็นคำอารมณ์ (Hope/Fear/Despair) คำที่
  ระดับ Peak ขึ้นกับผลแพ้ชนะ**จริง**ของเหตุการณ์สุดท้าย (`ev.deltas["winner"]` ผ่าน
  `scene_extractor._is_win_for()` ที่มีอยู่แล้ว) ไม่เดา — ไม่มีข้อมูลผลแพ้ชนะ (ไม่ใช่เหตุการณ์ต่อสู้)
  ใช้คำกลางๆ "Reckoning" แทน
- `analyze_pacing()` — ประมาณคร่าวๆจากความถี่เหตุการณ์ต่อช่วงวันจริง (เร็ว/ปานกลาง/ช้า/ทันที) — Beat
  breakdown เต็มรูปแบบเป็นหน้าที่ของ Phase K2 ตั้งใจเก็บไว้ที่นี่แค่ field ง่ายๆ ก่อน
- `build_lesson_text()` — ประกอบประโยคสรุปจาก field อื่นทั้งหมดล้วนๆ (string formatting ไม่ใช้ LLM
  เหมือน `exporter.py:_template_scene_prose()`)

**ทดสอบจริงบนโลกจริง (`tiandao/world.save`, ไม่ mock อะไรเลย)**:
1. รัน `build_story_lesson()` กับฉากจริงทั้งหมด **1,731/1,731 ฉาก — error 0 ฉาก**
2. ยืนยัน `escalation`/`emotional_shift` length ตรงกับจำนวนเหตุการณ์ในฉากทุกฉาก, field อื่นไม่ว่างเปล่า
   เลยสักฉาก
3. ตรวจฉากตัวอย่างจริงแยกตาม scene_type (Robbery/Auction/Escape/Death/Treasure/Betrayal) — ผลสมเหตุ
   สมผล เช่น scene_id=2-25 (Death, ล้างแค้นสำเร็จ) ได้ escalation=`['Peak']`, emotional_shift=
   `['Resolve']`
4. เจาะจงหาฉากหลายเหตุการณ์จริง (12/1,731 ฉากมีมากกว่า 1 เหตุการณ์ — ส่วนใหญ่ในโลกนี้เป็นฉากเหตุการณ์
   เดียว) และฉากที่มี foreshadowing จริง (199/1,731 ฉาก) — ทดสอบทั้งสองเส้นทางแล้วทำงานถูกต้อง (payoff
   ดึงข้อความ foreshadowing จริงจาก log มาต่อกับ payoff จริงถูกต้อง)

**ปัญหาที่เจอ**: ไม่มีบั๊กจริงที่ต้องแก้ — ข้อสังเกตเดียวคือฉากส่วนใหญ่ในโลกทดสอบนี้เป็นเหตุการณ์เดียว
(`scene_merge_window_days` เดิมทำให้ฉากส่วนใหญ่ไม่ merge กัน) ทำให้ escalation progression ข้ามหลาย
เหตุการณ์ยังไม่ได้เห็นตัวอย่างที่ชัดเจนมาก (ทดสอบฉากยาวสุดที่มี 2 เหตุการณ์ได้ผลถูกต้องเชิงเทคนิค
`['Low','Low']` แต่ไม่ใช่ตัวอย่างที่ tension ไต่ระดับสูงชัดๆ) — ไม่ใช่บั๊กของ Phase K1 เอง เป็นลักษณะ
ข้อมูลจริงของโลกที่ทดสอบ

**คำสั่งที่ใช้ได้จริงตอนนี้ (import แบบ Python เท่านั้น ยังไม่มี CLI แยก — รอ K7/lesson_exporter.py)**:
```python
from narrative_factory import parser as P, scene_extractor as SE, teacher as T
from tiandao import persist as PS, event_log as EL
sim = PS.load_sim("tiandao/world.save")
parsed = P.parse_log(sim, EL.default_log_path("tiandao/world.save"))
scenes = SE.extract_scenes(parsed, sim)
lesson = T.build_story_lesson(scenes[0])
```

### Phase K2 — Pacing Engine

**ไฟล์ใหม่**: `narrative_factory/pacing.py` — `assign_beats(n_events)` (แบ่ง Beat
Opening/Inciting/Rising/Peak/Aftermath จากจำนวนเหตุการณ์จริง), `build_scene_beats(scene)`,
`pacing_summary(beats)`

**การตัดสินใจสำคัญที่พบระหว่างออกแบบ**: `Peak` ต้องเป็นเหตุการณ์สุดท้ายของฉากเสมอ เพราะทั้งระบบ
(`genome.py`/`scene_extractor.py` ตั้งแต่ Phase B) นิยาม `scene.events[-1]` = anchor = ตัวตัดสิน
outcome/payoff ของฉากอยู่แล้ว — ผลคือ**โครงสร้างข้อมูลนี้ไม่มีที่ว่างให้ `Aftermath` จริงเลย** (เหตุการณ์
หลัง climax จะกลายเป็นฉากถัดไปแยกต่างหาก ไม่ใช่ event ในฉากเดียวกัน) บันทึกไว้ตรงๆ ใน docstring แทนที่จะ
ฝืนใส่ label ปลอมๆ ที่ไม่มีเหตุการณ์จริงรองรับ — `Aftermath` จะไม่ปรากฏในผลลัพธ์ไฟล์นี้เลยจนกว่าจะมี
Arc Builder (K5) ที่ดูข้ามหลายฉาก

**แก้ `teacher.py`**: `analyze_pacing()` เปลี่ยนจากฮิวริสติกเร็ว/ปานกลาง/ช้าแบบ K1 (ชั่วคราว) มาเรียก
`pacing.py` จริง คืน Beat chain เช่น "Rising -> Peak" แทน (ไม่ duplicate logic ตามกฎ Phase K)
`build_lesson_text()` ปรับข้อความให้เข้ากับ Beat chain แทนคำวิเศษณ์ไทยเดิม

**ทดสอบจริง**: unit-check `assign_beats(n)` สำหรับ n=0..7 ครบทุกกรณี (Peak อยู่ท้ายเสมอ, ไม่มี
Aftermath โผล่เลยสักครั้ง ตรงตามที่ออกแบบ) + รัน `build_story_lesson()` (ที่เรียก pacing.py จริงแล้ว)
กับฉากจริงทั้งหมด **1,731/1,731 ฉาก — error 0 ฉาก** ฉากยาวสุดจริง (0-644, 2 เหตุการณ์) ได้ Beat chain
"Opening -> Peak" ถูกต้องตามที่ออกแบบ

**ปัญหาที่เจอ**: ไม่มี — ข้อสังเกตเดิมจาก K1 ยังคงอยู่ (ฉากส่วนใหญ่ในโลกทดสอบนี้มีเหตุการณ์เดียว ทำให้
Beat chain ส่วนใหญ่เป็นแค่ `['Peak']` ยังไม่เห็นตัวอย่าง Beat 4-5 ขั้นจากข้อมูลจริงชัดๆ)

### Phase K3 — Hook Detector + Phase K4 — Payoff Detector

**ไฟล์ใหม่**: `narrative_factory/hook_detector.py` (`detect_hook(events, config)`),
`narrative_factory/payoff_detector.py` (`detect_payoff(scene)`) — refactor ออกจาก `teacher.py` (K1
ทำรวมไว้ชั่วคราวก่อน K3/K4 จะเสร็จตามที่บันทึกไว้ในรายงาน K1/K2) `teacher.py` แก้ให้เรียกทั้งสองไฟล์นี้
แทน ไม่มี logic ซ้ำอยู่สองที่

**K3 — ละเอียดกว่า K1 เดิม**: เพิ่มตาราง `hook_by_kind` ใน `config.yaml` (map จาก `event.kind` จริง
ตรงๆ เช่น "ประลอง"→Danger, "เปิดประมูล"→Opportunity, "ข้ามขั้น"→Desire, "ภัยธรรมชาติ"→World Event,
"ซ่อนตัว"→Mystery) ตรวจก่อน `hook_by_scene_type` เดิมของ K1 ซึ่งกลายเป็น fallback แทน (ไม่สร้างตาราง
fallback ซ้ำซ้อน)

**K4 — ปรับปรุงจาก K1 เดิม**: `detect_payoff()` ประกอบ Expectation จาก**ทุกรายการ foreshadowing ที่
เจอ** (join ด้วย " | ") แทนที่จะใช้แค่รายการล่าสุดรายการเดียวแบบ K1 เดิม — ยังคง reuse
`genome.compute_foreshadowing()`/`compute_payoff()` ตรงๆ ไม่คำนวณซ้ำ

**ทดสอบจริงบนโลกจริง**: รันกับฉากทั้งหมด **1,731/1,731 — error 0 ฉาก** — **1,624 ฉาก (94%)** ได้ hook
จากตาราง `hook_by_kind` ละเอียดจริง (ไม่ fallback) อีก 107 ฉาก fallback ไป `scene_type` ถูกต้อง —
**72 ฉาก** มี foreshadowing มากกว่า 1 รายการ ยืนยันว่า join ทำงานถูกต้อง — unit-test เฉพาะจุดของ
`hook_detector.detect_hook()` กับ kind ที่รู้จัก/ไม่รู้จัก/list ว่าง ผ่านครบ

**ปัญหาที่เจอ**: ไม่มี

### Phase K5 — Arc Builder

**ไฟล์ใหม่**: `narrative_factory/arc_builder.py` — `StoryArc` dataclass + `build_arcs_for_character()`/
`build_all_arcs()`

**การจับกลุ่ม**: ฉากของตัวละครเดียวกัน (`focal_cid`) ที่ `day_start` ห่างกันไม่เกิน
`arc_merge_window_days` (config.yaml ใหม่, ดีฟอลต์ 365 วัน — ใหญ่กว่า `scene_merge_window_days` ของ
Scene ที่ 3 วันมาก เพราะ Arc คือเรื่องราวช่วงยาว) ถือเป็นอาร์คเดียวกัน — reuse pattern การ cluster ตาม
ช่วงเวลาเดียวกับ `scene_extractor.py` แค่ทำที่ระดับ Scene แทนระดับ Event ทุก field ของ `StoryArc`
reuse ของที่มีอยู่แล้วทั้งหมด (`goal_by_scene_type`, `genome.conflict_level`, `genome.payoff`,
`teacher.analyze_conflict()`) ไม่คำนวณอะไรใหม่

**ทดสอบจริงบนโลกจริง**: รัน `build_all_arcs()` กับฉากทั้งหมด **1,731 ฉาก จาก 656 ตัวละคร (จาก 864
ตัวละครทั้งหมดในโลก) → สร้างได้ 1,314 อาร์ค** ยืนยันนับฉากรวมในทุกอาร์คตรงกับจำนวนฉากทั้งหมดเป๊ะ
(1,731 == 1,731 — ไม่มีฉากตกหล่น/ซ้ำ) field ไม่ว่างเปล่าและ `start_day<=end_day` ทุกอาร์ค — ตัวอย่าง
จริงที่ได้สมเหตุสมผล: cid=759 ("สัตว์อสูรป่า") มี 17 ฉาก แบ่งเป็น 3 อาร์คช่วงชีวิตจริง จบด้วยอาร์ค
สุดท้ายที่ resolution="ตาย: สัตว์อสูรป่าชิงสมบัติจากเงาทมิฬ — สัตว์อสูรป่าเป็นฝ่ายเสีย" (เห็นพัฒนาการ
ข้ามหลายฉากจริงเป็นครั้งแรกในบรรดา K1-K5 เพราะ Arc รวมฉากได้กว้างกว่า Scene แต่ละอันตัวเดียว)

**ปัญหาที่เจอ**: ไม่มี

### Phase K6 — Style Distillation

**ไฟล์ใหม่**: `narrative_factory/style_distill.py` — `StyleLesson` dataclass (`hook_pattern`,
`dialogue_pattern`, `pacing_pattern`, `cliffhanger_pattern`, `narration_pattern`) +
`distill_style(episode_text, agent, source_label, sim_reference)` + `contains_verbatim_copy()` +
`format_sim_reference()`

**ต่างจาก K1-K5 (rule-based ล้วน)**: งานนี้วิเคราะห์ร้อยแก้วอิสระที่มนุษย์เขียน (Novel_Episodes) ไม่มี
ทาง rule-based ได้จริง — ใช้ `OllamaAgent.complete()` ตัวเดียวกับ Phase 6/Phase E (ไม่สร้าง LLM client
ใหม่) ป้องกันการคัดลอกข้อความมีลิขสิทธิ์ 2 ชั้น: (1) system prompt สั่งห้ามคัดลอกตรงๆ (2)
`contains_verbatim_copy()` ตรวจภายหลังจริงด้วย n-gram matching (window 20 ตัวอักษร) — เจอ substring
ที่ตรงกับต้นฉบับเป๊ะถือว่า reject ทันที ไม่ export เลย

**บั๊กจริงที่เจอและแก้ (สำคัญ — กระทบทั้งระบบ ไม่ใช่แค่ K6)**: ทดสอบครั้งแรกกับ episode จริง (9,104
ตัวอักษร) ทั้ง `qwen2.5vl:7b` (ตอบนอกประเด็นสม่ำเสมอ คิดว่ากำลังถูกขอให้แต่งเรื่องต่อ/วิจารณ์งานเขียน) และ
`deepseek-r1:8b` (error `exceed_context_size_error` ตรงๆ) **ล้มเหลวทั้งคู่** — วินิจฉัยจริงพบว่า Ollama
ใช้ runtime context window แค่ **4096 token เป็นดีฟอลต์เสมอ** ไม่ว่าโมเดลจะรองรับยาวแค่ไหนจริง
(`ollama show` รายงาน 131072 แต่ถ้าไม่ส่ง `options.num_ctx` มาตรงๆ จะโดนตัดเหลือ 4096 อยู่ดี) —
prompt จริงของ K6 ยาวถึง 5,934 token เกิน default ไปมาก ทำให้ deepseek error ตรงๆ ส่วน qwen2.5vl ไม่
error แต่ตอบนอกประเด็น (คาดว่าโดนตัด context เงียบๆ) — **แก้ที่ `tiandao/ai/llm_agent.py` เพิ่ม
`num_ctx` parameter ให้ `OllamaAgent.complete()`/`_post_chat()`** (optional, ดีฟอลต์ `None` = พฤติกรรม
เดิมทุกประการสำหรับ caller เดิม Phase 5/6 ที่ prompt สั้นพอไม่เคยชนปัญหานี้) `style_distill.py` เพิ่ม
`_estimate_num_ctx()` ประมาณ token ที่ต้องใช้แบบ safe overestimate (0.75 token/ตัวอักษร) แล้วส่งเข้า
`complete()` ทุกครั้ง — **แก้แล้วทั้งสองโมเดลทำงานถูกต้อง** (พิสูจน์ว่าปัญหาคือ context window ไม่ใช่
ความสามารถของโมเดล ไม่จำเป็นต้องเปลี่ยนโมเดลเริ่มต้นของโปรเจกต์)

**ทดสอบจริง (ไม่ mock, ใช้ episode จริง 1 ตอนจาก Novel_Episodes — ไม่ทำทั้ง 170 ตอนเพื่อเวลา)**:
1. unit-test `contains_verbatim_copy()` เฉพาะจุด: กรณีคัดลอกตรงๆ (True ถูกต้อง), paraphrase (False
   ถูกต้อง), ข้อความสั้นกว่า window (False ถูกต้อง)
2. `distill_style()` จริงกับ `EPISODE_01.md` (9,104 ตัวอักษร) + `sim_reference` จริงจาก K1 (StoryLesson)
   + K5 (StoryArc) — ได้ StyleLesson จริงทั้งจาก `qwen2.5vl:7b` และ `deepseek-r1:8b` (หลังแก้ num_ctx)
   ทั้งคู่เป็นคำอธิบายเชิงรูปแบบ abstract จริง (เช่น "เปิดฉากด้วยคำถามปริศนาที่ทำให้ผู้อ่านอยากค้นหา
   คำตอบ") ไม่ใช่ข้อความยกมาจากต้นฉบับ — ตรวจซ้ำด้วย `contains_verbatim_copy()` = False ทั้งคู่ ยืนยัน
   ว่าไม่มีการคัดลอกจริง

**ปัญหาที่เจอ**: บั๊ก `num_ctx` ด้านบน (แก้แล้ว) — **ข้อควรระวังที่ยังไม่แก้**: ยังไม่ได้ทดสอบกับ 170
ตอนทั้งหมด (ทดสอบแค่ 1 ตอน) และยังไม่มี retry mechanism ถ้า `distill_style()` คืน `None` (parse fail/
คัดลอกตรวจพบ) — ตอนนี้แค่ log warning แล้วข้าม เป็นพฤติกรรมที่ตั้งใจ (เหมือน Dataset A ที่ fallback
กลับ template ไม่ทิ้งงานทั้งก้อน) แต่ K7 (Lesson Export) ต้องรู้ว่าอาจได้ StyleLesson น้อยกว่าจำนวน
episode จริงที่ป้อนเข้าไป

### Phase K7 — Lesson Export

**ไฟล์ใหม่**: `narrative_factory/lesson_exporter.py` (`export_lessons()`), `build_lessons.py` (CLI root
orchestrator เรียก K1+K5+K6 ครบแล้ว export)

**การตัดสินใจ**: export ไปที่ `datasets/lessons_v1/` (ชื่อ fixed ตามที่ ROLE Phase K กำหนดตรงๆ) ไม่ใช้
`versioning.next_version_dir()` แบบ Dataset A-E เพราะเป็นก้อนข้อมูลใหม่แยกต่างหาก ไม่ผูกกับ
incremental versioning เดิมของ Phase F — record เป็น ChatML `{"messages":[...]}` รูปแบบเดียวกับ
`dataset_formatter.py` เพื่อให้โหลดรวมกับ Dataset A-E ได้ตรงๆ ในขั้น Multi-Task Training ถัดไป

**ทดสอบจริงเต็มรูปแบบ (ไม่ mock)**: รัน `build_lessons.py --style-limit 2` บนโลกจริงทั้งใบ —
**สร้าง StoryLesson จริง 1,731 ฉาก + StoryArc จริง 1,314 อาร์ค ครบ 100%** บวก Style Distillation จริง
2 ตอนจาก Novel_Episodes ผ่าน Ollama — **ได้ StyleLesson จริง 1/2 ตอน อีก 1 ตอน (EPISODE_02.md) ถูก
`contains_verbatim_copy()` จับได้จริงว่า LLM คัดลอกข้อความจากต้นฉบับ แล้ว reject ทิ้งอัตโนมัติ** (ไม่ใช่
แค่ทฤษฎี — กลไกป้องกันลิขสิทธิ์ที่สร้างไว้ใน K6 ทำงานจริงและจับเคสจริงได้) ใช้เวลารวม 25 วินาที เขียนไฟล์
ที่ `datasets/lessons_v1/{story_lesson,arc_lesson,style_lesson}.jsonl` ครบ (1,731 / 1,314 / 1 record
ตามลำดับ) ตรวจ record ตัวอย่างแล้วรูปแบบ ChatML ถูกต้อง

**ปัญหาที่เจอ**: ไม่มีบั๊กใหม่ — สังเกตเห็นอักษรจีนหลุดปนใน StyleLesson ตัวอย่างหนึ่ง ("角色" แทน
"ตัวละคร") ตรงกับปัญหาข้อ 2 เดิมที่บันทึกไว้แล้ว (qwen2.5vl หลุดอักษรจีนปนบ่อย) ไม่ใช่บั๊กใหม่จาก K6
— `lesson_exporter.py` ยังไม่ผ่าน CJK filter ของ `scoring.py` เหมือนที่ Dataset A ทำ (ไม่จำเป็นเพราะ
Lesson dataset ไม่ได้ผ่าน Phase D Validator gate อยู่แล้วตามที่ออกแบบไว้ — เป็นข้อจำกัดที่รู้อยู่แล้ว
ไม่ใช่จุดบกพร่องที่ไม่รู้ตัว)

**คำสั่งที่ใช้ได้จริงตอนนี้**:
```bash
python build_lessons.py --style-limit 5 --novel-episodes-dir "G:/My Drive/Project/My_AI_Second_Brain/Novel_Episodes"
python build_lessons.py    # ไม่ระบุ --novel-episodes-dir = ข้าม K6 ได้แค่ K1/K5
```

### Multi-Task Training ขยาย (Phase K7 ต่อ)

**แก้**: `narrative_factory/dataset_formatter.py` เพิ่ม `_fmt_passthrough()` + ลงทะเบียน
`story_lesson.jsonl`/`arc_lesson.jsonl`/`style_lesson.jsonl` ใน `_FORMATTERS` (ไฟล์เหล่านี้เป็น ChatML
อยู่แล้วจาก `lesson_exporter.py` ไม่ต้องแปลงซ้ำ) — `autotrain.py` เพิ่ม `lessons_v1` เข้า version list
เอง**ถ้าโฟลเดอร์นี้มีอยู่จริง**เท่านั้น (ไม่กระทบ `export_state.json`/Phase F versioning เดิมเลย —
`lessons_v1` ไม่ใช่ pseudo-version ที่ปนกับ `v1,v2,...` ของจริง)

**ทดสอบจริง**: `dataset_formatter.load_dataset_dirs(datasets_dir, ["v1", "lessons_v1"])` โหลดรวมได้
**5,003 ตัวอย่างเป๊ะ** (1,957 จาก v1 เดิม [scene_sft 1,731 + planning 218 + chronicle 8] + 3,046 จาก
lessons_v1 ใหม่ [story_lesson 1,731 + arc_lesson 1,314 + style_lesson 1]) — ยืนยันว่า Dataset A-E เดิม
ไม่เสียหายเลย (ตัวเลขตรงกับที่ Phase H เคยนับไว้เป๊ะ) ตามกฎ "ต้องไม่ทำให้ Dataset เดิมเสีย"

**ปัญหาที่เจอ**: ไม่มี

### Shadow Evaluation V2 + Hot Swap (Phase K ต่อ)

**การตัดสินใจของผู้ใช้**: แทนที่ `scoring.py:WEIGHTS`/`PASS_THRESHOLD` เดิม (Timeline 25/Character 25/
Event 20/Memory 15/Style 15, ผ่านที่ 80) **ทั้งชุด** ด้วยตารางใหม่ (Timeline 20/Character 20/Event 15/
Memory 10/Style 20/**Pacing 15**, ผ่านที่ 85) — ต่างจาก Phase I ที่แยกค่าใหม่ไม่แตะของเดิม ผลคือ
Dataset A-E export ปกติก็ใช้เกณฑ์ใหม่นี้ตั้งแต่นี้ไปด้วย ไม่ใช่แค่ Phase J's Shadow Evaluation Gate

**แก้**:
- `narrative_factory/scoring.py` — `WEIGHTS`/`PASS_THRESHOLD` แทนที่ทั้งชุด เพิ่ม `_pacing_score()`
  (metric ใหม่ — เทียบจำนวน paragraph ของ candidate กับจำนวน Beat จริงจาก `pacing.assign_beats()`)
  `score_candidate()` เพิ่ม `scene: Optional[Scene] = None` (optional เพื่อไม่ให้ caller เก่าพัง — ไม่
  ส่งมา = ให้คะแนนเต็ม 15 แบบเป็นกลาง)
- `narrative_factory/exporter.py`, `narrative_factory/shadow_eval.py`, `narrative_factory/pipeline.py`
  — ทั้ง 3 จุดที่เรียก `score_candidate()` แก้ให้ส่ง `scene=scene` (มีอยู่แล้วทุกจุด ไม่ต้องหาข้อมูลเพิ่ม)
- `narrative_factory/config.yaml` — `dpo_chosen_threshold` ปรับจาก 85 เป็น **90** (เดิมตั้งไว้สูงกว่า
  `PASS_THRESHOLD=80` แต่พอ Phase K เปลี่ยน `PASS_THRESHOLD` เป็น 85 ค่าทั้งสองชนกันพอดี ทำให้ "chosen"
  ของ DPO ไม่เข้มกว่าเกณฑ์ผ่านปกติเหมือนที่ตั้งใจไว้แต่แรก — บั๊ก/ผลกระทบข้ามเฟสที่พบและแก้ระหว่างทดสอบ)

**Hot Swap**: ไม่ต้องแก้ `hotswap.py`/`evaluate_model.py` เลยตามที่ ROLE Phase K ระบุไว้ตรงๆ ("ไม่ต้อง
เปลี่ยนโครงหลัก ใช้ Metric ใหม่แทนของเดิม") — ทั้งสองไฟล์เรียก `scoring.score_candidate()` ผ่าน
`shadow_eval.py` อยู่แล้ว ได้ metric ใหม่ทันทีโดยอัตโนมัติ

**ทดสอบจริง (regression — ยืนยันว่า Dataset A-E เดิมไม่พังจากเกณฑ์ใหม่)**: รัน template (fallback
ปลอดภัยของ Dataset A) ผ่าน `score_candidate()` ใหม่กับฉากจริงทั้งหมด **1,731/1,731 ฉากผ่านเกณฑ์ใหม่
100%** (คะแนนเฉลี่ย 100.0, ต่ำสุด 95 — ฉากคะแนนต่ำสุดเป็นฉากหลายเหตุการณ์ที่เสีย pacing 5 แต้มเพราะ
template รวมเป็น paragraph เดียวเสมอ แต่ยังผ่านสบายเพราะ metric อื่นเต็มหมด) ยืนยัน `sum(WEIGHTS)==100`
จริง

**ทดสอบจริงครบตาม "การทดสอบที่ต้องทำ" ของ ROLE Phase K ทั้ง 7 ข้อ**:
1. ✅ StoryLesson จริงจากโลกจริง (K1 — 1,731 ฉาก)
2. ✅ Arc จริง (K5 — 1,314 อาร์ค)
3. ✅ StyleLesson จริง (K6 — 1 ตอนสำเร็จ + 1 ตอนถูก reject เพราะคัดลอกจริง)
4. ✅ Export Lesson Dataset จริง (K7 — `datasets/lessons_v1/`)
5. ✅ เทรน LoRA ด้วย Lesson Dataset จริง — `autotrain.py --force --max-steps 5` โหลด **5,003 ตัวอย่าง
   จาก v1+lessons_v1 จริง** เทรนจริง 5 step (loss 3.219→1.950) บันทึกที่ `loras/v2` (44.4 วินาที)
6. ✅ Evaluate จริง — `evaluate_model.py --candidate-lora loras/v2 --n-scenes 10` จริงบน GPU
7. ✅ เปรียบเทียบกับ Baseline จริง — **REJECT** (candidate mean_score=76.6 pass_rate=50% < baseline
   mean_score=87.7 pass_rate=90%) — ผลสมเหตุสมผลเหมือน `loras/v1` ใน Phase J (5 step ไม่พอให้ลู่เข้า
   จริงบนข้อมูล multi-task 5,003 ตัวอย่างที่หลากหลายกว่าเดิมอีก ยิ่งต้องใช้ step มากกว่าเดิมถึงจะลู่เข้า)
   — ยืนยันอีกครั้งว่า Shadow Evaluation Gate (พร้อม metric ใหม่ครบ 6 ตัวแล้ว) ทำงานถูกต้องสม่ำเสมอ

**ปัญหาที่เจอ**: ไม่มีบั๊กใหม่ (บั๊ก `dpo_chosen_threshold` ชนกันแก้แล้วด้านบน)

### เทรนจนลู่เข้าจริง (ไม่จำกัด step) — ตามคำสั่งผู้ใช้หลัง Phase K เสร็จ

**อัปเกรด `train_lora.py` ให้เทรนจนลู่เข้าได้จริง (ไม่ใช่แค่ smoke test)**:
- เพิ่ม held-out validation split (`eval_ratio`, ดีฟอลต์ 5%, สุ่มด้วย seed คงที่) วัด `eval_loss`
  จริงทุกจบ epoch — ไม่ใช่แค่ดู train_loss ต่อ step ที่ noisy
- เพิ่ม `EarlyStoppingCallback` (patience 2 epoch) + `load_best_model_at_end=True` +
  `metric_for_best_model="eval_loss"` — คืน adapter ของ epoch ที่ดีที่สุดจริง ไม่ใช่ epoch สุดท้ายเสมอ
  (กัน overfit) เปิด/ปิดได้ผ่าน parameter ใหม่
- เพิ่ม `lr_scheduler_type="cosine"` + คำนวณ `warmup_steps` เอง — **พบว่า transformers 5.15.0 ที่ลง
  ไว้ตัด `warmup_ratio` ออกจาก `TrainingArguments` แล้ว** (เช็คจริงจาก `__dataclass_fields__` เหลือแค่
  `warmup_steps`) ต้องคำนวณเป็นจำนวน step เอง (3% ของ total steps) แทนใช้ ratio ตรงๆ

**บั๊กจริงที่เจอระหว่างรันจริงครั้งแรก (ร้ายแรง — แก้แล้ว)**: รัน `autotrain.py --force --epochs 5`
จริงครั้งแรกบน 5,003 ตัวอย่าง จบ epoch 1 (loss ลดจาก 2.78→0.14 ปกติดี) แต่ **`eval_loss` ออกมาเป็น
`NaN`** — วินิจฉัยพบว่า `ChatDataset.__getitem__()` เดิม truncate ทั้ง `full_text` และ `prompt_text`
ด้วย `max_length` เดียวกัน ถ้า record ไหนมี prompt (system+user) ที่ยาวเกิน `max_length` อยู่แล้ว (เจอ
จริงกับ record ประเภท **chronicle** ที่มี event list ยาวมาก) label ทั้งก้อนจะโดน mask หมด (ไม่เหลือ
token คำตอบเลย) → loss เป็น `NaN` ทันที — **สแกนทั้ง 5,003 ตัวอย่างจริงพบ 5/4,753 ใน training set +
1/250 ใน eval set ที่เป็นแบบนี้** (`eval_loss` NaN เพราะ `per_device_eval_batch_size=1` แค่ตัวอย่างเดียว
ก็ poison ค่าเฉลี่ยทั้ง epoch ได้) เสี่ยงทำให้ `load_best_model_at_end`/`EarlyStoppingCallback` ตัดสินใจ
ผิดพลาดหรือพังกลางทาง — **หยุดการเทรนที่กำลังรันอยู่ทันที** (ตาม "ช้าได้แต่ต้องดีที่สุด" ไม่ปล่อยให้รัน
ต่อไปอีก 3-4 ชั่วโมงบนบั๊กที่รู้อยู่แล้ว) แก้ที่ `ChatDataset` โดยกันที่ว่างขั้นต่ำ `MIN_COMPLETION_TOKENS`
(64 token) ไว้ให้คำตอบเสมอ (ตัด prompt ให้สั้นลงแทนถ้าจำเป็น ไม่ตัดคำตอบทิ้งทั้งหมด) — **ทดสอบซ้ำกับ
ทั้ง 5,003 ตัวอย่างจริงยืนยันว่า all-masked เหลือ 0 ตัวอย่าง** (จาก 6 ตัวอย่างเดิม) แล้วรันเทรนใหม่ตั้งแต่
ต้นด้วยโค้ดที่แก้แล้ว

**ผลเทรนจริงจนลู่เข้า (`loras/v3`)**: รันครบ 5 epoch จริง (2,975 step, ~4.8 วินาที/step) —
`eval_loss` ลดลงต่อเนื่องสวยงามไม่มี NaN เลยสักครั้ง (ยืนยันว่าบั๊กด้านบนแก้หายขาดจริง):

| Epoch | eval_loss |
|---|---|
| 1 | 0.1602 |
| 2 | 0.1435 |
| 3 | 0.1364 |
| **4** | **0.1311 (ต่ำสุด — เลือกเป็น best model)** |
| 5 | 0.1320 (เริ่ม overfit เล็กน้อย) |

`load_best_model_at_end` ทำงานถูกต้อง — คืน checkpoint epoch 4 (ไม่ใช่ epoch 5 สุดท้าย) `EarlyStoppingCallback`
ไม่ trigger (ต้อง 2 epoch ติดไม่ดีขึ้น แต่ epoch 5 เป็นครั้งแรกที่แย่ลง คำนวณครบ 5 epoch cap พอดี)

**ประเมินจริงกับ Shadow Evaluation Gate**: `evaluate_model.py --candidate-lora loras/v3 --n-scenes 15`
— **REJECT อีกครั้ง** (candidate mean_score=84.0 pass_rate=**0%** vs baseline mean_score=89.0
pass_rate=100%) แม้เทรนจนลู่เข้าจริงแล้วก็ตาม (train loss/eval_loss ลดลงสวยงามจริง ไม่ใช่ปัญหา
"เทรนไม่พอ" เหมือนที่สงสัยไว้ตอน v1/v2)

**🔍 พบสาเหตุที่แท้จริงแล้ว (สำคัญมาก — ไม่ใช่แค่ "เทรนน้อยไป")**: ตรวจ output จริงของ `loras/v3` ทุก
ตัวอย่างพบรูปแบบเดียวกันหมด: `"วันที่ {เลขวันที่แต่งขึ้นเอง}: {เหตุการณ์แบบสั้นๆ}"` — ละเมิด
`Rule2_NoFabricatedEvents` ทุกฉากเพราะเลขวันที่ที่ตอบมา**ไม่ตรงกับวันจริงในฉากนั้นเลยสักครั้งเดียว** —
**สืบสาเหตุกับโค้ดจริงแล้วพบว่าเป็น spurious correlation ที่เรียนไม่ได้จริงตั้งแต่ต้น ไม่ใช่บั๊กเทรน**:
- `exporter.py:118` — `input_payload["events"]` ส่งแค่ `[e.text for e in scene.events]` (**ไม่มีเลข
  `day` เลย**) เข้า prompt ตอนเทรน (`dataset_formatter.py:build_scene_messages()` ก็ต่อแค่ `e` ตรงๆ
  ไม่มีวันที่)
- แต่ **output** ของ Scene SFT (template จาก `_template_scene_prose()`) ใส่ `f"วันที่ {e.day}{gap}: ..."`
  นำหน้าทุกเหตุการณ์เสมอ — โมเดลจึงเห็นแพทเทิร์นพื้นผิว "คำตอบเริ่มด้วยวันที่" ซ้ำๆ ใน 1,731 ตัวอย่าง
  Scene SFT (+ StoryLesson/ArcLesson ที่มี "payoff" ในรูปแบบเดียวกันอีก 3,045 ตัวอย่าง — รวมเป็น 95.5%
  ของ dataset ทั้งหมด) **โดยไม่เคยเห็นเลขวันที่จริงในฝั่ง input เลยสักครั้ง** — เป็นไปไม่ได้ที่โมเดลจะ
  เรียนรู้ mapping ที่ถูกต้องจากข้อมูลนี้ ยิ่งเทรนนานยิ่งมั่นใจในการ "เดา" เลขวันที่ปลอมที่ฟังดูสมจริง
  มากขึ้นเท่านั้น (ตรงกับที่เห็นจริง: คะแนนไม่ดีขึ้นแม้ eval_loss ลดลงต่อเนื่อง เพราะ eval_loss วัดแค่
  "เดาตัวอักษรถัดไปได้แม่นแค่ไหน" ไม่ได้วัดว่า Rule 2 ผ่านไหม)
- **สรุป**: การ "เทรนจนลู่เข้า" สำเร็จแล้วจริงตามที่สั่ง (eval_loss ลู่เข้าจริง ไม่ใช่ underfitting) แต่
  **ข้อมูล Dataset A (template) ในสภาพปัจจุบันมีข้อบกพร่องเชิงโครงสร้างที่ทำให้เทรนแล้วแย่ลงเสมอ ไม่ว่า
  จะเทรนนานแค่ไหน** — ไม่ใช่สิ่งที่แก้ได้ด้วยการเทรนเพิ่ม/เปลี่ยน hyperparameter ต้องแก้ที่ตัวข้อมูล
  (เอาเลข `day` ใส่ใน input ให้ mapping เรียนได้จริง หรือตัดคำนำหน้า "วันที่ N:" ออกจาก output template
  เพราะการขอให้ LLM "จำ" เลข ID ที่ไม่เคยเห็นเป็นงานที่ผิดธรรมชาติของโมเดล generative ตั้งแต่ต้น)

---

## ปัญหาที่เจอจริงและยังไม่แก้ (สำคัญที่สุด — อ่านก่อนใช้งานจริง)

### 1. บั๊กเอนจินหลัก: `Event.seq` เคยไม่ unique จริง (แก้แล้ว — สำคัญที่สุดที่เจอทั้งเซสชัน)
`tiandao/sim.py` เดิมเพิ่ม `self.seq` แค่ครั้งเดียวต่อหนึ่ง "ทิก" แต่หนึ่งทิกเรียก `self.emit()` ได้
มากกว่าหนึ่งครั้ง (เหตุการณ์ผลพวง เช่น มารบุก+ผู้ต้านทาน) ทำให้ Event คนละเรื่องกันมี `seq` ซ้ำได้จริง
(628/8673 เหตุการณ์ในรันหนึ่งซ้ำ) — ทำให้ `narrative_factory` สร้าง `scene_id` ชนกัน (สอง scene
ที่ไม่เกี่ยวข้องกันเลยได้ id เดียวกัน) ตรวจจับได้ตอน Phase D ทดสอบ dataset จริง **แก้แล้ว** โดยย้าย
`self.seq += 1` เข้าไปใน `emit()` เอง — ทดสอบ `run.py`/`daemon.py` แล้วไม่กระทบพฤติกรรมซิม (seq ไม่เคย
ถูกใช้ในการตัดสินใจใดๆ อยู่แล้ว)

### 2. คุณภาพเนื้อหา Phase 6 (History Generator) ยังไม่ถึงมาตรฐาน `Novel_Episodes`
ทดสอบแล้ว 3 รอบกับตัวละครเดียวกัน (cid=770, ประวัติจริง: ข้ามขั้นสำเร็จ, บุกกินคนจากแดนมาร 4 ครั้ง,
ชิงสมบัติแล้วแพ้):

| รอบ | โมเดล | ผลลัพธ์ |
|---|---|---|
| 1 | `qwen2.5vl:7b`, prompt เวอร์ชันแรก | เนื้อหาทั่วไปซ้ำๆ ไม่แตะเหตุการณ์จริงที่ให้ไปเกือบทั้งหมด มีอักษรจีนหลุดปน |
| 2 | `qwen3-coder:30b` (ใหญ่กว่า 4 เท่า) | รูปแบบบทพูดถูกต้องขึ้น แต่เนื้อหา**แย่กว่า**เดิม ซ้ำประโยคเกือบคำต่อคำ 6 ช่วงติด ไม่ใช้ข้อมูลจริงเลย |
| 3 | `qwen2.5vl:7b`, prompt เวอร์ชันบังคับอ้างอิงทีละฉาก | ชื่อตัวละครถูกต้องบางฉาก (พิสูจน์ pipeline ส่งข้อมูลถูก) แต่**แต่งฉากหลอนขึ้นมาเอง** (อ้างวันที่ที่ไม่มีจริง ผูกชื่อเข้ากับเหตุการณ์ผิด) และข้ามฉากจริงไป 4 จาก 8 ฉาก ทั้งที่ prompt สั่งห้ามชัดเจน |

**สรุป**: โมเดล local ขนาด 7-30B ที่มีในเครื่องตอนนี้ ยังไม่สามารถถือกฎหลายข้อพร้อมกันได้แม่นยำพอจะใช้
งานจริงโดยไม่ตรวจทานเอง — กลไก (data → prompt → LLM → ไฟล์) ถูกต้อง 100% แต่**ต้องมีคนตรวจ/แก้เนื้อหา
ที่ LLM สร้างก่อนใช้จริงเสมอ** ไม่ใช่ auto-publish ได้ทันที **นี่คือเหตุผลที่ `build_dataset.py`
(Phase E) เลือกใช้ template แบบเรียบเป็นค่าเริ่มต้นแทนการยิง LLM ทุกฉาก** — พิสูจน์แล้วว่า template
ผ่าน Phase D validator 100% (2,864/2,864 ฉาก) ในขณะที่ LLM ยังทำไม่ได้ขนาดนั้น

แนวทางที่ยังไม่ได้ลอง (ถ้าจะสู้ต่อ): ลดจำนวนฉากต่อตอนเหลือ 3-4, ลอง `deepseek-r1:8b`, หรือ generate
ทีละฉากแยกกันแล้วเอามาต่อเองแทนที่จะขอทีเดียวทั้งตอน

### 3. `world.save` โตไม่มีเพดาน — **แก้แล้วใน Phase G (opt-in ผ่าน `daemon.py`)**
`sim.log` คือตัวการเดิม — ตอนนี้ `daemon.py --keep-recent-events N` (ดีฟอลต์เปิดอยู่ N=5000) flush
ของเก่าลง `tiandao/event_log.py` sidecar file แล้วตัด `sim.log` ในหน่วยความจำทิ้ง ดูส่วนที่ 4 ด้านบน
— `run.py` ยังไม่มีกลไกนี้ (ไม่ใช่จุดที่เจอปัญหาจริง ยังปล่อยสะสมไม่มีเพดานเหมือนเดิมถ้าใช้ยาวๆ)

### 4. จุดที่ไม่ deterministic ในเอนจินเดิม — **แก้แล้วใน Phase G**
`tiandao/sim.py` เคยมีบล็อก `w.current_disaster = random.choice([...])` (flavor text ภัยพิบัติ) ที่ใช้
โมดูล `random` กลาง แทนที่จะเป็น `self.rng` ของซิม — ยืนยันผลกระทบจริงไว้ก่อนแก้ (รัน `--seed 20
--events 8000` สองครั้งติดกันได้จำนวนเหตุการณ์ต่างกัน 8689 vs 8641 ทั้งที่ seed เดียวกัน) แก้เป็น
`rng.choice(...)` แล้ว (`rng` = `self.rng` ที่มีอยู่แล้วในสโคปเดียวกัน) ทดสอบซ้ำแล้วว่ารัน seed เดิม
ได้ผลเหมือนกันทุกตัวเลข 100%

### 5. Ollama ไม่มีโมเดลที่ ROLE.md แนะนำโดยตรง
ROLE.md แนะนำ `llama3:8b`/`qwen2.5:7b` แต่เครื่องนี้มี `qwen2.5vl:7b` (vision-language variant),
`deepseek-r1:8b`, `qwen3-coder:30b`, `qwen3-embedding:4b` — เลือกใช้ `qwen2.5vl:7b` เป็นค่าเริ่มต้น
เพราะตระกูล Qwen2.5 รองรับภาษาไทยดีที่สุดในบรรดาตัวเลือกที่มี แต่ยังไม่ใช่โมเดลที่ ROLE.md ตั้งใจเป๊ะๆ
(ดูปัญหาข้อ 2 — ส่วนหนึ่งอาจเป็นเพราะเรื่องนี้)

### 6. Dataset B/C (Dialogue/Monologue) ว่างเปล่าถ้าไม่เคยรันด้วย `--llm`
ตั้งใจ — เอนจินไม่มีกลไกบันทึกบทพูด/ความคิดจริงถ้าไม่เปิด Layer 3 (Phase 5) ตอนรันซิม ไม่ปั้นของปลอม
ขึ้นมาแทน ถ้าอยากได้ Dataset B/C ต้องรัน `python run.py --llm ...` หรือ `python daemon.py --llm ...`
ก่อน (ช้ามาก — ดูปัญหาข้อ 2 ของ Cultivator Brain v2/Phase 5) แล้วค่อย `build_dataset.py`

### 7. Romance/Comedy ไม่มีในระบบ Style Tagging
`narrative_factory/tagger.py` ไม่ติด tag สองอันนี้เลยโดยตั้งใจ เพราะเอนจินไม่มีกลไกความรัก/มุกตลกที่
เป็นเหตุการณ์แยกให้ตรวจจับได้อย่างมีมูล — ติดแบบเดามั่วดีกว่าไม่ติด

### 8. `dpo_pairs.jsonl` จะว่างเปล่าถ้าไม่เคยรัน `--llm --full` ซ้ำมากกว่าหนึ่งครั้ง
ตั้งใจ — Chosen/Rejected ของ scene_id เดียวกันเกิดได้ก็ต่อเมื่อ Ollama เคยตอบทั้งแบบผ่าน (คะแนน>=85)
และแบบไม่ผ่านให้ scene เดียวกันในคนละรอบ export เท่านั้น (ดู Phase I ด้านบน) — **ทดสอบจริงพบว่า
`qwen2.5vl:7b` แทบไม่หลุด 6 กฎเลยกับงาน "เรียบเรียงเหตุการณ์จริงเป็นร้อยแก้ว" (0 reject จาก 30
candidate จริง)** ดังนั้นในทางปฏิบัติต้องรันปริมาณมากพอ (หลายสิบ-หลายร้อยฉาก) ถึงจะสะสม Rejected ได้เอง
ตามธรรมชาติ ไม่ใช่แค่รัน --full สองสามครั้งกับฉากเดิมไม่กี่ฉากแล้วคาดหวังว่าจะมี — เหมือนกับ Dataset B/C
ที่ว่างถ้าไม่เคย --llm

### 9. Ollama native safetensors (`--experimental`) ไม่รองรับ Qwen2/Qwen2.5
ตรวจสอบจริงกับ Ollama 0.33.2 บนเครื่องนี้: `FROM`/`ADAPTER` แบบ safetensors ตรงๆ (ไม่ผ่าน GGUF) รองรับ
แค่ Llama/Mistral/Gemma/Phi3 — โปรเจกต์นี้ใช้ Qwen2.5-7B-Instruct จึงต้องแปลง GGUF จริงเสมอ (ดู Phase J)
ไม่มีทางลัดผ่านความสามารถ native ของ Ollama ได้ในตอนนี้ ต้องพึ่ง `vendor_llama_cpp_convert/` ต่อไป

### 10. ~~ยังไม่มี LoRA เวอร์ชันไหนผ่าน Shadow Evaluation Gate จริง~~ — **แก้แล้ว: `loras/v4` ผ่านจริง
และ deploy เข้า Ollama จริงแล้ว**
`loras/v1` (5 step smoke test), `loras/v2` (5 step, multi-task), `loras/v3` (5 epoch จนลู่เข้าจริงแต่
ข้อมูลมี spurious correlation) ถูก Gate ปฏิเสธตามลำดับ — **`loras/v4`** (5 epoch จนลู่เข้า + แก้ข้อมูล
spurious correlation แล้ว) **ผ่าน Gate จริงเป็นตัวแรกของโปรเจกต์** ยืนยันด้วย held-out set จริง 79 ฉาก
ที่ไม่เคยเห็นตอนเทรน (mean_score 99.9 vs baseline 88.1) — **`cultivator-brain:latest`/`v4` สร้างจริง
และรันได้จริงใน Ollama แล้ว** (ดูหัวข้อ "Hot-Swap Deploy จริง" ด้านบน)

**อัปเดต (หลังพัก)**: Shadow Evaluation Gate ข้างต้นวัดคุณภาพงานที่ `loras/v4` **ถูกเทรนมาโดยตรง** (Scene
SFT/Story Lesson/Arc Lesson/Chronicle/Planning ผ่าน `scoring.py`) — แต่ Layer 3 สด (`llm_agent.py`) เป็น
งานคนละแบบ (JSON `{"dialogue","thought"}` สั้นๆ) ที่ `loras/v4` ไม่เคยเห็นตัวอย่างตอนเทรนเลย (ไม่มี
Dataset B/C เพราะ world ที่ใช้เทรนไม่เคยรันด้วย `--llm`) ทดสอบ A/B จริง 45 เหตุการณ์เทียบกับ
`qwen2.5vl:7b` เดิมพบว่าแย่กว่าจริงสำหรับงานนี้โดยเฉพาะ (JSON parse 84% vs 100%, CJK leak 18% vs 2% —
รายละเอียดเต็มอยู่ในหัวข้อ "หมายเหตุ: พักงานไว้ตรงนี้" ด้านบน) — **`OLLAMA_MODEL` เปลี่ยนกลับเป็น
`qwen2.5vl:7b` แล้ว** `cultivator-brain:latest` ยังคงมีประโยชน์จริงสำหรับงานที่มันถูกเทรนมา (dataset
export/lesson generation) แค่ไม่ใช่ตัวเลือกที่ดีสำหรับ Layer 3 สดในสภาพปัจจุบัน เหลือแค่การตัดสินใจแยกต่างหากว่า
จะเปลี่ยน `config_ai.OLLAMA_MODEL` ให้ Layer 3 ใช้โมเดลนี้ด้วยหรือไม่ (ยังไม่ได้ทำ)

### 11. Ollama runtime context window ดีฟอลต์แค่ 4096 token เสมอ ไม่ว่าโมเดลรองรับยาวแค่ไหนจริง —
**แก้แล้วบางส่วน (Phase K6)**
`ollama show` รายงาน context length ตามที่โมเดลรองรับจริง (เช่น 131072) แต่ถ้า client ไม่ส่ง
`options.num_ctx` มาตรงๆ ตอนเรียก `/api/chat` runtime จะตัดเหลือ 4096 token เสมอ — เจอจริงตอน Phase K6
(prompt ยาว ~5,900 token ทำให้ `deepseek-r1:8b` error ตรงๆ ส่วน `qwen2.5vl:7b` ไม่ error แต่ตอบนอก
ประเด็นสม่ำเสมอ) แก้แล้วที่ `tiandao/ai/llm_agent.py` (เพิ่ม `num_ctx` parameter, optional) แต่**แก้
เฉพาะจุดที่ `style_distill.py` เรียกใช้เท่านั้น** — จุดอื่นที่อาจมี prompt ยาวในอนาคต (เช่น
`tiandao/ai/history.py` Phase 6 ถ้าเพิ่ม `HISTORY_MAX_SCENES` มากๆ) ยังไม่ได้ส่ง `num_ctx` เผื่อไว้
ต้องระวังถ้า prompt ยาวเกิน 4096 token ที่จุดอื่นในอนาคต

### 12. Dataset A (Scene SFT) template มี spurious correlation ที่เทรนไม่ได้จริง — **แก้แล้ว**
**สำคัญที่สุดที่พบตอน "เทรนจนลู่เข้า"** — ไม่ใช่แค่บั๊กเทรน แต่เป็นข้อบกพร่องเชิงโครงสร้างของข้อมูล:
`_template_scene_prose()` (exporter.py) ใส่ `"วันที่ {e.day}: ..."` นำหน้าทุกเหตุการณ์ใน**output** เสมอ
แต่ **input** ตอนเทรน (`build_scene_messages()`) ไม่มีเลข `day` ให้เห็นเลย (`exporter.py:118` เดิมส่งแค่
`e.text`) — โมเดลจึงเรียนแค่ "ต้องเดาเลขวันที่ขึ้นมาเอง" ซึ่งเดาผิดเสมอ (ละเมิด
`Rule2_NoFabricatedEvents` ทุกครั้ง) พิสูจน์จริงแล้วว่าเทรนจนลู่เข้า (`eval_loss` ลดจาก 0.16→0.131,
ไม่ underfitting) ก็ยังคง reject 100% เพราะปัญหาอยู่ที่การออกแบบข้อมูล ไม่ใช่ปริมาณการเทรน

**แก้แล้ว**: เพิ่ม `narrative_factory/exporter.py:build_scene_input_payload()` — ใส่เลข `day` นำหน้า
แต่ละเหตุการณ์ใน `input.events` ตรงๆ (`"วันที่ {e.day}: {e.text}"` ตรงกับรูปแบบใน output template เป๊ะ)
ให้ mapping เรียนได้จริง — `shadow_eval.py:_scene_input_payload()` แก้ให้ delegate ไปฟังก์ชันเดียวกัน
(เดิม 2 ไฟล์มี logic คล้ายกันแยกกัน เสี่ยง drift ถ้าแก้จุดเดียว) ยืนยันแล้วว่า exporter/shadow_eval
ให้ผลเหมือนกันเป๊ะ — re-export ด้วย `build_dataset.py --full` เป็น `datasets/v2/` (ยืนยัน on-disk มี
`"วันที่ N: ..."` นำหน้าจริง) อัปเดต `export_state.json` ให้ชี้ v2 แทน v1 เดิม แล้วลบ `datasets/v1/`
ทิ้ง (ข้อมูลเดิมมีบั๊กจริง ไม่ต้องการให้ใครใช้ผิดโดยไม่ตั้งใจอีก)

**ผลเทรนใหม่ด้วยข้อมูลที่แก้แล้ว (`loras/v4`) — 🎉 ผ่าน Shadow Evaluation Gate จริงเป็นตัวแรกของ
โปรเจกต์**: เทรนครบ 5 epoch เหมือนเดิม `eval_loss` ลดลงต่อเนื่อง**และต่ำกว่า v3 มาก**
(0.0919→0.0777→0.0690→0.0642→**0.0635** ดีที่สุดที่ epoch 5 ยังไม่ overfit ต่างจาก v3 ที่แย่ลงตั้งแต่
epoch 5) — ยืนยันว่าการมีเลขวันที่ใน input ทำให้งานนี้เป็น mapping ที่เรียนรู้ได้จริงและง่ายขึ้นมาก
(loss ต่ำกว่าเดิมครึ่งหนึ่ง)

**ประเมินจริงครั้งแรก** (`evaluate_model.py --n-scenes 15`, สุ่มด้วย seed เดิม): candidate
mean_score=100.0 pass_rate=100% vs baseline 89.8/93% — **APPROVE** — แต่ตรวจสอบเพิ่มพบว่า **ฉากทั้ง
15 ที่สุ่มมาเคยอยู่ในชุดเทรนทั้งหมด (0/15 เป็น held-out จริง)** ทำให้ผลนี้อาจสะท้อนแค่ "จำได้" ไม่ใช่
"เขียนเก่งขึ้นจริง" (`candidate` output ตรงกับ template เป๊ะทุกตัวอักษร ยืนยันว่าเป็นการจำจริง)

**🔬 ทดสอบ generalization จริงเพิ่ม (สำคัญที่สุด)**: หาฉากที่เป็น held-out จริงตอนเทรน (สุ่มด้วย
`random.Random(20260830)` เดียวกับตอนเทรน จับคู่กับ `_meta.scene_id` ของ raw record ก่อนแปลงเป็น
ChatML) เจอ **79 ฉากที่โมเดลไม่เคยเห็นเลยระหว่างเทรน** ประเมินจริงกับทั้ง baseline และ candidate บน
79 ฉากนี้โดยเฉพาะ:
- baseline: mean_score=88.1, pass_rate=86% (n=79)
- **candidate (loras/v4): mean_score=99.9, pass_rate=100% (n=79)**
- **APPROVE จริง** บนฉากที่ไม่เคยเห็นเลย — ตรวจ output ตัวอย่างพบว่ายังคงตรงกับ template เป๊ะแม้เป็นฉาก
  ใหม่ที่ไม่เคยเทรน (เช่น scene 0-62/0-84/1-108) — **พิสูจน์ว่าโมเดลเรียนรู้ "ทักษะทั่วไป" จริง (อ่านเลข
  วันที่จาก input แล้วอ้างอิงกลับได้ถูกต้องเสมอ) ไม่ใช่แค่ท่องจำ 1,731 ฉากที่เทรนมา**

**สรุป**: `loras/v4` คือ LoRA เวอร์ชันแรกของโปรเจกต์ที่ผ่าน Shadow Evaluation Gate จริง พร้อมหลักฐาน
generalization ที่แท้จริง (ไม่ใช่แค่คะแนนสูงเพราะจำได้)

**อัปเดต (หลังพัก)**: ตรวจ Story/Arc Lesson data ตามที่ค้างไว้ (ดูหัวข้อ "หมายเหตุ: พักงานไว้ตรงนี้" ข้อ 2
ด้านบน) พบว่ามีปัญหาแบบเดียวกันนี้จริง **รุนแรงกว่า Dataset A เดิมด้วยซ้ำ** — `lesson_exporter.py` เดิมใส่
แค่ `scene_id`/`arc_id` เปล่าๆ ใน input ไม่มีเนื้อหาฉากเลย (Dataset A เดิมยังมี event text ให้ครบ แค่ขาด
เลขวันที่) กระทบ 3,045/5,003 ตัวอย่าง (60.9%) ของ Multi-Task Training — แก้แล้วด้วยแนวทางเดียวกัน (ใส่
เนื้อหาฉากจริงกลับเข้า input ผ่าน `build_scene_input_payload()`/`StoryArc.scene_summaries` ใหม่) และ
re-export `datasets/lessons_v1/` แล้ว — **อัปเดต: เทรน `loras/v5` ด้วยข้อมูลที่แก้แล้วเสร็จแล้ว**
(`autotrain.py --force --epochs 5`, `eval_loss` ลดถึง 0.0174 ต่ำกว่า v4 มาก) ผ่าน Shadow Evaluation
Gate จริง (เทียบ v4 บน held-out 15/175 ฉาก — เสมอกันที่ 100/100 คะแนน) และ spot-check output จริงบน
งาน story/arc lesson โดยตรงแล้ว (arc_lesson 4/4 ตรงเป๊ะ, story_lesson 4/6 ตรงเป๊ะ) — ดูรายละเอียดครบใน
`ส่วนที่ 5` ด้านบน (หัวข้อ Phase K) **ยังไม่ deploy** เข้า Ollama (เป็นการตัดสินใจแยกต่างหาก)

### 13. `genome.compute_foreshadowing()` เคยจับคู่ precursor event ข้ามตัวละครที่ไม่เกี่ยวข้องกับฉาก — **แก้แล้ว**
พบระหว่าง spot-check output ของ `loras/v5` บนงาน story_lesson: ฉาก `1-2945` (เยว่ฉางทรยศเยว่ยาน) ได้
foreshadowing อ้างถึง "เย่เฟย" ที่ไม่ใช่ผู้เกี่ยวข้องในฉากนั้นเลย — สืบสวนพบว่า `compute_foreshadowing()`
ค้นย้อนหลังใน**ประวัติทั้งชีวิต**ของตัวละครโฟกัส (`scene_extractor.index_by_character()` เก็บเหตุการณ์ที่
ตัวละครเป็นทั้ง actor และ target ไม่ใช่แค่ฉากที่เกี่ยวข้องกัน — ตั้งใจแบบนั้นตั้งแต่ Phase B) แล้วกรองแค่
`event.kind` ตรงกับตาราง `foreshadowing_precursors` เท่านั้น **ไม่เคยเช็คว่าคู่กรณีในเหตุการณ์นั้นเกี่ยวข้อง
กับฉากปัจจุบันหรือไม่** — ยืนยันจริง: เหตุการณ์ที่พบ (`day=88, kind=สะสางเรื่องเก่า, actor=228(เย่เฟย)
-> target=208(เยว่ฉาง)`) เป็นเหตุการณ์จริง กราวด์กับ log จริง 100% (ไม่ใช่การแต่งข้อมูล) แค่คู่กรณีเป็น
คนละคนกับฉากปัจจุบัน ทำให้ "การปูเรื่อง" ไม่เชื่อมโยงกับฉากจริงเชิงความหมาย

**แก้**: `compute_foreshadowing()`/`build_genome()` เพิ่มพารามิเตอร์ `other_participants` (ผู้เกี่ยวข้อง
อื่นในฉากปัจจุบัน ไม่รวมตัวละครโฟกัส) — precursor event ที่มีคู่กรณี (`target is not None`) ต้องมีคู่กรณี
นั้นอยู่ใน `other_participants` ด้วยถึงจะนับ เหตุการณ์เดี่ยว (บำเพ็ญคนเดียว ไม่มี target) ยังผ่านได้เสมอ
เหมือนเดิม (ไม่มีคู่กรณีให้ขัดแย้ง) — `scene_extractor.py` ส่ง `sc.participants - {focal}` เข้าไปตรงจุด
เดียวที่เรียก `build_genome()` (caller เดียว ไม่ต้องทำ backward-compat shim)

**ผลกระทบจริงต่อ coverage (วัดจริงบน `tiandao/world.save` เดิม ไม่ mock)**:
| | ก่อนแก้ | หลังแก้ |
|---|---|---|
| ฉากที่มี foreshadowing | 199/1,731 (11.5%) | **102/1,731 (5.9%)** |
| ฉากที่มี foreshadowing >1 รายการ | 72 | **19** |

coverage ลดลงเกือบครึ่ง — ยืนยันว่า precursor match ส่วนใหญ่ที่เจอเดิมเป็นเหตุการณ์ที่พูดถึงคนละคนกับฉาก
จริงๆ ไม่ใช่กรณีหายาก — ยืนยันเคสของฉาก `1-2945` คืนค่า foreshadowing ว่างเปล่าถูกต้องแล้วหลังแก้

~~**ยังไม่ได้ทำ**: re-export `datasets/v*`/`datasets/lessons_v1/`~~ — **ทำแล้ว** (ดูข้อ 17 ด้านล่าง
สำหรับสรุปรวมของรอบ re-export + เทรน `loras/v6` — ทำพร้อมกับแก้บั๊กข้อ 14-16 ด้านล่างในรอบเดียวกัน)

### 14. Dataset E (Planning) `state` ไม่มีข้อมูลที่ตัดสิน `plan` จริง — **แก้แล้ว**
ตรวจตามคำสั่งผู้ใช้ให้เช็คบั๊กอื่นก่อน re-export/เทรน v6 — พบว่า `_reconstruct_breakthrough_plan()`
(`exporter.py`) เลือก method (Craft/Buy/Trade/Rob/Travel) จากการค้นย้อนหลังใน `character_log` ทั้งหมด
แต่ `state` (ฝั่ง input ที่ export ออกไปเทรน) มีแค่ `had_pill_at_breakthrough`/`at_furnace`/`at_market`/
`place_kind` ซึ่ง**ไม่มีผลต่อการเลือก method เลย** — ยืนยันกับข้อมูลจริงใน `datasets/v2/planning.jsonl`:
ฉากที่ `at_market=True` (อยู่ตลาดจริง) ยังได้ plan `['Travel', 'Breakthrough']` เหมือนฉากที่ไม่ได้อยู่
ตลาดเลย — 204/218 ตัวอย่าง (93.6%) ยุบเหลือ `Travel` เดียวกันหมด เป็น majority-class shortcut ไม่ใช่
mapping ที่เรียนรู้ได้จริง — **แก้**: เพิ่ม `state["recent_method_evidence"]` = ข้อความเหตุการณ์จริงที่
เป็นตัวตัดสิน method (หรือ `None` ถ้าไม่เจอ = ใช้ Travel fallback) เข้า state ตรงๆ

### 15. Dataset D (Chronicle) มีเลขปีหลุดในฝั่ง output แต่ไม่มีในฝั่ง input — **แก้แล้ว**
บั๊กเดียวกับ Dataset A ปัญหาข้อ 12 เป๊ะ แค่คนละไฟล์ — `build_dataset_d()` เดิม `events` (input) = แค่
`s.genome.payoff` ไม่มีเลขปี แต่ `chronicle` (output) ใส่ `"ปีที่ {day_start//365} — ..."` นำหน้าทุก
บรรทัดเสมอ — ยืนยันกับข้อมูลจริงใน `datasets/v2/chronicle.jsonl` แล้ว — **แก้**: ใส่เลขปีเข้า `events`
ตรงๆ ให้ตรงกับ `chronicle` (กระทบแค่ 8 ตัวอย่างในโลกนี้ แต่แก้ให้ครบตามมาตรฐานเดียวกับ Dataset A/E)

### 16. Dataset B/C (Dialogue/Monologue) ไม่มีเหตุการณ์ที่กระตุ้นบทพูด/ความคิดในฝั่ง input — **แก้แล้ว**
(ยังไม่มีผลกระทบจริงตอนนี้ — Dataset B/C ว่างเปล่าเสมอเพราะโลกนี้ไม่เคยรันด้วย `--llm` แต่แก้ไว้ก่อนกัน
ปัญหาเดียวกันทันทีที่มีข้อมูลจริง) `moment.dialogue`/`moment.thought` ถูกสร้างจริงตอน Layer 3 สดโดยมี
`[เหตุการณ์ที่เพิ่งเกิด]` เป็น input หลัก (`llm_agent.py:build_prompt()`) แต่ record ที่ export ออกมา
เดิมไม่มีเหตุการณ์นี้เลย — `ctx.recent_memory` (`history`/`memory`) ถูก `memory_retriever.py` กรอง
`e.day < scene.day_start` ตัดเหตุการณ์ปัจจุบันออกไปตั้งใจอยู่แล้ว (กัน "เห็นอนาคต") ผลข้างเคียงคือตัด
ต้นเหตุของบทพูด/ความคิดออกไปด้วย มีแค่ `emotion` (label หยาบ) เป็นเงื่อนงำเดียว — **แก้**: เพิ่ม field
`event` ใหม่ (รูปแบบเดียวกับ `build_prompt()`) เข้า dialogue/monologue record ทั้งคู่

### 17. re-export ครบ + เทรน `loras/v6` (รวมบั๊กข้อ 13-16 ทั้งหมด)
`python build_dataset.py --full` → `datasets/v3` (Dataset A-E ครบ 1,731 ฉาก, ยืนยันแล้วว่า chronicle มี
"ปีที่" ใน input และ planning มี `recent_method_evidence` จริง) + `python build_lessons.py --style-limit 2
--novel-episodes-dir ...` → `datasets/lessons_v1` ใหม่ (story_lesson มี `[ความเข้มข้น=N]` ต่อเหตุการณ์แล้ว
— ดูข้อ 13 ต่อ ด้านล่างเรื่อง escalation grounding เพิ่มเติม)

**ข้อสังเกตเพิ่มเติมจาก story_lesson (ต่อจากปัญหาข้อ 13)**: แม้แก้ foreshadowing แล้ว spot-check ยังพบว่า
`escalation`/`emotional_shift` เรียนไม่เต็มที่ เพราะมาจาก `genome.compute_conflict_level()` ที่อ่าน
`event.deltas["margin"]` (เลขดิบ เช่น 16.514) **ที่ไม่ปรากฏใน `e.text` เลย** — arc_lesson ไม่มีปัญหานี้
เพราะใส่ `conflict_level` เป็นตัวเลขตรงๆ ใน `scene_summaries` อยู่แล้ว (สอดคล้องกับผล spot-check: arc_lesson
4/4 ตรง vs story_lesson 4/6) — **แก้**: `lesson_exporter.py:_story_lesson_record()` เพิ่ม
`[ความเข้มข้น=N]` ต่อท้ายแต่ละเหตุการณ์ใน input โดยเฉพาะ (ไม่แตะ `build_scene_input_payload()` ที่ใช้ร่วม
กับ Dataset A/Shadow Eval เพราะ field นี้ไม่เกี่ยวกับงานของ Dataset A เลย) — ยืนยันด้วย record จริงของฉาก
`0-62` (ฉากที่ v5 เคยทำนายผิด): input ตอนนี้มี `[ความเข้มข้น=100]` ตรงกับ escalation "Peak" ใน ground
truth แล้ว

**เทรน `loras/v6`**: เรียก `train_lora.train()` ตรงๆ (ไม่ผ่าน `autotrain.py` เพราะ `--full` ตั้งใจไม่
อัปเดต `export_state.json` — autotrain จะยังชี้ไปที่ `v2` เดิม) ด้วย `["v3", "lessons_v1"]` (5,003
ตัวอย่าง) `epochs=5` เหมือน v3-v5 — บันทึกผลลง `datasets/train_state.json` เองหลังเทรนเสร็จเพื่อให้
`autotrain.py` เห็นประวัติครบถ้วนในอนาคต

**ผลจริง `loras/v6`**: `eval_loss` 0.00730→0.00488→**0.00484 (ต่ำสุด, epoch 3)**→0.00510→0.00537 —
ต่ำกว่า `v5` (0.0174) อีกเกือบ 4 เท่า สอดคล้องกับที่ข้อมูลกราวด์แน่นขึ้นอีกรอบ (255 ฉาก held-out)

**Shadow Evaluation Gate (v6 vs v5, held-out 15/255 ฉากจริง)**: เสมอกันที่เพดานคะแนนอีกครั้ง (100.0/100%
ทั้งคู่) → APPROVE — คำอธิบายเดียวกับรอบ v5: Dataset A (v2→v3) ไม่ได้เปลี่ยนรูปแบบงาน จึงไม่แปลกที่คะแนน
งาน Scene SFT เท่าเดิม ตัวชี้วัดที่มีความหมายจริงสำหรับรอบนี้คือ spot-check ด้านล่าง

**Spot-check ยืนยันว่าบั๊กที่แก้ได้ผลจริง**: รัน generate จริงซ้ำบนฉากเป๊ะๆ 3 ฉากที่ `v5` เคยตอบผิด
(ทั้งหมดยังอยู่ในชุด held-out ของ `v6` พอดี — เทียบตรงๆ ได้):
- `0-644` (escalation ผิดใน v5: "Peak→Low" ที่ควรเป็น "Low→Low") → **v6 ตรงเป๊ะแล้ว**
- `0-62` (escalation/emotion/outcome word ผิดทั้ง 3 จุดใน v5) → **v6 ได้ escalation ("Peak") และ
  outcome word ("รอดตายด้วยชะตา") ถูกแล้ว** เหลือแค่ emotion ("Despair" ที่ควรเป็น "Resolve") ยังพลาด —
  จาก 3 จุดผิดเหลือ 1 จุด
- `1-2945` (foreshadowing ข้ามตัวละคร "เย่เฟย" ใน v5) → **v6 ตรงเป๊ะแล้ว** (foreshadowing ว่างเปล่า
  ถูกต้อง)

เพิ่มตัวอย่างใหม่อีก 5 story_lesson + 4 arc_lesson (สุ่มจาก held-out) — รวมทั้งหมด **10/12 ตรงเป๊ะ (83%)**
ดีขึ้นจากรอบ `v5` (8/10 = 80%) และดีขึ้นชัดเจนที่จุดที่เคยผิดเป๊ะๆ ทั้ง 3 จุด

**ปัญหาใหม่ที่สังเกตเห็น (เล็กน้อย ยังไม่ได้แก้)**: ฉาก `1-4946` (เหตุการณ์เดียว ความเข้มข้นต่ำ) ground
truth ไม่มี foreshadowing แต่ v6 กลับ**เดา**ข้อความ foreshadowing ขึ้นมาเอง ("หานเทียนฝึกอาคมกักกันลม
สำเร็จ") — คนละแบบกับบั๊กเดิม (ไม่ใช่ข้ามตัวละครที่ไม่เกี่ยวข้อง แต่เป็นการ "เติมคำตอบ" ทั้งที่ควรว่างเปล่า)
พบแค่ 1/9 story_lesson ตัวอย่างรอบนี้ — เก็บไว้เป็นข้อสังเกต ยังไม่ใช่เรื่องด่วน

**สรุปรวม**: บั๊กทั้ง 5 ข้อ (13-16 + conflict_level grounding) แก้ได้ผลจริง ยืนยันด้วย eval_loss ที่ลดลง
ต่อเนื่องและ spot-check ที่ตรงเป๊ะกับฉากที่เคยผิดมาก่อน

**อัปเดต — deploy จริงแล้ว**: `hotswap.py --adapter loras/v6 --version v6 --eval-result
datasets/eval_results/eval_20260831T133250Z.json` สำเร็จ (`approved: true` จาก held-out gate) —
`cultivator-brain:v6`/`:latest` อยู่ใน Ollama จริงแล้ว (4.7GB, digest `d21686d95f52`) ยืนยันเรียกจริงผ่าน
`ollama run` ตอบในสไตล์ story_lesson ที่เรียนมาถูกต้อง (Hook/conflict/escalation/Beat/emotion/payoff
ครบรูปแบบ) — ลบ `merged/` (~29GB intermediate) ทิ้งหลัง deploy เสร็จ เหมือนตอน v4

**ข้อควรรู้ (สำคัญ)**: deploy นี้**ไม่ได้เปลี่ยน** `tiandao/ai/config_ai.py:OLLAMA_MODEL` (ยังเป็น
`qwen2.5vl:7b` ตามที่ปัญหาข้อ 1 เปลี่ยนกลับไปแล้วจากหลักฐาน A/B จริง) — `v6` มีข้อจำกัดเดียวกับ `v4` เป๊ะ
(ไม่มี Dataset B/C ในชุดเทรน เพราะโลกนี้ไม่เคยรันด้วย `--llm`) คาดว่า Layer 3 จะยังมีปัญหาเดียวกัน
(JSON parse ไม่เสถียร/CJK หลุด) ถ้าจะทดสอบ `v6` กับงาน Layer 3 สดต้องเปลี่ยน `OLLAMA_MODEL` เองแล้ว
วัดผลจริงอีกรอบก่อนตัดสินใจ ไม่ใช่เปลี่ยนตามที่ `hotswap.py` แนะนำเฉยๆ

### 🚀 Hot-Swap Deploy จริง — `cultivator-brain:latest` ใช้งานได้แล้วจริงใน Ollama

รัน `hotswap.py --adapter loras/v4 --version v4 --eval-result datasets/eval_results/eval_true_holdout_v4.json`
จริง (ใช้ไฟล์ผล held-out test ที่น่าเชื่อถือจริง ไม่ใช่ไฟล์จาก `evaluate_model.py` ที่ปนเปื้อนความจำ) —
Gate ตรวจผ่าน (`approved: true`) → merge LoRA เข้า Qwen2.5-7B-Instruct เต็มจริง (bf16, CPU) → แปลง
GGUF จริง → `ollama create -q q4_K_M` → `ollama cp` → **สำเร็จจริงทั้งหมดใน 11 นาที 48 วินาที**

**ยืนยันจริงใน Ollama**: `ollama list` เห็น `cultivator-brain:v4` และ `cultivator-brain:latest` (4.7GB
ทั้งคู่ ชี้ digest เดียวกัน) — `ollama run cultivator-brain:latest` ตอบข้อความไทยจริงได้ (ทดสอบด้วย
prompt แบบสั้นที่ไม่ตรงฟอร์แมต ChatML เป๊ะ โมเดลตอบในสไตล์ StoryLesson ที่เรียนมาจาก multi-task
training จริง ยืนยันว่าโมเดลที่ deploy คือตัวที่เทรนจริง ไม่ใช่ base model เปล่า) — ลบไฟล์ intermediate
ขนาดใหญ่ (`merged/`, ~29GB) ทิ้งแล้วหลัง deploy เสร็จ (ข้อมูลถูก bake เข้า Ollama model แล้ว ไม่ต้องเก็บซ้ำ)

**อัปเดต — ผู้ใช้สั่งเปลี่ยนแล้ว**: `tiandao/ai/config_ai.py:OLLAMA_MODEL` เปลี่ยนจาก `qwen2.5vl:7b`
เป็น `cultivator-brain:latest` จริงตามคำสั่ง — คอมเมนต์ในโค้ดบันทึกไว้ชัดเจนว่าเปลี่ยนกลับได้ทันที
(แค่ค่า string เดียว) ถ้าคุณภาพแย่ลง

**ทดสอบจริง**: เรียก `OllamaAgent().chat()` ตัวเดียวกับที่ `BrainManager`/Layer 3 ใช้จริง (ผ่าน
`llm_agent.build_prompt()` กับตัวละคร/เหตุการณ์จริงจาก `tiandao/world.save`) — **ทำงานได้เชิงกลไก**
(parse JSON `{"dialogue","thought"}` สำเร็จ ไม่ crash) **แต่พบปัญหาคุณภาพจริงที่ตรงกับปัญหาเดิมที่เคย
บันทึกไว้แล้ว**: `thought` ที่ตอบมามีอักษรจีนหลุดปน (`"...ต้อง时刻保持警惕"`) ตรงกับปัญหาข้อ 2 เดิม (CJK
หลุดปนจาก qwen2.5vl ตอน Phase 6) — เป็นไปได้ว่าเป็นพฤติกรรมที่สืบทอดมาจากตระกูล Qwen2.5 เอง (ฐานของ
`loras/v4` ก็คือ Qwen2.5-7B-Instruct) ไม่ใช่ปัญหาใหม่จาก LoRA โดยตรง — **ยังไม่ได้ประเมินเชิงคุณภาพ
เทียบกับ `qwen2.5vl:7b` เดิมอย่างเป็นระบบ** (แค่ smoke test 1 ครั้ง) เก็บไว้เป็นข้อสังเกตให้ผู้ใช้ตัดสินใจ
เองว่าจะเปลี่ยนกลับหรือไม่หลังใช้งานจริงสักพัก

---

## ไฟล์ทั้งหมดที่เพิ่ม/แก้

**ใหม่ (Cultivator Brain v2)**: `daemon.py`, `dashboard.py`, `generate_episode.py`,
`templates/dashboard.html`, `tiandao/persist.py`, `tiandao/seasons.py`, `tiandao/ai/` (ทั้งโฟลเดอร์:
`__init__.py`, `brain.py`, `config_ai.py`, `event_bus.py`, `goap.py`, `history.py`, `llm_agent.py`,
`memory.py`, `utility.py`)

**ใหม่ (Narrative Dataset Factory)**: `build_dataset.py`, `narrative_factory/` (ทั้งโฟลเดอร์:
`__init__.py`, `config.yaml`, `parser.py`, `genome.py`, `scene_extractor.py`, `context_builder.py`,
`memory_retriever.py`, `validator.py`, `scoring.py`, `tagger.py`, `exporter.py`, `versioning.py`,
`incremental.py`)

**ใหม่ (Closed-Loop Flywheel — Phase G)**: `tiandao/event_log.py`, `tiandao/ai/llm_queue.py`

**ใหม่ (Closed-Loop Flywheel — Phase H)**: `narrative_factory/dataset_formatter.py`, `train_lora.py`,
`autotrain.py`

**ใหม่ (Closed-Loop Flywheel — Phase I)**: `narrative_factory/dpo_builder.py`, `build_dpo_pairs.py`

**ใหม่ (Closed-Loop Flywheel — Phase J)**: `narrative_factory/shadow_eval.py`, `evaluate_model.py`,
`merge_lora.py`, `hotswap.py`, `vendor_llama_cpp_convert/` (vendor จาก `ggml-org/llama.cpp`,
MIT license — ไม่ใช่โค้ดของโปรเจกต์เอง เข้า `.gitignore` แล้ว)

**ใหม่ (Phase K)**: `narrative_factory/teacher.py` (K1), `narrative_factory/pacing.py` (K2),
`narrative_factory/hook_detector.py` (K3), `narrative_factory/payoff_detector.py` (K4),
`narrative_factory/arc_builder.py` (K5), `narrative_factory/style_distill.py` (K6),
`narrative_factory/lesson_exporter.py` + `build_lessons.py` (K7)

**แก้ (Phase K ต่อ)**:
- `narrative_factory/scoring.py` — Shadow Evaluation V2: แทนที่ `WEIGHTS`/`PASS_THRESHOLD` ทั้งชุด
  (Timeline/Character/Event/Memory/Style/**Pacing** ใหม่, ผ่านที่ 85) เพิ่ม `_pacing_score()`,
  `score_candidate()` รับ `scene: Optional[Scene] = None` เพิ่ม
- `narrative_factory/exporter.py`, `narrative_factory/shadow_eval.py`, `narrative_factory/pipeline.py`
  — ส่ง `scene=scene` ให้ `score_candidate()` ใหม่ทั้ง 3 จุด
- `narrative_factory/config.yaml` — `dpo_chosen_threshold` 85→90 (กันชนกับ `PASS_THRESHOLD` ใหม่ที่
  ก็เป็น 85 เหมือนกันพอดี), เพิ่ม `hook_by_kind` (K3), `arc_merge_window_days` (K5)
- `narrative_factory/dataset_formatter.py` — เพิ่ม `_fmt_passthrough()` + ลงทะเบียน
  `story_lesson.jsonl`/`arc_lesson.jsonl`/`style_lesson.jsonl` (K7 Multi-Task Training)
- `autotrain.py` — เพิ่ม `lessons_v1` เข้า version list เองถ้าโฟลเดอร์นี้มีอยู่จริง (K7)

**แก้ (K1-K6 เพิ่มเติม)**:
- `tiandao/ai/config_ai.py` — `OLLAMA_MODEL` เปลี่ยนจาก `qwen2.5vl:7b` เป็น `cultivator-brain:latest`
  ตามคำสั่งผู้ใช้หลัง Hot-Swap deploy จริง (Layer 3 บทพูด/ความคิดตัวละครสด — ยังไม่เคยพิสูจน์เชิงคุณภาพ
  เป็นระบบ พบ CJK หลุดปนจาก smoke test 1 ครั้ง ตรงกับปัญหาเดิม ไม่ใช่บั๊กใหม่)
- `narrative_factory/config.yaml` — เพิ่ม `hook_by_scene_type`/`conflict_type_by_scene_type` (K1)
- `narrative_factory/teacher.py` — `analyze_pacing()` เรียก `pacing.py` จริงแทนฮิวริสติกชั่วคราว (K2),
  `analyze_hook()`/`analyze_payoff()` เรียก `hook_detector.py`/`payoff_detector.py` แทน logic เดิม
  ในตัว (K3/K4) — ไม่มี logic ซ้ำระหว่างไฟล์
- `tiandao/ai/llm_agent.py` — เพิ่ม `num_ctx` parameter (optional, ดีฟอลต์ `None` = พฤติกรรมเดิม) ให้
  `OllamaAgent.complete()`/`_post_chat()` (K6 — แก้บั๊กจริง Ollama ตัด context เหลือ 4096 token เป็น
  ดีฟอลต์เสมอไม่ว่าโมเดลรองรับยาวแค่ไหน กระทบทุก caller ที่ prompt ยาวเกิน 4096 token ในอนาคต)
- `train_lora.py` — เพิ่ม held-out eval split (`eval_ratio`), `EarlyStoppingCallback` +
  `load_best_model_at_end`, cosine LR + `warmup_steps` (คำนวณเองเพราะ transformers 5.15.0 ตัด
  `warmup_ratio` ออกแล้ว) — **แก้บั๊กจริงร้ายแรงใน `ChatDataset.__getitem__()`**: เพิ่ม
  `MIN_COMPLETION_TOKENS` กันไม่ให้ prompt ที่ยาวเกิน `max_length` (เจอกับ record chronicle) ตัด label
  คำตอบทิ้งทั้งหมดจนเป็น `NaN` (เจอจริง 6/5,003 ตัวอย่าง — แก้แล้วเหลือ 0)
- `narrative_factory/exporter.py` — เพิ่ม `build_scene_input_payload()` ใส่เลข `day` เข้า
  `input.events` (แก้ปัญหาข้อ 12 — spurious correlation), `shadow_eval.py:_scene_input_payload()`
  แก้ให้ delegate ไปฟังก์ชันเดียวกัน ไม่ duplicate — re-export เป็น `datasets/v2/` แทน `v1` เดิม
  (ลบ `v1` ทิ้งแล้ว มีบั๊กจริง), อัปเดต `export_state.json` ให้ชี้ `v2`

**แก้ (Phase G-J เดิม)**:
- `run.py` — flag `--save/--resume/--llm`, เรียก `drain_llm_queue()` หลัง `sim.run()` (Phase G)
- `tiandao/sim.py` — event bus hook, utility/GOAP hook, season hook, `d["margin"]`/`d["winner"]` ที่
  7 จุดต่อสู้, `place=a.place`/`realm=a.realm` ใน `emit()`, ย้าย `self.seq += 1` เข้า `emit()`,
  `random.choice`→`rng.choice` ที่บล็อกภัยพิบัติ (Phase G — แก้ non-determinism)
- `tiandao/models.py` — เพิ่ม `Event.place`/`Event.realm` (+ `__setstate__` backward-compat)
- `tiandao/intent.py` — extract `sample_weighted()` ออกจาก `choose()` (refactor เล็กๆ พฤติกรรมเดิม)
- `tiandao/ai/brain.py` — `BrainManager` เพิ่ม `llm_queue`/`drain_llm_queue()` + `__setstate__` ใหม่
  (Phase G), `on_event()` เปลี่ยนจากเรียก Ollama ตรงเป็น enqueue
- `daemon.py` — `--keep-recent-events`/`--event-log-path`/`--no-trim-log`/`--llm-drain-budget` (Phase G)
- `narrative_factory/parser.py`, `narrative_factory/pipeline.py`, `tiandao/ai/history.py`,
  `generate_episode.py`, `build_dataset.py` — รับ `event_log_path` เพื่อ merge ประวัติเต็มกับ sidecar
  log (Phase G)
- `.gitignore` — `tiandao/world.save`, `tiandao/world.save.events.jsonl`, `datasets/`, `loras/` (Phase H)
- `narrative_factory/exporter.py` — `_validated_or_fallback()`/`build_dataset_a()` คืน `CandidateOutcome`
  พร้อมคะแนน+violations ของ candidate ที่ reject แทนที่จะทิ้งไป, `export_all()` เขียน
  `rejected_candidates.jsonl` เพิ่ม (Phase I)
- `narrative_factory/config.yaml` — เพิ่ม `dpo_chosen_threshold: 85` (Phase I — แยกจาก
  `PASS_THRESHOLD=80` เดิมของ `scoring.py`; ปรับเป็น 90 ภายหลังตอน Phase K — ดูหัวข้อ Shadow
  Evaluation V2 ด้านบน)
- `build_dataset.py` — `--full` เลิกเรียก `INC.record_export`/`INC.save_state` (Phase I — แก้บั๊กจริง
  ที่เจอตอนทดสอบ: รัน `--full` ซ้ำทำให้ `export_state.json` นับฉากเดิมซ้ำเป็นฉากใหม่ พองจำนวนที่
  `autotrain.py` ใช้ตัดสินใจเทรน)
- `narrative_factory/dataset_formatter.py` — extract `build_scene_messages()` ออกจาก `_fmt_scene_sft()`
  ให้ `shadow_eval.py` (Phase J) ใช้ prompt เดียวกับตอนเทรนเป๊ะ (refactor เล็กๆ พฤติกรรมเดิม)
- `.gitignore` — เพิ่ม `merged/`, `vendor_llama_cpp_convert/`, `*.gguf` (Phase J)

**ไม่แตะเลย**: `tiandao/rules.py`, `tiandao/events.py`, `tiandao/clans.py`, `tiandao/places.py`,
`tiandao/skills.py`, `autotune.py`, `tiandao/tuning.py`, `tiandao/metrics.py`, `tiandao/chronicle.py`,
`tiandao/story.py`, `dashboard.py`
