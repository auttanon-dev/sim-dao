# -*- coding: utf-8 -*-
"""ค่าแรงตามเวลาทำงาน — เงินที่คนได้ต้องมีคนจ่าย

    from tiandao import wages as WAGES

ก่อนมีไฟล์นี้ งานสามัญทุกอย่าง (กิจวัตร "Working", ทำนา, ค้าขายทั่วไป, ตีเหล็กชาวบ้าน, รักษาชาวบ้าน,
ปกป้องชาวบ้าน, ขูดรีดชาวบ้าน, ลาดตระเวน) เสกเหรียญทองขึ้นมาจาก randint ครั้งละหนึ่งเทิร์น ไม่มีผู้จ่าย
และไม่ผูกกับเวลาที่ทำงาน วัดจากโลก seed 11 ปีที่ 9–19: เงินของคนที่ยังต้องหาเลี้ยงชีพเพิ่มขึ้นมัธยฐานแค่
+0.1 ทองต่อปี เพราะแต่ละคนได้เทิร์นไม่ถึงปีละครั้ง ตลาดข้าวที่ใช้เงินจึงทำไม่ได้เลย
(SIM_DAO_AUTONOMOUS_WORLD_DESIGN_TH.md §6.1, §9.1, invariant 4)

แบบจำลอง: เศรษฐกิจของสถานที่
-----------------------------
ทุนตั้งต้น: ตอนสร้างโลกไม่มีใครมีเหรียญทองเลย เงินทุกเหรียญเคยมาจากการเสกต่อเทิร์น พอเลิกเสก ระบบจึงออกทุน
ตั้งต้น WAGE_START_GOLD ให้คนที่เห็นครั้งแรก (ไม่รวมทารกที่เกิดในโลก) และนับไว้ใน wage_stats["issued"]

ทุกสถานที่มีลิ้นชักเงินของตลาดท้องถิ่น (`Sim.market_till` คีย์เป็น (แดน, สถานที่) เพราะหลายแดนใช้ผัง
สถานที่ชุดเดียวกัน) หนึ่งรอบนาฬิกาโลก:
  1. ใช้จ่าย — ทุกคนที่อยู่ในที่หนึ่งใช้เงินส่วนที่เกินเงินเก็บ (WAGE_KEEP_GOLD) ไปกับของและบริการในที่นั้น
     ในอัตรา WAGE_SPEND_RATE ต่อปี เงินเข้าลิ้นชักของที่นั้น
  2. ค่าแรง — ลิ้นชักจ่ายออกทั้งหมดให้คนที่ทำงานในรอบนี้ ทั้งที่ที่นั้นและที่อื่นในแดนเดียวกันที่ห่างไม่เกิน
     WAGE_REACH_HOPS ก้าว คนที่ใกล้กว่าได้น้ำหนักมากกว่า (1/(1+ก้าว)) ถ้าไม่มีใครทำงานในระยะ เงินค้างในลิ้นชัก
     วัดแล้ว ถ้าจ่ายเฉพาะคนในที่เดียวกัน คนที่อยู่ในที่ที่ไม่มีใครใช้จ่ายไม่มีรายได้เลยและอดตาย ทั้งที่อยู่ห่าง
     ตลาดที่คึกคักแค่ก้าวเดียว
  ค่าครองชีพก้อนเดิมของปุถุชน (rules.upkeep) ไม่ถูกคิดเมื่อเปิดค่าแรง เพราะค่าข้าวกับการใช้จ่ายข้างบนคือค่าครองชีพจริงแล้ว

  คนทำงาน = ผู้ใหญ่ที่ยังต้องหาเลี้ยงชีพ (ต่ำกว่าขั้น FOOD_BIGU_REALM) อยู่กับที่ ไม่ได้เดินทาง ซ่อนตัว ปิดด่าน
  หรือติดคุก เมื่อเปิดระบบอาหารด้วย คนผลิตอาหารได้รายได้จากการขายข้าวแทน (tiandao/food.py) ไม่ได้ค่าแรงซ้ำ

ทุกการเคลื่อนไหวของเงินในไฟล์นี้และในการซื้อข้าว (food.py) เป็นการโอนสองด้าน เงินทองรวมของทุกคน + ลิ้นชัก
ตลาด + ลิ้นชักไร่ ไม่เปลี่ยนจากรอบของค่าแรงและอาหาร (ดู test_wages.py) เหรียญทองเก็บตามชั้นของแดน
(`ch.money[world.tier]`) — โค้ดเก่าบางจุดยังเก็บตาม wid ซึ่งเป็นบั๊กแยกที่ยังไม่ได้แก้ในขั้นนี้
"""
import collections
import math

from . import config as C
from . import household as HH
from . import places as PL
from . import travel as TR

STAT_KEYS = ("issued", "spent", "paid", "food_bought", "farm_paid")
_EPS = 1e-9


def new_stats() -> dict:
    return {k: 0.0 for k in STAT_KEYS}


def tier_of(sim, ch) -> int:
    return sim.world(ch.world_id).tier


def gold(sim, ch) -> float:
    return ch.money.get(tier_of(sim, ch), 0.0)


def record(sim, cause, tier, amount) -> None:
    """บันทึกทองที่เกิด (บวก) หรือหาย (ลบ) จากโลกด้วยสาเหตุ `cause` — ผลรวมทุกสาเหตุต่อชั้นเท่ากับ total_gold เสมอ
    (§6.1: ห้ามสร้างหรือทำลายทองโดยไม่มีบัญชีเหตุผล ดู gold_gap และ test_ledger.py)"""
    if amount:
        flows = sim.__dict__.setdefault("gold_flows", {}).setdefault(cause, {})
        flows[tier] = flows.get(tier, 0.0) + amount


def set_gold(sim, ch, tier, value, cause) -> None:
    """ตั้งทองชั้น `tier` ของคนนี้เป็น `value` เมื่อทองส่วนต่างเกิดหรือหายจากโลก (ไม่ได้ย้ายจากใคร) — บันทึกส่วนต่างเป็น `cause`"""
    record(sim, cause, tier, value - ch.money.get(tier, 0.0))
    ch.money[tier] = value


def clear_gold(sim, ch, cause) -> None:
    """ทองทุกชั้นของคนนี้ออกจากโลก (เช่น ผนึกเข้าแดนลับซึ่งไม่นับในบัญชีทอง) — บันทึกเป็น `cause`"""
    for tier, amount in ch.money.items():
        record(sim, cause, tier, -amount)
    ch.money = {}


def retier(sim, world, old_tier) -> None:
    """แดนเปลี่ยนชั้น (rules: ฟื้นขึ้นชั้นหรือเสื่อมลงชั้น) — เงินตราของแดนเปลี่ยนตาม บันทึกเป็นทองออกจากชั้นเดิมเข้าชั้นใหม่
    (`realm_retier`) บัญชีทองทุกชั้นจึงยังปิด:
    - ลิ้นชักตลาดและไร่ของแดนนี้ (คีย์ด้วยที่ จึงเป็นทองของชั้นใหม่อยู่แล้ว)
    - ทองชั้นเดิมของคนที่มีชีวิตอยู่ในแดนนี้ คลังชุมชนของแดนนี้ และกระเป๋าของครัวเรือนที่บ้านอยู่ในแดนนี้ ย้ายไปชั้นใหม่
      — วัดแล้ว seed 11: แดนหนึ่งเสื่อมจากชั้น 2 เป็น 1 เงินของทุกคนค้างเป็นทองชั้น 2 ที่ใช้ในแดนไม่ได้ เด็ก 13 คนอดตาย
        ภายในสี่เดือนขณะผู้ปกครองอยู่ด้วยและมีทองหลายร้อย"""
    if world.tier == old_tier:
        return
    from . import household as HH
    new = world.tier
    moved = sum(v for till in (sim.market_till, sim.farm_till, getattr(sim, "market_reserve", {}))
                for (wid, _p), v in till.items() if wid == world.wid)
    moved += getattr(sim, "ruin_gold", {}).get(world.wid, 0.0)   # ทองในซากคีย์ด้วยแดน เป็นทองชั้นใหม่ไปด้วย
    purses = ([ch.money for ch in sim.living_in(world.wid)]
              + [t for (wid, _p), t in sorted(getattr(sim, "settlement_treasury", {}).items()) if wid == world.wid]
              + [hh.purse for _hid, hh in sorted(HH._table(sim).items()) if hh.home is not None and hh.home[0] == world.wid])
    for purse in purses:
        gold = purse.pop(old_tier, 0.0)
        if gold:
            purse[new] = purse.get(new, 0.0) + gold
            moved += gold
    record(sim, "realm_retier", old_tier, -moved)
    record(sim, "realm_retier", world.tier, moved)


def market_depth(sim, wid, place) -> float:
    """เงินที่ตลาดของที่นี้รับซื้อของได้มากสุด — ตลาดหรือเมืองลึกกว่าหมู่บ้าน MARKET_DEPTH_CITY เท่า (เพดานของทุนสำรองด้วย)"""
    city = place is not None and 0 <= place < len(PL.PLACES) and PL.PLACES[place][3] in ("ตลาด", "เมือง")
    return C.MARKET_DEPTH_BASE * (1 + sim.world(wid).tier) * (C.MARKET_DEPTH_CITY if city else 1.0)


def settlement_purse(sim, spot):
    """คลังของชุมชนที่ (แดน, สถานที่) {tier: ทอง} — รับมรดกที่ไม่มีทายาท สำนัก หรือตระกูลรับ (Sim.settle_estate)"""
    return sim.__dict__.setdefault("settlement_treasury", {}).setdefault(spot, {})


def gold_gap(sim, tier) -> float:
    """ทองที่มีจริงลบทองตามบัญชีสาเหตุ — ต้องเป็นศูนย์ (ต่างแค่ทศนิยม)"""
    return total_gold(sim, tier) - sum(f.get(tier, 0.0) for f in getattr(sim, "gold_flows", {}).values())


def move_gold(sim, ch, amount) -> None:
    """เพิ่ม (หรือลดเมื่อติดลบ) เหรียญทองของคนนี้ในสกุลของแดนที่เขาอยู่"""
    tier = tier_of(sim, ch)
    ch.money[tier] = ch.money.get(tier, 0.0) + amount


def _present(ch, day) -> bool:
    """อยู่กับที่ในสถานที่หนึ่ง — ใช้จ่ายและทำงานในตลาดของที่นั้นได้"""
    return (ch.alive and not ch.hidden and ch.travel_dest < 0 and ch.place is not None
            and ch.place >= 0 and getattr(ch, "jail_until", 0) <= day)


def earns_wages(ch, day) -> bool:
    """ทำงานรับค่าแรงจากตลาดท้องถิ่นรอบนี้ไหม"""
    if not (_present(ch, day) and ch.age(day) >= 14 and ch.realm < C.FOOD_BIGU_REALM
            and getattr(ch, "sentient", True) and not getattr(ch, "is_beast", False)
            and not getattr(ch, "is_spirit", False) and not getattr(ch, "is_lord", False)):
        return False
    # คนผลิตอาหารได้รายได้จากการขายข้าวแล้ว — ถ้าระบบอาหารปิด เขาก็เป็นแรงงานทั่วไปเหมือนคนอื่น
    return not (C.FOOD_ENABLED and ch.produces_food())


def tick(sim, days) -> None:
    """หนึ่งรอบของตลาดท้องถิ่นทุกแห่ง: ใช้จ่ายเข้าลิ้นชัก แล้วจ่ายค่าแรงออกตามวันทำงาน"""
    if days <= 0:
        return
    day = sim.day
    stats = sim.wage_stats
    spend_share = 1.0 - math.exp(-C.WAGE_SPEND_RATE * days / 365.0)

    workers_at = collections.defaultdict(list)
    for cid in sorted(sim.alive_cids):
        ch = sim.cast[cid]
        if not ch.gold_endowed:
            ch.gold_endowed = True
            # ทุนตั้งต้นเฉพาะคนที่สร้างพร้อมโลก (B3c) — คนที่มาเติมทีหลัง (repopulate ผู้ปกครองใหม่ ฯลฯ) มาตัวเปล่า
            # เดิมได้ทุกคนที่ระบบเห็นครั้งแรก เป็นทองเสกราว 2,900 ต่อปี
            if cid < getattr(sim, "genesis_cast", 0):
                move_gold(sim, ch, C.WAGE_START_GOLD)
                stats["issued"] += C.WAGE_START_GOLD
                record(sim, "start_gold", tier_of(sim, ch), C.WAGE_START_GOLD)
        if not _present(ch, day):
            continue
        spare = gold(sim, ch) - C.WAGE_KEEP_GOLD
        if spare > _EPS:
            spent = spare * spend_share
            move_gold(sim, ch, -spent)
            spot = (ch.world_id, ch.place)
            # ภาษีชุมชน (§7.3 หลังแก้อายุขัย): ส่วนหนึ่งของการใช้จ่ายเข้าคลังชุมชนของที่นั้น — คลังเลี้ยงเด็ก (A5) ได้ทุนสม่ำเสมอ
            # ไม่ต้องรอมรดกของคนตาย วัดแล้ว คลังชุมชนปีแรกเคยได้ ~4,900 ทองจากคนรุ่นแรกที่ตายเพราะบั๊กอายุขัย แก้แล้วเหลือ ~1,150
            levy = spent * C.CIVIC_LEVY
            if levy > 0:
                town = settlement_purse(sim, spot)
                town[tier_of(sim, ch)] = town.get(tier_of(sim, ch), 0.0) + levy
                stats["civic_levy"] = stats.get("civic_levy", 0.0) + levy
            sim.market_till[spot] = sim.market_till.get(spot, 0.0) + spent - levy
            stats["spent"] += spent
        if earns_wages(ch, day):
            workers_at[(ch.world_id, ch.place)].append(ch)

    _mine(sim, workers_at, days)
    _public_works(sim, days)
    _clan_stipends(sim)

    # ทุนสำรองของตลาดไม่เกินของที่คนมาขายที่นี่ในหนึ่งปี (market_demand ลดลงตามเวลา) และไม่เกินความลึก — ส่วนเกินคืนลิ้นชัก
    # จ่ายเป็นค่าแรง (ขั้น B3b) วัดแล้วถ้าใช้ความลึกเป็นเพดานอย่างเดียว ทุนสำรองกองนิ่งแสนกว่าทองใน 50 ปี
    fade = math.exp(-days / 365.0)
    demand = sim.__dict__.setdefault("market_demand", {})
    for spot in sorted(demand):
        demand[spot] *= fade
    for spot in sorted(sim.market_reserve):
        extra = sim.market_reserve[spot] - _reserve_cap(sim, spot)
        if extra > _EPS:
            sim.market_reserve[spot] -= extra
            sim.market_till[spot] = sim.market_till.get(spot, 0.0) + extra
            stats["reserve_released"] = stats.get("reserve_released", 0.0) + extra

    for spot in sorted(sim.market_till):
        till = sim.market_till[spot]
        if till <= _EPS:
            continue
        wid, place = spot
        # ตลาดกันส่วนหนึ่งไว้เป็นทุนรับซื้อของ (ขั้น B3b) ไม่เกินเพดาน ที่เหลือจ่ายเป็นค่าแรง
        reserve = sim.market_reserve.get(spot, 0.0)
        keep = max(0.0, min(till * C.MARKET_RESERVE_SHARE, _reserve_cap(sim, spot) - reserve))
        if keep > 0:
            sim.market_reserve[spot] = reserve + keep
            till -= keep
            sim.market_till[spot] = till
            stats["reserve_kept"] = stats.get("reserve_kept", 0.0) + keep
        payees = [(ch, 1.0) for ch in workers_at.get(spot, ())]
        for other, hops in TR.places_within(sim, place, C.WAGE_REACH_HOPS):
            payees += [(ch, 1.0 / (1.0 + hops)) for ch in workers_at.get((wid, other), ())]
        if not payees:
            continue
        total_w = sum(weight for _ch, weight in payees)
        for ch, weight in payees:                  # ทุกคนทำงานเต็มรอบเท่ากัน ต่างกันแค่ระยะทาง
            move_gold(sim, ch, till * weight / total_w)
            HH.contribute(sim, ch, till * weight / total_w)
        sim.market_till[spot] = 0.0
        stats["paid"] += till


def _public_works(sim, days) -> None:
    """คลังชุมชนจ้างงานสาธารณะ (ขั้น C1) — ทองเหนือพื้น เข้าลิ้นชักตลาดของที่นั้นแล้วจ่ายเป็นค่าแรงตามกฎเดิม

    พื้น = ค่ามื้อของเด็กในระยะส่งข้าวถึง (FOOD_REACH_HOPS) หนึ่งปี — คลังเลี้ยงเด็ก (A5) ก่อนจ้างงานเสมอ
    ใช้ส่วนเหนือพื้น CIVIC_SPEND_RATE ต่อปีแบบลดลงตามเวลา (เหมือนการใช้จ่ายของคน WAGE_SPEND_RATE) เฉพาะทองชั้นของแดนตอนนี้
    วัดแล้ว (B3c) คลังชุมชนนิ่งอยู่ 250k–330k ทองที่ปีที่ 50 ขณะค่าแรงต่ำกว่า B3b ราว 35%"""
    towns = getattr(sim, "settlement_treasury", {})
    if not towns:
        return
    day = sim.day
    kids = collections.Counter()
    for cid in sim.alive_cids:
        ch = sim.cast[cid]
        if ch.age(day) < 14 and ch.place is not None and ch.place >= 0:
            kids[(ch.world_id, ch.place)] += 1
    share = 1.0 - math.exp(-C.CIVIC_SPEND_RATE * days / 365.0)
    meal_year = 365.0 * C.FOOD_RATION_CHILD * C.FOOD_PRICE
    stats = sim.wage_stats
    for spot in sorted(towns):
        wid, place = spot
        tier = sim.world(wid).tier
        bal = towns[spot].get(tier, 0.0)
        if bal <= _EPS or place is None or place < 0:
            continue
        near = kids[spot] + sum(kids[(wid, p)] for p, _h in TR.places_within(sim, place, C.FOOD_REACH_HOPS))
        spend = (bal - near * meal_year) * share
        if spend <= _EPS:
            continue
        towns[spot][tier] = bal - spend
        sim.market_till[spot] = sim.market_till.get(spot, 0.0) + spend
        stats["civic_works"] = stats.get("civic_works", 0.0) + spend


def _clan_stipends(sim) -> None:
    """ศาลบรรพชนเลี้ยงสมาชิกที่ยากจน (ขั้น C2) — ผู้ใหญ่ในตระกูลที่อยู่ในแดนชั้นเดียวกับทองของศาล มีทองชั้นนั้นไม่ถึง WAGE_KEEP_GOLD
    ได้เติมถึง WAGE_KEEP_GOLD จากส่วนที่เหนือพื้น — พื้น = ค่ามื้อเด็กของตระกูลในชั้นนั้น CLAN_FLOOR_YEARS ปี (ศาลเลี้ยงเด็กก่อน food._buy)
    คนที่จนที่สุดได้ก่อน เรียงด้วย cid เมื่อเท่ากัน"""
    halls = getattr(sim, "clan_treasury", {})
    if not halls:
        return
    day = sim.day
    kids, poor = collections.Counter(), collections.defaultdict(list)
    for cid in sorted(sim.alive_cids):
        ch = sim.cast[cid]
        clan = getattr(ch, "clan", -1)
        if clan < 0 or clan not in halls:
            continue
        tier = tier_of(sim, ch)
        if ch.age(day) < 14:
            kids[(clan, tier)] += 1
        elif (getattr(ch, "sentient", True) and not getattr(ch, "is_beast", False)
              and ch.money.get(tier, 0.0) < C.WAGE_KEEP_GOLD):
            poor[(clan, tier)].append(ch)
    meal_year = 365.0 * C.FOOD_RATION_CHILD * C.FOOD_PRICE
    stats = sim.wage_stats
    for (clan, tier), members in sorted(poor.items()):
        hall = halls[clan]
        spare = hall.get(tier, 0.0) - C.CLAN_FLOOR_YEARS * meal_year * kids[(clan, tier)]
        for ch in sorted(members, key=lambda c: (c.money.get(tier, 0.0), c.cid)):
            if spare <= _EPS:
                break
            give = min(C.WAGE_KEEP_GOLD - ch.money.get(tier, 0.0), spare)
            hall[tier] -= give
            ch.money[tier] = ch.money.get(tier, 0.0) + give
            spare -= give
            stats["clan_stipends"] = stats.get("clan_stipends", 0.0) + give


def _reserve_cap(sim, spot) -> float:
    wid, place = spot
    return min(market_depth(sim, wid, place), getattr(sim, "market_demand", {}).get(spot, 0.0))


def is_mine(place) -> bool:
    return place is not None and 0 <= place < len(PL.PLACES) and "เหมือง" in PL.PLACES[place][0]


def _mine(sim, workers_at, days) -> None:
    """ทองที่ขุดได้จากเหมือง — แหล่งกำเนิดทองที่ประกาศ (§6.1 ขั้น B3b) แทนทองที่ตลาดเสกให้คนขายของ

    MINE_GOLD_PER_YEAR ทั้งจักรวาล แบ่งตามจำนวนคนที่ทำงานในเหมืองรอบนี้ ไม่มีใครทำงานที่เหมืองก็ไม่มีทองถูกขุด บันทึก `mine_output`
    ทองเข้ากองทุนเหมืองของชั้นนั้น (`Sim.mine_purse[tier]`) ซึ่งรับซื้อวัตถุดิบที่คนเก็บมาขาย (Sim ค้าขาย) — วัดแล้วถ้าทองจากเหมือง
    เป็นค่าแรงคนงานอย่างเดียว ผู้ฝึกที่หาเงินจากการขายวัตถุดิบจนลง คนที่เห็นตัวเลือกปิดด่านลดจาก 4.2% เหลือ 2.1%
    กองทุนเกินผลผลิตราวหนึ่งปีของชั้นนั้น (`mine_recent`) ส่วนเกินเป็นค่าแรงของคนงานในเหมืองชั้นนั้นรอบนี้"""
    fade = math.exp(-days / 365.0)
    recent = sim.__dict__.setdefault("mine_recent", {})
    for tier in sorted(recent):
        recent[tier] *= fade
    purse = sim.__dict__.setdefault("mine_purse", {})
    total = C.MINE_GOLD_PER_YEAR * days / 365.0
    mines = [(spot, len(chs)) for spot, chs in sorted(workers_at.items()) if chs and is_mine(spot[1])]
    crew = sum(n for _spot, n in mines)
    if total > 0 and crew:
        for spot, n in mines:
            tier, gold = sim.world(spot[0]).tier, total * n / crew
            purse[tier] = purse.get(tier, 0.0) + gold
            recent[tier] = recent.get(tier, 0.0) + gold
            record(sim, "mine_output", tier, gold)
    for tier in sorted(purse):
        extra = purse[tier] - recent.get(tier, 0.0)
        crews = [(spot, n) for spot, n in mines if sim.world(spot[0]).tier == tier]
        if extra <= _EPS or not crews:
            continue
        purse[tier] -= extra
        size = sum(n for _spot, n in crews)
        for spot, n in crews:                          # เข้าลิ้นชักของเหมือง จ่ายเป็นค่าแรงตามกฎเดิม
            sim.market_till[spot] = sim.market_till.get(spot, 0.0) + extra * n / size
        sim.wage_stats["mine_wages"] = sim.wage_stats.get("mine_wages", 0.0) + extra


def fiat_pay(amount):
    """ค่าตอบแทนแบบเดิมที่เสกจากความว่างเปล่า — เมื่อเปิดค่าแรงตามเวลา งานเหล่านี้ไม่จ่ายเงินตรงอีก
    เพราะเวลาที่ทำงานได้ค่าแรงจากตลาดท้องถิ่นแล้ว (ถ้ายังจ่ายซ้ำ จะเป็นเงินสองก้อนสำหรับงานเดียว)"""
    return 0 if C.WAGES_ENABLED else amount


def total_gold(sim, tier) -> float:
    """เหรียญทองทั้งหมดของชั้นนี้ ในมือคน (รวมผู้ตาย) ในลิ้นชักตลาด ลิ้นชักไร่ของแดนชั้นนี้ และทองของผู้ตายที่ถูกย่อ
    เป็นบันทึกแล้ว (Sim.prune_departed) คลังทองของสำนัก (มรดกของสมาชิกที่ไม่มีทายาท) กระเป๋ากลางของครัวเรือน คลังตระกูล
    คลังชุมชน และทองที่ผนึกในแดนลับ"""
    held = sum(ch.money.get(tier, 0.0) for ch in sim.cast)
    tills = sum(v for till in (sim.market_till, sim.farm_till, getattr(sim, "market_reserve", {}))
                for (wid, _place), v in till.items() if sim.world(wid).tier == tier)
    sects = sum(getattr(o, "treasury_gold", {}).get(tier, 0.0) for o in getattr(sim, "orgs", ()))
    return (held + tills + sects + HH.purse_gold(sim, tier) + HH.clan_gold(sim, tier)
            + getattr(sim, "buried_gold", {}).get(tier, 0.0)
            + sum(t.get(tier, 0.0) for t in getattr(sim, "settlement_treasury", {}).values())
            + sum(getattr(k, "gold", {}).get(tier, 0.0) for k in getattr(sim, "caches", ()))    # เซฟก่อนรุ่น 24 ยังไม่มี
            + getattr(sim, "mine_purse", {}).get(tier, 0.0)
            + sum(g for wid, g in getattr(sim, "ruin_gold", {}).items() if sim.world(wid).tier == tier))
