# -*- coding: utf-8 -*-
"""โครงกระดูกในฐานะ **โครงสร้างรับแรง** ไม่ใช่รายชื่อชิ้นส่วน (พรอมต์ §4–5)

ทำไมต้องมีทั้งที่ Phase 1 มีความยาวท่อนอยู่แล้ว
--------------------------------------------------------------------------------------------
Phase 1 ใช้กระดูกเป็นแค่ "คาน" ที่กำหนดแขนโมเมนต์ แต่กระดูกยัง **รับแรงและหักได้** ซึ่งเป็น
สิ่งที่ Phase 4 (การบาดเจ็บ) ทั้งเฟสตั้งอยู่บนมัน กระดูกจึงต้องมีหน้าตัดจริง ไม่ใช่แค่ความยาว

มวลกับรูปทรงมาจากไหน — และทำไมไม่ขัดกันเอง
--------------------------------------------------------------------------------------------
องค์ประกอบร่างกาย (anatomy.Body) เป็นผู้กำหนด *งบมวลกระดูกรวม* อยู่แล้ว ถ้าคำนวณมวลจาก
รูปทรงอีกทางหนึ่ง จะได้ความจริงสองชุดที่ไม่ตรงกัน จึงทำกลับทาง: **งบมวลแจกให้แต่ละชิ้น
ตามส่วนแบ่ง แล้วแก้สมการย้อนหารัศมี**

    มวล = ความหนาแน่น × ปริมาตร ≈ ρ · πr²L      (พรอมต์ §4 อนุมัติทรงกระบอกไว้)
    ⟹ r = sqrt( มวล / (ρ · π · L) )

รัศมีจึงเป็นสิ่งที่ *โผล่ออกมา* จากมวลกับความยาว คนตัวสูงที่มวลกระดูกเท่ากันจะได้กระดูกที่
**ยาวกว่าแต่เรียวกว่า** หน้าตัดเล็กลง ความเค้นที่แรงเท่ากันจึงสูงกว่า — หักง่ายกว่าจริงๆ
โดยไม่ต้องเขียนกฎว่า "คนสูงกระดูกเปราะ"

ข้อจำกัด (พรอมต์ §41)
--------------------------------------------------------------------------------------------
ทรงกระบอกตันเป็นค่าประมาณ กระดูกจริงเป็นท่อกลวงมีโพรงไขกระดูก ค่าความหนาแน่นที่ใช้จึงเป็น
ความหนาแน่นเฉลี่ยทั้งชิ้นรวมโพรง ไม่ใช่ความหนาแน่นของเนื้อกระดูกคอร์ติคัล และความแข็งแรงที่
ใช้เป็นค่ากลางของกระดูกยาวผู้ใหญ่ ไม่ได้แยกตามชิ้นหรือตามอายุ
"""
import math

from .. import physics as PHYS
from . import constants as K


class Bone:
    """กระดูกหนึ่งชิ้น (หรือหนึ่งคู่) — รูปทรงมาจากมวลกับความยาว ไม่ได้ตั้งไว้"""

    __slots__ = ("name", "count", "length", "mass", "radius", "area")

    def __init__(self, name, count, length, mass):
        self.name = name
        self.count = count                 # กี่ชิ้นในร่าง (ซ้าย/ขวา)
        self.length = length               # m — ต่อชิ้น
        self.mass = mass                   # kg — รวมทุกชิ้นของชื่อนี้
        per_piece = mass / count if count else mass
        # r = sqrt(m / (ρπL)) — แก้ย้อนจาก m = ρπr²L
        self.radius = (math.sqrt(per_piece / (K.BONE_DENSITY * math.pi * length))
                       if length > 0 else 0.0)
        self.area = math.pi * self.radius ** 2       # m^2 — หน้าตัดต่อชิ้น

    # ---------------------------------------------------------------- ความเค้น
    def stress(self, force: float) -> float:
        """ความเค้นตามแนวแกนเมื่อรับแรง (Pa)

            σ = F / A                                          (พรอมต์ §5)

        แรงถูกหารด้วยจำนวนชิ้นที่รับร่วมกัน — ยืนสองขาแล้วกระดูกต้นขาแต่ละข้างรับครึ่งเดียว
        """
        if self.area <= 0.0:
            return 0.0
        return (force / self.count) / self.area

    def bending_stress(self, force: float, lever: float = None) -> float:
        """ความเค้นจากแรงดัด (Pa) — โหมดที่กระดูกยาวหักจริงเกือบทุกครั้ง

            σ = M·y / I     โดย M = F·L,  y = r,  I = πr⁴/4 (หน้าตัดกลม)
            ⟹ σ = 4·F·L / (π·r³)

        แรงกระแทกด้านข้างอันตรายกว่าแรงกดตามแนวแกนมาก เพราะ r³ ในตัวส่วนทำให้กระดูกเรียว
        เสียเปรียบอย่างรุนแรง — เป็นเหตุผลเชิงเรขาคณิตล้วนๆ ไม่ใช่ตัวคูณที่ตั้งขึ้น
        """
        if self.radius <= 0.0:
            return 0.0
        arm = self.length * 0.5 if lever is None else lever
        moment = (force / self.count) * arm
        return 4.0 * moment / (math.pi * self.radius ** 3)

    # ---------------------------------------------------------------- การหัก
    def fracture_ratio(self, stress: float, mode: str = "compressive") -> float:
        """ความเค้นที่ได้รับ เทียบกับความแข็งแรงของกระดูก — 1.0 คือถึงเกณฑ์พอดี"""
        return stress / _YIELD[mode]

    def fracture_risk(self, stress: float, mode: str = "compressive") -> float:
        """โอกาสหัก 0..1 — เส้นโค้ง ไม่ใช่เกณฑ์ตัด (พรอมต์ §5)

            P = [ σ(k·(r − 1)) − σ(−k) ] / [ 1 − σ(−k) ]      โดย r = ความเค้น/ความแข็งแรง

        แกนกลางคือ logistic ตามสเปก แต่ **ปรับให้ผ่านศูนย์** เพราะ σ(k·(0−1)) เพียวๆ ให้
        ค่าราว 0.003 นั่นแปลว่ากระดูกมีโอกาสหักทั้งที่ไม่มีแรงมากระทำเลย ซึ่งไม่ใช่เส้นโค้ง
        ที่นุ่มนวล แต่เป็นความผิดพลาด การหารด้วย (1 − σ(−k)) ทำให้:
            ความเค้น 0        -> 0.000  (ไม่มีแรง ไม่มีโอกาสหัก)
            ความเค้น = เกณฑ์  -> ~0.500  (โดนเท่ากันเป๊ะยังหักบ้างไม่หักบ้าง)
            ความเค้น >> เกณฑ์ -> เข้าใกล้ 1
        """
        floor = PHYS.logistic(-K.FRACTURE_SHARPNESS)
        raw = PHYS.logistic(K.FRACTURE_SHARPNESS * (self.fracture_ratio(stress, mode) - 1.0))
        return max(0.0, (raw - floor) / (1.0 - floor))

    def explain(self, load: float = 0.0) -> dict:
        out = {
            "จำนวน (ชิ้น)": self.count,
            "ความยาว (m)": round(self.length, 3),
            "มวลรวม (kg)": round(self.mass, 3),
            "รัศมี (m)": round(self.radius, 4),
            "หน้าตัด (cm^2)": round(self.area * 1e4, 2),
        }
        if load:
            axial = self.stress(load)
            bend = self.bending_stress(load)
            out["รับแรง (N)"] = round(load)
            out["ความเค้นแนวแกน (MPa)"] = round(axial / 1e6, 1)
            out["โอกาสหักจากแรงอัด"] = round(self.fracture_risk(axial, "compressive"), 4)
            out["ความเค้นจากการดัด (MPa)"] = round(bend / 1e6, 1)
            out["โอกาสหักจากการดัด"] = round(self.fracture_risk(bend, "bending"), 4)
        return out


_YIELD = {
    "compressive": K.BONE_YIELD_COMPRESSIVE,
    "tensile": K.BONE_YIELD_TENSILE,
    "bending": K.BONE_YIELD_BENDING,
}


class Skeleton:
    """กระดูกทั้งชุดของร่างหนึ่ง — สร้างจากงบมวลกระดูกและความยาวท่อน"""

    __slots__ = ("bones",)

    def __init__(self, gen, bone_mass: float):
        self.bones = {}
        for name in sorted(K.BONE_SPEC):
            share, segment, count = K.BONE_SPEC[name]
            self.bones[name] = Bone(name, count, _segment_length(gen, segment),
                                    bone_mass * share)

    def __getitem__(self, name) -> Bone:
        return self.bones[name]

    @property
    def total_mass(self) -> float:
        return sum(b.mass for b in self.bones.values())

    def weakest_under(self, force: float, mode: str = "compressive"):
        """กระดูกชิ้นที่เสี่ยงหักที่สุดเมื่อแรงเท่านี้ผ่านเข้ามา — คืน (ชื่อ, โอกาสหัก)"""
        risks = [(b.fracture_risk(b.stress(force), mode), n) for n, b in self.bones.items()]
        risk, name = max(risks)
        return name, risk

    def explain(self, load: float = 0.0) -> dict:
        return {name: bone.explain(load) for name, bone in sorted(self.bones.items())}


def _segment_length(gen, segment: str) -> float:
    """ความยาวของท่อนหนึ่ง — บางท่อนไม่ได้อยู่ใน SEGMENT_RATIO จึงคิดจากส่วนสูงตรงๆ"""
    extra = {
        "skull_span": K.SKULL_SPAN_RATIO,
        "foot": K.FOOT_LENGTH_RATIO,
        "hand": K.HAND_LENGTH_RATIO,
    }
    if segment in extra:
        return gen.height * extra[segment]
    return gen.segment(segment)
