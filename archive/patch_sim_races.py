# -*- coding: utf-8 -*-
with open('tiandao/sim.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Demon Possession Event in the 30-day loop
# Hook into the 30 day loop
old_spy = '''                # Imperial Spy Network'''
new_spy = '''                # Demon Temptation (Possession)
                for ch in self.cast.values():
                    if ch.alive and not getattr(ch, "is_demon", False) and not getattr(ch, "is_spirit", False) and not getattr(ch, "is_beast", False):
                        if getattr(ch, "karmic_debt", 0) > 1000 or getattr(ch, "ambition", 0) > 80:
                            if self.rng.random() < 0.05: # 5% chance every 30 days
                                ch.is_demon = True
                                ch.dao = "วิถีมาร"
                                if ch.org is not None and ch.org < len(self.orgs):
                                    # Leave current sect
                                    org = self.orgs[ch.org]
                                    if ch.cid in org.members: org.members.remove(ch.cid)
                                    if ch.cid in org.core_disciples: org.core_disciples.remove(ch.cid)
                                    if ch.cid in org.inner_disciples: org.inner_disciples.remove(ch.cid)
                                    if ch.cid in org.outer_disciples: org.outer_disciples.remove(ch.cid)
                                ch.org = None
                                print(f"\\n🩸 [มารสิงสู่] [{ch.name}] ถูกจิตมารเข้าครอบงำเพราะกิเลสหนา! กลายเป็นเผ่ามารอย่างสมบูรณ์แบบ!")

                # Beast Horde Siege
                beast_kings = [c for c in self.cast.values() if c.alive and getattr(c, "is_beast", False) and c.realm >= 4]
                for king in beast_kings:
                    if not getattr(king, "has_human_form", False):
                        king.has_human_form = True
                        king.name = "ราชันย์อสูร" + self.rng.choice(["เพลิง", "ทมิฬ", "สายฟ้า", "โลหิต", "น้ำแข็ง"])
                        print(f"\\n🐉 [คลื่นสัตว์อสูร] สัตว์อสูรบำเพ็ญตบะทะลวงขั้นสำเร็จ จำแลงกายเป็นมนุษย์ นามว่า [{king.name}]!")
                    
                    if self.rng.random() < 0.1: # 10% chance to attack a city
                        import tiandao.config as C
                        if hasattr(C, "CITIES"):
                            targets = [city for city in C.CITIES if "ชายแดน" in city.get("type_desc", "") or "หน้าด่านสำนัก" in city.get("type_desc", "")]
                            if targets:
                                target = self.rng.choice(targets)
                                print(f"\\n🌋 [คลื่นสัตว์อสูรบุกเมือง] [{king.name}] นำกองทัพอสูรบุกโจมตีเมือง <{target['name_th']}>!")
                                ruler_cid = target.get("ruler_cid", -1)
                                if ruler_cid in self.cast and self.cast[ruler_cid].alive:
                                    ruler = self.cast[ruler_cid]
                                    # Fake combat for siege
                                    if king.realm > ruler.realm:
                                        print(f" -> 🔴 เมืองแตก! [{ruler.name}] พ่ายแพ้ต่อราชันย์อสูรและสิ้นชีพ! กฎหมายเมืองล่มสลาย!")
                                        ruler.alive = False
                                        target["law_strictness"] = 0
                                    else:
                                        print(f" -> 🟢 ป้องกันเมืองสำเร็จ! [{ruler.name}] สังหารราชันย์อสูรได้ เมืองสงบสุข!")
                                        king.alive = False
                                        ruler.max_hp = getattr(ruler, "max_hp", 100) + 50
                                        print(f" -> 🔮 [{ruler.name}] ดูดซับแก่นอสูร พลังชีวิตสูงสุดเพิ่มขึ้น!")

                # Imperial Spy Network'''
content = content.replace(old_spy, new_spy)

with open('tiandao/sim.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("sim.py updated with Demon Possession and Beast Horde Sieges!")
