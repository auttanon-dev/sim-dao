import json

narratives = []
with open('out/events_0.jsonl', 'r', encoding='utf-8') as f:
    for line in f:
        try:
            ev = json.loads(line)
            if ev.get('kind') in ("อันตราย", "วิถียุทธ", "การค้า", "ความสงบ") and "ความสัมพันธ์" in ev.get('text', ''):
                narratives.append(ev.get('text'))
        except Exception as e:
            continue

print("--- Affection Narrative Events Encountered ---")
for msg in narratives[:10]:
    if msg: print(msg)
