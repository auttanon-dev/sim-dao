# -*- coding: utf-8 -*-
"""โลกหนึ่งใบมีผู้เขียนได้โปรเซสเดียว (แบบ §12.1) — persist.writer_lock

    python -m unittest test_writer_lock -v

เคยมี daemon กับตัวเดินโลกอีกตัวเดินโลกเดียวกันพร้อมกัน เซฟทับกันและต่อท้ายประวัติชนกันจนไฟล์เสีย
"""
import os
import subprocess
import sys
import tempfile
import time
import unittest

from tiandao import persist as PS

HERE = os.path.dirname(os.path.abspath(__file__))
HOLD = ("import sys, time; sys.path.insert(0, sys.argv[1]); from tiandao import persist as PS; "
        "l = PS.writer_lock(sys.argv[2]); print('held', flush=True); time.sleep(600)")


class WriterLockTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.save = os.path.join(self.folder.name, "world.save")

    def tearDown(self):
        self.folder.cleanup()

    def hold_in_another_process(self):
        p = subprocess.Popen([sys.executable, "-c", HOLD, HERE, self.save], stdout=subprocess.PIPE, text=True)
        self.assertEqual(p.stdout.readline().strip(), "held")
        return p

    def test_a_second_writer_fails_fast_with_a_clear_message(self):
        first = PS.writer_lock(self.save)
        with self.assertRaises(PS.WorldLocked) as ctx:
            PS.writer_lock(self.save)
        self.assertIn("มีอีกโปรเซสกำลังเดินโลก", str(ctx.exception))
        first.close()
        PS.writer_lock(self.save).close()                    # ปิดแล้วคนต่อไปเข้าได้

    def test_a_crashed_writer_does_not_leave_the_world_locked(self):
        p = self.hold_in_another_process()
        with self.assertRaises(PS.WorldLocked):
            PS.writer_lock(self.save)
        p.kill()                                             # ตายกลางทางโดยไม่ได้ปล่อยเอง
        p.wait()
        p.stdout.close()
        deadline = time.time() + 10
        while True:
            try:
                PS.writer_lock(self.save).close()
                break
            except PS.WorldLocked:
                self.assertLess(time.time(), deadline, "ล็อกค้างหลังโปรเซสตาย")
                time.sleep(0.2)

    def test_run_py_refuses_to_save_a_world_another_process_is_running(self):
        p = self.hold_in_another_process()
        try:
            done = subprocess.run([sys.executable, os.path.join(HERE, "run.py"), "--events", "50", "--no-autotune",
                                   "--no-chronicle", "--save", "--save-path", self.save,
                                   "--out", os.path.join(self.folder.name, "out")],
                                  cwd=HERE, capture_output=True, text=True, encoding="utf-8",
                                  env=dict(os.environ, PYTHONIOENCODING="utf-8"), timeout=300)
        finally:
            p.kill()
            p.wait()
            p.stdout.close()
        self.assertNotEqual(done.returncode, 0)
        self.assertIn("มีอีกโปรเซสกำลังเดินโลก", done.stderr + done.stdout)
        self.assertFalse(os.path.exists(self.save), "ต้องหยุดก่อนเดินหรือเซฟอะไรเลย")


if __name__ == "__main__":
    unittest.main()
