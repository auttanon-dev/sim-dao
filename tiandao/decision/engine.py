# -*- coding: utf-8 -*-
"""Decision Engine — แกนกลางแบบ Hybrid (ไม่ผูกกับโลกใดโลกหนึ่ง)

    DecisionContext
      → Candidate filter (requirement → context → LOD limit)
      → Goal Selection (Utility AI: ต้องการอะไร)  → GOAP (ทำอย่างไร)  → plan
      → Utility Scoring ของทุก (action, target)  [scoring.py]
      → Softmax (temperature × ความไม่แน่นอน, seed)
      → Decision (+ Explanation ถ้าเปิด)
    หลัง execute: feedback() → Memory / Belief / Relationship / plan progress

การผูกกับ Sim Dao อยู่ใน simdao.py — ไฟล์นี้ไม่ import อะไรจากเอนจินโลกเลย จึงเทสต์ได้ด้วยสถานการณ์
สังเคราะห์ (Li Wei กับหมาป่า) และนำไปใช้กับโลกอื่นได้
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from . import config as DCFG
from . import softmax as SM
from .actions import ActionRegistry, eligible_targets
from .context import AgentMind, GoalChoice, PerceivedEntity
from .explanation import DecisionExplanation
from .goals import GoalEvaluator
from .planner import GoapPlanner
from .scoring import UtilityScorer


@dataclass
class Decision:
    action_id: Optional[str]
    target: Any = None
    breakdown: Any = None
    options: List[Any] = field(default_factory=list)
    probabilities: List[float] = field(default_factory=list)
    probability: float = 0.0
    temperature: float = 0.0
    mode: str = "stochastic"
    goal: str = ""
    plan: List[str] = field(default_factory=list)
    explanation: Optional[DecisionExplanation] = None
    stats: Dict[str, int] = field(default_factory=dict)

    def probability_of(self, action_id):
        """รวม P ของทุกเป้าหมายของ action นี้"""
        return sum(p for o, p in zip(self.options, self.probabilities) if o.action_id == action_id)

    def utility_of(self, action_id):
        vals = [o.utility for o in self.options if o.action_id == action_id]
        return max(vals) if vals else None

    def option(self, action_id, target=None):
        for o in self.options:
            if o.action_id == action_id and (target is None or o.target == target):
                return o
        return None


class DecisionEngine:
    def __init__(self, cfg=None, section="demo", registry=None, mode=None):
        self.cfg = cfg or DCFG.load()
        self.section = section
        self.registry = registry or ActionRegistry.from_config(self.cfg, section)
        self.scorer = UtilityScorer(self.cfg)
        self.goals = GoalEvaluator(self.cfg, section)
        self.planner = GoapPlanner(self.cfg, self.registry)
        self.mode = mode                      # None = ใช้ของ profile/config
        self.minds: Dict[Any, AgentMind] = {}
        self.stats: Dict[str, float] = {}

    # ---------------------------------------------------------------- จิตใจถาวร
    def mind(self, agent_id, name=""):
        m = self.minds.get(agent_id)
        if m is None:
            m = AgentMind(agent_id=agent_id, name=name)
            self.minds[agent_id] = m
        return m

    def _bump(self, key, n=1):
        self.stats[key] = self.stats.get(key, 0) + n

    # ---------------------------------------------------------------- Goal → GOAP
    def update_goal(self, ctx, rng=None, mode="stochastic", available=None):
        m = ctx.mind
        recheck = ctx.extra.get("recheck_goal", True)
        if recheck or not m.goal:
            choice = self.goals.evaluate(ctx, current=m.goal, rng=rng, mode=mode)
            self._bump("goal_evals")
            if choice.goal_id != m.goal:
                m.goal, m.plan = choice.goal_id, []
            m.goal_day = ctx.now
            ctx.goal = choice
        else:
            ctx.goal = GoalChoice(goal_id=m.goal, score=0.0, ranking=[(m.goal, 0.0)])
        if not m.goal:
            ctx.plan = []
            return
        need_plan = (not m.plan or m.plan_goal != m.goal
                     or (available is not None and m.plan[0] not in available))
        if need_plan and ctx.extra.get("use_planner", True):
            g = self.goals.get(m.goal)
            t = ctx.traits
            att = max(self.cfg.get("risk.personality_min", 0.3),
                      1.0 + self.cfg.get("risk.personality", 0.8) * (t.get("caution", 0.5) - t.get("bravery", 0.5)))
            p = self.planner.plan(m.goal, g.desired if g else {}, ctx.facts, available, att)
            self._bump("plans")
            m.plan = p.steps if p.found else []
            m.plan_goal, m.plan_day = m.goal, ctx.now
        ctx.plan = list(m.plan)

    # ---------------------------------------------------------------- ตัดสินใจ
    def _lod_value(self, key, lod, default):
        table = self.cfg.get(f"lod.{key}", {}) or {}
        return table.get(lod, table.get(str(lod), default))

    def decide(self, ctx, rng=None, candidate_ids=None, explain=None):
        cfg = self.cfg
        prof = cfg.profile(ctx.profile)
        weights = prof["weights"]
        mode = self.mode or prof.get("mode", "stochastic")
        lod = ctx.lod
        stats = {}

        cands = self.registry.candidates(ctx, candidate_ids, stats)
        limit = int(self._lod_value("candidate_limit", lod, 64))
        if len(cands) > limit:
            # LOD: ตัดตัวเลือกที่ระบบเดิมให้น้ำหนักต่ำทิ้งก่อน (ไม่ต้องคิด utility ให้ action หลายร้อยตัว)
            cands.sort(key=lambda s: (-ctx.legacy.get(s.legacy_kind or s.id, 0.0), s.id))
            stats["lod_cut"] = len(cands) - limit
            cands = cands[:limit]
        if not cands:
            return Decision(None, stats=stats)
        available = {s.id for s in cands}

        ctx.extra.setdefault("use_planner", bool(self._lod_value("use_planner", lod, True)))
        if self.goals.goals:
            self.update_goal(ctx, rng, mode, available)

        use_targets = bool(self._lod_value("use_targets", lod, True))
        tlimit = int(min(self._lod_value("target_limit", lod, 4),
                         cfg.get("engine.max_target_options", 4)))
        simplified = lod >= 2
        options = []
        for spec in cands:
            if spec.needs_target and spec.target_select == "engine" and use_targets and tlimit > 0:
                targets = eligible_targets(ctx, spec)
                targets.sort(key=lambda e: (-(e.relation.hatred + e.relation.affection + e.in_danger
                                              + (1.0 if e.hostile else 0.0)), str(e.eid)))
                for t in targets[:tlimit]:
                    options.append(self.scorer.score(ctx, spec, t, weights, simplified))
            else:
                options.append(self.scorer.score(ctx, spec, None, weights, simplified))
        stats["options"] = len(options)
        self._bump("decisions")
        self._bump("options", len(options))

        # ความไม่แน่นอนของข้อมูลทำให้ใจลังเลขึ้น — temperature ขยายตามความมั่นใจเฉลี่ยที่ต่ำ
        T = max(cfg.get("engine.temperature_min", 0.01), float(prof["temperature"]))
        confs = [o.factors["belief_confidence"].raw for o in options]
        avg_conf = sum(confs) / len(confs) if confs else 1.0
        T_eff = T * (1.0 + cfg.get("engine.uncertainty_temperature", 0.5) * (1.0 - avg_conf))
        idx, probs = SM.select([o.utility for o in options], T_eff, mode, rng)
        chosen = options[idx]
        dec = Decision(chosen.action_id, chosen.target, chosen, options, probs, probs[idx], T_eff, mode,
                       ctx.goal.goal_id if ctx.goal else "", list(ctx.plan), None, stats)
        ctx.mind.decisions += 1
        ctx.mind.habituate(chosen.action_id, ctx.now, cfg)
        ctx.mind.last = {"action": chosen.action_id, "target": chosen.target, "p_success": chosen.p_success,
                         "utility": chosen.utility, "now": ctx.now}
        if explain is None:
            explain = cfg.get("engine.explain", True)
        if explain:
            dec.explanation = DecisionExplanation.build(dec, ctx, cfg)
        return dec

    # ---------------------------------------------------------------- Feedback Loop
    def feedback(self, mind: AgentMind, now, action_id, target=None, target_kind="", location=None,
                 success=None, damage=0.0, near_death=False, died=False, reward=None,
                 revealed_power=None, self_power=None, relation_changes=None, note="",
                 truth_self_power=None):
        """Observe Result → Memory Update → Belief Update → Relationship Update

        target            eid ของคู่กรณี (ถ้ามี)       revealed_power  {eid: พลังที่เห็นเต็มตาตอนปะทะ}
        damage            HP ที่เสียไป 0..1              relation_changes {eid: {dim: delta}}
        คืน dict สรุปสิ่งที่เปลี่ยน (ใช้ดีบัก/เทสต์)"""
        cfg = self.cfg
        spec = self.registry.get(action_id)
        out = {"surprise": 0.0, "memories": [], "beliefs": [], "relations": []}
        last = mind.last if mind.last and mind.last.get("action") == action_id else None
        if success is not None and last is not None:
            out["surprise"] = abs((1.0 if success else 0.0) - last.get("p_success", 1.0))
            mind.surprises += out["surprise"]

        # ---- Memory ----
        if died:
            valence = -1.0
        elif near_death:
            valence = -0.9
        elif success is None:
            valence = 0.0 if reward is None else reward
        else:
            valence = (cfg.get("memory.success_valence", 0.3) if reward is None else reward) if success \
                else cfg.get("memory.failure_valence", -0.5)
        valence = max(-1.0, min(1.0, valence - damage * 0.5))
        intensity = min(1.0, 0.25 + damage + (0.5 if near_death else 0.0) + 0.5 * out["surprise"])
        importance = 0.95 if near_death or died else 0.4 + 0.4 * abs(valence)
        # prediction error (Rescorla–Wagner): สำเร็จตามคาดแทบไม่เพิ่มความจำ ผิดคาดจำแรง
        if success is not None and last is not None:
            salience = out["surprise"]
        elif near_death or died:
            salience = 1.0
        else:
            salience = cfg.get("memory.default_salience", 0.5)
        if near_death or died:
            salience = 1.0
        out["salience"] = salience
        if spec is not None and abs(valence) > 1e-6:
            tgt = PerceivedEntity(eid=target, kind=target_kind) if target is not None else None
            for tag in spec.tag_list(tgt, location):
                mind.memory.remember(tag, valence, now, cfg, intensity, importance, note, salience)
                out["memories"].append(tag)

        # ---- Belief ----
        for eid, pw in (revealed_power or {}).items():
            mind.beliefs.observe(f"power:{eid}", pw, "combat", now, cfg, truth=pw)
            out["beliefs"].append(f"power:{eid}")
        if self_power is not None:
            mind.beliefs.observe("power:self", self_power, "self", now, cfg,
                                 truth=truth_self_power if truth_self_power is not None else self_power)
            out["beliefs"].append("power:self")

        # ---- Relationship ----
        step = cfg.get("relationship.feedback_step", 0.15)
        if target is not None and spec is not None and spec.social == "harm" and success is False:
            mind.relations.adjust(target, cfg, fear=step * (1.0 + damage), respect=step * 0.5)
            out["relations"].append(target)
        if target is not None and near_death:
            mind.relations.adjust(target, cfg, fear=step * 2, hatred=step)
            out["relations"].append(target)
        for eid, dims in (relation_changes or {}).items():
            mind.relations.adjust(eid, cfg, **dims)
            out["relations"].append(eid)

        # ---- แผน: ทำก้าวแรกสำเร็จแล้วก็เลื่อนไปก้าวถัดไป ----
        if mind.plan and mind.plan[0] == action_id and success is not False:
            mind.plan = mind.plan[1:]
        return out
