"""ครัวเรือน (แบบ §7.1 ขั้น H1: สมาชิกภาพ ยังไม่มีผลทางเศรษฐกิจ)

ทุกคนที่ยังมีชีวิตอยู่ในครัวเรือนเดียวเสมอ (`check` ตรวจ invariant นี้) คนโสดเป็นครัวเรือนคนเดียว
ครัวเรือนอยู่ใน `sim.households` (hid -> models.Household) และ `Character.household` ชี้กลับ

กฎสมาชิกภาพ — ไม่มีการสุ่ม ทุกทางเรียงด้วย cid:
- คนใหม่ที่ spawn ตั้งครัวเรือนของตัวเอง ทารกย้ายเข้าครัวเรือนของผู้ปกครอง (guardians.assign ทั้งตอนเกิดและตอนเปลี่ยนผู้ปกครอง)
- แต่งงาน (`Sim.marry`): คู่ย้ายเข้าครัวเรือนของอีกฝ่าย พร้อมเด็กในความดูแลของตัวเอง
- ถึง ADULT_AGE (16) แล้วไม่มีพ่อแม่หรือคู่ครองอยู่ในครัวเรือนเดียวกัน แยกไปตั้งครัวเรือนของตัวเอง (`tick`)
- ตาย: ออกจากครัวเรือน หัวหน้าตายแล้วคู่ครอง → สมาชิกที่เติบใหญ่แล้วอายุมากที่สุด → สมาชิกอายุมากที่สุด รับเป็นหัวหน้า
  ไม่เหลือใครแล้วครัวเรือนสลาย
บ้าน (`home`) คือที่อยู่ของหัวหน้า คำนวณทุกครั้ง ไม่เก็บซ้ำ

กระเป๋ากลาง (ขั้น H2): ทองเข้าออกผ่าน `transfer` ทางเดียว ไม่มีทองเกิดหรือหาย (wages.total_gold นับรวม)
- ครัวเรือนที่มีเด็ก: สมาชิกที่มีรายได้และอยู่ในระยะส่งถึงบ้าน (FOOD_REACH_HOPS แดนเดียวกัน) ใส่ HOUSEHOLD_TITHE ของรายได้
  (`contribute`) จนกระเป๋ามีค่าข้าวของเด็กครบ HOUSEHOLD_PURSE_DAYS วัน
- ค่าข้าวของเด็กที่อยู่ในระยะส่งถึงบ้านจ่ายจากกระเป๋าก่อน (`pay_for`) แล้วผู้ปกครอง แล้วหมู่บ้าน (food._buy)
- ย้ายออก: กระเป๋าอยู่กับครัวเรือน คนสุดท้ายย้ายออกก็ถือกระเป๋าไปครัวเรือนใหม่ คนสุดท้ายตายแล้วกระเป๋าเข้าเงินของเขา
  ก่อนแบ่งมรดก (Sim.kill เรียก on_death ก่อน settle_estate)
"""
from . import config as C
from . import travel as TR
from .models import Household


def _table(sim):
    return sim.__dict__.setdefault("households", {})


def of(sim, ch):
    return _table(sim).get(getattr(ch, "household", -1))


def home(sim, hh):
    head = sim.cast[hh.head]
    return head.world_id, head.place


def _merge(purse, into):
    for tier, gold in purse.items():
        if gold:
            into[tier] = into.get(tier, 0.0) + gold


def found(sim, ch):
    """ตั้งครัวเรือนใหม่ที่มี `ch` คนเดียวเป็นหัวหน้า (ออกจากครัวเรือนเดิมก่อน กระเป๋าของครัวเรือนที่เขาทิ้งว่างตามมาด้วย)"""
    left = _leave(sim, ch)
    sim.household_seq = getattr(sim, "household_seq", 0) + 1
    hh = Household(sim.household_seq, ch.cid, [ch.cid], sim.day)
    _merge(left, hh.purse)
    _table(sim)[hh.hid] = hh
    ch.household = hh.hid
    return hh


def join(sim, ch, hh):
    """ย้าย `ch` เข้าครัวเรือน `hh` (กระเป๋าของครัวเรือนที่เขาทิ้งว่างรวมเข้า `hh`)"""
    if getattr(ch, "household", -1) == hh.hid:
        return hh
    _merge(_leave(sim, ch), hh.purse)
    hh.members.append(ch.cid)
    ch.household = hh.hid
    return hh


def _leave(sim, ch):
    """ถอน `ch` ออกจากครัวเรือนปัจจุบัน — หัวหน้าออกแล้วมีผู้รับช่วงตาม `_next_head` ไม่เหลือใครแล้วครัวเรือนสลาย
    คืนกระเป๋าของครัวเรือนที่สลาย (ว่างถ้ายังมีคนอยู่) ให้ผู้เรียกส่งต่อ — ไม่มีทองหาย"""
    table = _table(sim)
    hh = table.get(getattr(ch, "household", -1))
    ch.household = -1
    if hh is None:
        return {}
    if ch.cid in hh.members:
        hh.members.remove(ch.cid)
    if not hh.members:
        del table[hh.hid]
        return hh.purse
    if hh.head == ch.cid:
        hh.head = _next_head(sim, hh, ch)
    return {}


def _next_head(sim, hh, old):
    cast = sim.cast
    if old.spouse is not None and old.spouse in hh.members:
        return old.spouse
    grown = [cast[c] for c in hh.members if getattr(cast[c], "came_of_age", True)]
    pool = grown or [cast[c] for c in hh.members]
    return min(pool, key=lambda c: (c.born_day, c.cid)).cid


def on_death(sim, ch):
    """ออกจากครัวเรือนตอนตาย — เป็นคนสุดท้ายแล้วกระเป๋าเข้าเงินของเขา (Sim.kill เรียกก่อน settle_estate จึงตกทอดตามกฎมรดก)"""
    _merge(_leave(sim, ch), ch.money)


# ---------------------------------------------------------------- กระเป๋ากลาง (ขั้น H2)
def _tier(sim, ch):
    return sim.world(ch.world_id).tier


def transfer(sim, hh, ch, amount, tier):
    """ย้ายทอง `amount` จากเงินของ `ch` เข้ากระเป๋า `hh` (ติดลบ = ออกจากกระเป๋าเข้าเงินของ `ch`) — ทางเดียวของกระเป๋า"""
    ch.money[tier] = ch.money.get(tier, 0.0) - amount
    hh.purse[tier] = hh.purse.get(tier, 0.0) + amount


def in_reach(sim, hh, ch):
    """อยู่ในระยะส่งถึงบ้าน: แดนเดียวกัน อยู่กับที่ (ไม่เดินทาง ซ่อนตัว หรือติดคุก) และไม่เกิน FOOD_REACH_HOPS จากบ้าน"""
    wid, place = home(sim, hh)
    if (ch.world_id != wid or place is None or place < 0 or ch.place is None or ch.place < 0
            or ch.hidden or ch.travel_dest >= 0 or getattr(ch, "jail_until", 0) > sim.day):
        return False
    return ch.place == place or any(p == ch.place for p, _hops in TR.places_within(sim, place, C.FOOD_REACH_HOPS))


def children_of(sim, hh):
    return [sim.cast[c] for c in hh.members if sim.cast[c].age(sim.day) < 14]


def purse_cap(sim, hh):
    """ทองที่กระเป๋ารับได้: ค่าข้าวของเด็กในครัวเรือน HOUSEHOLD_PURSE_DAYS วัน"""
    return len(children_of(sim, hh)) * C.FOOD_RATION_CHILD * C.FOOD_PRICE * C.HOUSEHOLD_PURSE_DAYS


def _stats(sim):
    return sim.__dict__.setdefault("household_stats", {})


def contribute(sim, ch, income):
    """สมาชิกที่เพิ่งได้รายได้ `income` ใส่ส่วน HOUSEHOLD_TITHE เข้ากระเป๋า ถ้าครัวเรือนมีเด็ก เขาอยู่ในระยะส่งถึงบ้าน
    และกระเป๋ายังไม่เต็มเพดาน"""
    hh = of(sim, ch)
    if hh is None or income <= 0 or ch.age(sim.day) < 14 or not children_of(sim, hh) or not in_reach(sim, hh, ch):
        return 0.0
    tier = _tier(sim, ch)
    amount = min(income * C.HOUSEHOLD_TITHE, purse_cap(sim, hh) - hh.purse.get(tier, 0.0), ch.money.get(tier, 0.0))
    if amount <= 0:
        return 0.0
    transfer(sim, hh, ch, amount, tier)
    stats = _stats(sim)
    stats["tithe"] = stats.get("tithe", 0.0) + amount
    return amount


def pay_for(sim, child, cost):
    """จ่ายค่าข้าวของเด็กจากกระเป๋ากลาง (เด็กต้องอยู่ในระยะส่งถึงบ้าน) — คืนทองที่จ่ายได้ ทองออกจากกระเป๋าไปตามทางของผู้เรียก"""
    hh = of(sim, child)
    if hh is None or cost <= 0 or not in_reach(sim, hh, child):
        return 0.0
    tier = _tier(sim, child)
    paid = min(cost, hh.purse.get(tier, 0.0))
    if paid > 0:
        hh.purse[tier] -= paid
        stats = _stats(sim)
        stats["purse_paid"] = stats.get("purse_paid", 0.0) + paid
    return paid


def purse_gold(sim, tier):
    return sum(hh.purse.get(tier, 0.0) for hh in _table(sim).values())


def dependants(sim, ch):
    """คนที่ย้ายตาม `ch` เมื่อเขาย้ายครัวเรือน — เด็กในความดูแลที่อยู่ครัวเรือนเดียวกัน"""
    hh = of(sim, ch)
    if hh is None:
        return []
    return [sim.cast[c] for c in sorted(hh.members)
            if c != ch.cid and sim.cast[c].age(sim.day) < 14 and getattr(sim.cast[c], "guardian", -1) == ch.cid]


def marry(sim, a, b):
    """รวมครัวเรือนตอนแต่งงาน: `b` และเด็กในความดูแลของ `b` ย้ายเข้าครัวเรือนของ `a`"""
    hh = of(sim, a) or found(sim, a)
    for kid in dependants(sim, b):
        join(sim, kid, hh)
    join(sim, b, hh)


def tick(sim):
    """ทุกรอบนาฬิกาโลก: ผู้ใหญ่ (ADULT_AGE) ที่ไม่มีพ่อแม่หรือคู่ครองอยู่ในครัวเรือนเดียวกันแยกไปตั้งครัวเรือนเอง"""
    day, cast = sim.day, sim.cast
    for hid in sorted(_table(sim)):
        hh = _table(sim).get(hid)
        if hh is None or len(hh.members) < 2:
            continue
        for cid in sorted(hh.members):
            ch = cast[cid]
            if cid == hh.head or ch.age(day) < C.ADULT_AGE:
                continue
            family = set(ch.parents or ()) | ({ch.spouse} if ch.spouse is not None else set())
            if not family & set(hh.members):
                found(sim, ch)


def check(sim):
    """ข้อที่ผิด invariant (ว่าง = ถูกทั้งหมด): ทุกคนที่ยังมีชีวิตอยู่ในครัวเรือนเดียว สมาชิกตรงกับที่ตัวละครชี้
    หัวหน้าเป็นสมาชิกที่ยังมีชีวิต ไม่มีครัวเรือนว่าง"""
    problems = []
    table = _table(sim)
    seen = {}
    for hid, hh in table.items():
        if not hh.members:
            problems.append(f"ครัวเรือน {hid} ไม่มีสมาชิก")
        if hh.head not in hh.members:
            problems.append(f"หัวหน้าครัวเรือน {hid} ไม่ได้อยู่ในครัวเรือน")
        for cid in hh.members:
            ch = sim.cast[cid]
            if not ch.alive:
                problems.append(f"คนตาย {cid} ยังอยู่ในครัวเรือน {hid}")
            if cid in seen:
                problems.append(f"{cid} อยู่สองครัวเรือน ({seen[cid]}, {hid})")
            seen[cid] = hid
            if getattr(ch, "household", -1) != hid:
                problems.append(f"{cid} ชี้ไปที่ครัวเรือน {getattr(ch, 'household', -1)} แต่อยู่ใน {hid}")
    for cid in sim.alive_cids:
        if cid not in seen:
            problems.append(f"{cid} ยังมีชีวิตแต่ไม่อยู่ในครัวเรือนไหน")
    return problems


def build(sim):
    """สร้างครัวเรือนจากความสัมพันธ์ที่มีอยู่ (เซฟก่อนรุ่น 17) — ไม่แตะ RNG เรียงด้วย cid
    คู่ครองที่ยังมีชีวิตอยู่ด้วยกัน, เด็กอายุต่ำกว่า 14 อยู่กับผู้ปกครอง (ไม่มีก็พ่อแม่), วัยรุ่นต่ำกว่า ADULT_AGE อยู่กับพ่อแม่ที่ยังมีชีวิต
    นอกนั้นครัวเรือนคนเดียว"""
    cast, day = sim.cast, sim.day
    for hh in _table(sim).values():                    # สร้างใหม่ทั้งหมด — กระเป๋าเดิม (ถ้ามี) เข้าเงินของหัวหน้า ไม่มีทองหาย
        _merge(getattr(hh, "purse", {}), cast[hh.head].money)
    sim.households, sim.household_seq = {}, 0
    living = [cast[c] for c in sorted(sim.alive_cids)]
    for ch in living:
        ch.household = -1
    for ch in living:                                   # ผู้ใหญ่และคู่ครอง
        if ch.age(day) < 14 or ch.household >= 0:
            continue
        if ch.age(day) < C.ADULT_AGE and any(0 <= p < len(cast) and cast[p].alive for p in ch.parents or ()):
            continue
        hh = found(sim, ch)
        mate = cast[ch.spouse] if ch.spouse is not None and 0 <= ch.spouse < len(cast) else None
        if mate is not None and mate.alive and mate.household < 0 and mate.age(day) >= 14:
            join(sim, mate, hh)
    for ch in living:                                   # เด็กและวัยรุ่นที่ยังอยู่กับครอบครัว
        if ch.household >= 0:
            continue
        carers = ([ch.guardian] if ch.age(day) < 14 and getattr(ch, "guardian", -1) >= 0 else []) + list(ch.parents or ())
        host = next((cast[c] for c in carers if 0 <= c < len(cast) and cast[c].alive and cast[c].household >= 0), None)
        if host is not None:
            join(sim, ch, _table(sim)[host.household])
        else:
            found(sim, ch)
