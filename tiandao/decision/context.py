# -*- coding: utf-8 -*-
"""Decision Context — ทุกอย่างที่ตัวละคร "มี" ตอนต้องตัดสินใจหนึ่งครั้ง

แยกเป็นสองชนิด:
  · AgentMind  — สถานะถาวรของจิตใจ (belief · memory · relationship deltas · goal · plan) ถูกเซฟไปกับโลก
  · DecisionContext — ภาพรวมชั่วคราว ณ จังหวะตัดสินใจ สร้างใหม่ทุกครั้งจาก AgentMind + perception

ทุกค่าใน DecisionContext เป็นมุมมองของตัวละคร: entity ที่ "เห็น" (ไม่ใช่ทุกตัวในโลก) และพลังของ
entity อ่านผ่าน BeliefStore เท่านั้น — Decision Engine ไม่มีทางเข้าถึง WorldState จริง
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .beliefs import BeliefStore
from .memory import MemoryStore
from .relationships import Relation, RelationshipBook


@dataclass
class AgentState:
    """Character State ที่ตัวละครรู้เกี่ยวกับตัวเอง (ค่าดิบ — normalize ใน needs/risk)"""
    hp: float = 100.0
    hp_max: float = 100.0
    stamina: float = 100.0
    stamina_max: float = 100.0
    hunger: float = 0.0          # 0..1
    thirst: float = 0.0          # 0..1
    fatigue: float = 0.0         # 0..1
    level: float = 0.0           # cultivation / level (ใช้คำนวณช่องว่างการมองพลัง)
    power: float = 1.0           # พลังของตัวเองตามจริง — ตัวละครเห็นผ่าน belief "power:self"
    injuries: float = 0.0        # 0..1
    inventory: Dict[str, float] = field(default_factory=dict)
    money: float = 0.0
    location: Any = None
    horizon: float = 0.0         # เวลาชีวิตที่คาดว่าเหลือ (หน่วยเวลาโลก) — 0 = ไม่รู้ ใช้ time_scale

    @property
    def hp_ratio(self):
        return 0.0 if self.hp_max <= 0 else max(0.0, min(1.0, self.hp / self.hp_max))

    @property
    def stamina_ratio(self):
        return 0.0 if self.stamina_max <= 0 else max(0.0, min(1.0, self.stamina / self.stamina_max))


@dataclass
class PerceivedEntity:
    """entity ที่ตัวละคร "เห็น/รู้ว่าอยู่ใกล้" — ไม่มี field พลังจริง (อยู่ใน BeliefStore)"""
    eid: Any
    kind: str = "npc"                    # npc / beast / ...
    name: str = ""
    tags: Tuple[str, ...] = ()
    hostile: bool = False                # เป็นศัตรู/คุกคามเรา (ตามที่เชื่อ)
    threatens: Tuple[Any, ...] = ()      # กำลังคุกคามใคร (eid) — ใช้หา "เพื่อนตกอยู่ในอันตราย"
    in_danger: float = 0.0               # 0..1 ตามที่เราเชื่อ
    has_loot: bool = False
    level: float = 0.0                   # ระดับที่มองเห็นจากภายนอก (ขั้น/ชั้น)
    relation: Relation = field(default_factory=Relation)


@dataclass
class Environment:
    danger: float = 0.0                  # 0..1
    weather: str = "clear"
    bad_weather: float = 0.0             # 0..1
    time_of_day: str = "day"
    night: float = 0.0                   # 0/1
    terrain: str = "plain"
    allies_nearby: int = 0
    escape_routes: int = 1
    resources: Dict[str, float] = field(default_factory=dict)   # 0..1 ต่อชนิด
    crowd: float = 0.0                   # 0..1
    social: str = ""                     # บรรยากาศสังคม เช่น "market", "sect", "battle"
    features: Dict[str, float] = field(default_factory=dict)    # ฟีเจอร์เพิ่มเติมจาก adapter

    def feature(self, name):
        if name in self.features:
            return self.features[name]
        if name.startswith("resource:"):
            return self.resources.get(name.split(":", 1)[1], 0.0)
        v = getattr(self, name, 0.0)
        return float(v) if isinstance(v, (int, float)) else 0.0


@dataclass
class GoalChoice:
    goal_id: str = ""
    score: float = 0.0
    ranking: List[Tuple[str, float]] = field(default_factory=list)   # [(goal, score)] สูง→ต่ำ
    reasons: Dict[str, float] = field(default_factory=dict)


@dataclass
class AgentMind:
    """จิตใจถาวรของตัวละครหนึ่งตัว — pickle ไปกับโลก"""
    agent_id: Any
    name: str = ""
    beliefs: BeliefStore = field(default_factory=BeliefStore)
    memory: MemoryStore = field(default_factory=MemoryStore)
    relations: RelationshipBook = field(default_factory=RelationshipBook)
    goal: str = ""
    goal_day: float = -1e18
    plan: List[str] = field(default_factory=list)
    plan_goal: str = ""
    plan_day: float = -1e18
    last: Optional[dict] = None          # การตัดสินใจล่าสุด (เก็บ prediction ไว้เทียบผลจริง)
    decisions: int = 0
    surprises: float = 0.0
    woken: bool = False                  # มีเหตุการณ์ปลุก (ถูกโจมตี) → ประเมินเป้าหมายใหม่ทันที
    habit: Dict[str, Tuple[float, float]] = field(default_factory=dict)   # action -> (ระดับ, วันที่)

    # ---- Habituation (ความเบื่อ/ชินชา): ทำซ้ำแล้วแรงจูงใจลด แบบ leaky integrator
    #   h(t) = h(t₀)·e^(−Δt/τ) + 1 ทุกครั้งที่ทำ      penalty = 1 − e^(−h/h₀)
    def habit_level(self, action, now, cfg):
        lv = self.habit.get(action)
        if lv is None:
            return 0.0
        tau = max(1e-6, cfg.get("habituation.tau", 60.0))
        import math
        return lv[0] * math.exp(-max(0.0, now - lv[1]) / tau)

    def habituate(self, action, now, cfg):
        self.habit[action] = (self.habit_level(action, now, cfg) + 1.0, now)
        cap = int(cfg.get("habituation.max_entries", 24))
        if len(self.habit) > cap:
            for k in sorted(self.habit, key=lambda a: self.habit[a][1])[: len(self.habit) - cap]:
                self.habit.pop(k, None)


@dataclass
class DecisionContext:
    agent_id: Any
    name: str
    now: float
    state: AgentState
    needs: Dict[str, float]
    traits: Dict[str, float]
    mind: AgentMind
    env: Environment = field(default_factory=Environment)
    entities: List[PerceivedEntity] = field(default_factory=list)
    legacy: Dict[str, float] = field(default_factory=dict)    # action_id -> น้ำหนักจากระบบเดิม
    profile: str = "default"
    lod: int = 0
    facts: Dict[str, bool] = field(default_factory=dict)      # ข้อเท็จจริงเชิงสัญลักษณ์ (จาก belief) สำหรับ GOAP
    goal: Optional[GoalChoice] = None
    plan: List[str] = field(default_factory=list)
    extra: Dict[str, Any] = field(default_factory=dict)

    @property
    def beliefs(self):
        return self.mind.beliefs

    @property
    def memory(self):
        return self.mind.memory

    def entity(self, eid):
        for e in self.entities:
            if e.eid == eid:
                return e
        return None

    def allies_in_danger(self):
        return [e for e in self.entities if e.relation.affection > 0 and e.in_danger > 0]
