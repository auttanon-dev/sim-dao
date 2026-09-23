# -*- coding: utf-8 -*-
"""ทดสอบการแก้บั๊กสมบัติฟ้าดินทั้ง 3 ตัว"""
import contextlib, io, sys
sys.path.insert(0, "/tmp/simdao")
from tiandao import sim as S, config as C, rules as R

sim = S.Sim(seed=17, tiers=3)
w = sim.worlds[0]
legend_iids = list(sim.legend_iids)
print(f"สมบัติฟ้าดินในโลก {len(legend_iids)} ชิ้น\n")

def where(sim):
    held, sealed, opened = set(), set(), set()
    for c in sim.cast:
        if c.alive: held.update(c.items)
    for k in sim.caches:
        (opened if k.opened else sealed).update(k.items)
    lost = [i for i in sim.legend_iids if i in sim.items and i not in held and i not in sealed]
    return len(held & set(sim.legend_iids)), len(sealed & set(sim.legend_iids)), len(lost)

# --- 1. แดนลับกับดัก: เจ้าของชนะ -> ผนึกต้องยังอยู่ ของต้องไม่หาย
owner = sim.living_in(0)[0]
owner.realm = 9
raider = sim.living_in(0)[1]
raider.realm = 0
iid = legend_iids[0]
owner.items = [iid]
with contextlib.redirect_stdout(io.StringIO()):
    k = sim.make_cache(owner, faked=True)
print(f"แดนลับกับดักของ{owner.name} มีของ {len(k.items)} ชิ้น opened={k.opened}")
with contextlib.redirect_stdout(io.StringIO()):
    d = sim.open_cache(raider, k, sim.rng)
print(f"  คนอ่อนบุกเข้าไป -> opened={k.opened} ของยังอยู่ {len(k.items)} ชิ้น (สมบัติฟ้าดินอยู่ครบ {iid in k.items}) | {d.get('ผนึก')}")
assert not k.opened and iid in k.items, "เจ้าของชนะแล้วผนึกต้องยังอยู่ ของต้องไม่หาย"

# --- 2. คนแกร่งบุกสำเร็จ -> ต้องได้ของ และ k.items ต้องถูกล้าง
strong = sim.living_in(0)[2]
strong.realm = 9
strong.skills = ["มหาอาคมเปิดทวารมิติถาวร", "มหาอาคมตรึงกาลนิ่งงัน"]
with contextlib.redirect_stdout(io.StringIO()):
    d = sim.open_cache(strong, k, sim.rng)
print(f"  คนแกร่งบุก -> opened={k.opened} ของเหลือในแดนลับ {len(k.items)} | ผู้บุกได้ของ {iid in strong.items}")
assert k.opened and k.items == [] and iid in strong.items

# --- 3. สมบัติหายจากโลก -> การกวาดต้องผนึกกลับคืน
# จำลองของหลุดหายจากโลก — ถอดออกจากมือใครก็ตามที่ถืออยู่จริง
for _c in sim.cast:
    if iid in _c.items:
        _c.items.remove(iid)
for _k in sim.caches:
    if iid in _k.items:
        _k.items.remove(iid)
h, sl, lost = where(sim)
print(f"\nหลังจำลองของหาย: มีคนถือ {h} · อยู่ในผนึก {sl} · หายไปเฉยๆ {lost}")
assert lost >= 1
with contextlib.redirect_stdout(io.StringIO()):
    n = sim.reseal_lost_legends()
h2, sl2, lost2 = where(sim)
print(f"หลังกวาด: ผนึกกลับคืน {n} ชิ้น -> มีคนถือ {h2} · อยู่ในผนึก {sl2} · หายไปเฉยๆ {lost2}")
assert lost2 == 0, "หลังกวาดต้องไม่มีสมบัติฟ้าดินหายจากโลกเลย"
ev = [e for e in sim.log if e.kind == "สมบัติฟ้าดินหวนคืนผนึก"]
print(f"  เหตุการณ์: {ev[-1].text[:90]}")
print(f"     {list(ev[-1].deltas.items())[0]}")

# --- 4. เดินโลกจริงแล้วต้องไม่มีของหายสะสม
with contextlib.redirect_stdout(io.StringIO()):
    for _ in range(60000):
        if sim.step() is None: break
h3, sl3, lost3 = where(sim)
print(f"\nเดิน 60,000 เหตุการณ์ (ปีที่ {sim.day//365}): มีคนถือ {h3} · อยู่ในผนึก {sl3} · หายไปเฉยๆ {lost3}")
sweeps = [e for e in sim.log if e.kind == "สมบัติฟ้าดินหวนคืนผนึก"]
print(f"  การกวาดที่ทำงานจริงระหว่างเดิน: {len(sweeps)-1} ครั้ง")
print("\n✓ แก้ครบทั้ง 3 ข้อ: กับดักไม่กินของ · ล้าง k.items · สมบัติฟ้าดินไม่มีวันสูญหายจริง")
