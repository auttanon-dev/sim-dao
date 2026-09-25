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
from . import travel as TR

STAT_KEYS = ("issued", "spent", "paid", "food_bought", "farm_paid")
_EPS = 1e-9


def new_stats() -> dict:
    return {k: 0.0 for k in STAT_KEYS}


def tier_of(sim, ch) -> int:
    return sim.world(ch.world_id).tier


def gold(sim, ch) -> float:
    return ch.money.get(tier_of(sim, ch), 0.0)


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
    return not (C.FOOD_ENABLED and getattr(ch, "profession", "") in C.FOOD_PRODUCERS)


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
            move_gold(sim, ch, C.WAGE_START_GOLD)
            stats["issued"] += C.WAGE_START_GOLD
        if not _present(ch, day):
            continue
        spare = gold(sim, ch) - C.WAGE_KEEP_GOLD
        if spare > _EPS:
            spent = spare * spend_share
            move_gold(sim, ch, -spent)
            spot = (ch.world_id, ch.place)
            sim.market_till[spot] = sim.market_till.get(spot, 0.0) + spent
            stats["spent"] += spent
        if earns_wages(ch, day):
            workers_at[(ch.world_id, ch.place)].append(ch)

    for spot in sorted(sim.market_till):
        till = sim.market_till[spot]
        if till <= _EPS:
            continue
        wid, place = spot
        payees = [(ch, 1.0) for ch in workers_at.get(spot, ())]
        for other, hops in TR.places_within(sim, place, C.WAGE_REACH_HOPS):
            payees += [(ch, 1.0 / (1.0 + hops)) for ch in workers_at.get((wid, other), ())]
        if not payees:
            continue
        total_w = sum(weight for _ch, weight in payees)
        for ch, weight in payees:                  # ทุกคนทำงานเต็มรอบเท่ากัน ต่างกันแค่ระยะทาง
            move_gold(sim, ch, till * weight / total_w)
        sim.market_till[spot] = 0.0
        stats["paid"] += till


def fiat_pay(amount):
    """ค่าตอบแทนแบบเดิมที่เสกจากความว่างเปล่า — เมื่อเปิดค่าแรงตามเวลา งานเหล่านี้ไม่จ่ายเงินตรงอีก
    เพราะเวลาที่ทำงานได้ค่าแรงจากตลาดท้องถิ่นแล้ว (ถ้ายังจ่ายซ้ำ จะเป็นเงินสองก้อนสำหรับงานเดียว)"""
    return 0 if C.WAGES_ENABLED else amount


def total_gold(sim, tier) -> float:
    """เหรียญทองทั้งหมดของชั้นนี้ ในมือคน (รวมผู้ตาย) ในลิ้นชักตลาด และลิ้นชักไร่ของแดนชั้นนี้"""
    held = sum(ch.money.get(tier, 0.0) for ch in sim.cast)
    tills = sum(v for till in (sim.market_till, sim.farm_till)
                for (wid, _place), v in till.items() if sim.world(wid).tier == tier)
    return held + tills
