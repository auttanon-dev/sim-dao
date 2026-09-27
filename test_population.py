# -*- coding: utf-8 -*-
"""เพดานประชากรและการย่อคนตายนานแล้ว (ระยะ 1 ขั้น 3)

    python -m unittest test_population -v

สิ่งที่ล็อกไว้
  · โอกาสตั้งครรภ์เต็มที่จนถึงขนาดที่แดนเติมคนถึง แล้วลดเป็นเส้นตรงจนเป็นศูนย์ที่ K = POP_K_MULT เท่า
  · คนเป็นทั้งจักรวาลถึง POP_CEILING แล้ว repopulate ไม่เติมคนอีก
  · คนที่ตายเกิน PRUNE_DEAD_YEARS ปีกลายเป็นบันทึกย่อที่ cid เดิม เว้นคนที่ยังมีลูกเล็กหรือเด็กในความดูแลที่ยังมีชีวิต
    ทองรวมไม่เปลี่ยน และบันทึกย่อเซฟ/โหลดได้
"""
import contextlib
import io
import os
import tempfile
import unittest
from dataclasses import fields
from unittest import mock

from tiandao import config as C
from tiandao import events as E
from tiandao import persist as PS
from tiandao import sim as S
from tiandao import wages as WAGES
from tiandao.models import Character, Departed

BIRTH = next(e for e in E.EVENT_TABLE if e["kind"] == "กำเนิดทายาท")


def quiet(fn, *a, **kw):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*a, **kw)


class FertilityTests(unittest.TestCase):
    def setUp(self):
        self.sim = quiet(S.Sim, seed=5)
        self.world = self.sim.world(0)
        self.target = self.sim.realm_target(self.world)

    def at(self, n):
        self.world.n_alive = n
        return self.sim.fertility(self.world)

    def test_full_until_the_realm_is_full_then_falls_to_zero_at_k(self):
        k = C.POP_K_MULT * self.target
        self.assertEqual(self.at(self.target), 1.0)
        self.assertAlmostEqual(self.at((self.target + k) / 2), 0.5)
        self.assertEqual(self.at(k), 0.0)
        self.assertEqual(self.at(k + 50), 0.0)

    def test_a_couple_in_a_realm_at_k_has_no_child(self):
        people = [c for c in self.sim.living_in(0) if c.age(self.sim.day) >= 20 and c.sentient]
        a = next(c for c in people if c.gender == "ชาย")
        t = next(c for c in people if c.gender == "หญิง")
        before = len(self.sim.cast)
        self.world.n_alive = int(C.POP_K_MULT * self.target)
        outcome, _text, _d = quiet(self.sim.resolve, BIRTH, a, t, self.world, 30, self.sim.rng)
        self.assertEqual(outcome, "ยังไม่มีทายาท")
        self.assertEqual(len(self.sim.cast), before)


class CeilingTests(unittest.TestCase):
    def test_no_one_is_brought_in_once_the_whole_world_is_at_the_ceiling(self):
        sim = quiet(S.Sim, seed=5)
        world = sim.world(0)
        world.n_alive = 0                                  # แดนนี้ขาดคนเต็มที่
        before = len(sim.cast)
        with mock.patch.object(C, "POP_CEILING", len(sim.alive_cids)):
            quiet(sim.repopulate, world, 365)
        self.assertEqual(len(sim.cast), before)
        with mock.patch.object(C, "POP_CEILING", len(sim.alive_cids) + 1000):
            quiet(sim.repopulate, world, 365)
        self.assertGreater(len(sim.cast), before, "ต่ำกว่าเพดานยังเติมคนได้ตามปกติ")


class PruneTests(unittest.TestCase):
    def setUp(self):
        self.sim = quiet(S.Sim, seed=5)
        sim = self.sim
        sim.day = 50 * 365
        people = [c for c in sim.cast if c.alive and c.sentient]
        self.old, self.recent, self.parent, self.guardian, self.kid, self.ward = people[:6]
        for ch in (self.old, self.recent, self.parent, self.guardian):
            ch.children, ch.wards = [], []
        self.kid.born_day = sim.day - 5 * 365                      # ลูกเล็กที่ยังมีชีวิต
        self.parent.children = [self.kid.cid]
        self.old.money = {0: 123.0}
        long_ago = sim.day - (C.PRUNE_DEAD_YEARS + 1) * 365
        for ch in (self.old, self.parent, self.guardian):
            quiet(sim.kill, ch, "ทดสอบ", natural=True)
            ch.death_day = long_ago
        self.guardian.wards = [self.ward.cid]          # ตั้งหลังตาย (การตายส่งเด็กต่อให้คนอื่นแล้ว) เพื่อทดสอบเงื่อนไขนี้ตรงๆ
        quiet(sim.kill, self.recent, "ทดสอบ", natural=True)
        self.tiers = {w.tier for w in sim.worlds}
        self.gold = {t: WAGES.total_gold(sim, t) for t in self.tiers}
        sim.prune_departed()

    def test_the_long_dead_become_a_short_record_at_the_same_cid(self):
        ch = self.sim.cast[self.old.cid]
        self.assertIs(type(ch), Departed)
        self.assertEqual((ch.cid, ch.name, ch.alive), (self.old.cid, self.old.name, False))
        for f in fields(Character):
            getattr(ch, f.name)                                     # อ่านได้ทุก field ไม่พัง

    def test_the_recently_dead_and_those_with_living_dependants_are_kept_whole(self):
        for ch in (self.recent, self.parent, self.guardian):
            self.assertIs(type(self.sim.cast[ch.cid]), Character)

    def test_gold_totals_do_not_change(self):
        for t in self.tiers:
            self.assertAlmostEqual(WAGES.total_gold(self.sim, t), self.gold[t], places=6)

    def test_the_short_record_survives_save_and_load(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "world.save")
            PS.save_sim(self.sim, path)
            back = PS.load_sim(path)
        ch = back.cast[self.old.cid]
        self.assertIs(type(ch), Departed)
        self.assertEqual(ch.name, self.old.name)


if __name__ == "__main__":
    unittest.main()
