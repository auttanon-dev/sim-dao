# -*- coding: utf-8 -*-
import heapq
import random

from . import config as C
from . import events as E
from . import rules as R
from .models import Cache, Character, Event, Item, Org, World
from .treasures import TREASURES, BURST_MULT
from . import skills as SK
from . import crafting as CR
from . import places as PL
from . import clans as CL
from . import intent as IN
from . import travel as TR
from . import chronicle as CH
from . import seasons as SEASONS
from .ai import BrainManager, EventBus


class Sim:
    def __init__(self, seed=0, tiers=3):
        self.rng = random.Random(seed)
        self.seed = seed
        self.day = 0
        self.last_day = 0
        self.seq = 0
        self.cast = []
        self.items = {}
        self.caches = []
        self.ruined = {}          # place_idx -> วันที่ฟื้นคืน
        self.orgs = []
        self.log = []
        self.bounties = {} # cid -> reward amount
        self.queue = []
        self.rumors = []
        self.place_stock = {}     # place_idx -> ปริมาณทรัพยากร/สัตว์อสูรที่เหลืออยู่ตอนนี้ (ระบบนิเวศ)
        self.eco_scarce = {}      # place_idx -> True ขณะที่ยังอยู่ในสถานะขาดแคลน (ค้างจนกว่าจะฟื้นจริง)
        self.eco_recovered = set()  # place_idx ที่เพิ่งฟื้นจากขาดแคลน — ใช้เป็นข่าวลือครั้งเดียวแล้วเคลียร์ทิ้ง
        self.skill_fragments = []   # ชิ้นส่วนวิชาแก้ทางโกลาหลที่ฝังกระจายไว้ทั่วโลกมนุษย์
        self.next_id = {"c": 0, "i": 0, "k": 0, "o": 0, "r": 0, "f": 0}

        # Cultivator Brain v2 (ai/) — Event Bus + CharacterBrain skeleton, ดู tiandao/ai/__init__.py
        self.event_bus = EventBus()
        self.brain_manager = BrainManager()
        self.event_bus.subscribe(self.brain_manager.on_event)

        # มหาผนึกสะกดหมื่นมาร (แดนลับรอยแยกเชื่อมโลกมนุษย์-แดนมาร)
        self.mara_seal = getattr(C, "MARA_SEAL_INITIAL", 100.0)
        self.mara_seal_broken = False
        self.mara_seal_notified_weak = False

        # สร้างโลก: บันไดระดับ + แดนมารอยู่ข้างๆ ชั้นล่างสุด
        self.worlds = []
        for t in range(tiers):
            self.worlds.append(World(wid=t, name=C.TIER_NAMES[t], tier=t))
        for t in range(tiers - 1):
            self.worlds[t].up = t + 1
        for t in range(tiers):
            self.worlds[t].place_key = t
        mara = World(wid=len(self.worlds), name=C.MARA_WORLD_NAME, tier=0, kind="mara")
        mara.place_key = "mara"
        self.worlds.append(mara)
        self.worlds[0].lateral.append(mara.wid)
        mara.lateral.append(0)
        self.chaos_wid = None
        top = min(C.CHAOS_TIER, tiers - 1)
        chaos = World(wid=len(self.worlds), name=C.CHAOS_WORLD_NAME, tier=top, kind="chaos")
        chaos.place_key = 2
        self.worlds.append(chaos)
        self.chaos_wid = chaos.wid
        self.worlds[top].lateral.append(chaos.wid)
        chaos.lateral.append(top)

        # อาณาจักรวัฒนธรรมเพื่อนบ้านของโลกมนุษย์ (5 ดินแดนวัฒนธรรม)
        sister_realms = [
            ("siam", C.SIAM_WORLD_NAME),
            ("fusang", getattr(C, "FUSANG_WORLD_NAME", "แดนอาทิตย์อุทัย")),
            ("steppe", getattr(C, "STEPPE_WORLD_NAME", "แดนทุ่งหญ้าคีตาวายุ")),
            ("oasis", getattr(C, "OASIS_WORLD_NAME", "แดนโอเอซิสพันราตรี")),
            ("bharata", getattr(C, "BHARATA_WORLD_NAME", "แดนชมพูทวีป")),
        ]
        self.sister_wids = {}
        self.border_pairs = {}
        for pkey, wname in sister_realms:
            sw = World(wid=len(self.worlds), name=wname, tier=0, kind="mortal")
            sw.place_key = pkey
            if tiers > 1:
                sw.up = self.worlds[1].wid   # ผู้บำเพ็ญข้ามฟ้าขึ้นแดนเซียนได้เช่นกัน
            self.worlds.append(sw)
            self.sister_wids[pkey] = sw.wid
            self.border_pairs[sw.wid] = self.worlds[0].wid
            self.border_pairs[self.worlds[0].wid] = sw.wid
        self.siam_wid = self.sister_wids["siam"]

        for w in self.worlds:
            if w.kind == "chaos":
                continue
            n = C.CAST_SIZE if w.kind == "mortal" else C.CAST_SIZE // 3
            for _ in range(n):
                self.spawn(w, age_years=self.rng.randint(8, 45))
        self.spawn_chaos_race()
        self.seed_treasures()
        self.legend_iids = [iid for iid, it in self.items.items() if it.legend]
        self.seed_ancient_rumors()
        self.seed_skill_fragments()

    def spawn_chaos_race(self):
        """เผ่าโกลาหล — ผู้นำมีคนเดียว ที่เหลือลดหลั่นลงมา"""
        w = self.world(self.chaos_wid)
        for i in range(C.CHAOS_POP):
            ch = self.spawn(w, age_years=self.rng.randint(200, 3000))
            ch.chaos_rank = max(0, min(len(C.CHAOS_RANKS) - 1,
                                       int(abs(self.rng.gauss(0, 1.3)))))
            ch.blood = {"chaos": 1.0}
            ch.inner_none = True
            ch.realm = C.REALM_CAP
        lord = max(self.living_in(w.wid), key=lambda c: c.chaos_rank)
        lord.is_lord = True
        lord.chaos_rank = len(C.CHAOS_RANKS) - 1
        self.lord_cid = lord.cid

    def crown_new_lord(self):
        """เจ้าโกลาหลตาย ผู้แข็งแกร่งที่สุดที่เหลือขึ้นแทนทันที"""
        pool = self.living_in(self.chaos_wid)
        if not pool:
            return None
        n = max(pool, key=lambda c: (c.chaos_rank, R.power(c, self.world(c.world_id))))
        n.is_lord = True
        n.chaos_rank = len(C.CHAOS_RANKS) - 1
        self.lord_cid = n.cid
        return n

    def seed_treasures(self):
        """ยุคแรกเริ่มมีสมบัติมากมาย — 24 ชิ้นเอกถูกโปรยไว้ในโลกตั้งแต่ต้น"""
        rng = self.rng
        maxt = max(w.tier for w in self.worlds)
        for name, kind, desc, grade, cd, tier in TREASURES:
            t = min(tier, maxt)
            homes = [w for w in self.worlds if w.tier == t and w.kind == "mortal"]
            w = rng.choice(homes) if homes else self.worlds[0]
            it = Item(iid=self.nid("i"), kind="สมบัติฟ้าดิน", tier=t, grade=grade,
                      name=name, legend=True, power_desc=desc, cooldown=cd * 1)
            self.items[it.iid] = it
            pool = self.living_in(w.wid)
            if pool and rng.random() < 0.45:      # บางชิ้นอยู่ในมือคน
                rng.choice(pool).items.append(it.iid)
            else:                                  # ที่เหลือนอนอยู่ในแดนลับรอผู้มีวาสนา
                k = Cache(kid=self.nid("k"), world_id=w.wid, owner=-1,
                          owner_name="ผู้วางฟ้าดิน", sealed_day=0,
                          seal=C.SEAL_BASE * rng.uniform(0.2, 2.5), items=[it.iid],
                          currency=rng.uniform(0, 50), era_sealed=0)
                self.caches.append(k)

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

    def nid(self, k):
        self.next_id[k] += 1
        return self.next_id[k] - 1

    def world(self, wid):
        return self.worlds[wid]

    def living(self):
        return [c for c in self.cast if c.alive]

    def living_in(self, wid):
        return [c for c in self.cast if c.alive and c.world_id == wid and c.sentient]

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
        gender = rng.choice(["ชาย", "หญิง"]) if blood.get("demon", 0) < 0.8 else rng.choice(["ชาย", "หญิง", "ไม่มีเพศ"])
        fear = round(rng.uniform(0.1, 0.9), 2)
        greed = round(rng.uniform(0.1, 0.9), 2)
        compassion = round(rng.uniform(0.1, 0.9), 2)
        
        # City (only applicable for tier 1)
        city_id = -1
        if world.tier == 1 and hasattr(C, "CITIES") and C.CITIES:
            city = rng.choice(C.CITIES)
            city_id = city["id"]
        ch = Character(
            cid=self.nid("c"),
            name=name,
            world_id=world.wid, dao=dao, dao_tags=list(C.DAO_POOL[dao]),
            born_day=self.day - age_years * 365, blood=blood,
            fate=rng.randint(C.FATE_MIN, C.FATE_MAX), origin=origin,
            gender=gender, fear=fear, greed=greed, compassion=compassion,
            tribe=tribe, city_id=city_id
        )
        ch.traits = IN.pick_traits(rng)
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
        if blood.get("demon", 0) > 0.8 and age_years < 60:
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
        ch.last_day = self.day
        self.cast.append(ch)
        world.n_alive += 1
        if ch.realm == 0:
            world.n_mortal += 1
        self.schedule(ch, rng.randint(30, 900))
        return ch

    def schedule(self, ch, gap):
        heapq.heappush(self.queue, (self.day + max(1, gap), ch.cid))

    def repopulate(self, world, elapsed):
        if world.kind == "chaos":
            target = C.CHAOS_POP
            deficit = target - world.n_alive
            if deficit > 0 and self.rng.random() < 0.02:
                ch = self.spawn(world, self.rng.randint(100, 800))
                ch.chaos_rank = 0
                ch.blood = {"chaos": 1.0}
                ch.inner_none = True
                ch.realm = C.REALM_CAP
            return
        target = C.CAST_SIZE if world.kind == "mortal" else C.CAST_SIZE // 3
        deficit = target - world.n_alive
        if deficit <= 0 or elapsed <= 0:
            return
        exp = deficit * (elapsed / 365.0) * C.REPOP_RATE
        n = int(exp) + (1 if self.rng.random() < exp % 1.0 else 0)
        for _ in range(min(n, deficit)):
            self.spawn(world, self.rng.randint(0, 14))

    # ------------------------------------------------------------ ตาย
    def kill(self, ch, cause, killer=None, natural=False):
        if not ch.alive:
            return
        ch.alive = False
        ch.death_day = self.day
        ch.death_cause = cause
        if ch.is_lord:
            # เจ้าโกลาหลไม่มีวันตาย แค่สลายไปจนพลังฟื้น แล้วกลับมาแข็งแกร่งขึ้น
            ch.alive = True
            ch.death_day = None
            ch.death_cause = ""
            ch.hidden = True
            ch.decay = 0.0
            ch.lord_returns += 1
            ch.return_day = self.day + self.rng.randint(*C.LORD_RETURN_DAYS)
            self.schedule(ch, ch.return_day - self.day)
            return
        w = self.world(ch.world_id)
        w.n_alive -= 1
        if ch.realm == 0:
            w.n_mortal -= 1
        R.death_return(w, ch, natural)
        if killer:
            killer.kills += 1
            if ch.is_unique_beast:
                killer.cores += 10
                killer.mats += 5
            if not ch.hated():        # ฆ่ามนุษย์มารถือเป็นการชอบธรรม ไม่เกิดหนี้ค้างคา
                R.add_debt(killer, "ฆ่า", ch.cid, ch.name, self.day)
            for iid in ch.items:                      # ของตกอยู่กับคนฆ่า
                killer.items.append(iid)
            ch.items = []
            self.org_avenge(ch, killer)
            if ch.clan >= 0 and killer.clan != ch.clan:
                for m in self.cast:
                    if m.alive and m.clan == ch.clan:
                        m.rivals[killer.cid] = m.rivals.get(killer.cid, 0) + 2
        elif ch.realm >= C.CACHE_MIN_REALM or any(
                self.items[i].legend for i in ch.items):
            # สมบัติฟ้าดินที่มีชื่อไม่มีวันสูญหาย เจ้าของตายก็ถูกผนึกรอผู้มีวาสนาคนต่อไป
            self.make_cache(ch, faked=False)

    def org_avenge(self, victim, killer):
        if victim.org is None:
            return
        org = self.orgs[victim.org]
        if not org.alive or killer.org == victim.org:
            return
        if killer.org is not None:
            org.grudges[killer.org] = org.grudges.get(killer.org, 0) + C.GRUDGE_PER_KILL
        for cid in org.members:
            m = self.cast[cid]
            if m.alive and self.rng.random() < C.ORG_AVENGE_P:
                m.rivals[killer.cid] = m.rivals.get(killer.cid, 0) + 3

    # ------------------------------------------------------------ ของ / แดนลับ
    def make_item(self, kind, tier, grade, maker=None):
        it = Item(iid=self.nid("i"), kind=kind, tier=tier, grade=grade, maker=maker)
        it.name = f"{kind}ชั้น{min(9, int(grade * 3) + 1)}"
        self.items[it.iid] = it
        return it

    def make_cache(self, ch, faked):
        k = Cache(kid=self.nid("k"), world_id=ch.world_id, owner=ch.cid,
                  owner_name=ch.name, sealed_day=self.day,
                  seal=C.SEAL_BASE * (0.5 + 0.25 * ch.realm),
                  items=list(ch.items), currency=sum(ch.money.values()),
                  trap=faked, era_sealed=self.world(ch.world_id).era)
        ch.items = []
        self.caches.append(k)
        return k

    def open_cache(self, ch, k, rng):
        k.opened = True
        d = {}
        if k.trap and self.cast[k.owner].alive:
            owner = self.cast[k.owner]
            owner.hidden = False
            win, lose, margin = R.resolve_clash(owner, ch, self.world(ch.world_id),
                                                self.items, rng)
            res = R.apply_defeat(self, self.world(ch.world_id), win, lose, margin, rng)
            d["กับดัก"] = f"{owner.name}แกล้งตายรออยู่ — {lose.name}{res}"
            d["margin"] = round(margin, 3)
            d["winner"] = win.cid
            return d
        rot = 1.0 - min(1.0, max(0.0, -R.seal_left(k, self.day) / C.SEAL_BASE)) * C.CACHE_ROT
        got = 0
        for iid in k.items:
            it = self.items[iid]
            it.condition *= rot
            if it.condition > 0.15:
                ch.items.append(iid)
                got += 1
        tier = self.world(k.world_id).tier
        ch.money[tier] = ch.money.get(tier, 0.0) + k.currency * rot
        d["แดนลับ"] = f"มรดกของ{k.owner_name}จากยุคที่ {k.era_sealed} — ได้ของ {got} ชิ้น"
        return d

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
        for idx in self.place_stock:
            p = PL.PLACES[idx]
            if p[1] != world.place_key:
                continue
            if self.eco_scarce.get(idx):
                pool.append(("ขาดแคลน", idx, p[0]))
            elif idx in self.eco_recovered:
                pool.append(("อุดมสมบูรณ์", idx, p[0]))
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
            self.eco_recovered.discard(subject)   # ข่าวฟื้นตัวเป็นข่าวครั้งเดียว ไม่ใช่สถานะค้าง
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
        if len(self.rumors) > C.RUMOR_MAX_ACTIVE:
            self.rumors.pop(0)

    def seed_ancient_rumors(self):
        """ตำนานจากรันก่อนหน้า (tiandao/chronicle.json) แทรกเป็นข่าวลือเก่าแก่ในรันนี้"""
        legends = CH.all_legends(limit=8)
        if not legends:
            return
        for lg in self.rng.sample(legends, min(2, len(legends))):
            text = (f"คนแก่เล่าตำนานยุคก่อนถึง [{lg['name']}] {lg['race']}สาย{lg['dao']} "
                    f"ผู้ไปถึง{lg['peak_realm']} เมื่อหลายชั่วอายุคนก่อน ({lg['status']})")
            self.rumors.append({
                "id": self.nid("r"), "kind": "ตำนาน", "subject": lg["name"],
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

    # ------------------------------------------------------------ ระบบนิเวศ
    def eco_ratio(self, place_idx):
        """สัดส่วนความอุดมสมบูรณ์ของแหล่งนี้ตอนนี้ (0..1)
        ยิ่งถูกเก็บเกี่ยวหนัก ยิ่งลดลง ฟื้นเองตามเวลาที่ผ่านไป"""
        if place_idx is None or place_idx < 0:
            return 1.0
        stock = self.place_stock.get(place_idx)
        if stock is None:
            stock = C.ECO_CAP
            self.place_stock[place_idx] = stock
        return max(C.ECO_MIN_YIELD, min(1.0, stock / C.ECO_CAP))

    def eco_regen(self, elapsed_days):
        if not self.place_stock or elapsed_days <= 0:
            return
        grow = C.ECO_REGEN_PER_YEAR * SEASONS.regen_multiplier(self.day) * (elapsed_days / 365.0)
        for idx in list(self.place_stock):
            stock = min(C.ECO_CAP, self.place_stock[idx] + grow)
            self.place_stock[idx] = stock
            self._update_eco_state(idx, stock)

    def eco_harvest(self, place_idx, amount):
        if place_idx is None or place_idx < 0:
            return
        stock = max(0.0, self.place_stock.get(place_idx, C.ECO_CAP) - amount)
        self.place_stock[place_idx] = stock
        self._update_eco_state(place_idx, stock)

    def _update_eco_state(self, idx, stock):
        """สถานะขาดแคลนค้างอยู่จนกว่าจะฟื้นข้ามเกณฑ์ recover จริง — ไม่ใช่แค่กระเตื้องนิดหน่อยแล้วนับว่าอุดมสมบูรณ์"""
        ratio = stock / C.ECO_CAP
        if ratio < C.ECO_SCARCE_RATIO:
            self.eco_scarce[idx] = True
        elif self.eco_scarce.get(idx) and ratio >= C.ECO_RECOVER_RATIO:
            self.eco_scarce[idx] = False
            self.eco_recovered.add(idx)

    # ------------------------------------------------------------ ลูปหลัก
    def step(self):
        rng = self.rng
        actor = None
        
        # --- City Governance Initialization ---
        if not getattr(self, "cities_initialized", False):
            self.cities_initialized = True
            if hasattr(C, "CITIES"):
                for c in C.CITIES:
                    c_type = c.get("type_desc", "")
                    strictness = 50
                    title = "นายอำเภอ"
                    faction = "ราชสำนัก"
                    ruler_name = "หวังป๋อ"
                    realm = 3
                    
                    if "เมืองหลวง" in c_type:
                        strictness = 90
                        title = "ฮ่องเต้"
                        ruler_name = "หมิงหยวนตี้"
                        realm = 6
                    elif "ชายแดน" in c_type:
                        strictness = 80
                        title = "แม่ทัพใหญ่"
                        faction = "กองทัพทหารม้าเหล็ก"
                        ruler_name = "เฉินเฟิง"
                        realm = 5
                    elif "หน้าด่านสำนัก" in c_type:
                        strictness = 40
                        title = "ตัวแทนสำนัก"
                        faction = "พันธมิตรยุทธ"
                        ruler_name = "เย่ฟาน"
                        realm = 7
                    elif "ลับแล" in c_type or "เถื่อน" in c_type or "ตลาดมืด" in c_type:
                        strictness = 10
                        title = "ราชาตลาดมืด"
                        faction = "สมาคมนักฆ่า"
                        ruler_name = "เงาทมิฬ"
                        realm = 8
                        
                    c["law_strictness"] = strictness
                    
                    # Spawn the Ruler
                    ruler = self.spawn(self.worlds[0]) # Spawn in mortal world
                    ruler.name = ruler_name
                    ruler.realm = realm
                    ruler.title = title
                    ruler.faction = faction
                    ruler.city_id = c["id"]
                    ruler.is_loner = True # Don't wander taking disciples
                    ruler.energy = 100
                    if title == "ฮ่องเต้":
                        ruler.is_emperor = True
                        ruler.dragon_aura = True
                    c["ruler_cid"] = ruler.cid
                    
        while self.queue:
            day, cid = heapq.heappop(self.queue)
            ch = self.cast[cid]
            if not ch.alive:
                continue
            self.day = max(self.day, day)
            # --- Routine & Energy System ---
            # Update MP limits
            ch.max_mp = max(100.0, float(ch.realm * 100))
            if getattr(ch, "current_mp", 0) < ch.max_mp:
                ch.current_mp = min(ch.max_mp, getattr(ch, "current_mp", 100.0) + (ch.max_mp * 0.1))
                
            time_of_day = self.day % 4
            
            # ------------------------------------------------
            # Beast Forest Farming (ป่าหมื่นอสูร)
            # ------------------------------------------------
            if ch.energy > 50 and getattr(ch, "is_beast", False) == False and getattr(ch, "is_demon", False) == False and getattr(ch, "is_spirit", False) == False:
                if self.rng.random() < 0.1: # 10% chance to farm
                    ch.energy -= 40
                    if self.rng.random() < 0.15: # 15% chance to encounter beast
                        # Spawn wild beast
                        beast = self.spawn(self.worlds[0])
                        beast.name = "สัตว์อสูรป่า"
                        beast.is_beast = True
                        beast.realm = max(1, ch.realm + self.rng.randint(-1, 1))
                        print(f"\n🐾 [ป่าหมื่นอสูร] [{ch.name}] ออกล่าสัตว์อสูรและปะทะกับ [{beast.name}] ขั้น {beast.realm}!")
                        # We don't trigger combat.resolve directly here to avoid circular imports / missing world refs if not careful,
                        # but we can just use the event emitter or resolve it simply:
                        import tiandao.combat as combat
                        combat.resolve_combat(ch, beast, self.worlds[0], self)
                    else:
                        ch.insight += 10
                        # gain some items or spirit stones
                        print(f"\n🌲 [ป่าหมื่นอสูร] [{ch.name}] ล่าสัตว์อสูรสำเร็จ ได้รับศิลาปราณและค่าความเข้าใจ!")
            
            # Energy consumption and state
            
            # Sect Facility: หอโอสถ Healing
            if getattr(ch, "hp", 100) < getattr(ch, "max_hp", 100) and getattr(ch, "org", None) is not None and ch.org < len(self.orgs):
                org = self.orgs[ch.org]
                if hasattr(org, "facilities") and "หอโอสถ" in org.facilities:
                    master_cid = org.facilities["หอโอสถ"]
                    if master_cid in self.cast and self.cast[master_cid].alive:
                        master = self.cast[master_cid]
                        ch.hp = getattr(ch, "max_hp", 100)
                        # Add to debts/relations to show gratitude
                        ch.debts.append({"target": master_cid, "amount": 1, "done": False, "reason": "รักษาบาดแผลที่หอโอสถ"})
            
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
                        earned = rng.randint(10, 50) * max(1, ch.realm)
                        ch.money[self.world(ch.world_id).tier] = ch.money.get(self.world(ch.world_id).tier, 0.0) + earned
                        # Send cut to master
                        if ch.master_cid != -1 and ch.master_cid in self.cast:
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
            

            if self.day > getattr(self, "last_disaster_day", 0) + 30:
                self.last_disaster_day = self.day
                
                # Sect Resource Distribution & Facilities
                for org in self.orgs:
                    if org.alive and org.members:
                        # Assign Facilities
                        if not hasattr(org, "facilities"): org.facilities = {}
                        if "หอโอสถ" not in org.facilities or org.facilities["หอโอสถ"] not in self.cast or not self.cast[org.facilities["หอโอสถ"]].alive:
                            alchs = [c for c in org.members if c in self.cast and self.cast[c].alive and getattr(self.cast[c], "alch_rank", 0) > 0]
                            if alchs: org.facilities["หอโอสถ"] = max(alchs, key=lambda c: getattr(self.cast[c], "alch_rank", 0))
                        
                        if "หอศาสตรา" not in org.facilities or org.facilities["หอศาสตรา"] not in self.cast or not self.cast[org.facilities["หอศาสตรา"]].alive:
                            smiths = [c for c in org.members if c in self.cast and self.cast[c].alive and getattr(self.cast[c], "forge_rank", 0) > 0]
                            if smiths: org.facilities["หอศาสตรา"] = max(smiths, key=lambda c: getattr(self.cast[c], "forge_rank", 0))
                        
                        if "ลานฝึกยุทธ" not in org.facilities or org.facilities["ลานฝึกยุทธ"] not in self.cast or not self.cast[org.facilities["ลานฝึกยุทธ"]].alive:
                            fighters = [c for c in org.members if c in self.cast and self.cast[c].alive and self.cast[c].realm >= 4]
                            if fighters: org.facilities["ลานฝึกยุทธ"] = max(fighters, key=lambda c: self.cast[c].realm)
                        
                        org.monthly_resource = getattr(org, "monthly_resource", 10000)
                        pool_c = org.monthly_resource * 0.4
                        pool_i = org.monthly_resource * 0.4
                        pool_o = org.monthly_resource * 0.2
                        
                        cd = getattr(org, "core_disciples", [])
                        id_ = getattr(org, "inner_disciples", [])
                        od = getattr(org, "outer_disciples", [])
                        
                        if cd:
                            share = int(pool_c / len(cd))
                            for cid in cd:
                                if cid in self.cast and self.cast[cid].alive: self.cast[cid].money[0] = self.cast[cid].money.get(0, 0) + share
                        if id_:
                            share = int(pool_i / len(id_))
                            for cid in id_:
                                if cid in self.cast and self.cast[cid].alive: self.cast[cid].money[0] = self.cast[cid].money.get(0, 0) + share
                        if od:
                            share = int(pool_o / len(od))
                            for cid in od:
                                if cid in self.cast and self.cast[cid].alive: self.cast[cid].money[0] = self.cast[cid].money.get(0, 0) + share

                # ------------------------------------------------
                # Divine Spirits Hunting Demons
                # ------------------------------------------------
                spirits = [c for c in self.cast if c.alive and getattr(c, "is_spirit", False)]
                demons = [c for c in self.cast if c.alive and getattr(c, "is_demon", False)]
                if spirits and demons:
                    if self.rng.random() < 0.3: # 30% chance for a holy crusade
                        hunter = self.rng.choice(spirits)
                        target = self.rng.choice(demons)
                        print(f"\n⚔️ [บัญชาสวรรค์] เผ่าวิญญาณศักดิ์สิทธิ์ [{hunter.name}] บุกสังหารมารร้าย [{target.name}] เพื่อรักษาสมดุลโลก!")
                        import tiandao.combat as combat
                        combat.resolve_combat(hunter, target, self.worlds[0], self)
                
                # Demon Temptation (Possession)
                for ch in self.cast:
                    if ch.alive and not getattr(ch, "is_demon", False) and not getattr(ch, "is_spirit", False) and not getattr(ch, "is_beast", False):
                        if getattr(ch, "karmic_debt", 0) > 1000 or getattr(ch, "ambition", 0) > 80:
                            if self.rng.random() < 0.05: # 5% chance every 30 days
                                ch.is_demon = True
                                ch.dao = "วิถีมาร"
                                if ch.org is not None and ch.org < len(self.orgs):
                                    # Leave current sect
                                    org = self.orgs[ch.org]
                                    if ch.cid in org.members: org.members.remove(ch.cid)
                                    if ch.cid in org.core_disciples: org.core_disciples.remove(ch.cid)
                                    if ch.cid in org.inner_disciples: org.inner_disciples.remove(ch.cid)
                                    if ch.cid in org.outer_disciples: org.outer_disciples.remove(ch.cid)
                                ch.org = None
                                print(f"\n🩸 [มารสิงสู่] [{ch.name}] ถูกจิตมารเข้าครอบงำเพราะกิเลสหนา! กลายเป็นเผ่ามารอย่างสมบูรณ์แบบ!")

                # Beast Horde Siege
                beast_kings = [c for c in self.cast if c.alive and getattr(c, "is_beast", False) and c.realm >= 4]
                for king in beast_kings:
                    if not getattr(king, "has_human_form", False):
                        king.has_human_form = True
                        king.name = "ราชันย์อสูร" + self.rng.choice(["เพลิง", "ทมิฬ", "สายฟ้า", "โลหิต", "น้ำแข็ง"])
                        print(f"\n🐉 [คลื่นสัตว์อสูร] สัตว์อสูรบำเพ็ญตบะทะลวงขั้นสำเร็จ จำแลงกายเป็นมนุษย์ นามว่า [{king.name}]!")
                    
                    if self.rng.random() < 0.1: # 10% chance to attack a city
                        if hasattr(C, "CITIES"):
                            targets = [city for city in C.CITIES if "ชายแดน" in city.get("type_desc", "") or "หน้าด่านสำนัก" in city.get("type_desc", "")]
                            if targets:
                                target = self.rng.choice(targets)
                                print(f"\n🌋 [คลื่นสัตว์อสูรบุกเมือง] [{king.name}] นำกองทัพอสูรบุกโจมตีเมือง <{target['name_th']}>!")
                                ruler_cid = target.get("ruler_cid", -1)
                                if 0 <= ruler_cid < len(self.cast) and self.cast[ruler_cid].alive:
                                    ruler = self.cast[ruler_cid]
                                    # Fake combat for siege
                                    if king.realm > ruler.realm:
                                        print(f" -> 🔴 เมืองแตก! [{ruler.name}] พ่ายแพ้ต่อราชันย์อสูรและสิ้นชีพ! กฎหมายเมืองล่มสลาย!")
                                        ruler.alive = False
                                        target["law_strictness"] = 0
                                    else:
                                        print(f" -> 🟢 ป้องกันเมืองสำเร็จ! [{ruler.name}] สังหารราชันย์อสูรได้ เมืองสงบสุข!")
                                        king.alive = False
                                        ruler.max_hp = getattr(ruler, "max_hp", 100) + 50
                                        print(f" -> 🔮 [{ruler.name}] ดูดซับแก่นอสูร พลังชีวิตสูงสุดเพิ่มขึ้น!")

                # Imperial Spy Network
                if len(self.orgs) > 0:
                    target_sect = self.rng.choice(self.orgs)
                    if target_sect.alive:
                        stealth_level = self.rng.randint(50, 100)
                        if stealth_level > getattr(target_sect, "alert_level", 50):
                            intel_gathered = self.rng.randint(10, 50)
                            target_sect.threat_level = getattr(target_sect, "threat_level", 0) + intel_gathered
                            # log silently or print (using print here for engine logs as requested by user)
                            print(f"\n🕵️‍♂️ [องครักษ์เสื้อแพร] แทรกซึมสำเร็จ! พบว่า {target_sect.name} ซ่องสุมกำลัง (ภัยคุกคาม: {target_sect.threat_level}/100)")
                        else:
                            print(f"\n🔴 [องครักษ์เสื้อแพร] ความแตก! สายลับถูกจับกุมและสังหารโดย {target_sect.name}")
                            
                for w in self.worlds:
                    w.disaster_timer = getattr(w, "disaster_timer", 0) + 1
                    w.current_disaster = rng.choice(["ปกติ", "กบฏราชสำนัก", "โรคระบาดใหญ่", "สมบัติโบราณปรากฏ"])
                    if w.current_disaster == "กบฏราชสำนัก":
                        print(f"🚨💥 [ภัยพิบัติแผ่นดิน] {w.name} เกิดกบฏราชสำนัก!")
                    elif w.current_disaster == "โรคระบาดใหญ่":
                        print(f"🚨🦠 [ภัยพิบัติแผ่นดิน] {w.name} เกิดโรคระบาด!")
                    elif w.current_disaster == "สมบัติโบราณปรากฏ":
                        print(f"🚨📜 [ภัยพิบัติแผ่นดิน] {w.name} สมบัติปรากฏ!")
                    SEASONS.maybe_trigger_disaster(self, w, rng)

            if ch.hidden:
                if ch.is_lord:
                    ch.last_day = self.day
                    if self.day >= ch.return_day:
                        ch.hidden = False
                        w0 = self.world(ch.world_id)
                        self.emit(w0, "เจ้าโกลาหลคืนกลับ", ch, None, ["ทำลาย"], "คืนกลับ",
                                  f"{ch.name}หวนคืนสู่ห้วงโกลาหลอีกครั้ง แข็งแกร่งกว่าเดิม "
                                  f"(ครั้งที่ {ch.lord_returns})", 0,
                                  {"ไม่มีวันตาย": "สลายไปแล้วก่อพลังกลับมาใหม่"})
                        self.schedule(ch, rng.randint(30, 400))
                    else:
                        self.schedule(ch, max(1, ch.return_day - self.day))
                    continue
                R.age_and_decay(self, ch, self.world(ch.world_id),
                                self.day - ch.last_day, rng)
                ch.last_day = self.day
                if ch.alive:
                    if rng.random() < 0.15:
                        ch.hidden = False
                    self.schedule(ch, rng.randint(2000, 12000))
                continue

            if ch.travel_dest >= 0:
                # กำลังเดินทางอยู่ (ตั้งไว้จาก resolve() "เดินทาง") — เหมือนกับ ch.hidden ด้านบน: ไม่ผ่าน
                # การเลือก intent ปกติเลยจนกว่าจะถึงจุดหมายจริง แค่ไปโผล่เช็คเป็นระยะระหว่างทางแทน
                world0 = self.world(ch.world_id)
                R.age_and_decay(self, ch, world0, self.day - ch.last_day, rng)
                ch.last_day = self.day
                if not ch.alive:
                    continue
                if self.day >= ch.travel_arrival_day:
                    dest_name = PL.PLACES[ch.travel_dest][0] if 0 <= ch.travel_dest < len(PL.PLACES) else "?"
                    ch.place = ch.travel_dest
                    ch.travel_dest = -1
                    self.emit(world0, "เดินทาง", ch, None, ["เดินทาง"], "มาถึง",
                              f"{ch.name}เดินทางมาถึง{dest_name}แล้ว", 0, {})
                    travel_ev = next(e for e in E.EVENT_TABLE if e["kind"] == "เดินทาง")
                    self.schedule(ch, rng.randint(*travel_ev["gap"]))
                    continue
                hit = TR.roll_enroute_event(rng)
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

            actor = ch
            break
        if actor is None:
            return None

        elapsed = self.day - self.last_day
        self.last_day = self.day
        self.eco_regen(elapsed)
        world = self.world(actor.world_id)

        # แก่/เสื่อมคิดเฉพาะตอนตัวละครขยับ (เร็วกว่าไล่ทุกคนทุกเหตุการณ์)
        R.age_and_decay(self, actor, world, self.day - actor.last_day, rng)
        actor.last_day = self.day

        for w in self.worlds:
            R.heaven_inflow(w, w.n_mortal, self.day - w.checked_day)
            self.repopulate(w, self.day - w.checked_day)
            
            if w.tier == 1:
                if w.n_alive >= C.HEAVEN_POP_LIMIT:
                    w.is_closed = True
                elif w.n_alive < C.HEAVEN_POP_LIMIT * 0.8:
                    w.is_closed = False
                    
            w.checked_day = self.day
            notes = R.check_world(self, w, rng)
            if notes is not None:
                self.emit(w, "ยุคล่ม", actor, None, ["ความตาย"], "วัฏจักร",
                          f"{w.name} สิ้นพลังฟ้า ยุคหนึ่งจบลง ผู้ล่วงลับ {len(notes)} คน",
                          0, {"โลกตกระดับ": f"เหลือชั้น {w.tier}"})

        if not actor.alive:
            return self.emit(world, "สิ้นอายุขัย", actor, None, ["ความตาย"], "ตาย",
                             f"{actor.name}สิ้นอายุขัย", elapsed, {})

        # การเสื่อมสลายของมหาผนึกหมื่นมารตามกาลเวลาและแรงสั่นสะเทือน
        if elapsed > 0:
            seal_decay = (elapsed / 365.0) * getattr(C, "MARA_SEAL_DECAY_PER_YEAR", 0.5)
            if rng.random() < getattr(C, "MARA_SEAL_SHOCK_P", 0.04):
                shock = rng.uniform(0.5, 3.0)
                seal_decay += shock
            if seal_decay > 0:
                self.mara_seal = max(0.0, self.mara_seal - seal_decay)
                if self.mara_seal <= getattr(C, "MARA_SEAL_WEAK_THRESHOLD", 30.0) and not self.mara_seal_notified_weak and not self.mara_seal_broken:
                    self.mara_seal_notified_weak = True
                    self.emit(self.worlds[0], "มหาผนึกสั่นคลอน", None, None, ["ทำลาย"], "ผนึกอ่อนแอ",
                              f"⚠️⚡ [มหาผนึกสั่นคลอน] แดนลับรอยแยกผนึกหมื่นมารสะกดโลกเริ่มอ่อนกำลังลง (เหลือ {self.mara_seal:.1f}%) ไอปีศาจเริ่มรั่วไหลสู่โลกมนุษย์!",
                              0, {"พลังผนึก": f"{self.mara_seal:.1f}%"})
                if self.mara_seal <= getattr(C, "MARA_SEAL_BROKEN_THRESHOLD", 0.0) and not self.mara_seal_broken:
                    self.mara_seal_broken = True
                    self.emit(self.worlds[0], "มหาผนึกแตกพัง", None, None, ["ทำลาย", "ความตาย"], "ผนึกพังทลาย",
                              f"🚨💀 [มหาผนึกแตกพัง] มหาผนึกสะกดหมื่นมารในแดนลับรอยแยกพังทลายลงแล้ว! แดนมารและโลกมนุษย์เชื่อมต่อถึงกันโดยสมบูรณ์!",
                              0, {"พลังผนึก": "พังทลาย (0.0%)", "สัญจร": "เปิดทางเชื่อมต่อโลกมนุษย์-แดนมาร"})

        # มารบุกโลกมนุษย์ (หากผนึกแตก โอกาสบุกจะเพิ่มขึ้นอย่างมาก)
        mara_raid_p = C.MARA_RAID_P * (2.5 if getattr(self, "mara_seal_broken", False) else 1.0)
        if world.kind == "mortal" and world.lateral and rng.random() < mara_raid_p:
            mw = self.world(world.lateral[0])
            if mw.kind == "mara":
                self.mara_raid(world, elapsed, rng)
        if (world.kind == "mortal" and self.chaos_wid is not None
                and self.chaos_wid in world.lateral and rng.random() < C.CHAOS_RAID_P):
            self.chaos_raid(world, elapsed, rng)
        # ดิ่งลงโลกมนุษย์ตรงๆ ผ่านรูหนอน ไม่ผ่านแดนเซียน
        if (world.kind == "mortal" and world.place_key == 0
                and self.chaos_wid is not None and rng.random() < C.CHAOS_INVADE_P):
            self.chaos_invade(world, elapsed, rng)

        others = [c for c in self.living_in(world.wid) if c.cid != actor.cid]

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
                win, lose, margin = R.resolve_clash(h, actor, world, self.items, rng)
                res = R.apply_defeat(self, world, win, lose, margin, rng)
                actor.rivals[h.cid] = actor.rivals.get(h.cid, 0) + 2
                e = self.emit(world, "ล่ามนุษย์มาร", h, actor, ["เลือด", "ทำลาย"], res,
                              f"{h.name}ตามล่า{actor.name}เพราะเป็นมนุษย์มาร — {lose.name}เป็นฝ่ายเสีย",
                              elapsed, {"เผ่า": actor.race(), "margin": round(margin, 3),
                                        "winner": win.cid})
                if not actor.alive:
                    return e

        city_dict = None
        if hasattr(C, "CITIES") and actor.city_id >= 0:
            for c in C.CITIES:
                if c["id"] == actor.city_id:
                    city_dict = c
                    break
                    
        # Update pick_event call to include city
        # Layer 1 Utility AI (Cultivator Brain v2, Phase 2) ต่อยอด IN.weigh() เดิม ก่อนสุ่มเลือก
        w = IN.weigh(actor, self, E.EVENT_TABLE, bool(others))
        w = self.brain_manager.decide(actor, self, w)
        kind = IN.sample_weighted(w, rng)
        ev = next((e for e in E.EVENT_TABLE if e["kind"] == kind), None) \
            or E.pick_event(actor, rng, bool(others), city=city_dict)
        target = None
        if ev["tgt"]:
            if ev["kind"] == "สะสางเรื่องเก่า":
                owed = [c for c in others
                        if any(not d["done"] and d["target"] == c.cid for d in actor.debts)]
                target = rng.choice(owed) if owed else rng.choice(others)
            elif ev["kind"] == "ชิงสมบัติ":
                targets_with_treasures = []
                for c in others:
                    for iid in c.items:
                        it = self.items.get(iid)
                        if it and it.name in [t[0] for t in TREASURES]:
                            targets_with_treasures.append(c)
                            break
                if targets_with_treasures and rng.random() < getattr(actor, "greed", 0.5) * 2:
                    target = rng.choice(targets_with_treasures)
                else:
                    foes = [c for c in others if c.cid in actor.rivals]
                    target = rng.choice(foes) if foes and rng.random() < 0.55 else rng.choice(others)
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
        if getattr(actor, "org", None) is not None and actor.org < len(self.orgs) and rng.random() < 0.1:
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
                if target_cid in self.cast and self.cast[target_cid].alive:
                    target_ch = self.cast[target_cid]
                    import tiandao.combat as combat
                    # Law Enforcement Check
                    blocked = False
                    if actor.city_id >= 0 and hasattr(C, "CITIES"):
                        city_dict = next((c for c in C.CITIES if c["id"] == actor.city_id), None)
                        if city_dict and "law_strictness" in city_dict:
                            if rng.random() * 100 < city_dict["law_strictness"]:
                                blocked = True
                                r_cid = city_dict.get("ruler_cid", -1)
                                if r_cid in self.cast and self.cast[r_cid].alive:
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
        IN.learn_from_outcome(actor, ev["kind"], before, IN.snapshot(actor))
        if ev["kind"] == "ค้นแดนลับ" and actor.rumor_leads:
            actor.rumor_leads = [l for l in actor.rumor_leads if l["kind"] != "แดนลับ"]
        for t in ev["tags"]:
            actor.exp[t] = actor.exp.get(t, 0) + 1
        e = self.emit(world, ev["kind"], actor, target, ev["tags"], outcome, text, elapsed, d)
        if actor.alive:
            if actor.travel_dest >= 0:
                # เพิ่งเริ่มเดินทางจริง (resolve() ตั้ง travel_dest/travel_arrival_day ไว้แล้ว) — ต้อง
                # นัดตื่นครั้งแรกภายใน TRAVEL_ENROUTE_CHECK_DAYS ไม่ใช่กระโดดตรงไปวันถึงเลย ไม่งั้นจะไม่มี
                # โอกาสได้เช็คเหตุการณ์ระหว่างทางสักครั้งเดียวสำหรับทริปสั้น (บล็อก ch.travel_dest ด้านบน
                # ใน step() เป็นตัวจัดการรอบเช็คถัดๆ ไปเองหลังจากนี้)
                first_wake = min(C.TRAVEL_ENROUTE_CHECK_DAYS, actor.travel_arrival_day - self.day)
                self.schedule(actor, max(1, first_wake))
            else:
                self.schedule(actor, gap if not actor.hidden else rng.randint(2000, 12000))
        return e

    def chaos_invade(self, world, elapsed, rng):
        """เผ่าโกลาหลมาถึงโลกมนุษย์แล้วทำอะไร:
        เล็งสถานที่ที่มวลปราณหนาแน่นที่สุด ทำลายสิ่งก่อสร้าง กลืนกินแร่และของ
        แล้วขยายรอยแยกให้กว้างขึ้นเพื่อดึงขุนพลระดับสูงลงมาสมทบ"""
        pool = self.living_in(self.chaos_wid)
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
        defenders = [x for x in self.living_in(world.wid) if x.place == spot]
        d = {"รอยแยก": f"กว้าง {world.rift:.1f} — ขั้นที่ลงมาได้ถึง {C.CHAOS_RANKS[min(cap, len(C.CHAOS_RANKS)-1)]}",
             "ถูกกด": f"ลงมาโลกมนุษย์แล้วถูกกดลง {C.CHAOS_DESCEND_PUSH} ขั้นตามกฎของโลกล่าง"}
        if defenders:
            v = max(defenders, key=lambda x: R.power(x, world, self.items))
            win, lose, margin = R.resolve_clash(c, v, world, self.items, rng, self.day)
            res = R.apply_defeat(self, world, win, lose, margin, rng)
            d["ผู้ต้านทาน"] = f"{v.name} — {res}"
            d["margin"] = round(margin, 3)
            d["winner"] = win.cid
            if R.has_anti_chaos(v):
                d["แก้ทาง"] = "ผู้ต้านทานรู้วิชาที่แก้ทางเผ่าโกลาหล"
            if win is not c:
                world.rift = max(0.0, world.rift - C.RIFT_GROWTH)
                self.emit(world, "โกลาหลบุกโลกมนุษย์", c, v, ["ทำลาย", "ต่อสู้"], "ถูกขับไล่",
                          f"{c.name}({c.realm_name()}) ทะลุรูหนอนลงมาถล่ม{spot_name} "
                          f"แต่ถูก{v.name}ขับไล่กลับไป", elapsed, d)
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

    def chaos_raid(self, world, elapsed, rng):
        """เผ่าโกลาหลบุกมาทำลายทุกอย่างให้กลับเป็นความว่างก่อนกำเนิดจักรวาล"""
        raiders = self.living_in(self.chaos_wid)
        prey = self.living_in(world.wid)
        if not raiders or not prey:
            return
        c = rng.choice(raiders)
        prey.sort(key=lambda x: -R.power(x, world, self.items))
        v = rng.choice(prey[:3])          # ไล่ล่าผู้แข็งแกร่งก่อน แต่ไม่ใช่คนเดิมทุกครั้ง
        win, lose, margin = R.resolve_clash(c, v, world, self.items, rng, self.day)
        res = R.apply_defeat(self, world, win, lose, margin, rng)
        d = {"แพ้ทาง": "มนุษย์แพ้ทางเผ่าโกลาหล", "margin": round(margin, 3), "winner": win.cid}
        if R.has_anti_chaos(v):
            d["แก้ทาง"] = "รู้วิชาที่แก้ทางเผ่าโกลาหลได้"
        if v.alive and not v.thrall and rng.random() < C.CHAOS_THRALL_P:
            v.thrall = True
            v.blood["chaos"] = v.blood.get("chaos", 0.0) + 0.2
            R.normalize(v.blood)
            v.org = None
            d["ตกเป็นพวกมัน"] = f"{v.name}ยอมสวามิภักดิ์ — ได้รับการดูแล แต่เป็นทาสของมัน"
        self.emit(world, "โกลาหลบุก", c, v, ["ทำลาย", "ความตาย"], res,
                  f"{c.name}({c.realm_name()}) บุก{world.name}ปะทะ{v.name} — {lose.name}เป็นฝ่ายเสีย",
                  elapsed, d)

    def mara_raid(self, world, elapsed, rng):
        mara_world = self.world(world.lateral[0])
        raiders = [c for c in self.living_in(mara_world.wid) if c.realm >= 2]
        prey = self.living_in(world.wid)
        if not raiders or not prey:
            return
            
        m, v = rng.choice(raiders), rng.choice(prey)
        
        if world.defense_array > 0:
            if rng.random() < 0.80:  # โอกาสสกัดสำเร็จ 80%
                world.defense_array = max(0.0, world.defense_array - 15.0)
                d_array = {"ค่ายกลทำงาน": f"สกัดกั้นมารได้ พลังค่ายกลเหลือ {world.defense_array:.1f}/{world.defense_max:.1f}"}
                self.emit(world, "มารบุก", m, v, ["ทำลาย"], "ถูกสกัดกั้น",
                          f"ค่ายกลป้องกันโลกปกป้อง{v.name}จากการรุกรานของ{m.name}", elapsed, d_array)
                return
            else:
                world.defense_array = max(0.0, world.defense_array - 5.0)
                
        if rng.random() < C.MARA_CONVERT_P:
            v.blood["mara"] = v.blood.get("mara", 0.0) + 0.25
            R.normalize(v.blood)
            v.inner += 1.5
            self.emit(world, "มารบุก", m, v, ["ทำลาย", "เลือด"], "ถูกครอบงำ",
                      f"{m.name}จากแดนมารครอบงำ{v.name} เลือดมารลุกลาม", elapsed,
                      {"เผ่า": v.race()})
        else:
            self.kill(v, f"ถูก{m.name}จากแดนมารกินเป็นอาหาร", killer=m)
            self.emit(world, "มารบุก", m, v, ["ทำลาย", "ความตาย"], "ตาย",
                      f"{m.name}จากแดนมารจับ{v.name}ไปเป็นอาหาร", elapsed, {})

    # ------------------------------------------------------------ ผลลัพธ์
    def resolve(self, ev, a, t, w, gap, rng):
        k, d = ev["kind"], {}
        if k == "เหตุการณ์เมือง":
            if getattr(a, "hp", 0) <= 0: return "ทั่วไป", "บาดเจ็บหนักเกินกว่าจะเดินในเมือง", d
            
            a.cities_visited = getattr(a, "cities_visited", 0) + 1
            if hasattr(a, "update_title"): a.update_title()
            
            # 🤖 👶 [ระบบอายุขัยและชราภาพ]
            age_now = a.age(self.day)
            if age_now >= 60:
                a.max_hp = max(50, getattr(a, "max_hp", 100) - 2)
                a.hp = min(getattr(a, "hp", 100), a.max_hp)
                if age_now >= 85 and rng.randint(1, 100) < 15:
                    self.kill(a, f"สิ้นอายุขัยในวัย {age_now} ปี อย่างสงบ")
                    return "ความสงบ", f"🧓🍂 [สิ้นอายุขัย] ปิดตำนานยอดฝีมือ... [{a.name}] สิ้นใจลงด้วยโรคชราในวัย {age_now} ปี", d
            
            if a.city_id >= 0 and hasattr(C, "CITIES"):
                city = next((c for c in C.CITIES if c["id"] == a.city_id), None)
                if city:
                    safety = city["attributes"]["safety"]
                    jianghu = city["attributes"]["jianghu"]
                    wealth = city["attributes"]["wealth"]
                    info = city["attributes"]["info"]
                    faction = city["dominant_faction"]
                    
                    potion_cost = 40
                    disaster = getattr(w, "current_disaster", "ปกติ")
                    if disaster == "กบฏราชสำนัก": safety = max(5, safety - 40)
                    elif disaster == "โรคระบาดใหญ่": potion_cost = 120
                    elif disaster == "สมบัติโบราณปรากฏ": jianghu = min(100, jianghu + 20)
                    
                    if not hasattr(a, "companions") or not isinstance(a.companions, dict):
                        a.companions = {}
                    if not hasattr(a, "nemeses") or not isinstance(a.nemeses, dict):
                        a.nemeses = {}
                        
                    # ⚔️ คำนวณพลังรบรวม (ตัวเอก + อาวุธ + สหาย)
                    combat_power = R.power(a, w)
                    if a.inventory.get("อาวุธ") == "กระบี่เหล็กเย็น":
                        combat_power += 25
                    
                    c_bonus = {"แม่นางเยว่เอ๋อร์": 10, "จ้าวเถี่ยซาน": 40, "ศิษย์พี่ใหญ่เซี่ย": 20, "แม่นางเยี่ยเสวี่ย": 30}
                    for comp in a.companions.keys():
                        combat_power += c_bonus.get(comp, 0)
                    
                    pre_msg = ""
                    # [ทักษะสหาย] หมอยาปรุงยาให้ฟรี
                    if "แม่นางเยว่เอ๋อร์" in a.companions and a.inventory.get("ยาสมานแผล", 0) == 0:
                        a.inventory["ยาสมานแผล"] = a.inventory.get("ยาสมานแผล", 0) + 1
                        pre_msg += "🌸 [ทักษะสหาย] แม่นางเยว่เอ๋อร์ปรุง 'ยาสมานแผล' ให้ฟรี! "
                    
                    def check_hp(msg_prefix):
                        msg_append = ""
                        if getattr(a, "hp", 100) < (getattr(a, "max_hp", 100) * 0.4) and a.inventory.get("ยาสมานแผล", 0) > 0:
                            a.inventory["ยาสมานแผล"] -= 1
                            old_hp = a.hp
                            a.hp = min(a.max_hp, a.hp + 30)
                            msg_append = f" 🤖 [สัญชาตญาณ] ดื่มยาสมานแผล ฟื้นฟู +{a.hp - old_hp} HP (เหลือยา {a.inventory['ยาสมานแผล']} ขวด)"
                            
                        if getattr(a, "hp", 100) <= 0:
                            self.kill(a, "สิ้นชีพในการต่อสู้ที่เมือง")
                            msg_append += " 💀 [ข่าวลือยุทธภพ] สิ้นชีพแดนยุทธภพแล้ว!"
                        return pre_msg + msg_prefix + msg_append
                        
                    # 🤖 🏛️ [ระบบก่อตั้งสำนักและการทรยศหักหลัง]
                    if getattr(a, "realm", 1) >= 4 and getattr(a, "sect_name", None) is None and rng.randint(1, 100) < 10:
                        a.sect_name = f"สำนัก{a.name[:3]}"
                        a.sect_role = "เจ้าสำนัก"
                        msg = f"🏯 [ก่อตั้งสำนัก] บารมีแก่กล้า! [{a.name}] สถาปนา [{a.sect_name}] ขึ้น!"
                        # ชวนคน
                        for c in self.living_in(w.wid):
                            if c.cid != a.cid and getattr(c, "sect_name", None) is None and rng.random() < 0.2:
                                c.sect_name = a.sect_name
                                c.sect_role = "ศิษย์ในสำนัก"
                                msg += f" 📜 รับ [{c.name}] เป็นศิษย์"
                        return "วิถียุทธ", pre_msg + msg, d
                        
                    if getattr(a, "sect_role", "") == "ศิษย์ในสำนัก" and rng.randint(1, 100) < 5:
                        masters = [m for m in self.living_in(w.wid) if getattr(m, "sect_name", "") == a.sect_name and getattr(m, "sect_role", "") == "เจ้าสำนัก"]
                        if masters:
                            master = masters[0]
                            if rng.random() < 0.5:
                                self.kill(master, f"ถูกศิษย์ทรยศ {a.name} ลอบสังหารด้วยยาพิษ")
                                a.sect_role = "เจ้าสำนัก"
                                msg = f"☠️ [ศิษย์ทรยศสำเร็จ] [{a.name}] วางยาพิษ [{master.name}] สำเร็จ! สถาปนาตนเป็นเจ้าสำนักคนใหม่!"
                                return "อันตราย", pre_msg + msg, d
                            else:
                                a.hp = max(0, a.hp - 40)
                                a.sect_role = "ศิษย์ทรยศ"
                                msg = f"🛡️ [แผนแตก] เจ้าสำนัก [{master.name}] จับได้! ฟาดฝ่ามือใส่ [{a.name}] ขับออกจากสำนักเป็นศิษย์ทรยศ! (-40 HP)"
                                msg = check_hp(msg)
                                return "อันตราย", msg, d
                        
                    # 🤖 💥 [ความล้ำ: ระบบฆ่ากันเองข้ามตัวละคร & บุพเพ] 💥
                    if rng.randint(1, 100) <= 15:
                        other_chars = [c for c in self.living_in(w.wid) if c.cid != a.cid]
                        if other_chars:
                            b = rng.choice(other_chars)
                            if not hasattr(b, "companions"): b.companions = {}
                            if not hasattr(b, "nemeses"): b.nemeses = {}
                            
                            if b.name in a.nemeses:
                                rival_power = R.power(b, w)
                                if getattr(b, "inventory", {}).get("อาวุธ") == "กระบี่เหล็กเย็น": rival_power += 25
                                msg = f"⚔️ [ศึกสายเลือด] คู่แค้นล้างปฐพี! [{a.name}] และ [{b.name}] ชักอาวุธเข้าห้ำหั่นกัน!"
                                if combat_power >= rival_power:
                                    a.insight += 2.0
                                    a.enemies_defeated = getattr(a, "enemies_defeated", 0) + 1
                                    self.kill(b, f"ถูก {a.name} สังหารในการดวลเดือด")
                                    del a.nemeses[b.name]
                                    msg += f" 🦅 [{a.name}] โค่นศัตรูสำเร็จ!"
                                else:
                                    b.insight += 2.0
                                    b.enemies_defeated = getattr(b, "enemies_defeated", 0) + 1
                                    self.kill(a, f"ถูก {b.name} สังหารในการดวลเดือด")
                                    if a.name in b.nemeses: del b.nemeses[a.name]
                                    msg += f" 💀 [{a.name}] ถูกสังหารโดย [{b.name}]!"
                                return "อันตราย", pre_msg + msg, d
                            
                            if b.name not in a.companions and b.name not in a.nemeses:
                                if getattr(a, "moral", 0) * getattr(b, "moral", 0) >= 0: # ธรรมะเจอธรรมะ
                                    a.companions[b.name] = 80
                                    b.companions[a.name] = 80
                                    msg = f"💖 [แต่งงาน] [{a.name}] และ [{b.name}] พบกันที่ {city['name_th']} และเข้าพิธีวิวาห์!"
                                    
                                    # 👶 กำเนิดทายาท
                                    if rng.random() < 0.5:
                                        child = self.spawn(w)
                                        child.parent_name = a.name
                                        child.generation = getattr(a, "generation", 1) + 1
                                        child.money[w.wid] = a.money.get(w.wid, 0) // 2
                                        msg += f" 🍼 [สายเลือดสืบทอด] ให้กำเนิดทายาทชื่อ [{child.name}] (รุ่นที่ {child.generation})!"
                                    return "ความสัมพันธ์", pre_msg + msg, d
                                else:
                                    a.nemeses[b.name] = {"title": getattr(b, "title", ""), "power": R.power(b, w), "hatred": 100}
                                    b.nemeses[a.name] = {"title": getattr(a, "title", ""), "power": combat_power, "hatred": 100}
                                    msg = f"😡 [ศึกข้ามอุดมการณ์] [{a.name}] ประจันหน้ากับ [{b.name}] ฝ่ายธรรมะและอธรรมไม่มีวันอยู่ร่วมโลก! (ผูกปมแค้น)"
                                    return "ความสัมพันธ์", pre_msg + msg, d
                        
                    # [💡 TRIGGER พิเศษ: การตามล่าของศัตรูคู่อาฆาต]
                    dangerous_nemeses = [n for n, info in a.nemeses.items() if info.get("hatred", 0) >= 100]
                    if dangerous_nemeses and rng.randint(1, 100) > safety:
                        hunter = rng.choice(dangerous_nemeses)
                        h_info = a.nemeses[hunter]
                        msg = f"🚨 [เผชิญหน้าคู่แค้น] {hunter} ({h_info.get('title', '')}) ปรากฏตัวขวางหน้าหมายเอาชีวิต!"
                        if combat_power >= h_info.get("power", 0):
                            msg += f" 🦅 [ล้างแค้นสำเร็จ] ท่านโค่น {hunter} ลงได้สะใจ! (+150 เงิน, ได้ EXP)"
                            a.money[w.wid] = a.money.get(w.wid, 0) + 150
                            a.insight += 1.2
                            a.enemies_defeated = getattr(a, "enemies_defeated", 0) + 1
                            R.cultivate(a, gap)
                            del a.nemeses[hunter]
                            return "อันตราย", pre_msg + msg, d
                        else:
                            msg += f" 💥 [พ่ายแพ้คู่แค้น] ท่านพลาดท่าบาดเจ็บสาหัส เสีย -50 HP และถูกชิงทรัพย์ -100 เงิน"
                            a.hp -= 50
                            a.money[w.wid] = max(0, a.money.get(w.wid, 0) - 100)
                            a.nemeses[hunter]["hatred"] = 60
                            msg = check_hp(msg)
                            return "อันตราย", msg, d
                    
                    if rng.randint(1, 100) > safety:
                        msg = "⚠️ [เหตุการณ์อันตราย] ปาร์ตี้ของคุณโดนโจรป่าดักโจมตี!"
                        enemy_power = rng.randint(40, max(90, int(w.tier*40)))
                        
                        if combat_power >= enemy_power:
                            a.money[w.wid] = a.money.get(w.wid, 0) + 100
                            a.insight += 0.5
                            a.enemies_defeated = getattr(a, "enemies_defeated", 0) + 1
                            R.cultivate(a, gap)
                            
                            if "เถาตี้" not in a.nemeses:
                                a.nemeses["เถาตี้"] = {"title": "จ้าวค่ายโจรเหล็ก", "power": 45, "hatred": 40}
                                msg = "🦅 [ชัยชนะ] ท่านสยบหัวหน้าโจรป่าได้สำเร็จ แต่มันอาฆาตหนีไปกบดาน! (สร้างคู่แค้น)"
                            else:
                                a.nemeses["เถาตี้"]["hatred"] = min(100, a.nemeses["เถาตี้"]["hatred"] + 40)
                                msg = f"🦅 [ชัยชนะ] ท่านสยบโจรป่าได้ แต่เถาตี้ยิ่งแค้นท่าน! (Hatred: {a.nemeses['เถาตี้']['hatred']}/100)"
                                
                            if a.companions:
                                for c in a.companions.keys():
                                    if type(a.companions[c]) == int: a.companions[c] = min(100, a.companions[c] + 10)
                                msg += " 💞 (+10 Affection)"
                            return "อันตราย", pre_msg + msg, d
                        else:
                            saved_by_love = None
                            for c, aff in list(a.companions.items()):
                                if type(aff) == int and aff >= 80:
                                    saved_by_love = c
                                    break
                            
                            if saved_by_love:
                                del a.companions[saved_by_love]
                                msg = f"💥 [พ่ายแพ้] 💖 [ปาฏิหาริย์แห่งรัก] {saved_by_love} กระโดดขวางวิถีกระบี่ ยอมเจ็บแทนท่าน! (ออกจากปาร์ตี้ไป)"
                                msg = check_hp(msg)
                                return "อันตราย", pre_msg + msg, d
                                
                            dmg = 50
                            msg_add = ""
                            if "จ้าวเถี่ยซาน" in a.companions:
                                dmg = dmg // 2
                                msg_add = " 🛡️ จ้าวเถี่ยซานรับแรงกระแทก!"
                            a.hp -= dmg
                            a.money[w.wid] = max(0, a.money.get(w.wid, 0) - 40)
                            msg = f"💥 [พ่ายแพ้] เสีย -{dmg} HP และเสีย -40 เงิน{msg_add}"
                            msg = check_hp(msg)
                            return "อันตราย", msg, d
                        
                    if rng.randint(1, 100) <= jianghu:
                        subs = ["tavern_friend", "buy_weapon", "train", "tournament"]
                        if a.companions:
                            subs.append("drink_tea")
                        sub = rng.choice(subs)
                        
                        if sub == "tournament":
                            if "คุณชายมู่" not in a.nemeses:
                                a.nemeses["คุณชายมู่"] = {"title": "กระบี่วารีคลั่ง", "power": 35, "hatred": 30}
                            h_info = a.nemeses["คุณชายมู่"]
                            msg = f"🥋 [การประลอง] ท่านเจอกับ คุณชายมู่"
                            if combat_power >= h_info["power"]:
                                a.insight += 0.4
                                a.enemies_defeated = getattr(a, "enemies_defeated", 0) + 1
                                R.cultivate(a, gap)
                                a.nemeses["คุณชายมู่"]["hatred"] = min(100, h_info["hatred"] + 35)
                                msg += f" 🏆 [ชนะประลอง] เขาเสียหน้าและเกลียดท่านมากขึ้น! (Hatred: {a.nemeses['คุณชายมู่']['hatred']}/100)"
                            else:
                                a.hp -= 10
                                msg += f" 🥈 [แพ้ประลอง] เสีย -10 HP"
                                msg = check_hp(msg)
                        elif sub == "drink_tea":
                            comp = rng.choice(list(a.companions.keys()))
                            choice = rng.choice(["share_gold", "talk_martial", "ignore"])
                            if choice == "share_gold" and a.money.get(w.wid, 0) >= 50:
                                a.money[w.wid] -= 50
                                if type(a.companions[comp]) == int: a.companions[comp] = min(100, a.companions[comp] + 25)
                                msg = f"🍻 [ความสัมพันธ์] ชวน {comp} ดื่มชา 💞 (+25 Affection)"
                            elif choice == "talk_martial":
                                a.insight += 0.3
                                R.cultivate(a, gap)
                                if type(a.companions[comp]) == int: a.companions[comp] = min(100, a.companions[comp] + 15)
                                msg = f"🍻 [ความสัมพันธ์] แลกเปลี่ยนวิชากับ {comp} 💞 (+15 Affection)"
                            else:
                                if type(a.companions[comp]) == int: a.companions[comp] = max(0, a.companions[comp] - 15)
                                msg = f"🍻 [ความสัมพันธ์] ดื่มชากับ {comp} แต่ละเลย 💔 (-15 Affection)"
                        elif sub == "tavern_friend":
                            if len(a.companions) < 2:
                                new_f = rng.choice(["แม่นางเยว่เอ๋อร์", "จ้าวเถี่ยซาน", "ศิษย์พี่ใหญ่เซี่ย", "แม่นางเยี่ยเสวี่ย"])
                                if new_f not in a.companions:
                                    a.companions[new_f] = 20
                                    msg = f"🤝 [สหายใหม่] {new_f} ยินดีร่วมเดินทาง! (ความสนิท 20)"
                                else:
                                    msg = "🍃 เจอคนรู้จักเก่า นั่งดื่มเหล้าทักทายกันเฉยๆ"
                            else:
                                msg = "🎒 ปาร์ตี้เต็มแล้ว จึงได้เพียงพูดคุยแลกเปลี่ยนสุรา"
                        elif sub == "buy_weapon":
                            if a.money.get(w.wid, 0) >= 150 and a.inventory.get("อาวุธ") is None:
                                a.money[w.wid] -= 150
                                a.inventory["อาวุธ"] = "กระบี่เหล็กเย็น"
                                msg = "🛍️ สวมใส่ 'กระบี่เหล็กเย็น' สำเร็จ"
                            else:
                                msg = "🍃 พ่อค้าเร่ขาย 'กระบี่เหล็กเย็น' (ราคา 150) แต่ไม่ได้ซื้อ"
                        elif sub == "train":
                            a.insight += 0.4
                            R.cultivate(a, gap)
                            msg = "🥋 นั่งสมาธิร่วมกันในหุบเขา ได้รับ EXP"
                        
                        return "วิถียุทธ", pre_msg + msg, d

                    if rng.randint(1, 100) <= wealth:
                        if a.companions and rng.random() > 0.5:
                            comp = rng.choice(list(a.companions.keys()))
                            if a.money.get(w.wid, 0) >= 40:
                                a.money[w.wid] -= 40
                                if type(a.companions[comp]) == int: a.companions[comp] = min(100, a.companions[comp] + 20)
                                msg = f"🛍️ [ความสัมพันธ์] ซื้อสมุนไพรให้ {comp} 💞 (+20 Affection)"
                            else:
                                msg = f"🛍️ [ความสัมพันธ์] {comp} อยากได้สมุนไพรแต่เงินไม่พอ"
                            return "การค้า", pre_msg + msg, d
                            
                        msg_add = ""
                        if "ศิษย์พี่ใหญ่เซี่ย" in a.companions:
                            potion_cost = 20
                            msg_add = " 📜 ศิษย์พี่ใหญ่เซี่ยต่อราคาเหลือ 20 เงิน!"
                            
                        if a.money.get(w.wid, 0) >= potion_cost and a.inventory.get("ยาสมานแผล", 0) < 2:
                            a.money[w.wid] -= potion_cost
                            a.inventory["ยาสมานแผล"] += 1
                            msg = f"🎒 ซื้อยาสมานแผลสำเร็จ (จ่าย {potion_cost} เงิน){msg_add}"
                        else:
                            msg = f"🍃 เจอร้านขาย 'ยาสมานแผล' (ราคา {potion_cost}){msg_add} แต่ไม่ได้ซื้อ"
                            
                        return "การค้า", pre_msg + msg, d
                        
                    # ทั่วไป
                    a.hp = min(getattr(a, "max_hp", 100), getattr(a, "hp", 100) + 10)
                    msg = "🍃 ปาร์ตี้เดินทางผ่านทุ่งหญ้าอย่างสงบ ฟื้นฟู +10 HP"
                    return "ความสงบ", pre_msg + msg, d
            return "ทั่วไป", f"{a.name} เดินเล่นในเมือง", d








        # --- อีเวนท์สายอาชีพใหม่ ---
        if k == "สะสมบุญบารมี":
            a.merit += rng.uniform(5.0, 15.0)
            a.moral = getattr(a, "moral", 0) + 2
            a.insight += rng.uniform(0.1, 0.5)
            R.cultivate(a, gap)
            if hasattr(a, "update_title"): a.update_title()
            return "บุญบารมี", f"{a.name}ออกโปรดสัตว์ สะสมบุญบารมีเพิ่มขึ้น", d
            
        if k == "ลาดตระเวน":
            a.money[w.wid] = a.money.get(w.wid, 0) + 10
            return "ลาดตระเวน", f"{a.name}ออกลาดตระเวนรักษาความสงบ ได้รับเบี้ยหวัด", d
            
        if k == "เปิดประมูล":
            if a.city_id >= 0:
                profit = rng.randint(100, 500)
                a.money[w.wid] = a.money.get(w.wid, 0) + profit
                return "ประมูล", f"{a.name}จัดงานประมูลในเมือง ได้กำไร {profit} เหรียญทอง", d
            return "ค้าขาย", f"{a.name}เร่ขายของทั่วไป", d

        if k == "จับกุมอาชญากร":
            if not t: return "ล้มเหลว", "ไม่พบอาชญากร", d
            if R.power(a, w) > R.power(t, w):
                d["เป้าหมาย"] = f"จับกุม {t.name} สำเร็จ"
                bounty = rng.randint(20, 100)
                a.money[w.wid] = a.money.get(w.wid, 0) + bounty
                a.moral = getattr(a, "moral", 0) + 3
                if hasattr(a, "update_title"): a.update_title()
                self.kill(t, f"ถูกจับกุมโดย {a.name}")
                return "จับกุม", f"{a.name}บุกจับกุม {t.name} ได้รับรางวัล {bounty}", d
            else:
                t.bonds[a.cid] = min(-10, t.bonds.get(a.cid, 0) - 20)
                return "ล้มเหลว", f"{a.name}พยายามจับกุม {t.name} แต่สู้ไม่ได้", d

        if k == "ลอบสังหาร":
            if not t: return "ล้มเหลว", "ไม่มีเป้าหมาย", d
            if a.profession in ("นักบวช", "นักพรต"):
                a.karma += 50.0 # ฆ่าคนกรรมพุ่ง
            
            # โอกาสสำเร็จขึ้นกับพลัง
            if R.power(a, w) * 1.5 > R.power(t, w):
                self.kill(t, f"ถูกลอบสังหารโดย {a.name}")
                a.money[w.wid] = a.money.get(w.wid, 0) + rng.randint(50, 200)
                a.moral = getattr(a, "moral", 0) - 5
                if hasattr(a, "update_title"): a.update_title()
                d["สังหาร"] = f"{t.name} ถูกลิดรอนวิญญาณ"
                return "สังหาร", f"{a.name}ลอบสังหาร {t.name} สำเร็จ", d
            else:
                t.bonds[a.cid] = min(-10, t.bonds.get(a.cid, 0) - 50)
                return "ล้มเหลว", f"{a.name}ลอบสังหาร {t.name} พลาด โดนหมายหัวกลับ", d

        if k == "ดักปล้น":
            if not t: return "ล้มเหลว", "ไม่มีเป้าหมาย", d
            if R.power(a, w) > R.power(t, w):
                stolen = t.money.get(w.wid, 0) // 2
                t.money[w.wid] = t.money.get(w.wid, 0) - stolen
                a.money[w.wid] = a.money.get(w.wid, 0) + stolen
                a.moral = getattr(a, "moral", 0) - 3
                if hasattr(a, "update_title"): a.update_title()
                t.bonds[a.cid] = min(-10, t.bonds.get(a.cid, 0) - 30)
                return "ปล้นสำเร็จ", f"{a.name}ดักปล้น {t.name} ได้เงิน {stolen}", d
            else:
                t.bonds[a.cid] = min(-10, t.bonds.get(a.cid, 0) - 10)
                return "ล้มเหลว", f"{a.name}พยายามปล้น {t.name} แต่โดนตีกลับ", d

        if k == "ทำนายชะตา":
            if not t: return "ล้มเหลว", "ไม่มีผู้ว่าจ้าง", d
            a.insight += rng.uniform(0.1, 0.5)
            t.insight += rng.uniform(0.1, 0.3)
            fee = rng.randint(5, 20)
            if t.money.get(w.wid, 0) >= fee:
                t.money[w.wid] -= fee
                a.money[w.wid] = a.money.get(w.wid, 0) + fee
            return "ทำนาย", f"{a.name}ตรวจดวงชะตาให้ {t.name} ชี้แนะหนทาง", d

        if k == "ขายข่าวลับ":
            if not t: return "ล้มเหลว", "ไม่มีลูกค้า", d
            fee = rng.randint(10, 50)
            if t.money.get(w.wid, 0) >= fee:
                t.money[w.wid] -= fee
                a.money[w.wid] = a.money.get(w.wid, 0) + fee
                t.bonds[a.cid] = max(0, t.bonds.get(a.cid, 0) + 10)
                return "ข่าวลับ", f"{a.name}ขายข้อมูลสำคัญให้ {t.name}", d
            return "ล้มเหลว", f"{t.name}ไม่มีเงินจ่ายค่าข่าวให้ {a.name}", d


        if k == "บำเพ็ญ":
            pv = self.place_of(a)
            if a.race() == "อสูร":
                boost = 1.0 + (w.tier * 0.5)
                if pv and pv[2] >= 2:
                    boost += 1.0
                R.cultivate(a, gap * boost)
            else:
                R.cultivate(a, gap)
            if pv and pv[3] == "ลานฝึก":
                a.insight += 0.4
                d["ลานฝึก"] = self.place_name(a)
            if w.tier == 0 and w.defense_array < w.defense_max and a.realm >= 2 and rng.random() < 0.4:
                restore = rng.uniform(2, 5)
                w.defense_array = min(w.defense_max, w.defense_array + restore)
                d["ซ่อมค่ายกล"] = f"เสริมพลังค่ายกลโลก (+{restore:.1f}) เหลือ {w.defense_array:.1f}/{w.defense_max:.1f}"
            return "บำเพ็ญ", f"{a.name}เก็บตัวบำเพ็ญที่{self.place_name(a)}", d

        if k == "ขัดเกลาสายเลือด":
            R.refine_blood(a, gap)
            return "ขัดเกลา", f"{a.name}ขัดเกลาสายเลือด{a.race()}ของตน", d

        if k == "ข้ามขั้น":
            pills = [i for i in a.items if self.items[i].kind == "ยาวิเศษ"]
            use, pname = 0.0, None
            if pills:
                best = max(pills, key=lambda i: getattr(self.items[i], "pill_bonus", 0.1))
                use = getattr(self.items[best], "pill_bonus", 0.1) / C.PILL_BREAK_BONUS
                pname = self.items[best].name
                a.items.remove(best)
            res, txt = R.attempt_break(self, a, w, rng, pills=use)
            if res == "ยังไม่ถึง":
                R.cultivate(a, gap)
                return "สะสมต่อ", f"{a.name}รู้ว่ายังไม่ถึงเวลา จึงบำเพ็ญต่อ", d
                
            if res is True:
                # evaluate_master_relationship
                if a.master_cid != -1 and a.master_cid in self.cast:
                    master = self.cast[a.master_cid]
                    if master.alive and a.realm > master.realm:
                        loyalty = getattr(a, "loyalty", 50)
                        ambition = getattr(a, "ambition", 50)
                        rebellion_score = ambition - loyalty
                        
                        if rebellion_score > 30:
                            # Betray Master
                            txt += f"\n -> [เนรคุณ] {a.name} ลุ่มหลงอำนาจ สังหารอาจารย์ {master.name} เพื่อชิงตำแหน่ง!"
                            self.kill(master, f"ถูกศิษย์ทรยศ {a.name} สังหารเพื่อชิงอำนาจ")
                            a.master_cid = -1
                            if a.cid in master.disciples: master.disciples.remove(a.cid)
                        elif ambition > 60 and loyalty >= 50:
                            # Peaceful Departure
                            txt += f"\n -> [แยกตัว] {a.name} คารวะอาจารย์และขอแยกตัวไปตั้งสาขาใหม่ด้วยดี"
                            a.master_cid = -1
                            if a.cid in master.disciples: master.disciples.remove(a.cid)
                        else:
                            # Stay Loyal
                            txt += f"\n -> [กตัญญู] แม้พลังสูงส่ง {a.name} ยังเคารพ {master.name} และยอมให้เป็นผู้อาวุโสสูงสุด"
                            master.is_loner = True # Force master to retire

            if pname:
                d["ใช้ยา"] = f"กิน{pname}ก่อนข้ามขั้น"
            d["คลังฟ้า"] = f"{w.name} {w.state()} ({w.ratio()*100:.0f}%)"
            d["ที่"] = self.place_name(a)
            return res, txt, d

        if k == "ฝึกวิชา":
            grade = 2 if a.realm >= SK.GRADE_REALM_BAR[2] else (
                1 if a.realm >= SK.GRADE_REALM_BAR[1] else 0)
            grade = rng.choice([grade, max(0, grade - 1)])
            pool = [x for x in SK.by_tier_grade(min(a.tier, 2), grade)
                    if x[0] not in a.skills]
            if not pool:
                R.cultivate(a, gap)
                return "ไม่มีวิชาให้ฝึก", f"{a.name}หาวิชาใหม่ฝึกไม่ได้ จึงบำเพ็ญต่อ", d
            pv = self.place_of(a)
            if grade == 2 and not (pv and pv[3] in ("ลานฝึก", "สำนัก", "แดนต้องห้าม")):
                R.cultivate(a, gap)
                return "ไม่มีที่ฝึก", f"{a.name}หาที่ฝึกวิชาขั้นสูงไม่ได้ที่{self.place_name(a)}", d
            sk = rng.choice(pool)
            p = C.LEARN_BASE_P + 0.05 * (a.realm - SK.GRADE_REALM_BAR[grade]) \
                - 0.12 * grade - a.decay * 0.05
            if rng.random() > max(0.05, min(0.95, p)):
                a.decay += C.LEARN_BACKFIRE * (0.5 + 0.4 * grade)
                return "ฝึกพลาด", f"{a.name}ฝึก{sk[0]}ไม่สำเร็จ ธาตุไฟเข้าแทรก", d
            a.skills.append(sk[0])
            d["วิชา"] = f"{SK.GRADE_NAME[sk[3]]} · สาย{sk[1]} — {sk[4]}"
            d["ที่ฝึก"] = self.place_name(a)
            req = SK.REQUIREMENTS.get(sk[0])
            if req:
                d["เงื่อนไข"] = req
            if sk[5]:
                d["แก้ทางโกลาหล"] = "วิชานี้แก้ทางเผ่าโกลาหลได้"
            return "สำเร็จ", f"{a.name}ฝึก{sk[0]}สำเร็จ", d
        if k == "ทำนา":
            earn = rng.randint(5, 15)
            a.money[w.tier] = a.money.get(w.tier, 0) + earn
            return "สำเร็จ", f"{a.name}ทำนาได้ผลผลิต", {"เงินที่ได้": earn}
        if k == "ค้าขายทั่วไป":
            earn = rng.randint(20, 50)
            a.money[w.tier] = a.money.get(w.tier, 0) + earn
            return "สำเร็จ", f"{a.name}ค้าขายทั่วไปได้กำไร", {"เงินที่ได้": earn}
        if k == "ตีเหล็กชาวบ้าน":
            earn = rng.randint(10, 30)
            a.money[w.tier] = a.money.get(w.tier, 0) + earn
            a.mats += 1
            return "สำเร็จ", f"{a.name}ตีเหล็กชาวบ้านขาย", {"เงินที่ได้": earn}
        if k == "รักษาชาวบ้าน":
            earn = rng.randint(10, 40)
            a.money[w.tier] = a.money.get(w.tier, 0) + earn
            a.decay = max(0.0, a.decay - 0.1)
            return "สำเร็จ", f"{a.name}รักษาชาวบ้าน", {"เงินที่ได้": earn}
        if k == "ปกป้องชาวบ้าน":
            earn = rng.randint(30, 80)
            a.money[w.tier] = a.money.get(w.tier, 0) + earn
            if rng.random() < 0.2:
                a.mat_stock["ศิลาปราณห้าธาตุ"] = a.mat_stock.get("ศิลาปราณห้าธาตุ", 0) + 1
            return "สำเร็จ", f"{a.name}ปกป้องชาวบ้านจากภัยร้าย", {"เงินที่ได้": earn, "ผลลัพธ์": "ชาวบ้านซาบซึ้ง"}
        if k == "ขูดรีดชาวบ้าน":
            earn = rng.randint(50, 150)
            a.money[w.tier] = a.money.get(w.tier, 0) + earn
            a.decay += 0.2
            if "มารในใจ" not in a.traits:
                a.traits.append("มารในใจ")
            return "สำเร็จ", f"{a.name}ขูดรีดชาวบ้านอย่างโหดเหี้ยม", {"เงินที่ได้": earn, "ผลลัพธ์": "สร้างความแค้น"}


        if k == "ล่าอสูร":
            pv = self.place_of(a)
            eco = self.eco_ratio(a.place)
            n = max(1, round(rng.randint(*C.CORE_PER_HUNT) * eco))
            if pv and pv[4] == "แก่นพลัง":
                n += 2
            a.cores += n
            got = max(1, round(rng.randint(1, 4) * eco))
            a.mats += got
            self.eco_harvest(a.place, got + n * 0.3)

            if rng.random() < 0.4:
                a.mat_stock["โลหิตอสูรกลั่น"] = a.mat_stock.get("โลหิตอสูรกลั่น", 0) + rng.randint(1, 2)
                d["ของพิเศษ"] = "โลหิตอสูรกลั่น"
            if rng.random() < 0.3:
                a.mat_stock["ศิลาปราณห้าธาตุ"] = a.mat_stock.get("ศิลาปราณห้าธาตุ", 0) + rng.randint(1, 3)
                d["ของพิเศษ"] = (d.get("ของพิเศษ", "") + " ศิลาปราณห้าธาตุ").strip()

            if pv and pv[4] in ("แร่", "สมุนไพร"):
                table = PL.ORE_PRICE if pv[4] == "แร่" else PL.HERB_PRICE
                tier_names = [x for x in table
                              if (PL.ORE_PRICE if pv[4] == "แร่" else PL.HERB_PRICE)[x] > 0]
                pick = rng.choice(tier_names)
                a.mat_stock[pick] = a.mat_stock.get(pick, 0) + 1
                self.eco_harvest(a.place, 1.0)
                tail = " (แหล่งนี้เริ่มร่อยหรอ)" if eco < 0.5 else ""
                d["เก็บได้"] = f"{pick} ที่{self.place_name(a)}{tail}"
            a.money[w.tier] = a.money.get(w.tier, 0.0) + n * 2.0
            if rng.random() < 0.10 and a.fate <= 0:
                self.kill(a, "ตายในการล่าอสูร")
                return "ตาย", f"{a.name}ตายในการล่าอสูร", d
            return "ได้แก่นพลัง", f"{a.name}ล่าอสูรได้แก่นพลัง {n} เม็ด", d

        if k == "หลอมค่ายกล":
            pv = self.place_of(a)
            furnace = pv[5] if pv else -1
            if furnace < 0:
                return "ไม่มีเตา", f"{a.name}อยากหลอมค่ายกล แต่{self.place_name(a)}ไม่มีเตาหลอม", d
            if a.mats < 3:
                return "ขาดวัตถุดิบ", f"{a.name}อยากหลอมค่ายกลแต่วัตถุดิบไม่พอ", d
            a.mats -= 3
            if rng.random() > 0.6:
                return "ล้มเหลว", f"{a.name}หลอมค่ายกลล้มเหลว วัตถุดิบสูญเปล่า", d
            recipe = rng.choice(C.ARRAY_WEAPON_KINDS)
            it = self.make_item("อาวุธค่ายกล", w.tier, 1.0, maker=a.cid)
            it.name = recipe
            a.items.append(it.iid)
            d["ได้ของ"] = recipe
            return "สำเร็จ", f"{a.name}หลอม{recipe}สำเร็จ", d

        if k in ("หลอมยา", "หลอมอาวุธ"):
            is_pill = (k == "หลอมยา")
            rk = a.alch_rank if is_pill else a.forge_rank
            if rk < 0:                      # เพิ่งเข้าสาย เริ่มจากฝึกหัด
                rk = 0
                if is_pill:
                    a.alch_rank = 0
                else:
                    a.forge_rank = 0
                d["เข้าสาย"] = CR.ALCHEMY_RANKS[0] if is_pill else CR.FORGE_RANKS[0]
            pv = self.place_of(a)
            furnace = pv[5] if pv else -1
            if furnace < 0:
                return "ไม่มีเตา", f"{a.name}อยากลง{k} แต่{self.place_name(a)}ไม่มีเตาหลอม", d
            d["เตาที่ใช้"] = f"{self.place_name(a)} (เตาระดับ {furnace})"
            if a.mats < CR.CRAFT_MAT_COST or a.cores < C.CRAFT_CORE_COST:
                return "ขาดวัตถุดิบ", f"{a.name}อยากลง{k}แต่วัตถุดิบไม่พอ", d
            a.mats -= CR.CRAFT_MAT_COST
            a.cores -= C.CRAFT_CORE_COST
            table = CR.PILLS if is_pill else CR.WEAPONS
            pool = [x for x in table if CR.can_make(rk, x[1], x[2]) and x[1] <= furnace]
            if not pool:
                return "ทำไม่ได้", f"{a.name}ฝีมือยังไม่ถึงจะลง{k}ชิ้นใด", d
            pool.sort(key=lambda x: -(x[1] * 3 + x[2]))
            recipe = pool[0] if rng.random() < 0.35 else rng.choice(pool)
            lvl = getattr(a, "alchemy" if is_pill else "forge") + C.CRAFT_GAIN
            setattr(a, "alchemy" if is_pill else "forge", lvl)
            p_ok = min(0.92, 0.30 + 0.10 * (rk - recipe[1] * 3 - recipe[2]) + 0.05 * lvl)
            if rng.random() > max(0.05, p_ok):
                return "ล้มเหลว", f"{a.name}หลอม{recipe[0]}ล้มเหลว วัตถุดิบสูญเปล่า", d
            if is_pill:
                it = self.make_item("ยาวิเศษ", recipe[1], 1.0 + recipe[4] * 4, maker=a.cid)
                it.name = recipe[0]
                it.power_desc = recipe[3]
                it.pill_bonus = recipe[4]
            else:
                it = self.make_item("อาวุธวิเศษ", recipe[1], recipe[3], maker=a.cid)
                it.name = recipe[0]
            a.items.append(it.iid)
            d["ได้ของ"] = recipe[0]
            # เลื่อนขั้นช่างเมื่อสั่งสมพอ
            need = (rk + 1) * CR.RANK_XP
            if lvl >= need and rk < 8:
                if is_pill:
                    a.alch_rank += 1
                    d["เลื่อนขั้นช่าง"] = CR.ALCHEMY_RANKS[a.alch_rank]
                else:
                    a.forge_rank += 1
                    d["เลื่อนขั้นช่าง"] = CR.FORGE_RANKS[a.forge_rank]
            return "สำเร็จ", f"{a.name}หลอม{recipe[0]}สำเร็จ", d

        if k == "ค้นแดนลับ":
            frag = next((f for f in self.skill_fragments
                         if f["place"] == a.place and not f["found"]
                         and f["piece"] not in a.fragments.get(f["skill"], [])), None)
            if frag and rng.random() < C.FRAGMENT_FIND_P * (1.0 + a.fate * C.FRAGMENT_FATE_BONUS):
                frag["found"] = True
                got = a.fragments.setdefault(frag["skill"], [])
                got.append(frag["piece"])
                need = C.FRAGMENTS_PER_SKILL
                if len(got) >= need and frag["skill"] not in a.skills:
                    a.skills.append(frag["skill"])
                    sk = SK.SKILL_INDEX.get(frag["skill"])
                    d["ต่อวิชาสำเร็จ"] = f"ต่อชิ้นส่วนครบ {need}/{need} — ได้วิชา「{frag['skill']}」ขั้นสูงสุดทันที"
                    if sk:
                        d["วิชา"] = f"{SK.GRADE_NAME[sk[3]]} · สาย{sk[1]} — {sk[4]}"
                        if sk[5]:
                            d["แก้ทางโกลาหล"] = "วิชานี้แก้ทางเผ่าโกลาหลได้"
                    return "ต่อวิชาโบราณสำเร็จ", \
                        f"{a.name}ต่อเศษจารึกวิชาโบราณครบทุกชิ้น ตรัสรู้「{frag['skill']}」ในทันที!", d
                d["ชิ้นส่วนวิชา"] = f"พบเศษวิชา「{frag['skill']}」ชิ้นที่ {frag['piece']+1}/{need} (มีแล้ว {len(got)}/{need})"
                return "พบชิ้นส่วนวิชา", \
                    f"{a.name}ขุดพบเศษจารึกวิชาโบราณชิ้นหนึ่งซ่อนอยู่ที่{self.place_name(a)}", d
            found = [c for c in self.caches if c.world_id == w.wid and not c.opened
                     and R.seal_left(c, self.day) <= 0]
            if not found:
                return "ไม่พบ", f"{a.name}ออกค้นหาแดนลับแต่ไม่พบร่องรอย", d
            led_kids = {l["subject"] for l in getattr(a, "rumor_leads", ()) if l["kind"] == "แดนลับ"}
            led = [c for c in found if c.kid in led_kids]
            cache = led[0] if led else rng.choice(found)
            tail = " ตามรอยข่าวลือที่เคยได้ยินมา" if led else ""
            if a.race() == "อสูร":
                a.insight += cache.seal * 0.2
                d["วิวัฒนาการ"] = f"{a.name}ดูดซับพลังแดนลับเพื่อวิวัฒนาการก้าวกระโดด"
                self.caches.remove(cache)
                return "ค้นพบ", f"{a.name}พบแดนลับของ{cache.owner_name} กลืนกินแก่นพลัง{tail}", d
            d.update(self.open_cache(a, cache, rng))
            return "ค้นพบ", f"{a.name}เปิดแดนลับของ{cache.owner_name}ได้{tail}", d

        if k == "ซ่อนตัว":
            if a.realm >= C.CACHE_MIN_REALM:
                faked = rng.random() < C.CACHE_TRAP_P
                self.make_cache(a, faked=faked)
                a.hidden = True
                a.money = {}
                d["แดนลับ"] = "แกล้งตายวางกับดัก" if faked else "ผนึกสมบัติทิ้งไว้"
                return "ซ่อนตัว", f"{a.name}หายไปจากโลก สร้างแดนลับผนึกสมบัติไว้", d
            R.cultivate(a, gap)
            return "เก็บตัว", f"{a.name}เก็บตัวเงียบไปพักหนึ่ง", d

        if k == "สงครามเบิกฟ้า":
            up = self.world(w.up) if w.up is not None else None
            if not up or not up.is_closed:
                return "ไม่มีเป้าหมาย", f"{a.name}พร้อมทำสงครามเบิกฟ้า แต่ประตูไม่ได้ปิด", d
            
            damage = a.realm * 5.0
            up.defense_array = max(0.0, up.defense_array - damage)
            d["โจมตีค่ายกล"] = f"พลังค่ายกลแดนเซียนลดลงเหลือ {up.defense_array:.1f}/{up.defense_max}"
            
            if up.defense_array <= 0:
                up.is_closed = False
                d["ประตูปิดกั้นพังทลาย"] = "แดนเซียนถูกเจาะทะลวง! เผ่าโกลาหลสามารถบุกได้แล้ว!"
                return "เปิดสวรรค์", f"{a.name}ทำลายค่ายกลแดนเซียนสำเร็จ! ประตูสวรรค์เปิดออก", d
            else:
                if rng.random() < 0.3:
                    self.kill(a, "ทัณฑ์สวรรค์")
                    return "ตาย", f"{a.name}ถูกทัณฑ์สวรรค์สังหารระหว่างทำสงครามเบิกฟ้า", d
                return "โจมตีสวรรค์", f"{a.name}นำทัพโจมตีค่ายกลสวรรค์ แต่ยังไม่แตก", d

        if k == "ข้ามฟ้า":
            if a.realm < C.ASCEND_MIN_REALM or w.up is None:
                R.cultivate(a, gap)
                return "ยังไม่ถึง", f"{a.name}เพ่งมองฟ้า รู้ว่ายังไม่ถึงเวลา", d
            up = self.world(w.up)
            if up.is_closed and up.tier == 1:
                return "ประตูปิด", f"{a.name}พยายามทะลวงฟ้า แต่ประตูสวรรค์ถูกปิดกั้น!", d
            if rng.random() > C.ASCEND_P:
                self.kill(a, "ดับสูญในด่านข้ามฟ้า")
                return "ตาย", f"{a.name}พ่ายในด่านข้ามฟ้า ดับสูญ", d
            up = self.world(w.up)
            a.drawn = 0.0                       # พลังถูกขนออกจากโลกนี้ถาวร
            a.world_id = up.wid
            a.tier = up.tier
            a.realm = C.ASCEND_RESET_REALM
            a.ascends += 1
            a.peak_tier = max(a.peak_tier, up.tier)
            a.org = None
            d["ข้ามฟ้า"] = f"{w.name} → {up.name} (เริ่มใหม่จากขั้นต่ำสุด)"
            return "ข้ามฟ้า", f"{a.name}ข้ามฟ้าขึ้นสู่{up.name}", d

        if k == "ลงโลกล่าง":
            pv = self.place_of(a)
            gate = PL.GATES.get(pv[0]) if pv else None
            if not gate:
                return "ไม่มีประตู", f"{a.name}ยังหาทางลงโลกล่างไม่เจอ", d
            fee = gate["fee"]
            if fee and a.money.get(w.tier, 0.0) < fee / 1000.0:
                return "ค่าผ่านทางไม่พอ", f"{a.name}จ่ายค่าเปิด{pv[0]}ไม่ไหว", d
            if fee:
                a.money[w.tier] = a.money.get(w.tier, 0.0) - fee / 1000.0
            key = gate["to"]
            dest = next((x for x in self.worlds
                         if x.place_key == key and x.kind != "chaos"), None)
            if dest is None:
                return "ประตูปิด", f"{pv[0]}ไม่เปิดในเวลานี้", d
            a.world_id = dest.wid
            a.tier = dest.tier
            a.realm = max(0, a.realm - gate["push"])
            pl = PL.places_in(dest.place_key)
            a.place = rng.choice(pl) if pl else -1
            a.org = None
            d["ลงโลกล่าง"] = (f"ผ่าน{pv[0]} → {dest.name} "
                              f"(ถูกกดพลัง {gate['push']} ขั้น เหลือ {a.realm_name()})")
            if fee:
                d["ค่าผ่านทาง"] = f"{fee:,} {PL.CURRENCY[min(w.tier, 2)]}"
            return "ลงโลกล่าง", f"{a.name}ก้าวลงสู่{dest.name}ผ่าน{pv[0]}", d

        if k == "ไส้ศึกลงมือ":
            if a.spy_for is None or a.org is None:
                return "ไม่ใช่ไส้ศึก", f"{a.name}ใช้ชีวิตไปตามปกติ", d
            host = self.orgs[a.org]
            master = self.orgs[a.spy_for] if a.spy_for < len(self.orgs) else None
            if master is None or not host.alive:
                return "ไร้นาย", f"{a.name}ขาดการติดต่อกับนายเก่า", d
            mode = rng.choice(["รั่วข่าวแดนลับ", "ก่อวินาศกรรม", "เปิดทางให้ศัตรู"])
            host.grudges[master.oid] = host.grudges.get(master.oid, 0) + 4
            if mode == "รั่วข่าวแดนลับ":
                pool = [c for c in self.caches if c.world_id == w.wid and not c.opened]
                if pool:
                    tgt = rng.choice(pool)
                    tgt.seal = min(tgt.seal, 1.0)     # ผนึกถูกเปิดเผยพิกัด
                    d["ข่าวรั่ว"] = f"พิกัดแดนลับของ{tgt.owner_name}ถึงมือ{master.name}"
            elif mode == "ก่อวินาศกรรม":
                victims = [c for c in self.living_in(w.wid)
                           if c.org == host.oid and c.items and c.cid != a.cid]
                if victims:
                    v = rng.choice(victims)
                    iid = v.items.pop()
                    self.items[iid].condition *= 0.2
                    d["วินาศกรรม"] = f"ของของ{v.name}ถูกทำให้เสียหาย"
            else:
                foes = [c for c in self.living_in(w.wid) if c.org == master.oid]
                if foes:
                    f = rng.choice(foes)
                    victims = [c for c in self.living_in(w.wid) if c.org == host.oid]
                    if victims:
                        v = rng.choice(victims)
                        win, lose, margin = R.resolve_clash(f, v, w, self.items, rng, self.day)
                        res = R.apply_defeat(self, w, win, lose, margin, rng)
                        d["เปิดทาง"] = f"{f.name}เข้าโจมตี{v.name} — {res}"
                        d["margin"] = round(margin, 3)
                        d["winner"] = win.cid
            a.inner += 1.0
            R.add_debt(a, "ทรยศ", host.founder, host.name, self.day)
            return "ไส้ศึกลงมือ", f"{a.name}ลงมือให้{master.name}จากในไส้ของ{host.name}", d

        if k == "ตั้งสำนัก":
            bar = C.ORG_FOUND_REALM_MARA if a.hated() else C.ORG_FOUND_REALM
            if a.realm < bar or a.org is not None:
                return "ผ่านไป", f"{a.name}ใช้ชีวิตไปตามทาง", d
            if rng.random() > (C.ORG_FOUND_P_MARA if a.hated() else C.ORG_FOUND_P):
                return "ผ่านไป", f"{a.name}คิดจะตั้งสำนักแต่ยังไม่ลงมือ", d
            is_mara = a.hated()
            kind = "ลัทธิมาร" if is_mara else rng.choice(C.ORG_KINDS)
            oname = (rng.choice(E.MARA_WORD) + rng.choice(E.MARA_TAIL)) if is_mara \
                else (rng.choice(E.ORG_WORD) + rng.choice(E.ORG_TAIL))
            org = Org(oid=self.nid("o"), kind=kind, name=oname, mara=is_mara,
                      world_id=w.wid, founder=a.cid, founded_day=self.day)
            org.members.append(a.cid)
            a.org = org.oid
            # ลัทธิมารกับสำนักมนุษย์เป็นศัตรูกันแต่ต้น
            for other in self.orgs:
                if other.alive and other.world_id == w.wid and other.mara != is_mara:
                    org.grudges[other.oid] = org.grudges.get(other.oid, 0) + 2
                    other.grudges[org.oid] = other.grudges.get(org.oid, 0) + 2
            self.orgs.append(org)
            for c in self.living_in(w.wid):
                if c.hated() != is_mara:
                    continue          # สำนักมนุษย์ไม่รับมนุษย์มาร และกลับกัน
                if c.org is None and rng.random() < C.ORG_JOIN_P:
                    c.org = org.oid
                    org.members.append(c.cid)
                    if rng.random() < C.SPY_P:
                        c.spy_for = rng.choice([o.oid for o in self.orgs]) if self.orgs else None
            d["ก่อตั้ง"] = f"{kind} {org.name} สมาชิก {len(org.members)} คน" + (" (ลัทธิมนุษย์มาร)" if is_mara else "")
            return "ก่อตั้ง", f"{a.name}ก่อตั้ง{org.name}", d

        if k == "เดินทาง":
            # เดินทางจริงบนกราฟภูมิศาสตร์ (tiandao/geo.py + travel.py) แทนการ teleport ทันทีแบบเดิม —
            # เลือกจุดหมายด้วย logic เดิมเป๊ะ (seek/avoid จากข่าวลือ) แค่ไม่ใส่ a.place ทันที เปลี่ยนเป็น
            # ตั้ง travel_dest/travel_arrival_day แล้วให้ Sim.step() (บล็อกเดียวกับ ch.hidden) จัดการ
            # เดินทางหลายวันจริง + เหตุการณ์ระหว่างทางแทน (ดู sim.py ใกล้ "elif ch.travel_dest >= 0:")
            pl = [p for p in PL.places_in(w.place_key) if p != a.place]
            if pl:
                old = self.place_name(a)
                seek = {l["subject"] for l in getattr(a, "rumor_leads", ()) if l["kind"] == "อุดมสมบูรณ์"}
                avoid = {l["subject"] for l in getattr(a, "rumor_leads", ()) if l["kind"] == "ขาดแคลน"}
                frag_place = {f["fid"]: f["place"] for f in self.skill_fragments}
                seek |= {frag_place[l["subject"]] for l in getattr(a, "rumor_leads", ())
                         if l["kind"] == "ชิ้นส่วนวิชา" and l["subject"] in frag_place}
                seek_pl = [p for p in pl if p in seek]
                safe_pl = [p for p in pl if p not in avoid] or pl
                if seek_pl and rng.random() < 0.6:
                    dest = rng.choice(seek_pl)
                else:
                    dest = rng.choice(safe_pl)
                allow_barrier = getattr(self, "mara_seal_broken", False) or (getattr(self, "mara_seal", 100.0) <= getattr(C, "MARA_SEAL_WEAK_THRESHOLD", 30.0) and rng.random() < getattr(C, "MARA_SEAL_LEAK_P", 0.15))
                days = TR.shortest_path_days(a.place, dest, a.realm, allow_mara_barrier=allow_barrier)
                if days is None:
                    # ไม่ควรเกิดจริง (pl มาจาก world_key เดียวกันซึ่งเชื่อมกันหมดในตัว geo.py เสมอ)
                    # กันไว้เผื่อข้อมูลกราฟผิดพลาดในอนาคต — ไม่เดินทาง แทนที่จะพัง
                    return "ผ่านไป", f"{a.name}ยังหาทางไปไม่เจอ", d
                a.travel_dest = dest
                a.travel_arrival_day = self.day + days
                dest_name = PL.PLACES[dest][0]
                tail = ""
                if dest in frag_place.values() and dest in seek:
                    tail = " (ตามข่าวลือไปตามหาเศษวิชาโบราณ)"
                elif dest in seek:
                    tail = " (ตามข่าวลือว่าที่นี่กลับมาอุดมสมบูรณ์)"
                d["เดินทาง"] = f"{old} → {dest_name} (คาดว่าใช้เวลา {days} วัน)"
                return "ออกเดินทาง", f"{a.name}ออกเดินทางจาก{old}มุ่งหน้าสู่{dest_name}{tail}", d
            return "ผ่านไป", f"{a.name}ออกเดินทาง", d

        if k == "ค้าขาย":
            pv = self.place_of(a)
            mult = 3.0 if pv and pv[3] in ("ตลาด", "เมือง") else 1.0
            gain = rng.uniform(0.5, 3.0) * mult
            # ขายวัตถุดิบที่สะสมไว้ตามราคาประเมิน
            sold = []
            for name, n in list(a.mat_stock.items()):
                price = PL.ORE_PRICE.get(name) or PL.HERB_PRICE.get(name, 0)
                if price and n:
                    gain += price * n / 1000.0
                    sold.append(f"{name} x{n}")
                    a.mat_stock[name] = 0
            a.money[w.tier] = a.money.get(w.tier, 0.0) + gain
            
            if rng.random() < 0.25:
                a.mat_stock["แร่เหล็กทมิฬ"] = a.mat_stock.get("แร่เหล็กทมิฬ", 0) + 1
                d["ซื้อ"] = "แร่เหล็กทมิฬ"
            if rng.random() < 0.2:
                a.mat_stock["ไหมแมงมุมวิญญาณ"] = a.mat_stock.get("ไหมแมงมุมวิญญาณ", 0) + 1
                d["ซื้อ"] = (d.get("ซื้อ", "") + " ไหมแมงมุมวิญญาณ").strip()
                
            if sold:
                d["ขายของ"] = ", ".join(sold[:3])
            d["ที่"] = self.place_name(a)
            return "ค้าขาย", f"{a.name}ค้าขายที่{self.place_name(a)}", d

        if k == "ภัยธรรมชาติ":
            a.decay += 0.7
            if a.realm == 0 and rng.random() < 0.20:
                if a.fate > 0:
                    a.fate -= 1
                    a.near_death += 1
                    return "รอดตายด้วยชะตา", f"{a.name}เกือบตายในภัยพิบัติ", d
                self.kill(a, "ตายในภัยพิบัติ")
                return "ตาย", f"{a.name}ตายในภัยพิบัติ", d
            return "รอดมาได้", f"{a.name}ฝ่าภัยพิบัติมาได้", d

        if k == "กำเนิดทายาท":
            if a.age(self.day) < 16 or t.age(self.day) < 16:
                return "ยังไม่ถึงวัย", f"{a.name}กับ{t.name}ยังไม่ถึงวัยมีทายาท", d
            if a.gender == "ไม่มีเพศ" or t.gender == "ไม่มีเพศ" or a.gender == t.gender:
                return "ล้มเหลว", f"{a.name}และ{t.name}ไม่สามารถมีทายาทร่วมกันได้", d
                
            # ผูกพันธะคู่ครอง
            if a.spouse is None and t.spouse is None:
                a.spouse = t.cid
                t.spouse = a.cid
                
            # เช็คเผ่าพันธุ์ต้องห้าม (มนุษย์กับมาร)
            if a.race() == "มนุษย์" and t.race() == "มาร":
                if "พัวพันกับมาร" not in a.traits: a.traits.append("พัวพันกับมาร")
            elif a.race() == "มาร" and t.race() == "มนุษย์":
                if "พัวพันกับมาร" not in t.traits: t.traits.append("พัวพันกับมาร")
                
            child = self.spawn(w, age_years=0)
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
            p_realm = a.realm + t.realm
            if p_realm > 0:
                child.insight += p_realm * 2.0
                child.refine += p_realm * 2.0
                d["ทายาทผู้ฝึกตน"] = f"{child.name} ได้รับพรสวรรค์มหาศาลตั้งแต่เกิด!"
            
            # โบนัสทายาทผู้ฝึกตน
            p_realm = a.realm + t.realm
            if p_realm > 0:
                child.insight += p_realm * 2.0
                child.refine += p_realm * 2.0
                d["ทายาทผู้ฝึกตน"] = f"{child.name} ได้รับพรสวรรค์มหาศาลตั้งแต่เกิด!"
                v += rng.uniform(-CL.MUTATE, CL.MUTATE)
                blood[kk] = max(0.0, v)
            # สายเลือดวิญญาณเจือจางทุกรุ่น ส่วนที่หายไปกลายเป็นเลือดอสูร
            lost = blood.get("spirit", 0.0) * CL.SPIRIT_DILUTE
            blood["spirit"] = blood.get("spirit", 0.0) - lost
            blood["demon"] = blood.get("demon", 0.0) + lost
            child.blood = R.normalize(blood)
            child.parents = [a.cid, t.cid]
            child.generation = max(a.generation, t.generation) + 1
            child.clan = a.clan if a.clan >= 0 else t.clan
            child.place = a.place
            child.origin = "ทายาทตระกูล" if child.clan >= 0 else "ชาวบ้าน"
            if child.clan >= 0:
                child.name = CL.CLANS[child.clan][0].replace("ตระกูล", "") + rng.choice(E.GIVEN)
            a.children.append(child.cid)
            t.children.append(child.cid)
            a.bonds[t.cid] = a.bonds.get(t.cid, 0) + 2
            d["ทายาท"] = f"{child.name} — {child.race()} รุ่นที่ {child.generation}"
            if lost > 0.01:
                d["สายเลือดเจือจาง"] = f"เลือดวิญญาณลดลง {lost*100:.0f}% กลายเป็นเลือดอสูร"
            clan = CL.CLANS[child.clan][0] if child.clan >= 0 else "ไร้ตระกูล"
            return "กำเนิด", f"{a.name}กับ{t.name}ให้กำเนิด{child.name}แห่ง{clan}", d

        if k == "ให้สัญญา":
            if a.ascends > 0 and t.ascends == 0:
                a.bonds[t.cid] = a.bonds.get(t.cid, 0) + 1 # ไม่ได้ใจคนพื้นเมือง
                d["อคติ"] = f"{t.name} ยังคงมีอคติกับผู้ทะยานข้ามฟ้า"
            else:
                a.bonds[t.cid] = a.bonds.get(t.cid, 0) + 1
                t.bonds[a.cid] = t.bonds.get(a.cid, 0) + 1
            return "ผูกพัน", f"{a.name}ให้สัญญากับ{t.name}", d

        if k == "ถ่ายทอดวิชา":
            t.insight += 0.5
            if a.ascends > 0 and t.ascends == 0:
                t.bonds[a.cid] = t.bonds.get(a.cid, 0) + 0 # อคติ
                d["อคติ"] = f"{t.name} รับวิชาแต่ไม่ซาบซึ้งใจผู้ทะยานข้ามฟ้า"
            else:
                t.bonds[a.cid] = t.bonds.get(a.cid, 0) + 2
            return "ถ่ายทอด", f"{a.name}ถ่ายทอดวิถีให้{t.name}", d

        if k == "หักหลัง":
            dmg = 3
            if a.ascends > 0 and t.ascends == 0:
                dmg *= 2
                d["อคติ"] = f"{t.name} แค้นพวกหน้าใหม่เป็นทวีคูณ"
            t.rivals[a.cid] = t.rivals.get(a.cid, 0) + dmg
            t.bonds.pop(a.cid, None)
            R.add_debt(a, "ทรยศ", t.cid, t.name, self.day)
            d["จิตมาร"] = f"{a.name} +หนี้ค้างคา (รวม {a.inner:.1f})"
            return "หักหลัง", f"{a.name}หักหลัง{t.name}", d

        if k == "สะสางเรื่องเก่า":
            if R.settle_debt(a, t.cid):
                d["จิตมาร"] = f"คลายลงเหลือ {a.inner:.1f}"
                return "สะสาง", f"{a.name}กลับไปสะสางเรื่องค้างคากับ{t.name}", d
            return "ไม่มีอะไรค้าง", f"{a.name}พบ{t.name}อีกครั้ง ไม่มีอะไรค้างคา", d

        if k == "ชิงสมบัติ":
            treas = [i for i in t.items if self.items[i].kind != "ยาวิเศษ"]
            if not treas:
                return "ไม่มีของ", f"{a.name}หมายตาสมบัติของ{t.name} แต่ไม่มีอะไรให้ชิง", d
            win, lose, margin = R.resolve_clash(a, t, w, self.items, rng)
            res = R.apply_defeat(self, w, win, lose, margin, rng)
            d["margin"] = round(margin, 3)
            d["winner"] = win.cid
            if win is a and lose.alive:
                iid = treas[0]
                t.items.remove(iid)
                a.items.append(iid)
                d["ชิงได้"] = self.items[iid].name
            lose.rivals[win.cid] = lose.rivals.get(win.cid, 0) + 2
            return res, f"{a.name}ชิงสมบัติจาก{t.name} — {lose.name}เป็นฝ่ายเสีย", d

        if k == "สงครามสำนัก":
            if a.org is None or t.org is None or a.org == t.org:
                return "ล้มเหลว", f"{a.name}พยายามก่อสงครามแต่เป้าหมายไม่ชัดเจน", d
            
            org_a = self.orgs[a.org]
            org_b = self.orgs[t.org]
            if not org_a.alive or not org_b.alive:
                return "ล้มเหลว", "สำนักล่มสลายไปแล้ว สงครามจึงไม่เกิด", d
                
            # รวมพลังหมาหมู่
            a_members = [self.cast[c] for c in org_a.members if self.cast[c].alive and self.cast[c].world_id == w.wid]
            b_members = [self.cast[c] for c in org_b.members if self.cast[c].alive and self.cast[c].world_id == w.wid]
            
            if not a_members or not b_members:
                return "ไร้กำลัง", "มีสำนักที่ไม่มีกำลังคนในโลกนี้เลย", d
                
            power_a = sum(R.power(m, w, self.items) for m in a_members)
            power_b = sum(R.power(m, w, self.items) for m in b_members)
            
            win_org, lose_org = (org_a, org_b) if power_a >= power_b else (org_b, org_a)
            win_mems, lose_mems = (a_members, b_members) if power_a >= power_b else (b_members, a_members)
            
            # คนแพ้โดนปล้นและอาจตาย
            loot_money = 0
            casualties = 0
            for m in lose_mems:
                m_money = m.money.get(w.tier, 0)
                loot = int(m_money * 0.5)
                m.money[w.tier] = m_money - loot
                loot_money += loot
                
                # โอกาสตาย 30% หรือรอดด้วยชะตา
                if rng.random() < 0.3:
                    if m.fate > 0:
                        m.fate -= 1
                    else:
                        m.alive = False
                        m.place = None
                        m.org = None
                        casualties += 1
                        
            # ผู้รอดชีวิตจากสำนักที่แพ้กลายเป็นผู้พเนจร, สำนักล่มสลาย
            lose_org.alive = False
            for c in self.cast:
                if c.org == lose_org.oid:
                    c.org = None
                    c.origin = "ผู้พเนจร"
                    
            # แบ่งของให้ผู้ชนะ
            if loot_money > 0 and win_mems:
                share = loot_money // len(win_mems)
                for m in win_mems:
                    m.money[w.tier] = m.money.get(w.tier, 0) + share
                    
            d["ผู้ชนะ"] = win_org.name
            d["ผู้แพ้"] = lose_org.name
            d["พลังรวมชนะ"] = int(max(power_a, power_b))
            d["พลังรวมแพ้"] = int(min(power_a, power_b))
            d["ผู้เสียชีวิต"] = casualties
            d["เงินปล้น"] = loot_money
            
            if lose_org.oid in win_org.grudges: del win_org.grudges[lose_org.oid]
            if win_org.oid in lose_org.grudges: del lose_org.grudges[win_org.oid]
            
            return "จบสิ้น", f"สงครามแตกหัก! {win_org.name} กวาดล้าง {lose_org.name} จนล่มสลาย", d


        # ประลอง / ล้างแค้น
        win, lose, margin = R.resolve_clash(a, t, w, self.items, rng)
        lethal = C.DEATH_MARGIN * (C.DUEL_LETHAL_MULT if k == "ประลอง" else 1.0)
        res = R.apply_defeat(self, w, win, lose, margin, rng, lethal)
        if k == "ล้างแค้น" and win is a:
            R.settle_debt(a, t.cid)
        dmg = 2 if k == "ล้างแค้น" else 1
        if win.ascends > 0 and lose.ascends == 0 and k in ("ชิงสมบัติ", "ล้างแค้น", "ประลอง"):
            dmg *= 2
            d["อคติ"] = f"{lose.name} เกลียดพวกหน้าใหม่ที่กำเริบเสิบสาน"
        lose.rivals[win.cid] = lose.rivals.get(win.cid, 0) + dmg
        d["ผล"] = f"{win.name}({win.realm_name()}) เหนือกว่า {lose.name}({lose.realm_name()})"
        d["margin"] = round(margin, 3)
        d["winner"] = win.cid
        verb = {"ตาย": f"{lose.name}ดับดิ้น", "รอดตายด้วยชะตา": f"{lose.name}รอดด้วยชะตา",
                "พ่ายแพ้": f"{lose.name}เป็นฝ่ายพ่าย"}.get(res, f"{lose.name}{res}")
        return res, f"{a.name}{k}กับ{t.name} — {verb}", d

    def emit(self, world, kind, a, t, tags, outcome, text, gap, d):
        self.seq += 1   # เดิม increment ที่ step() ครั้งเดียวต่อทิก แต่ step()เดียวเรียก emit() ได้
                         # มากกว่า 1 ครั้ง (เช่น เหตุการณ์ผลพวง) ทำให้ seq ซ้ำกันได้ — ย้ายมาที่นี่
                         # ให้ seq เป็น ID ไม่ซ้ำจริงต่อหนึ่ง Event เสมอ (พบจาก narrative_factory
                         # Phase E ที่ scene_id ชนกันเพราะ seq ซ้ำ)
        e = Event(seq=self.seq, day=self.day, gap_days=gap, world_id=world.wid,
                  era=world.era, kind=kind, actor=a.cid if a else -1,
                  target=t.cid if t else None, tags=list(tags),
                  outcome=outcome, text=text, deltas=d, place=a.place if a else -1, realm=a.realm if a else 0)
        self.log.append(e)
        self.event_bus.publish(e, self)
        return e

    def run(self, n):
        for _ in range(n):
            if self.step() is None:
                break
        return self
