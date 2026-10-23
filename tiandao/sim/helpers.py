# -*- coding: utf-8 -*-
"""Sim — ตัวช่วยทั่วไป"""
from ._common import *  # noqa: F401,F403
from ._common import _REACH_CACHE, _PLACE_SETS, _CENTERS, _reach_from, _auction_q  # noqa: F401


class HelpersMixin:
    # ------------------------------------------------------------ helpers
    def place_name(self, ch):
        return PL.PLACES[ch.place][0] if ch.place >= 0 else "ที่ใดสักแห่ง"

    def place_of(self, ch):
        if ch.place < 0:
            return None
        if self.ruined.get(ch.place, 0) > self.day:
            p = PL.PLACES[ch.place]
            return (p[0] + " (ซากปรักหักพัง)", p[1], p[2], "ซากปรักหักพัง", None, -1)
        return PL.PLACES[ch.place]

    def route_to_building(self, ch, building_types):
        """เช็คว่าตัวละครยืนอยู่ในอาคารประเภทที่ต้องการภายใน place ปัจจุบันหรือยัง — คืน True ถ้าใช่ (ทำ
        กิจกรรมต่อได้เลย) ถ้ายัง ตั้ง building_dest/building_arrival_day ให้เดินไปแล้วคืน False (ผู้เรียกควร
        return ทันทีให้ตัวละครเดินก่อน — เหมือน resolve() ของ "เดินทาง" ที่แค่ตั้ง travel_dest แล้วคืนเลย
        ไม่ทำอะไรต่อ ปล่อยให้ step()/การนัดตื่นครั้งถัดไปจัดการที่เหลือ)"""
        if SETTLE.building_type_of(ch.place, ch.building) in building_types:
            return True
        target = SETTLE.find_building_of_type(ch.place, building_types)
        if target is None:
            return True  # เมืองนี้ไม่มีอาคารประเภทนี้เลย — ปล่อยให้ตรรกะระดับ place เดิมตัดสินใจต่อ
        ch.building_dest = target
        ch.building_arrival_day = self.day + C.SETTLEMENT_TRAVEL_DAYS
        return False

    def nid(self, k):
        self.next_id[k] += 1
        return self.next_id[k] - 1

    def world(self, wid):
        return self.worlds[wid]

    def living(self):
        # เรียง cid เสมอ — set ของ Python ให้ลำดับที่ต่างออกไปหลัง pickle/unpickle ผลคือรันต่อ
        # จาก save แล้วโลกเดินคนละทางกับรันรวดเดียว ทั้งที่ seed เดียวกัน (rng.choice เลือกตามลำดับ)
        return [self.cast[cid] for cid in self.alive_sorted()]

    def pick_destination(self, actor, options, rng):
        """เลือกจุดหมายโดยถ่วงระยะทาง — ที่ใกล้มีโอกาสมากกว่า แต่ที่ไกลไม่ได้ถูกตัดขาด

        เดิมใช้ rng.choice(options) ตรงๆ วัดจริงแล้วระยะที่เลือกไปเฉลี่ย 90.5 หน่วย เทียบกับ
        ค่าเฉลี่ยของ "ทุกที่ที่ไปได้" 90.6 หน่วย = อัตราส่วน 1.00 พอดี ไม่มีความลำเอียงเลย
        ภูมิศาสตร์จึงเป็นแค่ค่าผ่านทางที่จ่ายทีหลัง ไม่ได้กำหนดว่าใครจะไปไหน ผลคือไม่มี
        "ภูมิภาค" ไม่มีเพื่อนบ้าน ทุกคนกระจายทั่วแผนที่เท่ากันหมด

        ระยะที่ยอมไปโตตามความเร็วเดินทางจริง (ขั้นสูงเหาะเร็วกว่า โลกจึงเล็กลงสำหรับเขา)
        และผู้พเนจรยอมไปไกลกว่าคนอื่นตามวิถีของตัวเอง
        """
        if not options:
            return None
        if len(options) == 1 or actor.place < 0:
            return rng.choice(options)
        dist = TR.distances_from(actor.place)
        scale = C.TRAVEL_PREF_RANGE * (TR.travel_speed(actor.realm, character=actor)
                                       / C.TRAVEL_BASE_SPEED)
        if actor.archetype == "ผู้พเนจร":
            scale *= C.TRAVEL_PREF_WANDERER
        weights = []
        for p in options:
            d = dist.get(p)
            weights.append(0.0 if d is None else math.exp(-d / max(1e-6, scale)))
        total = sum(weights)
        if total <= 0.0:
            return rng.choice(options)
        r, acc = rng.random() * total, 0.0
        for p, w in zip(options, weights):
            acc += w
            if r <= acc:
                return p
        return options[-1]

    def social_pool(self, actor, world, rng):
        """คนที่ actor "พบได้จริงตอนนี้" — ไม่ใช่ทุกคนที่ยังไม่ตายทั้งโลก

        เดิมใช้ living_in(world.wid) ตรงๆ ผลคือคนสองคนที่ห่างกันครึ่งแผนที่ (วัดจริงเฉลี่ย 145
        หน่วย ทั้งที่เดินทาง 90 หน่วยกินเวลา ~28 วัน) ชิงสมบัติ ล้างแค้น รับเป็นศิษย์ หรือมีทายาท
        ร่วมกันได้โดยไม่มีใครขยับ — ตำแหน่งจึงไม่มีความหมายทางสังคมเลย

        ที่นี่กรองด้วยระยะทางจริงบนกราฟ: อยู่ที่เดียวกัน = เจอแน่นอน ไกลออกไปโอกาสลดแบบ
        exponential ตาม SOCIAL_RANGE ส่วนคนที่ผูกพันกันอยู่แล้ว (สำนัก ตระกูล ศิษย์-อาจารย์
        มิตร ศัตรูที่จองเวรกัน) ติดต่อกันได้ไกลกว่า เพราะมีเหตุให้ตามหากันข้ามแดน
        """
        # คนที่ "หายไปจากโลก" ติดต่อไม่ได้ — ฤๅษีที่ซ่อนตัวสร้างแดนลับ และนักโทษที่ถูกคุมขัง
        # (วัดจริงหลังใส่ระบบคุมขัง: ยังมีคนเดินไปถ่ายทอดวิชาและให้คำมั่นสัญญากับคนที่อยู่ในคุก)
        everyone = [c for c in self.living_in(world.wid)
                    if c.cid != actor.cid and not getattr(c, "hidden", False)
                    and c.age(self.day) >= 14]
        if actor.place < 0 or not everyone:
            return everyone
        reach = _reach_from(actor.place)

        local, linked, far = [], [], []
        for c in everyone:
            if c.place < 0:
                continue
            if c.place == actor.place:
                local.append(c)
                continue
            p = reach.get(c.place)
            if p is None:
                continue            # ไปไม่ถึงกันบนกราฟ = ไม่มีทางเจอ
            personal = (c.cid in actor.bonds or c.cid in actor.rivals
                        or c.cid == actor.master_cid or c.cid in actor.disciples)
            same_org = ((actor.org is not None and actor.org == c.org)
                        or (actor.clan >= 0 and actor.clan == c.clan))
            if personal or same_org:
                # ศัตรูที่จองเวรหรือศิษย์ที่หนีไป ตามหากันข้ามแดนได้ไกล — นั่นคือเรื่อง
                # แต่ "แค่สังกัดสำนักเดียวกัน" ไม่ควรแปลว่าคุยกันได้ทั้งแผ่นดิน สำนักที่มีศิษย์
                # เป็นร้อยจะกลืนความหมายของตำแหน่งไปหมด จึงให้เอื้อมได้สั้นกว่ามาก
                reach_mult = C.SOCIAL_BOND_REACH if personal else C.SOCIAL_ORG_REACH
                if rng.random() < min(1.0, p * reach_mult):
                    linked.append(c)
            elif rng.random() < p:
                far.append(c)

        # คนที่อยู่ตรงหน้ามาก่อนเสมอ — ถ้ามีคนแถวนี้ คนไกลที่ไม่ได้เกี่ยวข้องอะไรด้วยไม่ควรถูกหยิบ
        # (ถ้าเอาทุกคนมารวมกัน คนไกลจะท่วมคนใกล้ด้วยจำนวน เพราะมีสถานที่หลายร้อยแห่ง)
        if local or linked:
            return local + linked
        # ไม่มีใครอยู่แถวนี้เลย — คนสันโดษกลางป่ายังพอมีโอกาสเจอคนผ่านทาง
        return far

    def alive_sorted(self):
        """cid ของคนเป็นทั้งหมด เรียงแล้ว — แคชไว้ เพราะถูกเรียกทุก emit และทุก living_in()

        ต้องเรียงเสมอ (ไม่ใช่วนบน set ตรงๆ) เพราะลำดับของ set เปลี่ยนหลัง pickle/unpickle ทำให้
        รันต่อจาก save แล้วโลกเดินคนละทาง — ดู test_determinism.py
        """
        cache = getattr(self, "_alive_cache", None)
        if cache is None or cache[0] != getattr(self, "_alive_ver", 0):
            cache = (getattr(self, "_alive_ver", 0), sorted(self.alive_cids))
            self._alive_cache = cache
        return cache[1]

    def _ripe_cache_worlds(self):
        """แดนที่มีแดนลับผนึกเสื่อมพร้อมให้เข้าไปค้น — คิดใหม่วันละครั้ง ใช้ร่วมกันทั้งวัน"""
        # ผนึกเสื่อมช้ามาก (SEAL_DECAY_PER_YEAR) ค้างไว้ 30 วันไม่ทำให้ผลต่างในทางปฏิบัติ
        c = getattr(self, "_ripe_cache", None)
        if c is not None and self.day - c[0] < 30:
            return c[1]
        ready = set()
        day = self.day
        for k in self.caches:
            if not k.opened and k.world_id not in ready and R.seal_left(k, day) <= 0:
                ready.add(k.world_id)
        self._ripe_cache = (day, ready)
        return ready

    def _fragment_places(self):
        """สถานที่ที่ยังมีเศษวิชาตกค้างอยู่ — คิดใหม่วันละครั้งเช่นกัน"""
        c = getattr(self, "_frag_cache", None)
        if c is not None and self.day - c[0] < 30:
            return c[1]
        places = {f["place"] for f in self.skill_fragments if not f["found"]}
        self._frag_cache = (self.day, places)
        return places

    def living_in(self, wid):
        """คนเป็นในแดนหนึ่ง — จัดกลุ่มไว้ทั้งจักรวาลครั้งเดียวแล้วใช้ซ้ำ

        โปรไฟล์จริง 40,000 เหตุการณ์: บรรทัด list comprehension เดิมกิน **44 วินาทีจาก 100**
        คือ 44% ของเวลาทั้งซิม เพราะ social_pool() เรียกมันทุกเหตุการณ์ และแต่ละครั้งวนคนเป็น
        ทั้งจักรวาล 3,700 คนเพื่อคัดเอาแดนเดียว พอมี 126 แดน งานนี้เลยกลายเป็นงานหลักของซิม

        แคชนี้ใช้เงื่อนไขเดียวกับ alive_sorted() คือถือว่า "ยังใช้ได้" ตราบใดที่ลิสต์คนเป็นยัง
        เป็นอ็อบเจกต์เดิม (เทียบด้วย `is` ไม่ใช่ ==) บวกตัวนับการย้ายแดน ซึ่ง move_world() เป็น
        ที่เดียวที่เปลี่ยน world_id ของคนเป็น ส่วนการเกิด/ตายเปลี่ยนความยาว alive_cids อยู่แล้ว
        ลำดับที่คืนออกไปยังเรียงตาม cid เหมือนเดิมเป๊ะ — ดู test_determinism.py
        """
        lst = self.alive_sorted()
        ver = getattr(self, "_world_move_ver", 0)
        if getattr(self, "_wi_src", None) is not lst or getattr(self, "_wi_ver", -1) != ver:
            idx = {}
            cast = self.cast
            for cid in lst:
                c = cast[cid]
                if c.sentient:
                    idx.setdefault(c.world_id, []).append(c)
            self._wi, self._wi_src, self._wi_ver = idx, lst, ver
        # ต้องคืน **สำเนา** — ผู้เรียกหลายที่ทำ .sort() กับผลลัพธ์ตรงๆ (เช่น chaos_raid)
        # ถ้าคืนลิสต์ในแคชไปเลย การเรียงนั้นจะไปทำลายลำดับ cid ของแคช แล้วรอบต่อไปที่ใครก็ตาม
        # ขอแดนเดียวกันจะได้ลำดับที่ต่างออกไป = โลกเดินคนละทาง ทั้งที่ seed เดียวกัน
        got = self._wi.get(wid)
        return list(got) if got else []
