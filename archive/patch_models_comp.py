import re

with open('tiandao/models.py', 'r', encoding='utf-8') as f:
    content = f.read()

pattern = re.compile(r'(    inventory: dict = field\(default_factory=lambda: \{"อาวุธ": None, "ยาสมานแผล": 0\}\))')

def replacer(match):
    return '''    inventory: dict = field(default_factory=lambda: {"อาวุธ": None, "ยาสมานแผล": 0})
    companions: List[str] = field(default_factory=list)'''

new_content = pattern.sub(replacer, content)

with open('tiandao/models.py', 'w', encoding='utf-8') as f:
    f.write(new_content)
print("models.py updated with companions.")
