import re

with open('tiandao/models.py', 'r', encoding='utf-8') as f:
    content = f.read()

pattern = re.compile(r'(    hp: int = 100\n    max_hp: int = 100)')

def replacer(match):
    return '''    hp: int = 100
    max_hp: int = 100
    inventory: Dict[str, any] = field(default_factory=lambda: {"อาวุธ": None, "ยาสมานแผล": 0})'''

new_content = pattern.sub(replacer, content)

with open('tiandao/models.py', 'w', encoding='utf-8') as f:
    f.write(new_content)
print("models.py updated with inventory.")
