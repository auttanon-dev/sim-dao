# -*- coding: utf-8 -*-
with open('tiandao/combat.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Demon MP/HP drain and Beast Special Looting
old_combat = '''    # --- Calculate Damage ---'''
new_combat = '''    # --- Demon Drain & Beast Loot ---
    if getattr(attacker, "is_demon", False):
        log.append(f"🩸 [{attacker.name}] ใช้วิชามารดูดกลืนพลัง! ฟื้นฟู HP และ MP ของตนเอง")
        attacker.hp = min(getattr(attacker, "max_hp", 100), getattr(attacker, "hp", 100) + 30)
        attacker.current_mp = min(getattr(attacker, "max_mp", 100), getattr(attacker, "current_mp", 100) + 30)
        
    # --- Calculate Damage ---'''
content = content.replace(old_combat, new_combat)

old_loot = '''            log.append(f"☠️ [{target.name}] ใช้ยันต์วิเศษหนีรอดจากความตายไปได้!")
            escaped = True
            target.hp = getattr(target, "max_hp", 100) * 0.1 # รอดตายด้วย HP 10%
        else:'''
new_loot = '''            log.append(f"☠️ [{target.name}] ใช้ยันต์วิเศษหนีรอดจากความตายไปได้!")
            escaped = True
            target.hp = getattr(target, "max_hp", 100) * 0.1 # รอดตายด้วย HP 10%
        else:
            if getattr(target, "is_beast", False):
                attacker.max_hp = getattr(attacker, "max_hp", 100) + 20
                log.append(f"🔮 [{attacker.name}] ควักแก่นอสูรของ [{target.name}] มาดูดซับ! (Max HP +20)")
            elif getattr(target, "is_demon", False):
                attacker.karmic_debt = max(0, getattr(attacker, "karmic_debt", 0) - 500)
                log.append(f"✨ [{attacker.name}] สังหารมารร้าย! สวรรค์ประทานพร ลดค่ากรรมลง (-500)")'''
content = content.replace(old_loot, new_loot)

with open('tiandao/combat.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("combat.py updated with Demon Drain and Beast Looting!")
