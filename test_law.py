# -*- coding: utf-8 -*-
"""กฎหมายยุทธภพ: จับกุม = คุมขัง ไม่ใช่ประหาร · มือสังหารต้องมีเหตุ

    python -m unittest test_law -v

ที่มา (วัดจริงจากรัน 102 ปี ก่อนแก้ 7,375 ศพ):
  "จับกุมอาชญากร"  478 ศพ (6%) — ไม่เคยตรวจว่าเป้าหมายทำผิดอะไร มือปราบจับชาวนาไปประหารได้
  "ลอบสังหาร"      560 ศพ (7%) — ไม่เคยตรวจว่าผู้ลงมือมีเหตุอะไร และเงินค่าจ้างเกิดจากอากาศ
รวม 13% ของความตายทั้งจักรวาลเป็นความตายที่เล่าเป็นเรื่องไม่ได้ (รอบล่าสุดกินตัวเอกไปสองคน)
"""
import contextlib
import heapq
import io
import unittest

from tiandao import config as C
from tiandao import events as E
from tiandao import intent as IN
from tiandao import rules as R
from tiandao import economy as EC
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
        return seq[0]


def world_with_two(seed=7):
    sim = quiet(S.Sim, seed=seed, tiers=3)
    w = sim.world(0)
    people = [c for c in sim.living_in(0) if c.sentient and c.age(sim.day) >= 16]
    cop, crook = people[0], people[1]
    cop.profession = "มือปราบ"
    cop.realm, cop.peak_realm = 4, 4
    crook.realm, crook.peak_realm = 1, 1
    crook.kills, crook.moral = 0, 0
    crook.money = {0: 200}
    for c in (cop, crook):
        c.rivals, c.bonds, c.debts = {}, {}, []
        c.hidden, c.jail_until = False, 0
    return sim, w, cop, crook


ARREST = next(e for e in E.EVENT_TABLE if e["kind"] == "จับกุมอาชญากร")
KILL_EV = next(e for e in E.EVENT_TABLE if e["kind"] == "ลอบสังหาร")


class TestArrest(unittest.TestCase):
    def test_an_innocent_is_never_arrested(self):
        sim, w, cop, victim = world_with_two()
        victim.profession = "ชาวนา"       # ไม่มีประวัติ ไม่ใช่อาชีพผิดกฎ
        out, text, d = sim.resolve(ARREST, cop, victim, w, 30, StubRng())
        self.assertEqual(out, "ไม่พบอาชญากร")
        self.assertTrue(victim.alive, "คนไม่มีความผิดต้องไม่ตายเพราะการจับกุม")
        self.assertFalse(victim.hidden)

    def test_a_petty_criminal_goes_to_jail_not_to_the_grave(self):
        sim, w, cop, crook = world_with_two()
        crook.profession = "โจรป่า"        # ผิดกฎในตัว แต่ยังไม่ได้ฆ่าใคร
        out, text, d = sim.resolve(ARREST, cop, crook, w, 30, StubRng())
        self.assertEqual(out, "คุมขัง")
        self.assertTrue(crook.alive, "โจรที่ยังไม่ฆ่าใครต้องถูกขัง ไม่ใช่ถูกฆ่า")
        self.assertTrue(crook.hidden)
        self.assertGreater(crook.jail_until, sim.day)
        self.assertGreaterEqual(crook.rivals.get(cop.cid, 0), C.JAIL_GRUDGE,
                                "ติดคุกแล้วต้องจองเวรผู้จับ — เป็นเชื้อของเรื่องเล่าตอนพ้นโทษ")
        self.assertIn("โทษ", d)

    def test_the_bounty_comes_from_the_seized_loot(self):
        sim, w, cop, crook = world_with_two()
        crook.profession = "โจรป่า"
        crook.money = {0: 200}
        cop.money = {0: 0}
        sim.resolve(ARREST, cop, crook, w, 30, StubRng())
        self.assertEqual(crook.money[0], 100, "ของกลางต้องถูกยึดจากตัวอาชญากรจริง")
        self.assertEqual(cop.money[0], 100, "ค่าหัวต้องมาจากของกลาง ไม่ใช่เกิดจากอากาศ")

    def test_a_mass_murderer_is_executed(self):
        sim, w, cop, killer = world_with_two()
        killer.kills = C.EXECUTE_KILLS
        out, text, d = sim.resolve(ARREST, cop, killer, w, 30, StubRng())
        self.assertEqual(out, "ประหาร")
        self.assertFalse(killer.alive, "ฆ่าคนมาหลายศพ โทษประหารยังเป็นความตายที่มีเหตุให้เล่า")
        self.assertIn("ความผิด", d)

    def test_losing_the_fight_creates_a_real_grudge_on_both_sides(self):
        sim, w, cop, crook = world_with_two()
        crook.profession = "โจรป่า"
        crook.realm, crook.peak_realm = 7, 7      # โจรแรงกว่ามือปราบ
        out, text, d = sim.resolve(ARREST, cop, crook, w, 30, StubRng())
        self.assertEqual(out, "ล้มเหลว")
        self.assertTrue(crook.alive)
        self.assertGreater(crook.rivals.get(cop.cid, 0), 0)
        self.assertGreater(cop.rivals.get(crook.cid, 0), 0)


class TestPrisonersAreNotSoldiers(unittest.TestCase):
    """คนที่ถูกขังอยู่ไม่ได้อยู่ในแนวรบ

    ไม่ได้ออกแบบไว้ล่วงหน้า — เจอตอนเทสต์การพ้นโทษพังแล้วไล่ดูว่าใครฆ่านักโทษ
    คำตอบคือ "สงครามสำนัก" ซึ่งนับสมาชิกทุกคนที่ยังมีชีวิตเป็นกำลังพล รวมถึงคนที่
    นอนอยู่ในคุกและคนที่ปิดด่านอยู่ในแดนลับของตัวเอง แล้วให้พวกเขาตายในสนามรบ
    ที่ไม่เคยไปถึง
    """

    def test_a_jailed_disciple_does_not_die_in_his_sects_war(self):
        sim, w, cop, crook = world_with_two(7)
        crook.profession = "โจรป่า"
        sim.resolve(ARREST, cop, crook, w, 30, StubRng())
        if not crook.hidden:
            self.skipTest("ฉากนี้จับไม่ติด")
        deaths = []
        real_kill = sim.kill

        def watch(ch, cause, **kw):
            if ch.cid == crook.cid:
                deaths.append(cause)
            return real_kill(ch, cause, **kw)

        sim.kill = watch
        for _ in range(40):
            if not crook.hidden or not crook.alive:
                break
            quiet(sim.run, 2000)
        self.assertNotIn("สงครามสำนัก", deaths,
                         "คนที่อยู่ในคุกต้องไม่ถูกนับเป็นกำลังพลของสำนัก")


class TestJailTime(unittest.TestCase):
    def _jail(self, seed=7, stocked=True):
        sim, w, cop, crook = world_with_two(seed)
        crook.profession = "โจรป่า"
        if stocked:
            # ให้เสบียงติดคุกไปด้วย เพราะตั้งแต่มีเศรษฐกิจปราณ คนที่ถูกขังไว้จะดูดปราณ
            # ฟ้าดินไม่ได้ ขั้นจึงถดถอย อายุขัยที่ขั้นนั้นให้มาก็หดตาม และเขาตายคอดคุก
            # ก่อนครบกำหนดโทษ — ซึ่งเป็นผลลัพธ์ที่ถูกต้องของโลก แต่ไม่ใช่สิ่งที่เทสต์
            # ชุดนี้ตั้งใจวัด (ดู TestJailStarvesACultivator ข้างล่างที่วัดเรื่องนั้นโดยตรง)
            EC.add_stones(crook, 2, 50)
        sim.resolve(ARREST, cop, crook, w, 30, StubRng())
        return sim, cop, crook

    def test_a_prisoner_does_not_act_while_inside(self):
        sim, cop, crook = self._jail()
        start = sim.seq
        quiet(sim.run, 400)
        acted = [e for e in sim.log[start:] if e.actor == crook.cid
                 and e.kind not in ("พ้นโทษ", "แหกคุก")]
        self.assertEqual(acted, [], "คนติดคุกต้องไม่เดินทาง ค้าขาย หรือบำเพ็ญอยู่ในคุก")

    def test_the_prisoner_walks_out_when_the_sentence_ends(self):
        sim, cop, crook = self._jail()
        for _ in range(60):
            if not crook.hidden or not crook.alive:
                break
            quiet(sim.run, 2000)
        self.assertTrue(crook.alive or not crook.hidden)
        if crook.alive:
            self.assertFalse(crook.hidden, "พ้นกำหนดโทษแล้วต้องได้กลับเข้าโลก")
            self.assertEqual(crook.jail_until, 0)
            kinds = [e.kind for e in sim.log if e.actor == crook.cid]
            self.assertIn("พ้นโทษ", kinds, "การพ้นโทษต้องเป็นเหตุการณ์ที่บันทึกไว้เล่าได้")

    def test_a_prisoner_arrested_while_in_hiding_still_walks_out_on_time(self):
        # ซ่อนตัวนัดเทิร์นถัดไปไว้ไกลหลายปี ถ้าการจับกุมไม่เลื่อนใบนั้น เขาจะค้างในคุกเลยวันพ้นโทษจนถึงเทิร์นนั้น
        sim, w, cop, crook = world_with_two(7)
        crook.profession = "โจรป่า"
        crook.hidden = True
        far = sim.day + 12000
        sim.queue = [(day, cid) for day, cid in sim.queue if cid != crook.cid] + [(far, crook.cid)]
        heapq.heapify(sim.queue)
        sim.resolve(ARREST, cop, crook, w, 30, StubRng())
        tickets = [day for day, cid in sim.queue if cid == crook.cid]
        self.assertEqual(tickets, [crook.jail_until], "เทิร์นเดียว ไม่เกินวันพ้นโทษ")

    def test_a_far_stronger_prisoner_can_break_out(self):
        sim, cop, crook = self._jail()
        crook.realm = cop.realm + C.JAIL_ESCAPE_REALM_GAP
        crook.peak_realm = crook.realm
        # การบังคับ rng.random() = 0.0 ข้างล่างทำให้ **ทุก** การทอยเป็นจริง รวมถึงการทอยตาย
        # ใน age_and_decay ที่เกิดก่อนการทอยแหกคุกในตาเดียวกัน เขาจึงตายก่อนได้แหกคุก
        # ให้ชะตากับกำลังกายเต็มไว้ เพื่อให้เทสนี้วัด "กลไกแหกคุก" จริงๆ ไม่ใช่วัดว่าใครตายก่อน
        crook.fate, crook.decay = 99, 0.0
        crook.hp = crook.max_hp
        # บังคับให้การทอยแหกคุกผ่านทุกครั้ง แต่ไม่แตะ RNG ของโลก
        sim.rng.random = lambda: 0.0
        # เดินโลกจนกว่าเขาจะได้ตาของตัวเอง ไม่ใช่จำนวน tick ตายตัว — ในโลกที่มีคนหลายพัน
        # ลำดับคิวขึ้นกับสายสุ่มทั้งเส้น การผูกกับเลข 3000 จึงพังทุกครั้งที่มีการดึง rng
        # เพิ่มที่ไหนสักแห่งในเอนจิน (ครั้งล่าสุด: การสุ่มธาตุประจำตัวตอนเกิด)
        for _ in range(40):
            quiet(sim.run, 3000)
            if any(e.actor == crook.cid and e.kind == "แหกคุก" for e in sim.log):
                break
            if not crook.alive:
                break
        kinds = [e.kind for e in sim.log if e.actor == crook.cid]
        self.assertIn("แหกคุก", kinds)
        self.assertEqual(crook.jail_until, 0, "แหกคุกออกมาแล้วต้องไม่ถือว่าติดคุกอยู่อีก")
        # หลังจากนั้นเขาอาจเลือกปิดด่านบำเพ็ญ (hidden=True อีกครั้ง) ได้เองตามปกติ — ที่ต้อง
        # ยืนยันคือพ้นจากการคุมขัง ไม่ใช่ว่าเขาจะไม่หายไปจากโลกด้วยเหตุอื่นอีกเลย
        self.assertEqual(getattr(crook, "seclude_until", 0) > 0 or not crook.hidden, True)


class TestAssassin(unittest.TestCase):
    def test_no_motive_no_murder(self):
        sim, w, killer, stranger = world_with_two()
        killer.profession = "นักฆ่า"
        out, text, d = sim.resolve(KILL_EV, killer, stranger, w, 30, StubRng())
        self.assertEqual(out, "ไม่มีเหตุให้ลงมือ")
        self.assertTrue(stranger.alive, "มือสังหารต้องไม่ฆ่าคนแปลกหน้าที่ยืนอยู่ข้างๆ ฟรีๆ")

    def test_a_personal_grudge_is_motive_enough(self):
        sim, w, killer, foe = world_with_two()
        killer.profession = "นักฆ่า"
        killer.rivals[foe.cid] = 3
        out, text, d = sim.resolve(KILL_EV, killer, foe, w, 30, StubRng())
        self.assertIn(out, ("สังหาร", "ล้มเหลว"))
        self.assertEqual(d.get("เหตุที่ลงมือ"), "แค้นส่วนตัว")

    def test_a_contract_moves_money_from_the_client(self):
        sim, w, killer, target = world_with_two()
        killer.profession = "นักฆ่า"
        client = next(c for c in sim.living_in(0)
                      if c.cid not in (killer.cid, target.cid) and c.sentient)
        client.money = {0: 5000}
        client.rivals = {target.cid: 5}
        killer.bonds[client.cid] = 1
        killer.money = {0: 0}
        before = client.money[0]
        out, text, d = sim.resolve(KILL_EV, killer, target, w, 30, StubRng())
        self.assertIn("รับจ้างจาก", d.get("เหตุที่ลงมือ", ""))
        self.assertLess(client.money[0], before, "ค่าจ้างต้องออกจากกระเป๋าผู้ว่าจ้าง")
        self.assertEqual(killer.money[0], before - client.money[0])
        self.assertGreater(client.bonds.get(killer.cid, 0), 0, "ผู้ว่าจ้างกับมือสังหารรู้ความลับกัน")
        if out == "สังหาร":
            self.assertNotIn(target.cid, client.rivals, "เป้าหมายตายแล้ว แค้นของผู้ว่าจ้างก็จบ")

    def test_a_failed_attempt_makes_the_target_an_enemy(self):
        sim, w, killer, foe = world_with_two()
        killer.profession = "นักฆ่า"
        killer.rivals[foe.cid] = 1
        killer.realm, killer.peak_realm = 1, 1
        foe.realm, foe.peak_realm = 8, 8
        out, text, d = sim.resolve(KILL_EV, killer, foe, w, 30, StubRng())
        self.assertEqual(out, "ล้มเหลว")
        self.assertGreater(foe.rivals.get(killer.cid, 0), 0, "รู้แล้วว่าใครจะเอาชีวิต ต้องจองเวรได้")


class TestIntentGating(unittest.TestCase):
    def test_no_criminal_nearby_means_no_arrest_attempt(self):
        sim, w, cop, plain = world_with_two()
        plain.profession = "ชาวนา"
        others = [plain]
        weights = IN.weigh(cop, sim, E.EVENT_TABLE, True, others=others)
        self.assertNotIn("จับกุมอาชญากร", weights,
                         "ไม่มีใครผิดกฎแถวนี้ ก็ไม่ควรเสียตาของโลกไปกับการตามจับ")
        plain.profession = "โจรป่า"
        weights2 = IN.weigh(cop, sim, E.EVENT_TABLE, True, others=others)
        self.assertIn("จับกุมอาชญากร", weights2)

    def test_no_motive_nearby_means_no_assassination_attempt(self):
        sim, w, killer, plain = world_with_two()
        killer.profession = "นักฆ่า"
        killer.bonds, killer.rivals, killer.org = {}, {}, None
        others = [plain]
        self.assertNotIn("ลอบสังหาร", IN.weigh(killer, sim, E.EVENT_TABLE, True, others=others))
        killer.rivals[plain.cid] = 2
        self.assertIn("ลอบสังหาร", IN.weigh(killer, sim, E.EVENT_TABLE, True, others=others))


class TestRobbingSomeoneWhoHasNothing(unittest.TestCase):
    """เจตนายังเป็นของตัวละคร แต่เป้าต้องตรงกับเจตนา

    วัดจริงจากบันทึกผู้มีจิตใจสองรอบติด: ตงฟางเฟินเลือก "ชิงสมบัติ" แล้วจบด้วย "ไม่มีของ"
    6/6 ครั้ง (ปีที่ 104-118) และ 5/5 ครั้ง (ปีที่ 118-129) — รอบหลังนี้พรอมต์ติดป้าย
    "ไม่มีอะไรมีค่าติดตัว" ให้เห็นทุกคนแล้วด้วย แต่โมเดล 8B ยังเล็งคนเดิม
    ด่านกรองใน IN.weigh() ถามแค่ "แถวนี้มีใครมีของไหม" ส่วนชื่อเป้าเป็นของตัวละคร ช่องว่าง
    ระหว่างสองอย่างนี้คือเทิร์นที่หายไปเปล่าๆ ปีละหลายครั้งตลอดชีวิตที่ลงมือได้ไม่กี่สิบครั้ง
    """

    def _world(self):
        sim = quiet(S.Sim, seed=5)
        quiet(sim.run, 6000)
        return sim

    def _strip(self, sim, ch):
        for i in list(ch.items):
            if i in sim.items and sim.items[i].kind != "ยาวิเศษ":
                ch.items.remove(i)

    def test_the_engine_redirects_to_someone_who_actually_has_something(self):
        sim = self._world()
        here = None
        for c in sim.living():
            peers = [o for o in sim.living()
                     if o is not c and o.place == c.place
                     and any(i in sim.items and sim.items[i].kind != "ยาวิเศษ" for i in o.items)]
            if peers:
                here, rich = c, peers[0]
                break
        self.assertIsNotNone(here, "ต้องหาฉากที่มีคนถือของอยู่แถวนั้นให้เจอก่อน")
        poor = next((o for o in sim.living()
                     if o is not here and o is not rich and o.place == here.place), None)
        if poor is None:
            self.skipTest("ฉากนี้มีคนไม่พอ")
        self._strip(sim, poor)
        others = [o for o in sim.living() if o is not here and o.place == here.place]
        self.assertEqual(sim.loot_count(poor), 0)
        aimed = sim.aim_theft(poor, others)
        self.assertGreater(sim.loot_count(aimed), 0,
                           "ตั้งใจจะชิง แล้วแถวนั้นมีคนถือของอยู่ ก็ไม่ควรจบด้วยมือเปล่า")

    def test_it_never_touches_a_target_that_already_has_something(self):
        """คนที่ตัวละครเลือกเองและมีของอยู่แล้ว ต้องไม่ถูกเปลี่ยน — เจตนาเป็นของเขา"""
        sim = self._world()
        rich = next((c for c in sim.living() if sim.loot_count(c) > 0), None)
        if rich is None:
            self.skipTest("โลกนี้ไม่มีใครถือของเลย")
        others = [o for o in sim.living() if o is not rich][:8]
        self.assertIs(sim.aim_theft(rich, others), rich)

    def test_it_is_deterministic(self):
        """เลือกแบบคงที่ ไม่ดึง rng — ไม่งั้นโลกจะไม่คงที่ (ดู test_determinism)"""
        sim = self._world()
        pool = [c for c in sim.living()[:200]]
        poor = next((c for c in pool if sim.loot_count(c) == 0), None)
        if poor is None:
            self.skipTest("ทุกคนถือของหมด")
        before = sim.rng.getstate()
        first = sim.aim_theft(poor, pool)
        second = sim.aim_theft(poor, pool)
        self.assertIs(first, second)
        self.assertEqual(before, sim.rng.getstate(), "aim_theft ต้องไม่ดึง rng")

    def test_it_still_fails_honestly_when_nobody_has_anything(self):
        """ไม่ใช่การยัดเป้าให้สำเร็จเสมอ — ถ้าทั้งฉากไม่มีใครมีอะไร ก็ต้องล้มเหลวตามจริง"""
        sim = self._world()
        a = sim.living()[0]
        others = [o for o in sim.living() if o is not a and o.place == a.place]
        if not others:
            self.skipTest("ฉากนี้ไม่มีใครอยู่ด้วย")
        for o in others:
            self._strip(sim, o)
        t = others[0]
        self.assertIs(sim.aim_theft(t, others), t, "ไม่มีใครมีอะไร ก็ต้องไม่ยัดเป้าให้")
        row = next(e for e in E.EVENT_TABLE if e["kind"] == "ชิงสมบัติ")
        out, _text, _d = sim.resolve(row, a, t, sim.world(a.world_id), 30, StubRng(0.0))
        self.assertEqual(out, "ไม่มีของ")


class TestWholeWorld(unittest.TestCase):
    def test_the_law_stops_being_a_death_machine(self):
        sim = quiet(S.Sim, seed=11)
        quiet(sim.run, 40000)
        arrested_dead = [c for c in sim.cast
                         if not c.alive and "ถูกจับกุมโดย" in (getattr(c, "death_cause", "") or "")]
        self.assertEqual(arrested_dead, [], "การจับกุมต้องไม่ใช่การประหารอีกต่อไป")
        executed = [c for c in sim.cast
                    if not c.alive and "ประหารตามกฎหมาย" in (getattr(c, "death_cause", "") or "")]
        for c in executed:
            self.assertGreaterEqual(R.crime_weight(c), C.EXECUTE_KILLS,
                                    f"{c.name} ถูกประหารโดยความผิดไม่ถึงเกณฑ์")
        jailed = [e for e in sim.log if e.outcome == "คุมขัง"]
        freed = [e for e in sim.log if e.kind == "พ้นโทษ"]
        self.assertGreater(len(jailed), 0, "โลกควรมีการจับกุมเกิดขึ้นจริง")
        self.assertGreater(len(freed), 0, "และควรมีคนพ้นโทษกลับมาด้วย")
        self.assertLess(len(executed), len(jailed), "คนถูกขังต้องมากกว่าคนถูกประหาร")

    def test_every_assassination_had_a_reason(self):
        sim = quiet(S.Sim, seed=11)
        quiet(sim.run, 40000)
        hits = [e for e in sim.log if e.kind == "ลอบสังหาร" and e.outcome == "สังหาร"]
        self.assertGreater(len(hits), 0)
        for e in hits:
            self.assertIn("เหตุที่ลงมือ", e.deltas or {},
                          "การสังหารทุกครั้งต้องบันทึกเหตุไว้ ไม่งั้นเขียนเป็นนิยายไม่ได้")


if __name__ == "__main__":
    unittest.main()
