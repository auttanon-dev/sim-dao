import re

with open('tiandao/models.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Update Org class
old_org = '''    threat_level: int = 0
    facilities: Dict[str, int] = field(default_factory=dict)   # name -> master cid'''
if old_org not in content:
    # Meaning threat_level is not there yet. We need to add it.
    old_org = '''    facilities: Dict[str, int] = field(default_factory=dict)   # name -> master cid'''
    new_org = '''    facilities: Dict[str, int] = field(default_factory=dict)   # name -> master cid
    alert_level: int = 50
    threat_level: int = 0'''
    content = content.replace(old_org, new_org)

# Update Character class
old_char = '''    sect_rank: str = ""'''
new_char = '''    sect_rank: str = ""
    karmic_debt: int = 0
    is_emperor: bool = False
    dragon_aura: bool = False'''
content = content.replace(old_char, new_char)

# Update World class
old_world = '''    level: int = 1'''
new_world = '''    level: int = 1
    empire_stability: int = 100'''
content = content.replace(old_world, new_world)

with open('tiandao/models.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("models.py updated with Imperial Politics!")
