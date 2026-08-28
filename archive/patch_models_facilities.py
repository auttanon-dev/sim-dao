import re

with open('tiandao/models.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Update Org class
old_org = '''    inner_disciples: List[int] = field(default_factory=list)
    outer_disciples: List[int] = field(default_factory=list)'''

new_org = '''    inner_disciples: List[int] = field(default_factory=list)
    outer_disciples: List[int] = field(default_factory=list)
    facilities: Dict[str, int] = field(default_factory=dict)   # name -> master cid'''
content = content.replace(old_org, new_org)

with open('tiandao/models.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("models.py updated with Sect Facilities!")
