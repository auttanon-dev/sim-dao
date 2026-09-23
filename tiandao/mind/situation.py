# -*- coding: utf-8 -*-
"""เข้ารหัสสถานการณ์ของตัวละครเป็นเวกเตอร์ x สำหรับความจำเชิงเชื่อมโยง

    from tiandao.mind import situation as SIT
    x = SIT.encode(sim, ch, others)

**งานจริงอยู่ที่ไฟล์นี้ ไม่ใช่ที่สมการ Hopfield**
สมการดึงคืนความจำที่ ξᵀx สูงสุด ถ้า x เข้ารหัสสิ่งที่ไม่เกี่ยวกับการตัดสินใจ มันก็จะดึง
ความจำที่ไม่เกี่ยวกับการตัดสินใจกลับมาอย่างมั่นใจ — สมการไม่มีทางรู้ว่าอะไรสำคัญ
คนที่ตัดสินว่าอะไรสำคัญคือคนเขียนไฟล์นี้

หลักที่ใช้เลือกช่อง
==================
1. **ใส่สิ่งที่เปลี่ยนการตัดสินใจ ไม่ใช่สิ่งที่บรรยายตัวละคร**
   ชื่อ ตระกูล อายุที่แน่นอน ไม่ได้เปลี่ยนว่าวันนี้ควรทำอะไร — ไม่ใส่
   ส่วนแรงกดดันจากปราณที่ไม่พอเลี้ยงขั้น เปลี่ยนทุกอย่าง — ใส่ และให้น้ำหนักมาก
2. **ห้ามใส่น้ำหนักจาก IN.weigh()**
   ถ้าใส่ ความจำจะกลายเป็นการจำคำตอบของฮิวริสติกเดิม แล้วทั้งระบบก็เป็นแค่
   ทางอ้อมที่แพงกว่าของเดิม จุดประสงค์คือให้ตัวละครจำ **สิ่งที่ตัวเองเคยทำ**
   ไม่ใช่จำสิ่งที่ตารางน้ำหนักบอกว่าควรทำ
3. **สเกลให้อยู่ราว 0..1 ทุกช่อง** เพราะ ξᵀx เป็นผลรวมของทุกช่อง ช่องที่สเกลใหญ่กว่า
   จะกลืนช่องอื่นหมด (เงินที่นับเป็นหมื่นจะทำให้อารมณ์ที่อยู่ 0..1 ไม่มีความหมายเลย)
   ค่าที่มีหางยาว (เงิน จำนวนศัตรู) ใช้ log1p ก่อนหาร ไม่ใช่หารตรงๆ
4. **ไม่ใช้ rng** ผลต้องคงที่สำหรับสถานะเดียวกันเสมอ ไม่งั้นความจำจะเทียบกันไม่ได้

น้ำหนักรายกลุ่ม (GROUP_W) คือที่ที่บอกว่า "อะไรสำคัญกว่าอะไร" — คูณเข้าไปก่อนทำ
normalize จึงมีผลต่อโคไซน์ความคล้ายจริง ไม่ใช่แค่ตัวประดับ
"""
import math

from .. import config as C
from .. import economy as EC
from .. import emotions as EM
from .. import elements as EL
from .. import places as PL

PLACE_TYPES = ("สำนัก", "เมือง", "แหล่งวัตถุดิบ", "ลานฝึก", "แดนต้องห้าม",
               "ตลาด", "ประตูมิติ", "ด่านชายแดน", "แดนลับ")

# น้ำหนักของแต่ละกลุ่มช่อง — คูณก่อน normalize
GROUP_W = {
    "body": 1.0,        # ขั้น ความเสื่อม กำลังกาย จิตมาร
    "qi": 2.0,          # แรงกดดันจากปราณ — ตัวที่เปลี่ยนการตัดสินใจมากที่สุดหลังรื้อเศรษฐกิจ
    "place": 1.2,       # ที่ยืน
    "wealth": 0.8,      # ทรัพย์
    "social": 1.2,      # สำนัก ศัตรู มิตร หนี้
    "heart": 1.5,       # เจ็ดอารมณ์หกปรารถนา — นี่คือสิ่งที่ทำให้คนสองคนในสถานการณ์
                        # เดียวกันตัดสินใจต่างกัน ถ้าน้ำหนักต่ำ ทุกคนจะกลายเป็นคนเดียวกัน
    "element": 0.5,
    "scene": 1.3,       # ใครอยู่ตรงนั้นด้วย
}


def _log1p_scaled(v, div):
    return min(1.0, math.log1p(max(0.0, v)) / max(1e-9, math.log1p(div)))


def q(v, levels=C.SITUATION_LEVELS):
    """แบ่งค่าต่อเนื่องเป็นระดับ — ข้อนี้สำคัญกว่าที่เห็น

    วัดจริงก่อนมี: เข้ารหัสค่าต่อเนื่องตรงๆ ทำให้ **ทุกสถานการณ์ไม่เหมือนกันเลยแม้แต่ครั้งเดียว**
    (อารมณ์ 0.4821 vs 0.4823 ก็เป็นคนละเวกเตอร์) ความจำจึงไม่มีวันชี้ไปทางเดียวกัน
    ส่วนแบ่งถูกหารกระจายทุกครั้ง ความมั่นใจเกาะอยู่ใต้ 0.2 และดึงคืนได้ 3 ครั้งจาก 344

    คนไม่ได้จำสถานการณ์เป็นทศนิยม เขาจำเป็นหมวด — "โกรธรุนแรง ที่ลานฝึก ขั้นตื่นชี่"
    ระดับความเข้มที่โลกนี้ใช้อยู่แล้วในใบประวัติ (เล็กน้อย/ปานกลาง/มาก/รุนแรง/ท่วมท้น)
    ก็มีห้าระดับพอดี การแบ่งระดับจึงไม่ใช่การทำให้ข้อมูลหยาบลง มันคือการเข้ารหัส
    **ในหน่วยเดียวกับที่ความจำของคนทำงาน** ซึ่งเป็นเงื่อนไขที่ทำให้ "เคยเจอเรื่องแบบนี้"
    เป็นประโยคที่มีความหมายได้ตั้งแต่แรก
    """
    n = max(1, int(levels))
    return min(1.0, max(0.0, round(max(0.0, min(1.0, v)) * n) / n))


def field_names():
    """ชื่อของทุกช่องตามลำดับ — มีไว้ให้ดีบักและให้เทสต์ยืนยันว่าลำดับไม่เลื่อน"""
    names = ["realm", "decay", "hp_frac", "inner", "grip", "fate", "bottleneck"]
    names += ["qi_short", "qi_spare", "ceiling", "purse_years"]
    names += [f"place_{t}" for t in PLACE_TYPES] + ["place_grade", "eco", "tier"]
    names += ["stones", "gold"]
    names += ["has_org", "org_rank", "rivals", "bonds", "disciples", "debts",
              "has_master", "skills", "depth"]
    names += [f"emo_{e}" for e in EM.EMOTIONS] + [f"des_{d}" for d in EM.DESIRES]
    names += [f"el_{e}" for e in EL.GEN_ORDER]
    names += ["others", "rival_here", "bond_here", "loot_here", "power_ratio",
              "stronger_here"]
    return names


DIM = len(field_names())


def encode(sim, ch, others=()):
    """คืนเวกเตอร์ความยาว DIM — ยังไม่ normalize (Memory จัดการให้)"""
    w = sim.world(ch.world_id)
    gw = GROUP_W
    out = []

    # ---- ร่างกายและใจ ----
    hp_cap = max(1e-9, getattr(ch, "max_hp", 100.0))
    out += [x * gw["body"] for x in (
        ch.realm / max(1, C.REALM_CAP),            # ขั้นเป็นจำนวนเต็มอยู่แล้ว ไม่ต้องแบ่งระดับ
        q(ch.decay / max(1e-9, C.REGRESS_AT)),
        q(getattr(ch, "hp", hp_cap) / hp_cap),
        q(ch.inner / 10.0),
        q(getattr(ch, "grip", 1.0)),
        q(ch.fate / 5.0),
        1.0 if ch.at_bottleneck() else 0.0,
    )]

    # ---- งบปราณ: แรงกดดันที่ทำให้ "หยุดฝึกไม่ได้" มีความหมาย ----
    rho = sim.qi_density(ch.place, w) if ch.place is not None else C.QI_REFERENCE
    ceiling = EC.place_ceiling(rho)
    short = max(0.0, ch.realm - ceiling)
    spare = max(0.0, ceiling - ch.realm)
    need = max(1e-9, EC.upkeep_qi(ch.realm))
    out += [x * gw["qi"] for x in (
        q(short / 3.0),
        q(spare / 3.0),
        q(max(0.0, ceiling) / max(1, C.REALM_CAP)),
        q(EC.purse_qi(ch) / (need * 10.0)),
    )]

    # ---- ที่ยืน ----
    pv = PL.PLACES[ch.place] if ch.place is not None and 0 <= ch.place < len(PL.PLACES) else None
    ptype = pv[3] if pv else ""
    out += [(1.0 if ptype == t else 0.0) * gw["place"] for t in PLACE_TYPES]
    out += [x * gw["place"] for x in (
        (pv[2] / 2.0) if pv else 0.0,
        q(sim.eco_ratio(ch.place) if ch.place is not None else 1.0, 3),
        w.tier / max(1, len(C.TIER_NAMES) - 1),
    )]

    # ---- ทรัพย์ (หางยาว ใช้ log) ----
    out += [x * gw["wealth"] for x in (
        q(_log1p_scaled(EC.purse_qi(ch), 500.0), 4),
        q(_log1p_scaled(sum(ch.money.values()), 5000.0), 4),
    )]

    # ---- สังคม ----
    org = sim.orgs[ch.org] if ch.org is not None and 0 <= ch.org < len(sim.orgs) else None
    rank = 0.0
    if org is not None:
        if ch.cid in getattr(org, "core_disciples", ()):
            rank = 1.0
        elif ch.cid in getattr(org, "inner_disciples", ()):
            rank = 0.6
        elif ch.cid in getattr(org, "outer_disciples", ()):
            rank = 0.3
    out += [x * gw["social"] for x in (
        1.0 if org is not None else 0.0,
        rank,
        q(_log1p_scaled(len(ch.rivals), 20.0), 4),
        q(_log1p_scaled(len(ch.bonds), 20.0), 4),
        q(_log1p_scaled(len(ch.disciples), 10.0), 3),
        q(_log1p_scaled(sum(1 for d in ch.debts if not d.get("done")), 8.0), 3),
        1.0 if ch.master_cid >= 0 else 0.0,
        q(_log1p_scaled(len(ch.skills), 10.0), 4),
        q(max((getattr(ch, "mastery", None) or {}).values(), default=0) / 40.0, 3),
    )]

    # ---- เจ็ดอารมณ์ หกปรารถนา ----
    emo = getattr(ch, "emotions", None) or {}
    des = getattr(ch, "desires", None) or {}
    # ห้าระดับ ตรงกับคำบรรยายความเข้มที่ใบประวัติใช้ (เล็กน้อย/ปานกลาง/มาก/รุนแรง/ท่วมท้น)
    out += [q(emo.get(e, 0.0)) * gw["heart"] for e in EM.EMOTIONS]
    out += [q(des.get(d, 0.0)) * gw["heart"] for d in EM.DESIRES]

    # ---- ธาตุ ----
    el = EL.ensure(ch)
    out += [(1.0 if el == e else 0.0) * gw["element"] for e in EL.GEN_ORDER]

    # ---- ฉาก: ใครอยู่ตรงนั้นด้วย ----
    pool = [o for o in others if o is not None and o.cid != ch.cid]
    rival_here = any(o.cid in ch.rivals or ch.cid in o.rivals for o in pool)
    bond_here = any(o.cid in ch.bonds for o in pool)
    loot_here = any(getattr(o, "items", None) for o in pool)
    my_realm = ch.realm + 1.0
    ratio = max((o.realm + 1.0) / my_realm for o in pool) if pool else 0.0
    out += [x * gw["scene"] for x in (
        q(_log1p_scaled(len(pool), 12.0), 3),
        1.0 if rival_here else 0.0,
        1.0 if bond_here else 0.0,
        1.0 if loot_here else 0.0,
        q(ratio / 3.0, 4),
        1.0 if ratio > 1.0 else 0.0,
    )]
    return out


def beta_of(ch):
    """β ประจำตัว — นิสัยกลายเป็นความคมของการดึงคืน

    คนเด็ดขาด/ดื้อ ดึงความจำเดียวที่ใกล้สุดมาใช้ (β สูง) = "คนนี้ทำอย่างเดิมเสมอ"
    คนใจรวน/ลังเล เฉลี่ยความจำหลายก้อน (β ต่ำ) = ตัดสินใจไม่เหมือนเดิมสองครั้ง
    จิตมารที่หนักทำให้ใจไม่มั่น จึงลด β ลงด้วย — ความมืดในใจทำให้คนทำสิ่งที่ตัวเอง
    คาดไม่ถึง ซึ่งเป็นสิ่งที่แนวนี้เล่ากันมาตลอด
    """
    traits = set(getattr(ch, "traits", ()) or ())
    b = C.HOPFIELD_BETA
    if "พยาบาท" in traits or "โลภมาก" in traits:
        b *= 1.35            # ล็อกเป้า ไม่เปลี่ยนใจ
    if "ใจโอบอ้อม" in traits:
        b *= 1.1
    if "ขี้ระแวง" in traits or "ลังเล" in traits:
        b *= 0.7
    b *= 1.0 / (1.0 + min(1.0, ch.inner / 12.0))
    return max(C.HOPFIELD_BETA_MIN, min(C.HOPFIELD_BETA_MAX, b))
