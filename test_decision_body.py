# -*- coding: utf-8 -*-
"""ระบบตัดสินใจถามร่างกายก่อนตัดสินใจ — Phase 6 (§32) + TEST 10

    python -m unittest test_decision_body -v

พรอมต์ §32 ห้ามให้ระบบตัดสินใจดู HP อย่างเดียว: ก่อนเลือกว่าจะสู้หรือจะหนี ต้องถามว่า
**ร่างนี้วิ่งได้เร็วเท่าไร ยืนไหวไหม ออกหมัดได้ไหม** แล้วเอาคำตอบไปคิด Expected Utility
ตัวอย่างในพรอมต์คือคนที่ขาซ้ายเจ็บ วิ่งได้ 4.1 m/s หนีจากศัตรูที่วิ่ง 5.3 m/s แล้วพบว่า
P(หนีรอด) = 0.31 ต่ำกว่า P(ชนะ) = 0.46 จึงเลือกสู้ — ไฟล์นี้ยืนยันทั้งตัวเลขและพฤติกรรม

ส่วน TEST 10 ยืนยันเส้นแบ่งของ §33: บาดเจ็บจริงเท่ากันแต่รู้สึกไม่เท่ากัน ความสามารถจริง
ต้องเท่ากันเป๊ะ แต่การตัดสินใจต่างกันได้
"""
import contextlib
import io
import math
import random
import unittest

from tiandao import body as B
from tiandao.decision import (AgentState, DecisionContext, DecisionEngine, Environment,
                              PerceivedEntity, PhysicalCapability, Relation)
from tiandao.decision import config as DCFG
from tiandao.decision.needs import basic_needs, threat_pressure
from tiandao.decision.simdao import capability_of
from tiandao.decision.scoring import _logistic
from tiandao.models import Character

CFG = DCFG.load()
TRAITS = CFG.get("personality.traits")
WIN_SCALE = CFG.get("risk.win_scale", 0.35)
ESCAPE_SCALE = CFG.get("risk.escape_scale", 0.32)


def traits(**kw):
    t = {k: 0.5 for k in TRAITS}
    t.update(kw)
    return t


def person(cid=0, body_seed=7):
    ch = Character(cid=cid, name=f"ผู้ทดสอบ {cid}", world_id=0, dao="วิถีดาบ",
                   dao_tags=[], born_day=0, gender="ชาย")
    ch.body_seed = body_seed
    return ch


def capability(speed=None, **kw):
    """คำตอบจากร่างกายแบบกำหนดเอง — ใช้ตรึงตัวแปรให้เหลือตัวที่กำลังวัด"""
    cap = PhysicalCapability(known=True, speed=5.0, reaction=0.18, carry=60.0, strike=200.0,
                             endurance=40.0, word="ปกติดี")
    if speed is not None:
        cap.speed = speed
    for k, v in kw.items():
        setattr(cap, k, v)
    return cap


def scene(eng, name, cap, tr=None, self_power=100.0, enemy_power=100.0, enemy_speed=0.0,
          now=0.0, injuries=0.0):
    """เจอศัตรูหนึ่งตัวที่เรารู้พลังและเห็นความเร็วของมัน"""
    mind = eng.mind(name, name)
    mind.beliefs.observe("power:self", self_power, "self", now, CFG)
    mind.beliefs.observe("power:wolf", enemy_power, "sight", now, CFG, confidence=0.8,
                         truth=enemy_power)
    ents = [PerceivedEntity("wolf", "beast", "หมาป่า", hostile=True, speed=enemy_speed,
                            relation=Relation())]
    st = AgentState(hp=100, hp_max=100, power=self_power, stamina=80, location="valley",
                    money=50, injuries=injuries, body=cap)
    needs = basic_needs(st, {"safety": threat_pressure(ents, mind.beliefs, now, CFG, self_power)})
    return DecisionContext(name, name, now, st, needs, tr or traits(), mind,
                           Environment(danger=0.3), ents,
                           facts={"enemy_near": True, "ally_danger": False})


def decide(eng, ctx, seed=0):
    return eng.decide(ctx, random.Random(seed))


class EngineAsksTheBodyTests(unittest.TestCase):
    """§32 — ความเร็วและความสามารถเข้าไปอยู่ในสมการ ไม่ใช่แค่ HP"""

    def setUp(self):
        self.eng = DecisionEngine(cfg=CFG, section="demo", mode="stochastic")

    def test_escape_probability_matches_the_worked_example_in_the_prompt(self):
        """4.1 m/s หนีจาก 5.3 m/s = 0.31 ตามตัวอย่าง §32 เป๊ะ (เป็นการสอบเทียบสเกล)"""
        ctx = scene(self.eng, "a", capability(speed=4.1), enemy_speed=5.3)
        opt = decide(self.eng, ctx).option("run_away")
        self.assertAlmostEqual(opt.p_success, 0.31, places=2)
        self.assertAlmostEqual(opt.p_success,
                               _logistic(math.log(4.1 / 5.3) / ESCAPE_SCALE), places=9)

    def test_the_slower_runner_counts_on_escaping_less(self):
        fast = decide(self.eng, scene(self.eng, "f", capability(speed=5.9), enemy_speed=5.3))
        slow = decide(self.eng, scene(self.eng, "s", capability(speed=4.1), enemy_speed=5.3))
        self.assertGreater(fast.option("run_away").p_success,
                           slow.option("run_away").p_success)
        self.assertGreater(fast.probability_of("run_away"), slow.probability_of("run_away"))

    def test_a_hurt_leg_tilts_the_choice_from_running_to_fighting(self):
        """พฤติกรรมที่พรอมต์ §32 ขอ: เลือกสู้เพราะหนีไม่พ้น ไม่ใช่เพราะกล้าขึ้น

        สองฉากนี้ต่างกันแค่ความเร็วของตัวเอง — นิสัย พลัง ศัตรู และความต้องการเหมือนกันหมด
        """
        sound = decide(self.eng, scene(self.eng, "h", capability(speed=5.9),
                                       self_power=94.5, enemy_speed=5.3))
        hurt = decide(self.eng, scene(self.eng, "i", capability(speed=4.1, leg=0.4, fight=0.9),
                                      self_power=94.5, enemy_speed=5.3))
        # P(ชนะ) เท่ากันทั้งสองฉาก เพราะพลังไม่ได้เปลี่ยน — ที่เปลี่ยนคือ P(หนีรอด)
        self.assertAlmostEqual(sound.option("attack_enemy", "wolf").p_success,
                               hurt.option("attack_enemy", "wolf").p_success, places=9)
        self.assertAlmostEqual(hurt.option("attack_enemy", "wolf").p_success, 0.46, places=2)
        self.assertAlmostEqual(hurt.option("run_away").p_success, 0.31, places=2)
        ratio_sound = sound.probability_of("attack_enemy") / sound.probability_of("run_away")
        ratio_hurt = hurt.probability_of("attack_enemy") / hurt.probability_of("run_away")
        self.assertGreater(ratio_hurt, ratio_sound)

    def test_without_a_pursuer_speed_the_old_fixed_chance_is_used(self):
        """โลก/จังหวะที่ไม่รู้ความเร็วผู้ไล่ ต้องได้พฤติกรรมเดิมทุกประการ"""
        spec = self.eng.registry.get("run_away")
        blind = decide(self.eng, scene(self.eng, "b", capability(speed=4.1), enemy_speed=0.0))
        self.assertEqual(blind.option("run_away").p_success, spec.success)
        no_body = decide(self.eng, scene(self.eng, "n", PhysicalCapability(), enemy_speed=5.3))
        self.assertEqual(no_body.option("run_away").p_success, spec.success)

    def test_a_body_that_cannot_stand_cannot_choose_to_run(self):
        ctx = scene(self.eng, "c", capability(speed=4.1, can_stand=False), enemy_speed=5.3)
        ids = {s.id for s in self.eng.registry.candidates(ctx)}
        self.assertNotIn("run_away", ids)
        self.assertIn("run_away", {s.id for s in self.eng.registry.candidates(
            scene(self.eng, "c2", capability(speed=4.1), enemy_speed=5.3))})

    def test_a_body_that_cannot_fight_cannot_choose_to_attack(self):
        """§32 ตรงตัว: HP เต็มแต่ร่างกายสู้ไม่ได้ ก็ไม่ใช่ตัวเลือก"""
        ctx = scene(self.eng, "d", capability(can_fight=False))
        self.assertEqual(ctx.state.hp, 100)
        self.assertNotIn("attack_enemy", {s.id for s in self.eng.registry.candidates(ctx)})
        # โลกที่ไม่มีแบบจำลองร่างกาย ใช้เกณฑ์เดิม (HP > 0 + stamina พอ)
        self.assertIn("attack_enemy", {s.id for s in self.eng.registry.candidates(
            scene(self.eng, "d2", PhysicalCapability()))})

    def test_the_energy_cost_follows_the_bodys_own_effort_ceiling(self):
        """แรงที่เรียกใช้ได้จริงมาจากร่างกาย (ความล้า+เลือด+เชื้อเพลิง+อุณหภูมิ คูณกัน)"""
        strong = decide(self.eng, scene(self.eng, "e1", capability(effort=1.0)))
        weak = decide(self.eng, scene(self.eng, "e2", capability(effort=0.25)))
        self.assertGreater(weak.option("attack_enemy", "wolf").additive["energy_cost"].raw,
                           strong.option("attack_enemy", "wolf").additive["energy_cost"].raw)

    def test_the_explanation_says_why_running_looked_hopeless(self):
        ctx = scene(self.eng, "x", capability(speed=4.1), enemy_speed=5.3)
        note = decide(self.eng, ctx).option("run_away").factors["belief_confidence"].note
        self.assertIn("4.10", note)
        self.assertIn("5.30", note)


class Test10PerceivedVersusActualTests(unittest.TestCase):
    """TEST 10 — บาดเจ็บจริงเท่ากัน รู้สึกไม่เท่ากัน: กายเท่ากัน ใจต่างกัน"""

    def setUp(self):
        self.eng = DecisionEngine(cfg=CFG, section="demo", mode="stochastic")
        self.a = person(40, body_seed=13)
        self.b = person(40, body_seed=13)
        for ch in (self.a, self.b):
            ch.injuries.setdefault("left_leg", {})["bone"] = 0.45
            ch.blood_frac = 0.80

    def caps_from(self, ch, bias, day=50.0):
        """ใช้ทางเดียวกับที่ adapter ของโลกจริงใช้ — ไม่แปลงเองในเทสต์"""
        return capability_of(ch, B.felt(ch, day, bias))

    def test_physical_capability_is_identical(self):
        self.assertEqual(B.capabilities(self.a), B.capabilities(self.b))

    def test_decision_behaviour_may_differ(self):
        optimist = self.caps_from(self.a, +1.0)
        pessimist = self.caps_from(self.b, -1.0)
        self.assertGreater(optimist.speed, pessimist.speed)
        self.assertLess(optimist.severity, pessimist.severity)
        enemy = 6.0
        p_opt = decide(self.eng, scene(self.eng, "o", optimist, enemy_speed=enemy,
                                       injuries=optimist.severity))
        p_pes = decide(self.eng, scene(self.eng, "p", pessimist, enemy_speed=enemy,
                                       injuries=pessimist.severity))
        self.assertGreater(p_opt.option("run_away").p_success,
                           p_pes.option("run_away").p_success)
        self.assertNotAlmostEqual(p_opt.probability_of("run_away"),
                                  p_pes.probability_of("run_away"), places=4)
        # ...ทั้งที่ร่างจริงของสองคนนี้เหมือนกันทุกนิวตัน
        self.assertEqual(B.estimated_max_speed(self.a), B.estimated_max_speed(self.b))


class SimDaoWiringTests(unittest.TestCase):
    """เสียบเข้าโลกจริงแล้วยังเป็นโลกเดิม — และร่างกายถูกถามจริง"""

    def world(self, steps=400, seed=9):
        from tiandao import decision as DE
        from tiandao import sim as S
        sim = S.Sim(seed=seed, tiers=3)
        eng = DE.attach(sim)
        with contextlib.redirect_stdout(io.StringIO()):
            for _ in range(steps):
                sim.step()
        return sim, eng

    def test_the_context_built_from_the_world_carries_real_body_answers(self):
        sim, eng = self.world()
        actor = next(c for c in sim.cast if c.alive)
        others = [c for c in sim.cast if c.alive and c.cid != actor.cid][:4]
        ctx, _chars = eng.build_context(actor, sim, {"ประลอง": 1.0}, others, 0)
        cap = ctx.state.body
        self.assertTrue(cap.known)
        self.assertGreater(cap.speed, 0.0)
        self.assertGreater(cap.reaction, 0.0)
        self.assertEqual(cap.word, B.perception.describe(B.felt(
            actor, sim.day, ctx.traits["bravery"] - ctx.traits["caution"])))
        for fact in ("can_fight", "can_run", "can_stand"):
            self.assertIn(fact, ctx.facts)

    def test_building_a_context_never_draws_from_the_worlds_random_stream(self):
        """ถ้าแตะ sim.rng โลกทั้งโลกจะเดินไม่เหมือนเดิม — เส้นตายของเอนจินนี้"""
        sim, eng = self.world()
        actor = next(c for c in sim.cast if c.alive)
        others = [c for c in sim.cast if c.alive and c.cid != actor.cid][:4]
        before = sim.rng.getstate()
        eng.build_context(actor, sim, {"ประลอง": 1.0}, others, 0)
        self.assertEqual(sim.rng.getstate(), before)

    def test_what_the_character_feels_is_not_what_the_world_knows(self):
        """ฟิสิกส์ใช้ของจริง ใจใช้ที่รู้สึก — ตรวจว่าไม่มีใครสลับสองอย่างนี้"""
        sim, eng = self.world()
        hurt = next(c for c in sim.cast if c.alive)
        hurt.blood_frac = 0.70
        hurt.injuries.setdefault("right_arm", {})["muscle"] = 0.5
        actual = B.capabilities(hurt)
        others = [c for c in sim.cast if c.alive and c.cid != hurt.cid][:3]
        ctx, _ = eng.build_context(hurt, sim, {"ประลอง": 1.0}, others, 0)
        self.assertNotAlmostEqual(ctx.state.body.speed, actual["speed"], places=6)
        self.assertEqual(B.capabilities(hurt), actual)      # การถามไม่เปลี่ยนร่างจริง


if __name__ == "__main__":
    unittest.main(verbosity=2)
