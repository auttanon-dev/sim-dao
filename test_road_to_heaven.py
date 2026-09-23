# -*- coding: utf-8 -*-
"""ถนนขึ้นฟ้า: บันไดเส้นเดียว · กำแพงที่มองเห็นได้ · และการเกณฑ์ที่ไม่มีใครอธิบาย

    python -m unittest test_road_to_heaven -v

ที่มา (วัดจริง 307 ปี เมล็ด 11 ก่อนแก้):
  คนโลกมนุษย์ถึงขั้น 6+ (เกณฑ์ข้ามฟ้า) 43 คน · ถึงขั้น 9 (ยอดของแดน) 8 คน
  **ข้ามฟ้าจากโลกมนุษย์ 0 ครั้ง** — ทั้ง 66 ครั้งในจักรวาลมาจากแดนเซียนและแดนสาขา
  ประตูแดนเซียนเปิดแค่ 0.4% ของเวลา (ประชากร 175 ชนเพดาน 120) และ IN.weigh() ลบตัวเลือก
  "ข้ามฟ้า" ทิ้งทั้งอันตอนประตูปิด — เหตุการณ์ผล "ประตูปิด" จึงเกิด 0 ครั้ง ตัวละครไม่เคยรู้
  ว่ามีกำแพงอยู่ ยอดบันไดของโลกเป็นทางตันที่เงียบสนิท และฉากสุดยอดของโลก (บุกห้วงโกลาหล)
  เป็นของคนที่เกิดบนแดนสูงอยู่แล้วเท่านั้น
"""
import contextlib
import io
import unittest

from tiandao import config as C
from tiandao import events as E
from tiandao import intent as IN
from tiandao import sim as S
from tiandao.mind import persona as P


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


ASCEND = next(e for e in E.EVENT_TABLE if e["kind"] == "ข้ามฟ้า")


def a_peak_cultivator(seed=7, realm=None):
    sim = quiet(S.Sim, seed=seed, tiers=3)
    w = sim.world(0)
    ch = next(c for c in sim.living_in(0) if c.sentient and c.age(sim.day) >= 16)
    ch.realm = ch.peak_realm = C.REALM_CAP if realm is None else realm
    ch.insight, ch.refine, ch.decay, ch.fate = 200.0, 0.0, 0.0, 0
    return sim, w, ch


class TestOneLadder(unittest.TestCase):
    def test_the_ladder_never_restarts(self):
        from tiandao.models import Character
        def mk(tier, realm):
            c = Character(cid=0, name="x", world_id=0, dao="d", dao_tags=[], born_day=0)
            c.tier, c.realm = tier, realm
            return c
        # ขั้นสูงสุดของโลกล่าง ต่อด้วยขั้นต่ำสุดของโลกบน เป็นเส้นเดียวไม่ย้อนกลับ
        self.assertEqual(mk(0, C.REALM_CAP).rank() + 1, mk(1, 0).rank())
        self.assertEqual(mk(1, C.REALM_CAP).rank() + 1, mk(2, 0).rank())
        self.assertEqual(mk(2, C.REALM_CAP).rank(), C.REALM_TOP)
        # และชื่อขั้นก็ไม่ย้อนกลับไปเรียกปุถุชนอีก
        self.assertEqual(mk(0, C.REALM_CAP).realm_name(), C.REALMS[-1])
        self.assertTrue(mk(1, 0).realm_name().startswith("เซียน"))
        self.assertTrue(mk(2, 0).realm_name().startswith("เทพ"))

    def test_climbing_gets_harder_not_easier_after_ascending(self):
        from tiandao import rules as R
        from tiandao.models import Character
        def mk(tier, realm):
            c = Character(cid=0, name="x", world_id=0, dao="d", dao_tags=[], born_day=0)
            c.tier, c.realm = tier, realm
            return c
        sim = quiet(S.Sim, seed=7, tiers=3)
        w0, w1 = sim.world(0), sim.world(1)
        bottom_of_mortal = R.need(mk(0, 0), w0)
        top_of_mortal = R.need(mk(0, C.REALM_CAP), w0)
        first_of_heaven = R.need(mk(1, 0), w1)
        # เดิมเกณฑ์รีเซ็ตตาม realm: ขั้นแรกของแดนเซียนใช้แค่ 6 เท่ากับปุถุชนในโลกมนุษย์
        self.assertGreater(first_of_heaven, bottom_of_mortal * 4,
                           "ข้ามฟ้าแล้วเกณฑ์สะสมต้องไม่รีเซ็ตกลับไปเท่าปุถุชน")
        # ขั้นแรกของแดนบนเบากว่าขั้นสุดท้ายของแดนล่างได้เล็กน้อย (12% ต่อชั้นจาก PURITY_PER_TIER)
        # เพราะปราณข้างบนบริสุทธิ์กว่า — นั่นคือรางวัลของการข้ามฟ้า แต่ต้องไม่ใช่การเริ่มใหม่
        self.assertGreater(first_of_heaven, top_of_mortal * 0.9)

    def test_lifespan_keeps_counting_across_the_sky(self):
        from tiandao.models import Character
        def mk(tier, realm):
            c = Character(cid=0, name="x", world_id=0, dao="d", dao_tags=[], born_day=0)
            c.tier, c.realm, c.natural_lifespan = tier, realm, 100
            return c
        self.assertGreater(mk(1, 0).lifespan(), mk(0, C.REALM_CAP).lifespan(),
                           "ข้ามฟ้าแล้วอายุขัยต้องไม่ถอยหลัง")


class TestTheWall(unittest.TestCase):
    def test_a_closed_gate_is_something_he_can_go_and_see(self):
        sim, w, ch = a_peak_cultivator(realm=C.ASCEND_MIN_REALM)
        up = sim.world(w.up)
        up.is_closed = True
        weights = IN.weigh(ch, sim, E.EVENT_TABLE, False)
        self.assertIn("ข้ามฟ้า", weights,
                      "เดิมลบตัวเลือกนี้ทิ้ง ตัวละครจึงไม่เคยรู้ว่ามีกำแพง")
        out, text, d = sim.resolve(ASCEND, ch, None, w, 30, StubRng(0.0))
        self.assertEqual(out, "ประตูปิด")
        self.assertIn("กำแพง", d)
        self.assertIn("ทางที่เหลือ", d, "ต้องบอกด้วยว่ายังมีทางอะไรเหลืออยู่")
        self.assertTrue(ch.alive)

    def test_the_one_who_tops_out_the_world_cannot_be_kept_out(self):
        sim, w, ch = a_peak_cultivator()          # ขั้น 9 = ยอดของโลกมนุษย์
        up = sim.world(w.up)
        up.is_closed = True
        out, text, d = sim.resolve(ASCEND, ch, None, w, 30, StubRng(0.0))
        self.assertEqual(out, "ข้ามฟ้า")
        self.assertIn("ฟ้าเปิดทางให้", d)
        self.assertEqual(ch.world_id, up.wid)
        self.assertEqual(ch.rank(), C.REALM_CAP + 1, "ขั้นต้องไต่ต่อ ไม่ใช่ย้อนกลับไปศูนย์")

    def test_arriving_teaches_him_how_small_he_is(self):
        sim, w, ch = a_peak_cultivator()
        up = sim.world(w.up)
        up.is_closed = False
        out, text, d = sim.resolve(ASCEND, ch, None, w, 30, StubRng(0.0))
        self.assertEqual(out, "ข้ามฟ้า")
        self.assertIn("ขั้นของข้า", d)
        self.assertIn("สิ่งที่เพิ่งรู้", d, "ต้องมีบรรทัดที่บอกว่าเขาเพิ่งรู้ว่าบันไดยาวกว่าที่เคยเห็น")
        sheet = P.self_sheet(sim, ch)
        self.assertIn(str(C.REALM_TOP + 1), sheet["ขั้นพลัง"],
                      "คนที่ข้ามฟ้าแล้วต้องเห็นบันไดจริงทั้งเส้น")

    def test_a_mortal_only_sees_his_own_worlds_ceiling(self):
        sim, w, ch = a_peak_cultivator()
        sheet = P.self_sheet(sim, ch)
        self.assertIn(f"จาก {C.REALM_BAND} ของโลกนี้", sheet["ขั้นพลัง"],
                      "คนที่ยังไม่เคยขึ้นไป ไม่ควรรู้ว่าเหนือโลกตัวเองมีอีกกี่ขั้น")
        self.assertNotIn(str(C.REALM_TOP + 1), sheet["ขั้นพลัง"])


class TestCrossingSurvival(unittest.TestCase):
    def test_preparation_decides_who_lives(self):
        sim, w, ready = a_peak_cultivator()
        ready.insight, ready.refine, ready.fate = 500.0, 0.0, 3
        ready.inventory = {"ยาสมานแผล": 5}
        sim2, w2, bare = a_peak_cultivator(seed=9)
        bare.insight, bare.refine, bare.fate = 0.0, 0.0, 0
        bare.inventory = {}
        sim.world(w.up).is_closed = False
        sim2.world(w2.up).is_closed = False
        _, _, d_ready = sim.resolve(ASCEND, ready, None, w, 30, StubRng(0.0))
        _, _, d_bare = sim2.resolve(ASCEND, bare, None, w2, 30, StubRng(0.0))
        def chance(d):
            return float(d["ความพร้อม"].split("โอกาสรอด")[1].strip().rstrip("%"))
        self.assertGreater(chance(d_ready), chance(d_bare) + 10,
                           "คนที่เตรียมตัวมาต้องรอดมากกว่าคนที่เพิ่งแตะเกณฑ์")
        self.assertLessEqual(chance(d_ready), C.ASCEND_P_MAX * 100 + 0.01)


class TestConscription(unittest.TestCase):
    def _ready_world(self, seed=7):
        sim = quiet(S.Sim, seed=seed, tiers=3)
        w = sim.world(0)
        ch = next(c for c in sim.living_in(0) if c.sentient and c.age(sim.day) >= 16)
        ch.realm = ch.peak_realm = C.CONSCRIPT_REALM_BAR + 1
        return sim, w, ch

    def test_heaven_takes_the_strongest_and_explains_nothing(self):
        sim, w, ch = self._ready_world()
        taken = sim.conscript(w, sim.rng)
        self.assertIsNotNone(taken)
        self.assertEqual(taken.cid, ch.cid, "ฟ้าเอาคนที่แรงที่สุดของแดนไปก่อน")
        self.assertEqual(taken.world_id, w.up)
        self.assertEqual(taken.tier, sim.world(w.up).tier)
        ev = sim.log[-1]
        self.assertEqual(ev.kind, "เกณฑ์ขึ้นฟ้า")
        self.assertEqual(ev.outcome, "ถูกเกณฑ์")
        self.assertEqual(ev.deltas["เหตุผลที่แจ้ง"], "ไม่มี — ทูตฟ้าไม่ตอบคำถามใด")
        for word in ("โกลาหล", "เจ้าโกลาหล", "ศึก"):
            self.assertNotIn(word, ev.text,
                             "คนข้างล่างต้องไม่ถูกบอกว่าถูกเอาไปรบกับอะไร")

    def test_being_taken_does_not_reset_what_he_climbed(self):
        sim, w, ch = self._ready_world()
        before = ch.rank()
        sim.conscript(w, sim.rng)
        self.assertGreater(ch.rank(), before,
                           "ถูกพาขึ้นไปแล้วขั้นต้องไต่ต่อ (tier ขึ้น realm คงเดิม) ไม่ใช่เริ่มใหม่")

    def test_two_rumours_that_contradict_each_other(self):
        sim, w, ch = self._ready_world()
        before = len(sim.rumors)
        sim.conscript(w, sim.rng)
        fresh = [r for r in sim.rumors[before:] if r["kind"] == "เกณฑ์ขึ้นฟ้า"]
        self.assertEqual(len(fresh), 2, "ต้องเหลือข่าวลือสองกระแสที่ขัดกันเอง")
        joined = " ".join(r["text"] for r in fresh)
        self.assertIn("ศึก", joined)          # กระแสหนึ่ง: ข้างบนกำลังรบอะไรอยู่
        self.assertIn("โค่นอำนาจ", joined)     # อีกกระแส: ฟ้ากลัวคนแข็งแกร่ง
        self.assertTrue(all(not r["true"] for r in fresh),
                        "ไม่มีใครยืนยันได้ว่ากระแสไหนจริง")

    def test_those_left_behind_have_a_face_to_blame(self):
        sim, w, ch = self._ready_world()
        kid = next((sim.cast[c] for c in ch.children if 0 <= c < len(sim.cast)), None)
        if kid is None:                      # ผูกลูกให้หนึ่งคนถ้ายังไม่มี
            kid = next(c for c in sim.living_in(0) if c.cid != ch.cid and c.sentient)
            ch.children.append(kid.cid)
            kid.parents.append(ch.cid)
        sim.conscript(w, sim.rng)
        envoy = sim.log[-1].actor
        self.assertNotEqual(envoy, ch.cid, "ต้องมีทูตจากแดนบนเป็นผู้ลงมือ")
        self.assertGreaterEqual(kid.rivals.get(envoy, 0), C.CONSCRIPT_KIN_GRUDGE,
                                "คนที่เหลืออยู่ต้องมีคนให้จองเวร ไม่ใช่โกรธอากาศ")

    def test_the_realm_remembers_and_that_becomes_the_war(self):
        sim, w, ch = self._ready_world()
        up = sim.world(w.up)
        up.is_closed = True
        # ch ถึงขั้นสูงกว่า จึงถูกเอาตัวไปก่อน ส่วน ch2 ยังอยู่ — เขาคือคนที่ต้องรู้สึกอะไรกับเรื่องนี้
        ch.realm = ch.peak_realm = C.CONSCRIPT_REALM_BAR + 2
        ch2 = [c for c in sim.living_in(0) if c.sentient and c.cid != ch.cid][0]
        ch2.realm = ch2.peak_realm = C.ASCEND_MIN_REALM
        calm = IN.weigh(ch2, sim, E.EVENT_TABLE, False).get("สงครามเบิกฟ้า", 0)
        taken = sim.conscript(w, sim.rng)
        self.assertEqual(taken.cid, ch.cid)
        angry = IN.weigh(ch2, sim, E.EVENT_TABLE, False).get("สงครามเบิกฟ้า", 0)
        self.assertGreater(w.resentment, 0.0)
        self.assertGreater(angry, calm,
                           "แดนที่ถูกเกณฑ์คนไปเรื่อยๆ ต้องมีคนอยากทุบประตูนั้นมากขึ้น")
        self.assertLessEqual(w.resentment, C.RESENT_CAP)


class TestFrontline(unittest.TestCase):
    def test_the_conscripted_get_a_slot_in_the_raid(self):
        sim = quiet(S.Sim, seed=7, tiers=3)
        # ทีมที่คัดมาแล้วล้วนเป็นคนที่เกิดบนแดนสูง + มีผู้มาจากโลกล่างรออยู่ในกองสำรอง
        natives = [c for c in sim.living() if c.tier > 0][:6]
        for c in natives:
            c.birth_wid = c.world_id
        riser = next(c for c in sim.living_in(0) if c.sentient)
        riser.tier, riser.birth_wid = 1, 0
        chosen = [(100.0 - i, c) for i, c in enumerate(natives)]
        pool = chosen + [(50.0, riser)]
        out = sim._frontline(chosen, pool)
        self.assertIn(riser.cid, [c.cid for _sc, c in out],
                      "ฟ้าเกณฑ์เขาขึ้นมาเพื่อศึกนี้ — ถ้าไม่เคยถูกเลือก การถูกเกณฑ์ก็ไร้ความหมาย")
        self.assertEqual(len(out), len(chosen), "จำนวนคนในทีมต้องเท่าเดิม (สลับ ไม่ใช่เพิ่ม)")

    def test_a_team_that_already_has_one_is_left_alone(self):
        sim = quiet(S.Sim, seed=7, tiers=3)
        team = [c for c in sim.living() if c.tier > 0][:4]
        for c in team:
            c.birth_wid = c.world_id
        team[1].birth_wid = 0          # มีผู้มาจากโลกล่างอยู่แล้วหนึ่งคน
        chosen = [(100.0 - i, c) for i, c in enumerate(team)]
        self.assertEqual(sim._frontline(chosen, chosen), chosen)


class TestTheWholeRoad(unittest.TestCase):
    def test_someone_born_mortal_reaches_the_realms_above(self):
        sim = quiet(S.Sim, seed=11)
        quiet(sim.run, 120000)
        mortal_born = [c for c in sim.cast if c.birth_wid == 0]
        risen = [c for c in mortal_born if c.tier > 0]
        self.assertGreater(len(mortal_born), 1000)
        self.assertGreater(len(risen), 0,
                           "วัดจริงก่อนแก้: คนที่เกิดในโลกมนุษย์ขึ้นไปแดนบนได้ 0 คนใน 307 ปี")
        self.assertGreater(max(c.rank() for c in risen), C.REALM_CAP,
                           "และต้องมีคนไต่ต่อบนนั้นได้จริง ไม่ใช่ขึ้นไปแล้วจบ")
        kinds = [e.kind for e in sim.log]
        self.assertIn("เกณฑ์ขึ้นฟ้า", kinds)
        self.assertIn("ประตูปิด", [e.outcome for e in sim.log])


if __name__ == "__main__":
    unittest.main()
