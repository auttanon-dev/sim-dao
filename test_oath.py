# -*- coding: utf-8 -*-
"""คำสาบานตามสายของตัวละคร — ชาวบ้าน/ผู้ฝึกตน/สายพุทธะ/อสูร พูดไม่เหมือนกัน

    python -m unittest test_oath -v
"""
import contextlib
import io
import shutil
import tempfile
import unittest

from tiandao import events as E
from tiandao import intent as IN
from tiandao import rules as R
from tiandao import sim as S
from tiandao.mind import backend as B
from tiandao.mind import prompt as PR
from tiandao.mind import storyteller as ST
from tiandao.mind.runner import RunConfig, open_world


def quiet(fn, *a, **kw):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*a, **kw)


class TestOathForm(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sim = quiet(S.Sim, seed=6, tiers=3)

    def _one(self, **kw):
        c = next(x for x in self.sim.living() if not x.is_beast)
        import copy
        c = copy.copy(c)
        c.blood = dict(c.blood)
        for k, v in kw.items():
            setattr(c, k, v)
        return c

    def test_mortal_villager(self):
        c = self._one(realm=0, dao="วิถีค้าขาย")
        c.blood = {"human": 1.0}
        self.assertEqual(R.oath_form(c), "ให้คำมั่นสัญญา")

    def test_cultivator_swears_by_dao_heart(self):
        c = self._one(realm=3, dao="วิถีดาบ")
        c.blood = {"human": 1.0}
        self.assertEqual(R.oath_form(c), "สาบานต่อจิตเต๋า")

    def test_buddhist_path_beats_realm(self):
        for realm in (0, 5):
            c = self._one(realm=realm, dao="วิถีความว่าง")
            c.blood = {"human": 1.0}
            self.assertEqual(R.oath_form(c), "ให้คำมั่นต่อจิตพุทธะ")

    def test_demon_blood_swears_by_the_asura_heart(self):
        c = self._one(realm=2, dao="วิถีดาบ")
        c.blood = {"demon": 1.0}
        self.assertEqual(R.oath_form(c), "ให้คำสัตย์ต่อจิตอสูร")
        beast = self._one(realm=1, dao="วิถีดาบ", is_beast=True)
        beast.blood = {"human": 1.0}
        self.assertEqual(R.oath_form(beast), "ให้คำสัตย์ต่อจิตอสูร")

    def test_mara_blood_swears_by_the_mara_heart(self):
        pure = self._one(realm=2, dao="วิถีดาบ")
        pure.blood = {"mara": 1.0}
        self.assertEqual(pure.race(), "มารแท้")
        self.assertEqual(R.oath_form(pure), "สาบานต่อจิตมาร")
        half = self._one(realm=2, dao="วิถีดาบ")
        half.blood = {"human": 0.5, "mara": 0.5}
        self.assertEqual(half.race(), "มนุษย์มาร")
        self.assertEqual(R.oath_form(half), "สาบานต่อจิตมาร")

    def test_oath_dao_has_its_own_line(self):
        c = self._one(realm=0, dao="วิถีคำสัตย์")
        c.blood = {"human": 1.0}
        self.assertIn("วิถีคำสัตย์", R.oath_form(c))


class TestOathInWorld(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.sim = open_world(RunConfig(out_dir=self.tmp, seed=3, capacity=10, story=False), B.MockThinker())
        self.mind = self.sim.mind.active()[0]
        self.me = self.sim.cast[self.mind.cid]

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_engine_text_names_the_oath(self):
        a, t = self.me, next(c for c in self.sim.living() if c.cid != self.me.cid)
        a.realm, a.dao = 3, "วิถีดาบ"
        a.blood = {"human": 1.0}
        outcome, text, d = self.sim.resolve({"kind": "ให้สัญญา", "tgt": True}, a, t, self.sim.worlds[0], 0, self.sim.rng)
        self.assertEqual(outcome, "ผูกพัน")
        self.assertIn("สาบานต่อจิตเต๋า", text)
        self.assertEqual(d.get("คำสาบาน"), "สาบานต่อจิตเต๋า")

    def test_prompt_tells_the_character_its_own_oath(self):
        self.me.realm, self.me.dao = 2, "วิถีดาบ"
        self.me.blood = {"human": 1.0}
        others = [c for c in self.sim.living()
                  if c.world_id == self.me.world_id and c.cid != self.me.cid and c.age(self.sim.day) >= 16][:8]
        w = IN.weigh(self.me, self.sim, E.EVENT_TABLE, True, others=others)
        w["ให้สัญญา"] = 1000.0
        ctx = PR.build(self.sim, self.mind, self.me, w, others, E.EVENT_TABLE, False)
        self.assertIn("สายของข้าสาบานว่า: สาบานต่อจิตเต๋า", ctx.user)

    def test_story_prompt_carries_both_oaths(self):
        other_mind = self.sim.mind.active()[1]
        other = self.sim.cast[other_mind.cid]
        self.me.realm, self.me.dao = 4, "วิถีดาบ"
        self.me.blood = {"human": 1.0}
        other.blood = {"demon": 1.0}
        entry = {"id": "d-9", "seq": 9, "day": self.sim.day, "year": 0, "cid": self.me.cid, "name": self.me.name,
                 "place": "ลานฝึก", "action": "ให้สัญญา", "target": other.name, "target_cid": other.cid,
                 "dest": "", "why": "อยากมีพันธมิตร", "thought": "", "emotion": "", "long_goal": "",
                 "outcome": "ผูกพัน", "text": "ให้สัญญากัน", "details": {}, "side": [], "alive": True}
        _, user = ST.build(self.sim, entry)
        self.assertIn("ถ้อยคำเวลาสาบาน: สาบานต่อจิตเต๋า", user)
        self.assertIn("ให้คำสัตย์ต่อจิตอสูร", user)
        self.assertIn("ห้ามให้ผู้ฝึกตนพูดแบบชาวบ้าน", user)


if __name__ == "__main__":
    unittest.main()
