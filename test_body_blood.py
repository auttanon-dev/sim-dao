# -*- coding: utf-8 -*-
"""เลือด การไหลเวียน และความล้า — Phase 4 (§8, §16–19)

    python -m unittest test_body_blood -v

ข้อที่ตรงกับชุดทดสอบในสเปก (พรอมต์ §43):

    TEST 6  ปริมาตรเลือดลด   ->  สมรรถภาพต้องลด
    TEST 8  ความล้าเพิ่ม      ->  แรงที่เรียกใช้ได้ต้องลด

TEST 10 (สภาพจริงเท่ากันแต่การรับรู้ต่างกัน) ยังไม่มี — อยู่ Phase 7 พร้อมการต่อกับ
Decision Engine เพราะต้องมีฝั่งที่ "รับรู้" ก่อนจึงจะแยกจากฝั่งที่ "เป็นจริง" ได้
"""
import contextlib
import io
import math
import pickle
import unittest

from tiandao import body as B
from tiandao import sim as S
from tiandao.body import capability, circulation as CIRC, constants as K
from tiandao.body.condition import Condition, resolve
from tiandao.models import Character


def quiet(fn, *a, **kw):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*a, **kw)


def person(cid=0, gender="ชาย", body_seed=7):
    ch = Character(cid=cid, name=f"ผู้ทดสอบ {cid}", world_id=0, dao="วิถีดาบ",
                   dao_tags=[], born_day=0, gender=gender)
    ch.body_seed = body_seed
    return ch


class SpecTests(unittest.TestCase):
    def test_6_losing_blood_costs_performance(self):
        """TEST 6 ของสเปก"""
        ch = person()
        full = B.estimated_max_speed(ch)
        ch.blood_frac = 0.70
        bled = B.estimated_max_speed(ch)
        self.assertLess(bled, full)
        self.assertGreater(B.reaction_time(ch), 0.0)
        ch.blood_frac = 0.55
        self.assertLess(B.estimated_max_speed(ch), bled, "ยิ่งเสียเลือดยิ่งแย่ลง")

    def test_8_fatigue_cuts_the_force_a_muscle_can_deliver(self):
        """TEST 8 ของสเปก"""
        body = B.body_of(person())
        rested = body.leg_force(Condition(fatigue=0.0))
        tired = body.leg_force(Condition(fatigue=0.5))
        spent = body.leg_force(Condition(fatigue=1.0))
        self.assertAlmostEqual(tired / rested, 0.5, places=6)
        self.assertAlmostEqual(spent, 0.0, places=9)


class CirculationTests(unittest.TestCase):
    """สมการไหลเวียน (§16–19)"""

    def test_blood_volume_comes_from_body_mass(self):
        for cid in range(20):
            body = B.body_of(person(cid))
            self.assertAlmostEqual(CIRC.blood_volume(body),
                                   body.mass * K.BLOOD_VOLUME_PER_KG, places=12)
        # ร่างอ้างอิงควรมีเลือดราวห้าลิตร ซึ่งเป็นช่วงของผู้ใหญ่จริง
        self.assertTrue(3.0 < CIRC.blood_volume(B.body_of(person())) < 7.0)

    def test_cardiac_output_is_rate_times_stroke_volume(self):
        body, cond = B.body_of(person()), Condition()
        self.assertAlmostEqual(
            CIRC.cardiac_output(body, cond, 0.4),
            CIRC.heart_rate(body, cond, 0.4) * CIRC.stroke_volume(body, cond), places=12)

    def test_the_heart_speeds_up_to_compensate_for_lost_blood(self):
        body = B.body_of(person())
        calm = CIRC.heart_rate(body, Condition(blood=1.0))
        bled = CIRC.heart_rate(body, Condition(blood=0.7))
        self.assertGreater(bled, calm)
        self.assertLessEqual(bled, K.HEART_RATE_MAX)

    def test_oxygen_delivery_would_fall_quadratically_but_the_heart_claws_it_back(self):
        """DO2 ลดสองทาง (ปริมาตรต่อครั้ง × ความเข้มข้น) จึงควรเป็น blood² = 0.25 ที่เลือดครึ่ง
        แต่หัวใจเร่งชดเชย ผลจริงจึงอยู่ระหว่าง blood² กับ blood — นั่นคือประเด็นของแบบจำลอง
        """
        body = B.body_of(person())
        full = CIRC.oxygen_delivery(body, Condition(blood=1.0))
        half = CIRC.oxygen_delivery(body, Condition(blood=0.5))
        self.assertLess(half / full, 1.0, "เสียเลือดแล้วออกซิเจนต้องลด")
        self.assertGreater(half / full, 0.25, "หัวใจต้องชดเชยได้บ้าง ไม่ใช่ลดตาม blood² เต็มๆ")
        # ถ้าหัวใจไม่เร่งเลย จะเป็นกำลังสองพอดี — ตรวจพจน์นั้นแยกเพื่อยืนยันว่าสูตรถูก
        flat = (CIRC.stroke_volume(body, Condition(blood=0.5)) * 0.5
                / (CIRC.stroke_volume(body, Condition(blood=1.0)) * 1.0))
        self.assertAlmostEqual(flat, 0.25, places=9)

    def test_mild_blood_loss_is_compensated_but_severe_is_not(self):
        self.assertEqual(Condition(blood=0.95).oxygen_factor, 1.0)
        self.assertEqual(Condition(blood=K.BLOOD_COMPENSATED_ABOVE).oxygen_factor, 1.0)
        mid = Condition(blood=0.70).oxygen_factor
        self.assertTrue(0.0 < mid < 1.0)
        self.assertEqual(Condition(blood=K.BLOOD_FATAL_BELOW).oxygen_factor, 0.0)

    def test_consciousness_has_its_own_threshold_above_death(self):
        """มีช่วงที่หมดสติแต่ยังไม่ตาย — ช่องให้คนอื่นช่วยได้ทัน"""
        self.assertTrue(Condition(blood=0.70).conscious)
        self.assertFalse(Condition(blood=0.55).conscious)
        self.assertLess(K.BLOOD_DEATH_BELOW, K.BLOOD_UNCONSCIOUS_BELOW)


class BleedingTests(unittest.TestCase):
    """เลือดออกและการแข็งตัว (§18)"""

    def test_no_wound_means_no_bleeding(self):
        self.assertEqual(B.bleeding(person()), 0.0)

    def test_a_wound_that_tears_vessels_bleeds(self):
        ch = person()
        B.hurt(ch, 700.0, region="left_leg", key=("bleed",))
        self.assertGreater(ch.injuries["left_leg"].get("vessel", 0.0), 0.0)
        self.assertGreater(B.bleeding(ch), 0.0)

    def test_the_flow_slows_as_the_wound_clots(self):
        """อัตราเลือดออกเป็นสถานะที่สลายตัวเอง — เรียกกี่ครั้งก็ได้ผลเท่ากัน"""
        ch = person()
        B.hurt(ch, 700.0, region="left_leg", key=("clotting",))
        opened = B.bleeding(ch)
        B.tick(ch, math.log(2.0) / K.CLOT_RATE_PER_DAY)
        self.assertAlmostEqual(B.bleeding(ch), opened / 2.0, places=6)

    def test_a_harder_blow_past_the_fracture_point_still_matters(self):
        """ความเสียหายของกระดูกอิ่มตัว แต่ความรุนแรงที่เกินเกณฑ์ต้องไปลงที่เนื้อเยื่อรอบข้าง

        ตอนยังไม่มีตัวคูณนี้ แรง 400 J กับ 1500 J ให้หลอดเลือดฉีกเท่ากันเป๊ะ
        """
        mild, hard = person(1), person(2)
        B.hurt(mild, 450.0, region="left_leg", key=("m",))
        B.hurt(hard, 1400.0, region="left_leg", key=("h",))
        self.assertGreater(hard.injuries["left_leg"]["vessel"],
                           mild.injuries["left_leg"]["vessel"])

    def test_clotting_makes_the_total_loss_finite(self):
        """แผลปิดตัวเอง ปริมาณที่เสียจึงลู่เข้าค่าหนึ่ง ไม่ไหลจนหมดตัวเสมอ"""
        ch = person()
        B.hurt(ch, 700.0, region="left_leg", key=("clot",))
        B.tick(ch, 400.0)
        self.assertGreater(ch.blood_frac, 0.0)

    def test_a_femur_fracture_costs_about_a_quarter_of_the_blood(self):
        """เทียบกับของจริง (1–1.5 ลิตรจาก 5 ลิตร) — ตอนตั้งค่าผิดเคยเสียแค่ 2%"""
        ch = person()
        B.hurt(ch, 700.0, region="left_leg", key=("femur",))
        ch.injuries["left_leg"]["bone"] = K.FRACTURE_DAMAGE
        start = ch.blood_frac
        B.tick(ch, 3.0)
        lost = start - ch.blood_frac
        self.assertGreater(lost, 0.10, f"เสียเลือดแค่ {lost:.1%} — น้อยเกินจะมีความหมาย")

    def test_the_world_kills_people_who_bleed_out(self):
        sim = quiet(S.Sim, seed=7, tiers=2)
        ch = sim.living_in(0)[0]
        ch.blood_frac = K.BLOOD_DEATH_BELOW - 0.02
        quiet(lambda: __import__("tiandao.rules", fromlist=["x"])
              .age_and_decay(sim, ch, sim.worlds[0], 1, sim.rng))
        self.assertFalse(ch.alive)
        self.assertIn("เลือด", ch.death_cause)


class FatigueTests(unittest.TestCase):
    """ความล้า (§8)"""

    def test_fatigue_approaches_one_without_ever_passing_it(self):
        ch = person()
        for _ in range(50):
            B.exert(ch, 1.0)
        self.assertLess(ch.fatigue, 1.0)
        self.assertGreater(ch.fatigue, 0.9)

    def test_the_first_effort_tires_more_than_a_later_one(self):
        ch = person()
        first = B.exert(ch, 1.0)
        second = B.exert(ch, 1.0) - first
        self.assertLess(second, first)

    def test_rest_clears_fatigue_at_its_half_life(self):
        ch = person()
        ch.fatigue = 1.0
        B.tick(ch, math.log(2.0) / K.FATIGUE_RECOVERY_RATE)
        self.assertAlmostEqual(ch.fatigue, 0.5, places=6)


class ConditionTests(unittest.TestCase):
    """วัตถุสภาพร่างกายที่รวมทุกอย่างไว้ที่เดียว"""

    def test_fatigue_and_oxygen_multiply_rather_than_add(self):
        cond = Condition(fatigue=0.5, blood=0.70)
        self.assertAlmostEqual(cond.effort_factor,
                               0.5 * cond.oxygen_factor, places=12)
        self.assertGreater(cond.effort_factor, 0.0, "สองอย่างรวมกันไม่ควรกลายเป็นศูนย์")

    def test_defaults_mean_a_whole_body(self):
        cond = Condition()
        self.assertEqual((cond.fatigue, cond.blood, cond.injury), (0.0, 1.0, None))
        self.assertEqual(cond.effort_factor, 1.0)
        self.assertIs(resolve(None), B.condition.HEALTHY)

    def test_passing_a_bare_number_is_refused_loudly(self):
        """ลายเซ็นเดิมรับ fatigue เป็นทศนิยม ถ้าโค้ดเก่าหลุดมาต้องดัง ไม่ใช่เงียบแล้วผิด"""
        with self.assertRaises(TypeError):
            resolve(0.5)
        with self.assertRaises(TypeError):
            capability.jump_height(B.body_of(person()), 0.5)

    def test_it_reads_the_character_straight(self):
        ch = person()
        ch.fatigue, ch.blood_frac = 0.3, 0.8
        cond = Condition.of(ch)
        self.assertEqual((cond.fatigue, cond.blood), (0.3, 0.8))


class IntegrationTests(unittest.TestCase):
    def test_one_long_step_matches_many_short_ones(self):
        """เอนจินกระโดดข้ามเวลาเป็นวัน ผลต้องไม่ขึ้นกับว่าแบ่งละเอียดแค่ไหน

        ความล้าและอัตราเลือดออกเป็นเลขชี้กำลังล้วน จึงตรงกัน **เป๊ะ** ส่วนปริมาตรเลือด
        ต่างได้เล็กน้อยเพราะพจน์ความดัน (เลือดพร่องแล้วไหลช้าลง) ถูกประเมินถี่ขึ้นเมื่อ
        แบ่งย่อย — นั่นคือฟิสิกส์จริงของการป้อนกลับ ไม่ใช่ความคลาดเคลื่อนของวิธีอินทิเกรต
        ตอนที่การแข็งตัวยังไม่ถูกจำเป็นสถานะ ช่องว่างนี้อยู่ที่ 29% ไม่ใช่ 3%
        """
        a, b = person(1), person(1)
        for ch in (a, b):
            B.hurt(ch, 700.0, region="left_leg", key=("step",))
            ch.fatigue = 0.9
        B.tick(a, 60.0)
        for _ in range(60):
            B.tick(b, 1.0)
        self.assertAlmostEqual(a.fatigue, b.fatigue, places=9)
        self.assertAlmostEqual(a.bleed, b.bleed, places=9)
        self.assertAlmostEqual(a.blood_frac, b.blood_frac, delta=0.05)

    def test_the_new_fields_survive_a_save_and_old_saves_start_whole(self):
        ch = person()
        ch.fatigue, ch.blood_frac = 0.4, 0.7
        back = pickle.loads(pickle.dumps(ch))
        self.assertEqual((back.fatigue, back.blood_frac), (0.4, 0.7))
        old = person(2)
        del old.__dict__["fatigue"]
        del old.__dict__["blood_frac"]
        back = pickle.loads(pickle.dumps(old))
        self.assertEqual((back.fatigue, back.blood_frac), (0.0, 1.0))

    def test_the_world_reaches_a_liveable_equilibrium(self):
        sim = quiet(S.Sim, seed=7, tiers=3)
        quiet(sim.run, 12000)
        alive = [c for c in sim.cast if c.alive]
        self.assertGreater(len(alive), 100)
        blood = sorted(c.blood_frac for c in alive)
        self.assertGreater(blood[len(blood) // 2], 0.95, "คนครึ่งโลกเลือดพร่อง")
        self.assertLess(min(blood), 1.0, "ไม่มีใครเสียเลือดเลย — ระบบไม่ได้ทำงาน")
        self.assertTrue(all(c.blood_frac >= 0.0 for c in alive))
        self.assertTrue(all(0.0 <= c.fatigue <= 1.0 for c in alive))

    def test_bleeding_out_becomes_a_real_cause_of_death(self):
        sim = quiet(S.Sim, seed=7, tiers=3)
        quiet(sim.run, 12000)
        bled = [c for c in sim.cast if not c.alive and "เลือด" in (c.death_cause or "")]
        self.assertTrue(bled, "ไม่มีใครตายเพราะเสียเลือดเลย — ทางตายนี้ไม่ได้ทำงาน")
        dead = [c for c in sim.cast if not c.alive]
        self.assertLess(len(bled) / len(dead), 0.35,
                        "เสียเลือดกลายเป็นสาเหตุการตายหลักของโลก — มากเกินไป")


if __name__ == "__main__":
    unittest.main()
