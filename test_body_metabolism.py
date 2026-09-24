# -*- coding: utf-8 -*-
"""งานกล พลังงาน การหายใจ และอุณหภูมิกาย — Phase 5 (§20–23)

    python -m unittest test_body_metabolism -v

บัญชีที่ต้องปิดได้: งานกลหนึ่งจูลต้องเผาเชื้อเพลิงสี่จูล ส่วนที่เหลือกลายเป็นความร้อน
ทั้งหมด แล้วร่างต้องระบายมันทิ้ง ถ้าสามอย่างนี้ไม่ตรงกัน แปลว่ามีพลังงานหายหรืองอกที่ไหนสักแห่ง
"""
import contextlib
import io
import math
import pickle
import unittest

from tiandao import body as B
from tiandao import sim as S
from tiandao.body import constants as K, metabolism as MET
from tiandao.body.condition import Condition
from tiandao.models import Character


def quiet(fn, *a, **kw):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*a, **kw)


def person(cid=0, gender="ชาย", body_seed=7):
    ch = Character(cid=cid, name=f"ผู้ทดสอบ {cid}", world_id=0, dao="วิถีดาบ",
                   dao_tags=[], born_day=0, gender=gender)
    ch.body_seed = body_seed
    return ch


class WorkAndEnergyTests(unittest.TestCase):
    """งานกล -> ต้นทุนพลังงาน -> ความร้อน (§22)"""

    def test_the_energy_budget_closes(self):
        """เผาเท่าไร = งานที่ได้ + ความร้อนที่เกิด — ไม่มีพลังงานหายหรืองอก"""
        work = 5000.0
        burned = MET.metabolic_cost(work)
        heat = MET.heat_from_work(work)
        self.assertAlmostEqual(burned, work + heat, places=6)
        self.assertAlmostEqual(work / burned, K.MUSCLE_EFFICIENCY, places=9)

    def test_basal_rate_follows_kleibers_three_quarter_law(self):
        small, big = B.body_of(person(1)), B.body_of(person(2))
        if abs(small.mass - big.mass) < 1.0:
            self.skipTest("สองร่างนี้มวลใกล้กันเกินกว่าจะวัดความชัน")
        if small.mass > big.mass:
            small, big = big, small
        ratio = MET.basal_rate(big) / MET.basal_rate(small)
        self.assertAlmostEqual(ratio, (big.mass / small.mass) ** K.BMR_EXPONENT, places=9)
        # ตัวใหญ่กินมากกว่ารวมๆ แต่ **น้อยกว่าเมื่อเทียบต่อกิโลกรัม**
        self.assertGreater(MET.basal_rate(big), MET.basal_rate(small))
        self.assertLess(MET.basal_rate(big) / big.mass,
                        MET.basal_rate(small) / small.mass)

    def test_a_resting_adult_burns_a_plausible_amount(self):
        body = B.body_of(person())
        kcal = MET.basal_rate(body) * 86400.0 / 4184.0
        self.assertTrue(1100 < kcal < 2600, f"BMR {kcal:.0f} kcal/วัน อยู่นอกช่วงที่เป็นไปได้")

    def test_fat_is_the_reserve_that_decides_how_long_you_last(self):
        """คนอ้วนอดได้นานกว่า — โผล่จากองค์ประกอบร่างกาย ไม่ได้เขียนเป็นกฎ"""
        lean = B.body_of(person())
        import copy
        padded = copy.deepcopy(lean)
        padded.fat_mass *= 3.0
        padded.mass = (padded.bone_mass + padded.muscle_mass + padded.organ_mass
                       + padded.fat_mass)
        cond = Condition()
        self.assertGreater(MET.endurance_days(padded, cond),
                           MET.endurance_days(lean, cond))
        # และคลังไขมันต้องใหญ่กว่าคลังไกลโคเจนหลายสิบเท่า
        self.assertGreater(MET.fat_reserve(lean), MET.glycogen_capacity(lean) * 20)

    def test_spending_work_drains_the_glycogen_store(self):
        ch = person()
        before = ch.fuel
        B.spend(ch, 200_000.0)
        self.assertLess(ch.fuel, before)
        self.assertGreaterEqual(ch.fuel, 0.0)

    def test_an_empty_store_still_leaves_something_to_work_with(self):
        """ไกลโคเจนหมดไม่ได้แปลว่าขยับไม่ได้ — ร่างหันไปใช้ไขมันซึ่งช้ากว่า"""
        self.assertEqual(Condition(fuel=1.0).fuel_factor, 1.0)
        spent = Condition(fuel=0.0).fuel_factor
        self.assertAlmostEqual(spent, K.SPENT_FUEL_FLOOR, places=9)
        self.assertGreater(spent, 0.0)


class RespirationTests(unittest.TestCase):
    """การหายใจ (§20)"""

    def test_minute_ventilation_is_rate_times_tidal_volume(self):
        body = B.body_of(person())
        tidal = body.mass * K.TIDAL_VOLUME_PER_KG
        self.assertAlmostEqual(MET.minute_ventilation(body, 0.0),
                               K.RESP_RATE_REST * tidal, places=9)
        self.assertGreater(MET.minute_ventilation(body, 1.0),
                           MET.minute_ventilation(body, 0.0))

    def test_oxygen_demand_tracks_the_metabolic_rate(self):
        body = B.body_of(person())
        self.assertAlmostEqual(
            MET.oxygen_demand(body, 0.5),
            MET.metabolic_power(body, 0.5) * 60.0 / K.ENERGY_PER_LITRE_O2, places=9)

    def test_hard_work_on_lost_blood_runs_an_oxygen_debt(self):
        """จุดที่ระบบเลือดของเฟสก่อนมาเจอกับพลังงานของเฟสนี้"""
        body = B.body_of(person())
        self.assertEqual(MET.oxygen_debt(body, Condition(), 0.0), 0.0)
        strained = MET.oxygen_debt(body, Condition(blood=0.6), 1.0)
        self.assertGreater(strained, 0.0)
        self.assertLessEqual(strained, 1.0)


class TemperatureTests(unittest.TestCase):
    """อุณหภูมิกาย (§23)"""

    def test_the_equation_has_heat_capacity_in_it(self):
        """สเปกเขียน dT/dt = Q_เกิด − Q_ระบาย ซึ่งหน่วยเป็นวัตต์ ไม่ใช่เคลวินต่อวินาที

        ต้องหารด้วย m·c ผลคือค่าคงที่เวลา τ = m·c/(k·A) ซึ่งทำให้ร่างใหญ่เย็นช้ากว่า
        """
        small, big = B.body_of(person(1)), B.body_of(person(2))
        if small.mass > big.mass:
            small, big = big, small
        self.assertAlmostEqual(MET.heat_capacity(big), big.mass * K.BODY_SPECIFIC_HEAT,
                               places=6)
        tau_small = MET.heat_capacity(small) / MET.conductance(small)
        tau_big = MET.heat_capacity(big) / MET.conductance(big)
        self.assertGreater(tau_big, tau_small, "ร่างใหญ่ต้องเย็นช้ากว่า")

    def test_fat_insulates(self):
        """ไขมันเป็นทั้งเชื้อเพลิงและฉนวน — คนผอมที่วิ่งเร็วคือคนที่ตายก่อนในฤดูหนาว"""
        import copy
        lean = B.body_of(person())
        padded = copy.deepcopy(lean)
        padded.fat_mass *= 3.0
        padded.mass = (padded.bone_mass + padded.muscle_mass + padded.organ_mass
                       + padded.fat_mass)
        self.assertLess(MET.conductance(padded), MET.conductance(lean))
        self.assertGreater(MET.equilibrium_temp(padded, 5.0),
                           MET.equilibrium_temp(lean, 5.0))

    def test_a_living_body_defends_its_temperature(self):
        """ถ้าไม่มีการควบคุมเชิงรุก คนนั่งในอากาศ 24°C จะมีแกนกลาง 30°C แล้วตายทั้งโลก"""
        body = B.body_of(person())
        held = MET.equilibrium_temp(body, 24.0)
        self.assertGreater(held, 35.0, "ร่างต้องสู้กลับ ไม่ใช่เข้าสมดุลกับอากาศเฉยๆ")
        self.assertLess(held, 38.5)
        # แต่การสู้มีเพดาน — หนาวพอจะพ้นเพดานแล้วฟิสิกส์ชนะ
        self.assertLess(MET.equilibrium_temp(body, -20.0, clothing=0.0),
                        K.HYPOTHERMIA_BELOW)

    def test_every_season_is_survivable_when_dressed_for_it(self):
        body = B.body_of(person())
        for day in (30, 120, 210, 300):
            ambient, clothing = MET.climate_of(day)
            core = MET.equilibrium_temp(body, ambient, 0.0, clothing)
            self.assertEqual(MET.thermal_state(core), "ปกติ",
                             f"วันที่ {day}: อากาศ {ambient}°C -> แกนกลาง {core:.1f}°C")

    def test_wind_and_water_are_what_actually_kill(self):
        body = B.body_of(person())
        ambient, clothing = MET.climate_of(300)          # ฤดูหนาว
        calm = MET.equilibrium_temp(body, ambient, 0.0, clothing)
        windy = MET.equilibrium_temp(body, ambient, 0.0, clothing, wind=1.0)
        soaked = MET.equilibrium_temp(body, ambient, 0.0, clothing, wind=0.5, wet=True)
        self.assertLess(windy, calm)
        self.assertLess(soaked, windy)
        self.assertLessEqual(soaked, K.HYPOTHERMIA_DEATH)

    def test_temperature_steps_in_closed_form(self):
        body = B.body_of(person())
        one = MET.step_temperature(body, 30.0, 20.0, 5.0)
        many = 30.0
        for _ in range(500):
            many = MET.step_temperature(body, many, 20.0, 0.01)
        self.assertAlmostEqual(one, many, places=6)

    def test_thermal_penalty_is_zero_in_the_normal_band(self):
        self.assertEqual(MET.thermal_penalty(37.0), 0.0)
        self.assertEqual(MET.thermal_penalty(36.0), 0.0)
        self.assertGreater(MET.thermal_penalty(33.0), 0.0)
        self.assertGreater(MET.thermal_penalty(41.0), 0.0)
        self.assertLessEqual(MET.thermal_penalty(20.0), 1.0)


class NoFieldCollisionTests(unittest.TestCase):
    """บทเรียนที่ต้องไม่ซ้ำ — ประกาศฟิลด์ทับของเดิมโดยไม่รู้ตัว"""

    def test_the_old_energy_field_is_untouched(self):
        """`energy` (0–100) เป็นของระบบล่าอสูร/เหตุการณ์เมืองมาก่อน เฟสนี้ใช้ `fuel`

        ตอนเผลอประกาศ `energy` ซ้ำ ค่าเฉลี่ยทั้งโลกกลายเป็น 2.23 ซึ่งไม่ใช่ทั้งสองสเกล
        """
        import dataclasses
        fields = {f.name: f for f in dataclasses.fields(Character)}
        self.assertEqual(fields["energy"].default, 100.0)
        self.assertEqual(fields["fuel"].default, 1.0)
        src = io.open("tiandao/models.py", encoding="utf-8").read()
        self.assertEqual(src.count("\n    energy:"), 1, "ประกาศ energy ซ้ำอีกแล้ว")
        self.assertEqual(src.count("\n    fuel:"), 1)

    def test_no_dataclass_field_is_declared_twice(self):
        """กันบั๊กคลาสนี้ทั้งคลาส — เคยเกิดกับ hp/max_hp และเกือบเกิดกับ energy"""
        import collections
        import re
        src = io.open("tiandao/models.py", encoding="utf-8").read()
        for block in src.split("@dataclass")[1:]:
            body = block.split("\n\n\n")[0]
            names = re.findall(r"^    ([a-z_][a-z0-9_]*)\s*:", body, re.M)
            dupes = [n for n, c in collections.Counter(names).items() if c > 1]
            self.assertEqual(dupes, [], f"ฟิลด์ถูกประกาศซ้ำ: {dupes}")


class WorldTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sim = quiet(S.Sim, seed=7, tiers=3)
        quiet(cls.sim.run, 12000)
        cls.alive = [c for c in cls.sim.cast if c.alive]

    def test_everyone_keeps_a_liveable_core_temperature(self):
        temps = [c.core_temp for c in self.alive]
        self.assertTrue(all(K.HYPOTHERMIA_DEATH < t < K.HYPERTHERMIA_DEATH for t in temps))
        self.assertTrue(34.0 < sum(temps) / len(temps) < 38.5)

    def test_fuel_stays_inside_its_own_scale(self):
        self.assertTrue(all(0.0 <= c.fuel <= 1.0 for c in self.alive))

    def test_the_old_energy_system_still_runs_on_its_own_scale(self):
        vals = [c.energy for c in self.alive]
        self.assertTrue(all(0.0 <= v <= 100.0 for v in vals))
        self.assertGreater(max(vals), 1.0, "ระบบเดิมถูกทับด้วยสเกล 0–1 อีกแล้ว")

    def test_the_new_fields_survive_a_save(self):
        ch = self.alive[0]
        back = pickle.loads(pickle.dumps(ch))
        self.assertAlmostEqual(back.fuel, ch.fuel, places=12)
        self.assertAlmostEqual(back.core_temp, ch.core_temp, places=12)
        old = person(9)
        del old.__dict__["fuel"]
        del old.__dict__["core_temp"]
        back = pickle.loads(pickle.dumps(old))
        self.assertEqual((back.fuel, back.core_temp), (1.0, 37.0))


if __name__ == "__main__":
    unittest.main()
