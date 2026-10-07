# Controller specification v1 — conservative surplus-only candidate

2 ตุลาคม 2026 · สถานะ **DESIGN / NOT IMPLEMENTED / NOT VALIDATED**

ฐาน source `95b07ea260d19771810e7748eb61fbbb50db2174` และ [ชุดหลักฐานถาวร](../../tools/food_storage_eval/effort_diagnostic_v1/README.md) งานนี้เก็บหลักฐานและออกแบบเท่านั้น ไม่สร้าง prototype เพิ่ม ไม่ execute simulation ไม่แก้ production และไม่ commit/push

เป้าหมายคือหลีกเลี่ยงผลผลิตส่วนที่ถูก cap ทิ้ง โดยรักษา realized feeding/pack/reserve และไม่เปลี่ยน roster/profession/fieldwork/body capacity ไม่มีการคืนเวลา เพิ่มกิจกรรม หรือให้ค่าแรงอาชีพเดิม เมื่อ inputs/config/forecast assumptions ไม่ครบหรือพิสูจน์ขอบเขตความเสี่ยงไม่ได้ ให้ **effort=1** พร้อมเหตุผล; fallback นี้ไม่รับประกันว่า baseline จะไม่มี shortage

## 1. Scope ของ candidate

Candidate v1 จำกัดการลดไว้ที่ **closed local food component** ซึ่งตรวจได้ว่าไม่มี imports ที่ต้องพึ่ง และไม่มี outgoing demand/competing destination ที่ยังไม่ได้คำนวณ สถานที่ shared/exporting/import-dependent หรือมี reachability/ประชากรนอก scope ที่ประเมินไม่ได้ให้ e=1 ก่อน รุ่นนี้ไม่เสนอกฎแบ่ง effort ระหว่างหลายแหล่งเพื่อ optimize network

การมี granary ใกล้เคียงว่าง ณ ขณะหนึ่งไม่เท่ากับไม่มีคู่แข่ง; ต้องใช้กราฟ/serving scope และ demand ทุก destination ที่แหล่งนั้นส่งถึง ไม่กรองเพียงระยะจาก focal หากไม่สามารถรับรองขอบเขตนี้ให้ abstain รุ่นนี้อาจไม่ทำงานกับสถานที่ส่วนใหญ่ใน world จริง เป็น tradeoff ที่ยอมรับเพื่อจำกัดข้ออ้าง

ลดเฉพาะกรณีที่ conservative projection ของ e=1 มี **production-caused cap overflow** และ e ที่เสนอรักษา closing reserve เดียวกับ e=1 ที่ binding cap พร้อม meals, packs/larders, hunger และ payment outcomes ที่ไม่แย่ลงภายใต้ current snapshot ไม่ใช้ overflow ย้อนหลังเป็นคำสั่งลดใน tick ถัดไป ไม่เครดิต death returns หรือ speculative imports เพื่อสร้าง headroom

## 2. Timing และความหมายของ effort

Source `Sim._world_tick` เรียก `FOOD.tick(sim, sim.day-sim.food_day)` ก่อน WAGES.tick และปรับ food_day หลังจบ tick ภายใน food.tick ลำดับคือ spoil/endowment → สร้าง eaters/workers/child snapshots → production → prices/reservation/transport/feed → pack/larder/pay → hunger responses → cap/adapt

**Decision point ที่เสนอ:** หลัง spoil/endowment และ snapshot formation ก่อนคำนวณ production/ก่อน `_set_prices` ณ day=t ใช้ actual days=Δ=t−previous_food_day ไม่สมมติว่า Δ=30 เสมอ Effort ใช้หนึ่งค่าต่อ local spot กับ adult production capacity ของ **food tick นี้เท่านั้น** ต้อง re-evaluate ทุก tick; ไม่ส่งค่าเก่าข้าม tick โดยอัตโนมัติ

Native accounting ลงผลผลิตย้อนหลังให้ช่วง [t−Δ,t) ด้วย eligibility ณ t Candidate ใช้ semantics เดียวกันโดยไม่ให้เครดิตเวลา/แรงงานจริงรายวัน ไม่อ้างว่าเลือก e ณ t แล้วป้องกันเหตุการณ์ตลอดอดีต interval ได้ หากต้องการ policy ที่เลือก effort ล่วงหน้าเพื่อใช้ [t,t_next) จริง ต้องออกแบบ clock/state persistence ใหม่แยกต่างหากก่อน implementation ไม่ผสมกับ v1 นี้

Post-tick เป็น feedback/journaling เท่านั้น: ถ้าพบ debt/unmet/unpaid/shortfall ให้ RECOVER และ e=1 ที่ decision point ถัดไป ไม่มีอาหารหรือรายได้ย้อนหลังมาชดเชย และไม่แก้ผล feeding ที่เกิดแล้ว เหตุฉุกเฉินก่อน production มีผลให้ e=1 ทันที ณ decision point; หาก state เปลี่ยนระหว่าง snapshot/commit ให้ invalidate projection และ e=1 ไม่อ้างการตอบสนอง mid-interval ที่ engine ไม่ได้จำลอง

### ข้อมูลที่รู้จริงและข้อมูลที่ห้ามใช้

| ใช้ได้ ณ decision point | การใช้/ข้อจำกัด |
| --- | --- |
| day, food_day, actual Δ, frozen config และ deterministic seasonal calendar | season_mean ของ interval ปัจจุบัน; known future seasonal factors สำหรับ lookahead ไม่ใช้ endpoint season อย่างเดียว |
| actual granary หลัง spoil/endowment; actual pack/larder inventory และ accessible ownership | นับของที่มีจริง ไม่รวม attributed/shared reserve เต็มจำนวนหลายที่; packs/larders ของคนอื่นไม่ใช่ freely pooled stock |
| actual living/working/away/jail/hidden/realm/age/roster และ BODY.work_capacity; CHILD.labour ณ t | capacity ปัจจุบันเท่านั้น ไม่รู้ future survivors/returnees/recruits และไม่เพิ่ม capacity จากการลด effort |
| current eater snapshots, rations/pregnancy ที่ทราบ, household draw semantics, demand bounds ที่ผู้ใช้อนุมัติ | ไม่ใช้ future births/migration/demand โดยรู้ผลล่วงหน้า; ขาด bounds ให้ e=1 |
| graph/reachability, serving stores, current reachable destination population/ownership | ขาด scope หรือ shared dependencies ให้ e=1; prior arrivals/asks เป็น history ไม่ใช่ guaranteed future delivery |
| current wallet/purse/charity funds, current hunger/food stats, actual farm/market tills | ไม่ใช้ farm pay ที่ยังไม่จ่ายหรือค่าแรงตลาดในอนาคตมาจ่ายมื้อปัจจุบัน; funding/relief ไม่รู้ครบให้ e=1 |
| prior **observed** outcomes, inventory target/debt และ last availability fingerprint | สำหรับ recovery/hysteresis; ใช้ event เมื่อถูกสังเกตแล้วเท่านั้น |

ห้ามส่ง `fixture.shock`, shock step, future death list, future travel departure/return schedule, future source stock หรือ baseline counterfactual save เข้า controller สถานะ travel_dest ที่มีอยู่แล้วรู้ได้ แต่ไม่สมมติว่าจะถึง/กลับตรงเวลาตาม fixture Future seasonal schedule เป็น known model calendar; death/travel/competition/demand shocks เป็น unpredictable และต้องใช้ risk envelope ไม่ใช่ oracle

## 3. Production และ inverse target

สำหรับ spot s: A=Σ raw adult capacity ของ actual eligible roster, H=actual child capacity, μ=season_mean(t−Δ,Δ), L=FOOD_LAND_CAP_DAY, k=FOOD_PER_WORKER_DAY

```text
F(x) = L × (1 − exp(−k×x/L))
P(e) = Δ × μ × F(A×e + H)
```

H ไม่คูณ e; ไม่ใช้ e×P(1) Body capacity/profession/fieldwork คงเดิม Pay ยังใช้น้ำหนัก raw adult capacities ตามกฎเดิม ไม่ใช่ A×e และเด็กไม่ได้ farm pay ใหม่ Marginal child output เปลี่ยนได้จาก nonlinear curve โดย child labour ไม่เปลี่ยน

สำหรับ closed component ที่ได้ validated bounds: S0=local actual stock ณ decision, O_ub=upper bound ของ outflows ที่ต้องรักษา (meals/pack/larder/other allowed flows), R_required=closing inventory target ที่ผ่าน floor/season/stress checks การนับปัจจุบันไม่รวม spoil ที่หักไปแล้วซ้ำและไม่นับ income เป็นอาหาร

```text
P_required = max(0, O_ub + R_required − S0)   # imports credit = 0
e_required = (−L/k × log(1−P_required/(Δ×μ×L)) − H) / A
e_target = clamp(max(e_required, e_min), e_min, 1)
```

ใช้ inverse เฉพาะ A>0, Δ>0, μ>0 และ 0≤P_required<ΔμL; domain invalid/capacity infeasible ให้ e=1 และระบุ baseline deficiency ถ้ามี ค่า inverse เป็น candidate input ไม่ใช่ safety certificate ต้องผ่าน projection/checks ด้านล่างหลัง clamp และ ramp เสมอ ไม่ใช้ inverse แทน feeding/affordability/accounting

`R_required` สำหรับ surplus-only entry ต้องรักษา closing reserve ของ baseline ที่ binding cap (ไม่ลด reserve เพื่อแลก overflow) และไม่น้อยกว่า approved reserve floor/stress target ถ้า target เกิน real cap ให้ e=1 + report infeasible; ห้ามขยาย cap หรือสร้างอาหารเพื่อทำให้ผ่าน ไม่เลือก e=0.75/0.5 เพียงเพราะเป็น diagnostic levels และไม่ sweep thresholds

## 4. Conservative projection contract — ยังไม่ได้พิสูจน์/implement

Forecaster ที่ต้องออกแบบเพิ่มเป็น deterministic, read-only local model ของ native food stages ใช้ current snapshot และ approved bounds ไม่ step โลก, ไม่ draw RNG, ไม่ติดตั้ง wrappers/prototype ในงานนี้ ต้องมี valid-domain certificate; ไม่รู้ branch/accounting/funding ครบให้ `UNKNOWN` แล้ว e=1 ไม่ถือ optimistic point forecast เป็น certificate

ที่ e=1 และ proposed e ตรวจ:

1. real allocation/feeding/pack/larder/cap semantics ใน certified closed scope; O_ub ครอบคลุม transfers ทุกชนิดที่อนุญาต ไม่มี omitted exports หรือเครดิต future endowment/death-return;
2. positive overflow ของ e=1 มาจาก current production และ production reduction ไม่เกิน discard ที่คำนวณได้หลัง all actual competing uses ไม่ใช้ negative float noise เป็น surplus;
3. projected meals/eaten/pack/larder/hunger/physical shortfall/unpaid/unmet ไม่แย่กว่า e=1; pre-existing shortage/unpaid/unmet หรือ hunger flag ที่ประเมินไม่ครบให้ e=1;
4. closing reserve ที่ e รักษา baseline binding-cap outcome และ approved floor; pricing/pay/funds transfers ต้องไม่แย่ลงตามกติกาที่อนุมัติ;
5. full effort ใน lookahead + stress envelope รักษา floor และเติม reserve debt ได้ ไม่สมมติว่า absent/dead producer กลับมาเอง ไม่สมมติ future child capacity จาก chores ปัจจุบันแน่นอน;
6. any unknown/NaN/unbounded demand/config mismatch/state change → e=1 ไม่ sanitize เพื่อให้ลดได้

Forecast ใช้สภาพปัจจุบันกับ scenario bounds ไม่ใช้ realized baseline future trace ถ้าต้องการ reference e=1 ใน decision เป็น **current-snapshot projection** เท่านั้น ไม่ใช่ parallel world/oracle แฝง การทำ pure forecast ถูกต้อง/เร็วพอและ coverage ของ bounds ยังเป็น implementation blocker

## 5. Reserve repayment, seasonal risk และ shocks

เก็บ controller bookkeeping แยกจาก food/gold ledger: `mode` = FULL / REDUCE / RECOVER, `committed_inventory_target`, `safe_streak`, last observed availability/scope/config fingerprint, reason และ last command ไม่เปลี่ยน original hashes/state fields โดยปริยาย ต้องตัดสิน persistence/versioning ก่อน integration

เมื่อเริ่มลด บันทึก inventory target ที่รับปากรักษา; target อาจเพิ่มสำหรับ known low season ตาม policy ที่เลือก ห้ามลด target เพื่อลบ debt อัตโนมัติหลัง stock ใช้ไป การลด demand/cap หลัง death อาจทำให้ target เดิม infeasible ต้องอยู่ e=1 และ report จนมี approved target-retirement rule ไม่สร้างอาหารหรือปล่อยว่าหนี้หายโดยตัวเลข

```text
debt = max(0, committed_inventory_target − observed accessible local reserve)
```

Debt คือ observed target shortfall ไม่ใช่ parallel-baseline stock gap และไม่ควรเรียกว่าอาหารที่พิสูจน์ว่า controller ทำหาย สูตร P_required มี R_required−S0 อยู่แล้ว **ห้ามบวก debt ซ้ำ** Recovery ผลิตที่ e=1 ด้วย roster ที่มีจริง เติม target จาก net surplusหลัง consumption/loss ไม่ถือการคืน e ว่า debt cleared

ถ้า debt>tolerance หรือ availability/scope/demand แย่ลง, shortfall/unpaid/unmet เกิด, future floor/stress test fail/unknown ให้ RECOVER ก่อนลดครั้งใหม่ ออกจาก recovery ได้เมื่อ actual reserve กลับถึง target, no deficits/affordability alerts, scope/availability complete และผ่าน stable safe streak/hysteresis ที่ผู้ใช้เลือก Emergency return to 1 ต้อง bypass downward-ramp limits; recovery ไม่รอครบ cooldown ก่อนคืน 1

Known low season: ดูค่าเฉลี่ยทุก projected interval และเวลาที่คาดว่าเติมสำรองได้ ถ้า low season/repayment horizon ขัด target ให้ e=1 ล่วงหน้าจาก calendar ที่ระบบรู้ ห้ามตีความ winter restoration test ที่รู้ future producer shocks เป็นหลักฐาน forecasting death

Producer risk: guard observed loss/away/jail/hidden ทันทีที่ decision snapshot เห็น และ stress envelope เช่น loss of largest eligible adult/zero future child labour เป็นสมมติฐานที่ต้องเลือก ไม่รู้ล่วงหน้าว่าใครจะตาย หาก loss มากกว่า envelope, arrival demand spike, topology/config/ownership change หรือเหตุการณ์หลัง commit ยังป้องกันไม่ได้และ e=1 ของคนที่เหลืออาจไม่พอ

Imports/competition: v1 ให้ credit imports=0 และ abstain shared/export scope ไม่อนุญาตให้นับ last imports หรือ attributed reserve เป็น guaranteed arrivals หาก zero-import projection พึ่ง future relief ที่ไม่รู้ funding ก็ abstain ทางเลือก network-aware เป็น design/validation ใหม่ ไม่เปิดใช้ด้วย fixture evidence นี้

## 6. Pricing, affordability และ farm pay

Frozen diagnostic config มี FOOD_PRICE_ELASTICITY=0 และ FOOD_PRICE=0.1 ดังนั้น fixtures ใช้ **ราคาคงที่** ดู [erratum](../../tools/food_storage_eval/effort_diagnostic_v1/ERRATA_TH.md) รุ่นนี้ไม่อ้างว่าพิสูจน์ dynamic-price guard

ใช้ `_set_prices`/price_at และ `_buy` semantics เดิม ณ stage เดิม ถ้า config เปลี่ยนเป็น elasticity>0 หรือ pricing contractต่างจาก certified model ให้ e=1 จนทดสอบใหม่ แม้ราคาคงที่ supply/pack purchases/funding/producer absence ทำให้ farm revenue/pay เปลี่ยนได้ ต้องรายงาน realized meal/pack revenue, tills และ per-cid pay ไม่ใช้ revenue aggregate แทน consumer wellbeing

Physical shortfall, offered-but-unpaid meals และ final unmet เป็นคนละตัว guard/report ห้ามใช้ซื้อไม่ได้ว่าไม่มีอาหารหรือใช้มี stock ว่าทุกคนกินได้ Relief/household/charity ต้องตามทรัพยากรและกฎจริง ไม่เพิ่มเงินให้ passing criterion Income จาก farm pay หลัง meals ไม่ใช่เงินที่ย้อนมาจ่าย meals tickเดียวกัน

Farm pay ยังคง raw BODY.work_capacity weights ของ workers snapshot ตาม `_pay_farmers` ไม่มีการแก้ pay policy ไม่มี normal wages/time credit ถ้า fieldwork ยังอยู่ `WAGES.earns_wages` ต้องยัง exclusion เดิม ภายใต้ surplus-only certificate ให้ meals/pack transfers และ pay ไม่แย่ลง; หาก prove ไม่ได้ให้ e=1 ไม่แก้ pay เพื่อชดเชย

## 7. Guard evidence matrix — ทุก guard เป็นข้อเสนอ

| Guard | Fixtures ที่รองรับเหตุผล | สมมติฐานเพิ่มเติม | ยังป้องกันไม่ได้ |
| --- | --- | --- | --- |
| ลดเฉพาะ production-caused discard และรักษา reserve/feeding | 1 ลด overflow โดย unmet=0 ใน schedule เดิม; 2 nonlinear adult/child | certified current projection ปิดทุก stage และ funding; baseline cap binding | inaccurate outflow bounds, cap changes, future shocks; fixture1 ไม่พิสูจน์ threshold |
| reserve debt lock/คืน 1 โดยไม่ถือว่าฟื้นทันที | 5 คืน 1 แล้วยัง unmet; 8 stock debt แม้ไม่มี added unmet | accessible inventory target, approved repayment horizon/retirement rule | cap infeasible, full productionต่ำกว่า demand, repeated loss |
| known seasonal lookahead | 5 crossing low season | calendar/config deterministic, horizonยาวพอและ future demand bounds | weather/config shocks หรือ populationเปลี่ยนนอก bounds |
| zero-import/no-shared-scope default | 4,6,7 supply/competition เปลี่ยน arrivalsจริง | reachabilityทุก destination complete; true closed scope | new reachable eaters/stores/topology, future exports; v1 ไม่ optimize shared network |
| availability observation + stress reserve | 8 death/travel, return1ไม่คืนคน/availability | explicit loss envelope, no future child guarantee, observation at commit | multiple losses, unseen event after commit, recovery before next decisionไม่ได้ |
| no-normal producerยังต้อง capacity | 3 effort .5เพิ่ม physical/unmet | rations/working/body snapshotsครบและ boundsconservative | endogenous recruits/relocation/body evolution; no-normalไม่เท่ากับ shortageทุกครั้ง |
| affordability independent veto | 3 hidden eater no money; checks separate unpaid/unmet | fund ownership/relief/householdครบ; same-tick pay ordering | dynamicpricingไม่ได้ทดสอบ, poverty/charity flowsในโลกจริง, income shocks |
| fail unknown/stale/config to e=1 | ข้อจำกัดของทุก fixture | valid-domain/version checksไม่ใช้ heuristicแทนข้อมูล | baselineเองไม่ปลอดภัย; fallbackไม่ป้องกันเหตุที่ full effortแก้ไม่ได้ |
| downward ramp + stable-entry hysteresis | 5/8 ชี้ path dependence; ไม่มี fixture calibrate ramp | parametersถูกเลือกก่อน test, emergencyreturn1 bypass | chatter near thresholds, lag policy, long-run cycles ยังไม่ได้ทดสอบ |
| no-extra-RNG/no-free-ledger transfers | diagnostics ทั้ง11subcasesมี e1 equivalence/determinism/closure | implementation read-only decisionและsame source | controllerยังไม่implement; real endogenous eventsอาจเปลี่ยน downstream RNG paths |

ห้ามเรียก guard ใดว่า verified protection จาก matrix นี้; evidence รองรับปัญหา/เหตุผลของ guard ไม่พิสูจน์ proposed rule

## 8. Pseudocode (เอกสารเท่านั้น)

```text
before_native_production(snapshot, previous_bookkeeping, approved_parameters):
    if parameters incomplete or input/config/version invalid:
        return command(1, FULL, reason=UNKNOWN)
    # No access to scenario names, shock schedule or future realized traces.
    risk = inspect_current_state_and_known_calendar(snapshot)
    if risk.unknown or not certified_closed_food_scope(snapshot):
        return command(1, RECOVER if outstanding_target else FULL, reason=UNCERTAIN_SCOPE)
    if observed_loss_or_away_change or deficit_or_affordability_alert or debt > eps:
        return command(1, RECOVER, reason=RESTORE)
    full = project_current_snapshot(1, real_stage_rules, approved_bounds)
    future = stress_project_full_effort(known_calendar, current_bounds, no_future_import_credit)
    if full.unknown or future.unknown or !floor_and_repayment_feasible(future):
        return command(1, RECOVER, reason=RISK_OR_INFEASIBLE)
    if !full.production_caused_binding_cap_overflow:
        return command(1, FULL, reason=NO_CERTIFIED_DISCARD)
    if !entry_hysteresis_met:
        return command(1, FULL, reason=WAIT_FOR_STABILITY)
    target = preserve_full_closing_target_and_approved_floor(full, future, outstanding_target)
    e = clamp(analytic_inverse_required_production(target), e_min, 1)
    e = apply_downward_ramp_only(e, last_command)  # may make e higher/more conservative
    reduced = project_current_snapshot(e, real_stage_rules, approved_bounds)
    if reduced.unknown or !all_meals_packs_reserve_affordability_pay_checks_pass(full, reduced):
        return command(1, FULL, reason=NOT_SURPLUS_ONLY)
    if snapshot_version_changed_before_commit: return command(1, FULL, reason=STALE)
    return command(e, REDUCE, target, reason=CERTIFIED_WITHIN_DECLARED_ASSUMPTIONS)

after_native_tick(observed_actual_outcomes, previous_bookkeeping):
    journal actual stock/pack/larder/produced/eaten/overflow/loss/shortfall/unpaid/unmet/revenue/pay
    update debt from actual accessible reserve and committed target; never add virtual food
    on any missing outcome/failed closure/observed deficit/producer or scope change:
        mark RECOVER and next effort=1; stop claiming safety; preserve first adverse boundary
    else update stable streak; clear debt only from observed repayment
```

Mode changes/forecaster do not mutate roster/eligibility/body/RNG/food/gold. How controller state is persisted and included in new hashes is a later integration decision; e=1/disabled path must retain original production state/RNG semantics.

## 9. Safety statement และ next gate

Conditional model safety ที่เสนอคือ no added shortage/affordability deterioration และ preserved reserve ใน declared closed snapshot/domain/bounded stress scenarios **ถ้า** forecaster, ownership, timing, inputs และ bounds ถูกต้อง ยังไม่มี implementation/test พิสูจน์เงื่อนไขนี้เลย

World-wide safety ยังรับรองไม่ได้: unbounded shocks, endogenous policy/household/death/travel/market/price feedback และ future population/graph changes อยู่นอก diagnostic shell การ default1 ช่วย abstain แต่ไม่ทำให้ทุกโลกปลอดภัย

ก่อน implementation ต้องให้ผู้ใช้ตัดสิน [DECISIONS_TH.md](DECISIONS_TH.md), ตรึง parameters/domain แล้วอนุมัติ [TEST_PLAN_TH.md](TEST_PLAN_TH.md) แยก งานนี้ไม่ได้ execute tests, forecast หรือ simulation และหยุดที่เอกสาร specification
