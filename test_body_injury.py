# -*- coding: utf-8 -*-
"""บาดเจ็บเฉพาะส่วน การเสียหน้าที่ และการหาย — Phase 3 (§26–28, §34)

    python -m unittest test_body_injury -v

ข้อที่ตรงกับชุดทดสอบในสเปก (พรอมต์ §43):

    TEST 5  ความเร็วปะทะสองเท่า  ->  พลังงานจลน์สี่เท่า
    TEST 7  ขาบาดเจ็บ            ->  ความเร็ววิ่งต้องลด

TEST 6 (เสียเลือด) · TEST 8 (ความล้า) · TEST 10 (การรับรู้ร่างกายตัวเอง) ยังไม่มี —
ระบบที่ต้องใช้อยู่ใน Phase 5–7 การเขียนเทสต์ที่ผ่านโดยไม่มีระบบรองรับคือการอ้างว่ามีของที่ยังไม่มี
"""
import collections
import contextlib
import copy
import io
import pickle
import unittest

from tiandao import body as B
from tiandao import rules as R
from tiandao import sim as S
from tiandao.body import constants as K, injury as INJ
from tiandao.models import Character


def quiet(fn, *a, **kw):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*a, **kw)


def person(cid=0, gender="ชาย", body_seed=7):
    ch = Character(cid=cid, name=f"ผู้ทดสอบ {cid}", world_id=0, dao="วิถีดาบ",
                   dao_tags=[], born_day=0, gender=gender)
    ch.body_seed = body_seed
    return ch


class ImpactTests(unittest.TestCase):
    """พลังงานกระทบผ่านชั้นเนื้อเยื่อ (§26)"""

    def test_5_doubling_impact_speed_quadruples_the_energy(self):
        """TEST 5 ของสเปก — E = ½mv² ไม่ใช่สัดส่วนตรงกับความเร็ว"""
        slow = INJ.kinetic_energy(4.0, 6.0)
        fast = INJ.kinetic_energy(4.0, 12.0)
        self.assertAlmostEqual(fast / slow, 4.0, places=9)
        self.assertAlmostEqual(slow, 0.5 * 4.0 * 36.0, places=9)

    def test_energy_is_conserved_across_the_tissue_stack(self):
        """ที่ดูดซับรวมกับที่ทะลุถึงกระดูก ต้องเท่ากับที่ใส่เข้าไป"""
        ch = person()
        log = B.hurt(ch, 500.0, region="left_leg", key=("cons",))
        absorbed = sum(v["ดูดซับ (J)"] for v in log["ชั้นที่ดูดซับ"].values())
        self.assertAlmostEqual(absorbed + log["พลังงานถึงกระดูก (J)"], 500.0, delta=0.4)

    def test_a_thicker_fat_layer_shields_the_bone(self):
        """ความอ้วนดูดพลังงานได้มากกว่า — โผล่จากองค์ประกอบร่างกาย ไม่ได้เขียนเป็นกฎ"""
        lean = B.body_of(person())
        padded = copy.deepcopy(lean)
        padded.fat_mass *= 3.0
        padded.mass = (padded.bone_mass + padded.muscle_mass + padded.organ_mass
                       + padded.fat_mass)
        thin = INJ.apply_impact(lean, {}, 600.0, "left_leg")
        thick = INJ.apply_impact(padded, {}, 600.0, "left_leg")
        self.assertGreater(thick["ชั้นที่ดูดซับ"]["fat"]["ความหนา (mm)"],
                           thin["ชั้นที่ดูดซับ"]["fat"]["ความหนา (mm)"])
        self.assertLess(thick["พลังงานถึงกระดูก (J)"], thin["พลังงานถึงกระดูก (J)"])

    def test_the_same_energy_concentrated_is_far_more_dangerous(self):
        """คมดาบกับหมัดพลังงานเท่ากัน แต่พื้นที่สัมผัสและระยะหยุดต่างกันคนละเรื่อง"""
        body = B.body_of(person())
        fist = INJ.apply_impact(body, {}, 300.0, "left_leg", K.CONTACT_AREA_FIST,
                                None, K.IMPACT_STOP_DISTANCE)
        blade = INJ.apply_impact(body, {}, 300.0, "left_leg", K.CONTACT_AREA_BLADE,
                                 None, K.BLADE_STOP_DISTANCE)
        # เทียบที่ความเค้น ไม่ใช่ที่ความน่าจะเป็น — ความน่าจะเป็นมีเพดานที่ 1 พอค่าหนึ่งอิ่มตัว
        # แล้วอัตราส่วนก็ไม่มีความหมายอีก ส่วนความเค้นเป็นปริมาณทางฟิสิกส์ที่ไม่มีเพดาน
        #
        # อัตราส่วนที่ได้ (~3.6 เท่า) มาจากสองทางรวมกัน: ระยะหยุดสั้นกว่า 2.5 เท่า
        # (F = E/d) และพลังงานทะลุถึงกระดูกมากกว่า 1.44 เท่าเพราะพื้นที่แคบทำให้ชั้น
        # เนื้อเยื่อดูดซับได้น้อยลง — ไม่ใช่ตัวเลขที่ตั้งไว้ แต่เป็นผลคูณของสองกลไก
        self.assertGreater(blade["ความเค้นจากการดัด (MPa)"],
                           fist["ความเค้นจากการดัด (MPa)"] * 3)
        self.assertGreater(blade["พลังงานถึงกระดูก (J)"], fist["พลังงานถึงกระดูก (J)"])
        self.assertGreater(blade["โอกาสหัก"], fist["โอกาสหัก"])

    def test_a_short_fall_does_not_break_a_femur_but_a_long_one_does(self):
        """ระยะหยุดแรงเป็นคุณสมบัติของเหตุการณ์ — ใช้ค่าของหมัดกับการตกทำให้ตก 1 m ขาหัก"""
        body = B.body_of(person())
        low = INJ.fall_impact(body, {}, 1.0, "left_leg")
        high = INJ.fall_impact(body, {}, 6.0, "left_leg")
        self.assertLess(low["โอกาสหัก"], 0.10, "ตกหนึ่งเมตรไม่ควรหักกระดูกต้นขา")
        self.assertGreater(high["โอกาสหัก"], 0.90, "ตกหกเมตรควรหักแน่นอน")

    def test_a_strike_gets_its_energy_from_the_arm_not_from_a_stat(self):
        ch = person()
        body = B.body_of(ch)
        expected = (body.endpoint_force("arm") * body.gen.arm_length
                    * K.STRIKE_STROKE_RATIO)
        self.assertAlmostEqual(B.strike_energy(ch), expected, places=9)
        self.assertTrue(60.0 < B.strike_energy(ch) < 500.0,
                        "พลังหมัดอยู่นอกช่วงที่เป็นไปได้")


class FunctionLossTests(unittest.TestCase):
    """บาดเจ็บต้องลดความสามารถ **เฉพาะส่วน** (§27–28)"""

    def test_7_a_leg_injury_slows_running_down(self):
        """TEST 7 ของสเปก"""
        ch = person()
        before = B.estimated_max_speed(ch)
        B.hurt(ch, 600.0, region="left_leg", key=("t7",))
        after = B.estimated_max_speed(ch)
        self.assertLess(after, before)
        self.assertGreater(after, 0.0, "เจ็บขาแล้วยังต้องขยับได้ ไม่ใช่หยุดนิ่ง")

    def test_an_arm_injury_does_not_slow_running(self):
        ch = person()
        before = B.estimated_max_speed(ch)
        B.hurt(ch, 600.0, region="right_arm", key=("arm",))
        self.assertAlmostEqual(B.estimated_max_speed(ch), before, places=9,
                               msg="เจ็บแขนไม่ควรทำให้วิ่งช้าลง")

    def test_an_arm_injury_weakens_the_punch(self):
        ch = person()
        before = B.strike_energy(ch)
        B.hurt(ch, 600.0, region="right_arm", key=("punch",))
        self.assertLess(B.strike_energy(ch), before)

    def test_a_head_injury_slows_reaction_but_not_leg_force(self):
        ch = person()
        speed, reaction = B.estimated_max_speed(ch), B.reaction_time(ch)
        B.hurt(ch, 900.0, region="head", key=("head",))
        self.assertGreater(B.reaction_time(ch), reaction)
        self.assertAlmostEqual(B.estimated_max_speed(ch), speed, places=9)

    def test_function_never_reaches_zero(self):
        ch = person()
        for i in range(8):
            B.hurt(ch, 5000.0, region="left_leg", key=("crush", i))
            B.hurt(ch, 5000.0, region="right_leg", key=("crush2", i))
        self.assertGreaterEqual(INJ.capacity(ch.injuries, "leg"), K.MIN_FUNCTION)
        self.assertGreater(B.estimated_max_speed(ch), 0.0)

    def test_an_injured_body_is_weaker_in_the_power_formula(self):
        sim = quiet(S.Sim, seed=7, tiers=2)
        ch = sim.living_in(0)[0]
        before = R.power(ch, sim.worlds[0])
        B.hurt(ch, 900.0, region="left_leg", key=("pow",))
        self.assertLess(R.power(ch, sim.worlds[0]), before)


class HealingTests(unittest.TestCase):
    """บาดเจ็บที่ไม่มีวันหายคือระบบที่พังในระยะยาว (§34)"""

    def state(self):
        return {"left_leg": {"skin": 1.0, "fat": 1.0, "muscle": 1.0, "bone": 0.8}}

    def test_damage_decays_at_its_own_half_life(self):
        for tissue, half in K.HEAL_HALF_LIFE_DAYS.items():
            st = {"left_leg": {tissue: 1.0}}
            INJ.heal(st, half)
            self.assertAlmostEqual(st["left_leg"][tissue], 0.5, places=6,
                                   msg=f"{tissue} ไม่หายครึ่งทางที่ครึ่งชีวิตของมัน")

    def test_skin_heals_faster_than_bone(self):
        st = self.state()
        INJ.heal(st, 30.0)
        self.assertLess(st["left_leg"]["skin"], st["left_leg"]["bone"])

    def test_healing_is_closed_form_so_step_size_does_not_matter(self):
        """เอนจินนี้กระโดดข้ามเวลาเป็นวัน ผลต้องไม่ขึ้นกับว่าแบ่งช่วงเวลาละเอียดแค่ไหน"""
        one, many = self.state(), self.state()
        INJ.heal(one, 90.0)
        for _ in range(90):
            INJ.heal(many, 1.0)
        for tissue in ("muscle", "bone"):
            self.assertAlmostEqual(one["left_leg"][tissue], many["left_leg"][tissue],
                                   places=9)

    def test_a_fully_healed_region_leaves_nothing_in_the_save(self):
        st = self.state()
        INJ.heal(st, 4000.0)
        self.assertEqual(st, {}, "หายสนิทแล้วต้องไม่แบกเศษไว้ในเซฟ")

    def test_a_partially_healed_region_can_be_hurt_again(self):
        """heal() ลบคีย์ที่หายสนิท — apply_impact ต้องทนคีย์ไม่ครบ (เคยเป็น KeyError จริง)"""
        ch = person()
        B.hurt(ch, 400.0, region="left_leg", key=("h1",))
        INJ.heal(ch.injuries, 200.0)
        B.hurt(ch, 400.0, region="left_leg", key=("h2",))
        self.assertIn("left_leg", ch.injuries)

    def test_the_world_heals_people_as_time_passes(self):
        sim = quiet(S.Sim, seed=7, tiers=2)
        ch = sim.living_in(0)[0]
        B.hurt(ch, 900.0, region="left_leg", key=("w",))
        before = INJ.severity(ch.injuries)
        R.age_and_decay(sim, ch, sim.worlds[0], 365, sim.rng)
        self.assertLess(INJ.severity(ch.injuries), before,
                        "ผ่านไปหนึ่งปีแล้วบาดแผลต้องเบาลง")


class DeterminismTests(unittest.TestCase):
    def test_the_same_blow_always_lands_the_same_way(self):
        a, b = person(5), person(5)
        log_a = B.hurt(a, 500.0, key=("same", 1))
        log_b = B.hurt(b, 500.0, key=("same", 1))
        self.assertEqual(log_a["ส่วน"], log_b["ส่วน"])
        self.assertEqual(a.injuries, b.injuries)

    def test_hurting_people_never_moves_the_world_rng(self):
        sim = quiet(S.Sim, seed=7, tiers=2)
        before = sim.rng.getstate()
        for i, ch in enumerate(sim.living_in(0)[:40]):
            B.hurt(ch, 700.0, key=("r", i))
        self.assertEqual(sim.rng.getstate(), before)

    def test_region_choice_follows_surface_area(self):
        """ขาสองข้างกินพื้นที่ผิว 44% หัวแค่ 7% — ส่วนกว้างต้องโดนบ่อยกว่าจริง"""
        hits = collections.Counter(INJ.pick_region("x", i) for i in range(4000))
        self.assertGreater(hits["left_leg"] + hits["right_leg"], hits["head"] * 3)
        self.assertEqual(set(hits) - set(INJ.REGIONS), set())

    def test_injuries_survive_a_save_and_old_saves_start_clean(self):
        ch = person(3)
        B.hurt(ch, 600.0, region="left_leg", key=("save",))
        self.assertEqual(pickle.loads(pickle.dumps(ch)).injuries, ch.injuries)
        old = person(4)
        del old.__dict__["injuries"]
        self.assertEqual(pickle.loads(pickle.dumps(old)).injuries, {})


class InjuryInTheWorldTests(unittest.TestCase):
    """ระบบต้องทำงานในซิมจริง ไม่ใช่เฉพาะตอนถูกเรียกด้วยมือ"""

    @classmethod
    def setUpClass(cls):
        cls.sim = quiet(S.Sim, seed=7, tiers=3)
        quiet(cls.sim.run, 12000)
        cls.alive = [c for c in cls.sim.cast if c.alive]

    def test_losing_fights_actually_injures_people(self):
        self.assertTrue([c for c in self.alive if c.injuries],
                        "เดินโลกมาหมื่นสองพันเหตุการณ์แล้วไม่มีใครเจ็บเลย")

    def test_most_people_are_not_crippled(self):
        """บาดเจ็บต้องมีความหมายแต่ไม่กลืนโลก — สมดุลระหว่างการเกิดใหม่กับการหาย"""
        share = sum(1 for c in self.alive if c.injuries) / len(self.alive)
        self.assertLess(share, 0.60, f"มีคนเจ็บ {share:.0%} ของโลก — มากเกินไป")
        legs = [INJ.capacity(c.injuries, "leg") for c in self.alive]
        self.assertGreater(sum(legs) / len(legs), 0.90, "ขาของคนทั้งโลกแย่เกินไป")

    def test_someone_is_hurt_badly_enough_to_matter(self):
        """ถ้าไม่มีใครเจ็บหนักเลย ระบบก็ไม่ได้ทำอะไรนอกจากเพิ่มตัวเลข"""
        worst = min((INJ.capacity(c.injuries, "leg") for c in self.alive), default=1.0)
        self.assertLess(worst, 0.85, "ไม่มีใครเจ็บหนักพอจะกระทบความสามารถจริง")

    def test_damage_stays_inside_its_own_bounds(self):
        for ch in self.alive:
            for region, tissues in ch.injuries.items():
                self.assertIn(region, INJ.REGIONS)
                for tissue, level in tissues.items():
                    self.assertGreaterEqual(level, 0.0)
                    self.assertLessEqual(level, 1.0, f"{region}/{tissue} = {level}")


if __name__ == "__main__":
    unittest.main()
