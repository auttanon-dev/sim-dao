# -*- coding: utf-8 -*-
"""ร่างกายต้องเป็นต้นเหตุของความสามารถ ไม่ใช่ผลลัพธ์ของค่าพลังที่ตั้งไว้ — Phase 1–2

    python -m unittest test_body -v

    Phase 1  องค์ประกอบมวล · กล้ามเนื้อ · ข้อต่อ · ความสามารถทางกาย
    Phase 2  โครงกระดูกที่รับแรงและหักได้ (§4–5) · จุดศูนย์กลางมวลและการทรงตัว (§10)

ข้อที่ไฟล์นี้ล็อกไว้ ตรงกับชุดทดสอบที่สเปกกำหนด (พรอมต์ §43) เท่าที่สองเฟสนี้ครอบคลุม:

    TEST 1  PCSA เพิ่ม  ->  แรงสูงสุดต้องเพิ่ม
    TEST 2  แขนโมเมนต์เปลี่ยน  ->  ทอร์กที่ข้อต้องเปลี่ยนตาม
    TEST 3  มวลเพิ่มแต่แรงเท่าเดิม  ->  ความเร่ง/ความสามารถต้องลด
    TEST 4  ความเร็วขณะพ้นพื้นเพิ่ม  ->  ความสูงกระโดดต้องเพิ่มตาม h = v²/2g
    TEST 9  แรงเสียดทานต่ำมาก  ->  แรงในแนวราบสูงสุดต้องลด

TEST 5 (พลังงานจลน์ของการปะทะ) · TEST 6 (เสียเลือด) · TEST 7 (ขาบาดเจ็บ) ·
TEST 8 (ความล้า) · TEST 10 (การรับรู้ร่างกายตัวเอง) **ยังไม่อยู่ใน Phase 1** — ระบบที่
ต้องใช้ยังไม่มี การเขียนเทสต์ที่ผ่านโดยไม่มีระบบรองรับจะเป็นการอ้างว่ามีของที่ยังไม่มี
"""
import contextlib
import copy
import io
import math
import unittest

from tiandao import body as B
from tiandao import rules as R
from tiandao import sim as S
from tiandao.body import (anatomy, balance, capability, constants as K,
                          genetics, skeleton)
from tiandao.models import Character


def quiet(fn, *a, **kw):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*a, **kw)


def person(cid=0, gender="ชาย", body_seed=7):
    ch = Character(cid=cid, name=f"ผู้ทดสอบ {cid}", world_id=0, dao="วิถีดาบ",
                   dao_tags=[], born_day=0, gender=gender)
    ch.body_seed = body_seed
    return ch


def bodies(n=400, body_seed=7):
    return [B.body_of(person(cid, "ชาย" if cid % 2 == 0 else "หญิง", body_seed))
            for cid in range(n)]


class SpecTests(unittest.TestCase):
    """ชุดทดสอบตามสเปก (พรอมต์ §43)"""

    def test_1_more_cross_section_means_more_force(self):
        gen = genetics.Genetics(7, 0, "ชาย")
        small = anatomy.MuscleGroup("leg", 8.0, 0.10, gen.specific_tension)
        big = anatomy.MuscleGroup("leg", 16.0, 0.10, gen.specific_tension)
        self.assertGreater(big.pcsa, small.pcsa)
        self.assertGreater(big.max_force, small.max_force)
        # Fmax = σ × PCSA — ความสัมพันธ์ต้องเป็นเชิงเส้นตรงตามสูตร ไม่ใช่ตัวคูณที่เดาเอา
        self.assertAlmostEqual(big.max_force / small.max_force, big.pcsa / small.pcsa, places=9)
        self.assertAlmostEqual(big.max_force, gen.specific_tension * big.pcsa, places=6)

    def test_2_a_different_lever_arm_changes_joint_torque(self):
        body = B.body_of(person())
        base_arm = body.moment_arm("knee")
        base_torque = body.joint_torque("knee")
        self.assertAlmostEqual(base_torque, body.group_force("leg") * base_arm, places=6)
        # τ = r·F — คูณแขนโมเมนต์สองเท่า ทอร์กต้องเป็นสองเท่าพอดี
        longer = copy.deepcopy(body)
        longer.gen.segment_ratio["femur"] *= 2.0
        self.assertAlmostEqual(longer.moment_arm("knee"), base_arm * 2.0, places=9)
        self.assertAlmostEqual(longer.joint_torque("knee") / base_torque, 2.0, places=6)

    def test_3_more_mass_at_the_same_force_means_less_capability(self):
        light = B.body_of(person())
        heavy = copy.deepcopy(light)
        heavy.fat_mass += 25.0          # อ้วนขึ้นล้วนๆ กล้ามเนื้อเท่าเดิม
        heavy.mass += 25.0
        self.assertAlmostEqual(heavy.leg_force(), light.leg_force(), places=6,
                               msg="เพิ่มไขมันไม่ควรทำให้แรงกล้ามเนื้อเปลี่ยน")
        self.assertLess(capability.jump_height(heavy), capability.jump_height(light))
        self.assertLess(capability.max_running_speed(heavy),
                        capability.max_running_speed(light))
        self.assertLess(capability.strength_index(heavy), capability.strength_index(light))

    def test_4_jump_height_follows_takeoff_velocity_exactly(self):
        for cid in range(12):
            body = B.body_of(person(cid))
            v = capability.takeoff_velocity(body)
            if v <= 0:
                continue
            # h = v² / 2g — ไม่ใช่สูตรอื่นที่บังเอิญให้ตัวเลขใกล้กัน
            self.assertAlmostEqual(capability.jump_height(body),
                                   v * v / (2.0 * K.GRAVITY), places=9)

    def test_4b_a_faster_takeoff_always_jumps_higher(self):
        body = B.body_of(person())
        stronger = copy.deepcopy(body)
        stronger.muscles["leg"].max_force *= 1.25
        self.assertGreater(capability.takeoff_velocity(stronger),
                           capability.takeoff_velocity(body))
        self.assertGreater(capability.jump_height(stronger), capability.jump_height(body))

    def test_9_low_friction_caps_the_usable_ground_force(self):
        body = B.body_of(person())
        stone = capability.max_running_speed(body, K.TERRAIN_FRICTION["หิน"])
        ice = capability.max_running_speed(body, K.TERRAIN_FRICTION["น้ำแข็ง"])
        mud = capability.max_running_speed(body, K.TERRAIN_FRICTION["โคลน"])
        self.assertLess(ice, mud, "น้ำแข็งต้องลื่นกว่าโคลน")
        self.assertLess(mud, stone)
        self.assertLess(ice, stone * 0.75, "พื้นน้ำแข็งต้องกดความเร็วลงอย่างมีนัยสำคัญ")


class EmergenceTests(unittest.TestCase):
    """สิ่งที่พิสูจน์ว่าความสามารถ *โผล่ออกมา* จริง ไม่ได้ถูกตั้งไว้"""

    def test_body_mass_is_the_sum_of_its_tissues_with_no_double_counted_water(self):
        for body in bodies(120):
            total = body.bone_mass + body.muscle_mass + body.organ_mass + body.fat_mass
            self.assertAlmostEqual(body.mass, total, places=9)
            # น้ำอยู่ *ข้างใน* เนื้อเยื่อแล้ว ถ้าถูกนับเป็นก้อนที่ห้าจะเกินมวลรวมทันที
            self.assertLess(body.water_mass, body.mass,
                            "มวลน้ำต้องเป็นส่วนหนึ่งของมวลรวม ไม่ใช่ก้อนที่บวกเพิ่ม")
            self.assertGreater(body.water_mass, body.mass * 0.35)

    def test_same_weight_different_composition_means_different_capability(self):
        """พรอมต์ §3: สองคนที่ชั่งน้ำหนักได้เท่ากันต้องอธิบายได้ว่าทำไมเก่งไม่เท่ากัน"""
        lean = B.body_of(person())
        fat = copy.deepcopy(lean)
        moved = 8.0
        fat.muscle_mass -= moved
        fat.fat_mass += moved
        fat.muscles["leg"].max_force *= (lean.muscle_mass - moved) / lean.muscle_mass
        self.assertAlmostEqual(fat.mass, lean.mass, places=9, msg="ต้องหนักเท่ากันเป๊ะ")
        self.assertLess(capability.jump_height(fat), capability.jump_height(lean))
        self.assertLess(capability.strength_index(fat), capability.strength_index(lean))

    def test_two_people_of_the_same_height_can_have_different_proportions(self):
        """พรอมต์ §2: สัดส่วนต้องไม่ใช่ค่าคงที่ตัวเดียวสำหรับทุกคน"""
        ratios = {round(b.gen.segment_ratio["femur"], 4) for b in bodies(200)}
        self.assertGreater(len(ratios), 100, "ทุกคนมีสัดส่วนต้นขาเท่ากันหมด")

    def test_no_capability_is_stored_anywhere_on_the_character(self):
        """ไม่มี Strength/Speed/Endurance เป็นฟิลด์ที่เก็บไว้ — มีแต่คำนวณเอา"""
        import dataclasses
        names = {f.name.lower() for f in dataclasses.fields(Character)}
        for banned in ("strength", "speed", "endurance", "agility", "stamina",
                       "jump", "carry_capacity", "reaction_time"):
            self.assertNotIn(banned, names, f"มีฟิลด์ {banned} เป็นแหล่งความจริงแล้ว")

    def test_every_value_is_physically_plausible_across_a_population(self):
        """ไม่ใช่แค่คำนวณได้ ต้องอยู่ในช่วงที่มนุษย์เป็นไปได้จริงด้วย (พรอมต์ §41)"""
        for body in bodies(400):
            self.assertTrue(1.40 <= body.gen.height <= 2.10)
            self.assertTrue(30.0 <= body.mass <= 140.0, f"มวล {body.mass:.1f} kg")
            self.assertTrue(13.0 <= body.bmi <= 38.0, f"BMI {body.bmi:.1f}")
            self.assertTrue(1.0 <= capability.max_running_speed(body) <= 13.5)
            self.assertTrue(0.0 <= capability.jump_height(body) <= 1.2)
            self.assertTrue(0.0 <= capability.carry_capacity(body) <= 140.0)
            self.assertTrue(0.10 <= capability.reaction_time(body) <= 0.40)
            # แรงที่ปลายขาเทียบน้ำหนักตัว — มนุษย์อยู่ราว 1.5–4.5 เท่า
            self.assertTrue(1.0 <= body.leg_force() / (body.mass * K.GRAVITY) <= 5.5)


class DeterminismTests(unittest.TestCase):
    """โลกต้องเดินซ้ำได้เหมือนเดิม — ร่างกายห้ามเป็นตัวทำให้เพี้ยน"""

    def test_the_same_character_always_gets_the_same_body(self):
        a = B.body_of(person(42))
        B._CACHE.clear()
        b = B.body_of(person(42))
        self.assertAlmostEqual(a.mass, b.mass, places=12)
        self.assertAlmostEqual(a.gen.height, b.gen.height, places=12)
        self.assertEqual(a.gen.segment_ratio, b.gen.segment_ratio)

    def test_building_a_body_never_touches_the_world_rng(self):
        sim = quiet(S.Sim, seed=7, tiers=2)
        before = sim.rng.getstate()
        for ch in sim.living_in(0)[:50]:
            B.body_of(ch)
            B.estimated_max_speed(ch)
            B.strength_of(ch)
            R.power(ch, sim.worlds[0])
        self.assertEqual(sim.rng.getstate(), before,
                         "การสร้างร่างกายขยับ RNG หลัก — โลกจะเดินคนละทางทันที")

    def test_different_worlds_give_different_bodies(self):
        self.assertNotAlmostEqual(B.body_of(person(1, body_seed=1)).mass,
                                  B.body_of(person(1, body_seed=2)).mass, places=6)

    def test_an_old_save_character_without_body_seed_still_works(self):
        """เซฟเก่าไม่มีฟิลด์นี้ — ต้องได้ร่างที่คงที่ ไม่ใช่ระเบิดหรือสุ่มใหม่ทุกครั้ง"""
        import pickle
        ch = person(9)
        del ch.__dict__["body_seed"]
        restored = pickle.loads(pickle.dumps(ch))
        self.assertEqual(restored.body_seed, 0, "__setstate__ ต้องเติมค่าปริยายให้")
        self.assertAlmostEqual(B.body_of(restored).mass,
                               B.body_of(restored).mass, places=12)

    def test_the_body_cache_never_reaches_the_save_file(self):
        """แคชอยู่ระดับโมดูล ไม่ใช่บน Character — ไม่งั้นเซฟจะบวมและ pickle ช้าลง"""
        import pickle
        ch = person(3)
        B.body_of(ch)
        blob = pickle.dumps(ch)
        self.assertNotIn(b"MuscleGroup", blob)
        self.assertNotIn(b"Genetics", blob)
        # ฟิลด์ที่เพิ่มเข้าเซฟจริงมีแค่จำนวนเต็มตัวเดียว
        self.assertIsInstance(ch.body_seed, int)


class PowerIntegrationTests(unittest.TestCase):
    """ร่างกายมีผลกับพลังจริง แต่ต้องเป็นปัจจัยเล็ก ไม่ใช่ตัวตัดสิน"""

    def setUp(self):
        self.sim = quiet(S.Sim, seed=7, tiers=2)
        self.w = self.sim.worlds[0]

    def test_a_stronger_body_yields_more_power_all_else_equal(self):
        a, b = self.sim.living_in(0)[:2]
        for src, dst in ((a, b),):
            for field in ("realm", "tier", "insight", "decay", "skills", "mastery",
                          "blood", "bloodline_buff", "dao", "dao_tags"):
                setattr(dst, field, copy.deepcopy(getattr(src, field)))
        weak, strong = sorted((a, b), key=B.strength_of)
        if abs(B.strength_of(weak) - B.strength_of(strong)) < 1e-9:
            self.skipTest("สองคนนี้ร่างกายเท่ากันพอดี")
        self.assertGreater(R.power(strong, self.w), R.power(weak, self.w))

    def test_the_body_moves_power_by_only_a_few_percent(self):
        """โลกนี้พลังมาจากขั้น วิชา ธาตุ ปราณ — กายวิภาคต้องไม่กลืนทั้งระบบ"""
        ch = self.sim.living_in(0)[0]
        base = R.power(ch, self.w)
        span = []
        for idx in (0.6, 1.0, 1.8):        # ช่วงดัชนีที่ประชากรจริงกินได้
            span.append(1.0 + K.BODY_POWER_WEIGHT * (idx - 1.0))
        self.assertLess(max(span) / min(span), 1.35,
                        "ร่างกายขยับพลังมากเกินไปจนระบบเดิมถูกกลืน")
        self.assertGreater(base, 0.0)


class SkeletonTests(unittest.TestCase):
    """โครงกระดูกต้องเป็นโครงสร้างรับแรงจริง (พรอมต์ §4–5)"""

    def test_bone_mass_has_exactly_one_source_of_truth(self):
        for body in bodies(60):
            self.assertAlmostEqual(body.skeleton.total_mass, body.bone_mass, places=9,
                                   msg="มวลกระดูกจากชิ้นส่วนไม่ตรงกับงบขององค์ประกอบร่างกาย")

    def test_radius_is_solved_back_from_mass_and_length(self):
        """m = ρπr²L ต้องกลับไปกลับมาได้ — รัศมีไม่ใช่ค่าที่ตั้งขึ้นแยกต่างหาก"""
        for body in bodies(40):
            for bone in body.skeleton.bones.values():
                volume = math.pi * bone.radius ** 2 * bone.length
                self.assertAlmostEqual(K.BONE_DENSITY * volume * bone.count, bone.mass,
                                       places=9)

    def test_stress_is_force_over_area(self):
        bone = B.body_of(person()).skeleton["femur"]
        self.assertAlmostEqual(bone.stress(10_000.0),
                               (10_000.0 / bone.count) / bone.area, places=6)
        # เชิงเส้นตรงตามสูตร ไม่ใช่เส้นโค้งที่เดาเอา
        self.assertAlmostEqual(bone.stress(20_000.0) / bone.stress(10_000.0), 2.0, places=9)

    def test_a_taller_frame_gets_thinner_bones_and_more_stress(self):
        """ข้ออ้างในเอกสารของ skeleton.py ต้องเป็นจริง ไม่ใช่คำบรรยายลอยๆ"""
        short = B.body_of(person())
        tall = copy.deepcopy(short)
        tall.gen.height *= 1.15          # สูงขึ้นแต่มวลกระดูกเท่าเดิม
        tall.skeleton = B.Skeleton(tall.gen, short.bone_mass)
        a, b = short.skeleton["femur"], tall.skeleton["femur"]
        self.assertGreater(b.length, a.length)
        self.assertLess(b.radius, a.radius, "กระดูกยาวขึ้นที่มวลเท่าเดิมต้องเรียวลง")
        self.assertGreater(b.stress(8000.0), a.stress(8000.0))

    def test_fracture_risk_is_a_curve_that_starts_at_zero(self):
        bone = B.body_of(person()).skeleton["femur"]
        self.assertEqual(bone.fracture_risk(0.0), 0.0, "ไม่มีแรงต้องไม่มีโอกาสหัก")
        at_yield = bone.fracture_risk(K.BONE_YIELD_COMPRESSIVE)
        self.assertGreater(at_yield, 0.45)
        self.assertLess(at_yield, 0.55, "ที่เกณฑ์พอดีต้องราวครึ่งๆ ไม่ใช่ 0 หรือ 1")
        self.assertLess(bone.fracture_risk(K.BONE_YIELD_COMPRESSIVE * 3), 1.0000001)
        # ต้องเพิ่มแบบไม่ลดลงเลยตลอดช่วง และไม่ใช่ขั้นบันได 0/1
        seen = [bone.fracture_risk(K.BONE_YIELD_COMPRESSIVE * r / 10.0) for r in range(0, 31)]
        self.assertEqual(seen, sorted(seen))
        self.assertGreater(len({round(x, 3) for x in seen}), 8, "เส้นโค้งแบนเกินไป")

    def test_bending_breaks_a_long_bone_long_before_compression_does(self):
        """ความจริงทางกลศาสตร์: กระดูกยาวหักจากการดัด ไม่ใช่จากการกดตามแนวแกน"""
        bone = B.body_of(person()).skeleton["femur"]
        force = 9000.0
        self.assertGreater(bone.bending_stress(force), bone.stress(force) * 10)
        self.assertGreater(bone.fracture_risk(bone.bending_stress(force), "bending"),
                           bone.fracture_risk(bone.stress(force), "compressive"))

    def test_every_bone_has_a_plausible_cross_section(self):
        for body in bodies(200):
            for name, bone in body.skeleton.bones.items():
                self.assertGreater(bone.radius, 0.002, name)
                self.assertLess(bone.radius, 0.060, name)
                self.assertGreater(bone.length, 0.05, name)


class BalanceTests(unittest.TestCase):
    """จุดศูนย์กลางมวลและการทรงตัว (พรอมต์ §10)"""

    def test_segment_masses_add_up_to_the_whole_body(self):
        for body in bodies(60):
            self.assertAlmostEqual(sum(balance.segment_masses(body).values()),
                                   body.mass, places=9)

    def test_centre_of_mass_emerges_near_the_measured_human_value(self):
        """ไม่ได้ตั้งไว้ — รวมจากมวล×ตำแหน่งของทุกส่วนแล้วออกมาเองราว 0.54 ของส่วนสูง"""
        for body in bodies(80):
            frac = balance.com_height(body) / body.gen.height
            self.assertTrue(0.50 < frac < 0.60, f"COM อยู่ที่ {frac:.3f} ของส่วนสูง")

    def test_com_is_the_mass_weighted_average_of_body_and_load(self):
        body = B.body_of(person())
        load, arm = 30.0, 0.40
        expected = (body.mass * K.COM_AHEAD_OF_ANKLE + load * arm) / (body.mass + load)
        self.assertAlmostEqual(balance.com_offset(body, load, arm), expected, places=12)

    def test_a_heavier_load_in_front_eats_the_balance_margin(self):
        body = B.body_of(person())
        margins = [balance.balance_margin(body, kg, 0.45) for kg in (0, 20, 40, 80, 160)]
        self.assertEqual(margins, sorted(margins, reverse=True))
        self.assertGreater(margins[0], 0.0)

    def test_max_stable_load_is_solved_not_searched(self):
        """คำตอบต้องอยู่บนขอบพอดี — เอาค่ากลับไปแทนในสมการสมดุลแล้วต้องได้ศูนย์"""
        body = B.body_of(person())
        arm = 0.55
        limit = balance.max_stable_load(body, arm)
        self.assertTrue(0.0 < limit < 1e6)
        self.assertAlmostEqual(balance.balance_margin(body, limit, arm), 0.0, places=9)
        self.assertFalse(balance.is_stable(body, limit * 1.05, arm))
        self.assertTrue(balance.is_stable(body, limit * 0.95, arm))

    def test_holding_a_load_close_is_limited_by_the_back_not_by_balance(self):
        """สองเกณฑ์อยู่ร่วมกันจริง และเกณฑ์ไหนบีบก่อนขึ้นกับว่าถือไว้ไกลแค่ไหน"""
        body = B.body_of(person())
        torque_limit = capability.carry_capacity(body)
        near = balance.max_stable_load(body, K.CARRY_LEVER_ARM)
        self.assertGreater(near, torque_limit, "ถือใกล้ตัว หลังต้องเป็นตัวจำกัดก่อนสมดุล")
        far = balance.max_stable_load(body, 0.75)
        self.assertLess(far, near, "ยิ่งถือไกล สมดุลยิ่งบีบเร็วขึ้น")

    def test_a_longer_foot_makes_it_harder_to_tip_forward(self):
        small = B.body_of(person())
        big = copy.deepcopy(small)
        big.gen.height *= 1.2           # เท้ายาวขึ้นตามส่วนสูง
        self.assertGreater(balance.support_polygon(big)["front"],
                           balance.support_polygon(small)["front"])
        self.assertGreater(balance.balance_margin(big, 40.0),
                           balance.balance_margin(small, 40.0))


if __name__ == "__main__":
    unittest.main()
