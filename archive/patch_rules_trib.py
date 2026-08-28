# -*- coding: utf-8 -*-
with open('tiandao/rules.py', 'r', encoding='utf-8') as f:
    content = f.read()

old_break = '''    # สำเร็จ — ถอนพลังจากคลังฟ้า
    take = min(cost, world.heaven)
    world.heaven -= take
    ch.drawn += take
    ch.realm += 1'''
new_break = '''    # ------------------------------------------------
    # Heavenly Tribulation (ทัณฑ์สวรรค์)
    # ------------------------------------------------
    tribulation_msg = ""
    # Spirit bloodline does not face Tribulation (they cultivate bloodline natively)
    if not getattr(ch, "is_spirit", False):
        if ch.realm + 1 in [4, 7, 9]:
            import tiandao.config as C
            tribulation_msg = f"\\n⚡ [ทัณฑ์สวรรค์] ฟ้าดินพิโรธ! ส่งสายฟ้าฟาดฟัน {ch.name} เพื่อหยุดยั้งการเบิกมรรค!"
            
            # Massive damage based on the realm they are trying to reach
            trib_dmg = (ch.realm + 1) * 30
            
            # Survival mechanics
            hp_pool = getattr(ch, "hp", 100)
            if hp_pool <= trib_dmg:
                # Fail the breakthrough because they couldn't endure it
                ch.hp = 1
                ch.decay += C.BACKLASH_DECAY * 2.0
                return "บาดเจ็บสาหัส", tribulation_msg + f"\\n -> ❌ {ch.name} ทนรับทัณฑ์สวรรค์ไม่ไหว บาดเจ็บปางตาย การทะลวงขั้นล้มเหลว!"
            else:
                ch.hp -= trib_dmg
                tribulation_msg += f"\\n -> 🛡️ {ch.name} ทนรับทัณฑ์สวรรค์สำเร็จ! (สูญเสีย HP {trib_dmg})"

    # สำเร็จ — ถอนพลังจากคลังฟ้า
    take = min(cost, world.heaven)
    world.heaven -= take
    ch.drawn += take
    ch.realm += 1'''

content = content.replace(old_break, new_break)

old_ret = '''        if ch.realm == 1:
            world.n_mortal -= 1
        ch.breaks += 1
        return True, f"{ch.name}ข้ามขั้นสำเร็จ"'''
new_ret = '''        if ch.realm == 1:
            world.n_mortal -= 1
        ch.breaks += 1
        return True, f"{ch.name}ข้ามขั้นสำเร็จ" + tribulation_msg'''
content = content.replace(old_ret, new_ret)

with open('tiandao/rules.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("rules.py updated with Heavenly Tribulation!")
