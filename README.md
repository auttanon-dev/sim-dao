# Sim Dao — วิถีสวรรค์

โลกจำลองยุทธภพที่เดินเอง: ผู้คนเกิด แก่ ทำนา ค้าขาย แต่งงาน มีลูก ป่วย อดอยาก บำเพ็ญ
ข้ามขั้น ตั้งสำนัก ประลอง ล้างแค้น และตาย — บนแผนที่ 755 สถานที่ใน 118 แดน

ตัวโลกทั้งหมดเขียนด้วย Rust (`simdao_core/`) ส่วน Python มีแค่ตัวห่อ บรรทัดคำสั่ง และหน้าเว็บ

## เริ่มใช้

```bash
pip install maturin fastapi uvicorn
cd simdao_core && maturin develop --release && cd ..

python run.py --years 50                   # โลกใหม่ เดิน 50 ปี แล้วสรุป
python run.py --seed 7 --years 100 --save  # เซฟไว้ที่ out/world.json
python run.py --resume --forever           # เดินต่อไปเรื่อยๆ เซฟทุก 5 ปีของโลก
python app.py                              # หน้าเว็บดูโลกสด http://127.0.0.1:8000
```

จาก Python โดยตรง:

```python
from simdao import World
w = World(seed=7)
w.run_years(10)
w.stats()        # ประชากร สาเหตุการตาย บัญชีอาหาร/ทอง
w.recent(20)     # เหตุการณ์ล่าสุด
w.person(42)     # รายละเอียดคนหนึ่ง
w.save("out/world.json"); w = World.load("out/world.json")
```

## โครงสร้าง

| ที่ | หน้าที่ |
|---|---|
| `simdao_core/src/engine/sim.rs` | สร้างโลก คิวเทิร์น (หนึ่งนัดต่อคน) นาฬิกาโลกรายเดือน บันทึกเหตุการณ์ |
| `simdao_core/src/engine/world.rs` | นาฬิกาโลก: ร่างกาย ฟ้าฝน อาหาร ทอง ธรรมชาติ ปราณฟ้า ครอบครัว สำนัก |
| `simdao_core/src/engine/life.rs` | เกิด ตั้งชื่อ อายุขัย ตั้งครรภ์ คลอด ตาย มรดก ข่าวการตาย |
| `simdao_core/src/engine/act.rs` | เทิร์นของคน: เลือกการกระทำแบบถ่วงน้ำหนักตามความต้องการ แล้วลงมือ เดินทาง |
| `simdao_core/src/engine/cultivation.rs` | บำเพ็ญ ปิดด่าน ข้ามขั้น (กำแพงพลังงาน) ข้ามฟ้า สอนศิษย์ |
| `simdao_core/src/engine/conflict.rs` | ประลอง ล้างแค้น ปล้น จับกุม คุมขัง |
| `simdao_core/src/engine/trades.rs` | หมอรักษาคน ปรุงยาวิเศษ ตีอาวุธ |
| `simdao_core/src/engine/disease.rs` | โรคระบาดแบบ SIR ต่อสถานที่ |
| `simdao_core/src/engine/sect.rs` | ตั้ง เข้า สืบทอด สลายสำนัก |
| `simdao_core/src/engine/config.rs` | ค่าคงที่ทั้งหมดของโลก (ปรับได้ด้วย `World(config={...})`) |
| `simdao_core/src/physics.rs` · `noise.rs` | สมการ (ลอจิสติก แลนเชสเตอร์ ฮอว์กส์ …) และสนามปราณบนผิวดาว |
| `simdao_core/data/world.json` | ข้อมูลคงที่: สถานที่ ถนน ชื่อคน อาชีพ วิถี |
| `simdao/` | ตัวห่อ Python (`World`) และตัวเดินโลกเบื้องหลัง (`Runner`) |
| `run.py` · `app.py` · `web/index.html` | บรรทัดคำสั่ง และหน้าเว็บ |

## กติกาที่โลกนี้ถือ

- **บัญชีปิดเสมอ** — อาหารและทองทุกหน่วยมีที่มาและที่ไปที่มีชื่อ (`stats()` รายงานยอดจริงเทียบยอดตามบัญชี)
- **seed เดียวกันได้โลกเดียวกัน** ทุกเครื่อง และเซฟแล้วโหลดเดินต่อได้เหมือนไม่เคยหยุด
- **ไม่มีอะไรเสกจากอากาศ** — ข้าวมาจากคนทำนาบนที่ดินจำกัด ยาวิเศษมาจากสมุนไพรกับแก่นพลังที่มีคนไปเก็บ
  การข้ามขั้นดูดปราณจากคลังฟ้าของแดน ซึ่งฟื้นแบบลอจิสติกและได้คืนเมื่อผู้บำเพ็ญตาย

## เทสต์

```bash
cd simdao_core && cargo test --release && cd ..
python -m pytest tests
```
