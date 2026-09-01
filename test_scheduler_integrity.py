# -*- coding: utf-8 -*-
"""Verification test for a critical scheduler bug found while running a real --llm bootstrap job:

tiandao/sim.py's step() pops a character into the loop variable `ch` (top of the main while-loop),
then much later runs a "Demon Temptation" block every ~30 sim-days that used to write
`for ch in living_now: ...` -- silently SHADOWING the outer `ch`. Every ~30 days, whichever
character happened to be popped from the scheduler queue in that exact step() call had its
identity hijacked: all the code from that point on (through `actor = ch`) operated on some
unrelated character instead, and the real popped character was never rescheduled -- permanently
dropped from the queue with no error, no crash, nothing in the log.

Confirmed via a live run: a fresh seed reliably emptied Sim.queue entirely (0 pending turns for
1,570 still-alive characters) after ~142,000 step() calls, silently halting the simulation forever
(Sim.run() stops the moment step() returns None). This is exactly the kind of failure that would
make a long daemon.py run or a large --llm bootstrap job quietly stop making progress with no
visible sign anything went wrong."""
import sys
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

sys.path.insert(0, str(Path(__file__).resolve().parent))

from tiandao.sim import Sim


def test_alive_characters_always_have_a_pending_turn():
    """หลังรัน step() หลายรอบ (ครอบคลุมการทำงานของบล็อก 30 วันหลายครั้งแน่ๆ) ตัวละครที่ยังไม่ตาย
    ทุกคนต้องมี entry ค้างอยู่ใน queue เสมอ (เทิร์นถัดไปของตัวเอง) -- ห้ามมีใครหลุดจากคิวไปเฉยๆ"""
    sim = Sim(seed=7, tiers=1)
    sim.last_disaster_day = -1000  # บังคับให้บล็อก 30 วัน (จุดที่มีบั๊ก) ทำงานตั้งแต่ step() แรกแน่ๆ

    for _ in range(300):
        if sim.step() is None:
            break

    queued_cids = {cid for _, cid in sim.queue}
    stranded = sim.alive_cids - queued_cids
    assert not stranded, (
        f"ตัวละครที่ยังมีชีวิตอยู่แต่หลุดจากคิว scheduler ถาวร (ไม่มี turn ค้างอยู่เลย): {stranded} -- "
        f"นี่คือบั๊ก variable shadowing ('for ch in living_now' ทับ ch ของตัวละครที่ pop จริง) กลับมาอีกแล้ว"
    )
    print(f"  ✓ ตัวละครที่ยังมีชีวิตทั้ง {len(sim.alive_cids)} คน มี turn ค้างอยู่ใน queue ครบทุกคน")


def test_long_run_never_exhausts_queue_prematurely():
    """รันยาวพอที่จะเคยชนบั๊กเดิมจริง (เดิมคิวว่างที่ราว 142,000 step() สำหรับ seed=42) -- ต้องไม่ว่างก่อนถึง
    จุดนั้นอีก มิฉะนั้น Sim.run() จะ 'if step() is None: break' หยุดซิมไปเงียบๆ ทั้งที่ควรรันต่อได้"""
    import os
    import contextlib

    sim = Sim(seed=42, tiers=3)
    CHECK_UPTO = 160000  # เกินจุดที่บั๊กเดิมทำให้คิวว่าง (~142,069) ไปพอสมควร
    with open(os.devnull, "w", encoding="utf-8") as devnull:
        with contextlib.redirect_stdout(devnull):
            for i in range(CHECK_UPTO):
                if sim.step() is None:
                    raise AssertionError(
                        f"คิว scheduler ว่างก่อนเวลาอันควรที่ step()#{i} (day={sim.day}, "
                        f"alive={len(sim.alive_cids)}) -- ตัวละครที่ยังไม่ตายควรมี turn ค้างอยู่เสมอ"
                    )
    print(f"  ✓ รัน {CHECK_UPTO} step() ผ่านจุดที่บั๊กเดิมทำให้คิวว่างไปแล้ว ไม่มีปัญหา "
          f"(day={sim.day}, alive={len(sim.alive_cids)})")


if __name__ == "__main__":
    print("=== ทดสอบความสมบูรณ์ของ scheduler queue (บั๊ก variable shadowing ที่เจอจริง) ===")
    test_alive_characters_always_have_a_pending_turn()
    test_long_run_never_exhausts_queue_prematurely()
    print("\n\U0001f389 SCHEDULER INTEGRITY TESTS PASSED!")
