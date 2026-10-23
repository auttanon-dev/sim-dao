# -*- coding: utf-8 -*-
"""Sim — ลูปหลักและนาฬิกาโลก"""
from ._common import *  # noqa: F401,F403
from ._common import _REACH_CACHE, _PLACE_SETS, _CENTERS, _reach_from, _auction_q  # noqa: F401


class ClockMixin:
    # ------------------------------------------------------------ ลูปหลัก
    # ------------------------------------------------------------ นาฬิกาโลก
    # งานของโลก (ทรัพยากรฟื้น ปราณไหลเข้า ประชากร ภัยประจำเดือน วิกฤต) เดิมทำงานเฉพาะตอนมีตัวละคร
    # ถึงคิว ถ้าทุกคนปิดด่านหรือหลับยาว โลกทั้งใบก็หยุดตาม แล้วค่อยคิดรวบเป็นก้อนเดียวตอนมีคนตื่น
    # และถ้าคิวตัวละครว่าง ซิมหยุดทั้งที่ธรรมชาติควรเดินต่อ (SIM_DAO_AUTONOMOUS_WORLD_DESIGN_TH.md §5.1)
    # ตอนนี้โลกมีใบนัดของตัวเองทุก WORLD_TICK_DAYS วัน ถ้าตรงวันกับเทิร์นตัวละคร งานของโลกทำก่อน
    def _advance_eco(self):
        """ทรัพยากรฟื้นตามวันที่ผ่านไปจริง — เรียกได้ทั้งจากเทิร์นตัวละครและนาฬิกาโลก ไม่นับวันซ้ำ"""
        elapsed = self.day - self.eco_day
        self.eco_day = self.day
        self.eco_regen(elapsed)

    def _mara_seal_tick(self, rng):
        """มหาผนึกหมื่นมารเดินปีละครั้ง: เสื่อมตามเวลา + แรงสั่นสะเทือน (สุ่มปีละครั้ง) + ฝ่ายธรรมะซ่อมเมื่ออ่อนแอ

        เดิมคำนวณใน _next_turn ซึ่งคือ **ต่อเทิร์นของตัวละคร** — MARA_SEAL_SHOCK_P = 0.04 จึงถูกสุ่มหลายพันครั้งต่อปี
        (แรงสั่นราว 1.75% × หลายร้อยครั้ง) ผนึกพังในปีที่ 5 ทั้งที่การเสื่อมตามเวลา 0.5%/ปี ต้องใช้ 200 ปี และ
        MARA_SEAL_REPAIR_P ถูกตั้งไว้แต่ไม่มีใครเรียก ผนึกที่พังจึงไม่มีวันกลับ (test_world_coherence 4.5)"""
        if getattr(self, "mara_seal_day", None) is None:
            self.mara_seal_day = self.day       # เซฟเก่า: ผนึกเสื่อมถึงวันนี้แล้วด้วยวิธีเดิม เริ่มนับปีจากตอนนี้
        years = (self.day - self.mara_seal_day) // 365
        if years <= 0:
            return
        self.mara_seal_day += years * 365
        mortal = self.worlds[0]
        decay = years * C.MARA_SEAL_DECAY_PER_YEAR * self.nature_speedup(mortal)   # โลกที่ถูกรีดหนัก ผนึกเสื่อมเร็วขึ้น
        if rng.random() < C.MARA_SEAL_SHOCK_P:            # ปีละครั้ง ไม่ใช่ต่อเทิร์น
            decay += rng.uniform(0.5, 3.0)
        self.mara_seal = max(0.0, self.mara_seal - decay)
        if self.mara_seal <= C.MARA_SEAL_WEAK_THRESHOLD and not self.mara_seal_notified_weak and not self.mara_seal_broken:
            self.mara_seal_notified_weak = True
            self.emit(mortal, "มหาผนึกสั่นคลอน", None, None, ["ทำลาย"], "ผนึกอ่อนแอ",
                      f"⚠️⚡ [มหาผนึกสั่นคลอน] แดนลับรอยแยกผนึกหมื่นมารสะกดโลกเริ่มอ่อนกำลังลง (เหลือ {self.mara_seal:.1f}%) ไอปีศาจเริ่มรั่วไหลสู่โลกมนุษย์!",
                      0, {"พลังผนึก": f"{self.mara_seal:.1f}%"})
        if self.mara_seal <= C.MARA_SEAL_BROKEN_THRESHOLD and not self.mara_seal_broken:
            self.mara_seal_broken = True
            self.emit(mortal, "มหาผนึกแตกพัง", None, None, ["ทำลาย", "ความตาย"], "ผนึกพังทลาย",
                      f"🚨💀 [มหาผนึกแตกพัง] มหาผนึกสะกดหมื่นมารในแดนลับรอยแยกพังทลายลงแล้ว! แดนมารและโลกมนุษย์เชื่อมต่อถึงกันโดยสมบูรณ์!",
                      0, {"พลังผนึก": "พังทลาย (0.0%)", "สัญจร": "เปิดทางเชื่อมต่อโลกมนุษย์-แดนมาร"})
        if self.mara_seal >= C.MARA_SEAL_WEAK_THRESHOLD:
            return
        # ซ่อม: ผู้บำเพ็ญฝ่ายธรรมะในโลกมนุษย์ (แดนที่ผนึกตั้งอยู่) — ไม่มีใครพอ ผนึกก็พังต่อไป
        crew = sorted((c for c in self.living_in(mortal.wid)
                       if c.moral >= C.MARA_SEAL_REPAIR_MORAL and c.realm >= C.MARA_SEAL_REPAIR_REALM
                       and not c.is_chaos() and not c.hidden),
                      key=lambda c: (-c.realm, c.cid))[:C.MARA_SEAL_REPAIR_CREW]
        if not crew or rng.random() >= C.MARA_SEAL_REPAIR_P:
            return
        before = self.mara_seal
        self.mara_seal = min(C.MARA_SEAL_INITIAL,
                             self.mara_seal + sum(c.realm for c in crew) * C.MARA_SEAL_REPAIR_PER_REALM)
        was_broken = self.mara_seal_broken
        if self.mara_seal > C.MARA_SEAL_BROKEN_THRESHOLD:
            self.mara_seal_broken = False
        if self.mara_seal > C.MARA_SEAL_WEAK_THRESHOLD:
            self.mara_seal_notified_weak = False
        lead = crew[0]
        self.emit(mortal, "ซ่อมมหาผนึก", lead, None, ["ปกป้อง"],
                  "ผนึกกลับคืน" if was_broken and not self.mara_seal_broken else "ซ่อมสำเร็จ",
                  f"{lead.name}นำผู้บำเพ็ญฝ่ายธรรมะ {len(crew)} คนซ่อมมหาผนึกหมื่นมาร "
                  f"({before:.1f}% → {self.mara_seal:.1f}%)", 0,
                  {"พลังผนึก": f"{self.mara_seal:.1f}%", "ผู้ร่วมซ่อม": ", ".join(c.name for c in crew)})

    def _world_tick(self, rng):
        """งานประจำของโลกหนึ่งรอบ ณ วันที่นาฬิกาโลกนัดไว้ แล้วนัดรอบถัดไป"""
        self.day = max(self.day, self.world_tick_day)
        self.world_tick_day = self.day + C.WORLD_TICK_DAYS
        self._advance_eco()
        if C.GUARDIANS_ENABLED:
            GUARD.tick(self)
        HH.tick(self)
        if C.FOOD_ENABLED:
            FOOD.tick(self, self.day - self.food_day)
        if C.WAGES_ENABLED:
            WAGES.tick(self, self.day - self.food_day)
        NEWS.tick(self)                     # ข่าวความตายที่เดินทางมาถึงรอบนี้ (ก่อนความแค้นจางตามเวลา)
        self.fade_grudges(self.day - self.food_day)
        self.check_processes()
        self.food_day = self.day
        if self.day - getattr(self, "prune_day", 0) >= 365:
            self.prune_day = self.day
            self.prune_departed()
        WT.tick(self, rng)      # ต้นไม้โลกในแดนลับต้นกำเนิด (ดู tiandao/worldtree.py)
        self._mara_seal_tick(rng)
        # เดิมเรียกทุกเหตุการณ์ ซึ่งวน 126 แดนทุกครั้งเพื่อบวกทรัพยากรของไม่กี่วัน —
        # โปรไฟล์จริง: 5.0 วินาทีจาก 100 (5%) โดยได้ผลเท่ากันทุกประการถ้าสะสมเป็นก้อน
        if self.day - getattr(self, "_portal_regen_day", -10**9) >= C.WORLD_TICK_DAYS:
            PORT.regen(self, self.day - getattr(self, "_portal_regen_day", 0))
            self._portal_regen_day = self.day
        PORT.tick(self, rng)    # การสร้างประตูมิติ (ดู tiandao/portals.py)
        # งานประมูลใหญ่ของตลาด — ทอยครั้งเดียวต่อแดนมนุษย์ต่อรอบโลก (AUCTION_EVENT_P = โอกาสต่อหนึ่งช่วงเวลาโลก)
        for w in self.worlds:
            if w.kind == "mortal" and rng.random() < C.AUCTION_EVENT_P:
                self.market_auction(w, rng)

        # มารบุกโลกมนุษย์ — ทอยครั้งเดียวต่อแดนมนุษย์ที่ติดแดนมารต่อรอบโลก (ผนึกแตก โอกาส × 2.5 เท่าเดิม)
        # เดิมทอย MARA_RAID_P ทุกเทิร์นของตัวละครใน _step: seed 42 ใน 100 ปี 1,754 ครั้ง (17.5 ต่อปี)
        mara_raid_p = C.MARA_RAID_P * (2.5 if getattr(self, "mara_seal_broken", False) else 1.0)
        for w in self.worlds:
            if (w.kind == "mortal" and w.lateral and self.world(w.lateral[0]).kind == "mara"
                    and rng.random() < mara_raid_p):
                self.mara_raid(w, 0, rng)
        if self.day - getattr(self, "last_disaster_day", 0) >= C.WORLD_TICK_DAYS:
            round_days = self.day - getattr(self, "last_disaster_day", 0)
            self.last_disaster_day = self.day
            
            # Sect Resource Distribution & Facilities
            for org in self.orgs:
                if org.alive and org.members:
                    # Assign Facilities
                    if not hasattr(org, "facilities"): org.facilities = {}
                    cast_len = len(self.cast)
                    if "หอโอสถ" not in org.facilities or not (0 <= org.facilities["หอโอสถ"] < cast_len) or not self.cast[org.facilities["หอโอสถ"]].alive:
                        alchs = [c for c in org.members if 0 <= c < cast_len and self.cast[c].alive and getattr(self.cast[c], "alch_rank", 0) > 0]
                        if alchs: org.facilities["หอโอสถ"] = max(alchs, key=lambda c: getattr(self.cast[c], "alch_rank", 0))

                    if "หอศาสตรา" not in org.facilities or not (0 <= org.facilities["หอศาสตรา"] < cast_len) or not self.cast[org.facilities["หอศาสตรา"]].alive:
                        smiths = [c for c in org.members if 0 <= c < cast_len and self.cast[c].alive and getattr(self.cast[c], "forge_rank", 0) > 0]
                        if smiths: org.facilities["หอศาสตรา"] = max(smiths, key=lambda c: getattr(self.cast[c], "forge_rank", 0))

                    if "ลานฝึกยุทธ" not in org.facilities or not (0 <= org.facilities["ลานฝึกยุทธ"] < cast_len) or not self.cast[org.facilities["ลานฝึกยุทธ"]].alive:
                        fighters = [c for c in org.members if 0 <= c < cast_len and self.cast[c].alive and self.cast[c].realm >= 4]
                        if fighters: org.facilities["ลานฝึกยุทธ"] = max(fighters, key=lambda c: self.cast[c].realm)
                    
                    # เครื่องพิมพ์เงินที่ซ่อนอยู่: เดิม `monthly_resource = 10000` ถูกเสก
                    # ขึ้นมาทุกเดือนให้ทุกสำนัก แล้วหารให้ศิษย์ — สำนักที่มีศิษย์เอกคนเดียว
                    # จะได้คนละ 4,000 ต่อเดือน = 48,000 ต่อปี **จากอากาศ**
                    # วัดจริงโลก 50 ปี: คนรวยที่สุดถือ 2.28 ล้าน ทั้งที่ลงมือแค่ 27 ครั้ง
                    # ตลอดชีวิต และมีรายได้ที่บันทึกไว้รวมกันแค่ 113 เหรียญ
                    # ตอนนี้ทรัพย์ของสำนักมาจาก **ค่าบำรุงที่ศิษย์จ่ายเข้ามา** เท่านั้น
                    # เป็นการกระจายซ้ำ ไม่ใช่การสร้างเงินใหม่ — และเป็นกลไกที่ถูกต้องของ
                    # สำนักในแนวนี้อยู่แล้ว (สำนักเก็บส่วย แล้วเลี้ยงศิษย์)
                    # ---- ผลผลิตจริงของสำนัก: คอบบ์-ดักลาส ศิษย์ × อาณาเขต ----
                    # ค่าบำรุงจากศิษย์ยังเก็บอยู่ (เป็นการกระจายซ้ำ) แต่ตอนนี้มี
                    # **ผลผลิตที่ขุดได้จริง** เพิ่มเข้ามา ซึ่งถูกหักออกจากคลังฟ้าจริงๆ
                    # สำนักจึงรวยได้ก็ต่อเมื่อมีทั้งคนและแผ่นดินที่ปราณหนา — และการ
                    # ที่สำนักหนึ่งรวยขึ้นแปลว่าโลกจนลงเท่านั้นพอดี ไม่มีใครได้ฟรี
                    self.sect_dues(org)

                    self.sect_mine(org)

            # ------------------------------------------------
            # Divine Spirits Hunting Demons
            # ------------------------------------------------
            living_now = self.living()
            # บัญชาสวรรค์เป็นหน้าที่รบของผู้ใหญ่ ทั้งผู้ล่าและเป้าหมายต้องพ้นวัยเด็ก
            # มิฉะนั้นสิ่งมีชีวิตที่เกิดมาพร้อมสายเลือดวิญญาณ/มารจะออกรบตั้งแต่อายุหนึ่งปี
            spirits = [c for c in living_now
                       if c.age(self.day) >= 14 and getattr(c, "is_spirit", False) and BODY.can_fight(c)]
            demons = [c for c in living_now
                      if c.age(self.day) >= 14 and getattr(c, "is_demon", False)]
            if spirits and demons:
                if self.rng.random() < PHYS.hazard_p(C.CRUSADE_PER_YEAR, round_days):
                    hunter = self.rng.choice(spirits)
                    target = self.rng.choice(demons)
                    safe_print(f"\n⚔️ [บัญชาสวรรค์] เผ่าวิญญาณศักดิ์สิทธิ์ [{hunter.name}] บุกสังหารมารร้าย [{target.name}] เพื่อรักษาสมดุลโลก!")
                    import tiandao.combat as combat
                    combat.resolve_combat(hunter, target, self.worlds[0], self, lethal=True)
                    # เดิมบล็อกนี้ print() อย่างเดียว ไม่ emit — เหตุการณ์ดราม่าที่สุดของโลก
                    # จึงไม่มีอยู่ในประวัติศาสตร์ ไม่ขึ้นใน log ไม่ถูกนับเป็นจุดเปลี่ยนของใคร
                    # และโรงงานนิยายมองไม่เห็นเลยสักครั้ง วัดจริง 121 ปี: 0 บรรทัดใน log
                    self.emit(self.worlds[0], "บัญชาสวรรค์", hunter, target,
                              ["ต่อสู้", "ความตาย"],
                              # ผู้ล่าตายในศึกนี้ได้ (lethal=True) — ผลต้องบอกความตายของผู้ล่า ไม่ใช่ "มารหนีรอด"
                              # เฉยๆ ราวกับผู้ล่ายังอยู่ (test_world_coherence 3.1: ศพเป็นผู้กระทำในเทิร์นเดียวกัน)
                              "ตาย" if not hunter.alive else ("สังหารมารสำเร็จ" if not target.alive else "มารหนีรอด"),
                              f"{hunter.name}แห่งเผ่าวิญญาณศักดิ์สิทธิ์รับบัญชาสวรรค์ "
                              f"บุกสังหาร{target.name}ผู้ตกเป็นมาร เพื่อรักษาสมดุลของโลก"
                              + ("" if hunter.alive else f" แต่{hunter.name}ดับสิ้นในศึกนั้นเอง"),
                              0, {"เหตุแห่งบัญชา": "เผ่าวิญญาณศักดิ์สิทธิ์ล้างมารตามหน้าที่",
                                  "ชะตาของมาร": "ดับสูญ" if not target.alive else "รอดไปได้",
                                  "ชะตาของผู้ล่า": "ดับสิ้น" if not hunter.alive else "รอดกลับมา"})
            
            # Demon Temptation (Possession) — ตัวแปรลูปตั้งชื่อ pc ตั้งใจ ห้ามใช้ ch ซ้ำ: บั๊กจริงที่เจอ
            # ตอนรัน --llm scale ยาว — "for ch in living_now" เดิมทับตัวแปร ch ของตัวละครที่เพิ่ง pop
            # จากคิวด้านบน (line ~697) ทำให้โค้ดหลังจากนี้ (ch.hidden ฯลฯ จนถึง actor=ch) กลาย
            # เป็นอ้างอิงถึงคนละคนไปเลย ทุก ~30 วันที่บล็อกนี้ทำงาน — เจ้าของ turn จริงไม่เคยถูก
            # schedule ต่อเลย ทำให้หลุดจากคิวถาวรทีละคน สะสมจนคิวว่างหมดทั้งที่ยังมีคนเป็นๆ อยู่
            for pc in living_now:
                # จิตมารเป็นวิกฤตของคนที่เติบโตพอจะมีกรรม/ความทะเยอทะยานของตนเอง
                # เด็กเคยถูกเลือกจากลูปประชากรโลกนี้ แม้เทิร์นของเด็กเองจะถูกกันไว้แล้ว
                if (pc.age(self.day) >= 14
                        and not getattr(pc, "is_demon", False)
                        and not getattr(pc, "is_spirit", False)
                        and not getattr(pc, "is_beast", False)):
                    if getattr(pc, "karmic_debt", 0) > 1000 or getattr(pc, "ambition", 0) > 80:
                        if self.rng.random() < PHYS.hazard_p(C.DEMON_TEMPTATION_PER_YEAR, round_days):
                            pc.is_demon = True
                            pc.dao = "วิถีมาร"
                            if pc.org is not None and pc.org < len(self.orgs):
                                # Leave current sect
                                org = self.orgs[pc.org]
                                if pc.cid in org.members: org.members.remove(pc.cid)
                                if pc.cid in org.core_disciples: org.core_disciples.remove(pc.cid)
                                if pc.cid in org.inner_disciples: org.inner_disciples.remove(pc.cid)
                                if pc.cid in org.outer_disciples: org.outer_disciples.remove(pc.cid)
                            pc.org = None
                            # เดิม print() เฉยๆ เช่นกัน — การตกเป็นมารคือจุดเปลี่ยนชีวิตที่ใหญ่ที่สุด
                            # ที่ตัวละครหนึ่งจะมีได้ แต่ไม่เคยถูกบันทึกไว้เลย
                            self.emit(self.world(pc.world_id), "มารสิงร่าง", pc, None,
                                      ["ความตาย"], "ตกเป็นมาร",
                                      f"{pc.name}ถูกจิตมารเข้าครอบงำเพราะกิเลสหนา "
                                      f"ละทิ้งสำนักเดิม กลายเป็นเผ่ามารอย่างสมบูรณ์",
                                      0, {"เหตุที่ถูกครอบงำ":
                                              ("กรรมหนัก" if getattr(pc, "karmic_debt", 0) > 1000
                                               else "ทะเยอทะยานเกินตัว"),
                                          "วิถีใหม่": "วิถีมาร"})

            # Beast Horde Siege
            beast_kings = [c for c in living_now if getattr(c, "is_beast", False) and c.realm >= 4]
            for king in beast_kings:
                if not getattr(king, "has_human_form", False):
                    king.has_human_form = True
                    # มีแค่ 5 ชื่อ โลกที่เดินนานจึงมีราชันย์อสูรเพลิงหลายตัวพร้อมกัน
                    king.name = self.unique_name(
                        "ราชันย์อสูร" + self.rng.choice(["เพลิง", "ทมิฬ", "สายฟ้า", "โลหิต", "น้ำแข็ง"]),
                        old=king.name, marker="ตัวที่")
                    safe_print(f"\n🐉 [คลื่นสัตว์อสูร] สัตว์อสูรบำเพ็ญตบะทะลวงขั้นสำเร็จ จำแลงกายเป็นมนุษย์ นามว่า [{king.name}]!")
                
                if self.rng.random() < PHYS.hazard_p(C.BEAST_CITY_RAID_PER_YEAR, round_days):
                    if self.cities:
                        targets = [city for city in self.cities if "ชายแดน" in city.get("type_desc", "") or "หน้าด่านสำนัก" in city.get("type_desc", "")]
                        if targets:
                            target = self.rng.choice(targets)
                            safe_print(f"\n🌋 [คลื่นสัตว์อสูรบุกเมือง] [{king.name}] นำกองทัพอสูรบุกโจมตีเมือง <{target['name_th']}>!")
                            ruler_cid = target.get("ruler_cid", -1)
                            if 0 <= ruler_cid < len(self.cast) and self.cast[ruler_cid].alive:
                                ruler = self.cast[ruler_cid]
                                # Fake combat for siege
                                if king.realm > ruler.realm:
                                    safe_print(f" -> 🔴 เมืองแตก! [{ruler.name}] พ่ายแพ้ต่อราชันย์อสูรและสิ้นชีพ! กฎหมายเมืองล่มสลาย!")
                                    self.kill(ruler, "อสูรบุกเมือง", killer=king)
                                    target["law_strictness"] = 0
                                else:
                                    safe_print(f" -> 🟢 ป้องกันเมืองสำเร็จ! [{ruler.name}] สังหารราชันย์อสูรได้ เมืองสงบสุข!")
                                    self.kill(king, "ถูกผู้ปกครองเมืองสังหาร", killer=ruler)
                                    ruler.max_hp = getattr(ruler, "max_hp", 100) + 50
                                    safe_print(f" -> 🔮 [{ruler.name}] ดูดซับแก่นอสูร พลังชีวิตสูงสุดเพิ่มขึ้น!")

            # Imperial Spy Network
            if len(self.orgs) > 0:
                target_sect = self.rng.choice(self.orgs)
                if target_sect.alive:
                    stealth_level = self.rng.randint(50, 100)
                    if stealth_level > getattr(target_sect, "alert_level", 50):
                        intel_gathered = self.rng.randint(10, 50)
                        target_sect.threat_level = min(
                            100, getattr(target_sect, "threat_level", 0) + intel_gathered)
                        # log silently or print (using print here for engine logs as requested by user)
                        safe_print(f"\n🕵️‍♂️ [องครักษ์เสื้อแพร] แทรกซึมสำเร็จ! พบว่า {target_sect.name} ซ่องสุมกำลัง (ภัยคุกคาม: {target_sect.threat_level}/100)")
                    else:
                        safe_print(f"\n🔴 [องครักษ์เสื้อแพร] ความแตก! สายลับถูกจับกุมและสังหารโดย {target_sect.name}")
                        
            for w in self.worlds:
                w.disaster_timer = getattr(w, "disaster_timer", 0) + 1
                w.current_disaster = rng.choice(["ปกติ", "กบฏราชสำนัก", "โรคระบาดใหญ่", "สมบัติโบราณปรากฏ"])
                if w.current_disaster == "กบฏราชสำนัก":
                    safe_print(f"🚨💥 [ภัยพิบัติแผ่นดิน] {w.name} เกิดกบฏราชสำนัก!")
                elif w.current_disaster == "โรคระบาดใหญ่":
                    safe_print(f"🚨🦠 [ภัยพิบัติแผ่นดิน] {w.name} เกิดโรคระบาด!")
                elif w.current_disaster == "สมบัติโบราณปรากฏ":
                    safe_print(f"🚨📜 [ภัยพิบัติแผ่นดิน] {w.name} สมบัติปรากฏ!")
                SEASONS.maybe_trigger_disaster(self, w, rng)

        # นับประชากรใหม่เป็นรอบ ก่อนเอาตัวเลขไปคิดปราณที่ไหลเข้าโลก
        if self.day - getattr(self, "_recount_day", -10**9) >= C.WORLD_TICK_DAYS:
            self._recount_day = self.day
            self.recount_worlds()
        # บังคับกฎ "สมบัติฟ้าดินไม่มีวันสูญหาย" เป็นรอบ — ตรวจผลลัพธ์ ไม่ใช่ไล่อุดทีละทางที่รั่ว
        if self.day - getattr(self, "_legend_sweep_day", -10**9) >= C.LEGEND_SWEEP_DAYS:
            self._legend_sweep_day = self.day
            self.reseal_lost_legends()
        for w in self.worlds:
            # สะสมงานประจำโลกไว้ทำเป็นก้อนทุก WORLD_TICK_DAYS แทนที่จะทำทุกเหตุการณ์ — ผลเท่าเดิม
            # เพราะทั้งปราณไหลเข้าและการเพิ่มประชากรคิดจาก "จำนวนวันที่ผ่านไป" อยู่แล้ว แต่พอมี 120 แดน
            # การวนทุกแดนทุกเหตุการณ์กลายเป็นงานที่หนักที่สุดของซิมไปเลย
            if self.day - w.checked_day < C.WORLD_TICK_DAYS:
                continue
            R.heaven_inflow(w, w.n_mortal, self.day - w.checked_day)
            self.repopulate(w, self.day - w.checked_day)
            
            if w.wid == 0:
                self.check_fate()
            if getattr(w, "resentment", 0.0) > 0.0:
                yrs = (self.day - w.checked_day) / 365.0
                w.resentment = max(0.0, w.resentment - C.RESENT_DECAY_PER_YEAR * yrs)
            if w.tier == 1:
                if w.n_alive >= C.HEAVEN_POP_LIMIT:
                    if not w.is_closed:
                        # ฟ้าปิดประตูด้วยการ **ตั้งค่ายกลขึ้นใหม่** ไม่ใช่ปิดเฉยๆ ถ้าไม่ตั้งใหม่
                        # ค่ายกลที่เคยถูกทุบเหลือ 0 จะค้างอยู่อย่างนั้น แล้วทุกครั้งที่โควตา
                        # ประชากรปิดประตูอีก คนเดียวก็ทุบเปิดได้ในหมัดเดียว (วัดจริงหลังเปิดใช้
                        # สงครามเบิกฟ้า: "เปิดสวรรค์" 37 ครั้งใน 102 ปี ทั้งที่ควรเป็นเรื่องใหญ่)
                        w.defense_array = w.defense_max
                    w.is_closed = True
                elif w.n_alive < C.HEAVEN_POP_LIMIT * 0.8:
                    w.is_closed = False
                    
            w.checked_day = self.day
            notes = R.check_world(self, w, rng)
            if notes is not None:
                self.emit(w, "ยุคล่ม", None, None, ["ความตาย"], "วัฏจักร",
                          f"{w.name} สิ้นพลังฟ้า ยุคหนึ่งจบลง ผู้ล่วงลับ {len(notes)} คน",
                          0, {"โลกตกระดับ": f"เหลือชั้น {w.tier}",
                              "ผู้ล่วงลับ": ", ".join(notes)})

        CRISES.tick(self)

    def requeue(self, ch, day):
        """ย้ายเทิร์นที่รออยู่ของคนนี้ไปเป็นวันที่กำหนด — คิวต้องมีใบเดียวต่อคน (ดู persist._repair_queue)

        O(ขนาดคิว) จึงใช้เฉพาะเหตุที่นานๆ เกิด เช่น ความหิวดึงคนออกจากด่านหรือส่งคนไปหาอาหาร
        """
        self.queue = [(d, c) for d, c in self.queue if c != ch.cid]
        heapq.heapify(self.queue)
        heapq.heappush(self.queue, (max(day, self.day), ch.cid))
