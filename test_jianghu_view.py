"""Observer API: actual local residents, location-scoped events and no world writes."""
import pickle
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from jianghu_routes import asset_names, make_router
from tiandao import places
from tiandao.character_art import catalog
from tiandao.jianghu_view import project_world
from tiandao.models import Character, World


INN = next(i for i, p in enumerate(places.PLACES) if p[0] == 'โรงเตี๊ยมสยบพยัคฆ์')


class ObserverTests(unittest.TestCase):
    def setUp(self):
        def character(cid, **kw):
            values = dict(cid=cid, name=f'จอมยุทธ์ {cid}', world_id=0, dao='กระบี่',
                          dao_tags=[], born_day=0, place=INN)
            values.update(kw)
            return Character(**values)
        self.cast = [character(0), character(1, hidden=True), character(2, alive=False),
                     character(3, travel_dest=0), character(4, world_id=1), character(5, place=0)]
        self.sim = NS(worlds=[World(0, 'โลกมนุษย์', 0), World(1, 'อีกโลก', 0)], orgs=[], day=30,
                      log=[NS(seq=1, day=1, kind='เดินทาง', text='ถึงโรงเตี๊ยม', place=INN, world_id=0),
                           NS(seq=2, day=2, kind='ฝึก', text='คนละโลก', place=INN, world_id=1),
                           NS(seq=3, day=3, kind='ฝึก', text='คนละที่', place=0, world_id=0)],
                      living=lambda: [c for c in self.cast if c.alive])

    def test_presence_and_events_do_not_leak_between_locations(self):
        data = project_world(self.sim)
        self.assertEqual(data['place']['id'], INN)
        self.assertEqual([a['id'] for a in data['residents']], [0])
        self.assertEqual([e['seq'] for e in data['events']], [1])
        self.assertEqual(data['place']['population'], 1)

    def test_observer_does_not_mutate_characters(self):
        before = pickle.dumps(self.cast)
        project_world(self.sim)
        project_world(self.sim, place_idx=0)
        self.assertEqual(pickle.dumps(self.cast), before)

    def test_only_finished_scenes_are_advertised(self):
        self.assertEqual(project_world(self.sim)['scene']['id'], 'river-inn')
        for name, scene_id in [('สำนักกระบี่จักรพรรดิ', 'sword-sect'), ('ป่าไผ่เหล็กเก้าชั้น', 'bamboo-forest')]:
            place_idx = next(i for i, p in enumerate(places.PLACES) if p[0] == name)
            data = project_world(self.sim, place_idx=place_idx)
            self.assertEqual(data['scene']['id'], scene_id)
            self.assertEqual(data['place']['scene_id'], scene_id)
            self.assertEqual(data['residents'], [])
        self.assertIsNone(project_world(self.sim, place_idx=0)['scene'])
        with self.assertRaises(ValueError):
            project_world(self.sim, place_idx=-999)

    def test_every_declared_character_sheet_is_a_real_drawable_file(self):
        """แคตาล็อกต้องไม่อ้างแผ่นภาพที่ไม่มีไฟล์ และทุกกรอบต้องอยู่ในขอบเขตของแผ่นจริง

        บั๊กที่เจอ: character-art.json อ้าง characters-elders.png (แผ่นที่ 3 ในบทบรรยายศิลป์)
        ซึ่งไม่เคยถูกสร้างเป็นไฟล์ ผู้อาวุโสจึงขอรูปที่ตอบ 404 ทุกครั้ง และกรอบ [0,0,1,1]
        ที่ค้างไว้เป็นค่าเริ่มต้นก็วาดได้แค่หนึ่งพิกเซล
        """
        import struct
        root = Path(__file__).resolve().parent / 'static' / 'jianghu'
        sizes = {}
        for entry in catalog():
            sheet = entry['sheet']
            path = root / sheet
            self.assertTrue(path.is_file(), sheet)
            if sheet not in sizes:
                header = path.read_bytes()[:33]
                sizes[sheet] = struct.unpack('>II', header[16:24])
            width, height = sizes[sheet]
            x, y, w, h = entry['source']
            self.assertGreater(w * h, 1, entry['id'])
            self.assertLessEqual(x + w, width, entry['id'])
            self.assertLessEqual(y + h, height, entry['id'])
        # แผ่นที่ยังไม่มีศิลปะของตัวเองต้องระบุไว้ตรงๆ ว่ากำลังยืมกรอบของแผ่นอื่นอยู่
        borrowed = [e for e in catalog() if e.get('art_pending')]
        self.assertTrue(all(e['age_group'] == 'elder' for e in borrowed))

    def test_renderer_and_router_agree_on_which_sheets_exist(self):
        """รายการแผ่นในฝั่งเบราว์เซอร์ (scene-model.mjs) ต้องครอบคลุมทุกแผ่นที่แคตาล็อกใช้

        ถ้าไม่ครบ ฝั่งหน้าเว็บจะทิ้ง appearance เงียบๆ แล้วถอยไปใช้แผ่นหลัก — ภาพที่เตรียมไว้
        ทั้งชุดจะไม่เคยถูกวาดเลย โดยไม่มีข้อผิดพลาดใดๆ ให้เห็น
        """
        import re
        text = (Path(__file__).resolve().parent / 'static' / 'jianghu' / 'scene-model.mjs').read_text(encoding='utf-8')
        listed = set(re.findall(r"'([\w.-]+\.png)'", re.search(r'CHARACTER_SHEETS = \[(.*?)\]', text, re.S).group(1)))
        self.assertEqual(listed, {entry['sheet'] for entry in catalog()})
        self.assertTrue(listed <= asset_names())

    def test_elders_get_a_stable_drawable_appearance(self):
        """ตัวละครสูงอายุทั้งสองเพศต้องได้ภาพที่วาดได้จริงและคงเดิมทุกครั้ง"""
        from tiandao.character_art import appearance_for
        from tiandao.models import Character
        sheets = {entry['sheet'] for entry in catalog()}
        seen = set()
        for cid in range(40):
            elder = Character(cid=cid, name=f'ผู้อาวุโส {cid}', world_id=0, dao='วิถีดาบ',
                              dao_tags=[], born_day=0, gender='หญิง' if cid % 2 else 'ชาย')
            look = appearance_for(elder, 70 * 365)
            self.assertIn(look['sheet'], sheets)
            self.assertIn(look['sheet'], asset_names())
            self.assertGreater(look['source'][2] * look['source'][3], 1)
            self.assertEqual(look, appearance_for(elder, 71 * 365))
            seen.add(look['id'])
        self.assertGreater(len(seen), 1, 'ผู้อาวุโสทั้งโลกไม่ควรหน้าตาเหมือนกันหมด')

    def test_http_assets_inputs_and_read_only_routes(self):
        app = FastAPI(); app.include_router(make_router('unused.save'))
        with patch('jianghu_routes.load_world', return_value=(self.sim, 'save')):
            with TestClient(app) as client:
                self.assertEqual(client.get('/jianghu').status_code, 200)
                # ทุกไฟล์ที่ router ประกาศว่าเสิร์ฟได้ ต้องมีอยู่จริง — รายการมาจากที่เดียวกับที่
                # หน้าเว็บใช้ขอ (ไฟล์คงที่ + แผ่นตัวละครทุกแผ่นใน character-art.json)
                self.assertIn('characters.png', asset_names())
                for asset in sorted(asset_names()):
                    response = client.get('/jianghu-assets/' + asset)
                    self.assertEqual(response.status_code, 200, asset)
                    if asset.endswith('.mjs'):
                        self.assertIn('javascript', response.headers['content-type'])
                self.assertEqual(client.get('/jianghu-assets/world.save').status_code, 404)
                self.assertEqual(client.get('/api/jianghu?world=999999').status_code, 400)
                self.assertEqual(client.get('/api/jianghu?place=-99').status_code, 400)
                self.assertEqual(client.post('/api/jianghu').status_code, 405)
                self.assertEqual(client.get('/api/jianghu').json()['residents'][0]['id'], 0)


if __name__ == '__main__':
    unittest.main()
