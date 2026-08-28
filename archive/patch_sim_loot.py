import re

with open('tiandao/sim.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Inject make_rare_item function right below make_item
old_make_item = '''    def make_item(self, kind, tier, grade, maker=None):
        it = Item(iid=self.nid("i"), kind=kind, tier=tier, grade=grade, maker=maker)
        it.name = f"{kind}วิถี{min(9, int(grade * 3) + 1)}"
        self.items[it.iid] = it
        return it'''

new_make_item = '''    def make_item(self, kind, tier, grade, maker=None):
        it = Item(iid=self.nid("i"), kind=kind, tier=tier, grade=grade, maker=maker)
        it.name = f"{kind}วิถี{min(9, int(grade * 3) + 1)}"
        self.items[it.iid] = it
        return it
        
    def make_rare_item(self, tier, grade_idx):
        grade_name = C.ITEM_GRADES[grade_idx]
        # Choose a random category and then a random item from it
        category = self.rng.choice(list(C.MANUALS_AND_TALISMANS.keys()))
        specific_name = self.rng.choice(C.MANUALS_AND_TALISMANS[category])
        
        it = Item(iid=self.nid("i"), kind=category, tier=tier, grade=float(grade_idx)/3.0)
        it.name = f"{specific_name} [{grade_name}]"
        
        # We can store the raw specific name in maker field or create a new field if needed, 
        # but let's just parse it from name or store it in a dict on the character later.
        # Actually, adding 'subkind' to Item is safer. Let's assume we can just check it.kind and it.name
        
        self.items[it.iid] = it
        return it'''

content = content.replace(old_make_item, new_make_item)

# Hook it into cache creation!
# In make_cache:
old_cache = '''        for _ in range(rng.randint(1, 3 + w.tier)):
            k = rng.choice(["อาวุธ", "ชุดเกราะ", "วัตถุดิบปรุงยา"])
            it = self.make_item(k, w.tier, rng.random(), a.cid)
            items.append(it.iid)'''
            
new_cache = '''        for _ in range(rng.randint(1, 3 + w.tier)):
            if rng.random() < 0.3: # 30% chance for a rare manual/talisman
                it = self.make_rare_item(w.tier, rng.randint(0, len(C.ITEM_GRADES)-1))
            else:
                k = rng.choice(["อาวุธ", "ชุดเกราะ", "วัตถุดิบปรุงยา"])
                it = self.make_item(k, w.tier, rng.random(), a.cid)
            items.append(it.iid)'''
            
content = content.replace(old_cache, new_cache)

with open('tiandao/sim.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("sim.py updated with rare loot drops!")
