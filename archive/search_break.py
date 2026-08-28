# -*- coding: utf-8 -*-
with open('tiandao/sim.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if "attempt_break" in line:
        for j in range(max(0, i-5), min(len(lines), i+15)):
            print(f"{j}: {lines[j].strip()}")
