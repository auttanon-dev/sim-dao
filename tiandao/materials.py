# -*- coding: utf-8 -*-
"""โซ่วัตถุดิบ — ผูก "ของชิ้นไหน" เข้ากับ "ที่ไหน" และ "สูตรอะไร"

ก่อนหน้านี้วัตถุดิบในซิมเป็นตัวเลขก้อนเดียว (Character.mats) วัตถุดิบทุกชนิดแทนกันได้หมด
ผลคือไม่เคยมีใครต้องการ *ของชิ้นใดชิ้นหนึ่ง* จึงไม่มีวันเกิดการแย่งชิง ไม่มีการค้าที่มีความหมาย
และไม่มีเหตุผลจะเดินทางไปที่ใดที่หนึ่งเป็นการเฉพาะ

โมดูลนี้เติมสามอย่างที่ขาด:
  1. วัตถุดิบแต่ละชนิดมี "ระดับโลก" ของมัน และขึ้นเฉพาะสถานที่ที่คู่ควร
     (เดิม sim สุ่มจากตารางราคาทั้งก้อน ถ้ำหินแกรนิตดิบในโลกมนุษย์จึงออกแร่ระดับสวรรค์ได้)
  2. ทุกสูตรยา/อาวุธต้องการวัตถุดิบ *ชนิดเฉพาะ* ไม่ใช่ "วัตถุดิบ 3 หน่วย"
  3. ค้นย้อนได้ว่าของชิ้นนี้หาได้ที่ไหนบ้าง — เพื่อให้เจตนา (intent.py) รู้ว่าควรเดินไปทางไหน

ทุกอย่างเป็นตัวเลขล้วน ไม่มี LLM
"""
import hashlib

from . import crafting as CR
from . import places as PL

# ---------------------------------------------------------------- ระดับของวัตถุดิบ
# ORES/HERBS ใน crafting.py มี tier ติดมาอยู่แล้ว แต่ไม่เคยถูกใช้ที่ไหนเลย — ใช้ตรงนี้
MAT_TIER = {}
MAT_KIND = {}
for _name, _t in CR.ORES:
    MAT_TIER[_name] = _t
    MAT_KIND[_name] = "แร่"
for _name, _t in CR.HERBS:
    MAT_TIER[_name] = _t
    MAT_KIND[_name] = "สมุนไพร"

# ของที่หล่นจากอสูร ไม่ผูกกับสถานที่ ใช้ได้ทุกระดับ
BEAST_MATS = ("โลหิตอสูรกลั่น", "ศิลาปราณห้าธาตุ")
for _name in BEAST_MATS:
    MAT_TIER.setdefault(_name, 0)
    MAT_KIND.setdefault(_name, "แก่นพลัง")

# world_key ใน PLACES -> ระดับวัตถุดิบที่ขึ้นแถวนั้น
WORLD_MAT_TIER = {0: 0, "siam": 0, "mara": 0, "abyss": 0, "ocean": 0, 1: 1, 2: 2, "chaos": 2}
# แดนเซียนสาขาทุกแดนอยู่ชั้นเดียวกับแดนเซียน — ต้องใส่ให้ครบ ไม่งั้น .get(key, 0) จะตกไปเป็น
# ชั้น 0 เงียบๆ แล้วเหมืองในแดนเซียนสาขาจะขุดได้แต่แร่ระดับโลกมนุษย์ทั้งที่เป็นแดนเซียน
WORLD_MAT_TIER.update({k: 1 for k in PL.BRANCH_PLACE_KEYS})


def price_of(name):
    return PL.ORE_PRICE.get(name) or PL.HERB_PRICE.get(name) or 100.0


def _sorted_pool(kind, tier):
    """วัตถุดิบชนิดนั้นระดับนั้น เรียงจากถูกไปแพง (แพง = หายาก)"""
    pool = [n for n, t in MAT_TIER.items()
            if t == tier and MAT_KIND.get(n) == kind and n not in BEAST_MATS]
    pool.sort(key=price_of)
    return pool


# ---------------------------------------------------------------- ของขึ้นที่ไหน
# เกรดของสถานที่คุมว่าของหายากแค่ไหนที่โผล่ที่นี่ได้ (0 = ที่ธรรมดา, 2 = แหล่งชั้นเลิศ)
GRADE_DEPTH = {0: 2, 1: 4, 2: 5}


def materials_at(place_idx):
    """คืนรายชื่อวัตถุดิบที่เก็บได้จริงที่สถานที่นี้ (เรียงจากพบง่ายไปพบยาก)"""
    if place_idx is None or place_idx < 0 or place_idx >= len(PL.PLACES):
        return []
    p = PL.PLACES[place_idx]
    kind = p[4]
    if kind not in ("แร่", "สมุนไพร"):
        return []
    tier = WORLD_MAT_TIER.get(p[1], 0)
    pool = _sorted_pool(kind, tier)
    return pool[:GRADE_DEPTH.get(p[2], 2)]


def is_core_site(place_idx):
    """แหล่ง 'แก่นพลัง' — ล่าอสูรเอาแก่นได้ แต่ไม่มีแร่/สมุนไพรให้เก็บ"""
    if place_idx is None or place_idx < 0 or place_idx >= len(PL.PLACES):
        return False
    return PL.PLACES[place_idx][4] == "แก่นพลัง"


def core_sites(world_key=None):
    return [i for i, p in enumerate(PL.PLACES)
            if p[4] == "แก่นพลัง" and (world_key is None or p[1] == world_key)]


def harvestable(place_idx):
    """ที่นี่มีอะไรให้ 'ออกไปเก็บ' ไหม — แร่/สมุนไพร หรือแก่นพลัง"""
    return bool(materials_at(place_idx)) or is_core_site(place_idx)


def roll_material(place_idx, rng, eco=1.0):
    """สุ่มของหนึ่งชิ้นจากที่นี่ — ของแพงออกยากกว่า และแหล่งที่ร่อยหรอยิ่งออกแต่ของถูก"""
    pool = materials_at(place_idx)
    if not pool:
        return None
    # น้ำหนักลดหลั่นตามลำดับความหายาก แล้วบีบเพิ่มเมื่อ eco ต่ำ
    weights = []
    for i in range(len(pool)):
        w = (0.55 ** i)
        if i > 0:
            w *= max(0.05, eco)
        weights.append(w)
    total = sum(weights)
    r, acc = rng.random() * total, 0.0
    for name, w in zip(pool, weights):
        acc += w
        if r <= acc:
            return name
    return pool[0]


# ---------------------------------------------------------------- ของชิ้นนี้หาได้ที่ไหน
_SOURCES = None


def sources_of(mat):
    """index ของสถานที่ทั้งหมดที่วัตถุดิบชิ้นนี้ขึ้น"""
    global _SOURCES
    if _SOURCES is None:
        _SOURCES = {}
        for idx in range(len(PL.PLACES)):
            for m in materials_at(idx):
                _SOURCES.setdefault(m, []).append(idx)
    return _SOURCES.get(mat, ())


def sources_in_world(mat, world_key):
    return [i for i in sources_of(mat) if PL.PLACES[i][1] == world_key]


# ---------------------------------------------------------------- สูตรต้องใช้อะไร
def _stable_rand(seed_text, n):
    """ลำดับตัวเลข 0..1 ที่เหมือนเดิมทุกครั้งสำหรับข้อความเดียวกัน — สูตรจะได้ไม่เปลี่ยนไปมาระหว่างรัน"""
    out = []
    h = hashlib.sha256(seed_text.encode("utf-8")).digest()
    while len(out) < n:
        for i in range(0, len(h) - 1, 2):
            out.append(int.from_bytes(h[i:i + 2], "big") / 65535.0)
            if len(out) >= n:
                break
        h = hashlib.sha256(h).digest()
    return out


def _build_recipe_mats():
    """ผูกวัตถุดิบเข้ากับทุกสูตรแบบคงที่ (hash ของชื่อสูตร) — เกรดสูงใช้ของหลากหลายและมากขึ้น

    ของ "(ธรรมชาติ)" คือการกลั่นสมบัติธรรมชาติ จึงบังคับให้ต้องมีตัวมันเองเป็นแกน
    """
    table = {}
    for is_pill, rows in ((True, CR.PILLS), (False, CR.WEAPONS)):
        kind = "สมุนไพร" if is_pill else "แร่"
        for row in rows:
            name, tier, grade = row[0], row[1], row[2]
            pool = _sorted_pool(kind, tier)
            if not pool:
                continue
            need = []
            base = name.replace(" (ธรรมชาติ)", "")
            if base != name and base in MAT_TIER:
                need.append((base, 1 + grade // 2))
            n_kinds = (1 + grade) - len(need)
            if n_kinds > 0:
                rolls = _stable_rand(name, n_kinds * 2)
                # ของสามัญทำจากของสามัญ — ช่วงที่หยิบได้กว้างขึ้นตามเกรด และล้อกับ GRADE_DEPTH
                # ของแหล่ง เพื่อให้สูตรเกรดต่ำหาวัตถุดิบได้จากแหล่งธรรมดาจริงๆ
                span = pool[:GRADE_DEPTH.get(grade, len(pool))] or pool
                picked = []
                for j in range(n_kinds):
                    idx = int(rolls[j * 2] * len(span)) % len(span)
                    for _ in range(len(span)):
                        cand = span[idx]
                        if cand not in picked and all(cand != m for m, _q in need):
                            break
                        idx = (idx + 1) % len(span)
                    picked.append(span[idx])
                    qty = 1 + int(rolls[j * 2 + 1] * grade)
                    need.append((span[idx], qty))
            if grade >= 2 and pool and all(m != pool[-1] for m, _q in need):
                need.append((pool[-1], 1))     # ของชั้นยอดต้องมีของหายากที่สุดของระดับนั้นเป็นแกน
            # ของสายสวรรค์ต้องใช้แก่นอสูรกลั่นด้วย ไม่ใช่แค่แร่กับหญ้า
            if tier >= 1 and grade >= 1:
                need.append(("โลหิตอสูรกลั่น", 1))
            table[name] = need
    return table


RECIPE_MATS = _build_recipe_mats()


def recipe_mats(recipe_name):
    return RECIPE_MATS.get(recipe_name, ())


def shortfall(mat_stock, reqs):
    """ขาดอะไรอยู่บ้าง — dict ชื่อของ -> จำนวนที่ยังขาด (ว่าง = ครบแล้ว)"""
    lack = {}
    for name, qty in reqs:
        have = mat_stock.get(name, 0)
        if have < qty:
            lack[name] = qty - have
    return lack


def can_afford(mat_stock, reqs):
    return not shortfall(mat_stock, reqs)


def consume(mat_stock, reqs):
    for name, qty in reqs:
        left = mat_stock.get(name, 0) - qty
        if left > 0:
            mat_stock[name] = left
        else:
            mat_stock.pop(name, None)


def describe(reqs):
    return " + ".join(f"{n}×{q}" for n, q in reqs)


def useful_for(is_pill, rank, tier_cap):
    """วัตถุดิบที่ "สายนี้ ระดับนี้" ใช้ได้จริง — แยกสายยากับสายอาวุธออกจากกัน

    สำคัญ: นักปรุงยาใช้สมุนไพร ช่างตีเหล็กใช้แร่ ถ้าเช็ครวมกัน ช่างที่เพิ่งเก็บสมุนไพรมาเต็มถุง
    จะถูกนับว่า "มีของแล้ว" แล้วไปยืนหลอมอาวุธซึ่งต้องใช้แร่ จบด้วยขาดวัตถุดิบทุกครั้ง
    """
    if rank is None or rank < 0:
        rank = 0
    keep = set()
    for row in (CR.PILLS if is_pill else CR.WEAPONS):
        name, tier, grade = row[0], row[1], row[2]
        if tier > tier_cap or not CR.can_make(rank, tier, grade):
            continue
        for m, _q in recipe_mats(name):
            keep.add(m)
    return keep


def useful_to(rank_pill, rank_forge, tier_cap):
    """ชุดวัตถุดิบที่ "ช่างระดับนี้ใช้ได้จริง" — ใช้ตัดสินว่าอะไรควรเก็บไว้ อะไรขายได้

    ก่อนหน้านี้ ค้าขาย ขายทุกอย่างที่ไม่ได้อยู่ใน wants ทิ้งหมด และ wants จะถูกตั้งก็ต่อเมื่อ
    "หลอมพลาดไปแล้ว" เท่านั้น ผลคือช่างเก็บสมุนไพรมาแล้วเอาไปขายก่อนจะได้ใช้ วนอยู่แบบนี้
    ทั้งชีวิต — วัดจริงคือขายบ่อยเป็นสองเท่าของการออกเก็บ
    """
    keep = set()
    for is_pill, ranks in ((True, rank_pill), (False, rank_forge)):
        if ranks is None or ranks < 0:
            continue
        rows = CR.PILLS if is_pill else CR.WEAPONS
        for row in rows:
            name, tier, grade = row[0], row[1], row[2]
            if tier > tier_cap or not CR.can_make(ranks, tier, grade):
                continue
            for m, _q in recipe_mats(name):
                keep.add(m)
    return keep


def can_craft_now(mat_stock, is_pill, rank, tier_cap, furnace):
    """มีของครบสำหรับสูตรใดสูตรหนึ่งที่ทำได้ ณ เตานี้ไหม — เงื่อนไขเดียวกับที่ handler ตรวจเป๊ะ

    ถ้าเจตนาเช็คแค่ "มีวัตถุดิบสายนี้อยู่บ้าง" ตัวละครจะยังเดินไปยืนหน้าเตาทั้งที่ของไม่ครบสูตร
    แล้วจบด้วย "ขาดวัตถุดิบ" — เสียเทิร์นที่มีอยู่ราว 30 ครั้งต่อชีวิตไปเปล่าๆ
    """
    if rank is None or rank < 0:
        rank = 0
    for row in (CR.PILLS if is_pill else CR.WEAPONS):
        name, tier, grade = row[0], row[1], row[2]
        if tier > tier_cap or tier > furnace or not CR.can_make(rank, tier, grade):
            continue
        if can_afford(mat_stock, recipe_mats(name)):
            return True
    return False


def plan_shortfall(mat_stock, is_pill, rank, tier_cap):
    """ของที่ยังขาดสำหรับสูตรที่ "ใกล้จะทำได้ที่สุด" ในสายนี้ — ใช้ตั้งเป้าว่าจะไปหาอะไร

    เดิม ch.wants ถูกตั้งตอน handler หลอมพลาดเท่านั้น พอเจตนาฉลาดขึ้นจนไม่เดินไปหลอมทั้งที่
    ของไม่ครบ ความล้มเหลวก็หายไป และ wants ก็ไม่เคยถูกตั้งอีกเลย — ระบบตามหาวัตถุดิบตายไปด้วย
    ตัวนี้ย้ายการคิดว่า "ยังขาดอะไร" มาไว้ก่อนลงมือ แทนที่จะรอให้พลาดก่อน
    """
    if rank is None or rank < 0:
        rank = 0
    best = None
    for row in (CR.PILLS if is_pill else CR.WEAPONS):
        name, tier, grade = row[0], row[1], row[2]
        if tier > tier_cap or not CR.can_make(rank, tier, grade):
            continue
        lack = shortfall(mat_stock, recipe_mats(name))
        if not lack:
            return name, {}
        score = (sum(lack.values()), -(tier * 3 + grade))
        if best is None or score < best[0]:
            best = (score, name, lack)
    if best is None:
        return None, {}
    return best[1], best[2]


# ---------------------------------------------------------------- เครื่องมือค่ายกล
# ARRAY_TYPES (config) คือ "ค่ายกลที่กางออกมา" ซึ่งกิน mat_stock ตอนสู้อยู่แล้ว (rules.array_effects)
# ส่วน ARRAY_WEAPON_KINDS คือ "เครื่องมือ" ที่ต้องหลอมขึ้นมาก่อน — เดิมหลอมด้วย Character.mats
# ซึ่งเป็นตัวเลขก้อนเดียว จึงเป็นสายเดียวที่ยังไม่ได้ต่อเข้าโซ่วัตถุดิบ
ARRAY_TOOL_MATS = {
    "ธงค่ายกล":          [("ศิลาปราณห้าธาตุ", 2)],                        # ผืนธงต้องมีปราณห้าธาตุคุมทิศ
    "คัมภีร์เหล็กจารึก":  [("__ore__", 2)],                                # แผ่นเหล็กจารึกอักขระ
    "พู่กันกระดูกอสูร":   [("โลหิตอสูรกลั่น", 2)],                        # ด้ามทำจากกระดูกและโลหิตอสูร
    "หมุดตรึงทิศ":        [("__ore__", 2), ("ศิลาปราณห้าธาตุ", 1)],       # หมุดเหล็กตอกยึดผังค่ายกล
}


def array_mats(tool_name, tier):
    """วัตถุดิบของเครื่องมือค่ายกลชิ้นหนึ่ง — "__ore__" แทนแร่สามัญที่สุดของระดับโลกนั้น"""
    ores = _sorted_pool("แร่", tier)
    common = ores[0] if ores else None
    out = []
    for name, qty in ARRAY_TOOL_MATS.get(tool_name, ()):
        if name == "__ore__":
            if common is None:
                continue
            name = common
        out.append((name, qty))
    return out


def array_tools_ready(mat_stock, tier):
    """เครื่องมือค่ายกลที่ทำได้ตอนนี้ (ของครบ)"""
    return [t for t in ARRAY_TOOL_MATS if can_afford(mat_stock, array_mats(t, tier))]


def plan_array_shortfall(mat_stock, tier):
    """เครื่องมือค่ายกลที่ใกล้จะทำได้ที่สุด และของที่ยังขาด"""
    best = None
    for t in ARRAY_TOOL_MATS:
        lack = shortfall(mat_stock, array_mats(t, tier))
        if not lack:
            return t, {}
        n = sum(lack.values())
        if best is None or n < best[0]:
            best = (n, t, lack)
    return (best[1], best[2]) if best else (None, {})


# ---------------------------------------------------------------- เตาหลอมประจำถิ่น
# crafting.FURNACES นิยามเตาไว้ 9 ชนิดพร้อมระดับและเกรด แต่ไม่เคยถูกอ่านที่ไหนเลย —
# ระบบใช้แค่ตัวเลขระดับใน PLACES[5] ทำให้ทุกเตาในโลกเหมือนกันหมดและไม่มีชื่อ
_FURNACE_AT = {}


def furnace_of(place_idx):
    """เตาประจำสถานที่นี้ — (ชื่อ, ระดับ, เกรด) หรือ None ถ้าที่นี่ไม่มีเตา

    เลือกแบบคงที่จาก index ของสถานที่ เตาจึงเป็นของประจำถิ่นจริง ไม่เปลี่ยนไปมาทุกครั้งที่หลอม
    """
    if place_idx is None or place_idx < 0 or place_idx >= len(PL.PLACES):
        return None
    if place_idx in _FURNACE_AT:
        return _FURNACE_AT[place_idx]
    p = PL.PLACES[place_idx]
    lv = p[5]
    if lv is None or lv < 0:
        _FURNACE_AT[place_idx] = None
        return None
    pool = [f for f in CR.FURNACES if f[1] == lv]
    if not pool:
        pool = sorted(CR.FURNACES, key=lambda f: abs(f[1] - lv))[:1]
    # แหล่งสมุนไพร/สำนักยาควรได้ "หม้อปรุงยา" ส่วนเมืองแร่/สำนักช่างควรได้ "เตาหลอม"
    want_pot = p[4] == "สมุนไพร"
    matched = [f for f in pool if f[0].startswith("หม้อ") == want_pot]
    if matched:
        pool = matched
    # เกรดของสถานที่ชี้ว่าควรได้เตาดีแค่ไหนในบรรดาเตาระดับเดียวกัน
    pool.sort(key=lambda f: f[2])
    idx = min(len(pool) - 1, int(p[2] * len(pool) / 3))
    # กระจายไม่ให้ทุกที่ได้เตาชื่อเดียวกัน โดยยังคงที่ต่อสถานที่
    same = [f for f in pool if f[2] == pool[idx][2]]
    chosen = same[place_idx % len(same)]
    _FURNACE_AT[place_idx] = chosen
    return chosen


# ---------------------------------------------------------------- ชิ้นส่วนหายากจากซากอสูร
# config.MATERIAL_KINDS มีของ 10 อย่าง แต่มีแค่ 2 อย่างที่ระบบใช้จริง (ศิลาปราณห้าธาตุ /
# โลหิตอสูรกลั่น) ที่เหลือเป็นชิ้นส่วนอสูรที่ไม่มีทางใดได้มาเลย — ให้เป็นของหล่นจากการล่า
try:
    from . import config as _C
    BEAST_PARTS = tuple(x for x in _C.MATERIAL_KINDS if x not in MAT_TIER)
except Exception:      # pragma: no cover
    BEAST_PARTS = ()

BEAST_PART_PRICE = 1200.0     # ราคากลางของชิ้นส่วนอสูร (อยู่ระหว่างแร่กลางกับแร่ดี)


def market_price(name):
    """ราคาที่ตลาดรับซื้อ — ครอบคลุมทั้งแร่ สมุนไพร และชิ้นส่วนอสูร (0 = ขายไม่ได้)"""
    p = PL.ORE_PRICE.get(name) or PL.HERB_PRICE.get(name)
    if p:
        return p
    if name in BEAST_PARTS:
        return BEAST_PART_PRICE
    return 0.0


_SITES_CACHE = {}


def sites_of(name):
    """สถานที่ทั้งหมดที่วัตถุดิบชิ้นนี้ขึ้นได้ — ผกผันของ materials_at

    ใช้หาปริมาณสำรองที่เหลือของของชิ้นหนึ่ง (ดู sim.reserve_frac และกฎของ Hotelling)
    ตารางสถานที่คงที่ตลอดการรัน จึงสร้างดัชนีครั้งเดียวแล้วใช้ซ้ำได้
    """
    if not _SITES_CACHE:
        for idx in range(len(PL.PLACES)):
            for n in materials_at(idx):
                _SITES_CACHE.setdefault(n, []).append(idx)
    return _SITES_CACHE.get(name, ())
