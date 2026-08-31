# -*- coding: utf-8 -*-
"""Phase D — Quality Validator: "หัวใจของระบบ" ตาม ROLE.md — เช็ค 6 กฎ ก่อนอนุญาตให้ candidate
(ข้อความที่ Dataset Generator สร้างมา ไม่ว่าจะจาก LLM/template/มนุษย์เขียนเอง) เข้า dataset จริง

ทำงานอิสระจากตัวสร้าง — รับแค่ (text, scene, context_map, sim, character_log) แล้วเทียบกับความจริงจาก
log/context เท่านั้น ไม่สนใจว่า text มาจากไหน

ทุก rule เป็น "heuristic ตรวจจับด้วย string matching" ไม่ใช่ NLU เต็มรูปแบบ — บอกข้อจำกัดไว้ใน
docstring ของแต่ละฟังก์ชันตรงๆ ออกแบบให้ false positive ต่ำที่สุด (Reject ของดีเกินไปดีกว่าปล่อยของเสีย
ผ่าน) แต่ยอมรับว่า false negative เป็นไปได้ (การแต่งเรื่องที่แนบเนียนมากอาจหลุดรอด)
"""
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

from tiandao import config as C

from .context_builder import CharacterContext
from .parser import ParsedEvent
from .scene_extractor import Scene

_DAY_PATTERN = re.compile(r"วันที่\s*(\d+)")
_CJK_PATTERN = re.compile(r"[一-鿿]")   # อักษรจีน — เจอจริงจาก qwen2.5vl ตอน Phase 6 (Cultivator Brain v2)

_ENEMY_WORDS = ("ศัตรู", "คู่แค้น", "เกลียด", "ปรปักษ์", "อริ")
_ALLY_WORDS = ("มิตร", "สหาย", "เพื่อนรัก", "รักใคร่", "ไว้ใจ")


@dataclass
class Violation:
    rule: str
    detail: str


@dataclass
class ValidationResult:
    passed: bool = True
    violations: List[Violation] = field(default_factory=list)

    def add(self, rule: str, detail: str) -> None:
        self.violations.append(Violation(rule, detail))
        self.passed = False


def _all_realm_names() -> Set[str]:
    names = set()
    for tier in range(3):
        for realm in range(C.REALM_CAP + 1):
            names.add(C.realm_name(tier, realm))
    return names


_ALL_REALM_NAMES = _all_realm_names()


def check_rule1_no_new_characters(text: str, scene: Scene, context_map: Dict[int, CharacterContext],
                                   sim) -> List[str]:
    """Rule 1 — ห้ามเพิ่มตัวละครใหม่: ชื่อใครก็ตามในโลก (sim.cast) ที่ปรากฏใน text ต้องเป็นคนที่
    "เกี่ยวข้อง" กับฉากนี้จริง (ผู้ร่วมฉาก หรือถูกอ้างถึงในความสัมพันธ์ของตัวโฟกัส) — ชื่อคนอื่นที่โผล่
    มาลอยๆ ถือว่าเพิ่มตัวละครใหม่เข้ามาโดยไม่มีมูล

    ข้อจำกัด: ตรวจจับได้เฉพาะชื่อที่ตรงกับตัวละครจริงในซิม (string match พอดิบพอดี) — ชื่อที่ประดิษฐ์
    ขึ้นเองไม่ตรงกับใครเลยในซิมจะตรวจไม่เจอด้วยวิธีนี้ (ต้องใช้ NER ถ้าจะตรวจกรณีนั้น)

    ชื่อตัวละครในเอนจินนี้เป็นการเรียงพยางค์จากคลังคำเล็กๆ ต่อกัน (SURNAME+GIVEN) ทำให้ชื่อสั้นบางชื่อ
    บังเอิญเป็น substring อยู่ใน "ชื่อยาวกว่าของอีกคนที่เกี่ยวข้องจริง" ได้ (เช่น "ฟานซิน" ไปซ้อนอยู่ใน
    ชื่อของผู้ร่วมฉากตัวจริงที่ยาวกว่า) — ก่อนเช็คจึง "กลบ" ชื่อที่อนุญาตแล้วออกจาก text ก่อนเสมอ
    (ยาวสุดก่อน กันไม่ให้ชื่อสั้นที่ซ้อนอยู่ข้างในโดนตรวจซ้ำ) เหลือแต่ข้อความที่ไม่มีชื่อที่อนุญาตปนแล้ว
    ค่อยหาชื่อที่ไม่ควรอยู่ตรงนั้น"""
    allowed_cids = set(scene.participants)
    focal_ctx = context_map.get(scene.focal_cid)
    if focal_ctx:
        allowed_cids |= {r["cid"] for r in focal_ctx.relationship}
    allowed_names = {c.name for c in sim.cast if c.cid in allowed_cids and c.name}

    masked = text
    for name in sorted(allowed_names, key=len, reverse=True):
        masked = masked.replace(name, "�" * len(name))

    violations = []
    for c in sim.cast:
        if c.cid in allowed_cids or not c.name or c.name in allowed_names:
            continue
        if c.name in masked:
            violations.append(f'พบชื่อ "{c.name}" (cid={c.cid}) ที่ไม่เกี่ยวข้องกับฉากนี้เลย')
    return violations


def check_rule2_no_fabricated_days(text: str, character_log: List[ParsedEvent],
                                    scene: Optional[Scene] = None) -> List[str]:
    """Rule 2 — ห้ามสร้างเหตุการณ์ที่ไม่มีใน Log: ถ้า text ระบุ "วันที่ N" ที่ N ไม่ตรงกับวันของ
    เหตุการณ์จริงใดๆ เลย ถือว่าแต่งวันที่ขึ้นมาเอง (สัญญาณของการแต่งเหตุการณ์ปลอม — ตรงตามปัญหาที่เจอ
    จริงตอน Phase 6 ของ Cultivator Brain v2 ที่โมเดลแต่งวันที่ 11342/13142/14555 ขึ้นมาเองทั้งที่ไม่มี
    อยู่จริง)

    วันที่ "จริง" มาจากทั้งประวัติของตัวละครโฟกัส (character_log) **และ** เหตุการณ์ทั้งหมดของฉากนี้เอง
    (scene.events) — ฉากหนึ่งอาจมีผู้เกี่ยวข้องหลายคน (scene_extractor.py รวมฉากตามผู้ร่วมเหตุการณ์
    ไม่ใช่แค่ตัวโฟกัสคนเดียว) เหตุการณ์ของ "คนอื่นในฉากเดียวกัน" ก็เป็นวันที่จริงเช่นกัน แม้จะไม่อยู่ใน
    ประวัติส่วนตัวของตัวโฟกัสก็ตาม (พบเป็นบั๊กจริงตอนทดสอบ Phase E — ไม่ใช่แค่สมมุติ)

    ข้อจำกัด: ตรวจจับเฉพาะที่ข้อความระบุวันที่ตัวเลขชัดเจนแบบ "วันที่ N" เท่านั้น"""
    real_days = {e.day for e in character_log}
    if scene is not None:
        real_days |= {e.day for e in scene.events}
    violations = []
    for day_str in _DAY_PATTERN.findall(text):
        day = int(day_str)
        if day not in real_days:
            violations.append(f"อ้างวันที่ {day} ซึ่งไม่มีเหตุการณ์จริงของตัวละครนี้ในวันนั้นเลย")
    return violations


def check_rule3_timeline_order(text: str) -> List[str]:
    """Rule 3 — ลำดับเวลาต้องถูกต้อง: ถ้า text พูดถึงหลายวันที่ ลำดับที่ปรากฏต้องเรียงจากน้อยไปมาก"""
    days = [int(d) for d in _DAY_PATTERN.findall(text)]
    violations = []
    for i in range(1, len(days)):
        if days[i] < days[i - 1]:
            violations.append(f"ลำดับเวลาสลับ: วันที่ {days[i-1]} ตามด้วยวันที่ {days[i]} (ย้อนอดีต)")
    return violations


def _edit_distance_leq(a: str, b: str, k: int) -> bool:
    if abs(len(a) - len(b)) > k:
        return False
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i] + [0] * len(b)
        for j, cb in enumerate(b, 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb))
        prev = cur
    return prev[-1] <= k


def check_rule4_names_exact(text: str, scene: Scene, sim) -> List[str]:
    """Rule 4 — ชื่อต้องตรง: ชื่อตัวละครที่ปรากฏต้องสะกดตรงกับในซิมเป๊ะ — ใช้ edit distance <=1 จับคำที่
    "เกือบตรง" กับชื่อผู้ร่วมฉากแต่ไม่ตรงเป๊ะ (สะกดผิด/ตัดคำผิดจาก LLM)

    เทียบทีละ "คำย่อย" ของชื่อ (ชื่อจริง/นามสกุลแยกกัน) ไม่ใช่ทั้งชื่อเต็มเป็นก้อนเดียว — เพราะชื่อ
    ตัวละครแดนสยามเป็น "ชื่อจริง นามสกุล" มีเว้นวรรค (เช่น "จัน จันทรังษี") ในขณะที่ token ที่ตัดจากข้อความ
    ด้วย regex ไม่รวมช่องว่าง เทียบกับชื่อเต็มที่มีวรรคตรงๆ จะยาวไม่เท่ากันจนหลุดการเช็คไปเสมอ

    ข้อจำกัด: ใช้ edit distance ง่ายๆ ไม่ใช่ fuzzy matching เต็มรูปแบบ อาจ false-positive กับคำบังเอิญ
    คล้ายชื่อ"""
    participant_names = [c.name for c in sim.cast if c.cid in scene.participants]
    name_parts = {part for name in participant_names for part in name.split()}
    violations = []
    tokens = set(re.findall(r"[ก-๙]{3,}", text))
    for tok in tokens:
        if tok in participant_names or tok in name_parts:
            continue
        for part in name_parts:
            if _edit_distance_leq(tok, part, 1):
                violations.append(f'คำ "{tok}" ใกล้เคียงชื่อ "{part}" มาก อาจสะกดผิด')
                break
    return violations


def check_rule5_realm_matches(text: str, context_map: Dict[int, CharacterContext],
                               scene: Scene) -> List[str]:
    """Rule 5 — Realm ต้องตรง: ถ้า text เอ่ยชื่อขั้นบำเพ็ญใดๆ ต้องเป็นขั้นจริงของ**ผู้ร่วมฉากคนใดคน
    หนึ่ง** ณ เวลาของฉากนั้น (มาจาก Event.realm ที่ log จริงแล้ว — ดู context_builder.py)

    เช็คกับผู้ร่วมฉาก**ทุกคน** ไม่ใช่แค่ตัวโฟกัส เพราะฉากหนึ่งอาจมีหลายเหตุการณ์ของคนละคน (เช่น ฉาก
    ที่มีทั้งการข้ามขั้นของคนหนึ่งและการต่อสู้ของอีกคนหนึ่งในช่วงเวลาใกล้กัน) ข้อความจึงเอ่ยขั้นของคนอื่น
    ที่ไม่ใช่ตัวโฟกัสได้อย่างถูกต้องเช่นกัน (พบเป็นบั๊กจริงตอนทดสอบ Phase E — ไม่ใช่แค่สมมุติ)"""
    valid_realms = {ctx.realm_name for ctx in context_map.values() if ctx.realm_name}
    if not valid_realms:
        return []
    violations = []
    for name in _ALL_REALM_NAMES:
        if name and name in text and name not in valid_realms:
            violations.append(f'เอ่ยขั้น "{name}" ซึ่งไม่ตรงกับขั้นจริงของผู้ร่วมฉากคนไหนเลย '
                               f"(ที่ควรเป็น: {sorted(valid_realms)})")
    return violations


def check_rule6_relationship_matches(text: str, focal_ctx: Optional[CharacterContext]) -> List[str]:
    """Rule 6 — Relationship ต้องตรง: ถ้า text ใช้คำบ่งชี้ "ศัตรู" กับคนที่จริงๆ มีสัมพันธ์เป็นบวก
    (หรือกลับกัน) ถือว่าขัดกับความสัมพันธ์จริง (จาก ch.rivals/ch.bonds — ดู context_builder.py)

    ข้อจำกัด: ตรวจจับด้วย keyword ตายตัว ไม่เข้าใจบริบทประโยคจริง (เช่นประชดประชันจะจับผิด)"""
    if focal_ctx is None:
        return []
    violations = []
    for rel in focal_ctx.relationship:
        name = rel["name"]
        if name not in text:
            continue
        score = rel["score"]
        if score > 0 and any(w in text for w in _ENEMY_WORDS):
            violations.append(f'เรียก "{name}" ด้วยคำเชิงศัตรู ทั้งที่ความสัมพันธ์จริงเป็นบวก ({score:+d})')
        if score < 0 and any(w in text for w in _ALLY_WORDS):
            violations.append(f'เรียก "{name}" ด้วยคำเชิงมิตร ทั้งที่ความสัมพันธ์จริงเป็นลบ ({score:+d})')
    return violations


def validate_candidate(text: str, scene: Scene, context_map: Dict[int, CharacterContext],
                        sim, character_log: List[ParsedEvent]) -> ValidationResult:
    """เรียกทั้ง 6 กฎ — ผิดข้อไหนก็ตาม passed=False พร้อมรายละเอียดครบทุกข้อที่ผิด (ไม่หยุดที่ข้อแรก)"""
    result = ValidationResult()
    focal_ctx = context_map.get(scene.focal_cid)

    for detail in check_rule1_no_new_characters(text, scene, context_map, sim):
        result.add("Rule1_NoNewCharacters", detail)
    for detail in check_rule2_no_fabricated_days(text, character_log, scene):
        result.add("Rule2_NoFabricatedEvents", detail)
    for detail in check_rule3_timeline_order(text):
        result.add("Rule3_TimelineOrder", detail)
    for detail in check_rule4_names_exact(text, scene, sim):
        result.add("Rule4_NamesExact", detail)
    for detail in check_rule5_realm_matches(text, context_map, scene):
        result.add("Rule5_RealmMatches", detail)
    for detail in check_rule6_relationship_matches(text, focal_ctx):
        result.add("Rule6_RelationshipMatches", detail)
    return result
