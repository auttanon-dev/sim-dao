# -*- coding: utf-8 -*-
"""บัญชีทองและข้าวปิดทุกก้าว (แบบ §6.1) — ทองหรือข้าวเกิดหรือหายได้เฉพาะทางที่มีสาเหตุในบัญชี

ทอง: wages.total_gold == ผลรวมของ Sim.gold_flows ทุกสาเหตุ (wages.gold_gap == 0) ทุกชั้น
ข้าว: food.total_held == food.ledger_balance(food_stats)

    python -m unittest test_ledger -v
"""
import contextlib
import io
import os
import pickle
import tempfile
import unittest

from tiandao import config as C
from tiandao import food as FOOD
from tiandao import persist as PS
from tiandao import sim as S
from tiandao import wages as WAGES


def quiet(fn, *a, **kw):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*a, **kw)


def tiers(sim):
    return sorted({w.tier for w in sim.worlds})


SEEDS = (11, 12, 13)
YEARS = 30


def _gaps(sim):
    """ช่องว่างของบัญชีที่เกินทศนิยม — ว่าง = ปิดทั้งสองบัญชี"""
    out = [f"ทองชั้น {t} {WAGES.gold_gap(sim, t):+.6f}" for t in tiers(sim) if abs(WAGES.gold_gap(sim, t)) > 1e-6]
    food = FOOD.total_held(sim) - FOOD.ledger_balance(sim.food_stats)
    return out + ([f"ข้าว {food:+.6f}"] if abs(food) > 1e-4 else [])


def _walk(seed):
    """เดินโลก YEARS ปีจากเริ่ม ตรวจทั้งสองบัญชีทุก 25 ก้าว — คืน (ช่องว่างที่พบครั้งแรก, gold_flows)"""
    sim = quiet(S.Sim, seed=seed)
    n = 0
    while sim.day < YEARS * 365:
        quiet(sim.step)
        n += 1
        if n % 25 == 0 and _gaps(sim):
            return [f"ก้าวที่ {n} วันที่ {sim.day}: {_gaps(sim)}"], sim.gold_flows, sim.wage_stats
    return _gaps(sim), sim.gold_flows, sim.wage_stats


class LedgerTests(unittest.TestCase):
    def assertClosed(self, sim, where):
        for t in tiers(sim):
            self.assertAlmostEqual(WAGES.gold_gap(sim, t), 0.0, places=6, msg=f"ทองชั้น {t} {where}")
        self.assertAlmostEqual(FOOD.total_held(sim), FOOD.ledger_balance(sim.food_stats), places=4, msg=f"ข้าว {where}")

    def test_every_step_of_a_running_world_keeps_both_ledgers(self):
        import multiprocessing
        with multiprocessing.Pool(len(SEEDS)) as pool:
            results = pool.map(_walk, SEEDS)
        for seed, (problems, flows, wages) in zip(SEEDS, results):
            self.assertEqual(problems, [], f"seed {seed}")
            self.assertGreater(flows["start_gold"][0], 0.0)
            self.assertNotIn("market_sale", flows, "ตลาดจ่ายจากทุนสำรอง ไม่เสกทอง (B3b)")
            self.assertGreater(wages.get("market_paid", 0.0), 0.0)

    def test_a_raw_write_outside_the_ledger_is_caught(self):
        sim = quiet(S.Sim, seed=11)
        quiet(sim.run, 1500)
        ch = next(c for c in sim.living() if c.money)
        tier = next(iter(ch.money))
        ch.money[tier] += 7.0
        self.assertAlmostEqual(WAGES.gold_gap(sim, tier), 7.0)
        WAGES.set_gold(sim, ch, tier, ch.money[tier] - 7.0, "test")
        self.assertAlmostEqual(WAGES.gold_gap(sim, tier), 7.0, msg="set_gold บันทึกส่วนต่าง ช่องว่างเดิมยังอยู่")

    def test_a_realm_changing_tier_with_gold_in_its_tills_keeps_every_tier_closed(self):
        sim = quiet(S.Sim, seed=11)
        quiet(sim.run, 1500)
        world = next(w for w in sim.worlds if w.tier > 0)
        old = world.tier
        WAGES.record(sim, "test", old, 25.0)                # ทองในลิ้นชักของแดนนี้ที่มีบัญชีรองรับ
        sim.farm_till[(world.wid, 0)] = sim.farm_till.get((world.wid, 0), 0.0) + 25.0
        self.assertClosed(sim, "ก่อนเปลี่ยนชั้น")
        world.tier = old - 1
        WAGES.retier(sim, world, old)
        self.assertClosed(sim, "หลังเสื่อมลงชั้น")
        world.tier = old
        WAGES.retier(sim, world, old - 1)
        self.assertClosed(sim, "หลังฟื้นขึ้นชั้น")

    def test_a_demoted_realm_turns_its_residents_treasuries_and_purses_into_the_new_tier(self):
        from tiandao import household as HH
        sim = quiet(S.Sim, seed=11)
        quiet(sim.run, 1500)
        world = next(w for w in sim.worlds if w.tier > 0 and sim.living_in(w.wid))
        old = world.tier
        resident = sim.living_in(world.wid)[0]
        outsider = next(c for c in sim.living() if c.world_id != world.wid)
        hh = HH.of(sim, resident)
        hh.home = (world.wid, resident.place)
        for purse in (resident.money, WAGES.settlement_purse(sim, (world.wid, 0)), hh.purse, outsider.money):
            WAGES.record(sim, "test", old, 10.0)
            purse[old] = purse.get(old, 0.0) + 10.0
        before = {k: resident.money.get(k, 0.0) for k in (old, old - 1)}
        outsider_old = outsider.money[old]
        world.tier = old - 1
        WAGES.retier(sim, world, old)
        self.assertNotIn(old, resident.money)
        self.assertAlmostEqual(resident.money[old - 1], before[old] + before[old - 1])
        self.assertNotIn(old, sim.settlement_treasury[(world.wid, 0)])
        self.assertNotIn(old, hh.purse)
        self.assertEqual(outsider.money[old], outsider_old, "คนแดนอื่นไม่เปลี่ยน")
        self.assertClosed(sim, "หลังเสื่อมลงชั้น")

    def test_gold_sealed_in_a_secret_realm_reaches_the_opener_per_tier_less_its_decay(self):
        sim = quiet(S.Sim, seed=11)
        quiet(sim.run, 1500)
        owner, opener = [c for c in sim.living() if c.sentient][:2]
        WAGES.clear_gold(sim, opener, "test")
        WAGES.clear_gold(sim, owner, "test")
        WAGES.set_gold(sim, owner, 0, 40.0, "test")
        WAGES.set_gold(sim, owner, 1, 10.0, "test")
        k = quiet(sim.make_cache, owner, False)
        self.assertEqual((k.gold, owner.money), ({0: 40.0, 1: 10.0}, {}))
        self.assertClosed(sim, "หลังผนึก")
        k.trap = False
        k.sealed_day = sim.day - 10 ** 6                  # ผนึกเสื่อมหมดแล้ว — ทองเสื่อมตาม CACHE_ROT เต็มที่
        rot = 1.0 - C.CACHE_ROT
        deposit = sim.ruin_deposit(sim.world(k.world_id))
        d = quiet(sim.open_cache, opener, k, sim.rng)
        self.assertAlmostEqual(opener.money[0], 40.0 * rot)
        self.assertAlmostEqual(opener.money[1], 10.0 * rot, msg="ทองชั้น 1 ไม่ถูกรวมเข้าชั้นของแดน")
        self.assertEqual(k.gold, {})
        self.assertIn("ทองในแดนลับ", d)
        here = sim.world(k.world_id)
        local = {0: 40.0, 1: 10.0}[here.tier]
        self.assertAlmostEqual(-sum(sim.gold_flows.get("cache_rot", {}).values()), (50.0 - local) * (1 - rot),
                               msg="ทองต่างชั้นที่เสื่อมหายไปกับผนึก")
        self.assertAlmostEqual(sim.ruin_gold[here.wid] - deposit, local * (1 - rot),
                               msg="ทองชั้นของแดนที่เสื่อมตกค้างเป็นเหรียญในซาก (B3c)")
        self.assertClosed(sim, "หลังเปิด")

    def test_a_version_23_save_turns_cache_currency_into_gold_of_its_realms_tier(self):
        sim = quiet(S.Sim, seed=11)
        quiet(sim.run, 1500)
        k = next(c for c in sim.caches if not c.opened)
        for c in sim.caches:
            c.__dict__.pop("gold", None)
            c.currency = 0.0
        k.currency = 33.0
        state = sim.rng.getstate()
        for version in (23, 20):                  # 20: ผ่านขั้นเปิดบัญชี (รุ่น 21) ก่อนแดนลับมี gold — เคยพังใน world.save จริง
            with tempfile.TemporaryDirectory() as folder:
                path = os.path.join(folder, "old.save")
                with open(path, "wb") as f:
                    pickle.dump({"save_version": version, "sim": sim}, f)
                back = PS.load_sim(path)
            tier = back.world(k.world_id).tier
            kb = next(c for c in back.caches if c.kid == k.kid)
            self.assertEqual(kb.gold, {tier: 33.0})
            self.assertFalse(hasattr(kb, "currency"))
            self.assertEqual(back.rng.getstate(), state)
        self.assertClosed(back, "เซฟรุ่น 20 หลังย้ายทองแดนลับ")

    def test_ruin_coins_come_from_a_finite_deposit_that_runs_dry(self):
        sim = quiet(S.Sim, seed=11)
        quiet(sim.run, 1500)
        ch = next(c for c in sim.living() if c.sentient)
        w = sim.world(ch.world_id)
        sim.ruin_deposit(w)
        WAGES.record(sim, "test", w.tier, 5.0 - sim.ruin_gold[w.wid])
        sim.ruin_gold[w.wid] = 5.0
        before = ch.money.get(w.tier, 0.0)
        for _ in range(20):
            quiet(sim.ruined_cache_find, ch, sim.rng, {})
        self.assertAlmostEqual(ch.money.get(w.tier, 0.0) - before, 5.0, msg="ได้ไม่เกินที่เหลือในซาก")
        self.assertEqual(sim.ruin_gold[w.wid], 0.0)
        self.assertClosed(sim, "หลังซากหมด")

    def test_only_those_made_with_the_world_get_starting_gold(self):
        sim = quiet(S.Sim, seed=11)
        quiet(sim.run, 1500)
        late = quiet(sim.spawn, sim.worlds[0], age_years=30)
        self.assertGreaterEqual(late.cid, sim.genesis_cast)
        self.assertFalse(late.gold_endowed)
        issued = sum(sim.gold_flows["start_gold"].values())
        quiet(WAGES.tick, sim, 30)
        self.assertTrue(late.gold_endowed)
        self.assertEqual(sum(sim.gold_flows["start_gold"].values()), issued, "คนที่มาทีหลังมาตัวเปล่า (ค่าแรงรอบนี้ไม่นับ)")
        self.assertClosed(sim, "หลังรอบค่าแรง")

    def test_save_and_load_keep_the_ledger_closed(self):
        sim = quiet(S.Sim, seed=11)
        quiet(sim.run, 2000)
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "w.save")
            PS.save_sim(sim, path)
            back = PS.load_sim(path)
        self.assertEqual(back.gold_flows, sim.gold_flows)
        quiet(back.run, 1000)
        self.assertClosed(back, "หลังโหลดแล้วเดินต่อ")

    def test_a_version_20_save_opens_the_ledger_at_its_current_gold_without_moving_the_rng(self):
        sim = quiet(S.Sim, seed=11)
        quiet(sim.run, 2000)
        held = {t: WAGES.total_gold(sim, t) for t in tiers(sim)}
        del sim.gold_flows
        state = sim.rng.getstate()
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "old.save")
            with open(path, "wb") as f:
                pickle.dump({"save_version": 20, "sim": sim}, f)
            back = PS.load_sim(path)
        self.assertEqual({t: v for t, v in back.gold_flows["opening"].items()}, {t: v for t, v in held.items() if v})
        self.assertEqual(back.rng.getstate(), state)
        quiet(back.run, 1000)
        self.assertClosed(back, "เซฟเก่าเดินต่อ")


if __name__ == "__main__":
    unittest.main()
