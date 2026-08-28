# -*- coding: utf-8 -*-
with open('tiandao/sim.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for j in range(max(0, 769-10), min(len(lines), 769+10)):
    print(f"{j+1}: {repr(lines[j])}")
