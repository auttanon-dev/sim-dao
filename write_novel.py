# -*- coding: utf-8 -*-
"""Phase L — Novel Writer CLI: เขียนนิยายทั้งเรื่องจากชีวิตตัวละครหนึ่งคนในโลกที่เซฟไว้แล้ว

ต่างจาก `generate_episode.py` (Phase 6) ตรงเจตนา ไม่ใช่แค่ตรงขนาด:
  - `generate_episode.py` ขอ **ร้อยแก้วก้อนเดียว** จากฉากเด่นไม่กี่ฉาก ได้ "ตอนสรุป" หนึ่งตอน
  - ไฟล์นี้เดินผ่าน **จุดเปลี่ยนจริงทุกจุดของชีวิตคนนั้น** (scene_extractor) แล้วกางแต่ละจุดเป็น
    ฉากเต็ม 5 บีต ผ่าน 4 pass ของ `narrative_factory/writer.py` — หนึ่งจุดเปลี่ยน = หนึ่งบท

    python run.py --seed 1 --events 200000 --save        # ให้โลกมีประวัติสะสมก่อน
    python write_novel.py --dry                           # ดูโครงนิยายโดยไม่เรียกโมเดลเลย (เร็ว)
    python write_novel.py --cid 42 --chapters 20          # เขียนจริง

ความช้าเป็นเรื่องที่ยอมรับไว้แล้วโดยตั้งใจ: หนึ่งบทเรียกโมเดล 9 ครั้งเป็นอย่างน้อย (โครง 1 + บทสนทนา 3
+ ร้อยแก้ว 5) ยังไม่รวมรอบซ่อม — แลกกับฉากที่มีบทสนทนาจริงและยาวพอจะเรียกว่าฉาก แทนที่จะเป็นย่อหน้าสรุป
"""
import argparse
import os
import sys
import time

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from tiandao import event_log as EL
from tiandao import persist as PS
from tiandao.ai import config_ai as ACFG
from tiandao.ai import llm_agent as LLM

from narrative_factory import context_builder as CB
from narrative_factory import parser as P
from narrative_factory import scene_cast as SCAST
from narrative_factory import scene_extractor as SE
from narrative_factory import writer as W


def pick_cid(sim, log, min_points):
    """เลือกชีวิตที่มีจุดเปลี่ยนมากที่สุด — ไม่ใช้ story.rank เพราะอันนั้นวัดความ "เก่ง" ไม่ใช่ความ
    "มีเรื่องให้เล่า" คนที่ข้ามขั้นรวดเดียวจนสุดโดยไม่เคยเสียอะไรเลยไม่ใช่นิยาย"""
    cands = SCAST.novel_candidates(log, sim, min_points=min_points)
    return (cands[0][0], len(cands[0][1]), len(cands)) if cands else (None, 0, 0)


def chapter_heading(n: int, pkg: W.ScenePackage) -> str:
    where = pkg.place_name if pkg.building in ("", "-") else f"{pkg.place_name} · {pkg.building}"
    change = (" — " + " ".join(pkg.changes)) if pkg.changes else ""
    return f"## บทที่ {n} · {pkg.scene_type_th}{change}\n\n*ปีที่ {pkg.year} {pkg.season} · {where}*"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--save-path", default=PS.DEFAULT_PATH)
    ap.add_argument("--event-log-path", default=None,
                    help="ดีฟอลต์ {save-path}.events.jsonl — ให้ประวัติเต็มถ้า daemon.py เคย trim log")
    ap.add_argument("--cid", type=int, default=None,
                    help="ตัวละครที่จะเขียนเป็นนิยาย — ไม่ใส่ = เลือกคนที่มีจุดเปลี่ยนมากที่สุด")
    ap.add_argument("--chapters", type=int, default=0, help="0 = เขียนทุกจุดเปลี่ยน")
    ap.add_argument("--min-points", type=int, default=SCAST.MIN_TURNING_POINTS)
    ap.add_argument("--target-chars", type=int, default=ACFG.SCENE_TARGET_CHARS,
                    help="ความยาวเป้าหมายต่อหนึ่งบท (ตัวอักษรไทย)")
    ap.add_argument("--prose-model", default=ACFG.OLLAMA_PROSE_MODEL)
    ap.add_argument("--structure-model", default=ACFG.OLLAMA_STRUCTURE_MODEL)
    ap.add_argument("--dry", action="store_true",
                    help="ไม่เรียกโมเดลเลย — ได้โครงนิยาย (บท/ฉาก/ผู้ร่วม/สิ่งที่เปลี่ยน) ไว้ตรวจก่อนจ่าย GPU")
    ap.add_argument("--out", default="out/novels")
    a = ap.parse_args()

    try:
        sim = PS.load_sim(a.save_path)
    except FileNotFoundError:
        print(f"ไม่พบไฟล์ {a.save_path} — รัน `python run.py --save` หรือ `python daemon.py` ก่อน")
        return

    cfg = P.load_config()
    parsed = P.parse_log(sim, a.event_log_path or EL.default_log_path(a.save_path))
    if not parsed:
        print("log ว่างเปล่า — ไม่มีอะไรให้เขียน")
        return

    cid = a.cid
    if cid is None:
        cid, n_points, n_cands = pick_cid(sim, parsed, a.min_points)
        if cid is None:
            print(f"ไม่มีชีวิตไหนมีจุดเปลี่ยนถึง {a.min_points} จุด — รันซิมให้ยาวกว่านี้ก่อน")
            return
        print(f"[novel] เลือกอัตโนมัติจาก {n_cands} ชีวิตที่คู่ควร: cid={cid} ({n_points} จุดเปลี่ยน)")

    name = next((c.name for c in sim.cast if c.cid == cid), str(cid))
    scenes = [s for s in SE.extract_scenes(parsed, sim, cfg) if s.focal_cid == cid]
    if not scenes:
        print(f"ไม่พบฉากของ [{name}] cid={cid} เลย")
        return
    if a.chapters > 0:
        scenes = scenes[:a.chapters]

    by_cid = SE.index_by_character(parsed)
    presence = SCAST.Presence(parsed)   # log เต็ม ไม่ใช่ sim.log ที่ถูก trim (ดู studio.py)
    agent = None if a.dry else LLM.OllamaAgent(model=a.prose_model, timeout=ACFG.SCENE_PASS_TIMEOUT)
    scribe = W.SceneWriter(agent=agent, structure_model=a.structure_model,
                           prose_model=a.prose_model)

    print(f"[novel] [{name}] cid={cid} — {len(scenes)} บท"
          + (" (โหมดแห้ง ไม่เรียกโมเดล)" if a.dry else
             f" · โครง {a.structure_model} · ร้อยแก้ว {a.prose_model}"))

    parts = [f"# {name}\n"]
    total_chars = calls = flagged = 0
    t0 = time.time()
    for i, scene in enumerate(scenes, 1):
        ctx_map = CB.build_scene_context(scene, sim, by_cid, cfg)
        pkg = W.build_package(scene, sim, ctx_map, by_cid.get(cid, []),
                              presence=presence, config=cfg)
        pkg.target_chars = a.target_chars
        script = scribe.write(pkg)
        issues = script.issues + [f"{b.stage}: {x}" for b in script.beats for x in b.issues]
        if issues:
            flagged += 1
        total_chars += len(script.prose)
        calls += script.calls
        parts.append(chapter_heading(i, pkg))
        parts.append(script.prose if script.prose.strip() else
                     "\n".join(f"- {e}" for e in pkg.events))
        rewrites = sum(b.rewrites for b in script.beats)
        print(f"  บทที่ {i:>3}/{len(scenes)} {pkg.scene_type_th:<12} "
              f"{len(script.prose):>6} ตัวอักษร | บทพูด {script.dialogue_count:>2} | "
              f"เรียก {script.calls:>2} | ซ่อม {rewrites} | "
              + (f"ค้าง {len(issues)} ข้อ: {issues[0][:60]}" if issues else "ผ่าน"))

    os.makedirs(a.out, exist_ok=True)
    tag = "dry" if a.dry else a.prose_model.replace(":", "-").replace("/", "-")
    path = os.path.join(a.out, f"novel_{cid}_{name}_{tag}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n\n".join(parts))

    mins = (time.time() - t0) / 60
    print(f"\n[novel] {len(scenes)} บท {total_chars:,} ตัวอักษร "
          f"(เฉลี่ย {total_chars // max(1, len(scenes)):,} ตัวอักษร/บท) "
          f"| เรียกโมเดล {calls} ครั้ง | {mins:.1f} นาที")
    if flagged:
        print(f"[novel] {flagged} บทยังมีข้อค้างหลังรอบซ่อม — ดูรายบรรทัดด้านบน")
    print(f"[novel] บันทึกไว้ที่ {path}")


if __name__ == "__main__":
    main()
