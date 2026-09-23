# -*- coding: utf-8 -*-
"""Dynamic Weather & Seasonal Atmosphere Engine for Tiandao World Simulator.

Generates real-time weather phenomena, particle overlays, and gameplay modifiers
for all 10 realms and 182 places based on seasonal cycles and regional climates.
"""
import math
import zlib
from typing import Dict, List, Any

from . import seasons as SEASONS

# Weather Types Definitions with Particle Configurations
WEATHER_CATALOG = {
    "sakura_breeze": {
        "name": "สายลมโปรยกลีบซากุระ",
        "particle_type": "petal",
        "particle_color": "#ffb3c6",
        "particle_count": 45,
        "wind_x": 1.5,
        "wind_y": 0.8,
        "effect_desc": "กลีบซากุระโบราณปลิดปลิว ฟื้นฟูปราณจิตใจ +15%",
        "bonus_stat": {"regen_mult": 1.15, "insight_bonus": 1.10}
    },
    "lotus_rain": {
        "name": "พิรุณหยาดน้ำค้างบงกช",
        "particle_type": "raindrop",
        "particle_color": "#48cae4",
        "particle_count": 80,
        "wind_x": 0.5,
        "wind_y": 4.0,
        "effect_desc": "สายฝนแห่งความชุ่มชื้น สมุนไพรเติบโตเร็วขึ้น +20%",
        "bonus_stat": {"herb_yield": 1.20, "regen_mult": 1.10}
    },
    "heavy_snow": {
        "name": "พายุหิมะน้ำแข็งนิรันดร์",
        "particle_type": "snowflake",
        "particle_color": "#ffffff",
        "particle_count": 65,
        "wind_x": 2.0,
        "wind_y": 1.8,
        "effect_desc": "หิมะโปรยขาวโพลน เหมาะแก่การกักตนฝึกสมาธิในเรือนพัก +25%",
        "bonus_stat": {"seclusion_bonus": 1.25, "travel_speed": 0.8}
    },
    "golden_sandstorm": {
        "name": "พายุทรายทองคำหมื่นราตรี",
        "particle_type": "sand_grain",
        "particle_color": "#e9c46a",
        "particle_count": 70,
        "wind_x": 3.5,
        "wind_y": 0.4,
        "effect_desc": "พายุทรายสีทองบดบังทัศนวิสัย ปลุกพลังธาตุดินและแร่ทองคำ +20%",
        "bonus_stat": {"mine_yield": 1.20, "stealth_bonus": 1.30}
    },
    "crimson_ember": {
        "name": "ละอองเพลิงลาวาโลกันตร์",
        "particle_type": "ember",
        "particle_color": "#e63946",
        "particle_count": 40,
        "wind_x": 0.2,
        "wind_y": -1.2,  # ลอยขึ้น
        "effect_desc": "ไอความร้อนเดือดพล่าน เพิ่มอัตราสำเร็จการหลอมศาสตรา +25%",
        "bonus_stat": {"forge_rate": 1.25, "fire_dao": 1.20}
    },
    "celestial_aurora": {
        "name": "แสงออโรร่าม่านเมฆเซียน",
        "particle_type": "qi_sparkle",
        "particle_color": "#caf0f8",
        "particle_count": 35,
        "wind_x": 0.3,
        "wind_y": 0.3,
        "effect_desc": "ละอองปราณสวรรค์เจิดจรัส เพิ่มโอกาสเบิกมรรคเข้าใจเต๋า +30%",
        "bonus_stat": {"breakthrough_rate": 1.30, "dao_insight": 1.25}
    },
    "golden_sunshine": {
        "name": "แสงสุริยันต์ทอประกายฟ้า",
        "particle_type": "sun_ray",
        "particle_color": "#ffd166",
        "particle_count": 20,
        "wind_x": 0.1,
        "wind_y": 0.1,
        "effect_desc": "อากาศแจ่มใส การเดินทางและการค้าขายราบรื่น +20%",
        "bonus_stat": {"trade_gain": 1.20, "travel_speed": 1.15}
    }
}


def get_current_weather(day: int, realm_key: Any) -> Dict[str, Any]:
    """คำนวณสภาพอากาศประจำวันสำหรับดินแดนที่กำหนด"""
    season_name, _, _, _ = SEASONS.season_of(day)
    
    # Deterministic weather hash from day and realm
    # zlib.crc32 แทน hash() — hash() ของสตริงใน Python สุ่ม seed ใหม่ทุกโปรเซส ทำให้อากาศของ
    # "วันเดียวกันในดินแดนเดียวกัน" เปลี่ยนไปมาทุกครั้งที่เจนนิยายใหม่ ทั้งที่ควรคงที่ตลอดกาล
    seed = (day // 7) * 31 + zlib.crc32(str(realm_key).encode("utf-8")) % 100
    
    weather_key = "golden_sunshine"
    
    if realm_key == "fusang":
        weather_key = "sakura_breeze" if season_name == "ฤดูใบไม้ผลิ" else "lotus_rain" if season_name == "ฤดูร้อน" else "heavy_snow" if season_name == "ฤดูหนาว" else "golden_sunshine"
    elif realm_key == "siam":
        weather_key = "lotus_rain" if season_name in ("ฤดูฝน", "ฤดูร้อน") else "golden_sunshine"
    elif realm_key == "steppe":
        weather_key = "heavy_snow" if season_name in ("ฤดูหนาว", "ฤดูใบไม้ร่วง") else "golden_sunshine"
    elif realm_key == "oasis":
        weather_key = "golden_sandstorm" if (seed % 3 == 0) else "golden_sunshine"
    elif realm_key == "bharata":
        weather_key = "lotus_rain" if (seed % 2 == 0) else "golden_sunshine"
    elif realm_key in (1, 2):  # แดนเซียน / สวรรค์นอกชั้นฟ้า
        weather_key = "celestial_aurora" if (seed % 2 == 0) else "golden_sunshine"
    elif realm_key == "mara":
        weather_key = "crimson_ember"
    elif realm_key == "chaos":
        weather_key = "celestial_aurora"
    elif realm_key == "abyss":          # แดนใต้พิภพไม่มีแดด มีแต่ไฟกับหมอกวิญญาณ
        weather_key = "crimson_ember"
    elif realm_key == "ocean":          # ใต้สมุทร — แสงเรืองจากปะการังและฝนใต้น้ำ
        weather_key = "celestial_aurora" if (seed % 2 == 0) else "lotus_rain"
    else:  # โลกมนุษย์
        if season_name == "ฤดูหนาว":
            weather_key = "heavy_snow"
        elif season_name == "ฤดูฝน":
            weather_key = "lotus_rain"
        elif season_name == "ฤดูร้อน":
            weather_key = "golden_sunshine"
        else:
            weather_key = "golden_sunshine"
            
    info = WEATHER_CATALOG.get(weather_key, WEATHER_CATALOG["golden_sunshine"])
    return {
        "day": day,
        "season": season_name,
        "realm_key": realm_key,
        "weather_key": weather_key,
        **info
    }
