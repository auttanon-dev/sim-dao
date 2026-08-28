import sys
sys.path.append('.')
from tiandao.sim import Sim
from tiandao.models import World
import tiandao.config as C

s = Sim()
s.init_worlds()
s.repopulate_all()

heaven_wars = 0
wars_won = 0
heaven_wars_deaths = 0

for _ in range(200000):
    e = s.step()
    if e:
        if e['kind'] == 'สงครามเบิกฟ้า':
            heaven_wars += 1
            if 'ประตูปิดกั้นพังทลาย' in e.get('d', {}):
                wars_won += 1
            if e['result'] == 'ตาย':
                heaven_wars_deaths += 1

print('--- Diagnostic Results ---')
print(f'Events run: {s.seq}')
print(f'Elapsed years: {s.day / 365.0:.1f}')
print(f'Heaven Wars Attempted: {heaven_wars}')
print(f'Heaven Wars Won (Gates broken): {wars_won}')
print(f'Heaven Wars Deaths: {heaven_wars_deaths}')

w1 = s.world(1)
if w1:
    print(f'Tier 1 Population: {w1.n_alive} / {C.HEAVEN_POP_LIMIT}')
    print(f'Tier 1 Closed: {w1.is_closed}')
    print(f'Tier 1 Energy: {w1.heaven:.1f} / {w1.cap():.1f}')
