# ข้อแก้ไขเชิงตีความของรายงาน diagnostic เดิม

2 ตุลาคม 2026 · ไม่มีการเปลี่ยนผลดิบหรือรันใหม่

รายงานเดิมเขียนว่า pricing เปลี่ยนตาม stock และรายได้ที่เพิ่มอาจมาจากราคาสูงขึ้น ประโยคนั้นอธิบายความสามารถของโค้ดทั่วไป แต่ไม่ตรงกับ config ของชุด fixtures นี้

manifest ระบุ `FOOD_PRICE_ELASTICITY = 0.0` และ `FOOD_PRICE = 0.1` ใน frozen `tiandao/food.py` ฟังก์ชัน `_set_prices` คืน price map ว่างเมื่อ elasticity<=0; `price_at` จึงคืน FOOD_PRICE ทุกแห่ง ราคาของทุก variant ในชุดนี้คงที่ 0.1 ทองต่อสำรับ

ดังนั้นรายได้ไร่ที่ต่างกันใน fixtures นี้มาจากปริมาณอาหารที่ซื้อได้/การซื้อเสบียง/ผู้ผลิตที่ได้ pay และ realized transfers ตามกฎเดิม ไม่ใช่การตอบสนองของ dynamic pricing ต่อ effort ต่ำ ชุดนี้ยังไม่พิสูจน์ guard สำหรับ elasticity>0

รายงานเดิมเก็บ byte-for-byte เพื่อรักษา provenance ให้ใช้ erratum นี้ประกอบการอ่าน ค่า farm revenue/pay, unpaid/unmet, ledgers และผล determinism ไม่ถูกเปลี่ยน

อีกข้อจำกัด: e=1 agreement ของ fixtures เทียบ real food kernel ภายใต้ shell ที่ตรึง recruit/release และ hunger-driven relocation/process interruption เหมือนกันทั้งสอง arms ไม่ใช่หลักฐานว่า controller ที่ยังไม่มี implementation เทียบ full production world แล้ว
