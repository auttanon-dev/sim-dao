"""ส่งออกตาราง/ค่าคงที่ระดับโมดูลทั้งหมดของต้นฉบับ Python เป็น simdao_core/data/tables.json
(ชื่อตัวพิมพ์ใหญ่ที่แปลงเป็น JSON ได้) — ใช้ตอนย้ายระบบไป Rust; หลังจากนี้ไฟล์ JSON คือแหล่งจริง"""
import importlib, json, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
MODS = ["config", "lore", "skills", "treasures", "elements", "clans", "crafting", "materials", "minerals",
        "emotions", "childhood", "weather", "seasons", "crises", "portals", "worldtree", "branches", "intent",
        "events", "dialogue", "story", "news", "economy", "guardians", "household", "death", "places",
        "paths", "food", "wages", "settlement", "travel", "body.constants", "foresight", "realm_map"]

def conv(v, depth=0):
    if depth > 8:
        raise TypeError
    if isinstance(v, (bool, int, float, str)) or v is None:
        return v
    if isinstance(v, (list, tuple)):
        return [conv(x, depth + 1) for x in v]
    if isinstance(v, (set, frozenset)):
        return sorted((conv(x, depth + 1) for x in v), key=str)
    if isinstance(v, dict):
        return {str(k): conv(x, depth + 1) for k, x in v.items()}
    raise TypeError(type(v))

out = {}
for m in MODS:
    mod = importlib.import_module("tiandao." + m)
    tab = {}
    for k, v in vars(mod).items():
        if k.isupper() or (k[:1].isupper() and k.replace("_", "").isupper()):
            try:
                tab[k] = conv(v)
            except TypeError:
                pass
    out[m] = tab
# ค่าที่คำนวณจากตรรกะของต้นฉบับ (ธาตุของวิชาแต่ละวิชาเดาจากชื่อ/คำบรรยาย)
from tiandao import elements as _EL, skills as _SK
out["derived"] = {"skill_element": {row[0]: _EL.skill_element(row[0]) for row in _SK.SKILLS}}
dst = os.path.join(ROOT, "simdao_core", "data", "tables.json")
with open(dst, "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
print(dst, os.path.getsize(dst), {m: len(t) for m, t in out.items()})
