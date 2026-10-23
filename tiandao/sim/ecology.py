# -*- coding: utf-8 -*-
"""Sim — ระบบนิเวศ"""
from ._common import *  # noqa: F401,F403
from ._common import _REACH_CACHE, _PLACE_SETS, _CENTERS, _reach_from, _auction_q  # noqa: F401


class EcologyMixin:
    # ------------------------------------------------------------ ระบบนิเวศ (แบบ §6.2 R1–R3)
    # คลังแยกชนิดต่อ (แดน, สถานที่, ชนิด): "herb" สมุนไพร "beast" สัตว์อสูร "ore" แร่ — ชนิดหลักของที่นั้นตาม eco_kind
    # เก็บได้ไม่เกินที่มีจริง ทีละหน่วย (eco_harvest คืนหน่วยที่ได้) ไม่มีพื้นผลผลิตขั้นต่ำอีก — วัดแล้ว (seed 11–13 เดิน 50 ปี)
    # แหล่งสมุนไพรและแร่ที่มีคนใช้ 70–78% อยู่ที่พื้นตั้งแต่ปีที่ 25 และการเก็บ 71–80% เกิดตอนคลังอยู่ที่พื้น คือของเกิดจากอากาศ
    # บัญชี `material_stats`: คลังรวม = genesis + regrown + seeded − harvested − disaster (test_resources)
    def eco_kind(self, place_idx):
        """ชนิดทรัพยากรหลักของสถานที่ — แหล่งแร่/สมุนไพร/แก่นพลัง ตามผัง ที่อื่น (เมือง สำนัก ป่า) คือสัตว์อสูรที่ล่าได้"""
        p = PL.PLACES[place_idx] if place_idx is not None and 0 <= place_idx < len(PL.PLACES) else None
        return {"แร่": "ore", "สมุนไพร": "herb"}.get(p[4] if p and len(p) > 4 else None, "beast")

    def _eco_key(self, wid, place_idx, kind):
        key = (wid, place_idx, kind or self.eco_kind(place_idx))
        if key not in self.place_stock:
            cap = C.ECO_KINDS[key[2]][0]
            self.place_stock[key] = cap
            self._eco_dirty()
            self._material_flow("genesis", cap)
        return key

    def _material_flow(self, cause, amount):
        stats = self.__dict__.setdefault("material_stats", {})
        stats[cause] = stats.get(cause, 0.0) + amount

    def eco_ratio(self, wid, place_idx, kind=None):
        """สัดส่วนที่เหลือของคลังชนิด `kind` (ค่าตั้ง = ชนิดหลักของที่นั้น) ที่ `place_idx` ในแดน `wid` (0..1) — ไม่มีพื้น"""
        if place_idx is None or place_idx < 0:
            return 1.0
        key = self._eco_key(wid, place_idx, kind)
        return min(1.0, self.place_stock[key] / C.ECO_KINDS[key[2]][0])

    def eco_regen(self, elapsed_days):
        """แหล่งทรัพยากรฟื้นตัวแบบลอจิสติก ไม่ใช่เส้นตรง — อัตราและเพดานตามชนิด (ECO_KINDS)

        ของเดิมเขียน `min(ECO_CAP, stock + grow)` ซึ่งเป็นสองข้อผิดเดียวกับที่ heaven_inflow
        เคยเป็นก่อนแก้ และตรวจเจอซ้ำที่นี่ตอนรื้อระบบทรัพยากร
          1. แหล่งที่ถูกขุดจนเหลือเศษ ฟื้นเร็วเท่าแหล่งที่เกือบเต็ม — "ขุดจนโทรม" จึงไม่เคย
             เป็นสภาพที่อยู่ได้นานพอจะมีผลต่อการตัดสินใจของใคร
          2. min() ที่เพดานคือการทำผลผลิตหายจากระบบเงียบๆ
        ลอจิสติกแก้ทั้งคู่ สมุนไพรและสัตว์อสูรคูณฤดูกาล แร่ไม่ (สายแร่ก่อตัวช้าตามปี ไม่ตามฤดู)
        ต่ำกว่า ECO_SEED ยกขึ้นเป็น ECO_SEED ก่อนโต (เมล็ดในดิน สัตว์ย้ายเข้ามาจากที่ใกล้เคียง) บันทึกเป็น `seeded`
        """
        if not self.place_stock or elapsed_days <= 0:
            return
        season = SEASONS.regen_multiplier(self.day)
        for key in list(self.place_stock):
            cap, r = C.ECO_KINDS[key[2]]
            rate = r * (1.0 if key[2] == "ore" else season) / 365.0
            old = self.place_stock[key]
            if old < C.ECO_SEED:
                self._material_flow("seeded", C.ECO_SEED - old)
                old = C.ECO_SEED
            stock = PHYS.logistic_growth(old, cap, rate, elapsed_days)
            self._material_flow("regrown", stock - old)
            self.place_stock[key] = stock
            self._update_eco_state(key, stock)
        self._eco_dirty()

    def eco_harvest(self, wid, place_idx, amount, kind=None, cause="harvested"):
        """เอาออกจากคลังชนิด `kind` ไม่เกินที่มี — คืนหน่วยที่ได้จริง ผู้เรียกให้ของตามนี้เท่านั้น"""
        if place_idx is None or place_idx < 0 or amount <= 0:
            return 0.0
        key = self._eco_key(wid, place_idx, kind)
        taken = min(amount, self.place_stock[key])
        self.place_stock[key] -= taken
        self._eco_dirty()
        self._material_flow(cause, taken)
        self._update_eco_state(key, self.place_stock[key])
        return taken

    def eco_take_units(self, wid, place_idx, units, kind=None):
        """เอาของเป็นชิ้นเต็ม (ไม่เกิน `units`) — คืนจำนวนชิ้นที่ได้"""
        if place_idx is None or place_idx < 0 or units <= 0:
            return 0
        key = self._eco_key(wid, place_idx, kind)
        n = min(int(units), int(self.place_stock[key] + 1e-9))
        return int(round(self.eco_harvest(wid, place_idx, float(n), kind))) if n > 0 else 0

    def blood_state(self, world):
        """สภาวะโลกที่สายเลือดของทารกปรับตามตอนเกิด: สงคราม > ทรัพยากรน้อย > ยุคของแดน (เสื่อม/ปกติ/รุ่งเรือง)
        สงคราม = มหาศึกโกลาหลกำลังถล่มโลกมนุษย์ (crises.chaos_campaign) และทารกเกิดในแดนมนุษย์"""
        if world.kind == "mortal" and getattr(self, "chaos_campaign", None):
            return "สงคราม"
        if self.is_scarce(world):
            return "ทรัพยากรน้อย"
        return world.state()

    def eco_mean(self, world):
        """ค่าเฉลี่ย eco_ratio ของคลังวัตถุดิบที่มีอยู่ในแดน (0..1) — แดนที่ยังไม่มีใครแตะคลังเลย = 1.0
        คำนวณทุกแดนในรอบเดียวแล้วจำไว้ (ถูกถามทุกการเกิด ทุกรอบอาหาร และทุกการทอยภัย — สแกนแยกแดนละรอบทำให้ซิมช้าลงเท่าตัว)
        แคชถูกล้างทุกครั้งที่ place_stock เปลี่ยน (_eco_dirty) จึงเท่ากับคำนวณใหม่เสมอ — เข้าเซฟไปก็ได้ค่าเดียวกับคำนวณใหม่"""
        sums = self.__dict__.get("_eco_means")
        if sums is None:
            acc = {}
            for k, v in self.place_stock.items():
                s = acc.setdefault(k[0], [0.0, 0])
                s[0] += min(1.0, v / C.ECO_KINDS[k[2]][0])
                s[1] += 1
            sums = self._eco_means = {wid: s / n for wid, (s, n) in acc.items()}
        return sums.get(world.wid, 1.0)

    def _eco_dirty(self):
        self.__dict__.pop("_eco_means", None)

    def is_scarce(self, world):
        """แดนอยู่ในสถานะ "ทรัพยากรน้อย" — คลังเฉลี่ยต่ำกว่าเกณฑ์ขาดแคลนเดิมของระบบนิเวศ (ECO_SCARCE_RATIO)"""
        return self.eco_mean(world) < C.ECO_SCARCE_RATIO

    def nature_damage(self, world):
        """ดัชนีความเสียหายของธรรมชาติในแดน 0..1 — คำนวณจากสภาวะที่สะสมจริงทั้งหมด ไม่มีตัวนับใหม่ ไม่สุ่ม

        ทรัพยากรหมด (น้ำหนักหลัก NATURE_W_RESOURCE): 1 − ค่าเฉลี่ย eco_ratio ของคลังที่มีอยู่ในแดน (ลดเมื่อเก็บเกินกำลังผลิต
          และภัยแล้ง ฟื้นแบบลอจิสติกช้าเมื่อเหลือน้อย — จึงสะสม) ผสมกับต้นไม้โลกที่ถูกใช้/ตาย (tree_vitality / capacity)
        พลังฟ้าฟุ่มเฟือย (NATURE_W_HEAVEN): 1 − heaven/cap — ถูกถอนไปข้ามขั้น ขุด ดึงปราณ
        สงคราม (NATURE_W_WAR): สัดส่วนสถานที่ในแดนที่ยังมีรอยเลือดในช่วงจำของวงจรแค้น (blood_marks จากการฆ่าจริง)"""
        eco_loss = 1.0 - self.eco_mean(world)
        if getattr(self, "tree_vitality", None) is not None:
            tree_loss = 1.0 - (min(1.0, self.tree_vitality / max(1e-9, WT.capacity(self)))
                               if self.tree_alive else 0.0)
            resource = (1 - C.NATURE_TREE_SHARE) * eco_loss + C.NATURE_TREE_SHARE * tree_loss
        else:
            resource = eco_loss
        heaven = 1.0 - min(1.0, world.heaven / max(1e-9, world.cap()))
        places = PL.places_in(world.place_key)
        book = getattr(self, "blood_marks", None) or {}
        cut = self.day - C.FEUD_HALF_LIFE_DAYS * C.FEUD_KEEP_HALFLIVES
        war = (sum(1 for p in places if any(t >= cut for t in book.get(p, ()))) / len(places)) if places else 0.0
        dmg = C.NATURE_W_RESOURCE * resource + C.NATURE_W_HEAVEN * heaven + C.NATURE_W_WAR * war
        return max(0.0, min(1.0, dmg))

    def nature_speedup(self, world):
        """ตัวคูณจังหวะธรรมชาติ = 1 + NATURE_SPEEDUP_MAX × damage (เร็วขึ้นไม่เกิน 50%) — ใช้กับภัยตามฤดู
        การเสื่อมของมหาผนึก และแรงกดดันมหาศึกโกลาหล (test_world_coherence 4.3)"""
        return 1.0 + C.NATURE_SPEEDUP_MAX * self.nature_damage(world)

    def _update_eco_state(self, key, stock):
        """สถานะขาดแคลนของชนิดหลักของที่นั้น (คีย์ (แดน, สถานที่)) ค้างอยู่จนกว่าจะฟื้นข้ามเกณฑ์ recover จริง"""
        wid, idx, kind = key
        if kind != self.eco_kind(idx):
            return
        ratio = stock / C.ECO_KINDS[kind][0]
        spot = (wid, idx)
        if ratio < C.ECO_SCARCE_RATIO:
            self.eco_scarce[spot] = True
        elif self.eco_scarce.get(spot) and ratio >= C.ECO_RECOVER_RATIO:
            self.eco_scarce[spot] = False
            self.eco_recovered.add(spot)
