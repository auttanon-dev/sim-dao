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
- เสบียงติดตัว: เติมได้จากส่วนเกินของยุ้งฉางเท่านั้น ใช้กินตอนเดินทางหรือปิดด่าน
- ขาดอาหาร: นับวันหิวติดกัน คนที่ไม่มีข้าวเหลือในระยะส่งถึงเลย จะเดินทางไปที่ใกล้ที่สุดในแดนเดียวกันที่ยังมีอาหาร
  ผู้ปิดด่านที่เสบียงหมดออกจากด่านก่อนกำหนด ถ้าหิวครบ FOOD_STARVE_DAYS จะอดตาย

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

STAT_KEYS = ("endowed", "produced", "eaten", "spoiled", "carried_lost", "lost",
             "starved", "migrated", "seclusion_cut")
_AMOUNTS = ("endowed", "produced", "eaten", "spoiled", "carried_lost", "lost")
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
    """ไม่ได้อยู่ในที่ที่มียุ้งฉาง — ต้องกินจากเสบียงติดตัว"""
    return ch.travel_dest >= 0 or _secluded(ch, day) or ch.place is None or ch.place < 0


def _working(ch, day) -> bool:
    return (ch.alive and getattr(ch, "profession", "") in C.FOOD_PRODUCERS
            and ch.age(day) >= 14 and not ch.hidden and not _away(ch, day)
            and getattr(ch, "jail_until", 0) <= day)


def season_mean(start, days) -> float:
    """ตัวคูณฤดูเฉลี่ยตลอดช่วง [start, start+days) — ช่วงยาวข้ามฤดูไม่ใช้ฤดูของวันสุดท้ายวันเดียว"""
    n = max(1, int(days))
    return sum(SEASONS.regen_multiplier(int(start + i * days // n)) for i in range(n)) / n


def land_output_per_day(workers: int) -> float:
    """สำรับต่อวันจากที่ดินหนึ่งแห่ง — คนแรกๆ ได้เกือบเต็มแรง คนหลังๆ ได้น้อยลงเมื่อที่ดินเริ่มเต็ม"""
    cap = C.FOOD_LAND_CAP_DAY
    return cap * (1.0 - math.exp(-workers * C.FOOD_PER_WORKER_DAY / cap))


def _endow(sim, ch):
    """เสบียงที่คนติดตัวมาตอนระบบเห็นเขาครั้งแรก — แหล่งที่ประกาศไว้ นับใน stats['endowed']"""
    amount = C.FOOD_START_DAYS * ration(ch, sim.day)
    ch.food = amount
    sim.food_stats["endowed"] += amount


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


def tick(sim, days) -> None:
    """หนึ่งรอบของยุ้งฉางทุกแห่ง: เน่า → ผลิต → กิน → เติมเสบียง → ตอบสนองความหิว"""
    if days <= 0:
        return
    day = sim.day
    stats = sim.food_stats

    keep = math.exp(-C.FOOD_SPOIL_PER_YEAR * days / 365.0)
    for place in sorted(sim.granary):
        lost = sim.granary[place] * (1.0 - keep)
        sim.granary[place] -= lost
        stats["spoiled"] += lost

    eaters_at = collections.defaultdict(list)
    away = []
    workers_at = collections.Counter()
    for cid in sorted(sim.alive_cids):
        ch = sim.cast[cid]
        if _working(ch, day):
            workers_at[ch.place] += 1
        if not eats(ch):
            continue
        if ch.food is None:
            _endow(sim, ch)
        (away.append(ch) if _away(ch, day) else eaters_at[ch.place].append(ch))

    season = season_mean(day - days, days)
    for place in sorted(workers_at):
        made = land_output_per_day(workers_at[place]) * days * season
        sim.granary[place] = sim.granary.get(place, 0.0) + made
        stats["produced"] += made

    supplied, short = {}, {}
    for place in sorted(eaters_at):
        total = sum(days * ration(ch, day) for ch in eaters_at[place])
        take = min(sim.granary.get(place, 0.0), total)
        sim.granary[place] = sim.granary.get(place, 0.0) - take
        supplied[place] = take
        if total - take > _EPS:
            short[place] = total - take
    for place, amount in _carry_in(sim, short).items():
        supplied[place] += amount
    for place in sorted(eaters_at):
        _feed_place(sim, place, eaters_at[place], days, supplied[place])
    for ch in away:
        need = days * ration(ch, day)
        eaten = min(ch.food, need)
        ch.food -= eaten
        _account(sim, ch, need, eaten, days)

    hungry = [ch for place in sorted(eaters_at) for ch in eaters_at[place]] + away
    for ch in sorted(hungry, key=lambda c: c.cid):
        if ch.hunger_days >= C.FOOD_STARVE_DAYS:
            _starve(sim, ch)
        elif ch.hunger_days > 0:
            _respond(sim, ch)


def _feed_place(sim, place, group, days, supplied):
    """แบ่งข้าวที่ได้มาให้คนในที่นี้ตามความต้องการเท่ากันทุกคน ส่วนที่ขาดกินจากเสบียงติดตัว"""
    day = sim.day
    need = [days * ration(ch, day) for ch in group]
    total = sum(need)
    share = min(1.0, supplied / total) if total > 0 else 1.0
    extra = supplied - total * share           # ข้าวที่ส่งมาเกิน (ปัดเศษ) กลับเข้ายุ้งฉางที่นี่
    if extra > _EPS:
        sim.granary[place] = sim.granary.get(place, 0.0) + extra
    for ch, n in zip(group, need):
        got = n * share
        from_pack = min(ch.food, n - got)
        ch.food -= from_pack
        _account(sim, ch, n, got + from_pack, days)

    # เติมเสบียงติดตัวได้จากส่วนที่เกินกว่ายุ้งฉางต้องเก็บไว้เลี้ยงคนในที่นี้เท่านั้น
    keep_level = C.FOOD_GRANARY_KEEP_DAYS * sum(ration(ch, day) for ch in group)
    spare = sim.granary[place] - keep_level
    if spare <= 0:
        return
    want = [max(0.0, C.FOOD_PACK_DAYS * ration(ch, day) - ch.food) for ch in group]
    total_want = sum(want)
    if total_want <= 0:
        return
    give = min(spare, total_want)
    for ch, w in zip(group, want):
        ch.food += w * give / total_want
    sim.granary[place] -= give


_REACH = {}


def _reach(sim, place):
    """ยุ้งฉางอื่นในแดนเดียวกันที่ส่งข้าวมาถึงที่นี้ได้ — [(สถานที่, ก้าว)] เรียงใกล้ไปไกล (กราฟคงที่ แคชได้)"""
    got = _REACH.get((place, C.FOOD_REACH_HOPS))
    if got is None:
        key = PL.PLACES[place][1]
        got = sorted((sim.hops_between(place, other), other) for other in PL.places_in(key)
                     if other != place)
        got = [(other, hops) for hops, other in got if hops <= C.FOOD_REACH_HOPS]
        _REACH[(place, C.FOOD_REACH_HOPS)] = got
    return got


def _carry_in(sim, short):
    """ส่งข้าวจากยุ้งฉางใกล้เคียงไปที่ที่ยังขาด — คืน {สถานที่: สำรับที่มาถึง}

    ที่ที่ขาดขอจากทุกยุ้งฉางในระยะ ถ่วงน้ำหนักตามปริมาณที่มีและความใกล้ ยุ้งฉางที่ถูกขอเกินกว่าที่มี
    แบ่งให้ผู้ขอตามสัดส่วนคำขอ ลำดับของสถานที่จึงไม่มีผลว่าใครได้ก่อน ข้าวสูญระหว่างทางตามจำนวนก้าว
    """
    arrived = collections.defaultdict(float)
    asks = collections.defaultdict(dict)                 # ต้นทาง -> {ปลายทาง: (ขอเท่าไร, ก้าว)}
    for dest in sorted(short):
        sources = [(src, hops) for src, hops in _reach(sim, dest)
                   if sim.granary.get(src, 0.0) > _EPS]
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
            arrived[dest] += came
    return arrived


def _starve(sim, ch):
    world = sim.world(ch.world_id)
    where = sim.place_name(ch)
    sim.kill(ch, "อดอาหาร", natural=True)
    sim.food_stats["starved"] += 1
    sim.emit(world, "อดตาย", ch, None, ["ความตาย"], "ตาย",
             f"{ch.name}อดอาหารจนสิ้นใจที่{where}", 0,
             {"วันที่ไม่ได้กิน": f"{ch.hunger_days:.0f} วัน"})


def _respond(sim, ch):
    """คนที่เริ่มหิว: ผู้ปิดด่านออกจากด่าน คนที่อยู่ในที่ที่ยุ้งฉางว่างเดินทางไปหาอาหาร"""
    day = sim.day
    if _secluded(ch, day):
        if ch.food <= _EPS:
            ch.seclude_until = day
            ch.seclude_cut = True
            sim.food_stats["seclusion_cut"] += 1
            sim.requeue(ch, day)
        return
    if ch.travel_dest >= 0 or ch.age(day) < 14 or ch.place is None or ch.place < 0:
        return
    if sim.granary.get(ch.place, 0.0) > _EPS or any(
            sim.granary.get(src, 0.0) > _EPS for src, _hops in _reach(sim, ch.place)):
        return                      # ยังมีข้าวในระยะส่งถึง แค่ไม่พอ ย้ายไปก็ไปแย่งที่เดียวกัน
    dest = _nearest_food(sim, ch)
    if dest is None:
        return
    place, travel_days = dest
    ch.travel_dest = place
    ch.travel_arrival_day = day + travel_days
    sim.food_stats["migrated"] += 1
    sim.requeue(ch, ch.travel_arrival_day)
    sim.emit(sim.world(ch.world_id), "ย้ายหาอาหาร", ch, None, ["เดินทาง"], "ออกเดินทาง",
             f"{ch.name}ทิ้ง{sim.place_name(ch)}ที่ยุ้งฉางว่างเปล่า ออกเดินทางไป{PL.PLACES[place][0]}"
             f"ที่ยังมีข้าว", 0, {"ระยะทาง": f"{travel_days} วัน"})


def _nearest_food(sim, ch):
    """ที่ใกล้ที่สุดในแดนเดียวกันที่ยุ้งฉางยังมีอาหาร — คืน (สถานที่, วันเดินทาง) หรือ None"""
    world = sim.world(ch.world_id)
    best = None
    for place in PL.places_in(world.place_key):
        if place == ch.place or sim.granary.get(place, 0.0) <= _EPS:
            continue
        days = TR.shortest_path_days(ch.place, place, ch.realm, character=ch)
        if days is None:
            continue
        key = (days, -sim.granary[place], place)
        if best is None or key < best[0]:
            best = (key, place, days)
    return None if best is None else (best[1], best[2])


def on_death(sim, ch):
    """เสบียงของผู้ตายตกเป็นของยุ้งฉางที่เขาอยู่ ถ้าตายกลางทางก็สูญไปกับเขา"""
    if ch.food is None or ch.food <= 0:
        return
    if ch.travel_dest >= 0 or ch.place is None or ch.place < 0:
        sim.food_stats["lost"] += ch.food
    else:
        sim.granary[ch.place] = sim.granary.get(ch.place, 0.0) + ch.food
    ch.food = 0.0


def total_held(sim) -> float:
    """อาหารทั้งหมดที่มีอยู่ในโลกตอนนี้ — เสบียงติดตัวทุกคน (รวมผู้ตาย) + ยุ้งฉางทุกแห่ง"""
    return (sum(ch.food for ch in sim.cast if ch.food is not None)
            + sum(sim.granary.values()))
