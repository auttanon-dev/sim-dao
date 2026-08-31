# -*- coding: utf-8 -*-
"""Phase K6 — Style Distillation: ดึง "รูปแบบ" การเล่าเรื่องจาก Novel_Episodes (คลังนิยายจริงที่มี
ลิขสิทธิ์) ผ่าน LLM — **ห้ามคัดลอกข้อความจากต้นฉบับเด็ดขาด ต้อง distill เป็น "รูปแบบเชิงโครงสร้าง"
เท่านั้น** (ตาม `ROLE` Phase K ย้ำไว้ตรงๆ)

ต่างจาก K1-K5 (rule-based ล้วนบนข้อมูล simulation ที่มีโครงสร้างชัดเจน) — งานนี้วิเคราะห์ร้อยแก้วอิสระ
ที่มนุษย์เขียน ไม่มีทาง rule-based ได้จริง ใช้ `OllamaAgent.complete()` ตัวเดียวกับที่ Phase 6/Phase E
ใช้อยู่แล้ว (ไม่สร้าง LLM client ใหม่)

**ป้องกันการคัดลอกด้วย 2 ชั้น** (สำคัญมาก — ถ้าข้อความมีลิขสิทธิ์หลุดเข้า training data จริงจะเป็น
ความเสี่ยงด้านทรัพย์สินทางปัญญาของโปรเจกต์ ไม่ใช่แค่เรื่องรูปแบบ):
1. System prompt สั่งตรงๆ ห้ามยกประโยคจากต้นฉบับมาทั้งดุ้น
2. `contains_verbatim_copy()` ตรวจภายหลังจริงด้วย n-gram matching — ถ้าเจอ substring ยาว >=
   `MIN_COPY_LEN` ตัวอักษรตรงกับต้นฉบับ ถือว่า reject ทันที ไม่ export เลย (คนละหน้าที่กับ Phase D
   validator ที่เช็คความถูกต้องกับ sim log — อันนี้เช็คกับต้นฉบับนิยายจริงแทน)

Input ตาม ROLE Phase K: Novel_Episodes (ตอนดิบ) + StoryArc/StoryLesson จากซิมของเราเอง (ใส่เป็นบริบท
เสริมให้ LLM เทียบรูปแบบระหว่างนิยายจริงกับสิ่งที่ซิมสร้างได้ตอนนี้)
"""
import logging
import re
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

MIN_COPY_LEN = 20  # อักษรไทยติดกันยาวเท่านี้ขึ้นไปที่ตรงกับต้นฉบับ ถือว่าเสี่ยงคัดลอกตรงๆ

_STYLE_FIELDS = ("hook_pattern", "dialogue_pattern", "pacing_pattern",
                 "cliffhanger_pattern", "narration_pattern")
_LABELS = {f: f.upper() for f in _STYLE_FIELDS}


@dataclass
class StyleLesson:
    source_label: str
    hook_pattern: str
    dialogue_pattern: str
    pacing_pattern: str
    cliffhanger_pattern: str
    narration_pattern: str
    # เก็บตอนนิยายจริงที่ใช้วิเคราะห์ไว้ด้วย (เดิมไม่มี) — ให้ lesson_exporter.py ใส่ลงฝั่ง input ตอน
    # export ChatML แทนที่จะมีแค่ source_label เปล่าๆ ไม่งั้นเป็น spurious correlation แบบเดียวกับที่
    # เจอใน story_lesson/arc_lesson (ปัญหาข้อ 2 — ดู CULTIVATOR_BRAIN_STATUS.md) แต่แย่กว่านั้นอีก เพราะ
    # ที่นี่ต่อให้มี episode content ให้จริง โมเดลก็ยังต้องมโนสไตล์จาก label เปล่าๆ ไม่ได้เลย
    episode_text: str = ""


_SYSTEM_PROMPT = (
    "งานนี้คือ 'การวิเคราะห์เชิงวิชาการ' เท่านั้น ห้ามแต่งเนื้อเรื่องต่อ ห้ามเขียนนิยายเพิ่มเติมเด็ดขาด "
    "ห้ามสรุปเนื้อเรื่อง ห้ามให้คำแนะนำการเขียนต่อ — หน้าที่เดียวของคุณคือนักวิจารณ์วรรณกรรมที่วิเคราะห์ "
    "'รูปแบบเชิงเทคนิค' ของตอนนิยายที่ให้มาเท่านั้น "
    "ห้ามคัดลอกประโยคจากต้นฉบับมาทั้งดุ้นเด็ดขาด ต้องอธิบายเป็นภาษาสรุปเชิงเทคนิคของตัวเองเท่านั้น "
    "(เช่น 'เปิดฉากด้วยคำถามปริศนาที่ตัวละครไม่รู้คำตอบ' ไม่ใช่ยกประโยคเปิดจริงมา) "
    "ตอบเป็น 5 บรรทัดเป๊ะๆ ตามรูปแบบนี้เท่านั้น ห้ามมีคำอธิบายอื่นก่อน/หลัง ห้ามมีหัวข้อลำดับเลข "
    "ห้ามมี <think> หรือขั้นตอนคิดใดๆ ทั้งสิ้น ตอบแค่ 5 บรรทัดนี้ตรงๆ:\n"
    "HOOK_PATTERN: <คำอธิบายรูปแบบการเปิดฉาก 1-2 ประโยค>\n"
    "DIALOGUE_PATTERN: <คำอธิบายรูปแบบบทสนทนา 1-2 ประโยค>\n"
    "PACING_PATTERN: <คำอธิบายรูปแบบจังหวะการเล่า 1-2 ประโยค>\n"
    "CLIFFHANGER_PATTERN: <คำอธิบายรูปแบบการทิ้งท้าย 1-2 ประโยค>\n"
    "NARRATION_PATTERN: <คำอธิบายรูปแบบมุมมองการบรรยาย 1-2 ประโยค>"
)


def contains_verbatim_copy(source: str, candidate: str, window: int = MIN_COPY_LEN) -> bool:
    """ตรวจว่า candidate มีข้อความยาว >= window ตัวอักษรตรงกับ source เป๊ะๆ หรือไม่ — ใช้ n-gram set
    แทน DP หา longest-common-substring เต็มรูปแบบ (ไม่ต้องรู้ความยาวพอดีเป๊ะ แค่ต้องรู้ว่า "มีการคัดลอก
    เกิดขึ้นไหม" — O(n+m) แทน O(n*m))"""
    if len(source) < window or len(candidate) < window:
        return False
    source_ngrams = {source[i:i + window] for i in range(len(source) - window + 1)}
    return any(candidate[i:i + window] in source_ngrams
               for i in range(len(candidate) - window + 1))


def _parse_style_response(content: str) -> Optional[dict]:
    """ค้นหาบรรทัด `LABEL: ...` ของแต่ละ field ที่ไหนก็ได้ในข้อความ (ทนต่อคำอธิบายส่วนเกินที่โมเดลอาจ
    ใส่มาก่อน/หลังแม้สั่งห้ามแล้วก็ตาม รวมถึง <think>...</think> ของโมเดลสาย reasoning) — ต้องเจอครบ
    ทั้ง 5 field ถึงจะถือว่า parse สำเร็จ ไม่งั้นคืน None ทั้งหมด (ไม่เอาผลลัพธ์ครึ่งๆ กลางๆ ไปใช้)"""
    content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL)
    result = {}
    for field, label in _LABELS.items():
        m = re.search(rf"{label}\s*[:：]\s*(.+)", content)
        if not m:
            return None
        result[field] = m.group(1).strip().strip("*").strip()
    return result


def format_sim_reference(lesson=None, arc=None) -> str:
    """แปลง StoryLesson (K1)/StoryArc (K5) จากซิมของเราเองเป็นข้อความสั้นๆ ใส่เป็นบริบทเสริมให้ LLM
    เทียบรูปแบบระหว่างนิยายจริงกับสิ่งที่ซิมสร้างได้ตอนนี้ (Input ตัวที่ 2-3 ตาม ROLE Phase K)"""
    parts = []
    if lesson is not None:
        parts.append(f"ฉากตัวอย่างจากซิม: hook={lesson.hook}, conflict={lesson.conflict}, "
                      f"pacing={lesson.pacing}, payoff={lesson.payoff}")
    if arc is not None:
        parts.append(f"อาร์คตัวอย่างจากซิม: protagonist={arc.protagonist}, goal={arc.goal}, "
                      f"climax={arc.climax}, resolution={arc.resolution}")
    return "\n".join(parts)


def _estimate_num_ctx(system: str, user: str, min_ctx: int = 4096, headroom: int = 1024) -> int:
    """ประมาณ context window ที่ต้องใช้แบบระวังไว้ก่อน (safe overestimate ที่ 0.75 token/ตัวอักษร —
    วัดจริงจาก Phase K6: prompt 9,854 ตัวอักษร ใช้จริง 5,934 token ≈ 0.6 token/ตัวอักษร) ป้องกัน
    `exceed_context_size_error` ของ Ollama (ดีฟอลต์ runtime แค่ 4096 token ไม่ว่าโมเดลรองรับยาวแค่ไหน
    จริง — ดู `llm_agent.py:_post_chat` docstring)"""
    approx_tokens = int((len(system) + len(user)) * 0.75)
    return max(min_ctx, approx_tokens + headroom)


def distill_style(episode_text: str, agent, source_label: str = "",
                   sim_reference: str = "") -> Optional[StyleLesson]:
    """เรียก LLM วิเคราะห์รูปแบบจากตอนนิยายจริง 1 ตอน — คืน None ถ้า parse ไม่ได้ หรือตรวจพบว่า
    LLM คัดลอกข้อความจากต้นฉบับมาตรงๆ (reject ทันที ไม่ retry อัตโนมัติ — ให้ผู้เรียกตัดสินใจเอง)"""
    ref_block = f"\n\n[อ้างอิงจากซิมของเราเอง]\n{sim_reference}" if sim_reference else ""
    user = f"[ตอนนิยาย]\n{episode_text}{ref_block}\n\n[งาน] วิเคราะห์รูปแบบตามที่ระบบสั่งด้านบน"
    num_ctx = _estimate_num_ctx(_SYSTEM_PROMPT, user)
    raw = agent.complete(_SYSTEM_PROMPT, user, num_ctx=num_ctx)
    if raw is None:
        logger.warning("style_distill: เรียก Ollama ไม่สำเร็จสำหรับ %s", source_label)
        return None
    parsed = _parse_style_response(raw)
    if parsed is None:
        logger.warning("style_distill: parse คำตอบไม่สำเร็จสำหรับ %s (หา label ไม่ครบ 5 ตัว): %.150s",
                        source_label, raw)
        return None
    combined = " ".join(parsed.values())
    if contains_verbatim_copy(episode_text, combined):
        logger.warning("style_distill: ตรวจพบ LLM คัดลอกข้อความจากต้นฉบับตรงๆ ที่ %s — reject",
                        source_label)
        return None
    return StyleLesson(source_label=source_label, episode_text=episode_text, **parsed)
