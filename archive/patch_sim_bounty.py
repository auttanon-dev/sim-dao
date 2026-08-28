# -*- coding: utf-8 -*-
with open('tiandao/sim.py', 'r', encoding='utf-8') as f:
    content = f.read()

old_init = '''        self.log = []'''
new_init = '''        self.log = []
        self.bounties = {} # cid -> reward amount'''
content = content.replace(old_init, new_init)

old_loop = '''            # ------------------------------------------------
            # Grand Auction (งานประมูลใหญ่ระดับทวีป) Every 365 Days
            # ------------------------------------------------'''
new_loop = '''            # ------------------------------------------------
            # Bounty Board (ป้ายประกาศจับ)
            # ------------------------------------------------
            if self.day % 10 == 0:
                # 1. Update Board
                for ch in self.cast.values():
                    if ch.alive:
                        if getattr(ch, "is_demon", False) or getattr(ch, "karmic_debt", 0) > 2000:
                            if ch.cid not in self.bounties:
                                reward = ch.realm * 500
                                self.bounties[ch.cid] = reward
                                print(f"\\n📜 [ประกาศจับ] ราชสำนักตั้งค่าหัว [{ch.name}] ({'มารร้าย' if getattr(ch, 'is_demon', False) else 'จอมวายร้าย'}) เป็นเงิน {reward} ศิลาปราณ!")
                
                # 2. Hunters Check Board
                hunters = [c for c in self.cast.values() if c.alive and c.cid not in self.bounties and (getattr(c, "is_loner", False) or getattr(c, "profession", "") == "ผู้พเนจร")]
                for hunter in hunters:
                    if self.bounties and self.rng.random() < 0.2: # 20% chance to hunt
                        target_cid = self.rng.choice(list(self.bounties.keys()))
                        if target_cid in self.cast and self.cast[target_cid].alive:
                            target = self.cast[target_cid]
                            print(f"\\n🦅 [นักล่าค่าหัว] [{hunter.name}] รับป้ายประกาศจับ ออกตามล่า [{target.name}]!")
                            import tiandao.combat as combat
                            result = combat.resolve_combat(hunter, target, self.worlds[0], self)
                            if not target.alive:
                                reward = self.bounties.pop(target_cid, 0)
                                hunter.spirit_stones = getattr(hunter, "spirit_stones", 0) + reward
                                print(f" -> 💰 [{hunter.name}] ขึ้นเงินรางวัลสำเร็จ! ได้รับ {reward} ศิลาปราณ")
                        else:
                            # Target already dead
                            self.bounties.pop(target_cid, None)

            # ------------------------------------------------
            # Grand Auction (งานประมูลใหญ่ระดับทวีป) Every 365 Days
            # ------------------------------------------------'''
content = content.replace(old_loop, new_loop)

with open('tiandao/sim.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("sim.py updated with Bounty Board!")
