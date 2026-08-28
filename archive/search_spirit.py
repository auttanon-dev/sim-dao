# -*- coding: utf-8 -*-
with open('tiandao/config.py', 'r', encoding='utf-8') as f:
    for i, line in enumerate(f):
        if 'SPIRIT' in line or 'spirit' in line.lower() or 'วิญญาณ' in line:
            print(f"{i+1}: {line.strip()}")
