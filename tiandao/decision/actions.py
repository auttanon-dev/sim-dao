# -*- coding: utf-8 -*-
"""Action Model — ทุก action อธิบาย metadata ของตัวเองได้ (ไม่มี decision logic อยู่ใน action)

ตัวอย่าง (YAML):

    attack_enemy:
      target: enemy
      requirements: [enemy_visible, can_attack]
      effects: [enemy_hp_down, stamina_down]
      rewards: {survival: 0.3, loot: 0.4, reputation: 0.3}
      costs: {stamina: 20, time: 5, resources: 0}
      risk: {injury: 0.4, death: 0.08, combat: true}
      relevant_goals: [survive, protect_friend, revenge, gain_loot]
      personality: {bravery: 0.8, aggression: 0.5, caution: -0.6}
      social: harm
      memory_tags: ["action:{id}", "foe:{target_kind}", "entity:{target}"]
      environment: {night: -0.2}
      goap: {pre: {enemy_near: true}, eff: {enemy_defeated: true}, cost: 2}

การประเมินทั้งหมดอยู่ที่ scoring.py (ระบบกลาง) — ActionSpec เป็นแค่ข้อมูล
"""
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

TARGET_TYPES = ("none", "enemy", "ally", "ally_in_danger", "threat_to_ally", "beast", "any", "loot")


@dataclass
class ActionSpec:
    id: str
    label: str = ""
    target: str = "none"
    target_select: str = "engine"          # engine = Decision Engine เลือกเป้า · external = ให้โลกเลือก
    requirements: List[str] = field(default_factory=list)
    effects: List[str] = field(default_factory=list)
    rewards: Dict[str, float] = field(default_factory=dict)
    costs: Dict[str, float] = field(default_factory=dict)
    risk: Dict[str, Any] = field(default_factory=dict)
    success: float = 1.0                   # โอกาสสำเร็จพื้นฐานของ action ที่ไม่ใช่การต่อสู้
    relevant_goals: List[str] = field(default_factory=list)
    personality: Dict[str, float] = field(default_factory=dict)
    social: str = "none"                   # help / harm / betray / bond / flee / none
    memory_tags: List[str] = field(default_factory=list)
    environment: Dict[str, float] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    legacy_kind: Optional[str] = None
    goap: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_combat(self):
        return bool(self.risk.get("combat"))

    @property
    def needs_target(self):
        return self.target != "none"

    @classmethod
    def from_dict(cls, aid, d, defaults=None):
        d = dict(defaults or {}, **(d or {}))
        known = {f for f in cls.__dataclass_fields__}
        kw = {k: v for k, v in d.items() if k in known and k != "id"}
        for k in ("requirements", "effects", "relevant_goals", "memory_tags", "tags"):
            kw[k] = list(kw.get(k) or [])
        for k in ("rewards", "costs", "risk", "personality", "environment", "goap"):
            kw[k] = dict(kw.get(k) or {})
        spec = cls(id=str(aid), **kw)
        if spec.target not in TARGET_TYPES:
            raise ValueError(f"action {aid}: target '{spec.target}' ไม่รู้จัก ({TARGET_TYPES})")
        return spec

    def tag_list(self, target=None, location=None):
        """แท็กความจำที่เกี่ยวกับ action นี้ (เติม {id} {target} {target_kind} {location})"""
        out = []
        for t in self.memory_tags or ["action:{id}"]:
            if "{target" in t and target is None:
                continue
            if "{location}" in t and location is None:
                continue
            out.append(t.format(id=self.id, target=getattr(target, "eid", target),
                                target_kind=getattr(target, "kind", ""), location=location))
        return out


# ---------------------------------------------------------------- requirements (ตามชื่อ — pickle ได้)
def _enemy_visible(ctx, spec, target):
    return any(e.hostile for e in ctx.entities)


def _ally_in_danger(ctx, spec, target):
    return bool(ctx.allies_in_danger())


def _can_attack(ctx, spec, target):
    """§32: "Decision Engine ห้ามใช้ HP อย่างเดียว" — ถ้ามีแบบจำลองร่างกายให้ถามร่างกาย

    HP ยังเป็นเงื่อนไขอยู่ (ตายแล้วไม่สู้) แต่คนที่ HP เต็มและขาหักสองข้างก็สู้ไม่ได้
    โลกที่ไม่มีแบบจำลองร่างกาย (known=False) ใช้เกณฑ์เดิมทุกประการ
    """
    if ctx.state.stamina < spec.costs.get("stamina", 0.0) or ctx.state.hp <= 0:
        return False
    cap = ctx.state.body
    return cap.can_fight if cap.known else True


def _has_food(ctx, spec, target):
    return ctx.state.inventory.get("food", 0) > 0


def _has_money(ctx, spec, target):
    return ctx.state.money >= spec.costs.get("resources", 0.0)


def _not_exhausted(ctx, spec, target):
    return ctx.state.fatigue < 0.95


def _can_move(ctx, spec, target):
    """ขยับตัวเองได้ไหม — ยืนไหวและยังรู้สึกตัว (§32 CanStand)"""
    cap = ctx.state.body
    return (cap.can_stand and cap.conscious) if cap.known else True


def _target_available(ctx, spec, target):
    return bool(eligible_targets(ctx, spec))


REQUIREMENTS: Dict[str, Callable] = {
    "enemy_visible": _enemy_visible,
    "ally_in_danger": _ally_in_danger,
    "can_attack": _can_attack,
    "has_food": _has_food,
    "has_money": _has_money,
    "not_exhausted": _not_exhausted,
    "can_move": _can_move,
    "target_available": _target_available,
}


def register_requirement(name, fn):
    REQUIREMENTS[name] = fn


def check_requirement(name, ctx, spec, target=None):
    neg = name.startswith("!")
    name = name[1:] if neg else name
    if name.startswith("fact:"):
        ok = bool(ctx.facts.get(name[5:], False))
    else:
        fn = REQUIREMENTS.get(name)
        if fn is None:
            raise KeyError(f"requirement '{name}' ไม่ได้ลงทะเบียน (ดู actions.REQUIREMENTS)")
        ok = bool(fn(ctx, spec, target))
    return not ok if neg else ok


def eligible_targets(ctx, spec):
    t = spec.target
    if t == "none":
        return []
    ents = ctx.entities
    if t == "enemy":
        return [e for e in ents if e.hostile]
    if t == "ally":
        return [e for e in ents if e.relation.affection > 0]
    if t == "ally_in_danger":
        return [e for e in ents if e.relation.affection > 0 and e.in_danger > 0]
    if t == "threat_to_ally":
        endangered = {e.eid for e in ctx.allies_in_danger()}
        return [e for e in ents if endangered.intersection(e.threatens)]
    if t == "beast":
        return [e for e in ents if e.kind == "beast"]
    if t == "loot":
        return [e for e in ents if e.has_loot]
    return list(ents)


# ---------------------------------------------------------------- registry + candidate filter
class ActionRegistry:
    def __init__(self, specs=None):
        self.specs: Dict[str, ActionSpec] = {}
        self.by_legacy: Dict[str, ActionSpec] = {}
        for s in specs or ():
            self.add(s)

    def add(self, spec: ActionSpec):
        self.specs[spec.id] = spec
        if spec.legacy_kind:
            self.by_legacy[spec.legacy_kind] = spec
        return spec

    def get(self, aid):
        return self.specs.get(aid)

    def __contains__(self, aid):
        return aid in self.specs

    def __len__(self):
        return len(self.specs)

    @classmethod
    def from_config(cls, cfg, section):
        sec = cfg.get(section, {}) or {}
        defaults = sec.get("defaults", {}) or {}
        reg = cls()
        for aid, d in (sec.get("actions", {}) or {}).items():
            reg.add(ActionSpec.from_dict(aid, d, defaults))
        return reg

    def candidates(self, ctx, ids=None, stats=None):
        """All Actions → Requirement Check → Context Filter → Candidate Actions"""
        pool = [self.specs[i] for i in ids if i in self.specs] if ids is not None \
            else list(self.specs.values())
        out = []
        for spec in pool:
            if not all(check_requirement(r, ctx, spec) for r in spec.requirements):
                if stats is not None:
                    stats["requirement"] = stats.get("requirement", 0) + 1
                continue
            if spec.needs_target and spec.target_select == "engine" and not eligible_targets(ctx, spec):
                if stats is not None:
                    stats["context"] = stats.get("context", 0) + 1
                continue
            out.append(spec)
        return out
