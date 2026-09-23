# -*- coding: utf-8 -*-
"""พารามิเตอร์ตั้งต้นของร่างกาย — สิ่งเดียวที่ "เกิดมาพร้อมตัว" และไม่เปลี่ยนตามเหตุการณ์

หลักการที่ทำให้ทั้งแพ็กเกจนี้ปลอดภัยกับซิมเดิม
--------------------------------------------------------------------------------------------
1. **ไม่แตะ RNG หลักของโลก** ทุกค่าสุ่มจาก `random.Random` ที่ผูกกับ (seed ของโลก, cid)
   แบบเดียวกับที่ persist ใช้เติม natural_lifespan/bloodline_affinity ให้เซฟเก่า
   ถ้าดึงจาก sim.rng แม้ครั้งเดียว โลกทั้งใบจะเดินคนละทางทันทีและ test_determinism จะพัง
2. **ไม่เก็บลงเซฟ** ร่างกายทั้งก้อนคำนวณใหม่ได้เสมอจาก (body_seed, cid, gender) สามค่านี้
   จึงไม่มีอะไรต้อง migrate และเซฟไม่บวม — ตัวละคร 2,700 คนในเซฟ 11 MB ถ้าแนบโครงกระดูก
   กับกล้ามเนื้อครบทุกคนจะโตเป็นหลักร้อย MB โดยไม่ได้อะไรกลับมา
3. **บริสุทธิ์** ฟังก์ชันในไฟล์นี้ไม่แก้สถานะใดๆ ให้ค่าเดิมเสมอสำหรับอินพุตเดิม

`body_seed` คือ seed ของโลก (Sim.seed) ตัวละครจากเซฟเก่าที่ไม่มีฟิลด์นี้จะได้ 0
ซึ่งยังคงที่และเดินซ้ำได้ เพียงแต่เป็นคนละร่างกับที่โลก seed อื่นจะให้ — ยอมรับได้
เพราะร่างกายไม่เคยถูกเปรียบเทียบข้ามเซฟ
"""
import random

from . import constants as K

_SALT = 0xB0D1E5        # กันไม่ให้ชนกับสตรีมย่อยอื่นที่ผูกกับ (seed, cid) เหมือนกัน


def _rng(body_seed: int, cid: int) -> random.Random:
    return random.Random(((int(body_seed) & 0xFFFFFFFF) << 32) ^ (int(cid) << 3) ^ _SALT)


def _clamped_normal(rng, mean, sd, lo, hi):
    """สุ่มแบบปกติแล้วหนีบให้อยู่ในช่วงที่เป็นไปได้ทางกายวิภาค (พรอมต์ §2)"""
    return min(hi, max(lo, rng.gauss(mean, sd)))


class Genetics:
    """ค่าตั้งต้นของร่างหนึ่งร่าง — อ่านอย่างเดียว สร้างจาก (body_seed, cid, gender)

    ทั้งหมดเป็นหน่วย SI ยกเว้นตัวที่เป็นสัดส่วนไร้หน่วยซึ่งระบุไว้ในชื่อ
    """

    __slots__ = ("cid", "gender", "height", "frame", "fat_fraction", "lbm_coef",
                 "specific_tension", "neuro_efficiency", "fast_fiber", "segment_ratio")

    def __init__(self, body_seed: int, cid: int, gender: str):
        rng = _rng(body_seed, cid)
        self.cid = cid
        # เพศที่ไม่อยู่ในตาราง (สัตว์อสูรที่จำแลงกาย เผ่าโกลาหล) ใช้ค่าของชายเป็นฐาน
        key = gender if gender in K.HEIGHT_MEAN else "ชาย"
        self.gender = key

        self.height = _clamped_normal(rng, K.HEIGHT_MEAN[key], K.HEIGHT_SD,
                                      K.HEIGHT_MIN, K.HEIGHT_MAX)
        self.frame = _clamped_normal(rng, K.FRAME_MEAN, K.FRAME_SD,
                                     K.FRAME_MIN, K.FRAME_MAX)
        self.fat_fraction = _clamped_normal(rng, K.FAT_FRACTION_MEAN[key], K.FAT_FRACTION_SD,
                                            K.FAT_FRACTION_MIN, K.FAT_FRACTION_MAX)
        self.lbm_coef = K.LBM_COEF[key]

        self.specific_tension = _clamped_normal(
            rng, K.SPECIFIC_TENSION_MEAN, K.SPECIFIC_TENSION_SD,
            K.SPECIFIC_TENSION_MIN, K.SPECIFIC_TENSION_MAX)
        self.neuro_efficiency = _clamped_normal(
            rng, K.NEURO_EFFICIENCY_MEAN, K.NEURO_EFFICIENCY_SD,
            K.NEURO_EFFICIENCY_MIN, K.NEURO_EFFICIENCY_MAX)
        self.fast_fiber = _clamped_normal(rng, K.FAST_FIBER_MEAN, K.FAST_FIBER_SD,
                                          K.FAST_FIBER_MIN, K.FAST_FIBER_MAX)

        # สัดส่วนแต่ละท่อนสุ่มแยกกัน — คนสูงเท่ากันจึงขายาว/ตัวยาวไม่เท่ากันจริง
        # เรียงชื่อก่อนวนเพื่อให้ลำดับการดึงเลขสุ่มคงที่ ไม่ขึ้นกับลำดับใน dict
        self.segment_ratio = {}
        for name in sorted(K.SEGMENT_RATIO_MEAN):
            mean = K.SEGMENT_RATIO_MEAN[name]
            self.segment_ratio[name] = _clamped_normal(
                rng, mean, K.SEGMENT_RATIO_SD,
                mean - K.SEGMENT_RATIO_CLAMP, mean + K.SEGMENT_RATIO_CLAMP)

    # ---- ความยาวจริงของแต่ละท่อน (m) ----
    def segment(self, name: str) -> float:
        """ความยาวท่อนหนึ่งเป็นเมตร — BoneLength_i = Height × ratio_i (พรอมต์ §2)"""
        return self.height * self.segment_ratio[name]

    @property
    def leg_length(self) -> float:
        """ความยาวขาทั้งท่อน (ต้นขา + หน้าแข้ง) เป็นเมตร"""
        return self.segment("femur") + self.segment("tibia")

    @property
    def arm_length(self) -> float:
        return self.segment("upper_arm") + self.segment("forearm")

    def explain(self) -> dict:
        """ค่าทั้งหมดในรูปที่อ่านได้ สำหรับโหมดดีบัก (พรอมต์ §44)"""
        return {
            "เพศ": self.gender,
            "ส่วนสูง (m)": round(self.height, 3),
            "โครงร่าง (×)": round(self.frame, 3),
            "สัดส่วนไขมัน": round(self.fat_fraction, 3),
            "ความตึงจำเพาะ (Pa)": round(self.specific_tension),
            "ประสิทธิภาพประสาท-กล้ามเนื้อ": round(self.neuro_efficiency, 3),
            "สัดส่วนเส้นใยหดเร็ว": round(self.fast_fiber, 3),
            "ความยาวท่อน (m)": {k: round(self.height * v, 3)
                                 for k, v in sorted(self.segment_ratio.items())},
        }


def of(character, body_seed: int = 0) -> Genetics:
    """ค่าตั้งต้นของตัวละครหนึ่งคน — ใช้ body_seed ที่ติดตัวมาถ้ามี"""
    seed = getattr(character, "body_seed", 0) or body_seed
    return Genetics(seed, character.cid, getattr(character, "gender", ""))
