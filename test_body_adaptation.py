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
