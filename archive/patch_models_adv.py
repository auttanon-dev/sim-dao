import re

with open('tiandao/models.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Let's find the Character dataclass definition and insert new fields
if "energy: float" not in content:
    # Inject fields after insight/refine
    old_fields = '''    insight: float = 0.0        # ซากุระบาน (ปัญญา)
    refine: float = 0.0         # ซากศพหอด (วิญญาณ)'''
    
    new_fields = '''    insight: float = 0.0        # ค่าการรู้แจ้ง
    refine: float = 0.0         # ค่าหลอมวิญญาณ
    
    # --- Advanced Combat & Routine Fields ---
    energy: float = 100.0
    current_mp: float = 100.0
    max_mp: float = 100.0
    active_formation: str = ""
    formation_duration: int = 0
    current_state: str = "Sleeping"
    life_goal: str = "บำเพ็ญเพียรแสวงหามรรควิถี"
    
    # --- Sect & Hierarchy Fields ---
    is_loner: bool = False
    master_cid: int = -1
    disciples: list = field(default_factory=list)'''
    
    content = content.replace(old_fields, new_fields)
    
    with open('tiandao/models.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("models.py updated with new fields!")
else:
    print("models.py already has energy field.")
