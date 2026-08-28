import re

with open('tiandao/events.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Add the event to EVENT_TABLE
new_event_line = '    dict(kind="เหตุการณ์เมือง",  w=15, gap=(50, 300), tags=["เมือง"], tgt=False),\n'
content = content.replace('    dict(kind="สะสมบุญบารมี",', new_event_line + '    dict(kind="สะสมบุญบารมี",')

# We also need to add logic in pick_event
# Right now pick_event just adds weights for other professions. We can boost "เหตุการณ์เมือง" if they are in a city.
pattern = re.compile(r'(        # ถ้าเป็นชาวบ้าน/อาชีพทั่วไป กรองเรื่องเหนือธรรมชาติ.*?weighted_pool\.append\(\(e, max\(0, w\)\)\))', re.DOTALL)

def replacer(match):
    return '''        if k == "เหตุการณ์เมือง":
            if city: w += 50
            else: w = 0
            
''' + match.group(1)

new_content = pattern.sub(replacer, content)

with open('tiandao/events.py', 'w', encoding='utf-8') as f:
    f.write(new_content)
print("events.py updated.")
