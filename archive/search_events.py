# -*- coding: utf-8 -*-
with open('tiandao/sim.py', 'r', encoding='utf-8') as f:
    for line in f:
        if 'k, d = ev["kind"]' in line:
            break
    for _ in range(300):
        l = next(f)
        if 'if k ==' in l or 'elif k ==' in l:
            print(l.strip())
