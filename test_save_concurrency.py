# -*- coding: utf-8 -*-
"""เซฟต้องไม่ล้มเพราะมีคนกำลังอ่านไฟล์เซฟอยู่ — บั๊ก WinError 5 ของ live viewer

    python -m unittest test_save_concurrency -v

บั๊กที่ไฟล์นี้ล็อกไว้ (WORLD_CONDITIONS_REFERENCE_TH.md, หัวข้อ "Live viewer ชนกับการเซฟบน Windows")
-----------------------------------------------------------------------------------------------
WorldRunner เขียน world.save.tmp แล้ว os.replace ทับ world.save ส่วน /api/jianghu เปิดอ่าน
world.save ทุกรอบ poll บน Windows การแทนไฟล์ที่อีก handle เปิดค้างอยู่ได้ WinError 5 แล้ว runner
เปลี่ยนสถานะเป็น error — โลกหยุดเดินแบบสุ่มๆ แค่เพราะมีคนเปิดหน้าดูโลก

สัญญาที่ล็อกไว้:
  1. ผู้อ่านที่อ่านผ่าน persist ไม่ขวางการเซฟ และผู้อ่านที่กำลังอ่านอยู่ได้สแนปช็อตเดิมครบ ไม่ครึ่งๆ
  2. ผู้อ่านภายนอกที่ถือไฟล์ไว้ชั่วครู่ (โปรแกรมอื่น, แอนตี้ไวรัส) ทำให้เซฟรอ ไม่ใช่ล้ม
  3. ถ้าถูกขวางนานเกินขอบเขต เซฟต้องล้มอย่างชัดเจน และไฟล์เซฟเดิมต้องอยู่ครบ
"""
import contextlib
import io
import os
import pickle
import tempfile
import threading
import time
import unittest
from unittest import mock

from tiandao import persist as PS
from tiandao import sim as S


def small_world(steps=200):
    with contextlib.redirect_stdout(io.StringIO()):
        sim = S.Sim(seed=7)
        sim.run(steps)
    return sim


class SaveWhileReadingTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.dir.name, "world.save")
        self.sim = small_world()
        PS.save_sim(self.sim, self.path)

    def tearDown(self):
        self.dir.cleanup()

    def test_a_reader_mid_read_does_not_block_the_save_and_keeps_its_snapshot(self):
        old_day = self.sim.day
        with PS.open_for_read(self.path) as reader:
            head = reader.read(16)
            with contextlib.redirect_stdout(io.StringIO()):
                self.sim.run(50)
            PS.save_sim(self.sim, self.path)          # เคยได้ WinError 5 ตรงนี้
            blob = pickle.loads(head + reader.read())
        self.assertEqual(blob["sim"].day, old_day, "ผู้อ่านต้องได้สแนปช็อตเดิมครบทั้งก้อน")
        self.assertEqual(PS.load_sim(self.path).day, self.sim.day)

    def test_polling_readers_never_break_repeated_saves(self):
        errors, loads, stop = [], [], threading.Event()

        def poll():
            while not stop.is_set():
                try:
                    loads.append(PS.load_sim(self.path).day)
                except Exception as exc:          # noqa: BLE001 — เก็บไว้รายงาน
                    errors.append(exc)

        readers = [threading.Thread(target=poll) for _ in range(2)]
        for t in readers:
            t.start()
        try:
            for _ in range(40):
                with contextlib.redirect_stdout(io.StringIO()):
                    self.sim.run(5)
                PS.save_sim(self.sim, self.path)
        finally:
            stop.set()
            for t in readers:
                t.join()
        self.assertEqual(errors, [])
        self.assertGreater(len(loads), 10, "ผู้อ่านต้องได้อ่านซ้อนกับการเซฟจริง")
        self.assertEqual(PS.load_sim(self.path).day, self.sim.day)

    def test_a_foreign_reader_holding_the_file_briefly_only_delays_the_save(self):
        foreign = open(self.path, "rb")               # ไม่ได้อ่านผ่าน persist: ไม่แชร์สิทธิ์ลบ
        threading.Timer(0.4, foreign.close).start()
        PS.save_sim(self.sim, self.path)
        self.assertTrue(foreign.closed)
        self.assertEqual(PS.load_sim(self.path).day, self.sim.day)

    def test_a_reader_that_never_lets_go_fails_the_save_loudly_and_keeps_the_old_file(self):
        with open(self.path, "rb") as f:
            before = f.read()
        with contextlib.redirect_stdout(io.StringIO()):
            self.sim.run(50)
        with open(self.path, "rb"), mock.patch.object(PS, "REPLACE_RETRY_SECONDS", 0.3):
            if os.name == "nt":
                with self.assertRaises(PermissionError):
                    PS.save_sim(self.sim, self.path)
            else:
                PS.save_sim(self.sim, self.path)      # POSIX ไม่ล็อกไฟล์ที่เปิดอ่านอยู่
                return
        with open(self.path, "rb") as f:
            self.assertEqual(f.read(), before, "ไฟล์เซฟเดิมต้องไม่ถูกแตะ")
        self.assertFalse(os.path.exists(self.path + ".tmp"), "ไม่ทิ้งไฟล์ชั่วคราวค้าง")


if __name__ == "__main__":
    unittest.main()


class RunnerSaveFailureTests(unittest.TestCase):
    """เซฟล้มชั่วคราวต้องไม่หยุดโลก แต่ล้มติดกันต้องหยุดพร้อมเหตุผล และห้ามรายงานวันที่ยังไม่ได้เซฟ"""

    def test_a_failed_save_is_reported_not_raised_and_the_world_keeps_its_state(self):
        from tiandao import worldloop as WL
        with tempfile.TemporaryDirectory() as folder:
            cfg = WL.LoopConfig(save_path=os.path.join(folder, "world.save"), chunk_events=20,
                                autotune=False, trim_log=False)
            sim = small_world()
            denied = PermissionError(13, "Access is denied")
            with mock.patch.object(PS, "save_sim", side_effect=denied), \
                    contextlib.redirect_stdout(io.StringIO()):
                summary = WL.run_round(sim, cfg, {})
            self.assertFalse(summary["saved"])
            self.assertIn("PermissionError", summary["save_error"])
            self.assertEqual(summary["day_to"], sim.day)
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertTrue(WL.run_round(sim, cfg, {})["saved"])
            self.assertEqual(PS.load_sim(cfg.save_path).day, sim.day)

    def test_consecutive_failures_stop_the_world_at_the_limit(self):
        from tiandao import worldloop as WL
        failed = {"saved": False, "save_error": "PermissionError: denied"}
        failures = 0
        for _ in range(WL.MAX_SAVE_FAILURES - 1):
            failures = WL.check_saved(failed, failures)
        self.assertEqual(WL.check_saved({"saved": True}, failures), 0, "เซฟสำเร็จล้างตัวนับ")
        with self.assertRaises(WL.SaveFailures):
            for _ in range(WL.MAX_SAVE_FAILURES):
                failures = WL.check_saved(failed, failures)
