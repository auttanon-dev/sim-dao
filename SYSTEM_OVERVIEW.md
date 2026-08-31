# วิถีสวรรค์ (Sim Dao Engine) — ภาพรวมระบบทั้งหมด

เอกสารนี้อธิบาย**สถาปัตยกรรมปัจจุบันทั้งหมด**ของโปรเจกต์ ไม่ใช่ log การพัฒนาตามลำดับเวลา (ดูนั่นได้ที่
`CULTIVATOR_BRAIN_STATUS.md`/`CULTIVATOR_BRAIN_STATUS_PHASE_K.md`/`LOCATION_GRAPH_STATUS.md`) — เขียน
ขึ้นเพื่อให้เห็นภาพรวมทั้งระบบในการวิเคราะห์ครั้งเดียว อ้างอิง `SPEC.md` (เอกสารออกแบบกลไกดั้งเดิม) เป็น
หลักสำหรับกฎเกมแกนกลาง แต่ปรับให้ตรงกับโค้ดจริงปัจจุบัน (ภูมิศาสตร์ขยายจาก 80 เป็น 102 แห่งแล้ว
เป็นต้น)

**ระบบทั้งหมดแบ่งเป็น 5 ชั้น ทำงานแยกอิสระ ต่อกันเป็น pipeline ทางเดียว**:

```
[1] เอนจินซิมหลัก (ตัวเลขล้วน ไม่มี AI)
      ↓ world.save (pickle) + sim.log/events.jsonl
[2] ระบบ AI หลายชั้น + ระบบเดินทาง (เสียบเข้าเอนจินเดิม, ผลกระทบต่อพฤติกรรมจริง)
      ↓ world.save เดียวกัน (มีผลจากพฤติกรรม AI/การเดินทางแล้ว)
[3] Narrative Dataset Factory (offline, อ่าน world.save/log แปลงเป็น training data)
      ↓ datasets/v{N}/*.jsonl + datasets/lessons_v1/*.jsonl
[4] Closed-Loop Flywheel (เทรน LoRA จากข้อมูล → ประเมิน → deploy)
      ↓ loras/v{N}/ → cultivator-brain:v{N} ใน Ollama
[5] (ยังไม่เริ่ม) Map Viewer — mapgen4-style WebGL แสดงกราฟภูมิศาสตร์จาก [2]
```

---

## 1. เอนจินซิมหลัก (`tiandao/`)

**ตัวเลขล้วน ไม่มี LLM/AI เลยในชั้นนี้** — deterministic 100% ด้วย seed เดียว (สองแสนเหตุการณ์ ≈
50 วินาทีบนเครื่องทั่วไป) กฎออกแบบละเอียดอยู่ใน `SPEC.md` — สรุปเชิงสถาปัตยกรรมที่นี่:

### กลไก tick/event loop (`tiandao/sim.py`)

**ไม่ใช่ fixed loop ต่อวัน** — เป็น global `heapq` เดียวคีย์ด้วย `(day, cid)` ต่อ "เทิร์นถัดไปของตัวละคร
คนนั้น" `Sim.schedule(ch, gap)` เป็นกลไก schedule ตัวเดียวทั้งระบบ หนึ่ง `step()` = pop ตัวละครหนึ่งคน
จากคิว → ตัดสินใจ → resolve ผลจริงทันที (synchronous) → schedule เทิร์นถัดไป (`gap` วันข้างหน้า จาก
`EVENT_TABLE`) — **หนึ่ง tick = หนึ่งเหตุการณ์ ไม่ใช่หนึ่งหน่วยเวลา** ตัวละครแต่ละคนมี `gap` ต่างกันมาก
(20-400 วันไปจนถึง 2000-12000 วันสำหรับเจ้าโกลาหลที่ตาย) ทำให้ `self.day` (นาฬิกากลาง) ก้าวไม่สม่ำเสมอ

**การตัดสินใจ (3 ชั้น, `tiandao/intent.py`)**:
1. `IN.weigh()` — น้ำหนักฐานจากอาชีพ/นิสัย + override เอาตัวรอด (decay/fate วิกฤต) + โบนัสตามสถานที่
   (ยืนอยู่ตลาดอยากค้าขาย, ช่างไม่มีเตาอยากเดินทางหาเตา) + โบนัสสถานการณ์ (ศัตรู/หนี้ค้าง/ข่าวลือ) +
   bias จากประสบการณ์ส่วนตัว (EMA ของผลลัพธ์ที่เคยเจอ)
2. `brain_manager.decide()` — ชั้น AI เสริม (ส่วนที่ 2 ด้านล่าง) ปรับน้ำหนักซ้ำอีกที
3. `IN.sample_weighted()` — สุ่มถ่วงน้ำหนักเลือกจริง แล้วส่งเข้า `Sim.resolve()` (dispatcher ยักษ์
   `if k == "...":`) ที่ mutate state จริงตาม event kind ที่เลือก

### โมเดลข้อมูล (`tiandao/models.py`)

- **`Character`** — ~90 fields: สายเลือด 4 สัดส่วน (มนุษย์/วิญญาณ/อสูร/มาร), `realm`/`tier` (ขั้น/ชั้นโลก),
  `insight`/`refine` (สะสมสองด่าน), `inner` (จิตมาร), เศรษฐกิจ (`money`/`mat_stock`/`items`),
  ความสัมพันธ์ (`rivals`/`bonds`/`debts`), `place`/`travel_dest`/`travel_arrival_day` (ตำแหน่ง — ดู
  ส่วนที่ 3), `hidden`/`return_day` (สถานะไม่ทำงานยาว เช่น เจ้าโกลาหลตาย/ซ่อนตัว)
- **`Event`** — `seq`/`day`/`kind`/`actor`/`target`/`outcome`/`text`/`deltas`/`place`/`realm` —
  ทุกเหตุการณ์ที่เกิดขึ้นจริงถูก log เป็น `Event` (ผ่าน `Sim.emit()`) เข้า `sim.log` — นี่คือ "Chronicle"
  ที่ Narrative Dataset Factory (ส่วนที่ 4) อ่านย้อนหลังทั้งหมด
- **`World`** — แทนแต่ละชั้นฟ้า (`tier`, `place_key`, คลังฟ้า `heaven_bank`, ยุค `era`, ภัยพิบัติ)

### กฎเกมแกนกลาง (รายละเอียดเต็มใน `SPEC.md`)

ขั้นบำเพ็ญไต่ไม่ย้อนกลับ, หลายโลกซ้อนชั้น (`TIER_STEP`), สายเลือด 4 สัดส่วนกำหนดกลไกงอกเอง, เลื่อนขั้น
ผ่าน 2 ด่าน (พลัง+จิตมาร), **บัญชีพลังฟ้า** (heaven treasury — ไหลเข้าจากสามัญชน ไหลออกตอนข้ามขั้น
คืนกลับตอนตาย รั่วถาวรตอนข้ามฟ้า — คลังต่ำ = ยุคเสื่อม), แดนลับ (คลังปิดผนึกหลังตาย/ซ่อนตัว), สมบัติฟ้า
ดิน 24 ชิ้นมีชื่อ, เผ่าโกลาหล (บุกโลกมนุษย์ทำลายสถานที่ 80 ปี, เจ้าโกลาหลไม่มีวันตายจริง แค่หายไปแล้ว
กลับมาแข็งขึ้น), องค์กร/ตระกูล (มีไส้ศึก 12%, จำความแค้นข้ามรุ่น), สายช่าง 9 ขั้น (หลอมยา/อาวุธจากแร่+
สมุนไพร 30 ชนิด), ประตูมิติ 5 บาน (ลงโลกล่างเสียขั้น มีค่าผ่านทาง)

**ภูมิศาสตร์ — ขยายจาก 80 เป็น 102 แห่งแล้ว** (`tiandao/places.py`): 6 กลุ่ม `world_key` —
`0`=โลกมนุษย์(20), `1`=แดนเซียน(22), `2`=สวรรค์นอกชั้นฟ้า(22), `mara`=แดนมาร(20, ใหม่กว่า SPEC.md เดิม
ที่นับรวมไว้แล้ว), `siam`=แดนสยาม(13, **ใหม่ทั้งหมด** ไม่มีใน SPEC.md), `chaos`=ที่กบดานเผ่าโกลาหล(5,
**ใหม่ทั้งหมด**) — `siam`/`chaos` ไม่มีอยู่ตอนเขียน `SPEC.md` ครั้งแรก แต่ละแห่งมีบทบาทจริง (แหล่ง
วัตถุดิบ/เตาหลอม/ลานฝึก/ตลาด) ไม่ใช่แค่ชื่อประดับ

**เครื่องมือรัน**: `python run.py --seed N --events N` (ครั้งเดียวจบ), `python daemon.py
--chunk-events N --iterations N` (เดินต่อเนื่องหลายรอบ + ปรับค่าคงที่เอง + trim log กันไฟล์บวม —
Phase G), `python dashboard.py` (ดูสถานะสดคู่กับ daemon)

---

## 2. ระบบ AI หลายชั้น — "Cultivator Brain v2" (`tiandao/ai/`)

เสียบเข้าเอนจินเดิมแบบ **ไม่แก้พฤติกรรมเดิม** (แค่ boost น้ำหนักที่คำนวณมาแล้ว ไม่เคยบังคับ) — ประวัติ
การตัดสินใจ/เหตุผลออกแบบเต็มอยู่ใน `CULTIVATOR_BRAIN_STATUS.md` ส่วนที่ 2 สรุปสถาปัตยกรรมที่นี่:

- **Layer 1 — Utility AI** (`utility.py`) — Need 7 แบบ (Escape/Meditate/Breakthrough/Revenge/Wealth/
  Reputation/DaoPursuit) คำนวณจาก field ที่มีอยู่แล้วบน `Character` — ยืนยันผลจริง: advancement_rate
  ขยับจาก ~0.20-0.24 → 0.26-0.29
- **Layer 2 — Hierarchical GOAP** (`goap.py`) — decompose เฉพาะ Goal "Breakthrough" เป็น 4 วิธีหา
  ยา (หลอมเอง/ซื้อ/ประมูล/ปล้น) ตาม precondition จริงจาก state ตัวละคร
- **Layer 3 — Local LLM Agent** (`llm_agent.py`, ผ่าน Ollama) — trigger เฉพาะ event "น่าจดจำ"
  (ทรยศ/ประลอง/ล้างแค้น/ข้ามขั้น ฯลฯ) สร้างบทพูด+ความคิดตัวละคร เป็น blocking HTTP call จึงมีคิวแยก
  ไม่บล็อก sim loop (`llm_queue.py`, Phase G) — **ปิดเป็นค่าเริ่มต้น** (`LLM_ENABLED=False`) เปิดผ่าน
  `--llm`
- **Memory System** (`memory.py`) — episodic (เพดาน 30/คน), semantic ต่อสถานที่ (EMA danger/fortune),
  relationship (อ่านจาก `rivals`/`bonds` เดิมตรงๆ), reputation (`{region: {fame, notoriety}}`)

**สถานะ deploy ปัจจุบัน**: `tiandao/ai/config_ai.py:OLLAMA_MODEL = "qwen2.5vl:7b"` (**ไม่ใช่**
`cultivator-brain:latest`) — เปลี่ยนกลับหลังพิสูจน์ด้วย A/B จริงว่า LoRA ที่เทรนเอง (v4/v6) แย่กว่า
สำหรับงานนี้เฉพาะ (JSON parse ไม่เสถียร 84% vs 100%, CJK หลุดปนมากกว่า) เพราะไม่เคยเห็นตัวอย่างงาน
dialogue/thought ตอนเทรนเลย (Dataset B/C ว่างเปล่า — ดูส่วนที่ 4)

---

## 3. ระบบเดินทาง/ภูมิศาสตร์จริง (`tiandao/geo.py`, `tiandao/travel.py`) — เพิ่มล่าสุด

รายละเอียดเต็มอยู่ใน `LOCATION_GRAPH_STATUS.md` — สรุปสั้น: เดิมตัวละครเปลี่ยนที่อยู่แบบ teleport
ทันที (`a.place = rng.choice(...)`) ไม่มีระยะทาง/เวลาเดินทางจริงเลย ตอนนี้แก้แล้ว:

- `tiandao/geo.py` (generated, ห้ามแก้มือ) — พิกัด 2 มิติของทั้ง 102 แห่ง + กราฟถนนจาก Delaunay
  triangulation (กรอง edge ข้าม `world_key` ทิ้ง เหลือแค่ 5 ประตูมิติจริงเป็นทางเชื่อมข้ามโลก) —
  **ออกแบบให้พิกัด/mesh นี้ใช้ต่อกับ mapgen4 viewer ได้ตรงๆ ในอนาคต** (Delaunay mesh คือโครงสร้างข้อมูล
  หลักของ mapgen4 อยู่แล้ว)
- `tiandao/travel.py` (pure stdlib, ไม่พึ่ง scipy/numpy ตอน runtime) — Dijkstra หาระยะทาง/เวลาเดินทาง
  จริง ปรับตามขั้นบำเพ็ญ (`realm` สูง = เร็วขึ้น)
- ผูกเข้า event loop เดิมโดย reuse pattern `hidden`+`return_day` ที่มีอยู่แล้ว (ไม่ใช่กลไกใหม่แยกขาด) —
  ตัวละครเดินทางจริงหลายวัน มีโอกาสเจอเหตุการณ์ระหว่างทาง (พบของ/ถูกปล้น/บาดเจ็บ ถึงตายได้จริง)

**ยังไม่ทำ**: ประตูมิติ (`"ลงโลกล่าง"`) กับการหนีตอนเผ่าโกลาหลบุกยังคง teleport ทันทีเหมือนเดิม
(ตัดสินใจเว้นไว้ตั้งใจ), map viewer (WebGL/mapgen4 จริง) ยังไม่เริ่มเลย

---

## 4. Narrative Dataset Factory (`narrative_factory/`)

**Offline ทั้งหมด** — โหลด `world.save`/log ที่เซฟไว้แล้วมาแปลงเป็น training dataset ไม่รบกวนซิมสด
Pipeline เรียงเป็นขั้น (A-F ตาม `ROLE (1).md` เดิม):

```
sim.log/events.jsonl (parser.py)
  → ParsedEvent (scene_type มาตรฐาน จาก config.yaml, ไม่ hardcode)
  → คลัสเตอร์เป็น Scene (scene_extractor.py, ผู้เล่นร่วมกัน+ห่างกัน ≤3 วัน)
  → Narrative Genome ต่อฉาก (genome.py: conflict_level จาก margin จริง, foreshadowing ค้นย้อนหลัง
    เฉพาะเหตุการณ์ที่เกี่ยวข้องกับฉากจริงเท่านั้น — แก้บั๊กข้ามตัวละครที่ไม่เกี่ยวข้องแล้วเซสชันนี้)
  → Character Context (context_builder.py: Realm/Dao/Personality/Relationship/Reputation/Goal/Emotion,
    Memory Retriever คัด "เกี่ยวข้องจริง" ไม่ยัดทั้งชีวิต)
  → Quality Validator + Scoring (validator.py/scoring.py: 6 กฎแข็ง — ห้ามตัวละครใหม่/เหตุการณ์
    แต่งขึ้น/ลำดับเวลาผิด/ชื่อผิด/Realm ผิด/ความสัมพันธ์ผิด — ผิดข้อไหนก็ reject ทันที + คะแนน 6 มิติ
    Timeline/Character/Event/Memory/Style/Pacing ต้อง ≥85)
  → Export (exporter.py): Dataset A (Scene SFT) / B (Dialogue) / C (Monologue) / D (Chronicle) /
    E (Planning) → datasets/v{N}/*.jsonl (incremental versioning, build_dataset.py)
  → Lesson Export (Phase K, teacher.py/arc_builder.py/style_distill.py/lesson_exporter.py):
    Story Lesson (โครงสร้างการเล่าเรื่องต่อฉาก) / Arc Lesson (เส้นทางตัวละครข้ามหลายฉาก) /
    Style Lesson (วิเคราะห์รูปแบบจาก Novel_Episodes จริง ผ่าน LLM + กันคัดลอกด้วย n-gram check) →
    datasets/lessons_v1/*.jsonl (build_lessons.py)
```

**ข้อจำกัดที่รู้อยู่แล้ว**: Dataset B/C ว่างเปล่าเสมอถ้าไม่เคยรันซิมด้วย `--llm` (ไม่ปั้นบทพูดปลอม) —
world ปัจจุบันไม่เคยรันแบบนั้น ยังว่างอยู่

**บั๊กใหญ่ที่เจอและแก้ทั้งหมดในเซสชันนี้** (รายละเอียดเต็ม `CULTIVATOR_BRAIN_STATUS.md` ข้อ 12-16):
ทุก dataset (A/D/E + Story/Arc Lesson) เคยมี spurious correlation — output อ้างอิงข้อมูล (เลขวันที่/
เลขปี/หลักฐานการตัดสินใจ/conflict_level ดิบ) ที่**ไม่อยู่ในฝั่ง input เลย** ทำให้โมเดลเรียนไม่ได้จริง
ต้องเดาสุ่ม — แก้ครบทุกจุดแล้ว ยืนยันด้วย eval_loss ที่ลดลงจริงและ spot-check ที่ตรงกับ ground truth
มากขึ้นชัดเจน

---

## 5. Closed-Loop Self-Learning Flywheel

```
datasets/v{N} + lessons_v1 (dataset_formatter.py แปลงเป็น ChatML รวมกัน — Multi-Task Training)
  → train_lora.py (QLoRA 4-bit, transformers+peft+bitsandbytes ตรงๆ ไม่ใช้ Unsloth/TRL เพราะ
    torch nightly build เข้ากันไม่ได้) — เทรนจนลู่เข้าจริง (held-out eval split + early stopping +
    cosine LR) autotrain.py เป็นตัวเรียกอัตโนมัติเมื่อฉากสะสมใหม่ครบโควต้า
  → held_out_scene_ids.json (ข้อ 3 เซสชันนี้ — บันทึกจริงว่าฉากไหนกันไว้เป็น validation ตอนเทรน
    ให้ evaluate_model.py ใช้ประเมิน generalization จริงได้อัตโนมัติ ไม่ต้องทำ manual)
  → evaluate_model.py — Shadow Evaluation Gate: เทียบ candidate LoRA กับ baseline บนฉาก held-out
    จริง ผ่าน Phase D Validator/Scoring ตัวเดียวกับตอน export อนุมัติเฉพาะ mean_score ≥ baseline
  → hotswap.py — merge_lora.py (bf16 เต็ม บน CPU) → convert_hf_to_gguf.py (vendor จาก llama.cpp,
    MIT license) → ollama create -q q4_K_M → ollama cp เข้า cultivator-brain:latest
  → build_dpo_pairs.py (Phase I, แยกต่างหาก) — จับคู่ Chosen (ผ่านเกณฑ์)/Rejected (ไม่ผ่าน) ของ
    scene_id เดียวกันจากคนละรอบ export สร้างคู่ DPO ได้ (ยังไม่ได้ใช้เทรนจริงด้วย DPO)
```

**LoRA versions ที่มีอยู่ (`loras/v1`-`v6`)**: v1-v3 ถูก Shadow Gate ปฏิเสธ (smoke test สั้นไป / ข้อมูล
มี spurious correlation) — v4 ผ่าน Gate จริงเป็นตัวแรก (แก้ Dataset A แล้ว) — v5 เทรนด้วย
story/arc/style lesson ที่แก้ spurious correlation แล้ว (eval_loss ต่ำกว่า v4 ~4 เท่า) — **v6 คือ
เวอร์ชันล่าสุด** เทรนด้วยข้อมูลที่แก้ครบทุกบั๊ก (foreshadowing/chronicle/planning/dialogue grounding)
**deploy จริงแล้วเป็น `cultivator-brain:latest` ใน Ollama** แต่ Layer 3 สด (ส่วนที่ 2) ยังไม่ได้ใช้
เพราะช่องว่าง Dataset B/C เดิม

---

## 6. สถานะปัจจุบัน (สรุปรวม ณ ตอนเขียนเอกสารนี้)

| ส่วน | สถานะ |
|---|---|
| เอนจินซิมหลัก | ทำงานสมบูรณ์ deterministic ยืนยันแล้ว |
| ระบบเดินทางจริง | ทำงานสมบูรณ์ ทดสอบ end-to-end แล้ว (departure/en-route/arrival จริง) |
| AI Layer 1-2 (Utility/GOAP) | ใช้งานจริงเสมอ (ไม่ปิดได้) ยืนยันผลกระทบจริงแล้ว |
| AI Layer 3 (LLM สด) | ปิดเป็นค่าเริ่มต้น ใช้ `qwen2.5vl:7b` เมื่อเปิด (ไม่ใช่ LoRA ของโปรเจกต์เอง) |
| Narrative Dataset Factory | ทำงานสมบูรณ์ทุก dataset ยกเว้น B/C (ว่างเปล่าตามดีไซน์) |
| LoRA ล่าสุด (v6) | เทรน+ประเมิน+deploy สำเร็จ แต่ยังไม่ได้ใช้งานจริงใน Layer 3 |
| world.save ปัจจุบัน | สร้างใหม่ 31 ส.ค. 2026 — 6,616 ตัวละคร (มีชีวิต 888), 119,058 เหตุการณ์, 37,916 ฉาก, 657 ปีจำลอง (seed=1) — มีข้อมูลเดินทางจริง 15,114 เหตุการณ์ในนั้นแล้ว |
| Map viewer (mapgen4) | ยังไม่เริ่ม — มีแค่ข้อมูลพิกัด/mesh พร้อมใช้ (`tiandao/geo.py`) |

**ไฟล์อ้างอิงละเอียดเพิ่มเติม**: `SPEC.md` (กฎเกมแกนกลาง), `CULTIVATOR_BRAIN_STATUS.md` +
`CULTIVATOR_BRAIN_STATUS_PHASE_K.md` (ประวัติ/เหตุผลการตัดสินใจของ AI+dataset factory+flywheel ทั้งหมด
แบบละเอียดที่สุด), `LOCATION_GRAPH_STATUS.md` (ระบบเดินทาง แบบละเอียดที่สุด รวมบันทึกอุบัติเหตุ
world.save)
