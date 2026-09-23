# -*- coding: utf-8 -*-
"""แดนลับ: มีของเสมอ · และเป็นที่พัก ไม่ใช่ทางลัด

    python -m unittest test_secret_realm -v

สองกฎของโลกที่ไฟล์นี้ล็อกไว้
  1. **แดนลับมีของเสมอ ต่างกันแค่มากหรือน้อย** — ผลลัพธ์ "ไม่พบ" ไม่ควรมีอยู่ตั้งแต่แรก
     วัดจริงก่อนแก้: ค้นแดนลับ 4,693 ครั้งจบด้วย "ไม่พบ" 99% และในบันทึกผู้มีจิตใจปีที่
     118-129 จบด้วย "ไม่พบ" 13/13 ครั้ง = 13% ของการตัดสินใจทั้งหมดของตัวเอกที่หายไป
     กับการออกไปเสี่ยงตายแล้วกลับมามือเปล่า
  2. **คนที่อยู่ในแดนลับของตัวเองเลื่อนขั้นไม่ได้ ต้องออกมาข้างนอกก่อน** — ถ้าหายเข้าไป
     นอนกอดสมบัติแล้วยังไต่ขั้นได้ด้วย การซ่อนตัวจะกลายเป็นทางที่ดีที่สุดของทุกคน แล้ว
     ตัวละครก็จะหายจากเวทีไปทีละคนโดยที่ยังแข็งแกร่งขึ้นเรื่อยๆ
"""
import collections
import contextlib
import io
import unittest

from tiandao import config as C
from tiandao import events as E
from tiandao import rules as R
from tiandao import sim as S


def quiet(fn, *a, **kw):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*a, **kw)


class StubRng:
    """สุ่มแบบกำหนดผลได้ — ใช้บังคับกิ่งของ handler ทีละกิ่ง"""
    def __init__(self, value=0.0):
        self.value = value

    def random(self):
        return self.value

    def randint(self, a, b):
        return a

    def uniform(self, a, b):
        return a

    def choice(self, seq):
        seq = list(seq)
        return seq[0]

    def sample(self, seq, k):
        return list(seq)[:k]

    def shuffle(self, seq):
        return None


def a_world(seed=7, steps=20000):
    sim = quiet(S.Sim, seed=seed)
    quiet(sim.run, steps)
    return sim


class TestASecretRealmAlwaysHasSomething(unittest.TestCase):
    def test_a_search_never_comes_back_empty_handed(self):
        sim = a_world()
        seeks = [e for e in sim.log if e.kind == "ค้นแดนลับ"]
        self.assertGreater(len(seeks), 50, "ต้องมีคนออกค้นจริงพอจะวัดได้")
        self.assertEqual([e for e in seeks if e.outcome == "ไม่พบ"], [],
                         "แดนลับมีของเสมอ — ผลลัพธ์ 'ไม่พบ' ไม่ควรมีอยู่แล้ว")

    def test_how_much_varies_between_big_medium_and_small(self):
        """มีของเสมอ ไม่ได้แปลว่าได้เท่ากันทุกครั้ง"""
        sim = a_world()
        kinds = collections.Counter(e.outcome for e in sim.log if e.kind == "ค้นแดนลับ")
        self.assertGreater(kinds.get("พบซากแดนลับ", 0), 0, "ชั้นเล็ก: ซากที่ถูกกวาดไปแล้ว")
        self.assertGreater(sum(kinds.values()) - kinds.get("พบซากแดนลับ", 0), 0,
                           "ต้องมีคนเจอของชั้นที่ใหญ่กว่าซากบ้าง ไม่ใช่ได้ก้นถุงเหมือนกันหมด")
        self.assertLess(kinds.get("ค้นพบ", 0), sum(kinds.values()) * 0.5,
                        "แดนลับเต็มใบต้องยังเป็นของหายาก")

    def test_the_small_find_actually_puts_things_in_his_hands(self):
        sim = a_world()
        ch = next(c for c in sim.living() if c.alive)
        cores0, ins0 = ch.cores, ch.insight
        d = {}
        out, text = sim.ruined_cache_find(ch, StubRng(0.0), d)
        self.assertEqual(out, "พบซากแดนลับ")
        self.assertIn(ch.name, text)
        self.assertGreater(ch.cores, cores0, "ต้องได้แก่นพลังติดมือกลับมา")
        self.assertGreater(ch.insight, ins0, "และได้ความเข้าใจจากรอยจารึกที่เหลืออยู่")
        self.assertIn("เก็บตกจากซาก", d)

    def test_luck_makes_the_difference_between_two_people_at_the_same_spot(self):
        """ของที่ได้ผูกกับชะตา ไม่ใช่สุ่มล้วน — กติกาเดิมของโลก (ดู FRAGMENT_FATE_BONUS)"""
        sim = a_world()
        a, b = sim.living()[0], sim.living()[1]
        a.fate, b.fate = 0, 5
        a.cores = b.cores = 0
        sim.ruined_cache_find(a, StubRng(0.0), {})
        sim.ruined_cache_find(b, StubRng(0.0), {})
        self.assertGreater(b.cores, a.cores, "ผู้มีวาสนาต้องได้มากกว่าคนธรรมดาที่จุดเดียวกัน")


class TestTheRealmIsAShelterNotAShortcut(unittest.TestCase):
    def _hidden(self, sim):
        ch = next(c for c in sim.living() if c.alive and c.realm >= 2)
        ch.hidden, ch.hide_day = True, sim.day
        ch.seclude_until = ch.jail_until = 0
        return ch

    def test_the_engine_can_tell_the_three_kinds_of_disappearing_apart(self):
        """ซ่อนตัว · ปิดด่าน · ติดคุก ใช้ธง hidden ร่วมกัน แต่กฎตรงข้ามกัน"""
        sim = a_world(steps=6000)
        ch = self._hidden(sim)
        self.assertTrue(R.in_secret_realm(ch))
        ch.seclude_until = sim.day + 1000
        self.assertFalse(R.in_secret_realm(ch), "ปิดด่านคือการหายไปเพื่อทะลวงขั้น คนละเรื่องกัน")
        ch.seclude_until, ch.jail_until = 0, sim.day + 1000
        self.assertFalse(R.in_secret_realm(ch), "ติดคุกก็ไม่ใช่แดนลับของตัวเอง")
        ch.jail_until, ch.hidden = 0, False
        self.assertFalse(R.in_secret_realm(ch))

    def test_he_cannot_break_through_while_he_is_in_there(self):
        sim = a_world(steps=6000)
        ch = self._hidden(sim)
        w = sim.world(ch.world_id)
        ch.insight = R.need(ch, w) * 3          # สะสมเกินพอแล้ว
        realm0 = ch.realm
        out, text = R.attempt_break(sim, ch, w, StubRng(0.0))
        self.assertEqual(out, "อยู่ในแดนลับ")
        self.assertEqual(ch.realm, realm0, "ขั้นต้องไม่ขยับแม้แต่ขั้นเดียว")
        self.assertIn("แดนลับ", text)

    def test_the_same_man_can_break_through_once_he_steps_outside(self):
        """กติกาต้องเป็น 'ต้องออกมาก่อน' ไม่ใช่ 'ทำไม่ได้เลย'"""
        sim = a_world(steps=6000)
        ch = self._hidden(sim)
        w = sim.world(ch.world_id)
        ch.insight, ch.decay = R.need(ch, w) * 3, 0.0
        ch.hidden = False
        out, _text = R.attempt_break(sim, ch, w, StubRng(0.0))
        self.assertNotEqual(out, "อยู่ในแดนลับ",
                            "ออกมาข้างนอกแล้วต้องกลับมาเป็นเรื่องปกติทันที")

    def test_accumulation_is_still_allowed_in_there(self):
        """สะสมได้ แต่เลื่อนขั้นไม่ได้ — แดนลับเป็นที่พัก ไม่ใช่คุก"""
        sim = a_world(steps=6000)
        ch = self._hidden(sim)
        before = R.accumulation(ch)
        R.cultivate(ch, 365)
        self.assertGreater(R.accumulation(ch), before)


class TestComingBackOut(unittest.TestCase):
    def test_the_world_hears_about_it(self):
        sim = a_world(steps=60000)
        out = [e for e in sim.log if e.kind == "ออกจากแดนลับ"]
        self.assertGreater(len(out), 0, "คนหายไปหลายสิบปีแล้วโผล่กลับมา ต้องเป็นเหตุการณ์ที่เห็นได้")
        e = out[0]
        self.assertIn("เวลาที่หายไป", e.deltas)
        self.assertIn("ที่แดนลับพรากไป", e.deltas)
        self.assertIn("ขั้นพลังตอนออกมา", e.deltas)

    def test_it_reads_as_a_yearly_beat(self):
        """หน้าอ่านปิดตอนเมื่อเจอเหตุการณ์รายปี การกลับเข้าสู่เวทีต้องนับเป็นจังหวะรายปี"""
        self.assertEqual(E.SCALE_OF["ออกจากแดนลับ"], E.SCALE_YEAR)
        self.assertEqual(E.SCALE_OF["ออกจากด่าน"], E.SCALE_YEAR)


if __name__ == "__main__":
    unittest.main()
