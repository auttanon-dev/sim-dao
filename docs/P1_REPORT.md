# P1 Report: Polity core, offices, succession, sect lifecycle, event tiers

## What was built
- **`polity.rs`:** a single `Polity` type for every kind of power (City, Sect, and Clan, Region, RealmCourt, HeavenCourt, Cult and Rebel reserved for later phases). Each has offices, a succession rule, standing (legitimacy, support, authority, stability), policy, interests, relations, factions, a treasury, a parent and city traits. Ids are stable, and a fallen polity keeps its slot.
- **Migration (P1a):** `Engine.sects` and `Engine.cities` were folded into `Engine.polities`. Sects keep their old ids. `Person.city` becomes `Person.office`. Pre-P1 saves are converted in `after_load`. The behaviour fingerprint was unchanged by this step.
- **`governance.rs`:**
  - **Eligibility:** one explicit function. A candidate must be alive, adult, in the same world and sentient, and must not be chaos, a thrall or a dissolved lord. They hold at most one office, but promotion within the same polity is allowed. Sect offices require membership, cultivation and inner-disciple realm for elders. Lawful cities exclude criminals.
  - **Succession:** Heredity, then Council, then Strength. Appointment by the overlord falls back to Council. Mandate is reserved and falls back to Council. Council voting is deterministic, weighing realm, bonds, rivalry and merit. How a ruler took the seat sets their starting legitimacy.
  - **Vacancies:** filled **immediately** at death, ascension, crossing a gate or leaving a sect. If nobody qualifies, the polity enters an interregnum: a logged "no leader" event. A sect with no successor dissolves.
  - **Offices:** sects get elders (1 + members/8, capped at 6). Cities get 2 officials, with titles that depend on the city type.
  - **Sect ranks:** sect master, elder, inner disciple, outer disciple. Treasury payouts follow rank (shares 4/3/2/1) at `sect_payout_rate` = 0.6 per year. Member dues (`sect_tithe`) are unchanged.
  - **Founding requirements:** realm, ambition, `sect_found_cost` = 150 gold moved into the new treasury, site qi ≥ 0.5, no living sect already seated there, and world capacity = Σqi / 1.5. That gives about 8 sects for a main world, 5 for a sister world and 2 for a branch world.
  - **Decline:** a sect is weak below 3 members or with stability < 0.3. After 24 weak months it **merges** into a stronger neighbour if it is headless or tiny, **becomes subordinate** if a neighbour is at least 2× stronger, or **dissolves** after 48 months.
  - **Standing:** updated monthly from food security, crime, treasury, and the head's power relative to rivals.
  - **`check_polities()`:** an invariant checker. No dead or orphaned holders, back-pointers consistent, no double offices, nothing held in a fallen polity.
- **`history.rs`:** event tiers.
  - **Historic:** always logged.
  - **Notable:** logged up to `notable_per_world_year` = 24 per world, then counted.
  - **Routine:** counted only. Routine acts of *important* people (office holders, realm ≥ 7 in band, those from upper realms) are promoted to notable.
  - Every event is counted in `ledger.counts` and in the per-world `world_counts`. Forked foresight engines log everything, so foresight scoring is unchanged.

## Intentional behaviour changes
1. **Sect founding is limited** by qi capacity, one sect per site and a founding cost. Peak sect count falls from 139–162 to 40–46.
2. **Sect succession is by elder council vote** instead of highest realm.
3. **Cities succeed by type:** capitals by heredity, frontiers, counties and sect outposts by appointment (falling back to council and then strength), black markets by strength. Before, every city went to the strongest person present.
4. **Vacancies are filled immediately**, not at the next monthly tick.
5. **Sects pay out their treasury to members**, so gold held in sects falls from about 0.8M to about 0.05M by year 300 and returns to people.
6. **Logging is filtered:** about 18–25 events per main world per year, 5–9 for smaller worlds. Before, it was 30–65, mostly routine.
7. **Population** at year 20 is 1540 against 1626 before. The 300-year trajectory keeps the same shape as P0.

## Bugs found and fixed along the way
- **Saves were not byte-stable**, because `used_names` was a `HashSet`. Fixed in P0.
- **`after_load` re-inserted a dissolved chaos lord into the per-place index**, so a reloaded world could drift from an uninterrupted one. Fixed, and covered by the new test `at_index_matches_truth`.
- **Migrated legacy cities lost their succession rule.** A shared `city_rule()` now serves both paths. Found by the exact-continuation migration test.
- **`is_criminal` re-parsed a JSON table on every call.** It is now cached.

## Tests
- 35 Rust tests, including the long ones.
- New tests:
  - succession under every rule (heredity skipping an ineligible eldest child, council election refilling the elder seat, strength, appointment by the overlord's favour)
  - interregnum
  - founding requirements
  - founding moves gold without creating it
  - weak-sect merge, with the gold ledger exact
  - subordination
  - leaving releases office
  - 40-year invariants plus the per-world sect cap
  - event tiers
  - pre-P1 save migration with exact behavioural continuation
  - per-place index consistency
- 5 Python tests pass.

## Measurements: 300 years, sequential runs on the same machine
| seed | P0 s | P1 s | pop y300 P0 → P1 | peak sects P0 → P1 | sects y300 P0 → P1 |
|---|---|---|---|---|---|
| 1 | 30.5 | 40.8 | 1413 → 1404 | 162 → 46 | 71 → 15 |
| 2 | 37.7 | 42.1 | 1187 → 1132 | 139 → 43 | 75 → 12 |
| 3 | 38.9 | 34.3 | 1502 → 1230 | 161 → 43 | 61 → 8 |
| total | 107.0 | 117.2 | | | |

P1 runs at about 91% of P0's throughput overall, above the 80% target. Run-to-run noise is about ±15%.

## Open issues to carry forward
- **Sect counts fall to 8–15 by year 300** because cultivators decline (900 → 330), a pre-existing population and cultivation issue for P7. Founding rules are not the binding cause late in the run, since capacity is well above the living count.
- **Gold accumulates in place tills and treasuries** (1.75–1.84M by year 300, up from 1.6M in P0). This is P2 work: tax, budgets and a stone economy.
- **Food ledger drift** reaches about -6e-4 by year 300, unchanged from P0. Also P2.
- **Officials are appointed from whoever is present at a city's seat.** P4 will make appointments interest-driven: patronage, bribery, factions.
- **Standing is computed but only feeds sect decline.** P2 makes it feed taxes and support, and P5 makes it feed coups and rebellions.

## Raw output

### seed 1 (P1)
```
year,alive,cultivators,sects,cities_ruled,gold_people,gold_sects,gold_places,food_delta,gold_delta,steps,events,secs
50,1305,848,27,34/34,564756,11338,135336,-1.23e-4,-6.24e-8,348084,15787,6.29
100,1017,723,46,34/34,717165,37678,347236,-1.91e-4,1.23e-7,588106,34010,12.18
150,882,579,39,34/34,823311,51264,621312,-2.18e-4,6.06e-7,761681,50866,20.99
200,900,469,36,33/34,887433,56511,945831,-2.84e-4,1.30e-6,939594,65097,28.59
250,1038,382,21,34/34,876081,51248,1356040,-4.04e-4,2.14e-6,1161519,76120,35.35
300,1404,338,15,34/34,869753,54476,1751638,-6.22e-4,3.35e-6,1481112,84963,40.77
build 0.01s · run 40.77s · 36329 steps/s · 7.36 sim-years/s
logged events per world per year:
  0 โลกมนุษย์            17.7
  1 แดนเซียน             22.6
  2 สวรรค์นอกชั้นฟ้า     25.1
```

### seed 2 (P1)
```
year,alive,cultivators,sects,cities_ruled,gold_people,gold_sects,gold_places,food_delta,gold_delta,steps,events,secs
50,1302,837,29,34/34,573896,11280,126916,-1.25e-4,-5.72e-8,334342,15505,7.21
100,979,693,43,33/34,758609,40176,305017,-1.51e-4,1.04e-7,563759,32797,16.40
150,843,576,39,33/34,849244,53015,596716,-1.67e-4,5.90e-7,729327,48510,24.09
200,860,469,32,34/34,887537,53098,954062,-2.04e-4,1.29e-6,890977,61200,31.61
250,983,399,16,34/34,839258,46649,1404145,-3.03e-4,2.24e-6,1085071,71282,36.67
300,1132,369,12,34/34,779742,60805,1844395,-5.01e-4,3.47e-6,1339457,79087,42.13
build 0.01s · run 42.13s · 31793 steps/s · 7.12 sim-years/s
logged events per world per year:
  0 โลกมนุษย์            18.9
  1 แดนเซียน             19.4
  2 สวรรค์นอกชั้นฟ้า     25.1
```

### seed 3 (P1)
```
year,alive,cultivators,sects,cities_ruled,gold_people,gold_sects,gold_places,food_delta,gold_delta,steps,events,secs
50,1235,817,30,34/34,576358,11074,125182,-1.12e-4,-5.76e-8,340485,15362,3.90
100,932,678,43,34/34,731773,36525,336692,-1.59e-4,1.22e-7,558693,32661,11.91
150,827,542,35,31/34,826927,48814,624705,-2.03e-4,6.10e-7,722016,47996,16.57
200,876,434,28,34/34,854921,55632,984816,-2.65e-4,1.35e-6,896540,60632,23.09
250,1029,355,15,34/34,807666,53693,1428085,-3.53e-4,2.37e-6,1133714,70184,29.63
300,1230,319,8,34/34,780971,59440,1842425,-5.25e-4,3.64e-6,1445097,77331,34.26
build 0.01s · run 34.26s · 42183 steps/s · 8.76 sim-years/s
logged events per world per year:
  0 โลกมนุษย์            18.0
  1 แดนเซียน             19.0
  2 สวรรค์นอกชั้นฟ้า     25.3
```
