# -*- coding: utf-8 -*-
"""ตรวจว่าปฏิสัมพันธ์อิงตำแหน่งจริง — กันไม่ให้ถอยกลับไปเป็นโลกที่ทุกคนเอื้อมถึงกันหมด

ก่อนแก้: others = living_in(world.wid) คือทุกคนที่ยังไม่ตายทั้งโลก ผลวัดจริงคือ 94.7% ของ
เหตุการณ์ที่มีคู่กรณี เกิดระหว่างคนที่อยู่คนละที่ ห่างกันเฉลี่ย 145 หน่วย (เดินทาง 90 หน่วย
กินเวลา ~28 วัน) — ตำแหน่งไม่มีความหมายทางสังคมเลย

หลังแก้ (Sim.social_pool): ควรกลับด้าน — ส่วนใหญ่ต้องอยู่ที่เดียวกัน ส่วนที่ยังข้ามระยะได้
ต้องมีเหตุผลรองรับ (ศัตรูจองเวร ศิษย์-อาจารย์ สำนัก/ตระกูลเดียวกัน หรือไม่มีใครอยู่แถวนั้นเลย)
"""
import collections
import contextlib
import io

from tiandao import config as C
from tiandao import sim as S

STEPS = 20000
SEED = 2026
MIN_LOCAL_RATIO = 0.70      # อย่างน้อย 70% ของคู่กรณีต้องยืนอยู่ที่เดียวกัน
MIN_JUSTIFIED = 0.95        # ที่ข้ามระยะได้ ต้องมีเหตุผลรองรับอย่างน้อย 95%

# เหตุการณ์ที่ "ตั้งใจข้ามระยะ" — ฝ่ายหนึ่งยกข้ามแดนมาเอง หรือถูกส่งมาตามหน้าที่ ไม่ได้เลือก
# คู่กรณีจาก social_pool การข้ามระยะจึงถูกต้องตามธรรมชาติของมัน ไม่นับเป็นการละเมิดตำแหน่ง
# รายชื่ออยู่ใน config เพราะตัวซิมเป็นฝ่ายประกาศเจตนาของมันเอง ไม่ใช่ให้เทสต์เดาเอง
RAID_KINDS = C.CROSS_PLACE_KINDS


def _place(x):
    """บาง target ไม่ใช่ตัวละคร (หรือ place ยังเป็น None) — นับเป็นไม่มีตำแหน่ง"""
    p = getattr(x, "place", None)
    return p if isinstance(p, int) else -1


def collect():
    rec = []
    orig = S.Sim.emit

    def patched(self, world, kind, actor, target, tags, outcome, text, elapsed,
                deltas=None, **kw):
        if actor is not None and target is not None:
            rec.append((
                kind,
                _place(actor),
                _place(target),
                # สถานะ "ตอนนี้" เชื่อได้เฉพาะเหตุการณ์ที่ไม่แก้ความสัมพันธ์ก่อน emit — "ทรยศ"
                # ตัด bonds ทิ้งก่อนบันทึก "ล้างแค้น" สะสางหนี้ก่อนบันทึก พออ่านสถานะหลัง
                # เหตุการณ์จึงดูเหมือนคนสองคนที่ไม่เคยรู้จักกันเลย (วัดจริง: ทรยศ 51 · ล้างแค้น 1)
                (getattr(target, "cid", None) in actor.bonds
                 or getattr(target, "cid", None) in actor.rivals
                 or getattr(target, "cid", None) == actor.master_cid
                 or getattr(target, "cid", None) in actor.disciples),
                actor.org is not None and actor.org == getattr(target, "org", object()),
                actor.clan >= 0 and actor.clan == getattr(target, "clan", -2),
                len([c for c in self.living_in(world.wid)
                     if c.cid != actor.cid and c.place == actor.place]),
                # ตัวซิมบันทึกเหตุผลไว้ให้แล้วตั้งแต่ก่อนแตะความสัมพันธ์ (ดู Sim.reach_reason)
                bool(isinstance(deltas, dict) and deltas.get(C.PRIOR_TIE_KEY)),
            ))
        return orig(self, world, kind, actor, target, tags, outcome, text, elapsed,
                    deltas, **kw)

    S.Sim.emit = patched
    try:
        sim = S.Sim(seed=SEED, tiers=3)
        with contextlib.redirect_stdout(io.StringIO()):
            for _ in range(STEPS):
                sim.step()
    finally:
        S.Sim.emit = orig
    return sim, rec


def main():
    print(f"รันซิม {STEPS} เหตุการณ์...")
    sim, rec = collect()
    print(f"  วันที่ {sim.day} | มีชีวิต {len(sim.alive_cids)} คน")

    pairs = [r for r in rec if r[1] >= 0 and r[2] >= 0]
    same = [r for r in pairs if r[1] == r[2]]
    far = [r for r in pairs if r[1] != r[2]]
    assert pairs, "ไม่มีเหตุการณ์ที่มีคู่กรณีเลย"

    ratio = len(same) / len(pairs)
    print(f"\n  คู่กรณีทั้งหมด {len(pairs)} ครั้ง")
    print(f"  ยืนอยู่ที่เดียวกัน : {len(same)} ({ratio*100:.1f}%)")
    print(f"  อยู่คนละที่        : {len(far)} ({(1-ratio)*100:.1f}%)")
    assert ratio >= MIN_LOCAL_RATIO, (
        f"ปฏิสัมพันธ์ไม่อิงตำแหน่งพอ — อยู่ที่เดียวกันแค่ {ratio*100:.1f}% "
        f"(ต้องการอย่างน้อย {MIN_LOCAL_RATIO*100:.0f}%)")

    reason = collections.Counter()
    for _k, _a, _b, bonded, org, clan, n_local, prior_tie in far:
        if _k in RAID_KINDS:
            reason["ยกมาบุก/ออกล่าข้ามแดนตามหน้าที่"] += 1
        elif prior_tie:
            reason["ความสัมพันธ์เดิมที่ซิมบันทึกไว้ก่อนเหตุ"] += 1
        elif bonded:
            reason["ศัตรู/มิตร/ศิษย์-อาจารย์"] += 1
        elif org:
            reason["สำนักเดียวกัน"] += 1
        elif clan:
            reason["ตระกูลเดียวกัน"] += 1
        elif n_local == 0:
            reason["ไม่มีใครอยู่แถวนั้นเลย"] += 1
        else:
            reason["ไม่มีเหตุผลรองรับ"] += 1
    print("\n  เหตุผลที่ยังเอื้อมถึงกันข้ามระยะได้:")
    for k, v in reason.most_common():
        print(f"    {k}: {v} ({v/len(far)*100:.0f}%)")

    # เหตุผลที่บันทึกไว้ก่อน mutate ต้องไม่กลายเป็นตะกร้ารับทุกอย่าง — ถ้าคู่ข้ามระยะทุกคู่
    # ถูกตีตราว่า "มีเหตุผล" แปลว่าเกณฑ์หลวมจนตรวจอะไรไม่ได้อีกแล้ว
    tied = sum(1 for r in far if r[7])
    print(f"\n  ในจำนวนที่ข้ามระยะ ซิมบันทึกเหตุผลไว้ก่อนเหตุการณ์ {tied} จาก {len(far)} ครั้ง")
    assert tied < len(far), "คู่ข้ามระยะถูกตีตราว่ามีเหตุผลหมดทุกคู่ — เกณฑ์หลวมเกินไป"

    unjust = reason.get("ไม่มีเหตุผลรองรับ", 0)
    just_ratio = 1.0 - unjust / max(1, len(far))
    assert just_ratio >= MIN_JUSTIFIED, (
        f"มีคู่กรณีข้ามระยะที่ไม่มีเหตุผลรองรับ {unjust} ครั้ง ({(1-just_ratio)*100:.0f}%)")

    print(f"\n✓ ปฏิสัมพันธ์อิงตำแหน่งจริง ({ratio*100:.1f}% อยู่ที่เดียวกัน, "
          f"ที่ข้ามระยะมีเหตุผลรองรับ {just_ratio*100:.0f}%)")


if __name__ == "__main__":
    main()
