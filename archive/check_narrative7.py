import json

narratives = []
with open('out/events_0.jsonl', 'r', encoding='utf-8') as f:
    for line in f:
        try:
            ev = json.loads(line)
            if ev.get('kind') in ("อันตราย", "วิถียุทธ", "การค้า", "ความสงบ") and ("คู่แค้น" in ev.get('text', '') or "เถาตี้" in ev.get('text', '') or "คุณชายมู่" in ev.get('text', '')):
                narratives.append(ev.get('text'))
        except Exception as e:
            continue

print("--- Nemesis Narrative Events Encountered ---")
for msg in narratives[:10]:
    if msg: print(msg)
