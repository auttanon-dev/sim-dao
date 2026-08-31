# -*- coding: utf-8 -*-
"""Phase G — คิวงาน LLM แบบไม่บล็อก sim loop (ต่อยอด Layer 3 — Phase 5)

เดิม `BrainManager.on_event()` เรียก Ollama แบบ blocking ทันทีที่เจอ event น่าจดจำ (พิสูจน์แล้วว่า
500 เหตุการณ์ธรรมดา + `--llm` ใช้เวลา 8 นาที 35 วินาที — ดู CULTIVATOR_BRAIN_STATUS.md) ตอนนี้
`on_event()` แค่ enqueue งานไว้ (แทบไม่เสียเวลา) แล้วให้ `run.py`/`daemon.py` เรียก `drain_llm_queue()`
เป็นช่วงๆ แยกจากการเดิน `sim.step()` เอง

นี่**ไม่ใช่** async แบบ multi-thread จริง (เลี่ยง race condition กับ `sim.brain_manager`/
`CharacterBrain` ที่ยังไม่ได้ออกแบบให้ thread-safe โดยตั้งใจ — เพิ่มความซับซ้อน/ความเสี่ยงเกินความจำเป็น)
แต่เป็น **"deferred batch"**: sim เดินเต็มสปีดได้ก่อน (enqueue ไม่ทำ HTTP call เลย) แล้วค่อยประมวลผล
คิว LLM เป็นช่วงที่ควบคุมได้ (budget ต่อครั้ง) — ทำให้ throughput ของซิมไม่ขึ้นกับความเร็ว Ollama
ระหว่างเดินอีกต่อไป ค่าใช้จ่ายจริงถูกเลื่อนไปเกิดตอน drain ซึ่งผู้เรียกควบคุมจังหวะได้เอง
"""
from dataclasses import dataclass
from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from ..models import Event


@dataclass
class LLMJob:
    cid: int
    event: "Event"


class LLMJobQueue:
    """FIFO ธรรมดา — เป็น plain data (list ของ dataclass) จึง pickle ได้ฟรีเหมือนส่วนอื่นของ Sim"""

    def __init__(self) -> None:
        self._jobs: List[LLMJob] = []

    def enqueue(self, cid: int, event: "Event") -> None:
        self._jobs.append(LLMJob(cid=cid, event=event))

    def __len__(self) -> int:
        return len(self._jobs)

    def pop_batch(self, budget: int) -> List[LLMJob]:
        """ดึงงานออกจากคิวสูงสุด budget อัน (budget<=0 = เอาทั้งหมด) — งานที่เหลือยังอยู่ในคิวรอรอบถัดไป"""
        if budget <= 0 or budget >= len(self._jobs):
            batch, self._jobs = self._jobs, []
        else:
            batch, self._jobs = self._jobs[:budget], self._jobs[budget:]
        return batch
