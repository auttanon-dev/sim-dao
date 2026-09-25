# -*- coding: utf-8 -*-
"""การบาดเจ็บเฉพาะส่วน — พลังงานผ่านชั้นเนื้อเยื่อ แล้วเสียหน้าที่ตามส่วนที่โดน (§26–28)

ต่างจากทุกอย่างก่อนหน้านี้อย่างไร
--------------------------------------------------------------------------------------------
กายวิภาคกับโครงกระดูก *คำนวณกลับมาได้เสมอ* จาก (seed, cid) แต่บาดเจ็บคือ **ประวัติศาสตร์**
ของร่างนั้น อนุมานย้อนหลังไม่ได้ จึงเป็นส่วนแรกของระบบร่างกายที่ต้องเก็บลงเซฟจริง
เก็บเป็น dict ที่ว่างเปล่าสำหรับคนที่ไม่เจ็บ — ต้นทุนในเซฟจึงแทบเป็นศูนย์จนกว่าจะมีคนเจ็บจริง

โซ่ของการบาดเจ็บ
--------------------------------------------------------------------------------------------
    พลังงานกระทบ  ->  ชั้นเนื้อเยื่อดูดซับทีละชั้น  ->  ที่เหลือแปลงเป็นแรงที่กระดูก
                  ->  ความเค้น/โอกาสหัก (Phase 2)   ->  เสียหน้าที่เฉพาะส่วน

      E = ½·m_eff·v²        (การกระแทก · §26)
      E = F·d               (การชก — งานที่แขนทำได้ตามที่กายวิภาคให้)
      E = m·g·h             (การตก)
      E_ถัดไป = E − E_ดูดซับ  (§26 — ชั้นที่ดูดไม่ไหวจึงส่งต่อ)
      E_ดูดซับ = min(E × สัดส่วนที่ดูดได้, เพดานของชั้นนั้น)
      F = E/d_หยุด           (งาน-พลังงาน: พลังงานที่เหลือถูกหยุดในระยะสั้นๆ)
                            d_หยุด ต่างกันตามเหตุการณ์ — หมัด 3 ซม. ตกทั้งตัว 20 ซม.

**ความอ้วนช่วยดูดพลังงาน** ชั้นไขมันหนากว่าเก็บพลังงานได้มากกว่าก่อนถึงกระดูก ซึ่งเป็นเรื่องจริง
และโผล่ออกมาจากองค์ประกอบร่างกายเอง ไม่ได้เขียนเป็นกฎ — คนอ้วนวิ่งช้ากว่าแต่ทนถูกตีมากกว่า

ข้อจำกัด (พรอมต์ §41)
--------------------------------------------------------------------------------------------
ความหนาของชั้นเนื้อเยื่อประมาณจากมวลองค์ประกอบหารพื้นที่ผิว ไม่ใช่การวัดจริงรายจุด
ค่าความเหนียวของเนื้อเยื่อเป็นพลังงานต่อปริมาตรระดับคร่าวๆ ที่ปรับให้ผลลัพธ์อยู่ในช่วงที่
สมเหตุสมผล (ชกหนักทำให้ฟกช้ำ ตกจากที่สูงทำให้กระดูกหัก) ไม่ใช่ค่าจากวรรณกรรมทางคลินิก
ไม่มีเส้นประสาท เส้นเลือดรายเส้น หรือการติดเชื้อ — เลือดออกอยู่ใน Phase 5
"""
import hashlib
import math

from .. import physics as PHYS
from . import constants as K

# ---------------------------------------------------------------- ส่วนของร่างและชั้นเนื้อเยื่อ
REGIONS = ("head", "chest", "abdomen", "left_arm", "right_arm", "left_leg", "right_leg")

# ชั้นเนื้อเยื่อเรียงจากนอกเข้าใน (พรอมต์ §26) — กระดูกกับอวัยวะจัดการแยกเพราะใช้กลไกคนละแบบ
SOFT_LAYERS = ("skin", "fat", "muscle")

# ส่วนไหนมีอวัยวะสำคัญอยู่ข้างใน และกระดูกชิ้นไหนคุ้มส่วนนั้น
REGION_BONE = {
    "head": "skull", "chest": "ribcage", "abdomen": "spine",
    "left_arm": "humerus", "right_arm": "humerus",
    "left_leg": "femur", "right_leg": "femur",
}
REGION_HAS_ORGAN = {"head", "chest", "abdomen"}

# ส่วนแบ่งมวลกล้ามเนื้อและพื้นที่ผิวของแต่ละส่วน — ใช้ประมาณความหนาของชั้น
REGION_MUSCLE_GROUP = {
    "head": "trunk", "chest": "trunk", "abdomen": "trunk",
    "left_arm": "arm", "right_arm": "arm", "left_leg": "leg", "right_leg": "leg",
}
REGION_SURFACE_SHARE = {
    "head": 0.07, "chest": 0.18, "abdomen": 0.13,
    "left_arm": 0.09, "right_arm": 0.09, "left_leg": 0.22, "right_leg": 0.22,
}


def surface_area(body) -> float:
    """พื้นที่ผิวกาย (m²) — สูตร Du Bois ซึ่งเป็นความสัมพันธ์เชิงประจักษ์

        A = 0.007184 · m^0.425 · h^0.725       (m ใน kg, h ใน cm)
    """
    return 0.007184 * (body.mass ** 0.425) * ((body.gen.height * 100.0) ** 0.725)


def layer_thickness(body, region: str) -> dict:
    """ความหนาของแต่ละชั้นในส่วนนั้น (m) — มาจากมวลองค์ประกอบหารพื้นที่ผิว

    ไม่ได้ตั้งไว้: คนที่ไขมันมากได้ชั้นไขมันหนากว่าโดยอัตโนมัติ และคนที่กล้ามเนื้อขาใหญ่
    ได้ชั้นกล้ามเนื้อที่ขาหนากว่า
    """
    area = surface_area(body) * REGION_SURFACE_SHARE[region]
    if area <= 0.0:
        return {name: 0.0 for name in SOFT_LAYERS}
    fat_here = body.fat_mass * REGION_SURFACE_SHARE[region]
    muscle_here = (body.muscles[REGION_MUSCLE_GROUP[region]].mass
                   * REGION_SURFACE_SHARE[region] / _GROUP_SURFACE[REGION_MUSCLE_GROUP[region]])
    return {
        "skin": K.SKIN_THICKNESS,
        "fat": fat_here / (K.FAT_DENSITY * area),
        "muscle": muscle_here / (K.MUSCLE_DENSITY * area),
    }


# พื้นที่ผิวรวมของทุกส่วนที่ใช้กล้ามเนื้อกลุ่มเดียวกัน — ใช้หารให้มวลกลุ่มกระจายถูก
_GROUP_SURFACE = {}
for _r, _g in REGION_MUSCLE_GROUP.items():
    _GROUP_SURFACE[_g] = _GROUP_SURFACE.get(_g, 0.0) + REGION_SURFACE_SHARE[_r]


# ---------------------------------------------------------------- พลังงานของการกระทบ
def kinetic_energy(mass: float, velocity: float) -> float:
    """E = ½·m·v²  (พรอมต์ §26) — ความเร็วสองเท่าให้พลังงานสี่เท่า"""
    return 0.5 * mass * velocity * velocity


def fall_energy(body, height_m: float) -> float:
    """พลังงานจากการตก E = m·g·h"""
    return body.mass * K.GRAVITY * max(0.0, height_m)


def fall_impact(body, state, height_m: float, region: str, rng=None,
                bone_factor: float = 1.0) -> dict:
    """ตกจากที่สูงลงส่วนหนึ่งของร่าง — ใช้พื้นที่สัมผัสและระยะหยุดของการตกให้ถูกต้อง

    มีไว้เพื่อให้ผู้เรียกไม่ต้องจำว่าการตกต่างจากการถูกชกตรงไหน (พื้นที่กว้างกว่าสิบเท่า
    และระยะหยุดยาวกว่าเกือบเจ็ดเท่า) การใส่ค่าของการชกให้การตกคือสิ่งที่ทำให้ตกหนึ่งเมตร
    แล้วกระดูกหัก
    """
    return apply_impact(body, state, fall_energy(body, height_m), region,
                        K.CONTACT_AREA_FALL, rng, K.FALL_STOP_DISTANCE, bone_factor)


def strike_energy(body, cond=None) -> float:
    """พลังงานที่หมัดของร่างนี้ส่งออกได้ (J) — งานที่แขนทำได้ ไม่ใช่ค่าที่ตั้งไว้

        E = F_ปลายแขน × ระยะชก        (งาน-พลังงาน)

    ร่างอ้างอิงได้ราว 200 J ซึ่งอยู่ในช่วงที่วัดกันจริงของหมัดคนที่ฝึกมา (ราว 100–300 J)
    พลังนี้ไม่ได้มาจากค่า Strength — มาจาก PCSA ของแขน แขนโมเมนต์ และความยาวท่อน
    """
    force = body.endpoint_force("arm", cond)
    return force * body.gen.arm_length * K.STRIKE_STROKE_RATIO


# ---------------------------------------------------------------- สถานะบาดเจ็บ
def _blank_region(region: str) -> dict:
    out = {name: 0.0 for name in SOFT_LAYERS}
    out["bone"] = 0.0
    if region in REGION_HAS_ORGAN:
        out["organ"] = 0.0
    return out


def damage_of(state, region: str, tissue: str) -> float:
    """ความเสียหายของเนื้อเยื่อหนึ่งในส่วนหนึ่ง 0..1 — ไม่มีข้อมูล = ไม่เจ็บ"""
    if not state:
        return 0.0
    return float(state.get(region, {}).get(tissue, 0.0))


def worst(state) -> tuple:
    """ส่วนที่เจ็บหนักที่สุด — คืน (ชื่อส่วน, ระดับ 0..1) หรือ (None, 0.0) ถ้าไม่เจ็บเลย"""
    if not state:
        return None, 0.0
    best = (0.0, None)
    for region, tissues in state.items():
        level = max(tissues.values()) if tissues else 0.0
        if level > best[0]:
            best = (level, region)
    return best[1], best[0]


def severity(state) -> float:
    """ความบาดเจ็บรวมทั้งร่าง 0..1 — ถ่วงตามความสำคัญของเนื้อเยื่อ"""
    if not state:
        return 0.0
    total = 0.0
    for region, tissues in state.items():
        for tissue, level in tissues.items():
            total += level * K.TISSUE_SEVERITY.get(tissue, 0.5)
    return min(1.0, total / len(REGIONS))


# ---------------------------------------------------------------- การกระทบจริง
def apply_impact(body, state, energy: float, region: str, contact_area: float = None,
                 rng=None, stop_distance: float = None, bone_factor: float = 1.0) -> dict:
    """ส่งพลังงานเข้าไปในส่วนหนึ่งของร่าง — แก้ `state` แล้วคืนบันทึกว่าเกิดอะไรขึ้น

    ชั้นนอกดูดซับก่อน เหลือเท่าไรส่งต่อชั้นใน (พรอมต์ §26) พลังงานที่ทะลุถึงกระดูกถูกแปลง
    เป็นแรงด้วยงาน-พลังงาน (F = E/d) แล้วส่งให้กลไกความเค้น/โอกาสหักของ Phase 2 ตัดสิน

    `rng` ใช้เฉพาะตัดสินว่ากระดูกหักจริงไหม (โอกาสจาก fracture_risk) ถ้าไม่ส่งมาจะ
    คืนค่าโอกาสไว้ในบันทึกโดยไม่ตัดสิน — ผู้เรียกจึงคุมสตรีมสุ่มได้เองทั้งหมด
    """
    if region not in REGION_BONE:
        raise ValueError(f"ไม่รู้จักส่วนของร่าง: {region}")
    area = K.CONTACT_AREA_FIST if contact_area is None else contact_area
    stop = K.IMPACT_STOP_DISTANCE if stop_distance is None else stop_distance
    # heal() ลบคีย์ที่หายสนิทออกไปเพื่อไม่ให้เซฟแบกเศษไว้ ส่วนที่เคยเจ็บแล้วหายแล้วจึงมี
    # คีย์ไม่ครบ — ทุกการอ่านด้านล่างต้องทนสภาพนั้นได้ (เจอจริงเป็น KeyError ตอนโดนซ้ำที่เดิม)
    here = state.setdefault(region, _blank_region(region))
    thick = layer_thickness(body, region)
    log = {"ส่วน": region, "พลังงานเข้า (J)": round(energy, 1), "ชั้นที่ดูดซับ": {}}

    left = max(0.0, energy)
    torn = 0.0          # ความเสียหายที่จะกลายเป็นหลอดเลือดฉีก (สะสมระหว่างทาง)
    for name in SOFT_LAYERS:
        volume = thick[name] * area
        if volume <= 0.0:
            continue
        # ดูดได้แค่เศษส่วนหนึ่งของที่ไหลเข้า และไม่เกินเพดานของชั้นตัวเอง
        # เนื้อเยื่ออ่อนไม่ใช่ตัวดูดซับที่ดี ส่วนที่เหลือทะลุผ่านไปหากระดูกเสมอ
        absorbed = min(left * K.ABSORB_FRACTION[name], K.TISSUE_TOUGHNESS[name] * volume)
        left -= absorbed
        # ความเสียหายเทียบกับ *พลังงานที่ทำให้หมดสภาพ* ซึ่งใหญ่กว่าเพดานการดูดซับมาก
        destroy = K.DESTROY_DENSITY[name] * volume
        if destroy > 0.0:
            added = absorbed / destroy
            here[name] = min(1.0, here.get(name, 0.0) + added)
            if name == "muscle":
                torn += added        # หลอดเลือดเดินอยู่ในกล้ามเนื้อ ฉีกไปพร้อมกัน
        log["ชั้นที่ดูดซับ"][name] = {
            "ความหนา (mm)": round(thick[name] * 1000, 1),
            "ดูดซับ (J)": round(absorbed, 1),
            "ความเสียหายรวม": round(here[name], 3),
        }

    log["พลังงานถึงกระดูก (J)"] = round(left, 1)
    bone_before = here.get("bone", 0.0)
    if left <= 0.0:
        if torn > 0.0:
            here["vessel"] = min(1.0, here.get("vessel", 0.0) + torn * K.VESSEL_TEAR_SHARE)
            log["หลอดเลือดฉีก"] = round(here["vessel"], 3)
        return log

    # ---- พลังงานที่เหลือแปลงเป็นแรง แล้วให้กลไกกระดูกของ Phase 2 ตัดสิน ----
    bone = body.skeleton[REGION_BONE[region]]
    force = left / stop
    # กระดูกวัยเด็ก/วัยชราและกระดูกที่ปรับตัวจากแรงกดมีความทนไม่เท่ากัน การหาร stress
    # ด้วยตัวคูณเทียบเท่ากับปรับเกณฑ์ความแข็งแรง โดยไม่แก้ Skeleton ตั้งต้นที่สร้างจาก seed
    stress = bone.bending_stress(force) / max(0.05, bone_factor)
    risk = bone.fracture_risk(stress, "bending")
    log["แรงที่กระดูก (N)"] = round(force)
    log["ความเค้นจากการดัด (MPa)"] = round(stress / 1e6, 1)
    log["โอกาสหัก"] = round(risk, 4)
    if rng is not None and rng.random() < risk:
        here["bone"] = min(1.0, here.get("bone", 0.0) + K.FRACTURE_DAMAGE)
        log["กระดูกหัก"] = True
    else:
        # ไม่หักก็ยังบอบช้ำตามสัดส่วนความเค้นที่รับไป
        here["bone"] = min(1.0, here.get("bone", 0.0) + risk * K.BONE_BRUISE_DAMAGE)

    # หลอดเลือดไม่ใช่ชั้นที่พลังงานต้องเจาะผ่าน แต่เดินอยู่ในกล้ามเนื้อและตามกระดูก
    # จึงฉีกตามความเสียหายที่เกิดกับสองอย่างนั้น — เป็นผลพลอยได้ ไม่ใช่ขั้นตอนแยก
    # นี่คือต้นทางของการเสียเลือดทั้งหมด (ดู circulation.bleed_rate · §18)
    # ความรุนแรงที่ "เกินจุดหัก" ไปแล้วยังต้องมีผล แม้ความเสียหายของกระดูกจะอิ่มตัว
    # แรงที่ทะลุเกณฑ์ไปสามเท่าย่อมฉีกเนื้อเยื่อรอบข้างมากกว่าแรงที่เพิ่งพอหัก
    overload = min(K.MAX_OVERLOAD, max(1.0, bone.fracture_ratio(stress, "bending")))
    torn += (here.get("bone", 0.0) - bone_before) * overload
    log["ความรุนแรงเกินเกณฑ์ (เท่า)"] = round(overload, 2)
    if torn > 0.0:
        here["vessel"] = min(1.0, here.get("vessel", 0.0) + torn * K.VESSEL_TEAR_SHARE)
        log["หลอดเลือดฉีก"] = round(here["vessel"], 3)

    if region in REGION_HAS_ORGAN:
        through = max(0.0, left - K.TISSUE_TOUGHNESS["bone_shield"] * area)
        if through > 0.0:
            here["organ"] = min(1.0, here.get("organ", 0.0) + through / K.ORGAN_ENERGY_SCALE)
            log["อวัยวะภายในกระทบ (J)"] = round(through, 1)
    return log


def rng_for(*parts) -> "object":
    """สตรีมสุ่มที่ผูกกับเหตุการณ์หนึ่ง — ไม่แตะ RNG หลักของโลก

    ใช้แพทเทิร์นเดียวกับ persist และ body.genetics: เหตุการณ์เดิมให้ผลเดิมเสมอ และการ
    เพิ่มการบาดเจ็บเข้ามาไม่เลื่อนสตรีมของโลกจนอนาคตเปลี่ยนไปทั้งใบ
    """
    import random
    key = "|".join(str(p) for p in parts).encode("utf-8")
    return random.Random(int.from_bytes(hashlib.sha256(key).digest()[:8], "big"))


def pick_region(*parts) -> str:
    """เลือกส่วนที่ถูกโดนแบบคาดเดาได้จากเหตุการณ์ — ถ่วงน้ำหนักตามพื้นที่ผิว

    ส่วนที่กว้างกว่าโดนบ่อยกว่าโดยธรรมชาติ (ขาสองข้างรวมกัน 44% ของผิวกาย หัวแค่ 7%)
    """
    roll = rng_for("region", *parts).random()
    total = sum(REGION_SURFACE_SHARE.values())
    upto = 0.0
    for region in REGIONS:
        upto += REGION_SURFACE_SHARE[region] / total
        if roll <= upto:
            return region
    return REGIONS[-1]


# ---------------------------------------------------------------- การหาย (§34)
def heal(state, days: float, recovery_factor: float = 1.0) -> None:
    """เดินความเสียหายทุกชิ้นเข้าหาศูนย์ตามเวลาที่ผ่านไป — แก้ `state` ในที่

        ระดับ(t) = ระดับ · e^{−λt}

    **อินทิเกรตเป็นรูปแบบปิดข้ามช่วงเวลา** ไม่ใช่เดินทีละก้าว เพราะเอนจินนี้กระโดดข้ามเวลา
    เป็นวัน (ดู Event.gap_days) ไม่มี tick ต่อเนื่องให้เดิน — ใช้ physics.relax ที่มีอยู่แล้ว
    เนื้อเยื่อแต่ละชนิดหายคนละความเร็ว ผิวหนังเร็วสุด กระดูกและอวัยวะช้าสุด
    """
    if not state or days <= 0.0:
        return
    for region in list(state):
        tissues = state[region]
        for tissue in list(tissues):
            rate = K.HEAL_RATE.get(tissue)
            if rate is None:
                continue
            level = PHYS.relax(tissues[tissue], 0.0, rate * max(0.05, recovery_factor), days)
            if level < K.HEAL_CLEAR_BELOW:
                del tissues[tissue]        # หายแล้ว ไม่ต้องแบกเศษไว้ในเซฟ
            else:
                tissues[tissue] = level
        if not tissues:
            del state[region]              # ส่วนนี้หายสนิท เอาออกจาก dict ทั้งก้อน


# ---------------------------------------------------------------- การเสียหน้าที่ (§28)
def capacity(state, group: str) -> float:
    """ตัวคูณความสามารถที่เหลือของกล้ามเนื้อกลุ่มหนึ่ง 0..1

    กระดูกหักที่ขาทำให้รับน้ำหนักแทบไม่ได้ ส่วนกล้ามเนื้อฉีกลดแรงตามสัดส่วน — น้ำหนักของ
    เนื้อเยื่อแต่ละชนิดต่างกันเพราะผลต่อการออกแรงต่างกัน (พรอมต์ §28)

    **เฉพาะส่วน** เจ็บแขนไม่ทำให้วิ่งช้า เจ็บขาไม่ทำให้กำลังแขนตก
    """
    if not state:
        return 1.0
    loss = 0.0
    for region in REGIONS:
        if REGION_MUSCLE_GROUP[region] != group:
            continue
        tissues = state.get(region)
        if not tissues:
            continue
        for tissue, level in tissues.items():
            loss += level * K.FUNCTION_LOSS_WEIGHT.get(tissue, 0.0)
    # ขาสองข้าง/แขนสองข้างแบ่งภาระกัน เจ็บข้างเดียวจึงไม่หมดทั้งกลุ่ม
    sides = sum(1 for r in REGIONS if REGION_MUSCLE_GROUP[r] == group)
    return max(K.MIN_FUNCTION, 1.0 - loss / max(1, sides))


def region_function(state, region: str) -> float:
    """หน้าที่ที่เหลือของ **ส่วนเดียว** 0..1 — แขนซ้ายข้างเดียว ไม่ใช่แขนทั้งคู่

    `capacity()` ตอบเรื่องการออกแรงของกลุ่มกล้ามเนื้อ ซึ่งแขนสองข้างหารกัน — ถูกแล้ว
    สำหรับคำถามว่า "ยกของหนักได้เท่าไร" แต่ผิดสำหรับคำถามว่า "ใช้แขนซ้ายได้ไหม"
    (§32 CanUseLeftArm) ข้างที่หักยังคงหัก ต่อให้อีกข้างสมบูรณ์
    """
    if region not in REGION_BONE:
        raise ValueError(f"ไม่รู้จักส่วนของร่าง: {region}")
    tissues = (state or {}).get(region)
    if not tissues:
        return 1.0
    loss = sum(level * K.FUNCTION_LOSS_WEIGHT.get(tissue, 0.0)
               for tissue, level in tissues.items())
    return max(K.MIN_FUNCTION, 1.0 - loss)


def reaction_penalty(state) -> float:
    """เวลาตอบสนองที่เพิ่มขึ้นจากบาดเจ็บที่ศีรษะ (สัดส่วน) — สมองกระทบทำให้ช้าลง"""
    if not state:
        return 0.0
    head = state.get("head", {})
    return (head.get("organ", 0.0) * K.HEAD_REACTION_PENALTY
            + head.get("bone", 0.0) * K.HEAD_REACTION_PENALTY * 0.5)


def explain(body, state) -> dict:
    """สถานะบาดเจ็บทั้งร่างในรูปที่อ่านได้ (พรอมต์ §44)"""
    if not state:
        return {"สถานะ": "ไม่มีบาดเจ็บ"}
    out = {"ความบาดเจ็บรวม": round(severity(state), 3)}
    region, level = worst(state)
    out["ส่วนที่หนักสุด"] = f"{region} ({level:.2f})" if region else "—"
    out["รายส่วน"] = {
        r: {t: round(v, 3) for t, v in sorted(tis.items()) if v > 0.0}
        for r, tis in sorted(state.items()) if any(v > 0.0 for v in tis.values())
    }
    out["ความสามารถที่เหลือ"] = {
        "ขา (×)": round(capacity(state, "leg"), 3),
        "แขน (×)": round(capacity(state, "arm"), 3),
        "ลำตัว (×)": round(capacity(state, "trunk"), 3),
        "เวลาตอบสนองเพิ่มขึ้น": f"{reaction_penalty(state):.0%}",
    }
    return out
