import json
from collections import Counter

counts = Counter()
narratives = []

with open('out/events_0.jsonl', 'r', encoding='utf-8') as f:
    for line in f:
        try:
            ev = json.loads(line)
            counts[ev.get('kind')] += 1
            # We want to see some of the narrative messages
            if ev.get('kind') in ("เหตุการณ์เมือง", "เผชิญภัย", "วิถียุทธ", "ข่าวสาร", "โชคลาภ", "ทั่วไป"):
                narratives.append(ev.get('msg'))
        except Exception as e:
            continue

print("--- Narrative Events Encountered ---")
for msg in narratives[:15]:
    print(msg)
