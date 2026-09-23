# -*- coding: utf-8 -*-
"""Tiandao Procedural Terrain Engine — Mapgen4-style Heightmap, Biomes, and Rivers.

Provides procedural heightmaps, floating sky islands, desert dunes, rivers, 
and biome shading for all 10 realms (Mortal, 5 Sister Realms, Immortal, Heaven, Mara, Chaos).
"""
import functools
import math
import random
from typing import Dict, List, Any, Tuple

from . import config as C
from . import noise as NZ
from . import places as PL
from . import geo as GEO

# Biome definitions with thematic colors and properties
BIOMES = {
    "deep_ocean": {"name": "มหาสมุทรลึก", "color": "#0d1b2a", "type": "water"},
    "shallow_water": {"name": "น่านน้ำชายฝั่ง", "color": "#1b4965", "type": "water"},
    "beach": {"name": "หาดทรายชายฝั่ง", "color": "#e0c097", "type": "land"},
    "plains": {"name": "ที่ราบลุ่มเขียวขจี", "color": "#588157", "type": "land"},
    "forest": {"name": "ป่าไม้อุดมสมบูรณ์", "color": "#3a5a40", "type": "land"},
    "rainforest_himavanta": {"name": "ป่าดงดิบหิมพานต์", "color": "#2d6a4f", "type": "land"},
    "sakura_valley": {"name": "หุบเขาซากุระพันปี", "color": "#c77dff", "type": "land"},
    "steppe_grassland": {"name": "ทุ่งหญ้าสเตปป์หมื่นลี้", "color": "#709775", "type": "land"},
    "yellow_desert": {"name": "ทะเลทรายทรายเหลือง", "color": "#d4a373", "type": "land"},
    "oasis_emerald": {"name": "โอเอซิสมรกต", "color": "#52b788", "type": "land"},
    "sacred_ganga_basin": {"name": "ลุ่มน้ำคงคาสวรรค์", "color": "#74c69d", "type": "land"},
    "high_hills": {"name": "เนินเขาสูง", "color": "#8c7851", "type": "land"},
    "mountains": {"name": "เทือกเขาหินผา", "color": "#6c757d", "type": "mountain"},
    "snow_peaks": {"name": "ยอดเขาหิมะนิรันดร์", "color": "#e9ecef", "type": "mountain"},
    "floating_sky_island": {"name": "เกาะสวรรค์ลอยฟ้า", "color": "#90e0ef", "type": "sky"},
    "floating_jade_crag": {"name": "เกาะศิลาหยกเซียนลอยฟ้า", "color": "#caf0f8", "type": "sky"},
    "volcanic_crag": {"name": "เทือกเขาภูเขาไฟมาร", "color": "#3f1d24", "type": "mara"},
    "ash_wastes": {"name": "ทุ่งเถ้าถ่านทมิฬ", "color": "#2b2d42", "type": "mara"},
    "blood_swamp": {"name": "บึงมารโลหิต", "color": "#540b0e", "type": "mara"},
    "cosmic_void_shard": {"name": "เศษอุกกาบาตห้วงอวกาศ", "color": "#240046", "type": "chaos"},
    "chaos_nebula": {"name": "เนบิวลามิติมืด", "color": "#10002b", "type": "chaos"},
}

REALM_PROPERTIES = {
    0: {
        "name": "โลกมนุษย์ (Mortal Realm)",
        "theme": "mortal",
        "center": (0.0, 0.0),
        "base_z": 0.0,
        "is_floating": False,
        "desc": "ดินแดนจงหยวนตอนกลาง ทวีปหลักอันอุดมสมบูรณ์และมีเทือกเขากระบี่สูงตระหง่าน",
    },
    "siam": {
        "name": "แดนสยาม (Siam)",
        "theme": "tropical_wetlands",
        "center": (-180.0, -120.0),
        "base_z": 5.0,
        "is_floating": False,
        "desc": "ดินแดนลุ่มน้ำเจ้าพระยา ป่าหิมพานต์เขียวชอุ่ม และทุ่งนาข้าวสีทอง",
    },
    "fusang": {
        "name": "แดนอาทิตย์อุทัย (Fusang)",
        "theme": "volcanic_islands",
        "center": (200.0, -40.0),
        "base_z": 8.0,
        "is_floating": False,
        "desc": "หมู่เกาะซากุระ ภูเขาไฟฟูจิ และศาลเจ้าเสาโทริอิกลางมหาสมุทร",
    },
    "steppe": {
        "name": "แดนทุ่งหญ้าคีตาวายุ (Steppe)",
        "theme": "highland_steppe",
        "center": (-20.0, 220.0),
        "base_z": 35.0,
        "is_floating": False,
        "desc": "ทุ่งหญ้าสเตปป์กว้างใหญ่จรดเส้นขอบฟ้าและเทือกเขาหิมะหลังคาโลก",
    },
    "oasis": {
        "name": "แดนโอเอซิสพันราตรี (Oasis)",
        "theme": "desert_oasis",
        "center": (-240.0, 40.0),
        "base_z": 10.0,
        "is_floating": False,
        "desc": "ผืนทะเลทรายสีทองอร่าม สลับกับเมืองโอเอซิสมรกตและหอดูดาวดวงดารา",
    },
    "bharata": {
        "name": "แดนชมพูทวีป (Bharata)",
        "theme": "sacred_vedic",
        "center": (-40.0, -220.0),
        "base_z": 15.0,
        "is_floating": False,
        "desc": "ดินแดนลุ่มน้ำคงคาสวรรค์ มหาวิหารนาลันทา และเทือกเขาหิมาลัยศักดิ์สิทธิ์",
    },
    1: {
        "name": "แดนเซียน (Immortal Realm)",
        "theme": "floating_sky",
        "center": (350.0, 180.0),
        "base_z": 200.0,
        "is_floating": True,
        "desc": "หมู่เกาะศิลาหยกและตำหนักเซียนลอยอยู่เหนือชั้นเมฆา พร้อมน้ำตกสวรรค์",
    },
    2: {
        "name": "สวรรค์นอกชั้นฟ้า (Beyond Heaven)",
        "theme": "high_celestial",
        "center": (650.0, 320.0),
        "base_z": 450.0,
        "is_floating": True,
        "desc": "ดินแดนชั้นสูงสุด ขอบจักรวาลดวงดาวและประตูมิติทะยานฟ้า",
    },
    "mara": {
        "name": "แดนมาร (Mara Realm)",
        "theme": "volcanic_abyss",
        "center": (240.0, -260.0),
        "base_z": -60.0,
        "is_floating": False,
        "desc": "หุบเหวลาวาเดือด หินออบซิเดียนทมิฬ บึงมารโลหิต และมหาผนึกสะกดหมื่นมาร",
    },
    "chaos": {
        "name": "ที่กบดานเผ่าโกลาหล (Chaos Realm)",
        "theme": "cosmic_void",
        "center": (520.0, -120.0),
        "base_z": 300.0,
        "is_floating": True,
        "desc": "ห้วงลึกอวกาศมืดมิด เศษซากอุกกาบาตลอยคว้าง และรูหนอนมิติบิดเบี้ยว",
    },
}


# เมล็ดของภูมิประเทศ — ต้องเป็นตัวเดียวกับ seed ของโลก ไม่ใช่ 42 ที่ฝังไว้
# ของเดิม `_noise_2d` เป็นผลบวกของไซน์สามตัวที่ seed เข้าไป **ในเฟส** (`sin(x + seed*1.7)`)
# ซึ่งไม่ได้เปลี่ยนสนาม มันเลื่อนสนามเดิม โลกทุกใบจึงมีภูเขาชุดเดียวกันแค่ขยับที่
# และที่เรียกใช้ก็ส่ง seed=42 คงที่ ไม่เคยรับ seed ของโลกเลย
_WORLD_SEED = 0


def use_seed(seed: int) -> None:
    """ผูกภูมิประเทศกับ seed ของโลกหนึ่ง — เรียกก่อนวาดแผนที่

    เป็น state ระดับโมดูลเหมือน PLACES/GEO ที่มีอยู่แล้ว จึงรองรับได้ทีละโลก
    ยอมรับข้อจำกัดนี้เพราะชั้นนี้เป็นชั้นแสดงผล (dashboard/godview) ไม่มีใครในเอนจินเรียก
    ถ้าวันหนึ่งต้องวาดสองโลกพร้อมกัน ต้องเปลี่ยนเป็นส่งสนามเข้ามาเป็นพารามิเตอร์
    """
    global _WORLD_SEED
    _WORLD_SEED = int(seed)
    _planet.cache_clear()
    _layer.cache_clear()


@functools.lru_cache(maxsize=8)
def _planet(seed: int):
    """ดาวดวงเดียวกับที่เอนจินใช้ — ภูเขาที่วาดออกมาคือที่ที่ปราณโผล่จริง ไม่ใช่ภาพประดับ"""
    return NZ.Planet(seed=seed ^ 0x91F1_0000, radius=C.PLANET_RADIUS,
                     amp=C.PLANET_AMP, lam=C.PLANET_LAMBDA,
                     octaves=C.PLANET_OCTAVES,
                     warp_octaves=C.PLANET_WARP_OCTAVES)


@functools.lru_cache(maxsize=8)
def _layer(seed: int, channel: int):
    """สนามเสริมสำหรับชั้นอื่นที่ไม่ใช่ความสูง (เช่น ความชุ่มชื้น)"""
    return NZ.Planet(seed=(seed * 8191 + channel) ^ 0x7E44_1A17,
                     lam=C.PLANET_LAMBDA, octaves=4, warp_octaves=2)


def _noise_2d(x: float, y: float, seed: int = 0) -> float:
    """F(p̂ + λW(p̂)) ที่พิกัดแผนที่นี้ คืน 0..1

    `seed` เป็นตัวแยกชั้น (0 = ความสูงจากดาวจริง · อื่นๆ = สนามเสริม) ไม่ใช่เมล็ดของโลก
    เมล็ดของโลกมาจาก use_seed() ชั้นความสูงกับชั้นความชุ่มชื้นจึงเป็นสนามคนละผืน
    ไม่มีทางเหมือนกันเป๊ะโดยบังเอิญ (บั๊กที่การเลื่อนเฟสของโค้ดเดิมเสี่ยงจะเจอ)
    """
    d = NZ.sphere_dir(x, y, C.PLANET_SPAN)
    pl = _planet(_WORLD_SEED) if int(seed) == 0 else _layer(_WORLD_SEED, int(seed))
    return 0.5 + 0.5 * pl.height(*d, scale=C.PLANET_SCALE)


TERRAIN_OCTAVES = 5       # เก็บไว้เพื่อความเข้ากันได้ย้อนหลัง — ตอนนี้ชั้นมาจาก config.PLANET_*
TERRAIN_RELIEF = 22.0     # ความสูงต่ำของพื้นที่ภูมิประเทศเพิ่มเข้าไป (±หน่วย) — พอจะข้ามเกณฑ์
                          # ไบโอมที่ 30 กับ 50 ได้ แต่ไม่มากพอจะทำให้เมืองไปโผล่เหนือสำนัก


def compute_place_3d_and_biome(place_idx: int) -> Tuple[float, float, float, str, str]:
    """คำนวณพิกัด 3D (x, y, z) และ Biome สำหรับสถานที่หนึ่งๆ"""
    p = PL.PLACES[place_idx]
    name, world_key, grade, ptype, res, furn, sec_parent, is_sealed = p
    x, y = GEO.COORDS[place_idx]
    
    realm_info = REALM_PROPERTIES.get(world_key, REALM_PROPERTIES[0])
    base_z = realm_info["base_z"]
    theme = realm_info["theme"]
    
    # คำนวณความสูงตามประเภทสถานที่
    # ใช้พิกัดจริงเป็นตัวเข้า ไม่ใช่ place_idx — เพื่อนบ้านบนแผนที่ต้องได้พื้นที่สูงใกล้กัน
    # ของเดิมส่ง seed=100+place_idx ทำให้สถานที่ที่ติดกันได้สนามคนละผืน ภูมิประเทศจึงกระโดด
    # ระหว่างจุดที่อยู่ข้างกัน ซึ่งขัดกับความเป็นภูมิประเทศ
    local_elev = _noise_2d(x, y)
    z_offset = local_elev * 25.0
    
    if ptype == "เมือง":
        z_offset = 5.0 + grade * 3.0
    elif ptype == "สำนัก":
        z_offset = 25.0 + grade * 12.0  # สำนักมักอยู่บนภูเขาสูงหรือหน้าผา
    elif ptype == "ลานฝึก":
        z_offset = 8.0 + grade * 4.0
    elif ptype == "ด่านชายแดน":
        z_offset = 6.0
    elif ptype == "ประตูมิติ":
        z_offset = 20.0
    elif ptype == "แดนลับ":
        if is_sealed:
            z_offset = -15.0  # รอยแยกลึกลงไปใต้ดิน
        else:
            z_offset = 35.0 + grade * 15.0

    # ความสูงตามประเภทข้างบนคือ "สำนักอยู่บนเขา เมืองอยู่ที่ราบ" ซึ่งเป็นเจตนาของผู้เขียน
    # แต่ของเดิมเขียนทับ local_elev ทิ้งทั้งก้อน ค่า noise ที่คำนวณมาจึงไม่เคยถูกใช้เลย
    # ทุกโลกได้ความสูงชุดเดียวกันเป๊ะ ตอนนี้บวกภูมิประเทศจริงเข้าไปเป็น **ความสูงต่ำของพื้น**
    # ที่ประเภทนั้นไปตั้งอยู่บน — สำนักยังอยู่สูงกว่าเมืองเสมอ แต่สำนักบนสันเขาในเมล็ดหนึ่ง
    # อาจอยู่บนเนินเตี้ยในอีกเมล็ดหนึ่ง ซึ่งพลิกเกณฑ์ไบโอม (z >= 30 -> ภูเขา, z >= 50 -> หิมะ)
    # ให้เป็นคนละแผนที่โดยไม่ต้องแตะชื่อสถานที่ที่เขียนไว้เลยสักตัว
    z_offset += (local_elev - 0.5) * 2.0 * TERRAIN_RELIEF

    z = round(base_z + z_offset, 2)
    
    # ระบุ Biome ตาม Theme และข้อมูลสถานที่
    biome_key = "plains"
    if theme == "floating_sky" or realm_info["is_floating"]:
        if world_key == "chaos":
            biome_key = "cosmic_void_shard" if ptype != "แดนลับ" else "chaos_nebula"
        else:
            biome_key = "floating_sky_island" if grade >= 1 else "floating_jade_crag"
    elif theme == "volcanic_abyss":
        if "โลหิต" in name or res == "แก่นพลัง":
            biome_key = "blood_swamp"
        elif "ภูเขาไฟ" in name or res == "แร่":
            biome_key = "volcanic_crag"
        else:
            biome_key = "ash_wastes"
    elif theme == "tropical_wetlands":
        if "หิมพานต์" in name or res == "สมุนไพร":
            biome_key = "rainforest_himavanta"
        elif "แม่น้ำ" in name or "น้ำ" in name:
            biome_key = "shallow_water"
        else:
            biome_key = "plains"
    elif theme == "volcanic_islands":
        if "ฟูจิ" in name or "ภูเขาไฟ" in name:
            biome_key = "volcanic_crag"
        elif "ซากุระ" in name or res == "สมุนไพร":
            biome_key = "sakura_valley"
        elif "ท่าเรือ" in name or "สมุทร" in name:
            biome_key = "shallow_water"
        else:
            biome_key = "forest"
    elif theme == "highland_steppe":
        if "หิมะ" in name or "หลังคาโลก" in name or z >= 50.0:
            biome_key = "snow_peaks"
        else:
            biome_key = "steppe_grassland"
    elif theme == "desert_oasis":
        if "โอเอซิส" in name or "มรกต" in name or res == "สมุนไพร":
            biome_key = "oasis_emerald"
        else:
            biome_key = "yellow_desert"
    elif theme == "sacred_vedic":
        if "คงคา" in name or "ลำน้ำ" in name:
            biome_key = "sacred_ganga_basin"
        elif "หิมาลัย" in name or "สุเมรุ" in name:
            biome_key = "snow_peaks"
        else:
            biome_key = "forest"
    else:  # Mortal
        if "ทรายเหลือง" in name:
            biome_key = "yellow_desert"
        elif "กระบี่สวรรค์" in name or z >= 30.0:
            biome_key = "mountains"
        elif "แม่น้ำ" in name or "ท่า" in name:
            biome_key = "shallow_water"
        elif res == "สมุนไพร":
            biome_key = "forest"
        else:
            # ที่ที่ผู้เขียนไม่ได้ระบุไว้ — ให้ **ความชุ่มชื้น** จากสนามอีกผืนตัดสิน
            # ใช้สนามคนละชั้น (seed=2) ไม่ใช่ชั้นความสูง ไม่งั้นที่สูงจะชื้นตามกันหมด
            # ซึ่งผิดทั้งทางภูมิศาสตร์และทำให้แผนที่อ่านซ้ำซาก
            wet = _noise_2d(x, y, seed=2)
            biome_key = ("high_hills" if wet < 0.4 else
                         "plains" if wet < 0.62 else "forest")

    biome_name = BIOMES[biome_key]["name"]
    return x, y, z, biome_key, biome_name


def generate_terrain_mesh(grid_size: int = 40) -> Dict[str, Any]:
    """สร้าง Grid Heightmap Mesh และ River Polylines สำหรับทั้งแผนที่โลก"""
    min_x, max_x = -320.0, 750.0
    min_y, max_y = -340.0, 420.0
    
    dx = (max_x - min_x) / grid_size
    dy = (max_y - min_y) / grid_size
    
    grid = []
    for gy in range(grid_size):
        row = []
        cy = min_y + gy * dy
        for gx in range(grid_size):
            cx = min_x + gx * dx
            
            # Find nearest realm center
            nearest_rk = 0
            best_dist = 99999.0
            for rk, rinfo in REALM_PROPERTIES.items():
                rcx, rcy = rinfo["center"]
                dist = math.hypot(cx - rcx, cy - rcy)
                if dist < best_dist:
                    best_dist = dist
                    nearest_rk = rk
            
            rinfo = REALM_PROPERTIES[nearest_rk]
            is_floating = rinfo["is_floating"]
            base_z = rinfo["base_z"]
            
            # Procedural height calculation
            noise_val = _noise_2d(cx, cy, seed=1)
            
            # Island mask (falloff around realm centers)
            mask = max(0.0, 1.0 - (best_dist / 140.0))
            if is_floating:
                elev = noise_val * mask * 0.8 + 0.2 if mask > 0.1 else 0.0
            else:
                elev = (noise_val * 0.7 + 0.3) * mask
                
            # Biome resolution
            if elev <= 0.05 and not is_floating:
                b_key = "deep_ocean"
            elif elev <= 0.15 and not is_floating:
                b_key = "shallow_water"
            elif is_floating:
                b_key = "floating_sky_island" if nearest_rk != "chaos" else "cosmic_void_shard"
            elif rinfo["theme"] == "desert_oasis":
                b_key = "yellow_desert" if elev > 0.1 else "oasis_emerald"
            elif rinfo["theme"] == "tropical_wetlands":
                b_key = "rainforest_himavanta" if elev > 0.3 else "plains"
            elif rinfo["theme"] == "volcanic_abyss":
                b_key = "volcanic_crag" if elev > 0.35 else "ash_wastes"
            elif rinfo["theme"] == "highland_steppe":
                b_key = "snow_peaks" if elev > 0.55 else "steppe_grassland"
            elif rinfo["theme"] == "volcanic_islands":
                b_key = "sakura_valley" if elev > 0.35 else "forest"
            elif elev > 0.6:
                b_key = "snow_peaks"
            elif elev > 0.4:
                b_key = "mountains"
            elif elev > 0.25:
                b_key = "high_hills"
            else:
                b_key = "plains"
                
            color = BIOMES.get(b_key, BIOMES["plains"])["color"]
            
            row.append({
                "x": round(cx, 1),
                "y": round(cy, 1),
                "elev": round(elev, 3),
                "z": round(base_z + elev * 40.0, 1),
                "biome": b_key,
                "color": color,
                "floating": is_floating,
                "realm": nearest_rk
            })
        grid.append(row)
        
    # Major Rivers
    rivers = [
        {
            "name": "แม่น้ำเจ้าพระยาโบราณ (สยาม - มนุษย์)",
            "color": "#48cae4",
            "points": [(-160.0, -100.0), (-130.0, -80.0), (-90.0, -50.0), (-40.0, -25.0), (10.0, 5.0)]
        },
        {
            "name": "แม่น้ำคงคาสวรรค์ (ชมพูทวีป)",
            "color": "#90e0ef",
            "points": [(-40.0, -210.0), (-35.0, -160.0), (-30.0, -100.0), (-20.0, -40.0), (10.0, 5.0)]
        },
        {
            "name": "สายธารามารโลหิต (แดนมาร)",
            "color": "#9b2226",
            "points": [(230.0, -240.0), (200.0, -200.0), (160.0, -150.0), (110.0, -90.0)]
        }
    ]
    
    return {
        "grid": grid,
        "grid_size": grid_size,
        "bounds": {"min_x": min_x, "max_x": max_x, "min_y": min_y, "max_y": max_y},
        "rivers": rivers,
        "realms": REALM_PROPERTIES,
        "biomes": BIOMES
    }


def get_all_places_data() -> List[Dict[str, Any]]:
    """รวบรวมข้อมูลสถานที่ 3D ทั้งหมดพร้อมสถานะและข้อมูลความเชื่อมโยง"""
    places_data = []
    for i, p in enumerate(PL.PLACES):
        name, w, grade, ptype, res, furn, sec_parent, is_sealed = p
        x, y, z, biome_key, biome_name = compute_place_3d_and_biome(i)
        
        realm_name = REALM_PROPERTIES.get(w, {}).get("name", str(w))
        
        places_data.append({
            "idx": i,
            "name": name,
            "realm_key": w,
            "realm_name": realm_name,
            "grade": grade,
            "type": ptype,
            "resource": res,
            "furnace": furn,
            "x": x,
            "y": y,
            "z": z,
            "biome_key": biome_key,
            "biome_name": biome_name,
            "is_sealed": is_sealed
        })
    return places_data
