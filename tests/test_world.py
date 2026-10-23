# -*- coding: utf-8 -*-
"""เทสต์ฝั่ง Python — ตัวห่อ simdao ใช้งานได้ และโลกจากเอนจิน Rust สมเหตุสมผล
(กฎละเอียดของโลกทดสอบฝั่ง Rust: cd simdao_core && cargo test --release)"""
import os

import pytest

from simdao import World


@pytest.fixture(scope="module")
def world():
    w = World(seed=5)
    w.run_years(20)
    return w


def test_world_runs_and_lives(world):
    s = world.stats()
    assert s["population"] > 1000
    assert s["ever_born"] > s["population"] // 2
    assert world.day >= 20 * 365


def test_ledgers_close(world):
    s = world.stats()
    assert abs(s["food_total"] - s["food_ledger"]) < 1e-3 * s["food_ledger"]
    assert abs(s["gold_total"] - s["gold_ledger"]) < 1e-6 * s["gold_ledger"]


def test_events_and_people_are_readable(world):
    evs = world.recent(20)
    assert evs and all({"seq", "day", "kind", "text"} <= set(e) for e in evs)
    p = world.person(world.people(limit=1)[0]["id"])
    assert p["alive"] and p["name"] and p["place_name"]


def test_same_seed_same_history():
    a, b = World(seed=9), World(seed=9)
    a.run_years(5)
    b.run_years(5)
    assert a.recent(50) == b.recent(50)


def test_save_and_resume(tmp_path, world):
    path = os.path.join(tmp_path, "w.json")
    world.save(path)
    again = World.load(path)
    assert again.day == world.day and again.population == world.population
    world.run_years(2)
    again.run_years(2)
    assert again.recent(30) == world.recent(30)
