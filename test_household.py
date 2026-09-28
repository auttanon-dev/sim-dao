# -*- coding: utf-8 -*-
"""ครัวเรือน (แบบ §7.1 ขั้น H1: สมาชิกภาพ) — tiandao/household.py

    python -m unittest test_household -v
"""
import contextlib
import io
import os
import pickle
import tempfile
import unittest
from unittest import mock

from tiandao import config as C
from tiandao import events as E
from tiandao import guardians as GUARD
from tiandao import household as HH
from tiandao import persist as PS
from tiandao import sim as S

BIRTH = next(e for e in E.EVENT_TABLE if e["kind"] == "กำเนิดทายาท")


def quiet(fn, *a, **kw):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*a, **kw)


class HouseholdTests(unittest.TestCase):
    def setUp(self):
        self.sim = quiet(S.Sim, seed=5)
        self.sim.day = 3000
        adults = [c for c in self.sim.living_in(0) if c.sentient and 20 <= c.age(self.sim.day) <= 45
                  and c.spouse is None]
        self.man = next(c for c in adults if c.gender == "ชาย")
        self.woman = next(c for c in adults if c.gender == "หญิง")
        self.others = [c for c in adults if c not in (self.man, self.woman)]

    def kid(self, age, guardian):
        child = quiet(self.sim.spawn, self.sim.world(0), age_years=0)
        child.born_day = self.sim.day - age * 365
        child.came_of_age = age >= 14
        GUARD.assign(self.sim, child, guardian, "รับเลี้ยง")
        return child

    def assertHealthy(self):
        self.assertEqual(HH.check(self.sim), [])

    def test_everyone_starts_in_exactly_one_household(self):
        self.assertHealthy()
        baby = quiet(self.sim.spawn, self.sim.world(0), age_years=0)
        self.assertEqual(HH.of(self.sim, baby).members, [baby.cid])

    def test_marriage_merges_households_and_brings_the_wards_along(self):
        ward = self.kid(6, self.woman)
        self.assertEqual(ward.household, self.woman.household)
        self.assertTrue(self.sim.marry(self.man, self.woman))
        hh = HH.of(self.sim, self.man)
        self.assertEqual(set(hh.members), {self.man.cid, self.woman.cid, ward.cid})
        self.assertEqual((self.man.spouse, self.woman.spouse), (self.woman.cid, self.man.cid))
        self.assertFalse(self.sim.marry(self.man, self.others[0]), "แต่งซ้อนไม่ได้")
        self.assertHealthy()

    def test_the_heir_action_and_city_weddings_marry_through_the_same_path(self):
        quiet(self.sim.resolve, BIRTH, self.man, self.woman, self.sim.world(0), 30, self.sim.rng)
        self.assertEqual(self.man.household, self.woman.household)
        self.assertHealthy()

    def test_a_dead_head_is_succeeded_by_the_spouse_and_the_widow_can_remarry(self):
        self.sim.marry(self.man, self.woman)
        hid = self.man.household
        quiet(self.sim.kill, self.man, "ทดสอบ")
        hh = self.sim.households[hid]
        self.assertEqual((hh.head, hh.members), (self.woman.cid, [self.woman.cid]))
        self.assertIsNone(self.woman.spouse)
        self.assertEqual(self.man.spouse, self.woman.cid, "ประวัติคู่ครองของผู้ตายคงไว้")
        self.assertTrue(self.sim.marry(self.woman, self.others[0]))
        self.assertHealthy()

    def test_without_a_spouse_the_eldest_grown_member_leads_then_the_eldest_and_empty_households_dissolve(self):
        head = self.woman
        young = self.kid(9, head)
        teen = self.kid(15, head)
        teen.guardian = -1
        hid = head.household
        # ปิดระบบผู้ปกครองให้เห็นลำดับหัวหน้าอย่างเดียว — เปิดอยู่ เด็กจะถูกส่งไปผู้ปกครองใหม่ทันทีที่ผู้ปกครองตาย
        with mock.patch.object(C, "GUARDIANS_ENABLED", False):
            quiet(self.sim.kill, head, "ทดสอบ")
            self.assertEqual(self.sim.households[hid].head, teen.cid, "เติบใหญ่แล้วก่อน")
            quiet(self.sim.kill, teen, "ทดสอบ")
            self.assertEqual(self.sim.households[hid].head, young.cid)
            quiet(self.sim.kill, young, "ทดสอบ")
        self.assertNotIn(hid, self.sim.households)
        self.assertHealthy()

    def test_an_adult_without_parents_or_spouse_at_home_moves_out(self):
        ward = self.kid(10, self.woman)
        child = self.kid(12, self.woman)
        child.parents = [self.woman.cid]
        for c in (ward, child):
            c.born_day = self.sim.day - C.ADULT_AGE * 365 - 1
        quiet(HH.tick, self.sim)
        self.assertNotEqual(ward.household, self.woman.household, "ไม่มีพ่อแม่หรือคู่ครองในครัวเรือน")
        self.assertEqual(child.household, self.woman.household, "ลูกอยู่กับพ่อแม่ต่อได้")
        self.assertHealthy()

    def test_a_new_guardian_takes_the_child_into_their_household(self):
        child = self.kid(5, self.woman)
        GUARD.assign(self.sim, child, self.man, "สืบต่อ")
        self.assertEqual(child.household, self.man.household)
        self.assertHealthy()

    def test_households_never_touch_the_world_rng(self):
        ward = self.kid(6, self.woman)                  # spawn ใช้ rng ของโลก — วัดหลังเตรียมคนแล้ว
        state = self.sim.rng.getstate()
        self.sim.marry(self.man, self.woman)
        quiet(HH.tick, self.sim)
        HH.build(self.sim)
        self.assertEqual(self.sim.rng.getstate(), state)
        self.assertHealthy()

    def test_a_version_16_save_builds_households_from_family_ties_without_moving_the_rng(self):
        ward = self.kid(6, self.woman)
        self.sim.marry(self.man, self.woman)
        del self.sim.households, self.sim.household_seq
        for c in self.sim.cast:
            c.__dict__.pop("household", None)
        state = self.sim.rng.getstate()
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "old.save")
            with open(path, "wb") as f:
                pickle.dump({"save_version": 16, "sim": self.sim}, f)
            back = PS.load_sim(path)
        self.assertEqual(HH.check(back), [])
        m, w, k = (back.cast[c.cid] for c in (self.man, self.woman, ward))
        self.assertEqual(m.household, w.household)
        self.assertEqual(k.household, w.household)
        self.assertEqual(back.rng.getstate(), state)


class RunningWorldTests(unittest.TestCase):
    def test_the_invariant_holds_through_a_running_world_and_a_save(self):
        sim = quiet(S.Sim, seed=11)
        for _ in range(8):
            quiet(sim.run, 2500)
            self.assertEqual(HH.check(sim), [], f"ปีที่ {sim.day // 365}")
        self.assertTrue(any(len(h.members) >= 3 for h in sim.households.values()))
        self.assertTrue(any(c.spouse is not None for c in sim.living()))
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "w.save")
            PS.save_sim(sim, path)
            back = PS.load_sim(path)
        self.assertEqual(HH.check(back), [])
        self.assertEqual({h: sorted(v.members) for h, v in back.households.items()},
                         {h: sorted(v.members) for h, v in sim.households.items()})


if __name__ == "__main__":
    unittest.main()
