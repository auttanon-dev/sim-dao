# -*- coding: utf-8 -*-
"""บันทึก/โหลดสถานะโลกทั้งก้อน — ให้ซิมเดินต่อข้ามการเรียกโปรแกรมได้ ไม่ใช่รันทีเดียวจบ

Sim ทั้งตัวเป็น dataclass/list/dict/random.Random ล้วนๆ pickle ได้ตรงๆ
โดยไม่ต้องเขียน schema เอง — โหลดกลับมาได้ครบทั้ง rng state, คิวเหตุการณ์, log

ข้อจำกัด: ไฟล์ save ผูกกับโครงสร้าง dataclass ใน models.py ตอนที่เซฟ ถ้าโครงสร้างเปลี่ยนทีหลัง
(เพิ่ม/ลบ field) save เก่าอาจโหลดไม่ขึ้น — ไม่มีระบบ migration ให้ ถ้าพังให้เริ่ม seed ใหม่
"""
import pickle

DEFAULT_PATH = "tiandao/world.save"


def save_sim(sim, path=DEFAULT_PATH):
    with open(path, "wb") as f:
        pickle.dump(sim, f, protocol=pickle.HIGHEST_PROTOCOL)


def load_sim(path=DEFAULT_PATH):
    with open(path, "rb") as f:
        sim = pickle.load(f)
    _backfill_new_attrs(sim)
    return sim


def _backfill_new_attrs(sim):
    """save ที่เซฟไว้ก่อนมี Cultivator Brain v2 (tiandao/ai/) ยังไม่มี event_bus/brain_manager บน
    object — เติมให้เหมือนตอน __init__ ปกติ เพื่อให้ resume ไฟล์เก่าไม่พัง"""
    if not hasattr(sim, "event_bus"):
        from .ai import BrainManager, EventBus
        sim.event_bus = EventBus()
        sim.brain_manager = BrainManager()
        sim.event_bus.subscribe(sim.brain_manager.on_event)
