import re

with open('tiandao/models.py', 'r', encoding='utf-8') as f:
    content = f.read()

pattern = re.compile(r'inventory: Dict\[str, any\]')

def replacer(match):
    return 'inventory: dict'

new_content = pattern.sub(replacer, content)

with open('tiandao/models.py', 'w', encoding='utf-8') as f:
    f.write(new_content)
print("models.py fixed.")
