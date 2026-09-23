# -*- coding: utf-8 -*-
"""สมการจากโลกจริงที่โลกนี้ยืมมาใช้ — และคุณสมบัติที่ทำให้มันดีกว่าเลขที่จูนมือ

    python -m unittest test_physics -v

สิ่งที่ไฟล์นี้ล็อกไว้ไม่ใช่ "ค่าที่ถูกต้อง" แต่เป็น **คุณสมบัติของรูปสมการ** ซึ่งเป็นเหตุผล
ทั้งหมดที่ยืมของจริงมาใช้แทนการตั้งเลขเอง
  · อยู่ในขอบเขตเองโดยไม่ต้อง clamp — ตัวบีบไม่มีวันกลายเป็นตัวตัดสินผล
  · ทิศทางถูกต้องเสมอ (มากขึ้นต้องดีขึ้น ไม่ใช่ดีขึ้นแล้วพลิกกลับ)
  · มีจุดเหมาะสมที่หาด้วยอนุพันธ์ได้ และจุดนั้นเปลี่ยนตามสถานการณ์ของแต่ละคนเอง
  · ไม่ดึง rng เลย — โลกยังคงที่
"""
import contextlib
import io
import math
import unittest

from tiandao import config as C
from tiandao import physics as P
from tiandao import rules as R
from tiandao import sim as S


def quiet(fn, *a, **kw):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*a, **kw)


class TestBarrierCrossing(unittest.TestCase):
    """โอกาสข้ามขั้น — เดิมเป็นเส้นตรงที่ถูกบีบที่ 0.95 แปลว่าตัวบีบคือสิ่งที่ตัดสินผลจริง"""

    def test_it_never_needs_a_clamp(self):
        for gap in (-50.0, -1.0, 0.0, 1.0, 50.0, 1e6):
            for shift in (-100.0, 0.0, 100.0):
                p = P.barrier_odds(gap, [shift])
                self.assertGreater(p, 0.0)
                self.assertLess(p, 1.0)

    def test_more_surplus_always_helps_and_never_flips(self):
        last = -1.0
        for gap in [x / 10.0 for x in range(-20, 51)]:
            p = P.barrier_odds(gap, [])
            self.assertGreater(p, last, "โอกาสต้องเพิ่มขึ้นเสมอเมื่อสะสมได้มากขึ้น")
            last = p

    def test_exactly_at_the_wall_gives_the_configured_base(self):
        self.assertAlmostEqual(P.barrier_odds(0.0, [], base_p=0.55), 0.55, places=9)

    def test_surplus_is_measured_against_the_wall_not_in_raw_units(self):
        """กำแพงขั้นที่ 25 สูงกว่าขั้นที่ 2 หลายเท่า ส่วนเกิน 1 หน่วยจึงมีความหมายคนละเรื่อง"""
        low_req, high_req = 10.0, 400.0
        surplus = 5.0
        p_low = P.barrier_odds(surplus / low_req, [])
        p_high = P.barrier_odds(surplus / high_req, [])
        self.assertGreater(p_low, p_high,
                           "ส่วนเกินเท่ากันต้องช่วยคนขั้นต่ำมากกว่าคนขั้นสูง")

    def test_the_engine_uses_it_and_the_old_clamps_are_gone(self):
        sim = quiet(S.Sim, seed=5)
        quiet(sim.run, 6000)
        ch = max(sim.living(), key=lambda c: c.rank())
        w = sim.world(ch.world_id)
        p = R.break_odds(sim, ch, w)
        self.assertGreater(p, 0.0)
        self.assertLess(p, 1.0)
        ch.insight += R.need(ch, w) * 20
        self.assertLess(R.break_odds(sim, ch, w), 1.0,
                        "สะสมมหาศาลก็ยังไม่ถึง 1 — และไม่ต้องมี min(0.95) ไปกั้น")


class TestWhenToActIsADerivative(unittest.TestCase):
    """เงื่อนไขจุดเหมาะสม k·(1-p)·(L-t) = 1 — 'วันที่เสียไป ต้องซื้อโอกาสกลับมาให้คุ้ม'"""

    def test_a_young_man_waits_and_an_old_man_moves_now(self):
        young = P.best_wait_days(p_now=0.55, z_rate=0.002, life_left=200 * 365.0)
        old = P.best_wait_days(p_now=0.55, z_rate=0.002, life_left=3 * 365.0)
        self.assertGreater(young, old,
                           "คนที่มีชีวิตเหลือมากกว่า ควรรอสะสมนานกว่า — ออกมาเองจากสมการ")
        self.assertEqual(old, 0.0, "เหลืออายุไม่กี่ปี ต้องลงมือเดี๋ยวนี้แม้โอกาสยังไม่ดี")

    def test_slow_progress_means_waiting_buys_nothing(self):
        fast = P.best_wait_days(0.55, 0.002, 200 * 365.0)
        slow = P.best_wait_days(0.55, 1e-7, 200 * 365.0)
        self.assertGreater(fast, slow)
        self.assertEqual(slow, 0.0)

    def test_decay_winning_over_progress_forces_the_attempt(self):
        self.assertEqual(P.best_wait_days(0.55, -0.001, 100 * 365.0), 0.0,
                         "ความเสื่อมชนะการสะสม = รอไปมีแต่แย่ลง")

    def test_already_good_odds_mean_there_is_little_left_to_buy(self):
        self.assertLess(P.best_wait_days(0.98, 0.002, 200 * 365.0),
                        P.best_wait_days(0.55, 0.002, 200 * 365.0))

    def test_the_answer_really_satisfies_the_derivative_condition(self):
        """ตรวจกับสมการตรงๆ ไม่ใช่เชื่อผลลัพธ์ลอยๆ"""
        p0, k, L = 0.55, 0.002, 200 * 365.0
        t = P.best_wait_days(p0, k, L, horizon=L)
        p_at = P.logistic(P.logit(p0) + k * t)
        self.assertAlmostEqual(k * (1.0 - p_at) * (L - t), 1.0, places=3)

    def test_the_world_uses_it_and_people_differ(self):
        sim = quiet(S.Sim, seed=5)
        quiet(sim.run, 12000)
        waits = []
        for ch in sim.living()[:400]:
            w = sim.world(ch.world_id)
            waits.append(R.break_timing(sim, ch, w)["wait_days"])
        self.assertGreater(len(set(round(x) for x in waits)), 3,
                           "แต่ละคนต้องได้จังหวะของตัวเอง ไม่ใช่เลขเดียวกันทั้งโลก")


class TestLogisticRecovery(unittest.TestCase):
    def test_it_never_passes_the_ceiling_without_a_min(self):
        for days in (1, 365, 36500, 10 ** 7):
            self.assertLessEqual(P.logistic_growth(900.0, 1000.0, 0.001, days), 1000.0 + 1e-9)

    def test_a_drained_world_recovers_slowly_and_a_half_full_one_fast(self):
        drained = P.logistic_growth(10.0, 1000.0, 0.001, 365) - 10.0
        middling = P.logistic_growth(500.0, 1000.0, 0.001, 365) - 500.0
        self.assertLess(drained, middling,
                        "ยุคเสื่อมต้องยาว ไม่ใช่หายไปเองเพราะการเติมคงที่")

    def test_it_matches_the_closed_form_of_the_equation(self):
        K, H0, r, t = 1000.0, 100.0, 0.001, 500.0
        want = K * H0 * math.exp(r * t) / (K + H0 * (math.exp(r * t) - 1.0))
        self.assertAlmostEqual(P.logistic_growth(H0, K, r, t), want, places=6)


class TestLanchester(unittest.TestCase):
    def test_a_narrow_win_is_a_bloodbath_and_a_rout_is_cheap(self):
        _s, narrow = P.lanchester(100, 99)
        _s, rout = P.lanchester(100, 1)
        self.assertLess(narrow, 0.2, "ชนะฉิวเฉียดต้องแทบไม่เหลือสำนัก")
        self.assertGreater(rout, 0.99, "ชนะขาดต้องแทบไม่เสียใคร")

    def test_the_bigger_side_wins(self):
        self.assertEqual(P.lanchester(100, 40)[0], 1)
        self.assertEqual(P.lanchester(40, 100)[0], -1)

    def test_it_obeys_the_square_law(self):
        a, b = 130.0, 50.0
        _s, frac = P.lanchester(a, b)
        self.assertAlmostEqual(frac * a, math.sqrt(a * a - b * b), places=6)


class TestEntropyTribulation(unittest.TestCase):
    """ทัณฑ์สวรรค์ = ฟ้าดินทวงหนี้เอนโทรปี ไม่ใช่รายการขั้นที่ตั้งเอาเอง"""

    def test_a_mortal_owes_nothing(self):
        self.assertEqual(P.entropy_karma(80.0, 80.0, 10.0), 0.0)
        self.assertEqual(P.strike_chance(0.0, 9, 0.004), 0.0)

    def test_the_debt_is_about_the_ratio_not_the_difference(self):
        """ยืดอายุจาก 80 เป็น 800 ติดหนี้เท่ากับยืดจาก 800 เป็น 8000"""
        a = P.entropy_karma(800.0, 80.0, 10.0)
        b = P.entropy_karma(8000.0, 800.0, 10.0)
        self.assertAlmostEqual(a, b, places=9)

    def test_the_chance_rises_to_certainty_without_a_clamp(self):
        last = -1.0
        for karma in range(0, 400, 10):
            p = P.strike_chance(karma, 9, 0.004)
            self.assertGreaterEqual(p, last)
            self.assertLess(p, 1.0)
            last = p
        self.assertGreater(P.strike_chance(10000, 29, 0.004), 0.999)

    def test_the_engine_charges_the_long_lived_more(self):
        sim = quiet(S.Sim, seed=5)
        quiet(sim.run, 6000)
        ch = max(sim.living(), key=lambda c: c.rank())
        karma = P.entropy_karma(ch.lifespan(), ch.natural_lifespan, C.ENTROPY_K)
        self.assertGreaterEqual(karma, 0.0)
        if ch.rank() > 0:
            self.assertGreater(karma, 0.0, "คนที่ไต่ขั้นมาแล้วต้องติดหนี้ฟ้า")


class TestTimeDilatedAbode(unittest.TestCase):
    """ปราณยิ่งหนาแน่น เวลาที่ได้ใช้ยิ่งมากกว่าเวลาโลกภายนอก"""

    def test_dense_qi_gives_more_time_not_less(self):
        thin = P.time_dilation(100.0, 1400.0)
        dense = P.time_dilation(1300.0, 1400.0)
        self.assertGreater(dense, thin)
        self.assertGreaterEqual(thin, 1.0,
                                "ถ้ำต้องไม่เคยแย่กว่าการนั่งบำเพ็ญกลางทุ่ง")

    def test_it_is_capped_before_the_dimension_collapses(self):
        self.assertLessEqual(P.time_dilation(1399.999, 1400.0, cap=6.0), 6.0)
        self.assertLessEqual(P.time_dilation(10 ** 9, 1400.0, cap=6.0), 6.0)

    def test_places_really_differ_in_the_live_world(self):
        sim = quiet(S.Sim, seed=5)
        quiet(sim.run, 4000)
        w = sim.worlds[0]
        vals = {round(P.time_dilation(sim.qi_density(i, w), C.QI_CRITICAL,
                                      C.QI_DILATION_CAP), 3)
                for i in range(0, 200)}
        self.assertGreater(len(vals), 2,
                           "ถ้าทุกที่ให้ค่าเท่ากัน สถานที่ก็ยังไม่มีความหมายอยู่ดี")


class TestWaveInterference(unittest.TestCase):
    """รวมคลื่นใช้ตอนประสานวิชา · หักล้างใช้ตอนปะทะ — คนละสูตรกัน"""

    def test_combining_two_allies_in_phase_beats_the_sum_of_parts(self):
        self.assertAlmostEqual(P.wave_sum(100, 100, 0), 200.0, places=6)
        self.assertAlmostEqual(P.wave_sum(100, 100, 180), 0.0, places=6)

    def test_a_shield_of_the_same_element_does_not_add_to_the_attack(self):
        """ถ้าใช้สูตรรวมคลื่นกับการปะทะ ธาตุเดียวกันจะทำให้โล่ของฝ่ายรับ 'บวกเข้า' กับพลังโจมตี
        แปลว่าใช้ธาตุเดียวกับคู่ต่อสู้แล้วเจ็บหนักขึ้น ซึ่งกลับหัว"""
        wrong = P.wave_sum(100, 80, 15) - 80          # วิธีที่ผิด
        right = P.wave_cancel(100, 80, 15)
        self.assertGreater(wrong, 90, "วิธีผิดให้ดาเมจพุ่งเพราะโล่ไปเสริมพลังโจมตี")
        self.assertLessEqual(right, 100.0)

    def test_water_cancels_fire_and_fire_does_not_cancel_fire(self):
        self.assertAlmostEqual(P.wave_cancel(100, 80, 180), 20.0, places=6)
        self.assertAlmostEqual(P.wave_cancel(100, 80, 0), 100.0, places=6)
        self.assertAlmostEqual(P.wave_cancel(100, 80, 90), 100.0, places=6)


class TestNoneOfThisTouchesTheDice(unittest.TestCase):
    def test_the_physics_module_never_draws_from_rng(self):
        sim = quiet(S.Sim, seed=3)
        quiet(sim.run, 3000)
        before = sim.rng.getstate()
        ch = sim.living()[0]
        w = sim.world(ch.world_id)
        R.break_odds(sim, ch, w)
        R.break_timing(sim, ch, w)
        R.track_rates(ch, sim.day)
        P.logistic_growth(10, 100, 0.001, 365)
        P.lanchester(10, 5)
        P.time_dilation(500, 1400)
        self.assertEqual(before, sim.rng.getstate(),
                         "คณิตศาสตร์ต้องไม่ขยับลูกเต๋า ไม่งั้นโลกจะไม่คงที่")

    def test_the_world_is_still_reproducible(self):
        a = quiet(S.Sim, seed=11)
        quiet(a.run, 4000)
        b = quiet(S.Sim, seed=11)
        quiet(b.run, 4000)
        self.assertEqual([e.kind for e in a.log], [e.kind for e in b.log])
        self.assertEqual(a.day, b.day)


if __name__ == "__main__":
    unittest.main()


class TestEnergyIsConserved(unittest.TestCase):
    """กฎข้อแรก: พลังฟ้าดินต้องไม่หายจากระบบโดยไม่มีที่มาที่ไป

    บัญชีของโลกนี้มีสี่ช่อง
      คลังฟ้าของแต่ละแดน (world.heaven) · ที่ผู้บำเพ็ญถือไว้ (ch.drawn)
      ที่คืนมาตอนตาย (death_return) · ที่ถูกขนออกจากแดนตอนข้ามฟ้า (ถาวร)
    """

    def test_a_breakthrough_moves_energy_it_does_not_create_it(self):
        sim = quiet(S.Sim, seed=5)
        quiet(sim.run, 6000)
        ch = max(sim.living(), key=lambda c: c.rank())
        w = sim.world(ch.world_id)
        ch.insight += R.need(ch, w) * 5
        ch.decay, ch.hidden = 0.0, False
        before = w.heaven + ch.drawn

        class _Sure:
            def random(self):
                return 0.0

            def randint(self, a, b):
                return a

            def uniform(self, a, b):
                return a

            def choice(self, seq):
                return list(seq)[0]

        R.attempt_break(sim, ch, w, _Sure())
        after = w.heaven + ch.drawn
        self.assertAlmostEqual(before, after, places=6,
                               msg="พลังที่ถอนจากคลังฟ้าต้องไปอยู่ในตัวเขาพอดี ไม่มากไม่น้อย")

    def test_dying_gives_part_of_it_back(self):
        sim = quiet(S.Sim, seed=5)
        quiet(sim.run, 6000)
        ch = max(sim.living(), key=lambda c: c.drawn)
        w = sim.world(ch.world_id)
        if ch.drawn <= 0:
            self.skipTest("ยังไม่มีใครถอนพลังจากคลังฟ้าในรันสั้นนี้")
        held, before = ch.drawn, w.heaven
        R.death_return(w, ch, natural=True)
        self.assertEqual(ch.drawn, 0.0, "ตายแล้วต้องไม่ถือพลังค้างไว้")
        self.assertGreater(w.heaven, before, "และคลังฟ้าต้องได้คืนจริง")
        self.assertLessEqual(w.heaven - before, held + 1e-6,
                             "คืนได้ไม่เกินที่เคยถอนไป — ห้ามสร้างพลังจากอากาศ")

    def test_the_pool_never_exceeds_the_ceiling_over_a_long_run(self):
        sim = quiet(S.Sim, seed=9)
        quiet(sim.run, 20000)
        for w in sim.worlds:
            self.assertLessEqual(w.heaven, w.cap() + 1e-6, f"{w.name} ล้นเพดาน")
            self.assertGreaterEqual(w.heaven, -1e-9, f"{w.name} ติดลบ")

    def test_nobody_holds_more_than_the_universe_ever_had(self):
        sim = quiet(S.Sim, seed=9)
        quiet(sim.run, 20000)
        total_held = sum(c.drawn for c in sim.cast)
        total_cap = sum(w.cap() for w in sim.worlds)
        self.assertLess(total_held, total_cap,
                        "ที่คนถือรวมกันต้องไม่เกินความจุของทั้งจักรวาล")


class TestPracticeMakesDepth(unittest.TestCase):
    """กฎกำลังของการฝึกฝน — ฝึกของเดิมต้องได้อะไรเสมอ แต่ได้น้อยลงเรื่อยๆ"""

    def test_it_climbs_forever_but_never_reaches_one(self):
        last = -1.0
        for n in (0, 1, 5, 50, 5000, 10 ** 8):
            m = P.practice_mastery(n, 0.5)
            self.assertGreater(m, last)
            self.assertLess(m, 1.0, "ไม่มีใครชำนาญถึงที่สุด")
            last = m
        self.assertEqual(P.practice_mastery(0, 0.5), 0.0)

    def test_early_reps_are_worth_far_more_than_late_ones(self):
        first = P.practice_gain(0, 0.5)
        hundredth = P.practice_gain(100, 0.5)
        self.assertGreater(first, hundredth * 100,
                           "ครั้งแรกต้องคุ้มกว่าครั้งที่ร้อยอย่างมาก")
        self.assertGreater(hundredth, 0.0, "แต่ครั้งที่ร้อยก็ยังไม่เป็นศูนย์")

    def test_one_deep_technique_can_beat_several_shallow_ones(self):
        """一招鲜吃遍天 — แก่นของแนวนี้ ที่ระบบเดิมทำไม่ได้เพราะวิชาเป็น binary"""
        deep = C.SKILL_BASE_SHARE + C.SKILL_MASTERY_SHARE * P.practice_mastery(
            200, C.PRACTICE_EXPONENT)
        shallow = C.SKILL_BASE_SHARE + C.SKILL_MASTERY_SHARE * P.practice_mastery(
            1, C.PRACTICE_EXPONENT)
        self.assertGreater(deep, shallow * 1.5)

    def test_the_world_really_deepens_techniques(self):
        sim = quiet(S.Sim, seed=7)
        quiet(sim.run, 30000)
        deepest = max((max((c.mastery or {}).values(), default=0) for c in sim.living()),
                      default=0)
        self.assertGreater(deepest, 1, "ต้องมีคนฝึกวิชาเดิมซ้ำจริง ไม่ใช่เก็บชื่อวิชาอย่างเดียว")
        kinds = {e.outcome for e in sim.log if e.kind == "ฝึกวิชา"}
        self.assertIn("ลึกขึ้น", kinds)


class TestSurprisalRanksTheStory(unittest.TestCase):
    def test_the_expected_is_worth_almost_nothing(self):
        self.assertLess(P.surprisal(0.99), 0.05)
        self.assertAlmostEqual(P.surprisal(0.5), 1.0, places=9)
        self.assertGreater(P.surprisal(0.001), 9.0)

    def test_rarer_always_means_more_surprising(self):
        last = -1.0
        for p in (0.99, 0.8, 0.5, 0.2, 0.05, 0.01, 0.0001):
            v = P.surprisal(p)
            self.assertGreater(v, last)
            last = v

    def test_every_event_in_the_world_carries_it(self):
        sim = quiet(S.Sim, seed=7)
        quiet(sim.run, 12000)
        self.assertTrue(all(isinstance(e.surprise, (int, float)) for e in sim.log))
        self.assertGreater(max(e.surprise for e in sim.log), 4.0,
                           "ต้องมีเหตุการณ์ที่แทบไม่น่าเกิดบ้างในหมื่นเหตุการณ์")

    def test_a_rare_death_outranks_an_ordinary_day(self):
        sim = quiet(S.Sim, seed=7)
        quiet(sim.run, 12000)
        deaths = [e.surprise for e in sim.log if e.outcome == "ตาย"]
        plain = [e.surprise for e in sim.log if e.outcome == "ค้าขาย"]
        if not deaths or not plain:
            self.skipTest("รันสั้นเกินไป")
        self.assertGreater(max(deaths), max(plain))


class TestFeudsCluster(unittest.TestCase):
    def test_a_killing_raises_the_local_rate_then_it_cools(self):
        now = 10000.0
        fresh = P.hawkes_intensity(0.0, [now - 10], now, 0.3, 2200.0)
        stale = P.hawkes_intensity(0.0, [now - 30000], now, 0.3, 2200.0)
        self.assertGreater(fresh, stale * 50, "แค้นเก่าสามสิบปีต้องเย็นลงไปมากแล้ว")
        self.assertGreater(fresh, 0.0)

    def test_many_killings_stack_up(self):
        now = 1000.0
        one = P.hawkes_intensity(0.0, [now], now, 0.3, 2200.0)
        five = P.hawkes_intensity(0.0, [now] * 5, now, 0.3, 2200.0)
        self.assertAlmostEqual(five, one * 5, places=9)

    def test_the_heat_is_local_not_global(self):
        """ฆ่ากันที่หุบเขาหนึ่ง ไม่ได้ทำให้อีกฟากของแดนลุกเป็นไฟด้วย"""
        sim = quiet(S.Sim, seed=7)
        quiet(sim.run, 30000)
        heats = [sim.feud_heat(p) for p in range(0, 300)]
        cold = sum(1 for h in heats if h < 0.01)
        self.assertGreater(cold, 10, "ต้องมีแถบที่สงบอยู่ด้วย ไม่ใช่ร้อนทั้งโลก")
        self.assertGreater(max(heats), 0.2, "และต้องมีแถบที่เดือดจริง")


class TestAuctionsFindAPrice(unittest.TestCase):
    def test_the_winner_pays_the_second_price(self):
        idx, pay = P.second_price([100.0, 70.0, 30.0])
        self.assertEqual(idx, 0)
        self.assertEqual(pay, 70.0)

    def test_a_lone_bidder_pays_his_own_bid(self):
        self.assertEqual(P.second_price([42.0]), (0, 42.0))
        self.assertEqual(P.second_price([]), (-1, 0.0))

    def test_values_are_heavy_tailed_not_flat(self):
        vals = [P.lognormal_value(100.0, 1.1, (i + 0.5) / 400.0) for i in range(400)]
        vals.sort()
        median = vals[200]
        top = vals[-4]           # ราว 1% บนสุด
        self.assertGreater(top, median * 8,
                           "ของ 1% บนสุดต้องแพงกว่าของกลางหลายเท่า ไม่ใช่แบนราบ")
        self.assertLess(vals[0], median, "และต้องมีของถูกอยู่ด้วย")

    def test_the_world_runs_real_auctions(self):
        sim = quiet(S.Sim, seed=7)
        quiet(sim.run, 30000)
        rows = [e for e in sim.log
                if e.kind == "เปิดประมูล" and e.deltas.get("ผู้เข้าประมูล")]
        if not rows:
            self.skipTest("ยังไม่มีงานประมูลในรันนี้")
        counts = {int(e.deltas["ผู้เข้าประมูล"]) for e in rows}
        self.assertGreater(max(counts), 2, "งานประมูลต้องมีมากกว่าสองคนสู้ราคาบ้าง")
        # ราคาคิดเป็นหน่วยปราณแล้ว (หินวิญญาณ) ไม่ใช่เหรียญทอง จึงเป็นทศนิยมพร้อมหน่วย
        prices = sorted(float(e.deltas["ราคาตั้งต้น"].split()[0]) for e in rows)
        self.assertGreater(prices[-1], prices[len(prices) // 2] * 4,
                           "ต้องมีล็อตที่แพงกว่าของกลางหลายเท่า")


class TestPricesFollowScarcity(unittest.TestCase):
    def test_scarce_is_dear_and_plentiful_is_cheap(self):
        dear = P.scarcity_price(100, 10, 1, 0.7)
        cheap = P.scarcity_price(100, 1, 10, 0.7)
        self.assertGreater(dear, 100)
        self.assertLess(cheap, 100)
        self.assertAlmostEqual(P.scarcity_price(100, 5, 5, 0.7), 100.0, places=6)

    def test_the_same_ratio_moves_the_price_the_same_way(self):
        """ของที่เหลือครึ่งเดียวควรแพงขึ้นเท่ากัน ไม่ว่าจะเริ่มจาก 100 หรือ 10,000 ชิ้น"""
        a = P.scarcity_price(100, 100, 50, 0.7) / 100
        b = P.scarcity_price(100, 10000, 5000, 0.7) / 100
        self.assertAlmostEqual(a, b, places=9)

    def test_it_is_bounded_so_the_market_never_explodes(self):
        self.assertLessEqual(P.scarcity_price(100, 10 ** 9, 1, 0.7, hi=8.0), 800.0)
        self.assertGreaterEqual(P.scarcity_price(100, 1, 10 ** 9, 0.7, lo=0.25), 25.0)

    def test_the_world_prices_things_differently_across_places(self):
        sim = quiet(S.Sim, seed=7)
        quiet(sim.run, 20000)
        from tiandao import materials as MAT
        name = "หญ้าปราณเขียว"
        base = MAT.price_of(name) or 100.0
        seen = {round(sim.price_now(w, name, base), 3) for w in sim.worlds[:4]}
        self.assertGreater(len(seen), 1, "ราคาต้องไม่เท่ากันทุกแดน")


class TestTheRankingBoard(unittest.TestCase):
    def test_beating_a_stronger_man_is_worth_more(self):
        _a1, _b1 = P.elo_update(1500, 1500, True, k=32)
        _a2, _b2 = P.elo_update(1500, 1900, True, k=32)
        self.assertGreater(_a2 - 1500, _a1 - 1500,
                           "ม้ามืดโค่นเซียนต้องได้แต้มมากกว่าชนะคนเสมอกัน")

    def test_bullying_the_weak_earns_almost_nothing(self):
        gain, _ = P.elo_update(1900, 1200, True, k=32)
        self.assertLess(gain - 1900, 2.0)

    def test_points_are_conserved(self):
        a, b = P.elo_update(1500, 1700, True, k=32)
        self.assertAlmostEqual(a + b, 1500 + 1700, places=9)

    def test_the_rating_predicts_the_fight(self):
        self.assertAlmostEqual(P.elo_expected(1500, 1500), 0.5, places=9)
        self.assertGreater(P.elo_expected(1900, 1500), 0.9)
        self.assertLess(P.elo_expected(1100, 1500), 0.1)

    def test_the_world_ends_up_with_a_real_board(self):
        sim = quiet(S.Sim, seed=7)
        quiet(sim.run, 30000)
        elos = sorted((c.elo for c in sim.living()), reverse=True)
        self.assertGreater(elos[0] - elos[-1], 150,
                           "กระดานต้องแยกคนเก่งออกจากคนอ่อนได้จริง")
        self.assertGreater(sum(1 for e in elos if e >= C.ELO_FAME_BAR), 0,
                           "ต้องมีคนที่ไต่ขึ้นมามีชื่อได้บ้าง")


class TestNewsTravels(unittest.TestCase):
    def test_distance_costs_reach(self):
        near = P.spread_reach(1, 0.72)
        far = P.spread_reach(6, 0.72)
        self.assertGreater(near, far * 5)
        self.assertEqual(P.spread_reach(0, 0.72), 1.0, "ที่เดียวกันย่อมรู้แน่นอน")

    def test_it_is_multiplicative_per_step(self):
        self.assertAlmostEqual(P.spread_reach(3, 0.5), 0.125, places=9)

    def test_the_world_computes_hops_on_the_graph(self):
        sim = quiet(S.Sim, seed=7)
        quiet(sim.run, 4000)
        self.assertEqual(sim.hops_between(5, 5), 0)
        hops = {sim.hops_between(0, p) for p in range(1, 60)}
        self.assertGreater(len(hops), 2,
                           "ระยะบนกราฟต้องมีหลายระดับ ไม่ใช่ใกล้เท่ากันหมด")
        self.assertLessEqual(max(hops), C.RUMOR_MAX_HOPS)
