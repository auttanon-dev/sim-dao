# -*- coding: utf-8 -*-
"""กิจวัตรวัยเด็กรายปี (tiandao/childhood.py, แบบ §7.2 ขั้น A)

    python -m unittest test_upbringing -v
"""
import contextlib
import io
import unittest

from tiandao import childhood as CHILD
from tiandao import config as C
from tiandao import food as FOOD
from tiandao import sim as S


def quiet(fn, *a, **kw):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*a, **kw)


class UpbringingTests(unittest.TestCase):
    def setUp(self):
        self.sim = quiet(S.Sim, seed=5)
        self.sim.day = 5000
        self.world = self.sim.world(0)
        self.adult = next(c for c in self.sim.living_in(0) if c.sentient and 25 <= c.age(self.sim.day) <= 50)

    def child(self, age, place=None):
        kid = quiet(self.sim.spawn, self.world, age_years=0)
        kid.born_day = self.sim.day - age * 365 - 10
        kid.place = self.adult.place if place is None else place
        kid.parents = [self.adult.cid]
        kid.guardian = self.adult.cid
        self.adult.wards.append(kid.cid)
        return kid

    def turn(self, kid):
        return quiet(CHILD.turn, self.sim, kid, self.world, 0, self.sim.rng)

    def test_an_infant_is_cared_for_and_the_bond_grows_by_the_days_spent(self):
        kid = self.child(1)
        before = kid.bonds.get(self.adult.cid, 0)
        self.turn(kid)
        p = kid.process
        self.assertEqual((p.kind, p.payload["routine"], p.payload["with"]), ("upbringing", CHILD.CARE, [self.adult.cid]))
        self.assertEqual(p.end_day, kid.born_day + 2 * 365, "ถึงวันเกิดถัดไป")
        self.sim.day += 365 // 2
        self.sim.settle_routine(kid)
        self.assertEqual(kid.bonds[self.adult.cid] - before, int(C.CHILD_BOND_PER_YEAR / 2))
        self.assertEqual(self.adult.bonds[kid.cid], int(C.CHILD_BOND_PER_YEAR / 2))

    def test_children_in_the_same_place_play_and_bond_both_ways(self):
        kid = self.child(8)
        friend = self.child(9)
        self.adult.place = kid.place + 1                    # ผู้ดูแลไม่อยู่ เรียนที่บ้านได้น้ำหนักต่ำ
        seen = set()
        for day in range(40):
            self.sim.day = 5000 + day
            kid.process = None
            routine, with_ = CHILD.choose(self.sim, kid, CHILD._rng(self.sim, kid))
            seen.add(routine)
            if routine == CHILD.PLAY:
                self.assertIn(friend.cid, with_)
        self.assertIn(CHILD.PLAY, seen)
        kid.process = None
        self.sim.start_process(kid, "upbringing", 365, {"routine": CHILD.PLAY, "with": [friend.cid],
                                                        "guardian": kid.guardian, "carry": {}},
                               C.CHILD_BOND_PER_YEAR)
        self.sim.day += 365
        self.sim.settle_routine(kid)
        self.assertEqual((kid.bonds[friend.cid], friend.bonds[kid.cid]), (3, 3))

    def test_choosing_a_routine_does_not_touch_the_world_rng(self):
        kid = self.child(6)
        state = self.sim.rng.getstate()
        CHILD.start(self.sim, kid, kid.born_day + 7 * 365, CHILD._rng(self.sim, kid))
        self.assertEqual(self.sim.rng.getstate(), state)

    def test_a_change_of_guardian_stops_the_routine_and_the_child_chooses_again_today(self):
        kid = self.child(5)
        self.turn(kid)
        self.sim.day += 100
        kid.guardian = -1
        quiet(self.sim.check_processes)
        self.assertIsNone(kid.process)
        self.assertIn((self.sim.day, kid.cid), self.sim.queue)
        self.assertEqual(self.sim.process_stats["upbringing:ผู้ปกครองเปลี่ยน"], 1)

    def test_hunger_stops_the_routine(self):
        kid = self.child(9)
        self.turn(kid)
        self.sim.day += 30
        quiet(FOOD._respond, self.sim, kid)
        self.assertFalse(kid.process is not None and kid.process.kind == "upbringing")

    def test_a_routine_still_open_at_fourteen_is_settled_on_the_first_adult_turn(self):
        kid = self.child(13)
        self.turn(kid)
        self.sim.day = kid.process.end_day + 5
        self.sim.queue = [(self.sim.day, kid.cid)]
        quiet(self.sim.step)
        self.assertFalse(kid.process is not None and kid.process.kind == "upbringing")

    def test_a_running_world_uses_the_routines(self):
        sim = quiet(S.Sim, seed=11)
        quiet(sim.run, 20000)
        routines = [e.deltas.get("กิจวัตร") for e in sim.log if e.kind == "เติบโต"]
        self.assertTrue({CHILD.CARE, CHILD.PLAY, CHILD.HOME} <= set(routines), set(routines))


if __name__ == "__main__":
    unittest.main()
