# -*- coding: utf-8 -*-
"""Utility Scoring — ระบบกลางที่ประเมินทุก action (action ไม่มี logic ของตัวเอง)

    core    = ER·w_er × (1 + w_goal·GR) × clamp(1 + w_pers·PB) × max(min, 1 − w_conf·(1−conf)·aversion)
    Utility = core + w_need·NP + w_social·S + w_mem·M + w_env·E + w_legacy·L
                   − w_risk·R − w_energy·EC − w_time·TC − w_res·RC

ทุกองค์ประกอบถูก normalize ก่อนรวม:
    ER, GR, NP, R, EC, TC, RC, H ∈ [0, 1]      PB, S, M, E ∈ [−1, 1]
    L (legacy log-prior ln(w/ḡ)) ไม่บีบ — ช่วงของ utility ทั้งก้อนถูก clamp แทน
Utility ถูก clamp ใน [engine.utility_min, engine.utility_max]

ที่มาทางคณิตศาสตร์/ฟิสิกส์ของแต่ละพจน์
    P(success)  Bradley–Terry / logistic ของ ln(พลังตัวเอง / พลังศัตรูตามความเชื่อ)
    Risk        กฎกำลังสองของ Lanchester → E[ความเสียหาย] และ P(แพ้) → 1 − exp(−raw)  (saturating)
    Energy      relative depletion  1 − exp(−k·s/R)
    Time        exponential discounting  1 − exp(−ρt)  ρ ขึ้นกับ patience
    Memory      Ebbinghaus forgetting curve + Rescorla–Wagner salience (memory.py) → tanh
    Habituation leaky integrator h ← h·e^(−Δt/τ) + 1 → 1 − e^(−h/h₀)  (ทำซ้ำแล้วเบื่อ)
    Belief      Kalman / inverse-variance fusion (beliefs.py) → ConfidenceFactor
    Selection   Boltzmann distribution (softmax.py)

Breakdown คือ "แหล่งความจริงเดียว": utility คำนวณจาก Breakdown.total() และ Decision Explanation
อ่านจาก Breakdown ตัวเดียวกัน — คำอธิบายจึงตรงกับค่าที่ใช้จริงเสมอ (TEST 10)
"""
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .actions import ActionSpec


def _clamp(x, lo, hi):
    return lo if x < lo else hi if x > hi else x


def lanchester_loss(me, enemy):
    """สัดส่วนกำลังที่เสียไปเมื่อ "ชนะ" ตามกฎกำลังสองของ Lanchester: 1 − √(1 − (B/A)²)"""
    try:
        from .. import physics as PHYS          # reuse ของเดิมใน Sim Dao ถ้ามี
        side, left = PHYS.lanchester(me, enemy)
        return 1.0 - left if side > 0 else 1.0
    except ImportError:                           # ใช้ engine นอก Sim Dao
        if enemy >= me:
            return 1.0
        return 1.0 - math.sqrt(1.0 - (enemy / me) ** 2)


def _logistic(z):
    if z >= 0:
        return 1.0 / (1.0 + math.exp(-z))
    ez = math.exp(z)
    return ez / (1.0 + ez)


@dataclass
class Term:
    name: str
    raw: float            # ค่าหลัง normalize
    weight: float
    value: float          # multiplicative: ตัวคูณ · additive: ส่วนที่บวก/ลบเข้า utility จริง
    note: str = ""


@dataclass
class Breakdown:
    action_id: str
    target: Any = None
    target_name: str = ""
    factors: Dict[str, Term] = field(default_factory=dict)     # expected_reward / goal / personality / belief
    additive: Dict[str, Term] = field(default_factory=dict)
    core: float = 0.0
    utility: float = 0.0
    utility_min: float = -3.0
    utility_max: float = 3.0
    p_success: float = 1.0
    enemy_power: Optional[float] = None
    enemy_confidence: Optional[float] = None
    self_power: Optional[float] = None
    beliefs_used: List[Tuple[str, Any, float]] = field(default_factory=list)
    memories_used: List[Tuple[str, float, float]] = field(default_factory=list)  # (tag, valence, strength)

    @property
    def key(self):
        return self.action_id if self.target is None else f"{self.action_id}@{self.target}"

    def compute_core(self):
        c = 1.0
        for t in self.factors.values():
            c *= t.value
        return c

    def total(self):
        raw = self.compute_core() + sum(t.value for t in self.additive.values())
        return _clamp(raw, self.utility_min, self.utility_max)


class UtilityScorer:
    def __init__(self, cfg):
        self.cfg = cfg

    # ---------------------------------------------------------------- ตัวช่วยบุคลิก
    @staticmethod
    def trait_bias(coefs, traits):
        """Σ coef × (trait − 0.5)×2 / Σ|coef| ∈ [−1,1] + รายการ trait ที่มีผลมากสุด"""
        if not coefs:
            return 0.0, []
        tot = sum(abs(v) for v in coefs.values()) or 1.0
        parts = []
        for t, c in coefs.items():
            parts.append((t, c * (traits.get(t, 0.5) - 0.5) * 2.0))
        parts.sort(key=lambda p: -abs(p[1]))
        return _clamp(sum(p[1] for p in parts) / tot, -1.0, 1.0), parts

    def valuation(self, cat, traits):
        table = (self.cfg.get("reward_valuation", {}) or {}).get(cat) or {}
        v = 1.0 + sum(c * (traits.get(t, 0.5) - 0.5) * 2.0 for t, c in table.items())
        return max(self.cfg.get("reward_valuation.valuation_min", 0.1), v)

    # ---------------------------------------------------------------- พลังตามความเชื่อ
    def perceived_self(self, ctx):
        cfg = self.cfg
        v, conf = ctx.beliefs.get("power:self", ctx.now, cfg)
        if v is None:
            v = ctx.state.power
        bias = cfg.get("belief.self_bias", 0.25) * (ctx.traits.get("bravery", 0.5)
                                                  - ctx.traits.get("caution", 0.5))
        return max(1e-6, v * (1.0 + bias))

    def perceived_enemy(self, ctx, spec, target):
        """(พลังศัตรูที่ใช้คิด, ความมั่นใจ, key ของ belief) — อ่าน BeliefStore เท่านั้น"""
        cfg = self.cfg
        key = None
        if target is not None:
            key = f"power:{target.eid}"
        elif spec.risk.get("threat_key"):
            key = spec.risk["threat_key"].format(location=ctx.state.location, id=spec.id)
        v, conf = (None, 0.0) if key is None else ctx.beliefs.get(key, ctx.now, cfg)
        if v is None:
            # ไม่รู้อะไรเลย — สมมติว่าพอๆ กับตัวเอง × default_threat และไม่มั่นใจ
            v = self.perceived_self(ctx) * cfg.get("risk.default_threat", 1.0)
            conf = cfg.get("belief.default_power_confidence", 0.15)
        tilt = ctx.traits.get("caution", 0.5) - ctx.traits.get("bravery", 0.5)
        used = v * (1.0 + cfg.get("belief.pessimism", 0.6) * (1.0 - conf) * tilt)
        return max(1e-6, used), conf, key, v

    # ---------------------------------------------------------------- score หนึ่งตัวเลือก
    def score(self, ctx, spec: ActionSpec, target=None, weights=None, simplified=False):
        cfg = self.cfg
        w = weights or cfg.need("weights")
        traits = ctx.traits
        bd = Breakdown(spec.id, None if target is None else target.eid,
                       "" if target is None else (target.name or str(target.eid)),
                       utility_min=cfg.get("engine.utility_min", -3.0),
                       utility_max=cfg.get("engine.utility_max", 3.0))

        # ---- ความน่าจะเป็นที่จะสำเร็จ (จากความเชื่อ) ----
        conf_used = 1.0
        conf_notes = []
        if spec.is_combat and not simplified:
            me = self.perceived_self(ctx)
            enemy, conf, key, believed = self.perceived_enemy(ctx, spec, target)
            # Bradley–Terry: P(win) = A^k / (A^k + B^k) = logistic(k·ln(A/B)),  k = 1/win_scale
            # (สมมูลกับ Elo ใน physics.elo_expected เมื่อ rating ∝ ln พลัง)
            p_win = _logistic(math.log(me / enemy) / cfg.get("risk.win_scale", 0.35))
            bd.p_success, bd.enemy_power, bd.enemy_confidence, bd.self_power = p_win, believed, conf, me
            conf_used = conf
            if key:
                bd.beliefs_used.append((key, float(f"{believed:.4g}"), round(conf, 3)))
                conf_notes.append(f"{key}={believed:.3g} conf={conf:.2f}")
            else:
                conf_notes.append(f"ไม่รู้พลังอีกฝ่าย conf={conf:.2f}")
        else:
            esc, esc_note = self.escape_odds(ctx, spec, target)
            bd.p_success = spec.success if esc is None else esc
            if esc_note:
                conf_notes.append(esc_note)
            for k in spec.risk.get("belief_keys", []) or []:
                if simplified:
                    break
                kk = k.format(location=ctx.state.location, id=spec.id)
                v, c = ctx.beliefs.get(kk, ctx.now, cfg)
                conf_used = min(conf_used, c)
                bd.beliefs_used.append((kk, v, round(c, 3)))
                conf_notes.append(f"{kk}={v} conf={c:.2f}")

        # ---- Expected Reward ----
        # หมวด "บรรเทา" (safety/survival/hunger/...) มีค่าเท่ากับความขาดที่มีอยู่ (marginal utility
        # ของการบรรเทา = deficit ตอนนี้) — คนที่ปลอดภัยอยู่แล้วไม่ได้อะไรจากการหนี
        relief = set(cfg.get("expected_reward.relief_categories", []) or [])
        r2n = cfg.get("reward_to_need", {}) or {}
        er_raw, er_parts = 0.0, []
        for cat, amt in spec.rewards.items():
            val = self.valuation(cat, traits)
            if cat in relief:
                val *= ctx.needs.get(r2n.get(cat, cat), 0.0)
            er_raw += amt * val
            er_parts.append(f"{cat}{amt:g}×{val:.2f}")
        er = min(1.0, er_raw * bd.p_success / cfg.get("expected_reward.normalizer", 1.5))
        bd.factors["expected_reward"] = Term(
            "expected_reward", er, w.get("expected_reward", 1.0), er * w.get("expected_reward", 1.0),
            f"{' + '.join(er_parts) or '-'} × P(success)={bd.p_success:.2f}")

        # ---- Goal Relevance ----
        gr, gnote = self.goal_relevance(ctx, spec)
        wg = w.get("goal_relevance", 1.0)
        bd.factors["goal_relevance"] = Term("goal_relevance", gr, wg, 1.0 + wg * gr, gnote)

        # ---- Personality ----
        pb, parts = self.trait_bias(spec.personality, traits)
        wp = w.get("personality", 1.0)
        pf = _clamp(1.0 + wp * pb, cfg.get("personality.factor_min", 0.3),
                    cfg.get("personality.factor_max", 2.2))
        pnote = ", ".join(f"{t}={traits.get(t, 0.5):.2f}" for t, _ in parts[:3])
        bd.factors["personality"] = Term("personality", pb, wp, pf, pnote)

        # ---- Belief Confidence ----
        wc = w.get("belief_confidence", 1.0)
        aversion = cfg.get("belief.aversion_base", 0.25) + cfg.get("belief.aversion_caution", 0.75) \
            * traits.get("caution", 0.5)
        cf = max(cfg.get("belief.factor_min", 0.2), 1.0 - wc * (1.0 - conf_used) * aversion)
        bd.factors["belief_confidence"] = Term("belief_confidence", conf_used, wc, cf,
                                               "; ".join(conf_notes) or "ไม่ต้องใช้ข้อมูลที่ไม่แน่นอน")
        bd.core = bd.compute_core()

        # ---- Additive ----
        np_, npnote = self.need_pressure(ctx, spec, bd.p_success)
        self._add(bd, "need_pressure", np_, w, +1, npnote)
        if not simplified:
            s, snote = self.social(ctx, spec, target)
            self._add(bd, "social", s, w, +1, snote)
            m, hits = ctx.memory.bias(spec.tag_list(target, ctx.state.location), ctx.now, cfg)
            bd.memories_used = [(tr.tag, round(tr.valence, 2), round(st, 3)) for tr, st in hits]
            self._add(bd, "memory", m, w, +1,
                      "; ".join(f"{tr.note or tr.tag} ({tr.valence:+.2f}×{st:.2f})" for tr, st in hits[:3]))
            e, enote = self.environment(ctx, spec)
            self._add(bd, "environment", e, w, +1, enote)
        lg, lnote = self.legacy(ctx, spec)
        if lnote:
            self._add(bd, "legacy_intent", lg, w, +1, lnote)
        hv = ctx.mind.habit_level(spec.id, ctx.now, cfg) if hasattr(ctx.mind, "habit_level") else 0.0
        if hv > 0:
            hb = 1.0 - math.exp(-hv / cfg.get("habituation.scale", 3.0))
            self._add(bd, "habituation", hb, w, -1, f"ทำซ้ำสะสม h={hv:.1f}")
        r, rnote = self.risk(ctx, spec, target, bd, simplified)
        self._add(bd, "risk", r, w, -1, rnote)
        ec, tc, rc, cnote = self.costs(ctx, spec)
        self._add(bd, "energy_cost", ec, w, -1, cnote["energy"])
        self._add(bd, "time_cost", tc, w, -1, cnote["time"])
        self._add(bd, "resource_cost", rc, w, -1, cnote["resource"])
        bd.utility = bd.total()
        return bd

    @staticmethod
    def _add(bd, name, raw, w, sign, note):
        wt = w.get(name, 1.0)
        bd.additive[name] = Term(name, raw, wt, sign * wt * raw, note)

    # ---------------------------------------------------------------- องค์ประกอบ
    def goal_relevance(self, ctx, spec):
        cfg = self.cfg
        plan = ctx.plan or []
        if plan and plan[0] == spec.id:
            return cfg.get("goal_relevance.plan_next_step", 1.0), f"ก้าวถัดไปของแผน {ctx.goal.goal_id if ctx.goal else ''}"
        if spec.id in plan:
            return cfg.get("goal_relevance.plan_later_step", 0.5), "อยู่ในแผน"
        if ctx.goal is None:
            return 0.0, ""
        if ctx.goal.goal_id in spec.relevant_goals:
            return cfg.get("goal_relevance.goal_member", 0.6), f"ตรงเป้าหมาย {ctx.goal.goal_id}"
        best, why = 0.0, ""
        k = int(cfg.get("goal_selection.top_k", 3))
        for gid, sc in ctx.goal.ranking[1:k]:
            if gid in spec.relevant_goals:
                v = cfg.get("goal_relevance.secondary_goal_scale", 0.3) * _clamp(sc, 0.0, 1.0)
                if v > best:
                    best, why = v, f"เป้าหมายรอง {gid}"
        return best, why

    def need_pressure(self, ctx, spec, p_success):
        cfg = self.cfg
        mp = cfg.get("reward_to_need", {}) or {}
        tot, parts = 0.0, []
        for cat, amt in spec.rewards.items():
            need = mp.get(cat, cat)
            nv = ctx.needs.get(need, 0.0)
            if nv > 0 and amt > 0:
                tot += amt * nv
                if f"{need}={nv:.2f}" not in parts:
                    parts.append(f"{need}={nv:.2f}")
        return min(cfg.get("need_pressure.cap", 1.0), tot * p_success), ", ".join(parts)

    def social(self, ctx, spec, target):
        cfg, t = self.cfg, ctx.traits
        mode = spec.social
        if mode == "none":
            return 0.0, ""
        loyal = t.get("loyalty", 0.5)
        if mode == "help":
            cands = [target] if target is not None else ctx.allies_in_danger()
            best, who = 0.0, ""
            for e in cands:
                v = cfg.get("social.help_ally", 1.0) * e.relation.affection * max(e.in_danger, 0.0) \
                    * (0.5 + 0.5 * loyal)
                if v > best:
                    best, who = v, e.name or str(e.eid)
            return _clamp(best, -1, 1), (f"{who} ตกอยู่ในอันตราย" if who else "")
        if mode == "harm" and target is not None:
            r = target.relation
            v = (cfg.get("social.hatred_harm", 0.8) * r.hatred
                 - cfg.get("social.affection_harm", 1.0) * r.affection
                 - cfg.get("social.fear_harm", 0.4) * r.fear
                 - cfg.get("social.respect_harm", 0.2) * r.respect)
            notes = []
            if r.hatred > 0.05:
                notes.append(f"แค้น {r.hatred:.2f}")
            if r.fear > 0.05:
                notes.append(f"กลัว {r.fear:.2f}")
            prot = 0.0
            for ally in ctx.allies_in_danger():
                if ally.eid in target.threatens:
                    pv = cfg.get("social.protect_bonus", 0.9) * ally.relation.affection * ally.in_danger \
                        * (0.5 + 0.5 * loyal)
                    if pv > prot:
                        prot = pv
                        notes.append(f"ปกป้อง {ally.name or ally.eid}")
            return math.tanh(v + prot), ", ".join(notes)
        if mode == "betray":
            aff = target.relation.affection if target is not None else 0.0
            v = (-cfg.get("social.betray_loyalty", 1.2) * (0.5 * loyal + 0.5 * aff)
                 + cfg.get("social.betray_greed", 0.4) * (t.get("greed", 0.5) - 0.5) * 2)
            return math.tanh(v), f"loyalty={loyal:.2f}"
        if mode == "bond":
            if target is None:
                return 0.0, ""
            r = target.relation
            v = cfg.get("social.bond_trust", 0.6) * ((r.trust - 0.5) * 2 + r.affection - r.hatred)
            return math.tanh(v), f"trust={r.trust:.2f}"
        if mode == "flee":
            worst, who = 0.0, ""
            for e in ctx.allies_in_danger():
                v = e.relation.affection * e.in_danger
                if v > worst:
                    worst, who = v, e.name or str(e.eid)
            v = -cfg.get("social.abandon_ally", 0.7) * worst * loyal
            return _clamp(v, -1, 1), (f"ทิ้ง {who} ไว้ข้างหลัง" if who else "")
        return 0.0, ""

    def environment(self, ctx, spec):
        if not spec.environment:
            return 0.0, ""
        raw, notes = 0.0, []
        for feat, coef in spec.environment.items():
            fv = ctx.env.feature(feat)
            if fv:
                raw += coef * fv
                notes.append(f"{feat}={fv:.2f}")
        return math.tanh(raw / self.cfg.get("environment.squash", 1.0)), ", ".join(notes)

    def legacy(self, ctx, spec):
        if not ctx.legacy:
            return 0.0, ""
        k = spec.legacy_kind or spec.id
        v = ctx.legacy.get(k)
        if v is None or v <= 0:
            return 0.0, ""
        gm = ctx.extra.get("legacy_gm")
        if gm is None:
            pos = [x for x in ctx.legacy.values() if x > 0]
            gm = math.exp(sum(math.log(x) for x in pos) / len(pos)) if pos else 1.0
            ctx.extra["legacy_gm"] = gm
        x = math.log(v / gm)
        # "log" = log-prior: การสุ่มแบบ roulette เดิม (P ∝ w) คือ Boltzmann ของ ln w ที่ T=1 พอดี
        # ใส่ ln(w/ḡ) เป็นพจน์ใน utility จึงเท่ากับใช้ระบบเดิมเป็น prior แล้วให้พจน์อื่นเป็นหลักฐาน
        # (P ∝ w · e^{ΔU}) · "tanh" = บีบให้อยู่ใน [−1,1]
        if self.cfg.get("legacy_intent.mode", "tanh") == "log":
            return x, f"ln(w/ḡ) = ln({v:.1f}/{gm:.1f})"
        return math.tanh(x / self.cfg.get("legacy_intent.scale", 1.5)), \
            f"intent.weigh={v:.1f} (เฉลี่ย {gm:.1f})"

    def escape_odds(self, ctx, spec, target=None):
        """P(หนีรอด) จาก **ความเร็ว** ไม่ใช่จากพลัง (§32) — คืน (p, note) หรือ (None, "")

            P = logistic(ln(v_เรา / v_ผู้ไล่) / s)

        รูปเดียวกับ Bradley–Terry ที่ใช้คิดโอกาสชนะ เปลี่ยนแต่ปริมาณ: การไล่กันตัดสิน
        ด้วยความเร็ว การปะทะตัดสินด้วยพลัง ผู้ไล่ที่นับคือ **คนที่เร็วที่สุด** ที่มองเห็น
        เพราะหนีพ้นเก้าคนแต่ไม่พ้นคนที่สิบก็คือไม่พ้น

        v_เรา มาจากสภาพที่ **รู้สึก** (§33) จึงเป็นความเร็วที่เจ้าตัวคิดว่าทำได้ ไม่ใช่ของจริง
        นี่คือที่มาของพฤติกรรมที่พรอมต์ §32 ยกเป็นตัวอย่าง: ขาเจ็บ → v ตก → P(หนี) ต่ำกว่า
        P(ชนะ) → เลือกสู้ทั้งที่บาดเจ็บ ไม่ใช่เพราะกล้า แต่เพราะหนีไม่พ้น
        """
        if not spec.risk.get("escape"):
            return None, ""
        cap = ctx.state.body
        if not cap.known or cap.speed <= 0.0:
            return None, ""
        pursuers = [target] if target is not None else [e for e in ctx.entities if e.hostile]
        speeds = [e.speed for e in pursuers if e is not None and e.speed > 0.0]
        if not speeds:
            return None, ""
        fastest = max(speeds)
        p = _logistic(math.log(cap.speed / fastest)
                      / self.cfg.get("risk.escape_scale", 0.32))
        return p, f"ความเร็ว {cap.speed:.2f} vs ผู้ไล่ {fastest:.2f} m/s → P(หนีรอด)={p:.2f}"

    def risk(self, ctx, spec, target, bd, simplified=False):
        cfg = self.cfg
        rk = spec.risk
        if rk.get("injury", 0.0) + rk.get("death", 0.0) <= 0:
            return 0.0, ""
        t = ctx.traits
        notes = []
        # การปะทะ: ความเสียหายที่คาดได้จากกฎกำลังสองของ Lanchester (physics.lanchester)
        #   ชนะ (P=p): เหลือกำลัง √(1 − (B/A)²) → เสียไป 1 − √(1 − (B/A)²)
        #   แพ้ (1−p): เสียทั้งหมด
        #   E[damage] = p·(1 − √(1 − (B/A)²)) + (1 − p)        ∈ [0,1], สูสี = 1
        # ความเสี่ยงตายผูกกับโอกาสแพ้ (1 − p) ส่วนการบาดเจ็บผูกกับ E[damage]
        dmg, lose = 1.0, 1.0
        if spec.is_combat and bd.enemy_power is not None:
            me = bd.self_power
            enemy, _conf, _k, _b = self.perceived_enemy(ctx, spec, target)
            p = bd.p_success
            dmg = p * lanchester_loss(me, enemy) + (1.0 - p)
            lose = 1.0 - p
            notes.append(f"พลัง {enemy:.3g} vs {me:.3g} → E[เสียหาย]={dmg:.2f}, P(แพ้)={lose:.2f}")
        base = rk.get("injury", 0.0) * dmg + rk.get("death", 0.0) * cfg.get("risk.death_weight", 3.0) * lose
        st = ctx.state
        inj = 1.0 + cfg.get("risk.injury_hp", 1.2) * (1.0 - st.hp_ratio) \
            + cfg.get("risk.injury_wounds", 0.8) * st.injuries
        env = ctx.env
        envm = max(cfg.get("risk.env_min", 0.4),
                   1.0 + cfg.get("risk.env_danger", 0.6) * env.danger
                   - min(cfg.get("risk.env_ally_cap", 0.4), cfg.get("risk.env_ally_each", 0.1) * env.allies_nearby)
                   - min(cfg.get("risk.env_escape_cap", 0.2), cfg.get("risk.env_escape_each", 0.05) * env.escape_routes))
        pers = max(cfg.get("risk.personality_min", 0.3),
                   1.0 + cfg.get("risk.personality", 0.8) * (t.get("caution", 0.5) - t.get("bravery", 0.5)))
        memm = 1.0
        if not simplified:
            neg = ctx.memory.negative_weight(spec.tag_list(target, st.location), ctx.now, cfg)
            memm = 1.0 + cfg.get("memory.risk_gain", 0.6) * neg
            if neg > 0:
                notes.append(f"ความจำร้าย×{memm:.2f}")
        raw = base * inj * envm * pers * memm
        if inj > 1.01:
            notes.append(f"HP {st.hp_ratio:.0%}")
        notes.append(f"base={base:.2f}")
        return 1.0 - math.exp(-raw / cfg.get("risk.squash", 1.0)), ", ".join(notes)

    def costs(self, ctx, spec):
        cfg, st, t = self.cfg, ctx.state, ctx.traits
        c = spec.costs
        # แรง: สัดส่วนของแรงที่เหลือที่ต้องใช้ (relative depletion) — แรงเหลือน้อย ทุกหน่วยแพงขึ้น
        #   EC = 1 − exp(−k · s / R)          R = stamina ที่เหลือ × (1 − g·fatigue)
        # ถ้าโลกมีแบบจำลองร่างกาย (§32) ตัวคูณที่สองมาจากร่างกายจริง: effort_factor ซึ่งรวม
        # ความล้า เลือดที่เสีย เชื้อเพลิง และอุณหภูมิแกนกลางเข้าด้วยกันแบบ **คูณกัน**
        # (ดู body/condition.py) แทนการอ่านตัวเลข stamina เดิมซ้ำอีกครั้ง
        stam = c.get("stamina", 0.0)
        cap = st.body
        floor = cfg.get("costs.reserve_min", 0.05)
        if cap.known:
            left = max(floor, cap.effort)
        else:
            left = max(floor, 1.0 - cfg.get("costs.fatigue_gain", 1.0) * st.fatigue)
        reserve = max(1e-6, st.stamina * left)
        ec = 1.0 - math.exp(-cfg.get("costs.stamina_gain", 1.5) * stam / reserve) if stam > 0 else 0.0
        # เวลา: exponential discounting — ρ ขึ้นกับความอดทน (คนใจร้อนลดค่าอนาคตเร็ว)
        #   TC = 1 − exp(−ρ·t)   ρ = (1/τ) · (1 + g·(0.5 − patience)·2)
        # ถ้ารู้อายุขัยที่เหลือ H: τ = f·H (Yaari 1965 — อัตราคิดลดเวลา ∝ hazard ของความตาย)
        # ผู้บำเพ็ญที่เหลือพันปีจึงปิดด่านสามปีได้โดยไม่รู้สึกเสียดาย ส่วนคนแก่ใกล้ตายรอไม่ได้
        tm = c.get("time", 0.0)
        tau = cfg.get("costs.horizon_fraction", 0.2) * st.horizon if st.horizon > 0 \
            else cfg.get("costs.time_scale", 60.0)
        rho = (1.0 / max(1e-6, tau)) \
            * max(0.0, 1.0 + cfg.get("costs.patience_gain", 0.8) * (0.5 - t.get("patience", 0.5)) * 2)
        tc = 1.0 - math.exp(-rho * tm) if tm > 0 else 0.0
        res = c.get("resources", 0.0)
        rc = min(1.0, res / max(st.money, cfg.get("costs.resource_scale_min", 10.0))) if res > 0 else 0.0
        return (min(1.0, ec), min(1.0, tc), rc,
                {"energy": f"stamina {stam:g}" if stam else "",
                 "time": f"time {tm:g}" if tm else "",
                 "resource": f"{res:g}/{st.money:.0f}" if res else ""})
