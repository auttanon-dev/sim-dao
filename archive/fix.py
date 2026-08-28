import re

with open('tiandao/sim.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix the broken replacement string
broken_str = r'if k == "สงครามเบิกฟ้า":\n            up = self.world(w.up) if w.up is not None else None\n            if not up or not up.is_closed:\n                return "ไม่มีเป้าหมาย", f"{a.name}พร้อมทำสงครามเบิกฟ้า แต่ประตูไม่ได้ปิด", d\n            \n            damage = a.realm * 5.0\n            up.defense_array = max(0.0, up.defense_array - damage)\n            d["โจมตีค่ายกล"] = f"พลังค่ายกลแดนเซียนลดลงเหลือ {up.defense_array:.1f}/{up.defense_max}"\n            \n            if up.defense_array <= 0:\n                up.is_closed = False\n                d["ประตูปิดกั้นพังทลาย"] = "แดนเซียนถูกเจาะทะลวง! เผ่าโกลาหลสามารถบุกได้แล้ว!"\n                return "เปิดสวรรค์", f"{a.name}ทำลายค่ายกลแดนเซียนสำเร็จ! ประตูสวรรค์เปิดออก", d\n            else:\n                if rng.random() < 0.3:\n                    self.kill(a, "ทัณฑ์สวรรค์")\n                    return "ตาย", f"{a.name}ถูกทัณฑ์สวรรค์สังหารระหว่างทำสงครามเบิกฟ้า", d\n                return "โจมตีสวรรค์", f"{a.name}นำทัพโจมตีค่ายกลสวรรค์ แต่ยังไม่แตก", d\n\n        if k == "ข้ามฟ้า":'

fixed_str = '''        if k == "สงครามเบิกฟ้า":
            up = self.world(w.up) if w.up is not None else None
            if not up or not up.is_closed:
                return "ไม่มีเป้าหมาย", f"{a.name}พร้อมทำสงครามเบิกฟ้า แต่ประตูไม่ได้ปิด", d
            
            damage = a.realm * 5.0
            up.defense_array = max(0.0, up.defense_array - damage)
            d["โจมตีค่ายกล"] = f"พลังค่ายกลแดนเซียนลดลงเหลือ {up.defense_array:.1f}/{up.defense_max}"
            
            if up.defense_array <= 0:
                up.is_closed = False
                d["ประตูปิดกั้นพังทลาย"] = "แดนเซียนถูกเจาะทะลวง! เผ่าโกลาหลสามารถบุกได้แล้ว!"
                return "เปิดสวรรค์", f"{a.name}ทำลายค่ายกลแดนเซียนสำเร็จ! ประตูสวรรค์เปิดออก", d
            else:
                if rng.random() < 0.3:
                    self.kill(a, "ทัณฑ์สวรรค์")
                    return "ตาย", f"{a.name}ถูกทัณฑ์สวรรค์สังหารระหว่างทำสงครามเบิกฟ้า", d
                return "โจมตีสวรรค์", f"{a.name}นำทัพโจมตีค่ายกลสวรรค์ แต่ยังไม่แตก", d

        if k == "ข้ามฟ้า":'''

content = content.replace(broken_str, fixed_str)

with open('tiandao/sim.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("sim.py fixed.")
