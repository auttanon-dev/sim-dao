# -*- coding: utf-8 -*-
"""Phase E/F — Dataset Export CLI: สร้าง training dataset จากโลกที่เซฟไว้แล้ว แบบ incremental

ดีฟอลต์เป็น incremental เสมอ (Phase F): รันซ้ำบนโลกที่โตขึ้น (daemon.py เดินต่อแล้ว --save ทับ) จะ
export "เฉพาะฉากใหม่" เป็น v{N} ถัดไป ไม่ประมวลผล/เขียนของเดิมซ้ำ — เอา v1..vN มารวมกันถึงจะได้
dataset เต็ม (state เก็บไว้ที่ datasets/export_state.json)

    python run.py --seed 1 --events 20000 --save      # ให้โลกมีประวัติสะสมก่อน
    python build_dataset.py                            # export v1 (ฉากทั้งหมดที่มี ครั้งแรกไม่มี state)
    python daemon.py --chunk-events 20000 --iterations 5 --save-path tiandao/world.save
    python build_dataset.py                            # export v2 (เฉพาะฉากใหม่จาก 5 รอบที่เพิ่งเดิน)
    python build_dataset.py --full                      # บังคับ export ฉากทั้งหมดใหม่ทั้งก้อน (ไม่สน state)
    python build_dataset.py --llm --llm-limit 5         # ให้ Ollama เขียน Dataset A จริง 5 ฉากแรก (ของใหม่)
"""
import argparse
import os
import sys

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from narrative_factory import exporter as EX
from narrative_factory import incremental as INC
from narrative_factory import parser as P
from narrative_factory import scene_extractor as SE
from tiandao import event_log as EL
from tiandao import persist as PS
from tiandao.ai import config_ai as ACFG
from tiandao.ai import llm_agent as LLM


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--save-path", default=None, help="ดีฟอลต์ tiandao/persist.DEFAULT_PATH")
    ap.add_argument("--event-log-path", default=None,
                     help="ดีฟอลต์ {save-path}.events.jsonl (Phase G) — ต้องระบุถ้า daemon.py เคย "
                          "flush+trim log แล้ว ไม่งั้นจะเห็นแค่เหตุการณ์ล่าสุดที่เหลือใน world.save "
                          "ไม่ใช่ประวัติเต็ม")
    ap.add_argument("--out", default=".", help="โฟลเดอร์แม่ที่มี/จะสร้าง datasets/ ข้างใน")
    ap.add_argument("--full", action="store_true",
                     help="บังคับ export ฉากทั้งหมดใหม่ทั้งก้อน ไม่สน export_state.json เดิม "
                          "(ปกติใช้ตอนอยากได้ snapshot เต็มสักครั้ง ไม่ใช่ทุกครั้ง)")
    ap.add_argument("--llm", action="store_true", help="ให้ Ollama เขียน Dataset A จริงบางส่วน")
    ap.add_argument("--llm-limit", type=int, default=5,
                     help="จำนวนฉากสูงสุดที่จะเรียก Ollama จริง (ที่เหลือใช้ template — ช้า+เสี่ยงหลอน "
                          "ถ้าเปิดเยอะ ดู CULTIVATOR_BRAIN_STATUS.md ประกอบการตัดสินใจ)")
    a = ap.parse_args()

    save_path = a.save_path or PS.DEFAULT_PATH
    try:
        sim = PS.load_sim(save_path)
    except FileNotFoundError:
        print(f"ไม่พบไฟล์ {save_path} — รัน `python run.py --save` ก่อน")
        return

    event_log_path = a.event_log_path or EL.default_log_path(save_path)
    parsed = P.parse_log(sim, event_log_path)
    scenes = SE.extract_scenes(parsed, sim)
    by_cid = SE.index_by_character(parsed)
    print(f"[build_dataset] {len(parsed)} เหตุการณ์ -> {len(scenes)} ฉากทั้งหมดในโลกนี้ "
          f"(รวม log ที่ flush ไปแล้ว: {os.path.exists(event_log_path)})")

    cfg = P.load_config()
    datasets_dir = os.path.join(a.out, cfg.get("datasets_dir", "datasets"))

    if a.full:
        new_scenes = scenes
        state = INC.load_state(datasets_dir)
        print("[build_dataset] --full: export ฉากทั้งหมดใหม่ทั้งก้อน (ไม่สน state เดิม)")
    else:
        state = INC.load_state(datasets_dir)
        new_scenes = INC.select_new_scenes(scenes, state.last_exported_seq)
        print(f"[build_dataset] incremental: เคย export ถึง seq {state.last_exported_seq} แล้ว "
              f"-> ฉากใหม่ {len(new_scenes)}/{len(scenes)}")

    if not new_scenes:
        print("[build_dataset] ไม่มีฉากใหม่ตั้งแต่ export ครั้งก่อน — ไม่สร้างเวอร์ชันใหม่ (โลกยังไม่โต "
              "ขึ้นพอ ลอง run.py/daemon.py --save เพิ่มก่อน)")
        return

    # Dataset A เป็นร้อยแก้วบรรยายฉาก — ใช้โมเดลสายสำนวนเหมือน history.py
    agent = LLM.OllamaAgent(model=ACFG.OLLAMA_PROSE_MODEL) if a.llm else None
    if a.llm:
        print(f"[build_dataset] เปิด --llm จำกัดที่ {a.llm_limit} ฉากแรก (ที่เหลือใช้ template)")

    version_dir = EX.export_all(new_scenes, sim, by_cid, a.out, world_seed=sim.seed,
                                 total_events=len(parsed), agent=agent, llm_limit=a.llm_limit)

    if a.full:
        # --full คือ snapshot เต็มแบบ ad-hoc ("ไม่สน state เดิม") — ต้องไม่แตะ export_state.json เลย
        # ไม่งั้นฉากเดิมที่ export ซ้ำจะถูกนับเป็น "ฉากใหม่" อีกรอบใน history ทำให้
        # autotrain.py (Phase H) นับ accumulated_scene_count พองเกินจริง (บั๊กจริงที่เจอตอนทดสอบ
        # Phase I — รัน --full ซ้ำสองครั้งเพื่อสร้าง DPO pair ทำให้ scene_count ในนับซ้ำ 1,731 ฉาก
        # เดิมเป็น 2 เท่า)
        print(f"[build_dataset] เขียนเสร็จที่ {version_dir} ({len(new_scenes)} ฉาก) — "
              f"--full ไม่อัปเดต export_state.json (เป็น snapshot แยก ไม่นับสะสมเป็นฉากใหม่)")
    else:
        INC.record_export(state, version_dir, new_scenes)
        INC.save_state(datasets_dir, state)
        print(f"[build_dataset] เขียนเสร็จที่ {version_dir} ({len(new_scenes)} ฉากใหม่) — "
              f"state อัปเดตแล้ว (last_exported_seq={state.last_exported_seq})")


if __name__ == "__main__":
    main()
