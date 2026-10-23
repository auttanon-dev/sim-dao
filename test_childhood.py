# -*- coding: utf-8 -*-
"""วัยเด็กต้องเป็นช่วงชีวิตจริง ไม่ใช่ผู้ใหญ่ตัวเล็ก และต้องตามไปถึงชีวประวัติ."""
import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from tiandao import events as E
from tiandao import sim as S


def quiet(fn, *args, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*args, **kwargs)


class ChildhoodTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sim = quiet(S.Sim, seed=81, tiers=1)

    def test_child_turn_is_growth_not_an_adult_action(self):
        sim = self.sim
        father, mother = sim.cast[0], sim.cast[1]
        child = sim.spawn(sim.worlds[0], age_years=0)
        child.parents = [father.cid, mother.cid]
        before_skills = list(child.skills)
        sim.day = child.born_day
        event = sim._childhood_turn(child, sim.worlds[0], 0, sim.rng)
        self.assertEqual(event.kind, "เติบโต")
        self.assertEqual(event.outcome, "ได้รับการเลี้ยงดู")
        self.assertEqual(child.skills, before_skills)
        self.assertEqual(child.childhood[0]["age"], 0)



    def test_parent_realm_bonus_is_applied_once(self):
        sim = self.sim
        adults = [c for c in sim.living_in(0) if c.age(sim.day) >= 16]
        father = next(c for c in adults if c.gender == "ชาย")
        mother = next(c for c in adults if c.gender == "หญิง")
        father.realm, mother.realm = 3, 4
        before = len(sim.cast)
        outcome, _text, _details = sim.resolve(
            {"kind": "กำเนิดทายาท", "tgt": True}, father, mother,
            sim.worlds[0], 0, sim.rng)
        self.assertEqual(outcome, "ตั้งครรภ์")
        sim.day = mother.pregnancy.end_day
        child = sim.deliver(mother)
        self.assertEqual(child.cid, before)
        self.assertEqual(child.insight, 14.0)
        self.assertEqual(child.refine, 14.0)


class MindOutputGuardsTests(unittest.TestCase):
    pass




if __name__ == "__main__":
    unittest.main()
