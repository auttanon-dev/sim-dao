# -*- coding: utf-8 -*-
"""Sim Dao — ฝั่ง Python ของโลกจำลอง

ตัวโลกทั้งหมด (คน แดน สำนัก ยุ้งฉาง บัญชี) อยู่ในเอนจิน Rust (`simdao_core.Engine`)
แพ็กเกจนี้แค่ห่อให้เรียกง่าย: คืน dict/list แทนสตริง JSON และมีตัวเดินโลกเบื้องหลัง

    from simdao import World
    w = World(seed=7)
    w.run_years(10)
    print(w.stats()["population"], w.events(limit=5))
    w.save("out/world.json")
"""
import json
import os

import simdao_core as _core

DEFAULT_SAVE = os.path.join("out", "world.json")


class World:
    """โลกหนึ่งใบ — บางๆ รอบ simdao_core.Engine"""

    def __init__(self, seed=0, config=None, _engine=None):
        if _engine is not None:
            self.engine = _engine
        else:
            self.engine = _core.Engine(seed, json.dumps(config) if config else None)

    # ---------------------------------------------------------------- เดิน
    def run(self, steps):
        """เดินไป `steps` เทิร์น คืนจำนวนที่เดินได้จริง"""
        return self.engine.run(int(steps))

    def run_until(self, day):
        return self.engine.run_until(int(day))

    def run_years(self, years):
        return self.engine.run_until(self.engine.day + int(round(years * 365)))

    # ---------------------------------------------------------------- อ่าน
    @property
    def day(self):
        return self.engine.day

    @property
    def year(self):
        return self.engine.day / 365.0

    @property
    def seed(self):
        return self.engine.seed

    @property
    def population(self):
        return self.engine.population

    @property
    def last_seq(self):
        return self.engine.last_seq

    def stats(self):
        return json.loads(self.engine.stats_json())

    def events(self, since=0, limit=1000, kind=None, person=None):
        return json.loads(self.engine.events_json(since, limit, kind, person))

    def recent(self, n=50, **kw):
        """เหตุการณ์ล่าสุด `n` รายการ (ใหม่สุดก่อน)"""
        return list(reversed(self.events(since=max(0, self.last_seq - n), limit=n, **kw)))

    def person(self, pid):
        return json.loads(self.engine.person_json(int(pid)))

    def people(self, world=None, place=None, alive=True, limit=100000):
        return json.loads(self.engine.people_json(world, place, alive, limit))

    def worlds(self):
        return json.loads(self.engine.worlds_json())

    def places(self):
        return json.loads(self.engine.places_json())

    def edges(self):
        return json.loads(self.engine.edges_json())

    def sects(self):
        return json.loads(self.engine.sects_json())

    def config(self):
        return json.loads(self.engine.config_json())

    # ---------------------------------------------------------------- เซฟ
    def save(self, path=DEFAULT_SAVE):
        d = os.path.dirname(path)
        if d:
            os.makedirs(d, exist_ok=True)
        self.engine.save(path)

    @classmethod
    def load(cls, path=DEFAULT_SAVE):
        return cls(_engine=_core.Engine.load(path))

    @classmethod
    def load_or_create(cls, path=DEFAULT_SAVE, seed=0, config=None):
        if os.path.exists(path):
            return cls.load(path)
        return cls(seed=seed, config=config)
