import re

with open('tiandao/sim.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Add import
if "from tiandao import combat" not in content:
    content = content.replace("from tiandao import story", "from tiandao import story\nfrom tiandao import combat")

# Replace "ล้างแค้น" logic
old_revenge = '''            if R.power(a, w) * 1.5 > R.power(t, w):
                self.kill(t, f"ถูกล้างแค้นโดย {a.name}")
                a.money[w.wid] = a.money.get(w.wid, 0) + rng.randint(50, 200)
                d["ผลลัพธ์"] = f"{t.name} ถูกทำลายจิตวิญญาณ"
                return "ล้างแค้น", f"{a.name}ล้างแค้น {t.name} สำเร็จ", d
            else:
                self.kill(a, f"ถูก {t.name} สังหารกลับ")
                return "ถูกฆ่ากลับ", f"{a.name}พลาดท่าถูก {t.name} สังหาร", d'''

new_revenge = '''            winner, loser, combat_log = combat.resolve_combat(a, t, w, self)
            self.kill(loser, f"ถูก {winner.name} สังหาร")
            if winner == a:
                a.money[w.wid] = a.money.get(w.wid, 0) + rng.randint(50, 200)
                d["ผลลัพธ์"] = combat_log
                return "ล้างแค้น", f"{a.name}ล้างแค้น {t.name} สำเร็จ", d
            else:
                d["ผลลัพธ์"] = combat_log
                return "ถูกฆ่ากลับ", f"{a.name}พลาดท่าถูก {t.name} สังหาร", d'''

content = content.replace(old_revenge, new_revenge)


# Replace duel logic
old_duel = '''                                if combat_power >= rival_power:
                                    a.insight += 2.0
                                    a.enemies_defeated = getattr(a, "enemies_defeated", 0) + 1
                                    self.kill(b, f"ถูก {a.name} สังหารในการดวลเดือด")
                                    del a.nemeses[b.name]
                                    msg += f" 💥 [{a.name}] พิชิตศัตรู!"
                                else:
                                    b.insight += 2.0
                                    b.enemies_defeated = getattr(b, "enemies_defeated", 0) + 1
                                    self.kill(a, f"ถูก {b.name} สังหารในการดวลเดือด")
                                    if a.name in b.nemeses: del b.nemeses[a.name]
                                    msg += f" 💥 [{a.name}] ถูกสังหารโดย [{b.name}]!"
                                return "ดวลเดือด", pre_msg + msg, d'''

new_duel = '''                                winner, loser, combat_log = combat.resolve_combat(a, b, w, self)
                                winner.insight += 2.0
                                winner.enemies_defeated = getattr(winner, "enemies_defeated", 0) + 1
                                self.kill(loser, f"ถูก {winner.name} สังหารในการดวลเดือด")
                                
                                if winner == a:
                                    if b.name in getattr(a, "nemeses", {}): del a.nemeses[b.name]
                                else:
                                    if a.name in getattr(b, "nemeses", {}): del b.nemeses[a.name]
                                    
                                msg += f"\\n{combat_log}"
                                return "ดวลเดือด", pre_msg + msg, d'''

content = content.replace(old_duel, new_duel)

# Replace Faction War logic (I injected it earlier, it might look slightly different)
old_faction = '''                                if combat_power >= rival_power:
                                    a.insight += 3.0
                                    self.kill(b, f"ตกตายในสงครามขั้วอำนาจด้วยเงื้อมมือของ {a.name}")
                                    msg += f" 💥 [{a.name}] จากฝ่ายธรรมะคว้าชัย!" if a.moral > 0 else f" 💥 [{a.name}] จากฝ่ายอธรรมพิชิตศัตรู!"
                                else:
                                    b.insight += 3.0
                                    self.kill(a, f"ตกตายในสงครามขั้วอำนาจด้วยเงื้อมมือของ {b.name}")
                                    msg += f" 💥 [{a.name}] พลาดท่าตายตก!"
                                return "สงครามขั้วอำนาจ", pre_msg + msg, d'''

new_faction = '''                                winner, loser, combat_log = combat.resolve_combat(a, b, w, self)
                                winner.insight += 3.0
                                self.kill(loser, f"ตกตายในสงครามขั้วอำนาจด้วยเงื้อมมือของ {winner.name}")
                                msg += f"\\n{combat_log}"
                                return "สงครามขั้วอำนาจ", pre_msg + msg, d'''
content = content.replace(old_faction, new_faction)

with open('tiandao/sim.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("sim.py updated with combat.py logic")
