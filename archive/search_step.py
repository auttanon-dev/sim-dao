# -*- coding: utf-8 -*-
with open('tiandao/sim.py', 'r', encoding='utf-8') as f:
    in_step = False
    for line in f:
        if 'def step' in line:
            in_step = True
        if in_step and 'insight' in line:
            print(line.strip())
