# -*- coding: utf-8 -*-
"""เพดานยุ้งฉาง การเน่าตามฤดู และการเดินทางตามฤดู (แบบ §6.3)

    python -m unittest test_food_storage -v

ตรวจตัวคูณและกฎบัญชีตรงๆ — ไม่ตรวจสถิติจากตัวอย่างเล็ก (เช่น หน้าหนาวต้องอดตายมากกว่าทุกฤดู)
การกวาดหลาย seed 50 ปีเป็นรายงานสมดุล ไม่ใช่เทสต์
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
from tiandao import food as FOOD
from tiandao import persist as PS
from tiandao import physics as PHYS
from tiandao import seasons as SEASONS
from tiandao import sim as S
from tiandao import travel as TR
from test_food import food_on, no_spoil, only, places_by_hops, setup_person

MONTH = 365.0 / 12.0
SPRING, SUMMER, RAINY, WINTER = 10, 100, 200, 300          # วันกลางของแต่ละฤดูในปี (seasons.season_of)


def quiet(fn, *a, **kw):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*a, **kw)


def in_ledger(sim):
    """ข้าวตามบัญชีลบข้าวที่มีจริง — ต้องเป็นศูนย์"""
    return FOOD.ledger_balance(sim.food_stats) - FOOD.total_held(sim)


class CapacityTests(unittest.TestCase):
    def setUp(self):
        self.sim = quiet(S.Sim, seed=5)
        self.a, self.near, self.far = places_by_hops(self.sim)
        self.spot, self.near_spot = (0, self.a), (0, self.near)
        self.sim.granary = {self.spot: 0.0}
        self.people = [setup_person(self.sim, c, self.a) for c in self.sim.cast[:3]]

    def cap(self, people):
        return FOOD.store_capacity(self.sim, {self.spot: list(people)})

    def test_capacity_is_three_months_of_expected_consumption(self):
        self.assertEqual(C.FOOD_STORE_MONTHS, 3)
        adult, child = self.people[0], setup_person(self.sim, self.people[1], self.a, age=6)
        want = C.FOOD_STORE_MONTHS * MONTH * (C.FOOD_RATION_ADULT + C.FOOD_RATION_CHILD)
        self.assertAlmostEqual(self.cap([adult, child])[self.spot], want)
        with mock.patch.object(C, "FOOD_STORE_MONTHS", 5):
            self.assertAlmostEqual(self.cap([adult, child])[self.spot], want * 5 / 3, msg="มาจากค่าคงที่ตัวเดียว")

    def test_each_person_counts_once_across_every_granary_that_can_reach_them(self):
        self.sim.granary[self.near_spot] = 0.0
        cap = self.cap(self.people[:1])
        self.assertGreater(cap[self.near_spot], 0.0, "ยุ้งฉางในระยะแบ่งความต้องการไปด้วย")
        self.assertAlmostEqual(sum(cap.values()), C.FOOD_STORE_MONTHS * MONTH * C.FOOD_RATION_ADULT)

    def test_duplicate_references_do_not_count_a_person_twice(self):
        p = self.people[0]
        once = self.cap([p])[self.spot]
        p.org, p.clan, p.household, p.building = 0, 0, 0, 0     # เป็นสมาชิกสำนัก ตระกูล ครัวเรือน อาคาร
        self.assertAlmostEqual(self.cap([p, p, p])[self.spot], once)

    def test_the_dead_add_no_capacity(self):
        alive, dead = self.people[:2]
        dead.alive = False
        self.assertAlmostEqual(self.cap([alive, dead])[self.spot], self.cap([alive])[self.spot])
        self.assertEqual(self.cap([dead])[self.spot], 0.0)

    def test_stock_above_capacity_is_cut_and_recorded_as_spoilage(self):
        cap = self.cap(self.people[:1])[self.spot]
        self.sim.granary[self.spot] = cap + 100.0
        before = dict(self.sim.food_stats)
        gap = in_ledger(self.sim)
        FOOD._cap_granaries(self.sim, {self.spot: self.people[:1]})
        self.assertAlmostEqual(self.sim.granary[self.spot], cap)
        self.assertAlmostEqual(self.sim.food_stats["spoiled"] - before["spoiled"], 100.0)
        self.assertAlmostEqual(self.sim.food_stats["overflow"] - before.get("overflow", 0.0), 100.0)
        self.assertAlmostEqual(in_ledger(self.sim), gap, msg="บัญชีข้าวปิดทั้งก่อนและหลังตัด")

    def test_stock_below_capacity_is_untouched(self):
        self.sim.granary[self.spot] = 10.0
        spoiled = self.sim.food_stats["spoiled"]
        FOOD._cap_granaries(self.sim, {self.spot: self.people[:1]})
        self.assertEqual(self.sim.granary[self.spot], 10.0)
        self.assertEqual(self.sim.food_stats["spoiled"], spoiled)

    def test_a_falling_population_lowers_capacity_and_the_cut_is_spoilage(self):
        two = self.people[:2]
        self.sim.granary[self.spot] = self.cap(two)[self.spot]
        two[1].alive = False
        spoiled, gap = self.sim.food_stats["spoiled"], in_ledger(self.sim)
        FOOD._cap_granaries(self.sim, {self.spot: two})
        half = C.FOOD_STORE_MONTHS * MONTH * C.FOOD_RATION_ADULT
        self.assertAlmostEqual(self.sim.granary[self.spot], half)
        self.assertAlmostEqual(self.sim.food_stats["spoiled"] - spoiled, half)
        self.assertAlmostEqual(in_ledger(self.sim), gap)


class TickTests(unittest.TestCase):
    def setUp(self):
        self.sim = quiet(S.Sim, seed=5)
        self.a, self.near, self.far = places_by_hops(self.sim)
        self.sim.granary = {}
        self.eater = setup_person(self.sim, self.sim.cast[0], self.a)

    def test_carried_in_food_cannot_leave_a_granary_above_capacity(self):
        self.sim.granary = {(0, self.a): 0.0, (0, self.near): 10_000.0}
        with food_on(), no_spoil(), only(self.sim, self.eater):
            FOOD.tick(self.sim, 30)
        cap = FOOD.store_capacity(self.sim, {(0, self.a): [self.eater]})
        for spot, stock in self.sim.granary.items():
            self.assertLessEqual(stock, cap[spot] + 1e-9)
            self.assertGreaterEqual(stock, 0.0)
        self.assertGreater(self.sim.food_stats["eaten"], 0.0, "ขนมากินได้จริง")

    def test_each_round_closes_the_food_ledger_and_the_demand_ledger(self):
        self.sim.granary = {(0, self.a): 5_000.0}
        hungry = setup_person(self.sim, self.sim.cast[1], self.far)          # ไม่มีข้าวในระยะ ต้องหิว
        with food_on(), only(self.sim, self.eater, hungry):
            for _ in range(4):
                opening, stats0 = FOOD.total_held(self.sim), dict(self.sim.food_stats)
                FOOD.tick(self.sim, 30)
                self.sim.day += 30
                s = self.sim.food_stats
                moved = {k: s[k] - stats0.get(k, 0.0) for k in ("endowed", "produced", "eaten", "spoiled",
                                                                 "carried_lost", "lost", "required", "unmet")}
                closing = (opening + moved["endowed"] + moved["produced"] - moved["eaten"] - moved["spoiled"]
                           - moved["carried_lost"] - moved["lost"])
                self.assertAlmostEqual(FOOD.total_held(self.sim), closing, places=6)
                self.assertAlmostEqual(moved["required"], moved["eaten"] + moved["unmet"], places=6)
                for k, v in moved.items():
                    self.assertGreaterEqual(v, -1e-9, k)
        self.assertGreater(self.sim.food_stats["unmet"], 0.0, "คนที่ไม่มีข้าวถึงนับเป็นความต้องการที่ไม่ได้กิน")
        for stock in self.sim.granary.values():
            self.assertGreaterEqual(stock, 0.0)


class VolunteerLabourTests(unittest.TestCase):
    """คนลงไร่ช่วงข้าวขาด (_adapt_labour) ต้องกลับไปทำงานเดิมได้เมื่อยุ้งฉางเต็มเพดาน แม้เพดานต่ำกว่า 90 วันของคนที่นี่"""

    def setUp(self):
        self.sim = quiet(S.Sim, seed=5)
        self.a, self.near, self.far = places_by_hops(self.sim)
        self.spot = (0, self.a)
        self.helper = setup_person(self.sim, self.sim.cast[0], self.a)
        self.helper.fieldwork = True
        self.idle = setup_person(self.sim, self.sim.cast[1], self.a)
        self.idle.fieldwork = False

    def adapt(self, deficit=None, cap=None, eaters=None):
        eaters = eaters or [self.helper]
        FOOD._adapt_labour(self.sim, {self.spot: eaters}, {self.spot: [self.helper]}, deficit or {}, 30, 1.0, cap)

    def test_an_adequate_reserve_sends_volunteers_back_to_their_work(self):
        self.sim.granary = {self.spot: C.FOOD_DEST_STOCK_DAYS * C.FOOD_RATION_ADULT}
        self.adapt(cap=FOOD.store_capacity(self.sim, {self.spot: [self.helper]}))
        self.assertFalse(self.helper.fieldwork)

    def test_a_full_local_share_with_thin_area_reserves_keeps_the_only_producer(self):
        self.sim.granary = {self.spot: 0.0, (0, self.near): 0.0}          # สองยุ้งฉางส่งถึงที่นี่ ยุ้งฉางข้างบ้านว่าง
        cap = FOOD.store_capacity(self.sim, {self.spot: [self.helper]})
        self.assertLess(cap[self.spot], C.FOOD_DEST_STOCK_DAYS * C.FOOD_RATION_ADULT, "ส่วนของที่นี่ไม่ถึง 90 วัน")
        self.sim.granary[self.spot] = cap[self.spot]
        self.adapt(cap=cap)
        self.assertTrue(self.helper.fieldwork, "เป็นคนผลิตคนเดียว ปล่อยแล้วข้าวหมดในหนึ่งสองรอบ")

    def test_a_full_local_share_releases_labour_beyond_what_feeds_the_place(self):
        farmer = setup_person(self.sim, self.sim.cast[2], self.a, profession="ชาวนา")
        self.sim.granary = {self.spot: 0.0, (0, self.near): 0.0}
        eaters = [self.helper, farmer]
        cap = FOOD.store_capacity(self.sim, {self.spot: eaters})
        self.sim.granary[self.spot] = cap[self.spot]
        self.assertGreaterEqual(FOOD.land_output_per_day(BODY.work_capacity(farmer)), 2 * C.FOOD_RATION_ADULT)
        FOOD._adapt_labour(self.sim, {self.spot: eaters}, {self.spot: [farmer, self.helper]}, {}, 30, 1.0, cap)
        self.assertFalse(self.helper.fieldwork, "ชาวนาประจำผลิตพอเลี้ยงที่นี่ คนลงไร่เป็นแรงงานเกิน")

    def test_a_zero_capacity_with_zero_stock_is_not_an_adequate_reserve(self):
        self.sim.granary = {self.spot: 0.0}
        self.adapt(cap={self.spot: 0.0})              # เพดานศูนย์ทั้งที่คนที่นี่ต้องกิน (ป้อนตรงๆ เพื่อตรวจขอบ)
        self.assertTrue(self.helper.fieldwork)

    def test_a_place_short_this_round_keeps_its_volunteers_even_at_a_tiny_limit(self):
        self.sim.granary = {self.spot: 5.0}
        self.adapt(deficit={self.spot: 10.0}, cap={self.spot: 5.0})
        self.assertTrue(self.helper.fieldwork, "ยังขาดข้าวรอบนี้ ไม่ปล่อยกลับแม้ยุ้งฉางถึงเพดานเล็กๆ")

    def test_a_shortage_recruits_volunteers_again(self):
        self.sim.granary = {self.spot: 0.0}
        self.helper.fieldwork = False
        FOOD._adapt_labour(self.sim, {self.spot: [self.idle]}, {}, {self.spot: 30 * 10.0}, 30, 1.0,
                           FOOD.store_capacity(self.sim, {self.spot: [self.idle]}))
        self.assertTrue(self.idle.fieldwork)

    def test_an_adequate_shared_reserve_releases_volunteers(self):
        self.sim.granary = {self.spot: 0.0, (0, self.near): 0.0}
        cap = FOOD.store_capacity(self.sim, {self.spot: [self.helper]})
        self.sim.granary = dict(cap)                                       # ทั้งสองยุ้งฉางเต็ม = 91 วันของคนที่นี่
        self.adapt(cap=cap)
        self.assertFalse(self.helper.fieldwork)

    def test_overlapping_coverage_does_not_trap_a_volunteer_and_both_ledgers_close(self):
        farmer = setup_person(self.sim, self.sim.cast[2], self.a, profession="ชาวนา")
        self.sim.granary = {self.spot: 0.0, (0, self.near): 0.0}
        with food_on(), no_spoil(), only(self.sim, self.helper, farmer):
            for _ in range(6):
                opening, stats0 = FOOD.total_held(self.sim), dict(self.sim.food_stats)
                FOOD.tick(self.sim, 30)
                self.sim.day += 30
                s = self.sim.food_stats
                d = {k: s[k] - stats0.get(k, 0.0) for k in s if isinstance(s[k], float)}
                self.assertAlmostEqual(FOOD.total_held(self.sim), opening + d["endowed"] + d["produced"] - d["eaten"]
                                       - d["spoiled"] - d["carried_lost"] - d["lost"], places=6)
                self.assertAlmostEqual(d["required"], d["eaten"] + d["unmet"], places=6)
                if not self.helper.fieldwork:
                    break
        self.assertFalse(self.helper.fieldwork, "มีคนผลิตประจำพอแล้ว ยุ้งฉางเต็มเพดาน ไม่ติดอยู่ในไร่")


class SurplusReleaseTests(unittest.TestCase):
    """ยุ้งฉางของที่นี่เต็มเพดานแต่ข้าวสำรองไม่ถึง 90 วัน: ปล่อยแรงงานที่เกินทีละคน (แรงน้อยก่อน) คิดผลผลิตใหม่หลังปล่อยแต่ละคน
    ผลผลิต = land_output_per_day(แรงรวม) × ฤดู เหมือนการลงไร่ ความต้องการ = สำรับของทุกคนที่กินที่นี่ รวมเด็ก"""

    def setUp(self):
        self.sim = quiet(S.Sim, seed=5)
        self.a, self.near, _far = places_by_hops(self.sim)
        self.spot = (0, self.a)
        cast = self.sim.cast
        self.farmer = setup_person(self.sim, cast[0], self.a, profession="ชาวนา", age=25)
        self.strong = setup_person(self.sim, cast[1], self.a, age=25)
        self.weak = setup_person(self.sim, cast[2], self.a, age=85)
        self.strong.fieldwork = self.weak.fieldwork = True
        self.others = [setup_person(self.sim, c, self.a) for c in cast[3:9]]           # รวมเก้าคนกินที่นี่

    def decide(self, season, extra=()):
        eaters = [self.farmer, self.strong, self.weak] + self.others + list(extra)
        self.sim.granary = {self.spot: 0.0, (0, self.near): 0.0}
        cap = FOOD.store_capacity(self.sim, {self.spot: eaters})
        self.sim.granary[self.spot] = cap[self.spot]                                 # ส่วนของที่นี่เต็ม ข้างบ้านว่าง
        assigned = FOOD.assigned_demand(self.sim, {self.spot: eaters})
        self.assertLess(FOOD.attributed_reserve(self.sim, self.spot, assigned),
                        C.FOOD_DEST_STOCK_DAYS * sum(FOOD.ration(c, self.sim.day) for c in eaters))
        FOOD._adapt_labour(self.sim, {self.spot: eaters}, {self.spot: [self.farmer, self.strong, self.weak]}, {}, 30,
                           season, cap)
        return self.strong.fieldwork, self.weak.fieldwork

    def test_unequal_workers_the_weakest_leaves_first_and_output_is_recomputed_after_each_release(self):
        self.assertLess(BODY.work_capacity(self.weak), BODY.work_capacity(self.strong))
        need = 9 * C.FOOD_RATION_ADULT
        n_all = sum(BODY.work_capacity(c) for c in (self.farmer, self.strong, self.weak))
        self.assertGreaterEqual(FOOD.land_output_per_day(n_all - BODY.work_capacity(self.weak)), need)
        self.assertLess(FOOD.land_output_per_day(BODY.work_capacity(self.farmer)), need)
        self.assertEqual(self.decide(1.0), (True, False), "คนแรงน้อยออก คนแรงมากยังต้องอยู่")

    def test_a_lean_season_keeps_labour_a_rich_season_releases(self):
        self.assertEqual(self.decide(0.5), (True, True), "หน้าหนาว ผลผลิตครึ่งเดียว ต้องใช้ทุกคน")
        self.strong.fieldwork = self.weak.fieldwork = True
        self.assertEqual(self.decide(1.5), (True, False))

    def test_dependants_count_in_the_consumption_the_remaining_workers_must_cover(self):
        self.assertEqual(self.decide(1.0), (True, False))
        self.strong.fieldwork = self.weak.fieldwork = True
        kids = [setup_person(self.sim, c, self.a, age=6) for c in self.sim.cast[9:15]]
        self.assertEqual(self.decide(1.0, kids), (True, True), "เด็กหกคนกินเพิ่ม ปล่อยใครไม่ได้")

    def test_the_calculations_do_not_move_food_change_workers_or_draw_random_numbers(self):
        eaters = {self.spot: [self.farmer, self.strong, self.weak] + self.others}
        self.sim.granary = {self.spot: 123.0, (0, self.near): 45.0}
        granary, rng = dict(self.sim.granary), self.sim.rng.getstate()
        flags = [c.fieldwork for c in eaters[self.spot]]
        FOOD.store_capacity(self.sim, eaters)
        FOOD.attributed_reserve(self.sim, self.spot, FOOD.assigned_demand(self.sim, eaters))
        self.assertEqual(self.sim.granary, granary)
        self.assertEqual([c.fieldwork for c in eaters[self.spot]], flags)
        self.decide(1.0)
        self.assertEqual(self.sim.rng.getstate(), rng, "การตัดสินใจลงไร่/ปล่อยไม่ใช้เลขสุ่ม")


class AttributedReserveTests(unittest.TestCase):
    """ส่วนของข้าวในยุ้งฉางที่ใช้ร่วมกัน (attributed_reserve) — แบ่งตามสัดส่วนความต้องการชุดเดียวกับเพดาน ไม่นับซ้ำ"""

    def setUp(self):
        self.sim = quiet(S.Sim, seed=5)
        self.a, self.near, self.far = places_by_hops(self.sim)
        self.people = [setup_person(self.sim, c, self.a) for c in self.sim.cast[:12]]

    def reserve(self, eaters_at):
        assigned = FOOD.assigned_demand(self.sim, eaters_at)
        return {spot: FOOD.attributed_reserve(self.sim, spot, assigned) for spot in eaters_at}

    def test_places_sharing_a_granary_cannot_each_claim_its_whole_stock(self):
        here, there = self.people[0], setup_person(self.sim, self.people[1], self.near)
        self.sim.granary = {(0, self.a): 100.0, (0, self.near): 0.0}
        got = self.reserve({(0, self.a): [here], (0, self.near): [there]})
        self.assertAlmostEqual(sum(got.values()), 100.0)
        self.assertAlmostEqual(got[(0, self.a)], 50.0)

    def test_a_high_demand_neighbour_takes_most_of_a_shared_stock(self):
        there = [setup_person(self.sim, p, self.near) for p in self.people[1:11]]
        self.sim.granary = {(0, self.a): 500.0, (0, self.near): 0.0}
        got = self.reserve({(0, self.a): [self.people[0]], (0, self.near): there})
        self.assertLess(got[(0, self.a)], C.FOOD_DEST_STOCK_DAYS * C.FOOD_RATION_ADULT,
                        "สต็อกรวม 500 แต่ส่วนของคนเดียวที่นี่ไม่ถึง 90 วัน")
        self.assertAlmostEqual(sum(got.values()), 500.0)

    def test_asymmetric_coverage_splits_by_assigned_demand(self):
        there = setup_person(self.sim, self.people[1], self.near)
        self.sim.granary = {(0, self.a): 80.0}                           # ข้างบ้านไม่มียุ้งฉาง ส่งถึงจากที่นี่เท่านั้น
        got = self.reserve({(0, self.a): [self.people[0]], (0, self.near): [there]})
        self.assertAlmostEqual(got[(0, self.a)], 40.0)
        self.assertAlmostEqual(got[(0, self.near)], 40.0)

    def test_attributed_reserves_never_exceed_actual_stock_and_zero_demand_claims_nothing(self):
        self.sim.granary = {(0, self.a): 70.0, (0, self.near): 30.0, (0, self.far): 999.0}
        eaters = {(0, self.a): self.people[:3], (0, self.near): [setup_person(self.sim, self.people[5], self.near)],
                  (0, self.far): []}
        got = self.reserve(eaters)
        self.assertLessEqual(sum(got.values()), 100.0 + 1e-9, "ยุ้งฉางที่ไกลเกินระยะไม่ถูกนับ")
        self.assertEqual(got[(0, self.far)], 0.0)
        self.assertAlmostEqual(sum(got.values()), 100.0)


class BoomBustTests(unittest.TestCase):
    """ซ้ำรอยวงจรที่เจอใน seed 12: ที่ที่ไม่มีคนผลิตประจำ ส่วนของยุ้งฉางที่นี่เล็ก ข้างบ้านมียุ้งฉางที่ไม่มีข้าวเข้า"""

    def run_place(self, rounds=20, release_at_local_limit=False):
        sim = quiet(S.Sim, seed=5)
        a, near, _far = places_by_hops(sim)
        people = [setup_person(sim, c, a) for c in sim.cast[:4]]
        for p in people:
            p.fieldwork = False
        sim.granary = {(0, a): 0.0, (0, near): 0.0}
        patches = [food_on(), only(sim, *people), mock.patch.object(FOOD, "_seek_food", lambda *a: None),
                   mock.patch.object(FOOD, "_respond", lambda *a: None)]
        if release_at_local_limit:          # กฎก่อนแก้: เต็มเพดานของที่นี่ = ปล่อยทุกคน
            def local(sim_, spot, assigned):
                lim = C.FOOD_STORE_MONTHS * MONTH * assigned[0].get(spot, 0.0)
                return float("inf") if sim_.granary.get(spot, 0.0) >= lim - 1e-9 else 0.0
            patches.append(mock.patch.object(FOOD, "attributed_reserve", local))
        short, helpers = [], []
        with contextlib.ExitStack() as stack:
            for p in patches:
                stack.enter_context(p)
            for _ in range(rounds):
                unmet = sim.food_stats.get("unmet", 0.0)
                FOOD.tick(sim, 30)
                sim.day += 30
                short.append(sim.food_stats.get("unmet", 0.0) - unmet > 1e-6)
                helpers.append(sum(p.fieldwork for p in people))
                for p in people:
                    p.hunger_days = 0.0             # วัดการขาดของแต่ละรอบ ไม่ให้ใครตายกลางการทดลอง
        return short, helpers

    def test_the_old_rule_runs_short_again_after_releasing_the_only_producers(self):
        short, helpers = self.run_place(release_at_local_limit=True)
        self.assertTrue(any(short[4:]), "ปล่อยทุกคนเมื่อเต็มเพดานของที่นี่แล้วข้าวหมดซ้ำ")
        self.assertIn(0, helpers[4:])

    def test_releasing_only_surplus_labour_prevents_the_shortage_without_keeping_everyone(self):
        short, helpers = self.run_place()
        self.assertFalse(any(short[4:]), f"หลังรอบแรกๆ ไม่ขาดอีก: {short}")
        self.assertTrue(all(h >= 1 for h in helpers[4:]), "ยังมีคนผลิต")
        self.assertLess(min(helpers[4:]), 4, f"ไม่ได้เก็บทุกคนไว้ตลอด: {helpers}")


class CapacityAccountingTests(unittest.TestCase):
    def setUp(self):
        self.sim = quiet(S.Sim, seed=5)
        self.a, self.near, self.far = places_by_hops(self.sim)
        self.person = setup_person(self.sim, self.sim.cast[0], self.a)

    def test_a_person_s_allocated_demand_sums_to_their_ration_over_unique_existing_granaries(self):
        self.sim.granary = {(0, self.a): 0.0, (0, self.near): 0.0}
        stores = FOOD.serving_granaries(self.sim, (0, self.a))
        self.assertEqual(len(stores), len(set(stores)))
        cap = FOOD.store_capacity(self.sim, {(0, self.a): [self.person]})
        self.assertAlmostEqual(sum(cap[s] for s in stores) / (C.FOOD_STORE_MONTHS * MONTH), C.FOOD_RATION_ADULT)

    def test_a_missing_local_granary_is_not_in_the_divisor(self):
        self.sim.granary = {(0, self.near): 0.0}                       # ที่นี่ไม่มียุ้งฉางของตัวเอง
        self.assertEqual(FOOD.serving_granaries(self.sim, (0, self.a)), [(0, self.near)])
        cap = FOOD.store_capacity(self.sim, {(0, self.a): [self.person]})
        self.assertAlmostEqual(cap[(0, self.near)], C.FOOD_STORE_MONTHS * MONTH * C.FOOD_RATION_ADULT)

    def test_demand_with_no_granary_in_reach_is_allocated_to_nobody(self):
        self.sim.granary = {(0, self.far): 0.0}
        self.assertEqual(FOOD.serving_granaries(self.sim, (0, self.a)), [])
        self.assertEqual(FOOD.store_capacity(self.sim, {(0, self.a): [self.person]}), {(0, self.far): 0.0})


class SeasonalSpoilageTests(unittest.TestCase):
    def test_the_annual_spoilage_rate_is_unchanged_by_the_seasons(self):
        year = SEASONS.mean_over(lambda d: SEASONS.factor(SEASONS.SPOIL, d), 0, 365)
        self.assertAlmostEqual(year, 1.0, delta=0.01)
        self.assertAlmostEqual(sum(SEASONS.SPOIL.values()) / 4, 1.0)
        self.assertAlmostEqual(sum(SEASONS.MISHAP.values()) / 4, 1.0)

    def test_food_rots_faster_in_the_hot_wet_season_than_in_winter(self):
        lost = {}
        for label, day in (("rainy", RAINY + 20), ("winter", WINTER + 20)):
            sim = quiet(S.Sim, seed=5)
            a, _near, _far = places_by_hops(sim)
            eater = setup_person(sim, sim.cast[0], a)
            sim.day = sim.food_day = day
            sim.granary = {(0, a): 50.0}
            with food_on(), only(sim, eater):
                FOOD.tick(sim, 30)
            s = sim.food_stats
            lost[label] = s["spoiled"] - s.get("overflow", 0.0)
            keep = pow(2.718281828459045, -C.FOOD_SPOIL_PER_YEAR * FOOD.SEASONS.mean_over(
                lambda d: SEASONS.factor(SEASONS.SPOIL, d), day - 30, 30) * 30 / 365.0)
            self.assertAlmostEqual(lost[label], 50.0 * (1.0 - keep), places=6)
        self.assertGreater(lost["rainy"], lost["winter"])


class SeasonalTravelTests(unittest.TestCase):
    def setUp(self):
        self.sim = quiet(S.Sim, seed=5)
        self.a, self.near, self.far = places_by_hops(self.sim)

    def test_a_winter_journey_takes_longer_than_the_same_journey_in_spring(self):
        spring = TR.shortest_path_days(self.a, self.far, 0, day=SPRING)
        winter = TR.shortest_path_days(self.a, self.far, 0, day=WINTER)
        self.assertGreater(winter, spring)
        self.assertEqual(spring, TR.shortest_path_days(self.a, self.far, 0), "ฤดูใบไม้ผลิคือความเร็วอ้างอิง")
        self.assertAlmostEqual(TR.travel_speed(0, day=WINTER) / TR.travel_speed(0), SEASONS.TRAVEL_SPEED["ฤดูหนาว"])

    def test_the_mishap_chance_rises_in_winter_and_falls_in_spring(self):
        days = C.TRAVEL_ENROUTE_CHECK_DAYS
        p = {name: PHYS.hazard_p(C.TRAVEL_MISHAP_PER_YEAR * SEASONS.MISHAP[name], days) for name in SEASONS.MISHAP}
        self.assertLess(p["ฤดูใบไม้ผลิ"], PHYS.hazard_p(C.TRAVEL_MISHAP_PER_YEAR, days))
        self.assertGreater(p["ฤดูหนาว"], PHYS.hazard_p(C.TRAVEL_MISHAP_PER_YEAR, days))

        class Fixed:                                   # ทอยได้ค่าระหว่างโอกาสของสองฤดู
            def __init__(self, first):
                self.values = [first, 0.0]

            def random(self):
                return self.values.pop(0)

        between = (p["ฤดูใบไม้ผลิ"] + p["ฤดูหนาว"]) / 2
        self.assertIsNone(TR.roll_enroute_event(Fixed(between), days=days, day=SPRING))
        self.assertIsNotNone(TR.roll_enroute_event(Fixed(between), days=days, day=WINTER))


class ContinuityTests(unittest.TestCase):
    def test_the_same_seed_gives_the_same_food_history(self):
        runs = []
        for _ in range(2):
            sim = quiet(S.Sim, seed=9)
            quiet(sim.run, 1500)
            runs.append((sim.day, sim.food_stats, sim.granary))
        self.assertEqual(runs[0], runs[1])

    def test_save_and_load_mid_year_continues_like_one_run(self):
        straight = quiet(S.Sim, seed=7)
        quiet(straight.run, 2000)
        split = quiet(S.Sim, seed=7)
        quiet(split.run, 1000)
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "world.save")
            PS.save_sim(split, path)
            split = PS.load_sim(path)
        quiet(split.run, 1000)
        self.assertEqual(split.day, straight.day)
        self.assertEqual(split.food_stats, straight.food_stats)
        self.assertEqual(split.granary, straight.granary)

    def test_a_save_without_the_new_food_fields_loads_and_its_overfull_granaries_are_cut_into_spoilage(self):
        sim = quiet(S.Sim, seed=5)
        quiet(sim.run, 300)
        for key in ("overflow", "required", "unmet"):
            sim.food_stats.pop(key, None)
        spot = next(iter(sorted(sim.granary)))
        sim.granary[spot] += 1_000_000.0                          # เซฟก่อนมีเพดาน: ยุ้งฉางล้นเกินปีหนึ่ง
        sim.food_stats["endowed"] += 1_000_000.0                  # ข้าวที่เคยได้มาตามบัญชีของเซฟเก่า
        rng = sim.rng.getstate()
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "old.save")
            with open(path, "wb") as f:
                pickle.dump({"save_version": 30, "sim": sim}, f)
            back = PS.load_sim(path)
        self.assertEqual(back.rng.getstate(), rng, "ย้ายรุ่นไม่แตะ RNG")
        gap = in_ledger(back)
        quiet(back.run, 400)
        self.assertGreater(back.food_stats["overflow"], 900_000.0)
        self.assertAlmostEqual(in_ledger(back), gap, delta=1e-6 * FOOD.total_held(back) + 1e-6)
        for stock in back.granary.values():
            self.assertGreaterEqual(stock, 0.0)


if __name__ == "__main__":
    unittest.main()
