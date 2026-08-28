import re

with open('tiandao/rules.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if 'return' in line and 'ch.realm_name()' in line and '{note}' in line:
        lines[i] = '''
    tribulation = ""
    if ch.tier <= 0 and (ch.realm + 1) in C.MORTAL_REALMS_CONFIG:
        t = C.MORTAL_REALMS_CONFIG[ch.realm + 1]["tribulation"]
        if t != "ไม่มี":
            tribulation = f" ฝ่าวิกฤต [{t}]"
    return "ผ่าน", f"{ch.name}เลื่อนเป็น{ch.realm_name()} ({note}){tribulation}"
'''

with open('tiandao/rules.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)
print("Line patched in rules.py!")
