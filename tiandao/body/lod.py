# -*- coding: utf-8 -*-
"""ระดับรายละเอียดของสรีรวิทยาสำหรับประชากรจำนวนมาก (§42)

LOD เปลี่ยนความถี่/รายละเอียดของ *คำอธิบาย* ไม่เปลี่ยนสมการสถานะหลัก เพราะสมการทุกชุดเป็น
closed-form อยู่แล้วและเดินข้ามช่วงยาวได้ใน O(1) ตัวละครนอกจอจึงไม่ต้อง tick รายเฟรม แต่
เลือด แผล และอุณหภูมิยังไม่หายไปจากโลกเพียงเพราะกล้องมองไม่เห็น
"""

CRITICAL, ACTIVE, RECOVERING, DORMANT = range(4)
NAMES = {CRITICAL: "critical", ACTIVE: "active", RECOVERING: "recovering", DORMANT: "dormant"}


def level(character, active: bool = False) -> int:
    if active:
        return ACTIVE
    injury = getattr(character, "injuries", None) or {}
    if (getattr(character, "bleed", 0.0) > 0.001
            or getattr(character, "blood_frac", 1.0) < 0.75
            or getattr(character, "core_temp", 37.0) < 35.0
            or getattr(character, "core_temp", 37.0) > 39.5):
        return CRITICAL
    if injury or getattr(character, "fatigue", 0.0) > 0.05:
        return RECOVERING
    return DORMANT


def name(character, active: bool = False) -> str:
    return NAMES[level(character, active)]
