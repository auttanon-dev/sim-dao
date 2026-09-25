# -*- coding: utf-8 -*-
"""นาฬิกาโลก: งานของโลกเดินตามวัน ไม่ใช่ตามว่าใครถึงคิว

    python -m unittest test_world_clock -v

ก่อนมีนาฬิกาโลก งานของโลกทั้งหมด (ทรัพยากรฟื้น ปราณไหลเข้า เพิ่มประชากร ภัยประจำเดือน วิกฤต)
ทำงานเฉพาะตอนมีตัวละครถึงคิว ถ้าทุกคนปิดด่านแปดปี โลกหยุดแปดปีแล้วคิดรวบเป็นก้อนเดียวตอนมีคนตื่น
และถ้าคิวว่าง ซิมหยุดทั้งที่ธรรมชาติควรเดินต่อ (SIM_DAO_AUTONOMOUS_WORLD_DESIGN_TH.md §5.1, §13.2
"ทุกคนกำลังทำกิจกรรมยาว — ฤดูกาล การเติบโต และ critical event ของโลกยังเกิด")
"""
import contextlib
import heapq
import io
import os
import pickle
import tempfile
import unittest
from unittest import mock

from tiandao import config as C
from tiandao import persist as PS
from tiandao import sim as S


def quiet(fn, *a, **kw):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*a, **kw)


def world_after(steps, seed=3):
    sim = quiet(S.Sim, seed=seed)
    quiet(sim.run, steps)
    return sim


def record_ticks(sim):
    """คืน list ที่เก็บวันของนาฬิกาโลกทุกครั้งที่มันทำงาน"""
    ticks, original = [], sim._world_tick

    def tick(rng):
        original(rng)
        ticks.append(sim.day)
    sim._world_tick = tick
    return ticks


class WorldClockTests(unittest.TestCase):
    def test_world_work_keeps_a_monthly_rhythm_while_everyone_is_secluded(self):
        sim = world_after(300)
        start = sim.day
        wake = start + 8 * 365
        sleepers = {cid for _day, cid in sim.queue}
        sim.queue = [(wake, cid) for cid in sleepers]
        heapq.heapify(sim.queue)
        ticks = record_ticks(sim)
        with mock.patch.object(sim, "repopulate"):      # แยกนาฬิกาออกจากการเติมประชากร
            event = quiet(sim.step)

        # ใครก็ตามที่ถึงคิวก่อนวันออกจากด่าน ต้องเป็นคนที่โลกสร้างขึ้นระหว่างนั้น (เช่นต้นไม้โลกตั้ง
        # แดนสาขา) ไม่ใช่คนในด่านที่ตื่นก่อนกำหนด — และนั่นก็คือหลักฐานว่าโลกไม่ได้หยุดรอ
        self.assertTrue(event.day == wake or event.actor not in sleepers)
        self.assertLessEqual(ticks[0] - start, C.WORLD_TICK_DAYS)
        self.assertEqual({b - a for a, b in zip(ticks, ticks[1:])}, {C.WORLD_TICK_DAYS},
                         "งานของโลกต้องเดินทุกเดือนระหว่างที่ทุกคนปิดด่าน ไม่ใช่รอคนตื่น")
        self.assertGreater(ticks[-1], event.day - C.WORLD_TICK_DAYS)
        self.assertGreaterEqual(sim.worlds[0].checked_day, ticks[-1], "ปราณไหลเข้าโลกตามเวลา")
        self.assertGreaterEqual(sim.eco_day, ticks[-1], "ทรัพยากรฟื้นตามเวลา")

    def test_the_world_outlives_a_population_that_died_out(self):
        sim = world_after(300)
        for ch in list(sim.living()):
            quiet(sim.kill, ch, "ทดสอบ", natural=True)
        died = sim.day
        ticks = record_ticks(sim)
        event = quiet(sim.step)

        self.assertIsNotNone(event, "คิวคนว่างต้องไม่ทำให้โลกหยุด")
        self.assertTrue(ticks, "นาฬิกาโลกต้องเดินระหว่างที่ไม่มีใครถึงคิว")
        self.assertLessEqual(ticks[0] - died, C.WORLD_TICK_DAYS)
        self.assertGreater(event.day, died)

    def test_a_world_where_nobody_ever_comes_reports_an_empty_queue(self):
        sim = world_after(200)
        sim.queue = []
        start = sim.day
        with mock.patch.object(C, "WORLD_IDLE_LIMIT_DAYS", 365), \
                mock.patch.object(sim, "repopulate"):
            self.assertIsNone(quiet(sim.step))
        self.assertGreater(sim.day, start + 365 - C.WORLD_TICK_DAYS)
        self.assertEqual(sim.eco_day, sim.day, "ระหว่างรอ ธรรมชาติยังเดินจนถึงวันสุดท้าย")

    def test_a_world_tick_and_a_turn_on_the_same_day_run_world_first(self):
        sim = world_after(200)
        due = sim.world_tick_day
        cid = sim.queue[0][1]
        sim.queue = [(due, cid)]
        order = []
        original = sim._world_tick
        sim._world_tick = lambda rng: (order.append("world"), original(rng))
        event = quiet(sim.step)
        order.append("turn")
        self.assertEqual(order[:2], ["world", "turn"])
        self.assertEqual(event.day, due)


class WorldClockSaveTests(unittest.TestCase):
    def test_an_older_save_gets_a_clock_without_moving_the_rng(self):
        sim = world_after(200)
        del sim.world_tick_day, sim.eco_day
        rng_state = sim.rng.getstate()
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "world.save")
            with open(path, "wb") as f:
                pickle.dump({"save_version": 1, "sim": sim}, f)
            loaded = PS.load_sim(path)
        self.assertEqual(loaded.world_tick_day, loaded.day)
        self.assertEqual(loaded.eco_day, loaded.last_day)
        self.assertEqual(loaded.rng.getstate(), rng_state)

    def test_a_current_save_keeps_the_clock_exactly(self):
        sim = world_after(200)
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "world.save")
            PS.save_sim(sim, path)
            loaded = PS.load_sim(path)
        self.assertEqual((loaded.world_tick_day, loaded.eco_day), (sim.world_tick_day, sim.eco_day))


if __name__ == "__main__":
    unittest.main()
