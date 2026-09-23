# -*- coding: utf-8 -*-
"""ให้ผู้มีจิตใจได้เจอกันแล้วมีบทสนทนาจริง

    python -m unittest test_minds_social -v
"""
import shutil
import tempfile
import unittest

from tiandao import events as E
from tiandao import intent as IN
from tiandao.models import Event
from tiandao.mind import backend as B
from tiandao.mind import config as MC
from tiandao.mind import prompt as PR
from tiandao.mind import storyteller as ST
from tiandao.mind.manager import Pending
from tiandao.mind.runner import RunConfig, open_world


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.sim = open_world(RunConfig(out_dir=self.tmp, seed=3, capacity=10, story=False), B.MockThinker())
        self.mm = self.sim.mind
        self.a, self.b = self.mm.active()[0], self.mm.active()[1]
        self.ca, self.cb = self.sim.cast[self.a.cid], self.sim.cast[self.b.cid]
        self.cb.world_id, self.cb.place, self.cb.travel_dest = self.ca.world_id, self.ca.place, -1

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def ctx(self):
        others = [c for c in self.sim.living()
                  if c.world_id == self.ca.world_id and c.cid != self.ca.cid and c.age(self.sim.day) >= 16][:10]
        w = IN.weigh(self.ca, self.sim, E.EVENT_TABLE, True, others=others)
        for k in MC.SOCIAL_KINDS:
            w[k] = max(w.get(k, 0), 1.0)
        return PR.build(self.sim, self.a, self.ca, w, others, E.EVENT_TABLE, False)


class TestFacing(Base):
    def test_co_located_mind_is_shown_and_social_actions_offered(self):
        ctx = self.ctx()
        self.assertIn("[คนที่ยืนอยู่ตรงหน้าข้าเดี๋ยวนี้]", ctx.user)
        self.assertIn(self.cb.name, ctx.user)
        self.assertTrue(set(MC.SOCIAL_KINDS) & set(ctx.menu), "ต้องมีทางเลือกที่ทำต่อกันได้ในเมนู")

    def test_nobody_facing_when_far_away(self):
        for m in self.mm.active()[1:]:
            self.sim.cast[m.cid].place = (self.ca.place + 5) % 20
        self.assertEqual(PR.facing_minds(self.sim, self.ca), [])
        self.assertNotIn("[คนที่ยืนอยู่ตรงหน้าข้าเดี๋ยวนี้]", self.ctx().user)

    def test_travelling_mind_is_not_facing(self):
        self.cb.travel_dest = (self.ca.place + 3) % 20
        self.assertNotIn(self.cb, PR.facing_minds(self.sim, self.ca))


class TestMotiveReachesTheOther(Base):
    def _act(self, kind="ให้สัญญา", why="อยากมีพันธมิตรไว้พึ่ง", tags=("สัญญา",)):
        step = PR.Step(kind=kind, why=why)
        step.target_cid, step.target_name = self.cb.cid, self.cb.name
        self.mm._pending[self.ca.cid] = Pending(source="คิดใหม่", step=step)
        ev = Event(seq=10**9, day=self.sim.day, gap_days=0, world_id=0, era=1, kind=kind,
                   actor=self.ca.cid, target=self.cb.cid, tags=list(tags), outcome="ผูกพัน",
                   text=f"{self.ca.name}ให้สัญญากับ{self.cb.name}")
        self.b.interrupted = False
        self.mm.on_event(ev, self.sim)
        return ev

    def test_other_side_learns_the_reason_and_rethinks(self):
        self._act()
        self.assertTrue(any("อยากมีพันธมิตรไว้พึ่ง" in t for t in self.b.inbox),
                        "อีกฝ่ายต้องรู้ว่าเขาทำเพราะอะไร")
        self.assertTrue(self.b.interrupted, "ผู้มีจิตใจมาหาเรา ควรได้คิดว่าจะตอบอย่างไร")

    def test_stranger_action_does_not_carry_a_reason(self):
        stranger = next(c for c in self.sim.living() if c.cid not in self.mm.minds)
        ev = Event(seq=10**9 + 1, day=self.sim.day, gap_days=0, world_id=0, era=1, kind="ให้สัญญา",
                   actor=stranger.cid, target=self.cb.cid, tags=["สัญญา"], outcome="ผูกพัน", text="ให้สัญญา")
        self.b.inbox = []
        self.mm.on_event(ev, self.sim)
        self.assertTrue(self.b.inbox)
        self.assertNotIn("เขาบอกว่า", self.b.inbox[-1])


class TestTwoMindScene(Base):
    def test_story_prompt_carries_both_sides(self):
        self.b.long_goal = "ขึ้นเป็นเจ้าสำนักให้ได้"
        self.b.emotion = "ระแวง"
        entry = {"id": "d-1", "seq": 1, "day": self.sim.day, "year": self.sim.day // 365, "cid": self.ca.cid,
                 "name": self.ca.name, "place": "ลานฝึก", "action": "ให้สัญญา", "target": self.cb.name,
                 "target_cid": self.cb.cid, "dest": "", "why": "อยากมีพันธมิตร", "thought": "ข้าต้องมีพวก",
                 "emotion": "คาดหวัง", "long_goal": "เป็นยอดฝีมือ", "outcome": "ผูกพัน",
                 "text": "ให้สัญญากัน", "details": {}, "side": [], "alive": True}
        _, user = ST.build(self.sim, entry)
        self.assertIn("[ใจของอีกฝ่าย]", user)
        self.assertIn("ขึ้นเป็นเจ้าสำนักให้ได้", user)
        self.assertIn("ระแวง", user)
        self.assertIn("อย่างน้อยสามรอบ", user)
        self.assertIn("ปฏิเสธ", user)

    def test_scene_with_a_plain_person_stays_simple(self):
        stranger = next(c for c in self.sim.living() if c.cid not in self.mm.minds)
        entry = {"id": "d-2", "seq": 2, "day": self.sim.day, "year": 0, "cid": self.ca.cid, "name": self.ca.name,
                 "place": "ลานฝึก", "action": "ประลอง", "target": stranger.name, "target_cid": stranger.cid,
                 "dest": "", "why": "ลองฝีมือ", "thought": "", "emotion": "", "long_goal": "",
                 "outcome": "ชนะ", "text": "ชนะการประลอง", "details": {}, "side": [], "alive": True}
        _, user = ST.build(self.sim, entry)
        self.assertNotIn("[ใจของอีกฝ่าย]", user)
        self.assertIn("มีบทสนทนาโต้ตอบ", user)


if __name__ == "__main__":
    unittest.main()
