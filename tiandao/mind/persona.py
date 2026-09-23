# -*- coding: utf-8 -*-
"""แปลงตัวเลขของตัวละครเป็นคำพูดที่คนอ่านเข้าใจ — ทั้งสำหรับพรอมต์และหน้าอ่าน

หลักคิด: โมเดลขนาดเล็ก (4-8B) ตีความ "fear=0.83" ได้ไม่ดี แต่เข้าใจ "ขี้ระวังจนเกือบขลาด" ได้ทันที
ทุกค่าที่ส่งให้โมเดลจึงผ่านไฟล์นี้ก่อน และหน้าอ่านใช้คำชุดเดียวกัน ผู้อ่านจะเห็นตัวละครแบบเดียว
กับที่โมเดลเห็นตอนตัดสินใจ
"""
from .. import clans as CL
from .. import config as C
from .. import events as E
from .. import places as PL
from .. import elements as EL
from .. import economy as EC
from .. import emotions as EM


def _scale(v, words):
    """v ในช่วง 0..1 -> คำที่เหมาะ (words เรียงจากต่ำไปสูง)"""
    v = max(0.0, min(0.999, float(v)))
    return words[int(v * len(words))]


def temperament(ch):
    parts = [
        _scale(getattr(ch, "fear", 0.5), ["กล้าบ้าบิ่น", "ใจกล้า", "ระมัดระวัง", "ขี้ขลาดหวาดระแวง"]),
        _scale(getattr(ch, "greed", 0.5), ["มักน้อยสันโดษ", "พอประมาณ", "อยากได้ใคร่มี", "โลภไม่รู้จักพอ"]),
        _scale(getattr(ch, "compassion", 0.5), ["เย็นชาไร้เมตตา", "ถือประโยชน์ตนก่อน", "มีน้ำใจ", "เมตตาสูง"]),
    ]
    amb = getattr(ch, "ambition", 50) / 100.0
    parts.append(_scale(amb, ["ไม่ทะเยอทะยาน", "ทะเยอทะยานพอควร", "ทะเยอทะยานสูง", "กระหายอำนาจ"]))
    return parts


def health_words(ch):
    hp = getattr(ch, "hp", 100)
    mx = max(1, getattr(ch, "max_hp", 100))
    r = hp / mx
    body = ("บาดเจ็บสาหัส" if r < 0.3 else "บาดเจ็บ" if r < 0.7 else "ร่างกายสมบูรณ์")
    decay = getattr(ch, "decay", 0.0)
    if decay > 2.5:
        body += " ร่างกายโรยราใกล้สิ้นอายุ"
    elif decay > 1.8:
        body += " ร่างกายเริ่มทรุดโทรม"
    inner = getattr(ch, "inner", 0.0)
    if getattr(ch, "inner_none", False):
        mind = "จิตใจใสสะอาดไร้จิตมาร"
    elif inner > 6:
        mind = "จิตมารหนักหน่วงจนเกือบคุมไม่อยู่"
    elif inner > 3:
        mind = "มีเรื่องค้างคาใจหลายเรื่อง จิตมารก่อตัว"
    elif inner > 1:
        mind = "มีเรื่องค้างคาใจอยู่บ้าง"
    else:
        mind = "จิตใจค่อนข้างสงบ"
    return body, mind


def wealth_words(ch):
    total = 0.0
    for tier, amount in getattr(ch, "money", {}).items():
        total += PL.to_mortal(amount, tier) if hasattr(PL, "to_mortal") else amount
    if total < 50:
        return "ยากจนข้นแค้น"
    if total < 500:
        return "พอมีพอกิน"
    if total < 5000:
        return "มีฐานะ"
    if total < 50000:
        return "ร่ำรวย"
    return "มั่งคั่งมหาศาล"


def org_name(sim, ch):
    if ch.org is None or ch.org >= len(sim.orgs):
        return ""
    return sim.orgs[ch.org].name


def clan_name(ch):
    if getattr(ch, "clan", -1) is None or ch.clan < 0 or ch.clan >= len(CL.CLANS):
        return ""
    return CL.CLANS[ch.clan][0]


def world_name(sim, ch):
    try:
        return sim.world(ch.world_id).name
    except (IndexError, AttributeError):
        return "?"


def place_label(sim, place_idx):
    if place_idx is None or place_idx < 0 or place_idx >= len(PL.PLACES):
        return "ที่ใดสักแห่ง"
    p = PL.PLACES[place_idx]
    return f"{p[0]} ({p[3]})"


def item_names(sim, ch, limit=5):
    names = []
    for iid in getattr(ch, "items", [])[:limit]:
        it = sim.items.get(iid) if hasattr(sim.items, "get") else None
        if it is not None:
            names.append(it.name or it.kind)
    return names


def short_identity(sim, ch):
    """หนึ่งบรรทัด: ชื่อ เผ่า ขั้น สังกัด — ใช้แนะนำคนรอบตัว"""
    bits = [ch.name, f"{ch.gender} อายุ {ch.age(sim.day)}", ch.race(), ch.realm_name()]
    org = org_name(sim, ch)
    if org:
        bits.append(f"สำนัก{org}" if not org.startswith("สำนัก") else org)
    clan = clan_name(ch)
    if clan:
        bits.append(clan)
    if getattr(ch, "profession", ""):
        bits.append(ch.profession)
    return " · ".join(bits)


def surname(name):
    """แซ่/ชื่อสกุลจากชื่อเต็ม — ชื่อแบบตงหยวนไม่มีช่องว่าง ต้องตัดจากรายการแซ่ที่โลกนี้ใช้"""
    n = (name or "").strip()
    if not n:
        return ""
    if " " in n:
        return n.split()[0]
    for s in sorted(E.SURNAME, key=len, reverse=True):
        if n.startswith(s):
            return s
    # ชื่อจากตระกูล/เผ่าอื่นไม่อยู่ในรายการแซ่ — ตัดพยางค์ชื่อตัวท้ายออกแทน (เหยาปิง -> เหยา)
    for g in sorted(E.GIVEN, key=len, reverse=True):
        if n.endswith(g) and len(n) > len(g):
            return n[:-len(g)]
    return n          # ไม่รู้จริงๆ ใช้ชื่อเต็ม ดีกว่าตัดสระหัวคำให้อ่านไม่ออก


def address_form(me, other):
    """คำเรียกอีกฝ่ายตามมารยาทยุทธภพ — โมเดลเล็กไม่รู้ธรรมเนียมนี้เอง ต้องบอกให้ตรงตัว

    วัดจากรันจริง: เรื่องเล่า 151 เรื่องใช้ "เจ้า" 81 ครั้ง ใช้ "สหาย" 0 ครั้ง ทุกคนจึงพูดกันห้วนๆ
    เหมือนคุยกับศัตรูตลอดเวลา ทั้งที่ส่วนใหญ่เป็นคนแปลกหน้าหรือมิตร
    """
    if other.cid == getattr(me, "master_cid", -1):
        return "อาจารย์"
    if other.cid in getattr(me, "disciples", []) or other.cid in getattr(me, "children", []):
        return other.name
    if other.cid == getattr(me, "spouse", None):
        return other.name
    if me.rivals.get(other.cid, 0) > 0:
        return "เจ้า"                       # มีเรื่องบาดหมางกัน ไม่ต้องสุภาพ
    sn = surname(other.name)
    if other.realm - me.realm >= 2 or getattr(other, "title", "") in ("ฮ่องเต้", "แม่ทัพใหญ่"):
        return f"ท่าน{sn}"                  # ขั้นสูงกว่าสองขั้นขึ้นไป หรือมีตำแหน่งใหญ่
    return f"สหาย{sn}"                      # คนทั่วไป เรียกอย่างสุภาพตามธรรมเนียม


def relation_to(me, other, sim, impressions=None):
    """ความสัมพันธ์ของ me ต่อ other เป็นคำพูด"""
    rel = []
    if other.cid == getattr(me, "master_cid", -1):
        rel.append("อาจารย์ของข้า")
    if other.cid in getattr(me, "disciples", []):
        rel.append("ศิษย์ของข้า")
    if other.cid == getattr(me, "spouse", None):
        rel.append("คู่ครองของข้า")
    if other.cid in getattr(me, "parents", []):
        rel.append("บุพการีของข้า")
    if other.cid in getattr(me, "children", []):
        rel.append("ลูกของข้า")
    r = me.rivals.get(other.cid, 0)
    if r >= 5:
        rel.append("ศัตรูคู่อาฆาต")
    elif r > 0:
        rel.append("มีเรื่องบาดหมาง")
    b = me.bonds.get(other.cid, 0)
    if b >= 5:
        rel.append("สนิทสนมผูกพันลึกซึ้ง")
    elif b > 0:
        rel.append("รู้จักมีไมตรี")
    for dbt in getattr(me, "debts", []):
        if not dbt.get("done") and dbt.get("target") == other.cid:
            rel.append(f"ข้าติดค้างเรื่อง{dbt.get('kind', '')}กับเขา")
            break
    if me.org is not None and me.org == other.org:
        rel.append("ร่วมสำนัก")
    if me.clan >= 0 and me.clan == other.clan:
        rel.append("ร่วมตระกูล")
    if impressions and other.cid in impressions:
        rel.append(f"ความรู้สึก: {impressions[other.cid]}")
    return ", ".join(rel) if rel else "คนแปลกหน้า"


def realm_words(sim, ch):
    """ขั้นพลังพร้อม "บันไดเท่าที่เขารู้"

    คนที่ยังไม่เคยข้ามฟ้าไม่รู้ว่าเหนือโลกของตัวเองมีอะไร เขาจึงเห็นแค่เพดานของโลกนี้
    (ขั้นที่ 9 จาก 10) — ส่วนคนที่ข้ามฟ้าไปแล้วเห็นบันไดจริงทั้งเส้น (ขั้นที่ 10 จาก 30) และรู้ว่า
    สิ่งที่ตัวเองไต่มาสุดชีวิตคือขั้นต่ำสุดของที่ใหม่ นี่คือความรู้ที่ต้อง "ไปถึงก่อนจึงจะได้มา"
    """
    from .. import config as C
    line = f"{ch.realm_name()} ({world_name(sim, ch)})"
    if ch.ascends > 0 or ch.tier > 0:
        line += f" — ขั้นที่ {ch.rank()} จาก {C.REALM_TOP + 1} ของบันไดทั้งเส้น"
        if ch.realm == 0 and ch.tier > 0:
            line += " (ข้าเป็นคนที่อ่อนที่สุดของแดนนี้)"
    else:
        line += f" — ขั้นที่ {ch.rank()} จาก {C.REALM_BAND} ของโลกนี้"
        if ch.realm >= C.REALM_CAP:
            line += " (สุดทางของโลกนี้แล้ว เหนือขึ้นไปข้ายังไม่รู้ว่ามีอะไร)"
    if ch.at_bottleneck():
        line += " — สะสมพอจะทะลวงขั้นแล้ว"
    return line


def qi_words(sim, ch):
    """บอกเป็นภาษาคนว่าเลี้ยงตัวไหวไหม ที่นี่เลี้ยงได้ถึงขั้นไหน และในกระเป๋ามีเท่าไร

    ตัวเลขดิบไม่มีความหมายกับโมเดลภาษา สิ่งที่มีความหมายคือคำตัดสิน — "ที่นี่บางเกินกว่า
    จะยึดขั้นของข้าไว้ได้" คือประโยคที่พาไปสู่การตัดสินใจย้ายถิ่น ส่วน "ปราณ 1.85/ปี"
    ไม่พาไปไหนเลย
    """
    
    if ch.realm <= 0:
        return "ยังเป็นปุถุชน ไม่ต้องเลี้ยงปราณในกาย"
    w = sim.world(ch.world_id)
    rho = sim.qi_density(ch.place, w) if hasattr(sim, "qi_density") else C.QI_REFERENCE
    ceiling = EC.place_ceiling(rho)
    held = EC.purse_qi(ch)
    purse = (f"หินวิญญาณติดตัวคิดเป็นปราณ {held:,.0f} หน่วย"
             if held > 0 else "ไม่มีหินวิญญาณติดตัวเลย")
    grip = getattr(ch, "grip", 1.0)
    if ceiling >= ch.realm + 1:
        stand = f"ปราณที่{sim.place_name(ch)}หนาพอเลี้ยงข้าได้สบาย (ถึงขั้นที่ {ceiling:.0f})"
    elif ceiling >= ch.realm:
        stand = f"ปราณที่นี่พอดีกับขั้นของข้า ไม่เหลือให้สะสม (ถึงขั้นที่ {ceiling:.0f})"
    else:
        stand = (f"ปราณที่นี่บางเกินกว่าจะยึดขั้นของข้าไว้ได้ "
                 f"(ที่นี่เลี้ยงได้แค่ขั้นที่ {max(0.0, ceiling):.0f})")
    if grip < 0.35:
        stand += " — พลังในกายเริ่มรวนแล้ว ถ้าไม่หาทางแก้ ขั้นจะถดถอย"
    elif grip < 0.75:
        stand += " — เริ่มยึดขั้นไว้ได้ไม่มั่นเท่าเดิม"
    return f"{stand} · {purse}"


def rank_words(ch) -> str:
    """แปลคะแนนอันดับเป็นคำที่คนในโลกใช้พูดกันจริง (ดู physics.elo_update)"""
    e = float(getattr(ch, "elo", 1500.0) or 1500.0)
    if e >= C.ELO_LEGEND_BAR:
        return f"ชื่อสะเทือนยุทธภพ ({e:.0f} แต้ม)"
    if e >= C.ELO_FAME_BAR:
        return f"มีชื่อในกระดาน ({e:.0f} แต้ม)"
    if e >= 1500.0:
        return f"พอมีคนรู้จัก ({e:.0f} แต้ม)"
    return f"ยังไม่มีใครจดจำ ({e:.0f} แต้ม)"


def self_sheet(sim, ch):
    """ข้อมูลตัวเองแบบที่ตัวละครรู้จักตัวเอง — dict ของบรรทัด (ใช้ทั้งพรอมต์และหน้าอ่าน)"""
    # อารมณ์ถูกคิดแบบ lazy (เหตุการณ์ไหนไม่เกิดกับเขา ก็ไม่มีใครไปคำนวณการสงบให้)
    # ก่อนจะอ่านออกมาเป็นคำจึงต้องดึงกลับเข้าหาฐานใจตามวันที่ผ่านไปก่อน ไม่งั้นพรอมต์จะบอกว่า
    # เขายัง "โกรธท่วมท้น" อยู่ ทั้งที่เรื่องนั้นผ่านมาแปดสิบปีแล้ว — decay() คงที่และไม่ใช้ rng
    EM.decay(ch, sim.day)
    body, mind = health_words(ch)
    age = ch.age(sim.day)
    left = ch.lifespan() - age
    sheet = {
        "ชื่อ": ch.name,
        "เพศ/อายุ": f"{ch.gender} {age} ปี (อายุขัยเหลือราว {max(0, left)} ปี)",
        "เผ่า": ch.race(),
        "ถิ่นกำเนิด": f"{getattr(ch, 'origin', '')} · {getattr(ch, 'tribe', '')}",
        "ขั้นพลัง": realm_words(sim, ch),
        "วิถี": f"{ch.dao} ({', '.join(ch.dao_tags)})" if ch.dao_tags else ch.dao,
        # ห้าธาตุ — บอกทั้งธาตุของตัวเองและวงจรเกิด/ข่ม เพราะตัวละครในโลกนี้รู้กติกานี้กันหมด
        # และมันคือสิ่งที่ตัดสินว่าวิชาไหนฝึกแล้วไปได้ดี และปะทะใครแล้วได้เปรียบ
        "ธาตุประจำตัว": EL.words(ch),
        # อันดับในกระดานยุทธภพ — ชื่อเสียงที่วัดได้จากผลการปะทะจริง ไม่ใช่ตัวนับ
        "ชื่อเสียงในยุทธภพ": rank_words(ch),
        # งบปราณของตัวเอง — **ต้องบอก** ไม่งั้นตัวละครจะถดถอยลงโดยไม่รู้ว่าเพราะอะไร
        # และจะไม่มีวันตัดสินใจย้ายถิ่นหรือหาหินวิญญาณเพื่อแก้ปัญหาที่เขามองไม่เห็น
        # (บทเรียนเดียวกับวิถีหยั่งรู้อนาคตที่เจ้าของไม่รู้ว่าตัวเองมี จึงไม่เคยใช้เลย 29 ปี)
        "ปราณในกายและที่ยืน": qi_words(sim, ch),
        "อาชีพ": getattr(ch, "profession", ""),
        "แนวทางชีวิต": getattr(ch, "archetype", ""),
        "นิสัยเด่น": ", ".join(list(getattr(ch, "traits", [])) + temperament(ch)),
        "ร่างกาย": body,
        "จิตใจ": mind,
        # เจ็ดอารมณ์ หกปรารถนา — "นิสัยเด่น" ข้างบนคือสิ่งที่เขาเป็นมาตลอด สองบรรทัดนี้คือ
        # ใจของเขา **ตอนนี้** ที่เปลี่ยนไปตามสิ่งที่พบเจอ ตัวละครจึงตัดสินใจจากใจวันนี้ ไม่ใช่วันเกิด
        "อารมณ์ในใจตอนนี้": EM.emotion_words(ch),
        "สิ่งที่ใจข้าปรารถนาที่สุด": EM.desire_words(ch),
        "ฐานะ": wealth_words(ch),
    }
    # ระบบจำลองอนาคต — คนที่ "มี" ต้องรู้ว่าตัวเองมี ไม่งั้นก็ไม่มีวันใช้
    # วัดจริงจากโลกปีที่ 89-118: เจ้าของระบบไม่เคยใช้สักครั้งตลอด 29 ปี ทั้งที่ `IN.weigh()` ให้
    # น้ำหนัก 30 และเมนูมีตัวเลือกนี้ทุกครั้ง (วัด 60/60 คน) สาเหตุคือบล็อก [นิมิตที่ข้าเห็น] ใน
    # พรอมต์โผล่เฉพาะตอนที่ "เคยใช้ไปแล้ว" จึงกลายเป็นงูกินหาง — ไม่เคยใช้ ก็ไม่มีนิมิต ก็ไม่มี
    # อะไรในพรอมต์บอกว่าเขามีวิถีนี้ เหลือแต่ชื่อการกระทำลอยๆ ในเมนูที่โมเดล 8B มองข้ามทุกครั้ง
    if getattr(ch, "system_foresight", False) and getattr(C, "FORESIGHT_ON", True):
        _vs = list(getattr(ch, "visions", None) or [])
        if _vs:
            _gap = sim.day - _vs[-1].get("day", 0)
            _hist = f"ครั้งล่าสุดปีที่ {_vs[-1].get('day', 0) // 365}"
            _when = ("ตอนนี้ใช้ได้แล้ว" if _gap >= C.FORESIGHT_COOLDOWN_DAYS
                     else f"ยังใช้ไม่ได้ ต้องรออีกราว {max(1, (C.FORESIGHT_COOLDOWN_DAYS - _gap) // 30)} เดือน")
        else:
            _hist, _when = "ยังไม่เคยใช้เลยสักครั้ง", "ตอนนี้ใช้ได้แล้ว"
        sheet["วิถีพิเศษที่มีอยู่ในตัวข้า"] = (
            "หยั่งรู้อนาคต — ข้ามองเห็นสิ่งที่ยังไม่เกิดได้ปีละครั้ง สิ่งที่เห็นคือสิ่งที่จะเกิดจริง "
            "ถ้าข้าไม่ทำอะไรต่างจากเดิม จ่ายด้วยชะตาหนึ่งแต้มและจิตมารที่หนักขึ้น "
            f"({_hist} · {_when})")
    org = org_name(sim, ch)
    if org:
        sheet["สังกัด"] = f"{org} ({getattr(ch, 'sect_rank', '') or 'สมาชิก'})"
    clan = clan_name(ch)
    if clan:
        sheet["ตระกูล"] = clan
    items = item_names(sim, ch)
    if items:
        sheet["ของติดตัว"] = ", ".join(items)
    skills = list(getattr(ch, "skills", []))[:5]
    if skills:
        sheet["วิชา"] = ", ".join(skills)
    _st = EM.stirred(ch)
    if _st:
        sheet["ใจที่ยังไม่สงบ"] = "ผิดไปจากใจปกติของข้า: " + ", ".join(_st)
    if getattr(ch, "wants", None):
        sheet["กำลังขาด"] = ", ".join(list(ch.wants)[:4])
    if getattr(ch, "spy_for", None) is not None and ch.spy_for < len(sim.orgs):
        sheet["ความลับ"] = f"แท้จริงเป็นไส้ศึกของ{sim.orgs[ch.spy_for].name}"
    if getattr(ch, "hated", None) and ch.hated():
        sheet["สถานะในสังคม"] = "เป็นมนุษย์มาร ถูกผู้คนรังเกียจและตามล่า"
    return sheet


def ties(sim, ch, impressions=None, limit=8):
    """คนสำคัญในชีวิต (ไม่จำเป็นต้องอยู่ใกล้) — อาจารย์ ศิษย์ คู่ครอง ศัตรู มิตร"""
    cids = []
    for cid in ([ch.master_cid] if ch.master_cid >= 0 else []) + list(ch.disciples[:3]):
        cids.append(cid)
    if ch.spouse is not None:
        cids.append(ch.spouse)
    cids += [c for c, _ in sorted(ch.rivals.items(), key=lambda kv: -kv[1])[:3]]
    cids += [c for c, _ in sorted(ch.bonds.items(), key=lambda kv: -kv[1])[:3]]
    seen, out = set(), []
    for cid in cids:
        if cid in seen or cid is None or cid < 0 or cid >= len(sim.cast):
            continue
        seen.add(cid)
        other = sim.cast[cid]
        state = "" if other.alive else " (ล่วงลับแล้ว)"
        out.append(f"{other.name}{state}: {relation_to(ch, other, sim, impressions)}")
        if len(out) >= limit:
            break
    return out


def era_words(sim, ch):
    try:
        w = sim.world(ch.world_id)
        return f"{w.name} ยุคที่ {w.era} — {w.state()}"
    except (IndexError, AttributeError):
        return ""
