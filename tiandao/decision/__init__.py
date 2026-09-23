# -*- coding: utf-8 -*-
"""Decision Engine (Hybrid) — Utility AI + Softmax + Belief + Memory + Personality + Social
+ Risk/Cost + Goal Selection + GOAP + Feedback Loop + Explanation + AI LOD/Scheduler

    from tiandao import decision as DE
    DE.attach(sim)                   # เปิดใช้กับ Sim Dao (ปิดเป็นค่าเริ่มต้น — ดู simdao.py)
    print(sim.decision_engine.explain_text(cid))

แกนกลาง (engine.py, scoring.py, ...) ไม่ผูกกับเอนจินโลก — simdao.py คือ adapter ตัวเดียว
ค่าคงที่ทั้งหมดอยู่ใน tiandao/decision/config/*.yaml
"""
from .config import DecisionConfig, load as load_config
from .context import AgentMind, AgentState, DecisionContext, Environment, PerceivedEntity
from .engine import Decision, DecisionEngine
from .relationships import Relation


def attach(sim, cfg=None, mode=None, focus=(), **kw):
    """ผูก Decision Engine เข้ากับ Sim ที่มีอยู่ (ใช้ได้กับ save เก่า) — คืน SimDecisionEngine"""
    from .simdao import SimDecisionEngine
    eng = SimDecisionEngine(cfg=cfg, mode=mode, focus=focus, **kw)
    eng.bind(sim)
    return eng


def detach(sim):
    from .simdao import unbind
    unbind(sim)


__all__ = ["DecisionEngine", "Decision", "DecisionConfig", "load_config", "AgentMind", "AgentState",
           "DecisionContext", "Environment", "PerceivedEntity", "Relation", "attach", "detach"]
