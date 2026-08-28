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
                    
                    if rng.randint(1, 100) > safety:
                        sub = rng.choice(["robbery", "assassin", "brawl"])
                        if sub == "robbery":
                            a.hp -= 25
                            a.money[w.wid] = max(0, a.money.get(w.wid, 0) - 80)
                            msg = "⚠️ [เหตุการณ์อันตราย] เจอโจรป่าถือมีดดาบพุ่งเข้ามาดักปล้น! ท่านพยายามต่อสู้แต่พลาดท่า เสีย -25 HP เงินหาย"
                        elif sub == "assassin":
                            a.hp -= 40
                            msg = "⚠️ [เหตุการณ์อันตราย] นักฆ่าลึกลับหน้ากากเหล็กซุ่มโจมตีจากบนหลังคา! ท่านหลบไม่พ้น เสีย -40 HP"
                        elif sub == "brawl":
                            a.hp -= 15
                            msg = "⚠️ [เหตุการณ์อันตราย] เกิดเหตุชาวยุทธตะลุมบอนกันกลางตลาด ท่านโดนลูกหลงอาวุธซัด เสีย -15 HP"
                            
                        if a.hp <= 0:
                            self.kill(a, "ลมปราณแตกซ่านสิ้นชีพในเมือง")
                            msg += " (และดับสูญ)"
                            
                        return "อันตราย", msg, d
                        
                    if rng.randint(1, 100) <= jianghu:
                        sub = rng.choice(["gamble", "master", "reward_duel"])
                        if sub == "gamble":
                            if rng.random() > 0.5:
                                a.money[w.wid] = a.money.get(w.wid, 0) + 150
                                msg = "⚔️ [เหตุการณ์ยุทธภพ] พบวงไฮโลของเหล่าจอมยุทธ ท่านเสี่ยงโชคและชนะ ได้เงิน +150"
                            else:
                                a.money[w.wid] = max(0, a.money.get(w.wid, 0) - 100)
                                msg = "⚔️ [เหตุการณ์ยุทธภพ] พบวงไฮโลของเหล่าจอมยุทธ ท่านเสี่ยงโชคแต่พ่ายแพ้ เสียเงิน -100"
                        elif sub == "master":
                            a.hp = min(a.max_hp, a.hp + 35)
                            msg = "⚔️ [เหตุการณ์ยุทธภพ] เจอปรมาจารย์ขี้เมาเร้นกาย ท่านถูกใจอัธยาศัยจึงมอบโอสถทิพย์ ฟื้นฟู +35 HP"
                        elif sub == "reward_duel":
                            a.hp -= 20
                            a.money[w.wid] = a.money.get(w.wid, 0) + 200
                            msg = "⚔️ [เหตุการณ์ยุทธภพ] ท่านขึ้นเวทีประลองยุทธชิงเงินรางวัล ขับเคี่ยวชนะมาได้ เสีย -20 HP ได้ +200 เงิน"
                            if a.hp <= 0:
                                self.kill(a, "ตายในการประลองเมือง")
                                msg += " (และดับสูญคาสนามประลอง)"
                        
                        return "วิถียุทธ", msg, d

                    if rng.randint(1, 100) <= wealth:
                        sub = rng.choice(["shop_herb", "forced_auction", "job"])
                        if sub == "shop_herb":
                            if a.money.get(w.wid, 0) >= 60:
                                a.money[w.wid] -= 60
                                a.hp = min(a.max_hp, a.hp + 25)
                                msg = "🛍️ [เหตุการณ์การค้า] พ่อค้าเร่ขาย 'บัวหิมะพันปี' ท่านจ่าย 60 เพื่อฟื้นฟู +25 HP"
                            else:
                                msg = "💸 [เหตุการณ์การค้า] พ่อค้าเร่ขาย 'บัวหิมะพันปี' แต่เงินท่านไม่พอ ปล่อยโอกาสหลุดมือ"
                        elif sub == "forced_auction":
                            a.money[w.wid] = max(0, a.money.get(w.wid, 0) - 40)
                            msg = "🛍️ [เหตุการณ์การค้า] โรงประมูลบังคับจ่ายค่าธรรมเนียมเข้าชมของวิเศษ ท่านเสีย -40 เงิน"
                        elif sub == "job":
                            a.money[w.wid] = a.money.get(w.wid, 0) + 90
                            msg = "🛍️ [เหตุการณ์การค้า] คหบดีใหญ่จ้างท่านเป็นผู้คุ้มกันจวนชั่วคราว ได้ค่าตอบแทน +90 เงิน"
                            
                        return "การค้า", msg, d
                        
                    # ทั่วไป
                    if faction == "Imperial":
                        a.hp = min(a.max_hp, a.hp + 10)
                        msg = "🏛️ [เหตุการณ์ความสงบ] กองทหารหลวงลาดตระเวนเข้มงวด ท่านพักผ่อนสบาย ฟื้นฟู +10 HP"
                    elif faction == "Orthodox":
                        msg = "🕊️ [เหตุการณ์ความสงบ] บรรยากาศร่มเย็น ศิษย์ฝั่งธรรมะคอยช่วยเหลือชาวบ้านที่เดือดร้อน"
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
    print("Regex failed to match! Wait, maybe the regex is wrong.")
