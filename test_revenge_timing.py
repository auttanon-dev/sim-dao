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
from tiandao import news as NEWS
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


class TestWhoCarriesTheGrudge(unittest.TestCase):
    """ฆ่าหนึ่งคน ใครแค้นผู้ฆ่า — ครอบครัวแค้นเต็มที่ คนตระกูลเดียวกันที่อยู่ตรงนั้นแค้นพอประมาณ ที่ไกลยังไม่รู้"""

    def setUp(self):
        self.sim = quiet(S.Sim, seed=5)
        people = [c for c in self.sim.cast if c.alive and c.world_id == 0 and c.place is not None
                  and c.place >= 0 and not c.hidden and c.sentient]
        (self.victim, self.killer, self.parent, self.child, self.spouse, self.clan_here, self.clan_far,
         self.clan_hidden, self.stranger) = people[:9]
        here = self.victim.place
        far = next(p for p in (c.place for c in people) if p != here)
        for c in people[:9]:
            c.rivals, c.org, c.clan, c.hidden = {}, None, -1, False
        v = self.victim
        v.clan, self.killer.clan = 0, 1
        v.parents, v.children, v.spouse = [self.parent.cid], [self.child.cid], self.spouse.cid
        self.parent.place = far                                  # ครอบครัวอยู่ไกลก็แค้น
        self.child.clan, self.child.place = 0, here              # ญาติที่เป็นคนตระกูลอยู่ตรงนั้นด้วย ได้ระดับเดียว
        self.clan_here.clan, self.clan_here.place = 0, here
        self.clan_far.clan, self.clan_far.place = 0, far
        self.clan_hidden.clan, self.clan_hidden.place, self.clan_hidden.hidden = 0, here, True
        self.stranger.place = here
        quiet(self.sim.kill, v, "ถูกสังหาร", killer=self.killer)

    def grudge(self, ch):
        return ch.rivals.get(self.killer.cid, 0)

    def arrive(self):
        """ส่งข่าวที่ค้างทั้งหมด (§7.4 ข้อ 8: คนไกลรู้เมื่อข่าวเดินทางถึง)"""
        self.sim.day = max([item[0] for item in self.sim.death_news] + [self.sim.day])
        NEWS.tick(self.sim)

    def test_family_on_the_spot_knows_at_once_and_distant_family_once_the_news_arrives(self):
        self.assertEqual(self.grudge(self.child), C.GRUDGE_KIN)
        self.assertEqual(self.grudge(self.parent), 0, "ข่าวยังไปไม่ถึง")
        self.arrive()
        for kin in (self.parent, self.child, self.spouse):
            self.assertEqual(self.grudge(kin), C.GRUDGE_KIN)

    def test_distant_and_hidden_clansfolk_carry_the_lighter_grudge_once_the_news_arrives(self):
        self.arrive()
        for other in (self.clan_far, self.clan_hidden):
            self.assertEqual(self.grudge(other), C.GRUDGE_NEAR)
        self.assertNotIn(self.killer.cid, self.stranger.rivals, "คนนอกไม่แค้นแม้ได้ข่าว")

    def test_clansfolk_on_the_spot_carry_a_lighter_grudge(self):
        self.assertEqual(self.grudge(self.clan_here), C.GRUDGE_NEAR)

    def test_nobody_far_away_hidden_or_unrelated_carries_it_yet(self):
        for other in (self.clan_far, self.clan_hidden, self.stranger):
            self.assertNotIn(self.killer.cid, other.rivals)


class TestGrudgesFade(unittest.TestCase):
    def setUp(self):
        self.sim = quiet(S.Sim, seed=5)
        self.me, self.foe, gone = [c for c in self.sim.cast if c.alive][:3]
        quiet(self.sim.kill, gone, "ทดสอบ", natural=True)
        self.me.rivals = {self.foe.cid: 1.0, gone.cid: 5}
        self.gone = gone

    def test_a_grudge_fades_each_year_and_one_against_the_dead_is_dropped(self):
        self.sim.fade_grudges(365)
        self.assertAlmostEqual(self.me.rivals[self.foe.cid], 1.0 - C.GRUDGE_FADE_PER_YEAR)
        self.assertNotIn(self.gone.cid, self.me.rivals, "แค้นคนตายชำระไม่ได้")
        self.sim.fade_grudges(365 * 5)
        self.assertEqual(self.me.rivals, {}, "จางหมดแล้วไม่เป็นคู่แค้นอีก")

    def test_the_world_clock_fades_grudges_every_round(self):
        self.sim.world_tick_day = self.sim.food_day + 365          # รอบของโลกที่ห่างจากรอบก่อนหนึ่งปี
        quiet(self.sim._world_tick, self.sim.rng)
        self.assertAlmostEqual(self.me.rivals[self.foe.cid], 1.0 - C.GRUDGE_FADE_PER_YEAR)


if __name__ == "__main__":
    unittest.main()
