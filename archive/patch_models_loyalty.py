import re

with open('tiandao/models.py', 'r', encoding='utf-8') as f:
    content = f.read()

old_fields = '''    is_loner: bool = False
    master_cid: int = -1
    disciples: List[int] = field(default_factory=list)'''

new_fields = '''    is_loner: bool = False
    master_cid: int = -1
    disciples: List[int] = field(default_factory=list)
    loyalty: int = 50
    ambition: int = 50'''

content = content.replace(old_fields, new_fields)

with open('tiandao/models.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("models.py updated with loyalty and ambition!")
