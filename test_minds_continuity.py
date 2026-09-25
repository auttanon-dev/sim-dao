# -*- coding: utf-8 -*-
import shutil
import tempfile
import unittest

from tiandao.models import Event
from tiandao.mind import backend as B
from tiandao.mind import prompt as PR
from tiandao.mind import storyteller as ST
from tiandao.mind.manager import Pending
from tiandao.mind.runner import RunConfig, open_world


class MindContinuityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.sim = open_world(RunConfig(out_dir=self.tmp, seed=3, capacity=9, story=False),
                              B.MockThinker())
        self.mm = self.sim.mind
        self.mind = self.mm.active()[0]
        self.actor = self.sim.cast[self.mind.cid]
        self.target = next(c for c in self.sim.living() if c.cid not in self.mm.minds)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _dead_target_event(self):
        step = PR.Step(kind="ล้างแค้น", target_cid=self.target.cid,
                       target_name=self.target.name, why="ให้เขาชดใช้")
        self.mm._pending[self.actor.cid] = Pending(source="คิดใหม่", step=step)
        self.target.alive = False
        return Event(seq=10**9, day=self.sim.day, gap_days=0, world_id=self.actor.world_id,
                     era=1, kind="ล้างแค้น", actor=self.actor.cid, target=self.target.cid,
                     tags=["ต่อสู้", "ความตาย"], outcome="ตาย",
                     text=f"{self.actor.name}ล้างแค้นกับ{self.target.name} — {self.target.name}ดับดิ้น")

    def test_dead_revenge_target_retires_goal_and_plan(self):
        self.mind.long_goal = f"ล้างแค้น{self.target.name}ให้สำนึกผิด"
        self.mind.short_goal = f"ตามหา{self.target.name}"
        self.mind.plan = [{"kind": "ล้างแค้น", "target_cid": self.target.cid,
                           "target_name": self.target.name}]
        ev = self._dead_target_event()
        self.mm.after_action(self.actor, self.sim, "ล้างแค้น", self.target, ev)

        self.assertEqual(self.mind.long_goal, "")
        self.assertEqual(self.mind.short_goal, "")
        self.assertEqual(self.mind.plan, [])
        self.assertTrue(self.mind.goal_stale)
        self.assertTrue(self.mind.interrupted)
        self.assertTrue(any("ตายแล้ว" in text for text in self.mind.memories))

    def test_death_story_prompt_locks_timeline_and_survivors(self):
        ev = self._dead_target_event()
        self.mm.after_action(self.actor, self.sim, "ล้างแค้น", self.target, ev)
        entry = next(e for e in self.mm.story_queue if e.get("id") == f"d-{ev.seq}")
        system, user = ST.build(self.sim, entry)

        self.assertIn("ลำดับเวลาเป็นกฎบังคับ", system)
        self.assertIn(f"ตอนเปิดฉาก {self.target.name}ยังมีชีวิต", user)
        self.assertIn(f"หลังผลลัพธ์ {self.actor.name}: ยังมีชีวิต", user)
        self.assertIn(f"หลังผลลัพธ์ {self.target.name}: เสียชีวิต", user)
        self.assertIn("ห้ามอ้างว่าคนใดเคยตายหรือถูกฆ่าก่อนฉากนี้", user)

    def test_attach_repairs_old_save_pointing_at_dead_scar_target(self):
        self.target.alive = False
        self.mind.scars = [{"cid": self.target.cid, "name": self.target.name,
                            "year": 1, "outcome": "หักหลัง", "times": 1}]
        self.mind.short_goal = f"ล้างแค้น{self.target.name}ก่อน"
        self.mind.plan = [{"kind": "ล้างแค้น", "target_cid": self.target.cid,
                           "target_name": self.target.name}]
        self.mind.goal_stale = False
        self.mind.interrupted = False

        self.mm.attach(self.sim)

        self.assertEqual(self.mind.short_goal, "")
        self.assertEqual(self.mind.plan, [])
        self.assertTrue(self.mind.goal_stale)
        self.assertTrue(self.mind.interrupted)
        self.assertEqual(len(self.mind.scars), 1, "scar เป็นประวัติศาสตร์จึงต้องเก็บไว้")

    def test_third_party_death_retires_help_plan(self):
        self.mind.short_goal = f"ช่วย{self.target.name}ฝึกวิชาให้ได้"
        self.mind.plan = [{"kind": "ถ่ายทอดวิชา", "target_cid": self.target.cid,
                           "target_name": self.target.name}]
        killer = next(c for c in self.sim.living()
                      if c.cid not in self.mm.minds and c.cid != self.target.cid)
        self.target.alive = False
        ev = Event(seq=10**9 + 1, day=self.sim.day, gap_days=0,
                   world_id=self.target.world_id, era=1, kind="ลอบสังหาร",
                   actor=killer.cid, target=self.target.cid, tags=["ความตาย"],
                   outcome="ตาย", text=f"{killer.name}สังหาร{self.target.name}")
        self.mm.on_event(ev, self.sim)
        self.assertEqual(self.mind.short_goal, "")
        self.assertEqual(self.mind.plan, [])
        self.assertTrue(self.mind.interrupted)


if __name__ == "__main__":
    unittest.main()
