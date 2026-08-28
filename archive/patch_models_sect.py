import re

with open('tiandao/models.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Update Org class
old_org = '''    members: List[int] = field(default_factory=list)
    grudges: Dict[int, int] = field(default_factory=dict)   # oid -> ระดับ'''

new_org = '''    members: List[int] = field(default_factory=list)
    grudges: Dict[int, int] = field(default_factory=dict)   # oid -> ระดับ
    monthly_resource: int = 10000
    core_disciples: List[int] = field(default_factory=list)
    inner_disciples: List[int] = field(default_factory=list)
    outer_disciples: List[int] = field(default_factory=list)'''
content = content.replace(old_org, new_org)

# Update Character class
old_char = '''    is_loner: bool = False
    master_cid: int = -1
    disciples: List[int] = field(default_factory=list)'''

new_char = '''    is_loner: bool = False
    master_cid: int = -1
    disciples: List[int] = field(default_factory=list)
    sect_rank: str = ""'''
content = content.replace(old_char, new_char)

with open('tiandao/models.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("models.py updated with Sect hierarchies!")
