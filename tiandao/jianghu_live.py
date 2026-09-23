"""Viewer lifecycle for the existing SimDao WorldRunner."""
import asyncio
import os
import shutil
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from . import worldloop as WL


def viewer_config(save_path):
    # One scheduler turn per update: large daemon batches skip too much to watch.
    return WL.LoopConfig(save_path=os.path.abspath(save_path), chunk_events=1,
                         interval=2.0, autotune=False, llm=False)


def start_live(save_path, runner=WL.RUNNER):
    if runner.status()['state'] in ('running', 'stopping'):
        raise RuntimeError('โลกกำลังเดินอยู่แล้ว')
    path = Path(save_path).resolve()
    # Validate the existing world before making a backup or starting any writes.
    WL.PS.load_sim(str(path))
    backup_dir = path.parent / 'backups'
    backup_dir.mkdir(exist_ok=True)
    backup = backup_dir / (path.name + '.before-live-' + datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
    shutil.copy2(path, backup)
    status = runner.start(viewer_config(path))
    return {**status, 'backup_path': str(backup)}


def live_status(save_path, runner=WL.RUNNER):
    status = runner.status()
    matches = bool(status['save_path']) and os.path.normcase(os.path.abspath(status['save_path'])) == os.path.normcase(os.path.abspath(save_path))
    last = status['last'] if matches else None
    return {'state': status['state'] if matches else 'idle',
            'error': status['error'] if matches else '',
            'revision': status['iterations'] if matches else 0,
            'saved_day': last['day_to'] if last else None,
            'poll_ms': 2000}


def viewer_lifespan(save_path):
    @asynccontextmanager
    async def lifespan(app):
        if os.environ.get('TIANDAO_LIVE') == '1':
            start_live(save_path)
        try:
            yield
        finally:
            # Wait for the existing runner's final atomic save before server exit.
            WL.RUNNER.stop()
            await asyncio.to_thread(WL.RUNNER.join)
    return lifespan
