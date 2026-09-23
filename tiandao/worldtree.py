# -*- coding: utf-8 -*-
"""แดนลับต้นกำเนิด และต้นไม้โลก — ตัวปรับสมดุลระหว่างแดนเบื้องล่างกับแดนเซียน

ต้นไม้โลกซ่อนตัวอยู่ในแดนลับต้นกำเนิด ไม่มีใครไปถึงได้ด้วยการเดินทางตามปกติ มันเห็นทั้งสองโลกและ
ทำสี่อย่าง — ทั้งสี่อย่างนี้ผูกกับ "ความมีชีวิต" ของมันเอง ซึ่งไม่ใช่ทรัพยากรที่ไม่มีวันหมด:

  1. **แจกของให้โลกที่กำลังเสื่อม** — โลกไหนคลังฟ้าพร่องจนเข้ายุคเสื่อม ต้นไม้จะหย่อนสมุนไพรหายาก
     แร่หายาก วิชาหายาก หรือสมบัติลับลงไปให้ฝั่งนั้น เพื่อดึงสองโลกกลับมาสมดุลกัน
  2. **คัดคนเข้าไปแย่งชิงสมบัติ** — เปิดแดนลับเป็นครั้งคราว ดูดผู้บำเพ็ญจากหลายแดนเข้าไปพร้อมกัน
     มีคนได้ มีคนไม่ได้กลับ
  3. **เป็นต้นกำเนิดของแดนเซียนสาขา** — คนที่รอดออกมาพร้อมวิชาที่ไม่มีใครเคยเห็น บางคนไปตั้งสำนัก
     ของตัวเองจนกลายเป็นดินแดนใหม่ (ดู branches.py — 108 แดนแรกคือคนรุ่นก่อนหน้าที่ทำแบบเดียวกัน)
  4. **ถ้ามันตาย สมดุลสองโลกพัง** — ปราณของทั้งโลกมนุษย์และแดนเซียนรั่วไหลต่อเนื่อง และรอยแยก
     โกลาหลกว้างขึ้นเอง โดยไม่ต้องมีใครมาบุก

ทุกการกระทำของมันกินความมีชีวิตของตัวเอง และมันฟื้นช้ากว่าที่ใช้ ถ้าโลกเสื่อมถี่เกินไปจนมันต้อง
แจกของตลอดเวลา มันจะตายเพราะพยายามช่วย — ซึ่งเป็นโศกนาฏกรรมที่ตั้งใจให้เป็นไปได้จริง
"""
from . import config as C
from . import crafting as CR
from . import skills as SK
from .models import Item


def capacity(sim) -> float:
    """เพดานความมีชีวิตของต้นไม้ — โตตามจำนวนแดนที่ยังยืนอยู่

    ต้นไม้โลกไม่ได้เลี้ยงสองโลกเฉยๆ มันหยั่งรากอยู่กับทุกแดนที่ยังมีชีวิต ยิ่งมีแดนมากและแดนเหล่านั้น
    ไม่ถูกทำลาย มันก็ยิ่งดูดปราณจากเครือข่ายที่กว้างขึ้นมาเลี้ยงตัวเองได้มากขึ้น — และนี่คือเหตุผลที่
    การตั้งแดนสาขาใหม่ไม่ได้เป็นแค่ของประดับ มันทำให้ตัวปรับสมดุลของจักรวาลแข็งแรงขึ้นจริง
    "แดนที่ยังยืนอยู่" นับเฉพาะแดนที่ยังมีคนอยู่ ถ้าแดนไหนร้างคนหมด รากที่หยั่งไว้ตรงนั้นก็ตายไปด้วย
    """
    standing = sum(1 for w in sim.worlds if w.kind == "mortal" and w.n_alive > 0)
    return C.TREE_VITALITY_BASE + C.TREE_VITALITY_PER_REALM * standing


def regen_rate(sim) -> float:
    """อัตราฟื้นต่อปี — โตตามเพดานด้วย ไม่งั้นเพดานที่สูงขึ้นก็ไปไม่ถึงอยู่ดี"""
    return C.TREE_REGEN_PER_YEAR * (capacity(sim) / C.TREE_VITALITY_BASE)


def init(sim) -> None:
    """ตั้งค่าเริ่มต้น — เรียกซ้ำได้ปลอดภัย ใช้กับเซฟเก่าที่ยังไม่มีฟิลด์พวกนี้ด้วย"""
    if not hasattr(sim, "tree_vitality"):
        sim.tree_vitality = capacity(sim)
        sim.tree_alive = True
        sim.tree_last_tick = 0
        sim.tree_gifts = 0
        sim.tree_trials = 0
        sim.tree_founded = 0
        sim.tree_peak = sim.tree_vitality


def _worlds_in_decline(sim):
    """โลกที่ต้นไม้แล 'สองฝั่ง' อยู่ — แดนเบื้องล่าง (โลกมนุษย์) กับแดนเซียนหลัก"""
    watch = []
    for w in sim.worlds:
        if w.wid in (0, 1) and w.kind == "mortal":
            watch.append(w)
    return [w for w in watch if w.ratio() < C.TREE_DECLINE_AT]


def _gift_for(sim, world, rng):
    """หย่อนของหายากลงให้โลกที่กำลังเสื่อม — คืน (ผู้รับ, คำอธิบายของ) หรือ None"""
    people = [c for c in sim.living_in(world.wid) if c.alive]
    if not people:
        return None
    # ให้คนที่ "พอจะใช้ของเป็น" ไม่ใช่สุ่มทั้งโลก — ไม่งั้นสมบัติหายไปกับชาวบ้านที่ไม่เคยบำเพ็ญ
    # กิ่งที่หยั่งลงมาไม่ได้ให้แค่ของชิ้นเดียวกับคนเดียว — แร่และสมุนไพรที่โผล่ตามมาทั้งแดนคือ
    # ทรัพยากรของแดนนั้น ทำให้แดนที่ต้นไม้โลกเลือกบ่อยรวยขึ้นจริง และออกทุนผนึกได้โดยไม่ล้ม
    world.resource = min(C.REALM_RESOURCE_MAX,
                         getattr(world, "resource", C.REALM_RESOURCE_INIT)
                         + C.REALM_RESOURCE_GIFT)
    people.sort(key=lambda c: -(c.realm * 10 + len(c.skills)))
    who = rng.choice(people[:max(3, len(people) // 10)])
    roll = rng.random()
    if roll < 0.35:
        name = rng.choice(CR.HERBS)[0] if CR.HERBS else "สมุนไพรบรรพกาล"
        who.mat_stock[name] = who.mat_stock.get(name, 0) + rng.randint(2, 5)
        return who, f"สมุนไพรหายาก {name}"
    if roll < 0.65:
        name = rng.choice(CR.ORES)[0] if CR.ORES else "แร่บรรพกาล"
        who.mat_stock[name] = who.mat_stock.get(name, 0) + rng.randint(2, 5)
        return who, f"แร่หายาก {name}"
    if roll < 0.88:
        pool = [x for x in SK.by_tier_grade(min(world.tier + 1, 2), 2) if x[0] not in who.skills]
        if pool:
            sk = rng.choice(pool)
            who.learn_skill(sk[0])
            return who, f"วิชาหายาก {sk[0]}"
        return None
    iid = sim.nid("i")
    it = Item(iid=iid, name=f"สมบัติลับแห่งต้นไม้โลก", kind="ของใช้",
              grade=rng.uniform(3.0, 6.0), tier=world.tier, cooldown=rng.randint(2, 6))
    sim.items[iid] = it
    who.items.append(iid)
    return who, f"สมบัติลับ {it.name} (ชั้น {it.grade:.1f})"


def tick(sim, rng) -> None:
    """งานประจำของต้นไม้โลก — เรียกจาก sim.step() ทุกช่วง TREE_TICK_DAYS"""
    init(sim)
    if sim.day - sim.tree_last_tick < C.TREE_TICK_DAYS:
        return
    elapsed = sim.day - sim.tree_last_tick
    sim.tree_last_tick = sim.day

    if not sim.tree_alive:
        _collapse(sim, elapsed)
        return

    cap = capacity(sim)
    sim.tree_vitality = min(cap, sim.tree_vitality + regen_rate(sim) * elapsed / 365.0)
    sim.tree_peak = max(getattr(sim, "tree_peak", 0.0), sim.tree_vitality)

    # 1) แจกของให้ฝั่งที่กำลังเสื่อม
    for w in _worlds_in_decline(sim):
        if sim.tree_vitality < C.TREE_GIFT_COST or rng.random() > C.TREE_GIFT_P:
            continue
        got = _gift_for(sim, w, rng)
        if got is None:
            continue
        who, what = got
        sim.tree_vitality -= C.TREE_GIFT_COST
        sim.tree_gifts += 1
        sim.emit(w, "ต้นไม้โลกหยั่งกิ่ง", who, None, ["สมบัติ"], "ได้รับ",
                 f"ต้นไม้โลกในแดนลับต้นกำเนิดหยั่งกิ่งลงสู่{w.name}ที่กำลังเสื่อม "
                 f"หย่อน{what}ให้{who.name}", 0,
                 {"เหตุที่หยั่ง": f"{w.name} {w.state()} (คลังฟ้าเหลือ {w.ratio()*100:.0f}%)",
                  "ความมีชีวิตของต้นไม้": f"{sim.tree_vitality:.0f}/{cap:.0f}"})

    # 2) เปิดแดนลับ คัดคนเข้าไปแย่งชิงสมบัติ
    if sim.tree_vitality >= C.TREE_TRIAL_COST and rng.random() < C.TREE_TRIAL_P:
        _trial(sim, rng)

    if sim.tree_vitality <= 0:
        sim.tree_alive = False
        sim.emit(sim.worlds[0], "ต้นไม้โลกดับสูญ", None, None, ["ทำลาย", "ความตาย"], "ดับสูญ",
                 "ต้นไม้โลกในแดนลับต้นกำเนิดเหี่ยวเฉาจนดับสูญ "
                 "สมดุลระหว่างแดนเบื้องล่างกับแดนเซียนขาดสะบั้น", 0,
                 {"ผลที่ตามมา": "ปราณของทั้งสองโลกรั่วไหลต่อเนื่อง และรอยแยกโกลาหลกว้างขึ้นเอง",
                  "แจกของไปแล้ว": sim.tree_gifts, "เปิดแดนลับไปแล้ว": sim.tree_trials})


def _trial(sim, rng) -> None:
    """คัดผู้บำเพ็ญจากหลายแดนเข้าไปแย่งชิงสมบัติในแดนลับ"""
    pool = [c for c in sim.living()
            if sim.world(c.world_id).kind == "mortal" and c.realm >= C.TREE_TRIAL_REALM
            and not c.hidden]
    if len(pool) < C.TREE_TRIAL_MIN:
        return
    pool.sort(key=lambda c: c.cid)          # เรียงให้ผลคงที่ก่อนสุ่ม (ดู test_determinism)
    chosen = rng.sample(pool, min(C.TREE_TRIAL_SIZE, len(pool)))
    sim.tree_vitality -= C.TREE_TRIAL_COST
    sim.tree_trials += 1

    chosen.sort(key=lambda c: -(c.realm * 10 + len(c.skills) + c.insight))
    winner = chosen[0]
    iid = sim.nid("i")
    it = Item(iid=iid, name="ผลไม้ต้นกำเนิด", kind="ยาวิเศษ",
              grade=rng.uniform(4.0, 7.0), tier=1, cooldown=1)
    it.pill_bonus = C.PILL_BREAK_BONUS * 2
    from . import crafting as CR
    it.lifespan_bonus = CR.longevity_years(it.name, it.tier, 2)
    sim.items[iid] = it
    winner.items.append(iid)
    winner.insight += 25

    fallen = []
    for c in chosen[1:]:
        if rng.random() < C.TREE_TRIAL_DEATH_P and c.fate <= 0:
            sim.kill(c, "ดับสูญในแดนลับต้นกำเนิด", killer=winner)
            fallen.append(c.name)
        elif c.alive:
            c.insight += 5
            c.rivals[winner.cid] = c.rivals.get(winner.cid, 0) - 2

    d = {"ผู้ถูกคัดเข้าไป": " · ".join(c.name for c in chosen),
         "มาจากแดน": " · ".join(sorted({sim.world(c.world_id).name for c in chosen})),
         "ความมีชีวิตของต้นไม้": f"{sim.tree_vitality:.0f}/{capacity(sim):.0f}"}
    if fallen:
        d["ผู้ไม่ได้กลับออกมา"] = " · ".join(fallen)

    # 3) ผู้ชนะบางคนไม่กลับสำนักเดิม แต่ไปตั้งแดนเซียนสาขาของตัวเอง
    if winner.realm >= C.TREE_FOUND_REALM and rng.random() < C.TREE_FOUND_P:
        new_wid = _found_branch(sim, winner, rng)
        if new_wid is not None:
            d["ตั้งแดนใหม่"] = f"{winner.name}ตั้ง{sim.world(new_wid).name}ขึ้นเป็นสาขาของตนเอง"

    sim.emit(sim.world(winner.world_id), "แดนลับต้นกำเนิดเปิด", winner, None,
             ["สมบัติ", "ต่อสู้"], "ชิงสมบัติสำเร็จ",
             f"แดนลับต้นกำเนิดเปิดออก ดูด {len(chosen)} ผู้บำเพ็ญจากหลากแดนเข้าไปพร้อมกัน "
             f"{winner.name}เป็นผู้ได้ผลไม้ต้นกำเนิดไป", 0, d)


def _found_branch(sim, founder, rng):
    """ตั้งแดนเซียนสาขาใหม่จากผู้ที่รอดออกมาจากแดนลับ — เพิ่ม World จริงตอนซิมกำลังเดิน"""
    from .models import World
    if len(sim.worlds) >= C.TREE_BRANCH_CAP:
        return None
    line = rng.choice(sorted({s[1] for s in SK.SKILLS}))
    name = f"แดนเซียน{founder.name}"
    if any(w.name == name for w in sim.worlds):
        return None
    bw = World(wid=len(sim.worlds), name=name, tier=1, kind="mortal")
    bw.place_key = 1
    bw.up = sim.worlds[2].wid if len(sim.worlds) > 2 else None
    bw.skill_line = line
    bw.branch_origin = f"ก่อตั้งโดย{founder.name} ผู้รอดจากแดนลับต้นกำเนิด"
    bw.lateral.append(sim.worlds[1].wid)
    sim.worlds[1].lateral.append(bw.wid)
    sim.worlds.append(bw)
    sim.branch_wids.append(bw.wid)
    sim.tree_founded += 1
    for _ in range(C.BRANCH_CAST // 2):
        sim.spawn(bw, age_years=rng.randint(8, 45))
    return bw.wid


def _collapse(sim, elapsed: int) -> None:
    """ต้นไม้ตายแล้ว — สมดุลสองโลกพังลงเรื่อยๆ ไม่ต้องมีใครมาบุก"""
    yrs = elapsed / 365.0
    for w in sim.worlds:
        if w.wid in (0, 1):
            w.heaven = max(0.0, w.heaven - C.TREE_COLLAPSE_DRAIN * yrs)
            w.rift += C.TREE_COLLAPSE_RIFT * yrs
