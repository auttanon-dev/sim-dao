# -*- coding: utf-8 -*-
"""ความเสี่ยงขึ้นกับเวลาที่เผชิญ ไม่ใช่จำนวนครั้งที่ถูกตรวจ (แบบ §5.4) — physics.hazard_p

    python -m unittest test_hazards -v
"""
import random
import unittest

from tiandao import config as C
from tiandao import physics as PHYS
from tiandao import travel as TR


class HazardTests(unittest.TestCase):
    def test_each_rate_reproduces_the_old_chance_at_the_old_cadence(self):
        for rate, days, old in ((C.TRAVEL_MISHAP_PER_YEAR, 15, 0.08), (C.CRUSADE_PER_YEAR, 30, 0.30),
                                (C.DEMON_TEMPTATION_PER_YEAR, 30, 0.05), (C.BEAST_CITY_RAID_PER_YEAR, 30, 0.10),
                                (C.CHAOS_SPAWN_PER_YEAR, 30, 0.02)):
            self.assertAlmostEqual(PHYS.hazard_p(rate, days), old, places=3)

    def test_risk_grows_with_exposure_and_splitting_time_changes_nothing(self):
        r = C.TRAVEL_MISHAP_PER_YEAR
        self.assertEqual(PHYS.hazard_p(r, 0), 0.0)
        self.assertLess(PHYS.hazard_p(r, 5), PHYS.hazard_p(r, 15))
        # สองช่วง 15 วันเท่ากับหนึ่งช่วง 30 วัน — ตรวจถี่แค่ไหนความเสี่ยงรวมก็เท่าเดิม
        survive_twice = (1 - PHYS.hazard_p(r, 15)) ** 2
        self.assertAlmostEqual(1 - survive_twice, PHYS.hazard_p(r, 30))

    def test_a_short_final_leg_of_travel_is_less_risky(self):
        rng = random.Random(1)
        n = 20000
        short = sum(TR.roll_enroute_event(rng, days=3) is not None for _ in range(n))
        full = sum(TR.roll_enroute_event(rng, days=15) is not None for _ in range(n))
        self.assertLess(short, full * 0.4)
        self.assertEqual(sum(TR.roll_enroute_event(rng, days=0) is not None for _ in range(1000)), 0)


if __name__ == "__main__":
    unittest.main()
