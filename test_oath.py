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




if __name__ == "__main__":
    unittest.main()
