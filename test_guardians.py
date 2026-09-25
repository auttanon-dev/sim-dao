# -*- coding: utf-8 -*-
"""ผู้ปกครองเด็ก (tiandao/guardians.py): ทุกเด็กมีผู้ใหญ่รับผิดชอบ และส่งต่อได้เมื่อผู้ใหญ่ตาย

    python -m unittest test_guardians -v

สิ่งที่ล็อกไว้ (SIM_DAO_AUTONOMOUS_WORLD_DESIGN_TH.md §7.2 ข้อ 5, §7.4 ข้อ 6, §13.2 "ผู้ดูแลเสียชีวิต")
  · พ่อแม่เป็นผู้ปกครองก่อน ถ้าไม่มี ญาติ คนในตระกูล แล้วผู้ใหญ่ในที่เดียวกัน ตามลำดับ
  · ผู้ปกครองตาย เด็กได้คนใหม่ในธุรกรรมความตายเดียวกัน
  · ผู้ปกครองย้าย เด็กตามไป ครบ 14 ปีพ้นการดูแล คนที่ไม่ใช่พ่อแม่รับเลี้ยงได้ไม่เกินเพดาน
  · ผู้ปกครองที่อยู่ด้วยจ่ายค่าข้าวของเด็ก หมู่บ้านเลี้ยงเฉพาะเด็กที่ไม่มีใครอยู่ด้วย
"""
import contextlib
import io
import os
import tempfile
import unittest
from unittest import mock

from tiandao import config as C
from tiandao import food as FOOD
from tiandao import guardians as GUARD
from tiandao import persist as PS
from tiandao import sim as S
from tiandao import wages as WAGES
from test_food import only, places_by_hops, setup_person


def quiet(fn, *a, **kw):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*a, **kw)


def on(**flags):
    stack = contextlib.ExitStack()
    stack.enter_context(mock.patch.object(C, "GUARDIANS_ENABLED", True))
    for name, value in flags.items():
        stack.enter_context(mock.patch.object(C, name, value))
    return stack


class GuardianRulesTests(unittest.TestCase):
    def setUp(self):
        self.sim = quiet(S.Sim, seed=5)
        self.a, self.near, self.far = places_by_hops(self.sim)
        self.people = list(self.sim.cast[:8])
        for ch in self.people:
            setup_person(self.sim, ch, self.a)
            ch.parents, ch.children, ch.spouse, ch.clan = [], [], None, -1
            ch.guardian, ch.wards, ch.money = -1, [], {}

    def family(self):
        mother, uncle, child = self.people[0], self.people[1], self.people[2]
        grandma = self.people[3]
        setup_person(self.sim, child, self.a, age=6)
        setup_person(self.sim, grandma, self.near, age=60)
        child.parents = [mother.cid]
        mother.children = [child.cid]
        mother.parents = [grandma.cid]
        grandma.children = [mother.cid, uncle.cid]
        return mother, uncle, grandma, child

    def test_a_parent_is_the_first_guardian(self):
        mother, _uncle, _grandma, child = self.family()
        with on(), only(self.sim, *self.people[:4]):
            GUARD.tick(self.sim)
        self.assertEqual(child.guardian, mother.cid)
        self.assertEqual(mother.wards, [child.cid])

    def test_when_the_guardian_dies_family_takes_over_at_once(self):
        mother, _uncle, grandma, child = self.family()
        with on(), only(self.sim, *self.people[:4]):
            GUARD.tick(self.sim)
            quiet(self.sim.kill, mother, "ทดสอบ", natural=True)
        self.assertEqual(child.guardian, grandma.cid, "ย่าเป็นญาติใกล้ที่ยังมีชีวิต")
        self.assertEqual(child.place, grandma.place, "เด็กย้ายไปอยู่กับผู้ปกครองใหม่")
        self.assertEqual(self.sim.guardian_stats["reassigned"], 1)
        self.assertTrue(any(e.kind == "รับเลี้ยง" and e.target == child.cid for e in self.sim.log))

    def test_an_orphan_with_no_family_is_fostered_by_a_local_adult_who_can_afford_it(self):
        orphan = setup_person(self.sim, self.people[2], self.a, age=4)
        poor, rich = self.people[4], self.people[5]
        WAGES.move_gold(self.sim, rich, 500.0)
        with on(), only(self.sim, orphan, poor, rich):
            GUARD.tick(self.sim)
        self.assertEqual(orphan.guardian, rich.cid)

    def test_a_foster_carer_takes_no_more_than_the_limit(self):
        carer = self.people[0]
        orphans = [setup_person(self.sim, ch, self.a, age=5) for ch in self.people[1:4]]
        with on(GUARDIAN_MAX_WARDS=2), only(self.sim, carer, *orphans):
            GUARD.tick(self.sim)
        self.assertEqual(len(carer.wards), 2)
        self.assertEqual(self.sim.guardian_stats["unplaced"], 1)

    def test_wards_follow_their_guardian_to_a_new_home(self):
        mother, _uncle, _grandma, child = self.family()
        with on(), only(self.sim, *self.people[:4]):
            GUARD.tick(self.sim)
            mother.place = self.far
            GUARD.on_arrival(self.sim, mother, self.a)
        self.assertEqual(child.place, self.far)

    def test_guardianship_ends_at_fourteen(self):
        mother, _uncle, _grandma, child = self.family()
        with on(), only(self.sim, *self.people[:4]):
            GUARD.tick(self.sim)
            child.born_day = self.sim.day - 14 * 365
            GUARD.tick(self.sim)
        self.assertEqual(child.guardian, -1)
        self.assertEqual(mother.wards, [])

    def test_the_guardian_pays_for_the_childs_food_and_the_village_only_steps_in_without_one(self):
        mother, _uncle, _grandma, child = self.family()
        WAGES.move_gold(self.sim, mother, 100.0)
        mother.food = C.FOOD_PACK_DAYS * C.FOOD_RATION_ADULT      # เสบียงเต็มแล้ว วัดแค่ค่าอาหารมื้อ
        child.food = C.FOOD_PACK_DAYS * C.FOOD_RATION_CHILD
        self.sim.granary = {(0, self.a): 1000.0}
        with on(FOOD_ENABLED=True, WAGES_ENABLED=True, FOOD_SPOIL_PER_YEAR=0.0), \
                only(self.sim, mother, child):
            GUARD.tick(self.sim)
            FOOD.tick(self.sim, 30)
        self.assertEqual(self.sim.food_stats["charity"], 0.0)
        spent = 100.0 - WAGES.gold(self.sim, mother)
        self.assertAlmostEqual(spent, 30 * (C.FOOD_RATION_ADULT + C.FOOD_RATION_CHILD) * C.FOOD_PRICE)


class GuardiansInTheRunningWorldTests(unittest.TestCase):
    def test_most_children_have_a_guardian_living_with_them(self):
        with on():
            sim = quiet(S.Sim, seed=11)
            quiet(sim.run, 8000)
        kids = [c for c in sim.living() if c.age(sim.day) < 14]
        cared = [c for c in kids if c.guardian >= 0]
        self.assertGreater(len(cared), 0.9 * len(kids))
        for child in cared:
            g = sim.cast[child.guardian]
            self.assertTrue(g.alive)
            self.assertIn(child.cid, g.wards)
        self.assertLessEqual(max(len(c.wards) for c in sim.living()),
                             C.GUARDIAN_MAX_WARDS + max(len(c.children) for c in sim.living()))

    def test_switched_off_nobody_is_assigned(self):
        sim = quiet(S.Sim, seed=11)
        quiet(sim.run, 3000)
        self.assertTrue(all(ch.guardian == -1 and not ch.wards for ch in sim.cast))
        self.assertEqual(sim.guardian_stats, GUARD.new_stats())

    def test_save_and_load_with_every_life_system_on_continues_like_one_run(self):
        with on(FOOD_ENABLED=True, WAGES_ENABLED=True):
            straight = quiet(S.Sim, seed=7)
            quiet(straight.run, 2400)
            split = quiet(S.Sim, seed=7)
            quiet(split.run, 1200)
            with tempfile.TemporaryDirectory() as folder:
                path = os.path.join(folder, "world.save")
                PS.save_sim(split, path)
                split = PS.load_sim(path)
            quiet(split.run, 1200)
        self.assertEqual(split.day, straight.day)
        self.assertEqual(split.guardian_stats, straight.guardian_stats)
        self.assertEqual([c.guardian for c in split.cast], [c.guardian for c in straight.cast])


if __name__ == "__main__":
    unittest.main()
