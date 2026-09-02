# สถานะระบบ Sim Dao — ปัจจุบัน

> อัปเดต 3 ก.ย. 2026 (commit `d7ce154`) — เอกสารนี้เน้น **"ตอนนี้มีอะไร ใช้โมเดลอะไร"**
> ตัวเลขทุกตัวในเอกสารนี้ดึงจากโค้ด/ไฟล์จริง ไม่ได้เขียนจากความจำ
>
> ต่างจาก `SYSTEM_OVERVIEW.md` ที่เป็นเอกสารสถาปัตยกรรมเชิงลึก (และ **ล้าสมัยบางส่วนแล้ว** —
> ระบุว่ามี 102 สถานที่ ทั้งที่จริงมี 182 และเขียนไว้ก่อนการเปลี่ยนโมเดลทั้งหมดในวันที่ 2-3 ก.ย.)

---

## 1. โมเดลที่ใช้ — แยกตามหน้าที่

**สำคัญ: ระบบใช้โมเดล 4 ตัว คนละบทบาทกัน** 3 ตัวแรกเป็น "ผู้สอน" (สร้างข้อมูล) ตัวที่ 4 เป็น "ผู้เรียน"

| บทบาท | โมเดล | ตั้งค่าที่ | ใช้ที่ไหน |
|---|---|---|---|
| **Layer 3** — บทพูด/ความคิด JSON | `scb10x/typhoon2.5-qwen3-4b` | `config_ai.OLLAMA_MODEL` | `brain.py:186` |
| **ร้อยแก้ว** — บรรยายตอน/ฉาก | `hf.co/nectec/pathumma-thaillm-8b-think-3.0.0-GGUF:Q4_K_M` | `config_ai.OLLAMA_PROSE_MODEL` | `history.py`, `exporter.py`, `generate_episode.py` |
| **Style Distillation** | `qwen2.5vl:7b` | `config_ai.OLLAMA_STYLE_MODEL` | `build_lessons.py` |
| **ฐานเทรน LoRA** (ผู้เรียน) | `scb10x/typhoon2.5-qwen3-4b` | `--model` ใน `autotrain/train_lora/evaluate_model/merge_lora/hotswap` | HuggingFace weights |

### ทำไมถึงเลือกแบบนี้ (วัดจริง ไม่ได้เดา)

วัดด้วย `tools/ab_full_capability.py` บน prompt จริงจาก `world.save` — **n เท่ากันทุกโมเดล**
(T1=20, T2=30, T3=10, T4=15) ผลเต็มอยู่ใน `out/ab_full_results.json`

| โมเดล | T1 json | T2 gate | T2 คะแนน | T3 style | T4 ตัวอักษร | T4 cjk | T1 วิ/ครั้ง |
|---|---|---|---|---|---|---|---|
| qwen2.5vl:7b *(เดิม)* | 20/20 | 23/30 | 93.3 | **6/10** | 3586 | **34** ⚠️ | 3.4 |
| typhoon2.5-qwen3-4b | 20/20 | 26/30 | 85.0 | 5/10 | 2058 | 0 | **3.2** |
| llama3.1-typhoon2-8b | 18/20 | **30/30** | **95.2** | 3/10 | 843 | 0 | 3.4 |
| pathumma-8b-think | 19/20 | 27/30 | 92.7 | 4/10 | 1856 | 0 | 7.6 |

- `qwen2.5vl:7b` เป็น**ตัวเดียวที่มีอักษรจีนปนในร้อยแก้วไทย** (34 ตัวใน 15 ตอน ตัวอื่น 0 หมด) จึงเลิกใช้ในสองงานหลัก
- คะแนน T2 สูงสุดของ `llama3.1-typhoon2-8b` **ไม่ได้แปลว่าเขียนดีที่สุด** — มันเขียนสั้นมาก (843 ตัวอักษร
  เหมือนกรอกฟอร์ม) เลยไม่มีโอกาสผิดกฎ validator วัด "ตรงข้อเท็จจริง" ไม่ได้วัดสำนวน
- เลือกร้อยแก้วจากการ**อ่านเทียบตัวต่อตัวบนตัวละครเดียวกัน** (`out/episode_compare.json`) ไม่ใช่จากคะแนน

### โมเดลสาย reasoning (Qwen3) ต้องจัดการเพิ่ม

ทั้ง typhoon2.5 และ pathumma เป็น Qwen3 ที่พ่น `<think>...</think>` ออกมาก่อนคำตอบ ถ้าไม่จัดการ
เหตุผลภาษาอังกฤษจะไหลลง dataset ตรงๆ (วัดจริง: ตอนนิยายแรกของ pathumma เป็นภาษาไทยแค่ 39%)

- `llm_agent._post_chat()` เติม `/no_think` อัตโนมัติให้โมเดลใน `ACFG.NO_THINK_MODELS`
- `llm_agent._strip_think()` ตัด `<think>` ทิ้ง รวมกรณีเปิดแท็กค้างไม่ปิด
- มีเทสต์คุม: `test_llm_agent_parsing.py`

---

## 2. ระบบมีอะไรบ้าง

### 2.1 เอนจินซิม (`tiandao/`) — ตัวเลขล้วน ไม่มี LLM

- **182 สถานที่** / **356 เส้นเชื่อม** / **135 วิชา** (ยืนยันจากโค้ดจริง)
- คิวเหตุการณ์เดียว `heapq` คีย์ `(day, cid)` — 1 tick = 1 เหตุการณ์ ไม่ใช่ 1 หน่วยเวลา
- เดินทางจริงด้วย Dijkstra (`travel.py` + `geo.py`) มีเวลาเดินทาง/เหตุการณ์ระหว่างทาง
- เดินในเมืองไปอาคารเป้าหมายจริง (`Sim.route_to_building` + `settlement.py`)

### 2.2 AI 3 ชั้น (`tiandao/ai/`)

| ชั้น | ไฟล์ | สถานะ |
|---|---|---|
| Layer 1 Utility AI | `utility.py` | ใช้งานตลอด ปิดไม่ได้ |
| Layer 2 GOAP | `goap.py` | ใช้งานตลอด (decompose เฉพาะ Goal Breakthrough) |
| Layer 3 LLM | `llm_agent.py` + `llm_queue.py` | **ปิดเป็นค่าเริ่มต้น** (`LLM_ENABLED=False`) เปิดด้วย `--llm` |

### 2.3 Narrative Factory + Flywheel

`sim.log → parser → scene_extractor → genome → context_builder → validator/scoring → exporter`
แล้วต่อด้วย `train_lora → evaluate_model (Shadow Gate) → merge_lora → hotswap`

### 2.4 หน้าเว็บ 5 หน้า (`dashboard.py`)

`/` แดชบอร์ด · `/map` แผนที่ · `/godview` มุมมองพระเจ้า · `/settlement/{idx}` ผังเมือง · `/combat` ประลองยุทธ์
— เชื่อมถึงกันครบทุกหน้าแล้ว และแผนที่มีปุ่มลิงก์ไปผังเมืองของสถานที่ที่เลือกอยู่

---

## 3. ข้อมูลที่มีอยู่ตอนนี้

| ไฟล์ | จำนวน | หมายเหตุ |
|---|---|---|
| `out/bootstrap_v3.save` | 29.5 MB | โลกหลัก — 2,290 narrative moments, คิว LLM ค้าง 5,588 งาน (รันต่อได้ด้วย `--resume`) |
| `datasets/v4/scene_sft.jsonl` | 21,819 | |
| `datasets/v4/dialogue.jsonl` | **1,780** | Dataset B — **ไม่ว่างเปล่าเป็นครั้งแรก** |
| `datasets/v4/monologue.jsonl` | **1,780** | Dataset C — เช่นกัน |
| `datasets/v4/planning.jsonl` | 3,656 | |
| `datasets/lessons_v1/story_lesson.jsonl` | 23,453 | |
| `datasets/lessons_v1/arc_lesson.jsonl` | 17,655 | |
| `datasets/lessons_v1/style_lesson.jsonl` | **4** | ⚠️ **คอขวดหลัก** — ดูข้อ 5 |
| `loras/v1..v6` | 6 เวอร์ชัน | เทรนด้วยฐานเก่า (Qwen2.5-7B) **ใช้ไม่ได้กับฐานใหม่แล้ว** |

**⚠️ `tiandao/world.save` (707 KB) ไม่ใช่โลกจริง** — เป็นไฟล์ทดสอบที่เขียนทับของเดิมไปโดยพลาด
โลกที่ใช้งานจริงคือ `out/bootstrap_v3.save`

---

## 4. เทสต์ (ผ่านหมดทุกตัว)

`test_break` · `test_all_realms` · `test_factions` · `test_godview_export` · `test_immersion_extensions` ·
`test_settlement` · `test_settlement_routing` · `test_llm_agent_parsing` · `test_scheduler_integrity` ·
`tools/test_system_integrity` (9 ชุดใหญ่ในตัวเดียว)

---

## 5. งานที่ยังค้าง (เรียงตามความสำคัญ)

1. **Style Lesson มีแค่ 4 อัน** — นี่คือคอขวดของเป้าหมาย "บรรยายเหมือน Novel_Episodes" ไม่ใช่จำนวน step
   ตอนเทรน มีต้นฉบับ **500 ตอน** รออยู่ รันแล้วได้ประมาณ 215 อัน (reject ~57%)
   ใช้เวลา ~3.7 ชม. — ตอนนี้ `build_lessons.py` เซฟทีละตอนแล้ว หยุดกลางคันไม่เสียงาน
2. **dialogue/monologue ยังเป็นของโมเดลเก่า** — 1,780+1,780 อันสร้างด้วย `qwen2.5vl:7b` ถ้าอยากให้ข้อมูล
   สม่ำเสมอกับ setup ใหม่ ต้องสร้างใหม่ (~2 ชม. คิวค้าง 5,588 งานยังอยู่)
3. **เทรน LoRA v7** — ~8 ชม./epoch บนฐาน 4B (เดิม 13.4 ชม. บน 7B) ยังไม่เคยรันจริง
4. **ปิดลูป** — `evaluate_model` (Shadow Gate) → `hotswap` → เปลี่ยน `OLLAMA_MODEL` เป็น
   `cultivator-brain:latest` ถ้าผ่านเกณฑ์ ตอนนี้ยังไม่มี LoRA ตัวไหนถูกใช้งานจริงเลย

---

## 6. บั๊กสำคัญที่แก้ไปแล้ว (2-3 ก.ย.)

| บั๊ก | ผลกระทบ | commit |
|---|---|---|
| `for ch in living_now` ทับตัวแปรลูปหลักใน `step()` | ทุก ~30 วันจำลอง ตัวละครที่ถูก pop หลุดจากคิวถาวร สะสมจนคิวว่างทั้งที่ยังมีคนเป็นๆ (ซิมหยุดเงียบๆ ที่ ~142,000 tick) | `9b6c89c` |
| `living()`/`living_in()` สแกน `self.cast` ทั้งก้อน | ช้าลงเรื่อยๆ ตามอายุซิม (cast โตไม่มีวันหด) | `9b6c89c` |
| `cid in self.cast` (int เทียบ Character) | เป็น False เสมอ → ระบบรักษาที่หอโอสถ/ส่วนแบ่งอาจารย์/แจกทรัพยากรสำนัก ไม่เคยทำงานเลย | `9b6c89c` |
| `is_notable` OR กับ outcome "สำเร็จ" | 35.6% ของทุกเหตุการณ์กลายเป็นงาน LLM (121,302 งาน = ~4.9 วัน) | `6550021` |
| `_parse_response` ใช้ `json.loads` ตรงๆ | JSON พังนิดเดียวก็เก็บ JSON ดิบเป็น "ความคิด" ของตัวละคร ปนเปื้อน dataset | `9b6c89c` |
| `run.py` drain ทั้งคิวก่อน `--save` | คิวใหญ่เกินไป = ไม่มีวันถึงบรรทัด save (แก้ด้วย `--llm-budget`) | `6550021` |
