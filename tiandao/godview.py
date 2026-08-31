# -*- coding: utf-8 -*-
"""God's View (มุมมองพระเจ้า) Lightweight Snapshot Exporter & Timeline Engine.

Converts large simulation state (~90 fields per character for thousands of characters)
into an ultra-compact JSON payload (<200 KB) specifically optimized for high-performance
WebGL / Pixi.js rendering at 60 FPS.
"""
import json
import math
import os
from pathlib import Path
from typing import Dict, List, Any, Optional

from . import config as C
from . import places as PL
from . import geo as GEO
from . import terrain as TERRAIN
from . import rules as R
from . import seasons as SEASONS


def extract_lightweight_snapshot(sim) -> Dict[str, Any]:
    """สกัดเฉพาะฟิลด์ที่จำเป็นสำหรับการเรนเดอร์ WebGL เพื่อความเบาและรวดเร็วสูงสุด (<150 KB)"""
    day = sim.day
    years = day // 365
    season_name, regen_mult, disaster_p, disaster_kind = SEASONS.season_of(day)
    seal_info = R.mara_seal_state(sim)
    
    # 1. ข้อมูลผู้บำเพ็ญที่มีชีวิต (ดึงเฉพาะ 8 fields ที่ต้องใช้แสดงผลและอนิเมชั่น)
    living_chars = []
    for c in sim.living():
        living_chars.append([
            c.cid,                              # 0: id
            c.name,                             # 1: name
            getattr(c, "place", -1),             # 2: current place index
            getattr(c, "travel_dest", -1),       # 3: travel destination place index (-1 if idle)
            c.realm,                            # 4: realm level (0-9)
            getattr(c, "dao", "วิถีดาบ"),        # 5: dao path
            1 if getattr(c, "is_lord", False) else 0, # 6: lord/master flag
            getattr(c, "combat_power", 10.0),   # 7: combat power
        ])
        
    # 2. ข้อมูลสรุปประชากรและสถิติดินแดน
    world_summaries = []
    for w in sim.worlds:
        world_summaries.append({
            "wid": w.wid,
            "name": w.name,
            "tier": w.tier,
            "kind": w.kind,
            "place_key": getattr(w, "place_key", w.tier),
            "ratio": round(w.ratio() * 100, 1),
            "state": w.state(),
            "population": len(sim.living_in(w.wid))
        })
        
    # 3. เหตุการณ์สำคัญล่าสุด (Top Impactful Events)
    recent_events = []
    for e in sim.log[-15:]:
        recent_events.append({
            "day": e.day,
            "kind": e.kind,
            "text": e.text
        })
        
    # 4. ข้อมูลโครงสร้างสถานที่ 182 แห่ง และเส้นทางเชื่อม 356 เส้น
    places_3d = TERRAIN.get_all_places_data()
    
    return {
        "meta": {
            "day": day,
            "years": years,
            "season": season_name,
            "regen_mult": regen_mult,
            "total_population": len(living_chars),
            "total_orgs": len(getattr(sim, "orgs", [])),
            "total_caches": len(getattr(sim, "caches", [])),
            "mara_seal": seal_info,
        },
        "worlds": world_summaries,
        "cultivators": living_chars,
        "recent_events": list(reversed(recent_events)),
        "places": places_3d,
        "edges": [
            {
                "from": e[0],
                "to": e[1],
                "distance": e[2],
                "type": e[3] if len(e) > 3 else "road",
                "traversable": e[4] if len(e) > 4 else True
            }
            for e in GEO.EDGES
        ]
    }


def save_lightweight_snapshot(sim, out_path: str = "out/godview_snapshot.json") -> str:
    """บันทึก Lightweight Snapshot ลงไฟล์ JSON สำหรับ Fast Cache / Polling"""
    payload = extract_lightweight_snapshot(sim)
    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(',', ':'))
    return str(p)


def build_timeline_history(sim) -> Dict[str, Any]:
    """สร้างดัชนี Timeline ประวัติศาสตร์สำหรับ Replay Mode Scrubber"""
    timeline = []
    
    # รวบรวมเหตุการณ์สำคัญจาก Log ทั้งหมด
    milestones = []
    for e in sim.log:
        if e.kind in ("ภัยพิบัติแผ่นดิน", "คลื่นสัตว์อสูร", "ศึกใหญ่", "ทะลวงขั้น", "ดับสูญ", "มหาผนึกมาร"):
            milestones.append({
                "day": e.day,
                "year": e.day // 365,
                "kind": e.kind,
                "text": e.text
            })
            
    return {
        "current_day": sim.day,
        "total_years": sim.day // 365,
        "milestones_count": len(milestones),
        "milestones": milestones[-200:],  # เก็บ 200 เหตุการณ์สำคัญล่าสุดสำหรับ timeline scrubber
    }
