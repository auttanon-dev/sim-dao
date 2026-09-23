# -*- coding: utf-8 -*-
"""ซิมต้องไม่ล้มเพราะหน้าคอนโซลเข้ารหัสภาษาไทย/อิโมจิไม่ได้

บั๊กจริงบนวินโดวส์: stdout ที่ไม่ใช่ UTF-8 (คอนโซลเริ่มต้น, ถูก redirect ลงไฟล์, รันเป็นบริการ)
ทำให้ print() ในซิมโยน UnicodeEncodeError กลางรัน — ตรรกะของโลกพังเพราะหน้าจอ

    python -m unittest test_console_encoding -v
"""
import contextlib
import io
import sys
import unittest

from tiandao import console
from tiandao import sim as S


def narrow_stream(encoding="cp1252"):
    """สตรีมข้อความที่เข้ารหัสได้แคบและเข้มงวด — จำลอง stdout ของวินโดวส์ที่ถูก redirect"""
    return io.TextIOWrapper(io.BytesIO(), encoding=encoding, errors="strict",
                            write_through=True)


class SafePrintTests(unittest.TestCase):
    def test_emoji_and_thai_survive_a_cp1252_stream(self):
        out = narrow_stream()
        with contextlib.redirect_stdout(out):
            console.safe_print("🌲 [ป่าหมื่นอสูร] ล่าสัตว์อสูรสำเร็จ!")
            console.safe_print("plain ascii line")
        text = out.buffer.getvalue().decode("cp1252")
        self.assertIn("plain ascii line", text)
        self.assertTrue(text.strip(), "ต้องยังเขียนอะไรออกไป ไม่ใช่กลืนบรรทัดทิ้งเงียบๆ")

    def test_plain_print_is_what_actually_breaks(self):
        """ยืนยันว่าเงื่อนไขในเทสต์นี้จำลองปัญหาจริง ไม่ใช่เทสต์ที่ผ่านเพราะไม่มีอะไรเกิดขึ้น"""
        out = narrow_stream()
        with contextlib.redirect_stdout(out):
            with self.assertRaises(UnicodeEncodeError):
                print("🌲 ป่าหมื่นอสูร")

    def test_enable_utf8_is_idempotent_and_never_raises(self):
        console._DONE = False
        try:
            fake = narrow_stream()
            with contextlib.redirect_stdout(fake):
                console.enable_utf8()
                console.enable_utf8()
            self.assertEqual(fake.encoding, "utf-8")
        finally:
            console._DONE = False
            console.enable_utf8()

    def test_enable_utf8_tolerates_streams_without_reconfigure(self):
        console._DONE = False
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                console.enable_utf8()
        finally:
            console._DONE = False
            console.enable_utf8()


class SimulationSurvivesNarrowConsoleTests(unittest.TestCase):
    STEPS = 4000

    def test_world_keeps_running_with_a_cp1252_stdout(self):
        """เดินโลกจริงโดยให้ stdout เข้ารหัสได้แค่ cp1252 — ต้องเดินครบทุกก้าว

        4,000 เหตุการณ์ครอบคลุมบล็อกที่ print อิโมจิ (ป่าหมื่นอสูร บัญชาสวรรค์ คลื่นสัตว์อสูร
        องครักษ์เสื้อแพร ภัยพิบัติแผ่นดิน) ซึ่งทำงานเป็นรอบทุกๆ ไม่กี่สิบวัน
        """
        out = narrow_stream()
        sim = S.Sim(seed=11, tiers=2)
        with contextlib.redirect_stdout(out):
            for _ in range(self.STEPS):
                sim.step()
        self.assertGreater(len(sim.log), 0)
        self.assertGreater(sim.day, 0)

    def test_narrow_console_does_not_change_the_world(self):
        """หน้าจอเป็นเรื่องการแสดงผล ไม่ใช่ตรรกะ — โลกที่รันใต้ stdout แคบต้องเหมือนกันเป๊ะ"""
        def run(stream):
            sim = S.Sim(seed=11, tiers=2)
            with contextlib.redirect_stdout(stream):
                for _ in range(1500):
                    sim.step()
            return [(e.day, e.kind, e.outcome, e.actor, e.target) for e in sim.log]

        self.assertEqual(run(narrow_stream()), run(io.StringIO()))


if __name__ == "__main__":
    unittest.main()
