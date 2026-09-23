# -*- coding: utf-8 -*-
"""ยันต์หนีตาย — กลไกที่เขียนไว้ครบแต่ไม่เคยทำงานเลยสักครั้ง

    python -m unittest test_combat_escape -v

บั๊กสองชั้นที่ทับกันใน combat.resolve_combat จน `escaped` เป็น False เสมอ:

1. **ลำดับ** — ริบของ (`loser.items = []`) อยู่ก่อนลูปตรวจยันต์ ลูปจึงวนบนรายการว่างทุกครั้ง
   ต่อให้ผู้แพ้ถือยันต์อยู่จริงก็ไม่มีทางถูกพบ
2. **ชื่อชนิด** — เทียบ `kind` กับ "ยันต์วิเศษ (ใช้แล้วทิ้ง)" ซึ่งเป็น *ชื่อหมวด* ใน
   config.MANUALS_AND_TALISMANS ไม่ใช่ kind ของไอเท็มที่ sim.stash_relic สร้างจริง
   ("ยันต์วิเศษ") ต่อให้แก้ลำดับแล้วก็ยังไม่ match อยู่ดี

ผลที่วัดได้: `escaped` ถูกส่งกลับไปให้ sim ใช้จริง (`if winner is ch and not escaped`)
ทางหนีตายของทั้งโลกจึงปิดสนิทมาตลอด
"""
import contextlib
import io
import unittest

from tiandao import combat
from tiandao import config as C
from tiandao import sim as S


def quiet(fn, *a, **kw):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*a, **kw)


class EscapeTests(unittest.TestCase):
    def setUp(self):
        self.sim = quiet(S.Sim, seed=5, tiers=2)
        self.w = self.sim.worlds[0]
        people = [c for c in self.sim.living_in(0) if c.sentient][:2]
        self.strong, self.weak = people
        # ช่องว่างขั้นพลังกว้างพอให้ผลการปะทะไม่ขึ้นกับการทอย (ตัวคูณต่างกัน 55 เท่า
        # ส่วนเสียงรบกวนของ resolve_combat อยู่ที่ ±20% เท่านั้น)
        self.strong.realm, self.weak.realm = 9, 0
        for c in (self.strong, self.weak):
            c.items = []

    def give(self, ch, name):
        it = self.sim.make_item(C.TALISMAN_KIND, 0, 1.0)
        it.name = name
        ch.items.append(it.iid)
        return it

    def fight(self):
        return quiet(combat.resolve_combat, self.strong, self.weak, self.w, self.sim)

    def test_the_escape_talisman_actually_saves_the_loser(self):
        talisman = self.give(self.weak, C.TALISMAN_ESCAPE)
        winner, loser, _log, escaped = self.fight()
        self.assertIs(winner, self.strong)
        self.assertIs(loser, self.weak)
        self.assertTrue(escaped, "ถือยันต์เคลื่อนย้ายอยู่แต่ยังหนีไม่ได้")
        self.assertNotIn(talisman.iid, self.sim.items, "ยันต์เป็นของใช้แล้วทิ้ง ต้องหายไปจากโลก")
        self.assertNotIn(talisman.iid, self.weak.items)

    def test_escaping_means_keeping_what_you_carry(self):
        """หนีทันแล้วต้องพาของติดตัวไปด้วย — เดิมริบของก่อนจึงไม่มีอะไรเหลือให้หนี"""
        self.give(self.weak, C.TALISMAN_ESCAPE)
        keep = self.sim.make_item("อาวุธ", 0, 1.0)
        self.weak.items.append(keep.iid)
        _winner, _loser, _log, escaped = self.fight()
        self.assertTrue(escaped)
        self.assertIn(keep.iid, self.weak.items, "หนีทันแต่ของยังถูกริบ")
        self.assertNotIn(keep.iid, self.strong.items)

    def test_without_a_talisman_the_loser_is_looted_as_before(self):
        loot = self.sim.make_item("อาวุธ", 0, 1.0)
        self.weak.items.append(loot.iid)
        _winner, _loser, _log, escaped = self.fight()
        self.assertFalse(escaped)
        self.assertEqual(self.weak.items, [], "ไม่มียันต์ก็ต้องถูกริบเหมือนเดิม")
        self.assertIn(loot.iid, self.strong.items)

    def test_the_other_talismans_in_the_same_category_do_not_grant_escape(self):
        """config ระบุผลของยันต์อีกสองใบไว้คนละอย่าง (เกราะทองคำ · สายฟ้าพิพากษา)
        และยังไม่มีกลไกรองรับ — ต้องไม่ถูกเหมาเป็นยันต์หนี
        """
        others = [n.split(" (")[0] for n in C.MANUALS_AND_TALISMANS["ยันต์วิเศษ (ใช้แล้วทิ้ง)"]
                  if not n.startswith(C.TALISMAN_ESCAPE)]
        self.assertTrue(others, "หมวดนี้ต้องมียันต์ใบอื่นนอกจากใบหนี")
        for name in others:
            with self.subTest(name=name):
                self.setUp()
                self.give(self.weak, name)
                _w, _l, _log, escaped = self.fight()
                self.assertFalse(escaped, f"{name} ไม่ควรทำให้หนีได้")


class ItemKindContractTests(unittest.TestCase):
    """ฝั่งที่สร้างของกับฝั่งที่ตรวจของต้องพูดถึงชนิดเดียวกัน — บั๊กเดิมคือสองฝั่งหลุดจากกัน"""

    def test_stash_relic_creates_the_kind_combat_looks_for(self):
        sim = quiet(S.Sim, seed=5, tiers=2)
        ch = next(c for c in sim.living_in(0) if c.sentient)

        class OnlyTalismans:
            """บังคับให้สุ่มได้หมวดยันต์เสมอ เพื่อตรวจ contract ไม่ใช่ตรวจโชค"""

            @staticmethod
            def choice(seq):
                first = seq[0]
                if isinstance(first, tuple):        # รายการ (หมวด, ชื่อ) ของ MANUALS_AND_TALISMANS
                    return next(x for x in seq if x[0].startswith("ยันต์"))
                return first

        it = sim.stash_relic(ch, OnlyTalismans())
        self.assertEqual(it.kind, C.TALISMAN_KIND)
        self.assertIn(it.name, [n.split(" (")[0]
                                for n in C.MANUALS_AND_TALISMANS["ยันต์วิเศษ (ใช้แล้วทิ้ง)"]])

    def test_the_escape_name_is_a_real_entry_in_the_category(self):
        names = [n.split(" (")[0]
                 for n in C.MANUALS_AND_TALISMANS["ยันต์วิเศษ (ใช้แล้วทิ้ง)"]]
        self.assertIn(C.TALISMAN_ESCAPE, names,
                      "ชื่อยันต์หนีใน config ต้องมีอยู่จริงในหมวด ไม่งั้นไม่มีทาง match")


if __name__ == "__main__":
    unittest.main()
