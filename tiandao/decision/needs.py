# -*- coding: utf-8 -*-
"""Needs — แรงกดดันภายในของตัวละคร (ทุกตัว normalize เป็น 0..1)

survival · hunger · thirst · rest · safety · wealth · social · status · revenge · training ·
exploration · longevity — และอื่นๆ ที่ adapter เพิ่มได้ (dict ธรรมดา ไม่ fix ชุด)

ไฟล์นี้มีตัวคำนวณพื้นฐานจาก AgentState + สิ่งที่เห็น สำหรับโลกทั่วไป ส่วน Sim Dao คำนวณ need
ของตัวเองใน simdao.py (reuse tiandao/ai/utility.py:compute_needs ของเดิม)
"""
import math


def clamp01(x):
    return 0.0 if x < 0 else 1.0 if x > 1 else x


def threat_pressure(entities, beliefs, now, cfg, self_power):
    """safety need = P(แพ้) สูงสุดต่อศัตรูที่เห็น ตาม Bradley–Terry บนพลัง "ตามความเชื่อ"

        P(lose) = 1 − logistic(ln(P_self / P_enemy) / s)

    ศัตรูที่ไม่เคยรู้พลังเลย = สมมติว่าสูสี (P = 0.5) — ไม่รู้คืออันตราย"""
    s = cfg.get("risk.win_scale", 0.35)
    worst = 0.0
    for e in entities:
        if not e.hostile:
            continue
        v, _conf = beliefs.get(f"power:{e.eid}", now, cfg)
        if v is None:
            v = self_power * cfg.get("risk.default_threat", 1.0)
        z = math.log(max(1e-9, self_power) / max(1e-9, v)) / s
        worst = max(worst, 1.0 - 1.0 / (1.0 + math.exp(-z)))
    return worst


def basic_needs(state, extra=None):
    """need จากร่างกาย — เติม/ทับด้วย extra"""
    out = {
        "survival": clamp01(1.0 - state.hp_ratio),
        "hunger": clamp01(state.hunger),
        "thirst": clamp01(state.thirst),
        "rest": clamp01(max(state.fatigue, 1.0 - state.stamina_ratio)),
    }
    out.update(extra or {})
    return out
