# -*- coding: utf-8 -*-
"""Sim — บันทึก ภาพรวม และการเดินโลก"""
from ._common import *  # noqa: F401,F403
from ._common import _REACH_CACHE, _PLACE_SETS, _CENTERS, _reach_from, _auction_q  # noqa: F401


class RecordsMixin:
    SNAP_FIELDS = ("ของในตัว", "สำนัก", "ตระกูล", "วิชา", "มิตร", "ศัตรู", "ศิษย์",
                   "อาจารย์", "โลก", "เป็นอยู่", "ขั้นนักปรุงยา", "ขั้นช่างตีเหล็ก",
                   "ความเสื่อม", "จิตมาร")

    @staticmethod
    def state_snap(ch):
        """ลายนิ้วมือสถานะของตัวละคร ณ วินาทีหนึ่ง — ทั้งหมดเป็น int เทียบเท่ากันได้ตรงๆ

        ใช้หา "จุดเปลี่ยนจริง" ด้วยการ diff กับเหตุการณ์ก่อนหน้าของคนเดียวกัน แทนการเดาจากสตริง
        outcome ซึ่งพิสูจน์แล้วว่าเชื่อไม่ได้ — "ทำนา/สำเร็จ" กับ "หลอมยา/สำเร็จ" ใช้คำเดียวกัน
        แต่อันหนึ่งไม่เปลี่ยนอะไรเลย

        สองตัวท้าย (ความเสื่อม/จิตมาร) ปัดเป็นขั้นหยาบๆ ไม่ให้ค่าทศนิยมขยับนิดเดียวแล้วนับเป็น
        จุดเปลี่ยน — แต่ยังบอกได้ว่าคนนี้กำลังโรยราหรือใจกำลังมืด ซึ่งบทสนทนาต้องรู้
        """
        return (len(ch.items),
                ch.org if ch.org is not None else -1,
                ch.clan,
                len(ch.skills),
                len(ch.bonds),
                len(ch.rivals),
                len(ch.disciples),
                ch.master_cid,
                ch.world_id,
                int(ch.alive),
                ch.alch_rank,
                ch.forge_rank,
                int(ch.decay * 2),
                int(ch.inner * 2))

    def bystanders(self, a, world):
        """คนอื่นที่ยืนอยู่ตรงนั้นด้วย — เปิดใช้ด้วย config.LOG_BYSTANDERS เท่านั้น

        ปกติ **ปิดไว้** เพราะต้องสแกนคนเป็นทั้งหมดทุกครั้งที่ emit (คนพันกว่าคน x แสนสี่หมื่นเหตุการณ์)
        ทำให้ซิมช้าลงราว 60% โดยที่ชั้นนิยายใช้จริงแค่ราว 20 ฉากต่อเรื่องเท่านั้น — ให้
        narrative_factory ประกอบย้อนหลังเอาเองจาก log จะถูกกว่ามาก (ดู scene_cast.py)
        """
        # `place` เป็น None ได้จริง ไม่ใช่แค่ -1 — ตัวละครบางกลุ่มถูกสร้างโดยยังไม่เคยถูกวาง
        # ตำแหน่ง (เผ่าโกลาหลที่ inner_none, ตัวที่เพิ่ง spawn ก่อน assign place) เช็คแค่ `< 0`
        # จึงระเบิดเป็น TypeError กลางรันยาว — เจอจริงตอนรัน 400,000 เหตุการณ์เพื่อดูการปะทะกับ
        # เจ้าโกลาหล ล้มทั้งซิมโดยที่รันสั้นๆ ไม่เคยเจอ
        if a is None or not getattr(C, "LOG_BYSTANDERS", False):
            return ()
        here = getattr(a, "place", None)
        if here is None or here < 0:
            return ()
        out = []
        for cid in self.alive_sorted():
            if cid == a.cid:
                continue
            c = self.cast[cid]
            if getattr(c, "place", None) == here and c.world_id == a.world_id:
                out.append(cid)
                if len(out) >= C.PRESENT_MAX:
                    break
        return tuple(out)

    # ผลลัพธ์ที่ "ตามคาด" กับที่ "เหลือเชื่อ" — ใช้ตอนที่ handler ไม่ได้ส่งความน่าจะเป็นมาให้
    # ตัวเลขมาจากการวัดสัดส่วนจริงของผลลัพธ์แต่ละแบบในโลก 50 ปี ไม่ได้ตั้งเอาเอง
    RARE_OUTCOMES = {
        "ตาย": 0.02, "ดับสูญ": 0.01, "จิตมารกลืน": 0.01, "ประหาร": 0.01,
        "รอดตายด้วยชะตา": 0.03, "เปิดสวรรค์": 0.002, "ข้ามฟ้า": 0.01,
        "ต่อวิชาโบราณสำเร็จ": 0.005, "ค้นพบ": 0.01, "พบชิ้นส่วนวิชา": 0.03,
        "เปลี่ยนชะตา": 0.01, "ชะตาลิขิต": 0.02, "จบสิ้น": 0.005,
        "เป็นไปตามนิมิต": 0.02, "ชะตาเปลี่ยนไป": 0.01,
    }

    def surprise_of(self, kind, outcome, d):
        """ความประหลาดใจของเหตุการณ์นี้ เป็นบิต (ดู physics.surprisal)

        ถ้า handler ส่งความน่าจะเป็นจริงมาใน d["p"] ก็ใช้ค่านั้น (แม่นที่สุด) ถ้าไม่ส่งมา
        ก็ประเมินจากความหายากของผลลัพธ์ที่วัดได้จากโลกจริง ส่วนผลลัพธ์ทั่วไปที่ไม่อยู่ในตาราง
        ถือว่าเกิดได้เป็นปกติ = แทบไม่มีค่าสารสนเทศ
        """
        p = d.get("p") if isinstance(d, dict) else None
        if not isinstance(p, (int, float)) or not (0.0 < p <= 1.0):
            p = self.RARE_OUTCOMES.get(outcome, C.COMMON_OUTCOME_P)
        return round(PHYS.surprisal(p), 2)

    def hops_between(self, a_place, b_place):
        """กี่ก้าวบนกราฟสถานที่ — แคชไว้ เพราะถูกถามทุกครั้งที่มีคนอาจได้ยินข่าว"""
        if a_place is None or b_place is None or a_place < 0 or b_place < 0:
            return 0
        if a_place == b_place:
            return 0
        key = (a_place, b_place) if a_place < b_place else (b_place, a_place)
        book = getattr(self, "_hops", None)
        if book is None:
            book = self._hops = {}
        if key in book:
            return book[key]
        try:
            dist = TR.distances_from(a_place)
            step = max(1.0, C.RUMOR_HOP_LENGTH)
            hops = int(round(dist.get(b_place, step * C.RUMOR_MAX_HOPS) / step))
        except Exception:
            hops = C.RUMOR_MAX_HOPS
        hops = max(0, min(C.RUMOR_MAX_HOPS, hops))
        book[key] = hops
        return hops

    def scarcity_of(self, world, name):
        """อุปสงค์/อุปทานของวัตถุดิบหนึ่งในแดนหนึ่ง — คืน (อุปสงค์, อุปทาน)

        ทั้งสองค่ามาจากของที่โลกนี้มีอยู่แล้ว ไม่ได้เพิ่มข้อมูลใหม่ให้ต้องดูแล
          อุปสงค์ = จำนวนคนในแดนที่ "กำลังตามหา" ของชิ้นนี้ (ch.wants)
          อุปทาน = จำนวนที่มีอยู่ในถุงของคนในแดน + ความสมบูรณ์ของแหล่งที่ยังขุดได้
        คิดใหม่วันละครั้งแล้วใช้ซ้ำ เพราะการวนคนทั้งแดนทุกครั้งที่มีคนค้าขายจะแพงเกินไป
        """
        book = getattr(self, "_price_day", None)
        if book != self.day:
            self._price_day = self.day
            self._price_cache = {}
        cache = getattr(self, "_price_cache", None)
        if cache is None:
            cache = self._price_cache = {}
        key = (world.wid, name)
        if key in cache:
            return cache[key]
        demand = supply = 0.0
        for c in self.living_in(world.wid):
            if getattr(c, "wants", None):
                demand += c.wants.get(name, 0)
            if getattr(c, "mat_stock", None):
                supply += c.mat_stock.get(name, 0)
        supply += C.MARKET_NATURAL_SUPPLY
        demand += C.MARKET_NATURAL_DEMAND
        cache[key] = (demand, supply)
        return cache[key]

    def price_now(self, world, name, base):
        """ราคา ณ วันนี้ของแดนนี้ — P = P₀·(D/S)^ε (ดู physics.scarcity_price)

        ก่อนหน้านี้ราคาวัตถุดิบเป็นค่าคงที่ในตาราง วัดจริงโลก 50 ปี: `ค้าขาย` 3,453 ครั้ง
        **ได้ผลลัพธ์เดียวกันหมด** คือคำว่า "ค้าขาย" ไม่มีกำไรขาดทุน ไม่มีอะไรให้ตัดสินใจ
        ทั้งที่ข้อมูลอุปสงค์อุปทานมีอยู่ครบแล้ว แค่ยังไม่มีใครเอามาคูณกัน
        """
        d0, s0 = self.scarcity_of(world, name)
        now = PHYS.scarcity_price(base, d0, s0, C.PRICE_ELASTICITY,
                                  C.PRICE_FLOOR, C.PRICE_CEILING)
        # ชั้นที่สอง: กฎของ Hotelling — ของที่ **กำลังจะหมด** แพงตั้งแต่ก่อนหมด
        # scarcity_price ตอบว่า "ตอนนี้ของขาดไหม" ซึ่งเป็นคนละคำถามกับ "ของกำลังจะหมดไหม"
        # ใช้ความสมบูรณ์เฉลี่ยของแหล่งที่ให้ของชิ้นนี้ในแดนเป็นตัวแทนปริมาณสำรอง
        # ผลที่ต้องการ: คนตุนของตั้งแต่ยังมี แทนที่จะมารู้ตัวตอนหยิบแล้วไม่มี
        reserve = self.reserve_frac(world, name)
        return PHYS.hotelling_price(now, reserve, C.HOTELLING_ELASTICITY,
                                    C.HOTELLING_LO, C.HOTELLING_HI)

    def reserve_frac(self, world, name):
        """สัดส่วนปริมาณสำรองที่เหลือของวัตถุดิบชิ้นหนึ่งในแดนหนึ่ง (0..1)

        คิดวันละครั้งเหมือน scarcity_of ด้วยเหตุผลเดียวกัน — วนแหล่งทั้งแดนทุกครั้งที่มี
        คนค้าขายจะแพงเกินไปในรันยาว
        """
        book = getattr(self, "_reserve_day", None)
        if book != self.day:
            self._reserve_day = self.day
            self._reserve_cache = {}
        cache = getattr(self, "_reserve_cache", None)
        if cache is None:
            cache = self._reserve_cache = {}
        key = (world.wid, name)
        if key in cache:
            return cache[key]
        sites = MAT.sites_of(name) if hasattr(MAT, "sites_of") else ()
        here = set(PL.places_in(world.place_key))
        vals = [self.eco_ratio(world.wid, idx) for idx in sites if idx in here]   # แหล่งในแดนนี้เท่านั้น
        cache[key] = (sum(vals) / len(vals)) if vals else 1.0
        return cache[key]

    def mark_bloodshed(self, world, place):
        """บันทึกรอยนองเลือด **ของสถานที่นั้น** — เชื้อไฟของวงจรแค้น

        ทำไมต้องเป็นรายสถานที่ ไม่ใช่รายแดน: ลองแบบรายแดนแล้ววัดได้ว่าสัมประสิทธิ์การกระจาย
        แทบไม่ขยับ (1.10 -> 1.05) เพราะทั้งแดนมีเหตุนองเลือดถี่พอที่ความร้อนจะ **ชนเพดาน
        ตลอดห้าสิบปี** ยุคสงบกับยุคนองเลือดจึงไม่ต่างกันเลย
        ความแค้นจริงเป็นเรื่องของ "แถบนั้น" — ฆ่ากันที่หุบเขาหนึ่ง ไม่ได้ทำให้อีกฟากของแดน
        ลุกเป็นไฟด้วย การผูกกับสถานที่จึงทำให้เกิดทั้งแถบที่เดือดและแถบที่สงบในเวลาเดียวกัน
        """
        if place is None or place < 0:
            return
        book = getattr(self, "blood_marks", None)
        if book is None:
            book = self.blood_marks = {}
        marks = book.setdefault(place, [])
        cut = self.day - C.FEUD_HALF_LIFE_DAYS * C.FEUD_KEEP_HALFLIVES
        marks[:] = [t for t in marks if t >= cut][-C.FEUD_MARK_CAP:]
        marks.append(self.day)

    def feud_heat(self, place):
        """ความร้อนของวงจรแค้น ณ สถานที่หนึ่ง (ดู physics.hawkes_intensity)"""
        book = getattr(self, "blood_marks", None)
        if not book or place is None or place < 0:
            return 0.0
        return PHYS.hawkes_intensity(0.0, book.get(place, ()), self.day,
                                     C.FEUD_ALPHA, C.FEUD_HALF_LIFE_DAYS)

    def _event_site(self, world, a, t):
        """(แดน, สถานที่, อาคาร) ที่เหตุการณ์เกิดจริง — สถานที่ต้องอยู่ในผังของแดนของเหตุการณ์เสมอ

        เดิมใช้แดนที่ผู้เรียกส่งมาแต่สถานที่ของผู้กระทำเสมอ เหตุการณ์ข้ามแดน (มารบุก โกลาหลบุกโลกมนุษย์ เกณฑ์ขึ้นฟ้า
        บัญชาสวรรค์ ลงโลกล่าง) จึงอ้างสถานที่ในแดนอื่น (test_world_coherence 3.2: 6,414 รายการใน seed 11–15)
        ลำดับ: ผู้กระทำอยู่ในแดนนั้น → ที่ของผู้กระทำ · ไม่งั้นผู้ถูกกระทำอยู่ในแดนนั้น → ที่ของผู้ถูกกระทำ (ที่ที่ถูกบุก)
        · ไม่งั้นเหตุเกิดตรงที่ผู้กระทำยืนอยู่ → แดนของผู้กระทำ (เช่นลงโลกล่างหลังย้ายแดนแล้ว)"""
        if a is None:
            # เหตุการณ์ระดับโลก (มหาผนึก ลางมหาศึก ยุคล่ม ...) เกิดกับทั้งแดน — แดนคือแดนที่ผู้เรียกส่งมา ที่เกิดคือศูนย์กลาง
            # ของแดนนั้น (สถานที่ที่เชื่อมสถานที่อื่นมากที่สุด) ทุกเหตุการณ์จึงบอกได้ว่าเกิดที่ไหน (test_world_coherence 3.3)
            return world, self._world_center(world), -1
        layout = self._places_of(world.place_key)
        if a.place is not None and a.place in layout:
            return world, a.place, a.building
        if t is not None and t.place is not None and t.place in layout:
            return world, t.place, t.building
        own = self.world(a.world_id)
        if a.place is not None and a.place in self._places_of(own.place_key):
            return own, a.place, a.building
        # ผู้กระทำไม่มีที่ยืนในผังของแดนไหนเลย (เช่น place ว่างระหว่างย้าย) — ใช้ศูนย์กลางของแดนเหมือนเหตุการณ์ระดับโลก
        # (test_world_coherence 3.3: สงครามสำนัก seed 11 วัน 59270 เคยได้ place -1)
        return world, self._world_center(world), -1

    def _world_center(self, world):
        """ศูนย์กลางของแดน: สถานที่ในผังที่มีเพื่อนบ้านห่างหนึ่งก้าวมากที่สุด (เท่ากันเอาเลขน้อย) — ผังคงที่ แคชระดับโมดูล"""
        key = world.place_key
        if key not in _CENTERS:
            layout = PL.places_in(key)
            _CENTERS[key] = max(layout, key=lambda p: (len(TR.places_within(self, p, 1)), -p)) if layout else -1
        return _CENTERS[key]

    @staticmethod
    def _places_of(key):
        """สถานที่ในผังหนึ่ง — ผังคงที่หลัง import (places.PLACES) แคชระดับโมดูล ไม่เก็บใน Sim (ไม่เข้าเซฟ)"""
        if key not in _PLACE_SETS:
            _PLACE_SETS[key] = frozenset(PL.places_in(key))
        return _PLACE_SETS[key]

    def emit(self, world, kind, a, t, tags, outcome, text, gap, d):
        self.seq += 1   # เดิม increment ที่ step() ครั้งเดียวต่อทิก แต่ step()เดียวเรียก emit() ได้
                         # มากกว่า 1 ครั้ง (เช่น เหตุการณ์ผลพวง) ทำให้ seq ซ้ำกันได้ — ย้ายมาที่นี่
                         # ให้ seq เป็น ID ไม่ซ้ำจริงต่อหนึ่ง Event เสมอ (พบจาก narrative_factory
                         # Phase E ที่ scene_id ชนกันเพราะ seq ซ้ำ)
        world, place, building = self._event_site(world, a, t)
        e = Event(seq=self.seq, day=self.day, gap_days=gap, world_id=world.wid,
                  era=world.era, kind=kind, actor=a.cid if a else -1,
                  target=t.cid if t else None, tags=list(tags),
                  outcome=outcome, text=text, deltas=d, place=place,
                  realm=a.realm if a else 0,
                  building=building,
                  present=self.bystanders(a, world),
                  surprise=self.surprise_of(kind, outcome, d),
                  snap=self.state_snap(a) if a else ())
        # ใจขยับตามสิ่งที่พบเจอ — วางไว้ที่ emit เพราะนี่คือ "คอขวดเดียว" ที่ทุกเหตุการณ์ในโลก
        # ต้องผ่าน (ไม่ว่าจะมาจาก resolve, เหตุการณ์ของโลก หรือผลพวง) จึงไม่มีทางหลุด
        # react() ไม่ใช้ rng เลย ความคงที่ของโลกจึงไม่เสีย และผู้ถูกกระทำรู้สึกคนละอย่างกับผู้ลงมือ
        # ทุกความตายที่มนุษย์ทำกับมนุษย์คือเชื้อไฟของวงจรแค้น — วางไว้ที่ emit เพราะนี่คือ
        # คอขวดเดียวที่ทุกเหตุการณ์ในโลกต้องผ่าน จึงไม่มีทางหลุด
        if outcome in C.BLOODY_OUTCOMES and kind in C.BLOODY_KINDS:
            self.mark_bloodshed(world, a.place if a is not None else -1)
        if a is not None:
            EM.react(a, kind, outcome, tags, self.day, role="actor")
        if t is not None and t is not a:
            EM.react(t, kind, outcome, tags, self.day, role="target")
        self.log.append(e)
        self.event_bus.publish(e, self)
        return e

    def step(self):
        """Advance one event and repair derived population counters after nested events.

        A single event can kill and reincarnate several characters (or create a
        beast and move people) after the normal 30-day recount has run. Keeping
        the counters exact at the event boundary makes autonomous repopulation
        and heaven inflow decisions independent of which event happened last.
        Crisis waves run on the world clock (see _world_tick), not per event.
        """
        seq0, deaths0 = self.seq, getattr(self, "death_seq", 0)
        event = self._step()
        if getattr(self, "death_seq", 0) > deaths0:
            self._announce_unrecorded_deaths(seq0, deaths0)
        if getattr(self, "_world_counts_dirty", False):
            self.recount_worlds()
            self._world_counts_dirty = False
        return event

    def _announce_unrecorded_deaths(self, seq0, deaths0):
        """ทุกความตายในก้าวนี้ต้องมีเหตุการณ์ในประวัติ — ถ้าไม่มีเหตุการณ์ของก้าวเดียวกันที่ผู้ตายเป็นผู้กระทำหรือผู้ถูกกระทำ
        หรือถูกเอ่ยชื่อในรายละเอียด (เช่น "ผู้ไม่ได้กลับออกมา" ของแดนลับต้นกำเนิด) ให้บันทึกเหตุการณ์ "สิ้นชีพ" หนึ่งรายการ

        เดิมหลายทางฆ่าโดยไม่ emit (ล่าสัตว์อสูรในป่าหมื่นอสูร, R.fight จากผู้เรียกที่ไม่บันทึกผล) คนจึงหายจากประวัติ
        โดยมีแค่ DeathRecord (test_world_coherence 2.1: สัตว์อสูร 7,166 คน 2,616 ใน seed 11–15) — แก้ที่จุดเดียวที่ทุกก้าวผ่าน
        ไม่ใช่ไล่แก้ทีละทาง ทางฆ่าที่เพิ่มในอนาคตจึงไม่หลุด ไม่ใช้เลขสุ่ม"""
        recent = []
        for e in reversed(self.log):
            if e.seq <= seq0:
                break
            recent.append(e)
        named = {cid for e in recent for cid in (e.actor, e.target) if cid is not None}
        details = " ".join(str(v) for e in recent for v in (e.deltas or {}).values())
        fresh = []
        for rec in reversed(getattr(self, "deaths", [])):
            if rec.death_id <= deaths0:
                break
            fresh.append(rec)
        for rec in reversed(fresh):
            dead = self.cast[rec.cid]
            if rec.cid in named or (dead.name and dead.name in details):
                continue
            killer = self.cast[rec.killer] if 0 <= rec.killer < len(self.cast) else None
            text = f"{dead.name}สิ้นชีพ — {rec.cause}"
            # ผู้ลงมือบันทึกในรายละเอียด ไม่ใช่ผู้ถูกกระทำ: เหตุการณ์นี้เป็นเรื่องของผู้ตายคนเดียว ผู้ลงมืออาจอยู่ที่อื่นแล้ว
            # (เป็น target จะกลายเป็น "คู่กรณีข้ามระยะที่ไม่มีเหตุผล" ใน test_locality)
            # บันทึกด้วยวันที่ตายจริง — ก้าวเดียวกันอาจเลื่อนวันของโลกไปแล้ว (รอบโลกทำงานหลังความตาย) ตั้งก่อน emit
            # เพื่อให้ความจำของผู้ที่ได้รับเหตุการณ์ (brain.remember ใน event_bus) ได้วันเดียวกับใน log
            today, self.day = self.day, rec.day
            try:
                ev = self.emit(self.world(rec.world_id), "สิ้นชีพ", dead, None, [], "ตาย", text, 0,
                               {"สาเหตุ": rec.cause, "ผู้ลงมือ": killer.name if killer else "-",
                                "ผู้ลงมือ_cid": str(rec.killer)})
            finally:
                self.day = today
            if ev.place < 0:                 # ตายกลางทาง: ที่เดียวกับที่มรดกไร้ผู้รับตกไป (estate_spot)
                wid, spot = self.estate_spot(dead)
                if wid == ev.world_id:
                    ev.place = spot
            named.add(rec.cid)

    def run(self, n):
        self.last_run_steps = 0
        for _ in range(n):
            if self.step() is None:
                break
            self.last_run_steps += 1
        return self
