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
            return [f"ก้าวที่ {n} วันที่ {sim.day}: {_gaps(sim)}"], sim.gold_flows
    return _gaps(sim), sim.gold_flows


class LedgerTests(unittest.TestCase):
    def assertClosed(self, sim, where):
        for t in tiers(sim):
            self.assertAlmostEqual(WAGES.gold_gap(sim, t), 0.0, places=6, msg=f"ทองชั้น {t} {where}")
        self.assertAlmostEqual(FOOD.total_held(sim), FOOD.ledger_balance(sim.food_stats), places=4, msg=f"ข้าว {where}")

    def test_every_step_of_a_running_world_keeps_both_ledgers(self):
        import multiprocessing
        with multiprocessing.Pool(len(SEEDS)) as pool:
            results = pool.map(_walk, SEEDS)
        for seed, (problems, flows) in zip(SEEDS, results):
            self.assertEqual(problems, [], f"seed {seed}")
            self.assertGreater(flows["start_gold"][0], 0.0)
            self.assertGreater(sum(flows.get("market_sale", {}).values()), 0.0)

    def test_a_raw_write_outside_the_ledger_is_caught(self):
        sim = quiet(S.Sim, seed=11)
        quiet(sim.run, 1500)
        ch = next(c for c in sim.living() if c.money)
        tier = next(iter(ch.money))
        ch.money[tier] += 7.0
        self.assertAlmostEqual(WAGES.gold_gap(sim, tier), 7.0)
        WAGES.set_gold(sim, ch, tier, ch.money[tier] - 7.0, "test")
        self.assertAlmostEqual(WAGES.gold_gap(sim, tier), 7.0, msg="set_gold บันทึกส่วนต่าง ช่องว่างเดิมยังอยู่")

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
