# -*- coding: utf-8 -*-
"""Sim — ของ / แดนลับ"""
from ._common import *  # noqa: F401,F403
from ._common import _REACH_CACHE, _PLACE_SETS, _CENTERS, _reach_from, _auction_q  # noqa: F401


class ItemsMixin:
    # ------------------------------------------------------------ ของ / แดนลับ
    def make_item(self, kind, tier, grade, maker=None):
        it = Item(iid=self.nid("i"), kind=kind, tier=tier, grade=grade, maker=maker)
        # config.ITEM_GRADES นิยามชื่อชั้นไว้ 4 ชั้นแต่ไม่เคยถูกใช้ — ของจึงชื่อว่า "อาวุธชั้น 3"
        gname = C.ITEM_GRADES[min(len(C.ITEM_GRADES) - 1, tier + (1 if grade >= 2.0 else 0))]
        it.name = f"{kind}{gname}"
        if kind == "ยาวิเศษ":
            it.lifespan_bonus = CR.longevity_years(it.name, tier, grade)
        self.items[it.iid] = it
        return it

    def stash_relic(self, ch, rng):
        """ของที่ผู้เก็บตัวทิ้งไว้ในแดนลับ — คัมภีร์หรือยันต์ (config.MANUALS_AND_TALISMANS)

        ตรงกับกฎของโลกที่ว่า "คนระดับสูงที่ไปต่อไม่ได้มักหาที่ซ่อนตัว ทำแดนลับ ทิ้งสมบัติปิดผนึกไว้"
        ก่อนหน้านี้ตารางคัมภีร์/ยันต์ถูกนิยามไว้แต่ไม่มีทางใดในเกมที่จะได้มันมาเลย
        """
        cats = list(C.MANUALS_AND_TALISMANS.items())
        if not cats:
            return None
        cat, names = rng.choice(cats)
        kind = C.TALISMAN_KIND if cat.startswith("ยันต์") else "คัมภีร์"
        it = self.make_item(kind, min(ch.tier, 2), 1.0 + 0.5 * ch.realm / 9.0, maker=ch.cid)
        it.name = rng.choice(names).split(" (")[0]
        return it

    def sect_territory(self, org):
        """อาณาเขตของสำนัก = ผลรวมความหนาแน่นปราณของที่ที่ศิษย์ยืนอยู่จริง

        จงใจไม่เพิ่ม field "ดินแดนที่ครอง" ให้ Org เพราะข้อมูลนั้นมีอยู่แล้วในตำแหน่งของ
        สมาชิก และการนิยามแบบนี้ทำให้ **การแผ่อิทธิพลเป็นผลของพฤติกรรม ไม่ใช่ตัวเลขที่ตั้ง**
        สำนักที่ส่งศิษย์ไปยึดหุบเขาปราณหนาก็รวยขึ้นจริง สำนักที่หดตัวอยู่ในสำนักก็จนลงเอง
        นับที่ละแห่งครั้งเดียว (ส่งคนไปกระจุกที่เดิมร้อยคนไม่ได้อาณาเขตเพิ่ม) และจำกัดจำนวน
        แห่งไว้ ไม่งั้นสำนักที่สมาชิกกระจายทั่วแดนจะกลายเป็นเจ้าของทั้งโลกโดยไม่ต้องรบ
        """
        w = self.world(org.world_id)
        seen = {}
        cast_len = len(self.cast)
        for cid in org.members:
            if not (0 <= cid < cast_len):
                continue
            m = self.cast[cid]
            # อาณาเขตอยู่ในแดนของสำนัก — ศิษย์ที่อยู่แดนอื่นถือเลขสถานที่ของผังอื่น (เดิมสร้างคีย์คลังข้ามแดน)
            if not m.alive or m.place is None or m.place < 0 or m.world_id != org.world_id:
                continue
            if m.place not in seen:
                seen[m.place] = self.qi_density(m.place, w)
        if not seen:
            return 0.0
        top = sorted(seen.values(), reverse=True)[:C.SECT_TERRITORY_CAP]
        return float(sum(top))

    def sect_dues(self, org):
        """ค่าบำรุงสำนัก: สมาชิกจ่าย SECT_DUES_RATE ของเงินตัวเองเข้าคลังทองของสำนัก (org.treasury_gold ตามชั้น)
        แล้วคลังแจก SECT_PAYOUT_RATE ของแต่ละชั้นให้ศิษย์สายแกน สายใน สายนอก 40/40/20 — เฉพาะศิษย์ที่อยู่แดนชั้นนั้น
        (ทองชั้นไหนใช้ได้ในแดนชั้นนั้น) กลุ่มที่ไม่มีใครรับ ส่วนนั้นค้างอยู่ในคลัง

        เดิมค่าบำรุงเข้า org.treasury ซึ่งเป็นตัวเลขเดียวรวมทุกชั้นและอยู่นอก wages.total_gold ส่วนแจกปัดลงด้วย int()
        และส่วนของกลุ่มที่ไม่มีศิษย์ถูกหักออกไปเฉยๆ ทองหายรอบละราว 160–175 เหรียญ (seed 11 ก้าวที่ 12,000)
        org.treasury ที่ค้างจากเซฟเก่าคงไว้ตามเดิม ทองก้อนนั้นหลุดจากบัญชีไปตั้งแต่ก่อนแก้ ไม่นำกลับเข้ามาเสกเพิ่ม"""
        cast = self.cast
        purse = org.__dict__.setdefault("treasury_gold", {})
        for cid in org.members:
            if not (0 <= cid < len(cast)) or not cast[cid].alive:
                continue
            mem = cast[cid]
            tier = self.world(mem.world_id).tier
            due = mem.money.get(tier, 0.0) * C.SECT_DUES_RATE
            if due > 0:
                mem.money[tier] = mem.money.get(tier, 0.0) - due
                purse[tier] = purse.get(tier, 0.0) + due
        pools = ((0.4, getattr(org, "core_disciples", [])), (0.4, getattr(org, "inner_disciples", [])),
                 (0.2, getattr(org, "outer_disciples", [])))
        for tier in sorted(purse):
            payout = purse[tier] * C.SECT_PAYOUT_RATE
            if payout <= 0:
                continue
            for share, group in pools:
                live = [cast[c] for c in group if 0 <= c < len(cast) and cast[c].alive
                        and self.world(cast[c].world_id).tier == tier]
                if not live:
                    continue
                each = payout * share / len(live)
                for m in live:
                    m.money[tier] = m.money.get(tier, 0.0) + each
                purse[tier] -= each * len(live)

    def sect_mine(self, org):
        """สำนักขุดปราณจากอาณาเขตของตนเข้าคลัง แล้วตกผลึกเป็นหินวิญญาณแจกศิษย์

        ผลผลิตมาจาก economy.sect_output (คอบบ์-ดักลาส) และ **ถูกหักจากคลังฟ้าของแดนจริง**
        ถ้าคลังไม่พอก็ได้เท่าที่มี ซึ่งแปลว่าในยุคเสื่อมสำนักจนลงพร้อมกันทั้งแดน
        โดยไม่ต้องเขียนเหตุการณ์ "เศรษฐกิจตกต่ำ" แยก
        """
        w = self.world(org.world_id)
        out = EC.sect_output(sum(1 for cid in org.members
                                 if 0 <= cid < len(self.cast) and self.cast[cid].alive),
                             self.sect_territory(org))
        got = min(out, w.extractable())
        if got <= 0:
            org.monthly_resource = 0.0
            return 0.0
        w.heaven -= got
        org.treasury_qi = getattr(org, "treasury_qi", 0.0) + got
        org.monthly_resource = got
        # แจกออกตามลำดับชั้นศิษย์ ส่วนที่เหลือค้างคลังไว้เป็นทุนของสำนัก
        share_out = org.treasury_qi * C.SECT_PAYOUT_RATE
        org.treasury_qi -= share_out
        grade = min(len(EC.GRADE_NAMES) - 1, w.tier)
        for pool, group in ((0.4, getattr(org, "core_disciples", [])),
                            (0.4, getattr(org, "inner_disciples", [])),
                            (0.2, getattr(org, "outer_disciples", []))):
            live = [cid for cid in group
                    if 0 <= cid < len(self.cast) and self.cast[cid].alive]
            if not live:
                continue
            each = share_out * pool / len(live)
            for cid in live:
                EC.add_stones(self.cast[cid], grade, EC.mint(each, grade))
        return got

    def on_realm_fall(self, ch, steps, qi_year):
        """ขั้นหล่นเพราะเลี้ยงตัวไม่ไหว — บันทึกไว้ให้เห็น ไม่ใช่หล่นเงียบๆ

        ถ้าไม่ emit ออกมา ตัวละครจะอ่อนลงโดยที่ทั้งผู้เขียนและชั้นจิตใจไม่รู้ว่าเกิดอะไร
        ซึ่งเป็นบั๊กคลาสเดียวกับ "กลไกที่ไม่มี outcome แยก" ที่เคยทำให้ถ่ายทอดวิชาตายไป
        สองพันครั้งโดยไม่มีใครรู้
        """
        w = self.world(ch.world_id)
        d = {"ปราณที่หาได้ต่อปี": f"{qi_year:.2f}",
             "ที่ยืน": f"{self.place_name(ch)} เลี้ยงได้ถึงขั้น "
                       f"{EC.place_ceiling(self.qi_density(ch.place, w)):.1f}",
             "หินวิญญาณที่เหลือ": f"{EC.purse_qi(ch):.1f} หน่วยปราณ"}
        self.emit(w, "ขั้นถดถอย", ch, None, ("ถดถอย",), "ยึดขั้นไม่อยู่",
                  f"{ch.name}เลี้ยงปราณในกายไว้ไม่ไหว ขั้นถดถอยลง {steps} ขั้น "
                  f"เหลือ{ch.realm_name()}", 0, d)

    def qi_field(self):
        """ดาวของจักรวาลนี้ — D(p) = R + A·F(p̂ + λW(p̂)) - ‖p‖ (ดู noise.Planet)

        สร้างครั้งเดียวต่อซิม ไม่ใช้ rng หลัก จึงเป็นฟังก์ชันบริสุทธิ์ของ (seed, ทิศ) เท่านั้น
        โลกที่โหลดจากเซฟคนละจุดได้ดาวดวงเดียวกันเสมอ
        """
        f = getattr(self, "_qi_field", None)
        if f is None:
            f = self._qi_field = NZ.Planet(
                seed=getattr(self, "seed", 0) ^ 0x91F1_0000,
                radius=C.PLANET_RADIUS, amp=C.PLANET_AMP,
                lam=C.PLANET_LAMBDA, octaves=C.PLANET_OCTAVES,
                warp_octaves=C.PLANET_WARP_OCTAVES)
        return f

    def place_dir(self, place_idx):
        """ทิศของสถานที่บนผิวดาว p̂ — ฉายจากพิกัดแผนที่ระนาบขึ้นทรงกลม"""
        if place_idx is None or not (0 <= place_idx < len(GEO.COORDS)):
            return (0.0, 0.0, 1.0)
        x, y = GEO.COORDS[place_idx]
        return NZ.sphere_dir(x, y, C.PLANET_SPAN)

    def place_surface(self, place_idx):
        """รัศมีของผิวดาวที่สถานที่นี้ = R + A·F(p̂ + λW(p̂)) — คิดครั้งเดียวแล้วจำไว้"""
        book = getattr(self, "_surf_cache", None)
        if book is None:
            book = self._surf_cache = {}
        v = book.get(place_idx)
        if v is None:
            d = self.place_dir(place_idx)
            v = book[place_idx] = self.qi_field().surface_radius(
                *d, scale=C.PLANET_SCALE)
        return v

    def place_sdf(self, place_idx, radial=0.0):
        """D(p) ที่สถานที่นี้ — บวก = ฝังอยู่ใต้ผิว · ลบ = ลอยอยู่เหนือผิว

        `radial` คือระยะที่สถานที่นั้นอยู่ห่างจากผิวตามแนวรัศมี (เป็นสัดส่วนของ A)
        นี่คือที่ที่ "เกาะสวรรค์ลอยฟ้า" กับ "แดนลับที่ถูกผนึกใต้ดิน" มีตัวเลขจริงของตัวเอง
        แผนที่ความสูงให้ค่าได้ค่าเดียวต่อพิกัด จึงแทนห้องใต้ดินหรือเกาะลอยไม่ได้เลย
        """
        surf = self.place_surface(place_idx)
        return surf - (surf + radial * C.PLANET_AMP)

    def qi_field_at(self, place_idx):
        """ความเข้มของเส้นปราณที่สถานที่นี้ (0..1) — คิดครั้งเดียวต่อสถานที่แล้วจำไว้

        ใช้ F(p̂ + λW(p̂)) ตัวเดียวกับที่กำหนดความสูงของภูมิประเทศ **โดยเจตนา**
        ในโลกนี้ภูเขาคือที่ที่ปราณโผล่ ไม่ใช่สองเรื่องที่เกิดขึ้นแยกกัน — และเพราะสนามถูกบิด
        (λW) เส้นระดับของมันจึงเป็น **เส้นใยยาว** ไม่ใช่หยดกลม ซึ่งคือรูปร่างของ "เส้นปราณ
        ของแผ่นดิน" ที่คนตามรอยไปได้ วัดจริงที่ค่าที่ใช้อยู่: λ=0 ได้เส้นขอบ 3,060 หน่วย
        · λ=1 ได้ 4,569 ที่พื้นที่เท่ากัน = ยาวขึ้น 1.49 เท่า

        พิกัดของสถานที่คงที่ตลอดการรัน ค่าสนามจึงคงที่ด้วย ต่างจาก eco ที่เปลี่ยนตามการขุด
        การแยกสองอย่างนี้ทำให้ "ที่นี่ปราณหนาโดยธรรมชาติ" กับ "ที่นี่ถูกขุดจนโทรม"
        อ่านแยกกันได้ — ที่ปราณหนาที่ถูกขุดพังยังฟื้นกลับมาหนาได้
        """
        book = getattr(self, "_qi_field_cache", None)
        if book is None:
            book = self._qi_field_cache = {}
        v = book.get(place_idx)
        if v is None:
            if place_idx is None or not (0 <= place_idx < len(GEO.COORDS)):
                v = 0.5
            else:
                d = self.place_dir(place_idx)
                # F คืน -1..1 · แปลงเป็น 0..1 ที่นี่ครั้งเดียว
                v = 0.5 + 0.5 * self.qi_field().height(*d, scale=C.PLANET_SCALE)
            book[place_idx] = max(0.0, min(1.0, v))
        return book[place_idx]

    def qi_density(self, place_idx, world):
        """ความหนาแน่นของปราณฟ้าดิน ณ จุดหนึ่ง — ตัวเลขที่สำคัญที่สุดในโลกนี้

        มันตัดสินว่าใครยึดขั้นไหนไว้ได้ (economy.place_ceiling) เวลาในถ้ำเดินเร็วแค่ไหน
        (physics.time_dilation) และสำนักไหนรวย (economy.sect_output) จึงสมควรมาจาก
        **ภูมิศาสตร์จริงที่ต่างกันทุกเมล็ด** ไม่ใช่เลข 0/1/2 ที่พิมพ์ไว้ในตาราง

        สี่ปัจจัย:
          · **สนามปราณ** — Perlin ที่พิกัดของที่นี่ ต่างกันทุก seed และ **หนาแน่นเป็นแถบ
            ต่อเนื่อง** เพราะ noise มีสหสัมพันธ์เชิงพื้นที่ หุบเขาข้างกันจึงหนาไปด้วยกัน
            ซึ่งเป็นสิ่งที่การสุ่มรายจุดให้ไม่ได้ และเป็นเหตุผลที่ "ครองดินแดน" มีความหมาย
          · เกรดที่เขียนด้วยมือ (0-2) — เจตนาของผู้เขียนว่าที่นี่ควรเป็นแดนศักดิ์สิทธิ์หรือ
            ทุ่งร้าง เก็บไว้เป็น **อคติ** ไม่ใช่คำตัดสิน สนามเป็นตัวปรับขึ้นลงจากฐานนั้น
          · ชั้นของแดน — โลกระดับสูงปราณบริสุทธิ์และหนาแน่นกว่า (กฎเดิมของโลก)
          · สัดส่วนนิเวศที่เหลือ — ถูกขุดจนโทรม ปราณก็บางลงตาม (เปลี่ยนได้ ต่างจากสามข้อแรก)
        """
        pv = PL.PLACES[place_idx] if 0 <= place_idx < len(PL.PLACES) else None
        grade = pv[2] if pv else 0
        eco = self.eco_ratio(world.wid, place_idx) if place_idx is not None and place_idx >= 0 else 1.0
        field = self.qi_field_at(place_idx)
        # สนาม 0 -> คูณ (1-W) · สนาม 1 -> คูณ (1+W) · สนาม 0.5 -> คูณ 1 พอดี
        # เขียนแบบนี้เพื่อให้ W = 0 คืนพฤติกรรมเดิมเป๊ะ ปรับกลับได้ถ้าไม่ชอบ
        shape = 1.0 - C.QI_FIELD_W + 2.0 * C.QI_FIELD_W * field
        # การขุดทำให้ปราณบางลง แต่ **ไม่เท่ากับที่มันทำให้ของหมด**
        # ของเดิมคูณ eco เข้าไปตรงๆ (ช่วง 0.2-1.5 = ต่างกัน 7.5 เท่า) ซึ่งกลบสนามภูมิศาสตร์
        # (ช่วง 0.5-1.5 = 3 เท่า) จนหมด วัดจริงปีที่ 55: ที่ที่คนกระจุกทุกแห่งมีเพดานติดลบ
        # ทั้งที่ตอนปีที่ 0 หุบเขาโอสถหลวงเลี้ยงได้ถึงขั้น 4.8 — ภูมิศาสตร์ของเมล็ดถูกลบทิ้ง
        # ด้วยเรื่องว่าคนไปกระจุกที่ไหน
        #
        # แยกสองเรื่องออกจากกัน: สมุนไพรกับแร่หมดได้จริงและหมดเร็ว ส่วนปราณฟ้าดินเป็น
        # คุณสมบัติของแผ่นดิน มันบางลงเมื่อถูกดูดหนัก แต่ไม่ถึงกับหายไป — และฟื้นกลับมา
        # หนาได้เมื่อคนย้ายไป ส่วนที่ปราณบางโดยธรรมชาติจะขุดหรือไม่ขุดก็บางอยู่วันยังค่ำ
        wear = 1.0 - C.QI_ECO_W + C.QI_ECO_W * max(0.0, min(1.5, eco))
        return ((grade + 1) * C.QI_PER_GRADE * shape
                * (1.0 + C.QI_PER_TIER * world.tier)
                * wear)

    def make_cache(self, ch, faked):
        k = Cache(kid=self.nid("k"), world_id=ch.world_id, owner=ch.cid,
                  owner_name=ch.name, sealed_day=self.day,
                  seal=C.SEAL_BASE * (0.5 + 0.25 * ch.realm),
                  items=list(ch.items), trap=faked, era_sealed=self.world(ch.world_id).era)
        for tier in sorted(ch.money):                  # ทองทุกชั้นย้ายเข้าแดนลับ (ยังนับในบัญชีทอง) ไม่ใช่หายไป
            if ch.money[tier] > 0:
                k.gold[tier] = ch.money.pop(tier)
        # ผู้เก็บตัวมักจารึกวิชาหรือวางยันต์ทิ้งไว้ให้คนยุคหลัง
        if self.rng.random() < C.CACHE_RELIC_P:
            relic = self.stash_relic(ch, self.rng)
            if relic is not None:
                k.items.append(relic.iid)
        ch.items = []
        self.caches.append(k)
        return k

    def ruin_deposit(self, w):
        """ทองที่ยังเหลือในซากของแดน `w` — ตั้งทุกแดนครั้งแรกที่มีคนค้น แบ่งตามคนในแดน (แหล่งกำเนิดที่ประกาศ `ruin_genesis`)
        แล้วเพิ่มเมื่อแดนลับถูกเปิด (ทองส่วนที่เสื่อมตามผนึกตกค้างอยู่ในซาก) ไม่มีวันเกิดเพิ่มเอง"""
        gold = self.__dict__.setdefault("ruin_gold", {})
        if not gold:
            # ตั้งทุกแดนพร้อมกันครั้งแรกที่มีคนค้น: ทองรวมของแต่ละชั้น (RUIN_GOLD_DEPOSIT × (1 + ชั้น) ต่อแดน) แบ่งตามจำนวนคนในแดน
            # วัดแล้วถ้าแบ่งเท่ากันทุกแดน แดนที่คนค้นมากหมดในไม่กี่ปี ขณะที่ราวแสนทองค้างในแดนที่ไม่มีใครค้น
            by_tier = collections.defaultdict(list)
            for x in self.worlds:
                by_tier[x.tier].append(x)
            for tier, worlds in sorted(by_tier.items()):
                total = C.RUIN_GOLD_DEPOSIT * (1 + tier) * len(worlds)
                pops = [len(self.living_in(x.wid)) for x in worlds]
                people = sum(pops)
                for x, n in zip(worlds, pops):
                    gold[x.wid] = total * (n / people if people else 1.0 / len(worlds))
                    WAGES.record(self, "ruin_genesis", tier, gold[x.wid])
        return gold.setdefault(w.wid, 0.0)

    def ruined_cache_find(self, ch, rng, d):
        """ชั้นเล็กที่สุดของการค้นแดนลับ — ซากแดนลับที่ถูกกวาดไปก่อนหน้าแล้ว

        ทำไมต้องมี: "แดนลับมีของเสมอ ต่างกันแค่มากหรือน้อย" เป็นกฎของโลกนี้ ผลลัพธ์ "ไม่พบ"
        จึงเป็นสิ่งที่ไม่ควรมีตั้งแต่แรก วัดจริงก่อนแก้ — ค้นแดนลับ 4,693 ครั้งจบด้วย "ไม่พบ"
        99% และในบันทึกผู้มีจิตใจปีที่ 118-129 จบด้วย "ไม่พบ" 13/13 ครั้ง คิดเป็น 13% ของ
        การตัดสินใจทั้งหมดของตัวเอกที่หายไปกับการออกไปเสี่ยงตายแล้วกลับมามือเปล่า

        ของที่ได้ผูกกับ **ชะตา** ของคนค้น ไม่ใช่สุ่มล้วน — "ผู้มีวาสนา" ได้มากกว่าคนธรรมดา
        ที่ยืนอยู่จุดเดียวกัน ซึ่งเป็นกติกาเดิมของโลกอยู่แล้ว (ดู FRAGMENT_FATE_BONUS)
        และเขียนของลงใน `d` ให้บันทึกเห็นว่าได้อะไรกลับมาบ้าง
        """
        w = self.world(ch.world_id)
        luck = 1.0 + C.RUIN_CORES_FATE * max(0, getattr(ch, "fate", 0))
        # หางหนัก: ซากส่วนใหญ่เหลือของก้นถุง แต่นานๆ ครั้งมีคนเจอของที่คนก่อนหน้ามองข้าม
        # ของเดิมใช้ randint ซึ่งแบนราบ — "แดนลับมีของเสมอ" จึงกลายเป็น "ได้เท่ากันทุกครั้ง"
        # มีพื้นไว้ เพราะ "แดนลับมีของเสมอ" และเพราะถ้าปล่อยให้ตัวคูณลงไปใกล้ศูนย์ได้
        # มันจะกลบผลของชะตาจนหมด — ผู้มีวาสนากับคนธรรมดาจะได้เท่ากันที่ปลายล่าง
        rich = max(C.RUIN_MIN_MULT,
                   PHYS.lognormal_value(1.0, C.RUIN_VALUE_SIGMA, rng.random()))
        luck *= rich
        cores = max(1, int(round(rng.randint(*C.RUIN_CORES) * luck)))
        if rich >= C.RUIN_JACKPOT:
            d["วาสนา"] = f"ซากนี้ยังไม่มีใครค้นถึงก้น — ได้ของมากกว่าปกติ {rich:.1f} เท่า"
        ch.cores += cores
        d["เก็บตกจากซาก"] = f"แก่นพลัง×{cores}"

        gain = rng.uniform(*C.RUIN_INSIGHT) * luck
        ch.insight += gain
        d["อ่านรอยจารึกที่เหลืออยู่"] = f"ความเข้าใจ +{gain:.1f}"

        # เหรียญในซากมาจากกองทองของซากในแดนนี้ (`ruin_gold`) ซึ่งมีจำกัด หมดแล้วก็ไม่มีอีก (B3c) — เดิมเสกจากอากาศราว 7,800 ทองต่อปี
        coins = min(int(rng.randint(*C.RUIN_MONEY) * luck), self.ruin_deposit(w))
        if coins > 0:
            self.ruin_gold[w.wid] -= coins
            ch.money[w.tier] = ch.money.get(w.tier, 0) + coins
            d["เหรียญทองที่ร่วงอยู่"] = f"{coins:,}"
        # หินวิญญาณที่คนก่อนหน้าทำหล่นไว้ — **ไม่หักจากคลังฟ้า** เพราะปราณก้อนนี้ถูกขุด
        # ออกจากโลกไปแล้วตั้งแต่รุ่นก่อน มันแค่เปลี่ยนมือ ถ้าหักซ้ำคือทำบัญชีพัง
        stones = C.RUIN_STONES * luck
        if stones > 0:
            grade = min(len(EC.GRADE_NAMES) - 1, w.tier)
            ch_stones = EC.mint(stones, grade)
            EC.add_stones(ch, grade, ch_stones)
            d["หินวิญญาณที่ตกค้าง"] = f"{EC.grade_name(grade)} ×{ch_stones:.1f}"

        if ch.mat_stock is not None and rng.random() < C.RUIN_MAT_P:
            pool = MAT.materials_at(ch.place)
            if pool:
                m = rng.choice(list(pool))
                ch.mat_stock[m] = ch.mat_stock.get(m, 0) + 1
                d["ของที่ติดมือกลับมา"] = m

        # ร่องรอยที่ชี้ไปยังแดนลับจริง — ทำให้การค้นครั้งนี้ "พาไปสู่ครั้งหน้า" แทนที่จะจบลอยๆ
        sealed = [c for c in self.caches if c.world_id == w.wid and not c.opened]
        if sealed and rng.random() < C.RUIN_LEAD_P:
            k = rng.choice(sealed)
            leads = [l for l in getattr(ch, "rumor_leads", [])
                     if not (l["kind"] == "แดนลับ" and l["subject"] == k.kid)]
            leads.append({"kind": "แดนลับ", "subject": k.kid, "true": True})
            ch.rumor_leads = leads[-C.RUMOR_LEAD_MAX:]
            d["ร่องรอยที่พบ"] = f"จารึกชี้ทางไปแดนลับของ{k.owner_name} — ผนึกยังไม่คลาย"
            return "พบซากแดนลับ", (f"{ch.name}พบซากแดนลับที่ถูกกวาดไปนานแล้วที่"
                                   f"{self.place_name(ch)} เก็บของที่ตกค้างและอ่านเจอ"
                                   f"จารึกชี้ทางไปยังแดนลับของ{k.owner_name}")
        return "พบซากแดนลับ", (f"{ch.name}พบซากแดนลับที่ถูกกวาดไปนานแล้วที่"
                               f"{self.place_name(ch)} เหลือเพียงของที่ตกค้างให้เก็บ")

    def open_cache(self, ch, k, rng):
        """เปิดแดนลับ — ของในนั้นต้องไปถึงมือใครสักคนเสมอ ไม่งั้นมันหายจากโลกถาวร

        บั๊กเดิมสามชั้นซ้อน วัดจริงที่ปีที่ 946: สมบัติฟ้าดิน 27 ชิ้นมีคนถืออยู่แค่ 6 ชิ้น
          1. ตั้ง k.opened = True **ก่อน** เช็คกับดัก แล้ว return ออกไปโดยไม่แจกของเลย
             แดนลับนั้นจึงถูกทำเครื่องหมายว่าเปิดแล้ว ไม่มีใครมาเปิดอีก ของข้างในหายถาวร
             — วัดได้ 24 ชิ้นค้างแบบนี้
          2. แจกของแล้วไม่เคยล้าง k.items ทำให้สมบัติชิ้นเดียวถูกบันทึกอยู่ในหลายแดนลับ
             พร้อมกัน ข่าวลือจึงชี้ไปที่แดนลับที่ว่างเปล่าได้
          3. ของที่ผุจนต่ำกว่าเกณฑ์ถูกทิ้งไว้เฉยๆ รวมถึงสมบัติฟ้าดินที่มีชื่อ ซึ่งขัดกับกฎของ
             โลกที่ว่ามันไม่มีวันสูญหาย
        """
        d = {}
        if k.trap and self.cast[k.owner].alive:
            owner = self.cast[k.owner]
            owner.hidden = False
            win, lose, margin, res = R.fight(self, self.world(ch.world_id), owner, ch, rng)
            d["กับดัก"] = f"{owner.name}แกล้งตายรออยู่ — {lose.name}{res}"
            d["margin"] = round(margin, 3)
            d["winner"] = win.cid
            if win is not ch:
                # เจ้าของกับดักชนะ — ผนึกยังอยู่ ของยังอยู่ในนั้น รอผู้มีวาสนาคนต่อไป
                d["ผนึก"] = "ยังไม่ถูกเปิด รอคนต่อไป"
                return d
            d["ผนึก"] = "ผู้บุกฝ่ากับดักเข้าไปได้"
        k.opened = True
        rot = 1.0 - min(1.0, max(0.0, -R.seal_left(k, self.day) / C.SEAL_BASE)) * C.CACHE_ROT
        got, rotted = 0, 0
        for iid in k.items:
            it = self.items.get(iid)
            if it is None:
                continue
            it.condition *= rot
            if it.legend:
                # สมบัติฟ้าดินที่มีชื่อไม่ผุจนใช้ไม่ได้ และต้องถึงมือผู้เปิดเสมอ
                it.condition = max(it.condition, 0.35)
                ch.items.append(iid)
                got += 1
            elif it.condition > 0.15:
                ch.items.append(iid)
                got += 1
            else:
                rotted += 1
                self.items.pop(iid, None)     # ผุจนสูญสลาย ออกจากโลกอย่างเป็นทางการ
        k.items = []                          # ของออกจากแดนลับแล้ว ห้ามค้างชื่อไว้ซ้ำ
        # ทองที่ผนึกไว้ถึงผู้เปิดตามชั้นเดิม ส่วนที่เสื่อมตามผนึก (rot) หายไป — เดิมตั้ง k.currency = 0 ก่อนอ่าน ผู้เปิดจึงได้ศูนย์ทุกครั้ง
        # และ currency รวมทุกชั้นเป็นก้อนเดียว
        here = self.world(k.world_id)
        for tier, gold in sorted(k.gold.items()):
            ch.money[tier] = ch.money.get(tier, 0.0) + gold * rot
            if tier == here.tier:                     # ส่วนที่เสื่อมตกค้างเป็นเหรียญในซากของแดนนี้ (B3c)
                self.ruin_deposit(here)
                self.ruin_gold[here.wid] += gold * (1.0 - rot)
            else:                                     # ทองต่างชั้นใช้ในซากของแดนนี้ไม่ได้ — หายไปกับผนึก
                WAGES.record(self, "cache_rot", tier, -gold * (1.0 - rot))
        if k.gold:
            d["ทองในแดนลับ"] = f"{sum(k.gold.values()) * rot:,.1f}"
        k.gold = {}
        d["แดนลับ"] = f"มรดกของ{k.owner_name}จากยุคที่ {k.era_sealed} — ได้ของ {got} ชิ้น"
        if rotted:
            d["ผุสูญสลาย"] = f"{rotted} ชิ้น"
        return d

    def reseal_lost_legends(self):
        """กฎเหล็กของโลก: สมบัติฟ้าดินที่มีชื่อไม่มีวันสูญหาย — บังคับให้เป็นจริงเสมอ

        แทนที่จะไล่อุดทีละทางที่ของอาจหลุดออกจากโลก (ตายในศึกที่ไม่ผ่าน kill · สถานที่ถูกถล่ม ·
        แดนลับที่เปิดแล้วแต่ไม่มีใครรับของ) ตรวจ**ผลลัพธ์**เป็นรอบแล้วผนึกกลับคืน ทางไหนที่ยัง
        รั่วอยู่ในอนาคตก็จะถูกจับได้ด้วยตัวเดียวกันนี้ วัดจริงที่ปีที่ 946: มี 2 ชิ้นหายจากโลกไป
        เฉยๆ ไม่อยู่กับใคร ไม่อยู่ในแดนลับไหนเลย
        """
        held = set()
        for c in self.cast:
            if c.alive:
                held.update(c.items)
        sealed = set()
        open_caches = []
        for k in self.caches:
            if k.opened:
                open_caches.append(k)
            else:
                sealed.update(k.items)
        lost = [iid for iid in self.legend_iids
                if iid in self.items and iid not in held and iid not in sealed]
        if not lost:
            return 0
        rng = self.rng
        w = self.worlds[0]
        k = Cache(kid=self.nid("k"), world_id=w.wid, owner=-1,
                  owner_name="ผู้วางฟ้าดิน", sealed_day=self.day,
                  seal=C.SEAL_BASE, items=list(lost),
                  trap=False, era_sealed=w.era)
        self.caches.append(k)
        names = " · ".join(self.items[i].name for i in lost[:5])
        self.emit(w, "สมบัติฟ้าดินหวนคืนผนึก", None, None, ["หลอมรวม"], "ผนึกกลับคืน",
                  f"สมบัติฟ้าดิน {len(lost)} ชิ้นที่ขาดผู้ครองถูกฟ้าดินผนึกกลับสู่แดนลับ "
                  f"รอผู้มีวาสนาคนต่อไป", 0,
                  {"สมบัติที่หวนคืน": names,
                   "กฎที่บังคับ": "สมบัติฟ้าดินที่มีชื่อไม่มีวันสูญหาย"})
        return len(lost)

    def seed_skill_fragments(self):
        """วิชาแก้ทางเผ่าโกลาหลของเดิมหายากเกินไป — แยกเป็นชิ้นส่วนฝังไว้ทั่วโลกมนุษย์แทน
        ใครมีโชคก็เจอได้โดยไม่ต้องรอขั้นสูง ต่อครบจึงตรัสรู้วิชาสมบูรณ์ทันที"""
        rng = self.rng
        homes = PL.places_in(0)   # กระจายเฉพาะในโลกมนุษย์เท่านั้น
        if not homes:
            return
        for name, _cat, _tier, _grade, _desc, anti_chaos in SK.SKILLS:
            if not anti_chaos:
                continue
            for piece in range(C.FRAGMENTS_PER_SKILL):
                self.skill_fragments.append({
                    "fid": self.nid("f"), "skill": name, "piece": piece,
                    "place": rng.choice(homes), "found": False,
                })
