import re

with open('tiandao/sim.py', 'r', encoding='utf-8') as f:
    content = f.read()

new_logic = '''        if k == "เหตุการณ์เมือง":
            if getattr(a, "hp", 0) <= 0: return "ทั่วไป", "บาดเจ็บหนักเกินกว่าจะเดินในเมือง", d
            
            if a.city_id >= 0 and hasattr(C, "CITIES"):
                city = next((c for c in C.CITIES if c["id"] == a.city_id), None)
                if city:
                    safety = city["attributes"]["safety"]
                    jianghu = city["attributes"]["jianghu"]
                    wealth = city["attributes"]["wealth"]
                    info = city["attributes"]["info"]
                    faction = city["dominant_faction"]
                    
                    # ⚔️ คำนวณพลังรบรวม (ตัวเอก + อาวุธ + สหาย)
                    combat_power = R.power(a, w)
                    if a.inventory.get("อาวุธ") == "กระบี่เหล็กเย็น":
                        combat_power += 25
                    
                    c_bonus = {"แม่นางเยว่เอ๋อร์": 10, "จ้าวเถี่ยซาน": 40, "ศิษย์พี่ใหญ่เซี่ย": 20}
                    for comp in getattr(a, "companions", []):
                        combat_power += c_bonus.get(comp, 0)
                    
                    pre_msg = ""
                    # [ทักษะสหาย] หมอยาปรุงยาให้ฟรี
                    if "แม่นางเยว่เอ๋อร์" in getattr(a, "companions", []) and a.inventory.get("ยาสมานแผล", 0) == 0:
                        a.inventory["ยาสมานแผล"] = a.inventory.get("ยาสมานแผล", 0) + 1
                        pre_msg += "🌸 [ทักษะสหาย] แม่นางเยว่เอ๋อร์ปรุง 'ยาสมานแผล' ให้ฟรี 1 ขวด! "
                    
                    def check_hp(msg_prefix):
                        msg_append = ""
                        if getattr(a, "hp", 100) < (getattr(a, "max_hp", 100) * 0.4) and a.inventory.get("ยาสมานแผล", 0) > 0:
                            a.inventory["ยาสมานแผล"] -= 1
                            old_hp = a.hp
                            a.hp = min(a.max_hp, a.hp + 30)
                            msg_append = f" 🤖 [สัญชาตญาณ] บาดเจ็บสาหัสจึงดื่มยาสมานแผล ฟื้นฟู +{a.hp - old_hp} HP (เหลือยา {a.inventory['ยาสมานแผล']} ขวด)"
                            
                        if getattr(a, "hp", 100) <= 0:
                            self.kill(a, "ลมปราณแตกซ่านสิ้นชีพในเมือง")
                            msg_append += " 💀 (และดับสูญคายุทธภพ)"
                        return pre_msg + msg_prefix + msg_append
                    
                    if rng.randint(1, 100) > safety:
                        msg = "⚠️ [เหตุการณ์อันตราย] ปาร์ตี้ของคุณโดนพรรคมารและโจรป่าปิดล้อมดักโจมตี!"
                        enemy_power = rng.randint(30, max(80, int(w.tier*40)))
                        
                        if combat_power >= enemy_power:
                            a.money[w.wid] = a.money.get(w.wid, 0) + 100
                            a.insight += 0.5
                            R.cultivate(a, gap)
                            msg = "🦅 [ชัยชนะ] ด้วยกำลังเสริมจากสหายร่วมทีม ท่านสยบศัตรูได้! ได้ +100 เงินและ EXP"
                            return "อันตราย", pre_msg + msg, d
                        else:
                            dmg = 40
                            msg_add = ""
                            if "จ้าวเถี่ยซาน" in getattr(a, "companions", []):
                                dmg = dmg // 2
                                msg_add = " 🛡️ [ทักษะสหาย] จ้าวเถี่ยซานใช้โล่เหล็กรับแรงกระแทก ดาเมจลดลงครึ่งหนึ่ง!"
                            a.hp -= dmg
                            a.money[w.wid] = max(0, a.money.get(w.wid, 0) - 50)
                            msg = f"💥 [พ่ายแพ้] ปาร์ตี้แตกกระเจิง เสีย -{dmg} HP และเสีย -50 เงิน{msg_add}"
                            msg = check_hp(msg)
                            return "อันตราย", msg, d
                        
                    if rng.randint(1, 100) <= jianghu:
                        sub = rng.choice(["tavern_friend", "buy_weapon", "train"])
                        if sub == "tavern_friend":
                            if len(getattr(a, "companions", [])) < 2:
                                new_f = rng.choice(["แม่นางเยว่เอ๋อร์", "จ้าวเถี่ยซาน", "ศิษย์พี่ใหญ่เซี่ย"])
                                if new_f not in getattr(a, "companions", []):
                                    a.companions.append(new_f)
                                    roles = {"แม่นางเยว่เอ๋อร์": "หมอยา", "จ้าวเถี่ยซาน": "นักคุ้มกันภัย", "ศิษย์พี่ใหญ่เซี่ย": "สายสืบ"}
                                    msg = f"🤝 [สหายใหม่] {new_f} (อาชีพ: {roles[new_f]}) ยินดีร่วมเดินทางไปกับท่าน!"
                                else:
                                    msg = "🍃 [เหตุการณ์ยุทธภพ] เจอคนรู้จักเก่า นั่งดื่มเหล้าทักทายกันเฉยๆ"
                            else:
                                msg = "🎒 [ระบบ] ปาร์ตี้ของท่านเต็มแล้ว (2 คน) จึงได้เพียงพูดคุยแลกเปลี่ยนสุรา"
                        elif sub == "buy_weapon":
                            if a.money.get(w.wid, 0) >= 150 and a.inventory.get("อาวุธ") is None:
                                a.money[w.wid] -= 150
                                a.inventory["อาวุธ"] = "กระบี่เหล็กเย็น"
                                msg = "🛍️ [คลังไอเทม] สวมใส่ 'กระบี่เหล็กเย็น' สำเร็จ พลังโจมตีเพิ่มขึ้น"
                            else:
                                msg = "🍃 [เหตุการณ์ยุทธภพ] พ่อค้าเร่ขาย 'กระบี่เหล็กเย็น' (ราคา 150) แต่ท่านไม่ได้ซื้อ"
                        elif sub == "train":
                            a.insight += 0.4
                            R.cultivate(a, gap)
                            msg = "🥋 [เหตุการณ์ยุทธภพ] นั่งสมาธิร่วมกันในหุบเขาเพื่อโคจรลมปราณ ได้รับ EXP"
                        
                        return "วิถียุทธ", pre_msg + msg, d

                    if rng.randint(1, 100) <= wealth:
                        potion_price = 40
                        msg_add = ""
                        if "ศิษย์พี่ใหญ่เซี่ย" in getattr(a, "companions", []):
                            potion_price = 20
                            msg_add = " 📜 [ทักษะสหาย] ศิษย์พี่ใหญ่เซี่ยสืบรู้ราคาต้นทุน ต่อราคาค่ายาเหลือ 20 เงิน!"
                            
                        if a.money.get(w.wid, 0) >= potion_price and a.inventory.get("ยาสมานแผล", 0) < 2:
                            a.money[w.wid] -= potion_price
                            a.inventory["ยาสมานแผล"] += 1
                            msg = f"🎒 [คลังไอเทม] ซื้อยาสมานแผลสำเร็จ (จ่าย {potion_price} เงิน){msg_add}"
                        else:
                            msg = f"🍃 [เหตุการณ์การค้า] เจอร้านขาย 'ยาสมานแผล' (ราคา {potion_price}){msg_add} แต่ไม่ได้ซื้อ"
                            
                        return "การค้า", pre_msg + msg, d
                        
                    # ทั่วไป
                    a.hp = min(getattr(a, "max_hp", 100), getattr(a, "hp", 100) + 10)
                    msg = "🍃 [เหตุการณ์ทั่วไป] ปาร์ตี้เดินทางผ่านทุ่งหญ้าอย่างสงบ ทุกคนร่วมร้องเพลงแลกเปลี่ยนวิชา ฟื้นฟู +10 HP"
                    return "ความสงบ", pre_msg + msg, d
            return "ทั่วไป", f"{a.name} เดินเล่นในเมือง", d
'''

pattern = re.compile(r'(        if k == "เหตุการณ์เมือง":.*?            return "ทั่วไป", f"\{a\.name\} เดินเล่นในเมือง", d\n)', re.DOTALL)

def replacer(match):
    return new_logic + '\n'

new_content = pattern.sub(replacer, content)

if new_content != content:
    with open('tiandao/sim.py', 'w', encoding='utf-8') as f:
        f.write(new_content)
    print("sim.py updated successfully.")
else:
    print("Regex failed to match!")
