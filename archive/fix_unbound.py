# -*- coding: utf-8 -*-
with open('tiandao/sim.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace("            import tiandao.config as C\\n", "")

with open('tiandao/sim.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Removed inner import of C")
