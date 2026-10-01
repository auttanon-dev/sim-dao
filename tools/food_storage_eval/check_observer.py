"""Bounded, uninstrumented control for balance_run schema-2 observers.

python check_observer.py <source> <balance-run.json>
"""
import contextlib
import hashlib
import io
import json
import pathlib
import sys

sys.path.insert(0, sys.argv[1])
from tiandao import sim as S, food as F, wages as W
expected = json.loads(pathlib.Path(sys.argv[2]).read_text(encoding='utf-8'))
if expected['config']['variant'] != 'D':
    raise SystemExit('This control intentionally supports only the unchanged default policy D.')
with contextlib.redirect_stdout(io.StringIO()):
    s = S.Sim(seed=expected['seed'])
    while s.day < expected['requested_years'] * 365:
        s.step()
assert s.day == expected['end_day']
assert s.food_stats == expected['food_stats_raw']
assert hashlib.sha256(repr(sorted(s.granary.items())).encode()).hexdigest() == expected['granary_sha256']
assert hashlib.sha256(repr(s.rng.getstate()).encode()).hexdigest() == expected['rng_sha256']
assert sum(c.fieldwork for c in s.cast if c.alive) == expected['volunteer_metrics']['alive_flagged']
assert sum(c.fieldwork and F._working(c, s.day) for c in s.cast if c.alive) == expected['volunteer_metrics']['alive_productive']
assert abs(F.ledger_balance(s.food_stats) - F.total_held(s)) < 1e-4
assert max(abs(W.gold_gap(s, t)) for t in {w.tier for w in s.worlds}) < 1e-6
print('observer control passed: exact food stats, stocks, RNG and endpoint counts; food/gold ledgers close')
