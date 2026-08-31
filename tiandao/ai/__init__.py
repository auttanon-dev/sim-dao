# -*- coding: utf-8 -*-
"""Cultivator Brain v2 — expansion module ตาม ROLE.md

Phase 1 (นี่): Event Bus + CharacterBrain skeleton (episodic memory เท่านั้น ไม่มี GOAP/LLM)
ไม่แก้ tiandao/models.py หรือ tiandao/intent.py เลย — CharacterBrain ผูกกับ Character ผ่าน cid
เป็น component แยก ตามกฎ "ห้ามแก้ Character ตรงๆ ถ้าไม่จำเป็น"
"""
from .brain import BrainManager, CharacterBrain, EpisodicMemory
from .event_bus import EventBus

__all__ = ["EventBus", "BrainManager", "CharacterBrain", "EpisodicMemory"]
