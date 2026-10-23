# -*- coding: utf-8 -*-
"""หน้าเว็บดูโลกสด — เดินโลกใน thread เบื้องหลัง และให้หน้าเว็บอ่านสถานะ

    python app.py                       # เปิดโลกจาก out/world.json (หรือสร้างใหม่) ที่ http://127.0.0.1:8000
    SIMDAO_SAVE=out/other.json SIMDAO_SEED=7 python app.py
"""
import os

import uvicorn
from fastapi import Body, FastAPI, HTTPException
from fastapi.responses import FileResponse

from simdao import World, DEFAULT_SAVE
from simdao.runner import Runner

BASE = os.path.dirname(os.path.abspath(__file__))
SAVE = os.environ.get("SIMDAO_SAVE", DEFAULT_SAVE)
SEED = int(os.environ.get("SIMDAO_SEED", "0"))

runner = Runner(World.load_or_create(SAVE, seed=SEED), save_path=SAVE)
app = FastAPI(title="Sim Dao")


def W():
    return runner.world


@app.get("/")
def index():
    return FileResponse(os.path.join(BASE, "web", "index.html"))


@app.get("/api/status")
def status():
    with runner.lock:
        s = W().stats()
    s.update(running=runner.running, speed=runner.years_per_second, error=runner.error, save=SAVE)
    return s


@app.get("/api/events")
def events(since: int = 0, limit: int = 200, kind: str = None, person: int = None):
    with runner.lock:
        if since <= 0:
            return W().recent(limit, kind=kind, person=person)
        return list(reversed(W().events(since=since, limit=limit, kind=kind, person=person)))


@app.get("/api/worlds")
def worlds():
    with runner.lock:
        return W().worlds()


@app.get("/api/places")
def places(world: int = None):
    with runner.lock:
        out = W().places()
    return [p for p in out if world is None or p["world"] == world]


@app.get("/api/edges")
def edges():
    return W().edges()


@app.get("/api/sects")
def sects():
    with runner.lock:
        return [s for s in W().sects() if s["alive"]]


@app.get("/api/people")
def people(world: int = None, place: int = None, limit: int = 500):
    with runner.lock:
        return W().people(world=world, place=place, limit=limit)


@app.get("/api/person/{pid}")
def person(pid: int):
    with runner.lock:
        try:
            p = W().person(pid)
        except ValueError:
            raise HTTPException(404, "ไม่มีคนนี้")
        p["events"] = W().recent(40, person=pid)
    return p


@app.post("/api/run/start")
def start(body: dict = Body(default={})):
    if "speed" in body:
        runner.years_per_second = float(body["speed"])
    runner.start()
    return {"running": runner.running}


@app.post("/api/run/stop")
def stop():
    runner.stop()
    return {"running": runner.running}


@app.post("/api/save")
def save():
    runner.save()
    return {"saved": SAVE}


@app.on_event("shutdown")
def _shutdown():
    if runner.running:
        runner.stop()


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("PORT", "8000")))
