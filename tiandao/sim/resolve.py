# -*- coding: utf-8 -*-
"""Sim — resolve: ผลของการกระทำแต่ละชนิด"""
from ._common import *  # noqa: F401,F403
from ._common import _REACH_CACHE, _PLACE_SETS, _CENTERS, _reach_from, _auction_q  # noqa: F401


class ResolveMixin:
    def resolve(self, ev, a, t, w, gap, rng):
        k, d = ev["kind"], {}
        # คู่กรณีที่ยืนคนละที่ต้องบันทึกไว้ตรงนี้ว่า "เอื้อมถึงกันได้เพราะอะไร" — ที่นี่คือจุดเดียว
        # ที่ยังอ่านความสัมพันธ์ก่อนเหตุการณ์ได้ครบทุกชนิดเหตุการณ์ หลังจากนี้ handler แต่ละตัว
        # แก้ความสัมพันธ์ได้ตามใจ (ทรยศตัด bonds ทิ้ง ล้างแค้นสะสางหนี้) แล้วหลักฐานจะหายไป
        # ตรวจเฉพาะคู่ที่อยู่คนละที่ เพราะคู่ที่ยืนตรงหน้ากันไม่ต้องมีเหตุผลอะไรมารองรับ
        if t is not None and t is not a and getattr(a, "place", -1) != getattr(t, "place", -2):
            tie = self.reach_reason(a, t)
            if tie:
                d[C.PRIOR_TIE_KEY] = tie
        if k == "เหตุการณ์เมือง":
            if getattr(a, "hp", 0) <= 0: return "ทั่วไป", "บาดเจ็บหนักเกินกว่าจะเดินในเมือง", d
            
            a.cities_visited = getattr(a, "cities_visited", 0) + 1
            if hasattr(a, "update_title"): a.update_title()
            
            # ความชราอยู่ที่เพดานอายุขัย (rules.age_and_decay) และร่างกายตามอายุร่าง (body.work_capacity) — ไม่มีทางตายซ้ำที่นี่
            if a.city_id >= 0:
                city = next((c for c in self.cities if c["id"] == a.city_id), None)
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
                            # คู่ครองต้องเป็นผู้ใหญ่ เดิมเด็กในเมืองถูกสุ่มมาแต่งงานและมีลูกได้
                            adult_chars = [c for c in other_chars if c.age(self.day) >= C.ADULT_AGE]
                            if not adult_chars:
                                return "ทั่วไป", pre_msg + f"{a.name}เดินชมเมืองโดยไม่มีเหตุสำคัญ", d
                            b = rng.choice(adult_chars)
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
                                    self.marry(a, b)
                                    msg = f"💖 [แต่งงาน] [{a.name}] และ [{b.name}] พบกันที่ {city['name_th']} และเข้าพิธีวิวาห์!"
                                    
                                    # 👶 ตั้งครรภ์ (คลอดเมื่อครบกำหนด — Sim.conceive)
                                    if rng.random() < 0.5 and {a.gender, b.gender} == {"ชาย", "หญิง"} \
                                            and min(a.age(self.day), b.age(self.day)) >= C.ADULT_AGE:
                                        mother = a if a.gender == "หญิง" else b
                                        fertile = self.fertility(w)
                                        if (mother.pregnancy is None and mother.postpartum_until <= self.day
                                                and (fertile >= 1.0 or rng.random() < fertile)):
                                            self.conceive(mother, b if mother is a else a, a)
                                            msg += f" 🤰 [ตั้งครรภ์] {mother.name}ตั้งครรภ์ทายาทรุ่นถัดไป!"
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
                            WAGES.set_gold(self, a, w.tier, a.money.get(w.tier, 0) + 150, "nemesis_spoils")
                            a.insight += 1.2
                            a.enemies_defeated = getattr(a, "enemies_defeated", 0) + 1
                            self.begin_cultivation(a, gap)
                            del a.nemeses[hunter]
                            return "อันตราย", pre_msg + msg, d
                        else:
                            msg += f" 💥 [พ่ายแพ้คู่แค้น] ท่านพลาดท่าบาดเจ็บสาหัส เสีย -50 HP และถูกชิงทรัพย์ -100 เงิน"
                            a.hp -= 50
                            WAGES.set_gold(self, a, w.tier, max(0, a.money.get(w.tier, 0) - 100), "robbed")
                            a.nemeses[hunter]["hatred"] = 60
                            msg = check_hp(msg)
                            return "อันตราย", msg, d
                    
                    if rng.randint(1, 100) > safety:
                        msg = "⚠️ [เหตุการณ์อันตราย] คณะเดินทางของคุณโดนโจรป่าดักโจมตี!"
                        enemy_power = rng.randint(40, max(90, int(w.tier*40)))
                        
                        if combat_power >= enemy_power:
                            WAGES.set_gold(self, a, w.tier, a.money.get(w.tier, 0) + 100, "bandit_spoils")
                            a.insight += 0.5
                            a.enemies_defeated = getattr(a, "enemies_defeated", 0) + 1
                            self.begin_cultivation(a, gap)
                            
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
                                msg = f"💥 [พ่ายแพ้] 💖 [ปาฏิหาริย์แห่งรัก] {saved_by_love} กระโดดขวางวิถีกระบี่ ยอมเจ็บแทนท่าน! (ออกจากคณะเดินทางไป)"
                                msg = check_hp(msg)
                                return "อันตราย", pre_msg + msg, d
                                
                            dmg = 50
                            msg_add = ""
                            if "จ้าวเถี่ยซาน" in a.companions:
                                dmg = dmg // 2
                                msg_add = " 🛡️ จ้าวเถี่ยซานรับแรงกระแทก!"
                            a.hp -= dmg
                            WAGES.set_gold(self, a, w.tier, max(0, a.money.get(w.tier, 0) - 40), "robbed")
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
                                self.begin_cultivation(a, gap)
                                a.nemeses["คุณชายมู่"]["hatred"] = min(100, h_info["hatred"] + 35)
                                msg += f" 🏆 [ชนะประลอง] เขาเสียหน้าและเกลียดท่านมากขึ้น! (Hatred: {a.nemeses['คุณชายมู่']['hatred']}/100)"
                            else:
                                a.hp -= 10
                                msg += f" 🥈 [แพ้ประลอง] เสีย -10 HP"
                                msg = check_hp(msg)
                        elif sub == "drink_tea":
                            comp = rng.choice(list(a.companions.keys()))
                            choice = rng.choice(["share_gold", "talk_martial", "ignore"])
                            if choice == "share_gold" and a.money.get(w.tier, 0) >= 50:
                                WAGES.set_gold(self, a, w.tier, a.money.get(w.tier, 0) - 50, "event_spend")
                                if type(a.companions[comp]) == int: a.companions[comp] = min(100, a.companions[comp] + 25)
                                msg = f"🍻 [ความสัมพันธ์] ชวน {comp} ดื่มชา 💞 (+25 Affection)"
                            elif choice == "talk_martial":
                                a.insight += 0.3
                                self.begin_cultivation(a, gap)
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
                                msg = "🎒 คณะเดินทางเต็มแล้ว จึงได้เพียงพูดคุยแลกเปลี่ยนสุรา"
                        elif sub == "buy_weapon":
                            if a.money.get(w.tier, 0) >= 150 and a.inventory.get("อาวุธ") is None:
                                WAGES.set_gold(self, a, w.tier, a.money.get(w.tier, 0) - 150, "event_spend")
                                a.inventory["อาวุธ"] = "กระบี่เหล็กเย็น"
                                msg = "🛍️ สวมใส่ 'กระบี่เหล็กเย็น' สำเร็จ"
                            else:
                                msg = "🍃 พ่อค้าเร่ขาย 'กระบี่เหล็กเย็น' (ราคา 150) แต่ไม่ได้ซื้อ"
                        elif sub == "train":
                            a.insight += 0.4
                            self.begin_cultivation(a, gap)
                            msg = "🥋 นั่งสมาธิร่วมกันในหุบเขา ได้รับ EXP"
                        
                        return "วิถียุทธ", pre_msg + msg, d

                    if rng.randint(1, 100) <= wealth:
                        if a.companions and rng.random() > 0.5:
                            comp = rng.choice(list(a.companions.keys()))
                            if a.money.get(w.tier, 0) >= 40:
                                WAGES.set_gold(self, a, w.tier, a.money.get(w.tier, 0) - 40, "event_spend")
                                if type(a.companions[comp]) == int: a.companions[comp] = min(100, a.companions[comp] + 20)
                                msg = f"🛍️ [ความสัมพันธ์] ซื้อสมุนไพรให้ {comp} 💞 (+20 Affection)"
                            else:
                                msg = f"🛍️ [ความสัมพันธ์] {comp} อยากได้สมุนไพรแต่เงินไม่พอ"
                            return "การค้า", pre_msg + msg, d
                            
                        msg_add = ""
                        if "ศิษย์พี่ใหญ่เซี่ย" in a.companions:
                            potion_cost = 20
                            msg_add = " 📜 ศิษย์พี่ใหญ่เซี่ยต่อราคาเหลือ 20 เงิน!"
                            
                        if a.money.get(w.tier, 0) >= potion_cost and a.inventory.get("ยาสมานแผล", 0) < 2:
                            WAGES.set_gold(self, a, w.tier, a.money.get(w.tier, 0) - potion_cost, "event_spend")
                            a.inventory["ยาสมานแผล"] += 1
                            msg = f"🎒 ซื้อยาสมานแผลสำเร็จ (จ่าย {potion_cost} เงิน){msg_add}"
                        else:
                            msg = f"🍃 เจอร้านขาย 'ยาสมานแผล' (ราคา {potion_cost}){msg_add} แต่ไม่ได้ซื้อ"
                            
                        return "การค้า", pre_msg + msg, d
                        
                    # ทั่วไป
                    a.hp = min(getattr(a, "max_hp", 100), getattr(a, "hp", 100) + 10)
                    msg = "🍃 คณะเดินทางเดินทางผ่านทุ่งหญ้าอย่างสงบ ฟื้นฟู +10 HP"
                    return "ความสงบ", pre_msg + msg, d
            return "ทั่วไป", f"{a.name} เดินเล่นในเมือง", d








        # --- อีเวนท์สายอาชีพใหม่ ---
        if k == "สะสมบุญบารมี":
            a.merit += rng.uniform(5.0, 15.0)
            a.moral = getattr(a, "moral", 0) + 2
            a.insight += rng.uniform(0.1, 0.5)
            self.begin_cultivation(a, gap)
            if hasattr(a, "update_title"): a.update_title()
            return "บุญบารมี", f"{a.name}ออกโปรดสัตว์ สะสมบุญบารมีเพิ่มขึ้น", d
            
        if k == "ลาดตระเวน":
            WAGES.set_gold(self, a, w.tier, a.money.get(w.tier, 0) + WAGES.fiat_pay(10), "fiat_work")
            return "ลาดตระเวน", f"{a.name}ออกลาดตระเวนรักษาความสงบ ได้รับเบี้ยหวัด", d
            
        if k == "เปิดประมูล":
            return self.auction(a, w, rng, d)

        if k == "จับกุมอาชญากร":
            if not t: return "ล้มเหลว", "ไม่พบอาชญากร", d
            if not R.is_criminal(t):
                # ด่านสุดท้าย เผื่อ target มาจากทางอื่น (ผู้มีจิตใจเลือกเอง/ตารางเหตุการณ์)
                return "ไม่พบอาชญากร", f"{a.name}ไม่พบอาชญากรที่ต้องตามจับแถวนี้", d
            if R.power(a, w) <= R.power(t, w):
                # จับไม่สำเร็จ = จองเวรจริง (rivals) ไม่ใช่แค่ bonds ติดลบที่ไม่มีใครอ่าน
                t.rivals[a.cid] = t.rivals.get(a.cid, 0) + 1
                a.rivals[t.cid] = a.rivals.get(t.cid, 0) + 1
                return "ล้มเหลว", f"{a.name}พยายามจับกุม {t.name} แต่สู้ไม่ได้", d
            a.moral = getattr(a, "moral", 0) + 3
            if hasattr(a, "update_title"): a.update_title()
            weight = R.crime_weight(t)
            # ค่าหัวมาจากของกลางที่ยึดได้ ไม่ใช่เงินที่เกิดจากอากาศ (เดิม randint(20,100) ลอยๆ)
            loot = int(t.money.get(w.tier, 0) * 0.5)
            bounty = max(20, min(loot, 300)) if loot > 0 else rng.randint(20, 60)
            WAGES.set_gold(self, t, w.tier, max(0, t.money.get(w.tier, 0) - loot), "seized_from_criminal")
            WAGES.set_gold(self, a, w.tier, a.money.get(w.tier, 0) + bounty, "bounty")
            d["ของกลางที่ยึดได้"] = bounty
            if weight >= C.EXECUTE_KILLS:
                # ฆ่าคนมาแล้วหลายศพ — โทษประหาร ยังเป็นความตายที่มีเหตุให้เล่าได้
                d["ความผิด"] = f"ฆ่าคนมาแล้ว {getattr(t, 'kills', 0)} ศพ"
                self.kill(t, f"ถูกประหารตามกฎหมายโดย {a.name}", killer=a)
                return "ประหาร", f"{a.name}จับกุมและประหาร {t.name} ตามกฎหมาย " \
                                 f"(ความผิดหนัก {weight} ระดับ)", d
            lo, hi = C.JAIL_DAYS
            years = int(min(hi, lo + (hi - lo) * min(1.0, weight / float(C.EXECUTE_KILLS))) / 365)
            t.jail_until = self.day + years * 365
            t.jailer = a.cid
            t.hidden = True                 # ออกจากเวทีชั่วคราว (ทุกที่ที่กรอง hidden ข้ามให้เอง)
            t.travel_dest = -1              # ถูกจับกลางทางก็ไม่ได้ไปต่อ
            t.rivals[a.cid] = t.rivals.get(a.cid, 0) + C.JAIL_GRUDGE
            d["ความผิด"] = f"ระดับ {weight}"
            d["โทษ"] = f"คุมขัง {years} ปี"
            # **ห้าม schedule() ให้ผู้ถูกจับที่นี่** — เขามีคิวของตัวเองอยู่แล้วหนึ่งใบ การใส่เพิ่ม
            # ทำให้คนหนึ่งคนมีสองเทิร์นในคิวตลอดไป (test_autonomy/test_scheduler_integrity จับได้)
            # จังหวะแหกคุกเกิดตอนคิวเดิมของเขาถึงเอง แล้วบล็อกติดคุกใน step() จะเลื่อนไปวันพ้นโทษ
            # แต่ใบเดิมอาจอยู่หลังวันพ้นโทษ (ถูกจับตอนซ่อนตัว ซึ่งนัดเทิร์นไว้ 2,000–12,000 วัน) จึงเลื่อนใบเดิมมาไม่ให้เกิน
            # วันพ้นโทษ ไม่งั้นพ้นโทษแล้วยังค้างในคุกหลายปี คุกเลิกเลี้ยงตั้งแต่วันพ้นโทษ และคนที่ซ่อนตัวทำงานแลกข้าวไม่ได้
            # (test_law: ถูกจับ 86 วันหลังเก็บตัว เทิร์นถัดไปอยู่หลังวันพ้นโทษ 1,454 วัน อดตายในคุก 77 วันหลังพ้นโทษ)
            pending = min((when for when, cid in self.queue if cid == t.cid), default=None)
            if pending is not None and pending > t.jail_until:
                self.requeue(t, t.jail_until)
            return "คุมขัง", f"{a.name}จับกุม {t.name} ได้ ส่งเข้าคุมขัง {years} ปี " \
                             f"ยึดของกลาง {bounty}", d

        if k == "ลอบสังหาร":
            if not t: return "ล้มเหลว", "ไม่มีเป้าหมาย", d
            motive = R.assassin_motive(self, a, t)
            if motive is None:
                # ไม่มีแค้น ไม่มีคนจ้าง ก็ไม่มีเหตุจะฆ่าคนแปลกหน้าที่ยืนอยู่ข้างๆ
                return "ไม่มีเหตุให้ลงมือ", f"{a.name}ไม่มีเหตุจะลงมือกับใครแถวนี้", d
            why, client = motive
            d["เหตุที่ลงมือ"] = why
            if a.profession in ("นักบวช", "นักพรต"):
                a.karma += 50.0 # ฆ่าคนกรรมพุ่ง
            fee = 0
            if client is not None:
                fee = min(client.money.get(w.tier, 0), rng.randint(*C.ASSASSIN_FEE))
                client.money[w.tier] = client.money.get(w.tier, 0) - fee
                a.money[w.tier] = a.money.get(w.tier, 0) + fee
                client.bonds[a.cid] = client.bonds.get(a.cid, 0) + C.ASSASSIN_CLIENT_BOND
                a.bonds[client.cid] = a.bonds.get(client.cid, 0) + C.ASSASSIN_CLIENT_BOND
                client.moral = getattr(client, "moral", 0) - 3
                client.karma += 20.0
                d["ผู้ว่าจ้าง"] = f"{client.name} จ่าย {fee}"
            # โอกาสสำเร็จขึ้นกับพลัง
            if R.power(a, w) * 1.5 > R.power(t, w):
                self.kill(t, f"ถูกลอบสังหารโดย {a.name}", killer=a)
                a.moral = getattr(a, "moral", 0) - 5
                if hasattr(a, "update_title"): a.update_title()
                if client is not None:
                    client.rivals.pop(t.cid, None)   # แค้นของผู้ว่าจ้างจบลงพร้อมกับเป้าหมาย
                d["สังหาร"] = f"{t.name} ถูกลิดรอนวิญญาณ"
                return "สังหาร", f"{a.name}ลอบสังหาร {t.name} สำเร็จ ({why})", d
            else:
                t.rivals[a.cid] = t.rivals.get(a.cid, 0) + 3   # รู้ตัวแล้วว่าใครจะเอาชีวิต
                t.bonds[a.cid] = min(-10, t.bonds.get(a.cid, 0) - 50)
                return "ล้มเหลว", f"{a.name}ลอบสังหาร {t.name} พลาด โดนหมายหัวกลับ", d

        if k == "ดักปล้น":
            if not t: return "ล้มเหลว", "ไม่มีเป้าหมาย", d
            if R.power(a, w) > R.power(t, w):
                stolen = t.money.get(w.tier, 0) // 2           # ครึ่งหนึ่งของที่พกอยู่ — ย้ายระหว่างคน ไม่ใช่ทองเกิดหรือหาย
                t.money[w.tier] = t.money.get(w.tier, 0) - stolen
                a.money[w.tier] = a.money.get(w.tier, 0) + stolen
                self.wrong_done(a, t, "ปล้น", stolen)
                a.moral = getattr(a, "moral", 0) - 3
                if hasattr(a, "update_title"): a.update_title()
                t.bonds[a.cid] = min(-10, t.bonds.get(a.cid, 0) - 30)
                return "ปล้นสำเร็จ", f"{a.name}ดักปล้น {t.name} ได้เงิน {stolen}", d
            else:
                t.bonds[a.cid] = min(-10, t.bonds.get(a.cid, 0) - 10)
                return "ล้มเหลว", f"{a.name}พยายามปล้น {t.name} แต่โดนตีกลับ", d

        if k == "ทำนายชะตา":
            if not t: return "ล้มเหลว", "ไม่มีผู้ว่าจ้าง", d
            a.insight += rng.uniform(0.1, 0.5)
            t.insight += rng.uniform(0.1, 0.3)
            fee = rng.randint(5, 20)
            if t.money.get(w.tier, 0) >= fee:
                t.money[w.tier] -= fee
                a.money[w.tier] = a.money.get(w.tier, 0) + fee
            return "ทำนาย", f"{a.name}ตรวจดวงชะตาให้ {t.name} ชี้แนะหนทาง", d

        if k == "ขายข่าวลับ":
            if not t: return "ล้มเหลว", "ไม่มีลูกค้า", d
            fee = rng.randint(10, 50)
            if t.money.get(w.tier, 0) >= fee:
                t.money[w.tier] -= fee
                a.money[w.tier] = a.money.get(w.tier, 0) + fee
                t.bonds[a.cid] = max(0, t.bonds.get(a.cid, 0) + 10)
                return "ข่าวลับ", f"{a.name}ขายข้อมูลสำคัญให้ {t.name}", d
            return "ล้มเหลว", f"{t.name}ไม่มีเงินจ่ายค่าข่าวให้ {a.name}", d


        if k == "บำเพ็ญ":
            pv = self.place_of(a)
            if a.race() == "อสูร":
                boost = 1.0 + (w.tier * 0.5)
                if pv and pv[2] >= 2:
                    boost += 1.0
                self.begin_cultivation(a, gap, boost)
            else:
                self.begin_cultivation(a, gap)
            if pv and pv[3] == "ลานฝึก":
                a.insight += 0.4
                d["ลานฝึก"] = self.place_name(a)
            if w.tier == 0 and w.defense_array < w.defense_max and a.realm >= 2 and rng.random() < 0.4:
                restore = rng.uniform(2, 5)
                w.defense_array = min(w.defense_max, w.defense_array + restore)
                d["ซ่อมค่ายกล"] = f"เสริมพลังค่ายกลโลก (+{restore:.1f}) เหลือ {w.defense_array:.1f}/{w.defense_max:.1f}"
            # ตกผลึกปราณส่วนเกินเป็นหินวิญญาณ — ทางเดียวที่ **คนไม่มีเงินสร้างทุนได้เอง**
            # เงื่อนไข: ที่ตรงนี้ต้องเลี้ยงเขาได้เกินขั้นที่เขายืนอยู่ ส่วนเกินนั้นเท่านั้น
            # ที่ตกผลึกได้ คนที่ยึดขั้นสูงเกินแผ่นดินใต้เท้าจึงไม่มีวันเก็บทุนได้เลย
            # ต้องย้ายหรือยอมลง — ซึ่งเป็นแรงผลักให้คนออกเดินทางหาที่ที่ดีกว่า
            rho = self.qi_density(a.place, w)
            spare = EC.place_ceiling(rho) - a.realm
            if spare > 0 and w.extractable() > 0:
                crop = min(EC.upkeep_qi(a.realm) * spare * C.CONDENSE_RATE * (gap / 365.0),
                           w.extractable())
                if crop > 0:
                    w.heaven -= crop
                    a.qi_taken = getattr(a, "qi_taken", 0.0) + crop
                    grade = min(len(EC.GRADE_NAMES) - 1, w.tier)
                    EC.add_stones(a, grade, EC.mint(crop, grade))
                    d["ตกผลึก"] = (f"{EC.grade_name(grade)} +{EC.mint(crop, grade):.2f} ก้อน "
                                   f"(ที่นี่เลี้ยงได้ถึงขั้น {EC.place_ceiling(rho):.1f})")
            return "บำเพ็ญ", f"{a.name}เก็บตัวบำเพ็ญที่{self.place_name(a)}", d

        if k == "ขัดเกลาสายเลือด":
            R.refine_blood(a, gap)
            return "ขัดเกลา", f"{a.name}ขัดเกลาสายเลือด{a.race()}ของตน", d

        if k == "ข้ามขั้น":
            # ยังสะสมไม่พอไม่ควรกินยาเสียเปล่า
            if R.accumulation(a) < R.need(a, w):
                self.begin_cultivation(a, gap)
                return "สะสมต่อ", f"{a.name}รู้ว่ายังไม่ถึงเวลา จึงบำเพ็ญต่อ", d
            pills = [i for i in a.items if self.items[i].kind == "ยาวิเศษ"]
            use, pname = 0.0, None
            if pills:
                best = max(pills, key=lambda i: getattr(self.items[i], "pill_bonus", 0.1))
                use = getattr(self.items[best], "pill_bonus", 0.1) / C.PILL_BREAK_BONUS
                pname = self.items[best].name
                a.items.remove(best)
                a.longevity_bonus += getattr(self.items[best], "lifespan_bonus", 0)
            res, txt = R.attempt_break(self, a, w, rng, pills=use)
            if res == "ยังไม่ถึง":
                self.begin_cultivation(a, gap)
                return "สะสมต่อ", f"{a.name}รู้ว่ายังไม่ถึงเวลา จึงบำเพ็ญต่อ", d
                
            # `attempt_break` คืนสตริง "ผ่าน" เมื่อสำเร็จ ไม่เคยคืน True เลย (ดู rules.py บรรทัดสุดท้าย
            # ของฟังก์ชัน) เงื่อนไข `res is True` เดิมจึงเป็นเท็จเสมอ — บล็อกความสัมพันธ์ศิษย์-อาจารย์
            # ทั้งก้อนนี้ไม่เคยทำงานเลยสักครั้งตั้งแต่เขียนมา ทั้งการเนรคุณสังหารอาจารย์ การแยกตัว
            # ไปตั้งสาขา และการยอมให้อาจารย์เป็นผู้อาวุโส (วัดจริง: ข้ามขั้นสำเร็จ 39 จาก 50 ครั้ง
            # คืนค่า "ผ่าน" ทุกครั้ง ไม่มี True สักครั้งเดียว)
            if res == "ผ่าน":
                # evaluate_master_relationship
                if a.master_cid != -1 and 0 <= a.master_cid < len(self.cast):
                    master = self.cast[a.master_cid]
                    if master.alive and a.realm > master.realm:
                        loyalty = getattr(a, "loyalty", 50)
                        ambition = getattr(a, "ambition", 50)
                        rebellion_score = ambition - loyalty
                        
                        if rebellion_score > 30:
                            # Betray Master
                            txt += f"\n -> [เนรคุณ] {a.name} ลุ่มหลงอำนาจ สังหารอาจารย์ {master.name} เพื่อชิงตำแหน่ง!"
                            self.kill(master, f"ถูกศิษย์ทรยศ {a.name} สังหารเพื่อชิงอำนาจ")
                            a.master_cid = -1
                            if a.cid in master.disciples: master.disciples.remove(a.cid)
                        elif ambition > 60 and loyalty >= 50:
                            # Peaceful Departure
                            txt += f"\n -> [แยกตัว] {a.name} คารวะอาจารย์และขอแยกตัวไปตั้งสาขาใหม่ด้วยดี"
                            a.master_cid = -1
                            if a.cid in master.disciples: master.disciples.remove(a.cid)
                        else:
                            # Stay Loyal
                            txt += f"\n -> [กตัญญู] แม้พลังสูงส่ง {a.name} ยังเคารพ {master.name} และยอมให้เป็นผู้อาวุโสสูงสุด"
                            master.is_loner = True # Force master to retire

            if pname:
                d["ใช้ยา"] = f"กิน{pname}ก่อนข้ามขั้น"
            d["คลังฟ้า"] = f"{w.name} {w.state()} ({w.ratio()*100:.0f}%)"
            d["ที่"] = self.place_name(a)
            return res, txt, d

        if k == "ฝึกวิชา":
            grade = 2 if a.realm >= SK.GRADE_REALM_BAR[2] else (
                1 if a.realm >= SK.GRADE_REALM_BAR[1] else 0)
            # ผู้บำเพ็ญขั้นสูงย่อมเก็บวิชาชั้นรองไว้ด้วย ไม่ใช่รู้แต่วิชาสูงสุดอย่างเดียว
            # (วัดจริง: วิชาต่อคนพีคที่ขั้น 2-3 แล้วกลับ "ลดลง" ที่ขั้น 4+ ซึ่งกลับหัวกับนิยาย
            #  เพราะขั้นสูงถูกบังคับให้เล็งแต่วิชาขั้น 2 ที่ต้องมีลานฝึกและสำเร็จยากกว่า)
            grade = rng.choice([grade, max(0, grade - 1), max(0, grade - 1), max(0, grade - 2)])
            pool = [x for x in SK.by_tier_grade(min(a.tier, 2), grade)
                    if x[0] not in a.skills]
            # ฝึกของเดิมให้ลึกขึ้น — ทางที่เคยไม่มีอยู่เลย วิชาเคยเป็น binary มีหรือไม่มี
            # ฝึกวิชาที่มีอยู่แล้วจึงไม่ได้อะไร ต้องไปหาวิชาใหม่ท่าเดียว ผลคือวัดจริงโลก 50 ปี
            # วิชาต่อคนเฉลี่ย 0.95 และ 1,020 จาก 2,184 คนไม่มีวิชาเลย (47%) ในโลกบำเพ็ญ
            # ตอนนี้ "หนึ่งวิชาฝึกสี่สิบปี" เป็นเส้นทางที่เลือกได้จริง (ดู physics.practice_mastery)
            # คนที่มีวิชาน้อยยังควรหาของใหม่ก่อน คนที่มีหลายวิชาแล้วถึงค่อยเลือกฝึกให้ลึก
            # (ตั้งเป็นค่าคงที่ตอนแรกแล้ววัดได้ว่าวิชาต่อคนลดจาก 0.95 เหลือ 0.76 เพราะการฝึกลึก
            #  ไปแย่งโอกาสการเรียนของใหม่มาตั้งแต่วิชาแรก)
            _dp = C.DEEPEN_W * min(1.0, len(a.skills) / C.DEEPEN_AFTER)
            if a.skills and (not pool or rng.random() < _dp):
                _mast = a.mastery if isinstance(getattr(a, "mastery", None), dict) else {}
                a.mastery = _mast
                name = min(a.skills, key=lambda n: (_mast.get(n, 0), n))
                reps = _mast.get(name, 0)
                before = PHYS.practice_mastery(reps, C.PRACTICE_EXPONENT)
                _mast[name] = reps + 1
                from .. import body as BODY
                BODY.train(a, 0.75)
                after = PHYS.practice_mastery(reps + 1, C.PRACTICE_EXPONENT)
                a.insight += C.DEEPEN_INSIGHT * (after - before) * 10.0
                d["ฝึกซ้ำ"] = f"{name} — ครั้งที่ {reps + 1}"
                d["ความชำนาญ"] = f"{before:.0%} -> {after:.0%}"
                d["p"] = 1.0
                return "ลึกขึ้น", f"{a.name}ฝึก{name}ซ้ำจนเข้าใจลึกกว่าเดิม", d
            if not pool:
                self.begin_cultivation(a, gap)
                return "ไม่มีวิชาให้ฝึก", f"{a.name}หาวิชาใหม่ฝึกไม่ได้ จึงบำเพ็ญต่อ", d
            pv = self.place_of(a)
            if grade == 2 and not (pv and pv[3] in ("ลานฝึก", "สำนัก", "แดนต้องห้าม")):
                self.begin_cultivation(a, gap)
                return "ไม่มีที่ฝึก", f"{a.name}หาที่ฝึกวิชาขั้นสูงไม่ได้ที่{self.place_name(a)}", d
            if grade == 2 and not self.route_to_building(a, ("dojo",)):
                return "เดินไปลานฝึก", f"{a.name}มุ่งหน้าไปยังลานประลองยุทธ์กลาง{self.place_name(a)}", d
            # แต่ละแดนถนัดคนละทาง — สยามเน้นกาย ชมพูทวีปเน้นจิต ฯลฯ (ดู paths.REALM_BODY_BIAS)
            # เป็นการ "เอน" ไม่ใช่บังคับ คนสยามที่ไปฝึกสายจิตจนสมดุลก็ยังมีอยู่จริง
            # สาขาแต่ละแห่งมีวิชาประจำแดนของตัวเอง คนในนั้นจึงฝึกไปคนละทางกับสาขาอื่นจริงๆ
            # การเลือกวิชาเป็นการ "แคบเข้าแล้วค่อยเลือก" ขั้นเดียวกันทั้งสามชั้น:
            # สายประจำแดน -> ทางที่แดนนั้นถนัด -> ธาตุประจำตัว  ชั้นหลังเลือก **ภายในกอง
            # ที่ชั้นก่อนแคบไว้แล้ว** ไม่ใช่เริ่มนับหนึ่งใหม่จากทั้งกอง
            #
            # บั๊กเดิม: เลือกวิชาสายประจำแดนมาแล้ว บรรทัดถัดมา EL.best_of(pool, ...) ไปหยิบ
            # จาก `pool` ทั้งก้อนแล้วเขียนทับ ด้วย ELEMENT_PICK_P = 0.7 การเอนของแดน
            # (BRANCH_SKILL_BIAS = 0.55) จึงเหลือผลจริงแค่ราว 30% วัดจริงที่ 60,000 เหตุการณ์:
            # มีแค่ 10 จาก 41 สาขา (24%) ที่วิชาประจำแดนเด่นเกิน 15% ของวิชาที่คนในแดนรู้
            # — "สามพันโลก" ที่ผลิตคนแบบเดียวกันหมด ซึ่งเป็นสิ่งเดียวที่ทำให้สาขาต่างกัน
            # การเลือกวิชาเป็นการ "แคบเข้าแล้วค่อยเลือก" ชั้นธาตุจึงต้องเลือก **ภายในกองที่
            # ชั้นก่อนหน้าแคบไว้แล้ว** ไม่ใช่เริ่มนับหนึ่งใหม่จากทั้งกองแล้วลบผลของชั้นก่อนทิ้ง
            #
            # บั๊กเดิม: เลือกวิชาสายประจำแดนมาแล้ว บรรทัดถัดมา EL.best_of(pool, ...) หยิบจาก
            # `pool` ทั้งก้อนมาเขียนทับ ด้วย ELEMENT_PICK_P = 0.7 การเอนของแดน
            # (BRANCH_SKILL_BIAS = 0.55) จึงเหลือผลจริงราว 30% วัดจริงที่ 60,000 เหตุการณ์:
            # มีแค่ 10 จาก 41 สาขา (24%) ที่วิชาประจำแดนเด่นเกิน 15% ของวิชาที่คนในแดนรู้
            # — "สามพันโลก" ที่ผลิตคนแบบเดียวกันหมด ทั้งที่วิชาประจำแดนคือสิ่งเดียวที่ทำให้สาขาต่างกัน
            line = getattr(w, "skill_line", None)
            same_line = [x for x in pool if x[1] == line] if line else []
            if line and rng.random() < C.BRANCH_SKILL_BIAS and same_line:
                # สายประจำแดนไม่มีวิชาที่เขาเรียนได้ตอนนี้ ก็ต้องปล่อยให้ไปทางอื่น ไม่ใช่ติดตาย
                choice_pool = same_line
            else:
                choice_pool = PATHS.prefer_pool(pool, w.place_key, rng, personal=a.body_bias)
                same_line = []          # รอบนี้ไม่ได้เลือกด้วยสายประจำแดน
            sk = rng.choice(choice_pool)
            # ห้าธาตุ: คนไม่ได้หยิบวิชามั่วๆ เขามองหาวิชาที่ "ถูกกับธาตุของตัวเอง" ก่อน
            # ก่อนหน้านี้การเลือกวิชาเป็นการสุ่มล้วน ฝึกพลาดจึงเป็นลูกเต๋าล้วนๆ ด้วย
            # (วัดจริง: ฝึกพลาด 60 จาก 137 ครั้ง = 44% ของการกระทำที่ถูกเลือกมากที่สุดในโลก)
            _el = EL.ensure(a)
            if rng.random() < C.ELEMENT_PICK_P:
                # ถามคำถามที่แคบลงว่า "วิชา**ในกองที่แคบไว้แล้ว** อันไหนถูกกับธาตุข้าที่สุด" ธาตุยังสำคัญ
                # เท่าเดิม แต่ไม่ลบสายประจำแดนหรือทางที่แดนถนัดทิ้ง บั๊กเดิมแก้แค่สายประจำแดน รอบที่เลือกตาม
                # ทางที่แดนถนัดยังหยิบจากทั้งกอง ความเอนของแดนจึงเหลือผลแค่ 30% ของการเลือก วัดที่ 45 ปี
                # 6 เส้นทาง: สยามเอนไปทางกาย 0.46–0.65 ชมพูทวีป 0.34–0.45 ทั้งที่ตั้งไว้ 0.72 และ 0.30
                sk = EL.best_of(choice_pool, _el)[0]
            _aff = EL.affinity(_el, EL.skill_element(sk[0]))
            p = C.LEARN_BASE_P + 0.05 * (a.realm - SK.GRADE_REALM_BAR[grade]) \
                - 0.12 * grade - a.decay * 0.05 + C.ELEMENT_LEARN_W * _aff
            d["ธาตุของวิชา"] = (f"{EL.skill_element(sk[0])} · {EL.relation_words(_el, EL.skill_element(sk[0]))}"
                                 f" — {'ถูกทางกับข้า' if _aff > 0.5 else 'พอไปด้วยกันได้' if _aff > 0 else 'ขัดกับธาตุของข้า'}")
            _pw = max(0.05, min(0.95, p))
            d["p"] = _pw
            if rng.random() > _pw:
                from .. import body as BODY
                BODY.train(a, 0.45)  # ฝึกพลาดก็ยังลงแรง แม้ความเข้าใจยังไม่สำเร็จ
                a.decay += C.LEARN_BACKFIRE * (0.5 + 0.4 * grade)
                # ฝึกพลาดก็ได้บทเรียน — ไม่มากเท่าสำเร็จ แต่ไม่ใช่เสียเปล่าทั้งหมด
                a.insight += C.TRAIN_FAIL_INSIGHT
                d["ที่ได้กลับมา"] = "บทเรียนจากความผิดพลาด"
                return "ฝึกพลาด", f"{a.name}ฝึก{sk[0]}ไม่สำเร็จ ธาตุไฟเข้าแทรก", d
            # การฝึกวิชาสำเร็จเคย **ไม่ให้ความก้าวหน้าในการบำเพ็ญเลย** ให้แค่ชื่อวิชาในรายการ
            # (มีแต่กิ่งที่ฝึกไม่ได้ ที่เรียก cultivate() แทน) วัดจริงจากบันทึกผู้มีจิตใจ 48 ปี:
            # "ฝึกวิชา" เป็นการกระทำที่ถูกเลือกมากที่สุด 66/270 ครั้ง (24%) — คนเก่งที่สุดในโลก
            # จึงยังอยู่แค่ขั้นหลอมกระดูกหลังผ่านไปครึ่งศตวรรษ เพราะเวลาหนึ่งในสี่ของชีวิตเขา
            # หมดไปกับสิ่งที่ไม่ขยับด่านทั้งสองของการข้ามขั้นแม้แต่นิดเดียว
            # ในเชิงเรื่อง การเข้าถึงวิชาชั้นสูงคือการเข้าถึง "ทาง" — ต้องได้ทั้งความเข้าใจและกาย
            a.insight += C.TRAIN_INSIGHT_BASE + C.TRAIN_INSIGHT_PER_GRADE * grade
            a.refine += C.TRAIN_REFINE * (1.0 + 0.5 * grade)
            a.learn_skill(sk[0])        # เรียนจบครั้งแรก = ฝึกไปแล้วหนึ่งครั้ง
            from .. import body as BODY
            BODY.train(a, 1.0 + 0.25 * grade)
            d["วิชา"] = f"{SK.GRADE_NAME[sk[3]]} · สาย{sk[1]} — {sk[4]}"
            d["ทาง"] = f"{PATHS.skill_path(sk[0])}บำเพ็ญ · ตอนนี้เป็น{PATHS.path_of(a)}"
            d["ที่ฝึก"] = self.place_name(a)
            req = SK.REQUIREMENTS.get(sk[0])
            if req:
                d["เงื่อนไข"] = req
            if sk[5]:
                d["แก้ทางโกลาหล"] = "วิชานี้แก้ทางเผ่าโกลาหลได้"
            return "สำเร็จ", f"{a.name}ฝึก{sk[0]}สำเร็จ", d
        if k == "ทำนา":
            earn = WAGES.fiat_pay(rng.randint(5, 15))
            WAGES.set_gold(self, a, w.tier, a.money.get(w.tier, 0) + earn, "fiat_work")
            return "สำเร็จ", f"{a.name}ทำนาได้ผลผลิต", {"เงินที่ได้": earn}
        if k == "ค้าขายทั่วไป":
            earn = WAGES.fiat_pay(rng.randint(20, 50))
            WAGES.set_gold(self, a, w.tier, a.money.get(w.tier, 0) + earn, "fiat_work")
            return "สำเร็จ", f"{a.name}ค้าขายทั่วไปได้กำไร", {"เงินที่ได้": earn}
        if k == "ตีเหล็กชาวบ้าน":
            earn = WAGES.fiat_pay(rng.randint(10, 30))
            WAGES.set_gold(self, a, w.tier, a.money.get(w.tier, 0) + earn, "fiat_work")
            a.mats += 1
            return "สำเร็จ", f"{a.name}ตีเหล็กชาวบ้านขาย", {"เงินที่ได้": earn}
        if k == "รักษาชาวบ้าน":
            earn = WAGES.fiat_pay(rng.randint(10, 40))
            WAGES.set_gold(self, a, w.tier, a.money.get(w.tier, 0) + earn, "fiat_work")
            a.decay = max(0.0, a.decay - 0.1)
            return "สำเร็จ", f"{a.name}รักษาชาวบ้าน", {"เงินที่ได้": earn}
        if k == "ปกป้องชาวบ้าน":
            earn = WAGES.fiat_pay(rng.randint(30, 80))
            WAGES.set_gold(self, a, w.tier, a.money.get(w.tier, 0) + earn, "fiat_work")
            if rng.random() < 0.2:
                a.mat_stock["ศิลาปราณห้าธาตุ"] = a.mat_stock.get("ศิลาปราณห้าธาตุ", 0) + 1
            return "สำเร็จ", f"{a.name}ปกป้องชาวบ้านจากภัยร้าย", {"เงินที่ได้": earn, "ผลลัพธ์": "ชาวบ้านซาบซึ้ง"}
        if k == "ขูดรีดชาวบ้าน":
            earn = WAGES.fiat_pay(rng.randint(50, 150))
            WAGES.set_gold(self, a, w.tier, a.money.get(w.tier, 0) + earn, "fiat_work")
            a.decay += 0.2
            if "มารในใจ" not in a.traits:
                a.traits.append("มารในใจ")
            return "สำเร็จ", f"{a.name}ขูดรีดชาวบ้านอย่างโหดเหี้ยม", {"เงินที่ได้": earn, "ผลลัพธ์": "สร้างความแค้น"}


        if k == "เก็บวัตถุดิบ":
            # การเก็บของโดยเฉพาะ — แยกจาก "ล่าอสูร" ที่เป็นการต่อสู้และมีสิทธิตาย
            # นี่คือกิจวัตรของช่างหลอม/นักปรุงยา และเป็นทางเดียวที่จะได้ของชิ้นที่ตัวเองตามหา
            pool = MAT.materials_at(a.place)
            if not pool and not MAT.is_core_site(a.place):
                return ("ไม่มีอะไรให้เก็บ",
                        f"{a.name}มองหาวัตถุดิบที่{self.place_name(a)} แต่ที่นี่ไม่มีอะไรให้เก็บ", d)
            eco = self.eco_ratio(a.world_id, a.place)
            if not pool:
                # แหล่งแก่นพลัง — เก็บแก่นจากซากอสูรโดยไม่ต้องออกล่าเอง (ไม่มีความเสี่ยงตาย
                # แต่ได้น้อยกว่าล่าจริง) ก่อนหน้านี้ 9 แหล่งนี้ไม่มีทางเก็บอะไรได้เลย
                got_cores = self.eco_take_units(a.world_id, a.place, max(1, round(rng.randint(*C.GATHER_CORE_PER_TRIP) * eco)))
                if got_cores <= 0:
                    return "มือเปล่า", f"{a.name}ออกเก็บแก่นพลังที่{self.place_name(a)}แต่ซากอสูรที่นี่หมดแล้ว", d
                a.cores += got_cores
                d["เก็บได้"] = f"แก่นพลัง×{got_cores}"
                # สายหินวิญญาณที่แทรกอยู่ในแหล่งแก่นพลัง — ขุดขึ้นมาก็คือดูดปราณออกจากโลก
                if rng.random() < C.VEIN_FIND_P and w.extractable() > 0:
                    vein = min(C.VEIN_QI * eco * (1.0 + a.fate * C.VEIN_FATE), w.extractable())
                    w.heaven -= vein
                    grade = min(len(EC.GRADE_NAMES) - 1, w.tier)
                    EC.add_stones(a, grade, EC.mint(vein, grade))
                    d["สายหินวิญญาณ"] = f"{EC.grade_name(grade)} ×{EC.mint(vein, grade):.1f}"
                d["ที่"] = self.place_name(a)
                if rng.random() < 0.35 and self.eco_take_units(a.world_id, a.place, 1):
                    a.mat_stock["โลหิตอสูรกลั่น"] = a.mat_stock.get("โลหิตอสูรกลั่น", 0) + 1
                    d["ของพิเศษ"] = "โลหิตอสูรกลั่น"
                return ("เก็บได้", f"{a.name}เก็บแก่นพลัง {got_cores} เม็ดที่{self.place_name(a)}", d)
            n = self.eco_take_units(a.world_id, a.place, max(1, round(rng.randint(*C.GATHER_PER_TRIP) * eco)))
            if n <= 0:
                d["สภาพแหล่ง"] = "หมดแล้ว"
                return "มือเปล่า", f"{a.name}ออกเก็บวัตถุดิบแต่แหล่งที่{self.place_name(a)}ถูกเก็บจนหมด", d
            got = {}
            wanted_here = [m for m in getattr(a, "wants", ()) if m in pool]
            for _ in range(n):
                # ถ้ากำลังตามหาของชิ้นไหนอยู่และที่นี่มี ก็จะเพ่งหาชิ้นนั้นเป็นหลัก
                if wanted_here and rng.random() < C.GATHER_FOCUS_P:
                    pick = rng.choice(wanted_here)
                else:
                    pick = MAT.roll_material(a.place, rng, eco)
                if not pick:
                    continue
                a.mat_stock[pick] = a.mat_stock.get(pick, 0) + 1
                got[pick] = got.get(pick, 0) + 1
                if a.wants.get(pick):
                    left = a.wants[pick] - 1
                    if left > 0:
                        a.wants[pick] = left
                    else:
                        a.wants.pop(pick, None)
            if sum(got.values()) < n:                        # ชิ้นที่สุ่มไม่ได้อะไรคืนคลัง (ไม่ได้เก็บจริง)
                back = n - sum(got.values())
                self.place_stock[self._eco_key(a.world_id, a.place, None)] += back
                self._eco_dirty()
                self._material_flow("harvested", -back)
            if not got:
                return "มือเปล่า", f"{a.name}ออกเก็บวัตถุดิบแต่กลับมามือเปล่า", d
            d["เก็บได้"] = ", ".join(f"{m}×{q}" for m, q in got.items())
            d["ที่"] = self.place_name(a)
            if eco < 0.5:
                d["สภาพแหล่ง"] = "เริ่มร่อยหรอ"
            if a.wants:
                d["ยังตามหา"] = ", ".join(list(a.wants)[:3])
            return ("เก็บได้", f"{a.name}เก็บ{d['เก็บได้']}ที่{self.place_name(a)}", d)

        if k == "ล่าอสูร":
            pv = self.place_of(a)
            eco = self.eco_ratio(a.world_id, a.place)
            eco = self.eco_ratio(a.world_id, a.place, "beast")          # ล่าอสูรตัดจากคลังสัตว์อสูรของที่นั้นเสมอ
            n = max(1, round(rng.randint(*C.CORE_PER_HUNT) * eco))
            if pv and pv[4] == "แก่นพลัง":
                n += 2
            n = self.eco_take_units(a.world_id, a.place, n, "beast")
            a.cores += n
            # ล่าอสูรเคยให้แต่ของ (แก่นพลัง/วัตถุดิบ) ไม่ให้ความก้าวหน้าเลย ทั้งที่การปะทะของจริง
            # และการกลั่นแก่นพลังคือสายกายของแนวนิยายนี้โดยตรง — เป็นเหตุผลอีกข้อที่โลกไต่ขั้นไม่ขึ้น
            a.refine += min(C.HUNT_REFINE_CAP, C.HUNT_REFINE_PER_CORE * n)
            a.insight += C.HUNT_INSIGHT
            got = self.eco_take_units(a.world_id, a.place, max(1, round(rng.randint(1, 4) * eco)), "beast")
            a.mats += got

            if rng.random() < 0.4:
                k_blood = self.eco_take_units(a.world_id, a.place, rng.randint(1, 2), "beast")
                if k_blood:
                    a.mat_stock["โลหิตอสูรกลั่น"] = a.mat_stock.get("โลหิตอสูรกลั่น", 0) + k_blood
                    d["ของพิเศษ"] = "โลหิตอสูรกลั่น"
            if rng.random() < 0.3:
                k_stone = self.eco_take_units(a.world_id, a.place, rng.randint(1, 3), "beast")
                if k_stone:
                    a.mat_stock["ศิลาปราณห้าธาตุ"] = a.mat_stock.get("ศิลาปราณห้าธาตุ", 0) + k_stone
                    d["ของพิเศษ"] = (d.get("ของพิเศษ", "") + " ศิลาปราณห้าธาตุ").strip()
            # ชิ้นส่วนหายากจากซากอสูร — config.MATERIAL_KINDS เคยนิยามไว้เฉยๆ ไม่มีใครอ่าน
            if MAT.BEAST_PARTS and rng.random() < C.BEAST_PART_P:
                part = rng.choice(MAT.BEAST_PARTS)
                if self.eco_take_units(a.world_id, a.place, 1, "beast"):
                    a.mat_stock[part] = a.mat_stock.get(part, 0) + 1
                    d["ของพิเศษ"] = (d.get("ของพิเศษ", "") + " " + part).strip()

            if pv and pv[4] in ("แร่", "สมุนไพร"):
                # ของที่ได้ต้องคู่ควรกับระดับโลกและเกรดของแหล่ง — เดิมสุ่มจากตารางราคาทั้งก้อน
                # ถ้ำหินแกรนิตดิบในโลกมนุษย์จึงเคยออกแร่ระดับสวรรค์ได้
                pick = MAT.roll_material(a.place, rng, self.eco_ratio(a.world_id, a.place))
                if pick and self.eco_take_units(a.world_id, a.place, 1):
                    a.mat_stock[pick] = a.mat_stock.get(pick, 0) + 1
                    tail = " (แหล่งนี้เริ่มร่อยหรอ)" if eco < 0.5 else ""
                    d["เก็บได้"] = f"{pick} ที่{self.place_name(a)}{tail}"
                    if a.wants.get(pick):
                        left = a.wants[pick] - 1
                        if left > 0:
                            a.wants[pick] = left
                        else:
                            a.wants.pop(pick, None)
                        d["ของที่ตามหา"] = pick
            WAGES.set_gold(self, a, w.tier, a.money.get(w.tier, 0.0) + n * 2.0, "hunt_cores")
            if rng.random() < 0.10 and a.fate <= 0:
                self.kill(a, "ตายในการล่าอสูร")
                return "ตาย", f"{a.name}ตายในการล่าอสูร", d
            return "ได้แก่นพลัง", f"{a.name}ล่าอสูรได้แก่นพลัง {n} เม็ด", d

        if k == "หลอมค่ายกล":
            # ผู้ที่รู้สายหุ่นกลใช้เตาเดียวกันหลอม "หุ่น" แทน "ค่ายกล" — ไม่ต้องเพิ่มชนิดเหตุการณ์
            # ใหม่ในตาราง เพราะทั้งสองอย่างคืองานช่างที่ใช้เตาหลอมเหมือนกัน
            got = self.build_puppet(a, w, rng, d)
            if got is not None:
                return got
            pv = self.place_of(a)
            furnace = pv[5] if pv else -1
            if furnace < 0:
                return "ไม่มีเตา", f"{a.name}อยากหลอมค่ายกล แต่{self.place_name(a)}ไม่มีเตาหลอม", d
            tier = min(a.tier, 2)
            ready_tools = MAT.array_tools_ready(a.mat_stock, tier)
            if not ready_tools:
                target, lack = MAT.plan_array_shortfall(a.mat_stock, tier)
                for name, n in lack.items():
                    a.wants[name] = max(a.wants.get(name, 0), n)
                d["ตั้งใจจะหลอม"] = target
                d["ยังขาด"] = ", ".join(f"{n}×{q}" for n, q in lack.items())
                return ("ขาดวัตถุดิบ",
                        f"{a.name}อยากหลอม{target} แต่ยังขาด{d['ยังขาด']}", d)
            fur = MAT.furnace_of(a.place)
            if fur:
                d["เตาที่ใช้"] = f"{fur[0]} ที่{self.place_name(a)}"
            recipe = rng.choice(ready_tools)
            reqs = MAT.array_mats(recipe, tier)
            MAT.consume(a.mat_stock, reqs)
            d["วัตถุดิบที่ใช้"] = MAT.describe(reqs)
            if rng.random() > C.ARRAY_CRAFT_P:
                return "ล้มเหลว", f"{a.name}หลอม{recipe}ล้มเหลว วัตถุดิบสูญเปล่า", d
            it = self.make_item("อาวุธค่ายกล", w.tier, 1.0, maker=a.cid)
            it.name = recipe
            a.items.append(it.iid)
            d["ได้ของ"] = recipe
            return "สำเร็จ", f"{a.name}หลอม{recipe}สำเร็จ", d

        if k in ("หลอมยา", "หลอมอาวุธ"):
            is_pill = (k == "หลอมยา")
            rk = a.alch_rank if is_pill else a.forge_rank
            if rk < 0:                      # เพิ่งเข้าสาย เริ่มจากฝึกหัด
                rk = 0
                if is_pill:
                    a.alch_rank = 0
                else:
                    a.forge_rank = 0
                d["เข้าสาย"] = CR.ALCHEMY_RANKS[0] if is_pill else CR.FORGE_RANKS[0]
            pv = self.place_of(a)
            furnace = pv[5] if pv else -1
            if furnace < 0:
                return "ไม่มีเตา", f"{a.name}อยากลง{k} แต่{self.place_name(a)}ไม่มีเตาหลอม", d
            if not self.route_to_building(a, ("craft",)):
                return "เดินไปเตาหลอม", f"{a.name}มุ่งหน้าไปยังเตาหลอมกลาง{self.place_name(a)}", d
            fur = MAT.furnace_of(a.place)
            fur_grade = fur[2] if fur else 0
            d["เตาที่ใช้"] = (f"{fur[0]} ที่{self.place_name(a)}" if fur
                              else f"{self.place_name(a)} (เตาระดับ {furnace})")
            if a.cores < C.CRAFT_CORE_COST:
                return "ขาดวัตถุดิบ", f"{a.name}อยากลง{k}แต่แก่นพลังไม่พอ", d
            table = CR.PILLS if is_pill else CR.WEAPONS
            pool = [x for x in table if CR.can_make(rk, x[1], x[2]) and x[1] <= furnace]
            if not pool:
                return "ทำไม่ได้", f"{a.name}ฝีมือยังไม่ถึงจะลง{k}ชิ้นใด", d
            pool.sort(key=lambda x: -(x[1] * 3 + x[2]))
            # เลือกเฉพาะสูตรที่มีวัตถุดิบครบจริง — ของดีที่สุดที่ "ทำได้ตอนนี้"
            ready = [x for x in pool if MAT.can_afford(a.mat_stock, MAT.recipe_mats(x[0]))]
            if not ready:
                # ทำไม่ได้เพราะขาดของ — จำไว้ว่าขาดอะไร แล้วออกไปหา/ไปซื้อ (ดู intent.py)
                target = pool[0]
                lack = MAT.shortfall(a.mat_stock, MAT.recipe_mats(target[0]))
                for name, n in lack.items():
                    a.wants[name] = max(a.wants.get(name, 0), n)
                if len(a.wants) > C.WANT_MAX:
                    for name in list(a.wants)[:-C.WANT_MAX]:
                        a.wants.pop(name, None)
                d["ตั้งใจจะหลอม"] = target[0]
                d["ยังขาด"] = ", ".join(f"{n}×{q}" for n, q in lack.items())
                where = [PL.PLACES[i][0] for i in MAT.sources_of(next(iter(lack), ""))][:2]
                if where:
                    d["หาได้ที่"] = ", ".join(where)
                return ("ขาดวัตถุดิบ",
                        f"{a.name}อยากหลอม{target[0]} แต่ยังขาด{d['ยังขาด']}", d)
            recipe = ready[0] if rng.random() < 0.35 else rng.choice(ready)
            # ลงเตาหนึ่งครั้ง = หลอมได้หลายชิ้นจนกว่าวัตถุดิบหรือแก่นพลังจะหมด ไม่ใช่ชิ้นเดียวจบ
            # ตัวละครหนึ่งคนได้ลงมือแค่ราว 30 ครั้งตลอดชีวิต ถ้าเข้าเตาทั้งทีได้ชิ้นเดียว
            # ของทั้งโลกก็จะมีอยู่ไม่กี่สิบชิ้นตลอดกาล (วัดจริงคือ ~50 ชิ้นใน 15,000 วัน)
            # ของยิ่งสูงชั้นยิ่งหลอมได้น้อยชิ้นต่อเตา — ของสามัญเท่านั้นที่ทำเป็นล็อตได้
            batch_cap = max(1, C.CRAFT_MAX_BATCH - recipe[1] * 2 - recipe[2])
            made, failed, lvl = [], 0, getattr(a, "alchemy" if is_pill else "forge")
            reqs = MAT.recipe_mats(recipe[0])
            used = 0
            while len(made) + failed < batch_cap:
                if a.cores < C.CRAFT_CORE_COST or not MAT.can_afford(a.mat_stock, reqs):
                    break
                MAT.consume(a.mat_stock, reqs)
                a.cores -= C.CRAFT_CORE_COST
                used += 1
                lvl += C.CRAFT_GAIN
                p_ok = min(0.92, C.CRAFT_BASE_P + 0.10 * (rk - recipe[1] * 3 - recipe[2])
                           + 0.05 * lvl + C.FURNACE_GRADE_BONUS * fur_grade)
                if rng.random() > max(0.05, p_ok):
                    failed += 1
                    continue
                if is_pill:
                    it = self.make_item("ยาวิเศษ", recipe[1], 1.0 + recipe[4] * 4, maker=a.cid)
                    it.name = recipe[0]
                    it.power_desc = recipe[3]
                    it.pill_bonus = recipe[4]
                    it.lifespan_bonus = CR.longevity_years(recipe[0], recipe[1], recipe[2])
                else:
                    # เนื้อแร่ในสูตรปรับคุณภาพชิ้นงาน: แร่แข็งคมและคงรูปกว่า แร่อ่อน (ทองคำ ทองแดง) บิ่นง่าย
                    ore_q = MIN.forge_quality(reqs, C.ORE_QUALITY_W)
                    it = self.make_item("อาวุธวิเศษ", recipe[1], recipe[3] * ore_q, maker=a.cid)
                    it.name = recipe[0]
                    if ore_q != 1.0:
                        d["เนื้อแร่"] = f"{'แข็งกว่า' if ore_q > 1 else 'อ่อนกว่า'}ค่ากลาง คุณภาพ ×{ore_q:.2f}"
                a.items.append(it.iid)
                made.append(it.iid)
            setattr(a, "alchemy" if is_pill else "forge", lvl)
            if used:
                d["วัตถุดิบที่ใช้"] = MAT.describe([(m, q * used) for m, q in reqs])
            if not made:
                return ("ล้มเหลว",
                        f"{a.name}หลอม{recipe[0]}ล้มเหลว {failed} ครั้ง วัตถุดิบสูญเปล่า", d)
            d["ได้ของ"] = f"{recipe[0]}×{len(made)}" if len(made) > 1 else recipe[0]
            if failed:
                d["เสียไประหว่างหลอม"] = failed
            # เลื่อนขั้นช่างเมื่อสั่งสมพอ
            need = (rk + 1) * CR.RANK_XP
            if lvl >= need and rk < 8:
                if is_pill:
                    a.alch_rank += 1
                    d["เลื่อนขั้นช่าง"] = CR.ALCHEMY_RANKS[a.alch_rank]
                else:
                    a.forge_rank += 1
                    d["เลื่อนขั้นช่าง"] = CR.FORGE_RANKS[a.forge_rank]
            tail = f" {len(made)} ชิ้น" if len(made) > 1 else ""
            return "สำเร็จ", f"{a.name}หลอม{recipe[0]}สำเร็จ{tail}", d

        if k == "ค้นแดนลับ":
            frag = next((f for f in self.skill_fragments
                         if f["place"] == a.place and not f["found"]
                         and f["piece"] not in a.fragments.get(f["skill"], [])), None)
            if frag and rng.random() < C.FRAGMENT_FIND_P * (1.0 + a.fate * C.FRAGMENT_FATE_BONUS):
                frag["found"] = True
                got = a.fragments.setdefault(frag["skill"], [])
                got.append(frag["piece"])
                need = C.FRAGMENTS_PER_SKILL
                if len(got) >= need and frag["skill"] not in a.skills:
                    a.learn_skill(frag["skill"])
                    # ดัชนีวิชาอยู่ใน rules ไม่ใช่ skills — SK.SKILL_INDEX ไม่เคยมีอยู่จริง
                    # กิ่งนี้จึงโยน AttributeError ล้มทั้งซิมทุกครั้งที่มีคนต่อเศษวิชาครบ
                    # (หายากมากจนไม่เคยโผล่ในเทสต์: FRAGMENT_FIND_P = 0.03 ต่อชิ้น คูณสี่ชิ้น)
                    sk = R.SKILL_INDEX.get(frag["skill"])
                    d["ต่อวิชาสำเร็จ"] = f"ต่อชิ้นส่วนครบ {need}/{need} — ได้วิชา「{frag['skill']}」ขั้นสูงสุดทันที"
                    if sk:
                        d["วิชา"] = f"{SK.GRADE_NAME[sk[3]]} · สาย{sk[1]} — {sk[4]}"
                        if sk[5]:
                            d["แก้ทางโกลาหล"] = "วิชานี้แก้ทางเผ่าโกลาหลได้"
                    return "ต่อวิชาโบราณสำเร็จ", \
                        f"{a.name}ต่อเศษจารึกวิชาโบราณครบทุกชิ้น ตรัสรู้「{frag['skill']}」ในทันที!", d
                d["ชิ้นส่วนวิชา"] = f"พบเศษวิชา「{frag['skill']}」ชิ้นที่ {frag['piece']+1}/{need} (มีแล้ว {len(got)}/{need})"
                return "พบชิ้นส่วนวิชา", \
                    f"{a.name}ขุดพบเศษจารึกวิชาโบราณชิ้นหนึ่งซ่อนอยู่ที่{self.place_name(a)}", d
            found = [c for c in self.caches if c.world_id == w.wid and not c.opened
                     and R.seal_left(c, self.day) <= 0]
            if not found:
                # กฎของโลก: แดนลับมีของเสมอ ต่างกันแค่มากหรือน้อย — ไม่มีแดนลับที่ยังผนึกอยู่
                # ให้เปิด ก็ยังมี "ซาก" ของแดนลับรุ่นก่อนที่ถูกกวาดไปแล้วให้เก็บตก
                out, text = self.ruined_cache_find(a, rng, d)
                return out, text, d
            led_kids = {l["subject"] for l in getattr(a, "rumor_leads", ()) if l["kind"] == "แดนลับ"}
            led = [c for c in found if c.kid in led_kids]
            cache = led[0] if led else rng.choice(found)
            tail = " ตามรอยข่าวลือที่เคยได้ยินมา" if led else ""
            if a.race() == "อสูร":
                a.insight += cache.seal * 0.2
                d["วิวัฒนาการ"] = f"{a.name}ดูดซับพลังแดนลับเพื่อวิวัฒนาการก้าวกระโดด"
                for tier, gold in cache.gold.items():         # ทองในแดนลับไปกับพลังที่ถูกกลืน
                    WAGES.record(self, "cache_devoured", tier, -gold)
                self.caches.remove(cache)
                return "ค้นพบ", f"{a.name}พบแดนลับของ{cache.owner_name} กลืนกินแก่นพลัง{tail}", d
            d.update(self.open_cache(a, cache, rng))
            # กับดัก (เจ้าของแกล้งตายรออยู่) ฆ่าผู้ค้นได้ และถ้าเจ้าของชนะ แดนลับก็ยังไม่ถูกเปิด — เดิมรายงาน "ค้นพบ/เปิดได้"
            # ทุกกรณี ศพจึงเป็นผู้เปิดแดนลับ (test_world_coherence 3.1)
            if not a.alive:
                return "ตาย", f"{a.name}ตายด้วยกับดักในแดนลับของ{cache.owner_name}", d
            if not cache.opened:
                return "ติดกับดัก", f"{a.name}เจอกับดักในแดนลับของ{cache.owner_name} ต้องถอยออกมา", d
            return "ค้นพบ", f"{a.name}เปิดแดนลับของ{cache.owner_name}ได้{tail}", d

        if k == "จำลองอนาคต":
            if not getattr(a, "system_foresight", False):
                return "ไม่มีระบบ", f"{a.name}ไม่มีวิถีหยั่งรู้อนาคตอยู่ในตัว", d
            last = a.visions[-1]["day"] if a.visions else -10 ** 9
            if self.day - last < C.FORESIGHT_COOLDOWN_DAYS:
                left = C.FORESIGHT_COOLDOWN_DAYS - (self.day - last)
                return "ยังไม่ถึงเวลา", f"{a.name}เพ่งมองอนาคต แต่ภาพยังไม่ยอมเปิดให้เห็น " \
                                        f"(อีก {left // 30} เดือน)", d
            from .. import foresight as FS
            vision = FS.glimpse(self, a)
            # ราคาของการมองสิ่งที่ฟ้าไม่ให้เห็น — ไม่มีราคาแล้วความตายก็ไม่เหลือน้ำหนักในเรื่อง
            if a.fate > 0:
                a.fate -= 1
                d["ราคาที่จ่าย"] = f"ชะตาหายไปหนึ่งแต้ม (เหลือ {a.fate})"
            else:
                a.decay += C.FORESIGHT_COST_DECAY
                d["ราคาที่จ่าย"] = "ชะตาหมดแล้ว จึงจ่ายด้วยอายุขัยของตัวเอง"
            a.inner += C.FORESIGHT_INNER
            a.visions.append(vision)
            del a.visions[:-3]
            for cid, day in vision["deaths"].items():
                a.foreseen[str(cid)] = day
            d["นิมิต"] = " | ".join(vision["lines"])
            d["มองไปข้างหน้า"] = f"{vision['horizon'] // 30} เดือน"
            d["จิตมาร"] = f"หนักขึ้นเป็น {a.inner:.1f}"
            return "เห็นอนาคต", f"{a.name}จำลองอนาคตของตนออกมาดู — " \
                                 f"เห็น {len(vision['lines'])} ภาพที่ยังไม่เกิด", d

        if k == "ปิดด่าน":
            years = rng.randint(*C.SECLUDE_YEARS)
            self.start_process(a, "seclusion", years * 365, {"snap": {}}, 1.0)
            a.hidden = True
            a.travel_dest = -1
            # ภาพของโลกตอนเข้าด่าน — ตอนออกมาจะได้รู้ว่าอะไรเปลี่ยนไปบ้าง ไม่ใช่โผล่มาเฉยๆ
            ties = ([a.master_cid] if a.master_cid >= 0 else []) + list(a.disciples[:4]) \
                + list(a.children[:4]) + ([a.spouse] if a.spouse is not None else []) \
                + [c for c, _v in sorted(a.rivals.items(), key=lambda kv: -kv[1])[:4]] \
                + [c for c, _v in sorted(a.bonds.items(), key=lambda kv: -kv[1])[:3]]
            snap = {}
            for cid in ties:
                if isinstance(cid, int) and 0 <= cid < len(self.cast):
                    o = self.cast[cid]
                    snap[str(cid)] = [o.name, int(o.alive), o.rank(), o.realm_name()]
            a.seclude_snap = {"day": self.day, "era": w.era, "state": w.state(),
                              "orgs": sum(1 for o in self.orgs if o.alive),
                              "n_alive": w.n_alive, "ties": snap}
            # ถ้ำกาลเวลา — ปราณยิ่งหนาแน่น เวลาที่ผู้บำเพ็ญ "ได้ใช้" ยิ่งมากกว่าเวลาโลกภายนอก
            # (ดู physics.time_dilation) นี่คือสิ่งที่ทำให้ "สถานที่" มีค่าต่างกันจริงๆ และให้
            # เหตุผลว่าทำไมคนถึงแย่งชิงถ้ำบำเพ็ญกัน — ก่อนหน้านี้ปิดด่านที่ไหนก็ได้เท่ากันหมด
            rho = self.qi_density(a.place, w)
            gamma = PHYS.time_dilation(rho, C.QI_CRITICAL, C.QI_DILATION_CAP)
            a.seclude_snap["gamma"] = gamma
            a.process.yield_rate = gamma          # ผลต่อวันของด่านนี้ (accrue_process)
            d["ปราณ ณ ที่แห่งนี้"] = f"{rho:.0f}/{C.QI_CRITICAL:.0f} ของขีดที่มิติรับไหว"
            d["เวลาที่ได้ใช้จริง"] = (f"{gamma:.2f} เท่าของเวลาข้างนอก"
                                      + (" — ที่นี่แทบไม่ต่างจากข้างนอก" if gamma < 1.15 else
                                         " — ถ้ำดี" if gamma < 2.0 else
                                         " — มิติที่นี่เกือบทนไม่ไหวแล้ว"))
            d["กำหนดออกจากด่าน"] = f"อีก {years} ปี ({E.date_words(a.seclude_until)})"
            d["ฝากไว้กับโลก"] = (f"ยุค{w.state()} · สำนัก {a.seclude_snap['orgs']} แห่ง · "
                                 f"คนในแดน {w.n_alive}")
            return "เข้าด่าน", f"{a.name}ปิดด่านบำเพ็ญ ตัดขาดจากโลกภายนอก {years} ปี", d

        if k == "ซ่อนตัว":
            if a.realm >= C.CACHE_MIN_REALM:
                faked = rng.random() < C.CACHE_TRAP_P
                self.make_cache(a, faked=faked)
                a.hidden = True
                a.hide_day = self.day
                WAGES.clear_gold(self, a, "sealed_in_cache")
                d["แดนลับ"] = "แกล้งตายวางกับดัก" if faked else "ผนึกสมบัติทิ้งไว้"
                # กติกาที่ตัวละครควรรู้ตัวตั้งแต่ก้าวเข้าไป — แดนลับคือที่พัก ไม่ใช่ทางลัด
                d["ราคาของการหายไป"] = "ในแดนลับตัดขาดจากฟ้าดิน สะสมได้แต่เลื่อนขั้นไม่ได้"
                return "ซ่อนตัว", f"{a.name}หายไปจากโลก สร้างแดนลับผนึกสมบัติไว้", d
            self.begin_cultivation(a, gap)
            return "เก็บตัว", f"{a.name}เก็บตัวเงียบไปพักหนึ่ง", d

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

        if k == "ข้ามฟ้า":
            if a.realm < C.ASCEND_MIN_REALM or w.up is None:
                self.begin_cultivation(a, gap)
                return "ยังไม่ถึง", f"{a.name}เพ่งมองฟ้า รู้ว่ายังไม่ถึงเวลา", d
            up = self.world(w.up)
            if up.is_closed and up.tier == 1:
                if C.ASCEND_PEAK_EXCEPTION and a.realm >= C.REALM_CAP:
                    # ผู้ไต่ถึงยอดของโลกตัวเองแล้ว ฟ้าปิดกั้นไว้ไม่ได้ — โควตาประชากรของแดนบนมีไว้
                    # กันคนทั่วไป ไม่ใช่กันคนที่สุดทางของชั้นฟ้าหนึ่งแล้วจริงๆ (ถ้ากันได้หมด ยอด
                    # บันไดของโลกก็เป็นทางตันเงียบๆ — วัดจริง 307 ปี: ข้ามฟ้าจากโลกมนุษย์ 0 ครั้ง)
                    d["ฟ้าเปิดทางให้"] = "ผู้สุดทางของโลกนี้ ประตูปิดกั้นไว้ไม่ได้"
                else:
                    # ให้ได้ "ไปเห็นกำแพงด้วยตาตัวเอง" — เดิม IN.weigh() ลบตัวเลือกนี้ทิ้งตอนประตูปิด
                    # ตัวละครจึงไม่เคยรู้ว่ามีกำแพง และไม่มีเหตุให้คิดถึง "สงครามเบิกฟ้า" เลย
                    d["กำแพง"] = f"ค่ายกลปิดฟ้าของ{up.name} เหลือ {up.defense_array:.0f}/{up.defense_max:.0f}"
                    d["ทางที่เหลือ"] = "ทุบค่ายกลนั้นลง หรือรอจนวันที่ฟ้าเปิดประตูเอง"
                    return "ประตูปิด", f"{a.name}พยายามทะลวงฟ้า แต่ประตูสวรรค์ถูกปิดกั้น!", d
            # โอกาสรอดขึ้นกับการเตรียมตัว ไม่ใช่ทอยเหรียญค่าคงที่ — เดิมตายจริง 34/66 ครั้ง (55%)
            # เท่ากันหมดทั้งคนที่สะสมเกินเกณฑ์สองเท่าและคนที่เพิ่งแตะเกณฑ์พอดี
            req = R.need(a, w)
            acc = R.accumulation(a)
            prep = max(0.0, acc / max(1.0, req) - 1.0)          # สะสมเกินเกณฑ์กี่เท่า
            pills = sum(v for kk, v in (a.inventory or {}).items() if "ยา" in str(kk))
            p_live = min(C.ASCEND_P_MAX, C.ASCEND_P
                         + C.ASCEND_P_PREP_W * min(2.0, prep)
                         + C.ASCEND_P_FATE_W * a.fate
                         + C.ASCEND_P_PILL_W * min(5, pills))
            d["ความพร้อม"] = (f"สะสม {acc:.1f}/{req:.1f} · ชะตา {a.fate} · โอสถ {pills} "
                               f"→ โอกาสรอด {p_live * 100:.0f}%")
            if rng.random() > p_live:
                self.kill(a, "ดับสูญในด่านข้ามฟ้า")
                return "ตาย", f"{a.name}พ่ายในด่านข้ามฟ้า ดับสูญ", d
            up = self.world(w.up)
            old_name = a.realm_name()
            a.drawn = 0.0                       # พลังถูกขนออกจากโลกนี้ถาวร
            self.move_world(a, up.wid)          # ย้ายพร้อมปรับตัวนับประชากรทั้งสองแดน
            a.tier = up.tier
            a.realm = C.ASCEND_RESET_REALM
            a.ascends += 1
            a.peak_tier = max(a.peak_tier, up.tier)
            a.org = None
            # ขั้นภายในชั้นฟ้ากลับไปเป็น 0 แต่ **พลังไม่ลดลงแม้แต่หน่วยเดียว** (ขั้น 9 ของโลกล่าง
            # = ขั้น 0 ของโลกบนพอดีตาม TIER_STEP) และ rank() ก็ไต่ต่อจาก 9 เป็น 10 ไม่ได้ย้อนกลับ
            # สิ่งที่เปลี่ยนคือเขาเพิ่งเห็นว่าบันไดยาวกว่าที่เคยเห็น และตัวเองยืนที่ขั้นล่างสุดของมัน
            locals_ = [c for c in self.living_in(up.wid) if c.cid != a.cid and c.sentient]
            d["ข้ามฟ้า"] = f"{w.name} → {up.name}"
            d["ขั้นของข้า"] = f"{old_name} → {a.realm_name()} (ขั้นที่ {a.rank()} จาก {C.REALM_TOP + 1})"
            if locals_:
                top = max(locals_, key=lambda c: c.rank())
                d["สิ่งที่เพิ่งรู้"] = (f"ขั้นที่ไต่มาสุดชีวิตคือขั้นต่ำสุดของที่นี่ — "
                                        f"ที่นี่มีถึง{top.realm_name()} (ขั้นที่ {top.rank()})")
            return "ข้ามฟ้า", f"{a.name}ข้ามฟ้าขึ้นสู่{up.name} — " \
                              f"ผู้เก่งสุดของโลกเดิมกลายเป็นผู้อ่อนสุดของโลกใหม่", d

        if k == "ลงโลกล่าง":
            pv = self.place_of(a)
            gate = PL.GATES.get(pv[0]) if pv else None
            if not gate:
                return "ไม่มีประตู", f"{a.name}ยังหาทางลงโลกล่างไม่เจอ", d
            fee = gate["fee"]
            if fee and a.money.get(w.tier, 0.0) < fee / 1000.0:
                return "ค่าผ่านทางไม่พอ", f"{a.name}จ่ายค่าเปิด{pv[0]}ไม่ไหว", d
            if fee:
                WAGES.set_gold(self, a, w.tier, a.money.get(w.tier, 0.0) - fee / 1000.0, "gate_fee")
            key = gate["to"]
            dest = next((x for x in self.worlds
                         if x.place_key == key and x.kind != "chaos"), None)
            if dest is None:
                return "ประตูปิด", f"{pv[0]}ไม่เปิดในเวลานี้", d
            self.move_world(a, dest.wid)        # ย้ายพร้อมปรับตัวนับประชากรทั้งสองแดน
            a.tier = dest.tier
            a.peak_tier = max(a.peak_tier, a.tier)   # ผ่านประตูขึ้นแดนชั้นสูง — นับเป็นขั้นสูงสุดด้วย
            a.realm = max(0, a.realm - gate["push"])
            pl = PL.places_in(dest.place_key)
            a.place = rng.choice(pl) if pl else -1
            a.org = None
            d["ลงโลกล่าง"] = (f"ผ่าน{pv[0]} → {dest.name} "
                              f"(ถูกกดพลัง {gate['push']} ขั้น เหลือ {a.realm_name()})")
            if fee:
                d["ค่าผ่านทาง"] = f"{fee:,} {PL.CURRENCY[min(w.tier, 2)]}"
            return "ลงโลกล่าง", f"{a.name}ก้าวลงสู่{dest.name}ผ่าน{pv[0]}", d

        if k == "ไส้ศึกลงมือ":
            if a.spy_for is None or a.org is None:
                return "ไม่ใช่ไส้ศึก", f"{a.name}ใช้ชีวิตไปตามปกติ", d
            host = self.orgs[a.org]
            master = self.orgs[a.spy_for] if a.spy_for < len(self.orgs) else None
            if master is None or not host.alive:
                return "ไร้นาย", f"{a.name}ขาดการติดต่อกับนายเก่า", d
            mode = rng.choice(["รั่วข่าวแดนลับ", "ก่อวินาศกรรม", "เปิดทางให้ศัตรู"])
            host.grudges[master.oid] = host.grudges.get(master.oid, 0) + 4
            if mode == "รั่วข่าวแดนลับ":
                pool = [c for c in self.caches if c.world_id == w.wid and not c.opened]
                if pool:
                    tgt = rng.choice(pool)
                    tgt.seal = min(tgt.seal, 1.0)     # ผนึกถูกเปิดเผยพิกัด
                    d["ข่าวรั่ว"] = f"พิกัดแดนลับของ{tgt.owner_name}ถึงมือ{master.name}"
            elif mode == "ก่อวินาศกรรม":
                victims = [c for c in self.living_in(w.wid)
                           if c.org == host.oid and c.items and c.cid != a.cid]
                if victims:
                    v = rng.choice(victims)
                    iid = v.items.pop()
                    self.items[iid].condition *= 0.2
                    d["วินาศกรรม"] = f"ของของ{v.name}ถูกทำให้เสียหาย"
            else:
                foes = [c for c in self.living_in(w.wid) if c.org == master.oid]
                if foes:
                    f = rng.choice(foes)
                    victims = [c for c in self.living_in(w.wid) if c.org == host.oid]
                    if victims:
                        v = rng.choice(victims)
                        win, lose, margin, res = R.fight(self, w, f, v, rng, day=self.day)
                        d["เปิดทาง"] = f"{f.name}เข้าโจมตี{v.name} — {res}"
                        d["margin"] = round(margin, 3)
                        d["winner"] = win.cid
            a.inner += 1.0
            R.add_debt(a, "ทรยศ", self.org_head(host), host.name, self.day)
            return "ไส้ศึกลงมือ", f"{a.name}ลงมือให้{master.name}จากในไส้ของ{host.name}", d

        if k == "เข้าสำนัก":
            # ก่อนหน้านี้สำนักโตได้ทางเดียวคือ "ตั้งใหม่" ไม่มีใครเข้าสังกัดสำนักที่มีอยู่เลย
            # ผลคือมีคนสังกัดสำนักแค่ 2% ของประชากร สงครามสำนัก/ไส้ศึกจึงแทบไม่มีความหมาย
            if a.org is not None:
                return "มีสังกัดแล้ว", f"{a.name}มีสังกัดอยู่แล้ว", d
            here = []
            for org in self.orgs:
                if not org.alive or org.world_id != w.wid:
                    continue
                if org.mara != a.hated():          # ฝ่ายธรรมะกับลัทธิมารไม่รับกันและกัน
                    continue
                n_here = sum(1 for m in org.members
                             if m < len(self.cast) and self.cast[m].alive
                             and self.cast[m].place == a.place)
                if n_here:
                    here.append((org, n_here))
            if not here:
                return "ไม่มีสำนักแถวนี้", f"{a.name}ยังไม่เจอสำนักที่รับคนแถว{self.place_name(a)}", d
            here.sort(key=lambda x: -x[1])
            org = here[0][0]
            founder = self.cast[self.org_head(org)] if self.org_head(org) < len(self.cast) else None
            if founder is not None and a.realm > founder.realm:
                return "ไม่ยอมก้มหัว", f"{a.name}ฝีมือเหนือกว่าผู้ก่อตั้ง{org.name} จึงไม่ยอมเข้าสังกัด", d
            if rng.random() > C.ORG_JOIN_P:
                return "ยังไม่ตัดสินใจ", f"{a.name}ลังเลที่จะเข้าสังกัด{org.name}", d
            a.org = org.oid if org.oid < len(self.orgs) else self.orgs.index(org)
            a.org = self.orgs.index(org)
            org.members.append(a.cid)
            rank = "ศิษย์สายใน" if a.realm >= C.ORG_INNER_REALM else "ศิษย์สายนอก"
            (org.inner_disciples if rank == "ศิษย์สายใน" else org.outer_disciples).append(a.cid)
            d["สำนัก"] = org.name
            d["ตำแหน่ง"] = rank
            d["ที่"] = self.place_name(a)
            # เข้าสำนักศัตรูของสำนักที่ตัวเองเคยแค้น = โอกาสเป็นไส้ศึกในอนาคต
            return "เข้าสังกัด", f"{a.name}เข้าเป็น{rank}ของ{org.name}ที่{self.place_name(a)}", d

        if k == "ตั้งสำนัก":
            bar = C.ORG_FOUND_REALM_MARA if a.hated() else C.ORG_FOUND_REALM
            if a.realm < bar or a.org is not None:
                return "ผ่านไป", f"{a.name}ใช้ชีวิตไปตามทาง", d
            if rng.random() > (C.ORG_FOUND_P_MARA if a.hated() else C.ORG_FOUND_P):
                return "ผ่านไป", f"{a.name}คิดจะตั้งสำนักแต่ยังไม่ลงมือ", d
            is_mara = a.hated()
            kind = "ลัทธิมาร" if is_mara else rng.choice(C.ORG_KINDS)
            oname = (rng.choice(E.MARA_WORD) + rng.choice(E.MARA_TAIL)) if is_mara \
                else (rng.choice(E.ORG_WORD) + rng.choice(E.ORG_TAIL))
            org = Org(oid=self.nid("o"), kind=kind, name=oname, mara=is_mara,
                      world_id=w.wid, founder=a.cid, founded_day=self.day)
            org.members.append(a.cid)
            a.org = org.oid
            # ลัทธิมารกับสำนักมนุษย์เป็นศัตรูกันแต่ต้น
            for other in self.orgs:
                if other.alive and other.world_id == w.wid and other.mara != is_mara:
                    org.grudges[other.oid] = org.grudges.get(other.oid, 0) + 2
                    other.grudges[org.oid] = other.grudges.get(org.oid, 0) + 2
            self.orgs.append(org)
            for c in self.living_in(w.wid):
                if c.hated() != is_mara:
                    continue          # สำนักมนุษย์ไม่รับมนุษย์มาร และกลับกัน
                if c.org is None and rng.random() < C.ORG_JOIN_P:
                    c.org = org.oid
                    org.members.append(c.cid)
                    if rng.random() < C.SPY_P:
                        c.spy_for = rng.choice([o.oid for o in self.orgs]) if self.orgs else None
            d["ก่อตั้ง"] = f"{kind} {org.name} สมาชิก {len(org.members)} คน" + (" (ลัทธิมนุษย์มาร)" if is_mara else "")
            return "ก่อตั้ง", f"{a.name}ก่อตั้ง{org.name}", d

        if k == "เดินทาง":
            # เดินทางจริงบนกราฟภูมิศาสตร์ (tiandao/geo.py + travel.py) แทนการ teleport ทันทีแบบเดิม —
            # เลือกจุดหมายด้วย logic เดิมเป๊ะ (seek/avoid จากข่าวลือ) แค่ไม่ใส่ a.place ทันที เปลี่ยนเป็น
            # ตั้ง travel_dest/travel_arrival_day แล้วให้ Sim.step() (บล็อกเดียวกับ ch.hidden) จัดการ
            # เดินทางหลายวันจริง + เหตุการณ์ระหว่างทางแทน (ดู sim.py ใกล้ "elif ch.travel_dest >= 0:")
            pl = [p for p in PL.places_in(w.place_key) if p != a.place]
            if pl:
                old = self.place_name(a)
                seek = {l["subject"] for l in getattr(a, "rumor_leads", ()) if l["kind"] == "อุดมสมบูรณ์"}
                avoid = {l["subject"] for l in getattr(a, "rumor_leads", ()) if l["kind"] == "ขาดแคลน"}
                frag_place = {f["fid"]: f["place"] for f in self.skill_fragments}
                seek |= {frag_place[l["subject"]] for l in getattr(a, "rumor_leads", ())
                         if l["kind"] == "ชิ้นส่วนวิชา" and l["subject"] in frag_place}
                # จุดหมายที่ "มีของที่ตัวเองกำลังขาด" มาก่อนข่าวลือทั่วไป — ถ้าไม่ผูกตรงนี้
                # แรงผลักจาก intent.py จะทำได้แค่ให้ออกเดินทาง แต่เดินสะเปะสะปะไม่ถึงแหล่ง
                want_pl = []
                for m in getattr(a, "wants", ()):
                    want_pl += [i for i in MAT.sources_in_world(m, w.place_key) if i != a.place]
                want_pl = [p for p in want_pl if p in pl]
                seek_pl = [p for p in pl if p in seek]
                safe_pl = [p for p in pl if p not in avoid] or pl
                if want_pl and rng.random() < C.WANT_SEEK_P:
                    dest = self.pick_destination(a, want_pl, rng)
                    tail_want = True
                elif seek_pl and rng.random() < 0.6:
                    dest = self.pick_destination(a, seek_pl, rng)
                    tail_want = False
                else:
                    dest = self.pick_destination(a, safe_pl, rng)
                    tail_want = False
                allow_barrier = getattr(self, "mara_seal_broken", False) or (getattr(self, "mara_seal", 100.0) <= getattr(C, "MARA_SEAL_WEAK_THRESHOLD", 30.0) and rng.random() < getattr(C, "MARA_SEAL_LEAK_P", 0.15))
                days = TR.shortest_path_days(a.place, dest, a.realm,
                                             allow_mara_barrier=allow_barrier,
                                             character=a, day=self.day)
                if days is None:
                    # ไม่ควรเกิดจริง (pl มาจาก world_key เดียวกันซึ่งเชื่อมกันหมดในตัว geo.py เสมอ)
                    # กันไว้เผื่อข้อมูลกราฟผิดพลาดในอนาคต — ไม่เดินทาง แทนที่จะพัง
                    return "ผ่านไป", f"{a.name}ยังหาทางไปไม่เจอ", d
                dest_name = PL.PLACES[dest][0]
                if C.FOOD_ENABLED and not FOOD.provision(self, a, days):
                    # ซื้อเสบียงได้ไม่พอกินจนถึงจุดหมาย — ไม่ออกไปอดตายกลางทาง (tiandao/food.py)
                    d["เสบียง"] = f"ไม่พอกินตลอดทาง {days} วัน"
                    return "ผ่านไป", f"{a.name}อยากไป{dest_name} แต่เสบียงไม่พอเดินทาง {days} วัน", d
                self.start_process(a, "travel", days, {"dest": dest, "origin": a.place})
                tail = ""
                if tail_want:
                    lack = ", ".join(list(a.wants)[:2])
                    tail = f" (ออกไปตามหา{lack})"
                elif dest in frag_place.values() and dest in seek:
                    tail = " (ตามข่าวลือไปตามหาเศษวิชาโบราณ)"
                elif dest in seek:
                    tail = " (ตามข่าวลือว่าที่นี่กลับมาอุดมสมบูรณ์)"
                d["เดินทาง"] = f"{old} → {dest_name} (คาดว่าใช้เวลา {days} วัน)"
                return "ออกเดินทาง", f"{a.name}ออกเดินทางจาก{old}มุ่งหน้าสู่{dest_name}{tail}", d
            return "ผ่านไป", f"{a.name}ออกเดินทาง", d

        if k == "ค้าขาย":
            pv = self.place_of(a)
            at_market_place = bool(pv and pv[3] in ("ตลาด", "เมือง"))
            if at_market_place and not self.route_to_building(a, ("market",)):
                return "เดินไปตลาด", f"{a.name}มุ่งหน้าไปยังตลาดกลาง{self.place_name(a)}", d
            mult = 3.0 if at_market_place else 1.0
            # ตลาดจ่ายจากทุนสำรองของที่นี้ (เงินที่ชาวบ้านใช้จ่ายเข้าตลาด wages.tick) ไม่เกินความลึกของตลาด — ขั้น B3b
            # เดิมทองเกิดจากอากาศราวหมื่นต่อปี และของที่เกินความลึกหายจากถุงทั้งที่ไม่ได้เงิน
            # ปิดค่าแรงอยู่ = ไม่มีเงินใช้จ่ายเข้าตลาดให้กันเป็นทุน ตลาดจ่ายแบบเดิม (ทองเกิด บันทึก market_sale) เหมือน fiat_pay
            # ทุนสำรองที่รับซื้อได้: ที่นี่ก่อน แล้วตลาดในระยะส่งข้าวถึง (FOOD_REACH_HOPS) ใกล้ไปไกล — วัดแล้วถ้าใช้ของที่นี่อย่างเดียว
            # ขายได้แค่ราว 200 ทองต่อปี เพราะคนขายของที่แหล่งวัตถุดิบ แต่เงินใช้จ่ายเข้าตลาดในเมือง
            spot = (a.world_id, a.place)
            depth = WAGES.market_depth(self, a.world_id, a.place)
            funds = [spot] + ([(a.world_id, p) for p, _h in TR.places_within(self, a.place, C.FOOD_REACH_HOPS)]
                              if a.place is not None and a.place >= 0 else [])
            # แล้วกองทุนเหมืองของชั้นนี้ (ทองที่ขุดได้ รับซื้อวัตถุดิบ — wages._mine)
            reserve = (sum(self.market_reserve.get(f, 0.0) for f in funds)
                       + self.mine_purse.get(w.tier, 0.0)) if C.WAGES_ENABLED else depth
            budget = min(reserve, depth)
            gain = min(rng.uniform(0.5, 3.0) * mult, budget)       # กำไรจากการค้าเล็ก ๆ น้อย ๆ ก็จ่ายจากทุนสำรอง
            # ขายวัตถุดิบที่สะสมไว้ตามราคาประเมิน ทีละชิ้นเท่าที่ทุนสำรองรับไหว ที่เหลืออยู่ในถุง
            sold, unsold = [], 0.0
            # ช่างเก็บของที่สูตรของตัวเองต้องใช้ไว้ ไม่เทขายทิ้งแล้วมาบ่นว่าขาดวัตถุดิบทีหลัง
            useful = ()
            if a.alch_rank >= 0 or a.forge_rank >= 0:
                useful = MAT.useful_to(a.alch_rank, a.forge_rank, min(a.tier, 2))
            for name, n in list(a.mat_stock.items()):
                price = self.price_now(w, name, MAT.market_price(name))
                keep = a.wants.get(name, 0)     # ของที่ตัวเองยังต้องใช้ ไม่ขาย
                if name in useful:
                    keep = max(keep, C.CRAFT_KEEP_STOCK)
                n_sell = n - keep
                if price and n_sell > 0:
                    unit = price / C.MAT_COIN_DIV
                    fit = min(n_sell, int((budget - gain) // unit)) if unit > 0 else n_sell
                    unsold += unit * (n_sell - fit)
                    if fit <= 0:
                        continue
                    gain += unit * fit
                    sold.append(f"{name} x{fit}")
                    if n - fit > 0:
                        a.mat_stock[name] = n - fit
                    else:
                        a.mat_stock.pop(name, None)
            # ความลึกของตลาด — ตลาดหมู่บ้านไม่มีเงินพอจะรับของระดับสมบัติ
            # ก่อนหน้านี้ไม่มีเพดานเลย คนหนึ่งขายแร่กองหนึ่งแล้วได้เงิน 1.4 ล้านในห้ารอบ
            # (วัดจริง: คนรวยที่สุดของโลกลงมือแค่ 27 ครั้งตลอดชีวิต ค้าขาย 5 ครั้ง)
            # ของที่ขายไม่หมดยังอยู่ในถุง ต้องเอาไปตลาดใหญ่กว่าหรือรอรอบหน้า —
            # ซึ่งเป็นเหตุผลที่งานประมูลมีอยู่ในโลกนี้ตั้งแต่แรก
            if unsold > 0:
                d["ตลาดรับไม่ไหว"] = (f"ขายได้ {gain:,.0f} ยังเหลือของมูลค่า {unsold:,.0f} "
                                       f"— ที่นี่ไม่มีเงินพอ ต้องไปตลาดใหญ่กว่าหรือเข้าประมูล")
            if not C.WAGES_ENABLED:
                WAGES.set_gold(self, a, w.tier, a.money.get(w.tier, 0.0) + gain, "market_sale")
            else:
                # ของที่มาขาย (เพดานทุนสำรอง wages.tick) แบ่งเท่ากันให้ทุกตลาดในระยะ — ผลรวมเพดานเท่ากับของที่มาขายจริง
                demand = self.__dict__.setdefault("market_demand", {})
                for f in funds:
                    demand[f] = demand.get(f, 0.0) + (gain + unsold) / len(funds)
                if unsold > 0:
                    self.wage_stats["market_unsold"] = self.wage_stats.get("market_unsold", 0.0) + unsold
                if gain > 0:
                    owed = gain
                    for f in funds:                                     # จ่ายจากที่ใกล้ก่อน
                        part = min(self.market_reserve.get(f, 0.0), owed)
                        if part > 0:
                            self.market_reserve[f] -= part
                            owed -= part
                        if owed <= 1e-12:
                            break
                    if owed > 1e-12:                                    # ส่วนที่เหลือ กองทุนเหมืองรับซื้อ
                        self.mine_purse[w.tier] = self.mine_purse.get(w.tier, 0.0) - owed
                        self.wage_stats["mine_bought"] = self.wage_stats.get("mine_bought", 0.0) + owed
                    a.money[w.tier] = a.money.get(w.tier, 0.0) + gain
                    self.wage_stats["market_paid"] = self.wage_stats.get("market_paid", 0.0) + gain

            # ซื้อของที่ "ตัวเองต้องการจริง" ไม่ใช่ของสุ่มที่ไม่มีสูตรไหนใช้
            # ตลาดมีของตามระดับโลกที่ตลาดนั้นตั้งอยู่ ของสูงกว่านั้นต้องขึ้นไปซื้อเอง
            bought = []
            if at_market_place and a.wants:
                budget = a.money.get(w.tier, 0.0)
                for name, need in list(a.wants.items()):
                    if MAT.MAT_TIER.get(name, 0) > w.tier:
                        continue
                    price = (self.price_now(w, name, MAT.price_of(name))
                             / C.MAT_COIN_DIV * C.MARKET_MARKUP)
                    qty = 0
                    while qty < need and budget >= price and rng.random() < C.MARKET_STOCK_P:
                        budget -= price
                        qty += 1
                    if qty:
                        a.mat_stock[name] = a.mat_stock.get(name, 0) + qty
                        left = need - qty
                        if left > 0:
                            a.wants[name] = left
                        else:
                            a.wants.pop(name, None)
                        bought.append(f"{name} x{qty}")
                if not C.WAGES_ENABLED:
                    WAGES.set_gold(self, a, w.tier, budget, "market_purchase")
                else:
                    paid = a.money.get(w.tier, 0.0) - budget   # ซื้อจากตลาด — ทองเข้าทุนสำรองของที่นี้ (เดิมหายไป)
                    a.money[w.tier] = budget
                    self.market_reserve[spot] = self.market_reserve.get(spot, 0.0) + paid
            if bought:
                d["ซื้อ"] = ", ".join(bought[:3])
            if a.wants:
                d["ยังตามหา"] = ", ".join(list(a.wants)[:3])
            if sold:
                d["ขายของ"] = ", ".join(sold[:3])
            d["ที่"] = self.place_name(a)
            d["กำไรรอบนี้"] = f"{gain:,.0f}"
            # ของที่ราคาผิดปกติในแดนนี้ตอนนี้ — เป็นข้อมูลที่ทำให้การค้าเป็นการตัดสินใจจริง
            hot = []
            for name in list(a.wants or ())[:3]:
                b = MAT.price_of(name)
                if not b:
                    continue
                mult = self.price_now(w, name, b) / max(1e-9, b)
                if mult >= C.PRICE_NEWSWORTHY or mult <= 1.0 / C.PRICE_NEWSWORTHY:
                    hot.append(f"{name} {'แพงขึ้น' if mult > 1 else 'ถูกลง'} {mult:.1f} เท่า")
            if hot:
                d["ราคาผิดปกติ"] = " · ".join(hot)
            return "ค้าขาย", f"{a.name}ค้าขายที่{self.place_name(a)} ได้กำไร {gain:,.0f}", d

        if k == "ภัยธรรมชาติ":
            a.decay += 0.7
            if a.realm == 0 and rng.random() < 0.20:
                if a.fate > 0:
                    a.fate -= 1
                    a.near_death += 1
                    return "รอดตายด้วยชะตา", f"{a.name}เกือบตายในภัยพิบัติ", d
                self.kill(a, "ตายในภัยพิบัติ")
                return "ตาย", f"{a.name}ตายในภัยพิบัติ", d
            return "รอดมาได้", f"{a.name}ฝ่าภัยพิบัติมาได้", d

        if k == "กำเนิดทายาท":
            if a.age(self.day) < 16 or t.age(self.day) < 16:
                return "ยังไม่ถึงวัย", f"{a.name}กับ{t.name}ยังไม่ถึงวัยมีทายาท", d
            if a.gender == "ไม่มีเพศ" or t.gender == "ไม่มีเพศ" or a.gender == t.gender:
                return "ล้มเหลว", f"{a.name}และ{t.name}ไม่สามารถมีทายาทร่วมกันได้", d
                
            self.marry(a, t)                     # ผูกพันธะคู่ครองถ้ายังโสดทั้งคู่
                
            # เช็คเผ่าพันธุ์ต้องห้าม (มนุษย์กับมาร)
            if a.race() == "มนุษย์" and t.race() == "มาร":
                if "พัวพันกับมาร" not in a.traits: a.traits.append("พัวพันกับมาร")
            elif a.race() == "มาร" and t.race() == "มนุษย์":
                if "พัวพันกับมาร" not in t.traits: t.traits.append("พัวพันกับมาร")

            mother = a if a.gender == "หญิง" else t
            father = t if mother is a else a
            if mother.pregnancy is not None or mother.postpartum_until > self.day:
                why = "ตั้งครรภ์อยู่แล้ว" if mother.pregnancy is not None else "เพิ่งคลอด ยังพักฟื้นอยู่"
                return "ยังไม่มีทายาท", f"{mother.name}{why}", d
            fertile = self.fertility(w)
            if fertile < 1.0 and rng.random() >= fertile:
                d["คนในแดน"] = f"{w.n_alive}/{C.POP_K_MULT * self.realm_target(w):.0f}"
                return "ยังไม่มีทายาท", f"{a.name}กับ{t.name}ยังไม่มีทายาท แดนนี้คนแน่นแล้ว", d
            p = self.conceive(mother, father, a)
            d["กำหนดคลอด"] = f"อีก {p.end_day - self.day} วัน"
            return "ตั้งครรภ์", f"{mother.name}ตั้งครรภ์กับ{father.name}", d

        if k == "ให้สัญญา":
            if a.ascends > 0 and t.ascends == 0:
                a.bonds[t.cid] = a.bonds.get(t.cid, 0) + 1 # ไม่ได้ใจคนพื้นเมือง
                d["อคติ"] = f"{t.name} ยังคงมีอคติกับผู้ทะยานข้ามฟ้า"
            else:
                a.bonds[t.cid] = a.bonds.get(t.cid, 0) + 1
                t.bonds[a.cid] = t.bonds.get(a.cid, 0) + 1
            d["คำสาบาน"] = R.oath_form(a)
            return "ผูกพัน", f"{a.name}ให้สัญญากับ{t.name} โดย{R.oath_form(a)}", d

        if k == "ถ่ายทอดวิชา":
            # บั๊กคลาสเดียวกับ "ทรยศ" และ "สงครามสำนัก": กลไกที่ถูกเลือกบ่อยมากแต่ไม่เคย
            # ส่งมอบสิ่งที่ชื่อของมันบอกเลย วัดจริงโลก 50 ปี: ถ่ายทอดวิชา **2,882 ครั้ง**
            # แต่ผู้รับได้แค่ความเข้าใจ +0.5 กับความผูกพัน — **ไม่เคยได้วิชาสักอันเดียว**
            # ผลคือผู้บำเพ็ญ 309 จาก 828 คนไม่มีวิชาเลยทั้งที่อายุมัธยฐาน 48 ปี เพราะทางเดียว
            # ที่จะได้วิชาคือฝึกเอาเองเท่านั้น สายสำนักกับสายตระกูลจึงไม่มีความหมายในทางกลไก
            t.insight += 0.5
            if a.ascends > 0 and t.ascends == 0:
                t.bonds[a.cid] = t.bonds.get(a.cid, 0) + 0 # อคติ
                d["อคติ"] = f"{t.name} รับวิชาแต่ไม่ซาบซึ้งใจผู้ทะยานข้ามฟ้า"
            else:
                t.bonds[a.cid] = t.bonds.get(a.cid, 0) + 2
            if not isinstance(getattr(a, "mastery", None), dict):
                a.mastery = {}
            if not isinstance(getattr(t, "mastery", None), dict):
                t.mastery = {}
            # สอนได้เฉพาะวิชาที่ **ตัวเองเข้าใจพอ** และผู้รับยังไม่มี — เลือกอันที่ชำนาญที่สุด
            teachable = R.teachable(a, t)
            if not teachable:
                # แยก outcome ออกให้วัดได้ — ไม่งั้น "สอนแล้วไม่มีอะไรจะสอน" กับ "สอนสำเร็จ"
                # จะถูกนับรวมกันจนมองไม่เห็นว่ากลไกทำงานจริงหรือเปล่า (บทเรียนจากรอบที่แล้ว)
                d["ที่ผู้รับได้"] = "ได้แต่หลักคิด ไม่ได้ตัววิชา"
                return "ไม่มีวิชาจะสอน", f"{a.name}ถ่ายทอดวิถีให้{t.name} แต่ไม่มีวิชาที่ส่งต่อได้", d
            # รับได้ไหม ขึ้นกับสามอย่าง: ขั้นของผู้รับถึงเกรดวิชาไหม · ธาตุถูกกันไหม ·
            # อาจารย์เข้าใจลึกแค่ไหน (สอนสิ่งที่ตัวเองรู้ครึ่งๆ กลางๆ ก็ได้ผลครึ่งๆ กลางๆ) — rules.teach_chance
            name = teachable[0]
            d["p"], deep = R.teach_chance(a, t, name)
            d["วิชาที่สอน"] = f"{name} (ธาตุ{EL.skill_element(name)} · อาจารย์ชำนาญ {deep:.0%})"
            if rng.random() > d["p"]:
                t.insight += C.TRAIN_FAIL_INSIGHT
                d["ที่ผู้รับได้"] = "ยังรับไม่ไหว ได้แต่เค้าโครง"
                return "รับไม่ไหว", f"{a.name}ถ่ายทอด{name}ให้{t.name} แต่{t.name}ยังรับไม่ไหว", d
            # ได้รูปมา แต่ยังไม่ได้ความลึกของอาจารย์ — ต้องไปฝึกเอง (ดู physics.practice_mastery)
            t.learn_skill(name)
            t.insight += C.TRAIN_INSIGHT_BASE * C.TEACH_INSIGHT_SHARE
            a.merit = getattr(a, "merit", 0.0) + 1.0
            d["ที่ผู้รับได้"] = f"ได้วิชา「{name}」ไปทั้งอัน แต่ยังตื้น ต้องไปฝึกเอง"
            return "ถ่ายทอด", f"{a.name}ถ่ายทอด{name}ให้{t.name}จนรับไปได้ทั้งวิชา", d

        if k in ("ทรยศ", "หักหลัง"):
            # บั๊กที่อยู่มานาน: ตารางเหตุการณ์ใช้ชื่อ "ทรยศ" แต่ handler นี้เคยเช็ค "หักหลัง"
            # จึง **ไม่เคยทำงานเลยสักครั้ง** (วัดจริง 102 ปี: "หักหลัง" 0 ครั้ง) การทรยศทั้ง
            # 2,489 ครั้งเลยไหลไปจบที่กิ่งประลองท้ายฟังก์ชัน คือกลายเป็น "ดวลกันตาย" 317 ศพ
            # และข้อความอ่านไม่ได้ความ: "ทาริกทรยศกับจาฟาร์ — ทาริกดับดิ้น" (คนทรยศตายเอง)
            tie = R.trust_tie(self, a, t)
            if tie is None:
                # ทรยศคนแปลกหน้าไม่ได้ ต้องมีความไว้ใจอยู่ก่อนจึงจะมีอะไรให้หักหลัง
                return "ไม่มีใครให้ทรยศ", f"{a.name}ไม่มีใครแถวนี้ที่ไว้ใจเขาพอจะถูกหักหลัง", d
            d["ความไว้ใจที่ถูกใช้"] = tie
            dmg = 3
            if a.ascends > 0 and t.ascends == 0:
                dmg *= 2
                d["อคติ"] = f"{t.name} แค้นพวกหน้าใหม่เป็นทวีคูณ"
            t.rivals[a.cid] = t.rivals.get(a.cid, 0) + dmg
            t.bonds.pop(a.cid, None)
            a.bonds.pop(t.cid, None)
            # การหักหลังคือการฉกฉวยจากความไว้ใจ ไม่ใช่การดวล — ของและความลับเปลี่ยนมือ ไม่ใช่ชีวิต
            # (ถ้าเขาอยากเอาชีวิตจริง นั่นคือ "ลอบสังหาร" ซึ่งมีกลไกและเงื่อนไขของตัวเองอยู่แล้ว)
            gain = []
            spoil = [i for i in t.items if self.items[i].kind != "ยาวิเศษ"]
            if spoil:
                iid = spoil[0]
                t.items.remove(iid)
                a.items.append(iid)
                self.items[iid].owner = a.cid
                gain.append(self.items[iid].name)
            cash = int(t.money.get(w.tier, 0) * 0.4)
            if cash > 0:
                t.money[w.tier] = t.money.get(w.tier, 0) - cash
                a.money[w.tier] = a.money.get(w.tier, 0) + cash
                gain.append(f"{cash} เหรียญ")
            if t.skills and (not a.skills or len(a.skills) < len(t.skills)):
                sk = t.skills[-1]
                if a.learn_skill(sk):
                    gain.append(f"วิชา{sk}")
            if a.org is not None and a.org == t.org and a.org < len(self.orgs):
                org = self.orgs[a.org]
                org.grudges[a.org] = org.grudges.get(a.org, 0)   # รอยร้าวในสำนักเดียวกัน
                d["รอยร้าว"] = f"เรื่องนี้เกิดขึ้นในสำนัก{org.name}เอง"
            if t.master_cid == a.cid and t.cid in a.disciples:
                a.disciples.remove(t.cid)
                t.master_cid = -1
                d["ความสัมพันธ์ที่ขาด"] = "ศิษย์-อาจารย์"
            before_inner = a.inner
            R.add_debt(a, "ทรยศ", t.cid, t.name, self.day)
            d["ที่ได้ไป"] = ", ".join(gain) if gain else "ไม่ได้อะไรติดมือ นอกจากความแค้น"
            if a.inner > before_inner:
                d["จิตมาร"] = f"{a.name} +หนี้ค้างคา (รวม {a.inner:.1f})"
            else:
                # คนที่ไร้จิตมาร (inner_none) หักหลังแล้วไม่ค้างคาใจเลย — เดิมบันทึกโม้ว่า
                # "+หนี้ค้างคา (รวม 0.0)" ทั้งที่ไม่มีอะไรเพิ่ม อ่านย้อนแล้วเข้าใจผิดได้
                d["จิตมาร"] = f"{a.name}ไร้จิตมาร เรื่องนี้ไม่ค้างคาใจเขาเลย"
            return "หักหลัง", f"{a.name}หักหลัง{t.name}ผู้ที่{tie}" \
                              + (f" ชิง{gain[0]}ไป" if gain else ""), d

        if k == "สะสางเรื่องเก่า":
            if R.settle_debt(a, t.cid):
                d["จิตมาร"] = f"คลายลงเหลือ {a.inner:.1f}"
                return "สะสาง", f"{a.name}กลับไปสะสางเรื่องค้างคากับ{t.name}", d
            return "ไม่มีอะไรค้าง", f"{a.name}พบ{t.name}อีกครั้ง ไม่มีอะไรค้างคา", d

        if k == "ชิงสมบัติ":
            treas = [i for i in t.items if self.items[i].kind != "ยาวิเศษ"]
            if not treas:
                return "ไม่มีของ", f"{a.name}หมายตาสมบัติของ{t.name} แต่ไม่มีอะไรให้ชิง", d
            win, lose, margin, res = R.fight(self, w, a, t, rng)
            d["margin"] = round(margin, 3)
            d["winner"] = win.cid
            left = [i for i in treas if i in t.items]     # หนีด้วยยันต์ได้ ยันต์หายไปแล้วและไม่เสียของ
            if win is a and lose.alive and res != "หนีรอด" and left:
                iid = left[0]
                t.items.remove(iid)
                a.items.append(iid)
                d["ชิงได้"] = self.items[iid].name
            lose.rivals[win.cid] = lose.rivals.get(win.cid, 0) + 2
            return res, f"{a.name}ชิงสมบัติจาก{t.name} — {lose.name}เป็นฝ่ายเสีย", d

        if k == "สงครามสำนัก":
            if a.org is None or t.org is None or a.org == t.org:
                return "ล้มเหลว", f"{a.name}พยายามก่อสงครามแต่เป้าหมายไม่ชัดเจน", d
            
            org_a = self.orgs[a.org]
            org_b = self.orgs[t.org]
            if not org_a.alive or not org_b.alive:
                return "ล้มเหลว", "สำนักล่มสลายไปแล้ว สงครามจึงไม่เกิด", d
                
            # รวมพลังหมาหมู่ — เฉพาะคนที่ **อยู่ในโลกและออกมาสู้ได้จริง**
            # ไม่นับคนที่ถูกขังอยู่ในคุกหรือปิดด่านอยู่ในแดนลับของตัวเอง สองพวกนี้ไม่ได้อยู่
            # ในแนวรบ และก่อนหน้านี้พวกเขาถูกนับเป็นกำลังพลและ **ตายในสงครามทั้งที่อยู่ในคุก**
            # (เจอตอนเทสต์การพ้นโทษพัง: นักโทษตายคาคุกด้วยสาเหตุ "สงครามสำนัก")
            def _in_the_field(c):
                return (c.alive and c.world_id == w.wid and not getattr(c, "hidden", False)
                        and getattr(c, "jail_until", 0) <= self.day)
            a_members = [self.cast[c] for c in org_a.members if _in_the_field(self.cast[c])]
            b_members = [self.cast[c] for c in org_b.members if _in_the_field(self.cast[c])]
            
            if not a_members or not b_members:
                return "ไร้กำลัง", "มีสำนักที่ไม่มีกำลังคนในโลกนี้เลย", d
                
            power_a = sum(R.power(m, w, self.items) for m in a_members)
            power_b = sum(R.power(m, w, self.items) for m in b_members)
            
            # กฎกำลังสองของแลนเชสเตอร์ (ดู tiandao/physics.py) — ของเดิมตัดสินด้วย
            # `power_a >= power_b` แล้วให้ฝ่ายแพ้ตาย 30% ต่อคน ส่วนฝ่ายชนะ **ไม่เสียใครเลย**
            # แปลว่าสงคราม 100 ต่อ 99 จบเหมือน 100 ต่อ 1 เป๊ะ ทั้งที่อย่างแรกควรเป็นชัยชนะ
            # ที่เลือดอาบจนแทบไม่เหลือสำนัก กฎกำลังสองให้ความต่างนั้นมาเอง และเลข 30%
            # ที่ตั้งเอาเองก็ไม่ต้องมีอีกต่อไป — อัตราตายของทั้งสองฝ่ายมาจากสมการเดียวกัน
            side, left_frac = PHYS.lanchester(power_a, power_b)
            win_org, lose_org = (org_a, org_b) if side >= 0 else (org_b, org_a)
            win_mems, lose_mems = (a_members, b_members) if side >= 0 else (b_members, a_members)
            win_loss_rate = 1.0 - left_frac          # ชนะฉิวเฉียด = เสียคนเกือบหมด
            d["ชัยชนะแบบไหน"] = (f"เหลือกำลัง {left_frac:.0%} จากที่ยกมา — "
                                 + ("ชนะแบบเลือดอาบ" if left_frac < 0.4 else
                                    "ชนะแบบบอบช้ำ" if left_frac < 0.75 else "ชนะแบบแทบไม่เสียใคร"))

            # คนแพ้โดนปล้นและอาจตาย
            loot_money = 0
            casualties = 0
            own_dead = 0
            for m in lose_mems:
                m_money = m.money.get(w.tier, 0)
                loot = int(m_money * 0.5)
                WAGES.set_gold(self, m, w.tier, m_money - loot, "war_loot_taken")
                loot_money += loot

                # ฝ่ายแพ้ถูกตีแตก — อัตราตายมาจาก C.WAR_ROUT_RATE ไม่ใช่เลขที่ตั้งเอาเอง
                if rng.random() < C.WAR_ROUT_RATE:
                    if m.fate > 0:
                        m.fate -= 1
                    else:
                        self.kill(m, "สงครามสำนัก", killer=win_mems[0])
                        m.place = None
                        m.org = None
                        casualties += 1
            # ฝ่ายชนะก็เสียคนตามสัดส่วนที่สมการบอก — นี่คือสิ่งที่ของเดิมไม่มีเลย
            for m in list(win_mems):
                if rng.random() < win_loss_rate:
                    if m.fate > 0:
                        m.fate -= 1
                    else:
                        self.kill(m, "สงครามสำนัก", killer=lose_mems[0])
                        m.place = None
                        own_dead += 1
            d["ผู้เสียชีวิตฝ่ายชนะ"] = own_dead
                        
            # ผู้รอดชีวิตจากสำนักที่แพ้กลายเป็นผู้พเนจร, สำนักล่มสลาย
            lose_org.alive = False
            for c in self.living():
                if c.org == lose_org.oid:
                    c.org = None
                    c.origin = "ผู้พเนจร"
                    
            # แบ่งของให้ผู้ชนะ
            if loot_money > 0 and win_mems:
                share = loot_money // len(win_mems)
                for m in win_mems:
                    WAGES.set_gold(self, m, w.tier, m.money.get(w.tier, 0) + share, "war_loot_shared")
                    
            d["ผู้ชนะ"] = win_org.name
            d["ผู้แพ้"] = lose_org.name
            d["พลังรวมชนะ"] = int(max(power_a, power_b))
            d["พลังรวมแพ้"] = int(min(power_a, power_b))
            d["ผู้เสียชีวิต"] = casualties
            d["เงินปล้น"] = loot_money
            
            if lose_org.oid in win_org.grudges: del win_org.grudges[lose_org.oid]
            if win_org.oid in lose_org.grudges: del lose_org.grudges[win_org.oid]
            
            return "จบสิ้น", f"สงครามแตกหัก! {win_org.name} กวาดล้าง {lose_org.name} จนล่มสลาย", d


        # ประลอง / ล้างแค้น
        # การประลองที่ "ไม่มีเรื่องบาดหมางกันมาก่อน" คือการวัดฝีมือ ไม่ใช่การฆ่ากัน — ยุทธภพ
        # แพ้แล้วยอม แล้วเก็บไปฝึกต่อ วัดจริงก่อนแก้: ประลอง 2,419 ครั้ง ตาย 303 ศพ (12.5%)
        # และผู้แพ้ได้ความแค้นติดตัวไปทุกครั้ง ซึ่งย้อนกลับมาเป็นล้างแค้น 4,144 ครั้ง — วงจร
        # ที่ทำให้คนแปลกหน้าสองคนซ้อมมือกันแล้วจบด้วยศพและการล้างแค้นข้ามรุ่น
        grudge = a.rivals.get(t.cid, 0) + t.rivals.get(a.cid, 0)
        friendly = (k == "ประลอง" and grudge == 0)
        mult = (C.DUEL_FRIENDLY_LETHAL_MULT if friendly
                else C.DUEL_LETHAL_MULT if k == "ประลอง" else 1.0)
        win, lose, margin, res = R.fight(self, w, a, t, rng, lethal_at=C.DEATH_MARGIN * mult,
                                         lethal=(k != "ประลอง"))
        if k == "ล้างแค้น" and win is a:
            R.settle_debt(a, t.cid)
        dmg = 2 if k == "ล้างแค้น" else 1
        if win.ascends > 0 and lose.ascends == 0 and k in ("ชิงสมบัติ", "ล้างแค้น", "ประลอง"):
            dmg *= 2
            d["อคติ"] = f"{lose.name} เกลียดพวกหน้าใหม่ที่กำเริบเสิบสาน"
        if friendly and res in ("พ่ายแพ้", "รอดตายด้วยชะตา") and margin < C.DUEL_SHAME_MARGIN:
            # แพ้อย่างสมศักดิ์ศรี: ได้ความเข้าใจจากการปะมือกับคนที่เหนือกว่า และเกิดความนับถือกัน
            lose.insight += C.DUEL_LESSON_INSIGHT
            win.merit = getattr(win, "merit", 0.0) + 1.0
            lose.bonds[win.cid] = lose.bonds.get(win.cid, 0) + 1
            win.bonds[lose.cid] = win.bonds.get(lose.cid, 0) + 1
            d["สิ่งที่ผู้แพ้ได้"] = "ความเข้าใจจากการปะมือ และความนับถือต่อผู้ชนะ"
            return res, f"{a.name}ประลองกับ{t.name} — {lose.name}ยอมแพ้อย่างสมศักดิ์ศรี", d
        lose.rivals[win.cid] = lose.rivals.get(win.cid, 0) + dmg
        d["ผล"] = f"{win.name}({win.realm_name()}) เหนือกว่า {lose.name}({lose.realm_name()})"
        d["margin"] = round(margin, 3)
        d["winner"] = win.cid
        verb = {"ตาย": f"{lose.name}ดับดิ้น", "รอดตายด้วยชะตา": f"{lose.name}รอดด้วยชะตา",
                "พ่ายแพ้": f"{lose.name}เป็นฝ่ายพ่าย"}.get(res, f"{lose.name}{res}")
        return res, f"{a.name}{k}กับ{t.name} — {verb}", d
