import re

with open('tiandao/sim.py', 'r', encoding='utf-8') as f:
    content = f.read()

new_resolutions = '''        # --- อีเวนท์สายอาชีพใหม่ ---
        if k == "สะสมบุญบารมี":
            a.merit += rng.uniform(5.0, 15.0)
            a.insight += rng.uniform(0.1, 0.5)
            R.cultivate(a, gap)
            return "บุญบารมี", f"{a.name}ออกโปรดสัตว์ สะสมบุญบารมีเพิ่มขึ้น", d
            
        if k == "ลาดตระเวน":
            a.money[w.wid] = a.money.get(w.wid, 0) + 10
            return "ลาดตระเวน", f"{a.name}ออกลาดตระเวนรักษาความสงบ ได้รับเบี้ยหวัด", d
            
        if k == "เปิดประมูล":
            if a.city_id >= 0:
                profit = rng.randint(100, 500)
                a.money[w.wid] = a.money.get(w.wid, 0) + profit
                return "ประมูล", f"{a.name}จัดงานประมูลในเมือง ได้กำไร {profit} เหรียญทอง", d
            return "ค้าขาย", f"{a.name}เร่ขายของทั่วไป", d

        if k == "จับกุมอาชญากร":
            if not t: return "ล้มเหลว", "ไม่พบอาชญากร", d
            if R.power(a, w) > R.power(t, w):
                d["เป้าหมาย"] = f"จับกุม {t.name} สำเร็จ"
                bounty = rng.randint(20, 100)
                a.money[w.wid] = a.money.get(w.wid, 0) + bounty
                self.kill(t, f"ถูกจับกุมโดย {a.name}")
                return "จับกุม", f"{a.name}บุกจับกุม {t.name} ได้รับรางวัล {bounty}", d
            else:
                self.set_bond(t, a.cid, min(-10, self.get_bond(t, a.cid) - 20))
                return "ล้มเหลว", f"{a.name}พยายามจับกุม {t.name} แต่สู้ไม่ได้", d

        if k == "ลอบสังหาร":
            if not t: return "ล้มเหลว", "ไม่มีเป้าหมาย", d
            if a.profession in ("นักบวช", "นักพรต"):
                a.karma += 50.0 # ฆ่าคนกรรมพุ่ง
            
            # โอกาสสำเร็จขึ้นกับพลัง
            if R.power(a, w) * 1.5 > R.power(t, w):
                self.kill(t, f"ถูกลอบสังหารโดย {a.name}")
                a.money[w.wid] = a.money.get(w.wid, 0) + rng.randint(50, 200)
                d["สังหาร"] = f"{t.name} ถูกลิดรอนวิญญาณ"
                return "สังหาร", f"{a.name}ลอบสังหาร {t.name} สำเร็จ", d
            else:
                self.set_bond(t, a.cid, min(-10, self.get_bond(t, a.cid) - 50))
                return "ล้มเหลว", f"{a.name}ลอบสังหาร {t.name} พลาด โดนหมายหัวกลับ", d

        if k == "ดักปล้น":
            if not t: return "ล้มเหลว", "ไม่มีเป้าหมาย", d
            if R.power(a, w) > R.power(t, w):
                stolen = t.money.get(w.wid, 0) // 2
                t.money[w.wid] = t.money.get(w.wid, 0) - stolen
                a.money[w.wid] = a.money.get(w.wid, 0) + stolen
                self.set_bond(t, a.cid, min(-10, self.get_bond(t, a.cid) - 30))
                return "ปล้นสำเร็จ", f"{a.name}ดักปล้น {t.name} ได้เงิน {stolen}", d
            else:
                self.set_bond(t, a.cid, min(-10, self.get_bond(t, a.cid) - 10))
                return "ล้มเหลว", f"{a.name}พยายามปล้น {t.name} แต่โดนตีกลับ", d

        if k == "ทำนายชะตา":
            if not t: return "ล้มเหลว", "ไม่มีผู้ว่าจ้าง", d
            a.insight += rng.uniform(0.1, 0.5)
            t.insight += rng.uniform(0.1, 0.3)
            fee = rng.randint(5, 20)
            if t.money.get(w.wid, 0) >= fee:
                t.money[w.wid] -= fee
                a.money[w.wid] = a.money.get(w.wid, 0) + fee
            return "ทำนาย", f"{a.name}ตรวจดวงชะตาให้ {t.name} ชี้แนะหนทาง", d

        if k == "ขายข่าวลับ":
            if not t: return "ล้มเหลว", "ไม่มีลูกค้า", d
            fee = rng.randint(10, 50)
            if t.money.get(w.wid, 0) >= fee:
                t.money[w.wid] -= fee
                a.money[w.wid] = a.money.get(w.wid, 0) + fee
                self.set_bond(t, a.cid, max(0, self.get_bond(t, a.cid) + 10))
                return "ข่าวลับ", f"{a.name}ขายข้อมูลสำคัญให้ {t.name}", d
            return "ล้มเหลว", f"{t.name}ไม่มีเงินจ่ายค่าข่าวให้ {a.name}", d
'''

pattern = re.compile(r'(    def resolve\(self, ev, a, t, w, gap, rng\):\n        k, d = ev\["kind"\], \{\})', re.DOTALL)

def replacer(match):
    return match.group(1) + "\n" + new_resolutions

new_content = pattern.sub(replacer, content)

if new_content != content:
    with open('tiandao/sim.py', 'w', encoding='utf-8') as f:
        f.write(new_content)
    print("sim.py updated resolve() successfully.")
else:
    print("Regex failed to match!")
