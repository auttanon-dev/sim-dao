import json
try:
    with open('cities.json', 'r', encoding='utf-8') as f:
        cities = json.load(f)
    print("Found cities.json with", len(cities), "cities.")
except Exception as e:
    print("Error loading cities.json:", e)

with open('tiandao/config.py', 'r', encoding='utf-8') as f:
    if "CITIES" in f.read():
        print("CITIES is in config.py")
    else:
        print("CITIES is NOT in config.py")
