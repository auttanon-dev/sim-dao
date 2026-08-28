import re

with open('tiandao/config.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if "CITIES" in line:
        for j in range(i, min(len(lines), i+15)):
            print(f"{j}: {lines[j].strip()}")
        break
