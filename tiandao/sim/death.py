# -*- coding: utf-8 -*-
"""Sim — ความตาย มรดก และตำแหน่งของผู้ตาย"""
from ._common import *  # noqa: F401,F403
from ._common import _REACH_CACHE, _PLACE_SETS, _CENTERS, _reach_from, _auction_q  # noqa: F401


class DeathMixin:
    # ------------------------------------------------------------ ตาย
    def kill(self, ch, cause, killer=None, natural=False):
        """ความตายทุกกรณีผ่านทางเดียว — ขั้นทั้งหมดอยู่ที่ tiandao/death.py (แบบ §7.4)"""
        DEATH.resolve(self, ch, cause, killer, natural)

    # ------------------------------------------------------------ มรดกและตำแหน่งของผู้ตาย
    def marry(self, a, b):
        """แต่งงาน — ทางเดียวของการผูกคู่ครอง: ทั้งคู่ต้องยังโสด (หม้ายแต่งใหม่ได้) แล้วรวมครัวเรือน คืน True ถ้าแต่งจริง"""
        if a is b or a.spouse is not None or b.spouse is not None:
            return False
        if not a.alive or not b.alive:
            # คนตายแต่งงานไม่ได้ — เดิม HH.marry ตั้งครัวเรือนใหม่ให้ศพเป็นหัวหน้า (seed 12 วัน 3347: ผู้ถูกสังหารวันนั้น
            # ถูกเลือกเป็นคู่ของ "กำเนิดทายาท") ศพจึงค้างในครัวเรือนตลอดไป
            return False
        a.spouse, b.spouse = b.cid, a.cid
        HH.marry(self, a, b)
        return True

    def heirs_of(self, ch):
        """ทายาทตามกฎหมาย (§7.4 ขั้น A4) ลำดับแรกที่มีคนรับ: คู่ครองที่ยังมีชีวิต → ลูกที่โตแล้วทุกคน → พ่อแม่ที่ยังมีชีวิต
        → พี่น้องที่โตแล้วทุกคน (พ่อหรือแม่เดียวกันอย่างน้อยหนึ่งคน) เรียงด้วย cid"""
        cast = self.cast
        living = lambda c: 0 <= c < len(cast) and cast[c].alive                       # noqa: E731
        grown = lambda c: living(c) and cast[c].age(self.day) >= C.ADULT_AGE           # noqa: E731
        if ch.spouse is not None and living(ch.spouse):
            return [cast[ch.spouse]]
        kids = [cast[c] for c in ch.children if grown(c)]
        if kids:
            return kids
        parents = [cast[c] for c in sorted(set(ch.parents or ())) if living(c)]
        if parents:
            return parents
        siblings = {s for p in ch.parents or () if 0 <= p < len(cast)
                    for s in getattr(cast[p], "children", ()) if s != ch.cid and grown(s)}
        return [cast[c] for c in sorted(siblings)]

    def estate_spot(self, ch):
        """ที่ที่มรดกไร้ผู้รับตกเป็นของ (แดน, สถานที่): ที่ที่ตาย กลางทางก็ที่ที่กำลังไป ไม่มีทั้งคู่ก็สถานที่แรกของแดน"""
        if ch.place is not None and ch.place >= 0:
            return ch.world_id, ch.place
        if ch.travel_dest >= 0:
            return ch.world_id, ch.travel_dest
        places = PL.places_in(self.world(ch.world_id).place_key)
        return ch.world_id, (places[0] if places else -1)

    def settle_estate(self, ch, items_to_heirs):
        """ทองของผู้ตายไปที่ทายาท (แบ่งเท่ากัน) ไม่มีทายาทเข้าคลังทองของสำนัก ไม่มีสำนักแต่อยู่ในตระกูลเข้าคลังตระกูล
        (ศาลบรรพชน §7.4 ข้อ 5) นอกนั้นตกเป็นของคลังชุมชนที่ที่ตาย (`settlement_treasury`, ขั้น A4) ของธรรมดาไปที่ทายาทเมื่อไม่มีผู้ฆ่าริบ ของที่มีชื่อยังตามกฎเดิม (ผนึกในแดนลับ)
        เดิมทองอยู่บนศพตลอดไป ไม่มีใครได้ใช้"""
        heirs = self.heirs_of(ch)
        org = (self.orgs[ch.org] if ch.org is not None and 0 <= ch.org < len(self.orgs)
               and self.orgs[ch.org].alive else None)
        stats = self.__dict__.setdefault("estate_stats", {"to_heirs": 0.0, "to_sect": 0.0, "unclaimed": 0.0,
                                                          "items_to_heirs": 0})
        stats.setdefault("to_clan", 0.0)
        stats.setdefault("to_settlement", 0.0)
        clan = getattr(ch, "clan", -1)
        for tier, gold in list(ch.money.items()):
            if gold <= 0:
                continue
            if heirs:
                for h in heirs:
                    h.money[tier] = h.money.get(tier, 0.0) + gold / len(heirs)
                stats["to_heirs"] += gold
            elif org is not None:
                purse = org.__dict__.setdefault("treasury_gold", {})
                purse[tier] = purse.get(tier, 0.0) + gold
                stats["to_sect"] += gold
            elif clan >= 0:
                hall = HH.clan_purse(self, clan)
                hall[tier] = hall.get(tier, 0.0) + gold
                stats["to_clan"] += gold
            else:
                town = WAGES.settlement_purse(self, self.estate_spot(ch))
                town[tier] = town.get(tier, 0.0) + gold
                stats["to_settlement"] += gold
            ch.money[tier] = 0.0
        if items_to_heirs:
            self._settle_goods(ch, heirs, stats)

    def _settle_goods(self, ch, heirs, stats):
        """ของธรรมดา วัตถุดิบ และของในถุงของผู้ตายที่ไม่มีผู้ฆ่าริบ — ไปที่ทายาท ไม่มีทายาทลงบัญชี "ฝังไปกับศพ"

        เดิมส่งต่อแค่ของธรรมดาเมื่อมีทายาท วัตถุดิบ (mat_stock) ของในถุง (inventory) และของเมื่อไม่มีทายาทค้างบนศพตลอดไป
        (test_world_coherence 2.2: seed 11–15 วัตถุดิบ 3,990 ครั้ง ของ 106 ครั้ง) ของที่มีชื่อ (legend) ยังตามกฎเดิม
        (ผนึกในแดนลับที่ death.resolve P8) ไม่มีทายาท: ของอยู่ใน sim.items ต่อแต่ไม่มีเจ้าของ บันทึกไว้ที่ buried_items
        วัตถุดิบและของในถุงนับไว้ที่ buried_mats / buried_inventory — แบบเดียวกับ buried_gold ไม่มีของหายเงียบ"""
        regular = [i for i in ch.items if i in self.items and not self.items[i].legend]
        bag = {name: n for name, n in getattr(ch, "inventory", {}).items()
               if isinstance(n, (int, float)) and not isinstance(n, bool) and n > 0}
        mats = {name: n for name, n in getattr(ch, "mat_stock", {}).items() if n > 0}
        if heirs:
            for n, iid in enumerate(regular):
                heirs[n % len(heirs)].items.append(iid)
            for store, goods in (("mat_stock", mats), ("inventory", bag)):
                for name, qty in sorted(goods.items()):
                    if isinstance(qty, int):                         # นับเป็นชิ้น: แบ่งเท่ากัน เศษไปทายาทคนแรก
                        share, rest = divmod(qty, len(heirs))
                        parts = [share + (1 if k < rest else 0) for k in range(len(heirs))]
                    else:
                        parts = [qty / len(heirs)] * len(heirs)
                    for h, part in zip(heirs, parts):
                        if part:
                            held = getattr(h, store)
                            held[name] = (held.get(name) or 0) + part
            stats["items_to_heirs"] += len(regular)
            stats["mats_to_heirs"] = stats.get("mats_to_heirs", 0) + sum(mats.values())
        else:
            self.__dict__.setdefault("buried_items", []).extend(regular)
            for store, goods in (("buried_mats", mats), ("buried_inventory", bag)):
                buried = self.__dict__.setdefault(store, {})
                for name, qty in goods.items():
                    buried[name] = buried.get(name, 0) + qty
            stats["items_buried"] = stats.get("items_buried", 0) + len(regular)
            stats["mats_buried"] = stats.get("mats_buried", 0) + sum(mats.values())
        for iid in regular:
            ch.items.remove(iid)
        ch.mat_stock = {}
        for name in bag:
            ch.inventory[name] = 0

    def org_head(self, org):
        """ผู้นำสำนักตอนนี้ — ผู้ก่อตั้งจนกว่าจะมีผู้สืบทอด"""
        lead = getattr(org, "leader", -1)
        return lead if lead >= 0 else org.founder

    def next_org_head(self, org):
        """ผู้นำคนถัดไปของสำนัก — ศิษย์สายแกน แล้วสายใน สายนอก สมาชิกอื่น ในกลุ่มเดียวกันเลือกขั้นสูงสุด (ไม่ใช้ RNG)"""
        cast = self.cast
        for group in (org.core_disciples, org.inner_disciples, org.outer_disciples, org.members):
            cands = [c for c in group if 0 <= c < len(cast) and cast[c].alive]
            if cands:
                return cast[max(cands, key=lambda c: (cast[c].realm, -c))]
        return None

    def next_sect_master(self, sect):
        """เจ้าสำนักคนถัดไปตามชื่อสำนัก — คนในสำนักที่ขั้นสูงสุด (ไม่ใช้ RNG)"""
        same = [c for c in map(self.cast.__getitem__, self.alive_sorted()) if getattr(c, "sect_name", None) == sect]
        return max(same, key=lambda c: (c.realm, -c.cid)) if same else None

    def succeed(self, ch, killer):
        """ตำแหน่งของผู้ตายมีคนรับช่วงทันที ไม่ว่างค้างตลอดไป
        - ผู้นำสำนัก: ศิษย์สายแกน แล้วสายใน สายนอก สมาชิกอื่น ในกลุ่มเดียวกันเลือกขั้นสูงสุด
        - ผู้คุมหอโอสถ/หอศาสตรา: สมาชิกที่ฝีมือทางนั้นสูงสุด (กฎเดียวกับที่ตั้งผู้คุมรายเดือน)
        - เจ้าสำนักตามชื่อสำนัก: ผู้ฆ่าที่อยู่สำนักเดียวกัน (ชิงตำแหน่ง) ไม่งั้นคนในสำนักที่ขั้นสูงสุด
        - เจ้าเมือง: คนในเมืองที่ขั้นสูงสุด รับตำแหน่งเดิม
        """
        cast = self.cast
        ok = lambda c: 0 <= c < len(cast) and cast[c].alive                      # noqa: E731
        world = self.world(ch.world_id)
        for org in self.orgs:
            if not org.alive:
                continue
            if self.org_head(org) == ch.cid:
                new = self.next_org_head(org)
                if new is not None:
                    org.leader = new.cid
                    self.emit(self.world(new.world_id), "สืบทอดตำแหน่ง", new, ch, ["ชื่อเสียง"], "เป็นผู้นำสำนัก",
                              f"{new.name}รับช่วงเป็นผู้นำ{org.name}ต่อจาก{ch.name}", 0, {"สำนัก": org.name})
            if org.alive and self.next_org_head(org) is None:
                org.alive = False           # ไม่เหลือสมาชิกที่ยังมีชีวิต สำนักสลายไป (ทุกที่ข้ามสำนักที่ alive=False อยู่แล้ว)
            for name, master in list(org.facilities.items()):
                if master != ch.cid:
                    continue
                skill = {"หอโอสถ": "alch_rank", "หอศาสตรา": "forge_rank"}.get(name)
                cands = [c for c in org.members if ok(c) and (skill is None or getattr(cast[c], skill, 0) > 0)]
                if cands:
                    org.facilities[name] = max(cands, key=lambda c: (getattr(cast[c], skill, 0) if skill
                                                                     else cast[c].realm, -c))
                else:
                    del org.facilities[name]
        sect = getattr(ch, "sect_name", None)
        if sect and getattr(ch, "sect_role", "") == "เจ้าสำนัก":
            ch.sect_role = ""
            if killer is not None and killer.alive and getattr(killer, "sect_name", None) == sect:
                new = killer
            else:
                new = self.next_sect_master(sect)
            if new is not None:
                new.sect_role = "เจ้าสำนัก"
                self.emit(self.world(new.world_id), "สืบทอดตำแหน่ง", new, ch, ["ชื่อเสียง"], "เป็นเจ้าสำนัก",
                          f"{new.name}ขึ้นเป็นเจ้า{sect}ต่อจาก{ch.name}", 0, {"สำนัก": sect})
        for city in self.cities:
            if city.get("ruler_cid") != ch.cid:
                continue
            here = [c for c in map(cast.__getitem__, self.alive_sorted()) if getattr(c, "city_id", -1) == city["id"]]
            new = max(here, key=lambda c: (c.realm, -c.cid)) if here else None
            city["ruler_cid"] = new.cid if new is not None else -1
            if new is not None:
                new.title = getattr(ch, "title", "") or getattr(new, "title", "")
                self.emit(world, "สืบทอดตำแหน่ง", new, ch, ["ชื่อเสียง"], "เป็นเจ้าเมือง",
                          f"{new.name}ขึ้นปกครองเมืองต่อจาก{ch.name}", 0, {"เมือง": city.get("name", city["id"])})
