# -*- coding: utf-8 -*-
with open('tiandao/sim.py', 'r', encoding='utf-8') as f:
    for line in f:
        if 'if k == "ข้ามขั้น":' in line:
            print(line.rstrip())
            for _ in range(50):
                print(next(f).rstrip())
            break
