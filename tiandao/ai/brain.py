# -*- coding: utf-8 -*-
"""CharacterBrain — component ที่ผูกกับ Character ผ่าน cid เท่านั้น ไม่ใช่ field บน Character dataclass
(ตามกฎ ROLE.md: "หากมีคลาสเดิมอยู่แล้ว เช่น Character ให้ใช้ CharacterBrain เป็น Component ไม่แก้
Character ตรงๆ ถ้าไม่จำเป็น")

Phase 1: เก็บ episodic memory แบบมีเพดานต่อคนเท่านั้น ยังไม่มี Utility/GOAP/LLM จริง
(ดู tiandao/ai/config_ai.py สำหรับ NOTABLE_KINDS ที่ Phase 5 จะใช้เป็นตัวกระตุ้น LLM)

BrainManager แขวนอยู่บน Sim ตัวเดียว (sim.brain_manager) — pickle ได้ฟรีเพราะเป็นส่วนหนึ่งของ object
graph ของ Sim อยู่แล้ว (ดู tiandao/persist.py) ไม่ต้องแก้ persist.py เพิ่ม
"""
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Dict, List, Tuple

from . import config_ai as ACFG
from . import goap as GOAP
from . import llm_agent as LLM
from . import llm_queue as LLMQ
from . import memory as MEM
from . import utility as UT

if TYPE_CHECKING:
    from ..models import Character, Event
    from ..sim import Sim

logger = logging.getLogger(__name__)


@dataclass
class EpisodicMemory:
    """เหตุการณ์หนึ่งเรื่องที่ตัวละครจำไว้ — วัตถุดิบของ Layer 3 (Ollama) ใน Phase 5"""
    day: int
    kind: str
    outcome: str
    text: str


@dataclass
class CharacterBrain:
    cid: int
    episodic: List[EpisodicMemory] = field(default_factory=list)
    # Layer 1 — Utility AI (Phase 2): อัปเดตทุกครั้งที่ตัวละครนี้ต้องตัดสินใจ (ดู decide() ด้านล่าง)
    needs: Dict[str, float] = field(default_factory=dict)
    current_goal: str = ""
    goal_score: float = 0.0
    # Layer 2 — Hierarchical GOAP (Phase 3): method ล่าสุดที่ planner เลือกให้ goal ปัจจุบัน (debug/log)
    goap_method: str = ""
    # Memory System (Phase 4): Semantic (ต่อสถานที่) + Reputation (ต่อภูมิภาค)
    # Relationship ไม่เก็บในนี้ — อ่านจาก ch.rivals/ch.bonds ตรงๆ ผ่าน tiandao/ai/memory.py แทน
    semantic: Dict[int, MEM.PlaceFact] = field(default_factory=dict)
    reputation: Dict[str, Dict[str, int]] = field(default_factory=dict)
    # Layer 3 — Local LLM Agent (Phase 5): บทพูด/ความคิดที่ Ollama สร้างให้ ("Memory Update" ตาม ROLE.md)
    narrative_moments: List[LLM.NarrativeMoment] = field(default_factory=list)

    def __setstate__(self, state: dict) -> None:
        """save เก่าที่เซฟไว้ก่อนมี field ใหม่ (semantic/reputation/narrative_moments ฯลฯ) ยัง
        unpickle ได้ — เติมค่า default ให้ field ที่ยังไม่เคยมีตอนเซฟ (dataclass ไม่เรียก __init__
        ตอน unpickle เอง)"""
        self.__dict__.update(state)
        self.__dict__.setdefault("semantic", {})
        self.__dict__.setdefault("reputation", {})
        self.__dict__.setdefault("goap_method", "")
        self.__dict__.setdefault("needs", {})
        self.__dict__.setdefault("current_goal", "")
        self.__dict__.setdefault("goal_score", 0.0)
        self.__dict__.setdefault("narrative_moments", [])

    def remember_narrative(self, moment: LLM.NarrativeMoment) -> None:
        self.narrative_moments.append(moment)
        if len(self.narrative_moments) > ACFG.NARRATIVE_MOMENT_CAP:
            del self.narrative_moments[: len(self.narrative_moments) - ACFG.NARRATIVE_MOMENT_CAP]

    def remember(self, ev: "Event") -> None:
        self.episodic.append(EpisodicMemory(day=ev.day, kind=ev.kind, outcome=ev.outcome, text=ev.text))
        if len(self.episodic) > ACFG.EPISODIC_MEMORY_CAP:
            del self.episodic[: len(self.episodic) - ACFG.EPISODIC_MEMORY_CAP]

    def is_notable(self, ev: "Event") -> bool:
        """kind ที่เป็นดราม่า หรือ outcome ที่น่าจดจำในตัวเอง (ตาย) — แต่ต้องไม่ใช่ outcome กลุ่ม
        "สุดท้ายไม่มีอะไรเกิดขึ้น" (ดู ACFG.NON_EVENT_OUTCOMES) เพราะ kind ดราม่าจำนวนมากจบลงแบบ
        ไม่มีเนื้อเรื่อง เช่น "ค้นแดนลับ → ไม่พบ" / "ข้ามฟ้า → ยังไม่ถึง" ซึ่งไม่มีอะไรให้ Layer 3 เล่า"""
        if ev.outcome in ACFG.NON_EVENT_OUTCOMES:
            return False
        return ev.kind in ACFG.NOTABLE_KINDS or ev.outcome in ACFG.NOTABLE_OUTCOMES

    def observe_place(self, place_idx: int, ev: "Event") -> None:
        MEM.observe_place(self.semantic, place_idx, ev)

    def note_reputation(self, region: str, ev: "Event") -> None:
        MEM.update_reputation(self.reputation, region, ev)

    def relationships(self, ch: "Character", n: int = 5) -> List[Tuple[int, int]]:
        return MEM.top_relationships(ch, n)

    def update_utility(self, ch: "Character", sim: "Sim") -> Dict[str, float]:
        """คำนวณ Dual Utility (Survival/Ambition) ใหม่ทั้งหมดจาก state ปัจจุบันของ ch แล้วจำ Goal
        ที่ชนะไว้ (ใช้ต่อใน Phase 3 — GOAP) คืนค่า needs dict ให้ apply_utility() ใช้ boost น้ำหนัก"""
        self.needs = UT.compute_needs(ch, sim)
        self.current_goal, self.goal_score = UT.top_goal(self.needs)
        return self.needs


class BrainManager:
    """เก็บ CharacterBrain ของทุกตัวละครที่เคยมี event เกิดขึ้น — สร้างแบบ lazy ตอนต้องใช้ครั้งแรก"""

    def __init__(self) -> None:
        self.brains: Dict[int, CharacterBrain] = {}
        self._agent: "LLM.OllamaAgent | None" = None   # lazy — สร้างเฉพาะตอนต้องเรียกจริงครั้งแรก
        self.llm_queue = LLMQ.LLMJobQueue()            # Phase G — งาน LLM ที่รอ drain แบบไม่บล็อก sim

    def __setstate__(self, state: dict) -> None:
        """save เก่าที่เซฟไว้ก่อนมี _agent (ก่อน Phase 5) หรือ llm_queue (ก่อน Phase G) ยัง unpickle
        ได้ — เติมค่า default ให้ (BrainManager ไม่ใช่ dataclass แต่ pickle ก็ไม่เรียก __init__
        เหมือนกัน จึงต้องมี __setstate__ เองแบบเดียวกับ CharacterBrain)"""
        self.__dict__.update(state)
        self.__dict__.setdefault("_agent", None)
        self.__dict__.setdefault("llm_queue", LLMQ.LLMJobQueue())

    def get_or_create(self, cid: int) -> CharacterBrain:
        brain = self.brains.get(cid)
        if brain is None:
            brain = CharacterBrain(cid=cid)
            self.brains[cid] = brain
        return brain

    def decide(self, ch: "Character", sim: "Sim", weights: Dict[str, float]) -> Dict[str, float]:
        """Layer 1 — Utility AI ต่อยอด tiandao/intent.py:weigh() (Phase 2)

        เรียกจาก tiandao/sim.py ตรงจุดตัดสินใจของตัวละคร (แทนที่ IN.choose() เดิมด้วย
        IN.weigh() -> brain_manager.decide() -> IN.sample_weighted()) — ไม่แก้ตาราง weigh() เดิม
        เลย แค่ boost น้ำหนักที่คำนวณมาแล้วให้เอียงไปทาง Need ที่ชนะ"""
        brain = self.get_or_create(ch.cid)
        needs = brain.update_utility(ch, sim)
        weights = UT.apply_utility(weights, needs)
        # Layer 2 GOAP: ตอนนี้ decompose เฉพาะ Breakthrough (ดู tiandao/ai/goap.py ว่าทำไม) —
        # Need อื่นหยุดอยู่แค่ Layer 1 boost ด้านบน
        brain.goap_method = ""
        if brain.current_goal == "Breakthrough":
            brain.goap_method = GOAP.plan_breakthrough(ch, sim, weights) or "Ready"
        return weights

    def on_event(self, ev: "Event", sim: "Sim") -> None:
        """Subscriber ของ EventBus — เรียกหลังทุก event ถูก log แล้ว"""
        if ev.actor is None:
            return
        brain = self.get_or_create(ev.actor)
        brain.remember(ev)

        actor_ch = sim.cast[ev.actor] if 0 <= ev.actor < len(sim.cast) else None
        if actor_ch is not None:
            if actor_ch.place is not None and actor_ch.place >= 0:
                brain.observe_place(actor_ch.place, ev)
            region = sim.world(actor_ch.world_id).name
            brain.note_reputation(region, ev)

        if not brain.is_notable(ev):
            return

        if not ACFG.LLM_ENABLED or actor_ch is None:
            logger.debug("brain: cid=%s เจอเหตุการณ์น่าจดจำ kind=%s outcome=%s (LLM ปิดอยู่ — "
                         "เปิดด้วย --llm)", ev.actor, ev.kind, ev.outcome)
            return

        # Layer 3 — Local LLM Agent (Phase 5) + Phase G: แค่ enqueue ไม่เรียก Ollama ตรงนี้เลย
        # (ของเดิมเรียก blocking ตรงนี้ทันที ทำให้ sim loop ช้าลงมหาศาลตามที่วัดไว้แล้ว) ผู้เรียก
        # (run.py/daemon.py) ต้องเรียก self.drain_llm_queue(sim, budget) เองเป็นช่วงๆ ถึงจะมีผล
        self.llm_queue.enqueue(ev.actor, ev)

    def drain_llm_queue(self, sim: "Sim", budget: int = 0) -> int:
        """ประมวลผลงาน LLM ที่ค้างอยู่ในคิวสูงสุด budget อัน (<=0 = ทั้งหมด) — เรียก Ollama จริงตรงนี้
        (ยังเป็น blocking call เหมือนเดิม แค่ **แยกจากลูปหลักของ sim.step() แล้ว** เรียกตอนไหนก็ได้ที่
        ผู้ใช้สะดวก เช่น หลัง sim.run() แต่ละก้อนใน daemon.py) คืนจำนวนงานที่ประมวลผลจริง"""
        batch = self.llm_queue.pop_batch(budget)
        if not batch:
            return 0
        if self._agent is None:
            self._agent = LLM.OllamaAgent()
        processed = 0
        for job in batch:
            ch = sim.cast[job.cid] if 0 <= job.cid < len(sim.cast) else None
            if ch is None:
                continue
            brain = self.get_or_create(job.cid)
            system, user = LLM.build_prompt(ch, brain, sim, job.event)
            result = self._agent.chat(system, user)
            if result is not None:
                brain.remember_narrative(LLM.NarrativeMoment(
                    day=job.event.day, kind=job.event.kind,
                    dialogue=result["dialogue"], thought=result["thought"]))
            processed += 1
        return processed
