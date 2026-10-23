# -*- coding: utf-8 -*-
"""Sim — กิจกรรมยาว (ActionProcess)"""
from ._common import *  # noqa: F401,F403
from ._common import _REACH_CACHE, _PLACE_SETS, _CENTERS, _reach_from, _auction_q  # noqa: F401


class ProcessMixin:
    # ------------------------------------------------------------ กิจกรรมยาว (models.ActionProcess, แบบ §5.2)
    def start_process(self, ch, kind, days, payload=None, yield_rate=0.0):
        """เริ่มกิจกรรมยาววันนี้ ครบกำหนดอีก `days` วัน — การบำเพ็ญที่ค้างอยู่ได้ผลถึงวันนี้ก่อนถูกแทน"""
        self.settle_routine(ch)
        ch.process = ActionProcess(kind, self.day, self.day + max(0, int(days)), self.day, yield_rate,
                                   dict(payload or {}))
        return ch.process

    def accrue_process(self, ch):
        """คิดผลของกิจกรรมยาวตามวันที่ทำไปจริงจนถึงวันนี้ ไม่เกินกำหนดจบ — คืนจำนวนวันที่เพิ่งคิด
        ปิดด่าน: ความเข้าใจและการกลั่นตามปีที่รู้สึก (วัน/365 × yield_rate ซึ่งคือ gamma ของปราณที่นั่น)"""
        p = ch.process
        if p is None:
            return 0
        if p.progress_day < 0:
            # เริ่มผ่านช่องเดิม (ไม่รู้วันเริ่ม) — ใช้วันในภาพโลกตอนเข้าด่าน ไม่มีก็นับหนึ่งปีก่อนครบกำหนด
            start = p.payload.get("snap", {}).get("day")
            p.start_day = p.progress_day = int(start) if start is not None else p.end_day - 365
        upto = min(self.day, p.end_day)
        days = max(0, upto - p.progress_day)
        if days and p.kind == "seclusion":
            felt = days / 365.0 * (p.yield_rate or 1.0)
            ch.insight += C.SECLUDE_INSIGHT_PER_YEAR * felt
            ch.refine += C.SECLUDE_REFINE_PER_YEAR * felt
        elif days and p.kind == "cultivation":
            R.cultivate(ch, days * (p.yield_rate or 1.0), self.items)
        elif days and p.kind == "upbringing":
            CHILD.accrue(self, ch, p, days)
        p.progress_day = max(p.progress_day, upto)
        return days

    def interrupt_process(self, ch, reason):
        """หยุดกิจกรรมยาวกลางทางวันนี้ — คืน True ถ้าหยุดจริง
        ปิดด่าน: ได้ผลถึงวันนี้ แล้วออกจากด่านในเทิร์นวันนี้พร้อมเหตุ (บล็อกออกจากด่านใน _step)
        เดินทาง: หยุดอยู่ที่ต้นทาง — ยังไม่มีตำแหน่งกลางทางบนแผนที่"""
        p = ch.process
        if p is None or not ch.alive or p.end_day <= self.day:
            return False
        stats = self.__dict__.setdefault("process_stats", {})
        stats[f"{p.kind}:{reason}"] = stats.get(f"{p.kind}:{reason}", 0) + 1
        if p.kind == "seclusion":
            self.accrue_process(ch)
            p.end_day = self.day
            ch.seclude_cut = reason
        elif p.kind == "cultivation":
            self.settle_routine(ch)                  # เลิกบำเพ็ญ เทิร์นถัดไปยังเป็นวันเดิม
            return True
        elif p.kind == "upbringing":
            self.settle_routine(ch)                  # เด็กเลือกกิจวัตรใหม่วันนี้ (requeue ข้างล่าง)
        else:
            ch.process = None
            self.emit(self.world(ch.world_id), "หยุดเดินทาง", ch, None, ["เดินทาง"], "หยุดกลางทาง",
                      f"{ch.name}ต้องหยุดการเดินทาง — {reason}", 0, {"เหตุ": reason})
        if any(c == ch.cid for _, c in self.queue):
            # ผู้ที่กำลังอยู่ในเทิร์นของตัวเอง (เช่นคนเดินทางที่ไปรบเองแล้วแพ้) ไม่มีใบในคิว — ท้ายเทิร์นนัดให้เอง
            # ถ้า requeue ตรงนี้จะได้สองใบ และโหลดเซฟแล้ว _repair_queue ตัดใบหนึ่งทิ้ง โลกเดินต่างจากไม่เซฟ
            self.requeue(ch, self.day)
        return True

    def conceive(self, mother, father, initiator):
        """ตั้งครรภ์ (แบบ §7.2) — ครรภ์เป็น ActionProcess บนแม่ คลอดเมื่อครบ GESTATION_DAYS (check_processes)
        `initiator` คือฝ่ายที่ชวน ตระกูลของเด็กตามฝ่ายนี้ก่อนเหมือนตอนเกิดทันที"""
        mother.pregnancy = ActionProcess("pregnancy", self.day, self.day + C.GESTATION_DAYS, self.day, 0.0,
                                         {"father": father.cid, "initiator": initiator.cid})
        return mother.pregnancy

    def end_pregnancy(self, mother, reason):
        """ครรภ์สิ้นสุดก่อนคลอด — แท้ง บาดเจ็บสาหัส อดอาหาร หรือแม่ตาย คืน True ถ้ามีครรภ์ให้จบ"""
        p = mother.pregnancy
        if p is None:
            return False
        mother.pregnancy = None
        stats = self.__dict__.setdefault("process_stats", {})
        stats[f"pregnancy:{reason}"] = stats.get(f"pregnancy:{reason}", 0) + 1
        if mother.alive:
            mother.postpartum_until = self.day + C.POSTPARTUM_DAYS
            self.emit(self.world(mother.world_id), "แท้ง", mother, None, ["คน", "เลือด"], "สูญเสียครรภ์",
                      f"{mother.name}สูญเสียครรภ์ — {reason}", 0, {"เหตุ": reason,
                                                                  "อายุครรภ์": f"{self.day - p.start_day} วัน"})
        return True

    def deliver(self, mother):
        """คลอดเมื่อครบกำหนด — ทารกเกิดที่ที่แม่อยู่ สายเลือด ธาตุ ตระกูล และโบนัสผู้ฝึกตนเหมือนการเกิดเดิม
        แล้วแม่พักฟื้น POSTPARTUM_DAYS ผู้ปกครองคือแม่ (หรือพ่อ) ทันทีผ่าน guardians.at_birth"""
        p = mother.pregnancy
        mother.pregnancy = None
        mother.postpartum_until = self.day + C.POSTPARTUM_DAYS
        father = self.cast[p.payload["father"]]
        a, t = (father, mother) if p.payload.get("initiator") == father.cid else (mother, father)
        w = self.world(mother.world_id)
        rng = self.rng
        d = {}
        child = self.spawn(w, age_years=0)
        if C.FOOD_ENABLED:
            child.food = 0.0       # ทารกไม่ได้พกเสบียงมา กินจากยุ้งฉางของที่ที่เกิด
        if C.WAGES_ENABLED:
            child.gold_endowed = True   # ทารกไม่ได้ทุนตั้งต้นจากอากาศ — ได้จากกระเป๋ากลางของครัวเรือนแม่เท่าที่มี (B3c)
            home = HH.of(self, mother)
            gift = min(C.WAGE_START_GOLD, max(0.0, home.purse.get(w.tier, 0.0))) if home is not None else 0.0
            if gift > 0:
                HH.transfer(self, home, child, -gift, w.tier)
        blood = {}
        for kk in C.BLOODS:
            v = (a.blood.get(kk, 0.0) + t.blood.get(kk, 0.0)) * CL.INHERIT_MIX
            if v > 0.05:
                blood[kk] = min(1.0, v)
        if sum(blood.values()) > 1.0:
            s = sum(blood.values())
            blood = {kk: v/s for kk, v in blood.items()}
        child.blood = blood
        child.bonds[a.cid] = 10
        child.bonds[t.cid] = 10
        # โบนัสทายาทผู้ฝึกตน
        p_realm = a.realm + t.realm
        if p_realm > 0:
            child.insight += p_realm * 2.0
            child.refine += p_realm * 2.0
            d["ทายาทผู้ฝึกตน"] = f"{child.name} ได้รับพรสวรรค์มหาศาลตั้งแต่เกิด!"
            # กลายพันธุ์: เลขสุ่มตัวเดียวเท่าเดิม ใช้กับทุกสายที่ลูกมีจริงเท่ากัน (เลือดเป็นสัดส่วนที่ส่งต่อทางพันธุกรรม — ผู้ใช้ตัดสิน)
            # เดิมบรรทัดนี้อยู่นอกลูป ค่า v/kk ค้างจากรอบสุดท้าย (chaos) — ลูกผู้ฝึกตนทุกคนได้เลือดโกลาหลจากที่ไม่มีที่มา
            # (seed 16 ปีที่ 30/60/90: 195/215/237 คนที่พ่อแม่ไม่มีเลือดโกลาหลเลย)
            m = rng.uniform(-CL.MUTATE, CL.MUTATE)
            for kk in list(blood):
                blood[kk] = max(0.0, blood[kk] + m)
        # สายเลือดไหลตามสภาวะโลกตอนเกิด (เดิม: วิญญาณ → อสูร SPIRIT_DILUTE ทุกรุ่นไม่ว่าโลกเป็นอย่างไร)
        # ขนาด = SPIRIT_DILUTE (ค่าเดิม) × ตัวคูณของสภาวะ · ทิศ = จากสายที่เสียเปรียบไปสายที่ได้เปรียบ (C.BLOOD_DRIFT)
        state = self.blood_state(w)
        srcs, dst, mult = C.BLOOD_DRIFT[state]
        lost = 0.0
        for src in srcs:
            moved = blood.get(src, 0.0) * CL.SPIRIT_DILUTE * mult
            blood[src] = blood.get(src, 0.0) - moved
            lost += moved
        if lost > 0:
            blood[dst] = blood.get(dst, 0.0) + lost
        child.blood = R.normalize(blood)
        # โกลาหลเป็นการติดเชื้อ ไม่ใช่สัดส่วน (ผู้ใช้ตัดสิน กฎข้อ 7): ลูกที่ได้เลือดโกลาหลจากพ่อแม่ (ลูกของทาสโกลาหล) เป็นโกลาหลเต็มตัวตั้งแต่เกิด
        if child.blood.get("chaos", 0.0) > 0.0:
            child.blood = {"chaos": 1.0}
        # เผ่าวิญญาณตามเลือดจริงของลูก — เดิม is_spirit ค้างจากเลือดสุ่มตอน spawn ก่อนผสมจากพ่อแม่ (ปีที่ 30: ธง 97 คน ป้ายเผ่า 73 คน)
        child.is_spirit = child.blood.get("spirit", 0.0) >= C.BLOOD_RACE_AT
        # ดวงรับพรสืบจากพ่อแม่ (ค่าเฉลี่ยของคนที่มีสายนั้น · ไม่มีใครมี = จุดกึ่งกลาง) — เดิมสุ่มใหม่ทุกคนเกิด
        # ไม่มีอะไรคงอยู่ข้ามรุ่น (test_world_coherence 4.4) · ไม่ทอยเลขเลย (ลดการสุ่ม ผู้ใช้อนุมัติ)
        mid = (C.BLOODLINE_AFFINITY_MIN + C.BLOODLINE_AFFINITY_MAX) / 2
        child.bloodline_affinity = {}
        for line, share in child.blood.items():
            if share <= 0.0:
                continue
            got = [p.bloodline_affinity[line] for p in (a, t) if line in (p.bloodline_affinity or {})]
            child.bloodline_affinity[line] = round(sum(got) / len(got) if got else mid, 4)
        child.bloodline_grants = {}
        self.apply_bloodline_buff(child)
        child.parents = [a.cid, t.cid]
        # ธาตุสืบสาย — ต้องตั้งตรงนี้ ไม่ใช่ใน spawn() เพราะตอน spawn ยังไม่รู้ว่าใครเป็นพ่อแม่
        # (วัดจริงตอนตั้งไว้ใน spawn: ลูกได้ธาตุตรงกับพ่อแม่ 22% = เท่ากับสุ่มล้วนพอดี)
        EL.roll(child, rng, (a, t))
        d["ธาตุของทายาท"] = f"{child.element} ({EL.relation_words(a.element, t.element)})"
        child.generation = max(a.generation, t.generation) + 1
        child.clan = a.clan if a.clan >= 0 else t.clan
        child.place = mother.place              # เกิดที่ที่แม่อยู่ตอนคลอด
        child.origin = "ทายาทตระกูล" if child.clan >= 0 else "ชาวบ้าน"
        if child.clan >= 0:
            child.name = self.unique_name(
                CL.CLANS[child.clan][0].replace("ตระกูล", "") + rng.choice(E.GIVEN), old=child.name)
        a.children.append(child.cid)
        t.children.append(child.cid)
        a.bonds[t.cid] = a.bonds.get(t.cid, 0) + 2
        d["ทายาท"] = f"{child.name} — {child.race()} รุ่นที่ {child.generation}"
        if lost > 0.01:
            d["สายเลือดเจือจาง"] = (f"{state}: เลือด{'/'.join(C.BLOOD_TH[s] for s in srcs)}ลดลง "
                                    f"{lost*100:.0f}% กลายเป็นเลือด{C.BLOOD_TH[dst]}")
        clan = CL.CLANS[child.clan][0] if child.clan >= 0 else "ไร้ตระกูล"
        d["child_id"] = child.cid
        if C.GUARDIANS_ENABLED:
            GUARD.at_birth(self, child, mother, father)
        if getattr(mother, "place", -1) != getattr(father, "place", -2):
            # คลอดหลังปฏิสนธิหลายเดือน พ่ออาจเดินทางไปที่อื่นแล้ว (ยิ่งเมื่อระยะทางเป็นของจริง การเดินทางกินเวลาเป็นปี)
            # เหตุการณ์นี้ไม่ผ่าน resolve() จึงไม่มีใครบันทึกว่าทำไมคู่นี้เอื้อมถึงกันข้ามระยะ — test_locality นับเป็น
            # "ไม่มีเหตุผลรองรับ" 21 จาก 30 ครั้ง ทั้งที่เหตุผลชัดที่สุดในโลก: เขาเป็นพ่อของเด็ก
            d[C.PRIOR_TIE_KEY] = "เป็นพ่อของทารกที่เพิ่งเกิด"
        self.emit(w, "กำเนิดทายาท", mother, father, ["คน", "เลือด"], "กำเนิด",
                  f"{a.name}กับ{t.name}ให้กำเนิด{child.name}แห่ง{clan}", 0, d)
        return child

    def begin_cultivation(self, ch, days, rate=1.0):
        """บำเพ็ญจากวันนี้ไปจนถึงเทิร์นถัดไป (`days` คือช่วงที่ _next_turn นัดไว้) ผลคิดตามวันที่ได้บำเพ็ญจริง
        ตอนเทิร์นถัดไปหรือตอนถูกขัดจังหวะ — `rate` คูณวันที่นับ (อสูรในแดนสูง)
        ระหว่างเดินทางหรือปิดด่านอยู่แล้ว (เช่นชนะโจรกลางทาง) ได้ผลทันทีแบบเดิม ไม่ทับกิจกรรมที่ทำอยู่"""
        if ch.process is not None and ch.process.kind != "cultivation":
            R.cultivate(ch, days * rate, self.items)
            return None
        if CHILD.teaching(self, ch):
            rate *= C.GUARDIAN_TEACH_COST        # เวลาที่ใช้สอนเด็กในความดูแล (childhood.py) ไม่ได้ใช้บำเพ็ญ
        return self.start_process(ch, "cultivation", days, None, rate)

    def settle_routine(self, ch):
        """ปิดกิจวัตรที่จ่ายผลตามวันและค้างอยู่ (บำเพ็ญ หรือกิจวัตรวัยเด็ก) ได้ผลถึงวันนี้ ไม่เกินกำหนด"""
        if ch.process is not None and ch.process.kind in ("cultivation", "upbringing"):
            self.accrue_process(ch)
            ch.process = None

    def check_processes(self):
        """ทุกรอบของโลก: คนที่หมดสติหยุดทุกกิจกรรม คนที่ยืนไม่ได้หยุดเดินทาง (ยังนั่งบำเพ็ญในด่านต่อได้)"""
        for cid in self.alive_sorted():
            ch = self.cast[cid]
            if ch.pregnancy is not None:
                if ch.pregnancy.end_day <= self.day:
                    self.deliver(ch)
                elif not BODY.can_fight(ch):
                    self.end_pregnancy(ch, "บาดเจ็บสาหัส")
                elif ch.hunger_days >= C.PREGNANCY_STARVE_DAYS:
                    self.end_pregnancy(ch, "อดอาหาร")
            p = ch.process
            if p is None or p.end_day <= self.day:
                continue
            why = CHILD.broken(self, ch, p) if p.kind == "upbringing" else None
            if why:
                self.interrupt_process(ch, why)
            elif not BODY.conscious(ch):
                self.interrupt_process(ch, "หมดสติ")
            elif p.kind == "travel" and not BODY.can_stand(ch):
                self.interrupt_process(ch, "บาดเจ็บจนเดินต่อไม่ได้")

    def fade_grudges(self, days):
        """ความแค้นจางลง GRUDGE_FADE_PER_YEAR ต่อปี จางหมดแล้วลบทิ้ง แค้นคนที่ตายไปแล้วลบทิ้งเลย

        ใครอยู่ใน `rivals` คือคู่แค้น (ใช้เลือกเป้าทั่วเอนจิน) และถือแค้นอยู่เรื่องเดียวก็ดันให้อยากล้างแค้นแล้ว
        แค้นที่ไม่เคยหายจึงเป็นวงจรไม่รู้จบ แค้นคนตายชำระไม่ได้ ผลเดียวของมันคือการล้างแค้นที่ไปตกกับคนข้างตัว
        (เซฟจริงปีที่ 1,228: 54% ของความแค้นเป็นแค้นคนตาย 468 คนถือแต่แค้นคนตาย)
        """
        fade = C.GRUDGE_FADE_PER_YEAR * days / 365.0
        for cid in self.alive_cids:
            rivals = self.cast[cid].rivals
            for foe, level in list(rivals.items()):
                if level <= fade or not (0 <= foe < len(self.cast)) or not self.cast[foe].alive:
                    del rivals[foe]
                else:
                    rivals[foe] = level - fade
