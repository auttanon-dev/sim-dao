# -*- coding: utf-8 -*-
"""โหมดดาวเคราะห์ (units.py) และตารางแร่จริง (minerals.py)

    python -m unittest test_planet_scale -v

สัญญาที่ล็อกไว้
  1. ค่าตั้งคือปิด และตอนปิดความเร็ว/วันเดินทางต้องเท่าสูตรเดิมทุกค่า (ซิมเดิมไม่เปลี่ยน)
  2. ตอนเปิด ระยะคิดเป็น กม. จริง: ปุถุชนเดิน 30 กม./วัน ข้ามโลกมนุษย์ใช้เวลาเป็นปี ผู้บำเพ็ญขั้นสูงใช้เป็นวัน
  3. แผนที่ของโลกหนึ่งใบต้องไม่กว้างเกินครึ่งเส้นรอบวงดาวของมัน
  4. แร่ทุกชนิดในเรื่องมีแร่จริงรองรับ และค่ากายภาพอยู่ในช่วงที่เป็นไปได้
"""
import types
import unittest

from tiandao import config as C
from tiandao import crafting as CR
from tiandao import geo as GEO
from tiandao import minerals as MIN
from tiandao import places as PL
from tiandao import terrain as TER
from tiandao import travel as TR
from tiandao import units as U


def planet_cfg(**over):
    """สำเนา config ที่เปิดโหมดดาวเคราะห์ — ไม่แตะ config จริง เทสต์อื่นจึงไม่ได้รับผล"""
    ns = types.SimpleNamespace(**{k: getattr(C, k) for k in dir(C) if k.isupper()})
    ns.REAL_DISTANCE = True
    for k, v in over.items():
        setattr(ns, k, v)
    return ns


def human_world():
    return [i for i, p in enumerate(PL.PLACES) if p[1] == 0]


class DefaultIsUnchanged(unittest.TestCase):
    def test_off_by_default(self):
        self.assertFalse(C.REAL_DISTANCE)

    def test_speed_matches_the_old_formula(self):
        for realm in range(0, 30):
            old = C.TRAVEL_BASE_SPEED * (1.0 + C.TRAVEL_REALM_SPEEDUP * realm)
            self.assertEqual(TR.travel_speed(realm), old)


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
        old = TR.shortest_path_days(places[0], far, 0)
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
                self.assertIn(m["setting"], MIN.SETTING_BIOMES)
                self.assertTrue(MIN.describe(name).startswith(name))

    def test_known_facts(self):
        self.assertEqual(max(MIN.REAL_MINERALS, key=lambda n: MIN.REAL_MINERALS[n]["mohs"]), "แร่วัชรเพชรสวรรค์")
        self.assertEqual(max(MIN.REAL_MINERALS, key=lambda n: MIN.REAL_MINERALS[n]["density"]), "ทองคำเซียนบริสุทธิ์")
        self.assertTrue(MIN.scratches("แร่วัชรเพชรสวรรค์", "แร่เหล็กไหลแท้"))
        self.assertFalse(MIN.scratches("ทองคำเซียนบริสุทธิ์", "แร่เหล็กไหลแท้"))
        self.assertAlmostEqual(MIN.mass_kg("ทองคำเซียนบริสุทธิ์", 300), 5.79, places=2)

    def test_every_setting_names_biomes_the_map_really_has(self):
        seen = {TER.compute_place_3d_and_biome(i)[3] for i in range(len(PL.PLACES))}
        for setting, biomes in MIN.SETTING_BIOMES.items():
            with self.subTest(setting=setting):
                self.assertTrue(set(biomes) & seen, f"ไม่มี biome ของ {setting} อยู่บนแผนที่เลย")

    def test_non_ores_are_unrestricted(self):
        self.assertIsNone(MIN.real_of("หญ้าปราณเขียว"))
        self.assertTrue(MIN.fits_biome("หญ้าปราณเขียว", "plains"))


if __name__ == "__main__":
    unittest.main()
