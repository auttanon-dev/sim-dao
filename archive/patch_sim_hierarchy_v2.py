import re

with open('tiandao/sim.py', 'r', encoding='utf-8') as f:
    content = f.read()

old_disaster = '''            if self.day > getattr(self, "last_disaster_day", 0) + 30:
                self.last_disaster_day = self.day
                for w in self.worlds:'''
                
new_disaster = '''            if self.day > getattr(self, "last_disaster_day", 0) + 30:
                self.last_disaster_day = self.day
                
                # Sect Resource Distribution
                for org in self.orgs:
                    if org.alive and org.members:
                        org.monthly_resource = getattr(org, "monthly_resource", 10000)
                        pool_c = org.monthly_resource * 0.4
                        pool_i = org.monthly_resource * 0.4
                        pool_o = org.monthly_resource * 0.2
                        
                        cd = getattr(org, "core_disciples", [])
                        id_ = getattr(org, "inner_disciples", [])
                        od = getattr(org, "outer_disciples", [])
                        
                        if cd:
                            share = int(pool_c / len(cd))
                            for cid in cd:
                                if cid in self.cast and self.cast[cid].alive: self.cast[cid].money[0] = self.cast[cid].money.get(0, 0) + share
                        if id_:
                            share = int(pool_i / len(id_))
                            for cid in id_:
                                if cid in self.cast and self.cast[cid].alive: self.cast[cid].money[0] = self.cast[cid].money.get(0, 0) + share
                        if od:
                            share = int(pool_o / len(od))
                            for cid in od:
                                if cid in self.cast and self.cast[cid].alive: self.cast[cid].money[0] = self.cast[cid].money.get(0, 0) + share

                for w in self.worlds:'''
content = content.replace(old_disaster, new_disaster)

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
                    import tiandao.combat as combat
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

old_gap = '''        gap = rng.randint(*ev["gap"])'''
content = content.replace(old_gap, injection + "\\n" + old_gap)

with open('tiandao/sim.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("sim.py updated with Sect Hierarchy mechanics!")
