"""บันทึกวิถีสวรรค์ — อ่านชีวิตของตัวละครที่คิดเองตัดสินใจเอง (ชั้น tiandao/mind)

    .\\Start-Minds.ps1                 # เปิดที่ http://127.0.0.1:8002
    python -m uvicorn mind_app:app --port 8002
"""
import asyncio
from contextlib import asynccontextmanager
import os
from pathlib import Path

from fastapi import Body, FastAPI, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse

from tiandao.mind.runner import RUNNER, RunConfig, read_journal
from tiandao.mind.novel import NOVEL

ROOT = Path(__file__).resolve().parent


def _config():
    return RunConfig(
        out_dir=os.environ.get("TIANDAO_MIND_DIR", str(ROOT / "out" / "minds")),
        source_save=os.environ.get("TIANDAO_MIND_SOURCE", ""),
        seed=int(os.environ.get("TIANDAO_MIND_SEED", "1")),
        capacity=int(os.environ.get("TIANDAO_MIND_COUNT", "40")),
        story=os.environ.get("TIANDAO_MIND_STORY", "1") != "0",
    )


@asynccontextmanager
async def lifespan(app):
    RUNNER.configure(_config())
    if os.environ.get("TIANDAO_MIND_AUTOSTART") == "1":
        RUNNER.start()
    try:
        yield
    finally:
        RUNNER.stop()
        await asyncio.to_thread(RUNNER.join)


app = FastAPI(title="SimDao · บันทึกผู้มีจิตใจ", lifespan=lifespan)


def _retry(fn):
    # เธรดโลกกำลังแก้ข้อมูลอยู่ระหว่างอ่าน — อ่านซ้ำไม่กี่ครั้งถูกกว่าการล็อกทั้งโลกระหว่างรอโมเดลคิด
    for _ in range(5):
        try:
            return fn()
        except RuntimeError:
            continue
    return fn()


@app.get("/")
def page():
    return FileResponse(ROOT / "templates" / "minds.html", headers={"Cache-Control": "no-cache"})


@app.get("/api/status")
def status():
    return _retry(RUNNER.status)


@app.get("/api/journal")
def journal(cid: int | None = None, limit: int = 120, before: int | None = None, types: str = ""):
    kinds = {t for t in types.split(",") if t} or None
    return read_journal(RUNNER.cfg.journal_path, cid=cid, limit=max(1, min(limit, 1000)),
                        before_seq=before, types=kinds)


@app.get("/api/mind/{cid}")
def mind(cid: int):
    data = _retry(lambda: RUNNER.sim.mind.profile(RUNNER.sim, cid))
    if data is None:
        raise HTTPException(404, "ไม่พบผู้มีจิตใจคนนี้")
    return data


@app.post("/api/start")
def start():
    if NOVEL.running():
        raise HTTPException(409, "กำลังแต่งนิยายอยู่ กรุณารอหรือสั่งพักก่อนเดินโลก")
    try:
        return RUNNER.start()
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc


@app.post("/api/stop")
def stop():
    return RUNNER.stop()


@app.post("/api/config")
def configure(body: dict = Body(...)):
    if RUNNER.state in ("running", "stopping"):
        raise HTTPException(409, "ต้องพักโลกก่อนเปลี่ยนเวลาและจำนวนผู้มีจิตใจ")
    minutes = float(body.get("minutes", RUNNER.cfg.max_minutes or 25))
    count = int(body.get("count", RUNNER.cfg.capacity))
    if not 0.1 <= minutes <= 10080:
        raise HTTPException(422, "เวลากำหนดได้ตั้งแต่ 0.1 ถึง 10,080 นาที")
    if not 1 <= count <= 200:
        raise HTTPException(422, "จำนวนผู้มีจิตใจกำหนดได้ตั้งแต่ 1 ถึง 200 คน")
    RUNNER.cfg.max_minutes = minutes
    RUNNER.cfg.capacity = count
    RUNNER.sim.mind.set_capacity(RUNNER.sim, count)
    RUNNER.save()
    return RUNNER.status()


@app.get("/api/novel/status")
def novel_status():
    return NOVEL.status()


@app.post("/api/novel/start")
def novel_start(body: dict = Body(...)):
    if RUNNER.state in ("running", "stopping"):
        raise HTTPException(409, "กรุณาพักโลกก่อนแต่งนิยาย เพื่อไม่ให้สองงานแย่งโมเดล")
    try:
        return NOVEL.start(RUNNER.sim, RUNNER.cfg.journal_path, int(body["cid"]), RUNNER.backend,
                           RUNNER.cfg.out_dir, chapters=int(body.get("chapters", 6)))
    except (KeyError, TypeError, ValueError, RuntimeError) as exc:
        raise HTTPException(409, str(exc)) from exc


@app.post("/api/novel/stop")
def novel_stop():
    return NOVEL.stop()


@app.get("/api/novel/download")
def novel_download():
    data = NOVEL.status()
    if not data["out_path"] or not os.path.exists(data["out_path"]):
        raise HTTPException(404, "ยังไม่มีไฟล์นิยาย")
    return FileResponse(data["out_path"], media_type="text/markdown",
                        filename=os.path.basename(data["out_path"]))


@app.get("/api/mind/{cid}/biography.md")
def biography(cid: int):
    profile = _retry(lambda: RUNNER.sim.mind.profile(RUNNER.sim, cid))
    if profile is None:
        raise HTTPException(404)
    entries = list(reversed(read_journal(RUNNER.cfg.journal_path, cid=cid, limit=100000)))
    out = [f"# ชีวประวัติของ {profile['name']}", "", f"_{profile['identity']}_", ""]
    if profile["long_goal"]:
        out += [f"**เป้าหมายชีวิต:** {profile['long_goal']}", ""]
    for e in entries:
        head = f"### ปีที่ {e.get('year')} · {e.get('place', '')}"
        t = e.get("type")
        if t == "decision" and e.get("cid") == cid:
            out.append(head)
            if e.get("thought"):
                out.append(f"> {e['thought']}")
            who = f" กับ{e['target']}" if e.get("target") else ""
            dest = f" → {e['dest']}" if e.get("dest") else ""
            out.append(f"**ตัดสินใจ:** {e['action']}{who}{dest} — {e.get('why', '')}")
            out.append(f"**ผล:** {e['outcome']} — {e['text']}")
            if e.get("story"):
                out += ["", e["story"]]
        elif t == "decision":
            out += [head, f"{e['name']} {e['action']} กับ{profile['name']} — {e['outcome']}: {e['text']}"]
        elif t in ("birth", "childhood", "received", "event", "join", "death"):
            out += [head, e.get("text", "")]
        out.append("")
    return PlainTextResponse("\n".join(out), headers={
        "Content-Disposition": f'attachment; filename="biography-{cid}.md"'})
