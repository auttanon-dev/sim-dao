# -*- coding: utf-8 -*-
"""เพดานของ event log (tiandao/event_log.py และ run.py --save)

    python -m unittest test_event_log -v

สิ่งที่ล็อกไว้
  · flush_and_trim เก็บในหน่วยความจำแค่ล่าสุด ส่วนที่เหลือต่อท้ายไฟล์ ประวัติเต็มกลับมาครบ ไม่ซ้ำ ไม่หาย แม้เรียกหลายรอบ
  · run.py --save กับ --resume ซ้ำหลายรอบ world.save ไม่สะสม log ตั้งแต่เริ่มโลก (100 ปีจำลองเคยมี ~290,000 เหตุการณ์)
"""
import contextlib
import io
import os
import subprocess
import sys
import tempfile
import unittest

from tiandao import event_log as EL
from tiandao import persist as PS
from tiandao import sim as S

HERE = os.path.dirname(os.path.abspath(__file__))


def quiet(fn, *a, **kw):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*a, **kw)


def seqs(events):
    return [e.seq for e in events]


class FlushAndTrimTests(unittest.TestCase):
    def test_memory_keeps_only_the_latest_and_the_file_keeps_the_rest_exactly_once(self):
        sim = quiet(S.Sim, seed=3)
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "world.save.events.jsonl")
            everything = []
            for _ in range(3):
                quiet(sim.run, 1500)
                everything += [e for e in sim.log if not everything or e.seq > everything[-1].seq]
                EL.flush_and_trim(sim, path, 400)
                self.assertLessEqual(len(sim.log), 400)
            whole = EL.full_log(sim, path)
            self.assertEqual(seqs(whole), seqs(everything))
            self.assertEqual(len(set(seqs(whole))), len(whole), "ไม่มีเหตุการณ์ซ้ำ")


class RunPyTrimsTheSaveTests(unittest.TestCase):
    def _run(self, folder, *extra):
        cmd = [sys.executable, os.path.join(HERE, "run.py"), "--seed", "3", "--events", "1500",
               "--no-autotune", "--no-chronicle", "--save", "--save-path", os.path.join(folder, "world.save"),
               "--out", os.path.join(folder, "out"), "--keep-recent-events", "300", *extra]
        subprocess.run(cmd, cwd=HERE, check=True, capture_output=True, timeout=900)

    def test_resuming_and_saving_again_does_not_pile_the_whole_history_into_the_save(self):
        with tempfile.TemporaryDirectory() as folder:
            self._run(folder)
            self._run(folder, "--resume")
            save = os.path.join(folder, "world.save")
            sim = PS.load_sim(save)
            self.assertLessEqual(len(sim.log), 300)
            whole = EL.full_log(sim, EL.default_log_path(save))
            self.assertEqual(len(set(seqs(whole))), len(whole), "ไม่มีเหตุการณ์ซ้ำ")
            self.assertEqual(seqs(whole), sorted(seqs(whole)))
            self.assertGreater(len(whole), 2000, "สองรอบ รอบละ 1,500 เหตุการณ์ ประวัติต้องอยู่ครบ")


if __name__ == "__main__":
    unittest.main()
