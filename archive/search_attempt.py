# -*- coding: utf-8 -*-
import os

for root, _, files in os.walk('tiandao'):
    for file in files:
        if file.endswith('.py'):
            with open(os.path.join(root, file), 'r', encoding='utf-8') as f:
                content = f.read()
                if 'attempt_break' in content:
                    print(f"Found attempt_break in {file}")
