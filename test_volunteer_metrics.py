import unittest
from unittest import mock

from tiandao import config as C, food as F, models as M, sim as S
from test_food import quiet, setup_person, places_by_hops
from tools.food_storage_eval.volunteer_metrics import VolunteerMetrics, aggregate


class VolunteerMetricTests(unittest.TestCase):
    def setUp(self):
        self.sim = quiet(S.Sim, seed=11)
        a, near, _ = places_by_hops(self.sim)
        self.near = near
        self.ch = setup_person(self.sim, self.sim.cast[0], a)
        self.ch.fieldwork = True
        self.ch.jail_until = 0
        self.sim.alive_cids = {self.ch.cid}
        self.tracker = VolunteerMetrics(F._working)
        self.tracker.observe(self.sim)

    def tick(self, day):
        self.sim.day = day
        self.tracker.credit_production(self.sim, 30)

    def test_death_closes_at_death_day_even_with_flag_true(self):
        self.tick(30)
        self.ch.alive = False
        self.ch.death_day = 37
        self.sim.alive_cids.clear()
        self.sim.day = 60
        result = self.tracker.summary(self.sim)
        self.assertEqual(result['alive_flagged'], 0)
        self.assertEqual(result['completed_by_reason']['death']['flag_tenure_days'], [37])
        self.assertEqual(result['productive_worker_days'], 30)

    def test_prune_is_not_policy_release(self):
        self.ch.alive = False
        self.ch.death_day = 12
        self.sim.alive_cids.clear()
        self.sim.cast[self.ch.cid] = M.Departed(self.ch)
        self.sim.day = 36500
        result = self.tracker.summary(self.sim)
        self.assertEqual(result['completed_by_reason']['death']['flag_tenure_days'], [12])
        self.assertEqual(result['completed_by_reason']['policy_release']['count'], 0)

    def check_pause(self, attr, value, restored):
        self.tick(30)
        setattr(self.ch, attr, value)
        self.tick(60)
        paused = self.tracker.summary(self.sim)
        self.assertEqual((paused['alive_flagged'], paused['alive_productive']), (1, 0))
        self.assertEqual(paused['open_flag_tenure_days'], [60])
        setattr(self.ch, attr, restored)
        self.tick(90)
        result = self.tracker.summary(self.sim)
        self.assertEqual(result['productive_worker_days'], 60)
        self.assertEqual(result['productive_interval_days'], [30, 30])
        self.assertEqual(result['completed_by_reason']['policy_release']['count'], 0)

    def test_travel_pauses_production_not_flag_spell(self): self.check_pause('travel_dest', self.near, -1)
    def test_hidden_pauses_production_not_flag_spell(self): self.check_pause('hidden', True, False)
    def test_prison_pauses_production_not_flag_spell(self): self.check_pause('jail_until', 61, 0)

    def test_policy_release_and_reentry_split_productive_intervals(self):
        self.tick(30)
        self.ch.fieldwork = False
        self.tracker.labour_transition(self.sim, {self.ch.cid: True})
        self.ch.fieldwork = True
        self.tracker.labour_transition(self.sim, {self.ch.cid: False})
        self.tick(60)
        result = self.tracker.summary(self.sim)
        self.assertEqual(result['completed_by_reason']['policy_release']['flag_tenure_days'], [30])
        self.assertEqual(result['productive_interval_days'], [30, 30])

    def test_other_flag_reset_is_labelled_other(self):
        self.sim.day = 10
        self.ch.fieldwork = False
        result = self.tracker.summary(self.sim)
        self.assertEqual(result['completed_by_reason']['other']['flag_tenure_days'], [10])

    def test_new_recruit_is_eligible_but_has_not_produced_yet(self):
        result = self.tracker.summary(self.sim)
        self.assertEqual(result['alive_productive'], 1)
        self.assertEqual(result['alive_flagged_produced_last_interval'], 0)
        self.assertEqual(result['productive_worker_days'], 0)
        self.tick(30)
        result = self.tracker.summary(self.sim)
        self.assertEqual(result['alive_flagged_produced_last_interval'], 1)

    def test_median_and_cross_seed_aggregation_have_distinct_weights(self):
        runs = [dict(alive_flagged=2, alive_productive=1, open_flag_tenure_days=[1, 9], open_flag_tenure_median=5),
                dict(alive_flagged=1, alive_productive=1, open_flag_tenure_days=[100], open_flag_tenure_median=100),
                dict(alive_flagged=0, alive_productive=0, open_flag_tenure_days=[], open_flag_tenure_median=None)]
        result = aggregate(runs)
        self.assertEqual(result['mean_seed_flag_tenure_medians'], 52.5)
        self.assertEqual(result['pooled_person_flag_tenure_median'], 9)
        self.assertEqual(result['nonempty_seed_medians'], 2)

    def test_real_death_and_prune_hooks_close_once_without_policy_release(self):
        originals = [(F, 'tick'), (F, '_adapt_labour'), (S.Sim, 'kill'), (S.Sim, 'prune_departed')]
        import contextlib
        with contextlib.ExitStack() as stack:
            for obj, name in originals: stack.enter_context(mock.patch.object(obj, name, getattr(obj, name)))
            self.tracker.install(S.Sim, F)
            self.sim.day = 17
            quiet(self.sim.kill, self.ch, 'metric fixture', natural=True)
            self.ch.children = []; self.ch.wards = []
            self.sim.day = 17 + (C.PRUNE_DEAD_YEARS + 1) * 365
            self.sim.prune_departed()
            self.assertIsInstance(self.sim.cast[self.ch.cid], M.Departed)
            result = self.tracker.summary(self.sim)
            self.assertEqual(result['completed_by_reason']['death']['flag_tenure_days'], [17])
            self.assertEqual(result['completed_by_reason']['policy_release']['count'], 0)

    def test_observations_do_not_mutate_character_or_rng(self):
        before, rng = dict(self.ch.__dict__), self.sim.rng.getstate()
        self.tracker.observe(self.sim)
        self.tracker.summary(self.sim)
        self.tracker.credit_production(self.sim, 30)
        self.assertEqual(self.ch.__dict__, before)
        self.assertEqual(self.sim.rng.getstate(), rng)


if __name__ == '__main__': unittest.main()
