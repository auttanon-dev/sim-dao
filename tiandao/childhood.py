"""วัยเด็ก (อายุ 0–13) เป็นกิจวัตรรายปีที่ถูกขัดจังหวะได้ — แบบ §7.2

เด็กไม่เข้าเมนูของผู้ใหญ่เลย (Sim._step ส่งทุกคนที่อายุต่ำกว่า 14 มาที่ `turn` ที่เดียว) ในเทิร์นวันเกิด
เด็กเลือกกิจวัตรหนึ่งอย่างตามช่วงวัย แล้วทำไปจนวันเกิดถัดไปเป็น ActionProcess("upbringing") ผลคิดตามวันที่ทำจริง
(`accrue` ผ่าน Sim.accrue_process) ถูกขัดจังหวะเมื่อผู้ปกครองเปลี่ยน หิว หรือหมดสติ แล้วเลือกใหม่วันนั้น

ช่วงวัยและกิจวัตร:
- 0–2 ได้รับการเลี้ยงดู — ผูกพันกับผู้ดูแล ไม่มีตัวเลือก
- 3–13 เล่นกับเด็กที่อยู่ที่เดียวกัน (ผูกพันกันสองทาง) / เรียนรู้ที่บ้านกับผู้ดูแล / พัก
- 7–13 ช่วยงานบ้าน: แรงงาน CHILD_LABOUR_SHARE ของผู้ใหญ่ในการผลิตอาหารของที่ที่อยู่ (food.tick) ไม่มีค่าแรง
- 7–13 เรียนกับผู้ปกครอง: ผู้ปกครองที่อยู่ด้วยและมีวิชาเกรด 0 ที่สอนได้ — โอกาสได้วิชาตามกฎเดียวกับ "ถ่ายทอดวิชา"
  (rules.teach_chance) คิดตามส่วนของปีที่เรียนจริง ความเข้าใจเพิ่มไม่เกิน CHILD_INSIGHT_CAP ตลอดวัยเด็ก
- 7–13 ฝึกพื้นฐาน: ผู้ปกครองที่อยู่ด้วยเป็นผู้บำเพ็ญ (ขั้น 1 ขึ้นไป) หรืออยู่ในตระกูลหรือสำนัก — วันที่ฝึกจริงเป็นการฝึกต่อเนื่อง
  (BODY.log_training ภาระ CHILD_TRAIN_WORK × CHILD_TRAIN_SESSIONS_PER_WEEK / 7 ต่อวัน ร่างกายปรับตัวตามคำตอบปิดใน BODY.tick
  ครั้งถัดไป) การกลั่นกายตามวันที่ฝึกไม่เกิน CHILD_REFINE_CAP
  และนับวันตามสายของผู้ปกครอง (กาย จิต สมดุล) ไว้ใน childhood_gain["path:..."] สำหรับตอนเติบใหญ่
  ผู้ปกครองที่กำลังสอนหรือฝึกเด็กบำเพ็ญได้ GUARDIAN_TEACH_COST ของปกติ (Sim.begin_cultivation)

เติบใหญ่ (`come_of_age`, เทิร์นผู้ใหญ่เทิร์นแรกหลังอายุ 14 ครั้งเดียว): กิจวัตรที่ทำนานที่สุดให้ลักษณะติดตัวถาวร
(ROOT_TRAITS) ความเอนทางกายจากการนับวันตามสายตอนฝึก และเข้าสำนักของครูที่ยังมีชีวิตถ้าผูกพันถึง SECT_ENTRY_BOND

ขอความช่วยเหลือ: เทิร์นของเด็กที่หิวหรืออยู่ที่ที่ไม่มีข้าวใกล้ๆ ขอให้คนที่อยู่ใกล้ข้าวรับไปเลี้ยง (guardians.refoster)
ก่อนเลือกกิจวัตร — ไม่ต้องรอหิวจนระบบอาหารพาไป

การสุ่มใช้สตรีมที่ผูกกับ (seed, cid, วันเริ่ม) ไม่ดึงจาก rng หลักของโลก การเพิ่มระบบนี้จึงไม่เลื่อนลำดับสุ่มของโลก
"""
import random

from . import config as C
from . import guardians as GUARD
from . import body as BODY
from . import paths as PATHS
from . import rules as R

CARE, PLAY, HOME, REST = "ได้รับการเลี้ยงดู", "เล่นกับเพื่อน", "เรียนรู้ที่บ้าน", "พักผ่อน"
CHORES = "ช่วยงานบ้าน"
STUDY = "เรียนกับผู้ปกครอง"
TRAIN = "ฝึกพื้นฐาน"
MENTORED = (STUDY, TRAIN)
# กิจวัตรหลักตอนเติบใหญ่ -> ลักษณะติดตัว; เท่ากันใช้ลำดับนี้
ROUTINE_ORDER = (TRAIN, STUDY, CHORES, PLAY, HOME, CARE, REST)
ROOT_TRAITS = {CHORES: "ขยันงานไร่", STUDY: "ศิษย์ติดตาม", TRAIN: "ฝึกกายแต่เด็ก", PLAY: "เพื่อนมาก"}
PATH_LEAN = {"กายบำเพ็ญ": 1.0, "จิตบำเพ็ญ": 0.0}              # สายอื่น (สมดุล ยังไม่แน่ชัด) = 0.5
CHORE_AGE = 7
BAND_OUTCOME = ((2, "ได้รับการเลี้ยงดู"), (6, "เรียนรู้โลก"), (10, "ช่วยครอบครัว"), (13, "เตรียมเติบใหญ่"))
MAX_PLAYMATES = 3


def _rng(sim, child):
    return random.Random((getattr(sim, "seed", 0) << 32) ^ (child.cid << 20) ^ sim.day ^ 0xC41D)


def carer(sim, child):
    """ผู้ดูแลที่อยู่ด้วยจริง: ผู้ปกครอง ไม่มีก็พ่อแม่ที่ยังมีชีวิตและอยู่แดนเดียวกัน"""
    cast = sim.cast
    cids = ([child.guardian] if getattr(child, "guardian", -1) >= 0 else []) + list(child.parents or ())
    for cid in cids:
        if 0 <= cid < len(cast) and cast[cid].alive and cast[cid].world_id == child.world_id:
            return cast[cid]
    return None


def playmates(sim, child):
    day = sim.day
    return [c for c in sim.living_in(child.world_id)
            if c.cid != child.cid and c.place == child.place and 3 <= c.age(day) < 14]


def choose(sim, child, rng):
    """(กิจวัตร, คนที่ทำด้วย) — น้ำหนักตามสิ่งที่มีอยู่รอบตัวจริง ไม่มีเพื่อนก็เล่นไม่ได้ ไม่มีผู้ดูแลก็เรียนที่บ้านไม่ได้"""
    age = child.age(sim.day)
    home = carer(sim, child)
    if age <= 2:
        return CARE, [home.cid] if home is not None else []
    friends = playmates(sim, child)
    options = [(REST, 0.5, [])]
    if friends:
        pick = sorted(friends, key=lambda c: (-child.bonds.get(c.cid, 0), c.cid))[:MAX_PLAYMATES]
        options.append((PLAY, 2.0, [c.cid for c in pick]))
    if home is not None:
        options.append((HOME, 2.0 if home.place == child.place else 0.5, [home.cid]))
    if age >= CHORE_AGE:
        # ช่วยงานบ่อยขึ้นเมื่อผู้ดูแลเป็นคนผลิตอาหาร หรือข้าวแถวนี้เริ่มไม่พอ — ทำกับผู้ดูแลถ้าอยู่ที่เดียวกัน
        weight = 1.0
        if home is not None and home.produces_food():
            weight += 1.5
        if C.FOOD_ENABLED and not GUARD.food_near(sim, child.world_id, child.place):
            weight += 1.5
        together = [home.cid] if home is not None and home.place == child.place else []
        options.append((CHORES, weight, together))
        if home is not None and home.place == child.place and R.teachable(home, child, max_grade=0):
            options.append((STUDY, 2.0, [home.cid]))
        if home is not None and home.place == child.place and can_train(home):
            options.append((TRAIN, 1.5, [home.cid]))
    roll = rng.random() * sum(w for _, w, _ in options)
    for routine, w, with_ in options:
        roll -= w
        if roll < 0:
            return routine, with_
    return options[-1][0], options[-1][2]


def can_train(ch) -> bool:
    """ฝึกพื้นฐานให้เด็กได้: เป็นผู้บำเพ็ญ หรืออยู่ในตระกูลหรือสำนัก"""
    return ch.realm >= 1 or getattr(ch, "clan", -1) >= 0 or bool(getattr(ch, "sect_name", None))


def teaching(sim, ch) -> bool:
    """ผู้ใหญ่คนนี้กำลังสอนหรือฝึกเด็กในความดูแลอยู่ไหม (เด็กที่เรียนหรือฝึกกับเขาและกิจวัตรยังไม่จบ)"""
    for cid in getattr(ch, "wards", ()):
        p = sim.cast[cid].process if 0 <= cid < len(sim.cast) else None
        if (p is not None and p.kind == "upbringing" and p.payload.get("routine") in MENTORED
                and ch.cid in p.payload["with"] and p.end_day > sim.day):
            return True
    return False


def labour(ch, day) -> float:
    """ส่วนแรงงานผู้ใหญ่ที่เด็กคนนี้ให้การผลิตอาหารของที่ที่อยู่ตอนนี้ (0 = ไม่ได้ช่วยงาน)"""
    p = ch.process
    if p is None or p.kind != "upbringing" or p.payload.get("routine") != CHORES:
        return 0.0
    return C.CHILD_LABOUR_SHARE if CHORE_AGE <= ch.age(day) < 14 and p.end_day > day else 0.0


def ask_for_help(sim, child, world):
    """เด็กที่หิวหรืออยู่ไกลข้าวขอให้คนที่อยู่ใกล้ข้าวรับไปเลี้ยง ถ้าผู้ปกครองตอนนี้เลี้ยงไม่ไหว (ไม่มีข้าวใกล้ที่อยู่)
    ผู้ปกครองที่อยู่ใกล้ข้าวอยู่แล้วไม่ต้องย้าย รอบนาฬิกาโลกพาเด็กไปอยู่ด้วยเอง — คืน True ถ้าได้ผู้ดูแลใหม่"""
    if not (C.FOOD_ENABLED and C.GUARDIANS_ENABLED) or child.food is None:
        return False
    if child.hunger_days <= 0 and GUARD.food_near(sim, child.world_id, child.place):
        return False
    guardian = GUARD.guardian_of(sim, child)
    if guardian is not None and GUARD.food_near(sim, guardian.world_id, guardian.place):
        return False
    stats = sim.guardian_stats
    stats["asked_help"] = stats.get("asked_help", 0) + 1
    found = GUARD.refoster(sim, child, guardian)
    if found:
        stats["help_found"] = stats.get("help_found", 0) + 1
    elif _to_granary(sim, child):
        return False
    new = GUARD.guardian_of(sim, child)
    sim.emit(sim.world(child.world_id), "ขอความช่วยเหลือ", child, new if found else None, ["วัยเด็ก", "ครอบครัว"],
             "ได้ผู้ดูแลใหม่" if found else "ไม่มีใครรับ",
             f"{child.name}ขอความช่วยเหลือ" + (f" {new.name}รับไปเลี้ยงที่{sim.place_name(new)}" if found
                                                else " แต่ไม่มีใครที่อยู่ใกล้ข้าวรับได้"),
             0, {"หิวมาแล้ว": f"{child.hunger_days:.0f} วัน"})
    return found


def _to_granary(sim, child):
    """ไม่มีผู้ใหญ่ใกล้ข้าวรับได้ แต่แดนนี้ยังมีข้าว — เด็กไปพึ่งยุ้งฉางที่ใกล้ที่สุดที่มีข้าวพอ แล้วกินข้าวของหมู่บ้านที่นั่น
    (มื้อที่ไม่มีใครจ่าย คลังชุมชนของที่นั่นจ่ายให้ถ้ายังมีทอง — food._buy ขั้น A5 เดิมหมู่บ้านให้ฟรี)
    seed 12 ก่อนมีทางนี้: เด็กสองคนในแดนโกลาหลขอความช่วยเหลือแล้วไม่มีใครรับ อดตายทั้งที่แดนมีข้าว 16,697 สำรับ"""
    from . import food as FOOD                      # food นำเข้า childhood — นำเข้าตอนใช้เพื่อไม่ให้วน
    if child.place is None or child.place < 0:
        return False
    hub = FOOD._nearest_food(sim, child)
    if hub is None:
        return False
    old = sim.place_name(child)
    child.place, child.building = hub[0], -1
    stats = sim.guardian_stats
    stats["granary_ward"] = stats.get("granary_ward", 0) + 1
    sim.emit(sim.world(child.world_id), "พึ่งพิงยุ้งฉาง", child, None, ["วัยเด็ก", "ครอบครัว"], "ได้ที่พึ่ง",
             f"{child.name}ไม่มีผู้ใหญ่ใกล้ข้าวรับเลี้ยง จึงออกจาก{old}ไปพึ่งยุ้งฉางของ{sim.place_name(child)}",
             0, {"หิวมาแล้ว": f"{child.hunger_days:.0f} วัน"})
    return True


def start(sim, child, end_day, rng):
    routine, with_ = choose(sim, child, rng)
    payload = {"routine": routine, "with": with_, "guardian": getattr(child, "guardian", -1), "carry": {}}
    if routine == STUDY:
        payload["skill"] = R.teachable(sim.cast[with_[0]], child, max_grade=0)[0]
    if routine == TRAIN:
        payload["path"] = PATHS.path_of(sim.cast[with_[0]])
    return sim.start_process(child, "upbringing", end_day - sim.day, payload, C.CHILD_BOND_PER_YEAR)


def accrue(sim, child, p, days):
    """ผูกพันตามวันที่ทำจริง — สะสมเศษไว้ใน payload แล้วเพิ่มเป็นจำนวนเต็ม (bonds เป็นจำนวนเต็มทั้งเอนจิน)"""
    tally = child.upbringing_days
    routine = p.payload["routine"]
    tally[routine] = tally.get(routine, 0.0) + days
    if routine in MENTORED:
        key = f"mentor:{p.payload['with'][0]}"
        tally[key] = tally.get(key, 0.0) + days
    if p.payload["routine"] == REST:
        return
    if p.payload["routine"] == STUDY:
        _study(sim, child, p, days)
    if p.payload["routine"] == TRAIN:
        child.refine += _gain(child, "refine", days / 365.0 * C.CHILD_TRAIN_REFINE_PER_YEAR, C.CHILD_REFINE_CAP)
        BODY.log_training(child, days, C.CHILD_TRAIN_WORK * C.CHILD_TRAIN_SESSIONS_PER_WEEK / 7.0)
        key = "path:" + p.payload["path"]
        child.childhood_gain[key] = child.childhood_gain.get(key, 0.0) + days
    carry = p.payload["carry"]
    gain = days / 365.0 * p.yield_rate
    for cid in p.payload["with"]:
        other = sim.cast[cid]
        if not other.alive:
            continue
        total = carry.get(cid, 0.0) + gain
        whole = int(total)
        carry[cid] = total - whole
        if whole:
            child.bonds[cid] = child.bonds.get(cid, 0) + whole
            other.bonds[child.cid] = other.bonds.get(child.cid, 0) + whole


def _gain(child, key, amount, cap):
    """เพิ่มผลวัยเด็กไม่เกินเพดานตลอดชีวิต — คืนส่วนที่ได้จริง"""
    got = max(0.0, min(amount, cap - child.childhood_gain.get(key, 0.0)))
    child.childhood_gain[key] = child.childhood_gain.get(key, 0.0) + got
    return got


def _study(sim, child, p, days):
    """เรียนกับผู้ปกครอง: ความเข้าใจตามวันที่เรียน (มีเพดาน) และโอกาสได้วิชา = teach_chance × ส่วนของปีที่เรียนช่วงนี้
    สุ่มจากสตรีมของเด็ก (seed, cid, วัน) ไม่แตะ rng ของโลก ได้วิชาแล้วเรียนต่อได้แต่ไม่ได้วิชาเดิมซ้ำ"""
    child.insight += _gain(child, "insight", days / 365.0 * C.CHILD_STUDY_INSIGHT_PER_YEAR, C.CHILD_INSIGHT_CAP)
    name = p.payload.get("skill")
    teacher = sim.cast[p.payload["with"][0]]
    if not name or name in child.skills or not teacher.alive:
        return
    chance, _deep = R.teach_chance(teacher, child, name)
    if _rng(sim, child).random() < chance * min(1.0, days / 365.0):
        child.learn_skill(name)
        child.childhood_gain["skills"] = child.childhood_gain.get("skills", 0.0) + 1
        sim.emit(sim.world(child.world_id), "เรียนวิชา", child, teacher, ["วัยเด็ก", "วิชา"], "ได้วิชา",
                 f"{child.name}เรียน{name}จาก{teacher.name}จนทำได้", 0, {"วิชา": name, "โอกาส": f"{chance:.0%}"})


def broken(sim, child, p):
    """เหตุที่กิจวัตรนี้ไปต่อไม่ได้ (None = ไปต่อได้) — ตรวจทุกรอบนาฬิกาโลก"""
    if getattr(child, "guardian", -1) != p.payload.get("guardian", -1):
        return "ผู้ปกครองเปลี่ยน"
    if p.payload["routine"] in (CARE, HOME) + MENTORED and any(not sim.cast[c].alive for c in p.payload["with"]):
        return "ผู้ดูแลจากไป"
    return None


def _bully(sim, child, with_, world):
    """เด็กโดนแกล้งในปีที่ได้กิจวัตรเล่น (ผู้ใช้อนุมัติ 2026-10-05) — ไม่สุ่ม ตัดสินจากสภาวะ
    ผู้แกล้ง: เพื่อนเล่นที่โตกว่า ≥ BULLY_AGE_GAP ปี ที่ ambition − compassion สูงสุด (≥ BULLY_MIN)
    ผู้โดน: เด็กคนนี้ ถ้าขลาดที่สุดในกลุ่ม หรือผู้ปกครองไม่ได้อยู่ที่เดียวกัน
    ผล: แค้นผู้แกล้ง · กลัว/ชิงชัง (EM.react) · โดนรวม BULLY_TRAIT_YEARS ปี → รากนิสัย "ระวังคน" · ผู้แกล้งเสียความสนิทกับกลุ่ม
    บันทึกเฉพาะครั้งแรกของคู่นั้น และตอนติดรากนิสัย"""
    from . import emotions as EM
    age = child.age(sim.day)
    group = [sim.cast[c] for c in with_ if 0 <= c < len(sim.cast) and sim.cast[c].alive]
    if not group:
        return
    home = carer(sim, child)
    alone = home is None or home.place != child.place
    timid = child.fear >= max(c.fear for c in group)
    if not (alone or timid):
        return
    older = [c for c in group if c.age(sim.day) - age >= C.BULLY_AGE_GAP
             and c.ambition - c.compassion >= C.BULLY_MIN]
    if not older:
        return
    bully = max(older, key=lambda c: (c.ambition - c.compassion, -c.cid))
    log = child.__dict__.setdefault("bullied_by", {})
    first = bully.cid not in log
    log[bully.cid] = log.get(bully.cid, 0) + 1
    child.rivals[bully.cid] = child.rivals.get(bully.cid, 0) + 1
    EM.react(child, "โดนแกล้ง", "โดนแกล้ง", day=sim.day)
    for c in group:
        if c.cid != bully.cid:
            c.bonds[bully.cid] = c.bonds.get(bully.cid, 0) - 1
            bully.bonds[c.cid] = bully.bonds.get(c.cid, 0) - 1
    if first:
        sim.emit(world, "แกล้ง", bully, child, ["วัยเด็ก"], "แกล้งเพื่อน",
                 f"{bully.name}วัย {bully.age(sim.day)} ปี แกล้ง{child.name}วัย {age} ปี"
                 + (" ที่ไม่มีผู้ใหญ่อยู่ใกล้" if alone else ""), 0, {"ผู้ปกครองอยู่ใกล้": not alone})
    if sum(log.values()) >= C.BULLY_TRAIT_YEARS and "ระวังคน" not in child.traits:
        child.traits.append("ระวังคน")
        sim.emit(world, "เติบโต", child, bully, ["วัยเด็ก"], "ติดนิสัยระวังคน",
                 f"{child.name}ถูกแกล้งมา {sum(log.values())} ปี จนกลายเป็นเด็กที่ระวังคน", 0,
                 {"รากนิสัย": "ระวังคน", "ผู้แกล้ง": bully.name})


def _cheat(sim, child, world):
    """เด็กยากจนโกงเงินทอนพ่อค้าที่ตลาด ในปีที่ช่วยงาน (ผู้ใช้อนุมัติ 2026-10-05) — ไม่สุ่ม ทองย้ายผ่าน WAGES.move_gold เท่านั้น
    ผู้กระทำ: อายุ CHILD_CHEAT_AGE ความโลภ ≥ CHILD_CHEAT_GREED เงินตัวเอง+ครัวเรือนไม่พอค่าข้าว FOOD_SECLUDE_KEEP_DAYS วัน
    ถูกจับ (ไม่สุ่ม): พ่อค้าขั้นสูงกว่า หรือเคยโกงพ่อค้าคนนี้แล้ว → คืนทองทั้งหมด + Sim.wrong_done("โกง") (หนี้กรรม ความแค้นของครัวเรือน)
    ถูกจับครบ CHILD_CHEAT_BAN_AFTER ครั้ง → ตลาดลงโทษ (ห้ามเข้าแผงจนเติบใหญ่ — เด็กเข้าคุกในระบบนี้ไม่ได้ เพราะเทิร์นเด็กล้างสถานะซ่อน)
    สำเร็จครบ CHILD_CHEAT_TRAIT_AFTER ปี → รากนิสัย "หัวหมอ" ความโลภเพิ่ม"""
    from . import places as PL
    from . import wages as WAGES
    from . import food as F
    from . import household as HH
    lo, hi = C.CHILD_CHEAT_AGE
    age = child.age(sim.day)
    if not (C.WAGES_ENABLED and lo <= age <= hi and child.greed >= C.CHILD_CHEAT_GREED):
        return
    if getattr(child, "cheat_banned", False) or not (0 <= child.place < len(PL.PLACES)):
        return
    if PL.PLACES[child.place][3] not in C.AUCTION_PLACES:
        return
    tier = WAGES.tier_of(sim, child)
    home = HH.of(sim, child)
    have = WAGES.gold(sim, child) + (home.purse.get(tier, 0.0) if home is not None else 0.0)
    need = C.FOOD_SECLUDE_KEEP_DAYS * F.ration(child, sim.day) * F.price_at(sim, F._spot(child))
    if have >= need:
        return
    shops = [c for c in sim.living_in(child.world_id) if c.place == child.place and c.cid != child.cid
             and c.age(sim.day) >= 16 and getattr(c, "profession", "") in C.AUCTION_HOSTS
             and WAGES.tier_of(sim, c) == tier and WAGES.gold(sim, c) > 0]
    if not shops:
        return
    marks = child.__dict__.setdefault("cheated", {})
    # เลือกพ่อค้าที่ยังไม่เคยโกงก่อน (คนเดิมจำหน้าได้) แล้วจึงรวยที่สุด — ถ้าเลือกแต่คนรวยที่สุด ปีที่สองก็โกงคนเดิมแล้วถูกจับเสมอ
    mark = max(shops, key=lambda c: (c.cid not in marks, WAGES.gold(sim, c), -c.cid))
    amount = min(WAGES.gold(sim, mark) * C.CHILD_CHEAT_SHARE, need - have)
    if amount <= 0:
        return
    caught = mark.realm > child.realm or mark.cid in marks
    WAGES.move_gold(sim, mark, -amount)
    WAGES.move_gold(sim, child, amount)
    marks[mark.cid] = marks.get(mark.cid, 0) + 1
    if caught:
        WAGES.move_gold(sim, child, -amount)          # คืนทองครบ
        WAGES.move_gold(sim, mark, amount)
        sim.wrong_done(child, mark, "โกง", amount)
        child.cheat_caught = getattr(child, "cheat_caught", 0) + 1
        banned = child.cheat_caught >= C.CHILD_CHEAT_BAN_AFTER
        if banned:
            child.cheat_banned = True
        sim.emit(world, "ถูกจับได้ว่าโกง", child, mark, ["วัยเด็ก", "ทรัพย์"], "ถูกตลาดลงโทษ" if banned else "คืนเงิน",
                 f"{mark.name}จับได้ว่า{child.name}วัย {age} ปี โกงเงินทอน {amount:.2f} เหรียญ — {child.name}ต้องคืนทั้งหมด"
                 + (" และถูกห้ามเข้าแผงในตลาดอีก" if banned else ""), 0,
                 {"เงินที่คืน": round(amount, 4), "ถูกจับครั้งที่": child.cheat_caught})
        return
    child.cheat_ok = getattr(child, "cheat_ok", 0) + 1
    if child.cheat_ok == 1:
        sim.emit(world, "โกงเงินทอน", child, mark, ["วัยเด็ก", "ทรัพย์"], "โกงสำเร็จ",
                 f"{child.name}วัย {age} ปี ที่บ้านไม่มีเงินค่าข้าว แอบโกงเงินทอนของ{mark.name}ไป {amount:.2f} เหรียญ", 0,
                 {"เงินที่ได้": round(amount, 4)})
    if child.cheat_ok >= C.CHILD_CHEAT_TRAIT_AFTER and "หัวหมอ" not in child.traits:
        child.traits.append("หัวหมอ")
        child.greed = min(1.0, child.greed + C.CHILD_CHEAT_GREED_UP)
        sim.emit(world, "เติบโต", child, None, ["วัยเด็ก"], "ติดนิสัยหัวหมอ",
                 f"{child.name}โกงเงินทอนสำเร็จมา {child.cheat_ok} ปี จนติดนิสัยหัวหมอ", 0, {"รากนิสัย": "หัวหมอ"})


def turn(sim, child, world, elapsed, rng):
    """เทิร์นของเด็ก: เลือกกิจวัตรถึงวันเกิดถัดไป บันทึกหนึ่งเรื่องต่อปีของอายุ แล้วนัดเทิร์นถัดไปใกล้วันเกิด"""
    age = max(0, child.age(sim.day))
    next_birthday = child.born_day + (age + 1) * 365
    ask_for_help(sim, child, world)
    p = start(sim, child, next_birthday, _rng(sim, child))
    routine, with_ = p.payload["routine"], p.payload["with"]
    if routine == PLAY:
        _bully(sim, child, with_, world)
    elif routine == CHORES:
        _cheat(sim, child, world)
    names = "และ".join(sim.cast[c].name for c in with_[:2])
    outcome = next(o for top, o in BAND_OUTCOME if age <= top)
    if routine == CARE:
        text = f"{child.name}เติบโตในอ้อมอกของ{names}" if names else f"{child.name}วัย {age} ปี เติบโตโดยไม่มีผู้ดูแลอยู่ใกล้"
    elif routine == PLAY:
        text = f"{child.name}วัย {age} ปี เล่นซนกับ{names}จนสนิทกัน"
    elif routine == HOME:
        text = f"{child.name}วัย {age} ปี เรียนรู้ผู้คนและวิถีชีวิตจาก{names}"
    elif routine == TRAIN:
        text = f"{child.name}วัย {age} ปี ฝึกพื้นฐานกับ{names} ({p.payload['path']})"
    elif routine == STUDY:
        text = f"{child.name}วัย {age} ปี เรียน{p.payload['skill']}กับ{names}"
    elif routine == CHORES:
        text = (f"{child.name}วัย {age} ปี ช่วย{names}ทำงานหาอาหาร" if names
                else f"{child.name}วัย {age} ปี ช่วยงานเก็บหาอาหารที่{sim.place_name(child)}")
    else:
        text = f"{child.name}วัย {age} ปี ใช้เวลาเงียบๆ เติบโตตามวัย"
    if carer(sim, child) is None and age > 2:
        outcome = "เติบโตโดยไร้ผู้ปกครอง"
    history = getattr(child, "childhood", None)
    if not isinstance(history, list):
        history = child.childhood = []
    # บันทึกเป็นเหตุการณ์เฉพาะครั้งแรกที่เด็กทำกิจวัตรนั้น (หรือครั้งแรกที่ต้องโตโดยไร้ผู้ปกครอง) — การคำนวณทั้งหมด (กิจวัตร
    # บุคลิกภาพ ROOT_TRAITS การฝึก การได้วิชา แรงงาน) อยู่ใน start/accrue ไม่ขึ้นกับว่าบันทึกหรือไม่ · เดิมบันทึกทุกปีของทุกเด็ก:
    # seed 42 ใน 100 ปี "เติบโต" 44,578 เหตุการณ์ = 18.6% ของประวัติ ("วัย 6 ปี เล่นซน" ซ้ำทุกปี) บังเรื่องของผู้ใหญ่
    seen = {(h.get("routine"), h.get("outcome") == "เติบโตโดยไร้ผู้ปกครอง") for h in history if isinstance(h, dict)}
    event = None
    if (routine, outcome == "เติบโตโดยไร้ผู้ปกครอง") not in seen:
        event = sim.emit(world, "เติบโต", child, None, ["วัยเด็ก"], outcome, text, elapsed,
                         {"อายุ": f"{age} ปี", "กิจวัตร": routine})
    if not any(h.get("age") == age for h in history if isinstance(h, dict)):
        history.append({"day": sim.day, "age": age, "text": text, "place": child.place,
                        "outcome": outcome, "routine": routine,
                        # ปีที่ไม่บันทึกเหตุการณ์ใช้ตำแหน่งประวัติ ณ ตอนนั้น (sim.seq) — สมุดชีวิตของชั้นจิตใจเรียงตาม seq และต้องเป็นตัวเลข
                        # (mind/manager._backfill_childhood: int(seq) — None ทำให้ test_minds พัง)
                        "seq": event.seq if event else sim.seq})
        del history[:-14]
    # กลับมาอีกครั้งใกล้วันเกิดถัดไป (ตัวคลาดเคลื่อนจาก rng ของโลกเหมือนเดิม) — ถูกขัดจังหวะก็ได้เทิร์นเร็วกว่านี้
    sim.schedule(child, max(30, next_birthday - sim.day + rng.randint(0, 30)))
    # ไม่ได้บันทึกปีนี้ — คืนเหตุการณ์ล่าสุดของโลก (แบบเดียวกับ Sim._step ตอนผู้ลงมือตาย) เพราะ step() คืน None = โลกหยุดเดิน
    return event if event is not None else (sim.log[-1] if sim.log else None)


def main_routine(ch):
    """กิจวัตรที่ทำนานที่สุดในวัยเด็ก — เด็กจากเซฟก่อนรุ่น 16 ไม่มีการนับวัน ใช้ประวัติรายปีใน `childhood` แทน"""
    tally = {r: d for r, d in ch.upbringing_days.items() if r in ROUTINE_ORDER}
    if not tally:
        for h in ch.childhood:
            if isinstance(h, dict) and h.get("routine") in ROUTINE_ORDER:
                tally[h["routine"]] = tally.get(h["routine"], 0.0) + 365.0
    if not tally:
        return None
    return max(ROUTINE_ORDER, key=lambda r: (tally.get(r, 0.0), -ROUTINE_ORDER.index(r)))


def _personal_lean(ch):
    """ความเอนทางกายจากวันที่ฝึกตามสายของครู (กาย 1 จิต 0 อื่นๆ 0.5) — None ถ้าไม่เคยฝึกพื้นฐาน"""
    days = {k[5:]: v for k, v in ch.childhood_gain.items() if k.startswith("path:") and v > 0}
    total = sum(days.values())
    if total <= 0:
        return None
    return sum(PATH_LEAN.get(path, 0.5) * d for path, d in days.items()) / total


def _mentor(sim, ch):
    """ครูที่เรียนหรือฝึกด้วยนานที่สุด (None ถ้าไม่เคย)"""
    mentors = {int(k[7:]): v for k, v in ch.upbringing_days.items() if k.startswith("mentor:")}
    if not mentors:
        return None
    cid = max(mentors, key=lambda c: (mentors[c], -c))
    return sim.cast[cid] if 0 <= cid < len(sim.cast) else None


def come_of_age(sim, ch, world):
    """เติบใหญ่ครั้งเดียวตอนเทิร์นผู้ใหญ่เทิร์นแรก: ลักษณะติดตัวจากกิจวัตรหลัก ความเอนทางกาย และเข้าสำนักของครู
    ไม่ใช้การสุ่ม — ผลเป็นของสิ่งที่เด็กทำมาจริงเท่านั้น"""
    ch.came_of_age = True
    d = {}
    routine = main_routine(ch)
    trait = ROOT_TRAITS.get(routine)
    if routine:
        d["กิจวัตรหลัก"] = routine
    if trait and trait not in ch.traits:
        ch.traits.append(trait)
        d["ลักษณะติดตัว"] = trait
    lean = _personal_lean(ch)
    if lean is not None:
        ch.body_bias = lean
        d["ความเอนทางกาย"] = f"{lean:.2f}"
    mentor = _mentor(sim, ch)
    if (mentor is not None and mentor.alive and getattr(mentor, "sect_name", None)
            and not getattr(ch, "sect_name", None) and ch.bonds.get(mentor.cid, 0) >= C.SECT_ENTRY_BOND):
        ch.sect_name, ch.sect_role = mentor.sect_name, "ศิษย์ในสำนัก"
        d["เข้าสำนัก"] = f"{mentor.sect_name} (ครู {mentor.name})"
        sim.emit(world, "เข้าสำนัก", ch, mentor, ["สำนัก", "วัยเด็ก"], "ศิษย์ในสำนัก",
                 f"{ch.name}เติบใหญ่แล้วเข้า{mentor.sect_name}ตามครู{mentor.name}", 0, {"สำนัก": mentor.sect_name})
    gain = ch.childhood_gain
    if gain.get("skills"):
        d["วิชาที่ได้ตอนเด็ก"] = f"{gain['skills']:.0f}"
    if gain.get("insight") or gain.get("refine"):
        d["ผลจากวัยเด็ก"] = f"ความเข้าใจ +{gain.get('insight', 0.0):.1f} · กาย +{gain.get('refine', 0.0):.2f}"
    close = sorted(((v, c) for c, v in ch.bonds.items() if 0 <= c < len(sim.cast) and sim.cast[c].alive),
                   reverse=True)[:3]
    if close:
        d["คนใกล้ชิด"] = "、".join(sim.cast[c].name for _, c in close)
    text = f"{ch.name}อายุ 14 เติบใหญ่" + (f" ผ่านวัยเด็กด้วยการ{routine}" if routine else "") + (
        f" ติดตัวมาเป็นคน{trait}" if trait else "")
    event = sim.emit(world, "เติบใหญ่", ch, None, ["วัยเด็ก"], "เติบใหญ่", text, 0, d)
    history = ch.childhood if isinstance(ch.childhood, list) else []
    history.append({"day": sim.day, "age": 14, "text": text, "place": ch.place, "outcome": "เติบใหญ่",
                    "routine": routine, "seq": event.seq})
    del history[:-15]
    ch.childhood = history
    return event
