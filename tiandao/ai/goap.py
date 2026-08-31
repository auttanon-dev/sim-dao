# -*- coding: utf-8 -*-
"""Layer 2 — Hierarchical GOAP (Phase 3), ต่อยอด Layer 1 Utility (tiandao/ai/utility.py)

ROLE.md ให้ตัวอย่างไว้ชัดเจนหนึ่งอัน: Goal "Breakthrough" แตกเป็น "Find Pill" ที่มี 4 วิธี
(Buy/Rob/Craft/Trade) — เอนจินนี้มีกลไก "ยาวิเศษ" (Item.kind == "ยาวิเศษ") ที่เพิ่มโอกาสข้ามขั้นอยู่
แล้วจริงๆ (ดู tiandao/rules.py:attempt_break, tiandao/sim.py บล็อก "ข้ามขั้น") — Find Pill ในที่นี้คือ
"หาไอเทมนั้นติดตัวก่อนจะลองข้ามขั้น" พอดีเป๊ะ ไม่ต้องประดิษฐ์กลไกใหม่

Phase 3 นี้ decompose เฉพาะ Breakthrough เท่านั้น (ตัวอย่างเดียวที่ ROLE.md ระบุรายละเอียดพอจะ map เข้า
event kind ที่มีอยู่จริงได้) — Need อื่นยังใช้การ boost แบบเรียบของ Phase 2 ต่อไป ขยายแพทเทิร์นเดียวกัน
นี้ไปยัง Goal อื่นทีหลังได้ถ้าต้องการ ไม่ใช่ตอนนี้ (เลี่ยงการสร้าง tree ที่ยังไม่มีตัวอย่างรองรับ)

Replan: ไม่มี state "แผนค้าง" แยกต่างหาก — precondition ของแต่ละ method คำนวณจาก state จริงของ
ตัวละครใหม่ทุกเทิร์นที่ถูกเรียก เพราะ "ยาวิเศษ" ถูกใช้ (a.items.remove(...)) ก่อน roll เสมอไม่ว่าจะ
สำเร็จหรือล้มเหลว เทิร์นถัดไปจึงไม่มียาอีกแล้วโดยอัตโนมัติ ทำให้ planner เลือก method ใหม่เองโดยไม่ต้อง
มีกลไก cache-then-invalidate ซ้อนขึ้นมา — Replan จึงเป็นผลพลอยได้ของการคำนวณสดทุกครั้ง
"""
from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable, Dict, List, Optional

from . import config_ai as ACFG

if TYPE_CHECKING:
    from ..models import Character
    from ..sim import Sim


def _has_pill(ch: "Character", sim: "Sim") -> bool:
    return any(sim.items[iid].kind == "ยาวิเศษ" for iid in ch.items if iid in sim.items)


def _at_furnace(ch: "Character", sim: "Sim") -> bool:
    pv = sim.place_of(ch)
    return bool(pv and pv[5] >= 0)


def _at_market(ch: "Character", sim: "Sim") -> bool:
    pv = sim.place_of(ch)
    return bool(pv and pv[3] in ("ตลาด", "เมือง"))


def _has_money(ch: "Character", sim: "Sim") -> bool:
    return sum(ch.money.values()) >= ACFG.PILL_BUY_MIN_MONEY


def _can_rob(ch: "Character", sim: "Sim") -> bool:
    return getattr(ch, "greed", 0.5) >= 0.6 or "โลภมาก" in ch.traits


@dataclass(frozen=True)
class Method:
    name: str
    kind: str    # event kind ใน tiandao/events.py:EVENT_TABLE ที่ method นี้ตรงกับ
    precondition: Callable[["Character", "Sim"], bool]


# ลำดับที่ planner ลองก่อน-หลัง: Craft ควบคุมได้เองมากสุด -> Buy -> Trade -> Rob เป็นทางเลือกสุดท้าย
FIND_PILL_METHODS: List[Method] = [
    Method("Craft", "หลอมยา",    lambda ch, sim: _at_furnace(ch, sim) and getattr(ch, "alchemy", 0.0) > 0),
    Method("Buy",   "ค้าขาย",    lambda ch, sim: _at_market(ch, sim) and _has_money(ch, sim)),
    Method("Trade", "เปิดประมูล", lambda ch, sim: _at_market(ch, sim) and _has_money(ch, sim)),
    Method("Rob",   "ชิงสมบัติ",  _can_rob),
]


def plan_breakthrough(ch: "Character", sim: "Sim", weights: Dict[str, float]) -> Optional[str]:
    """แตก Goal "Breakthrough" เป็นแผนย่อย "Find Pill" (Buy/Rob/Craft/Trade)

    คืนชื่อ method ที่เลือก ("Craft"/"Buy"/"Trade"/"Rob"/"Travel") หรือ None ถ้ามียาติดตัวพร้อมข้าม
    ขั้นได้เลย — ใช้ debug/บันทึกใน CharacterBrain.goap_method เท่านั้น ตัวที่มีผลจริงคือ weights ที่
    ถูกแก้ไข in-place"""
    if _has_pill(ch, sim):
        if "ข้ามขั้น" in weights:
            weights["ข้ามขั้น"] *= ACFG.GOAP_READY_BOOST
        return None

    for method in FIND_PILL_METHODS:
        if method.precondition(ch, sim) and method.kind in weights:
            weights[method.kind] *= ACFG.GOAP_SUBGOAL_BOOST
            return method.name

    # ไม่มี method ไหนเข้าเงื่อนไขเลย (ไม่มีเตา ไม่มีเงิน ไม่ได้อยู่ตลาด ไม่ได้โลภ) — ต้องเดินทางไปหา
    # โอกาสก่อน (reuse "เดินทาง" ที่มีอยู่แล้วในตาราง ไม่สร้าง kind ใหม่)
    if "เดินทาง" in weights:
        weights["เดินทาง"] *= ACFG.GOAP_SUBGOAL_BOOST
    return "Travel"
