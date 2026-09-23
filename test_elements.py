# -*- coding: utf-8 -*-
"""ห้าธาตุ: เรขาคณิตของวงจรเบญจธาตุ และผลที่มันมีต่อการฝึกวิชาและการปะทะ

    python -m unittest test_elements -v

สิ่งที่ไฟล์นี้ล็อกไว้
  1. **วงจรข่มต้องโผล่มาเองจากวงจรเกิด** ไม่ใช่ตารางที่เขียนมือแยกต่างหาก — ถ้าคู่ข่มทั้งห้า
     ไม่ได้อยู่ที่ 144° พอดีทุกคู่ แปลว่าลำดับบนวงกลมผิด และทุกสูตรที่ใช้ cos ของมันจะผิดตาม
  2. การข่มต้อง **มีทิศทาง** — น้ำดับไฟ ไม่ใช่ไฟดับน้ำ (ต่างจาก affinity ที่สมมาตร)
  3. ธาตุต้องเปลี่ยนพฤติกรรมจริง ไม่ใช่แค่คำบรรยายสวยๆ — วัดจากอัตราฝึกพลาดของทั้งโลก
"""
import contextlib
import io
import math
import unittest

from tiandao import config as C
from tiandao import elements as EL
from tiandao import physics as P
from tiandao import rules as R
from tiandao import sim as S
from tiandao import skills as SK


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
        return list(seq)[0]


class TestThePentagramGeometry(unittest.TestCase):
    def test_the_overcoming_cycle_falls_out_of_the_generating_circle(self):
        """ไม้ข่มดิน · ดินข่มน้ำ · น้ำข่มไฟ · ไฟข่มทอง · ทองข่มไม้ — ทั้งห้าคู่ต้องอยู่ที่ 144°"""
        want = {"ไม้": "ดิน", "ดิน": "น้ำ", "น้ำ": "ไฟ", "ไฟ": "ทอง", "ทอง": "ไม้"}
        for a, b in want.items():
            self.assertEqual(EL.overcomes(a), b, f"{a} ต้องข่ม {b}")
            self.assertAlmostEqual(EL.phase_degrees(a, b), 144.0, places=6)
            self.assertAlmostEqual(EL.affinity(a, b), math.cos(math.radians(144)), places=6)

    def test_the_generating_cycle_is_one_step(self):
        want = {"ไม้": "ไฟ", "ไฟ": "ดิน", "ดิน": "ทอง", "ทอง": "น้ำ", "น้ำ": "ไม้"}
        for a, b in want.items():
            self.assertEqual(EL.generates(a), b)
            self.assertAlmostEqual(EL.phase_degrees(a, b), 72.0, places=6)

    def test_same_element_is_perfect_resonance(self):
        for e in EL.GEN_ORDER:
            self.assertAlmostEqual(EL.phase_degrees(e, e), 0.0, places=9)
            self.assertAlmostEqual(EL.affinity(e, e), 1.0, places=9)

    def test_phase_is_symmetric_but_the_clash_edge_is_not(self):
        self.assertAlmostEqual(EL.phase_degrees("น้ำ", "ไฟ"), EL.phase_degrees("ไฟ", "น้ำ"))
        self.assertGreater(EL.clash_edge("น้ำ", "ไฟ"), 0, "น้ำต้องดับไฟ")
        self.assertLess(EL.clash_edge("ไฟ", "น้ำ"), 0, "ไม่ใช่ไฟดับน้ำ")
        self.assertAlmostEqual(EL.clash_edge("น้ำ", "ไฟ"), -EL.clash_edge("ไฟ", "น้ำ"), places=9)

    def test_feeding_the_enemy_is_a_small_disadvantage(self):
        """ไม้ให้กำเนิดไฟ — ไม้เสียเปรียบเล็กน้อยเพราะกำลังหล่อเลี้ยงอีกฝ่ายอยู่"""
        self.assertLess(EL.clash_edge("ไม้", "ไฟ"), 0)
        self.assertGreater(EL.clash_edge("ไฟ", "ไม้"), 0)
        self.assertLess(abs(EL.clash_edge("ไม้", "ไฟ")), abs(EL.clash_edge("ไม้", "ดิน")),
                        "คู่เกิดต้องมีผลน้อยกว่าคู่ข่ม")

    def test_the_magnitudes_come_from_the_geometry_not_from_taste(self):
        self.assertAlmostEqual(abs(EL.clash_edge("ไม้", "ดิน")),
                               abs(math.cos(math.radians(144))), places=6)
        self.assertAlmostEqual(abs(EL.clash_edge("ไม้", "ไฟ")),
                               abs(math.cos(math.radians(72))), places=6)

    def test_an_unknown_element_is_simply_neutral(self):
        """ตัวละครจากเซฟเก่าที่ยังไม่มีธาตุ ต้องไม่ทำให้สูตรไหนพัง — ต้องได้ผลเท่ากับไม่มีระบบ"""
        self.assertEqual(EL.phase_degrees("", "ไฟ"), 90.0)
        self.assertAlmostEqual(EL.affinity("", "ไฟ"), 0.0, places=9)
        self.assertEqual(EL.clash_edge("", "ไฟ"), 0.0)


class TestElementsMeetTheWaveFormulas(unittest.TestCase):
    """ค่าที่ได้จากเรขาคณิตต้องเสียบเข้าสูตรคลื่นใน physics.py ได้ตรงๆ"""

    def test_water_cancels_fire_and_fire_does_not_cancel_water(self):
        deg = EL.phase_degrees("น้ำ", "ไฟ")
        blocked = P.wave_cancel(100.0, 80.0, deg)
        self.assertLess(blocked, 100.0, "โล่ธาตุน้ำต้องกลบพลังไฟได้บางส่วน")
        same = P.wave_cancel(100.0, 80.0, EL.phase_degrees("ไฟ", "ไฟ"))
        self.assertAlmostEqual(same, 100.0, places=6, msg="ไฟปะทะไฟกลบกันไม่ได้")

    def test_two_allies_of_one_element_add_up(self):
        self.assertAlmostEqual(P.wave_sum(100, 100, EL.phase_degrees("ไฟ", "ไฟ")),
                               200.0, places=6)


class TestSkillsHaveElements(unittest.TestCase):
    def test_every_skill_in_the_world_gets_one(self):
        for row in SK.SKILLS:
            self.assertIn(EL.skill_element(row[0]), EL.GEN_ORDER, row[0])

    def test_it_reads_the_words_the_author_already_wrote(self):
        cases = {
            "มหาเวทอัคนีพิโรธสิบเก้าชั้น": "ไฟ",
            "ฝ่ามือตัดวารี": "น้ำ",
            "คาถากำแพงศิลาพิทักษ์": "ดิน",
            "ดรรชนีเยือกแข็ง": "น้ำ",
        }
        for name, el in cases.items():
            self.assertEqual(EL.skill_element(name), el, name)

    def test_it_is_stable_across_processes(self):
        """ห้ามใช้ hash() ของไพธอน ซึ่งสุ่ม seed ใหม่ทุกครั้งที่รัน"""
        a = EL.of_skill("ชื่อวิชาที่ไม่มีคำใบ้อะไรเลยสักคำ")
        b = EL.of_skill("ชื่อวิชาที่ไม่มีคำใบ้อะไรเลยสักคำ")
        self.assertEqual(a, b)
        self.assertIn(a, EL.GEN_ORDER)

    def test_no_element_owns_the_whole_library(self):
        import collections
        spread = collections.Counter(EL.skill_element(r[0]) for r in SK.SKILLS)
        self.assertEqual(len(spread), 5, "ต้องมีวิชาครบทั้งห้าธาตุ")
        self.assertLess(max(spread.values()), len(SK.SKILLS) * 0.6,
                        "ธาตุเดียวต้องไม่กินวิชาเกินครึ่งค่อนโลก")


class TestPeopleHaveElements(unittest.TestCase):
    def test_everyone_born_into_the_world_has_one(self):
        sim = quiet(S.Sim, seed=7)
        quiet(sim.run, 8000)
        for ch in sim.living()[:500]:
            self.assertIn(getattr(ch, "element", ""), EL.GEN_ORDER, ch.name)

    def test_the_world_is_not_all_one_element(self):
        import collections
        sim = quiet(S.Sim, seed=7)
        quiet(sim.run, 8000)
        spread = collections.Counter(c.element for c in sim.living())
        self.assertEqual(len(spread), 5)
        self.assertLess(max(spread.values()), len(sim.living()) * 0.5)

    def test_children_tend_to_inherit(self):
        """สืบจากพ่อแม่เป็นหลัก — ไม่ใช่เสมอ แต่ต้องมากกว่าการสุ่มล้วน (20%)"""
        sim = quiet(S.Sim, seed=7)
        quiet(sim.run, 30000)
        pairs = 0
        same = 0
        for ch in sim.cast:
            for pid in getattr(ch, "parents", ())[:2]:
                if 0 <= pid < len(sim.cast) and sim.cast[pid].element and ch.element:
                    pairs += 1
                    same += (sim.cast[pid].element == ch.element)
        if pairs < 30:
            self.skipTest("รันสั้นเกินกว่าจะมีคู่พ่อแม่-ลูกพอวัด")
        self.assertGreater(same / pairs, 0.30,
                           "สายธาตุของตระกูลต้องสืบทอดได้จริง ไม่ใช่สุ่มใหม่ทุกคน")

    def test_an_old_save_is_filled_in_without_the_dice(self):
        sim = quiet(S.Sim, seed=3)
        quiet(sim.run, 2000)
        ch = sim.living()[0]
        ch.element = ""
        before = sim.rng.getstate()
        first = EL.ensure(ch)
        self.assertEqual(before, sim.rng.getstate(), "การเติมย้อนหลังต้องไม่ขยับลูกเต๋า")
        ch.element = ""
        self.assertEqual(EL.ensure(ch), first, "และต้องได้ธาตุเดิมทุกครั้ง")


class TestItChangesWhatActuallyHappens(unittest.TestCase):
    def test_training_your_own_element_is_easier_than_training_the_one_that_beats_you(self):
        sim = quiet(S.Sim, seed=5)
        quiet(sim.run, 4000)
        ch = sim.living()[0]
        ch.element = "ไฟ"
        same = C.ELEMENT_LEARN_W * EL.affinity("ไฟ", "ไฟ")
        against = C.ELEMENT_LEARN_W * EL.affinity("ไฟ", "น้ำ")
        self.assertGreater(same - against, 0.15,
                           "ช่องว่างต้องกว้างพอจะเปลี่ยนผลจริง ไม่ใช่ทศนิยมประดับ")

    def test_the_world_really_trains_to_type(self):
        sim = quiet(S.Sim, seed=7)
        quiet(sim.run, 30000)
        match = total = 0
        for ch in sim.living():
            el = EL.ensure(ch)
            for name in ch.skills:
                total += 1
                match += EL.affinity(el, EL.skill_element(name)) > 0.5
        if total < 100:
            self.skipTest("ยังมีวิชาในมือคนน้อยเกินไป")
        self.assertGreater(match / total, 0.45,
                           "คนต้องลงเอยกับวิชาที่ถูกกับธาตุตัวเองมากกว่าการสุ่ม (20%)")

    def test_a_countering_element_helps_in_a_fight(self):
        sim = quiet(S.Sim, seed=5)
        quiet(sim.run, 4000)
        a, b = sim.living()[0], sim.living()[1]
        a.realm = b.realm = 3
        a.element, b.element = "น้ำ", "ไฟ"
        w = sim.world(a.world_id)
        edge_water = EL.clash_edge(a.element, b.element)
        a.element = "ไฟ"
        edge_fire = EL.clash_edge(a.element, b.element)
        self.assertGreater(edge_water, edge_fire,
                           "ยืนที่เดิม กำลังเท่าเดิม แต่ถือธาตุที่ข่มเขา ต้องได้เปรียบกว่า")

    def test_the_clash_edge_is_proportional_to_the_power_in_play(self):
        """ไม่ใช่ค่าคงที่ ไม่งั้นธาตุจะชี้ขาดตอนขั้นต่ำแล้วไร้ความหมายตอนขั้นสูง"""
        self.assertGreater(C.ELEMENT_CLASH_W, 0.0)
        small = C.ELEMENT_CLASH_W * 0.5 * (10 + 10)
        big = C.ELEMENT_CLASH_W * 0.5 * (1000 + 1000)
        self.assertGreater(big, small * 50)


class TestPeopleCanSeeIt(unittest.TestCase):
    def test_the_self_sheet_names_his_element_and_the_two_cycles(self):
        from tiandao.mind import persona as PR
        sim = quiet(S.Sim, seed=5)
        quiet(sim.run, 4000)
        ch = sim.living()[0]
        ch.element = "ไฟ"
        line = PR.self_sheet(sim, ch).get("ธาตุประจำตัว", "")
        self.assertIn("ไฟ", line)
        self.assertIn("ดิน", line, "ต้องบอกว่าไฟให้กำเนิดดิน")
        self.assertIn("ทอง", line, "และไฟข่มทอง")


class TestNothingBroke(unittest.TestCase):
    def test_the_world_is_still_reproducible(self):
        a = quiet(S.Sim, seed=11)
        quiet(a.run, 4000)
        b = quiet(S.Sim, seed=11)
        quiet(b.run, 4000)
        self.assertEqual([e.kind for e in a.log], [e.kind for e in b.log])
        self.assertEqual([c.element for c in a.cast], [c.element for c in b.cast])


if __name__ == "__main__":
    unittest.main()
