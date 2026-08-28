import re

with open('tiandao/models.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Add hp and max_hp
pattern = re.compile(r'(    karma: float = 0\.0\n    spouse: Optional\[int\] = None)')

def replacer(match):
    return '''    karma: float = 0.0
    spouse: Optional[int] = None
    hp: int = 100
    max_hp: int = 100'''

new_content = pattern.sub(replacer, content)

with open('tiandao/models.py', 'w', encoding='utf-8') as f:
    f.write(new_content)
print("models.py updated with hp.")
