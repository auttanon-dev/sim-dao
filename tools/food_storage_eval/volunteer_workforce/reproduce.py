"""Durable full-tick regressions and the deferred child-labour reproducer.

python tools/food_storage_eval/volunteer_workforce/reproduce.py [--source SOURCE]
The source directory must contain tiandao/. Full-tick tests use isolated fixture
contexts; the deferred child reproducer keeps the production policy constants.
"""
import argparse
import contextlib
import io
import json
import pathlib
import sys
import unittest
from types import SimpleNamespace

REPO = pathlib.Path(__file__).resolve().parents[3]
ap = argparse.ArgumentParser()
ap.add_argument('--source', type=pathlib.Path, default=REPO)
ap.add_argument('--child-only', action='store_true')
args = ap.parse_args()
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(args.source.resolve()))
from tiandao import sim as S, food as F, body as B, childhood as CH, config as C
from test_food import quiet, setup_person, places_by_hops

sim = quiet(S.Sim, seed=11)
a, near, _ = places_by_hops(sim)
regular = setup_person(sim, sim.cast[0], a, profession=C.FOOD_PRODUCERS[0])
helper = setup_person(sim, sim.cast[1], a)
kids = [setup_person(sim, ch, a, age=10) for ch in sim.cast[2:10]]
for ch in [regular, helper] + kids: ch.fieldwork = ch is helper; ch.jail_until = 0; ch.pregnancy = None
for ch in kids:
    ch.process = SimpleNamespace(kind='upbringing', payload={'routine': CH.CHORES}, end_day=30)
spot = (0, a)
sim.granary = {spot: 0., (0, near): 0.}
eaters = {spot: [regular, helper] + kids}
cap = F.store_capacity(sim, eaters)
sim.granary[spot] = cap[spot]
need = sum(F.ration(ch, sim.day) for ch in eaters[spot])
rule_without = F.land_output_per_day(B.work_capacity(regular))
actual_without = F.land_output_per_day(B.work_capacity(regular) + sum(CH.labour(ch, sim.day) for ch in kids))
F._adapt_labour(sim, eaters, {spot: [regular, helper]}, {}, 30, 1., cap)
assert rule_without < need <= actual_without and helper.fieldwork
print(json.dumps(dict(deferred_child_mismatch=True, need=need, rule_without=rule_without,
                      production_without=actual_without, helper_retained=helper.fieldwork)))
if not args.child_only:
    suite = unittest.defaultTestLoader.loadTestsFromNames(['test_food_workforce', 'test_volunteer_metrics'])
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(not result.wasSuccessful())
