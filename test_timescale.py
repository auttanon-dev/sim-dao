# -*- coding: utf-8 -*-
"""ช่วงเวลาสามชั้น: วัน · เดือน · ปี — และการปิดด่านที่โลกไม่รออยู่เหมือนเดิม

    python -m unittest test_timescale -v

ที่มา (วัดจริงจากบันทึกผู้มีจิตใจ 72 ปี · 1,042 บรรทัด):
  ช่องว่างระหว่างการตัดสินใจของตัวละครคนเดียวกัน **มัธยฐาน 324 วัน** — ตัวเอกลงมือปีละครั้ง
  รายวัน (<30 วัน) มีแค่ **2%** · รายเดือน 53% · รายปี 43%
  ผลคือเรื่องกระโดดเป็นปีๆ ตลอด ไม่มีจังหวะ "วันต่อวัน" ให้เรื่องปะทะเกิดขึ้นเลย และการข้ามปี
  ก็เป็นการข้ามแบบ **ไม่รู้ตัว** (มาจาก gap ของเหตุการณ์) ไม่มีฉากไหนบอกว่าโลกเปลี่ยนไปอะไร
"""
import collections
import contextlib
import io
import statistics as st
import unittest

from tiandao import config as C
from tiandao import events as E
from tiandao import intent as IN
from tiandao import sim as S


def quiet(fn, *a, **kw):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*a, **kw)


class StubRng:
    def __init__(self, value=0.0):
        self.value = value

    def random(self):
        return self.value

    def randint(self, a, b):
        return a

    def uniform(self, a, b):
        return a

    def choice(self, seq):
        return seq[0]


SECLUDE = next(e for e in E.EVENT_TABLE if e["kind"] == "ปิดด่าน")


class TestThreeBands(unittest.TestCase):
    def test_every_action_has_a_time_band(self):
        for e in E.EVENT_TABLE:
            self.assertIn(E.SCALE_OF[e["kind"]], (E.SCALE_DAY, E.SCALE_MONTH, E.SCALE_YEAR))

    def test_the_bands_hold_the_right_kinds(self):
        day = {k for k, v in E.SCALE_OF.items() if v == E.SCALE_DAY}
        month = {k for k, v in E.SCALE_OF.items() if v == E.SCALE_MONTH}
        year = {k for k, v in E.SCALE_OF.items() if v == E.SCALE_YEAR}
        for k in ("ประลอง", "ล้างแค้น", "ทรยศ", "ให้สัญญา", "เหตุการณ์เมือง", "ทำนา"):
            self.assertIn(k, day, f"{k} คือเรื่องเฉพาะหน้า ต้องอยู่จังหวะรายวัน")
        for k in ("เดินทาง", "ค้นแดนลับ", "ฝึกวิชา", "ล่าอสูร", "หลอมยา"):
            self.assertIn(k, month, f"{k} คือการเดินทาง/อาชีพรอง ต้องอยู่จังหวะรายเดือน")
        for k in ("บำเพ็ญ", "ปิดด่าน", "ข้ามขั้น", "ข้ามฟ้า"):
            self.assertIn(k, year, f"{k} คือการทะลวงขั้น/ประวัติศาสตร์ ต้องอยู่จังหวะรายปี")

    def test_the_calendar_reads_like_a_calendar(self):
        self.assertEqual(E.date_words(0), "ปีที่ 0 เดือน 1 วันที่ 1")
        self.assertTrue(E.date_words(12 * 365 + 95).startswith("ปีที่ 12 เดือน 4"))

    def test_a_real_run_actually_has_daily_texture(self):
        sim = quiet(S.Sim, seed=11)
        quiet(sim.run, 30000)
        per = collections.defaultdict(list)
        for e in sim.log:
            # วัยเด็กเดินปีละครั้งโดยตั้งใจ — วัดจังหวะเฉพาะการกระทำของผู้ใหญ่
            if e.actor >= 0 and e.kind != "เติบโต":
                per[e.actor].append(e.day)
        gaps = [b - a for v in per.values() if len(v) > 3
                for a, b in zip(sorted(v), sorted(v)[1:])]
        self.assertGreater(len(gaps), 500)
        median = st.median(gaps)
        share_day = sum(1 for g in gaps if g < 30) / len(gaps)
        # ก่อนแก้: มัธยฐาน 324 วัน · รายวัน 2%
        self.assertLess(median, 90, f"มัธยฐานช่องว่าง {median} วัน — ยังกระโดดเป็นปีอยู่")
        self.assertGreater(share_day, 0.30, f"จังหวะรายวันมีแค่ {share_day * 100:.0f}%")
        # แต่ต้องไม่กลายเป็นโลกที่ทุกอย่างเกิดวันต่อวันจนไม่มีจังหวะรายปีเหลือ
        self.assertGreater(sum(1 for g in gaps if g > 365) / len(gaps), 0.05,
                           "ต้องยังมีการข้ามปีอยู่ ไม่งั้นการบำเพ็ญไม่เหลือน้ำหนัก")


class TestSeclusion(unittest.TestCase):
    def _ready(self, seed=7):
        sim = quiet(S.Sim, seed=seed, tiers=3)
        w = sim.world(0)
        ch = next(c for c in sim.living_in(0) if c.sentient and c.age(sim.day) >= 16)
        ch.insight, ch.refine, ch.decay = 40.0, 0.0, 0.0
        ch.fate = 2          # ชะตาเหลือ — ไม่งั้นเลเยอร์ "อยู่รอด" จะกดเจตนาสายบำเพ็ญทิ้งทั้งชุด
        return sim, w, ch

    def test_entering_seclusion_takes_him_out_of_the_world(self):
        sim, w, ch = self._ready()
        out, text, d = sim.resolve(SECLUDE, ch, None, w, 30, StubRng())
        self.assertEqual(out, "เข้าด่าน")
        self.assertTrue(ch.hidden)
        self.assertGreater(ch.seclude_until, sim.day)
        self.assertIn("กำหนดออกจากด่าน", d)
        self.assertIn("ties", ch.seclude_snap, "ต้องถ่ายภาพโลกไว้ก่อนปิดประตู")

    def test_he_does_nothing_while_inside(self):
        sim, w, ch = self._ready()
        sim.resolve(SECLUDE, ch, None, w, 30, StubRng())
        start = sim.seq
        quiet(sim.run, 300)
        chosen = {e["kind"] for e in E.EVENT_TABLE}
        # เหตุการณ์ของโลกที่ "เกิดกับเขา" ระหว่างอยู่ในด่านยังเกิดได้ (ภัยพิบัติ · จิตมารกำเริบ
        # จนตกเป็นมารกลางด่าน ซึ่งเป็นหายนะคลาสสิกของการปิดด่านอยู่แล้ว) ที่ต้องไม่มีคือ
        # **การกระทำที่เขาเลือกเอง** — ปิดประตูแล้วต้องไม่โผล่ไปเดินตลาดหรือประลองกับใคร
        acted = [e.kind for e in sim.log[start:]
                 if e.actor == ch.cid and e.kind in chosen and e.kind != "ปิดด่าน"]
        self.assertEqual(acted, [], "คนปิดด่านต้องไม่โผล่ไปลงมือทำอะไรข้างนอก")

    def test_coming_out_reports_what_changed(self):
        sim, w, ch = self._ready()
        sim.resolve(SECLUDE, ch, None, w, 30, StubRng())
        before = ch.insight
        for _ in range(80):
            if not ch.hidden or not ch.alive:
                break
            quiet(sim.run, 500)
        if not ch.alive:
            self.skipTest("ตายในด่าน — เป็นไปได้ตามกฎอายุขัย")
        self.assertFalse(ch.hidden)
        self.assertEqual(ch.seclude_until, 0)
        self.assertGreater(ch.insight, before, "อยู่ในด่านหลายปีต้องได้ความเข้าใจกลับมา")
        out = [e for e in sim.log if e.kind == "ออกจากด่าน" and e.actor == ch.cid]
        self.assertTrue(out, "การออกจากด่านต้องเป็นเหตุการณ์ที่บันทึกไว้")
        d = out[-1].deltas
        for key in ("เวลาในด่าน", "ที่ได้จากด่าน", "ขั้นของข้าตอนนี้", "โลกที่เปลี่ยนไป"):
            self.assertIn(key, d, f"รายงานออกจากด่านต้องมี '{key}'")

    def test_the_diff_names_the_dead_and_the_risen(self):
        sim, w, ch = self._ready()
        friend = next(c for c in sim.living_in(0) if c.cid != ch.cid and c.sentient)
        rival = next(c for c in sim.living_in(0)
                     if c.cid not in (ch.cid, friend.cid) and c.sentient)
        ch.bonds[friend.cid] = 5
        ch.rivals[rival.cid] = 5
        sim.resolve(SECLUDE, ch, None, w, 30, StubRng())
        sim.kill(friend, "ตายระหว่างที่เขาอยู่ในด่าน")
        rival.realm = min(C.REALM_CAP, rival.realm + 2)
        rival.peak_realm = rival.realm
        d = sim.seclusion_diff(ch, w, 5)
        self.assertIn(friend.name, d.get("คนที่ไม่ได้อยู่รอเขา", ""))
        self.assertIn(rival.name, d.get("คนที่ไต่แซงไปแล้ว", ""))

    def test_seclusion_is_only_tempting_when_there_is_something_to_break(self):
        sim, w, ch = self._ready()
        ch.insight, ch.refine = 0.0, 0.0
        low = IN.weigh(ch, sim, E.EVENT_TABLE, False).get("ปิดด่าน", 0)
        ch.insight = 500.0
        high = IN.weigh(ch, sim, E.EVENT_TABLE, False).get("ปิดด่าน", 0)
        self.assertTrue(ch.at_bottleneck())
        self.assertGreater(high, low + 10,
                           "ปิดด่านตอนไม่มีอะไรจะทะลวง = ทิ้งเวลาหลายปีไปเปล่าๆ")

    def test_the_world_keeps_secluding_people_over_a_long_run(self):
        sim = quiet(S.Sim, seed=11)
        quiet(sim.run, 40000)
        entered = [e for e in sim.log if e.outcome == "เข้าด่าน"]
        left = [e for e in sim.log if e.kind == "ออกจากด่าน"]
        self.assertGreater(len(entered), 20, "ต้องมีคนเลือกปิดด่านจริง")
        self.assertGreater(len(left), 5, "และต้องมีคนออกมาเจอโลกใหม่จริง")
        changed = [e for e in left
                   if e.deltas.get("โลกที่เปลี่ยนไป", "").find("เหมือนวันที่เขาปิดประตู") < 0]
        self.assertGreater(len(changed), 0,
                           "อย่างน้อยต้องมีคนที่ออกมาแล้วพบว่าโลกไม่เหมือนเดิม")

    def test_seclusion_reaches_the_menu_of_the_people_who_need_it(self):
        """น้ำหนักสูงอย่างเดียวไม่พอ — ต้องติด 12 อันดับแรกถึงจะมีตัวตนสำหรับผู้มีจิตใจ

        เทสเดิม (`..._only_tempting_when_there_is_something_to_break`) วัดแค่ว่าน้ำหนัก "ขึ้น"
        ซึ่งผ่านมาตลอดทั้งที่ของจริงใช้ไม่ได้ เพราะเอนจินสุ่มตามน้ำหนัก (ค่าน้อยก็ยังมีโอกาส) แต่
        ผู้มีจิตใจเห็นเมนูแค่ `MENU_MAX_ACTIONS` อันดับแรก ค่าที่ "ขึ้นแล้วแต่ยังเตี้ย" จึงหายไปเงียบๆ
        วัดจริงปีที่ 104-118: ปิดด่านอันดับ 18/18 · โผล่ในเมนู 2/60 คน · ผู้มีจิตใจใช้จริง 0 ครั้ง
        """
        from tiandao.mind import actions as A
        from tiandao.mind import config as MC
        sim, w, ch = self._ready()
        ch.insight, ch.refine = 0.0, 0.0
        menu_far = A.build_menu(IN.weigh(ch, sim, E.EVENT_TABLE, False),
                                E.EVENT_TABLE, MC.MENU_MAX_ACTIONS)
        ch.insight = 500.0
        menu_near = A.build_menu(IN.weigh(ch, sim, E.EVENT_TABLE, False),
                                 E.EVENT_TABLE, MC.MENU_MAX_ACTIONS)
        self.assertNotIn("ปิดด่าน", menu_far,
                         "ยังไม่มีอะไรจะทะลวง ก็ไม่ควรมีตัวเลือกทิ้งชีวิตสามถึงแปดปี")
        self.assertIn("ปิดด่าน", menu_near,
                      "ถึงคอขวดแล้วตัวเลือกนี้ต้องอยู่ในสิ่งที่ตัวละคร 'เห็น' จริงๆ")

    def test_the_menu_share_across_a_live_world(self):
        """วัดทั้งโลกจริง ไม่ใช่ตัวละครที่เซ็ตค่าเอง — ต้องเห็นตัวเลือกนี้บ้าง แต่ไม่ใช่ทุกคน"""
        from tiandao.mind import actions as A
        from tiandao.mind import config as MC
        sim = quiet(S.Sim, seed=7)
        quiet(sim.run, 30000)
        pool = [c for c in sim.cast
                if c.alive and getattr(c, "sentient", True) and c.age(sim.day) > 20]
        pool.sort(key=lambda c: -c.rank())
        pool = pool[:120]
        seen = sum(1 for c in pool
                   if "ปิดด่าน" in A.build_menu(
                       IN.weigh(c, sim, E.EVENT_TABLE, False),
                       E.EVENT_TABLE, MC.MENU_MAX_ACTIONS))
        self.assertGreater(seen, len(pool) * 0.05,
                           "น้อยเกินไป = ผู้มีจิตใจจะไม่มีวันเลือกปิดด่านเลย (ของเดิมวัดได้ 3%)")
        self.assertLess(seen, len(pool) * 0.8,
                        "มากเกินไป = ทั้งโลกเอาแต่ปิดด่าน เรื่องจะหยุดเดิน")


if __name__ == "__main__":
    unittest.main()
