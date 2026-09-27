# -*- coding: utf-8 -*-
"""ตั้งครรภ์เป็นกระบวนการ (แบบ §7.2) และเมืองกับเจ้าเมืองอยู่ในเซฟ (เซฟรุ่น 15)

    python -m unittest test_pregnancy -v
"""
import contextlib
import io
import os
import pickle
import tempfile
import unittest
from unittest import mock

from tiandao import body as BODY
from tiandao import config as C
from tiandao import events as E
from tiandao import food as FOOD
from tiandao import persist as PS
from tiandao import sim as S

BIRTH = next(e for e in E.EVENT_TABLE if e["kind"] == "กำเนิดทายาท")


def quiet(fn, *a, **kw):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*a, **kw)


class PregnancyTests(unittest.TestCase):
    def setUp(self):
        self.sim = quiet(S.Sim, seed=5)
        self.sim.day = 1000
        self.world = self.sim.world(0)
        adults = [c for c in self.sim.living_in(0) if c.sentient and 20 <= c.age(self.sim.day) <= 40]
        self.father = next(c for c in adults if c.gender == "ชาย")
        self.mother = next(c for c in adults if c.gender == "หญิง")
        self.world.n_alive = 0                              # แดนยังไม่เต็ม ตั้งครรภ์ได้แน่นอน

    def conceive(self):
        return quiet(self.sim.resolve, BIRTH, self.father, self.mother, self.world, 30, self.sim.rng)[0]

    def test_a_child_is_born_where_the_mother_is_after_the_gestation(self):
        before = len(self.sim.cast)
        self.assertEqual(self.conceive(), "ตั้งครรภ์")
        self.assertEqual(len(self.sim.cast), before, "ยังไม่มีเด็กจนกว่าจะคลอด")
        p = self.mother.pregnancy
        self.assertEqual((p.kind, p.end_day - p.start_day), ("pregnancy", C.GESTATION_DAYS))
        self.mother.place = (self.father.place + 1) % 5
        self.sim.day = p.end_day
        quiet(self.sim.check_processes)
        child = self.sim.cast[before]
        self.assertEqual((child.parents, child.place, child.age(self.sim.day)),
                         ([self.father.cid, self.mother.cid], self.mother.place, 0))
        self.assertEqual(child.guardian, self.mother.cid)
        self.assertIsNone(self.mother.pregnancy)
        self.assertEqual(self.mother.postpartum_until, self.sim.day + C.POSTPARTUM_DAYS)
        born = [e for e in self.sim.log if e.kind == "กำเนิดทายาท" and e.outcome == "กำเนิด"]
        self.assertEqual(len(born), 1)
        self.assertEqual(str(born[0].deltas["child_id"]), str(child.cid))

    def test_no_second_conception_while_pregnant_or_recovering(self):
        self.conceive()
        self.assertEqual(self.conceive(), "ยังไม่มีทายาท")
        self.sim.day = self.mother.pregnancy.end_day
        quiet(self.sim.check_processes)
        self.assertEqual(self.conceive(), "ยังไม่มีทายาท", "ยังพักฟื้นหลังคลอด")
        self.sim.day += C.POSTPARTUM_DAYS
        self.assertEqual(self.conceive(), "ตั้งครรภ์")

    def test_a_pregnant_mother_eats_more(self):
        plain = FOOD.ration(self.mother, self.sim.day)
        self.conceive()
        self.assertAlmostEqual(FOOD.ration(self.mother, self.sim.day), plain * (1 + C.PREGNANCY_FOOD_EXTRA))

    def test_severe_injury_starvation_and_death_end_the_pregnancy(self):
        before = len(self.sim.cast)
        self.conceive()
        with mock.patch.object(BODY, "can_fight", return_value=False):
            quiet(self.sim.check_processes)
        self.assertIsNone(self.mother.pregnancy)
        self.sim.day += C.POSTPARTUM_DAYS
        self.conceive()
        self.mother.hunger_days = C.PREGNANCY_STARVE_DAYS
        quiet(self.sim.check_processes)
        self.assertIsNone(self.mother.pregnancy)
        self.mother.hunger_days = 0
        self.sim.day += C.POSTPARTUM_DAYS
        self.conceive()
        quiet(self.sim.kill, self.mother, "ทดสอบ")
        self.assertIsNone(self.mother.pregnancy)
        stats = self.sim.process_stats
        self.assertEqual((stats["pregnancy:บาดเจ็บสาหัส"], stats["pregnancy:อดอาหาร"],
                          stats["pregnancy:มารดาเสียชีวิต"]), (1, 1, 1))
        self.assertEqual(len(self.sim.cast), before, "ไม่มีเด็กเกิดจากครรภ์ที่จบก่อนกำหนด")


class CityTests(unittest.TestCase):
    def test_each_world_has_its_own_rulers_and_they_survive_a_save(self):
        a = quiet(S.Sim, seed=5)
        quiet(a.run, 50)
        b = quiet(S.Sim, seed=6)
        quiet(b.run, 50)
        rulers = [c["ruler_cid"] for c in a.cities]
        self.assertTrue(all(r >= 0 for r in rulers))
        a.cities[0]["ruler_cid"] = -1                          # สองโลกไม่แชร์ state เมืองกัน (เดิมแก้ config.CITIES ร่วม)
        self.assertEqual(b.cities[0]["ruler_cid"], rulers[0])
        a.cities[0]["ruler_cid"] = rulers[0]
        self.assertNotIn("ruler_cid", C.CITIES[0], "config.CITIES ไม่ถูกแก้อีก")
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "w.save")
            PS.save_sim(a, path)
            back = PS.load_sim(path)
        self.assertEqual([c["ruler_cid"] for c in back.cities], rulers)

    def test_a_version_14_save_finds_its_rulers_by_title_without_moving_the_rng(self):
        sim = quiet(S.Sim, seed=5)
        quiet(sim.run, 50)
        rulers = {c["id"]: c["ruler_cid"] for c in sim.cities}
        strict = {c["id"]: c["law_strictness"] for c in sim.cities}
        del sim.cities                                        # เซฟก่อนรุ่น 15 ไม่มีเมืองอยู่ในตัว
        state = sim.rng.getstate()
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "old.save")
            with open(path, "wb") as f:
                pickle.dump({"save_version": 14, "sim": sim}, f)
            back = PS.load_sim(path)
        self.assertEqual({c["id"]: c["ruler_cid"] for c in back.cities}, rulers)
        self.assertEqual({c["id"]: c["law_strictness"] for c in back.cities}, strict)
        self.assertEqual(back.rng.getstate(), state)


if __name__ == "__main__":
    unittest.main()
