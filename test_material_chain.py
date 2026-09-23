# -*- coding: utf-8 -*-
"""ตรวจว่าโซ่วัตถุดิบทำงานจริง — เก็บของ → หลอม → ขาดของ → ออกเดินทาง/เข้าตลาด

ก่อนมี materials.py วัตถุดิบเป็นตัวเลขก้อนเดียว ไม่มีใครเคยต้องการของชิ้นใดชิ้นหนึ่ง
เทสต์นี้ยืนยันสี่ข้อ:
  1. ของที่เก็บได้คู่ควรกับระดับโลกของสถานที่ (ไม่มีแร่สวรรค์โผล่ในถ้ำโลกมนุษย์)
  2. การหลอมกินวัตถุดิบชนิดเฉพาะจริง ไม่ใช่ตัวเลขรวม
  3. คนที่หลอมไม่ได้จะ "จำ" ว่าตัวเองขาดอะไร (ch.wants)
  4. ความขาดแคลนแปลงเป็นการกระทำ — เจตนาเดินทาง/ค้าขายถูกดันขึ้นจริง
"""
import sys

from tiandao import sim as S
from tiandao import materials as MAT
from tiandao import places as PL
from tiandao import intent as IN

STEPS = 30000


def test_place_tier_integrity():
    print("\n=== 1. ของที่เก็บได้ต้องคู่ควรกับระดับโลกของสถานที่ ===")
    bad = []
    for idx, p in enumerate(PL.PLACES):
        want_tier = MAT.WORLD_MAT_TIER.get(p[1], 0)
        for m in MAT.materials_at(idx):
            if MAT.MAT_TIER[m] != want_tier:
                bad.append((p[0], m))
    assert not bad, f"วัตถุดิบผิดระดับ: {bad[:5]}"
    with_mats = [i for i in range(len(PL.PLACES)) if MAT.materials_at(i)]
    print(f"  ✓ {len(with_mats)} สถานที่มีวัตถุดิบ ทุกชิ้นตรงระดับโลก")


def test_every_recipe_has_mats():
    print("\n=== 2. ทุกสูตรต้องระบุวัตถุดิบชนิดเฉพาะ ===")
    from tiandao import crafting as CR
    missing = [r[0] for r in (CR.PILLS + CR.WEAPONS) if not MAT.recipe_mats(r[0])]
    assert not missing, f"สูตรที่ยังไม่มีวัตถุดิบ: {missing[:5]}"
    # ทุกวัตถุดิบที่สูตรเรียกใช้ต้องหาได้จากที่ไหนสักแห่งจริง
    orphan = set()
    for reqs in MAT.RECIPE_MATS.values():
        for name, _q in reqs:
            if name not in MAT.BEAST_MATS and not MAT.sources_of(name):
                orphan.add(name)
    assert not orphan, f"วัตถุดิบที่ไม่มีที่ไหนผลิต: {sorted(orphan)[:5]}"
    print(f"  ✓ {len(MAT.RECIPE_MATS)} สูตร ทุกชิ้นมีวัตถุดิบ และทุกวัตถุดิบมีแหล่งจริง")


def test_chain_emerges():
    print(f"\n=== 3. รันซิมจริง {STEPS} เหตุการณ์ ===")
    sim = S.Sim(seed=2026, tiers=3)
    for _ in range(STEPS):
        sim.step()
    print(f"  ซิมเดินถึงวันที่ {sim.day} — มีชีวิตอยู่ {len(sim.alive_cids)} คน")

    crafted, lacked, gathered = [], [], []
    craft_try = 0
    for ev in sim.log:
        if ev.kind in ("หลอมยา", "หลอมอาวุธ"):
            craft_try += 1
        d = getattr(ev, "deltas", None) or {}
        if "วัตถุดิบที่ใช้" in d:
            crafted.append(d["วัตถุดิบที่ใช้"])
        if "ยังขาด" in d:
            lacked.append(d)
        if "เก็บได้" in d:
            gathered.append(d["เก็บได้"])

    waste = len(lacked) / max(1, craft_try)
    print(f"  ลงมือหลอมทั้งหมด               : {craft_try} ครั้ง")
    print(f"  หลอมโดยกินวัตถุดิบชนิดเฉพาะ    : {len(crafted)} ครั้ง")
    print(f"  ไปยืนหน้าเตาทั้งที่ของไม่ครบ    : {len(lacked)} ครั้ง ({waste*100:.0f}%)")
    print(f"  เก็บวัตถุดิบจากแหล่ง            : {len(gathered)} ครั้ง")
    assert crafted, "ไม่มีการหลอมที่กินวัตถุดิบจริงเลย"
    assert gathered, "ไม่มีใครเก็บวัตถุดิบได้เลย"
    # เจตนารู้เงื่อนไขแล้ว การเดินไปหลอมทั้งที่ของไม่ครบจึงต้องเป็นส่วนน้อย
    assert waste < 0.25, f"ยังเดินไปหลอมทั้งที่ของไม่ครบถึง {waste*100:.0f}% ของการลงมือหลอม"

    print("\n  ตัวอย่างการหลอมที่กินของจริง:")
    for x in crafted[:3]:
        print(f"    - {x}")
    seekers = [c for c in sim.cast if c.alive and getattr(c, "wants", None)]
    print(f"\n  คนที่กำลังตามหาวัตถุดิบอยู่ตอนนี้: {len(seekers)} คน")
    assert seekers, "ไม่มีใครถือความต้องการค้างไว้เลย"
    return sim, seekers


def test_scarcity_moves_people(sim, seekers):
    print("\n=== 4. ความขาดแคลนต้องแปลงเป็นการกระทำ ===")
    import tiandao.events as E
    moved = 0
    checked = 0
    for ch in seekers[:200]:
        table = E.EVENT_TABLE
        w_with = IN.weigh(ch, sim, table, True)
        saved, ch.wants = ch.wants, {}
        w_without = IN.weigh(ch, sim, table, True)
        ch.wants = saved
        checked += 1
        if (w_with.get("เดินทาง", 0) > w_without.get("เดินทาง", 0)
                or w_with.get("ค้าขาย", 0) > w_without.get("ค้าขาย", 0)
                or w_with.get("ล่าอสูร", 0) > w_without.get("ล่าอสูร", 0)):
            moved += 1
    ratio = moved / checked
    print(f"  {moved}/{checked} คน ({ratio:.0%}) มีน้ำหนักเดินทาง/ค้าขาย/เก็บของสูงขึ้นเพราะของที่ขาด")
    assert ratio > 0.8, "ความขาดแคลนไม่ได้ผลักดันพฤติกรรมจริง"


if __name__ == "__main__":
    test_place_tier_integrity()
    test_every_recipe_has_mats()
    sim, seekers = test_chain_emerges()
    test_scarcity_moves_people(sim, seekers)
    print("\n✓ โซ่วัตถุดิบทำงานครบวง")
