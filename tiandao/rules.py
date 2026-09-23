# -*- coding: utf-8 -*-
"""ตัวตัดสินผลทั้งหมด — โค้ดล้วน ไม่มี LLM"""
import math
import random

from . import config as C
from . import physics as PHYS
from . import elements as EL
from . import body as BODY
from .models import Character, World
from .skills import GRADE_POWER, ANTI_CHAOS_CUT, SKILLS

SKILL_INDEX = {s[0]: s for s in SKILLS}


# คำสาบานตามสายของผู้พูด — "ให้คำมั่นสัญญา" เป็นคำของชาวบ้าน ผู้ฝึกตนสาบานต่อจิตเต๋าของตัวเอง
# สายพุทธะสาบานต่อจิตพุทธะ อสูรให้คำสัตย์ต่อจิตอสูร คำสาบานจึงบอกว่าผู้พูดเป็นใครโดยไม่ต้องอธิบาย
BUDDHA_DAO = frozenset({"วิถีความว่าง", "วิถีตันตระวัชระ"})
OATH_MORTAL = "ให้คำมั่นสัญญา"


def oath_form(ch) -> str:
    """คำสาบานที่ตัวละครคนนี้ใช้ — ใช้ทั้งในข้อความเหตุการณ์ พรอมต์ และเรื่องเล่า"""
    race = ch.race() if hasattr(ch, "race") else ""
    if race in ("เผ่าโกลาหล", "ทาสโกลาหล"):
        return "ให้คำสัตย์ต่อจิตโกลาหล"
    if race in ("มารแท้", "มนุษย์มาร") or race.startswith("มารผสม"):
        return "สาบานต่อจิตมาร"          # เลือดมารมีจิตมารของตัวเอง ไม่ใช่จิตอสูร
    if race in ("อสูร",) or race.startswith("อสูรผสม") or getattr(ch, "is_beast", False):
        return "ให้คำสัตย์ต่อจิตอสูร"
    if race == "สัตว์วิญญาณ":
        return "ให้คำสัตย์ต่อจิตวิญญาณบรรพกาล"
    if getattr(ch, "dao", "") in BUDDHA_DAO:
        return "ให้คำมั่นต่อจิตพุทธะ"
    if getattr(ch, "dao", "") == "วิถีคำสัตย์":
        return "สาบานด้วยวิถีคำสัตย์ของตน"
    if getattr(ch, "realm", 0) >= 1:
        return "สาบานต่อจิตเต๋า"
    return OATH_MORTAL


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
    """พลังจากวิชาที่รู้ — สายมิติกับสายเวลาให้มากกว่าสายอื่นหลายเท่า

    เพราะสองสายนี้ไม่ได้ใช้พลังภายใต้กฎของโลกเหมือนสายอื่น แต่แตะตัวกฎเอง (ย่นระยะทาง ·
    พับผืนฟ้า · หน่วงเวลา · ตรึงกาล) และวิชาทั้งหมดของสองสายอยู่ tier 1 ขึ้นไปซึ่งคนโลกมนุษย์
    เรียนตรงๆ ไม่ได้เลย วัดจริงที่ปีที่ 946: ทั้งจักรวาลมีคนรู้สายมิติ 3 คนจากคนเป็น 3,700 คน
    ถ้าผลตอบแทนเท่าสายทั่วไป การไต่ขึ้นไปเรียนก็ไม่มีเหตุผลให้ทำเลย
    """
    p = 0.0
    mast = getattr(ch, "mastery", None) or {}
    for name in ch.skills:
        sk = SKILL_INDEX.get(name)
        if sk:
            w = GRADE_POWER[sk[3]] * (1.0 + 0.2 * sk[2])
            if sk[1] in C.RARE_LINES:
                w *= C.RARE_LINE_MULT
            # ความชำนาญ: รู้วิชาเฉยๆ ได้พลังฐาน ฝึกจนช่ำชองได้เพิ่มอีกเท่าตัว
            # นี่คือจุดที่ "หนึ่งวิชาฝึกสี่สิบปี" เอาชนะ "สิบวิชาแบบงูๆ ปลาๆ" ได้
            m = PHYS.practice_mastery(mast.get(name, 0), C.PRACTICE_EXPONENT)
            p += w * (C.SKILL_BASE_SHARE + C.SKILL_MASTERY_SHARE * m)
    return p


def has_anti_chaos(ch: Character, items=None) -> bool:
    """แก้ทางเผ่าโกลาหลได้ไหม — จากวิชาที่รู้ หรือจากตราประทับสุญตาที่ถืออยู่

    เพิ่มทางที่สองเข้ามาเพราะวัดจริงจากโลกที่เดิน 445 ปีแล้วพบว่าวิชาแก้ทางทั้ง 18 วิชาสูญพันธุ์
    หมด (0 คนที่ยังมีชีวิตรู้สักวิชา) ตัว counter ที่ออกแบบไว้จึงหายไปจากโลกโดยไม่มีใครรู้ตัว
    """
    if any(SKILL_INDEX.get(n, (0, 0, 0, 0, 0, False))[5] for n in ch.skills):
        return True
    if items:
        from .treasures import has_anti_chaos_treasure
        return has_anti_chaos_treasure(ch, items)
    return False


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
        from . import paths as PATHS
        body, spirit = PATHS.shares(ch)
        # สายจิต: ความเข้าใจแปลงเป็นพลังได้มากกว่า | สายกาย: ความเสื่อมกัดพลังได้น้อยกว่า
        # เขียนเป็นตัวคูณบนพจน์เดิม ไม่ใช่บวกก้อนใหม่ — เพื่อให้ "สายไหนได้เปรียบ" ขึ้นกับว่า
        # ตัวละครสะสมอะไรมามากกว่ากัน (ความเข้าใจ vs อายุขัยที่เหลือ) ไม่ใช่ได้แต้มฟรีเพราะเลือกสาย
        p = (world.tier * C.TIER_STEP
             + ch.realm * C.REALM_STEP
             + ch.insight * C.INSIGHT_W * (1.0 + C.PATH_SPIRIT_INSIGHT * spirit)
             + blood_power(ch)
             + skill_power(ch)
             - ch.decay * C.DECAY_W * (1.0 - C.PATH_BODY_TOUGH * body))
        if body >= PATHS.BALANCE_AT and spirit >= PATHS.BALANCE_AT:
            p += C.PATH_BALANCE_BONUS
        # พรมีผลเฉพาะตราบที่ยังมีผู้สูงสุดในสายเลือดนั้นอยู่ Sim จะคำนวณค่าใหม่ทันทีเมื่อเกิด/ตาย
        p *= 1.0 + getattr(ch, "bloodline_buff", 0.0)
        # ร่างกายจริงมีผลกับพลัง แต่เป็น **หนึ่งปัจจัย** ไม่ใช่ตัวตัดสิน — โลกนี้พลังส่วนใหญ่
        # มาจากขั้น วิชา ธาตุ และปราณ ดัชนีอยู่รอบ 1.0 และถ่วงด้วย BODY_POWER_WEIGHT
        # จึงขยับพลังได้ราว ±2.5% ตามส่วนเบี่ยงเบนของประชากร (ดู tiandao/body/capability)
        p *= 1.0 + BODY.BODY_POWER_WEIGHT * (BODY.strength_of(ch) - 1.0)
    if items:
        p += item_power(ch, items, day)
    # หุ่นที่เชิดอยู่สู้แทนเจ้าของได้จริง — นับเป็นพลังของเจ้าของ ไม่ใช่ตัวละครแยก เพราะหุ่นไม่มี
    # เจตจำนงของตัวเอง ไม่ควรกินคิวเหตุการณ์และไม่ควรถูกนับเป็นประชากรของแดน
    n = getattr(ch, 'puppets', 0)
    if n:
        p += C.PUPPET_POWER_EACH * min(n, puppet_cap(ch))
    return p


def puppet_line_grade(ch, line: str) -> int:
    """เกรดสูงสุดที่รู้ในสายหุ่นสายหนึ่ง — คืน -1 ถ้าไม่รู้เลย"""
    best = -1
    for n in ch.skills:
        sk = SKILL_INDEX.get(n)
        if sk and sk[1] == line:
            best = max(best, sk[3])
    return best


def mind_weight(ch) -> float:
    """น้ำหนักวิชาสายจิตที่ผู้นี้ฝึกมา — ถ่วงตามเกรดเหมือนที่ portals.mastery ทำกับสายมิติ"""
    m = 0.0
    for n in ch.skills:
        sk = SKILL_INDEX.get(n)
        if sk and sk[1] in C.PUPPET_MIND_LINES:
            m += 1.0 + sk[3]
    return m


def puppet_cap(ch) -> int:
    """ถือหุ่นได้มากสุดกี่ตน — เกรดของสายหุ่นเป็นฐาน บวกโบนัสจากวิชาสายจิตที่ฝึกควบคู่มา

    การเชิดหุ่นคือการแบ่งจิตไปคุมอีกร่างหนึ่ง วิชาสายหุ่นบอกว่า "เชิดเป็น" แต่สายจิตบอกว่า
    "แบ่งจิตไปได้กี่ทาง" — คนที่ฝึกแต่สายหุ่นล้วนๆ จึงตันที่เพดานของวิชา ส่วนคนที่ฝึกจิตมาแน่น
    ด้วยจะเชิดได้เป็นกองทัพ นี่คือเหตุผลที่สายนี้จับคู่กับสายจิตแล้วคุ้มกว่าจับคู่กับสายกาย
    """
    g = max(puppet_line_grade(ch, 'หุ่นกล'), puppet_line_grade(ch, 'เชิดศพ'))
    if g < 0:
        return 0
    base = C.PUPPET_CAP_BY_GRADE[min(g, len(C.PUPPET_CAP_BY_GRADE) - 1)]
    bonus = int(mind_weight(ch) / C.PUPPET_MIND_PER_SLOT)
    return base + min(bonus, C.PUPPET_MIND_MAX_BONUS)

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
    # การบิดเบือนของเผ่าโกลาหลเล่นงานทั้งกายและใจพร้อมกัน คนที่ฝึกมาแต่ด้านเดียวจะถูกเจาะที่
    # ด้านที่ตัวเองว่าง — ผู้ที่บำเพ็ญสมดุลทั้งสองทางจึงเป็นสายเดียวที่ยืนต้านมันได้จริง
    from . import paths as PATHS
    if PATHS.is_balanced(victim):
        edge *= (1.0 - C.PATH_BALANCE_EDGE)
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
            if details["type"] == "สังหาร": array_p = 3.5
            elif details["type"] == "ตรึงกาย": array_p = 3.0
            
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


def dao_edge(a, b) -> float:
    """วิถีข่มกัน — บวกให้ a ถ้าวิถีของ a ข่มวิถีของ b, ลบถ้าตรงกันข้าม

    เดิมตารางนี้อยู่ใน combat.py และถูกเรียกแค่ 3 จุด (ล่าอสูร ล่ามนุษย์มาร ประลองในลาน)
    ซึ่งกินการปะทะแค่ 16.8% ของทั้งโลก การปะทะที่เหลือ 83.2% ผ่าน resolve_clash ตัวนี้
    ซึ่งไม่เคยดู ch.dao เลย กฎ "แต่ละเผ่าแพ้ทางกันเอง" จึงแทบไม่มีผลจริง
    """
    da, db = getattr(a, "dao", None), getattr(b, "dao", None)
    if not da or not db or da == db:
        return 0.0
    tbl = C.DAO_ADVANTAGE
    if db in tbl.get(da, ()):
        return C.DAO_EDGE
    if da in tbl.get(db, ()):
        return -C.DAO_EDGE
    return 0.0


def resolve_clash(a, b, world, items, rng, day=None):
    p_a = power(a, world, items, day)
    p_b = power(b, world, items, day)
    
    arr_p_a, type_a, buffs_a = array_effects(a, items)
    arr_p_b, type_b, buffs_b = array_effects(b, items)
    
    p_a += arr_p_a
    p_b += arr_p_b
    
    # ห้าธาตุข่มกัน — น้ำดับไฟ ไม่ใช่ไฟดับน้ำ จึงต้องเป็นค่าที่มีทิศทาง (ดู elements.clash_edge)
    # คิดเป็นสัดส่วนของกำลังเฉลี่ยของคู่ปะทะ ไม่ใช่ค่าคงที่ ไม่งั้นธาตุจะสำคัญมากตอนขั้นต่ำ
    # แล้วแทบไม่มีผลเลยตอนขั้นสูงที่ตัวเลขกำลังใหญ่ขึ้นเป็นร้อยเท่า
    _eel = EL.clash_edge(EL.ensure(a), EL.ensure(b))
    _emag = C.ELEMENT_CLASH_W * 0.5 * (p_a + p_b)
    adv = p_a - p_b + chaos_edge(a, b) + dao_edge(a, b) + _eel * _emag
    
    if type_a == "สังหาร": b.decay += 1.0
    if type_b == "สังหาร": a.decay += 1.0
    
    if type_a == "ตรึงกาย": adv += 1.5
    if type_b == "ตรึงกาย": adv -= 1.5

    if day is not None:                      # ใช้พลังชิ้นเอกแล้วต้องรอฟื้น
        for ch in (a, b):
            for iid in ch.items:
                it = items.get(iid)
                if it and it.legend and day >= it.ready_day:
                    it.ready_day = day + it.cooldown
    # ต้องหนีบก่อนเข้า exp() — โลกนี้ไม่มีเพดานพลัง ผู้บำเพ็ญโตได้เรื่อยๆ และเจ้าโกลาหลก็แข็งขึ้น
    # ทุกครั้งที่คืนกลับ พอช่องว่างพลังกว้างพอ (adv/TEMP < -709) math.exp() ก็ overflow แล้วซิม
    # ตายทั้งรอบ วัดจริง: รอบ 2,000 ปีล้มที่ปีที่ 963 ตอนเจ้าโกลาหลคืนกลับครั้งที่ 37
    # ที่ค่านี้ผลลัพธ์คือ "ฝ่ายหนึ่งชนะแน่นอน" อยู่แล้ว การหนีบจึงไม่เปลี่ยนพฤติกรรมของโลก
    x = max(-60.0, min(60.0, adv / C.TEMP))
    p_a = 1.0 / (1.0 + math.exp(-x))
    a_won = rng.random() < p_a
    # กระดานจัดอันดับยุทธภพ (Elo) — ชื่อเสียงที่ **ทำนายผลการปะทะได้จริง** ต่างจาก `merit`
    # ที่เป็นแค่ตัวนับซึ่งเพิ่มขึ้นอย่างเดียว คุณสมบัติที่ทำให้มันเหมาะกับโลกนี้:
    #   ไล่รังแกคนอ่อนแทบไม่ได้แต้ม · ม้ามืดโค่นเซียนสะเทือนกระดานจริง · แต้มรวมไม่เฟ้อ
    a.elo, b.elo = PHYS.elo_update(getattr(a, "elo", 1500.0), getattr(b, "elo", 1500.0),
                                   a_won, C.ELO_K)
    if a_won:
        return a, b, (abs(adv) if adv > 0 else 0.15)
    return b, a, (abs(adv) if adv < 0 else 0.15)


def apply_defeat(sim, world, win, lose, margin, rng, lethal_at=None):
    lethal_at = C.DEATH_MARGIN if lethal_at is None else lethal_at
    lethal_at *= (1.0 - C.DANGER_PER_TIER) ** world.tier     # โลกสูงยิ่งอันตราย
    lose.decay += C.DECAY_PER_FIGHT * (1.0 + margin) / (1.0 + 0.25 * lose.realm)
    # ผู้แพ้รับแรงเข้าร่างจริงเป็นบาดเจ็บเฉพาะส่วน (ดู body/injury · §26–28) พลังงานมาจาก
    # หมัดของผู้ชนะตามกายวิภาคของเขาเอง ถ่วงด้วยว่าเฉือนกันขาดแค่ไหน
    # ใช้สตรีมสุ่มที่ผูกกับเหตุการณ์ ไม่ดึงจาก rng ของโลก — การเพิ่มระบบนี้จึงไม่เลื่อน
    # สตรีมหลักจนอนาคตทั้งใบเปลี่ยนไปเพราะการอัปเกรด
    _blow = BODY.strike_energy(win) * (1.0 + margin) * BODY.DEFEAT_IMPACT_SCALE
    if _blow > 0.0:
        BODY.hurt(lose, _blow, key=(getattr(sim, "day", 0), win.cid, lose.cid,
                                    round(margin, 4)))
    # การปะทะเหนื่อยทั้งสองฝ่าย ผู้แพ้มากกว่าเพราะต้องรับแรงด้วย (§8)
    # ความล้าคลายเองใน age_and_decay ตามเวลาที่ผ่านไป จึงไม่สะสมไปตลอดกาล
    BODY.exert(lose, BODY.constants.FIGHT_WORK)
    BODY.exert(win, BODY.constants.FIGHT_WORK_WINNER)
    # หุ่นรับแรงแทนเจ้าของ — แพ้ทีหนึ่งก็พังไปตนหนึ่ง ทำให้กำลังจากหุ่นไม่สะสมขึ้นเรื่อยๆ ฟรีๆ
    if getattr(lose, 'puppets', 0) and rng.random() < C.PUPPET_BREAK_P:
        lose.puppets -= 1
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
            # หนี้บางก้อน (เช่น บุญคุณจากหอโอสถ) ถูกสร้างโดยไม่มีคีย์ kind ในเวอร์ชันก่อน
            ch.inner = max(0.0, ch.inner - C.DEBT_WEIGHT.get(d.get("kind"), 1.0))
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
    # ใช้ rank() (ขั้นที่ไต่มาจริงทั้งเส้น 0-29) ไม่ใช่ realm (0-9 ภายในชั้นฟ้า) — ไม่งั้นการข้าม
    # ฟ้ารีเซ็ตเกณฑ์สะสมให้ตกจาก 33 เหลือ 6 คือโลกบนไต่ง่ายกว่าโลกล่าง (ดู models.Character.rank)
    base = C.NEED_BASE + C.NEED_PER_REALM * ch.rank()
    return base * (1.0 - C.PURITY_PER_TIER) ** world.tier


def break_shifts(sim, ch: Character, world: World, pills: int = 0):
    """แรงทั้งหมดที่ดันกำแพงขั้นขึ้นหรือกดลง — คืน list ของค่า z พร้อมชื่อไว้อธิบาย

    แยกออกมาเป็นฟังก์ชันของตัวเองเพราะถูกใช้สองที่ที่ต้องตรงกันเป๊ะ: `attempt_break()`
    ตอนลงมือจริง และ `break_timing()` ตอนตัวละครชั่งใจว่าควรลงมือเมื่อไร ถ้าสองที่นี้ใช้
    สูตรคนละชุด ตัวละครจะวางแผนจากโลกที่ไม่มีอยู่จริง
    """
    from . import paths as PATHS
    from .treasures import aid_of
    _b, _s = PATHS.shares(ch)
    ratio = max(C.HEAVEN_RATIO_FLOOR, min(1.0, world.ratio()))
    parts = [
        ("ความเสื่อมในตัว", -C.BREAK_Z_DECAY * ch.decay),
        ("ยาวิเศษ", C.BREAK_Z_PILL * pills),
        ("ความบริสุทธิ์ของแดน", C.BREAK_Z_TIER * world.tier),
        ("สายจิต", C.BREAK_Z_SPIRIT * _s),
        ("ความพร่องของคลังฟ้า", C.BREAK_Z_SCARCE * math.log(ratio)),
        ("ฟ้ากดคนที่ขึ้นสูง", -C.BREAK_Z_REALM * ch.realm),
    ]
    _aid = aid_of(ch, getattr(sim, "items", {}) or {}, path="จิต")
    if _aid:
        parts.append(("สมบัติช่วยบำเพ็ญ", C.BREAK_Z_PER_P * _aid["break_bonus"]))
    return parts


def break_odds(sim, ch: Character, world: World, pills: int = 0) -> float:
    """โอกาสผ่านด่านพลัง — ภาพการข้ามกำแพงพลังงาน (ดู tiandao/physics.py)

    ส่วนเกินคิดเป็น **สัดส่วนของกำแพง** ไม่ใช่ค่าสัมบูรณ์ เพราะกำแพงของขั้นที่ 25 สูงกว่า
    ขั้นที่ 2 หลายเท่า การสะสมเกิน 1 หน่วยจึงมีความหมายคนละเรื่องกัน
    """
    req = max(1e-6, need(ch, world))
    gap = (accumulation(ch) - req) / req
    return PHYS.barrier_odds(gap, [v for _n, v in break_shifts(sim, ch, world, pills)],
                             base_p=C.BREAK_BASE_P, softness=C.BREAK_SOFTNESS)


def break_timing(sim, ch: Character, world: World, pills: int = 0) -> dict:
    """ควรลงมือทะลวงขั้นเมื่อไร — หาจุดที่อนุพันธ์เป็นศูนย์ ไม่ใช่เกณฑ์ตัดแข็ง

    เกณฑ์เดิม (`at_bottleneck()` = สะสมถึง 90% ของเกณฑ์) ตอบได้แค่ "พอหรือยัง" ซึ่งเป็น
    คำถามผิด วัดจริงโลก 47 ปี: ข้ามขั้น 3,629 ครั้ง จบด้วย "สะสมต่อ" 1,894 ครั้ง = 52%
    ของการลงมือทั้งหมดเป็นการลงมือก่อนเวลา เพราะเกณฑ์ปล่อยผ่านตั้งแต่ยังสะสมไม่ครบ

    คำถามที่ถูกคือ "ควรลงมือเมื่อไร" ซึ่งเป็นโจทย์หาค่าสูงสุดของ p(t)·(อายุที่เหลือ - t)
    (ดู physics.best_wait_days สำหรับที่มาของเงื่อนไข k·(1-p)·(L-t) = 1)

    `k` คืออัตราที่ z เพิ่มต่อวัน มาจากสองแรงที่หักล้างกัน
      + การสะสมที่เขาทำได้จริงช่วงหลัง (วัดจากตัวเขาเอง ไม่ใช่ค่าคงที่ของโลก)
      - ความเสื่อมที่เดินหน้าไปเรื่อยๆ ไม่ว่าจะทำอะไร
    ถ้าความเสื่อมชนะ k ติดลบ = รอไปมีแต่แย่ลง ต้องลงมือเดี๋ยวนี้
    """
    req = max(1e-6, need(ch, world))
    acc = accumulation(ch)
    p_now = break_odds(sim, ch, world, pills)
    life_left = max(0.0, (ch.lifespan() - ch.age(sim.day)) * 365.0)
    # k = d(z)/d(วัน) — การสะสมดันขึ้น ความเสื่อมดันลง
    k = (getattr(ch, "acc_rate", 0.0) / (C.BREAK_SOFTNESS * req)
         - C.BREAK_Z_DECAY * getattr(ch, "decay_rate", 0.0))
    wait = PHYS.best_wait_days(p_now, k, life_left,
                               horizon=C.BREAK_WAIT_HORIZON_DAYS)
    if acc < req:
        # ยังไม่ถึงกำแพงด้วยซ้ำ — อย่างน้อยต้องรอจนสะสมครบก่อน ไม่ว่าอนุพันธ์จะว่ายังไง
        r = max(1e-9, getattr(ch, "acc_rate", 0.0))
        wait = max(wait, min(C.BREAK_WAIT_HORIZON_DAYS, (req - acc) / r))
    return {"p": p_now, "wait_days": wait, "k": k, "life_left": life_left,
            "ready": wait <= C.BREAK_READY_DAYS and acc >= req}


def in_secret_realm(ch: Character) -> bool:
    """อยู่ในแดนลับของตัวเองอยู่ไหม (จาก "ซ่อนตัว" — ไม่ใช่ติดคุกและไม่ใช่ปิดด่าน)

    ทั้งสามสถานะใช้ธง `hidden` ร่วมกันโดยตั้งใจ (ทุกที่ในโลกที่กรอง hidden จะข้ามให้เอง)
    ฟังก์ชันนี้จึงต้องแยกให้ออกว่าเป็นแบบไหน เพราะกฎของแต่ละแบบตรงข้ามกัน:
    ปิดด่านคือการหายไปเพื่อ **ทะลวงขั้น** ส่วนแดนลับคือการหายไปแล้ว **ขั้นไม่ขยับ**
    """
    if not getattr(ch, "hidden", False):
        return False
    if getattr(ch, "seclude_until", 0) or getattr(ch, "jail_until", 0):
        return False
    return not getattr(ch, "is_lord", False)


def attempt_break(sim, ch: Character, world: World, rng, pills=0):
    """คืน (ผลลัพธ์, ข้อความ) — ต้องผ่านสองด่าน พลัง แล้วก็จิตมาร"""
    if ch.realm >= C.REALM_CAP:
        return "ตัน", "ตันขั้นสูงสุดของโลกนี้แล้ว"
    # กฎของโลก: คนที่หลบอยู่ในแดนลับของตัวเอง **เลื่อนขั้นไม่ได้** ต้องออกมาข้างนอกก่อน
    # เหตุผลเชิงดีไซน์: ถ้าหายเข้าไปนอนกอดสมบัติแล้วยังไต่ขั้นได้ด้วย การซ่อนตัวจะกลายเป็น
    # ทางที่ดีที่สุดของทุกคน แล้วตัวละครก็จะหายจากเวทีไปทีละคนโดยที่ยังแข็งแกร่งขึ้นเรื่อยๆ
    # กติกานี้ทำให้แดนลับเป็น "ที่พัก" ไม่ใช่ "ทางลัด" — สะสมได้ แต่ต้องกลับออกมาสู่โลกถึงจะข้ามได้
    if in_secret_realm(ch):
        return "อยู่ในแดนลับ", f"{ch.name}สะสมพลังไว้เต็มเปี่ยม แต่ในแดนลับที่ตัดขาดจาก" \
                               f"ฟ้าดิน ไม่มีทัณฑ์สวรรค์ให้ข้าม จึงไม่มีขั้นให้เลื่อน"
    req = need(ch, world)
    acc = accumulation(ch)
    if acc < req:
        return "ยังไม่ถึง", ""

    cultivators = max(0, world.n_alive - world.n_mortal)
    crowd_load = cultivators / max(1.0, C.HEAVEN_CULTIVATORS_PER_LOAD)
    crowd_cost = min(C.HEAVEN_CROWD_COST_CAP, 1.0 + C.HEAVEN_CROWD_COST * crowd_load)
    cost = C.BREAK_COST * (ch.realm + 1) ** 2 * crowd_cost
    # ---- บัญชีปิด: ฟ้าต้องจ่ายได้ครบ ไม่งั้นไม่มีขั้นให้เลื่อน ----
    # เดิมเขียนว่า take = min(cost, world.heaven) ตอนสำเร็จ ซึ่งแปลว่าคลังมีเท่าไรก็หยิบ
    # เท่านั้น **ส่วนที่ขาดหายไปเฉยๆ** คนเลื่อนขั้นได้โดยที่โลกไม่ได้จ่าย เป็นรูเดียวกับ
    # เครื่องปั๊มเงินของสำนักเป๊ะ แค่คนละสกุล และเป็นรูที่ทำให้ "ยุคเสื่อม" ไม่เคยกัดใครจริง
    # ตอนนี้ถ้าฟ้าไม่พอ ต้องเอาหินวิญญาณของตัวเองมาเติม — ซึ่งคือเหตุผลที่คนตุนหิน
    # และถ้ายังไม่พออีกก็เลื่อนไม่ได้ ต้องรอให้โลกฟื้นหรือไปหาแดนที่ปราณหนากว่า
    from . import economy as _EC
    short = cost - max(0.0, world.heaven)
    if short > 0:
        if _EC.purse_qi(ch) < short:
            return "ปราณฟ้าดินไม่พอ", \
                f"{ch.name}สะสมพร้อมแล้วแต่ปราณฟ้าดินใน{world.name}เหลือไม่พอให้ทะลวงขั้น"
    # เดิมลดโอกาสก็ต่อเมื่อพลังเหลือน้อยกว่าค่าใช้จ่ายครั้งเดียว จึงแทบไม่เกิดผลในคลังหลักหมื่น
    # ตอนนี้สัดส่วนพลังที่คนรุ่นก่อนเหลือไว้ส่งผลต่อคนรุ่นหลังตลอดช่วง 0-100%
    p = break_odds(sim, ch, world, pills)

    # หักการสะสม **หลัง** รู้ผลแต่ละด่าน ไม่ใช่ก่อน — inner_trial คิด resist จาก ch.insight
    # ถ้าหักทิ้งตรงนี้ก่อน คนจะถูกลดแต้มต้านทานลงก่อนเข้าด่านที่ใช้แต้มนั้นพอดี
    if rng.random() > p:
        _spend_accumulation(ch, req, C.BREAK_FAIL_SPEND)
        ch.fails += 1
        ch.decay += C.BACKLASH_DECAY * 0.5
        return "ล้มเหลว", f"{ch.name}ล้มเหลวในการข้ามขั้น การสะสมสูญเปล่า"

    trial = inner_trial(ch, world, rng)
    if trial == "พ่าย":
        _spend_accumulation(ch, req, 1.0)
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
    # เผ่าวิญญาณไม่ต้องฝ่าทัณฑ์ (ขัดเกลาสายเลือดโดยกำเนิด ไม่ได้แย่งพลังจากฟ้า)
    if not getattr(ch, "is_spirit", False):
        # ทัณฑ์สวรรค์ = ฟ้าดินทวงหนี้เอนโทรปี (กฎข้อสองของอุณหพลศาสตร์)
        # การฝึกตนเพื่อยืดอายุคือการกดความไร้ระเบียบในตัวเองให้ต่ำกว่าที่ธรรมชาติกำหนด
        # ซึ่งทำได้ก็ต่อเมื่อผลักมันออกไปที่อื่น ฟ้าดินจึงต้องทวงคืน — ของเดิมกำหนดเป็นรายการ
        # ขั้นตายตัว (4, 7, 9) ซึ่งเป็นเลขที่ตั้งเอาเองล้วนๆ และแปลว่าคนที่ยืดอายุตัวเองไป
        # หกร้อยปีแต่ไม่ได้อยู่ขั้นในรายการ ไม่เคยติดหนี้ฟ้าเลยสักนิด
        # ตอนนี้รายการเดิมยังอยู่ (เป็น "ด่านที่ฟ้าตั้งไว้") แต่เพิ่มการทวงตามหนี้จริงเข้าไปด้วย
        _karma = PHYS.entropy_karma(ch.lifespan(), ch.natural_lifespan, C.ENTROPY_K)
        _owed = rng.random() < PHYS.strike_chance(_karma, ch.realm + 1, C.TRIB_LAMBDA)
        if (ch.realm + 1) in C.TRIB_REALMS or _owed:
            # เพดานกำลังกายต้องตรงกับขั้นปัจจุบันก่อนวัด — ของเดิมอ่านค่า default 100 ที่ไม่เคยโต
            sync_hp(ch)
            tribulation_msg = f"\n⚡ [ทัณฑ์สวรรค์] ฟ้าดินพิโรธ! ส่งสายฟ้าฟาดฟัน {ch.name} เพื่อหยุดยั้งการเบิกมรรค!"
            # ความแรงของทัณฑ์ผูกกับ **หนี้ที่ติดไว้** ไม่ใช่ขั้นเปล่าๆ — คนที่ยืดอายุตัวเอง
            # มากกว่าย่อมโดนหนักกว่า แม้จะอยู่ขั้นเดียวกัน
            frac = C.TRIB_BASE_FRAC * (1.0 + _karma / C.TRIB_KARMA_SCALE)
            raw = ch.max_hp * frac
            # ทัณฑ์เบาลงได้ด้วยการเตรียมตัว — ตรงกับกฎที่ตั้งไว้ว่าเลื่อนขั้นต้องสะสม แต่มีตัวช่วยได้
            resist = 1.0
            resist -= min(C.TRIB_PILL_CAP, pills * C.TRIB_PILL_REDUCE)
            resist -= min(C.TRIB_SURPLUS_CAP, max(0.0, acc - req) * C.TRIB_SURPLUS_REDUCE)
            from .treasures import aid_of as _aid_of
            if _aid_of(ch, getattr(sim, "items", {}) or {}, path="จิต"):
                resist -= C.TRIB_AID_REDUCE
            trib_dmg = raw * max(C.TRIB_RESIST_FLOOR, resist)
            hp_pool = getattr(ch, "hp", ch.max_hp)
            if hp_pool <= trib_dmg:
                # ทนไม่ไหว — บาดเจ็บหนักแต่ยังไม่พิการถาวร ฟื้นได้ตามกาลใน age_and_decay
                ch.hp = max(1.0, ch.max_hp * C.TRIB_FAIL_LEFT)
                ch.decay += C.BACKLASH_DECAY * 2.0
                _spend_accumulation(ch, req, C.TRIB_FAIL_SPEND)
                ch.fails += 1
                return "บาดเจ็บสาหัส", tribulation_msg + f"\n -> ❌ {ch.name} ทนรับทัณฑ์สวรรค์ไม่ไหว บาดเจ็บปางตาย การทะลวงขั้นล้มเหลว!"
            else:
                ch.hp = hp_pool - trib_dmg
                tribulation_msg += f"\n -> 🛡️ {ch.name} ทนรับทัณฑ์สวรรค์สำเร็จ! (สูญเสียกำลังกาย {trib_dmg:.0f})"

    # สำเร็จ — ถอนพลังจากคลังฟ้า
    _spend_accumulation(ch, req, 1.0)
    take = min(cost, max(0.0, world.heaven))
    world.heaven = max(0.0, world.heaven - take)
    if take < cost:
        # ส่วนที่ฟ้าจ่ายไม่ไหว เจ้าตัวเผาหินของตัวเองเติม — ตรวจไว้แล้วข้างบนว่ามีพอ
        take += _EC.burn_qi(ch, cost - take)
    ch.drawn += take
    ch.grip = 1.0
    ch.realm += 1
    world.breakthroughs = getattr(world, "breakthroughs", 0) + 1
    sync_hp(ch, C.BREAK_HEAL_ON_RISE)   # ขั้นใหม่ = กายใหม่ เพดานกำลังกายขยายตาม
    if ch.realm == 1:
        world.n_mortal -= 1
    ch.breaks += 1
    ch.peak_realm = max(ch.peak_realm, ch.realm)
    ch.decay = max(0.0, ch.decay - 0.5)
    if hasattr(sim, "update_apex_blessing"):
        sim.update_apex_blessing(ch)
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
    """คลังฟ้าฟื้นตัว — ลอจิสติกจากตัวมันเอง + เศษที่สามัญชนเติมให้ทุกปี

    ของเดิมเติมเป็นเส้นตรงจากจำนวนสามัญชนแล้วตัดที่เพดานด้วย min() ซึ่งผิดสองทาง
      1. โลกที่ถูกดูดจนแห้งฟื้นด้วยความเร็วเท่ากับโลกที่เกือบเต็ม — ยุคเสื่อมจึงไม่เคยยาว
         พอจะเป็นยุคเสื่อมจริง มันหายไปเองภายในไม่กี่สิบปีเสมอ
      2. การตัดที่เพดานคือ **การทำพลังงานหายจากระบบเงียบๆ** ซึ่งขัดกับกฎข้อแรกของ
         เทอร์โมไดนามิกส์ที่โลกนี้ประกาศไว้เองว่า "สมบัติฟ้าดินมีจำกัด"

    ลอจิสติก dH/dt = r·H(1 - H/K) แก้ทั้งสองข้อ: ฟื้นช้าตอนแห้ง เร็วที่สุดตรงกลาง แล้ว
    ช้าลงเองเมื่อเข้าใกล้เพดาน — **ไม่ต้องมี min() ไปตัด** (ดู physics.logistic_growth)
    ส่วนสามัญชนยังเป็นแหล่งเติมจากภายนอก ทำหน้าที่เป็น "เมล็ด" ให้โลกที่ถูกดูดจนเหลือศูนย์
    ยังกลับมาได้ ไม่ติดอยู่ที่ศูนย์ตลอดกาลตามธรรมชาติของลอจิสติก
    """
    years = elapsed_days / 365.0
    cap = world.cap()
    grown = PHYS.logistic_growth(world.heaven, cap, C.HEAVEN_REGEN_PER_DAY, elapsed_days)
    seeded = grown + mortals * C.LIFE_INFLOW * years
    world.heaven = min(cap, max(0.0, seeded))
    world.rift = max(0.0, world.rift - years * C.RIFT_HEAL_PER_YEAR)


def death_return(world: World, ch: Character, natural: bool):
    """ผู้บำเพ็ญตายคืนพลังมาก เพราะสะสมไว้เยอะ
    แต่ถูกฆ่ากลางคันคืนได้แค่เศษ เพราะวงจรชีวิตถูกตัดขาด"""
    rate = C.NATURAL_RETURN if natural else C.KILLED_RETURN
    world.heaven = min(world.cap(), world.heaven + ch.drawn * rate)
    ch.drawn = 0.0


# ------------------------------------------------------------------ กำลังกาย
def hp_cap(ch: Character) -> float:
    """เพดานกำลังกายตามขั้น — สูตรเดียวกับที่ combat_vis.py ใช้แสดงผลมาตลอด (100 + realm*65)

    ของเดิม `max_hp` ใน models.py เป็น 100 คงที่ ไม่โตตามขั้นเลย ขณะที่ทัณฑ์สวรรค์คิดจาก
    (realm+1)*30 ซึ่งที่ realm 3 = 120 เกิน 100 เสมอ ทัณฑ์จึงล้มเหลว 100% สำหรับทุกคนที่ไม่ใช่
    เผ่าวิญญาณ (บรรทัด is_spirit คือทางออกเดียวที่มีอยู่) นี่คือกำแพงที่ทำให้ทั้งจักรวาลตันที่ realm 3
    """
    return C.HP_BASE + C.HP_PER_REALM * ch.realm


def sync_hp(ch: Character, heal_frac: float = 0.0) -> None:
    """ปรับเพดานให้ตรงกับขั้นปัจจุบัน โดยรักษาสัดส่วนกำลังกายที่เหลืออยู่ แล้วฟื้นให้ตามที่สั่ง"""
    old_cap = getattr(ch, "max_hp", None) or C.HP_BASE
    if old_cap <= 0:
        old_cap = C.HP_BASE
    frac = min(1.0, max(0.0, (getattr(ch, "hp", old_cap) or 0.0) / old_cap))
    ch.max_hp = hp_cap(ch)
    ch.hp = ch.max_hp * min(1.0, frac + max(0.0, heal_frac))


def _spend_accumulation(ch: Character, req: float, ratio: float = 1.0) -> None:
    """หักการสะสมที่ใช้ไปกับการข้ามขั้น — เรียก **หลัง** รู้ผลทุกด่านแล้วเท่านั้น"""
    ch.insight = max(0.0, ch.insight - req * 0.8 * ratio)
    ch.refine = max(0.0, ch.refine - req * 0.2 / 3.0 * ratio)


# ------------------------------------------------------------------ ความเสื่อม
def track_rates(ch: Character, day: int):
    """วัดว่า "ตัวเขาเอง" สะสมได้และเสื่อมลงวันละเท่าไรช่วงหลัง

    เป็นอนุพันธ์ที่วัดจากชีวิตจริงของเขา ไม่ใช่ค่าคงที่ของโลก — นักรบกับนักปรุงยาสะสม
    คนละความเร็ว และคนคนเดียวกันตอนหนุ่มกับตอนแก่ก็ไม่เท่ากัน ค่านี้คือ `k` ในเงื่อนไข
    จุดเหมาะสม k·(1-p)·(L-t) = 1 (ดู rules.break_timing และ physics.best_wait_days)

    ใช้ค่าเฉลี่ยถ่วงน้ำหนักแบบครึ่งชีวิต เพราะช่วงเวลาระหว่างการวัดไม่เท่ากันเลย (บางคน
    โผล่มาทุก 30 วัน บางคนหายไปในด่านแปดปี) น้ำหนักจึงต้องคิดจากเวลาที่ผ่านไปจริง
    ไม่ใช่จำนวนครั้งที่วัด — `w = exp(-Δt/τ)` เมื่อ τ = ครึ่งชีวิต/ln2

    ไม่ดึง rng และไม่เปลี่ยนอะไรนอกจากตัวนับสามตัวนี้ (ความคงที่ของโลกไม่ขยับ)
    """
    gap = day - getattr(ch, "acc_mark_day", 0)
    acc = accumulation(ch)
    if gap <= 0:
        ch.acc_mark, ch.decay_mark, ch.acc_mark_day = acc, ch.decay, day
        return
    tau = max(1.0, C.RATE_HALF_LIFE_DAYS / math.log(2.0))
    w = math.exp(-gap / tau)
    d_acc = (acc - getattr(ch, "acc_mark", 0.0)) / gap
    d_dec = (ch.decay - getattr(ch, "decay_mark", 0.0)) / gap
    ch.acc_rate = w * getattr(ch, "acc_rate", 0.0) + (1.0 - w) * max(0.0, d_acc)
    ch.decay_rate = w * getattr(ch, "decay_rate", 0.0) + (1.0 - w) * max(0.0, d_dec)
    ch.acc_mark, ch.decay_mark, ch.acc_mark_day = acc, ch.decay, day


def upkeep(ch: Character, world: World, years: float):
    """ค่าใช้จ่ายของปุถุชน — จ่ายเป็นเหรียญทอง

    ผู้ฝึกไม่ผ่านทางนี้แล้ว เขาจ่ายเป็นปราณผ่าน sustain() ข้างล่าง เพราะเงินทองซื้อข้าวได้
    แต่ซื้อการคงอยู่ของขั้นไม่ได้ — สองอย่างนี้เป็นคนละสกุลและคนละกลไกโดยตั้งใจ
    """
    if years <= 0 or not ch.alive or ch.realm > 0:
        return 0.0
    cost = C.UPKEEP_BASE * ((1.0 + ch.rank()) ** C.UPKEEP_POW) * years
    wid = world.wid
    have = ch.money.get(wid, 0.0)
    if have >= cost:
        ch.money[wid] = have - cost
        return cost
    ch.money[wid] = 0.0
    short = (cost - have) / max(1e-9, cost)
    ch.decay += C.UPKEEP_SHORT_DECAY * short * years
    return have


def sustain(sim, ch: Character, world: World, years: float):
    """หัวใจของกฎ "หยุดฝึกไม่ได้" — เดินงบปราณของผู้ฝึกหนึ่งคนไปข้างหน้าหนึ่งช่วง

    ลำดับของแหล่งปราณ เรียงตามที่คนจริงจะทำ
      1. **ดูดจากฟ้าดินตรงที่ยืนอยู่** — ฟรี ไม่ต้องมีสักเหรียญ นี่คือกติกาที่ทำให้ยุทธภพ
         ยังมีคนยากไร้ที่แข็งแกร่งขึ้นได้ในถ้ำร้าง และเป็นวาล์วกันไม่ให้การถดถอยกลายเป็น
         หลุมมรณะที่คนจนตกลงไปแล้วไม่มีวันขึ้นมา
      2. **เผาหินวิญญาณ** — เฉพาะส่วนที่ดูดไม่พอ หินคือทางลัดของคนที่ไม่มีที่ยืนดีพอ
         หรือที่ยึดขั้นสูงเกินกว่าแผ่นดินใต้เท้าจะเลี้ยงไหว
      3. **ขาดเหลือเท่าไรก็คือขาด** — ไม่มีการยืม ไม่มีการติดลบ ส่วนที่ขาดไปปรากฏเป็น
         ขั้นสมดุล R* ที่ต่ำกว่าขั้นจริง แล้วความมั่นคงก็คลายลงตามสมการผ่อนคลาย

    ที่ดูดออกมาทั้งหมดถูกหักจากคลังฟ้าจริง ไม่ใช่เสกขึ้นมา — นี่คือจุดที่ "เงินขึ้นกับ
    ทรัพยากร" กลายเป็นความจริงเชิงบัญชี ไม่ใช่ความตั้งใจ

    คืน (ปราณที่ได้จริงต่อปี, ปราณที่ดูดจากโลก)
    """
    from . import economy as EC
    if years <= 0 or not ch.alive or ch.realm <= 0:
        return 0.0, 0.0
    # ดูดเผื่อขั้นถัดไปด้วย ไม่ใช่แค่พอเลี้ยงตัว — **ส่วนเกินนี้คือสิ่งที่ทำให้โลกล้นได้**
    # ถ้าทุกคนดูดแค่พอเลี้ยงตัว คลังฟ้าจะเข้าสมดุลนิ่งๆ แล้วยุคเสื่อมจะไม่มีวันเกิด
    # (ตรวจด้วยแบบจำลอง ODE ก่อนเขียน: ไม่มีพจน์ความทะเยอทะยาน = เส้นตรงนิ่งตลอดกาล)
    reach = ch.realm + C.AMBITION_REALMS
    rho = sim.qi_density(ch.place, world) if hasattr(sim, "qi_density") else C.QI_REFERENCE
    want = EC.absorb_per_year(reach, rho) * years
    pool = max(0.0, world.heaven)
    drawn = min(want, pool)
    world.heaven = pool - drawn
    ch.qi_taken = getattr(ch, "qi_taken", 0.0) + drawn
    # ส่วนหนึ่งของปราณที่ดูดเข้ามาไม่ได้ถูกเผาทิ้ง แต่**สะสมอยู่ในร่าง** — ซึ่งก็คือนิยาม
    # ของการบำเพ็ญนั่นเอง ส่วนนี้จึงคืนสู่ฟ้าตอนเจ้าตัวตาย (ดู death_return)
    # ถ้าไม่มีบรรทัดนี้ ปราณที่ถูกดูดไปเลี้ยงร่างจะหายจากระบบถาวร โลกจะไหลลงทางเดียว
    # แล้วนิ่งอยู่ที่สภาพเสื่อมตลอดกาล — วัดแล้วเจอจริง: คลังฟ้าค้างที่ 13-18% ตั้งแต่
    # ปีที่ 150 ถึงปีที่ 305 ไม่ขยับ ซึ่งเป็นโศกนาฏกรรมของส่วนรวมที่ถูกต้องตามสมการ
    # แต่ไม่ใช่โลกที่มียุคให้เล่า
    ch.drawn = getattr(ch, "drawn", 0.0) + drawn * C.SUSTAIN_STORE
    need = EC.upkeep_qi(ch.realm) * years
    got = drawn
    if got < need:
        got += EC.burn_qi(ch, need - got)
    per_year = got / max(1e-9, years)
    ch.qi_in = per_year
    return per_year, drawn


def hold_realm(ch: Character, qi_per_year: float, gap_days: int) -> int:
    """ความมั่นคงของขั้นเดินไปข้างหน้า — คืนจำนวนขั้นที่หล่นในช่วงนี้ (ปกติ 0)

        dG/dt = -λ·(R - R*)·G      เมื่อเลี้ยงตัวไม่ไหว
        dG/dt = +λ'·(1 - G)        เมื่อเลี้ยงไหวแล้ว

    ใช้ physics.relax ซึ่งเป็นรูปแบบปิด จึงไม่แกว่งแม้ตัวละครจะหายไปจากคิวหลายปี
    (เหตุการณ์หนึ่งของคนขั้นสูงห่างกันได้เป็นสิบปี ออยเลอร์ก้าวเดียวจะพังทันที)

    ทำไมแรงกดดันคูณเข้าไปในอัตรา ไม่ใช่ในเป้าหมาย: คนที่เกินขั้นที่เลี้ยงไหวไปหนึ่งขั้น
    กับเกินไปสามขั้น ปลายทางเหมือนกันคือหล่น ต่างกันที่ **ความเร็ว** ซึ่งเป็นสิ่งที่
    อ่านเป็นเรื่องได้: คนแรกโรยราอยู่หลายสิบปี คนหลังทรุดลงภายในไม่กี่ปี
    """
    from . import economy as EC
    if gap_days <= 0 or not ch.alive or ch.realm <= 0:
        return 0
    star = EC.supported_realm(qi_per_year)
    grip = getattr(ch, "grip", 1.0)
    pressure = ch.realm - star
    fell = 0
    if pressure > 0:
        lam = C.GRIP_LAMBDA * min(C.GRIP_PRESSURE_CAP, pressure)
        grip = PHYS.relax(grip, 0.0, lam, gap_days)
        while grip <= C.GRIP_FLOOR and ch.realm > 0:
            ch.realm -= 1
            fell += 1
            grip = 1.0
            # หล่นลงมาแล้วแรงกดดันเบาลง ถ้ายังไม่พออีกก็หล่นต่อในรอบเดียวกันได้
            pressure = ch.realm - star
            if pressure <= 0:
                break
            lam = C.GRIP_LAMBDA * min(C.GRIP_PRESSURE_CAP, pressure)
            grip = PHYS.relax(grip, 0.0, lam, gap_days)
    else:
        grip = PHYS.relax(grip, 1.0, C.GRIP_RISE, gap_days)
    ch.grip = min(1.0, max(0.0, grip))
    return fell


def age_and_decay(sim, ch: Character, world: World, gap_days: int, rng):
    years = gap_days / 365.0
    # วัดอัตราของตัวเขาเองก่อนอย่างอื่น — นี่คือจุดเดียวที่ตัวละครทุกคนผ่านทุกครั้งที่โลกเดิน
    track_rates(ch, getattr(sim, "day", ch.acc_mark_day))
    # สภาพร่างกายเดินไปตามเวลาที่ผ่านไปจริง: เลือดออกจากแผลที่ยังเปิด สร้างเลือดใหม่
    # คลายความล้า และแผลสมาน (ดู body.tick · §8, §18, §34) ทั้งหมดอินทิเกรตเป็นรูปแบบปิด
    # ข้าม gap ทีเดียว เพราะเอนจินนี้กระโดดข้ามเวลาเป็นวัน ไม่มี tick ต่อเนื่องให้เดิน
    if getattr(ch, "injuries", None) or getattr(ch, "fatigue", 0.0)             or getattr(ch, "bleed", 0.0) or getattr(ch, "blood_frac", 1.0) < 1.0:
        BODY.tick(ch, gap_days)
        # เสียเลือดจนหมดคือทางตายจริงที่ไม่ผ่านการปะทะ — บาดแผลที่ไม่มีใครห้ามเลือดให้
        # ฆ่าคนได้เองหลังเหตุการณ์จบไปแล้ว ถ้าไม่มีทางนี้ คนจะค้างอยู่ที่เลือดสามสิบ
        # เปอร์เซ็นต์ตลอดกาลโดยไม่มีอะไรเกิดขึ้น
        if ch.alive and ch.blood_frac < BODY.constants.BLOOD_DEATH_BELOW:
            sim.kill(ch, "เลือดไหลจนหมดจากบาดแผลที่ไม่มีใครห้ามให้")
            return
    upkeep(ch, world, years)
    # งบปราณของผู้ฝึก — ดูดฟรีจากที่ยืน แล้วเผาหินเติมส่วนที่ขาด (ดู sustain)
    qi_year, _drawn = sustain(sim, ch, world, years)
    fell = hold_realm(ch, qi_year, gap_days)
    if fell and ch.realm == 0:
        world.n_mortal += 1
    if fell and hasattr(sim, "on_realm_fall"):
        sim.on_realm_fall(ch, fell, qi_year)
    from . import paths as PATHS
    from .treasures import aid_of
    body, spirit = PATHS.shares(ch)
    # กายบำเพ็ญคือการหลอมเนื้อกระดูกให้ทนกาลเวลา ส่วนจิตบำเพ็ญเผาร่างเป็นเชื้อเพลิงของดวงจิต
    path_mult = (1.0 - C.PATH_BODY_DECAY * body) * (1.0 + C.PATH_SPIRIT_FRAIL * spirit)
    aid = aid_of(ch, getattr(sim, "items", {}) or {}, path="กาย")
    if aid:
        path_mult *= aid["decay_mult"]
    ch.decay += years * C.DECAY_PER_YEAR * (1.0 + C.DECAY_PER_REALM_MULT * ch.realm) * path_mult
    # โลกต่ำหล่อเลี้ยงคนที่เกินขั้นไม่ได้
    over = ch.realm - (C.SUPPORTED_REALM + world.tier * 2)
    if over > 0:
        ch.decay += years * C.OVERPOWER_DRAIN * over
    # ความเสื่อมยังทำให้ขั้นหล่นได้ แต่ตอนนี้เป็นทางที่สอง ไม่ใช่ทางเดียว — ทางแรกคือ
    # เลี้ยงตัวไม่ไหว (hold_realm ข้างบน) ทางนี้คือร่างกายพังจากการรบและกาลเวลา
    # เก็บไว้ทั้งคู่เพราะมันเล่าคนละเรื่อง: อันหนึ่งคือหมดทรัพยากร อีกอันคือหมดสภาพ
    if ch.decay >= C.REGRESS_AT and ch.realm > 0:
        was_apex = (ch.tier >= len(C.TIER_NAMES) - 1 and ch.realm >= C.REALM_CAP)
        ch.realm -= 1
        ch.grip = 1.0
        if ch.realm == 0:
            world.n_mortal += 1
        ch.decay -= C.REGRESS_AT * 0.6
        if was_apex and hasattr(sim, "update_apex_blessing"):
            sim.update_apex_blessing(ch)
    # เพดานกำลังกายต้องตามขั้นเสมอ และบาดแผลต้องฟื้นได้ตามกาล ไม่งั้นคนที่รอดทัณฑ์มาแบบ
    # สะบักสะบอมจะติดอยู่ที่กำลังกายเกือบศูนย์ไปตลอดชีวิต แล้วไม่มีวันฝ่าทัณฑ์รอบหน้าได้อีก
    sync_hp(ch, years * C.HP_REGEN_FRAC_PER_YEAR)
    # เจ้าโกลาหล **ไม่มีอายุขัย** — มันไม่แก่ตาย ฆ่าได้อย่างเดียว ถ้าไม่กันตรงนี้ไว้ มันจะ
    # "ตายเอง" เป็นระยะแล้วเข้าเส้นทางสลาย-ก่อร่างใหม่ฟรีๆ โดยไม่มีใครต้องออกแรงสักคน
    if ch.is_lord:
        ch.decay = 0.0
        return
    if ch.age(sim.day) >= ch.lifespan():
        # ผู้ใกล้สิ้นอายุขัยกินยาอายุวัฒนะที่มีอยู่เอง เลือกเม็ดที่ต่ออายุได้มากที่สุด
        pills = [iid for iid in ch.items
                 if iid in getattr(sim, "items", {})
                 and sim.items[iid].kind == "ยาวิเศษ"
                 and getattr(sim.items[iid], "lifespan_bonus", 0) > 0]
        if pills:
            iid = max(pills, key=lambda x: sim.items[x].lifespan_bonus)
            pill = sim.items[iid]
            ch.items.remove(iid)
            ch.longevity_bonus += pill.lifespan_bonus
            if ch.age(sim.day) < ch.lifespan():
                return
        sim.kill(ch, "สิ้นอายุขัย", natural=True)


def cultivate(ch: Character, gap_days: int, items=None):
    """บำเพ็ญ — `items` เป็นตัวเลือก ใส่มาเมื่อไหร่ประทีปดวงจิตพันภพถึงจะออกฤทธิ์

    ทำเป็นพารามิเตอร์ที่ไม่ใส่ก็ได้ เพราะฟังก์ชันนี้ถูกเรียกจาก 13 จุดทั่ว sim.py และจากเทสต์เก่า
    ที่ไม่มี items อยู่ในมือ — การบังคับให้ทุกที่ส่งมาจะพังของเดิมโดยไม่ได้อะไรเพิ่ม
    """
    yrs = min(4.0, gap_days / 365.0)
    ch.decay = max(0.0, ch.decay - C.CULTIVATE_HEAL)
    gain = 0.45 * yrs * eff(ch, "human")
    if items:
        from .treasures import aid_of
        aid = aid_of(ch, items, path="จิต")
        if aid:
            gain *= aid["insight_mult"]
    ch.insight += gain
    ch.refine += 0.10 * yrs * eff(ch, "spirit")


def refine_blood(ch: Character, gap_days: int):
    yrs = min(4.0, gap_days / 365.0)
    ceiling = ch.blood.get("spirit", 0.0)
    ch.refine = min(ceiling, ch.refine + 0.18 * yrs * eff(ch, "spirit"))


# ------------------------------------------------------------------ ยุค / โลก
def check_world(sim, world: World, rng):
    # ยุคเดินเองตามกาลสำหรับโลกที่ไม่เคยล่มและไม่เคยฟื้น (แดนมาร ห้วงโกลาหล) — ดู ERA_DRIFT_YEARS
    last = getattr(world, "era_day", 0)
    if sim.day - last >= C.ERA_DRIFT_YEARS * 365:
        world.era_day = sim.day
        world.era += 1
    if world.ratio() > C.COLLAPSE_RATIO:
        # รอดพ้นยุคเสื่อมแล้ว — ล้างสถิติการล่มติดต่อกัน
        if world.ratio() >= C.DECLINE_RATIO:
            world.fall_streak = 0
        # เสื่อมได้ก็ฟื้นได้ — แต่ต้อง **รุ่งเรืองต่อเนื่องเป็นร้อยปี** ไม่ใช่แค่เต็มในวันที่ตรวจพอดี
        if world.ratio() >= C.RECOVER_RATIO:
            if getattr(world, "flourish_day", None) is None:
                world.flourish_day = sim.day
            held = (sim.day - world.flourish_day) / 365.0
        else:
            world.flourish_day = None
            held = 0.0
        if (held >= C.RECOVER_YEARS
                and world.tier + 1 < len(C.TIER_NAMES)
                and world.kind == "mortal" and rng.random() < C.RECOVER_P):
            world.tier += 1
            world.flourish_day = None
            world.era += 1
            world.era_day = sim.day
            # ภาชนะใหญ่ขึ้น แต่พลังในนั้นเท่าเดิม — ของเดิมเติมเป็น cap*0.8 ของชั้นใหม่ ซึ่ง
            # เสกพลังขึ้นมาจากอากาศ (cap โต 2.4 เท่าต่อชั้น) ขัดกับกฎ "วิถีสวรรค์มีพลังจำกัด"
            # และทำให้เลื่อนชั้นซ้ำๆ ได้ฟรี ตอนนี้ ratio จึงร่วงเองหลังเลื่อน ต้องสะสมใหม่จริง
            world.heaven = min(world.cap(), world.heaven)
        return None
    notes = []
    for ch in sim.living_in(world.wid):
        if ch.is_lord:
            # เจ้าโกลาหลไม่ได้อยู่ใต้วัฏจักรยุคของแดนไหน — มันมาก่อนแดนพวกนั้น วัดจริง 300 ปี:
            # มันสลาย 6 ครั้ง และ **ทุกครั้งเกิดจากยุคล่มของแดนที่มันสังกัด ไม่ใช่ฝีมือใครเลย**
            # ศัตรูสูงสุดของโลกที่ตายเองเพราะแดนหมดอายุ ไม่ใช่เรื่องเล่า
            continue
        if rng.random() < C.ERA_CULL_P * (0.4 + 0.12 * ch.realm):
            sim.kill(ch, f"ดับสูญไปกับยุคที่ {world.era}", natural=True)
            notes.append(ch.name)
        else:
            # ถูกกดขั้นลง — ปราณที่ผูกไว้กับขั้นที่เสียไปต้องคืนสู่ฟ้า ไม่ใช่หายไปเฉยๆ
            # (คู่กับ death_return ที่คืนปราณของคนที่ตาย — หลักเดียวกัน คนละเหตุ)
            drop = min(C.ERA_PUSHDOWN, ch.realm)
            if drop > 0 and getattr(ch, "drawn", 0.0) > 0:
                back = ch.drawn * (drop / max(1, ch.realm)) * C.ERA_RETURN
                ch.drawn -= back
                world.heaven = min(world.cap(), world.heaven + back)
            ch.realm = max(0, ch.realm - drop)
            ch.grip = 1.0
    for ch in sim.living_in(world.wid):
        ch.tier = world.tier
        ch.peak_tier = max(ch.peak_tier, ch.tier)
    world.n_mortal = sum(1 for c in sim.living_in(world.wid) if c.realm == 0)
    world.n_alive = len(sim.living_in(world.wid))
    world.flourish_day = None
    world.fall_streak = getattr(world, "fall_streak", 0) + 1
    if world.tier > 0 and world.fall_streak >= C.DEMOTE_AFTER:
        world.tier -= 1          # โลกที่เสื่อม **ซ้ำซาก** จึงกลายเป็นโลกระดับต่ำลง
        world.fall_streak = 0
    # เดิมเขียน `world.heaven = world.cap() * 0.7` ตรงนี้ — **เสกปราณ 49,000 หน่วยจาก
    # อากาศทุกครั้งที่ยุคล่ม** เป็นบั๊กคลาสเดียวกับ org.monthly_resource = 10000 เป๊ะ
    # แค่คนละสกุล และเจอด้วยวิธีเดียวกัน: รันยาวแล้วเห็นคลังฟ้าเด้งจาก 13% เป็น 65%
    # ในช่วงเดียว โดยไม่มีเหตุการณ์ไหนในบันทึกอธิบายได้
    #
    # ตอนนี้การฟื้นของโลกมาจากที่ที่มันควรมา: **คนที่ตายและคนที่ถูกกดขั้นคืนปราณที่เคย
    # ถอนไป** (death_return และบล็อกข้างบน) ยุคเสื่อมจึงฟื้นได้ก็ต่อเมื่อมีคนล้มตายจริง
    # ซึ่งเป็นวงจรผู้ล่า-เหยื่อแบบ Lotka-Volterra: ผู้ฝึกคือผู้ล่า ปราณของโลกคือเหยื่อ
    # ถ้าไม่มีใครตาย ยุคเสื่อมก็ยาวต่อไป — ซึ่งเป็นสิ่งที่ควรเป็น
    world.era += 1
    world.era_day = sim.day
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


# ---------------------------------------------------------------- กฎหมายยุทธภพ
def is_criminal(ch) -> bool:
    """คนนี้ "ผิดกฎ" ในสายตาทางการไหม — ใช้ตัดสินว่าใครถูกจับกุมได้

    เดิมไม่มีฟังก์ชันนี้: "จับกุมอาชญากร" เล็งใครก็ได้ที่ยืนอยู่แถวนั้น มือปราบจึงตามจับชาวนา
    และตัวเอกที่ไม่เคยทำอะไรผิดได้ฟรี วัดจริง 102 ปี = 478 ศพ
    """
    if getattr(ch, "kills", 0) > 0:
        return True                                   # ฆ่าคนมาแล้ว
    if getattr(ch, "moral", 0) <= C.CRIMINAL_MORAL:
        return True                                   # ประวัติเสียสะสม (ปล้น/ขูดรีด/ทรยศ)
    if getattr(ch, "profession", "") in C.CRIMINAL_PROFESSIONS:
        return True                                   # อาชีพผิดกฎหมายอยู่ในตัว
    if getattr(ch, "hated", None) and ch.hated():
        return True                                   # มนุษย์มาร — ถูกตามล่าโดยกฎของโลก
    if getattr(ch, "spy_for", None) is not None:
        return True                                   # ไส้ศึกที่ถูกจับได้
    return False


def crime_weight(ch) -> int:
    """หนักเบาของความผิด — ตัดสินว่าคุมขังนานเท่าไร หรือถึงขั้นประหาร"""
    n = getattr(ch, "kills", 0)
    if getattr(ch, "hated", None) and ch.hated():
        n += 1
    if getattr(ch, "profession", "") in C.CRIMINAL_PROFESSIONS:
        n += 1
    if getattr(ch, "moral", 0) <= C.CRIMINAL_MORAL * 2:
        n += 1
    return n


def assassin_motive(sim, a, t):
    """เหตุที่ทำให้ a ลงมือสังหาร t ได้ — คืน (คำอธิบายเหตุ, ผู้ว่าจ้างหรือ None) หรือ None ถ้าไม่มีเหตุ

    มือสังหารไม่ใช่เครื่องจักรที่ฆ่าคนข้างตัว — เขาลงมือเพราะแค้นเอง หรือเพราะมีคนจ่าย
    ผู้ว่าจ้างหามาจาก **คนที่เขารู้จักอยู่แล้ว** (a.bonds ซึ่งเล็กมาก) ไม่ใช่สแกนคนทั้งแดน
    เพื่อไม่ให้ต้นทุนต่อเหตุการณ์โตตามประชากร
    """
    if t.cid in getattr(a, "rivals", {}):
        return "แค้นส่วนตัว", None
    for dbt in getattr(a, "debts", ()):
        if not dbt.get("done") and dbt.get("target") == t.cid:
            return "สะสางเรื่องค้างคา", None
    if a.org is not None and t.org is not None and a.org < len(sim.orgs):
        org = sim.orgs[a.org]
        if getattr(org, "alive", False) and org.grudges.get(t.org, 0) >= 3:
            return f"คำสั่งของ{org.name}", None
    fee_max = C.ASSASSIN_FEE[1]
    for cid in sorted(getattr(a, "bonds", {}) or {}):
        if cid == t.cid or not (0 <= cid < len(sim.cast)):
            continue
        c = sim.cast[cid]
        if (c.alive and c.world_id == a.world_id and c.rivals.get(t.cid, 0) > 0
                and c.money.get(a.world_id, 0) >= fee_max):
            return f"รับจ้างจาก{c.name}", c
    return None


def trust_tie(sim, a, t):
    """ความไว้ใจที่ a ใช้หักหลัง t ได้ — คืนคำอธิบายความสัมพันธ์ หรือ None ถ้าไม่มีอะไรให้ทรยศ

    การทรยศต้องมีความไว้ใจอยู่ก่อน คนแปลกหน้าไม่มีอะไรให้หักหลังกัน — เดิมไม่มีเงื่อนไขนี้
    เพราะ handler ของ "ทรยศ" ไม่เคยทำงาน (ชื่อ kind ไม่ตรงกัน) ทุกอย่างจึงไหลไปเป็นการดวล
    """
    if t.cid == getattr(a, "spouse", None):
        return "เป็นคู่ครองของเขา"
    if t.cid == getattr(a, "master_cid", -1):
        return "เป็นอาจารย์ของเขา"
    if t.cid in getattr(a, "disciples", ()):
        return "เป็นศิษย์ของเขา"
    if t.cid in getattr(a, "parents", ()) or t.cid in getattr(a, "children", ()):
        return "เป็นสายเลือดเดียวกัน"
    if a.bonds.get(t.cid, 0) > 0 and t.bonds.get(a.cid, 0) > 0:
        return "ไว้ใจเขาอยู่"
    if t.bonds.get(a.cid, 0) >= C.BETRAY_BOND_MIN:
        return "ไว้ใจเขามาก"
    if a.org is not None and a.org == t.org:
        return "ร่วมสำนักเดียวกัน"
    if a.clan >= 0 and a.clan == t.clan:
        return "ร่วมตระกูลเดียวกัน"
    for dbt in getattr(t, "debts", ()):
        if not dbt.get("done") and dbt.get("target") == a.cid:
            return "ติดค้างเรื่องกับเขาอยู่"
    return None
