# -*- coding: utf-8 -*-
with open('tiandao/sim.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i in range(390, 398):
    if 'import tiandao.config as C' in lines[i]:
        lines[i] = ''

with open('tiandao/sim.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)
print("Removed inner import of C")
