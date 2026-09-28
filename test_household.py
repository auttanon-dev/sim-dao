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


class PurseTests(unittest.TestCase):
    """กระเป๋ากลาง (ขั้น H2) — ทองเข้าออกทาง household.transfer ทางเดียว wages.total_gold นับรวม"""

    def setUp(self):
        from test_food import setup_person
        self.sim = quiet(S.Sim, seed=5)
        self.sim.day = 3000
        people = [c for c in self.sim.living_in(0) if c.sentient and 20 <= c.age(self.sim.day) <= 45 and c.spouse is None]
        self.parent, self.other = people[0], people[1]
        for c in (self.parent, self.other):
            setup_person(self.sim, c, 3, food=10.0, age=30)
        self.child = quiet(self.sim.spawn, self.sim.world(0), age_years=0)
        setup_person(self.sim, self.child, 3, food=0.0, age=6)
        GUARD.assign(self.sim, self.child, self.parent, "รับเลี้ยง")
        self.hh = HH.of(self.sim, self.parent)
        self.hh.home = (0, 3)                          # บ้านอยู่ที่ที่ผู้ปกครองอยู่ประจำ (setup_person ย้ายเขามาหลังตั้งครัวเรือน)
        self.tier = self.sim.world(0).tier
        self.parent.money[self.tier] = 1000.0

    def total(self):
        from tiandao import wages as WAGES
        return WAGES.total_gold(self.sim, self.tier)

    def test_an_earner_at_home_tithes_until_the_ninety_day_cap(self):
        cap = 1 * C.FOOD_RATION_CHILD * C.FOOD_PRICE * C.HOUSEHOLD_PURSE_DAYS
        before = self.total()
        self.assertAlmostEqual(HH.contribute(self.sim, self.parent, 20.0), 20.0 * C.HOUSEHOLD_TITHE)
        HH.contribute(self.sim, self.parent, 500.0)
        self.assertAlmostEqual(self.hh.purse[self.tier], cap)
        self.assertEqual(HH.contribute(self.sim, self.parent, 500.0), 0.0, "เต็มเพดานแล้ว")
        self.assertAlmostEqual(self.total(), before)

    def test_no_tithe_without_children_or_from_afar(self):
        single = HH.of(self.sim, self.other)
        self.assertEqual(HH.contribute(self.sim, self.other, 100.0), 0.0, "ไม่มีเด็กในครัวเรือน")
        self.parent.travel_dest = 5
        self.assertEqual(HH.contribute(self.sim, self.parent, 100.0), 0.0, "กำลังเดินทาง")
        self.parent.travel_dest = -1
        far = next(p for p in range(60) if p != 3 and p not in
                   {q for q, _h in HH.TR.places_within(self.sim, 3, C.FOOD_REACH_HOPS)})
        self.hh.head = self.other.cid if False else self.hh.head
        self.parent.place = far
        self.child.place = far
        self.assertFalse(HH.in_reach(self.sim, self.hh, self.parent), "บ้านไม่ย้ายทันทีที่หัวหน้าเดินไปที่อื่น")
        HH.tick(self.sim)
        self.assertEqual(self.hh.home, (0, far))
        self.assertTrue(HH.in_reach(self.sim, self.hh, self.parent), "หัวหน้าอยู่ประจำที่ใหม่แล้ว บ้านย้ายตาม")
        self.child.place = 3
        self.assertFalse(HH.in_reach(self.sim, self.hh, self.child), "เด็กอยู่นอกระยะส่งถึงบ้าน")
        self.assertEqual(single.purse, {})

    def test_the_purse_pays_for_the_child_first_then_the_guardian(self):
        from tiandao import food as FOOD, wages as WAGES
        with mock.patch.multiple(C, WAGES_ENABLED=True, GUARDIANS_ENABLED=True, FOOD_ENABLED=True):
            self.hh.purse[self.tier] = 1.0
            guardian_gold = WAGES.gold(self.sim, self.parent)
            got, paid = FOOD._buy(self.sim, self.child, 30.0)          # 30 สำรับ = 3 ทอง
        self.assertAlmostEqual((got, paid), (30.0, 3.0))
        self.assertAlmostEqual(self.hh.purse[self.tier], 0.0)
        self.assertAlmostEqual(guardian_gold - WAGES.gold(self.sim, self.parent), 2.0, "ส่วนที่เหลือจากผู้ปกครอง")

    def test_gold_is_conserved_through_merge_move_split_and_death(self):
        self.hh.purse[self.tier] = 4.0
        self.parent.money[self.tier] -= 4.0
        before = self.total()
        solo = HH.of(self.sim, self.other)
        solo.purse[self.tier] = 2.0
        self.other.money[self.tier] = self.other.money.get(self.tier, 0.0) - 2.0
        self.sim.marry(self.parent, self.other)              # กระเป๋าของครัวเรือนที่ว่างรวมเข้า
        self.assertAlmostEqual(self.hh.purse[self.tier], 6.0)
        self.assertAlmostEqual(self.total(), before)
        GUARD.assign(self.sim, self.child, self.other, "สืบต่อ")      # ย้ายในครัวเรือนเดียวกัน ไม่มีอะไรเปลี่ยน
        HH.found(self.sim, self.child)                       # แยกออก กระเป๋าอยู่กับครัวเรือนเดิม
        self.assertAlmostEqual(self.hh.purse[self.tier], 6.0)
        quiet(self.sim.kill, self.other, "ทดสอบ")
        heirs_before = self.parent.money[self.tier]
        quiet(self.sim.kill, self.parent, "ทดสอบ")           # คนสุดท้าย: กระเป๋าเข้าเงินก่อนแบ่งมรดก
        self.assertNotIn(self.hh.hid, self.sim.households)
        self.assertAlmostEqual(self.total(), before)

    def test_the_last_member_moving_out_takes_the_purse_along(self):
        self.hh.purse[self.tier] = 3.0
        self.parent.money[self.tier] -= 3.0
        before = self.total()
        HH.found(self.sim, self.child)
        target = HH.of(self.sim, self.other)
        HH.join(self.sim, self.parent, target)
        self.assertNotIn(self.hh.hid, self.sim.households)
        self.assertAlmostEqual(target.purse[self.tier], 3.0)
        self.assertAlmostEqual(self.total(), before)

    def test_a_version_17_save_gets_empty_purses_without_moving_the_rng(self):
        for hh in self.sim.households.values():
            hh.__dict__.pop("purse", None)
        state = self.sim.rng.getstate()
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "old.save")
            with open(path, "wb") as f:
                pickle.dump({"save_version": 17, "sim": self.sim}, f)
            back = PS.load_sim(path)
        self.assertTrue(all(hh.purse == {} for hh in back.households.values()))
        self.assertEqual(back.rng.getstate(), state)


class LarderTests(unittest.TestCase):
    """ครัว (ขั้น H3) — ข้าวอยู่ที่บ้าน นับใน food.total_held ไม่ย้ายข้ามที่"""
    setUp = PurseTests.setUp

    def food(self):
        from tiandao import food as FOOD
        return FOOD.total_held(self.sim)

    def test_only_children_within_reach_of_home_draw_from_the_larder(self):
        self.hh.larder = 100.0
        ration = lambda ch: 1.0
        self.assertEqual(HH.draw(self.sim, [self.child], 10, ration), {self.child.cid: 10.0})
        self.assertAlmostEqual(self.hh.larder, 90.0)
        self.child.travel_dest = 5
        self.assertEqual(HH.draw(self.sim, [self.child], 10, ration), {}, "กำลังเดินทาง")
        self.child.travel_dest = -1
        self.child.world_id = next(w.wid for w in self.sim.worlds if w.wid != 0)
        self.assertEqual(HH.draw(self.sim, [self.child], 10, ration), {}, "อยู่แดนอื่น")
        self.child.world_id = 0
        self.assertEqual(HH.draw(self.sim, [self.child], 1000, ration), {self.child.cid: 90.0}, "ครัวไม่พอ ได้เท่าที่มี")
        self.assertAlmostEqual(self.hh.larder, 0.0)

    def test_the_purse_stocks_only_from_the_granarys_spare_at_the_market_price(self):
        self.sim.granary[(0, 3)] = 500.0
        self.hh.purse[self.tier] = 100.0
        self.parent.money[self.tier] -= 100.0
        food, till = self.food(), self.sim.farm_till.get((0, 3), 0.0)
        ration = lambda ch: 2.0
        paid = HH.stock(self.sim, {(0, 3): 40.0}, ration)
        self.assertAlmostEqual(self.hh.larder, 40.0, msg="ไม่เกินส่วนเกินของยุ้งฉาง")
        self.assertAlmostEqual(paid[(0, 3)], 40.0 * C.FOOD_PRICE)
        self.assertAlmostEqual(self.hh.purse[self.tier], 100.0 - 40.0 * C.FOOD_PRICE)
        HH.stock(self.sim, {(0, 3): 1000.0}, ration)
        self.assertAlmostEqual(self.hh.larder, C.LARDER_DAYS * 2.0, msg="ไม่เกิน LARDER_DAYS วันของเด็ก")
        self.assertAlmostEqual(self.food(), food, msg="ข้าวแค่ย้ายจากยุ้งฉางเข้าครัว")
        self.assertEqual(self.sim.farm_till.get((0, 3), 0.0), till, "ผู้เรียกส่งทองเข้าลิ้นชักไร่")

    def test_a_moving_home_returns_the_larder_to_the_old_granary(self):
        self.hh.larder = 30.0
        food, old = self.food(), self.sim.granary.get((0, 3), 0.0)
        self.parent.travel_dest = 7
        HH.tick(self.sim)
        self.assertEqual(self.hh.home, (0, 3), "เดินทางอยู่ บ้านยังไม่ย้าย")
        self.parent.travel_dest, self.parent.place = -1, 7
        HH.tick(self.sim)
        self.assertEqual((self.hh.home, self.hh.larder), ((0, 7), 0.0))
        self.assertAlmostEqual(self.sim.granary[(0, 3)], old + 30.0)
        self.assertAlmostEqual(self.food(), food)

    def test_food_is_conserved_through_marriage_across_places_and_the_last_death(self):
        solo = HH.of(self.sim, self.other)
        solo.home, solo.larder = (0, 9), 12.0
        self.hh.larder = 20.0
        food, there = self.food(), self.sim.granary.get((0, 9), 0.0)
        self.sim.marry(self.parent, self.other)              # บ้านอยู่คนละที่: ข้าวคืนยุ้งฉางที่ (0, 9)
        self.assertAlmostEqual(self.hh.larder, 20.0)
        self.assertAlmostEqual(self.sim.granary[(0, 9)], there + 12.0)
        HH.found(self.sim, self.child)
        quiet(self.sim.kill, self.other, "ทดสอบ")
        quiet(self.sim.kill, self.parent, "ทดสอบ")           # คนสุดท้าย: ข้าวในครัวคืนยุ้งฉางที่บ้าน
        self.assertNotIn(self.hh.hid, self.sim.households)
        self.assertAlmostEqual(self.food(), food)

    def test_a_household_dissolving_into_one_at_the_same_home_brings_its_larder(self):
        solo = HH.of(self.sim, self.other)
        solo.home, solo.larder = (0, 3), 12.0
        food = self.food()
        HH.join(self.sim, self.other, self.hh)
        self.assertAlmostEqual(self.hh.larder, 12.0)
        self.assertAlmostEqual(self.food(), food)

    def test_a_version_18_save_gets_empty_larders_and_a_fixed_home_without_moving_the_rng(self):
        for hh in self.sim.households.values():
            hh.__dict__.pop("larder", None)
            hh.__dict__.pop("home", None)
        state = self.sim.rng.getstate()
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "old.save")
            with open(path, "wb") as f:
                pickle.dump({"save_version": 18, "sim": self.sim}, f)
            back = PS.load_sim(path)
        self.assertTrue(all(hh.larder == 0.0 for hh in back.households.values()))
        self.assertEqual(back.households[self.hh.hid].home, (0, 3))
        self.assertEqual(back.rng.getstate(), state)


class SuccessionTests(unittest.TestCase):
    """สืบทอดและคลังตระกูล (ขั้น H4) — ทองและข้าวตรงตัวทุกทาง"""
    setUp = PurseTests.setUp

    def totals(self):
        from tiandao import food as FOOD, wages as WAGES
        return WAGES.total_gold(self.sim, self.tier), FOOD.total_held(self.sim)

    def fund(self, purse=5.0, larder=20.0):
        self.hh.purse[self.tier] = purse
        self.parent.money[self.tier] -= purse
        self.hh.larder = larder

    def test_the_successor_takes_the_household_with_its_purse_and_larder_intact(self):
        self.sim.marry(self.parent, self.other)
        self.fund()
        before = self.totals()
        quiet(self.sim.kill, self.parent, "ทดสอบ")
        self.assertEqual(self.hh.head, self.other.cid, "คู่ครองรับช่วง")
        self.assertIn(self.hh.hid, self.sim.households)
        self.assertEqual((self.hh.purse[self.tier], self.hh.larder), (5.0, 20.0))
        self.assertAlmostEqual(self.totals()[0], before[0])
        self.assertAlmostEqual(self.totals()[1], before[1])

    def heirless_last_member(self):
        self.parent.spouse, self.parent.children, self.parent.org = None, [], None
        HH.found(self.sim, self.child)                       # เด็กแยกไป ผู้ปกครองเหลือคนเดียวพร้อมกระเป๋าและครัว
        self.fund()
        self.assertEqual(self.sim.heirs_of(self.parent), [])

    def test_an_heirless_clan_member_leaves_the_purse_to_the_clan_and_the_larder_to_the_granary(self):
        self.heirless_last_member()
        self.parent.clan = 2
        granary = self.sim.granary.get((0, 3), 0.0) + self.parent.food     # เสบียงติดตัวของผู้ตายเข้ายุ้งฉางด้วย (food.on_death)
        own = self.parent.money[self.tier]
        before, flows = self.totals(), repr(getattr(self.sim, "gold_flows", {}))
        quiet(self.sim.kill, self.parent, "ทดสอบ")
        self.assertNotIn(self.hh.hid, self.sim.households)
        self.assertAlmostEqual(self.sim.clan_treasury[2][self.tier], own + 5.0, msg="กระเป๋าและทองส่วนตัว (A1) เข้าศาลบรรพชน")
        self.assertAlmostEqual(self.parent.money.get(self.tier, 0.0), 0.0)
        self.assertEqual(repr(self.sim.gold_flows), flows, "ย้ายจากคนเข้าคลัง ไม่ใช่ทองเกิดหรือหาย")
        self.assertAlmostEqual(self.sim.granary[(0, 3)], granary + 20.0)
        self.assertAlmostEqual(self.totals()[0], before[0])
        self.assertAlmostEqual(self.totals()[1], before[1])

    def test_without_a_clan_the_purse_follows_the_old_estate_rules(self):
        self.heirless_last_member()
        self.parent.clan = -1
        before = self.totals()
        quiet(self.sim.kill, self.parent, "ทดสอบ")
        self.assertEqual(self.sim.clan_treasury, {})
        self.assertAlmostEqual(self.totals()[0], before[0])
        self.assertAlmostEqual(self.totals()[1], before[1])

    def test_a_sect_still_takes_an_heirless_members_estate_before_the_clan(self):
        from tiandao.models import Org
        self.heirless_last_member()
        self.parent.clan = 2
        org = Org(len(self.sim.orgs), "สำนัก", "สำนักทดสอบ", 0, self.other.cid, 0)
        self.sim.orgs.append(org)
        self.parent.org = org.oid if hasattr(org, "oid") else len(self.sim.orgs) - 1
        own = self.parent.money[self.tier]
        before = self.totals()
        quiet(self.sim.kill, self.parent, "ทดสอบ")
        self.assertAlmostEqual(org.treasury_gold[self.tier], own)
        self.assertAlmostEqual(self.sim.clan_treasury[2][self.tier], 5.0, msg="กระเป๋าไร้ทายาทยังเข้าตระกูล (H4)")
        self.assertAlmostEqual(self.totals()[0], before[0])

    def test_a_living_heir_outside_the_household_inherits_the_purse_not_the_clan(self):
        self.heirless_last_member()
        self.parent.clan = 2
        self.parent.children = [self.other.cid]
        self.other.born_day = self.sim.day - 30 * 365
        heir_gold = self.other.money.get(self.tier, 0.0)
        own = self.parent.money[self.tier]
        quiet(self.sim.kill, self.parent, "ทดสอบ")
        self.assertEqual(self.sim.clan_treasury.get(2, {}), {})
        self.assertAlmostEqual(self.other.money[self.tier], heir_gold + own + 5.0)

    def test_a_version_19_save_gets_an_empty_clan_treasury_without_moving_the_rng(self):
        del self.sim.clan_treasury
        state = self.sim.rng.getstate()
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "old.save")
            with open(path, "wb") as f:
                pickle.dump({"save_version": 19, "sim": self.sim}, f)
            back = PS.load_sim(path)
        self.assertEqual(back.clan_treasury, {})
        self.assertEqual(back.rng.getstate(), state)


class RunningWorldTests(unittest.TestCase):
    def test_a_running_world_keeps_its_food_ledger_with_larders(self):
        from tiandao import food as FOOD
        sim = quiet(S.Sim, seed=11)
        for _ in range(4):
            quiet(sim.run, 3000)
            self.assertAlmostEqual(FOOD.total_held(sim), FOOD.ledger_balance(sim.food_stats), places=4)
            self.assertEqual(HH.check(sim), [])
        self.assertGreater(HH.larder_food(sim), 0.0)
        self.assertGreater(sim.household_stats.get("larder_eaten", 0.0), 0.0)
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "w.save")
            PS.save_sim(sim, path)
            back = PS.load_sim(path)
        self.assertEqual({h: (v.home, v.larder) for h, v in back.households.items()},
                         {h: (v.home, v.larder) for h, v in sim.households.items()})

    def test_a_world_with_purses_keeps_its_gold_ledger(self):
        from tiandao import wages as WAGES
        sim = quiet(S.Sim, seed=11)
        quiet(sim.run, 12000)
        self.assertGreater(HH.purse_gold(sim, 0) + sum(HH.purse_gold(sim, t) for t in (1, 2)), 0.0)
        self.assertGreater(sim.household_stats.get("purse_paid", 0.0), 0.0)
        from tiandao import food as FOOD
        before = {t: WAGES.total_gold(sim, t) for t in (0, 1, 2)}
        issued, tithe, paid = (sim.wage_stats["issued"], sim.household_stats.get("tithe", 0.0),
                               sim.household_stats.get("purse_paid", 0.0))
        sim.day += C.WORLD_TICK_DAYS
        # ขั้นของรอบโลกที่ทองของครัวเรือนผ่าน: ผู้ปกครอง ครัวเรือน ค่าข้าว ค่าแรง (รอบโลกทั้งรอบ test_sect_dues ตรวจแล้ว)
        quiet(GUARD.tick, sim)
        quiet(HH.tick, sim)
        quiet(FOOD.tick, sim, C.WORLD_TICK_DAYS)
        quiet(WAGES.tick, sim, C.WORLD_TICK_DAYS)
        self.assertGreater(sim.household_stats["tithe"] - tithe, 0.0)
        self.assertGreater(sim.household_stats["purse_paid"] - paid, 0.0)
        after = {t: WAGES.total_gold(sim, t) for t in (0, 1, 2)}
        self.assertAlmostEqual(sum(after.values()) - sum(before.values()), sim.wage_stats["issued"] - issued, places=6)

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
