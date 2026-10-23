# -*- coding: utf-8 -*-
"""Sim — เทิร์นถัดไป การเดินทาง และเหตุการณ์ข้างเคียง"""
from ._common import *  # noqa: F401,F403
from ._common import _REACH_CACHE, _PLACE_SETS, _CENTERS, _reach_from, _auction_q  # noqa: F401


class TurnMixin:
    def _next_turn(self, actor, gap, rng):
        """นัดเทิร์นถัดไปของผู้ที่เพิ่งลงมือ ตามสภาพที่การกระทำนั้นทิ้งไว้"""
        if actor.travel_dest >= 0:
            # เพิ่งเริ่มเดินทางจริง (resolve() ตั้ง travel_dest/travel_arrival_day ไว้แล้ว) — ต้อง
            # นัดตื่นครั้งแรกภายใน TRAVEL_ENROUTE_CHECK_DAYS ไม่ใช่กระโดดตรงไปวันถึงเลย ไม่งั้นจะไม่มี
            # โอกาสได้เช็คเหตุการณ์ระหว่างทางสักครั้งเดียวสำหรับทริปสั้น (บล็อก ch.travel_dest ด้านบน
            # ใน step() เป็นตัวจัดการรอบเช็คถัดๆ ไปเองหลังจากนี้)
            first_wake = min(C.TRAVEL_ENROUTE_CHECK_DAYS, actor.travel_arrival_day - self.day)
            self.schedule(actor, max(1, first_wake))
        elif actor.building_dest >= 0:
            # เพิ่งเริ่มเดินในเมืองไปอาคารเป้าหมาย (resolve() เรียก route_to_building ตั้ง
            # building_dest ไว้แล้ว) — นัดตื่นตรงวันถึงเลย เดินในเมืองสั้นมากไม่ต้องเช็คระหว่างทาง
            self.schedule(actor, max(1, actor.building_arrival_day - self.day))
        elif actor.hidden and actor.seclude_until > self.day:
            # เพิ่งเข้าด่าน — ตื่นวันครบด่าน รอบ 2,000–12,000 วันข้างล่างเป็นของแดนลับซึ่งไม่มีวันออก แต่ด่านยาวแค่
            # SECLUDE_YEARS ก่อนแก้ คนที่ครบด่านแล้วยังซ่อนอยู่จนถึงเทิร์นที่นัดไว้ วัดกับเซฟจริงปีที่ 1,228: ผู้ใหญ่ 439 คน
            # อยู่ในสภาพนี้ เทิร์นถัดไปมัธยฐานอีก 8 ปี เปิดระบบอาหารแล้วเขาอดตายเพราะต้องซื้อข้าวโดยไม่มีรายได้
            # (41% ของคนที่อดตาย) ปิดระบบอยู่เขาหายจากเวทีราวหนึ่งในห้าของผู้ใหญ่ทั้งโลก
            self.schedule(actor, actor.seclude_until - self.day)
        else:
            self.schedule(actor, gap if not actor.hidden else rng.randint(2000, 12000))

    def chaos_invade(self, world, elapsed, rng):
        """เผ่าโกลาหลมาถึงโลกมนุษย์แล้วทำอะไร:
        เล็งสถานที่ที่มวลปราณหนาแน่นที่สุด ทำลายสิ่งก่อสร้าง กลืนกินแร่และของ
        แล้วขยายรอยแยกให้กว้างขึ้นเพื่อดึงขุนพลระดับสูงลงมาสมทบ"""
        pool = [c for c in self.living_in(self.chaos_wid)
                if c.alive and not c.hidden and c.age(self.day) >= 14]
        cap = int(world.rift / C.RIFT_RANK_PER) + 1
        raiders = [c for c in pool if c.chaos_rank <= cap] or pool
        if not raiders:
            return
        c = rng.choice(raiders)
        # เป้าหมาย: สถานที่ขั้นสูงที่ยังไม่ถูกทำลาย
        cands = [i for i in PL.places_in(world.place_key)
                 if PL.PLACES[i][2] == 2 and self.ruined.get(i, 0) <= self.day]
        if not cands:
            cands = [i for i in PL.places_in(world.place_key)
                     if self.ruined.get(i, 0) <= self.day]
        if not cands:
            return
        
        # ปะทะค่ายกลป้องกันโลกมนุษย์ก่อน
        if world.defense_array > 0:
            if rng.random() < 0.75:  # โอกาสสกัดสำเร็จ 75%
                world.defense_array = max(0.0, world.defense_array - 20.0)
                d_array = {"ค่ายกลทำงาน": f"สกัดกั้นการบุกได้สำเร็จ พลังค่ายกลเหลือ {world.defense_array:.1f}/{world.defense_max:.1f}"}
                self.emit(world, "โกลาหลบุกโลกมนุษย์", c, None, ["ทำลาย"], "ถูกสกัดกั้น",
                          f"ค่ายกลป้องกันโลกทำงาน สกัด{c.name}ไว้ได้ทัน", elapsed, d_array)
                return
            else:
                world.defense_array = max(0.0, world.defense_array - 10.0)
                
        spot = rng.choice(cands)
        spot_name = PL.PLACES[spot][0]
        defenders = [x for x in self.living_in(world.wid)
                     if x.place == spot and x.age(self.day) >= 14 and not x.hidden]   # คนในคุก/ในด่านไม่อยู่บนเวที
        d = {"รอยแยก": f"กว้าง {world.rift:.1f} — ขั้นที่ลงมาได้ถึง {C.CHAOS_RANKS[min(cap, len(C.CHAOS_RANKS)-1)]}",
             "ถูกกด": f"ลงมาโลกมนุษย์แล้วถูกกดลง {C.CHAOS_DESCEND_PUSH} ขั้นตามกฎของโลกล่าง"}
        if defenders:
            v = max(defenders, key=lambda x: R.power(x, world, self.items))
            win, lose, margin, res = R.fight(self, world, c, v, rng, day=self.day)
            d["ผู้ต้านทาน"] = f"{v.name} — {res}"
            d["margin"] = round(margin, 3)
            d["winner"] = win.cid
            if R.has_anti_chaos(v, self.items):
                d["แก้ทาง"] = "ผู้ต้านทานรู้วิชาที่แก้ทางเผ่าโกลาหล"
            if win is not c:
                world.rift = max(0.0, world.rift - C.RIFT_GROWTH)
                # แพ้ศึกอาจถึงตาย (R.fight ฆ่าผู้แพ้ได้) — ผลต้องบอกว่าตาย ไม่ใช่แค่ถูกขับไล่กลับไป
                self.emit(world, "โกลาหลบุกโลกมนุษย์", c, v, ["ทำลาย", "ต่อสู้"],
                          "ถูกขับไล่" if c.alive else "ตาย",
                          f"{c.name}({c.realm_name()}) ทะลุรูหนอนลงมาถล่ม{spot_name} "
                          + (f"แต่ถูก{v.name}ขับไล่กลับไป" if c.alive else f"แต่สิ้นชีพด้วยมือ{v.name}"),
                          elapsed, d)
                return
        # ทำลายสถานที่ + กลืนกินแร่และของที่นั่น
        self.ruined[spot] = self.day + C.RUIN_YEARS * 365
        eaten = 0
        for x in self.living_in(world.wid):
            if x.place == spot:
                eaten += sum(x.mat_stock.values()) + len(x.items)
                x.mat_stock = {}
                x.items = [i for i in x.items if self.items[i].legend]
                x.place = rng.choice(PL.places_in(world.place_key))
        world.rift += C.RIFT_GROWTH
        world.heaven = max(0.0, world.heaven - 20.0)     # มวลปราณถูกกลืนไปด้วย
        d["ทำลาย"] = f"{spot_name}กลายเป็นซากปรักหักพัง {C.RUIN_YEARS} ปี"
        if eaten:
            d["กลืนกิน"] = f"แร่และของ {eaten} ชิ้นถูกย่อยสลาย"
        self.emit(world, "โกลาหลบุกโลกมนุษย์", c, None, ["ทำลาย", "ความตาย"], "ทำลายสำเร็จ",
                  f"{c.name}({c.realm_name()}) ทะลุรูหนอนลงมาถล่ม{spot_name}จนราบ "
                  f"รอยแยกในโลกมนุษย์กว้างขึ้น", elapsed, d)

    def _frontline(self, chosen, pool):
        """คนที่ถูกเกณฑ์ขึ้นมาจากโลกล่าง ย่อมถูกส่งไปยืนแนวหน้า

        ฟ้าเกณฑ์เขาขึ้นมาเพื่อศึกนี้ (ดู conscript) ถ้าสุดท้ายการคัดตัวยังเอาแต่คนที่เกิดบนแดนสูง
        อยู่แล้ว การถูกเกณฑ์ก็ไม่มีความหมายอะไรเลย — วัดจริง 313 ปี: ผู้ร่วมศึกบุกห้วงโกลาหล
        18 คน และคณะผนึก 25 คน **ไม่มีใครเกิดในโลกมนุษย์แม้คนเดียว** ทั้งที่ 42 คนขึ้นมาถึงแดนบนแล้ว
        จึงกันที่ไว้หนึ่งที่: ถ้าในทีมยังไม่มีผู้มาจากโลกล่าง ให้สลับคนที่อ่อนที่สุดในทีมออก
        และเอาผู้มาจากโลกล่างที่แรงที่สุดเข้าแทน (เฉพาะคนที่ผ่านเกณฑ์กำลังของทีมอยู่แล้ว)
        """
        if not C.FRONTLINE_FROM_BELOW or not chosen:
            return chosen
        risen_worlds = {w.wid for w in self.worlds if w.tier == 0}
        def from_below(c):
            return c.tier > 0 and getattr(c, "birth_wid", -1) in risen_worlds
        if any(from_below(c) for _sc, c in chosen):
            return chosen
        cand = [(sc, c) for sc, c in pool if from_below(c)]
        if not cand:
            return chosen
        best = max(cand, key=lambda x: x[0])
        out = list(chosen[:-1]) + [best]
        out.sort(key=lambda x: -x[0])
        return out

    def check_fate(self):
        """นิมิตที่หมดอายุแล้ว — เกิดตามที่เห็น หรือถูกเปลี่ยนไปแล้ว?

        นี่คือหัวใจของธีม "วิถีสวรรค์ vs การเลือกของคน" ที่กลายเป็นตัวเลขวัดได้จริง:
        ผู้มีระบบเห็นว่าใครจะตายวันไหน พอวันนั้นผ่านไปแล้ว เอนจินเทียบให้ว่าเขาเปลี่ยนมันได้ไหม
        (ไม่ได้นับว่าเขาเป็นคนเปลี่ยนเอง — โลกอาจเบนไปเพราะอย่างอื่นก็ได้ ซึ่งก็ยังเป็นเรื่องเล่า:
         "สิ่งที่ข้าเห็นไม่เกิดขึ้น" กับ "สิ่งที่ข้าเห็นเกิดขึ้นทั้งที่ข้าพยายามแล้ว")
        """
        # ตัดสินนิมิตที่หมดอายุของ "ทุกคน" ไม่ใช่แค่คนที่ยังมีชีวิต — เดิมวน self.living() นิมิตของผู้เห็นที่ตายไปแล้วจึงค้างไม่ถูก
        # ตัดสินตลอดกาล · ผู้เห็นที่ตายแล้วได้แค่นับผล (คนตายลงมือเป็นผู้กระทำเหตุการณ์ไม่ได้ — test_world_coherence 3.1)
        # แต่ละนิมิตถูกลบทันทีที่ตัดสิน จึงนับครั้งเดียวเสมอ
        for ch in self.cast:
            seen = getattr(ch, "foreseen", None)
            if not seen:
                continue
            for key in list(seen):
                day = seen[key]
                if self.day < day + C.FORESIGHT_GRACE_DAYS:
                    continue
                cid = int(key)
                del seen[key]
                if not (0 <= cid < len(self.cast)):
                    continue
                other = self.cast[cid]
                w = self.world(ch.world_id)
                if not ch.alive:
                    if other.alive or abs(other.death_day - day) > C.FORESIGHT_GRACE_DAYS:
                        ch.fate_changed += 1
                    else:
                        ch.fate_kept += 1
                    continue
                if other.alive:
                    ch.fate_changed += 1
                    self.emit(w, "เปลี่ยนชะตา", ch, other, ["ตัดสินใจ", "รู้แจ้ง"], "ชะตาเปลี่ยนไป",
                              f"{other.name}ควรตายไปแล้วตามนิมิตที่{ch.name}เห็น "
                              f"แต่วันนั้นผ่านไปโดยที่เขายังอยู่", 0,
                              {"สิ่งที่เห็นไว้": f"{other.name}จะตายวันที่ {day} ({E.date_words(day)})",
                               "สิ่งที่เกิดขึ้นจริง": f"{other.name}ยังมีชีวิตอยู่",
                               "เปลี่ยนชะตาได้แล้ว": f"{ch.fate_changed} ครั้ง"})
                elif abs(other.death_day - day) <= C.FORESIGHT_GRACE_DAYS:
                    ch.fate_kept += 1
                    self.emit(w, "ชะตาลิขิต", ch, other, ["ความตาย", "ตัดสินใจ"], "เป็นไปตามนิมิต",
                              f"{other.name}ตายตามที่{ch.name}เห็นในนิมิตไม่ผิดเพี้ยน — "
                              f"{getattr(other, 'death_cause', '')}", 0,
                              {"สิ่งที่เห็นไว้": E.date_words(day),
                               "สิ่งที่เกิดขึ้นจริง": E.date_words(other.death_day),
                               # เดิมเขียนว่า "ฝืนชะตาไม่สำเร็จ" ซึ่งไม่จริงในกรณีส่วนใหญ่ — เขา
                               # ไม่ได้พยายามฝืนอะไรเลย ตัวนับนี้นับแค่ว่านิมิตที่เห็นไว้เป็นจริง
                               "นิมิตที่เป็นจริงแล้ว": f"{ch.fate_kept} ครั้ง"})
                else:
                    # ตายแต่ไม่ตรงวันที่เห็น (ก่อนหรือหลังเกินช่วงผ่อนผัน) — เดิมนิมิตถูกลบเงียบๆ ไม่นับไม่บันทึก
                    # สิ่งที่เห็นไว้ไม่เกิดขึ้นตามนั้น = ชะตาเบนไป นับเป็นเปลี่ยนชะตา แต่บอกตรงๆ ว่านิมิตไม่เป็นจริง
                    ch.fate_changed += 1
                    when = "ก่อน" if other.death_day < day else "หลัง"
                    self.emit(w, "เปลี่ยนชะตา", ch, other, ["ความตาย", "รู้แจ้ง"], "นิมิตไม่เป็นจริง",
                              f"{other.name}ตาย{when}วันที่{ch.name}เห็นในนิมิต — สิ่งที่เห็นไว้ไม่เกิดขึ้นตามนั้น", 0,
                              {"สิ่งที่เห็นไว้": f"{other.name}จะตายวันที่ {day} ({E.date_words(day)})",
                               "สิ่งที่เกิดขึ้นจริง": f"ตายวันที่ {other.death_day} ({E.date_words(other.death_day)}) "
                                                     f"— {getattr(other, 'death_cause', '')}",
                               "เปลี่ยนชะตาได้แล้ว": f"{ch.fate_changed} ครั้ง"})

    def seclusion_diff(self, ch, world, yrs):
        """โลกเปลี่ยนไปอะไรระหว่างที่เขาอยู่ในด่าน — หัวใจของการกระโดดข้ามเวลาแบบรู้ตัว

        ถ้าออกจากด่านมาแล้วบันทึกเขียนแค่ "เขาออกมา" การข้ามเวลาก็ไม่มีความหมายในเชิงเรื่อง
        สิ่งที่ผู้อ่าน (และตัวละคร) ต้องรู้คือ ใครตายไปแล้ว ใครแซงขั้นเขาไป ศัตรูไปถึงไหน
        และโลกยังเป็นยุคเดิมหรือเปลี่ยนไปแล้ว
        """
        snap = getattr(ch, "seclude_snap", {}) or {}
        d = {"เวลาในด่าน": f"{yrs} ปี",
             "ที่ได้จากด่าน": f"ความเข้าใจ +{C.SECLUDE_INSIGHT_PER_YEAR * yrs:.1f} · "
                              f"กาย +{C.SECLUDE_REFINE_PER_YEAR * yrs:.2f}",
             "ขั้นของข้าตอนนี้": f"{ch.realm_name()} (ขั้นที่ {ch.rank()})"
                                  + (" — สะสมพอจะทะลวงขั้นแล้ว" if ch.at_bottleneck() else "")}
        died, rose, same = [], [], 0
        for cid, old in (snap.get("ties") or {}).items():
            i = int(cid)
            if not (0 <= i < len(self.cast)):
                continue
            o = self.cast[i]
            was_alive, was_rank = bool(old[1]), int(old[2])
            if was_alive and not o.alive:
                died.append(f"{o.name} ({getattr(o, 'death_cause', '') or 'ไม่ทราบสาเหตุ'})")
            elif o.alive and o.rank() > was_rank:
                rose.append(f"{o.name} {old[3]} → {o.realm_name()}")
            else:
                same += 1
        if died:
            d["คนที่ไม่ได้อยู่รอเขา"] = " · ".join(died[:4])
        if rose:
            d["คนที่ไต่แซงไปแล้ว"] = " · ".join(rose[:4])
        changes = []
        if snap.get("era") is not None and world.era != snap["era"]:
            changes.append(f"ยุคที่ {snap['era']} จบลงแล้ว ตอนนี้เป็นยุคที่ {world.era}")
        if snap.get("state") and world.state() != snap["state"]:
            changes.append(f"แดนจาก{snap['state']}กลายเป็น{world.state()}")
        now_orgs = sum(1 for o in self.orgs if o.alive)
        if snap.get("orgs") is not None and now_orgs != snap["orgs"]:
            diff = now_orgs - snap["orgs"]
            changes.append(f"สำนักในจักรวาล{'เพิ่มขึ้น' if diff > 0 else 'ล้มหายไป'} {abs(diff)} แห่ง")
        if snap.get("n_alive") is not None and world.n_alive != snap["n_alive"]:
            changes.append(f"คนในแดนจาก {snap['n_alive']} เป็น {world.n_alive}")
        if died:
            changes.append(f"คนใกล้ตัวจากไป {len(died)} คน")
        d["โลกที่เปลี่ยนไป"] = " · ".join(changes) if changes else "โลกยังเหมือนวันที่เขาปิดประตู"
        ch.seclude_snap = {}
        return d

    def conscript(self, world, rng):
        """ฟ้าลงมาเอาตัวคนที่พลังถึงเกณฑ์ขึ้นไป — **โดยไม่บอกว่าเอาไปทำอะไร**

        นี่คือสะพานเส้นเดียวที่คนโลกมนุษย์ข้ามไปถึงศึกกับเผ่าโกลาหลได้จริง (วัดจริง 307 ปี:
        ข้ามฟ้าจากโลกมนุษย์ด้วยตัวเอง 0 ครั้ง เพราะประตูแดนเซียนเปิดแค่ 0.4% ของเวลา) แต่สิ่งที่
        สำคัญกว่าสะพานคือ **ความไม่รู้**: คนข้างล่างไม่มีทางรู้ว่าข้างบนกำลังทำศึกอะไรอยู่ เขารู้
        แค่ว่าคนเก่งที่สุดของแดนถูกพาตัวไปแล้วไม่กลับมา เหลือไว้เป็นข่าวลือสองกระแสที่ขัดกันเอง
        และไม่มีใครยืนยันได้ว่าอันไหนจริง:
          "ฟ้าเกณฑ์คนไปทำศึกอะไรที่ไม่บอกใคร"  vs  "ฟ้ากลัวคนแข็งแกร่งจะขึ้นไปโค่นอำนาจ"
        ความบาดหมางที่เหลือไว้ (world.resentment) กลายเป็นแรงผลักของ "สงครามเบิกฟ้า" รุ่นต่อไป
        — คือวงจรที่ทำให้กำแพงฟ้าเป็นความขัดแย้งของโลก ไม่ใช่แค่กฎกติกาข้อหนึ่ง
        """
        if world.up is None:
            return
        up = self.world(world.up)
        pool = [c for c in self.living_in(world.wid)
                if c.sentient and not c.hidden and c.travel_dest < 0
                and c.realm >= C.CONSCRIPT_REALM_BAR
                and c.age(self.day) >= C.CONSCRIPT_MIN_AGE]
        if not pool:
            return
        taken = max(pool, key=lambda c: (c.rank(), -c.cid))   # ฟ้าเอาคนที่แรงที่สุดไปก่อน
        envoys = [c for c in self.living_in(up.wid)
                  if c.sentient and not c.hidden and c.rank() > taken.rank()]
        envoy = max(envoys, key=lambda c: (c.rank(), -c.cid)) if envoys else None
        kin = [cid for cid in (list(taken.children) + list(taken.parents)
                               + list(taken.disciples)
                               + ([taken.master_cid] if taken.master_cid >= 0 else [])
                               + ([taken.spouse] if taken.spouse is not None else []))
               if isinstance(cid, int) and 0 <= cid < len(self.cast) and self.cast[cid].alive]
        d = {"ผู้ถูกเกณฑ์": f"{taken.name} ({taken.realm_name()} ขั้นที่ {taken.rank()})",
             "เหตุผลที่แจ้ง": "ไม่มี — ทูตฟ้าไม่ตอบคำถามใด",
             "คนที่เหลืออยู่": ", ".join(self.cast[c].name for c in kin[:4]) or "ไม่มีใครใกล้ตัว"}
        if envoy is not None:
            d["ทูตจากแดนบน"] = f"{envoy.name} ({envoy.realm_name()})"
            for cid in kin:
                k = self.cast[cid]
                k.rivals[envoy.cid] = k.rivals.get(envoy.cid, 0) + C.CONSCRIPT_KIN_GRUDGE
            taken.rivals[envoy.cid] = taken.rivals.get(envoy.cid, 0) + 1
        world.resentment = min(C.RESENT_CAP,
                               getattr(world, "resentment", 0.0) + C.CONSCRIPT_RESENT)
        d["ความบาดหมางของแดน"] = f"{world.resentment:.1f}"
        # ย้ายขึ้นไปทั้งตัว โดย **ขั้นไม่ถูกรีเซ็ต** (เขาไม่ได้ข้ามฟ้าเอง เขาถูกพาไป)
        self.move_world(taken, up.wid)
        taken.tier = up.tier
        taken.peak_tier = max(taken.peak_tier, up.tier)
        taken.org = None
        pl = PL.places_in(up.place_key)
        if pl:
            taken.place = rng.choice(pl)
        self.emit(world, "เกณฑ์ขึ้นฟ้า", envoy or taken, taken, ["คน", "สูญเสีย"], "ถูกเกณฑ์",
                  f"ทูตจาก{up.name}ลงมาเอาตัว{taken.name}ขึ้นฟ้าไป ไม่มีใครได้รับคำอธิบายว่าเพื่ออะไร",
                  0, d)
        for text in (f"เล่ากันว่าข้างบนกำลังทำศึกอะไรอยู่ จึงต้องเกณฑ์คนที่พลังถึงเกณฑ์ขึ้นไปช่วย "
                     f"แต่ไม่มีใครยืนยันได้ — {taken.name}ก็ไม่เคยส่งข่าวกลับมา",
                     f"บางคนว่าฟ้ากลัวผู้ที่ไต่ถึงยอดจะขึ้นไปโค่นอำนาจของพวกที่อยู่มาก่อน "
                     f"จึงเอาตัว{taken.name}ไปเสียก่อนที่จะสายเกินไป"):
            self.rumors.append({
                "id": self.nid("r"), "kind": "เกณฑ์ขึ้นฟ้า", "subject": taken.cid,
                "world_id": world.wid, "place": taken.place, "text": text, "day": self.day,
                "true": False, "heard": set(),
            })
        self.trim_rumors()
        return taken

    def coalition_strike(self, world, elapsed, rng):
        """หลายสำนักรวมกำลังกันบุกผ่านรอยแยกเข้าไปปราบเจ้าโกลาหลถึงห้วงโกลาหล

        ออกแบบให้ **คนเดียวยังชนะไม่ได้เหมือนเดิม** — พลังของทีมไม่ใช่ผลบวกตรงๆ แต่ลดหลั่นลงตาม
        ลำดับ (COALITION_FALLOFF) คนที่สองช่วยได้ 60% ของพลังตัวเอง คนที่สาม 36% ไล่ลงไป การเอา
        คนอ่อนมากองรวมกันเยอะๆ จึงไม่ช่วยอะไร ต้องมีตัวจริงหลายคนพร้อมกันในโลกเดียวกันจริงๆ

        และสู้กันใน **ห้วงโกลาหล** ไม่ใช่ในโลกของฝ่ายบุก — เจ้าโกลาหลอยู่ในถิ่นที่มันแข็งที่สุด ส่วน
        ฝ่ายบุกถูกกดตามกฎของโลกที่สูงกว่า นี่คือราคาของการเลือกไปถึงตัวมันแทนที่จะรอมันมา

        ชนะแล้วมันไม่ตายถาวร (kill() ของเจ้าโกลาหลคือการสลายแล้วกลับมาแข็งขึ้น) แต่รอยแยกปิดสนิท
        และโลกได้พักจริง — เป็นวัฏจักรที่มีไคลแมกซ์ ไม่ใช่กำแพงตันแบบเดิม
        """
        lord = self.cast[self.lord_cid] if self.lord_cid is not None else None
        if lord is None or not lord.alive:
            return
        if lord.hidden:
            # มันสลายไปแล้วยังไม่คืนกลับ — ไม่มีอะไรให้ปราบ แต่รอยแยกยังเปิดอยู่ จึงยกไป "ปิดรอยแยก"
            # แทน วัดจริง 513 ปี: มันสลาย 27 ครั้ง ครั้งละ 2,000-12,000 วัน คือหายไปเกินครึ่งของ
            # ประวัติศาสตร์ ระหว่างนั้นไม่มีใครทำอะไรรอยแยกได้เลย จนบวมถึง 149.1 และโลกมนุษย์ล่ม
            return self.seal_rift(world, elapsed, rng)
        # ทั้งจักรวาลใช้รายชื่อชุดเดียวกันในการระดมพล ถ้าเพิ่งวัดไปว่าคนที่แรงที่สุดยังไม่ถึงเกณฑ์
        # แม้แต่จะ "เข้าร่วม" ทีม การสแกนซ้ำอีก 178 แดนก็ไม่มีทางได้ผลต่างออกไป จึงจำค่าไว้ก่อน
        # นี่ไม่ใช่คูลดาวน์ของการยกทัพ (การยกทัพยังเกิดได้ทันทีที่มีคนแรงพอ) แค่ข้ามการสแกนที่
        # พิสูจน์แล้วว่าไม่มีทางได้ผล วัดจริง: การสแกนนี้กิน 33-55% ของเวลาซิมโดยไม่เกิดอะไรเลย
        _probe = getattr(self, "_coalition_probe", None)
        cw = self.world(self.chaos_wid)
        # ระดมพลจาก **ทุกแดนที่ไม่ใช่ห้วงโกลาหล** ไม่ใช่เฉพาะแดนที่ถูกฉีก — แดนที่ถูกบุกบ่อยที่สุด
        # คือโลกมนุษย์ (tier 0) ซึ่งไม่มีวันมีใครแรงพอ วัดจริงตอนทดสอบครั้งแรกที่ดึงจากแดนเดียว:
        # ยกไป 3 ครั้ง กำลังรวมได้ 24.9-32.7 ปะทะเจ้าโกลาหล 90 — แพ้ทุกครั้งโดยไม่มีทางเป็นอื่น
        # ผู้ที่แรงพอจริงอยู่บนสวรรค์นอกชั้นฟ้า การ "รวมกำลัง" จึงต้องข้ามแดน ไม่งั้นไม่มีความหมาย
        def strength(c):
            return R.power(c, self.world(c.world_id), self.items, self.day)

        lord_power = R.power(lord, cw, self.items, self.day)
        floor = lord_power * C.COALITION_MIN_SHARE
        if (_probe is not None and self.day - _probe[0] < C.COALITION_PROBE_DAYS
                and _probe[1] < floor):
            return
        # ต้องกัน `is_lord` ออกจากกองกำลังที่ยกไปปราบมันเอง — ตัวกรองเดิมกรองด้วย "อยู่ในห้วง
        # โกลาหลไหม" ซึ่งเจ้าโกลาหลไม่เข้าข่าย เพราะ world_id ของมันคือแดนเซียน มันจึงผ่านตัวกรอง
        # แล้วขึ้นเป็นหัวหน้าทีมทุกครั้ง (แรงที่สุดในจักรวาล) วัดจริงจากรอบ 2,000 ปี: ศึกพันธมิตร
        # 7 ครั้ง **นำโดยถังซิน(เจ้าโกลาหล) ทั้ง 7 ครั้ง และแพ้ทั้ง 7 ครั้ง** — พลังของศัตรูถูกนับ
        # เป็นกำลังฝ่ายเราแล้วเอาไปสู้กับตัวมันเอง
        # คำนวณพลังครั้งเดียวแล้วใช้ซ้ำ — ของเดิมเรียก strength() สามรอบ (กรอง · เรียง · รวมพลัง)
        # ทำให้ R.power() ถูกเรียก 706,534 ครั้งต่อ 3,000 เหตุการณ์ = 235 ครั้ง/เหตุการณ์
        scored = [(strength(c), c) for c in self.living()
                  if self.world(c.world_id).kind != "chaos" and not c.is_lord
                  and not c.thrall and not c.hidden]
        self._coalition_probe = (self.day, max((sc for sc, _c in scored), default=0.0))
        pool = [(sc, c) for sc, c in scored if sc >= floor]
        if len(pool) < C.COALITION_MIN:
            # ระดมพลไม่สำเร็จก็ต้องติดคูลดาวน์ด้วย ไม่งั้นบรรทัดนี้จะถูกวิ่งซ้ำทุกเหตุการณ์ตราบใด
            # ที่เจ้าโกลาหลตื่นอยู่ — วัดจริงด้วย cProfile: กิน 55% ของเวลาซิมทั้งหมดโดยไม่เกิดอะไร
            world.last_coalition = self.day - C.COALITION_COOLDOWN + C.COALITION_FAIL_COOLDOWN
            return
        # พลังของฝ่ายบุกวัดจาก **โลกของตัวเอง** ไม่ใช่จากห้วงโกลาหลที่กำลังจะบุกเข้าไป
        # R.power() คิด world.tier * TIER_STEP เข้าไปในพลังด้วย ถ้าวัดฝ่ายบุกในห้วงโกลาหล (tier 2)
        # พวกเขาจะได้โบนัสของแดนชั้นสูงติดตัวฟรีๆ เพียงเพราะเดินเข้าไปยืนตรงนั้น — วัดจริงตอนเขียน
        # เทสต์: ทีมที่ "อ่อนที่สุด" ในโลกยังได้ 161.3 แซงเจ้าโกลาหลที่ 122.5 คือใครก็ปราบได้
        # ความได้เปรียบเจ้าถิ่นของมันจึงอยู่ที่ "มันได้พลังถิ่นตัวเอง ส่วนฝ่ายบุกไม่ได้" ตามธรรมชาติ
        pool.sort(key=lambda sc: -sc[0])
        top = pool[:C.COALITION_SIZE]
        top = self._frontline(top, pool)
        team = [c for _sc, c in top]
        if len(team) < C.COALITION_MIN:
            world.last_coalition = self.day - C.COALITION_COOLDOWN + C.COALITION_FAIL_COOLDOWN
            return

        anti = [c for c in team if R.has_anti_chaos(c, self.items)]
        team_power = sum(sc * (C.COALITION_FALLOFF ** i)
                         for i, (sc, _c) in enumerate(top))
        team_power += C.COALITION_ANTI_BONUS * len(anti)
        # รางวัลของการระดมคนได้มาก — ยิ่งเกินขั้นต่ำเท่าไหร่ยิ่งประสานกำลังกันได้ดีขึ้นเท่านั้น
        team_power *= 1.0 + C.COALITION_UNITY * max(0, len(team) - C.COALITION_MIN)
        # ตัดสินด้วยสมการเดียวกับการปะทะทุกคู่ในเอนจิน (rules.resolve_clash) ไม่ใช่เทียบตัวเลขตรงๆ
        # ศึกที่กำลังสูสีกันจึงพลิกได้จริง ไม่ใช่รู้ผลตั้งแต่ยังไม่เริ่ม
        home = lord_power * C.COALITION_HOME_EDGE
        # ตราประทับสุญตาสยบโกลาหล — ตรึงการบิดเบือนของถิ่นมันเอง ลดความได้เปรียบเจ้าถิ่นลงครึ่ง
        # นี่คือเหตุผลเดียวที่สมบัติชิ้นนี้มีอยู่ในโลก: ทำให้ศึกที่แพ้แน่ๆ กลายเป็นศึกที่มีลุ้น
        from ..treasures import (ANTI_CHAOS_HOME_CUT, ANTI_CHAOS_TREASURE,
                                has_anti_chaos_treasure)
        sealer = next((c for c in team if has_anti_chaos_treasure(c, self.items)), None)
        if sealer is not None:
            home *= (1.0 - ANTI_CHAOS_HOME_CUT)
            d_seal = f"{sealer.name}ชู{ANTI_CHAOS_TREASURE}ตรึงห้วงโกลาหลไว้"
        else:
            d_seal = None
        adv = team_power - home
        margin = abs(adv) / max(1.0, home)
        won = rng.random() < 1.0 / (1.0 + math.exp(-adv / C.TEMP))

        world.last_coalition = self.day
        leader = team[0]
        d = {
            "พันธมิตร": " · ".join(f"{c.name}({c.realm_name()})" for c in team),
            "กำลังฝ่ายพันธมิตร": f"{team_power:.1f}",
            "กำลังเจ้าโกลาหล": f"{home:.1f} (พลัง {lord_power:.1f} x เจ้าถิ่น "
                                f"{C.COALITION_HOME_EDGE} · สลายมาแล้ว {lord.lord_returns} ครั้ง)",
            "margin": round(margin, 3),
            "รอยแยก": f"{world.rift:.1f}",
        }
        if anti:
            d["วิชาแก้ทาง"] = " · ".join(c.name for c in anti)
        if d_seal:
            d["ตราประทับ"] = d_seal
        d["สายบำเพ็ญของทีม"] = " · ".join(PATHS.path_of(c) for c in team)

        if won:
            d["winner"] = leader.cid
            fallen = []
            # ชนะก็ยังมีคนไม่ได้กลับ — ยิ่งชนะฉิวเฉียดยิ่งเสียคน
            for c in team[1:]:
                if rng.random() < max(0.0, 0.45 - margin) and c.fate <= 0:
                    self.kill(c, f"สละชีพในศึกปราบ{lord.name}", killer=lord)
                    fallen.append(c.name)
            for c in team:
                if c.alive:
                    c.insight += 10      # รางวัลต้องเล็ก — ตั้ง 40 แล้ววัดจริงพบว่าทีมเดิมชนะซ้ำแล้ว
                                         # โตหนีจนศึกครั้งหลังไม่เหลือความไม่แน่นอนเลย
                                         # ไม่แจก "ชื่อเสียง" เป็นฟิลด์ใหม่ที่ไม่มีใครอ่าน —
                                         # ชื่อเสียงในเอนจินนี้ประกอบย้อนหลังจาก log อยู่แล้ว
                                         # (tiandao/ai/memory.py:update_reputation)
            world.rift = 0.0
            self.kill(lord, "ถูกพันธมิตรข้ามแดนปราบ", killer=leader)
            if fallen:
                d["ผู้สละชีพ"] = " · ".join(fallen)
            d["รอยแยกหลังศึก"] = "ปิดสนิท"
            self.emit(cw, "พันธมิตรปราบเจ้าโกลาหล", leader, lord, ["ทำลาย", "ต่อสู้", "ความตาย"],
                      "ปราบสำเร็จ",
                      f"{len(team)} ผู้แกร่งจากหลากแดน นำโดย{leader.name} รวมกำลังบุกผ่านรอยแยก"
                      f"เหนือ{world.name}เข้าห้วงโกลาหล และปราบ{lord.name}จนสลาย รอยแยกปิดสนิท",
                      elapsed, d)
            return

        d["winner"] = lord.cid
        fallen = []
        for c in team:
            if rng.random() < C.COALITION_CASUALTY and c.fate <= 0:
                self.kill(c, f"ดับสูญในห้วงโกลาหลด้วยน้ำมือ{lord.name}", killer=lord)
                fallen.append(c.name)
            elif c.alive:
                c.decay += 2.0
                c.near_death += 1
        world.rift += C.RIFT_GROWTH
        if fallen:
            d["ผู้ดับสูญ"] = " · ".join(fallen)
        d["รอยแยกหลังศึก"] = f"กว้างขึ้นเป็น {world.rift:.1f}"
        self.emit(cw, "พันธมิตรปราบเจ้าโกลาหล", leader, lord, ["ทำลาย", "ต่อสู้", "ความตาย"],
                  "พ่ายแพ้",
                  f"{len(team)} ผู้แกร่งจากหลากแดน นำโดย{leader.name} บุกผ่านรอยแยกเหนือ{world.name} "
                  f"เข้าห้วงโกลาหล แต่ถูก{lord.name}บดขยี้ รอยแยกยิ่งกว้างกว่าเดิม",
                  elapsed, d)

    def seal_rift(self, world, elapsed, rng):
        """ยกไปปิดรอยแยกตอนเจ้าโกลาหลไม่อยู่ — งานช่าง ไม่ใช่งานรบ

        ใช้ผู้ชำนาญวิชามิติกับค่ายกลเป็นหลัก (คนที่ปิดรอยต่อระหว่างภพได้) ปิดได้ทีละส่วน ไม่หมดในครั้ง
        เดียว และยังมีคนหายไปในรอยแยกได้จริง
        """
        if world.rift <= 0:
            return
        # เกณฑ์ผู้ปิดรอยแยก — ต้องตรงกับที่ docstring สัญญาไว้จริง คือ "มิติ **กับค่ายกล**"
        # ของเดิมเช็คแต่สายมิติ ซึ่งวัดจริงที่ปีที่ 513 มีคนรู้ทั้งจักรวาลแค่ 3 คน (วิชาสายมิติทั้ง 3
        # วิชาอยู่ tier 1 ขึ้นไป คนโลกมนุษย์เรียนไม่ได้เลย) ส่วนสายค่ายกลมีคนรู้ 262 คน — เงื่อนไข
        # จึงเป็นเท็จตลอดกาลแบบเดียวกับบั๊กชุดก่อน วัดจริง 121 ปีหลังแก้รอบที่แล้ว: ยกไปปิดรอยแยก
        # 0 ครั้ง รอยแยกโลกมนุษย์ค้างที่ 149 -> 158 ไม่ลดลงเลยสักครั้งเดียว
        def _sealer(c):
            if c.hidden or c.is_lord or c.thrall:
                return 0.0
            m = PORT.mastery(c) * 2.0
            for n in c.skills:
                sk = R.SKILL_INDEX.get(n)
                if sk and sk[1] == "ค่ายกล":
                    m += 1.0 + sk[3]
            if R.has_anti_chaos(c, self.items):
                m += 3.0
            return m

        crew = [c for c in self.living_in(world.wid) if _sealer(c) > 0]
        away = False
        if len(crew) < C.COALITION_MIN:
            # แดนที่ถูกฉีกคือแดนชั้นล่างสุด ซึ่งโดยโครงสร้างแล้วแทบไม่มีผู้ชำนาญพอ — ต้องเรียก
            # ข้ามแดนเหมือนศึกพันธมิตร ไม่งั้นโลกที่เดือดร้อนที่สุดคือโลกที่ช่วยตัวเองไม่ได้ตลอดกาล
            crew = [c for c in self.living()
                    if self.world(c.world_id).kind != "chaos" and _sealer(c) > 0]
            away = True
        if len(crew) < C.COALITION_MIN:
            return
        crew.sort(key=lambda c: -_sealer(c))
        crew = crew[:C.COALITION_SIZE]
        world.last_coalition = self.day
        before = world.rift
        closed = min(before, C.SEAL_PER_CREW * len(crew))
        world.rift = max(0.0, before - closed)
        leader = crew[0]
        fallen = []
        for c in crew[1:]:
            if rng.random() < C.SEAL_DEATH_P and c.fate <= 0:
                self.kill(c, "ถูกรอยแยกโกลาหลกลืนหาย")
                fallen.append(c.name)
        d = {"คณะปิดรอยแยก": " · ".join(c.name for c in crew),
             "ที่มาของคณะ": "ระดมข้ามแดน" if away else "คนในแดนนี้เอง",
             "รอยแยก": f"{before:.1f} -> {world.rift:.1f}",
             "เหตุที่ทำได้ตอนนี้": "เจ้าโกลาหลสลายไปยังไม่คืนกลับ"}
        if fallen:
            d["ผู้ถูกกลืนหาย"] = " · ".join(fallen)
        self.emit(world, "ปิดรอยแยกโกลาหล", leader, None, ["ทำลาย"], "ปิดได้บางส่วน",
                  f"{len(crew)} ผู้ชำนาญมิติและค่ายกลแห่ง{world.name} นำโดย{leader.name} "
                  f"ยกไปปิดรอยแยกขณะที่เจ้าโกลาหลยังไม่คืนกลับ", elapsed, d)

    def seal_lord(self, world, elapsed, rng):
        """ส่งคณะไปผนึกเจ้าโกลาหลขณะที่มันสลายอยู่ — ไม่ได้ฆ่ามัน แต่หยุดการสะสมพลังของมัน

        ทำไมกลไกนี้ถึงต้องมี: เมื่อการกลับมาของมันผูกกับ "ความตายทั่วจักรวาล" โลกก็ไม่มีทางหยุดมัน
        ได้ด้วยการอยู่เฉยๆ เพราะยังไงคนก็ตายทุกวัน การผนึกคือปุ่มเดียวที่โลกกดได้จริง และมันมีราคา
        สามชั้นตามที่เจ้าของโลกกำหนดไว้:
          1. **มีคนต้องตาย** อย่างน้อยหนึ่งคนเสมอ (LORD_SEAL_SACRIFICE) ไม่มีการผนึกที่ฟรี
          2. **แดนผู้ออกทุนจ่ายทรัพยากรมหาศาล** — เลือกแดนที่รวยที่สุดที่จ่ายไหว
          3. ข้อ 2 ทำให้เกิดผลตามมาเอง: แดนรวยจนลงทุกครั้งที่โลกต้องพึ่งมัน ส่วนแดนจนสะสมทรัพยากร
             ของตัวเองไปเรื่อยๆ จนไล่ทัน — ยกเว้นแดนที่หาสมบัติหรือทรัพยากรเก่งจริง ซึ่งจ่ายแล้วก็ยัง
             รวยอยู่ดี ความมั่งคั่งของ 126 แดนจึงสับเปลี่ยนกันเองไปตามประวัติศาสตร์ ไม่ต้องเขียนเพิ่ม
        """
        lord = self.cast[self.lord_cid] if self.lord_cid is not None else None
        if lord is None or not lord.hidden:
            return                      # ผนึกได้เฉพาะตอนมันสลายอยู่ ตอนมันตื่นต้องไปสู้เอา
        if getattr(self, "lord_seal", 0.0) > 0.0:
            return                      # ผนึกเดิมยังอยู่ ไม่มีเหตุให้ผนึกซ้ำ

        # ผู้ออกทุน: แดนที่คลังหนาที่สุดและจ่ายไหว — ไม่จำเป็นต้องเป็นแดนที่เดือดร้อนเอง
        n_before = getattr(self, "lord_seals_made", 0)
        cost = C.LORD_SEAL_COST * (1.0 + C.LORD_SEAL_COST_GROWTH * n_before)
        funder, best = None, 0.0
        for w in self.worlds:
            r = getattr(w, "resource", 0.0)
            if r >= cost and r > best:
                funder, best = w, r
        if funder is None:
            return                      # ทั้งจักรวาลยังไม่มีแดนไหนรวยพอ ต้องรอสะสมก่อน

        crew = [c for c in self.living()
                if self.world(c.world_id).kind != "chaos" and not c.is_lord
                and not c.hidden and not c.thrall]
        if len(crew) < C.LORD_SEAL_MIN:
            return
        crew.sort(key=lambda c: -R.power(c, self.world(c.world_id), self.items, self.day))
        scored_crew = [(R.power(c, self.world(c.world_id), self.items, self.day), c) for c in crew]
        crew = [c for _sc, c in self._frontline(scored_crew[:C.LORD_SEAL_SIZE], scored_crew)]

        team_power = sum(R.power(c, self.world(c.world_id), self.items, self.day) for c in crew)
        strength = min(100.0, C.LORD_SEAL_POWER_W * team_power)
        pool = getattr(self, "lord_pool", 0.0)
        funder.resource = best - cost
        self.lord_seal = strength
        self._lord_seal_day = self.day
        self.lord_seals_made = getattr(self, "lord_seals_made", 0) + 1
        # คูลดาวน์ของตัวเอง ไม่แตะ world.last_coalition — ของนั้นใช้ร่วมกันระหว่างศึกพันธมิตร
        # กับการปิดรอยแยก ถ้าการผนึกไปรีเซ็ตมันด้วย (ซึ่งเกิดบ่อยเพราะเจ้าโกลาหลสลายอยู่เกือบ
        # ตลอด) อีกสองอย่างจะอดทำงานไปด้วย — วัดจริง: ศึกพันธมิตร 0 ครั้งใน 93 ปี
        self.lord_seal_last = self.day

        # ราคาที่จ่ายด้วยชีวิต — ผู้นำคณะคือคนที่ยืนกลางผนึก จึงเป็นคนแรกที่ไม่ได้กลับออกมา
        leader = crew[0]
        fallen = list(crew[:C.LORD_SEAL_SACRIFICE])
        for c in crew[C.LORD_SEAL_SACRIFICE:]:
            if rng.random() < C.LORD_SEAL_EXTRA_DEATH_P:
                fallen.append(c)
        cost_txt = "{:,.0f} (เหลือ {:,.0f})".format(cost, funder.resource)
        d = {"คณะผนึก": " · ".join(c.name for c in crew),
             "แดนผู้ออกทุน": funder.name + " จ่าย " + cost_txt,
             "ความแรงผนึก": "{:.1f} — เสื่อมปีละ {}".format(strength, C.LORD_SEAL_DECAY_PER_YEAR),
             "ผลของผนึก": "เจ้าโกลาหลหยุดสะสมพลังจากความตายจนกว่าผนึกจะเสื่อมหมด",
             "พลังที่มันสะสมค้างไว้": "{:,.0f}/{:,.0f}".format(pool, C.LORD_POOL_TARGET),
             "ผู้สละชีวิต": " · ".join(c.name for c in fallen)}
        self.emit(world, "ผนึกเจ้าโกลาหล", leader, lord, ["ทำลาย", "ความตาย"], "ผนึกสำเร็จ",
                  f"{len(crew)} ผู้บำเพ็ญจากหลากแดน นำโดย{leader.name} ยกเข้าห้วงโกลาหลขณะที่"
                  f"{lord.name}ยังสลายอยู่ ร่วมกันลงมหาผนึกตรึงมันไว้ "
                  f"โดยแลกด้วยชีวิตของผู้ที่ยืนกลางผนึก", elapsed, d)
        for c in fallen:
            self.kill(c, "สละชีวิตลงมหาผนึกตรึงเจ้าโกลาหล")

    def chaos_raid(self, world, elapsed, rng):
        """เผ่าโกลาหลบุกมาทำลายทุกอย่างให้กลับเป็นความว่างก่อนกำเนิดจักรวาล"""
        # เจ้าโกลาหลไม่ออกปล้นหมู่บ้านเอง — การบุกเป็นงานของบริวาร เดิมมันถูกสุ่มเป็นผู้บุกได้ แล้วสู้ในแดนชั้นต่ำที่พลังมันถูกกด
        # จนแพ้ชาวบ้านขั้น 0 (seed 2027 ปีที่ 5: ขั้น 9 พลัง 91 แพ้ขั้น 0 พลัง 58 ห่าง 7.5) นับเป็นชัยชนะเดี่ยวเหนือเจ้าโกลาหล
        raiders = [c for c in self.living_in(self.chaos_wid) if c.age(self.day) >= 14 and not c.is_lord]
        prey = [c for c in self.living_in(world.wid) if c.age(self.day) >= 14]
        if not raiders or not prey:
            return
        c = rng.choice(raiders)
        prey.sort(key=lambda x: -R.power(x, world, self.items))
        v = rng.choice(prey[:3])          # ไล่ล่าผู้แข็งแกร่งก่อน แต่ไม่ใช่คนเดิมทุกครั้ง
        win, lose, margin, res = R.fight(self, world, c, v, rng, day=self.day)
        d = {"แพ้ทาง": "มนุษย์แพ้ทางเผ่าโกลาหล", "margin": round(margin, 3), "winner": win.cid}
        if R.has_anti_chaos(v, self.items):
            d["แก้ทาง"] = "รู้วิชาที่แก้ทางเผ่าโกลาหลได้"
        if v.alive and not v.thrall and rng.random() < C.CHAOS_THRALL_P:
            v.thrall = True
            # ติดเชื้อโกลาหล = เป็นโกลาหลเต็มตัวทันที ไม่เหลือส่วนของเผ่าเดิม (ผู้ใช้ตัดสิน กฎข้อ 7) — เดิมเพิ่มเลือดโกลาหลทีละ 0.2
            # ร่างกายยังเป็นมนุษย์ (กฎข้อ 5): กินข้าว อายุขัย เพศ ทอง/ข้าวที่ถือ ไม่ได้อยู่ในเลือด บัญชีจึงไม่ขยับ
            v.blood = {"chaos": 1.0}
            v.is_spirit = False
            v.org = None
            d["ตกเป็นพวกมัน"] = f"{v.name}ยอมสวามิภักดิ์ — ได้รับการดูแล แต่เป็นทาสของมัน"
        self.emit(world, "โกลาหลบุก", c, v, ["ทำลาย", "ความตาย"], res,
                  f"{c.name}({c.realm_name()}) บุก{world.name}ปะทะ{v.name} — {lose.name}เป็นฝ่ายเสีย",
                  elapsed, d)

    def mara_raid(self, world, elapsed, rng):
        mara_world = self.world(world.lateral[0])
        raiders = [c for c in self.living_in(mara_world.wid)
                   if c.realm >= 2 and c.age(self.day) >= 14]
        prey = [c for c in self.living_in(world.wid) if c.age(self.day) >= 14]
        if not raiders or not prey:
            return
            
        m = rng.choice(raiders)
        v = self._pick_raid_victim(m, prey, rng)
        if v is None:
            return
        if C.MARA_RAID_MATCH_REALM:
            # ส่งมารที่ขั้นพลังใกล้เหยื่อที่สุดมาบุก — เดิมสุ่มทั้งแดนมาร เหยื่อขั้น 1-3 จึงเจอมารขั้น 6
            # เป็นส่วนใหญ่ (วัดจริง 1,536 จาก 3,000 ครั้ง) การสู้กลับเลยไม่มีวันเกิดกับตัวละครของเรา
            # ลำดับ (ไม่กิน RNG เพิ่ม): ขั้นใกล้เหยื่อ → บุกครั้งล่าสุดนานที่สุด (raided_day) → cid
            # เดิมเสมอกันเอา cid น้อยเสมอ มารคนเดิมจึงถูกส่งมาทุกครั้ง (seed 42: 3 คนแรกถือ 35% ของ 1,754 ครั้ง)
            m = min(raiders, key=lambda c: (abs(c.realm - v.realm), getattr(c, "raided_day", -10 ** 9), c.cid))
        m.raided_day = self.day
        
        if world.defense_array > 0:
            if rng.random() < 0.80:  # โอกาสสกัดสำเร็จ 80%
                world.defense_array = max(0.0, world.defense_array - 15.0)
                d_array = {"ค่ายกลทำงาน": f"สกัดกั้นมารได้ พลังค่ายกลเหลือ {world.defense_array:.1f}/{world.defense_max:.1f}"}
                self.emit(world, "มารบุก", m, v, ["ทำลาย"], "ถูกสกัดกั้น",
                          f"ค่ายกลป้องกันโลกปกป้อง{v.name}จากการรุกรานของ{m.name}", elapsed, d_array)
                return
            else:
                world.defense_array = max(0.0, world.defense_array - 5.0)
                
        # ผู้ที่แข็งแกร่งพอไม่ยอมเป็นอาหาร — สู้กลับ (วัดจริงรอบ 3: ความแค้นต่อมารสะสมไว้ 15 ครั้ง
        # แต่ไม่มีทางชำระเลย เพราะมารอยู่อีกโลก ตรงนี้คือจุดที่ความแค้นได้ตอนจบ)
        if v.realm >= m.realm - C.MARA_FIGHT_REALM_GAP:
            p_win = min(C.MARA_FIGHT_WIN_MAX,
                        max(C.MARA_FIGHT_WIN_MIN,
                            0.5 + (v.realm - m.realm) * C.MARA_FIGHT_REALM_W
                            + (C.MARA_FIGHT_GRUDGE_W if m.cid in v.rivals else 0.0)))
            if rng.random() < p_win:
                had_grudge = m.cid in v.rivals
                v.kills += 1
                v.decay += 0.3
                v.rivals.pop(m.cid, None)          # ชำระแค้นแล้ว ไม่ต้องแบกต่อ
                self.kill(m, f"ถูก{v.name}สังหารขณะบุกโลกมนุษย์", killer=v)
                self.emit(world, "มารบุก", v, m, ["ต่อสู้", "ความตาย"], "ปราบมารได้",
                          f"{m.name}จากแดนมารจู่โจม{v.name} แต่คราวนี้{v.name}สู้กลับและสังหารมันลงได้",
                          elapsed, {"ล้างแค้นสำเร็จ": m.name} if had_grudge else {})
                return
            v.hp = max(1, getattr(v, "hp", 100) - C.MARA_FIGHT_LOSS_HP)
            v.decay += 0.5
        if rng.random() < C.MARA_CONVERT_P:
            v.blood["mara"] = v.blood.get("mara", 0.0) + 0.25
            R.normalize(v.blood)
            v.inner += 1.5
            self.emit(world, "มารบุก", m, v, ["ทำลาย", "เลือด"], "ถูกครอบงำ",
                      f"{m.name}จากแดนมารครอบงำ{v.name} เลือดมารลุกลาม", elapsed,
                      {"เผ่า": v.race()})
        elif v.fate > 0:
            # ชะตาช่วยได้ครั้งหนึ่ง เหมือนภัยพิบัติ — วัดจริง (รันเทียบรอบ 2): ผู้มีจิตใจ 15 จาก 15 คนที่ตาย
            # ตายเพราะมารบุกทั้งหมด อายุเรื่องเฉลี่ยแค่ ~7 ปี เรื่องจบก่อนได้เริ่ม คนรอดจะได้ "แผลกับความแค้น"
            # ต่อมารตัวนั้นแทน ซึ่งเป็นแรงผลักเนื้อเรื่องต่อ (แท็ก "เลือด" ทำให้ผู้มีจิตใจหยุดคิดใหม่)
            v.fate -= 1
            v.near_death += 1
            v.decay += 0.5
            v.rivals[m.cid] = v.rivals.get(m.cid, 0) + C.MARA_RAID_GRUDGE
            self.emit(world, "มารบุก", m, v, ["ทำลาย", "เลือด"], "รอดตายด้วยชะตา",
                      f"{m.name}จากแดนมารจู่โจม{v.name} แต่{v.name}หนีรอดมาได้อย่างหวุดหวิด และจดจำใบหน้ามันไว้",
                      elapsed, {"ความแค้น": m.name})
        else:
            self.kill(v, f"ถูก{m.name}จากแดนมารกินเป็นอาหาร", killer=m)
            self.emit(world, "มารบุก", m, v, ["ทำลาย", "ความตาย"], "ตาย",
                      f"{m.name}จากแดนมารจับ{v.name}ไปเป็นอาหาร", elapsed, {})

    def bid_purse(self, ch, world):
        """กำลังซื้อของคนคนหนึ่งในงานประมูลของยุทธภพ คิดเป็นหน่วยปราณ

        ผู้ฝึกจ่ายด้วยหินวิญญาณ ปุถุชนจ่ายด้วยเหรียญทองซึ่งแปลงเป็นปราณตามอัตราตลาด
        (ดู economy.stone_gold) สองสกุลจึงอยู่ในกระดานเดียวกันได้โดยไม่ต้องแกล้งว่า
        มันเป็นสกุลเดียวกัน — และผลที่ตามมาคือปุถุชนสู้ราคาของวิเศษไม่ไหวโดยโครงสร้าง
        ไม่ใช่เพราะเราเขียนกฎห้ามเขาเข้าร่วม
        """
        qi = EC.purse_qi(ch)
        gold = ch.money.get(world.tier, 0.0)
        if C.STONE_GOLD_PER_QI > 0:
            qi += gold / C.STONE_GOLD_PER_QI
        return qi

    def market_auction(self, world, rng):
        """ตลาด/เมืองเปิดงานประมูลใหญ่ ใครอยู่ที่นั่นก็ได้เข้าร่วม — ไม่ต้องรอให้มีพ่อค้ามาจัด"""
        here = {}
        for c in self.living_in(world.wid):
            if c.hidden or c.travel_dest >= 0 or c.age(self.day) < 14:
                continue
            if self.bid_purse(c, world) < C.AUCTION_MIN_QI:
                continue      # ไม่มีทรัพย์ติดตัว = มาดูได้ แต่ไม่นับเป็นคนที่ทำให้งานเกิด
            if 0 <= c.place < len(PL.PLACES) and PL.PLACES[c.place][3] in C.AUCTION_PLACES:
                here.setdefault(c.place, []).append(c)
        spots = [(p, folk) for p, folk in sorted(here.items()) if len(folk) >= 3]
        if not spots:
            return
        place, folk = spots[rng.randrange(len(spots))]
        # เจ้าภาพหมุนเวียน — ไม่สุ่ม
        # เดิมเลือกพ่อค้าที่รวยที่สุดเสมอ คนเดิมจึงเป็นเจ้าภาพทุกงานของที่นั้น (seed 42: เจ้าภาพคนเดียว 37 งานใน 100 ปี)
        # ลำดับ: ไม่ได้เปิดงานนานที่สุดก่อน → คนอาชีพค้าขายก่อนคนอื่นเมื่อเท่ากัน → รวยกว่า → cid (ถ้าหมุนเฉพาะในหมู่พ่อค้า
        # ตลาดที่มีพ่อค้าคนเดียวก็ยังเป็นคนเดิมทุกงาน)
        folk.sort(key=lambda c: (getattr(c, "auction_hosted_day", -10 ** 9),
                                 getattr(c, "profession", "") not in C.AUCTION_HOSTS,
                                 -self.bid_purse(c, world), c.cid))
        host = folk[0]
        host.auction_hosted_day = self.day
        outcome, text, d = self.auction(host, world, rng, {})
        if outcome == "ประมูล":
            self.emit(world, "เปิดประมูล", host, None, ["แลกเปลี่ยน", "ทรัพย์", "คน"], outcome,
                      f"{PL.PLACES[place][0]}เปิดงานประมูลใหญ่ — {text}", 0, d)

    def auction(self, host, w, rng, d):
        """งานประมูล — เหตุการณ์หมู่ ไม่ใช่เรื่องของคนเดียว

        เดิมเหตุการณ์นี้แค่บวกเงินให้เจ้าภาพแล้วจบ ("จัดงานประมูลได้กำไร 300 เหรียญ") ทั้งที่งานประมูล
        คือฉากที่นิยายกำลังภายในใช้รวมคนหลายฝ่ายไว้ในที่เดียว ตอนนี้จึงดึงคนที่อยู่สถานที่เดียวกันมาสู้ราคากันจริง
        แล้วส่งรายชื่อผู้ร่วมงานกับราคาที่เสนอไปให้ชั้นเรื่องเล่าใช้เขียนฉากที่มีคนพูดหลายคน

        ประมูลแบบราคาที่สอง: ผู้ชนะจ่ายเท่าราคาสูงสุดของคนที่แพ้ + 1 (ไม่จ่ายเต็มเพดานตัวเอง)
        เป็นกติกาที่ทำให้ "เกือบได้" มีความหมาย และเกิดความแค้นระหว่างผู้แข่งขันอย่างมีเหตุผล
        """
        wid = w.wid
        here = [c for c in self.living_in(wid)
                if c.cid != host.cid and not c.hidden and c.travel_dest < 0
                and c.place == host.place and c.age(self.day) >= 14
                and self.bid_purse(c, w) >= C.AUCTION_MIN_QI]
        here.sort(key=lambda c: (-self.bid_purse(c, w), c.cid))
        bidders = here[:C.AUCTION_MAX_BIDDERS]
        if len(bidders) < 2:
            # ไม่มีคนพอจะสู้ราคา กลายเป็นการเร่ขายธรรมดา
            earn = rng.randint(30, 120)
            WAGES.set_gold(self, host, w.tier, host.money.get(w.tier, 0) + earn, "street_sale")
            return "ค้าขาย", f"{host.name}ตั้งแผงขายของ แต่ไม่มีคนมากพอจะเปิดประมูล ได้ {earn} เหรียญ", d

        lot_item = None
        for iid in getattr(host, "items", []):
            it = self.items.get(iid)
            if it is not None and (lot_item is None or it.grade > self.items[lot_item].grade):
                lot_item = iid
        lot_name = self.items[lot_item].name if lot_item is not None else rng.choice(C.AUCTION_LOTS)
        # มูลค่าของล็อตนี้มี "หางหนัก" — ของส่วนใหญ่ธรรมดา นานๆ ครั้งมีของที่เปลี่ยนชีวิตคน
        # ใช้ล็อกนอร์มัลเพราะมูลค่าเกิดจากปัจจัยหลายอย่าง **คูณกัน** (คุณภาพ x ความหายาก x
        # สภาพ x วาสนา) ผลคูณของตัวแปรสุ่มหลายตัวลู่เข้าหาล็อกนอร์มัลเสมอ ต่างจากผลบวก
        # ที่ลู่เข้าหาการแจกแจงปกติ — ของเดิมใช้ randint ซึ่งแบนราบ ไม่มีของในตำนานเลย
        base = PHYS.lognormal_value(sum(C.AUCTION_BASE_PRICE) / 2.0,
                                    C.LOT_VALUE_SIGMA, rng.random())
        base *= (1 + (self.items[lot_item].tier if lot_item else 0))
        # ตาราง AUCTION_BASE_PRICE เขียนไว้เป็นเหรียญทองตั้งแต่ยุคที่มีสกุลเดียว แปลงเป็น
        # หน่วยปราณให้อยู่กระดานเดียวกับกระเป๋าของผู้ร่วมประมูล ไม่งั้นราคาจะอยู่คนละมาตรา
        # กับกำลังซื้อ แล้วทุกคนจะจ่ายด้วยเหรียญทองล้วนเหมือนเดิม (วัดแล้วเจอจริง:
        # "จ่ายเป็นหินวิญญาณ 0.0 หน่วย" ทุกงาน)
        if C.STONE_GOLD_PER_QI > 0:
            base /= C.STONE_GOLD_PER_QI

        # มูลค่าในใจของแต่ละคน — **ส่วนตัวและไม่เท่ากัน** (independent private values)
        # ของเดิมคำนวณจากความโลภกับขั้นพลังแบบตายตัว คนกลุ่มเดิมจึงชนะทุกงานตลอดกาล
        # ในทฤษฎีการประมูล ความไม่แน่นอนของมูลค่าส่วนตัวคือสิ่งที่ทำให้ราคาปิดมีความหมาย
        bids = []
        for c in bidders:
            want = C.AUCTION_GREED_W * getattr(c, "greed", 0.5) + 0.3 + 0.05 * c.realm
            private = PHYS.lognormal_value(base * want, C.BID_VALUE_SIGMA, rng.random())
            # ราคาที่เสนอถูกปัดลงเป็นทศนิยมตามความละเอียดที่ประกาศในบันทึกตั้งแต่ต้นทาง
            # (ดู _auction_q) บัญชีที่โอนจริง ตัวเลขใน deltas และข้อความในบันทึกจึงเป็น
            # "ราคาเดียวกัน" ไม่ใช่ราคาเต็มความละเอียดอันหนึ่งกับราคาที่ถูกปัดให้อ่านง่ายอีกอันหนึ่ง
            # (วัดจริง: ยอดที่ย้ายมือต่างจากราคาที่รายงานอยู่ 0.0467 หน่วยปราณทุกงาน)
            bids.append((_auction_q(min(self.bid_purse(c, w), private)), c))
        # ประมูลแบบวิกเครย์: ผู้ชนะจ่ายเท่าราคาอันดับสอง (ดู physics.second_price)
        idx, pay = PHYS.second_price([b[0] for b in bids])
        winner = bids[idx][1]
        rest = sorted((b for i, b in enumerate(bids) if i != idx),
                      key=lambda b: (-b[0], b[1].cid))
        runner_up = rest[0][1]
        # ปัดลง ไม่ปัดใกล้สุด — ราคาต้องไม่เกินเพดานของผู้ชนะและไม่เกินราคาอันดับสอง+ก้าว
        price = _auction_q(min(bids[idx][0], pay * C.AUCTION_STEP))
        d["ผู้เข้าประมูล"] = len(bids)
        d["ราคาตั้งต้น"] = f"{base:,.1f} หน่วยปราณ"
        if price <= 1e-6:
            return "ค้าขาย", f"{host.name}เปิดประมูลแต่ไม่มีใครสู้ราคา", d

        # จ่ายด้วยหินวิญญาณก่อน ขาดเท่าไรค่อยเติมด้วยเหรียญทอง — และเป็นการ **ย้ายมือ**
        # ไม่ใช่การเผา (ดู economy.transfer_qi) ถ้าใช้ burn_qi บัญชีปราณของโลกจะรั่วทุกครั้ง
        # ที่มีคนซื้อของ
        grade = min(len(EC.GRADE_NAMES) - 1, w.tier)
        paid = EC.transfer_qi(winner, host, float(price), grade)
        left = price - paid
        if left > 0 and C.STONE_GOLD_PER_QI > 0:
            gold = min(winner.money.get(w.tier, 0.0), left * C.STONE_GOLD_PER_QI)
            winner.money[w.tier] = winner.money.get(w.tier, 0.0) - gold
            host.money[w.tier] = host.money.get(w.tier, 0.0) + gold
        d["จ่ายเป็นหินวิญญาณ"] = f"{paid:,.1f} หน่วยปราณ"
        if lot_item is not None:
            host.items.remove(lot_item)
            winner.items.append(lot_item)
        # คนที่พลาดของไปอย่างฉิวเฉียดย่อมเก็บไปคิด ส่วนเจ้าภาพได้ไมตรีจากลูกค้า
        runner_up.rivals[winner.cid] = runner_up.rivals.get(winner.cid, 0) + 1
        winner.bonds[host.cid] = winner.bonds.get(host.cid, 0) + 1
        host.bonds[winner.cid] = host.bonds.get(winner.cid, 0) + 1

        d["ของที่ประมูล"] = lot_name
        # เรียงจากราคาสูงไปต่ำ ผู้ชนะอยู่หัวแถวเสมอ — เดิมเรียงตามลำดับผู้เข้าประมูล (ตามกระเป๋า)
        # คนอ่าน (และชั้นเรื่องเล่า) จึงเห็นราคาแรกในแถวน้อยกว่าราคาที่ผู้ชนะจ่าย แล้วเข้าใจว่า
        # ผู้ชนะจ่ายแพงกว่าที่ใครเสนอ ทั้งที่เป็นแค่ลำดับการแสดงผล
        ranked = [bids[idx]] + rest
        d["ผู้ร่วมประมูล"] = " · ".join(f"{c.name} (สู้ถึง {b:.1f})" for b, c in ranked)
        d["ผู้ชนะ"] = f"{winner.name} จ่าย {price:.1f} หน่วยปราณ"
        d["ราคาที่จ่าย"] = price
        d["คู่แข่งคนสุดท้าย"] = runner_up.name
        d["ราคาที่คู่แข่งสู้ถึง"] = rest[0][0]
        # ผู้ชนะ/ผู้แพ้เป็นผู้กระทำของบรรทัดตัวเอง (เจ้าภาพเป็นผู้ถูกกระทำ) — เดิมเจ้าภาพเป็นผู้กระทำทั้งสามเหตุการณ์ ประวัติของเจ้าภาพ
        # จึงเต็มไปด้วยประมูล (seed 42: เจ้าภาพคนเดียว 112 จาก 168 เหตุการณ์ของตัวเอง) · ข้อความ รายละเอียด และจำนวนเหตุการณ์คงเดิม
        self.emit(w, "เปิดประมูล", winner, host, ["แลกเปลี่ยน", "ทรัพย์", "คน"], "ชนะประมูล",
                  f"{winner.name}ประมูล{lot_name}ไปได้ในราคา {price:.1f} หน่วยปราณ "
                  f"เฉือน{runner_up.name}ไปอย่างหวุดหวิด", 0, dict(d))
        self.emit(w, "เปิดประมูล", runner_up, host, ["แลกเปลี่ยน", "ทรัพย์", "คน"], "พลาดประมูล",
                  f"{runner_up.name}สู้ราคา{lot_name}จนสุดตัว แต่แพ้{winner.name}ไปเพียงก้าวเดียว",
                  0, dict(d))
        return "ประมูล", (f"{host.name}เปิดงานประมูล{lot_name} มีผู้ร่วมสู้ราคา {len(bids)} คน "
                          f"{winner.name}เป็นผู้ชนะที่ราคา {price:.1f} หน่วยปราณ"), d

    def _pick_raid_victim(self, m, prey, rng):
        """มารเลือกเหยื่อแบบนักล่า ไม่ใช่สุ่มทั้งโลก — สุ่มถ่วงน้ำหนักด้วยการทอยครั้งเดียว (เดินซ้ำได้)

        เดิม rng.choice(prey) ทำให้ยอดฝีมือกลางเมืองหลวงโดนจับกินพอๆ กับเด็กเลี้ยงแพะที่ชายป่า
        ซึ่งขัดกับตรรกะโลก: มารล่าคนที่อ่อนกว่า อยู่โดดเดี่ยว อยู่ใกล้รอยแยก/แดนอันตราย หรือกลางทาง
        ส่วนเมือง ตลาด และสำนักมีผู้คนกับค่ายกลคุ้มกัน
        """
        here = {}
        for c in prey:
            here[c.place] = here.get(c.place, 0) + 1
        cands, weights = [], []
        for c in prey:
            if c.hidden:
                continue                          # ซ่อนตัวอยู่ในแดนลับ มารหาไม่เจอ
            # มารที่กินคนมาแล้วหลายศพย่อม "หิวและกล้าขึ้น" — เลิกเลือกแต่คนอ่อน แล้วเริ่มเล็งเหยื่อ
            # ที่สมศักดิ์ศรีขึ้นเรื่อยๆ วัดจริงจากบันทึก 104 ปี: มารตัวเดียว (เมอร์กิต เยซูเก ที่ 2)
            # กินตัวเอกไป 4 คนจาก 9 การตายของรอบนั้น เพราะมันเลือกคนอ่อนได้ตลอดไปโดยไม่มีวัน
            # เจอคนที่สู้กลับได้ — ความกล้าที่โตตามจำนวนศพทำให้วงจรนี้จบด้วยตัวมันเอง
            bold = min(C.MARA_BOLD_CAP, getattr(m, "kills", 0) * C.MARA_BOLD_PER_KILL)
            w = (C.MARA_VICTIM_REALM_DECAY + bold) ** c.realm
            if c.realm > m.realm:
                w *= C.MARA_VICTIM_STRONGER + bold   # สู้ไม่ได้ มันไม่เสี่ยง (แต่ยิ่งหิวยิ่งเสี่ยง)
            if c.travel_dest >= 0:
                w *= C.MARA_VICTIM_TRAVEL         # กลางทางไม่มีใครช่วย
            else:
                ptype = PL.PLACES[c.place][3] if 0 <= c.place < len(PL.PLACES) else ""
                w *= C.MARA_VICTIM_PLACE.get(ptype, 1.0)
                if here.get(c.place, 0) <= 1:
                    w *= C.MARA_VICTIM_ALONE      # อยู่คนเดียว
            cands.append(c)
            weights.append(w)
        total = sum(weights)
        if total <= 0:
            return None
        r = rng.random() * total
        for c, w in zip(cands, weights):
            r -= w
            if r <= 0:
                return c
        return cands[-1]
