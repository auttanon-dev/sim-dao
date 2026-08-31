# -*- coding: utf-8 -*-
"""Tactical Combat Visualizer Engine for Tiandao World Simulator.

Simulates vivid turn-based Wuxia/Xianxia duels between two cultivators,
generating structured action rounds, skill VFX cues, damage calculations,
Qi flows, and cinematic martial arts commentaries.
"""
import math
import random
from typing import Dict, List, Any, Optional, Tuple

from . import skills as SK
from . import config as C


# VFX Effect Mapping for Skills
SKILL_VFX_MAP = {
    "มวยไทย": "fist_flame",
    "กระบี่": "sword_beam",
    "ดาบ": "iai_slash",
    "องเมียวจิ": "shikigami_fire",
    "ธนู": "eagle_arrow",
    "แปรธาตุ": "alchemy_circle",
    "เวททราย": "sand_storm",
    "วัชระ": "diamond_body",
    "ตันตระ": "mandala_golden",
    "ฝ่ามือ": "buddha_palm",
    "กระบี่บิน": "flying_swords",
    "สายฟ้า": "lightning_tribulation",
    "เลือด": "blood_scythe"
}


def _get_char_skills(ch) -> List[Tuple[str, str, int, str]]:
    """ดึงรายชื่อทักษะวิชาของผู้บำเพ็ญ หรือจัดสรรวิชาตามถิ่นกำเนิดและขั้นพลัง"""
    skills = []
    if hasattr(ch, "skills") and ch.skills:
        for s in ch.skills:
            if isinstance(s, tuple) and len(s) >= 4:
                skills.append((s[0], s[1], s[3], s[4]))
                
    if not skills:
        dao = getattr(ch, "dao", "วิถีดาบ")
        realm = getattr(ch, "realm", 0)
        
        # Default skill set based on dao & cultural flavor
        if "มวย" in dao or getattr(ch, "tribe", "") == "ชาวสยาม":
            skills = [
                ("หมัดตรงศอกกลับพื้นฐาน", "มวยไทย", 0, "หมัดตรงและศอกกลับพื้นฐานเน้นความหนักแน่น"),
                ("หมัดเข่าศอกตีลอยลม", "มวยไทย", 1, "ผสานหมัด เข่า ศอกเป็นจังหวะเดียว"),
                ("แม่ไม้มวยไทยเก้าท่าจอมราชันย์", "มวยไทย", 2, "ผสานเก้ากระบวนท่าโบราณเป็นชุดโจมตีไร้เทียมทาน")
            ]
        elif "ดาบ" in dao or getattr(ch, "tribe", "") == "ชาวอาทิตย์อุทัย":
            skills = [
                ("เพลงดาบเคนโด้ฟันตรง", "ดาบ", 0, "การฟันดาบตรงเด็ดขาด"),
                ("เพลงดาบซากุระร่วงหล่น", "ดาบ", 1, "ร่ายรำดาบประหนึ่งกลีบซากุระปลิดปลิว"),
                ("วิชาดาบอิไอสวรรค์ตัดมิติพริบตา", "ดาบ", 2, "ชักดาบตัดมิติในเสี้ยวพริบตา ฟันทะลุเกราะ")
            ]
        elif "ลม" in dao or "เกาทัณฑ์" in dao or getattr(ch, "tribe", "") == "ชาวทุ่งหญ้า":
            skills = [
                ("ยิงธนูสั้นล่ากวาง", "ธนู", 0, "การยิงธนูพื้นฐาน"),
                ("เพลงธนูหลังม้าเกาทัณฑ์คู่", "ธนู", 1, "ยิงธนูบนหลังม้าอย่างแม่นยำ"),
                ("มหาศรเทพอินทรีทะลวงเก้าชั้นฟ้า", "ธนู", 2, "ยิงศรปราณเหินเวหาทะลวงภูเขา")
            ]
        elif "แปรธาตุ" in dao or "ดาว" in dao or getattr(ch, "tribe", "") == "ชาวโอเอซิส":
            skills = [
                ("กระบี่โค้งฟันตัดผ้า", "กระบี่", 0, "ตวัดดาบโค้งดั่งสายลม"),
                ("มนตราอัญเชิญจินนี่เพลิงสวรรค์", "เวททราย", 1, "เรียกเปลวไฟเวทมนตร์"),
                ("มหาศาสตร์เล่นแร่แปรธาตุศิลานักปราชญ์", "แปรธาตุ", 2, "หลอมรวมพลังจักรวาลแปรเปลี่ยนธาตุ")
            ]
        elif "วัชระ" in dao or "ความว่าง" in dao or getattr(ch, "tribe", "") == "ชาวชมพูทวีป":
            skills = [
                ("ฝ่ามือควงไม้พลองนักพรต", "กระบอง", 0, "ควงพลองปัดป้องการโจมตี"),
                ("โยคะสมาธิฌานเก้าขั้น", "วัชระ", 1, "เข้าสู่ภวังค์ตัดขาดจากความเจ็บปวด"),
                ("มหาคัมภีร์กายเพชรวัชระอมตะ", "วัชระ", 2, "แปรเปลี่ยนสรีระให้แข็งแกร่งดั่งเพชร")
            ]
        else:
            skills = [
                ("เพลงกระบี่ตัดลม", "กระบี่", 0, "ตวัดกระบี่ฟันพื้นฐาน"),
                ("กระบี่ไร้เงาเก้าเปลี่ยน", "กระบี่", 1, "เงากระบี่ซ้อนทับแปดทิศ"),
                ("เพลงกระบี่บินประหารเซียน", "กระบี่บิน", 2, "บังคับกระบี่เซียนผ่าชั้นเมฆ")
            ]
    return skills


def simulate_duel(c1, c2, max_rounds: int = 5) -> Dict[str, Any]:
    """จำลองการประลองยุทธ์รอบต่อรอบระหว่าง 2 ผู้บำเพ็ญ"""
    c1_name = getattr(c1, "name", "ผู้ประลองหนึ่ง")
    c2_name = getattr(c2, "name", "ผู้ประลองสอง")
    c1_realm = getattr(c1, "realm", 1)
    c2_realm = getattr(c2, "realm", 1)
    
    # Calculate Max HP and Initial Qi
    max_hp1 = 100.0 + c1_realm * 65.0
    max_hp2 = 100.0 + c2_realm * 65.0
    hp1 = max_hp1
    hp2 = max_hp2
    qi1 = 100.0 + c1_realm * 30.0
    qi2 = 100.0 + c2_realm * 30.0
    
    skills1 = _get_char_skills(c1)
    skills2 = _get_char_skills(c2)
    
    rounds = []
    
    for r_num in range(1, max_rounds + 1):
        if hp1 <= 0 or hp2 <= 0:
            break
            
        # Determine attacker order (speed/fate initiative)
        c1_first = (r_num % 2 == 1) if abs(c1_realm - c2_realm) <= 1 else (c1_realm >= c2_realm)
        
        fighters = [(c1, c2, 1, 2)] if c1_first else [(c2, c1, 2, 1)]
        fighters.append((c2, c1, 2, 1) if c1_first else (c1, c2, 1, 2))
        
        for atk, dfn, atk_idx, dfn_idx in fighters:
            if (atk_idx == 1 and hp1 <= 0) or (atk_idx == 2 and hp2 <= 0):
                continue
                
            atk_skills = skills1 if atk_idx == 1 else skills2
            chosen_skill = atk_skills[min(r_num - 1, len(atk_skills) - 1)]
            s_name, s_type, s_grade, s_desc = chosen_skill
            
            # Damage calculation
            base_power = (getattr(atk, "realm", 1) + 1) * 18.0 + (s_grade + 1) * 15.0
            is_crit = (random.random() < 0.25)
            crit_mult = 1.65 if is_crit else 1.0
            damage = round(base_power * crit_mult * random.uniform(0.85, 1.15), 1)
            
            # Apply damage
            if dfn_idx == 1:
                hp1 = max(0.0, round(hp1 - damage, 1))
            else:
                hp2 = max(0.0, round(hp2 - damage, 1))
                
            vfx = SKILL_VFX_MAP.get(s_type, "sword_beam")
            
            commentary = f"[{atk.name}] ร่ายวิชา 【{s_name}】 ปลดปล่อยพลัง {s_type} สร้างความเสียหาย {damage} แต้ม!"
            if is_crit:
                commentary += " 💥 โจมตีเข้าจุดตายรุนแรงเป็นพิเศษ!"
                
            rounds.append({
                "round": r_num,
                "attacker_id": atk_idx,
                "attacker_name": atk.name,
                "defender_id": dfn_idx,
                "defender_name": dfn.name,
                "skill_name": s_name,
                "skill_type": s_type,
                "skill_grade": s_grade,
                "damage": damage,
                "is_crit": is_crit,
                "vfx": vfx,
                "commentary": commentary,
                "hp1": hp1,
                "hp2": hp2,
                "hp1_pct": round((hp1 / max_hp1) * 100, 1),
                "hp2_pct": round((hp2 / max_hp2) * 100, 1)
            })
            
            if hp1 <= 0 or hp2 <= 0:
                break

    # Determine Winner
    if hp1 > hp2:
        winner_idx = 1
        winner_name = c1_name
        summary = f"🏆 【{c1_name}】 เป็นฝ่ายได้รับชัยชนะในการประลองยุทธ์!"
    elif hp2 > hp1:
        winner_idx = 2
        winner_name = c2_name
        summary = f"🏆 【{c2_name}】 เป็นฝ่ายได้รับชัยชนะในการประลองยุทธ์!"
    else:
        winner_idx = 0
        winner_name = "เสมอกัน"
        summary = "🤝 ทั้งสองฝ่ายฝีมือทัดเทียม ผลการประลองยุทธ์เสมอกันอย่างสมเกียรติ!"

    return {
        "fighter1": {
            "name": c1_name,
            "realm": c1_realm,
            "realm_name": getattr(c1, "realm_name", lambda: "ผู้ฝึกตน")(),
            "dao": getattr(c1, "dao", "วิถีดาบ"),
            "max_hp": max_hp1,
            "final_hp": hp1
        },
        "fighter2": {
            "name": c2_name,
            "realm": c2_realm,
            "realm_name": getattr(c2, "realm_name", lambda: "ผู้ฝึกตน")(),
            "dao": getattr(c2, "dao", "วิถีดาบ"),
            "max_hp": max_hp2,
            "final_hp": hp2
        },
        "total_rounds": len(rounds),
        "rounds": rounds,
        "winner_id": winner_idx,
        "winner_name": winner_name,
        "summary": summary
    }
