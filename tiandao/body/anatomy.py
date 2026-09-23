# -*- coding: utf-8 -*-
"""กายวิภาคที่คำนวณได้ — องค์ประกอบมวล กล้ามเนื้อ และข้อต่อ

ลำดับการอนุพัทธ์ (พรอมต์ §1): GENETICS → COMPOSITION → MUSCLE → JOINT
ไม่มีขั้นไหนย้อนกลับไปแก้ขั้นก่อนหน้า และไม่มีค่าใดถูก "ตั้ง" — ทุกค่าคำนวณมาจากขั้นบน

มวลรวมของร่างไม่ได้ถูกกำหนดมาก่อนแล้วค่อยแบ่ง แต่**โผล่ออกมาจากองค์ประกอบ**:

    BodyMass = BoneMass + MuscleMass + OrganMass + FatMass

ทำไมไม่มี FluidMass เป็นก้อนที่ห้า (พรอมต์ §3 ระบุห้าก้อน)
--------------------------------------------------------------------------------------------
เพราะจะ **นับน้ำซ้ำ** กล้ามเนื้อมีน้ำอยู่ราว 76% ของมวลตัวมันเองอยู่แล้ว อวัยวะราว 75%
ถ้าบวกน้ำเป็นก้อนแยกอีก คนหนัก 70 kg จะกลายเป็น 95 kg ทันทีโดยไม่มีอะไรเพิ่มขึ้นจริง
น้ำจึงถูกแทนด้วย `water_mass` ซึ่งเป็นค่า **ที่อนุพัทธ์จากเนื้อเยื่อที่มีอยู่แล้ว** ไม่ใช่ก้อนมวล
(ระบบเสียเลือด/ขาดน้ำใน Phase 5 จะอ่านค่านี้ ไม่ใช่บวกเข้ามวลรวม)
"""
import math

from . import constants as K
from . import genetics as G
from .skeleton import Skeleton


class MuscleGroup:
    """กล้ามเนื้อหนึ่งกลุ่ม — แรงสูงสุดมาจากพื้นที่หน้าตัด ไม่ใช่จากค่าที่ตั้งไว้

        PCSA = มวล / (ความหนาแน่น × ความยาวเส้นใย)      [m^2]
        Fmax = σ × PCSA                                  [N]

    `σ` คือความตึงจำเพาะของแต่ละคน (genetics.specific_tension) จึงเป็นไปได้ที่คนสองคน
    มวลกล้ามเนื้อเท่ากันแต่ออกแรงได้ไม่เท่ากัน
    """

    __slots__ = ("name", "mass", "agonist_mass", "fiber_length", "pcsa", "max_force")

    def __init__(self, name, mass, fiber_length, specific_tension):
        self.name = name
        self.mass = mass                      # kg — ทั้งกลุ่ม รวมฝั่งที่ทำงานตรงข้ามกัน
        # เฉพาะฝั่งที่ออกแรงไปทางเดียวกับการเคลื่อนไหวเท่านั้นที่นับเข้า PCSA
        # (กลุ่มขามีทั้งเหยียดและงอ การถีบพื้นใช้แต่ฝั่งเหยียด)
        self.agonist_mass = mass * K.AGONIST_SHARE[name]
        self.fiber_length = fiber_length      # m
        self.pcsa = (self.agonist_mass / (K.MUSCLE_DENSITY * fiber_length)
                     if fiber_length > 0 else 0.0)
        self.max_force = specific_tension * self.pcsa     # N — แรงระดับเอ็น ไม่ใช่แรงที่พื้น

    def available_force(self, neuro_efficiency: float, effort: float = 1.0) -> float:
        """แรงที่เรียกใช้ได้จริงตอนนี้

            F = Fmax × ประสิทธิภาพประสาท-กล้ามเนื้อ × ตัวคูณจากสภาพร่างกาย

        ตัวคูณสุดท้ายรวมความล้ากับออกซิเจนที่เลือดส่งมาให้ (ดู Condition.effort_factor)
        สองอย่างนี้ **คูณกัน ไม่ใช่บวกกัน** — ล้าครึ่งหนึ่งและออกซิเจนครึ่งหนึ่ง
        เหลือแรงหนึ่งในสี่ ตามพรอมต์ §7–8, §19
        """
        return self.max_force * neuro_efficiency * max(0.0, effort)


class Body:
    """ร่างหนึ่งร่างที่คำนวณเสร็จแล้ว — อ่านอย่างเดียว ไม่ถูกเก็บลงเซฟ

    สร้างใหม่ได้เสมอจาก Genetics จึงถือเป็นแคชที่ทิ้งได้ (ดู tiandao/body/__init__.py)
    """

    __slots__ = ("gen", "bone_mass", "muscle_mass", "organ_mass", "fat_mass",
                 "mass", "muscles", "skeleton")

    def __init__(self, gen: G.Genetics):
        self.gen = gen
        # ---- 1. มวลไร้ไขมันจากส่วนสูงและโครงร่าง (allometric: มวล ∝ ส่วนสูง^2) ----
        lean = gen.lbm_coef * (gen.height ** 2) * gen.frame
        self.bone_mass = lean * K.LEAN_BONE_FRACTION
        self.organ_mass = lean * K.LEAN_ORGAN_FRACTION
        self.muscle_mass = lean * K.LEAN_MUSCLE_FRACTION
        # ---- 2. ไขมันเป็นสัดส่วนของมวล *รวม* จึงต้องแก้สมการกลับ ----
        #     f = Fat / (Lean + Fat)  ⟹  Fat = Lean · f / (1 − f)
        f = gen.fat_fraction
        self.fat_mass = lean * f / (1.0 - f)
        # ---- 3. มวลรวมโผล่ออกมาเอง ไม่ได้ถูกตั้ง ----
        self.mass = self.bone_mass + self.muscle_mass + self.organ_mass + self.fat_mass

        # ---- 4. แบ่งกล้ามเนื้อเป็นกลุ่ม แล้วหาแรงสูงสุดของแต่ละกลุ่ม ----
        segment_for = {"leg": gen.segment("femur"), "arm": gen.segment("upper_arm"),
                       "trunk": gen.segment("torso")}
        self.muscles = {}
        for name in sorted(K.MUSCLE_GROUP_SHARE):
            mass = self.muscle_mass * K.MUSCLE_GROUP_SHARE[name]
            fiber = segment_for[name] * K.FIBER_LENGTH_RATIO[name]
            self.muscles[name] = MuscleGroup(name, mass, fiber, gen.specific_tension)

        # ---- 5. โครงกระดูก: งบมวลจากข้อ 1 แจกตามส่วนแบ่ง แล้วรัศมีถูกแก้ย้อนจากมวล+ความยาว
        # จึงไม่มีความจริงสองชุดเรื่องมวลกระดูก (ดู skeleton.py)
        self.skeleton = Skeleton(gen, self.bone_mass)

    # ---------------------------------------------------------------- มวลและน้ำ
    @property
    def lean_mass(self) -> float:
        return self.bone_mass + self.muscle_mass + self.organ_mass

    @property
    def water_mass(self) -> float:
        """น้ำในตัว — **อนุพัทธ์จากเนื้อเยื่อ ไม่ใช่มวลก้อนที่ห้า** (ดูหัวไฟล์)"""
        w = K.WATER_FRACTION
        return (self.muscle_mass * w["muscle"] + self.organ_mass * w["organ"]
                + self.bone_mass * w["bone"] + self.fat_mass * w["fat"])

    @property
    def bmi(self) -> float:
        return self.mass / (self.gen.height ** 2)

    # ---------------------------------------------------------------- แรงและทอร์ก
    def group_force(self, group: str, cond=None) -> float:
        """แรงที่กล้ามเนื้อกลุ่มหนึ่งออกได้ตอนนี้ (N) — หักลบส่วนที่บาดเจ็บทำให้ใช้ไม่ได้

        ตัวคูณจากบาดเจ็บ **เฉพาะส่วน** เจ็บแขนไม่ลดแรงขา (ดู injury.capacity · §28)
        """
        from .condition import resolve
        cond = resolve(cond)
        base = self.muscles[group].available_force(self.gen.neuro_efficiency,
                                                   cond.effort_factor)
        if cond.injury:
            from . import injury as INJ
            base *= INJ.capacity(cond.injury, group)
        return base

    def endpoint_force(self, limb: str, cond=None) -> float:
        """แรงที่ **ปลายแขนขา** กระทำต่อโลกภายนอก (N)

        แรงกล้ามเนื้อไม่ใช่แรงที่พื้นได้รับ มันต้องผ่านคานสองทอดก่อน:

            τ_ข้อ   = F_กล้ามเนื้อ × แขนโมเมนต์        (สั้นมาก ~4 ซม.)
            F_ปลาย  = τ_ข้อ / ความยาวแขนกลประสิทธิผล    (ยาวกว่ามาก ~45 ซม.)

        อัตราทดนี้ (~1:11) คือเหตุผลที่กล้ามเนื้อออกแรงระดับสองหมื่นนิวตันแล้วกดพื้นได้
        เพียงระดับสองพัน — ตอนเขียนครั้งแรกข้ามขั้นนี้ไป จึงได้แรงขา 35 kN และกระโดดสูง 8.6 m
        และเป็นเหตุผลที่ **คนขายาวกว่าได้เปรียบตอนวิ่ง แต่เสียเปรียบตอนออกแรงดัน**
        """
        joint = "knee" if limb == "leg" else "elbow"
        return self.joint_torque(joint, cond) / self.effective_limb_length(limb)

    def effective_limb_length(self, limb: str) -> float:
        """ความยาวแขนกลจากข้อถึงจุดที่แรงออกสู่ภายนอก (m)"""
        full = self.gen.leg_length if limb == "leg" else self.gen.arm_length
        return full * K.LIMB_EFFECTIVE_RATIO[limb]

    def leg_force(self, cond=None) -> float:
        """แรงกดพื้นที่ขาทั้งสองข้างสร้างได้ (N) — ตัวตั้งต้นของทั้งวิ่งและกระโดด"""
        return self.endpoint_force("leg", cond)

    def joint_torque(self, joint: str, cond=None) -> float:
        """ทอร์กรอบข้อหนึ่ง (N·m)

            τ = r · F            (พรอมต์ §6 — ที่มุมที่แขนโมเมนต์ยาวที่สุด sinθ = 1)

        แขนโมเมนต์ r คิดจากความยาวท่อนที่ข้อนั้นขับ ความสามารถออกแรงจึงขึ้นกับ
        **รูปร่าง** ด้วย ไม่ใช่ขึ้นกับมวลกล้ามเนื้ออย่างเดียว — คนขายาวได้ทอร์กมากกว่า
        ที่แรงกล้ามเนื้อเท่ากัน แต่ต้องออกแรงมากกว่าเพื่อความเร็วปลายเท่ากัน
        """
        group, _segment = _JOINT_SOURCE[joint]
        return self.group_force(group, cond) * self.moment_arm(joint)

    def moment_arm(self, joint: str) -> float:
        """แขนโมเมนต์ของข้อหนึ่ง (m)"""
        _group, segment = _JOINT_SOURCE[joint]
        return self.gen.segment(segment) * K.MOMENT_ARM_RATIO[joint]

    def explain(self) -> dict:
        """รายละเอียดที่ย้อนกลับไปหาการคำนวณได้ (พรอมต์ §44)"""
        return {
            "พันธุกรรม": self.gen.explain(),
            "องค์ประกอบมวล (kg)": {
                "กระดูก": round(self.bone_mass, 2),
                "กล้ามเนื้อ": round(self.muscle_mass, 2),
                "อวัยวะ": round(self.organ_mass, 2),
                "ไขมัน": round(self.fat_mass, 2),
                "รวม": round(self.mass, 2),
                "(น้ำที่อยู่ในเนื้อเยื่อเหล่านี้)": round(self.water_mass, 2),
            },
            "ดัชนีมวลกาย": round(self.bmi, 1),
            "กล้ามเนื้อ": {
                name: {
                    "มวล (kg)": round(m.mass, 2),
                    "ความยาวเส้นใย (m)": round(m.fiber_length, 4),
                    "PCSA (cm^2)": round(m.pcsa * 1e4, 1),
                    "แรงสูงสุด (N)": round(m.max_force),
                    "แรงที่ใช้ได้ (N)": round(m.available_force(self.gen.neuro_efficiency)),
                } for name, m in sorted(self.muscles.items())
            },
            "โครงกระดูก": self.skeleton.explain(),
            "ทอร์กข้อต่อ (N·m)": {
                j: round(self.joint_torque(j)) for j in sorted(_JOINT_SOURCE)
            },
            "แขนโมเมนต์ (m)": {j: round(self.moment_arm(j), 4) for j in sorted(_JOINT_SOURCE)},
            "แรงที่ปลาย (N)": {
                "ขา (กดพื้น)": round(self.endpoint_force("leg")),
                "แขน (ดัน/ดึง)": round(self.endpoint_force("arm")),
            },
        }


# ข้อต่อไหนถูกขับด้วยกล้ามเนื้อกลุ่มไหน และแขนโมเมนต์อิงความยาวท่อนใด
_JOINT_SOURCE = {
    "knee": ("leg", "femur"),
    "hip": ("leg", "femur"),
    "elbow": ("arm", "upper_arm"),
    "shoulder": ("arm", "upper_arm"),
    "spine": ("trunk", "torso"),
}
