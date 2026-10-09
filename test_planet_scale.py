# -*- coding: utf-8 -*-
"""โหมดดาวเคราะห์ (units.py) และตารางแร่จริง (minerals.py)

    python -m unittest test_planet_scale -v

สัญญาที่ล็อกไว้
  1. ปิดโหมด (REAL_DISTANCE = False) แล้วความเร็ว/วันเดินทางต้องเท่าสูตรเดิมทุกค่า
  2. ตอนเปิด ระยะคิดเป็น กม. จริง: ปุถุชนเดิน 30 กม./วัน ข้ามโลกมนุษย์ใช้เวลาเป็นปี ผู้บำเพ็ญขั้นสูงใช้เป็นวัน
  3. แผนที่ของโลกหนึ่งใบต้องไม่กว้างเกินครึ่งเส้นรอบวงดาวของมัน
  4. แร่ทุกชนิดในเรื่องมีแร่จริงรองรับ และค่ากายภาพอยู่ในช่วงที่เป็นไปได้
"""
import types
import unittest

from tiandao import config as C
from tiandao import crafting as CR
from tiandao import geo as GEO
from tiandao import materials as MAT
from tiandao import minerals as MIN
from tiandao import places as PL
from tiandao import travel as TR
from tiandao import units as U


def planet_cfg(on=True, **over):
    """สำเนา config ที่เปิด/ปิดโหมดระยะทางจริง — ไม่แตะ config จริง เทสต์อื่นจึงไม่ได้รับผล"""
    ns = types.SimpleNamespace(**{k: getattr(C, k) for k in dir(C) if k.isupper()})
    ns.REAL_DISTANCE = on
    for k, v in over.items():
        setattr(ns, k, v)
    return ns


def human_world():
    return [i for i, p in enumerate(PL.PLACES) if p[1] == 0]


class SwitchedOffIsTheOldFormula(unittest.TestCase):
    def test_speed_matches_the_old_formula(self):
        off = planet_cfg(on=False)
        for realm in range(0, 30):
            old = C.TRAVEL_BASE_SPEED * (1.0 + C.TRAVEL_REALM_SPEEDUP * realm)
            self.assertEqual(TR.travel_speed(realm, off), old)


class PlanetMode(unittest.TestCase):
    def setUp(self):
        self.cfg = planet_cfg()

    def test_a_mortal_walks_thirty_km_a_day(self):
        self.assertAlmostEqual(TR.travel_speed(0, self.cfg) * U.km_per_unit(self.cfg), 30.0)

    def test_speed_grows_with_every_realm(self):
        speeds = [U.km_per_day(r, self.cfg) for r in range(30)]
        self.assertEqual(speeds, sorted(speeds))
        self.assertGreater(speeds[9] / speeds[0], 20)       # ยอดโลกมนุษย์เร็วกว่าคนเดินเท้าหลายสิบเท่า
        self.assertGreater(speeds[19] / speeds[9], 20)

    def test_crossing_the_human_world_takes_a_mortal_years_and_an_immortal_days(self):
        places = human_world()
        dist = TR.distances_from(places[0])
        far = max((p for p in places if p in dist), key=lambda p: dist[p])
        mortal = TR.shortest_path_days(places[0], far, 0, self.cfg)
        immortal = TR.shortest_path_days(places[0], far, 15, self.cfg)
        old = TR.shortest_path_days(places[0], far, 0, planet_cfg(on=False))
        self.assertGreater(mortal, 365)
        self.assertGreater(mortal, 5 * old)
        self.assertLess(immortal, 10)

    def test_each_world_map_fits_on_half_its_planet(self):
        tier_of = {0: 0, 1: 1, 2: 2}
        for key, tier in tier_of.items():
            idx = [i for i, p in enumerate(PL.PLACES) if p[1] == key]
            xs = [GEO.COORDS[i][0] for i in idx]
            ys = [GEO.COORDS[i][1] for i in idx]
            span_km = U.to_km(max(max(xs) - min(xs), max(ys) - min(ys)), self.cfg)
            with self.subTest(world=key):
                self.assertLessEqual(span_km, U.planet_of(tier)["circumference_km"] / 2)

    def test_km_round_trips(self):
        self.assertAlmostEqual(U.to_units(U.to_km(37.5, self.cfg), self.cfg), 37.5)

    def test_higher_worlds_are_bigger_and_heavier(self):
        p = [U.planet_of(t) for t in (0, 1, 2)]
        self.assertAlmostEqual(p[0]["circumference_km"], 40030, delta=10)
        self.assertLess(p[0]["radius_km"], p[1]["radius_km"])
        self.assertLess(p[1]["gravity"], p[2]["gravity"])


class RealMinerals(unittest.TestCase):
    def test_every_ore_has_a_real_mineral_and_nothing_extra(self):
        self.assertEqual(set(MIN.REAL_MINERALS), {n for n, _ in CR.ORES})

    def test_physical_values_are_plausible(self):
        for name, m in MIN.REAL_MINERALS.items():
            with self.subTest(ore=name):
                self.assertTrue(1.0 <= m["mohs"] <= 10.0)
                self.assertTrue(2.0 <= m["density"] <= 22.6)        # ออสเมียม 22.59 คือธาตุที่หนาแน่นที่สุด
                self.assertTrue(m["melt_c"] is None or 200 < m["melt_c"] < 3500)
                self.assertTrue(m["settings"] and set(m["settings"]) <= set(MIN.SETTING_NAMES))
                self.assertTrue(any(MIN.fits_province(name, p) for p in MIN.PROVINCES))
                self.assertTrue(MIN.describe(name).startswith(name))

    def test_known_facts(self):
        self.assertEqual(max(MIN.REAL_MINERALS, key=lambda n: MIN.REAL_MINERALS[n]["mohs"]), "แร่วัชรเพชรสวรรค์")
        self.assertEqual(max(MIN.REAL_MINERALS, key=lambda n: MIN.REAL_MINERALS[n]["density"]), "ทองคำเซียนบริสุทธิ์")
        self.assertTrue(MIN.scratches("แร่วัชรเพชรสวรรค์", "แร่เหล็กไหลแท้"))
        self.assertFalse(MIN.scratches("ทองคำเซียนบริสุทธิ์", "แร่เหล็กไหลแท้"))
        self.assertAlmostEqual(MIN.mass_kg("ทองคำเซียนบริสุทธิ์", 300), 5.79, places=2)

    def test_non_ores_are_unrestricted(self):
        self.assertIsNone(MIN.real_of("หญ้าปราณเขียว"))
        self.assertTrue(MIN.fits_province("หญ้าปราณเขียว", "basin"))


class Geology(unittest.TestCase):
    """แหล่งแร่ออกแร่ตามจังหวัดธรณี (config.ORE_GEOLOGY)"""

    def ore_sites(self):
        return [i for i, p in enumerate(PL.PLACES) if p[4] == "แร่"]

    def test_provinces_are_fixed_and_balanced(self):
        counts = {}
        for i in range(len(PL.PLACES)):
            counts[MIN.province_of(i)] = counts.get(MIN.province_of(i), 0) + 1
        self.assertEqual(set(counts), set(MIN.PROVINCES))
        self.assertLessEqual(max(counts.values()) - min(counts.values()), 1)
        from tiandao import terrain as TER
        before = [MIN.province_of(i) for i in range(len(PL.PLACES))]
        TER.use_seed(123)                       # seed ของโลกเปลี่ยน จังหวัดธรณีต้องไม่เปลี่ยน
        try:
            self.assertEqual(before, [MIN.province_of(i) for i in range(len(PL.PLACES))])
        finally:
            TER.use_seed(0)

    def test_a_site_offers_its_own_province_first_and_as_many_kinds_as_before(self):
        for i in self.ore_sites():
            got = MAT.materials_at(i)
            p = PL.PLACES[i]
            tier = MAT.WORLD_MAT_TIER.get(p[1], 0)
            pool = MAT._sorted_pool("แร่", tier)
            with self.subTest(place=p[0]):
                self.assertEqual(len(got), min(len(pool), MAT.GRADE_DEPTH.get(p[2], 2)))
                fits = [MIN.fits_province(m, MIN.province_of(i)) for m in got]
                self.assertEqual(fits, sorted(fits, reverse=True))      # ที่เข้าจังหวัดมาก่อนทั้งหมด

    def test_ordinary_sites_no_longer_all_give_the_same_two_ores(self):
        tier0 = [i for i in self.ore_sites() if MAT.WORLD_MAT_TIER.get(PL.PLACES[i][1], 0) == 0]
        self.assertGreater(len({tuple(MAT.materials_at(i)[:2]) for i in tier0}), 1)

    def test_every_ore_still_has_a_source_somewhere(self):
        for name in MIN.REAL_MINERALS:
            with self.subTest(ore=name):
                self.assertTrue(MAT.sources_of(name))

    def test_hard_ore_makes_a_better_blade_and_soft_ore_a_worse_one(self):
        w = C.ORE_QUALITY_W
        self.assertEqual(MIN.forge_quality([("หญ้าปราณเขียว", 2)], w), 1.0)
        self.assertEqual(MIN.forge_quality([("แร่วัชรเพชรสวรรค์", 1)], w), 1.0 + w)
        soft = MIN.forge_quality([("ทองคำเซียนบริสุทธิ์", 1)], w)
        hard = MIN.forge_quality([("แร่เหล็กไหลแท้", 1)], w)
        self.assertLess(soft, 1.0)
        self.assertGreater(hard, 1.0)
        self.assertGreaterEqual(soft, 1.0 - w)
        self.assertEqual(MIN.forge_quality([("แร่เหล็กไหลแท้", 1)], 0.0), 1.0)


class FoodTransport(unittest.TestCase):
    """โหมดระยะทางจริง: ข้าวที่ขนส่งสูญตามกิโลเมตร ไม่ใช่ตามจำนวนก้าว"""

    def test_loss_follows_real_road_distance(self):
        from tiandao import food as FOOD
        self.assertTrue(C.REAL_DISTANCE)
        places = human_world()
        dist = TR.distances_from(places[0])
        near, far = sorted((p for p in places[1:] if p in dist), key=lambda p: dist[p])[::len(places) - 2][:2]
        k_near, k_far = FOOD._carry_keep(places[0], near, 1), FOOD._carry_keep(places[0], far, 1)
        self.assertGreater(k_near, k_far)                    # ก้าวเท่ากัน ไกลกว่าเสียมากกว่า
        self.assertAlmostEqual(k_near, (1 - C.FOOD_CARRY_LOSS_PER_1000KM) ** (U.to_km(dist[near]) / 1000))
        self.assertTrue(0.0 < k_far < 1.0)


if __name__ == "__main__":
    unittest.main()
