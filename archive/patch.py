import re

with open('tiandao/sim.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update is_closed flag in step
content = re.sub(
    r'(self\.repopulate\(w, self\.day - w\.checked_day\)\s+)(w\.checked_day = self\.day)',
    r'\1if w.tier == 1:\n                if w.n_alive >= 120:  # C.HEAVEN_POP_LIMIT is 120\n                    w.is_closed = True\n                elif w.n_alive < 120 * 0.8:\n                    w.is_closed = False\n            \2',
    content
)

# 2. Block ascension if gate is closed
content = re.sub(
    r'(if a\.realm < C\.ASCEND_MIN_REALM or w\.up is None:\s+R\.cultivate\(a, gap\)\s+return "[^"]+", f"\{a\.name\}[^"]+", d\s+)(if rng\.random\(\) > C\.ASCEND_P:)',
    r'\1up = self.world(w.up)\n            if up.is_closed and up.tier == 1:\n                return "ประตูปิด", f"{a.name}พยายามทะลวงฟ้า แต่ประตูสวรรค์ถูกปิดกั้น!", d\n            \2',
    content
)

# 3. Child bonuses
content = re.sub(
    r'(child = self\.spawn\(w, age_years=0\)\s+blood = \{\}\s+for kk in C\.BLOODS:\s+v = \(a\.blood\.get\(kk, 0\.0\) \+ t\.blood\.get\(kk, 0\.0\)\) \* CL\.INHERIT_MIX\s+if v > 0\.05:\s+blood\[kk\] = min\(1\.0, v\)\s+if sum\(blood\.values\(\)\) > 1\.0:\s+s = sum\(blood\.values\(\)\)\s+blood = \{kk: v/s for kk, v in blood\.items\(\)\}\s+child\.blood = blood\s+child\.bonds\[a\.cid\] = 10\s+child\.bonds\[t\.cid\] = 10)',
    r'\1\n            p_realm = a.realm + t.realm\n            if p_realm > 0:\n                child.insight += p_realm * 2.0\n                child.refine += p_realm * 2.0\n                d["ทายาทผู้ฝึกตน"] = f"{child.name} ได้รับพรสวรรค์มหาศาลตั้งแต่เกิด!"',
    content
)

# 4. Prejudice in ให้สัญญา
content = re.sub(
    r'(if k == "ให้สัญญา":\s+)a\.bonds\[t\.cid\] = a\.bonds\.get\(t\.cid, 0\) \+ 1\s+t\.bonds\[a\.cid\] = t\.bonds\.get\(a\.cid, 0\) \+ 1',
    r'\1if a.ascends > 0 and t.ascends == 0:\n                a.bonds[t.cid] = a.bonds.get(t.cid, 0) + 1\n                d["อคติ"] = f"{t.name} ยังคงมีอคติกับผู้ทะยานข้ามฟ้า"\n            else:\n                a.bonds[t.cid] = a.bonds.get(t.cid, 0) + 1\n                t.bonds[a.cid] = t.bonds.get(a.cid, 0) + 1',
    content
)

# 5. Prejudice in ถ่ายทอดวิชา
content = re.sub(
    r'(if k == "ถ่ายทอดวิชา":\s+t\.insight \+= 0\.5\s+)t\.bonds\[a\.cid\] = t\.bonds\.get\(a\.cid, 0\) \+ 2',
    r'\1if a.ascends > 0 and t.ascends == 0:\n                t.bonds[a.cid] = t.bonds.get(a.cid, 0) + 0\n                d["อคติ"] = f"{t.name} รับวิชาแต่ไม่ซาบซึ้งใจผู้ทะยานข้ามฟ้า"\n            else:\n                t.bonds[a.cid] = t.bonds.get(a.cid, 0) + 2',
    content
)

# 6. Prejudice in หักหลัง
content = re.sub(
    r'(if k == "หักหลัง":\s+)t\.rivals\[a\.cid\] = t\.rivals\.get\(a\.cid, 0\) \+ 3\s+t\.bonds\.pop\(a\.cid, None\)',
    r'\1dmg = 3\n            if a.ascends > 0 and t.ascends == 0:\n                dmg *= 2\n                d["อคติ"] = f"{t.name} แค้นพวกหน้าใหม่เป็นทวีคูณ"\n            t.rivals[a.cid] = t.rivals.get(a.cid, 0) + dmg\n            t.bonds.pop(a.cid, None)',
    content
)

# 7. Prejudice in ล้างแค้น/ชิงสมบัติ/ประลอง
content = re.sub(
    r'(if k == "ล้างแค้น" and win is a:\s+R\.settle_debt\(a, t\.cid\)\s+)lose\.rivals\[win\.cid\] = lose\.rivals\.get\(win\.cid, 0\) \+ \(2 if k == "ล้างแค้น" else 1\)',
    r'\1dmg = 2 if k == "ล้างแค้น" else 1\n        if win.ascends > 0 and lose.ascends == 0 and k in ("ชิงสมบัติ", "ล้างแค้น", "ประลอง"):\n            dmg *= 2\n            d["อคติ"] = f"{lose.name} เกลียดพวกหน้าใหม่ที่กำเริบเสิบสาน"\n        lose.rivals[win.cid] = lose.rivals.get(win.cid, 0) + dmg',
    content
)

# 8. Add สงครามเบิกฟ้า to single actor actions in resolve (e.g. before k == "ซ่อนตัว" or "ข้ามฟ้า")
content = content.replace(
    r'        if k == "ข้ามฟ้า":',
    r'        if k == "สงครามเบิกฟ้า":\n            up = self.world(w.up) if w.up is not None else None\n            if not up or not up.is_closed:\n                return "ไม่มีเป้าหมาย", f"{a.name}พร้อมทำสงครามเบิกฟ้า แต่ประตูไม่ได้ปิด", d\n            \n            damage = a.realm * 5.0\n            up.defense_array = max(0.0, up.defense_array - damage)\n            d["โจมตีค่ายกล"] = f"พลังค่ายกลแดนเซียนลดลงเหลือ {up.defense_array:.1f}/{up.defense_max}"\n            \n            if up.defense_array <= 0:\n                up.is_closed = False\n                d["ประตูปิดกั้นพังทลาย"] = "แดนเซียนถูกเจาะทะลวง! เผ่าโกลาหลสามารถบุกได้แล้ว!"\n                return "เปิดสวรรค์", f"{a.name}ทำลายค่ายกลแดนเซียนสำเร็จ! ประตูสวรรค์เปิดออก", d\n            else:\n                if rng.random() < 0.3:\n                    self.kill(a, "ทัณฑ์สวรรค์")\n                    return "ตาย", f"{a.name}ถูกทัณฑ์สวรรค์สังหารระหว่างทำสงครามเบิกฟ้า", d\n                return "โจมตีสวรรค์", f"{a.name}นำทัพโจมตีค่ายกลสวรรค์ แต่ยังไม่แตก", d\n\n        if k == "ข้ามฟ้า":'
)

with open('tiandao/sim.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("sim.py patched.")
