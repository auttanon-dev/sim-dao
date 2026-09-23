# -*- coding: utf-8 -*-
"""Adapter: ผูก Decision Engine เข้ากับเอนจินวิถีสวรรค์ (tiandao/sim.py) โดยไม่รื้อของเดิม

จุดเสียบมีจุดเดียวใน Sim._step():

    w = IN.weigh(...)                      # ของเดิม — น้ำหนัก + ตัดสิ่งที่ทำไม่ได้ (requirement)
    w = brain_manager.decide(...)          # ของเดิม — Utility 7 Need + GOAP Breakthrough
    mind_choice = mind.choose(...)         # ของเดิม — ตัวเอกที่มี LLM
    if mind_choice is None and decision_engine: mind_choice = decision_engine.choose(...)   ← ใหม่
    kind = mind_choice.kind if mind_choice else IN.sample_weighted(w, rng)                ← เดิม

feedback ผูกผ่าน event_bus (เหมือน brain_manager) จึงไม่ต้องแก้ resolve()/emit() เลย

WorldState → Perception → BeliefState
  · พลังจริงของทุกคนอ่านจาก rules.power() **เฉพาะตอนสังเกต** แล้วผ่าน perceive_power() (noise +
    ปกปิดตามช่องว่างขั้น) ก่อนเก็บเป็น belief — scoring อ่านได้แต่ belief
  · ปะทะกันจริงแล้วจึงได้ "เห็นเต็มตา" (source=combat, ความมั่นใจสูง) ผ่าน feedback
  · ข่าวลือ (ได้ยินข่าวลือ) เข้า belief แบบ source=rumor ความมั่นใจต่ำ

Determinism: ไม่แตะ sim.rng เลย — เลขสุ่มทุกตัวมาจาก hash(seed, cid, seq) (ดู rng.py) และถ้าไม่ได้
attach engine โลกเดินเหมือนเดิมทุกประการ
"""
import math
from collections import deque
from dataclasses import dataclass
from typing import Any, Optional

from . import config as DCFG
from . import rng as DRNG
from .actions import ActionRegistry, ActionSpec
from .beliefs import perceive_power
from .context import AgentState, DecisionContext, Environment, PerceivedEntity
from .engine import DecisionEngine
from .relationships import Relation
from .scheduler import goal_recheck_due
from .scoring import _logistic


@dataclass
class EngineChoice:
    """หน้าตาเดียวกับ mind.manager.Choice — Sim._step ใช้แค่ .kind และ .target"""
    kind: str
    target: Any = None
    source: str = "decision_engine"


def _merge_tag_defaults(cfg, kind, tags):
    """spec อัตโนมัติสำหรับ kind ที่ไม่ได้เขียนไว้: รวม metadata ของทุก tag (reward/risk เอาค่ามาก,
    personality บวกกัน)"""
    table = cfg.get("simdao.tag_defaults", {}) or {}
    rewards, risk, pers = {}, {}, {}
    for t in tags:
        d = table.get(t) or {}
        for k, v in (d.get("rewards") or {}).items():
            rewards[k] = max(rewards.get(k, 0.0), v)
        for k, v in (d.get("risk") or {}).items():
            risk[k] = v if isinstance(v, bool) else max(risk.get(k, 0.0), v)
        for k, v in (d.get("personality") or {}).items():
            pers[k] = pers.get(k, 0.0) + v
    return {"rewards": rewards, "risk": risk, "personality": pers}


def build_registry(cfg, event_table):
    reg = ActionRegistry.from_config(cfg, "simdao")
    engine_targets = set(cfg.get("simdao.engine_targets", []) or [])
    defaults = cfg.get("simdao.defaults", {}) or {}
    for e in event_table:
        kind = e["kind"]
        spec = reg.get(kind)
        if spec is None:
            d = _merge_tag_defaults(cfg, kind, e.get("tags", ()))
            d["costs"] = {"time": sum(e["gap"]) / 2.0}
            spec = reg.add(ActionSpec.from_dict(kind, d, defaults))
        spec.legacy_kind = kind
        spec.tags = list(e.get("tags", ()))
        if e.get("tgt"):
            if spec.target == "none":
                spec.target = "any"
            spec.target_select = "engine" if kind in engine_targets else "external"
        else:
            spec.target, spec.target_select = "none", "engine"
        reg.by_legacy[kind] = spec
    return reg


def unbind(sim):
    eng = getattr(sim, "decision_engine", None)
    bus = getattr(sim, "event_bus", None)
    if eng is not None and bus is not None:
        bus._subscribers = [h for h in bus._subscribers if getattr(h, "__self__", None) is not eng]
    sim.decision_engine = None


class SimDecisionEngine(DecisionEngine):
    def __init__(self, cfg=None, mode=None, focus=(), enabled=True):
        from .. import events as E
        cfg = cfg or DCFG.load()
        super().__init__(cfg=cfg, section="simdao", registry=build_registry(cfg, E.EVENT_TABLE), mode=mode)
        self.enabled = enabled
        self.focus = set(focus)
        self.seed = 0
        self.lod_counts = {0: 0, 1: 0, 2: 0, 3: 0}
        self.source_counts = {"engine": 0, "involuntary": 0, "legacy": 0}
        self._explain = {}
        self._seen_money = {}

    # ---- pickle: ไม่เก็บ explanation (ข้อมูลดีบักชั่วคราว) ลงไฟล์เซฟ ----
    def __getstate__(self):
        st = dict(self.__dict__)
        st["_explain"] = {}
        st["_seen_money"] = {}
        return st

    def __setstate__(self, st):
        self.__dict__.update(st)
        self.__dict__.setdefault("_explain", {})
        self.__dict__.setdefault("_seen_money", {})

    def bind(self, sim):
        unbind(sim)
        self.seed = getattr(sim, "seed", 0)
        sim.decision_engine = self
        sim.event_bus.subscribe(self.on_event)
        return self

    # ================================================================ WorldState → Context
    def _power(self, sim, ch):
        from .. import rules as R
        try:
            p = R.power(ch, sim.world(ch.world_id), sim.items, sim.day)
        except Exception:
            p = 0.0
        return max(1e-3, p)

    def _level(self, ch):
        from .. import config as C
        # ช่องว่างหนึ่งชั้นโลก = TIER_STEP/REALM_STEP ขั้น (อัตราส่วนเดียวกับที่ rules.power ใช้)
        return ch.tier * (C.TIER_STEP / C.REALM_STEP) + ch.realm

    def _see_power(self, mind, sim, actor, other, key, force=False):
        """perception: ถ้าความเชื่อเดิมยังสดพอก็ไม่มองใหม่ (ประหยัด + ความเชื่อไม่แกว่ง)"""
        cfg = self.cfg
        v, conf = mind.beliefs.get(key, sim.day, cfg)
        if not force and v is not None and conf >= cfg.get("belief.refresh_confidence", 0.4):
            return
        truth = self._power(sim, other)
        gap = self._level(other) - self._level(actor)
        period = int(sim.day // max(1, cfg.get("perception.refresh_period", 60)))
        seen, c = perceive_power(truth, gap, cfg, (self.seed, actor.cid, other.cid, period))
        mind.beliefs.observe(key, seen, "sight", sim.day, cfg, confidence=c, truth=truth)

    def _see_self(self, mind, sim, actor):
        cfg = self.cfg
        v, conf = mind.beliefs.get("power:self", sim.day, cfg)
        if v is not None and conf >= cfg.get("belief.refresh_confidence", 0.4):
            return
        truth = self._power(sim, actor)
        mind.beliefs.observe("power:self", truth, "self", sim.day, cfg, truth=truth)

    def _relation(self, actor, c, mind, sim):
        cfg = self.cfg
        kin = cfg.get("simdao.kin_affection", {}) or {}
        bond = actor.bonds.get(c.cid, 0)
        riv = actor.rivals.get(c.cid, 0)
        aff = math.tanh(max(0, bond) / cfg.get("relationship.bond_scale", 10.0))
        if actor.spouse == c.cid:
            aff = max(aff, kin.get("spouse", 0.8))
        if c.cid in actor.parents:
            aff = max(aff, kin.get("parent", 0.7))
        if c.cid in actor.children:
            aff = max(aff, kin.get("child", 0.7))
        if actor.master_cid == c.cid:
            aff = max(aff, kin.get("master", 0.6))
        if c.cid in actor.disciples:
            aff = max(aff, kin.get("disciple", 0.5))
        same_org = actor.org is not None and actor.org == c.org
        same_clan = actor.clan >= 0 and actor.clan == c.clan
        if same_org:
            aff = max(aff, kin.get("org", 0.25))
        if same_clan:
            aff = max(aff, kin.get("clan", 0.3))
        hatred = math.tanh(max(0, riv) / cfg.get("relationship.rival_scale", 10.0))
        owe = sum(1 for d in actor.debts if not d.get("done") and d.get("target") == c.cid)
        base = Relation(trust=0.5 + 0.5 * aff - 0.5 * hatred, affection=aff, hatred=hatred,
                        debt=math.tanh(owe), loyalty=aff if (same_org or same_clan) else 0.0,
                        faction=1.0 if (same_org or same_clan) else (-1.0 if hatred > 0.5 else 0.0))
        return mind.relations.get(c.cid, base.clamp())

    def _entities(self, mind, sim, actor, others, lod):
        cfg = self.cfg
        cap = int(cfg.get("simdao.max_entities", 12))

        def rank(c):
            personal = actor.bonds.get(c.cid, 0) + actor.rivals.get(c.cid, 0) \
                + (5 if actor.cid in c.rivals else 0)
            return (-personal, c.cid)
        seen = sorted(others, key=rank)[:cap]
        ents, chars = [], {}
        self._seen_money[actor.cid] = [sum(c.money.values()) if c.money else 0.0 for c in seen]
        for c in seen:
            if not c.alive:
                continue
            if lod <= 1:
                self._see_power(mind, sim, actor, c, f"power:{c.cid}")
            rel = self._relation(actor, c, mind, sim)
            hostile = actor.rivals.get(c.cid, 0) > 0 or c.rivals.get(actor.cid, 0) > 0
            loot = any(sim.items[i].kind != "ยาวิเศษ" for i in c.items if i in sim.items)
            ents.append(PerceivedEntity(eid=c.cid, kind="beast" if c.is_beast else "npc", name=c.name,
                                        hostile=hostile, has_loot=loot, level=self._level(c),
                                        relation=rel))
            chars[c.cid] = c
        # ใครกำลังคุกคามใคร + เพื่อน "ตกอยู่ในอันตราย" = P(เพื่อนแพ้) ตามความเชื่อของเรา (Bradley–Terry)
        scale = cfg.get("risk.win_scale", 0.35)
        ratio_bar = cfg.get("simdao.ally_danger_ratio", 1.2)
        for e in ents:
            c = chars[e.eid]
            e.threatens = tuple(o.eid for o in ents if o.eid != e.eid and c.rivals.get(o.eid, 0) > 0)
        if lod <= 1:
            for ally in ents:
                if ally.relation.affection <= 0:
                    continue
                pa, _ = mind.beliefs.get(f"power:{ally.eid}", sim.day, cfg)
                worst = 0.0
                for t in ents:
                    if ally.eid not in t.threatens:
                        continue
                    pt, _ = mind.beliefs.get(f"power:{t.eid}", sim.day, cfg)
                    if pa and pt and pt >= ratio_bar * pa:
                        worst = max(worst, 1.0 - _logistic(math.log(pa / pt) / scale))
                ally.in_danger = worst
        return ents, chars

    def _traits(self, ch):
        emo, des = ch.emotions or {}, ch.desires or {}
        tr = set(ch.traits or ())
        fear, greed, comp = ch.fear, ch.greed, ch.compassion

        def cl(x):
            return 0.0 if x < 0 else 1.0 if x > 1 else x
        return {
            "bravery": cl(1.0 - fear + (0.2 if "บ้าพลัง" in tr else 0) - (0.2 if "ขลาดกลัว" in tr else 0)),
            "caution": cl(fear + (0.25 if "ขลาดกลัว" in tr else 0)),
            "greed": cl(greed + (0.2 if "โลภมาก" in tr else 0)),
            "kindness": cl(comp + (0.2 if "ใจโอบอ้อม" in tr else 0)),
            "aggression": cl(0.5 * emo.get("โกรธ", 0) + 0.3 * emo.get("ชิงชัง", 0)
                             + (0.3 if "พยาบาท" in tr else 0)
                             + (0.2 if ch.archetype == "มารหิวกระหาย" else 0)),
            "loyalty": cl(getattr(ch, "loyalty", 50) / 100.0),
            "curiosity": cl(0.6 * des.get("อยากรู้", 0.5) + (0.3 if "ใฝ่รู้" in tr else 0) + 0.1),
            "ambition": cl(0.5 * getattr(ch, "ambition", 50) / 100.0 + 0.5 * des.get("อยากเป็นใหญ่", 0.5)),
            "patience": cl(1.0 - 0.6 * emo.get("โกรธ", 0) - 0.3 * emo.get("อยาก", 0) + 0.2),
            "honor": cl(0.5 + getattr(ch, "moral", 0) / 100.0),
            "selfishness": cl(0.5 * greed + 0.5 * (1.0 - comp)),
        }

    def _needs(self, ch, sim, ents, mind, self_power, env_danger):
        from ..ai import utility as UT
        cfg = self.cfg
        self._seen_money = getattr(self, "_seen_money", {})
        ut = UT.compute_needs(ch, sim)
        des = ch.desires or {}
        hp_ratio = max(0.0, min(1.0, ch.hp / max(1.0, ch.max_hp)))
        scale = cfg.get("risk.win_scale", 0.35)
        safety = 0.0
        for e in ents:
            if e.hostile:
                pe, _ = mind.beliefs.get(f"power:{e.eid}", sim.day, cfg)
                if pe:
                    safety = max(safety, 1.0 - _logistic(math.log(self_power / pe) / scale))
        # ความขาดแคลนเชิงเปรียบเทียบ (relative deprivation — Yitzhaki 1979) เทียบกับคนที่เห็น:
        #   D = E[max(0, m_j − m_i)] / (E[m_j] + ε)   → ในโลกที่ทุกคนไม่มีเงิน ไม่มีใครรู้สึกจน
        money = sum(ch.money.values()) if ch.money else 0.0
        seen = self._seen_money.get(ch.cid, [])
        if seen:
            mean = sum(seen) / len(seen)
            dep = sum(max(0.0, m - money) for m in seen) / len(seen) / (mean + cfg.get("simdao.money_epsilon", 1.0))
        else:
            dep = 0.0
        poverty = max(0.0, min(1.0, dep))
        # แรงขับยาวของหกปรารถนาเทียบกันเอง (relative motive strength): ปรารถนาที่เด่นกว่าค่าเฉลี่ยของ
        # "ใจดวงเดียวกัน" คือสิ่งที่ผลักจริง — d̂ = clamp(0.5 · d / mean(d))  ทุกตัวเท่ากัน = 0.5
        dvals = [v for v in des.values() if isinstance(v, (int, float))]
        dmean = (sum(dvals) / len(dvals)) if dvals else 0.5

        def drive(key):
            return max(0.0, min(1.0, 0.5 * des.get(key, dmean) / max(1e-6, dmean)))
        # แรงขับการบำเพ็ญ: สัดส่วนที่สะสมไปถึงกำแพงขั้นถัดไป (ยิ่งใกล้ยิ่งเร่ง) × ความทะเยอทะยาน
        from .. import rules as R
        from .. import intent as IN
        try:
            ratio = min(1.0, R.accumulation(ch) / max(1e-6, R.need(ch, sim.world(ch.world_id))))
        except Exception:
            ratio = 0.0
        training = max(ut.get("Breakthrough", 0.0) if ch.at_bottleneck() else 0.0,
                       ratio * (0.5 + 0.5 * max(drive("อยากเป็นใหญ่"), drive("อยากพ้นทุกข์"))))
        if getattr(ch, "profession", "") in IN.MUNDANE_PROFESSIONS:
            training *= cfg.get("simdao.mundane_training_scale", 0.2)
        return {
            "survival": max(1.0 - hp_ratio, min(1.0, ch.decay / 2.0), ut.get("Escape", 0.0)),
            "safety": max(safety, env_danger * 0.5),
            "longevity": ut.get("Meditate", 0.0),
            "training": training,
            "revenge": ut.get("Revenge", 0.0),
            "wealth": 0.5 * ut.get("Wealth", 0.0) * (0.5 + 0.5 * poverty) + 0.5 * poverty,
            "status": 0.5 * ut.get("Reputation", 0.0) + 0.5 * drive("อยากเป็นใหญ่"),
            "exploration": 0.5 * ut.get("DaoPursuit", 0.0) * drive("อยากรู้"),
            "social": drive("อยากเป็นที่รัก") * 0.7,
            "hunger": float(getattr(ch, "hunger", 0.0) or 0.0),
            "rest": max(0.0, 1.0 - getattr(ch, "energy", 100.0) / 100.0),
        }

    def _facts(self, ch, sim, ents, mind, self_power):
        from ..ai import goap as OLDGOAP
        cfg = self.cfg
        scale = cfg.get("risk.win_scale", 0.35)
        hostile = [e for e in ents if e.hostile]
        can_win = False
        for e in hostile:
            pe, _ = mind.beliefs.get(f"power:{e.eid}", sim.day, cfg)
            if pe and _logistic(math.log(self_power / pe) / scale) >= 0.5:
                can_win = True
        hurt = ch.decay > 1.8 or ch.hp < 0.4 * max(1.0, ch.max_hp)
        return {
            # reuse precondition ของ GOAP เดิม (tiandao/ai/goap.py) — ความรู้เกี่ยวกับตัวเอง
            "at_bottleneck": ch.at_bottleneck(),
            "has_pill": OLDGOAP._has_pill(ch, sim),
            "at_market": OLDGOAP._at_market(ch, sim),
            "at_furnace": OLDGOAP._at_furnace(ch, sim),
            "has_money": OLDGOAP._has_money(ch, sim),
            "has_materials": sum((ch.mat_stock or {}).values()) > 0,
            # ไปตลาดมือเปล่า (ไม่มีของขายและไม่มีของที่อยากซื้อ) = เสียเที่ยว — กฎเดียวกับ TRADE_EMPTY_MULT เดิม
            "has_trade_goods": sum((ch.mat_stock or {}).values()) > 0 or bool(ch.wants),
            "has_skills": bool(ch.skills),
            "enemy_near": bool(hostile),
            "believe_can_win": can_win,
            "has_rival": bool(ch.rivals),
            "ally_danger": any(e.relation.affection > 0 and e.in_danger > 0 for e in ents),
            "safe": not hostile and not hurt,
            "recovered": not hurt,
        }

    def _satisfied_facts(self, needs):
        """satisficing (Simon 1956): เป้าหมายเชิงความต้องการถือว่า "พอแล้ว" เมื่อ need ต่ำกว่าเกณฑ์"""
        bar = self.cfg.get("goal_selection.satisfied_below", 0.3)
        return {fact: needs.get(need, 0.0) < bar
                for fact, need in (self.cfg.get("simdao.need_facts", {}) or {}).items()}

    def _environment(self, ch, sim, ents):
        from .. import config as C
        heat = sim.feud_heat(ch.place) if hasattr(sim, "feud_heat") else 0.0
        # Hawkes intensity ของรอยนองเลือด → ความน่าจะเป็นเจอความรุนแรง 1 − e^(−λ/λ_cap)
        danger = 1.0 - math.exp(-heat / max(1e-6, C.FEUD_HEAT_CAP))
        brain = sim.brain_manager.brains.get(ch.cid) if hasattr(sim, "brain_manager") else None
        fact = brain.semantic.get(ch.place) if brain is not None else None
        if fact is not None:
            danger = max(danger, fact.danger)            # ความรู้จากประสบการณ์ตรง (ai/memory.py)
        allies = sum(1 for e in ents if e.relation.affection > 0.3)
        eco = sim.eco_ratio(ch.place) if hasattr(sim, "eco_ratio") else 1.0
        return Environment(danger=danger, allies_nearby=allies, crowd=min(1.0, len(ents) / 10.0),
                           features={"eco": eco, "feud_heat": heat})

    def _lod(self, ch, others):
        cfg = self.cfg
        if ch.cid in self.focus:
            return 0
        if not getattr(ch, "sentient", True) and cfg.get("simdao.lod_statistical_unsentient", True):
            return 3
        hostile = any(ch.rivals.get(c.cid, 0) > 0 or c.rivals.get(ch.cid, 0) > 0 for c in others)
        hurt = ch.decay > 1.8 or ch.hp < 0.5 * max(1.0, ch.max_hp)
        if hostile or hurt:
            return 0
        # attention: คนรอบตัวที่ "เกี่ยวกับเรา" (ผูกพัน/แค้น/ครอบครัว/สำนัก) เท่านั้นที่ต้องคิดเรื่องเป้า
        # ฝูงชนที่ไม่รู้จักใครเลย → LOD 2 (ประเมินแบบย่อ ให้โลกเลือกเป้าตามตรรกะเดิม)
        personal = any(c.cid in ch.bonds or c.cid in ch.rivals or c.cid == ch.spouse
                       or c.cid == ch.master_cid or c.cid in ch.disciples
                       or (ch.org is not None and c.org == ch.org) for c in others)
        if others and not personal:
            return 2
        if not others:
            from .. import intent as IN
            if getattr(ch, "profession", "") in IN.MUNDANE_PROFESSIONS \
                    and cfg.get("simdao.lod_statistical_mundane_alone", True):
                return 3
            return 2
        return 1

    def _profile(self, ch):
        cfg = self.cfg
        if cfg.get("simdao.cautious_trait") in (ch.traits or ()):
            return "cautious"
        return (cfg.get("simdao.profile_by_archetype", {}) or {}).get(ch.archetype, "default")

    def build_context(self, actor, sim, weights, others, lod):
        cfg = self.cfg
        mind = self.mind(actor.cid, actor.name)
        self._see_self(mind, sim, actor)
        self_power, _ = mind.beliefs.get("power:self", sim.day, cfg)
        ents, chars = self._entities(mind, sim, actor, others, lod)
        # สัตว์อสูรแถวนี้: ถ้าไม่เคยรู้ ให้คาดเดาจากอันตรายของสถานที่ (inference ความมั่นใจต่ำ)
        env = self._environment(actor, sim, ents)
        bkey = f"beast:{actor.place}"
        if mind.beliefs.get(bkey, sim.day, cfg)[0] is None and "ล่าอสูร" in weights:
            mind.beliefs.observe(bkey, self_power * math.exp(env.danger), "inference", sim.day, cfg,
                                 confidence=cfg.get("simdao.beast_prior_confidence", 0.3))
        st = AgentState(hp=float(actor.hp), hp_max=float(max(1, actor.max_hp)),
                        stamina=float(getattr(actor, "energy", 100.0)), stamina_max=100.0,
                        fatigue=max(0.0, 1.0 - getattr(actor, "energy", 100.0) / 100.0),
                        level=self._level(actor), power=self_power,
                        injuries=min(1.0, actor.decay / 2.0),
                        money=sum(actor.money.values()) if actor.money else 0.0,
                        location=actor.place,
                        horizon=max(0.0, (actor.lifespan() - actor.age(sim.day)) * 365.0))
        ctx = DecisionContext(
            agent_id=actor.cid, name=actor.name, now=sim.day, state=st,
            needs=self._needs(actor, sim, ents, mind, self_power, env.danger),
            traits=self._traits(actor), mind=mind, env=env, entities=ents,
            legacy={k: v for k, v in weights.items() if v > 0}, profile=self._profile(actor), lod=lod,
            facts=self._facts(actor, sim, ents, mind, self_power))
        ctx.facts.update(self._satisfied_facts(ctx.needs))
        ctx.extra["recheck_goal"] = goal_recheck_due(cfg, lod, mind.goal_day, sim.day, mind.woken)
        mind.woken = False
        return ctx, chars

    # ================================================================ ตัดสินใจ
    def choose(self, actor, sim, weights, others, world=None):
        if not self.enabled or not weights:
            return None
        lod = self._lod(actor, others)
        self.lod_counts[lod] = self.lod_counts.get(lod, 0) + 1
        if lod >= 3:
            self.source_counts["legacy"] += 1
            return None                      # LOD 3 = ให้ระบบเดิมสุ่มตามน้ำหนัก (statistical)
        # ฟ้าลิขิต — เรื่องที่ไม่มีใครเลือกเอง เกิดตามสัดส่วนน้ำหนักเดิม
        invol = [k for k in (self.cfg.get("simdao.involuntary", []) or []) if weights.get(k, 0) > 0]
        total = sum(v for v in weights.values() if v > 0)
        if invol and total > 0:
            iw = sum(weights[k] for k in invol)
            if DRNG.uniform(self.seed, actor.cid, sim.seq, "fate") < iw / total:
                u, acc = DRNG.uniform(self.seed, actor.cid, sim.seq, "fate-kind") * iw, 0.0
                for k in invol:
                    acc += weights[k]
                    if u <= acc:
                        self.source_counts["involuntary"] += 1
                        return EngineChoice(k, None, "ฟ้าลิขิต")
        ctx, chars = self.build_context(actor, sim, weights, others, lod)
        cands = [k for k in weights if weights[k] > 0 and k not in invol and k in self.registry]
        rng = DRNG.rng_for(self.seed, actor.cid, sim.seq, "decide")
        want_explain = bool(self.cfg.get("engine.explain", True)) and (
            lod <= int(self.cfg.get("simdao.explain_lod_max", 1)) or actor.cid in self.focus)
        dec = self.decide(ctx, rng, cands, explain=want_explain)
        self._maybe_prune(sim)
        if dec.action_id is None:
            self.source_counts["legacy"] += 1
            return None
        self.source_counts["engine"] += 1
        if dec.explanation is not None:
            q = self._explain.get(actor.cid)
            if q is None:
                q = self._explain[actor.cid] = deque(maxlen=int(self.cfg.get("engine.explain_keep", 6)))
            q.append(dec.explanation)
        target = chars.get(dec.target) if dec.target is not None else None
        return EngineChoice(dec.action_id, target)

    def _maybe_prune(self, sim):
        every = int(self.cfg.get("simdao.prune_every", 2000))
        if every > 0 and self.stats.get("decisions", 0) % every == 0:
            alive = sim.alive_cids
            for cid in [c for c in self.minds if c not in alive]:
                self.minds.pop(cid, None)
                self._explain.pop(cid, None)

    # ================================================================ Feedback (event bus)
    def on_event(self, ev, sim):
        if not self.enabled or ev.actor is None or ev.actor < 0:
            return
        cfg = self.cfg
        spec = self.registry.get(ev.kind)
        actor = sim.cast[ev.actor] if ev.actor < len(sim.cast) else None
        target = sim.cast[ev.target] if ev.target is not None and 0 <= ev.target < len(sim.cast) else None
        good = set(cfg.get("simdao.outcomes.good", []) or [])
        bad = set(cfg.get("simdao.outcomes.bad", []) or [])
        near = set(cfg.get("simdao.outcomes.near_death", []) or [])
        winner = (ev.deltas or {}).get("winner") if isinstance(ev.deltas, dict) else None

        # ---- ผู้ลงมือ ----
        mind = self.minds.get(ev.actor)
        if mind is not None and actor is not None and spec is not None:
            if winner is not None:
                success = winner == ev.actor
            elif ev.outcome in good:
                success = True
            elif ev.outcome in bad:
                success = False
            else:
                success = None
            loser_is_me = winner is not None and winner != ev.actor
            died = not actor.alive
            near_death = ev.outcome in near and (loser_is_me or winner is None)
            damage = cfg.get("simdao.combat_damage_loser", 0.6) if (loser_is_me or near_death) else 0.0
            revealed, self_pw, rel = {}, None, {}
            if spec.is_combat and target is not None:
                revealed[target.cid] = self._power(sim, target)       # ปะทะกันจริง = เห็นเต็มตา
                self_pw = self._power(sim, actor)
            if ev.kind == "ล่าอสูร" and success is not None:
                k = cfg.get("simdao.beast_learning", 0.5)
                pw = self._power(sim, actor) * math.exp(-k if success else k)
                mind.beliefs.observe(f"beast:{actor.place}", pw, "combat", sim.day, cfg)
            if target is not None and spec.social == "bond" and success is not False:
                step = cfg.get("relationship.feedback_step", 0.15)
                rel[target.cid] = {"trust": step, "affection": step * 0.5}
            self.feedback(mind, sim.day, ev.kind, target=ev.target,
                          target_kind="npc" if target is None or not target.is_beast else "beast",
                          location=actor.place, success=success, damage=damage,
                          near_death=near_death, died=died, revealed_power=revealed,
                          self_power=self_pw, relation_changes=rel, note=ev.text[:60])
        # ---- ข่าวลือ → belief (source=rumor ความมั่นใจต่ำ อาจผิดได้) ----
        if ev.kind == "ได้ยินข่าวลือ" and mind is not None and actor is not None:
            for lead in (actor.rumor_leads or [])[-1:]:
                mind.beliefs.hear(f"lead:{lead.get('kind')}:{lead.get('subject')}", True, sim.day, cfg)

        # ---- ผู้ถูกกระทำ: จำว่าใครทำอะไรกับตน + ถูกปลุกให้คิดใหม่ ----
        if target is not None and target.alive and ev.kind in (cfg.get("simdao.wake_kinds", []) or []):
            tmind = self.mind(target.cid, target.name)
            tmind.woken = True
            if winner is not None and winner == target.cid:
                valence = 0.3                 # ถูกท้าแต่ป้องกันตัวได้
            else:
                valence = -0.8 if ev.outcome in near else -0.5
            tmind.memory.remember(f"entity:{ev.actor}", valence, sim.day, cfg,
                                  intensity=0.9 if ev.outcome in near else 0.5,
                                  importance=0.8, note=f"{ev.kind}: {ev.text[:50]}")
            if actor is not None and (spec is None or spec.is_combat):
                tmind.beliefs.observe(f"power:{ev.actor}", self._power(sim, actor), "combat", sim.day, cfg)
            step = cfg.get("relationship.feedback_step", 0.15)
            if valence < 0:
                tmind.relations.adjust(ev.actor, cfg, hatred=step, fear=step * (1.5 if winner == ev.actor else 0.5),
                                       trust=-step)

    # ================================================================ ดีบัก
    def explanations(self, cid):
        return list(self._explain.get(cid, ()))

    def explain_text(self, cid, n=1):
        ex = self.explanations(cid)[-n:]
        return "\n\n".join(e.format_text() for e in ex) if ex else ""

    def summary(self):
        d = max(1, self.stats.get("decisions", 0))
        return {"decisions": self.stats.get("decisions", 0),
                "avg_options": round(self.stats.get("options", 0) / d, 2),
                "goal_evals": self.stats.get("goal_evals", 0), "plans": self.stats.get("plans", 0),
                "lod": dict(self.lod_counts), "source": dict(self.source_counts),
                "minds": len(self.minds)}
