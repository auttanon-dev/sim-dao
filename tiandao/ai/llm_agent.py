# -*- coding: utf-8 -*-
"""Layer 3 — Local LLM Agent (Phase 5): ใช้ Ollama เรียกเฉพาะตอน event "น่าจดจำ" เท่านั้น
(ดู CharacterBrain.is_notable / config_ai.NOTABLE_KINDS,NOTABLE_OUTCOMES) — ห้ามเรียกทุก tick

ปิดไว้เป็นค่าเริ่มต้น (config_ai.LLM_ENABLED = False) เพราะเป็น blocking HTTP call ต่อครั้ง — ถ้าเปิด
ตลอดเวลาจะทำให้ batch simulation (autotune.py/daemon.py ที่ต้องรันเร็วหลายหมื่นเหตุการณ์) ช้าลงมหาศาล
เปิดใช้ผ่าน --llm ใน run.py/daemon.py เฉพาะตอนอยากได้บทพูด/ความคิดจริงสำหรับสร้างนิยาย (Phase 6)

httpx ถูก import แบบ lazy ข้างในนี้เท่านั้น (ไม่ import ตอนโหลดโมดูล) เพื่อไม่ให้ทั้งแพ็กเกจ
tiandao.ai ต้องพึ่ง httpx แม้ตอนไม่ได้เปิดใช้ Layer 3 เลย
"""
import json
import logging
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Dict, Optional, Tuple

from . import config_ai as ACFG

if TYPE_CHECKING:
    from ..models import Character, Event
    from ..sim import Sim
    from .brain import CharacterBrain

logger = logging.getLogger(__name__)


@dataclass
class NarrativeMoment:
    """ผลลัพธ์ของ Layer 3 หนึ่งครั้ง — การเก็บอันนี้ไว้ใน CharacterBrain.narrative_moments
    คือ "Memory Update" ตามที่ ROLE.md ระบุว่าเป็นผลลัพธ์อย่างหนึ่งของ Layer 3"""
    day: int
    kind: str
    dialogue: str
    thought: str


def infer_emotion(ch: "Character", ev: "Event") -> str:
    """Current Emotion แบบ heuristic เบาๆ ที่เป็น "ข้อมูลป้อนเข้า" ให้ prompt (ตาม ROLE.md ที่ระบุ
    Current Emotion เป็นหนึ่งใน field ของ prompt) — คำนวณสดจาก state ที่มีอยู่แล้ว ไม่เพิ่ม field
    ใหม่บน Character"""
    max_hp = getattr(ch, "max_hp", 100) or 100
    hp_ratio = getattr(ch, "hp", 100) / max_hp
    if ev.outcome == "ตาย":
        return "สิ้นหวัง"
    if ev.kind == "ทรยศ":
        return "โกรธแค้น"
    if hp_ratio < 0.3:
        return "หวาดกลัว"
    if ev.kind == "ข้ามขั้น" and ev.outcome not in ("ล้มเหลว", "ยังไม่ถึง"):
        return "ปีติยินดี"
    if getattr(ch, "fear", 0.5) > 0.7:
        return "วิตกกังวล"
    if getattr(ch, "greed", 0.5) > 0.7 and ev.kind in ("ชิงสมบัติ", "ดักปล้น"):
        return "ลิงโลด"
    return "สงบนิ่ง"


def build_prompt(ch: "Character", brain: "CharacterBrain", sim: "Sim", ev: "Event") -> Tuple[str, str]:
    """ประกอบ prompt ตามฟิลด์ที่ ROLE.md กำหนด: Character / Traits / Memory / Current Emotion /
    Event / Task — คืน (system_prompt, user_prompt)"""
    region = sim.world(ch.world_id).name
    rep = brain.reputation.get(region, {"fame": 0, "notoriety": 0})
    rel_lines = "\n".join(f"- cid {cid}: {score:+d}" for cid, score in brain.relationships(ch, n=3)) \
        or "- ไม่มีใครสนิทหรือแค้นเป็นพิเศษตอนนี้"
    memory_lines = "\n".join(f"- (วัน {m.day}) {m.kind}: {m.text}" for m in brain.episodic[-3:]) \
        or "- ยังไม่มีความทรงจำ"
    place_fact = brain.semantic.get(ch.place)
    place_note = place_fact.note() if place_fact else "ไม่คุ้นเคย"
    emotion = infer_emotion(ch, ev)

    system = (
        "คุณคือนักเขียนนิยายกำลังภายในแนวเซียนหรูสไตล์จีน กำลังคิดแทนตัวละครหนึ่งตัวในสถานการณ์หนึ่ง "
        'ตอบเป็น JSON เท่านั้นตามรูปแบบ {"dialogue": "...", "thought": "..."} '
        "ห้ามมีข้อความอื่นนอกเหนือจาก JSON และห้ามใส่ markdown code fence "
        "เขียนเป็นภาษาไทยล้วนเท่านั้น ห้ามมีอักษรจีนหรือภาษาอื่นปนอยู่ในคำตอบแม้แต่คำเดียว"
    )
    user = (
        f"[ตัวละคร] {ch.name} — {ch.race()} สาย{ch.dao} ({ch.archetype}) ขั้น {ch.realm_name()}\n"
        f"[นิสัย] {', '.join(ch.traits) or 'ไม่มีเด่นชัด'} "
        f"(กลัว {ch.fear:.1f} โลภ {ch.greed:.1f} เมตตา {ch.compassion:.1f})\n"
        f"[ชื่อเสียงที่ {region}] fame={rep['fame']} notoriety={rep['notoriety']}\n"
        f"[ความสัมพันธ์เด่น]\n{rel_lines}\n"
        f"[ความจำล่าสุด]\n{memory_lines}\n"
        f"[ความรู้สึกต่อสถานที่นี้] {place_note}\n"
        f"[อารมณ์ปัจจุบัน] {emotion}\n"
        f"[เหตุการณ์ที่เพิ่งเกิด] {ev.kind} — {ev.text} (ผล: {ev.outcome})\n"
        f"[งาน] เขียนบทพูดสั้น 1 ประโยคที่ {ch.name} อาจพูดออกมาตอนนี้ และความคิดในใจสั้น 1 ประโยค "
        "ให้สอดคล้องกับนิสัย อารมณ์ และเหตุการณ์ข้างต้น"
    )
    return system, user


_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)
_OPEN_THINK_RE = re.compile(r"<think>.*", re.DOTALL)


def _strip_think(content: str) -> str:
    """ตัด <think>...</think> ของโมเดลสาย reasoning (Qwen3 — ทั้ง typhoon2.5 และ pathumma) ทิ้ง

    ต่อให้ส่ง /no_think ไปแล้วโมเดลก็ยังพ่น think block ออกมาได้เป็นครั้งคราว ถ้าไม่ตัดทิ้งตรงนี้
    เหตุผลของโมเดล (บ่อยครั้งเป็นภาษาอังกฤษ) จะไหลลง dataset ตรงๆ — เจอจริงตอนทดสอบ pathumma
    ครั้งแรก: ตอนนิยายที่ได้เป็นภาษาไทยแค่ 39% ที่เหลือเป็น chain-of-thought อังกฤษ
    (เคสที่ยังเปิด <think> ค้างไว้ไม่ปิด ตัดตั้งแต่แท็กเปิดจนจบข้อความ)"""
    content = _THINK_RE.sub("", content)
    content = _OPEN_THINK_RE.sub("", content)
    return content.strip()


def _strip_code_fence(content: str) -> str:
    content = _strip_think(content)
    if content.startswith("```"):
        content = content.strip("`")
        if "\n" in content:
            content = content.split("\n", 1)[1]
    return content.strip()


_DIALOGUE_RE = re.compile(r'"dialogue"\s*:\s*"((?:[^"\\]|\\.)*)"')
_THOUGHT_RE = re.compile(r'"thought"\s*:\s*"((?:[^"\\]|\\.)*)"')


def _unescape_json_string(s: str) -> str:
    try:
        return json.loads(f'"{s}"')
    except json.JSONDecodeError:
        return s


def _parse_response(content: str) -> Dict[str, str]:
    """โมเดลจริง (แม้เปิด format=json แล้ว) ยังพัง JSON บ่อย — comma ห้อยท้ายก่อนปิดวงเล็บ, ตัดขาด
    กลางคัน (ชนเพดาน token), หรือโครงสร้างเพี้ยน (วงเล็บเกิน/ขาด) เจอจริงตอนรัน --llm ครั้งแรกที่ scale
    (dry run 3000 เหตุการณ์) ก่อนแก้ตรงนี้ ทุก parse ที่พังจะได้ dialogue="" thought=<JSON ดิบที่พัง>
    ซึ่งเอาไปเทรน LoRA ต่อจะสอนให้โมเดลเขียน "ความคิด" เป็นไวยากรณ์ JSON พัง — จึงต้องกู้เท่าที่กู้ได้
    ก่อนยอมแพ้ และตอนยอมแพ้จริงๆ ต้องคืนค่าว่าง ไม่ใช่ข้อความดิบ"""
    content = _strip_code_fence(content)
    try:
        data = json.loads(content)
        return {
            "dialogue": str(data.get("dialogue", "")).strip(),
            "thought": str(data.get("thought", "")).strip(),
        }
    except (json.JSONDecodeError, AttributeError):
        pass

    repaired = re.sub(r",\s*}", "}", content)  # comma ห้อยท้าย — ข้อผิดพลาดที่พบบ่อยที่สุด
    if repaired != content:
        try:
            data = json.loads(repaired)
            return {
                "dialogue": str(data.get("dialogue", "")).strip(),
                "thought": str(data.get("thought", "")).strip(),
            }
        except (json.JSONDecodeError, AttributeError):
            pass

    d_match = _DIALOGUE_RE.search(content)
    t_match = _THOUGHT_RE.search(content)
    if d_match or t_match:
        logger.warning("llm_agent: JSON พังทั้งก้อน แต่กู้ field ได้บางส่วนด้วย regex: %.120s", content)
        return {
            "dialogue": _unescape_json_string(d_match.group(1)).strip() if d_match else "",
            "thought": _unescape_json_string(t_match.group(1)).strip() if t_match else "",
        }

    logger.warning("llm_agent: parse JSON จาก Ollama ไม่สำเร็จ กู้ field ไม่ได้เลย ทิ้งข้อความนี้: %.120s", content)
    return {"dialogue": "", "thought": ""}


class OllamaAgent:
    """ห่อ HTTP call ไป Ollama local server — sync/blocking โดยตั้งใจ (ดูเหตุผลที่หัวไฟล์)"""

    def __init__(self, host: str = ACFG.OLLAMA_HOST, model: str = ACFG.OLLAMA_MODEL,
                 timeout: float = ACFG.OLLAMA_TIMEOUT) -> None:
        self.host = host
        self.model = model
        self.timeout = timeout

    def _post_chat(self, system: str, user: str, timeout: Optional[float] = None,
                    num_ctx: Optional[int] = None, response_format: Optional[str] = None) -> Optional[str]:
        """เรียก /api/chat ดิบๆ คืนข้อความ (ยังไม่ parse) หรือ None ถ้าเรียกไม่สำเร็จ — ใช้ร่วมกัน
        ทั้ง chat() (Layer 3 บทพูด/ความคิดสั้นๆ), tiandao/ai/history.py (Phase 6 ร้อยแก้วยาว) และ
        narrative_factory/style_distill.py (Phase K6 วิเคราะห์ตอนนิยายยาว)

        **`num_ctx`**: Ollama ดีฟอลต์ context window ของ runtime ไว้แค่ 4096 token เสมอไม่ว่าโมเดล
        จะรองรับยาวแค่ไหนจริง (`ollama show` อาจบอก 131072 แต่ถ้าไม่ส่ง `options.num_ctx` มาตรงๆ จะ
        โดนตัดเหลือ 4096 อยู่ดี) — เจอบั๊กจริงตอน Phase K6: prompt ยาว ~5,900 token ทำให้
        `deepseek-r1:8b` error `exceed_context_size_error` ตรงๆ ส่วน `qwen2.5vl:7b` ไม่ error แต่ตอบ
        นอกประเด็นสม่ำเสมอ (คาดว่าโดนตัด context เงียบๆ) — ไม่ใส่พารามิเตอร์นี้ (None) คือพฤติกรรมเดิม
        ทุกประการสำหรับ caller เดิม (Phase 5/6) ที่ prompt สั้นพอไม่เคยชนปัญหานี้"""
        try:
            import httpx
        except ImportError:
            logger.error("llm_agent: ต้องติดตั้ง httpx ก่อนเรียก Ollama (pip install httpx) — "
                         "หรือปิด config_ai.LLM_ENABLED ไว้ก่อนถ้ายังไม่พร้อม")
            return None

        options = {"temperature": ACFG.OLLAMA_TEMPERATURE}
        if num_ctx is not None:
            options["num_ctx"] = num_ctx

        # โมเดลสาย reasoning ต้องสั่งปิดโหมดคิดก่อน ไม่งั้นจะเสียเวลา (และโควตา token) ไปกับ
        # chain-of-thought ที่เราไม่ได้ใช้ แถม JSON พังและมีภาษาอังกฤษปนออกมา
        if self.model in ACFG.NO_THINK_MODELS and "/no_think" not in user:
            user = f"{user}\n/no_think"

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
            "options": options,
        }
        if response_format is not None:
            # Ollama's structured-output mode (constrains sampling to valid JSON) — cuts down on
            # trailing-comma/truncated output a lot, but not to zero, so _parse_response() still
            # has to repair/gracefully-degrade on top of this
            payload["format"] = response_format

        try:
            resp = httpx.post(
                f"{self.host}/api/chat",
                json=payload,
                timeout=timeout if timeout is not None else self.timeout,
            )
            resp.raise_for_status()
        except httpx.HTTPError:
            logger.warning("llm_agent: เรียก Ollama ไม่สำเร็จ (model=%s, host=%s)",
                           self.model, self.host, exc_info=True)
            return None

        return resp.json().get("message", {}).get("content", "")

    def chat(self, system: str, user: str) -> Optional[Dict[str, str]]:
        """Layer 3 (Phase 5): ขอผลลัพธ์เป็น JSON {"dialogue","thought"} สั้นๆ"""
        content = self._post_chat(system, user, response_format="json")
        if content is None:
            return None
        return _parse_response(content)

    def complete(self, system: str, user: str, timeout: Optional[float] = None,
                 num_ctx: Optional[int] = None) -> Optional[str]:
        """Phase 6 (History Generator)/Phase K6 (Style Distillation): ขอร้อยแก้วยาวเป็นข้อความธรรมดา
        ไม่ใช่ JSON — ใส่ `num_ctx` ถ้า prompt ยาวเกิน 4096 token (ดู docstring `_post_chat`)"""
        content = self._post_chat(system, user, timeout=timeout, num_ctx=num_ctx)
        if content is None:
            return None
        return _strip_code_fence(content)
