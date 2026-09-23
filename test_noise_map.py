# -*- coding: utf-8 -*-
"""แผนที่มาจากเมล็ด — Perlin gradient noise แทนตารางเกรดที่พิมพ์ไว้

    python -m unittest test_noise_map -v

สมการที่ล็อกไว้:  n(p) = Σ w_i · [ g_i · (p - p_i) ]

ก่อนแก้: `terrain._noise_2d` เป็นผลบวกของไซน์สามตัวที่ seed เข้าไป **ในเฟส**
`sin(x*0.035 + seed*1.7)` ซึ่งไม่ได้เปลี่ยนสนาม มัน **เลื่อน** สนามเดิม และที่เรียกใช้
ก็ส่ง `seed=42` คงที่ทุกที่ ทุกโลกจึงมีภูมิประเทศชุดเดียวกันเป๊ะ
ส่วนความหนาแน่นปราณมาจากเลข 0/1/2 ในตาราง PLACES ซึ่งเหมือนกันทุกเมล็ด

คุณสมบัติสามข้อที่ทำให้ gradient noise ต่างจากการสุ่มธรรมดา และห้ามหาย:
  1. **ค่าเป็นศูนย์ที่ทุกมุมแลตทิซ** — เพราะ (p - p_i) = 0 ยอดจึงไปโผล่กลางช่อง
     ไม่ใช่บนมุม ซึ่งเป็นเหตุผลทั้งหมดที่ Perlin ชนะ value noise
  2. **สหสัมพันธ์เชิงพื้นที่** — ที่อยู่ใกล้กันปราณใกล้เคียงกัน จึงเกิด "แถบปราณ" ที่
     ครองเป็นดินแดนได้ ซึ่งการสุ่มรายจุดให้ไม่ได้เลย
  3. **ไม่มีทิศที่ชอบ** — ถ้าสนามเอนไปตามแกน แถบปราณทุกเส้นจะวิ่งเหนือ-ใต้เหมือนกันหมด
"""
import contextlib
import io
import math
import statistics as st
import unittest

from tiandao import config as C
from tiandao import economy as EC
from tiandao import geo as GEO
from tiandao import noise as NZ
from tiandao import places as PL
from tiandao import sim as S
from tiandao import terrain as TERRAIN


def quiet(fn, *a, **kw):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*a, **kw)


class TestItIsRealGradientNoise(unittest.TestCase):
    def test_the_value_is_zero_at_every_lattice_corner(self):
        """g_i·(p - p_i) = 0 เมื่อ p อยู่บนมุมพอดี — ลายเซ็นของ gradient noise"""
        f = NZ.Field(7)
        for i in range(-3, 4):
            for j in range(-3, 4):
                self.assertAlmostEqual(f.noise(float(i), float(j)), 0.0, places=12)

    def test_it_is_continuous_across_cell_edges(self):
        """ข้ามขอบช่องแล้วค่าต้องไม่กระโดด ไม่งั้นจะเห็นเป็นเส้นตารางบนแผนที่"""
        f = NZ.Field(3)
        for edge in (1.0, 2.0, -1.0):
            a = f.noise(edge - 1e-7, 0.31)
            b = f.noise(edge + 1e-7, 0.31)
            self.assertLess(abs(a - b), 1e-5)

    def test_the_quintic_fade_flattens_at_both_ends(self):
        """f'(0)=f'(1)=0 และ f''(0)=f''(1)=0 — ความชันของสนามจึงต่อเนื่องข้ามขอบช่อง"""
        h = 1e-5
        for t in (0.0, 1.0):
            d1 = (NZ.fade(min(1.0, t + h)) - NZ.fade(max(0.0, t - h))) / (2 * h)
            self.assertLess(abs(d1), 1e-3)
        self.assertAlmostEqual(NZ.fade(0.5), 0.5, places=12)

    def test_it_has_no_preferred_direction(self):
        """ความแปรปรวนตามแกน x แกน y และแนวทแยง ต้องใกล้เคียงกัน"""
        f = NZ.Field(11)
        along_x = st.pstdev([f.noise(t * 0.17, 0.5) for t in range(400)])
        along_y = st.pstdev([f.noise(0.5, t * 0.17) for t in range(400)])
        diag = st.pstdev([f.noise(t * 0.12, t * 0.12) for t in range(400)])
        lo, hi = min(along_x, along_y, diag), max(along_x, along_y, diag)
        self.assertLess(hi / max(1e-9, lo), 1.6,
                        "สนามเอนไปทางใดทางหนึ่ง แถบปราณจะวิ่งทิศเดียวกันหมด")

    def test_the_output_stays_in_range_without_clamping(self):
        f = NZ.Field(5)
        vals = [f.fbm(i * 0.13, j * 0.17, octaves=5)
                for i in range(80) for j in range(80)]
        self.assertGreaterEqual(min(vals), 0.0)
        self.assertLessEqual(max(vals), 1.0)
        self.assertAlmostEqual(st.mean(vals), 0.5, delta=0.06)

    def test_more_octaves_add_detail_without_shifting_the_average(self):
        f = NZ.Field(5)
        pts = [(i * 0.31, j * 0.29) for i in range(50) for j in range(50)]
        one = [f.fbm(x, y, octaves=1) for x, y in pts]
        five = [f.fbm(x, y, octaves=5) for x, y in pts]
        self.assertAlmostEqual(st.mean(one), st.mean(five), delta=0.05)


class TestTheSeedActuallyChangesTheField(unittest.TestCase):
    def test_the_same_seed_gives_the_same_field_forever(self):
        a, b = NZ.Field(7), NZ.Field(7)
        for x, y in ((0.3, 0.7), (12.5, -4.25), (-99.1, 55.5)):
            self.assertEqual(a.fbm(x, y), b.fbm(x, y))

    def test_a_different_seed_is_a_different_field_not_a_shifted_one(self):
        """ของเดิม seed เข้าไปในเฟส = สนามเดิมที่เลื่อนที่ ต้องพิสูจน์ว่าไม่ใช่แบบนั้นแล้ว

        ถ้าเป็นแค่การเลื่อน จะหาออฟเซตหนึ่งค่าที่ทำให้สองสนามทับกันได้ ทดสอบด้วยการหา
        สหสัมพันธ์สูงสุดข้ามออฟเซตหลายค่า — ถ้าเลื่อนทับกันได้จะมีค่าใกล้ 1
        """
        a, b = NZ.Field(7), NZ.Field(8)
        pts = [(i * 0.37, j * 0.41) for i in range(40) for j in range(40)]
        va = [a.noise(x, y) for x, y in pts]
        best = 0.0
        for off in (0.0, 0.5, 1.0, 1.5, 2.0, 3.0, 5.0, 7.5):
            vb = [b.noise(x + off, y + off) for x, y in pts]
            sa, sb = st.pstdev(va), st.pstdev(vb)
            if sa > 0 and sb > 0:
                ma, mb = st.mean(va), st.mean(vb)
                cov = sum((p - ma) * (q - mb) for p, q in zip(va, vb)) / len(va)
                best = max(best, abs(cov / (sa * sb)))
        self.assertLess(best, 0.5, "สองเมล็ดยังเป็นสนามเดียวกันที่เลื่อนที่")


class TestTheMapHasBeltsNotScatteredDots(unittest.TestCase):
    def field_at(self, sim, x, y):
        d = NZ.sphere_dir(x, y, C.PLANET_SPAN)
        return 0.5 + 0.5 * sim.qi_field().height(*d, scale=C.PLANET_SCALE)

    def test_places_close_together_share_their_qi(self):
        """semivariogram ต้องโตตามระยะแล้วอิ่มตัว — ลายเซ็นของสนามที่เกาะกลุ่มจริง

        วัดจริง (seed 7): 5 หน่วย -> 0.033 · 20 -> 0.081 · 40 -> 0.097 · 160 -> 0.096
        ระยะสหสัมพันธ์ราว 40 หน่วย = หนึ่งในสี่ของแดน เทียบกับการสุ่มรายจุดที่ได้ 0.336
        ทุกระยะเท่ากันหมด
        """
        sim = quiet(S.Sim, seed=7)
        pts = [(x, y) for x in range(-90, 91, 9) for y in range(-90, 91, 9)]

        def gap(d):
            return st.mean(abs(self.field_at(sim, x, y) - self.field_at(sim, x + d, y))
                           for x, y in pts)

        near, mid, far = gap(5.0), gap(20.0), gap(80.0)
        self.assertLess(near, mid, "ใกล้กันต้องคล้ายกันมากกว่าห่างกันปานกลาง")
        self.assertLess(mid, far * 1.05, "ต้องโตตามระยะแล้วอิ่มตัว")
        self.assertLess(far, 0.25, "ถ้าเท่ากับการสุ่มรายจุด (0.34) ก็ไม่ได้เกาะกลุ่มเลย")

    def test_the_field_is_cached_per_place_not_recomputed(self):
        sim = quiet(S.Sim, seed=7)
        first = sim.qi_field_at(3)
        self.assertEqual(sim.qi_field_at(3), first)
        self.assertIn(3, sim._qi_field_cache)

    def test_a_place_outside_the_map_gets_a_neutral_field(self):
        sim = quiet(S.Sim, seed=7)
        self.assertEqual(sim.qi_field_at(None), 0.5)
        self.assertEqual(sim.qi_field_at(10 ** 9), 0.5)


class TestEachSeedIsADifferentWorldToLiveIn(unittest.TestCase):
    def ceilings(self, seed):
        sim = quiet(S.Sim, seed=seed)
        w = sim.worlds[0]
        return {i: EC.place_ceiling(sim.qi_density(i, w))
                for i in PL.places_in(0, include_secrets=False)}

    def test_the_rich_valleys_move_between_seeds(self):
        a, b = self.ceilings(7), self.ceilings(99)
        moved = [i for i in a if abs(a[i] - b[i]) > 0.5]
        self.assertGreater(len(moved), len(a) * 0.3,
                           "อย่างน้อยหนึ่งในสามของสถานที่ต้องเลี้ยงคนได้คนละขั้น")

    def test_the_best_place_in_the_world_is_not_always_the_same_one(self):
        tops = set()
        for seed in (7, 8, 99, 1234):
            d = self.ceilings(seed)
            tops.add(max(d, key=lambda k: d[k]))
        self.assertGreater(len(tops), 1,
                           "ถ้าที่ปราณหนาสุดเป็นที่เดิมทุกเมล็ด แผนที่ก็ยังไม่ได้เจนจริง")

    def test_the_authored_grade_still_biases_the_result(self):
        """เกรดที่เขียนด้วยมือคือเจตนาของผู้เขียน ต้องเป็นอคติ ไม่ใช่ถูกลบทิ้ง"""
        for seed in (7, 8, 99):
            d = self.ceilings(seed)
            hi = st.mean(d[i] for i in d if PL.PLACES[i][2] == 2)
            lo = st.mean(d[i] for i in d if PL.PLACES[i][2] == 0)
            self.assertGreater(hi, lo + 2.0, f"seed {seed}: เกรดหมดความหมายไปแล้ว")

    def test_turning_the_field_off_restores_the_old_behaviour_exactly(self):
        """W=0 ต้องคืนพฤติกรรมเดิมเป๊ะ — ปรับกลับได้ถ้าไม่ชอบ"""
        sim = quiet(S.Sim, seed=7)
        w = sim.worlds[0]
        old_w = C.QI_FIELD_W
        try:
            C.QI_FIELD_W = 0.0
            for i in PL.places_in(0, include_secrets=False)[:8]:
                grade = PL.PLACES[i][2]
                plain = ((grade + 1) * C.QI_PER_GRADE
                         * (1.0 + C.QI_PER_TIER * w.tier)
                         * max(0.2, min(1.5, sim.eco_ratio(i))))
                self.assertAlmostEqual(sim.qi_density(i, w), plain, places=9)
        finally:
            C.QI_FIELD_W = old_w


class TestTheTerrainFollowsTheSameSeed(unittest.TestCase):
    def snapshot(self, seed):
        TERRAIN.use_seed(seed)
        return [TERRAIN.compute_place_3d_and_biome(i) for i in range(25)]

    def test_the_mountains_move_between_seeds(self):
        a, b = self.snapshot(7), self.snapshot(8)
        moved = sum(1 for p, q in zip(a, b) if abs(p[2] - q[2]) > 1.0)
        self.assertGreater(moved, 10, "ความสูงต้องต่างกันจริง ไม่ใช่สนามเดิมที่เลื่อนที่")

    def test_the_same_seed_draws_the_same_map(self):
        self.assertEqual([p[2:] for p in self.snapshot(7)],
                         [p[2:] for p in self.snapshot(7)])

    def test_a_sect_still_sits_higher_than_a_city(self):
        """ภูมิประเทศเพิ่มความสูงต่ำของพื้น แต่ห้ามกลบเจตนาว่าสำนักอยู่บนเขา"""
        self.snapshot(7)
        for seed in (7, 8, 99):
            TERRAIN.use_seed(seed)
            sects, cities = [], []
            for i in PL.places_in(0, include_secrets=False):
                z = TERRAIN.compute_place_3d_and_biome(i)[2]
                if PL.PLACES[i][3] == "สำนัก":
                    sects.append(z)
                elif PL.PLACES[i][3] == "เมือง":
                    cities.append(z)
            if sects and cities:
                self.assertGreater(st.mean(sects), st.mean(cities),
                                   f"seed {seed}: เมืองไปโผล่เหนือสำนัก")

    def test_the_ground_is_continuous_across_the_map(self):
        """ของเดิมส่ง seed=100+place_idx ทำให้จุดที่ติดกันได้สนามคนละผืน ภูมิประเทศกระโดด

        วัดบนตะแกรง ไม่ใช่บนสถานที่ 25 แห่ง เพราะพอสนามถูกบิดเป็นเส้นใยแล้ว สถานที่สองแห่ง
        ที่ห่างกัน 20 หน่วยอาจอยู่คนละฝั่งของเส้นปราณได้จริง — นั่นคือคุณสมบัติของเส้นใย
        ไม่ใช่ความไม่ต่อเนื่อง สิ่งที่ต้องล็อกคือสนาม **ต่อเนื่อง** ไม่ใช่ว่าเพื่อนบ้านคล้ายกันเสมอ
        """
        TERRAIN.use_seed(7)
        for x in (-50.0, 0.0, 120.0):
            a = TERRAIN._noise_2d(x, 30.0)
            b = TERRAIN._noise_2d(x + 1e-4, 30.0)
            self.assertLess(abs(a - b), 1e-3, "สนามกระโดดในระยะที่เล็กกว่าหนึ่งก้าวเดิน")


class TestTheWarpMakesVeinsNotBlobs(unittest.TestCase):
    """λW คือพจน์ที่ทำให้เส้นระดับเปลี่ยนจากหยดกลมเป็นเส้นใยยาว — ข้อนี้คือเหตุผลทั้งหมด
    ที่ใช้สูตรนี้แทน fBm ล้วน ถ้าวันหนึ่งมันหายไป "เส้นปราณของแผ่นดิน" จะกลายเป็น
    หยดปราณที่กระจายเป็นจุดๆ ซึ่งตามรอยไปไม่ได้และครองเป็นดินแดนไม่ได้
    """

    GRID, HALF = 100, 600.0

    def grid(self, lam):
        pl = NZ.Planet(seed=7, lam=lam, octaves=5, warp_octaves=2)
        out = []
        for i in range(self.GRID):
            x = -self.HALF + 2 * self.HALF * i / (self.GRID - 1)
            row = []
            for j in range(self.GRID):
                y = -self.HALF + 2 * self.HALF * j / (self.GRID - 1)
                row.append(pl.height(*NZ.sphere_dir(x, y, C.PLANET_SPAN),
                                     scale=C.PLANET_SCALE))
            out.append(row)
        return out

    @staticmethod
    def edge_length(g, thr):
        """จำนวนครั้งที่เส้นระดับตัดผ่านขอบระหว่างช่อง = ความยาวเส้นขอบของบริเวณ"""
        n, c = len(g), 0
        for i in range(n):
            for j in range(n - 1):
                if (g[i][j] > thr) != (g[i][j + 1] > thr):
                    c += 1
                if (g[j][i] > thr) != (g[j + 1][i] > thr):
                    c += 1
        return c

    def measure(self, lam):
        g = self.grid(lam)
        flat = [v for row in g for v in row]
        thr = st.median(flat)          # ตัดที่ค่ากลาง พื้นที่จึงเท่ากันทุก λ โดยสร้าง
        return self.edge_length(g, thr), st.pstdev(flat)

    def test_warping_stretches_the_regions_into_filaments(self):
        """พื้นที่เท่ากัน แต่เส้นขอบยาวขึ้น = บริเวณถูกยืดเป็นเส้น ไม่ใช่โตขึ้น

        วัดจริงที่ค่าที่ใช้อยู่ (scale 12 · 5 octaves · λ=1) บนตะแกรง 100x100 ช่วง ±600:
            λ=0 ได้เส้นขอบ 3,060 หน่วย · λ=1 ได้ 4,569 = **1.49 เท่า**
        ยืนยันที่ความละเอียดอื่นด้วย: (100,±600,3 oct) 1.52 เท่า · (120,±400,5 oct) 1.48 เท่า

        หมายเหตุที่ต้องบันทึกไว้: ตอนวัดครั้งแรกได้ 3.2 เท่า แต่นั่นวัดที่ scale=3 ซึ่งลายหยาบ
        กว่าระยะห่างของตะแกรงมาก พอมาใช้ scale=12 จริงแล้ววัดที่ตะแกรงหยาบเดิม ลายละเอียด
        ถูกนับไม่ครบ (aliasing) ตัวเลข 3.2 จึงเป็นของสเกลคนละค่า ไม่ใช่ของการตั้งค่าที่ใช้จริง
        """
        plain, _ = self.measure(0.0)
        warped, _ = self.measure(1.0)
        self.assertGreater(warped, plain * 1.3,
                           "บิดแล้วเส้นขอบต้องยาวขึ้นชัดเจนที่พื้นที่เท่ากัน")

    def test_more_warp_means_more_filaments(self):
        lens = [self.measure(lam)[0] for lam in (0.0, 0.5, 1.0)]
        self.assertEqual(lens, sorted(lens), "λ มากขึ้นต้องยืดมากขึ้นอย่างเป็นลำดับ")

    def test_it_changes_shape_not_loudness(self):
        """ส่วนเบี่ยงเบนมาตรฐานต้องแทบไม่ขยับ — ไม่งั้นมันแค่เพิ่มความแรงของ noise เฉยๆ"""
        _, sd0 = self.measure(0.0)
        _, sd1 = self.measure(1.0)
        self.assertLess(abs(sd1 - sd0) / max(1e-9, sd0), 0.25)

    def test_lambda_zero_is_exactly_plain_fbm(self):
        """λ=0 ต้องคืนเป็น fBm ปกติเป๊ะ — ปรับกลับได้ถ้าไม่ชอบ"""
        pl = NZ.Planet(seed=7, lam=0.0, octaves=5)
        d = NZ.sphere_dir(37.0, -21.0, C.PLANET_SPAN)
        direct = pl.fbm3(d[0] * C.PLANET_SCALE, d[1] * C.PLANET_SCALE,
                         d[2] * C.PLANET_SCALE, scale=1.0)
        self.assertAlmostEqual(pl.height(*d, scale=C.PLANET_SCALE), direct, places=12)

    def test_the_warp_does_not_all_point_the_same_way(self):
        """ถ้าสามช่องมาจากสนามเดียวกัน เวกเตอร์บิดจะชี้ไปทาง (1,1,1) เกือบตลอด
        ซึ่งไม่ใช่การบิด มันคือการเลื่อนทั้งดาวไปทางเดียว
        """
        pl = NZ.Planet(seed=7)
        dots = []
        for i in range(60):
            q = (i * 0.61, i * 0.37, i * 0.23)
            w = pl.warp(*q)
            n = math.sqrt(sum(c * c for c in w))
            if n > 1e-9:
                dots.append(sum(c for c in w) / (n * math.sqrt(3.0)))
        self.assertLess(abs(st.mean(dots)), 0.35,
                        "เวกเตอร์บิดเอนไปทางทแยงเหมือนกันหมด = สามช่องสัมพันธ์กัน")


class TestTheSignedDistanceWorks(unittest.TestCase):
    """D(p) = R + A·F(...) - ‖p‖  ·  บวก = ในเนื้อหิน · ลบ = ในอากาศ · ศูนย์ = บนผิว

    เก็บ SDF ไว้ (ไม่ใช่แค่แผนที่ความสูง) เพราะแผนที่ความสูงให้ค่าได้ค่าเดียวต่อพิกัด
    จึงแทน "เกาะสวรรค์ลอยฟ้า" กับ "แดนลับที่ถูกผนึกใต้ดิน" ไม่ได้เลย — ทั้งสองอย่างนี้
    มีอยู่ในโลกนี้แล้ว (terrain.BIOMES และ PLACES ที่ is_sealed)
    """

    def test_the_sign_says_inside_or_outside(self):
        pl = NZ.Planet(seed=7)
        d = NZ.sphere_dir(80.0, -40.0, C.PLANET_SPAN)
        r = pl.surface_radius(*d, scale=C.PLANET_SCALE)
        deep = pl.sdf(d[0] * r * 0.8, d[1] * r * 0.8, d[2] * r * 0.8, scale=C.PLANET_SCALE)
        on = pl.sdf(d[0] * r, d[1] * r, d[2] * r, scale=C.PLANET_SCALE)
        sky = pl.sdf(d[0] * r * 1.2, d[1] * r * 1.2, d[2] * r * 1.2, scale=C.PLANET_SCALE)
        self.assertGreater(deep, 0.0, "ใต้ผิวต้องเป็นบวก")
        self.assertAlmostEqual(on, 0.0, places=9)
        self.assertLess(sky, 0.0, "เหนือผิวต้องเป็นลบ")

    def test_the_magnitude_is_a_real_distance_along_the_ray(self):
        """ขยับเข้าออกตามรัศมีเท่าไร D ต้องเปลี่ยนเท่านั้นพอดี"""
        pl = NZ.Planet(seed=7)
        d = NZ.sphere_dir(-120.0, 200.0, C.PLANET_SPAN)
        r = pl.surface_radius(*d, scale=C.PLANET_SCALE)
        for step in (0.01, 0.05, 0.2):
            got = pl.sdf(d[0] * (r + step), d[1] * (r + step), d[2] * (r + step),
                         scale=C.PLANET_SCALE)
            self.assertAlmostEqual(got, -step, places=9)

    def test_the_surface_stays_within_the_amplitude(self):
        pl = NZ.Planet(seed=7, radius=1.0, amp=0.12)
        for i in range(-6, 7):
            for j in range(-6, 7):
                r = pl.surface_radius(*NZ.sphere_dir(i * 180.0, j * 180.0,
                                                     C.PLANET_SPAN),
                                      scale=C.PLANET_SCALE)
                self.assertGreaterEqual(r, 1.0 - 0.12 - 1e-9)
                self.assertLessEqual(r, 1.0 + 0.12 + 1e-9)


class TestTheWorldHasNoEdge(unittest.TestCase):
    def test_the_field_is_defined_everywhere_including_far_outside_the_map(self):
        """บนทรงกลมไม่มีขอบ — สนามต้องให้ค่าได้ทุกทิศ ไม่ต้องตัดหรือซ้ำ"""
        sim = quiet(S.Sim, seed=7)
        pl = sim.qi_field()
        for x, y in ((0, 0), (10 ** 5, 0), (0, -10 ** 5), (10 ** 6, 10 ** 6)):
            v = pl.height(*NZ.sphere_dir(float(x), float(y), C.PLANET_SPAN),
                          scale=C.PLANET_SCALE)
            self.assertGreaterEqual(v, -1.0)
            self.assertLessEqual(v, 1.0)


if __name__ == "__main__":
    unittest.main()
