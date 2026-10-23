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







class TestTheHybridKeepsCharactersVaried(unittest.TestCase):
    """บทเรียนที่แพงที่สุดของฟีเจอร์นี้ — ล็อกไว้ไม่ให้กลับไปเป็นเหมือนเดิม

    ปล่อยให้ความจำตอบได้ไม่จำกัด: ตอบไป 2,573 จาก 2,774 การตัดสินใจ (93%) ประหยัด
    การเรียกโมเดลได้เยอะมาก แต่ **เอนโทรปีของการกระทำต่อคนร่วงจาก 2.95 เหลือ 1.58 บิต**
    ตัวละครวนทำสิ่งเดิม เพราะความจำที่ถูกย้ำจะยิ่งมั่นใจขึ้นเรื่อยๆ เป็นป้อนกลับบวก
    ความมั่นใจสูงจึงไม่ใช่เกณฑ์ที่พอ ต้องมีเพดานตัดวงจรโดยตรง
    """








if __name__ == "__main__":
    unittest.main()
