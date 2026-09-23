"""Local pixel viewer routes, shared with the existing dashboard."""
from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from tiandao.character_art import catalog
from tiandao.jianghu_view import load_world, project_world
from tiandao.jianghu_live import live_status, start_live
from tiandao.worldloop import RUNNER

# ไฟล์คงที่ของหน้าดูโลก (โค้ด สไตล์ และภาพฉาก) — ส่วนแผ่นตัวละครมาจากแคตาล็อกโดยตรง
# เพื่อไม่ให้สามที่นี้หลุดจากกันอีก: แคตาล็อกประกาศแผ่นไหน เราต้องเสิร์ฟแผ่นนั้น และไฟล์ต้องมีจริง
# (บั๊กที่เจอ: แคตาล็อกอ้าง characters-elders.png ซึ่งไม่เคยถูกสร้าง — ขอแล้วได้ 404)
_STATIC_ASSETS = frozenset({
    "jianghu.css", "jianghu.js", "scene-model.mjs", "scene-renderer.mjs", "scene-config.mjs",
    "river-inn.png", "sword-sect.png", "bamboo-forest.png",
})


def asset_names():
    """ชื่อไฟล์ทั้งหมดที่หน้าดูโลกมีสิทธิ์ขอ — แผ่นตัวละครถูกอนุมานจาก character-art.json"""
    return _STATIC_ASSETS | {entry["sheet"] for entry in catalog()}


def make_router(save_path):
    router = APIRouter()
    root = Path(__file__).resolve().parent
    allowed = asset_names()

    @router.get("/jianghu")
    def view():
        return FileResponse(root / "templates" / "jianghu.html", headers={"Cache-Control": "no-cache"})

    @router.get("/jianghu-assets/{name}")
    def asset(name: str):
        if name not in allowed:
            raise HTTPException(404)
        path = root / "static" / "jianghu" / name
        if not path.is_file():
            raise HTTPException(404)
        media = "text/javascript" if path.suffix in {".js", ".mjs"} else None
        return FileResponse(path, media_type=media, headers={"Cache-Control": "no-cache"})

    @router.get("/api/jianghu")
    def snapshot(place: int | None = None, world: int | None = None):
        try:
            sim, source = load_world(save_path)
            return {**project_world(sim, source, place, world), 'live': live_status(save_path)}
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        except (OSError, EOFError) as exc:
            raise HTTPException(503, "อ่านโลกจำลองไม่สำเร็จ กรุณาลองอีกครั้ง") from exc

    @router.post('/api/jianghu/live/start')
    def resume():
        try:
            return start_live(save_path)
        except RuntimeError as exc:
            raise HTTPException(409, str(exc)) from exc
        except (OSError, EOFError, ValueError) as exc:
            raise HTTPException(503, 'เปิดโลกเดิมไม่สำเร็จ') from exc

    @router.post('/api/jianghu/live/stop')
    def pause():
        return RUNNER.stop()

    return router
