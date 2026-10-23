# Politics & Interests: Design and Revised Migration Plan

Status: proposal (not yet implemented). Branch: `rust-core-phase1`.

## 1. What exists today

**Rust engine (`simdao_core/src/engine/`)**

| Area | State |
|---|---|
| Cities | `society.rs`: `City` has a ruler, strictness and four attributes. Succession goes to the strongest person present. |
| Sects | `model.rs::Sect` has a leader, a member list, a treasury and inter-sect `grudges`. There are no ranks or dues, and nothing limits founding (158 sects after 100 years). |
| People | Personality (greed, compassion, ambition), `bonds`/`rivals`, `debts`, `moral`, `crimes`, `merit`, `leads`. |
| Ledgers | Food and gold close every month: place `till`/`treasury`, personal gold, `ruin_gold`. |
| Decisions | `act.rs::choose` builds a weighted menu, and one RNG draw picks the action. |

**Python only (not yet ported), with what each system feeds into politics**

| Python file | Content | Role in politics |
|---|---|---|
| `clans.py`, `household.py`, `guardians.py`, `childhood.py` | Kin groups, households, guardianship, heirs | Clans become polities; inheritance carries the claim to a seat |
| `sim/resolve.py` | Sect ranks, spies, sect war, war loot | Become polity offices, espionage and war |
| `economy.py`, `wages.py` | Spirit-stone grades, upkeep, sect output, transfers | Treasuries, taxes and stipends |
| `news.py`, rumours, `decision/` | Beliefs, memory, goals, scoring | "Available information" and interest-based choices |
| `worldtree.py`, `portals.py`, `branches.py` | Branch worlds, portals | Territory and access rights that polities fight over |
| `crises.py` | Betrayal, mobilisation | Become polity decisions, not random events |

## 2. Core design: one `Polity` type

To avoid writing each system twice, cities, sects, clans, realms and the heavenly court all share **one** structure. Today's `City` and `Sect` will be migrated into it. Save files stay compatible through serde defaults and a one-time conversion in `after_load`.

```rust
enum PolityKind { City, Clan, Sect, Realm, HeavenCourt, Cult /*mara*/ , Rebel }
enum Succession { Heredity, Appointment, Council /*elders vote*/, Strength /*challenge*/, Mandate /*heaven confirms*/ }

struct Polity {
    id, kind, name, world, seat: u32, territory: Vec<u32>,
    parent: Option<PolityId>,            // a vassal of a realm, a city under a sect, ...
    succession: Succession,
    offices: Vec<Office>,                // ruler at index 0, then ministers/elders/officials
    // the political state, 0..1
    legitimacy, support, authority, stability,
    // resources: real ledgers, nothing is created from nothing
    treasury_gold: f64, stones: [f64; GRADES], stores: [f64; 3],
    policy: Policy,                      // tax, toll, law strictness, conscription, gate fee, realm access
    interests: Interests,                // weights on territory/stones/qi/treasure/routes/techniques/realm access/security
    relations: BTreeMap<PolityId, Relation>, // trust, fear, debt, treaty, war
    factions: Vec<Faction>,              // internal cliques, capped per polity
    founded, fallen: Option<i64>,
}
struct Office { title, rank: u8, holder: Option<Pid>, appointed_by: Option<Pid>, salary: f64 }
struct Faction { leader: Pid, members: Vec<Pid>, aim: Aim /*seat, policy, secession*/, strength: f64 }
struct Relation { trust: f32, fear: f32, debt: f64, treaty: Treaty, since: i64 }
```

New fields on a person: `polity: Option<PolityId>`, `office: Option<(PolityId,u8)>`, `faction`, `patron: Option<Pid>` and `favors: BTreeMap<Pid,i16>`. Favours are a ledger of obligations, separate from `bonds`.

### Where the political numbers come from

All rules are deterministic. The RNG is used only through the existing seeded `Xoshiro`.

- **Legitimacy:** set by how the ruler gained the seat (inherited or confirmed > elected > appointed > seized by force), then decays toward a value based on performance.
- **Support:** food security, the tax burden relative to wealth, public order (crime), and the outcome of recent wars.
- **Authority:** the ruler's power relative to the strongest office holders, plus the treasury's ability to pay salaries.
- **Stability:** a slow average of the three above. Low stability raises the chance of plots, coups, rebellions and secession.

### How polities act (monthly, inside `world_tick`)

1. **Collect revenue.** Tax is drawn from place `till`, and tolls from gate and trade fees. Each transfer is posted to the ledger.
2. **Pay salaries and upkeep.** This covers spirit-stone upkeep for cultivators who hold office.
3. **Allocate the budget** between granary relief, garrison, sect resources and bribes, according to `interests` × the current situation.
4. **Review foreign policy.** The polity compares the expected value of alliance, tribute, trade or war with each neighbour. The inputs are interest overlap, power ratio, trust, fear and debt.
5. **Review internal politics.** It appoints, dismisses or purges officials and reacts to factions.

### How people act politically (new `Act` variants inside `choose`)

`SeekOffice`, `Bribe(t)`, `SeekPatron(t)`, `DoFavor(t)`, `CallFavor(t)`, `Plot(polity)`, `Coup`, `Rebel`, `Petition`, `Embezzle`, `Spy(polity)` and `Defect(polity)`.

Each one's weight is an **expected utility**, computed from:
- the person's personality and cultivation level
- their relationships and favours owed
- what they *know*: the rumour and knowledge model of phase P4. A person cannot plot against a ruler they don't know is weak.

This replaces flat weights, and the same approach is how the Python `decision/` engine gets ported. It is one framework, not a second system.

### Succession and change of rule

When a seat is vacated (death, a challenge, a coup, deposition by the parent polity, a heavenly mandate), it is filled by the polity's `Succession` rule. A faction can contest the result, which produces candidates, backing measured in power plus favours plus bribes, and then either a peaceful outcome or civil war. Afterwards:
- **A failed coup** means the plotters are executed or exiled, and they gain grudges.
- **A successful one** means low legitimacy for a period.

Civil wars can split a polity into a new `Rebel` polity, which can later be recognised or crushed. When stability stays below a threshold for long enough, the polity collapses and its territory and treasury pass to the strongest neighbour or to its successor factions.

### Limits that prevent runaway behaviour

- Every polity count is bounded by the number of settlements.
- A new sect needs a free seat, a minimum realm and a starting treasury, and it pays a founding cost.
- There is a cap on factions per polity and on offices per rank.
- The `Rebel` polity has a timeout.
- Only significant events are logged: changes of top office, coups, wars, treaties and collapses. Everything else goes to `ledger.count`.

### Effects on the rest of the simulation

| Political lever | Effect |
|---|---|
| Tax burden and stability | Birth rate, and the weights for leaving or arriving in migration |
| Granary relief from the budget | Reduces starvation and illness |
| Law strictness and garrison | The arrest chance already in `law_at` and how crime behaves |
| Toll and access policy | Gates, trade routes and entry to secret realms and world-tree branches |
| War | Casualties, loot (posted to the ledger), territory transfer, refugees |

## 3. Dependencies found between the remaining batches and politics

1. **The spirit-stone economy** (was Batch 5) is a prerequisite for taxes, salaries and treasuries. **Move it earlier.**
2. **Rumours and knowledge** (was Batch 5) are needed for decisions based on available information. **Move them earlier.**
3. **The decision engine** (was Batch 5) would become a second scoring system. **Merge it** into the utility layer instead of porting it separately.
4. **Sect ranks and war, clans and households** (was Batch 4) must be built **as polities from the start**. Otherwise they get rewritten.
5. **`City`** (just committed) gets migrated into `Polity` in P1. That code is small, so the migration costs little.
6. **Gates, portals and world-tree branches** become controlled territory, so they need `Polity` first.
7. **Crises and era collapse** become polity-driven hooks.
8. **Splitting `act.rs` and `world.rs`** should happen *before* politics adds about 15 new actions.
9. **Population rebalance** must come after policy effects exist. Tuning it now would be undone.

## 4. Revised phases (each one is committed and pushed, with regression tests and a probe run)

| Phase | Content | Tests added |
|---|---|---|
| **P0** | Split `act.rs` and `world.rs` into modules. Add a long-run metrics harness (`tests/long_run`) that checks population band, polity count, event rate and ledger closure. Record a performance baseline. | ledger closure over 300 years, determinism (same seed gives the same hash) |
| **P1** | `Polity` core with offices and succession rules. Migrate `City` and `Sect` into it. Add sect ranks and dues, plus the limits on sect founding. | each succession rule, vacancy filling, save migration |
| **P2** | Spirit-stone economy: grades, upkeep and minting from real qi. Polity treasury, tax, tolls, salaries and budget allocation. | tax and salary ledger closure, budget is never negative |
| **P3** | Kinship: clans as polities, households, guardians, heirs and inheritance of claims. Port childhood and emotions, with emotions feeding into utility. | heir order, orphan guardianship, clan seat inheritance |
| **P4** | Information and interests: rumour spreading, knowledge and belief, memory. A utility-based `choose`. Favours, patronage, bribery, corruption and embezzlement. | utility picks the dominant option, knowledge gating |
| **P5** | Inter-polity relations: alliances, treaties, tribute, vassalage, war (generalised from sect war), spies, mara cults. Coups, rebellions, civil war, fragmentation and collapse. | alliance forms when interests align and breaks when they don't; a coup changes the ruler; collapse transfers territory |
| **P6** | Territory and access: trade routes, gates, portals and world-tree branches as held assets. Realm-level polities and the heavenly court. Crises and era collapse. | access control, toll ledger |
| **P7** | Body detail, dashboard and README, population rebalance, 500-year stability over several seeds, performance check. | stability bands over 5 seeds |
| **P8** | Full validation against Python behaviour. Only after that, and with fresh approval, delete the old Python system. | — |

The old Python system stays in place until P8, as requested. The earlier approval to delete it now waits for that point.

## 5. Stability targets for P7

- Population stays within ±30% of the initial level over 500 years, across 5 seeds.
- Polities per world stay ≤ the number of settlements × 1.5.
- Coups and civil wars: between 1 and 4 changes of regime per polity per century, on average.
- Logged events stay ≤ about 30 per simulated year in each world.
- Food, gold and stone ledgers close with |Δ| < 1e-6.
- Performance stays at or above 80% of the P0 baseline in steps per second.
