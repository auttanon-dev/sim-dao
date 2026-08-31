# -*- coding: utf-8 -*-
"""ตัวตัดสินผลทั้งหมด — โค้ดล้วน ไม่มี LLM"""
import math
import random

from . import config as C
from .models import Character, World
from .skills import GRADE_POWER, ANTI_CHAOS_CUT, SKILLS

SKILL_INDEX = {s[0]: s for s in SKILLS}


# ------------------------------------------------------------------ สายเลือด
def eff(ch: Character, kind: str) -> float:
    """ประสิทธิภาพของเส้นทางเติบโตแต่ละสาย — ยิ่งเลือดผสม ยิ่งทำงานได้ไม่เต็ม"""
    return ch.blood.get(kind, 0.0) ** C.PURITY_EXP


def blood_power(ch: Character) -> float:
    b = ch.blood
    p = b.get("spirit", 0.0) * C.SPIRIT_BASE_W * (0.4 + 0.6 * ch.refine)
    p += b.get("demon", 0.0) * C.DEMON_BASE_W
    p += b.get("mara", 0.0) * C.MARA_BASE_W * (1.0 + min(ch.inner, 6.0) * 0.10)
    return p


def normalize(blood: dict):
    s = sum(blood.values()) or 1.0
    for k in blood:
        blood[k] /= s
    return blood


# ------------------------------------------------------------------ พลัง
def item_power(ch: Character, items, day: int = None) -> float:
    from .treasures import BURST_MULT
    p = 0.0
    for iid in ch.items:
        it = items.get(iid)
        if not it or it.kind == "ยาวิเศษ":
            continue
        p += C.TREASURE_POWER * it.grade * it.condition
        # สมบัติชิ้นเอกปล่อยพลังเต็มได้เมื่อฟื้นพลังครบเท่านั้น
        if it.legend and day is not None and day >= it.ready_day:
            from .treasures import SUPREME
            sup = SUPREME.get(it.name)
            p += (sup["burst"] if sup and "burst" in sup else BURST_MULT) * it.grade * it.condition
    return p


def skill_power(ch: Character) -> float:
    p = 0.0
    for name in ch.skills:
        sk = SKILL_INDEX.get(name)
        if sk:
            p += GRADE_POWER[sk[3]] * (1.0 + 0.2 * sk[2])
    return p


def has_anti_chaos(ch: Character) -> bool:
    return any(SKILL_INDEX.get(n, (0, 0, 0, 0, 0, False))[5] for n in ch.skills)


def power(ch: Character, world: World, items=None, day: int = None) -> float:
    if ch.is_chaos():
        # ตาม SPEC: ความได้เปรียบของโกลาหลต้องมาจาก CHAOS_EDGE (ค่าคงที่) ล้วนๆ ไม่ใช่จากพลังดิบ
        # พลังฐานจึงต้องเทียบเท่ามนุษย์ขั้นสูงสุดพอดี (eff_tier แทน world.tier ตรงๆ ไม่บวกซ้อน)
        # ch.realm ถูกตั้งไว้ที่ REALM_CAP ตั้งแต่เกิดอยู่แล้ว ส่วน chaos_rank เป็นแค่ตัวแปรเล็กๆ
        # ให้แตกต่างกันภายในเผ่าโกลาหลเอง ไม่ใช่พลังก้อนใหญ่ระดับเดียวกับการไต่ขั้นของมนุษย์
        eff_tier = min(C.CHAOS_TIER, world.tier)
        rank = ch.chaos_rank
        if world.tier < C.CHAOS_TIER:      # ลงมาโลกที่ต่ำกว่าถิ่นตัวเอง = ถูกกดเหมือนทุกคน
            rank = max(0, rank - C.CHAOS_DESCEND_PUSH)
        p = (eff_tier * C.TIER_STEP + ch.realm * C.REALM_STEP + rank * 1.0
             + ch.insight * C.INSIGHT_W + blood_power(ch) + skill_power(ch)
             - ch.decay * C.DECAY_W)
        if ch.is_lord:
            p += C.CHAOS_LORD_BONUS + ch.lord_returns * C.LORD_GROWTH
    else:
        p = (world.tier * C.TIER_STEP
             + ch.realm * C.REALM_STEP
             + ch.insight * C.INSIGHT_W
             + blood_power(ch)
             + skill_power(ch)
             - ch.decay * C.DECAY_W)
    if items:
        p += item_power(ch, items, day)
    return p


def chaos_edge(a, b) -> float:
    """มนุษย์แพ้ทางเผ่าโกลาหล — เว้นแต่จะมีวิชาที่แก้ทางได้
    ทาสของเผ่าโกลาหลไม่ถูกแพ้ทาง เพราะมันดีกับคนของมัน"""
    if a.is_chaos() == b.is_chaos():
        return 0.0
    if (a.is_chaos() and b.thrall) or (b.is_chaos() and a.thrall):
        return 0.0
    edge = C.CHAOS_EDGE
    victim = b if a.is_chaos() else a
    if has_anti_chaos(victim):
        edge *= (1.0 - ANTI_CHAOS_CUT)
    return edge if a.is_chaos() else -edge


def array_effects(ch, items):
    from .config import ARRAY_TYPES
    has_array = False
    buffs = {"flag": False, "slate": False, "pegs": False, "pen": False}
    
    for iid in ch.items:
        it = items.get(iid)
        if it and getattr(it, "kind", "") == "อาวุธค่ายกล":
            has_array = True
            if it.name == "ธงค่ายกล": buffs["flag"] = True
            elif it.name == "คัมภีร์เหล็กจารึก": buffs["slate"] = True
            elif it.name == "หมุดตรึงทิศ": buffs["pegs"] = True
            elif it.name == "พู่กันกระดูกอสูร": buffs["pen"] = True
            
    if not has_array:
        return 0.0, None, buffs
        
    best_array = None
    best_power = 0.0
    best_cost = None
    
    for array_name, details in ARRAY_TYPES.items():
        can_cast = True
        cost = details["cost"]
        for mat, amount in cost.items():
            if ch.mat_stock.get(mat, 0) < amount:
                can_cast = False
                break
        if can_cast:
            array_p = 2.0 
            if details["type"] == "DPS": array_p = 3.5
            elif details["type"] == "CC": array_p = 3.0
            
            if array_p > best_power:
                best_power = array_p
                best_array = array_name
                best_cost = cost

    if best_array:
        for mat, amount in best_cost.items():
            ch.mat_stock[mat] -= amount
        
        if buffs["flag"]: best_power *= 1.5 
        if buffs["slate"]: best_power += 1.5 
        if buffs["pegs"]: ch.decay = max(0.0, ch.decay - 1.0) 
        
        return best_power, ARRAY_TYPES[best_array]["type"], buffs
    return 0.0, None, buffs


def resolve_clash(a, b, world, items, rng, day=None):
    p_a = power(a, world, items, day)
    p_b = power(b, world, items, day)
    
    arr_p_a, type_a, buffs_a = array_effects(a, items)
    arr_p_b, type_b, buffs_b = array_effects(b, items)
    
    p_a += arr_p_a
    p_b += arr_p_b
    
    adv = p_a - p_b + chaos_edge(a, b)
    
    if type_a == "DPS": b.decay += 1.0
    if type_b == "DPS": a.decay += 1.0
    
    if type_a == "CC": adv += 1.5
    if type_b == "CC": adv -= 1.5

    if day is not None:                      # ใช้พลังชิ้นเอกแล้วต้องรอฟื้น
        for ch in (a, b):
            for iid in ch.items:
                it = items.get(iid)
                if it and it.legend and day >= it.ready_day:
                    it.ready_day = day + it.cooldown
    p_a = 1.0 / (1.0 + math.exp(-adv / C.TEMP))
    if rng.random() < p_a:
        return a, b, (abs(adv) if adv > 0 else 0.15)
    return b, a, (abs(adv) if adv < 0 else 0.15)


def apply_defeat(sim, world, win, lose, margin, rng, lethal_at=None):
    lethal_at = C.DEATH_MARGIN if lethal_at is None else lethal_at
    lethal_at *= (1.0 - C.DANGER_PER_TIER) ** world.tier     # โลกสูงยิ่งอันตราย
    lose.decay += C.DECAY_PER_FIGHT * (1.0 + margin) / (1.0 + 0.25 * lose.realm)
    win.decay += C.DECAY_PER_FIGHT * 0.4 / (1.0 + 0.25 * win.realm)
    if margin >= lethal_at:
        from .treasures import SUPREME
        for iid in lose.items:
            it = sim.items.get(iid)
            if it and it.legend and SUPREME.get(it.name, {}).get("revive") \
                    and sim.day >= it.ready_day:
                it.ready_day = sim.day + it.cooldown
                lose.decay = max(0.0, lose.decay - 1.0)
                lose.near_death += 1
                return f"รอดด้วย{it.name}"
        if lose.fate > 0:
            lose.fate -= 1
            lose.near_death += 1
            lose.decay += 0.8
            return "รอดตายด้วยชะตา"
        sim.kill(lose, f"ถูก{win.name}สังหาร", killer=win)
        return "ตาย"
    if margin >= 0.6:
        lose.near_death += 1
    return "พ่ายแพ้"


# ------------------------------------------------------------------ จิตมาร
def add_debt(ch: Character, kind: str, target: int, name: str, day: int):
    if ch.inner_none:
        return
    ch.debts.append(dict(kind=kind, target=target, name=name, day=day, done=False))
    ch.inner += C.DEBT_WEIGHT.get(kind, 1.0)


def settle_debt(ch: Character, target: int) -> bool:
    """สะสางเรื่องค้างคากับคนคนหนึ่ง — จิตมารคลาย"""
    found = False
    for d in ch.debts:
        if not d["done"] and d["target"] == target:
            d["done"] = True
            ch.inner = max(0.0, ch.inner - C.DEBT_WEIGHT.get(d["kind"], 1.0))
            found = True
    return found


def inner_trial(ch: Character, world: World, rng):
    """ด่านจิตมาร แยกจากด่านพลัง — คืน (ผ่าน/กดไว้/พ่าย)"""
    if ch.inner_none:
        return "ไร้จิตมาร"
    strength = ch.inner * C.INNER_TRIAL_W + C.INNER_PER_REALM * ch.realm
    if ch.inner_art:
        strength *= C.INNER_ART_RISK
    resist = ch.insight + ch.refine * 2.0 + 2.0
    p = resist / (resist + strength)
    r = rng.random()
    if r < p:
        return "ผ่าน"
    if r < p + (1.0 - p) * 0.55:
        return "กดไว้"
    return "พ่าย"


# ------------------------------------------------------------------ เลื่อนขั้น
def accumulation(ch: Character) -> float:
    return ch.insight + ch.refine * 3.0


def need(ch: Character, world: World) -> float:
    base = C.NEED_BASE + C.NEED_PER_REALM * ch.realm
    return base * (1.0 - C.PURITY_PER_TIER) ** world.tier


def attempt_break(sim, ch: Character, world: World, rng, pills=0):
    """คืน (ผลลัพธ์, ข้อความ) — ต้องผ่านสองด่าน พลัง แล้วก็จิตมาร"""
    if ch.realm >= C.REALM_CAP:
        return "ตัน", "ตันขั้นสูงสุดของโลกนี้แล้ว"
    req = need(ch, world)
    acc = accumulation(ch)
    if acc < req:
        return "ยังไม่ถึง", ""

    cost = C.BREAK_COST * (ch.realm + 1) ** 2
    scarce = 1.0 if world.heaven >= cost else max(0.15, world.heaven / max(cost, 1e-6))

    p = C.BREAK_BASE_P
    p += (acc - req) * C.SURPLUS_BONUS
    p -= ch.decay * C.DECAY_PENALTY
    p += pills * C.PILL_BREAK_BONUS
    p += C.PURITY_PER_TIER * world.tier
    p *= scarce                                  # คลังฟ้าพร่อง = ไต่ยากขึ้นทั้งโลก
    p -= 0.04 * ch.realm                         # ฟ้ากดคนที่ขึ้นสูง
    p = max(0.03, min(0.95, p))

    ch.insight = max(0.0, ch.insight - req * 0.8)
    ch.refine = max(0.0, ch.refine - req * 0.2 / 3.0)

    if rng.random() > p:
        ch.fails += 1
        ch.decay += C.BACKLASH_DECAY * 0.5
        return "ล้มเหลว", f"{ch.name}ล้มเหลวในการข้ามขั้น การสะสมสูญเปล่า"

    trial = inner_trial(ch, world, rng)
    if trial == "พ่าย":
        ch.blood["mara"] = ch.blood.get("mara", 0.0) + C.INNER_FALL_MARA
        normalize(ch.blood)
        ch.decay += C.BACKLASH_DECAY
        ch.inner += 1.0
        if rng.random() < 0.25 and ch.fate <= 0:
            sim.kill(ch, "จิตมารกลืนกินจนดับสูญ")
            return "จิตมารกลืน", f"{ch.name}พ่ายต่อจิตมารของตัวเอง สิ้นใจคาที่"
        return "จิตมารกลืน", f"{ch.name}พ่ายต่อจิตมาร ส่วนมารในตัวลุกลาม"
    if trial == "กดไว้":
        ch.inner += 0.5
        ch.decay += 0.4

    # ------------------------------------------------
    # Heavenly Tribulation (ทัณฑ์สวรรค์)
    # ------------------------------------------------
    tribulation_msg = ""
    # Spirit bloodline does not face Tribulation (they cultivate bloodline natively)
    if not getattr(ch, "is_spirit", False):
        if ch.realm + 1 in [4, 7, 9]:
            tribulation_msg = f"\n⚡ [ทัณฑ์สวรรค์] ฟ้าดินพิโรธ! ส่งสายฟ้าฟาดฟัน {ch.name} เพื่อหยุดยั้งการเบิกมรรค!"
            
            # Massive damage based on the realm they are trying to reach
            trib_dmg = (ch.realm + 1) * 30
            
            # Survival mechanics
            hp_pool = getattr(ch, "hp", 100)
            if hp_pool <= trib_dmg:
                # Fail the breakthrough because they couldn't endure it
                ch.hp = 1
                ch.decay += C.BACKLASH_DECAY * 2.0
                return "บาดเจ็บสาหัส", tribulation_msg + f"\n -> ❌ {ch.name} ทนรับทัณฑ์สวรรค์ไม่ไหว บาดเจ็บปางตาย การทะลวงขั้นล้มเหลว!"
            else:
                ch.hp -= trib_dmg
                tribulation_msg += f"\n -> 🛡️ {ch.name} ทนรับทัณฑ์สวรรค์สำเร็จ! (สูญเสีย HP {trib_dmg})"

    # สำเร็จ — ถอนพลังจากคลังฟ้า
    take = min(cost, world.heaven)
    world.heaven -= take
    ch.drawn += take
    ch.realm += 1
    if ch.realm == 1:
        world.n_mortal -= 1
    ch.breaks += 1
    ch.peak_realm = max(ch.peak_realm, ch.realm)
    ch.decay = max(0.0, ch.decay - 0.5)
    if ch.inner_art:
        ch.inner += C.INNER_ART_BONUS
    note = {"ผ่าน": "ข้ามด่านจิตมารได้", "กดไว้": "กดจิตมารไว้ได้แต่ยังค้าง",
            "ไร้จิตมาร": "ไร้จิตมารขวางทาง"}[trial]
    if trial == "ผ่าน":
        ch.insight += 1.0

    tribulation = ""
    if ch.tier <= 0 and (ch.realm + 1) in C.MORTAL_REALMS_CONFIG:
        t = C.MORTAL_REALMS_CONFIG[ch.realm + 1]["tribulation"]
        if t != "ไม่มี":
            tribulation = f" ฝ่าวิกฤต [{t}]"
    return "ผ่าน", f"{ch.name}เลื่อนเป็น{ch.realm_name()} ({note}){tribulation}"


# ------------------------------------------------------------------ บัญชีฟ้า
def heaven_inflow(world: World, mortals: int, elapsed_days: int):
    """เกิด แก่ เจ็บ — สามัญชนให้น้อยแต่ให้ทุกปี"""
    years = elapsed_days / 365.0
    world.heaven = min(world.cap(), world.heaven + mortals * C.LIFE_INFLOW * years)
    world.rift = max(0.0, world.rift - years * C.RIFT_HEAL_PER_YEAR)


def death_return(world: World, ch: Character, natural: bool):
    """ผู้บำเพ็ญตายคืนพลังมาก เพราะสะสมไว้เยอะ
    แต่ถูกฆ่ากลางคันคืนได้แค่เศษ เพราะวงจรชีวิตถูกตัดขาด"""
    rate = C.NATURAL_RETURN if natural else C.KILLED_RETURN
    world.heaven = min(world.cap(), world.heaven + ch.drawn * rate)
    ch.drawn = 0.0


# ------------------------------------------------------------------ ความเสื่อม
def age_and_decay(sim, ch: Character, world: World, gap_days: int, rng):
    years = gap_days / 365.0
    ch.decay += years * C.DECAY_PER_YEAR * (1.0 + C.DECAY_PER_REALM_MULT * ch.realm)
    # โลกต่ำหล่อเลี้ยงคนที่เกินขั้นไม่ได้
    over = ch.realm - (C.SUPPORTED_REALM + world.tier * 2)
    if over > 0:
        ch.decay += years * C.OVERPOWER_DRAIN * over
    if ch.decay >= C.REGRESS_AT and ch.realm > 0:
        ch.realm -= 1
        if ch.realm == 0:
            world.n_mortal += 1
        ch.decay -= C.REGRESS_AT * 0.6
    if ch.age(sim.day) > ch.lifespan():
        sim.kill(ch, "สิ้นอายุขัย", natural=True)


def cultivate(ch: Character, gap_days: int):
    yrs = min(4.0, gap_days / 365.0)
    ch.decay = max(0.0, ch.decay - C.CULTIVATE_HEAL)
    ch.insight += 0.45 * yrs * eff(ch, "human")
    ch.refine += 0.10 * yrs * eff(ch, "spirit")


def refine_blood(ch: Character, gap_days: int):
    yrs = min(4.0, gap_days / 365.0)
    ceiling = ch.blood.get("spirit", 0.0)
    ch.refine = min(ceiling, ch.refine + 0.18 * yrs * eff(ch, "spirit"))


# ------------------------------------------------------------------ ยุค / โลก
def check_world(sim, world: World, rng):
    if world.ratio() > C.COLLAPSE_RATIO:
        # เสื่อมได้ก็ฟื้นได้ — คลังเต็มนานพอ โลกไต่ระดับกลับขึ้น
        if (world.ratio() >= C.RECOVER_RATIO and world.tier + 1 < len(C.TIER_NAMES)
                and world.kind == "mortal" and rng.random() < C.RECOVER_P):
            world.tier += 1
            world.era += 1
            world.heaven = world.cap() * 0.8
        return None
    notes = []
    for ch in sim.living_in(world.wid):
        if rng.random() < C.ERA_CULL_P * (0.4 + 0.12 * ch.realm):
            sim.kill(ch, f"ดับสูญไปกับยุคที่ {world.era}", natural=True)
            notes.append(ch.name)
        else:
            ch.realm = max(0, ch.realm - C.ERA_PUSHDOWN)
    for ch in sim.living_in(world.wid):
        ch.tier = world.tier
        ch.peak_tier = max(ch.peak_tier, ch.tier)
    world.n_mortal = sum(1 for c in sim.living_in(world.wid) if c.realm == 0)
    world.n_alive = len(sim.living_in(world.wid))
    if world.tier > 0:
        world.tier -= 1          # โลกที่เสื่อมกลายเป็นโลกระดับต่ำลง
    world.heaven = world.cap() * 0.7
    world.era += 1
    return notes


def seal_left(cache, day: int) -> float:
    yrs = (day - cache.sealed_day) / 365.0
    return cache.seal - yrs * C.SEAL_DECAY_PER_YEAR


def mara_seal_state(sim) -> dict:
    """ประเมินสถานะของมหาผนึกหมื่นมารสะกดโลก"""
    seal = getattr(sim, "mara_seal", getattr(C, "MARA_SEAL_INITIAL", 100.0))
    broken = getattr(sim, "mara_seal_broken", False)
    if broken or seal <= getattr(C, "MARA_SEAL_BROKEN_THRESHOLD", 0.0):
        status = "พังทลาย (สัญจรข้ามแดนได้สมบูรณ์)"
    elif seal <= getattr(C, "MARA_SEAL_WEAK_THRESHOLD", 30.0):
        status = "สั่นคลอน (ไอปีศาจรั่วไหล)"
    else:
        status = "แน่นหนา (ข้ามผ่านไม่ได้)"
    return {"seal": round(seal, 2), "broken": broken, "status": status}
