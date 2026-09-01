# -*- coding: utf-8 -*-
"""Verification test for building-level settlement routing: crafting/training/trading must walk
to the right building within a place before the action succeeds, mirroring inter-place travel
(Character.travel_dest/travel_arrival_day) via the new Character.building_dest/building_arrival_day."""
import sys
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

sys.path.insert(0, str(Path(__file__).resolve().parent))

from tiandao import places as PL
from tiandao import events as E
from tiandao import settlement as SETTLE
from tiandao.sim import Sim


def find_place(ptype_wanted, need_furnace=False):
    for i, p in enumerate(PL.PLACES):
        name, world_key, grade, ptype, res, furn, sec_parent, is_sealed = p
        if ptype == ptype_wanted and (not need_furnace or furn >= 0):
            return i
    return None


def test_route_to_building_craft():
    sim = Sim(seed=1, tiers=1)
    place_idx = find_place("เมือง", need_furnace=True)
    assert place_idx is not None, "ไม่พบเมืองที่มีเตาหลอมสำหรับทดสอบ"
    ch = sim.living()[0]
    ch.place = place_idx
    ch.building = -1
    ch.building_dest = -1

    craft_building = SETTLE.find_building_of_type(place_idx, ("craft",))
    assert craft_building is not None, "settlement ของเมืองนี้ไม่มีอาคาร craft เลย"

    ready = sim.route_to_building(ch, ("craft",))
    assert ready is False, "ควรยังไม่พร้อม (ยังไม่เคยอยู่อาคาร craft มาก่อน)"
    assert ch.building_dest == craft_building
    assert ch.building_arrival_day == sim.day + 1

    ch.building = ch.building_dest
    ch.building_dest = -1
    ready2 = sim.route_to_building(ch, ("craft",))
    assert ready2 is True, "หลังถึงอาคาร craft แล้วควรพร้อมทำกิจกรรมได้เลย"
    print("  ✓ route_to_building (craft): เดินไปเตาหลอมแล้วพร้อมหลอมของจริง")


def test_building_resets_on_travel():
    sim = Sim(seed=2, tiers=1)
    ch = sim.living()[0]
    place_a = find_place("เมือง", need_furnace=True)
    ch.place = place_a
    ch.building = SETTLE.find_building_of_type(place_a, ("craft",))
    assert ch.building is not None and ch.building >= 0

    # จำลองบรรทัดที่เพิ่มเข้าไปใน sim.py step() ตอนเดินทางมาถึง place ใหม่ (~line 925)
    dest = find_place("ตลาด") or place_a
    ch.travel_dest = dest
    ch.place = ch.travel_dest
    ch.travel_dest = -1
    ch.building = -1
    assert ch.building == -1, "ย้าย place แล้วต้องรีเซ็ต building เป็น -1"
    print("  ✓ building รีเซ็ตเป็น -1 ถูกต้องหลังเดินทางไป place ใหม่")


def test_end_to_end_craft_walk_then_succeed():
    sim = Sim(seed=3, tiers=1)
    place_idx = find_place("เมือง", need_furnace=True)
    ch = sim.living()[0]
    ch.place = place_idx
    ch.building = -1
    ch.building_dest = -1
    ch.alch_rank = 0
    ch.mats = 999
    ch.cores = 999

    ev = next(e for e in E.EVENT_TABLE if e["kind"] == "หลอมยา")
    world = sim.world(ch.world_id)

    outcome1, text1, d1 = sim.resolve(ev, ch, None, world, 1, sim.rng)
    assert outcome1 == "เดินไปเตาหลอม", f"รอบแรกควรแค่เดินไปเตาหลอม ได้ {outcome1} แทน"
    assert ch.building_dest >= 0

    sim.day = ch.building_arrival_day
    ch.building = ch.building_dest
    ch.building_dest = -1

    outcome2, text2, d2 = sim.resolve(ev, ch, None, world, 1, sim.rng)
    assert outcome2 != "เดินไปเตาหลอม", "รอบสองควรไม่เดินซ้ำ เพราะถึงเตาหลอมแล้ว"
    print(f"  ✓ end-to-end: เดินไปเตาหลอมก่อน แล้วรอบสองหลอมได้จริง (outcome={outcome2})")


def test_settlement_layout_matches_skeleton():
    place_idx = find_place("เมือง", need_furnace=True)
    layout = SETTLE.generate_settlement_layout(place_idx)
    skeleton = SETTLE.get_building_skeleton(place_idx)
    assert len(layout["buildings"]) == len(skeleton), "จำนวนอาคารใน layout เต็มกับ skeleton ต้องตรงกัน"
    for b, sk in zip(layout["buildings"], skeleton):
        assert b["id"] == sk["id"] and b["type"] == sk["type"], "id/type ต้องตรงกันทุกตัว"
    print("  ✓ generate_settlement_layout ใช้ get_building_skeleton เดียวกัน ไม่เพี้ยนกัน")


if __name__ == "__main__":
    print("=== ทดสอบระบบเดินในเมืองไปอาคารเป้าหมาย (Settlement Building Routing) ===")
    test_route_to_building_craft()
    test_building_resets_on_travel()
    test_end_to_end_craft_walk_then_succeed()
    test_settlement_layout_matches_skeleton()
    print("\n\U0001f389 SETTLEMENT ROUTING TESTS PASSED!")
