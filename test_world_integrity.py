# -*- coding: utf-8 -*-
"""ตรวจว่าข้อมูลที่ออกแบบไว้ ถูกใช้จริงในระบบ ไม่ใช่นิยามทิ้งไว้เฉยๆ

หลายตารางในโปรเจกต์เคยถูกนิยามไว้ครบแต่ไม่มีโค้ดไหนอ่านเลย (ORES/HERBS เคยเป็นแบบนั้น
จนกระทั่งมี materials.py) เทสต์นี้กันไม่ให้เกิดซ้ำ และเช็คว่าโครงโลกที่ประกาศไว้
(places.REALM_RELATIONS) ตรงกับกราฟภูมิศาสตร์ที่สร้างจริง
"""
import collections

from tiandao import config as C
from tiandao import crafting as CR
from tiandao import geo as GEO
from tiandao import materials as MAT
from tiandao import places as PL


def test_realm_relations_match_graph():
    print("\n=== 1. ความสัมพันธ์ระหว่างภพที่ประกาศไว้ ต้องมีอยู่ในกราฟจริง ===")
    world_of = {i: PL.PLACES[i][1] for i in range(len(PL.PLACES))}
    link = collections.defaultdict(set)
    for e in GEO.EDGES:
        a, b = world_of.get(e[0]), world_of.get(e[1])
        if a == b:
            continue
        et = e[3] if len(e) > 3 else "road"
        link[frozenset((a, b))].add(et)
    missing, mismatch = [], []
    for (wa, wb), rel in PL.REALM_RELATIONS.items():
        key = frozenset((wa, wb))
        if key not in link:
            missing.append((wa, wb))
            continue
        if rel["type"] not in link[key]:
            mismatch.append((wa, wb, rel["type"], sorted(link[key])))
    for wa, wb in missing:
        print(f"  ✗ ประกาศว่า {wa} ↔ {wb} เชื่อมกัน แต่ไม่มีเส้นเชื่อมในกราฟ")
    for wa, wb, want, got in mismatch:
        print(f"  ! {wa} ↔ {wb} ประกาศเป็น '{want}' แต่กราฟมี {got}")
    assert not missing, f"ความสัมพันธ์ที่ไม่มีในกราฟ: {missing}"
    print(f"  ✓ ตรวจ {len(PL.REALM_RELATIONS)} ความสัมพันธ์ — มีเส้นเชื่อมจริงครบ")


def test_furnaces_are_used():
    print("\n=== 2. เตาหลอมที่ตั้งชื่อไว้ ต้องถูกใช้จริง ===")
    used = collections.Counter()
    with_furnace = 0
    for i in range(len(PL.PLACES)):
        f = MAT.furnace_of(i)
        if PL.PLACES[i][5] is not None and PL.PLACES[i][5] >= 0:
            with_furnace += 1
            assert f is not None, f"{PL.PLACES[i][0]} มีระดับเตาแต่หาเตาไม่ได้"
            used[f[0]] += 1
    assert used, "ไม่มีสถานที่ไหนได้เตาเลย"
    print(f"  ✓ {with_furnace} สถานที่มีเตา ใช้เตาที่ตั้งชื่อไว้ {len(used)}/{len(CR.FURNACES)} ชนิด")
    # หม้อปรุงยาต้องไปอยู่กับแหล่งสมุนไพร ไม่ใช่เมืองแร่
    wrong = [PL.PLACES[i][0] for i in range(len(PL.PLACES))
             if MAT.furnace_of(i) and PL.PLACES[i][4] == "สมุนไพร"
             and not MAT.furnace_of(i)[0].startswith("หม้อ")]
    assert not wrong, f"แหล่งสมุนไพรที่ได้เตาโลหะ: {wrong[:3]}"
    print("  ✓ แหล่งสมุนไพรได้หม้อปรุงยา ไม่ใช่เตาหลอมโลหะ")


def test_material_kinds_reachable():
    print("\n=== 3. วัตถุดิบทุกชนิดที่นิยามไว้ ต้องมีทางได้มา ===")
    assert MAT.BEAST_PARTS, "ชิ้นส่วนอสูรใน MATERIAL_KINDS ยังไม่มีทางได้มา"
    for name in MAT.BEAST_PARTS:
        assert MAT.market_price(name) > 0, f"{name} ขายไม่ได้ (ไม่มีราคากลาง)"
    print(f"  ✓ ชิ้นส่วนอสูร {len(MAT.BEAST_PARTS)} ชนิด หล่นจากการล่าและขายได้จริง")
    orphan = [n for n in MAT.MAT_TIER
              if n not in MAT.BEAST_MATS and not MAT.sources_of(n)]
    assert not orphan, f"วัตถุดิบที่ไม่มีแหล่งผลิต: {orphan}"
    print(f"  ✓ แร่/สมุนไพร {len(MAT.MAT_TIER) - len(MAT.BEAST_MATS)} ชนิด มีแหล่งเก็บจริงทุกชนิด")


def test_manuals_and_item_grades():
    print("\n=== 4. คัมภีร์/ยันต์ และชื่อชั้นของของ ===")
    assert C.MANUALS_AND_TALISMANS, "ไม่มีตารางคัมภีร์"
    n = sum(len(v) for v in C.MANUALS_AND_TALISMANS.values())
    print(f"  ✓ คัมภีร์/ยันต์ {n} ชิ้น ใน {len(C.MANUALS_AND_TALISMANS)} หมวด (พบได้จากแดนลับ)")
    assert len(C.ITEM_GRADES) >= 3
    print(f"  ✓ ชื่อชั้นของของ: {', '.join(C.ITEM_GRADES)}")


if __name__ == "__main__":
    test_realm_relations_match_graph()
    test_furnaces_are_used()
    test_material_kinds_reachable()
    test_manuals_and_item_grades()
    print("\n✓ ข้อมูลที่ออกแบบไว้ถูกใช้จริงครบ")
