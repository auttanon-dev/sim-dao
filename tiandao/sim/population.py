# -*- coding: utf-8 -*-
"""Sim — ประชากร: เกิด ตั้งชื่อ เติมคน"""
from ._common import *  # noqa: F401,F403
from ._common import _REACH_CACHE, _PLACE_SETS, _CENTERS, _reach_from, _auction_q  # noqa: F401


class PopulationMixin:
    # ------------------------------------------------------------ ประชากร
    def roll_blood(self, world):
        rng = self.rng
        if world.kind == "mara":
            b = {"mara": rng.uniform(0.7, 1.0), "human": rng.uniform(0, 0.2),
                 "demon": rng.uniform(0, 0.2), "spirit": 0.0}
        else:
            r = rng.random()
            if r < 0.70:      # มนุษย์ — เยอะแต่อ่อนแอ
                b = {"human": rng.uniform(0.8, 1.0), "spirit": rng.uniform(0, 0.1),
                     "demon": rng.uniform(0, 0.1), "mara": rng.uniform(0, 0.05)}
            elif r < 0.80:    # ผสมวิญญาณ
                b = {"human": rng.uniform(0.4, 0.7), "spirit": rng.uniform(0.3, 0.6),
                     "demon": 0.0, "mara": 0.0}
            elif r < 0.88:    # ผสมอสูร
                b = {"human": rng.uniform(0.4, 0.7), "demon": rng.uniform(0.3, 0.6),
                     "spirit": 0.0, "mara": 0.0}
            elif r < 0.93:    # สัตว์วิญญาณสายบริสุทธิ์ — น้อยมาก
                b = {"spirit": rng.uniform(0.9, 1.0), "human": 0.0,
                     "demon": rng.uniform(0, 0.1), "mara": 0.0}
            elif r < 0.98:    # อสูร
                b = {"demon": rng.uniform(0.85, 1.0), "spirit": rng.uniform(0, 0.15),
                     "human": 0.0, "mara": 0.0}
            else:             # มนุษย์มาร
                b = {"human": rng.uniform(0.4, 0.6), "mara": rng.uniform(0.4, 0.6),
                     "spirit": 0.0, "demon": 0.0}
        return R.normalize(b)

    def unique_name(self, name, old=None, marker="ที่"):
        """ชื่อต้องไม่ซ้ำกับใครในจักรวาล — ถ้าซ้ำให้เติมพยางค์/ลำดับให้ต่างกัน

        ทำไม: รันจริงเจอมารชื่อ "เซียวจื่อ" กินคน ขณะที่ผู้มีจิตใจชื่อเดียวกันมีชีวิตอยู่มา 68 ปี
        อ่านบันทึกแล้วแยกไม่ออกว่าใครเป็นใคร ซึ่งทำลายคุณค่าของบันทึกในฐานะวัตถุดิบนิยาย
        ไม่ใช้ RNG: วนเติมแบบกำหนดได้ เพื่อไม่ให้ลำดับสุ่มของโลกเปลี่ยนไปจากการตั้งชื่อ
        """
        used = getattr(self, "used_names", None)
        if used is None:
            used = self.used_names = {c.name for c in getattr(self, "cast", ())}
        if old:
            used.discard(old)
        base = (name or "ผู้ไร้นาม").strip()
        if base not in used:
            used.add(base)
            return base
        ordinal = marker != "ที่" or " " in base    # ชื่อมีช่องว่าง/ชื่อสัตว์ = ต่อพยางค์แล้วอ่านไม่เป็นชื่อ
        for i, extra in enumerate(E.GIVEN):
            cand = f"{base} {marker} {i + 2}" if ordinal else base + extra
            if cand not in used:
                used.add(cand)
                return cand
        if not ordinal:
            # พยางค์เดียวหมดแล้ว (ชื่อฐานนี้ถูกใช้ครบ 20 แบบ) — ลองสองพยางค์ ยังอ่านเป็นชื่อคน
            # ดีกว่า "หลัวจื่อ ที่ 4" ที่เจอในรันจริง
            for a in E.GIVEN:
                for b in E.GIVEN:
                    cand = base + a + b
                    if cand not in used:
                        used.add(cand)
                        return cand
        n = 2
        while f"{base} {marker} {n}" in used:
            n += 1
        cand = f"{base} {marker} {n}"
        used.add(cand)
        return cand

    def spawn(self, world, age_years=0):
        rng = self.rng
        pkey = world.place_key
        dao = rng.choice(list(C.DAO_POOL.keys()))
        if pkey == "siam":
            if rng.random() < 0.5: dao = "วิถีมวยไทย"
            name = f"{rng.choice(E.THAI_GIVEN)} {rng.choice(E.THAI_SURNAME)}"
            tribe = "ชาวสยาม"
        elif pkey == "fusang":
            if rng.random() < 0.5: dao = "วิถีดาบ"
            name = f"{rng.choice(E.JAPAN_SURNAME)} {rng.choice(E.JAPAN_GIVEN)}"
            tribe = "ชาวอาทิตย์อุทัย"
        elif pkey == "steppe":
            if rng.random() < 0.5: dao = "วิถีแห่งลม"
            name = f"{rng.choice(E.STEPPE_SURNAME)} {rng.choice(E.STEPPE_GIVEN)}"
            tribe = "ชาวทุ่งหญ้า"
        elif pkey == "oasis":
            if rng.random() < 0.5: dao = "วิถีแห่งดวงดาว"
            name = f"{rng.choice(E.ARAB_GIVEN)} {rng.choice(E.ARAB_SURNAME)}"
            tribe = "ชาวโอเอซิส"
        elif pkey == "bharata":
            if rng.random() < 0.5: dao = "วิถีความว่าง"
            name = f"{rng.choice(E.VEDIC_GIVEN)} {rng.choice(E.VEDIC_SURNAME)}"
            tribe = "ชาวชมพูทวีป"
        else:
            name = rng.choice(E.SURNAME) + rng.choice(E.GIVEN)
            tr_r, tr_acc, tribe = rng.random(), 0.0, "ชาวตงหยวน"
            for t, p in getattr(C, "TRIBES", [("ชาวตงหยวน", 1.0)]):
                tr_acc += p
                if tr_r <= tr_acc:
                    tribe = t
                    break

        r, acc, origin = rng.random(), 0.0, "ชาวบ้าน"
        for o, p in E.ORIGINS:
            acc += p
            if r <= acc:
                origin = o
                break
        blood = self.roll_blood(world)
        
        # Gender and Personality
        # ทุกคนมีเพศ — ร่างกายมนุษย์อยู่เสมอทุกเผ่า (ผู้ใช้ตัดสิน กฎข้อ 5) เดิมอสูร ≥ 0.9 สุ่ม "ไม่มีเพศ" ได้ · ทอยครั้งเดียวเท่าเดิม
        gender = rng.choice(["ชาย", "หญิง"])
        fear = round(rng.uniform(0.1, 0.9), 2)
        greed = round(rng.uniform(0.1, 0.9), 2)
        compassion = round(rng.uniform(0.1, 0.9), 2)
        # ทะเยอทะยาน/ภักดี เคยเป็นค่าคงที่ 50 ทั้งโลก (models.py) ทุกคนจึงเหมือนกันหมด และเงื่อนไข
        # ที่โค้ดอื่นเขียนรอไว้ก็เป็นเท็จตลอดกาล: "มารสิงสู่" ต้องการ ambition > 80 (ไม่มีวันจริง)
        # ส่วนดราม่าศิษย์เนรคุณหลังข้ามขั้นต้องการ ambition - loyalty > 30 (ก็ได้ 0 เสมอ)
        # วัดจริง 60,000 เหตุการณ์: is_demon = 0 คน และเหตุการณ์บัญชาสวรรค์ 0 ครั้ง
        ambition = rng.randint(10, 95)
        loyalty = rng.randint(10, 95)
        
        # City (only applicable for tier 1)
        city_id = -1
        if world.tier == 1 and self.cities:
            city = rng.choice(self.cities)
            city_id = city["id"]
        ch = Character(
            cid=self.nid("c"),
            name=name,
            world_id=world.wid, dao=dao, dao_tags=list(C.DAO_POOL[dao]),
            born_day=self.day - age_years * 365,
            natural_lifespan=0,           # สุ่มท้าย spawn เมื่อรู้ขั้นแล้ว — ต้องรอดมาถึงอายุตอนสร้าง (R.natural_lifespan)
            blood=blood,
            fate=rng.randint(C.FATE_MIN, C.FATE_MAX), origin=origin,
            gender=gender, fear=fear, greed=greed, compassion=compassion,
            ambition=ambition, loyalty=loyalty,
            body_seed=self.seed,        # ร่างกายสร้างกลับมาได้จาก (seed, cid) — ดู tiandao/body/
            body_age=float(age_years),  # อายุทางสรีรวิทยาเดินต่อด้วย body.adaptation.tick
            # เผ่าวิญญาณศักดิ์สิทธิ์: เดิม `is_spirit` ไม่เคยถูกตั้งเป็น True ที่ไหนเลยทั้งโปรเจกต์
            # สายเลือดวิญญาณมีอยู่จริง (วัดจริง 51 คนเลือดบริสุทธิ์ จาก 1,253 คน) แต่ "เผ่า" ในเชิง
            # พฤติกรรมไม่เคยมีอยู่ — บล็อกบัญชาสวรรค์ที่เขียนไว้จึงไม่เคยทำงานสักครั้ง
            is_spirit=blood.get("spirit", 0.0) >= C.BLOOD_RACE_AT,
            tribe=tribe, city_id=city_id
        )
        ch.traits = IN.pick_traits(rng)
        ch.bloodline_affinity = {
            line: round(rng.uniform(C.BLOODLINE_AFFINITY_MIN, C.BLOODLINE_AFFINITY_MAX), 4)
            for line, share in blood.items() if share > 0.0
        }
        if rng.random() < 0.05:
            ch.traits.append("พรสวรรค์")
            
        # Apply tribe traits
        if tribe == "เผ่าเหมียว" and "ผู้ใช้พิษ" not in ch.traits: ch.traits.append("ผู้ใช้พิษ")
        if tribe == "เผ่าเร่ร่อน" and "สายแข็งแกร่ง" not in ch.traits: ch.traits.append("สายแข็งแกร่ง")
        if tribe == "เผ่าทิเบต" and "จิตวิญญาณลี้ลับ" not in ch.traits: ch.traits.append("จิตวิญญาณลี้ลับ")
        if tribe == "เผ่าคนป่า" and "สายสัญชาตญาณ" not in ch.traits: ch.traits.append("สายสัญชาตญาณ")
        if tribe == "ชาวอุยกูร์" and "เจ้าเล่ห์" not in ch.traits: ch.traits.append("เจ้าเล่ห์")
            
        # Profession
        prof_r, prof_acc, prof = rng.random(), 0.0, "ชาวนา"
        for p_name, p_prob in getattr(C, "PROFESSIONS", [("ผู้ฝึกตน", 1.0)]):
            prof_acc += p_prob
            if prof_r <= prof_acc:
                prof = p_name
                break
        ch.profession = prof
        
        ch.archetype = IN.pick_archetype(ch, rng)
        ch.inner_none = rng.random() < C.INNER_NONE_P
        ch.inner_art = (not ch.inner_none) and rng.random() < C.INNER_ART_P
        # อสูรระดับต่ำยังไม่มีจิตนึกคิด พอแก่กล้าจึงมี
        if blood.get("demon", 0) >= C.BLOOD_RACE_AT and age_years < 60:
            ch.sentient = False
        if ch.race() == "อสูร" and rng.random() < C.UNIQUE_BEAST_CHANCE:
            ch.is_unique_beast = True
            ch.unique_title = rng.choice(C.UNIQUE_BEAST_TITLES)
            ch.realm = min(C.REALM_CAP, ch.realm + 2)
            ch.peak_realm = ch.realm
            ch.sentient = True
        if origin in ("ศิษย์สำนัก", "ทายาทตระกูล") and age_years > 14:
            ch.realm = rng.randint(1, 2)
            ch.peak_realm = max(ch.peak_realm, ch.realm)
        ch.tier = world.tier
        ch.peak_tier = max(ch.peak_tier, ch.tier)   # เกิดในแดนชั้นสูง — ขั้นสูงสุดต้องไม่ต่ำกว่าขั้นปัจจุบัน (seed 42: 10,706 คน)
        pl = PL.places_in(world.place_key)
        ch.place = self.rng.choice(pl) if pl else -1
        # ทายาทตระกูล = เกิดในตระกูลจริง มีบ้านเป็นสถานที่ของตระกูล
        if origin == "ทายาทตระกูล" and world.kind != "chaos":
            cl = CL.clans_in(world.place_key)
            if cl:
                ch.clan = self.rng.choice(cl)
                home = CL.CLANS[ch.clan][4]
                for i, pp in enumerate(PL.PLACES):
                    if pp[0] == home:
                        ch.place = i
                        break
                if pkey == "siam":
                    ch.name = f"{self.rng.choice(E.THAI_GIVEN)} " \
                        f"{CL.CLANS[ch.clan][0].replace('ตระกูล', '').strip()}"
                elif pkey == "fusang":
                    ch.name = f"{CL.CLANS[ch.clan][0].replace('ตระกูล', '').strip()} " \
                        f"{self.rng.choice(E.JAPAN_GIVEN)}"
                elif pkey == "steppe":
                    ch.name = f"{CL.CLANS[ch.clan][0].replace('ตระกูล', '').strip()} " \
                        f"{self.rng.choice(E.STEPPE_GIVEN)}"
                elif pkey == "oasis":
                    ch.name = f"{self.rng.choice(E.ARAB_GIVEN)} " \
                        f"{CL.CLANS[ch.clan][0].replace('ตระกูล', '').strip()}"
                elif pkey == "bharata":
                    ch.name = f"{self.rng.choice(E.VEDIC_GIVEN)} " \
                        f"{CL.CLANS[ch.clan][0].replace('ตระกูล', '').strip()}"
                else:
                    ch.name = CL.CLANS[ch.clan][0].replace("ตระกูล", "") + \
                        self.rng.choice(E.GIVEN)
                if CL.CLANS[ch.clan][2] == 2 and age_years > 14:
                    ch.realm = min(C.REALM_CAP, ch.realm + CL.HEIR_HEADSTART)
                    ch.peak_realm = ch.realm
        # อายุขัยพื้น: มีเงื่อนไขว่ารอดมาถึงอายุตอนสร้าง — lifespan() ตอนนี้คือโบนัสขั้นล้วน (natural_lifespan ยังเป็น 0)
        ch.natural_lifespan = R.natural_lifespan(rng.random(), age_years - ch.lifespan())
        # ใจของคนคนนี้ — สุ่มหลังนิสัย/วิถี/ลักษณะพิเศษถูกตั้งครบแล้ว เพราะ roll() อ่านค่าพวกนั้น
        # ไปกำหนดทิศของอารมณ์และปรารถนา (คนขลาดกลัวจะ 'กลัว' สูงจริง ไม่ขัดกันเอง)
        ch.birth_wid = world.wid
        EM.roll(ch, rng)
        # ธาตุประจำตัว — สืบจากพ่อแม่ก่อน ที่เหลือคือสิ่งที่ฟ้าให้มา (ดู tiandao/elements.py)
        _par = [self.cast[i] for i in getattr(ch, "parents", ()) if 0 <= i < len(self.cast)]
        EL.roll(ch, rng, _par)
        ch.name = self.unique_name(ch.name)
        ch.last_day = self.day
        # ขั้นสูงสุดต้องไม่ต่ำกว่าขั้นที่เกิดมามี — เส้นทางสร้างคนหลายทางตั้ง realm โดยไม่ตั้ง peak_realm (seed 42: 4,488 คน หลังแก้ peak_tier)
        ch.peak_tier = max(ch.peak_tier, ch.tier)
        ch.peak_realm = max(ch.peak_realm, ch.realm)
        self.cast.append(ch)
        self.alive_cids.add(ch.cid)
        self._alive_ver = getattr(self, "_alive_ver", 0) + 1
        self._world_counts_dirty = True
        world.n_alive += 1
        if ch.realm == 0:
            world.n_mortal += 1
        self.apply_bloodline_buff(ch)
        ch.came_of_age = age_years >= 14       # ผู้ใหญ่ที่เติมเข้ามาไม่มีวัยเด็กในโลกนี้ให้สรุป
        HH.found(self, ch)                     # ทารกย้ายเข้าครัวเรือนของผู้ปกครองตอน guardians.assign
        self.schedule(ch, rng.randint(30, 900))
        return ch

    def schedule(self, ch, gap):
        heapq.heappush(self.queue, (self.day + max(1, gap), ch.cid))

    def _childhood_turn(self, child, world, elapsed, rng):
        """เทิร์นของเด็กอายุต่ำกว่า 14 — กิจวัตรตามวัยอยู่ที่ tiandao/childhood.py ไม่เข้าเมนูของผู้ใหญ่"""
        return CHILD.turn(self, child, world, elapsed, rng)

    def realm_target(self, world):
        """ขนาดที่แดนนี้เติมคนเข้ามาจนถึง (repopulate) — ฐานของเพดานการเกิด POP_K_MULT เท่า"""
        if world.kind == "chaos":
            return C.CHAOS_POP
        if getattr(world, "skill_line", None):
            # แดนสาขาโตได้ไม่เกินขนาดของตัวเอง — ถ้าปล่อยให้เติมถึง CAST_SIZE เหมือนแดนหลัก
            # 108 สาขาจะกลายเป็นประชากร 16,200 คน (วัดจริง: พุ่งจาก 3,944 เป็น 9,751 ใน 5 ปี
            # แล้วยังไม่หยุด) ซึ่งกลบแดนหลักจนโลกทั้งใบเป็นเรื่องของสาขาไปหมด
            return C.BRANCH_CAST
        if world.wid == 0:
            return C.HOME_CAST                       # เวทีหลัก — คนต้องแน่นพอจะมีเรื่องกัน
        return C.CAST_SIZE if world.kind == "mortal" else C.CAST_SIZE // 3

    def fertility(self, world):
        """โอกาสตั้งครรภ์เมื่อคู่หนึ่งพยายามมีทายาทในแดนนี้ — เต็มที่จนถึงขนาดที่แดนเติมคนถึง แล้วลดเป็นเส้นตรง
        จนเป็นศูนย์ที่เพดาน K = POP_K_MULT เท่าของขนาดนั้น แดนที่คนล้นจึงเกิดช้าลงเอง ไม่ใช่ตัดทิ้งทันที"""
        target = self.realm_target(world)
        cap = C.POP_K_MULT * target
        return max(0.0, min(1.0, (cap - world.n_alive) / max(1.0, cap - target)))

    def repopulate(self, world, elapsed):
        if world.kind == "chaos":
            target = C.CHAOS_POP
            deficit = target - world.n_alive
            if deficit > 0 and self.rng.random() < PHYS.hazard_p(C.CHAOS_SPAWN_PER_YEAR, elapsed):
                ch = self.spawn(world, self.rng.randint(100, 800))
                ch.chaos_rank = 0
                ch.blood = {"chaos": 1.0}
                ch.inner_none = True
                ch.realm = C.REALM_CAP
                ch.peak_realm = ch.realm
            return
        if len(self.alive_cids) >= C.POP_CEILING:
            return          # ทั้งจักรวาลคนถึงเพดานแล้ว ไม่เติมคนจากภายนอกอีก (เจ้าโกลาหลข้างบนมีจำนวนตายตัวของตัวเอง)
        target = self.realm_target(world)
        deficit = target - world.n_alive
        if deficit <= 0 or elapsed <= 0:
            return
        exp = deficit * (elapsed / 365.0) * C.REPOP_RATE
        n = int(exp) + (1 if self.rng.random() < exp % 1.0 else 0)
        # เปิดระบบอาหารอยู่ ผู้ที่เข้ามาเติมเป็นผู้ใหญ่วัยทำงานที่อพยพเข้ามา (ประกาศเป็นแหล่งประชากร) ไม่ใช่เด็ก
        # ไม่มีพ่อแม่อายุ 0–14 ปี วัดกับเซฟจริงปีที่ 1,228: 413 จาก 414 คนที่ repopulate สร้างใน 15 ปีเป็นเด็กแบบนั้น
        # ซึ่งไม่มีใครเลี้ยงและอดตาย แล้วประชากรที่ลดลงก็ทำให้ repopulate สร้างเด็กแบบเดิมเพิ่มอีก
        # ปิดระบบอาหาร: เหมือนเดิมทุกประการ (สุ่มครั้งเดียวต่อคนเท่ากัน)
        low, high = (15, 40) if C.FOOD_ENABLED else (0, 14)
        for _ in range(min(n, deficit)):
            self.spawn(world, self.rng.randint(low, high))

    def recount_worlds(self):
        """นับประชากรของทุกแดนใหม่จากของจริง — เดินรายชื่อคนเป็นรอบเดียว O(คนเป็น) ไม่ใช่ต่อแดน

        ทำเป็นรอบแทนที่จะไล่ปิดรูทีละจุด เพราะ `n_alive`/`n_mortal` ถูกบวกลบกระจายอยู่หลายที่ทั่ว
        เอนจิน (เกิด ตาย ข้ามขั้น ถอยขั้น ข้ามฟ้า ข้ามประตูมิติ ยุคล่ม) และทุกครั้งที่เพิ่มทางใหม่ก็มี
        โอกาสลืมอีก วัดจริงหลัง 513 ปี: โลกมนุษย์นับสามัญชนไว้ 2,714 คนทั้งที่มีอยู่จริง 144 คน
        ซึ่งคูณตรงเข้าไปในปราณที่ไหลเข้าโลก (rules.heaven_inflow) — ผิดไป 19 เท่าเงียบๆ ตลอด 500 ปี
        """
        alive_n = [0] * len(self.worlds)
        mortal_n = [0] * len(self.worlds)
        for cid in self.alive_cids:
            ch = self.cast[cid]
            wid = ch.world_id
            if 0 <= wid < len(alive_n):
                alive_n[wid] += 1
                if ch.realm == 0:
                    mortal_n[wid] += 1
        for w in self.worlds:
            w.n_alive = alive_n[w.wid]
            w.n_mortal = mortal_n[w.wid]

    def _is_apex(self, ch):
        return (ch.alive and not ch.is_chaos()
                and ch.tier >= len(C.TIER_NAMES) - 1 and ch.realm >= C.REALM_CAP)

    def apply_bloodline_buff(self, ch):
        """ตรึงค่าพรจากผู้สูงสุดแต่ละคนไว้จนกว่าผู้ให้จะตายหรือหลุดจากขั้นสูงสุด"""
        active = getattr(self, "apex_blessings", {})
        grants = getattr(ch, "bloodline_grants", {})
        grants = {cid: amount for cid, amount in grants.items() if cid in active}
        for cid, blessings in active.items():
            if cid in grants:
                continue
            amount = 0.0
            for blood, strength in blessings.items():
                share = ch.blood.get(blood, 0.0)
                if share > 0.0:
                    affinity = ch.bloodline_affinity.get(blood, C.BLOODLINE_AFFINITY_MIN)
                    amount += strength * share * affinity
            if amount > 0.0:
                grants[cid] = min(C.BLOODLINE_BLESS_CAP, amount)
        ch.bloodline_grants = grants
        # ผู้สูงสุดหลายคนช่วยคงพรไว้ แต่ใช้ค่าที่แรงที่สุดเพื่อไม่ให้จำนวนผู้สูงสุดทบพลังไร้เพดาน
        ch.bloodline_buff = max(grants.values(), default=0.0)

    def refresh_bloodline_buffs(self):
        """พรดับทันทีเมื่อผู้ให้คนสุดท้ายตาย/หลุดขั้น และคงอยู่ถ้ายังมีผู้สูงสุดคนอื่น"""
        active = getattr(self, "apex_blessings", {})
        self.apex_blessings = {
            cid: blessings for cid, blessings in active.items()
            if 0 <= cid < len(self.cast) and self._is_apex(self.cast[cid])
        }
        for ch in self.living():
            self.apply_bloodline_buff(ch)

    def update_apex_blessing(self, ch):
        """สร้างพรสุ่มครั้งเดียวเมื่อถึงสูงสุด หรือถอนพรเมื่อไม่ครองขั้นนั้นแล้ว"""
        if not hasattr(self, "apex_blessings"):
            self.apex_blessings = {}
        changed = False
        if self._is_apex(ch):
            if ch.cid not in self.apex_blessings:
                if not ch.bloodline_blessings:
                    ch.bloodline_blessings = {
                        blood: round(self.rng.uniform(C.BLOODLINE_BLESS_MIN, C.BLOODLINE_BLESS_MAX), 4)
                        for blood, share in ch.blood.items() if share > 0.0
                    }
                self.apex_blessings[ch.cid] = dict(ch.bloodline_blessings)
                changed = True
        elif ch.cid in self.apex_blessings:
            self.apex_blessings.pop(ch.cid, None)
            changed = True
        if changed:
            self.refresh_bloodline_buffs()

    def move_world(self, ch, new_wid):
        """ย้ายตัวละครข้ามแดน พร้อมปรับตัวนับประชากรของทั้งสองแดนให้ถูก

        มีไว้เพราะเดิมทุกที่ที่เขียน `ch.world_id = ...` ตรงๆ ไม่เคยลด `n_mortal` ของแดนเดิมเลย
        และ `n_mortal` คือตัวคูณของปราณที่ไหลเข้าโลก (rules.heaven_inflow) — วัดจริงหลัง 513 ปี:
        โลกมนุษย์นับสามัญชนไว้ 2,714 คน ทั้งที่มีคนอยู่จริง 144 คน คือปราณไหลเข้าเกินจริง 19 เท่า
        """
        old = self.world(ch.world_id)
        new = self.world(new_wid)
        if old.wid == new.wid:
            return
        old.n_alive -= 1
        new.n_alive += 1
        if ch.realm == 0:
            old.n_mortal = max(0, old.n_mortal - 1)
            new.n_mortal += 1
        ch.world_id = new.wid
        # ที่อยู่ต้องอยู่ในผังของแดนที่เจ้าของอยู่จริงเสมอ — เดิมข้ามฟ้า (resolve "ข้ามฟ้า") ย้ายแดนแต่ไม่ย้ายที่
        # ตัวละครจึงอยู่ในสวรรค์ชั้นนอกที่สถานที่แดนลับของโลกล่าง (test_world_coherence 3.2: 498 เหตุการณ์ใน seed 11–15)
        # แก้ที่จุดเดียวที่ทุกการย้ายแดนผ่าน: ที่ที่ไม่อยู่ในผังใหม่ → สถานที่แรกของแดนใหม่ (ทางเข้า) ไม่ใช้เลขสุ่ม
        # ผู้เรียกที่เลือกที่ลงเอง (ถูกเกณฑ์ ลงโลกล่าง รับเด็กไปเลี้ยง) ตั้งทับหลังจากนี้ตามเดิม
        layout = self._places_of(new.place_key)
        if ch.place is None or ch.place not in layout:
            entry = PL.places_in(new.place_key)
            ch.place = entry[0] if entry else -1
            ch.building = -1
        if ch.travel_dest is not None and ch.travel_dest >= 0 and ch.travel_dest not in layout:
            ch.travel_dest = -1
            ch.building_dest = -1
        self._world_counts_dirty = True
        self._world_move_ver = getattr(self, "_world_move_ver", 0) + 1
