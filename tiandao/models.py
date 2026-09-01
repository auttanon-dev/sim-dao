# -*- coding: utf-8 -*-
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional

from . import config as C


@dataclass
class Item:
    iid: int
    kind: str            # ยาวิเศษ / อาวุธวิเศษ / สมบัติฟ้าดิน
    tier: int
    grade: float         # คุณภาพ
    condition: float = 1.0   # ของก็เสื่อมได้ 0 = พัง
    maker: Optional[int] = None
    name: str = ""
    legend: bool = False          # สมบัติฟ้าดินชิ้นที่มีชื่อ มีชิ้นเดียวในทุกโลก
    power_desc: str = ""
    cooldown: int = 0             # วันที่ต้องรอให้พลังฟื้นเต็ม
    ready_day: int = 0
    pill_bonus: float = 0.0


@dataclass
class Cache:
    kid: int
    world_id: int
    owner: int               # ใครฝากไว้
    owner_name: str
    sealed_day: int
    seal: float              # ความแรงผนึก (ปี) เสื่อมลงเรื่อยๆ
    items: List[int] = field(default_factory=list)
    currency: float = 0.0
    trap: bool = False       # แกล้งตาย รออยู่ข้างใน
    opened: bool = False
    era_sealed: int = 1


@dataclass
class Org:
    oid: int
    kind: str
    name: str
    world_id: int
    founder: int
    founded_day: int
    members: List[int] = field(default_factory=list)
    grudges: Dict[int, int] = field(default_factory=dict)   # oid -> ระดับ
    monthly_resource: int = 10000
    core_disciples: List[int] = field(default_factory=list)
    inner_disciples: List[int] = field(default_factory=list)
    outer_disciples: List[int] = field(default_factory=list)
    facilities: Dict[str, int] = field(default_factory=dict)   # name -> master cid
    alert_level: int = 50
    threat_level: int = 0
    mara: bool = False        # สำนักของมนุษย์มาร รับเฉพาะพวกเดียวกัน
    alive: bool = True


@dataclass
class World:
    wid: int
    name: str
    tier: int
    kind: str = "mortal"      # mortal / mara
    heaven: float = C.HEAVEN_CAP
    era: int = 1
    up: Optional[int] = None      # โลกที่ข้ามฟ้าขึ้นไป
    lateral: List[int] = field(default_factory=list)   # โลกระดับเดียวกันที่เชื่อมถึง
    place_key: object = 0     # คีย์ที่ใช้หาสถานที่ในโลกนี้
    n_mortal: int = 0
    n_alive: int = 0
    checked_day: int = 0
    rift: float = 0.0         # ความกว้างของรอยแยกโกลาหลในโลกนี้
    defense_array: float = 100.0  # พลังค่ายกลป้องกันของโลก (ลดลงเมื่อมีผู้บุกรุก)
    defense_max: float = 100.0    # พลังค่ายกลป้องกันสูงสุด
    is_closed: bool = False       # ประตูปิดกั้นการทะลวงผ่านหรือไม่

    def cap(self) -> float:
        return C.HEAVEN_CAP * (C.HEAVEN_CAP_PER_TIER ** self.tier)

    def ratio(self) -> float:
        return self.heaven / self.cap()

    def state(self) -> str:
        r = self.ratio()
        if r >= C.FLOURISH_RATIO:
            return "ยุครุ่งเรือง"
        if r >= C.DECLINE_RATIO:
            return "ยุคปกติ"
        return "ยุคเสื่อม"


@dataclass
class Character:
    cid: int
    name: str
    world_id: int
    dao: str
    dao_tags: List[str]
    born_day: int
    blood: Dict[str, float] = field(default_factory=dict)
    realm: int = 0
    insight: float = 0.0        # การสะสมจากการบำเพ็ญ (สายมนุษย์)
    refine: float = 0.0         # การขัดเกลาสายเลือด (สายวิญญาณ)
    
    # --- Advanced Combat & Routine Fields ---
    energy: float = 100.0
    current_mp: float = 100.0
    max_mp: float = 100.0
    active_formation: str = ""
    formation_duration: int = 0
    current_state: str = "Sleeping"
    life_goal: str = "บำเพ็ญเพียรแสวงหามรรควิถี"
    
    # --- Sect & Hierarchy Fields ---
    is_loner: bool = False
    master_cid: int = -1
    disciples: List[int] = field(default_factory=list)
    sect_rank: str = ""
    karmic_debt: int = 0
    is_emperor: bool = False
    dragon_aura: bool = False
    is_demon: bool = False
    is_beast: bool = False
    has_human_form: bool = False
    is_spirit: bool = False
    hp: float = 100.0
    max_hp: float = 100.0
    loyalty: int = 50
    ambition: int = 50

    decay: float = 0.0
    fate: int = 1
    alive: bool = True
    hidden: bool = False        # ซ่อนตัวทำแดนลับ
    death_day: Optional[int] = None
    death_cause: str = ""
    drawn: float = 0.0          # พลังที่ถอนจากคลังฟ้าไปแล้ว
    inner: float = 0.0          # จิตมาร
    inner_none: bool = False
    inner_art: bool = False
    debts: List[dict] = field(default_factory=list)   # หนี้ค้างคา
    exp: Dict[str, int] = field(default_factory=dict)
    learn: Dict[str, float] = field(default_factory=dict)   # เจตนา -> ค่าประสบการณ์สะสม (EMA ของผลลัพธ์ที่เจอ)
    rumor_leads: List[dict] = field(default_factory=list)   # ข่าวลือที่ยังตามอยู่ (แดนลับ/สมบัติที่ได้ยินมา)
    fragments: Dict[str, List[int]] = field(default_factory=dict)  # ชื่อวิชาแก้ทางโกลาหล -> ชิ้นส่วนที่เก็บได้แล้ว
    forge: float = 0.0
    alchemy: float = 0.0
    cores: int = 0
    items: List[int] = field(default_factory=list)
    money: Dict[int, float] = field(default_factory=dict)   # tier -> จำนวน
    spirit_stones: float = 1000.0   # เงินตราหลักสำหรับประมูล
    org: Optional[int] = None
    spy_for: Optional[int] = None
    rivals: Dict[int, int] = field(default_factory=dict)
    bonds: Dict[int, int] = field(default_factory=dict)
    peak_realm: int = 0
    peak_tier: int = 0
    near_death: int = 0
    kills: int = 0
    breaks: int = 0
    fails: int = 0
    ascends: int = 0
    origin: str = "ชาวบ้าน"
    last_day: int = 0
    tier: int = 0
    sentient: bool = True       # อสูรระดับต่ำยังไม่มีจิตนึกคิด
    skills: List[str] = field(default_factory=list)
    chaos_rank: int = -1        # -1 = ไม่ใช่เผ่าโกลาหล
    is_lord: bool = False       # เจ้าโกลาหล มีคนเดียว
    lord_returns: int = 0       # เจ้าโกลาหลกลับมาแล้วกี่ครั้ง ยิ่งกลับยิ่งแข็ง
    return_day: int = 0         # วันที่จะกลับมา
    thrall: bool = False        # ตกเป็นพวกเผ่าโกลาหล — ได้รับการดูแล แต่เป็นทาส
    forge_rank: int = -1
    alch_rank: int = -1
    mats: int = 0               # วัตถุดิบที่เก็บสะสมไว้
    place: int = -1             # สถานที่ที่อยู่ตอนนี้ (ดัชนีใน places.PLACES) — ระหว่างเดินทางยังคงเป็น
                                 # จุดออกเดินทางเดิม จะเปลี่ยนเป็นปลายทางตอนถึงจริงเท่านั้น
    travel_dest: int = -1       # กำลังเดินทางไปไหน (ดัชนีใน places.PLACES) — -1 = ไม่ได้เดินทางอยู่
    travel_arrival_day: int = 0 # จะถึงจุดหมายวันไหน (มีความหมายเฉพาะตอน travel_dest >= 0)
    building: int = -1          # อาคารที่อยู่ตอนนี้ภายใน place ปัจจุบัน (ดัชนีใน settlement ของ place นั้น)
                                 # — -1 = ยังไม่ระบุ/อยู่ในเมืองทั่วไป, รีเซ็ตเป็น -1 ทุกครั้งที่ place เปลี่ยน
    building_dest: int = -1     # กำลังเดินไปอาคารไหนภายในเมือง — -1 = ไม่ได้เดินอยู่
    building_arrival_day: int = 0 # จะถึงอาคารวันไหน (มีความหมายเฉพาะตอน building_dest >= 0)
    mat_stock: Dict[str, int] = field(default_factory=dict)   # วัตถุดิบแยกชนิด
    clan: int = -1              # ตระกูลที่สังกัด (ดัชนีใน clans.CLANS)
    parents: List[int] = field(default_factory=list)
    children: List[int] = field(default_factory=list)
    generation: int = 0
    traits: List[str] = field(default_factory=list)
    archetype: str = "ผู้พเนจร"
    is_unique_beast: bool = False
    unique_title: str = ""
    gender: str = "ชาย"
    fear: float = 0.5
    greed: float = 0.5
    compassion: float = 0.5
    profession: str = "ผู้ฝึกตน"
    tribe: str = "ชาวตงหยวน"
    city_id: int = -1
    merit: float = 0.0
    karma: float = 0.0
    spouse: Optional[int] = None
    hp: int = 100
    max_hp: int = 100
    inventory: dict = field(default_factory=lambda: {"อาวุธ": None, "ยาสมานแผล": 0})
    companions: dict = field(default_factory=dict)
    nemeses: dict = field(default_factory=dict)
    cities_visited: int = 0
    enemies_defeated: int = 0
    generation: int = 1
    parent_name: str = None
    moral: int = 0
    title: str = "ชาวยุทธนิรนาม"
    sect_name: str = None
    sect_role: str = "ศิษย์พเนจร"


    def update_title(self):
        level = getattr(self, "realm", 1)
        if level >= 10:
            self.title = "มหาเทพกระบี่สยบฟ้า" if self.moral >= 50 else "พญามารโลหิตกลืนวิญญาณ" if self.moral <= -50 else "ปรมาจารย์ไร้พ่าย"
        elif level >= 5:
            self.title = "จอมยุทธคุณธรรม" if self.moral >= 20 else "ดาวโจรแดนเถื่อน" if self.moral <= -20 else "ผู้ท่องโลกีย์"
        else:
            self.title = "ศิษย์ฝ่ายธรรมะ" if self.moral >= 10 else "นักเลงเจ้าถิ่น" if self.moral <= -10 else "ชาวยุทธนิรนาม"

    def age(self, day: int) -> int:
        return (day - self.born_day) // 365

    def lifespan(self) -> int:
        base = C.LIFESPAN[min(self.realm, C.REALM_CAP)]
        return int(base * (1.0 + 0.5 * self.blood.get("demon", 0.0)))

    def at_bottleneck(self) -> bool:
        """สะสมพอจะข้ามขั้นแล้ว — ต้องลงมือ ไม่ใช่นั่งบำเพ็ญต่อ"""
        need = C.NEED_BASE + C.NEED_PER_REALM * self.realm
        return (self.insight + self.refine * 3.0) >= need * 0.9

    def is_chaos(self) -> bool:
        return self.chaos_rank >= 0

    def mara_rank(self) -> str:
        from .places import MARA_RANKS
        return MARA_RANKS[min(self.realm, len(MARA_RANKS) - 1)]

    def realm_name(self) -> str:
        if self.is_lord:
            return "เจ้าโกลาหล"
        if self.is_chaos():
            return C.CHAOS_RANKS[min(self.chaos_rank, len(C.CHAOS_RANKS) - 1)]
        if self.blood.get("mara", 0.0) >= 0.85:
            return self.mara_rank()
        if self.race() == "อสูร":
            name = C.BEAST_RANKS[min(self.realm, len(C.BEAST_RANKS) - 1)]
            return f"{self.unique_title}{name}" if self.is_unique_beast else name
        return C.realm_name(self.tier, self.realm)

    def hated(self) -> bool:
        """มนุษย์มาร — เป็นที่รังเกียจของมนุษย์ทุกคน"""
        return (self.blood.get("mara", 0.0) >= C.MARA_HATE_BLOOD
                and self.blood.get("human", 0.0) >= 0.25)

    def race(self) -> str:
        """ป้ายเผ่าที่อ่านง่าย คำนวณจากสัดส่วนสายเลือด"""
        if self.is_chaos():
            return "เผ่าโกลาหล"
        if self.thrall:
            return "ทาสโกลาหล"
        b = self.blood
        top = max(C.BLOODS, key=lambda k: b.get(k, 0.0))
        v = b.get(top, 0.0)
        if v >= 0.85:
            return {"human": "มนุษย์", "spirit": "สัตว์วิญญาณ", "demon": "อสูร",
                    "mara": "มารแท้", "chaos": "เลือดโกลาหล"}[top]
        if b.get("mara", 0) >= 0.3 and b.get("human", 0) >= 0.3:
            return "มนุษย์มาร"
        if top == "human":
            second = max((k for k in C.BLOODS if k != "human"), key=lambda k: b.get(k, 0))
            return "มนุษย์ผสม" + C.BLOOD_TH[second]
        return C.BLOOD_TH[top] + "ผสม"

    def to_dict(self):
        return asdict(self)

    def __setstate__(self, state: dict) -> None:
        """save เก่าที่เซฟไว้ก่อนมีระบบเดินทางจริง (tiandao/travel.py) ยัง unpickle ได้ — เติมค่า default
        แทน (ไม่ได้เดินทางอยู่) เหมือนที่ Event ทำไว้แล้วด้านล่างตอนเพิ่ม place/realm"""
        self.__dict__.update(state)
        self.__dict__.setdefault("travel_dest", -1)
        self.__dict__.setdefault("travel_arrival_day", 0)
        self.__dict__.setdefault("building", -1)
        self.__dict__.setdefault("building_dest", -1)
        self.__dict__.setdefault("building_arrival_day", 0)


@dataclass
class Event:
    seq: int
    day: int
    gap_days: int
    world_id: int
    era: int
    kind: str
    actor: int
    target: Optional[int]
    tags: List[str]
    outcome: str
    text: str
    deltas: Dict[str, str] = field(default_factory=dict)
    place: int = -1   # ที่ตั้งตอนเกิดเหตุ (ดัชนีใน places.PLACES) — -1 = ไม่ทราบ, เติมโดย Sim.emit()
    realm: int = -1   # ขั้นของ actor ตอนเกิดเหตุจริง (realm ย้อนถอยได้จาก decay แบบไม่ถูก log เป็น
                       # event เลย — เก็บตรงนี้เป็นหลักฐานเดียวที่แม่นสำหรับ validator ตรวจ "Realm ต้องตรง")

    def to_dict(self):
        return asdict(self)

    def __setstate__(self, state: dict) -> None:
        """log/save เก่าที่เซฟไว้ก่อนมี field "place"/"realm" ยัง unpickle ได้ — เติมค่า default แทน
        (dataclass ไม่เรียก __init__ ตอน unpickle เอง)"""
        self.__dict__.update(state)
        self.__dict__.setdefault("place", -1)
        self.__dict__.setdefault("realm", -1)
