# -*- coding: utf-8 -*-
"""Sim — หนึ่งเทิร์นของตัวละคร (_step)"""
from ._common import *  # noqa: F401,F403
from ._common import _REACH_CACHE, _PLACE_SETS, _CENTERS, _reach_from, _auction_q  # noqa: F401


class StepMixin:
    def _step(self):
        rng = self.rng
        actor = None
        
        # --- City Governance Initialization ---
        if not getattr(self, "cities_initialized", False):
            self.cities_initialized = True
            for c in self.cities:
                    office = city_office(c.get("type_desc", ""))
                    strictness, title, faction = office["strictness"], office["title"], office["faction"]
                    ruler_name, realm = office["name"], office["realm"]
                    c["law_strictness"] = strictness
                    
                    # Spawn the Ruler
                    # เจ้าเมืองคือผู้ใหญ่ที่มีตำแหน่ง ไม่ใช่ทารกอายุศูนย์ปีซึ่งถูกเปลี่ยนชื่อ
                    # แล้วส่งไปปกครองเมืองทันที
                    ruler = self.spawn(self.worlds[0], age_years=rng.randint(30, 60))
                    # เมืองหลายเมืองใช้ชื่อเจ้าเมืองชุดเดียวกัน (นายอำเภอ "หวังป๋อ" ทุกเมือง) —
                    # ผ่าน unique_name ให้คนที่สองได้ชื่อที่ต่างออกไป ไม่งั้นบันทึกแยกเจ้าเมืองไม่ออก
                    ruler.name = self.unique_name(ruler_name, old=ruler.name)
                    ruler.realm = realm
                    ruler.peak_realm = max(ruler.peak_realm, ruler.realm)
                    ruler.title = title
                    ruler.faction = faction
                    ruler.city_id = c["id"]
                    ruler.is_loner = True # Don't wander taking disciples
                    ruler.energy = 100
                    if title == "ฮ่องเต้":
                        ruler.is_emperor = True
                        ruler.dragon_aura = True
                    c["ruler_cid"] = ruler.cid
                    
        idle_until = self.day + C.WORLD_IDLE_LIMIT_DAYS
        while True:
            # นาฬิกาโลกมาก่อนเทิร์นตัวละครที่ตรงวันกัน และเดินต่อแม้คิวตัวละครว่าง
            if not self.queue or self.queue[0][0] >= self.world_tick_day:
                if not self.queue and self.world_tick_day > idle_until:
                    break       # ไม่มีใครเหลือให้ถึงคิว และโลกเดินเปล่ามานานพอแล้ว
                self._world_tick(rng)
                continue
            day, cid = heapq.heappop(self.queue)
            ch = self.cast[cid]
            if not ch.alive:
                continue
            self.day = max(self.day, day)
            if ch.age(self.day) < 14:
                # ด่านอายุต้องมาก่อนระบบพลังงาน/ล่าอสูรและสถานะเดินทางทั้งหมด มิฉะนั้น
                # แม้จะกรอง intent ด้านล่างแล้ว ทารกก็ยังออกล่าอสูรจาก routine ด้านบนได้
                # พร้อมซ่อมสถานะผู้ใหญ่ที่อาจติดมากับเซฟจากรุ่นก่อน
                ch.hidden = False
                ch.seclude_until = 0
                ch.travel_dest = -1
                ch.building_dest = -1
                actor = ch
                break
            # --- Routine & Energy System ---
            # Update MP limits
            ch.max_mp = max(100.0, float(ch.realm * 100))
            if getattr(ch, "current_mp", 0) < ch.max_mp:
                ch.current_mp = min(ch.max_mp, getattr(ch, "current_mp", 100.0) + (ch.max_mp * 0.1))
                
            time_of_day = self.day % 4
            
            # ------------------------------------------------
            # Beast Forest Farming (ป่าหมื่นอสูร)
            # ------------------------------------------------
            if ch.energy > 50 and getattr(ch, "is_beast", False) == False and getattr(ch, "is_demon", False) == False and getattr(ch, "is_spirit", False) == False and BODY.can_fight(ch):
                if self.rng.random() < PHYS.hazard_p(C.BEAST_HUNT_PER_YEAR, self.day - ch.last_day):   # ตามเวลาตั้งแต่เทิร์นก่อน
                    ch.energy -= 40
                    if self.rng.random() < 0.15: # 15% chance to encounter beast
                        # Spawn wild beast
                        beast = self.spawn(self.worlds[0])
                        # ชนิดของอสูรมาจาก cid ไม่ใช่ rng — ตั้งใจ ไม่งั้นการแก้ชื่อจะกิน RNG เพิ่ม
                        # หนึ่งครั้งต่ออสูรหนึ่งตัว แล้วเลื่อนทุกอย่างที่สุ่มหลังจากนั้นทั้งโลก
                        # (determinism ของ seed เดิมจะพังทันที — ดู test_determinism.py)
                        # 224 ชื่อผสมยังซ้ำเมื่อโลกเดินนานพอ — ต่อท้าย "ตัวที่ N" ให้แยกตัวออกจากกันได้
                        beast.name = self.unique_name(
                            C.BEAST_KIND[beast.cid % len(C.BEAST_KIND)]
                            + C.BEAST_TRAIT[(beast.cid // len(C.BEAST_KIND)) % len(C.BEAST_TRAIT)],
                            old=beast.name, marker="ตัวที่")
                        beast.is_beast = True
                        beast.realm = min(C.REALM_CAP, max(1, ch.realm + self.rng.randint(-1, 1)))
                        beast.peak_realm = max(beast.peak_realm, beast.realm)
                        safe_print(f"\n🐾 [ป่าหมื่นอสูร] [{ch.name}] ออกล่าสัตว์อสูรและปะทะกับ [{beast.name}] ขั้น {beast.realm}!")
                        # We don't trigger combat.resolve directly here to avoid circular imports / missing world refs if not careful,
                        # but we can just use the event emitter or resolve it simply:
                        import tiandao.combat as combat
                        winner, loser, _clog, escaped = combat.resolve_combat(ch, beast, self.worlds[0], self)
                        # เดิมทิ้งผลการต่อสู้ทั้งก้อน อสูรที่ถูกสร้างมาเพื่อฉากนี้จึงค้างอยู่ในโลกตลอดไป
                        # วัดจริงปี 174: โลกมนุษย์มีสัตว์อสูรป่า 666 ตัว เทียบกับมนุษย์ 30 คน
                        # โลกจึงกลายเป็นโลกของสัตว์ ทั้งคิวเหตุการณ์และผู้สืบเรื่องของชั้นจิตใจ
                        if winner is ch and not escaped:
                            self.kill(beast, f"ถูก{ch.name}ล่าเอาแก่นพลัง", killer=ch)
                        else:
                            ch.hp = max(1, getattr(ch, "hp", 100) - C.BEAST_HUNT_LOSS_HP)
                            self.kill(beast, "หนีหายเข้าป่าลึก", natural=True)
                    else:
                        ch.insight += 10
                        # gain some items or spirit stones
                        safe_print(f"\n🌲 [ป่าหมื่นอสูร] [{ch.name}] ล่าสัตว์อสูรสำเร็จ ได้รับศิลาปราณและค่าความเข้าใจ!")
            
            # Energy consumption and state
            
            # Sect Facility: หอโอสถ Healing
            if getattr(ch, "hp", 100) < getattr(ch, "max_hp", 100) and getattr(ch, "org", None) is not None and ch.org < len(self.orgs):
                org = self.orgs[ch.org]
                if hasattr(org, "facilities") and "หอโอสถ" in org.facilities:
                    master_cid = org.facilities["หอโอสถ"]
                    if 0 <= master_cid < len(self.cast) and self.cast[master_cid].alive:
                        master = self.cast[master_cid]
                        ch.hp = getattr(ch, "max_hp", 100)
                        # Add to debts/relations to show gratitude
                        ch.debts.append({"kind": "บุญคุณ", "target": master_cid, "amount": 1,
                                                         "done": False, "name": "", "day": self.day,
                                                         "reason": "รักษาบาดแผลที่หอโอสถ"})
            
            if ch.energy <= 30:
                ch.current_state = "Sleeping"
                ch.energy += 70
                # When sleeping, they don't do major events as often, push them back
                if rng.random() < 0.5:
                    heapq.heappush(self.queue, (self.day + 1, cid))
                    continue
            else:
                if time_of_day == 0:
                    ch.current_state = "Cultivating"
                    ch.energy -= 10
                elif time_of_day == 1:
                    ch.current_state = "Working" if rng.random() < 0.5 else "Relaxing"
                    if ch.current_state == "Working":
                        ch.energy -= 20
                        # Earn money based on realm
                        earned = WAGES.fiat_pay(rng.randint(10, 50) * max(1, ch.realm))
                        WAGES.set_gold(self, ch, self.world(ch.world_id).tier, ch.money.get(self.world(ch.world_id).tier, 0.0) + earned, "fiat_work")
                        # Send cut to master
                        if ch.master_cid != -1 and 0 <= ch.master_cid < len(self.cast):
                            master = self.cast[ch.master_cid]
                            if master.alive:
                                cut = int(earned * 0.6)
                                master.money[self.world(master.world_id).tier] = master.money.get(self.world(master.world_id).tier, 0.0) + cut
                                ch.money[self.world(ch.world_id).tier] -= cut
                    else:
                        ch.energy += 20
                elif time_of_day == 2:
                    ch.current_state = "Socializing"
                    ch.energy -= 10
                else:
                    ch.current_state = "Sleeping"
                    ch.energy += 50
                    
            # --- Master & Disciple System ---
            if ch.realm >= 7 and not ch.is_loner and rng.random() < 0.05:
                # Look for a disciple in the same world
                pool = [c for c in self.living_in(ch.world_id) if c.realm < 4 and c.master_cid == -1 and c.cid != ch.cid]
                if pool:
                    disciple = rng.choice(pool)
                    disciple.master_cid = ch.cid
                    ch.disciples.append(disciple.cid)
                    # print(f"[{ch.name}] รับ [{disciple.name}] เป็นศิษย์สายตรง!")
                    
            ch.energy = min(100.0, getattr(ch, "energy", 100.0))
            


            if ch.hidden and getattr(ch, "seclude_until", 0):
                # อยู่ในด่าน — เวลาผ่านไปข้างนอกเต็มที่ ส่วนในด่านมีแต่การบำเพ็ญ
                R.age_and_decay(self, ch, self.world(ch.world_id), self.day - ch.last_day, rng)
                ch.last_day = self.day
                if not ch.alive:
                    continue
                if self.day < ch.seclude_until:
                    self.schedule(ch, ch.seclude_until - self.day)
                    continue
                # ผลของด่านคิดตามวันที่อยู่จริง (accrue_process) ถูกขัดจังหวะก็ได้เท่าที่อยู่ ไม่ปัดขึ้นเป็นหนึ่งปี
                # เวลาที่ "ได้ใช้" ไม่เท่ากับเวลาที่โลกภายนอกผ่านไป ถ้าปราณตรงนั้นหนาแน่นพอ (yield_rate = gamma)
                cut_short = getattr(ch, "seclude_cut", False)
                ch.seclude_cut = False
                self.accrue_process(ch)
                proc = ch.process
                done = (proc.progress_day - proc.start_day) / 365.0
                yrs = done if cut_short else max(1, int(round(done)))
                ch.hidden = False
                wv = self.world(ch.world_id)
                EM.decay(ch, self.day)
                for key in list(ch.emotions):
                    base = ch.emo_base.get(key, ch.emotions[key])
                    ch.emotions[key] += (base - ch.emotions[key]) * C.SECLUDE_FOCUS
                d_out = self.seclusion_diff(ch, wv, yrs)
                ch.process = None
                if cut_short:
                    d_out["เหตุที่ออก"] = (cut_short if isinstance(cut_short, str)
                                          else "เสบียงหมดก่อนครบกำหนด")
                spent = f"{yrs:.1f}" if cut_short else f"{yrs}"
                self.emit(wv, "ออกจากด่าน", ch, None, ["อดทน", "รู้แจ้ง"], "ออกจากด่าน",
                          f"{ch.name}ออกจากด่านหลังปิดตัวไป {spent} ปี — "
                          f"{d_out.get('โลกที่เปลี่ยนไป', 'โลกยังเหมือนเดิม')}", 0, d_out)
                self.schedule(ch, rng.randint(3, 30))
                continue

            if ch.hidden and getattr(ch, "jail_until", 0):
                # ติดคุกอยู่ — ใช้ hidden ร่วมกับ jail_until โดยตั้งใจ: ทุกที่ในโลกที่กรอง hidden
                # อยู่แล้ว (เหยื่อมารบุก งานประมูล ศึกพันธมิตร คู่ครอง) ข้ามคนติดคุกให้เองทันที
                # แต่การตื่นต้องมาจากกำหนดโทษ ไม่ใช่การทอย 15% ของ "ซ่อนตัวสร้างแดนลับ"
                R.age_and_decay(self, ch, self.world(ch.world_id), self.day - ch.last_day, rng)
                ch.last_day = self.day
                if not ch.alive:
                    continue
                w_j = self.world(ch.world_id)
                # ผู้จับกุมที่บันทึกไว้ตอนจับ ไม่ใช่เดาจากคู่แค้น — ความแค้นจางและแค้นคนตายถูกลบ (Sim.fade_grudges)
                # ถ้าเดาจากคู่แค้น ผู้จับที่ตายระหว่างโทษจะหายไปจากความจำ แล้วนักโทษแหกคุกไม่ได้อีกเลย
                # เซฟเก่าที่ไม่ได้บันทึกไว้ยังเดาจากคู่แค้นที่แค้นที่สุดแบบเดิม
                jcid = getattr(ch, "jailer", -1)
                if jcid < 0 and ch.rivals:
                    jcid = max(ch.rivals, key=lambda c: (ch.rivals[c], -c))
                jailer = self.cast[jcid] if 0 <= jcid < len(self.cast) else None
                if self.day < ch.jail_until:
                    gap_j = ch.jail_until - self.day
                    bar = (jailer.realm + C.JAIL_ESCAPE_REALM_GAP) if jailer is not None else 99
                    if ch.realm >= bar and rng.random() < C.JAIL_ESCAPE_P:
                        ch.jail_until, ch.jailer, ch.hidden = 0, -1, False
                        ch.decay += 0.3
                        self.emit(w_j, "แหกคุก", ch, jailer, ["ทำลาย"], "แหกคุก",
                                  f"{ch.name}ทลายที่คุมขังหลบหนีออกมาได้ก่อนพ้นโทษ", 0,
                                  {"โทษที่เหลือ": f"{gap_j // 365} ปี"})
                        self.schedule(ch, rng.randint(30, 200))
                    else:
                        self.schedule(ch, gap_j)
                    continue
                ch.jail_until, ch.jailer, ch.hidden = 0, -1, False
                self.emit(w_j, "พ้นโทษ", ch, jailer, ["อดทน"], "พ้นโทษ",
                          f"{ch.name}พ้นโทษคุมขัง กลับสู่ยุทธภพอีกครั้ง", 0, {})
                self.schedule(ch, rng.randint(30, 200))
                continue

            if ch.hidden:
                # เงื่อนไข `ch.return_day` สำคัญ ไม่ใช่แค่ `is_lord` — เจ้าโกลาหลก็ใช้เหตุการณ์
                # "ซ่อนตัว" ธรรมดาได้เหมือนคนอื่น (sim.py ~2300) ซึ่งไม่ได้ตั้ง return_day ให้
                # ค่าดีฟอลต์ของมันคือ 0 (models.py) เงื่อนไขเดิม `self.day >= ch.return_day` จึงเป็น
                # จริงทันทีทุกครั้งที่มันแค่ไปหลบ แล้วยิงเหตุการณ์ "เจ้าโกลาหลคืนกลับ" ออกมาทั้งที่
                # ไม่เคยตาย — วัดจริงจากรัน 475,904 เหตุการณ์ (439 ปี): มีเหตุการณ์คืนกลับ 17 ครั้ง
                # แต่ 9 ครั้งแรกขึ้นว่า "(ครั้งที่ 0)" คือข่าวปลอมล้วนๆ ประวัติศาสตร์ของโลกจึงบันทึก
                # การคืนชีพของศัตรูสูงสุดผิดไปเกินครึ่ง
                if ch.is_lord:
                    ch.last_day = self.day
                    pool = getattr(self, "lord_pool", 0.0)
                    if pool >= C.LORD_POOL_TARGET:
                        ch.hidden = False
                        ch.lord_returns += 1
                        self.lord_pool = 0.0
                        self.lord_seal = 0.0
                        w0 = self.world(ch.world_id)
                        self.emit(w0, "เจ้าโกลาหลคืนกลับ", ch, None, ["ทำลาย"], "คืนกลับ",
                                  f"{ch.name}ก่อร่างกลับสู่ห้วงโกลาหลอีกครั้ง แข็งแกร่งกว่าเดิม "
                                  f"(ครั้งที่ {ch.lord_returns})", 0,
                                  {"พลังที่สะสมครบ": f"{pool:,.0f}/{C.LORD_POOL_TARGET:,.0f}",
                                   "ที่มาของพลัง": "ความตายทั่วจักรวาลระหว่างที่มันสลายอยู่"})
                        self.schedule(ch, rng.randint(30, 400))
                    else:
                        self.schedule(ch, 365)
                    continue
                R.age_and_decay(self, ch, self.world(ch.world_id),
                                self.day - ch.last_day, rng)
                ch.last_day = self.day
                if ch.alive:
                    if rng.random() < 0.15:
                        # ออกจากแดนลับ — ต้องเป็นเหตุการณ์ที่เห็นได้ ไม่ใช่แค่พลิกธงเงียบๆ
                        # คนหายไปจากโลกหลายสิบปีแล้วโผล่กลับมา คือจังหวะเรื่องที่ทั้งโลกควรรู้
                        # และเป็นที่ที่กติกา "ในแดนลับเลื่อนขั้นไม่ได้" แสดงราคาของมันออกมา
                        yrs = max(0, (self.day - getattr(ch, "hide_day", 0))) // 365
                        ch.hidden = False
                        w0 = self.world(ch.world_id)
                        acc = R.accumulation(ch)
                        req = max(1.0, R.need(ch, w0))
                        full = acc >= req
                        self.emit(w0, "ออกจากแดนลับ", ch, None, ["อดทน", "ตัดสินใจ"],
                                  "กลับสู่โลก",
                                  f"{ch.name}ก้าวออกจากแดนลับกลับสู่โลกอีกครั้ง "
                                  f"หลังหายไป {yrs} ปี", 0,
                                  {"เวลาที่หายไป": f"{yrs} ปี",
                                   "ขั้นพลังตอนออกมา": ch.realm_name(),
                                   "การสะสม": f"{acc:.0f}/{req:.0f}"
                                              + (" — เต็มแล้ว รอแค่ฟ้าดินข้างนอก" if full
                                                 else " — ยังไม่ถึงเกณฑ์"),
                                   "ที่แดนลับพรากไป": "ตลอดเวลาในนั้น ขั้นพลังไม่ขยับแม้แต่ขั้นเดียว"})
                        ch.hide_day = 0
                    self.schedule(ch, rng.randint(2000, 12000))
                continue

            if ch.travel_dest >= 0:
                # กำลังเดินทางอยู่ (ตั้งไว้จาก resolve() "เดินทาง") — เหมือนกับ ch.hidden ด้านบน: ไม่ผ่าน
                # การเลือก intent ปกติเลยจนกว่าจะถึงจุดหมายจริง แค่ไปโผล่เช็คเป็นระยะระหว่างทางแทน
                world0 = self.world(ch.world_id)
                on_road = self.day - ch.last_day
                R.age_and_decay(self, ch, world0, on_road, rng)
                ch.last_day = self.day
                if not ch.alive:
                    continue
                if self.day >= ch.travel_arrival_day:
                    dest_name = PL.PLACES[ch.travel_dest][0] if 0 <= ch.travel_dest < len(PL.PLACES) else "?"
                    old_place = ch.place
                    ch.place = ch.travel_dest
                    ch.travel_dest = -1
                    if C.GUARDIANS_ENABLED:
                        GUARD.on_arrival(self, ch, old_place)
                    ch.building = -1  # place ใหม่ = ยังไม่ระบุอาคาร ต้อง route ใหม่ถ้าจำเป็น
                    self.emit(world0, "เดินทาง", ch, None, ["เดินทาง"], "มาถึง",
                              f"{ch.name}เดินทางมาถึง{dest_name}แล้ว", 0, {})
                    travel_ev = next(e for e in E.EVENT_TABLE if e["kind"] == "เดินทาง")
                    self.schedule(ch, rng.randint(*travel_ev["gap"]))
                    continue
                hit = TR.roll_enroute_event(rng, days=on_road, day=self.day)
                if hit is not None:
                    outcome, deltas = hit
                    if "hp" in deltas:
                        ch.hp = max(0, ch.hp + deltas["hp"])
                    if "mats" in deltas:
                        ch.mats = ch.mats + deltas["mats"]
                    text = {
                        "พบของ": f"{ch.name}พบของมีค่าตกอยู่ระหว่างทาง",
                        "ถูกปล้น": f"{ch.name}ถูกปล้นระหว่างทาง",
                        "บาดเจ็บ": f"{ch.name}บาดเจ็บจากอุบัติเหตุระหว่างทาง",
                    }.get(outcome, f"{ch.name}เจอเหตุการณ์ระหว่างทาง")
                    fatal = ch.hp <= 0
                    if fatal:
                        # ต้อง outcome="ตาย" ไม่ใช่ "บาดเจ็บ" — narrative_factory/config.yaml จำแนก
                        # scene_type=Death จาก outcome นี้เป๊ะๆ เท่านั้น (death_outcomes: ["ตาย"])
                        outcome = "ตาย"
                        text = f"{ch.name}เสียชีวิตจากอุบัติเหตุระหว่างทาง"
                    self.emit(world0, "เดินทาง", ch, None, ["เดินทาง"], outcome, text, 0, {})
                    if fatal:
                        self.kill(ch, "เสียชีวิตระหว่างเดินทาง")
                if ch.alive and ch.travel_dest >= 0:
                    next_check = min(C.TRAVEL_ENROUTE_CHECK_DAYS, ch.travel_arrival_day - self.day)
                    self.schedule(ch, max(1, next_check))
                continue

            if ch.building_dest >= 0:
                # กำลังเดินข้ามเมืองไปอาคารเป้าหมาย (ตั้งไว้จาก resolve() ผ่าน Sim.route_to_building) —
                # สั้นกว่าเดินทางข้าม place มาก (SETTLEMENT_TRAVEL_DAYS วัน) เลยไม่ต้องเช็คเหตุการณ์ระหว่าง
                # ทางแบบ ch.travel_dest ด้านบน แค่รอถึงวันแล้วปล่อยให้เลือกเทิร์นปกติทำงานต่อ
                world0 = self.world(ch.world_id)
                R.age_and_decay(self, ch, world0, self.day - ch.last_day, rng)
                ch.last_day = self.day
                if not ch.alive:
                    continue
                if self.day >= ch.building_arrival_day:
                    ch.building = ch.building_dest
                    ch.building_dest = -1
                    travel_ev = next(e for e in E.EVENT_TABLE if e["kind"] == "เดินทาง")
                    self.schedule(ch, rng.randint(*travel_ev["gap"]))
                    continue
                self.schedule(ch, max(1, ch.building_arrival_day - self.day))
                continue

            actor = ch
            break
        if actor is None:
            return None

        elapsed = self.day - self.last_day
        self.last_day = self.day
        self._advance_eco()
        world = self.world(actor.world_id)

        # แก่/เสื่อมคิดเฉพาะตอนตัวละครขยับ (เร็วกว่าไล่ทุกคนทุกเหตุการณ์)
        # เด็กยังต้องให้กายวิภาคเดินตามเวลาจริง แต่ยังไม่ควรถูกคิดค่าคงสภาพขั้นพลัง
        # ความเสื่อม อายุขัย หรือจิตมารด้วยกฎของผู้ใหญ่ ก่อนหน้านี้เด็กอายุสิบปีจึงมี
        # เหตุการณ์ "สิ้นอายุขัย" ได้ทั้งที่ intent ของเด็กถูกกันไว้ด้านล่างแล้ว
        actor_gap = self.day - actor.last_day
        self.settle_routine(actor)           # การบำเพ็ญตั้งแต่เทิร์นก่อนได้ผลก่อนแก่และก่อนเลือกทำอะไรต่อ
        if actor.age(self.day) < 14:
            BODY.tick(actor, actor_gap, day=self.day, fed=FOOD.fed_share(actor))
        else:
            R.age_and_decay(self, actor, world, actor_gap, rng)
            if actor.alive and not actor.came_of_age:
                CHILD.come_of_age(self, actor, world)   # หลังร่างกายเดิน การฝึกปีสุดท้ายจึงนับแล้ว
        actor.last_day = self.day


        if not actor.alive:
            # ตายระหว่างร่างกายเดิน (age_and_decay): อายุขัยหมด หรือบาดแผล/อวัยวะล้มเหลว/ร่างเย็น ฯลฯ — เหตุการณ์ต้องบอกสาเหตุจริง
            # (death_cause ที่ DEATH.resolve บันทึก) เดิมเขียน "สิ้นอายุขัย" ทุกกรณี: seed 42 ใน 50 ปีมี 615 คนที่ตายจากบาดแผล
            # แต่ประวัติบอกว่าแก่ตาย
            cause = actor.death_cause or "สิ้นอายุขัย"
            kind = "สิ้นอายุขัย" if cause.startswith("สิ้นอายุขัย") else "สิ้นชีพ"
            return self.emit(world, kind, actor, None, ["ความตาย"], "ตาย",
                             f"{actor.name}สิ้นอายุขัย" if kind == "สิ้นอายุขัย" else f"{actor.name}สิ้นชีพ — {cause}",
                             elapsed, {"สาเหตุ": cause})

        # งานประมูลใหญ่ของตลาด — เหตุการณ์ของ "สถานที่" ไม่ใช่ของอาชีพ
        # วัดจากรันจริง 79 ปี: ผู้มีจิตใจได้เข้างานประมูลแค่ครั้งเดียว เพราะท่า "เปิดประมูล" เปิดให้เฉพาะ
        # พ่อค้า (หลงจู๊/เถ้าแก่/นักประมูล) ซึ่งแทบไม่มีใครในกลุ่มตัวเอก ฉากหมู่จึงไม่เคยเกิด
        # (ย้ายไป _world_tick: AUCTION_EVENT_P คือโอกาสต่อแดนต่อหนึ่งช่วงเวลาโลก ตามที่ config ระบุ — เดิมทอยที่นี่ทุกเทิร์นของตัวละคร
        #  แดนที่คนมากจึงมีงานประมูลถี่ตามจำนวนเทิร์น ไม่ใช่ตามเวลา: seed 42 ใน 100 ปี 3,232 งาน เจ้าภาพคนเดียวถือ 37 งาน)

        # โลกที่ถูกฉีกจนรอยแยกกว้างพอ จะรวมกำลังบุกกลับเข้าไปถึงถิ่นของมันเอง
        # ยกไปปราบได้เมื่อ **มีตัวให้ปราบ** (มันตื่นอยู่) หรือเมื่อรอยแยกกว้างจนทนไม่ไหว
        # เงื่อนไขเดิมมีแต่ข้อหลัง ซึ่งพอ seal_rift ใช้งานได้จริงแล้วรอยแยกก็แทบไม่เคยถึง 3.0 อีก
        # เลย — วัดจริง 300 ปี: ศึกพันธมิตร 0 ครั้ง ทั้งที่เจ้าโกลาหลตื่นอยู่รวมกันหลายสิบปี
        _lord = self.cast[self.lord_cid] if self.lord_cid is not None else None
        _awake = _lord is not None and _lord.alive and not _lord.hidden
        if (world.kind == "mortal" and self.chaos_wid is not None
                and (_awake or world.rift >= C.COALITION_RIFT_TRIGGER)
                and self.day - getattr(world, "last_coalition", -C.COALITION_COOLDOWN)
                    >= C.COALITION_COOLDOWN
                and rng.random() < C.COALITION_P):
            self.coalition_strike(world, elapsed, rng)
        # ฟ้าเกณฑ์คนขึ้นไปเมื่อโกลาหลกำลังกดดันจักรวาล — คนข้างล่างไม่รู้สาเหตุ รู้แค่ว่าคนหาย
        if (world.kind == "mortal" and world.tier == 0 and world.up is not None
                and (_awake or world.rift > 0.0
                     or getattr(self, "lord_seal", 0.0) <= 0.0)
                and rng.random() < C.CONSCRIPT_P):
            self.conscript(world, rng)

        # มหาผนึกตรึงเจ้าโกลาหลเสื่อมลงตามกาลเวลา — พอเสื่อมหมด มันกลับมาสะสมพลังต่อทันที
        # ต้องวัดจาก **เวลาจริงของโลก** ไม่ใช่ `elapsed` ซึ่งคือช่องว่างส่วนตัวของตัวละครที่เพิ่ง
        # ขยับ วัดจริง 150 ปี: ผนึกเสื่อมได้แค่ 0.37/ปี ทั้งที่ตั้งไว้ 2.0 — ช้ากว่า 5 เท่า เพราะ
        # ผลรวมของ elapsed ที่ผ่านบรรทัดนี้คือเวลาของคนกลุ่มเล็กๆ ในโลกมนุษย์เท่านั้น ผลคือ
        # ผนึกกลายเป็นของถาวรโดยบังเอิญ เจ้าโกลาหลไม่เคยสะสมพลังได้เลยสักหน่วยใน 150 ปี
        if getattr(self, "lord_seal", 0.0) > 0.0:
            gap = self.day - getattr(self, "_lord_seal_day", self.day)
            self._lord_seal_day = self.day
            was = self.lord_seal
            self.lord_seal = max(0.0, was - C.LORD_SEAL_DECAY_PER_YEAR * gap / 365.0)
            if self.lord_seal <= 0.0:
                self.emit(world, "มหาผนึกโกลาหลเสื่อม", None, None, ["ทำลาย"], "ผนึกสลาย",
                          "มหาผนึกที่ตรึงเจ้าโกลาหลไว้เสื่อมสลายจนหมดแล้ว "
                          "มันเริ่มดูดพลังจากความตายทั่วจักรวาลอีกครั้ง", elapsed,
                          {"ผนึกที่เหลือก่อนสลาย": f"{was:.1f}",
                           "พลังที่มันค้างไว้": f"{getattr(self, 'lord_pool', 0.0):,.0f}/"
                                                f"{C.LORD_POOL_TARGET:,.0f}"})
        # ส่งคนไปผนึกมันขณะที่มันสลายอยู่ — โลกทำได้เฉพาะช่วงนี้เท่านั้น
        if (world.kind == "mortal" and self.chaos_wid is not None
                and self.day - getattr(self, "lord_seal_last", -C.LORD_SEAL_COOLDOWN)
                    >= C.LORD_SEAL_COOLDOWN
                and rng.random() < C.LORD_SEAL_P):
            self.seal_lord(world, elapsed, rng)
        if (world.kind == "mortal" and self.chaos_wid is not None
                and self.chaos_wid in world.lateral and rng.random() < C.CHAOS_RAID_P):
            self.chaos_raid(world, elapsed, rng)
        # ดิ่งลงโลกมนุษย์ตรงๆ ผ่านรูหนอน ไม่ผ่านแดนเซียน
        if (world.kind == "mortal" and world.place_key == 0
                and self.chaos_wid is not None and rng.random() < C.CHAOS_INVADE_P):
            self.chaos_invade(world, elapsed, rng)

        # Nested world events (notably conscription) can move the active actor.
        # Prepare peers, eligibility, targets and action funds in the actor's
        # current world, after those events, rather than the world of this turn's start.
        world = self.world(actor.world_id)
        # เหตุการณ์ระดับโลกข้างบน (มารบุก ศึกพันธมิตร ผนึกเจ้าโกลาหล โกลาหลบุก โกลาหลดิ่งลง) รันกลางเทิร์นของ actor
        # หลังจากตรวจว่ายังมีชีวิตแล้ว และฆ่า actor เองได้ — เดิมเทิร์นเดินต่อจนศพเป็นผู้กระทำ (seed 12: event 24729
        # โกลาหลบุกสังหาร cid 409 แล้ว 24730 ให้ 409 "กำเนิดทายาท") จบเทิร์นที่นี่ด้วยเหตุการณ์ล่าสุด ไม่จัดคิวให้ศพ
        if not actor.alive:
            return self.log[-1] if self.log else None

        # เด็กมีชีวิตและประวัติของตัวเอง แต่ยังไม่ใช้เมนูการกระทำของผู้ใหญ่ การปล่อยลงไป
        # ใน intent ปกติเคยทำให้ทารกอายุ 0 ปีประลอง ปล้น ปิดด่าน และตายจากการล่าอสูร
        # เก็บหนึ่งบันทึกต่อปีไว้บน Character เพื่อให้ชั้นจิตใจที่รับเขาตอนโตย้อนอ่านได้
        if actor.age(self.day) < 14:
            return self._childhood_turn(actor, world, elapsed, rng)

        others = self.social_pool(actor, world, rng)

        if world.kind == "mortal":
            if rng.random() < C.RUMOR_SPAWN_P:
                self.spawn_rumor(world, rng)
            self.try_hear_rumor(actor, world, rng)

        # มนุษย์มารเป็นที่รังเกียจ — มีคนตามล่าโดยไม่ต้องมีเหตุส่วนตัว
        if actor.hated() and others and rng.random() < C.MARA_HUNT_P:
            hunters = [c for c in others if not c.hated()
                       and c.blood.get("human", 0) > 0.5]
            if hunters:
                h = rng.choice(hunters)
                win, lose, margin, res = R.fight(self, world, h, actor, rng)
                actor.rivals[h.cid] = actor.rivals.get(h.cid, 0) + 2
                e = self.emit(world, "ล่ามนุษย์มาร", h, actor, ["เลือด", "ทำลาย"], res,
                              f"{h.name}ตามล่า{actor.name}เพราะเป็นมนุษย์มาร — {lose.name}เป็นฝ่ายเสีย",
                              elapsed, {"เผ่า": actor.race(), "margin": round(margin, 3),
                                        "winner": win.cid})
                if not actor.alive:
                    return e

        # เหตุการณ์ที่เกิดกลางสเต็ปฆ่าคนได้ และไม่ได้ฆ่าแต่ `actor` — การตามล่ามนุษย์มาร
        # ข้างบนดึงผู้ล่ามาจาก `others` แล้ว apply_defeat ฆ่าฝ่ายไหนก็ได้ ยามเดิมเช็คแต่
        # actor ตายหรือยัง ถ้าผู้ล่าเป็นฝ่ายตาย กองเป้าหมายจะค้างศพไว้ แล้วมือจับที่เลือก
        # เป้าจากกองนี้จะไปกระทำกับศพ (วัดจริง: seed 11 วันที่ 4,183 มีเหตุการณ์ "ทรยศ"
        # ที่เป้าตายไปแล้วในเหตุการณ์ก่อนหน้าของสเต็ปเดียวกัน)
        # คัดที่นี่ที่เดียวเพราะเป็นจุดก่อนการเลือกเป้าทุกชนิด — ยามรายมือจับจะหลุดได้เสมอ
        if others:
            others = [c for c in others if c.alive]

        city_dict = None
        if actor.city_id >= 0:
            for c in self.cities:
                if c["id"] == actor.city_id:
                    city_dict = c
                    break
                    
        # Update pick_event call to include city
        # Layer 1 Utility AI (Cultivator Brain v2, Phase 2) ต่อยอด IN.weigh() เดิม ก่อนสุ่มเลือก
        IN.plan_wants(actor, MAT)      # คิดก่อนว่ายังขาดอะไร แล้วค่อยชั่งน้ำหนักเจตนา
        loot_nearby = any(
            any(self.items[i].kind != "ยาวิเศษ" for i in c.items if i in self.items)
            for c in others)
        owed = {d["target"] for d in actor.debts if not d["done"]}
        debtor_nearby = any(c.cid in owed for c in others) if owed else False
        # แดนลับสะสมไปเรื่อยๆ ไม่มีเพดาน (ปีที่ 590 มี 6,117 แห่ง) การวนทั้งหมดทุกเหตุการณ์จึงเป็น
        # งาน O(แดนลับ) ต่อเหตุการณ์ วัดด้วย cProfile: genexpr นี้ถูกเรียก 17.6 ล้านครั้งต่อ 3,000
        # เหตุการณ์ = 30% ของเวลาซิม และจะแย่ลงเรื่อยๆ ตามอายุโลก จึงทำ index ใหม่วันละครั้ง
        secret_available = (actor.place in self._fragment_places()
                            or world.wid in self._ripe_cache_worlds())
        w = IN.weigh(actor, self, E.EVENT_TABLE, bool(others), loot_nearby,
                     debtor_nearby, secret_available, others=others)
        w = self.brain_manager.decide(actor, self, w)
        # Decision Engine (tiandao/decision): Utility+Softmax+Belief+Memory+Social+GOAP
        # ไม่ได้ attach ไว้ (ค่าเริ่มต้น) = ทางเดิมทุกประการ และไม่แตะ rng หลักเลย
        _de = getattr(self, "decision_engine", None)
        mind_choice = _de.choose(actor, self, w, others, world) if _de is not None else None
        kind = mind_choice.kind if mind_choice is not None else IN.sample_weighted(w, rng)
        ev = next((e for e in E.EVENT_TABLE if e["kind"] == kind), None) \
            or E.pick_event(actor, rng, bool(others), city=city_dict)
        target = None
        if ev["tgt"] and mind_choice is not None and mind_choice.target is not None:
            target = mind_choice.target
            if ev["kind"] == "ชิงสมบัติ":
                target = self.aim_theft(target, others)
        elif ev["tgt"]:
            if ev["kind"] == "สะสางเรื่องเก่า":
                owed = [c for c in others
                        if any(not d["done"] and d["target"] == c.cid for d in actor.debts)]
                target = rng.choice(owed) if owed else rng.choice(others)
            elif ev["kind"] == "ชิงสมบัติ":
                # เดิมเล็งเฉพาะคนที่ถือ "สมบัติฟ้าดิน" ชิ้นเอก แล้วที่เหลือสุ่มมั่ว ผลคือ 96%
                # ของการชิงสมบัติจบด้วย "ไม่มีของ" เพราะคนทั่วไปไม่มีอะไรติดตัวเลย
                # ตอนนี้เล็งคนที่มีของให้ชิงจริงๆ (handler รับของทุกอย่างที่ไม่ใช่ยา)
                legend_names = {t[0] for t in TREASURES}
                rich, has_any = [], []
                for c in others:
                    best = 0
                    for iid in c.items:
                        it = self.items.get(iid)
                        if it and it.kind != "ยาวิเศษ":
                            best = max(best, 2 if it.name in legend_names else 1)
                    if best == 2:
                        rich.append(c)
                    elif best == 1:
                        has_any.append(c)
                if rich and rng.random() < getattr(actor, "greed", 0.5) * 2:
                    target = rng.choice(rich)
                elif rich or has_any:
                    target = rng.choice(rich + has_any)
                else:
                    foes = [c for c in others if c.cid in actor.rivals]
                    target = rng.choice(foes) if foes and rng.random() < 0.55 else rng.choice(others)
            elif ev["kind"] == "กำเนิดทายาท":
                # เดิมใช้ทางเลือกทั่วไป (ศัตรู 55% หรือสุ่ม) ผลคือ 47% ของการมีทายาทจบด้วย "ล้มเหลว"
                # เพราะคู่เป็นเพศเดียวกัน ไร้เพศ หรือยังเป็นเด็ก — เสียตาเปล่าและอ่านไม่เป็นเรื่อง
                mates = [c for c in others
                         if c.gender not in ("ไม่มีเพศ",) and c.gender != actor.gender
                         and c.age(self.day) >= C.ADULT_AGE]
                spouse = next((c for c in mates if c.cid == actor.spouse), None)
                if spouse is not None:
                    target = spouse                      # มีคู่ครองแล้วก็มีทายาทกับคู่ของตัวเอง
                elif mates:
                    close = sorted(mates, key=lambda c: (-actor.bonds.get(c.cid, 0), c.cid))
                    top = [c for c in close if actor.bonds.get(c.cid, 0) > 0]
                    target = rng.choice(top) if top else rng.choice(mates)
                else:
                    target = rng.choice(others)          # ไม่มีใครเข้าเกณฑ์ ปล่อยให้ handler ตัดสิน
            elif ev["kind"] == "สงครามสำนัก":
                # เดิมไม่มีกิ่งของตัวเอง จึงตกไปใช้ทางเลือกทั่วไปซึ่งสุ่มจากคนที่ยืนอยู่แถวนั้น
                # แต่คนที่ยืนอยู่แถวนั้นคือ **คนสำนักเดียวกัน** (ตัวละครอยู่รวมกันตามสำนัก) หรือ
                # ไม่ก็คนไร้สังกัด ทั้งสองกรณี handler ตอบ "ล้มเหลว" ทันทีตั้งแต่บรรทัดแรก
                # วัดจริงโลก 47 ปี: สงครามสำนัก 658 ครั้ง จบด้วย "ล้มเหลว" 657 ครั้ง = 99.8%
                # เป็นกลไกที่เขียนไว้ครบแต่ไม่เคยทำงานเลย แบบเดียวกับ "ทรยศ" และ "สงครามเบิกฟ้า"
                # สงครามสำนักคือการ "ยกทัพไปตี" ไม่ใช่การทะเลาะกับคนที่ยืนอยู่ข้างๆ เป้าหมาย
                # จึงต้องหาจากทั้งโลก ไม่ใช่จาก others (คนที่อยู่สถานที่เดียวกัน)
                # วัดจริงโลก 20 ปี: คู่ที่ยืนอยู่สถานที่เดียวกันและ **ต่างสำนักกัน = 0 คู่**
                # เพราะแต่ละสำนักอยู่กันคนละที่ กลไกนี้จึงเป็นไปไม่ได้ทางโครงสร้างมาตลอด
                # (สงคราม 403 ครั้ง จบด้วย "เป้าหมายไม่ชัดเจน" 397 ครั้ง)
                def _foe_pool(pool):
                    return [c for c in pool
                            if c.org is not None and c.org != actor.org
                            and 0 <= c.org < len(self.orgs) and self.orgs[c.org].alive]
                foes = _foe_pool(others) or _foe_pool(self.living_in(world.wid))
                if actor.org is not None and 0 <= actor.org < len(self.orgs):
                    mine = self.orgs[actor.org]
                    hated = [c for c in foes if c.org in getattr(mine, "grudges", {})]
                    if hated:
                        foes = hated          # มีเรื่องคาใจกันอยู่ก่อน ก็ไปที่สำนักนั้นก่อน
                target = rng.choice(foes) if foes else rng.choice(others)
            elif ev["kind"] == "ถ่ายทอดวิชา":
                # สอนคนที่ยัง "ขาดสิ่งที่ข้ามี" ก่อน — ทางเลือกทั่วไปสุ่มมั่วจากคนแถวนั้น
                # ทำให้ครึ่งค่อนของการถ่ายทอดตกไปที่คนที่มีวิชานั้นอยู่แล้ว
                mine = set(getattr(actor, "skills", ()) or ())
                need = [c for c in others if mine - set(getattr(c, "skills", ()) or ())]
                kin = [c for c in need
                       if c.cid in getattr(actor, "disciples", ()) or c.cid in actor.children]
                pool2 = kin or need
                target = rng.choice(pool2) if pool2 else rng.choice(others)
            elif ev["kind"] == "ประลอง":
                # ประลองคือการหา "คู่มือที่สมกัน" ไม่ใช่การไปหาศัตรู — ทางเลือกทั่วไปข้างล่างเล็ง
                # ศัตรูเก่า 55% ทำให้การประลองเกือบทั้งหมดกลายเป็นศึกแค้น (จึงถึงตายบ่อย) ทั้งที่
                # การไปเอาคืนศัตรูมีเจตนา "ล้างแค้น" ของตัวเองอยู่แล้ว
                peers = [c for c in others
                         if c.cid not in actor.rivals and actor.cid not in c.rivals
                         and abs(c.realm - actor.realm) <= 1]
                if peers:
                    target = rng.choice(peers)
                else:
                    plain = [c for c in others if c.cid not in actor.rivals]
                    target = rng.choice(plain) if plain else rng.choice(others)
            elif ev["kind"] == "ทรยศ":
                # หักหลังได้เฉพาะคนที่ไว้ใจเรา และย่อมเลือกคนที่ไว้ใจมากที่สุด (เจ็บที่สุด)
                trusted = [c for c in others if R.trust_tie(self, actor, c) is not None]
                if trusted:
                    target = max(trusted, key=lambda c: (actor.bonds.get(c.cid, 0)
                                                         + c.bonds.get(actor.cid, 0), -c.cid))
                else:
                    target = None
            elif ev["kind"] == "จับกุมอาชญากร":
                # เล็ง "คนที่ผิดกฎจริง" เท่านั้น ไม่มีใครผิดก็ปล่อยให้ handler ตอบว่าไม่พบอาชญากร
                # (เดิมสุ่มคนข้างตัว ทางการจึงประหารชาวนาและตัวเอกที่ไม่เคยทำอะไรผิด)
                crooks = [c for c in others if R.is_criminal(c)]
                if crooks:
                    worst = max(R.crime_weight(c) for c in crooks)
                    heavy = [c for c in crooks if R.crime_weight(c) == worst]
                    target = rng.choice(heavy)       # ตามจับรายที่หนักที่สุดก่อน
                else:
                    target = None
            elif ev["kind"] == "ลอบสังหาร":
                # ต้องมีเหตุ: แค้นของตัวเอง เรื่องค้างคา คำสั่งสำนัก หรือมีคนจ้าง
                cands = [c for c in others if R.assassin_motive(self, actor, c) is not None]
                if cands:
                    foes = [c for c in cands if c.cid in actor.rivals]
                    target = rng.choice(foes if foes else cands)
                else:
                    target = None
            elif ev["kind"] == "สงครามสำนัก":
                if actor.org is not None and actor.org < len(self.orgs):
                    actor_org = self.orgs[actor.org]
                    if actor_org.grudges:
                        rival_oid = max(actor_org.grudges, key=actor_org.grudges.get)
                        rival_members = [c for c in others if c.org == rival_oid]
                        if rival_members:
                            target = rng.choice(rival_members)
                if target is None:
                    target = rng.choice(others)
            else:
                foes = [c for c in others if c.cid in actor.rivals]
                target = rng.choice(foes) if foes and rng.random() < 0.55 else rng.choice(others)


        # --- Sect Rank Challenge ---
        if (getattr(actor, "org", None) is not None and actor.org < len(self.orgs)
                and BODY.can_fight(actor)
                and rng.random() < 0.1):
            org = self.orgs[actor.org]
            rank = getattr(actor, "sect_rank", "ศิษย์สายนอก")
            target_list = []
            new_rank = ""
            if rank == "ศิษย์สายนอก" and getattr(org, "inner_disciples", []):
                target_list = org.inner_disciples
                new_rank = "ศิษย์สายใน"
            elif rank == "ศิษย์สายใน" and getattr(org, "core_disciples", []):
                target_list = org.core_disciples
                new_rank = "ศิษย์สืบทอด"
                
            if target_list:
                target_cid = rng.choice(target_list)
                if 0 <= target_cid < len(self.cast) and self.cast[target_cid].alive:
                    target_ch = self.cast[target_cid]
                    import tiandao.combat as combat
                    # Law Enforcement Check
                    blocked = False
                    if actor.city_id >= 0:
                        city_dict = next((c for c in self.cities if c["id"] == actor.city_id), None)
                        if city_dict and "law_strictness" in city_dict:
                            if rng.random() * 100 < city_dict["law_strictness"]:
                                blocked = True
                                r_cid = city_dict.get("ruler_cid", -1)
                                if 0 <= r_cid < len(self.cast) and self.cast[r_cid].alive:
                                    ruler = self.cast[r_cid]
                                    return self.emit(world, "กฎหมายเมือง", actor, target_ch, ["กฎหมาย"], "ถูกสกัด", f"[{ruler.title} {ruler.name}] ผู้ปกครองเมืองเข้ามาสกัดการต่อสู้! ผิดกฎเมืองที่มีความเข้มงวด {city_dict['law_strictness']}/100", elapsed, {})
                    
                    if blocked:
                        return self.emit(world, "กฎหมายเมือง", actor, target_ch, ["กฎหมาย"], "ถูกสกัด", f"กองทหารลาดตระเวนเมืองเข้ามาสกัดการต่อสู้!", elapsed, {})
                    
                    win, lose, log, escaped = combat.resolve_combat(actor, target_ch, world, self)
                    if win.cid == actor.cid:
                        # Swap ranks
                        actor.sect_rank = new_rank
                        target_ch.sect_rank = rank
                        if rank == "ศิษย์สายนอก": 
                            if actor.cid in org.outer_disciples: org.outer_disciples.remove(actor.cid)
                            org.inner_disciples.append(actor.cid)
                            if target_ch.cid in org.inner_disciples: org.inner_disciples.remove(target_ch.cid)
                            org.outer_disciples.append(target_ch.cid)
                        elif rank == "ศิษย์สายใน":
                            if actor.cid in org.inner_disciples: org.inner_disciples.remove(actor.cid)
                            org.core_disciples.append(actor.cid)
                            if target_ch.cid in org.core_disciples: org.core_disciples.remove(target_ch.cid)
                            org.inner_disciples.append(target_ch.cid)
                        
                        return self.emit(world, "เลื่อนขั้นสำนัก", actor, target_ch, ["ชื่อเสียง"], "ชนะประลอง", f"[{actor.name}] โค่น [{target_ch.name}] แย่งตำแหน่ง {new_rank} สำเร็จ!", elapsed, {})
                    else:
                        return self.emit(world, "เลื่อนขั้นสำนัก", actor, target_ch, ["ชื่อเสียง"], "แพ้ประลอง", f"[{actor.name}] ท้าประลองแย่งตำแหน่ง {new_rank} แต่พ่ายแพ้ต่อ [{target_ch.name}]", elapsed, {})
        gap = rng.randint(*ev["gap"])
        before = IN.snapshot(actor)
        outcome, text, d = self.resolve(ev, actor, target, world, gap, rng)
        # ผู้ลงมือตายระหว่างการกระทำของตัวเอง (ข้ามขั้นพลาด, สู้ในเมืองแพ้ ฯลฯ) — ผลต้องบอกว่าตาย
        # ไม่ใช่ผลปกติของการกระทำ ไม่งั้นบันทึกจะเป็นคนตายแล้วยังลงมือในเทิร์นเดียวกัน
        if not actor.alive and outcome not in C.BLOODY_OUTCOMES:
            d = dict(d or {})
            d["ผลก่อนสิ้นชีพ"] = outcome
            outcome = "ตาย"
        IN.learn_from_outcome(actor, ev["kind"], before, IN.snapshot(actor))
        if ev["kind"] == "ค้นแดนลับ" and actor.rumor_leads:
            actor.rumor_leads = [l for l in actor.rumor_leads if l["kind"] != "แดนลับ"]
        for t in ev["tags"]:
            actor.exp[t] = actor.exp.get(t, 0) + 1
        e = self.emit(world, ev["kind"], actor, target, ev["tags"], outcome, text, elapsed, d)
        if actor.alive:
            self._next_turn(actor, gap, rng)
        return e
