# -*- coding: utf-8 -*-
with open('tiandao/sim.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if "def resolve(" in line:
        for j in range(i, i+15):
            print(f"{j}: {lines[j].strip()}")
        break
