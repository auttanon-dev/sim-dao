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
                    
                    # ⚔️ โบนัสพลังต่อสู้
                    combat_power = R.power(a, w)
                    if a.inventory.get("อาวุธ") == "กระบี่เหล็กเย็น":
                        combat_power += 25
                    
                    def check_hp(msg_prefix):
                        # ใช้ยาอัตโนมัติถ้าเลือดต่ำ
                        msg_append = ""
                        if getattr(a, "hp", 100) < (getattr(a, "max_hp", 100) * 0.4) and a.inventory.get("ยาสมานแผล", 0) > 0:
                            a.inventory["ยาสมานแผล"] -= 1
                            old_hp = a.hp
                            a.hp = min(a.max_hp, a.hp + 30)
                            msg_append = f" 🤖 [สัญชาตญาณ] บาดเจ็บสาหัสจึงดื่มยาสมานแผล ฟื้นฟู +{a.hp - old_hp} HP (เหลือยา {a.inventory['ยาสมานแผล']} ขวด)"
                            
                        if getattr(a, "hp", 100) <= 0:
                            self.kill(a, "ลมปราณแตกซ่านสิ้นชีพในเมือง")
                            msg_append += " 💀 (และดับสูญคายุทธภพ)"
                        return msg_prefix + msg_append
                    
                    if rng.randint(1, 100) > safety:
                        msg = "⚠️ [เหตุการณ์อันตราย] ท่านถูกนักฆ่าและโจรป่าล้อมโจมตีในมุมมืด!"
                        enemy_power = rng.randint(15, max(60, int(w.tier*30)))
                        
                        if combat_power >= enemy_power:
                            a.money[w.wid] = a.money.get(w.wid, 0) + 80
                            a.insight += 0.4
                            R.cultivate(a, gap)
                            msg = "🦅 [ชัยชนะ] ด้วยวรยุทธและอาวุธในมือ ท่านสยบโจรป่าได้! ได้เงิน +80 และ EXP"
                        else:
                            a.hp -= 35
                            a.money[w.wid] = max(0, a.money.get(w.wid, 0) - 60)
                            msg = "💥 [พ่ายแพ้] ศัตรูมีฝีมือเหนือกว่า ท่านถูกฟันบาดเจ็บเสีย -35 HP และถูกชิงทรัพย์ -60 เงิน"
                            msg = check_hp(msg)
                            
                        return "อันตราย", msg, d
                        
                    if rng.randint(1, 100) <= jianghu:
                        sub = rng.choice(["train", "buy_weapon", "duel"])
                        if sub == "train":
                            a.insight += 0.6
                            R.cultivate(a, gap)
                            msg = "🥋 [เหตุการณ์ยุทธภพ] ท่านพบศิลาจารึกเคล็ดวิชาโบราณในป่าไผ่ จึงนั่งสมาธิฝึกฝน ได้รับ EXP มหาศาล"
                        elif sub == "buy_weapon":
                            if a.money.get(w.wid, 0) >= 200 and a.inventory.get("อาวุธ") is None:
                                a.money[w.wid] -= 200
                                a.inventory["อาวุธ"] = "กระบี่เหล็กเย็น"
                                msg = "🛍️ [คลังไอเทม] ท่านซื้อ 'กระบี่เหล็กเย็น' สำเร็จ! (พลังรบเพิ่มขึ้นมาก)"
                            else:
                                msg = "🍃 [เหตุการณ์ยุทธภพ] ร้านอาวุธนำ 'กระบี่เหล็กเย็น' มาขาย (ราคา 200) แต่ท่านไม่ได้ซื้อ"
                        elif sub == "duel":
                            a.insight += 0.25
                            R.cultivate(a, gap)
                            a.hp -= 10
                            msg = "🥋 [เหตุการณ์ยุทธภพ] ชาวยุทธท้องถิ่นท้าดวลฝีมือ ได้รับ EXP แต่บาดเจ็บเสีย -10 HP"
                            msg = check_hp(msg)
                        
                        return "วิถียุทธ", msg, d

                    if rng.randint(1, 100) <= wealth:
                        if a.money.get(w.wid, 0) >= 40 and a.inventory.get("ยาสมานแผล", 0) < 2:
                            a.money[w.wid] -= 40
                            a.inventory["ยาสมานแผล"] += 1
                            msg = "🎒 [คลังไอเทม] เจอร้านขายยา ท่านจึงซื้อ 'ยาสมานแผล' มาตุน 1 ขวด (ราคา 40 เงิน)"
                        else:
                            msg = "🍃 [เหตุการณ์การค้า] เจอร้านขาย 'ยาสมานแผล' (ราคา 40) แต่ท่านตัดสินใจเดินผ่านไป"
                            
                        return "การค้า", msg, d
                        
                    # ทั่วไป
                    if faction == "Imperial":
                        a.hp = min(getattr(a, "max_hp", 100), getattr(a, "hp", 100) + 15)
                        a.insight += 0.1
                        msg = "🏛️ [เหตุการณ์ความสงบ] กองทหารหลวงลาดตระเวนเข้มงวด ท่านโคจรลมปราณพักผ่อน ฟื้นฟู +15 HP และได้ EXP"
                    else:
                        msg = "🍃 [เหตุการณ์ทั่วไป] บรรยากาศในเมืองเป็นไปอย่างราบเรียบ ไม่มีเหตุการณ์พิเศษเกิดขึ้น"
                    return "ความสงบ", msg, d
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
