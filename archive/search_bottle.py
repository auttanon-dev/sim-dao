# -*- coding: utf-8 -*-
import os

for root, _, files in os.walk('tiandao'):
    for file in files:
        if file.endswith('.py'):
            with open(os.path.join(root, file), 'r', encoding='utf-8') as f:
                content = f.read()
                if 'at_bottleneck' in content:
                    print(f"Found in {file}")
