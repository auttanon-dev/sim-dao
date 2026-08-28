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
                    
                    if not hasattr(a, "companions") or not isinstance(a.companions, dict):
                        a.companions = {}
                    if not hasattr(a, "nemeses") or not isinstance(a.nemeses, dict):
                        a.nemeses = {}
                        
                    # ⚔️ คำนวณพลังรบรวม (ตัวเอก + อาวุธ + สหาย)
                    combat_power = R.power(a, w)
                    if a.inventory.get("อาวุธ") == "กระบี่เหล็กเย็น":
                        combat_power += 25
                    
                    c_bonus = {"แม่นางเยว่เอ๋อร์": 10, "จ้าวเถี่ยซาน": 40, "ศิษย์พี่ใหญ่เซี่ย": 20, "แม่นางเยี่ยเสวี่ย": 30}
                    for comp in a.companions.keys():
                        combat_power += c_bonus.get(comp, 0)
                    
                    pre_msg = ""
                    # [ทักษะสหาย] หมอยาปรุงยาให้ฟรี
                    if "แม่นางเยว่เอ๋อร์" in a.companions and a.inventory.get("ยาสมานแผล", 0) == 0:
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
                        
                    # [💡 TRIGGER พิเศษ: การตามล่าของศัตรูคู่อาฆาต]
                    dangerous_nemeses = [n for n, info in a.nemeses.items() if info.get("hatred", 0) >= 100]
                    if dangerous_nemeses and rng.randint(1, 100) > safety:
                        hunter = rng.choice(dangerous_nemeses)
                        h_info = a.nemeses[hunter]
                        msg = f"🚨 [เผชิญหน้าคู่แค้น] {hunter} ({h_info['title']}) ปรากฏตัวขวางหน้าหมายเอาชีวิต!"
                        if combat_power >= h_info["power"]:
                            msg += f" 🦅 [ล้างแค้นสำเร็จ] ท่านโค่น {hunter} ลงได้สะใจ! (+150 เงิน, ได้ EXP)"
                            a.money[w.wid] = a.money.get(w.wid, 0) + 150
                            a.insight += 1.0
                            R.cultivate(a, gap)
                            del a.nemeses[hunter]
                            return "อันตราย", pre_msg + msg, d
                        else:
                            msg += f" 💥 [พ่ายแพ้คู่แค้น] ท่านพลาดท่าบาดเจ็บสาหัส เสีย -50 HP และถูกชิงทรัพย์ -100 เงิน"
                            a.hp -= 50
                            a.money[w.wid] = max(0, a.money.get(w.wid, 0) - 100)
                            a.nemeses[hunter]["hatred"] = 60
                            msg = check_hp(msg)
                            return "อันตราย", msg, d
                    
                    if rng.randint(1, 100) > safety:
                        msg = "⚠️ [เหตุการณ์อันตราย] ปาร์ตี้ของคุณโดนพรรคมารและโจรป่าดักโจมตี!"
                        enemy_power = rng.randint(40, max(90, int(w.tier*40)))
                        
                        if combat_power >= enemy_power:
                            a.money[w.wid] = a.money.get(w.wid, 0) + 100
                            a.insight += 0.5
                            R.cultivate(a, gap)
                            
                            # สร้างศัตรูคู่อาฆาตใหม่
                            if "เถาตี้" not in a.nemeses:
                                a.nemeses["เถาตี้"] = {"title": "จ้าวค่ายโจรเหล็ก", "power": 45, "hatred": 40}
                                msg = "🦅 [ชัยชนะ] ท่านสยบหัวหน้าโจรป่าได้สำเร็จ แต่มันอาฆาตหนีไปกบดาน! (สร้างคู่แค้นใหม่)"
                            else:
                                a.nemeses["เถาตี้"]["hatred"] = min(100, a.nemeses["เถาตี้"]["hatred"] + 40)
                                msg = f"🦅 [ชัยชนะ] ท่านสยบโจรป่าได้ แต่เถาตี้ยิ่งแค้นท่านหนักขึ้น! (Hatred: {a.nemeses['เถาตี้']['hatred']}/100)"
                                
                            # เพิ่มความสัมพันธ์
                            if a.companions:
                                for c in a.companions.keys():
                                    a.companions[c] = min(100, a.companions[c] + 10)
                                msg += " 💞 ทุกคนเชื่อมั่นกันมากขึ้น (+10 Affection)"
                            return "อันตราย", pre_msg + msg, d
                        else:
                            # เช็กคนรักเสียสละชีวิต
                            saved_by_love = None
                            for c, aff in list(a.companions.items()):
                                if aff >= 80:
                                    saved_by_love = c
                                    break
                            
                            if saved_by_love:
                                del a.companions[saved_by_love]
                                msg = f"💥 [พ่ายแพ้] ปาร์ตี้พ่ายแพ้... 💖 [ปาฏิหาริย์แห่งรัก] {saved_by_love} กระโดดขวางวิถีกระบี่ ยอมเจ็บแทนท่าน! (ออกจากปาร์ตี้ไปรักษาตัว)"
                                msg = check_hp(msg)
                                return "อันตราย", pre_msg + msg, d
                                
                            dmg = 50
                            msg_add = ""
                            if "จ้าวเถี่ยซาน" in a.companions:
                                dmg = dmg // 2
                                msg_add = " 🛡️ [ทักษะสหาย] จ้าวเถี่ยซานรับแรงกระแทก ดาเมจลดลงครึ่งหนึ่ง!"
                            a.hp -= dmg
                            a.money[w.wid] = max(0, a.money.get(w.wid, 0) - 40)
                            msg = f"💥 [พ่ายแพ้] ปาร์ตี้พ่ายแพ้ เสีย -{dmg} HP และเสีย -40 เงิน{msg_add}"
                            msg = check_hp(msg)
                            return "อันตราย", msg, d
                        
                    if rng.randint(1, 100) <= jianghu:
                        subs = ["tavern_friend", "buy_weapon", "train", "tournament"]
                        if a.companions:
                            subs.append("drink_tea")
                        sub = rng.choice(subs)
                        
                        if sub == "tournament":
                            if "คุณชายมู่" not in a.nemeses:
                                a.nemeses["คุณชายมู่"] = {"title": "กระบี่วารีคลั่ง", "power": 35, "hatred": 30}
                            h_info = a.nemeses["คุณชายมู่"]
                            msg = f"🥋 [การประลอง] ท่านร่วมประลองยุทธเจอกับ คุณชายมู่ ({h_info['title']})"
                            if combat_power >= h_info["power"]:
                                a.insight += 0.4
                                R.cultivate(a, gap)
                                a.nemeses["คุณชายมู่"]["hatred"] = min(100, h_info["hatred"] + 35)
                                msg += f" 🏆 [ชนะประลอง] ท่านชนะและได้อันดับเหนือกว่า เขาเสียหน้าและเกลียดท่านมากขึ้น! (Hatred: {a.nemeses['คุณชายมู่']['hatred']}/100)"
                            else:
                                a.hp -= 10
                                msg += f" 🥈 [แพ้ประลอง] ท่านพ่ายแพ้ให้เพลงกระบี่รวดเร็ว เสีย -10 HP"
                                msg = check_hp(msg)
                        elif sub == "drink_tea":
                            comp = rng.choice(list(a.companions.keys()))
                            choice = rng.choice(["share_gold", "talk_martial", "ignore"])
                            if choice == "share_gold" and a.money.get(w.wid, 0) >= 50:
                                a.money[w.wid] -= 50
                                a.companions[comp] = min(100, a.companions[comp] + 25)
                                msg = f"🍻 [ความสัมพันธ์] ชวน {comp} ดื่มชาและซื้อของให้ (-50 เงิน) 💞 (+25 Affection)"
                            elif choice == "talk_martial":
                                a.insight += 0.3
                                R.cultivate(a, gap)
                                a.companions[comp] = min(100, a.companions[comp] + 15)
                                msg = f"🍻 [ความสัมพันธ์] แลกเปลี่ยนวิชากับ {comp} ได้ EXP 💞 (+15 Affection)"
                            else:
                                a.companions[comp] = max(0, a.companions[comp] - 15)
                                msg = f"🍻 [ความสัมพันธ์] ดื่มชากับ {comp} แต่ละเลย 💔 (-15 Affection)"
                        elif sub == "tavern_friend":
                            if len(a.companions) < 2:
                                new_f = rng.choice(["แม่นางเยว่เอ๋อร์", "จ้าวเถี่ยซาน", "ศิษย์พี่ใหญ่เซี่ย", "แม่นางเยี่ยเสวี่ย"])
                                if new_f not in a.companions:
                                    a.companions[new_f] = 20
                                    msg = f"🤝 [สหายใหม่] {new_f} ยินดีร่วมเดินทางไปกับท่าน! (ความสนิท 20)"
                                else:
                                    msg = "🍃 [เหตุการณ์ยุทธภพ] เจอคนรู้จักเก่า นั่งดื่มเหล้าทักทายกันเฉยๆ"
                            else:
                                msg = "🎒 [ระบบ] ปาร์ตี้เต็มแล้ว จึงได้เพียงพูดคุยแลกเปลี่ยนสุรา"
                        elif sub == "buy_weapon":
                            if a.money.get(w.wid, 0) >= 150 and a.inventory.get("อาวุธ") is None:
                                a.money[w.wid] -= 150
                                a.inventory["อาวุธ"] = "กระบี่เหล็กเย็น"
                                msg = "🛍️ [คลังไอเทม] สวมใส่ 'กระบี่เหล็กเย็น' สำเร็จ พลังโจมตีเพิ่มขึ้น"
                            else:
                                msg = "🍃 [เหตุการณ์ยุทธภพ] พ่อค้าเร่ขาย 'กระบี่เหล็กเย็น' (ราคา 150) แต่ไม่ได้ซื้อ"
                        elif sub == "train":
                            a.insight += 0.4
                            R.cultivate(a, gap)
                            msg = "🥋 [เหตุการณ์ยุทธภพ] นั่งสมาธิร่วมกันในหุบเขา ได้รับ EXP"
                        
                        return "วิถียุทธ", pre_msg + msg, d

                    if rng.randint(1, 100) <= wealth:
                        if a.companions and rng.random() > 0.5:
                            comp = rng.choice(list(a.companions.keys()))
                            if a.money.get(w.wid, 0) >= 40:
                                a.money[w.wid] -= 40
                                a.companions[comp] = min(100, a.companions[comp] + 20)
                                msg = f"🛍️ [ความสัมพันธ์] จ่าย 40 เงินซื้อสมุนไพรให้ {comp} 💞 (+20 Affection)"
                            else:
                                msg = f"🛍️ [ความสัมพันธ์] {comp} อยากได้สมุนไพรแต่ท่านเงินไม่พอ"
                            return "การค้า", pre_msg + msg, d
                            
                        potion_price = 40
                        msg_add = ""
                        if "ศิษย์พี่ใหญ่เซี่ย" in a.companions:
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
                    msg = "🍃 [เหตุการณ์ทั่วไป] ปาร์ตี้เดินทางผ่านทุ่งหญ้าอย่างสงบ แลกเปลี่ยนวิชา ฟื้นฟู +10 HP"
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
