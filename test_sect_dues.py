# -*- coding: utf-8 -*-
"""ค่าบำรุงสำนักอยู่ในบัญชีทอง (Sim.sect_dues) — ทองไม่หายระหว่างเก็บค่าบำรุงและแจกศิษย์

    python -m unittest test_sect_dues -v
"""
import contextlib
import io
import unittest

from tiandao import config as C
from tiandao import sim as S
from tiandao import wages as WAGES
from tiandao.models import Org


def quiet(fn, *a, **kw):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*a, **kw)


def declared(sim):
    return sum(sum(v.values()) for v in sim.gold_flows.values())


def ledger(sim):
    return {t: WAGES.total_gold(sim, t) for t in range(3)}


class SectDuesTests(unittest.TestCase):
    def setUp(self):
        self.sim = quiet(S.Sim, seed=5)
        people = [c for c in self.sim.living() if c.sentient][:6]
        self.org = Org(len(self.sim.orgs), "สำนัก", "สำนักทดสอบ", people[0].world_id, people[0].cid, 0)
        self.sim.orgs.append(self.org)
        self.core, self.inner, self.visitor = people[0], people[1], people[2]
        self.org.members = [c.cid for c in people[:3]]
        self.org.core_disciples, self.org.inner_disciples, self.org.outer_disciples = [self.core.cid], [self.inner.cid], []
        self.low = self.sim.world(self.core.world_id).tier
        self.high = next(w for w in self.sim.worlds if w.tier != self.low)
        self.visitor.world_id = self.high.wid
        self.org.core_disciples.append(self.visitor.cid)
        for c in (self.core, self.inner):
            c.money = {self.low: 100.0}
        self.visitor.money = {self.high.tier: 50.0}
        self.org.treasury_gold = {}

    def test_dues_and_payouts_keep_every_tier_of_the_ledger(self):
        before = ledger(self.sim)
        self.sim.sect_dues(self.org)
        after = ledger(self.sim)
        for t in before:
            self.assertAlmostEqual(after[t], before[t], places=9)
        self.assertGreater(self.org.treasury_gold[self.low], 0.0)

    def test_payouts_are_exact_and_only_in_the_tier_the_disciple_lives_in(self):
        self.sim.sect_dues(self.org)
        dues = 200.0 * C.SECT_DUES_RATE
        payout = dues * C.SECT_PAYOUT_RATE
        core_gets = payout * 0.4 / 1                            # ศิษย์สายแกนชั้นนี้มีคนเดียว (อีกคนอยู่แดนชั้นอื่น)
        inner_gets = payout * 0.4
        self.assertAlmostEqual(self.core.money[self.low], 100.0 * (1 - C.SECT_DUES_RATE) + core_gets)
        self.assertAlmostEqual(self.inner.money[self.low], 100.0 * (1 - C.SECT_DUES_RATE) + inner_gets)
        self.assertNotIn(self.low, self.visitor.money, "ไม่ได้ทองชั้นที่ตัวเองไม่ได้อยู่")
        self.assertAlmostEqual(self.org.treasury_gold[self.low], dues - core_gets - inner_gets,
                               msg="ส่วนของสายนอกที่ไม่มีคนรับค้างอยู่ในคลัง ไม่หายไป")

    def test_a_running_world_tick_keeps_the_gold_ledger(self):
        sim = quiet(S.Sim, seed=11)
        quiet(sim.run, 12000)
        for _ in range(3):
            before, flows = sum(ledger(sim).values()), declared(sim)
            quiet(sim._world_tick, sim.rng)
            # ทองเปลี่ยนได้เฉพาะทางที่ประกาศในบัญชีสาเหตุ (ทุนตั้งต้น ทองจากเหมือง ฯลฯ — B1)
            self.assertAlmostEqual(sum(ledger(sim).values()) - before, declared(sim) - flows, places=6)


if __name__ == "__main__":
    unittest.main()
