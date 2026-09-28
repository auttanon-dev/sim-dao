# -*- coding: utf-8 -*-
import copy
import unittest
from types import SimpleNamespace

from tiandao import body as BODY
from tiandao import places as PL
from tiandao import terrain as TERRAIN
from tiandao import travel as TRAVEL


def person(**changes):
    data = dict(cid=99001, gender="ชาย", body_seed=123, body_age=20.0,
                fatigue=0.0, blood_frac=1.0, bleed=0.0, fuel=1.0,
                core_temp=37.0, injuries={}, muscle_adaptation=0.0,
                cardio_adaptation=0.0, bone_adaptation=0.0,
                muscle_stimulus=0.0, cardio_stimulus=0.0, bone_stimulus=0.0)
    data.update(changes)
    return SimpleNamespace(**data)


class AdaptationTests(unittest.TestCase):
    def test_training_is_delayed_and_improves_force_after_rest(self):
        ch = person()
        before = BODY.strength_of(ch)
        BODY.train(ch, 1.0)
        self.assertEqual(BODY.strength_of(ch), before)
        BODY.adaptation.tick(ch, 7.0)
        self.assertGreater(ch.muscle_adaptation, 0.0)
        self.assertGreater(BODY.strength_of(ch), before)

    def test_closed_form_is_step_independent(self):
        one = person()
        BODY.train(one, 1.0)
        many = copy.deepcopy(one)
        BODY.adaptation.tick(one, 30.0)
        for _ in range(30):
            BODY.adaptation.tick(many, 1.0)
        self.assertAlmostEqual(one.muscle_stimulus, many.muscle_stimulus, places=12)
        self.assertAlmostEqual(one.muscle_adaptation, many.muscle_adaptation, places=5)

    def test_old_save_shape_gets_safe_defaults(self):
        # Condition.of must also tolerate duck-typed/old objects that have no Phase 8 fields.
        old = SimpleNamespace(cid=1, gender="ชาย", body_seed=1, fatigue=0.0,
                              blood_frac=1.0, fuel=1.0, core_temp=37.0, injuries={})
        cond = BODY.condition_of(old)
        self.assertGreater(cond.muscle_factor, 0.0)


class SustainedTrainingTests(unittest.TestCase):
    """การฝึกต่อเนื่องเป็นแหล่งกระตุ้นคงที่ — คำตอบปิดใน body/adaptation.py"""
    LOAD = 0.75 / 7.0

    @staticmethod
    def old_tick(ch, days):
        """สูตรก่อนมีการฝึกต่อเนื่อง ลอกตรงตัว — ผู้ใหญ่ที่ฝึกเป็นครั้งๆ ต้องได้ผลนี้ทุกบิต"""
        import math
        K = BODY.constants
        recovery = BODY.adaptation.age_factors(ch.body_age)["recovery"]
        ks, kd, gain = K.STIMULUS_DECAY_RATE, K.ADAPTATION_DECAY_RATE, K.ADAPTATION_GAIN_RATE * recovery
        for system in BODY.adaptation.SYSTEMS:
            s0, a0 = getattr(ch, system + "_stimulus"), getattr(ch, system + "_adaptation")
            es, ed = math.exp(-ks * days), math.exp(-kd * days)
            setattr(ch, system + "_stimulus", s0 * es)
            setattr(ch, system + "_adaptation", max(0.0, min(1.0, a0 * ed + gain * s0 * (ed - es) / (ks - kd))))
        ch.body_age += days / 365.0

    def test_discrete_training_is_bit_for_bit_the_old_formula(self):
        a, b = person(), person()
        for ch in (a, b):
            BODY.train(ch, 1.0)
        BODY.adaptation.tick(a, 40.0)
        self.old_tick(b, 40.0)
        self.assertEqual(vars(a), vars(b))
        BODY.tick(a, 30.0)                                  # ไม่มีการฝึกค้าง BODY.tick ใช้ทางเดิม
        self.assertEqual(getattr(a, "training_days_pending", 0.0), 0.0)

    def test_the_closed_form_matches_a_fine_numerical_integration(self):
        K = BODY.constants
        ch = person(body_age=10.0, muscle_stimulus=0.3, muscle_adaptation=0.1)
        BODY.adaptation.tick(ch, 300.0, 200.0, self.LOAD)
        s, a, dt = 0.3, 0.1, 0.01
        gain = K.ADAPTATION_GAIN_RATE * BODY.adaptation.age_factors(10.0)["recovery"]
        for i in range(int(300 / dt)):
            r = K.STIMULUS_PER_WORK * self.LOAD if i * dt < 200.0 else 0.0
            s, a = s + dt * (r - K.STIMULUS_DECAY_RATE * s), a + dt * (gain * s - K.ADAPTATION_DECAY_RATE * a)
        self.assertAlmostEqual(ch.muscle_stimulus, s, places=3)
        self.assertAlmostEqual(ch.muscle_adaptation, a, places=3)

    def test_splitting_a_training_span_gives_the_same_body(self):
        whole, split = person(body_age=10.0), person(body_age=10.0)
        BODY.adaptation.tick(whole, 365.0, 365.0, self.LOAD)
        BODY.adaptation.tick(split, 100.0, 100.0, self.LOAD)
        BODY.adaptation.tick(split, 265.0, 265.0, self.LOAD)
        for system in BODY.adaptation.SYSTEMS:
            self.assertAlmostEqual(getattr(whole, system + "_adaptation"), getattr(split, system + "_adaptation"))

    def test_a_year_of_weekly_sessions_builds_about_half_the_muscle_adaptation(self):
        ch = person(body_age=10.0)
        BODY.log_training(ch, 365.0, self.LOAD)
        BODY.tick(ch, 365.0)
        self.assertTrue(0.4 <= ch.muscle_adaptation <= 0.5, ch.muscle_adaptation)
        self.assertEqual(ch.training_days_pending, 0.0, "tick ใช้การฝึกที่บันทึกไว้หมดแล้ว")

    def test_only_the_days_actually_trained_count(self):
        full, part = person(body_age=10.0), person(body_age=10.0)
        BODY.log_training(full, 365.0, self.LOAD)
        BODY.log_training(part, 120.0, self.LOAD)
        BODY.tick(full, 365.0)
        BODY.tick(part, 365.0)
        self.assertLess(part.muscle_adaptation, full.muscle_adaptation)
        self.assertGreater(part.muscle_adaptation, 0.0)


class OrganAndLODTests(unittest.TestCase):
    def test_chest_organ_damage_reduces_oxygen_delivery(self):
        hurt = person(injuries={"chest": {"organ": 0.6}})
        self.assertLess(BODY.condition_of(hurt).oxygen_factor, 1.0)

    def test_brain_failure_removes_consciousness(self):
        hurt = person(injuries={"head": {"organ": 1.0}})
        self.assertFalse(BODY.conscious(hurt))
        self.assertEqual(BODY.organs.fatal_failure(hurt.injuries), "brain")

    def test_lod_never_hides_critical_state(self):
        self.assertEqual(BODY.lod.level(person()), BODY.lod.DORMANT)
        self.assertEqual(BODY.lod.level(person(bleed=0.1)), BODY.lod.CRITICAL)
        self.assertEqual(BODY.lod.level(person(injuries={"left_leg": {"bone": 0.5}})),
                         BODY.lod.RECOVERING)

    def test_pain_is_not_the_same_number_as_tissue_damage(self):
        state = {"left_leg": {"bone": 0.5}}
        self.assertNotEqual(BODY.pain.level(state), 0.5)

    def test_joint_torque_changes_with_angle(self):
        ch = person()
        body = BODY.body_of(ch)
        middle = BODY.joints.state(body, "knee", BODY.condition_of(ch))
        edge = BODY.joints.state(body, "knee", BODY.condition_of(ch), angle=0.0)
        self.assertGreater(middle.available_torque, edge.available_torque)

    def test_f_equals_ma_motion_helper(self):
        ch = person()
        body = BODY.body_of(ch)
        a = BODY.capability.forward_acceleration(body)
        x, v = BODY.capability.motion_after(body, 2.0)
        self.assertAlmostEqual(v, a * 2.0)
        self.assertAlmostEqual(x, 0.5 * a * 4.0)


class TravelAndTerrainTests(unittest.TestCase):
    def test_leg_injury_slows_actual_travel(self):
        healthy = person()
        hurt = person(cid=99002, injuries={"left_leg": {"bone": 1.0},
                                          "right_leg": {"bone": 1.0}})
        self.assertLess(TRAVEL.travel_speed(0, character=hurt),
                        TRAVEL.travel_speed(0, character=healthy))

    def test_branch_places_use_immortal_terrain_and_name(self):
        idx = next(i for i, p in enumerate(PL.PLACES) if p[1] == "br000")
        _x, _y, _z, biome, _label = TERRAIN.compute_place_3d_and_biome(idx)
        self.assertTrue(biome.startswith("floating_"))
        row = next(x for x in TERRAIN.get_all_places_data() if x["idx"] == idx)
        self.assertEqual(row["realm_name"], PL.BRANCH_NAMES[0])


if __name__ == "__main__":
    unittest.main()
