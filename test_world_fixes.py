# -*- coding: utf-8 -*-
"""สู้กลับตอนมารบุก · ชื่อไม่ซ้ำทั้งจักรวาล · เพดานสัดส่วนอสูรในหมู่ผู้มีจิตใจ

    python -m unittest test_world_fixes -v
"""
import contextlib
import io
import shutil
import tempfile
import unittest

from tiandao import config as C
from tiandao import persist as PS
from tiandao import sim as S
from tiandao.mind import backend as B
from tiandao.mind import config as MC
from tiandao.mind.runner import RunConfig, open_world


def quiet(fn, *a, **kw):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*a, **kw)


class StubRng:
    """สุ่มแบบกำหนดผลได้ — ใช้ตรวจกิ่งของ mara_raid ทีละกิ่ง"""
    def __init__(self, value):
        self.value = value

    def random(self):
        return self.value

    def choice(self, seq):
        return seq[0]

    def randint(self, a, b):
        return a

    def uniform(self, a, b):
        return a


class TestUniqueNames(unittest.TestCase):
    def test_world_has_no_duplicate_names(self):
        sim = quiet(S.Sim, seed=5, tiers=2)
        names = [c.name for c in sim.cast]
        self.assertEqual(len(names), len(set(names)))

    def test_unique_name_adds_a_distinguishing_part(self):
        sim = quiet(S.Sim, seed=5, tiers=2)
        first = sim.unique_name("เซียวจื่อ")
        second = sim.unique_name("เซียวจื่อ")
        third = sim.unique_name("ทาคากิ โทโมเอะ")
        fourth = sim.unique_name("ทาคากิ โทโมเอะ")
        self.assertNotEqual(first, second)
        self.assertTrue(second.startswith("เซียวจื่อ"))
        self.assertNotEqual(third, fourth)
        self.assertTrue(fourth.startswith("ทาคากิ โทโมเอะ ที่ "))

    def test_names_stay_unique_while_the_world_runs(self):
        sim = quiet(S.Sim, seed=11, tiers=2)
        quiet(sim.run, 4000)
        names = [c.name for c in sim.cast]
        self.assertEqual(len(names), len(set(names)), "มีคนชื่อซ้ำกันเกิดขึ้นระหว่างโลกเดิน")

    def test_many_duplicates_still_read_as_names(self):
        sim = quiet(S.Sim, seed=5, tiers=2)
        made = [sim.unique_name("หลัวจื่อ") for _ in range(30)]
        self.assertEqual(len(set(made)), 30)
        self.assertEqual([n for n in made if " ที่ " in n], [], "ชื่อคนไม่ควรลงท้ายด้วย ที่ N ถ้ายังผสมพยางค์ได้")

    def test_beast_names_get_an_ordinal(self):
        sim = quiet(S.Sim, seed=5, tiers=2)
        first = sim.unique_name("พยัคฆ์เขี้ยวเพลิง", marker="ตัวที่")
        second = sim.unique_name("พยัคฆ์เขี้ยวเพลิง", marker="ตัวที่")
        self.assertEqual(second, first + " ตัวที่ 2")

    def test_old_save_gets_a_name_set(self):
        sim = quiet(S.Sim, seed=5, tiers=2)
        del sim.used_names
        PS._backfill_new_attrs(sim)
        self.assertEqual(sim.used_names, {c.name for c in sim.cast})


class TestMaraFightBack(unittest.TestCase):
    def setUp(self):
        self.sim = quiet(S.Sim, seed=7, tiers=3)
        self.world = next(w for w in self.sim.worlds
                          if w.kind == "mortal" and w.lateral and self.sim.world(w.lateral[0]).kind == "mara")
        self.mara_world = self.sim.world(self.world.lateral[0])
        self.raider = next(c for c in self.sim.living_in(self.mara_world.wid) if c.realm >= 2)
        self.world.defense_array = 0.0

    def _prey(self, realm):
        prey = self.sim.living_in(self.world.wid)
        victim = prey[0]
        for c in prey:                      # ให้เหลือเป้าเดียวที่เลือกได้ เพื่อตรวจผลของกิ่งเดียว
            c.hidden = c.cid != victim.cid
        victim.realm = realm
        victim.fate = 1
        return victim

    def test_strong_victim_can_kill_the_raider(self):
        victim = self._prey(self.raider.realm + 1)
        self.sim.mara_raid(self.world, 0, StubRng(0.0))
        ev = self.sim.log[-1]
        self.assertEqual((ev.kind, ev.outcome), ("มารบุก", "ปราบมารได้"))
        self.assertEqual(ev.actor, victim.cid)
        self.assertTrue(victim.alive)
        self.assertFalse(self.sim.cast[ev.target].alive, "มารที่ถูกส่งมาต้องถูกสังหาร")

    def test_losing_the_fight_still_leaves_fate_and_wounds(self):
        victim = self._prey(self.raider.realm)
        victim.hp = 100
        self.sim.mara_raid(self.world, 0, StubRng(0.999))   # แพ้การสู้ และไม่ถูกครอบงำ
        self.assertTrue(self.raider.alive)
        self.assertTrue(victim.alive, "ยังมีชะตาเหลือ ต้องรอดตาย")
        self.assertEqual(victim.fate, 0)
        self.assertLess(victim.hp, 100)
        self.assertEqual(self.sim.log[-1].outcome, "รอดตายด้วยชะตา")

    def test_weak_victim_never_fights(self):
        victim = self._prey(0)
        self.raider.realm = max(3, self.raider.realm)
        victim.fate = 0
        self.sim.mara_raid(self.world, 0, StubRng(0.999))
        self.assertTrue(self.raider.alive)
        self.assertFalse(victim.alive)
        self.assertEqual(self.sim.log[-1].outcome, "ตาย")


class TestWildBeastPopulation(unittest.TestCase):
    def test_hunted_beasts_do_not_pile_up_in_the_world(self):
        sim = quiet(S.Sim, seed=11, tiers=2)
        quiet(sim.run, 12000)
        alive = sim.living_in(0)
        beasts = [c for c in alive if getattr(c, "is_beast", False)]
        humans = [c for c in alive if not getattr(c, "is_beast", False)]
        self.assertTrue(humans, "โลกมนุษย์ต้องยังมีมนุษย์")
        self.assertLess(len(beasts), len(humans),
                        f"สัตว์อสูรป่า {len(beasts)} ตัว เทียบมนุษย์ {len(humans)} คน — อสูรค้างในโลก")


class TestHomeWorldDensity(unittest.TestCase):
    def test_home_world_is_the_crowded_stage(self):
        sim = quiet(S.Sim, seed=11, tiers=3)
        quiet(sim.run, 30000)
        home = len(sim.living_in(0))
        others = [len(sim.living_in(w.wid)) for w in sim.worlds
                  if w.wid != 0 and w.kind == "mortal" and not getattr(w, "skill_line", None)]
        self.assertGreater(home, C.CAST_SIZE,
                           f"โลกมนุษย์มีแค่ {home} คน — เวทีหลักต้องแน่นกว่าเพดานแดนอื่น")
        self.assertGreater(home, max(others or [0]), "โลกมนุษย์ต้องมีคนมากกว่าแดนอื่น")
        self.assertTrue(any(c.age(sim.day) < 16 for c in sim.living_in(0)))

    def test_branch_realms_stay_small(self):
        sim = quiet(S.Sim, seed=11, tiers=3)
        branches = [w for w in sim.worlds if getattr(w, "skill_line", None)]
        self.assertLessEqual(len(branches), C.BRANCH_REALMS + 4,
                             "แดนสาขาตั้งต้นต้องไม่เกินที่ตั้งค่าไว้")
        self.assertLess(len(branches) * C.BRANCH_CAST, C.HOME_CAST * 2,
                        "ประชากรรวมของสาขาไม่ควรกลบเวทีหลัก")


class TestRaidRealmMatching(unittest.TestCase):
    def test_the_raider_sent_is_the_one_closest_in_realm(self):
        sim = quiet(S.Sim, seed=7, tiers=3)
        world = next(w for w in sim.worlds
                     if w.kind == "mortal" and w.lateral and sim.world(w.lateral[0]).kind == "mara")
        world.defense_array = 0.0
        # เอาชาวแดนมารทุกคนมาเป็นผู้บุก แล้วตั้งขั้นพลังให้กระจาย — ไม่กรองด้วย realm >= 2
        # ก่อน เพราะจำนวนมารที่ขั้นถึงตอนสร้างโลกขึ้นกับลำดับ RNG ซึ่งขยับได้ทุกครั้งที่มี
        # การสุ่มอย่างอื่นเพิ่มเข้ามา (เช่นตอนเพิ่มเจ็ดอารมณ์หกปรารถนา) เทสต์นี้ตรวจ "การจับคู่
        # ขั้นพลัง" ไม่ได้ตรวจการกระจายประชากร จึงไม่ควรพังเพราะประชากรเปลี่ยน
        raiders = list(sim.living_in(sim.world(world.lateral[0]).wid))
        self.assertGreaterEqual(len(raiders), 3, "แดนมารต้องมีมารหลายตัวจึงจะทดสอบการจับคู่ได้")
        for i, c in enumerate(raiders):
            c.realm = 2 + (i % 6)
            c.peak_realm = max(getattr(c, "peak_realm", 0), c.realm)
        prey = sim.living_in(world.wid)
        victim = prey[0]
        for c in prey:
            c.hidden = c.cid != victim.cid
        victim.realm = 5
        victim.fate = 0
        closest = min(raiders, key=lambda c: (abs(c.realm - 5), c.cid))
        sim.mara_raid(world, 0, StubRng(0.999))       # แพ้ทุกการทอย เพื่อดูแค่ว่าใครถูกส่งมา
        ev = sim.log[-1]
        self.assertEqual(ev.actor, closest.cid, "ต้องเป็นมารที่ขั้นพลังใกล้เหยื่อที่สุด")
        self.assertEqual(ev.target, victim.cid)


class TestBeastMindCap(unittest.TestCase):
    def test_beasts_cannot_take_over_the_cast(self):
        tmp = tempfile.mkdtemp()
        try:
            cfg = RunConfig(out_dir=tmp, seed=4, capacity=12, story=False)
            sim = open_world(cfg, B.MockThinker())
            mind = sim.mind
            beasts = [c for c in sim.living()
                      if c.cid not in mind.minds and getattr(c, "sentient", True) and c.age(sim.day) >= MC.MIND_MIN_AGE]
            for c in beasts[:8]:                 # จำลองอสูรร่างมนุษย์ที่ฆ่าผู้มีจิตใจแล้วได้สืบบท
                c.is_beast, c.has_human_form = True, True
            for m in list(mind.active())[:6]:    # เปิดที่ว่างให้ผู้สืบบท
                mind.minds[m.cid].alive = False
                sim.cast[m.cid].alive = False
            mind.successor_hints = [(c.cid, "ผู้ที่ปลิดชีพผู้มีจิตใจ") for c in beasts[:8]]
            mind.ensure_cast(sim)
            n_beast = sum(1 for m in mind.active() if getattr(sim.cast[m.cid], "is_beast", False))
            cap = max(1, int(cfg.capacity * MC.BEAST_MIND_MAX_RATIO))
            self.assertLessEqual(n_beast, cap, f"อสูรเป็นผู้มีจิตใจ {n_beast} คน เกินเพดาน {cap}")
            self.assertGreaterEqual(len(mind.active()), cfg.capacity - 2, "ต้องยังเติมคนให้ครบด้วยคนอื่น")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
