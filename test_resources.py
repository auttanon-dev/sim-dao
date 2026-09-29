# -*- coding: utf-8 -*-
"""ทรัพยากรในแหล่ง (แบบ §6.2) — ระบบนิเวศแยกตามแดน (R1) แยกชนิดและเก็บได้เท่าที่มีจริง (R2) แร่ฟื้นช้า (R3)

บัญชีคลังทรัพยากร: คลังรวม = genesis + regrown + seeded − harvested − disaster

    python -m unittest test_resources -v
"""
import contextlib
import io
import os
import pickle
import tempfile
import unittest

from tiandao import config as C
from tiandao import persist as PS
from tiandao import places as PL
from tiandao import sim as S


def quiet(fn, *a, **kw):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*a, **kw)


def ledger_gap(sim):
    m = getattr(sim, "material_stats", {})
    held = sum(sim.place_stock.values())
    return held - (m.get("genesis", 0) + m.get("regrown", 0) + m.get("seeded", 0)
                   - m.get("harvested", 0) - m.get("disaster", 0))


class EcologyTests(unittest.TestCase):
    def setUp(self):
        self.sim = quiet(S.Sim, seed=5)
        by_key = {}
        for w in self.sim.worlds:
            by_key.setdefault(w.place_key, []).append(w)
        self.a, self.b = next(ws for ws in by_key.values() if len(ws) >= 2)[:2]
        self.herb = next(i for i in PL.places_in(self.a.place_key) if self.sim.eco_kind(i) == "herb")
        self.ore = next((i for i in PL.places_in(self.a.place_key) if self.sim.eco_kind(i) == "ore"), None)

    def cap(self, kind):
        return C.ECO_KINDS[kind][0]

    def test_harvesting_one_realm_leaves_the_same_place_in_a_sister_realm_untouched(self):
        self.sim.eco_harvest(self.a.wid, self.herb, self.cap("herb") * 0.9)
        self.assertAlmostEqual(self.sim.eco_ratio(self.a.wid, self.herb), 0.1)
        self.assertEqual(self.sim.eco_ratio(self.b.wid, self.herb), 1.0, "แดนพี่น้องที่ใช้ผังเดียวกันไม่โทรมตาม")
        self.assertTrue(self.sim.eco_scarce[(self.a.wid, self.herb)])
        self.assertNotIn((self.b.wid, self.herb), self.sim.eco_scarce)

    def test_a_harvest_never_takes_more_than_is_there_and_an_empty_stock_gives_nothing(self):
        cap = self.cap("herb")
        self.assertEqual(self.sim.eco_harvest(self.a.wid, self.herb, cap + 10), cap, "ได้เท่าที่มี")
        self.assertEqual(self.sim.eco_ratio(self.a.wid, self.herb), 0.0, "ไม่มีพื้นผลผลิตขั้นต่ำ")
        self.assertEqual(self.sim.eco_take_units(self.a.wid, self.herb, 5), 0)
        self.assertAlmostEqual(ledger_gap(self.sim), 0.0, places=9)

    def test_hunting_draws_on_the_beasts_not_the_ore_of_a_mine(self):
        if self.ore is None:
            self.skipTest("แดนนี้ไม่มีแหล่งแร่")
        self.sim.eco_take_units(self.a.wid, self.ore, 3, "beast")
        self.assertEqual(self.sim.eco_ratio(self.a.wid, self.ore), 1.0, "แร่ไม่ลด")
        self.assertLess(self.sim.eco_ratio(self.a.wid, self.ore, "beast"), 1.0)

    def test_ore_regrows_far_slower_than_herbs(self):
        if self.ore is None:
            self.skipTest("แดนนี้ไม่มีแหล่งแร่")
        for idx in (self.herb, self.ore):
            self.sim.eco_harvest(self.a.wid, idx, self.cap(self.sim.eco_kind(idx)) - 2.0)
        self.sim.eco_regen(365)
        herb = self.sim.eco_ratio(self.a.wid, self.herb) * self.cap("herb")
        ore = self.sim.eco_ratio(self.a.wid, self.ore) * self.cap("ore")
        self.assertGreater(herb - 2.0, 3 * (ore - 2.0), "สมุนไพรฟื้นในราวปี สายแร่ฟื้นช้า")
        self.assertGreater(ore, 2.0, "แต่แร่ก็ฟื้น (ช้า) ไม่ตายถาวร")
        self.assertAlmostEqual(ledger_gap(self.sim), 0.0, places=9)

    def test_a_running_world_keeps_the_material_ledger_and_every_key_in_its_realm(self):
        quiet(self.sim.run, 4000)
        self.assertGreater(self.sim.material_stats.get("harvested", 0), 0)
        self.assertAlmostEqual(ledger_gap(self.sim), 0.0, places=6)
        for wid, idx, kind in self.sim.place_stock:
            self.assertIn(idx, PL.places_in(self.sim.world(wid).place_key), "สถานที่อยู่ในผังของแดนนั้นจริง")
            self.assertIn(kind, C.ECO_KINDS)
            self.assertGreaterEqual(self.sim.place_stock[(wid, idx, kind)], 0.0)

    def test_a_scarcity_rumour_still_points_at_a_place_number_the_mind_can_use(self):
        from tiandao import events as E, intent as IN
        self.sim.eco_harvest(self.a.wid, self.herb, self.cap("herb"))
        scarce = []
        for _ in range(400):                                      # ข่าวลือค้างได้ไม่กี่เรื่อง — เก็บทันทีที่เกิด
            quiet(self.sim.spawn_rumor, self.a, self.sim.rng)
            if self.sim.rumors and self.sim.rumors[-1]["kind"] == "ขาดแคลน":
                scarce.append(self.sim.rumors[-1])
        self.assertTrue(scarce, "มีข่าวลือเรื่องขาดแคลน")
        self.assertEqual({r["subject"] for r in scarce}, {self.herb})
        ch = next(c for c in self.sim.living_in(self.a.wid) if c.sentient)
        ch.rumor_leads = [{"kind": "ขาดแคลน", "subject": scarce[0]["subject"], "true": True}]
        IN.weigh(ch, self.sim, E.EVENT_TABLE, False)             # เคยพังเมื่อหัวข้อเป็น (แดน, สถานที่)

    def save_as(self, version):
        state = self.sim.rng.getstate()
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "old.save")
            with open(path, "wb") as f:
                pickle.dump({"save_version": version, "sim": self.sim}, f)
            back = PS.load_sim(path)
        self.assertEqual(back.rng.getstate(), state)
        return back

    def test_a_version_28_save_copies_each_places_stock_to_every_realm_as_its_main_kind(self):
        self.sim.place_stock = {self.herb: 9.0}                   # ก่อนรุ่น 29: คีย์สถานที่ เพดานเดิม 18
        self.sim.eco_scarce = {self.herb: True}
        self.sim.eco_recovered = {self.herb}
        back = self.save_as(28)
        realms = [w.wid for w in back.worlds if self.herb in PL.places_in(w.place_key)]
        self.assertGreaterEqual(len(realms), 2)
        self.assertEqual(back.place_stock, {(wid, self.herb, "herb"): 0.5 * self.cap("herb") for wid in realms})
        self.assertEqual(back.eco_scarce, {(wid, self.herb): True for wid in realms})
        self.assertEqual(back.eco_recovered, {(wid, self.herb) for wid in realms})
        self.assertAlmostEqual(ledger_gap(back), 0.0, places=9)

    def test_a_version_29_save_turns_each_stock_into_its_main_kind(self):
        self.sim.place_stock = {(self.a.wid, self.herb): 18.0, (self.a.wid, 0): 4.5}
        self.sim.__dict__.pop("material_stats", None)
        back = self.save_as(29)
        self.assertEqual(back.place_stock[(self.a.wid, self.herb, "herb")], self.cap("herb"))
        kind0 = back.eco_kind(0)
        self.assertEqual(back.place_stock[(self.a.wid, 0, kind0)], 0.25 * self.cap(kind0))
        self.assertAlmostEqual(ledger_gap(back), 0.0, places=9)


if __name__ == "__main__":
    unittest.main()
