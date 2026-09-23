# -*- coding: utf-8 -*-
"""AI Scheduler + AI Level of Detail

อย่าให้ NPC ทุกตัวคิดทุกอย่างทุก frame:

    LOD 0  Full decision        — การต่อสู้ / ศัตรูอยู่ตรงหน้า / ตัวละครที่ถูกจับตา
    LOD 1  Reduced candidates   — มีคนที่เกี่ยวข้องกับเรารอบตัว (ตัด action น้ำหนักต่ำ, เป้าน้อยลง)
    LOD 2  Simplified utility   — อยู่ลำพังหรือท่ามกลางคนแปลกหน้า (ไม่ประเมินเป้า/belief/memory/social,
                                  ไม่ replan)
    LOD 3  Statistical          — ไม่มีจิตนึกคิด / ชาวบ้านไกลตา → ให้ระบบเดิมสุ่มตามน้ำหนัก

AIScheduler ใช้ได้ทั้งโลก real-time (หน่วยวินาที: combat 0.2–1 s, active 1–5 s, distant 10–60 s,
offscreen = event-driven) และโลกแบบ event heap ของ Sim Dao (หน่วยวัน: ช่วงที่ต้องประเมินเป้าหมายใหม่)
"""
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from . import rng as DRNG

LOD_FULL, LOD_REDUCED, LOD_SIMPLE, LOD_STATISTICAL = 0, 1, 2, 3
TIER_OF_LOD = {0: "combat", 1: "active", 2: "distant", 3: "offscreen"}


@dataclass
class ScheduleEntry:
    next_time: Optional[float]
    tier: str
    woken: bool = False


@dataclass
class AIScheduler:
    """ตัดสินว่า "ถึงเวลาคิดใหม่หรือยัง" ต่อ agent

    realtime: due() ใช้ช่วง [min,max] ของ tier + jitter ที่ derive จาก seed (reproducible)
    wake(agent) = เหตุการณ์ปลุก (ถูกโจมตี/เห็นศัตรู) → คิดใหม่ทันทีรอบถัดไป ไม่รอรอบ
    """
    intervals: Dict[str, list] = field(default_factory=dict)
    seed: int = 0
    entries: Dict[Any, ScheduleEntry] = field(default_factory=dict)

    @classmethod
    def from_config(cls, cfg, seed=0):
        return cls(intervals=dict(cfg.get("scheduler.realtime", {}) or {}), seed=seed)

    def interval(self, agent_id, tier, now):
        lo, hi = (self.intervals.get(tier) or [None, None])
        if lo is None:
            return None                           # event-driven เท่านั้น
        u = DRNG.uniform(self.seed, str(agent_id), int(now * 1000))
        return lo + (hi - lo) * u

    def due(self, agent_id, now, tier):
        e = self.entries.get(agent_id)
        if e is None or e.woken or e.tier != tier:
            return True
        return e.next_time is not None and now >= e.next_time

    def done(self, agent_id, now, tier):
        gap = self.interval(agent_id, tier, now)
        self.entries[agent_id] = ScheduleEntry(None if gap is None else now + gap, tier)

    def wake(self, agent_id):
        e = self.entries.get(agent_id)
        if e is not None:
            e.woken = True

    def tick(self, agents, now, tier_of):
        """โลก real-time: คืนรายชื่อ agent ที่ถึงคิวคิด ณ เวลานี้ (แล้วบันทึกว่าคิดแล้ว)"""
        out = []
        for a in agents:
            tier = tier_of(a)
            if self.due(a, now, tier):
                out.append(a)
                self.done(a, now, tier)
        return out


def goal_recheck_due(cfg, lod, last_day, now, woken=False):
    """Sim Dao: ประเมินเป้าหมายใหม่เมื่อถึงรอบของ LOD นั้น หรือถูกปลุกด้วยเหตุการณ์"""
    if woken:
        return True
    table = cfg.get("scheduler.simdao_goal_recheck_days", {}) or {}
    gap = table.get(lod, table.get(str(lod), 0))
    return now - last_day >= gap
