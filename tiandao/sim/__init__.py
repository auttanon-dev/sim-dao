# -*- coding: utf-8 -*-
"""โลกจำลองหนึ่งใบ — Sim ประกอบจาก mixin ต่อหมวด (ไฟล์ละหมวดในแพ็กเกจนี้)

ทุก mixin ใช้ import ชุดเดียวกันจาก _common.py; pickle อ้าง tiandao.sim.Sim เหมือนเดิม เซฟเก่าโหลดได้
"""
from ._common import *  # noqa: F401,F403
from ._common import _REACH_CACHE, _PLACE_SETS, _CENTERS, _reach_from, _auction_q, city_office  # noqa: F401
from .helpers import HelpersMixin
from .population import PopulationMixin
from .death import DeathMixin
from .puppets import PuppetMixin
from .cycle import CycleMixin
from .processes import ProcessMixin
from .items import ItemsMixin
from .rumors import RumorMixin
from .ecology import EcologyMixin
from .clock import ClockMixin
from .step import StepMixin
from .turns import TurnMixin
from .outcomes import OutcomeMixin
from .resolve import ResolveMixin
from .records import RecordsMixin


class Sim(HelpersMixin, PopulationMixin, DeathMixin, PuppetMixin, CycleMixin, ProcessMixin, ItemsMixin, RumorMixin, EcologyMixin, ClockMixin, StepMixin, TurnMixin, OutcomeMixin, ResolveMixin, RecordsMixin):
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
        self.households, self.household_seq = {}, 0   # tiandao/household.py
        self.clan_treasury = {}   # clan -> {tier: ทอง} กระเป๋าของครัวเรือนที่สลายโดยไม่มีทายาท (household.on_death)
        self.mine_purse = {}      # tier -> ทองที่ขุดได้ซึ่งรอรับซื้อวัตถุดิบ (wages._mine)
        self.mine_recent = {}     # tier -> ทองที่ขุดได้ในราวหนึ่งปีล่าสุด (เพดานกองทุนเหมือง)
        self.market_demand = {}   # (wid, place) -> มูลค่าของที่คนมาขายที่นี่ในราวหนึ่งปีล่าสุด (ลดลงตามเวลา)
        self.market_reserve = {}  # (wid, place) -> ทุนสำรองของตลาด (ทองชั้นของแดน) รับซื้อของ — wages.tick กันไว้จากเงินที่ใช้จ่าย
        self.settlement_treasury = {}   # (wid, place) -> {tier: ทอง} มรดกที่ไม่มีผู้รับตกเป็นของชุมชน (settle_estate)
        self.gold_flows = {}      # สาเหตุ -> {tier: ทอง} ทุกทางที่ทองเกิดหรือหาย (wages.record) ยอดรวม = wages.total_gold
        self.cities = copy.deepcopy(C.CITIES)   # เมืองของโลกนี้ — เจ้าเมืองอยู่ในเซฟ (เดิมแก้ config.CITIES ของ module)
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
        self.death_news = []        # คิวข่าวความตาย (tiandao/news.py) — (วันถึง, ผู้ตาย, ผู้รับ, ผู้ฆ่า, ความแค้น)
        self.news_stats = {}
        # คีย์ (wid, place_idx) — หลายแดนใช้ผังสถานที่ชุดเดียวกัน คีย์ด้วยสถานที่อย่างเดียวทำให้ขุดแดนหนึ่งแล้วอีกแดนโทรมไปด้วย (§6.2 R1)
        self.place_stock = {}     # (wid, place_idx, ชนิด) -> ทรัพยากรที่เหลืออยู่ตอนนี้ (ระบบนิเวศ §6.2)
        self.material_stats = {}  # บัญชีคลังทรัพยากร: genesis regrown seeded harvested disaster
        self.eco_scarce = {}      # (wid, place_idx) -> True ขณะที่ยังอยู่ในสถานะขาดแคลน (ค้างจนกว่าจะฟื้นจริง)
        self.eco_recovered = set()  # (wid, place_idx) ที่เพิ่งฟื้นจากขาดแคลน — ใช้เป็นข่าวลือครั้งเดียวแล้วเคลียร์ทิ้ง
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
            from ..decision import attach as _attach_decision
            _attach_decision(self)

        # มหาผนึกสะกดหมื่นมาร (แดนลับรอยแยกเชื่อมโลกมนุษย์-แดนมาร)
        self.mara_seal = getattr(C, "MARA_SEAL_INITIAL", 100.0)
        self.mara_seal_broken = False
        self.mara_seal_notified_weak = False
        self.mara_seal_day = 0                   # วันที่มหาผนึกเดินปีล่าสุด (_mara_seal_tick)

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
            from .. import realm_map as RM
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
        self.genesis_cast = len(self.cast)      # คนที่สร้างพร้อมโลก — ได้ทุนตั้งต้น (wages.tick) คนที่มาทีหลังไม่ได้ (B3c)

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
            ch.peak_realm = ch.realm
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
                          era_sealed=0)
                k.gold = {w.tier: rng.uniform(0, 50)}          # ทองที่ผู้วางฟ้าดินทิ้งไว้ — แหล่งกำเนิดที่ประกาศ
                WAGES.record(self, "cache_genesis", w.tier, k.gold[w.tier])
                self.caches.append(k)
