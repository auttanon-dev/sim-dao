# -*- coding: utf-8 -*-
"""Phase L — Scene Writer: กางฉากหนึ่งฉากเป็นร้อยแก้วเต็มแบบ "ดูหนัง" ด้วยการเรียก LLM หลายรอบ

เหตุผลที่ต้องมีชั้นนี้แยกจาก `exporter.py`
---------------------------------------------------------------------------------------------
`exporter.build_dataset_a()` เดิมขอ **ก้อนเดียวจบ**: ส่ง event.text เรียงกันไปแล้วสั่งว่า
"เรียบเรียงเป็นร้อยแก้วสั้นๆ" ซึ่งเหมาะกับงานที่มันถูกเขียนมาเพื่อทำจริง (ปั้น dataset สำหรับเทรน
LoRA — ต้องการตัวอย่างจำนวนมาก สั้น กราวด์ 100%) แต่ขัดกับเป้าหมาย "นิยายยาว มีบทสนทนาละเอียด
เหมือนกำลังดูหนัง" ตรงๆ สามข้อ:

  1. **คำสั่งบอกให้เขียนสั้น** — และ `scoring._pacing_score` เดิมก็ลงโทษของยาวด้วย (แก้แล้วใน
     รอบก่อน) โมเดลจึงถูกกดให้สรุปทุกฉากเหลือย่อหน้าเดียวโดยไม่มีใครตั้งใจ
  2. **prompt ไม่มีอะไรให้เขียนบทสนทนาเลย** — ไม่มีรายชื่อผู้อยู่ในเหตุการณ์ ไม่มีนิสัย ไม่มี
     ความสัมพันธ์ ไม่มีสภาพอากาศ/อาคาร มีแต่ข้อความสรุปเหตุการณ์ โมเดลจึงเลี่ยงบทพูด
  3. **ขอทุกอย่างพร้อมกันในครั้งเดียว** — โครงเรื่อง + บทพูด + สำนวน + ความตรงข้อเท็จจริง โมเดล
     ขนาด 4-8B ทำพร้อมกันไม่ไหว จะทิ้งอย่างใดอย่างหนึ่งเสมอ (วัดจริงจาก A/B ของโปรเจกต์นี้เอง:
     ตัวที่คะแนนความตรงสูงสุดคือตัวที่เขียนสั้นที่สุด 843 ตัวอักษร)

ชั้นนี้จึงแบ่งงานเป็น 4 pass ให้แต่ละรอบทำเรื่องเดียว
---------------------------------------------------------------------------------------------
  pass 1  โครงฉาก      JSON  บีตละ 1-2 ประโยคว่า "กล้องเห็นอะไร ใครขยับ" — ยังไม่เขียนสำนวน
  pass 2  บทสนทนา      JSON  เฉพาะบีตที่ต้องมีบทพูด คืน [{ผู้พูด, คำพูด, กิริยา}] ตรวจชื่อได้ทันที
  pass 3  ร้อยแก้ว      ข้อความ  ต่อบีต โดยเห็นท้ายบีตก่อนหน้าเป็นบริบท ให้ต่อกันได้ลื่น
  pass 4  ตรวจต่อเนื่อง  **ไม่ใช้ LLM** — deterministic ล้วน (ดู `check_scene`) แล้วสั่งเขียนซ้ำ
                        เฉพาะบีตที่ผิด ไม่ทิ้งทั้งฉาก

pass 4 จงใจไม่ใช้โมเดล เพราะสิ่งที่ต้องตรวจ (ชื่อนอกบัญชี วันที่ที่ไม่มีจริง ลำดับเวลา อักษรจีนปน
ความยาว บทพูดขาด) ตรวจด้วยโค้ดได้แม่นกว่าและฟรี — และ Phase D (`validator.py`) เขียนกฎพวกนี้ไว้
ครบแล้ว ไม่ควรมีโมเดลตัวที่สองมาเดาซ้ำในสิ่งที่โค้ดรู้คำตอบแน่นอนอยู่แล้ว

การเลือกโมเดลต่อ pass อยู่ใน `tiandao/ai/config_ai.py` (OLLAMA_STRUCTURE_MODEL / OLLAMA_PROSE_MODEL)
พร้อมตารางผลวัดจริงที่ใช้ตัดสิน — ไม่ hardcode ชื่อโมเดลในไฟล์นี้
"""
import logging
import copy
import threading
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Set, Tuple

from tiandao import places as PL
from tiandao import seasons as SEASONS
from tiandao import weather as WEATHER
from tiandao.ai import config_ai as ACFG
from tiandao.ai import llm_agent as LLM

_WRITE_LOCK = threading.Lock()

from . import pacing as PACE
from . import scene_cast as SC
from .context_builder import CharacterContext
from .parser import ParsedEvent, load_config
from .scene_extractor import Scene

logger = logging.getLogger(__name__)

_CJK = re.compile(r"[一-鿿]")
_DAY = re.compile(r"วันที่\s*(\d+)")
_QUOTE = re.compile(r'["“”„«»]|(?<![ก-๙])\'')

# คำอธิบายไทยของฟิลด์ snap ที่เปลี่ยน — บอกคนเขียนว่าฉากนี้ "ได้อะไร เสียอะไร" ซึ่งเป็นแก่นของฉาก
_CHANGE_WORD = {
    "ของในตัว": ("ได้ของติดตัวมา", "สูญของไป"),
    "สำนัก": ("ผูกตัวกับสำนัก", "ขาดจากสำนัก"),
    "ตระกูล": ("เข้าสังกัดตระกูล", "ขาดจากตระกูล"),
    "วิชา": ("ได้วิชาใหม่", "เสียวิชาไป"),
    "มิตร": ("ได้มิตรเพิ่ม", "เสียมิตรไป"),
    "ศัตรู": ("ก่อศัตรูเพิ่ม", "ปลดเปลื้องศัตรูไปได้"),
    "ศิษย์": ("รับศิษย์", "เสียศิษย์"),
    "อาจารย์": ("ได้อาจารย์", "ขาดจากอาจารย์"),
    "โลก": ("ข้ามไปอีกแดนหนึ่ง", "ข้ามไปอีกแดนหนึ่ง"),
    "เป็นอยู่": ("ฟื้นคืน", "สิ้นชีพ"),
    "ขั้นนักปรุงยา": ("ฝีมือปรุงยาขยับขึ้น", "ฝีมือปรุงยาถดถอย"),
    "ขั้นช่างตีเหล็ก": ("ฝีมือตีเหล็กขยับขึ้น", "ฝีมือตีเหล็กถดถอย"),
    "ความเสื่อม": ("ร่างโรยราลง", "ร่างกระชุ่มกระชวยขึ้น"),
    "จิตมาร": ("ใจมืดลง", "ใจสว่างขึ้น"),
}


# ---------------------------------------------------------------- สำนวนฉากที่ส่งให้โมเดล
@dataclass
class CastCard:
    """ตัวละครหนึ่งคนเท่าที่ฉากนี้ต้องรู้ — จงใจไม่ยัดทั้งชีวิต (เหตุผลเดียวกับ context_builder)"""
    cid: int
    name: str
    role: str
    realm: str
    dao: str
    archetype: str
    traits: List[str] = field(default_factory=list)
    emotion: str = ""
    relation: str = ""

    def line(self) -> str:
        bits = [f"{self.name} ({self.role})", f"สาย{self.dao}" if self.dao else "", self.realm,
                self.archetype, ("นิสัย " + "/".join(self.traits)) if self.traits else "",
                ("อารมณ์ตอนนี้ " + self.emotion) if self.emotion else "", self.relation]
        return " — ".join(b for b in bits if b)


@dataclass
class ScenePackage:
    """ทุกอย่างที่คนเขียนฉากนี้ต้องรู้ ประกอบครั้งเดียวแล้วใช้ซ้ำได้ทั้ง 4 pass"""
    scene_id: str
    scene_type_th: str
    year: int
    day_start: int
    day_end: int
    place_name: str
    place_kind: str
    building: str
    season: str
    weather: str
    focal_name: str
    cast: List[CastCard]
    roster: List[str]
    real_days: Set[int]
    changes: List[str]
    memory: List[str]
    events: List[str]
    beats: List[PACE.Beat]
    target_chars: int = ACFG.SCENE_TARGET_CHARS
    previous_chapter: str = ""

    def setting_block(self) -> str:
        where = self.place_name if self.building in ("", "-") else f"{self.place_name} ({self.building})"
        return (f"[เมื่อไหร่ที่ไหน] ปีที่ {self.year} {self.season} ฟ้า{self.weather} — {where}"
                f" ({self.place_kind})")

    def cast_block(self) -> str:
        return "[ผู้อยู่ในฉาก]\n" + "\n".join(f"- {c.line()}" for c in self.cast)

    def truth_block(self) -> str:
        parts = ["[สิ่งที่เกิดขึ้นจริงตามบันทึก — ห้ามขัด ห้ามเพิ่มเหตุการณ์นอกนี้]"]
        parts += [f"- {t}" for t in self.events]
        if self.changes:
            parts.append("[ฉากนี้เปลี่ยนอะไรไป]")
            parts += [f"- {c}" for c in self.changes]
        if self.memory:
            parts.append("[สิ่งที่ตัวละครหลักจำได้จากก่อนหน้านี้]")
            parts += [f"- {m}" for m in self.memory[:4]]
        if self.previous_chapter:
            parts.append('[ท้ายตอนก่อนหน้า — ใช้รักษาน้ำเสียงและรอยต่อ ไม่เล่าซ้ำ และไม่เพิ่มผู้ร่วมฉากจากข้อความนี้]\n' + self.previous_chapter)
        return "\n".join(parts)

    def rules_block(self) -> str:
        return ("[กติกาเหล็ก]\n"
                f"- ตัวละครที่เอ่ยชื่อได้มีเพียง: {', '.join(self.roster)} ห้ามเพิ่มชื่อใหม่แม้แต่ชื่อเดียว\n"
                "- ห้ามแต่งเหตุการณ์ที่ไม่มีในบันทึก ห้ามสลับลำดับ ห้ามข้ามเหตุการณ์ใด\n"
                "- ห้ามระบุเลขวันที่ในร้อยแก้ว ใช้คำบอกเวลาแบบเล่าเรื่องแทน (เช่น เช้าวันนั้น สามวันต่อมา)\n"
                "- เขียนภาษาไทยล้วน ห้ามมีอักษรจีนหรือภาษาอื่นปนแม้แต่ตัวเดียว\n"
                "- สำนวนนิยายกำลังภายในจีน ห้ามใช้คำทับศัพท์สมัยใหม่")


def _prev_snap(char_log: Sequence[ParsedEvent], anchor: ParsedEvent) -> tuple:
    prev = None
    for e in char_log:
        if (e.day, e.seq) >= (anchor.day, anchor.seq):
            break
        if getattr(e, "snap", ()):
            prev = e.snap
    return tuple(prev or ())


def _describe_changes(changed: Dict[str, Tuple[int, int]]) -> List[str]:
    out = []
    for fieldname, (before, after) in changed.items():
        up, down = _CHANGE_WORD.get(fieldname, (f"{fieldname}เพิ่ม", f"{fieldname}ลด"))
        out.append(up if after > before else down)
    return out


def _place_bits(place: Optional[int], building: int) -> Tuple[str, str, str]:
    if place is None or place < 0 or place >= len(PL.PLACES):
        return "ที่ใดสักแห่ง", "-", "-"
    p = PL.PLACES[place]
    b = "-"
    if building is not None and building >= 0:
        try:
            from tiandao import settlement as SETTLE
            b = SETTLE.building_type_of(place, building) or "-"
        except Exception:
            b = "-"
    return p[0], p[3], b


def _relation_word(focal_ctx: Optional[CharacterContext], cid: int) -> str:
    if focal_ctx is None:
        return ""
    for rel in focal_ctx.relationship:
        if rel["cid"] == cid:
            return "สนิทสนมกัน" if rel["score"] > 0 else "บาดหมางกัน"
    return ""


def _disambiguate(cast: List[CastCard], sim) -> None:
    """แยกคนชื่อเดียวกันที่บังเอิญมาอยู่ในฉากเดียวกันออกจากกัน — แก้ที่ฉาก ไม่ใช่ที่เอนจิน

    ชื่อตัวละครในเอนจินเกิดจากการต่อพยางค์จากคลังคำเล็กๆ (`rng.choice(SURNAME) + rng.choice(GIVEN)`)
    โลกหนึ่งจึงมีตัวละคร 4,296 ตัวแต่มีชื่อไม่ซ้ำกันแค่ 1,033 ชื่อ — ชื่อซ้ำเป็นเรื่องปกติของโลกนี้
    และไม่ใช่บั๊ก (คนชื่อซ้ำกันมีจริง) แต่ **สองคนชื่อเดียวกันในฉากเดียวกัน**พังทันทีสามชั้น: ผู้อ่าน
    แยกไม่ออก, โมเดลระบุผู้พูดไม่ได้, และ `_clean_lines` จับคู่ผู้พูดกลับเข้าบัญชีรายชื่อผิดตัว
    (เจอจริงตั้งแต่บทแรกของตัวละครแรกที่ลอง: มี "เย่ฟาน" สองคนอยู่ในฉากเดียวกัน)

    วิธีแยกใช้ของที่นิยายจีนใช้จริง — ระบุสังกัดหรือสายวิชาต่อท้ายชื่อ ไม่ใช่ใส่เลขกำกับ
    """
    from collections import Counter
    dup = {n for n, k in Counter(c.name for c in cast).items() if k > 1}
    if not dup:
        return
    for c in cast:
        if c.name not in dup:
            continue
        ch = next((x for x in sim.cast if x.cid == c.cid), None)
        tag = ""
        if ch is not None and ch.org is not None and ch.org < len(sim.orgs):
            tag = f"แห่ง{sim.orgs[ch.org].name}"
        elif c.dao:
            tag = f"สาย{c.dao}"
        elif c.realm:
            tag = f"ขั้น{c.realm}"
        if tag:
            c.name = f"{c.name}{tag}"


def build_package(scene: Scene, sim, ctx_map: Dict[int, CharacterContext],
                  char_log: Sequence[ParsedEvent], presence: Optional[SC.Presence] = None,
                  config: Optional[dict] = None) -> ScenePackage:
    """ประกอบสำนวนฉากจากของที่มีอยู่แล้วทั้งหมด — ไม่คำนวณอะไรใหม่ที่โมดูลอื่นทำไว้แล้ว

    `presence` เป็นตัวเลือก: ถ้าส่งมา จะได้ "คนที่ยืนอยู่ตรงนั้นด้วยแต่ไม่ได้ลงมือ" เข้าฉากเป็นตัว
    ประกอบ (ประกอบย้อนหลังจาก log — ดู scene_cast.Presence) ถ้าไม่ส่งก็ได้แค่ผู้ลงมือกับคู่กรณี
    """
    cfg = config or load_config()
    anchor = scene.events[-1]
    pname, pkind, bname = _place_bits(scene.location, getattr(anchor, "building", -1))
    world = sim.world(scene.world_id)
    try:
        wdesc = WEATHER.get_current_weather(anchor.day, getattr(world, "place_key", 0)).get("name", "-")
    except Exception:
        wdesc = "-"

    focal_ctx = ctx_map.get(scene.focal_cid)
    by_cid_name = {c.cid: c.name for c in sim.cast}

    cast: List[CastCard] = []
    seen: Set[int] = set()
    for cid in [scene.focal_cid] + [c for c in scene.participants if c != scene.focal_cid]:
        ctx = ctx_map.get(cid)
        if ctx is None or cid in seen:
            continue
        seen.add(cid)
        cast.append(CastCard(
            cid=cid, name=ctx.name,
            role="ตัวเอกของฉาก" if cid == scene.focal_cid else "ผู้ร่วมเหตุการณ์",
            realm=ctx.realm_name, dao=ctx.dao, archetype=ctx.archetype,
            traits=list(ctx.traits)[:3], emotion=ctx.emotion,
            relation=_relation_word(focal_ctx, cid),
        ))
    if presence is not None:
        taken = {c.name for c in cast}
        for cid in presence.who_at(scene.location if scene.location is not None else -1,
                                   anchor.day, exclude=seen, limit=3):
            name = by_cid_name.get(cid)
            ch = next((c for c in sim.cast if c.cid == cid), None)
            # ตัวประกอบที่ชื่อชนกับคนที่มีบทบาทจริงอยู่แล้ว ตัดทิ้งไปเลย — มันไม่ได้ทำอะไรในฉากนี้
            # การเก็บไว้มีแต่ทำให้ผู้อ่าน (และตัวโมเดลเอง) แยกไม่ออกว่าใครเป็นใคร
            if not name or ch is None or name in taken:
                continue
            seen.add(cid)
            taken.add(name)
            cast.append(CastCard(cid=cid, name=name, role="อยู่ในที่เกิดเหตุ ไม่ได้ลงมือ",
                                 realm=ch.realm_name(), dao=ch.dao, archetype=ch.archetype))
    _disambiguate(cast, sim)

    changed = SC.snap_diff(_prev_snap(char_log, anchor), tuple(getattr(anchor, "snap", ()) or ()),
                           tuple(cfg.get("snap_field_names", SC_SNAP_FIELDS)))
    real_days = {e.day for e in scene.events} | {e.day for e in char_log}

    return ScenePackage(
        scene_id=scene.scene_id,
        scene_type_th=cfg.get("scene_type_th", {}).get(scene.scene_type,
                                                       cfg.get("default_scene_type_th", "ฉาก")),
        year=anchor.day // 365, day_start=scene.day_start, day_end=scene.day_end,
        place_name=pname, place_kind=pkind, building=bname,
        season=SEASONS.season_of(anchor.day)[0], weather=str(wdesc),
        focal_name=focal_ctx.name if focal_ctx else by_cid_name.get(scene.focal_cid, "?"),
        cast=cast, roster=[c.name for c in cast], real_days=real_days,
        changes=_describe_changes(changed),
        memory=list(focal_ctx.recent_memory) if focal_ctx else [],
        events=[f"{e.kind}: {e.text} (ผล: {e.outcome})" for e in scene.events],
        beats=PACE.build_scene_beats(scene).beats,
    )


SC_SNAP_FIELDS = ("ของในตัว", "สำนัก", "ตระกูล", "วิชา", "มิตร", "ศัตรู", "ศิษย์", "อาจารย์",
                  "โลก", "เป็นอยู่", "ขั้นนักปรุงยา", "ขั้นช่างตีเหล็ก", "ความเสื่อม", "จิตมาร")


# ---------------------------------------------------------------- ผลลัพธ์
@dataclass
class WrittenBeat:
    stage: str
    outline: str = ""
    lines: List[Dict[str, str]] = field(default_factory=list)
    prose: str = ""
    issues: List[str] = field(default_factory=list)
    rewrites: int = 0
    dialogue_done: bool = False


@dataclass
class SceneScript:
    scene_id: str
    beats: List[WrittenBeat]
    used_llm: bool = False
    calls: int = 0
    issues: List[str] = field(default_factory=list)
    outline_done: bool = False

    @property
    def prose(self) -> str:
        return "\n\n".join(b.prose.strip() for b in self.beats if b.prose.strip())

    @property
    def dialogue_count(self) -> int:
        return sum(len(b.lines) for b in self.beats)

    @property
    def passed(self) -> bool:
        return not self.issues and all(not b.issues for b in self.beats)


# ---------------------------------------------------------------- pass 1 — โครงฉาก
_BEAT_BRIEF = {
    "Opening": "ปูภาพสถานที่และอากาศ ให้เห็นว่าใครอยู่ตรงไหน ยังไม่ต้องมีบทพูด",
    "Inciting": "สิ่งที่พาตัวเอกมาถึงจุดนี้ เริ่มมีคนเอ่ยปาก",
    "Rising": "การเผชิญหน้า ยืดเยื้อที่สุดในฉาก บทสนทนาหลักอยู่ตรงนี้",
    "Peak": "จุดที่สถานะเปลี่ยนจริง คำพูดและการกระทำที่ตัดสิน",
    "Aftermath": "ผลที่ตามมาทันที ใครเห็น ใครจำ ปิดฉาก",
}


def build_outline_prompt(pkg: ScenePackage) -> Tuple[str, str]:
    system = ("คุณคือผู้กำกับที่กำลังวางบล็อกกิ้งของฉากหนึ่งก่อนถ่ายทำ ยังไม่ต้องเขียนสำนวน "
              'ตอบเป็น JSON เท่านั้นตามรูปแบบ {"beats": [{"stage": "...", "outline": "...", '
              '"speakers": ["ชื่อ", ...]}]} ห้ามมีข้อความอื่นนอก JSON')
    stages = "\n".join(f"- {b.stage}: {_BEAT_BRIEF[b.stage]}" for b in pkg.beats)
    user = (f"{pkg.setting_block()}\n{pkg.cast_block()}\n\n{pkg.truth_block()}\n\n"
            f"[โครงที่ต้องวาง — ครบทั้ง 5 บีต เรียงตามนี้]\n{stages}\n\n"
            f"{pkg.rules_block()}\n\n"
            "[งาน] เขียน outline ของแต่ละบีต บีตละ 1-2 ประโยค บอกว่ากล้องเห็นอะไรและใครขยับ "
            "พร้อมระบุ speakers ว่าบีตนั้นใครจะได้พูดบ้าง (เลือกจากรายชื่อที่อนุญาตเท่านั้น "
            "บีตที่ไม่มีบทพูดให้ speakers เป็นลิสต์ว่าง)")
    return system, user


def _apply_outline(script: SceneScript, data) -> bool:
    if not isinstance(data, dict):
        return False
    by_stage = {}
    for item in data.get("beats") or []:
        if isinstance(item, dict) and item.get("stage"):
            by_stage[str(item["stage"]).strip()] = item
    hit = False
    for b in script.beats:
        item = by_stage.get(b.stage)
        if item:
            b.outline = str(item.get("outline", "")).strip()
            hit = True
    return hit


# ---------------------------------------------------------------- pass 2 — บทสนทนา
def build_dialogue_prompt(pkg: ScenePackage, beat: PACE.Beat, outline: str,
                          previous: List[Dict[str, str]]) -> Tuple[str, str]:
    system = ("คุณคือคนเขียนบทสนทนาให้นิยายกำลังภายในจีน เขียนเฉพาะบทพูดของบีตเดียวที่ระบุ "
              'ตอบเป็น JSON เท่านั้นตามรูปแบบ {"lines": [{"speaker": "ชื่อ", "line": "คำพูด", '
              '"action": "กิริยาสั้นๆ ระหว่างพูด"}]} ห้ามมีข้อความอื่นนอก JSON '
              "เขียนภาษาไทยล้วน ห้ามมีอักษรจีนปน")
    said = ""
    if previous:
        said = "\n[บทพูดที่ผ่านมาแล้วในฉากนี้ — อย่าพูดซ้ำความเดิม]\n" + "\n".join(
            f'- {l.get("speaker","")}: {l.get("line","")}' for l in previous[-8:])
    mat = "\n".join(f"- {m}" for m in beat.material) or "- (ไม่มีเหตุการณ์ดิบเฉพาะของบีตนี้)"
    user = (f"{pkg.setting_block()}\n{pkg.cast_block()}\n\n{pkg.truth_block()}\n{said}\n\n"
            f"[บีตที่กำลังเขียน] {beat.stage} — {_BEAT_BRIEF[beat.stage]}\n"
            f"[โครงของบีตนี้] {outline or '(ยังไม่มีโครง ให้อ่านจากเหตุการณ์ดิบด้านล่าง)'}\n"
            f"[เหตุการณ์ดิบของบีตนี้]\n{mat}\n\n{pkg.rules_block()}\n\n"
            f"[งาน] เขียนบทพูดของบีตนี้อย่างน้อย {ACFG.SCENE_DIALOGUE_LINES} บรรทัด "
            "ให้เป็นการโต้ตอบกันจริง ไม่ใช่ต่างคนต่างพูด แต่ละบรรทัดต้องมีน้ำเสียงตรงกับนิสัยและ"
            "ความสัมพันธ์ของคนพูด และห้ามพูดถึงสิ่งที่ยังไม่เกิดขึ้นในฉากนี้")
    return system, user


def _clean_lines(data, roster: Sequence[str]) -> List[Dict[str, str]]:
    """รับเฉพาะบรรทัดที่ผู้พูดอยู่ในบัญชีรายชื่อจริง — กันตัวละครใหม่ตั้งแต่ก่อนเขียนร้อยแก้ว"""
    items = data.get("lines") if isinstance(data, dict) else data
    out: List[Dict[str, str]] = []
    for it in items or []:
        if not isinstance(it, dict):
            continue
        sp = str(it.get("speaker", "")).strip()
        line = str(it.get("line", "")).strip()
        if not line:
            continue
        if sp not in roster:
            match = next((n for n in roster if n and (n in sp or sp in n)), None)
            if match is None:
                logger.debug("writer: ทิ้งบทพูดของ %r ซึ่งไม่อยู่ในบัญชีรายชื่อฉาก", sp)
                continue
            sp = match
        out.append({"speaker": sp, "line": line, "action": str(it.get("action", "")).strip()})
    return out


# ---------------------------------------------------------------- pass 3 — ร้อยแก้ว
def build_prose_prompt(pkg: ScenePackage, beat: PACE.Beat, written: WrittenBeat,
                       tail: str, notes: Sequence[str] = ()) -> Tuple[str, str]:
    target = max(200, int(pkg.target_chars * beat.weight))
    system = ("คุณคือนักเขียนนิยายกำลังภายในจีนที่เขียนฉากแบบให้ผู้อ่านเห็นภาพเหมือนกำลังดูหนัง "
              "บรรยายด้วยรายละเอียดที่จับต้องได้ (แสง เสียง กลิ่น น้ำหนักของอากาศ สีหน้ามือไม้) "
              "เขียนเป็นย่อหน้าร้อยแก้วเท่านั้น ห้ามใส่หัวข้อ ห้ามใส่เลขข้อ ห้ามอธิบายว่ากำลังทำอะไร "
              "ส่งกลับเฉพาะตัวร้อยแก้ว")
    lines = "\n".join(
        f'- {l["speaker"]}: "{l["line"]}"' + (f'  [{l["action"]}]' if l.get("action") else "")
        for l in written.lines) or "- (บีตนี้ไม่มีบทพูด บรรยายล้วน)"
    ctx_tail = f"\n[ท้ายบีตก่อนหน้า — เขียนต่อให้ลื่น ห้ามเล่าซ้ำ]\n...{tail[-400:]}\n" if tail else ""
    mat = "\n".join(f"- {m}" for m in beat.material)
    fix = ("\n[ต้องแก้ให้ได้ในรอบนี้]\n" + "\n".join(f"- {n}" for n in notes)) if notes else ""
    user = (f"{pkg.setting_block()}\n{pkg.cast_block()}\n\n{pkg.truth_block()}\n{ctx_tail}\n"
            f"[บีตที่กำลังเขียน] {beat.stage} — {_BEAT_BRIEF[beat.stage]}\n"
            f"[โครงของบีตนี้] {written.outline}\n"
            + (f"[เหตุการณ์ดิบของบีตนี้]\n{mat}\n" if mat else "")
            + f"[บทพูดที่ต้องร้อยเข้าไปให้ครบทุกบรรทัด ตามลำดับนี้]\n{lines}\n\n"
            f"{pkg.rules_block()}{fix}\n\n"
            f"[งาน] เขียนบีตนี้เป็นร้อยแก้วยาวประมาณ {target} ตัวอักษร "
            + ("แทรกบทพูดทุกบรรทัดไว้ในเครื่องหมายคำพูด พร้อมกิริยาและความคิดของคนพูดรอบๆ บทพูดนั้น "
               if written.lines else "บรรยายล้วนไม่ต้องมีบทพูด ")
            + "แบ่งเป็นหลายย่อหน้า อย่าสรุปรวบรัด")
    return system, user


# ---------------------------------------------------------------- pass 4 — ตรวจต่อเนื่อง
def check_beat(pkg: ScenePackage, beat: PACE.Beat, written: WrittenBeat) -> List[str]:
    """ตรวจบีตเดียว — deterministic ล้วน ไม่เรียกโมเดล (ดูเหตุผลที่ docstring หัวไฟล์)"""
    text = written.prose.strip()
    issues: List[str] = []
    if not text:
        return ["บีตนี้ว่างเปล่า"]
    target = max(200, int(pkg.target_chars * beat.weight))
    if len(text) < target * 0.45:
        issues.append(f"สั้นเกินไป ({len(text)} ตัวอักษร ควรราว {target}) — เขียนให้เห็นภาพมากกว่านี้")
    if _CJK.search(text):
        issues.append("มีอักษรจีนปนอยู่ ต้องเป็นภาษาไทยล้วน")
    if len(re.findall(r'\b[A-Za-z]{3,}\b', text)) >= 6:
        issues.append('มีข้อความภาษาอังกฤษปนอยู่ ให้ส่งเฉพาะเนื้อเรื่องภาษาไทย')
    for d in _DAY.findall(text):
        if int(d) not in pkg.real_days:
            issues.append(f"อ้างวันที่ {d} ซึ่งไม่มีอยู่จริงในบันทึก — ห้ามระบุเลขวันที่")
            break
    if beat.wants_dialogue and written.lines and not _QUOTE.search(text):
        issues.append("บีตนี้ต้องมีบทสนทนาอยู่ในเครื่องหมายคำพูด แต่ไม่พบเลย")
    missing = [l["line"] for l in written.lines if l["line"][:12] and l["line"][:12] not in text]
    if missing:
        issues.append(f"บทพูด {len(missing)} บรรทัดหายไปจากร้อยแก้ว เช่น «{missing[0][:40]}»")
    return issues


def check_scene(pkg: ScenePackage, script: SceneScript, sim=None, scene: Optional[Scene] = None,
                ctx_map: Optional[Dict[int, CharacterContext]] = None,
                char_log: Optional[Sequence[ParsedEvent]] = None) -> List[str]:
    """ตรวจทั้งฉาก — ความยาวรวม ลำดับบีต ชื่อนอกบัญชี และ (ถ้าส่ง sim มา) กฎ 6 ข้อของ Phase D"""
    issues: List[str] = []
    prose = script.prose
    if len(prose) < ACFG.SCENE_MIN_CHARS:
        issues.append(f"ทั้งฉากยาว {len(prose)} ตัวอักษร ต่ำกว่าเกณฑ์ฉากเต็ม ({ACFG.SCENE_MIN_CHARS})")
    if [b.stage for b in script.beats] != PACE.BEAT_STAGES:
        issues.append("ลำดับบีตไม่ครบหรือสลับ")
    if script.dialogue_count == 0:
        issues.append("ทั้งฉากไม่มีบทสนทนาเลย")
    if sim is not None and scene is not None and ctx_map is not None:
        from . import validator as V
        result = V.validate_candidate(prose, scene, ctx_map, sim, list(char_log or []))
        issues += [f"{v.rule}: {v.detail}" for v in result.violations]
    return issues


# ---------------------------------------------------------------- ตัวประสาน
class SceneWriter:
    """เขียนฉากเป็นร้อยแก้วเต็มด้วย 4 pass — `agent=None` คือโหมดแห้ง (ประกอบ prompt ได้ ไม่เรียกโมเดล)

    รับ `agent` ตัวเดียวแล้วสลับโมเดลราย pass ผ่าน `model=` ของ `_post_chat` แทนที่จะถือ agent สองตัว
    — Ollama โหลดโมเดลไว้ในหน่วยความจำอยู่แล้ว การสลับไปมาต่อฉากมีต้นทุนแค่ครั้งแรกของแต่ละตัว
    """

    def __init__(self, agent: Optional[LLM.OllamaAgent] = None,
                 structure_model: str = ACFG.OLLAMA_STRUCTURE_MODEL,
                 prose_model: str = ACFG.OLLAMA_PROSE_MODEL,
                 repair_rounds: int = ACFG.SCENE_REPAIR_ROUNDS, should_stop=None, progress=None,
                 resume=None, checkpoint=None) -> None:
        self.agent = agent
        self.structure_model = structure_model
        self.prose_model = prose_model
        self.repair_rounds = repair_rounds
        self.should_stop = should_stop or (lambda: False)
        self.progress = progress or (lambda message: None)
        self.resume = resume
        self.checkpoint = checkpoint or (lambda script: None)

    # -- helpers ------------------------------------------------------------
    def _complete(self, method, system, user, script, num_predict, model, temperature):
        # Retry only the interrupted pass, checking pause between requests.
        # A fixed ceiling prevents an unbounded generation loop.
        while True:
            if self.should_stop():
                raise InterruptedError('พักการเขียน')
            script.calls += 1
            try:
                return method(system, user, timeout=ACFG.SCENE_PASS_TIMEOUT,
                              num_ctx=ACFG.SCENE_NUM_CTX, num_predict=num_predict,
                              model=model, temperature=temperature)
            except LLM.CompletionTruncated:
                if num_predict >= 4096:
                    raise
                num_predict = min(4096, num_predict * 2)
                self.progress('คำตอบยาวเกินงบรอบแรก กำลังเขียนช่วงเดิมให้จบ')

    def _json(self, system: str, user: str, script: SceneScript, num_predict: int):
        if self.should_stop():
            raise InterruptedError('พักการเขียน')
        self.progress('กำลังวางฉากและบทสนทนา')
        if self.agent is None:
            return None
        return self._complete(self.agent.complete_json, system, user, script,
                              num_predict, self.structure_model, ACFG.SCENE_STRUCT_TEMPERATURE)

    def _prose(self, system: str, user: str, script: SceneScript, target_chars: int) -> Optional[str]:
        if self.should_stop():
            raise InterruptedError('พักการเขียน')
        self.progress('กำลังเรียบเรียงและตรวจร้อยแก้ว')
        if self.agent is None:
            return None
        return self._complete(self.agent.complete, system, user, script,
                              min(4096, max(1200, int(target_chars * 1.4))),
                              self.prose_model, ACFG.SCENE_PROSE_TEMPERATURE)

    # -- ทางเดินหลัก --------------------------------------------------------
    def write(self, pkg: ScenePackage) -> SceneScript:
        while not _WRITE_LOCK.acquire(timeout=.25):
            if self.should_stop():
                raise InterruptedError('พักการเขียน')
        try:
            return self._write(pkg)
        finally:
            _WRITE_LOCK.release()

    def _write(self, pkg: ScenePackage) -> SceneScript:
        script = copy.deepcopy(self.resume) if self.resume is not None else SceneScript(
            scene_id=pkg.scene_id, beats=[WrittenBeat(stage=b.stage) for b in pkg.beats])
        if script.scene_id != pkg.scene_id or [b.stage for b in script.beats] != [b.stage for b in pkg.beats]:
            raise ValueError('ร่างที่บันทึกไว้ไม่ตรงกับฉากนี้')

        # pass 1 — โครงฉากทั้ง 5 บีตในครั้งเดียว (ถูกและทำให้บีตรู้จักกันเอง)
        if not script.outline_done:
            sys_p, usr_p = build_outline_prompt(pkg)
            data = self._json(sys_p, usr_p, script, num_predict=900)
            if data is not None and _apply_outline(script, data):
                script.used_llm = True
                script.outline_done = True
        for b, wb in zip(pkg.beats, script.beats):
            if not wb.outline:
                wb.outline = " ".join(b.material) or _BEAT_BRIEF[b.stage]
        self.checkpoint(script)

        # pass 2 — บทสนทนา เฉพาะบีตที่ต้องมี
        spoken: List[Dict[str, str]] = []
        for b, wb in zip(pkg.beats, script.beats):
            if not b.wants_dialogue:
                continue
            if wb.dialogue_done:
                spoken += wb.lines
                continue
            sys_d, usr_d = build_dialogue_prompt(pkg, b, wb.outline, spoken)
            d = self._json(sys_d, usr_d, script, num_predict=1200)
            if d is not None:
                wb.lines = _clean_lines(d, pkg.roster)
                if wb.lines:
                    script.used_llm = True
                    wb.dialogue_done = True
                    spoken += wb.lines
                    self.checkpoint(script)

        # pass 3 — ร้อยแก้วต่อบีต โดยเห็นท้ายบีตก่อนหน้า
        tail = ""
        for b, wb in zip(pkg.beats, script.beats):
            if wb.prose:
                tail = wb.prose
                continue
            sys_r, usr_r = build_prose_prompt(pkg, b, wb, tail)
            out = self._prose(sys_r, usr_r, script, max(200, int(pkg.target_chars * b.weight)))
            if out:
                wb.prose = out.strip()
                script.used_llm = True
                tail = wb.prose
                self.checkpoint(script)

        # pass 4 — ตรวจต่อเนื่อง (ไม่มีโมเดล) แล้วสั่งเขียนซ้ำเฉพาะบีตที่ผิด
        for _round in range(self.repair_rounds + 1):
            bad = []
            tail = ""
            for b, wb in zip(pkg.beats, script.beats):
                wb.issues = check_beat(pkg, b, wb)
                if wb.issues:
                    bad.append((b, wb, tail))
                tail = wb.prose or tail
            if not bad or self.agent is None or _round == self.repair_rounds:
                break
            for b, wb, prev_tail in bad:
                sys_r, usr_r = build_prose_prompt(pkg, b, wb, prev_tail, notes=wb.issues)
                out = self._prose(sys_r, usr_r, script, max(200, int(pkg.target_chars * b.weight)))
                if out:
                    wb.prose = out.strip()
                    wb.rewrites += 1
                    self.checkpoint(script)

        script.issues = check_scene(pkg, script)
        self.checkpoint(script)
        return script


def write_scene(scene: Scene, sim, ctx_map: Dict[int, CharacterContext],
                char_log: Sequence[ParsedEvent], agent: Optional[LLM.OllamaAgent] = None,
                presence: Optional[SC.Presence] = None,
                config: Optional[dict] = None) -> Tuple[ScenePackage, SceneScript]:
    """ทางเข้าสั้นๆ สำหรับผู้เรียกภายนอก — ประกอบสำนวนฉากแล้วเขียนจบในบรรทัดเดียว"""
    pkg = build_package(scene, sim, ctx_map, char_log, presence=presence, config=config)
    return pkg, SceneWriter(agent=agent).write(pkg)
