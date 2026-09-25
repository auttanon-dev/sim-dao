# -*- coding: utf-8 -*-
"""เลือด การไหลเวียน และความล้า (§8, §16–19)

ทำไมสามเรื่องนี้อยู่ไฟล์เดียวกัน
--------------------------------------------------------------------------------------------
เพราะมันเป็นวงจรเดียวกัน กล้ามเนื้อออกแรง → ต้องการออกซิเจน → หัวใจสูบเลือดไปส่ง →
ถ้าส่งไม่ทันความล้าสะสมเร็วขึ้น และถ้าเสียเลือด ทุกพจน์ในโซ่นี้ลดลงพร้อมกัน แยกไฟล์แล้ว
จะต้องอ้างอิงไปมาจนอ่านยากกว่าเดิม

    ปริมาตรเลือด      BV = มวลกาย × สัมประสิทธิ์                         (§17)
    ปริมาตรต่อครั้ง    SV ∝ ปริมาตรเลือดที่มี
    เลือดที่สูบได้      CO = HR × SV                                      (§16)
    ออกซิเจนที่ส่งได้   DO2 = CO × ความเข้มข้นออกซิเจนในเลือด              (§19)
    เลือดที่เสียไป      dV/dt = −Q  →  V(t) = V₀ − ∫Q dt                  (§18)
    ความล้า            dF/dt = อัตรา × ภาระงาน − อัตราฟื้น × (เวลาพัก)     (§8)

ทุกสมการอินทิเกรตเป็น **รูปแบบปิดข้ามช่วงเวลา** ไม่ใช่เดินทีละก้าว เพราะเอนจินนี้กระโดด
ข้ามเวลาเป็นวัน (ดู Event.gap_days) ใช้ physics.relax เหมือนที่การหายของบาดแผลใช้

ข้อจำกัด (§41)
--------------------------------------------------------------------------------------------
ไม่มีความดันโลหิตเป็นตัวเลขจริง ไม่มีการแยกหลอดเลือดแดง/ดำ ไม่มีภาวะช็อกเป็นสถานะแยก
อัตราการไหลของเลือดออกคิดจาก "ความเสียหายของหลอดเลือดในส่วนนั้น" รวมๆ ไม่ใช่รายเส้น
เป้าหมายคือให้การเสียเลือดมีน้ำหนักจริงในการตัดสินใจ ไม่ใช่ความแม่นยำทางเวชศาสตร์
"""
from .. import physics as PHYS
from . import constants as K


# ---------------------------------------------------------------- ปริมาตรเลือด (§17)
def blood_volume(body) -> float:
    """ปริมาตรเลือดปกติของร่างนี้ (ลิตร) — จากมวลกาย ไม่ใช่ค่าที่ตั้งไว้"""
    return body.mass * K.BLOOD_VOLUME_PER_KG


def blood_litres(body, cond) -> float:
    """ปริมาตรเลือดที่เหลืออยู่จริงตอนนี้ (ลิตร)"""
    return blood_volume(body) * cond.blood


# ---------------------------------------------------------------- การสูบฉีด (§16)
def heart_rate(body, cond, exertion: float = 0.0) -> float:
    """อัตราการเต้นหัวใจ (ครั้ง/นาที) — ขึ้นตามงานที่ทำ และขึ้นอีกเมื่อเสียเลือด

    หัวใจเร่งเพื่อชดเชยเลือดที่หายไป นี่คือเหตุผลที่เลือดพร่องเล็กน้อยแทบไม่มีผลต่อ
    สมรรถภาพ — ร่างชดเชยได้จนถึงจุดหนึ่ง แล้วจึงทรุด (ดู Condition.oxygen_factor)
    """
    rest = K.HEART_RATE_REST
    span = K.HEART_RATE_MAX - rest
    load = min(1.0, max(0.0, exertion))
    deficit = max(0.0, 1.0 - cond.blood)
    return min(K.HEART_RATE_MAX, rest + span * (load + deficit * K.HEART_COMPENSATION))


def stroke_volume(body, cond) -> float:
    """ปริมาตรเลือดที่หัวใจส่งออกต่อการบีบหนึ่งครั้ง (ลิตร)

    ∝ ปริมาตรเลือดที่มีอยู่ — เลือดน้อยลง หัวใจก็มีของให้ส่งน้อยลงในแต่ละครั้ง
    """
    return blood_volume(body) * K.STROKE_VOLUME_FRACTION * cond.blood * cond.cardio_factor


def cardiac_output(body, cond, exertion: float = 0.0) -> float:
    """CO = HR × SV  (ลิตร/นาที)"""
    return heart_rate(body, cond, exertion) * stroke_volume(body, cond)


def oxygen_delivery(body, cond, exertion: float = 0.0) -> float:
    """DO2 = CO × ความเข้มข้นออกซิเจนในเลือด  (ลิตรออกซิเจน/นาที) — §19

    เสียเลือดกดค่านี้ **สองทาง**: ปริมาตรต่อครั้งลดลง และความเข้มข้นออกซิเจนลดลง
    ผลจึงแรงกว่าที่เห็นจากตัวเลขเลือดตรงๆ ซึ่งตรงกับความจริง
    """
    return cardiac_output(body, cond, exertion) * K.ARTERIAL_O2_CONTENT * cond.blood


# ---------------------------------------------------------------- เลือดออก (§18)
def bleed_rate(character) -> float:
    """อัตราการเสียเลือดตอนนี้ — สัดส่วนของปริมาตรปกติต่อวัน

    เป็น **สถานะที่เก็บไว้** ไม่ใช่ค่าที่คำนวณสดจากแผล เพราะการแข็งตัวของเลือดเป็น
    กระบวนการที่เดินหน้าไปตามเวลา ถ้าคำนวณใหม่จากความเสียหายของหลอดเลือดทุกครั้ง
    แผลเดิมจะ "เริ่มแข็งตัวใหม่" ทุกครั้งที่ถูกถาม แล้วปริมาณเลือดที่เสียจะขึ้นกับว่าเรา
    เรียก tick() กี่ครั้ง ไม่ใช่ขึ้นกับเวลาที่ผ่านไป (วัดจริง: เดิน 60 ก้าวเสียเลือด 49%
    แต่เดินทีเดียว 60 วันเสีย 20% ทั้งที่ควรเท่ากัน)
    """
    return max(0.0, float(getattr(character, "bleed", 0.0)))


def open_wound(character, vessel_damage: float) -> float:
    """เปิดแผลใหม่ — เพิ่มอัตราเลือดออกตามความเสียหายของหลอดเลือดที่เพิ่งเกิด"""
    if vessel_damage <= 0.0:
        return bleed_rate(character)
    character.bleed = bleed_rate(character) + vessel_damage * K.BLEED_PER_VESSEL_DAMAGE
    return character.bleed


def tick(character, body, days: float) -> dict:
    """เดินสภาพร่างกายไปข้างหน้าตามเวลาที่ผ่านไปจริง — แก้ตัวละครในที่

    ทุกพจน์อินทิเกรตเป็นรูปแบบปิด และ **ผลไม่ขึ้นกับว่าแบ่งช่วงเวลาละเอียดแค่ไหน**
    เพราะอัตราเลือดออกเป็นสถานะที่สลายตัวเอง ไม่ใช่ค่าที่เริ่มนับใหม่ทุกครั้ง:

        เสียไปทั้งหมด = Q₀·(1 − e^{−k·t}) / k        แล้ว  Q(t) = Q₀·e^{−k·t}

    ซึ่งต่อกันได้พอดีเมื่อแบ่งเป็นช่วงย่อย (ผลรวมของอนุกรมเรขาคณิตยุบกลับเป็นสูตรเดิม)
    """
    from .condition import Condition
    if days <= 0.0:
        return {}
    cond = Condition.of(character)
    lost = 0.0
    rate = bleed_rate(character)
    if rate > 0.0:
        clot = K.CLOT_RATE_PER_DAY
        # ความดันที่ยังดันเลือดออกมาได้ลดลงเมื่อเลือดพร่อง — ใช้ค่า ณ ต้นช่วง
        lost = rate * cond.blood * (1.0 - PHYS.relax(1.0, 0.0, clot, days)) / clot
        character.blood_frac = max(0.0, cond.blood - lost)
        character.bleed = PHYS.relax(rate, 0.0, clot, days)

    # สร้างเลือดใหม่เข้าหาระดับปกติ — ช้ากว่าการเสียมาก (ครึ่งทางในราวห้าสัปดาห์)
    character.blood_frac = PHYS.relax(getattr(character, "blood_frac", 1.0), 1.0,
                                      K.BLOOD_REGEN_RATE * cond.recovery_factor, days)
    character.fatigue = PHYS.relax(getattr(character, "fatigue", 0.0), 0.0,
                                   K.FATIGUE_RECOVERY_RATE * cond.recovery_factor, days)
    return {"เสียเลือด (เท่าของปกติ)": round(lost, 4),
            "เลือดคงเหลือ": round(character.blood_frac, 4),
            "อัตราที่ยังไหลอยู่": round(character.bleed, 5),
            "ความล้า": round(character.fatigue, 4)}


# ---------------------------------------------------------------- ความล้า (§8)
def exert(character, work: float) -> float:
    """สะสมความล้าจากงานที่เพิ่งทำ — คืนระดับความล้าใหม่

        dF = อัตรา × ภาระงาน × (1 − F)

    พจน์ (1 − F) ทำให้ความล้าเข้าใกล้ 1 แบบเส้นกำกับ ไม่ทะลุ และทำให้ครั้งแรกๆ เหนื่อย
    มากกว่าครั้งหลังเมื่อเหนื่อยอยู่แล้ว ซึ่งตรงกับความรู้สึกจริงมากกว่าการบวกคงที่
    """
    now = min(1.0, max(0.0, getattr(character, "fatigue", 0.0)))
    now += K.FATIGUE_PER_WORK * max(0.0, work) * (1.0 - now)
    character.fatigue = min(1.0, now)
    return character.fatigue


def explain(body, cond, exertion: float = 0.0, character=None) -> dict:
    return {
        "ปริมาตรเลือดปกติ (L)": round(blood_volume(body), 2),
        "เหลืออยู่ (L)": round(blood_litres(body, cond), 2),
        "อัตราหัวใจ (ครั้ง/นาที)": round(heart_rate(body, cond, exertion)),
        "ส่งออกต่อครั้ง (mL)": round(stroke_volume(body, cond) * 1000, 1),
        "เลือดที่สูบได้ (L/นาที)": round(cardiac_output(body, cond, exertion), 2),
        "ออกซิเจนที่ส่งได้ (L/นาที)": round(oxygen_delivery(body, cond, exertion), 3),
        "อัตราเลือดออก (เท่าของปกติ/วัน)": round(bleed_rate(character), 4) if character else 0.0,
        "ตัวคูณจากออกซิเจน": round(cond.oxygen_factor, 3),
        "รู้สึกตัว": cond.conscious,
    }
