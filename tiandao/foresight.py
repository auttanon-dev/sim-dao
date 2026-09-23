# -*- coding: utf-8 -*-
"""ระบบจำลองอนาคต — นิมิตที่ "จริง" เพราะโลกนี้คำนวณได้

ทำไมเอนจินนี้ทำได้แบบไม่ต้องโกง: โลกทั้งใบเดินด้วย RNG เมล็ดเดียวและคิว heapq เดียว
(ดู Sim.step) อนาคตจึงไม่ใช่เรื่องที่ต้องเดา — สำเนาโลกไว้แล้วเดินต่อไปข้างหน้า สิ่งที่เห็นคือ
สิ่งที่ **จะเกิดขึ้นจริงถ้าไม่มีใครทำอะไรต่างจากเดิม** วัดจริงบนโลกอายุ 26 ปี (ตัวละคร 3,600 คน):
สำเนา 27 MB · เดินอนาคต 90 วัน รวม 1.25 วินาที · และโลกจริงไม่ขยับแม้แต่ tick เดียว

สามข้อที่ต้องระวังและถูกจัดการไว้ในไฟล์นี้
  1. **สำเนาต้องไม่เรียกโมเดลภาษาและไม่เขียนสมุดชีวิต** — ชั้นจิตใจถูกถอดออกจากสำเนา และ
     สมาชิกของ event_bus ที่ผูกกับ MindManager ถูกตัดทิ้ง ไม่งั้นการมองอนาคตหนึ่งครั้งจะยิง
     คำขอไปที่ Ollama เป็นสิบครั้งและเขียนบันทึกปลอมลงไฟล์จริง
  2. **โลกจริงต้องไม่ขยับ** — ทุกอย่างเกิดบนสำเนา แล้วสำเนาถูกทิ้ง RNG ของโลกจริงไม่ถูกดึงเลย
     แม้แต่ครั้งเดียว (เทสต์ตรวจ rng.getstate() ก่อน/หลัง)
  3. **นิมิตต้องมีราคา** — ไม่งั้นตัวเอกไม่มีวันตายและเรื่องก็ไม่เหลืออะไรให้ลุ้น ราคาคือชะตา
     (fate) จิตมารที่หนักขึ้น และคูลดาวน์ ยิ่งมองไกลยิ่งพร่ามัว (เกิน CLEAR_DAYS เห็นแต่เค้าโครง)
"""
import pickle

from . import config as C
from . import events as E

HOSTILE = ("ล้างแค้น", "ลอบสังหาร", "ชิงสมบัติ", "ทรยศ", "ดักปล้น", "มารบุก", "ล่ามนุษย์มาร",
           "จับกุมอาชญากร", "สงครามสำนัก", "ประลอง")
WORLD_SHAKING = ("ยุคล่ม", "มารบุก", "โกลาหลบุก", "โกลาหลบุกโลกมนุษย์", "เกณฑ์ขึ้นฟ้า",
                 "เจ้าโกลาหลคืนกลับ", "มหาผนึกโกลาหลเสื่อม", "เปิดสวรรค์", "ปิดรอยแยกโกลาหล")

# สิ่งที่ "คุ้มค่าจะเป็นคำทำนาย" เวลาต้องถอยไปมองคนรอบตัว (ข้อ 6 ใน glimpse)
# วัดจริงจากนิมิตสองครั้งแรกที่ใช้จริงในโลกปีที่ 119 และ 124: ห้าบรรทัดที่ได้คือ
#   "คนแปลกหน้าจะฝึกวิชา — ฝึกพลาด" · "คนแปลกหน้าจะบำเพ็ญ" · "คนแปลกหน้าจะเดินทาง"
# ซึ่งเป็นคำทำนายที่ **ตัดสินใจอะไรไม่ได้เลย** จ่ายชะตาไปหนึ่งแต้มเพื่อรู้ว่าคนที่ไม่รู้จัก
# จะออกเดินทาง — ไม่คุ้ม และทำให้ระบบไม้ตายของตัวเอกกลายเป็นของประดับ
WORTH_SEEING = frozenset({
    "ล้างแค้น", "ลอบสังหาร", "ชิงสมบัติ", "ทรยศ", "หักหลัง", "ดักปล้น", "มารบุก",
    "ล่ามนุษย์มาร", "จับกุมอาชญากร", "สงครามสำนัก", "สงครามเบิกฟ้า", "ข้ามขั้น",
    "ข้ามฟ้า", "ปิดด่าน", "ตั้งสำนัก", "เกณฑ์ขึ้นฟ้า", "ค้นแดนลับ", "กำเนิดทายาท",
})
DULL_OUTCOMES = frozenset({"ผ่านไป", "ทั่วไป", "สะสมต่อ", "ไม่พบ", "ไม่มีของ",
                           "ไม่มีอะไรค้าง", "เดินไปตลาด", "ออกเดินทาง", "บำเพ็ญ",
                           "ค้าขาย", "เก็บได้", "ถ่ายทอด"})


def _fork(sim):
    """สำเนาโลกที่ "ตาบอดและใบ้" — เดินเองได้ แต่ไม่เรียกโมเดลและไม่เขียนอะไรลงดิสก์"""
    # ถอดชั้นจิตใจออกจากโลกจริง "ชั่วคราว" ก่อนสำเนา — สองเหตุผล: สำเนาจะได้เล็กและเร็วขึ้น
    # และของที่ผู้ใช้แนบไว้ที่ sim.mind (แบ็กเอนด์ คอนเนกชัน ฯลฯ) อาจ pickle ไม่ได้เลย
    mind = getattr(sim, "mind", None)
    bus = getattr(sim, "event_bus", None)
    subs = list(getattr(bus, "_subscribers", []) or [])
    if mind is not None:
        sim.mind = None
        if bus is not None:
            bus._subscribers = [h for h in subs if getattr(h, "__self__", None) is not mind]
    try:
        blob = pickle.dumps(sim, protocol=pickle.HIGHEST_PROTOCOL)
    finally:
        if mind is not None:
            sim.mind = mind
            if bus is not None:
                bus._subscribers = subs
    fork = pickle.loads(blob)
    fork.mind = None
    bus = getattr(fork, "event_bus", None)
    subs = getattr(bus, "_subscribers", None)
    if subs is not None:
        bus._subscribers = [h for h in subs
                            if type(getattr(h, "__self__", None)).__name__ != "MindManager"]
    return fork


def _ties_of(ch):
    out = [ch.cid]
    out += [ch.master_cid] if ch.master_cid >= 0 else []
    out += list(ch.disciples[:5]) + list(ch.children[:5]) + list(ch.parents[:2])
    out += [ch.spouse] if ch.spouse is not None else []
    out += [c for c, _v in sorted(ch.rivals.items(), key=lambda kv: -kv[1])[:5]]
    out += [c for c, _v in sorted(ch.bonds.items(), key=lambda kv: -kv[1])[:5]]
    return {c for c in out if isinstance(c, int) and c >= 0}


def glimpse(sim, ch, days=None):
    """มองอนาคต — คืน dict: lines (คำบรรยายนิมิต) · deaths (cid -> วันที่จะตาย) · horizon

    ไม่แตะโลกจริงเลย และไม่คิดราคาให้ (ผู้เรียกเป็นคนจ่าย ดู Sim.foresee)
    """
    days = int(days or C.FORESIGHT_HORIZON)
    cid = ch.cid
    ties = _ties_of(ch)
    n0 = len(sim.cast)
    alive0 = {i: sim.cast[i].alive for i in ties if i < n0}
    rank0 = {i: sim.cast[i].rank() for i in ties if i < n0}
    day0 = sim.day

    fork = _fork(sim)
    # ขอบฟ้าที่ยืดได้ — เดินต่อไปเรื่อยๆ จนกว่าจะเห็น "เรื่องของตัวเขาเอง" พอสมควร
    #
    # ทำไมต้องยืด: ขอบฟ้าคงที่หนึ่งปีถูกตั้งจากสมมติฐานว่าคนหนึ่งลงมือหลายครั้งต่อปี แต่วัดจริง
    # จากโลกปีที่ 118-129 — ผู้มีจิตใจ 9 คน ตัดสินใจรวม 103 ครั้งใน 11 ปี = **คนละราวปีละครั้ง**
    # ขอบฟ้าหนึ่งปีจึงสั้นกว่าจังหวะชีวิตของเจ้าของนิมิตเอง ผลคือทั้งสองครั้งที่ใช้จริง ไม่มี
    # บรรทัด "ข้าจะ..." สักบรรทัดเดียว เหลือแต่ของคนอื่นจากทางถอยข้อ 6
    # ยืดเฉพาะตอนที่ยังไม่เห็นอะไร จึงไม่แพงขึ้นในกรณีที่ปีนั้นมีเรื่องของเขาอยู่แล้ว
    target = fork.day + days
    hard = fork.day + max(days, int(getattr(C, "FORESIGHT_HORIZON_MAX", days)))
    want = int(getattr(C, "FORESIGHT_MIN_PERSONAL", 3))
    seen, personal = [], 0
    while fork.day < hard:
        if fork.day >= target and personal >= want:
            break
        ev = fork.step()
        if ev is None:
            break
        mine_ev = (ev.actor == cid or ev.target == cid)
        if mine_ev:
            personal += 1
        # เก็บกว้างกว่าที่ต้องใช้เล็กน้อย — คนที่กำลังปิดด่านหรือเดินทางไกลจะไม่มี "เรื่องของ
        # ตัวเอง" ในช่วงนั้นเลย นิมิตจึงต้องมีของรอบตัวเขาไว้ใช้แทน (ดูข้อ 6 ข้างล่าง)
        if (mine_ev or ev.kind in WORLD_SHAKING
                or ev.place == ch.place or "ความตาย" in (ev.tags or ())):
            if len(seen) < 400:
                seen.append(ev)
    days = fork.day - day0          # ขอบฟ้าที่เดินจริง (ใช้บอกผู้อ่านว่ามองไปไกลแค่ไหน)

    deaths, lines = {}, []

    def when(day):
        gap = day - day0
        if gap <= C.FORESIGHT_CLEAR_DAYS:
            return E.date_words(day)
        return f"อีกราว {max(1, gap // 30)} เดือนข้างหน้า (ภาพพร่ามัว)"

    # 1. ความตาย — ของตัวเองก่อน แล้วค่อยคนใกล้ตัว
    for i in sorted(ties):
        if i >= len(fork.cast) or i >= n0:
            continue
        f = fork.cast[i]
        if alive0.get(i) and not f.alive:
            deaths[i] = f.death_day
            who = "ตัวข้าเอง" if i == cid else f.name
            lines.append(f"{when(f.death_day)}: **{who}จะตาย** — {getattr(f, 'death_cause', '') or 'ไม่เห็นสาเหตุ'}")
    # 2. ใครจะลงมือกับข้า
    for ev in seen:
        if ev.target == cid and ev.kind in HOSTILE:
            a = sim.cast[ev.actor] if 0 <= ev.actor < n0 else None
            nm = a.name if a is not None else "ใครบางคน"
            lines.append(f"{when(ev.day)}: {nm}จะ{ev.kind}กับข้า — {ev.outcome}")
    # 3. สิ่งที่ตัวเองจะลงมือทำและผลของมัน — หัวใจของการใช้ระบบนี้จริงๆ ในแนวนิยาย:
    #    "ถ้าข้าทะลวงขั้นเดือนหน้า มันจะสำเร็จไหม" · "ถ้าข้าไปแดนลับนั้น ข้าจะได้อะไรกลับมา"
    mine = 0
    for ev in seen:
        if ev.actor == cid and ev.kind not in ("เหตุการณ์เมือง", "ได้ยินข่าวลือ") and mine < 4:
            tail = f" — {ev.outcome}"
            if ev.kind in ("ข้ามขั้น", "ปิดด่าน", "ข้ามฟ้า", "ค้นแดนลับ", "สงครามเบิกฟ้า"):
                tail += f": {ev.text[:70]}"
            lines.append(f"{when(ev.day)}: ข้าจะ{ev.kind}{tail}")
            mine += 1
    # 4. ศัตรูที่จะไต่แซง
    for i in sorted(ties):
        if i == cid or i >= len(fork.cast) or i >= n0:
            continue
        f = fork.cast[i]
        if f.alive and f.rank() > rank0.get(i, f.rank()):
            lines.append(f"ภายใน {days // 30} เดือนนี้: {f.name}จะไต่ถึง{f.realm_name()}")
    # 5. ฟ้าดินสะเทือน
    big = []
    for ev in seen:
        if ev.kind in WORLD_SHAKING and ev.world_id == ch.world_id:
            key = (ev.kind, ev.outcome)
            if key not in big:
                big.append(key)
                lines.append(f"{when(ev.day)}: {ev.kind} — {ev.outcome}")
    # 6. ถ้ายังไม่เห็นอะไรเลย — คนที่ปิดด่านหรือกำลังเดินทางไกลจะไม่มี "เรื่องของตัวเอง" ใน
    #    ช่วงนั้นจริงๆ (วัดแล้ว 2 ใน 3 คนได้ภาพว่างเปล่า) จึงถอยไปมองสิ่งที่จะเกิดรอบตัวเขาแทน:
    #    ใครจะตายในแดนนี้ และอะไรจะเกิดขึ้นที่เขายืนอยู่ — นิมิตที่ใช้ตัดสินใจอะไรได้อยู่ดี
    if len(lines) < 2:
        # เรียงตาม "ใกล้ตัวเขาแค่ไหน" ไม่ใช่ตามลำดับ cid (ซึ่งคือลำดับที่คนเกิดในโลก แปลว่า
        # ของเดิมหยิบคนที่แก่ที่สุดในโลกมาก่อนเสมอ = คนแปลกหน้าทั้งนั้น)
        #   0 = คนของเขา (ศิษย์ ลูก คู่ครอง ศัตรูคู่อาฆาต สหาย)  1 = คนที่ยืนอยู่ที่เดียวกัน
        #   2 = คนร่วมสำนัก   3 = คนอื่นในโลกเดียวกัน
        def _closeness(i):
            if i in ties:
                return 0
            other = sim.cast[i]
            if other.place == ch.place:
                return 1
            if other.org is not None and other.org == ch.org:
                return 2
            return 3

        near = 0
        cands = [i for i, f in enumerate(fork.cast[:n0])
                 if f.world_id == ch.world_id and sim.cast[i].alive and not f.alive]
        cands.sort(key=lambda i: (_closeness(i), fork.cast[i].death_day))
        for i in cands:
            if near >= 3:
                break
            f = fork.cast[i]
            how = "คนของข้า" if _closeness(i) == 0 else ("คนที่ยืนอยู่ตรงนี้กับข้า"
                                                        if _closeness(i) == 1 else "")
            tag = f" ({how})" if how else ""
            lines.append(f"{when(f.death_day)}: {f.name}จะตาย{tag} — "
                         f"{getattr(f, 'death_cause', '') or 'ไม่เห็นสาเหตุ'}")
            deaths[i] = f.death_day     # เก็บไว้ตรวจว่าเขาเปลี่ยนชะตานี้ได้ไหม (ดู Sim.check_fate)
            near += 1
        # เหตุการณ์รอบตัว — เอาเฉพาะที่ "คุ้มค่าจะเป็นคำทำนาย" การจ่ายชะตาหนึ่งแต้มเพื่อรู้ว่า
        # คนแปลกหน้าจะออกเดินทาง ทำให้ไม้ตายของตัวเอกกลายเป็นของประดับ (วัดจริงปีที่ 119/124)
        rest = [ev for ev in seen
                if ev.actor != cid and ev.kind in WORTH_SEEING
                and ev.outcome not in DULL_OUTCOMES]
        rest.sort(key=lambda ev: (_closeness(ev.actor) if 0 <= ev.actor < n0 else 3, ev.day))
        for ev in rest:
            if near >= 5:
                break
            a = sim.cast[ev.actor] if 0 <= ev.actor < n0 else None
            lines.append(f"{when(ev.day)}: {(a.name if a else 'ใครบางคน')}จะ{ev.kind}"
                         f" — {ev.outcome}")
            near += 1
    if not lines:
        lines.append(f"ภาพว่างเปล่า — {days // 30} เดือนข้างหน้าไม่มีอะไรที่ฟ้ายอมให้ข้าเห็น")
    return {"horizon": days, "day": day0, "lines": lines[:C.FORESIGHT_MAX_LINES],
            "deaths": deaths}
