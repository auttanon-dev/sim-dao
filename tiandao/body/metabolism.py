# -*- coding: utf-8 -*-
"""งานกล พลังงาน การหายใจ และอุณหภูมิกาย (§20–23)

ทำไมสี่เรื่องนี้อยู่ไฟล์เดียวกัน
--------------------------------------------------------------------------------------------
เพราะเป็นบัญชีเดียวกันที่ปิดได้ กล้ามเนื้อทำงานกล → ต้องใช้พลังงานเคมีมากกว่านั้นสี่เท่า
เพราะประสิทธิภาพราว 25% → **ส่วนที่เหลือกลายเป็นความร้อนทั้งหมด** → ร่างต้องระบายทิ้ง
และการเผาผลาญนั้นต้องการออกซิเจน ซึ่งการหายใจกับการไหลเวียนเป็นผู้ส่ง ถ้าแยกไฟล์
จะต้องอ้างถึงกันไปมาจนอ่านยากกว่าอยู่ด้วยกัน

    ต้นทุนพลังงาน   E = W / ประสิทธิภาพ                              (§22)
    ความร้อนที่เกิด  Q = E × (1 − ประสิทธิภาพ)                        (§22 → §23)
    อัตราพื้นฐาน     BMR ∝ มวล^0.75                                   (กฎของไคลเบอร์)
    การระบายอากาศ   VE = อัตราหายใจ × ปริมาตรต่อครั้ง                  (§20)
    ออกซิเจนที่ต้องใช้ = กำลังเผาผลาญ / พลังงานต่อลิตรออกซิเจน           (§20)
    สมดุลความร้อน   dT/dt = (Q_เกิด − Q_ระบาย) / (m·c)                 (§23)

**หมายเหตุสำคัญเรื่องสมการอุณหภูมิ** สเปกเขียนไว้ว่า `dT/dt = HeatGenerated − HeatLost`
ซึ่ง **หน่วยไม่ใช่เคลวินต่อวินาที** — มันคือวัตต์ สมการที่ถูกต้องต้องหารด้วยความจุความร้อน
ของร่างทั้งก้อน (m·c) ผลพลอยได้คือเราได้ค่าคงที่เวลา τ = m·c/(kA) มาฟรี ซึ่งทำให้
**คนตัวใหญ่เย็นช้ากว่าคนตัวเล็ก** โดยไม่ต้องเขียนกฎข้อนั้นเลย

สองอย่างที่โผล่ออกมาจากองค์ประกอบร่างกายเอง ไม่ได้เขียนเป็นกฎ
--------------------------------------------------------------------------------------------
  · **ไขมันคือเชื้อเพลิง** — คนที่มีไขมันมากอดได้นานกว่าเป็นสัปดาห์ เพราะ 1 กิโลกรัม
    ให้พลังงานราว 37 เมกะจูล มากกว่าคลังไกลโคเจนทั้งตัวหลายสิบเท่า
  · **ไขมันคือฉนวน** — ชั้นไขมันหนากว่านำความร้อนออกช้ากว่า จึงทนหนาวได้จริง
    คนผอมที่วิ่งเร็วกว่าเป็นคนเดียวกับที่ตายก่อนในฤดูหนาว

ข้อจำกัด (§41)
--------------------------------------------------------------------------------------------
ไม่มีการแยกไกลโคเจนในตับกับในกล้ามเนื้อ ไม่มีคีโตน ไม่มีการปรับตัวของเมตาบอลิซึม
ไม่มีเหงื่อเป็นกลไกแยก (คิดรวมอยู่ในสัมประสิทธิ์การระบาย) และไม่มีภาวะไข้จากการติดเชื้อ
เป้าหมายคือให้ "อดอยาก" และ "หนาวตาย" เป็นผลของบัญชีที่ปิดได้ ไม่ใช่สถานะที่ตั้งขึ้น
"""
from .. import physics as PHYS
from . import constants as K


# ---------------------------------------------------------------- งานกลและต้นทุน (§22)
def metabolic_cost(work_joules: float, efficiency: float = None) -> float:
    """พลังงานเคมีที่ต้องใช้เพื่อทำงานกลเท่านี้ (J)

        E = W / ประสิทธิภาพ                                  (§22)

    ประสิทธิภาพราว 25% แปลว่าทุกหนึ่งจูลของงานที่ทำได้จริง ต้องเผาสี่จูล
    """
    eff = K.MUSCLE_EFFICIENCY if efficiency is None else efficiency
    return max(0.0, work_joules) / max(1e-9, eff)


def heat_from_work(work_joules: float, efficiency: float = None) -> float:
    """ความร้อนที่เกิดจากการทำงานกลเท่านี้ (J) — ส่วนที่ไม่ได้กลายเป็นงาน"""
    eff = K.MUSCLE_EFFICIENCY if efficiency is None else efficiency
    return metabolic_cost(work_joules, eff) * (1.0 - eff)


def basal_rate(body) -> float:
    """อัตราเผาผลาญพื้นฐาน (วัตต์) — จากมวลกาย ไม่ใช่ค่าที่ตั้งไว้

        BMR ∝ มวล^0.75        (กฎของไคลเบอร์)

    เลขชี้กำลัง 3/4 ไม่ใช่ 1 คือเหตุผลที่สัตว์ตัวใหญ่กินน้อยกว่าตามสัดส่วนน้ำหนัก
    และเป็นที่มาของความจริงที่ว่าคนตัวเล็กหิวบ่อยกว่าเมื่อเทียบต่อกิโลกรัม
    """
    return K.BMR_COEF * (body.mass ** K.BMR_EXPONENT)


def metabolic_power(body, exertion: float = 0.0) -> float:
    """กำลังเผาผลาญรวมตอนนี้ (วัตต์) — พื้นฐานบวกส่วนที่มาจากการออกแรง"""
    return basal_rate(body) * (1.0 + K.EXERTION_METABOLIC_SPAN * max(0.0, exertion))


# ---------------------------------------------------------------- คลังพลังงาน (§21)
def glycogen_capacity(body) -> float:
    """พลังงานที่คลังไกลโคเจนเก็บได้เต็มที่ (J)

    ไกลโคเจนเก็บอยู่ในกล้ามเนื้อและตับ คลังจึงโตตาม **มวลกล้ามเนื้อ** ไม่ใช่ตามน้ำหนักตัว
    """
    return body.muscle_mass * K.GLYCOGEN_PER_KG_MUSCLE


def fat_reserve(body) -> float:
    """พลังงานที่ไขมันในตัวเก็บไว้ (J) — คลังใหญ่ที่สุดของร่างอย่างไม่มีอะไรใกล้เคียง"""
    return body.fat_mass * K.FAT_ENERGY_PER_KG


def endurance_days(body, cond, exertion: float = 0.0) -> float:
    """อดได้กี่วันก่อนเชื้อเพลิงหมด — ผลรวมของคลังทั้งสองหารด้วยกำลังที่ใช้

    คนอ้วนอดได้นานกว่าเป็นสัปดาห์ ไม่ใช่เพราะเขียนกฎไว้ แต่เพราะไขมันคือเชื้อเพลิงจริง
    """
    power = metabolic_power(body, exertion)
    if power <= 0.0:
        return float("inf")
    stored = glycogen_capacity(body) * cond.fuel + fat_reserve(body)
    return stored / (power * 86400.0)


# ---------------------------------------------------------------- การหายใจ (§20)
def oxygen_demand(body, exertion: float = 0.0) -> float:
    """ออกซิเจนที่ต้องใช้ตอนนี้ (ลิตร/นาที)

        ความต้องการ = กำลังเผาผลาญ / พลังงานที่ได้ต่อออกซิเจนหนึ่งลิตร
    """
    watts = metabolic_power(body, exertion)
    return watts * 60.0 / K.ENERGY_PER_LITRE_O2


def minute_ventilation(body, exertion: float = 0.0) -> float:
    """VE = อัตราหายใจ × ปริมาตรต่อครั้ง (ลิตร/นาที) — §20

    ปริมาตรต่อครั้งโตตามขนาดร่าง ส่วนอัตราหายใจเร่งตามงานที่ทำ
    """
    tidal = body.mass * K.TIDAL_VOLUME_PER_KG
    rate = K.RESP_RATE_REST + (K.RESP_RATE_MAX - K.RESP_RATE_REST) * min(1.0, max(0.0, exertion))
    return rate * tidal


def oxygen_debt(body, cond, exertion: float = 0.0) -> float:
    """ส่วนของความต้องการออกซิเจนที่ส่งไปไม่ถึง (0..1) — §19–20

    ถ้าการไหลเวียนส่งได้น้อยกว่าที่การเผาผลาญต้องการ ส่วนที่ขาดต้องไปเอาจากวิถีไร้ออกซิเจน
    ซึ่งสะสมความล้าเร็วกว่ามาก นี่คือจุดที่ระบบเลือดของ Phase 4 มาเจอกับพลังงานของเฟสนี้
    """
    from . import circulation as CIRC
    need = oxygen_demand(body, exertion)
    if need <= 0.0:
        return 0.0
    supply = CIRC.oxygen_delivery(body, cond, exertion) * K.O2_EXTRACTION
    return max(0.0, min(1.0, 1.0 - supply / need))


# ---------------------------------------------------------------- อุณหภูมิกาย (§23)
def heat_capacity(body) -> float:
    """ความจุความร้อนของร่างทั้งก้อน (J/K) — m·c"""
    return body.mass * K.BODY_SPECIFIC_HEAT


def conductance(body, clothing: float = None, wind: float = 0.0, wet: bool = False) -> float:
    """ความสามารถระบายความร้อนออกสู่สิ่งแวดล้อม (W/K)

        k_eff · A       โดย A คือพื้นที่ผิว

    ชั้นไขมันเป็นฉนวน จึงลดค่านี้ — **คนอ้วนเย็นช้ากว่า** โดยไม่ต้องเขียนกฎข้อนั้น
    ลมเพิ่มการพา น้ำเพิ่มมหาศาล (น้ำนำความร้อนดีกว่าอากาศหลายสิบเท่า) เสื้อผ้าลด
    """
    from . import injury as INJ
    clothing = K.DEFAULT_CLOTHING if clothing is None else clothing
    area = INJ.surface_area(body)
    fat_layer = body.fat_mass / (K.FAT_DENSITY * max(1e-6, area))   # ความหนาเฉลี่ย (m)
    insulation = 1.0 + fat_layer * K.FAT_INSULATION + max(0.0, clothing) * K.CLOTHING_INSULATION
    k = K.SKIN_CONDUCTANCE * (1.0 + max(0.0, wind) * K.WIND_CONVECTION)
    if wet:
        k *= K.WET_CONDUCTION_MULT
    return k * area / insulation


def equilibrium_temp(body, ambient: float, exertion: float = 0.0, clothing: float = None,
                     wind: float = 0.0, wet: bool = False) -> float:
    """อุณหภูมิที่ร่างจะเข้าสู่สมดุลถ้าสภาพนี้อยู่นานพอ (°C)

    ถ้าร่างเป็นก้อนวัตถุเฉยๆ สมดุลคือ T = T_อากาศ + Q/(k·A) ซึ่งให้ 30°C ที่อากาศ 24°C
    — ทั้งโลกจะตายด้วยภาวะตัวเย็น สิ่งมีชีวิตไม่ได้ทำแบบนั้น **มันสู้กลับ**

        Q(T) = Q₀ · (1 + g·(T_ตั้ง − T))      เมื่อ T ต่ำกว่าจุดตั้ง (สั่น · หดหลอดเลือด)

    ใส่กลับเข้าสมการสมดุล Q(T) = k·A·(T − T_อากาศ) แล้วแก้หา T ได้รูปแบบปิด:

        T = [ Q₀·(1 + g·T_ตั้ง) + k·A·T_อากาศ ] / ( k·A + Q₀·g )

    การผลิตความร้อนมีเพดาน (สั่นเต็มที่ได้ราวห้าเท่า) พอพ้นเพดานแล้วร่างสู้ไม่ไหวอีก
    อุณหภูมิจึงร่วงตามฟิสิกส์ล้วน — นั่นคือจุดที่ความหนาวเริ่มฆ่าคนจริง
    """
    cloth = K.DEFAULT_CLOTHING if clothing is None else clothing
    base = metabolic_power(body, exertion) * K.METABOLIC_HEAT_SHARE
    k = conductance(body, cloth, wind, wet)
    if k <= 0.0:
        return K.HYPERTHERMIA_ABOVE
    g = K.SHIVER_GAIN
    regulated = (base * (1.0 + g * K.TEMP_SET_POINT) + k * ambient) / (k + base * g)
    # ตรวจว่าการผลิตความร้อนที่ต้องใช้ ณ จุดนั้น ยังอยู่ในเพดานที่ร่างทำได้จริงไหม
    need = base * (1.0 + g * max(0.0, K.TEMP_SET_POINT - regulated))
    ceiling = base * K.SHIVER_MAX
    if need <= ceiling:
        return min(regulated, K.TEMP_SET_POINT + base / k) if regulated > K.TEMP_SET_POINT             else regulated
    # สู้ไม่ไหวแล้ว — ตรึงการผลิตไว้ที่เพดาน แล้วปล่อยให้ฟิสิกส์ตัดสิน
    return ambient + ceiling / k


def step_temperature(body, now: float, ambient: float, days: float, exertion: float = 0.0,
                     clothing: float = None, wind: float = 0.0, wet: bool = False) -> float:
    """เดินอุณหภูมิแกนกลางไปข้างหน้า (°C) — รูปแบบปิด ไม่ใช่ออยเลอร์

        dT/dt = (Q_เกิด − k·A·(T − T_อากาศ)) / (m·c)

    เป็นสมการเชิงอนุพันธ์เชิงเส้น คำตอบคือการเข้าหา T_สมดุล แบบเอกซ์โพเนนเชียลด้วย
    ค่าคงที่เวลา τ = m·c / (k·A) — จึงใช้ physics.relax ได้ตรงๆ เหมือนทุกอย่างในระบบนี้

    **τ คือเหตุผลที่คนตัวใหญ่เย็นช้ากว่า** มวลอยู่ในตัวเศษ พื้นที่ผิวอยู่ในตัวส่วน และ
    พื้นที่ผิวโตช้ากว่ามวล นี่คือกฎกำลังสองกับกำลังสามที่ทำให้สัตว์ขั้วโลกตัวใหญ่
    """
    cloth = K.DEFAULT_CLOTHING if clothing is None else clothing
    k = conductance(body, cloth, wind, wet)
    cap = heat_capacity(body)
    if k <= 0.0 or cap <= 0.0:
        return now
    target = equilibrium_temp(body, ambient, exertion, cloth, wind, wet)
    return PHYS.relax(now, target, k / cap * 86400.0, days)


def thermal_state(core: float) -> str:
    """ชื่อสภาวะจากอุณหภูมิแกนกลาง — ใช้ในบันทึกและการตัดสินใจ"""
    if core <= K.HYPOTHERMIA_DEATH:
        return "ตัวเย็นจนหัวใจหยุด"
    if core <= K.HYPOTHERMIA_BELOW:
        return "ตัวเย็นเกิน"
    if core >= K.HYPERTHERMIA_DEATH:
        return "ร่างร้อนจนอวัยวะล้มเหลว"
    if core >= K.HYPERTHERMIA_ABOVE:
        return "ร่างร้อนเกิน"
    return "ปกติ"


def thermal_penalty(core: float) -> float:
    """ส่วนของสมรรถภาพที่หายไปเพราะอุณหภูมิผิดปกติ (0..1)

    ในช่วงปกติเป็นศูนย์ แล้วไต่ขึ้นเมื่อพ้นขอบทั้งสองข้าง — ร่างกายทำงานได้ดีในช่วงแคบ
    """
    if K.HYPOTHERMIA_BELOW < core < K.HYPERTHERMIA_ABOVE:
        return 0.0
    if core <= K.HYPOTHERMIA_BELOW:
        span = max(1e-6, K.HYPOTHERMIA_BELOW - K.HYPOTHERMIA_DEATH)
        return min(1.0, (K.HYPOTHERMIA_BELOW - core) / span)
    span = max(1e-6, K.HYPERTHERMIA_DEATH - K.HYPERTHERMIA_ABOVE)
    return min(1.0, (core - K.HYPERTHERMIA_ABOVE) / span)


def climate_of(day: int) -> tuple:
    """อากาศและการแต่งกายของวันนั้น — ต่อยอดจาก seasons.SEASON_TABLE ที่โลกใช้อยู่แล้ว

    คืน (อุณหภูมิอากาศ °C, ความหนาของเสื้อผ้า) ตั้งใจไม่สร้างระบบอากาศคู่ขนานขึ้นใหม่
    ด้วยเหตุผลเดียวกับที่ seasons.py เขียนไว้เรื่องไม่สร้างระบบเศรษฐกิจซ้อน
    """
    from .. import seasons as SEASONS
    name = SEASONS.season_of(day)[0]
    return (K.SEASON_AMBIENT.get(name, K.DEFAULT_AMBIENT),
            K.SEASON_CLOTHING.get(name, K.DEFAULT_CLOTHING))


# ---------------------------------------------------------------- เดินเวลา
def tick(character, body, days: float, ambient: float = None, exertion: float = 0.0,
         clothing: float = 0.0, wind: float = 0.0, fed: float = 1.0) -> dict:
    """เดินพลังงานและอุณหภูมิไปตามเวลาที่ผ่านไป — แก้ตัวละครในที่

    กินพลังงานจากคลังไกลโคเจนก่อน แล้วจึงจากไขมัน (ซึ่งเฟสนี้ยังไม่ลดมวลไขมันจริง —
    การเปลี่ยนองค์ประกอบร่างกายคือการปรับตัว อยู่ใน Phase 8 และต้องเก็บส่วนต่างจาก
    พันธุกรรมไว้ต่างหาก ดู genetics.py)
    """
    if days <= 0.0:
        return {}
    used = metabolic_power(body, exertion) * days * 86400.0
    cap = glycogen_capacity(body)
    store = getattr(character, "fuel", 1.0) * cap
    from_glycogen = min(store, used)
    character.fuel = max(0.0, (store - from_glycogen) / cap) if cap > 0 else 0.0
    # กินอาหารเติมคลังกลับเข้าหาเต็มด้วยอัตราหนึ่ง เฉพาะวันที่ได้กินจริง — `fed` มาจากยุ้งฉาง
    # (tiandao/food.py) ถ้าปิดระบบอาหารอยู่ fed = 1 คือสมมติแบบเดิมว่าคนหาอะไรกินได้ตามปกติ
    character.fuel = PHYS.relax(character.fuel, 1.0, K.REFEED_RATE, days * fed)

    amb = K.DEFAULT_AMBIENT if ambient is None else ambient
    character.core_temp = step_temperature(
        body, getattr(character, "core_temp", K.CORE_TEMP_NORMAL), amb, days,
        exertion, clothing, wind)
    return {"พลังงานที่ใช้ (kJ)": round(used / 1000, 1),
            "คลังไกลโคเจนเหลือ": round(character.fuel, 4),
            "อุณหภูมิแกนกลาง (°C)": round(character.core_temp, 2),
            "สภาวะ": thermal_state(character.core_temp)}


def explain(body, cond, ambient: float = None, exertion: float = 0.0) -> dict:
    amb = K.DEFAULT_AMBIENT if ambient is None else ambient
    return {
        "อัตราเผาผลาญพื้นฐาน (W)": round(basal_rate(body), 1),
        "กำลังเผาผลาญตอนนี้ (W)": round(metabolic_power(body, exertion), 1),
        "คลังไกลโคเจนเต็ม (kJ)": round(glycogen_capacity(body) / 1000, 0),
        "พลังงานจากไขมัน (MJ)": round(fat_reserve(body) / 1e6, 1),
        "อดได้ (วัน)": round(endurance_days(body, cond, exertion), 1),
        "ออกซิเจนที่ต้องใช้ (L/นาที)": round(oxygen_demand(body, exertion), 2),
        "ระบายอากาศ (L/นาที)": round(minute_ventilation(body, exertion), 1),
        "ออกซิเจนที่ขาด": round(oxygen_debt(body, cond, exertion), 3),
        "ความจุความร้อน (kJ/K)": round(heat_capacity(body) / 1000, 1),
        "ระบายความร้อนได้ (W/K)": round(conductance(body), 2),
        "อุณหภูมิสมดุลที่อากาศ %.0f°C" % amb: round(equilibrium_temp(body, amb, exertion), 2),
        "สภาวะตอนนี้": thermal_state(cond.core_temp),
    }
