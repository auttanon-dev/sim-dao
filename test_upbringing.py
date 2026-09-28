# -*- coding: utf-8 -*-
"""กิจวัตรวัยเด็กรายปี (tiandao/childhood.py, แบบ §7.2 ขั้น A)

    python -m unittest test_upbringing -v
"""
import contextlib
import io
import unittest
from unittest import mock

from tiandao import childhood as CHILD
from tiandao import config as C
from tiandao import food as FOOD
from tiandao import guardians as GUARD
from tiandao import sim as S


def quiet(fn, *a, **kw):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*a, **kw)


class UpbringingTests(unittest.TestCase):
    def setUp(self):
        self.sim = quiet(S.Sim, seed=5)
        self.sim.day = 5000
        self.world = self.sim.world(0)
        self.adult = next(c for c in self.sim.living_in(0) if c.sentient and 25 <= c.age(self.sim.day) <= 50)

    def child(self, age, place=None):
        kid = quiet(self.sim.spawn, self.world, age_years=0)
        kid.born_day = self.sim.day - age * 365 - 10
        kid.place = self.adult.place if place is None else place
        kid.parents = [self.adult.cid]
        kid.guardian = self.adult.cid
        self.adult.wards.append(kid.cid)
        return kid

    def turn(self, kid):
        return quiet(CHILD.turn, self.sim, kid, self.world, 0, self.sim.rng)

    def test_an_infant_is_cared_for_and_the_bond_grows_by_the_days_spent(self):
        kid = self.child(1)
        before = kid.bonds.get(self.adult.cid, 0)
        self.turn(kid)
        p = kid.process
        self.assertEqual((p.kind, p.payload["routine"], p.payload["with"]), ("upbringing", CHILD.CARE, [self.adult.cid]))
        self.assertEqual(p.end_day, kid.born_day + 2 * 365, "ถึงวันเกิดถัดไป")
        self.sim.day += 365 // 2
        self.sim.settle_routine(kid)
        self.assertEqual(kid.bonds[self.adult.cid] - before, int(C.CHILD_BOND_PER_YEAR / 2))
        self.assertEqual(self.adult.bonds[kid.cid], int(C.CHILD_BOND_PER_YEAR / 2))

    def test_children_in_the_same_place_play_and_bond_both_ways(self):
        kid = self.child(8)
        friend = self.child(9)
        self.adult.place = kid.place + 1                    # ผู้ดูแลไม่อยู่ เรียนที่บ้านได้น้ำหนักต่ำ
        seen = set()
        for day in range(40):
            self.sim.day = 5000 + day
            kid.process = None
            routine, with_ = CHILD.choose(self.sim, kid, CHILD._rng(self.sim, kid))
            seen.add(routine)
            if routine == CHILD.PLAY:
                self.assertIn(friend.cid, with_)
        self.assertIn(CHILD.PLAY, seen)
        kid.process = None
        self.sim.start_process(kid, "upbringing", 365, {"routine": CHILD.PLAY, "with": [friend.cid],
                                                        "guardian": kid.guardian, "carry": {}},
                               C.CHILD_BOND_PER_YEAR)
        self.sim.day += 365
        self.sim.settle_routine(kid)
        self.assertEqual((kid.bonds[friend.cid], friend.bonds[kid.cid]), (3, 3))

    def test_choosing_a_routine_does_not_touch_the_world_rng(self):
        kid = self.child(6)
        state = self.sim.rng.getstate()
        CHILD.start(self.sim, kid, kid.born_day + 7 * 365, CHILD._rng(self.sim, kid))
        self.assertEqual(self.sim.rng.getstate(), state)

    def test_a_change_of_guardian_stops_the_routine_and_the_child_chooses_again_today(self):
        kid = self.child(5)
        self.turn(kid)
        self.sim.day += 100
        kid.guardian = -1
        quiet(self.sim.check_processes)
        self.assertIsNone(kid.process)
        self.assertIn((self.sim.day, kid.cid), self.sim.queue)
        self.assertEqual(self.sim.process_stats["upbringing:ผู้ปกครองเปลี่ยน"], 1)

    def test_hunger_stops_the_routine(self):
        kid = self.child(9)
        self.turn(kid)
        self.sim.day += 30
        quiet(FOOD._respond, self.sim, kid)
        self.assertFalse(kid.process is not None and kid.process.kind == "upbringing")

    def test_a_routine_still_open_at_fourteen_is_settled_on_the_first_adult_turn(self):
        kid = self.child(13)
        self.turn(kid)
        self.sim.day = kid.process.end_day + 5
        self.sim.queue = [(self.sim.day, kid.cid)]
        quiet(self.sim.step)
        self.assertFalse(kid.process is not None and kid.process.kind == "upbringing")

    def test_chores_are_only_for_children_of_seven_and_up(self):
        for age, allowed in ((6, False), (7, True)):
            kid = self.child(age)
            seen = set()
            for day in range(60):
                self.sim.day = 5000 + day
                seen.add(CHILD.choose(self.sim, kid, CHILD._rng(self.sim, kid))[0])
            self.assertEqual(CHILD.CHORES in seen, allowed, age)

    def test_chores_add_a_quarter_of_an_adult_to_the_harvest_with_no_wage_and_a_closed_ledger(self):
        from test_food import food_on, no_spoil, only, setup_person
        from tiandao import wages as WAGES
        with food_on(), no_spoil(), mock.patch.object(C, "WAGES_ENABLED", True):
            farmer, kid = self.adult, self.child(9)
            setup_person(self.sim, farmer, 3, food=100.0, profession="ชาวนา")
            setup_person(self.sim, kid, 3, food=100.0, age=9)
            self.sim.granary = {}
            self.sim.farm_till = {}
            self.sim.start_process(kid, "upbringing", 365, {"routine": CHILD.CHORES, "with": [], "guardian": kid.guardian,
                                                            "carry": {}}, C.CHILD_BOND_PER_YEAR)
            gold = WAGES.gold(self.sim, kid)
            before = dict(self.sim.food_stats)
            held = FOOD.total_held(self.sim)
            with only(self.sim, farmer, kid):
                FOOD.tick(self.sim, 30)
            season = FOOD.season_mean(self.sim.day - 30, 30)
            made = self.sim.food_stats["produced"] - before["produced"]
            self.assertAlmostEqual(made, FOOD.land_output_per_day(1 + C.CHILD_LABOUR_SHARE) * 30 * season)
            self.assertAlmostEqual(self.sim.food_stats["child_produced"] - before.get("child_produced", 0.0),
                                   made - FOOD.land_output_per_day(1) * 30 * season)
            self.assertEqual(WAGES.gold(self.sim, kid), gold, "เด็กไม่ได้ค่าแรง")
            # setup_person ใส่เสบียงนอกบัญชี จึงเทียบการเปลี่ยนแปลง: ข้าวที่มีอยู่เปลี่ยนเท่าที่บัญชีเปลี่ยนพอดี
            self.assertAlmostEqual(FOOD.total_held(self.sim) - held,
                                   FOOD.ledger_balance(self.sim.food_stats) - FOOD.ledger_balance(before), places=6)

    def test_a_hungry_child_asks_for_help_and_goes_to_someone_near_food(self):
        with mock.patch.multiple(C, FOOD_ENABLED=True, GUARDIANS_ENABLED=True):
            kid = self.child(8)
            kid.food = 0.0
            kid.hunger_days = 3.0
            carers = [c for c in self.sim.living_in(0) if c.cid != self.adult.cid and c.sentient
                      and 25 <= c.age(self.sim.day) <= 60 and c.place != self.adult.place and not c.hidden]
            for host in carers:                                 # ข้าวอยู่นอกระยะส่งของผู้ปกครองเดิม
                self.sim.granary = {(0, host.place): 10000.0}
                if not GUARD.food_near(self.sim, 0, self.adult.place):
                    break
            self.assertFalse(GUARD.food_near(self.sim, 0, self.adult.place))
            self.turn(kid)
        self.assertNotEqual(kid.guardian, self.adult.cid)
        self.assertTrue(GUARD.food_near(self.sim, 0, self.sim.cast[kid.guardian].place))
        asked = [e for e in self.sim.log if e.kind == "ขอความช่วยเหลือ" and e.actor == kid.cid]
        self.assertEqual([e.outcome for e in asked], ["ได้ผู้ดูแลใหม่"])
        self.assertEqual((self.sim.guardian_stats["asked_help"], self.sim.guardian_stats["help_found"]), (1, 1))

    def test_with_no_adult_to_take_them_a_child_goes_to_the_nearest_granary_and_eats_there(self):
        from test_food import no_spoil, only
        with mock.patch.multiple(C, FOOD_ENABLED=True, GUARDIANS_ENABLED=True, WAGES_ENABLED=True), no_spoil(), \
                mock.patch.object(GUARD, "refoster", return_value=False):      # ไม่มีผู้ใหญ่ใกล้ข้าวคนไหนรับได้
            kid = self.child(7)
            kid.is_spirit = kid.is_beast = False                # เด็กธรรมดาที่ต้องกินข้าว (spawn สุ่มเผ่าได้)
            self.assertTrue(FOOD.eats(kid))
            kid.guardian, self.adult.wards = -1, []
            kid.food, kid.hunger_days = 0.0, 5.0
            for hub in range(60):                               # ยุ้งฉางที่มีข้าวอยู่นอกระยะส่งของที่เด็กอยู่
                self.sim.granary = {(0, hub): 5000.0}
                if hub != kid.place and not GUARD.food_near(self.sim, 0, kid.place):
                    break
            self.turn(kid)
            self.assertEqual(kid.place, hub)
            self.assertEqual([e.outcome for e in self.sim.log if e.kind == "พึ่งพิงยุ้งฉาง"], ["ได้ที่พึ่ง"])
            self.assertEqual(self.sim.guardian_stats["granary_ward"], 1)
            held, before = FOOD.total_held(self.sim), dict(self.sim.food_stats)
            with only(self.sim, kid):
                FOOD.tick(self.sim, 30)
            self.assertEqual(kid.hunger_days, 0.0, "กินข้าวของยุ้งฉางที่นั่นได้")
            eaten = self.sim.food_stats["eaten"] - before["eaten"]
            self.assertAlmostEqual(eaten, 30 * C.FOOD_RATION_CHILD)
            self.assertAlmostEqual(FOOD.total_held(self.sim) - held,
                                   FOOD.ledger_balance(self.sim.food_stats) - FOOD.ledger_balance(before), places=6)

    def test_a_child_fed_by_a_guardian_near_food_does_not_ask(self):
        with mock.patch.multiple(C, FOOD_ENABLED=True, GUARDIANS_ENABLED=True):
            kid = self.child(8)
            kid.food, kid.hunger_days = 0.0, 3.0
            self.sim.granary = {(0, self.adult.place): 10000.0}
            self.turn(kid)
        self.assertEqual(kid.guardian, self.adult.cid)
        self.assertFalse(any(e.kind == "ขอความช่วยเหลือ" for e in self.sim.log))

    # ---------------------------------------------------------------- ขั้น C1: เรียนกับผู้ปกครอง
    def teacher_with_skill(self):
        from tiandao import skills as SK
        name = next(sk[0] for sk in SK.SKILLS if sk[3] == 0)
        self.adult.skills, self.adult.mastery = [name], {name: 20}
        return name

    def study(self, kid, name, days=365):
        return self.sim.start_process(kid, "upbringing", days, {"routine": CHILD.STUDY, "with": [self.adult.cid],
                                                                "guardian": kid.guardian, "carry": {}, "skill": name},
                                      C.CHILD_BOND_PER_YEAR)

    def test_study_is_offered_only_with_a_guardian_here_who_can_teach(self):
        kid = self.child(9)

        def seen():
            options = set()
            for day in range(5000, 5060):
                self.sim.day = day
                options.add(CHILD.choose(self.sim, kid, CHILD._rng(self.sim, kid))[0])
            return options

        self.adult.skills = []
        self.assertNotIn(CHILD.STUDY, seen())
        name = self.teacher_with_skill()
        self.assertIn(CHILD.STUDY, seen())
        self.adult.place = kid.place + 1
        self.assertNotIn(CHILD.STUDY, seen(), "ผู้ปกครองต้องอยู่ที่เดียวกัน")
        self.adult.place = kid.place
        kid.skills = [name]
        self.assertNotIn(CHILD.STUDY, seen(), "ไม่มีวิชาที่เด็กยังไม่มี")

    def test_the_adult_teaching_rule_is_the_shared_one(self):
        from tiandao import rules as R
        name = self.teacher_with_skill()
        kid = self.child(9)
        chance, deep = R.teach_chance(self.adult, kid, name)
        from tiandao import elements as EL, physics as PHYS
        expect = (C.TEACH_BASE_P + C.TEACH_REALM_W * kid.realm
                  + C.ELEMENT_LEARN_W * EL.affinity(EL.ensure(kid), EL.skill_element(name))
                  + C.TEACH_DEPTH_W * PHYS.practice_mastery(20, C.PRACTICE_EXPONENT))
        self.assertAlmostEqual(chance, max(0.05, min(0.95, expect)))
        self.assertEqual(R.teachable(self.adult, kid), [name])

    def test_study_insight_stops_at_the_lifetime_cap(self):
        name = self.teacher_with_skill()
        kid = self.child(9)
        kid.childhood_gain = {"insight": C.CHILD_INSIGHT_CAP - 0.1}
        insight = kid.insight
        self.study(kid, name)
        self.sim.day += 365
        with mock.patch.object(CHILD.R, "teach_chance", return_value=(0.0, 0.0)):
            self.sim.settle_routine(kid)
        self.assertAlmostEqual(kid.insight - insight, 0.1)
        self.assertAlmostEqual(kid.childhood_gain["insight"], C.CHILD_INSIGHT_CAP)

    def test_a_full_year_of_study_at_a_sure_chance_teaches_the_skill_without_touching_the_world_rng(self):
        name = self.teacher_with_skill()
        kid = self.child(9)
        self.study(kid, name)
        self.sim.day += 365
        state = self.sim.rng.getstate()
        with mock.patch.object(CHILD.R, "teach_chance", return_value=(1.0, 1.0)):
            quiet(self.sim.settle_routine, kid)
        self.assertIn(name, kid.skills)
        self.assertEqual(self.sim.rng.getstate(), state)
        self.assertTrue(any(e.kind == "เรียนวิชา" and e.actor == kid.cid for e in self.sim.log))

    def test_a_guardian_who_is_teaching_cultivates_at_ninety_percent(self):
        name = self.teacher_with_skill()
        kid = self.child(9)
        self.sim.begin_cultivation(self.adult, 100)
        self.assertEqual(self.adult.process.yield_rate, 1.0)
        self.sim.settle_routine(self.adult)
        self.study(kid, name)
        self.sim.begin_cultivation(self.adult, 100)
        self.assertAlmostEqual(self.adult.process.yield_rate, C.GUARDIAN_TEACH_COST)

    # ---------------------------------------------------------------- ขั้น C2: ฝึกพื้นฐาน
    def options(self, kid):
        seen = set()
        for day in range(5000, 5060):
            self.sim.day = day
            seen.add(CHILD.choose(self.sim, kid, CHILD._rng(self.sim, kid))[0])
        return seen

    def test_training_needs_a_guardian_here_who_cultivates_or_has_a_clan_or_sect(self):
        kid = self.child(9)
        self.adult.realm, self.adult.clan, self.adult.sect_name = 0, -1, None
        self.assertNotIn(CHILD.TRAIN, self.options(kid))
        for setup in ({"realm": 1}, {"clan": 0}, {"sect_name": "สำนักทดสอบ"}):
            self.adult.realm, self.adult.clan, self.adult.sect_name = 0, -1, None
            for k, v in setup.items():
                setattr(self.adult, k, v)
            self.assertIn(CHILD.TRAIN, self.options(kid), setup)
        self.adult.place = kid.place + 1
        self.assertNotIn(CHILD.TRAIN, self.options(kid), "ผู้ปกครองต้องอยู่ที่เดียวกัน")
        self.assertNotIn(CHILD.TRAIN, self.options(self.child(6)), "อายุ 7 ขึ้นไป")

    def test_training_loads_the_body_pays_refinement_up_to_the_cap_and_tallies_the_guardian_path(self):
        from tiandao import paths as PATHS
        kid = self.child(9)
        self.adult.realm = 2
        kid.muscle_stimulus = 0.0
        with mock.patch.object(CHILD, "choose", return_value=(CHILD.TRAIN, [self.adult.cid])):
            self.turn(kid)
        self.assertEqual(kid.muscle_stimulus, 0.0, "ไม่มีแรงกระตุ้นก้อนเดียวตอนเริ่มอีกแล้ว")
        path = PATHS.path_of(self.adult)
        self.assertEqual(kid.process.payload["path"], path)
        kid.childhood_gain["refine"] = C.CHILD_REFINE_CAP - 0.01
        refine = kid.refine
        self.sim.day += 200
        self.sim.settle_routine(kid)
        self.assertAlmostEqual(kid.refine - refine, 0.01)
        self.assertEqual(kid.childhood_gain["path:" + path], 200)
        self.assertEqual(kid.training_days_pending, 200, "วันที่ฝึกจริงรอร่างกายเดินครั้งถัดไป")
        muscle = getattr(kid, "muscle_adaptation", 0.0)
        from tiandao import body as BODY
        BODY.tick(kid, 200)
        self.assertGreater(kid.muscle_adaptation - muscle, 0.2)

    def test_a_guardian_who_is_training_a_ward_also_pays_the_time_cost(self):
        kid = self.child(9)
        self.adult.realm = 2
        self.sim.start_process(kid, "upbringing", 365, {"routine": CHILD.TRAIN, "with": [self.adult.cid],
                                                        "guardian": kid.guardian, "carry": {}, "path": "กายบำเพ็ญ"},
                               C.CHILD_BOND_PER_YEAR)
        self.sim.begin_cultivation(self.adult, 100)
        self.assertAlmostEqual(self.adult.process.yield_rate, C.GUARDIAN_TEACH_COST)

    def test_a_running_world_uses_the_routines(self):
        sim = quiet(S.Sim, seed=11)
        quiet(sim.run, 20000)
        routines = [e.deltas.get("กิจวัตร") for e in sim.log if e.kind == "เติบโต"]
        self.assertTrue({CHILD.CARE, CHILD.PLAY, CHILD.HOME, CHILD.CHORES} <= set(routines), set(routines))
        self.assertGreater(sim.food_stats.get("child_produced", 0.0), 0.0)
        self.assertAlmostEqual(FOOD.total_held(sim), FOOD.ledger_balance(sim.food_stats),
                               delta=1e-6 * max(1.0, sim.food_stats["produced"]))


if __name__ == "__main__":
    unittest.main()
