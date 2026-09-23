# -*- coding: utf-8 -*-
"""เทสต์สำหรับใบงาน TASK_MINDS_FIX.md — ห้ามแก้ไฟล์นี้ แก้โค้ดใน tiandao/mind/ จนเทสต์ผ่าน

    python -m unittest test_minds_fix -v
"""
import json
import math
import os
import shutil
import tempfile
import unittest

from tiandao import places as PL
from tiandao import travel as TR
from tiandao.models import Event
from tiandao.mind import backend as B
from tiandao.mind import config as MC
from tiandao.mind import prompt as PR
from tiandao.mind import storyteller as ST
from tiandao.mind.runner import MindRunner, RunConfig, open_world, read_journal


def make_event(sim, seq, kind, actor, target=None, tags=("ต่อสู้",), outcome="ตาย", text="", day=None):
    return Event(seq=seq, day=sim.day if day is None else day, gap_days=0, world_id=0, era=1, kind=kind,
                 actor=actor, target=target, tags=list(tags), outcome=outcome, text=text or kind)


def days_between(a, b, realm=0):
    if a == b:
        return 0
    return TR.shortest_path_days(a, b, realm)


class Base(unittest.TestCase):
    capacity = 12
    seed = 3

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.cfg = RunConfig(out_dir=self.tmp, seed=self.seed, capacity=self.capacity, story=False)
        self.sim = open_world(self.cfg, B.MockThinker())
        self.mind = self.sim.mind

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def journal(self):
        path = self.cfg.journal_path
        if not os.path.exists(path):
            return []
        with open(path, encoding="utf-8") as f:
            return [json.loads(line) for line in f]


# ---------------------------------------------------------------- งานที่ 1: มารบุกท่วมบันทึก
class TestFix1Successors(Base):
    def _dead_mind_and_killer(self):
        victim = self.sim.cast[self.mind.active()[0].cid]
        killer = next(c for c in self.sim.living() if c.cid not in self.mind.minds and c.cid != victim.cid)
        victim.alive = False
        return victim, killer

    def test_config_has_killer_kinds(self):
        self.assertIn("ล้างแค้น", MC.SUCCESSOR_KILLER_KINDS)
        self.assertIn("ประลอง", MC.SUCCESSOR_KILLER_KINDS)
        self.assertNotIn("มารบุก", MC.SUCCESSOR_KILLER_KINDS)

    def test_raid_killer_is_not_successor(self):
        victim, killer = self._dead_mind_and_killer()
        ev = make_event(self.sim, 10**9, "มารบุก", killer.cid, victim.cid, tags=("ความตาย",))
        self.mind._mark_dead(self.sim, victim, ev)
        self.assertNotIn(killer.cid, [cid for cid, _ in self.mind.successor_hints])

    def test_chosen_fight_killer_is_successor(self):
        victim, killer = self._dead_mind_and_killer()
        ev = make_event(self.sim, 10**9, "ล้างแค้น", killer.cid, victim.cid, tags=("เลือด",))
        self.mind._mark_dead(self.sim, victim, ev)
        self.assertIn(killer.cid, [cid for cid, _ in self.mind.successor_hints])


class TestFix1Collapse(Base):
    def test_config_has_collapse_kinds(self):
        self.assertIn("มารบุก", MC.COLLAPSE_KINDS)

    def test_repeated_raids_write_one_line_per_year(self):
        cid = self.mind.active()[0].cid
        victims = [c for c in self.sim.living() if c.cid not in self.mind.minds][:6]
        day0 = self.sim.day
        for i, v in enumerate(victims[:5]):
            self.mind.on_event(make_event(self.sim, 10**9 + i, "มารบุก", cid, v.cid, day=day0), self.sim)
        raids = [e for e in self.journal() if e.get("cid") == cid and e.get("action") == "มารบุก"]
        self.assertEqual(len(raids), 1, "เหตุการณ์ซ้ำชนิดเดียวกันในปีเดียวกันต้องเหลือบรรทัดเดียว")
        memories = [m for m in self.mind.minds[cid].memories if "มารบุก" in m]
        self.assertLessEqual(len(memories), 1)
        # ปีถัดไปเขียนได้อีกหนึ่งบรรทัด
        self.mind.on_event(make_event(self.sim, 10**9 + 99, "มารบุก", cid, victims[5].cid, day=day0 + 366), self.sim)
        raids = [e for e in self.journal() if e.get("cid") == cid and e.get("action") == "มารบุก"]
        self.assertEqual(len(raids), 2)

    def test_other_events_are_not_collapsed(self):
        cid = self.mind.active()[0].cid
        for i in range(3):
            self.mind.on_event(make_event(self.sim, 10**9 + i, "ได้ยินข่าวลือ", cid, None,
                                          tags=("คน",), outcome="ได้ยิน"), self.sim)
        rumors = [e for e in self.journal() if e.get("cid") == cid and e.get("action") == "ได้ยินข่าวลือ"]
        self.assertEqual(len(rumors), 3)


# ---------------------------------------------------------------- งานที่ 2: ให้ผู้มีจิตใจได้เจอกัน
class TestFix2Home(Base):
    def test_minds_start_near_home(self):
        home = self.mind.home_place
        self.assertIsInstance(home, int)
        self.assertGreaterEqual(home, 0)
        minds = [self.sim.cast[m.cid] for m in self.mind.active()]
        near = [c for c in minds
                if c.world_id == 0 and (days_between(home, c.place) or 10**9) <= MC.HOME_RADIUS_DAYS]
        self.assertGreaterEqual(len(near), math.ceil(len(minds) * 0.75),
                                f"ผู้มีจิตใจต้องเริ่มใกล้ {PL.PLACES[home][0]} ภายใน {MC.HOME_RADIUS_DAYS} วัน")

    def test_home_place_survives_save_load(self):
        home = self.mind.home_place
        from tiandao import persist as PS
        PS.save_sim(self.sim, self.cfg.save_path)
        again = open_world(self.cfg, B.MockThinker())
        self.assertEqual(again.mind.home_place, home)


class TestFix2Home2(TestFix2Home):
    seed = 1
    capacity = 20


class TestFix2People(Base):
    def test_other_minds_listed_first(self):
        me = self.sim.cast[self.mind.active()[0].cid]
        other_minds = [self.sim.cast[m.cid] for m in self.mind.active()[1:4]]
        strangers = [c for c in self.sim.living() if c.cid not in self.mind.minds and c.age(self.sim.day) >= 16][:8]
        # ใส่ศัตรูไว้ด้วย — ปกติศัตรูได้คะแนนสูงสุด แต่ผู้มีจิตใจต้องมาก่อน
        me.rivals[strangers[0].cid] = 9
        picked = PR.pick_people(self.sim, me, strangers + other_minds, 8)
        first = [c.cid for c in picked[:len(other_minds)]]
        self.assertEqual(sorted(first), sorted(c.cid for c in other_minds))

    def test_destinations_show_where_other_minds_are(self):
        me = self.sim.cast[self.mind.active()[0].cid]
        key = self.sim.world(me.world_id).place_key
        options = [p for p in PL.places_in(key) if p != me.place and days_between(me.place, p, me.realm) is not None]
        far = max(options, key=lambda p: days_between(me.place, p, me.realm))
        friend = self.sim.cast[self.mind.active()[1].cid]
        for m in self.mind.active()[2:]:          # คนอื่นยืนอยู่ที่เดียวกับเรา จะได้ไม่แย่งช่องจุดหมาย
            self.sim.cast[m.cid].place = me.place
        friend.world_id = me.world_id
        friend.place = far
        dests = PR.pick_destinations(self.sim, me, MC.DESTINATIONS_MAX)
        self.assertIn(far, [p for p, _, _ in dests], "ที่ที่ผู้มีจิตใจอีกคนอยู่ต้องถูกเสนอเป็นจุดหมาย")
        note = next(n for p, _, n in dests if p == far)
        self.assertTrue(any(friend.name in x for x in note), "หมายเหตุต้องบอกชื่อผู้มีจิตใจที่อยู่ที่นั่น")


# ---------------------------------------------------------------- งานที่ 3: เรื่องเล่าต้องจบที่ผลจริง
def sample_entry(sim, cid, outcome="ออกเดินทาง", action="เดินทาง"):
    return {"id": "d-1", "seq": 1, "day": sim.day, "year": sim.day // 365, "cid": cid,
            "name": sim.cast[cid].name, "place": "หุบเขาหมอกลวงตา (แหล่งวัตถุดิบ)", "action": action,
            "target": "", "dest": "ถ้ำหินแกรนิตดิบ (แหล่งวัตถุดิบ)" if action == "เดินทาง" else "",
            "why": "หาวัตถุดิบ", "thought": "ข้าต้องไป", "emotion": "คาดหวัง", "long_goal": "",
            "outcome": outcome, "text": "ออกเดินทางแล้ว", "details": {}, "side": []}


class TestFix3Story(Base):
    def test_prompt_rules(self):
        cid = self.mind.active()[0].cid
        _, user = ST.build(self.sim, sample_entry(self.sim, cid))
        self.assertIn("ยังไม่ถึงที่หมาย", user)
        self.assertIn("ห้ามเล่าเหตุการณ์ที่เกิดหลังจากผลนี้", user)
        self.assertIn("ข้า/เจ้า", user)
        self.assertNotIn("ใช้ความคิดในใจแทนบทสนทนา", user)
        _, user2 = ST.build(self.sim, sample_entry(self.sim, cid, outcome="สำเร็จ", action="บำเพ็ญ"))
        self.assertNotIn("ยังไม่ถึงที่หมาย", user2)
        self.assertIn("ห้ามเล่าเหตุการณ์ที่เกิดหลังจากผลนี้", user2)

    def test_clean_story(self):
        raw = ("เฉินเจี้ยนตัดสินใจเดินลึกเข้าไปในป่า เขาใช้ความคิดในใจแทนบทสนทนา ก้าวไปข้างหน้า\n"
               "\"ถ้าฉันไปแล้วไม่พบอะไร ฉันจะเสียเวลา\" เขาคิด\n"
               "เขามีฉันทะแรงกล้า\n"
               "[ให้เขียน] ฉากสั้นยาว 3-6 ย่อหน้า")
        out = ST.clean_story(raw)
        self.assertNotIn("ใช้ความคิดในใจแทนบทสนทนา", out)
        self.assertNotIn("[ให้เขียน]", out)
        self.assertIn("เดินลึกเข้าไปในป่า", out)
        self.assertIn("ก้าวไปข้างหน้า", out)
        self.assertIn("ถ้าข้าไปแล้วไม่พบอะไร ข้าจะเสียเวลา", out)
        self.assertIn("ฉันทะ", out, "คำว่า ฉันทะ ต้องไม่ถูกเปลี่ยน")
        for phrase in MC.STORY_LEAK_PHRASES:
            self.assertNotIn(phrase, out)


class LeakyThinker(B.MockThinker):
    def write(self, system, user):
        return "ฉันจะไปให้ถึง [ให้เขียน] แล้วเขาก็เดินต่อ"


class TestFix3Runner(unittest.TestCase):
    def test_runner_cleans_before_saving(self):
        tmp = tempfile.mkdtemp()
        try:
            cfg = RunConfig(out_dir=tmp, seed=9, capacity=20, story=True, max_years=4)
            MindRunner().configure(cfg, LeakyThinker()).run_blocking()
            stories = [e["story"] for e in read_journal(cfg.journal_path, limit=100000) if e.get("story")]
            self.assertTrue(stories, "ไม่มีเรื่องเล่าให้ตรวจ")
            for s in stories:
                self.assertNotIn("[ให้เขียน]", s)
                self.assertNotIn("ฉัน", s)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
