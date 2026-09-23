"""Local, reader-first autonomous fiction app."""
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime
import os
from pathlib import Path
import shutil

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse
from narrative_factory.serial import RUNNER

ROOT = Path(__file__).resolve().parent
SAVE = os.environ.get('TIANDAO_SAVE_PATH', str(ROOT / 'tiandao/world.save'))
OUTPUT = os.environ.get('TIANDAO_SERIAL_DIR', str(ROOT / 'out/serial'))


@asynccontextmanager
async def lifespan(app):
    RUNNER.configure(SAVE, OUTPUT)
    if os.environ.get('TIANDAO_SERIAL') == '1':
        path = Path(SAVE)
        if not path.is_file():
            raise RuntimeError('ไม่พบบันทึกโลกเดิม')
        backups = path.parent / 'backups'; backups.mkdir(exist_ok=True)
        shutil.copy2(path, backups / (path.name + '.before-novel-' + datetime.now().strftime('%Y%m%d-%H%M%S-%f')))
        RUNNER.start()
    try:
        yield
    finally:
        RUNNER.stop()
        await asyncio.to_thread(RUNNER.join)


app = FastAPI(title='SimDao · นิยายที่ดำเนินต่อเอง', lifespan=lifespan)


@app.get('/')
def reader():
    return FileResponse(ROOT / 'templates/serial.html', headers={'Cache-Control':'no-cache'})


@app.get('/api/serial')
def status():
    return RUNNER.status()


@app.get('/api/serial/chapter/{index}')
def chapter(index: int):
    chapters = RUNNER.library.chapters()
    if index < 1 or index > len(chapters):
        raise HTTPException(404)
    return chapters[index-1]


@app.post('/api/serial/start')
def start():
    try:
        return RUNNER.start()
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc


@app.post('/api/serial/stop')
def stop():
    return RUNNER.stop()


@app.get('/book.md')
def download():
    parts = ['# '+RUNNER.library.book['title']]
    for c in RUNNER.library.chapters():
        parts.append(f"## ตอนที่ {c['index']} · {c['title']}\n\n{c['prose']}")
    return PlainTextResponse('\n\n'.join(parts), headers={'Content-Disposition':'attachment; filename="simdao-novel.md"'})
