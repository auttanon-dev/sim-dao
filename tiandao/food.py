# -*- coding: utf-8 -*-
"""อาหาร: ยุ้งฉางหมู่บ้าน — วงจรแรกที่ทำให้ชีวิตมีแหล่งเลี้ยงจริง

    from tiandao import food as FOOD

ก่อนมีไฟล์นี้ คลังพลังงานของร่างกายเติมกลับเข้าหาเต็มเองตามเวลา (body/metabolism.py เขียนไว้เองว่า
"สมมติว่าคนหาอะไรกินได้ตามปกติ") ไม่มีใครผลิตอาหาร ไม่มีใครขาด และภัยแล้งไม่มีผลต่อปากท้อง
(SIM_DAO_AUTONOMOUS_WORLD_DESIGN_TH.md §6.1, §14 vertical slice)

แบบจำลอง
--------
- หน่วย: **สำรับ** = อาหารของผู้ใหญ่หนึ่งคนหนึ่งวัน เด็กกินครึ่งสำรับ
- ใครกิน: คนที่มีจิตและยังต่ำกว่าขั้น FOOD_BIGU_REALM ผู้ถึงขั้นนั้นดำรงกายด้วยปราณ ซึ่งมีต้นทุนอยู่ใน
  ปราณคงขั้นแล้ว ไม่ใช่พลังงานฟรี วิญญาณ อสูร หุ่นเชิด และเจ้าโกลาหลไม่กินข้าว
- ผลิต: คนมีอาชีพผลิตอาหาร (FOOD_PRODUCERS) ที่อยู่กับที่ ไม่ได้เดินทาง ซ่อนตัว หรือปิดด่าน ทำงานบนที่ดินของ
  สถานที่นั้น ผลผลิตโตตามแรงงานแต่อิ่มตัวที่เพดานของที่ดิน (FOOD_LAND_CAP_DAY) คูณฤดูกาล แหล่งที่ประกาศคือการ
  เติบโตตามฤดูของที่นา ไม่ผูกกับคลังทรัพยากรป่า (place_stock/eco_ratio) เพราะคลังนั้นคือสัตว์อสูร แร่ และสมุนไพร
  ขนาด ECO_CAP ที่นักล่าและคนเก็บวัตถุดิบขุดอยู่ ลองผูกแล้ว ที่นาเสื่อมตามการล่าอสูรจนคนอดตายทั้งที่ไม่มีใครทำนาเกิน
- ยุ้งฉาง: ผลผลิตเข้ายุ้งฉางของสถานที่ คนที่อยู่ที่นั่นกินจากยุ้งฉางก่อน ที่ยังขาดรับข้าวจากยุ้งฉางอื่นในแดนเดียวกัน
  ที่ห่างไม่เกิน FOOD_REACH_HOPS ก้าว (ข้าวสูญระหว่างทาง FOOD_CARRY_LOSS_PER_HOP ต่อก้าว) ถ้ายังไม่พอ ทุกคนได้ส่วน
  เท่ากันตามความต้องการ (ไม่ให้ cid ต่ำหรือสถานที่ลำดับต้นได้ก่อน) ที่ขาดกินจากเสบียงติดตัว ของในยุ้งฉางเน่าตามเวลา
- เสบียงติดตัว: เติมได้จากส่วนเกินของยุ้งฉางเท่านั้น ใช้กินตอนเดินทาง ผู้ปิดด่านได้ข้าวส่งถึงถ้ำจากยุ้งฉางของ
  ที่นั้นเหมือนคนในที่นั้น (`_away`) เสบียงติดตัวเป็นแค่สำรอง
- แรงงาน: ที่ที่ข้าวไม่พอแม้รวมข้าวที่ขนมาจากที่ใกล้เคียง ผู้ใหญ่ที่ไม่ได้ผลิตอาหารลงไร่ (`Character.fieldwork`)
  จนพอชดเชยส่วนที่ขาดหรือที่ดินเต็ม แล้วกลับไปทำงานเดิมเมื่อยุ้งฉางของที่นั้นมีข้าวเหลือเฟือ (`_adapt_labour`)
- ขาดอาหาร: นับวันหิวติดกัน คนที่ไม่มีข้าวเหลือในระยะส่งถึงเลย จะเดินทางไปที่ใกล้ที่สุดในแดนเดียวกันที่ยังมีอาหาร
  ผู้ปิดด่านที่ไม่มีข้าวส่งถึงและเสบียงหมดออกจากด่านก่อนกำหนด ถ้าหิวครบ FOOD_STARVE_DAYS จะอดตาย
- ราคา: เมื่อเปิดค่าแรง (WAGES_ENABLED, tiandao/wages.py) ข้าวจากยุ้งฉางราคา FOOD_PRICE ทองต่อสำรับ เงินเข้า
  ลิ้นชักของไร่ต้นทาง แล้วจ่ายให้คนผลิตที่ทำงานที่นั่นรอบนี้ เด็กที่ไม่มีเงินให้พ่อแม่ที่อยู่ที่เดียวกันจ่ายแทน
  ส่วนที่ยังขาด หมู่บ้านเลี้ยงเด็กฟรีจากยุ้งฉาง (นับใน stats["charity"]) — ยังไม่มีระบบผู้ปกครอง และวัดแล้ว
  ถ้าไม่เลี้ยง เด็กกำพร้า (คนที่ repopulate สร้างขึ้นโดยไม่มีพ่อแม่) อดตาย 1,516 จาก 2,238 รายใน 12 ปี ทั้งที่
  ยุ้งฉางมีข้าวค้างสองล้านสำรับ ผู้ใหญ่ที่ซื้อไม่ไหวทำงานให้หมู่บ้านแลกข้าวถ้าทำงานได้ นักโทษได้ข้าวจากคุก (`_relief`)
  นอกนั้นไม่ได้ข้าว ข้าวนั้นอยู่ในยุ้งฉางต่อ
  ปิดค่าแรงอยู่ = ข้าวในยุ้งฉางแจกฟรีแบบเดิม
- ที่อยู่ของยุ้งฉางคือ (แดน, สถานที่) เพราะหลายแดนใช้ผังสถานที่ชุดเดียวกัน (place_key) ยุ้งฉางของแดนหนึ่ง
  ต้องไม่เลี้ยงคนอีกแดน

ทุกอย่างคิดเป็นช่วงบนนาฬิกาโลก (Sim._world_tick) ไม่ใช่ตามเทิร์นตัวละคร คนที่ห่างเทิร์นเป็นปีก็ยังกินทุกเดือน
และเส้นตายอดตายไม่ถูกข้ามเกินหนึ่งรอบนาฬิกา

บัญชีปิดได้เสมอ: เสบียงติดตัวทุกคน + ยุ้งฉางทุกแห่ง
    = endowed + produced − eaten − spoiled − carried_lost − lost   (ดู test_food.py)
"""
import collections
import math

from . import config as C
from . import places as PL
from . import seasons as SEASONS
from . import travel as TR
from . import wages as WAGES
from . import guardians as GUARD

STAT_KEYS = ("endowed", "produced", "eaten", "spoiled", "carried_lost", "lost", "charity",
             "starved", "migrated", "seclusion_cut", "took_up_farming", "left_farming",
             "worked_for_food", "prison_rations", "trip_rations", "trips_put_off")
_AMOUNTS = ("endowed", "produced", "eaten", "spoiled", "carried_lost", "lost", "charity",
            "worked_for_food", "prison_rations", "trip_rations")
_EPS = 1e-9


def new_stats() -> dict:
    return {k: 0.0 if k in _AMOUNTS else 0 for k in STAT_KEYS}


def ledger_balance(stats) -> float:
    """อาหารที่ควรมีอยู่ในโลกตามบัญชี — ต้องเท่ากับ total_held() เสมอ"""
    return (stats["endowed"] + stats["produced"] - stats["eaten"] - stats["spoiled"]
            - stats.get("carried_lost", 0.0) - stats["lost"])


def eats(ch) -> bool:
    """คนนี้ต้องกินข้าวไหม"""
    return (ch.alive and getattr(ch, "sentient", True)
            and not getattr(ch, "is_spirit", False) and not getattr(ch, "is_beast", False)
            and not getattr(ch, "is_lord", False) and ch.realm < C.FOOD_BIGU_REALM)


def ration(ch, day) -> float:
    """สำรับต่อวันที่คนนี้ต้องกิน"""
    return C.FOOD_RATION_CHILD if ch.age(day) < 14 else C.FOOD_RATION_ADULT


def fed_share(ch) -> float:
    """สัดส่วนวันที่กินอิ่ม นับตั้งแต่ร่างกายเดินครั้งก่อน แล้วล้างตัวนับ — ร่างกายถามทุกครั้งที่เดิน

    ปิดระบบอาหารอยู่ หรือคนนี้ไม่ต้องกินข้าว = อิ่มเต็มที่ ร่างกายเติมพลังงานตามปกติ
    """
    if not C.FOOD_ENABLED:
        return 1.0
    fed, missed = ch.food_fed, ch.food_missed
    ch.food_fed = ch.food_missed = 0.0
    total = fed + missed
    return 1.0 if total <= _EPS else fed / total


def _secluded(ch, day) -> bool:
    return bool(ch.hidden) and getattr(ch, "seclude_until", 0) > day


def _away(ch, day) -> bool:
    """ไม่ได้อยู่ในที่ที่มียุ้งฉาง — ต้องกินจากเสบียงติดตัว

    ผู้ปิดด่านไม่นับว่าไม่อยู่: สำนักหรือครอบครัวส่งข้าวถึงถ้ำทุกวัน เขาจึงกินจากยุ้งฉางของที่ที่ปิดด่านอยู่
    (และจ่ายค่าข้าวเมื่อเปิดค่าแรง) เหมือนคนในที่นั้น เสบียงติดตัวเป็นแค่สำรอง ก่อนหน้านี้ผู้ปิดด่านกินจาก
    เสบียงติดตัวอย่างเดียวซึ่งเติมได้ไม่เกิน FOOD_PACK_DAYS เกือบทุกคนจึงออกจากด่านในเดือนแรก ลองให้ตุนเสบียง
    ทั้งช่วงไว้ก่อนเข้าด่านแล้ว ข้าวที่ถูกกักไว้ในถ้ำ 273,000 สำรับทำให้คนข้างนอกอดตายเพิ่มจาก 470 เป็น 607
    การส่งข้าวถึงถ้ำไม่เพิ่มความต้องการรวมเลย เพราะเขาต้องกินอยู่แล้วไม่ว่าจะปิดด่านหรือไม่
    เปิดค่าแรงอยู่ ผู้ปิดด่านจ่ายค่าข้าวแต่ไม่มีรายได้ จึงออกมาหาเลี้ยงชีพก่อนเงินเหลือต่ำกว่าค่าข้าว
    FOOD_SECLUDE_KEEP_DAYS วัน (`_leave_before_broke`) วัดแล้ว ถ้ารอจนเงินหมด ออกมาแล้วอดตายราวสองร้อยคนต่อ seed
    """
    return ch.travel_dest >= 0 or ch.place is None or ch.place < 0


def _able_to_farm(ch, day) -> bool:
    """อยู่ในวัยทำงาน อยู่ที่ที่มีที่ดิน และไม่ได้ซ่อนตัว ปิดด่าน หรือติดคุก"""
    return (ch.alive and ch.age(day) >= 14 and not ch.hidden and not _away(ch, day)
            and getattr(ch, "jail_until", 0) <= day)


def _working(ch, day) -> bool:
    return ch.produces_food() and _able_to_farm(ch, day)


def season_mean(start, days) -> float:
    """ตัวคูณฤดูเฉลี่ยตลอดช่วง [start, start+days) — ช่วงยาวข้ามฤดูไม่ใช้ฤดูของวันสุดท้ายวันเดียว"""
    n = max(1, int(days))
    return sum(SEASONS.regen_multiplier(int(start + i * days // n)) for i in range(n)) / n


def land_output_per_day(workers: int) -> float:
    """สำรับต่อวันจากที่ดินหนึ่งแห่ง — คนแรกๆ ได้เกือบเต็มแรง คนหลังๆ ได้น้อยลงเมื่อที่ดินเริ่มเต็ม"""
    cap = C.FOOD_LAND_CAP_DAY
    return cap * (1.0 - math.exp(-workers * C.FOOD_PER_WORKER_DAY / cap))


def _endow(sim, ch):
    """เสบียงตั้งต้นตอนระบบเห็นคนนี้ครั้งแรก — แหล่งที่ประกาศไว้ นับใน stats['endowed']

    รวม FOOD_START_DAYS วันต่อคนเท่าเดิม แต่ติดตัวแค่ FOOD_PACK_DAYS วัน ที่เหลือเข้ายุ้งฉางของที่ที่เขาอยู่
    ของในยุ้งฉางแบ่งกันกินและขนไปให้ที่ใกล้เคียงได้ ส่วนของติดตัวแบ่งใครไม่ได้ วัดกับเซฟจริงปีที่ 1,228:
    ตอนให้ทั้งหมดติดตัว คนอดตาย 701 คนในห้าปีแรกหลังเปิดระบบ (ปีแรก 366) ส่วนใหญ่เป็นผู้ใหญ่ที่ยังมีเงิน
    """
    total = C.FOOD_START_DAYS * ration(ch, sim.day)
    sim.food_stats["endowed"] += total
    if _away(ch, sim.day):
        ch.food = total
        return
    ch.food = min(total, C.FOOD_PACK_DAYS * ration(ch, sim.day))
    spot = _spot(ch)
    sim.granary[spot] = sim.granary.get(spot, 0.0) + total - ch.food


def _account(sim, ch, need, eaten, days):
    """บันทึกการกินหนึ่งช่วงของคนหนึ่งคน — วันหิวติดกัน และวันอิ่ม/หิวที่ร่างกายจะใช้"""
    sim.food_stats["eaten"] += eaten
    rate = need / days if days > 0 else 0.0
    missed_days = (need - eaten) / rate if rate > 0 else 0.0
    if missed_days <= _EPS:
        ch.hunger_days = 0.0
    elif eaten > _EPS:
        ch.hunger_days = missed_days          # อาหารหมดกลางช่วง ความหิวเพิ่งเริ่มนับ
    else:
        ch.hunger_days += days
    ch.food_fed += days - missed_days
    ch.food_missed += missed_days


def _spot(ch):
    """ยุ้งฉางที่คนนี้กินอยู่ — (แดน, สถานที่)"""
    return (ch.world_id, ch.place)


def tick(sim, days) -> None:
    """หนึ่งรอบของยุ้งฉางทุกแห่ง: เน่า → ผลิต → กิน (และจ่ายค่าข้าว) → เติมเสบียง → จ่ายคนผลิต → ตอบสนองความหิว"""
    if days <= 0:
        return
    day = sim.day
    stats = sim.food_stats

    keep = math.exp(-C.FOOD_SPOIL_PER_YEAR * days / 365.0)
    for spot in sorted(sim.granary):
        lost = sim.granary[spot] * (1.0 - keep)
        sim.granary[spot] -= lost
        stats["spoiled"] += lost

    eaters_at = collections.defaultdict(list)
    away = []
    workers_at = collections.defaultdict(list)
    for cid in sorted(sim.alive_cids):
        ch = sim.cast[cid]
        if _working(ch, day):
            workers_at[_spot(ch)].append(ch)
        if not eats(ch):
            continue
        if ch.food is None:
            _endow(sim, ch)
        (away.append(ch) if _away(ch, day) else eaters_at[_spot(ch)].append(ch))

    season = season_mean(day - days, days)
    for spot in sorted(workers_at):
        made = land_output_per_day(len(workers_at[spot])) * days * season
        sim.granary[spot] = sim.granary.get(spot, 0.0) + made
        stats["produced"] += made

    sources, short = {}, {}
    for spot in sorted(eaters_at):
        total = sum(days * ration(ch, day) for ch in eaters_at[spot])
        take = min(sim.granary.get(spot, 0.0), total)
        sim.granary[spot] = sim.granary.get(spot, 0.0) - take
        sources[spot] = {spot: take}
        if total - take > _EPS:
            short[spot] = total - take
    deficit = dict(short)                   # ส่วนที่ยังขาดหลังรวมข้าวที่ขนมาจากที่ใกล้เคียงแล้ว
    for dest, came in _carry_in(sim, short).items():
        for src, amount in came.items():
            sources[dest][src] = sources[dest].get(src, 0.0) + amount
            deficit[dest] -= amount
    short = set()
    for spot in sorted(eaters_at):
        short |= _feed_place(sim, spot, eaters_at[spot], days, sources[spot])
    for ch in away:
        need = days * ration(ch, day)
        eaten = min(ch.food, need)
        ch.food -= eaten
        _account(sim, ch, need, eaten, days)
    _pay_farmers(sim, workers_at)

    if C.WAGES_ENABLED:
        _leave_before_broke(sim, [ch for spot in sorted(eaters_at) for ch in eaters_at[spot]])

    hungry = [ch for spot in sorted(eaters_at) for ch in eaters_at[spot]] + away
    for ch in sorted(hungry, key=lambda c: c.cid):
        if ch.hunger_days >= C.FOOD_STARVE_DAYS:
            _starve(sim, ch)
        elif ch.hunger_days > 0:
            _respond(sim, ch)
        elif ch.cid in short and not _secluded(ch, day):
            _seek_food(sim, ch)             # ยุ้งฉางเริ่มไม่พอ ออกตอนนี้ขณะยังมีเสบียงพอเดินทาง
    _adapt_labour(sim, eaters_at, workers_at, deficit, days, season)


def _payers(sim, ch):
    """ใครจ่ายค่าข้าวของคนนี้: ตัวเขาเอง แล้วถ้าเป็นเด็ก ผู้ปกครองที่อยู่ด้วย (เปิดระบบผู้ปกครอง)
    หรือพ่อแม่ที่ยังมีชีวิตและอยู่ที่เดียวกัน (ปิดระบบผู้ปกครอง)"""
    payers = [ch]
    if ch.age(sim.day) < 14 and C.GUARDIANS_ENABLED:
        guardian = GUARD.payer(sim, ch)
        return payers + ([guardian] if guardian is not None else [])
    if ch.age(sim.day) < 14:
        for cid in getattr(ch, "parents", ()) or ():
            if 0 <= cid < len(sim.cast):
                parent = sim.cast[cid]
                if parent.alive and _spot(parent) == _spot(ch) and not _away(parent, sim.day):
                    payers.append(parent)
    return payers


def _buy(sim, ch, amount):
    """ซื้อข้าวจากยุ้งฉางได้เท่าไรจาก `amount` ที่แบ่งให้ — คืน (สำรับที่ได้, ทองที่จ่าย)

    ปิดค่าแรงอยู่ = ยุ้งฉางแจกฟรี เปิดค่าแรง = ได้เท่าที่ตัวเองหรือพ่อแม่ (ถ้าเป็นเด็ก) จ่ายไหว
    เด็กได้ส่วนที่ยังขาดฟรีจากหมู่บ้าน ผู้ใหญ่ไม่ได้
    """
    if amount <= _EPS or not C.WAGES_ENABLED:
        return amount, 0.0
    cost = amount * C.FOOD_PRICE
    paid = 0.0
    for payer in _payers(sim, ch):
        part = min(max(0.0, WAGES.gold(sim, payer)), cost - paid)
        if part > 0:
            WAGES.move_gold(sim, payer, -part)
            paid += part
        if cost - paid <= _EPS:
            break
    got = paid / C.FOOD_PRICE
    if ch.age(sim.day) < 14 and amount - got > _EPS:
        sim.food_stats["charity"] += amount - got
        got = amount
    return got, paid


def _relief(sim, ch, amount):
    """ผู้ใหญ่ที่ซื้อข้าวส่วนของตัวเองไม่ไหว — คืนสำรับที่ได้โดยไม่ต้องจ่ายทอง (`amount` คือส่วนที่ยุ้งฉางมีให้แต่เขาซื้อไม่ไหว)

    - ทำงานได้ (อยู่กับที่ ไม่ได้ซ่อนตัว ปิดด่าน หรือติดคุก): ทำงานให้หมู่บ้านแลกข้าวส่วนนั้น (stats['worked_for_food'])
    - ติดคุก: คุกเลี้ยงนักโทษจากยุ้งฉางของที่นั้น (stats['prison_rations']) แบบ §9.4 "คุกต้องมีทรัพยากรเลี้ยงผู้ต้องขัง"
    - นอกนั้น (ซ่อนตัวในแดนลับ) ไม่ได้ ผู้ปิดด่านออกมาหาเลี้ยงชีพก่อนเงินหมดอยู่แล้ว (`_leave_before_broke`)
    วัดกับสำเนาเซฟจริงหลังแก้เทิร์นหลังเข้าด่าน (3 เส้นทาง 100 ปี): ผู้ใหญ่ที่อดตายขณะอยู่กับที่ 1,210 จาก 1,341 คนอยู่ข้างยุ้งฉาง
    ที่มีข้าวพอเขาอย่างน้อย 30 วัน ทุกคนทำงานได้ ตลาดตรงนั้นแทบไม่มีเงินหมุน (มีแค่ 28 ราย) จึงไม่มีค่าแรงให้ซื้อข้าว คนผลิตอาหาร 444 คน
    อดตายข้างข้าวที่ตัวเองปลูก ญาติ ตระกูล หรือสำนักที่มีเงินพอช่วยอยู่ด้วยมีไม่ถึงหนึ่งในสิบ และนักโทษอดตายอีก 288 คน
    ข้าวส่วนนี้นับเป็นข้าวที่กินตามปกติ บัญชีข้าวจึงยังปิด ไร่ไม่ได้เงินจากข้าวส่วนนี้ เหมือนข้าวที่หมู่บ้านเลี้ยงเด็ก
    """
    if amount <= _EPS or ch.age(sim.day) < 14:
        return 0.0
    if getattr(ch, "jail_until", 0) > sim.day:
        sim.food_stats["prison_rations"] += amount
        return amount
    if _able_to_farm(ch, sim.day):
        sim.food_stats["worked_for_food"] += amount
        return amount
    return 0.0


def _feed_place(sim, spot, group, days, sources):
    """แบ่งข้าวที่ได้มาให้คนในที่นี้ตามความต้องการเท่ากันทุกคน ส่วนที่ขาดหรือซื้อไม่ไหวกินจากเสบียงติดตัว

    `sources` คือข้าวที่ได้มารอบนี้แยกตามยุ้งฉางต้นทาง — ค่าข้าวที่จ่ายแบ่งให้ไร่ต้นทางตามสัดส่วนนี้
    คืนเซต cid ของคนที่ยุ้งฉางให้ได้ไม่ครบรอบนี้ (ต้องควักเสบียงติดตัวหรือหิว)
    """
    day = sim.day
    supplied = sum(sources.values())
    need = [days * ration(ch, day) for ch in group]
    total = sum(need)
    share = min(1.0, supplied / total) if total > 0 else 1.0
    taken = paid = 0.0
    short = set()
    for ch, n in zip(group, need):
        got, cost = _buy(sim, ch, n * share)
        got += _relief(sim, ch, n * share - got)
        taken += got
        paid += cost
        if n - got > _EPS:
            short.add(ch.cid)
        from_pack = min(ch.food, n - got)
        ch.food -= from_pack
        _account(sim, ch, n, got + from_pack, days)
    unsold = supplied - taken                    # ส่งมาเกินหรือไม่มีใครรับไป อยู่ในยุ้งฉางที่นี่ต่อ
    if unsold > _EPS:
        sim.granary[spot] = sim.granary.get(spot, 0.0) + unsold
    if paid > 0:
        for src, amount in sorted(sources.items()):
            if amount > 0:
                sim.farm_till[src] = sim.farm_till.get(src, 0.0) + paid * amount / supplied
        sim.wage_stats["food_bought"] += paid

    # เติมเสบียงติดตัวได้จากส่วนที่เกินกว่ายุ้งฉางต้องเก็บไว้เลี้ยงคนในที่นี้เท่านั้น
    keep_level = C.FOOD_GRANARY_KEEP_DAYS * sum(ration(ch, day) for ch in group)
    spare = sim.granary.get(spot, 0.0) - keep_level
    if spare <= 0:
        return short
    want = [max(0.0, C.FOOD_PACK_DAYS * ration(ch, day) - ch.food) for ch in group]
    total_want = sum(want)
    if total_want <= 0:
        return short
    give = min(spare, total_want)
    for ch, w in zip(group, want):
        _sell_to_pack(sim, ch, spot, w * give / total_want)
    return short


def _sell_to_pack(sim, ch, spot, amount):
    """ขายข้าวจากยุ้งฉาง `spot` ใส่เสบียงติดตัวเท่าที่จ่ายไหว — ทองเข้าลิ้นชักของไร่ที่นั้น คืนสำรับที่ได้"""
    got, cost = _buy(sim, ch, amount)
    ch.food += got
    sim.granary[spot] -= got
    if cost > 0:
        sim.farm_till[spot] = sim.farm_till.get(spot, 0.0) + cost
        sim.wage_stats["food_bought"] += cost
    return got


def _pay_farmers(sim, workers_at):
    """ลิ้นชักของไร่จ่ายให้คนผลิตที่ทำงานที่นั่นรอบนี้เท่ากันทุกคน — ไม่มีใครทำงานก็ค้างไว้รอรอบหน้า"""
    for spot in sorted(sim.farm_till):
        till = sim.farm_till[spot]
        farmers = workers_at.get(spot)
        if till <= _EPS or not farmers:
            continue
        for ch in farmers:
            WAGES.move_gold(sim, ch, till / len(farmers))
        sim.farm_till[spot] = 0.0
        sim.wage_stats["farm_paid"] += till


def _adapt_labour(sim, eaters_at, workers_at, deficit, days, season):
    """แรงงานตอบสนองต่อข้าวขาด — การขาดแคลนทำให้คนเปลี่ยนงาน (แบบ §1 ข้อ 5 และตัวอย่างใน §3)

    อาชีพสุ่มครั้งเดียวตอนเกิดและไม่เคยเปลี่ยน แดนสาขาเล็กๆ มีคนผลิตอาหารแค่ 1–4 คน พอมารบุกกินคนผลิตไปก็ไม่มีใคร
    มาแทน วัดกับสำเนาเซฟจริง 3 เส้นทาง 50 ปี: เด็กในแดนที่เหลือคนผลิต 0 คนอดตาย 123–166 ต่อพันคน-ปี แดนที่มี 4 คน
    ขึ้นไป 1–3 ต่อพันคน-ปี เส้นทางที่มารบุกหนักเด็กอดตาย 748 และ 764 คน เส้นทางที่เบากว่า 214 คน
    - ที่ที่ข้าวรอบนี้ไม่พอแม้รวมข้าวที่ขนมาจากที่ใกล้เคียงแล้ว: ผู้ใหญ่ที่ยังอยู่ที่นั่นและไม่ได้ผลิตอาหารลงไร่ คนที่มีเงิน
      น้อยก่อน ทีละคน จนผลผลิตต่อวันของที่นั้นเพิ่มพอชดเชยส่วนที่ขาด หรือจนคนถัดไปเพิ่มผลผลิตได้ไม่ถึงสำรับที่ตัวเอง
      กิน (ที่ดินเต็มแล้ว ลงไปอีกก็ไม่ช่วย)
    - ที่ที่ยุ้งฉางมีข้าวพอเลี้ยงคนที่กินที่นั่นได้ FOOD_DEST_STOCK_DAYS วันแล้ว: คนที่ลงไร่อยู่กลับไปทำงานเดิม
    คิดหลังคนที่มีที่ไปได้ออกเดินทางหาข้าวแล้ว คนที่ลงไร่ทำงานตั้งแต่รอบหน้า (Character.produces_food)
    """
    day = sim.day
    stats = sim.food_stats
    for spot in sorted(workers_at):
        need = sum(ration(ch, day) for ch in eaters_at.get(spot, ()))
        if sim.granary.get(spot, 0.0) < C.FOOD_DEST_STOCK_DAYS * need:
            continue
        for ch in workers_at[spot]:
            if ch.fieldwork:
                ch.fieldwork = False
                stats["left_farming"] += 1
    for spot in sorted(deficit):
        short_per_day = deficit[spot] / days
        if short_per_day <= _EPS:
            continue
        n = len(workers_at.get(spot, ()))
        target = land_output_per_day(n) * season + short_per_day
        idle = sorted((ch for ch in eaters_at[spot] if not ch.produces_food() and _able_to_farm(ch, day)),
                      key=lambda c: (WAGES.gold(sim, c), c.cid))
        for ch in idle:
            output = land_output_per_day(n) * season
            if output >= target or (land_output_per_day(n + 1) * season - output) < C.FOOD_RATION_ADULT:
                break
            ch.fieldwork = True
            stats["took_up_farming"] += 1
            n += 1


def _reach(sim, place):
    """ยุ้งฉางอื่นบนผังเดียวกันที่ส่งข้าวมาถึงที่นี้ได้ — [(สถานที่, ก้าว)]"""
    return TR.places_within(sim, place, C.FOOD_REACH_HOPS)


def _carry_in(sim, short):
    """ส่งข้าวจากยุ้งฉางใกล้เคียงในแดนเดียวกันไปที่ที่ยังขาด — คืน {ปลายทาง: {ต้นทาง: สำรับที่มาถึง}}

    ที่ที่ขาดขอจากทุกยุ้งฉางในระยะ ถ่วงน้ำหนักตามปริมาณที่มีและความใกล้ ยุ้งฉางที่ถูกขอเกินกว่าที่มี
    แบ่งให้ผู้ขอตามสัดส่วนคำขอ ลำดับของสถานที่จึงไม่มีผลว่าใครได้ก่อน ข้าวสูญระหว่างทางตามจำนวนก้าว
    """
    arrived = collections.defaultdict(dict)
    asks = collections.defaultdict(dict)                 # ต้นทาง -> {ปลายทาง: (ขอเท่าไร, ก้าว)}
    for dest in sorted(short):
        wid, place = dest
        sources = [((wid, src), hops) for src, hops in _reach(sim, place)
                   if sim.granary.get((wid, src), 0.0) > _EPS]
        weight = {src: sim.granary[src] / (1.0 + hops) for src, hops in sources}
        total_w = sum(weight.values())
        for src, hops in sources:
            keep = (1.0 - C.FOOD_CARRY_LOSS_PER_HOP) ** hops
            asks[src][dest] = (short[dest] * weight[src] / total_w / keep, hops)
    for src in sorted(asks):
        wanted = sum(amount for amount, _ in asks[src].values())
        scale = min(1.0, sim.granary[src] / wanted) if wanted > 0 else 0.0
        for dest in sorted(asks[src]):
            amount, hops = asks[src][dest]
            sent = amount * scale
            came = sent * (1.0 - C.FOOD_CARRY_LOSS_PER_HOP) ** hops
            sim.granary[src] -= sent
            sim.food_stats["carried_lost"] += sent - came
            arrived[dest][src] = came
    return arrived


def _leave_before_broke(sim, people):
    """ผู้ปิดด่านที่เงินเหลือไม่พอค่าข้าว FOOD_SECLUDE_KEEP_DAYS วัน ออกจากด่านมาหาเลี้ยงชีพ"""
    day = sim.day
    for ch in sorted(people, key=lambda c: c.cid):
        if not _secluded(ch, day):
            continue
        keep = C.FOOD_SECLUDE_KEEP_DAYS * ration(ch, day) * C.FOOD_PRICE
        if WAGES.gold(sim, ch) < keep:
            _end_seclusion(sim, ch, "เงินค่าข้าวใกล้หมด ออกมาหาเลี้ยงชีพ")


def _end_seclusion(sim, ch, reason):
    """ให้ผู้ปิดด่านออกจากด่านวันนี้ — ผลของการปิดด่านคิดตามเวลาที่อยู่จริงตอนเทิร์นออกจากด่าน"""
    ch.seclude_until = sim.day
    ch.seclude_cut = reason
    sim.food_stats["seclusion_cut"] += 1
    sim.requeue(ch, sim.day)


def _starve(sim, ch):
    world = sim.world(ch.world_id)
    where = sim.place_name(ch)
    sim.kill(ch, "อดอาหาร", natural=True)
    sim.food_stats["starved"] += 1
    sim.emit(world, "อดตาย", ch, None, ["ความตาย"], "ตาย",
             f"{ch.name}อดอาหารจนสิ้นใจที่{where}", 0,
             {"วันที่ไม่ได้กิน": f"{ch.hunger_days:.0f} วัน"})


def _respond(sim, ch):
    """คนที่เริ่มหิว: ผู้ปิดด่านออกจากด่าน คนที่ไม่มีข้าวในระยะส่งถึงเลยเดินทางไปหาอาหาร"""
    day = sim.day
    if _secluded(ch, day):
        if ch.food <= _EPS:
            _end_seclusion(sim, ch, "เสบียงหมดก่อนครบกำหนด")
        return
    if ch.age(day) < 14:
        _child_hungry(sim, ch)
        return
    _seek_food(sim, ch)


def _child_hungry(sim, ch):
    """เด็กเดินทางหาข้าวเองไม่ได้ — เด็กที่หิวถูกพาไปหาข้าว

    ผู้ปกครองอยู่ใกล้ข้าว: ไม่ต้องทำอะไร (GUARD.tick พาเด็กไปอยู่ด้วยก่อนมื้อถัดไป หรือข้าวแถวนั้นแค่ไม่พอ ซึ่ง _adapt_labour ดูแล)
    ไม่มีผู้ปกครอง หรือที่ของผู้ปกครองไม่มีข้าวใกล้ๆ: คนที่อยู่ใกล้ข้าวรับไปเลี้ยง (GUARD.refoster) เดิมทำเฉพาะผู้ปกครองที่ไม่ต้อง
    กินข้าว (วิญญาณ ผู้ถึงขั้นงดธัญญาหาร ซึ่งไม่มีวันหิวจึงไม่มีวันย้าย) แต่วัดแล้วผู้ปกครองที่กินข้าวก็ไปไม่ถึงข้าวเกือบทุกราย
    และเด็กที่ไม่มีผู้ปกครองเป็นสองในสามของเด็กที่อดตาย"""
    if not C.GUARDIANS_ENABLED:
        return
    guardian = GUARD.guardian_of(sim, ch)
    if guardian is not None and GUARD.food_near(sim, guardian.world_id, guardian.place):
        return
    GUARD.refoster(sim, ch, guardian)


def _seek_food(sim, ch):
    """ยุ้งฉางแถวนี้เลี้ยงไม่พอ — เดินทางไปที่ใกล้ที่สุดในแดนเดียวกันที่มีข้าวเหลือเฟือ ถ้าไปถึงก่อนอดตาย

    เรียกทั้งตอนเริ่มหิว และตอนที่ยุ้งฉางเริ่มให้ไม่ครบแม้ยังไม่หิว (ต้องควักเสบียงติดตัว) เพราะวัดกับเซฟจริง
    ปีที่ 1,228: คนที่รอจนหิวแล้วค่อยออกเดินทาง ออกไปพร้อมเสบียงศูนย์วัน บนทางที่ใช้มัธยฐาน 61 วัน แต่อดได้แค่
    40 วัน อดตายกลางทาง 173 คนในปีแรก 162 คนในนั้นเป็นการเดินทางที่ไปไม่ถึงตั้งแต่ก่อนออก
    ไปได้ = วันเดินทาง ≤ trip_endurance ไปไม่ถึงก็อยู่ที่เดิม

    คนที่ซ่อนตัวอยู่ไม่ออกเดินทาง: คนติดคุกเดินออกจากคุกไม่ได้ และคนที่เพิ่งถูกตัดด่านยังซ่อนอยู่จนเทิร์นออกจากด่าน
    ถ้าออกเดินทางตอนนี้ เทิร์นที่ควรถึงจุดหมายจะถูกใช้ไปกับการออกจากด่าน (บล็อกซ่อนตัวใน Sim._step มาก่อนบล็อกเดินทาง)
    เขาจึงค้างกลางทางกินแต่เสบียงติดตัว ส่วนคนติดคุกค้างกลางทางไปจนพ้นโทษ คุกเลี้ยงก็ไม่ได้ วัดกับสำเนาเซฟจริง
    3 เส้นทาง 100 ปี: คนที่ย้ายหาข้าวแล้วอดตายกลางทาง 38 คน ทุกคนค้างเลยวันที่ควรถึงแล้ว
    """
    day = sim.day
    if (ch.travel_dest >= 0 or ch.hidden or ch.age(day) < 14
            or ch.place is None or ch.place < 0):
        return
    wid = ch.world_id
    dest = _nearest_food(sim, ch)
    if dest is None:
        return
    place, travel_days = dest
    if travel_days > trip_endurance(ch, day, ch.food):
        return                      # ไปไม่ถึงก่อนอดตาย อยู่รอข้าวที่ส่งมาถึงที่นี่ดีกว่า
    ch.travel_dest = place
    ch.travel_arrival_day = day + travel_days
    sim.food_stats["migrated"] += 1
    sim.requeue(ch, ch.travel_arrival_day)
    sim.emit(sim.world(wid), "ย้ายหาอาหาร", ch, None, ["เดินทาง"], "ออกเดินทาง",
             f"{ch.name}ทิ้ง{sim.place_name(ch)}ที่ยุ้งฉางว่างเปล่า ออกเดินทางไป{PL.PLACES[place][0]}"
             f"ที่ยังมีข้าว", 0, {"ระยะทาง": f"{travel_days} วัน"})


def trip_endurance(ch, day, pack) -> float:
    """วันเดินทางที่ไปได้ก่อนอดตาย ถ้าออกเดินทางพร้อมเสบียงติดตัว `pack` สำรับ —
    วันที่เสบียงพอกิน + วันที่ยังอดได้ − FOOD_TRIP_MARGIN_DAYS"""
    return pack / ration(ch, day) + (C.FOOD_STARVE_DAYS - ch.hunger_days) - C.FOOD_TRIP_MARGIN_DAYS


def provision(sim, ch, travel_days) -> bool:
    """เตรียมเสบียงก่อนออกเดินทาง — คืน False ถ้าเสบียงไม่พอไปถึง (ไม่ควรออกเดินทาง)

    ซื้อข้าวจากยุ้งฉางของที่นี่ใส่เสบียงติดตัวให้พอกินตลอดทางและเผื่อ FOOD_TRIP_MARGIN_DAYS วัน ทางไกลจึงแบกได้เกิน
    FOOD_PACK_DAYS ขายให้ได้เฉพาะส่วนที่เกินกว่ายุ้งฉางต้องเก็บไว้เลี้ยงคนที่อยู่ต่อ เหมือนการเติมเสบียงรายเดือน
    รวมที่ซื้อได้แล้วยังไปไม่ถึงก่อนอดตาย (trip_endurance กฎเดียวกับการย้ายหาข้าว) ก็ไม่ซื้อและไม่ออกเดินทาง

    วันของรอบนี้ที่ผ่านไปแล้ว (นับจาก sim.food_day) นับรวมกับวันเดินทาง เพราะรอบถัดไปคิดมื้อของทั้งรอบกับคนที่อยู่
    กลางทางตอนนั้นจากเสบียงติดตัว ไม่ใช่เฉพาะวันที่เดินทางจริง การย้ายหาข้าวไม่ต้องบวก เพราะออกเดินทางในรอบที่เพิ่ง
    กินจากยุ้งฉางไปแล้ว วัดกับสำเนาเซฟจริง 3 เส้นทาง 100 ปี ก่อนมีการเตรียมเสบียง: อดตายกลางทาง 458 จาก 665
    คนที่อดตาย 254 คนออกเดินทางที่ไปไม่ถึงตั้งแต่ก่อนออก และอีก 165 คนดูไปถึงได้ถ้าไม่นับวันของรอบที่ผ่านไปแล้ว
    (เสบียงมัธยฐาน 15 วัน ทาง 40 วัน ตายวันที่ 35)
    """
    if not eats(ch) or ch.food is None:
        return True     # ระบบยังไม่เคยเห็นคนนี้ — เจอครั้งแรกกลางทางได้เสบียงตั้งต้นติดตัวทั้งหมด (_endow)
    day = sim.day
    travel_days += max(0, day - sim.food_day)
    can = 0.0
    want = (travel_days + C.FOOD_TRIP_MARGIN_DAYS) * ration(ch, day) - ch.food
    if want > _EPS and not _away(ch, day):
        staying = [c for c in sim.living_in(ch.world_id)
                   if c.place == ch.place and c is not ch and eats(c) and not _away(c, day)]
        spare = (sim.granary.get(_spot(ch), 0.0)
                 - C.FOOD_GRANARY_KEEP_DAYS * sum(ration(c, day) for c in staying))
        can = min(want, max(0.0, spare))
        if C.WAGES_ENABLED:
            can = min(can, max(0.0, WAGES.gold(sim, ch)) / C.FOOD_PRICE)
    if travel_days > trip_endurance(ch, day, ch.food + can):
        sim.food_stats["trips_put_off"] += 1
        return False
    if can > _EPS:
        sim.food_stats["trip_rations"] += _sell_to_pack(sim, ch, _spot(ch), can)
    return True


def _nearest_food(sim, ch):
    """ที่ใกล้ที่สุดในแดนเดียวกัน นอกระยะส่งข้าวของที่นี่ ที่ยุ้งฉางมีข้าวเลี้ยงคนที่ไปได้อย่างน้อย
    FOOD_DEST_STOCK_DAYS วัน — คืน (สถานที่, วันเดินทาง) หรือ None (ที่ในระยะส่งอยู่แล้วส่งข้าวมาให้เองได้)"""
    world = sim.world(ch.world_id)
    enough = C.FOOD_DEST_STOCK_DAYS * ration(ch, sim.day)
    in_reach = {p for p, _hops in _reach(sim, ch.place)}
    # เรียงด้วยระยะทางที่แคชไว้ต่อต้นทาง แล้วคิดวันเดินทางเฉพาะที่ที่เลือก — shortest_path_days รัน Dijkstra
    # ใหม่ทุกคู่ การถามทุกสถานที่ของแดนให้ทุกคนที่ข้าวเริ่มไม่พอทำให้ทั้งซิมช้าลงเกือบครึ่ง
    dist = TR.distances_from(ch.place)
    best = None
    for place in PL.places_in(world.place_key):
        stock = sim.granary.get((world.wid, place), 0.0)
        if place == ch.place or place in in_reach or stock < enough or place not in dist:
            continue
        key = (dist[place], -stock, place)
        if best is None or key < best:
            best = key
    if best is None:
        return None
    days = TR.shortest_path_days(ch.place, best[2], ch.realm, character=ch)
    return None if days is None else (best[2], days)


def on_death(sim, ch):
    """เสบียงของผู้ตายตกเป็นของยุ้งฉางที่เขาอยู่ ถ้าตายกลางทางก็สูญไปกับเขา"""
    if ch.food is None or ch.food <= 0:
        return
    if ch.travel_dest >= 0 or ch.place is None or ch.place < 0:
        sim.food_stats["lost"] += ch.food
    else:
        sim.granary[_spot(ch)] = sim.granary.get(_spot(ch), 0.0) + ch.food
    ch.food = 0.0


def total_held(sim) -> float:
    """อาหารทั้งหมดที่มีอยู่ในโลกตอนนี้ — เสบียงติดตัวทุกคน (รวมผู้ตาย) + ยุ้งฉางทุกแห่ง"""
    return (sum(ch.food for ch in sim.cast if ch.food is not None)
            + sum(sim.granary.values()))
