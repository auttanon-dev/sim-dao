# -*- coding: utf-8 -*-
"""Watabou-Style Procedural Settlement & Virtual Village/City Generator.

Generates deterministic, beautiful vector layouts (Wards, Road Skeletons, Building Parcels,
City Walls, Waterways, and Living Character Occupants) for all 182 places in Sim Dao.
"""
import math
import random
from functools import lru_cache
from typing import Dict, List, Any, Optional, Tuple

from . import places as PL
from . import config as C

# Cultural styling configurations for settlement generation
CULTURAL_PALETTES = {
    "abyss": {
        "wall_type": "stone_castle",
        "wall_color": "#2b2b33",
        "roof_colors": ["#1b1b22", "#3a2a3f", "#4a2c2a", "#6d597a"],
        "accent_color": "#9d4edd",
        "water_color": "#5a1e1e",
        "ground_color": "#17161c",
        "tree_color": "#3d405b",
        "special_buildings": ["ตำหนักยมบาล", "โรงหลอมกระดูก", "ท่าน้ำสุราลืมชาติ", "หอคอยมองบ้านเกิด"],
    },
    "ocean": {
        "wall_type": "moat_and_wood",
        "wall_color": "#1b6b7a",
        "roof_colors": ["#00b4d8", "#0077b6", "#48cae4", "#90e0ef"],
        "accent_color": "#ffd6a5",
        "water_color": "#023e8a",
        "ground_color": "#0b2b3a",
        "tree_color": "#2a9d8f",
        "special_buildings": ["ท้องพระโรงมังกร", "ตลาดไข่มุกเงือก", "อู่ต่อเรือปะการัง", "หอสังข์เรียกคลื่น"],
    },
    "siam": {
        "wall_type": "moat_and_wood",
        "wall_color": "#8d6e63",
        "roof_colors": ["#d4af37", "#b08968", "#795548", "#e07a5f"],
        "accent_color": "#ffd166",
        "water_color": "#48cae4",
        "ground_color": "#2c2820",
        "tree_color": "#38b000",
        "special_buildings": ["ค่ายมวยไทยปฐพีเพลิง", "โรงช้างศึกหลวง", "อารามสถูปทองคำ", "เรือนแพตลาดน้ำ"],
    },
    "fusang": {
        "wall_type": "stone_castle",
        "wall_color": "#495057",
        "roof_colors": ["#212529", "#343a40", "#6c757d", "#c77dff"],
        "accent_color": "#e63946",
        "water_color": "#0077b6",
        "ground_color": "#1e2229",
        "tree_color": "#ff70a6",  # ซากุระชมพู
        "special_buildings": ["ปราสาทไดเมียว", "สำนักดาบอิไอ", "ศาลเจ้าเสาโทริอิ", "หอองเมียวจิ"],
    },
    "steppe": {
        "wall_type": "wood_palisade",
        "wall_color": "#6c584c",
        "roof_colors": ["#f8f9fa", "#e9ecef", "#dee2e6", "#dda15e"],
        "accent_color": "#2a9d8f",
        "water_color": "#90e0ef",
        "ground_color": "#333d29",
        "tree_color": "#606c38",
        "special_buildings": ["กระโจมทองคำข่าน", "ลานยิงธนูหลังม้า", "วิหารเสาโอโวเต็งกรี", "คอกม้าศึกพายุ"],
    },
    "oasis": {
        "wall_type": "adobe_sandstone",
        "wall_color": "#b08968",
        "roof_colors": ["#e9c46a", "#f4a261", "#e76f51", "#2a9d8f"],
        "accent_color": "#e76f51",
        "water_color": "#52b788",
        "ground_color": "#3d312a",
        "tree_color": "#2d6a4f",  # อินทผาลัม
        "special_buildings": ["หออภิมหาเวทแปรธาตุ", "หอดูดาวดวงดารา", "ตลาดบาซาร์เครื่องเทศ", "วังสุลต่านโอเอซิส"],
    },
    "bharata": {
        "wall_type": "carved_redstone",
        "wall_color": "#9c6644",
        "roof_colors": ["#e76f51", "#f4a261", "#e9c46a", "#c77dff"],
        "accent_color": "#ffb703",
        "water_color": "#48cae4",
        "ground_color": "#2b2620",
        "tree_color": "#40916c",
        "special_buildings": ["มหาวิหารนาลันทา", "ท่าน้ำบันไดหินคงคา (Ghat)", "สำนักโยคะกายเพชร", "สระบงกชสหัสวรรษ"],
    },
    1: {  # แดนเซียน
        "wall_type": "jade_floating_barrier",
        "wall_color": "#caf0f8",
        "roof_colors": ["#90e0ef", "#00b4d8", "#0077b6", "#caf0f8"],
        "accent_color": "#ffd166",
        "water_color": "#90e0ef",
        "ground_color": "#172554",
        "tree_color": "#48cae4",  # ต้นไม้เซียนประกายฟ้า
        "special_buildings": ["วังโอสถสวรรค์", "หอประมูลเซียนลอยฟ้า", "แท่นรับทัณฑ์อัสนี", "น้ำตกสวรรค์เก้าชั้น"],
    },
    "mara": {  # แดนมาร
        "wall_type": "obsidian_spikes",
        "wall_color": "#212529",
        "roof_colors": ["#540b0e", "#9e2a2b", "#333533", "#e63946"],
        "accent_color": "#e63946",
        "water_color": "#9b2226",  # ลาวา/บึงโลหิต
        "ground_color": "#1b1918",
        "tree_color": "#3f1d24",
        "special_buildings": ["พระราชวังทมิฬนิรันดร์", "แท่นพิพากษาลิขิตมาร", "เตาหลอมกลืนจิต", "ค่ายทหารมารกระดูก"],
    },
    0: {  # โลกมนุษย์ (จงหยวน)
        "wall_type": "stone_brick_wall",
        "wall_color": "#5c677d",
        "roof_colors": ["#33415c", "#7d8597", "#b56576", "#d4af37"],
        "accent_color": "#d4af37",
        "water_color": "#48cae4",
        "ground_color": "#212529",
        "tree_color": "#2d6a4f",
        "special_buildings": ["จวนเจ้าเมือง", "สำนักกระบี่หลวง", "หอประมูลรุ่งอรุณ", "โรงเตี๊ยมสยบพยัคฆ์"],
    }
}


def _pseudo_rand(seed: int, idx: int) -> float:
    """Deterministic pseudo-random float [0.0, 1.0] from seed and index."""
    n = math.sin(seed * 12.9898 + idx * 78.233) * 43758.5453
    return n - math.floor(n)


def _settlement_sizing(ptype: str, grade: int) -> Tuple[float, int, int, bool]:
    """ขนาด/จำนวนวอร์ดและอาคารตามประเภทและระดับชั้นสถานที่ — จุดเดียวที่กำหนดค่านี้ ใช้ร่วมกันทั้ง
    get_building_skeleton (เอนจินซิม) และ generate_settlement_layout (เรนเดอร์เต็ม) กันไม่ให้เพี้ยนกัน"""
    if ptype == "เมือง":
        return 280.0 + grade * 60.0, 6 + grade * 2, 7 + grade * 3, True
    elif ptype == "สำนัก":
        return 240.0 + grade * 40.0, 4 + grade, 5 + grade * 2, True
    elif ptype == "ตลาด":
        return 220.0 + grade * 30.0, 4, 6, False
    elif ptype == "ด่านชายแดน" or ptype == "ประตูมิติ":
        return 180.0, 3, 4, True
    else:  # ลานฝึก / แหล่งวัตถุดิบ / แดนลับ
        return 160.0, 3, 3, False


def _building_type_for_ward(ward_id: int) -> str:
    if ward_id == 1:
        return "market"
    elif ward_id == 2:
        return "dojo"
    elif ward_id == 3:
        return "craft"
    elif ward_id == 5:
        return "temple"
    return "house"


@lru_cache(maxsize=256)
def get_building_skeleton(place_idx: int) -> Tuple[Dict[str, Any], ...]:
    """รายการอาคารแบบเบา (id/type/ward_id/b_i เท่านั้น ไม่มีเรขาคณิต) ของสถานที่หนึ่งๆ — deterministic
    เต็มที่ (ผูกกับ place_idx เท่านั้น) ใช้ทั้งฝั่งเรนเดอร์ผังเมืองเต็ม (generate_settlement_layout) และฝั่ง
    เอนจินซิม (Sim.route_to_building) ให้ตรงกันเป๊ะเสมอ — ห้ามคำนวณรายการอาคารซ้ำที่อื่น"""
    if place_idx < 0 or place_idx >= len(PL.PLACES):
        place_idx = 0
    _, _, grade, ptype, _, _, _, _ = PL.PLACES[place_idx]
    _, n_districts, n_buildings_per_ward, _ = _settlement_sizing(ptype, grade)

    buildings: List[Dict[str, Any]] = [{"id": 0, "type": "citadel", "ward_id": 0, "b_i": -1}]
    b_id = 1
    for ward_id in range(n_districts):
        for b_i in range(n_buildings_per_ward):
            buildings.append({"id": b_id, "type": _building_type_for_ward(ward_id),
                               "ward_id": ward_id, "b_i": b_i})
            b_id += 1
    return tuple(buildings)


def find_building_of_type(place_idx: int, types: Tuple[str, ...]) -> Optional[int]:
    """หาอาคารแรกที่ตรงกับประเภทที่ต้องการในสถานที่นี้ (deterministic) — คืน None ถ้าไม่มีอาคารประเภทนั้นเลย"""
    for b in get_building_skeleton(place_idx):
        if b["type"] in types:
            return b["id"]
    return None


@lru_cache(maxsize=256)
def _building_type_by_id(place_idx: int) -> Dict[int, str]:
    return {b["id"]: b["type"] for b in get_building_skeleton(place_idx)}


def building_type_of(place_idx: int, building_id: int) -> Optional[str]:
    """หาประเภทของอาคาร id นี้แบบ O(1) — ใช้เช็ค "อยู่อาคารที่ต้องการอยู่แล้วหรือยัง" ที่ถูกเรียกทุกครั้ง
    ที่มีการพยายามหลอมยา/ฝึกวิชา/ค้าขาย (บ่อยกว่า find_building_of_type ที่เรียกแค่ตอนต้องเดินใหม่)"""
    return _building_type_by_id(place_idx).get(building_id)


def generate_settlement_layout(place_idx: int, sim=None) -> Dict[str, Any]:
    """สร้างโครงสร้างผังเมืองเสมือนจริง (Watabou Procedural Settlement) สำหรับสถานที่ใดๆ"""
    if place_idx < 0 or place_idx >= len(PL.PLACES):
        place_idx = 0
    p = PL.PLACES[place_idx]
    name, world_key, grade, ptype, res, furn, sec_parent, is_sealed = p

    palette = CULTURAL_PALETTES.get(world_key, CULTURAL_PALETTES[0])
    seed = place_idx * 1009 + grade * 37 + len(name)

    radius, n_districts, n_buildings_per_ward, has_walls = _settlement_sizing(ptype, grade)

    # 1. Generate City Center and Wards (Districts)
    wards = []
    ward_names_pool = [
        "ย่านปราสาท/ตำหนักหลัก (Citadel)",
        "ย่านตลาดการค้าและโอสถ (Market Bazaar)",
        "ย่านโรงฝึกยุทธ์และลานประลอง (Martial Dojo)",
        "ย่านช่างตีเหล็กและหลอมศาสตรา (Smiths & Alchemy)",
        "ย่านเรือนพักผู้บำเพ็ญ (Residential Quarters)",
        "ย่านอารามและหอคัมภีร์ (Sanctum Library)",
        "ย่านท่าน้ำและสะพานข้ามภพ (Docks & Gates)",
        "ย่านสวนสมุนไพรและถ้ำกักตน (Seclusion Groves)"
    ]
    
    for d in range(n_districts):
        angle = (d / n_districts) * 2 * math.pi + _pseudo_rand(seed, d * 3) * 0.4
        dist = (_pseudo_rand(seed, d * 7 + 1) * 0.5 + 0.35) * radius
        wx = dist * math.cos(angle)
        wy = dist * math.sin(angle)
        w_radius = 45.0 + _pseudo_rand(seed, d * 11) * 30.0
        w_name = ward_names_pool[d % len(ward_names_pool)]
        wards.append({
            "id": d,
            "name": w_name,
            "x": round(wx, 1),
            "y": round(wy, 1),
            "radius": round(w_radius, 1)
        })

    # 2. Generate Road Skeleton (Main Avenues + Alleys)
    roads = []
    # Main ring road
    ring_points = []
    n_ring_pts = 12
    for r_i in range(n_ring_pts):
        ang = (r_i / n_ring_pts) * 2 * math.pi
        r_dist = radius * (0.8 + _pseudo_rand(seed, r_i * 13) * 0.1)
        ring_points.append((round(r_dist * math.cos(ang), 1), round(r_dist * math.sin(ang), 1)))
    ring_points.append(ring_points[0])
    roads.append({"name": "ถนนวงแหวนรอบนอก", "type": "main", "points": ring_points})

    # Radial arterial roads from center (0,0) to gates
    n_gates = 4 if has_walls else 3
    gates = []
    for g_i in range(n_gates):
        g_ang = (g_i / n_gates) * 2 * math.pi + 0.3
        gx = round(radius * 0.85 * math.cos(g_ang), 1)
        gy = round(radius * 0.85 * math.sin(g_ang), 1)
        gates.append({"id": g_i, "name": f"ประตูนครทิศที่ {g_i+1}", "x": gx, "y": gy})
        roads.append({"name": f"ถนนใหญ่สู่ประตู {g_i+1}", "type": "main", "points": [(0.0, 0.0), (gx, gy)]})

    # Connect wards to nearest road
    for w in wards:
        roads.append({
            "name": f"ตรอกเชื่อม {w['name']}",
            "type": "alley",
            "points": [(0.0, 0.0), (w["x"], w["y"])]
        })

    # 3. Generate Building Parcels — id/type/ward_id มาจาก get_building_skeleton (จุดเดียวที่กำหนด
    # รายชื่ออาคาร ใช้ร่วมกับเอนจินซิมด้วย) ที่นี่เติมแค่เรขาคณิต/ชื่อ/สีสำหรับเรนเดอร์
    building_name_pool = {
        "market": "ร้านค้าโอสถและวัตถุดิบ",
        "dojo": "ลานประลองยุทธ์",
        "craft": "เตาหลอมศาสตรา",
        "temple": "หอคัมภีร์และสมาธิ",
        "house": "เรือนพักผู้บำเพ็ญ",
    }
    special_names = palette["special_buildings"]
    wards_by_id = {w["id"]: w for w in wards}
    buildings = []

    for sk in get_building_skeleton(place_idx):
        b_id = sk["id"]
        if sk["type"] == "citadel":
            central_name = special_names[0] if special_names else "ตำหนักใหญ่"
            buildings.append({
                "id": b_id,
                "name": central_name,
                "type": "citadel",
                "x": 0.0,
                "y": 0.0,
                "width": 46.0,
                "height": 46.0,
                "rotation": 0.0,
                "roof_color": palette["roof_colors"][0],
                "ward_id": 0,
                "capacity": 10,
                "occupants": []
            })
            continue

        w = wards_by_id[sk["ward_id"]]
        b_seed = seed + w["id"] * 100 + sk["b_i"] * 17
        b_ang = _pseudo_rand(b_seed, 1) * 2 * math.pi
        b_dist = _pseudo_rand(b_seed, 2) * (w["radius"] * 0.75) + 12.0
        bx = round(w["x"] + b_dist * math.cos(b_ang), 1)
        by = round(w["y"] + b_dist * math.sin(b_ang), 1)

        b_w = round(16.0 + _pseudo_rand(b_seed, 3) * 14.0, 1)
        b_h = round(14.0 + _pseudo_rand(b_seed, 4) * 12.0, 1)
        rot = round(_pseudo_rand(b_seed, 5) * math.pi, 2)

        b_name = f"{building_name_pool[sk['type']]} #{b_id}"
        roof_col = palette["roof_colors"][b_id % len(palette["roof_colors"])]

        buildings.append({
            "id": b_id,
            "name": b_name,
            "type": sk["type"],
            "x": bx,
            "y": by,
            "width": b_w,
            "height": b_h,
            "rotation": rot,
            "roof_color": roof_col,
            "ward_id": w["id"],
            "capacity": 4,
            "occupants": []
        })

    # 4. Populate with Living Cultivators (if Sim instance provided)
    if sim is not None:
        living = [c for c in sim.living() if getattr(c, "place", -1) == place_idx]
        for c_idx, c in enumerate(living):
            # ใช้อาคารจริงที่เอนจิน route ไปแล้ว (Sim.route_to_building) ถ้ามี — สุ่มแบบเดิมเฉพาะตัวละคร
            # ที่ยังไม่เคยถูก route ไปอาคารเฉพาะเจาะจง (building == -1)
            real_b_id = getattr(c, "building", -1)
            if getattr(c, "is_lord", False):
                target_b_idx = 0
            elif real_b_id >= 0 and any(b["id"] == real_b_id for b in buildings):
                target_b_idx = next(i for i, b in enumerate(buildings) if b["id"] == real_b_id)
            else:
                target_b_idx = c_idx % len(buildings)
            b_target = buildings[target_b_idx]
            
            c_info = {
                "cid": c.cid,
                "name": c.name,
                "realm": c.realm,
                "realm_name": c.realm_name(),
                "dao": getattr(c, "dao", "วิถีทั่วไป"),
                "is_lord": getattr(c, "is_lord", False),
                "current_building_id": b_target["id"],
                "routine_action": "ฝึกปราณในเรือนพัก" if b_target["type"] == "house" else "แลกเปลี่ยนสมบัติในตลาด" if b_target["type"] == "market" else "ประลองวิชา" if b_target["type"] == "dojo" else "หลอมยาและศาสตรา",
                "x": b_target["x"] + _pseudo_rand(c.cid, 1) * 10.0 - 5.0,
                "y": b_target["y"] + _pseudo_rand(c.cid, 2) * 10.0 - 5.0
            }
            b_target["occupants"].append(c_info)

    # 5. City Walls & Waterways
    city_wall = None
    if has_walls:
        wall_pts = []
        n_wall_pts = 16
        for w_i in range(n_wall_pts):
            w_ang = (w_i / n_wall_pts) * 2 * math.pi
            w_r = radius * (0.92 + _pseudo_rand(seed, w_i * 19) * 0.08)
            wall_pts.append((round(w_r * math.cos(w_ang), 1), round(w_r * math.sin(w_ang), 1)))
        wall_pts.append(wall_pts[0])
        city_wall = {
            "type": palette["wall_type"],
            "color": palette["wall_color"],
            "points": wall_pts,
            "gates": gates
        }

    return {
        "place_idx": place_idx,
        "name": name,
        "realm_key": world_key,
        "type": ptype,
        "grade": grade,
        "radius": radius,
        "palette": palette,
        "wards": wards,
        "roads": roads,
        "buildings": buildings,
        "city_wall": city_wall,
        "total_buildings": len(buildings),
        "total_occupants": sum(len(b["occupants"]) for b in buildings)
    }
