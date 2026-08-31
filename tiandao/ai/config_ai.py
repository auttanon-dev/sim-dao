# -*- coding: utf-8 -*-
"""ค่าคงที่ของ Cultivator Brain — แยกจาก tiandao/config.py เดิมโดยตั้งใจ เพราะไฟล์นั้นเป็นค่าคงที่ของ
"ฟิสิกส์โลก" ที่ tiandao/tuning.py + autotune.py ปรับข้ามรันอยู่แล้ว ส่วนนี้เป็นค่าคงที่ของ "สมองตัวละคร"
คนละชั้นกัน ไม่ควรปนกัน
"""

# เหตุการณ์ที่ถือว่า "น่าจดจำ" พอจะเป็นตัวกระตุ้น Layer 3 (Ollama) ใน Phase 5 — Phase 1 นี้ใช้แค่
# ทำเครื่องหมายไว้ในความทรงจำ ยังไม่มีการเรียก LLM จริง
# คัดจาก tiandao/events.py:EVENT_TABLE (kind) + outcome ที่ resolve_clash ใน sim.py คืนมา
NOTABLE_KINDS = frozenset({
    "ทรยศ", "ไส้ศึกลงมือ", "ประลอง", "ล้างแค้น", "ค้นแดนลับ",
    "ชิงสมบัติ", "ข้ามขั้น", "ข้ามฟ้า", "สงครามสำนัก",
})
NOTABLE_OUTCOMES = frozenset({"ตาย", "สำเร็จ"})

# ความจำ episodic ต่อตัวละคร — มีเพดานตั้งใจ กันไม่ให้ world.save โตไม่มีที่สิ้นสุด
# (ตอนทดสอบ daemon.py 10 รอบ/200k เหตุการณ์ก่อนหน้านี้ ไฟล์โตถึง 73MB จาก sim.log ที่ไม่มีเพดาน —
# ระบบความจำใหม่นี้ต้องไม่ทำปัญหาเดิมซ้ำ)
EPISODIC_MEMORY_CAP = 30

# โมเดล Ollama สำหรับ Layer 3 (บทพูด/ความคิดตัวละคร)
# เดิมเป็น qwen2.5vl:7b (เลือกเพราะตระกูล Qwen2.5 รองรับภาษาไทยดีที่สุดในบรรดาโมเดลที่ติดตั้งไว้บน
# เครื่องนี้ — ollama list: qwen2.5vl:7b, deepseek-r1:8b, qwen3-coder:30b, qwen3-embedding:4b)
# เคยเปลี่ยนเป็น cultivator-brain:latest หลัง Phase K hot-swap (loras/v4 ผ่าน Shadow Evaluation Gate
# ด้วย held-out test 79 ฉากจริง) แต่ **เปลี่ยนกลับแล้ว** หลังวัดผลจริงแบบ A/B เทียบคำตอบเดียวกัน (prompt/
# character/brain state ชุดเดียวกัน) 45 เหตุการณ์ครบทุก NOTABLE_KINDS — cultivator-brain:latest แย่กว่า
# ชัดเจนสำหรับงาน JSON {"dialogue","thought"} นี้โดยเฉพาะ: JSON parse สำเร็จ 38/45 (84%) เทียบ 45/45
# ของ qwen2.5vl:7b, อักษรจีนหลุดปน 8/45 (18%) เทียบ 1/45, มี 1 ครั้งตอบว่างเปล่าใช้เวลา 32 วินาที และ
# อย่างน้อย 1 ครั้งหลุด raw state text ภาษาจีนยาวปนออกมาใน thought — ตรงกับที่คาดไว้ตอนเปลี่ยน (loras/v4
# ไม่เคยเห็น Dataset B/C ตอนเทรนเพราะ world ที่ใช้เทรนไม่เคยรันด้วย --llm) รายละเอียดเต็มดู
# CULTIVATOR_BRAIN_STATUS.md ปัญหาข้อ 10
OLLAMA_MODEL = "qwen2.5vl:7b"
OLLAMA_HOST = "http://localhost:11434"
OLLAMA_TIMEOUT = 30.0
OLLAMA_TEMPERATURE = 0.8

# Layer 3 — Local LLM Agent (Phase 5): ปิดไว้เป็นค่าเริ่มต้นโดยตั้งใจ — การเรียก Ollama เป็น blocking
# HTTP call ต่อครั้ง (วินาทีระดับ) ถ้าเปิดตลอดจะทำให้ batch simulation (autotune.py/daemon.py ที่ต้อง
# รันเร็วหลายหมื่นเหตุการณ์) ช้าลงมหาศาล เปิดผ่าน --llm ใน run.py/daemon.py เฉพาะตอนอยากได้บทพูด/
# ความคิดจริงสำหรับสร้างนิยาย (Phase 6) เท่านั้น
LLM_ENABLED = False
NARRATIVE_MOMENT_CAP = 10   # ความจำ "โมเมนต์ที่ LLM สร้างให้แล้ว" สูงสุดต่อคน (กันไม่ให้ save โตไม่มีเพดาน)

# History Generator (Phase 6): เครื่องมือเรียกแยกหลังซิมจบ (ดู generate_episode.py) ไม่ผูกกับ
# LLM_ENABLED ด้านบน (ตัวนั้นคุมเฉพาะระหว่างซิมกำลังเดินสด)
HISTORY_MAX_SCENES = 8       # จำนวนฉากเด่นสูงสุดต่อหนึ่งตอนที่สร้าง
HISTORY_TIMEOUT = 120.0      # ร้อยแก้วยาวกว่าบทพูดสั้นของ Layer 3 มาก ให้เวลามากกว่า OLLAMA_TIMEOUT

# Layer 1 — Utility AI (Phase 2): แรงชักจูงของ Need ที่ชนะต่อน้ำหนักเดิมใน intent.py:weigh()
# weight_ใหม่ = weight_เดิม * (1 + UTILITY_GAIN * คะแนน Need) — ชักจูงเท่านั้น ไม่เคยลดหรือบังคับ
# (0..1) เพื่อรักษาความสุ่มเดิมของเอนจินไว้ ปรับตัวเลขนี้ถ้าอยากให้ Utility "แรง"/"เบา" กว่านี้
UTILITY_GAIN = 0.6

# Layer 2 — Hierarchical GOAP (Phase 3): ตอนนี้ decompose เฉพาะ Goal "Breakthrough" (ตัวอย่างที่
# ROLE.md ระบุไว้ชัดเจน) — ขยายไปยัง Goal อื่นทีหลังได้ด้วยแพทเทิร์นเดียวกัน
PILL_BUY_MIN_MONEY = 500      # เกณฑ์เงินขั้นต่ำที่ถือว่า "พอซื้อ/ประมูลยาได้" (หน่วยของโลกนั้นๆ)
GOAP_READY_BOOST = 2.0        # มียาติดตัวแล้ว — เร่งให้ลองข้ามขั้นเลย
GOAP_SUBGOAL_BOOST = 1.8      # ยังไม่มียา — เร่งให้ไปทำ sub-goal (หา/ซื้อ/ปล้น/หลอม) ก่อน

# Memory System (Phase 4): Semantic memory ต่อสถานที่ (tiandao/ai/memory.py)
SEMANTIC_ALPHA = 0.3           # EMA ของ danger/fortune ต่อสถานที่ — เอนเอียงไปทางประสบการณ์ล่าสุด
SEMANTIC_MEMORY_CAP = 20       # จำนวนสถานที่สูงสุดที่จำไว้ต่อคน (ตัดที่ไม่ได้ไปนานสุดทิ้งก่อน)
SEMANTIC_NOTE_THRESHOLD = 0.5  # ค่า danger/fortune ที่ถือว่าพอจะสรุปเป็น "อันตราย"/"โชคดี" ได้แล้ว
