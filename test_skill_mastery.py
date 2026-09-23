# -*- coding: utf-8 -*-
"""มีวิชาอยู่ในมือ = ฝึกมาแล้วอย่างน้อยหนึ่งครั้ง

    python -m unittest test_skill_mastery -v

กติกาข้อนี้เป็นของโลกเอง (ดู Character.learn_skill) ไม่ใช่ของมือจับใดมือจับหนึ่ง แต่เดิมมีแค่
"ฝึกวิชา" กับ "ถ่ายทอดวิชา" ที่ตั้ง mastery ให้ อีกห้าทางต่อชื่อวิชาเข้า list เฉยๆ:
จุติคืนสังสารวัฏ · ตื่นความทรงจำชาติก่อน · ต่อเศษวิชาโบราณ · ชิงวิชาจากการหักหลัง ·
ต้นไม้โลกหยั่งกิ่ง

ผลของช่องว่างนั้นวัดได้จริงสองอย่าง ไม่ใช่เรื่องความสะอาดของข้อมูลอย่างเดียว:
  · rules.skill_power คูณ practice_mastery(0) = 0 วิชานั้นจึงเหลือแค่ SKILL_BASE_SHARE
  · สอนต่อไม่ได้เลย เพราะ TEACH_MIN_REPS กรอง mastery ออกก่อนทุกครั้ง
คนที่ได้วิชามาด้วยวิธีที่หายากที่สุดในโลก จึงเป็นคนที่วิชานั้นใช้การไม่ได้พอดี
"""
import contextlib
import io
import unittest

from tiandao import config as C
from tiandao import events as E
from tiandao import rules as R
from tiandao import sim as S
from tiandao import skills as SK
from tiandao import worldtree as WT
from tiandao.models import Character

BETRAY = next(e for e in E.EVENT_TABLE if e["kind"] == "ทรยศ")
SEARCH = next(e for e in E.EVENT_TABLE if e["kind"] == "ค้นแดนลับ")


def quiet(fn, *a, **kw):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*a, **kw)


class StubRng:
    """ทอยแบบคาดเดาได้ — ให้ผลของเทสต์ขึ้นกับตรรกะ ไม่ใช่กับโชค"""

    def __init__(self, value=0.0):
        self.value = value

    def random(self):
        return self.value

    def randint(self, a, b):
        return a

    def uniform(self, a, b):
        return a

    def choice(self, seq):
        return seq[0]

    def sample(self, seq, k):
        return list(seq)[:k]


def unpractised(sim):
    """คนที่ถือวิชาโดยความชำนาญยังเป็นศูนย์ — ตามกติกาของโลกต้องไม่มีเลย"""
    return [(c.cid, n) for c in sim.cast for n in c.skills if c.mastery.get(n, 0) < 1]


def person(cid=0):
    return Character(cid=cid, name=f"ผู้ทดสอบ {cid}", world_id=0, dao="วิถีดาบ",
                     dao_tags=[], born_day=0)


class LearnSkillTests(unittest.TestCase):
    """ตัวช่วยกลางต้องรักษากติกาได้เองโดยผู้เรียกไม่ต้องจำ"""

    def test_a_skill_arrives_already_practised_once(self):
        ch = person()
        self.assertTrue(ch.learn_skill("วิชาหนึ่ง"), "วิชาใหม่ต้องรายงานว่าใหม่")
        self.assertEqual(ch.skills, ["วิชาหนึ่ง"])
        self.assertEqual(ch.mastery["วิชาหนึ่ง"], 1)

    def test_the_same_skill_is_never_held_twice(self):
        ch = person()
        ch.learn_skill("วิชาหนึ่ง")
        self.assertFalse(ch.learn_skill("วิชาหนึ่ง"), "ของที่มีอยู่แล้วต้องไม่รายงานว่าใหม่")
        self.assertEqual(ch.skills, ["วิชาหนึ่ง"])

    def test_depth_already_earned_is_never_reset(self):
        """ฝึกมาสี่สิบครั้งแล้วได้วิชาเดียวกันจากอีกทางหนึ่ง ต้องไม่ถูกดึงกลับเป็นหนึ่ง"""
        ch = person()
        ch.learn_skill("วิชาหนึ่ง")
        ch.mastery["วิชาหนึ่ง"] = 40
        ch.learn_skill("วิชาหนึ่ง")
        self.assertEqual(ch.mastery["วิชาหนึ่ง"], 40)

    def test_a_larger_floor_lifts_but_a_smaller_one_does_not(self):
        ch = person()
        ch.learn_skill("วิชาหนึ่ง", reps=3)
        self.assertEqual(ch.mastery["วิชาหนึ่ง"], 3)
        ch.learn_skill("วิชาหนึ่ง", reps=1)
        self.assertEqual(ch.mastery["วิชาหนึ่ง"], 3)

    def test_a_zero_or_negative_floor_cannot_break_the_invariant(self):
        """reps=0 เคยต่อชื่อวิชาเข้ามือโดยไม่สร้างความชำนาญ — สร้างสภาพเดียวกับบั๊กที่
        เมธอดนี้มีไว้กำจัดพอดี invariant ต้องไม่ขึ้นกับความระวังของผู้เรียก
        """
        for reps in (0, -5):
            ch = person()
            ch.learn_skill("วิชาหนึ่ง", reps=reps)
            self.assertEqual(ch.mastery.get("วิชาหนึ่ง", 0), 1, f"reps={reps}")
            self.assertEqual([n for n in ch.skills if ch.mastery.get(n, 0) < 1], [])

    def test_a_zero_floor_still_does_not_erase_earned_depth(self):
        ch = person()
        ch.learn_skill("วิชาหนึ่ง")
        ch.mastery["วิชาหนึ่ง"] = 40
        ch.learn_skill("วิชาหนึ่ง", reps=0)
        self.assertEqual(ch.mastery["วิชาหนึ่ง"], 40)

    def test_a_missing_mastery_table_is_rebuilt_not_crashed_into(self):
        """ตัวละครจากเซฟเก่าที่ mastery ไม่ใช่ dict ต้องรับวิชาใหม่ได้โดยไม่ระเบิด"""
        ch = person()
        ch.__dict__["mastery"] = None
        ch.learn_skill("วิชาหนึ่ง")
        self.assertEqual(ch.mastery, {"วิชาหนึ่ง": 1})

    def test_a_practised_skill_is_worth_more_power_than_a_hollow_one(self):
        """ยืนยันว่ากติกานี้มีผลจริงกับพลัง ไม่ใช่แค่ตัวเลขในตาราง"""
        ch = person()
        name = next(s[0] for s in SK.SKILLS)
        ch.learn_skill(name)
        with_practice = R.skill_power(ch)
        ch.mastery = {}
        self.assertGreater(with_practice, R.skill_power(ch))


class GrantPathTests(unittest.TestCase):
    """ทุกทางที่วิชาเข้ามือคนได้ ต้องผ่านกติกาเดียวกัน"""

    def setUp(self):
        self.sim = quiet(S.Sim, seed=11, tiers=2)
        self.w = self.sim.worlds[0]

    def holder_ok(self, ch, name):
        self.assertIn(name, ch.skills)
        self.assertGreaterEqual(ch.mastery.get(name, 0), 1,
                                f"{ch.name} ถือ「{name}」แต่นับว่าฝึกมาศูนย์ครั้ง")

    def test_a_reincarnated_baby_can_use_what_it_was_born_with(self):
        ch = next(c for c in self.sim.living_in(0) if c.sentient)
        baby = quiet(self.sim.reincarnate, ch)
        self.assertTrue(baby.skills, "ทารกจุติต้องได้วิชาเมล็ดของสายวัฏจักรติดตัว")
        for name in baby.skills:
            self.holder_ok(baby, name)

    def test_past_life_skills_come_back_already_practised(self):
        ch = next(c for c in self.sim.living_in(0) if c.sentient)
        ch.skills, ch.mastery = [], {}
        ch.past_skills = [s[0] for s in SK.SKILLS[:5]]
        ch.past_name, ch.past_dao, ch.past_realm = "ชาติก่อน", ch.dao, 5
        quiet(self.sim.wake_past_life, ch)
        self.assertTrue(ch.skills, "ตื่นความทรงจำแล้วต้องได้วิชาเดิมกลับมาบ้าง")
        for name in ch.skills:
            self.holder_ok(ch, name)

    def test_completing_an_ancient_fragment_set_gives_a_usable_skill(self):
        a = next(c for c in self.sim.living_in(0) if c.sentient)
        a.skills, a.mastery, a.fragments = [], {}, {}
        frag = next(f for f in self.sim.skill_fragments if not f["found"])
        frag["place"] = a.place
        name = frag["skill"]
        a.fragments[name] = [p for p in range(C.FRAGMENTS_PER_SKILL) if p != frag["piece"]]
        out, _text, _d = self.sim.resolve(SEARCH, a, None, self.w, 30, StubRng())
        self.assertEqual(out, "ต่อวิชาโบราณสำเร็จ")
        self.holder_ok(a, name)

    def test_a_stolen_skill_is_usable_in_the_new_hands(self):
        people = [c for c in self.sim.living_in(0) if c.sentient and c.age(self.sim.day) >= 16]
        a, t = people[0], people[1]
        for c in (a, t):
            c.rivals, c.bonds, c.debts, c.items = {}, {}, [], []
            c.skills, c.mastery = [], {}
            c.money = {0: 200}
            c.master_cid, c.disciples, c.spouse = -1, [], None
            c.org, c.clan = None, -1
        name = next(s[0] for s in SK.SKILLS)
        t.learn_skill(name)
        t.bonds[a.cid] = 3
        a.bonds[t.cid] = 3
        out, _text, d = self.sim.resolve(BETRAY, a, t, self.w, 30, StubRng())
        self.assertEqual(out, "หักหลัง")
        self.assertIn(f"วิชา{name}", d["ที่ได้ไป"], "ต้องชิงวิชาไปได้จริงในเทสต์นี้")
        self.holder_ok(a, name)

    def test_a_skill_dropped_by_the_world_tree_is_usable(self):
        WT.init(self.sim)
        # 0.65 <= roll < 0.88 คือกิ่งที่หย่อน "วิชาหายาก" ลงมา (ดู worldtree._gift_for)
        got = WT._gift_for(self.sim, self.w, StubRng(0.7))
        self.assertIsNotNone(got, "ทอยนี้ต้องตกกิ่งวิชาหายาก")
        who, what = got
        self.assertIn("วิชาหายาก", what)
        self.holder_ok(who, what.split("วิชาหายาก ")[1])


class WorldInvariantTests(unittest.TestCase):
    """ด่านสุดท้าย — เดินโลกจริงแล้วต้องไม่มีใครถือวิชาที่ฝึกมาศูนย์ครั้ง

    ข้อนี้กันทางแจกวิชา **ทางใหม่** ที่จะถูกเพิ่มในอนาคตด้วย ไม่ใช่แค่ห้าทางที่รู้จักตอนนี้
    """

    @classmethod
    def setUpClass(cls):
        cls.sim = quiet(S.Sim, seed=11, tiers=3)
        quiet(cls.sim.run, 12000)

    def test_no_one_holds_a_skill_they_have_never_practised(self):
        holders = [c for c in self.sim.cast if c.skills]
        self.assertGreater(len(holders), 50, "ต้องมีคนถือวิชามากพอจะวัดได้")
        self.assertEqual(unpractised(self.sim), [])

    def test_nobody_holds_the_same_skill_twice(self):
        dupes = [c.cid for c in self.sim.cast if len(c.skills) != len(set(c.skills))]
        self.assertEqual(dupes, [])

    def test_mastery_never_records_a_skill_nobody_holds(self):
        stray = [(c.cid, n) for c in self.sim.cast for n in c.mastery if n not in c.skills]
        self.assertEqual(stray, [])


if __name__ == "__main__":
    unittest.main()
