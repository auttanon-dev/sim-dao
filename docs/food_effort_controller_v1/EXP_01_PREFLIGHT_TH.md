# EXP-01 — preflight ก่อน implementation

2026-10-02 · **PREFLIGHT_PENDING — ยังไม่สร้าง controller/harness และยังไม่รัน tests**

อ้างอิง [SPEC_TH.md](SPEC_TH.md), [DECISIONS_TH.md](DECISIONS_TH.md), [TEST_PLAN_TH.md](TEST_PLAN_TH.md) และคำสั่ง EXP-01 ของผู้ใช้ ฐาน frozen source `95b07ea260d19771810e7748eb61fbbb50db2174` ไม่แก้เอกสาร spec เดิมให้ดูเหมือนผ่านการทดสอบแล้ว

## ข้อกำหนดที่ผู้ใช้เลือกแล้ว

| Contract | EXP-01 | ตำแหน่งใน spec |
| --- | --- | --- |
| Timing | native pre-production หลัง spoil/endowment/snapshots; accounting-only ของ tick ปัจจุบัน | §2 |
| Scope | certified closed-local/surplus-only; shared/export ที่รับรองไม่ได้ fallback 1 | §1, §4 |
| Imports/pricing | imports credit 0; elasticity=0 เท่านั้น | §5, §6 |
| Production | F(A×e+H); ไม่ลด child capacity ปัจจุบัน; raw capacity/pay/roster ไม่เปลี่ยน | §3 |
| Reserve | รักษา baseline binding-cap closing reserve; target เกิน cap หรือข้อมูลไม่พอ fallback พร้อม reason | §3–5 |
| Lookahead | 90 accounted days; demand bound 1.10×current known daily ration demand | §4–5 |
| Availability stress | largest currently eligible adult loss 30 วัน; future child lower bound 0; worst position ไม่ใช้ fixture schedule | §4–5 |
| Terminal | reserve ≥30×bounded daily demand | §4–5 |
| Effort | continuous minimum .90; ลดได้ไม่เกิน .10 ต่อ decision | §3, §8 |
| Entry/reentry | 2 consecutive certified-safe observations; unknown/unsafe observation reset streak | §5, §8 |
| Emergency | เพิ่มกลับ 1 ที่ native decision ถัดไปทันที ไม่รอ ramp/streak | §2, §5 |
| Debt | ไม่ลด committed target เพื่อลบ debt; ownership/topology เปลี่ยน fallback และ target unresolved | §5 |
| Preservation | strict meals/packs/affordability/per-cid farm pay; ไม่มี occupational pay/time/activity credit | §4, §6 |
| Bookkeeping | ภายนอก simulation/save ไม่เพิ่ม original state fields/hash schema | §5, §8 |
| Batch | 11 subcases × baseline/candidate ×2 repetitions =44 runs; controller ไม่เห็นชื่อ/schedule/future trace | test plan |
| Stop | runtime/metadata errors หยุด INCOMPLETE ไม่ retry; added harm เป็น candidate failure แล้วทำ independent cases ที่เหลือ | test plan + คำสั่งล่าสุด |

ไม่มีข้อขัดกันในค่าตัวเลขที่ผู้ใช้ตรึง ข้อความ DESIGN ONLY ในเอกสารเดิมเป็นสถานะของงานออกแบบก่อนหน้า; คำสั่งล่าสุดอนุญาตเฉพาะ experimental implementation/tests แล้ว ไม่อนุญาต production integration

## นิยามที่ยังต้องปิดก่อน implementation

**1. Horizon และ stress loss กับ retrospective accounting**

Source ใช้ eligibility ณปลาย tick กับผลผลิตทั้ง `[t−Δ,t)` ไม่จำลองแรงงานรายวัน จึงมีความต่างระหว่างลดแรงงานเฉพาะ 30 วันใน daily forecast กับตัด producer จาก native snapshot ของช่วงนั้น EXP-01 ยังไม่ได้เลือกวิธีเทียบสอง semantics นี้

ข้อเสนอเพื่อให้ตรวจได้และ conservative: horizon `[t,t+90)` เริ่มหลัง closing ของ tick ที่กำลังตัดสิน; future effort=1 ใช้ native cadence Δ ของ miniature ที่ประกาศไว้ ไม่อ้างว่า cadence ของโลกจริงรับรองล่วงหน้า ตรวจ hypothetical loss `[t+s,t+s+30)` ทุก integer start `s=0..60` (calendar/source เป็น integer days) และตัด largest adult จาก **ทุก future native interval ที่ทับ loss window ด้วยความยาวบวก** นี่เป็น lower bound ที่อาจคิด loss รวมเกิน 30 accounted days ไม่ใช่การเปลี่ยน actual production formula หรืออ่าน shock จริง ไม่เลือกเฉพาะ loss ที่เกิดจริง/ตรง native boundary

ผู้ที่ตายหรือไม่ eligible แล้ว ณ snapshot ไม่อยู่ใน future available capacity และไม่เครดิตกลับมาเอง การสิ้นสุด hypothetical loss budget ของผู้ที่ eligible ปัจจุบันเป็น risk assumption ของ envelope ไม่ใช่ prediction ว่า producer จริงจะกลับมา หากไม่ยอมรับ interval-overlap ต้องกำหนด endpoint-only contract ให้ชัดก่อนเขียน forecaster

ตรวจให้ bounded food obligations ไม่ขาดทุก native prefix และตรวจ floor 30 วัน **เฉพาะ terminal** ไม่เติม reserve floor 30 วันทุก prefix เป็น guard ใหม่โดยเงียบ ๆ Forecast ต้องรวม spoil, nonlinear production, meals และ conservative bounds ของ pack outflows; ไม่เครดิต future imports/endowment/death returns, cap growth หรือ future child labour Current strict affordability/pay comparison ต้องใช้ current-snapshot projection ตาม stage จริง ไม่ใช้ stress demand เป็นผู้ซื้อสมมติที่ได้รับเงินฟรี

**2. Window เดิมไม่พอสำหรับ observation/recovery coverage**

เดิมสอง subcases มี 4×30=120 วัน; ที่เหลือมี 3×10=30 หรือ 4×10=40 วัน แต่แม้ 120 วันก็ไม่มี 90 วันหลัง decision สุดท้ายของ core และ shock เดิมเกิดที่ core tick 2 ก่อนสร้าง pre-shock streak 2 ครั้ง จึงควรตรึง lead-in/tail ก่อนรัน ไม่เลือกวันจากผลลัพธ์

ข้อเสนอเดียวจาก profile: เพิ่ม **2 native ticks ของ full effort** ก่อน start เดิมทั้งสอง arms เพื่อเก็บ safe observations จริง; initial population/stock/capital เดิมอยู่ ณวันเริ่มใหม่ ไม่มี reset ที่เข้า core คงวัน shock/return เดิมแบบ absolute; core เดิมใช้ controller; จากนั้น observation tail **90 วันของ full effort** ทั้งสอง armsเพื่อดู debt/recovery Tail เป็น externally mandated restore test ไม่ใช่หลักฐานว่า controller เลือกคืน 1 เอง การคืน 1 ตาม guard ต้องตรวจจาก core และ read-only interface checks แยกกัน

| Subcase | Δ | Initialization ใหม่ | Core ticks | Core end | Tail end | ticks/run |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| single_low_demand_overflow |30|10890|4|11070|11160|9|
| normal_volunteer_child |10|10930|4|10990|11080|15|
| no_normal_producer_affordability |10|10930|3|10980|11070|14|
| shared_source_competing_destinations |10|10930|4|10990|11080|15|
| winter_entry |30|11160|4|11340|11430|9|
| empty_stock_import_dependence |10|10930|4|10990|11080|15|
| delivery_reference |10|10930|4|10990|11080|15|
| delivery_source_scarcity |10|10930|4|10990|11080|15|
| delivery_more_competition |10|10930|4|10990|11080|15|
| producer_death_restore_effort |10|10930|4|10990|11080|15|
| producer_travel_restore_effort |10|10930|4|10990|11080|15|

Lead-in decisions ลงบัญชีจนถึง start เดิม; core decision dates เดิมไม่เลื่อน Death/travel shock ยังคง day10970 และ travel return day10990 ไม่ส่งข้อมูลเหล่านี้เข้า controller รวม 152 ticks ต่อ suite ×4 arms/repetitions = **608 food ticks /44 miniature runs** ไม่ใช่ world replay

Lead-in เปลี่ยน stock/pack/hunger/funds ที่เข้า core ตามพฤติกรรมจริง จึงไม่ใช่ initial core state เดิม ต้องรายงาน provenance ของหน้าต่างใหม่แยกจาก diagnostic เก่า Hidden-poor ไม่มีเงินใน fixture3 อาจถึง starvation threshold จริงระหว่าง window นี้; ไม่เติมอาหาร/เงิน ไม่แก้ threshold ไม่ห้าม baseline mortality ไม่ reset เพื่อรักษา fixture ให้อยู่ในสภาพที่ดูดี ถ้าคง window เดิม ต้องรายงาน observational coverage ไม่ครบ ไม่อ้างว่า projection 90 วันแทน observed recovery 90 วันได้

## Contracts เสนอสำหรับ manifest ก่อนรัน — ยังไม่ frozen

- Runtime batch limit 10 นาที รวม preflight execution/interface checks/run/report verification; evidence limit 10 MiB; concurrency1 ไม่มี retries/sweeps ชื่อ output ใหม่ ไม่เขียนทับ archive/out เก่า ขณะนี้ยังไม่เริ่ม clock ของ batch เพราะยังไม่มี approved window/forecast contract
- Compile checks สคริปต์ใหม่ทุกตัวก่อน execution; source/config/original evidence/tools hashes ก่อนและหลัง; source revision/full digest semantics เดิม; canonical every-key/full-state/RNG checks
- Exact equality สำหรับ e=1/disabled จาก identical current input และ deterministic repetitions; ห้ามใช้ metric epsilon แทน hashes ใน no-op arms Arms ที่เคยลดแล้วแต่กลับ1 ต้องแยก same-input equivalence ออกจาก path-dependent stock history
- Food/gold/demand ledger closure absolute residual <1e-7 หน่วย food/gold ตาม ledgerเดิม; scalar preservation absolute tolerance 1e-9 หน่วยของ metric ไม่เพิ่มตามผล; no-extra RNG exact0; roster/eligibility/cid ownership exact; effort formula absolute tolerance1e-12 และ produced formula1e-9 ตาม diagnosticเดิม Feasibility จะไม่เครดิต tolerance เป็นอาหาร/เงินหรืออนุญาต floor breach; ใช้ margin ไปทาง conservative
- ไม่เพิ่ม cooldown หรือ biological clearance margin ที่ผู้ใช้ไม่ระบุ; streak2 และ guard feasibility ตาม profile มี numerical roundoff contract แยกจาก risk bounds
- Reserve debt ใช้ committed target เดิมกับ actual accessible reserve ตาม spec ไม่ลด targetเมื่อ cap/demandลด และไม่บวก debtซ้ำใน inverse จะต้องระบุ phase ของ debt observation ใน trace ค่า post-spoil reserve อาจต่ำกว่า committed closing targetแม้ tickก่อนปิดที่ cap; literal pre-production debt veto สามารถทำให้เกิด full-effort abstentionได้ จะไม่เปลี่ยนไปวัด debt เฉพาะ closing เพื่อให้ profileลดได้มากขึ้นโดยเงียบ ๆ
- Lead-in full-effort observations นับได้เมื่อ current/future certificatesครบจริงเท่านั้น ไม่ตั้ง streak=2ล่วงหน้า ไม่ commit targetเสมือนมี reduction; tail restore ไม่ถูกนับเป็น qualified reduction
- Persist evidence ทันทีแต่ละ native phase/tick; status RUNNING/COMPLETED/INCOMPLETE ชัด; missing record/mismatch/runtime error แยก; first adverse boundaryเก็บพร้อม baseline/candidate differences
- Read-only fail-closed checks: missing/NaN/stale/version/config/domain, target>cap, scope/ownership changeพร้อม unresolved debt, upward bypass, two-streak reset, identical visible prefix with hidden future suffixต่างกัน ไม่มี food steppingเพิ่มใน checksเหล่านี้
- Full current projectionต้องไม่แก้ simulation/RNG; หากยังรับรอง local branch/funding/pack/household/topologyไม่ได้ คืนUNKNOWN/e1 ไม่ทำ optimistic forecast ตัวcontrollerรับเฉพาะ versioned immutable current observation/known calendar/history ไม่รับ MicroSim/case objectหรือ future scheduler
- Success gate: equivalence/interface/determinism/closureครบ +อย่างน้อยหนึ่ง qualified actual reductionลดoverflow +preservationครบ +no added harmใน admitted domain +expected abstentionในunsupported cases หากไม่มีqualified reduction สรุป objective unmet ไม่ลดguards

รายงาน reduction, abstention, certified-no-discard/no-op, baseline adversity, added candidate harm และ unresolved target ครบ11subcasesทั้ง2repetitions ไม่อ้างว่า closureหรือdeterminismพิสูจน์safety

## Provenance และสถานะ

อ่าน spec/test plan/decision list, archived fixture manifest/harness และ frozen `tiandao/food.py`, `tiandao/seasons.py` เท่านั้นใน preflight นี้ ยังไม่มีการ import/run food kernel, prototype หรือ44-run batch ยังไม่ freeze final executable manifest เพราะสองข้อข้างต้นยัง pending ไม่ใช่ runtime failure และไม่มี test results

ขอบเขตความเสี่ยงนอกการรับรองยังคงมี multiple producer losses, demand shockเกิน10%, เหตุหลังcommit, real-world endogenous recruitment/travel/households/market/price feedback และlong-run stability ไม่มี deployment/tuning/world replay/commit/push งาน implementationรอการปิด forecast/window contractตามคำสั่งผู้ใช้ที่ให้รายงานความกำกวมก่อน
