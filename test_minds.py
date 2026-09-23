# -*- coding: utf-8 -*-
"""เทสต์ชั้นจิตใจ (tiandao/mind) — ไม่ต้องเปิด Ollama ใช้ MockThinker/ตัวปลอมแทนทั้งหมด

    python -m unittest test_minds -v
"""
import contextlib
import hashlib
import io
import json
import os
import shutil
import tempfile
import unittest

from tiandao import events as E
from tiandao import intent as IN
from tiandao import sim as S
from tiandao.mind import backend as B
from tiandao.mind import prompt as PR
from tiandao.mind.manager import MindManager, trim_journal
from tiandao.mind.runner import MindRunner, RunConfig, open_world, read_journal


def quiet(fn, *a, **kw):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*a, **kw)


def digest(sim):
    h = hashlib.sha256()
    for e in sim.log:
        h.update(f"{e.seq}|{e.day}|{e.kind}|{e.outcome}|{e.actor}|{e.target}|{e.text}".encode())
    return h.hexdigest()


class ScriptedThinker(B.MockThinker):
    """ตอบตามสคริปต์ที่กำหนด เพื่อทดสอบว่าเอนจินทำตามที่จิตใจเลือกจริง"""
    def __init__(self, fn):
        self.fn = fn
        self.calls = 0

    def think_json(self, system, user):
        self.calls += 1
        return self.fn(user)


class BrokenThinker(B.MockThinker):
    def think_json(self, system, user):
        raise B.ThinkError("ติดต่อโมเดลไม่ได้ (จำลอง)")


class TestNoMindNoChange(unittest.TestCase):
    def test_manager_without_minds_keeps_world_identical(self):
        a = quiet(S.Sim, seed=7, tiers=3)
        b = quiet(S.Sim, seed=7, tiers=3)
        b.mind = MindManager(capacity=0)
        b.event_bus.subscribe(b.mind.on_event)
        quiet(a.run, 6000)
        quiet(b.run, 6000)
        self.assertEqual(digest(a), digest(b))


class TestParse(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.sim = open_world(RunConfig(out_dir=cls.tmp, seed=4, capacity=12), B.MockThinker())
        cls.mind = cls.sim.mind.active()[0]
        cls.ch = cls.sim.cast[cls.mind.cid]
        others = [c for c in cls.sim.living()
                  if c.world_id == cls.ch.world_id and c.cid != cls.ch.cid and c.age(cls.sim.day) >= 16][:10]
        w = IN.weigh(cls.ch, cls.sim, E.EVENT_TABLE, True, others=others)
        w["ประลอง"] = 1000.0
        w["เดินทาง"] = 900.0
        cls.ctx = PR.build(cls.sim, cls.mind, cls.ch, w, others, E.EVENT_TABLE, True)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_codes_names_and_noise(self):
        p2 = self.ctx.people[1][1]
        data = {"thought": "ข้าต้องลองฝีมือ", "emotion": "โกรธแค้นมาก",
                "plan": [{"action": "บินขึ้นสวรรค์", "target": ""},              # ไม่มีในเมนู -> ข้าม
                         {"action": " ประลอง (ท้าดวล)", "target": "P 2"},        # รหัสมีช่องว่าง
                         {"action": "เดินทาง", "place": "ไป D1 เลย"},
                         {"action": "ให้สัญญา", "target": p2.name}]}             # ใช้ชื่อแทนรหัส
        info, steps = PR.parse(data, self.ctx, self.sim, E.EVENT_TABLE)
        self.assertEqual(info["emotion"], "โกรธแค้น")
        self.assertEqual([s.kind for s in steps], ["ประลอง", "เดินทาง", "ให้สัญญา"])
        self.assertEqual(steps[0].target_cid, p2.cid)
        self.assertEqual(steps[1].place, self.ctx.destinations[0][1])
        self.assertEqual(steps[2].target_cid, p2.cid)

    def test_targeted_without_person_is_dropped(self):
        _, steps = PR.parse({"plan": [{"action": "ประลอง", "target": "P99"}]},
                            self.ctx, self.sim, E.EVENT_TABLE)
        self.assertEqual(steps, [])

    def test_lenient_json_from_model_text(self):
        from tiandao.ai.llm_agent import loads_lenient
        raw = '<think>hmm</think>\n```json\n{"thought": "ไปเถอะ", "plan": [{"action": "บำเพ็ญ",},],}\n```'
        data = loads_lenient(raw)
        self.assertEqual(data["plan"][0]["action"], "บำเพ็ญ")


class TestRun(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_mock_world_runs_and_resumes(self):
        cfg = RunConfig(out_dir=self.tmp, seed=9, capacity=20, story=True, max_years=4)
        r = MindRunner().configure(cfg, B.MockThinker())
        r.run_blocking()
        sim = r.sim
        self.assertGreater(sim.mind.stats["thinks"], 20)
        entries = read_journal(cfg.journal_path, limit=100000)
        decisions = [e for e in entries if e["type"] == "decision"]
        self.assertTrue(decisions)
        # การตัดสินใจทุกครั้งผูกกับเหตุการณ์จริงของโลก — ชนิดและคู่กรณีต้องตรงกับ log
        by_seq = {e.seq: e for e in sim.log}
        checked = 0
        for d in decisions:
            ev = by_seq.get(d["seq"])
            if ev is None:
                continue          # log ถูกตัดไปแล้ว
            checked += 1
            self.assertEqual(ev.kind, d["action"])
            self.assertEqual(ev.actor, d["cid"])
            if d["target_cid"] is not None:
                self.assertEqual(ev.target, d["target_cid"])
        self.assertGreater(checked, 0)
        self.assertTrue(any(e.get("story") for e in decisions))
        # เซฟแล้วเปิดใหม่: จิตใจยังอยู่ ไม่สมัคร event bus ซ้ำ
        seq = sim.seq
        again = open_world(cfg, B.MockThinker())
        self.assertEqual(again.seq, seq)
        self.assertEqual(len(again.mind.minds), len(sim.mind.minds))
        subs = [h for h in again.event_bus._subscribers if getattr(h, "__self__", None) is again.mind]
        self.assertEqual(len(subs), 1)

    def test_mind_choice_drives_engine(self):
        """สคริปต์ให้เดินทางไปจุดหมายลำดับที่ 3 — เอนจินต้องพาไปที่นั่นจริง และไม่ทำอย่างอื่นที่ไม่ได้เลือก"""
        chosen = {}

        def script(user):
            if "- D3:" in user and "- เดินทาง:" in user:
                line = next(l for l in user.splitlines() if l.startswith("- D3:"))
                chosen[line] = True
                return {"thought": "ข้าจะไปไกล", "plan": [{"action": "เดินทาง", "place": "D3", "why": "อยากเห็นโลก"}]}
            return {"thought": "พักก่อน", "plan": [{"action": "บำเพ็ญ", "why": "สะสมพลัง"}]}
        cfg = RunConfig(out_dir=self.tmp, seed=2, capacity=15, story=False, max_years=3)
        r = MindRunner().configure(cfg, ScriptedThinker(script))
        r.run_blocking()
        journal = read_journal(cfg.journal_path, limit=100000)
        trips = [e for e in journal if e["type"] == "decision" and e["action"] == "เดินทาง"
                 and e["source"] == "คิดใหม่" and e["outcome"] == "ออกเดินทาง"]
        self.assertTrue(trips, "ไม่มีใครได้เลือกเดินทางเลย")
        offered = " ".join(chosen)
        for t in trips:
            self.assertTrue(t["dest"] and t["dest"].split(" (")[0] in offered)
        acts = {e["action"] for e in journal if e["type"] == "decision" and e["source"] == "คิดใหม่"}
        self.assertLessEqual(acts, {"เดินทาง", "บำเพ็ญ"})

    def test_broken_model_falls_back_to_instinct(self):
        cfg = RunConfig(out_dir=self.tmp, seed=3, capacity=10, story=False, max_years=1)
        r = MindRunner().configure(cfg, BrokenThinker())
        r.run_blocking()
        self.assertGreater(r.sim.mind.stats["instinct"], 0)
        self.assertEqual(r.sim.mind.stats["thinks"], 0)
        inst = [e for e in read_journal(cfg.journal_path, limit=1000) if e.get("source") == "สัญชาตญาณ"]
        self.assertTrue(inst and "ติดต่อโมเดลไม่ได้" in inst[0]["error"])

    def test_dead_minds_are_replaced(self):
        cfg = RunConfig(out_dir=self.tmp, seed=6, capacity=25, story=False, max_years=12)
        r = MindRunner().configure(cfg, B.MockThinker())
        r.run_blocking()
        m = r.sim.mind
        dead = [x for x in m.minds.values() if not x.alive]
        self.assertTrue(dead, "12 ปีแล้วยังไม่มีใครตาย — ทดสอบการแทนที่ไม่ได้")
        self.assertGreaterEqual(len(m.active()), cfg.capacity - 2)

    def test_trim_future_journal(self):
        path = os.path.join(self.tmp, "j.jsonl")
        with open(path, "w", encoding="utf-8") as f:
            for seq in (5, 10, 15):
                f.write(json.dumps({"id": str(seq), "seq": seq}) + "\n")
        self.assertEqual(trim_journal(path, 10), 1)
        with open(path, encoding="utf-8") as f:
            self.assertEqual([json.loads(line)["seq"] for line in f], [5, 10])


if __name__ == "__main__":
    unittest.main()
