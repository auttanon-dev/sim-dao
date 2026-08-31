# -*- coding: utf-8 -*-
"""Phase K4 — Payoff Detector: จับคู่ Expectation -> Result ของฉาก

ตัวค้นย้อนหลัง (Foreshadowing) ตัวจริงอยู่ใน `genome.compute_foreshadowing()` แล้วตั้งแต่ Phase B ของ
Narrative Dataset Factory — ไฟล์นี้**ไม่ duplicate** การค้นย้อนหลังนั้นซ้ำ แค่ประกอบผลลัพธ์ที่มีอยู่แล้ว
(`NarrativeGenome.foreshadowing`/`payoff`) ให้เป็นคู่ Expectation -> Result ตามที่ `ROLE` Phase K
กำหนด ("ค้นย้อนหลังเหมือน Foreshadowing")

ต่างจาก `teacher.py:analyze_payoff()` เดิมของ K1 (ที่ใช้แค่ foreshadowing รายการล่าสุดรายการเดียว)
ตรงที่ไฟล์นี้ประกอบ Expectation จาก**ทุกรายการ foreshadowing ที่เจอ** (ไม่ตัดทิ้ง) ให้เห็นภาพการปูเรื่อง
เต็มๆ ก่อนไป Result จริง — `teacher.py` แก้ให้เรียกไฟล์นี้แทน
"""
from .scene_extractor import Scene


def detect_payoff(scene: Scene) -> str:
    """Expectation -> Result — reuse `NarrativeGenome.foreshadowing`/`payoff` ที่คำนวณไว้แล้วตรงๆ
    (ทั้งคู่กราวด์กับ log จริง 100% ตาม genome.py) ไม่คำนวณซ้ำ"""
    if scene.genome.foreshadowing:
        expectation = " | ".join(scene.genome.foreshadowing)
    else:
        expectation = "(ไม่มีการปูเรื่องล่วงหน้าที่พบในประวัติตัวละครนี้)"
    return f"{expectation} -> {scene.genome.payoff}"
