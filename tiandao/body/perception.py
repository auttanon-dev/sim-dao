# -*- coding: utf-8 -*-
"""สิ่งที่เจ้าตัว **คิดว่า** ร่างกายตัวเองเป็นอยู่ (§33)

ทำไมต้องแยกจากของจริง
--------------------------------------------------------------------------------------------
ไม่มีใครอ่านปริมาตรเลือดของตัวเองเป็นเปอร์เซ็นต์ คนที่เสียเลือดไปหนึ่งในสี่รู้แค่ว่า
"หน้ามืด" และมักยืนยันว่ายังไหวจนล้มลงไปเอง การให้ระบบตัดสินใจอ่านค่าจริงตรงๆ จะได้
ตัวละครที่ถอยพอดีเป๊ะทุกครั้ง ซึ่งไม่ใช่พฤติกรรมของคน

จึงแยกสองอย่างออกจากกันตามพรอมต์ §33:

    ของจริง (actual)      ฟิสิกส์ใช้ — แรง ความเร็ว การหักของกระดูก การตาย
    ที่รู้สึก (perceived)   ใจใช้ — ประเมินว่าควรสู้หรือควรหนี

ทั้งคู่เป็น `Condition` ชนิดเดียวกัน จึงส่งเข้าฟังก์ชันความสามารถตัวเดิมได้ทั้งคู่
"ความเร็วที่คิดว่าตัวเองวิ่งได้" คือสมการเดียวกับความเร็วจริง เพียงแต่ป้อนสภาพที่รู้สึก
ไม่ต้องมีสมการชุดที่สองสำหรับความเชื่อ

แบบจำลองการรับรู้
--------------------------------------------------------------------------------------------
ใช้ log-normal ตัวเดียวกับที่ระบบความเชื่อใช้มองพลังคนอื่น (decision/beliefs.py) แต่ใส่กับ
**ส่วนที่พร่อง** ไม่ใช่กับค่าตรงๆ เพราะสิ่งที่ร่างรับรู้คือความผิดปกติ ไม่ใช่ระดับสัมบูรณ์:

    d̂ = d · (1 − g·b) · exp(σ·ε)        ε ~ N(0,1)

    d = ส่วนที่พร่องจริง (ความล้า · เลือดที่หายไป · เชื้อเพลิงที่หมดไป · อุณหภูมิที่เพี้ยนไป)
    b = อคติ −1..+1 (บวก = มองโลกในแง่ดี "ยังไหว")     g = PERCEPTION_BIAS_GAIN
    σ = ความไม่แม่นของสัญญาณนั้น × (1 + k·(1 − ออกซิเจนที่สมองได้))

ค่ามัธยฐานของการประมาณเท่ากับค่าจริงเสมอ (exp(σε) มีมัธยฐาน 1) — คนทั่วไปเดาถูก
"โดยเฉลี่ย" แต่ผิดได้มากเป็นรายครั้ง และพจน์ออกซิเจนทำให้เกิดผลที่ตั้งใจให้เกิด:
**ยิ่งใกล้ตายยิ่งประเมินตัวเองเพี้ยน** สมองที่ขาดออกซิเจนตัดสินใจแย่ลงจริง

ข้อจำกัดที่รู้ตัว (§41)
--------------------------------------------------------------------------------------------
ระดับความเสียหายถูกนิยามไว้ในช่วง 0..1 ค่าที่รู้สึกจึงถูกหนีบที่ 1 ด้วย หางบนของการประเมิน
แผลที่เกือบพังสนิทจึงถูกตัดทิ้ง (วัดที่ระดับ 0.95: ราว 45% ของวันชนเพดาน ค่าเฉลี่ยของ
ความบาดเจ็บที่รู้สึกจึงต่ำกว่าของจริงราว 10%) **มัธยฐานยังตรงกับความจริงทุกระดับ** ซึ่งเป็น
สิ่งที่แบบจำลองนี้รับประกัน ไม่ใช่ค่าเฉลี่ย

ความคงที่และเซฟ
--------------------------------------------------------------------------------------------
ไม่เก็บอะไรลงตัวละครเลย ค่าที่รู้สึกคำนวณจาก (cid, วัน, สัญญาณ) จึงคงที่ตลอดทั้งวัน
ถามกี่ครั้งก็ได้คำตอบเดิม เดินต่อจากเซฟแล้วได้ค่าเดิม และไม่แตะ RNG หลักของโลก
"""
from . import constants as K
from . import injury as INJ
from .condition import Condition, resolve

#: สัญญาณที่ร่างรับรู้เกี่ยวกับตัวเอง — เรียงตามความแม่น (แม่นสุดก่อน)
SIGNALS = ("fatigue", "fuel", "temp", "injury", "blood")


def sigma(signal: str, cond) -> float:
    """ความไม่แม่นของสัญญาณหนึ่ง ณ สภาพปัจจุบัน

    ฐานมาจากตัวสัญญาณเอง แล้วบานออกเมื่อสมองได้ออกซิเจนน้อยลง — คนที่เสียเลือดหนัก
    ไม่ได้แค่ "อ่อนแรง" แต่ประเมินสภาพตัวเองผิดมากขึ้นด้วย
    """
    base = K.INTEROCEPTION_SD.get(signal, 0.25)
    hypoxia = 1.0 + K.HYPOXIA_NOISE_GAIN * (1.0 - resolve(cond).oxygen_factor)
    return max(K.PERCEPTION_SIGMA_FLOOR, base * hypoxia)


def _noise(cid, day, signal, sd: float, *extra) -> float:
    """exp(σ·ε) จากคีย์ — ค่าเดิมเสมอสำหรับ (คน, วัน, สัญญาณ) เดิม"""
    if sd <= 0.0:
        return 1.0
    import math
    eps = INJ.rng_for("perceive", cid, int(day), signal, *extra).gauss(0.0, 1.0)
    return math.exp(sd * eps)


def _felt(deficit: float, sd: float, bias: float, cid, day, signal, *extra) -> float:
    """ส่วนที่พร่องจริง → ส่วนที่พร่องตามที่รู้สึก"""
    if deficit <= 0.0:
        return 0.0
    tilt = max(0.0, 1.0 - K.PERCEPTION_BIAS_GAIN * max(-1.0, min(1.0, bias)))
    return deficit * tilt * _noise(cid, day, signal, sd, *extra)


def perceive(character, day: float = 0.0, bias: float = 0.0, actual=None) -> Condition:
    """สภาพร่างกาย **ตามที่เจ้าตัวรู้สึก** — ชนิดเดียวกับของจริง จึงใช้แทนกันได้ทุกที่

    `bias` บวก = มองโลกในแง่ดี (กล้า/ประมาท) · ลบ = มองในแง่ร้าย (ระแวง/ขลาด)
    ผู้เรียกเป็นคนแปลงนิสัยของโลกตัวเองมาเป็นเลขตัวนี้ — ร่างกายไม่รู้จักนิสัย
    """
    cond = resolve(character if actual is None else actual)
    cid = getattr(character, "cid", 0)
    # ขอบของความเชื่อ: คนที่ยังยืนพูดอยู่ **รู้** ว่าตัวเองไม่ได้หมดสติ ความเชื่อจึงห้ามหลุด
    # ไปอยู่ฝั่งที่ขัดกับข้อเท็จจริงนั้น ไม่ใช่การกดตัวเลขให้สวย แต่เพราะสัญญาณที่เถียงไม่ได้
    # (ยังรู้สึกตัว) เป็นข้อมูลที่เจ้าตัวมีอยู่ในมือเสมอ — ถ้าไม่หนีบ หางของ log-normal จะ
    # สร้างคนที่เชื่อว่าตัวเองเสียเลือดไปครึ่งตัวทั้งที่กำลังวิ่งอยู่
    floor = (min(cond.blood, K.BLOOD_UNCONSCIOUS_BELOW + K.PERCEPTION_SIGMA_FLOOR)
             if cond.conscious else 0.0)
    injuries = None
    if cond.injury:
        # แต่ละส่วนเพี้ยนของมันเอง — จึงเกิดกรณีที่รู้ว่าเจ็บ แต่เข้าใจผิดว่าเจ็บตรงไหนหนักกว่า
        sd_inj = sigma("injury", cond)
        injuries = {}
        for region, tissues in cond.injury.items():
            if not tissues:
                continue
            felt = {t: min(1.0, _felt(v, sd_inj, bias, cid, day, "injury", region))
                    for t, v in tissues.items() if v > 0.0}
            if felt:
                injuries[region] = felt
    return Condition(
        fatigue=_felt(cond.fatigue, sigma("fatigue", cond), bias, cid, day, "fatigue"),
        blood=max(floor, 1.0 - _felt(1.0 - cond.blood, sigma("blood", cond),
                                     bias, cid, day, "blood")),
        fuel=1.0 - _felt(1.0 - cond.fuel, sigma("fuel", cond), bias, cid, day, "fuel"),
        core_temp=K.CORE_TEMP_NORMAL + _signed(
            cond.core_temp - K.CORE_TEMP_NORMAL, sigma("temp", cond), bias, cid, day, "temp"),
        injury=injuries, muscle_factor=cond.muscle_factor, cardio_factor=cond.cardio_factor,
        bone_factor=cond.bone_factor, nerve_factor=cond.nerve_factor,
        recovery_factor=cond.recovery_factor)


def _signed(delta: float, sd: float, bias: float, cid, day, signal) -> float:
    """เหมือน `_felt` แต่รักษาเครื่องหมาย — หนาวยังคงหนาว ไม่กลายเป็นร้อน"""
    if delta == 0.0:
        return 0.0
    mag = _felt(abs(delta), sd, bias, cid, day, signal)
    return mag if delta > 0 else -mag


def band(character, day: float = 0.0, bias: float = 0.0, z: float = 1.0) -> dict:
    """ช่วงที่เจ้าตัว "พอจะบอกได้" ของแต่ละสัญญาณ (§33 "blood_loss ≈ 15–30%")

    ค่าที่รู้สึกคือจุดกลาง ส่วนความกว้างมาจาก σ ของสัญญาณนั้นโดยตรง:
    ช่วง = [d̂·e^(−zσ), d̂·e^(+zσ)] — ยิ่งสัญญาณคลุมเครือ ช่วงยิ่งกว้าง และช่วงของ
    คนที่เสียเลือดหนักจะกว้างกว่าของคนปกติเพราะ σ บานตามภาวะขาดออกซิเจน
    """
    import math
    cond = resolve(character)
    felt = perceive(character, day, bias, cond)
    out = {}
    for signal, value in (("fatigue", felt.fatigue), ("blood", 1.0 - felt.blood),
                          ("fuel", 1.0 - felt.fuel), ("injury", INJ.severity(felt.injury))):
        sd = sigma(signal, cond)
        spread = math.exp(z * sd)
        out[signal] = (round(max(0.0, value / spread), 3), round(min(1.0, value * spread), 3))
    return out


# ---------------------------------------------------------------- คำพูดแทนตัวเลข (§33)
# เจ้าตัวไม่ได้คิดเป็นตัวเลข — ลำดับนี้คือ "สิ่งที่รู้สึกก่อน" ไล่จากเรื่องที่ร้ายแรงที่สุด
def describe(cond) -> str:
    """สรุปสภาพที่รู้สึกเป็นคำเดียว — สิ่งที่ตัวละครจะพูดถ้ามีใครถามว่าเป็นอย่างไรบ้าง"""
    from . import metabolism as MET
    cond = resolve(cond)
    if not cond.conscious:
        return "จะไปแล้ว"
    thermal = MET.thermal_state(cond.core_temp)
    if thermal != "ปกติ":
        return thermal
    sev = INJ.severity(cond.injury)
    if cond.blood < K.BLOOD_COMPENSATED_ABOVE or sev >= 0.5:
        return "บาดเจ็บสาหัส"
    if sev >= 0.2:
        return "บาดเจ็บ"
    if cond.fatigue >= 0.7:
        return "หมดแรง"
    if cond.fatigue >= 0.35 or cond.fuel < 0.35:
        return "เหนื่อยล้า"
    if sev > 0.0:
        return "มีแผลเล็กน้อย"
    return "ปกติดี"


def explain(character, day: float = 0.0, bias: float = 0.0) -> dict:
    """เทียบของจริงกับที่รู้สึกไว้ข้างกัน (§44) — ใช้ดูว่าตัวละครกำลังหลอกตัวเองแค่ไหน"""
    actual = resolve(character)
    felt = perceive(character, day, bias, actual)
    return {
        "อคติ": round(bias, 3),
        "ของจริง": {"ความล้า": round(actual.fatigue, 3),
                    "เลือดที่เสียไป": round(1.0 - actual.blood, 3),
                    "บาดเจ็บรวม": round(INJ.severity(actual.injury), 3),
                    "คำเดียว": describe(actual)},
        "ที่รู้สึก": {"ความล้า": round(felt.fatigue, 3),
                     "เลือดที่เสียไป": round(1.0 - felt.blood, 3),
                     "บาดเจ็บรวม": round(INJ.severity(felt.injury), 3),
                     "คำเดียว": describe(felt)},
        "ช่วงที่พอบอกได้": band(character, day, bias),
        "ความไม่แม่นตอนนี้": {s: round(sigma(s, actual), 3) for s in SIGNALS},
    }
