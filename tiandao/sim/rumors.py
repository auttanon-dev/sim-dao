# -*- coding: utf-8 -*-
"""Sim — ข่าวลือ"""
from ._common import *  # noqa: F401,F403
from ._common import _REACH_CACHE, _PLACE_SETS, _CENTERS, _reach_from, _auction_q  # noqa: F401


class RumorMixin:
    # ------------------------------------------------------------ ข่าวลือ
    def spawn_rumor(self, world, rng):
        """ข่าวลือเกิดขึ้นเอง — แดนลับที่ยังไม่มีใครเจอ, ของวิเศษที่มีคนเห็น,
        หรือแหล่งวัตถุดิบที่ขาดแคลน/กลับมาอุดมสมบูรณ์ (เชื่อมกับระบบนิเวศ)"""
        pool = []
        for c in self.caches:
            if c.world_id == world.wid and not c.opened:
                pool.append(("แดนลับ", c.kid, c.owner_name))
        for iid in self.legend_iids:
            it = self.items.get(iid)
            if it:
                pool.append(("สมบัติ", iid, it.name))
        for key in sorted({k[:2] for k in self.place_stock}):
            if key[0] != world.wid:
                continue
            p = PL.PLACES[key[1]]
            if self.eco_scarce.get(key):                 # หัวข้อข่าวลือเป็นเลขสถานที่ (rumor_leads) — แดนคือแดนของข่าวนี้
                pool.append(("ขาดแคลน", key[1], p[0]))
            elif key in self.eco_recovered:
                pool.append(("อุดมสมบูรณ์", key[1], p[0]))
        for f in self.skill_fragments:
            if f["found"] or PL.PLACES[f["place"]][1] != world.place_key:
                continue
            pool.append(("ชิ้นส่วนวิชา", f["fid"], f["skill"]))
        if not pool:
            return
        kind, subject, label = rng.choice(pool)
        if kind == "ขาดแคลน":
            place = subject
            text = f"มีคนบ่นว่า{label}เริ่มหาของกินของใช้ยากขึ้นมากในระยะหลัง"
        elif kind == "อุดมสมบูรณ์":
            place = subject
            self.eco_recovered.discard((world.wid, subject))   # ข่าวฟื้นตัวเป็นข่าวครั้งเดียว ไม่ใช่สถานะค้าง
            text = f"มีคนเล่าว่า{label}กลับมาอุดมสมบูรณ์อีกครั้งหลังจากเงียบไปพักใหญ่"
        elif kind == "ชิ้นส่วนวิชา":
            frag = next(f for f in self.skill_fragments if f["fid"] == subject)
            place = frag["place"]
            place_name = PL.PLACES[place][0]
            text = f"มีคนเล่าลือว่าเคยขุดเจอเศษจารึกวิชาโบราณชิ้นหนึ่งใกล้{place_name} คาดว่าเป็นส่วนหนึ่งของ「{label}」"
        else:
            pl = PL.places_in(world.place_key)
            place = rng.choice(pl) if pl else -1
            place_name = PL.PLACES[place][0] if place >= 0 else "ที่ใดสักแห่ง"
            if kind == "แดนลับ":
                text = f"มีคนเล่าลือว่าเคยเห็นแสงประหลาดใกล้{place_name} คาดว่าเป็นแดนลับของ{label}"
            else:
                text = f"ข่าวลือแพร่สะพัดว่า「{label}」ปรากฏตัวแถว{place_name}"
        self.rumors.append({
            "id": self.nid("r"), "kind": kind, "subject": subject, "world_id": world.wid,
            "place": place, "text": text, "day": self.day,
            "true": rng.random() > C.RUMOR_FALSE_P, "heard": set(),
        })
        self.trim_rumors()

    def trim_rumors(self):
        """ข่าวลือค้างได้ RUMOR_MAX_ACTIVE เรื่อง ทิ้งเรื่องเก่าที่สุดก่อน — ยกเว้นตำนานยุคก่อน ซึ่งเล่าต่อกันไปทุกยุค
        ไม่นับในเพดานและไม่ถูกทิ้ง (เดิมตำนานเป็นข่าวที่เก่าที่สุดในโลกเสมอ จึงถูกดันออกราวปีที่ 2)"""
        extra = sum(1 for r in self.rumors if r["kind"] != "ตำนาน") - C.RUMOR_MAX_ACTIVE
        if extra <= 0:
            return
        kept = []
        for r in self.rumors:
            if extra > 0 and r["kind"] != "ตำนาน":
                extra -= 1
                continue
            kept.append(r)
        self.rumors[:] = kept

    def seed_ancient_rumors(self):
        """ข่าวลือตำนานยุคก่อน RUMOR_ANCIENT_LEGENDS เรื่องในโลกมนุษย์ — จำนวนและผลต่อโลกเท่ากันทุกรัน

        ตำนานจากรันก่อนหน้า (tiandao/chronicle.json) เป็นแค่ถ้อยคำของเรื่องเล่า เลือกด้วยสายสุ่มของงานเล่าเรื่อง
        ที่ได้จาก seed (decision.rng.rng_for) ไม่ใช่ self.rng ไม่มีไฟล์ก็ใช้ถ้อยคำกลาง การได้ยินตำนานไม่ให้เบาะแส
        และอารมณ์ตอบสนองตามชนิดเหตุการณ์ไม่ใช่ถ้อยคำ ถ้อยคำจึงไม่เปลี่ยนโลก (แบบ §12.4)
        เดิมใช้ self.rng.sample ตามจำนวนตำนานในไฟล์ (ไม่มีไฟล์ = ไม่มีข่าวลือ) seed เดียวกันจึงได้โลกต่างกันตามไฟล์ที่
        git ไม่เก็บ และ run.py เขียนไฟล์นี้ใหม่ทุกครั้งที่จบ รันถัดไปด้วย seed เดิมจึงได้โลกคนละใบ
        """
        from ..decision import rng as DRNG
        legends = CH.all_legends(limit=8)
        story_rng = DRNG.rng_for("ancient-legends", str(self.seed))
        told = story_rng.sample(legends, min(C.RUMOR_ANCIENT_LEGENDS, len(legends)))
        for i in range(C.RUMOR_ANCIENT_LEGENDS):
            if i < len(told):
                lg = told[i]
                subject = lg["name"]
                text = (f"คนแก่เล่าตำนานยุคก่อนถึง [{lg['name']}] {lg['race']}สาย{lg['dao']} "
                        f"ผู้ไปถึง{lg['peak_realm']} เมื่อหลายชั่วอายุคนก่อน ({lg['status']})")
            else:
                subject = "ยอดฝีมือไร้นาม"
                text = "คนแก่เล่าตำนานยุคก่อนถึงยอดฝีมือไร้นามผู้บำเพ็ญจนหายไปจากโลกเมื่อหลายชั่วอายุคนก่อน"
            self.rumors.append({
                "id": self.nid("r"), "kind": "ตำนาน", "subject": subject,
                "world_id": self.worlds[0].wid, "place": -1, "text": text,
                "day": 0, "true": True, "heard": set(),
            })

    def try_hear_rumor(self, actor, world, rng):
        pool_wid = world.wid
        cross = False
        border = getattr(self, "border_pairs", {}).get(world.wid)
        if border is not None and rng.random() < C.RUMOR_CROSS_BORDER_P:
            pool_wid, cross = border, True
        active = [r for r in self.rumors if r["world_id"] == pool_wid and actor.cid not in r["heard"]]
        if not active:
            return
        # ข่าวเดินทางบนกราฟสถานที่ ไม่ใช่โผล่พร้อมกันทั้งแดน (ดู physics.spread_reach)
        # โลกนี้ไม่มีพิกัด มันเป็นกราฟของสถานที่ที่เชื่อมกันด้วยเส้นทาง ระยะที่มีความหมายจริง
        # จึงเป็น "จำนวนก้าวที่ต้องเดินทาง" กฎกำลังสองผกผันใช้ไม่ได้เพราะไม่มีปริมาตรให้กระจาย
        # แต่การลดทอนต่อก้าวใช้ได้ตรงไปตรงมา ผลคือวีรกรรมในหุบเขาห่างไกลใช้เวลากว่าจะถึง
        # เมืองหลวง และเมืองที่เป็นชุมทางกลายเป็นศูนย์กลางข่าวสารเองโดยไม่ต้องประกาศ
        if not cross and actor.place is not None and actor.place >= 0:
            reach = []
            for r in active:
                src = r.get("place", -1)
                if src is None or src < 0:
                    reach.append(r)                  # ตำนานเก่าแก่ ไม่ผูกกับที่ไหน
                    continue
                hops = self.hops_between(actor.place, src)
                aged = (self.day - r.get("day", self.day)) / max(1.0, C.RUMOR_TRAVEL_DAYS)
                # ข่าวเก่าเดินทางไปได้ไกลกว่าข่าวใหม่ — เวลาเป็นตัวพาข่าว
                if rng.random() < PHYS.spread_reach(max(0, hops - int(aged)),
                                                    C.RUMOR_STEP_KEEP):
                    reach.append(r)
            if reach:
                active = reach
        pv = self.place_of(actor)
        p = C.RUMOR_HEAR_P
        if pv and pv[3] in ("ตลาด", "เมือง"):
            p *= C.RUMOR_HEAR_MARKET_MULT
        if rng.random() >= p:
            return
        r = rng.choice(active)
        r["heard"].add(actor.cid)
        if r["kind"] != "ตำนาน":
            leads = [l for l in actor.rumor_leads if l["kind"] != r["kind"] or l["subject"] != r["subject"]]
            leads.append({"kind": r["kind"], "subject": r["subject"], "true": r["true"]})
            actor.rumor_leads = leads[-C.RUMOR_LEAD_MAX:]
        source = "พ่อค้าเร่ร่อนข้ามพรมแดนเล่าว่า" if cross else "ได้ยินข่าวลือ:"
        self.emit(world, "ได้ยินข่าวลือ", actor, None, ["ข่าวลือ"], "ได้ยินมา",
                  f"{actor.name}{source} {r['text']}", 0, {})
