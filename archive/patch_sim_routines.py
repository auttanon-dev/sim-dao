import re

with open('tiandao/sim.py', 'r', encoding='utf-8') as f:
    content = f.read()

# I will inject Sect Economics and Daily Routine right into the step() loop!
# In step(), before returning None at the bottom of the loop or somewhere near the top of the event resolution.
# Let's find a good spot inside step().
# Right after we pop the character from queue and check if they are alive:
'''
            day, cid = heapq.heappop(self.queue)
            ch = self.cast[cid]
            if not ch.alive:
                continue
            self.day = max(self.day, day)
'''
# We will inject the routine logic there!

routine_injection = '''            # --- Routine & Energy System ---
            # Update MP limits
            ch.max_mp = max(100.0, float(ch.realm * 100))
            if getattr(ch, "current_mp", 0) < ch.max_mp:
                ch.current_mp = min(ch.max_mp, getattr(ch, "current_mp", 100.0) + (ch.max_mp * 0.1))
                
            time_of_day = self.day % 4
            
            # Energy consumption and state
            if ch.energy <= 30:
                ch.current_state = "Sleeping"
                ch.energy += 70
                # When sleeping, they don't do major events as often, push them back
                if rng.random() < 0.5:
                    heapq.heappush(self.queue, (self.day + 1, cid))
                    continue
            else:
                if time_of_day == 0:
                    ch.current_state = "Cultivating"
                    ch.energy -= 10
                elif time_of_day == 1:
                    ch.current_state = "Working" if rng.random() < 0.5 else "Relaxing"
                    if ch.current_state == "Working":
                        ch.energy -= 20
                        # Earn money based on realm
                        earned = rng.randint(10, 50) * max(1, ch.realm)
                        ch.money[self.world(ch.world_id).tier] = ch.money.get(self.world(ch.world_id).tier, 0.0) + earned
                        # Send cut to master
                        if ch.master_cid != -1 and ch.master_cid in self.cast:
                            master = self.cast[ch.master_cid]
                            if master.alive:
                                cut = int(earned * 0.6)
                                master.money[self.world(master.world_id).tier] = master.money.get(self.world(master.world_id).tier, 0.0) + cut
                                ch.money[self.world(ch.world_id).tier] -= cut
                    else:
                        ch.energy += 20
                elif time_of_day == 2:
                    ch.current_state = "Socializing"
                    ch.energy -= 10
                else:
                    ch.current_state = "Sleeping"
                    ch.energy += 50
                    
            # --- Master & Disciple System ---
            if ch.realm >= 7 and not ch.is_loner and rng.random() < 0.05:
                # Look for a disciple in the same world
                pool = [c for c in self.living_in(ch.world_id) if c.realm < 4 and c.master_cid == -1 and c.cid != ch.cid]
                if pool:
                    disciple = rng.choice(pool)
                    disciple.master_cid = ch.cid
                    ch.disciples.append(disciple.cid)
                    # print(f"[{ch.name}] รับ [{disciple.name}] เป็นศิษย์สายตรง!")
                    
            ch.energy = min(100.0, getattr(ch, "energy", 100.0))
            
'''

content = content.replace("            self.day = max(self.day, day)\n", "            self.day = max(self.day, day)\n" + routine_injection)

with open('tiandao/sim.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("sim.py updated with Routines and Sect Economics!")
