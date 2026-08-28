import json

narratives = []
with open('out/events_0.jsonl', 'r', encoding='utf-8') as f:
    for line in f:
        try:
            ev = json.loads(line)
            if ev.get('kind') in ("เหตุการณ์เมือง", "เผชิญภัย", "วิถียุทธ", "ข่าวสาร", "โชคลาภ", "ทั่วไป"):
                narratives.append(ev.get('text'))
        except Exception as e:
            continue

print("--- Narrative Events Encountered ---")
for msg in narratives[:20]:
    if msg: print(msg)
