# -*- coding: utf-8 -*-
"""Narrative Dataset Factory — สร้าง training dataset จาก tiandao/world.save สำหรับ LoRA/fine-tune

ไม่รันซิมเอง ไม่รบกวนความเร็ว run.py/daemon.py เลย (ตาม ROLE (1).md: offline/background worker
เท่านั้น) เรียกแยกบนโลกที่เซฟไว้แล้ว เหมือน generate_episode.py (Phase 6 ของ Cultivator Brain v2)

Phase A (ตอนนี้): parser.py + genome.py — sim.log → ParsedEvent (มี scene_type) พร้อมเครื่องมือ
คำนวณ Narrative Genome ("DNA ของฉาก") ให้ scene_extractor.py (Phase B) เรียกใช้ต่อ
"""
from .context_builder import CharacterContext, build_context, build_scene_context
from .genome import NarrativeGenome, build_genome
from .memory_retriever import retrieve_relevant_memory
from .parser import ParsedEvent, classify_scene_type, load_config, parse_log, participants_of
from .scene_extractor import Scene, extract_scenes, index_by_character
from .scoring import ScoreResult, score_candidate
from .tagger import tag_scene
from .validator import ValidationResult, Violation, validate_candidate
from .exporter import export_all
from . import incremental
from . import versioning

__all__ = [
    "ParsedEvent", "parse_log", "classify_scene_type", "load_config", "participants_of",
    "NarrativeGenome", "build_genome",
    "Scene", "extract_scenes", "index_by_character",
    "retrieve_relevant_memory",
    "CharacterContext", "build_context", "build_scene_context",
    "ValidationResult", "Violation", "validate_candidate",
    "ScoreResult", "score_candidate",
    "tag_scene", "export_all", "versioning", "incremental",
]
