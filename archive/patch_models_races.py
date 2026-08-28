import re

with open('tiandao/models.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Update Character class
old_char = '''    is_emperor: bool = False
    dragon_aura: bool = False'''
new_char = '''    is_emperor: bool = False
    dragon_aura: bool = False
    is_demon: bool = False
    is_beast: bool = False
    has_human_form: bool = False
    is_spirit: bool = False
    hp: float = 100.0
    max_hp: float = 100.0'''
content = content.replace(old_char, new_char)

with open('tiandao/models.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("models.py updated with race booleans!")
