# -*- coding: utf-8 -*-
"""Social / Relationship — ความสัมพันธ์หลายมิติต่อคนหนึ่งคน

มิติ (ทุกตัว 0..1 ยกเว้น debt ที่เป็น −1..1):
  trust · affection (มิตรภาพ/ความรัก) · hatred · fear · respect · debt (+ = เราเป็นหนี้เขา)
  · loyalty · faction (+1 ฝ่ายเดียวกัน, −1 ฝ่ายศัตรู, 0 ไม่เกี่ยว)

ใน Sim Dao ค่าพื้นฐานมาจาก field เดิม (bonds/rivals/debts/org/clan — ผ่าน simdao.py) แล้วบวก
"ส่วนต่างที่เรียนรู้" (feedback หลัง action) ซึ่งเก็บไว้ใน RelationshipBook นี้ ไม่เก็บซ้ำของเดิม
"""
from dataclasses import dataclass, field, fields
from typing import Dict

DIMS = ("trust", "affection", "hatred", "fear", "respect", "debt", "loyalty", "faction")


@dataclass
class Relation:
    trust: float = 0.5
    affection: float = 0.0
    hatred: float = 0.0
    fear: float = 0.0
    respect: float = 0.0
    debt: float = 0.0
    loyalty: float = 0.0
    faction: float = 0.0

    def clamp(self):
        for f in fields(self):
            lo = -1.0 if f.name in ("debt", "faction") else 0.0
            setattr(self, f.name, max(lo, min(1.0, getattr(self, f.name))))
        return self

    def plus(self, delta: "Relation"):
        out = Relation(**{d: getattr(self, d) + getattr(delta, d) for d in DIMS})
        # trust ของ delta เก็บเป็นส่วนต่างรอบ 0 ไม่ใช่รอบ 0.5
        return out.clamp()

    def to_dict(self):
        return {d: round(getattr(self, d), 3) for d in DIMS}


def neutral_delta():
    return Relation(trust=0.0)


@dataclass
class RelationshipBook:
    """ส่วนต่างที่ตัวละคร "เรียนรู้" ต่อแต่ละคน (feedback loop) — รวมกับ baseline ตอนใช้งาน"""
    deltas: Dict[object, Relation] = field(default_factory=dict)

    def get(self, other, baseline: Relation = None) -> Relation:
        base = baseline if baseline is not None else Relation()
        d = self.deltas.get(other)
        return base.plus(d) if d is not None else base

    def adjust(self, other, cfg, **dims):
        d = self.deltas.get(other)
        if d is None:
            d = neutral_delta()
            self.deltas[other] = d
        for k, v in dims.items():
            setattr(d, k, max(-1.0, min(1.0, getattr(d, k) + v)))
        cap = int(cfg.get("relationship.max_entries", 40))
        if len(self.deltas) > cap:
            weakest = sorted(self.deltas.items(),
                             key=lambda kv: sum(abs(getattr(kv[1], x)) for x in DIMS))
            for k, _ in weakest[: len(self.deltas) - cap]:
                self.deltas.pop(k, None)
        return d
