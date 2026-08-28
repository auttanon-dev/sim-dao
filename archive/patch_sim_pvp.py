import re

with open('tiandao/sim.py', 'r', encoding='utf-8') as f:
    content = f.read()

pvp_logic = '''
                    # 🤖 💥 [ความล้ำ: ระบบฆ่ากันเองข้ามตัวละคร] 💥
                    if rng.randint(1, 100) <= 15:
                        other_chars = [c for c in self.living_in(a.wid) if c.cid != a.cid]
                        if other_chars:
                            b = rng.choice(other_chars)
                            if not hasattr(b, "companions"): b.companions = {}
                            if not hasattr(b, "nemeses"): b.nemeses = {}
                            
                            # ⚔️ หากเป็นศัตรูคู่อาฆาต เปิดศึกทันที!
                            if b.name in a.nemeses:
                                rival_power = R.power(b, w)
                                if getattr(b, "inventory", {}).get("อาวุธ") == "กระบี่เหล็กเย็น": rival_power += 25
                                
                                msg = f"⚔️ [ศึกสายเลือด] คู่แค้นล้างปฐพี! [{a.name}] และ [{b.name}] บังเอิญพบกัน ทั้งคู่ชักอาวุธเข้าห้ำหั่นกันทันที!"
                                if combat_power >= rival_power:
                                    a.insight += 2.0
                                    a.enemies_defeated = getattr(a, "enemies_defeated", 0) + 1
                                    self.kill(b, f"ถูก {a.name} สังหารในการดวลเดือด")
                                    del a.nemeses[b.name]
                                    msg += f" 🦅 [{a.name}] โค่นศัตรูคู่อาฆาตสำเร็จ!"
                                else:
                                    b.insight += 2.0
                                    b.enemies_defeated = getattr(b, "enemies_defeated", 0) + 1
                                    self.kill(a, f"ถูก {b.name} สังหารในการดวลเดือด")
                                    if a.name in b.nemeses: del b.nemeses[a.name]
                                    msg += f" 💀 [{a.name}] พ่ายแพ้และถูกสังหารโดย [{b.name}]!"
                                return "อันตราย", pre_msg + msg, d
                            
                            # ถ้ายังไม่รู้จักกัน สุ่มความสัมพันธ์
                            if b.name not in a.companions and b.name not in a.nemeses:
                                roll = rng.choice(["love", "rival", "ignore"])
                                if roll == "love":
                                    a.companions[b.name] = 50
                                    b.companions[a.name] = 50
                                    msg = f"💖 [บุพเพสันนิวาส] [{a.name}] และ [{b.name}] พบกันในโรงเตี๊ยมและผูกมิตรกัน สัญญาจะช่วยเหลือซึ่งกันและกัน!"
                                    return "ความสัมพันธ์", pre_msg + msg, d
                                elif roll == "rival":
                                    a.nemeses[b.name] = {"title": "ชาวยุทธ", "power": R.power(b, w), "hatred": 100}
                                    b.nemeses[a.name] = {"title": "ชาวยุทธ", "power": combat_power, "hatred": 100}
                                    msg = f"😡 [ผูกปมแค้น] [{a.name}] ขัดคอกับ [{b.name}] เรื่องแย่งซื้อตำรา ทั้งสองประกาศเป็นศัตรูคู่อาฆาต!"
                                    return "ความสัมพันธ์", pre_msg + msg, d
'''

# Find the exact place to insert it. We will insert it before the Nemesis ambush trigger:
# "                    # [💡 TRIGGER พิเศษ: การตามล่าของศัตรูคู่อาฆาต]"

target = '                    # [💡 TRIGGER พิเศษ: การตามล่าของศัตรูคู่อาฆาต]'

new_content = content.replace(target, pvp_logic + '\n' + target)

with open('tiandao/sim.py', 'w', encoding='utf-8') as f:
    f.write(new_content)

print("sim.py patched with PvP and Romance logic.")
