with open('tiandao/sim.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    if line.strip().startswith('if k == "สงครามเบิกฟ้า":') or line.strip().startswith('up = self.world(w.up) if w.up is not None else None') or 'ไม่มีเป้าหมาย' in line or 'โจมตีค่ายกล' in line or 'ประตูปิดกั้นพังทลาย' in line or 'เปิดสวรรค์' in line or 'ทัณฑ์สวรรค์' in line or 'โจมตีสวรรค์' in line:
        # Just use standard tools instead of relying on regex replacement which caused bad spacing
        pass

# Let's just fix it completely using ast or direct string manipulation that doesn't mess up indents
import re
with open('tiandao/sim.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace multiple spaces with proper indentation
# Since the previous fix had a bad block, I'll extract it and rewrite it.
pattern = re.compile(r'(\s*)if k == "สงครามเบิกฟ้า":(.*?)\s*if k == "ข้ามฟ้า":', re.DOTALL)
def replacer(match):
    indent = match.group(1)
    if not indent.startswith('\n'):
        indent = '\n' + indent
    # Just 8 spaces for if k == ... inside esolve
    return '''
        if k == "สงครามเบิกฟ้า":
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

content = pattern.sub(replacer, content)

with open('tiandao/sim.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("sim.py indentation fixed.")
