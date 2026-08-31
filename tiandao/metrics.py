# -*- coding: utf-8 -*-
"""สรุปผลลัพธ์จากซิมหนึ่งรัน ให้เหลือตัวเลขไม่กี่ตัว — สำหรับตัวปรับสมดุลอ่านเทียบเป้าหมาย
(ดู tiandao/tuning.py) ไม่เกี่ยวกับการเรียนรู้ของ NPC แต่ละตัว (นั่นอยู่ใน intent.py)"""
from . import config as C


def summarize(sim, events_run: int) -> dict:
    normal = [c for c in sim.cast if not c.is_chaos() and not c.thrall]
    total = len(normal) or 1

    pyramid = [0] * (C.REALM_CAP + 1)
    for c in normal:
        pyramid[min(c.peak_realm, C.REALM_CAP)] += 1
    mono_hits, mono_total = 0, 0
    for i in range(len(pyramid) - 1):
        if pyramid[i] or pyramid[i + 1]:
            mono_total += 1
            if pyramid[i] >= pyramid[i + 1]:
                mono_hits += 1
    pyramid_monotonic = (mono_hits / mono_total) if mono_total else 1.0
    advancement_rate = 1.0 - (pyramid[0] / total)

    mortal_worlds = [w for w in sim.worlds if w.kind == "mortal"]
    era_gain = sum(max(0, w.era - 1) for w in mortal_worlds) / max(1, len(mortal_worlds))
    era_rate = era_gain / max(1, events_run) * 100000.0

    org_rate = len(sim.orgs) / max(1, events_run) * 100000.0
    cache_rate = len(sim.caches) / max(1, events_run) * 100000.0

    invasions = [e for e in sim.log if e.kind == "โกลาหลบุกโลกมนุษย์"]
    repelled = sum(1 for e in invasions if e.outcome in ("ถูกขับไล่", "ถูกสกัดกั้น"))
    chaos_defense_rate = (repelled / len(invasions)) if invasions else None

    return {
        "pyramid": pyramid,
        "pyramid_monotonic": pyramid_monotonic,
        "advancement_rate": advancement_rate,
        "era_rate": era_rate,
        "org_rate": org_rate,
        "cache_rate": cache_rate,
        "chaos_defense_rate": chaos_defense_rate,
        "chaos_samples": len(invasions),
        "population": total,
    }
