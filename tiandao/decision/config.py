# -*- coding: utf-8 -*-
"""โหลด config ของ Decision Engine — ทุกค่าคงที่อยู่ในไฟล์ YAML ใต้ tiandao/decision/config/

    decision_weights.yaml  น้ำหนักสมการ · profile ต่อบุคลิก/ประเภท NPC · ค่าคงที่ของทุกโมดูล
    actions_demo.yaml      ตัวอย่าง action ทั่วไป (attack_enemy/run_away/eat ...) ใช้ในเทสต์และเป็นแม่แบบ
    actions_simdao.yaml    metadata ของ event kind ใน tiandao/events.py:EVENT_TABLE + GOAP + goals

โค้ดทุกโมดูลอ่านค่าผ่าน `cfg.get("risk.win_scale")` — ไม่มี magic number กระจายในโค้ด
ถ้าไม่มี PyYAML ในเครื่องจะใช้ตัวอ่านชุดย่อยใน yamlish.py แทน (ผลเหมือนกันกับไฟล์ของเรา)
"""
import copy
import os

from . import yamlish

CONFIG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config")
DEFAULT_FILES = ("decision_weights.yaml", "actions_demo.yaml", "actions_simdao.yaml")


def load_yaml(path):
    with open(path, encoding="utf-8") as f:
        text = f.read()
    try:
        import yaml  # type: ignore
        return yaml.safe_load(text) or {}
    except ImportError:
        return yamlish.loads(text)


def deep_merge(base, over):
    """merge over เข้า base (สำเนาใหม่) — dict ซ้อนกันถูก merge ลึก ค่าอื่นถูกทับ"""
    out = copy.deepcopy(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


class DecisionConfig:
    """ห่อ dict ของ config + ตัวช่วยอ่านค่าแบบ path และคำนวณ profile ที่ merge แล้ว"""

    def __init__(self, data):
        self.data = data
        self._profile_cache = {}
        self._get_cache = {}

    # ---- อ่านค่า ----
    def get(self, path, default=None):
        # config ไม่เปลี่ยนหลังโหลด — memo ค่าที่อ่านแล้ว (วัดด้วย cProfile: get ถูกเรียก ~600 ครั้ง
        # ต่อการตัดสินใจหนึ่งครั้ง กินเวลา ~20% ของ engine ก่อนมี cache)
        hit = self._get_cache.get(path, _MISSING)
        if hit is not _MISSING:
            return default if hit is _ABSENT else hit
        v = self._lookup(path)
        self._get_cache[path] = v
        return default if v is _ABSENT else v

    def _lookup(self, path):
        node = self.data
        for part in path.split("."):
            if not isinstance(node, dict) or part not in node:
                return _ABSENT
            node = node[part]
        return node

    def need(self, path):
        """เหมือน get แต่ต้องมีค่าจริง — ใช้กับค่าที่ขาดไม่ได้ ให้พังตั้งแต่ต้นดีกว่าได้ผลเพี้ยนเงียบๆ"""
        v = self.get(path, _MISSING)
        if v is _MISSING:
            raise KeyError(f"decision config: ไม่มีค่า '{path}'")
        return v

    # ---- profile ----
    def profile(self, name):
        """engine + weights ที่ merge profile แล้ว: {"weights": {...}, "temperature": x, ...}"""
        name = name or "default"
        hit = self._profile_cache.get(name)
        if hit is not None:
            return hit
        base = {"weights": dict(self.need("weights")),
                "temperature": self.need("engine.temperature"),
                "mode": self.get("engine.mode", "stochastic")}
        prof = (self.get("profiles", {}) or {}).get(name) or {}
        merged = deep_merge(base, prof)
        self._profile_cache[name] = merged
        return merged

    def with_overrides(self, over):
        """config ใหม่ที่ทับค่าบางส่วน (ใช้ในเทสต์/เครื่องมือ) — ไม่แตะของเดิม"""
        return DecisionConfig(deep_merge(self.data, over))

    def __getstate__(self):
        return {"data": self.data}

    def __setstate__(self, state):
        self.data = state["data"]
        self._profile_cache = {}
        self._get_cache = {}


_MISSING = object()
_ABSENT = object()


def load(files=DEFAULT_FILES, overrides=None, config_dir=CONFIG_DIR):
    data = {}
    for name in files:
        path = name if os.path.isabs(name) else os.path.join(config_dir, name)
        if os.path.exists(path):
            data = deep_merge(data, load_yaml(path))
    if overrides:
        data = deep_merge(data, overrides)
    return DecisionConfig(data)
