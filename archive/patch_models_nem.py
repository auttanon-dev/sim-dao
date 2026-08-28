import re

with open('tiandao/models.py', 'r', encoding='utf-8') as f:
    content = f.read()

pattern = re.compile(r'    companions: dict = field\(default_factory=dict\)')

def replacer(match):
    return '''    companions: dict = field(default_factory=dict)
    nemeses: dict = field(default_factory=dict)'''

new_content = pattern.sub(replacer, content)

with open('tiandao/models.py', 'w', encoding='utf-8') as f:
    f.write(new_content)
print("models.py updated with nemeses.")
