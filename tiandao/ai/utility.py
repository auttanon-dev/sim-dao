# -*- coding: utf-8 -*-
"""Layer 1 — Utility AI (Dual Utility: Survival / Ambition) ตาม ROLE.md

คำนวณคะแนน "Need" หลายตัวจาก state จริงของตัวละคร (reuse field ใน models.Character ทั้งหมด — ไม่มี
field ใหม่บน Character เลย) แล้วเลือก Need คะแนนสูงสุดเป็น Current Goal ของเทิร์นนั้น

ผลลัพธ์ไม่ได้ "สั่ง" ให้ตัวละครทำอะไรตรงๆ — แค่ boost น้ำหนักที่ tiandao/intent.py:weigh() คำนวณไว้แล้ว
ให้เอียงไปทาง event kind ที่ตรงกับ Need ที่ชนะ (ต่อยอดของเดิม ไม่แทนที่ ตามกฎ Reuse-first ของ ROLE.md)

หมายเหตุ: เอนจินนี้ไม่มีสถิติ "Hunger"/"Qi" แยกเป็นของจริง (ไม่มีกลไกความหิว) จึงไม่ประดิษฐ์ field ใหม่ขึ้น
ลอยๆ เพื่อให้ตรงตาม ROLE.md เป๊ะ — Survival Utility ในนี้ใช้ HP + decay (ตัวแทนแรงกดดันอายุขัย/ความเสื่อม
ที่มีอยู่แล้วใน tiandao/rules.py) + Fear แทน Hunger/Qi ที่ไม่มีอยู่จริงในโมเดล
"""
from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable, Dict, List, Tuple

from . import config_ai as ACFG

if TYPE_CHECKING:
    from ..models import Character
    from ..sim import Sim


def _ratio(value: float, cap: float) -> float:
    return 0.0 if cap <= 0 else max(0.0, min(1.0, value / cap))


@dataclass(frozen=True)
class Need:
    name: str
    category: str            # "survival" หรือ "ambition"
    kinds: Tuple[str, ...]   # event kind ใน tiandao/events.py:EVENT_TABLE ที่ Need นี้ควร boost


def _need_escape(ch: "Character", sim: "Sim") -> float:
    hp_ratio = _ratio(getattr(ch, "hp", 100), getattr(ch, "max_hp", 100) or 100)
    return (1.0 - hp_ratio) * getattr(ch, "fear", 0.5)


def _need_meditate(ch: "Character", sim: "Sim") -> float:
    lifespan_ratio = _ratio(ch.age(sim.day), ch.lifespan())
    decay_pressure = min(1.0, ch.decay / 2.0)
    return lifespan_ratio * (1.0 - getattr(ch, "fear", 0.5) * 0.3) + decay_pressure * 0.5


def _need_breakthrough(ch: "Character", sim: "Sim") -> float:
    return 1.0 if ch.at_bottleneck() else 0.2


def _need_revenge(ch: "Character", sim: "Sim") -> float:
    if not ch.rivals:
        return 0.0
    heat = min(1.0, max(ch.rivals.values()) / 10.0)
    return heat * (1.3 if "พยาบาท" in ch.traits else 1.0)


def _need_wealth(ch: "Character", sim: "Sim") -> float:
    return getattr(ch, "greed", 0.5)


def _need_reputation(ch: "Character", sim: "Sim") -> float:
    merit_ratio = _ratio(getattr(ch, "merit", 0.0) + 50.0, 100.0)
    return merit_ratio * getattr(ch, "compassion", 0.5)


def _need_dao_pursuit(ch: "Character", sim: "Sim") -> float:
    return 1.0 - getattr(ch, "greed", 0.5) * 0.3   # แรงขับพื้นฐาน ลดลงถ้าโลภมาก (สนใจสมบัติมากกว่าวิถี)


# Need -> (category, kinds ที่ควร boost, ฟังก์ชันให้คะแนน 0..1)
_SCORERS: Dict[Need, Callable[["Character", "Sim"], float]] = {
    Need("Escape",       "survival", ("ซ่อนตัว",)):                   _need_escape,
    Need("Meditate",     "survival", ("บำเพ็ญ", "ขัดเกลาสายเลือด")):     _need_meditate,
    Need("Breakthrough", "ambition", ("ข้ามขั้น",)):                   _need_breakthrough,
    Need("Revenge",      "ambition", ("ล้างแค้น",)):                   _need_revenge,
    Need("Wealth",       "ambition", ("ค้าขาย", "ชิงสมบัติ")):          _need_wealth,
    Need("Reputation",   "ambition", ("ถ่ายทอดวิชา", "สะสมบุญบารมี")):   _need_reputation,
    Need("DaoPursuit",   "ambition", ("ฝึกวิชา", "ค้นแดนลับ")):         _need_dao_pursuit,
}
NEEDS: List[Need] = list(_SCORERS)


def compute_needs(ch: "Character", sim: "Sim") -> Dict[str, float]:
    return {need.name: max(0.0, min(1.0, fn(ch, sim))) for need, fn in _SCORERS.items()}


def top_goal(needs: Dict[str, float]) -> Tuple[str, float]:
    return max(needs.items(), key=lambda kv: kv[1])


def apply_utility(weights: Dict[str, float], needs: Dict[str, float]) -> Dict[str, float]:
    """boost weights ของ intent.weigh() ตามคะแนน Need — ไม่เคยลดน้ำหนักลง แค่เอียงให้สูงขึ้น
    เพื่อรักษาความสุ่มเดิมของเอนจินไว้ (ไม่บังคับ, แค่ชักจูง)"""
    if not weights or not needs:
        return weights
    by_name = {need.name: need for need in NEEDS}
    for need_name, score in needs.items():
        if score <= 0:
            continue
        boost = 1.0 + ACFG.UTILITY_GAIN * score
        for kind in by_name[need_name].kinds:
            if kind in weights:
                weights[kind] *= boost
    return weights
