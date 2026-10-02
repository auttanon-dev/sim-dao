# ปิดการตรวจ seed 18 / world 8 / place 85

ปิดงานวันที่ 2 ตุลาคม 2026 (Asia/Bangkok) ตามขอบเขตเดิมถึง day 11010
การเพิ่มเอกสารครั้งนี้อ่านผลเดิมเท่านั้น ไม่รัน simulation ซ้ำ ไม่แก้ production/policy
ไม่ commit/push และไม่เริ่มการทดลองถัดไป

- ไม่พบบัค production ใหม่ในช่วงที่ตรวจ
- release policy ปล่อยแรงงานส่วนเกินได้: day 10980 ปล่อย 7 คน และ tick ถัดไป day 11010 กินครบ 510 สำรับ
- ยังไม่พิสูจน์ความปลอดภัยทุกฤดู
- สาเหตุอาหารส่งถึงลดลงยังแยกต้นทางขาดกับการแข่งขันจัดสรรไม่ได้
- เรื่องแรงงานระยะยาวและ overflow ยังเป็นงานออกแบบ ไม่ใช่บัคที่ยืนยันจากกรณีนี้

ใช้ revision `95b07ea260d19771810e7748eb61fbbb50db2174`, Python 3.12.10,
production defaults, metrics schema 2, concurrency 1 หลักฐาน ledger ใหม่เดิมมีเฉพาะ
10920/10950/11010 และนำ anchor tick 10980 ที่ตรวจแล้วมาเก็บด้วย
ไม่มี checkpoint state/RNG ครบ; ผลเดิมมาจาก bounded replay ไม่ใช่ continuation จาก checkpoint

หลักฐานที่นำมาเก็บใช้ observer จาก `retry01` ซึ่งแก้การอ่าน boundary ของ `sim.cast`
ที่เป็น list แล้ว รอบแรกมี watch-boundary ว่าง จึงไม่ใช้เป็นหลักฐานรายบุคคล
no-observer control มาจากรอบแรก โดยผลเปรียบเทียบทั้งสี่ boundary ตรงกัน
ตาม `control_reuse.json` การแก้ observer และ replay ดังกล่าวเป็นงานที่ทำเสร็จก่อนการปิดงานนี้

## ค่าราย tick และ anchor

หน่วยอาหารคือสำรับ; normal/volunteer เป็นผู้ eligible ก่อนผลิต ไม่ใช่จำนวน flagged รวม Interval เป็นช่วงที่ tick ใช้ผลิตจริง ไม่ใช้ชื่อฤดู ณ endpoint แทน season mean

| day | interval | season mean | ผู้กิน | demand | normal / volunteer | ผลผลิต | physical deficit | unpaid | final unmet |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 10920 | [10890,10920) | 0.5 | 24 | 720.000000 | 5 / 0 | 296.868465 | 5.659418 | 0 | 3.419232 |
| 10950 | [10920,10950) | 0.5 | 19 | 570.000000 | 1 / 1 | 123.756658 | 435.542889 | 0 | 340.547113 |
| 10980 | [10950,10980) | 1.3 | 17 | 510.000000 | 1 / 10 | 1341.817541 | 0.000000 | 0.000000 | 0.000000 |
| 11010 | [10980,11010) | 1.3 | 17 | 510.000000 | 1 / 3 | 653.109805 | 0.000000 | 0 | 0.000000 |

Anchor 10980 ใช้ผล tick เดิม ไม่ trace ledger เพิ่ม: state ทั้ง Sim, ทุก state-key, RNG, granaries และ raw food_stats ตรงกับ no-observer เดิมทุกค่า Raw unpaid 10950 = −1.4654943925e−14 เป็น floating-point residual ของ offered−bought; ตารางแสดง 0 ด้วย tolerance 1e−9 ไม่ตีความเป็นเครดิต/หนี้ติดลบ Demand = อาหารที่ต้องกินในช่วง tick, physical deficit = demand หลัง household draw ลบ local allocation และ arrivals, unpaid = อาหารที่เสนอขายให้มื้อแต่ซื้อไม่สำเร็จ, final unmet = need−eaten หลัง relief/home/pack ไม่ใช่สิ่งเดียวกัน

## Stage ledger ตามลำดับ production code

แสดงยอด granary ของ place 85 ณแต่ละ stage ตาม food.py ของ frozen source บ้าน draw หลัง production; imports แจกผ่าน sources ไม่ฝาก granary ปลายทางก่อนมื้อ; unsold คืน granary แล้วเติม provisions ภายใน `_feed_place` ก่อนเติม household larder; cap/overflow เกิดก่อน adapt

| stage (ลำดับจริง) | 10920 stock | 10950 stock | 11010 stock |
| --- | --- | --- | --- |
| entry_before_spoil | 53.048086 | 0.000000 | 469.177083 |
| after_natural_spoil | 52.889773 | 0.000000 | 466.380903 |
| after_endowment | 52.889773 | 0.000000 | 466.380903 |
| after_production | 349.758238 | 123.756658 | 1119.490708 |
| after_household_draw | 349.758238 | 123.756658 | 1119.490708 |
| after_local_reservations | 0.000000 | 0.000000 | 609.490708 |
| after_transport | 0.000000 | 0.000000 | 609.490708 |
| after_target_meals_before_unsold_return | 0.000000 | 0.000000 | 609.490708 |
| after_target_unsold_return_before_provisions | 0.000000 | 0.000000 | 609.490708 |
| after_target_provisions | 0.000000 | 0.000000 | 609.490708 |
| after_feeding_all_places | 0.000000 | 0.000000 | 609.490708 |
| after_larder_stocking | 0.000000 | 0.000000 | 609.490708 |
| after_away_accounts | 0.000000 | 0.000000 | 609.490708 |
| after_farmer_pay | 0.000000 | 0.000000 | 609.490708 |
| after_leave_before_broke | 0.000000 | 0.000000 | 609.490708 |
| after_hunger_responses | 0.000000 | 0.000000 | 609.490708 |
| after_cap_before_adapt | 0.000000 | 0.000000 | 463.473958 |
| tick_exit_after_adapt | 0.000000 | 0.000000 | 463.473958 |

Movement ที่ใช้ยืนยันบัญชี (ไม่ย้ายลำดับ stage):

| รายการ | 10920 | 10950 | 11010 |
| --- | --- | --- | --- |
| Opening | 53.048086 | 0.000000 | 469.177083 |
| Natural spoilage | 0.158313 | 0.000000 | 2.796180 |
| Endowment | 0.000000 | 0.000000 | 0.000000 |
| Production | 296.868465 | 123.756658 | 653.109805 |
| Household fed ก่อน local allocation | 0.000000 | 0.000000 | 0.000000 |
| Local withdrawal/reservation | 349.758238 | 123.756658 | 510.000000 |
| Imports gross sent | 403.969356 | 11.856457 | 0 |
| Imports net arrivals | 364.582344 | 10.700452 | 0 |
| Import transport loss | 39.387012 | 1.156005 | 0 |
| Exports gross sent | 0 | 0 | 0 |
| Export loss | 0 | 0 | 0 |
| Local eaten | 716.580768 | 229.452887 | 510.000000 |
| กินจาก pack | 2.240186 | 94.995776 | 0.000000 |
| Unsold return | 0.000000 | -0.000000 | 0.000000 |
| เติม pack/provisions | 0 | 0 | 0 |
| Household larder draw จาก granary | 0.000000 | 0.000000 | 0.000000 |
| Net granary movement ใน hunger responses | 0.000000 | 0.000000 | 0.000000 |
| Overflow | 0.000000 | 0.000000 | 146.016750 |
| Closing food tick | 0.000000 | 0.000000 | 463.473958 |

Exports = 0 ทั้งสาม tick; ไม่มีการเคลื่อน granary ใน farmer pay/leave-before-broke/away accounts ตาม stage snapshots Food tick closing ของ 10950 คือ 0 ส่วน opening ของ 10980 เดิมคือ 13.669928: เป็นคนละ boundary และมี simulation events ระหว่างกัน งานนี้ไม่ได้ trace ประวัติ stock ระหว่าง tick จึงไม่อ้างที่มาของส่วนต่างนั้น Imports loss หักจาก gross sent ก่อนเป็น net arrivals; อย่าหัก loss ซ้ำจาก deficit หรือบวก imports เข้า granary ปลายทางอีกครั้ง

## เหตุที่ deficit เพิ่ม 10920 → 10950

Physical deficit เพิ่ม **429.883471** จาก 5.659418 เป็น 435.542889. ทั้งสอง tick ใช้ช่วง 30 วันและ season multiplier 0.5 แม้ day 10950 มีชื่อฤดู endpoint เป็นใบไม้ผลิ

| องค์ประกอบของ Δdeficit | สำรับ | หลักฐาน |
| --- | --- | --- |
| Demand เปลี่ยน | -150.000000 | 720 → 570 (ผู้กิน 24 → 19) |
| Opening stock ลด | 53.048086 | 53.048086 → 0 |
| Spoilage ลด | -0.158313 | 0.158313 → 0 |
| Production ลด | 173.111806 | 296.868465 → 123.756658 |
| Endowment/household draw | -0.000000 | 0 ทั้งสอง tick |
| Net delivery ลด | 353.881891 | 364.582344 → 10.700452 |
| รวม | 429.883471 | signed accounting decomposition |

Stock local ถูก reserve หมดทั้งสอง tick จึงใช้ decomposition opening−spoilage+endowment+production ได้ตรง จำนวนแรงงานปกติก่อนผลิตลด 5→1; capacity รวมลด 4.803113→1.775144 แม้มีอาสา 989 เพิ่มใน tick หลัง Season mean ไม่ลดเพิ่มในคู่นี้ Winter multiplier 0.5 เป็นบริบทของผลผลิตต่ำ แต่การเพิ่ม deficit ในคู่นี้ไม่ได้มาจาก season multiplier เปลี่ยน

Imports gross sent ลด 403.969356→11.856457 และ net arrivals ลด 364.582344→10.700452; loss ลด 39.387012→1.156005 จึงไม่มีหลักฐานว่า loss ที่เพิ่มเป็นตัวทำให้ deficit เพิ่ม การส่งถึงที่น้อยลงพิสูจน์ได้ แต่ไม่ได้เก็บคลัง/ความต้องการของทุกต้นทางหรือ allocation competition จึงยังตอบไม่ได้ว่าต้นทางขาดผลผลิตหรือถูกแบ่งให้ที่อื่นเท่าไร รายละเอียด edges (src/dest/sent/arrived/hops/loss) อยู่ใน tick_evidence.json ไม่ใช่ controlled causal experiment ของแพตช์

## Tick 11010 หลังการปล่อย 7 คน

ช่วง [10980,11010), season mean 1.3 ผู้ผลิตปกติ cid 978 + อาสา cid 963,2210,3678 รวม 4 คน capacity 3.927171; ผลผลิต **653.109805** หรือ **21.770327/วัน** ตรงกับ output ที่ policy ประเมินสำหรับ workforce ที่เหลือใน anchor เดิม (21.770326835104/วัน × 30) ผู้กิน 17 demand 510, physical deficit/unpaid/final unmet = 0; imports/exports/loss = 0; recruitment/release ใหม่ = 0

Opening 469.177083 − spoilage 2.796180 + production 653.109805 − local take 510 − overflow 146.016750 = closing 463.473958 อาสาที่ปล่อย 7 คนยังไม่กลับมา eligible ในฐานะอาสา (flag=false) แต่ผู้ที่ต้องกินยังอยู่ใน demand ของ tick จริง

Policy ผ่าน shortage, reserves 745.851282 < target 1530, ผ่าน local-full ที่ stock=cap463.473958 แล้วทดสอบถอน cid963: output ก่อน21.770327/วัน หลัง16.966584/วัน < need17 จึงไม่ปล่อยเพิ่ม candidate2210/3678 ไม่ถูกประเมิน output-after เป็น null ไม่มีการไล่รันเพื่อหา branch ที่ต้องการ

10920 ไม่มี eligible helpers จึงไม่ได้ประเมิน shortage release/reserves/local-full/marginal release (null); รับ989หนึ่งคน 10950 มี989หนึ่งคนแต่ deficit435.542889 ทำให้ shortage block; gates ถัดไป null รับเพิ่มสิบคนและหยุดที่3767เพราะ marginal production ต่ำกว่า adult ration ราย checks/ลำดับ actual recruitment/release และก่อน/หลังของราย cid อยู่ใน tick_evidence.json

หนึ่ง tick ที่กินครบยืนยันเฉพาะสถานที่นี้ ช่วงนี้ และ state จริงนี้ ไม่ยืนยันว่าปล่อย 7 คนปลอดภัยทุกฤดู และไม่เป็นหลักฐานควบคุมว่าแพตช์ใดทำให้ผลดีขึ้น

## Purity / closure / artifacts

Observed retry เทียบ no-observer control: full Sim hash, hash ทุก state key, RNG, granaries, raw food_stats ตรงกันที่ step-return 10920/10950/10980/11010 และ endpoint; differences=[] Anchor10950 ตรงรายงาน winter เดิม; anchor10980 ตรงผลเดิมเช่นกัน

Endpoint absolute food gap=4.40384610556e-06, gold gap=6.98491930962e-10, demand closure gap=1.22252458823e-07. Global closures ก่อน/หลังสาม tick และ independent production/stock, reservations, exports, unsold return, provisions, feeding และ supply-partition ผ่าน tolerance (อาหาร/demand1e−4, independent equations1e−6). Stage deltas เป็นการแสดงบัญชี; ใช้ independent equations เพิ่ม ไม่ใช้ telescoping identity เป็นหลักฐานเดี่ยว


## หลักฐานถาวรและ reproduce

- `stages.csv`: stage ledger ครบทั้งสี่ ticks รวม anchor 10980; ยุบ stage ซ้ำเมื่อยอดตรงกัน
- `summary.json`: ค่าราย tick 10920/10950/11010, deficit decomposition และ independent closure checks เดิม
- `tick_evidence.json`: selected ledger, transport edges, workforce snapshots และ policy gates ของทั้งสี่ ticks
- `purity.json`, `purity_evidence.json`: ผลเทียบและค่าจริงทั้ง observe/control พร้อม expected anchors สำหรับตรวจซ้ำแบบอ่านไฟล์
- `manifest.json`, `completed.json`, `control_reuse.json`: revision/runtime/ขอบเขต และ provenance เดิม (paths ใน provenance เป็นตำแหน่งเดิม)
- `worker.py`, `tick_observer.py`, `observer_common.py`: instrumentation เดิมสำหรับ reproduce
- `artifact_hashes.json`: SHA-256 ของไฟล์ถาวรและต้นทางที่คัดเลือก

ไม่รวม production source copies, source.tar, raw observe/control ทั้งชุด, effective-config dump,
progress logs, process logs หรือประวัติรายคนทั้งหมด แหล่งเดิมยังอยู่ใน `out/`
หลักฐาน purity เก็บ state hashes และ raw food stats ที่เปรียบเทียบ ไม่ใช่ save/checkpoint ที่กู้โลกได้
แหล่งเต็ม: `out/volunteer-bounded-diagnostic-95b07ea-seed18-20261002-retry01/`
และ `out/volunteer-tick10980-95b07ea-seed18-20261002/`

คำสั่งนี้เก็บเพื่อ reproduce ภายหลังเท่านั้น **ไม่ได้รันในการปิดงาน** และต้องมีโจทย์ใหม่ก่อนรัน:

```powershell
Set-Location 'D:\Sim Dao'
python tools/food_storage_eval/seed18_world8_place85/reproduce.py out/seed18-reproduce-NEW
```

`reproduce.py` ปฏิเสธ output ที่มีอยู่ ใช้ `git archive` ของ revision ที่ระบุ,
รัน observe/control sequential จาก seed 18 ถึง day 11010 เท่านั้น โดยไม่เขียน save โลก
ตรวจ purity, expected anchors และ endpoint closure จากหลักฐานถาวร
ต้องใช้ Python 3.12.10/runtime เดิมสำหรับ hashes แบบ exact; source hooks ผูกกับ revision นี้
คำสั่งตรวจไฟล์และ purity ที่ไม่รัน simulation:

```powershell
python tools/food_storage_eval/seed18_world8_place85/reproduce.py --verify-only
```

งานแรงงานระยะยาวและ overflow ต้องกำหนดโจทย์ออกแบบแยกต่างหาก การปิดกรณีนี้ไม่เปลี่ยน policy
และไม่เปิดการทดลองฤดูหรือ seed ถัดไปโดยอัตโนมัติ
