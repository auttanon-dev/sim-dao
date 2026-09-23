"""Read-only projections for the pixel-art viewer; no simulation turns or saves."""
import os
import threading
from collections import Counter
from itertools import islice

from . import geo, persist, places, seasons

_lock = threading.Lock()
_cached_key = None
_cached_sim = None
SCENE_IDS = {
    'โรงเตี๊ยมสยบพยัคฆ์': 'river-inn',
    'สำนักกระบี่จักรพรรดิ': 'sword-sect',
    'ป่าไผ่เหล็กเก้าชั้น': 'bamboo-forest',
}


def load_world(path):
    """Cache one save revision. Missing saves use an explicitly labelled seed preview."""
    global _cached_key, _cached_sim
    path = os.path.abspath(path)
    try:
        stat = os.stat(path)
        key = (path, stat.st_mtime_ns, stat.st_size)
        source = "save"
    except FileNotFoundError:
        key = (path, None)
        source = "preview"
    with _lock:
        if key != _cached_key:
            if source == "preview":
                from .sim import Sim
                candidate = Sim(seed=2026, tiers=3)
            else:
                candidate = persist.load_sim(path)
            _cached_sim, _cached_key = candidate, key
        return _cached_sim, source


def project_world(sim, source="save", place_idx=None, world_id=None):
    living = sorted(sim.living(), key=lambda ch: ch.cid)
    visible = [ch for ch in living if not ch.hidden and ch.travel_dest < 0]
    counts = Counter((ch.world_id, ch.place) for ch in visible)
    worlds = [{"id": w.wid, "name": w.name, "key": w.place_key}
              for w in sim.worlds if any(p[1] == w.place_key for p in places.PLACES)]
    if world_id is None:
        world_id = worlds[0]["id"] if worlds else 0
    world = next((w for w in sim.worlds if w.wid == world_id), None)
    if world is None or not any(w["id"] == world_id for w in worlds):
        raise ValueError("ไม่พบดินแดนนี้")
    locations = [{"id": i, "name": p[0], "type": p[3],
                  "x": geo.COORDS[i][0], "y": geo.COORDS[i][1],
                  "population": counts[(world_id, i)], "scene_id": SCENE_IDS.get(p[0])}
                 for i, p in enumerate(places.PLACES) if p[1] == world.place_key]
    valid = {p["id"] for p in locations}
    if place_idx is None:
        inn = next((p for p in locations if p["name"] == "โรงเตี๊ยมสยบพยัคฆ์"), None)
        place_idx = (inn or max(locations, key=lambda p: p["population"]))["id"]
    if place_idx not in valid:
        raise ValueError("สถานที่นี้ไม่ได้อยู่ในดินแดนที่เลือก")
    residents = []
    for ch in visible:
        if ch.world_id != world_id or ch.place != place_idx:
            continue
        org = next((o.name for o in sim.orgs if o.oid == ch.org), "ผู้เดินทางอิสระ")
        residents.append({"id": ch.cid, "name": ch.name, "realm": ch.realm_name(),
                          "dao": ch.dao, "hp": ch.hp, "max_hp": ch.max_hp,
                          "mp": ch.current_mp, "max_mp": ch.max_mp,
                          "org": org, "skills": list(ch.skills), "state": ch.current_state,
                          "bonds": len(ch.bonds), "rivals": len(ch.rivals),
                          "building": ch.building, "art_index": ch.cid % 8,
                          "gender": ch.gender, "age": max(0, ch.age(sim.day))})
    selected = next(p for p in locations if p["id"] == place_idx)
    local_events = (e for e in reversed(sim.log)
                    if e.place == place_idx and e.world_id == world_id)
    events = [{"seq": e.seq, "day": e.day, "kind": e.kind, "text": e.text}
              for e in islice(local_events, 18)]
    scene = ({"id": selected["scene_id"], "title": selected["name"]}
             if selected["scene_id"] else None)
    return {"source": source, "day": sim.day, "season": seasons.season_of(sim.day)[0],
            "scene": scene,
            "worlds": worlds, "world_id": world_id, "places": locations,
            "place": selected, "residents": residents, "events": events,
            "roads": [{"a": e[0], "b": e[1], "open": e[4] if len(e) > 4 else True}
                      for e in geo.EDGES if e[0] in valid and e[1] in valid]}
