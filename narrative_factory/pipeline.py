# -*- coding: utf-8 -*-
"""Narrative Dataset Factory — orchestrator

ตอนนี้ร้อย Phase A (parser.py) + Phase B (scene_extractor.py + genome.py) +
Phase C (context_builder.py + memory_retriever.py) ยัง**ไม่มี** validator.py/scoring.py/tagger.py/
exporter.py (Phase D-F) ตาม ROLE.md ที่สั่งไม่ให้สร้างทุกอย่างพร้อมกัน แต่ละ Phase ต้อง build ผ่าน
ก่อนค่อยต่อ Phase ถัดไป

รันตรงๆ เพื่อพิสูจน์ว่า Phase A+B+C ทำงานถูกต้องบนโลกที่เซฟไว้แล้ว:
    python -m narrative_factory.pipeline --save-path tiandao/world.save
    python -m narrative_factory.pipeline --demo-cid 42
"""
import argparse
import sys
from collections import Counter
from typing import List

from . import context_builder as CB
from . import parser as P
from . import scene_extractor as SE
from . import scoring as SC
from . import validator as V

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def run_phase_a(sim, event_log_path=None) -> List[P.ParsedEvent]:
    """sim (โหลดจาก tiandao/persist.py) -> List[ParsedEvent] — จุดเดียวที่ Phase B เรียกต่อ
    event_log_path: ถ้า daemon.py เคย flush+trim log แล้ว (Phase G) ต้องส่งมาด้วยถึงจะได้ประวัติเต็ม"""
    return P.parse_log(sim, event_log_path)


def run_phase_b(parsed: List[P.ParsedEvent], sim) -> List[SE.Scene]:
    """List[ParsedEvent] -> List[Scene] พร้อม Narrative Genome ต่อฉาก"""
    return SE.extract_scenes(parsed, sim)


def run_phase_c(scene: SE.Scene, sim, by_cid) -> dict:
    """Scene หนึ่งฉาก -> {cid: CharacterContext} ของผู้เกี่ยวข้องทั้งหมด"""
    return CB.build_scene_context(scene, sim, by_cid)


def _print_check(label: str, text: str, scene, ctx_map, sim, char_log) -> None:
    result = V.validate_candidate(text, scene, ctx_map, sim, char_log)
    score = SC.score_candidate(text, result, scene=scene)
    status = "PASS" if score.passed else "REJECT"
    print(f"  [{label}] {status} score={score.total}/100 {score.breakdown}")
    for v in result.violations:
        print(f"      ✗ {v.rule}: {v.detail}")


def run_phase_d_demo(scenes: List[SE.Scene], sim, by_cid) -> None:
    """พิสูจน์ว่าแต่ละกฎจับผิดได้จริง — สร้าง candidate ที่ผิดทีละกฎ (ทีละอันเท่านั้น) จากข้อมูลจริง
    ของฉากหนึ่ง แล้วให้ validator.py/scoring.py ตัดสิน คนละแนวทางกับการง้อ LLM ให้เขียนเรื่องแล้วมานั่ง
    ลุ้นว่าจะหลอนหรือเปล่า — ที่นี่คุมตัวแปรได้เองว่าอันไหน "ควร" ผิดข้อไหน"""
    # หา scene ที่ตัวโฟกัสมี relationship อย่างน้อย 1 คน เพื่อทดสอบ Rule 6 ได้ครบ
    scene = next((s for s in scenes
                  if by_cid.get(s.focal_cid) and CB.build_context(s, sim, by_cid[s.focal_cid], s.focal_cid).relationship),
                 scenes[0])
    char_log = by_cid.get(scene.focal_cid, [])
    ctx_map = CB.build_scene_context(scene, sim, by_cid)
    focal_ctx = ctx_map[scene.focal_cid]
    focal_name = focal_ctx.name
    real_day = scene.events[0].day
    other_real_day = char_log[0].day if char_log and char_log[0].day != real_day else real_day + 1

    print(f"[phase D demo] ใช้ฉาก [{scene.scene_id}] {scene.scene_type} โฟกัส={focal_name} "
          f"(realm จริง ณ ฉากนี้={focal_ctx.realm_name}) เป็นฐาน")

    good = f"{focal_name} อยู่ที่ขั้น{focal_ctx.realm_name} เมื่อวันที่ {real_day} — {scene.genome.payoff}"
    _print_check("GOOD (ควรผ่าน)", good, scene, ctx_map, sim, char_log)

    stranger = next((c.name for c in sim.cast
                      if c.cid not in scene.participants
                      and c.cid not in {r["cid"] for r in focal_ctx.relationship}
                      and c.name), None)
    if stranger:
        bad1 = f"{good} ขณะนั้น {stranger} ก็ปรากฏตัวขึ้นมาด้วย"
        _print_check("BAD Rule1 (ตัวละครใหม่)", bad1, scene, ctx_map, sim, char_log)

    bad2 = f"{good} แล้วเมื่อวันที่ 99999999 เขาก็ได้พบสมบัติวิเศษ"
    _print_check("BAD Rule2 (วันที่ปลอม)", bad2, scene, ctx_map, sim, char_log)

    later, earlier = max(real_day, other_real_day), min(real_day, other_real_day)
    bad3 = f"{focal_name} เมื่อวันที่ {later} ทำสำเร็จ ย้อนไปวันที่ {earlier} เขาเริ่มต้นเดินทาง"
    _print_check("BAD Rule3 (ลำดับเวลาสลับ)", bad3, scene, ctx_map, sim, char_log)

    misspelled = focal_name[:-1] + ("ก" if focal_name[-1] != "ก" else "ข")
    bad4 = f"{misspelled} อยู่ที่ขั้น{focal_ctx.realm_name} — {scene.genome.payoff}"
    _print_check("BAD Rule4 (สะกดชื่อผิด)", bad4, scene, ctx_map, sim, char_log)

    wrong_realm = next(n for n in V._ALL_REALM_NAMES if n != focal_ctx.realm_name)
    bad5 = f"{focal_name} อยู่ที่ขั้น{wrong_realm} — {scene.genome.payoff}"
    _print_check("BAD Rule5 (ขั้นผิด)", bad5, scene, ctx_map, sim, char_log)

    if focal_ctx.relationship:
        rel = focal_ctx.relationship[0]
        word = "ศัตรู" if rel["score"] >= 0 else "มิตร"
        bad6 = f"{focal_name} มองว่า {rel['name']} เป็น{word}ของเขา — {scene.genome.payoff}"
        _print_check(f"BAD Rule6 (ความสัมพันธ์ขัดจริง, score={rel['score']:+d})",
                     bad6, scene, ctx_map, sim, char_log)


def _print_scene(scene: SE.Scene, sim, by_cid) -> None:
    place_name = None
    if scene.location is not None and scene.location >= 0:
        from tiandao import places as PL
        place_name = PL.PLACES[scene.location][0]
    print(f"  [{scene.scene_id}] {scene.scene_type} วัน {scene.day_start}-{scene.day_end} "
          f"@ {place_name or '?'} | {len(scene.events)} เหตุการณ์ | ผู้เกี่ยวข้อง: {scene.participants}")
    g = scene.genome
    print(f"      genome: conflict={g.conflict_level} dao_theme={g.dao_theme} "
          f"emotion_curve={g.emotion_curve} foreshadowing={g.foreshadowing}")

    ctx_map = run_phase_c(scene, sim, by_cid)
    focal_ctx = ctx_map[scene.focal_cid]
    print(f"      [context ตัวโฟกัส: {focal_ctx.name}]")
    print(f"        realm={focal_ctx.realm_name} ({focal_ctx.realm_source}) | dao={focal_ctx.dao} "
          f"| goal={focal_ctx.current_goal} | emotion={focal_ctx.emotion}")
    print(f"        traits={focal_ctx.traits} fear={focal_ctx.fear:.1f} greed={focal_ctx.greed:.1f} "
          f"compassion={focal_ctx.compassion:.1f}")
    print(f"        reputation(ณ วันนั้น)={focal_ctx.reputation} "
          f"relationship({focal_ctx.relationship_source})={focal_ctx.relationship}")
    print(f"        recent_memory ({len(focal_ctx.recent_memory)} รายการ): "
          f"{focal_ctx.recent_memory[:2]}{'...' if len(focal_ctx.recent_memory) > 2 else ''}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--save-path", default=None, help="ดีฟอลต์ tiandao/persist.DEFAULT_PATH")
    ap.add_argument("--event-log-path", default=None,
                     help="ดีฟอลต์ {save-path}.events.jsonl (Phase G — ให้ประวัติเต็มถ้า daemon.py "
                          "เคย flush+trim log แล้ว)")
    ap.add_argument("--demo-cid", type=int, default=None,
                     help="โชว์ฉากทั้งหมดที่ตัวละคร cid นี้เป็นโฟกัส (สำหรับตรวจสอบด้วยตา)")
    ap.add_argument("--max-scenes", type=int, default=5)
    ap.add_argument("--phase-d-demo", action="store_true",
                     help="พิสูจน์ว่า Validator (Phase D) จับ candidate ที่ผิดแต่ละกฎได้จริง")
    a = ap.parse_args()

    from tiandao import persist as PS
    save_path = a.save_path or PS.DEFAULT_PATH
    try:
        sim = PS.load_sim(save_path)
    except FileNotFoundError:
        print(f"ไม่พบไฟล์ {save_path} — รัน `python run.py --save` ก่อน")
        return

    from tiandao import event_log as EL
    event_log_path = a.event_log_path or EL.default_log_path(save_path)
    parsed = run_phase_a(sim, event_log_path)
    scenes = run_phase_b(parsed, sim)
    by_cid = SE.index_by_character(parsed)

    with_margin = sum(1 for e in parsed if "margin" in e.deltas)
    with_place = sum(1 for e in parsed if e.place >= 0)
    with_realm = sum(1 for e in parsed if e.realm >= 0)
    print(f"[pipeline] Phase A: parse แล้ว {len(parsed)} เหตุการณ์ จากไฟล์ {save_path}")
    print(f"[pipeline]   margin จริง {with_margin} | place จริง {with_place} | realm จริง {with_realm}")
    print(f"[pipeline] Phase B: รวมเป็น {len(scenes)} ฉาก")
    for scene_type, n in Counter(s.scene_type for s in scenes).most_common():
        print(f"      {scene_type:12s} {n}")

    shown = scenes if a.demo_cid is None else [s for s in scenes if s.focal_cid == a.demo_cid]
    print(f"[pipeline] Phase C: ตัวอย่าง context (สูงสุด {a.max_scenes} ฉาก):")
    for scene in shown[:a.max_scenes]:
        _print_scene(scene, sim, by_cid)

    if a.phase_d_demo:
        print("[pipeline] Phase D: พิสูจน์ว่า validator จับแต่ละกฎได้จริง")
        run_phase_d_demo(scenes, sim, by_cid)


if __name__ == "__main__":
    main()
