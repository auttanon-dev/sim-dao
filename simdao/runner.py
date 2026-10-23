# -*- coding: utf-8 -*-
"""เดินโลกต่อเนื่องใน thread เบื้องหลัง — ใช้ร่วมกันทั้งหน้าเว็บ (app.py) และ run.py --forever

ตัวเอนจินไม่ thread-safe จึงมีล็อกเดียวคุมทุกการเข้าถึง: thread เดินโลกถือล็อกทีละก้อนเล็ก
(CHUNK_DAYS วันของโลก) หน้าเว็บอ่านสถานะได้ระหว่างก้อน
"""
import threading
import time

from . import World, DEFAULT_SAVE

CHUNK_DAYS = 30


class Runner:
    def __init__(self, world: World, save_path=DEFAULT_SAVE, years_per_second=1.0, autosave_years=5.0):
        self.world = world
        self.save_path = save_path
        self.years_per_second = years_per_second
        self.autosave_years = autosave_years
        self.lock = threading.RLock()
        self._thread = None
        self._stop = threading.Event()
        self.error = None

    @property
    def running(self):
        return self._thread is not None and self._thread.is_alive()

    def start(self):
        if self.running:
            return
        self._stop.clear()
        self.error = None
        self._thread = threading.Thread(target=self._loop, name="world-runner", daemon=True)
        self._thread.start()

    def stop(self, timeout=10.0):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout)
        self.save()

    def save(self):
        with self.lock:
            self.world.save(self.save_path)

    def _loop(self):
        last_save = self.world.day
        try:
            while not self._stop.is_set():
                t0 = time.monotonic()
                with self.lock:
                    moved = self.world.run_until(self.world.day + CHUNK_DAYS)
                    if self.world.population == 0 and moved == 0:
                        break
                    if self.world.day - last_save >= self.autosave_years * 365:
                        self.world.save(self.save_path)
                        last_save = self.world.day
                # คุมความเร็ว: years_per_second ปีของโลกต่อหนึ่งวินาทีจริง (<= 0 = เร็วที่สุด)
                if self.years_per_second > 0:
                    budget = CHUNK_DAYS / 365.0 / self.years_per_second
                    left = budget - (time.monotonic() - t0)
                    if left > 0:
                        self._stop.wait(left)
        except Exception as ex:  # pragma: no cover — รายงานให้หน้าเว็บเห็น ไม่ให้ thread ตายเงียบ
            self.error = repr(ex)
