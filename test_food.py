# -*- coding: utf-8 -*-
"""ยุ้งฉางหมู่บ้าน (tiandao/food.py): อาหารมีที่มา คนกินจริง ขาดแล้วหิว ย้ายหา หรืออดตาย

    python -m unittest test_food -v

สิ่งที่ล็อกไว้ (SIM_DAO_AUTONOMOUS_WORLD_DESIGN_TH.md §6.1, §7.4, §13.1–13.2)
  · บัญชีอาหารปิดเสมอ: ของที่มีอยู่ = ที่ได้มา − ที่ออกไป ไม่มีข้าวเกิดหรือหายโดยไม่มีบัญชี
  · ผลผลิตคิดตามวันที่ทำงานจริง ไม่ให้ล่วงหน้า และที่ดินหนึ่งแห่งมีเพดาน
  · ข้าวไม่พอ ทุกคนได้ส่วนเท่ากันตามความต้องการ ไม่ใช่ cid ต่ำได้ก่อน
  · เส้นตายอดตายไม่ถูกข้าม แม้เทิร์นของคนนั้นจะอยู่อีกหลายปี
  · ข้าวขาด ผู้ใหญ่ที่ไม่ได้ผลิตอาหารลงไร่จนพอหรือที่ดินเต็ม แล้วกลับไปทำงานเดิมเมื่อข้าวเหลือเฟือ
  · ปิดระบบอยู่ = โลกเดินเหมือนเดิมทุกประการ
"""
import contextlib
import heapq
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
from tiandao import places as PL
from tiandao import sim as S
from tiandao import travel as TR
from tiandao import wages as WAGES


def quiet(fn, *a, **kw):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*a, **kw)


def food_on():
    return mock.patch.object(C, "FOOD_ENABLED", True)


def no_spoil():
    """แยกกฎที่ทดสอบออกจากการเน่าของยุ้งฉางระหว่างรอบ"""
    return mock.patch.object(C, "FOOD_SPOIL_PER_YEAR", 0.0)


@contextlib.contextmanager
def only(sim, *people):
    """ให้ FOOD.tick เห็นเฉพาะคนกลุ่มนี้ — แยกกฎหนึ่งข้อออกจากประชากรทั้งโลก

    ขยับ `_alive_ver` ด้วย ไม่งั้นแคชของ alive_sorted()/living_in() ยังเห็นคนทั้งโลก (แคชดูแค่ตัวนับนี้)
    """
    saved = sim.alive_cids
    sim.alive_cids = {ch.cid for ch in people}
    sim._alive_ver = getattr(sim, "_alive_ver", 0) + 1
    try:
        yield
    finally:
        sim.alive_cids = saved
        sim._alive_ver += 1


def setup_person(sim, ch, place, *, food=0.0, profession="บัณฑิต", age=30, realm=0):
    ch.alive, ch.realm, ch.place, ch.world_id = True, realm, place, 0
    ch.profession = profession
    ch.born_day = sim.day - age * 365
    ch.hidden, ch.travel_dest, ch.seclude_until = False, -1, 0
    ch.food, ch.hunger_days, ch.food_fed, ch.food_missed = food, 0.0, 0.0, 0.0
    for attr in ("is_spirit", "is_beast", "is_lord"):
        setattr(ch, attr, False)
    ch.sentient = True
    return ch


def places_by_hops(sim):
    """(ที่หนึ่ง, ที่ห่างหนึ่งก้าว, ที่ที่ไกลเกินระยะส่งข้าวจากที่แรก) ในโลกมนุษย์"""
    home = PL.places_in(sim.worlds[0].place_key)
    for a in home:
        near = [b for b in home if sim.hops_between(a, b) == 1]
        far = [b for b in home if sim.hops_between(a, b) > C.FOOD_REACH_HOPS]
        if near and far:
            return a, near[0], far[0]
    raise AssertionError("ไม่มีสถานที่ที่ห่างพอในโลกมนุษย์")


class FoodRulesTests(unittest.TestCase):
    def setUp(self):
        self.sim = quiet(S.Sim, seed=5)
        self.sim.granary = {}
        self.a, self.near, self.far = places_by_hops(self.sim)
        self.people = [ch for ch in self.sim.cast[:4]]

    def test_a_farmer_is_paid_for_the_days_worked_and_land_has_a_ceiling(self):
        farmer = setup_person(self.sim, self.people[0], self.a, food=100.0, profession="ชาวนา")
        with food_on(), only(self.sim, farmer):
            FOOD.tick(self.sim, 30)
        season = FOOD.season_mean(self.sim.day - 30, 30)
        made = FOOD.land_output_per_day(1) * 30 * season
        self.assertAlmostEqual(self.sim.food_stats["produced"], made, places=6)
        self.assertLess(FOOD.land_output_per_day(1), C.FOOD_PER_WORKER_DAY)
        self.assertLess(FOOD.land_output_per_day(1000), C.FOOD_LAND_CAP_DAY + 1e-9)
        self.assertGreater(FOOD.land_output_per_day(2), FOOD.land_output_per_day(1))

    def test_an_away_farmer_produces_nothing(self):
        farmer = setup_person(self.sim, self.people[0], self.a, food=100.0, profession="ชาวนา")
        farmer.travel_dest = self.near
        with food_on(), only(self.sim, farmer):
            FOOD.tick(self.sim, 30)
        self.assertEqual(self.sim.food_stats["produced"], 0.0)
        self.assertAlmostEqual(farmer.food, 100.0 - 30 * C.FOOD_RATION_ADULT)

    def test_scarce_food_is_shared_by_need_not_by_cid(self):
        low, high = (setup_person(self.sim, ch, self.a) for ch in self.people[:2])
        child = setup_person(self.sim, self.people[2], self.a, age=5)
        self.sim.granary[(0, self.a)] = 25.0            # ต้องการ 30+30+15 = 75 มีแค่ 25 = หนึ่งในสาม
        with food_on(), no_spoil(), only(self.sim, low, high, child):
            FOOD.tick(self.sim, 30)
        self.assertAlmostEqual(low.food_fed, high.food_fed)
        self.assertAlmostEqual(low.food_fed, 10.0)
        self.assertAlmostEqual(child.food_fed, 10.0, msg="เด็กได้สัดส่วนเดียวกันของความต้องการที่น้อยกว่า")
        self.assertAlmostEqual(low.hunger_days, 20.0)

    def test_nearby_granaries_feed_a_place_that_has_none_and_the_road_costs_food(self):
        eater = setup_person(self.sim, self.people[0], self.a)
        self.sim.granary[(0, self.near)] = 1000.0
        with food_on(), no_spoil(), only(self.sim, eater):
            FOOD.tick(self.sim, 30)
        self.assertEqual(eater.hunger_days, 0.0)
        sent = 1000.0 - self.sim.granary[(0, self.near)]
        self.assertAlmostEqual(sent * (1 - C.FOOD_CARRY_LOSS_PER_HOP), 30.0, places=6)
        self.assertAlmostEqual(self.sim.food_stats["carried_lost"], sent - 30.0, places=6)

    def test_when_food_runs_short_idle_adults_farm_until_the_granary_is_plentiful(self):
        # แดนที่คนผลิตอาหารตายหมดและไม่มีข้าวที่ไหนในระยะส่ง: ผู้ใหญ่ที่อยู่ลงไร่แทน แล้วกลับไปทำงานเดิมเมื่อข้าวเหลือเฟือ
        people = [setup_person(self.sim, ch, self.a, food=60.0) for ch in self.people[:3]]
        with food_on(), no_spoil(), only(self.sim, *people):
            FOOD.tick(self.sim, 30)
            farming = [ch for ch in people if ch.fieldwork]
            self.assertTrue(farming, "ข้าวขาดและไม่มีที่ไหนให้ไป ต้องมีคนลงไร่")
            self.assertEqual(self.sim.food_stats["took_up_farming"], len(farming))
            self.assertEqual(self.sim.food_stats["produced"], 0.0, "ผลผลิตเริ่มรอบหน้า ไม่ให้ย้อนหลัง")
            self.assertFalse(WAGES.earns_wages(farming[0], self.sim.day), "คนลงไร่ได้เงินจากลิ้นชักไร่ ไม่ใช่ค่าแรงตลาด")
            for _ in range(24):
                FOOD.tick(self.sim, 30)
        self.assertGreater(self.sim.food_stats["produced"], 0.0)
        self.assertTrue(all(ch.alive for ch in people))
        self.assertGreaterEqual(self.sim.food_stats["left_farming"], 1, "ข้าวเหลือเฟือแล้วกลับไปทำงานเดิม")

    def test_nobody_takes_up_farming_on_land_that_is_already_full(self):
        crowd = [setup_person(self.sim, ch, self.a, food=60.0) for ch in self.sim.cast[:60]]
        with food_on(), no_spoil(), only(self.sim, *crowd):
            FOOD.tick(self.sim, 30)
        n = sum(ch.fieldwork for ch in crowd)
        season = FOOD.season_mean(self.sim.day - 30, 30)
        gain = lambda k: (FOOD.land_output_per_day(k) - FOOD.land_output_per_day(k - 1)) * season
        self.assertLess(n, len(crowd))
        self.assertGreaterEqual(gain(n), C.FOOD_RATION_ADULT, "คนสุดท้ายที่ลงไร่ยังเลี้ยงตัวเองได้")
        self.assertLess(gain(n + 1), C.FOOD_RATION_ADULT, "คนถัดไปเพิ่มผลผลิตไม่ถึงสำรับที่ตัวเองกิน")

    def test_when_supply_falls_short_they_leave_while_provisions_last(self):
        eater = setup_person(self.sim, self.people[0], self.a)
        trip = TR.shortest_path_days(self.a, self.far, eater.realm, character=eater)
        eater.food = 20 + trip + C.FOOD_TRIP_MARGIN_DAYS + 1      # หลังกินรอบนี้ยังพอเดินทางไปถึง
        self.sim.granary[(0, self.a)] = 10.0                        # ยุ้งฉางที่นี่ให้ได้ไม่ครบ
        self.sim.granary[(0, self.far)] = 1000.0
        before = {cid for _d, cid in self.sim.queue}
        with food_on(), no_spoil(), only(self.sim, eater), quiet_emit(self.sim):
            FOOD.tick(self.sim, 30)
        self.assertEqual(eater.hunger_days, 0.0, "ยังไม่หิว แต่ออกเพราะยุ้งฉางเริ่มไม่พอ")
        self.assertEqual(eater.travel_dest, self.far)
        self.assertEqual(sum(cid == eater.cid for _d, cid in self.sim.queue), 1, "คิวใบเดียวต่อคน")
        self.assertIn((eater.travel_arrival_day, eater.cid), self.sim.queue)
        self.assertEqual({cid for _d, cid in self.sim.queue} - {eater.cid}, before - {eater.cid})

    def test_nobody_sets_out_on_a_trip_they_cannot_survive(self):
        eater = setup_person(self.sim, self.people[0], self.a, food=0.0)
        self.sim.granary[(0, self.far)] = 1000.0
        with food_on(), no_spoil(), only(self.sim, eater), quiet_emit(self.sim):
            FOOD.tick(self.sim, 30)                                 # หิวแล้ว 30 วัน ไม่มีเสบียงเหลือ
        trip = TR.shortest_path_days(self.a, self.far, eater.realm, character=eater)
        self.assertGreater(trip, C.FOOD_STARVE_DAYS - 30 - C.FOOD_TRIP_MARGIN_DAYS)
        self.assertEqual(eater.travel_dest, -1, "ไปไม่ถึงก่อนอดตาย จึงอยู่ที่เดิม")
        self.assertEqual(self.sim.food_stats["migrated"], 0)

    def test_a_cultivator_past_bigu_does_not_eat(self):
        sage = setup_person(self.sim, self.people[0], self.a, realm=C.FOOD_BIGU_REALM)
        with food_on(), only(self.sim, sage):
            FOOD.tick(self.sim, 365)
        self.assertEqual(sage.hunger_days, 0.0)
        self.assertEqual(self.sim.food_stats["eaten"], 0.0)
        with food_on():
            self.assertEqual(FOOD.fed_share(sage), 1.0)

    def test_the_dead_leave_their_provisions_to_the_granary(self):
        eater = setup_person(self.sim, self.people[0], self.a, food=40.0)
        with food_on():
            quiet(self.sim.kill, eater, "ทดสอบ", natural=True)
        self.assertEqual(eater.food, 0.0)
        self.assertAlmostEqual(self.sim.granary[(0, self.a)], 40.0)

    def test_hunger_stops_the_body_from_refuelling(self):
        fed, hungry = (setup_person(self.sim, ch, self.a) for ch in self.people[:2])
        fed.fuel = hungry.fuel = 0.3
        BODY.tick(fed, 10, day=self.sim.day, fed=1.0)
        BODY.tick(hungry, 10, day=self.sim.day, fed=0.0)
        self.assertGreater(fed.fuel, hungry.fuel)


class SeclusionMealsTests(unittest.TestCase):
    """ผู้ปิดด่านได้ข้าวส่งถึงถ้ำจากยุ้งฉางของที่นั้น ไม่ต้องออกมาเพราะเสบียงติดตัว 30 วันหมด"""

    def setUp(self):
        self.sim = quiet(S.Sim, seed=5)
        self.sim.granary, self.sim.market_till, self.sim.farm_till = {}, {}, {}
        self.a, self.near, self.far = places_by_hops(self.sim)
        # เสบียงติดตัวเต็มแล้ว จะได้วัดแค่ข้าวส่งถึงถ้ำ ไม่ปนกับการซื้อเสบียงเติม
        self.monk = setup_person(self.sim, self.sim.cast[0], self.a,
                                 food=C.FOOD_PACK_DAYS * C.FOOD_RATION_ADULT)
        self.monk.hidden, self.monk.seclude_until = True, self.sim.day + 5 * 365
        self.monk.money = {}

    def test_a_secluded_cultivator_eats_from_the_local_granary_and_stays_in(self):
        self.sim.granary[(0, self.a)] = 1000.0
        with food_on(), no_spoil(), only(self.sim, self.monk):
            for _ in range(12):
                FOOD.tick(self.sim, 30)
        self.assertEqual(self.monk.hunger_days, 0.0)
        self.assertGreater(self.monk.seclude_until, self.sim.day, "ยังอยู่ในด่านครบปี")
        self.assertAlmostEqual(self.sim.granary[(0, self.a)], 1000.0 - 360.0)

    def test_with_wages_on_they_come_out_to_earn_before_going_broke(self):
        self.sim.granary[(0, self.a)] = 1000.0
        keep = C.FOOD_SECLUDE_KEEP_DAYS * C.FOOD_RATION_ADULT * C.FOOD_PRICE
        WAGES.move_gold(self.sim, self.monk, keep + 30 * C.FOOD_PRICE + 1.0)
        with food_on(), no_spoil(), mock.patch.object(C, "WAGES_ENABLED", True), \
                only(self.sim, self.monk):
            FOOD.tick(self.sim, 30)
            self.assertGreater(self.monk.seclude_until, self.sim.day, "ยังพอจ่าย อยู่ต่อ")
            FOOD.tick(self.sim, 30)
        self.assertEqual(self.monk.seclude_until, self.sim.day, "เงินเหลือต่ำกว่าเงินสำรอง ออกมาหาเลี้ยงชีพ")
        self.assertIn("เงิน", self.monk.seclude_cut)
        self.assertGreater(WAGES.gold(self.sim, self.monk), 0, "ออกมาตอนยังมีเงินเหลือ ไม่ใช่ตอนหมดตัว")


@contextlib.contextmanager
def quiet_emit(sim):
    with contextlib.redirect_stdout(io.StringIO()):
        yield


class FoodInTheRunningWorldTests(unittest.TestCase):
    def test_the_food_ledger_always_closes(self):
        with food_on():
            sim = quiet(S.Sim, seed=11)
            quiet(sim.run, 6000)
        self.assertGreater(sim.food_stats["produced"], 0)
        self.assertGreater(sim.food_stats["eaten"], 0)
        self.assertAlmostEqual(FOOD.total_held(sim), FOOD.ledger_balance(sim.food_stats), delta=1e-6
                               * max(1.0, sim.food_stats["produced"]))

    def test_starvation_is_not_skipped_while_the_turn_is_years_away(self):
        with food_on():
            sim = quiet(S.Sim, seed=11)
            quiet(sim.run, 300)
            victim = next(ch for ch in sim.living() if FOOD.eats(ch) and ch.age(sim.day) >= 14)
            for ch in sim.cast:
                ch.food = 0.0 if ch.food is not None or FOOD.eats(ch) else ch.food
            sim.granary = {}
            sim.queue = [(d if cid != victim.cid else sim.day + 10 * 365, cid) for d, cid in sim.queue]
            heapq.heapify(sim.queue)
            start = sim.day
            with mock.patch.object(FOOD, "_working", return_value=False):
                while victim.alive and sim.day < start + 365:
                    quiet(sim.step)
        self.assertFalse(victim.alive)
        self.assertEqual(victim.death_cause, "อดอาหาร")
        self.assertLessEqual(victim.death_day - start, C.FOOD_STARVE_DAYS + 2 * C.WORLD_TICK_DAYS)

    def test_a_secluded_cultivator_whose_provisions_run_out_comes_out_early_with_partial_gains(self):
        with food_on():
            sim = quiet(S.Sim, seed=11)
            quiet(sim.run, 300)
            monk = next(ch for ch in sim.living() if FOOD.eats(ch) and ch.age(sim.day) >= 14
                        and ch.travel_dest < 0 and not ch.hidden)
            sim.granary = {}
            monk.food = 10.0
            monk.hidden, monk.seclude_until = True, sim.day + 5 * 365
            monk.seclude_snap = {"day": sim.day, "gamma": 1.0}
            sim.requeue(monk, monk.seclude_until)
            insight = monk.insight
            start = sim.day
            with mock.patch.object(FOOD, "_working", return_value=False):
                while monk.alive and monk.seclude_until and sim.day < start + 365:
                    quiet(sim.step)
                while monk.alive and monk.hidden and sim.day < start + 365:
                    quiet(sim.step)
        self.assertTrue(monk.alive)
        self.assertFalse(monk.hidden, "ต้องออกจากด่านก่อนครบห้าปี")
        self.assertLess(sim.day - start, 365)
        out = [e for e in sim.log if e.kind == "ออกจากด่าน" and e.actor == monk.cid]
        self.assertEqual(out[-1].deltas.get("เหตุที่ออก"), "เสบียงหมดก่อนครบกำหนด")
        gained = monk.insight - insight
        self.assertLess(gained, C.SECLUDE_INSIGHT_PER_YEAR, "ได้ผลเท่าเวลาที่อยู่จริง ไม่ปัดเป็นหนึ่งปี")

    def test_switched_off_the_world_never_touches_food(self):
        sim = quiet(S.Sim, seed=11)
        quiet(sim.run, 3000)
        self.assertEqual(sim.granary, {})
        self.assertTrue(all(v == 0 for v in sim.food_stats.values()))
        self.assertTrue(all(ch.food is None for ch in sim.cast))


class FoodSaveTests(unittest.TestCase):
    def test_a_version_2_save_gets_an_empty_granary_without_moving_the_rng(self):
        sim = quiet(S.Sim, seed=5)
        quiet(sim.run, 200)
        del sim.granary, sim.food_stats, sim.food_day
        rng_state = sim.rng.getstate()
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "world.save")
            with open(path, "wb") as f:
                pickle.dump({"save_version": 2, "sim": sim}, f)
            loaded = PS.load_sim(path)
        self.assertEqual(loaded.granary, {})
        self.assertEqual(loaded.food_stats, FOOD.new_stats())
        self.assertEqual(loaded.food_day, loaded.day)
        self.assertEqual(loaded.rng.getstate(), rng_state)

    def test_save_and_load_with_food_on_continues_like_one_run(self):
        with food_on():
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
        self.assertEqual(split.food_stats, straight.food_stats)
        self.assertEqual(split.granary, straight.granary)
        self.assertEqual([c.food for c in split.cast], [c.food for c in straight.cast])


if __name__ == "__main__":
    unittest.main()
