# -*- coding: utf-8 -*-
"""เครื่องยนต์เจตนา — ตัวละครเลิกสุ่ม เริ่มมีความตั้งใจ

สามเลเยอร์ เรียงตามลำดับความสำคัญ:
  1. อยู่รอด (Survive)  — บาดเจ็บหนัก/ใกล้ตาย ให้ทุกอย่างอื่นรอ
  2. เติบโต (Grow)      — ตามอาร์คีไทป์ของตัวละคร
  3. สถานการณ์ (Event) — ศัตรูอยู่ตรงหน้า ตระกูลถูกโจมตี หนี้ค้างคาบีบ
"""
import random

from . import config as C

# ---------------------------------------------------------------- นิสัย
TRAITS = {
    "ใจโอบอ้อม": "เลือกช่วยคนและรักษาสมาชิกตระกูลก่อนเสมอ",
    "โลภมาก": "พร้อมทรยศพันธมิตรเพื่อชิงสมบัติ",
    "ขลาดกลัว": "เจอศัตรูแข็งกว่าแค่ขั้นเดียวก็ถอย",
    "พยาบาท": "ล็อกเป้าล้างแค้นยาวจนกว่าจะสำเร็จ",
    "บ้าพลัง": "ไล่ล่าขั้นพลังเหนือทุกสิ่ง ยอมเสี่ยงตาย",
    "ใฝ่รู้": "หมกมุ่นกับวิชาและการหลอมของมากกว่าการต่อสู้",
}

# ---------------------------------------------------------------- อาร์คีไทป์
# น้ำหนักเสริมที่บวกเข้ากับตารางเหตุการณ์พื้นฐาน
ARCHETYPES = {
    "นักล่าบ้าพลัง": {
        "บำเพ็ญ": 10, "ข้ามขั้น": 14, "ฝึกวิชา": 10, "ล่าอสูร": 8,
        "ค้นแดนลับ": 6, "ประลอง": 6, "ข้ามฟ้า": 5,
    },
    "พ่อค้าวาณิช": {
        "ค้าขาย": 18, "เดินทาง": 12, "ให้สัญญา": 6, "ชิงสมบัติ": 4,
        "ล่าอสูร": 4, "ตั้งสำนัก": 3,
    },
    "ช่างหลอม": {
        "หลอมยา": 12, "หลอมอาวุธ": 12, "ล่าอสูร": 10, "เดินทาง": 6,
        "ฝึกวิชา": 4, "ค้าขาย": 4,
    },
    "มารหิวกระหาย": {
        "ล้างแค้น": 10, "ทรยศ": 6, "ล่าอสูร": 8, "หลอมยา": 6,
        "ชิงสมบัติ": 8, "บำเพ็ญ": 6,
    },
    "ผู้พเนจร": {
        "เดินทาง": 10, "บำเพ็ญ": 8, "ให้สัญญา": 5, "สะสางเรื่องเก่า": 6,
    },
}

ARCH_BY_DAO = {
    "วิถีค้าขาย": "พ่อค้าวาณิช", "วิถียา": "ช่างหลอม", "วิถีเหล็ก": "ช่างหลอม",
    "วิถีเลือด": "มารหิวกระหาย", "วิถีพเนจร": "ผู้พเนจร",
    "วิถีมวยไทย": "นักล่าบ้าพลัง",
}


def pick_archetype(ch, rng):
    if ch.blood.get("mara", 0) >= 0.3 or ch.thrall:
        return "มารหิวกระหาย"
    a = ARCH_BY_DAO.get(ch.dao)
    if a:
        return a
    return rng.choice(["นักล่าบ้าพลัง", "นักล่าบ้าพลัง", "ผู้พเนจร", "ช่างหลอม"])


def pick_traits(rng):
    n = rng.choice([1, 1, 2])
    return rng.sample(list(TRAITS.keys()), n)


# ---------------------------------------------------------------- เรียนรู้จากประสบการณ์
def snapshot(ch):
    """สภาพตัวละครก่อน/หลังลงมือทำเจตนาหนึ่งครั้ง ใช้วัดว่าครั้งนั้นดีหรือร้ายกับตัวเอง"""
    return (ch.decay, ch.insight + ch.refine * 3.0, sum(ch.money.values()), ch.realm, ch.hp)


def learn_from_outcome(ch, kind, before, after):
    """จำผลจริงที่เจอไว้กับเจตนานั้น (EMA) — ไม่ใช่ปรับตารางกลาง แค่ความจำของตัวเอง"""
    d_decay = before[0] - after[0]      # ความเสื่อมลด = ดี
    d_acc = after[1] - before[1]        # สะสมได้เพิ่ม = ดี
    d_money = after[2] - before[2]
    d_realm = after[3] - before[3]      # ข้ามขั้นสำเร็จ = ดีมาก
    d_hp = after[4] - before[4]
    reward = (d_decay * 0.5 + d_realm * 2.0 + d_hp * 0.01
              + (0.3 if d_acc > 0 else -0.1 if d_acc < 0 else 0.0)
              + (0.1 if d_money > 0 else -0.05 if d_money < 0 else 0.0))
    if not ch.alive:
        reward -= 5.0
    reward = max(-3.0, min(3.0, reward))
    m = ch.learn
    m[kind] = m.get(kind, 0.0) * (1.0 - C.LEARN_ALPHA) + reward * C.LEARN_ALPHA


# ---------------------------------------------------------------- เลือกเจตนา
def weigh(ch, sim, table, has_others):
    """คืน dict ของ kind -> น้ำหนัก หลังผ่านสามเลเยอร์"""
    w = {}
    for e in table:
        if e["tgt"] and not has_others:
            continue
        w[e["kind"]] = float(e["w"])
        
    # ---- เลเยอร์ 0: อาชีพและนิสัย (อัปเดตใหม่) ----
    if getattr(ch, "profession", "ผู้ฝึกตน") != "ผู้ฝึกตน":
        # อาชีพสามัญ
        prof = ch.profession
        if prof == "ชาวนา": w["ทำนา"] = 50
        elif prof == "พ่อค้าทั่วไป": w["ค้าขายทั่วไป"] = 50
        elif prof == "ช่างชาวบ้าน": w["ตีเหล็กชาวบ้าน"] = 50
        elif prof == "หมอชาวบ้าน": w["รักษาชาวบ้าน"] = 50
        elif prof in ("นักฆ่า", "โจรป่า", "องครักษ์เสื้อแพร"):
            w["ลอบสังหาร"] = w.get("ลอบสังหาร", 0) + 45
            w["ดักปล้น"] = w.get("ดักปล้น", 0) + 35
        elif prof in ("มือปราบ", "ทหารรักษาพระนคร", "แม่ทัพใหญ่", "ทหารม้าเหล็ก",
                      "ทหารลาดตระเวน", "ทหารยาม", "ทหารกองปราบ", "ท่านอ๋อง"):
            w["จับกุมอาชญากร"] = w.get("จับกุมอาชญากร", 0) + 40
        elif prof in ("นักบวช", "นักพรต"):
            w["สะสมบุญบารมี"] = w.get("สะสมบุญบารมี", 0) + 45
        # ลดโอกาสทำเรื่องผู้ฝึกตน
        for k in ("บำเพ็ญ", "ข้ามขั้น", "ล่าอสูร", "ค้นแดนลับ", "ประลอง"):
            if k in w: w[k] *= 0.1
    else:
        # ผู้ฝึกตน
        fear = getattr(ch, "fear", 0.5)
        greed = getattr(ch, "greed", 0.5)
        comp = getattr(ch, "compassion", 0.5)
        
        w["ซ่อนตัว"] = w.get("ซ่อนตัว", 0) + fear * 15
        w["บำเพ็ญ"] = w.get("บำเพ็ญ", 0) + fear * 10
        w["ชิงสมบัติ"] = w.get("ชิงสมบัติ", 0) + greed * 15
        w["ทรยศ"] = w.get("ทรยศ", 0) + greed * 10
        w["ขูดรีดชาวบ้าน"] = w.get("ขูดรีดชาวบ้าน", 0) + greed * 15
        w["ปกป้องชาวบ้าน"] = w.get("ปกป้องชาวบ้าน", 0) + comp * 20
        w["ถ่ายทอดวิชา"] = w.get("ถ่ายทอดวิชา", 0) + comp * 10

    # ---- เลเยอร์ 1: อยู่รอด ----
    hurt = ch.decay > 1.8 or ch.fate == 0
    if hurt:
        for k in ("บำเพ็ญ", "ซ่อนตัว"):
            if k in w:
                w[k] += 30
        for k in ("ประลอง", "ล้างแค้น", "ชิงสมบัติ", "ล่าอสูร", "ข้ามขั้น"):
            w[k] = w.get(k, 0) * 0.15
        if "ขลาดกลัว" in ch.traits:
            for k in ("ประลอง", "ล้างแค้น", "ชิงสมบัติ"):
                w[k] = 0.0

    # ---- เลเยอร์ 2: เติบโต ----
    for k, bonus in ARCHETYPES.get(ch.archetype, {}).items():
        if k in w:
            w[k] += bonus

    pv = sim.place_of(ch)
    eco = sim.eco_ratio(ch.place) if hasattr(sim, "eco_ratio") else 1.0
    # ถึงคอขวดแล้วต้องหาตัวช่วย ไม่ใช่นั่งรอ
    if not hurt and ch.at_bottleneck():
        w["ข้ามขั้น"] = w.get("ข้ามขั้น", 0) + 25
        w["ค้นแดนลับ"] = w.get("ค้นแดนลับ", 0) + 8
        w["ค้าขาย"] = w.get("ค้าขาย", 0) + 5
    # ช่างที่อยากหลอมแต่ยืนอยู่ที่ไม่มีเตา -> ออกเดินทางไปหาเตา
    # ไม่มีเตาก็หลอมไม่ได้ ไม่ต้องเสียเวลาลอง
    if not (pv and pv[5] >= 0):
        w["หลอมยา"] = 0.0
        w["หลอมอาวุธ"] = 0.0
    if ch.archetype == "ช่างหลอม":
        if pv and pv[5] >= 0:
            w["หลอมยา"] = w.get("หลอมยา", 0) + 14
            w["หลอมอาวุธ"] = w.get("หลอมอาวุธ", 0) + 14
            w["เดินทาง"] = w.get("เดินทาง", 0) * 0.3
        else:
            w["เดินทาง"] = w.get("เดินทาง", 0) + 22
    # อยู่แหล่งวัตถุดิบก็เก็บของ อยู่ตลาดก็ขาย
    if pv:
        if pv[4]:
            w["ล่าอสูร"] = w.get("ล่าอสูร", 0) + 10 * eco
            if eco < 0.4:      # แหล่งนี้ร่อยหรอ — เริ่มมองหาที่อื่น
                w["เดินทาง"] = w.get("เดินทาง", 0) + (1.0 - eco) * 15
        if pv[3] in ("ตลาด", "เมือง"):
            w["ค้าขาย"] = w.get("ค้าขาย", 0) + 12
        if pv[3] in ("ลานฝึก", "สำนัก", "แดนต้องห้าม"):
            w["ฝึกวิชา"] = w.get("ฝึกวิชา", 0) + 12
            w["บำเพ็ญ"] = w.get("บำเพ็ญ", 0) + 6
        if pv[3] == "ประตูมิติ":
            w["ลงโลกล่าง"] = w.get("ลงโลกล่าง", 0) + 10

    # ---- เลเยอร์ 3: สถานการณ์ ----
    if ch.rivals:
        bump = 14 if "พยาบาท" in ch.traits else 6
        w["ล้างแค้น"] = w.get("ล้างแค้น", 0) + bump
    unresolved = sum(1 for d in ch.debts if not d["done"])
    if unresolved >= 3:
        w["สะสางเรื่องเก่า"] = w.get("สะสางเรื่องเก่า", 0) + 5 + unresolved
    if "โลภมาก" in ch.traits:
        w["ชิงสมบัติ"] = w.get("ชิงสมบัติ", 0) + 10
        w["ทรยศ"] = w.get("ทรยศ", 0) + 5
    if "ใจโอบอ้อม" in ch.traits:
        w["ถ่ายทอดวิชา"] = w.get("ถ่ายทอดวิชา", 0) + 8
        w["ให้สัญญา"] = w.get("ให้สัญญา", 0) + 6
        w["ทรยศ"] = w.get("ทรยศ", 0) * 0.2
    if ch.spy_for is not None and ch.org is not None:
        w["ไส้ศึกลงมือ"] = w.get("ไส้ศึกลงมือ", 0) + 12
    if ch.org is not None and ch.org < len(sim.orgs):
        org = sim.orgs[ch.org]
        if org.alive and org.grudges:
            max_grudge = max(org.grudges.values())
            if max_grudge >= 4:
                w["สงครามสำนัก"] = w.get("สงครามสำนัก", 0) + max_grudge * 2
                
    if ch.realm >= 7:
        w["ข้ามฟ้า"] = w.get("ข้ามฟ้า", 0) + 18
        w["ซ่อนตัว"] = w.get("ซ่อนตัว", 0) + 6

    # ข่าวลือที่เคยได้ยินมา — จูงใจให้ไปตามหา ไม่ใช่แค่รู้เฉยๆ
    from . import places as _PL
    for lead in getattr(ch, "rumor_leads", ()):
        if lead["kind"] == "แดนลับ":
            w["ค้นแดนลับ"] = w.get("ค้นแดนลับ", 0) + 10
        elif lead["kind"] == "สมบัติ":
            w["ค้นแดนลับ"] = w.get("ค้นแดนลับ", 0) + 5
            w["ชิงสมบัติ"] = w.get("ชิงสมบัติ", 0) + 6
        elif lead["kind"] in ("ขาดแคลน", "อุดมสมบูรณ์"):
            same_world = 0 <= lead["subject"] < len(_PL.PLACES) and \
                _PL.PLACES[lead["subject"]][1] == getattr(sim.world(ch.world_id), "place_key", None)
            if not same_world:
                continue
            if lead["kind"] == "ขาดแคลน" and lead["subject"] == ch.place:
                w["เดินทาง"] = w.get("เดินทาง", 0) + 12
            elif lead["kind"] == "อุดมสมบูรณ์":
                w["เดินทาง"] = w.get("เดินทาง", 0) + 6
        elif lead["kind"] == "ชิ้นส่วนวิชา":
            w["ค้นแดนลับ"] = w.get("ค้นแดนลับ", 0) + 8
            w["เดินทาง"] = w.get("เดินทาง", 0) + 5

    # ---- เลเยอร์ 4: ประสบการณ์ตรงของตัวเอง (เรียนรู้ได้ด้วยตัวเอง) ----
    if ch.learn:
        for k in list(w.keys()):
            bias = ch.learn.get(k, 0.0)
            if bias:
                w[k] *= max(C.LEARN_FLOOR, 1.0 + C.LEARN_GAIN * bias)

    # เหตุการณ์ที่ต้องมีคู่กรณี ต้องมีคนอื่นอยู่จริงเท่านั้น
    if not has_others:
        need_target = {e["kind"] for e in table if e["tgt"]}
        for k in need_target:
            w.pop(k, None)
    valid = {e["kind"] for e in table}
    return {k: v for k, v in w.items() if v > 0 and k in valid}


def sample_weighted(w, rng: random.Random):
    """สุ่มเลือกหนึ่ง kind ตามน้ำหนักใน w (roulette wheel) — คืน None ถ้า w ว่าง
    แยกออกมาจาก choose() เพื่อให้ Cultivator Brain (tiandao/ai/) แทรก boost น้ำหนักระหว่าง
    weigh() กับการสุ่มได้ โดยไม่ต้องแก้ตรรกะการสุ่มเอง"""
    if not w:
        return None
    total = sum(w.values())
    r, acc = rng.random() * total, 0.0
    for kind, v in w.items():
        acc += v
        if r <= acc:
            return kind
    return next(iter(w))


def choose(ch, sim, table, has_others, rng: random.Random):
    w = weigh(ch, sim, table, has_others)
    return sample_weighted(w, rng)
