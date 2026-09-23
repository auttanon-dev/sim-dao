# -*- coding: utf-8 -*-
"""ตรวจว่าโลกเดินซ้ำได้เหมือนเดิม — ทั้งรันใหม่จาก seed เดิม และรันต่อจากไฟล์ save

ข้อที่สองสำคัญกว่าที่คิด: ไปป์ไลน์นิยายรันต่อจาก save (--resume) เสมอ ถ้ารันต่อแล้วโลก
เดินคนละทางกับรันรวดเดียว แปลว่าผลลัพธ์ขึ้นกับ "หยุดตรงไหน" ซึ่งทำให้ทำซ้ำและดีบักไม่ได้

บั๊กที่เคยเจอ: living()/living_in() วนจาก set โดยตรง ลำดับของ set ใน Python เปลี่ยนไป
หลัง pickle/unpickle ทำให้ rng.choice(others) เลือกคนละคนหลังโหลด save
"""
import contextlib
import hashlib
import io
import os
import tempfile

from tiandao import persist as P
from tiandao import sim as S

SEED = 7
WARM = 12000
MORE = 4000


def digest(sim, n=1500):
    h = hashlib.sha256()
    for e in sim.log[-n:]:
        h.update(f"{e.day}|{e.kind}|{e.outcome}|{e.actor}|{e.target}|{e.text}".encode())
    return h.hexdigest()[:16]


# field ที่ migration ของเซฟเก่าเคยเขียนทับ — ถ้าการโหลดเซฟ "รุ่นปัจจุบัน" แตะอะไรในนี้
# แปลว่าการโหลดกลายเป็นการแก้โลก ไม่ใช่การอ่านโลก แล้วอนาคตจะแยกทางจากรันรวดเดียวทันที
# (วัดจริงก่อนแก้: mastery เปลี่ยน 15 คน · bloodline_affinity เปลี่ยน 36 คน · แยกทางใน 333 เหตุการณ์)
MIGRATED_FIELDS = ("mastery", "bloodline_affinity", "element", "birth_wid", "skills",
                   "emotions", "desires", "bloodline_blessings", "bloodline_buff",
                   "natural_lifespan", "longevity_bonus", "mat_stock", "wants")


def _freeze(value):
    if isinstance(value, dict):
        return tuple(sorted((k, _freeze(v)) for k, v in value.items()))
    if isinstance(value, list):
        return tuple(_freeze(v) for v in value)
    return value


def snapshot(sim):
    """สถานะที่การโหลดเซฟรุ่นปัจจุบันห้ามเปลี่ยนแม้แต่ค่าเดียว"""
    return {
        "rng": sim.rng.getstate(),
        "day": sim.day,
        "seq": sim.seq,
        "queue": sorted(sim.queue),
        "cast": {c.cid: tuple(_freeze(getattr(c, f, None)) for f in MIGRATED_FIELDS)
                 for c in sim.cast},
        "apex": dict(getattr(sim, "apex_blessings", {})),
    }


def check_load_preserved_state(before, loaded):
    """โหลดแล้วต้องได้โลกเดิมเป๊ะ — ก่อนจะพูดถึงการเดินต่อด้วยซ้ำ"""
    after = snapshot(loaded)
    assert after["rng"] == before["rng"], "โหลดแล้ว RNG หลักขยับ"
    assert after["day"] == before["day"] and after["seq"] == before["seq"]
    assert after["queue"] == before["queue"], "โหลดแล้วคิวเหตุการณ์ไม่เหมือนเดิม"
    assert len(before["queue"]) == len({cid for _d, cid in before["queue"]}),         "คิวมีใบซ้ำต่อคน — ต้องแก้ที่ตัวสร้างคิว ไม่ใช่ซ่อมเงียบๆ ตอนโหลด"
    changed = {}
    for cid, values in before["cast"].items():
        if after["cast"].get(cid) != values:
            for name, old_v, new_v in zip(MIGRATED_FIELDS, values, after["cast"][cid]):
                if old_v != new_v:
                    changed[name] = changed.get(name, 0) + 1
    assert not changed, f"โหลดเซฟรุ่นปัจจุบันแล้วข้อมูลเปลี่ยน: {changed}"
    assert after["apex"] == before["apex"], "โหลดแล้วพรของผู้สูงสุดเปลี่ยน"
    print(f"  ✓ โหลดแล้วสถานะไม่ขยับเลย ({len(before['cast']):,} ตัวละคร · "
          f"{len(MIGRATED_FIELDS)} field ที่ migration เคยแตะ)")


def run(steps, seed=SEED):
    sim = S.Sim(seed=seed, tiers=3)
    with contextlib.redirect_stdout(io.StringIO()):
        for _ in range(steps):
            sim.step()
    return sim


def main():
    print(f"=== 1. seed เดียวกัน รันสองครั้ง ต้องได้โลกเดียวกัน ({WARM:,} เหตุการณ์) ===")
    a, b = run(WARM), run(WARM)
    print(f"  A {digest(a)} | B {digest(b)}")
    assert digest(a) == digest(b), "seed เดียวกันแต่ได้ผลต่างกัน"
    assert a.day == b.day and len(a.alive_cids) == len(b.alive_cids)
    print(f"  ✓ ตรงกัน (วันที่ {a.day:,} · มีชีวิต {len(a.alive_cids)})")

    print(f"\n=== 2. เซฟ → โหลด → เดินต่ออีก {MORE:,} ต้องเท่ากับรันรวดเดียว ===")
    tmp = os.path.join(tempfile.mkdtemp(), "t.save")
    P.save_sim(a, tmp)
    print(f"  ไฟล์ save {os.path.getsize(tmp)/1024:.0f} KB")
    before = snapshot(a)
    loaded = P.load_sim(tmp)
    assert loaded.day == a.day, "โหลดกลับมาแล้ววันที่ไม่ตรง"
    assert len(loaded.alive_cids) == len(a.alive_cids), "โหลดกลับมาแล้วประชากรไม่ตรง"
    check_load_preserved_state(before, loaded)
    with contextlib.redirect_stdout(io.StringIO()):
        for _ in range(MORE):
            loaded.step()
    straight = run(WARM + MORE)
    print(f"  เดินต่อจาก save {digest(loaded)}")
    print(f"  รันรวดเดียว     {digest(straight)}")
    assert digest(loaded) == digest(straight), (
        "รันต่อจาก save แล้วโลกเดินคนละทางกับรันรวดเดียว — "
        "มักเกิดจากการวนบน set/dict ที่ลำดับเปลี่ยนหลัง unpickle")
    print("  ✓ ตรงกันเป๊ะ — รันต่อจาก save ได้โดยผลไม่เพี้ยน")


if __name__ == "__main__":
    main()
    print("\n✓ โลกเดินซ้ำได้ทั้งจาก seed และจาก save")
