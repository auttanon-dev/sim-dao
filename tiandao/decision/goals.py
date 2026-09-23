# -*- coding: utf-8 -*-
"""Goal Selection — Utility AI ระดับบน: "ตอนนี้ฉันควรต้องการอะไร?"

    score(goal) = (base + Σ w_n·need_n) × (1 + w_pers·PB(goal))
                + urgency_gain · max(need_n ที่เกี่ยว)^urgency_power
                + social (เฉพาะเป้าหมายแบบ protect: ความรัก × อันตรายของคนที่รัก)
                + commitment (ถ้าเป็นเป้าหมายเดิม — กันใจโลเล)

เป้าหมายที่ข้อเท็จจริงในใจบอกว่า "สำเร็จแล้ว" (desired ⊆ facts) หรือเงื่อนไขไม่ครบ (requires) ถูกข้าม
ไม่มีเป้าหมายไหนเกิน min_score = ไม่มีอะไรกดดัน (ไม่มี goal) → action ตัดสินด้วย utility ล้วน
เลือกด้วย softmax (goal_selection.temperature) — แล้วส่งต่อให้ GOAP ตอบว่า "จะทำอย่างไร"
"""
from dataclasses import dataclass, field
from typing import Dict, List

from . import softmax as SM
from .context import GoalChoice
from .scoring import UtilityScorer


@dataclass
class GoalDef:
    id: str
    needs: Dict[str, float] = field(default_factory=dict)
    personality: Dict[str, float] = field(default_factory=dict)
    desired: Dict[str, bool] = field(default_factory=dict)
    requires: List[str] = field(default_factory=list)
    base: float = 0.0
    social: str = ""

    @classmethod
    def from_dict(cls, gid, d):
        d = d or {}
        return cls(id=gid, needs=dict(d.get("needs") or {}), personality=dict(d.get("personality") or {}),
                   desired=dict(d.get("desired") or {}), requires=list(d.get("requires") or []),
                   base=float(d.get("base", 0.0)), social=str(d.get("social") or ""))


class GoalEvaluator:
    def __init__(self, cfg, section):
        self.cfg = cfg
        self.goals = [GoalDef.from_dict(g, d) for g, d in ((cfg.get(section, {}) or {}).get("goals") or {}).items()]

    def _ok(self, g, facts):
        for r in g.requires:
            neg = r.startswith("!")
            name = r[1:] if neg else r
            if bool(facts.get(name, False)) == neg:
                return False
        if g.desired and all(bool(facts.get(k, False)) == bool(v) for k, v in g.desired.items()):
            return False          # สำเร็จอยู่แล้ว
        return True

    def evaluate(self, ctx, current="", rng=None, mode="stochastic"):
        cfg = self.cfg
        gs = "goal_selection."
        rows, reasons = [], {}
        for g in self.goals:
            if not self._ok(g, ctx.facts):
                continue
            base = g.base + sum(w * ctx.needs.get(n, 0.0) for n, w in g.needs.items())
            pb, _ = UtilityScorer.trait_bias(g.personality, ctx.traits)
            s = base * (1.0 + cfg.get(gs + "personality_gain", 0.4) * pb)
            rel = [ctx.needs.get(n, 0.0) for n, w in g.needs.items() if w > 0]
            if rel:
                s += cfg.get(gs + "urgency_gain", 0.5) * max(rel) ** cfg.get(gs + "urgency_power", 2.0)
            if g.social == "protect":
                s += max((e.relation.affection * e.in_danger for e in ctx.allies_in_danger()), default=0.0)
            if g.id == current:
                s += cfg.get(gs + "commitment", 0.12)
            rows.append((g.id, s))
            reasons[g.id] = round(s, 4)
        if not rows or max(s for _, s in rows) < cfg.get(gs + "min_score", 0.0):
            return GoalChoice(ranking=sorted(rows, key=lambda r: -r[1]), reasons=reasons)
        idx, probs = SM.select([s for _, s in rows], cfg.get(gs + "temperature", 0.08), mode, rng)
        ranking = sorted(rows, key=lambda r: -r[1])
        return GoalChoice(goal_id=rows[idx][0], score=rows[idx][1], ranking=ranking, reasons=reasons)

    def get(self, gid):
        for g in self.goals:
            if g.id == gid:
                return g
        return None
