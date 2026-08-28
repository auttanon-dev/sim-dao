import re

with open('tiandao/models.py', 'r', encoding='utf-8') as f:
    content = f.read()

old_char = '''    items: List[int] = field(default_factory=list)
    money: Dict[int, float] = field(default_factory=dict)   # tier -> จำนวน'''
new_char = '''    items: List[int] = field(default_factory=list)
    money: Dict[int, float] = field(default_factory=dict)   # tier -> จำนวน
    spirit_stones: float = 1000.0   # เงินตราหลักสำหรับประมูล'''
content = content.replace(old_char, new_char)

with open('tiandao/models.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("models.py updated!")
