# -*- coding: utf-8 -*-
"""บันทึกตำนานข้ามรัน — ทุกครั้งที่ run.py จบ ตัวละครเด่นของรันนั้นถูกจดไว้ที่
tiandao/chronicle.json สะสมไปเรื่อยๆ รันครั้งถัดไปดึงมาใช้เป็นข่าวลือเก่าแก่ได้ (ดู Sim.seed_ancient_rumors)"""
import json
import os
from datetime import datetime, timezone

from . import story

DEFAULT_PATH = os.path.join(os.path.dirname(__file__), "chronicle.json")
MAX_RUNS = 30
LEGENDS_PER_RUN = 6


def load(path=DEFAULT_PATH) -> dict:
    if not os.path.exists(path):
        return {"runs": []}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save(state, path=DEFAULT_PATH):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def _legend_entry(score, ch, sim):
    from . import config as C
    status = "ยังอยู่" if ch.alive else f"ตาย — {ch.death_cause}"
    return {
        "cid": ch.cid, "name": ch.name, "race": ch.race(), "dao": ch.dao,
        "archetype": ch.archetype, "origin": ch.origin,
        "peak_realm": C.realm_name(ch.peak_tier, ch.peak_realm),
        "status": status, "score": round(score, 1),
        "kills": ch.kills, "breaks": ch.breaks, "ascends": ch.ascends,
        "treasures": [sim.items[i].name for i in ch.items if sim.items[i].legend],
    }


def record_run(sim, seed, events, path=DEFAULT_PATH) -> dict:
    """เรียกหลังจบรันหนึ่งครั้ง — คัดตัวละครเด่นสุดของรันนั้นจดไว้เป็นตำนาน"""
    state = load(path)
    legends = [_legend_entry(sc, ch, sim) for sc, ch in story.rank(sim, LEGENDS_PER_RUN)]
    worlds = [{"name": w.name, "tier": w.tier, "era": w.era, "state": w.state(),
               "ratio": round(w.ratio(), 3)} for w in sim.worlds if w.kind == "mortal"]
    entry = {
        "seed": seed, "events": events, "day": sim.day, "years": sim.day // 365,
        "recorded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "legends": legends, "worlds": worlds,
        "n_caches": len(sim.caches), "n_orgs": len(sim.orgs),
    }
    state["runs"].append(entry)
    state["runs"] = state["runs"][-MAX_RUNS:]
    save(state, path)
    return entry


def all_legends(path=DEFAULT_PATH, limit=20):
    """ตำนานทั้งหมดจากทุกรันที่เคยบันทึกไว้ เรียงจากเด่นสุด"""
    state = load(path)
    flat = []
    for run in state["runs"]:
        for lg in run["legends"]:
            flat.append({**lg, "seed": run["seed"], "years": run["years"],
                         "recorded_at": run["recorded_at"]})
    flat.sort(key=lambda x: -x["score"])
    return flat[:limit]


def format_hall_of_legends(path=DEFAULT_PATH, limit=15) -> str:
    legends = all_legends(path, limit)
    if not legends:
        return "ยังไม่มีตำนานถูกบันทึกไว้ — ลองรันอย่างน้อยหนึ่งครั้งก่อน (python run.py ...)"
    lines = ["📜 ตำนานที่สะสมมาจากทุกรัน 📜", "=" * 56]
    for i, lg in enumerate(legends, 1):
        lines.append(f"{i:2d}. [{lg['name']}] {lg['race']} · {lg['dao']} · {lg['peak_realm']} "
                      f"(seed {lg['seed']}, ผ่านไป {lg['years']} ปี) — {lg['status']}")
    return "\n".join(lines)
