# -*- coding: utf-8 -*-
"""ความตายเป็นธุรกรรมเดียว (แบบ §7.4) — tiandao/death.py

ทุกความตายในโลกที่เดิน 30 ปีผ่านการตรวจ death.check: ไม่มีใครชี้ถึงผู้ตาย (คู่ครอง ผู้ปกครอง ครัวเรือน ผู้นำสำนัก เจ้าเมือง)
และทองรวมเปลี่ยนเฉพาะทางที่บันทึก

    python -m unittest test_death -v
"""
import contextlib
import io
import os
import pickle
import tempfile
import unittest
from unittest import mock

from tiandao import config as C
from tiandao import persist as PS
from tiandao import sim as S

SEEDS = (11, 12, 13)
YEARS = 30


def quiet(fn, *a, **kw):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*a, **kw)


def _walk(seed):
    """เดินโลก YEARS ปีโดยตรวจทุกความตาย — คืน (ข้อผิดพลาด, จำนวนผู้ตายที่ไม่ใช่เจ้าโกลาหล, จำนวนบันทึกความตาย)"""
    C.DEATH_CHECK = True
    try:
        sim = quiet(S.Sim, seed=seed)
        while sim.day < YEARS * 365:
            quiet(sim.step)
    except RuntimeError as err:
        return str(err), 0, 0
    dead = sum(1 for c in sim.cast if not c.alive)
    return None, dead, len(sim.deaths) + sim.__dict__.get("pruned_total", 0)


class DeathTransactionTests(unittest.TestCase):
    def test_every_death_in_a_running_world_leaves_no_dangling_reference_and_keeps_the_ledger(self):
        import multiprocessing
        with multiprocessing.Pool(len(SEEDS)) as pool:
            results = pool.map(_walk, SEEDS)
        for seed, (err, dead, recorded) in zip(SEEDS, results):
            self.assertIsNone(err, f"seed {seed}")
            self.assertGreater(dead, 100, f"seed {seed}")
            self.assertGreaterEqual(recorded, dead, f"seed {seed}: ทุกความตายมีบันทึก (ที่ย่อไปแล้วนับด้วย)")

    def setUp(self):
        self.sim = quiet(S.Sim, seed=5)

    def victim(self):
        return next(c for c in self.sim.living() if c.sentient and not c.is_lord and c.realm < C.CACHE_MIN_REALM)

    def test_a_death_is_recorded_once_and_a_second_kill_does_nothing(self):
        ch = self.victim()
        with mock.patch.object(C, "DEATH_CHECK", True):
            quiet(self.sim.kill, ch, "ทดสอบ")
            n = len(self.sim.deaths)
            day = ch.death_day
            quiet(self.sim.kill, ch, "ซ้ำ")
        self.assertEqual(len(self.sim.deaths), n)
        rec = self.sim.deaths[-1]
        self.assertEqual((rec.cid, rec.cause, rec.day, rec.killer), (ch.cid, "ทดสอบ", day, -1))
        self.assertEqual(ch.death_cause, "ทดสอบ")

    def test_dying_mid_seclusion_still_counts_the_days_actually_spent(self):
        ch = self.victim()
        quiet(self.sim.start_process, ch, "seclusion", 365, {}, 1.0)
        self.sim.day += 100
        insight = ch.insight
        quiet(self.sim.kill, ch, "ทดสอบ")
        self.assertIsNone(ch.process)
        self.assertAlmostEqual(ch.insight - insight, C.SECLUDE_INSIGHT_PER_YEAR * 100 / 365.0,
                               msg="ได้ผล 100 วันที่ปิดด่านไปจริง ไม่ถูกล้างทิ้ง")

    def test_the_chaos_lord_dissolves_instead_of_dying_and_leaves_no_record(self):
        lord = self.sim.cast[self.sim.lord_cid]
        n = len(getattr(self.sim, "deaths", []))
        quiet(self.sim.kill, lord, "ทดสอบ")
        self.assertTrue(lord.alive)
        self.assertTrue(lord.hidden)
        self.assertEqual(len(getattr(self.sim, "deaths", [])), n)

    def test_the_check_catches_a_dangling_spouse(self):
        from tiandao import death as DEATH
        ch = self.victim()
        mate = next(c for c in self.sim.living() if c is not ch and c.sentient and c.spouse is None and ch.spouse is None)
        before = DEATH._gold(self.sim)
        mate.spouse = ch.cid                                  # ชี้ถึงผู้ตายโดยไม่ผ่านการแต่งงาน — การตายจะไม่รู้จักเขา
        ch.alive = False
        self.assertTrue(any("คู่ครอง" in p for p in DEATH.check(self.sim, ch, before)))

    def test_records_are_pruned_with_the_departed(self):
        ch = self.victim()
        quiet(self.sim.kill, ch, "ทดสอบ")
        ch.children, ch.wards = [], []
        self.sim.day += (C.PRUNE_DEAD_YEARS + 1) * 365
        self.sim.prune_departed()
        self.assertNotIn(ch.cid, {d.cid for d in self.sim.deaths})

    def test_a_version_27_save_gets_an_empty_death_record(self):
        for key in ("deaths", "death_seq"):
            self.sim.__dict__.pop(key, None)
        state = self.sim.rng.getstate()
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "old.save")
            with open(path, "wb") as f:
                pickle.dump({"save_version": 27, "sim": self.sim}, f)
            back = PS.load_sim(path)
        self.assertEqual((back.deaths, back.death_seq), ([], 0))
        self.assertEqual(back.rng.getstate(), state)


if __name__ == "__main__":
    unittest.main()
