# Effort-only diagnostic fixtures — COMPLETED

Frozen source 95b07ea260d19771810e7748eb61fbbb50db2174 · 2 ตุลาคม 2026

ครบ 8 กลุ่ม / 11 subcases / 33 variants ทุกระดับ effort 1.0, 0.75, 0.5 ที่ตรึงก่อนรัน ทุก variant ตรวจซ้ำ 2 ครั้ง ไม่มี parameter search ไม่มี production file edits ไม่ติดตั้งนโยบาย ไม่รันโลก 50 ปี ไม่ commit/push

## นิยามและ fixture assumptions

AST เปลี่ยนเพียง assignment adult capacity ที่ production: adults=sum(real BODY.work_capacity)×effort แล้วใช้ real F(adults+child helpers)×days×season_mean ไม่มีการคูณผลผลิตปลายทางด้วย effort
Child capacity เท่าเดิม; marginal child output อาจเปลี่ยนตาม nonlinear formula และไม่ถือเป็นการเปลี่ยน child labour
อาชีพ/fieldwork/roster/eligibility ไม่ถูกเปลี่ยนโดย effort ไม่มี recruit/release/extra activity หรือค่าแรงอาชีพเดิมแถม ไม่มีการให้เวลาว่างหรือ worker-days benefit
Farm pay ใช้ raw BODY.work_capacity weights ตามกฎเดิม ไม่เปลี่ยนเป็น effort weights; revenue มาจากเงินจริงที่ผู้กิน/ซื้อเสบียงจ่าย ราคาเปลี่ยนตาม stock จริง ดังนั้นรายได้เพิ่มไม่เท่ากับ welfare benefit

ใช้ real food tick, production, season mean, spoil, local reservation, _carry_in, proportional allocation, pricing, _buy/_feed_place/_account, pack purchases, _pay_farmers, _cap_granaries, store_capacity และ food/gold/demand ledgers
Delivery/asks/available/scale คำนวณใหม่ทุก variant จาก supply จริง ไม่ตรึงให้เท่า baseline ไม่มี free-food injection หลังเริ่ม ไม่ override cap หรือ starvation threshold

Fixture shell เป็นกราฟ 3-node star (หรือ isolated site), miniature state กับ real Character objects; ไม่มี households/clans/charity balances กำหนด initial food stocks/endowed และ initial gold capital ชัดใน manifest
ตรึง adaptive recruit/release และ hunger-driven migration/process interruption เหมือนกันทุก baseline/variant เพื่อคง roster/location ตามนิยามการทดลอง จึงไม่ใช่ full production-policy behavior
การตาย/เดินทางของผู้ผลิตเป็น shocks ล่วงหน้าเหมือนกันทุก effort ไม่ใช่ผลประโยชน์จาก effort ต่ำ Death shell ใช้ real food.on_death แต่ไม่มี estate/kin politics เก็บทองบน corpse เพื่อคง gold ledger
ไม่มี world scheduler, body adaptation, nonfarm labor/time allocation, travel engine/arrival progression หรือ household transfers ใช้ travel flag ตาม schedule ไม่จำลองรายได้อื่น
Real starvation threshold 40 วันคงเดิม; starvation outcomes หากเกิดถือเป็นผล diagnostic ไม่ใช่เหตุเพิ่มอาหาร/แก้ cap ในชุดนี้ starved=0

## การตรวจ

- Effort=1 ตรง real original F.tick baseline ภายใต้ fixture shell เดียวกัน ทั้งทุก tick metrics/stock/transport/pay/RNG และ full-state hashes
- ทุก 33 variants deterministic จากการรันซ้ำ 2 ครั้ง; RNG draws เพิ่ม=0 ไม่มีการสุ่ม world initialization
- Food/gold/demand closure gaps สูงสุด 4.40536496e-13/3.63797881e-12/3.69482223e-13; เกณฑ์ <1e-7
- Source/instrumentation before/after hashes ตรงกัน; compile-check scripts ก่อนเริ่ม
- Real relief(worked_for_food) ไม่ได้ถูกอ้างเป็น extra activity benefit; ผลรวมที่เกิดจริง=0.0

## ผลทุก fixture/effort

Totals รวม diagnostic ticks 2 ticks แล้วคืน effort=1 ตาม schedule ที่ตรึง (กลุ่ม 3 มี 1 recovery tick; ที่เหลือ 2) ห้ามตีความ totals ว่าใช้ effort ต่ำตลอดช่วง
all_metrics.csv แยก diagnostic/recovery physical/unmet และ deltas จาก baseline; outcomes.jsonl/records.jsonl เก็บทุก tick, repeated runs, raw stats/stock/roster/capacity/asks/scale/edges/pay/closure/state hashes

| fixture | effort | produced | eaten | overflow | stock final | loss | physical | unpaid | unmet | farm revenue | farm pay |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| single_low_demand_overflow | 1.0000 | 664.9106 | 120.0000 | 421.6369 | 91.2500 | 0.0000 | 0 | 0.0000 | 0.0000 | 15.0000 | 15.0000 |
| single_low_demand_overflow | 0.7500 | 574.2654 | 120.0000 | 331.0481 | 91.2500 | 0.0000 | 0 | 0.0000 | 0.0000 | 15.0000 | 15.0000 |
| single_low_demand_overflow | 0.5000 | 481.7118 | 120.0000 | 238.6244 | 91.2500 | 0.0000 | 0 | 0.0000 | 0.0000 | 15.0000 | 15.0000 |
| normal_volunteer_child | 1.0000 | 533.4292 | 180.0000 | 0.0000 | 296.8876 | 0.0000 | 0 | 0.0000 | 0.0000 | 31.5000 | 31.5000 |
| normal_volunteer_child | 0.7500 | 478.4039 | 180.0000 | 0.0000 | 270.0000 | 0.0000 | 0 | 0.0000 | 0.0000 | 28.7027 | 28.7027 |
| normal_volunteer_child | 0.5000 | 421.0374 | 180.0000 | 0.0000 | 270.0000 | 0.0000 | 0 | 0.0000 | 0.0000 | 22.9907 | 22.9907 |
| no_normal_producer_affordability | 1.0000 | 359.2328 | 210.0000 | 0.0000 | 148.9359 | 0.0000 | 0 | 30.0000 | 30.0000 | 21.0000 | 21.0000 |
| no_normal_producer_affordability | 0.7500 | 303.0491 | 210.0000 | 0.0000 | 92.9199 | 0.0000 | 0 | 30.0000 | 30.0000 | 21.0000 | 21.0000 |
| no_normal_producer_affordability | 0.5000 | 244.4750 | 185.9470 | 0.0000 | 58.4950 | 0.0000 | 27.4891 | 26.5639 | 54.0530 | 18.5947 | 18.5947 |
| shared_source_competing_destinations | 1.0000 | 249.4614 | 276.9127 | 0.0000 | 0.0000 | 12.4691 | 243.0873 | 0.0000 | 243.0873 | 27.6913 | 27.6913 |
| shared_source_competing_destinations | 0.7500 | 219.2463 | 248.2084 | 0.0000 | 0.0000 | 10.9583 | 271.7916 | 0.0000 | 271.7916 | 24.8208 | 24.8208 |
| shared_source_competing_destinations | 0.5000 | 188.3952 | 218.8998 | 0.0000 | 0.0000 | 9.4158 | 301.1002 | 0.0000 | 301.1002 | 21.8900 | 21.8900 |
| winter_entry | 1.0000 | 764.5210 | 960.0000 | 0.0000 | 102.1697 | 0.0000 | 0 | 0.0000 | 0.0000 | 96.0000 | 96.0000 |
| winter_entry | 0.7500 | 693.2110 | 908.9085 | 0.0000 | 82.3884 | 0.0000 | 51.0915 | 0.0000 | 51.0915 | 90.8908 | 90.8908 |
| winter_entry | 0.5000 | 618.8669 | 834.8373 | 0.0000 | 82.3884 | 0.0000 | 125.1627 | 0.0000 | 125.1627 | 83.4837 | 83.4837 |
| empty_stock_import_dependence | 1.0000 | 249.4614 | 238.9884 | 0.0000 | 0.0000 | 10.4731 | 121.0116 | 0.0000 | 121.0116 | 23.8988 | 23.8988 |
| empty_stock_import_dependence | 0.7500 | 219.2463 | 210.2840 | 0.0000 | 0.0000 | 8.9623 | 149.7160 | 0.0000 | 149.7160 | 21.0284 | 21.0284 |
| empty_stock_import_dependence | 0.5000 | 188.3952 | 180.9754 | 0.0000 | 0.0000 | 7.4198 | 179.0246 | 0.0000 | 179.0246 | 18.0975 | 18.0975 |
| delivery_reference | 1.0000 | 249.4614 | 240.0000 | 0.0000 | 58.8453 | 10.5263 | 0 | 0.0000 | 0.0000 | 25.9575 | 25.9575 |
| delivery_reference | 0.7500 | 219.2463 | 240.0000 | 0.0000 | 43.7979 | 10.5263 | 0 | 0.0000 | 0.0000 | 24.4467 | 24.4467 |
| delivery_reference | 0.5000 | 188.3952 | 240.0000 | 0.0000 | 17.5403 | 10.5263 | 0 | 0.0000 | 0.0000 | 24.0000 | 24.0000 |
| delivery_source_scarcity | 1.0000 | 249.4614 | 238.9884 | 0.0000 | 0.0000 | 10.4731 | 1.0116 | 0.0000 | 1.0116 | 23.8988 | 23.8988 |
| delivery_source_scarcity | 0.7500 | 219.2463 | 210.2840 | 0.0000 | 0.0000 | 8.9623 | 29.7160 | 0.0000 | 29.7160 | 21.0284 | 21.0284 |
| delivery_source_scarcity | 0.5000 | 188.3952 | 180.9754 | 0.0000 | 0.0000 | 7.4198 | 59.0246 | 0.0000 | 59.0246 | 18.0975 | 18.0975 |
| delivery_more_competition | 1.0000 | 249.4614 | 314.8371 | 0.0000 | 0.0000 | 14.4651 | 485.1629 | 0.0000 | 485.1629 | 31.4837 | 31.4837 |
| delivery_more_competition | 0.7500 | 219.2463 | 286.1327 | 0.0000 | 0.0000 | 12.9544 | 513.8673 | 0.0000 | 513.8673 | 28.6133 | 28.6133 |
| delivery_more_competition | 0.5000 | 188.3952 | 256.8241 | 0.0000 | 0.0000 | 11.4118 | 543.1759 | 0.0000 | 543.1759 | 25.6824 | 25.6824 |
| producer_death_restore_effort | 1.0000 | 306.8403 | 250.0000 | 0.0000 | 96.2122 | 0.0000 | 0 | 0.0000 | 0.0000 | 25.0000 | 25.0000 |
| producer_death_restore_effort | 0.7500 | 263.6409 | 250.0000 | 0.0000 | 53.2403 | 0.0000 | 0 | 0.0000 | 0.0000 | 25.0000 | 25.0000 |
| producer_death_restore_effort | 0.5000 | 218.9283 | 250.0000 | 0.0000 | 8.7636 | 0.0000 | 0 | 0.0000 | 0.0000 | 25.0000 | 25.0000 |
| producer_travel_restore_effort | 1.0000 | 364.2192 | 260.0000 | 0.0000 | 143.5911 | 0.0000 | 0 | 0.0000 | 20.0000 | 26.0000 | 26.0000 |
| producer_travel_restore_effort | 0.7500 | 321.0198 | 260.0000 | 0.0000 | 100.6192 | 0.0000 | 0 | 0.0000 | 20.0000 | 26.0000 | 26.0000 |
| producer_travel_restore_effort | 0.5000 | 276.3072 | 260.0000 | 0.0000 | 56.1425 | 0.0000 | 0 | 0.0000 | 20.0000 | 26.0000 | 26.0000 |

Physical shortfall เป็นอาหารที่ขาดหลัง allocation; unpaid เป็นมื้อส่วนที่เสนอแต่ซื้อไม่ไหวก่อน relief; unmet เป็นผลหลัง feeding/pack/relief ทั้งสามค่าไม่ใช่ค่าเดียวกัน
กลุ่ม no-normal producer มี hidden eater ไม่มีเงินเพื่อแยก affordability จาก supply เป็น assumption ล่วงหน้า ไม่ใช่ผลของ effort; child capacity อยู่ใน mixed normal+volunteer case

## Recovery หลังคืน effort 1.0

| fixture | effort | step | physical | baseline physical | unmet | baseline unmet | stock gap |
| --- | --- | --- | --- | --- | --- | --- | --- |
| single_low_demand_overflow | 1.0000 | 3 | 0 | 0 | 0.0000 | 0.0000 | 0.0000 |
| single_low_demand_overflow | 1.0000 | 4 | 0 | 0 | 0.0000 | 0.0000 | 0.0000 |
| single_low_demand_overflow | 0.7500 | 3 | 0 | 0 | 0.0000 | 0.0000 | 0.0000 |
| single_low_demand_overflow | 0.7500 | 4 | 0 | 0 | 0.0000 | 0.0000 | 0.0000 |
| single_low_demand_overflow | 0.5000 | 3 | 0 | 0 | 0.0000 | 0.0000 | 0.0000 |
| single_low_demand_overflow | 0.5000 | 4 | 0 | 0 | 0.0000 | 0.0000 | 0.0000 |
| normal_volunteer_child | 1.0000 | 3 | 0 | 0 | 0.0000 | 0.0000 | 0.0000 |
| normal_volunteer_child | 1.0000 | 4 | 0 | 0 | 0.0000 | 0.0000 | 0.0000 |
| normal_volunteer_child | 0.7500 | 3 | 0 | 0 | 0.0000 | 0.0000 | 0.0000 |
| normal_volunteer_child | 0.7500 | 4 | 0 | 0 | 0.0000 | 0.0000 | -26.8876 |
| normal_volunteer_child | 0.5000 | 3 | 0 | 0 | 0.0000 | 0.0000 | -37.9886 |
| normal_volunteer_child | 0.5000 | 4 | 0 | 0 | 0.0000 | 0.0000 | -26.8876 |
| no_normal_producer_affordability | 1.0000 | 3 | 0 | 0 | 10.0000 | 10.0000 | 0.0000 |
| no_normal_producer_affordability | 0.7500 | 3 | 0 | 0 | 10.0000 | 10.0000 | -56.0160 |
| no_normal_producer_affordability | 0.5000 | 3 | 0 | 0 | 10.0000 | 10.0000 | -90.4409 |
| shared_source_competing_destinations | 1.0000 | 3 | 70.2529 | 70.2529 | 70.2529 | 70.2529 | 0.0000 |
| shared_source_competing_destinations | 1.0000 | 4 | 70.2529 | 70.2529 | 70.2529 | 70.2529 | 0.0000 |
| shared_source_competing_destinations | 0.7500 | 3 | 70.2529 | 70.2529 | 70.2529 | 70.2529 | 0.0000 |
| shared_source_competing_destinations | 0.7500 | 4 | 70.2529 | 70.2529 | 70.2529 | 70.2529 | -0.0000 |
| shared_source_competing_destinations | 0.5000 | 3 | 70.2529 | 70.2529 | 70.2529 | 70.2529 | 0.0000 |
| shared_source_competing_destinations | 0.5000 | 4 | 70.2529 | 70.2529 | 70.2529 | 70.2529 | -0.0000 |
| winter_entry | 1.0000 | 3 | 0 | 0 | 0.0000 | 0.0000 | 0.0000 |
| winter_entry | 1.0000 | 4 | 0 | 0 | 0.0000 | 0.0000 | 0.0000 |
| winter_entry | 0.7500 | 3 | 51.0915 | 0 | 51.0915 | 0.0000 | -19.8900 |
| winter_entry | 0.7500 | 4 | 0 | 0 | 0.0000 | 0.0000 | -19.7813 |
| winter_entry | 0.5000 | 3 | 101.8336 | 0 | 101.8336 | 0.0000 | -19.8900 |
| winter_entry | 0.5000 | 4 | 0 | 0 | 0.0000 | 0.0000 | -19.7813 |
| empty_stock_import_dependence | 1.0000 | 3 | 30.2529 | 30.2529 | 30.2529 | 30.2529 | 0.0000 |
| empty_stock_import_dependence | 1.0000 | 4 | 30.2529 | 30.2529 | 30.2529 | 30.2529 | 0.0000 |
| empty_stock_import_dependence | 0.7500 | 3 | 30.2529 | 30.2529 | 30.2529 | 30.2529 | 0.0000 |
| empty_stock_import_dependence | 0.7500 | 4 | 30.2529 | 30.2529 | 30.2529 | 30.2529 | 0.0000 |
| empty_stock_import_dependence | 0.5000 | 3 | 30.2529 | 30.2529 | 30.2529 | 30.2529 | 0.0000 |
| empty_stock_import_dependence | 0.5000 | 4 | 30.2529 | 30.2529 | 30.2529 | 30.2529 | 0.0000 |
| delivery_reference | 1.0000 | 3 | 0 | 0 | 0.0000 | 0.0000 | 0.0000 |
| delivery_reference | 1.0000 | 4 | 0 | 0 | 0.0000 | 0.0000 | 0.0000 |
| delivery_reference | 0.7500 | 3 | 0 | 0 | 0.0000 | 0.0000 | -15.0775 |
| delivery_reference | 0.7500 | 4 | 0 | 0 | 0.0000 | 0.0000 | -15.0475 |
| delivery_reference | 0.5000 | 3 | 0 | 0 | 0.0000 | 0.0000 | -41.3874 |
| delivery_reference | 0.5000 | 4 | 0 | 0 | 0.0000 | 0.0000 | -41.3050 |
| delivery_source_scarcity | 1.0000 | 3 | 0.2529 | 0.2529 | 0.2529 | 0.2529 | 0.0000 |
| delivery_source_scarcity | 1.0000 | 4 | 0.2529 | 0.2529 | 0.2529 | 0.2529 | 0.0000 |
| delivery_source_scarcity | 0.7500 | 3 | 0.2529 | 0.2529 | 0.2529 | 0.2529 | 0.0000 |
| delivery_source_scarcity | 0.7500 | 4 | 0.2529 | 0.2529 | 0.2529 | 0.2529 | 0.0000 |
| delivery_source_scarcity | 0.5000 | 3 | 0.2529 | 0.2529 | 0.2529 | 0.2529 | 0.0000 |
| delivery_source_scarcity | 0.5000 | 4 | 0.2529 | 0.2529 | 0.2529 | 0.2529 | 0.0000 |
| delivery_more_competition | 1.0000 | 3 | 140.2529 | 140.2529 | 140.2529 | 140.2529 | 0.0000 |
| delivery_more_competition | 1.0000 | 4 | 140.2529 | 140.2529 | 140.2529 | 140.2529 | 0.0000 |
| delivery_more_competition | 0.7500 | 3 | 140.2529 | 140.2529 | 140.2529 | 140.2529 | 0.0000 |
| delivery_more_competition | 0.7500 | 4 | 140.2529 | 140.2529 | 140.2529 | 140.2529 | -0.0000 |
| delivery_more_competition | 0.5000 | 3 | 140.2529 | 140.2529 | 140.2529 | 140.2529 | 0.0000 |
| delivery_more_competition | 0.5000 | 4 | 140.2529 | 140.2529 | 140.2529 | 140.2529 | -0.0000 |
| producer_death_restore_effort | 1.0000 | 3 | 0 | 0 | 0.0000 | 0.0000 | 0.0000 |
| producer_death_restore_effort | 1.0000 | 4 | 0 | 0 | 0.0000 | 0.0000 | 0.0000 |
| producer_death_restore_effort | 0.7500 | 3 | 0 | 0 | 0.0000 | 0.0000 | -43.0576 |
| producer_death_restore_effort | 0.7500 | 4 | 0 | 0 | 0.0000 | 0.0000 | -42.9719 |
| producer_death_restore_effort | 0.5000 | 3 | 0 | 0 | 0.0000 | 0.0000 | -87.6231 |
| producer_death_restore_effort | 0.5000 | 4 | 0 | 0 | 0.0000 | 0.0000 | -87.4486 |
| producer_travel_restore_effort | 1.0000 | 3 | 0 | 0 | 10.0000 | 10.0000 | 0.0000 |
| producer_travel_restore_effort | 1.0000 | 4 | 0 | 0 | 0.0000 | 0.0000 | 0.0000 |
| producer_travel_restore_effort | 0.7500 | 3 | 0 | 0 | 10.0000 | 10.0000 | -43.0576 |
| producer_travel_restore_effort | 0.7500 | 4 | 0 | 0 | 0.0000 | 0.0000 | -42.9719 |
| producer_travel_restore_effort | 0.5000 | 3 | 0 | 0 | 10.0000 | 10.0000 | -87.6231 |
| producer_travel_restore_effort | 0.5000 | 4 | 0 | 0 | 0.0000 | 0.0000 | -87.4486 |

Stock gap คำนวณเทียบ tick baseline ที่มี shocks เดียวกัน จึงแยก stock/path dependence จาก capacity ณ tick ปัจจุบันได้ภายใน fixture นี้
พบ 2 recovery rows ที่ shortage/unmet ยังแย่กว่า baseline หลังคืน effort ภายในหน้าต่างที่เก็บ ห้ามอ้างว่าจะฟื้นนอกหน้าต่างหรือฟื้นในหนึ่ง tick เสมอ
Death case คืน effort ไม่คืนผู้ผลิตที่ตาย; travel case คืน effort ที่ tick 3 แต่ผู้เดินทางกลับ tick 4 เป็น lag ที่ระบุล่วงหน้า ไม่ใช่การรับรอง travel scheduling จริง

## Source scarcity เทียบกับการแข่งขัน

กลุ่ม 7 มี reference, initial source stock ลด (80→0) โดย competitors เท่าเดิม และ competitors เพิ่ม (1→15) โดย source initial stock เท่าเดิม ทุก case/rate รายงานทั้งสอง diagnostic ticks และ recovery
delivery_decomposition.csv แสดง realized requested net/arrived/transport loss และ conditional scarcity/competition ตาม observed asks; requested net=arrived+scarcity+competition ตรวจ <1e-7
การเพิ่ม demand เปลี่ยน assigned cap ตาม production rule จริง ไม่ override cap จึงไม่ใช่ pure allocation-only causal test; initial source-stock shock และ competing population เป็น fixture inputs ไม่ใช่การสร้าง/ถอนอาหารระหว่าง variant
ไม่มีการตรึง arrivals ให้เท่า reference การที่ effort ทำ supply ต่ำลงทำให้ requests/scale/arrivals เปลี่ยนจริง

## ข้อค้นพบเฉพาะที่ตรวจได้

- ผู้ผลิตคนเดียว/demand ต่ำ: overflow รวม 421.64 → 331.05 → 238.62 สำรับที่ effort 1.0/0.75/0.5 ตามลำดับ และ unmet เป็น 0 ทุกระดับ ภายใต้ schedule ที่คืน effort หลังสอง ticks ไม่ใช่คำรับรองว่าลดต่อเนื่องได้
- Winter: baseline unmet=0 แต่ระดับ 0.75/0.5 มี unmet รวม 51.09/125.16 สำรับ; tick แรกที่คืน effort=1 ยัง unmet 51.09/101.83 หลัง tick ถัดไปไม่มี unmet แต่ granary stock ยังต่ำกว่า baseline ประมาณ 19.78 สำรับ
- Death/travel: ชุดนี้ buffer พอจน effort ต่ำไม่เพิ่ม unmet จาก baseline แต่หลังคืน effort ยังเหลือ stock debt ประมาณ 42.97/87.45 สำรับที่ระดับเดิม 0.75/0.5 ภายในหน้าต่างนี้ Travel case มี unmet 10 สำรับใน tick ที่คืน effort แต่ยังเดินทางอยู่ เท่ากับ baseline; ไม่ใช่ additional shortage จาก effort ต่ำ และไม่มีการเครดิตการกลับมาจากการลด effort
- Child helper capacity เท่ากับ 0.25 ทุก tick/effort ใน mixed fixture; สูตร nonlinear เปลี่ยน marginal child output ได้แม้ child capacity คงเดิม
- Source-stock shock กับเพิ่ม competitors เป็นสอง exogenous inputs ที่แยกกันจริง แต่ค่าที่ชื่อ conditional competition ใน CSV เป็น residual ของ observed allocation: source stock ที่ลดก็ทำให้ residual นี้เพิ่มได้ ห้ามตีความชื่อคอลัมน์เป็น causal attribution โดยลำพัง

## Guards ที่ข้อมูลนี้ชี้ว่าจำเป็น

มี 11 variants ที่ physical shortfall หรือ unmet แย่กว่า effort=1 (ดู worsening.json) เก็บครบทุกกรณี ไม่เลือกเฉพาะผลดี
- ตรวจ demand/available reserve ตาม interval และ season mean ก่อนลด; overflow headroom ใน tick หนึ่งไม่รับรอง closing reserve/recovery ของ tick ถัดไป
- ไม่ใช้ assigned reserve หรือ imports เดิมเป็นอาหารที่จะมาถึงแน่นอน ต้องครอบคลุม source scarcity, competing requests, hops/loss และ network effects
- ชุมชนไม่มี normal producer ต้องเก็บ effective productive capacity ที่เพียงพอ; roster เดิมไม่ได้แปลว่า capacity เดิม
- คืน effort ก่อน shortage เมื่อรู้ winter/producer availability shocks; effort=1 คืนคนตายไม่ได้และแก้ travel absence ไม่ได้ทันที ต้องรายงาน recovery lag/stock debt แยก
- แยก affordability/unpaid และ final unmet จาก physical supply; farm revenue/pay ที่เปลี่ยนจากราคาไม่ใช่หลักฐานว่าคนกินดีขึ้นหรือเวลาว่างเพิ่ม

## ยังไม่พอออกแบบ controller

ยังไม่ตรึง/ทดสอบ reserve floor, ramp, hysteresis, detection/actuation latency หรือ recovery policy ไม่มีการเลือก threshold ที่ปลอดภัยจาก levels เหล่านี้
ไม่มี full-world endogenous migration/recruitment/death estate, body/time responses, nonfarm wages/activities, multi-seed/network topology coverage หรือ causal counterfactual นอก synthetic state
กราฟ/ประชากร/เงิน/stock/duration เป็น fixture assumptions ผลไม่รับรอง safety ทุกโลก และไม่มี effort ระดับใดได้รับการรับรองว่าปลอดภัย
หยุดหลังรายงาน ไม่เริ่ม controller, fixture tuning หรือ world replay ต่อเอง
