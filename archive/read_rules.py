# -*- coding: utf-8 -*-
with open('tiandao/rules.py', 'r', encoding='utf-8') as f:
    for line in f:
        if 'def attempt_break' in line:
            print(line.rstrip())
            for _ in range(50):
                print(next(f).rstrip())
            break
