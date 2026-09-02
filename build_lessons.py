# -*- coding: utf-8 -*-
"""Phase K7 — Lesson Export CLI: สร้าง StoryLesson (K1) + StoryArc (K5) จากโลกจริงทั้งหมด บวก
StyleLesson (K6) จาก Novel_Episodes จำนวนจำกัด (LLM ช้า+เสี่ยงคัดลอก จำกัดด้วย --style-limit) แล้ว
export ทั้งหมดเป็น ChatML ลง datasets/lessons_v1/

    python run.py --seed 1 --events 20000 --save
    python build_lessons.py --style-limit 5 --novel-episodes-dir "G:/My Drive/Project/My_AI_Second_Brain/Novel_Episodes"
    python build_lessons.py                    # ข้าม K6 ถ้าไม่ระบุ --novel-episodes-dir
"""
import argparse
import dataclasses
import glob
import json
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
from tiandao.ai import config_ai as ACFG
from tiandao.ai import llm_agent as LLM


def _load_style_cache(cache_path: str) -> dict:
    """อ่านผลวิเคราะห์สไตล์ที่ทำไว้แล้วรอบก่อน — คีย์เป็นชื่อไฟล์ตอน (EPISODE_xxx.md)

    Style Distillation คือขั้นที่แพงที่สุดในไฟล์นี้ (วัดจริง ~27 วินาที/ตอน — 500 ตอนคือ ~3.7 ชม.)
    แต่เดิม `export_lessons()` เขียนไฟล์ครั้งเดียวตอนจบ ทำให้ถ้าหยุดกลางคันงานหายทั้งหมด (เคยเสีย
    ไปจริง 133 ตอน) แคชนี้เก็บผลทีละตอนทันทีที่ได้ จึงรันต่อจากเดิมได้เสมอ"""
    cache = {}
    if not os.path.exists(cache_path):
        return cache
    with open(cache_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue  # บรรทัดพังจากการถูกฆ่ากลางคัน — ข้ามไป ถือว่ายังไม่เคยทำตอนนั้น
            if rec.get("source_label"):
                cache[rec["source_label"]] = rec
    return cache


def _append_style_cache(cache_path: str, label: str, lesson) -> None:
    """เขียนต่อท้ายทีละบรรทัดแล้ว flush ทันที — เก็บทั้งกรณีสำเร็จและกรณีถูก reject เพื่อไม่ต้องยิง
    LLM ซ้ำกับตอนที่รู้ผลแล้ว (reject กินเวลาเท่ากับสำเร็จ แต่ได้ผลลัพธ์เป็นศูนย์)"""
    os.makedirs(os.path.dirname(cache_path) or ".", exist_ok=True)
    rec = {"source_label": label, "ok": lesson is not None}
    if lesson is not None:
        rec["lesson"] = dataclasses.asdict(lesson)
    with open(cache_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())


def _distill_all_styles(episode_paths, agent, sim_ref, cache_path, retry_rejected):
    cache = _load_style_cache(cache_path)
    if cache:
        n_ok = sum(1 for r in cache.values() if r.get("ok"))
        print(f"[build_lessons] พบแคชเดิม {len(cache)} ตอน (สำเร็จ {n_ok}) — จะข้ามตอนที่ทำไปแล้ว")

    style_lessons, n_new, n_reused, n_reject = [], 0, 0, 0
    for path in episode_paths:
        label = os.path.basename(path)
        cached = cache.get(label)
        if cached is not None and (cached.get("ok") or not retry_rejected):
            if cached.get("ok"):
                style_lessons.append(SD.StyleLesson(**cached["lesson"]))
                n_reused += 1
            else:
                n_reject += 1
            continue

        with open(path, encoding="utf-8") as f:
            text = f.read()
        print(f"[build_lessons] วิเคราะห์รูปแบบจริง {label} ผ่าน Ollama (อาจใช้เวลาสักครู่)...",
              flush=True)
        lesson = SD.distill_style(text, agent, source_label=label, sim_reference=sim_ref)
        _append_style_cache(cache_path, label, lesson)   # เซฟทันที ก่อนไปตอนถัดไป
        n_new += 1
        if lesson is not None:
            style_lessons.append(lesson)
        else:
            n_reject += 1
            print(f"[build_lessons] ข้าม {label} (parse fail หรือตรวจพบคัดลอกข้อความ)")
    print(f"[build_lessons] StyleLesson: ใช้ได้ {len(style_lessons)} ตอน "
          f"(ยิง LLM ใหม่ {n_new} ตอน, ใช้แคชเดิม {n_reused} ตอน, ถูก reject รวม {n_reject} ตอน)")
    return style_lessons


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--save-path", default=None, help="ดีฟอลต์ tiandao/persist.DEFAULT_PATH")
    ap.add_argument("--event-log-path", default=None)
    ap.add_argument("--out", default=".", help="โฟลเดอร์แม่ที่มี/จะสร้าง datasets/ ข้างใน")
    ap.add_argument("--novel-episodes-dir", default=None,
                     help="โฟลเดอร์ Novel_Episodes จริง (ไม่ใส่ = ข้าม Style Distillation K6 ทั้งหมด)")
    ap.add_argument("--style-limit", type=int, default=5,
                     help="จำนวนตอนสูงสุดที่จะยิง Ollama วิเคราะห์ (ช้า+เสี่ยงคัดลอก ดีฟอลต์ 5 ตอน)")
    ap.add_argument("--style-cache", default=None,
                     help="ไฟล์แคชผลวิเคราะห์สไตล์รายตอน (ดีฟอลต์ {out}/datasets/style_cache.jsonl) — "
                          "เซฟทีละตอนทันที รันซ้ำจะข้ามตอนที่ทำไปแล้ว ไม่ต้องเริ่มใหม่ทั้งหมด")
    ap.add_argument("--retry-rejected", action="store_true",
                     help="ยิง LLM ซ้ำกับตอนที่เคยถูก reject (คัดลอก/parse ไม่ผ่าน) — ดีฟอลต์ข้ามไปเลย "
                          "เพราะการ reject กินเวลาเท่ากับสำเร็จ แต่ผลลัพธ์เป็นศูนย์")
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
        agent = LLM.OllamaAgent(model=ACFG.OLLAMA_STYLE_MODEL)
        sim_ref = SD.format_sim_reference(
            lesson=story_lessons[0] if story_lessons else None,
            arc=story_arcs[0] if story_arcs else None)
        cache_path = a.style_cache or os.path.join(a.out, "datasets", "style_cache.jsonl")
        style_lessons = _distill_all_styles(episode_paths, agent, sim_ref, cache_path,
                                             a.retry_rejected)
    else:
        print("[build_lessons] ไม่ได้ระบุ --novel-episodes-dir — ข้าม Style Distillation (K6) ทั้งหมด")

    out_dir = LE.export_lessons(story_lessons, scenes, story_arcs, style_lessons, sim,
                                 base_dir=a.out, config=cfg)
    print(f"[build_lessons] เขียนเสร็จที่ {out_dir}")


if __name__ == "__main__":
    main()
