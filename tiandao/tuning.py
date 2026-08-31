# -*- coding: utf-8 -*-
"""เอนจินปรับสมดุลตัวเองข้ามรัน — วัดผลจากซิมจริงเทียบกับเป้าหมาย
แล้วขยับค่าคงที่ใน config.py ทีละก้าวเล็กๆ ทุกครั้งที่รัน autotune.py คือหนึ่งรอบเรียนรู้
ผลที่ปรับได้ถูกจำไว้ในไฟล์ learned_config.json แล้ว run.py โหลดมาทับ config เองอัตโนมัติ"""
import json
import os

from . import config as C

DEFAULT_STATE_PATH = os.path.join(os.path.dirname(__file__), "learned_config.json")

# metric -> (ขอบล่าง, ขอบบน) ที่ถือว่า "โอเค" ไม่ต้องปรับ
TARGETS = {
    "advancement_rate":   (0.06, 0.25),   # สัดส่วนที่เคยข้ามพ้นปุถุชน — อิงจากตัวเลขใน SPEC.md
    "pyramid_monotonic":  (0.85, 1.01),   # พีระมิดขั้นต้องลดหลั่นลงเรื่อยๆ ไม่ป่องกลาง
    "era_rate":           (0.3, 3.0),     # จำนวนรอบตกยุค/ฟื้นยุค ต่อแสนเหตุการณ์
    "org_rate":           (3.0, 15.0),    # องค์กรที่ตั้งได้ ต่อแสนเหตุการณ์
    "chaos_defense_rate": (0.05, 0.25),   # ตาม SPEC เผ่าโกลาหลควรชนะเป็นส่วนใหญ่ — ป้องกันได้เองน้อย
                                           # (นี่คืออัตราป้องกัน "เปล่าๆ" ไม่นับวิชาแก้ทาง ซึ่งควรพลิกเกมได้จริง)
}

# ค่าคงที่ใน config.py ที่ยอมให้ปรับได้ -> (metric ที่คุม, ทิศทาง, min, max, ก้าวละเท่าไหร่)
# ทิศทาง +1 = เพิ่มค่านี้แล้ว metric มีแนวโน้มเพิ่มตาม, -1 = เพิ่มค่านี้แล้ว metric มีแนวโน้มลด
TUNABLES = {
    "BREAK_BASE_P":   ("advancement_rate",   +1, 0.35, 0.75, 0.02),
    "NEED_PER_REALM": ("pyramid_monotonic",  +1, 1.5, 6.0, 0.15),
    "BREAK_COST":     ("era_rate",           +1, 1.0, 4.0, 0.10),
    "ORG_FOUND_P":    ("org_rate",           +1, 0.10, 0.60, 0.02),
    "CHAOS_EDGE":     ("chaos_defense_rate", -1, 1.0, 1.5, 0.02),
}


def load_state(path=DEFAULT_STATE_PATH) -> dict:
    if not os.path.exists(path):
        return {"overrides": {}, "history": []}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_state(state, path=DEFAULT_STATE_PATH):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def apply_overrides(overrides: dict):
    """เขียนทับค่าคงที่ใน config module ตรงๆ — ทุกไฟล์ที่ import เป็น C เห็นค่าใหม่ทันที
    เพราะทุกที่เรียกผ่าน C.ชื่อตัวแปร ไม่มีใคร copy ค่าไปตอน import"""
    for k, v in overrides.items():
        setattr(C, k, v)


def _error(value, band):
    if value is None:
        return 0.0
    lo, hi = band
    if value < lo:
        return lo - value      # ต้องเพิ่ม metric นี้
    if value > hi:
        return hi - value      # ต้องลด metric นี้ (ค่าติดลบ)
    return 0.0


def propose_update(overrides: dict, metrics: dict, learning_rate: float = 1.0) -> dict:
    """คืน overrides ชุดใหม่ ขยับแต่ละค่าเข้าหาเป้าหมายทีละก้าว ไม่กระโดดข้ามช่วงที่ยอมรับได้"""
    new_overrides = dict(overrides)
    for param, (metric_name, direction, lo, hi, step) in TUNABLES.items():
        band = TARGETS.get(metric_name)
        if band is None:
            continue
        err = _error(metrics.get(metric_name), band)
        if err == 0.0:
            continue
        cur = new_overrides.get(param, getattr(C, param))
        move = step * (1 if err > 0 else -1) * direction * learning_rate
        new_overrides[param] = round(max(lo, min(hi, cur + move)), 4)
    return new_overrides
