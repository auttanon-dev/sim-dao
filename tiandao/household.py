"""ครัวเรือน (แบบ §7.1 ขั้น H1: สมาชิกภาพ ยังไม่มีผลทางเศรษฐกิจ)

ทุกคนที่ยังมีชีวิตอยู่ในครัวเรือนเดียวเสมอ (`check` ตรวจ invariant นี้) คนโสดเป็นครัวเรือนคนเดียว
ครัวเรือนอยู่ใน `sim.households` (hid -> models.Household) และ `Character.household` ชี้กลับ

กฎสมาชิกภาพ — ไม่มีการสุ่ม ทุกทางเรียงด้วย cid:
- คนใหม่ที่ spawn ตั้งครัวเรือนของตัวเอง ทารกย้ายเข้าครัวเรือนของผู้ปกครอง (guardians.assign ทั้งตอนเกิดและตอนเปลี่ยนผู้ปกครอง)
- แต่งงาน (`Sim.marry`): คู่ย้ายเข้าครัวเรือนของอีกฝ่าย พร้อมเด็กในความดูแลของตัวเอง
- ถึง ADULT_AGE (16) แล้วไม่มีพ่อแม่หรือคู่ครองอยู่ในครัวเรือนเดียวกัน แยกไปตั้งครัวเรือนของตัวเอง (`tick`)
- ตาย: ออกจากครัวเรือน หัวหน้าตายแล้วคู่ครอง → สมาชิกที่เติบใหญ่แล้วอายุมากที่สุด → สมาชิกอายุมากที่สุด รับเป็นหัวหน้า
  ไม่เหลือใครแล้วครัวเรือนสลาย
บ้าน (`Household.home`) เป็นที่ตายตัว (แดน, สถานที่) ตั้งจากที่อยู่ของหัวหน้าตอนตั้งครัวเรือน ย้ายเมื่อหัวหน้าไปอยู่ประจำที่อื่น
(`tick`: อยู่กับที่ ไม่เดินทาง ซ่อนตัว หรือติดคุก) — ข้าวในครัวไม่ย้ายตามคน

กระเป๋ากลาง (ขั้น H2): ทองเข้าออกผ่าน `transfer` ทางเดียว ไม่มีทองเกิดหรือหาย (wages.total_gold นับรวม)
- ครัวเรือนที่มีเด็ก: สมาชิกที่มีรายได้และอยู่ในระยะส่งถึงบ้าน (FOOD_REACH_HOPS แดนเดียวกัน) ใส่ HOUSEHOLD_TITHE ของรายได้
  (`contribute`) จนกระเป๋ามีค่าข้าวของเด็กครบ HOUSEHOLD_PURSE_DAYS วัน
- ค่าข้าวของเด็กที่อยู่ในระยะส่งถึงบ้านจ่ายจากกระเป๋าก่อน (`pay_for`) แล้วผู้ปกครอง แล้วหมู่บ้าน (food._buy)
- ย้ายออก: กระเป๋าอยู่กับครัวเรือน คนสุดท้ายย้ายออกก็ถือกระเป๋าไปครัวเรือนใหม่ คนสุดท้ายตายแล้วกระเป๋าเข้าเงินของเขา
  ก่อนแบ่งมรดก (Sim.kill เรียก on_death ก่อน settle_estate)

ครัว (ขั้น H3): ข้าวในครัว (`Household.larder`) อยู่ที่บ้าน นับใน food.total_held และเน่าอัตราเดียวกับยุ้งฉาง
- เด็กในครัวเรือนที่อยู่ในระยะส่งถึงบ้านกินจากครัวก่อน (`draw`) ส่วนที่ขาดซื้อจากยุ้งฉางตามลำดับเดิม
  (กระเป๋ากลาง → ผู้ปกครอง → หมู่บ้าน) คนที่เดินทาง ซ่อนตัว ติดคุก หรืออยู่แดนอื่นกินจากครัวไม่ได้
- กระเป๋ากลางซื้อข้าวจากยุ้งฉางของที่บ้านเข้าครัว (`stock`) ถึง LARDER_DAYS วันของเด็กในระยะ
  เฉพาะส่วนที่ยุ้งฉางมีเกินระดับที่ต้องเก็บไว้เลี้ยงคนที่นั่น (FOOD_GRANARY_KEEP_DAYS)
- ข้าวไม่ย้ายข้ามที่: บ้านย้าย ครัวเรือนสลาย หรือย้ายเข้าครัวเรือนที่บ้านอยู่ที่อื่น ข้าวในครัวคืนยุ้งฉางของบ้านเดิม
  (`_empty_larder`) ครัวเรือนที่สลายรวมเข้าครัวเรือนที่บ้านอยู่ที่เดียวกัน ข้าวรวมเข้าครัวใหม่

สืบทอด (ขั้น H4): หัวหน้าตาย ครัวเรือนอยู่ต่อพร้อมกระเป๋าและข้าวในครัวครบ ผู้รับช่วงตาม `_next_head`
(คู่ครอง → สมาชิกที่เติบใหญ่แล้วอายุมากสุด → สมาชิกอายุมากสุด) คนสุดท้ายตายโดยไม่มีทายาท (Sim.heirs_of) และอยู่ในตระกูล
กระเป๋าเข้าคลังตระกูล (`sim.clan_treasury[clan]` นับใน wages.total_gold) ไม่งั้นตามกฎมรดกเดิม ข้าวในครัวคืนยุ้งฉางของบ้านเสมอ

ตระกูลสืบผ่านครัวเรือน (§7.4 ขั้น A3) — เดิมได้ตระกูลแค่คนรุ่นแรกที่สุ่มตอนสร้างและลูกทางสายเลือด คนในตระกูลจึงเหลือราว 6–9%:
- แต่งงาน: คู่ที่ย้ายเข้าครัวเรือนรับตระกูลของหัวหน้าครัวเรือน (ถ้าหัวหน้ามีตระกูล) เด็กที่ย้ายตามมาไม่มีตระกูลก็รับด้วย
- รับเลี้ยง: เด็กที่ไม่มีตระกูลรับตระกูลของผู้ปกครอง ไม่มีก็ของหัวหน้าครัวเรือน (`adopt_clan`) เด็กที่มีตระกูลสายเลือดอยู่แล้วคงไว้
- ลูกที่เกิดยังได้ตระกูลจากพ่อแม่ตามเดิม (ส่วนคลอดใน Sim ตั้งชื่อตามตระกูลด้วย) คู่ที่แต่งแล้วอยู่ตระกูลเดียวกัน ลูกจึงได้ตามไปด้วย
"""
from . import config as C
from . import travel as TR
from .models import Household


def _table(sim):
    return sim.__dict__.setdefault("households", {})


def of(sim, ch):
    return _table(sim).get(getattr(ch, "household", -1))


def home(sim, hh):
    return hh.home


def _settled_at(sim, ch):
    """ที่ที่ `ch` อยู่ประจำตอนนี้ (แดน, สถานที่) — None ถ้ากำลังเดินทาง ซ่อนตัว ติดคุก หรือไม่ได้อยู่ในสถานที่"""
    if (ch.place is None or ch.place < 0 or ch.travel_dest >= 0 or ch.hidden
            or getattr(ch, "jail_until", 0) > sim.day):
        return None
    return ch.world_id, ch.place


def _empty_larder(sim, hh):
    """ข้าวในครัวคืนยุ้งฉางของบ้าน — ไม่มีข้าวหาย ไม่มีข้าวย้ายที่"""
    if hh.larder > 0 and hh.home is not None:
        sim.granary[hh.home] = sim.granary.get(hh.home, 0.0) + hh.larder
        stats = _stats(sim)
        stats["larder_returned"] = stats.get("larder_returned", 0.0) + hh.larder
        hh.larder = 0.0


def _absorb(sim, old, hh):
    """ครัวเรือน `old` ที่สลายส่งกระเป๋าเข้า `hh` — ข้าวในครัวรวมเข้าถ้าบ้านอยู่ที่เดียวกัน ไม่งั้นคืนยุ้งฉางบ้านเดิม"""
    if old is None:
        return
    _merge(old.purse, hh.purse)
    if old.home is not None and old.home == hh.home:
        hh.larder += old.larder
        old.larder = 0.0
    else:
        _empty_larder(sim, old)


def _merge(purse, into):
    for tier, gold in purse.items():
        if gold:
            into[tier] = into.get(tier, 0.0) + gold


def found(sim, ch):
    """ตั้งครัวเรือนใหม่ที่มี `ch` คนเดียวเป็นหัวหน้า (ออกจากครัวเรือนเดิมก่อน กระเป๋าของครัวเรือนที่เขาทิ้งว่างตามมาด้วย)"""
    left = _leave(sim, ch)
    sim.household_seq = getattr(sim, "household_seq", 0) + 1
    hh = Household(sim.household_seq, ch.cid, [ch.cid], sim.day, home=_settled_at(sim, ch))
    _absorb(sim, left, hh)
    _table(sim)[hh.hid] = hh
    ch.household = hh.hid
    return hh


def join(sim, ch, hh):
    """ย้าย `ch` เข้าครัวเรือน `hh` (กระเป๋าของครัวเรือนที่เขาทิ้งว่างรวมเข้า `hh`)"""
    if getattr(ch, "household", -1) == hh.hid:
        return hh
    _absorb(sim, _leave(sim, ch), hh)
    hh.members.append(ch.cid)
    ch.household = hh.hid
    return hh


def _leave(sim, ch):
    """ถอน `ch` ออกจากครัวเรือนปัจจุบัน — หัวหน้าออกแล้วมีผู้รับช่วงตาม `_next_head` ไม่เหลือใครแล้วครัวเรือนสลาย
    คืนครัวเรือนที่สลาย (None ถ้ายังมีคนอยู่) ให้ผู้เรียกส่งกระเป๋าและข้าวในครัวต่อ — ไม่มีทองหรือข้าวหาย"""
    table = _table(sim)
    hh = table.get(getattr(ch, "household", -1))
    ch.household = -1
    if hh is None:
        return None
    if ch.cid in hh.members:
        hh.members.remove(ch.cid)
    if not hh.members:
        del table[hh.hid]
        return hh
    if hh.head == ch.cid:
        hh.head = _next_head(sim, hh, ch)
    return None


def _next_head(sim, hh, old):
    cast = sim.cast
    if old.spouse is not None and old.spouse in hh.members:
        return old.spouse
    grown = [cast[c] for c in hh.members if getattr(cast[c], "came_of_age", True)]
    pool = grown or [cast[c] for c in hh.members]
    return min(pool, key=lambda c: (c.born_day, c.cid)).cid


def on_death(sim, ch):
    """ออกจากครัวเรือนตอนตาย — เป็นคนสุดท้ายแล้วกระเป๋าเข้าเงินของเขา (Sim.kill เรียกก่อน settle_estate จึงตกทอดตามกฎมรดก)
    ไม่มีทายาทแต่อยู่ในตระกูล กระเป๋าเข้าคลังตระกูลแทน ข้าวในครัวคืนยุ้งฉางของบ้าน"""
    old = _leave(sim, ch)
    if old is None:
        return
    if getattr(ch, "clan", -1) >= 0 and not sim.heirs_of(ch):
        _merge(old.purse, clan_purse(sim, ch.clan))
        stats = _stats(sim)
        stats["to_clan"] = stats.get("to_clan", 0.0) + sum(old.purse.values())
    else:
        _merge(old.purse, ch.money)
    old.purse = {}
    _empty_larder(sim, old)


def clan_purse(sim, clan):
    """คลังตระกูล {tier: ทอง} (ศาลบรรพชน) — รับกระเป๋าของครัวเรือนที่สลายโดยไม่มีทายาท"""
    return sim.__dict__.setdefault("clan_treasury", {}).setdefault(clan, {})


def clan_gold(sim, tier):
    return sum(t.get(tier, 0.0) for t in getattr(sim, "clan_treasury", {}).values())


# ---------------------------------------------------------------- กระเป๋ากลาง (ขั้น H2)
def _tier(sim, ch):
    return sim.world(ch.world_id).tier


def transfer(sim, hh, ch, amount, tier):
    """ย้ายทอง `amount` จากเงินของ `ch` เข้ากระเป๋า `hh` (ติดลบ = ออกจากกระเป๋าเข้าเงินของ `ch`) — ทางเดียวของกระเป๋า"""
    ch.money[tier] = ch.money.get(tier, 0.0) - amount
    hh.purse[tier] = hh.purse.get(tier, 0.0) + amount


def in_reach(sim, hh, ch):
    """อยู่ในระยะส่งถึงบ้าน: แดนเดียวกัน อยู่กับที่ (ไม่เดินทาง ซ่อนตัว หรือติดคุก) และไม่เกิน FOOD_REACH_HOPS จากบ้าน
    ครัวเรือนที่ยังไม่มีบ้านไม่มีใครอยู่ในระยะ"""
    if hh.home is None:
        return False
    wid, place = hh.home
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


# ---------------------------------------------------------------- ครัว (ขั้น H3)
def larder_food(sim):
    return sum(hh.larder for hh in _table(sim).values())


def spoil(sim, keep):
    """ข้าวในครัวเน่าอัตราเดียวกับยุ้งฉาง (`keep` = ส่วนที่เหลือ) — คืนสำรับที่เน่า"""
    lost = 0.0
    for hid in sorted(_table(sim)):
        hh = _table(sim)[hid]
        gone = hh.larder * (1.0 - keep)
        hh.larder -= gone
        lost += gone
    return lost


def draw(sim, children, days, ration):
    """เด็กที่อยู่ในระยะส่งถึงบ้านกินจากครัวก่อน — คืน {cid: สำรับที่ได้} ครัวไม่พอแบ่งตามสัดส่วนความต้องการ
    `ration(ch)` = สำรับต่อวันของเด็กคนนั้น"""
    wants = {}
    for ch in children:
        hh = of(sim, ch)
        if hh is not None and hh.larder > 0 and in_reach(sim, hh, ch):
            wants.setdefault(hh.hid, []).append((ch, days * ration(ch)))
    fed = {}
    for hid in sorted(wants):
        hh = _table(sim)[hid]
        total = sum(n for _ch, n in wants[hid])
        share = min(1.0, hh.larder / total) if total > 0 else 0.0
        for ch, n in wants[hid]:
            fed[ch.cid] = n * share
        hh.larder = max(0.0, hh.larder - total * share)
    if fed:
        stats = _stats(sim)
        stats["larder_eaten"] = stats.get("larder_eaten", 0.0) + sum(fed.values())
    return fed


def stock(sim, spare, ration):
    """กระเป๋ากลางซื้อข้าวเข้าครัวจากยุ้งฉางของที่บ้าน ถึง LARDER_DAYS วันของเด็กที่อยู่ในระยะส่งถึงบ้าน
    `spare` = {(แดน, สถานที่): ข้าวที่ยุ้งฉางมีเกินระดับที่ต้องเก็บ} ลดลงตามที่ซื้อไป — คืน {บ้าน: ทองที่จ่าย}
    ทองออกจากกระเป๋าไปลิ้นชักของไร่ที่บ้านตามทางของผู้เรียก"""
    paid_at = {}
    stats = _stats(sim)
    for hid in sorted(_table(sim)):
        hh = _table(sim)[hid]
        if hh.home is None or spare.get(hh.home, 0.0) <= 0:
            continue
        kids = [ch for ch in children_of(sim, hh) if in_reach(sim, hh, ch)]
        tier = sim.world(hh.home[0]).tier
        got = min(C.LARDER_DAYS * sum(ration(ch) for ch in kids) - hh.larder,
                  spare[hh.home], hh.purse.get(tier, 0.0) / C.FOOD_PRICE)
        if got <= 0:
            continue
        cost = got * C.FOOD_PRICE
        hh.purse[tier] -= cost
        hh.larder += got
        sim.granary[hh.home] -= got
        spare[hh.home] -= got
        paid_at[hh.home] = paid_at.get(hh.home, 0.0) + cost
        stats["larder_stocked"] = stats.get("larder_stocked", 0.0) + got
    return paid_at


def dependants(sim, ch):
    """คนที่ย้ายตาม `ch` เมื่อเขาย้ายครัวเรือน — เด็กในความดูแลที่อยู่ครัวเรือนเดียวกัน"""
    hh = of(sim, ch)
    if hh is None:
        return []
    return [sim.cast[c] for c in sorted(hh.members)
            if c != ch.cid and sim.cast[c].age(sim.day) < 14 and getattr(sim.cast[c], "guardian", -1) == ch.cid]


def marry(sim, a, b):
    """รวมครัวเรือนตอนแต่งงาน: `b` และเด็กในความดูแลของ `b` ย้ายเข้าครัวเรือนของ `a` และรับตระกูลของหัวหน้า"""
    hh = of(sim, a) or found(sim, a)
    kids = dependants(sim, b)
    for kid in kids:
        join(sim, kid, hh)
    join(sim, b, hh)
    clan = getattr(sim.cast[hh.head], "clan", -1)
    if clan >= 0:
        b.clan = clan
        for kid in kids:
            adopt_clan(sim, kid)


def adopt_clan(sim, child, guardian=None):
    """เด็กที่ยังไม่มีตระกูลรับตระกูลของผู้ปกครอง ไม่มีก็ของหัวหน้าครัวเรือน — คืน True ถ้าได้ตระกูลใหม่"""
    if getattr(child, "clan", -1) >= 0:
        return False
    hh = of(sim, child)
    for giver in (guardian, sim.cast[hh.head] if hh is not None else None):
        if giver is not None and getattr(giver, "clan", -1) >= 0:
            child.clan = giver.clan
            return True
    return False


def backfill_clans(sim):
    """เซฟก่อนรุ่น 22: ครัวเรือนที่หัวหน้ามีตระกูล คู่ครองของหัวหน้ารับตระกูล และคนที่ยังไม่ถึง ADULT_AGE ที่ไม่มีตระกูลรับด้วย
    — กฎเดียวกับการแต่งงานและรับเลี้ยง ไม่แตะ RNG เรียงด้วย hid"""
    cast, day = sim.cast, sim.day
    for hid in sorted(_table(sim)):
        hh = _table(sim)[hid]
        head = cast[hh.head]
        if getattr(head, "clan", -1) < 0:
            continue
        for cid in sorted(hh.members):
            ch = cast[cid]
            if cid == head.spouse or (ch.age(day) < C.ADULT_AGE and getattr(ch, "clan", -1) < 0):
                ch.clan = head.clan


def tick(sim):
    """ทุกรอบนาฬิกาโลก: ผู้ใหญ่ (ADULT_AGE) ที่ไม่มีพ่อแม่หรือคู่ครองอยู่ในครัวเรือนเดียวกันแยกไปตั้งครัวเรือนเอง"""
    day, cast = sim.day, sim.cast
    for hid in sorted(_table(sim)):                    # บ้านย้ายตามที่หัวหน้าไปอยู่ประจำ — ข้าวในครัวคืนยุ้งฉางบ้านเดิม
        hh = _table(sim)[hid]
        at = _settled_at(sim, cast[hh.head])
        if at is not None and at != hh.home:
            _empty_larder(sim, hh)
            hh.home = at
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
    หัวหน้าเป็นสมาชิกที่ยังมีชีวิต ไม่มีครัวเรือนว่าง ข้าวในครัวไม่ติดลบ และมีข้าวได้เฉพาะครัวเรือนที่มีบ้าน"""
    problems = []
    table = _table(sim)
    seen = {}
    for hid, hh in table.items():
        if not hh.members:
            problems.append(f"ครัวเรือน {hid} ไม่มีสมาชิก")
        if hh.head not in hh.members:
            problems.append(f"หัวหน้าครัวเรือน {hid} ไม่ได้อยู่ในครัวเรือน")
        if hh.larder < -1e-9 or (hh.larder > 1e-9 and hh.home is None):
            problems.append(f"ครัวของครัวเรือน {hid} ผิด ({hh.larder} ที่ {hh.home})")
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
    for hh in _table(sim).values():                    # สร้างใหม่ทั้งหมด — กระเป๋าเดิม (ถ้ามี) เข้าเงินของหัวหน้า ข้าวคืนยุ้งฉาง ไม่มีอะไรหาย
        _merge(getattr(hh, "purse", {}), cast[hh.head].money)
        _empty_larder(sim, hh)
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
