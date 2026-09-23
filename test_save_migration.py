# -*- coding: utf-8 -*-
"""เซฟเก่าต้องได้ของใหม่ครบ — ไม่ใช่โลกที่กลไกใหม่ปิดอยู่เงียบๆ

    python -m unittest test_save_migration -v

บทเรียนที่ไฟล์นี้ล็อกไว้
------------------------
ทุกครั้งที่เพิ่ม field ใหม่ให้ Character เราคิดว่าแค่ setdefault ใน __setstate__ ก็จบ แต่
setdefault ให้ **ค่าว่าง** ซึ่งกลไกใหม่อ่านว่า "ไม่มี/เป็นศูนย์" ทั้งที่ความจริงคือ "ไม่รู้"
ผลคือกลไกใหม่ทำงานเฉพาะกับโลกที่สร้างใหม่ และปิดสนิทกับโลกที่ผู้ใช้เดินมาแล้ว 152 ปี
ซึ่งเป็นโลกเดียวที่เขาสนใจ

วัดจริงจากเซฟปีที่ 152 ของผู้ใช้ ก่อนแก้:
  · ผู้ฝึก 303 จาก 578 คน (52%) ไม่มีธาตุประจำตัว และยิ่งขั้นสูงยิ่งแย่ (ขั้น 5 มีแค่ 26%)
    เพราะคนขั้นสูง = คนที่มีอยู่ก่อนระบบห้าธาตุทั้งนั้น
  · ผู้ฝึก 345 จาก 432 คนที่ "มีวิชาอยู่ในมือ" สอนวิชาของตัวเองไม่ได้เลย เพราะ mastery ว่าง
    = ฝึกมาศูนย์ครั้ง ซึ่งขัดกับกติกาของโลกเองที่ว่า "เรียนจบครั้งแรก = ฝึกไปแล้วหนึ่งครั้ง"
    ในบันทึกเห็นเป็นตัวเอกชุยอันสั่งถ่ายทอดวิชา 4 ครั้ง ได้ "ไม่มีวิชาจะสอน" ทั้ง 4 ครั้ง
  · และ rules.skill_power คูณ practice_mastery(0)=0 ทุกวิชา → ทั้งโลกถูกลดพลังเงียบๆ
"""
import contextlib
import io
import os
import pickle
import tempfile
import unittest

from tiandao import config as C
from tiandao import persist
from tiandao import rules as R
from tiandao import sim as S


def quiet(fn, *a, **kw):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*a, **kw)


def an_old_save():
    """เซฟที่ 'เก่า' จริงๆ — ลบ field ใหม่ออกจากตัวละครทุกคน แล้วเขียนด้วยรูปแบบไฟล์ยุคก่อน

    รูปแบบยุคก่อนคือ pickle ของ Sim เปล่าๆ ไม่มีซองบอกรุ่น (ดู persist.SAVE_VERSION)
    ต้องเขียนเองตรงนี้ ไม่ใช้ persist.save_sim เพราะ save_sim เขียนไฟล์ **รุ่นปัจจุบัน**
    ซึ่ง (ถูกต้องแล้ว) จะไม่ถูก migrate ตอนโหลด
    """
    sim = quiet(S.Sim, seed=11)
    quiet(sim.run, 4000)
    for ch in sim.cast:
        ch.__dict__.pop("element", None)
        ch.__dict__.pop("mastery", None)
    path = os.path.join(tempfile.mkdtemp(), "old.save")
    with open(path, "wb") as f:
        pickle.dump(sim, f, protocol=pickle.HIGHEST_PROTOCOL)
    return path


class TestAnOldSaveGetsTheFiveElements(unittest.TestCase):
    def test_everyone_comes_back_with_an_element(self):
        sim = persist.load_sim(an_old_save())
        alive = [c for c in sim.cast if c.alive]
        self.assertGreater(len(alive), 20, "ต้องมีคนพอจะวัดได้")
        missing = [c.name for c in alive if not getattr(c, "element", "")]
        self.assertEqual(missing, [], "โหลดเซฟเก่าแล้วต้องไม่มีใครไร้ธาตุ")

    def test_the_element_is_decided_by_who_he_is_not_by_when_we_loaded(self):
        """เติมย้อนหลังต้องไม่ขยับ RNG หลัก ไม่งั้นโหลดเซฟเดิมแล้วอนาคตเปลี่ยน"""
        path = an_old_save()
        a = persist.load_sim(path)
        b = persist.load_sim(path)
        self.assertEqual([c.element for c in a.cast], [c.element for c in b.cast])
        self.assertEqual(a.rng.getstate(), b.rng.getstate(),
                         "การเติม field ย้อนหลังห้ามแตะ RNG หลักของโลก")


class TestAnOldSaveCanTeachWhatItKnows(unittest.TestCase):
    def test_a_skill_in_his_hands_counts_as_practised_at_least_once(self):
        sim = persist.load_sim(an_old_save())
        holders = [c for c in sim.cast if c.alive and c.skills]
        self.assertGreater(len(holders), 5, "ต้องมีคนถือวิชาพอจะวัดได้")
        for ch in holders:
            for name in ch.skills:
                self.assertGreaterEqual(
                    ch.mastery.get(name, 0), C.TEACH_MIN_REPS,
                    f"{ch.name} ถือ「{name}」อยู่ในมือ แต่นับว่าฝึกมา 0 ครั้ง")

    def test_nobody_who_knows_something_is_left_unable_to_teach_it(self):
        sim = persist.load_sim(an_old_save())
        holders = [c for c in sim.cast if c.alive and c.skills]
        mute = [c.name for c in holders
                if not any(c.mastery.get(n, 0) >= C.TEACH_MIN_REPS for n in c.skills)]
        self.assertEqual(mute, [], "คนที่มีวิชาต้องสอนวิชานั้นได้")

    def test_the_backfill_does_not_hand_out_free_power(self):
        """เติมแค่ 'หนึ่งครั้ง' ซึ่งเป็นค่าต่ำสุดที่ยังจริง ไม่ใช่เติมจนช่ำชอง"""
        sim = persist.load_sim(an_old_save())
        for ch in sim.cast:
            for name in ch.skills:
                self.assertEqual(ch.mastery.get(name), 1,
                                 "ค่าที่เติมต้องเป็นหนึ่ง ไม่ใช่ค่าที่เดาเอาว่าเขาฝึกมาเยอะ")

    def test_power_from_a_known_skill_is_not_silently_docked(self):
        sim = persist.load_sim(an_old_save())
        ch = next(c for c in sim.cast if c.alive and c.skills)
        got = R.skill_power(ch)
        ch.mastery = {}
        self.assertGreater(got, R.skill_power(ch),
                           "mastery ว่างเคยกดพลังวิชาทั้งโลกลงเหลือแค่ส่วนฐาน")


class TestACurrentSaveIsNotTreatedAsOld(unittest.TestCase):
    """เกณฑ์ตัดสินต้องเป็น "รุ่นของไฟล์" ไม่ใช่ "ค่าใน field ว่างไหม"

    เกณฑ์เดิมตัดสินจากค่า (mastery ว่าง = เซฟเก่า) ซึ่งตรงกับโลกที่กำลังเดินอยู่ด้วย
    เซฟที่เพิ่งเขียนจากโค้ดปัจจุบันจึงถูกแก้ข้อมูลตอนโหลดทุกครั้ง
    """

    def test_a_save_written_now_declares_the_current_version(self):
        sim = quiet(S.Sim, seed=11)
        quiet(sim.run, 1500)
        path = os.path.join(tempfile.mkdtemp(), "new.save")
        persist.save_sim(sim, path)
        _, version = persist.read_save(path)
        self.assertEqual(version, persist.SAVE_VERSION)
        self.assertEqual(persist.read_save(an_old_save())[1], 0, "เซฟยุคก่อนต้องนับเป็นรุ่น 0")

    def test_loading_a_current_save_does_not_touch_mastery_or_bloodline(self):
        sim = quiet(S.Sim, seed=11)
        quiet(sim.run, 4000)
        before = {c.cid: (dict(c.mastery), dict(c.bloodline_affinity), c.element,
                          list(c.skills), c.birth_wid)
                  for c in sim.cast}
        path = os.path.join(tempfile.mkdtemp(), "new.save")
        persist.save_sim(sim, path)
        loaded = persist.load_sim(path)
        after = {c.cid: (dict(c.mastery), dict(c.bloodline_affinity), c.element,
                         list(c.skills), c.birth_wid)
                 for c in loaded.cast}
        self.assertEqual(after, before)
        # ต้องมีค่าที่ "ว่างอยู่จริงในโลกที่กำลังเดิน" อยู่บ้าง ไม่งั้นเทสต์นี้ว่างเปล่า — พิสูจน์
        # ไม่ได้ว่าเกณฑ์เดิม (ตัดสินจากค่า) จะเข้าใจผิดว่าเซฟปัจจุบันเป็นเซฟเก่า
        # เดิมใช้ "มีวิชาแต่ไม่มี mastery" เป็นตัวยึด แต่ตอนนี้กติกาห้ามมีเคสนั้นแล้ว
        # (ดู Character.learn_skill และ test_skill_mastery.py) จึงย้ายมายึด bloodline_affinity
        # ซึ่งยังว่างได้จริงเมื่อสายเลือดถูกเพิ่มเข้ามาทีหลัง — เป็นเกณฑ์ค่าอีกตัวที่ migration ใช้
        blanks = [c for c in sim.cast
                  if any(share > 0.0 and line not in c.bloodline_affinity
                         for line, share in c.blood.items())]
        self.assertTrue(blanks, "โลกที่เดินอยู่ต้องมีเคสที่เกณฑ์เดิมเข้าใจผิดว่าเป็นเซฟเก่า")

    def test_an_old_save_still_gets_migrated(self):
        """กันไม่ให้ 'แก้ให้เซฟใหม่ไม่ถูกแตะ' กลายเป็น 'ปิด migration ทิ้งทั้งระบบ'"""
        sim = persist.load_sim(an_old_save())
        alive = [c for c in sim.cast if c.alive]
        self.assertTrue(all(c.element for c in alive))
        self.assertTrue(all(c.mastery.get(n, 0) >= 1 for c in alive for n in c.skills))


class TestAFreshWorldIsUnaffected(unittest.TestCase):
    def test_a_newborn_still_earns_his_mastery_the_hard_way(self):
        """การเติมย้อนหลังต้องไม่เผลอไปเติมให้โลกที่ยังเดินอยู่ด้วย"""
        sim = quiet(S.Sim, seed=11)
        quiet(sim.run, 4000)
        blank = [c for c in sim.cast if c.alive and not c.skills]
        self.assertTrue(blank, "โลกใหม่ต้องยังมีคนที่ยังไม่มีวิชา")
        for ch in blank:
            self.assertEqual(ch.mastery, {}, "ไม่มีวิชา ก็ต้องไม่มีความชำนาญ")

    def test_a_fresh_world_has_no_gap_for_the_migration_to_fill(self):
        """โลกที่เดินด้วยโค้ดปัจจุบันต้องไม่มีช่องว่างที่ migration ของเซฟเก่าตั้งใจมาซ่อม

        นี่คือฝั่งตรงข้ามของ TestAnOldSaveCanTeachWhatItKnows: เซฟเก่าต้องถูกซ่อม
        ส่วนโลกใหม่ต้องไม่เคยเสียตั้งแต่แรก ถ้าข้อนี้แพ้ แปลว่ามีทางแจกวิชาทางใหม่ที่ลืม
        ตั้งความชำนาญอีกแล้ว (ดู Character.learn_skill)
        """
        sim = quiet(S.Sim, seed=11)
        quiet(sim.run, 4000)
        holders = [c for c in sim.cast if c.skills]
        self.assertGreater(len(holders), 20, "ต้องมีคนถือวิชามากพอจะวัดได้")
        hollow = [(c.name, n) for c in sim.cast for n in c.skills if c.mastery.get(n, 0) < 1]
        self.assertEqual(hollow, [], "โลกใหม่ต้องไม่มีใครถือวิชาที่ฝึกมาศูนย์ครั้ง")


if __name__ == "__main__":
    unittest.main()
