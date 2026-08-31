# -*- coding: utf-8 -*-
"""Phase K5 — Arc Builder: รวมหลาย `Scene` ของตัวละครเดียวกันเป็น `StoryArc` — rule-based ล้วน
ไม่แต่งเนื้อหาใหม่ (ตาม `ROLE` Phase K) reuse `Scene`/`NarrativeGenome`/`teacher.py` ที่มีอยู่แล้วทั้งหมด

**การจับกลุ่ม**: ฉากของตัวละครเดียวกัน (`focal_cid`) ที่ `day_start` ห่างกันไม่เกิน
`arc_merge_window_days` (config.yaml, ดีฟอลต์ 365) ถือเป็นอาร์คเดียวกัน — ใหญ่กว่า
`scene_merge_window_days` ของ Scene (Phase B, ดีฟอลต์ 3 วัน) มาก เพราะ Arc คือเรื่องราวช่วงยาวข้าม
หลายฉาก ไม่ใช่เหตุการณ์ติดกันในฉากเดียว (ใช้หลักการ cluster ตามช่วงเวลาเดียวกับ `scene_extractor.py`
แค่ทำงานที่ระดับ Scene แทนระดับ Event)

**ที่มาของแต่ละ field ใน `StoryArc` (ทุกอย่างมาจากข้อมูลจริง ไม่มีการแต่งขึ้น)**:
- `goal`: reuse `config.yaml:goal_by_scene_type` (ตารางเดียวกับที่ `context_builder.py` ใช้กำหนด
  `current_goal`) จาก `scene_type` ของ**ฉากแรกในอาร์ค** (สิ่งที่ตัวละครไล่ตามตอนเริ่มอาร์คจริง)
- `obstacle`/`climax`: ฉากที่มี `genome.conflict_level` สูงสุดในอาร์ค (จุดที่ตึงเครียดที่สุดจริง
  ตามที่ `genome.py` คำนวณไว้แล้ว) — `obstacle` = ประเภทความขัดแย้งของฉากนั้น (reuse
  `teacher.analyze_conflict()`), `climax` = `genome.payoff` จริงของฉากนั้น
- `resolution`: `genome.payoff` ของ**ฉากสุดท้ายในอาร์ค** (อาร์คจบด้วยผลจริงอะไร)
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .parser import load_config
from .scene_extractor import Scene


@dataclass
class StoryArc:
    arc_id: str
    protagonist: str
    start_day: int
    end_day: int
    goal: str
    obstacle: str
    climax: str
    resolution: str
    # กราวด์ให้ lesson_exporter.py ใส่ลงฝั่ง input ตอน export ChatML — ไม่งั้น goal/obstacle/climax/
    # resolution ด้านบนจะไม่มีที่มาให้เห็นในฝั่ง input เลย (spurious correlation แบบเดียวกับที่เจอใน
    # Dataset A ปัญหาข้อ 12 — ดู CULTIVATOR_BRAIN_STATUS.md)
    scene_summaries: List[str] = field(default_factory=list)
    # scene_id จริงของทุกฉากในอาร์ค (คู่ขนานกับ scene_summaries ข้างบน) — ให้ lesson_exporter.py ใส่เข้า
    # _meta.scene_ids ตอน export เพื่อให้ train_lora.py รู้ว่า record นี้ "เปิดเผย" เนื้อหาของฉากไหนบ้าง
    # ตอนคำนวณ held-out split (ข้อ 3 — ไม่งั้นฉากที่กันไว้เป็น held-out อาจรั่วผ่าน arc_lesson แทน)
    scene_ids: List[str] = field(default_factory=list)


def _group_by_protagonist(scenes: List[Scene]) -> Dict[int, List[Scene]]:
    groups: Dict[int, List[Scene]] = {}
    for s in scenes:
        groups.setdefault(s.focal_cid, []).append(s)
    return groups


def _cluster_by_gap(scenes: List[Scene], window: int) -> List[List[Scene]]:
    """แบ่งฉากของตัวละครคนเดียว (เรียงตามเวลาแล้ว) เป็นกลุ่มอาร์ค — ฉากที่ `day_start` ห่างจากฉากก่อน
    หน้าเกิน `window` วัน เริ่มอาร์คใหม่"""
    clusters: List[List[Scene]] = []
    current: List[Scene] = []
    for s in scenes:
        if current and (s.day_start - current[-1].day_start) > window:
            clusters.append(current)
            current = []
        current.append(s)
    if current:
        clusters.append(current)
    return clusters


def build_arcs_for_character(cid: int, scenes: List[Scene], sim, config: Optional[dict] = None
                              ) -> List[StoryArc]:
    """สร้าง `StoryArc` ทั้งหมดของตัวละครหนึ่งคนจากฉากจริงของเขา (`scenes` ไม่ต้องเรียงมาก่อนก็ได้
    ฟังก์ชันนี้ sort ตาม `day_start` ให้เอง)"""
    from . import teacher as T

    cfg = config or load_config()
    window = cfg.get("arc_merge_window_days", 365)
    goal_table = cfg.get("goal_by_scene_type", {})
    default_goal = cfg.get("default_goal", "DaoPursuit")
    name = next((c.name for c in sim.cast if c.cid == cid), str(cid))

    ordered = sorted(scenes, key=lambda s: s.day_start)
    arcs = []
    for i, cluster in enumerate(_cluster_by_gap(ordered, window)):
        climax_scene = max(cluster, key=lambda s: s.genome.conflict_level)
        last_scene = cluster[-1]
        arcs.append(StoryArc(
            arc_id=f"{cid}-{i}",
            protagonist=name,
            start_day=cluster[0].day_start,
            end_day=last_scene.day_end,
            goal=goal_table.get(cluster[0].scene_type, default_goal),
            obstacle=T.analyze_conflict(climax_scene, cfg),
            climax=climax_scene.genome.payoff,
            resolution=last_scene.genome.payoff,
            scene_summaries=[
                f"วันที่ {s.day_start} — {s.scene_type} (conflict_level={s.genome.conflict_level}): "
                f"{s.genome.payoff or '(ไม่มี payoff ชัดเจน)'}"
                for s in cluster
            ],
            scene_ids=[s.scene_id for s in cluster],
        ))
    return arcs


def build_all_arcs(scenes: List[Scene], sim, config: Optional[dict] = None) -> List[StoryArc]:
    """เอนทรีพอยต์หลัก — รับฉากทั้งหมดในโลก คืน `StoryArc` ของทุกตัวละครรวมกัน"""
    cfg = config or load_config()
    groups = _group_by_protagonist(scenes)
    arcs: List[StoryArc] = []
    for cid, char_scenes in groups.items():
        arcs.extend(build_arcs_for_character(cid, char_scenes, sim, cfg))
    return arcs
