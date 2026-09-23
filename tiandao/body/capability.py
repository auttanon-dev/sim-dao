# -*- coding: utf-8 -*-
"""ความสามารถทางกาย — สิ่งที่ "ทำได้จริง" ซึ่งอนุพัทธ์จากกายวิภาคล้วนๆ

ไม่มีค่าใดในไฟล์นี้ถูกตั้งไว้ล่วงหน้า ทุกค่าออกมาจากมวล แรง ความยาวท่อน และแรงโน้มถ่วง
(พรอมต์ §31, §45) ฟังก์ชันทุกตัวบริสุทธิ์และไม่แตะ RNG

ขอบเขต (พรอมต์ §41)
--------------------------------------------------------------------------------------------
ความสูงกระโดด · แรงบิด · ความสามารถยก · เวลาตอบสนอง คำนวณจากหลักการฟิสิกส์ตรงๆ
(งาน-พลังงาน · ทอร์ก · ความเร็วการนำสัญญาณประสาท) ส่วน **ความเร็ววิ่งสูงสุด** ใช้
ความสัมพันธ์เชิงประจักษ์ (scaling law) ไม่ใช่การอนุพัทธ์จากหลักการแรก — ระบุไว้ตรงนี้
เพราะการอ้างว่ามันคือฟิสิกส์บริสุทธิ์จะเป็นการอ้างเกินจริง
"""
import math

from . import constants as K


# ---------------------------------------------------------------- กระโดด
def jump_height(body, fatigue: float = 0.0) -> float:
    """ความสูงที่กระโดดขึ้นได้ (m) — จากงาน-พลังงาน ไม่ใช่จากตัวคูณ

        งานสุทธิที่ดันตัวขึ้น:   W = (F_ขา − mg) · d
        แปลงเป็นพลังงานจลน์:    W = ½·m·v²
        ⟹ v = sqrt(2·(F_ขา − mg)·d / m)
        ⟹ h = v² / (2g)                              (พรอมต์ §14)

    คนที่กล้ามเนื้อขาแข็งแรงกว่าจึงไม่ได้ "กระโดดสูงขึ้น 20%" ตรงๆ แต่สร้างอิมพัลส์ได้
    มากกว่า แล้วความสูงตามมาเอง และมวลที่มากขึ้นก็ถ่วงทั้งในพจน์ mg และตัวหาร m
    """
    v = takeoff_velocity(body, fatigue)
    return v * v / (2.0 * K.GRAVITY)


def takeoff_velocity(body, fatigue: float = 0.0) -> float:
    """ความเร็วขณะเท้าพ้นพื้น (m/s) — 0 ถ้าแรงขาไม่พอยกน้ำหนักตัวเองด้วยซ้ำ"""
    weight = body.mass * K.GRAVITY
    force = body.leg_force(fatigue) * K.JUMP_FORCE_EFFICIENCY
    net = force - weight
    if net <= 0.0:
        return 0.0
    push = body.gen.leg_length * K.PUSH_DISTANCE_RATIO
    return math.sqrt(2.0 * net * push / body.mass)


# ---------------------------------------------------------------- วิ่ง
def max_running_speed(body, friction: float = K.DEFAULT_FRICTION, fatigue: float = 0.0) -> float:
    """ความเร็วสูงสุดที่วิ่งได้ (m/s)

    ความเร็วไม่ได้ถูกตั้ง แต่มาจากสองสิ่งที่วัดได้จากร่าง:
      · **แรงกดพื้นต่อน้ำหนักตัว** (F_ขา / mg) — ตัวจำกัดหลักตาม Weyand et al. (2000)
        ที่พบว่านักวิ่งเร็วต่างกันที่แรงที่กดพื้นได้ ไม่ใช่ที่ความถี่ก้าว
      · **ความยาวขา** — ก้าวยาวกว่าที่ความถี่เท่ากันคือเร็วกว่า

        v_max = c · (Fratio/Fref)^a · (L_ขา/Lref)^b

    นี่คือ scaling law เชิงประจักษ์ ไม่ใช่การอนุพัทธ์จากหลักการแรก (ดูหัวไฟล์)
    จากนั้นหนีบด้วยเพดานแรงเสียดทาน: แรงในแนวราบเกิน μN ไม่ได้ เท้าจะลื่น (พรอมต์ §12)
    พื้นน้ำแข็ง (μ = 0.12) จึงทำให้คนเดิมวิ่งได้ช้าลงจริงโดยไม่ต้องเขียนกฎแยก
    """
    weight = body.mass * K.GRAVITY
    if weight <= 0.0:
        return 0.0
    usable = min(body.leg_force(fatigue), friction * weight * _FRICTION_HEADROOM)
    ratio = usable / weight
    speed = (K.RUN_SPEED_COEF
             * (ratio / K.RUN_REF_FORCE_RATIO) ** K.RUN_FORCE_EXPONENT
             * (body.gen.leg_length / K.RUN_REF_LEG_LENGTH) ** K.RUN_LEG_EXPONENT)
    return min(K.RUN_SPEED_MAX, max(K.RUN_SPEED_MIN, speed))


# ตอนวิ่ง แรงที่กดพื้นมีทั้งแนวดิ่งและแนวราบ ส่วนที่ต้องสู้กับแรงเสียดทานคือแนวราบ
# ซึ่งเป็นเศษส่วนหนึ่งของแรงรวม — ตัวเลขนี้คือ "เพดานแรงรวมที่พื้นยังรับไหว" เทียบ μN
# ตั้งให้สูงพอที่พื้นปกติ (μ = 0.70) จะไม่บีบใครเลย ไม่งั้นเพดานเสียดทานจะกลืนความต่าง
# ระหว่างคนจนความเร็วทุกคนเท่ากันหมด (วัดตอนตั้งไว้ 3.6: ส่วนเบี่ยงเบนความเร็วยุบเหลือ 0.34)
# ส่วนพื้นลื่นอย่างน้ำแข็ง (μ = 0.12) ยังบีบแรงเหลือไม่ถึงหนึ่งเท่าน้ำหนักตัวตามที่ควรเป็น
_FRICTION_HEADROOM = 7.0


# ---------------------------------------------------------------- ยก/แบก
def carry_capacity(body, fatigue: float = 0.0) -> float:
    """มวลสูงสุดที่ยกและพาไปได้ (kg) — จำกัดด้วยทอร์กของกระดูกสันหลัง ไม่ใช่ด้วยค่า Strength

        ทอร์กที่ต้องใช้:  τ = (m_ของ + m_ลำตัวบน) · g · แขนโมเมนต์
        ยกได้ก็ต่อเมื่อ:  τ ที่ต้องใช้ ≤ τ ที่ข้อมีให้                   (พรอมต์ §15)

    คืน 0 ถ้าลำพังลำตัวของตัวเองก็หนักเกินกว่าที่หลังจะพยุงไหว
    """
    available = body.joint_torque("spine", fatigue) * K.CARRY_SAFETY_FACTOR
    upper = body.mass * K.CARRY_TORSO_MASS_FRACTION
    own = upper * K.GRAVITY * K.CARRY_LEVER_ARM
    spare = available - own
    if spare <= 0.0:
        return 0.0
    return spare / (K.GRAVITY * K.CARRY_LEVER_ARM)


def can_lift(body, load_kg: float, fatigue: float = 0.0) -> bool:
    """ยกของหนักเท่านี้ไหวไหม — ใช้เกณฑ์ทอร์กเดียวกับ carry_capacity"""
    return load_kg <= carry_capacity(body, fatigue)


# ---------------------------------------------------------------- ระบบประสาท
def reaction_time(body, fatigue: float = 0.0) -> float:
    """เวลาตอบสนอง (s) — ไม่ใช่สเตตัสคงที่ แต่เป็นผลรวมของหน่วงจริง (พรอมต์ §24)

        T = T_ส่วนกลาง + ระยะทางเส้นประสาท / ความเร็วการนำสัญญาณ + หน่วงจากความล้า

    คนตัวสูงมีเส้นทางประสาทยาวกว่า จึงช้ากว่าเล็กน้อยโดยธรรมชาติ — เป็นผลของกายวิภาค
    ล้วนๆ ไม่ได้ตั้งใจให้เป็นโทษ ส่วน Phase ถัดไปจะบวกพจน์ของบาดเจ็บ ออกซิเจน และความเครียด
    """
    gen = body.gen
    central = K.REACTION_CENTRAL_BASE + K.REACTION_CENTRAL_SPAN * (1.0 - gen.neuro_efficiency)
    conduction = (gen.height * K.NERVE_PATH_RATIO) / K.NERVE_CONDUCTION_SPEED
    slowed = (central + conduction) * (1.0 + max(0.0, fatigue))
    return max(K.REACTION_MIN, slowed)


# ---------------------------------------------------------------- ดัชนีรวม
def strength_index(body, fatigue: float = 0.0) -> float:
    """พลังกายเทียบกับร่างอ้างอิงของโลก — ไร้หน่วย อยู่รอบ 1.0

    ใช้เป็น *หนึ่งปัจจัย* ของพลังรวมใน rules.power() เท่านั้น ไม่ใช่ตัวตัดสิน เพราะโลกนี้
    พลังส่วนใหญ่มาจากขั้น วิชา ธาตุ และปราณ (ดู constants.BODY_POWER_WEIGHT)

    คิดจากแรงขาต่อร่างอ้างอิง ถ่วงด้วยมวลที่ต้องพาไปเอง: ร่างที่หนักขึ้นเพราะกล้ามเนื้อ
    ได้เปรียบ ส่วนร่างที่หนักขึ้นเพราะไขมันเสียเปรียบ — ทั้งที่ชั่งน้ำหนักได้เท่ากัน (พรอมต์ §3)
    """
    weight = body.mass * K.GRAVITY
    if weight <= 0.0:
        return 0.0
    # "ดันตัวเองได้กี่เท่าของน้ำหนักตัว" — ไร้หน่วย เทียบกับค่ากลางของประชากรจึงอยู่รอบ 1.0
    # มวลอยู่ในตัวหารอยู่แล้ว ร่างที่หนักขึ้นเพราะไขมันจึงได้ดัชนีต่ำลงโดยอัตโนมัติ
    # ส่วนร่างที่หนักขึ้นเพราะกล้ามเนื้อได้แรงเพิ่มในตัวเศษมากกว่าที่เสียไปในตัวหาร
    return (body.leg_force(fatigue) / weight) / K.REFERENCE_FORCE_RATIO


def summary(body, friction: float = K.DEFAULT_FRICTION, fatigue: float = 0.0) -> dict:
    """ความสามารถทุกตัวในที่เดียว — ทุกค่าย้อนกลับไปหาการคำนวณได้ (พรอมต์ §44)"""
    return {
        "ความเร็ววิ่งสูงสุด (m/s)": round(max_running_speed(body, friction, fatigue), 2),
        "ความเร็วขณะพ้นพื้น (m/s)": round(takeoff_velocity(body, fatigue), 2),
        "ความสูงกระโดด (m)": round(jump_height(body, fatigue), 3),
        "แบกได้ (kg)": round(carry_capacity(body, fatigue), 1),
        "เวลาตอบสนอง (s)": round(reaction_time(body, fatigue), 3),
        "ดัชนีพลังกาย (×)": round(strength_index(body, fatigue), 3),
        "สัมประสิทธิ์เสียดทานที่ใช้": friction,
        "ความล้าที่ใช้": fatigue,
    }
