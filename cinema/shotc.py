# -*- coding: utf-8 -*-
"""Shot Compiler — bridges the simulation to Blender.

Reads a Tiandao save and emits shot.json: one entry per shot describing what the
camera sees, who is in frame, and how the scene is lit. Blender renders these
deterministically, so the same shot always produces the same image.

This module never mutates the simulation and never consumes simulation RNG.
Presentation only, in the same spirit as tiandao/character_art.py.

    python -m cinema.shotc --out shots.json --cid 42
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tiandao import character_art  # noqa: E402
from tiandao import places as PL  # noqa: E402

# ---------------------------------------------------------------- style guide
# 3D stylized. Every constant here is a deliberate art-direction decision, not a
# simulation value. Change these and every shot in the film changes with them —
# that is the point: one place to steer the look.

STYLE = {
    "name": "wuxia-3d-stylized",
    # Blender resolves this against its own enum; the renderer tolerates a
    # rename, so "eevee" here is safe across versions.
    "render": "eevee",
    "resolution": [1920, 1080],
    "fps": 24,
    # Aspect -> focal length in mm on a 36mm sensor. Long lens compresses space
    # and reads as "epic"; wide lens exaggerates depth and reads as "vast".
    "lens_by_size": {"establish": 24, "wide": 35, "medium": 50, "close": 85},
    "sizes": ["establish", "wide", "medium", "close"],
}

# Place type -> scene archetype. Same type always gets the same dressing, which
# is what stops locations from drifting between shots.
ARCHETYPE_BY_KIND = {
    "สำนัก": "sect_courtyard",
    "เมือง": "town_street",
    "ตลาด": "market_stall",
    "ลานฝึก": "training_ground",
    "แหล่งวัตถุดิบ": "wilderness",
    "แดนต้องห้าม": "forbidden",
    "ประตูมิติ": "realm_gate",
    "ด่านชายแดน": "border_pass",
    "แดนลับ": "hidden_lair",
}

# World -> (sun elevation deg, sun azimuth deg, sun colour, sky top, sky horizon)
# Dawn/dusk sit low; noon is high and neutral; night keeps a moonlit key.
SKY_BY_HOUR = {
    "night": (-0.35, 205, (0.18, 0.22, 0.34), (0.02, 0.03, 0.07), (0.08, 0.10, 0.18)),
    "dawn":  (6.0, 95, (1.0, 0.72, 0.52), (0.28, 0.36, 0.55), (0.98, 0.76, 0.55)),
    "day":   (42.0, 130, (1.0, 0.95, 0.86), (0.36, 0.55, 0.85), (0.80, 0.86, 0.92)),
    "dusk":  (8.0, 262, (1.0, 0.58, 0.34), (0.22, 0.20, 0.38), (0.96, 0.58, 0.40)),
}

# Event kind words -> shot size. Ordered: first match wins.
SIZE_RULES = [
    (("ตาย", "สวรรค์", "บรรลุ", "แปรงธาตุ", "อุบัติภาพ", "ลุกขึ้น"), "close"),
    (("ประลอง", "ต่อสู้", "โจมตี", "ฟาด", "ปราบ", "กระบี่", "เปรียบ", "ศึก"), "wide"),
    (("ตาย", "ฆ่า", "เลือด", "สังหาร"), "close"),
    (("เดินทาง", "เดิน", "ออกจาก", "ค้นพบ", "มาถึง", "กลับ"), "medium"),
]

# Realm -> aura colour and intensity. Cultivator rank is the strongest visual
# signal in the source data, so it drives lighting rather than a written note.
REALM_INFO = {
    0: ("none", 0.0), 1: ("pale_blue", 0.25), 2: ("pale_blue", 0.4),
    3: ("jade", 0.6), 4: ("jade", 0.8), 5: ("violet", 1.0),
    6: ("violet", 1.2), 7: ("gold", 1.5), 8: ("gold", 1.9), 9: ("white", 2.4),
}

# Standard hour to shoot each lighting phase in, when --hour is not given.
PHASE_HOURS = {"dawn": 6, "day": 12, "dusk": 18, "night": 22}


def phase_for_hour(hour: int) -> str:
    """Map a 24h clock hour to a lighting phase.

    day 7-17, dawn 5-7, dusk 17-21, night otherwise.
    """
    h = hour % 24
    if 5 <= h < 7:
        return "dawn"
    if 7 <= h < 17:
        return "day"
    if 17 <= h < 21:
        return "dusk"
    return "night"


def size_for_event(text: str) -> str:
    for words, size in SIZE_RULES:
        if any(w in text for w in words):
            return size
    return "medium"


def size_to_distance(size: str) -> float:
    """Camera distance in metres from the subject."""
    return {"establish": 34.0, "wide": 20.0, "medium": 8.0, "close": 2.6}[size]


def resolve_place(sim, ch) -> Optional[int]:
    """Place index for a character, or None if they are not at a known place."""
    val = getattr(ch, "place", -1)
    if isinstance(val, int) and 0 <= val < len(PL.PLACES):
        return val
    return None


def characters_at(sim, place_idx: int) -> List:
    """Everyone standing at this place, in stable cid order."""
    out = [ch for ch in sim.cast
           if getattr(ch, "alive", True) and resolve_place(sim, ch) == place_idx]
    return sorted(out, key=lambda c: c.cid)


def camera_for(size: str, subject, seed: int) -> Dict:
    """Deterministic camera. Same seed -> same framing, always."""
    dist = size_to_distance(size)
    rng = _hash_unit(seed)
    # Orbit angle per shot size: close-ups sit near eye level and slightly off
    # axis; wide shots lift and drift for a more composed frame.
    angle = {"establish": 25, "wide": 35, "medium": 20, "close": 8}[size]
    theta = math.radians(angle + rng * 20.0)
    height = {"establish": 9.0, "wide": 6.0, "medium": 2.4, "close": 1.65}[size]
    height += (rng - 0.5) * 0.5
    return {
        "size": size,
        "lens_mm": STYLE["lens_by_size"][size],
        "distance_m": round(dist, 3),
        "orbit_deg": round(math.degrees(theta), 2),
        "height_m": round(height, 3),
        # Handheld micro-drift keeps frames from feeling mechanically static.
        "handheld": 0.012 if size in ("medium", "close") else 0.004,
        "dof_fstop": {"establish": 8.0, "wide": 5.6, "medium": 2.8, "close": 1.8}[size],
        "focus_on": "subject" if size == "close" else "auto",
    }


def _hash_unit(*parts) -> float:
    import hashlib
    key = ":".join(str(p) for p in parts)
    return int.from_bytes(hashlib.sha256(key.encode("utf-8")).digest()[:4], "big") / 0xFFFFFFFF


def actor_for(sim, ch, frame_pos: List[float]) -> Dict:
    """Everything Blender needs to place and light one character."""
    age = ch.age(sim.day)
    realm = int(getattr(ch, "realm", 0) or 0)
    aura_name, aura_power = REALM_INFO.get(realm, ("white", 2.4))
    appearance = character_art.appearance_for(ch, sim.day)
    return {
        "cid": ch.cid,
        "name": ch.name,
        # Stable identity: the 3D model this character is permanently bound to.
        "model_id": appearance["id"],
        "gender": getattr(ch, "gender", ""),
        "age": age,
        "age_group": "elder" if age >= 60 else "adult",
        "realm": realm,
        "dao": getattr(ch, "dao", ""),
        # The 2D art id is a sprite-sheet slot, not a 3D model. It is kept only
        # as a cross-reference; model_id is the binding Blender must honour.
        "art_ref": appearance["id"],
        "state": getattr(ch, "current_state", ""),
        "screen_pos": frame_pos,
        "aura": {"name": aura_name, "power": round(aura_power, 2)},
        "is_beast": bool(getattr(ch, "is_beast", False)),
        "is_demon": bool(getattr(ch, "is_demon", False)),
        "is_emperor": bool(getattr(ch, "is_emperor", False)),
    }


def dressing_for(place_idx: int, seed: int) -> Dict:
    """Fixed set dressing per location. Deterministic, so a place never changes."""
    name, world_key, grade, kind, _res, _furnace, _secret, _seal = PL.PLACES[place_idx]
    archetype = ARCHETYPE_BY_KIND.get(kind, "town_street")
    return {
        "place_index": place_idx,
        "place_name": name,
        "world_key": world_key,
        "grade": grade,
        "kind": kind,
        "archetype": archetype,
        "layout_seed": seed % 100000,
        "density": round(0.3 + grade * 0.25, 2),
        "qi_density": round(grade * 0.4, 2),
    }


def build_shot(sim, focus, place_idx: int, index: int, hour: int, size: str) -> Dict:
    present = characters_at(sim, place_idx)
    seed = int(index) + place_idx * 977
    phase = phase_for_hour(hour)
    elev, azim, sun_col, sky_top, sky_hor = SKY_BY_HOUR[phase]

    # Subject offset inside the frame: keep focus near the rule-of-thirds line.
    ox = -0.22 if size in ("establish", "wide") else -0.08
    frame_pos = [ox, 0.0]

    actors = [actor_for(sim, c, frame_pos if c.cid == focus.cid else [ox + 0.3, -0.15])
              for c in present[:12]]

    return {
        "shot_id": f"S{index:04d}",
        "index": index,
        "day": sim.day,
        "hour": hour,
        "style": STYLE["name"],
        "location": dressing_for(place_idx, seed),
        "lighting": {
            "phase": phase,
            "sun_elevation_deg": elev,
            "sun_azimuth_deg": azim,
            "sun_color": list(sun_col),
            "sky_top": list(sky_top),
            "sky_horizon": list(sky_hor),
            "fog_density": round(0.004 + (2 - PL.PLACES[place_idx][2]) * 0.002, 4),
        },
        "camera": camera_for(size, focus, seed),
        "subject_cid": focus.cid,
        "actors": actors,
        "render": {"engine": STYLE["render"], "resolution": STYLE["resolution"],
                   "fps": STYLE["fps"], "duration_s": 3.0},
    }


def compile_episode(sim, cids: List[int], place_idx: int, hour: int,
                    shots_per_cid: int = 3) -> Dict:
    """Compile a list of characters at one location into a shot list."""
    subjects = []
    by_cid = {c.cid: c for c in sim.cast}
    for cid in cids:
        ch = by_cid.get(cid)
        if ch is not None:
            subjects.append(ch)
    if not subjects:
        raise SystemExit("no subjects found; is the save populated?")

    out, i = [], 0
    by_cid = {c.cid: c for c in sim.cast}
    for ch in subjects:
        state_text = f"{getattr(ch, 'current_state', '')} {getattr(ch, 'dao', '')}"
        for n in range(shots_per_cid):
            size = size_for_event(state_text) if n == 0 else ["medium", "wide", "close"][n % 3]
            out.append(build_shot(sim, ch, place_idx, i, hour, size))
            i += 1
    return {"version": 1, "style": STYLE, "shots": out}


def main() -> None:
    ap = argparse.ArgumentParser(description="Compile sim state into shot.json")
    ap.add_argument("--out", default="shots.json")
    ap.add_argument("--cid", type=int, action="append", default=None,
                    help="subject cid (repeatable); default = top ranked")
    ap.add_argument("--place", type=int, default=None, help="place index override")
    ap.add_argument("--hour", type=int, default=None,
                    help="24h clock hour; defaults to --phase")
    ap.add_argument("--phase", choices=sorted(PHASE_HOURS), default="day",
                    help="lighting phase (used when --hour is absent)")
    ap.add_argument("--save", default=None)
    args = ap.parse_args()

    from tiandao import persist as PS
    from tiandao import story

    sim = PS.load_sim(args.save) if args.save else PS.load_sim()
    print(f"loaded sim: day={sim.day} cast={len(sim.cast)}")

    cids = args.cid or [c.cid for _, c in story.rank(sim, top=5)]
    by_cid = {c.cid: c for c in sim.cast}
    focus = by_cid.get(cids[0])
    if focus is None:
        raise SystemExit(f"cid {cids[0]} not in save")

    place_idx = args.place
    if place_idx is None:
        place_idx = resolve_place(sim, focus)
    if place_idx is None:
        # Fall back to the hub so the compiler always has somewhere to point.
        place_idx = len(PL.PLACES) // 2
    name = PL.PLACES[place_idx][0]
    hour = args.hour if args.hour is not None else PHASE_HOURS[args.phase]
    print(f"subjects={cids} place={place_idx} ({name}) "
          f"hour={hour} phase={args.phase}")

    data = compile_episode(sim, cids, place_idx, hour)
    Path(args.out).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {len(data['shots'])} shots -> {args.out}")


if __name__ == "__main__":
    main()
