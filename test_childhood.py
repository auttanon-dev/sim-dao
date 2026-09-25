# -*- coding: utf-8 -*-
"""วัยเด็กต้องเป็นช่วงชีวิตจริง ไม่ใช่ผู้ใหญ่ตัวเล็ก และต้องตามไปถึงชีวประวัติ."""
import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from tiandao import events as E
from tiandao import sim as S
from tiandao.mind import prompt as PR
from tiandao.mind.manager import Mind, MindManager
from tiandao.mind.runner import read_journal
from tiandao.mind import storyteller as ST


def quiet(fn, *args, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*args, **kwargs)


class ChildhoodTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sim = quiet(S.Sim, seed=81, tiers=1)

    def test_child_turn_is_growth_not_an_adult_action(self):
        sim = self.sim
        father, mother = sim.cast[0], sim.cast[1]
        child = sim.spawn(sim.worlds[0], age_years=0)
        child.parents = [father.cid, mother.cid]
        before_skills = list(child.skills)
        sim.day = child.born_day
        event = sim._childhood_turn(child, sim.worlds[0], 0, sim.rng)
        self.assertEqual(event.kind, "เติบโต")
        self.assertEqual(event.outcome, "ได้รับการเลี้ยงดู")
        self.assertEqual(child.skills, before_skills)
        self.assertEqual(child.childhood[0]["age"], 0)

    def test_adopted_character_backfills_birth_and_childhood(self):
        sim = self.sim
        child = sim.spawn(sim.worlds[0], age_years=0)
        child.parents = [sim.cast[2].cid, sim.cast[3].cid]
        sim.day = child.born_day
        sim._childhood_turn(child, sim.worlds[0], 0, sim.rng)
        sim.day = child.born_day + 14 * 365
        with tempfile.TemporaryDirectory() as folder:
            path = str(Path(folder) / "journal.jsonl")
            manager = MindManager(capacity=1)
            manager.journal_path = path
            manager._adopt(sim, child, "")
            entries = list(reversed(read_journal(path, cid=child.cid, limit=100)))
        self.assertEqual(entries[0]["type"], "birth")
        self.assertTrue(any(e["type"] == "childhood" for e in entries))
        self.assertEqual(entries[-1]["type"], "join")

    def test_attach_migrates_an_existing_mind_once(self):
        sim = quiet(S.Sim, seed=82, tiers=1)
        child = sim.spawn(sim.worlds[0], age_years=14)
        child.parents = [sim.cast[0].cid, sim.cast[1].cid]
        manager = MindManager(capacity=1)
        manager.minds[child.cid] = Mind(child.cid, child.name, sim.day)
        with tempfile.TemporaryDirectory() as folder:
            path = str(Path(folder) / "journal.jsonl")
            manager.attach(sim, journal_path=path)
            first = read_journal(path, cid=child.cid, limit=100)
            manager.attach(sim, journal_path=path)
            second = read_journal(path, cid=child.cid, limit=100)
        self.assertTrue(manager.minds[child.cid].history_backfilled)
        self.assertEqual(sum(e["type"] == "birth" for e in first), 1)
        self.assertEqual(sum(e["type"] == "birth" for e in second), 1)

    def test_parent_realm_bonus_is_applied_once(self):
        sim = self.sim
        adults = [c for c in sim.living_in(0) if c.age(sim.day) >= 16]
        father = next(c for c in adults if c.gender == "ชาย")
        mother = next(c for c in adults if c.gender == "หญิง")
        father.realm, mother.realm = 3, 4
        before = len(sim.cast)
        outcome, _text, _details = sim.resolve(
            {"kind": "กำเนิดทายาท", "tgt": True}, father, mother,
            sim.worlds[0], 0, sim.rng)
        self.assertEqual(outcome, "กำเนิด")
        child = sim.cast[before]
        self.assertEqual(child.insight, 14.0)
        self.assertEqual(child.refine, 14.0)


class MindOutputGuardsTests(unittest.TestCase):
    def test_teaching_requires_a_real_teachable_skill_and_correct_direction(self):
        manager = MindManager(capacity=1)
        actor = SimpleNamespace(cid=1, skills=["วิชาหนึ่ง"], mastery={"วิชาหนึ่ง": 99}, bonds={})
        target = SimpleNamespace(cid=2, skills=[], mastery={}, bonds={})
        weights = {"ถ่ายทอดวิชา": 10.0}
        good = PR.Step("ถ่ายทอดวิชา", target_cid=2, why="อยากสอนวิชาให้เขา")
        backwards = PR.Step("ถ่ายทอดวิชา", target_cid=2, why="อยากได้วิชาจากเขา")
        self.assertTrue(manager._step_ok(good, actor, weights, [target], E.EVENT_TABLE))
        self.assertFalse(manager._step_ok(backwards, actor, weights, [target], E.EVENT_TABLE))
        target.skills.append("วิชาหนึ่ง")
        self.assertFalse(manager._step_ok(good, actor, weights, [target], E.EVENT_TABLE))

    def test_schema_placeholders_are_not_memories(self):
        class Ctx:
            menu = []
            people = []
            destinations = []
            scars = []
        info, _ = PR.parse({
            "thought": "ความคิดในใจของข้าตอนนี้ 2-4 ประโยค บอกว่าข้ารู้สึกและชั่งใจอะไร",
            "short_goal": "สิ่งที่ข้าตั้งใจทำให้ได้ในช่วงนี้ 1 ประโยค",
        }, Ctx(), None, E.EVENT_TABLE)
        self.assertEqual(info["thought"], "")
        self.assertEqual(info["short_goal"], "")

    def test_story_validator_catches_reversed_winner(self):
        entry = {"name": "จ้าวซาน", "target": "ฉินเฉิน", "action": "ประลอง",
                 "text": "จ้าวซานประลองกับฉินเฉิน — ฉินเฉินเป็นฝ่ายพ่าย",
                 "alive": True, "target_alive_after": True}
        wrong = "ฉินเฉินต่อสู้กลับอย่างไม่ย่อท้อ ในที่สุดฉินเฉินเอาชนะจ้าวซาน จ้าวซานเป็นฝ่ายพ่ายแพ้"
        right = "ทั้งคู่แลกกระบวนท่า ก่อนฉินเฉินเป็นฝ่ายพ่ายแพ้และยอมรับผลการประลอง"
        self.assertTrue(ST.validate_facts(entry, wrong))
        self.assertEqual(ST.validate_facts(entry, right), [])


if __name__ == "__main__":
    unittest.main()
