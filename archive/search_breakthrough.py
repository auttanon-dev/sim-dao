# -*- coding: utf-8 -*-
with open('tiandao/sim.py', 'r', encoding='utf-8') as f:
    for i, line in enumerate(f):
        if 'breakthrough' in line or 'ทะลวง' in line:
            print(f"sim.py - {i+1}: {line.strip()}")
