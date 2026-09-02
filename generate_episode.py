# -*- coding: utf-8 -*-
"""Phase 6 — History Generator CLI: สร้างตอนนิยายหนึ่งตอนจากประวัติของตัวละครในโลกที่เซฟไว้แล้ว

เครื่องมือนี้เรียกแยกจากซิม (ไม่ใช่ระหว่างซิมเดินสด) — ไม่ผูกกับ config_ai.LLM_ENABLED และไม่กระทบ
ความเร็วของ run.py/daemon.py เลย

    python run.py --seed 1 --events 20000 --save     # ให้โลกมีประวัติสะสมก่อน
    python generate_episode.py                        # เลือกตัวละครเด่นสุดอัตโนมัติ (story.rank)
    python generate_episode.py --cid 42                # เจาะจงตัวละคร
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

from tiandao import event_log as EL
from tiandao import persist as PS
from tiandao import story
from tiandao.ai import config_ai as ACFG
from tiandao.ai import history as HIST
from tiandao.ai import llm_agent as LLM


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--save-path", default=PS.DEFAULT_PATH)
    ap.add_argument("--event-log-path", default=None,
                     help="ดีฟอลต์ {save-path}.events.jsonl (Phase G — ให้ประวัติเต็มถ้า daemon.py "
                          "เคย flush+trim log แล้ว)")
    ap.add_argument("--cid", type=int, default=None,
                     help="ตัวละครที่จะเขียนตอน — ไม่ใส่ = เลือกตัวเด่นสุดอัตโนมัติด้วย story.rank")
    ap.add_argument("--max-scenes", type=int, default=None)
    ap.add_argument("--model", default=ACFG.OLLAMA_PROSE_MODEL,
                     help=f"โมเดล Ollama ที่จะใช้ (ดีฟอลต์ {ACFG.OLLAMA_MODEL} ใน config_ai.py) "
                          "ลองตัวอื่นได้ เช่น qwen3-coder:30b, deepseek-r1:8b")
    ap.add_argument("--out", default="out/episodes")
    a = ap.parse_args()

    try:
        sim = PS.load_sim(a.save_path)
    except FileNotFoundError:
        print(f"ไม่พบไฟล์ {a.save_path} — รัน `python run.py --save` หรือ `python daemon.py` ก่อน")
        return

    cid = a.cid
    if cid is None:
        ranked = story.rank(sim, top=1)
        if not ranked:
            print("ไม่มีตัวละครในซิมนี้ให้เลือก")
            return
        _, ch = ranked[0]
        cid = ch.cid
        print(f"[history] เลือกตัวละครเด่นสุดอัตโนมัติ: [{ch.name}] cid={cid}")

    print(f"[history] กำลังเรียก Ollama ({a.model}) สร้างตอน... (อาจใช้เวลาหลายสิบวินาทีถึงหลักนาที)")
    event_log_path = a.event_log_path or EL.default_log_path(a.save_path)
    agent = LLM.OllamaAgent(model=a.model, timeout=ACFG.HISTORY_TIMEOUT)
    text = HIST.generate_episode(sim, cid, max_scenes=a.max_scenes, agent=agent,
                                  event_log_path=event_log_path)

    os.makedirs(a.out, exist_ok=True)
    ch_name = next((c.name for c in sim.cast if c.cid == cid), str(cid))
    model_tag = a.model.replace(":", "-")
    path = os.path.join(a.out, f"episode_{cid}_{ch_name}_{model_tag}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"[history] บันทึกตอนไว้ที่ {path}")


if __name__ == "__main__":
    main()
