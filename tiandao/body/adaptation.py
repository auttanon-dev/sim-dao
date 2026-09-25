# -*- coding: utf-8 -*-
"""การปรับตัวจากการใช้งานและความเสื่อมตามวัย (§34–35)

การฝึกไม่ได้เพิ่มกล้ามทันที แต่ทิ้ง ``stimulus`` ไว้ก่อน แล้วร่างค่อยสร้างตัวระหว่างพัก:

    dS/dt = -ks S
    dA/dt = g S - kd A

ระบบแก้สมการคู่นี้แบบปิด จึงให้ผลเดียวกันเมื่อเดิน 30 วันครั้งเดียวหรือแบ่งเป็น 30 ครั้ง
ค่าที่เก็บบน Character เป็นประวัติของร่างและต้องอยู่ในเซฟ ส่วนกายวิภาคตั้งต้นยังสร้างใหม่
จาก seed ได้เหมือนเดิม
"""
import math

from . import constants as K


SYSTEMS = ("muscle", "cardio", "bone")


def age_factors(age_years: float) -> dict:
    """ตัวคูณสมรรถภาพตามวัยแบบต่อเนื่อง ไม่มีหน้าผาที่วันเกิดวันใดวันหนึ่ง"""
    age = max(0.0, float(age_years))
    # เติบโตถึงวัยหนุ่มสาว จากนั้นเสื่อมช้า ๆ; ไม่ปล่อยให้เป็นศูนย์เพื่อรองรับผู้ฝึกตนอายุยืน
    growth = min(1.0, 0.55 + 0.45 * age / K.ADULT_AGE) if age < K.ADULT_AGE else 1.0
    decline = max(0.45, math.exp(-K.AGE_DECLINE_RATE * max(0.0, age - K.AGE_DECLINE_START)))
    return {
        "muscle": growth * decline,
        "cardio": growth * max(0.50, math.exp(-K.CARDIO_AGE_DECLINE * max(0.0, age - K.AGE_DECLINE_START))),
        "bone": min(1.0, 0.65 + 0.35 * age / K.BONE_MATURE_AGE) if age < K.BONE_MATURE_AGE
                else max(0.50, math.exp(-K.BONE_AGE_DECLINE * max(0.0, age - K.BONE_DECLINE_START))),
        "nerve": max(0.55, math.exp(-K.NERVE_AGE_DECLINE * max(0.0, age - K.AGE_DECLINE_START))),
        "recovery": max(0.35, math.exp(-K.RECOVERY_AGE_DECLINE * max(0.0, age - K.ADULT_AGE))),
    }


def factors(character) -> dict:
    """รวมวัยกับการปรับตัวเป็นตัวคูณที่ Condition ใช้"""
    aged = age_factors(getattr(character, "body_age", K.ADULT_AGE))
    for system in SYSTEMS:
        trained = max(0.0, min(1.0, float(getattr(character, system + "_adaptation", 0.0))))
        aged[system] *= 1.0 + K.ADAPTATION_MAX_GAIN[system] * trained
    return aged


def stimulate(character, work: float, cardio_share: float = 0.65,
              bone_share: float = 0.35) -> None:
    """บันทึกแรงกระตุ้นจากงานหนึ่งครั้ง; ยังไม่เพิ่มสมรรถภาพจนกว่าจะผ่านช่วงพัก"""
    dose = max(0.0, float(work))
    shares = {"muscle": 1.0, "cardio": cardio_share, "bone": bone_share}
    for system, share in shares.items():
        name = system + "_stimulus"
        old = max(0.0, float(getattr(character, name, 0.0)))
        # การกระตุ้นมีเพดานและให้ผลลดหลั่น ไม่สามารถ spam เหตุการณ์ให้ไร้ขอบเขต
        setattr(character, name, min(1.0, old + K.STIMULUS_PER_WORK * dose * share * (1.0 - old)))


def tick(character, days: float) -> None:
    """เดิน stimulus/adaptation/อายุด้วยคำตอบ exact ของระบบสมการเชิงเส้น"""
    t = max(0.0, float(days))
    if t <= 0.0:
        return
    recovery = age_factors(getattr(character, "body_age", K.ADULT_AGE))["recovery"]
    ks = K.STIMULUS_DECAY_RATE
    kd = K.ADAPTATION_DECAY_RATE
    gain = K.ADAPTATION_GAIN_RATE * recovery
    for system in SYSTEMS:
        s_name, a_name = system + "_stimulus", system + "_adaptation"
        s0 = max(0.0, min(1.0, float(getattr(character, s_name, 0.0))))
        a0 = max(0.0, min(1.0, float(getattr(character, a_name, 0.0))))
        es, ed = math.exp(-ks * t), math.exp(-kd * t)
        built = gain * s0 * ((ed - es) / (ks - kd) if ks != kd else t * ed)
        setattr(character, s_name, s0 * es)
        setattr(character, a_name, max(0.0, min(1.0, a0 * ed + built)))
    character.body_age = max(0.0, float(getattr(character, "body_age", 0.0)) + t / 365.0)


def explain(character) -> dict:
    f = factors(character)
    return {
        "อายุร่าง (ปี)": round(float(getattr(character, "body_age", 0.0)), 2),
        "การปรับตัว": {s: round(float(getattr(character, s + "_adaptation", 0.0)), 3)
                         for s in SYSTEMS},
        "แรงกระตุ้นคงเหลือ": {s: round(float(getattr(character, s + "_stimulus", 0.0)), 3)
                               for s in SYSTEMS},
        "ตัวคูณตามวัยและการฝึก": {k: round(v, 3) for k, v in f.items()},
    }
