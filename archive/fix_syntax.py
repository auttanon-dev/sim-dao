# -*- coding: utf-8 -*-
with open('tiandao/sim.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('\\\\n        gap = rng.randint(*ev["gap"])', '        gap = rng.randint(*ev["gap"])')

with open('tiandao/sim.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Fixed syntax error")
