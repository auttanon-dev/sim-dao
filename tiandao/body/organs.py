# -*- coding: utf-8 -*-
"""หน้าที่อวัยวะสำคัญที่อนุมานจากความเสียหายเฉพาะตำแหน่ง

โมเดลบาดเจ็บเก็บชั้น ``organ`` รายบริเวณเพื่อให้เซฟเล็ก อวัยวะในบริเวณเดียวกันจึงรับ
การกระทบก้อนเดียวกัน แต่ผลทางสรีรวิทยาแยกกัน: สมองคุมสติ หัวใจ/ปอดคุมออกซิเจน
ตับ ไต และทางเดินอาหารคุมการฟื้นตัว นี่เป็นระดับรายละเอียดที่เข้ากับ event simulation
โดยไม่แสร้งเป็นเครื่องจำลองการแพทย์รายหลอดเลือด
"""

ORGANS = {
    "brain": ("head", 1.15),
    "heart": ("chest", 1.10),
    "lungs": ("chest", 0.95),
    "liver": ("abdomen", 0.75),
    "kidneys": ("abdomen", 0.65),
    "gut": ("abdomen", 0.55),
}


def functions(state) -> dict:
    """หน้าที่คงเหลือ 0..1; ความเสียหายเดียวกันกระทบแต่ละอวัยวะไม่เท่ากัน"""
    state = state or {}
    out = {}
    for name, (region, sensitivity) in ORGANS.items():
        damage = float(state.get(region, {}).get("organ", 0.0))
        out[name] = max(0.0, min(1.0, 1.0 - sensitivity * damage))
    return out


def oxygen_factor(state) -> float:
    f = functions(state)
    # การส่ง O2 เป็นโซ่ต่อกัน หัวใจหรือปอดพังอย่างใดอย่างหนึ่งก็เป็นคอขวด
    return max(0.0, min(f["heart"], f["lungs"]))


def recovery_factor(state) -> float:
    f = functions(state)
    return max(0.1, (f["liver"] * f["kidneys"] * f["gut"]) ** (1.0 / 3.0))


def conscious(state) -> bool:
    return functions(state)["brain"] > 0.08


def fatal_failure(state):
    """คืนชื่ออวัยวะที่ล้มเหลวทันที หรือ None ถ้ายังพอทำงานได้"""
    f = functions(state)
    for name in ("brain", "heart", "lungs"):
        if f[name] <= 0.02:
            return name
    return None


def explain(state) -> dict:
    return {name: round(value, 3) for name, value in functions(state).items()}
