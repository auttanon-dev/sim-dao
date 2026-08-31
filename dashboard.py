# -*- coding: utf-8 -*-
"""ดูโลกที่กำลังรันอยู่แบบสดๆ ผ่านเว็บ — อ่านอย่างเดียวจากไฟล์ save ที่ daemon.py (หรือ run.py --save)
เขียนไว้ ไม่รันซิมเอง คนละ process กับตัวที่เดินซิมจริง

    python daemon.py &          # เดินโลกไปเรื่อยๆ เซฟทุกรอบ
    python dashboard.py         # เปิดคู่กัน ดูที่ http://127.0.0.1:8000/ หรือ http://127.0.0.1:8000/map
"""
import os

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from tiandao import chronicle as CH
from tiandao import persist as PS
from tiandao import seasons as SEASONS
from tiandao import terrain as TERRAIN
from tiandao import geo as GEO
from tiandao import places as PL
from tiandao import rules as R

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SAVE_PATH = os.environ.get("TIANDAO_SAVE_PATH", PS.DEFAULT_PATH)

app = FastAPI(title="Tiandao Live Dashboard & Mapgen4 Visualizer")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))


def snapshot():
    try:
        sim = PS.load_sim(SAVE_PATH)
    except FileNotFoundError:
        return None
    season_name, regen_mult, disaster_p, disaster_kind = SEASONS.season_of(sim.day)
    worlds = [{
        "name": w.name, "tier": w.tier, "kind": w.kind, "era": w.era, "state": w.state(),
        "ratio": round(w.ratio() * 100, 1), "population": len(sim.living_in(w.wid)),
    } for w in sim.worlds]
    recent = [{"day": e.day, "kind": e.kind, "text": e.text} for e in sim.log[-20:]]
    seal_info = R.mara_seal_state(sim)
    return {
        "day": sim.day, "years": sim.day // 365, "season": season_name,
        "regen_mult": regen_mult,
        "population": len(sim.living()), "n_orgs": len(sim.orgs), "n_caches": len(sim.caches),
        "worlds": worlds, "recent_events": list(reversed(recent)),
        "mara_seal": seal_info
    }


@app.get("/api/status")
def api_status():
    snap = snapshot()
    if snap is None:
        return {"error": f"ไม่พบไฟล์ {SAVE_PATH} — ยังไม่มีโลกที่บันทึกไว้ "
                          f"(รัน `python run.py --save` หรือ `python daemon.py` ก่อน)"}
    return snap


@app.get("/api/legends")
def api_legends():
    return CH.all_legends()


@app.get("/api/map/terrain")
def api_map_terrain():
    return TERRAIN.generate_terrain_mesh()


@app.get("/api/map/places")
def api_map_places():
    return TERRAIN.get_all_places_data()


@app.get("/api/map/edges")
def api_map_edges():
    return [
        {
            "from": e[0],
            "to": e[1],
            "distance": e[2],
            "type": e[3] if len(e) > 3 else "road",
            "traversable": e[4] if len(e) > 4 else True,
        }
        for e in GEO.EDGES
    ]


@app.get("/api/map/cultivators")
def api_map_cultivators():
    try:
        sim = PS.load_sim(SAVE_PATH)
    except FileNotFoundError:
        return []
    
    living = sim.living()
    # Sample up to 120 most notable cultivators for smooth visualization
    sample = sorted(living, key=lambda c: (c.realm, getattr(c, "insight", 0)), reverse=True)[:120]
    
    res = []
    for c in sample:
        res.append({
            "cid": c.cid,
            "name": c.name,
            "realm": c.realm,
            "realm_name": c.realm_name(),
            "dao": c.dao,
            "world_id": c.world_id,
            "place": c.place,
            "place_name": sim.place_name(c),
            "travel_dest": getattr(c, "travel_dest", -1),
            "travel_arrival_day": getattr(c, "travel_arrival_day", 0),
            "is_lord": getattr(c, "is_lord", False),
            "tribe": getattr(c, "tribe", "ชาวบ้าน"),
        })
    return res


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse(request, "dashboard.html", {
        "snap": snapshot(),
        "legends": CH.all_legends(limit=10),
        "save_path": SAVE_PATH,
    })


@app.get("/map", response_class=HTMLResponse)
def map_view(request: Request):
    return templates.TemplateResponse(request, "map_visualizer.html", {
        "save_path": SAVE_PATH,
    })


from tiandao import godview as GV


@app.get("/api/godview/snapshot")
def api_godview_snapshot():
    try:
        sim = PS.load_sim(SAVE_PATH)
    except FileNotFoundError:
        return {"error": "world.save not found"}
    return GV.extract_lightweight_snapshot(sim)


@app.get("/api/godview/timeline")
def api_godview_timeline():
    try:
        sim = PS.load_sim(SAVE_PATH)
    except FileNotFoundError:
        return {"error": "world.save not found"}
    return GV.build_timeline_history(sim)


@app.get("/godview", response_class=HTMLResponse)
def godview_view(request: Request):
    return templates.TemplateResponse(request, "godview.html", {
        "save_path": SAVE_PATH,
    })


from tiandao import settlement as SETTLE


@app.get("/api/settlement/{place_idx}")
def api_settlement(place_idx: int):
    try:
        sim = PS.load_sim(SAVE_PATH)
    except FileNotFoundError:
        sim = None
    return SETTLE.generate_settlement_layout(place_idx, sim)


@app.get("/settlement/{place_idx}", response_class=HTMLResponse)
def settlement_view(request: Request, place_idx: int):
    return templates.TemplateResponse(request, "settlement.html", {
        "place_idx": place_idx,
        "save_path": SAVE_PATH,
    })


from tiandao import dialogue as DLG
from tiandao import weather as WTH
from tiandao import combat_vis as CMB


@app.get("/api/dialogue/encounter")
def api_dialogue_encounter(c1_id: int = 0, c2_id: int = 1, place_name: str = "โรงเตี๊ยมสยบพยัคฆ์"):
    try:
        sim = PS.load_sim(SAVE_PATH)
        living = sim.living()
        c1 = next((c for c in living if c.cid == c1_id), living[0] if living else None)
        c2 = next((c for c in living if c.cid == c2_id), living[1] if len(living) > 1 else None)
    except Exception:
        c1, c2 = None, None
    return DLG.generate_encounter_dialogue(c1, c2, location_name=place_name)


@app.get("/api/weather/current")
def api_weather_current(realm_key: str = "siam"):
    try:
        sim = PS.load_sim(SAVE_PATH)
        day = sim.day
    except Exception:
        day = 100
    rk = int(realm_key) if realm_key.isdigit() else realm_key
    return WTH.get_current_weather(day, rk)


@app.get("/api/combat/simulate/{c1_id}/{c2_id}")
def api_combat_simulate(c1_id: int, c2_id: int):
    try:
        sim = PS.load_sim(SAVE_PATH)
        living = sim.living()
        c1 = next((c for c in living if c.cid == c1_id), None)
        c2 = next((c for c in living if c.cid == c2_id), None)
        if not c1 or not c2:
            c1 = living[0] if living else None
            c2 = living[1] if len(living) > 1 else None
    except Exception:
        c1, c2 = None, None
    return CMB.simulate_duel(c1, c2)


@app.get("/combat", response_class=HTMLResponse)
def combat_view(request: Request):
    return templates.TemplateResponse(request, "combat.html", {
        "save_path": SAVE_PATH,
    })


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
