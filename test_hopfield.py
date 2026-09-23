# -*- coding: utf-8 -*-
"""ความจำเชิงเชื่อมโยง — E(x) = -1/β·log Σ exp(β·ξᵀx) + ½‖x‖²

    python -m unittest test_hopfield -v

สมการนี้คือพลังงานของ modern Hopfield network และการไล่ลงตามความชันของมันหนึ่งก้าว
ให้ x' = Ξ·softmax(βΞᵀx) ซึ่งคือ attention ของ transformer เป๊ะๆ
(Ramsauer et al. 2020 "Hopfield Networks is All You Need")

**มันไม่ได้มาแทนโมเดลภาษา มันคือแกนกลางหนึ่งชั้นของโมเดลภาษา** ที่ถอดออกมาโดยไม่มี
น้ำหนักที่เรียนมา เอาไปเขียนเรื่องเล่าไม่ได้ สิ่งที่ทำได้คือตอบว่า "ครั้งก่อนที่เจอเรื่อง
คล้ายกันนี้ ข้าทำอะไร"

ตัวเลขที่วัดได้จริงและเป็นเหตุผลของค่าตั้งทุกค่าในไฟล์นี้
  · ทายตรงกับที่ LLM เลือกจริง 41% จาก 24 ตัวเลือก (เดาอันที่พบบ่อยสุด 17% · สุ่ม 6%)
  · **เพดานที่แท้จริงคือ 68.6%** ไม่ใช่ 100% — LLM เองที่ temperature 0.8 เลือกซ้ำของ
    ตัวเองในสถานการณ์เดียวกันเป๊ะได้แค่เท่านั้น (110 กลุ่ม · มัธยฐาน 60%)
  · ปล่อยให้ความจำตอบได้ไม่จำกัด -> ตอบไป 93% และ **เอนโทรปีของการกระทำต่อคนร่วง
    จาก 2.95 เหลือ 1.58 บิต** ตัวละครวนซ้ำ · ใส่เพดานแล้วเอนโทรปีกลับมา 2.96
    และยังประหยัดการเรียกโมเดลได้ 17%
"""
import contextlib
import io
import math
import statistics as st
import unittest

from tiandao import config as C
from tiandao import hopfield as HF
from tiandao import sim as S
from tiandao.mind import config as MC
from tiandao.mind import situation as SIT


def quiet(fn, *a, **kw):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*a, **kw)


class TestTheEnergyIsTheFormula(unittest.TestCase):
    def test_it_matches_the_written_formula_term_by_term(self):
        """คิดมือเทียบตรงๆ ที่ σ=1 (scaled=False) ไม่ให้โค้ดกับสูตรแยกทางกันเงียบๆ"""
        m = HF.Memory(beta=5.0)
        xs = [[1.0, 0.0], [0.0, 1.0], [0.6, 0.8]]
        for i, v in enumerate(xs):
            m.store(v, f"a{i}")
        q = HF.normalize([0.8, 0.6])
        b = 5.0
        sims = [HF.dot(k, q) for k in m.keys]
        want = -(1.0 / b) * math.log(sum(math.exp(b * s) for s in sims)) + 0.5 * HF.dot(q, q)
        self.assertAlmostEqual(m.energy(q, scaled=False), want, places=10)

    def test_a_stored_memory_is_a_fixed_point(self):
        """x' = Ξ·softmax(βΞᵀx) ต้องคืนความจำนั้นเองเมื่อถามด้วยความจำนั้น"""
        m = HF.Memory(beta=40.0)
        m.store([1, 0, 0, 0], "ก")
        m.store([0, 1, 0, 0], "ข")
        got = m.retrieve_state([1, 0, 0, 0])
        self.assertAlmostEqual(got[0], 1.0, places=6)
        self.assertLess(abs(got[1]), 1e-6)

    def test_energy_is_lower_for_something_remembered(self):
        m = HF.Memory(beta=9.0)
        m.store([1, 0, 0], "ก")
        m.store([0.9, 0.1, 0], "ก")
        known = m.energy([1, 0, 0])
        strange = m.energy([0, 0, 1])
        self.assertLess(known, strange,
                        "พลังงานต้องต่ำกว่าเมื่อเคยเจอเรื่องแบบนี้ — นี่คือสวิตช์ว่าเชื่อได้ไหม")

    def test_an_empty_memory_reports_no_idea_instead_of_crashing(self):
        m = HF.Memory()
        self.assertEqual(m.energy([1, 0]), C.HOPFIELD_EMPTY_ENERGY)
        self.assertIsNone(m.recall([1, 0]).kind)

    def test_it_never_overflows_at_high_beta(self):
        """exp(β·s) ล้นได้ง่าย — หักค่าสูงสุดออกก่อนให้ผลเท่ากันทางพีชคณิต ไม่ใช่ประมาณ"""
        m = HF.Memory(beta=700.0)
        for i in range(8):
            m.store([1.0, i * 0.1, 0.0], f"a{i%3}")
        e = m.energy([1.0, 0.0, 0.0])
        self.assertTrue(math.isfinite(e))
        self.assertTrue(math.isfinite(m.recall([1.0, 0.0, 0.0]).confidence))


class TestBetaIsPersonality(unittest.TestCase):
    def a_bank(self):
        m = HF.Memory(beta=9.0)
        m.store([1.0, 0.0, 0.0], "ล้างแค้น")
        m.store([0.9, 0.3, 0.0], "ฝึกวิชา")
        m.store([0.8, 0.5, 0.0], "บำเพ็ญ")
        m.store([0.7, 0.6, 0.1], "เดินทาง")
        return m

    def test_high_beta_is_decisive_low_beta_is_torn(self):
        m = self.a_bank()
        q = [0.95, 0.15, 0.0]
        self.assertGreater(m.recall(q, beta=C.HOPFIELD_BETA_MAX).confidence,
                           m.recall(q, beta=C.HOPFIELD_BETA_MIN).confidence,
                           "β สูงต้องเด็ดขาดกว่า β ต่ำ ไม่งั้นนิสัยไม่มีผลอะไรเลย")

    def test_an_inner_demon_makes_the_mind_waver(self):
        sim = quiet(S.Sim, seed=3)
        ch = next(c for c in sim.cast if c.alive)
        ch.traits = []
        ch.inner = 0.0
        calm = SIT.beta_of(ch)
        ch.inner = 12.0
        dark = SIT.beta_of(ch)
        self.assertLess(dark, calm, "จิตมารหนักแล้วใจต้องไม่มั่นเท่าเดิม")

    def test_beta_stays_in_its_band(self):
        sim = quiet(S.Sim, seed=3)
        for ch in sim.cast[:60]:
            b = SIT.beta_of(ch)
            self.assertGreaterEqual(b, C.HOPFIELD_BETA_MIN)
            self.assertLessEqual(b, C.HOPFIELD_BETA_MAX)


class TestBetaIsScaledByTheSpread(unittest.TestCase):
    """เวกเตอร์สถานการณ์เป็นบวกทุกช่อง โคไซน์จึงกระจุกในช่วงแคบสูง (วัดจริง 0.577-0.893)
    ถ้าไม่หารด้วย σ ค่า β ที่ตั้งไว้จะแทบไม่มีผล — วัดจริง: ความมั่นใจ 167 จาก 193 ครั้ง
    อยู่ใต้ 0.2 และดึงคืนได้ 3 จาก 344 หลักเดียวกับที่ attention หารด้วย √d_k
    """

    def narrow_bank(self):
        m = HF.Memory(beta=C.HOPFIELD_BETA)
        for i, lab in enumerate(("ก", "ข", "ค", "ง", "จ")):
            m.store([1.0, 0.05 * i, 0.02 * i], lab)
        return m

    def test_scaling_makes_a_narrow_spread_usable(self):
        m = self.narrow_bank()
        q = [1.0, 0.0, 0.0]
        self.assertGreater(m.recall(q, scaled=True).confidence,
                           m.recall(q, scaled=False).confidence,
                           "ไม่ปรับสเกลแล้วความมั่นใจจะจมอยู่ต่ำตลอด")

    def test_sigma_is_one_when_there_is_nothing_to_compare(self):
        m = HF.Memory()
        m.store([1, 0], "ก")
        self.assertEqual(m.sigma([0.5]), 1.0)

    def test_sigma_has_a_floor(self):
        self.assertGreaterEqual(HF.Memory.sigma([0.5, 0.5, 0.5]), C.HOPFIELD_SIGMA_FLOOR)


class TestMemoriesMergeInsteadOfDrowningEachOther(unittest.TestCase):
    def test_the_same_situation_and_choice_merges(self):
        m = HF.Memory()
        for _ in range(9):
            m.store([1.0, 0.0, 0.0], "ฝึกวิชา")
        self.assertEqual(len(m), 1)
        self.assertAlmostEqual(m.weights[0], 9.0)

    def test_the_same_situation_with_a_different_choice_stays_separate(self):
        m = HF.Memory()
        m.store([1.0, 0.0], "ฝึกวิชา")
        m.store([1.0, 0.0], "ล้างแค้น")
        self.assertEqual(len(m), 2)

    def test_what_gets_forgotten_is_rare_and_old_not_merely_old(self):
        """ความจำที่เก่าแต่ถูกย้ำหลายครั้งคือสิ่งที่คนจำได้ไปตลอดชีวิต"""
        m = HF.Memory(cap=3)
        m.store([1, 0, 0, 0], "เก่าแต่ย้ำบ่อย", day=0, weight=9.0)
        m.store([0, 1, 0, 0], "ใหม่แต่ครั้งเดียว", day=900)
        m.store([0, 0, 1, 0], "ใหม่อีกอัน", day=950)
        m.store([0, 0, 0, 1], "ใหม่สุด", day=1000)
        self.assertIn("เก่าแต่ย้ำบ่อย", m.labels)
        self.assertEqual(len(m), 3)

    def test_it_survives_a_save_and_load(self):
        import pickle
        m = HF.Memory(beta=11.0)
        m.store([1, 0], "ก", day=5)
        back = pickle.loads(pickle.dumps(m, pickle.HIGHEST_PROTOCOL))
        self.assertEqual(back.labels, ["ก"])
        self.assertEqual(back.beta, 11.0)


class TestRecallRespectsWhatIsPossible(unittest.TestCase):
    def test_it_only_offers_actions_on_the_menu(self):
        m = HF.Memory(beta=20.0)
        m.store([1, 0, 0], "ล้างแค้น")
        m.store([0.98, 0.1, 0], "ฝึกวิชา")
        got = m.recall([1, 0, 0], allowed=["ฝึกวิชา"])
        self.assertEqual(got.kind, "ฝึกวิชา")
        self.assertNotIn("ล้างแค้น", got.share)

    def test_filtering_happens_before_the_softmax(self):
        """คัดหลัง softmax จะทำให้ส่วนแบ่งถูกดูดไปโดยตัวเลือกที่เลือกไม่ได้
        แล้วความมั่นใจที่รายงานออกมาจะต่ำกว่าความจริง
        """
        m = HF.Memory(beta=20.0)
        m.store([1, 0, 0], "ทำไม่ได้")
        m.store([0.9, 0.2, 0], "ทำได้")
        got = m.recall([1, 0, 0], allowed=["ทำได้"])
        self.assertAlmostEqual(sum(got.share.values()), 1.0, places=9)
        self.assertEqual(got.confidence, 1.0)

    def test_nothing_on_the_menu_means_no_answer(self):
        m = HF.Memory()
        m.store([1, 0], "ก")
        self.assertIsNone(m.recall([1, 0], allowed=["ข"]).kind)


class TestTheSituationVector(unittest.TestCase):
    def a_world(self):
        sim = quiet(S.Sim, seed=7)
        quiet(sim.run, 4000)
        return sim

    def test_the_layout_never_shifts_silently(self):
        self.assertEqual(SIT.DIM, len(SIT.field_names()))
        sim = self.a_world()
        ch = next(c for c in sim.cast if c.alive and c.place is not None)
        self.assertEqual(len(SIT.encode(sim, ch, [])), SIT.DIM)

    def test_it_is_deterministic(self):
        sim = self.a_world()
        ch = next(c for c in sim.cast if c.alive and c.place is not None)
        self.assertEqual(SIT.encode(sim, ch, []), SIT.encode(sim, ch, []))

    def test_continuous_values_are_bucketed_into_levels(self):
        """ถ้าไม่แบ่งระดับ ทุกสถานการณ์จะไม่เหมือนกันเลยแม้แต่ครั้งเดียว
        (อารมณ์ 0.4821 vs 0.4823 ก็เป็นคนละเวกเตอร์) แล้ว "เคยเจอเรื่องแบบนี้"
        จะไม่มีความหมาย — วัดจริงตอนไม่แบ่ง: ดึงคืนได้ 3 จาก 344
        """
        for v in (0.4821, 0.4823, 0.49):
            self.assertEqual(SIT.q(v), SIT.q(0.4822))
        levels = {SIT.q(i / 200.0) for i in range(201)}
        self.assertLessEqual(len(levels), C.SITUATION_LEVELS + 1)

    def test_two_people_in_the_same_place_are_told_apart_by_their_hearts(self):
        """ถ้าน้ำหนักของใจต่ำเกินไป ทุกคนในที่เดียวกันจะกลายเป็นคนเดียวกัน"""
        sim = self.a_world()
        here = [c for c in sim.cast if c.alive and c.place is not None]
        a = here[0]
        b = next(c for c in here[1:] if c.place == a.place and c.realm == a.realm)
        va, vb = SIT.encode(sim, a, []), SIT.encode(sim, b, [])
        self.assertLess(HF.dot(HF.normalize(va), HF.normalize(vb)), 0.9999)

    def test_the_qi_pressure_actually_moves_the_vector(self):
        sim = self.a_world()
        ch = next(c for c in sim.cast if c.alive and c.place is not None)
        ch.realm = 1
        low = SIT.encode(sim, ch, [])
        ch.realm = 8
        high = SIT.encode(sim, ch, [])
        self.assertNotEqual(low, high)


class TestTheHybridKeepsCharactersVaried(unittest.TestCase):
    """บทเรียนที่แพงที่สุดของฟีเจอร์นี้ — ล็อกไว้ไม่ให้กลับไปเป็นเหมือนเดิม

    ปล่อยให้ความจำตอบได้ไม่จำกัด: ตอบไป 2,573 จาก 2,774 การตัดสินใจ (93%) ประหยัด
    การเรียกโมเดลได้เยอะมาก แต่ **เอนโทรปีของการกระทำต่อคนร่วงจาก 2.95 เหลือ 1.58 บิต**
    ตัวละครวนทำสิ่งเดิม เพราะความจำที่ถูกย้ำจะยิ่งมั่นใจขึ้นเรื่อยๆ เป็นป้อนกลับบวก
    ความมั่นใจสูงจึงไม่ใช่เกณฑ์ที่พอ ต้องมีเพดานตัดวงจรโดยตรง
    """

    def test_there_is_a_ceiling_on_answering_from_habit(self):
        self.assertGreater(MC.RECALL_MAX_STREAK, 0)
        self.assertLessEqual(MC.RECALL_MAX_STREAK, 8,
                             "เพดานหลวมเกินไปก็เท่ากับไม่มีเพดาน")

    def test_there_is_a_guard_against_repeating_the_same_action(self):
        self.assertGreater(MC.RECALL_REPEAT_WINDOW, MC.RECALL_REPEAT_MAX)

    def test_the_trust_bar_is_high_enough_to_have_been_measured(self):
        """0.6 วัดแล้วปล่อยให้ความจำกลืน 93% ของการตัดสินใจ"""
        self.assertGreaterEqual(MC.RECALL_TRUST_CONF, 0.75)
        self.assertGreater(MC.RECALL_TRUST_CONF, MC.RECALL_ROUTINE_CONF,
                           "วันที่ต้องคิดต้องเข้มกว่าวันธรรมดา เพราะทางเลือกอีกทางคือคิดจริง")

    def test_a_routine_day_may_use_a_weaker_memory_than_a_thinking_day(self):
        """วันธรรมดาทางเลือกอีกทางคือลูกเต๋า เกณฑ์จึงต่ำได้โดยไม่เสียอะไร"""
        self.assertLess(MC.RECALL_ROUTINE_CONF, MC.RECALL_TRUST_CONF)

    def test_a_violent_shock_always_reaches_the_model(self):
        from tiandao.mind import manager as MG

        class FakeMind:
            shaken = True
        self.assertTrue(MG.MindManager._turning_point(FakeMind(), None))

    def test_a_bottleneck_is_a_state_not_a_turning_point(self):
        """วัดจริง: รวม at_bottleneck() เข้าไปแล้ว 263 จาก 315 วันที่ต้องคิด (83%)
        กลายเป็นจุดพลิก เพราะหลังรื้อเศรษฐกิจปราณ ตัวละครค้างที่คอขวดเป็นสิบปี
        """
        from tiandao.mind import manager as MG
        sim = quiet(S.Sim, seed=5)
        quiet(sim.run, 3000)
        ch = next((c for c in sim.cast if c.alive and c.at_bottleneck()), None)
        if ch is None:
            self.skipTest("รันสั้นเกินกว่าจะมีคนติดคอขวด")

        class FakeMind:
            shaken = False
        self.assertFalse(MG.MindManager._turning_point(FakeMind(), ch))


if __name__ == "__main__":
    unittest.main()
