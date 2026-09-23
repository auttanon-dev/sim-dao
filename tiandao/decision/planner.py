# -*- coding: utf-8 -*-
"""GOAP Planner — "ฉันจะทำ Goal นี้ให้สำเร็จอย่างไร?"

A* บนสถานะเชิงสัญลักษณ์ (dict fact -> bool) ที่มาจาก **ความเชื่อ** ของตัวละคร ไม่ใช่ WorldState
action แต่ละตัวประกาศ goap: {pre: {...}, eff: {...}, cost: n} ไว้ใน config

    g(n) = Σ (cost + risk_cost × attitude × risk_estimate)      h(n) = จำนวน fact ที่ยังไม่ตรง desired
    attitude = max(min, 1 + k·(caution − bravery))  — ตัวคูณเดียวกับ PersonalityRiskModifier ใน scoring
    (h admissible เพราะทุก action มี cost ≥ 1 และแก้ fact ได้หลายตัวพร้อมกันเท่านั้นที่ทำให้ h ประเมินเกิน —
     จึงใช้เป็น greedy-A* ที่เร็วและพอสำหรับแผนสั้น ≤ max_depth ก้าว)

ก้าวแรกของแผนต้องเป็น action ที่ทำได้ตอนนี้ (available) ถ้าผู้เรียกระบุ — แผนที่ก้าวแรกทำไม่ได้
ไม่มีประโยชน์ต่อการตัดสินใจรอบนี้ · replan ทุกครั้งที่เป้าหมายเปลี่ยน / ก้าวแรกทำไม่ได้แล้ว / แผนเก่าเกิน
"""
import heapq
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class Plan:
    goal: str
    steps: List[str] = field(default_factory=list)
    cost: float = 0.0
    expansions: int = 0
    found: bool = False


def _satisfied(state, desired):
    return all(bool(state.get(k, False)) == bool(v) for k, v in desired.items())


def _h(state, desired):
    return sum(1 for k, v in desired.items() if bool(state.get(k, False)) != bool(v))


def _freeze(state):
    return tuple(sorted((k, bool(v)) for k, v in state.items()))


class GoapPlanner:
    def __init__(self, cfg, registry):
        self.cfg = cfg
        self.actions = [s for s in registry.specs.values() if s.goap.get("eff")]

    def risk_estimate(self, spec):
        rk = spec.risk or {}
        return rk.get("injury", 0.0) + rk.get("death", 0.0) * self.cfg.get("risk.death_weight", 3.0)

    def _relevant_actions(self, desired):
        """backward relevance closure (regression planning): fact ที่เกี่ยว = desired ∪ pre ของ action
        ที่ผลของมันแตะ fact ที่เกี่ยว — action ที่ไม่แตะ fact ที่เกี่ยวเลยไม่ถูกใช้ (กันแผนมีก้าว "ถ่วงเวลา"
        ที่ไม่ช่วยอะไร เช่น ค้าขายก่อนสะสมบุญ เพียงเพราะค้าขายทำได้ตอนนี้)"""
        need = {k: bool(v) for k, v in desired.items()}
        changed = True
        while changed:
            changed = False
            for spec in self.actions:
                eff = spec.goap.get("eff") or {}
                if any(k in need and need[k] == bool(v) for k, v in eff.items()):
                    for k, v in (spec.goap.get("pre") or {}).items():
                        if k not in need:
                            need[k] = bool(v)
                            changed = True
        return [s for s in self.actions
                if any(k in need and need[k] == bool(v) for k, v in (s.goap.get("eff") or {}).items())]

    def plan(self, goal_id, desired: Dict[str, bool], facts: Dict[str, bool],
             available: Optional[set] = None, risk_attitude: float = 1.0) -> Plan:
        out = Plan(goal=goal_id)
        if not desired:
            return out
        if _satisfied(facts, desired):
            out.found = True
            return out
        max_depth = int(self.cfg.get("planner.max_depth", 5))
        max_exp = int(self.cfg.get("planner.max_expansions", 400))
        # risk-sensitive planning: คนกล้ามองต้นทุนความเสี่ยงของเส้นทางต่ำกว่าคนระวังตัว
        rc = self.cfg.get("planner.risk_cost", 2.0) * max(0.0, risk_attitude)
        relevant = self._relevant_actions(desired)
        start = dict(facts)
        counter = 0
        frontier = [(_h(start, desired), 0.0, counter, start, [])]
        best_g = {_freeze(start): 0.0}
        while frontier and out.expansions < max_exp:
            _f, g, _c, state, path = heapq.heappop(frontier)
            out.expansions += 1
            if _satisfied(state, desired):
                out.steps, out.cost, out.found = path, g, True
                return out
            if len(path) >= max_depth:
                continue
            for spec in relevant:
                if not path and available is not None and spec.id not in available:
                    continue
                pre = spec.goap.get("pre") or {}
                if any(bool(state.get(k, False)) != bool(v) for k, v in pre.items()):
                    continue
                eff = spec.goap.get("eff") or {}
                if all(bool(state.get(k, False)) == bool(v) for k, v in eff.items()):
                    continue          # ไม่เปลี่ยนอะไร
                nxt = dict(state)
                nxt.update({k: bool(v) for k, v in eff.items()})
                ng = g + float(spec.goap.get("cost", 1.0)) + rc * self.risk_estimate(spec)
                key = _freeze(nxt)
                if ng >= best_g.get(key, float("inf")):
                    continue
                best_g[key] = ng
                counter += 1
                heapq.heappush(frontier, (ng + _h(nxt, desired), ng, counter, nxt, path + [spec.id]))
        return out
