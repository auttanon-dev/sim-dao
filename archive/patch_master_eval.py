import re

with open('tiandao/sim.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace the block where res == True is processed or right after attempt_break.
old_attempt_break = '''            res, txt = R.attempt_break(self, a, w, rng, pills=use)
            if res == "ยังไม่ถึง":
                R.cultivate(a, gap)
                return "สะสมต่อ", f"{a.name}รู้ว่ายังไม่ถึงเวลา จึงบำเพ็ญต่อ", d'''

new_attempt_break = '''            res, txt = R.attempt_break(self, a, w, rng, pills=use)
            if res == "ยังไม่ถึง":
                R.cultivate(a, gap)
                return "สะสมต่อ", f"{a.name}รู้ว่ายังไม่ถึงเวลา จึงบำเพ็ญต่อ", d
                
            if res is True:
                # evaluate_master_relationship
                if a.master_cid != -1 and a.master_cid in self.cast:
                    master = self.cast[a.master_cid]
                    if master.alive and a.realm > master.realm:
                        loyalty = getattr(a, "loyalty", 50)
                        ambition = getattr(a, "ambition", 50)
                        rebellion_score = ambition - loyalty
                        
                        if rebellion_score > 30:
                            # Betray Master
                            txt += f"\\n -> [เนรคุณ] {a.name} ลุ่มหลงอำนาจ สังหารอาจารย์ {master.name} เพื่อชิงตำแหน่ง!"
                            self.kill(master, f"ถูกศิษย์ทรยศ {a.name} สังหารเพื่อชิงอำนาจ")
                            a.master_cid = -1
                            if a.cid in master.disciples: master.disciples.remove(a.cid)
                        elif ambition > 60 and loyalty >= 50:
                            # Peaceful Departure
                            txt += f"\\n -> [แยกตัว] {a.name} คารวะอาจารย์และขอแยกตัวไปตั้งสาขาใหม่ด้วยดี"
                            a.master_cid = -1
                            if a.cid in master.disciples: master.disciples.remove(a.cid)
                        else:
                            # Stay Loyal
                            txt += f"\\n -> [กตัญญู] แม้พลังสูงส่ง {a.name} ยังเคารพ {master.name} และยอมให้เป็นผู้อาวุโสสูงสุด"
                            master.is_loner = True # Force master to retire
'''

content = content.replace(old_attempt_break, new_attempt_break)

with open('tiandao/sim.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("sim.py updated with evaluate_master_relationship logic!")
