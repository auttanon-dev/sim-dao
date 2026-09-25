# -*- coding: utf-8 -*-
"""เหรียญทองต้องคีย์ตามชั้นของแดนเท่านั้น (models.Character.money: tier -> จำนวน)

    python -m unittest test_money_keys -v

บั๊กที่ล็อกไว้: หลายจุด (ลาดตระเวน ล้างแค้น จับกุม ปล้น ถ่ายทอดวิชา ประมูล ค่าครองชีพ ฯลฯ) เขียนเงินด้วย wid
ส่วนแห่งอื่นเขียนด้วยชั้น 49 จาก 52 แดนมี wid ไม่เท่ากับชั้น เงินของคนคนเดียวจึงแตกเป็นหลายกองที่มองไม่เห็นกัน
วัดที่ seed 11 หลังเดิน 20,000 ก้าว: คนมีชีวิต 89 คนถือเงินใต้คีย์ที่ไม่ใช่ชั้นของแดนตัวเอง ใช้คีย์ 3–40
ค่าครองชีพของปุถุชนนอกโลกมนุษย์อ่านเจอกระเป๋าว่างทุกครั้งแล้วรับความเสื่อมแทนการจ่าย
และส่วนแบ่งจากสำนักจ่ายเป็นเหรียญชั้น 0 เสมอไม่ว่าศิษย์อยู่แดนไหน
"""
import contextlib
import io
import os
import pickle
import re
import tempfile
import unittest
from unittest import mock

from tiandao import config as C
from tiandao import persist as PS
from tiandao import rules as R
from tiandao import sim as S
from tiandao import wages as WAGES


def quiet(fn, *a, **kw):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*a, **kw)


class MoneyKeyTests(unittest.TestCase):
    def test_a_running_world_only_ever_stores_gold_under_tiers(self):
        sim = quiet(S.Sim, seed=11)
        quiet(sim.run, 20000)
        tiers = {w.tier for w in sim.worlds}
        self.assertEqual({k for ch in sim.cast for k in ch.money} - tiers, set())

    def test_no_code_writes_gold_under_a_world_id(self):
        root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tiandao")
        pattern = re.compile(r"money(\.get)?[\[(](w\.wid|wid|world\.wid|a\.world_id|ch\.world_id)[\],]")
        hits = []
        for folder, _dirs, files in os.walk(root):
            for name in files:
                if name.endswith(".py"):
                    path = os.path.join(folder, name)
                    for no, line in enumerate(open(path, encoding="utf-8"), 1):
                        if pattern.search(line):
                            hits.append(f"{os.path.relpath(path, root)}:{no}")
        self.assertEqual(hits, [])

    def test_a_mortal_outside_the_human_world_pays_the_cost_of_living(self):
        sim = quiet(S.Sim, seed=5)
        world = next(w for w in sim.worlds if w.wid != w.tier)
        ch = sim.cast[0]
        ch.world_id, ch.realm, ch.money, ch.decay = world.wid, 0, {world.tier: 100.0}, 0.0
        paid = R.upkeep(ch, world, 1.0)
        self.assertGreater(paid, 0)
        self.assertAlmostEqual(ch.money[world.tier], 100.0 - paid)
        self.assertEqual(ch.decay, 0.0, "จ่ายไหวต้องไม่กร่อนตัวเอง")

    def test_with_wages_on_living_costs_are_the_real_purchases_not_a_second_charge(self):
        sim = quiet(S.Sim, seed=5)
        ch = sim.cast[0]
        ch.world_id, ch.realm, ch.money = 0, 0, {0: 100.0}
        with mock.patch.object(C, "WAGES_ENABLED", True):
            self.assertEqual(R.upkeep(ch, sim.worlds[0], 1.0), 0.0)
        self.assertEqual(ch.money[0], 100.0)

    def test_an_older_save_moves_world_id_gold_to_its_tier_without_losing_a_coin(self):
        sim = quiet(S.Sim, seed=5)
        quiet(sim.run, 200)
        world = next(w for w in sim.worlds if w.wid > max(x.tier for x in sim.worlds))
        ch = sim.cast[0]
        ch.money = {0: 5.0, world.wid: 7.0}
        total = sum(sum(c.money.values()) for c in sim.cast)
        rng_state = sim.rng.getstate()
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "world.save")
            with open(path, "wb") as f:
                pickle.dump({"save_version": 4, "sim": sim}, f)
            loaded = PS.load_sim(path)
        moved = loaded.cast[0].money
        self.assertNotIn(world.wid, moved)
        self.assertAlmostEqual(moved.get(world.tier, 0.0), 7.0 + (5.0 if world.tier == 0 else 0.0))
        self.assertAlmostEqual(sum(sum(c.money.values()) for c in loaded.cast), total)
        self.assertEqual(loaded.rng.getstate(), rng_state)

    def test_sect_payouts_are_paid_in_the_members_own_tier(self):
        sim = quiet(S.Sim, seed=5)
        member = sim.cast[0]
        world = next(w for w in sim.worlds if w.tier != 0)
        member.world_id, member.money = world.wid, {}
        WAGES.move_gold(sim, member, 12.0)
        self.assertEqual(member.money, {world.tier: 12.0})



class CombatInsightTests(unittest.TestCase):
    """ความเข้าใจที่เกินขั้นรับไหวต้องไม่กลายเป็นพลังรบเต็มจำนวน — ปัญหาที่การแก้เงินคีย์ผิดชั้นทำให้เห็น"""

    def test_insight_up_to_the_breakthrough_need_counts_in_full(self):
        sim = quiet(S.Sim, seed=5)
        ch, world = sim.cast[0], sim.worlds[0]
        ch.insight = R.need(ch, world)
        self.assertAlmostEqual(R.combat_insight(ch, world), ch.insight)
        ch.insight = 0.5 * R.need(ch, world)
        self.assertAlmostEqual(R.combat_insight(ch, world), ch.insight)

    def test_a_hoard_far_beyond_the_realm_has_diminishing_returns(self):
        sim = quiet(S.Sim, seed=5)
        ch, world = sim.cast[0], sim.worlds[2]
        req = R.need(ch, world)
        ch.insight = 3.1 * req
        got = R.combat_insight(ch, world)
        self.assertLess(got, 0.7 * ch.insight)
        self.assertGreater(got, req, "ยังได้ประโยชน์จากความเข้าใจที่มากขึ้น แค่ลดทอน")
        ch.insight = 4.0 * req
        self.assertGreater(R.combat_insight(ch, world), got, "มากขึ้นยังได้มากขึ้นเสมอ")


if __name__ == "__main__":
    unittest.main()
