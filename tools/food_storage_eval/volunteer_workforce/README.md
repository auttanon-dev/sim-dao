# Volunteer metrics / stale decision workforce — รายงานการแก้แบบจำกัดขอบเขต

1 ตุลาคม 2026 (Asia/Bangkok) · เริ่มจาก `2fe002436c5c8a8483e2d4fa86834eae1773f265` · ปิดงานด้วย local commit ตามที่ผู้ใช้อนุญาต; ไม่ push

งานนี้แก้สองส่วนแยกกัน: เครื่องมือวัด lifecycle อาสาสมัคร และข้อมูลแรงงานที่ `_adapt_labour` ใช้ตัดสินใจรอบอนาคต
ไม่มีการเปลี่ยน release policy, reserve90 threshold, local-full gate, release order, สูตรแรงเด็ก,
เพดานคลัง ราคา ration เกณฑ์อดตาย การกุศล หรือ random draws; ไม่เริ่ม network forecasting/จัดเวร

## A. Metric fix (observer เท่านั้น)

โค้ด: [volunteer_metrics.py](../volunteer_metrics.py), [balance_run.py](../balance_run.py),
[fixtures](../../../test_volunteer_metrics.py)

| schema 2 | นิยาม |
|---|---|
| `alive_flagged` | มีชีวิต ณ ปลายทาง และ fieldwork=true ไม่รวมผู้ตายหรือ Departed |
| `alive_productive` | ในกลุ่ม alive_flagged ที่ผ่าน `_working` ณ ปลายทาง: **มีสิทธิ์ผลิต** ไม่รับประกันว่าผลิตในช่วงที่ผ่านไปแล้ว (ผู้เพิ่ง recruit ยังไม่ผลิตจนรอบหน้า) |
| `alive_produced_last_interval` | คนที่มีชีวิตตอนนี้และถูกเครดิตเป็นอาสาผู้ผลิตใน food tick ล่าสุด รวมผู้ที่เพิ่ง policy release ตอนท้าย tick ได้ |
| `alive_flagged_produced_last_interval` | กลุ่มข้างต้นที่ยังถือ fieldwork ตอนนี้ ไม่ใช้ eligibility ณ ปลายทางแทนข้อมูลอดีต |
| `flag_spells`, `open_flag_tenure_days` | ช่วงถือ flag และ tenure ของ spell เปิดของคนมีชีวิต; travel/hidden/prison ไม่ปิด flag spell |
| `productive_intervals` | ช่วง `[day-days, day)` ที่ fieldwork=true และ `_working` ผ่าน **ก่อน** food tick (เหมือน snapshot ที่ใช้ผลิตใน simulation) รวมช่วงติดกันใน flag spell เดียว |
| `productive_worker_days` | ผลรวม days ที่ถูกเครดิต ไม่ใช่ความยาว flag spell และไม่ใช่ผลผลิตสำรับ; `volunteer_days` ระดับบนยังเป็น alias แบบ annualized/rounded |
| `completed_by_reason` | spell จบด้วย `policy_release`, `death`, หรือ `other` แยก sample/count/median |

**จุดเริ่ม/จบ:** policy recruitment เริ่มที่ day ของ adapt และผลิตตั้งแต่ tick ถัดไป; policy release จบที่ day ของ adapt
`Sim.kill` ปิด spell ที่ `death_day` แม้ flag ยัง true; fallback observe ตรวจ death_day ที่เก็บไว้ได้เช่นกัน
prune ตรวจปิด death ก่อนทิ้ง fieldwork และไม่เปิด/ปิด policy spell จากการเปลี่ยนเป็น `Departed`
`other` คือ fieldwork ถูกล้างขณะมีชีวิตนอก policy observer ไม่แกล้งอนุมานสาเหตุ
หากเริ่มสังเกต snapshot ที่มี flag อยู่แล้ว `entry_reason=observed` และ start เป็นวันเริ่มสังเกต (left-censored)
ไม่มีการย้อนแต่งประวัติที่ไม่มีหลักฐาน ไม่ล้าง fieldwork ของโลกเพื่อให้ metrics ดูถูกต้อง

interval/worker-days เป็นเครดิตตามนาฬิกา simulation ไม่ใช่ timesheet รายวัน: eligibility ณ food tick ใช้กับทั้งช่วงที่เพิ่งผ่าน
การตาย/ย้ายหลังผลิตไม่ถอนเครดิตที่ผ่านมา; หาก eligibility ขาดใน tick จะเกิดช่องว่างใน productive intervals
flag spell ที่ release แล้ว recruit ใหม่จะตัด productive intervals แม้เวลาเชื่อมติดกัน
ข้อมูล production ล่าสุดมาจาก snapshot ก่อน tick แยกจากสถานะหลัง adapt/การเคลื่อนที่ภายหลัง

**Median และข้าม seeds:** ใช้ `statistics.median` (N คู่เฉลี่ยสองค่ากลาง) ไม่ใช้ upper-middle
กลุ่มว่างเป็น `null`, ไม่ใช่ 0; completed medians แยกตามสาเหตุ
`aggregate([run['volunteer_metrics'], ...])` คืน mean count ต่อ seed (รวม seed กลุ่มว่าง),
mean ของ seed medians ที่ไม่ว่างพร้อม `nonempty_seed_medians`, และ pooled-person median จาก concatenated samples เป็นคนละช่อง
ห้ามตีความ mean ของ medians เป็น pooled median และห้ามรวม schema 1 กับ 2 โดยไม่ตรวจนิยาม
annualized rate หารด้วย `(end_day-start_day)/365` จริง; raw worker-days/intervals ยังเก็บเต็ม

**รายงานเดิม:** เพิ่มหมายเหตุใน [README เดิม](../README.md) และ [§55](../../../AUTONOMOUS_WORLD_PHASE0_TH.md)
คงตัวเลขและ [results_18seed.json](../results_18seed.json) เดิมทั้งหมด ค่า 182 คือ mean old open_spell รวมผู้ตาย;
5,397 คือ mean ของ upper-middle median ต่อ seed ไม่ใช่ pooled median ค่า 25.8k worker-days ใช้คนละนิยามและไม่ได้เสียจากปัญหา ongoing
ไม่มีรายละเอียดรายคนของ 18 seeds เก่าพอให้กู้ alive counts จึง **ไม่แทนค่าเฉลี่ยเดิมด้วย seed 11**

## B. Production fix: ยืนยัน red ก่อนแก้ข้อมูลอนาคต

โค้ดแก้มีเฉพาะ [food.py `_adapt_labour`](../../../tiandao/food.py); regression:
[test_food_workforce.py](../../../test_food_workforce.py)

full-tick fixture รัน `FOOD.tick(sim, 30)` จริง สร้าง workers_at → ผลิต → feed → เปลี่ยน eligibility → adapt
death ใช้ `Sim.kill` จริง; travel ใช้ `Sim.start_process(..., 'travel', ...)` จริง
การเปลี่ยนถูก inject หลัง feed เพื่อควบคุม boundary นี้ ไม่ใช่การเรียก adapt ด้วย list ผิดโดยลำพัง และไม่อ้างความถี่เหตุนี้ในโลกธรรมชาติ
fixture ใช้ประชากรจำกัด ปิด wages/guardians และ spoil ชั่วคราวผ่าน test context เพื่อแยก boundary
stocks ตั้งต้นมีแหล่งใน ledger ของ fixture; bounded replay ใช้ค่า production defaults ครบ ไม่ใช้ switches เหล่านี้

ผู้ผลิตปกติไม่ต้องกินข้าว (realm ≥ FOOD_BIGU_REALM) แต่ `_working` ผ่าน จึงเปลี่ยน alive/travel ของเขาโดย demand ไม่เปลี่ยน
ผู้กินคืออาสาหนึ่งผู้ใหญ่และเด็กหกขวบสองคน ไม่มี chores: demand ณ boundary = 2 สำรับ/วันอย่างถูกต้อง
ฤดูของช่วง day 90–120 = 0.7, ผู้ผลิตแรง 1 ให้ 3.358/วัน ≥ 2; หลังเขาตาย/ออกไป แรงที่เหลือหลังถอนอาสา = 0 < 2
ไม่มี deficit รอบที่ผ่านมา คลังท้องถิ่นเต็ม แต่ attributed reserve = 91.25 < 180 จึงเข้า **marginal/local-full** ไม่เข้า reserve90
โค้ดเดิมยังนับแรงผู้หมดสิทธิ์แล้วปล่อยอาสาคนเดียวผิด; patched code เก็บอาสาไว้
ผลผลิตช่วงที่ผ่านมา = `land_output_per_day(2) × 0.7 × 30` ไม่เปลี่ยน และ ledger ยังปิด

ก่อนแก้ production: 8 full-tick tests มี **7 fail + stationary control ผ่าน** ดู [red log](evidence/regression_red.txt)
หลังแก้: death/travel/hidden/prison/location/world/age ทั้งหมดผ่าน; stationary control ยังปล่อยส่วนเกินได้

การแก้สร้าง decision copy ของ workers_at โดยกรอง `_working(ch, day)` และ `_spot(ch)==spot`
ตรวจ alive, อายุ, travel, hidden, prison, producer eligibility และสถานที่/โลกปัจจุบันตามฟังก์ชันเดิม
รายชื่อแรงงานของช่วงที่ผลิตและรับค่าข้าวไปแล้วไม่ถูกแก้ในที่เดิม ไม่ย้ายเครดิตผลิต/ค่าจ้าง/ledger ย้อนหลัง
ผู้สมัคร idle ใน eaters snapshot ต้องยังอยู่ spot เดิมด้วย จึงไม่รับคนที่ย้ายไปแล้วให้ผลิตที่ต้นทาง
ไม่ล้าง flag ของคนที่ย้าย/พัก/ตายทั้งหมด และไม่สร้าง workforce ใหม่ทั่วโลกหรือโยกคนไปชุมชนอื่นอัตโนมัติ

**สิ่งที่คงไว้:** eaters/demand/deficit/capacity และฤดูเป็นข้อมูลจากรอบเดิมตาม policy เดิม ไม่ได้เปลี่ยนเป็น forecast
กรณีที่ผู้กินเองตาย/ย้ายก่อน adapt อาจมีคำถามเรื่อง demand snapshot เพิ่ม แต่ไม่ได้แก้ในงานนี้
fixture จงใจทำ demand คงที่เพื่อพิสูจน์ workforce bug โดยไม่ปนการเปลี่ยน demand/reserve semantics
recruitment ยังตอบสนอง deficit จากช่วงที่ผ่านมา ไม่มีการเพิ่ม target เพื่อชดเชยทุกความเสี่ยงในอนาคต

## การตรวจผลและหลักฐานแยกสองส่วน

| ตรวจ | ผล |
|---|---|
| metric fixtures | death, actual prune hooks, travel, hidden, prison, policy/other/reset, reentry, median/aggregation, observer purity และ recruit ก่อนผลิต ผ่าน |
| stationary / release order | strongest/weakest, seasonal trough, dependants, equal-capacity cid tie และ reverse input order ผ่าน |
| location guard | ไม่ recruit idle ที่ย้ายแล้ว; ไม่ล้าง fieldwork ของอาสาที่ย้ายด้วย stale origin snapshot ผ่าน |
| focused ชุดแรก | 24 checks ผ่าน (ก่อนเพิ่ม fixtures สุดท้าย) |
| scoped checks สุดท้าย | **127 checks ผ่าน**: food, storage, wages, metrics, workforce และ death transaction units ดู [log](evidence/scoped_checks.txt) |
| bounded metric-only | source `2fe0024`, seed 11, 2 ปี; observer เทียบ no-observer ได้ raw food stats, stocks, RNG และ endpoint counts เหมือนกัน |
| bounded production fix | สำเนา source หลังแก้, seed 11, 2 ปี; food stats/stocks/RNG/volunteer metrics ตรง metric-only ในช่วงนี้ |
| determinism | production-fix replay ซ้ำอีกหนึ่งครั้ง output JSON ทั้งก้อนตรงกัน รวม intervals, RNG และ stocks |
| conservation | full-tick และ bounded: food gap ~1.20e-8, gold gap ~2.91e-11; ledger และ required=eaten+unmet ตรวจใน food/storage suite |

bounded replay นี้มี alive_flagged=57, endpoint `_working`=57 แต่ alive_flagged ที่ถูกเครดิตผลิตใน tick ล่าสุด=37
last food day=720 ขณะที่ end_day=730; flag median=190 วัน; productive worker-days รวม=22,860
completed policy releases=101, deaths=1, other=0 ทั้ง metric-only และ patched source
ตัวเลขนี้ **ไม่ใช่ผลปี 50** และไม่แทนค่า 18 seeds; replay ไม่เกิดความต่างจึงไม่ได้พิสูจน์ว่า full-tick bug ไม่มีผลระยะยาว
ดู [bounded summary](evidence/bounded_summary.json) และ [observer control](evidence/production_fix_observer.txt)

**ข้อจำกัดการรันตรวจ:** เคยเรียกชุด `test_death` ทั้งโมดูลโดยพลาดตรวจว่ามี 30-year × 3-seed walk ภายใน
ก่อนหยุด suite log แสดงว่า walk นั้นจบ `ok` แล้ว แต่ suite ทั้งก้อนถูกยุติด้วย exit 4294967295 จึงไม่นับเป็นผลผ่านของงานนี้
เก็บ log ที่ถูกยุติไว้ใน output; runner ถาวร `run_checks.py` ตัด walk นั้นออกอย่างชัดเจนและให้ผลผ่าน 127 checks ข้างต้น
ไม่ได้รัน food-storage comparison 18 seeds ใหม่

## เรื่องแรงเด็กที่เลื่อนไว้

เก็บ reproducer ใน [reproduce.py](reproduce.py) (`--child-only`) และผล [child_reproducer.json](evidence/child_reproducer.json)
หนึ่งผู้ผลิตปกติ + หนึ่งอาสา + เด็ก chores 8 คน: demand=6/วัน
หลังถอนอาสา สูตร release ที่ไม่นับเด็ก=4.797/วัน แต่สูตรผลิตที่รวมแรงเด็ก 2 ได้ 13.272/วัน จึงยังรั้งอาสาตามกฎเดิม
ไม่ได้เพิ่ม reliance ต่อเด็กหรือแก้ release/recruitment formula ในงานนี้

ก่อนเสนอแก้สูตรนั้นต้องทดสอบ full-tick chores start/end, interruption เพราะหิว, hidden/เดินทาง/บ้านเปลี่ยน,
เด็กโตพ้นอายุแรงงาน/เข้าสู่วัยผู้ใหญ่, การหักมื้อจาก larder และช่วง tick ข้ามฤดู
ต้องทดสอบฤดูผลผลิตต่ำเมื่อ chores หยุดก่อน/หลัง boundary และ copied-state/world replay ที่วัด deficit/unmet/overflow/worker-days แยกกัน
หากเดินโลกสำเนาหลังถอนคน ประวัติและ random trajectory อาจเปลี่ยน แม้ RNG เริ่มเท่ากัน; ต้องรายงานจุดแยก ไม่อ้าง annual surplus ว่าหน้าหนาวปลอดภัย

## Reproduce

ทำจาก repo root ด้วย Python 3.12; คำสั่งนี้ไม่เขียนเซฟโลกเดิม ไม่ commit/push:

```powershell
python tools/food_storage_eval/volunteer_workforce/reproduce.py
python tools/food_storage_eval/volunteer_workforce/reproduce.py --child-only
python tools/food_storage_eval/volunteer_workforce/run_checks.py
python tools/food_storage_eval/volunteer_workforce/run_bounded.py out/volunteer-workforce-reproduce-NEW
```

`run_bounded.py` ปฏิเสธ output ที่มีอยู่ สร้าง before จาก `git archive 2fe0024 tiandao` และ after จาก tiandao working tree
รัน seed 11 สองปีต่อ source + repeat หลังแก้ + no-observer control ทั้งสอง source; ไม่เรียก run_compare.py
เก็บ source copies, JSON เต็ม และ comparison/sha256 ใน output ใหม่

ทำ red ซ้ำกับ before copy ที่สคริปต์สร้าง (expected nonzero; source baseline เท่านั้น fixtures มาจาก current tests):

```powershell
python tools/food_storage_eval/volunteer_workforce/reproduce.py --source out/volunteer-workforce-reproduce-NEW/before
```

raw outputs ครั้งนี้อยู่ใต้ `out/volunteer-workforce-fix-20261001/` (gitignored), evidence สำคัญอยู่ในโฟลเดอร์นี้ถาวร
โปรดแยก metric-only result ออกจาก production fix และไม่อนุมานผลต่อการอดตาย/อาหารทิ้งระยะยาวจาก bounded no-difference
ผู้ใช้รับงาน A/B และอนุญาต local commit แล้ว โดยตรวจ final diff และยืนยันว่าโค้ด/tests ตรงกับฉบับที่ผ่านการตรวจ จึงไม่รันงานซ้ำ
ค่า `no_commit_push` ใน evidence/manifest.json บันทึกสถานะ ณ เวลาตรวจหลักฐานก่อนการอนุญาต commit นี้
การประเมินหลาย seed หรือการเปลี่ยนนโยบายยังต้องได้รับคำสั่งเพิ่มเติม; ไม่เริ่มต่อโดยอัตโนมัติ

## ปิดการตรวจ seed 18 / world 8 / place 85

2 ตุลาคม 2026: [รายงานปิดงานและหลักฐานถาวร](../seed18_world8_place85/REPORT_TH.md) หยุดที่ day 11010 ไม่พบบัค production ใหม่ในช่วงที่ตรวจ ยังไม่พิสูจน์ความปลอดภัยทุกฤดู; การเพิ่มเอกสารไม่รัน simulation ซ้ำและไม่แก้ policy
