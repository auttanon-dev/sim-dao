# -*- coding: utf-8 -*-
"""Memory Retriever: "Relevant Memory Only" ตาม ROLE.md — ไม่ใช่แค่เอาเหตุการณ์ล่าสุด N อันมาดื้อๆ

หน้าที่เดียวของไฟล์นี้: จากประวัติเต็มของตัวละครโฟกัส (ก่อนวันที่ของฉากเท่านั้น — ห้ามเห็นอนาคต)
ให้คะแนนความเกี่ยวข้องกับฉากปัจจุบัน (คนเกี่ยวข้องเดียวกัน/สถานที่เดียวกัน/เป็นศัตรูกัน) แล้วตัดตาม
token budget ใน config.yaml — "ห้ามยัดทั้งชีวิต"
"""
from typing import TYPE_CHECKING, List, Optional, Set

from .parser import ParsedEvent, load_config, participants_of

if TYPE_CHECKING:
    from .scene_extractor import Scene

# ประมาณคร่าวๆ: ข้อความไทย ~3 ตัวอักษร/token (ไม่ต้องพึ่ง tokenizer จริงสำหรับงานกรองแบบนี้)
_CHARS_PER_TOKEN = 3


def _relevance_score(ev: ParsedEvent, scene_participants: Set[int], scene_location: Optional[int],
                      rival_cids: Set[int]) -> int:
    score = 1   # ฐาน — เคยเกิดขึ้นจริงกับตัวละครนี้ก็นับ
    if participants_of(ev) & scene_participants:
        score += 3   # คนเกี่ยวข้องเดียวกันกับฉากนี้
    if scene_location is not None and ev.place == scene_location:
        score += 2   # สถานที่เดียวกัน
    if participants_of(ev) & rival_cids:
        score += 2   # เกี่ยวข้องกับศัตรู/คู่แค้นของตัวละครนี้
    return score


def retrieve_relevant_memory(scene: "Scene", character_log: List[ParsedEvent],
                              rival_cids: Optional[Set[int]] = None,
                              config: Optional[dict] = None) -> List[str]:
    """คืนข้อความเหตุการณ์ก่อนหน้า (ก่อน scene.day_start เท่านั้น) ของตัวละครโฟกัส เรียงตามความ
    เกี่ยวข้องกับฉากนี้ก่อน แล้วค่อยความใหม่ ตัดเมื่อครบ token budget หรือจำนวนสูงสุด"""
    cfg = config or load_config()
    budget = cfg.get("memory_token_budget", 800)
    max_items = cfg.get("memory_max_items", 8)
    rivals = rival_cids or set()
    scene_participants = set(scene.participants)

    candidates = [e for e in character_log if e.day < scene.day_start]
    scored = [
        (_relevance_score(e, scene_participants, scene.location, rivals), e.day, e)
        for e in candidates
    ]
    scored.sort(key=lambda t: (-t[0], -t[1]))   # เกี่ยวข้องมากก่อน แล้วค่อยใหม่กว่าก่อน

    picked: List[str] = []
    used_tokens = 0
    for _score, _day, e in scored:
        approx_tokens = max(1, len(e.text) // _CHARS_PER_TOKEN)
        if used_tokens + approx_tokens > budget:
            continue
        picked.append(e.text)
        used_tokens += approx_tokens
        if len(picked) >= max_items:
            break
    return picked
