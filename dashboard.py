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

from tiandao.jianghu_live import viewer_lifespan
app = FastAPI(title="Tiandao Live Dashboard & Mapgen4 Visualizer", lifespan=viewer_lifespan(SAVE_PATH))
from jianghu_routes import make_router as make_jianghu_router
app.include_router(make_jianghu_router(SAVE_PATH))
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
        "world": _world_status_safe(),
    })


def _world_status_safe():
    """สถานะตัวเดินโลกสำหรับหน้าแรก — import แบบ lazy เพราะ endpoint ของมันนิยามอยู่ท้ายไฟล์"""
    try:
        from tiandao import worldloop as _WL
        return _WL.RUNNER.status()
    except Exception:
        return {"state": "idle", "iterations": 0, "last": None}


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


# ---------------------------------------------------------------- โรงเขียนนิยาย (Phase L2)
# ตรรกะทั้งหมดอยู่ใน narrative_factory/studio.py — ที่นี่เป็นแค่ทางเข้า HTTP ตามแพทเทิร์นเดียวกับ
# endpoint อื่นในไฟล์นี้ ยกเว้นเรื่องเดียวที่ต่าง: การเขียนหนึ่งบทกินเวลาเป็นนาที จึงไม่รอให้จบใน
# request เดียว แต่คืน job_id ให้หน้าเว็บ poll เอา (ดูเหตุผลเต็มใน docstring ของ studio.py)
from fastapi import Body, HTTPException
from fastapi.responses import PlainTextResponse

from narrative_factory import studio as STUDIO
from tiandao.ai import config_ai as ACFG


@app.get("/api/novel/models")
def api_novel_models():
    installed = STUDIO.ollama_models()
    return {
        "installed": installed,
        "default_prose": ACFG.OLLAMA_PROSE_MODEL,
        "default_structure": ACFG.OLLAMA_STRUCTURE_MODEL,
        "ollama_up": bool(installed),
    }


@app.get("/api/novel/candidates")
def api_novel_candidates(limit: int = 40, min_points: int = 0):
    try:
        return STUDIO.candidates(SAVE_PATH, limit=limit,
                                 min_points=min_points or STUDIO.SCAST.MIN_TURNING_POINTS)
    except FileNotFoundError:
        raise HTTPException(404, f"ไม่พบไฟล์ {SAVE_PATH} — รัน `python run.py --save` ก่อน")


@app.get("/api/novel/outline")
def api_novel_outline(cid: int, chapters: int = 0,
                      target_chars: int = ACFG.SCENE_TARGET_CHARS):
    try:
        return STUDIO.outline(SAVE_PATH, cid, chapters=chapters, target_chars=target_chars)
    except FileNotFoundError:
        raise HTTPException(404, f"ไม่พบไฟล์ {SAVE_PATH}")


@app.post("/api/novel/start")
def api_novel_start(body: dict = Body(...)):
    try:
        job = STUDIO.RUNNER.start(
            SAVE_PATH,
            cid=int(body["cid"]),
            chapters=int(body.get("chapters", 0)),
            prose_model=body.get("prose_model") or ACFG.OLLAMA_PROSE_MODEL,
            structure_model=body.get("structure_model") or ACFG.OLLAMA_STRUCTURE_MODEL,
            target_chars=int(body.get("target_chars", ACFG.SCENE_TARGET_CHARS)),
        )
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(409, str(exc))
    except FileNotFoundError:
        raise HTTPException(404, f"ไม่พบไฟล์ {SAVE_PATH}")
    return job.as_dict()


@app.get("/api/novel/job/{job_id}")
def api_novel_job(job_id: str):
    job = STUDIO.RUNNER.get(job_id)
    if job is None:
        raise HTTPException(404, "ไม่พบงานนี้ (เซิร์ฟเวอร์อาจถูกรีสตาร์ตไปแล้ว)")
    return job.as_dict()


@app.post("/api/novel/job/{job_id}/stop")
def api_novel_stop(job_id: str):
    if not STUDIO.RUNNER.stop(job_id):
        raise HTTPException(404, "ไม่พบงานนี้")
    return {"ok": True}


@app.post("/api/novel/job/{job_id}/rewrite/{index}")
def api_novel_rewrite(job_id: str, index: int):
    try:
        return STUDIO.RUNNER.rewrite(job_id, index).as_dict()
    except KeyError as exc:
        raise HTTPException(404, str(exc))
    except RuntimeError as exc:
        raise HTTPException(409, str(exc))


@app.get("/api/novel/job/{job_id}/download", response_class=PlainTextResponse)
def api_novel_download(job_id: str):
    job = STUDIO.RUNNER.get(job_id)
    if job is None:
        raise HTTPException(404, "ไม่พบงานนี้")
    return PlainTextResponse(job.markdown(), media_type="text/markdown; charset=utf-8",
                             headers={"Content-Disposition":
                                      f'attachment; filename="novel_{job.cid}.md"'})


# ---------------------------------------------------------------- ปุ่มเดินโลก (Phase L3)
# ตรรกะหนึ่งรอบใช้ตัวเดียวกับ daemon.py คือ tiandao/worldloop.py — ที่นี่แค่เปิด/ปิด/ถามสถานะ
from tiandao import worldloop as WL


@app.get("/api/world/status")
def api_world_status():
    return WL.RUNNER.status()


@app.post("/api/world/start")
def api_world_start(body: dict = Body(default={})):
    cfg = WL.LoopConfig(
        save_path=SAVE_PATH,
        seed=int(body.get("seed", 0)),
        tiers=int(body.get("tiers", 3)),
        chunk_events=int(body.get("chunk_events", 20000)),
        interval=float(body.get("interval", 5.0)),
        autotune=bool(body.get("autotune", True)),
        llm=bool(body.get("llm", False)),
    )
    try:
        return WL.RUNNER.start(cfg)
    except RuntimeError as exc:
        raise HTTPException(409, str(exc))


@app.post("/api/world/stop")
def api_world_stop():
    return WL.RUNNER.stop()


@app.get("/novel", response_class=HTMLResponse)
def novel_view(request: Request):
    return templates.TemplateResponse(request, "novel.html", {
        "save_path": SAVE_PATH,
    })


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
