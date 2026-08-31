# -*- coding: utf-8 -*-
"""โลกที่เดินไปเองต่อเนื่อง — ทิ้งให้รันในเทอร์มินัล (หรือแปะเข้า Task Scheduler/nohup) แล้วโลกเดินหน้า
ไปเรื่อยๆ เอง ไม่ต้องมีคนสั่ง run.py ใหม่ทุกครั้ง

แต่ละรอบ: เดินต่อจากไฟล์ save (หรือสร้างใหม่ถ้ายังไม่มี) -> รันทีละก้อน -> flush+trim event log
(Phase G) -> เซฟ -> drain คิว LLM ถ้าเปิด --llm (Phase G) -> วัดผลก้อนนั้นแล้วขยับค่าคงที่เข้าหาเป้า
(online tuning เบาๆ ต่อเนื่อง คนละหน้าที่กับ autotune.py ที่ทำ offline แบบ multi-seed ก้อนใหญ่) ->
พักตามช่วงเวลา -> วนต่อ

    python daemon.py                                   # เดินตลอดไปจนกด Ctrl+C
    python daemon.py --iterations 10 --interval 0      # เดิน 10 รอบรวดแล้วจบ
    python daemon.py --chunk-events 50000 --lr 0.05     # ก้อนใหญ่ขึ้น ปรับค่าช้าลง (มั่นคงขึ้น)
    python daemon.py --llm --llm-drain-budget 20        # เปิด Layer 3 จริง จำกัด 20 งาน/รอบ (ไม่บล็อกซิม)
"""
import argparse
import os
import sys
import time

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from tiandao import event_log as EL
from tiandao import metrics as M
from tiandao import persist as PS
from tiandao import tuning as TN
from tiandao.ai import config_ai as ACFG
from tiandao.sim import Sim


def load_or_create(save_path, seed, tiers):
    try:
        sim = PS.load_sim(save_path)
        print(f"[daemon] เดินต่อจาก {save_path} — วันที่ {sim.day} (ปีที่ {sim.day // 365})")
        return sim
    except FileNotFoundError:
        print(f"[daemon] ไม่พบ {save_path} — สร้างโลกใหม่จาก seed {seed}")
        return Sim(seed=seed, tiers=tiers)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=0, help="ใช้ตอนสร้างโลกใหม่ครั้งแรกเท่านั้น")
    ap.add_argument("--tiers", type=int, default=3)
    ap.add_argument("--chunk-events", type=int, default=20000)
    ap.add_argument("--interval", type=float, default=5.0, help="วินาทีที่พักระหว่างรอบ")
    ap.add_argument("--iterations", type=int, default=0, help="0 = เดินตลอดไปจนกด Ctrl+C")
    ap.add_argument("--lr", type=float, default=0.1, help="ความเร็วปรับค่าคงที่ต่อรอบ — เบากว่า autotune.py ตั้งใจ เพราะเป็น online จาก seed เดียว")
    ap.add_argument("--save-path", default=PS.DEFAULT_PATH)
    ap.add_argument("--no-autotune", action="store_true", help="ปิด online tuning ระหว่างเดิน")
    ap.add_argument("--llm", action="store_true",
                     help="เปิด Layer 3 (Ollama) จริงระหว่าง daemon เดิน — (Phase G) sim.run() เองไม่"
                          "บล็อกอีกต่อไป งานเข้าคิวแล้ว drain แยกทีหลังตาม --llm-drain-budget")
    ap.add_argument("--llm-drain-budget", type=int, default=20,
                     help="จำนวนงาน LLM สูงสุดที่ประมวลผลต่อรอบ (0 = ทั้งหมดที่ค้างอยู่ ไม่แนะนำถ้า "
                          "--chunk-events ใหญ่ เพราะงานค้างจะเยอะ) งานที่เหลือรอรอบถัดไปอัตโนมัติ")
    ap.add_argument("--event-log-path", default=None,
                     help="ดีฟอลต์ {save-path}.events.jsonl (Phase G)")
    ap.add_argument("--keep-recent-events", type=int, default=5000,
                     help="จำนวนเหตุการณ์ล่าสุดที่เก็บไว้ใน world.save (Phase G) — ที่เหลือ flush ลง "
                          "event-log-path แทน กัน world.save โตไม่มีเพดาน")
    ap.add_argument("--no-trim-log", action="store_true",
                     help="ปิดการ flush+trim log (Phase G) — กลับไปพฤติกรรมเดิมที่ sim.log สะสมไม่มี "
                          "เพดานใน world.save เอง")
    a = ap.parse_args()

    if a.llm:
        ACFG.LLM_ENABLED = True

    save_dir = os.path.dirname(a.save_path)
    if save_dir:
        os.makedirs(save_dir, exist_ok=True)
    event_log_path = a.event_log_path or EL.default_log_path(a.save_path)

    state = TN.load_state()
    if state.get("overrides"):
        TN.apply_overrides(state["overrides"])

    sim = load_or_create(a.save_path, a.seed, a.tiers)

    it = 0
    try:
        while a.iterations <= 0 or it < a.iterations:
            it += 1
            before_day = sim.day
            sim.run(a.chunk_events)

            log_note = ""
            if not a.no_trim_log:
                flushed = EL.flush_and_trim(sim, event_log_path, a.keep_recent_events)
                log_note = f" | flush log +{flushed} (world.save เหลือ {len(sim.log)} เหตุการณ์)"

            PS.save_sim(sim, a.save_path)

            llm_note = ""
            if a.llm:
                drained = sim.brain_manager.drain_llm_queue(sim, a.llm_drain_budget)
                backlog = len(sim.brain_manager.llm_queue)
                llm_note = f" | LLM: ประมวลผล {drained} งาน (ค้าง {backlog})"

            metrics = M.summarize(sim, a.chunk_events)
            if not a.no_autotune:
                overrides = TN.propose_update(state.get("overrides", {}), metrics, learning_rate=a.lr)
                state["overrides"] = overrides
                TN.save_state(state)

            print(f"[daemon] รอบ {it}: วัน {before_day}->{sim.day} (ปี {sim.day // 365}) "
                  f"| มีชีวิต {len(sim.living())} | advancement={metrics['advancement_rate']:.3f} "
                  f"| org_rate={metrics['org_rate']:.2f}{log_note}{llm_note}")

            if a.iterations <= 0 or it < a.iterations:
                time.sleep(max(0.0, a.interval))
    except KeyboardInterrupt:
        print("\n[daemon] ได้รับ Ctrl+C — บันทึกสถานะก่อนออก...")
        if not a.no_trim_log:
            EL.flush_and_trim(sim, event_log_path, a.keep_recent_events)
        PS.save_sim(sim, a.save_path)
        print(f"[daemon] บันทึกไว้ที่ {a.save_path} แล้ว เดินต่อได้ด้วย python daemon.py (ใช้ไฟล์เดิม) "
              f"— งาน LLM ที่ยังค้างอยู่ในคิว (ถ้ามี) จะถูกบันทึกไว้ด้วย ทำต่อได้ตอน resume")


if __name__ == "__main__":
    main()
