# -*- coding: utf-8 -*-
import json
import os
import shutil
import tempfile
import unittest

from tiandao.mind import backend as B
from tiandao.mind.novel import MindNovelJob
from tiandao.mind.runner import RunConfig, open_world


class _Writer:
    def write(self, _system, user):
        return "ตัวละครก้าวผ่านเหตุการณ์ตามบันทึกจริง\n\n" + user.split("[บันทึกจริง")[0][-120:]


class MindControlTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.cfg = RunConfig(out_dir=self.tmp, seed=3, capacity=9, story=False)
        self.sim = open_world(self.cfg, B.MockThinker())

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_capacity_can_shrink_and_grow_without_deleting_mind_history(self):
        mm = self.sim.mind
        original = set(mm.minds)
        self.assertEqual(mm.set_capacity(self.sim, 3), 3)
        self.assertEqual(len(mm.active()), 3)
        self.assertTrue(original.issubset(mm.minds), "ลดจำนวนต้องพัก component ไม่ใช่ลบประวัติ")
        self.assertEqual(mm.set_capacity(self.sim, 7), 7)
        self.assertEqual(len(mm.active()), 7)

    def test_selected_character_can_be_written_to_incremental_novel(self):
        mm = self.sim.mind
        mind = mm.active()[0]
        entry = {"type": "decision", "id": "d-1", "seq": 1, "day": 1, "year": 0,
                 "cid": mind.cid, "name": mind.name, "action": "ฝึกวิชา", "outcome": "สำเร็จ",
                 "text": f"{mind.name}ฝึกวิชาสำเร็จ", "why": "อยากแข็งแกร่ง", "thought": "ข้าต้องฝึก"}
        mm._journal(entry)
        job = MindNovelJob()
        status = job.start(self.sim, self.cfg.journal_path, mind.cid, _Writer(), self.tmp, chapters=3)
        self.assertEqual(status["cid"], mind.cid)
        job._thread.join(5)
        self.assertEqual(job.state, "complete", job.error)
        self.assertTrue(os.path.exists(job.out_path))
        with open(job.out_path, encoding="utf-8") as stream:
            text = stream.read()
        self.assertIn(f"# ชีวิตของ{mind.name}", text)
        self.assertIn("## บทที่ 1", text)


if __name__ == "__main__":
    unittest.main()
