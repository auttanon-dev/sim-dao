import re

# Patch rules.py to include Mortal Realms tribulation text
with open('tiandao/rules.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace the "ผ่าน" return line in attempt_break
content = re.sub(
    r'return "ผ่าน", f"\{ch.name\}เลื่อนเป็น\{ch.realm_name\(\)\} \(\{note\}\)"',
    '''tribulation = ""
    if ch.tier <= 0 and (ch.realm + 1) in C.MORTAL_REALMS_CONFIG:
        t = C.MORTAL_REALMS_CONFIG[ch.realm + 1]["tribulation"]
        if t != "ไม่มี":
            tribulation = f" ฝ่าวิกฤต [{t}]"
    return "ผ่าน", f"{ch.name}เลื่อนเป็น{ch.realm_name()} ({note}){tribulation}"''',
    content
)
with open('tiandao/rules.py', 'w', encoding='utf-8') as f:
    f.write(content)


# Patch sim.py to handle Canonical Factions
with open('tiandao/sim.py', 'r', encoding='utf-8') as f:
    sim_content = f.read()

factions_injection = '''
                        # ----------------------------------------------------
                        # 🏯 ขั้วอำนาจหลัก (Major Factions System)
                        # ----------------------------------------------------
                        if getattr(a, "sect_name", None) is None:
                            # Try to join a canonical faction based on moral and dao
                            available_sects = []
                            for align, sects in C.FACTIONS.items():
                                if align == "ฝ่ายธรรมะ" and a.moral < 10: continue
                                if align == "ฝ่ายอธรรม" and a.moral > -10: continue
                                for sect in sects:
                                    if sect["focus"] == a.dao:
                                        available_sects.append(sect)
                            if available_sects and rng.random() < 0.2: # 20% chance to join
                                chosen = rng.choice(available_sects)
                                a.sect_name = chosen["name"]
                                a.sect_role = "ศิษย์ในสำนัก"
                                print(f"🏯 [ขั้วอำนาจหลัก] {a.name} ({a.dao}) เข้าร่วม {a.sect_name} สำเร็จ! ({chosen['trait']})")
'''

sim_content = re.sub(
    r'(# --- 🏯 ระบบสำนักและศิษย์ทรยศ ---)',
    factions_injection + r'\n                        \1',
    sim_content
)

factions_pvp_injection = '''
                            # --- ⚔️ สงครามขั้วอำนาจ (Faction Wars) ---
                            a_align = None
                            b_align = None
                            for align, sects in C.FACTIONS.items():
                                for s in sects:
                                    if a.sect_name == s["name"]: a_align = align
                                    if b.sect_name == s["name"]: b_align = align
                            
                            is_faction_war = False
                            if a_align and b_align and a_align != b_align:
                                if (a_align == "ฝ่ายธรรมะ" and b_align == "ฝ่ายอธรรม") or (a_align == "ฝ่ายอธรรม" and b_align == "ฝ่ายธรรมะ"):
                                    is_faction_war = True
                            
                            if is_faction_war:
                                print(f"⚔️💥 [สงครามขั้วอำนาจ] {a.name} ({a.sect_name}) ปะทะ {b.name} ({b.sect_name}) กลางเมือง!")
                                self.resolve_duel(a, b)
                                continue
'''

sim_content = re.sub(
    r'(# สุ่มเกิดความสัมพันธ์เชิงบวกหรือลบ)',
    factions_pvp_injection + r'\n                            \1',
    sim_content
)

with open('tiandao/sim.py', 'w', encoding='utf-8') as f:
    f.write(sim_content)

print("rules.py and sim.py patched for Tribulations and Factions!")
