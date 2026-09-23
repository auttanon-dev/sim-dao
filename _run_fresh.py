# -*- coding: utf-8 -*-
"""สร้างโลกใหม่ตั้งแต่ปีที่ 0 แล้วเดินไป 2,000 ปี — กฎชุดปัจจุบันทั้งหมดตั้งแต่ปีแรก

ต่างจาก _run2000.py ตรงที่ไม่เดินต่อจากเซฟเก่าเลย เริ่มจาก seed ใหม่ล้วนๆ เพื่อให้ทั้ง 2,000 ปี
อยู่ภายใต้กฎเดียวกันหมด ไม่มีช่วงไหนที่กติกาต่างจากช่วงอื่น:
  · สายเวลา · สายวัฏจักร (ตายแล้วเกิดใหม่) · สายหุ่นกล · สายเชิดศพ
  · โบนัสสายจิตเพิ่มเพดานหุ่น · พลังคูณ 3 ของสายมิติ/เวลา
  · วงจรเจ้าโกลาหลแบบใหม่ (ฆ่าได้ · ไม่มีอายุขัย · สะสมพลังจากความตาย · ผนึกได้)
  · การแก้บั๊กทั้ง 31 ตัว รวมถึงเจ้าโกลาหลไม่นำทีมปราบตัวเอง

ทนเครื่องดับ: เซฟทุกก้อนแบบอะตอมมิก (persist.save_sim เขียน .tmp แล้ว os.replace) และรันซ้ำได้
เรียกซ้ำเมื่อไหร่ก็เดินต่อจากเซฟล่าสุดเอง
"""
import contextlib
import io
import json
import os
import sys
import time

from tiandao import event_log as EL
from tiandao import persist as PS
from tiandao import sim as S

SEED = 2029
SAVE = "out/fresh2000.save"
LOG = SAVE + ".events.jsonl"
MARK = SAVE + ".started"
CHUNK = 40000
TARGET_DAYS = 2000 * 365

os.makedirs("out", exist_ok=True)

if os.path.exists(MARK) and os.path.exists(SAVE):
    sim = PS.load_sim(SAVE)
    print(f"เดินต่อจากปีที่ {sim.day//365} | {len(sim.worlds)} แดน "
          f"| มีชีวิต {len(sim.alive_cids):,}", flush=True)
else:
    sim = S.Sim(seed=SEED, tiers=3)
    if os.path.exists(LOG):
        os.remove(LOG)
    open(MARK, "w").close()
    print(f"สร้างโลกใหม่ seed={SEED} | {len(sim.worlds)} แดน "
          f"| ประชากรตั้งต้น {len(sim.cast):,}", flush=True)

sim._log_flushed_count = 0
resume_year = sim.day // 365
if sim.day >= TARGET_DAYS:
    print(f"ถึงเป้าแล้ว: ปีที่ {resume_year}", flush=True)
    sys.exit(0)

# ตัดหาง log ที่ล้ำหน้าจุดเซฟ (เหตุการณ์ที่ flush แล้วแต่ยังไม่ถูกเซฟจะถูกสร้างซ้ำตอนเดินต่อ)
if os.path.exists(LOG) and os.path.getsize(LOG) > 0:
    tmp, kept, dropped = LOG + ".trim", 0, 0
    with io.open(LOG, encoding="utf-8") as src, io.open(tmp, "w", encoding="utf-8") as dst:
        for line in src:
            try:
                if json.loads(line).get("day", 0) > sim.day:
                    dropped += 1
                    continue
            except Exception:
                pass
            dst.write(line)
            kept += 1
    os.replace(tmp, LOG)
    if dropped:
        print(f"  ตัดเหตุการณ์ที่ล้ำจุดเซฟทิ้ง {dropped:,} รายการ (เหลือ {kept:,})", flush=True)

t0, events = time.time(), 0
while sim.day < TARGET_DAYS:
    with contextlib.redirect_stdout(io.StringIO()):
        for _ in range(CHUNK):
            if sim.step() is None:
                break
            events += 1
    EL.flush_and_trim(sim, LOG, 5000)
    PS.save_sim(sim, SAVE)
    liv = sim.living()
    lord = sim.cast[sim.lord_cid]
    print(f"  ปีที่ {sim.day//365:>5} | +{events:>9,} เหตุการณ์ | มีชีวิต {len(sim.alive_cids):>6,} "
          f"| แดน {len(sim.worlds):>3} | รอยแยก {sim.worlds[0].rift:>6.1f} "
          f"| มาร {sum(1 for c in liv if getattr(c,'is_demon',False)):>4} "
          f"วิญญาณ {sum(1 for c in liv if getattr(c,'is_spirit',False)):>4} "
          f"หุ่น {sum(getattr(c,'puppets',0) for c in liv):>4} "
          f"เวียนว่าย {sum(1 for c in liv if getattr(c,'cycle_born',False)):>4} "
          f"| เจ้าโกลาหล {'สลาย' if lord.hidden else 'ตื่น'} "
          f"{getattr(sim,'lord_pool',0):>6,.0f} ผนึก {getattr(sim,'lord_seal',0):>5.1f} "
          f"(คืนกลับ {lord.lord_returns}) | {time.time()-t0:>6.0f} วิ", flush=True)

EL.flush_and_trim(sim, LOG, 5000)
PS.save_sim(sim, SAVE)
print(f"จบ: ปีที่ {sim.day//365} | รอบนี้เดินไป {sim.day//365 - resume_year} ปี | "
      f"{events:,} เหตุการณ์ | {time.time()-t0:.0f} วินาที", flush=True)
