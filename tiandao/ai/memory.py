# -*- coding: utf-8 -*-
"""Memory System (Phase 4): Semantic + Relationship + Reputation

Episodic memory มีอยู่แล้วตั้งแต่ Phase 1 (CharacterBrain.episodic ใน tiandao/ai/brain.py) — ไฟล์นี้
เพิ่มอีกสามชนิดตามสเปคของ ROLE.md

Relationship Memory ไม่เก็บซ้ำ: tiandao/models.py:Character มี ch.rivals/ch.bonds อยู่แล้วและถูก
pickle/save อยู่แล้ว (tiandao/persist.py) — ฟังก์ชันในนี้แค่ "อ่าน" มันมาคำนวณเป็นคะแนนเดียวมี
เครื่องหมาย (ตามตัวอย่าง ROLE.md "Lin = -80") ไม่สร้างที่เก็บซ้อนที่จะเพี้ยนจากของจริงได้

Reputation ในนี้เก็บเป็นตัวเลขโครงสร้างต่อภูมิภาค (fame/notoriety) ยังไม่ปั้นข้อความฉายา — Phase 5
(Ollama) จะเป็นชั้นที่แปลงตัวเลขนี้เป็นฉายาจริง (เช่น "ผู้ใช้กระบี่โลหิต") ตอนสร้างบทพูด/ประวัติ
"""
from dataclasses import dataclass
from typing import TYPE_CHECKING, Dict, List, Tuple

from . import config_ai as ACFG

if TYPE_CHECKING:
    from ..models import Character, Event


# ---------------------------------------------------------------- Semantic (ความรู้เกี่ยวกับสถานที่)
@dataclass
class PlaceFact:
    place_idx: int
    danger: float = 0.0     # EMA เหตุการณ์ร้ายที่เคยเจอที่นี่ด้วยตัวเอง (0..1)
    fortune: float = 0.0    # EMA เหตุการณ์ดีที่เคยเจอที่นี่ด้วยตัวเอง (0..1)
    visits: int = 0
    last_day: int = 0

    def note(self) -> str:
        if self.danger >= ACFG.SEMANTIC_NOTE_THRESHOLD:
            return "อันตราย"
        if self.fortune >= ACFG.SEMANTIC_NOTE_THRESHOLD:
            return "โชคดี"
        return "เฉยๆ"


_BAD_OUTCOMES = frozenset({"ตาย", "พ่ายแพ้", "ล้มเหลว", "รอดตายด้วยชะตา"})
_GOOD_OUTCOMES = frozenset({"สำเร็จ", "ชนะ"})


def observe_place(semantic: Dict[int, PlaceFact], place_idx: int, ev: "Event") -> None:
    """อัปเดตความรู้จากประสบการณ์ตรง (คนละอย่างกับข่าวลือที่มี ch.rumor_leads ทำหน้าที่นี้อยู่แล้ว)"""
    fact = semantic.get(place_idx)
    if fact is None:
        fact = PlaceFact(place_idx=place_idx)
        semantic[place_idx] = fact
    fact.visits += 1
    fact.last_day = ev.day
    alpha = ACFG.SEMANTIC_ALPHA
    if ev.outcome in _BAD_OUTCOMES:
        fact.danger = fact.danger * (1 - alpha) + alpha
    if ev.outcome in _GOOD_OUTCOMES:
        fact.fortune = fact.fortune * (1 - alpha) + alpha
    if len(semantic) > ACFG.SEMANTIC_MEMORY_CAP:
        oldest = min(semantic.values(), key=lambda f: f.last_day)
        semantic.pop(oldest.place_idx, None)


# ---------------------------------------------------------------- Relationship (อ่านจาก ch.rivals/ch.bonds)
def relationship_score(ch: "Character", target_cid: int) -> int:
    """คะแนนความสัมพันธ์แบบมีเครื่องหมาย (+ดี / -แค้น) ตามตัวอย่าง ROLE.md เช่น "Lin = -80"""
    return ch.bonds.get(target_cid, 0) - ch.rivals.get(target_cid, 0)


def top_relationships(ch: "Character", n: int = 5) -> List[Tuple[int, int]]:
    """ความสัมพันธ์ที่ "เข้มข้น" ที่สุด n อันดับ (ดีสุด/แค้นสุด) — ใช้ป้อน prompt ให้ Layer 3 ใน Phase 5"""
    ids = set(ch.rivals) | set(ch.bonds)
    scored = [(cid, relationship_score(ch, cid)) for cid in ids]
    scored.sort(key=lambda pair: abs(pair[1]), reverse=True)
    return scored[:n]


# ---------------------------------------------------------------- Reputation (ต่อภูมิภาค)
_FAME_KINDS = frozenset({"ประลอง", "ถ่ายทอดวิชา", "ปกป้องชาวบ้าน", "สะสมบุญบารมี"})
_NOTORIETY_KINDS = frozenset({"ทรยศ", "ล้างแค้น", "ชิงสมบัติ", "ขูดรีดชาวบ้าน", "ดักปล้น"})


def update_reputation(reputation: Dict[str, Dict[str, int]], region: str, ev: "Event") -> None:
    if ev.kind not in _FAME_KINDS and ev.kind not in _NOTORIETY_KINDS:
        return
    bucket = reputation.setdefault(region, {"fame": 0, "notoriety": 0})
    if ev.kind in _FAME_KINDS and ev.outcome not in _BAD_OUTCOMES:
        bucket["fame"] += 1
    if ev.kind in _NOTORIETY_KINDS:
        bucket["notoriety"] += 1
