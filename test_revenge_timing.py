# -*- coding: utf-8 -*-
"""แค้นต้องมีจังหวะ ไม่ใช่ลูปค้าง

    python -m unittest test_revenge_timing -v

วัดจริงก่อนแก้ จากบันทึกผู้มีจิตใจปีที่ 129-152 (23 ปี ตัวเอก 9 คน):
  ล้างแค้น 20 ครั้ง และ **คู่เดียวกินไป 8 ครั้งใน 3 ปี** — เหลียงไห่อวิ๋นบุกเจียงถิงเฉิน
  ปี 134 (×2) 135 (×2) 136 (×4) จบด้วย "พ่ายแพ้" 5 ครั้งติด แล้วบุกใหม่ทุกครั้ง

ทำไมมันค้าง: apply_defeat ทำ lose.rivals[win] += 2 ทุกครั้งที่แพ้ และ intent ให้น้ำหนัก
ล้างแค้นตามการมี rivals เฉยๆ → แพ้แล้วแค้นเพิ่ม → น้ำหนักเพิ่ม → บุกอีก → แพ้อีก
เป็นป้อนกลับบวกล้วนที่ปิดตัวเองไม่ได้จนกว่าจะมีคนตาย

ทางออกที่ไฟล์นี้ล็อกไว้: ก่อนบุก ให้ประเมินด้วย Elo ที่ระบบเก็บจากทุกการปะทะอยู่แล้ว
(physics.elo_expected) โอกาสชนะต่ำ = ยังไม่ถึงเวลา แค้นแปลงเป็นแรงฝึกแทนแรงบุก
และเพราะแพ้ครั้งที่สอง Elo ยิ่งตก ครั้งที่สามจึงยิ่งไม่เกิดเอง — ลูปปิดตัวเอง
"""
import contextlib
import io
import unittest

from tiandao import config as C
from tiandao import events as E
from tiandao import intent as IN
from tiandao import physics as PHYS
from tiandao import sim as S


def quiet(fn, *a, **kw):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*a, **kw)


def a_pair(seed=5):
    """โลกเล็กๆ กับคนสองคนที่มีแค้นต่อกัน — คืน (sim, ผู้แค้น, คู่แค้น)"""
    sim = quiet(S.Sim, seed=seed)
    quiet(sim.run, 3000)
    living = [c for c in sim.cast if c.alive and c.place is not None]
    a, t = living[0], living[1]
    a.rivals = {t.cid: 6}
    a.traits = [x for x in a.traits if x != "พยาบาท"]
    return sim, a, t


def weights(sim, ch):
    return quiet(IN.weigh, ch, sim, E.EVENT_TABLE, True)


def revenge_weight(sim, ch):
    return weights(sim, ch).get("ล้างแค้น", 0.0)


class TestHeWeighsHisOddsBeforeStriking(unittest.TestCase):
    def test_a_hopeless_grudge_weighs_less_than_an_even_one(self):
        sim, a, t = a_pair()
        a.elo, t.elo = 1500.0, 1500.0
        even = revenge_weight(sim, a)
        a.elo, t.elo = 1300.0, 1900.0
        hopeless = revenge_weight(sim, a)
        self.assertLess(hopeless, even,
                        "บุกคนที่เหนือกว่ามากต้องน่าดึงดูดน้อยกว่าบุกคนที่สูสี")

    def test_an_even_match_is_not_penalised(self):
        sim, a, t = a_pair()
        a.elo, t.elo = 1600.0, 1500.0
        self.assertGreater(PHYS.elo_expected(a.elo, t.elo), C.REVENGE_ODDS_FAIR)
        strong = revenge_weight(sim, a)
        a.elo, t.elo = 1500.0, 1500.0
        even = revenge_weight(sim, a)
        self.assertGreaterEqual(strong, even * 0.99,
                                "คนที่เหนือกว่าต้องไม่ถูกหน่วง")

    def test_the_grudge_never_goes_away_entirely(self):
        """คนที่รู้ว่าสู้ไม่ได้แต่ยังไป คือสิ่งที่ต้องมีในเรื่อง"""
        sim, a, t = a_pair()
        a.elo, t.elo = 1000.0, 2400.0
        self.assertGreater(revenge_weight(sim, a), 0.0,
                           "แค้นต้องไม่ถูกคำนวณจนหายไปเป็นศูนย์")

    def test_a_grudge_he_cannot_act_on_becomes_training(self):
        sim, a, t = a_pair()
        a.elo, t.elo = 1500.0, 1500.0
        a.rivals = {}
        base = weights(sim, a).get("ฝึกวิชา", 0.0)
        a.rivals = {t.cid: 6}
        a.elo, t.elo = 1200.0, 2000.0
        held = weights(sim, a).get("ฝึกวิชา", 0.0)
        self.assertGreater(held, base,
                           "แค้นที่ยังบุกไม่ได้ต้องกลายเป็นแรงฝึก ไม่ใช่หายไปเฉยๆ")


class TestLosingTwiceMakesTheThirdTryRarer(unittest.TestCase):
    def test_the_loop_closes_itself(self):
        """จุดสำคัญ: แพ้แล้ว Elo ตก ซึ่งต้องลดน้ำหนักบุกลง ไม่ใช่เพิ่มอย่างที่เคยเป็น"""
        sim, a, t = a_pair()
        a.elo, t.elo = 1500.0, 1500.0
        before = revenge_weight(sim, a)
        for _ in range(3):
            a.elo, t.elo = PHYS.elo_update(a.elo, t.elo, False, C.ELO_K)
            a.rivals[t.cid] = a.rivals.get(t.cid, 0) + 2   # อย่างที่ apply_defeat ทำ
        after = revenge_weight(sim, a)
        self.assertLess(after, before,
                        "แพ้สามครั้งติดแล้วยังบุกหนักขึ้น = ลูปค้างแบบเดิม")


if __name__ == "__main__":
    unittest.main()
