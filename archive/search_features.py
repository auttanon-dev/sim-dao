# -*- coding: utf-8 -*-
with open('tiandao/config.py', 'r', encoding='utf-8') as f:
    for i, line in enumerate(f):
        if 'ค่ายกล' in line or 'ประมูล' in line:
            print(f"config.py - {i+1}: {line.strip()}")

with open('tiandao/models.py', 'r', encoding='utf-8') as f:
    for i, line in enumerate(f):
        if 'ค่ายกล' in line or 'ประมูล' in line or 'formation' in line:
            print(f"models.py - {i+1}: {line.strip()}")
