import re

with open('tiandao/sim.py', 'r', encoding='utf-8') as f:
    content = f.read()

disaster_logic = '''
            if self.day > getattr(self, "last_disaster_day", 0) + 30:
                self.last_disaster_day = self.day
                for w in self.worlds:
                    w.disaster_timer = getattr(w, "disaster_timer", 0) + 1
                    import random
                    w.current_disaster = random.choice(["ปกติ", "กบฏราชสำนัก", "โรคระบาดใหญ่", "สมบัติโบราณปรากฏ"])
                    if w.current_disaster == "กบฏราชสำนัก":
                        print(f"🚨💥 [ภัยพิบัติแผ่นดิน] {w.name} เกิดกบฏราชสำนัก!")
                    elif w.current_disaster == "โรคระบาดใหญ่":
                        print(f"🚨🦠 [ภัยพิบัติแผ่นดิน] {w.name} เกิดโรคระบาด!")
                    elif w.current_disaster == "สมบัติโบราณปรากฏ":
                        print(f"🚨📜 [ภัยพิบัติแผ่นดิน] {w.name} สมบัติปรากฏ!")
'''

pattern = re.compile(r'            self\.day = max\(self\.day, day\)')
def replacer(match):
    return '            self.day = max(self.day, day)\n' + disaster_logic

new_content = pattern.sub(replacer, content)
with open('tiandao/sim.py', 'w', encoding='utf-8') as f:
    f.write(new_content)
print("sim.py updated with Disaster Timer in step().")
