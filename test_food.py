# -*- coding: utf-8 -*-
"""ยุ้งฉางหมู่บ้าน (tiandao/food.py): อาหารมีที่มา คนกินจริง ขาดแล้วหิว ย้ายหา หรืออดตาย

    python -m unittest test_food -v

สิ่งที่ล็อกไว้ (SIM_DAO_AUTONOMOUS_WORLD_DESIGN_TH.md §6.1, §7.4, §13.1–13.2)
  · บัญชีอาหารปิดเสมอ: ของที่มีอยู่ = ที่ได้มา − ที่ออกไป ไม่มีข้าวเกิดหรือหายโดยไม่มีบัญชี
  · ผลผลิตคิดตามวันที่ทำงานจริง ไม่ให้ล่วงหน้า และที่ดินหนึ่งแห่งมีเพดาน
  · ข้าวไม่พอ ทุกคนได้ส่วนเท่ากันตามความต้องการ ไม่ใช่ cid ต่ำได้ก่อน
  · เส้นตายอดตายไม่ถูกข้าม แม้เทิร์นของคนนั้นจะอยู่อีกหลายปี
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
    """ให้ FOOD.tick เห็นเฉพาะคนกลุ่มนี้ — แยกกฎหนึ่งข้อออกจากประชากรทั้งโลก"""
    saved = sim.alive_cids
    sim.alive_cids = {ch.cid for ch in people}
    try:
        yield
    finally:
        sim.alive_cids = saved


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

    def test_food_beyond_reach_sends_the_hungry_on_the_road(self):
        eater = setup_person(self.sim, self.people[0], self.a)
        self.sim.granary[(0, self.far)] = 1000.0
        before = {cid for _d, cid in self.sim.queue}
        with food_on(), only(self.sim, eater), quiet_emit(self.sim):
            FOOD.tick(self.sim, 30)
        self.assertGreater(eater.hunger_days, 0)
        self.assertGreaterEqual(eater.travel_dest, 0, "ต้องออกเดินทางไปหาข้าว")
        self.assertEqual(sum(cid == eater.cid for _d, cid in self.sim.queue), 1, "คิวใบเดียวต่อคน")
        self.assertIn((eater.travel_arrival_day, eater.cid), self.sim.queue)
        self.assertEqual({cid for _d, cid in self.sim.queue} - {eater.cid}, before - {eater.cid})

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
