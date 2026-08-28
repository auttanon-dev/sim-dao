# -*- coding: utf-8 -*-
with open('tiandao/combat.py', 'r', encoding='utf-8') as f:
    content = f.read()

old_start = '''    # Start combat logging
    log = []'''
new_start = '''    # Start combat logging
    log = []
    
    # ------------------------------------------------
    # Formation Activation (กางค่ายกล)
    # ------------------------------------------------
    for fighter in [attacker, target]:
        # Simple simulation of having a flag
        if getattr(fighter, "active_formation", "") == "" and getattr(fighter, "current_mp", 0) >= 50:
            if sim.rng.random() < 0.2: # 20% chance they bought or crafted a flag
                formations = [
                    ("ค่ายกลเพลิงผลาญวิญญาณ", "DPS"),
                    ("ค่ายกลดินเหนี่ยวรั้ง", "CC"),
                    ("ค่ายกลรวมปราณฟ้าดิน", "Buff"),
                    ("ค่ายกลม่านกลืนแสง", "Stealth")
                ]
                chosen = sim.rng.choice(formations)
                fighter.active_formation = chosen[0]
                fighter.formation_type = chosen[1] # Store type temporarily for combat
                fighter.formation_duration = 3
                fighter.current_mp -= 50
                log.append(f"🏴 [{fighter.name}] ผลาญพลังปราณ 50 หน่วย กาง <{fighter.active_formation}>! (ชนิด: {fighter.formation_type})")
'''
content = content.replace(old_start, new_start)

old_turn = '''    for turn in range(1, 11):'''
new_turn = '''    for turn in range(1, 11):
        # ------------------------------------------------
        # Formation Turn Effects
        # ------------------------------------------------
        for fighter, enemy in [(attacker, target), (target, attacker)]:
            if getattr(fighter, "formation_duration", 0) > 0:
                ftype = getattr(fighter, "formation_type", "")
                if ftype == "DPS":
                    dmg = 20 * (fighter.realm + 1)
                    enemy.hp -= dmg
                    log.append(f"   🔥 <ค่ายกล> แผดเผา [{enemy.name}] ได้รับความเสียหาย {dmg}!")
                elif ftype == "Buff":
                    fighter.hp = min(getattr(fighter, "max_hp", 100), fighter.hp + 20)
                    fighter.current_mp = min(getattr(fighter, "max_mp", 100), fighter.current_mp + 20)
                    log.append(f"   ✨ <ค่ายกล> ฟื้นฟู HP/MP ให้ [{fighter.name}]!")
                fighter.formation_duration -= 1
                if fighter.formation_duration == 0:
                    fighter.active_formation = ""
                    log.append(f"   ⚠️ ค่ายกลของ [{fighter.name}] พลังงานหมดลงและสลายไป")
'''
content = content.replace(old_turn, new_turn)

old_dmg = '''        # --- Calculate Damage ---
        base_dmg_a = attacker.realm * 10
        base_dmg_t = target.realm * 10'''
new_dmg = '''        # --- Calculate Damage ---
        base_dmg_a = attacker.realm * 10
        base_dmg_t = target.realm * 10
        
        # Formation CC (Realm Suppression)
        if getattr(attacker, "formation_duration", 0) > 0 and getattr(attacker, "formation_type", "") == "CC":
            base_dmg_t *= 0.5
            log.append(f"   ⛰️ <ค่ายกลดิน> กดทับพลังของ [{target.name}] พลังโจมตีลดลงครึ่งหนึ่ง!")
        if getattr(target, "formation_duration", 0) > 0 and getattr(target, "formation_type", "") == "CC":
            base_dmg_a *= 0.5
            log.append(f"   ⛰️ <ค่ายกลดิน> กดทับพลังของ [{attacker.name}] พลังโจมตีลดลงครึ่งหนึ่ง!")
            
        # Formation Stealth (Miss Chance)
        miss_a = False
        miss_t = False
        if getattr(attacker, "formation_duration", 0) > 0 and getattr(attacker, "formation_type", "") == "Stealth":
            if sim.rng.random() < 0.5:
                miss_t = True
                log.append(f"   🌫️ <ค่ายกลม่าน> ทำให้การโจมตีของ [{target.name}] พลาดเป้า!")
        if getattr(target, "formation_duration", 0) > 0 and getattr(target, "formation_type", "") == "Stealth":
            if sim.rng.random() < 0.5:
                miss_a = True
                log.append(f"   🌫️ <ค่ายกลม่าน> ทำให้การโจมตีของ [{attacker.name}] พลาดเป้า!")
'''
content = content.replace(old_dmg, new_dmg)

old_apply = '''        # --- Apply Damage ---
        target.hp -= final_dmg_a
        attacker.hp -= final_dmg_t'''
new_apply = '''        # --- Apply Damage ---
        if not miss_a:
            target.hp -= final_dmg_a
        if not miss_t:
            attacker.hp -= final_dmg_t'''
content = content.replace(old_apply, new_apply)

with open('tiandao/combat.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("combat.py updated with Formations!")
