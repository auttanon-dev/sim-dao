# -*- coding: utf-8 -*-
"""Phase 6 — History Generator: ปลายทางที่ทุก Layer ก่อนหน้านี้ป้อนวัตถุดิบมาให้

ต่างจาก Layer 3 (tiandao/ai/llm_agent.py) ที่ trigger สดระหว่างซิมเดิน (บทพูด/ความคิดสั้นๆ ต่อ event
หนึ่งเรื่อง, ปิดไว้เป็นค่าเริ่มต้นเพราะ blocking) — History Generator เป็นเครื่องมือที่เรียกแยกทีหลัง
บนโลกที่เซฟไว้แล้ว (ดู generate_episode.py) ไม่ผูกกับ config_ai.LLM_ENABLED เพราะตอนนี้ไม่มีซิมกำลัง
เดินสดให้ช้าลง

Reuse ของเดิมทั้งหมด — ไม่สร้างกลไกเก็บประวัติคู่ขนานขึ้นมาใหม่:
  - tiandao/story.py:biography() ให้ "โครงชีวประวัติ" (สายเลือด/ขั้น/นิสัย/วิชา/สมบัติ) อยู่แล้ว
  - CharacterBrain.is_notable() (Phase 1) คัดฉากเด่นจาก sim.log เต็ม — มาตรฐานเดียวกับที่ Layer 3
    ใช้ตัดสินใจเรียก LLM ระหว่างซิมเดิน
  - CharacterBrain.narrative_moments (Phase 5) ถ้าเคยรัน --llm ไว้ก่อนหน้า บทพูด/ความคิดที่มีอยู่แล้ว
    ถูกใช้เป็น anchor ของฉากนั้นๆ แทนที่จะให้ LLM แต่งใหม่ทั้งหมด
"""
import logging
from typing import TYPE_CHECKING, List, Optional, Tuple

from . import llm_agent as LLM
from .brain import CharacterBrain

if TYPE_CHECKING:
    from ..models import Character, Event
    from ..sim import Sim

logger = logging.getLogger(__name__)


def select_scenes(ch: "Character", sim: "Sim", brain: CharacterBrain, max_scenes: int,
                   event_log_path: Optional[str] = None) -> List["Event"]:
    """คัดฉากเด่นจากประวัติเต็มของตัวละคร (ไม่ใช่แค่ episodic 30 อันล่าสุดที่เป็น working memory ของ
    Layer 1-3) กระจายให้ครอบคลุมทั้งชีวิต ไม่ใช่แค่ท้ายๆ

    event_log_path: ถ้า daemon.py เคย flush+trim log แล้ว (Phase G — ดู tiandao/event_log.py) ต้อง
    ส่งมาด้วยถึงจะได้ประวัติเต็ม ไม่งั้นเห็นแค่เหตุการณ์ล่าสุดที่เหลือใน sim.log"""
    from .. import event_log as EL
    full_log = EL.full_log(sim, event_log_path)
    candidates = [ev for ev in full_log
                  if (ev.actor == ch.cid or ev.target == ch.cid) and brain.is_notable(ev)]
    if len(candidates) <= max_scenes:
        return candidates
    step = len(candidates) / max_scenes
    return [candidates[int(i * step)] for i in range(max_scenes)]


def _moment_for(brain: CharacterBrain, ev: "Event") -> Optional[LLM.NarrativeMoment]:
    return next((m for m in brain.narrative_moments if m.day == ev.day and m.kind == ev.kind), None)


def build_episode_prompt(ch: "Character", sim: "Sim", brain: CharacterBrain,
                          scenes: List["Event"]) -> Tuple[str, str]:
    """ประกอบ prompt จากโครงชีวประวัติ (reuse story.biography) + ฉากเด่นที่คัดมา — คืน
    (system_prompt, user_prompt)"""
    from .. import story
    profile = story.biography(ch, sim).split("\n\n", 1)[0]

    lines: List[str] = []
    prev_day = None
    for i, ev in enumerate(scenes, 1):
        gap = "" if prev_day is None else f"(ผ่านไป {story.fmt_gap(ev.day - prev_day)}) "
        prev_day = ev.day
        line = f"ฉากที่ {i} — {gap}วัน {ev.day}: {ev.text}"
        moment = _moment_for(brain, ev)
        if moment:
            if moment.dialogue:
                line += f'\n  บทพูดที่เคยพูดไว้: "{moment.dialogue}"'
            if moment.thought:
                line += f"\n  ความคิดในใจตอนนั้น: {moment.thought}"
        lines.append(line)
    scenes_text = "\n".join(lines) or "- ยังไม่มีเหตุการณ์เด่นให้เล่า"
    n = len(scenes)

    system = (
        "คุณคือนักเขียนนิยายกำลังภายในแนวเซียนหรูสไตล์จีน กำลังเขียนตอนหนึ่งจากประวัติตัวละครที่ให้มา\n"
        "กฎเหล็กที่ต้องทำตามเป๊ะ ห้ามผิดแม้แต่ข้อเดียว:\n"
        f"1. ต้องมีหัวข้อช่วงย่อยทั้งหมด {n} ช่วงพอดี ห้ามมากหรือน้อยกว่านี้ ห้ามรวมสองฉากเข้าด้วยกัน "
        "ห้ามข้ามฉากไหนไปเฉยๆ\n"
        "2. ช่วงย่อยที่ N ต้องบรรยาย \"ฉากที่ N\" ที่ให้มาโดยตรงเท่านั้น ตามลำดับ 1,2,3,... เป๊ะๆ "
        "ห้ามสลับลำดับ ห้ามแต่งเหตุการณ์ใหม่ที่ไม่มีอยู่ในฉากที่ N นั้น\n"
        "3. ในเนื้อความของแต่ละช่วง ต้องเอ่ยถึงรายละเอียดที่ปรากฏจริงในข้อความของฉากนั้น (เช่น ชื่อคน/"
        "สัตว์อสูร/สถานที่/ผลลัพธ์ที่ระบุไว้) อย่างน้อยหนึ่งอย่างเสมอ ห้ามเขียนลอยๆ แบบทั่วไปที่ใช้กับ"
        "ฉากไหนก็ได้\n"
        "4. ห้ามใช้ประโยคหรือมุขซ้ำเดิมข้ามช่วง แต่ละช่วงต้องมีน้ำเสียง/อารมณ์ที่ต่างกันตามเหตุการณ์จริง\n"
        "รูปแบบการจัดหน้า:\n"
        "- หัวเรื่องตอน: # ตอนที่ ... <ชื่อตอนที่ตั้งเอง>\n"
        "- บรรทัดเปิดเรื่อง: **[ฉาก/สถานที่]:** ... และ **[สภาพแวดล้อม]:** ...\n"
        "- หัวข้อช่วงย่อย: ### [ช่วงที่ N: <ชื่อช่วงที่สื่อถึงฉากที่ N โดยเฉพาะ>]\n"
        "- บทพูดตัวละครขึ้นต้นด้วย **ชื่อตัวละคร [ท่าที/สีหน้า]:** แล้วตามด้วยคำพูดในเครื่องหมายคำพูด"
    )
    user = (
        f"[ข้อมูลตัวละคร]\n{profile}\n\n"
        f"[ฉากทั้งหมด {n} ฉากตามลำดับเวลา — นี่คือแกนเรื่องทั้งหมดที่มี ห้ามข้าม ห้ามสลับ ห้ามแต่งเพิ่ม]\n"
        f"{scenes_text}\n\n"
        f"[งาน] เขียนตอนหนึ่งของ {ch.name} จากฉากทั้ง {n} ฉากข้างต้น ให้มีช่วงย่อยครบ {n} ช่วง "
        "ช่วงละหนึ่งฉากตามลำดับ ตามกฎเหล็กทั้ง 4 ข้อด้านบน"
    )
    return system, user


def _fallback_episode(ch: "Character", scenes: List["Event"]) -> str:
    """ใช้เมื่อเรียก Ollama ไม่สำเร็จ — คืนโครงเรื่องดิบแทนร้อยแก้ว ดีกว่าไม่คืนอะไรเลย"""
    lines = [f"# {ch.name} — บันทึกเหตุการณ์เด่น (เรียก LLM ไม่สำเร็จ นี่คือโครงดิบแทนร้อยแก้ว)"]
    for ev in scenes:
        lines.append(f"- วัน {ev.day}: {ev.text}")
    return "\n".join(lines)


def generate_episode(sim: "Sim", cid: int, max_scenes: Optional[int] = None,
                      agent: Optional[LLM.OllamaAgent] = None,
                      event_log_path: Optional[str] = None) -> str:
    """สร้างตอนนิยายหนึ่งตอนจากประวัติของตัวละคร cid — คืนสตริงเดียว (เขียนไฟล์เองด้านนอกฟังก์ชันนี้)"""
    from . import config_ai as ACFG
    max_scenes = max_scenes or ACFG.HISTORY_MAX_SCENES

    ch = next((c for c in sim.cast if c.cid == cid), None)
    if ch is None:
        raise ValueError(f"ไม่พบตัวละคร cid={cid} ในซิมนี้")

    brain = sim.brain_manager.get_or_create(cid)
    scenes = select_scenes(ch, sim, brain, max_scenes, event_log_path)
    if not scenes:
        logger.warning("history: cid=%s ไม่มีเหตุการณ์เด่นพอจะเล่าเรื่อง (ลองตัวละครอื่น)", cid)
        return _fallback_episode(ch, scenes)

    system, user = build_episode_prompt(ch, sim, brain, scenes)
    agent = agent or LLM.OllamaAgent(timeout=ACFG.HISTORY_TIMEOUT)
    text = agent.complete(system, user, timeout=ACFG.HISTORY_TIMEOUT)
    if text is None:
        logger.warning("history: เรียก Ollama ไม่สำเร็จสำหรับ cid=%s — คืนโครงเรื่องดิบแทน", cid)
        return _fallback_episode(ch, scenes)
    return text
