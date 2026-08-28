import json
from collections import Counter

counts = Counter()
professions = Counter()
tribes = Counter()
cities = Counter()

with open('out/events_0.jsonl', 'r', encoding='utf-8') as f:
    for line in f:
        try:
            ev = json.loads(line)
            counts[ev.get('kind')] += 1
            if 'actor' in ev:
                professions[ev['actor'].get('profession')] += 1
                tribes[ev['actor'].get('tribe')] += 1
                cities[ev['actor'].get('city_id')] += 1
        except Exception as e:
            continue

print("--- Event Frequencies ---")
for k, v in counts.most_common(10):
    print(f"{k}: {v}")
print("\n--- Top Professions (actor count) ---")
for k, v in professions.most_common(10):
    print(f"{k}: {v}")
print("\n--- Tribes (actor count) ---")
for k, v in tribes.most_common():
    print(f"{k}: {v}")
