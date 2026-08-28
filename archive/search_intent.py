# -*- coding: utf-8 -*-
with open('tiandao/intent.py', 'r', encoding='utf-8') as f:
    for i, line in enumerate(f):
        if 'break' in line or 'ทะลวง' in line or 'realm +=' in line or 'realm =' in line:
            print(f"intent.py - {i+1}: {line.strip()}")
