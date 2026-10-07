# Acceptance tests และการทดลองเล็กที่สุด — ยังไม่ได้รัน

สถานะ tests ทุกข้อ: **PROPOSED / UNEXECUTED** ไม่มี candidate code/forecaster ที่ทดสอบแล้ว การอ่าน/เก็บ fixture evidence ในงานออกแบบไม่ใช่ execution ของ tests เหล่านี้

## Preconditions

ผู้ใช้เลือก parameter/domain/timing profile ใน DECISIONS_TH.md และอนุมัติงาน implementation/testing แยก Manifest ใหม่ต้องตรึง source, single candidate profile, native intervals, admission bounds, failure criteria, repetitions, walltime/output budget และ stop ruleก่อนรัน ไม่มีการใช้ diagnostic three levelsเป็นparameter sweepอีกครั้ง

Baseline arm คือ original food kernel กับ actual same shell, candidate armหนึ่งตัว ไม่มีการรันโลก ไม่มี fixed-baseline delivery override ไม่แสดง shock schedule/controller-readable fixture names ใช้ real nonlinear capacity/child/feeding/allocation/pricing/pay/cap/ledgers และไม่เพิ่มอาหาร/เงินหรือเปลี่ยน starvation/capเมื่อ unsafe

## Acceptance matrix

| Test | Input / trigger | Required assertions และ interpretation |
| --- | --- | --- |
| A1 disabled / e=1 equivalence | fixturesทุกsubcase; controllerdisabledหรือdomainunknownทุกtick | original food state/RNG hashes, every-key state, raw ledgers/stock/meals/pay เท่ากันที่ native phases/return; bookkeepingอยู่ภายนอกและไม่สร้างfieldsในbaseline ไม่อ้าง fixture shellว่าเทียบfullproductionpolicyแล้ว |
| A2 surplus-only success | fixture1 single low demand, actual cap-binding overflow; stable entryตามchosenprofile | candidateมีอย่างน้อยหนึ่ง qualified e<1 และลด actual overflow; meals/eaten/unpaid/unmet/stock/pack/revenue/per-cidpay ไม่แย่ลงภายใต้declaredbounds; ถ้า no-op ให้รายงาน gateไม่แสดงsuccessด้วยclosureอย่างเดียว ไม่ลดfloor/thresholdจนผ่าน |
| A3 nonlinear/child/roster | fixture2 และ fixture3 | P=ΔμF(Ae+H) ไม่ใช่ eP(1); H/rawbody/profession/fieldworkไม่เปลี่ยนโดยcontroller; no-normalต้องวัดcapacityไม่วัดheadcount; ไม่มี wage/time/activitycredit |
| A4 winter/stock debt | fixture5; restore1หลังobservedalert | knowncalendarถูกอ่านแต่shockfutureไม่ได้; must avoid proposedreductionที่certificateไม่ครอบคลุมseason; debtไม่ได้clearedด้วยreturn1; adverse tick/repayment lagและstockgapเปิดเผย ถ้าfull baselineขาดอยู่ต้องแยก baselinefailure จากaddedcandidatefailure |
| A5 shared imports/competition | fixtures4,6,7 reference/source-stock/competitor arms | v1ต้อง abstain scopeที่ certifyไม่ได้และe1เทียบ baseline; requests/scale/arrivalsคำนวณจาก supplyจริง ไม่มี reuseassignedreserve/lastarrivals; source-onlyshockและcompetingdemandchangeแยกกัน; conditionalcompetition residualไม่เรียกcausalreasonจากชื่อ |
| A6 producer loss/away/recovery | fixture8 deathและtravel | identicaldecisionในprefixก่อนshockถ้าvisibleinputsเหมือนกัน; return1เมื่อobservedavailabilityเปลี่ยน ไม่ก่อนจากschedule; no resurrection/no creditfuturearrival; report actual recoverylatency, persistent debt, baselineawayunmet vs addedunmet |
| A7 affordability/pay | fixture3 hiddenpoor; fixture2 child/normal/volunteer funds | physical/unpaid/unmetแยก; current fundsก่อนmealไม่รวมpayที่ยังไม่เกิด; farm revenueจากreal purchasesและ payrawbodyweight; zeroextraordinarywages/virtualfood/gold; source elasticity0คงราคา0.1; elasticity>0configout-of-domain→e1 ไม่อ้างว่าผ่าน dynamicpricing |
| A8 fail-closed / no oracle | missing/stale inputs, impossiblefloor/cap, unsupportedconfig; samecurrentstateกับfuture shock suffixต่างกัน | commande1พร้อมreason; missing/mismatch/errorแยก; forecaster/controllerไม่รู้fixturecase/shockstep/futuretraces; forgedboundsไม่ได้silent pass; baseline e1ยังอาจunsafeและต้องรายงาน |
| A9 determinism/no-extra-RNG/closure | repeatแต่ละarmจากinput/RNGเดียวกัน | commands, traceและfull-statehashes deterministic; controller/forecasterdraws=0; e1 RNG sequenceตรงbaseline; reducedarmrealfood/eventbranchอาจ divergeอย่างถูกต้อง ไม่บังคับ worldRNGเท่ากันทุกevent; food/gold/demandclosure และ stage/transferchecksจริง |
| A10 feedback stability / limitation | initialstockdebt/capchange และ near-threshold snapshots | no debtforgivenessทางtargetลด, no delayedemergencyrestoreเพราะramp/cooldown; hysteresiscountsอ้างจริงไม่สะสมsafeจากunknown; limitcycles/long-termchatterยังถือunknownเมื่อมีแค่สี่ticks |

Test tolerances ต้องตรึงหน่วยล่วงหน้า ใช้ prior diagnostic closure budget <1e-7 เป็น initial verification contract เท่านั้น ไม่เป็น biological safety threshold Exact e1 state/RNG agreement ไม่ผ่อนเป็น focal/tolerance-only comparison ห้ามแก้ serializerเพื่อตรวจผ่าน

## Smallest useful experiment สำหรับ profile เดียว

ใช้ **11 subcases เดิมครบ** มี baselinee1และcandidate1arm อย่างละ2repetitions = **44 miniature runs** (ตัวเดิมมี43 ticks รวมทุกsubcase จึงเป็น172 food ticks ทั้งสองarmsและrepetitions) ไม่ใช่ world replay ไม่เพิ่ม50-year/multi-seed ไม่เพิ่มvariantsเพื่อค้นค่า

จะใช้ inputfixturedataเดิมแต่เปลี่ยน **controller observation interface**: adapterส่งเฉพาะ current snapshot/knowncalendar/observedhistory, shock handlerอยู่คนละส่วน Controllerไม่มีcase name/parametersfuture/shockschedule การรู้อยู่ในharnessไม่เป็นสิทธิ์ให้controllerใช้

เพิ่ม read-only interface checks ที่ไม่ stepfood 4ชุด: missing-input fallback; stale/config-version fallback; identicalprefix/future-suffix metamorphic test สำหรับdeath/travel; impossiblefloor/cap-infeasible fallback รวมนี้เป็นminimum oracle/failclosed audits ไม่ใช่ parameter sweep

หาก chosen profileต้องการ Nsafe/lookaheadเกินwindowเดิม ให้รายงาน **insufficient test window** และเสนอ deterministic lead-in/windowล่วงหน้าจาก parameterที่เลือก ไม่เลือกช่วงจาก observedgoodoutcomes ไม่ถือno-opว่าoverflowobjectiveผ่านโดยอัตโนมัติ No-opในsharednetworkเป็นexpected conservative behavior และไม่ใช่ network-controller validation

Evidenceต่อtick: decision day/phase/accountedinterval, visibleinputhash, admittedbound/configprofile, exclusion/restore reason, commanded/actuale, rawadult/child, produced/eaten/overflow/stock/pack/loss, asks/available/scale/edges, physical/unpaid/unmet, revenue/till/per-cidpay, floor/target/debt/streak, closures, controllerdraws/RNGhash และ mode/first adverse boundary

Stop/report: compile/validation/runtimeerrorหรือ unexpectedmetadata/state mismatch→INCOMPLETE เก็บหลักฐานไม่ retryอัตโนมัติ Addedshortage/affordability harmเป็น **candidate rejection/diagnostic adverse result** ไม่แก้feeding/cap/thresholdหรือ parameters ต้อง retain firstadversecaseและทุกcaseที่ completed; จะ complete remainingindependent plannedcasesหรือstopentirebatch ต้องตรึงในmanifestก่อนรัน ไม่อ้างsafetyเมื่อearlystopขาดcoverage

Successgate: A1/A8/A9ครบ + at leastonecertifiedsurplus success A2 + no addedharmในaccepted-domain tests + expectedabstentionทุกunsupportedcase + explicitout-of-domain risk report การผ่าน gateนี้คือ **candidate under declared model assumptions** เท่านั้น ยังไม่อนุมัติ deploy/worldtest และไม่รับรอง safetyทุกโลก

หลังรายงานผลทดลองเล็กนี้ให้หยุด ไม่ต่อ world replay, controller tuning หรือproductionintegrationโดยอัตโนมัติ
