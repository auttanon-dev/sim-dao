import re

with open('tiandao/models.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Add fields to Character
char_pattern = re.compile(r'    enemies_defeated: int = 0')
def char_replacer(match):
    return '''    enemies_defeated: int = 0
    generation: int = 1
    parent_name: str = None
    moral: int = 0
    title: str = "ชาวยุทธนิรนาม"
    sect_name: str = None
    sect_role: str = "ศิษย์พเนจร"'''
content = char_pattern.sub(char_replacer, content)

# Add fields to World
world_pattern = re.compile(r'    ratio: float = 0\.0')
def world_replacer(match):
    return '''    ratio: float = 0.0
    current_disaster: str = "ปกติ"
    disaster_timer: int = 0'''
content = world_pattern.sub(world_replacer, content)

with open('tiandao/models.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("models.py updated with Ultimate Sim Character fields.")
