# -*- coding: utf-8 -*-
"""ประตูมิติ — เครื่องทุ่นแรงการเดินทางที่ต้องสร้างเอง ไม่ใช่ของที่มีมาแต่แรก

ทำไมถึงต้องมี และทำไมต้องแพงขนาดนี้
---------------------------------------------------------------------------------------------
หลังจากแดนเซียนสาขาแยกแผนที่ออกจากกันจริง (ดู realm_map.py) การเดินทางจากสาขาหนึ่งไปอีกสาขาหนึ่ง
ใช้เวลาราว **569 วันสำหรับผู้บำเพ็ญขั้น 3** เพราะทางเข้าออกมีทางเดียวคือวนผ่านแดนเซียนกลาง นั่นคือ
โลกที่การเดินทางมีน้ำหนักจริง แต่ก็เป็นโลกที่แทบไม่มีใครไปไหนได้ ประตูมิติคือทางออกที่ **ต้องจ่าย**:

  - สร้างได้เฉพาะผู้ที่รู้วิชาสายมิติ (skills.py สาย "มิติ") — ไม่ใช่ใครก็สร้างได้
  - กินทรัพยากรของแดนมหาศาล แดนที่ทรัพยากรไม่พอสร้างไม่ได้ ต่อให้มีคนเก่งแค่ไหน
  - หลายคนช่วยกันสร้างได้ และยิ่งคนในทีมชำนาญมิติมากเท่าไหร่ ต้นทุนยิ่งถูกลง
  - **ยิ่งสร้าง ยิ่งชำนาญ** — ทุกคนในทีมได้ `dimension_rank` เพิ่ม ซึ่งทำให้ประตูบานถัดไปถูกลงอีก
    นี่คือวงจรที่ทำให้อารยธรรมที่ลงทุนกับมิติตั้งแต่แรก ทิ้งห่างแดนอื่นเรื่อยๆ ด้วยตัวมันเอง

ประตูที่สร้างเสร็จคือ **เส้นทางถาวรบนแผนที่จริง** (ต่อเข้า geo.EDGES) ไม่ใช่การวาร์ปแบบยกเว้นกฎ —
ระบบเดินทางเดิมทั้งหมดใช้เส้นนี้ได้ทันทีโดยไม่ต้องรู้ว่ามันคือประตูมิติ
"""
import collections

from . import config as C
from . import geo as GEO
from . import places as PL
from . import travel as TV
from .rules import SKILL_INDEX

DIMENSION_LINE = "มิติ"


def init(sim) -> None:
    if not hasattr(sim, "portals"):
        sim.portals = []          # [(place_a, place_b, day, ผู้สร้าง)]
        sim.portal_last_tick = 0


def mastery(ch) -> float:
    """ความชำนาญมิติ = วิชาสายมิติที่รู้ (ถ่วงตามเกรด) + ประสบการณ์จากการสร้างประตูมาแล้ว"""
    m = 0.0
    for n in ch.skills:
        sk = SKILL_INDEX.get(n)
        if sk and sk[1] == DIMENSION_LINE:
            m += 1.0 + sk[3]                      # เกรดสูงยิ่งช่วยได้มาก
    return m + getattr(ch, "dimension_rank", 0) * C.PORTAL_RANK_W


def _crew_of(sim, world):
    """ผู้ชำนาญมิติในแดนนั้น — นับทั้งแดน ไม่ใช่เฉพาะคนที่บังเอิญยืนอยู่ที่สำนักใหญ่พอดี

    เดิมบังคับให้ต้องอยู่ ณ จุดเดียวกันอยู่แล้ว ซึ่งวัดจริง 513 ปีแล้วพบว่าแทบไม่เคยเกิด: 60 แดนที่
    ยังไม่มีประตู มี **0 แดน** ที่ผู้ชำนาญสองคนอยู่ที่สำนักใหญ่พร้อมกัน การสร้างประตูจึงหยุดสนิท
    ตั้งแต่ปีที่ 127 การสร้างสิ่งใหญ่ระดับแดนควรเป็นการ "เรียกตัวมารวมกัน" ไม่ใช่ความบังเอิญของ
    ตำแหน่ง — ผู้ร่วมสร้างจึงถูกเรียกมายังสำนักใหญ่ตอนลงมือจริง
    """
    return sorted((c for c in sim.living_in(world.wid) if mastery(c) > 0 and not c.hidden),
                  key=lambda c: -mastery(c))


def _sect_place(world):
    """สำนักใหญ่ของแดน — จุดที่ประตูจะถูกตั้ง"""
    for i, p in enumerate(PL.PLACES):
        if p[1] == world.place_key and p[3] == "สำนัก":
            return i
    ps = PL.places_in(world.place_key)
    return ps[0] if ps else None


def cost_for(crew) -> float:
    """ทรัพยากรที่ต้องใช้ — ทีมที่ชำนาญกว่าจ่ายถูกกว่า แต่ไม่มีวันฟรี"""
    total = sum(mastery(c) for c in crew)
    return max(C.PORTAL_COST_MIN,
               C.PORTAL_COST_BASE / (1.0 + C.PORTAL_CREW_W * total))


def _link(sim, a: int, b: int, dist: float) -> None:
    """ต่อเส้นทางถาวรลงแผนที่จริง แล้วล้างแคชเส้นทางเพื่อให้ทุกคนใช้ได้ทันที"""
    GEO.EDGES.append((a, b, dist, "portal", True))
    TV._ADJ = None
    TV._ADJ_OPEN = None       # ต้องล้างทั้งสองชุด ไม่งั้นเส้นทางตอนผนึกใหญ่แตกจะไม่เห็นประตูใหม่


def tick(sim, rng) -> None:
    """งานประจำของการสร้างประตู — เรียกจาก sim.step() ทุกช่วง PORTAL_TICK_DAYS"""
    init(sim)
    if sim.day - sim.portal_last_tick < C.PORTAL_TICK_DAYS:
        return
    sim.portal_last_tick = sim.day

    hub = getattr(GEO, "BRANCH_HUB", 0)
    existing = {(a, b) for a, b, _d, _w in sim.portals}
    built_from = collections.Counter(a for a, _b, _d, _w in sim.portals)
    hub_linked = {a for a, b, _d, _w in sim.portals if b == hub}
    for w in sim.worlds:
        if not getattr(w, "skill_line", None):        # เฉพาะแดนสาขาที่อยู่ไกลออกไป
            continue
        spot = _sect_place(w)
        if spot is None or built_from[spot] >= C.PORTAL_MAX_PER_REALM:
            continue
        if rng.random() > C.PORTAL_TRY_P:
            continue
        crew = _crew_of(sim, w)[:C.PORTAL_CREW_MAX]
        if len(crew) < C.PORTAL_CREW_MIN:
            continue
        # บานแรกของแดนต่อเข้าชุมทางกลางเสมอ บานถัดไปเชื่อมตรงไปยังแดนอื่นที่มีประตูแล้ว —
        # นี่คือสิ่งที่ทำให้ "ยิ่งสร้างยิ่งชำนาญ" หมุนได้จริง เพราะทีมเดิมมีบานที่สองให้สร้าง
        if spot not in hub_linked:
            target = hub
        else:
            others = [x for x in sorted(hub_linked) if x != spot and (spot, x) not in existing]
            if not others:
                continue
            target = rng.choice(others)
        need = cost_for(crew)
        have = getattr(w, "resource", 0.0)
        if have < need:
            continue

        w.resource = have - need
        leader = max(crew, key=mastery)
        for c in crew:
            c.dimension_rank = getattr(c, "dimension_rank", 0) + 1
            c.insight += C.PORTAL_INSIGHT
        dist = C.PORTAL_DISTANCE
        old_dist = TV.shortest_path_distance(spot, target) or 0.0
        _link(sim, spot, target, dist)
        sim.portals.append((spot, target, sim.day, leader.cid))
        existing.add((spot, target))
        built_from[spot] += 1
        if target == hub:
            hub_linked.add(spot)
        for c in crew:
            c.place = spot                 # ถูกเรียกมารวมกันที่สำนักใหญ่เพื่อลงมือสร้าง
        sim.emit(w, "สร้างประตูมิติ", leader, None, ["สมบัติ"], "สร้างสำเร็จ",
                 f"{len(crew)} ผู้ชำนาญวิชามิติแห่ง{w.name} นำโดย{leader.name} "
                 f"ร่วมกันเปิดทวารมิติถาวรเชื่อม{PL.PLACES[spot][0]}เข้ากับ{PL.PLACES[target][0]}", 0,
                 {"ผู้ร่วมสร้าง": " · ".join(f"{c.name}(มิติขั้น {c.dimension_rank})" for c in crew),
                  "ทรัพยากรที่ใช้": f"{need:,.0f} จากคลังของแดน (เหลือ {w.resource:,.0f})",
                  "ระยะทางเดิม": f"{old_dist:,.0f} หน่วย",
                  "ระยะทางใหม่": f"{dist:,.0f} หน่วย"})


def regen(sim, elapsed_days: int) -> None:
    """ทรัพยากรของแต่ละแดนงอกกลับช้าๆ — แดนที่เพิ่งสร้างประตูจึงสร้างบานต่อไปทันทีไม่ได้"""
    yrs = elapsed_days / 365.0
    # เดิมงอกเฉพาะแดนสาขา ทำให้แดนหลัก (โลกมนุษย์ แดนเซียน สวรรค์นอกชั้นฟ้า แดนพี่น้อง) ไม่มี
    # คลังของตัวเองเลย — สร้างประตูมิติไม่ได้ และออกทุนผนึกเจ้าโกลาหลก็ไม่ได้ ทั้งที่เป็นแดน
    # ที่ควรจะรวยที่สุด ตอนนี้ทุกแดนมีคลังของตัวเอง จ่ายแล้วจน สะสมแล้วรวย เหมือนกันหมด
    for w in sim.worlds:
        # รายได้ของแดนมาจากคนที่ออกไปหาของจริงๆ บวกความบริสุทธิ์ของชั้นแดน ไม่ใช่ก้อนคงที่
        # เท่ากันทุกแดน — ถ้าเท่ากันหมด "แดนรวยออกทุนแล้วจนลง" ก็ไม่มีความหมายอะไรเลย
        rate = (C.REALM_RESOURCE_REGEN + C.REALM_RESOURCE_POP_W * max(0, w.n_alive))
        rate *= 1.0 + C.REALM_RESOURCE_TIER_W * w.tier
        have = getattr(w, "resource", C.REALM_RESOURCE_INIT)
        # Exact linear income/proportional upkeep solution: independent of how
        # the same elapsed time is divided into ticks.
        if C.REALM_RESOURCE_UPKEEP > 0:
            import math
            decay = math.exp(-C.REALM_RESOURCE_UPKEEP * yrs)
            amount = have * decay + rate / C.REALM_RESOURCE_UPKEEP * (1 - decay)
        else:
            amount = have + rate * yrs
        w.resource = max(0.0, min(C.REALM_RESOURCE_MAX, amount))
