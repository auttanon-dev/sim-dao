# -*- coding: utf-8 -*-
import heapq
import math
import random

from . import config as C
from . import events as E
from . import branches as BR
from . import portals as PORT
from . import worldtree as WT
from . import paths as PATHS
from . import crises as CRISES
from . import rules as R
from .models import Cache, Character, Event, Item, Org, World
from .treasures import TREASURES, BURST_MULT
from . import skills as SK
from . import crafting as CR
from . import materials as MAT
from . import physics as PHYS
from . import elements as EL
from . import economy as EC
from . import geo as GEO
from . import noise as NZ
from . import places as PL
from . import clans as CL
from . import intent as IN
from . import travel as TR
from . import settlement as SETTLE
from . import chronicle as CH
from . import seasons as SEASONS
from . import emotions as EM
from . import body as BODY
from . import food as FOOD
from . import wages as WAGES
from . import guardians as GUARD
from .ai import BrainManager, EventBus
from .console import safe_print

# โอกาสพบกันตามระยะทาง คิดครั้งเดียวต่อสถานที่ต้นทาง; จำนวนใช้ PL.PLACES ปัจจุบันแบบ dynamic
# อยู่ระดับโมดูล ไม่ใช่บน Sim เพราะ Sim ถูก pickle ทั้งก้อน (ดู persist.py) ไม่ควรพกแคชไปด้วย
_REACH_CACHE = {}


def _reach_from(place):
    """place ปลายทาง -> โอกาสที่คนที่อยู่ตรงนั้นจะ 'พบได้' จาก place ต้นทางนี้ (0..1)"""
    cached = _REACH_CACHE.get(place)
    if cached is None:
        scale = max(1e-6, C.SOCIAL_RANGE)
        cached = {pl: math.exp(-d / scale) for pl, d in TR.distances_from(place).items()}
        _REACH_CACHE[place] = cached
    return cached


def _auction_q(value: float) -> float:
    """ปัดราคาประมูล **ลง** ให้เหลือทศนิยมเท่าที่บันทึกแสดงจริง (C.AUCTION_PRICE_DP)

    งานประมูลมีตัวเลขสามที่ต้องเป็นค่าเดียวกันเสมอ: เงินที่ย้ายมือจริง ตัวเลขใน deltas
    และราคาที่เขียนในบันทึก ถ้าโอนด้วยทศนิยมเต็มแต่รายงานแค่หนึ่งตำแหน่ง บัญชีของเจ้าภาพกับ
    ผู้ชนะจะไม่ตรงกับราคาที่ประกาศ (วัดจริง: ต่างกัน 0.0467 หน่วยปราณ) การตรวจบัญชีย้อนหลัง
    จากบันทึกจึงทำไม่ได้เลย

    ปัดลงไม่ใช่ปัดใกล้สุด เพราะราคาต้องไม่ทะลุเพดานสองอันของกติกาวิกเครย์:
    ต้องไม่เกินมูลค่าในใจของผู้ชนะ และไม่เกินราคาอันดับสองคูณก้าวราคา
    """
    step = 10.0 ** C.AUCTION_PRICE_DP
    return math.floor(max(0.0, value) * step) / step


class Sim:
    def __init__(self, seed=0, tiers=3):
        self.rng = random.Random(seed)
        self.seed = seed
        self.day = 0
        self.last_day = 0
        self.world_tick_day = 0   # ใบนัดถัดไปของนาฬิกาโลก (ดู _world_tick)
        self.eco_day = 0          # วันล่าสุดที่คิดการฟื้นของทรัพยากรไปแล้ว (ดู _advance_eco)
        self.food_day = 0         # วันล่าสุดที่ยุ้งฉางคิดไปแล้ว (ดู tiandao/food.py)
        self.granary = {}         # place_idx -> สำรับในยุ้งฉางของที่นั้น
        self.food_stats = FOOD.new_stats()
        self.market_till = {}     # (wid, place) -> ทองที่คนใช้จ่ายรอจ่ายเป็นค่าแรง (tiandao/wages.py)
        self.farm_till = {}       # (wid, place) -> ค่าข้าวที่รอจ่ายให้คนผลิตของที่นั้น
        self.wage_stats = WAGES.new_stats()
        self.guardian_stats = GUARD.new_stats()
        self.seq = 0
        self.cast = []
        self.used_names = set()          # ชื่อที่ถูกใช้แล้วทั้งจักรวาล (unique_name)
        self.alive_cids = set()   # cid ของคนที่ยังมีชีวิตอยู่ตอนนี้ — self.cast โตขึ้นเรื่อยๆ ไม่มีวันหด
                                    # (ต้องคง index==cid ไว้เสมอ ห้ามลบออกจาก cast) ดังนั้น living()/
                                    # living_in() ต้องสแกนจากตัวนี้แทน ไม่งั้นจะช้าลงเรื่อยๆ ตามอายุซิม
                                    # (สแกนคนตายสะสมทั้งหมดซ้ำทุกครั้ง — บั๊กจริงที่เจอตอนรัน --llm scale
                                    # ยาวหลายแสนเหตุการณ์ ยิ่งรันนานยิ่งช้าลงจนแทบไม่ขยับ)
        self._alive_ver = 0
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
        self.apex_blessings = {}  # cid ผู้สูงสุด -> {ชนิดสายเลือด: ความแรง}; มีเฉพาะผู้ที่ยังครองขั้น

        # Cultivator Brain v2 (ai/) — Event Bus + CharacterBrain skeleton, ดู tiandao/ai/__init__.py
        self.event_bus = EventBus()
        self.brain_manager = BrainManager()
        self.event_bus.subscribe(self.brain_manager.on_event)
        # Decision Engine แบบ Hybrid (tiandao/decision) — ปิดเป็นค่าเริ่มต้น เปิดด้วย
        # C.DECISION_ENGINE_ON = True, run.py --decision หรือ tiandao.decision.attach(sim)
        self.decision_engine = None
        if getattr(C, "DECISION_ENGINE_ON", False):
            from .decision import attach as _attach_decision
            _attach_decision(self)

        # มหาผนึกสะกดหมื่นมาร (แดนลับรอยแยกเชื่อมโลกมนุษย์-แดนมาร)
        self.mara_seal = getattr(C, "MARA_SEAL_INITIAL", 100.0)
        self.mara_seal_broken = False
        self.mara_seal_notified_weak = False

        # เจ้าโกลาหล: พลังที่มันสะสมจากความตายทั่วจักรวาลระหว่างที่สลายอยู่ กับผนึกที่หยุดการสะสมนั้น
        self.lord_pool = 0.0
        self.lord_seal = 0.0
        self.lord_seals_made = 0

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
            # แดนใต้พิภพ (นรก) และแดนวังมังกรใต้สมุทร — เป็นเพื่อนบ้านของโลกมนุษย์เช่นกัน
            # คนเป็นเดินทางไปได้ ส่วนคนตายยังคืนพลังให้ฟ้าตามเดิม ไม่ได้ถูกส่งลงใต้พิภพ
            ("abyss", getattr(C, "ABYSS_WORLD_NAME", "แดนใต้พิภพ")),
            ("ocean", getattr(C, "OCEAN_WORLD_NAME", "แดนวังมังกรใต้สมุทร")),
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

        # แดนเซียนสาขา — ใช้ผังภูมิศาสตร์ร่วมกับแดนเซียนหลัก (place_key = 1) ดูเหตุผลใน branches.py
        self.branch_wids = []
        if tiers > 1 and C.BRANCH_REALMS > 0:
            up_wid = self.worlds[2].wid if tiers > 2 else None
            from . import realm_map as RM
            for bi, b in enumerate(BR.build(C.BRANCH_REALMS)):
                bw = World(wid=len(self.worlds), name=b.name, tier=1, kind="mortal")
                bw.place_key = RM.realm_key(bi)   # แผนที่ของตัวเอง แยกขาดจากแดนอื่น (realm_map.py)
                bw.up = up_wid
                bw.skill_line = b.skill_line      # สายวิชาประจำแดน — ทำให้แต่ละสาขาผลิตคนคนละแบบ
                bw.resource = C.REALM_RESOURCE_INIT   # คลังทรัพยากรของแดน ใช้สร้างประตูมิติ
                bw.branch_origin = b.origin
                bw.lateral.append(self.worlds[1].wid)
                self.worlds[1].lateral.append(bw.wid)
                self.worlds.append(bw)
                self.branch_wids.append(bw.wid)

        for w in self.worlds:
            if w.kind == "chaos":
                continue
            if getattr(w, "skill_line", None):
                n = C.BRANCH_CAST                 # แดนสาขา — สำนักที่ขยายเป็นดินแดน ไม่ใช่อารยธรรม
            else:
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
        gender = rng.choice(["ชาย", "หญิง"]) if blood.get("demon", 0) < 0.8 else rng.choice(["ชาย", "หญิง", "ไม่มีเพศ"])
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
        if world.tier == 1 and hasattr(C, "CITIES") and C.CITIES:
            city = rng.choice(C.CITIES)
            city_id = city["id"]
        ch = Character(
            cid=self.nid("c"),
            name=name,
            world_id=world.wid, dao=dao, dao_tags=list(C.DAO_POOL[dao]),
            born_day=self.day - age_years * 365,
            natural_lifespan=rng.randint(C.MORTAL_LIFESPAN_MIN, C.MORTAL_LIFESPAN_MAX),
            blood=blood,
            fate=rng.randint(C.FATE_MIN, C.FATE_MAX), origin=origin,
            gender=gender, fear=fear, greed=greed, compassion=compassion,
            ambition=ambition, loyalty=loyalty,
            body_seed=self.seed,        # ร่างกายสร้างกลับมาได้จาก (seed, cid) — ดู tiandao/body/
            body_age=float(age_years),  # อายุทางสรีรวิทยาเดินต่อด้วย body.adaptation.tick
            # เผ่าวิญญาณศักดิ์สิทธิ์: เดิม `is_spirit` ไม่เคยถูกตั้งเป็น True ที่ไหนเลยทั้งโปรเจกต์
            # สายเลือดวิญญาณมีอยู่จริง (วัดจริง 51 คนเลือดบริสุทธิ์ จาก 1,253 คน) แต่ "เผ่า" ในเชิง
            # พฤติกรรมไม่เคยมีอยู่ — บล็อกบัญชาสวรรค์ที่เขียนไว้จึงไม่เคยทำงานสักครั้ง
            is_spirit=blood.get("spirit", 0.0) >= C.SPIRIT_PURE_AT,
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
        # ใจของคนคนนี้ — สุ่มหลังนิสัย/วิถี/ลักษณะพิเศษถูกตั้งครบแล้ว เพราะ roll() อ่านค่าพวกนั้น
        # ไปกำหนดทิศของอารมณ์และปรารถนา (คนขลาดกลัวจะ 'กลัว' สูงจริง ไม่ขัดกันเอง)
        ch.birth_wid = world.wid
        EM.roll(ch, rng)
        # ธาตุประจำตัว — สืบจากพ่อแม่ก่อน ที่เหลือคือสิ่งที่ฟ้าให้มา (ดู tiandao/elements.py)
        _par = [self.cast[i] for i in getattr(ch, "parents", ()) if 0 <= i < len(self.cast)]
        EL.roll(ch, rng, _par)
        ch.name = self.unique_name(ch.name)
        ch.last_day = self.day
        self.cast.append(ch)
        self.alive_cids.add(ch.cid)
        self._alive_ver = getattr(self, "_alive_ver", 0) + 1
        self._world_counts_dirty = True
        world.n_alive += 1
        if ch.realm == 0:
            world.n_mortal += 1
        self.apply_bloodline_buff(ch)
        self.schedule(ch, rng.randint(30, 900))
        return ch

    def schedule(self, ch, gap):
        heapq.heappush(self.queue, (self.day + max(1, gap), ch.cid))

    def _childhood_turn(self, child, world, elapsed, rng):
        """เดินหนึ่งปีวัยเด็กโดยไม่เปิดการกระทำของผู้ใหญ่.

        เด็กยังปรากฏในโลกและอาจได้รับผลจากภัยระดับโลก แต่เทิร์นส่วนตัวมีเพียงการเติบโต
        การเรียนรู้ และครอบครัว บันทึกย่อถูกเก็บกับตัวละครเพื่อนำไปสร้างชีวประวัติภายหลัง
        โดยไม่ต้องรักษา ``sim.log`` ทั้งก้อนตลอดอายุโลก
        """
        age = max(0, child.age(self.day))
        parents = [self.cast[cid] for cid in getattr(child, "parents", ())
                   if 0 <= cid < len(self.cast)]
        living_parents = [p for p in parents if p.alive]
        if living_parents:
            home = "และ".join(p.name for p in living_parents[:2])
            if age <= 2:
                outcome = "ได้รับการเลี้ยงดู"
                text = f"{child.name}เติบโตในอ้อมอกของ{home}"
            elif age <= 6:
                outcome = "เรียนรู้โลก"
                text = f"{child.name}วัย {age} ปี เรียนรู้ผู้คนและสถานที่รอบตัวโดยมี{home}คอยดูแล"
            elif age <= 10:
                outcome = "ช่วยครอบครัว"
                text = f"{child.name}วัย {age} ปี เริ่มช่วยงานและเรียนรู้วิถีชีวิตจาก{home}"
            else:
                outcome = "เตรียมเติบใหญ่"
                text = f"{child.name}วัย {age} ปี ฝึกความรับผิดชอบและค้นหาวิถีของตนภายใต้การดูแลของ{home}"
        else:
            if parents:
                outcome = "เติบโตโดยไร้ผู้ปกครอง"
                text = f"{child.name}วัย {age} ปี เติบโตต่อมาโดยไม่มีบิดามารดาอยู่เคียงข้าง"
            else:
                outcome = "เติบโต"
                text = f"{child.name}วัย {age} ปี เรียนรู้การใช้ชีวิตจากผู้คนรอบตัว"

        event = self.emit(world, "เติบโต", child, None, ["วัยเด็ก"], outcome,
                          text, elapsed, {"อายุ": f"{age} ปี"})
        history = getattr(child, "childhood", None)
        if not isinstance(history, list):
            history = child.childhood = []
        if not any(h.get("age") == age for h in history if isinstance(h, dict)):
            history.append({"day": self.day, "age": age, "text": text,
                            "place": child.place, "outcome": outcome, "seq": event.seq})
            del history[:-14]
        # กลับมาอีกครั้งใกล้วันเกิดถัดไป จึงมีประวัติพออ่านแต่ไม่ท่วมคิวโลก
        next_birthday = child.born_day + (age + 1) * 365
        self.schedule(child, max(30, next_birthday - self.day + rng.randint(0, 30)))
        return event

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
        if getattr(world, "skill_line", None):
            # แดนสาขาโตได้ไม่เกินขนาดของตัวเอง — ถ้าปล่อยให้เติมถึง CAST_SIZE เหมือนแดนหลัก
            # 108 สาขาจะกลายเป็นประชากร 16,200 คน (วัดจริง: พุ่งจาก 3,944 เป็น 9,751 ใน 5 ปี
            # แล้วยังไม่หยุด) ซึ่งกลบแดนหลักจนโลกทั้งใบเป็นเรื่องของสาขาไปหมด
            target = C.BRANCH_CAST
        elif world.wid == 0:
            target = C.HOME_CAST                     # เวทีหลัก — คนต้องแน่นพอจะมีเรื่องกัน
        else:
            target = C.CAST_SIZE if world.kind == "mortal" else C.CAST_SIZE // 3
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
        self._world_counts_dirty = True
        self._world_move_ver = getattr(self, "_world_move_ver", 0) + 1

    # ------------------------------------------------------------ ตาย
    def kill(self, ch, cause, killer=None, natural=False):
        if not ch.alive:
            return
        ch.alive = False
        ch.death_day = self.day
        ch.death_cause = cause
        if ch.is_lord and ch.hidden:
            # มันสลายไปแล้ว ฆ่าซ้ำไม่ได้ — วัดจริง 150 ปี: "ยุคล่ม" ของแดนที่มันสังกัดเรียก kill()
            # ใส่มันทั้งที่มันสลายอยู่ ซึ่งรีเซ็ตพลังที่มันสะสมมากลับเป็น 0 ให้โลกฟรีๆ
            ch.alive = True
            ch.death_day = None
            ch.death_cause = ""
            return
        if ch.is_lord:
            # เจ้าโกลาหล **ฆ่าได้** แต่ไม่มีอายุขัย — ที่ถูกฆ่าคือร่างที่ก่อขึ้น มันสลายกลับเป็นความ
            # โกลาหล แล้วก่อร่างใหม่เมื่อสะสมพลังจากความตายทั่วจักรวาลได้ครบ ไม่ใช่เมื่อครบเวลา
            # ที่หมอนสุ่มไว้ล่วงหน้า — ของเดิมตั้ง return_day = day + randint(2000, 12000) ตั้งแต่
            # วินาทีที่มันตาย แปลว่าโลกจะทำอะไรก็ไม่มีผล วันคืนกลับถูกล็อกไว้แล้ว การฆ่ามันจึงไม่มี
            # ความหมายเชิงกลไกเลยนอกจากพักหน้าจอ และการ "ส่งคนไปผนึก" ก็ไม่มีอะไรให้ผนึก
            ch.alive = True
            ch.death_day = None
            ch.death_cause = ""
            ch.hidden = True
            ch.decay = 0.0
            ch.return_day = 0
            self.lord_pool = 0.0
            cw = self.world(self.chaos_wid) if self.chaos_wid is not None else self.worlds[0]
            self.emit(cw, "เจ้าโกลาหลสลาย", ch, killer, ["ทำลาย", "ความตาย"], "สลายเป็นโกลาหล",
                      f"{ch.name}ถูกสังหารจนร่างสลายกลับเป็นความโกลาหล "
                      f"จะก่อร่างใหม่ได้ต่อเมื่อสะสมพลังจากความตายทั่วจักรวาลจนครบ", 0,
                      {"ผู้ลงมือ": killer.name if killer else "ไม่ปรากฏ",
                       "เหตุ": cause,
                       "สลายมาแล้ว": f"{ch.lord_returns} ครั้ง",
                       "พลังที่ต้องสะสมใหม่": f"0/{C.LORD_POOL_TARGET:,.0f}"})
            # Its existing turn (or the current actor's normal reschedule) wakes it.
            # Adding another turn here duplicates the lord's scheduler entries on
            # every defeat and makes it act increasingly often after returning.
            return
        # ทุกความตายในจักรวาลคือพลังที่ไหลกลับสู่ฟ้า และเผ่าโกลาหลแย่งส่วนแบ่งนั้นไป — ตราบใดที่
        # เจ้าโกลาหลยังสลายอยู่และยังไม่ถูกผนึก ความตายทุกครั้งคือการนับถอยหลังสู่การกลับมาของมัน
        lord = self.cast[self.lord_cid] if self.lord_cid is not None else None
        if lord is not None and lord.hidden and getattr(self, "lord_seal", 0.0) <= 0.0:
            gain = C.LORD_POOL_PER_DEATH * (1.0 + C.LORD_POOL_PER_REALM * ch.realm)
            if not natural:
                gain *= C.LORD_POOL_VIOLENT_X
            self.lord_pool = getattr(self, "lord_pool", 0.0) + gain
        if C.FOOD_ENABLED:
            FOOD.on_death(self, ch)
        if C.GUARDIANS_ENABLED:
            GUARD.on_death(self, ch)
        self.alive_cids.discard(ch.cid)
        self._alive_ver = getattr(self, "_alive_ver", 0) + 1
        self._world_counts_dirty = True
        if ch.cid in getattr(self, "apex_blessings", {}):
            self.apex_blessings.pop(ch.cid, None)
            self.refresh_bloodline_buffs()
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
            if ch.sentient and not ch.is_lord:
                self.raise_corpse(killer, ch, self.rng)
            self.org_avenge(ch, killer)
            if ch.clan >= 0 and killer.clan != ch.clan:
                for m in self.living():
                    if m.clan == ch.clan:
                        m.rivals[killer.cid] = m.rivals.get(killer.cid, 0) + 2
        elif ch.realm >= C.CACHE_MIN_REALM or any(
                self.items[i].legend for i in ch.items):
            # สมบัติฟ้าดินที่มีชื่อไม่มีวันสูญหาย เจ้าของตายก็ถูกผนึกรอผู้มีวาสนาคนต่อไป
            self.make_cache(ch, faked=False)

        # ผู้ฝึกสายวัฏจักร: ร่างตายแล้ว แต่ดวงจิตไปเกิดใหม่ — ทำหลังกระบวนการตายครบทุกอย่าง
        if ch.sentient and not ch.is_lord and self._knows_cycle(ch):
            self.reincarnate(ch)

    # ------------------------------------------------------------ หุ่นเชิด
    def raise_corpse(self, killer, victim, rng):
        """สายเชิดศพ: ฆ่าคนแล้วปลุกซากขึ้นมาเป็นหุ่นของตน

        ราคาของวิชานี้ไม่ใช่วัตถุดิบ แต่เป็น **กรรมค้างคา** — ตรงกับกฎของโลกที่ว่าการฆ่าต้องมีราคา
        และมนุษย์มารเป็นที่รังเกียจ ผู้ฝึกสายนี้จึงแกร่งขึ้นได้ฟรีในสนามรบ แต่สะสมจิตมารเร็วกว่าใคร
        ซึ่งย้อนมาเล่นงานตอนข้ามขั้นเอง
        """
        if R.puppet_line_grade(killer, "เชิดศพ") < 0:
            return
        cap = R.puppet_cap(killer)
        if killer.puppets >= cap or rng.random() >= C.PUPPET_RAISE_P:
            return
        killer.puppets += 1
        killer.puppet_kind = "เชิดศพ"
        R.add_debt(killer, "เชิดศพ", victim.cid, victim.name, self.day)
        killer.karmic_debt = getattr(killer, "karmic_debt", 0) + C.CORPSE_PUPPET_DEBT
        self.emit(self.world(killer.world_id), "เชิดซากเป็นหุ่น", killer, victim,
                  ["ความตาย", "ทำลาย"], "ปลุกซากสำเร็จ",
                  f"{killer.name}ปลุกซากของ{victim.name}ที่ยังไม่ทันเย็นให้ลุกขึ้นเดินตามคำสั่ง "
                  f"ร่างที่เคยเป็นคนกลายเป็นหุ่นเชิดตนหนึ่งของมัน", 0,
                  {"หุ่นในมือ": f"{killer.puppets}/{cap} ตน",
                   "ราคาที่จ่าย": f"จิตมารหนักขึ้น {C.CORPSE_PUPPET_DEBT:.0f}",
                   "ชนิดหุ่น": "ซากผู้บำเพ็ญ"})

    def build_puppet(self, a, w, rng, d):
        """สายหุ่นกล: หลอมหุ่นขึ้นมาเองจากแร่และแก่นพลังอสูร

        คืน tuple แบบเดียวกับ resolve() ถ้าลงมือจริง คืน None ถ้าไม่เข้าเงื่อนไข (ให้ไปทำค่ายกลตามเดิม)
        """
        g = R.puppet_line_grade(a, "หุ่นกล")
        if g < 0:
            return None
        cap = R.puppet_cap(a)
        if a.puppets >= cap:
            return None
        need_cores, need_mats = 1 + g, 2 + g
        if a.cores < need_cores or a.mats < need_mats:
            d["ยังขาด"] = f"แก่นพลัง {need_cores} · วัตถุดิบ {need_mats}"
            return ("ขาดวัตถุดิบ", f"{a.name}อยากหลอมหุ่นกล แต่ยังขาด{d['ยังขาด']}", d)
        a.cores -= need_cores
        a.mats -= need_mats
        d["วัตถุดิบที่ใช้"] = f"แก่นพลังอสูร {need_cores} · แร่ {need_mats}"
        if rng.random() >= C.PUPPET_CRAFT_P:
            return ("ล้มเหลว", f"{a.name}หลอมหุ่นกลล้มเหลว หุ่นแตกคามือ วัตถุดิบสูญเปล่า", d)
        a.puppets += 1
        if not a.puppet_kind:
            a.puppet_kind = "หุ่นกล"
        d["หุ่นในมือ"] = f"{a.puppets}/{cap} ตน"
        name = ("หุ่นไม้ชักใย", "หุ่นสัมฤทธิ์ไร้ความเจ็บ", "หุ่นเหล็กพันมือ")[min(g, 2)]
        return ("หลอมสำเร็จ", f"{a.name}หลอม{name}ขึ้นมาได้อีกหนึ่งตน เชิดมันสู้แทนตัวได้", d)

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
        for cid in org.members:
            m = self.cast[cid]
            if m.alive and self.rng.random() < C.ORG_AVENGE_P:
                m.rivals[killer.cid] = m.rivals.get(killer.cid, 0) + 3

    # ------------------------------------------------------------ ของ / แดนลับ
    def make_item(self, kind, tier, grade, maker=None):
        it = Item(iid=self.nid("i"), kind=kind, tier=tier, grade=grade, maker=maker)
        # config.ITEM_GRADES นิยามชื่อชั้นไว้ 4 ชั้นแต่ไม่เคยถูกใช้ — ของจึงชื่อว่า "อาวุธชั้น 3"
        gname = C.ITEM_GRADES[min(len(C.ITEM_GRADES) - 1, tier + (1 if grade >= 2.0 else 0))]
        it.name = f"{kind}{gname}"
        if kind == "ยาวิเศษ":
            it.lifespan_bonus = CR.longevity_years(it.name, tier, grade)
        self.items[it.iid] = it
        return it

    def stash_relic(self, ch, rng):
        """ของที่ผู้เก็บตัวทิ้งไว้ในแดนลับ — คัมภีร์หรือยันต์ (config.MANUALS_AND_TALISMANS)

        ตรงกับกฎของโลกที่ว่า "คนระดับสูงที่ไปต่อไม่ได้มักหาที่ซ่อนตัว ทำแดนลับ ทิ้งสมบัติปิดผนึกไว้"
        ก่อนหน้านี้ตารางคัมภีร์/ยันต์ถูกนิยามไว้แต่ไม่มีทางใดในเกมที่จะได้มันมาเลย
        """
        cats = list(C.MANUALS_AND_TALISMANS.items())
        if not cats:
            return None
        cat, names = rng.choice(cats)
        kind = C.TALISMAN_KIND if cat.startswith("ยันต์") else "คัมภีร์"
        it = self.make_item(kind, min(ch.tier, 2), 1.0 + 0.5 * ch.realm / 9.0, maker=ch.cid)
        it.name = rng.choice(names).split(" (")[0]
        return it

    def sect_territory(self, org):
        """อาณาเขตของสำนัก = ผลรวมความหนาแน่นปราณของที่ที่ศิษย์ยืนอยู่จริง

        จงใจไม่เพิ่ม field "ดินแดนที่ครอง" ให้ Org เพราะข้อมูลนั้นมีอยู่แล้วในตำแหน่งของ
        สมาชิก และการนิยามแบบนี้ทำให้ **การแผ่อิทธิพลเป็นผลของพฤติกรรม ไม่ใช่ตัวเลขที่ตั้ง**
        สำนักที่ส่งศิษย์ไปยึดหุบเขาปราณหนาก็รวยขึ้นจริง สำนักที่หดตัวอยู่ในสำนักก็จนลงเอง
        นับที่ละแห่งครั้งเดียว (ส่งคนไปกระจุกที่เดิมร้อยคนไม่ได้อาณาเขตเพิ่ม) และจำกัดจำนวน
        แห่งไว้ ไม่งั้นสำนักที่สมาชิกกระจายทั่วแดนจะกลายเป็นเจ้าของทั้งโลกโดยไม่ต้องรบ
        """
        w = self.world(org.world_id)
        seen = {}
        cast_len = len(self.cast)
        for cid in org.members:
            if not (0 <= cid < cast_len):
                continue
            m = self.cast[cid]
            if not m.alive or m.place is None or m.place < 0:
                continue
            if m.place not in seen:
                seen[m.place] = self.qi_density(m.place, w)
        if not seen:
            return 0.0
        top = sorted(seen.values(), reverse=True)[:C.SECT_TERRITORY_CAP]
        return float(sum(top))

    def sect_mine(self, org):
        """สำนักขุดปราณจากอาณาเขตของตนเข้าคลัง แล้วตกผลึกเป็นหินวิญญาณแจกศิษย์

        ผลผลิตมาจาก economy.sect_output (คอบบ์-ดักลาส) และ **ถูกหักจากคลังฟ้าของแดนจริง**
        ถ้าคลังไม่พอก็ได้เท่าที่มี ซึ่งแปลว่าในยุคเสื่อมสำนักจนลงพร้อมกันทั้งแดน
        โดยไม่ต้องเขียนเหตุการณ์ "เศรษฐกิจตกต่ำ" แยก
        """
        w = self.world(org.world_id)
        out = EC.sect_output(sum(1 for cid in org.members
                                 if 0 <= cid < len(self.cast) and self.cast[cid].alive),
                             self.sect_territory(org))
        got = min(out, max(0.0, w.heaven))
        if got <= 0:
            org.monthly_resource = 0.0
            return 0.0
        w.heaven -= got
        org.treasury_qi = getattr(org, "treasury_qi", 0.0) + got
        org.monthly_resource = got
        # แจกออกตามลำดับชั้นศิษย์ ส่วนที่เหลือค้างคลังไว้เป็นทุนของสำนัก
        share_out = org.treasury_qi * C.SECT_PAYOUT_RATE
        org.treasury_qi -= share_out
        grade = min(len(EC.GRADE_NAMES) - 1, w.tier)
        for pool, group in ((0.4, getattr(org, "core_disciples", [])),
                            (0.4, getattr(org, "inner_disciples", [])),
                            (0.2, getattr(org, "outer_disciples", []))):
            live = [cid for cid in group
                    if 0 <= cid < len(self.cast) and self.cast[cid].alive]
            if not live:
                continue
            each = share_out * pool / len(live)
            for cid in live:
                EC.add_stones(self.cast[cid], grade, EC.mint(each, grade))
        return got

    def on_realm_fall(self, ch, steps, qi_year):
        """ขั้นหล่นเพราะเลี้ยงตัวไม่ไหว — บันทึกไว้ให้เห็น ไม่ใช่หล่นเงียบๆ

        ถ้าไม่ emit ออกมา ตัวละครจะอ่อนลงโดยที่ทั้งผู้เขียนและชั้นจิตใจไม่รู้ว่าเกิดอะไร
        ซึ่งเป็นบั๊กคลาสเดียวกับ "กลไกที่ไม่มี outcome แยก" ที่เคยทำให้ถ่ายทอดวิชาตายไป
        สองพันครั้งโดยไม่มีใครรู้
        """
        w = self.world(ch.world_id)
        d = {"ปราณที่หาได้ต่อปี": f"{qi_year:.2f}",
             "ที่ยืน": f"{self.place_name(ch)} เลี้ยงได้ถึงขั้น "
                       f"{EC.place_ceiling(self.qi_density(ch.place, w)):.1f}",
             "หินวิญญาณที่เหลือ": f"{EC.purse_qi(ch):.1f} หน่วยปราณ"}
        self.emit(w, "ขั้นถดถอย", ch, None, ("ถดถอย",), "ยึดขั้นไม่อยู่",
                  f"{ch.name}เลี้ยงปราณในกายไว้ไม่ไหว ขั้นถดถอยลง {steps} ขั้น "
                  f"เหลือ{ch.realm_name()}", 0, d)

    def qi_field(self):
        """ดาวของจักรวาลนี้ — D(p) = R + A·F(p̂ + λW(p̂)) - ‖p‖ (ดู noise.Planet)

        สร้างครั้งเดียวต่อซิม ไม่ใช้ rng หลัก จึงเป็นฟังก์ชันบริสุทธิ์ของ (seed, ทิศ) เท่านั้น
        โลกที่โหลดจากเซฟคนละจุดได้ดาวดวงเดียวกันเสมอ
        """
        f = getattr(self, "_qi_field", None)
        if f is None:
            f = self._qi_field = NZ.Planet(
                seed=getattr(self, "seed", 0) ^ 0x91F1_0000,
                radius=C.PLANET_RADIUS, amp=C.PLANET_AMP,
                lam=C.PLANET_LAMBDA, octaves=C.PLANET_OCTAVES,
                warp_octaves=C.PLANET_WARP_OCTAVES)
        return f

    def place_dir(self, place_idx):
        """ทิศของสถานที่บนผิวดาว p̂ — ฉายจากพิกัดแผนที่ระนาบขึ้นทรงกลม"""
        if place_idx is None or not (0 <= place_idx < len(GEO.COORDS)):
            return (0.0, 0.0, 1.0)
        x, y = GEO.COORDS[place_idx]
        return NZ.sphere_dir(x, y, C.PLANET_SPAN)

    def place_surface(self, place_idx):
        """รัศมีของผิวดาวที่สถานที่นี้ = R + A·F(p̂ + λW(p̂)) — คิดครั้งเดียวแล้วจำไว้"""
        book = getattr(self, "_surf_cache", None)
        if book is None:
            book = self._surf_cache = {}
        v = book.get(place_idx)
        if v is None:
            d = self.place_dir(place_idx)
            v = book[place_idx] = self.qi_field().surface_radius(
                *d, scale=C.PLANET_SCALE)
        return v

    def place_sdf(self, place_idx, radial=0.0):
        """D(p) ที่สถานที่นี้ — บวก = ฝังอยู่ใต้ผิว · ลบ = ลอยอยู่เหนือผิว

        `radial` คือระยะที่สถานที่นั้นอยู่ห่างจากผิวตามแนวรัศมี (เป็นสัดส่วนของ A)
        นี่คือที่ที่ "เกาะสวรรค์ลอยฟ้า" กับ "แดนลับที่ถูกผนึกใต้ดิน" มีตัวเลขจริงของตัวเอง
        แผนที่ความสูงให้ค่าได้ค่าเดียวต่อพิกัด จึงแทนห้องใต้ดินหรือเกาะลอยไม่ได้เลย
        """
        surf = self.place_surface(place_idx)
        return surf - (surf + radial * C.PLANET_AMP)

    def qi_field_at(self, place_idx):
        """ความเข้มของเส้นปราณที่สถานที่นี้ (0..1) — คิดครั้งเดียวต่อสถานที่แล้วจำไว้

        ใช้ F(p̂ + λW(p̂)) ตัวเดียวกับที่กำหนดความสูงของภูมิประเทศ **โดยเจตนา**
        ในโลกนี้ภูเขาคือที่ที่ปราณโผล่ ไม่ใช่สองเรื่องที่เกิดขึ้นแยกกัน — และเพราะสนามถูกบิด
        (λW) เส้นระดับของมันจึงเป็น **เส้นใยยาว** ไม่ใช่หยดกลม ซึ่งคือรูปร่างของ "เส้นปราณ
        ของแผ่นดิน" ที่คนตามรอยไปได้ วัดจริงที่ค่าที่ใช้อยู่: λ=0 ได้เส้นขอบ 3,060 หน่วย
        · λ=1 ได้ 4,569 ที่พื้นที่เท่ากัน = ยาวขึ้น 1.49 เท่า

        พิกัดของสถานที่คงที่ตลอดการรัน ค่าสนามจึงคงที่ด้วย ต่างจาก eco ที่เปลี่ยนตามการขุด
        การแยกสองอย่างนี้ทำให้ "ที่นี่ปราณหนาโดยธรรมชาติ" กับ "ที่นี่ถูกขุดจนโทรม"
        อ่านแยกกันได้ — ที่ปราณหนาที่ถูกขุดพังยังฟื้นกลับมาหนาได้
        """
        book = getattr(self, "_qi_field_cache", None)
        if book is None:
            book = self._qi_field_cache = {}
        v = book.get(place_idx)
        if v is None:
            if place_idx is None or not (0 <= place_idx < len(GEO.COORDS)):
                v = 0.5
            else:
                d = self.place_dir(place_idx)
                # F คืน -1..1 · แปลงเป็น 0..1 ที่นี่ครั้งเดียว
                v = 0.5 + 0.5 * self.qi_field().height(*d, scale=C.PLANET_SCALE)
            book[place_idx] = max(0.0, min(1.0, v))
        return book[place_idx]

    def qi_density(self, place_idx, world):
        """ความหนาแน่นของปราณฟ้าดิน ณ จุดหนึ่ง — ตัวเลขที่สำคัญที่สุดในโลกนี้

        มันตัดสินว่าใครยึดขั้นไหนไว้ได้ (economy.place_ceiling) เวลาในถ้ำเดินเร็วแค่ไหน
        (physics.time_dilation) และสำนักไหนรวย (economy.sect_output) จึงสมควรมาจาก
        **ภูมิศาสตร์จริงที่ต่างกันทุกเมล็ด** ไม่ใช่เลข 0/1/2 ที่พิมพ์ไว้ในตาราง

        สี่ปัจจัย:
          · **สนามปราณ** — Perlin ที่พิกัดของที่นี่ ต่างกันทุก seed และ **หนาแน่นเป็นแถบ
            ต่อเนื่อง** เพราะ noise มีสหสัมพันธ์เชิงพื้นที่ หุบเขาข้างกันจึงหนาไปด้วยกัน
            ซึ่งเป็นสิ่งที่การสุ่มรายจุดให้ไม่ได้ และเป็นเหตุผลที่ "ครองดินแดน" มีความหมาย
          · เกรดที่เขียนด้วยมือ (0-2) — เจตนาของผู้เขียนว่าที่นี่ควรเป็นแดนศักดิ์สิทธิ์หรือ
            ทุ่งร้าง เก็บไว้เป็น **อคติ** ไม่ใช่คำตัดสิน สนามเป็นตัวปรับขึ้นลงจากฐานนั้น
          · ชั้นของแดน — โลกระดับสูงปราณบริสุทธิ์และหนาแน่นกว่า (กฎเดิมของโลก)
          · สัดส่วนนิเวศที่เหลือ — ถูกขุดจนโทรม ปราณก็บางลงตาม (เปลี่ยนได้ ต่างจากสามข้อแรก)
        """
        pv = PL.PLACES[place_idx] if 0 <= place_idx < len(PL.PLACES) else None
        grade = pv[2] if pv else 0
        eco = self.eco_ratio(place_idx) if place_idx is not None and place_idx >= 0 else 1.0
        field = self.qi_field_at(place_idx)
        # สนาม 0 -> คูณ (1-W) · สนาม 1 -> คูณ (1+W) · สนาม 0.5 -> คูณ 1 พอดี
        # เขียนแบบนี้เพื่อให้ W = 0 คืนพฤติกรรมเดิมเป๊ะ ปรับกลับได้ถ้าไม่ชอบ
        shape = 1.0 - C.QI_FIELD_W + 2.0 * C.QI_FIELD_W * field
        # การขุดทำให้ปราณบางลง แต่ **ไม่เท่ากับที่มันทำให้ของหมด**
        # ของเดิมคูณ eco เข้าไปตรงๆ (ช่วง 0.2-1.5 = ต่างกัน 7.5 เท่า) ซึ่งกลบสนามภูมิศาสตร์
        # (ช่วง 0.5-1.5 = 3 เท่า) จนหมด วัดจริงปีที่ 55: ที่ที่คนกระจุกทุกแห่งมีเพดานติดลบ
        # ทั้งที่ตอนปีที่ 0 หุบเขาโอสถหลวงเลี้ยงได้ถึงขั้น 4.8 — ภูมิศาสตร์ของเมล็ดถูกลบทิ้ง
        # ด้วยเรื่องว่าคนไปกระจุกที่ไหน
        #
        # แยกสองเรื่องออกจากกัน: สมุนไพรกับแร่หมดได้จริงและหมดเร็ว ส่วนปราณฟ้าดินเป็น
        # คุณสมบัติของแผ่นดิน มันบางลงเมื่อถูกดูดหนัก แต่ไม่ถึงกับหายไป — และฟื้นกลับมา
        # หนาได้เมื่อคนย้ายไป ส่วนที่ปราณบางโดยธรรมชาติจะขุดหรือไม่ขุดก็บางอยู่วันยังค่ำ
        wear = 1.0 - C.QI_ECO_W + C.QI_ECO_W * max(0.0, min(1.5, eco))
        return ((grade + 1) * C.QI_PER_GRADE * shape
                * (1.0 + C.QI_PER_TIER * world.tier)
                * wear)

    def make_cache(self, ch, faked):
        k = Cache(kid=self.nid("k"), world_id=ch.world_id, owner=ch.cid,
                  owner_name=ch.name, sealed_day=self.day,
                  seal=C.SEAL_BASE * (0.5 + 0.25 * ch.realm),
                  items=list(ch.items), currency=sum(ch.money.values()),
                  trap=faked, era_sealed=self.world(ch.world_id).era)
        # ผู้เก็บตัวมักจารึกวิชาหรือวางยันต์ทิ้งไว้ให้คนยุคหลัง
        if self.rng.random() < C.CACHE_RELIC_P:
            relic = self.stash_relic(ch, self.rng)
            if relic is not None:
                k.items.append(relic.iid)
        ch.items = []
        self.caches.append(k)
        return k

    def ruined_cache_find(self, ch, rng, d):
        """ชั้นเล็กที่สุดของการค้นแดนลับ — ซากแดนลับที่ถูกกวาดไปก่อนหน้าแล้ว

        ทำไมต้องมี: "แดนลับมีของเสมอ ต่างกันแค่มากหรือน้อย" เป็นกฎของโลกนี้ ผลลัพธ์ "ไม่พบ"
        จึงเป็นสิ่งที่ไม่ควรมีตั้งแต่แรก วัดจริงก่อนแก้ — ค้นแดนลับ 4,693 ครั้งจบด้วย "ไม่พบ"
        99% และในบันทึกผู้มีจิตใจปีที่ 118-129 จบด้วย "ไม่พบ" 13/13 ครั้ง คิดเป็น 13% ของ
        การตัดสินใจทั้งหมดของตัวเอกที่หายไปกับการออกไปเสี่ยงตายแล้วกลับมามือเปล่า

        ของที่ได้ผูกกับ **ชะตา** ของคนค้น ไม่ใช่สุ่มล้วน — "ผู้มีวาสนา" ได้มากกว่าคนธรรมดา
        ที่ยืนอยู่จุดเดียวกัน ซึ่งเป็นกติกาเดิมของโลกอยู่แล้ว (ดู FRAGMENT_FATE_BONUS)
        และเขียนของลงใน `d` ให้บันทึกเห็นว่าได้อะไรกลับมาบ้าง
        """
        w = self.world(ch.world_id)
        luck = 1.0 + C.RUIN_CORES_FATE * max(0, getattr(ch, "fate", 0))
        # หางหนัก: ซากส่วนใหญ่เหลือของก้นถุง แต่นานๆ ครั้งมีคนเจอของที่คนก่อนหน้ามองข้าม
        # ของเดิมใช้ randint ซึ่งแบนราบ — "แดนลับมีของเสมอ" จึงกลายเป็น "ได้เท่ากันทุกครั้ง"
        # มีพื้นไว้ เพราะ "แดนลับมีของเสมอ" และเพราะถ้าปล่อยให้ตัวคูณลงไปใกล้ศูนย์ได้
        # มันจะกลบผลของชะตาจนหมด — ผู้มีวาสนากับคนธรรมดาจะได้เท่ากันที่ปลายล่าง
        rich = max(C.RUIN_MIN_MULT,
                   PHYS.lognormal_value(1.0, C.RUIN_VALUE_SIGMA, rng.random()))
        luck *= rich
        cores = max(1, int(round(rng.randint(*C.RUIN_CORES) * luck)))
        if rich >= C.RUIN_JACKPOT:
            d["วาสนา"] = f"ซากนี้ยังไม่มีใครค้นถึงก้น — ได้ของมากกว่าปกติ {rich:.1f} เท่า"
        ch.cores += cores
        d["เก็บตกจากซาก"] = f"แก่นพลัง×{cores}"

        gain = rng.uniform(*C.RUIN_INSIGHT) * luck
        ch.insight += gain
        d["อ่านรอยจารึกที่เหลืออยู่"] = f"ความเข้าใจ +{gain:.1f}"

        coins = int(rng.randint(*C.RUIN_MONEY) * luck)
        if coins > 0:
            ch.money[w.tier] = ch.money.get(w.tier, 0) + coins
            d["เหรียญทองที่ร่วงอยู่"] = f"{coins:,}"
        # หินวิญญาณที่คนก่อนหน้าทำหล่นไว้ — **ไม่หักจากคลังฟ้า** เพราะปราณก้อนนี้ถูกขุด
        # ออกจากโลกไปแล้วตั้งแต่รุ่นก่อน มันแค่เปลี่ยนมือ ถ้าหักซ้ำคือทำบัญชีพัง
        stones = C.RUIN_STONES * luck
        if stones > 0:
            grade = min(len(EC.GRADE_NAMES) - 1, w.tier)
            ch_stones = EC.mint(stones, grade)
            EC.add_stones(ch, grade, ch_stones)
            d["หินวิญญาณที่ตกค้าง"] = f"{EC.grade_name(grade)} ×{ch_stones:.1f}"

        if ch.mat_stock is not None and rng.random() < C.RUIN_MAT_P:
            pool = MAT.materials_at(ch.place)
            if pool:
                m = rng.choice(list(pool))
                ch.mat_stock[m] = ch.mat_stock.get(m, 0) + 1
                d["ของที่ติดมือกลับมา"] = m

        # ร่องรอยที่ชี้ไปยังแดนลับจริง — ทำให้การค้นครั้งนี้ "พาไปสู่ครั้งหน้า" แทนที่จะจบลอยๆ
        sealed = [c for c in self.caches if c.world_id == w.wid and not c.opened]
        if sealed and rng.random() < C.RUIN_LEAD_P:
            k = rng.choice(sealed)
            leads = [l for l in getattr(ch, "rumor_leads", [])
                     if not (l["kind"] == "แดนลับ" and l["subject"] == k.kid)]
            leads.append({"kind": "แดนลับ", "subject": k.kid, "true": True})
            ch.rumor_leads = leads[-C.RUMOR_LEAD_MAX:]
            d["ร่องรอยที่พบ"] = f"จารึกชี้ทางไปแดนลับของ{k.owner_name} — ผนึกยังไม่คลาย"
            return "พบซากแดนลับ", (f"{ch.name}พบซากแดนลับที่ถูกกวาดไปนานแล้วที่"
                                   f"{self.place_name(ch)} เก็บของที่ตกค้างและอ่านเจอ"
                                   f"จารึกชี้ทางไปยังแดนลับของ{k.owner_name}")
        return "พบซากแดนลับ", (f"{ch.name}พบซากแดนลับที่ถูกกวาดไปนานแล้วที่"
                               f"{self.place_name(ch)} เหลือเพียงของที่ตกค้างให้เก็บ")

    def open_cache(self, ch, k, rng):
        """เปิดแดนลับ — ของในนั้นต้องไปถึงมือใครสักคนเสมอ ไม่งั้นมันหายจากโลกถาวร

        บั๊กเดิมสามชั้นซ้อน วัดจริงที่ปีที่ 946: สมบัติฟ้าดิน 27 ชิ้นมีคนถืออยู่แค่ 6 ชิ้น
          1. ตั้ง k.opened = True **ก่อน** เช็คกับดัก แล้ว return ออกไปโดยไม่แจกของเลย
             แดนลับนั้นจึงถูกทำเครื่องหมายว่าเปิดแล้ว ไม่มีใครมาเปิดอีก ของข้างในหายถาวร
             — วัดได้ 24 ชิ้นค้างแบบนี้
          2. แจกของแล้วไม่เคยล้าง k.items ทำให้สมบัติชิ้นเดียวถูกบันทึกอยู่ในหลายแดนลับ
             พร้อมกัน ข่าวลือจึงชี้ไปที่แดนลับที่ว่างเปล่าได้
          3. ของที่ผุจนต่ำกว่าเกณฑ์ถูกทิ้งไว้เฉยๆ รวมถึงสมบัติฟ้าดินที่มีชื่อ ซึ่งขัดกับกฎของ
             โลกที่ว่ามันไม่มีวันสูญหาย
        """
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
            if win is not ch:
                # เจ้าของกับดักชนะ — ผนึกยังอยู่ ของยังอยู่ในนั้น รอผู้มีวาสนาคนต่อไป
                d["ผนึก"] = "ยังไม่ถูกเปิด รอคนต่อไป"
                return d
            d["ผนึก"] = "ผู้บุกฝ่ากับดักเข้าไปได้"
        k.opened = True
        rot = 1.0 - min(1.0, max(0.0, -R.seal_left(k, self.day) / C.SEAL_BASE)) * C.CACHE_ROT
        got, rotted = 0, 0
        for iid in k.items:
            it = self.items.get(iid)
            if it is None:
                continue
            it.condition *= rot
            if it.legend:
                # สมบัติฟ้าดินที่มีชื่อไม่ผุจนใช้ไม่ได้ และต้องถึงมือผู้เปิดเสมอ
                it.condition = max(it.condition, 0.35)
                ch.items.append(iid)
                got += 1
            elif it.condition > 0.15:
                ch.items.append(iid)
                got += 1
            else:
                rotted += 1
                self.items.pop(iid, None)     # ผุจนสูญสลาย ออกจากโลกอย่างเป็นทางการ
        k.items = []                          # ของออกจากแดนลับแล้ว ห้ามค้างชื่อไว้ซ้ำ
        k.currency = 0.0
        tier = self.world(k.world_id).tier
        ch.money[tier] = ch.money.get(tier, 0.0) + k.currency * rot
        d["แดนลับ"] = f"มรดกของ{k.owner_name}จากยุคที่ {k.era_sealed} — ได้ของ {got} ชิ้น"
        if rotted:
            d["ผุสูญสลาย"] = f"{rotted} ชิ้น"
        return d

    def reseal_lost_legends(self):
        """กฎเหล็กของโลก: สมบัติฟ้าดินที่มีชื่อไม่มีวันสูญหาย — บังคับให้เป็นจริงเสมอ

        แทนที่จะไล่อุดทีละทางที่ของอาจหลุดออกจากโลก (ตายในศึกที่ไม่ผ่าน kill · สถานที่ถูกถล่ม ·
        แดนลับที่เปิดแล้วแต่ไม่มีใครรับของ) ตรวจ**ผลลัพธ์**เป็นรอบแล้วผนึกกลับคืน ทางไหนที่ยัง
        รั่วอยู่ในอนาคตก็จะถูกจับได้ด้วยตัวเดียวกันนี้ วัดจริงที่ปีที่ 946: มี 2 ชิ้นหายจากโลกไป
        เฉยๆ ไม่อยู่กับใคร ไม่อยู่ในแดนลับไหนเลย
        """
        held = set()
        for c in self.cast:
            if c.alive:
                held.update(c.items)
        sealed = set()
        open_caches = []
        for k in self.caches:
            if k.opened:
                open_caches.append(k)
            else:
                sealed.update(k.items)
        lost = [iid for iid in self.legend_iids
                if iid in self.items and iid not in held and iid not in sealed]
        if not lost:
            return 0
        rng = self.rng
        w = self.worlds[0]
        k = Cache(kid=self.nid("k"), world_id=w.wid, owner=-1,
                  owner_name="ผู้วางฟ้าดิน", sealed_day=self.day,
                  seal=C.SEAL_BASE, items=list(lost), currency=0.0,
                  trap=False, era_sealed=w.era)
        self.caches.append(k)
        names = " · ".join(self.items[i].name for i in lost[:5])
        self.emit(w, "สมบัติฟ้าดินหวนคืนผนึก", None, None, ["หลอมรวม"], "ผนึกกลับคืน",
                  f"สมบัติฟ้าดิน {len(lost)} ชิ้นที่ขาดผู้ครองถูกฟ้าดินผนึกกลับสู่แดนลับ "
                  f"รอผู้มีวาสนาคนต่อไป", 0,
                  {"สมบัติที่หวนคืน": names,
                   "กฎที่บังคับ": "สมบัติฟ้าดินที่มีชื่อไม่มีวันสูญหาย"})
        return len(lost)

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
        """แหล่งทรัพยากรฟื้นตัวแบบลอจิสติก ไม่ใช่เส้นตรง

        ของเดิมเขียน `min(ECO_CAP, stock + grow)` ซึ่งเป็นสองข้อผิดเดียวกับที่ heaven_inflow
        เคยเป็นก่อนแก้ และตรวจเจอซ้ำที่นี่ตอนรื้อระบบทรัพยากร
          1. แหล่งที่ถูกขุดจนเหลือเศษ ฟื้นเร็วเท่าแหล่งที่เกือบเต็ม — "ขุดจนโทรม" จึงไม่เคย
             เป็นสภาพที่อยู่ได้นานพอจะมีผลต่อการตัดสินใจของใคร
          2. min() ที่เพดานคือการทำผลผลิตหายจากระบบเงียบๆ
        ลอจิสติกแก้ทั้งคู่ และให้ "แหล่งที่ตายแล้วฟื้นช้ามาก" ฟรี ซึ่งเป็นสิ่งที่ทำให้
        ตัวละครต้องย้ายถิ่นจริงๆ แทนที่จะขุดที่เดิมไปเรื่อยๆ
        ฤดูกาลยังคูณอัตราการโตเหมือนเดิม (ฤดูไหนของงอกดีกว่ากัน)
        """
        if not self.place_stock or elapsed_days <= 0:
            return
        rate = (C.ECO_REGEN_PER_YEAR / C.ECO_CAP) * SEASONS.regen_multiplier(self.day) / 365.0
        for idx in list(self.place_stock):
            # เมล็ดเล็กๆ ด้วยเหตุผลเดียวกับคลังฟ้า: ลอจิสติกที่ศูนย์โตไม่ได้ตลอดกาล
            now = max(C.ECO_SEED, self.place_stock[idx])
            stock = PHYS.logistic_growth(now, C.ECO_CAP, rate, elapsed_days)
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

    def _world_tick(self, rng):
        """งานประจำของโลกหนึ่งรอบ ณ วันที่นาฬิกาโลกนัดไว้ แล้วนัดรอบถัดไป"""
        self.day = max(self.day, self.world_tick_day)
        self.world_tick_day = self.day + C.WORLD_TICK_DAYS
        self._advance_eco()
        if C.GUARDIANS_ENABLED:
            GUARD.tick(self)
        if C.FOOD_ENABLED:
            FOOD.tick(self, self.day - self.food_day)
        if C.WAGES_ENABLED:
            WAGES.tick(self, self.day - self.food_day)
        self.food_day = self.day
        WT.tick(self, rng)      # ต้นไม้โลกในแดนลับต้นกำเนิด (ดู tiandao/worldtree.py)
        # เดิมเรียกทุกเหตุการณ์ ซึ่งวน 126 แดนทุกครั้งเพื่อบวกทรัพยากรของไม่กี่วัน —
        # โปรไฟล์จริง: 5.0 วินาทีจาก 100 (5%) โดยได้ผลเท่ากันทุกประการถ้าสะสมเป็นก้อน
        if self.day - getattr(self, "_portal_regen_day", -10**9) >= C.WORLD_TICK_DAYS:
            PORT.regen(self, self.day - getattr(self, "_portal_regen_day", 0))
            self._portal_regen_day = self.day
        PORT.tick(self, rng)    # การสร้างประตูมิติ (ดู tiandao/portals.py)
        if self.day - getattr(self, "last_disaster_day", 0) >= C.WORLD_TICK_DAYS:
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
                    treasury = getattr(org, "treasury", 0.0)
                    for cid in org.members:
                        if not (0 <= cid < cast_len) or not self.cast[cid].alive:
                            continue
                        mem = self.cast[cid]
                        wkey = self.world(mem.world_id).tier
                        due = mem.money.get(wkey, 0.0) * C.SECT_DUES_RATE
                        if due > 0:
                            mem.money[wkey] = mem.money.get(wkey, 0.0) - due
                            treasury += due
                    payout = treasury * C.SECT_PAYOUT_RATE
                    org.treasury = treasury - payout
                    pool_c = payout * 0.4
                    pool_i = payout * 0.4
                    pool_o = payout * 0.2

                    cd = getattr(org, "core_disciples", [])
                    id_ = getattr(org, "inner_disciples", [])
                    od = getattr(org, "outer_disciples", [])

                    if cd:
                        share = int(pool_c / len(cd))
                        for cid in cd:
                            if 0 <= cid < cast_len and self.cast[cid].alive: WAGES.move_gold(self, self.cast[cid], share)
                    if id_:
                        share = int(pool_i / len(id_))
                        for cid in id_:
                            if 0 <= cid < cast_len and self.cast[cid].alive: WAGES.move_gold(self, self.cast[cid], share)
                    if od:
                        share = int(pool_o / len(od))
                        for cid in od:
                            if 0 <= cid < cast_len and self.cast[cid].alive: WAGES.move_gold(self, self.cast[cid], share)

                    self.sect_mine(org)

            # ------------------------------------------------
            # Divine Spirits Hunting Demons
            # ------------------------------------------------
            living_now = self.living()
            # บัญชาสวรรค์เป็นหน้าที่รบของผู้ใหญ่ ทั้งผู้ล่าและเป้าหมายต้องพ้นวัยเด็ก
            # มิฉะนั้นสิ่งมีชีวิตที่เกิดมาพร้อมสายเลือดวิญญาณ/มารจะออกรบตั้งแต่อายุหนึ่งปี
            spirits = [c for c in living_now
                       if c.age(self.day) >= 14 and getattr(c, "is_spirit", False)]
            demons = [c for c in living_now
                      if c.age(self.day) >= 14 and getattr(c, "is_demon", False)]
            if spirits and demons:
                if self.rng.random() < 0.3: # 30% chance for a holy crusade
                    hunter = self.rng.choice(spirits)
                    target = self.rng.choice(demons)
                    safe_print(f"\n⚔️ [บัญชาสวรรค์] เผ่าวิญญาณศักดิ์สิทธิ์ [{hunter.name}] บุกสังหารมารร้าย [{target.name}] เพื่อรักษาสมดุลโลก!")
                    import tiandao.combat as combat
                    combat.resolve_combat(hunter, target, self.worlds[0], self)
                    # เดิมบล็อกนี้ print() อย่างเดียว ไม่ emit — เหตุการณ์ดราม่าที่สุดของโลก
                    # จึงไม่มีอยู่ในประวัติศาสตร์ ไม่ขึ้นใน log ไม่ถูกนับเป็นจุดเปลี่ยนของใคร
                    # และโรงงานนิยายมองไม่เห็นเลยสักครั้ง วัดจริง 121 ปี: 0 บรรทัดใน log
                    self.emit(self.worlds[0], "บัญชาสวรรค์", hunter, target,
                              ["ต่อสู้", "ความตาย"],
                              "สังหารมารสำเร็จ" if not target.alive else "มารหนีรอด",
                              f"{hunter.name}แห่งเผ่าวิญญาณศักดิ์สิทธิ์รับบัญชาสวรรค์ "
                              f"บุกสังหาร{target.name}ผู้ตกเป็นมาร เพื่อรักษาสมดุลของโลก",
                              0, {"เหตุแห่งบัญชา": "เผ่าวิญญาณศักดิ์สิทธิ์ล้างมารตามหน้าที่",
                                  "ชะตาของมาร": "ดับสูญ" if not target.alive else "รอดไปได้"})
            
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
                        if self.rng.random() < 0.05: # 5% chance every 30 days
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
                
                if self.rng.random() < 0.1: # 10% chance to attack a city
                    if hasattr(C, "CITIES"):
                        targets = [city for city in C.CITIES if "ชายแดน" in city.get("type_desc", "") or "หน้าด่านสำนัก" in city.get("type_desc", "")]
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
                          0, {"โลกตกระดับ": f"เหลือชั้น {w.tier}"})

        CRISES.tick(self)

    def requeue(self, ch, day):
        """ย้ายเทิร์นที่รออยู่ของคนนี้ไปเป็นวันที่กำหนด — คิวต้องมีใบเดียวต่อคน (ดู persist._repair_queue)

        O(ขนาดคิว) จึงใช้เฉพาะเหตุที่นานๆ เกิด เช่น ความหิวดึงคนออกจากด่านหรือส่งคนไปหาอาหาร
        """
        self.queue = [(d, c) for d, c in self.queue if c != ch.cid]
        heapq.heapify(self.queue)
        heapq.heappush(self.queue, (max(day, self.day), ch.cid))

    def _step(self):
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
                    # เจ้าเมืองคือผู้ใหญ่ที่มีตำแหน่ง ไม่ใช่ทารกอายุศูนย์ปีซึ่งถูกเปลี่ยนชื่อ
                    # แล้วส่งไปปกครองเมืองทันที
                    ruler = self.spawn(self.worlds[0], age_years=rng.randint(30, 60))
                    # เมืองหลายเมืองใช้ชื่อเจ้าเมืองชุดเดียวกัน (นายอำเภอ "หวังป๋อ" ทุกเมือง) —
                    # ผ่าน unique_name ให้คนที่สองได้ชื่อที่ต่างออกไป ไม่งั้นบันทึกแยกเจ้าเมืองไม่ออก
                    ruler.name = self.unique_name(ruler_name, old=ruler.name)
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
            if ch.energy > 50 and getattr(ch, "is_beast", False) == False and getattr(ch, "is_demon", False) == False and getattr(ch, "is_spirit", False) == False:
                if self.rng.random() < 0.1: # 10% chance to farm
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
                        ch.money[self.world(ch.world_id).tier] = ch.money.get(self.world(ch.world_id).tier, 0.0) + earned
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
                days_in = self.day - int(ch.seclude_snap.get("day", self.day))
                # ออกก่อนกำหนดเพราะเสบียงหมด (tiandao/food.py) ได้ผลเท่าเวลาที่อยู่จริง ไม่ปัดขึ้นเป็นหนึ่งปี
                cut_short = getattr(ch, "seclude_cut", False)
                ch.seclude_cut = False
                yrs = days_in / 365.0 if cut_short else max(1, days_in // 365)
                # เวลาที่ "ได้ใช้" ไม่เท่ากับเวลาที่โลกภายนอกผ่านไป ถ้าปราณตรงนั้นหนาแน่นพอ
                gamma = float(ch.seclude_snap.get("gamma", 1.0) or 1.0)
                felt = yrs * gamma
                ch.insight += C.SECLUDE_INSIGHT_PER_YEAR * felt
                ch.refine += C.SECLUDE_REFINE_PER_YEAR * felt
                ch.seclude_until, ch.hidden = 0, False
                wv = self.world(ch.world_id)
                EM.decay(ch, self.day)
                for key in list(ch.emotions):
                    base = ch.emo_base.get(key, ch.emotions[key])
                    ch.emotions[key] += (base - ch.emotions[key]) * C.SECLUDE_FOCUS
                d_out = self.seclusion_diff(ch, wv, yrs)
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
                jailer = None
                if ch.rivals:
                    jcid = max(ch.rivals, key=lambda c: (ch.rivals[c], -c))
                    if 0 <= jcid < len(self.cast):
                        jailer = self.cast[jcid]
                if self.day < ch.jail_until:
                    gap_j = ch.jail_until - self.day
                    bar = (jailer.realm + C.JAIL_ESCAPE_REALM_GAP) if jailer is not None else 99
                    if ch.realm >= bar and rng.random() < C.JAIL_ESCAPE_P:
                        ch.jail_until, ch.hidden = 0, False
                        ch.decay += 0.3
                        self.emit(w_j, "แหกคุก", ch, jailer, ["ทำลาย"], "แหกคุก",
                                  f"{ch.name}ทลายที่คุมขังหลบหนีออกมาได้ก่อนพ้นโทษ", 0,
                                  {"โทษที่เหลือ": f"{gap_j // 365} ปี"})
                        self.schedule(ch, rng.randint(30, 200))
                    else:
                        self.schedule(ch, gap_j)
                    continue
                ch.jail_until, ch.hidden = 0, False
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
                R.age_and_decay(self, ch, world0, self.day - ch.last_day, rng)
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
        if actor.age(self.day) < 14:
            BODY.tick(actor, actor_gap, day=self.day, fed=FOOD.fed_share(actor))
        else:
            R.age_and_decay(self, actor, world, actor_gap, rng)
        actor.last_day = self.day


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

        # งานประมูลใหญ่ของตลาด — เหตุการณ์ของ "สถานที่" ไม่ใช่ของอาชีพ
        # วัดจากรันจริง 79 ปี: ผู้มีจิตใจได้เข้างานประมูลแค่ครั้งเดียว เพราะท่า "เปิดประมูล" เปิดให้เฉพาะ
        # พ่อค้า (หลงจู๊/เถ้าแก่/นักประมูล) ซึ่งแทบไม่มีใครในกลุ่มตัวเอก ฉากหมู่จึงไม่เคยเกิด
        if world.kind == "mortal" and rng.random() < C.AUCTION_EVENT_P:
            self.market_auction(world, rng)

        # มารบุกโลกมนุษย์ (หากผนึกแตก โอกาสบุกจะเพิ่มขึ้นอย่างมาก)
        mara_raid_p = C.MARA_RAID_P * (2.5 if getattr(self, "mara_seal_broken", False) else 1.0)
        if world.kind == "mortal" and world.lateral and rng.random() < mara_raid_p:
            mw = self.world(world.lateral[0])
            if mw.kind == "mara":
                self.mara_raid(world, elapsed, rng)
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
                win, lose, margin = R.resolve_clash(h, actor, world, self.items, rng)
                res = R.apply_defeat(self, world, win, lose, margin, rng)
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
        if hasattr(C, "CITIES") and actor.city_id >= 0:
            for c in C.CITIES:
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
        # ชั้นจิตใจ (tiandao/mind): ตัวละครที่มีจิตใจเลือกการกระทำ/เป้าหมายเอง แทนการสุ่มตามน้ำหนัก
        # ไม่ได้แนบ sim.mind ไว้ = ทางเดิมทุกประการ ไม่กิน RNG เพิ่ม (test_determinism.py)
        mind = getattr(self, "mind", None)
        mind_choice = mind.choose(actor, self, w, others, rng) if mind is not None else None
        # Decision Engine (tiandao/decision): Utility+Softmax+Belief+Memory+Social+GOAP สำหรับทุกคนที่
        # ไม่มีจิตใจ LLM — ไม่ได้ attach ไว้ (ค่าเริ่มต้น) = ทางเดิมทุกประการ และไม่แตะ rng หลักเลย
        _de = getattr(self, "decision_engine", None)
        if mind_choice is None and _de is not None:
            mind_choice = _de.choose(actor, self, w, others, world)
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
                and not (mind is not None and mind.skip_side_rolls(actor)) and rng.random() < 0.1):
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
                    if actor.city_id >= 0 and hasattr(C, "CITIES"):
                        city_dict = next((c for c in C.CITIES if c["id"] == actor.city_id), None)
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
        IN.learn_from_outcome(actor, ev["kind"], before, IN.snapshot(actor))
        if ev["kind"] == "ค้นแดนลับ" and actor.rumor_leads:
            actor.rumor_leads = [l for l in actor.rumor_leads if l["kind"] != "แดนลับ"]
        for t in ev["tags"]:
            actor.exp[t] = actor.exp.get(t, 0) + 1
        e = self.emit(world, ev["kind"], actor, target, ev["tags"], outcome, text, elapsed, d)
        if mind is not None:
            mind.after_action(actor, self, ev["kind"], target, e)
        if actor.alive:
            self._next_turn(actor, gap, rng)
        return e

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
                     if x.place == spot and x.age(self.day) >= 14]
        d = {"รอยแยก": f"กว้าง {world.rift:.1f} — ขั้นที่ลงมาได้ถึง {C.CHAOS_RANKS[min(cap, len(C.CHAOS_RANKS)-1)]}",
             "ถูกกด": f"ลงมาโลกมนุษย์แล้วถูกกดลง {C.CHAOS_DESCEND_PUSH} ขั้นตามกฎของโลกล่าง"}
        if defenders:
            v = max(defenders, key=lambda x: R.power(x, world, self.items))
            win, lose, margin = R.resolve_clash(c, v, world, self.items, rng, self.day)
            res = R.apply_defeat(self, world, win, lose, margin, rng)
            d["ผู้ต้านทาน"] = f"{v.name} — {res}"
            d["margin"] = round(margin, 3)
            d["winner"] = win.cid
            if R.has_anti_chaos(v, self.items):
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
        for ch in self.living():
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
        if len(self.rumors) > C.RUMOR_MAX_ACTIVE:
            del self.rumors[:len(self.rumors) - C.RUMOR_MAX_ACTIVE]
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
        from .treasures import (ANTI_CHAOS_HOME_CUT, ANTI_CHAOS_TREASURE,
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
        raiders = [c for c in self.living_in(self.chaos_wid) if c.age(self.day) >= 14]
        prey = [c for c in self.living_in(world.wid) if c.age(self.day) >= 14]
        if not raiders or not prey:
            return
        c = rng.choice(raiders)
        prey.sort(key=lambda x: -R.power(x, world, self.items))
        v = rng.choice(prey[:3])          # ไล่ล่าผู้แข็งแกร่งก่อน แต่ไม่ใช่คนเดิมทุกครั้ง
        win, lose, margin = R.resolve_clash(c, v, world, self.items, rng, self.day)
        res = R.apply_defeat(self, world, win, lose, margin, rng)
        d = {"แพ้ทาง": "มนุษย์แพ้ทางเผ่าโกลาหล", "margin": round(margin, 3), "winner": win.cid}
        if R.has_anti_chaos(v, self.items):
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
            # เลือกแบบกำหนดได้ (ไม่กิน RNG เพิ่ม) เสมอกันให้ cid น้อยกว่า
            m = min(raiders, key=lambda c: (abs(c.realm - v.realm), c.cid))
        
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
        # เจ้าภาพ: พ่อค้าที่รวยที่สุดในที่นั้น ถ้าไม่มีก็คนที่รวยที่สุด (คนอื่นเป็นผู้ร่วมประมูล)
        folk.sort(key=lambda c: (-self.bid_purse(c, world), c.cid))
        host = next((c for c in folk if getattr(c, "profession", "") in C.AUCTION_HOSTS), folk[0])
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
            host.money[w.tier] = host.money.get(w.tier, 0) + earn
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
        self.emit(w, "เปิดประมูล", host, winner, ["แลกเปลี่ยน", "ทรัพย์", "คน"], "ชนะประมูล",
                  f"{winner.name}ประมูล{lot_name}ไปได้ในราคา {price:.1f} หน่วยปราณ "
                  f"เฉือน{runner_up.name}ไปอย่างหวุดหวิด", 0, dict(d))
        self.emit(w, "เปิดประมูล", host, runner_up, ["แลกเปลี่ยน", "ทรัพย์", "คน"], "พลาดประมูล",
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

    # ------------------------------------------------------------ ผลลัพธ์
    def loot_count(self, ch):
        """ของที่ "ชิงได้" ติดตัวกี่ชิ้น — กฎเดียวกับที่ resolve("ชิงสมบัติ") ใช้ตัดสิน
        (ยาวิเศษไม่นับ เพราะกินหมดแล้วหมดเลย ไม่ใช่สมบัติที่ชิงต่อกันได้)"""
        return sum(1 for i in ch.items
                   if i in self.items and self.items[i].kind != "ยาวิเศษ")

    def aim_theft(self, target, others):
        """เล็งเป้าการชิงสมบัติใหม่ ถ้าคนที่ถูกเลือกไม่มีอะไรติดตัวเลย

        **เจตนายังเป็นของตัวละคร** — เขาเลือกเองว่าจะชิง สิ่งที่แก้คือเป้าให้ตรงกับเจตนานั้น
        ที่ต้องมีเพราะด่านกรองใน `IN.weigh()` ถามแค่ "แถวนี้มีใครมีของให้ชิงไหม" ส่วนชื่อเป้า
        เป็นของตัวละคร ช่องว่างระหว่างสองอย่างนี้วัดได้จากบันทึกจริงสองรอบติด: ตงฟางเฟิน
        ชิงสมบัติจบด้วย "ไม่มีของ" 6/6 ครั้ง (ปีที่ 104-118) และ 5/5 ครั้ง (ปีที่ 118-129)
        รอบหลังพรอมต์ติดป้าย "ไม่มีอะไรมีค่าติดตัว" ให้เห็นทุกคนแล้วด้วย แต่โมเดล 8B ยังเล็ง
        คนเดิม — ในชีวิตที่ลงมือได้ไม่กี่สิบครั้ง เทิร์นที่หายไปแบบนี้แพงมาก

        ไม่ใช่การยัดให้สำเร็จเสมอ: ถ้าทั้งฉากไม่มีใครมีอะไร ก็คืนเป้าเดิมให้ล้มเหลวตามจริง
        และไม่ดึง rng เลย (เลือกแบบคงที่) เพื่อไม่ให้กระทบความคงที่ของโลก
        """
        if target is None or self.loot_count(target) > 0:
            return target
        rich = [c for c in (others or []) if self.loot_count(c) > 0]
        if not rich:
            return target
        return max(rich, key=lambda c: (self.loot_count(c), -c.cid))

    def reach_reason(self, a, t):
        """ทำไมสองคนนี้ถึงเอื้อมถึงกันได้ทั้งที่อยู่คนละที่ — คืนคำอธิบาย หรือ "" ถ้าไม่มีเหตุ

        ใช้เกณฑ์เดียวกับที่ social_pool() ใช้ตัดสินว่าใครติดต่อข้ามระยะได้ (ผูกพัน/จองเวร/
        ศิษย์-อาจารย์/ร่วมสำนัก/ร่วมตระกูล) จึงเป็นการ "อ่านคำตอบเดิม" ไม่ใช่ตั้งเกณฑ์ใหม่
        """
        cid = getattr(t, "cid", None)
        if cid is None or cid == a.cid:
            return ""
        if cid == getattr(a, "master_cid", -1):
            return "เป็นอาจารย์ของเขา"
        if cid in getattr(a, "disciples", ()):
            return "เป็นศิษย์ของเขา"
        if a.rivals.get(cid) or getattr(t, "rivals", {}).get(a.cid):
            return "จองเวรกันอยู่ก่อนแล้ว"
        if a.bonds.get(cid) or getattr(t, "bonds", {}).get(a.cid):
            return "ผูกพันกันอยู่ก่อนแล้ว"
        if a.org is not None and a.org == getattr(t, "org", object()):
            return "ร่วมสำนักเดียวกัน"
        if a.clan >= 0 and a.clan == getattr(t, "clan", -2):
            return "ร่วมตระกูลเดียวกัน"
        return ""

    def resolve(self, ev, a, t, w, gap, rng):
        k, d = ev["kind"], {}
        # คู่กรณีที่ยืนคนละที่ต้องบันทึกไว้ตรงนี้ว่า "เอื้อมถึงกันได้เพราะอะไร" — ที่นี่คือจุดเดียว
        # ที่ยังอ่านความสัมพันธ์ก่อนเหตุการณ์ได้ครบทุกชนิดเหตุการณ์ หลังจากนี้ handler แต่ละตัว
        # แก้ความสัมพันธ์ได้ตามใจ (ทรยศตัด bonds ทิ้ง ล้างแค้นสะสางหนี้) แล้วหลักฐานจะหายไป
        # ตรวจเฉพาะคู่ที่อยู่คนละที่ เพราะคู่ที่ยืนตรงหน้ากันไม่ต้องมีเหตุผลอะไรมารองรับ
        if t is not None and t is not a and getattr(a, "place", -1) != getattr(t, "place", -2):
            tie = self.reach_reason(a, t)
            if tie:
                d[C.PRIOR_TIE_KEY] = tie
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
                            # คู่ครองต้องเป็นผู้ใหญ่ เดิมเด็กในเมืองถูกสุ่มมาแต่งงานและมีลูกได้
                            adult_chars = [c for c in other_chars if c.age(self.day) >= C.ADULT_AGE]
                            if not adult_chars:
                                return "ทั่วไป", pre_msg + f"{a.name}เดินชมเมืองโดยไม่มีเหตุสำคัญ", d
                            b = rng.choice(adult_chars)
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
                                        child.parents = [a.cid, b.cid]
                                        child.bonds[a.cid] = 10
                                        child.bonds[b.cid] = 10
                                        a.children.append(child.cid)
                                        b.children.append(child.cid)
                                        child.generation = getattr(a, "generation", 1) + 1
                                        child.money[w.tier] = a.money.get(w.tier, 0) // 2
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
                            a.money[w.tier] = a.money.get(w.tier, 0) + 150
                            a.insight += 1.2
                            a.enemies_defeated = getattr(a, "enemies_defeated", 0) + 1
                            R.cultivate(a, gap, self.items)
                            del a.nemeses[hunter]
                            return "อันตราย", pre_msg + msg, d
                        else:
                            msg += f" 💥 [พ่ายแพ้คู่แค้น] ท่านพลาดท่าบาดเจ็บสาหัส เสีย -50 HP และถูกชิงทรัพย์ -100 เงิน"
                            a.hp -= 50
                            a.money[w.tier] = max(0, a.money.get(w.tier, 0) - 100)
                            a.nemeses[hunter]["hatred"] = 60
                            msg = check_hp(msg)
                            return "อันตราย", msg, d
                    
                    if rng.randint(1, 100) > safety:
                        msg = "⚠️ [เหตุการณ์อันตราย] คณะเดินทางของคุณโดนโจรป่าดักโจมตี!"
                        enemy_power = rng.randint(40, max(90, int(w.tier*40)))
                        
                        if combat_power >= enemy_power:
                            a.money[w.tier] = a.money.get(w.tier, 0) + 100
                            a.insight += 0.5
                            a.enemies_defeated = getattr(a, "enemies_defeated", 0) + 1
                            R.cultivate(a, gap, self.items)
                            
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
                                msg = f"💥 [พ่ายแพ้] 💖 [ปาฏิหาริย์แห่งรัก] {saved_by_love} กระโดดขวางวิถีกระบี่ ยอมเจ็บแทนท่าน! (ออกจากคณะเดินทางไป)"
                                msg = check_hp(msg)
                                return "อันตราย", pre_msg + msg, d
                                
                            dmg = 50
                            msg_add = ""
                            if "จ้าวเถี่ยซาน" in a.companions:
                                dmg = dmg // 2
                                msg_add = " 🛡️ จ้าวเถี่ยซานรับแรงกระแทก!"
                            a.hp -= dmg
                            a.money[w.tier] = max(0, a.money.get(w.tier, 0) - 40)
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
                                R.cultivate(a, gap, self.items)
                                a.nemeses["คุณชายมู่"]["hatred"] = min(100, h_info["hatred"] + 35)
                                msg += f" 🏆 [ชนะประลอง] เขาเสียหน้าและเกลียดท่านมากขึ้น! (Hatred: {a.nemeses['คุณชายมู่']['hatred']}/100)"
                            else:
                                a.hp -= 10
                                msg += f" 🥈 [แพ้ประลอง] เสีย -10 HP"
                                msg = check_hp(msg)
                        elif sub == "drink_tea":
                            comp = rng.choice(list(a.companions.keys()))
                            choice = rng.choice(["share_gold", "talk_martial", "ignore"])
                            if choice == "share_gold" and a.money.get(w.tier, 0) >= 50:
                                a.money[w.tier] -= 50
                                if type(a.companions[comp]) == int: a.companions[comp] = min(100, a.companions[comp] + 25)
                                msg = f"🍻 [ความสัมพันธ์] ชวน {comp} ดื่มชา 💞 (+25 Affection)"
                            elif choice == "talk_martial":
                                a.insight += 0.3
                                R.cultivate(a, gap, self.items)
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
                                msg = "🎒 คณะเดินทางเต็มแล้ว จึงได้เพียงพูดคุยแลกเปลี่ยนสุรา"
                        elif sub == "buy_weapon":
                            if a.money.get(w.tier, 0) >= 150 and a.inventory.get("อาวุธ") is None:
                                a.money[w.tier] -= 150
                                a.inventory["อาวุธ"] = "กระบี่เหล็กเย็น"
                                msg = "🛍️ สวมใส่ 'กระบี่เหล็กเย็น' สำเร็จ"
                            else:
                                msg = "🍃 พ่อค้าเร่ขาย 'กระบี่เหล็กเย็น' (ราคา 150) แต่ไม่ได้ซื้อ"
                        elif sub == "train":
                            a.insight += 0.4
                            R.cultivate(a, gap, self.items)
                            msg = "🥋 นั่งสมาธิร่วมกันในหุบเขา ได้รับ EXP"
                        
                        return "วิถียุทธ", pre_msg + msg, d

                    if rng.randint(1, 100) <= wealth:
                        if a.companions and rng.random() > 0.5:
                            comp = rng.choice(list(a.companions.keys()))
                            if a.money.get(w.tier, 0) >= 40:
                                a.money[w.tier] -= 40
                                if type(a.companions[comp]) == int: a.companions[comp] = min(100, a.companions[comp] + 20)
                                msg = f"🛍️ [ความสัมพันธ์] ซื้อสมุนไพรให้ {comp} 💞 (+20 Affection)"
                            else:
                                msg = f"🛍️ [ความสัมพันธ์] {comp} อยากได้สมุนไพรแต่เงินไม่พอ"
                            return "การค้า", pre_msg + msg, d
                            
                        msg_add = ""
                        if "ศิษย์พี่ใหญ่เซี่ย" in a.companions:
                            potion_cost = 20
                            msg_add = " 📜 ศิษย์พี่ใหญ่เซี่ยต่อราคาเหลือ 20 เงิน!"
                            
                        if a.money.get(w.tier, 0) >= potion_cost and a.inventory.get("ยาสมานแผล", 0) < 2:
                            a.money[w.tier] -= potion_cost
                            a.inventory["ยาสมานแผล"] += 1
                            msg = f"🎒 ซื้อยาสมานแผลสำเร็จ (จ่าย {potion_cost} เงิน){msg_add}"
                        else:
                            msg = f"🍃 เจอร้านขาย 'ยาสมานแผล' (ราคา {potion_cost}){msg_add} แต่ไม่ได้ซื้อ"
                            
                        return "การค้า", pre_msg + msg, d
                        
                    # ทั่วไป
                    a.hp = min(getattr(a, "max_hp", 100), getattr(a, "hp", 100) + 10)
                    msg = "🍃 คณะเดินทางเดินทางผ่านทุ่งหญ้าอย่างสงบ ฟื้นฟู +10 HP"
                    return "ความสงบ", pre_msg + msg, d
            return "ทั่วไป", f"{a.name} เดินเล่นในเมือง", d








        # --- อีเวนท์สายอาชีพใหม่ ---
        if k == "สะสมบุญบารมี":
            a.merit += rng.uniform(5.0, 15.0)
            a.moral = getattr(a, "moral", 0) + 2
            a.insight += rng.uniform(0.1, 0.5)
            R.cultivate(a, gap, self.items)
            if hasattr(a, "update_title"): a.update_title()
            return "บุญบารมี", f"{a.name}ออกโปรดสัตว์ สะสมบุญบารมีเพิ่มขึ้น", d
            
        if k == "ลาดตระเวน":
            a.money[w.tier] = a.money.get(w.tier, 0) + WAGES.fiat_pay(10)
            return "ลาดตระเวน", f"{a.name}ออกลาดตระเวนรักษาความสงบ ได้รับเบี้ยหวัด", d
            
        if k == "เปิดประมูล":
            return self.auction(a, w, rng, d)

        if k == "จับกุมอาชญากร":
            if not t: return "ล้มเหลว", "ไม่พบอาชญากร", d
            if not R.is_criminal(t):
                # ด่านสุดท้าย เผื่อ target มาจากทางอื่น (ผู้มีจิตใจเลือกเอง/ตารางเหตุการณ์)
                return "ไม่พบอาชญากร", f"{a.name}ไม่พบอาชญากรที่ต้องตามจับแถวนี้", d
            if R.power(a, w) <= R.power(t, w):
                # จับไม่สำเร็จ = จองเวรจริง (rivals) ไม่ใช่แค่ bonds ติดลบที่ไม่มีใครอ่าน
                t.rivals[a.cid] = t.rivals.get(a.cid, 0) + 1
                a.rivals[t.cid] = a.rivals.get(t.cid, 0) + 1
                return "ล้มเหลว", f"{a.name}พยายามจับกุม {t.name} แต่สู้ไม่ได้", d
            a.moral = getattr(a, "moral", 0) + 3
            if hasattr(a, "update_title"): a.update_title()
            weight = R.crime_weight(t)
            # ค่าหัวมาจากของกลางที่ยึดได้ ไม่ใช่เงินที่เกิดจากอากาศ (เดิม randint(20,100) ลอยๆ)
            loot = int(t.money.get(w.tier, 0) * 0.5)
            bounty = max(20, min(loot, 300)) if loot > 0 else rng.randint(20, 60)
            t.money[w.tier] = max(0, t.money.get(w.tier, 0) - loot)
            a.money[w.tier] = a.money.get(w.tier, 0) + bounty
            d["ของกลางที่ยึดได้"] = bounty
            if weight >= C.EXECUTE_KILLS:
                # ฆ่าคนมาแล้วหลายศพ — โทษประหาร ยังเป็นความตายที่มีเหตุให้เล่าได้
                d["ความผิด"] = f"ฆ่าคนมาแล้ว {getattr(t, 'kills', 0)} ศพ"
                self.kill(t, f"ถูกประหารตามกฎหมายโดย {a.name}", killer=a)
                return "ประหาร", f"{a.name}จับกุมและประหาร {t.name} ตามกฎหมาย " \
                                 f"(ความผิดหนัก {weight} ระดับ)", d
            lo, hi = C.JAIL_DAYS
            years = int(min(hi, lo + (hi - lo) * min(1.0, weight / float(C.EXECUTE_KILLS))) / 365)
            t.jail_until = self.day + years * 365
            t.hidden = True                 # ออกจากเวทีชั่วคราว (ทุกที่ที่กรอง hidden ข้ามให้เอง)
            t.travel_dest = -1              # ถูกจับกลางทางก็ไม่ได้ไปต่อ
            t.rivals[a.cid] = t.rivals.get(a.cid, 0) + C.JAIL_GRUDGE
            d["ความผิด"] = f"ระดับ {weight}"
            d["โทษ"] = f"คุมขัง {years} ปี"
            # **ห้าม schedule() ให้ผู้ถูกจับที่นี่** — เขามีคิวของตัวเองอยู่แล้วหนึ่งใบ การใส่เพิ่ม
            # ทำให้คนหนึ่งคนมีสองเทิร์นในคิวตลอดไป (test_autonomy/test_scheduler_integrity จับได้)
            # จังหวะแหกคุกเกิดตอนคิวเดิมของเขาถึงเอง แล้วบล็อกติดคุกใน step() จะเลื่อนไปวันพ้นโทษ
            # แต่ใบเดิมอาจอยู่หลังวันพ้นโทษ (ถูกจับตอนซ่อนตัว ซึ่งนัดเทิร์นไว้ 2,000–12,000 วัน) จึงเลื่อนใบเดิมมาไม่ให้เกิน
            # วันพ้นโทษ ไม่งั้นพ้นโทษแล้วยังค้างในคุกหลายปี คุกเลิกเลี้ยงตั้งแต่วันพ้นโทษ และคนที่ซ่อนตัวทำงานแลกข้าวไม่ได้
            # (test_law: ถูกจับ 86 วันหลังเก็บตัว เทิร์นถัดไปอยู่หลังวันพ้นโทษ 1,454 วัน อดตายในคุก 77 วันหลังพ้นโทษ)
            pending = min((when for when, cid in self.queue if cid == t.cid), default=None)
            if pending is not None and pending > t.jail_until:
                self.requeue(t, t.jail_until)
            return "คุมขัง", f"{a.name}จับกุม {t.name} ได้ ส่งเข้าคุมขัง {years} ปี " \
                             f"ยึดของกลาง {bounty}", d

        if k == "ลอบสังหาร":
            if not t: return "ล้มเหลว", "ไม่มีเป้าหมาย", d
            motive = R.assassin_motive(self, a, t)
            if motive is None:
                # ไม่มีแค้น ไม่มีคนจ้าง ก็ไม่มีเหตุจะฆ่าคนแปลกหน้าที่ยืนอยู่ข้างๆ
                return "ไม่มีเหตุให้ลงมือ", f"{a.name}ไม่มีเหตุจะลงมือกับใครแถวนี้", d
            why, client = motive
            d["เหตุที่ลงมือ"] = why
            if a.profession in ("นักบวช", "นักพรต"):
                a.karma += 50.0 # ฆ่าคนกรรมพุ่ง
            fee = 0
            if client is not None:
                fee = min(client.money.get(w.tier, 0), rng.randint(*C.ASSASSIN_FEE))
                client.money[w.tier] = client.money.get(w.tier, 0) - fee
                a.money[w.tier] = a.money.get(w.tier, 0) + fee
                client.bonds[a.cid] = client.bonds.get(a.cid, 0) + C.ASSASSIN_CLIENT_BOND
                a.bonds[client.cid] = a.bonds.get(client.cid, 0) + C.ASSASSIN_CLIENT_BOND
                client.moral = getattr(client, "moral", 0) - 3
                client.karma += 20.0
                d["ผู้ว่าจ้าง"] = f"{client.name} จ่าย {fee}"
            # โอกาสสำเร็จขึ้นกับพลัง
            if R.power(a, w) * 1.5 > R.power(t, w):
                self.kill(t, f"ถูกลอบสังหารโดย {a.name}", killer=a)
                a.moral = getattr(a, "moral", 0) - 5
                if hasattr(a, "update_title"): a.update_title()
                if client is not None:
                    client.rivals.pop(t.cid, None)   # แค้นของผู้ว่าจ้างจบลงพร้อมกับเป้าหมาย
                d["สังหาร"] = f"{t.name} ถูกลิดรอนวิญญาณ"
                return "สังหาร", f"{a.name}ลอบสังหาร {t.name} สำเร็จ ({why})", d
            else:
                t.rivals[a.cid] = t.rivals.get(a.cid, 0) + 3   # รู้ตัวแล้วว่าใครจะเอาชีวิต
                t.bonds[a.cid] = min(-10, t.bonds.get(a.cid, 0) - 50)
                return "ล้มเหลว", f"{a.name}ลอบสังหาร {t.name} พลาด โดนหมายหัวกลับ", d

        if k == "ดักปล้น":
            if not t: return "ล้มเหลว", "ไม่มีเป้าหมาย", d
            if R.power(a, w) > R.power(t, w):
                stolen = t.money.get(w.tier, 0) // 2
                t.money[w.tier] = t.money.get(w.tier, 0) - stolen
                a.money[w.tier] = a.money.get(w.tier, 0) + stolen
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
            if t.money.get(w.tier, 0) >= fee:
                t.money[w.tier] -= fee
                a.money[w.tier] = a.money.get(w.tier, 0) + fee
            return "ทำนาย", f"{a.name}ตรวจดวงชะตาให้ {t.name} ชี้แนะหนทาง", d

        if k == "ขายข่าวลับ":
            if not t: return "ล้มเหลว", "ไม่มีลูกค้า", d
            fee = rng.randint(10, 50)
            if t.money.get(w.tier, 0) >= fee:
                t.money[w.tier] -= fee
                a.money[w.tier] = a.money.get(w.tier, 0) + fee
                t.bonds[a.cid] = max(0, t.bonds.get(a.cid, 0) + 10)
                return "ข่าวลับ", f"{a.name}ขายข้อมูลสำคัญให้ {t.name}", d
            return "ล้มเหลว", f"{t.name}ไม่มีเงินจ่ายค่าข่าวให้ {a.name}", d


        if k == "บำเพ็ญ":
            pv = self.place_of(a)
            if a.race() == "อสูร":
                boost = 1.0 + (w.tier * 0.5)
                if pv and pv[2] >= 2:
                    boost += 1.0
                R.cultivate(a, gap * boost, self.items)
            else:
                R.cultivate(a, gap, self.items)
            if pv and pv[3] == "ลานฝึก":
                a.insight += 0.4
                d["ลานฝึก"] = self.place_name(a)
            if w.tier == 0 and w.defense_array < w.defense_max and a.realm >= 2 and rng.random() < 0.4:
                restore = rng.uniform(2, 5)
                w.defense_array = min(w.defense_max, w.defense_array + restore)
                d["ซ่อมค่ายกล"] = f"เสริมพลังค่ายกลโลก (+{restore:.1f}) เหลือ {w.defense_array:.1f}/{w.defense_max:.1f}"
            # ตกผลึกปราณส่วนเกินเป็นหินวิญญาณ — ทางเดียวที่ **คนไม่มีเงินสร้างทุนได้เอง**
            # เงื่อนไข: ที่ตรงนี้ต้องเลี้ยงเขาได้เกินขั้นที่เขายืนอยู่ ส่วนเกินนั้นเท่านั้น
            # ที่ตกผลึกได้ คนที่ยึดขั้นสูงเกินแผ่นดินใต้เท้าจึงไม่มีวันเก็บทุนได้เลย
            # ต้องย้ายหรือยอมลง — ซึ่งเป็นแรงผลักให้คนออกเดินทางหาที่ที่ดีกว่า
            rho = self.qi_density(a.place, w)
            spare = EC.place_ceiling(rho) - a.realm
            if spare > 0 and w.heaven > 0:
                crop = min(EC.upkeep_qi(a.realm) * spare * C.CONDENSE_RATE * (gap / 365.0),
                           max(0.0, w.heaven))
                if crop > 0:
                    w.heaven -= crop
                    a.qi_taken = getattr(a, "qi_taken", 0.0) + crop
                    grade = min(len(EC.GRADE_NAMES) - 1, w.tier)
                    EC.add_stones(a, grade, EC.mint(crop, grade))
                    d["ตกผลึก"] = (f"{EC.grade_name(grade)} +{EC.mint(crop, grade):.2f} ก้อน "
                                   f"(ที่นี่เลี้ยงได้ถึงขั้น {EC.place_ceiling(rho):.1f})")
            return "บำเพ็ญ", f"{a.name}เก็บตัวบำเพ็ญที่{self.place_name(a)}", d

        if k == "ขัดเกลาสายเลือด":
            R.refine_blood(a, gap)
            return "ขัดเกลา", f"{a.name}ขัดเกลาสายเลือด{a.race()}ของตน", d

        if k == "ข้ามขั้น":
            # ยังสะสมไม่พอไม่ควรกินยาเสียเปล่า
            if R.accumulation(a) < R.need(a, w):
                R.cultivate(a, gap, self.items)
                return "สะสมต่อ", f"{a.name}รู้ว่ายังไม่ถึงเวลา จึงบำเพ็ญต่อ", d
            pills = [i for i in a.items if self.items[i].kind == "ยาวิเศษ"]
            use, pname = 0.0, None
            if pills:
                best = max(pills, key=lambda i: getattr(self.items[i], "pill_bonus", 0.1))
                use = getattr(self.items[best], "pill_bonus", 0.1) / C.PILL_BREAK_BONUS
                pname = self.items[best].name
                a.items.remove(best)
                a.longevity_bonus += getattr(self.items[best], "lifespan_bonus", 0)
            res, txt = R.attempt_break(self, a, w, rng, pills=use)
            if res == "ยังไม่ถึง":
                R.cultivate(a, gap, self.items)
                return "สะสมต่อ", f"{a.name}รู้ว่ายังไม่ถึงเวลา จึงบำเพ็ญต่อ", d
                
            # `attempt_break` คืนสตริง "ผ่าน" เมื่อสำเร็จ ไม่เคยคืน True เลย (ดู rules.py บรรทัดสุดท้าย
            # ของฟังก์ชัน) เงื่อนไข `res is True` เดิมจึงเป็นเท็จเสมอ — บล็อกความสัมพันธ์ศิษย์-อาจารย์
            # ทั้งก้อนนี้ไม่เคยทำงานเลยสักครั้งตั้งแต่เขียนมา ทั้งการเนรคุณสังหารอาจารย์ การแยกตัว
            # ไปตั้งสาขา และการยอมให้อาจารย์เป็นผู้อาวุโส (วัดจริง: ข้ามขั้นสำเร็จ 39 จาก 50 ครั้ง
            # คืนค่า "ผ่าน" ทุกครั้ง ไม่มี True สักครั้งเดียว)
            if res == "ผ่าน":
                # evaluate_master_relationship
                if a.master_cid != -1 and 0 <= a.master_cid < len(self.cast):
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
            # ผู้บำเพ็ญขั้นสูงย่อมเก็บวิชาชั้นรองไว้ด้วย ไม่ใช่รู้แต่วิชาสูงสุดอย่างเดียว
            # (วัดจริง: วิชาต่อคนพีคที่ขั้น 2-3 แล้วกลับ "ลดลง" ที่ขั้น 4+ ซึ่งกลับหัวกับนิยาย
            #  เพราะขั้นสูงถูกบังคับให้เล็งแต่วิชาขั้น 2 ที่ต้องมีลานฝึกและสำเร็จยากกว่า)
            grade = rng.choice([grade, max(0, grade - 1), max(0, grade - 1), max(0, grade - 2)])
            pool = [x for x in SK.by_tier_grade(min(a.tier, 2), grade)
                    if x[0] not in a.skills]
            # ฝึกของเดิมให้ลึกขึ้น — ทางที่เคยไม่มีอยู่เลย วิชาเคยเป็น binary มีหรือไม่มี
            # ฝึกวิชาที่มีอยู่แล้วจึงไม่ได้อะไร ต้องไปหาวิชาใหม่ท่าเดียว ผลคือวัดจริงโลก 50 ปี
            # วิชาต่อคนเฉลี่ย 0.95 และ 1,020 จาก 2,184 คนไม่มีวิชาเลย (47%) ในโลกบำเพ็ญ
            # ตอนนี้ "หนึ่งวิชาฝึกสี่สิบปี" เป็นเส้นทางที่เลือกได้จริง (ดู physics.practice_mastery)
            # คนที่มีวิชาน้อยยังควรหาของใหม่ก่อน คนที่มีหลายวิชาแล้วถึงค่อยเลือกฝึกให้ลึก
            # (ตั้งเป็นค่าคงที่ตอนแรกแล้ววัดได้ว่าวิชาต่อคนลดจาก 0.95 เหลือ 0.76 เพราะการฝึกลึก
            #  ไปแย่งโอกาสการเรียนของใหม่มาตั้งแต่วิชาแรก)
            _dp = C.DEEPEN_W * min(1.0, len(a.skills) / C.DEEPEN_AFTER)
            if a.skills and (not pool or rng.random() < _dp):
                _mast = a.mastery if isinstance(getattr(a, "mastery", None), dict) else {}
                a.mastery = _mast
                name = min(a.skills, key=lambda n: (_mast.get(n, 0), n))
                reps = _mast.get(name, 0)
                before = PHYS.practice_mastery(reps, C.PRACTICE_EXPONENT)
                _mast[name] = reps + 1
                from . import body as BODY
                BODY.train(a, 0.75)
                after = PHYS.practice_mastery(reps + 1, C.PRACTICE_EXPONENT)
                a.insight += C.DEEPEN_INSIGHT * (after - before) * 10.0
                d["ฝึกซ้ำ"] = f"{name} — ครั้งที่ {reps + 1}"
                d["ความชำนาญ"] = f"{before:.0%} -> {after:.0%}"
                d["p"] = 1.0
                return "ลึกขึ้น", f"{a.name}ฝึก{name}ซ้ำจนเข้าใจลึกกว่าเดิม", d
            if not pool:
                R.cultivate(a, gap, self.items)
                return "ไม่มีวิชาให้ฝึก", f"{a.name}หาวิชาใหม่ฝึกไม่ได้ จึงบำเพ็ญต่อ", d
            pv = self.place_of(a)
            if grade == 2 and not (pv and pv[3] in ("ลานฝึก", "สำนัก", "แดนต้องห้าม")):
                R.cultivate(a, gap, self.items)
                return "ไม่มีที่ฝึก", f"{a.name}หาที่ฝึกวิชาขั้นสูงไม่ได้ที่{self.place_name(a)}", d
            if grade == 2 and not self.route_to_building(a, ("dojo",)):
                return "เดินไปลานฝึก", f"{a.name}มุ่งหน้าไปยังลานประลองยุทธ์กลาง{self.place_name(a)}", d
            # แต่ละแดนถนัดคนละทาง — สยามเน้นกาย ชมพูทวีปเน้นจิต ฯลฯ (ดู paths.REALM_BODY_BIAS)
            # เป็นการ "เอน" ไม่ใช่บังคับ คนสยามที่ไปฝึกสายจิตจนสมดุลก็ยังมีอยู่จริง
            # สาขาแต่ละแห่งมีวิชาประจำแดนของตัวเอง คนในนั้นจึงฝึกไปคนละทางกับสาขาอื่นจริงๆ
            # การเลือกวิชาเป็นการ "แคบเข้าแล้วค่อยเลือก" ขั้นเดียวกันทั้งสามชั้น:
            # สายประจำแดน -> ทางที่แดนนั้นถนัด -> ธาตุประจำตัว  ชั้นหลังเลือก **ภายในกอง
            # ที่ชั้นก่อนแคบไว้แล้ว** ไม่ใช่เริ่มนับหนึ่งใหม่จากทั้งกอง
            #
            # บั๊กเดิม: เลือกวิชาสายประจำแดนมาแล้ว บรรทัดถัดมา EL.best_of(pool, ...) ไปหยิบ
            # จาก `pool` ทั้งก้อนแล้วเขียนทับ ด้วย ELEMENT_PICK_P = 0.7 การเอนของแดน
            # (BRANCH_SKILL_BIAS = 0.55) จึงเหลือผลจริงแค่ราว 30% วัดจริงที่ 60,000 เหตุการณ์:
            # มีแค่ 10 จาก 41 สาขา (24%) ที่วิชาประจำแดนเด่นเกิน 15% ของวิชาที่คนในแดนรู้
            # — "สามพันโลก" ที่ผลิตคนแบบเดียวกันหมด ซึ่งเป็นสิ่งเดียวที่ทำให้สาขาต่างกัน
            # การเลือกวิชาเป็นการ "แคบเข้าแล้วค่อยเลือก" ชั้นธาตุจึงต้องเลือก **ภายในกองที่
            # ชั้นก่อนหน้าแคบไว้แล้ว** ไม่ใช่เริ่มนับหนึ่งใหม่จากทั้งกองแล้วลบผลของชั้นก่อนทิ้ง
            #
            # บั๊กเดิม: เลือกวิชาสายประจำแดนมาแล้ว บรรทัดถัดมา EL.best_of(pool, ...) หยิบจาก
            # `pool` ทั้งก้อนมาเขียนทับ ด้วย ELEMENT_PICK_P = 0.7 การเอนของแดน
            # (BRANCH_SKILL_BIAS = 0.55) จึงเหลือผลจริงราว 30% วัดจริงที่ 60,000 เหตุการณ์:
            # มีแค่ 10 จาก 41 สาขา (24%) ที่วิชาประจำแดนเด่นเกิน 15% ของวิชาที่คนในแดนรู้
            # — "สามพันโลก" ที่ผลิตคนแบบเดียวกันหมด ทั้งที่วิชาประจำแดนคือสิ่งเดียวที่ทำให้สาขาต่างกัน
            line = getattr(w, "skill_line", None)
            same_line = [x for x in pool if x[1] == line] if line else []
            if line and rng.random() < C.BRANCH_SKILL_BIAS and same_line:
                # สายประจำแดนไม่มีวิชาที่เขาเรียนได้ตอนนี้ ก็ต้องปล่อยให้ไปทางอื่น ไม่ใช่ติดตาย
                choice_pool = same_line
            else:
                choice_pool = PATHS.prefer_pool(pool, w.place_key, rng)
                same_line = []          # รอบนี้ไม่ได้เลือกด้วยสายประจำแดน
            sk = rng.choice(choice_pool)
            # ห้าธาตุ: คนไม่ได้หยิบวิชามั่วๆ เขามองหาวิชาที่ "ถูกกับธาตุของตัวเอง" ก่อน
            # ก่อนหน้านี้การเลือกวิชาเป็นการสุ่มล้วน ฝึกพลาดจึงเป็นลูกเต๋าล้วนๆ ด้วย
            # (วัดจริง: ฝึกพลาด 60 จาก 137 ครั้ง = 44% ของการกระทำที่ถูกเลือกมากที่สุดในโลก)
            _el = EL.ensure(a)
            if rng.random() < C.ELEMENT_PICK_P:
                # ถ้ารอบนี้เอนไปทางสายประจำแดนแล้ว ให้ถามคำถามที่แคบลงว่า "วิชา**สายนี้**
                # อันไหนถูกกับธาตุข้าที่สุด" ธาตุยังสำคัญเท่าเดิม แต่ไม่ลบสายประจำแดนทิ้ง
                # แดนหลักที่ไม่มีสายประจำแดนยังเลือกจากทั้งกองเหมือนเดิมทุกประการ
                sk = EL.best_of(same_line or pool, _el)[0]
            _aff = EL.affinity(_el, EL.skill_element(sk[0]))
            p = C.LEARN_BASE_P + 0.05 * (a.realm - SK.GRADE_REALM_BAR[grade]) \
                - 0.12 * grade - a.decay * 0.05 + C.ELEMENT_LEARN_W * _aff
            d["ธาตุของวิชา"] = (f"{EL.skill_element(sk[0])} · {EL.relation_words(_el, EL.skill_element(sk[0]))}"
                                 f" — {'ถูกทางกับข้า' if _aff > 0.5 else 'พอไปด้วยกันได้' if _aff > 0 else 'ขัดกับธาตุของข้า'}")
            _pw = max(0.05, min(0.95, p))
            d["p"] = _pw
            if rng.random() > _pw:
                from . import body as BODY
                BODY.train(a, 0.45)  # ฝึกพลาดก็ยังลงแรง แม้ความเข้าใจยังไม่สำเร็จ
                a.decay += C.LEARN_BACKFIRE * (0.5 + 0.4 * grade)
                # ฝึกพลาดก็ได้บทเรียน — ไม่มากเท่าสำเร็จ แต่ไม่ใช่เสียเปล่าทั้งหมด
                a.insight += C.TRAIN_FAIL_INSIGHT
                d["ที่ได้กลับมา"] = "บทเรียนจากความผิดพลาด"
                return "ฝึกพลาด", f"{a.name}ฝึก{sk[0]}ไม่สำเร็จ ธาตุไฟเข้าแทรก", d
            # การฝึกวิชาสำเร็จเคย **ไม่ให้ความก้าวหน้าในการบำเพ็ญเลย** ให้แค่ชื่อวิชาในรายการ
            # (มีแต่กิ่งที่ฝึกไม่ได้ ที่เรียก cultivate() แทน) วัดจริงจากบันทึกผู้มีจิตใจ 48 ปี:
            # "ฝึกวิชา" เป็นการกระทำที่ถูกเลือกมากที่สุด 66/270 ครั้ง (24%) — คนเก่งที่สุดในโลก
            # จึงยังอยู่แค่ขั้นหลอมกระดูกหลังผ่านไปครึ่งศตวรรษ เพราะเวลาหนึ่งในสี่ของชีวิตเขา
            # หมดไปกับสิ่งที่ไม่ขยับด่านทั้งสองของการข้ามขั้นแม้แต่นิดเดียว
            # ในเชิงเรื่อง การเข้าถึงวิชาชั้นสูงคือการเข้าถึง "ทาง" — ต้องได้ทั้งความเข้าใจและกาย
            a.insight += C.TRAIN_INSIGHT_BASE + C.TRAIN_INSIGHT_PER_GRADE * grade
            a.refine += C.TRAIN_REFINE * (1.0 + 0.5 * grade)
            a.learn_skill(sk[0])        # เรียนจบครั้งแรก = ฝึกไปแล้วหนึ่งครั้ง
            from . import body as BODY
            BODY.train(a, 1.0 + 0.25 * grade)
            d["วิชา"] = f"{SK.GRADE_NAME[sk[3]]} · สาย{sk[1]} — {sk[4]}"
            d["ทาง"] = f"{PATHS.skill_path(sk[0])}บำเพ็ญ · ตอนนี้เป็น{PATHS.path_of(a)}"
            d["ที่ฝึก"] = self.place_name(a)
            req = SK.REQUIREMENTS.get(sk[0])
            if req:
                d["เงื่อนไข"] = req
            if sk[5]:
                d["แก้ทางโกลาหล"] = "วิชานี้แก้ทางเผ่าโกลาหลได้"
            return "สำเร็จ", f"{a.name}ฝึก{sk[0]}สำเร็จ", d
        if k == "ทำนา":
            earn = WAGES.fiat_pay(rng.randint(5, 15))
            a.money[w.tier] = a.money.get(w.tier, 0) + earn
            return "สำเร็จ", f"{a.name}ทำนาได้ผลผลิต", {"เงินที่ได้": earn}
        if k == "ค้าขายทั่วไป":
            earn = WAGES.fiat_pay(rng.randint(20, 50))
            a.money[w.tier] = a.money.get(w.tier, 0) + earn
            return "สำเร็จ", f"{a.name}ค้าขายทั่วไปได้กำไร", {"เงินที่ได้": earn}
        if k == "ตีเหล็กชาวบ้าน":
            earn = WAGES.fiat_pay(rng.randint(10, 30))
            a.money[w.tier] = a.money.get(w.tier, 0) + earn
            a.mats += 1
            return "สำเร็จ", f"{a.name}ตีเหล็กชาวบ้านขาย", {"เงินที่ได้": earn}
        if k == "รักษาชาวบ้าน":
            earn = WAGES.fiat_pay(rng.randint(10, 40))
            a.money[w.tier] = a.money.get(w.tier, 0) + earn
            a.decay = max(0.0, a.decay - 0.1)
            return "สำเร็จ", f"{a.name}รักษาชาวบ้าน", {"เงินที่ได้": earn}
        if k == "ปกป้องชาวบ้าน":
            earn = WAGES.fiat_pay(rng.randint(30, 80))
            a.money[w.tier] = a.money.get(w.tier, 0) + earn
            if rng.random() < 0.2:
                a.mat_stock["ศิลาปราณห้าธาตุ"] = a.mat_stock.get("ศิลาปราณห้าธาตุ", 0) + 1
            return "สำเร็จ", f"{a.name}ปกป้องชาวบ้านจากภัยร้าย", {"เงินที่ได้": earn, "ผลลัพธ์": "ชาวบ้านซาบซึ้ง"}
        if k == "ขูดรีดชาวบ้าน":
            earn = WAGES.fiat_pay(rng.randint(50, 150))
            a.money[w.tier] = a.money.get(w.tier, 0) + earn
            a.decay += 0.2
            if "มารในใจ" not in a.traits:
                a.traits.append("มารในใจ")
            return "สำเร็จ", f"{a.name}ขูดรีดชาวบ้านอย่างโหดเหี้ยม", {"เงินที่ได้": earn, "ผลลัพธ์": "สร้างความแค้น"}


        if k == "เก็บวัตถุดิบ":
            # การเก็บของโดยเฉพาะ — แยกจาก "ล่าอสูร" ที่เป็นการต่อสู้และมีสิทธิตาย
            # นี่คือกิจวัตรของช่างหลอม/นักปรุงยา และเป็นทางเดียวที่จะได้ของชิ้นที่ตัวเองตามหา
            pool = MAT.materials_at(a.place)
            if not pool and not MAT.is_core_site(a.place):
                return ("ไม่มีอะไรให้เก็บ",
                        f"{a.name}มองหาวัตถุดิบที่{self.place_name(a)} แต่ที่นี่ไม่มีอะไรให้เก็บ", d)
            eco = self.eco_ratio(a.place)
            if not pool:
                # แหล่งแก่นพลัง — เก็บแก่นจากซากอสูรโดยไม่ต้องออกล่าเอง (ไม่มีความเสี่ยงตาย
                # แต่ได้น้อยกว่าล่าจริง) ก่อนหน้านี้ 9 แหล่งนี้ไม่มีทางเก็บอะไรได้เลย
                got_cores = max(1, round(rng.randint(*C.GATHER_CORE_PER_TRIP) * eco))
                a.cores += got_cores
                self.eco_harvest(a.place, float(got_cores))
                d["เก็บได้"] = f"แก่นพลัง×{got_cores}"
                # สายหินวิญญาณที่แทรกอยู่ในแหล่งแก่นพลัง — ขุดขึ้นมาก็คือดูดปราณออกจากโลก
                if rng.random() < C.VEIN_FIND_P and w.heaven > 0:
                    vein = min(C.VEIN_QI * eco * (1.0 + a.fate * C.VEIN_FATE), w.heaven)
                    w.heaven -= vein
                    grade = min(len(EC.GRADE_NAMES) - 1, w.tier)
                    EC.add_stones(a, grade, EC.mint(vein, grade))
                    d["สายหินวิญญาณ"] = f"{EC.grade_name(grade)} ×{EC.mint(vein, grade):.1f}"
                d["ที่"] = self.place_name(a)
                if rng.random() < 0.35:
                    a.mat_stock["โลหิตอสูรกลั่น"] = a.mat_stock.get("โลหิตอสูรกลั่น", 0) + 1
                    d["ของพิเศษ"] = "โลหิตอสูรกลั่น"
                return ("เก็บได้", f"{a.name}เก็บแก่นพลัง {got_cores} เม็ดที่{self.place_name(a)}", d)
            n = max(1, round(rng.randint(*C.GATHER_PER_TRIP) * eco))
            got = {}
            wanted_here = [m for m in getattr(a, "wants", ()) if m in pool]
            for _ in range(n):
                # ถ้ากำลังตามหาของชิ้นไหนอยู่และที่นี่มี ก็จะเพ่งหาชิ้นนั้นเป็นหลัก
                if wanted_here and rng.random() < C.GATHER_FOCUS_P:
                    pick = rng.choice(wanted_here)
                else:
                    pick = MAT.roll_material(a.place, rng, eco)
                if not pick:
                    continue
                a.mat_stock[pick] = a.mat_stock.get(pick, 0) + 1
                got[pick] = got.get(pick, 0) + 1
                if a.wants.get(pick):
                    left = a.wants[pick] - 1
                    if left > 0:
                        a.wants[pick] = left
                    else:
                        a.wants.pop(pick, None)
            self.eco_harvest(a.place, float(n))
            if not got:
                return "มือเปล่า", f"{a.name}ออกเก็บวัตถุดิบแต่กลับมามือเปล่า", d
            d["เก็บได้"] = ", ".join(f"{m}×{q}" for m, q in got.items())
            d["ที่"] = self.place_name(a)
            if eco < 0.5:
                d["สภาพแหล่ง"] = "เริ่มร่อยหรอ"
            if a.wants:
                d["ยังตามหา"] = ", ".join(list(a.wants)[:3])
            return ("เก็บได้", f"{a.name}เก็บ{d['เก็บได้']}ที่{self.place_name(a)}", d)

        if k == "ล่าอสูร":
            pv = self.place_of(a)
            eco = self.eco_ratio(a.place)
            n = max(1, round(rng.randint(*C.CORE_PER_HUNT) * eco))
            if pv and pv[4] == "แก่นพลัง":
                n += 2
            a.cores += n
            # ล่าอสูรเคยให้แต่ของ (แก่นพลัง/วัตถุดิบ) ไม่ให้ความก้าวหน้าเลย ทั้งที่การปะทะของจริง
            # และการกลั่นแก่นพลังคือสายกายของแนวนิยายนี้โดยตรง — เป็นเหตุผลอีกข้อที่โลกไต่ขั้นไม่ขึ้น
            a.refine += min(C.HUNT_REFINE_CAP, C.HUNT_REFINE_PER_CORE * n)
            a.insight += C.HUNT_INSIGHT
            got = max(1, round(rng.randint(1, 4) * eco))
            a.mats += got
            self.eco_harvest(a.place, got + n * 0.3)

            if rng.random() < 0.4:
                a.mat_stock["โลหิตอสูรกลั่น"] = a.mat_stock.get("โลหิตอสูรกลั่น", 0) + rng.randint(1, 2)
                d["ของพิเศษ"] = "โลหิตอสูรกลั่น"
            if rng.random() < 0.3:
                a.mat_stock["ศิลาปราณห้าธาตุ"] = a.mat_stock.get("ศิลาปราณห้าธาตุ", 0) + rng.randint(1, 3)
                d["ของพิเศษ"] = (d.get("ของพิเศษ", "") + " ศิลาปราณห้าธาตุ").strip()
            # ชิ้นส่วนหายากจากซากอสูร — config.MATERIAL_KINDS เคยนิยามไว้เฉยๆ ไม่มีใครอ่าน
            if MAT.BEAST_PARTS and rng.random() < C.BEAST_PART_P:
                part = rng.choice(MAT.BEAST_PARTS)
                a.mat_stock[part] = a.mat_stock.get(part, 0) + 1
                d["ของพิเศษ"] = (d.get("ของพิเศษ", "") + " " + part).strip()

            if pv and pv[4] in ("แร่", "สมุนไพร"):
                # ของที่ได้ต้องคู่ควรกับระดับโลกและเกรดของแหล่ง — เดิมสุ่มจากตารางราคาทั้งก้อน
                # ถ้ำหินแกรนิตดิบในโลกมนุษย์จึงเคยออกแร่ระดับสวรรค์ได้
                pick = MAT.roll_material(a.place, rng, eco)
                if pick:
                    a.mat_stock[pick] = a.mat_stock.get(pick, 0) + 1
                    self.eco_harvest(a.place, 1.0)
                    tail = " (แหล่งนี้เริ่มร่อยหรอ)" if eco < 0.5 else ""
                    d["เก็บได้"] = f"{pick} ที่{self.place_name(a)}{tail}"
                    if a.wants.get(pick):
                        left = a.wants[pick] - 1
                        if left > 0:
                            a.wants[pick] = left
                        else:
                            a.wants.pop(pick, None)
                        d["ของที่ตามหา"] = pick
            a.money[w.tier] = a.money.get(w.tier, 0.0) + n * 2.0
            if rng.random() < 0.10 and a.fate <= 0:
                self.kill(a, "ตายในการล่าอสูร")
                return "ตาย", f"{a.name}ตายในการล่าอสูร", d
            return "ได้แก่นพลัง", f"{a.name}ล่าอสูรได้แก่นพลัง {n} เม็ด", d

        if k == "หลอมค่ายกล":
            # ผู้ที่รู้สายหุ่นกลใช้เตาเดียวกันหลอม "หุ่น" แทน "ค่ายกล" — ไม่ต้องเพิ่มชนิดเหตุการณ์
            # ใหม่ในตาราง เพราะทั้งสองอย่างคืองานช่างที่ใช้เตาหลอมเหมือนกัน
            got = self.build_puppet(a, w, rng, d)
            if got is not None:
                return got
            pv = self.place_of(a)
            furnace = pv[5] if pv else -1
            if furnace < 0:
                return "ไม่มีเตา", f"{a.name}อยากหลอมค่ายกล แต่{self.place_name(a)}ไม่มีเตาหลอม", d
            tier = min(a.tier, 2)
            ready_tools = MAT.array_tools_ready(a.mat_stock, tier)
            if not ready_tools:
                target, lack = MAT.plan_array_shortfall(a.mat_stock, tier)
                for name, n in lack.items():
                    a.wants[name] = max(a.wants.get(name, 0), n)
                d["ตั้งใจจะหลอม"] = target
                d["ยังขาด"] = ", ".join(f"{n}×{q}" for n, q in lack.items())
                return ("ขาดวัตถุดิบ",
                        f"{a.name}อยากหลอม{target} แต่ยังขาด{d['ยังขาด']}", d)
            fur = MAT.furnace_of(a.place)
            if fur:
                d["เตาที่ใช้"] = f"{fur[0]} ที่{self.place_name(a)}"
            recipe = rng.choice(ready_tools)
            reqs = MAT.array_mats(recipe, tier)
            MAT.consume(a.mat_stock, reqs)
            d["วัตถุดิบที่ใช้"] = MAT.describe(reqs)
            if rng.random() > C.ARRAY_CRAFT_P:
                return "ล้มเหลว", f"{a.name}หลอม{recipe}ล้มเหลว วัตถุดิบสูญเปล่า", d
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
            if not self.route_to_building(a, ("craft",)):
                return "เดินไปเตาหลอม", f"{a.name}มุ่งหน้าไปยังเตาหลอมกลาง{self.place_name(a)}", d
            fur = MAT.furnace_of(a.place)
            fur_grade = fur[2] if fur else 0
            d["เตาที่ใช้"] = (f"{fur[0]} ที่{self.place_name(a)}" if fur
                              else f"{self.place_name(a)} (เตาระดับ {furnace})")
            if a.cores < C.CRAFT_CORE_COST:
                return "ขาดวัตถุดิบ", f"{a.name}อยากลง{k}แต่แก่นพลังไม่พอ", d
            table = CR.PILLS if is_pill else CR.WEAPONS
            pool = [x for x in table if CR.can_make(rk, x[1], x[2]) and x[1] <= furnace]
            if not pool:
                return "ทำไม่ได้", f"{a.name}ฝีมือยังไม่ถึงจะลง{k}ชิ้นใด", d
            pool.sort(key=lambda x: -(x[1] * 3 + x[2]))
            # เลือกเฉพาะสูตรที่มีวัตถุดิบครบจริง — ของดีที่สุดที่ "ทำได้ตอนนี้"
            ready = [x for x in pool if MAT.can_afford(a.mat_stock, MAT.recipe_mats(x[0]))]
            if not ready:
                # ทำไม่ได้เพราะขาดของ — จำไว้ว่าขาดอะไร แล้วออกไปหา/ไปซื้อ (ดู intent.py)
                target = pool[0]
                lack = MAT.shortfall(a.mat_stock, MAT.recipe_mats(target[0]))
                for name, n in lack.items():
                    a.wants[name] = max(a.wants.get(name, 0), n)
                if len(a.wants) > C.WANT_MAX:
                    for name in list(a.wants)[:-C.WANT_MAX]:
                        a.wants.pop(name, None)
                d["ตั้งใจจะหลอม"] = target[0]
                d["ยังขาด"] = ", ".join(f"{n}×{q}" for n, q in lack.items())
                where = [PL.PLACES[i][0] for i in MAT.sources_of(next(iter(lack), ""))][:2]
                if where:
                    d["หาได้ที่"] = ", ".join(where)
                return ("ขาดวัตถุดิบ",
                        f"{a.name}อยากหลอม{target[0]} แต่ยังขาด{d['ยังขาด']}", d)
            recipe = ready[0] if rng.random() < 0.35 else rng.choice(ready)
            # ลงเตาหนึ่งครั้ง = หลอมได้หลายชิ้นจนกว่าวัตถุดิบหรือแก่นพลังจะหมด ไม่ใช่ชิ้นเดียวจบ
            # ตัวละครหนึ่งคนได้ลงมือแค่ราว 30 ครั้งตลอดชีวิต ถ้าเข้าเตาทั้งทีได้ชิ้นเดียว
            # ของทั้งโลกก็จะมีอยู่ไม่กี่สิบชิ้นตลอดกาล (วัดจริงคือ ~50 ชิ้นใน 15,000 วัน)
            # ของยิ่งสูงชั้นยิ่งหลอมได้น้อยชิ้นต่อเตา — ของสามัญเท่านั้นที่ทำเป็นล็อตได้
            batch_cap = max(1, C.CRAFT_MAX_BATCH - recipe[1] * 2 - recipe[2])
            made, failed, lvl = [], 0, getattr(a, "alchemy" if is_pill else "forge")
            reqs = MAT.recipe_mats(recipe[0])
            used = 0
            while len(made) + failed < batch_cap:
                if a.cores < C.CRAFT_CORE_COST or not MAT.can_afford(a.mat_stock, reqs):
                    break
                MAT.consume(a.mat_stock, reqs)
                a.cores -= C.CRAFT_CORE_COST
                used += 1
                lvl += C.CRAFT_GAIN
                p_ok = min(0.92, C.CRAFT_BASE_P + 0.10 * (rk - recipe[1] * 3 - recipe[2])
                           + 0.05 * lvl + C.FURNACE_GRADE_BONUS * fur_grade)
                if rng.random() > max(0.05, p_ok):
                    failed += 1
                    continue
                if is_pill:
                    it = self.make_item("ยาวิเศษ", recipe[1], 1.0 + recipe[4] * 4, maker=a.cid)
                    it.name = recipe[0]
                    it.power_desc = recipe[3]
                    it.pill_bonus = recipe[4]
                    it.lifespan_bonus = CR.longevity_years(recipe[0], recipe[1], recipe[2])
                else:
                    it = self.make_item("อาวุธวิเศษ", recipe[1], recipe[3], maker=a.cid)
                    it.name = recipe[0]
                a.items.append(it.iid)
                made.append(it.iid)
            setattr(a, "alchemy" if is_pill else "forge", lvl)
            if used:
                d["วัตถุดิบที่ใช้"] = MAT.describe([(m, q * used) for m, q in reqs])
            if not made:
                return ("ล้มเหลว",
                        f"{a.name}หลอม{recipe[0]}ล้มเหลว {failed} ครั้ง วัตถุดิบสูญเปล่า", d)
            d["ได้ของ"] = f"{recipe[0]}×{len(made)}" if len(made) > 1 else recipe[0]
            if failed:
                d["เสียไประหว่างหลอม"] = failed
            # เลื่อนขั้นช่างเมื่อสั่งสมพอ
            need = (rk + 1) * CR.RANK_XP
            if lvl >= need and rk < 8:
                if is_pill:
                    a.alch_rank += 1
                    d["เลื่อนขั้นช่าง"] = CR.ALCHEMY_RANKS[a.alch_rank]
                else:
                    a.forge_rank += 1
                    d["เลื่อนขั้นช่าง"] = CR.FORGE_RANKS[a.forge_rank]
            tail = f" {len(made)} ชิ้น" if len(made) > 1 else ""
            return "สำเร็จ", f"{a.name}หลอม{recipe[0]}สำเร็จ{tail}", d

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
                    a.learn_skill(frag["skill"])
                    # ดัชนีวิชาอยู่ใน rules ไม่ใช่ skills — SK.SKILL_INDEX ไม่เคยมีอยู่จริง
                    # กิ่งนี้จึงโยน AttributeError ล้มทั้งซิมทุกครั้งที่มีคนต่อเศษวิชาครบ
                    # (หายากมากจนไม่เคยโผล่ในเทสต์: FRAGMENT_FIND_P = 0.03 ต่อชิ้น คูณสี่ชิ้น)
                    sk = R.SKILL_INDEX.get(frag["skill"])
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
                # กฎของโลก: แดนลับมีของเสมอ ต่างกันแค่มากหรือน้อย — ไม่มีแดนลับที่ยังผนึกอยู่
                # ให้เปิด ก็ยังมี "ซาก" ของแดนลับรุ่นก่อนที่ถูกกวาดไปแล้วให้เก็บตก
                out, text = self.ruined_cache_find(a, rng, d)
                return out, text, d
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

        if k == "จำลองอนาคต":
            if not getattr(a, "system_foresight", False):
                return "ไม่มีระบบ", f"{a.name}ไม่มีวิถีหยั่งรู้อนาคตอยู่ในตัว", d
            last = a.visions[-1]["day"] if a.visions else -10 ** 9
            if self.day - last < C.FORESIGHT_COOLDOWN_DAYS:
                left = C.FORESIGHT_COOLDOWN_DAYS - (self.day - last)
                return "ยังไม่ถึงเวลา", f"{a.name}เพ่งมองอนาคต แต่ภาพยังไม่ยอมเปิดให้เห็น " \
                                        f"(อีก {left // 30} เดือน)", d
            from . import foresight as FS
            vision = FS.glimpse(self, a)
            # ราคาของการมองสิ่งที่ฟ้าไม่ให้เห็น — ไม่มีราคาแล้วความตายก็ไม่เหลือน้ำหนักในเรื่อง
            if a.fate > 0:
                a.fate -= 1
                d["ราคาที่จ่าย"] = f"ชะตาหายไปหนึ่งแต้ม (เหลือ {a.fate})"
            else:
                a.decay += C.FORESIGHT_COST_DECAY
                d["ราคาที่จ่าย"] = "ชะตาหมดแล้ว จึงจ่ายด้วยอายุขัยของตัวเอง"
            a.inner += C.FORESIGHT_INNER
            a.visions.append(vision)
            del a.visions[:-3]
            for cid, day in vision["deaths"].items():
                a.foreseen[str(cid)] = day
            d["นิมิต"] = " | ".join(vision["lines"])
            d["มองไปข้างหน้า"] = f"{vision['horizon'] // 30} เดือน"
            d["จิตมาร"] = f"หนักขึ้นเป็น {a.inner:.1f}"
            return "เห็นอนาคต", f"{a.name}จำลองอนาคตของตนออกมาดู — " \
                                 f"เห็น {len(vision['lines'])} ภาพที่ยังไม่เกิด", d

        if k == "ปิดด่าน":
            years = rng.randint(*C.SECLUDE_YEARS)
            a.seclude_until = self.day + years * 365
            a.hidden = True
            a.travel_dest = -1
            # ภาพของโลกตอนเข้าด่าน — ตอนออกมาจะได้รู้ว่าอะไรเปลี่ยนไปบ้าง ไม่ใช่โผล่มาเฉยๆ
            ties = ([a.master_cid] if a.master_cid >= 0 else []) + list(a.disciples[:4]) \
                + list(a.children[:4]) + ([a.spouse] if a.spouse is not None else []) \
                + [c for c, _v in sorted(a.rivals.items(), key=lambda kv: -kv[1])[:4]] \
                + [c for c, _v in sorted(a.bonds.items(), key=lambda kv: -kv[1])[:3]]
            snap = {}
            for cid in ties:
                if isinstance(cid, int) and 0 <= cid < len(self.cast):
                    o = self.cast[cid]
                    snap[str(cid)] = [o.name, int(o.alive), o.rank(), o.realm_name()]
            a.seclude_snap = {"day": self.day, "era": w.era, "state": w.state(),
                              "orgs": sum(1 for o in self.orgs if o.alive),
                              "n_alive": w.n_alive, "ties": snap}
            # ถ้ำกาลเวลา — ปราณยิ่งหนาแน่น เวลาที่ผู้บำเพ็ญ "ได้ใช้" ยิ่งมากกว่าเวลาโลกภายนอก
            # (ดู physics.time_dilation) นี่คือสิ่งที่ทำให้ "สถานที่" มีค่าต่างกันจริงๆ และให้
            # เหตุผลว่าทำไมคนถึงแย่งชิงถ้ำบำเพ็ญกัน — ก่อนหน้านี้ปิดด่านที่ไหนก็ได้เท่ากันหมด
            rho = self.qi_density(a.place, w)
            gamma = PHYS.time_dilation(rho, C.QI_CRITICAL, C.QI_DILATION_CAP)
            a.seclude_snap["gamma"] = gamma
            d["ปราณ ณ ที่แห่งนี้"] = f"{rho:.0f}/{C.QI_CRITICAL:.0f} ของขีดที่มิติรับไหว"
            d["เวลาที่ได้ใช้จริง"] = (f"{gamma:.2f} เท่าของเวลาข้างนอก"
                                      + (" — ที่นี่แทบไม่ต่างจากข้างนอก" if gamma < 1.15 else
                                         " — ถ้ำดี" if gamma < 2.0 else
                                         " — มิติที่นี่เกือบทนไม่ไหวแล้ว"))
            d["กำหนดออกจากด่าน"] = f"อีก {years} ปี ({E.date_words(a.seclude_until)})"
            d["ฝากไว้กับโลก"] = (f"ยุค{w.state()} · สำนัก {a.seclude_snap['orgs']} แห่ง · "
                                 f"คนในแดน {w.n_alive}")
            return "เข้าด่าน", f"{a.name}ปิดด่านบำเพ็ญ ตัดขาดจากโลกภายนอก {years} ปี", d

        if k == "ซ่อนตัว":
            if a.realm >= C.CACHE_MIN_REALM:
                faked = rng.random() < C.CACHE_TRAP_P
                self.make_cache(a, faked=faked)
                a.hidden = True
                a.hide_day = self.day
                a.money = {}
                d["แดนลับ"] = "แกล้งตายวางกับดัก" if faked else "ผนึกสมบัติทิ้งไว้"
                # กติกาที่ตัวละครควรรู้ตัวตั้งแต่ก้าวเข้าไป — แดนลับคือที่พัก ไม่ใช่ทางลัด
                d["ราคาของการหายไป"] = "ในแดนลับตัดขาดจากฟ้าดิน สะสมได้แต่เลื่อนขั้นไม่ได้"
                return "ซ่อนตัว", f"{a.name}หายไปจากโลก สร้างแดนลับผนึกสมบัติไว้", d
            R.cultivate(a, gap, self.items)
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
                R.cultivate(a, gap, self.items)
                return "ยังไม่ถึง", f"{a.name}เพ่งมองฟ้า รู้ว่ายังไม่ถึงเวลา", d
            up = self.world(w.up)
            if up.is_closed and up.tier == 1:
                if C.ASCEND_PEAK_EXCEPTION and a.realm >= C.REALM_CAP:
                    # ผู้ไต่ถึงยอดของโลกตัวเองแล้ว ฟ้าปิดกั้นไว้ไม่ได้ — โควตาประชากรของแดนบนมีไว้
                    # กันคนทั่วไป ไม่ใช่กันคนที่สุดทางของชั้นฟ้าหนึ่งแล้วจริงๆ (ถ้ากันได้หมด ยอด
                    # บันไดของโลกก็เป็นทางตันเงียบๆ — วัดจริง 307 ปี: ข้ามฟ้าจากโลกมนุษย์ 0 ครั้ง)
                    d["ฟ้าเปิดทางให้"] = "ผู้สุดทางของโลกนี้ ประตูปิดกั้นไว้ไม่ได้"
                else:
                    # ให้ได้ "ไปเห็นกำแพงด้วยตาตัวเอง" — เดิม IN.weigh() ลบตัวเลือกนี้ทิ้งตอนประตูปิด
                    # ตัวละครจึงไม่เคยรู้ว่ามีกำแพง และไม่มีเหตุให้คิดถึง "สงครามเบิกฟ้า" เลย
                    d["กำแพง"] = f"ค่ายกลปิดฟ้าของ{up.name} เหลือ {up.defense_array:.0f}/{up.defense_max:.0f}"
                    d["ทางที่เหลือ"] = "ทุบค่ายกลนั้นลง หรือรอจนวันที่ฟ้าเปิดประตูเอง"
                    return "ประตูปิด", f"{a.name}พยายามทะลวงฟ้า แต่ประตูสวรรค์ถูกปิดกั้น!", d
            # โอกาสรอดขึ้นกับการเตรียมตัว ไม่ใช่ทอยเหรียญค่าคงที่ — เดิมตายจริง 34/66 ครั้ง (55%)
            # เท่ากันหมดทั้งคนที่สะสมเกินเกณฑ์สองเท่าและคนที่เพิ่งแตะเกณฑ์พอดี
            req = R.need(a, w)
            acc = R.accumulation(a)
            prep = max(0.0, acc / max(1.0, req) - 1.0)          # สะสมเกินเกณฑ์กี่เท่า
            pills = sum(v for kk, v in (a.inventory or {}).items() if "ยา" in str(kk))
            p_live = min(C.ASCEND_P_MAX, C.ASCEND_P
                         + C.ASCEND_P_PREP_W * min(2.0, prep)
                         + C.ASCEND_P_FATE_W * a.fate
                         + C.ASCEND_P_PILL_W * min(5, pills))
            d["ความพร้อม"] = (f"สะสม {acc:.1f}/{req:.1f} · ชะตา {a.fate} · โอสถ {pills} "
                               f"→ โอกาสรอด {p_live * 100:.0f}%")
            if rng.random() > p_live:
                self.kill(a, "ดับสูญในด่านข้ามฟ้า")
                return "ตาย", f"{a.name}พ่ายในด่านข้ามฟ้า ดับสูญ", d
            up = self.world(w.up)
            old_name = a.realm_name()
            a.drawn = 0.0                       # พลังถูกขนออกจากโลกนี้ถาวร
            self.move_world(a, up.wid)          # ย้ายพร้อมปรับตัวนับประชากรทั้งสองแดน
            a.tier = up.tier
            a.realm = C.ASCEND_RESET_REALM
            a.ascends += 1
            a.peak_tier = max(a.peak_tier, up.tier)
            a.org = None
            # ขั้นภายในชั้นฟ้ากลับไปเป็น 0 แต่ **พลังไม่ลดลงแม้แต่หน่วยเดียว** (ขั้น 9 ของโลกล่าง
            # = ขั้น 0 ของโลกบนพอดีตาม TIER_STEP) และ rank() ก็ไต่ต่อจาก 9 เป็น 10 ไม่ได้ย้อนกลับ
            # สิ่งที่เปลี่ยนคือเขาเพิ่งเห็นว่าบันไดยาวกว่าที่เคยเห็น และตัวเองยืนที่ขั้นล่างสุดของมัน
            locals_ = [c for c in self.living_in(up.wid) if c.cid != a.cid and c.sentient]
            d["ข้ามฟ้า"] = f"{w.name} → {up.name}"
            d["ขั้นของข้า"] = f"{old_name} → {a.realm_name()} (ขั้นที่ {a.rank()} จาก {C.REALM_TOP + 1})"
            if locals_:
                top = max(locals_, key=lambda c: c.rank())
                d["สิ่งที่เพิ่งรู้"] = (f"ขั้นที่ไต่มาสุดชีวิตคือขั้นต่ำสุดของที่นี่ — "
                                        f"ที่นี่มีถึง{top.realm_name()} (ขั้นที่ {top.rank()})")
            return "ข้ามฟ้า", f"{a.name}ข้ามฟ้าขึ้นสู่{up.name} — " \
                              f"ผู้เก่งสุดของโลกเดิมกลายเป็นผู้อ่อนสุดของโลกใหม่", d

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
            self.move_world(a, dest.wid)        # ย้ายพร้อมปรับตัวนับประชากรทั้งสองแดน
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

        if k == "เข้าสำนัก":
            # ก่อนหน้านี้สำนักโตได้ทางเดียวคือ "ตั้งใหม่" ไม่มีใครเข้าสังกัดสำนักที่มีอยู่เลย
            # ผลคือมีคนสังกัดสำนักแค่ 2% ของประชากร สงครามสำนัก/ไส้ศึกจึงแทบไม่มีความหมาย
            if a.org is not None:
                return "มีสังกัดแล้ว", f"{a.name}มีสังกัดอยู่แล้ว", d
            here = []
            for org in self.orgs:
                if not org.alive or org.world_id != w.wid:
                    continue
                if org.mara != a.hated():          # ฝ่ายธรรมะกับลัทธิมารไม่รับกันและกัน
                    continue
                n_here = sum(1 for m in org.members
                             if m < len(self.cast) and self.cast[m].alive
                             and self.cast[m].place == a.place)
                if n_here:
                    here.append((org, n_here))
            if not here:
                return "ไม่มีสำนักแถวนี้", f"{a.name}ยังไม่เจอสำนักที่รับคนแถว{self.place_name(a)}", d
            here.sort(key=lambda x: -x[1])
            org = here[0][0]
            founder = self.cast[org.founder] if org.founder < len(self.cast) else None
            if founder is not None and a.realm > founder.realm:
                return "ไม่ยอมก้มหัว", f"{a.name}ฝีมือเหนือกว่าผู้ก่อตั้ง{org.name} จึงไม่ยอมเข้าสังกัด", d
            if rng.random() > C.ORG_JOIN_P:
                return "ยังไม่ตัดสินใจ", f"{a.name}ลังเลที่จะเข้าสังกัด{org.name}", d
            a.org = org.oid if org.oid < len(self.orgs) else self.orgs.index(org)
            a.org = self.orgs.index(org)
            org.members.append(a.cid)
            rank = "ศิษย์สายใน" if a.realm >= C.ORG_INNER_REALM else "ศิษย์สายนอก"
            (org.inner_disciples if rank == "ศิษย์สายใน" else org.outer_disciples).append(a.cid)
            d["สำนัก"] = org.name
            d["ตำแหน่ง"] = rank
            d["ที่"] = self.place_name(a)
            # เข้าสำนักศัตรูของสำนักที่ตัวเองเคยแค้น = โอกาสเป็นไส้ศึกในอนาคต
            return "เข้าสังกัด", f"{a.name}เข้าเป็น{rank}ของ{org.name}ที่{self.place_name(a)}", d

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
                # จุดหมายที่ "มีของที่ตัวเองกำลังขาด" มาก่อนข่าวลือทั่วไป — ถ้าไม่ผูกตรงนี้
                # แรงผลักจาก intent.py จะทำได้แค่ให้ออกเดินทาง แต่เดินสะเปะสะปะไม่ถึงแหล่ง
                want_pl = []
                for m in getattr(a, "wants", ()):
                    want_pl += [i for i in MAT.sources_in_world(m, w.place_key) if i != a.place]
                want_pl = [p for p in want_pl if p in pl]
                seek_pl = [p for p in pl if p in seek]
                safe_pl = [p for p in pl if p not in avoid] or pl
                mind_dest = (self.mind.take_destination(a, pl)
                             if getattr(self, "mind", None) is not None else None)
                if mind_dest is not None:
                    dest = mind_dest      # จุดหมายที่ตัวละครเลือกเอง (tiandao/mind)
                    tail_want = False
                elif want_pl and rng.random() < C.WANT_SEEK_P:
                    dest = self.pick_destination(a, want_pl, rng)
                    tail_want = True
                elif seek_pl and rng.random() < 0.6:
                    dest = self.pick_destination(a, seek_pl, rng)
                    tail_want = False
                else:
                    dest = self.pick_destination(a, safe_pl, rng)
                    tail_want = False
                allow_barrier = getattr(self, "mara_seal_broken", False) or (getattr(self, "mara_seal", 100.0) <= getattr(C, "MARA_SEAL_WEAK_THRESHOLD", 30.0) and rng.random() < getattr(C, "MARA_SEAL_LEAK_P", 0.15))
                days = TR.shortest_path_days(a.place, dest, a.realm,
                                             allow_mara_barrier=allow_barrier,
                                             character=a)
                if days is None:
                    # ไม่ควรเกิดจริง (pl มาจาก world_key เดียวกันซึ่งเชื่อมกันหมดในตัว geo.py เสมอ)
                    # กันไว้เผื่อข้อมูลกราฟผิดพลาดในอนาคต — ไม่เดินทาง แทนที่จะพัง
                    return "ผ่านไป", f"{a.name}ยังหาทางไปไม่เจอ", d
                dest_name = PL.PLACES[dest][0]
                if C.FOOD_ENABLED and not FOOD.provision(self, a, days):
                    # ซื้อเสบียงได้ไม่พอกินจนถึงจุดหมาย — ไม่ออกไปอดตายกลางทาง (tiandao/food.py)
                    d["เสบียง"] = f"ไม่พอกินตลอดทาง {days} วัน"
                    return "ผ่านไป", f"{a.name}อยากไป{dest_name} แต่เสบียงไม่พอเดินทาง {days} วัน", d
                a.travel_dest = dest
                a.travel_arrival_day = self.day + days
                tail = ""
                if tail_want:
                    lack = ", ".join(list(a.wants)[:2])
                    tail = f" (ออกไปตามหา{lack})"
                elif dest in frag_place.values() and dest in seek:
                    tail = " (ตามข่าวลือไปตามหาเศษวิชาโบราณ)"
                elif dest in seek:
                    tail = " (ตามข่าวลือว่าที่นี่กลับมาอุดมสมบูรณ์)"
                d["เดินทาง"] = f"{old} → {dest_name} (คาดว่าใช้เวลา {days} วัน)"
                return "ออกเดินทาง", f"{a.name}ออกเดินทางจาก{old}มุ่งหน้าสู่{dest_name}{tail}", d
            return "ผ่านไป", f"{a.name}ออกเดินทาง", d

        if k == "ค้าขาย":
            pv = self.place_of(a)
            at_market_place = bool(pv and pv[3] in ("ตลาด", "เมือง"))
            if at_market_place and not self.route_to_building(a, ("market",)):
                return "เดินไปตลาด", f"{a.name}มุ่งหน้าไปยังตลาดกลาง{self.place_name(a)}", d
            mult = 3.0 if at_market_place else 1.0
            gain = rng.uniform(0.5, 3.0) * mult
            # ขายวัตถุดิบที่สะสมไว้ตามราคาประเมิน
            sold = []
            # ช่างเก็บของที่สูตรของตัวเองต้องใช้ไว้ ไม่เทขายทิ้งแล้วมาบ่นว่าขาดวัตถุดิบทีหลัง
            useful = ()
            if a.alch_rank >= 0 or a.forge_rank >= 0:
                useful = MAT.useful_to(a.alch_rank, a.forge_rank, min(a.tier, 2))
            for name, n in list(a.mat_stock.items()):
                price = self.price_now(w, name, MAT.market_price(name))
                keep = a.wants.get(name, 0)     # ของที่ตัวเองยังต้องใช้ ไม่ขาย
                if name in useful:
                    keep = max(keep, C.CRAFT_KEEP_STOCK)
                n_sell = n - keep
                if price and n_sell > 0:
                    gain += price * n_sell / C.MAT_COIN_DIV
                    sold.append(f"{name} x{n_sell}")
                    if keep:
                        a.mat_stock[name] = keep
                    else:
                        a.mat_stock.pop(name, None)
            # ความลึกของตลาด — ตลาดหมู่บ้านไม่มีเงินพอจะรับของระดับสมบัติ
            # ก่อนหน้านี้ไม่มีเพดานเลย คนหนึ่งขายแร่กองหนึ่งแล้วได้เงิน 1.4 ล้านในห้ารอบ
            # (วัดจริง: คนรวยที่สุดของโลกลงมือแค่ 27 ครั้งตลอดชีวิต ค้าขาย 5 ครั้ง)
            # ของที่ขายไม่หมดยังอยู่ในถุง ต้องเอาไปตลาดใหญ่กว่าหรือรอรอบหน้า —
            # ซึ่งเป็นเหตุผลที่งานประมูลมีอยู่ในโลกนี้ตั้งแต่แรก
            depth = C.MARKET_DEPTH_BASE * (1 + w.tier) * (C.MARKET_DEPTH_CITY if at_market_place else 1.0)
            if gain > depth:
                d["ตลาดรับไม่ไหว"] = (f"ขายได้แค่ {depth:,.0f} จากมูลค่า {gain:,.0f} "
                                       f"— ที่นี่ไม่มีเงินพอ ต้องไปตลาดใหญ่กว่าหรือเข้าประมูล")
                gain = depth
            a.money[w.tier] = a.money.get(w.tier, 0.0) + gain

            # ซื้อของที่ "ตัวเองต้องการจริง" ไม่ใช่ของสุ่มที่ไม่มีสูตรไหนใช้
            # ตลาดมีของตามระดับโลกที่ตลาดนั้นตั้งอยู่ ของสูงกว่านั้นต้องขึ้นไปซื้อเอง
            bought = []
            if at_market_place and a.wants:
                budget = a.money.get(w.tier, 0.0)
                for name, need in list(a.wants.items()):
                    if MAT.MAT_TIER.get(name, 0) > w.tier:
                        continue
                    price = (self.price_now(w, name, MAT.price_of(name))
                             / C.MAT_COIN_DIV * C.MARKET_MARKUP)
                    qty = 0
                    while qty < need and budget >= price and rng.random() < C.MARKET_STOCK_P:
                        budget -= price
                        qty += 1
                    if qty:
                        a.mat_stock[name] = a.mat_stock.get(name, 0) + qty
                        left = need - qty
                        if left > 0:
                            a.wants[name] = left
                        else:
                            a.wants.pop(name, None)
                        bought.append(f"{name} x{qty}")
                a.money[w.tier] = budget
            if bought:
                d["ซื้อ"] = ", ".join(bought[:3])
            if a.wants:
                d["ยังตามหา"] = ", ".join(list(a.wants)[:3])
            if sold:
                d["ขายของ"] = ", ".join(sold[:3])
            d["ที่"] = self.place_name(a)
            d["กำไรรอบนี้"] = f"{gain:,.0f}"
            # ของที่ราคาผิดปกติในแดนนี้ตอนนี้ — เป็นข้อมูลที่ทำให้การค้าเป็นการตัดสินใจจริง
            hot = []
            for name in list(a.wants or ())[:3]:
                b = MAT.price_of(name)
                if not b:
                    continue
                mult = self.price_now(w, name, b) / max(1e-9, b)
                if mult >= C.PRICE_NEWSWORTHY or mult <= 1.0 / C.PRICE_NEWSWORTHY:
                    hot.append(f"{name} {'แพงขึ้น' if mult > 1 else 'ถูกลง'} {mult:.1f} เท่า")
            if hot:
                d["ราคาผิดปกติ"] = " · ".join(hot)
            return "ค้าขาย", f"{a.name}ค้าขายที่{self.place_name(a)} ได้กำไร {gain:,.0f}", d

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
            if C.FOOD_ENABLED:
                child.food = 0.0       # ทารกไม่ได้พกเสบียงมา กินจากยุ้งฉางของที่ที่เกิด
            if C.WAGES_ENABLED:
                child.gold_endowed = True   # ทารกไม่ได้ทุนตั้งต้น พ่อแม่จ่ายค่าข้าวให้
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
                v += rng.uniform(-CL.MUTATE, CL.MUTATE)
                blood[kk] = max(0.0, v)
            # สายเลือดวิญญาณเจือจางทุกรุ่น ส่วนที่หายไปกลายเป็นเลือดอสูร
            lost = blood.get("spirit", 0.0) * CL.SPIRIT_DILUTE
            blood["spirit"] = blood.get("spirit", 0.0) - lost
            blood["demon"] = blood.get("demon", 0.0) + lost
            child.blood = R.normalize(blood)
            # หลังผสมสายเลือดจริงแล้วจึงสุ่มดวงรับพรและตรึงปริมาณพรตามความเข้มข้นแรกเกิด
            child.bloodline_affinity = {
                line: round(rng.uniform(C.BLOODLINE_AFFINITY_MIN, C.BLOODLINE_AFFINITY_MAX), 4)
                for line, share in child.blood.items() if share > 0.0
            }
            child.bloodline_grants = {}
            self.apply_bloodline_buff(child)
            child.parents = [a.cid, t.cid]
            # ธาตุสืบสาย — ต้องตั้งตรงนี้ ไม่ใช่ใน spawn() เพราะตอน spawn ยังไม่รู้ว่าใครเป็นพ่อแม่
            # (วัดจริงตอนตั้งไว้ใน spawn: ลูกได้ธาตุตรงกับพ่อแม่ 22% = เท่ากับสุ่มล้วนพอดี)
            EL.roll(child, rng, (a, t))
            d["ธาตุของทายาท"] = f"{child.element} ({EL.relation_words(a.element, t.element)})"
            child.generation = max(a.generation, t.generation) + 1
            child.clan = a.clan if a.clan >= 0 else t.clan
            child.place = a.place
            child.origin = "ทายาทตระกูล" if child.clan >= 0 else "ชาวบ้าน"
            if child.clan >= 0:
                child.name = self.unique_name(
                    CL.CLANS[child.clan][0].replace("ตระกูล", "") + rng.choice(E.GIVEN), old=child.name)
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
            d["คำสาบาน"] = R.oath_form(a)
            return "ผูกพัน", f"{a.name}ให้สัญญากับ{t.name} โดย{R.oath_form(a)}", d

        if k == "ถ่ายทอดวิชา":
            # บั๊กคลาสเดียวกับ "ทรยศ" และ "สงครามสำนัก": กลไกที่ถูกเลือกบ่อยมากแต่ไม่เคย
            # ส่งมอบสิ่งที่ชื่อของมันบอกเลย วัดจริงโลก 50 ปี: ถ่ายทอดวิชา **2,882 ครั้ง**
            # แต่ผู้รับได้แค่ความเข้าใจ +0.5 กับความผูกพัน — **ไม่เคยได้วิชาสักอันเดียว**
            # ผลคือผู้บำเพ็ญ 309 จาก 828 คนไม่มีวิชาเลยทั้งที่อายุมัธยฐาน 48 ปี เพราะทางเดียว
            # ที่จะได้วิชาคือฝึกเอาเองเท่านั้น สายสำนักกับสายตระกูลจึงไม่มีความหมายในทางกลไก
            t.insight += 0.5
            if a.ascends > 0 and t.ascends == 0:
                t.bonds[a.cid] = t.bonds.get(a.cid, 0) + 0 # อคติ
                d["อคติ"] = f"{t.name} รับวิชาแต่ไม่ซาบซึ้งใจผู้ทะยานข้ามฟ้า"
            else:
                t.bonds[a.cid] = t.bonds.get(a.cid, 0) + 2
            if not isinstance(getattr(a, "mastery", None), dict):
                a.mastery = {}
            if not isinstance(getattr(t, "mastery", None), dict):
                t.mastery = {}
            # สอนได้เฉพาะวิชาที่ **ตัวเองเข้าใจพอ** และผู้รับยังไม่มี — เลือกอันที่ชำนาญที่สุด
            teachable = [n for n in a.skills if n not in t.skills
                         and a.mastery.get(n, 0) >= C.TEACH_MIN_REPS]
            if not teachable:
                # แยก outcome ออกให้วัดได้ — ไม่งั้น "สอนแล้วไม่มีอะไรจะสอน" กับ "สอนสำเร็จ"
                # จะถูกนับรวมกันจนมองไม่เห็นว่ากลไกทำงานจริงหรือเปล่า (บทเรียนจากรอบที่แล้ว)
                d["ที่ผู้รับได้"] = "ได้แต่หลักคิด ไม่ได้ตัววิชา"
                return "ไม่มีวิชาจะสอน", f"{a.name}ถ่ายทอดวิถีให้{t.name} แต่ไม่มีวิชาที่ส่งต่อได้", d
            name = max(teachable, key=lambda n: (a.mastery.get(n, 0), n))
            sk = next((x for x in SK.SKILLS if x[0] == name), None)
            # รับได้ไหม ขึ้นกับสามอย่าง: ขั้นของผู้รับถึงเกรดวิชาไหม · ธาตุถูกกันไหม ·
            # อาจารย์เข้าใจลึกแค่ไหน (สอนสิ่งที่ตัวเองรู้ครึ่งๆ กลางๆ ก็ได้ผลครึ่งๆ กลางๆ)
            bar = SK.GRADE_REALM_BAR[sk[3]] if sk else 0
            aff = EL.affinity(EL.ensure(t), EL.skill_element(name))
            deep = PHYS.practice_mastery(a.mastery.get(name, 1), C.PRACTICE_EXPONENT)
            p_ok = (C.TEACH_BASE_P + C.TEACH_REALM_W * (t.realm - bar)
                    + C.ELEMENT_LEARN_W * aff + C.TEACH_DEPTH_W * deep)
            d["p"] = max(0.05, min(0.95, p_ok))
            d["วิชาที่สอน"] = f"{name} (ธาตุ{EL.skill_element(name)} · อาจารย์ชำนาญ {deep:.0%})"
            if rng.random() > d["p"]:
                t.insight += C.TRAIN_FAIL_INSIGHT
                d["ที่ผู้รับได้"] = "ยังรับไม่ไหว ได้แต่เค้าโครง"
                return "รับไม่ไหว", f"{a.name}ถ่ายทอด{name}ให้{t.name} แต่{t.name}ยังรับไม่ไหว", d
            # ได้รูปมา แต่ยังไม่ได้ความลึกของอาจารย์ — ต้องไปฝึกเอง (ดู physics.practice_mastery)
            t.learn_skill(name)
            t.insight += C.TRAIN_INSIGHT_BASE * C.TEACH_INSIGHT_SHARE
            a.merit = getattr(a, "merit", 0.0) + 1.0
            d["ที่ผู้รับได้"] = f"ได้วิชา「{name}」ไปทั้งอัน แต่ยังตื้น ต้องไปฝึกเอง"
            return "ถ่ายทอด", f"{a.name}ถ่ายทอด{name}ให้{t.name}จนรับไปได้ทั้งวิชา", d

        if k in ("ทรยศ", "หักหลัง"):
            # บั๊กที่อยู่มานาน: ตารางเหตุการณ์ใช้ชื่อ "ทรยศ" แต่ handler นี้เคยเช็ค "หักหลัง"
            # จึง **ไม่เคยทำงานเลยสักครั้ง** (วัดจริง 102 ปี: "หักหลัง" 0 ครั้ง) การทรยศทั้ง
            # 2,489 ครั้งเลยไหลไปจบที่กิ่งประลองท้ายฟังก์ชัน คือกลายเป็น "ดวลกันตาย" 317 ศพ
            # และข้อความอ่านไม่ได้ความ: "ทาริกทรยศกับจาฟาร์ — ทาริกดับดิ้น" (คนทรยศตายเอง)
            tie = R.trust_tie(self, a, t)
            if tie is None:
                # ทรยศคนแปลกหน้าไม่ได้ ต้องมีความไว้ใจอยู่ก่อนจึงจะมีอะไรให้หักหลัง
                return "ไม่มีใครให้ทรยศ", f"{a.name}ไม่มีใครแถวนี้ที่ไว้ใจเขาพอจะถูกหักหลัง", d
            d["ความไว้ใจที่ถูกใช้"] = tie
            dmg = 3
            if a.ascends > 0 and t.ascends == 0:
                dmg *= 2
                d["อคติ"] = f"{t.name} แค้นพวกหน้าใหม่เป็นทวีคูณ"
            t.rivals[a.cid] = t.rivals.get(a.cid, 0) + dmg
            t.bonds.pop(a.cid, None)
            a.bonds.pop(t.cid, None)
            # การหักหลังคือการฉกฉวยจากความไว้ใจ ไม่ใช่การดวล — ของและความลับเปลี่ยนมือ ไม่ใช่ชีวิต
            # (ถ้าเขาอยากเอาชีวิตจริง นั่นคือ "ลอบสังหาร" ซึ่งมีกลไกและเงื่อนไขของตัวเองอยู่แล้ว)
            gain = []
            spoil = [i for i in t.items if self.items[i].kind != "ยาวิเศษ"]
            if spoil:
                iid = spoil[0]
                t.items.remove(iid)
                a.items.append(iid)
                self.items[iid].owner = a.cid
                gain.append(self.items[iid].name)
            cash = int(t.money.get(w.tier, 0) * 0.4)
            if cash > 0:
                t.money[w.tier] = t.money.get(w.tier, 0) - cash
                a.money[w.tier] = a.money.get(w.tier, 0) + cash
                gain.append(f"{cash} เหรียญ")
            if t.skills and (not a.skills or len(a.skills) < len(t.skills)):
                sk = t.skills[-1]
                if a.learn_skill(sk):
                    gain.append(f"วิชา{sk}")
            if a.org is not None and a.org == t.org and a.org < len(self.orgs):
                org = self.orgs[a.org]
                org.grudges[a.org] = org.grudges.get(a.org, 0)   # รอยร้าวในสำนักเดียวกัน
                d["รอยร้าว"] = f"เรื่องนี้เกิดขึ้นในสำนัก{org.name}เอง"
            if t.master_cid == a.cid and t.cid in a.disciples:
                a.disciples.remove(t.cid)
                t.master_cid = -1
                d["ความสัมพันธ์ที่ขาด"] = "ศิษย์-อาจารย์"
            before_inner = a.inner
            R.add_debt(a, "ทรยศ", t.cid, t.name, self.day)
            d["ที่ได้ไป"] = ", ".join(gain) if gain else "ไม่ได้อะไรติดมือ นอกจากความแค้น"
            if a.inner > before_inner:
                d["จิตมาร"] = f"{a.name} +หนี้ค้างคา (รวม {a.inner:.1f})"
            else:
                # คนที่ไร้จิตมาร (inner_none) หักหลังแล้วไม่ค้างคาใจเลย — เดิมบันทึกโม้ว่า
                # "+หนี้ค้างคา (รวม 0.0)" ทั้งที่ไม่มีอะไรเพิ่ม อ่านย้อนแล้วเข้าใจผิดได้
                d["จิตมาร"] = f"{a.name}ไร้จิตมาร เรื่องนี้ไม่ค้างคาใจเขาเลย"
            return "หักหลัง", f"{a.name}หักหลัง{t.name}ผู้ที่{tie}" \
                              + (f" ชิง{gain[0]}ไป" if gain else ""), d

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
                
            # รวมพลังหมาหมู่ — เฉพาะคนที่ **อยู่ในโลกและออกมาสู้ได้จริง**
            # ไม่นับคนที่ถูกขังอยู่ในคุกหรือปิดด่านอยู่ในแดนลับของตัวเอง สองพวกนี้ไม่ได้อยู่
            # ในแนวรบ และก่อนหน้านี้พวกเขาถูกนับเป็นกำลังพลและ **ตายในสงครามทั้งที่อยู่ในคุก**
            # (เจอตอนเทสต์การพ้นโทษพัง: นักโทษตายคาคุกด้วยสาเหตุ "สงครามสำนัก")
            def _in_the_field(c):
                return (c.alive and c.world_id == w.wid and not getattr(c, "hidden", False)
                        and getattr(c, "jail_until", 0) <= self.day)
            a_members = [self.cast[c] for c in org_a.members if _in_the_field(self.cast[c])]
            b_members = [self.cast[c] for c in org_b.members if _in_the_field(self.cast[c])]
            
            if not a_members or not b_members:
                return "ไร้กำลัง", "มีสำนักที่ไม่มีกำลังคนในโลกนี้เลย", d
                
            power_a = sum(R.power(m, w, self.items) for m in a_members)
            power_b = sum(R.power(m, w, self.items) for m in b_members)
            
            # กฎกำลังสองของแลนเชสเตอร์ (ดู tiandao/physics.py) — ของเดิมตัดสินด้วย
            # `power_a >= power_b` แล้วให้ฝ่ายแพ้ตาย 30% ต่อคน ส่วนฝ่ายชนะ **ไม่เสียใครเลย**
            # แปลว่าสงคราม 100 ต่อ 99 จบเหมือน 100 ต่อ 1 เป๊ะ ทั้งที่อย่างแรกควรเป็นชัยชนะ
            # ที่เลือดอาบจนแทบไม่เหลือสำนัก กฎกำลังสองให้ความต่างนั้นมาเอง และเลข 30%
            # ที่ตั้งเอาเองก็ไม่ต้องมีอีกต่อไป — อัตราตายของทั้งสองฝ่ายมาจากสมการเดียวกัน
            side, left_frac = PHYS.lanchester(power_a, power_b)
            win_org, lose_org = (org_a, org_b) if side >= 0 else (org_b, org_a)
            win_mems, lose_mems = (a_members, b_members) if side >= 0 else (b_members, a_members)
            win_loss_rate = 1.0 - left_frac          # ชนะฉิวเฉียด = เสียคนเกือบหมด
            d["ชัยชนะแบบไหน"] = (f"เหลือกำลัง {left_frac:.0%} จากที่ยกมา — "
                                 + ("ชนะแบบเลือดอาบ" if left_frac < 0.4 else
                                    "ชนะแบบบอบช้ำ" if left_frac < 0.75 else "ชนะแบบแทบไม่เสียใคร"))

            # คนแพ้โดนปล้นและอาจตาย
            loot_money = 0
            casualties = 0
            own_dead = 0
            for m in lose_mems:
                m_money = m.money.get(w.tier, 0)
                loot = int(m_money * 0.5)
                m.money[w.tier] = m_money - loot
                loot_money += loot

                # ฝ่ายแพ้ถูกตีแตก — อัตราตายมาจาก C.WAR_ROUT_RATE ไม่ใช่เลขที่ตั้งเอาเอง
                if rng.random() < C.WAR_ROUT_RATE:
                    if m.fate > 0:
                        m.fate -= 1
                    else:
                        self.kill(m, "สงครามสำนัก", killer=win_mems[0])
                        m.place = None
                        m.org = None
                        casualties += 1
            # ฝ่ายชนะก็เสียคนตามสัดส่วนที่สมการบอก — นี่คือสิ่งที่ของเดิมไม่มีเลย
            for m in list(win_mems):
                if rng.random() < win_loss_rate:
                    if m.fate > 0:
                        m.fate -= 1
                    else:
                        self.kill(m, "สงครามสำนัก", killer=lose_mems[0])
                        m.place = None
                        own_dead += 1
            d["ผู้เสียชีวิตฝ่ายชนะ"] = own_dead
                        
            # ผู้รอดชีวิตจากสำนักที่แพ้กลายเป็นผู้พเนจร, สำนักล่มสลาย
            lose_org.alive = False
            for c in self.living():
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
        # การประลองที่ "ไม่มีเรื่องบาดหมางกันมาก่อน" คือการวัดฝีมือ ไม่ใช่การฆ่ากัน — ยุทธภพ
        # แพ้แล้วยอม แล้วเก็บไปฝึกต่อ วัดจริงก่อนแก้: ประลอง 2,419 ครั้ง ตาย 303 ศพ (12.5%)
        # และผู้แพ้ได้ความแค้นติดตัวไปทุกครั้ง ซึ่งย้อนกลับมาเป็นล้างแค้น 4,144 ครั้ง — วงจร
        # ที่ทำให้คนแปลกหน้าสองคนซ้อมมือกันแล้วจบด้วยศพและการล้างแค้นข้ามรุ่น
        grudge = a.rivals.get(t.cid, 0) + t.rivals.get(a.cid, 0)
        friendly = (k == "ประลอง" and grudge == 0)
        win, lose, margin = R.resolve_clash(a, t, w, self.items, rng)
        mult = (C.DUEL_FRIENDLY_LETHAL_MULT if friendly
                else C.DUEL_LETHAL_MULT if k == "ประลอง" else 1.0)
        res = R.apply_defeat(self, w, win, lose, margin, rng, C.DEATH_MARGIN * mult)
        if k == "ล้างแค้น" and win is a:
            R.settle_debt(a, t.cid)
        dmg = 2 if k == "ล้างแค้น" else 1
        if win.ascends > 0 and lose.ascends == 0 and k in ("ชิงสมบัติ", "ล้างแค้น", "ประลอง"):
            dmg *= 2
            d["อคติ"] = f"{lose.name} เกลียดพวกหน้าใหม่ที่กำเริบเสิบสาน"
        if friendly and res in ("พ่ายแพ้", "รอดตายด้วยชะตา") and margin < C.DUEL_SHAME_MARGIN:
            # แพ้อย่างสมศักดิ์ศรี: ได้ความเข้าใจจากการปะมือกับคนที่เหนือกว่า และเกิดความนับถือกัน
            lose.insight += C.DUEL_LESSON_INSIGHT
            win.merit = getattr(win, "merit", 0.0) + 1.0
            lose.bonds[win.cid] = lose.bonds.get(win.cid, 0) + 1
            win.bonds[lose.cid] = win.bonds.get(lose.cid, 0) + 1
            d["สิ่งที่ผู้แพ้ได้"] = "ความเข้าใจจากการปะมือ และความนับถือต่อผู้ชนะ"
            return res, f"{a.name}ประลองกับ{t.name} — {lose.name}ยอมแพ้อย่างสมศักดิ์ศรี", d
        lose.rivals[win.cid] = lose.rivals.get(win.cid, 0) + dmg
        d["ผล"] = f"{win.name}({win.realm_name()}) เหนือกว่า {lose.name}({lose.realm_name()})"
        d["margin"] = round(margin, 3)
        d["winner"] = win.cid
        verb = {"ตาย": f"{lose.name}ดับดิ้น", "รอดตายด้วยชะตา": f"{lose.name}รอดด้วยชะตา",
                "พ่ายแพ้": f"{lose.name}เป็นฝ่ายพ่าย"}.get(res, f"{lose.name}{res}")
        return res, f"{a.name}{k}กับ{t.name} — {verb}", d

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
        vals = [self.eco_ratio(idx) for idx in sites] if sites else []
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

    def emit(self, world, kind, a, t, tags, outcome, text, gap, d):
        self.seq += 1   # เดิม increment ที่ step() ครั้งเดียวต่อทิก แต่ step()เดียวเรียก emit() ได้
                         # มากกว่า 1 ครั้ง (เช่น เหตุการณ์ผลพวง) ทำให้ seq ซ้ำกันได้ — ย้ายมาที่นี่
                         # ให้ seq เป็น ID ไม่ซ้ำจริงต่อหนึ่ง Event เสมอ (พบจาก narrative_factory
                         # Phase E ที่ scene_id ชนกันเพราะ seq ซ้ำ)
        e = Event(seq=self.seq, day=self.day, gap_days=gap, world_id=world.wid,
                  era=world.era, kind=kind, actor=a.cid if a else -1,
                  target=t.cid if t else None, tags=list(tags),
                  outcome=outcome, text=text, deltas=d, place=a.place if a else -1,
                  realm=a.realm if a else 0,
                  building=a.building if a else -1,
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
        event = self._step()
        if getattr(self, "_world_counts_dirty", False):
            self.recount_worlds()
            self._world_counts_dirty = False
        return event

    def run(self, n):
        self.last_run_steps = 0
        for _ in range(n):
            if self.step() is None:
                break
            self.last_run_steps += 1
        return self
