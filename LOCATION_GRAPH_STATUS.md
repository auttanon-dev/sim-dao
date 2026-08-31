# Location Graph — สถานะปัจจุบัน

เอกสารนี้สรุประบบเดินทางจริง (location graph + travel mechanics) ที่แทนที่การ teleport แบบเดิม —
ส่วนหนึ่งของแผนใหญ่กว่า (ดู "เป้าหมายเต็ม" ด้านล่าง) ที่ผู้ใช้วางไว้ 4 ข้อ งานรอบนี้ทำแค่ข้อ 1
(location graph) เท่านั้น ยังไม่แตะ viewer/mapgen4 (ข้อ 2-4)

**แผนที่อนุมัติแล้วอยู่ที่**: `C:\Users\user\.claude\plans\glowing-inventing-dolphin.md`

---

## เป้าหมายเต็ม (บริบทจากผู้ใช้ — 4 ข้อ)

1. **Location graph จริง** ← ทำรอบนี้ — node = สถานที่ที่มีอยู่แล้ว 102 แห่ง (world lore เดิม), edge =
   เส้นทาง+เวลาเดินทาง (ปรับตามขั้นบำเพ็ญ) ผูกกับ event loop เดิมแทน teleport, มี en-route random event
2. Viewer เห็นเป็นแผนที่จริง มีจุดตัวละครเดินไปมา แยกแผงตามแต่ละสวรรค์ — **ยังไม่ทำ**
3. สไตล์แผนที่แบบ mapgen4 (redblobgames.com/maps/mapgen4) — Delaunay/Voronoi + simplex noise +
   จำลองฝน/ลมหาแม่น้ำ/biome, เรนเดอร์ WebGL — **ยังไม่ทำ**
4. ฝัง mapgen4 engine เอง (พอร์ต/ดัดแปลงจาก github.com/redblobgames/mapgen4) ให้ terrain
   generate เองได้และเปลี่ยนตามเหตุการณ์ในเรื่องจริง — **ยังไม่ทำ**

**สำรวจโปรเจกต์อื่นแล้วก่อนเริ่ม** (ทั้ง sibling folders ใน `G:\My Drive\Project\` และภายใน tiandao
เอง): ไม่มีความพยายามทำ location graph/map มาก่อนที่ไหนเลย เป็นงานใหม่ทั้งหมด — โปรเจกต์วิดีโอ/UE5 ที่
เจอ (`My_AI_Second_Brain`) เป็นบทละครคนละเรื่อง (ช้านเทียน) ไม่ใช่ output จากซิมนี้ ไม่เกี่ยวข้องโดยตรง

---

## ระบบที่มีอยู่แล้วตอนนี้ (ทำงานได้จริง ทดสอบแล้ว)

### 1. ภูมิศาสตร์นิ่ง — `tiandao/geo.py` (ไฟล์ generated ห้ามแก้มือ)

- `COORDS[i]` — พิกัด 2 มิติของ `PLACES[i]` แต่ละแห่ง (102 จุด) จัดกลุ่มตาม `(world_key, grade)` เป็น
  6 คลัสเตอร์ภูมิภาค (0/1/2/mara/siam/chaos) แต่ละคลัสเตอร์แบ่งวงตาม grade (2=วงใน, 0=วงนอก) —
  ใช้ fixed seed (`LAYOUT_SEED=20260901`) **ไม่เกี่ยวกับ sim seed เลย** แผนที่จะเหมือนเดิมทุกรัน
  ไม่ว่าจะรันด้วย `--seed` อะไร
- `EDGES` — (place_a, place_b, distance) จาก Delaunay triangulation ของ `COORDS` **แต่กรอง edge ที่
  ข้าม world_key ทิ้งหมด** (บั๊กจริงที่เจอตอนทดสอบ — Delaunay ของจุดทั้งหมดรวมกันเชื่อมข้ามคลัสเตอร์เอง
  ถ้าคลัสเตอร์อยู่ใกล้กันพอ ทำให้เดินข้ามโลก/มิติได้ฟรีโดยไม่ผ่านประตู ผิดจากคอสมอโลจีเดิม — แก้แล้ว)
  แล้วเติมกลับเฉพาะเส้นทางข้าม world_key ของ 5 `GATES` จริงเท่านั้น (เชื่อมไปที่ใกล้สุดในโลกปลายทาง)
- Generator: `tools/generate_location_graph.py` — ใช้ `scipy.spatial.Delaunay` (**dev-time tool
  เท่านั้น** ไม่ใช่ runtime dependency ของ `tiandao/` — รันครั้งเดียวตอนี้ ต้อง re-run เองถ้า
  `places.PLACES` เปลี่ยนในอนาคต)
- **ยืนยันด้วยการทดสอบจริง**: ทุก world_key เชื่อมกันครบภายในตัวเอง (BFS reachability 100% ทั้ง 6
  ภูมิภาค) และข้าม world_key เชื่อมกันได้แค่ผ่าน 5 gate เท่านั้นจริงๆ (ทดสอบ `world0 -> siam` ที่ไม่มี
  gate เชื่อม ได้ `None` ถูกต้อง)

### 2. หาเส้นทาง/เวลาเดินทาง — `tiandao/travel.py` (pure stdlib)

- `shortest_path_distance(from, to)` — Dijkstra บน `geo.EDGES` (ใช้ `heapq` ตรงกับสไตล์เดิมของ
  `sim.py` เป๊ะ) คืนระยะทางรวมสั้นสุด หรือ `None` ถ้าไปไม่ถึง
- `travel_speed(realm)` — ยิ่งขั้นบำเพ็ญสูงยิ่งเดินเร็ว (เชิงเส้นตาม `TRAVEL_REALM_SPEEDUP`)
- `shortest_path_days(from, to, realm)` — ผลรวม แปลงเป็นจำนวนวันจริง (ปัดขึ้นอย่างน้อย
  `TRAVEL_MIN_DAYS`)
- `roll_enroute_event(rng)` — ทอยเหตุการณ์ระหว่างทาง (พบของ/ถูกปล้น/บาดเจ็บ) ใช้ `rng` ที่รับมาเสมอ
  **ไม่เคยใช้ `random` กลาง** (ตาม lesson จากปัญหาข้อ 4 เดิมในโปรเจกต์ — non-determinism ที่เคยเจอมาก่อน)
- ค่าคงที่ใหม่ใน `tiandao/config.py`: `TRAVEL_BASE_SPEED`, `TRAVEL_REALM_SPEEDUP`, `TRAVEL_MIN_DAYS`,
  `TRAVEL_ENROUTE_CHECK_DAYS`, `TRAVEL_ENROUTE_EVENT_P`

### 3. `Character` model (`tiandao/models.py`)

เพิ่ม `travel_dest: int = -1` (ปลายทาง, -1 = ไม่ได้เดินทางอยู่) และ `travel_arrival_day: int = 0`
(จะถึงวันไหน) — เพิ่ม `Character.__setstate__` ใหม่ (เดิมไม่มีเลย มีแค่ `Event` ที่มี) ให้ `world.save`
เก่าก่อนมีระบบนี้ยัง unpickle ได้ (เติม default ให้อัตโนมัติ)

### 4. Event loop จริง (`tiandao/sim.py`)

**สถาปัตยกรรม**: เอนจินมี global heap เดียว `(day, cid)` — `Sim.schedule()` เป็นกลไก schedule ตัวเดียว
ทั้งหมด ไม่มีระบบ delayed-effect แยกมาก่อน ระบบเดินทางเลย reuse pattern ที่มีอยู่แล้ว: `ch.hidden` +
`ch.return_day` (ใช้ตอนเจ้าโกลาหลตาย/กลับมา) — เพิ่ม branch คู่ขนาน `elif ch.travel_dest >= 0:` ที่หัว
loop (`Sim.step()`) แทนที่จะคิดกลไกใหม่ทั้งหมด

- **`resolve()` — `"เดินทาง"` branch**: logic เลือกจุดหมายเดิม (ตามข่าวลือ seek/avoid) **ไม่เปลี่ยนเลย**
  แค่ไม่ teleport ทันทีอีกต่อไป — คำนวณ `days` จาก `travel.shortest_path_days()` แล้วตั้ง
  `travel_dest`/`travel_arrival_day` แทน คืน outcome ใหม่ `"ออกเดินทาง"` (departure)
- **จุด schedule หลัง resolve()**: ถ้าเพิ่งเริ่มเดินทาง นัดตื่นครั้งแรกภายใน `TRAVEL_ENROUTE_CHECK_DAYS`
  วัน ไม่ใช่กระโดดตรงไปวันถึงเลย (**บั๊กจริงที่เจอและแก้แล้ว** — ถ้าไม่ทำแบบนี้ ทริประยะสั้นจะไม่มีโอกาส
  เจอเหตุการณ์ระหว่างทางแม้แต่ครั้งเดียว)
- **top-of-loop branch ใหม่**: ยังไม่ถึง → ทอย `roll_enroute_event()`, ถ้าเจอก็ apply deltas (hp/mats)
  + emit event จริง แล้วนัดเช็คครั้งถัดไป; ถึงแล้ว → ตั้ง `ch.place = travel_dest`, เคลียร์ `travel_dest`,
  emit event outcome `"มาถึง"` (arrival) — ทั้งสองกรณี emit ตรงผ่าน `self.emit()` ไม่ผ่าน intent-weighing
  pipeline เลย (ตัวละครไม่ได้ "เลือก" เหตุการณ์พวกนี้ — เหมือนที่เหตุการณ์ "เจ้าโกลาหลคืนกลับ" ทำอยู่แล้ว)
- **บาดเจ็บถึงตายระหว่างทาง**: ถ้า hp ≤ 0 จาก en-route event, outcome เปลี่ยนจาก `"บาดเจ็บ"` เป็น
  `"ตาย"` ก่อน emit (**บั๊กจริงที่เจอและแก้แล้ว** — `narrative_factory/config.yaml`'s
  `death_outcomes: ["ตาย"]` เช็ค string ตรงตัว ถ้าไม่แก้ ฉากตายระหว่างทางจะไม่ถูกจัดเป็น Death scene เลย)

---

## ทดสอบจริงที่ทำแล้ว (ไม่ mock)

1. **Connectivity**: ทุก world_key เชื่อมกันครบใน `geo.py` (BFS), ข้าม world_key เชื่อมได้แค่ผ่าน gate
2. **Determinism**: รัน `Sim(seed=1).run(8000)` สองครั้งอิสระ ได้ event count เท่ากันเป๊ะ (9316 == 9316)
   ทั้งก่อน/หลังแก้บั๊ก scheduling — ไม่ทำให้ non-determinism แบบที่เคยเจอ (ปัญหาข้อ 4 เดิม) กลับมา
3. **Journey จริง**: ตรวจ log จริงเจอ departure/arrival คนละวันชัดเจน (เช่น day=38 ออกเดินทาง →
   day=84 มาถึง — 46 วันจริง ไม่ใช่ tick เดียวกันแบบเดิม) พร้อม en-route event คั่นกลาง
   (เช่น day=53 "พบของ" ระหว่างทาง)
4. **En-route encounter**: หลังแก้บั๊ก scheduling พบ 38 ครั้งจาก ~570 departures ใน 8000 ticks
   (พบของ 16, ถูกปล้น 11, บาดเจ็บ 11) — สัดส่วนสมเหตุสมผลกับ `TRAVEL_ENROUTE_EVENT_P=0.08`
5. **narrative_factory compatibility**: `"เดินทาง"` kind ไม่เคยอยู่ใน `scene_type_map` อยู่แล้ว (ตกไป
   `Other` เหมือนเดิมทั้งก่อน/หลัง ไม่ใช่ regression) outcome ใหม่ทั้งหมด (`ออกเดินทาง`/`มาถึง`/`พบของ`/
   `ถูกปล้น`/`บาดเจ็บ`) ไม่อยู่ใน `death_outcomes`/`conflict_level.outcome_fallback` เลย ตกไป default
   เกณฑ์เดิมอย่างปลอดภัย (ไม่ throw error ตาม design เดิมของไฟล์นั้น) ยกเว้นกรณีตายที่แก้ให้ใช้
   outcome=`"ตาย"` ตรงๆ แล้ว (ข้อ 4 ด้านบน)

---

## เหตุขัดข้องระหว่างทำงาน (บันทึกไว้ตรงๆ ไม่ปิดบัง)

ตอนรันทดสอบ verification ขั้นสุดท้าย (`run.py --seed 7 --events 6000 --save`) **ลืมระบุ
`--save-path`** ทำให้เขียนทับ `tiandao/world.save` ตัวเดิม (โลกที่ใช้เทรน `loras/v1`-`v6` และ export
dataset ทั้งหมดของเซสชันนี้) โดยไม่ตั้งใจ — ไฟล์เดิมไม่ได้อยู่ใน git (`.gitignore` ตามที่ตั้งใจไว้
ป้องกันไฟล์ binary ใหญ่) จึงกู้คืนตัวเดิมเป๊ะๆ ไม่ได้จริง

**ความเสียหายจริง**: state ของ `Sim` ตัวเดิม (ตัวละคร/ประวัติ/rng state) หายไป **แต่ dataset ที่ export
ไปแล้วทั้งหมด (`datasets/v3/`, `datasets/lessons_v1/`) และ LoRA ที่เทรนแล้วทั้งหมด (`loras/v1`-`v6`)
ไม่ได้รับผลกระทบเลย** (เป็นไฟล์แยกที่ไม่ต้องพึ่ง `world.save` อีกต่อไปหลัง export เสร็จ) ตัวอย่างฉาก
เฉพาะเจาะจงที่เคยตรวจสอบ (spot-check v5/v6) ก็ยังมีบันทึกอยู่เป็นข้อความใน
`CULTIVATOR_BRAIN_STATUS.md` แม้โลกต้นทางจะหายไปแล้ว

**แก้ไข**: ย้ายไฟล์ที่เขียนทับผิดไปเก็บแยก (`tiandao/world.save.TRAVEL_TEST_seed7_DO_NOT_USE`) แล้ว
สร้างโลกใหม่ทดแทนด้วย `daemon.py --seed 1 --chunk-events 20000 --iterations 5 --save-path
tiandao/world.save` (ระบุ path ชัดเจนรอบนี้) — **เสร็จสมบูรณ์แล้ว**: ครบ 5 รอบ (ปีที่ 657, advancement
rate สุขภาพดีตลอด 0.243-0.268) ตัวละครสะสม 6,616 คน (มีชีวิต 888) เหตุการณ์รวม 119,058 (แยกเก็บ 5,000
ล่าสุดใน `world.save` + ที่เหลือ flush ไปที่ `world.save.events.jsonl` ตาม Phase G เดิม) — ยืนยันโหลด
กลับมาสำเร็จ, `narrative_factory` extract ได้ 37,916 ฉากจริง, เจอ event kind `"เดินทาง"` จริง 15,114
ครั้ง (ระบบเดินทางใหม่ทำงานทั่วทั้งโลกจริงแล้ว ไม่ใช่แค่ตัวอย่างทดสอบเล็กๆ) — **โลกใหม่นี้ใหญ่กว่าเดิมมาก**
(เดิม ~1,731 ฉาก/5,423 เหตุการณ์ → ใหม่ 37,916 ฉาก/119,058 เหตุการณ์) เพราะรันยาวกว่าเดิม (657 ปี)

**บทเรียน**: ต่อไปนี้ทุกรันทดสอบ/verification จะใช้ `--save-path` แยกเฉพาะ (เช่น
`tiandao/world.save.test_*`) ไม่ใช้ default path เด็ดขาด เว้นแต่ตั้งใจจะอัปเดต production world.save
จริงๆ

---

## ยังไม่ได้ทำ (ตัดขอบเขตไว้ตรงๆ ตามแผนที่อนุมัติ)

1. **`"ลงโลกล่าง"` (gate event) ยังคง teleport ทันทีเหมือนเดิม** — ยังไม่ได้ต่อเข้ากราฟ (ตัดสินใจไว้ตั้งแต่
   แผน เพราะเป็นการเดินทางข้ามมิติที่ควรเร็ว/กะทันหันอยู่แล้ว ไม่ใช่จุดที่ระบบ graph มีความหมายมากเท่า
   การเดินทางปกติ) — `geo.py` มีข้อมูล gate edge พร้อมแล้วถ้าจะต่อในอนาคต
2. **Chaos-invasion flee (`sim.py:1115`) ยังคง teleport ทันทีเหมือนเดิม** — เป็นการหนีฉุกเฉิน เวลาจริง
   ไม่สำคัญเท่าความเร่งด่วน ตัดสินใจเว้นไว้เหมือนกัน
3. **Viewer/mapgen4 (เป้าหมายข้อ 2-4)** — ยังไม่เริ่มเลย `geo.py`'s `COORDS`/Delaunay mesh ออกแบบมาให้
   ใช้ต่อได้ตรงๆ กับ mapgen4 (โครงสร้างข้อมูลเดียวกันเป๊ะ — Delaunay mesh คือหัวใจของ mapgen4 อยู่แล้ว)
   แต่การเรนเดอร์ WebGL/simplex noise/จำลองฝน-ลม เป็นงานแยกทั้งหมด ยังไม่ได้แตะ
4. **`tuning.py:TUNABLES`** — ค่าคงที่ travel ใหม่ (`TRAVEL_BASE_SPEED` ฯลฯ) ยังไม่ได้ลงทะเบียนให้
   autotune.py ปรับอัตโนมัติได้ (ทำได้ทีหลังถ้าต้องการ ตามแพทเทิร์นเดียวกับ 5 ค่าที่ลงทะเบียนไว้แล้ว)
5. **`scene_type_map`** ใน `narrative_factory/config.yaml` ยังไม่มี entry สำหรับ `"เดินทาง"` เลย
   (ไม่ใช่ regression จากงานนี้ — ไม่เคยมีมาตั้งแต่ต้น) ฉากเดินทางทั้งหมดยังตกเป็น scene_type=`Other`
   ถ้าอยากให้ dataset export จำแนกฉากเดินทางแยกจาก Other ในอนาคต ต้องเพิ่ม mapping เอง

## คำถามเปิดสำหรับตัดสินใจต่อ (ยังไม่ได้ถาม/ตัดสินใจ)

- **ค่าคงที่ความเร็วเดินทาง** (`TRAVEL_BASE_SPEED=3.0`, `TRAVEL_REALM_SPEEDUP=0.12`) เป็นค่าประมาณ
  เริ่มต้นที่ยังไม่ได้ปรับจูนกับ playtesting จริง — ทริประหว่าง world_key เดียวกันจริงตอนนี้อยู่ราวๆ
  10-50 วัน (ขึ้นกับ realm) เดินทางข้าม world_key ผ่าน gate ไกลกว่ามาก (200-700 วัน ตามระยะ Delaunay
  จริงระหว่างคลัสเตอร์) — ยังไม่รู้ว่าตัวเลขนี้ "รู้สึกถูก" ไหมเทียบกับจังหวะเรื่องที่ตั้งใจ
- **สัดส่วน en-route event** (`TRAVEL_ENROUTE_EVENT_P=0.08` ต่อการเช็คทุก `TRAVEL_ENROUTE_CHECK_DAYS=15`
  วัน) เป็นค่าประมาณเริ่มต้นเช่นกัน — เอฟเฟกต์ยังเบามาก (hp ±5/-10, mats +1) ยังไม่ได้ผูกกับไอเทม/สมบัติ
  จริงในระบบ (`self.items`) แค่ตัวเลขคร่าวๆ
