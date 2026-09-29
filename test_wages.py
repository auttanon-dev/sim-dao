# -*- coding: utf-8 -*-
"""ค่าแรงตามเวลาทำงาน (tiandao/wages.py) และค่าข้าว (tiandao/food.py): เงินที่ได้ต้องมีคนจ่าย

    python -m unittest test_wages -v

สิ่งที่ล็อกไว้ (SIM_DAO_AUTONOMOUS_WORLD_DESIGN_TH.md §6.1, §9.1–9.2, invariant 4 และ 12)
  · เงินไม่เกิดและไม่หายในรอบค่าแรงและค่าข้าว นอกจากทุนตั้งต้นที่ประกาศไว้ (wage_stats["issued"])
  · ค่าแรงมาจากเงินที่คนใช้จ่าย จ่ายให้คนที่ทำงานอยู่จริง ใกล้ได้มากกว่าไกล ไกลเกินระยะไม่ได้
  · งานสามัญไม่เสกเงินต่อเทิร์นเมื่อเปิดค่าแรง
  · ค่าข้าวไปถึงคนผลิตที่ไร่ต้นทาง ผู้ใหญ่ที่จ่ายไม่ไหวทำงานแลกข้าว นักโทษกินข้าวคุก เด็กให้พ่อแม่จ่ายหรือหมู่บ้านเลี้ยง
"""
import contextlib
import math
import io
import os
import pickle
import tempfile
import unittest
from unittest import mock

from tiandao import config as C
from tiandao import events as E
from tiandao import food as FOOD
from tiandao import persist as PS
from tiandao import places as PL
from tiandao import sim as S
from tiandao import wages as WAGES
from test_food import only, places_by_hops, setup_person


def quiet(fn, *a, **kw):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*a, **kw)


def switches(food=False, wages=True, guardians=False):
    stack = contextlib.ExitStack()
    stack.enter_context(mock.patch.object(C, "FOOD_ENABLED", food))
    stack.enter_context(mock.patch.object(C, "WAGES_ENABLED", wages))
    stack.enter_context(mock.patch.object(C, "GUARDIANS_ENABLED", guardians))
    return stack


def money_everywhere(sim):
    return sum(WAGES.total_gold(sim, tier) for tier in {w.tier for w in sim.worlds})


class WageRulesTests(unittest.TestCase):
    def setUp(self):
        self.sim = quiet(S.Sim, seed=5)
        self.sim.granary, self.sim.market_till, self.sim.farm_till = {}, {}, {}
        self.a, self.near, self.far = places_by_hops(self.sim)
        self.people = list(self.sim.cast[:6])
        for ch in self.people:
            ch.gold_endowed = True
            ch.money = {}
        self.sim.market_reserve = {}
        for name in ("MARKET_RESERVE_SHARE", "MINE_GOLD_PER_YEAR"):    # เทสต์การแบ่งค่าแรง — ทุนสำรองและเหมืองมีเทสต์ของตัวเอง
            patch = mock.patch.object(C, name, 0.0)
            patch.start()
            self.addCleanup(patch.stop)

    def test_the_market_keeps_its_share_of_spending_as_a_reserve_up_to_its_depth(self):
        rich = setup_person(self.sim, self.people[0], self.a, realm=5)
        worker = setup_person(self.sim, self.people[1], self.a)
        self.give(rich, 1000.0)
        self.sim.market_demand = {(0, self.a): 10.0 ** 9}       # มีคนมาขายของมาก — เพดานคือความลึก
        before = money_everywhere(self.sim)                 # นับทุนสำรองด้วย (wages.total_gold)
        with switches(), only(self.sim, rich, worker), mock.patch.object(C, "MARKET_RESERVE_SHARE", 0.03):
            WAGES.tick(self.sim, 30)
        spent = self.sim.wage_stats["spent"]
        kept = min(spent * 0.03, WAGES.market_depth(self.sim, 0, self.a))
        self.assertAlmostEqual(self.sim.market_reserve[(0, self.a)], kept)
        self.assertAlmostEqual(WAGES.gold(self.sim, worker), spent - kept)
        self.assertAlmostEqual(money_everywhere(self.sim), before, places=6)
        self.sim.market_reserve[(0, self.a)] = WAGES.market_depth(self.sim, 0, self.a)
        with switches(), only(self.sim, rich, worker), mock.patch.object(C, "MARKET_RESERVE_SHARE", 0.03):
            WAGES.tick(self.sim, 30)
        self.assertAlmostEqual(self.sim.market_reserve[(0, self.a)], WAGES.market_depth(self.sim, 0, self.a),
                               msg="เต็มความลึกแล้วไม่กันเพิ่ม")

    def test_a_reserve_above_a_years_sales_goes_back_to_wages(self):
        worker = setup_person(self.sim, self.people[1], self.a)
        self.sim.market_reserve = {(0, self.a): 50.0}
        self.sim.market_demand = {(0, self.a): 20.0}
        before = money_everywhere(self.sim)
        with switches(), only(self.sim, worker), mock.patch.object(C, "MARKET_RESERVE_SHARE", 0.03):
            WAGES.tick(self.sim, 30)
        cap = 20.0 * math.exp(-30 / 365.0)
        self.assertAlmostEqual(self.sim.market_reserve[(0, self.a)], cap)
        self.assertAlmostEqual(WAGES.gold(self.sim, worker), 50.0 - cap, msg="ส่วนเกินเป็นค่าแรง")
        self.assertAlmostEqual(money_everywhere(self.sim), before, places=6)

    def test_a_worked_mine_fills_its_tiers_purse_and_pays_miners_only_what_exceeds_a_years_output(self):
        world, mine = next((w, p) for w in self.sim.worlds for p in PL.places_in(w.place_key) if WAGES.is_mine(p))
        miner = setup_person(self.sim, self.people[1], mine)
        self.sim.move_world(miner, world.wid)
        miner.place = mine
        self.sim.mine_purse, self.sim.mine_recent = {}, {}
        before = money_everywhere(self.sim)
        with switches(), only(self.sim, miner), mock.patch.object(C, "MINE_GOLD_PER_YEAR", 365.0):
            WAGES.tick(self.sim, 30)
        self.assertAlmostEqual(self.sim.mine_purse[world.tier], 30.0, msg="ทองที่ขุดได้รอรับซื้อวัตถุดิบ")
        self.assertAlmostEqual(WAGES.gold(self.sim, miner), 0.0)
        self.assertAlmostEqual(money_everywhere(self.sim) - before, 30.0)
        self.assertAlmostEqual(sum(self.sim.gold_flows["mine_output"].values()), 30.0)
        self.sim.mine_purse[world.tier] += 100.0                 # กองทุนเกินผลผลิตหนึ่งปี (ไม่มีใครขายของมานาน)
        WAGES.record(self.sim, "test", world.tier, 100.0)
        with switches(), only(self.sim, miner), mock.patch.object(C, "MINE_GOLD_PER_YEAR", 365.0):
            WAGES.tick(self.sim, 30)
        recent = self.sim.mine_recent[world.tier]
        self.assertAlmostEqual(self.sim.mine_purse[world.tier], recent)
        self.assertAlmostEqual(WAGES.gold(self.sim, miner), 160.0 - recent, msg="ส่วนเกินเป็นค่าแรงคนงานเหมือง")
        mined = sum(self.sim.gold_flows["mine_output"].values())
        miner.place = next(p for p in PL.places_in(world.place_key) if not WAGES.is_mine(p))
        with switches(), only(self.sim, miner), mock.patch.object(C, "MINE_GOLD_PER_YEAR", 365.0):
            WAGES.tick(self.sim, 30)
        self.assertAlmostEqual(sum(self.sim.gold_flows["mine_output"].values()), mined, msg="ไม่มีคนงานในเหมือง ไม่มีทองขุด")

    def test_a_settlement_treasury_pays_public_wages_only_from_gold_above_a_year_of_childrens_meals(self):
        worker = setup_person(self.sim, self.people[1], self.a)
        kid = setup_person(self.sim, self.people[2], self.a, age=6)
        tier = self.sim.world(0).tier
        floor = 365.0 * C.FOOD_RATION_CHILD * C.FOOD_PRICE             # เด็กหนึ่งคนในระยะ
        self.sim.settlement_treasury = {(0, self.a): {tier: floor + 100.0}}
        before = money_everywhere(self.sim)
        with switches(), only(self.sim, worker, kid), mock.patch.object(C, "CIVIC_SPEND_RATE", 0.2):
            WAGES.tick(self.sim, 30)
        spent = 100.0 * (1.0 - math.exp(-0.2 * 30 / 365.0))
        self.assertAlmostEqual(self.sim.settlement_treasury[(0, self.a)][tier], floor + 100.0 - spent)
        self.assertAlmostEqual(WAGES.gold(self.sim, worker), spent, msg="งานสาธารณะเป็นค่าแรงของคนที่นั่น")
        self.assertAlmostEqual(money_everywhere(self.sim), before, places=6)
        self.sim.settlement_treasury = {(0, self.a): {tier: floor}}
        with switches(), only(self.sim, worker, kid), mock.patch.object(C, "CIVIC_SPEND_RATE", 0.2):
            WAGES.tick(self.sim, 30)
        self.assertAlmostEqual(self.sim.settlement_treasury[(0, self.a)][tier], floor, msg="ไม่ต่ำกว่าพื้นเลี้ยงเด็ก")

    def give(self, ch, gold):
        WAGES.move_gold(self.sim, ch, gold)

    def test_spending_becomes_wages_for_nearby_workers_and_no_gold_is_made(self):
        rich = setup_person(self.sim, self.people[0], self.a, realm=5)
        here = setup_person(self.sim, self.people[1], self.a)
        close = setup_person(self.sim, self.people[2], self.near)
        distant = setup_person(self.sim, self.people[3], self.far)
        self.give(rich, 1000.0)
        before = money_everywhere(self.sim)
        with switches(), only(self.sim, rich, here, close, distant):
            WAGES.tick(self.sim, 30)
        self.assertAlmostEqual(money_everywhere(self.sim), before, places=6)
        spent = self.sim.wage_stats["spent"]
        self.assertGreater(spent, 0)
        self.assertAlmostEqual(WAGES.gold(self.sim, here), spent * 1.0 / 1.5, places=6)
        self.assertAlmostEqual(WAGES.gold(self.sim, close), spent * 0.5 / 1.5, places=6)
        self.assertEqual(WAGES.gold(self.sim, distant), 0.0, "ไกลเกินระยะไม่ได้ค่าแรงจากที่นี่")
        self.assertEqual(WAGES.gold(self.sim, rich), 1000.0 - spent, "ผู้ฝึกขั้นสูงใช้จ่ายแต่ไม่รับค่าแรง")

    def test_only_those_actually_at_work_are_paid(self):
        rich = setup_person(self.sim, self.people[0], self.a, realm=5)
        worker = setup_person(self.sim, self.people[1], self.a)
        away = setup_person(self.sim, self.people[2], self.a)
        away.travel_dest = self.near
        child = setup_person(self.sim, self.people[3], self.a, age=8)
        self.give(rich, 500.0)
        with switches(), only(self.sim, rich, worker, away, child):
            WAGES.tick(self.sim, 30)
        self.assertAlmostEqual(WAGES.gold(self.sim, worker), self.sim.wage_stats["spent"])
        self.assertEqual(WAGES.gold(self.sim, away), 0.0)
        self.assertEqual(WAGES.gold(self.sim, child), 0.0)

    def test_money_with_nobody_to_pay_waits_in_the_till(self):
        rich = setup_person(self.sim, self.people[0], self.far, realm=5)
        self.give(rich, 500.0)
        with switches(), only(self.sim, rich):
            WAGES.tick(self.sim, 30)
        self.assertAlmostEqual(self.sim.market_till[(0, self.far)], self.sim.wage_stats["spent"])
        self.assertEqual(self.sim.wage_stats["paid"], 0.0)

    def test_the_starting_purse_is_issued_once_and_counted(self):
        newcomer = setup_person(self.sim, self.people[0], self.a)
        newcomer.gold_endowed = False
        with switches(), only(self.sim, newcomer):
            WAGES.tick(self.sim, 30)
            WAGES.tick(self.sim, 30)
        self.assertEqual(self.sim.wage_stats["issued"], C.WAGE_START_GOLD)

    def test_everyday_jobs_no_longer_mint_gold_per_turn(self):
        farmer = setup_person(self.sim, self.people[0], self.a, profession="ชาวนา")
        table = {e["kind"]: e for e in E.EVENT_TABLE}
        world = self.sim.worlds[0]
        for kind in ("ทำนา", "ค้าขายทั่วไป", "ตีเหล็กชาวบ้าน", "รักษาชาวบ้าน", "ปกป้องชาวบ้าน",
                     "ขูดรีดชาวบ้าน", "ลาดตระเวน"):
            ev = table.get(kind, {"kind": kind, "tags": [], "gap": (3, 15)})
            with switches():
                quiet(self.sim.resolve, ev, farmer, None, world, 10, self.sim.rng)
            self.assertEqual(sum(farmer.money.values()), 0.0, kind)
        with switches(wages=False):
            quiet(self.sim.resolve, table["ทำนา"], farmer, None, world, 10, self.sim.rng)
        self.assertGreater(sum(farmer.money.values()), 0.0, "ปิดค่าแรงอยู่ งานยังจ่ายแบบเดิม")


class FoodMoneyTests(unittest.TestCase):
    def setUp(self):
        self.sim = quiet(S.Sim, seed=5)
        self.sim.granary, self.sim.market_till, self.sim.farm_till = {}, {}, {}
        self.a, self.near, self.far = places_by_hops(self.sim)
        self.people = list(self.sim.cast[:6])
        for ch in self.people:
            ch.gold_endowed = True
            ch.money = {}

    def test_buyers_pay_the_farmer_who_grew_it(self):
        farmer = setup_person(self.sim, self.people[0], self.a, food=0.0, profession="ชาวนา")
        buyer = setup_person(self.sim, self.people[1], self.a)
        WAGES.move_gold(self.sim, buyer, 100.0)
        before = money_everywhere(self.sim)
        with switches(food=True), mock.patch.object(C, "FOOD_SPOIL_PER_YEAR", 0.0), \
                only(self.sim, farmer, buyer):
            FOOD.tick(self.sim, 30)
        self.assertAlmostEqual(money_everywhere(self.sim), before, places=6)
        paid = 100.0 - WAGES.gold(self.sim, buyer)
        self.assertGreaterEqual(paid, 30 * C.FOOD_PRICE - 1e-9, "ค่าข้าวของตัวเองอย่างน้อย")
        self.assertAlmostEqual(WAGES.gold(self.sim, farmer), paid, places=6)
        self.assertEqual(buyer.hunger_days, 0.0)

    def _feed_one(self, person, granary):
        self.sim.granary[(0, self.a)] = granary
        before = money_everywhere(self.sim)
        gap = FOOD.total_held(self.sim) - FOOD.ledger_balance(self.sim.food_stats)   # ข้าวที่เทสต์ใส่เองไม่มีในบัญชี
        with switches(food=True), mock.patch.object(C, "FOOD_SPOIL_PER_YEAR", 0.0), \
                only(self.sim, person):
            FOOD.tick(self.sim, 30)
        self.assertAlmostEqual(money_everywhere(self.sim), before, places=6, msg="ทำงานแลกข้าวไม่เสกทอง")
        self.assertAlmostEqual(FOOD.total_held(self.sim) - FOOD.ledger_balance(self.sim.food_stats), gap,
                               places=6, msg="ข้าวแลกแรงงานนับเป็นข้าวที่กินตามปกติ บัญชีข้าวยังปิด")

    def test_an_adult_who_cannot_pay_works_for_the_food_and_no_gold_moves(self):
        pauper = setup_person(self.sim, self.people[0], self.a)
        self._feed_one(pauper, 100.0)
        self.assertEqual(pauper.hunger_days, 0.0)
        self.assertAlmostEqual(self.sim.food_stats["worked_for_food"], 30.0)
        self.assertAlmostEqual(self.sim.granary[(0, self.a)], 70.0)
        self.assertAlmostEqual(sum(self.sim.farm_till.values()), 0.0, msg="ไร่ไม่ได้เงินจากข้าวที่แลกด้วยแรงงาน")

    def test_he_pays_what_he_can_and_works_for_the_rest(self):
        worker = setup_person(self.sim, self.people[0], self.a)
        WAGES.move_gold(self.sim, worker, 10 * C.FOOD_PRICE)         # ซื้อได้สิบวัน
        self._feed_one(worker, 100.0)
        self.assertEqual(worker.hunger_days, 0.0)
        self.assertAlmostEqual(WAGES.gold(self.sim, worker), 0.0)
        self.assertAlmostEqual(self.sim.food_stats["worked_for_food"], 20.0)

    def test_a_prisoner_is_fed_by_the_jail(self):
        prisoner = setup_person(self.sim, self.people[0], self.a)
        prisoner.hidden, prisoner.jail_until = True, self.sim.day + 3 * 365
        self._feed_one(prisoner, 100.0)
        self.assertEqual(prisoner.hunger_days, 0.0)
        self.assertAlmostEqual(self.sim.food_stats["prison_rations"], 30.0)

    def test_someone_hidden_away_who_cannot_pay_goes_hungry_and_the_food_stays(self):
        hermit = setup_person(self.sim, self.people[0], self.a)
        hermit.hidden = True                                         # ในแดนลับ ไม่ได้ปิดด่าน ไม่ได้ติดคุก
        self._feed_one(hermit, 100.0)
        self.assertEqual(hermit.hunger_days, 30.0)
        self.assertAlmostEqual(self.sim.granary[(0, self.a)], 100.0)

    def test_work_for_food_never_hands_out_more_than_the_granary_has(self):
        pauper = setup_person(self.sim, self.people[0], self.a)
        self._feed_one(pauper, 12.0)
        self.assertAlmostEqual(self.sim.food_stats["worked_for_food"], 12.0)
        self.assertAlmostEqual(self.sim.granary.get((0, self.a), 0.0), 0.0)
        self.assertAlmostEqual(pauper.hunger_days, 18.0)

    def test_a_child_is_fed_by_a_parent_here_or_else_by_the_village(self):
        parent = setup_person(self.sim, self.people[0], self.a)
        child = setup_person(self.sim, self.people[1], self.a, age=6)
        child.parents = [parent.cid]
        orphan = setup_person(self.sim, self.people[2], self.a, age=6)
        orphan.parents = []
        WAGES.move_gold(self.sim, parent, 100.0)
        self.sim.granary[(0, self.a)] = 1000.0
        tier = self.sim.world(0).tier
        self.sim.settlement_treasury = {(0, self.a): {tier: 50.0}}       # คลังชุมชนจ่ายค่ามื้อของเด็กที่ไม่มีใครจ่าย (A5)
        till = sum(self.sim.farm_till.values())
        with switches(food=True), mock.patch.object(C, "FOOD_SPOIL_PER_YEAR", 0.0), \
                only(self.sim, parent, child, orphan):
            FOOD.tick(self.sim, 30)
        self.assertEqual(child.hunger_days, 0.0)
        self.assertEqual(orphan.hunger_days, 0.0)
        own = 30 * C.FOOD_RATION_ADULT * C.FOOD_PRICE
        kid = 30 * C.FOOD_RATION_CHILD * C.FOOD_PRICE
        self.assertGreaterEqual(100.0 - WAGES.gold(self.sim, parent), own + kid - 1e-9)
        self.assertGreaterEqual(self.sim.food_stats["charity"], 30 * C.FOOD_RATION_CHILD - 1e-9)
        self.assertAlmostEqual(50.0 - self.sim.settlement_treasury[(0, self.a)][tier], kid, msg="คลังชุมชนจ่ายค่ามื้อ")
        self.assertGreaterEqual(sum(self.sim.farm_till.values()) - till, own + 2 * kid - 1e-9, msg="ทองถึงไร่")

    def test_a_nearby_settlement_pays_when_the_local_one_is_empty_but_not_one_out_of_reach(self):
        from tiandao import travel as TR
        orphan = setup_person(self.sim, self.people[2], self.a, age=6)
        orphan.parents = []
        self.sim.granary[(0, self.a)] = 1000.0
        tier = self.sim.world(0).tier
        near = {p for p, _h in TR.places_within(self.sim, self.a, C.FOOD_REACH_HOPS)}
        close = min(near)
        far = next(p for p in PL.places_in(self.sim.worlds[0].place_key) if p != self.a and p not in near)
        self.sim.settlement_treasury = {(0, far): {tier: 50.0}}
        with switches(food=True), mock.patch.object(C, "FOOD_SPOIL_PER_YEAR", 0.0), only(self.sim, orphan):
            FOOD.tick(self.sim, 30)
        self.assertGreater(orphan.hunger_days, 0.0, "คลังนอกระยะส่งข้าวถึงไม่จ่าย")
        self.assertEqual(self.sim.settlement_treasury[(0, far)][tier], 50.0)
        self.sim.settlement_treasury[(0, close)] = {tier: 50.0}
        orphan.hunger_days = 0.0
        with switches(food=True), mock.patch.object(C, "FOOD_SPOIL_PER_YEAR", 0.0), only(self.sim, orphan):
            FOOD.tick(self.sim, 30)
        self.assertEqual(orphan.hunger_days, 0.0, "ชุมชนใกล้ ๆ จ่ายแทน")
        self.assertAlmostEqual(50.0 - self.sim.settlement_treasury[(0, close)][tier], 30 * C.FOOD_RATION_CHILD * C.FOOD_PRICE)

    def test_with_the_settlement_treasury_empty_an_orphan_misses_meals(self):
        orphan = setup_person(self.sim, self.people[2], self.a, age=6)
        orphan.parents = []
        self.sim.granary[(0, self.a)] = 1000.0
        self.sim.settlement_treasury = {}
        with switches(food=True), mock.patch.object(C, "FOOD_SPOIL_PER_YEAR", 0.0), only(self.sim, orphan):
            FOOD.tick(self.sim, 30)
        self.assertGreater(orphan.hunger_days, 0.0)
        self.assertAlmostEqual(self.sim.food_stats["charity_unfunded"], 30 * C.FOOD_RATION_CHILD)
        self.assertAlmostEqual(self.sim.granary[(0, self.a)], 1000.0, msg="ข้าวที่ไม่มีใครจ่ายยังอยู่ในยุ้งฉาง")


class WagesInTheRunningWorldTests(unittest.TestCase):
    def test_a_world_with_food_and_wages_keeps_both_ledgers(self):
        with switches(food=True):
            sim = quiet(S.Sim, seed=11)
            quiet(sim.run, 6000)
        self.assertGreater(sim.wage_stats["paid"], 0)
        self.assertGreater(sim.wage_stats["farm_paid"], 0)
        self.assertAlmostEqual(FOOD.total_held(sim), FOOD.ledger_balance(sim.food_stats),
                               delta=1e-6 * max(1.0, sim.food_stats["produced"]))

    def test_switched_off_the_world_never_touches_wages(self):
        with switches(food=False, wages=False):
            sim = quiet(S.Sim, seed=11)
            quiet(sim.run, 3000)
        self.assertEqual((sim.market_till, sim.farm_till), ({}, {}))
        self.assertTrue(all(v == 0 for v in sim.wage_stats.values()))
        self.assertFalse(any(ch.gold_endowed for ch in sim.cast))

    def test_save_and_load_with_food_and_wages_continues_like_one_run(self):
        with switches(food=True):
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
        self.assertEqual(split.wage_stats, straight.wage_stats)
        self.assertEqual([c.money for c in split.cast], [c.money for c in straight.cast])

    def test_a_version_3_save_gets_spot_granaries_and_empty_tills_without_moving_the_rng(self):
        sim = quiet(S.Sim, seed=5)
        quiet(sim.run, 200)
        place = PL.places_in(sim.worlds[0].place_key)[0]
        sim.granary = {place: 50.0}
        del sim.market_till, sim.farm_till, sim.wage_stats
        sim.households = {}                          # เซฟรุ่น 3 ยังไม่มีครัวเรือน (สร้างใหม่ตอนย้ายรุ่น 17)
        rng_state = sim.rng.getstate()
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "world.save")
            with open(path, "wb") as f:
                pickle.dump({"save_version": 3, "sim": sim}, f)
            loaded = PS.load_sim(path)
        self.assertEqual(loaded.granary, {(0, place): 50.0})
        self.assertEqual((loaded.market_till, loaded.farm_till), ({}, {}))
        self.assertEqual(loaded.wage_stats, WAGES.new_stats())
        self.assertEqual(loaded.rng.getstate(), rng_state)


if __name__ == "__main__":
    unittest.main()
