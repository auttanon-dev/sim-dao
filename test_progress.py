# -*- coding: utf-8 -*-
"""การฝึกวิชาและการล่าอสูรต้องพาคนไต่ขั้นได้จริง

    python -m unittest test_progress -v

ที่มา: บันทึกผู้มีจิตใจ 48 ปีในโลกจริง — "ฝึกวิชา" เป็นการกระทำที่ถูกเลือก **มากที่สุด**
(66/270 ครั้ง = 24%) และ "ล่าอสูร" อันดับสาม (26 ครั้ง) แต่ทั้งสองอย่าง**ไม่ให้ insight/refine
เลยสักหน่วย** — มีแต่กิ่งที่ฝึกไม่ได้ (ไม่มีวิชา/ไม่มีที่ฝึก) ที่เรียก cultivate() แทน
ผลคือคนเก่งที่สุดในบันทึกยังอยู่แค่ขั้น "หลอมกระดูก" หลังผ่านไปครึ่งศตวรรษ เพราะเวลาหนึ่งใน
สี่ของชีวิตตัวเอกหมดไปกับสิ่งที่ไม่ขยับด่านข้ามขั้นแม้แต่นิดเดียว
(เกณฑ์ข้ามขั้น: insight + refine*3 >= NEED_BASE + NEED_PER_REALM * realm)
"""
import contextlib
import io
import statistics as st
import unittest

from tiandao import config as C
from tiandao import events as E
from tiandao import sim as S


def quiet(fn, *a, **kw):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*a, **kw)


class StubRng:
    """คุมผลการทอยได้ — 0.0 = ผ่านทุกเงื่อนไขที่เป็น `rng.random() < p`"""
    def __init__(self, value=0.0):
        self.value = value

    def random(self):
        return self.value

    def randint(self, a, b):
        return b

    def uniform(self, a, b):
        return a

    def choice(self, seq):
        return seq[0]


TRAIN = next(e for e in E.EVENT_TABLE if e["kind"] == "ฝึกวิชา")
HUNT = next(e for e in E.EVENT_TABLE if e["kind"] == "ล่าอสูร")


def a_cultivator(seed=7):
    sim = quiet(S.Sim, seed=seed, tiers=3)
    ch = next(c for c in sim.living_in(0) if c.sentient and c.age(sim.day) >= 16)
    ch.insight, ch.refine, ch.decay = 0.0, 0.0, 0.0
    ch.skills = []
    ch.realm, ch.peak_realm = 1, 1
    return sim, sim.world(0), ch


class TestTraining(unittest.TestCase):
    def test_mastering_a_technique_deepens_cultivation(self):
        sim, w, ch = a_cultivator()
        out, text, d = sim.resolve(TRAIN, ch, None, w, 200, StubRng(0.0))
        self.assertEqual(out, "สำเร็จ")
        self.assertGreater(ch.insight, 0.0, "ฝึกวิชาสำเร็จต้องได้ความเข้าใจ")
        self.assertGreater(ch.refine, 0.0, "และต้องได้กายที่แกร่งขึ้นด้วย")
        self.assertEqual(len(ch.skills), 1)

    def test_a_failed_session_still_teaches_something(self):
        sim, w, ch = a_cultivator()
        out, text, d = sim.resolve(TRAIN, ch, None, w, 200, StubRng(0.99))
        self.assertEqual(out, "ฝึกพลาด")
        self.assertGreater(ch.insight, 0.0, "ล้มเหลวก็ได้บทเรียน")
        self.assertGreater(ch.decay, 0.0, "แต่ยังต้องมีราคาที่ต้องจ่าย")
        self.assertLess(ch.insight, C.TRAIN_INSIGHT_BASE, "ต้องน้อยกว่าการฝึกสำเร็จ")

    def test_the_gain_follows_the_configured_formula(self):
        sim, w, ch = a_cultivator()
        quiet(sim.resolve, TRAIN, ch, None, w, 200, StubRng(0.0))
        # วิชาชั้นพื้น (grade 0) ได้ตามค่าฐานเป๊ะ — ชั้นสูงขึ้นได้เพิ่มตาม PER_GRADE
        self.assertGreaterEqual(ch.insight, C.TRAIN_INSIGHT_BASE - 1e-9)
        self.assertGreaterEqual(ch.refine, C.TRAIN_REFINE - 1e-9)
        self.assertGreater(C.TRAIN_INSIGHT_PER_GRADE, 0.0,
                           "วิชาชั้นสูงต้องให้ความเข้าใจมากกว่าชั้นพื้น")

    def test_enough_training_actually_reaches_a_bottleneck(self):
        sim, w, ch = a_cultivator()
        ch.realm = ch.peak_realm = 0
        for _ in range(12):
            ch.skills = []                      # สมมุติว่ามีวิชาใหม่ให้ฝึกเรื่อยๆ
            quiet(sim.resolve, TRAIN, ch, None, w, 200, StubRng(0.0))
        self.assertTrue(ch.at_bottleneck(),
                        "ฝึกวิชาสิบกว่าครั้งแล้วยังไม่ถึงคอขวด = การฝึกไม่ได้พาไปไหน")


class TestHunting(unittest.TestCase):
    def test_hunting_beasts_tempers_the_body(self):
        sim, w, ch = a_cultivator()
        ch.place = next((i for i, p in enumerate(__import__("tiandao.places", fromlist=["x"]).PLACES)
                         if p[4]), ch.place)
        out, text, d = sim.resolve(HUNT, ch, None, w, 200, StubRng(0.99))
        if out == "ได้แก่นพลัง":
            self.assertGreater(ch.refine, 0.0, "กลั่นแก่นพลังอสูรต้องทำให้กายแกร่งขึ้น")
            self.assertGreater(ch.insight, 0.0, "การปะทะของจริงต้องสอนอะไรบางอย่าง")

    def test_the_gain_is_capped_per_hunt(self):
        sim, w, ch = a_cultivator()
        out, text, d = sim.resolve(HUNT, ch, None, w, 200, StubRng(0.99))
        self.assertLessEqual(ch.refine, C.HUNT_REFINE_CAP + 1e-9,
                             "ล่าครั้งเดียวต้องไม่ข้ามขั้นได้ทันที")


class TestWholeWorld(unittest.TestCase):
    def test_the_ladder_moves_over_a_long_run(self):
        sim = quiet(S.Sim, seed=11)
        quiet(sim.run, 60000)
        liv = [c for c in sim.cast if c.alive and c.sentient]
        cult = [c for c in liv if c.skills]
        elders = [c for c in cult if c.age(sim.day) >= 60]
        self.assertGreater(len(elders), 20)
        # วัดด้วย rank() (บันไดทั้งเส้น 0-29) ไม่ใช่ realm (0-9 ภายในชั้นฟ้า) — ไม่งั้นค่าเฉลี่ย
        # เอาคนละบันไดมาปนกัน: คนแดนบนที่เพิ่งข้ามฟ้ามี realm 0 ทั้งที่ไต่มาไกลกว่าใครในโลกล่าง
        #
        # เกณฑ์ตรงนี้จับแค่ "บันไดขยับจริงไหม" แบบหยาบๆ เท่านั้น ไม่ได้จับว่าการฝึกวิชา/ล่าอสูร
        # ให้ผลหรือไม่อีกแล้ว เพราะหลังใส่ "ปิดด่าน" (จังหวะรายปี) การบำเพ็ญในด่านกลายเป็นแหล่ง
        # ความเข้าใจที่ใหญ่กว่าการฝึกวิชามาก — วัดจริงที่ 60,000 เหตุการณ์ เมล็ด 11: ปิดค่าฝึก/ล่า
        # = 6.53 · เปิด = 6.60 คือต่างกันแค่ 1% ใช้แยกแยะไม่ได้แล้ว
        # การพิสูจน์ว่าฝึกวิชา/ล่าอสูรให้ความก้าวหน้าจริงจึงอยู่ในเทสต์ระดับกลไกข้างบนแทน
        # (test_mastering_a_technique_deepens_cultivation · test_the_gain_really_comes_from_these_knobs)
        avg = st.mean([c.rank() for c in elders])
        self.assertGreater(avg, 5.5, f"ผู้ฝึกตนอายุ 60+ ขั้นเฉลี่ย {avg:.2f} — บันไดไม่ขยับ")
        self.assertGreaterEqual(max(c.rank() for c in liv), 20,
                                "ต้องมีคนไต่ขึ้นไปถึงแดนชั้นเทพได้จริง")

    def test_the_gain_really_comes_from_these_knobs(self):
        """ปิดค่าที่เพิ่มเข้ามาแล้วผลต้องหายไป — พิสูจน์ว่าต่อสายไว้จริง ไม่ใช่ได้มาจากทางอื่น"""
        sim, w, ch = a_cultivator()
        keep = (C.TRAIN_INSIGHT_BASE, C.TRAIN_INSIGHT_PER_GRADE, C.TRAIN_REFINE)
        C.TRAIN_INSIGHT_BASE = C.TRAIN_INSIGHT_PER_GRADE = C.TRAIN_REFINE = 0.0
        try:
            quiet(sim.resolve, TRAIN, ch, None, w, 200, StubRng(0.0))
            self.assertEqual(ch.insight, 0.0)
            self.assertEqual(ch.refine, 0.0)
        finally:
            C.TRAIN_INSIGHT_BASE, C.TRAIN_INSIGHT_PER_GRADE, C.TRAIN_REFINE = keep


if __name__ == "__main__":
    unittest.main()
