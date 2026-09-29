# -*- coding: utf-8 -*-
"""ทรัพยากรในแหล่ง (แบบ §6.2) — ระบบนิเวศของแต่ละแดนแยกกัน (R1)

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


class EcologyByRealmTests(unittest.TestCase):
    def setUp(self):
        self.sim = quiet(S.Sim, seed=5)
        # สองแดนที่ใช้ผังสถานที่ชุดเดียวกัน
        by_key = {}
        for w in self.sim.worlds:
            by_key.setdefault(w.place_key, []).append(w)
        self.a, self.b = next(ws for ws in by_key.values() if len(ws) >= 2)[:2]
        self.place = PL.places_in(self.a.place_key)[0]

    def test_harvesting_one_realm_leaves_the_same_place_in_a_sister_realm_untouched(self):
        self.sim.eco_harvest(self.a.wid, self.place, C.ECO_CAP * 0.9)
        self.assertAlmostEqual(self.sim.eco_ratio(self.a.wid, self.place), max(C.ECO_MIN_YIELD, 0.1))
        self.assertEqual(self.sim.eco_ratio(self.b.wid, self.place), 1.0, "แดนพี่น้องที่ใช้ผังเดียวกันไม่โทรมตาม")
        self.assertTrue(self.sim.eco_scarce[(self.a.wid, self.place)])
        self.assertNotIn((self.b.wid, self.place), self.sim.eco_scarce)

    def test_a_version_28_save_copies_each_places_stock_to_every_realm_with_that_place(self):
        self.sim.place_stock = {self.place: 5.0}
        self.sim.eco_scarce = {self.place: True}
        self.sim.eco_recovered = {self.place}
        state = self.sim.rng.getstate()
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "old.save")
            with open(path, "wb") as f:
                pickle.dump({"save_version": 28, "sim": self.sim}, f)
            back = PS.load_sim(path)
        realms = [w.wid for w in back.worlds if self.place in PL.places_in(w.place_key)]
        self.assertGreaterEqual(len(realms), 2)
        self.assertEqual(back.place_stock, {(wid, self.place): 5.0 for wid in realms})
        self.assertEqual(back.eco_scarce, {(wid, self.place): True for wid in realms})
        self.assertEqual(back.eco_recovered, {(wid, self.place) for wid in realms})
        self.assertEqual(back.rng.getstate(), state)

    def test_a_scarcity_rumour_still_points_at_a_place_number_the_mind_can_use(self):
        from tiandao import events as E, intent as IN
        self.sim.eco_harvest(self.a.wid, self.place, C.ECO_CAP)
        scarce = []
        for _ in range(400):                                      # ข่าวลือค้างได้ไม่กี่เรื่อง — เก็บทันทีที่เกิด
            quiet(self.sim.spawn_rumor, self.a, self.sim.rng)
            if self.sim.rumors and self.sim.rumors[-1]["kind"] == "ขาดแคลน":
                scarce.append(self.sim.rumors[-1])
        self.assertTrue(scarce, "มีข่าวลือเรื่องขาดแคลน")
        self.assertEqual({r["subject"] for r in scarce}, {self.place})
        ch = next(c for c in self.sim.living_in(self.a.wid) if c.sentient)
        ch.rumor_leads = [{"kind": "ขาดแคลน", "subject": scarce[0]["subject"], "true": True}]
        IN.weigh(ch, self.sim, E.EVENT_TABLE, False)             # เคยพังเมื่อหัวข้อเป็น (แดน, สถานที่)

    def test_a_running_world_keeps_every_stock_keyed_by_realm_and_place(self):
        quiet(self.sim.run, 3000)
        self.assertTrue(self.sim.place_stock)
        for wid, idx in self.sim.place_stock:
            self.assertIn(idx, PL.places_in(self.sim.world(wid).place_key), "สถานที่อยู่ในผังของแดนนั้นจริง")


if __name__ == "__main__":
    unittest.main()
