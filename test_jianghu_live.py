"""Exercise the real SimDao runner and observer together on an isolated save."""
import contextlib
import hashlib
import io
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from jianghu_routes import make_router
from tiandao import persist as PS, sim as S, worldloop as WL
from tiandao.jianghu_live import viewer_lifespan, live_status


def wait_for(predicate, timeout=20):
    # world.save เป็นโลกจริงที่โตขึ้นตามการใช้งาน การเซฟหนึ่งรอบจึงอาจเกินหนึ่งวินาที
    # timeout เดิม 5 วินาทีสั้นกว่าสาม atomic saves และทำให้เทสต์ล้มทั้งที่ runner ปกติ
    deadline = time.monotonic() + timeout
    while not predicate():
        if time.monotonic() >= deadline:
            raise AssertionError('Runner did not reach the expected state')
        time.sleep(.01)


class LiveObserverTests(unittest.TestCase):
    def test_real_runner_updates_viewer_pause_resume_and_shutdown(self):
        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()):
            path = str(Path(folder) / 'world.save')
            # โลกเล็กที่สร้างเอง — ไม่ผูกกับ tiandao/world.save ของผู้ใช้ที่โตได้หลายร้อย MB
            # (เซฟแต่ละรอบหลายวินาที ทำให้ runner ไม่ถึง 3 รอบภายใน timeout)
            seed_world = S.Sim(seed=7)
            seed_world.run(200)
            PS.save_sim(seed_world, path)
            original = Path(path).read_bytes()
            initial = PS.load_sim(path)
            cfg = WL.LoopConfig(save_path=path, chunk_events=1, interval=.02, autotune=False)
            app = FastAPI(lifespan=viewer_lifespan(path))
            app.include_router(make_router(path))
            with patch.dict(os.environ, {'TIANDAO_LIVE':'1'}), patch('tiandao.jianghu_live.viewer_config', return_value=cfg):
                try:
                    with TestClient(app) as client:
                        wait_for(lambda: WL.RUNNER.iterations >= 3)
                        data = client.get('/api/jianghu').json()
                        self.assertEqual(data['source'], 'save')
                        self.assertEqual(data['live']['state'], 'running')
                        self.assertGreater(data['live']['revision'], 0)
                        self.assertEqual(client.post('/api/jianghu/live/start').status_code, 409)
                        client.post('/api/jianghu/live/stop')
                        wait_for(lambda: WL.RUNNER.state == 'idle')
                        stopped = PS.load_sim(path)
                        self.assertGreater(stopped.seq, initial.seq)
                        self.assertEqual(client.get('/api/jianghu').json()['day'], stopped.day)
                        fingerprint = hashlib.sha256(Path(path).read_bytes()).digest()
                        time.sleep(.08)
                        self.assertEqual(hashlib.sha256(Path(path).read_bytes()).digest(), fingerprint)
                        self.assertEqual(client.post('/api/jianghu/live/start').status_code, 200)
                        wait_for(lambda: WL.RUNNER.iterations >= 2)
                    self.assertEqual(WL.RUNNER.state, 'idle')
                    self.assertGreater(PS.load_sim(path).seq, stopped.seq)
                    backups = sorted((Path(folder)/'backups').iterdir())
                    self.assertEqual(backups[0].read_bytes(), original)
                finally:
                    WL.RUNNER.stop(); WL.RUNNER.join()

    def test_viewer_polling_while_the_runner_saves_does_not_stop_the_world(self):
        # WORLD_CONDITIONS_REFERENCE_TH.md: บน Windows /api/jianghu เปิดอ่าน world.save ชนจังหวะ
        # os.replace ของ runner แล้ว runner ล้มเป็น error ด้วย WinError 5
        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()):
            path = str(Path(folder) / 'world.save')
            seed_world = S.Sim(seed=7)
            seed_world.run(200)
            PS.save_sim(seed_world, path)
            cfg = WL.LoopConfig(save_path=path, chunk_events=1, interval=0, autotune=False)
            app = FastAPI(lifespan=viewer_lifespan(path))
            app.include_router(make_router(path))
            with patch.dict(os.environ, {'TIANDAO_LIVE': '1'}), \
                    patch('tiandao.jianghu_live.viewer_config', return_value=cfg):
                try:
                    with TestClient(app) as client:
                        polls = 0
                        while WL.RUNNER.iterations < 60:
                            resp = client.get('/api/jianghu')
                            self.assertEqual(resp.status_code, 200, resp.text)
                            live = resp.json()['live']
                            self.assertEqual(live['state'], 'running', live['error'])
                            polls += 1
                        self.assertGreater(polls, 5)
                        self.assertEqual(WL.RUNNER.save_failures, 0)
                        client.post('/api/jianghu/live/stop')
                        wait_for(lambda: WL.RUNNER.state == 'idle')
                        self.assertEqual(live_status(path)['saved_day'], PS.load_sim(path).day)
                finally:
                    WL.RUNNER.stop(); WL.RUNNER.join()

    def test_read_only_launch_does_not_start_or_create_missing_world(self):
        with tempfile.TemporaryDirectory() as folder:
            path = str(Path(folder)/'missing.save')
            app = FastAPI(lifespan=viewer_lifespan(path)); app.include_router(make_router(path))
            with patch.dict(os.environ, {'TIANDAO_LIVE':'0'}), TestClient(app) as client:
                self.assertEqual(live_status(path)['state'], 'idle')
                self.assertEqual(client.post('/api/jianghu/live/start').status_code, 503)
                self.assertFalse(Path(path).exists())


if __name__ == '__main__':
    unittest.main()
