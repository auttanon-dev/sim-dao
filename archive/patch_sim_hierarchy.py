import re

with open('tiandao/sim.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update Sect Distribution in the 30-day loop
# The 30-day loop is at if self.day > getattr(self, "last_disaster_day", 0) + 30:
old_disaster = '''            if self.day > getattr(self, "last_disaster_day", 0) + 30:
                self.last_disaster_day = self.day
                for w in self.worlds:'''
                
new_disaster = '''            if self.day > getattr(self, "last_disaster_day", 0) + 30:
                self.last_disaster_day = self.day
                
                # Sect Resource Distribution
                for org in self.orgs:
                    if org.alive and org.members:
                        org.monthly_resource = getattr(org, "monthly_resource", 10000)
                        pool_c, pool_i, pool_o = org.monthly_resource * 0.4, org.monthly_resource * 0.4, org.monthly_resource * 0.2
                        if org.core_disciples:
                            share = int(pool_c / len(org.core_disciples))
                            for cid in org.core_disciples:
                                if cid in self.cast and self.cast[cid].alive: self.cast[cid].money[0] = self.cast[cid].money.get(0, 0) + share
                        if org.inner_disciples:
                            share = int(pool_i / len(org.inner_disciples))
                            for cid in org.inner_disciples:
                                if cid in self.cast and self.cast[cid].alive: self.cast[cid].money[0] = self.cast[cid].money.get(0, 0) + share
                        if org.outer_disciples:
                            share = int(pool_o / len(org.outer_disciples))
                            for cid in org.outer_disciples:
                                if cid in self.cast and self.cast[cid].alive: self.cast[cid].money[0] = self.cast[cid].money.get(0, 0) + share

                for w in self.worlds:'''
content = content.replace(old_disaster, new_disaster)

# 2. Assigning new members to Outer Disciple
# Search for .org = org_id and org.members.append(a.cid)
old_join = '''                    a.org = i
                    o.members.append(a.cid)
                    d["องค์กร"] = f"เข้าร่วม {o.name}"
                    return "เข้าองค์กร", f"{a.name}ได้รับเลือกเข้า {o.name}", d'''

new_join = '''                    a.org = i
                    o.members.append(a.cid)
                    a.sect_rank = "ศิษย์สายนอก"
                    if not hasattr(o, "outer_disciples"): o.outer_disciples = []
                    o.outer_disciples.append(a.cid)
                    d["องค์กร"] = f"เข้าร่วม {o.name}"
                    return "เข้าองค์กร", f"{a.name}ได้รับเลือกเข้าเป็นศิษย์สายนอกของ {o.name}", d'''
content = content.replace(old_join, new_join)

# 3. Add Rank Challenge Event logic inside resolve()
# Since we can't easily inject a new event into EVENT_TABLE without editing the massive config, 
# we can override an existing minor event, or add a chance for a character in a sect to do this *during* "ทำงาน" or something, 
# or inject it directly into the end of esolve() if they are in a sect.
# Actually, the user's snippet says "ท้าประลองแย่งตำแหน่ง".
# Let's add it to esolve when ev["kind"] == "สงครามสำนัก" but targeting their OWN sect members!
# Oh, that would be "ประลองภายใน". There is an event for it? Let's check Tiandao.
# If not, let's inject it into process_event where if the character is in a sect and ng.random() < 0.1, they challenge a higher rank instead of their normal action.

injection = '''
        # --- Sect Rank Challenge ---
        if getattr(actor, "org", None) is not None and actor.org < len(self.orgs) and rng.random() < 0.1:
            org = self.orgs[actor.org]
            rank = getattr(actor, "sect_rank", "ศิษย์สายนอก")
            target_list = []
            new_rank = ""
            if rank == "ศิษย์สายนอก" and getattr(org, "inner_disciples", []):
                target_list = org.inner_disciples
                new_rank = "ศิษย์สายใน"
            elif rank == "ศิษย์สายใน" and getattr(org, "core_disciples", []):
                target_list = org.core_disciples
                new_rank = "ศิษย์สืบทอด"
                
            if target_list:
                target_cid = rng.choice(target_list)
                if target_cid in self.cast and self.cast[target_cid].alive:
                    target_ch = self.cast[target_cid]
                    win, lose, log, escaped = combat.resolve_combat(actor, target_ch, world, self)
                    if win.cid == actor.cid:
                        # Swap ranks
                        actor.sect_rank = new_rank
                        target_ch.sect_rank = rank
                        if rank == "ศิษย์สายนอก": 
                            if actor.cid in org.outer_disciples: org.outer_disciples.remove(actor.cid)
                            org.inner_disciples.append(actor.cid)
                            if target_ch.cid in org.inner_disciples: org.inner_disciples.remove(target_ch.cid)
                            org.outer_disciples.append(target_ch.cid)
                        elif rank == "ศิษย์สายใน":
                            if actor.cid in org.inner_disciples: org.inner_disciples.remove(actor.cid)
                            org.core_disciples.append(actor.cid)
                            if target_ch.cid in org.core_disciples: org.core_disciples.remove(target_ch.cid)
                            org.inner_disciples.append(target_ch.cid)
                        
                        return self.emit(world, "เลื่อนขั้นสำนัก", actor, target_ch, ["ชื่อเสียง"], "ชนะประลอง", f"[{actor.name}] โค่น [{target_ch.name}] แย่งตำแหน่ง {new_rank} สำเร็จ!", elapsed, {})
                    else:
                        return self.emit(world, "เลื่อนขั้นสำนัก", actor, target_ch, ["ชื่อเสียง"], "แพ้ประลอง", f"[{actor.name}] ท้าประลองแย่งตำแหน่ง {new_rank} แต่พ่ายแพ้ต่อ [{target_ch.name}]", elapsed, {})
'''

# Find def step() and inject at the very top of def step(self): ... wait, esolve is better.
# Let's inject it into def step(self): right after gap = rng.randint(*ev["gap"])
# or right before gap = rng.randint.
old_gap = '''        gap = rng.randint(*ev["gap"])'''
content = content.replace(old_gap, injection + "\n" + old_gap)

with open('tiandao/sim.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("sim.py updated with Sect Hierarchy mechanics!")
