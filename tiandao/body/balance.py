# -*- coding: utf-8 -*-
"""จุดศูนย์กลางมวลและการทรงตัว (พรอมต์ §10)

    COM = Σ(m_i · r_i) / Σ m_i

ทำไมเรื่องนี้ไม่ใช่ของประดับ
--------------------------------------------------------------------------------------------
เพราะมันทำให้ "แบกของหนักแล้วเสียหลัก" เป็นผลของฟิสิกส์ ไม่ใช่กฎที่เขียนเพิ่ม ของที่ถือไว้
ข้างหน้าดึงจุดศูนย์กลางมวลรวมไปข้างหน้า ถ้ามันเลยขอบปลายเท้าไป คนก็ล้ม — และเพดานน้ำหนัก
ที่แบกได้จึงมีสองเกณฑ์ที่ต่างกันโดยธรรมชาติ: **หลังรับไหวไหม** (ทอร์ก) กับ **ยืนอยู่ได้ไหม**
(สมดุล) ซึ่งเกณฑ์ไหนบีบก่อนขึ้นกับว่าถือของไว้ใกล้ตัวแค่ไหน

ระบบพิกัดที่ใช้
--------------------------------------------------------------------------------------------
เป็นระนาบข้าง (sagittal) สองแกนเท่านั้น — พอสำหรับคำถามที่ซิมถามจริง (ล้มหน้า/ล้มหลัง)
    x  แนวหน้า-หลัง (m) บวก = ไปข้างหน้า จุดกำเนิดอยู่ที่ข้อเท้า
    z  แนวดิ่ง (m) วัดจากพื้น
ไม่ทำแกนข้างเพราะการล้มด้านข้างยังไม่มีเหตุการณ์ใดในโลกนี้ที่ต้องใช้ (พรอมต์ §41: ไม่จำลอง
สิ่งที่ละเอียดจนไม่มีผล) ฐานรองรับด้านข้างคำนวณไว้ให้แล้วถ้าเฟสหลังต้องใช้
"""
from . import constants as K


def segment_masses(body) -> dict:
    """มวลของแต่ละส่วนร่าง (kg) — รวมกันได้เท่ามวลรวมพอดี"""
    out = {}
    for name, frac in K.SEGMENT_MASS_FRACTION.items():
        count = 2 if name in K.SEGMENT_PAIRED else 1
        out[name] = body.mass * frac * count
    return out


def com_height(body) -> float:
    """ความสูงของจุดศูนย์กลางมวลจากพื้น (m) ขณะยืนตรง

    ไม่ได้ตั้งไว้ — รวมจากมวลและตำแหน่งของทุกส่วนร่าง แล้วออกมาเองราว 0.54 ของส่วนสูง
    ซึ่งใกล้ค่าที่วัดกันจริง (~0.55) โดยไม่ได้จูนให้ตรง
    """
    masses = segment_masses(body)
    total = sum(masses.values())
    if total <= 0.0:
        return 0.0
    height = body.gen.height
    return sum(m * K.SEGMENT_COM_HEIGHT[name] * height for name, m in masses.items()) / total


def support_polygon(body) -> dict:
    """ฐานรองรับตอนยืน (m) — วัดจากข้อเท้าเป็นจุดกำเนิด

    ปลายเท้าอยู่หน้าข้อเท้า ส้นเท้าอยู่หลัง คนเท้ายาวจึงล้มหน้ายากกว่าโดยรูปร่างล้วนๆ
    """
    foot = body.gen.height * K.FOOT_LENGTH_RATIO
    heel_to_ankle = foot * K.ANKLE_FROM_HEEL_RATIO
    width = (body.gen.segment("pelvis_width") * K.STANCE_WIDTH_RATIO
             + body.gen.height * K.FOOT_WIDTH_RATIO)
    return {"front": foot - heel_to_ankle, "back": -heel_to_ankle, "width": width}


def com_offset(body, load_kg: float = 0.0, load_arm: float = None) -> float:
    """ตำแหน่งหน้า-หลังของจุดศูนย์กลางมวลรวม (m) เทียบข้อเท้า

        x = (m_กาย·x_กาย + m_ของ·x_ของ) / (m_กาย + m_ของ)

    ยืนเปล่าๆ จุดศูนย์กลางมวลอยู่ค่อนไปหน้าข้อเท้านิดเดียว (COM_AHEAD_OF_ANKLE)
    ถือของไว้ข้างหน้าเท่าไร ยิ่งดึงไปข้างหน้าเท่านั้น
    """
    arm = K.CARRY_LEVER_ARM if load_arm is None else load_arm
    body_x = K.COM_AHEAD_OF_ANKLE
    total = body.mass + max(0.0, load_kg)
    if total <= 0.0:
        return body_x
    return (body.mass * body_x + max(0.0, load_kg) * arm) / total


def balance_margin(body, load_kg: float = 0.0, load_arm: float = None) -> float:
    """ระยะจากจุดศูนย์กลางมวลถึงขอบฐานรองรับที่ใกล้ที่สุด (m)

    บวก = ยังยืนอยู่ได้ · ศูนย์ = อยู่บนขอบพอดี · ลบ = ล้ม
    """
    poly = support_polygon(body)
    x = com_offset(body, load_kg, load_arm)
    return min(poly["front"] - x, x - poly["back"])


def is_stable(body, load_kg: float = 0.0, load_arm: float = None) -> bool:
    return balance_margin(body, load_kg, load_arm) > 0.0


def max_stable_load(body, load_arm: float = None) -> float:
    """น้ำหนักมากที่สุดที่ถือไว้ที่ระยะนั้นแล้วยังไม่ล้ม (kg)

    แก้สมการสมดุลย้อนกลับ ไม่ได้ค้นหาแบบไล่ทีละค่า:
        (m·x_กาย + M·x_ของ) / (m + M) = x_ขอบ
        ⟹ M = m·(x_ขอบ − x_กาย) / (x_ของ − x_ขอบ)
    ถ้าถือของไว้ใกล้ตัวกว่าขอบฐาน สมดุลไม่เคยเป็นตัวจำกัด — คืนอนันต์ในเชิงปฏิบัติ
    """
    arm = K.CARRY_LEVER_ARM if load_arm is None else load_arm
    edge = support_polygon(body)["front"]
    if arm <= edge:
        return float("inf")
    return max(0.0, body.mass * (edge - K.COM_AHEAD_OF_ANKLE) / (arm - edge))


def explain(body, load_kg: float = 0.0, load_arm: float = None) -> dict:
    poly = support_polygon(body)
    arm = K.CARRY_LEVER_ARM if load_arm is None else load_arm
    return {
        "ความสูงจุดศูนย์กลางมวล (m)": round(com_height(body), 3),
        "เทียบส่วนสูง (×)": round(com_height(body) / body.gen.height, 3),
        "ฐานรองรับ หน้า/หลัง (m)": [round(poly["back"], 3), round(poly["front"], 3)],
        "ความกว้างฐาน (m)": round(poly["width"], 3),
        "ของที่ถือ (kg)": round(load_kg, 1),
        "ระยะที่ถือไว้ข้างหน้า (m)": round(arm, 3),
        "ตำแหน่งจุดศูนย์กลางมวล (m)": round(com_offset(body, load_kg, arm), 4),
        "ระยะเหลือถึงขอบ (m)": round(balance_margin(body, load_kg, arm), 4),
        "ยืนอยู่ได้": is_stable(body, load_kg, arm),
        "ของหนักสุดที่ยังไม่ล้ม (kg)": round(max_stable_load(body, arm), 1),
    }
