import re

with open('tiandao/combat.py', 'r', encoding='utf-8') as f:
    content = f.read()

old_combat = '''def resolve_combat(attacker, target, world, sim_instance):'''
new_combat = '''def resolve_combat(attacker, target, world, sim_instance):
    # --- Imperial Karmic Backlash ---
    if getattr(target, "is_emperor", False) and getattr(target, "dragon_aura", False):
        log = []
        log.append(f"🐉 คำเตือนจากฟ้าดิน! กลิ่นอายมังกรทองของโอรสสวรรค์ปะทุขึ้นปกป้อง!")
        world.empire_stability = max(0, getattr(world, "empire_stability", 100) - 50)
        log.append(f"👑 ฮ่องเต้สวรรคต! ความมั่นคงแผ่นดินลดฮวบเหลือ {world.empire_stability}% เกิดกลียุค!")
        sim_instance.kill(target, "ถูกลอบปลงพระชนม์ (เกิดกลียุค)")
        
        attacker.karmic_debt = getattr(attacker, "karmic_debt", 0) + 10000
        log.append(f"⚡ ทัณฑ์สวรรค์ทำงาน! [{attacker.name}] แบกรับกรรมจากการทำลายสมดุลโลก (ค่ากรรม: {attacker.karmic_debt})")
        log.append(f"☠️ สายฟ้าเก้าสีผ่าลงมา ทำลายรากฐานวิถีเต๋า [{attacker.name}] สิ้นชีพในทันที!")
        sim_instance.kill(attacker, "ถูกทัณฑ์สวรรค์ (สังหารโอรสสวรรค์)")
        
        # return dummy win/lose/log/escaped
        return target, attacker, "\\n".join(log), False
'''
content = content.replace(old_combat, new_combat)

with open('tiandao/combat.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("combat.py updated with Karmic Backlash!")
