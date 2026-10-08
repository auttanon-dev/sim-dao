# -*- coding: utf-8 -*-
"""คำตอบผิดรูปแบบจากโมเดลต้องไม่ล้มการรัน และ cid ที่ไม่มีอยู่ต้องไม่ทำให้หน้าเว็บได้ 500

    python -m unittest test_minds_malformed -v

บั๊กที่ไฟล์นี้ล็อกไว้
--------------------
1. `prompt.parse` วน `data["feelings"]` ตรงๆ — โมเดลตอบ `"feelings": 0` หรือ `true` แล้ว TypeError
   หลุดออกจาก `Sim.step()` ทั้งรันหยุดที่สถานะ error (ส่วน `think_json` ล้มถูกจับไว้แล้ว แต่ parse ไม่ถูกจับ)
2. `thought`/`short_goal` ที่ไม่ใช่ข้อความถูก `str()` ตรงๆ ได้ "5" หรือ "{...}" ไปเป็นความคิดของตัวละคร
3. `studio.outline` ใช้ `cast[cid]` โดยไม่ตรวจ — cid เกินได้ IndexError, cid ติดลบได้ชื่อคนอื่น
"""
import contextlib
import io
import os
import random
import shutil
import tempfile
import unittest

from tiandao import events as E
from tiandao import intent as IN
from tiandao import persist as PS
from tiandao.mind import backend as B
from tiandao.mind import prompt as PR
from tiandao.mind.runner import MindRunner, RunConfig, open_world

JUNK = [None, 0, 5, -1, 3.7, True, False, "", "P1", "P99", [], [1, 2], ["P1"], {}, {"a": 1}, [None], [[]]]


class ParseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cfg = RunConfig(out_dir=cls.tmp, seed=3, capacity=12, story=False)
        cls.sim = open_world(cfg, B.MockThinker(), journal=False)
        # หาผู้มีจิตใจที่มีคนรอบตัว เพื่อให้รหัส P1 ชี้ถึงคนจริง
        for mind in cls.sim.mind.active():
            ch = cls.sim.cast[mind.cid]
            others = cls.sim.social_pool(ch, cls.sim.world(ch.world_id), random.Random(0))
            w = IN.weigh(ch, cls.sim, E.EVENT_TABLE, bool(others), others=others)
            cls.ctx = PR.build(cls.sim, mind, ch, w, others, E.EVENT_TABLE, True)
            if cls.ctx.people and cls.ctx.menu:
                break
        cls.good = B.MockThinker().think_json(cls.ctx.system, cls.ctx.user)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def parse(self, **override):
        return PR.parse(dict(self.good, **override), self.ctx, self.sim, E.EVENT_TABLE)

    def test_the_fixture_has_someone_to_feel_about(self):
        self.assertTrue(self.ctx.people and self.ctx.menu)

    def test_any_junk_in_any_field_never_raises(self):
        for key in ("thought", "emotion", "short_goal", "long_goal", "plan", "feelings"):
            for junk in JUNK:
                with self.subTest(key=key, junk=junk):
                    info, steps = self.parse(**{key: junk})
                    self.assertIsInstance(info, dict)
                    self.assertIsInstance(steps, list)

    def test_junk_inside_plan_steps_and_feelings_never_raises(self):
        for junk in JUNK:
            with self.subTest(junk=junk):
                self.parse(plan=[{"action": junk, "target": junk, "place": junk, "why": junk}],
                           feelings=[{"person": junk, "feeling": junk}, junk])

    def test_non_text_thought_does_not_become_a_thought(self):
        for junk in (5, True, {"a": 1}, 3.7):
            with self.subTest(junk=junk):
                self.assertEqual(self.parse(thought=junk)[0]["thought"], "")

    def test_a_list_of_sentences_is_joined(self):
        self.assertEqual(self.parse(thought=["ข้าลังเล", "แต่ต้องไป"])[0]["thought"], "ข้าลังเล แต่ต้องไป")

    def test_feelings_given_as_a_single_object_or_a_map_are_still_read(self):
        cid = self.ctx.people[0][1].cid
        one = self.parse(feelings={"person": "P1", "feeling": "ไว้ใจได้"})[0]["feelings"]
        self.assertEqual(one, {cid: "ไว้ใจได้"})
        mapped = self.parse(feelings={"P1": "ยังระแวง"})[0]["feelings"]
        self.assertEqual(mapped, {cid: "ยังระแวง"})

    def test_a_non_text_feeling_is_dropped(self):
        self.assertEqual(self.parse(feelings=[{"person": "P1", "feeling": 7}])[0]["feelings"], {})


class _Chaos(B.MockThinker):
    """โมเดลที่ตอบ JSON ถูกไวยากรณ์แต่ผิดชนิดข้อมูลแบบสุ่ม (คงที่ตาม seed)"""

    def __init__(self):
        self.rng = random.Random(11)

    def think_json(self, system, user):
        data = super().think_json(system, user)
        for key in list(data):
            if self.rng.random() < 0.5:
                data[key] = self.rng.choice(JUNK)
        return data


class WholeRunTests(unittest.TestCase):
    def test_a_world_keeps_walking_under_a_model_that_answers_the_wrong_types(self):
        tmp = tempfile.mkdtemp()
        try:
            cfg = RunConfig(out_dir=tmp, seed=2, capacity=40, story=False, max_years=1)
            runner = MindRunner().configure(cfg, _Chaos())
            with contextlib.redirect_stderr(io.StringIO()):
                runner.run_blocking()
            self.assertEqual(runner.state, "idle", runner.error)
            self.assertGreaterEqual(runner.sim.day // 365, 1)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class OutlineTests(unittest.TestCase):
    def test_an_unknown_or_negative_cid_is_refused_not_misread(self):
        from narrative_factory import studio as STUDIO
        from tiandao import sim as S
        tmp = tempfile.mkdtemp()
        try:
            path = os.path.join(tmp, "world.save")
            with contextlib.redirect_stdout(io.StringIO()):
                sim = S.Sim(seed=7)
                sim.run(200)
            PS.save_sim(sim, path)
            for cid in (len(sim.cast), 10 ** 8, -1):
                with self.subTest(cid=cid), self.assertRaises(LookupError):
                    STUDIO.outline(path, cid)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
