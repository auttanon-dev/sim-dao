# -*- coding: utf-8 -*-
"""ผู้ปกครองเด็ก (tiandao/guardians.py): ทุกเด็กมีผู้ใหญ่รับผิดชอบ และส่งต่อได้เมื่อผู้ใหญ่ตาย

    python -m unittest test_guardians -v

สิ่งที่ล็อกไว้ (SIM_DAO_AUTONOMOUS_WORLD_DESIGN_TH.md §7.2 ข้อ 5, §7.4 ข้อ 6, §13.2 "ผู้ดูแลเสียชีวิต")
  · พ่อแม่เป็นผู้ปกครองก่อน ถ้าไม่มี ญาติ คนในตระกูล แล้วผู้ใหญ่ในที่เดียวกัน ตามลำดับ
  · ผู้ปกครองตาย เด็กได้คนใหม่ในธุรกรรมความตายเดียวกัน
  · ผู้ปกครองย้าย เด็กตามไป ครบ 14 ปีพ้นการดูแล คนที่ไม่ใช่พ่อแม่รับเลี้ยงได้ไม่เกินเพดาน
  · เด็กหิวที่ผู้ปกครองไม่มีข้าวใกล้ๆ หรือไม่มีผู้ปกครอง ไปอยู่กับคนที่อยู่ใกล้ข้าว เกินเพดานได้ถ้าจำเป็น
    ในแดนไม่มีข้าวเลย ญาติแล้วคนในแดนอื่นชั้นและชนิดเดียวกันรับไป
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
from tiandao import places as PL
from tiandao import sim as S
from tiandao import wages as WAGES
from test_food import only, places_by_hops, setup_person


def quiet(fn, *a, **kw):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*a, **kw)


def on(**flags):
    """เปิดระบบผู้ปกครอง ส่วนอาหารและค่าแรง (เปิดเป็นค่าเริ่มต้นแล้ว) ปิดไว้ เว้นแต่เทสต์ขอเปิด"""
    stack = contextlib.ExitStack()
    flags = {"GUARDIANS_ENABLED": True, "FOOD_ENABLED": False, "WAGES_ENABLED": False, **flags}
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


class ChildRelocationSafetyTests(unittest.TestCase):
    """เปิดระบบอาหาร เด็กต้องไม่ถูกย้ายไปอยู่กับผู้ปกครองในที่ที่ไม่มีข้าวในระยะส่ง"""

    def setUp(self):
        self.sim = quiet(S.Sim, seed=5)
        self.sim.granary = {}
        self.a, self.near, self.far = places_by_hops(self.sim)
        self.guardian = setup_person(self.sim, self.sim.cast[0], self.a)
        self.child = setup_person(self.sim, self.sim.cast[1], self.a, age=6)
        for ch in (self.guardian, self.child):
            ch.parents, ch.children, ch.spouse, ch.clan, ch.guardian, ch.wards = [], [], None, -1, -1, []
        self.child.parents = [self.guardian.cid]
        self.guardian.children = [self.child.cid]
        self.sim.granary[(0, self.a)] = 500.0          # ที่เดิมของเด็กมีข้าว ที่ไกลไม่มี

    def test_a_ward_does_not_follow_into_a_place_with_no_food_in_reach(self):
        with on(FOOD_ENABLED=True), only(self.sim, self.guardian, self.child):
            GUARD.tick(self.sim)
            self.guardian.place = self.far
            GUARD.on_arrival(self.sim, self.guardian, self.a)
        self.assertEqual(self.child.place, self.a)
        self.assertEqual(self.child.guardian, self.guardian.cid, "ยังเป็นผู้ปกครองอยู่ แค่เด็กไม่ย้าย")

    def test_the_ward_rejoins_once_the_guardians_place_has_food(self):
        with on(FOOD_ENABLED=True), only(self.sim, self.guardian, self.child):
            GUARD.tick(self.sim)
            self.guardian.place = self.far
            GUARD.tick(self.sim)
            self.assertEqual(self.child.place, self.a)
            self.sim.granary[(0, self.far)] = 500.0
            GUARD.tick(self.sim)
        self.assertEqual(self.child.place, self.far)

    def test_moving_is_allowed_when_the_childs_own_place_has_no_food_either(self):
        self.sim.granary = {}
        with on(FOOD_ENABLED=True), only(self.sim, self.guardian, self.child):
            GUARD.tick(self.sim)
            self.guardian.place = self.far
            GUARD.on_arrival(self.sim, self.guardian, self.a)
        self.assertEqual(self.child.place, self.far, "ย้ายไม่ทำให้แย่ลง จึงอยู่กับผู้ปกครอง")

    def _hungry_child_far_from_food(self, guardian_realm):
        self.sim.granary = {(0, self.a): 500.0}
        carer = setup_person(self.sim, self.sim.cast[2], self.a)
        carer.parents, carer.children, carer.spouse, carer.clan, carer.guardian, carer.wards = [], [], None, -1, -1, []
        self.guardian.place = self.child.place = self.far
        self.guardian.realm = guardian_realm
        self.child.food = 0.0
        return carer

    def test_a_hungry_child_whose_guardian_never_eats_is_fostered_near_food(self):
        # พ่อที่ถึงขั้นงดธัญญาหารไม่หิว จึงไม่ย้ายหาข้าว — เด็กที่หิวอยู่ข้างๆ ไปอยู่กับคนที่อยู่ใกล้ข้าว
        carer = self._hungry_child_far_from_food(C.FOOD_BIGU_REALM)
        with on(FOOD_ENABLED=True, FOOD_SPOIL_PER_YEAR=0.0), only(self.sim, self.guardian, self.child, carer):
            GUARD.tick(self.sim)
            self.assertEqual(self.child.guardian, self.guardian.cid)
            FOOD.tick(self.sim, 30)
            self.assertEqual(self.child.guardian, carer.cid)
            self.assertEqual(self.child.place, self.a)
            self.assertEqual(self.sim.guardian_stats["refostered"], 1)
            FOOD.tick(self.sim, 30)
        self.assertTrue(self.child.alive)
        self.assertEqual(self.child.hunger_days, 0.0)

    def test_a_hungry_child_whose_guardian_has_no_food_near_goes_to_someone_who_does(self):
        # ผู้ปกครองที่กินข้าวแต่ไม่มีข้าวใกล้ๆ ก็ไปไม่ถึงข้าวเกือบทุกราย — ไม่รอให้เขาพาไปเอง
        carer = self._hungry_child_far_from_food(0)
        self.guardian.food = 0.0
        with on(FOOD_ENABLED=True, FOOD_SPOIL_PER_YEAR=0.0), only(self.sim, self.guardian, self.child, carer):
            GUARD.tick(self.sim)
            FOOD.tick(self.sim, 30)
        self.assertEqual(self.child.guardian, carer.cid)
        self.assertEqual(self.child.place, self.a)

    def test_a_guardian_near_food_keeps_a_hungry_child_and_the_child_is_brought_to_him(self):
        carer = self._hungry_child_far_from_food(0)
        self.guardian.place = self.a                                      # ผู้ปกครองอยู่ใกล้ข้าว เด็กยังอยู่ที่ไกล
        with on(FOOD_ENABLED=True, FOOD_SPOIL_PER_YEAR=0.0), only(self.sim, self.guardian, self.child, carer):
            self.child.guardian, self.guardian.wards = self.guardian.cid, [self.child.cid]
            FOOD.tick(self.sim, 30)
            self.assertEqual(self.child.guardian, self.guardian.cid)
            GUARD.tick(self.sim)
        self.assertEqual(self.child.place, self.a)
        self.assertEqual(self.sim.guardian_stats["refostered"], 0)

    def test_when_everyone_near_food_is_full_the_least_burdened_still_takes_a_hungry_child(self):
        carer = self._hungry_child_far_from_food(0)
        carer.wards = [c.cid for c in self.sim.cast[10:10 + C.GUARDIAN_MAX_WARDS]]   # เต็มเพดานแล้ว
        self.child.parents, self.guardian.children = [], []
        with on(FOOD_ENABLED=True, FOOD_SPOIL_PER_YEAR=0.0), only(self.sim, self.child, carer):
            FOOD.tick(self.sim, 30)
        self.assertEqual(self.child.guardian, carer.cid)
        self.assertEqual(len(carer.wards), C.GUARDIAN_MAX_WARDS + 1)

    def _abroad(self, wid, cast_index):
        """ผู้ใหญ่ที่อยู่ใกล้ข้าวในแดน `wid` — ในแดนของเด็กไม่มีข้าวที่ไหนเลย"""
        place = PL.places_in(self.sim.world(wid).place_key)[0]
        self.sim.granary = {(wid, place): 500.0}
        c = setup_person(self.sim, self.sim.cast[cast_index], place)
        c.world_id = wid
        c.parents, c.children, c.spouse, c.clan, c.guardian, c.wards = [], [], None, -1, -1, []
        self.guardian.place = self.child.place = self.far
        self.guardian.food = self.child.food = 0.0
        return c, place

    def test_with_no_food_anywhere_in_its_realm_a_hungry_child_is_taken_in_by_another_realm(self):
        siam = next(w.wid for w in self.sim.worlds if w.place_key == "siam")
        carer, place = self._abroad(siam, 2)
        with on(FOOD_ENABLED=True, FOOD_SPOIL_PER_YEAR=0.0), only(self.sim, self.guardian, self.child, carer):
            GUARD.tick(self.sim)
            FOOD.tick(self.sim, 30)
            self.assertEqual((self.child.world_id, self.child.place, self.child.guardian), (siam, place, carer.cid))
            self.assertEqual(self.sim.guardian_stats["fostered_across_realms"], 1)
            FOOD.tick(self.sim, 30)
        self.assertTrue(self.child.alive)
        self.assertEqual(self.child.hunger_days, 0.0)

    def test_a_relative_abroad_comes_before_a_stranger(self):
        siam = next(w.wid for w in self.sim.worlds if w.place_key == "siam")
        stranger, place = self._abroad(siam, 2)
        grandma = setup_person(self.sim, self.sim.cast[3], place, age=60)
        grandma.world_id, grandma.wards = siam, [c.cid for c in self.sim.cast[10:13]]   # เลี้ยงหลานอยู่แล้วสามคน
        grandma.children, self.guardian.parents = [self.guardian.cid], [grandma.cid]
        with on(FOOD_ENABLED=True, FOOD_SPOIL_PER_YEAR=0.0), \
                only(self.sim, self.guardian, self.child, stranger, grandma):
            GUARD.tick(self.sim)
            FOOD.tick(self.sim, 30)
        self.assertEqual(self.child.guardian, grandma.cid)

    def test_nobody_crosses_into_a_realm_of_another_kind(self):
        mara = next(w.wid for w in self.sim.worlds if w.kind == "mara")
        demon, _place = self._abroad(mara, 2)
        with on(FOOD_ENABLED=True, FOOD_SPOIL_PER_YEAR=0.0), only(self.sim, self.guardian, self.child, demon):
            GUARD.tick(self.sim)
            FOOD.tick(self.sim, 30)
        self.assertEqual(self.child.world_id, 0)
        self.assertEqual(self.child.guardian, self.guardian.cid)

    def test_among_equal_relatives_the_one_near_food_is_chosen(self):
        orphan = setup_person(self.sim, self.sim.cast[2], self.far, age=6)
        near_food = setup_person(self.sim, self.sim.cast[3], self.a)
        no_food = setup_person(self.sim, self.sim.cast[4], self.far)
        for ch in (orphan, near_food, no_food):
            ch.parents, ch.children, ch.spouse, ch.guardian, ch.wards, ch.money = [], [], None, -1, [], {}
        orphan.clan = near_food.clan = no_food.clan = 3
        with on(FOOD_ENABLED=True), only(self.sim, orphan, near_food, no_food):
            GUARD.tick(self.sim)
        self.assertEqual(orphan.guardian, near_food.cid)


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
        with on(GUARDIANS_ENABLED=False):
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
