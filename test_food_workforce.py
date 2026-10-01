"""Full food-tick regression: decision workforce must be current, not past labour."""
import contextlib
import unittest
from unittest import mock

from tiandao import body as B, config as C, food as F, sim as S, wages as W
from test_food import quiet, setup_person, places_by_hops, food_on, no_spoil, only


class DecisionWorkforceTests(unittest.TestCase):
    def run_boundary(self, change):
        sim = quiet(S.Sim, seed=11)
        a, near, far = places_by_hops(sim)
        sim.day = sim.food_day = 120
        farmer = setup_person(sim, sim.cast[0], a, profession=C.FOOD_PRODUCERS[0], realm=C.FOOD_BIGU_REALM)
        helper = setup_person(sim, sim.cast[1], a)
        kids = [setup_person(sim, c, a, age=6) for c in sim.cast[2:4]]
        for ch in [farmer, helper] + kids:
            ch.jail_until = 0
            ch.process = None
            ch.fieldwork = ch is helper
        spot, neighbour = (0, a), (0, near)
        eaters = {spot: [helper] + kids}
        self.assertFalse(F.eats(farmer))  # Departure/death does not change demand: exactly 2/day.
        sim.granary = {spot: 0.0, neighbour: 0.0}
        cap = F.store_capacity(sim, eaters)
        sim.granary[spot] = cap[spot]
        sim.food_stats = F.new_stats()
        sim.food_stats['endowed'] = cap[spot]
        sim.farm_till = {}
        n = B.work_capacity(farmer) + B.work_capacity(helper)
        season = F.season_mean(sim.day - 30, 30)
        expected_past = F.land_output_per_day(n) * season * 30
        self.assertGreaterEqual(F.land_output_per_day(B.work_capacity(farmer)) * season, 2)
        boundary = {}
        original_feed, original_adapt = F._feed_place, F._adapt_labour

        def feed(*args):
            result = original_feed(*args)
            if change == 'death':
                quiet(sim.kill, farmer, 'workforce regression', natural=True)
            elif change == 'travel':
                sim.start_process(farmer, 'travel', 30, {'dest': far, 'origin': a})
            elif change == 'hidden': farmer.hidden = True
            elif change == 'prison': farmer.jail_until = sim.day + 30
            elif change == 'location': farmer.place = near
            elif change == 'world': farmer.world_id = 1
            elif change == 'age': farmer.born_day = sim.day - 10 * 365
            return result

        def adapt(sim_, eaters_, workers_, deficit, days, season_, cap_):
            boundary.update(need=sum(F.ration(c, sim.day) for c in eaters_[spot]),
                            stock=sim.granary[spot], cap=cap_[spot], deficit=deficit.get(spot, 0),
                            reserve=F.attributed_reserve(sim, spot, F.assigned_demand(sim, eaters_)),
                            past_workers=[c.cid for c in workers_[spot]],
                            decision_eligible=F._working(farmer, sim.day) and F._spot(farmer) == spot)
            return original_adapt(sim_, eaters_, workers_, deficit, days, season_, cap_)

        gold_before = {w.tier: W.gold_gap(sim, w.tier) for w in sim.worlds}
        with food_on(), no_spoil(), only(sim, farmer, helper, *kids), \
                mock.patch.object(F, '_feed_place', feed), mock.patch.object(F, '_adapt_labour', adapt):
            quiet(F.tick, sim, 30)
        self.assertEqual(boundary['need'], 2)
        self.assertLessEqual(boundary['deficit'], 1e-9)
        self.assertAlmostEqual(boundary['stock'], boundary['cap'])
        self.assertLess(boundary['reserve'], C.FOOD_DEST_STOCK_DAYS * boundary['need'])
        self.assertEqual(boundary['past_workers'], [farmer.cid, helper.cid])
        self.assertAlmostEqual(sim.food_stats['produced'], expected_past)
        self.assertAlmostEqual(F.ledger_balance(sim.food_stats), F.total_held(sim), places=6)
        for tier, before in gold_before.items():
            self.assertAlmostEqual(W.gold_gap(sim, tier), before, places=6)
        if change == 'stationary':
            self.assertTrue(boundary['decision_eligible'])
            self.assertFalse(helper.fieldwork)
        else:
            self.assertFalse(boundary['decision_eligible'])
            self.assertTrue(helper.fieldwork, f'{change}: necessary volunteer was released using stale farmer')
        return sim, boundary

    def test_death_after_production_retains_necessary_volunteer(self): self.run_boundary('death')
    def test_travel_after_production_retains_necessary_volunteer(self): self.run_boundary('travel')
    def test_hidden_after_production_retains_necessary_volunteer(self): self.run_boundary('hidden')
    def test_prison_after_production_retains_necessary_volunteer(self): self.run_boundary('prison')
    def test_location_after_production_retains_necessary_volunteer(self): self.run_boundary('location')
    def test_world_after_production_retains_necessary_volunteer(self): self.run_boundary('world')
    def test_ineligible_age_after_production_retains_necessary_volunteer(self): self.run_boundary('age')
    def test_stationary_control_releases_surplus(self): self.run_boundary('stationary')

    def test_equal_capacity_release_order_uses_cid_not_input_order(self):
        for reverse in (False, True):
            sim = quiet(S.Sim, seed=11)
            a, near, _ = places_by_hops(sim)
            people = [setup_person(sim, c, a, age=25) for c in sim.cast[:6]]
            for ch in people: ch.jail_until = 0; ch.fieldwork = False
            people[0].profession = C.FOOD_PRODUCERS[0]
            people[1].fieldwork = people[2].fieldwork = True
            workers = people[:3][::-1] if reverse else people[:3]
            spot = (0, a)
            sim.granary = {spot: 0., (0, near): 0.}
            cap = F.store_capacity(sim, {spot: people})
            sim.granary[spot] = cap[spot]
            rng, stock = sim.rng.getstate(), dict(sim.granary)
            F._adapt_labour(sim, {spot: people}, {spot: workers}, {}, 30, 1., cap)
            self.assertFalse(people[1].fieldwork)
            self.assertTrue(people[2].fieldwork)
            self.assertEqual(sim.rng.getstate(), rng)
            self.assertEqual(sim.granary, stock)

    def test_recruitment_does_not_assign_idle_person_who_moved(self):
        sim = quiet(S.Sim, seed=11)
        a, near, _ = places_by_hops(sim)
        moved, staying = [setup_person(sim, c, a) for c in sim.cast[:2]]
        for ch in (moved, staying): ch.fieldwork = False; ch.jail_until = 0
        moved.place = near
        F._adapt_labour(sim, {(0, a): [moved, staying]}, {}, {(0, a): 30.}, 30, 1., {})
        self.assertFalse(moved.fieldwork)
        self.assertTrue(staying.fieldwork)

    def test_moved_volunteer_keeps_flag_without_being_counted_at_origin(self):
        sim = quiet(S.Sim, seed=11)
        a, near, _ = places_by_hops(sim)
        moved = setup_person(sim, sim.cast[0], near)
        moved.fieldwork = True
        spot = (0, a)
        sim.granary = {spot: 1000.}
        F._adapt_labour(sim, {spot: [moved]}, {spot: [moved]}, {}, 30, 1., {spot: 1000.})
        self.assertTrue(moved.fieldwork, 'ineligible origin snapshot must not clear the global flag')


if __name__ == '__main__': unittest.main()
