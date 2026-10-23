# -*- coding: utf-8 -*-
"""Sim — หุ่นเชิด"""
from ._common import *  # noqa: F401,F403
from ._common import _REACH_CACHE, _PLACE_SETS, _CENTERS, _reach_from, _auction_q  # noqa: F401


class PuppetMixin:
    # ------------------------------------------------------------ หุ่นเชิด
    def wrong_done(self, a, t, kind, gold):
        """ผลของการปล้นหรือริบของจากผู้ถูกฆ่า (ขั้นปล้น §7.4): ผู้ถูกกระทำแค้น ญาติในครัวเรือนและตระกูลเดียวกันในแดนแค้นรองลงมา
        ผู้กระทำติดหนี้กรรม นับครั้งที่ปล้นไว้ให้ crime_weight ได้ของมากก็มีเหตุให้ไปปิดด่าน (intent.weigh) และนับไว้ในสถิติ"""
        stats = self.__dict__.setdefault("crime_stats", {})
        stats[kind] = stats.get(kind, 0.0) + gold
        stats[kind + "_count"] = stats.get(kind + "_count", 0) + 1
        if gold >= 365.0 * C.FOOD_RATION_ADULT * C.FOOD_PRICE:
            a.big_haul_day = self.day
        if kind not in ("ปล้น", "โกง"):
            return                                  # ผู้ถูกฆ่า: ญาติแค้นเมื่อข่าวถึง (news) และผู้ฆ่าติดหนี้ผ่าน add_debt อยู่แล้ว
        if kind == "ปล้น":
            a.robberies = getattr(a, "robberies", 0) + 1
        # "โกง" (เด็กโกงเงินทอนแล้วถูกจับ — childhood._cheat): หนี้กรรมและความแค้นของพ่อค้า/ครัวเรือนแบบเดียวกับการปล้น
        R.add_debt(a, kind, t.cid, t.name, self.day)
        t.rivals[a.cid] = t.rivals.get(a.cid, 0) + C.GRUDGE_ROB
        hh = HH.of(self, t)
        kin = set(hh.members) if hh is not None else set()
        if t.clan >= 0:
            kin |= {c.cid for c in self.living_in(t.world_id) if c.clan == t.clan}
        for cid in sorted(kin - {t.cid, a.cid}):
            m = self.cast[cid]
            if m.alive:
                m.rivals[a.cid] = m.rivals.get(a.cid, 0) + C.GRUDGE_ROB_KIN

    def raise_corpse(self, killer, victim, rng):
        """สายเชิดศพ: ฆ่าคนแล้วปลุกซากขึ้นมาเป็นหุ่นของตน

        ราคาของวิชานี้ไม่ใช่วัตถุดิบ แต่เป็น **กรรมค้างคา** — ตรงกับกฎของโลกที่ว่าการฆ่าต้องมีราคา
        และมนุษย์มารเป็นที่รังเกียจ ผู้ฝึกสายนี้จึงแกร่งขึ้นได้ฟรีในสนามรบ แต่สะสมจิตมารเร็วกว่าใคร
        ซึ่งย้อนมาเล่นงานตอนข้ามขั้นเอง
        """
        if R.puppet_line_grade(killer, "เชิดศพ") < 0:
            return
        cap = R.puppet_cap(killer)
        if killer.puppets >= cap or rng.random() >= C.PUPPET_RAISE_P:
            return
        killer.puppets += 1
        killer.puppet_kind = "เชิดศพ"
        R.add_debt(killer, "เชิดศพ", victim.cid, victim.name, self.day)
        killer.karmic_debt = getattr(killer, "karmic_debt", 0) + C.CORPSE_PUPPET_DEBT
        self.emit(self.world(killer.world_id), "เชิดซากเป็นหุ่น", killer, victim,
                  ["ความตาย", "ทำลาย"], "ปลุกซากสำเร็จ",
                  f"{killer.name}ปลุกซากของ{victim.name}ที่ยังไม่ทันเย็นให้ลุกขึ้นเดินตามคำสั่ง "
                  f"ร่างที่เคยเป็นคนกลายเป็นหุ่นเชิดตนหนึ่งของมัน", 0,
                  {"หุ่นในมือ": f"{killer.puppets}/{cap} ตน",
                   "ราคาที่จ่าย": f"จิตมารหนักขึ้น {C.CORPSE_PUPPET_DEBT:.0f}",
                   "ชนิดหุ่น": "ซากผู้บำเพ็ญ"})

    def build_puppet(self, a, w, rng, d):
        """สายหุ่นกล: หลอมหุ่นขึ้นมาเองจากแร่และแก่นพลังอสูร

        คืน tuple แบบเดียวกับ resolve() ถ้าลงมือจริง คืน None ถ้าไม่เข้าเงื่อนไข (ให้ไปทำค่ายกลตามเดิม)
        """
        g = R.puppet_line_grade(a, "หุ่นกล")
        if g < 0:
            return None
        cap = R.puppet_cap(a)
        if a.puppets >= cap:
            return None
        need_cores, need_mats = 1 + g, 2 + g
        if a.cores < need_cores or a.mats < need_mats:
            d["ยังขาด"] = f"แก่นพลัง {need_cores} · วัตถุดิบ {need_mats}"
            return ("ขาดวัตถุดิบ", f"{a.name}อยากหลอมหุ่นกล แต่ยังขาด{d['ยังขาด']}", d)
        a.cores -= need_cores
        a.mats -= need_mats
        d["วัตถุดิบที่ใช้"] = f"แก่นพลังอสูร {need_cores} · แร่ {need_mats}"
        if rng.random() >= C.PUPPET_CRAFT_P:
            return ("ล้มเหลว", f"{a.name}หลอมหุ่นกลล้มเหลว หุ่นแตกคามือ วัตถุดิบสูญเปล่า", d)
        a.puppets += 1
        if not a.puppet_kind:
            a.puppet_kind = "หุ่นกล"
        d["หุ่นในมือ"] = f"{a.puppets}/{cap} ตน"
        name = ("หุ่นไม้ชักใย", "หุ่นสัมฤทธิ์ไร้ความเจ็บ", "หุ่นเหล็กพันมือ")[min(g, 2)]
        return ("หลอมสำเร็จ", f"{a.name}หลอม{name}ขึ้นมาได้อีกหนึ่งตน เชิดมันสู้แทนตัวได้", d)
