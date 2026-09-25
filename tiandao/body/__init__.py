# -*- coding: utf-8 -*-
"""ร่างกายที่เกิดจากกายวิภาค ไม่ใช่จากค่าพลังที่ตั้งขึ้นมาลอยๆ — Phase 1

    GENETICS → COMPOSITION → MUSCLE → JOINT → CAPABILITY

หลักเดียวที่ทั้งแพ็กเกจยึด: **ความสามารถต้องโผล่ออกมาจากร่างกาย ไม่ใช่ร่างกายถูกสร้าง
ให้ตรงกับความสามารถที่ตั้งไว้ก่อน** จึงไม่มี Strength/Speed/Endurance เป็นตัวเลขที่เก็บไว้
ที่ไหนเลย มีแต่มวล แรง ความยาวท่อน แล้วที่เหลือคำนวณเอา

สิ่งที่มีแล้ว (เรียงตามลำดับที่สร้าง)
--------------------------------------------------------------------------------------------
  · พารามิเตอร์ตั้งต้น 15 ตัว สุ่มแบบ deterministic จาก (seed ของโลก, cid)   genetics.py
  · องค์ประกอบมวล: กระดูก · กล้ามเนื้อ · อวัยวะ · ไขมัน (มวลรวมโผล่ออกมาเอง)  anatomy.py
  · กล้ามเนื้อสามกลุ่ม PCSA → Fmax = σ·PCSA → τ = r·F → แรงที่ปลายแขนขา      anatomy.py
  · ความเร็ววิ่ง · กระโดด · แบกหาม · เวลาตอบสนอง                            capability.py
  · จุดศูนย์กลางมวล ฐานรองรับ และการทรงตัว                                  balance.py
  · การบาดเจ็บรายส่วน การหักของกระดูก การเสียหน้าที่ และการหาย               injury.py
  · เลือด การไหลเวียน ออกซิเจน และความล้า                                   circulation.py
  · งาน พลังงาน การหายใจ และอุณหภูมิแกนกลาง                                metabolism.py
  · สิ่งที่เจ้าตัว **คิดว่า** ตัวเองเป็น ซึ่งไม่ตรงกับของจริง (§33)              perception.py
  · การปรับตัวจากการฝึกและความเสื่อมตามวัย                                  adaptation.py
  · หน้าที่สมอง หัวใจ ปอด ตับ ไต และทางเดินอาหารจากแผลเฉพาะตำแหน่ง             organs.py
  · LOD แบบ event-driven ที่ไม่ทิ้งสถานะสำคัญของคนนอกจอ                         lod.py

เรื่องเซฟและความคงที่ของโลก
--------------------------------------------------------------------------------------------
ร่างกาย **ไม่ถูกเก็บลงเซฟ** — คำนวณใหม่จาก (body_seed, cid, gender) ได้เสมอ จึงไม่ต้อง
migrate เซฟเก่า ไม่ต้องขยับ SAVE_VERSION และเซฟไม่บวม แคชเก็บไว้ในหน่วยความจำของโปรเซส
เท่านั้น (ไม่ติดไปกับ pickle ของ Sim) และไม่มีจุดใดแตะ RNG หลักของโลก
"""
from . import (adaptation, balance, capability, circulation, condition, constants,
               genetics, injury, joints, lod, metabolism, organs, pain, perception, skeleton)
from .anatomy import Body, MuscleGroup
from .skeleton import Bone, Skeleton
from .condition import Condition
from .genetics import Genetics

__all__ = ["Body", "Genetics", "MuscleGroup", "Bone", "Skeleton",
           "balance", "capability", "constants", "genetics", "skeleton",
           "body_of", "explain", "strength_of", "mass_of", "estimated_max_speed",
           "can_outrun", "can_jump", "can_lift", "carry_capacity", "reaction_time",
           "can_stand_with", "balance_margin", "fracture_risk", "BODY_POWER_WEIGHT",
           "injury", "injuries_of", "hurt", "fall", "strike_energy", "injury_summary",
           "DEFEAT_IMPACT_SCALE", "Condition", "circulation", "condition",
           "condition_of", "exert", "tick", "bleeding", "conscious",
           "metabolism", "spend", "endurance_days", "thermal_state",
           "perception", "can_stand", "can_fight", "can_run", "can_use_limb",
           "limb_function", "speed_margin", "can_escape", "felt", "felt_word",
           "capabilities", "adaptation", "organs", "pain", "lod", "train",
           "health_score", "joints"]

BODY_POWER_WEIGHT = constants.BODY_POWER_WEIGHT
DEFEAT_IMPACT_SCALE = constants.DEFEAT_IMPACT_SCALE

# แคชระดับโมดูล ไม่ใช่บน Character — Sim ถูก pickle ทั้งก้อน (ดู persist.py) แคชจึงไม่ควร
# ติดไปกับไฟล์เซฟ คีย์คือ (body_seed, cid, gender) ซึ่งเป็นทุกอย่างที่ใช้สร้างร่าง
_CACHE = {}
_CACHE_LIMIT = 8192


def body_of(character, body_seed: int = 0) -> Body:
    """ร่างกายของตัวละครหนึ่งคน — ค่าเดิมเสมอสำหรับคนเดิม

    เรียกได้บ่อยเท่าที่ต้องการ ต้นทุนครั้งแรกคือการสุ่ม 15 ค่าและคูณเลขไม่กี่สิบครั้ง
    """
    seed = int(getattr(character, "body_seed", 0) or body_seed)
    key = (seed, character.cid, getattr(character, "gender", ""))
    got = _CACHE.get(key)
    if got is None:
        if len(_CACHE) >= _CACHE_LIMIT:
            _CACHE.clear()      # โลกที่มีตัวละครมากกว่าเพดานจะสร้างใหม่เป็นรอบๆ ยอมรับได้
        got = _CACHE[key] = Body(Genetics(seed, character.cid,
                                          getattr(character, "gender", "")))
    return got


# ---------------------------------------------------------------- คำถามที่ระบบตัดสินใจถาม
# พรอมต์ §32: Decision Engine ต้องถาม "ร่างกายทำอะไรได้บ้าง" ไม่ใช่ดู HP อย่างเดียว
# ทุกฟังก์ชันด้านล่างรับตัวละครตรงๆ แล้วตอบเป็นหน่วย SI หรือค่าความจริง
# `fatigue` ยังเป็น 0 ตลอดใน Phase 1 — Phase 5 จะเป็นผู้จ่ายค่าจริงเข้ามา

def injuries_of(character) -> dict:
    """สถานะบาดเจ็บของตัวละคร — dict ว่างถ้าไม่เจ็บ (สร้างให้ถ้ายังไม่มี)"""
    state = getattr(character, "injuries", None)
    if not isinstance(state, dict):
        state = {}
        character.injuries = state
    return state


def strength_of(character, body_seed: int = 0) -> float:
    """ดัชนีพลังกายไร้หน่วยรอบ 1.0 — ตัวเดียวที่ rules.power() ใช้

    อ่านสถานะบาดเจ็บของตัวละครเองด้วย คนขาหักจึงอ่อนลงจริงโดยผู้เรียกไม่ต้องส่งอะไรเพิ่ม
    """
    return capability.strength_index(body_of(character, body_seed),
                                     Condition.of(character))


def mass_of(character, body_seed: int = 0) -> float:
    """มวลกาย (kg) ที่โผล่ออกมาจากองค์ประกอบ ไม่ได้ถูกตั้งไว้"""
    return body_of(character, body_seed).mass


def estimated_max_speed(character, friction=None, body_seed: int = 0) -> float:
    """ความเร็ววิ่งสูงสุดบนพื้นแบบหนึ่ง (m/s)"""
    mu = constants.DEFAULT_FRICTION if friction is None else friction
    return capability.max_running_speed(body_of(character, body_seed), mu,
                                        Condition.of(character))


def can_outrun(character, other, friction=None, body_seed: int = 0) -> bool:
    """วิ่งหนีคนนี้พ้นไหม — เทียบความเร็วจริงของสองร่าง ไม่ใช่เทียบค่าพลัง"""
    return (estimated_max_speed(character, friction, body_seed)
            > estimated_max_speed(other, friction, body_seed))


def can_jump(character, distance_m: float, body_seed: int = 0) -> bool:
    """ข้ามช่องกว้างเท่านี้ได้ไหม — ระยะไกลสุดที่มุมพุ่ง 45° คือ v²/g"""
    v = capability.takeoff_velocity(body_of(character, body_seed),
                                    Condition.of(character))
    return distance_m <= (v * v) / constants.GRAVITY


def can_lift(character, load_kg: float, body_seed: int = 0) -> bool:
    """ยกของหนักเท่านี้ไหวไหม — เกณฑ์คือทอร์กที่กระดูกสันหลังรับไหว"""
    return capability.can_lift(body_of(character, body_seed), load_kg,
                               Condition.of(character))


def carry_capacity(character, body_seed: int = 0) -> float:
    """มวลสูงสุดที่แบกไปได้ (kg)"""
    return capability.carry_capacity(body_of(character, body_seed),
                                     Condition.of(character))


def reaction_time(character, body_seed: int = 0) -> float:
    """เวลาตอบสนอง (s)"""
    return capability.reaction_time(body_of(character, body_seed),
                                    Condition.of(character))


def can_stand_with(character, load_kg: float, load_arm=None, body_seed: int = 0) -> bool:
    """ถือของหนักเท่านี้ไว้ข้างหน้าแล้วยังยืนอยู่ได้ไหม — เกณฑ์สมดุล ไม่ใช่เกณฑ์แรง"""
    return balance.is_stable(body_of(character, body_seed), load_kg, load_arm)


def balance_margin(character, load_kg: float = 0.0, load_arm=None,
                   body_seed: int = 0) -> float:
    """ระยะเหลือถึงขอบฐานรองรับ (m) — ลบแปลว่าล้ม"""
    return balance.balance_margin(body_of(character, body_seed), load_kg, load_arm)


def fracture_risk(character, bone: str, force: float, mode: str = "compressive",
                  body_seed: int = 0) -> float:
    """โอกาสที่กระดูกชิ้นหนึ่งจะหักเมื่อรับแรงเท่านี้ (0..1) — เส้นโค้ง ไม่ใช่เกณฑ์ตัด"""
    piece = body_of(character, body_seed).skeleton[bone]
    stress = piece.bending_stress(force) if mode == "bending" else piece.stress(force)
    stress /= Condition.of(character).bone_factor
    return piece.fracture_risk(stress, mode)


def hurt(character, energy: float, region=None, contact_area=None, rng=None,
         body_seed: int = 0, key=(), stop_distance=None) -> dict:
    """ส่งพลังงานกระทบเข้าร่างของตัวละคร — คืนบันทึกว่าเกิดอะไรขึ้นทีละชั้น

    ถ้าไม่ระบุ `region` จะเลือกให้แบบคาดเดาได้จาก `key` (ถ่วงตามพื้นที่ผิว) และถ้าไม่ส่ง
    `rng` มาจะสร้างสตรีมที่ผูกกับ `key` เอง — ทั้งสองทางไม่แตะ RNG หลักของโลก
    """
    state = injuries_of(character)
    spot = injury.pick_region(character.cid, *key) if region is None else region
    roll = injury.rng_for("fracture", character.cid, *key) if rng is None else rng
    log = injury.apply_impact(body_of(character, body_seed), state, energy, spot,
                              contact_area, roll, stop_distance,
                              Condition.of(character).bone_factor)
    _open_wound(character, log)
    return log


def fall(character, height_m: float, region=None, rng=None, body_seed: int = 0,
         key=()) -> dict:
    """ตกจากที่สูง — ใช้พื้นที่สัมผัสและระยะหยุดของการตก ไม่ใช่ของการถูกชก"""
    state = injuries_of(character)
    spot = injury.pick_region(character.cid, *key) if region is None else region
    roll = injury.rng_for("fall", character.cid, *key) if rng is None else rng
    log = injury.fall_impact(body_of(character, body_seed), state, height_m, spot, roll,
                             Condition.of(character).bone_factor)
    _open_wound(character, log)
    return log


def strike_energy(character, body_seed: int = 0) -> float:
    """พลังงานที่หมัดของคนนี้ส่งออกได้ (J) — งานที่แขนทำได้ตามกายวิภาค"""
    return injury.strike_energy(body_of(character, body_seed), Condition.of(character))


def injury_summary(character, body_seed: int = 0) -> dict:
    """สรุปบาดเจ็บและความสามารถที่เหลือ"""
    return injury.explain(body_of(character, body_seed),
                          getattr(character, "injuries", None))


def condition_of(character) -> Condition:
    """สภาพร่างกายตอนนี้ — ความล้า เลือด บาดเจ็บ รวมเป็นวัตถุเดียว"""
    return Condition.of(character)


def exert(character, work: float = 1.0) -> float:
    """สะสมความล้าจากงานที่เพิ่งทำ — คืนระดับความล้าใหม่ (§8)"""
    adaptation.stimulate(character, work)
    body = body_of(character)
    debt = metabolism.oxygen_debt(body, Condition.of(character), min(1.0, max(0.0, work)))
    return circulation.exert(character, work * (1.0 + constants.OXYGEN_DEBT_FATIGUE_GAIN * debt))


def train(character, work: float = 1.0) -> float:
    """ฝึกร่างโดยตั้งแรงกระตุ้นไว้ก่อน ผลจริงเกิดระหว่างพักใน tick()"""
    adaptation.stimulate(character, work)
    return max(0.0, float(work))


def tick(character, days: float, body_seed: int = 0, day: int = None,
         exertion: float = 0.0, lod_level=None) -> dict:
    """เดินสภาพร่างกายไปตามเวลาที่ผ่านไป — จุดเดียวที่ผู้เรียกต้องรู้จัก

    เลือดออก · สร้างเลือดใหม่ · คลายความล้า · แผลสมาน ทั้งหมดในครั้งเดียว
    ทุกอย่างอินทิเกรตเป็นรูปแบบปิดข้ามช่วงเวลา จึงเรียกครั้งเดียวต่อหนึ่ง gap ได้เลย
    ไม่ต้องแบ่งเป็นก้าวเล็กๆ และผลไม่ขึ้นกับว่าแบ่งละเอียดแค่ไหน

    ลำดับสำคัญ: เลือดออกใช้สภาพของแผล **ก่อน** แผลจะสมาน ไม่งั้นแผลที่หายแล้ว
    จะยังไม่เคยทำให้เสียเลือดเลยสักหยด
    """
    chosen_lod = lod.level(character) if lod_level is None else int(lod_level)
    body = body_of(character, body_seed)
    log = circulation.tick(character, body, days)
    ambient, clothing = (metabolism.climate_of(day) if day is not None
                         else (None, None))
    log.update(metabolism.tick(character, body, days, ambient, exertion,
                               constants.DEFAULT_CLOTHING if clothing is None else clothing))
    state = getattr(character, "injuries", None)
    if state:
        cond = Condition.of(character)
        injury.heal(state, days, cond.recovery_factor * organs.recovery_factor(state))
    adaptation.tick(character, days)
    log["LOD"] = lod.NAMES.get(chosen_lod, "custom")
    return log


def bleeding(character) -> float:
    """อัตราการเสียเลือดตอนนี้ เป็นสัดส่วนของปริมาตรปกติต่อวัน (§18)"""
    return circulation.bleed_rate(character)


def _open_wound(character, log) -> None:
    """แผลที่เพิ่งเกิดเริ่มไหลเลือด — ต่อจากหลอดเลือดที่ apply_impact รายงานว่าฉีก"""
    torn = log.get("หลอดเลือดฉีก")
    if torn:
        circulation.open_wound(character, torn)


def spend(character, work_joules: float, body_seed: int = 0) -> float:
    """จ่ายพลังงานสำหรับงานกลที่เพิ่งทำ — คืนสัดส่วนคลังที่เหลือ (§21–22)"""
    body = body_of(character, body_seed)
    cap = metabolism.glycogen_capacity(body)
    if cap <= 0.0:
        return 1.0
    cost = metabolism.metabolic_cost(work_joules)
    character.fuel = max(0.0, getattr(character, "fuel", 1.0) - cost / cap)
    return character.fuel


def endurance_days(character, body_seed: int = 0, exertion: float = 0.0) -> float:
    """อดได้อีกกี่วันก่อนเชื้อเพลิงหมด — ไขมันในตัวคือคลังหลัก"""
    return metabolism.endurance_days(body_of(character, body_seed),
                                     Condition.of(character), exertion)


def thermal_state(character) -> str:
    """สภาวะความร้อนของร่างตอนนี้เป็นคำ"""
    return metabolism.thermal_state(getattr(character, "core_temp",
                                            constants.CORE_TEMP_NORMAL))


def conscious(character) -> bool:
    """ยังรู้สึกตัวอยู่ไหม — เลือดต่ำกว่าระดับหนึ่งสมองไม่ได้ออกซิเจนพอ"""
    return Condition.of(character).conscious


def health_score(character, cond=None) -> float:
    """สรุปสุขภาพ 0..1 สำหรับ compatibility/UI; Anatomy State ยังเป็น source of truth"""
    c = Condition.of(character) if cond is None else condition.resolve(cond)
    vital = organs.functions(c.injury)
    mobility = min(injury.region_function(c.injury, "left_leg"),
                   injury.region_function(c.injury, "right_leg"))
    # geometric mean ทำให้คอขวดสำคัญจริง และไม่มีองค์ประกอบใดถูกกลบด้วยการบวกคะแนน
    terms = (max(0.001, c.blood), max(0.001, vital["brain"]),
             max(0.001, vital["heart"]), max(0.001, vital["lungs"]),
             max(0.001, mobility), max(0.001, 1.0 - injury.severity(c.injury)))
    import math
    return max(0.0, min(1.0, math.exp(sum(math.log(x) for x in terms) / len(terms))))


# ---------------------------------------------------------------- §32 คำถามปิด + §33 ที่รู้สึก
# ระบบตัดสินใจถามร่างกายก่อนตัดสินใจ ไม่ใช่ดู HP อย่างเดียว (พรอมต์ §32) ทุกฟังก์ชันด้านล่าง
# รับ `cond` ได้ ถ้าไม่ส่งมาจะใช้สภาพ **จริง** ของตัวละคร ส่วนใจของตัวละครควรส่งสภาพ
# **ที่รู้สึก** (ดู felt()) เข้ามาแทน — สมการเดียวกัน ป้อนสภาพคนละอัน

def can_stand(character, cond=None, body_seed: int = 0) -> bool:
    """ยังยืนด้วยลำแข้งตัวเองได้ไหม"""
    return capability.can_stand(body_of(character, body_seed),
                                Condition.of(character) if cond is None else cond)


def can_fight(character, cond=None, body_seed: int = 0) -> bool:
    """ยังสู้ไหวไหม — ไม่ใช่ "HP เหลือเท่าไร" แต่คือยังออกหมัดที่มีน้ำหนักได้ไหม"""
    return capability.can_fight(body_of(character, body_seed),
                                Condition.of(character) if cond is None else cond)


def limb_function(character, region: str, cond=None) -> float:
    """หน้าที่ที่เหลือของแขนหรือขาข้างหนึ่ง 0..1 (§32 CanUseLeftArm)"""
    c = Condition.of(character) if cond is None else cond
    return injury.region_function(c.injury, region)


def can_use_limb(character, region: str, cond=None) -> bool:
    """ใช้แขน/ขาข้างนี้ได้ไหม — ข้างที่หักยังคงหักแม้อีกข้างจะสมบูรณ์"""
    return limb_function(character, region, cond) >= constants.LIMB_USABLE_MIN


def can_run(character, cond=None, body_seed: int = 0) -> bool:
    """วิ่งได้ไหม — ต้องยืนไหวและขาใช้การได้ **ทั้งสองข้าง** (ขาเดียวได้แค่กระเผลก)"""
    return capability.can_run(body_of(character, body_seed),
                              Condition.of(character) if cond is None else cond)


def speed_margin(character, other, friction=None, cond=None, body_seed: int = 0) -> float:
    """ความเร็วของเราลบความเร็วของอีกฝ่าย (m/s) — บวกแปลว่าไล่ไม่ทัน

    เป็นปริมาณทางฟิสิกส์ล้วน ส่วนโอกาสหนีรอดเป็นเรื่องของใจที่ไม่รู้ความเร็วจริงของ
    ผู้ไล่ จึงอยู่ในระบบตัดสินใจ (decision/scoring.py) ไม่ใช่ที่นี่
    """
    mu = constants.DEFAULT_FRICTION if friction is None else friction
    mine = capability.max_running_speed(
        body_of(character, body_seed), mu,
        Condition.of(character) if cond is None else cond)
    return mine - estimated_max_speed(other, mu, body_seed)


def can_escape(character, pursuers, friction=None, cond=None, body_seed: int = 0) -> bool:
    """หนีพ้นไหม — เร็วกว่าผู้ไล่ทุกคน ถ้าช้ากว่าแม้คนเดียวก็ถูกไล่ทันในที่สุด

    ไม่มีระยะนำหน้าเข้ามาเกี่ยว เพราะระยะนำหน้าแค่ยืดเวลา: ตราบใดที่ Δv ติดลบ
    เวลาที่ถูกไล่ทันคือ d/|Δv| ซึ่งเป็นจำนวนจำกัดเสมอ
    """
    if not pursuers:
        return True
    return all(speed_margin(character, p, friction, cond, body_seed) > 0.0
               for p in pursuers)


def felt(character, day: float = 0.0, bias: float = 0.0) -> Condition:
    """สภาพร่างกาย **ตามที่เจ้าตัวรู้สึก** (§33) — ใจใช้ตัวนี้ ฟิสิกส์ใช้ของจริง"""
    return perception.perceive(character, day, bias)


def felt_word(character, day: float = 0.0, bias: float = 0.0) -> str:
    """สิ่งที่ตัวละครจะตอบถ้ามีคนถามว่าเป็นอย่างไรบ้าง"""
    return perception.describe(felt(character, day, bias))


def capabilities(character, cond=None, felt=None, friction=None,
                 body_seed: int = 0) -> dict:
    """คำตอบทุกข้อที่ระบบตัดสินใจถาม รวบมาในครั้งเดียว (§32)

    รวบไว้ที่เดียวเพราะผู้เรียกฝั่งตัดสินใจถามทีเดียวทุกข้อ และเพราะการสร้าง `Body`
    กับอ่านสภาพควรเกิดครั้งเดียวต่อการตัดสินใจหนึ่งครั้ง ไม่ใช่ครั้งละคำถาม

    **สองสภาพ สองหน้าที่** (§33) ถ้าส่ง `felt` มา:
      · ปริมาณที่ต้อง *ประเมิน* (ความเร็ว · หมัด · แรงที่เหลือ · ความหนักของแผล) ใช้ `felt`
      · ข้อเท็จจริงที่เจ้าตัว *รู้ได้ทันที* (ยังรู้สึกตัวไหม · ยืนอยู่ไหม) ใช้สภาพจริง
    เพราะคนที่ยังยืนอยู่ไม่ได้ "เดา" ว่าตัวเองยืนอยู่ — เขารู้ ส่วนความเร็วที่เหลือนั้นเดา
    ถ้าไม่ส่ง `felt` ทุกข้อคิดจากสภาพเดียวกันหมด (ค่าปริยาย = สภาพจริงของตัวละคร)
    """
    body = body_of(character, body_seed)
    mu = constants.DEFAULT_FRICTION if friction is None else friction
    real = Condition.of(character) if cond is None else cond
    mind = real if felt is None else felt
    stand = capability.can_stand(body, real)        # ยืนอยู่ไหม — ข้อเท็จจริง ไม่ใช่การเดา
    return {
        "speed": capability.max_running_speed(body, mu, mind),
        "reaction": capability.reaction_time(body, mind),
        "carry": capability.carry_capacity(body, mind),
        "strike": injury.strike_energy(body, mind),
        "fight": capability.fight_capacity(body, mind),
        "effort": mind.effort_factor,
        "arm": min(injury.region_function(mind.injury, "left_arm"),
                   injury.region_function(mind.injury, "right_arm")),
        "leg": min(injury.region_function(mind.injury, "left_leg"),
                   injury.region_function(mind.injury, "right_leg")),
        "severity": injury.severity(mind.injury),
        "pain": pain.level(mind.injury),
        "can_stand": stand,
        "can_fight": capability.can_fight(body, mind, standing=stand),
        "can_run": capability.can_run(body, mind, standing=stand),
        "conscious": real.conscious,
        "endurance": metabolism.endurance_days(body, mind),
        "word": perception.describe(mind),
    }


def explain(character, body_seed: int = 0, friction=None,
            load_kg: float = 0.0) -> dict:
    """คำอธิบายร่างกายทั้งก้อนสำหรับดีบัก — ทุกตัวเลขย้อนไปหาที่มาได้ (พรอมต์ §44)"""
    body = body_of(character, body_seed)
    mu = constants.DEFAULT_FRICTION if friction is None else friction
    state = getattr(character, "injuries", None)
    cond = Condition.of(character)
    return {
        "ตัวละคร": getattr(character, "name", f"cid {character.cid}"),
        "กายวิภาค": body.explain(),
        "ความสามารถ": capability.summary(body, mu, cond),
        "การทรงตัว": balance.explain(body, load_kg),
        "บาดเจ็บ": injury.explain(body, state),
        "ไหลเวียนและเลือด": circulation.explain(body, cond, character=character),
        "พลังงานและความร้อน": metabolism.explain(body, cond),
        "สิ่งที่ระบบตัดสินใจถาม": capabilities(character, cond=cond, friction=mu),
        "ที่รู้สึกเทียบกับของจริง": perception.explain(character),
        "การปรับตัวและวัย": adaptation.explain(character),
        "อวัยวะสำคัญ": organs.explain(state),
        "สุขภาพสรุป (derived)": round(health_score(character, cond), 3),
        "ข้อต่อ": {j: joints.state(body, j, cond).__dict__
                    for j in ("shoulder", "elbow", "wrist", "hip", "knee", "ankle", "spine")},
    }
