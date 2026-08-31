# -*- coding: utf-8 -*-
"""Phase E — Dataset Export

ประกอบ Dataset A-E (Scene SFT / Dialogue / Internal Monologue / World Chronicle / Planning) จาก
ผลลัพธ์ของ Phase A-D แล้วเขียนเป็น .jsonl ลง datasets/v{N}/ พร้อม metadata.json (ตาม DATASET
VERSIONING ของ ROLE.md)

**ค่าเริ่มต้น (ไม่เปิด --llm)** ใช้ "ร้อยแก้วแบบเรียบ" (เรียงต่อจาก event.text จริงตามลำดับ ไม่แต่ง
คำใหม่เลย) เป็น output ของ Dataset A — รับประกันว่าทุก record กราวด์กับ log 100% ผ่าน Phase D
validator เสมอ (เร็ว ใช้ได้กับฉากเป็นหมื่นในไม่กี่วินาที)

**เปิด --llm** ให้ Ollama เขียนร้อยแก้ว Dataset A จริงแทน (จำกัดจำนวนด้วย --llm-limit เพราะช้า+เสี่ยง
หลอน — พิสูจน์แล้วจาก Cultivator Brain v2 Phase 6) แล้วส่งผ่าน Phase D validator/scoring ทันที —
**ถ้า reject จะ fallback กลับไปใช้ template เสมอ ไม่ทิ้ง record ไปเฉยๆ**

Dataset B/C (Dialogue/Monologue) ใช้ได้เฉพาะฉากที่มีบทพูด/ความคิดจริงอยู่แล้วใน
`brain.narrative_moments` (สร้างไว้ตอนรันซิมด้วย `--llm` — Phase 5 ของ Cultivator Brain v2) เท่านั้น
**ไม่สร้างใหม่ที่ export time** (ขอบเขตตั้งใจของ Phase นี้ — ดู CULTIVATOR_BRAIN_STATUS.md/สรุป Phase E
สำหรับเหตุผล) ถ้าโลกที่โหลดมาไม่เคยรันด้วย --llm เลย Dataset B/C จะว่างเปล่า ซึ่งถูกต้องแล้ว (ไม่ปั้น
บทพูดปลอม) ไม่ใช่ error

**Phase I**: candidate ที่ Phase D ปฏิเสธไม่ถูกทิ้งไปเฉยๆ อีกต่อไป — เขียนลง `rejected_candidates.jsonl`
คู่กับ `scene_sft.jsonl` (พร้อม `violations` และคะแนน) ให้ `narrative_factory/dpo_builder.py` เอาไปจับคู่
กับ candidate ที่ผ่าน (chosen) ของ scene_id เดียวกันจากคนละเวอร์ชัน export สร้างคู่ DPO ได้จริง
"""
import json
import logging
import os
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from tiandao import places as PL
from tiandao.ai import llm_agent as LLM

from . import scoring as SC
from . import tagger as TAG
from . import validator as V
from . import versioning as VER
from .context_builder import CharacterContext
from .parser import ParsedEvent, load_config
from .scene_extractor import Scene

logger = logging.getLogger(__name__)


def _place_name(place_idx: Optional[int]) -> Optional[str]:
    if place_idx is None or place_idx < 0:
        return None
    return PL.PLACES[place_idx][0]


def _template_scene_prose(scene: Scene) -> str:
    """ร้อยแก้วแบบเรียบ — เรียง event.text จริงตามลำดับเวลา ไม่แต่งคำใหม่เลย (กราวด์ 100%)"""
    lines = []
    prev_day = None
    for e in scene.events:
        gap = "" if prev_day is None else f" (ผ่านไป {e.day - prev_day} วัน)"
        lines.append(f"วันที่ {e.day}{gap}: {e.text}")
        prev_day = e.day
    return " ".join(lines)


@dataclass
class CandidateOutcome:
    """ผลของการพยายามใช้ candidate จาก LLM หนึ่งตัว — เก็บพอให้ทั้ง Dataset A (Phase E) และ
    Phase I (DPO Pair Builder) ใช้ต่อได้โดยไม่ต้องเรียก validator ซ้ำสองที่"""
    text: str
    used_llm: bool
    score: Optional[int] = None
    rejected_text: Optional[str] = None
    rejected_violations: Optional[List[str]] = None


def _validated_or_fallback(candidate: Optional[str], fallback: str, scene: Scene,
                            ctx_map: Dict[int, CharacterContext], sim,
                            character_log: List[ParsedEvent]) -> CandidateOutcome:
    """ตรวจ candidate ผ่าน Phase D แล้วตัดสินว่าจะใช้จริงหรือ fallback กลับ template — **ไม่ทิ้ง
    candidate ที่ reject ไปเฉยๆ อีกต่อไป** (Phase I ต้องการเก็บไว้สร้างคู่ Chosen/Rejected)"""
    if not candidate:
        return CandidateOutcome(text=fallback, used_llm=False)
    result = V.validate_candidate(candidate, scene, ctx_map, sim, character_log)
    score = SC.score_candidate(candidate, result, scene=scene)
    if score.passed:
        return CandidateOutcome(text=candidate, used_llm=True, score=score.total)
    logger.info("exporter: candidate ของฉาก %s ไม่ผ่าน Phase D (score=%d/100) — ใช้ template แทน "
                "(candidate เดิมเก็บไว้ที่ rejected_candidates.jsonl สำหรับ Phase I)",
                scene.scene_id, score.total)
    violations = [f"{v.rule}: {v.detail}" for v in result.violations]
    return CandidateOutcome(text=fallback, used_llm=False, score=score.total,
                             rejected_text=candidate, rejected_violations=violations)


def build_scene_input_payload(scene: Scene, sim) -> Dict:
    """สร้าง input_payload (location/participants/events) ที่ทั้ง export (Dataset A) และ
    Shadow Evaluation (Phase J — `shadow_eval.py`) ต้องใช้ตรงกันเป๊ะ — extract ออกมาเป็นจุดเดียวกัน
    ป้องกันไม่ให้ prompt ตอนเทรน/ตอนประเมิน drift ห่างกันถ้าแก้แค่จุดเดียว

    **แก้ spurious correlation จริงที่พบตอนเทรนจนลู่เข้า (สำคัญ)**: เดิม `events` มีแค่ `e.text` ไม่มี
    เลขวันที่เลย ในขณะที่ output template (`_template_scene_prose()`) ใส่ `"วันที่ {day}: ..."` นำหน้า
    ทุกบรรทัดเสมอ — โมเดลที่เทรนจริงจนลู่เข้า (`eval_loss` ลด 0.160→0.131) เรียนแค่ "ต้องมีเลขวันที่
    นำหน้าเสมอ" แต่ไม่มีทางรู้ว่าควรเป็นเลขอะไรจาก input ที่ให้ไป จึงเดาสุ่มทุกครั้ง (ละเมิด
    `Rule2_NoFabricatedEvents` 100% ของฉากที่ทดสอบ) แก้โดยใส่เลข `day` เข้า input ตรงๆ ให้ mapping
    เรียนรู้ได้จริง"""
    participants = [c.name for c in sim.cast if c.cid in scene.participants]
    return {
        "location": _place_name(scene.location),
        "participants": participants,
        "events": [f"วันที่ {e.day}: {e.text}" for e in scene.events],
    }


def build_dataset_a(scene: Scene, sim, ctx_map: Dict[int, CharacterContext],
                     character_log: List[ParsedEvent], agent: Optional[LLM.OllamaAgent],
                     config: dict) -> Tuple[dict, Optional[dict]]:
    """Dataset A — Scene SFT — คืน (record, rejected_record) โดย rejected_record เป็น None เสมอถ้า
    ไม่มี candidate ถูก Phase D ปฏิเสธ (มีไว้ให้ export_all เก็บลง rejected_candidates.jsonl — Phase I)"""
    template = _template_scene_prose(scene)
    outcome = CandidateOutcome(text=template, used_llm=False)
    if agent is not None:
        system = ("คุณคือนักเขียนนิยายกำลังภายในสไตล์จีน เขียนร้อยแก้วบรรยายฉากตามเหตุการณ์ที่ให้มา "
                   "ตามลำดับเป๊ะๆ ห้ามแต่งเหตุการณ์ใหม่ ห้ามข้าม ห้ามสลับลำดับ ห้ามเพิ่มตัวละครที่ไม่มี "
                   "ในรายชื่อผู้เกี่ยวข้อง")
        participants = [c.name for c in sim.cast if c.cid in scene.participants]
        user = (f"[ผู้เกี่ยวข้อง] {', '.join(participants)}\n"
                f"[เหตุการณ์ตามลำดับ]\n{template}\n\n[งาน] เรียบเรียงเป็นร้อยแก้วสั้นๆ")
        candidate = agent.complete(system, user)
        outcome = _validated_or_fallback(candidate, template, scene, ctx_map, sim, character_log)

    scene_type_th = config.get("scene_type_th", {}).get(
        scene.scene_type, config.get("default_scene_type_th", "ฉาก"))
    instruction = f"เขียน{scene_type_th}"
    input_payload = build_scene_input_payload(scene, sim)
    record = {
        "instruction": instruction,
        "input": input_payload,
        "output": outcome.text,
        "tags": TAG.tag_scene(scene, config),
        "_meta": {"scene_id": scene.scene_id, "used_llm": outcome.used_llm, "score": outcome.score},
    }
    rejected_record = None
    if outcome.rejected_text is not None:
        rejected_record = {
            "instruction": instruction,
            "input": input_payload,
            "rejected_output": outcome.rejected_text,
            "score": outcome.score,
            "violations": outcome.rejected_violations,
            "_meta": {"scene_id": scene.scene_id},
        }
    return record, rejected_record


def build_dataset_bc(scene: Scene, sim, ctx_map: Dict[int, CharacterContext]) -> Tuple[Optional[dict], Optional[dict]]:
    """Dataset B (Dialogue) + C (Internal Monologue) — คืน (None, None) ถ้าไม่มีบทพูด/ความคิดจริง
    (จาก brain.narrative_moments เท่านั้น — ไม่สร้างใหม่ที่นี่ ดู docstring หัวไฟล์)

    **แก้ spurious correlation จริง (พบระหว่างตรวจสอบตามปัญหาข้อ 12/13 — ยังไม่มีผลกระทบจริงตอนนี้
    เพราะ Dataset B/C ว่างเปล่าเสมอจนกว่าจะมีโลกที่รันด้วย `--llm` แต่แก้ไว้ก่อนเพื่อไม่ให้เกิดปัญหาเดียว
    กับ Dataset A/E ทันทีที่มีข้อมูลจริง)**: `moment.dialogue`/`moment.thought` เดิมถูกสร้างจริงตอน
    Layer 3 สด (`llm_agent.py:build_prompt()`) โดยมี `[เหตุการณ์ที่เพิ่งเกิด] {kind} — {text} (ผล:
    {outcome})` เป็น input หลัก แต่ record ที่ export ออกมาที่นี่เดิม**ไม่มีเหตุการณ์นี้อยู่ในฝั่ง input
    เลย** (`history`/`memory` = `ctx.recent_memory` ซึ่ง `memory_retriever.py` กรอง `e.day <
    scene.day_start` ตัดเหตุการณ์ปัจจุบันออกไปตั้งใจอยู่แล้ว — เอาไว้กัน "เห็นอนาคต" แต่ผลข้างเคียงคือ
    ตัดเหตุการณ์ที่เป็นต้นเหตุของบทพูด/ความคิดออกไปด้วย) มีแค่ `emotion` (label หยาบๆ) เป็นเงื่อนงำเดียว
    — โมเดลไม่มีทางรู้ว่าเหตุการณ์อะไรที่ทำให้พูด/คิดแบบนั้นจากข้อมูลที่ให้ไป แก้โดยใส่เหตุการณ์ anchor
    ตรงๆ เป็น field ใหม่ `event` (รูปแบบเดียวกับ `build_prompt()` เป๊ะ — เหตุผลเดียวกับที่ moment นี้ถูก
    generate มา)"""
    brain = sim.brain_manager.brains.get(scene.focal_cid)
    if brain is None:
        return None, None
    anchor = scene.events[-1]
    moment = next((m for m in brain.narrative_moments if m.day == anchor.day and m.kind == anchor.kind), None)
    if moment is None:
        return None, None

    ctx = ctx_map[scene.focal_cid]
    event_line = f"{anchor.kind} — {anchor.text} (ผล: {anchor.outcome})"
    dialogue = {
        "speaker": ctx.name, "traits": ctx.traits, "emotion": ctx.emotion,
        "event": event_line, "history": ctx.recent_memory, "response": moment.dialogue,
        "_meta": {"scene_id": scene.scene_id},
    }
    monologue = {
        "character": ctx.name, "goal": ctx.current_goal, "event": event_line,
        "memory": ctx.recent_memory, "thought": moment.thought,
        "_meta": {"scene_id": scene.scene_id},
    }
    return dialogue, monologue


def build_dataset_d(scenes: List[Scene], sim) -> List[dict]:
    """Dataset D — World Chronicle: รวมฉากตาม (world_id, era) แล้วเรียงเป็นพงศาวดารสั้นๆ ต่อยุค

    **แก้ spurious correlation จริง (พบระหว่างตรวจสอบตามปัญหาข้อ 12/13 — ยืนยันกับข้อมูลจริงใน
    datasets/v2/chronicle.jsonl)**: เดิม `events` (ฝั่ง input) มีแค่ `s.genome.payoff` ไม่มีเลขปี ในขณะ
    ที่ `chronicle` (ฝั่ง output) ใส่ `f"ปีที่ {day_start // 365}: ..."` นำหน้าทุกบรรทัดเสมอ — บั๊กเดียว
    กับที่เจอใน Dataset A (ปัญหาข้อ 12) เป๊ะ แค่คนละไฟล์ — แก้ด้วยแนวทางเดียวกัน: ใส่เลขปีเข้า `events`
    (input) ตรงๆ ให้ mapping เรียนรู้ได้จริง"""
    groups: Dict[Tuple[int, int], List[Scene]] = defaultdict(list)
    for s in scenes:
        era = s.events[-1].era if s.events else 0
        groups[(s.world_id, era)].append(s)

    records = []
    for (world_id, era), group in sorted(groups.items()):
        group.sort(key=lambda s: s.day_start)
        world = sim.world(world_id)
        lines = [f"ปีที่ {s.day_start // 365} — {s.genome.payoff}" for s in group]
        records.append({
            "era": f"{world.name} ยุคที่ {era}",
            "events": lines,
            "chronicle": " ".join(lines),
            "_meta": {"world_id": world_id, "era": era, "n_scenes": len(group)},
        })
    return records


def _reconstruct_breakthrough_plan(scene: Scene, character_log: List[ParsedEvent],
                                    config: dict) -> Tuple[List[str], dict]:
    """mirror ของ tiandao/ai/goap.py:FIND_PILL_METHODS แต่คำนวณย้อนหลังจาก log จริง (ไม่ใช่ live
    state) เพราะ Dataset Factory ทำงานบนโลกที่เซฟไว้แล้ว ไม่มีซิมสดให้ถาม

    **แก้ spurious correlation จริง (พบระหว่างตรวจสอบตามปัญหาข้อ 12/13 — ยืนยันกับข้อมูลจริงใน
    datasets/v2/planning.jsonl)**: `plan` (ฝั่ง output) เดิมตัดสินจากการค้นย้อนหลังใน `character_log`
    ทั้งหมด (ตัวแปร `method`/`kind` ด้านล่าง) แต่ `state` (ฝั่ง input) เดิมมีแค่
    `had_pill_at_breakthrough`/`at_furnace`/`at_market`/`place_kind` ซึ่ง**ไม่มีผลต่อการเลือก method
    เลยสักนิด** (โค้ดจริงไม่เคยอ่านค่าพวกนี้ตอนตัดสินใจ) ตรวจ record จริงยืนยัน: ฉากที่ `at_market=True`
    ยังได้ plan `['Travel', 'Breakthrough']` เหมือนฉากที่ไม่ได้อยู่ตลาดเลย — โมเดลไม่มีทางเรียนรู้ mapping
    ที่ถูกต้องจาก `state` เดิมได้ (204/218 ตัวอย่างใน v2 ยุบเหลือ `Travel` เดียวกันหมด เป็น majority-class
    shortcut ไม่ใช่การเรียนรู้จริง) — แก้โดยใส่ `recent_method_evidence` (ข้อความเหตุการณ์จริงที่เป็น
    ตัวตัดสิน method หรือ `None` ถ้าไม่เจอเลย = Travel fallback) เข้า `state` ตรงๆ ให้ mapping เรียนรู้ได้จริง
    (ตรงกับแนวทางเดียวกับที่แก้ Dataset A ปัญหาข้อ 12 — ใส่ข้อมูลที่ตัดสินผลลัพธ์จริงกลับเข้า input)"""
    anchor = scene.events[-1]
    had_pill = "ใช้ยา" in anchor.deltas
    place_kind = None
    has_furnace = False
    if anchor.place is not None and anchor.place >= 0:
        p = PL.PLACES[anchor.place]
        place_kind, has_furnace = p[3], p[5] >= 0
    state = {
        "had_pill_at_breakthrough": had_pill,
        "at_furnace": has_furnace,
        "at_market": place_kind in ("ตลาด", "เมือง"),
        "place_kind": place_kind,
    }
    if had_pill:
        return ["Ready", "Breakthrough"], state

    method_kinds = config.get("goap_method_kinds", {})
    lookback = config.get("goap_lookback_days", 200)
    for method, kind in method_kinds.items():
        for e in reversed(character_log):
            if e.day >= anchor.day:
                continue
            if anchor.day - e.day > lookback:
                break
            if e.kind == kind:
                state["recent_method_evidence"] = e.text
                return [method, "Breakthrough"], state
    state["recent_method_evidence"] = None
    return ["Travel", "Breakthrough"], state


def build_dataset_e(scene: Scene, character_log: List[ParsedEvent], config: dict) -> Optional[dict]:
    """Dataset E — Planning: เฉพาะฉาก Breakthrough เท่านั้น (ตัวอย่างเดียวที่ ROLE.md ให้รายละเอียดพอ
    และเป็นฉากเดียวที่ tiandao/ai/goap.py มี GOAP จริงให้ mirror)"""
    if scene.scene_type != "Breakthrough":
        return None
    plan, state = _reconstruct_breakthrough_plan(scene, character_log, config)
    return {"goal": "Breakthrough", "state": state, "plan": plan,
            "_meta": {"scene_id": scene.scene_id}}


def export_all(scenes: List[Scene], sim, by_cid: Dict[int, List[ParsedEvent]], base_dir: str,
                world_seed: int, total_events: int, agent: Optional[LLM.OllamaAgent] = None,
                llm_limit: int = 0, config: Optional[dict] = None) -> str:
    """สร้างทุก Dataset แล้วเขียนลง datasets/v{N}/*.jsonl + metadata.json — คืน path ของโฟลเดอร์
    เวอร์ชันที่เขียน"""
    from .context_builder import build_scene_context

    cfg = config or load_config()
    scene_sft, dialogue, monologue, planning, rejected = [], [], [], [], []
    llm_used = 0

    for scene in scenes:
        char_log = by_cid.get(scene.focal_cid, [])
        ctx_map = build_scene_context(scene, sim, by_cid, cfg)
        use_agent = agent if (agent is not None and llm_used < llm_limit) else None
        record_a, rejected_a = build_dataset_a(scene, sim, ctx_map, char_log, use_agent, cfg)
        if record_a["_meta"]["used_llm"]:
            llm_used += 1
        scene_sft.append(record_a)
        if rejected_a is not None:
            rejected.append(rejected_a)

        d_rec, m_rec = build_dataset_bc(scene, sim, ctx_map)
        if d_rec:
            dialogue.append(d_rec)
        if m_rec:
            monologue.append(m_rec)

        e_rec = build_dataset_e(scene, char_log, cfg)
        if e_rec:
            planning.append(e_rec)

    chronicle = build_dataset_d(scenes, sim)

    datasets_dir = cfg.get("datasets_dir", "datasets")
    version_dir = VER.next_version_dir(os.path.join(base_dir, datasets_dir))
    files = {
        "scene_sft.jsonl": scene_sft, "dialogue.jsonl": dialogue,
        "monologue.jsonl": monologue, "chronicle.jsonl": chronicle,
        "planning.jsonl": planning, "rejected_candidates.jsonl": rejected,
    }
    for filename, records in files.items():
        with open(os.path.join(version_dir, filename), "w", encoding="utf-8") as f:
            for rec in records:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    meta = VER.make_metadata(
        world_seed=world_seed, event_count=total_events,
        character_count=len(sim.cast),
        counts={k.replace(".jsonl", ""): len(v) for k, v in files.items()},
    )
    VER.write_metadata(version_dir, meta)
    logger.info("exporter: เขียน %s (%d ฉาก, ใช้ LLM จริง %d ครั้ง, ปฏิเสธ %d candidate)",
                version_dir, len(scenes), llm_used, len(rejected))
    return version_dir
