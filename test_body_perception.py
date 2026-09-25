# -*- coding: utf-8 -*-
"""คำถามปิดของระบบตัดสินใจ และสภาพร่างกาย "ตามที่รู้สึก" — Phase 6 (§32–33)

    python -m unittest test_body_perception -v

สองเรื่องที่ต้องแยกกันให้ขาด: ร่างกายทำอะไรได้ (ฟิสิกส์ตัดสิน) กับเจ้าตัวคิดว่าทำอะไรได้
(ความรู้สึกตัดสิน) พรอมต์ TEST 10 บอกไว้ตรงๆ ว่าถ้าบาดเจ็บจริงเท่ากันแต่รู้สึกไม่เท่ากัน
**ความสามารถต้องเท่ากัน** ส่วนการตัดสินใจต่างกันได้ — เทสต์ในไฟล์นี้ยึดเส้นนั้น
"""
import random
import statistics
import unittest

from tiandao import body as B
from tiandao.body import capability as CAP
from tiandao.body import constants as K
from tiandao.body import injury as INJ
from tiandao.body import perception as P
from tiandao.body.condition import Condition
from tiandao.models import Character

GRAVITY = K.GRAVITY


def person(cid=0, gender="ชาย", body_seed=7):
    ch = Character(cid=cid, name=f"ผู้ทดสอบ {cid}", world_id=0, dao="วิถีดาบ",
                   dao_tags=[], born_day=0, gender=gender)
    ch.body_seed = body_seed
    return ch


def break_bone(ch, region, level=0.8):
    """ใส่กระดูกหักลงไปตรงๆ — เทสต์เรื่องผลของบาดเจ็บ ไม่ใช่เรื่องการเกิดบาดเจ็บ"""
    ch.injuries.setdefault(region, {})["bone"] = level
    return ch


# ============================================================ §32 คำถามปิด
class CapabilityQuestionTests(unittest.TestCase):
    """สิ่งที่ระบบตัดสินใจถามร่างกาย — ทุกคำตอบต้องมาจากแรงและมวล ไม่ใช่จาก HP"""

    def test_a_sound_body_can_do_everything(self):
        ch = person()
        self.assertTrue(B.can_stand(ch))
        self.assertTrue(B.can_run(ch))
        self.assertTrue(B.can_fight(ch))
        self.assertTrue(B.can_use_limb(ch, "left_arm"))

    def test_standing_is_decided_by_force_against_body_weight(self):
        """ยืนไม่ได้เพราะแรงขาไม่ถึงน้ำหนักตัว ไม่ใช่เพราะมีกฎว่า "ขาหัก = ล้ม" """
        ch = person(1)
        body = B.body_of(ch)
        break_bone(ch, "left_leg")
        break_bone(ch, "right_leg")
        cond = Condition.of(ch)
        ratio = body.leg_force(cond) / (body.mass * GRAVITY)
        self.assertLess(ratio, K.STAND_FORCE_MARGIN)       # เหตุ
        self.assertFalse(B.can_stand(ch))                  # ผล
        self.assertFalse(B.can_run(ch))                    # ยืนไม่ได้ก็วิ่งไม่ได้

    def test_one_broken_leg_still_stands_but_cannot_run(self):
        ch = break_bone(person(2), "left_leg")
        self.assertTrue(B.can_stand(ch))
        self.assertFalse(B.can_run(ch))
        # ข้างที่ดีต้องยังดีอยู่ — ความเสียหายไม่เกลี่ยข้ามข้าง
        self.assertLess(B.limb_function(ch, "left_leg"), K.LIMB_USABLE_MIN)
        self.assertEqual(B.limb_function(ch, "right_leg"), 1.0)

    def test_region_function_is_per_side_while_group_capacity_is_shared(self):
        """สองคำถามต่างกัน: "ยกของหนักได้เท่าไร" เกลี่ยสองข้าง "ใช้แขนซ้ายได้ไหม" ไม่เกลี่ย"""
        ch = break_bone(person(3), "right_arm")
        shared = INJ.capacity(ch.injuries, "arm")
        one_side = INJ.region_function(ch.injuries, "right_arm")
        self.assertGreater(shared, one_side)
        self.assertEqual(INJ.region_function(ch.injuries, "left_arm"), 1.0)
        self.assertFalse(B.can_use_limb(ch, "right_arm"))
        self.assertTrue(B.can_use_limb(ch, "left_arm"))

    def test_a_one_armed_fighter_still_fights(self):
        ch = break_bone(person(4), "right_arm")
        self.assertTrue(B.can_fight(ch))
        self.assertLess(CAP.fight_capacity(B.body_of(ch), Condition.of(ch)), 1.0)

    def test_the_unconscious_neither_stand_nor_fight(self):
        ch = person(5)
        ch.blood_frac = K.BLOOD_UNCONSCIOUS_BELOW - 0.05
        self.assertFalse(Condition.of(ch).conscious)
        self.assertFalse(B.can_stand(ch))
        self.assertFalse(B.can_fight(ch))

    def test_fight_capacity_is_measured_against_ones_own_sound_body(self):
        """คนตัวเล็กไม่ได้ "สู้ไม่ได้" เพราะเกิดมาตัวเล็ก — เกณฑ์เทียบกับตัวเองเสมอ"""
        for seed in (1, 5, 11, 23):
            ch = person(6, body_seed=seed)
            self.assertAlmostEqual(CAP.fight_capacity(B.body_of(ch)), 1.0, places=9)
            self.assertTrue(B.can_fight(ch))

    def test_escape_is_decided_by_speed_not_by_power(self):
        fast, slow = person(7, body_seed=3), person(8, body_seed=3)
        # ทำให้คนหนึ่งช้าลงจริงด้วยขาที่เจ็บ แล้วดูว่าใครหนีใครพ้น
        break_bone(slow, "left_leg", 0.5)
        v_fast, v_slow = B.estimated_max_speed(fast), B.estimated_max_speed(slow)
        self.assertGreater(v_fast, v_slow)
        self.assertAlmostEqual(B.speed_margin(fast, slow), v_fast - v_slow, places=9)
        self.assertTrue(B.can_escape(fast, [slow]))
        self.assertFalse(B.can_escape(slow, [fast]))
        # ไล่หลายคน: พ้นคนช้าแต่ไม่พ้นคนเร็ว = ไม่พ้น
        self.assertFalse(B.can_escape(slow, [slow, fast]))
        self.assertTrue(B.can_escape(fast, []))

    def test_the_capability_sheet_answers_in_si_units(self):
        caps = B.capabilities(person(9))
        for key in ("speed", "reaction", "carry", "strike", "fight", "effort", "arm", "leg",
                    "severity", "can_stand", "can_fight", "can_run", "conscious", "endurance",
                    "word"):
            self.assertIn(key, caps)
        self.assertTrue(K.RUN_SPEED_MIN <= caps["speed"] <= K.RUN_SPEED_MAX)
        self.assertTrue(0.10 <= caps["reaction"] <= 0.60)
        self.assertGreater(caps["carry"], 10.0)
        self.assertGreater(caps["strike"], 50.0)
        self.assertEqual(caps["severity"], 0.0)

    def test_the_capability_sheet_reads_the_condition_it_is_given(self):
        """ตารางความสามารถต้องเปลี่ยนตามสภาพที่ส่งเข้าไป ไม่ใช่ตามสภาพจริงอย่างเดียว"""
        ch = person(10)
        sound = B.capabilities(ch)
        tired = B.capabilities(ch, cond=Condition(fatigue=0.6))
        self.assertLess(tired["speed"], sound["speed"])
        self.assertLess(tired["effort"], sound["effort"])
        self.assertGreater(tired["reaction"], sound["reaction"])


# ============================================================ §33 สภาพที่รู้สึก
class SelfPerceptionTests(unittest.TestCase):
    """เจ้าตัวไม่ได้อ่านค่าจริงของตัวเอง — รู้ได้คร่าวๆ และผิดได้"""

    def bleeding(self, cid=20, blood=0.72):
        ch = person(cid)
        ch.blood_frac = blood
        return ch

    def grazed(self, cid=29):
        """เสียเลือดน้อย — ย่านที่ขอบ "ยังไม่หมดสติ" ไม่เข้ามาบีบการประเมิน"""
        return self.bleeding(cid, 0.95)

    def test_the_same_day_always_feels_the_same(self):
        ch = self.bleeding()
        a = P.perceive(ch, 100.0)
        b = P.perceive(ch, 100.0)
        self.assertEqual(a.blood, b.blood)
        self.assertEqual(a.fatigue, b.fatigue)

    def test_a_different_day_feels_different(self):
        ch = self.grazed()
        felt = {round(P.perceive(ch, d).blood, 6) for d in range(100, 140)}
        self.assertGreater(len(felt), 30)

    def test_the_typical_estimate_is_right_but_a_single_one_need_not_be(self):
        """มัธยฐานของการประเมินตรงกับความจริง (exp(σε) มัธยฐาน 1) แต่รายครั้งเพี้ยนได้มาก"""
        ch = self.grazed()
        actual = 1.0 - ch.blood_frac
        ratios = [(1.0 - P.perceive(ch, d).blood) / actual for d in range(2000)]
        self.assertAlmostEqual(statistics.median(ratios), 1.0, delta=0.03)
        self.assertGreater(max(ratios), 1.5)
        self.assertLess(min(ratios), 0.7)

    def test_bravery_underestimates_and_caution_overestimates(self):
        """วันเดียวกันใช้ ε ตัวเดียวกัน อคติจึงเรียงกันได้แน่นอน ไม่ใช่เรื่องของโชค"""
        ch = self.grazed()
        for day in range(50):
            brave = 1.0 - P.perceive(ch, day, bias=1.0).blood
            plain = 1.0 - P.perceive(ch, day, bias=0.0).blood
            afraid = 1.0 - P.perceive(ch, day, bias=-1.0).blood
            self.assertLess(brave, plain)
            self.assertLess(plain, afraid)

    def test_losing_blood_also_costs_the_judgement_of_how_bad_it_is(self):
        """สมองที่ขาดออกซิเจนประเมินตัวเองเพี้ยนขึ้น — ยิ่งใกล้ตายยิ่งไม่รู้ตัว"""
        sound = P.sigma("blood", Condition())
        hurt = P.sigma("blood", Condition(blood=0.60))
        self.assertGreater(hurt, sound)
        wide = P.band(self.bleeding(21, 0.60), 5.0)["blood"]
        narrow = P.band(self.bleeding(21, 0.90), 5.0)["blood"]
        self.assertGreater(wide[1] - wide[0], narrow[1] - narrow[0])

    def test_no_one_believes_himself_unconscious_while_standing_there(self):
        """ขอบของความเชื่อ: สัญญาณที่เถียงไม่ได้ (ยังรู้สึกตัวอยู่) เป็นข้อมูลที่เจ้าตัวมีเสมอ

        ถ้าไม่มีขอบนี้ หางของ log-normal จะสร้างคนที่เชื่อว่าตัวเองเสียเลือดไปครึ่งตัว
        ทั้งที่ยังยืนพูดอยู่ แล้วความสามารถ "ที่คิดว่ามี" จะกลายเป็นศูนย์ทั้งแผง
        """
        ch = self.bleeding(30, 0.80)
        self.assertTrue(Condition.of(ch).conscious)
        for day in range(300):
            felt = P.perceive(ch, day, bias=-1.0)
            self.assertTrue(felt.conscious)
            self.assertGreater(B.capabilities(ch, felt=felt)["effort"], 0.0)

    def test_the_felt_range_brackets_the_felt_value(self):
        ch = self.bleeding()
        felt = 1.0 - P.perceive(ch, 7.0).blood
        lo, hi = P.band(ch, 7.0)["blood"]
        self.assertLessEqual(lo, felt + 1e-9)
        self.assertGreaterEqual(hi, felt - 1e-9)

    def test_each_wound_is_misjudged_on_its_own(self):
        """รู้ว่าเจ็บ แต่เข้าใจผิดได้ว่าตรงไหนหนักกว่า — ความเพี้ยนแยกรายส่วน"""
        ch = person(22)
        break_bone(ch, "left_leg", 0.6)
        break_bone(ch, "right_arm", 0.6)
        flips = 0
        for day in range(200):
            felt = P.perceive(ch, day).injury
            if felt["right_arm"]["bone"] > felt["left_leg"]["bone"]:
                flips += 1
        self.assertGreater(flips, 10)
        self.assertLess(flips, 190)

    def test_perception_never_touches_the_real_body(self):
        ch = person(23)
        break_bone(ch, "chest", 0.4)
        before = {r: dict(t) for r, t in ch.injuries.items()}
        state = ch.injuries
        felt = P.perceive(ch, 3.0, bias=0.8)
        self.assertIsNot(felt.injury, state)
        self.assertEqual({r: dict(t) for r, t in ch.injuries.items()}, before)
        self.assertEqual(ch.blood_frac, 1.0)

    def test_a_sound_body_feels_sound(self):
        felt = P.perceive(person(24), 9.0, bias=-1.0)
        self.assertIsNone(felt.injury)
        self.assertEqual(felt.fatigue, 0.0)
        self.assertEqual(felt.blood, 1.0)
        self.assertEqual(P.describe(felt), "ปกติดี")

    def test_cold_never_feels_like_heat(self):
        ch = person(25)
        ch.core_temp = 34.0
        for day in range(100):
            self.assertLess(P.perceive(ch, day).core_temp, K.CORE_TEMP_NORMAL)
        ch.core_temp = 40.0
        for day in range(100):
            self.assertGreater(P.perceive(ch, day).core_temp, K.CORE_TEMP_NORMAL)

    def test_the_words_a_character_would_use(self):
        self.assertEqual(P.describe(Condition()), "ปกติดี")
        self.assertEqual(P.describe(Condition(fatigue=0.8)), "หมดแรง")
        self.assertEqual(P.describe(Condition(blood=0.4)), "จะไปแล้ว")
        self.assertEqual(B.felt_word(person(26)), "ปกติดี")

    def test_perception_does_not_disturb_the_worlds_random_stream(self):
        """ระบบใหม่ต้องไม่ขยับลำดับเลขสุ่มของโลก — ไม่งั้นโลกเดิมเดินไม่เหมือนเดิม"""
        ch = self.bleeding(27)
        random.seed(1234)
        before = random.getstate()
        P.perceive(ch, 11.0, bias=0.3)
        P.band(ch, 11.0)
        B.capabilities(ch)
        self.assertEqual(random.getstate(), before)

    def test_the_debug_view_shows_both_sides(self):
        ch = self.bleeding(28)
        out = P.explain(ch, 4.0, bias=1.0)
        self.assertLess(out["ที่รู้สึก"]["เลือดที่เสียไป"], out["ของจริง"]["เลือดที่เสียไป"])
        self.assertIn("blood", out["ความไม่แม่นตอนนี้"])


# ============================================================ TEST 10 (ครึ่งฝั่งฟิสิกส์)
class PerceptionDoesNotChangePhysicsTests(unittest.TestCase):
    """พรอมต์ TEST 10: บาดเจ็บจริงเท่ากัน + รู้สึกไม่เท่ากัน → ความสามารถจริงต้องเท่ากัน"""

    def setUp(self):
        self.a = break_bone(person(30, body_seed=13), "left_leg", 0.45)
        self.b = break_bone(person(30, body_seed=13), "left_leg", 0.45)

    def test_identical_injuries_give_identical_physical_capability(self):
        self.assertEqual(B.capabilities(self.a), B.capabilities(self.b))

    def test_feeling_different_does_not_move_a_single_newton(self):
        brave = B.felt(self.a, 50.0, bias=1.0)
        afraid = B.felt(self.b, 50.0, bias=-1.0)
        self.assertNotEqual(brave.injury["left_leg"]["bone"], afraid.injury["left_leg"]["bone"])
        # ความสามารถ "จริง" อ่านจากสภาพจริง — ไม่มีทางขึ้นกับความรู้สึก
        self.assertEqual(B.estimated_max_speed(self.a), B.estimated_max_speed(self.b))
        self.assertEqual(B.strike_energy(self.a), B.strike_energy(self.b))
        self.assertEqual(B.can_run(self.a), B.can_run(self.b))
        # แต่ความสามารถ "ที่คิดว่ามี" ต่างกัน — นี่คือสิ่งที่ใจใช้ตัดสินใจ
        body = B.body_of(self.a)
        self.assertGreater(CAP.max_running_speed(body, cond=brave),
                           CAP.max_running_speed(body, cond=afraid))

    def test_the_felt_speed_is_wrong_in_the_direction_of_the_bias(self):
        body = B.body_of(self.a)
        real = B.estimated_max_speed(self.a)
        brave = CAP.max_running_speed(body, cond=B.felt(self.a, 50.0, bias=1.0))
        afraid = CAP.max_running_speed(body, cond=B.felt(self.a, 50.0, bias=-1.0))
        self.assertGreater(brave, afraid)
        self.assertTrue(min(brave, afraid) <= real * 1.35)
        self.assertTrue(max(brave, afraid) >= real * 0.65)


if __name__ == "__main__":
    unittest.main(verbosity=2)
