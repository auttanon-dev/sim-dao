import json

narratives = []
with open('out/events_0.jsonl', 'r', encoding='utf-8') as f:
    for line in f:
        try:
            ev = json.loads(line)
            if ev.get('kind') in ("อันตราย", "วิถียุทธ", "ข่าวสาร", "การค้า", "ความสงบ"):
                narratives.append(ev.get('text'))
        except Exception as e:
            continue

print("--- HP & Money Narrative Events Encountered ---")
for msg in narratives[:10]:
    if msg: print(msg)
