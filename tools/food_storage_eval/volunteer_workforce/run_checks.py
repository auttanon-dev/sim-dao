"""Scoped unit/integration checks; explicitly exclude the 30-year death sweep."""
import pathlib
import sys
import unittest

REPO = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
import test_death

loader = unittest.defaultTestLoader
suite = loader.loadTestsFromNames(['test_food', 'test_food_storage', 'test_wages',
                                  'test_volunteer_metrics', 'test_food_workforce'])
for name in loader.getTestCaseNames(test_death.DeathTransactionTests):
    if name == 'test_every_death_in_a_running_world_leaves_no_dangling_reference_and_keeps_the_ledger':
        continue
    suite.addTest(test_death.DeathTransactionTests(name))
raise SystemExit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())
