# -*- coding: utf-8 -*-
"""Phase K7 — Lesson Export CLI: สร้าง StoryLesson (K1) + StoryArc (K5) จากโลกจริงทั้งหมด บวก
StyleLesson (K6) จาก Novel_Episodes จำนวนจำกัด (LLM ช้า+เสี่ยงคัดลอก จำกัดด้วย --style-limit) แล้ว
export ทั้งหมดเป็น ChatML ลง datasets/lessons_v1/

    python run.py --seed 1 --events 20000 --save
    python build_lessons.py --style-limit 5 --novel-episodes-dir "G:/My Drive/Project/My_AI_Second_Brain/Novel_Episodes"
    python build_lessons.py                    # ข้าม K6 ถ้าไม่ระบุ --novel-episodes-dir
"""
import argparse
import glob
import os
import sys

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from narrative_factory import arc_builder as AB
from narrative_factory import lesson_exporter as LE
from narrative_factory import parser as P
from narrative_factory import scene_extractor as SE
from narrative_factory import style_distill as SD
from narrative_factory import teacher as T
from tiandao import event_log as EL
from tiandao import persist as PS
from tiandao.ai import llm_agent as LLM


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--save-path", default=None, help="ดีฟอลต์ tiandao/persist.DEFAULT_PATH")
    ap.add_argument("--event-log-path", default=None)
    ap.add_argument("--out", default=".", help="โฟลเดอร์แม่ที่มี/จะสร้าง datasets/ ข้างใน")
    ap.add_argument("--novel-episodes-dir", default=None,
                     help="โฟลเดอร์ Novel_Episodes จริง (ไม่ใส่ = ข้าม Style Distillation K6 ทั้งหมด)")
    ap.add_argument("--style-limit", type=int, default=5,
                     help="จำนวนตอนสูงสุดที่จะยิง Ollama วิเคราะห์ (ช้า+เสี่ยงคัดลอก ดีฟอลต์ 5 ตอน)")
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
    cfg = P.load_config()
    print(f"[build_lessons] {len(scenes)} ฉากจริงในโลกนี้")

    story_lessons = [T.build_story_lesson(s, cfg) for s in scenes]
    print(f"[build_lessons] สร้าง StoryLesson (K1) จริง {len(story_lessons)} ฉาก")

    story_arcs = AB.build_all_arcs(scenes, sim, cfg)
    print(f"[build_lessons] สร้าง StoryArc (K5) จริง {len(story_arcs)} อาร์ค")

    style_lessons = []
    if a.novel_episodes_dir:
        episode_paths = sorted(glob.glob(os.path.join(a.novel_episodes_dir, "EPISODE_*.md")))[:a.style_limit]
        agent = LLM.OllamaAgent()
        sim_ref = SD.format_sim_reference(
            lesson=story_lessons[0] if story_lessons else None,
            arc=story_arcs[0] if story_arcs else None)
        for path in episode_paths:
            with open(path, encoding="utf-8") as f:
                text = f.read()
            label = os.path.basename(path)
            print(f"[build_lessons] วิเคราะห์รูปแบบจริง {label} ผ่าน Ollama (อาจใช้เวลาสักครู่)...")
            lesson = SD.distill_style(text, agent, source_label=label, sim_reference=sim_ref)
            if lesson is not None:
                style_lessons.append(lesson)
            else:
                print(f"[build_lessons] ข้าม {label} (parse fail หรือตรวจพบคัดลอกข้อความ)")
        print(f"[build_lessons] สร้าง StyleLesson (K6) จริง {len(style_lessons)}/{len(episode_paths)} ตอน")
    else:
        print("[build_lessons] ไม่ได้ระบุ --novel-episodes-dir — ข้าม Style Distillation (K6) ทั้งหมด")

    out_dir = LE.export_lessons(story_lessons, scenes, story_arcs, style_lessons, sim,
                                 base_dir=a.out, config=cfg)
    print(f"[build_lessons] เขียนเสร็จที่ {out_dir}")


if __name__ == "__main__":
    main()
