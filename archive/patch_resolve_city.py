import re

with open('tiandao/sim.py', 'r', encoding='utf-8') as f:
    content = f.read()

new_resolutions = '''        if k == "เหตุการณ์เมือง":
            if a.city_id >= 0 and hasattr(C, "CITIES"):
                city = next((c for c in C.CITIES if c["id"] == a.city_id), None)
                if city:
                    safety = city["attributes"]["safety"]
                    jianghu = city["attributes"]["jianghu"]
                    wealth = city["attributes"]["wealth"]
                    info = city["attributes"]["info"]
                    faction = city["dominant_faction"]
                    
                    if rng.randint(1, 100) > safety:
                        danger_events = [
                            f"⚠️ [เหตุการณ์อันตราย] ระหว่างเดินในเมือง มีโจรป่าถือมีดดาบพุ่งเข้ามาดักปล้นเงิน!",
                            f"⚠️ [เหตุการณ์อันตราย] {a.name} ถูกนักฆ่าลึกลับหน้ากากเหล็กซุ่มโจมตีจากบนหลังคา!",
                            f"⚠️ [เหตุการณ์อันตราย] เกิดเหตุตะลุมบอนกลางตลาดระหว่างพรรคอธรรมและชาวบ้าน วิ่งหลบด่วน!"
                        ]
                        a.insight += 0.1
                        return "เผชิญภัย", rng.choice(danger_events), d
                        
                    if rng.randint(1, 100) <= jianghu:
                        jianghu_events = [
                            f"⚔️ [วิถียุทธ] พบศิษย์เอกของสำนักใหญ่กำลังตั้งเวทีประลองยุทธหาคู่ครอง",
                            f"⚔️ [วิถียุทธ] เจอปรมาจารย์เร้นกายกำลังเมามายอยู่ข้างทาง ได้รับการชี้แนะ",
                            f"⚔️ [วิถียุทธ] มีการท้าดวลกระบี่ระหว่างยอดฝีมือสองท่าน الشاวยุทธยืนมุงดูกันเต็มถนน"
                        ]
                        a.insight += rng.uniform(0.1, 0.5)
                        return "วิถียุทธ", rng.choice(jianghu_events), d

                    if rng.randint(1, 100) <= info:
                        info_events = [
                            f"📜 [เบาะแส] เสี่ยวเอ้อในโรงเตี๊ยมกระซิบระบุพิกัดที่ซ่อนของ 'คัมภีร์เปลี่ยนเส้นเอ็น'",
                            f"📜 [เบาะแส] ได้ยินชาวบ้านคุยกันว่า คืนนี้จะมีการลักลอบขนอาวุธเถื่อนที่ท่าเรือลับ",
                            f"📜 [เบาะแส] หอนางโลมเปิดเผยข้อมูลว่า มีสายลับของราชสำนักแฝงตัวอยู่ในเมืองนี้"
                        ]
                        return "ข่าวสาร", rng.choice(info_events), d

                    if rng.randint(1, 100) <= wealth:
                        wealth_events = [
                            f"💰 [การค้า] โรงประมูลประจำเมืองเปิดตัว 'ดาบฆ่ามังกร' อาวุธระดับตำนาน",
                            f"💰 [การค้า] พ่อค้าเร่จากแดนไกลนำ 'สมุนไพรเก้าตะวันพันปี' มาเสนอขายในราคาพิเศษ",
                            f"💰 [การค้า] คหบดีใจบุญประกาศแจกเงินตราและเสบียงให้แก่ผู้ที่ยอมช่วยงานคุ้มกันสินค้า"
                        ]
                        a.money[w.wid] = a.money.get(w.wid, 0) + rng.randint(10, 50)
                        return "โชคลาภ", rng.choice(wealth_events), d

                    if faction == "Imperial":
                        msg = "🏛️ [ความสงบ] ทหารยามเดินตรวจตราอย่างเข้มงวด เมืองสงบเรียบร้อยดี"
                    elif faction == "Orthodox":
                        msg = "🕊️ [ความสงบ] บรรยากาศร่มเย็น ศิษย์ฝั่งธรรมะคอยช่วยเหลือชาวบ้านที่เดือดร้อน"
                    else:
                        msg = "🍃 [ทั่วไป] บรรยากาศในเมืองเป็นไปอย่างราบเรียบ ไม่มีเหตุการณ์พิเศษเกิดขึ้น"
                    return "ทั่วไป", msg, d
            return "ทั่วไป", f"{a.name} เดินเล่นในเมือง", d
'''

pattern = re.compile(r'(    def resolve\(self, ev, a, t, w, gap, rng\):\n        k, d = ev\["kind"\], \{\})', re.DOTALL)

def replacer(match):
    return match.group(1) + "\n" + new_resolutions

new_content = pattern.sub(replacer, content)

with open('tiandao/sim.py', 'w', encoding='utf-8') as f:
    f.write(new_content)
print("sim.py updated resolve() with new city events.")
