# -*- coding: utf-8 -*-
"""การเดินทาง — ระยะทาง/เวลาเดินทางจริงบนกราฟภูมิศาสตร์ (tiandao/geo.py) แทนการ teleport แบบเดิม

pure stdlib ล้วน (heapq เท่านั้น — ตรงกับสไตล์เดิมของ tiandao/sim.py) ไม่พึ่ง scipy/numpy ที่ตอน
tools/generate_location_graph.py ใช้สร้าง tiandao/geo.py (เป็นแค่ dev-time tool ไม่ใช่ runtime dependency)
"""
import heapq
from typing import Dict, List, Optional, Tuple

from . import config as C
from . import geo as GEO

_ADJ: Optional[Dict[int, List[Tuple[int, float]]]] = None  # lazy-built, cache ไว้ครั้งเดียวต่อโปรเซส
# กราฟอีกชุดสำหรับตอนที่มหาผนึกหมื่นมารพังแล้ว (เดินข้ามแดนมารได้) — เดิมเส้นทางแบบนี้ไม่ถูก cache
# เลย เพราะเงื่อนไข cache ผูกกับ `not allow_mara_barrier` อย่างเดียว ผลคือพอผนึกใหญ่แตก (ซึ่งเกิด
# แน่นอนในโลกที่เดินหลายร้อยปี) **ทุกการเดินทางในโลกจะสร้างกราฟ 755 สถานที่ใหม่ทั้งใบ** โปรไฟล์จริง:
# _adjacency ถูกเรียก 2,946 ครั้งจากการหาเส้นทาง 2,946 ครั้ง = ไม่เคย hit cache เลยสักครั้ง กิน 5%
# ของเวลาทั้งซิม และยิ่งแพงขึ้นเรื่อยๆ เมื่อมีประตูมิติเพิ่ม
_ADJ_OPEN: Optional[Dict[int, List[Tuple[int, float]]]] = None

# เหตุการณ์ระหว่างทาง — สุ่มเฉพาะตอนที่ TRAVEL_ENROUTE_EVENT_P ทอยติดแล้วเท่านั้น (ดู roll_enroute_event)
# จึงไม่มี "ปลอดภัย/ไม่มีอะไรเกิดขึ้น" ในตารางนี้ — การไม่ทอยติดคือกรณีปกติอยู่แล้ว
_ENROUTE_OUTCOMES: List[Tuple[str, float, Dict[str, int]]] = [
    ("พบของ", 0.35, {"mats": 1}),
    ("ถูกปล้น", 0.40, {"hp": -5}),
    ("บาดเจ็บ", 0.25, {"hp": -10}),
]


def _adjacency(allow_mara_barrier: bool = False) -> Dict[int, List[Tuple[int, float]]]:
    global _ADJ, _ADJ_OPEN
    if allow_mara_barrier:
        if _ADJ_OPEN is not None:
            return _ADJ_OPEN
    elif _ADJ is not None:
        return _ADJ
    adj: Dict[int, List[Tuple[int, float]]] = {}
    for edge in GEO.EDGES:
        a, b, dist = edge[0], edge[1], edge[2]
        etype = edge[3] if len(edge) > 3 else "road"
        traversable = edge[4] if len(edge) > 4 else True
        if not traversable:
            if allow_mara_barrier and etype == "sealed_barrier":
                traversable = True
            else:
                continue
        adj.setdefault(a, []).append((b, dist))
        adj.setdefault(b, []).append((a, dist))
    if allow_mara_barrier:
        _ADJ_OPEN = adj
    else:
        _ADJ = adj
    return adj


def shortest_path_distance(from_place: int, to_place: int, allow_mara_barrier: bool = False) -> Optional[float]:
    """Dijkstra บน tiandao/geo.py:EDGES — ระยะทางรวมสั้นสุด (หน่วยกราฟ) คืน None ถ้าไปไม่ถึงเลย (เช่น
    ข้าม world_key ที่ไม่มี gate เชื่อมกัน)"""
    if from_place == to_place:
        return 0.0
    adj = _adjacency(allow_mara_barrier=allow_mara_barrier)
    best: Dict[int, float] = {from_place: 0.0}
    pq: List[Tuple[float, int]] = [(0.0, from_place)]
    visited = set()
    while pq:
        d, node = heapq.heappop(pq)
        if node in visited:
            continue
        visited.add(node)
        if node == to_place:
            return d
        for neighbor, w in adj.get(node, ()):
            nd = d + w
            if neighbor not in best or nd < best[neighbor]:
                best[neighbor] = nd
                heapq.heappush(pq, (nd, neighbor))
    return None


_DIST_CACHE: Dict[int, Dict[int, float]] = {}


def distances_from(src: int, allow_mara_barrier: bool = False) -> Dict[int, float]:
    """ระยะทางจาก src ไปทุกจุดที่ไปถึงได้ — Dijkstra รอบเดียวแล้วแคชไว้ต่อ source

    ต่างจาก shortest_path_distance() ที่รัน Dijkstra ใหม่ทุกครั้งต่อคู่ (a, b) — ตัวนี้จำเป็นเมื่อ
    ต้องถามระยะจากคนหนึ่งไปหาคนอีกหลายร้อยคนทุก tick (ดู Sim.social_pool) มีสถานที่แค่ 182 จุด
    แคชจึงเต็มที่ 182 ชุด ไม่โต
    """
    if not allow_mara_barrier and src in _DIST_CACHE:
        return _DIST_CACHE[src]
    adj = _adjacency(allow_mara_barrier=allow_mara_barrier)
    best: Dict[int, float] = {src: 0.0}
    pq: List[Tuple[float, int]] = [(0.0, src)]
    visited = set()
    while pq:
        d, node = heapq.heappop(pq)
        if node in visited:
            continue
        visited.add(node)
        for neighbor, w in adj.get(node, ()):
            nd = d + w
            if neighbor not in best or nd < best[neighbor]:
                best[neighbor] = nd
                heapq.heappush(pq, (nd, neighbor))
    if not allow_mara_barrier:
        _DIST_CACHE[src] = best
    return best


def travel_speed(realm: int, config=None) -> float:
    """ระยะทาง (หน่วยกราฟ) ที่เดินได้ต่อวัน — ยิ่ง realm สูงยิ่งเร็ว (เชิงเส้นตาม TRAVEL_REALM_SPEEDUP)"""
    cfg = config or C
    return cfg.TRAVEL_BASE_SPEED * (1.0 + cfg.TRAVEL_REALM_SPEEDUP * max(0, realm))


def shortest_path_days(from_place: int, to_place: int, realm: int, config=None, allow_mara_barrier: bool = False) -> Optional[int]:
    """ระยะทางสั้นสุดแปลงเป็นจำนวนวันเดินทางจริง (ปัดขึ้นอย่างน้อย TRAVEL_MIN_DAYS) — คืน None ถ้าไปไม่ถึง
    (ผู้เรียกต้องจัดการกรณีนี้เอง เช่น fallback ไม่เดินทาง)"""
    cfg = config or C
    dist = shortest_path_distance(from_place, to_place, allow_mara_barrier=allow_mara_barrier)
    if dist is None:
        return None
    if dist == 0.0:
        return 0
    days = dist / travel_speed(realm, cfg)
    return max(cfg.TRAVEL_MIN_DAYS, round(days))


def roll_enroute_event(rng, config=None) -> Optional[Tuple[str, Dict[str, int]]]:
    """ทอยว่าจะเจอเหตุการณ์ระหว่างทางไหม (เรียกจาก sim.py ทุกครั้งที่ตัวละครที่กำลังเดินทางตื่นมาเช็ค
    ระหว่างทาง — ดู config.TRAVEL_ENROUTE_CHECK_DAYS) — ใช้ rng ที่รับมา (ไม่ใช่ random กลาง เพื่อ
    determinism ตามที่ทั้งโปรเจกต์ยึดถือ) คืน None ถ้าไม่เจออะไร (กรณีปกติ) หรือ (outcome, deltas) ถ้าเจอ"""
    cfg = config or C
    if rng.random() > cfg.TRAVEL_ENROUTE_EVENT_P:
        return None
    r, acc = rng.random(), 0.0
    for outcome, p, deltas in _ENROUTE_OUTCOMES:
        acc += p
        if r <= acc:
            return outcome, deltas
    return None
