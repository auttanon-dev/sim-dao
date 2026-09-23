# -*- coding: utf-8 -*-
"""ความตายและการหักหลังต้องมีเหตุ — ทรยศ · ประลอง · สงครามเบิกฟ้า

    python -m unittest test_deaths -v

สามบั๊กที่ไฟล์นี้ล็อกไว้ (พบจากการไล่สาเหตุการตายทั้งจักรวาล 102 ปี):

1. `ทรยศ` — ตารางเหตุการณ์ใช้ชื่อ "ทรยศ" แต่ handler เช็ค "หักหลัง" จึงไม่เคยทำงานเลย
   (วัดจริง: "หักหลัง" 0 ครั้ง) การทรยศ 2,489 ครั้งไหลไปจบที่กิ่งประลอง = ดวลกันตาย 317 ศพ
   และข้อความอ่านไม่ได้ความ "ทาริกทรยศกับจาฟาร์ — ทาริกดับดิ้น" (คนลงมือตายเอง)
2. `ประลอง` — เล็งศัตรูเก่า 55% ตามทางเลือกทั่วไป การวัดฝีมือจึงกลายเป็นศึกแค้น ตาย 12.5%
   และผู้แพ้ได้ความแค้นติดตัวทุกครั้ง ย้อนกลับเป็นล้างแค้น 4,144 ครั้ง
3. `สงครามเบิกฟ้า` — handler เขียนไว้ครบแต่ไม่มี kind ในตาราง จึงไม่มีใครเลือกได้ ผลคือ
   แดนเซียนปิดประตูด้วยค่ายกล 100/100 ตั้งแต่วันแรก และผู้ไต่ถึงขั้นข้ามฟ้า 25 คนไม่มีทางไปต่อ
"""
import contextlib
import io
import unittest

from tiandao import config as C
from tiandao import events as E
from tiandao import intent as IN
from tiandao import rules as R
from tiandao import sim as S
from tiandao.mind import actions as A


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


BETRAY = next(e for e in E.EVENT_TABLE if e["kind"] == "ทรยศ")
DUEL = next(e for e in E.EVENT_TABLE if e["kind"] == "ประลอง")


def pair(seed=7):
    sim = quiet(S.Sim, seed=seed, tiers=3)
    w = sim.world(0)
    people = [c for c in sim.living_in(0) if c.sentient and c.age(sim.day) >= 16]
    a, b = people[0], people[1]
    for c in (a, b):
        c.rivals, c.bonds, c.debts = {}, {}, []
        c.realm, c.peak_realm = 3, 3
        c.money = {0: 200}
        c.items = []
        c.skills = []
        c.master_cid, c.disciples, c.spouse = -1, [], None
        c.org, c.clan = None, -1
        c.hidden, c.jail_until = False, 0
    return sim, w, a, b


class TestBetrayal(unittest.TestCase):
    def test_a_stranger_has_nothing_to_betray(self):
        sim, w, a, t = pair()
        out, text, d = sim.resolve(BETRAY, a, t, w, 30, StubRng())
        self.assertEqual(out, "ไม่มีใครให้ทรยศ")
        self.assertTrue(t.alive)
        self.assertEqual(t.money[0], 200)

    def test_betrayal_takes_things_not_lives(self):
        sim, w, a, t = pair()
        t.bonds[a.cid] = 3
        a.bonds[t.cid] = 3
        out, text, d = sim.resolve(BETRAY, a, t, w, 30, StubRng())
        self.assertEqual(out, "หักหลัง")
        self.assertTrue(t.alive, "การหักหลังไม่ใช่การดวล — ไม่ควรมีใครตายจากมัน")
        self.assertNotIn(a.cid, t.bonds, "ความไว้ใจต้องขาดลง")
        self.assertGreaterEqual(t.rivals.get(a.cid, 0), 3)
        self.assertLess(t.money[0], 200, "ต้องมีอะไรเปลี่ยนมือจริง")
        self.assertGreater(a.money[0], 200)
        self.assertTrue(any(x["kind"] == "ทรยศ" for x in a.debts), "ต้องกลายเป็นหนี้ค้างคาใจ")
        self.assertIn("ความไว้ใจที่ถูกใช้", d)
        self.assertIn("หักหลัง", text)
        self.assertNotIn("ทรยศกับ", text, "ข้อความเดิมอ่านเหมือนไปประลองกัน")

    def test_betraying_a_master_severs_the_bond(self):
        sim, w, master, disciple = pair()
        disciple.master_cid = master.cid
        master.disciples = [disciple.cid]
        out, text, d = sim.resolve(BETRAY, master, disciple, w, 30, StubRng())
        self.assertEqual(out, "หักหลัง")
        self.assertEqual(disciple.master_cid, -1)
        self.assertNotIn(disciple.cid, master.disciples)
        self.assertEqual(d.get("ความสัมพันธ์ที่ขาด"), "ศิษย์-อาจารย์")

    def test_a_shared_sect_or_clan_counts_as_trust(self):
        sim, w, a, t = pair()
        a.clan = t.clan = 2
        self.assertIsNotNone(R.trust_tie(sim, a, t))
        a.clan = t.clan = -1
        a.org = t.org = 0
        self.assertIsNotNone(R.trust_tie(sim, a, t))

    def test_weigh_drops_betrayal_when_nobody_trusts_you(self):
        sim, w, a, t = pair()
        self.assertNotIn("ทรยศ", IN.weigh(a, sim, E.EVENT_TABLE, True, others=[t]))
        t.bonds[a.cid] = 3
        self.assertIn("ทรยศ", IN.weigh(a, sim, E.EVENT_TABLE, True, others=[t]))

    def test_the_world_never_kills_anyone_by_betrayal(self):
        sim = quiet(S.Sim, seed=11)
        quiet(sim.run, 40000)
        evs = [e for e in sim.log if e.kind == "ทรยศ"]
        self.assertGreater(len(evs), 0)
        dead = {c.cid: c.death_day for c in sim.cast if not c.alive}
        for e in evs:
            self.assertEqual(e.outcome, "หักหลัง")
            self.assertIn("ความไว้ใจที่ถูกใช้", e.deltas or {},
                          "ทุกการหักหลังต้องบันทึกว่าใช้ความไว้ใจอะไร")
            self.assertNotEqual(dead.get(e.target), e.day, "ไม่ควรมีใครตายเพราะถูกหักหลัง")
            self.assertNotEqual(dead.get(e.actor), e.day, "และคนลงมือยิ่งไม่ควรตายเอง")


class TestDuel(unittest.TestCase):
    def test_a_friendly_bout_ends_in_a_bow_not_a_grave(self):
        sim, w, a, t = pair()
        out, text, d = sim.resolve(DUEL, a, t, w, 30, StubRng())
        self.assertIn(out, ("พ่ายแพ้", "รอดตายด้วยชะตา"))
        self.assertTrue(a.alive and t.alive)
        self.assertIn("ยอมแพ้อย่างสมศักดิ์ศรี", text)
        loser = t if a.bonds.get(t.cid, 0) else a
        self.assertGreater(a.bonds.get(t.cid, 0), 0, "ปะมือกันแล้วเกิดความนับถือ")
        self.assertGreater(t.bonds.get(a.cid, 0), 0)
        self.assertEqual(t.rivals.get(a.cid, 0), 0, "การวัดฝีมือฉันมิตรต้องไม่สร้างความแค้น")
        self.assertIn("สิ่งที่ผู้แพ้ได้", d)

    def test_a_grudge_match_stays_dangerous(self):
        sim, w, a, t = pair()
        a.rivals[t.cid] = 4
        out, text, d = sim.resolve(DUEL, a, t, w, 30, StubRng())
        self.assertNotIn("ยอมแพ้อย่างสมศักดิ์ศรี", text,
                         "มีเรื่องบาดหมางกันอยู่ ไม่ใช่การประลองฉันมิตรอีกแล้ว")
        self.assertGreater(t.rivals.get(a.cid, 0) + a.rivals.get(t.cid, 0), 4)

    def test_duels_look_for_a_worthy_peer_not_an_old_enemy(self):
        sim = quiet(S.Sim, seed=5)
        quiet(sim.run, 3000)
        picked_rival = same_realm = total = 0
        for e in sim.log:
            if e.kind != "ประลอง" or e.target is None:
                continue
            a, t = sim.cast[e.actor], sim.cast[e.target]
            total += 1
            if t.cid in a.rivals:
                picked_rival += 1
            if abs(a.realm - t.realm) <= 1:
                same_realm += 1
        self.assertGreater(total, 20)
        self.assertLess(picked_rival / total, 0.35,
                        "ประลองไม่ควรเป็นการไปตามหาศัตรูเก่า — นั่นคือเจตนา 'ล้างแค้น'")
        self.assertGreater(same_realm / total, 0.5, "ควรเล็งคู่มือที่ขั้นพลังสมกัน")

    def test_duel_lethality_drops_and_honour_appears(self):
        sim = quiet(S.Sim, seed=11)
        quiet(sim.run, 40000)
        evs = [e for e in sim.log if e.kind == "ประลอง"]
        died = [e for e in evs if e.outcome == "ตาย"]
        honour = [e for e in evs if "ยอมแพ้อย่างสมศักดิ์ศรี" in e.text]
        self.assertGreater(len(evs), 100)
        self.assertLess(len(died) / len(evs), 0.11, "การประลองตายเกิน 11% คือศึกแค้น ไม่ใช่การวัดฝีมือ")
        self.assertGreater(len(honour), 0, "ต้องมีการแพ้อย่างสมศักดิ์ศรีเกิดขึ้นจริง")


class TestHeavenWar(unittest.TestCase):
    def test_the_action_exists_for_both_the_dice_and_the_minds(self):
        kinds = {e["kind"] for e in E.EVENT_TABLE}
        self.assertIn("สงครามเบิกฟ้า", kinds, "handler มีอยู่แต่ไม่มี kind = ไม่มีใครเลือกได้เลย")
        self.assertIn("สงครามเบิกฟ้า", A.ACTION_INFO, "ผู้มีจิตใจต้องเห็นตัวเลือกนี้ในเมนูด้วย")

    def test_it_is_offered_only_when_the_gate_is_actually_shut(self):
        sim = quiet(S.Sim, seed=7, tiers=3)
        ch = next(c for c in sim.living_in(0) if c.sentient and c.age(sim.day) >= 16)
        ch.realm = ch.peak_realm = C.ASCEND_MIN_REALM
        up = sim.world(sim.world(0).up)
        up.is_closed = False
        self.assertNotIn("สงครามเบิกฟ้า", IN.weigh(ch, sim, E.EVENT_TABLE, False))
        up.is_closed = True
        self.assertIn("สงครามเบิกฟ้า", IN.weigh(ch, sim, E.EVENT_TABLE, False))
        ch.realm = ch.peak_realm = 1
        self.assertNotIn("สงครามเบิกฟ้า", IN.weigh(ch, sim, E.EVENT_TABLE, False),
                         "ขั้นไม่ถึงก็ทุบกำแพงฟ้าไม่ได้")

    def test_breaking_the_array_opens_the_sky(self):
        sim = quiet(S.Sim, seed=7, tiers=3)
        w = sim.world(0)
        up = sim.world(w.up)
        up.is_closed = True
        up.defense_array = 10.0
        ch = next(c for c in sim.living_in(0) if c.sentient and c.age(sim.day) >= 16)
        ch.realm = ch.peak_realm = 8
        ev = next(e for e in E.EVENT_TABLE if e["kind"] == "สงครามเบิกฟ้า")
        out, text, d = sim.resolve(ev, ch, None, w, 30, StubRng(0.99))
        self.assertEqual(out, "เปิดสวรรค์")
        self.assertFalse(up.is_closed)
        self.assertLessEqual(up.defense_array, 0)

    def test_heaven_rebuilds_the_array_when_it_shuts_the_gate_again(self):
        sim = quiet(S.Sim, seed=7, tiers=3)
        up = next(w for w in sim.worlds if w.tier == 1)
        up.is_closed = False
        up.defense_array = 0.0
        up.n_alive = C.HEAVEN_POP_LIMIT + 5
        up.checked_day = -10 ** 6
        quiet(sim.run, 60)
        self.assertTrue(up.is_closed)
        # ค่ายกลถูกตั้งขึ้นใหม่ (จาก 0.0) แล้วอาจถูกทุบไปบ้างแล้วในไม่กี่เหตุการณ์ถัดมา เพราะ
        # ตอนนี้มีคนเลือก "สงครามเบิกฟ้า" จริง — ที่ต้องยืนยันคือมันไม่ค้างอยู่ที่ 0 ให้ใครก็
        # ทุบเปิดได้ในหมัดเดียว
        self.assertGreater(up.defense_array, up.defense_max * 0.4,
                           "ถ้าไม่ตั้งค่ายกลใหม่ ประตูที่ปิดอีกครั้งจะถูกทุบเปิดได้ในหมัดเดียว")

    def test_over_a_long_run_the_sky_is_fought_for_not_walked_through(self):
        sim = quiet(S.Sim, seed=11)
        quiet(sim.run, 60000)
        evs = [e for e in sim.log if e.kind == "สงครามเบิกฟ้า"]
        opened = [e for e in evs if e.outcome == "เปิดสวรรค์"]
        self.assertGreater(len(evs), 0, "ต้องมีคนลองทุบกำแพงฟ้าจริง")
        self.assertLess(len(opened), len(evs), "เปิดได้ทุกครั้งที่ลอง = ค่ายกลไม่ได้ถูกตั้งใหม่")


if __name__ == "__main__":
    unittest.main()
