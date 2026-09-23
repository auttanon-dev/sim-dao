# -*- coding: utf-8 -*-
"""แผนที่ของแดนเซียนสาขา — วางเป็นวงรอบแดนเซียนกลาง แยกขาดจากกันจริง

ทำไมต้องแยกขาด ไม่ใช่ให้ทุกสาขาใช้ผังเดียวกัน
---------------------------------------------------------------------------------------------
ตอนแรกสาขาทั้ง 108 แดนใช้ผังภูมิศาสตร์ร่วมกับแดนเซียนหลัก (place_key = 1) ซึ่งประหยัดมากแต่ทำให้
"การเดินทางข้ามแดน" ไม่มีความหมายเลย — ทุกคนอยู่บนแผนที่เดียวกันหมด การไปอีกสาขาจึงใช้เวลาเท่ากับ
เดินข้ามเมือง ไฟล์นี้แก้ตรงนั้น: แต่ละสาขาได้กลุ่มสถานที่ของตัวเอง วางไว้บนวงแหวนรอบแดนเซียนกลาง
ที่ระยะไกลมาก และ **ทางเข้าออกมีทางเดียวคือผ่านแดนเซียนกลาง** ไม่มีถนนลัดระหว่างสาขาต่อสาขา

ผลที่ตั้งใจให้เกิด:
  - เดินทางไปอีกสาขาใช้เวลาเป็นปีจริงๆ ไม่ใช่ไม่กี่วัน
  - แดนเซียนกลางกลายเป็นชุมทางของทั้งจักรวาลโดยธรรมชาติ ไม่ต้องบังคับ
  - และทำให้ "ประตูมิติ" มีเหตุผลที่จะมีอยู่ (ดู tiandao/portals.py) — ถ้าเดินทางสะดวกอยู่แล้ว
    การทุ่มทรัพยากรมหาศาลสร้างประตูก็ไม่มีใครทำ

ไฟล์นี้ตั้งใจไม่ import places หรือ geo เพื่อไม่ให้เกิดวงจร import — ทั้งสองไฟล์นั้นเรียกเข้ามาที่นี่
แล้วเอาผลไปต่อท้ายตารางของตัวเอง
"""
import math
from typing import List, Tuple

PLACES_PER_REALM = 5
RING_RADIUS = 900.0      # ระยะจากแดนเซียนกลางถึงวงแหวนชั้นในสุด — ไกลระดับเดินทางเป็นปี
RING_STEP = 260.0        # วงแหวนถัดไปห่างออกไปอีกเท่านี้ (กระจายเป็น 3 วง กันไม่ให้เบียดกัน)
RINGS = 3
CLUSTER_SPREAD = 26.0    # ขนาดของกลุ่มสถานที่ภายในสาขาหนึ่ง — เดินในแดนตัวเองใช้เวลาไม่กี่วัน


def realm_key(idx: int) -> str:
    """world_key ของสาขาที่ idx — ใช้เป็นคีย์เดียวกันทั้งใน PLACES และใน World.place_key"""
    return f"br{idx:03d}"


def _core(name: str) -> str:
    return name[len("แดนเซียน"):] if name.startswith("แดนเซียน") else name


def places_for(idx: int, realm_name: str) -> List[tuple]:
    """สถานที่ของสาขาหนึ่งแดน — รูปแบบเดียวกับ PLACES ใน places.py เป๊ะ

    (ชื่อ, world_key, grade, ประเภท, วัตถุดิบ, เตาหลอม, แดนลับของภพ, ติดผนึก)
    """
    k, c = realm_key(idx), _core(realm_name)
    return [
        (f"สำนักใหญ่{c}", k, 2, "สำนัก", None, 1, None, False),
        (f"นคร{c}", k, 1, "เมือง", "แร่", 0, None, False),
        (f"เหมืองศิลา{c}", k, 1, "แหล่งวัตถุดิบ", "แร่", -1, None, False),
        (f"หุบเขาโอสถ{c}", k, 1, "แหล่งวัตถุดิบ", "สมุนไพร", -1, None, False),
        (f"ลานประลอง{c}", k, 1, "ลานฝึก", None, -1, None, False),
    ]


def build_places(branch_names: List[str]) -> List[tuple]:
    out = []
    for i, name in enumerate(branch_names):
        out.extend(places_for(i, name))
    return out


def _cluster_center(i: int, n: int, hub: Tuple[float, float]) -> Tuple[float, float]:
    """จุดกลางของสาขาที่ i บนวงแหวนรอบ hub — กระจายเป็นหลายวงเพื่อไม่ให้เบียดกันเป็นพวง"""
    ring = i % RINGS
    per_ring = max(1, math.ceil(n / RINGS))
    slot = i // RINGS
    ang = 2.0 * math.pi * (slot / per_ring) + ring * (math.pi / RINGS / max(1, per_ring))
    r = RING_RADIUS + ring * RING_STEP
    return hub[0] + r * math.cos(ang), hub[1] + r * math.sin(ang)


def build_geo(start_index: int, branch_names: List[str], hub_xy: Tuple[float, float],
              hub_place_idx: int):
    """คืน (coords, edges) ที่ต้องต่อท้าย GEO.COORDS / GEO.EDGES

    edges ภายในสาขาเป็นถนนสั้น ส่วนทางออกมีเส้นเดียว — จากสำนักใหญ่ของสาขาไปยังชุมทางกลาง
    ของแดนเซียน ระยะเท่ากับระยะจริงบนแผนที่ ซึ่งไกลมากโดยตั้งใจ
    """
    coords: List[Tuple[float, float]] = []
    edges: List[tuple] = []
    n = len(branch_names)
    for i in range(n):
        cx, cy = _cluster_center(i, n, hub_xy)
        base = start_index + i * PLACES_PER_REALM
        for j in range(PLACES_PER_REALM):
            a = 2.0 * math.pi * j / PLACES_PER_REALM
            coords.append((round(cx + CLUSTER_SPREAD * math.cos(a), 2),
                           round(cy + CLUSTER_SPREAD * math.sin(a), 2)))
        # ถนนภายในสาขา — ทุกที่ถึงกันได้ผ่านสำนักใหญ่ (base) เป็นศูนย์กลางของแดนตัวเอง
        for j in range(1, PLACES_PER_REALM):
            d = round(math.dist(coords[-PLACES_PER_REALM], coords[-PLACES_PER_REALM + j]), 2)
            edges.append((base, base + j, d, "road", True))
        # ทางออกเดียวของสาขา — ประตูสู่แดนเซียนกลาง ระยะจริงบนแผนที่ (ไกลระดับเดินทางเป็นปี)
        gx, gy = coords[-PLACES_PER_REALM]
        edges.append((base, hub_place_idx, round(math.dist((gx, gy), hub_xy), 2), "gate", True))
    return coords, edges
