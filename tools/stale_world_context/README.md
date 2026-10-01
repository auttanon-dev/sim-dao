# Stale world context fix

Accepted starting revision: `560d879dc4f6d9f23f1421a44b2fc6aaa39cc115`.
Date: 2026-10-01, Asia/Bangkok. Accepted for a separate local commit; no push.

## Confirmed cause and exact reconciliation

At baseline `32c1478`, seed 21, day 670, `_step` captures world 0 for actor
2025 before `conscript()` moves that same actor to world 1. It later passes
world 0 into `resolve()`, while the trade's `spot` and market reserves use the
actor's new world 1. Reserve debits are tier 1, but mine funding and actor payout
use the stale tier 0. Event 5996 is the first completed step with a gap; the
older wages-tick scan only detects it at day 690.

| Holding | Tier | Change |
|---|---:|---:|
| 16 market reserves in world 1 | 1 | -55.449502905240344 |
| Mine purse | 0 | -186.2867573155646 |
| Actor 2025 money | 0 | +241.73626022080492 |
| Gold ledger flows | All | 0 |

Tier 0 gains 55.44950290524033 and tier 1 loses the matching amount. Aggregate
money is conserved within floating-point error (~5.7e-14 for the transaction).
No world tier changes or `retier` calls are involved. See
[first-event holdings and flow changes](evidence/first_event.json).
The confirmed stale-world cause is resolved; this does **not** close every kind
of accounting bug. Other food/labour follow-up items remain pending.

## Reproduce from fresh pinned snapshots

Run from the project root with Python 3.12 or later. Choose a new output directory;
the preparation tool refuses to reuse an existing directory. All source comes
from the named Git revisions, with the exact historical five-line fix added to
the two fixed snapshots. It does not sample candidate code from the working tree.

```powershell
python tools/stale_world_context/prepare_snapshots.py out/stale-world-repro-new
python tools/stale_world_context/check_regression.py out/stale-world-repro-new
python tools/stale_world_context/reproduce.py out/stale-world-repro-new/baseline out/stale-world-repro-new/baseline_replay.json
python tools/stale_world_context/reproduce.py out/stale-world-repro-new/baseline_fixed out/stale-world-repro-new/baseline_fixed_replay.json
python tools/stale_world_context/reproduce.py out/stale-world-repro-new/accepted_fixed out/stale-world-repro-new/accepted_fixed_replay.json
python tools/food_storage_eval/gold_tier_scan.py out/stale-world-repro-new/baseline 21
```

The archived revisions must be available locally. Regression tests are loaded
from this project's `test_event_context.py`; production imports are redirected
to the chosen source snapshot in a separate process. The bounded replay uses
default baseline configuration, seed 21, and stops at day 710. JSON records
every completed step's tier gaps plus moves and resolve arguments at days 660-710.

## Production change and context audit

`tiandao/sim.py` adds one assignment and explanatory comments before actor
action preparation: `world = self.world(actor.world_id)`.
The original world was captured before nested world events. Conscription can
move this same actor and assign the destination place/tier during those events.
The action's peers, eligibility, event, target, city lookup and funds are all
prepared afterward. There is no selected pre-move action or cached action-place
local to reuse or cancel. Refreshing at this boundary makes all those consumers
use the current actor context, including the trade's reserve and mine currency.
World-side events remain associated with their origin world.

No changes to prices, exchange rates, conscription/movement rules, food, labour,
or household-money policy. No ledger transfer was introduced. The accepted food
patch is preserved; production diff contains only `tiandao/sim.py`.

## Deterministic regression

`test_event_context.py` runs one real `_step` and real `conscript()` with a
controlled queue/random rolls. Trade uses the real handler and both a market
reserve and mine purse. A separate target-bearing action checks actual peer and
target selection; its resolve body is stubbed to avoid unrelated combat outcomes.
Stationary controls exercise both paths.

Before the production fix: 2 failures (moved trade's world and moved peer pool),
stationary control passes. After the fix: 3 tests pass (including two stationary
subcases). Assertions verify resolve/event world and place, destination peers
and target, correct reserve/mine debits and money tier, unchanged other-tier
funds, unchanged ledger flows, per-tier closure and conserved aggregate gold.
`check_regression.py` repeats the red/green check against a pristine archived
`560d879` source (without touching the working tree) and the fixed working tree.
Permanent original outputs: [red](evidence/regression_before_fix.txt),
[green](evidence/regression_after_fix.txt).

## Seed 21 replay, bounded through day 710

`reproduce.py <source_snapshot> <output_json>` checks per-tier gaps after every
step and records moves and resolve context in days 660-710. Snapshots are pinned
by revision and contain only the five-line production addition. Separate
manifests record source file hashes. No use of `run_compare.py`.

| Source | Original migration at day 670 | Subsequent action | Largest absolute tier gap |
|---|---|---|---:|
| Baseline `32c1478` | Actor 2025, world 0 to 1 | Seq 5996 trade, actor world 1 / passed world 0 | 55.4495029054 |
| Baseline + fix | Same actor, day and migration | Seq 5996 duel with actor 296; resolve and target world 1 | 2.04e-10 |
| Accepted `560d879` + fix | Original event absent on this different food-policy trajectory | Other moves logged at days 690/691 | 1.75e-10 |

The original trade is **not repeated** by the natural baseline+fix replay:
correct destination context changes peer selection and the random trajectory,
and action selection yields a duel. The accepted+fix world also does not repeat
the original actor/day case. Absence of the gap in either trajectory alone is
not proof of the trade fix; the deterministic regression forces the migrated
actor through a real trade and checks currency, funding and accounting directly.
All baseline+fix resolve contexts in the observed interval match actor world.

## Validation and review diff

All outputs below are retained in this tracked directory's `evidence/` folder.

| Check | Result | Output |
|---|---|---|
| Regression against archived accepted source, then fixed working tree | Before: 2 expected failures; after: 3 passed, stationary subcases pass | `regression_before_fix.txt`, `regression_after_fix.txt` |
| Focused pytest: event context, road to heaven/conscription, auction/trade, wages, ledger, money keys | 79 passed, 2 subtests passed; 314.23 s | `focused_tests.txt` |
| Broader pytest: world clock, short scheduler invariant, death, population, all realms, decision engine, autonomy | 56 passed; 129.28 s | `broader_tests.txt` |
| Standalone locality script, seed 2026, 20,000 events | Passed; 82.7% of interactions at same location, cross-location checks pass | `locality.txt` |
| Standalone determinism script, seed 7 | Two 12,000-event runs match; save/load + 4,000 events matches uninterrupted 16,000-event run | `determinism.txt` |
| Snapshot and scope verification | Other 112 tracked tiandao files match accepted HEAD after line-ending normalization | `validation_manifest.json` |
| Whitespace validation | `git diff --check` passed | No whitespace errors |

Total pytest coverage: **135 passed + 2 subtests**, plus standalone locality and
determinism checks. The locality/determinism files contain script entry points,
so they were executed directly rather than counted as pytest tests.
The road-to-heaven test includes its existing 120,000-step run; ledger and death
checks include their existing 30-year checks at seeds 11, 12 and 13. These were
relevant to event continuation, conscription and money accounting. No full suite
or 18-seed comparison was run.

Determinism digests: fresh runs `903202838f931b1f`; resumed and uninterrupted
continuation `b6ccc0a6bf35244d`.

[Production/test diff](evidence/production_and_regression.diff) contains the
production addition and complete new regression. [Replay evidence](evidence/replay_summary.json)
retains gap summaries, moves and the original actor's action contexts/steps;
the large source trees and full diagnostic replay files need not be committed.

At closeout, production and regression hashes still match the tested versions.
The permanent snapshot and red/green tools were verified using fresh snapshots;
the copied replay script matches the original verified script byte-for-byte.
Only documentation/reproducer/evidence paths and follow-up status were added
after the accepted tests. No production or regression changes required another
full test run; no full suite or 18-seed comparison was repeated.
