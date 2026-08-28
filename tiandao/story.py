# -*- coding: utf-8 -*-
"""คัดตัวละครที่น่าเล่า แล้วเรนเดอร์เป็นชีวประวัติ"""
from . import config as C


def interest(ch, sim):
    s = 0.0
    s += ch.peak_realm * 1.4 + ch.peak_tier * 8.0
    if ch.origin in ("ชาวบ้าน", "ทาส", "เด็กกำพร้า"):
        s += ch.peak_realm * 2.0
    s += ch.near_death * 2.0 + min(ch.kills, 8) * 0.7
    s += ch.fails * 1.2 + ch.ascends * 6.0
    s += len(ch.rivals) * 0.9 + len(ch.bonds) * 0.5
    s += min(ch.inner, 8.0) * 1.2
    if ch.inner_none:
        s += 3.0
    if ch.inner_art:
        s += 3.0
    if not ch.alive and ch.death_cause != "สิ้นอายุขัย":
        s += 3.0
    if ch.realm < ch.peak_realm:
        s += (ch.peak_realm - ch.realm) * 1.6
    s += (ch.forge + ch.alchemy) * 0.8
    s += ch.generation * 0.8
    if ch.clan >= 0:
        s += 2.0
    n = len([e for e in sim.log if e.actor == ch.cid or e.target == ch.cid])
    s += min(n, 50) * 0.25
    return s


def rank(sim, top=5):
    sc = [(interest(c, sim), c) for c in sim.cast if c.sentient]
    sc.sort(key=lambda x: -x[0])
    return sc[:top]


def fmt_gap(d):
    if d < 60:
        return f"{d} วัน"
    if d < 730:
        return f"{d // 30} เดือน"
    return f"{d // 365} ปี"


def blood_str(ch):
    parts = [f"{C.BLOOD_TH[k]} {v*100:.0f}%" for k, v in
             sorted(ch.blood.items(), key=lambda x: -x[1]) if v >= 0.05]
    return " / ".join(parts)


def biography(ch, sim):
    L = []
    L.append(f"# {ch.name} — {ch.race()} · {ch.dao} · กำเนิด{ch.origin}")
    from . import clans as CL
    if ch.clan >= 0:
        c = CL.CLANS[ch.clan]
        L.append(f"ตระกูล: {c[0]} — {c[3]}")
    L.append(f"สายเลือด: {blood_str(ch)} (รุ่นที่ {ch.generation})")
    st = (f"ยังอยู่ อายุ {ch.age(sim.day)} ปี" if ch.alive
          else f"ตายเมื่ออายุ {(ch.death_day - ch.born_day)//365} ปี — {ch.death_cause}")
    w = sim.world(ch.world_id)
    loc = sim.place_name(ch)
    L.append(f"ขั้นสูงสุด: {C.realm_name(ch.peak_tier, ch.peak_realm)} | ปัจจุบัน: {ch.realm_name()} "
             f"@ {loc}, {w.name} | {st}")
    L.append(f"แนวทาง: {ch.archetype} · นิสัย: {', '.join(ch.traits) or '-'}")
    inner = "ไร้จิตมาร" if ch.inner_none else (
        f"จิตมาร {ch.inner:.1f}" + (" (ฝึกเป็นวิชา)" if ch.inner_art else ""))
    legend = [sim.items[i] for i in ch.items if sim.items[i].legend]
    if legend:
        L.append("สมบัติฟ้าดินในครอบครอง: " + ", ".join(f"{i.name} — {i.power_desc}" for i in legend))
    if ch.skills:
        from . import skills as SK
        idx = {x[0]: x for x in SK.SKILLS}
        L.append("วิชาที่ฝึกสำเร็จ:")
        for n in ch.skills:
            sk = idx.get(n)
            if sk:
                mark = " ★แก้ทางโกลาหล" if sk[5] else ""
                L.append(f"  - {n} ({SK.GRADE_NAME[sk[3]]} สาย{sk[1]}) — {sk[4]}{mark}")
    if ch.hated():
        L.append("สถานะ: เป็นมนุษย์มาร ถูกมนุษย์รังเกียจและตามล่า")
    L.append(f"{inner} | ชะตาเหลือ {ch.fate} | เฉียดตาย {ch.near_death} | "
             f"ข้ามขั้นสำเร็จ {ch.breaks} ล้มเหลว {ch.fails} | ข้ามฟ้า {ch.ascends}")
    if ch.forge_rank >= 0 or ch.alch_rank >= 0:
        from . import crafting as CR
        bits = []
        if ch.forge_rank >= 0:
            bits.append(CR.FORGE_RANKS[ch.forge_rank])
        if ch.alch_rank >= 0:
            bits.append(CR.ALCHEMY_RANKS[ch.alch_rank])
        L.append("ขั้นช่าง: " + " · ".join(bits))
    if ch.thrall:
        L.append("สถานะ: ตกเป็นพวกเผ่าโกลาหล — ได้รับการดูแลจากพวกมัน แต่เป็นทาส")
    unresolved = [d for d in ch.debts if not d["done"]]
    if unresolved:
        L.append("เรื่องค้างคา: " + ", ".join(f"{d['kind']}{d['name']}" for d in unresolved[:6]))
    L.append("")
    prev = None
    for e in sim.log:
        if e.actor != ch.cid and e.target != ch.cid:
            continue
        gap = "" if prev is None else f"[ผ่านไป {fmt_gap(e.day - prev)}] "
        prev = e.day
        extra = "  ".join(f"({k}: {v})" for k, v in e.deltas.items())
        L.append(f"- {gap}{e.text} {extra}".rstrip())
    return "\n".join(L)
