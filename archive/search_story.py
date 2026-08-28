# -*- coding: utf-8 -*-
with open('tiandao/story.py', 'r', encoding='utf-8') as f:
    for i, line in enumerate(f):
        if 'ทะลวง' in line or 'realm' in line:
            print(f"story.py - {i+1}: {line.strip()}")
