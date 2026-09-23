# -*- coding: utf-8 -*-
"""การมีทายาท — ต้องเลือกคู่ที่มีทายาทร่วมกันได้จริง ไม่ใช่สุ่มใครก็ได้

    python -m unittest test_heirs -v
"""
import contextlib
import io
import unittest

from tiandao import config as C
from tiandao import events as E
from tiandao import intent as IN
from tiandao import sim as S


def quiet(fn, *a, **kw):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*a, **kw)


class Base(unittest.TestCase):
    def setUp(self):
        self.sim = quiet(S.Sim, seed=5, tiers=2)
        self.day = self.sim.day
        pool = [c for c in self.sim.living_in(0) if c.age(self.day) >= C.ADULT_AGE]
        self.me = next(c for c in pool if c.gender == "ชาย")
        self.others = [c for c in pool if c.cid != self.me.cid][:8]


class TestPartnerChoice(Base):
    def test_engine_births_succeed_when_partner_is_valid(self):
        mate = next(c for c in self.others if c.gender == "หญิง" and c.age(self.day) >= C.ADULT_AGE)
        outcome, text, d = self.sim.resolve({"kind": "กำเนิดทายาท", "tgt": True}, self.me, mate,
                                            self.sim.worlds[0], 0, self.sim.rng)
        self.assertEqual(outcome, "กำเนิด", text)
        self.assertEqual(self.me.spouse, mate.cid)

    def test_same_gender_still_fails_at_the_handler(self):
        same = next(c for c in self.others if c.gender == self.me.gender)
        outcome, _, _ = self.sim.resolve({"kind": "กำเนิดทายาท", "tgt": True}, self.me, same,
                                         self.sim.worlds[0], 0, self.sim.rng)
        self.assertEqual(outcome, "ล้มเหลว")

    def test_weigh_drops_the_option_without_any_valid_partner(self):
        males = [c for c in self.others if c.gender == "ชาย"] or [self.others[0]]
        for c in males:
            c.gender = "ชาย"
        self.me.gender = "ชาย"
        w = IN.weigh(self.me, self.sim, E.EVENT_TABLE, True, others=males)
        self.assertEqual(w.get("กำเนิดทายาท", 0), 0.0)
        mate = self.others[0]
        mate.gender = "หญิง"
        w2 = IN.weigh(self.me, self.sim, E.EVENT_TABLE, True, others=males + [mate])
        self.assertGreater(w2.get("กำเนิดทายาท", 0), 0.0)

    def test_children_keep_appearing_in_a_long_world(self):
        sim = quiet(S.Sim, seed=11, tiers=2)
        quiet(sim.run, 30000)
        births = [e for e in sim.log if e.kind == "กำเนิดทายาท"]
        got = [e for e in births if e.outcome == "กำเนิด"]
        self.assertTrue(births)
        self.assertGreater(len(got) / len(births), 0.8,
                           f"การมีทายาทสำเร็จแค่ {len(got)}/{len(births)} — เลือกคู่ผิดคนอยู่")
        alive = sim.living_in(0)
        self.assertTrue(alive, "โลกมนุษย์ต้องยังมีคน")
        self.assertTrue(any(c.age(sim.day) < 16 for c in alive), "ต้องยังมีเด็กเกิดใหม่ในโลก")


if __name__ == "__main__":
    unittest.main()
