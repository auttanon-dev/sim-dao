# -*- coding: utf-8 -*-
"""Sim — วัฏจักรเวียนว่าย"""
from ._common import *  # noqa: F401,F403
from ._common import _REACH_CACHE, _PLACE_SETS, _CENTERS, _reach_from, _auction_q  # noqa: F401


class CycleMixin:
    # ------------------------------------------------------------ วัฏจักรเวียนว่าย
    CYCLE_LINE = "วัฏจักร"

    def _knows_cycle(self, ch) -> bool:
        """มีวาสนาสายวัฏจักรไหม — ฝึกวิชาสายนี้อยู่ หรือเกิดใหม่มาจากผู้ฝึกสายนี้"""
        if getattr(ch, "cycle_born", False):
            return True
        for n in ch.skills:
            sk = R.SKILL_INDEX.get(n)
            if sk and sk[1] == self.CYCLE_LINE:
                return True
        return False

    def reincarnate(self, ch):
        """ผู้ฝึกสายวัฏจักรตายแล้วไปเกิดใหม่ — ร่างเดิมตายจริง แต่ดวงจิตไม่สลายไปกับมัน

        ทำไมถึงไม่ "ยกเลิกการตาย": ตัวละครเดิมต้องตายให้ครบกระบวนการจริง (คืนพลังให้ฟ้า ทิ้งแดนลับ
        ญาติตามล้าง สมบัติตกทอด) ไม่งั้นความตายของสายนี้จะไม่มีราคาอะไรเลย สิ่งที่ข้ามภพไปคือดวงจิต
        ซึ่งเกิดเป็นตัวละครใหม่ที่ยังจำอะไรไม่ได้ — จนกว่าจะบำเพ็ญถึงขั้นสูงพอ (REBIRTH_WAKE_REALM)

        ชาติใหม่ได้ **เคล็ดสายวัฏจักรเกรดต่ำติดตัวมาแต่เกิด** ตามกฎที่เจ้าของโลกตั้งไว้ว่า "พอไปเกิด
        ใหม่ก็จะมีความสามารถที่จะฝึกสายวัฏจักรได้อยู่แล้ว" — ถ้าไม่ให้ตรงนี้ วงจรจะขาดทันทีในชาติที่
        สอง เพราะวิชาสายวัฏจักรทั้งหมดอยู่ tier 1 ซึ่งคนเกิดใหม่ในโลกมนุษย์เรียนเองไม่ได้เลย
        """
        if getattr(ch, "rebirth_count", 0) >= C.REBIRTH_MAX:
            return None
        rng = self.rng
        # เกรด 2 ของสายนี้ = "กำหนดที่เกิดของชาติหน้าได้เอง" ที่เหลือเกิดที่ไหนก็ได้ในโลกล่าง
        pick_own = any(R.SKILL_INDEX.get(n, (None, None, None, -1))[3] >= 2
                       and R.SKILL_INDEX.get(n, (None, None))[1] == self.CYCLE_LINE
                       for n in ch.skills)
        if pick_own:
            dest = self.world(ch.world_id)
        else:
            pool = [w for w in self.worlds if w.kind == "mortal" and w.n_alive > 0]
            dest = rng.choice(pool) if pool else self.worlds[0]
        baby = self.spawn(dest, age_years=0)
        baby.cycle_born = True
        baby.rebirth_count = getattr(ch, "rebirth_count", 0) + 1
        baby.past_life = ch.cid
        baby.past_name = ch.name
        baby.past_dao = ch.dao
        baby.past_realm = ch.realm
        baby.past_skills = list(ch.skills)
        baby.memory_woken = False
        baby.fate = min(C.FATE_MAX, baby.fate + C.REBIRTH_FATE_BONUS)
        seed = next((s[0] for s in SK.SKILLS
                     if s[1] == self.CYCLE_LINE and s[3] == 0), None)
        if seed:
            baby.learn_skill(seed)
        self.emit(dest, "จุติคืนสังสารวัฏ", baby, None, ["ความตาย"], "เกิดใหม่",
                  f"ดวงจิตของ{ch.name}ไม่สลายไปกับร่าง หวนคืนสู่วงเวียนเกิดดับ "
                  f"แล้วจุติใหม่ที่{dest.name}ในนาม{baby.name}", 0,
                  {"ชาติก่อน": f"{ch.name} ({ch.realm_name()})",
                   "เวียนว่ายมาแล้ว": f"{baby.rebirth_count} ชาติ",
                   "ที่เกิด": "เลือกเองด้วยมหาอาคมจุติคืนสังสารวัฏ" if pick_own else "แล้วแต่วาสนา",
                   "ความทรงจำ": f"ถูกผนึกไว้จนกว่าจะบำเพ็ญถึงขั้น {C.REBIRTH_WAKE_REALM}"})
        return baby

    def wake_past_life(self, ch):
        """ตื่นความทรงจำชาติก่อน — เกิดเมื่อผู้เกิดใหม่บำเพ็ญถึงขั้นสูงพอ

        ได้วิชาเดิมกลับมาบางส่วน (REBIRTH_SKILL_KEEP) ไม่ใช่ทั้งหมด — ความทรงจำที่ข้ามภพมาได้คือ
        สิ่งที่ฝังลึกถึงระดับดวงจิต ไม่ใช่ทุกอย่างที่เคยรู้ และได้วิถีเดิมคืนมาด้วย
        """
        ch.memory_woken = True
        old = [n for n in getattr(ch, "past_skills", []) if n not in ch.skills]
        keep = int(len(old) * C.REBIRTH_SKILL_KEEP)
        got = self.rng.sample(old, keep) if keep else []
        for _name in got:
            # วิชาที่ระลึกได้คือวิชาที่เคยฝึกมาทั้งชาติก่อน ไม่ใช่ของที่เพิ่งเห็นครั้งแรก
            ch.learn_skill(_name)
        prev_dao = ch.dao
        if getattr(ch, "past_dao", None):
            ch.dao = ch.past_dao
            ch.dao_tags = list(C.DAO_POOL.get(ch.dao, ch.dao_tags))
        self.emit(self.world(ch.world_id), "ตื่นความทรงจำชาติก่อน", ch, None,
                  ["หลอมรวม"], "ระลึกชาติ",
                  f"{ch.name}บำเพ็ญถึงขั้นที่ดวงจิตทานรับความทรงจำเดิมไหว "
                  f"ภาพชาติก่อนในนาม{getattr(ch, 'past_name', '?')}หลั่งไหลกลับมาทั้งหมด", 0,
                  {"ชาติก่อน": f"{getattr(ch,'past_name','?')} เคยถึงขั้น {getattr(ch,'past_realm',0)}",
                   "เวียนว่ายมาแล้ว": f"{getattr(ch,'rebirth_count',0)} ชาติ",
                   "วิชาที่ระลึกได้": " · ".join(got) if got else "ไม่มีเลย จำได้แต่ใบหน้าคน",
                   "วิถีที่คืนมา": f"{prev_dao} -> {ch.dao}"})

    def org_avenge(self, victim, killer):
        if victim.org is None:
            return
        org = self.orgs[victim.org]
        if not org.alive or killer.org == victim.org:
            return
        if killer.org is not None:
            org.grudges[killer.org] = org.grudges.get(killer.org, 0) + C.GRUDGE_PER_KILL

    def prune_departed(self):
        """คนที่ตายเกิน PRUNE_DEAD_YEARS ปีกลายเป็นบันทึกย่อ (models.Departed) ที่ cid เดิม — ปีละครั้งจากนาฬิกาโลก

        เว้นคนที่ยังมีลูกอายุไม่ถึง 14 ปีหรือเด็กในความดูแลที่ยังมีชีวิต ทองที่ติดตัวผู้ตายไม่มีใครรับช่วงอยู่แล้ว
        ย้ายไปนับไว้ที่ buried_gold ยอดทองรวม (wages.total_gold) จึงไม่เปลี่ยน ส่วนเสบียงของผู้ตายเข้ายุ้งฉางไปตั้งแต่ตาย
        """
        cutoff = self.day - C.PRUNE_DEAD_YEARS * 365
        cast = self.cast
        buried = self.__dict__.setdefault("buried_gold", {})
        pruned = 0
        for i, ch in enumerate(cast):
            if ch.alive or type(ch) is Departed or ch.death_day is None or ch.death_day > cutoff:
                continue
            if any(0 <= c < len(cast) and cast[c].alive and (cast[c].age(self.day) < 14 or c in ch.wards)
                   for c in list(ch.children) + list(ch.wards)):
                continue
            for tier, gold in ch.money.items():
                if gold:
                    buried[tier] = buried.get(tier, 0.0) + gold
            cast[i] = Departed(ch)
            pruned += 1
        if pruned and getattr(self, "deaths", None):      # บันทึกความตายย่อไปพร้อมกับผู้ตาย — เซฟไม่โตไม่จำกัด
            gone = {i for i, c in enumerate(cast) if type(c) is Departed}
            self.deaths = [d for d in self.deaths if d.cid not in gone]
        self.pruned_total = getattr(self, "pruned_total", 0) + pruned
        return pruned
