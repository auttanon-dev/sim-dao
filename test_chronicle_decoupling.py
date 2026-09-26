# -*- coding: utf-8 -*-
"""โลกจาก seed เดียวกันต้องเหมือนกันไม่ว่า tiandao/chronicle.json จะมีอะไร (แบบ §12.4)

    python -m unittest test_chronicle_decoupling -v

chronicle.json เป็นไฟล์ที่ git ไม่เก็บ และ run.py เขียนใหม่ทุกครั้งที่จบรัน ตำนานในไฟล์จึงเป็นได้แค่ถ้อยคำของ
ข่าวลือตำนานยุคก่อน ห้ามเปลี่ยน RNG ของโลก จำนวนข่าวลือ หรือเหตุการณ์ใดๆ
"""
import contextlib
import hashlib
import io
import os
import subprocess
import sys
import unittest
from unittest import mock

from tiandao import chronicle as CH
from tiandao import config as C
from tiandao import sim as S

SEED = 7
STEPS = 3000


def legend(i):
    return {"name": f"ตำนานที่{i}", "race": "มนุษย์", "dao": "กระบี่", "peak_realm": "แก่นทอง",
            "status": "ยังอยู่", "score": 100.0 - i, "seed": i, "years": 10 * i, "recorded_at": "2026-01-01"}


def world_with(legends):
    with mock.patch.object(CH, "all_legends", return_value=legends), \
            contextlib.redirect_stdout(io.StringIO()):
        sim = S.Sim(seed=SEED)
        told = [r["text"] for r in sim.rumors if r["kind"] == "ตำนาน"]
        sim.run(STEPS)
    return sim, told


def fingerprint(sim):
    """ทุกอย่างของโลกที่ถ้อยคำไม่ควรแตะ — สถานะ RNG, ลำดับเหตุการณ์ (ไม่รวมถ้อยคำ), ใครยังอยู่ และข่าวลือ"""
    return (sim.day, sim.seq, sim.rng.getstate(), sorted(sim.alive_cids),
            [(e.day, e.kind, e.actor, e.target, e.outcome) for e in sim.log],
            [(r["id"], r["kind"], r["world_id"], r["place"], sorted(r["heard"])) for r in sim.rumors])


class ChronicleDecouplingTests(unittest.TestCase):
    def test_the_same_seed_makes_the_same_world_whatever_the_chronicle_holds(self):
        worlds = [world_with([]), world_with([legend(1)]), world_with([legend(i) for i in range(8)])]
        prints = [fingerprint(sim) for sim, _told in worlds]
        self.assertEqual(prints[0], prints[1], "ไม่มีไฟล์ เทียบกับมีตำนานเรื่องเดียว")
        self.assertEqual(prints[0], prints[2], "ไม่มีไฟล์ เทียบกับมีตำนานแปดเรื่อง")
        told = [t for _sim, t in worlds]
        self.assertTrue(all(len(t) == C.RUMOR_ANCIENT_LEGENDS for t in told), "จำนวนข่าวลือตำนานคงที่")
        self.assertNotEqual(told[0], told[2], "ถ้อยคำยังมาจากตำนานในไฟล์")
        self.assertTrue(any("ตำนานที่" in t for t in told[2]))

    def test_the_same_seed_makes_the_same_world_in_separate_processes(self):
        # hash ของ str เปลี่ยนตาม PYTHONHASHSEED ทุก process — โลกห้ามขึ้นกับลำดับที่ได้จาก hash แบบนั้น
        code = ("import test_chronicle_decoupling as T; sim, _ = T.world_with([]); "
                "print(T.digest(sim))")
        here = os.path.dirname(os.path.abspath(__file__))
        outs = []
        for hash_seed in ("1", "2"):
            env = dict(os.environ, PYTHONHASHSEED=hash_seed, PYTHONIOENCODING="utf-8")
            done = subprocess.run([sys.executable, "-c", code], cwd=here, env=env, check=True,
                                  capture_output=True, text=True, encoding="utf-8", timeout=600)
            outs.append(done.stdout.strip().splitlines()[-1])
        self.assertEqual(outs[0], outs[1])


def digest(sim):
    return hashlib.sha256(repr(fingerprint(sim)).encode("utf-8")).hexdigest()


if __name__ == "__main__":
    unittest.main()
