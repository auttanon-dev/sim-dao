import re

with open('tiandao/sim.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update the Emperor Initialization
old_emperor = '''                    if "เมืองหลวง" in c_type:
                        strictness = 90
                        title = "ท่านอ๋อง"
                        ruler_name = "จูหยวน"'''
                        
new_emperor = '''                    if "เมืองหลวง" in c_type:
                        strictness = 90
                        title = "ฮ่องเต้"
                        ruler_name = "หมิงหยวนตี้"'''
content = content.replace(old_emperor, new_emperor)

old_ruler_spawn = '''                    ruler.city_id = c["id"]
                    ruler.is_loner = True # Don't wander taking disciples
                    ruler.energy = 100
                    c["ruler_cid"] = ruler.cid'''
                    
new_ruler_spawn = '''                    ruler.city_id = c["id"]
                    ruler.is_loner = True # Don't wander taking disciples
                    ruler.energy = 100
                    if title == "ฮ่องเต้":
                        ruler.is_emperor = True
                        ruler.dragon_aura = True
                    c["ruler_cid"] = ruler.cid'''
content = content.replace(old_ruler_spawn, new_ruler_spawn)

# 2. Add Imperial Spy Event in 30-day loop
old_spy = '''                for w in self.worlds:'''
new_spy = '''                # Imperial Spy Network
                if len(self.orgs) > 0:
                    target_sect = self.rng.choice(self.orgs)
                    if target_sect.alive:
                        stealth_level = self.rng.randint(50, 100)
                        if stealth_level > getattr(target_sect, "alert_level", 50):
                            intel_gathered = self.rng.randint(10, 50)
                            target_sect.threat_level = getattr(target_sect, "threat_level", 0) + intel_gathered
                            # log silently or print (using print here for engine logs as requested by user)
                            print(f"\\n🕵️‍♂️ [องครักษ์เสื้อแพร] แทรกซึมสำเร็จ! พบว่า {target_sect.name} ซ่องสุมกำลัง (ภัยคุกคาม: {target_sect.threat_level}/100)")
                        else:
                            print(f"\\n🔴 [องครักษ์เสื้อแพร] ความแตก! สายลับถูกจับกุมและสังหารโดย {target_sect.name}")
                            
                for w in self.worlds:'''
content = content.replace(old_spy, new_spy)

with open('tiandao/sim.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("sim.py updated with Imperial Spies and Emperor Initialization!")
