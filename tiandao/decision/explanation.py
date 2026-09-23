# -*- coding: utf-8 -*-
"""Decision Explanation — ตอบว่า "ทำไม NPC ถึงตัดสินใจแบบนี้"

สร้างจาก Breakdown ตัวเดียวกับที่ใช้คำนวณ utility จริง (ไม่คำนวณซ้ำ) จึงตรงกับค่าจริงเสมอ
ตัวเลขแสดงเป็น "แต้ม" = utility × engine.display_scale (ค่าเริ่ม 100)

    NPC: Li Wei
    Decision: attack_enemy → Wolf            P=0.61   Final Utility: 72.4
    Goal: protect_friend   Plan: attack_enemy
    Core (multiplicative): ExpectedReward 0.48 × Goal ×2.20 × Personality ×1.28 × Belief ×0.87 = +46.9
      ...
    Additive:
      Need Pressure  +12.0  (safety=0.40)
      Social         +20.1  (ปกป้อง Mei)
      Memory          -8.2  (ถูกหมาป่ากัดเกือบตาย −0.90×0.91)
      Risk           -14.3  (threat=120/180, HP 70%)
      ...
    Beliefs used: power:wolf=120 conf=0.62
    Alternatives: run_away 61.8 (P=0.21) ...
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List

LABELS = {
    "expected_reward": "Expected Reward", "goal_relevance": "Goal Relevance",
    "personality": "Personality", "belief_confidence": "Belief Confidence",
    "need_pressure": "Need Pressure", "social": "Social", "memory": "Memory",
    "environment": "Environment", "legacy_intent": "Legacy Intent", "habituation": "Habituation", "risk": "Risk",
    "energy_cost": "Energy Cost", "time_cost": "Time Cost", "resource_cost": "Resource Cost",
}


@dataclass
class DecisionExplanation:
    agent: str
    agent_id: Any
    now: float
    decision: str
    target: Any
    target_name: str
    probability: float
    utility: float
    core: float
    factors: Dict[str, dict]
    additive: Dict[str, dict]
    beliefs: List[tuple]
    memories: List[tuple]
    goal: str
    goal_ranking: List[tuple]
    plan: List[str]
    temperature: float
    mode: str
    lod: int
    profile: str
    alternatives: List[dict] = field(default_factory=list)
    scale: float = 100.0

    @classmethod
    def build(cls, decision, ctx, cfg):
        bd = decision.breakdown
        scale = cfg.get("engine.display_scale", 100)
        n_alt = int(cfg.get("engine.explain_alternatives", 4))
        alts = []
        for opt, p in sorted(zip(decision.options, decision.probabilities), key=lambda x: -x[0].utility):
            if opt is bd:
                continue
            alts.append({"action": opt.action_id, "target": opt.target, "target_name": opt.target_name,
                         "utility": opt.utility, "probability": p})
            if len(alts) >= n_alt:
                break
        return cls(
            agent=ctx.name, agent_id=ctx.agent_id, now=ctx.now, decision=bd.action_id,
            target=bd.target, target_name=bd.target_name, probability=decision.probability,
            utility=bd.utility, core=bd.core,
            factors={k: {"raw": t.raw, "weight": t.weight, "factor": t.value, "note": t.note}
                     for k, t in bd.factors.items()},
            additive={k: {"raw": t.raw, "weight": t.weight, "value": t.value, "note": t.note}
                      for k, t in bd.additive.items()},
            beliefs=list(bd.beliefs_used), memories=list(bd.memories_used),
            goal=ctx.goal.goal_id if ctx.goal else "",
            goal_ranking=[(g, round(s, 3)) for g, s in (ctx.goal.ranking[:3] if ctx.goal else [])],
            plan=list(ctx.plan), temperature=decision.temperature, mode=decision.mode,
            lod=ctx.lod, profile=ctx.profile, alternatives=alts, scale=scale)

    # ---- ตรวจความสอดคล้อง (ใช้ในเทสต์) ----
    def recomputed_utility(self):
        core = 1.0
        for f in self.factors.values():
            core *= f["factor"]
        tot = core + sum(a["value"] for a in self.additive.values())
        return core, tot

    def to_dict(self):
        return {k: getattr(self, k) for k in self.__dataclass_fields__}

    def format_text(self):
        s = self.scale
        tgt = f" → {self.target_name}" if self.target_name else ""
        lines = [f"NPC: {self.agent} (#{self.agent_id})  t={self.now:g}  LOD {self.lod}  profile={self.profile}",
                 f"Decision: {self.decision}{tgt}",
                 f"Final Utility: {self.utility * s:.1f}   P={self.probability:.2f}   "
                 f"T={self.temperature:.3f} ({self.mode})"]
        if self.goal:
            rk = ", ".join(f"{g} {v * s:.0f}" for g, v in self.goal_ranking)
            lines.append(f"Goal: {self.goal}   [{rk}]")
        if self.plan:
            lines.append("Plan: " + " → ".join(self.plan))
        lines.append("")
        lines.append("Reason breakdown:")
        fac = []
        for k, f in self.factors.items():
            fac.append(f"{LABELS.get(k, k)} {f['factor']:.2f}" if k == "expected_reward"
                       else f"{LABELS.get(k, k)} ×{f['factor']:.2f}")
        lines.append(f"  Core = {' × '.join(fac)} = {self.core * s:+.1f}")
        for k, f in self.factors.items():
            if f["note"]:
                lines.append(f"    · {LABELS.get(k, k)}: {f['note']}")
        for k, a in self.additive.items():
            if abs(a["value"]) < 1e-9 and not a["note"]:
                continue
            note = f"   ({a['note']})" if a["note"] else ""
            lines.append(f"  {LABELS.get(k, k):<16}{a['value'] * s:+7.1f}{note}")
        if self.beliefs:
            lines.append("")
            lines.append("Belief: " + "; ".join(f"{k} = {v} (confidence {c:.2f})" for k, v, c in self.beliefs))
        if self.memories:
            lines.append("Memory: " + "; ".join(f"{t} v={v:+.2f} s={st:.2f}" for t, v, st in self.memories[:4]))
        if self.alternatives:
            lines.append("")
            lines.append("Alternative:")
            for a in self.alternatives:
                tn = f" → {a['target_name']}" if a["target_name"] else ""
                lines.append(f"  {a['action']}{tn}  Score = {a['utility'] * s:.1f}  (P={a['probability']:.2f})")
        return "\n".join(lines)
