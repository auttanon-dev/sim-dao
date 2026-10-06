# -*- coding: utf-8 -*-
"""นิยามว่าโลก "ถูกแล้ว" — สามแกน ตัวเลขตรงไปตรงมา (pytest -q test_world_coherence.py)

โลก seed 11–15 เดินคนละโปรเซส: seed 11 เดิน 200 ปี (แกน 3 ข้อ 1 ต้องมีประวัติ 200 ปีให้ตรวจ) seed 12–15 เดิน 60 ปี
(ราว 2 วินาทีต่อปีจำลอง — ผลัดกันรันขนาน เวลารวมเท่ากับโลก 200 ปีหนึ่งโลก) ไม่อ่านและไม่เขียน world.save
การตรวจระหว่างทางทำจากฝั่งเทสต์เท่านั้น (ห่อฟังก์ชันใน process ของเทสต์ ไม่แก้โค้ดใน tiandao/)

ที่มาของแต่ละเกณฑ์
แกนที่ 1 — ตัวเลขสมเหตุสมผล (ตรวจหลังรอบโลกทุกรอบ = ทุก WORLD_TICK_DAYS วัน)
  1.1 ประชากรไม่ติดลบ: ตัวนับต่อแดน (World.n_alive, n_mortal) เป็นค่าสะสมที่บวกลบเอง (death.resolve ลบทีละคน)
      จึงติดลบได้ถ้ามีทางนับซ้ำ — ต้องไม่ติดลบทุกรอบ และต้องเท่ากับการนับจริงจาก alive_cids
  1.2 อาหาร: ของที่มีจริงทั้งโลก (เสบียงติดตัวทุกคน + ยุ้งฉาง + ครัวของทุกครัวเรือน, food.total_held นับจากของจริง)
      ต้องเท่ากับ ที่ได้มา − ที่ออกไป ตามบัญชีสาเหตุ (food.ledger_balance) ทุกรอบ และครัวของครัวเรือน/ยุ้งฉางไม่ติดลบ
      ครัวเรือนไม่มีบัญชีแยกของตัวเอง ครัวจึงตรวจผ่านสมดุลรวม (ครัวอยู่ใน total_held) บวกกับไม่ติดลบ
  1.3 ทอง: ทองที่มีจริงต่อชั้น (wages.total_gold นับจากเงินทุกคน กระเป๋า คลัง ซาก ฯลฯ) ลบ ผลรวมบัญชีสาเหตุ
      (gold_flows: ทองที่ออกใหม่ได้เฉพาะจากต้นทางที่ประกาศ เช่น start_gold, mine_output) ต้องเป็นศูนย์ทุกรอบทุกชั้น
  1.4 อย่างน้อย 5 seed ระยะ 60–200 ปี
  เกณฑ์ความคลาดเคลื่อน: อาหาร 1e-6 × ปริมาณที่ไหลผ่าน ทอง 1e-6 ทอง (ทศนิยมสะสม ไม่ใช่ค่าที่ยอมให้หาย)
แกนที่ 2 — ตัวละครมีชีวิตและจำได้
  2.1 ทุกความตายต้องมีสาเหตุ (DeathRecord.cause ไม่ว่าง) และมีเหตุการณ์ใน log วันนั้นที่ผู้ตายเป็นผู้กระทำหรือผู้ถูกกระทำ
      หรือถูกเอ่ยชื่อในรายละเอียดของเหตุการณ์วันนั้น (เช่น "ผู้ไม่ได้กลับออกมา" ของแดนลับต้นกำเนิด — ผู้ใช้ตัดสินว่าพอ)
      — ถ้าไม่มีเหตุการณ์ ผู้อ่านประวัติจะเห็นคนหายไปเฉยๆ ("ตายจากอะไรไม่รู้")
  2.2 ทรัพย์ของผู้ตายไปถึงผู้รับเสมอ: หลังความตาย ผู้ตายไม่ถือทอง ของมีชื่อ (items) วัตถุดิบ และเสบียงเหลือ
      ทองที่ย้ายออกไปไม่หาย ตรวจด้วยบัญชีทองข้อ 1.3 ที่ปิดทุกรอบ
  2.3 ความจำอ้างเหตุการณ์จริง: ทุกรายการใน brain.episodic (วัน ชนิด ผล ข้อความ) ต้องตรงกับเหตุการณ์หนึ่งใน log
      คู่แค้น (rivals) และคู่ครองต้องเป็นคนที่มีอยู่ในรายชื่อ
  2.4 ไม่มีศพที่ไม่มีใครรู้: ทุกความตายถูกบันทึก (DeathRecord) คนที่ยังมีชีวิตที่ยังชี้ผู้ตายเป็นคู่ครองต้องมีข่าวที่กำลังเดินทาง
      ไปหาเขา (news.pending) ไม่มีใครมีผู้ตายเป็นผู้ปกครอง และครัวเรือนไม่มีสมาชิกที่ตายแล้ว (household.check)
แกนที่ 3 — เล่นได้เป็นเรื่อง
  3.1 เหตุการณ์ 200 ปีหลังสุด (seed 11) ต่อกัน: ทุกปีมีเหตุการณ์ และผู้กระทำทุกเหตุการณ์มีชีวิตอยู่ ณ วันนั้น
      และห้ามมีเหตุการณ์ที่ผู้กระทำตายไปแล้วก่อนหน้าในเทิร์นเดียวกัน (sim.step() เดียวกัน — แม้วันเดียวกันจะยอมให้)
      ยกเว้นเหตุการณ์ที่รายงานความตายของผู้นั้นเอง ("สิ้นชีพ" และเหตุการณ์ที่ผลเป็นความตาย เช่น "ล่าอสูร/ตาย")
      (เกิดแล้ว และยังไม่ตายก่อนวันนั้น) — ไม่มีคนตายแล้วยังลงมือ ไม่มีช่วงปีที่เรื่องขาดหาย
  3.2 เหตุการณ์ไม่อ้างสิ่งที่ไม่มี: ผู้กระทำ/ผู้ถูกกระทำ/คนที่อยู่ในฉากเป็น cid ที่มีในรายชื่อ แดนมีอยู่ และสถานที่อยู่ในผังของแดนนั้น
  3.3 ทุกเหตุการณ์มีผู้กระทำ (actor ≥ 0) และมีที่เกิด (place ≥ 0) — ยกเว้นเหตุการณ์ระดับโลกที่ไม่มีผู้กระทำโดยธรรมชาติ
      (ผู้ใช้ตัดสินว่าไม่ต้องมีผู้กระทำ) แต่เหตุการณ์ระดับโลกก็ยังต้องมีที่เกิด
แกนที่ 4 — วงจร (โลกต้องวนเป็นรอบ เล็ก → ใหญ่ → พัง → เริ่มใหม่ และสิ่งที่รอดข้ามรอบต้องปรับตัว — ผู้ใช้กำหนด)
  เดินโลกแยก seed 16 ยาว 400 ปี เก็บ series รายปี (จำนวนคนขั้น 7+ ขั้นสูงสุด ยุคของโลก พลังผนึก แรงกดดันมหาศึก แดนร่ำรวย สายเลือด)
  ไม่ปนกับตัวเลขแกน 1–3 (seed 11–15 เดิม) — 400 ปี ราว 28 นาที (~4.3 วินาทีต่อปี) · ลองลดเป็น 200 ปีแล้ว 4.3 (ก) และ 4.4
  เปลี่ยนจากผ่านเป็นไม่ผ่านเพราะข้อมูลน้อยลง (ส่วนความมั่งคั่ง 8% < 10%, ยุคเสื่อมสายมารเหลือ 59 คน) จึงคง 400 ปี
  4.1 วงจรปิด: จำนวนคนที่มีชีวิตที่อยู่ขั้น 7 ขึ้นไป ไม่นับเผ่าโกลาหล (ระบบสร้างมาบุก ขั้นสูงตั้งแต่เกิด — 17 จาก 37 ตอนเริ่ม) (series รายปี) ต้อง ขึ้นถึงจุดสูง → ลงต่ำกว่าจุดสูงอย่างมีนัยสำคัญ
      (≥ 50% และ ≥ 3 คน) → ขึ้นกลับ ครบอย่างน้อย 2 รอบ และจุดต่ำของทุกรอบต้องยังเหลือคนขั้น 7 ขึ้นไป (> 0 — พังแล้วเริ่มใหม่
      จากผู้รอด ไม่ใช่ล้างโลก) — สื่อว่า "พังแล้วเริ่มใหม่" เกิดจริง ไม่ใช่ไต่ขึ้นเส้นตรง
      ทำไมเลิกวัด "ขั้นสูงสุดของโลก" (ผู้ใช้ตัดสิน): ค่านั้นชนเพดาน REALM_CAP = 9 ตลอดทั้ง 400 ปี และยุคล่มกดขั้นลงแค่
      ERA_PUSHDOWN = 1 ขั้น เกณฑ์เดิม (แกว่ง ≥ 2 ขั้น) จึงผ่านไม่ได้แม้โลกจะวนจรจริง — ตัววัดผิด ไม่ใช่โลกผิด
      จำนวนคนขั้นสูงไม่มีเพดานแบบนั้น จึงเห็นการขึ้น-ลงของทั้งชั้นผู้แข็งแกร่ง (ห้ามแก้ REALM_CAP/ERA_PUSHDOWN เพื่อให้เกณฑ์เดิมผ่าน)
      แยกผลเป็นสองส่วน (ผู้ใช้ตัดสิน: รอบยาว ~250 ปีคือความสมจริง ไม่ลด RECOVER_YEARS = 300 — 2 รอบ = 500 ปีเกินเวลาทดสอบ):
      (ก) กลไกวงจรทำงาน — ผ่าน/ไม่ผ่าน พิสูจน์ทีละชิ้นบนโลกค่าปกติ (ไม่แก้ config) ใช้เวลาไม่กี่นาที:
          คลังฟ้าต่ำกว่า COLLAPSE_RATIO → ยุคล่มจริง · รุ่งเรืองครบ RECOVER_YEARS → โลกเลื่อนชั้นจริง (ขาดหนึ่งปี → ไม่เลื่อน)
          · หลังล่ม ผู้รอดถูกกดขั้นและคนขั้น 7+ ลดจริง · คลังฟื้นแล้วเดินซิมต่อ 10 ปี คนกลับมาข้ามขั้นได้จริง
          บัญชีทองต้องปิดหลังล่ม/เลื่อนชั้น · การบังคับคลังฟ้าและการทอย RECOVER_P = 0 (rng แยกส่งให้ check_world)
          เป็นการตั้งสถานการณ์ในเทสต์เท่านั้น ซิมจริงไม่ถูกแตะ
      (ข) วงจรครบรอบจริงหรือยัง — ยืนยันระยะยาว รายงานตัวเลข (UserWarning ในสรุปของ pytest) ไม่บังคับผ่าน
          ยกเว้นข้อ "รอบที่ครบต้องไม่ล้างโลก" ซึ่งยังบังคับ
  4.2 ธรรมชาติเป็นจังหวะ: เหตุการณ์ระดับโลกแต่ละชนิด (ที่ไม่มีผู้กระทำ ลางมหาศึกโกลาหล ภัยพิบัติตามฤดู) ต้องมีอย่างน้อยหนึ่งชนิด
      ที่ช่วงห่างสม่ำเสมอ (CV < 0.5 — สุ่มแบบปัวซองได้ราว 1) และความรุนแรงเพิ่มตามเวลา (สหสัมพันธ์อันดับ > 0.5)
  4.3 การรบกวนเร่งธรรมชาติ: (ก) วัดว่าการสะสมของมนุษย์ (แดนร่ำรวย) เป็นส่วนสำคัญของแรงกดดันมหาศึก (≥ 10%) และทำให้ลางมาเร็วกว่า
      เวลาอย่างเดียว (ลางถึงลาง = ศึก 3 ปี + พักฟื้น 12 ปี + สะสม 18.2 ปี = 33.2 ปี — ไม่ใช่แค่ช่วงสะสม)
      (ข) ธรรมชาติเร่งตามความเสียหาย (Sim.nature_damage 0..1: ทรัพยากรหมด 0.6 + พลังฟ้าถูกถอน 0.2 + รอยเลือด 0.2 ·
      speedup = 1 + 0.5 × damage คูณ disaster_p การเสื่อมของผนึก และแรงกดดันมหาศึก) — วัดจริงด้วยโลกสองใบ seed 16 เดิน 80 ปี
      ใบหนึ่งรีดคลังวัตถุดิบโลกมนุษย์เหลือ 5% ทุกรอบโลก (ผ่าน eco_harvest บัญชีวัตถุดิบยังปิด) อีกใบไม่แตะ:
      damage ต้องสูงกว่า ภัยตามฤดูถี่ขึ้นและผนึกเสื่อมเร็วขึ้นจริง speedup ไม่เกิน 1.5 และภัยถี่ขึ้นไม่เกิน 50% (+ คลาดสุ่ม 5%)
  4.4 ผู้รอดปรับตัว (ผู้ใช้ตัดสิน: ยุคเสื่อม → สายมนุษย์ทนทาน · ทรัพยากรน้อย → สายมนุษย์ประหยัด · สงคราม → สายสู้เก่งได้เปรียบ
      สายที่ต้องอยู่รอดอ่อนลง · ยุคปกติไม่ไหล · ต้องเห็นผลใน 1–2 รอบแรก):
      (ก) สายเลือดลูกสัมพันธ์กับพ่อแม่ (> 0.5 — ส่งต่อ ไม่ใช่สุ่มใหม่) ในโลกยาว · สายที่ขั้นเฉลี่ยสูงสุดต่อยุคเป็นรายงาน (UserWarning)
      (ก-2) อยู่รอดจริงในโลกยาว: ต่อสภาวะโลกตอนตาย (Sim.blood_state) ตัดสินด้วยสัดส่วนที่รอดถึงวัยชรา (≥ 62 ปี =
          อายุขัยเฉลี่ยปุถุชน 72 − 1 SD) แยกตามสายเลือดหลัก (สายละ ≥ 30 ผู้ตาย) — สายที่อยู่รอดดีที่สุดต้องเปลี่ยนตามสภาวะ และเป็น
          มนุษย์ในยุคเสื่อม/ทรัพยากรน้อย · เลิกใช้ "ขั้นเฉลี่ยสูงสุด" เป็นเกณฑ์ (ผู้ใช้ตัดสิน: อสูรนำเพราะพลังดิบทำให้ขึ้นขั้นเร็ว
          แต่ "ทนทาน" คืออยู่รอดยาวขึ้น ไม่ใช่ขึ้นขั้นสูง) และไม่ใช้อายุเฉลี่ยตอนตาย (ปนการตายจากสงคราม อดอาหาร โรค ที่กลไกยืด
          อายุขัยไม่ได้แตะ — อายุเฉลี่ยตอนตาย 34–40 ปี คนส่วนใหญ่ตายก่อนวัยชรา) — ทั้งสองยังรายงานเป็นข้อมูลประกอบ
      (ก-3) ทรัพยากรน้อยแบบบังคับสถานการณ์ (ชุดเร็ว — รายงาน + สองข้อบังคับ · ผู้ใช้ตัดสิน 2026-10-05): ถามว่า "เมื่อทรัพยากรหมด คนเข้าสู่
          ภาวะข้าวขาดจริงไหม หรือกลไกของโลกดูดซับได้?" แทน "ตายเพราะหิวเพิ่มไหม" — วัดแล้วข้าวลดจริงแต่ไม่มีใครตายเพิ่ม เพราะยุ้งฉาง
          3 เดือน คนลงไร่ และย้ายหาข้าว ซึ่งเป็นกลไกจริงของโลก · บังคับ: ผลผลิตข้าวลดเมื่อสมุนไพรหมด และบัญชีอาหารปิด · รายงาน:
          ความหิวสะสม ย้ายหาข้าว ลงไร่ชดเชย อดตาย และสาเหตุการตาย (เดิมวัดสาเหตุการตาย — ก่อนหน้านั้นวัดรอดถึงวัยชรา)
      (ข) สถานการณ์ 5 แบบ (ปกติ/เสื่อม/ทรัพยากรน้อย/สงคราม/รุ่งเรือง) คู่พ่อแม่ 20 คู่ชุดเดียวกันคลอดผ่าน conceive/deliver จริง
          ผู้ได้เปรียบ = สายที่ลูกได้เพิ่มเทียบยุคปกติ (ยุคปกติยังมีการเปลี่ยนจากกลไกเกิดเดิม: ตัดสาย < 0.05 แล้วปรับสัดส่วน และ
          กลายพันธุ์ที่ตกไปสายสุดท้าย chaos — จึงหักฐานยุคปกติออก) ต้องไม่ใช่สายเดียวกันทุกสถานการณ์ · เสื่อม/ทรัพยากรน้อย = มนุษย์
          · สงคราม = อสูร และมนุษย์ต้องลดลง
      (ค) ผลจริง: ยุคเสื่อม คนเลือดมนุษย์อายุเลยอายุขัยปกติไปครึ่งของส่วนที่ยืดได้ต้องยังรอด (ยุคปกติต้องตาย) ยืดไม่เกิน 10%
          · ทรัพยากรน้อย สำรับที่ต้องการของคนเลือดมนุษย์ ≥ 50% ต้องลด 0–10% และบัญชีอาหารต้องปิดเท่ากับรอบปกติ
  4.5 ไม่มีทางตัน (ผู้ใช้ตัดสิน): ผนึกพังถาวรเมื่อโลกเสื่อมจนไม่มีคนซ่อม = ถูกต้องตามธรรมชาติ เกณฑ์เดิม "ห้ามมีสถานะถาวร"
      จึง fail เสมอในโลกที่เสื่อมจนซ่อมไม่ได้ — เปลี่ยนเป็นวัดว่าโลก "ฟื้นได้ถ้ามีคนพอ":
      ผนึกพังในโลกที่ไม่มีฝ่ายธรรมะ 30 ปี ต้องยังพัง (ไม่ซ่อมจากอากาศ) แล้วใส่ฝ่ายธรรมะขั้น 7 กลับเข้าโลก 5 คน
      30 ปีต่อมาผนึกต้องซ่อมได้จริง (มีเหตุการณ์ "ซ่อมมหาผนึก" ผู้นำอยู่ในคณะ ผนึก > 0 ไม่เกิน 100 ไม่พังแล้ว)
      ส่วนที่ยังบังคับจากของเดิม: พลังฟ้า แรงกดดันมหาศึก จำนวนคนขั้น 7+ ห้ามค้างนิ่ง 100 ปีท้าย (โลกหยุดเดิน)
      ส่วนที่ย้ายเป็นรายงาน: ผนึกพังถาวร ยุคเสื่อมยาว 100 ปีท้าย ไม่มีมหาศึกในช่วงเสื่อม (ผลของโลกที่ตกต่ำนาน ตามที่ผู้ใช้ตัดสิน)
เกณฑ์ที่ไม่ผ่านจะ fail พร้อมจำนวนและตัวอย่าง ไม่มี skip/xfail — ถ้าข้อมูลไม่พอตรวจ ข้อความจะบอกว่าขาดอะไร
"""
import collections
import contextlib
import io
import multiprocessing

import pytest

SEEDS = (11, 12, 13, 14, 15)
LONG_SEED, LONG_YEARS, YEARS = 11, 200, 60
CYCLE_SEED, CYCLE_YEARS = 16, 400      # แกน 4 — โลกแยก ไม่ปนตัวเลขแกน 1–3 (seed 11–15 เหมือนเดิม)
CYCLE_HIGH_REALM = 7                   # 4.1: นับคนที่อยู่ขั้น 7 ขึ้นไป (ผู้ใช้ตัดสิน)
CYCLE_DROP = 0.5                       # 4.1: ลงอย่างมีนัยสำคัญ = ต่ำกว่าจุดสูงล่าสุด ≥ 50% / ขึ้นกลับ = สูงกว่าจุดต่ำจนจุดต่ำเหลือ ≤ 50% ของค่าใหม่
CYCLE_MIN_SWING = 3                    # 4.1: และต่างกันอย่างน้อย 3 คน (กันการแกว่ง 1→0→1 คนนับเป็นวงจร)
MIN_CYCLES = 2
RECLIMB_YEARS = 10                     # 4.1 (ค-2): หลังคลังฟื้น เดินซิมต่อกี่ปีเพื่อดูว่าคนกลับมาข้ามขั้นได้
NATURE_TRIAL_YEARS = 80               # 4.3 (ข): โลกสองใบ (รีดทรัพยากร / ไม่แตะ) เดินกี่ปีเพื่อเทียบจังหวะธรรมชาติ
NATURE_TRIAL_LEFT = 0.05              # 4.3 (ข): โลกที่ถูกรีด เหลือคลังวัตถุดิบเท่านี้ของเพดานหลังทุกรอบโลก
OLD_AGE = 62                           # 4.4: วัยชรา = อายุขัยเฉลี่ยปุถุชน − 1 SD (MORTAL_LIFESPAN_MU 72 − SIGMA 10)
SURVIVAL_FROM = 45                     # 4.4 บังคับสถานการณ์: กลุ่มที่วัดคือคนอายุ 45–61 ตอนเริ่ม (อายุขัยปุถุชนต่ำสุด MORTAL_LIFESPAN_MIN)
WAR_TRIAL_YEARS = 30                   # 4.3 (ก) บังคับสถานการณ์: เดินได้นานสุดกี่ปีเพื่อรอลางมหาศึกแรก
WAR_LOW_HEAVEN = 0.15                  # 4.3 (ก): คลังฟ้าที่ถูกกดไว้ (ต่ำกว่ายุคเสื่อม 0.25 สูงกว่าจุดยุคล่ม 0.12)
SURVIVAL_MIN_DEATHS = 30              # 4.4: สายเลือดต้องมีผู้ตายในสภาวะนั้นอย่างน้อยเท่านี้จึงนำมาเทียบ (กันค่าเฉลี่ยจากไม่กี่คน)
ADAPT_WARMUP_YEARS = 20                # 4.4: เดินโลกก่อนกี่ปีให้มีผู้ใหญ่เลือดผสมพอเป็นพ่อแม่
ADAPT_COUPLES = 20                     # 4.4: คู่พ่อแม่ต่อสถานการณ์ (ชุดเดียวกันทุกสถานการณ์)
ADAPT_MIN_GAIN = 0.002                 # 4.4: สายที่ลูกได้เพิ่มเฉลี่ยเทียบยุคปกติเกินเท่านี้ (0.2%) จึงนับว่าได้เปรียบ (กันเศษทศนิยม)
SEAL_TRIAL_YEARS = 30                # 4.5: ปีที่ให้โลกลองซ่อมผนึก (ไม่มีผู้ซ่อม / มีผู้ซ่อม) — 0.65^30 ≈ 0.00002 ที่จะไม่ซ่อมเลยเพราะดวง
RHYTHM_CV = 0.5                        # 4.2: CV ของช่วงห่าง < 0.5 = เป็นจังหวะ (สุ่มแบบปัวซอง CV ≈ 1)
TREND_RHO = 0.5                        # 4.2: สหสัมพันธ์อันดับของความรุนแรงกับเวลา > 0.5 = รุนแรงขึ้นจริง
FLAT_YEARS = 100                       # 4.5: ค่าที่ควรวนแต่คงที่ตลอด 100 ปีท้าย = ติดสถานะถาวร
EXAMPLES = 5
FOOD_REL_TOL, GOLD_TOL = 1e-6, 1e-6


def _add(bucket, key, example):
    bucket["count"][key] += 1
    if len(bucket["examples"][key]) < EXAMPLES:
        bucket["examples"][key].append(example)


def _walk(seed, years=YEARS):
    """เดินโลกหนึ่ง seed พร้อมตรวจระหว่างทาง — คืน dict ที่ pickle ได้ (ตัวเลขและตัวอย่างสั้นๆ)"""
    from tiandao import config as C
    from tiandao import death as DEATH
    from tiandao import food as F
    from tiandao import household as HH
    from tiandao import news as NEWS
    from tiandao import places as PL
    from tiandao import sim as S
    from tiandao import wages as W

    out = {"seed": seed, "years": years,
           "count": collections.Counter(), "examples": collections.defaultdict(list), "stats": {}}

    with contextlib.redirect_stdout(io.StringIO()):
        sim = S.Sim(seed=seed)
    tiers = sorted({w.tier for w in sim.worlds})

    # แกน 1 — หลังรอบโลกทุกรอบ
    real_tick = sim._world_tick
    checks = [0]

    def world_tick(rng):
        real_tick(rng)
        checks[0] += 1
        day = sim.day
        alive = [sim.cast[c] for c in sim.alive_cids]
        for w in sim.worlds:
            if w.n_alive < 0 or w.n_mortal < 0:
                _add(out, "1.1 negative population", f"day {day} world {w.wid} n_alive {w.n_alive} n_mortal {w.n_mortal}")
        counted = collections.Counter(c.world_id for c in alive)
        if not getattr(sim, "_world_counts_dirty", False):
            for w in sim.worlds:
                if w.n_alive != counted.get(w.wid, 0):
                    _add(out, "1.1 population counter != actual", f"day {day} world {w.wid} counter {w.n_alive} actual {counted.get(w.wid, 0)}")
        held, booked = F.total_held(sim), F.ledger_balance(sim.food_stats)
        flow = sim.food_stats["produced"] + sim.food_stats["endowed"]
        if abs(held - booked) > FOOD_REL_TOL * max(1.0, flow):
            _add(out, "1.2 food ledger open", f"day {day} held {held:.4f} booked {booked:.4f} gap {held - booked:.6f}")
        for spot, v in sim.granary.items():
            if v < -1e-9:
                _add(out, "1.2 negative granary", f"day {day} {spot} {v}")
        for hid, hh in HH._table(sim).items():
            if hh.larder < -1e-9:
                _add(out, "1.2 negative household larder", f"day {day} household {hid} {hh.larder}")
        for t in tiers:
            gap = W.gold_gap(sim, t)
            if abs(gap) > GOLD_TOL:
                _add(out, "1.3 gold ledger open", f"day {day} tier {t} gap {gap:.6f}")

    sim._world_tick = world_tick

    # แกน 2.1/2.2/2.4 — จับทุกความตายตอนเกิด (DeathRecord ถูกย่อทิ้งพร้อมผู้ตายหลัง 30 ปี)
    deaths = []
    real_resolve = DEATH.resolve

    def resolve(sim_, ch, cause, killer=None, natural=False):
        was_alive = ch.alive
        before_records = len(getattr(sim_, "deaths", []))
        real_resolve(sim_, ch, cause, killer, natural)
        if not was_alive or getattr(ch, "is_lord", False):
            return                          # ตายซ้ำไม่นับ / เจ้าโกลาหลสลายไม่ใช่ความตาย (death.resolve P0)
        recs = getattr(sim_, "deaths", [])
        deaths.append(dict(
            seq_at=sim_.seq, step_no=step_no[0],
            cid=ch.cid, day=sim_.day, cause=cause or "", who="beast" if getattr(ch, "is_beast", False) else "person",
            recorded=len(recs) > before_records and recs[-1].cid == ch.cid,
            gold=round(W.gold(sim_, ch), 9), items=len(ch.items),
            mats=sum(v for v in getattr(ch, "mat_stock", {}).values() if v > 0),
            food=round(ch.food or 0.0, 9)))

    DEATH.resolve = resolve

    # เทิร์น = หนึ่ง sim.step() — จดช่วงเลขเหตุการณ์ของแต่ละเทิร์น (3.1: ศพลงมือในเทิร์นเดียวกับที่ตาย)
    step_no, step_first_seq = [0], []
    real_step = sim.step

    def step():
        step_no[0] += 1
        step_first_seq.append(sim.seq + 1)
        return real_step()

    sim.step = step

    with contextlib.redirect_stdout(io.StringIO()):
        while sim.day < years * 365:
            if sim.step() is None:
                break
    out["stats"].update(day=sim.day, checks=checks[0], alive=len(sim.alive_cids), deaths=len(deaths),
                        events=len(sim.log), log_first_day=sim.log[0].day if sim.log else None)
    if checks[0] < years * 365 // C.WORLD_TICK_DAYS // 2:
        _add(out, "1.x too few checks", f"only {checks[0]} world rounds checked in {years} years")
    if sim.day < years * 365:
        _add(out, "1.x world stopped early", f"day {sim.day} < {years * 365} (queue exhausted)")

    events_by_day_cid = collections.defaultdict(set)
    details_by_day = collections.defaultdict(list)
    for e in sim.log:
        events_by_day_cid[e.day].add(e.actor)
        if e.target is not None:
            events_by_day_cid[e.day].add(e.target)
        details_by_day[e.day].extend(str(v) for v in (e.deltas or {}).values())

    # 2.1
    for d in deaths:
        if not d["cause"].strip():
            _add(out, "2.1 death without cause", f"cid {d['cid']} day {d['day']}")
        named = sim.cast[d["cid"]].name
        mentioned = bool(named) and any(named in s for s in details_by_day.get(d["day"], ()))
        if d["cid"] not in events_by_day_cid.get(d["day"], ()) and not mentioned:
            _add(out, f"2.1 death without an event that day ({d['who']})", f"cid {d['cid']} day {d['day']} cause {d['cause'][:40]}")
    # 2.2
    for d in deaths:
        if sim.cast[d["cid"]].alive:
            continue                          # ไปเกิดใหม่ในร่างเดิม (reincarnate) — ไม่ใช่ศพที่ทิ้งทรัพย์
        for key in ("gold", "items", "mats", "food"):
            if d[key] > 1e-9:
                _add(out, f"2.2 corpse still holds {key} ({d['who']})", f"cid {d['cid']} day {d['day']} {key} {d[key]} cause {d['cause'][:30]}")
    # 2.3
    log_keys = {(e.day, e.kind, e.outcome, e.text) for e in sim.log}
    n_mem = 0
    for cid, brain in getattr(sim.brain_manager, "brains", {}).items():
        for m in brain.episodic:
            n_mem += 1
            if (m.day, m.kind, m.outcome, m.text) not in log_keys:
                _add(out, "2.3 memory of an event not in history", f"cid {cid} day {m.day} {m.kind}/{m.outcome}")
    out["stats"]["memories"] = n_mem
    if n_mem == 0:
        _add(out, "2.3 no data", "brain_manager.brains has no episodic memories to check")
    ncast = len(sim.cast)
    for cid in sim.alive_cids:
        ch = sim.cast[cid]
        for r in ch.rivals:
            if not (0 <= r < ncast):
                _add(out, "2.3 rival who never existed", f"cid {cid} rival {r}")
        if ch.spouse is not None and not (0 <= ch.spouse < ncast):
            _add(out, "2.3 spouse who never existed", f"cid {cid} spouse {ch.spouse}")
    # 2.4
    for d in deaths:
        if not d["recorded"]:
            _add(out, "2.4 death not recorded", f"cid {d['cid']} day {d['day']}")
    for cid in sim.alive_cids:
        ch = sim.cast[cid]
        if ch.spouse is not None and 0 <= ch.spouse < ncast and not sim.cast[ch.spouse].alive \
                and not NEWS.pending(sim, ch.spouse, cid):
            _add(out, "2.4 widow never told", f"cid {cid} spouse {ch.spouse} died day {sim.cast[ch.spouse].death_day}")
        g = getattr(ch, "guardian", -1)
        if g is not None and 0 <= g < ncast and not sim.cast[g].alive:
            _add(out, "2.4 guardian is a corpse", f"cid {cid} guardian {g}")
    for problem in HH.check(sim):
        _add(out, "2.4 household problem", problem[:120])

    # 3.1
    # ทุกปีของช่วงที่เดิน (ชุดเต็ม: seed 11 200 ปีหลังสุด · ชุดเร็ว: ทุก seed ตลอด 60 ปี) ต้องมีเหตุการณ์
    start = sim.day - years * 365
    if not sim.log or sim.log[0].day > start + 365:
        _add(out, "3.1 no data", f"history starts day {sim.log[0].day if sim.log else None}, need day {start}")
    years_with = {e.day // 365 for e in sim.log if e.day >= start}
    for y in range(max(0, start // 365), sim.day // 365):
        if y not in years_with:
            _add(out, "3.1 year with no events", f"year {y}")
    import bisect
    died_at = {d["cid"]: d for d in deaths}
    for e in sim.log:
        if not (0 <= e.actor < ncast):
            continue
        d = died_at.get(e.actor)
        # เหตุการณ์ที่ผลคือความตาย (ตาย ประหาร ดับสูญ จบสิ้น — C.BLOODY_OUTCOMES) คือการรายงานความตายของผู้นั้นเอง
        # (emit หลัง kill ใน resolve เดียวกัน เช่น "ล่าอสูร/ตาย" "สิ้นอายุขัย/ตาย") ไม่ใช่ศพลงมือทำเรื่องใหม่
        same_turn = bisect.bisect_right(step_first_seq, e.seq) == d["step_no"] if d is not None else False
        if d is not None and e.kind != "สิ้นชีพ" and e.outcome not in C.BLOODY_OUTCOMES and e.seq > d["seq_at"] and same_turn:
            _add(out, "3.1 actor already died earlier in the same turn",
                 f"seq {e.seq} day {e.day} {e.kind} cid {e.actor} died at seq {d['seq_at']}")
        a = sim.cast[e.actor]
        if a.born_day > e.day:
            _add(out, "3.1 actor not yet born", f"seq {e.seq} day {e.day} cid {e.actor} born {a.born_day} {e.kind}")
        if not a.alive and a.death_day is not None and a.death_day < e.day:
            _add(out, "3.1 dead actor acts", f"seq {e.seq} day {e.day} cid {e.actor} died {a.death_day} {e.kind}")
    # 3.2 / 3.3
    wids = {w.wid: w for w in sim.worlds}
    places_of = {}
    for e in sim.log:
        if e.actor < 0:
            # เหตุการณ์ระดับโลก (มหาผนึกสั่นคลอน ลางมหาศึกโกลาหล ...) emit โดยไม่มีผู้กระทำ (a=None) — ผู้ใช้ตัดสินว่าถูกต้อง
            # ไม่ต้องมีผู้กระทำ จึงไม่นับในข้อนี้ แต่ยังต้องมีที่เกิด (ตรวจด้านล่างเหมือนทุกเหตุการณ์)
            out["stats"]["world_level_events"] = out["stats"].get("world_level_events", 0) + 1
        elif e.actor >= ncast:
            _add(out, "3.2 actor does not exist", f"seq {e.seq} cid {e.actor}")
        if e.target is not None and e.target >= 0 and e.target >= ncast:
            _add(out, "3.2 target does not exist", f"seq {e.seq} cid {e.target}")
        for p in e.present:
            if not (0 <= p < ncast):
                _add(out, "3.2 bystander does not exist", f"seq {e.seq} cid {p}")
        w = wids.get(e.world_id)
        if w is None:
            _add(out, "3.2 world does not exist", f"seq {e.seq} world {e.world_id}")
            continue
        if e.place is None or e.place < 0:
            _add(out, "3.3 event without place", f"seq {e.seq} day {e.day} {e.kind}")
            continue
        if w.place_key not in places_of:
            places_of[w.place_key] = set(PL.places_in(w.place_key))
        if e.place not in places_of[w.place_key]:
            _add(out, "3.2 place not in that world", f"seq {e.seq} day {e.day} {e.kind} place {e.place} world {e.world_id}")
    out["count"] = dict(out["count"])
    out["examples"] = dict(out["examples"])
    return out


def _cycle_walk(seed):
    """แกน 4 — เดินโลกยาว CYCLE_YEARS ปี เก็บ series รายปี (ไม่ใช่แค่สรุป) และเหตุการณ์ธรรมชาติระดับโลกทั้งหมด"""
    from tiandao import config as C
    from tiandao import sim as S
    with contextlib.redirect_stdout(io.StringIO()):
        sim = S.Sim(seed=seed)
    series, born_by_year = [], collections.defaultdict(list)
    seen_cast = len(sim.cast)

    def sample():
        alive = [sim.cast[c] for c in sim.alive_cids]
        people = [c for c in alive if not getattr(c, "is_lord", False) and not getattr(c, "is_beast", False)]
        mortal = [w for w in sim.worlds if w.kind == "mortal"]
        rich = sum(1 for w in mortal if w.n_alive > 0
                   and getattr(w, "resource", 0) >= C.REALM_RESOURCE_MAX * C.CRISIS_WEALTH_THRESHOLD)
        blood = collections.Counter()
        for c in people:
            for k, v in (c.blood or {}).items():
                blood[k] += v
        top = max((c.realm for c in people), default=0)
        series.append(dict(
            year=sim.day // 365, max_realm=top, high=sum(1 for c in people if c.realm >= CYCLE_HIGH_REALM and not c.is_chaos()),at_max=sum(1 for c in people if c.realm == top),
            mean_realm=sum(c.realm for c in people) / max(1, len(people)), alive=len(people),
            heaven0=round(sim.worlds[0].ratio(), 4), era0=sim.worlds[0].state(),
            mara_seal=round(getattr(sim, "mara_seal", 0.0), 3), seal_broken=bool(getattr(sim, "mara_seal_broken", False)),
            pressure=round(getattr(sim, "crisis_pressure", 0.0), 4), rich=rich,
            campaign=bool(getattr(sim, "chaos_campaign", None)), rift0=round(sim.worlds[0].rift, 4),
            blood={k: round(v / max(1, len(people)), 4) for k, v in blood.items()},
            realm_by_blood={k: round(sum(c.realm for c in people if max(c.blood or {"-": 1}, key=(c.blood or {"-": 1}).get) == k)
                                     / max(1, sum(1 for c in people if max(c.blood or {"-": 1}, key=(c.blood or {"-": 1}).get) == k)), 3)
                            for k in C.BLOODS}))

    # 4.4 — อายุที่ได้จริงตอนตาย ต่อสายเลือดหลัก ต่อสภาวะโลกตอนตาย (Sim.blood_state ตัวเดียวกับที่กลไกใช้)
    from tiandao import death as DEATH
    survival = collections.defaultdict(lambda: collections.defaultdict(lambda: [0, 0.0, 0]))
    real_resolve = DEATH.resolve

    def resolve(sim_, ch, cause, killer=None, natural=False):
        if ch.alive and ch.sentient and not ch.is_lord and not getattr(ch, "is_beast", False)                 and not ch.is_chaos() and ch.blood:
            state = sim_.blood_state(sim_.world(ch.world_id))
            row = survival[state][max(ch.blood, key=ch.blood.get)]
            age = ch.age(sim_.day)
            row[0] += 1
            row[1] += age
            row[2] += age >= OLD_AGE
        real_resolve(sim_, ch, cause, killer, natural)

    DEATH.resolve = resolve
    next_year = 0
    with contextlib.redirect_stdout(io.StringIO()):
        while sim.day < CYCLE_YEARS * 365:
            if sim.step() is None:
                break
            if len(sim.cast) > seen_cast:        # คนเกิดใหม่ — จดสายเลือดลูกเทียบพ่อแม่ (4.4)
                for c in sim.cast[seen_cast:]:
                    if c.parents and len(c.parents) == 2 and c.blood:
                        pa, pb = (sim.cast[p] for p in c.parents)
                        born_by_year[sim.day // 365].append(
                            ({k: round(v, 4) for k, v in c.blood.items()},
                             {k: round(((pa.blood or {}).get(k, 0) + (pb.blood or {}).get(k, 0)) / 2, 4) for k in C.BLOODS}))
                seen_cast = len(sim.cast)
            if sim.day >= next_year * 365:
                sample()
                next_year = sim.day // 365 + 1
    natural = [dict(day=e.day, kind=e.kind, outcome=e.outcome,
                    deltas={k: v for k, v in (e.deltas or {}).items() if isinstance(v, (int, float, str))})
               for e in sim.log
               if e.actor < 0 or e.kind in ("ลางมหาศึกโกลาหล", "สิ้นสุดมหาศึกโกลาหล", "ภัยพิบัติตามฤดู")]
    return dict(seed=seed, years=CYCLE_YEARS, day=sim.day, series=series, natural=natural,
                births={y: v for y, v in born_by_year.items()},
                survival={st: {k: tuple(v) for k, v in rows.items()} for st, rows in survival.items()})


class _Always:
    """rng ที่ทอยออก 0.0 เสมอ — ใช้กับ check_world เพื่อพิสูจน์ว่า "ถ้าเงื่อนไขครบ" กลไกเลื่อนชั้นทำงาน
    (RECOVER_P เป็นโอกาส ไม่ใช่เงื่อนไข) ไม่ได้ส่งเข้าซิม ซิมยังใช้ rng ของตัวเองทุกที่"""
    def random(self):
        return 0.0


def _gold_gaps(sim, W):
    return {t: round(W.gold_gap(sim, t), 6) for t in sorted({w.tier for w in sim.worlds})}


def _cycle_mechanism(seed=CYCLE_SEED):
    """แกน 4.1 (ก) และ 4.5 — พิสูจน์ "กลไกที่ทำให้เกิดรอบ" ทีละชิ้นบนโลกค่าปกติ (ไม่แก้ config) โดยไม่ต้องรอ 500 ปี
    คืนตัวเลขที่วัดได้ ให้เทสต์ย่อยตัดสินผ่าน/ไม่ผ่าน และให้ 4.1 (ข) ใช้ประกอบรายงาน"""
    from tiandao import config as C
    from tiandao import rules as R
    from tiandao import sim as S
    from tiandao import wages as W
    out = {}
    with contextlib.redirect_stdout(io.StringIO()):
        # (ก) คลังฟ้าต่ำกว่า COLLAPSE_RATIO → ยุคล่มจริง  (ค-1) ผู้รอดถูกกดขั้นลง ERA_PUSHDOWN
        sim = S.Sim(seed=seed)
        w = sim.worlds[0]
        w.heaven = w.cap() * C.COLLAPSE_RATIO * 0.5
        before = {c.cid: c.realm for c in sim.living_in(w.wid) if not c.is_lord}
        era0, gold0 = w.era, _gold_gaps(sim, W)
        notes = R.check_world(sim, w, sim.rng)
        survivors = [c for c in sim.living_in(w.wid) if c.cid in before]
        out["collapse"] = dict(
            world=w.name, fired=notes is not None, era=(era0, w.era), died=len(notes or []), people=len(before),
            pushed=sum(1 for c in survivors if c.realm == max(0, before[c.cid] - C.ERA_PUSHDOWN)),
            survivors=len(survivors), not_pushed=[(c.cid, before[c.cid], c.realm) for c in survivors
                                                  if c.realm != max(0, before[c.cid] - C.ERA_PUSHDOWN)][:5],
            # โลกมนุษย์ตอนเริ่มไม่มีคนขั้น 7+ (มีแต่เผ่าโกลาหล) จึงวัดชั้นที่ลดจากผลรวมขั้นของผู้รอด (ก่อน, หลัง)
            realm_sum=(sum(before[c.cid] for c in survivors), sum(c.realm for c in survivors)),
            gold=(gold0, _gold_gaps(sim, W)))
        # (ค-2) หลังฟื้น (คลังกลับมาเต็ม) คนต้องกลับมาข้ามขั้นได้จริง — เดินซิมด้วยกติกาปกติต่อ RECLIMB_YEARS ปี
        w.heaven = w.cap() * C.RECOVER_RATIO
        start_day, seq0 = sim.day, len(sim.log)
        while sim.day < start_day + RECLIMB_YEARS * 365:
            if sim.step() is None:
                break
        climbed = [e for e in sim.log[seq0:] if e.kind == "ข้ามขั้น" and e.outcome == "ผ่าน" and e.world_id == w.wid]
        out["reclimb"] = dict(years=RECLIMB_YEARS, breaks=len(climbed),
                              high=sum(1 for c in sim.living_in(w.wid) if c.realm >= CYCLE_HIGH_REALM))

        # (ข) รุ่งเรือง (ratio ≥ RECOVER_RATIO) ครบ RECOVER_YEARS → โลกเลื่อนชั้นจริง / ขาดไปปีเดียว → ไม่เลื่อน
        rises = {}
        for held in (C.RECOVER_YEARS - 1, C.RECOVER_YEARS):
            sim = S.Sim(seed=seed)
            w = sim.worlds[0]
            w.heaven = w.cap()
            w.flourish_day = sim.day - held * 365
            tier0, era0, gold0 = w.tier, w.era, _gold_gaps(sim, W)
            R.check_world(sim, w, _Always())
            rises[held] = dict(tier=(tier0, w.tier), era=(era0, w.era), gold=(gold0, _gold_gaps(sim, W)),
                               heaven_le_cap=w.heaven <= w.cap() + 1e-9)
        out["rise"] = rises

        # 4.5 — ผนึกพังในโลกที่ไม่มีผู้ซ่อม แล้วใส่ฝ่ายธรรมะขั้นสูงกลับเข้าโลก ผนึกต้องซ่อมได้จริง (ไม่ใช่ทางตัน)
        sim = S.Sim(seed=seed)
        w = sim.worlds[0]
        sim.mara_seal, sim.mara_seal_broken, sim.mara_seal_notified_weak = 0.0, True, True
        for c in sim.living_in(w.wid):                    # ไม่มีใครเป็นฝ่ายธรรมะ = โลกที่เสื่อมจนไม่เหลือผู้ปกป้อง
            c.moral = min(c.moral, C.MARA_SEAL_REPAIR_MORAL - 1)

        def years_of_ticks(n):
            for _ in range(n):
                sim.day += 365
                sim._mara_seal_tick(sim.rng)

        years_of_ticks(SEAL_TRIAL_YEARS)
        empty = dict(seal=round(sim.mara_seal, 3), broken=sim.mara_seal_broken)
        crew = sorted((c for c in sim.living_in(w.wid) if not c.is_lord and not c.is_chaos() and not c.hidden),
                      key=lambda c: (-c.realm, c.cid))[:C.MARA_SEAL_REPAIR_CREW]
        for c in crew:
            c.moral = max(c.moral, C.MARA_SEAL_REPAIR_MORAL * 2)
            c.realm = max(c.realm, CYCLE_HIGH_REALM)
        seq0 = len(sim.log)
        years_of_ticks(SEAL_TRIAL_YEARS)
        fixes = [e for e in sim.log[seq0:] if e.kind == "ซ่อมมหาผนึก"]
        out["seal"] = dict(empty=empty, crew=len(crew), repairs=len(fixes),
                           seal=round(sim.mara_seal, 3), broken=sim.mara_seal_broken,
                           leaders_in_crew=all(e.actor in {c.cid for c in crew} for e in fixes),
                           capped=sim.mara_seal <= C.MARA_SEAL_INITIAL)
    return out


def _nature_trial(destroy, seed=CYCLE_SEED, years=None):
    """แกน 4.3 (ข) — โลกสองใบ seed เดียวกัน ใบหนึ่งถูกรีดทรัพยากรหนัก (ทุกรอบโลกเก็บคลังวัตถุดิบของโลกมนุษย์ทุกใบ
    ให้เหลือ NATURE_TRIAL_LEFT ผ่าน eco_harvest จริง บัญชีวัตถุดิบยังปิด) อีกใบไม่แตะ — วัดจังหวะธรรมชาติที่เกิดจริง"""
    from tiandao import sim as S
    years = years or NATURE_TRIAL_YEARS
    with contextlib.redirect_stdout(io.StringIO()):
        sim = S.Sim(seed=seed)
        mortal = [w for w in sim.worlds if w.kind == "mortal"]
        real_tick, samples = sim._world_tick, []

        def world_tick(rng):
            if destroy:
                for k in [k for k in sim.place_stock if any(k[0] == w.wid for w in mortal)]:
                    excess = sim.place_stock[k] - NATURE_TRIAL_LEFT * _eco_cap(k)
                    if excess > 0:
                        sim.eco_harvest(k[0], k[1], excess, kind=k[2])
            real_tick(rng)
            samples.append((sim.nature_damage(sim.worlds[0]),
                            sum(sim.nature_speedup(w) for w in mortal) / len(mortal)))

        sim._world_tick = world_tick
        seal0 = sim.mara_seal
        while sim.day < years * 365:
            if sim.step() is None:
                break
    dis = sorted(e.day for e in sim.log if e.kind == "ภัยพิบัติตามฤดู")
    omens = [e.day for e in sim.log if e.kind == "ลางมหาศึกโกลาหล"]
    stats = getattr(sim, "material_stats", {})
    held = sum(sim.place_stock.values())
    flows = stats.get("genesis", 0) + stats.get("regrown", 0) + stats.get("seeded", 0) \
        - stats.get("harvested", 0) - stats.get("disaster", 0)
    return dict(destroy=destroy, years=sim.day / 365, disasters=len(dis),
                disaster_gap=(dis[-1] - dis[0]) / 365 / max(1, len(dis) - 1) if len(dis) > 1 else None,
                seal_loss_per_year=(seal0 - sim.mara_seal) / (sim.day / 365),
                seal_broken=sim.mara_seal_broken, omens=[round(d / 365, 1) for d in omens],
                damage=sum(d for d, _ in samples) / max(1, len(samples)),
                speedup=sum(s for _, s in samples) / max(1, len(samples)),
                speedup_max=max((s for _, s in samples), default=1.0),
                material_gap=held - flows)


ADAPT_STATES = ("ยุคปกติ", "ยุคเสื่อม", "ทรัพยากรน้อย", "สงคราม", "ยุครุ่งเรือง")


def _force_state(sim, w, state):
    """ตั้งสถานการณ์ของแดนในเทสต์ (ไม่ใช่ในซิมจริง): คลังฟ้า คลังวัตถุดิบ และมหาศึก ตามสภาวะที่ต้องการ"""
    from tiandao import config as C
    ratio = {"ยุคเสื่อม": C.DECLINE_RATIO / 2, "ยุครุ่งเรือง": (C.FLOURISH_RATIO + 1) / 2}.get(
        state, (C.DECLINE_RATIO + C.FLOURISH_RATIO) / 2)
    w.heaven = w.cap() * ratio
    for k in [k for k in sim.place_stock if k[0] == w.wid]:
        sim.place_stock[k] = C.ECO_KINDS[k[2]][0] * (0.1 if state == "ทรัพยากรน้อย" else 1.0)
    sim._eco_dirty()                      # เขียน place_stock ตรงๆ ในเทสต์ — ล้างแคช eco_mean แบบเดียวกับซิม
    sim.chaos_campaign = {"waves": 0, "next_day": sim.day + 10 ** 6} if state == "สงคราม" else None


def _adaptation_trial(seed=CYCLE_SEED):
    """แกน 4.4 — สถานการณ์ 5 แบบ คู่พ่อแม่ชุดเดียวกันคลอดลูกในแต่ละแบบ (ผ่าน conceive/deliver จริง) แล้ววัดว่าสายไหน
    ได้เพิ่มในลูกเทียบค่าเฉลี่ยพ่อแม่ (ผู้ได้เปรียบของสถานการณ์นั้น) · และวัดผลจริงของอายุขัย (ยุคเสื่อม) และอาหาร (ทรัพยากรน้อย)"""
    import copy
    from tiandao import config as C
    from tiandao import food as F
    from tiandao import rules as R
    from tiandao import sim as S
    out = {"drift": {}, "leader": {}}
    with contextlib.redirect_stdout(io.StringIO()):
        base = S.Sim(seed=seed)
        while base.day < ADAPT_WARMUP_YEARS * 365:      # ให้มีผู้ใหญ่เลือดผสมพอเป็นพ่อแม่
            base.step()
        for state in ADAPT_STATES:
            sim = copy.deepcopy(base)
            w = sim.worlds[0]
            _force_state(sim, w, state)
            assert sim.blood_state(w) == state, (state, sim.blood_state(w))
            adults = [c for c in sim.living_in(w.wid) if c.age(sim.day) >= 18 and not c.is_chaos()
                      and c.pregnancy is None and len([k for k, v in c.blood.items() if v > 0]) >= 2]
            moms = sorted((c for c in adults if c.gender == "หญิง"), key=lambda c: c.cid)[:ADAPT_COUPLES]
            dads = sorted((c for c in adults if c.gender == "ชาย"), key=lambda c: c.cid)[:ADAPT_COUPLES]
            gain = collections.Counter()
            n = 0
            for mom, dad in zip(moms, dads):
                parent = {k: (mom.blood.get(k, 0) + dad.blood.get(k, 0)) / 2 for k in C.BLOODS}
                sim.conceive(mom, dad, dad)
                before = len(sim.cast)
                sim.deliver(mom)
                child = sim.cast[before]
                for k in C.BLOODS:
                    gain[k] += child.blood.get(k, 0.0) - parent[k]
                n += 1
            out["drift"][state] = {k: round(v / max(1, n), 4) for k, v in gain.items()}
            out.setdefault("births", {})[state] = n
        # ผู้ได้เปรียบ "เพราะสภาวะ" = ส่วนที่ลูกได้เพิ่มเทียบยุคปกติ (ยุคปกติไม่ไหลตามที่ผู้ใช้ตัดสิน — การเปลี่ยนที่ยังเห็นในยุคปกติ
        # มาจากกลไกเกิดเดิม: ตัดสายที่ต่ำกว่า 0.05 แล้วปรับสัดส่วน และกลายพันธุ์ที่ตกไปสายสุดท้าย (chaos) เท่านั้น)
        calm = out["drift"]["ยุคปกติ"]
        out["vs_normal"] = {st: {k: round(v - calm.get(k, 0.0), 4) for k, v in d.items()}
                            for st, d in out["drift"].items() if st != "ยุคปกติ"}
        for st, d in out["vs_normal"].items():
            top = max(d, key=d.get)
            out["leader"][st] = top if d[top] > ADAPT_MIN_GAIN else "ไม่มีสายได้เปรียบ"

        # อายุขัย: คนเลือดมนุษย์มากที่สุดในโลกมนุษย์ อายุเลยอายุขัยปกติไปครึ่งทางของส่วนที่ยืดได้ — ยุคเสื่อมต้องรอด ยุคปกติต้องตาย
        life = {}
        for state in ("ยุคปกติ", "ยุคเสื่อม"):
            sim = copy.deepcopy(base)
            w = sim.worlds[0]
            _force_state(sim, w, state)
            ch = max((c for c in sim.living_in(w.wid) if not c.is_lord and c.age(sim.day) >= 14),
                     key=lambda c: (c.blood.get("human", 0), -c.cid))
            ch.items = [i for i in ch.items if getattr(sim.items.get(i), "lifespan_bonus", 0) <= 0]   # ไม่ให้ยาต่ออายุปน
            extra = ch.lifespan() * C.HUMAN_DECLINE_LIFESPAN * ch.blood.get("human", 0) / 2
            ch.born_day = sim.day - int((ch.lifespan() + extra) * 365)
            R.age_and_decay(sim, ch, w, 1, sim.rng)
            life[state] = dict(alive=ch.alive, human=round(ch.blood.get("human", 0), 3),
                               lifespan=ch.lifespan(), effective=round(R.lifespan_in(ch, w), 2),
                               age=round(ch.age(sim.day), 2))
        out["life"] = life

        # อาหาร: รอบอาหารเดียวกันในแดนทรัพยากรปกติ vs น้อย — สำรับที่ต้องการของคนเลือดมนุษย์ต้องลด บัญชีต้องปิด
        food = {}
        for state in ("ยุคปกติ", "ทรัพยากรน้อย"):
            sim = copy.deepcopy(base)
            w = sim.worlds[0]
            _force_state(sim, w, state)
            F.tick(sim, 30)
            humans = [c for c in sim.living_in(w.wid) if F.eats(c) and c.blood.get("human", 0) >= 0.5]
            food[state] = dict(humans=len(humans),
                               need=round(sum(F.ration(c, sim.day) for c in humans), 4),
                               per_cid={c.cid: F.ration(c, sim.day) for c in humans},
                               gap=F.total_held(sim) - F.ledger_balance(sim.food_stats))
        out["food"] = food
    return out


def _hold_state(sim, state):
    """คงสถานการณ์ของแดนมนุษย์ทุกใบไว้ทุกรอบโลก (โค้ดฝั่งเทสต์เท่านั้น): คลังฟ้าตามยุค · ทรัพยากรน้อย = เก็บคลังวัตถุดิบ
    ลงเหลือ 10% ผ่าน eco_harvest (บัญชีวัตถุดิบยังปิด) · สงคราม = มหาศึกค้างอยู่ (นัดคลื่นไว้ไกล จึงไม่ถล่มจริง)"""
    from tiandao import config as C
    ratio = {"ยุคเสื่อม": C.DECLINE_RATIO / 2, "ยุครุ่งเรือง": (C.FLOURISH_RATIO + 1) / 2}.get(
        state, (C.DECLINE_RATIO + C.FLOURISH_RATIO) / 2)
    mortal = [w for w in sim.worlds if w.kind == "mortal"]
    for w in mortal:
        w.heaven = w.cap() * ratio
    if state == "ทรัพยากรน้อย":
        for k in [k for k in sim.place_stock if any(k[0] == w.wid for w in mortal)]:
            excess = sim.place_stock[k] - 0.1 * C.ECO_KINDS[k[2]][0]
            if excess > 0:
                sim.eco_harvest(k[0], k[1], excess, kind=k[2])
    sim.chaos_campaign = {"waves": 0, "next_day": sim.day + 10 ** 6} if state == "สงคราม" else None


def _war_trial(force_low, seed=CYCLE_SEED):
    """แกน 4.3 (ก) บังคับสถานการณ์ — โลกสองใบ seed เดียวกัน ใบหนึ่งคลังฟ้าโลกมนุษย์ถูกกดไว้ที่ WAR_LOW_HEAVEN ของเพดานทุกรอบโลก
    (ต่ำกว่ายุคเสื่อม สูงกว่าจุดยุคล่ม) อีกใบไม่แตะ — วัดว่าลางมหาศึกโกลาหลมาเร็วขึ้นจริงหรือไม่"""
    from tiandao import sim as S
    with contextlib.redirect_stdout(io.StringIO()):
        sim = S.Sim(seed=seed)
        real_tick, samples = sim._world_tick, []

        def world_tick(rng):
            if force_low:
                w = sim.worlds[0]
                w.heaven = min(w.heaven, w.cap() * WAR_LOW_HEAVEN)
            real_tick(rng)
            samples.append((sim.day, getattr(sim, "crisis_pressure", 0.0), sim.nature_speedup(sim.worlds[0])))

        sim._world_tick = world_tick
        omen = None
        while sim.day < WAR_TRIAL_YEARS * 365 and omen is None:
            if sim.step() is None:
                break
            omen = next((e.day for e in sim.log[-5:] if e.kind == "ลางมหาศึกโกลาหล"), None)
    pre = [s for s in samples if omen is None or s[0] < omen]
    return dict(force_low=force_low, omen_day=omen, samples=[(d, round(p, 4), round(v, 4)) for d, p, v in samples],
                speedup=sum(v for _, _, v in pre) / max(1, len(pre)))


def _survival_trials(seed=CYCLE_SEED):
    """เดินโลกก่อน ADAPT_WARMUP_YEARS ปีครั้งเดียว แล้วสำเนาไปวัดทุกสถานการณ์ (เดิมเดินอุ่นเครื่องซ้ำทุกสถานการณ์ 80 ปีจำลองเปล่าๆ)"""
    import copy
    from tiandao import sim as S
    with contextlib.redirect_stdout(io.StringIO()):
        base = S.Sim(seed=seed)
        while base.day < ADAPT_WARMUP_YEARS * 365:
            base.step()
    return [_survival_trial(st, copy.deepcopy(base)) for st in ADAPT_STATES]


def _survival_trial(state, sim):
    """แกน 4.4 บังคับสถานการณ์ — จากโลกที่เดินมาแล้ว ADAPT_WARMUP_YEARS ปี (`sim` สำเนา) คงสถานการณ์ `state` ไว้ทุกรอบโลก
    กลุ่มที่วัด = คนในแดนมนุษย์ทุกใบ อายุ SURVIVAL_FROM–(OLD_AGE − 1) ตอนเริ่ม (ไม่นับเผ่าโกลาหล/เจ้าโกลาหล/สัตว์)
    เดินจนทุกคนในกลุ่มถึง OLD_AGE หรือตายก่อน — คืน {สายหลัก: (จำนวนคน, จำนวนที่รอดถึงวัยชรา)}"""
    with contextlib.redirect_stdout(io.StringIO()):
        mortal = {w.wid for w in sim.worlds if w.kind == "mortal"}
        from tiandao import config as C
        from tiandao import food as F
        ages = [c for c in sim.living() if c.world_id in mortal and c.sentient and not c.is_lord
                and not getattr(c, "is_beast", False) and not c.is_chaos() and c.blood
                and SURVIVAL_FROM <= c.age(sim.day) < OLD_AGE]
        # เทียบเฉพาะคนที่กินข้าวจริงตอนเริ่ม (food.eats) — ผู้ใช้ตัดสิน: กลไกประหยัด (HUMAN_SCARCE_FRUGAL ลดสำรับ) มีผลกับคนกินเท่านั้น
        # คนที่ไม่กินข้าว (วิญญาณบริสุทธิ์ หรือขั้นงดอาหาร FOOD_BIGU_REALM ขึ้นไป) ความหิวไม่ถึงตัวเลย จึงไม่นำมาเทียบ แต่นับรายงาน
        cohort = [c for c in ages if F.eats(c)]
        no_food = collections.Counter()
        why = collections.Counter()
        for c in ages:
            if not F.eats(c):
                no_food[max(c.blood, key=c.blood.get)] += 1
                why["วิญญาณบริสุทธิ์" if getattr(c, "is_spirit", False) else
                    f"ขั้น ≥ {C.FOOD_BIGU_REALM} (งดอาหาร)" if c.realm >= C.FOOD_BIGU_REALM else "อื่นๆ"] += 1
        line = {c.cid: max(c.blood, key=c.blood.get) for c in cohort}
        reached = set()
        real_tick = sim._world_tick
        # 4.4 สาเหตุการตาย (ผู้ใช้ตัดสิน): ทุกความตายในแดนมนุษย์ระหว่างช่วงบังคับ ทุกอายุ ทั้งคนกินและไม่กินข้าว
        from tiandao import death as DEATH
        causes = collections.defaultdict(collections.Counter)
        no_food_dead = collections.Counter()
        real_resolve = DEATH.resolve

        def resolve(sim_, ch, cause, killer=None, natural=False):
            if ch.alive and ch.world_id in mortal and ch.sentient and not ch.is_lord \
                    and not getattr(ch, "is_beast", False) and not ch.is_chaos() and ch.blood:
                blood = max(ch.blood, key=ch.blood.get)
                causes[blood][_death_kind(cause, killer)] += 1
                no_food_dead[blood] += not F.eats(ch)
            real_resolve(sim_, ch, cause, killer, natural)

        DEATH.resolve = resolve

        def world_tick(rng):
            _hold_state(sim, state)
            real_tick(rng)
            for c in cohort:
                if c.alive and c.age(sim.day) >= OLD_AGE:
                    reached.add(c.cid)

        sim._world_tick = world_tick
        _hold_state(sim, state)
        food0 = dict(sim.food_stats)
        end = sim.day + (OLD_AGE - SURVIVAL_FROM + 1) * 365
        while sim.day < end and any(c.alive and c.cid not in reached for c in cohort):
            if sim.step() is None:
                break
        state_seen = sim.blood_state(sim.worlds[0])
        # 4.4 ทรัพยากรน้อย — ความหิวถูกดูดซับอย่างไร: ส่วนต่างของบัญชีอาหารเดิม (food.STAT_KEYS) ระหว่างช่วงบังคับ
        food_delta = {k: round(sim.food_stats.get(k, 0) - food0.get(k, 0), 3)
                      for k in ("produced", "required", "unmet", "migrated", "took_up_farming", "left_farming",
                                "starved", "seclusion_cut")}
        food_gap = F.total_held(sim) - F.ledger_balance(sim.food_stats)
    out = collections.defaultdict(lambda: [0, 0])
    for c in cohort:
        out[line[c.cid]][0] += 1
        out[line[c.cid]][1] += c.cid in reached
    return dict(state=state, state_seen=state_seen, rows={k: tuple(v) for k, v in out.items()},
                no_food=dict(no_food), no_food_why=dict(why),
                causes={k: dict(v) for k, v in causes.items()}, no_food_dead=dict(no_food_dead),
                food=food_delta, food_gap=food_gap,
                years=round((sim.day / 365) - ADAPT_WARMUP_YEARS, 1))


DEATH_KINDS = ("อดอยาก/ร่างกาย", "ถูกฆ่า", "อายุ", "อื่นๆ")
_HUNGER_WORDS = ("อดอาหาร", "อดตาย", "ร่างเย็นจน", "ร่างร้อนจน")       # ไม่มีสาเหตุ "โรค" ในโค้ดเลย — ร่างกายล้มเพราะหิว/ร้อน/หนาว
_KILLED_WORDS = ("สังหาร", "ประหาร", "สงคราม", "บาดแผล", "เลือดไหล", "ล่าอสูร", "อสูรบุก", "สิ้นชีพในการต่อ",
                 "สละชีพในศึก", "กินเป็นอาหาร", "ล่าเอาแก่น", "ทรยศ")


def _death_kind(cause, killer):
    """หมวดของความตายจาก death_cause (และ killer) ที่ DEATH.resolve ได้รับ"""
    cause = cause or ""
    if any(w in cause for w in _HUNGER_WORDS):
        return "อดอยาก/ร่างกาย"
    if cause.startswith("สิ้นอายุขัย"):
        return "อายุ"
    if killer is not None or cause.startswith("ถูก") or any(w in cause for w in _KILLED_WORDS):
        return "ถูกฆ่า"
    return "อื่นๆ"


def _eco_cap(key):
    from tiandao import config as C
    return C.ECO_KINDS[key[2]][0]


# ------------------------------------------------------------------ สองชุด (pytest.ini: marker longrun)
# ชุดเร็ว (ค่าตั้ง `pytest -q -n 4`): เฉพาะเกณฑ์แกน 4 ที่บังคับสถานการณ์ได้ (4.1 ก, 4.3 ก/ข, 4.4, 4.5 ซ่อมผนึก)
# ชุดเต็ม (`pytest -q -n 4 -m "longrun or not longrun"`): + เกณฑ์ที่ต้องเดินโลก (ชื่อเทสต์/พารามิเตอร์มี longrun) — แกน 1–3 บน
#   5 seed × 60 ปี และ seed 11 200 ปี (3.1 ต้อง 200 ปีหลังสุด) และโลก seed 16 400 ปี (4.1 ข, 4.2, 4.4 ก, 4.5 โลกไม่หยุดเดิน,
#   รายงานระยะยาวของ 4.3 ก และ 4.4)
@pytest.fixture(scope="module")
def _fast_runs():
    # งานสั้นทั้งหมดในพูลเดียว 3 โปรเซส ที่เหลือรอคิว — ไฟล์นี้ช้าลงเองแต่แย่ง CPU กับอีก 3 worker ของ -n 4 น้อยลง
    # (6 โปรเซส: ไฟล์นี้ 5.4 นาทีเมื่อรันเดี่ยว แต่ทั้งชุดรวม 56 นาที ทั้งที่รันแยกกันรวมได้ ~31 นาที)
    with multiprocessing.Pool(3) as pool:
        nature = [pool.apply_async(_nature_trial, (d,)) for d in (False, True)]
        war = [pool.apply_async(_war_trial, (f,)) for f in (False, True)]
        survival = pool.apply_async(_survival_trials)
        mech = pool.apply_async(_cycle_mechanism)
        adapt = pool.apply_async(_adaptation_trial)
        return dict(mech.get(), nature=[n.get() for n in nature], adapt=adapt.get(),
                    war=[w.get() for w in war], survival=survival.get())


@pytest.fixture(scope="module")
def _long_runs():
    # ชุดเต็ม: โลกยาวทั้งหมด (seed 16 400 ปี, seed 11 200 ปี, 5 seed × 60 ปีของแกน 1–3) — หนึ่งโปรเซสต่อโลก ไม่รอคิว
    with multiprocessing.Pool(len(SEEDS) + 2) as pool:
        cycle = pool.apply_async(_cycle_walk, (CYCLE_SEED,))
        long = pool.apply_async(_walk, (LONG_SEED, LONG_YEARS))
        worlds = pool.map(_walk, SEEDS)
        return [long.get()], cycle.get(), worlds


@pytest.fixture(scope="module")
def worlds(_long_runs):
    return _long_runs[2]


@pytest.fixture(scope="module")
def mechanism(_fast_runs):
    return _fast_runs


@pytest.fixture(scope="module")
def long_worlds(_long_runs):
    return _long_runs[0]


@pytest.fixture(scope="module")
def cycle(_long_runs):
    return _long_runs[1]


@pytest.fixture(scope="module", params=[pytest.param("longrun_5seeds_60y", marks=pytest.mark.longrun),
                                        pytest.param("longrun_seed11_200y", marks=pytest.mark.longrun)])
def axis_worlds(request):
    """แกน 1–3 อยู่ในชุดเต็มทั้งหมด (ผู้ใช้ตัดสิน: ชุดเร็วเก็บเฉพาะสถานการณ์ที่บังคับได้) — ตรวจบน 5 seed × 60 ปี และ seed 11 × 200 ปี
    (เกณฑ์เดียวกันทุกข้อ)"""
    return request.param, request.getfixturevalue("worlds" if "5seeds" in request.param else "long_worlds")


def _report(worlds, prefixes):
    """รวมทุก seed เฉพาะเกณฑ์ที่ขึ้นต้นด้วย prefixes — คืนข้อความ ('' = ผ่าน)"""
    lines = []
    for w in worlds:
        for key in sorted(w["count"]):
            if key.startswith(prefixes):
                lines.append(f"seed {w['seed']} ({w['years']} ปี) {key}: {w['count'][key]} ครั้ง "
                             f"เช่น {w['examples'].get(key, [])[:3]}")
    return "\n".join(lines)


def test_axis1_population_never_negative(axis_worlds):
    _, worlds = axis_worlds
    msg = _report(worlds, ("1.1", "1.x"))
    assert not msg, "ประชากรติดลบหรือไม่ตรงการนับจริง:\n" + msg


def test_axis1_food_ledger_closes(axis_worlds):
    _, worlds = axis_worlds
    msg = _report(worlds, ("1.2",))
    assert not msg, "อาหารที่มีจริงไม่เท่าบัญชีที่ได้มา − ที่ออกไป:\n" + msg


def test_axis1_gold_conserved_except_declared_sources(axis_worlds):
    _, worlds = axis_worlds
    msg = _report(worlds, ("1.3",))
    assert not msg, "ทองต่อชั้นไม่ปิดกับบัญชีต้นทางที่ประกาศ:\n" + msg


def test_axis1_enough_worlds_and_years(axis_worlds):
    suite, worlds = axis_worlds
    if "5seeds" in suite:
        assert len(worlds) >= 5, f"ตรวจแค่ {len(worlds)} seed"           # 1.4 อย่างน้อย 5 seed
    assert all(w["stats"]["day"] >= w["years"] * 365 for w in worlds),         [(w["seed"], w["stats"]["day"]) for w in worlds]


def test_axis2_every_death_has_a_cause_and_an_event(axis_worlds):
    _, worlds = axis_worlds
    msg = _report(worlds, ("2.1",))
    total = sum(w["stats"]["deaths"] for w in worlds)
    assert not msg, f"ความตายที่ไม่มีสาเหตุหรือไม่มีเหตุการณ์ (จากความตายทั้งหมด {total}):\n" + msg


def test_axis2_estate_reaches_someone(axis_worlds):
    _, worlds = axis_worlds
    msg = _report(worlds, ("2.2",))
    assert not msg, "ศพยังถือทรัพย์อยู่หลังความตาย:\n" + msg


def test_axis2_memories_cite_real_events(axis_worlds):
    _, worlds = axis_worlds
    msg = _report(worlds, ("2.3",))
    assert not msg, "ความจำหรือความสัมพันธ์อ้างสิ่งที่ไม่มีในประวัติ:\n" + msg


def test_axis2_no_unnoticed_corpse(axis_worlds):
    _, worlds = axis_worlds
    msg = _report(worlds, ("2.4",))
    assert not msg, "มีความตายที่ไม่ถูกบันทึก หรือคนเป็นยังผูกกับศพโดยไม่มีข่าว:\n" + msg


def test_axis3_last_200_years_connect(axis_worlds):
    """3.1 — ชุดเร็วตรวจเกณฑ์เดียวกันบน 5 seed × 60 ปี · ชุดเต็มตรวจ 200 ปีหลังสุดของ seed 11 ตามที่เกณฑ์กำหนด"""
    suite, worlds = axis_worlds
    if "5seeds" not in suite:
        long = [w for w in worlds if w["seed"] == LONG_SEED]
        assert long and long[0]["stats"]["day"] >= LONG_YEARS * 365, "ไม่มีโลกที่เดินครบ 200 ปีให้ตรวจ"
    msg = _report(worlds, ("3.1",))
    assert not msg, "เรื่องขาดตอนหรือมีคนที่ไม่อยู่ ณ วันนั้นลงมือ:\n" + msg


def test_axis3_events_reference_real_people_and_places(axis_worlds):
    _, worlds = axis_worlds
    msg = _report(worlds, ("3.2",))
    assert not msg, "เหตุการณ์อ้างคน แดน หรือสถานที่ที่ไม่มีอยู่:\n" + msg


def test_axis3_every_event_has_actor_and_place(axis_worlds):
    _, worlds = axis_worlds
    msg = _report(worlds, ("3.3",))
    total = sum(w["stats"]["events"] for w in worlds)
    assert not msg, f"เหตุการณ์ลอยๆ ไม่มีผู้กระทำหรือที่เกิด (จากเหตุการณ์ทั้งหมด {total}):\n" + msg


# ------------------------------------------------------------------ แกนที่ 4 — วงจร
def _swings(values, drop, min_swing):
    """จุดพลิกของ series ด้วย hysteresis แบบสัดส่วน: [('up'/'down', ดัชนีที่ยืนยันการพลิก, ดัชนีจุดสูง/ต่ำก่อนพลิก)]
    ลง = ต่ำกว่าจุดสูงล่าสุด ≥ drop×จุดสูง และ ≥ min_swing · ขึ้น = สูงกว่าจุดต่ำล่าสุด ≥ drop×ค่าใหม่ และ ≥ min_swing"""
    turns, hi, lo, state = [], 0, 0, None
    for i, v in enumerate(values):
        if v > values[hi]:
            hi = i
        if v < values[lo]:
            lo = i
        if state != "down" and values[hi] - v >= max(min_swing, drop * values[hi]):
            turns.append(("down", i, hi))
            state, lo = "down", i
        elif state != "up" and v - values[lo] >= max(min_swing, drop * v):
            turns.append(("up", i, lo))
            state, hi = "up", i
    return turns


def _full_cycles(turns, values):
    """รอบ ขึ้น→ลง→ขึ้น ที่ครบ: [(ปีจุดสูง, ค่าสูง, ปีจุดต่ำ, ค่าต่ำ)] — จุดต่ำคือจุดที่การขึ้นครั้งถัดไปเริ่มนับ"""
    out = []
    for a, b, c in zip(turns, turns[1:], turns[2:]):
        if (a[0], b[0], c[0]) == ("up", "down", "up"):
            out.append((b[2], values[b[2]], c[2], values[c[2]]))
    return out


def _rank_corr(xs, ys):
    """สหสัมพันธ์อันดับแบบสเปียร์แมน (ไม่ใช้ scipy)"""
    def ranks(v):
        order = sorted(range(len(v)), key=v.__getitem__)
        r = [0.0] * len(v)
        for pos, i in enumerate(order):
            r[i] = pos
        return r
    rx, ry = ranks(xs), ranks(ys)
    n = len(xs)
    mx, my = sum(rx) / n, sum(ry) / n
    cov = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    sx = sum((a - mx) ** 2 for a in rx) ** 0.5
    sy = sum((b - my) ** 2 for b in ry) ** 0.5
    return cov / (sx * sy) if sx and sy else 0.0


def _num(value):
    try:
        return float(str(value).rstrip("%").split()[0])
    except (ValueError, IndexError):
        return None


def test_axis4_1a_heaven_low_collapses_era(mechanism):
    m = mechanism["collapse"]
    assert m["fired"] and m["era"][1] == m["era"][0] + 1, f"คลังฟ้าต่ำกว่า COLLAPSE_RATIO แต่ยุคไม่ล่ม: {m}"
    assert all(v == 0 for v in m["gold"][1].values()), f"ยุคล่มทำบัญชีทองไม่ปิด: {m['gold']}"


def test_axis4_1a_flourish_for_recover_years_rises(mechanism):
    from tiandao import config as C
    short, full = mechanism["rise"][C.RECOVER_YEARS - 1], mechanism["rise"][C.RECOVER_YEARS]
    assert full["tier"][1] == full["tier"][0] + 1 and full["era"][1] == full["era"][0] + 1, \
        f"รุ่งเรืองครบ RECOVER_YEARS = {C.RECOVER_YEARS} ปีแล้วโลกไม่เลื่อนชั้น: {full}"
    assert short["tier"][1] == short["tier"][0], f"ยังไม่ครบ {C.RECOVER_YEARS} ปี (ขาดหนึ่งปี) โลกกลับเลื่อนชั้น: {short}"
    assert full["heaven_le_cap"], "เลื่อนชั้นแล้วคลังฟ้าเกินเพดาน (เสกพลัง)"
    assert all(v == 0 for v in full["gold"][1].values()), f"เลื่อนชั้นทำบัญชีทองไม่ปิด: {full['gold']}"


def test_axis4_1a_realms_fall_after_collapse_and_reclimb_after_recovery(mechanism):
    m, r = mechanism["collapse"], mechanism["reclimb"]
    assert m["survivors"] and m["pushed"] == m["survivors"], \
        f"หลังยุคล่ม ผู้รอดไม่ถูกกดขั้นลงตาม ERA_PUSHDOWN: {m['pushed']}/{m['survivors']} คน เช่น {m['not_pushed']}"
    assert m["realm_sum"][1] < m["realm_sum"][0], f"ผลรวมขั้นของผู้รอดไม่ลดหลังยุคล่ม: {m['realm_sum']}"
    assert r["breaks"] > 0, f"คลังฟื้นแล้ว {r['years']} ปี ไม่มีใครข้ามขั้นสำเร็จเลย: {r}"


@pytest.mark.longrun
def test_axis4_1b_longrun_cycles_report(cycle, mechanism):
    """ยืนยันระยะยาว — รายงานตัวเลข ไม่บังคับผ่าน (ผู้ใช้ตัดสิน: รอบยาว ~250 ปี ต้องการ 2 รอบ = 500 ปี เกินเวลาทดสอบ
    และไม่ลด RECOVER_YEARS) ส่วนที่ต้องผ่านคือกลไกวงจร (4.1 ก ด้านบน) — ที่นี่ตรวจแค่ว่าโลกเดินครบและข้อมูลพอรายงาน"""
    import warnings
    s = cycle["series"]
    assert cycle["day"] >= CYCLE_YEARS * 365, f"โลกหยุดก่อนครบ {CYCLE_YEARS} ปี (วัน {cycle['day']})"
    high = [r["high"] for r in s]
    turns = _swings(high, CYCLE_DROP, CYCLE_MIN_SWING)
    eras = [r["era0"] for r in s]
    cycles = _full_cycles(turns, high)
    # ข้อนี้ยังบังคับ: รอบที่ครบแล้วต้องไม่ล้างโลก (จุดต่ำยังเหลือคนขั้นสูง) — ไม่ขึ้นกับว่ารอบยาวแค่ไหน
    wiped = [(s[lo]["year"], v) for _, _, lo, v in cycles if v <= 0]
    assert not wiped, f"วงจรที่จุดต่ำไม่เหลือคนขั้น {CYCLE_HIGH_REALM}+ เลย (ล้างโลก ไม่ใช่พังแล้วเริ่มใหม่): {wiped}"
    m, rise = mechanism, mechanism["rise"]
    warnings.warn(
        f"4.1 (ข) วงจรครบรอบจริงใน {CYCLE_YEARS} ปี: {len([c for c in cycles if c[3] > 0])} รอบ (ต้องการ {MIN_CYCLES})"
        f" · จุดพลิก {[(k, s[i]['year'], high[i]) for k, i, _ in turns][:12]}"
        f" · คนขั้น {CYCLE_HIGH_REALM}+ ทุก 25 ปี {[(s[i]['year'], high[i]) for i in range(0, len(s), 25)]}"
        f" · ยุคเปลี่ยน {sum(1 for a, b in zip(eras, eras[1:]) if a != b)} ครั้ง"
        f" || 4.1 (ก) กลไก: ล่ม {m['collapse']['era']} ตาย {m['collapse']['died']}/{m['collapse']['people']}"
        f" กดขั้น {m['collapse']['pushed']}/{m['collapse']['survivors']} ผลรวมขั้น {m['collapse']['realm_sum']}"
        f" · ฟื้น {m['reclimb']['years']} ปี ข้ามขั้นสำเร็จ {m['reclimb']['breaks']} ครั้ง"
        f" · เลื่อนชั้น {[(h, v['tier']) for h, v in rise.items()]}", UserWarning)


def _nature_families(cycle):
    """ตระกูลเหตุการณ์ธรรมชาติระดับโลก — กำหนดชัดทีละตระกูล [(ชื่อ, วันที่เกิดแต่ละครั้ง, ความรุนแรงแต่ละครั้งหรือ None)]
    คลื่นมหาศึกในศึกเดียวกันไม่ใช่เหตุการณ์ใหม่ (นัดทุก CRISIS_WAVE ตามตาราง) — ศึกหนึ่งครั้งนับจากลางถึงสิ้นสุด
    ความรุนแรงของศึก = ความเสียหายรวมของทุกคลื่น (raids + breaches + resource_lost/1000) ไม่ใช่เลขลำดับคลื่น"""
    ev = cycle["natural"]
    fams = []
    omens = [e for e in ev if e["kind"] == "ลางมหาศึกโกลาหล"]
    sev = []
    for i, o in enumerate(omens):
        end = omens[i + 1]["day"] if i + 1 < len(omens) else 10 ** 9
        waves = [w for w in ev if w["kind"] == "มหาศึกโกลาหลถล่มโลกมนุษย์" and o["day"] <= w["day"] < end]
        sev.append(sum((_num(w["deltas"].get("raids")) or 0) + (_num(w["deltas"].get("breaches")) or 0)
                       + (_num(w["deltas"].get("resource_lost")) or 0) / 1000.0 for w in waves) if waves else None)
    fams.append(("มหาศึกโกลาหล (นับจากลาง)", [o["day"] for o in omens], sev))
    seal = [e for e in ev if e["kind"] in ("มหาผนึกสั่นคลอน", "มหาผนึกแตกพัง")]
    fams.append(("มหาผนึกหมื่นมาร", [e["day"] for e in seal], [None] * len(seal)))
    per_year = collections.Counter(e["day"] // 365 for e in ev if e["kind"] == "ภัยพิบัติตามฤดู")
    years = sorted(per_year)
    fams.append(("ภัยพิบัติตามฤดู (ต่อปี)", [y * 365 for y in years], [per_year[y] for y in years]))
    fams.append(("แผ่นดินเคลื่อนไหว", [], []))
    return fams


@pytest.mark.longrun
def test_axis4_2_longrun_nature_is_rhythmic_and_escalates(cycle):
    lines, rhythmic = [], []
    for name, days, sev in _nature_families(cycle):
        if len(days) < 3:
            missing = "ไม่มีเหตุการณ์ชนิดนี้ในโค้ดเลย" if name == "แผ่นดินเคลื่อนไหว" else f"เกิด {len(days)} ครั้ง (วัน {days[:5]})"
            lines.append(f"  {name}: {missing} — น้อยกว่า 3 ครั้ง วัดจังหวะไม่ได้")
            continue
        gaps = [b - a for a, b in zip(days, days[1:])]
        mean = sum(gaps) / len(gaps)
        cv = (sum((g - mean) ** 2 for g in gaps) / len(gaps)) ** 0.5 / mean if mean else 0.0
        pts = [(d, v) for d, v in zip(days, sev) if v is not None]
        rho = _rank_corr([d for d, _ in pts], [v for _, v in pts]) if len(pts) >= 3 else None
        rho_text = "ไม่มีตัวเลขความรุนแรง" if rho is None else f"{rho:.2f}"
        lines.append(f"  {name}: {len(days)} ครั้ง ช่วงห่างเฉลี่ย {mean / 365:.1f} ปี CV {cv:.2f} ความรุนแรง~เวลา rho={rho_text}"
                     + (f" ความรุนแรง {[round(v, 1) for _, v in pts][:8]}" if pts else ""))
        if cv < RHYTHM_CV and rho is not None and rho > TREND_RHO:
            rhythmic.append(name)
    assert rhythmic, ("ไม่มีเหตุการณ์ธรรมชาติระดับโลกชนิดใดเกิดเป็นจังหวะ (CV < "
                      f"{RHYTHM_CV}) และรุนแรงขึ้นตามเวลา (rho > {TREND_RHO}) ใน {CYCLE_YEARS} ปี:" + chr(10) + chr(10).join(lines))


def test_axis4_3a_low_heaven_raises_nature_pressure(mechanism):
    """(ก) บังคับสถานการณ์ (_war_trial): โลกสองใบ seed เดียวกัน ใบหนึ่งคลังฟ้าโลกมนุษย์ถูกกดไว้ที่ WAR_LOW_HEAVEN ทุกรอบโลก
    เทียบ "ความเร็วที่ธรรมชาติกดดัน" (Sim.nature_speedup) ที่วันเดียวกันทุกรอบโลกก่อนลางแรก (ผู้ใช้ตัดสิน) — ค่าเฉลี่ยต้องสูงกว่า
    และสูงกว่าในอย่างน้อย 90% ของรอบที่เทียบได้ · วันที่ลางมาเป็นรายงานเท่านั้น: หยาบเกินไป เพราะลางรอรอบตรวจมหาศึก
    (ทุก CRISIS_TICK_DAYS) และรอให้ผู้บุกและประชากรพร้อมตามกติกาของโลก แรงกดดันที่ต่างกันจริงจึงอาจลงวันเดียวกัน"""
    calm, low = mechanism["war"]
    a = {d: (p, v) for d, p, v in calm["samples"]}
    b = {d: (p, v) for d, p, v in low["samples"]}
    days = sorted(set(a) & set(b))
    sa = [a[d][1] for d in days]
    sb = [b[d][1] for d in days]
    higher = sum(1 for x, y in zip(sa, sb) if y > x)
    pa = [a[d][0] for d in days]
    pb = [b[d][0] for d in days]
    msg = (f"  รอบที่เทียบได้ {len(days)} · speedup เฉลี่ย ไม่แตะ {sum(sa) / max(1, len(sa)):.3f} (สูงสุด {max(sa, default=0):.3f}) "
           f"vs คลังฟ้าถูกกด {WAR_LOW_HEAVEN:.0%} {sum(sb) / max(1, len(sb)):.3f} (สูงสุด {max(sb, default=0):.3f}) · "
           f"ถูกกดสูงกว่า {higher}/{len(days)} รอบ\n"
           f"  แรงกดดันมหาศึกวันเดียวกัน (ท้ายสุดที่เทียบได้) ไม่แตะ {pa[-1] if pa else None} vs ถูกกด {pb[-1] if pb else None}\n"
           f"  รายงาน (หยาบ): ลางแรก ไม่แตะวันที่ {calm['omen_day']} · ถูกกดวันที่ {low['omen_day']}")
    assert len(days) >= 12, "รอบที่เทียบได้น้อยเกินไป:\n" + msg
    assert sum(sb) / len(sb) > sum(sa) / len(sa) and higher >= 0.9 * len(days),         "กดคลังฟ้าแล้วความเร็วที่ธรรมชาติกดดันไม่สูงกว่าอย่างมีนัย:\n" + msg


def test_axis4_3b_damage_accelerates_nature(mechanism):
    """(ข) โลกสองใบ seed เดียวกัน (_nature_trial): รีดทรัพยากรหนัก vs ไม่แตะ — damage ต่างกัน จังหวะธรรมชาติต้องต่างกันจริง"""
    from tiandao import config as C
    # (ข) วัดจริงด้วยโลกสองใบ seed เดียวกัน (_nature_trial): รีดทรัพยากรหนัก vs ไม่แตะ — damage ต่างกัน จังหวะต้องต่างกันจริง
    calm, hurt = mechanism["nature"]
    dis_up = hurt["disasters"] / max(1, calm["disasters"]) - 1
    seal_up = hurt["seal_loss_per_year"] / max(1e-9, calm["seal_loss_per_year"]) - 1
    gap = lambda o: (o[-1] - o[0]) / (len(o) - 1) if len(o) > 1 else None
    msg = (f"  โลกสองใบ {NATURE_TRIAL_YEARS} ปี (ไม่แตะ → รีดทรัพยากรเหลือ {NATURE_TRIAL_LEFT:.0%}): "
           f"damage เฉลี่ย {calm['damage']:.3f} → {hurt['damage']:.3f} · speedup เฉลี่ย {calm['speedup']:.3f} → "
           f"{hurt['speedup']:.3f} (สูงสุด {hurt['speedup_max']:.3f})\n"
           f"  ภัยพิบัติตามฤดู {calm['disasters']} → {hurt['disasters']} ครั้ง ({dis_up:+.1%}) · "
           f"ผนึกเสื่อม {calm['seal_loss_per_year']:.3f} → {hurt['seal_loss_per_year']:.3f} %/ปี ({seal_up:+.1%}) · "
           f"ลางมหาศึก {calm['omens']} → {hurt['omens']} (ห่างเฉลี่ย {gap(calm['omens'])} → {gap(hurt['omens'])} ปี) · "
           f"บัญชีวัตถุดิบโลกที่ถูกรีด ต่าง {hurt['material_gap']:.2e}")
    assert hurt["damage"] > calm["damage"], "รีดทรัพยากรหนักแล้ว damage ไม่เพิ่ม (ดัชนีไม่อ่านสภาวะจริง):\n" + msg
    assert dis_up > 0 and seal_up > 0, "damage สูงกว่าแต่ภัยตามฤดูหรือการเสื่อมของผนึกไม่เร็วขึ้นจริง:\n" + msg
    assert max(calm["speedup_max"], hurt["speedup_max"]) <= 1.0 + C.NATURE_SPEEDUP_MAX + 1e-9 and dis_up <= 0.5 + 0.05, \
        "ธรรมชาติเร็วขึ้นเกินเพดาน 50%:\n" + msg
    assert abs(hurt["material_gap"]) < 1e-3 and abs(calm["material_gap"]) < 1e-3, "บัญชีวัตถุดิบไม่ปิด:\n" + msg




@pytest.mark.longrun
def test_axis4_3a_longrun_wealth_share_report(cycle):
    """(ก) ระยะยาว — รายงานเท่านั้น (ผู้ใช้ตัดสิน: ตัวตัดสินคือแบบบังคับสถานการณ์ในชุดเร็ว): ส่วนของแรงกดดันมหาศึกจากแดนร่ำรวย
    และช่วงห่างลางจริงเทียบกับถ้ามีแต่เวลา ในโลก seed 16 400 ปี"""
    import warnings
    from tiandao import config as C
    s = cycle["series"]
    assert cycle["day"] >= CYCLE_YEARS * 365, f"โลกหยุดก่อนครบ {CYCLE_YEARS} ปี"
    base = len(s) * C.CRISIS_PRESSURE_BASE
    wealth = sum(min(2.0, r["rich"] / 30.0) for r in s)
    share = wealth / (base + wealth) if base + wealth else 0.0
    omens = [e["day"] for e in cycle["natural"] if e["kind"] == "ลางมหาศึกโกลาหล"]
    gaps = [(b - a) / 365 for a, b in zip(omens, omens[1:])]
    campaign_years = (C.CRISIS_WARNING_DAYS + (C.CRISIS_WAVES - 1) * C.CRISIS_WAVE_DAYS) / 365
    base_only = campaign_years + C.CRISIS_RECOVERY_DAYS / 365 + C.CRISIS_PRESSURE_TRIGGER / C.CRISIS_PRESSURE_BASE
    warnings.warn(f"4.3 (ก) ระยะยาว: ส่วนของแรงกดดันจากแดนร่ำรวย {share:.0%} (เดิมเกณฑ์ ≥ 10%) · ลาง {len(omens)} ครั้ง "
                  f"ห่างเฉลี่ย {sum(gaps) / max(1, len(gaps)):.1f} ปี เทียบกับถ้ามีแต่เวลา {base_only:.1f} ปี", UserWarning)


@pytest.mark.longrun
def test_axis4_4_longrun_bloodline_inherited(cycle):
    """(ก) ส่งต่อ ไม่ใช่สุ่มใหม่: สายเลือดลูกสัมพันธ์กับค่าเฉลี่ยของพ่อแม่ (โลกยาว CYCLE_YEARS ปี) · สายที่ขั้นเฉลี่ยสูงสุดต่อยุคเป็นรายงาน"""
    import warnings
    from tiandao import config as C
    pairs = [(child.get(k, 0.0), par.get(k, 0.0)) for v in cycle["births"].values()
             for child, par in v for k in C.BLOODS]
    corr = _rank_corr([a for a, _ in pairs], [b for _, b in pairs]) if len(pairs) >= 10 else None
    leaders = collections.defaultdict(collections.Counter)
    for r in cycle["series"]:
        state = "มหาศึก" if r["campaign"] else r["era0"]
        # ไม่นับสายเลือดโกลาหล: เป็นเผ่าที่ระบบสร้างมาบุก ไม่ได้เกิดและรอดข้ามรอบในโลก (ขั้นสูงตั้งแต่เกิด นำทุกสภาวะเสมอ)
        ranked = {k: v for k, v in r["realm_by_blood"].items() if v > 0 and k != "chaos"}
        if ranked:
            leaders[state][max(ranked, key=ranked.get)] += 1
    assert corr is not None and corr > 0.5, f"สายเลือดไม่ได้ส่งต่อข้ามรุ่น: สหสัมพันธ์ลูก~พ่อแม่ {corr}"
    warnings.warn(f"4.4 ระยะยาว: สหสัมพันธ์สายเลือดลูก~พ่อแม่ {corr:.2f} (คนเกิด {sum(len(v) for v in cycle['births'].values())}) "
                  f"· สายที่ขั้นเฉลี่ยสูงสุดต่อสภาวะ (ปี) {dict((k, dict(v)) for k, v in leaders.items())}", UserWarning)


@pytest.mark.longrun
def test_axis4_4_longrun_survival_report(cycle):
    """(ก-2) ระยะยาว — รายงานเท่านั้น (ผู้ใช้ตัดสิน: ตัวตัดสินคือแบบบังคับสถานการณ์ในชุดเร็ว): ต่อสภาวะโลกตอนตาย สัดส่วนที่รอดถึง
    วัยชราและอายุเฉลี่ยตอนตาย แยกตามสายเลือดหลัก ในโลก seed 16 400 ปี"""
    import warnings
    table = {st: {k: (n, round(s / n, 1), round(o / n, 3)) for k, (n, s, o) in rows.items()}
             for st, rows in cycle["survival"].items()}
    best = {st: max((k for k, v in rows.items() if v[0] >= SURVIVAL_MIN_DEATHS), key=lambda k: rows[k][2], default=None)
            for st, rows in table.items()}
    assert table, "ไม่มีข้อมูลความตายในโลกยาว"
    warnings.warn(f"4.4 ระยะยาว: สายที่รอดถึงวัยชรามากที่สุด {best} · (ผู้ตาย, อายุเฉลี่ยตอนตาย, สัดส่วนรอดถึง {OLD_AGE}) {table}",
                  UserWarning)


def test_axis4_4_scarcity_food_absorbed_report(mechanism):
    """(ก-3) ทรัพยากรน้อย — รายงาน + สองข้อบังคับ (ผู้ใช้ตัดสิน 2026-10-05)
    คำถามที่ถาม: "เมื่อทรัพยากรหมด คนเข้าสู่ภาวะข้าวขาดจริงไหม หรือกลไกของโลกดูดซับได้?" — แทนคำถามเดิม "ตายเพราะหิวเพิ่มไหม"
    เพราะผลวัดแล้วข้าวลดจริงแต่ไม่มีใครตายเพิ่ม (อดอยาก 0.002 → 0.003): ยุ้งฉาง 3 เดือน คนลงไร่ชดเชย และย้ายไปหาข้าวที่อื่น
    เป็นกลไกที่มีอยู่จริงในโลก — ผู้ใช้ยืนยันว่าโลกทำงานถูก
    บังคับผ่าน: ผลผลิตข้าวช่วงบังคับต้องลดลงจริงเมื่อสมุนไพรหมด (เทียบยุคปกติ) และบัญชีอาหารต้องปิดทั้งสองโลก
    รายงาน: ความหิวสะสม (unmet = สำรับที่ขาด ≈ คน-วันที่หิว) ย้ายหาข้าว ลงไร่ชดเชย อดตาย ผู้ปิดด่านที่ต้องออก และสาเหตุการตาย"""
    import warnings
    runs = {r["state"]: r for r in mechanism["survival"]}
    calm, lean = runs["ยุคปกติ"], runs["ทรัพยากรน้อย"]
    fc, fl = calm["food"], lean["food"]
    drop = 1 - fl["produced"] / fc["produced"] if fc["produced"] else 0.0
    absorb = {"ลงไร่ชดเชย (คน-ครั้ง)": fl["took_up_farming"] - fc["took_up_farming"],
              "ย้ายหาข้าว (ครั้ง)": fl["migrated"] - fc["migrated"],
              "ผู้ปิดด่านออกมาหาข้าว": fl["seclusion_cut"] - fc["seclusion_cut"]}
    share = {}
    for st, r in runs.items():
        total = collections.Counter()
        for c in r["causes"].values():
            total.update(c)
        n = sum(total.values())
        share[st] = {k: round(total.get(k, 0) / n, 3) if n else 0.0 for k in DEATH_KINDS}
    msg = (f"  ผลผลิตข้าวช่วงบังคับ: ยุคปกติ {fc['produced']:,.0f} → ทรัพยากรน้อย {fl['produced']:,.0f} (ลด {drop:.1%})\n"
           f"  ความหิวสะสม (สำรับที่ขาด ≈ คน-วัน): {fc['unmet']:,.1f} → {fl['unmet']:,.1f} · อดตาย {fc['starved']} → {fl['starved']}\n"
           f"  กลไกดูดซับ (ส่วนที่เพิ่มเทียบยุคปกติ): {absorb}\n"
           f"  บัญชีอาหาร ยุคปกติ ต่าง {calm['food_gap']:.2e} · ทรัพยากรน้อย ต่าง {lean['food_gap']:.2e}\n"
           f"  สัดส่วนสาเหตุการตาย (รายงาน): {share}\n"
           f"  ผู้ตายที่ไม่ต้องกินข้าว ต่อสาย: {[(st, r['no_food_dead']) for st, r in runs.items()]}")
    assert all(r["state_seen"] == st for st, r in runs.items()), "บังคับสถานการณ์ไม่ติด:\n" + msg
    assert fl["produced"] < fc["produced"], "สมุนไพรหมดแล้วผลผลิตข้าวไม่ลดลง:\n" + msg
    tol = 1e-6 * max(1.0, fc["produced"])
    assert abs(calm["food_gap"]) < tol and abs(lean["food_gap"]) < tol, "บัญชีอาหารไม่ปิด:\n" + msg
    warnings.warn("4.4 ทรัพยากรน้อย (รายงาน): " + msg.replace("\n", " | "), UserWarning)


def test_axis4_4_leader_changes_with_world_state(mechanism):
    """(ข) คู่พ่อแม่ชุดเดียวกันคลอดในสถานการณ์ต่างกัน สายที่ลูกได้เพิ่ม (เทียบยุคปกติ) ต้องไม่ใช่สายเดียวกันทุกสถานการณ์"""
    a = mechanism["adapt"]
    msg = (f"  ผู้ได้เปรียบต่อสถานการณ์: {a['leader']}" + "\n" +
           f"  ลูก − ค่าเฉลี่ยพ่อแม่ (เทียบยุคปกติ): {a['vs_normal']}" + "\n" +
           f"  ลูก − ค่าเฉลี่ยพ่อแม่ (ดิบ): {a['drift']} · คลอด {a['births']}")
    assert all(n > 0 for n in a["births"].values()), "บางสถานการณ์ไม่มีการคลอด:" + "\n" + msg
    assert len(set(a["leader"].values())) > 1, "สายที่ได้เปรียบเป็นสายเดียวกันทุกสถานการณ์:" + "\n" + msg
    assert a["leader"]["ยุคเสื่อม"] == "human" and a["leader"]["ทรัพยากรน้อย"] == "human",         "ยุคเสื่อม/ทรัพยากรน้อย สายมนุษย์ (ทนทาน ประหยัด) ไม่ได้เปรียบ:" + "\n" + msg
    assert a["leader"]["สงคราม"] == "demon" and a["vs_normal"]["สงคราม"]["human"] < 0,         "สงคราม สายสู้เก่งไม่ได้เปรียบ หรือสายที่ต้องอยู่รอดไม่อ่อนลง:" + "\n" + msg


def test_axis4_4_adaptation_effects_are_real(mechanism):
    """(ค) ผลจริงของการปรับตัว: ยุคเสื่อม สายมนุษย์อายุเลยอายุขัยปกติแล้วยังรอด (ยุคปกติตาย) · ทรัพยากรน้อย สายมนุษย์กินน้อยลง
    ไม่เกิน 10% และบัญชีอาหารปิดเท่าเดิม"""
    from tiandao import config as C
    life, food = mechanism["adapt"]["life"], mechanism["adapt"]["food"]
    calm, lean = food["ยุคปกติ"], food["ทรัพยากรน้อย"]
    # เทียบคนชุดเดียวกัน (cid ที่อยู่ทั้งสองรอบ) — ผลรวมของทั้งแดนปนจำนวนคนที่ต่างกัน (ทรัพยากรน้อยผลผลิตลด คนย้ายออก/ตาย)
    same = sorted(set(calm["per_cid"]) & set(lean["per_cid"]))
    base = sum(calm["per_cid"][c] for c in same)
    cut = 1 - sum(lean["per_cid"][c] for c in same) / base if base else 0.0
    food = {k: {kk: vv for kk, vv in v.items() if kk != "per_cid"} for k, v in food.items()}
    msg = f"  เทียบคนชุดเดียวกัน {len(same)} คน · อายุขัย {life}" + "\n" + f"  อาหาร {food} (กินน้อยลง {cut:.1%})"
    assert life["ยุคเสื่อม"]["alive"] and not life["ยุคปกติ"]["alive"], "ยุคเสื่อม สายมนุษย์ไม่ได้อยู่นานขึ้นจริง:" + "\n" + msg
    assert life["ยุคเสื่อม"]["effective"] <= life["ยุคเสื่อม"]["lifespan"] * (1 + C.HUMAN_DECLINE_LIFESPAN) + 1e-9,         "อายุขัยยืดเกิน 10%:" + "\n" + msg
    assert 0 < cut <= C.HUMAN_SCARCE_FRUGAL + 1e-9, "ทรัพยากรน้อยแล้วสายมนุษย์ไม่ได้กินน้อยลง หรือลดเกิน 10%:" + "\n" + msg
    assert abs(lean["gap"] - calm["gap"]) < 1e-6 * max(1.0, calm["need"] * 30), "ลดการกินแล้วบัญชีอาหารไม่ปิด:" + "\n" + msg


def test_axis4_5_broken_seal_is_not_a_dead_end(mechanism):
    m = mechanism["seal"]
    assert m["empty"]["broken"] and m["empty"]["seal"] == 0.0, \
        f"ไม่มีฝ่ายธรรมะเลย {SEAL_TRIAL_YEARS} ปี ผนึกกลับฟื้นเอง (ซ่อมจากอากาศ): {m['empty']}"
    assert m["crew"] > 0 and m["repairs"] > 0, f"ใส่ฝ่ายธรรมะขั้นสูง {m['crew']} คนแล้ว {SEAL_TRIAL_YEARS} ปีไม่มีการซ่อมเลย: {m}"
    assert not m["broken"] and m["seal"] > 0, f"ซ่อมแล้วผนึกยังพัง: {m}"
    assert m["capped"] and m["leaders_in_crew"], f"ซ่อมเกิน 100 หรือผู้นำการซ่อมไม่ใช่คนในคณะ: {m}"


@pytest.mark.longrun
def test_axis4_5_longrun_world_not_frozen(cycle):
    """ส่วนที่ยังบังคับ: ค่าที่ต้องขยับตามเวลา (พลังฟ้า แรงกดดันมหาศึก จำนวนคนขั้นสูง) ห้ามค้างนิ่ง 100 ปีท้าย = โลกหยุดเดิน
    ผนึกพังถาวร ยุคเสื่อมยาว และไม่มีมหาศึกในช่วงเสื่อม รายงานเป็นตัวเลข (ผู้ใช้ตัดสินว่าเป็นธรรมชาติของโลกที่เสื่อม)"""
    import warnings
    s = cycle["series"]
    tail = [r for r in s if r["year"] >= s[-1]["year"] - FLAT_YEARS]
    frozen = [f"{label} คงที่ {next(iter({r[key] for r in tail}))} ตลอด {FLAT_YEARS} ปีท้าย"
              for key, label in (("heaven0", "พลังฟ้าดินโลกมนุษย์"), ("pressure", "แรงกดดันมหาศึก"),
                                 ("high", f"จำนวนคนขั้น {CYCLE_HIGH_REALM}+"))
              if len({r[key] for r in tail}) == 1]
    assert not frozen, "โลกหยุดเดิน:\n  " + "\n  ".join(frozen)
    broke = next((r["year"] for r in s if r["seal_broken"]), None)
    tail_start = tail[0]["year"]
    war = any(r["campaign"] for r in tail) or any(
        e["kind"] == "ลางมหาศึกโกลาหล" and e["day"] // 365 >= tail_start for e in cycle["natural"])
    warnings.warn(f"4.5 ระยะยาว: ผนึกพังปีที่ {broke} ท้ายรัน {s[-1]['mara_seal']} "
                  f"(พังอยู่ท้ายรัน = {s[-1]['seal_broken']}) · ยุค {FLAT_YEARS} ปีท้าย {sorted({r['era0'] for r in tail})} "
                  f"· มหาศึกใน {FLAT_YEARS} ปีท้าย = {war}", UserWarning)


# ------------------------------------------------------------------ กันบั๊กที่เจอจากการเดินโลกจริง (seed 42 273 ปี, 2026-10-05)
ERA_TRIAL_TICKS = 24                   # รอบโลก (30 วัน) ที่คงคลังฟ้าไว้ใต้จุดล่ม — บั๊กเดิมล่มทุกรอบ = 24 ครั้ง
SEED_TRIAL_YEARS = 6                   # เดินโลกต่อกี่ปีหลังคลังฟ้าโลกมนุษย์ถูกดูดถึงศูนย์ ต้องฟื้นขึ้นเหนือเมล็ด
CAUSE_TRIAL_YEARS = 15                 # เดินโลกกี่ปีเพื่อเทียบสาเหตุการตายกับเหตุการณ์วันเดียวกัน


def test_era_collapse_is_an_event_not_a_monthly_state():
    """ยุคล่มต้องเป็น "เหตุการณ์ที่โลกตกถึงจุดล่ม" ครั้งเดียว ไม่ใช่ซ้ำทุกรอบโลกที่คลังยังต่ำ (บั๊กเดิม: seed 42 ล่ม 1,165 ครั้งใน 273 ปี
    ห่างกัน 30 วัน ตายไปกับยุค 3,956 คน · โลกจริงยุคที่ 10,307) — คงคลังใต้จุดล่ม ERA_TRIAL_TICKS รอบ ต้องล่มครั้งเดียว
    แล้วคลังกลับขึ้นเหนือจุดล่มและตกอีกครั้ง จึงล่มครั้งที่สอง · และการดูด/ขุด/เก็บต้องไม่ลากคลังลงใต้เมล็ด (World.extractable) —
    เริ่มที่ 1.5 เท่าของเมล็ด เดิน SEED_TRIAL_YEARS ปี ต้องยังอยู่เหนือเมล็ด (โค้ดเดิมดูดลงถึง ~0 แล้วติดอยู่ตรงนั้น)"""
    from tiandao import config as C
    from tiandao import rules as R
    from tiandao import sim as S
    with contextlib.redirect_stdout(io.StringIO()):
        sim = S.Sim(seed=CYCLE_SEED)
        w = sim.worlds[0]
        era0 = w.era
        falls = []
        for i in range(ERA_TRIAL_TICKS):
            w.heaven = w.cap() * C.COLLAPSE_RATIO * 0.3
            sim.day += C.WORLD_TICK_DAYS
            if R.check_world(sim, w, sim.rng) is not None:
                falls.append(sim.day)
        held = len(falls)
        w.heaven = w.cap() * (C.COLLAPSE_RATIO + 0.05)
        sim.day += C.WORLD_TICK_DAYS
        R.check_world(sim, w, sim.rng)
        w.heaven = w.cap() * C.COLLAPSE_RATIO * 0.3
        sim.day += C.WORLD_TICK_DAYS
        again = R.check_world(sim, w, sim.rng) is not None

        sim2 = S.Sim(seed=CYCLE_SEED)
        w2 = sim2.worlds[0]
        seed = getattr(C, "HEAVEN_SEED_RATIO", 0.02) * w2.cap()      # ค่าตั้งเผื่อรันกับโค้ดเก่าที่ยังไม่มีเมล็ด (พิสูจน์ว่าเทสต์จับบั๊กได้)
        w2.heaven = seed * 1.5           # เหนือเมล็ดเล็กน้อย — โค้ดเดิมดูดลงถึงศูนย์ ใหม่ต้องดูดได้แค่ถึงเมล็ด
        start = sim2.day
        low = []
        while sim2.day < start + SEED_TRIAL_YEARS * 365:
            if sim2.step() is None:
                break
            low.append(w2.heaven)
    msg = (f"  คงใต้จุดล่ม {ERA_TRIAL_TICKS} รอบ: ล่ม {held} ครั้ง (วัน {falls[:5]}) · ยุค {era0} → {w.era} · "
           f"กลับขึ้นแล้วตกอีก: ล่ม = {again}\n"
           f"  คลังเริ่มที่ 1.5 เท่าของเมล็ด ({seed * 1.5:.0f}): หลัง {SEED_TRIAL_YEARS} ปี {w2.heaven:.1f} ต่ำสุด {min(low, default=0):.1f} "
           f"(เมล็ด {seed:.0f} · เพดาน {w2.cap():.0f})")
    assert held == 1, "คลังค้างใต้จุดล่ม ยุคล่มซ้ำทุกรอบโลก:\n" + msg
    assert again, "คลังกลับขึ้นเหนือจุดล่มแล้วตกอีก ยุคไม่ล่ม:\n" + msg
    # เมล็ดกันแค่การดูด/ขุด/เก็บ — ภัยและการทำลาย (หนาวจัด 5% บุกโกลาหล −20) ดึงลงใต้เมล็ดได้ตามกติกา (seed 16: จบ 1,397 จากเมล็ด 1,400)
    # จึงตรวจว่าไม่ลงต่ำกว่าครึ่งเมล็ด (ผู้ใช้อนุมัติ 2026-10-06) และไม่ติดลบเด็ดขาด
    assert min(low, default=0.0) >= 0.0 and w2.heaven >= 0.0, "คลังฟ้าติดลบ:\n" + msg
    assert w2.heaven >= seed * 0.5, "ผู้ฝึก/สำนัก/การเก็บเกี่ยวดูดคลังฟ้าลงต่ำกว่าครึ่งเมล็ด (ฟื้นไม่ได้):\n" + msg


def test_recorded_cause_matches_the_death_event():
    """สาเหตุที่บันทึก (death_cause) ต้องตรงกับเหตุการณ์ความตายวันเดียวกัน — บั๊กเดิม: ตายจากบาดแผลระหว่างร่างกายเดิน
    แต่เหตุการณ์เขียนว่า "สิ้นอายุขัย" (seed 42 ใน 50 ปี 615 คน) · ตรวจ: เหตุการณ์ "สิ้นอายุขัย" ของผู้ตายต้องมีสาเหตุเป็นอายุขัย
    และผู้ตายที่สาเหตุเป็นอายุขัยต้องไม่มีเหตุการณ์ความตายที่บอกสาเหตุอื่น"""
    from tiandao import config as C
    from tiandao import death as DEATH
    from tiandao import sim as S
    causes = {}
    real = DEATH.resolve

    def resolve(sim_, ch, cause, killer=None, natural=False):
        if ch.alive and not ch.is_lord:
            causes[ch.cid] = (sim_.day, cause)
        real(sim_, ch, cause, killer, natural)

    DEATH.resolve = resolve
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            sim = S.Sim(seed=CYCLE_SEED)
            while sim.day < CAUSE_TRIAL_YEARS * 365:
                if sim.step() is None:
                    break
    finally:
        DEATH.resolve = real
    wrong, checked = [], 0
    for e in sim.log:
        if e.kind != "สิ้นอายุขัย" or e.actor not in causes:
            continue
        checked += 1
        day, cause = causes[e.actor]
        if not cause.startswith("สิ้นอายุขัย"):
            wrong.append((e.seq, e.day, e.actor, cause[:40]))
    wound = sum(1 for d, c in causes.values() if "บาดแผล" in c or "เลือดไหล" in c)
    msg = (f"  เหตุการณ์ 'สิ้นอายุขัย' {checked} ครั้ง · สาเหตุจริงไม่ใช่อายุขัย {len(wrong)} เช่น {wrong[:5]}\n"
           f"  ผู้ตายทั้งหมด {len(causes)} · ตายจากบาดแผล/เลือดไหล {wound}")
    assert checked > 0 and wound > 0, "ข้อมูลไม่พอตรวจ (ไม่มีการตายตามวัยหรือจากบาดแผล):\n" + msg
    assert not wrong, "เหตุการณ์เขียนว่าสิ้นอายุขัย แต่สาเหตุที่บันทึกคืออย่างอื่น:\n" + msg


# ------------------------------------------------------------------ งานประมูล: จังหวะตามเวลาโลก และเจ้าภาพหมุนเวียน (2026-10-05)
AUCTION_TRIAL_YEARS = 8                # เดินโลกกี่ปีเพื่อนับงานประมูลต่อแดนต่อรอบโลก
AUCTION_HOST_ROUNDS = 6                # เปิดงานในตลาดเดียวกันกี่ครั้งเพื่อดูว่าเจ้าภาพหมุนเวียน


def test_auction_cadence_follows_the_world_clock():
    """AUCTION_EVENT_P คือโอกาสต่อแดนต่อหนึ่งช่วงเวลาโลก (config) — งานประมูลของตลาดในแดนหนึ่งต้องไม่เกินหนึ่งงานต่อรอบโลก
    บั๊กเดิม: ทอยทุกเทิร์นของตัวละครใน _step แดนที่คนมากจึงมีงานถี่ตามจำนวนเทิร์น (seed 42 ใน 100 ปี 3,232 งาน)"""
    from tiandao import config as C
    from tiandao import sim as S
    with contextlib.redirect_stdout(io.StringIO()):
        sim = S.Sim(seed=CYCLE_SEED)
        while sim.day < AUCTION_TRIAL_YEARS * 365:
            if sim.step() is None:
                break
    market = [e for e in sim.log if e.kind == "เปิดประมูล" and e.outcome == "ประมูล" and "เปิดงานประมูลใหญ่" in e.text]
    per_tick = collections.Counter((e.world_id, e.day // C.WORLD_TICK_DAYS) for e in market)
    over = [(k, v) for k, v in per_tick.items() if v > 1]
    mortal = sum(1 for w in sim.worlds if w.kind == "mortal")
    ticks = sim.day // C.WORLD_TICK_DAYS
    msg = (f"  งานประมูลของตลาด {len(market)} งานใน {AUCTION_TRIAL_YEARS} ปี · แดนมนุษย์ {mortal} · รอบโลก {ticks} · "
           f"ค่าคาด ≈ {mortal * ticks * C.AUCTION_EVENT_P:.0f} · แดน-รอบที่มีเกินหนึ่งงาน {len(over)} เช่น {over[:5]}")
    assert market, "ไม่มีงานประมูลของตลาดเลย (ตลาดหายไป):\n" + msg
    assert not over, "งานประมูลเกินหนึ่งงานต่อแดนต่อรอบโลก (ทอยตามเทิร์นตัวละคร ไม่ใช่ตามเวลาโลก):\n" + msg


def test_auction_host_rotates():
    """เจ้าภาพงานประมูลต้องหมุนเวียน — คนที่ไม่ได้เปิดงานมานานที่สุดก่อน (ไม่สุ่ม) บั๊กเดิม: พ่อค้าที่รวยที่สุดของที่นั้นเป็นเจ้าภาพทุกงาน
    (seed 42: คนเดียว 37 งานใน 100 ปี) · ตลาดเดียวกัน คนกลุ่มเดียวกัน เปิด AUCTION_HOST_ROUNDS ครั้ง ต้องมีเจ้าภาพมากกว่าหนึ่งคน"""
    from tiandao import config as C
    from tiandao import places as PL
    from tiandao import sim as S
    with contextlib.redirect_stdout(io.StringIO()):
        sim = S.Sim(seed=CYCLE_SEED)
        w = sim.worlds[0]
        market = next(i for i, p in enumerate(PL.PLACES) if p[1] == w.place_key and p[3] in C.AUCTION_PLACES)
        folk = [c for c in sim.living_in(w.wid) if c.age(sim.day) >= 14 and not c.is_chaos()][:6]
        for c in folk:
            c.place, c.hidden, c.travel_dest = market, False, -1
            c.money[w.tier] = 5000
        others = {c.cid for c in folk}
        for c in sim.living_in(w.wid):
            if c.cid not in others and c.place == market:
                c.place = (market + 1) % len(PL.PLACES)
        hosts = []
        for _ in range(AUCTION_HOST_ROUNDS):
            n = len(sim.log)
            sim.market_auction(w, sim.rng)
            hosts += [e.actor for e in sim.log[n:] if e.kind == "เปิดประมูล" and e.outcome == "ประมูล"]
            sim.day += 1
    msg = f"  เจ้าภาพ {hosts} · คนในตลาด {sorted(others)}"
    assert len(hosts) >= AUCTION_HOST_ROUNDS - 1, "ตลาดที่มีคนพอเปิดงานไม่ได้:\n" + msg
    assert len(set(hosts)) > 1, "เจ้าภาพคนเดิมทุกงาน:\n" + msg


# ------------------------------------------------------------------ วัยเด็ก: โดนแกล้ง / โกงเงินทอน (ผู้ใช้อนุมัติ 2026-10-05)
def _kids_world():
    from tiandao import sim as S
    with contextlib.redirect_stdout(io.StringIO()):
        return S.Sim(seed=CYCLE_SEED)


def test_bullied_child_becomes_wary():
    """เด็กที่โดนแกล้งต่อเนื่อง BULLY_TRAIT_YEARS ปีต้องติดรากนิสัย "ระวังคน" จริง แค้นผู้แกล้ง และผู้แกล้งเสียความสนิทกับกลุ่ม
    บันทึกเหตุการณ์ "แกล้ง" เฉพาะครั้งแรกของคู่นั้น"""
    from tiandao import childhood as CHILD
    from tiandao import config as C
    sim = _kids_world()
    w = sim.worlds[0]
    kids = [c for c in sim.living_in(w.wid) if c.sentient and not c.is_chaos()][:3]
    victim, bully, friend = kids
    for c in kids:
        c.place = victim.place
    victim.born_day, bully.born_day, friend.born_day = sim.day - 6 * 365, sim.day - 10 * 365, sim.day - 7 * 365
    victim.fear, bully.fear, friend.fear = 0.9, 0.1, 0.2
    bully.ambition, bully.compassion = 0.9, 0.1
    friend.ambition, friend.compassion = 0.3, 0.6
    victim.traits = [x for x in victim.traits if x != "ระวังคน"]
    n = len(sim.log)
    with contextlib.redirect_stdout(io.StringIO()):
        for _ in range(C.BULLY_TRAIT_YEARS):
            CHILD._bully(sim, victim, [bully.cid, friend.cid], w)
            sim.day += 365
    new_ev = [e for e in sim.log[n:] if e.kind == "แกล้ง"]
    msg = (f"  รากนิสัย {victim.traits} · แค้น {victim.rivals.get(bully.cid)} · โดนแกล้ง {getattr(victim, 'bullied_by', {})} · "
           f"ความสนิท เพื่อน→ผู้แกล้ง {friend.bonds.get(bully.cid)} · เหตุการณ์แกล้ง {len(new_ev)}")
    assert "ระวังคน" in victim.traits, "โดนแกล้งครบแล้วไม่ติดรากนิสัยระวังคน:\n" + msg
    assert victim.rivals.get(bully.cid, 0) >= C.BULLY_TRAIT_YEARS, "ผู้โดนไม่แค้นผู้แกล้ง:\n" + msg
    assert friend.bonds.get(bully.cid, 0) < 0, "ผู้แกล้งไม่เสียความสนิทกับกลุ่ม:\n" + msg
    assert len(new_ev) == 1, "บันทึกเหตุการณ์แกล้งเกินครั้งแรก:\n" + msg


def test_caught_cheater_returns_money_and_owes():
    """เด็กโกงเงินทอนแล้วถูกจับ (พ่อค้าขั้นสูงกว่า) ต้องคืนเงินครบ ได้หนี้กรรม พ่อค้าแค้น และบัญชีทองยังปิด
    · เด็กที่ไม่ถูกจับครบ CHILD_CHEAT_TRAIT_AFTER ปี ต้องติด "หัวหมอ" (พิสูจน์ว่าทางนี้ไปถึงได้)"""
    from tiandao import childhood as CHILD
    from tiandao import config as C
    from tiandao import places as PL
    from tiandao import wages as W
    sim = _kids_world()
    w = sim.worlds[0]
    market = next(i for i, pl in enumerate(PL.PLACES) if pl[1] == w.place_key and pl[3] in C.AUCTION_PLACES)
    people = [c for c in sim.living_in(w.wid) if c.sentient and not c.is_chaos()]
    kid, shop = people[0], people[1]
    tier = w.tier
    for c in (kid, shop):
        c.place, c.hidden, c.travel_dest, c.world_id = market, False, -1, w.wid
    for c in sim.living_in(w.wid):
        if c.cid not in (kid.cid, shop.cid) and c.place == market:
            c.place = (market + 1) % len(PL.PLACES)
    kid.born_day, kid.greed, kid.realm, kid.money = sim.day - 11 * 365, 0.9, 0, {}
    shop.born_day, shop.profession, shop.realm = sim.day - 40 * 365, C.AUCTION_HOSTS[0], 2
    W.set_gold(sim, shop, tier, 1000.0, "test_cheat_shop")
    gaps0 = {t: round(W.gold_gap(sim, t), 6) for t in sorted({x.tier for x in sim.worlds})}
    with contextlib.redirect_stdout(io.StringIO()):
        CHILD._cheat(sim, kid, w)
    debts = [d for d in kid.debts if d.get("kind") == "โกง"]
    gaps1 = {t: round(W.gold_gap(sim, t), 6) for t in gaps0}
    msg = (f"  เงินเด็ก {W.gold(sim, kid):.4f} · เงินพ่อค้า {W.gold(sim, shop):.4f} · หนี้กรรม {debts} · "
           f"แค้นพ่อค้า {shop.rivals.get(kid.cid)} · ถูกจับ {getattr(kid, 'cheat_caught', 0)} · บัญชีทอง {gaps0} → {gaps1}")
    assert getattr(kid, "cheat_caught", 0) == 1, "พ่อค้าขั้นสูงกว่าแต่เด็กไม่ถูกจับ:\n" + msg
    assert abs(W.gold(sim, kid)) < 1e-9 and abs(W.gold(sim, shop) - 1000.0) < 1e-9, "ถูกจับแล้วเงินไม่คืนครบ:\n" + msg
    assert debts and shop.rivals.get(kid.cid, 0) > 0, "ถูกจับแล้วไม่มีหนี้กรรมหรือพ่อค้าไม่แค้น:\n" + msg
    assert gaps1 == gaps0, "บัญชีทองเปลี่ยนจากการโกง (ทองเกิดหรือหาย):\n" + msg

    sim2 = _kids_world()
    w2 = sim2.worlds[0]
    people2 = [c for c in sim2.living_in(w2.wid) if c.sentient and not c.is_chaos()]
    kid2, shops = people2[0], people2[1:1 + C.CHILD_CHEAT_TRAIT_AFTER]
    for c in [kid2] + shops:
        c.place, c.hidden, c.travel_dest = market, False, -1
    for c in sim2.living_in(w2.wid):
        if c.cid not in {kid2.cid, *(s.cid for s in shops)} and c.place == market:
            c.place = (market + 1) % len(PL.PLACES)
    kid2.born_day, kid2.greed, kid2.realm, kid2.money = sim2.day - 10 * 365, 0.9, 1, {}
    kid2.traits = [x for x in kid2.traits if x != "หัวหมอ"]
    for s in shops:
        s.born_day, s.profession, s.realm = sim2.day - 40 * 365, C.AUCTION_HOSTS[0], 0
        W.set_gold(sim2, s, w2.tier, 1000.0, "test_cheat_shop")
    with contextlib.redirect_stdout(io.StringIO()):
        for _ in range(C.CHILD_CHEAT_TRAIT_AFTER):
            kid2.money = {}
            CHILD._cheat(sim2, kid2, w2)
            sim2.day += 365
    assert "หัวหมอ" in kid2.traits and getattr(kid2, "cheat_caught", 0) == 0, \
        f"โกงสำเร็จครบแล้วไม่ติดหัวหมอ: สำเร็จ {getattr(kid2, 'cheat_ok', 0)} ถูกจับ {getattr(kid2, 'cheat_caught', 0)} {kid2.traits}"


# ------------------------------------------------------------------ มารบุก: จังหวะตามเวลาโลก และผู้บุกหมุนเวียน (2026-10-06)
RAID_TRIAL_YEARS = 12                  # เดินโลกกี่ปีเพื่อนับมารบุกต่อแดนต่อรอบโลก
RAID_ROUNDS = 8                        # สั่งบุกกี่ครั้งเพื่อดูว่าผู้บุกหมุนเวียน


def _raider(e):
    return e.target if e.outcome == "ปราบมารได้" else e.actor


def test_mara_raid_cadence_follows_the_world_clock():
    """MARA_RAID_P ทอยครั้งเดียวต่อแดนมนุษย์ต่อรอบโลก — มารบุกในแดนหนึ่งต้องไม่เกินหนึ่งครั้งต่อรอบโลก
    บั๊กเดิม: ทอยทุกเทิร์นของตัวละครใน _step (seed 42 ใน 100 ปี 1,754 ครั้ง)"""
    from tiandao import config as C
    from tiandao import sim as S
    with contextlib.redirect_stdout(io.StringIO()):
        sim = S.Sim(seed=CYCLE_SEED)
        while sim.day < RAID_TRIAL_YEARS * 365:
            if sim.step() is None:
                break
    raids = [e for e in sim.log if e.kind == "มารบุก"]
    per_tick = collections.Counter((e.world_id, e.day // C.WORLD_TICK_DAYS) for e in raids)
    over = [(k, v) for k, v in per_tick.items() if v > 1]
    msg = f"  มารบุก {len(raids)} ครั้งใน {RAID_TRIAL_YEARS} ปี · แดน-รอบที่บุกเกินหนึ่งครั้ง {len(over)} เช่น {over[:5]}"
    assert raids, "ไม่มีมารบุกเลย (กลไกหายไป):\n" + msg
    assert not over, "มารบุกเกินหนึ่งครั้งต่อแดนต่อรอบโลก (ทอยตามเทิร์นตัวละคร):\n" + msg


def test_mara_raiders_rotate():
    """ผู้บุกต้องหมุนเวียน — ขั้นใกล้เหยื่อ → บุกครั้งล่าสุดนานที่สุด (raided_day) → cid ไม่สุ่มเพิ่ม
    บั๊กเดิม: เสมอกันเอา cid น้อยเสมอ มารคนเดิมถูกส่งมาทุกครั้ง (seed 42: 3 คนแรกถือ 35%) · มารขั้นเดียวกันหลายตน ต้องได้ผู้บุกหลายคน"""
    from tiandao import sim as S
    with contextlib.redirect_stdout(io.StringIO()):
        sim = S.Sim(seed=CYCLE_SEED)
        w = next(x for x in sim.worlds if x.kind == "mortal" and x.lateral and sim.world(x.lateral[0]).kind == "mara")
        mara = [c for c in sim.living_in(w.lateral[0]) if c.age(sim.day) >= 14][:4]
        for c in mara:
            c.realm = 3
        others = {c.cid for c in mara}
        for c in sim.living_in(w.lateral[0]):
            if c.cid not in others:
                c.realm = 0                   # นอกเกณฑ์ผู้บุก (ขั้น < 2)
        w.defense_array = 0.0
        raiders = []
        for _ in range(RAID_ROUNDS):
            n = len(sim.log)
            sim.mara_raid(w, 0, sim.rng)
            raiders += [_raider(e) for e in sim.log[n:] if e.kind == "มารบุก"]
            sim.day += 1
    msg = f"  ผู้บุก {raiders} · มารขั้น 3 {sorted(others)} · raided_day {[getattr(c, 'raided_day', None) for c in mara]}"
    assert len(raiders) >= RAID_ROUNDS // 2, "สั่งบุกแล้วไม่เกิดเหตุการณ์:\n" + msg
    assert len(set(raiders)) > 1, "ผู้บุกคนเดิมทุกครั้ง:\n" + msg


def test_childhood_history_seq_is_always_a_number():
    """ประวัติวัยเด็ก (Character.childhood) ต้องมี seq เป็นตัวเลขทุกปี — ชั้นจิตใจเรียงสมุดชีวิตด้วย int(seq)
    (mind/manager._backfill_childhood) บั๊ก: ตอนตัดเสียงรบกวนวัยเด็ก ปีที่ไม่บันทึกเหตุการณ์ได้ seq = None → test_minds พัง"""
    from tiandao import sim as S
    with contextlib.redirect_stdout(io.StringIO()):
        sim = S.Sim(seed=CYCLE_SEED)
        while sim.day < 6 * 365:
            if sim.step() is None:
                break
    rows = [(c.cid, h) for c in sim.cast for h in (getattr(c, "childhood", None) or []) if isinstance(h, dict)]
    bad = [(cid, h.get("age"), h.get("seq")) for cid, h in rows if not isinstance(h.get("seq"), int)]
    assert rows, "ไม่มีประวัติวัยเด็กให้ตรวจ"
    assert not bad, f"ประวัติวัยเด็กที่ seq ไม่ใช่ตัวเลข {len(bad)} จาก {len(rows)} เช่น {bad[:5]}"
