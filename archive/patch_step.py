import re

with open('tiandao/sim.py', 'r', encoding='utf-8') as f:
    content = f.read()

pattern = re.compile(r'(        kind = IN\.choose\(actor, self, E\.EVENT_TABLE, bool\(others\), rng\)\n        ev = next\(\(e for e in E\.EVENT_TABLE if e\["kind"\] == kind\), None\) \\\n            or E\.pick_event\(actor, rng, bool\(others\)\))', re.DOTALL)

def replacer(match):
    return '''        city_dict = None
        if hasattr(C, "CITIES") and actor.city_id >= 0:
            for c in C.CITIES:
                if c["id"] == actor.city_id:
                    city_dict = c
                    break
                    
        # Update pick_event call to include city
        kind = IN.choose(actor, self, E.EVENT_TABLE, bool(others), rng)
        ev = next((e for e in E.EVENT_TABLE if e["kind"] == kind), None) \\
            or E.pick_event(actor, rng, bool(others), city=city_dict)'''

new_content = pattern.sub(replacer, content)

if new_content != content:
    with open('tiandao/sim.py', 'w', encoding='utf-8') as f:
        f.write(new_content)
    print("sim.py updated step().")
else:
    print("Regex failed to match!")
