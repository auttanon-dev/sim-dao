# -*- coding: utf-8 -*-
with open('tiandao/sim.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i in range(385, 415):
    print(f"{i}: {repr(lines[i])}")
