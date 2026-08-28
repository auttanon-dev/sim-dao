# -*- coding: utf-8 -*-
with open('tiandao/sim.py', 'r', encoding='utf-8') as f:
    for line in f:
        if 'def resolve' in line:
            break
    for _ in range(50):
        print(next(f).strip())
