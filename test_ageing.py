# -*- coding: utf-8 -*-
"""อายุขัยและความชรา (แบบ §7.3)

    python -m unittest test_ageing -v
"""
import contextlib
import io
import random
import statistics as st
import unittest

from tiandao import config as C
from tiandao import rules as R
from tiandao import sim as S


def quiet(fn, *a, **kw):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*a, **kw)


class LifespanDrawTests(unittest.TestCase):
    def test_the_mortal_curve_stays_in_its_bounds_around_seventy_two(self):
        rng = random.Random(1)
        draws = [R.natural_lifespan(rng.random(), 0) for _ in range(20000)]
        self.assertGreaterEqual(min(draws), C.MORTAL_LIFESPAN_MIN)
        self.assertLessEqual(max(draws), C.MORTAL_LIFESPAN_MAX)
        self.assertAlmostEqual(st.median(draws), C.MORTAL_LIFESPAN_MU, delta=1.0)

    def test_the_draw_always_leaves_at_least_a_year_after_the_age_it_must_survive(self):
        rng = random.Random(2)
        for age in (0, 30, 60, 80, 94, 95, 120, 500):
            for _ in range(500):
                life = R.natural_lifespan(rng.random(), age)
                self.assertGreater(life, age, f"อายุ {age}")
                if age + 1 >= C.MORTAL_LIFESPAN_MAX:
                    self.assertLessEqual(life, age + 1 + C.LIFESPAN_TAIL_YEARS, "แก่กว่าเส้นแล้วอยู่ต่อได้ไม่นาน")


class SpawnTests(unittest.TestCase):
    def setUp(self):
        self.sim = quiet(S.Sim, seed=11)

    def test_nobody_in_a_new_world_starts_past_their_lifespan(self):
        over = [c.cid for c in self.sim.living() if c.age(self.sim.day) >= c.lifespan()]
        self.assertEqual(over, [], "เดิม 27–29% ของคนรุ่นแรกเกิดมาเกินอายุขัย")

    def test_adults_created_later_arrive_with_life_left(self):
        for age in (20, 45, 70, 90, 94):
            for _ in range(30):
                ch = quiet(self.sim.spawn, self.sim.worlds[0], age_years=age)
                self.assertGreater(ch.lifespan(), ch.age(self.sim.day), f"อายุ {age}")

    def test_no_mortal_dies_of_old_age_before_forty_five(self):
        quiet(self.sim.run, 20000)
        young = [c for c in self.sim.cast if not c.alive and c.death_cause == "สิ้นอายุขัย"
                 and (c.death_day - c.born_day) / 365 < C.MORTAL_LIFESPAN_MIN]
        self.assertEqual(young, [])


if __name__ == "__main__":
    unittest.main()
