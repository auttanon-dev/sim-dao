# -*- coding: utf-8 -*-
with open('tiandao/sim.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Divine Spirits & Beast Forest Farming in Routine Loop
old_routine = '''            # Energy consumption and state'''
new_routine = '''            # ------------------------------------------------
            # Beast Forest Farming (ป่าหมื่นอสูร)
            # ------------------------------------------------
            if ch.energy > 50 and getattr(ch, "is_beast", False) == False and getattr(ch, "is_demon", False) == False and getattr(ch, "is_spirit", False) == False:
                if self.rng.random() < 0.1: # 10% chance to farm
                    ch.energy -= 40
                    if self.rng.random() < 0.15: # 15% chance to encounter beast
                        # Spawn wild beast
                        beast = self.spawn(self.worlds[0])
                        beast.name = "สัตว์อสูรป่า"
                        beast.is_beast = True
                        beast.realm = max(1, ch.realm + self.rng.randint(-1, 1))
                        print(f"\\n🐾 [ป่าหมื่นอสูร] [{ch.name}] ออกล่าสัตว์อสูรและปะทะกับ [{beast.name}] ขั้น {beast.realm}!")
                        # We don't trigger combat.resolve directly here to avoid circular imports / missing world refs if not careful,
                        # but we can just use the event emitter or resolve it simply:
                        import tiandao.combat as combat
                        combat.resolve_combat(ch, beast, self.worlds[0], self)
                    else:
                        ch.insight += 10
                        # gain some items or spirit stones
                        print(f"\\n🌲 [ป่าหมื่นอสูร] [{ch.name}] ล่าสัตว์อสูรสำเร็จ ได้รับศิลาปราณและค่าความเข้าใจ!")
            
            # Energy consumption and state'''
content = content.replace(old_routine, new_routine)

# 2. Divine Spirits Hunting Demons
old_disaster = '''                # Demon Temptation (Possession)'''
new_disaster = '''                # ------------------------------------------------
                # Divine Spirits Hunting Demons
                # ------------------------------------------------
                spirits = [c for c in self.cast.values() if c.alive and getattr(c, "is_spirit", False)]
                demons = [c for c in self.cast.values() if c.alive and getattr(c, "is_demon", False)]
                if spirits and demons:
                    if self.rng.random() < 0.3: # 30% chance for a holy crusade
                        hunter = self.rng.choice(spirits)
                        target = self.rng.choice(demons)
                        print(f"\\n⚔️ [บัญชาสวรรค์] เผ่าวิญญาณศักดิ์สิทธิ์ [{hunter.name}] บุกสังหารมารร้าย [{target.name}] เพื่อรักษาสมดุลโลก!")
                        import tiandao.combat as combat
                        combat.resolve_combat(hunter, target, self.worlds[0], self)
                
                # Demon Temptation (Possession)'''
content = content.replace(old_disaster, new_disaster)

with open('tiandao/sim.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("sim.py updated with Beast Farming and Divine Spirits Hunting!")
