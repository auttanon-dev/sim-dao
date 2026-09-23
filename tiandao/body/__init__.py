# -*- coding: utf-8 -*-
"""ร่างกายที่เกิดจากกายวิภาค ไม่ใช่จากค่าพลังที่ตั้งขึ้นมาลอยๆ — Phase 1

    GENETICS → COMPOSITION → MUSCLE → JOINT → CAPABILITY

หลักเดียวที่ทั้งแพ็กเกจยึด: **ความสามารถต้องโผล่ออกมาจากร่างกาย ไม่ใช่ร่างกายถูกสร้าง
ให้ตรงกับความสามารถที่ตั้งไว้ก่อน** จึงไม่มี Strength/Speed/Endurance เป็นตัวเลขที่เก็บไว้
ที่ไหนเลย มีแต่มวล แรง ความยาวท่อน แล้วที่เหลือคำนวณเอา

สิ่งที่ Phase 1 ครอบคลุม
--------------------------------------------------------------------------------------------
  · พารามิเตอร์ตั้งต้น 15 ตัว สุ่มแบบ deterministic จาก (seed ของโลก, cid)
  · องค์ประกอบมวล: กระดูก · กล้ามเนื้อ · อวัยวะ · ไขมัน (มวลรวมโผล่ออกมาเอง)
  · กล้ามเนื้อสามกลุ่ม: PCSA → Fmax = σ·PCSA → แรงที่ใช้ได้จริง
  · ข้อต่อห้าข้อ: τ = r·F
  · ความสามารถ: ความเร็ววิ่ง · กระโดด · แบกหาม · เวลาตอบสนอง

สิ่งที่ยัง **ไม่** ครอบคลุม (เฟสถัดไป — ห้ามอ่านว่ามีแล้ว)
  · ความล้า การหายใจ ไหลเวียนเลือด พลังงาน อุณหภูมิ  (Phase 5–6)
  · การบาดเจ็บเฉพาะส่วนและการสูญเสียหน้าที่          (Phase 4)
  · จุดศูนย์กลางมวลและการทรงตัว                      (Phase 3)
พารามิเตอร์ `fatigue` มีอยู่ในทุกสูตรแล้วและเป็น 0 เสมอในเฟสนี้ เพื่อให้เฟสหลังเสียบค่าจริง
เข้ามาได้โดยไม่ต้องแก้ผู้เรียก

เรื่องเซฟและความคงที่ของโลก
--------------------------------------------------------------------------------------------
ร่างกาย **ไม่ถูกเก็บลงเซฟ** — คำนวณใหม่จาก (body_seed, cid, gender) ได้เสมอ จึงไม่ต้อง
migrate เซฟเก่า ไม่ต้องขยับ SAVE_VERSION และเซฟไม่บวม แคชเก็บไว้ในหน่วยความจำของโปรเซส
เท่านั้น (ไม่ติดไปกับ pickle ของ Sim) และไม่มีจุดใดแตะ RNG หลักของโลก
"""
from . import balance, capability, constants, genetics, injury, skeleton
from .anatomy import Body, MuscleGroup
from .skeleton import Bone, Skeleton
from .genetics import Genetics

__all__ = ["Body", "Genetics", "MuscleGroup", "Bone", "Skeleton",
           "balance", "capability", "constants", "genetics", "skeleton",
           "body_of", "explain", "strength_of", "mass_of", "estimated_max_speed",
           "can_outrun", "can_jump", "can_lift", "carry_capacity", "reaction_time",
           "can_stand_with", "balance_margin", "fracture_risk", "BODY_POWER_WEIGHT",
           "injury", "injuries_of", "hurt", "fall", "strike_energy", "injury_summary",
           "DEFEAT_IMPACT_SCALE"]

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


def strength_of(character, body_seed: int = 0, fatigue: float = 0.0) -> float:
    """ดัชนีพลังกายไร้หน่วยรอบ 1.0 — ตัวเดียวที่ rules.power() ใช้

    อ่านสถานะบาดเจ็บของตัวละครเองด้วย คนขาหักจึงอ่อนลงจริงโดยผู้เรียกไม่ต้องส่งอะไรเพิ่ม
    """
    return capability.strength_index(body_of(character, body_seed), fatigue,
                                     getattr(character, "injuries", None))


def mass_of(character, body_seed: int = 0) -> float:
    """มวลกาย (kg) ที่โผล่ออกมาจากองค์ประกอบ ไม่ได้ถูกตั้งไว้"""
    return body_of(character, body_seed).mass


def estimated_max_speed(character, friction=None, body_seed: int = 0,
                        fatigue: float = 0.0) -> float:
    """ความเร็ววิ่งสูงสุดบนพื้นแบบหนึ่ง (m/s)"""
    mu = constants.DEFAULT_FRICTION if friction is None else friction
    return capability.max_running_speed(body_of(character, body_seed), mu, fatigue,
                                        getattr(character, "injuries", None))


def can_outrun(character, other, friction=None, body_seed: int = 0,
               fatigue: float = 0.0, other_fatigue: float = 0.0) -> bool:
    """วิ่งหนีคนนี้พ้นไหม — เทียบความเร็วจริงของสองร่าง ไม่ใช่เทียบค่าพลัง"""
    return (estimated_max_speed(character, friction, body_seed, fatigue)
            > estimated_max_speed(other, friction, body_seed, other_fatigue))


def can_jump(character, distance_m: float, body_seed: int = 0,
             fatigue: float = 0.0) -> bool:
    """ข้ามช่องกว้างเท่านี้ได้ไหม — ระยะไกลสุดที่มุมพุ่ง 45° คือ v²/g"""
    v = capability.takeoff_velocity(body_of(character, body_seed), fatigue,
                                    getattr(character, "injuries", None))
    return distance_m <= (v * v) / constants.GRAVITY


def can_lift(character, load_kg: float, body_seed: int = 0, fatigue: float = 0.0) -> bool:
    """ยกของหนักเท่านี้ไหวไหม — เกณฑ์คือทอร์กที่กระดูกสันหลังรับไหว"""
    return capability.can_lift(body_of(character, body_seed), load_kg, fatigue,
                               getattr(character, "injuries", None))


def carry_capacity(character, body_seed: int = 0, fatigue: float = 0.0) -> float:
    """มวลสูงสุดที่แบกไปได้ (kg)"""
    return capability.carry_capacity(body_of(character, body_seed), fatigue,
                                     getattr(character, "injuries", None))


def reaction_time(character, body_seed: int = 0, fatigue: float = 0.0) -> float:
    """เวลาตอบสนอง (s)"""
    return capability.reaction_time(body_of(character, body_seed), fatigue,
                                    getattr(character, "injuries", None))


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
    return injury.apply_impact(body_of(character, body_seed), state, energy, spot,
                               contact_area, roll, stop_distance)


def fall(character, height_m: float, region=None, rng=None, body_seed: int = 0,
         key=()) -> dict:
    """ตกจากที่สูง — ใช้พื้นที่สัมผัสและระยะหยุดของการตก ไม่ใช่ของการถูกชก"""
    state = injuries_of(character)
    spot = injury.pick_region(character.cid, *key) if region is None else region
    roll = injury.rng_for("fall", character.cid, *key) if rng is None else rng
    return injury.fall_impact(body_of(character, body_seed), state, height_m, spot, roll)


def strike_energy(character, body_seed: int = 0, fatigue: float = 0.0) -> float:
    """พลังงานที่หมัดของคนนี้ส่งออกได้ (J) — งานที่แขนทำได้ตามกายวิภาค"""
    return injury.strike_energy(body_of(character, body_seed), fatigue,
                                getattr(character, "injuries", None))


def injury_summary(character, body_seed: int = 0) -> dict:
    """สรุปบาดเจ็บและความสามารถที่เหลือ"""
    return injury.explain(body_of(character, body_seed),
                          getattr(character, "injuries", None))


def explain(character, body_seed: int = 0, friction=None, fatigue: float = 0.0,
            load_kg: float = 0.0) -> dict:
    """คำอธิบายร่างกายทั้งก้อนสำหรับดีบัก — ทุกตัวเลขย้อนไปหาที่มาได้ (พรอมต์ §44)"""
    body = body_of(character, body_seed)
    mu = constants.DEFAULT_FRICTION if friction is None else friction
    state = getattr(character, "injuries", None)
    return {
        "ตัวละคร": getattr(character, "name", f"cid {character.cid}"),
        "กายวิภาค": body.explain(),
        "ความสามารถ": capability.summary(body, mu, fatigue, state),
        "การทรงตัว": balance.explain(body, load_kg),
        "บาดเจ็บ": injury.explain(body, state),
    }
