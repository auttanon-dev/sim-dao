# -*- coding: utf-8 -*-
with open('tiandao/sim.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

lines[768] = lines[768].replace('\\\\n', '')

with open('tiandao/sim.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)
print("Fixed syntax error")
