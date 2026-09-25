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
from tiandao import persist as PS
from tiandao import tuning as TN
from tiandao import worldloop as WL
from tiandao.ai import config_ai as ACFG


def load_or_create(cfg):
    """ห่อ WL.load_or_create ไว้เพื่อให้ยังพิมพ์บรรทัดเดิมออกทางเทอร์มินัลเหมือนก่อน"""
    sim, created = WL.load_or_create(cfg)
    if created:
        print(f"[daemon] ไม่พบ {cfg.save_path} — สร้างโลกใหม่จาก seed {cfg.seed}")
    else:
        print(f"[daemon] เดินต่อจาก {cfg.save_path} — วันที่ {sim.day} (ปีที่ {sim.day // 365})")
    return sim


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

    # ตรรกะหนึ่งรอบอยู่ใน tiandao/worldloop.py ชุดเดียว ใช้ร่วมกับปุ่ม "เดินโลก" บนหน้าเว็บ
    # (dashboard.py) — ไฟล์นี้เหลือหน้าที่แค่แปลง argparse เป็น LoopConfig แล้วรายงานผลออกเทอร์มินัล
    cfg = WL.LoopConfig(
        save_path=a.save_path, event_log_path=a.event_log_path, seed=a.seed, tiers=a.tiers,
        chunk_events=a.chunk_events, interval=a.interval, lr=a.lr,
        autotune=not a.no_autotune, trim_log=not a.no_trim_log,
        keep_recent_events=a.keep_recent_events,
        llm=a.llm, llm_drain_budget=a.llm_drain_budget,
    )

    state = TN.load_state()
    if state.get("overrides"):
        TN.apply_overrides(state["overrides"])

    sim = load_or_create(cfg)

    it = save_failures = 0
    try:
        while a.iterations <= 0 or it < a.iterations:
            it += 1
            r = WL.run_round(sim, cfg, state)
            if not r["saved"]:
                print(f"[daemon] รอบ {it}: เซฟไม่สำเร็จ ({r['save_error']}) — ไฟล์เซฟเดิมยังอยู่ครบ จะลองใหม่รอบหน้า")
            save_failures = WL.check_saved(r, save_failures)

            log_note = (f" | flush log +{r['log_flushed']} "
                        f"(world.save เหลือ {r['log_kept']} เหตุการณ์)") if not a.no_trim_log else ""
            llm_note = (f" | LLM: ประมวลผล {r['llm_drained']} งาน "
                        f"(ค้าง {r['llm_backlog']})") if a.llm else ""
            print(f"[daemon] รอบ {it}: วัน {r['day_from']}->{r['day_to']} (ปี {r['year']}) "
                  f"| มีชีวิต {r['alive']} | advancement={r['advancement_rate']:.3f} "
                  f"| org_rate={r['org_rate']:.2f}{log_note}{llm_note}")

            if r.get("exhausted"):
                raise RuntimeError(
                    "Simulation scheduler exhausted; the latest state was saved. "
                    "Inspect the save before restarting the daemon."
                )

            if a.iterations <= 0 or it < a.iterations:
                time.sleep(max(0.0, a.interval))
    except KeyboardInterrupt:
        print("\n[daemon] ได้รับ Ctrl+C — บันทึกสถานะก่อนออก...")
        if not a.no_trim_log:
            EL.flush_and_trim(sim, cfg.log_path(), a.keep_recent_events)
        PS.save_sim(sim, a.save_path)
        print(f"[daemon] บันทึกไว้ที่ {a.save_path} แล้ว เดินต่อได้ด้วย python daemon.py (ใช้ไฟล์เดิม) "
              f"— งาน LLM ที่ยังค้างอยู่ในคิว (ถ้ามี) จะถูกบันทึกไว้ด้วย ทำต่อได้ตอน resume")


if __name__ == "__main__":
    main()
