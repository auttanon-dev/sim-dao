import re

with open('tiandao/sim.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update Sect Facilities in the 30-day loop
old_disaster = '''                # Sect Resource Distribution
                for org in self.orgs:
                    if org.alive and org.members:'''
                    
new_disaster = '''                # Sect Resource Distribution & Facilities
                for org in self.orgs:
                    if org.alive and org.members:
                        # Assign Facilities
                        if not hasattr(org, "facilities"): org.facilities = {}
                        if "หอโอสถ" not in org.facilities or org.facilities["หอโอสถ"] not in self.cast or not self.cast[org.facilities["หอโอสถ"]].alive:
                            alchs = [c for c in org.members if c in self.cast and self.cast[c].alive and getattr(self.cast[c], "alch_rank", 0) > 0]
                            if alchs: org.facilities["หอโอสถ"] = max(alchs, key=lambda c: getattr(self.cast[c], "alch_rank", 0))
                        
                        if "หอศาสตรา" not in org.facilities or org.facilities["หอศาสตรา"] not in self.cast or not self.cast[org.facilities["หอศาสตรา"]].alive:
                            smiths = [c for c in org.members if c in self.cast and self.cast[c].alive and getattr(self.cast[c], "forge_rank", 0) > 0]
                            if smiths: org.facilities["หอศาสตรา"] = max(smiths, key=lambda c: getattr(self.cast[c], "forge_rank", 0))
                        
                        if "ลานฝึกยุทธ" not in org.facilities or org.facilities["ลานฝึกยุทธ"] not in self.cast or not self.cast[org.facilities["ลานฝึกยุทธ"]].alive:
                            fighters = [c for c in org.members if c in self.cast and self.cast[c].alive and self.cast[c].realm >= 4]
                            if fighters: org.facilities["ลานฝึกยุทธ"] = max(fighters, key=lambda c: self.cast[c].realm)
                        '''
content = content.replace(old_disaster, new_disaster)

# 2. Add Facility Healing in the daily routine
# Look for: if ch.energy <= 30:
old_routine = '''            # Energy consumption and state
            if ch.energy <= 30:'''

new_routine = '''            # Energy consumption and state
            
            # Sect Facility: หอโอสถ Healing
            if getattr(ch, "hp", 100) < getattr(ch, "max_hp", 100) and getattr(ch, "org", None) is not None and ch.org < len(self.orgs):
                org = self.orgs[ch.org]
                if hasattr(org, "facilities") and "หอโอสถ" in org.facilities:
                    master_cid = org.facilities["หอโอสถ"]
                    if master_cid in self.cast and self.cast[master_cid].alive:
                        master = self.cast[master_cid]
                        ch.hp = getattr(ch, "max_hp", 100)
                        # Add to debts/relations to show gratitude
                        ch.debts.append({"target": master_cid, "amount": 1, "done": False, "reason": "รักษาบาดแผลที่หอโอสถ"})
            
            if ch.energy <= 30:'''
content = content.replace(old_routine, new_routine)

with open('tiandao/sim.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("sim.py updated with Sect Facilities!")
