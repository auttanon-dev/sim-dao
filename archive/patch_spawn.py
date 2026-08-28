import re

with open('tiandao/sim.py', 'r', encoding='utf-8') as f:
    content = f.read()

# We want to replace the profession assignment and add tribe and city assignment
# We'll replace lines from 165 to 199.
# The safest way is to locate the def spawn and replace until ch.archetype = IN.pick_archetype(ch, rng)

pattern = re.compile(r'(    def spawn\(self, world, age_years=0\):.*?)(        ch\.archetype = IN\.pick_archetype\(ch, rng\))', re.DOTALL)

def replacer(match):
    return '''    def spawn(self, world, age_years=0):
        rng = self.rng
        dao = rng.choice(list(C.DAO_POOL.keys()))
        r, acc, origin = rng.random(), 0.0, "ชาวบ้าน"
        for o, p in E.ORIGINS:
            acc += p
            if r <= acc:
                origin = o
                break
        blood = self.roll_blood(world)
        
        # Gender and Personality
        gender = rng.choice(["ชาย", "หญิง"]) if blood.get("demon", 0) < 0.8 else rng.choice(["ชาย", "หญิง", "ไม่มีเพศ"])
        fear = round(rng.uniform(0.1, 0.9), 2)
        greed = round(rng.uniform(0.1, 0.9), 2)
        compassion = round(rng.uniform(0.1, 0.9), 2)
        
        # Tribe
        tr_r, tr_acc, tribe = rng.random(), 0.0, "ชาวตงหยวน"
        for t, p in getattr(C, "TRIBES", [("ชาวตงหยวน", 1.0)]):
            tr_acc += p
            if tr_r <= tr_acc:
                tribe = t
                break
                
        # City (only applicable for tier 1)
        city_id = -1
        if world.tier == 1 and hasattr(C, "CITIES") and C.CITIES:
            # Pick a city based on some logic, or randomly. Here, uniformly random.
            # But let's weight by tribe if possible? To keep it simple, purely random.
            city = rng.choice(C.CITIES)
            city_id = city["id"]
        
        ch = Character(
            cid=self.nid("c"),
            name=rng.choice(E.SURNAME) + rng.choice(E.GIVEN),
            world_id=world.wid, dao=dao, dao_tags=list(C.DAO_POOL[dao]),
            born_day=self.day - age_years * 365, blood=blood,
            fate=rng.randint(C.FATE_MIN, C.FATE_MAX), origin=origin,
            gender=gender, fear=fear, greed=greed, compassion=compassion,
            tribe=tribe, city_id=city_id
        )
        ch.traits = IN.pick_traits(rng)
        if rng.random() < 0.05:
            ch.traits.append("พรสวรรค์")
            
        # Apply tribe traits
        if tribe == "เผ่าเหมียว" and "ผู้ใช้พิษ" not in ch.traits: ch.traits.append("ผู้ใช้พิษ")
        if tribe == "เผ่าเร่ร่อน" and "สายแข็งแกร่ง" not in ch.traits: ch.traits.append("สายแข็งแกร่ง")
        if tribe == "เผ่าทิเบต" and "จิตวิญญาณลี้ลับ" not in ch.traits: ch.traits.append("จิตวิญญาณลี้ลับ")
        if tribe == "เผ่าคนป่า" and "สายสัญชาตญาณ" not in ch.traits: ch.traits.append("สายสัญชาตญาณ")
        if tribe == "ชาวอุยกูร์" and "เจ้าเล่ห์" not in ch.traits: ch.traits.append("เจ้าเล่ห์")
            
        # Profession
        prof_r, prof_acc, prof = rng.random(), 0.0, "ชาวนา"
        for p_name, p_prob in getattr(C, "PROFESSIONS", [("ผู้ฝึกตน", 1.0)]):
            prof_acc += p_prob
            if prof_r <= prof_acc:
                prof = p_name
                break
        ch.profession = prof
        
''' + match.group(2)

new_content = pattern.sub(replacer, content)

if new_content != content:
    with open('tiandao/sim.py', 'w', encoding='utf-8') as f:
        f.write(new_content)
    print("sim.py updated.")
else:
    print("Regex failed to match!")
