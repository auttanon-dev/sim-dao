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
    lifespan_bonus: int = 0       # อายุที่เพิ่มเมื่อกินโอสถ เม็ดเดียวใช้แล้วหมด


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
    # เดิมเป็น 10000 คงที่ = เครื่องปั๊มเงินที่เสกทรัพย์ให้ทุกสำนักทุกเดือนจากอากาศ
    # ตอนนี้เป็นผลผลิตจริงที่คำนวณจากศิษย์คูณอาณาเขต (ดู economy.sect_output)
    monthly_resource: float = 0.0
    treasury_qi: float = 0.0     # คลังปราณของสำนัก หน่วยเดียวกับหินวิญญาณ
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
    fall_streak: int = 0          # ล่มติดต่อกันกี่ครั้งแล้ว (ครบ DEMOTE_AFTER จึงร่วงชั้น)
    flourish_day: Optional[int] = None  # วันที่เริ่มรุ่งเรืองต่อเนื่อง (ครบ RECOVER_YEARS จึงเลื่อนชั้น)
    breakthroughs: int = 0        # จำนวนการเลื่อนขั้นที่เคยดึงพลังจากแดนนี้
    # ความบาดหมางที่แดนนี้มีต่อแดนบน — สะสมทุกครั้งที่ฟ้าลงมาเกณฑ์คนของตนไปโดยไม่อธิบาย
    # (ดู Sim.conscript) เป็นแรงผลักของ "สงครามเบิกฟ้า" และจางลงเองตามเวลา
    resentment: float = 0.0
    # วันที่เกิดการนองเลือดครั้งหลังๆ ในแดนนี้ — ใช้กับกระบวนการฮอว์กส์ (ดู physics.hawkes_intensity)
    # ความรุนแรงจุดชนวนตัวเอง ฆ่าหนึ่งครั้งแล้วแถบนั้นเดือดต่ออีกหลายปีแล้วค่อยสงบ
    # วัดจริงก่อนมี: ล้างแค้น+ลอบสังหาร 2,436 ครั้ง สัมประสิทธิ์การกระจาย 1.10 = สุ่มล้วน
    blood_marks: list = field(default_factory=list)

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
    natural_lifespan: int = 100   # สุ่ม 0-100 ตอนเกิดและไม่เปลี่ยนตามการเซฟ/โหลด
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
    # สายวัฏจักร — ดวงจิตที่เวียนว่ายข้ามภพ (ดู sim.reincarnate)
    cycle_born: bool = False       # เกิดมาพร้อมวาสนาสายวัฏจักรจากชาติก่อน
    rebirth_count: int = 0
    past_life: int = -1
    past_name: str = ""
    past_dao: str = ""
    past_realm: int = 0
    past_skills: List[str] = field(default_factory=list)
    memory_woken: bool = False
    # หุ่นเชิด — นับเป็นจำนวนตน ไม่ใช่ตัวละครเต็ม (ดู sim.build_puppet / sim.raise_corpse)
    puppets: int = 0
    puppet_kind: str = ""        # 'หุ่นกล' หรือ 'เชิดศพ'
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
    longevity_bonus: int = 0    # อายุที่ได้เพิ่มจากโอสถที่กินแล้ว
    bloodline_blessings: Dict[str, float] = field(default_factory=dict)  # พรที่ผู้นี้ให้เมื่อถึงสูงสุด
    bloodline_affinity: Dict[str, float] = field(default_factory=dict)   # ดวงรับพรของแต่ละสายเลือด
    bloodline_grants: Dict[int, float] = field(default_factory=dict)     # cid ผู้ให้ -> ค่าพรคงที่
    bloodline_buff: float = 0.0 # พรที่กำลังได้รับจากผู้สูงสุดซึ่งยังมีชีวิต
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
    wants: Dict[str, int] = field(default_factory=dict)       # วัตถุดิบที่ "ตอนนี้ต้องการ" แต่ยังขาด
                                                              # (ตั้งตอนหลอมไม่สำเร็จเพราะของไม่พอ)
                                                              # เป็นตัวขับให้ออกเดินทาง/ค้าขาย ดู intent.py
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
    # เจ็ดอารมณ์ หกปรารถนา (ดู tiandao/emotions.py) — ค่าจริงถูกสุ่มให้ไม่ซ้ำกันตอน Sim.spawn
    # ที่นี่เป็น dict ว่างเพราะ dataclass default ต้องไม่ผูกกับ rng และต้องไม่แชร์อ็อบเจกต์กัน
    emotions: Dict[str, float] = field(default_factory=dict)   # อารมณ์ตอนนี้ ขึ้นลงเร็ว
    desires: Dict[str, float] = field(default_factory=dict)    # แรงขับระยะยาว ขยับช้ามาก
    emo_base: Dict[str, float] = field(default_factory=dict)   # "ฐานใจ" ที่อารมณ์สงบกลับเข้าหา
    des_base: Dict[str, float] = field(default_factory=dict)
    emo_day: int = 0            # วันที่คำนวณการสงบของอารมณ์ไว้ล่าสุด (คิดแบบ lazy)
    # ถูกคุมขังอยู่ถึงวันไหน (0 = ไม่ได้ติดคุก) — คู่กับ hidden=True เพื่อให้ทุกที่ในโลกที่เคย
    # กรอง hidden อยู่แล้ว (เหยื่อมารบุก งานประมูล ศึกพันธมิตร) ข้ามคนติดคุกไปเองโดยไม่ต้องแก้
    jail_until: int = 0
    # แดนที่เกิด — ใช้แยก "ผู้มาจากโลกล่าง" ออกจากคนที่เกิดบนแดนสูงอยู่แล้ว ซึ่งเป็นความต่าง
    # ที่ทั้งเรื่องเล่าและการวัดผลต้องรู้ (ไม่งั้น peak_tier ของคนที่เกิดบนสวรรค์ก็ > 0 เหมือนกัน)
    birth_wid: int = -1
    # ปิดด่านบำเพ็ญอยู่ถึงวันไหน (0 = ไม่ได้ปิดด่าน) คู่กับ hidden=True เหมือนการคุมขัง
    # seclude_snap = ภาพของโลกตอนเข้าด่าน ใช้เทียบว่า "อะไรเปลี่ยนไป" ตอนออกมา
    # ระบบจำลองอนาคต (tiandao/foresight.py) — มีแค่ตัวเอกคนเดียวในโลก
    system_foresight: bool = False
    visions: List[dict] = field(default_factory=list)   # นิมิตที่เคยเห็น (ล่าสุดอยู่ท้าย)
    foreseen: dict = field(default_factory=dict)        # cid -> วันที่เห็นว่าเขาจะตาย
    fate_changed: int = 0                               # เปลี่ยนชะตาที่เห็นได้สำเร็จกี่ครั้ง
    fate_kept: int = 0                                  # กี่ครั้งที่มันเกิดตามนิมิตอยู่ดี
    seclude_until: int = 0
    # วันที่หายเข้าไปในแดนลับของตัวเอง (จาก "ซ่อนตัว") — ใช้บอกตอนออกมาว่าหายไปกี่ปี
    # และใช้เทียบว่าขั้นพลังไม่ขยับเลยระหว่างนั้น (ดู R.in_secret_realm)
    hide_day: int = 0
    # ธาตุประจำตัวจากห้าธาตุ (ดู tiandao/elements.py) — สืบจากพ่อแม่เป็นหลัก
    # ใช้ตัดสินว่าวิชาไหน "ถูกกับตัวเขา" และการปะทะธาตุไหนได้เปรียบเสียเปรียบ
    element: str = ""
    # ความชำนาญของแต่ละวิชา: ชื่อวิชา -> จำนวนครั้งที่ฝึก (ดู physics.practice_mastery)
    # วิชาเคยเป็น binary มีหรือไม่มี ฝึกของเดิมจึงไม่ได้อะไรเลย
    mastery: dict = field(default_factory=dict)
    # คะแนนอันดับยุทธภพแบบ Elo — ชื่อเสียงที่ทำนายผลการปะทะได้จริง ต่างจาก merit ที่เป็นตัวนับ
    elo: float = 1500.0
    # ---- เศรษฐกิจปราณ (ดู economy.py) ----
    # หินวิญญาณ: {เกรด: จำนวน} เป็นทศนิยมได้ เพราะหินที่ถูกดูดไปครึ่งก้อนเป็นของปกติ
    # แยกจาก money ซึ่งเป็นเหรียญทองของปุถุชนคนละสกุลกัน
    stones: dict = field(default_factory=dict)
    # ความมั่นคงในการยึดขั้นปัจจุบัน 0..1 — เลี้ยงตัวไม่ไหวแล้วค่อยๆ คลายลง ถึงพื้นแล้วขั้นหล่น
    grip: float = 1.0
    # ปราณที่หาได้จริงต่อปีครั้งล่าสุด — เก็บไว้ให้บันทึกกับใจของตัวละครอ่านออกว่า "พอไหม"
    qi_in: float = 0.0
    # ปราณที่เคยดูดจากฟ้าดินสะสมทั้งชีวิต — ใช้ตรวจบัญชีปิดของโลก
    qi_taken: float = 0.0
    # อัตราที่ "ตัวเขาเอง" สะสมได้และเสื่อมลงต่อวัน — วัดจากชีวิตจริงของเขาแบบค่าเฉลี่ย
    # ถ่วงน้ำหนักล่าสุด (ดู rules.age_and_decay) ไม่ใช่ค่าคงที่ของโลก เพราะนักรบกับ
    # นักปรุงยาสะสมคนละความเร็ว และคนคนเดียวกันตอนหนุ่มกับตอนแก่ก็ไม่เท่ากัน
    # ใช้หาจังหวะที่ควรทะลวงขั้นด้วยอนุพันธ์ (ดู rules.break_timing)
    acc_mark: float = 0.0
    acc_mark_day: int = 0
    acc_rate: float = 0.0
    decay_mark: float = 0.0
    decay_rate: float = 0.0
    seclude_snap: dict = field(default_factory=dict)
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
        # ขั้นย่อยทุกขั้นเพิ่ม 100 ปี ขั้นใหญ่ทุกแดนเพิ่มอีก 300 ปี โดยนับขั้นที่ผ่านในแดนก่อน
        # ต่อเนื่องด้วย แม้ข้ามฟ้าแล้ว realm จะเริ่มใหม่ที่ศูนย์
        if self.tier >= len(C.TIER_NAMES) - 1 and self.realm >= C.REALM_CAP:
            return C.SUPREME_LIFESPAN
        # ขั้นย่อยที่ "ผ่านมาแล้วจริง" ไม่ใช่ rank() — rank() คือตำแหน่งบนบันไดทั้งจักรวาล
        # (tier * REALM_BAND + realm) ซึ่งนับการข้ามฟ้าเป็นขั้นย่อยเพิ่มอีกหนึ่งขั้นเสมอ
        # ทั้งที่การข้ามฟ้าคือ "ขั้นใหญ่" ที่ได้ LIFESPAN_PER_MAJOR_REALM อยู่แล้ว
        # ผลคือคนขั้นเซียนแรกเริ่ม (tier=1, realm=0) เคยได้ 10 ขั้นย่อย + 1 ขั้นใหญ่ = เกินไป 100 ปี
        # ในหนึ่งชั้นฟ้ามีขั้นย่อยให้ไต่ REALM_CAP ครั้ง (0->9) การขึ้นชั้นฟ้าใหม่จึงเท่ากับ
        # ผ่านขั้นย่อยครบ REALM_CAP ของชั้นเดิม แล้วเริ่มนับ realm ของชั้นใหม่ต่อจากนั้น
        # rank() ยังคงเดิมทุกตัวอักษร เพราะเกณฑ์พลัง/การข้ามขั้นทั้งระบบผูกกับมันอยู่
        completed_minor = self.tier * C.REALM_CAP + self.realm
        base = (self.natural_lifespan
                + completed_minor * C.LIFESPAN_PER_MINOR_REALM
                + self.tier * C.LIFESPAN_PER_MAJOR_REALM)
        return int(base + self.longevity_bonus)

    def rank(self) -> int:
        """ขั้นที่ไต่มาได้จริง นับเป็นเส้นเดียวทั้งจักรวาล 0-29 (ดู config.REALM_TOP)

        `realm` เป็นตัวเลขภายในชั้นฟ้าหนึ่งๆ (0-9) การข้ามฟ้าจึงทำให้มันกลับไปเป็น 0 ทั้งที่
        ตัวละคร **ไม่ได้อ่อนลงเลย** (พลังเท่าเดิมเป๊ะ: ขั้น 9 ของโลกล่าง = ขั้น 0 ของโลกบน)
        ทุกที่ที่ถามว่า "เขาไต่มาได้ไกลแค่ไหน" ต้องถาม rank() ไม่ใช่ realm — ไม่งั้นเกณฑ์สะสม
        ของการข้ามขั้นจะรีเซ็ตตามไปด้วย แล้วโลกบนจะไต่ **ง่ายกว่า** โลกล่าง (เกณฑ์ตกจาก 33
        เหลือ 6) ซึ่งกลับหัวกับทั้งแนวเรื่องและความรู้สึกที่ควรได้: ยิ่งสูงยิ่งยาก
        """
        return self.tier * C.REALM_BAND + self.realm

    def learn_skill(self, name: str, reps: int = 1) -> bool:
        """รับวิชาเข้ามือ — คืน True ถ้าเป็นวิชาใหม่สำหรับเขา

        กติกาของโลกข้อหนึ่งที่เคยรั่วอยู่หลายทาง: **มีวิชาอยู่ในมือ = ฝึกมาแล้วอย่างน้อยหนึ่งครั้ง**
        มือจับ "ฝึกวิชา" กับ "ถ่ายทอดวิชา" ตั้ง mastery=1 ให้อยู่แล้ว แต่ทางที่เหลือ (จุติคืน
        สังสารวัฏ · ตื่นความทรงจำชาติก่อน · ต่อเศษวิชาโบราณ · ชิงวิชาจากการหักหลัง ·
        ต้นไม้โลกหยั่งกิ่ง) ต่อชื่อวิชาเข้า list เฉยๆ คนที่ได้วิชามาทางนั้นจึงถือวิชาที่
        "ฝึกมาศูนย์ครั้ง" ซึ่งเป็นไปไม่ได้ตามกติกา และมีผลจริงสองอย่าง:
          · rules.skill_power คูณ practice_mastery(0) = 0 วิชานั้นจึงให้แค่ SKILL_BASE_SHARE
          · สอนต่อไม่ได้เลย เพราะ TEACH_MIN_REPS กรอง mastery ออกก่อน
        รวมไว้ที่นี่เพราะ invariant เป็นเรื่องของข้อมูลใน Character เอง ไม่ใช่ของมือจับใดมือจับหนึ่ง
        ทางใหม่ที่จะแจกวิชาในอนาคตจึงได้ความถูกต้องมาฟรีโดยไม่ต้องจำ

        `reps` คือจำนวนครั้งขั้นต่ำที่ถือว่าฝึกมาแล้ว — **ยกขึ้นเท่านั้น ไม่เคยลด** คนที่ฝึกวิชา
        เดิมมา 40 ครั้งแล้วได้วิชาเดียวกันซ้ำจากอีกทางหนึ่ง ต้องไม่ถูกรีเซ็ตกลับเป็น 1
        ไม่แตะ RNG เลย โลกจึงเดินซ้ำได้เหมือนเดิม
        """
        mast = self.__dict__.get("mastery")
        if not isinstance(mast, dict):
            mast = {}
            self.mastery = mast
        fresh = name not in self.skills
        if fresh:
            self.skills.append(name)
        if mast.get(name, 0) < reps:
            mast[name] = reps
        return fresh

    def at_bottleneck(self) -> bool:
        """สะสมพอจะข้ามขั้นแล้ว — ต้องลงมือ ไม่ใช่นั่งบำเพ็ญต่อ"""
        need = C.NEED_BASE + C.NEED_PER_REALM * self.rank()
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
        self.__dict__.setdefault("natural_lifespan", 100)
        self.__dict__.setdefault("longevity_bonus", 0)
        self.__dict__.setdefault("bloodline_blessings", {})
        self.__dict__.setdefault("bloodline_affinity", {})
        self.__dict__.setdefault("bloodline_grants", {})
        self.__dict__.setdefault("bloodline_buff", 0.0)
        # ใจ (เจ็ดอารมณ์ หกปรารถนา) เพิ่มมาทีหลัง — save เก่าไม่มี เติมเป็นว่างไว้ก่อน
        # แล้ว emotions.ensure() จะอนุมานจากนิสัยที่เขามีอยู่ให้ตอนถูกใช้ครั้งแรก
        self.__dict__.setdefault("emotions", {})
        self.__dict__.setdefault("desires", {})
        self.__dict__.setdefault("emo_base", {})
        self.__dict__.setdefault("des_base", {})
        self.__dict__.setdefault("emo_day", self.__dict__.get("last_day", 0))
        self.__dict__.setdefault("jail_until", 0)
        self.__dict__.setdefault("birth_wid", self.__dict__.get("world_id", -1))
        self.__dict__.setdefault("system_foresight", False)
        self.__dict__.setdefault("visions", [])
        self.__dict__.setdefault("foreseen", {})
        self.__dict__.setdefault("fate_changed", 0)
        self.__dict__.setdefault("fate_kept", 0)
        self.__dict__.setdefault("seclude_until", 0)
        self.__dict__.setdefault("hide_day", 0)
        self.__dict__.setdefault("element", "")
        self.__dict__.setdefault("mastery", {})
        self.__dict__.setdefault("elo", 1500.0)
        self.__dict__.setdefault("stones", {})
        self.__dict__.setdefault("grip", 1.0)
        self.__dict__.setdefault("qi_in", 0.0)
        self.__dict__.setdefault("qi_taken", 0.0)
        self.__dict__.setdefault("acc_mark", 0.0)
        self.__dict__.setdefault("acc_mark_day", 0)
        self.__dict__.setdefault("acc_rate", 0.0)
        self.__dict__.setdefault("decay_mark", 0.0)
        self.__dict__.setdefault("decay_rate", 0.0)
        self.__dict__.setdefault("seclude_snap", {})


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
    surprise: float = 0.0     # ความประหลาดใจเป็นบิต = -log2(p) (ดู physics.surprisal)
                              # เอนจินรู้ความน่าจะเป็นของทุกอย่างอยู่แล้ว การเก็บไว้ตรงนี้ทำให้
                              # "ข้ามขั้นสำเร็จตามคาด" แยกจาก "ข้ามขั้นสำเร็จทั้งที่โอกาส 4%"
                              # ได้ด้วยตัวเลข — หน้าอ่านเลือกไคลแมกซ์ของบทเองได้จากค่านี้
    place: int = -1   # ที่ตั้งตอนเกิดเหตุ (ดัชนีใน places.PLACES) — -1 = ไม่ทราบ, เติมโดย Sim.emit()
    realm: int = -1   # ขั้นของ actor ตอนเกิดเหตุจริง (realm ย้อนถอยได้จาก decay แบบไม่ถูก log เป็น
                       # event เลย — เก็บตรงนี้เป็นหลักฐานเดียวที่แม่นสำหรับ validator ตรวจ "Realm ต้องตรง")
    building: int = -1        # อาคารที่เกิดเหตุภายในเมือง — "ในโรงตีเหล็ก" กับ "ที่ลานหน้าเมือง"
                              # ให้ภาพคนละแบบ ฉากที่จะเขียนเป็นหนังต้องรู้
    present: tuple = ()       # cid ของคนอื่นที่อยู่ตรงนั้นด้วย (สูงสุด PRESENT_MAX คน) — ฉากหนัง
                              # ต้องมีคนยืนดู ไม่ใช่มีแค่คู่กรณีสองคนกลางความว่างเปล่า
    snap: tuple = ()          # ลายนิ้วมือสถานะของ actor ณ วินาทีนั้น — ใช้หา "จุดเปลี่ยนจริง" ด้วยการ
                              # diff กับเหตุการณ์ก่อนหน้า แทนการเดาจากสตริง outcome (ซึ่งพิสูจน์แล้วว่า
                              # ผิด: "ทำนา/สำเร็จ" ถูกนับเป็นจุดเปลี่ยนพอๆ กับ "หลอมยา/สำเร็จ")
                              # ลำดับฟิลด์ดู Sim.state_snap()

    def to_dict(self):
        return asdict(self)

    def __setstate__(self, state: dict) -> None:
        """log/save เก่าที่เซฟไว้ก่อนมี field "place"/"realm"/"building"/"present"/"snap" ยัง
        unpickle ได้ — เติมค่า default แทน (dataclass ไม่เรียก __init__ ตอน unpickle เอง)"""
        self.__dict__.update(state)
        self.__dict__.setdefault("place", -1)
        self.__dict__.setdefault("realm", -1)
        self.__dict__.setdefault("building", -1)
        self.__dict__.setdefault("present", ())
        self.__dict__.setdefault("snap", ())
        self.__dict__.setdefault("surprise", 0.0)
