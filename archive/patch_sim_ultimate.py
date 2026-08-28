import re

with open('tiandao/sim.py', 'r', encoding='utf-8') as f:
    content = f.read()

new_logic = '''        if k == "เหตุการณ์เมือง":
            if getattr(a, "hp", 0) <= 0: return "ทั่วไป", "บาดเจ็บหนักเกินกว่าจะเดินในเมือง", d
            
            a.cities_visited = getattr(a, "cities_visited", 0) + 1
            if hasattr(a, "update_title"): a.update_title()
            
            # 🤖 👶 [ระบบอายุขัยและชราภาพ]
            age_now = a.age(self.day)
            if age_now >= 60:
                a.max_hp = max(50, getattr(a, "max_hp", 100) - 2)
                a.hp = min(getattr(a, "hp", 100), a.max_hp)
                if age_now >= 85 and rng.randint(1, 100) < 15:
                    self.kill(a, f"สิ้นอายุขัยในวัย {age_now} ปี อย่างสงบ")
                    return "ความสงบ", f"🧓🍂 [สิ้นอายุขัย] ปิดตำนานยอดฝีมือ... [{a.name}] สิ้นใจลงด้วยโรคชราในวัย {age_now} ปี", d
            
            if a.city_id >= 0 and hasattr(C, "CITIES"):
                city = next((c for c in C.CITIES if c["id"] == a.city_id), None)
                if city:
                    safety = city["attributes"]["safety"]
                    jianghu = city["attributes"]["jianghu"]
                    wealth = city["attributes"]["wealth"]
                    info = city["attributes"]["info"]
                    faction = city["dominant_faction"]
                    
                    potion_cost = 40
                    disaster = getattr(w, "current_disaster", "ปกติ")
                    if disaster == "กบฏราชสำนัก": safety = max(5, safety - 40)
                    elif disaster == "โรคระบาดใหญ่": potion_cost = 120
                    elif disaster == "สมบัติโบราณปรากฏ": jianghu = min(100, jianghu + 20)
                    
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
                        pre_msg += "🌸 [ทักษะสหาย] แม่นางเยว่เอ๋อร์ปรุง 'ยาสมานแผล' ให้ฟรี! "
                    
                    def check_hp(msg_prefix):
                        msg_append = ""
                        if getattr(a, "hp", 100) < (getattr(a, "max_hp", 100) * 0.4) and a.inventory.get("ยาสมานแผล", 0) > 0:
                            a.inventory["ยาสมานแผล"] -= 1
                            old_hp = a.hp
                            a.hp = min(a.max_hp, a.hp + 30)
                            msg_append = f" 🤖 [สัญชาตญาณ] ดื่มยาสมานแผล ฟื้นฟู +{a.hp - old_hp} HP (เหลือยา {a.inventory['ยาสมานแผล']} ขวด)"
                            
                        if getattr(a, "hp", 100) <= 0:
                            self.kill(a, "สิ้นชีพในการต่อสู้ที่เมือง")
                            msg_append += " 💀 [ข่าวลือยุทธภพ] สิ้นชีพแดนยุทธภพแล้ว!"
                        return pre_msg + msg_prefix + msg_append
                        
                    # 🤖 🏛️ [ระบบก่อตั้งสำนักและการทรยศหักหลัง]
                    if getattr(a, "realm", 1) >= 4 and getattr(a, "sect_name", None) is None and rng.randint(1, 100) < 10:
                        a.sect_name = f"สำนัก{a.name[:3]}"
                        a.sect_role = "เจ้าสำนัก"
                        msg = f"🏯 [ก่อตั้งสำนัก] บารมีแก่กล้า! [{a.name}] สถาปนา [{a.sect_name}] ขึ้น!"
                        # ชวนคน
                        for c in self.living_in(w.wid):
                            if c.cid != a.cid and getattr(c, "sect_name", None) is None and rng.random() < 0.2:
                                c.sect_name = a.sect_name
                                c.sect_role = "ศิษย์ในสำนัก"
                                msg += f" 📜 รับ [{c.name}] เป็นศิษย์"
                        return "วิถียุทธ", pre_msg + msg, d
                        
                    if getattr(a, "sect_role", "") == "ศิษย์ในสำนัก" and rng.randint(1, 100) < 5:
                        masters = [m for m in self.living_in(w.wid) if getattr(m, "sect_name", "") == a.sect_name and getattr(m, "sect_role", "") == "เจ้าสำนัก"]
                        if masters:
                            master = masters[0]
                            if rng.random() < 0.5:
                                self.kill(master, f"ถูกศิษย์ทรยศ {a.name} ลอบสังหารด้วยยาพิษ")
                                a.sect_role = "เจ้าสำนัก"
                                msg = f"☠️ [ศิษย์ทรยศสำเร็จ] [{a.name}] วางยาพิษ [{master.name}] สำเร็จ! สถาปนาตนเป็นเจ้าสำนักคนใหม่!"
                                return "อันตราย", pre_msg + msg, d
                            else:
                                a.hp = max(0, a.hp - 40)
                                a.sect_role = "ศิษย์ทรยศ"
                                msg = f"🛡️ [แผนแตก] เจ้าสำนัก [{master.name}] จับได้! ฟาดฝ่ามือใส่ [{a.name}] ขับออกจากสำนักเป็นศิษย์ทรยศ! (-40 HP)"
                                msg = check_hp(msg)
                                return "อันตราย", msg, d
                        
                    # 🤖 💥 [ความล้ำ: ระบบฆ่ากันเองข้ามตัวละคร & บุพเพ] 💥
                    if rng.randint(1, 100) <= 15:
                        other_chars = [c for c in self.living_in(w.wid) if c.cid != a.cid]
                        if other_chars:
                            b = rng.choice(other_chars)
                            if not hasattr(b, "companions"): b.companions = {}
                            if not hasattr(b, "nemeses"): b.nemeses = {}
                            
                            if b.name in a.nemeses:
                                rival_power = R.power(b, w)
                                if getattr(b, "inventory", {}).get("อาวุธ") == "กระบี่เหล็กเย็น": rival_power += 25
                                msg = f"⚔️ [ศึกสายเลือด] คู่แค้นล้างปฐพี! [{a.name}] และ [{b.name}] ชักอาวุธเข้าห้ำหั่นกัน!"
                                if combat_power >= rival_power:
                                    a.insight += 2.0
                                    a.enemies_defeated = getattr(a, "enemies_defeated", 0) + 1
                                    self.kill(b, f"ถูก {a.name} สังหารในการดวลเดือด")
                                    del a.nemeses[b.name]
                                    msg += f" 🦅 [{a.name}] โค่นศัตรูสำเร็จ!"
                                else:
                                    b.insight += 2.0
                                    b.enemies_defeated = getattr(b, "enemies_defeated", 0) + 1
                                    self.kill(a, f"ถูก {b.name} สังหารในการดวลเดือด")
                                    if a.name in b.nemeses: del b.nemeses[a.name]
                                    msg += f" 💀 [{a.name}] ถูกสังหารโดย [{b.name}]!"
                                return "อันตราย", pre_msg + msg, d
                            
                            if b.name not in a.companions and b.name not in a.nemeses:
                                if getattr(a, "moral", 0) * getattr(b, "moral", 0) >= 0: # ธรรมะเจอธรรมะ
                                    a.companions[b.name] = 80
                                    b.companions[a.name] = 80
                                    msg = f"💖 [แต่งงาน] [{a.name}] และ [{b.name}] พบกันที่ {city['name_th']} และเข้าพิธีวิวาห์!"
                                    
                                    # 👶 กำเนิดทายาท
                                    if rng.random() < 0.5:
                                        child = self.spawn(w)
                                        child.parent_name = a.name
                                        child.generation = getattr(a, "generation", 1) + 1
                                        child.money[w.wid] = a.money.get(w.wid, 0) // 2
                                        msg += f" 🍼 [สายเลือดสืบทอด] ให้กำเนิดทายาทชื่อ [{child.name}] (รุ่นที่ {child.generation})!"
                                    return "ความสัมพันธ์", pre_msg + msg, d
                                else:
                                    a.nemeses[b.name] = {"title": getattr(b, "title", ""), "power": R.power(b, w), "hatred": 100}
                                    b.nemeses[a.name] = {"title": getattr(a, "title", ""), "power": combat_power, "hatred": 100}
                                    msg = f"😡 [ศึกข้ามอุดมการณ์] [{a.name}] ประจันหน้ากับ [{b.name}] ฝ่ายธรรมะและอธรรมไม่มีวันอยู่ร่วมโลก! (ผูกปมแค้น)"
                                    return "ความสัมพันธ์", pre_msg + msg, d
                        
                    # [💡 TRIGGER พิเศษ: การตามล่าของศัตรูคู่อาฆาต]
                    dangerous_nemeses = [n for n, info in a.nemeses.items() if info.get("hatred", 0) >= 100]
                    if dangerous_nemeses and rng.randint(1, 100) > safety:
                        hunter = rng.choice(dangerous_nemeses)
                        h_info = a.nemeses[hunter]
                        msg = f"🚨 [เผชิญหน้าคู่แค้น] {hunter} ({h_info.get('title', '')}) ปรากฏตัวขวางหน้าหมายเอาชีวิต!"
                        if combat_power >= h_info.get("power", 0):
                            msg += f" 🦅 [ล้างแค้นสำเร็จ] ท่านโค่น {hunter} ลงได้สะใจ! (+150 เงิน, ได้ EXP)"
                            a.money[w.wid] = a.money.get(w.wid, 0) + 150
                            a.insight += 1.2
                            a.enemies_defeated = getattr(a, "enemies_defeated", 0) + 1
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
                        msg = "⚠️ [เหตุการณ์อันตราย] ปาร์ตี้ของคุณโดนโจรป่าดักโจมตี!"
                        enemy_power = rng.randint(40, max(90, int(w.tier*40)))
                        
                        if combat_power >= enemy_power:
                            a.money[w.wid] = a.money.get(w.wid, 0) + 100
                            a.insight += 0.5
                            a.enemies_defeated = getattr(a, "enemies_defeated", 0) + 1
                            R.cultivate(a, gap)
                            
                            if "เถาตี้" not in a.nemeses:
                                a.nemeses["เถาตี้"] = {"title": "จ้าวค่ายโจรเหล็ก", "power": 45, "hatred": 40}
                                msg = "🦅 [ชัยชนะ] ท่านสยบหัวหน้าโจรป่าได้สำเร็จ แต่มันอาฆาตหนีไปกบดาน! (สร้างคู่แค้น)"
                            else:
                                a.nemeses["เถาตี้"]["hatred"] = min(100, a.nemeses["เถาตี้"]["hatred"] + 40)
                                msg = f"🦅 [ชัยชนะ] ท่านสยบโจรป่าได้ แต่เถาตี้ยิ่งแค้นท่าน! (Hatred: {a.nemeses['เถาตี้']['hatred']}/100)"
                                
                            if a.companions:
                                for c in a.companions.keys():
                                    if type(a.companions[c]) == int: a.companions[c] = min(100, a.companions[c] + 10)
                                msg += " 💞 (+10 Affection)"
                            return "อันตราย", pre_msg + msg, d
                        else:
                            saved_by_love = None
                            for c, aff in list(a.companions.items()):
                                if type(aff) == int and aff >= 80:
                                    saved_by_love = c
                                    break
                            
                            if saved_by_love:
                                del a.companions[saved_by_love]
                                msg = f"💥 [พ่ายแพ้] 💖 [ปาฏิหาริย์แห่งรัก] {saved_by_love} กระโดดขวางวิถีกระบี่ ยอมเจ็บแทนท่าน! (ออกจากปาร์ตี้ไป)"
                                msg = check_hp(msg)
                                return "อันตราย", pre_msg + msg, d
                                
                            dmg = 50
                            msg_add = ""
                            if "จ้าวเถี่ยซาน" in a.companions:
                                dmg = dmg // 2
                                msg_add = " 🛡️ จ้าวเถี่ยซานรับแรงกระแทก!"
                            a.hp -= dmg
                            a.money[w.wid] = max(0, a.money.get(w.wid, 0) - 40)
                            msg = f"💥 [พ่ายแพ้] เสีย -{dmg} HP และเสีย -40 เงิน{msg_add}"
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
                            msg = f"🥋 [การประลอง] ท่านเจอกับ คุณชายมู่"
                            if combat_power >= h_info["power"]:
                                a.insight += 0.4
                                a.enemies_defeated = getattr(a, "enemies_defeated", 0) + 1
                                R.cultivate(a, gap)
                                a.nemeses["คุณชายมู่"]["hatred"] = min(100, h_info["hatred"] + 35)
                                msg += f" 🏆 [ชนะประลอง] เขาเสียหน้าและเกลียดท่านมากขึ้น! (Hatred: {a.nemeses['คุณชายมู่']['hatred']}/100)"
                            else:
                                a.hp -= 10
                                msg += f" 🥈 [แพ้ประลอง] เสีย -10 HP"
                                msg = check_hp(msg)
                        elif sub == "drink_tea":
                            comp = rng.choice(list(a.companions.keys()))
                            choice = rng.choice(["share_gold", "talk_martial", "ignore"])
                            if choice == "share_gold" and a.money.get(w.wid, 0) >= 50:
                                a.money[w.wid] -= 50
                                if type(a.companions[comp]) == int: a.companions[comp] = min(100, a.companions[comp] + 25)
                                msg = f"🍻 [ความสัมพันธ์] ชวน {comp} ดื่มชา 💞 (+25 Affection)"
                            elif choice == "talk_martial":
                                a.insight += 0.3
                                R.cultivate(a, gap)
                                if type(a.companions[comp]) == int: a.companions[comp] = min(100, a.companions[comp] + 15)
                                msg = f"🍻 [ความสัมพันธ์] แลกเปลี่ยนวิชากับ {comp} 💞 (+15 Affection)"
                            else:
                                if type(a.companions[comp]) == int: a.companions[comp] = max(0, a.companions[comp] - 15)
                                msg = f"🍻 [ความสัมพันธ์] ดื่มชากับ {comp} แต่ละเลย 💔 (-15 Affection)"
                        elif sub == "tavern_friend":
                            if len(a.companions) < 2:
                                new_f = rng.choice(["แม่นางเยว่เอ๋อร์", "จ้าวเถี่ยซาน", "ศิษย์พี่ใหญ่เซี่ย", "แม่นางเยี่ยเสวี่ย"])
                                if new_f not in a.companions:
                                    a.companions[new_f] = 20
                                    msg = f"🤝 [สหายใหม่] {new_f} ยินดีร่วมเดินทาง! (ความสนิท 20)"
                                else:
                                    msg = "🍃 เจอคนรู้จักเก่า นั่งดื่มเหล้าทักทายกันเฉยๆ"
                            else:
                                msg = "🎒 ปาร์ตี้เต็มแล้ว จึงได้เพียงพูดคุยแลกเปลี่ยนสุรา"
                        elif sub == "buy_weapon":
                            if a.money.get(w.wid, 0) >= 150 and a.inventory.get("อาวุธ") is None:
                                a.money[w.wid] -= 150
                                a.inventory["อาวุธ"] = "กระบี่เหล็กเย็น"
                                msg = "🛍️ สวมใส่ 'กระบี่เหล็กเย็น' สำเร็จ"
                            else:
                                msg = "🍃 พ่อค้าเร่ขาย 'กระบี่เหล็กเย็น' (ราคา 150) แต่ไม่ได้ซื้อ"
                        elif sub == "train":
                            a.insight += 0.4
                            R.cultivate(a, gap)
                            msg = "🥋 นั่งสมาธิร่วมกันในหุบเขา ได้รับ EXP"
                        
                        return "วิถียุทธ", pre_msg + msg, d

                    if rng.randint(1, 100) <= wealth:
                        if a.companions and rng.random() > 0.5:
                            comp = rng.choice(list(a.companions.keys()))
                            if a.money.get(w.wid, 0) >= 40:
                                a.money[w.wid] -= 40
                                if type(a.companions[comp]) == int: a.companions[comp] = min(100, a.companions[comp] + 20)
                                msg = f"🛍️ [ความสัมพันธ์] ซื้อสมุนไพรให้ {comp} 💞 (+20 Affection)"
                            else:
                                msg = f"🛍️ [ความสัมพันธ์] {comp} อยากได้สมุนไพรแต่เงินไม่พอ"
                            return "การค้า", pre_msg + msg, d
                            
                        msg_add = ""
                        if "ศิษย์พี่ใหญ่เซี่ย" in a.companions:
                            potion_cost = 20
                            msg_add = " 📜 ศิษย์พี่ใหญ่เซี่ยต่อราคาเหลือ 20 เงิน!"
                            
                        if a.money.get(w.wid, 0) >= potion_cost and a.inventory.get("ยาสมานแผล", 0) < 2:
                            a.money[w.wid] -= potion_cost
                            a.inventory["ยาสมานแผล"] += 1
                            msg = f"🎒 ซื้อยาสมานแผลสำเร็จ (จ่าย {potion_cost} เงิน){msg_add}"
                        else:
                            msg = f"🍃 เจอร้านขาย 'ยาสมานแผล' (ราคา {potion_cost}){msg_add} แต่ไม่ได้ซื้อ"
                            
                        return "การค้า", pre_msg + msg, d
                        
                    # ทั่วไป
                    a.hp = min(getattr(a, "max_hp", 100), getattr(a, "hp", 100) + 10)
                    msg = "🍃 ปาร์ตี้เดินทางผ่านทุ่งหญ้าอย่างสงบ ฟื้นฟู +10 HP"
                    return "ความสงบ", pre_msg + msg, d
            return "ทั่วไป", f"{a.name} เดินเล่นในเมือง", d
'''

pattern = re.compile(r'(        if k == "เหตุการณ์เมือง":.*?            return "ทั่วไป", f"\{a\.name\} เดินเล่นในเมือง", d\n)', re.DOTALL)
new_content = pattern.sub(new_logic + '\n', content)

with open('tiandao/sim.py', 'w', encoding='utf-8') as f:
    f.write(new_content)
print("sim.py updated with Ultimate Sim Features.")
