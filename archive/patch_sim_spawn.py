# -*- coding: utf-8 -*-
with open('tiandao/sim.py', 'r', encoding='utf-8') as f:
    content = f.read()

old_init = '''            import tiandao.config as C'''
new_init = '''            # Spawn initial Spirits
            for i in range(5):
                sp = self.spawn(self.worlds[0])
                sp.name = "วิญญาณศักดิ์สิทธิ์" + str(i)
                sp.is_spirit = True
                sp.realm = 6
                sp.insight = 1000
                sp.energy = 100
                
            import tiandao.config as C'''
content = content.replace(old_init, new_init)

with open('tiandao/sim.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("sim.py updated with initial Spirits spawn!")
