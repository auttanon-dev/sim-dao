# -*- coding: utf-8 -*-
"""ฤดูกาลเป็นวัฏจักร — กระทบอัตราฟื้นตัวของระบบนิเวศ (eco regen) และเป็นตัวจุดภัยพิบัติตามฤดู
แทนที่จะให้ทุกอย่างสุ่มล้วนแบบเดิม ใช้กลไก eco (place_stock/ruined/heaven) ที่มีอยู่แล้วใน sim.py
ไม่สร้างระบบเศรษฐกิจคู่ขนานขึ้นมาใหม่
"""
from . import places as PL

DAYS_PER_YEAR = 365
DAYS_PER_SEASON = DAYS_PER_YEAR // 4

# ชื่อฤดู -> (ตัวคูณ eco regen, โอกาสเกิดภัยพิบัติต่อทิกครั้ง (ทุก 30 วัน), ชนิดภัยพิบัติ)
SEASON_TABLE = [
    ("ฤดูใบไม้ผลิ", 1.3, 0.03, None),
    ("ฤดูร้อน",     0.7, 0.12, "ภัยแล้ง"),
    ("ฤดูฝน",       1.5, 0.08, "น้ำท่วม"),
    ("ฤดูหนาว",     0.5, 0.15, "ข้าวยากหมากแพง"),
]


def season_of(day: int):
    """คืน (ชื่อฤดู, ตัวคูณ regen, โอกาสภัยพิบัติ, ชนิดภัยพิบัติ) จากวันกลางของซิม"""
    idx = (day % DAYS_PER_YEAR) // DAYS_PER_SEASON
    idx = min(idx, len(SEASON_TABLE) - 1)
    return SEASON_TABLE[idx]


def regen_multiplier(day: int) -> float:
    return season_of(day)[1]


def _resource_places(world):
    return [i for i in PL.places_in(world.place_key)
            if PL.PLACES[i][3] == "แหล่งวัตถุดิบ"]


def maybe_trigger_disaster(sim, world, rng):
    """สุ่มตามน้ำหนักฤดูปัจจุบัน — ถ้าเกิด คืน Event ที่ถูกบันทึกไว้แล้ว, ไม่งั้นคืน None"""
    if world.kind != "mortal":
        return None
    name, _mult, disaster_p, kind = season_of(sim.day)
    if kind is None or rng.random() >= disaster_p:
        return None

    if kind == "ภัยแล้ง":
        spots = _resource_places(world)
        if not spots:
            return None
        n_hit = max(1, len(spots) // 3)
        for idx in rng.sample(spots, n_hit):
            sim.eco_harvest(idx, sim.place_stock.get(idx, 0.0) * 0.6)
        text = f"{name}แผดเผา{world.name} แหล่งวัตถุดิบ {n_hit} แห่งเหือดแห้งลงหนัก"

    elif kind == "น้ำท่วม":
        spots = _resource_places(world)
        if not spots:
            return None
        idx = rng.choice(spots)
        sim.ruined[idx] = sim.day + 60
        text = f"{name}ซัด{PL.PLACES[idx][0]}ใน{world.name}จนกลายเป็นซากปรักหักพังชั่วคราว"

    else:  # ข้าวยากหมากแพง — ฤดูหนาวโหด กระทบพลังฟ้าดินของโลกโดยตรง
        loss = world.heaven * 0.05
        world.heaven = max(0.0, world.heaven - loss)
        text = f"{name}เหน็บหนาวปกคลุม{world.name} ปุถุชนล้มตายมาก พลังฟ้าดินร่อยหรอลง"

    actor = next(iter(sim.living_in(world.wid)), None)
    if actor is None:
        return None
    return sim.emit(world, "ภัยพิบัติตามฤดู", actor, None,
                     ["ฤดูกาล", kind], kind, text, 0, {"ฤดู": name})
