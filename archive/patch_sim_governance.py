import re

with open('tiandao/sim.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Inject City Initialization into step()
old_step = '''    def step(self):
        rng = self.rng
        actor = None
        while self.queue:'''

new_step = '''    def step(self):
        rng = self.rng
        actor = None
        
        # --- City Governance Initialization ---
        if not getattr(self, "cities_initialized", False):
            self.cities_initialized = True
            import tiandao.config as C
            if hasattr(C, "CITIES"):
                for c in C.CITIES:
                    c_type = c.get("type_desc", "")
                    strictness = 50
                    title = "นายอำเภอ"
                    faction = "ราชสำนัก"
                    ruler_name = "หวังป๋อ"
                    realm = 3
                    
                    if "เมืองหลวง" in c_type:
                        strictness = 90
                        title = "ท่านอ๋อง"
                        ruler_name = "จูหยวน"
                        realm = 6
                    elif "ชายแดน" in c_type:
                        strictness = 80
                        title = "แม่ทัพใหญ่"
                        faction = "กองทัพทหารม้าเหล็ก"
                        ruler_name = "เฉินเฟิง"
                        realm = 5
                    elif "หน้าด่านสำนัก" in c_type:
                        strictness = 40
                        title = "ตัวแทนสำนัก"
                        faction = "พันธมิตรยุทธ"
                        ruler_name = "เย่ฟาน"
                        realm = 7
                    elif "ลับแล" in c_type or "เถื่อน" in c_type or "ตลาดมืด" in c_type:
                        strictness = 10
                        title = "ราชาตลาดมืด"
                        faction = "สมาคมนักฆ่า"
                        ruler_name = "เงาทมิฬ"
                        realm = 8
                        
                    c["law_strictness"] = strictness
                    
                    # Spawn the Ruler
                    ruler = self.spawn(self.worlds[0]) # Spawn in mortal world
                    ruler.name = ruler_name
                    ruler.realm = realm
                    ruler.title = title
                    ruler.faction = faction
                    ruler.city_id = c["id"]
                    ruler.is_loner = True # Don't wander taking disciples
                    ruler.energy = 100
                    c["ruler_cid"] = ruler.cid
                    
        while self.queue:'''
content = content.replace(old_step, new_step)

# 2. Inject Law Strictness into PvP event check
# Look for: win, lose, log, escaped = combat.resolve_combat(actor, target_ch, world, self)
old_combat = '''                    win, lose, log, escaped = combat.resolve_combat(actor, target_ch, world, self)'''

new_combat = '''                    # Law Enforcement Check
                    blocked = False
                    if actor.city_id >= 0 and hasattr(C, "CITIES"):
                        city_dict = next((c for c in C.CITIES if c["id"] == actor.city_id), None)
                        if city_dict and "law_strictness" in city_dict:
                            if rng.random() * 100 < city_dict["law_strictness"]:
                                blocked = True
                                r_cid = city_dict.get("ruler_cid", -1)
                                if r_cid in self.cast and self.cast[r_cid].alive:
                                    ruler = self.cast[r_cid]
                                    return self.emit(world, "กฎหมายเมือง", actor, target_ch, ["กฎหมาย"], "ถูกสกัด", f"[{ruler.title} {ruler.name}] ผู้ปกครองเมืองเข้ามาสกัดการต่อสู้! ผิดกฎเมืองที่มีความเข้มงวด {city_dict['law_strictness']}/100", elapsed, {})
                    
                    if blocked:
                        return self.emit(world, "กฎหมายเมือง", actor, target_ch, ["กฎหมาย"], "ถูกสกัด", f"กองทหารลาดตระเวนเมืองเข้ามาสกัดการต่อสู้!", elapsed, {})
                    
                    win, lose, log, escaped = combat.resolve_combat(actor, target_ch, world, self)'''
content = content.replace(old_combat, new_combat)

with open('tiandao/sim.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("sim.py updated with City Governance!")
