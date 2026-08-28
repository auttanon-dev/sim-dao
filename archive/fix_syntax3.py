# -*- coding: utf-8 -*-
with open('tiandao/sim.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for j in range(max(0, 769-5), min(len(lines), 769+5)):
    if 'gap = rng.randint(*ev["gap"])' in lines[j]:
        lines[j] = '        gap = rng.randint(*ev["gap"])\n'

with open('tiandao/sim.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)
print("Fixed syntax error")
