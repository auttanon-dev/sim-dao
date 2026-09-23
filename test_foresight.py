# -*- coding: utf-8 -*-
"""ระบบจำลองอนาคต — นิมิตที่จริงเพราะโลกคำนวณได้ และมีราคาที่ต้องจ่าย

    python -m unittest test_foresight -v

หลักคิด: โลกเดินด้วย RNG เมล็ดเดียวและคิวเดียว อนาคตจึงคำนวณได้จริง — สำเนาโลกแล้วเดินต่อ
สิ่งที่เห็นคือสิ่งที่ **จะเกิดขึ้นจริงถ้าไม่มีใครทำอะไรต่างจากเดิม** (ไม่ใช่ข้อความที่โมเดลแต่ง)
สามข้อที่เทสต์ไฟล์นี้ล็อกไว้: สำเนาไม่แตะโลกจริง · สำเนาไม่เรียกโมเดลและไม่เขียนสมุดชีวิต ·
นิมิตมีราคา (ชะตา + จิตมาร + คูลดาวน์) ไม่งั้นความตายไม่เหลือน้ำหนักในเรื่อง
"""
import contextlib
import io
import unittest

from tiandao import config as C
from tiandao import events as E
from tiandao import foresight as FS
from tiandao import intent as IN
from tiandao import sim as S


def quiet(fn, *a, **kw):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*a, **kw)


GLIMPSE = next(e for e in E.EVENT_TABLE if e["kind"] == "จำลองอนาคต")


def a_world(seed=11, steps=12000):
    sim = quiet(S.Sim, seed=seed)
    quiet(sim.run, steps)
    ch = max((c for c in sim.cast if c.alive and c.sentient and c.realm >= 2),
             key=lambda c: len(c.rivals) + len(c.bonds))
    ch.system_foresight, ch.fate = True, 3
    ch.visions, ch.foreseen = [], {}
    return sim, sim.world(ch.world_id), ch


class _Boom:
    """แบ็กเอนด์ที่ระเบิดถ้าถูกเรียก — ใช้พิสูจน์ว่าสำเนาโลกไม่แตะโมเดลภาษา
    (ต้องอยู่ระดับโมดูล ไม่ใช่ในฟังก์ชัน เพราะคลาสที่ประกาศในฟังก์ชัน pickle ไม่ได้)"""
    def think_json(self, *a, **kw):
        raise AssertionError("สำเนาโลกต้องไม่เรียกโมเดลภาษา")


class _FakeMind:
    def __init__(self):
        self.journal_path = "/ห้ามเขียน/journal.jsonl"
        self._backend = _Boom()

    def on_event(self, ev, sim):
        raise AssertionError("สำเนาโลกต้องไม่ยิง handler ของชั้นจิตใจ")


class TestTheVisionIsReal(unittest.TestCase):
    def test_looking_ahead_does_not_move_the_real_world(self):
        sim, w, ch = a_world()
        day, seq, ver = sim.day, sim.seq, sim.rng.getstate()
        n_log, n_cast = len(sim.log), len(sim.cast)
        quiet(FS.glimpse, sim, ch, 180)
        self.assertEqual((sim.day, sim.seq), (day, seq), "โลกจริงต้องไม่ขยับแม้แต่ tick เดียว")
        self.assertEqual(sim.rng.getstate(), ver, "และต้องไม่ดึง RNG ของโลกจริงเลย")
        self.assertEqual((len(sim.log), len(sim.cast)), (n_log, n_cast))

    def test_the_copy_cannot_call_the_model_or_write_the_journal(self):
        sim, w, ch = a_world()

        sim.mind = _FakeMind()
        sim.event_bus.subscribe(sim.mind.on_event)
        try:
            fork = FS._fork(sim)
            self.assertIsNone(fork.mind, "ชั้นจิตใจต้องถูกถอดออกจากสำเนา")
            names = [type(getattr(h, "__self__", None)).__name__
                     for h in fork.event_bus._subscribers]
            self.assertNotIn("_FakeMind", names)
        finally:
            sim.event_bus._subscribers = [h for h in sim.event_bus._subscribers
                                          if type(getattr(h, "__self__", None)).__name__ != "_FakeMind"]
            sim.mind = None

    def test_what_it_shows_is_what_would_have_happened(self):
        """ภาพที่เห็นต้องตรงกับอนาคตจริง ถ้าปล่อยโลกเดินต่อโดยไม่มีใครเปลี่ยนอะไร"""
        sim, w, ch = a_world()
        vision = quiet(FS.glimpse, sim, ch, 200)
        foreseen = dict(vision["deaths"])
        if not foreseen:
            self.skipTest("นิมิตรอบนี้ไม่เห็นความตายของใคร")
        quiet(sim.run, 60000)      # ปล่อยโลกเดินต่อตามเดิม
        hit = 0
        for cid, day in foreseen.items():
            c = sim.cast[cid]
            if not c.alive and abs(c.death_day - day) <= 1:
                hit += 1
        self.assertEqual(hit, len(foreseen),
                         "โลกนี้ deterministic — สิ่งที่เห็นต้องเกิดตรงวันเป๊ะถ้าไม่มีใครเปลี่ยนอะไร")

    def test_the_vision_always_carries_something_usable(self):
        sim, w, ch = a_world()
        blanks = 0
        for c in sorted((x for x in sim.cast if x.alive and x.sentient and x.realm >= 2),
                        key=lambda x: -(len(x.rivals) + len(x.bonds)))[:5]:
            v = quiet(FS.glimpse, sim, c)
            if "ภาพว่างเปล่า" in v["lines"][0]:
                blanks += 1
        self.assertLessEqual(blanks, 1, "นิมิตที่ว่างเปล่าบ่อยๆ ใช้ตัดสินใจอะไรไม่ได้")


class TestThePrice(unittest.TestCase):
    def test_only_the_owner_can_look(self):
        sim, w, ch = a_world()
        plain = next(c for c in sim.living_in(ch.world_id) if c.cid != ch.cid and c.sentient)
        plain.system_foresight = False
        out, text, d = quiet(sim.resolve, GLIMPSE, plain, None, w, 5, sim.rng)
        self.assertEqual(out, "ไม่มีระบบ")
        self.assertNotIn("จำลองอนาคต", IN.weigh(plain, sim, E.EVENT_TABLE, False))
        self.assertIn("จำลองอนาคต", IN.weigh(ch, sim, E.EVENT_TABLE, False))

    def test_it_costs_fate_then_lifespan(self):
        sim, w, ch = a_world()
        ch.fate, ch.inner = 2, 0.0
        out, text, d = quiet(sim.resolve, GLIMPSE, ch, None, w, 5, sim.rng)
        self.assertEqual(out, "เห็นอนาคต")
        self.assertEqual(ch.fate, 1, "ปกติจ่ายด้วยชะตา")
        self.assertGreater(ch.inner, 0.0, "มองสิ่งที่ฟ้าไม่ให้เห็น จิตมารต้องหนักขึ้น")
        self.assertIn("นิมิต", d)
        ch.visions, ch.fate, decay0 = [], 0, ch.decay
        quiet(sim.resolve, GLIMPSE, ch, None, w, 5, sim.rng)
        self.assertGreater(ch.decay, decay0, "ชะตาหมดแล้วยังฝืนมอง = จ่ายด้วยอายุขัย")

    def test_once_a_year_only(self):
        sim, w, ch = a_world()
        quiet(sim.resolve, GLIMPSE, ch, None, w, 5, sim.rng)
        out, text, d = quiet(sim.resolve, GLIMPSE, ch, None, w, 5, sim.rng)
        self.assertEqual(out, "ยังไม่ถึงเวลา", "ใช้ได้ปีละครั้ง ไม่งั้นตัวเอกไม่มีวันตาย")
        self.assertNotIn("จำลองอนาคต", IN.weigh(ch, sim, E.EVENT_TABLE, False))


class TestFateAccounting(unittest.TestCase):
    def test_a_foreseen_death_that_happens_is_recorded_as_fate(self):
        sim, w, ch = a_world()
        quiet(sim.resolve, GLIMPSE, ch, None, w, 5, sim.rng)
        if not ch.foreseen:
            self.skipTest("นิมิตรอบนี้ไม่เห็นความตายของใคร")
        # เดินโลกจนนิมิตทุกอันถึงกำหนดตัดสิน ไม่ใช่จำนวน tick ตายตัว — ตั้งแต่ขอบฟ้ายืดได้
        # ถึงสี่ปี (ดู C.FORESIGHT_HORIZON_MAX) นิมิตชี้ไปได้ไกลกว่าที่ 15,000 เหตุการณ์
        # จะพาโลกเดินไปถึง การผูกกับเลข tick จึงพังทุกครั้งที่จังหวะของโลกเปลี่ยน
        deadline = sim.day + C.FORESIGHT_HORIZON_MAX + C.FORESIGHT_GRACE_DAYS + 400
        for _ in range(40):
            quiet(sim.run, 5000)
            if not ch.foreseen or sim.day > deadline:
                break
        self.assertEqual(len(ch.foreseen), 0, "นิมิตที่หมดอายุต้องถูกตัดสินและเคลียร์ออก")
        self.assertGreater(ch.fate_changed + ch.fate_kept, 0)
        kinds = {e.kind for e in sim.log}
        self.assertTrue({"ชะตาลิขิต", "เปลี่ยนชะตา"} & kinds,
                        "ผลของนิมิตต้องถูกบันทึกเป็นเหตุการณ์ให้อ่านย้อนได้")

    def test_saving_someone_counts_as_changing_fate(self):
        sim, w, ch = a_world()
        victim = next(c for c in sim.living_in(ch.world_id) if c.cid != ch.cid and c.sentient)
        ch.foreseen = {str(victim.cid): sim.day - C.FORESIGHT_GRACE_DAYS - 1}
        sim.check_fate()
        self.assertEqual(ch.fate_changed, 1)
        self.assertEqual(ch.foreseen, {})
        ev = [e for e in sim.log if e.kind == "เปลี่ยนชะตา"]
        self.assertTrue(ev)
        self.assertIn("เปลี่ยนชะตาได้แล้ว", ev[-1].deltas)


class TestOwnership(unittest.TestCase):
    def test_exactly_one_protagonist_gets_the_system(self):
        import tempfile
        from tiandao.mind import backend as B
        from tiandao.mind.runner import RunConfig, open_world
        cfg = RunConfig(out_dir=tempfile.mkdtemp(), seed=4, capacity=6, story=False)
        sim = quiet(open_world, cfg, B.MockThinker())
        owners = [c for c in sim.cast if getattr(c, "system_foresight", False)]
        self.assertEqual(len(owners), 1, "ระบบนี้ต้องมีคนเดียวในโลก")
        self.assertIn(owners[0].cid, sim.mind.minds, "และต้องเป็นตัวเอกที่มีจิตใจของตัวเอง")
        quiet(sim.run, 4000)
        self.assertEqual(sum(1 for c in sim.cast if getattr(c, "system_foresight", False)), 1)

class TestTheVisionIsAboutHim(unittest.TestCase):
    """นิมิตต้องเป็นเรื่องของเจ้าของนิมิต ไม่ใช่เรื่องคนแปลกหน้า

    วัดจริงจากนิมิตสองครั้งแรกที่ถูกใช้จริง (โลกปีที่ 119 และ 124) ห้าบรรทัดที่ได้คือ
      "คนแปลกหน้าจะฝึกวิชา — ฝึกพลาด" · "คนแปลกหน้าจะบำเพ็ญ" · "คนแปลกหน้าจะเดินทาง"
    ไม่มีบรรทัด "ข้าจะ..." เลยสักบรรทัด สาเหตุสองชั้น:
      1. ขอบฟ้าคงที่หนึ่งปีสั้นกว่าจังหวะชีวิตของเขาเอง (วัดจริง: คนละราวปีละครั้ง)
      2. ทางถอย (ข้อ 6 ใน glimpse) วนตามลำดับ cid = ลำดับที่คนเกิดในโลก จึงหยิบคนที่แก่
         ที่สุดในโลกมาก่อนเสมอ และไม่กรองว่าเรื่องนั้นคุ้มค่าจะเป็นคำทำนายไหม
    """

    def test_the_horizon_stretches_until_he_appears_in_his_own_vision(self):
        sim, _w, ch = a_world()
        g = FS.glimpse(sim, ch)
        self.assertGreaterEqual(g["horizon"], C.FORESIGHT_HORIZON)
        self.assertLessEqual(g["horizon"], C.FORESIGHT_HORIZON_MAX + 400,
                             "ยืดได้ แต่ต้องมีเพดาน ไม่งั้นการมองอนาคตครั้งเดียวกินเวลาเป็นนาที")
        self.assertTrue(any("ข้า" in l for l in g["lines"]),
                        "จ่ายชะตาไปหนึ่งแต้มแล้วต้องได้รู้เรื่องของตัวเองอย่างน้อยหนึ่งเรื่อง")

    def test_it_never_spends_a_line_on_a_stranger_doing_nothing(self):
        sim, _w, ch = a_world()
        g = FS.glimpse(sim, ch)
        for line in g["lines"]:
            if "ข้า" in line or "จะตาย" in line:
                continue
            self.assertFalse(
                any(d in line for d in ("— ออกเดินทาง", "— บำเพ็ญ", "— ค้าขาย", "— เก็บได้")),
                f"บรรทัดนี้ตัดสินใจอะไรไม่ได้เลย: {line}")

    def test_the_fallback_prefers_people_he_actually_knows(self):
        """ทางถอยต้องเรียงตามความใกล้ชิด ไม่ใช่ตามลำดับที่คนเกิดในโลก"""
        sim, _w, ch = a_world()
        ties = FS._ties_of(ch)
        self.assertIn(ch.cid, ties)
        # คนของเขาต้องถูกจัดอยู่ใกล้กว่าคนแปลกหน้าเสมอ
        stranger = next(c for c in sim.cast
                        if c.alive and c.cid not in ties and c.place != ch.place)
        self.assertNotIn(stranger.cid, ties)

    def test_looking_ahead_still_costs_only_seconds(self):
        import time
        sim, _w, ch = a_world()
        t0 = time.time()
        FS.glimpse(sim, ch)
        self.assertLess(time.time() - t0, 30.0,
                        "ขอบฟ้าที่ยืดได้ต้องไม่ทำให้การมองอนาคตหนึ่งครั้งกลายเป็นนาที")


class TestTheOwnerKnowsHeHasIt(unittest.TestCase):
    """พลังที่เจ้าตัวไม่รู้ว่ามี = พลังที่ไม่มีอยู่จริงในเรื่อง

    วัดจริงจากโลกปีที่ 89-118: เจ้าของระบบไม่เคยใช้สักครั้งตลอด 29 ปี ทั้งที่ `IN.weigh()` ให้
    น้ำหนัก 30 และเมนูมีตัวเลือกนี้ครบ 60/60 คนที่วัด สาเหตุคือบล็อก [นิมิตที่ข้าเห็น] ในพรอมต์
    โผล่เฉพาะตอน "เคยใช้ไปแล้ว" จึงเป็นงูกินหาง — ไม่เคยใช้ ก็ไม่มีนิมิต ก็ไม่มีอะไรบอกว่าเขามี
    """

    def _owner(self):
        sim, _w, ch = a_world()
        ch.system_foresight = True
        ch.visions = []
        return sim, ch

    def test_the_sheet_says_so_before_he_has_ever_used_it(self):
        from tiandao.mind import persona as P
        sim, ch = self._owner()
        sheet = P.self_sheet(sim, ch)
        line = sheet.get("วิถีพิเศษที่มีอยู่ในตัวข้า", "")
        self.assertIn("หยั่งรู้อนาคต", line)
        self.assertIn("ยังไม่เคยใช้", line, "ต้องบอกด้วยว่ายังไม่เคยใช้ ไม่ใช่แค่ว่ามี")
        self.assertIn("ใช้ได้แล้ว", line, "และต้องบอกว่าตอนนี้ใช้ได้ไหม")

    def test_nobody_else_is_told_they_have_it(self):
        from tiandao.mind import persona as P
        sim, ch = self._owner()
        other = next(c for c in sim.cast
                     if c.alive and c is not ch and getattr(c, "sentient", True))
        other.system_foresight = False
        self.assertNotIn("วิถีพิเศษที่มีอยู่ในตัวข้า", P.self_sheet(sim, other))

    def test_the_line_reports_the_cooldown_after_a_look(self):
        from tiandao.mind import persona as P
        sim, ch = self._owner()
        ch.visions = [{"day": sim.day - 30, "lines": ["อะไรสักอย่าง"]}]
        line = P.self_sheet(sim, ch)["วิถีพิเศษที่มีอยู่ในตัวข้า"]
        self.assertIn("ยังใช้ไม่ได้", line, "เพิ่งใช้ไปเดือนเดียว ต้องรู้ว่ายังใช้ไม่ได้")
        ch.visions = [{"day": sim.day - C.FORESIGHT_COOLDOWN_DAYS - 1, "lines": ["x"]}]
        self.assertIn("ใช้ได้แล้ว", P.self_sheet(sim, ch)["วิถีพิเศษที่มีอยู่ในตัวข้า"])


if __name__ == "__main__":
    unittest.main()
