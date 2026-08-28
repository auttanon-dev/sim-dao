# -*- coding: utf-8 -*-
with open('tiandao/sim.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

def_step_idx = -1
for i, line in enumerate(lines):
    if "def step(" in line:
        def_step_idx = i
        break

if def_step_idx != -1:
    # Read the last 50 lines of step before the next def
    end_idx = len(lines)
    for i in range(def_step_idx + 1, len(lines)):
        if lines[i].startswith("    def "):
            end_idx = i
            break
    for j in range(max(def_step_idx, end_idx - 50), end_idx):
        print(f"{j}: {lines[j].rstrip()}")
