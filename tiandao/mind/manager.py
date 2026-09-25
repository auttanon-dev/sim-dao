# -*- coding: utf-8 -*-
"""MindManager — ตัวละครที่มีจิตใจ คิดเอง ตั้งเป้าหมายเอง วางแผนเอง

ตำแหน่งในเอนจิน (tiandao/sim.py `_step`)
---------------------------------------------------------------------------------------------
เอนจินเดิมคำนวณน้ำหนักเจตนา `w` (อาชีพ นิสัย สถานการณ์ ร่างกาย) แล้วสุ่มเลือกหนึ่งอย่าง
สำหรับคนที่มีจิตใจ ขั้น "สุ่มเลือก" ถูกแทนด้วย `choose()`:

    เมนู = สิ่งที่ w บอกว่าเป็นไปได้  ->  จิตใจ (LLM) เลือก การกระทำ + คน + ที่หมาย + เหตุผล
    ->  เอนจินเดิมตัดสินผลตามกฎโลกเหมือนทุกคน  ->  `after_action()` บันทึกลงบันทึกชีวิต

โมเดลจึงควบคุม "เจตนา" ได้เต็มที่ แต่ไม่เคยควบคุม "ผล" — ผลเป็นของวิถีสวรรค์เสมอ

ทำไมมีแผนหลายขั้น: ถ้าคิดใหม่ทุกเทิร์น ตัวละครจะเปลี่ยนใจไปมาและกินเวลาโมเดลทุกครั้ง แผนสามขั้น
ทำให้การกระทำต่อเนื่องเป็นเรื่องเดียวกัน (ไปหาแร่ -> หลอมอาวุธ -> ท้าประลอง) และคิดใหม่เฉพาะเมื่อ
แผนหมด ทำต่อไม่ได้ หรือมีคนมาทำอะไรเรา (ถูกโจมตี/ถูกหักหลัง)

ไม่มีจิตใจ = ไม่มีผลอะไรเลย: ถ้าไม่ได้แนบ MindManager ไว้ที่ `sim.mind` ทุกจุดที่แก้ใน sim.py เป็น
ทางเดิมเป๊ะ ไม่กิน RNG เพิ่ม — test_determinism.py ยังผ่าน
"""
import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from . import actions as A
from . import backend as B
from . import config as MC
from . import persona as P
from . import prompt as PR
from . import situation as SIT
from .. import hopfield as HF
from .. import travel as TR
from .. import emotions as EM
from .. import events as E
from .. import config as C

logger = logging.getLogger(__name__)


@dataclass
class Mind:
    cid: int
    name: str
    joined_day: int
    origin_note: str = ""
    alive: bool = True
    enabled: bool = True              # พักจิตใจได้เมื่อผู้ใช้ลดจำนวน โดยไม่ลบประวัติของตัวละคร
    death_day: Optional[int] = None
    death_cause: str = ""
    long_goal: str = ""
    long_goal_day: int = -1
    goal_stale: bool = False
    short_goal: str = ""
    emotion: str = ""
    last_thought: str = ""
    plan: List[dict] = field(default_factory=list)
    plan_day: int = 0
    # วันที่คิดใหญ่ครั้งล่าสุด — ใช้คุมงบการเรียกโมเดลเมื่อจังหวะเวลาถูกย่อยเป็นรายวัน
    last_think_day: int = -10 ** 9
    memories: List[str] = field(default_factory=list)
    inbox: List[str] = field(default_factory=list)
    impressions: Dict[int, str] = field(default_factory=dict)
    interrupted: bool = False
    n_thinks: int = 0
    n_plan_steps: int = 0
    n_instinct: int = 0
    last_error: str = ""
    last_realm: int = -1
    last_org: Optional[int] = None
    plan_origin: str = ""          # id ของบันทึกการคิดที่วางแผนชุดปัจจุบัน
    plan_thought: str = ""
    scars: List[dict] = field(default_factory=list)   # บาดแผลในใจ: [{cid, name, year, outcome, times}]
    # ความจำเชิงเชื่อมโยงของคนคนนี้ (ดู hopfield.py) — เก็บ (สถานการณ์ -> สิ่งที่เคยเลือก)
    # ของตัวเองเท่านั้น ไม่ใช่ของคนอื่น จึงเกิด "ตัวนี้เป็นแบบนี้ ตัดสินใจแบบนี้" ขึ้นเอง
    recall_mem: object = None
    # สะเทือนใจจริง — ตั้งเฉพาะเหตุการณ์ที่มีแท็กรุนแรง (ต่อสู้ เลือด ทรยศ ความตาย ชิงทรัพย์)
    # แยกจาก `interrupted` ที่ตั้งทุกครั้งที่คนรู้จักขยับตัวแถวนี้ (MC.SOCIAL_REPLY)
    # วัดจริงก่อนแยก: 213 จาก 260 วันที่ต้องคิด (82%) ถูกนับเป็น "จุดพลิก" จนความจำ
    # ไม่ได้ทำงานเลย ทั้งที่ส่วนใหญ่เป็นแค่เพื่อนบ้านเดินผ่าน
    shaken: bool = False
    recall_streak: int = 0        # ตอบด้วยความจำติดกันมาแล้วกี่ครั้ง — กันชีวิตกลายเป็นลูป
    recent_acts: List[str] = field(default_factory=list)   # สิ่งที่ทำล่าสุด (กันทำซ้ำ)
    # เซฟเก่าที่มีจิตใจอยู่ก่อนระบบประวัติวัยเด็ก ต้องเติมสมุดชีวิตเพียงครั้งเดียวหลังอัปเกรด
    history_backfilled: bool = False

    def __setstate__(self, state):
        # เซฟก่อนมีบาดแผลในใจ — dataclass ไม่เติมค่าเริ่มต้นให้ตอนโหลด pickle
        self.__dict__.update(state)
        self.__dict__.setdefault("scars", [])
        self.__dict__.setdefault("last_think_day", -10 ** 9)
        self.__dict__.setdefault("recall_mem", None)
        self.__dict__.setdefault("shaken", False)
        self.__dict__.setdefault("recall_streak", 0)
        self.__dict__.setdefault("recent_acts", [])
        self.__dict__.setdefault("enabled", True)
        self.__dict__.setdefault("history_backfilled", False)

    def remember(self, text):
        self.memories.append(text)
        del self.memories[:-MC.MEMORY_CAP]


@dataclass
class Choice:
    kind: str
    target: object = None       # Character หรือ None


@dataclass
class Pending:
    source: str                 # คิดใหม่ / ตามแผน / สัญชาตญาณ / ชะตาฟ้า
    step: Optional[PR.Step] = None
    info: dict = field(default_factory=dict)
    plan_left: List[dict] = field(default_factory=list)
    error: str = ""
    side: List[str] = field(default_factory=list)   # เหตุการณ์ผลพวงที่เกิดระหว่างลงมือ


class MindManager:
    def __init__(self, capacity=MC.MIND_CAPACITY):
        self.capacity = capacity
        self.minds: Dict[int, Mind] = {}
        self.story_queue: List[dict] = []
        self.stats = {"thinks": 0, "plan_steps": 0, "instinct": 0, "fate": 0, "errors": 0,
                      "stories": 0, "recall": 0}
        self.successor_hints: List[tuple] = []    # (cid, หมายเหตุที่มา)
        self._pending: Dict[int, Pending] = {}
        self._backend = None
        self.journal_path = ""
        self.activity = ""
        self.recent: List[dict] = []
        self.home_place = -1
        self._collapsed = {}

    # ------------------------------------------------------------ pickle
    def __getstate__(self):
        state = dict(self.__dict__)
        state["_backend"] = None
        state["_pending"] = {}
        return state

    def __setstate__(self, state):
        self.__dict__.update(state)
        self.__dict__.setdefault("_backend", None)
        self.__dict__.setdefault("_pending", {})
        self.__dict__.setdefault("recent", [])
        self.__dict__.setdefault("activity", "")
        self.__dict__.setdefault("successor_hints", [])
        self.__dict__.setdefault("home_place", -1)
        self.__dict__.setdefault("_collapsed", {})

    # ------------------------------------------------------------ การต่อเข้ากับโลก
    def _grant_system(self, sim):
        """ยกวิถีหยั่งรู้อนาคตให้ตัวเอกที่ตื่นรู้มานานที่สุด ถ้ายังไม่มีใครในโลกมี

        ต้องมีเมธอดนี้เพราะการยกระบบตอน _adopt() ใช้ได้แต่กับจิตใจดวงใหม่ — โลกที่รันมาก่อนหน้า
        (วัดจริง: โลกอายุ 104 ปี) ตัวเอกรุ่นแรกจึงไม่มีระบบ และระบบไปตกกับคนที่เพิ่งตื่นรู้ปีที่ 89
        ซึ่งไม่ใช่ตัวเอกของเรื่องที่ผู้อ่านตามมาตั้งแต่ต้น
        """
        if not getattr(MC, "SYSTEM_FORESIGHT_OWNER", True):
            return None
        if any(getattr(c, "system_foresight", False) for c in sim.cast):
            return None
        pool = [sim.cast[m.cid] for m in self.active() if 0 <= m.cid < len(sim.cast)]
        pool = [c for c in pool if c.alive]
        if not pool:
            return None
        owner = min(pool, key=lambda c: (self.minds[c.cid].joined_day, c.cid))
        owner.system_foresight = True
        self._journal({"type": "join", "id": f"sys-{owner.cid}", "seq": sim.seq, "day": sim.day,
                       "year": sim.day // 365, "cid": owner.cid, "name": owner.name,
                       "text": f"{owner.name}พบว่าตนมีวิถีหยั่งรู้อนาคตอยู่ในจิต — "
                               f"มองเห็นสิ่งที่ยังไม่เกิดได้ปีละครั้ง โดยจ่ายด้วยชะตาของตัวเอง",
                       "identity": P.short_identity(sim, owner),
                       "place": P.place_label(sim, owner.place)})
        return owner

    def attach(self, sim, backend=None, journal_path=None):
        """แนบเข้ากับโลก (เรียกทุกครั้งหลังโหลดเซฟด้วย) — ไม่สมัคร event bus ซ้ำ"""
        sim.mind = self
        if backend is not None:
            self._backend = backend
        if journal_path is not None:
            self.journal_path = journal_path
        bus = sim.event_bus
        if not any(getattr(h, "__self__", None) is self for h in bus._subscribers):
            bus.subscribe(self.on_event)
        self.ensure_cast(sim)
        self._migrate_childhood_history(sim)
        self._repair_dead_target_state(sim)
        # โลกที่รันมาก่อนหน้าจะไม่มีใครถือระบบ (ยกตอน _adopt ได้แต่กับจิตใจดวงใหม่) จึงยกให้
        # ตัวเอกที่ตื่นรู้มานานที่สุดตอนต่อชั้นจิตใจเข้าโลก — คนที่ผู้อ่านตามมาตั้งแต่ต้น
        self._grant_system(sim)
        return self

    def _migrate_childhood_history(self, sim):
        """เติมประวัติให้จิตใจจากเซฟเก่า หลังรู้ตำแหน่ง journal แล้ว และทำครั้งเดียว."""
        if not self.journal_path:
            return
        for mind in self.minds.values():
            if mind.history_backfilled or not (0 <= mind.cid < len(sim.cast)):
                continue
            self._backfill_childhood(sim, sim.cast[mind.cid])
            mind.history_backfilled = True

    def _repair_dead_target_state(self, sim):
        """ซ่อมเซฟเก่าที่เป้าหมาย/แผนยังชี้คนตาย ก่อนมี `_finish_dead_target()`.

        เก็บ scar ไว้เป็นอดีต (prompt บอกได้ว่าผู้ก่อตายแล้ว) แต่ห้ามให้เป้าหมายปัจจุบันหรือแผน
        ยังสั่งไปหาคนนั้น เซฟรันจริงปี 32 พบกรณีนี้กับเซียวเหลียนโดยตรง
        """
        revenge_words = ("ล้างแค้น", "แก้แค้น", "เอาคืน", "สำนึกผิด", "ชดใช้")
        for mind in self.active():
            dead = {}
            for scar in mind.scars:
                cid = scar.get("cid")
                if isinstance(cid, int) and 0 <= cid < len(sim.cast) and not sim.cast[cid].alive:
                    dead[cid] = sim.cast[cid].name
            kept_plan = []
            for step in mind.plan:
                cid = step.get("target_cid")
                if isinstance(cid, int) and 0 <= cid < len(sim.cast) and not sim.cast[cid].alive:
                    dead[cid] = sim.cast[cid].name
                else:
                    kept_plan.append(step)
            names = [name for name in dead.values() if name]
            stale_short = any(name in (mind.short_goal or "") for name in names)
            stale_long = any(name in (mind.long_goal or "") for name in names)
            plan_changed = len(kept_plan) != len(mind.plan)
            if not (stale_short or stale_long or plan_changed):
                continue
            mind.plan = kept_plan
            mind.goal_stale = True
            mind.interrupted = True
            if stale_short:
                mind.short_goal = ""
            if stale_long and any(word in (mind.long_goal or "") for word in revenge_words):
                mind.long_goal = ""
            note = " / ".join(names)
            mind.inbox.append(f"{note}ตายแล้ว เป้าหมายหรือแผนเดิมเกี่ยวกับเขาทำต่อไม่ได้")
            del mind.inbox[:-MC.INBOX_CAP]

    @property
    def backend(self):
        if self._backend is None:
            self._backend = B.from_env()
        return self._backend

    # ------------------------------------------------------------ คัดตัวละคร
    def active(self):
        return [m for m in self.minds.values() if m.alive and m.enabled]

    def set_capacity(self, sim, capacity):
        """เปลี่ยนจำนวนผู้มีจิตใจทันที โดยพัก/ปลุก component เดิมแทนการลบประวัติ."""
        self.capacity = max(1, int(capacity))
        active = sorted(self.active(), key=lambda m: (m.joined_day, m.cid))
        for mind in active[self.capacity:]:
            mind.enabled = False
            mind.plan = []
            self._pending.pop(mind.cid, None)
        if len(self.active()) < self.capacity:
            sleeping = sorted((m for m in self.minds.values() if not m.enabled),
                              key=lambda m: (m.joined_day, m.cid))
            for mind in sleeping:
                if len(self.active()) >= self.capacity:
                    break
                if 0 <= mind.cid < len(sim.cast) and sim.cast[mind.cid].alive:
                    mind.alive = True
                    mind.enabled = True
                    mind.goal_stale = True
                    mind.interrupted = True
        self.ensure_cast(sim)
        return len(self.active())

    def _eligible(self, sim, ch, taken_names):
        if not ch.alive or ch.cid in self.minds or ch.hidden:
            return False
        if not getattr(ch, "sentient", True):
            return False
        if getattr(ch, "is_beast", False) and not getattr(ch, "has_human_form", False):
            return False
        if ch.age(sim.day) < MC.MIND_MIN_AGE:
            return False
        if ch.lifespan() - ch.age(sim.day) < 5:
            return False          # ใกล้สิ้นอายุขัย — ยังไม่ทันได้เริ่มเรื่องก็จบ
        if ch.name in taken_names:
            return False
        return True

    def _score(self, sim, ch):
        s = ch.realm * 3.0 + ch.tier * 12.0
        s += 4.0 if ch.org is not None else 0.0
        s += 2.0 if ch.clan >= 0 else 0.0
        s += min(6, len(ch.rivals)) + min(6, len(ch.bonds)) + min(4, len(ch.skills))
        s += 3.0 if ch.disciples or ch.master_cid >= 0 else 0.0
        s += 2.0 if ch.traits else 0.0
        return s

    def ensure_cast(self, sim):
        """เติมผู้มีจิตใจให้ครบจำนวน — ผู้สืบเรื่องต่อ (ฆาตกร ศิษย์ ลูก) มาก่อน แล้วค่อยคัดตามคะแนน

        คัดแบบไม่ใช้ RNG ของโลก (เรียงคะแนนแล้วตัดสินเสมอด้วย cid) โลกจึงไม่เดินต่างไปเพียงเพราะเลือกคน
        """
        added = []
        taken = {m.name for m in self.active()}
        # เพดานอสูร: เรื่องนี้เป็นเรื่องของจอมยุทธ อสูรที่มีร่างมนุษย์เป็นตัวละครได้ แต่ไม่ควรกลายเป็นคนหมู่มาก
        beast_cap = max(1, int(self.capacity * MC.BEAST_MIND_MAX_RATIO))
        beasts = sum(1 for m in self.active() if getattr(sim.cast[m.cid], "is_beast", False))
        # 1) ผู้สืบเรื่อง
        hints, self.successor_hints = self.successor_hints, []
        for cid, note in hints:
            if len(self.active()) >= self.capacity:
                break
            if 0 <= cid < len(sim.cast) and self._eligible(sim, sim.cast[cid], taken):
                is_beast = getattr(sim.cast[cid], "is_beast", False)
                if is_beast and beasts >= beast_cap:
                    continue
                beasts += 1 if is_beast else 0
                added.append(self._adopt(sim, sim.cast[cid], note))
                taken.add(sim.cast[cid].name)
        # 2) คัดตามคะแนน โดยรวมคนไว้ในโลกเดียวกันก่อน และกันที่ไว้ให้ชาวบ้านธรรมดาราวหนึ่งในห้า
        need = self.capacity - len(self.active())
        if need <= 0:
            return added
        living = sim.living()
        if self.home_place < 0:
            # บ้านร่วม: รวมผู้มีจิตใจไว้ในรัศมีเดินทางเดียวกัน ให้ได้พบและมีเรื่องกันจริง
            self.home_place = self._choose_home(sim, living, taken)
        home = self.home_place
        archetype_cap = max(3, int(self.capacity * 0.35))
        place_cap = 6
        arche = {}
        places = {}
        for m in self.active():
            c = sim.cast[m.cid]
            arche[c.archetype] = arche.get(c.archetype, 0) + 1
            places[c.place] = places.get(c.place, 0) + 1
        mortal_slots = max(1, self.capacity // 5) - sum(
            1 for m in self.active() if sim.cast[m.cid].realm == 0)
        for wid in _world_order(sim):
            if need <= 0:
                break
            pool = [c for c in living if c.world_id == wid and self._eligible(sim, c, taken)]
            pool.sort(key=lambda c: (0 if self._near_home(home, c) else 1, -self._score(sim, c), c.cid))
            mortals = [c for c in pool if c.realm == 0]
            ordered = mortals[:max(0, mortal_slots)] + [c for c in pool if c.realm > 0] + mortals[max(0, mortal_slots):]
            ordered = [c for c in ordered if self._near_home(home, c)] + \
                      [c for c in ordered if not self._near_home(home, c)]
            for c in ordered:
                if need <= 0:
                    break
                if c.name in taken or c.cid in self.minds:
                    continue
                if arche.get(c.archetype, 0) >= archetype_cap or places.get(c.place, 0) >= place_cap:
                    continue
                if getattr(c, "is_beast", False):
                    if beasts >= beast_cap:
                        continue
                    beasts += 1
                added.append(self._adopt(sim, c, ""))
                taken.add(c.name)
                arche[c.archetype] = arche.get(c.archetype, 0) + 1
                places[c.place] = places.get(c.place, 0) + 1
                if c.realm == 0:
                    mortal_slots -= 1
                need -= 1
        return added

    def _near_home(self, home, c):
        if home < 0 or c.world_id != 0 or c.place is None or c.place < 0:
            return False
        if c.place == home:
            return True
        d = TR.shortest_path_days(home, c.place, 0)
        return d is not None and d <= MC.HOME_RADIUS_DAYS

    def _choose_home(self, sim, living, taken):
        pool = [c for c in living if c.world_id == 0 and self._eligible(sim, c, taken)]
        places = sorted({c.place for c in pool if c.place is not None and c.place >= 0})
        best, best_n = -1, -1
        for p in places:
            n = sum(1 for c in pool if self._near_home(p, c))
            if n > best_n:
                best, best_n = p, n
        return best

    def _adopt(self, sim, ch, note):
        m = Mind(cid=ch.cid, name=ch.name, joined_day=sim.day, origin_note=note,
                 last_realm=ch.realm, last_org=ch.org)
        self.minds[ch.cid] = m
        if self.journal_path:
            self._backfill_childhood(sim, ch)
            m.history_backfilled = True
        # ระบบจำลองอนาคตมีได้คนเดียวในโลก และเป็นของ "ตัวเอกคนแรกที่ตื่นรู้" (ดู foresight.py)
        # วางไว้ที่นี่เพราะนี่คือจุดเดียวที่จิตใจดวงใหม่ถือกำเนิด ไม่ว่ามาจากทางไหนก็ผ่านตรงนี้
        if getattr(MC, "SYSTEM_FORESIGHT_OWNER", True) and not any(
                getattr(c, "system_foresight", False) for c in sim.cast):
            ch.system_foresight = True
            m.origin_note = ((note + " · ") if note else "") + "ผู้มีวิถีหยั่งรู้อนาคตในตัว"
            self._journal({"type": "join", "id": f"sys-{ch.cid}", "seq": sim.seq, "day": sim.day,
                           "year": sim.day // 365, "cid": ch.cid, "name": ch.name,
                           "text": f"{ch.name}พบว่าตนมีวิถีหยั่งรู้อนาคตอยู่ในจิต — "
                                   f"มองเห็นสิ่งที่ยังไม่เกิดได้ปีละครั้ง โดยจ่ายด้วยชะตาของตัวเอง",
                           "identity": P.short_identity(sim, ch),
                           "place": P.place_label(sim, ch.place)})
        self._journal({"type": "join", "id": f"join-{ch.cid}-{sim.day}", "seq": sim.seq, "day": sim.day,
                       "year": sim.day // 365, "cid": ch.cid, "name": ch.name,
                       "text": (f"{ch.name} ตื่นรู้มีจิตใจเป็นของตัวเอง" + (f" — {note}" if note else "")),
                       "identity": P.short_identity(sim, ch), "place": P.place_label(sim, ch.place)})
        return m

    def _backfill_childhood(self, sim, ch):
        """เติมกำเนิดและวัยเด็กก่อนวันที่ตื่นรู้ลงสมุดชีวิตตามลำดับเวลาจริง."""
        parent_names = [sim.cast[cid].name for cid in getattr(ch, "parents", ())
                        if 0 <= cid < len(sim.cast)]
        if parent_names:
            born_text = f"{ch.name}ถือกำเนิด เป็นบุตรของ" + "และ".join(parent_names[:2])
        elif ch.born_day >= 0:
            born_text = f"{ch.name}ถือกำเนิดขึ้นในโลก แต่ไม่ปรากฏชื่อบิดามารดาในบันทึก"
        else:
            born_text = f"{ch.name}ถือกำเนิดก่อนยุคที่โลกเริ่มจดบันทึก"
        childhood = list(getattr(ch, "childhood", ()) or ())
        birth_seq = min((int(x.get("seq", 1)) for x in childhood if isinstance(x, dict)), default=1) - 1
        self._journal({"type": "birth", "id": f"birth-{ch.cid}", "seq": birth_seq,
                       "day": ch.born_day, "year": ch.born_day // 365,
                       "cid": ch.cid, "name": ch.name, "text": born_text,
                       "parents": parent_names, "identity": P.short_identity(sim, ch)},
                      backfill=True)
        for item in sorted(childhood, key=lambda x: x.get("day", 0)):
            day = int(item.get("day", ch.born_day))
            if day >= sim.day:
                continue
            self._journal({"type": "childhood", "id": f"child-{ch.cid}-{day}",
                           "seq": int(item.get("seq", birth_seq + 1)),
                           "day": day, "year": day // 365, "cid": ch.cid, "name": ch.name,
                           "action": "เติบโต", "outcome": item.get("outcome", "เติบโต"),
                           "text": item.get("text", ""),
                           "place": P.place_label(sim, item.get("place", ch.place))},
                          backfill=True)

    # ------------------------------------------------------------ ตัดสินใจ (เรียกจาก sim._step)
    def choose(self, actor, sim, weights, others, rng):
        mind = self.minds.get(actor.cid)
        if mind is None or not mind.alive or not mind.enabled:
            return None
        table = _table()
        # เมนูต้องสะท้อนสิ่งที่ทำได้จริง ไม่ใช่รอให้เอนจินตอบภายหลังว่าไม่มีอะไรจะสอน
        # ซ้ำเป็นสิบครั้ง ตัวเลือกที่ต้องมีเป้าถูกกรองอีกชั้นเมื่อรู้คนที่โมเดลเลือกแล้ว
        weights = dict(weights)
        if not any(self._can_teach(actor, other) for other in others):
            weights["ถ่ายทอดวิชา"] = 0.0
        # ฟ้าลิขิต: เรื่องที่ไม่มีใครเลือกเอง ยังเกิดตามน้ำหนักเดิม
        total = sum(v for v in weights.values() if v > 0)
        fate_w = {k: weights.get(k, 0) for k in A.INVOLUNTARY if weights.get(k, 0) > 0}
        if total > 0 and fate_w and rng.random() < sum(fate_w.values()) / total:
            kind = max(fate_w, key=fate_w.get)
            self._pending[actor.cid] = Pending(source="ชะตาฟ้า", step=PR.Step(kind=kind))
            self.stats["fate"] += 1
            return Choice(kind)

        self._notice_changes(mind, actor)
        plan = [PR.Step.from_dict(d) for d in mind.plan]
        interrupted = None
        if mind.interrupted and plan:
            interrupted, plan = plan, []
        stale = sim.day - mind.plan_day > 365 * 3
        step = None
        source = ""
        if plan and not stale and not mind.goal_stale:
            cand = plan[0]
            if self._step_ok(cand, actor, weights, others, table):
                step, plan = cand, plan[1:]
                source = "ตามแผน"
        if step is None and not self._may_think(mind, actor, sim):
            # ---- วันธรรมดา: ถามความจำก่อนโยนลูกเต๋า ----
            # ของเดิมปล่อยให้เอนจินสุ่มตามน้ำหนัก ซึ่งทำให้ตัวละครทำสิ่งที่ตัวเองไม่เคยทำ
            # อยู่เรื่อยๆ ในวันที่ไม่มีอะไรสำคัญ — นิสัยจึงไม่มีความต่อเนื่อง
            # ตรงนี้เกณฑ์ต่ำได้ เพราะทางเลือกอีกทางคือ "สุ่ม" ไม่ใช่ "โมเดลคิด"
            if MC.RECALL_ENABLED:
                got = self._recall(mind, actor, sim, weights, others, table,
                                   bar=MC.RECALL_ROUTINE_CONF)
                if got is not None:
                    mind.plan = []
                    self.stats["recall"] += 1
                    self.stats["recall_routine"] = self.stats.get("recall_routine", 0) + 1
                    mind.recall_streak += 1
                    self._note_act(mind, got.kind)
                    pend = Pending(source="ความเคยชิน", step=got)
                    pend.plan_left = []
                    self._pending[actor.cid] = pend
                    mind.interrupted = False
                    mind.shaken = False
                    tgt = None
                    if got.target_cid is not None:
                        tgt = next((c for c in others if c.cid == got.target_cid), None)
                    return Choice(got.kind, tgt)
            # วันธรรมดาของยุทธภพ — พอจังหวะเวลาถูกย่อยเป็นรายวัน (ดู events.SCALE_OF) ตัวละคร
            # ลงมือบ่อยขึ้นราวสามเท่า ถ้าเรียกโมเดลทุกครั้งที่แผนหมด ค่ารันจะโตตามไปด้วยทั้งที่
            # การกระทำส่วนใหญ่เป็นงานประจำวัน (ทำนา เดินตลาด ลาดตระเวน) ที่ไม่ต้องชั่งใจอะไร
            # วันพวกนั้นปล่อยให้ลูกเต๋าเดิน แต่ยังถูกบันทึกเป็นเหตุการณ์ในสมุดชีวิตเหมือนเดิม
            mind.plan = []
            mind.n_instinct += 1
            self.stats["routine"] = self.stats.get("routine", 0) + 1
            self._pending[actor.cid] = Pending(source="วันธรรมดา")
            mind.interrupted = False
            return None
        # ---- ความจำเชิงเชื่อมโยง: ถามตัวเองก่อนว่า "เคยเจอเรื่องแบบนี้ไหม" ----
        # วางไว้ **หลัง** _may_think โดยเจตนา จังหวะที่เป็นการตัดสินใจของชีวิต (ติดคอขวด
        # มีคนมาทำอะไรกับเรา เป้าหมายค้างคา) จึงยังได้คิดด้วยโมเดลจริงเสมอ ความจำรับงาน
        # เฉพาะวันที่เหลือ ซึ่งวัดแล้วเป็นส่วนใหญ่ของการเรียกโมเดลทั้งหมด
        #
        # วัดกับบันทึกจริง 575 การตัดสินใจของ LLM (แบ่งตามเวลา ความจำเห็นแต่อดีต):
        #   ทายตรงกับที่ LLM เลือก 41% จาก 24 ตัวเลือก · เดาอันที่พบบ่อยสุดได้ 17% · สุ่ม 6%
        #   และแม่นขึ้นตามความมั่นใจอย่างเป็นลำดับ: conf<0.3 -> 29% · 0.6-0.9 -> 44%
        #   · conf>=0.9 -> 63%
        # เพดานที่แท้จริงไม่ใช่ 100%: LLM เอง (temperature 0.8) เลือกซ้ำของตัวเองใน
        # สถานการณ์เดียวกันเป๊ะแค่ **68.6%** (110 กลุ่ม · มัธยฐาน 60% · เหมือนกันทุกครั้ง
        # เพียง 37 กลุ่ม) การดึงคืนที่ conf>=0.9 จึงอยู่ที่ราว 91% ของเพดานที่ทำได้จริง
        # ---- วันที่ต้องคิด: ข้ามโมเดลได้เฉพาะเมื่อ "เคยเจอเรื่องนี้มาแล้วชัดๆ" ----
        # เกณฑ์สูงกว่าวันธรรมดา เพราะทางเลือกอีกทางคือการคิดจริง ไม่ใช่การสุ่ม
        # และจังหวะที่เป็นจุดพลิกของชีวิตจริงๆ (ติดคอขวด · มีคนมาทำอะไรกับเรา ·
        # เป้าหมายค้างคา) ถูกกันไว้ไม่ให้ความจำแตะเลย — ฉากสำคัญต้องได้โมเดลคิดเสมอ
        if step is None and self._turning_point(mind, actor):
            self.stats["turning"] = self.stats.get("turning", 0) + 1
        if step is None and MC.RECALL_ENABLED and not self._turning_point(mind, actor):
            got = self._recall(mind, actor, sim, weights, others, table,
                               bar=MC.RECALL_TRUST_CONF)
            if got is not None:
                step, source = got, "ความจำ"
                mind.plan = []
                plan = []
                self.stats["recall"] += 1
                self.stats["recall_think"] = self.stats.get("recall_think", 0) + 1
                mind.recall_streak += 1
                self._note_act(mind, step.kind)

        if step is None:
            info, steps, err = self._think(mind, actor, sim, weights, others, table, interrupted)
            feasible = []
            for candidate in steps:
                if self._step_ok(candidate, actor, weights, others, table):
                    feasible.append(candidate)
                elif feasible:
                    break
            steps = feasible
            if not steps and not err:
                err = "แผนที่ตอบมาทำไม่ได้จริงในสถานการณ์นี้"
            if steps:
                step, plan = steps[0], steps[1:]
                source = "คิดใหม่"
                pend = Pending(source=source, step=step, info=info)
                # ประทับไว้เป็นความจำ — **เฉพาะการตัดสินใจที่โมเดลคิดจริง**
                # จงใจไม่เก็บสิ่งที่ตัวเองดึงคืนมา ไม่งั้นจะเป็นป้อนกลับที่ตอกย้ำคำเดาของ
                # ตัวเองจนกลายเป็นวงจรปิด ความจำต้องผูกกับการตัดสินใจที่มีเหตุผลรองรับ
                self._store_memory(mind, actor, sim, others, step.kind)
                mind.recall_streak = 0        # คิดจริงแล้ว เริ่มนับความเคยชินใหม่
                self._note_act(mind, step.kind)
            else:
                mind.plan = []
                mind.n_instinct += 1
                self.stats["instinct"] += 1
                self._pending[actor.cid] = Pending(source="สัญชาตญาณ", error=err)
                mind.interrupted = False
                return None
        else:
            pend = Pending(source=source, step=step)
            mind.n_plan_steps += 1
            self.stats["plan_steps"] += 1
            self._store_memory(mind, actor, sim, others, step.kind)
            self._note_act(mind, step.kind)
        mind.plan = [s.to_dict() for s in plan]
        mind.interrupted = False
        mind.shaken = False
        pend.plan_left = list(mind.plan)
        self._pending[actor.cid] = pend
        target = None
        if step.target_cid is not None:
            target = next((c for c in others if c.cid == step.target_cid), None)
        return Choice(step.kind, target)

    @staticmethod
    def _note_act(mind, kind):
        acts = getattr(mind, "recent_acts", None)
        if acts is None:
            acts = mind.recent_acts = []
        acts.append(kind)
        del acts[:-MC.RECALL_REPEAT_WINDOW]

    def _memory_of(self, mind, actor):
        mem = getattr(mind, "recall_mem", None)
        if mem is None:
            mem = mind.recall_mem = HF.Memory(beta=SIT.beta_of(actor))
        # β เป็นนิสัย และนิสัยเปลี่ยนได้ตามจิตมารที่หนักขึ้น จึงคิดใหม่ทุกครั้งที่ใช้
        mem.beta = SIT.beta_of(actor)
        return mem

    def _store_memory(self, mind, actor, sim, others, kind):
        try:
            mem = self._memory_of(mind, actor)
            mem.store(SIT.encode(sim, actor, others), kind, day=sim.day)
        except Exception as exc:                       # ความจำพังไม่ควรล้มการรัน
            mind.last_error = f"ประทับความจำไม่สำเร็จ: {exc}"

    @staticmethod
    def _turning_point(mind, actor):
        """จุดพลิกของชีวิต — ห้ามใช้ความจำ ต้องได้คิดจริงเสมอ

        สามอย่างนี้คือสิ่งที่ผู้อ่านจะจำได้: วันที่ติดคอขวดแล้วต้องเลือกว่าจะเสี่ยงไหม
        วันที่มีคนมาทำอะไรกับเรา และวันที่รู้ตัวว่าสิ่งที่ตามมาทั้งชีวิตไม่มีความหมายแล้ว
        ถ้าปล่อยให้ความจำตอบวันพวกนี้ เรื่องจะแบนลงทันทีโดยประหยัดได้ไม่กี่การเรียก
        """
        # จุดพลิกต้องเป็น **เหตุการณ์** ไม่ใช่ **สภาพ** — บทเรียนที่ได้จากการวัดสองรอบ
        #
        # ไม่รวม goal_stale: มันตั้งทุกครั้งที่ขั้นหรือสำนักเปลี่ยน
        #   (วัดจริง: รวมแล้ว 213/260 = 82% ของวันที่ต้องคิดกลายเป็นจุดพลิก)
        # ไม่รวม at_bottleneck(): หลังรื้อเศรษฐกิจปราณ ตัวละครค้างอยู่ที่คอขวด **เป็นสิบปี**
        #   เพราะจังหวะที่ควรข้ามถูกคุมด้วย break_timing และคลังฟ้าที่ไม่พอ
        #   (วัดจริง: รวมแล้ว 263/315 = 83%) คอขวดจึงเป็นสภาพ ไม่ใช่นาทีสำคัญ
        #   และ _may_think รับประกันอยู่แล้วว่าคนติดคอขวดได้คิด ส่วนการดึงคืนก็ยังต้อง
        #   ผ่านเกณฑ์ความคล้ายกับความมั่นใจสูง ถ้าเขาเคยอยู่ที่คอขวดนี้แล้วเลือกอย่างเดิม
        #   ทุกครั้ง การให้ความจำตอบก็ตรงกับนิสัยเขาพอดี ("เขารออย่างที่เคยรอ")
        # เหลือเฉพาะ shaken: มีคนลงมือกับเราจริง (ต่อสู้ เลือด ทรยศ ความตาย ชิงทรัพย์)
        return bool(mind.shaken)

    def _recall(self, mind, actor, sim, weights, others, table, bar=None):
        """ดึงการกระทำจากความจำ คืน Step หรือ None ถ้าความจำตอบไม่ได้แน่พอ

        คัดเมนูก่อนดึง ไม่ใช่หลัง — ความจำที่ชี้ไปยังการกระทำที่ทำไม่ได้ตอนนี้ต้องไม่ถูก
        นับส่วนแบ่ง ไม่งั้นความมั่นใจที่รายงานจะต่ำกว่าความจริงและเกณฑ์จะเพี้ยน
        """
        why = self.stats.setdefault("recall_why", {})
        def _no(tag):
            why[tag] = why.get(tag, 0) + 1
            return None
        # ---- เพดานความเคยชิน ----
        # วัดจริงตอนไม่มีเพดาน: ความจำตอบ 2,573 จาก 2,774 การตัดสินใจ (93%) แล้ว
        # **เอนโทรปีของการกระทำต่อคนร่วงจาก 2.95 เหลือ 1.58 บิต** ตัวละครวนทำสิ่งเดิม
        # ความมั่นใจสูงไม่ได้แปลว่าควรเชื่อทุกครั้ง — ความจำที่ถูกย้ำจะยิ่งมั่นใจขึ้นเรื่อยๆ
        # เป็นป้อนกลับบวก เพดานตรงนี้ตัดวงจรนั้นโดยตรง ไม่ใช่หวังให้เกณฑ์ความมั่นใจทำ
        # และอ่านเป็นเรื่องได้: คนทบทวนชีวิตตัวเองเป็นระยะ ไม่ใช่ทำตามความเคยชินตลอดไป
        if mind.recall_streak >= MC.RECALL_MAX_STREAK:
            return _no("ถึงเพดานความเคยชิน")
        mem = self._memory_of(mind, actor)
        if len(mem) < MC.RECALL_MIN_MEMORIES:
            return _no("ความจำน้อย")
        allowed = [k for k, v in weights.items() if v > 0 and k not in A.INVOLUNTARY]
        if not allowed:
            return _no("ไม่มีเมนู")
        try:
            x = SIT.encode(sim, actor, others)
        except Exception as exc:
            mind.last_error = f"เข้ารหัสสถานการณ์ไม่สำเร็จ: {exc}"
            return _no("เข้ารหัสพัง")
        got = mem.recall(x, allowed=allowed)
        self._recall_log(got)
        if got.kind is None:
            return _no("ไม่มีความจำที่ตรงเมนู")
        # เกณฑ์สองชั้น ต้องผ่านทั้งคู่
        #   best_sim = "เคยอยู่ในสถานการณ์ที่เกือบเหมือนกันนี้มาแล้วจริงไหม"
        #   confidence = "ความจำที่เกี่ยวข้องชี้ไปทางเดียวกันหรือขัดกันเอง"
        # ต้องมีสองชั้นเพราะตอนความจำยังน้อย ส่วนแบ่งจะถูกหารกันหลายทางจนความมั่นใจ
        # ต่ำเสมอ แม้จะเจอสถานการณ์เดิมเป๊ะ — วัดจริงในรันทดสอบ: ความมั่นใจเกาะอยู่
        # ในช่วง 0.0-0.4 ทั้งที่ความคล้ายของความจำที่ใกล้สุดแตะ 0.99
        if got.best_sim < MC.RECALL_MIN_SIM:
            return _no("ไม่คล้ายพอ")
        if got.confidence < (MC.RECALL_TRUST_CONF if bar is None else bar):
            return _no("ไม่มั่นใจพอ")
        # กันลูป: ถ้าจะทำสิ่งเดิมที่เพิ่งทำติดกันมาแล้ว ให้ไปคิดเอง
        # ความเคยชินที่ดีคือ "เขามักทำแบบนี้" ไม่ใช่ "เขาทำแบบนี้ซ้ำไม่หยุด"
        recent = list(getattr(mind, "recent_acts", ()))[-MC.RECALL_REPEAT_WINDOW:]
        if recent and recent.count(got.kind) >= MC.RECALL_REPEAT_MAX:
            return _no("จะทำซ้ำของเดิม")
        step = PR.Step(kind=got.kind, why="เคยเจอเรื่องแบบนี้มาแล้ว")
        if A.needs_target(got.kind, table):
            # ความจำบอกว่า "ทำอะไร" ไม่ได้บอกว่า "กับใคร" — เป้าต้องเลือกจากคนที่อยู่ตรงนั้น
            # จริงตอนนี้ ใช้กติกาเดียวกับที่เอนจินใช้อยู่แล้ว ไม่คิดใหม่
            t = self._recall_target(got.kind, actor, others)
            if t is None:
                return _no("หาเป้าไม่ได้")
            step.target_cid = t.cid
            step.target_name = t.name
        if not self._step_ok(step, actor, weights, others, table):
            return _no("เป้าทำไม่ได้")
        return step

    def _recall_log(self, got):
        """เก็บฮิสโตแกรมความมั่นใจไว้ให้ปรับเกณฑ์ได้จากข้อมูลจริง ไม่ใช่เดา"""
        book = self.stats.setdefault("recall_conf", [0, 0, 0, 0, 0])
        i = min(4, max(0, int(got.confidence * 5)))
        book[i] += 1

    @staticmethod
    def _recall_target(kind, actor, others):
        """เลือกเป้าให้การกระทำที่ดึงคืนมา — คนที่ "ค้างเรื่องกันมากที่สุด" ก่อน

        เรียงแบบคงที่ (ไม่ใช้ rng) เพราะการดึงคืนต้องทำซ้ำได้ ซึ่งเป็นเหตุผลหลักข้อหนึ่ง
        ที่ใช้ความจำแทนโมเดล
        """
        pool = [o for o in others if o is not None and o.cid != actor.cid and o.alive]
        if not pool:
            return None
        if kind in ("ล้างแค้น", "ลอบสังหาร", "ชิงสมบัติ", "ดักปล้น", "ทรยศ"):
            rivals = [o for o in pool if o.cid in actor.rivals]
            if rivals:
                return max(rivals, key=lambda o: (actor.rivals.get(o.cid, 0), -o.cid))
            return None
        if kind in ("ให้สัญญา", "ถ่ายทอดวิชา", "กำเนิดทายาท"):
            bonds = [o for o in pool if o.cid in actor.bonds]
            if bonds:
                return max(bonds, key=lambda o: (actor.bonds.get(o.cid, 0), -o.cid))
        return min(pool, key=lambda o: o.cid)

    @staticmethod
    def _can_teach(actor, target):
        mastery = getattr(actor, "mastery", {})
        if not isinstance(mastery, dict):
            return False
        target_skills = set(getattr(target, "skills", ()) or ())
        return any(name not in target_skills and mastery.get(name, 0) >= C.TEACH_MIN_REPS
                   for name in (getattr(actor, "skills", ()) or ()))

    def _step_ok(self, step, actor, weights, others, table):
        if weights.get(step.kind, 0) <= 0:
            return False
        if A.needs_target(step.kind, table):
            target = next((c for c in others if c.cid == step.target_cid), None)
            if target is None:
                return False
            if step.kind == "ถ่ายทอดวิชา":
                # "อยากเรียนจากเขา" คือทิศตรงข้ามกับ action สอนเขา ปฏิเสธแทนการบันทึก
                # เหตุผลกับการกระทำที่ขัดกันลงเป็นความทรงจำถาวร
                reverse = ("เรียนรู้จาก", "ได้วิชาจาก", "ขอวิชาจาก", "ให้เขาสอน")
                if any(word in (step.why or "") for word in reverse):
                    return False
                return self._can_teach(actor, target)
            if step.kind == "ให้สัญญา":
                # คำสัญญาเดิมยังอยู่ การกล่าวซ้ำกับคนเดิมโดยไม่มีเนื้อหาใหม่ไม่ใช่เหตุการณ์ใหม่
                if actor.bonds.get(target.cid, 0) > 0 and target.bonds.get(actor.cid, 0) > 0:
                    return False
            return True
        return True

    def _notice_changes(self, mind, ch):
        """ชีวิตเปลี่ยนครั้งใหญ่ (ขั้นพลัง/สำนัก) -> เป้าหมายชีวิตควรถูกทบทวน"""
        if mind.last_realm >= 0 and ch.realm != mind.last_realm:
            mind.goal_stale = mind.goal_stale or abs(ch.realm - mind.last_realm) >= 2
        if ch.org != mind.last_org:
            mind.goal_stale = True
        mind.last_realm, mind.last_org = ch.realm, ch.org

    @staticmethod
    def _may_think(mind, actor, sim):
        """ถึงเวลาคิดใหญ่หรือยัง — กันไม่ให้โมเดลถูกเรียกทุกวันธรรมดา

        คิดได้เสมอเมื่อ: ยังไม่เคยคิด · มีคนมาทำอะไรกับเรา (interrupted) · เป้าหมายค้างคา
        · หรือสะสมถึงคอขวดแล้ว (จังหวะรายปี — เรื่องปิดด่าน/ทะลวงขั้นเป็นการตัดสินใจของชีวิต
        ที่ต้องได้ชั่งใจเอง ไม่ใช่ปล่อยลูกเต๋า)
        """
        if mind.interrupted or mind.goal_stale or not mind.long_goal:
            return True
        if actor.at_bottleneck():
            return True
        return sim.day - getattr(mind, "last_think_day", -10 ** 9) >= MC.THINK_MIN_DAYS

    def _think(self, mind, actor, sim, weights, others, table, interrupted):
        ask_goal = (not mind.long_goal or mind.goal_stale
                    or sim.day - mind.long_goal_day > MC.LONG_GOAL_REFRESH_DAYS)
        ctx = PR.build(sim, mind, actor, weights, others, table, ask_goal, interrupted)
        if not ctx.menu:
            return {}, [], "ไม่มีทางเลือกที่ทำได้"
        self.activity = f"{actor.name} กำลังคิด…"
        t0 = time.time()
        try:
            data = self.backend.think_json(ctx.system, ctx.user)
        except Exception as exc:   # ติดต่อไม่ได้/ตอบพัง — ตัวละครยังต้องมีชีวิตต่อด้วยสัญชาตญาณ
            mind.last_error = str(exc)[:200]
            self.stats["errors"] += 1
            self.activity = f"{actor.name}: {mind.last_error}"
            logger.warning("mind: %s คิดไม่สำเร็จ: %s", actor.name, exc)
            return {}, [], mind.last_error
        info, steps = PR.parse(data, ctx, sim, table)
        self.activity = ""
        if not steps:
            mind.last_error = "คำตอบไม่มีการกระทำที่ทำได้จริง"
            self.stats["errors"] += 1
            return info or {}, [], mind.last_error
        mind.n_thinks += 1
        self.stats["thinks"] += 1
        mind.last_error = ""
        mind.last_thought = info.get("thought", "")
        mind.emotion = info.get("emotion", "") or mind.emotion
        mind.short_goal = info.get("short_goal", "") or mind.short_goal
        if ask_goal and info.get("long_goal"):
            mind.long_goal = info["long_goal"]
            mind.long_goal_day = sim.day
            mind.goal_stale = False
        for cid, text in info.get("feelings", {}).items():
            mind.impressions[cid] = text
        if len(mind.impressions) > MC.IMPRESSION_CAP:
            for cid in list(mind.impressions)[:-MC.IMPRESSION_CAP]:
                del mind.impressions[cid]
        mind.inbox = []
        mind.plan_day = sim.day
        mind.last_think_day = sim.day
        info["seconds"] = round(time.time() - t0, 1)
        info["menu"] = list(ctx.menu)
        return info, steps, ""

    def take_destination(self, actor, options):
        """เรียกจาก resolve('เดินทาง') — คืนจุดหมายที่จิตใจเลือกไว้ถ้ายังไปได้ ไม่งั้น None"""
        pend = self._pending.get(actor.cid)
        if pend is None or pend.step is None or pend.step.place is None:
            return None
        return pend.step.place if pend.step.place in options else None

    def skip_side_rolls(self, actor):
        """คนที่เลือกเองแล้ว ไม่ต้องโดนสุ่มท้าชิงตำแหน่งในสำนักทับการตัดสินใจ"""
        pend = self._pending.get(actor.cid)
        return pend is not None and pend.source in ("คิดใหม่", "ตามแผน")

    # ------------------------------------------------------------ หลังลงมือ
    def after_action(self, actor, sim, kind, target, event):
        pend = self._pending.pop(actor.cid, None)
        mind = self.minds.get(actor.cid)
        if mind is None or pend is None or event is None:
            return
        step = pend.step
        tname = target.name if target is not None else ""
        dest = ""
        if kind == "เดินทาง" and actor.travel_dest >= 0:
            dest = P.place_label(sim, actor.travel_dest)
        info = pend.info
        entry = {
            "type": "decision", "id": f"d-{event.seq}", "seq": event.seq, "day": event.day,
            "year": event.day // 365, "cid": actor.cid, "name": actor.name,
            "realm": actor.realm_name(), "place": P.place_label(sim, event.place),
            "source": pend.source, "action": kind, "target": tname,
            "target_cid": target.cid if target is not None else None, "dest": dest,
            "why": step.why if step is not None else "",
            "thought": info.get("thought", ""), "emotion": info.get("emotion", "") or mind.emotion,
            # ใจตอนตัดสินใจ (เจ็ดอารมณ์ หกปรารถนา) — จดไว้ทุกครั้งเพื่อให้อ่านย้อนได้ว่าเขาเปลี่ยน
            # ไปตอนไหนและเพราะอะไร "emotion" ข้างบนเป็นคำที่โมเดลรายงานเอง ส่วนนี่คือใจจริงในเครื่อง
            "heart": f"{EM.emotion_words(actor)} | {EM.desire_words(actor)}",
            "short_goal": mind.short_goal, "long_goal": mind.long_goal,
            "outcome": event.outcome, "text": event.text,
            "details": {str(k): str(v) for k, v in (event.deltas or {}).items()},
            "side": [], "plan_left": [f"{d['kind']}{(' กับ ' + d['target_name']) if d.get('target_name') else ''}"
                                                  for d in pend.plan_left],
            "error": pend.error, "seconds": info.get("seconds"),
            "alive": actor.alive,
            # snapshot หลังเอนจินตัดสินผล ใช้บังคับนักเล่าเรื่องไม่ให้แต่งว่าคนที่ยังอยู่ตายไปแล้ว
            "actor_alive_after": bool(actor.alive),
            "target_alive_after": bool(target.alive) if target is not None else None,
        }
        if pend.source == "คิดใหม่":
            mind.plan_origin, mind.plan_thought = entry["id"], entry["thought"]
        elif pend.source == "ตามแผน":
            entry["plan_origin"], entry["plan_thought"] = mind.plan_origin, mind.plan_thought
        if pend.side:
            entry["side"] = [t for t in pend.side if t != event.text][:6]
        if target is not None:
            entry["target_identity"] = P.short_identity(sim, target)
        self._journal(entry)
        who = f"กับ{tname}" if tname else ""
        mind.remember(f"ปีที่ {entry['year']}: ข้า{kind}{who} — {event.outcome}: {event.text}")
        if target is not None and not target.alive:
            self._finish_dead_target(mind, target, kind, event)
        if pend.source in ("คิดใหม่", "ตามแผน"):
            self._maybe_story(entry, event)
        if not actor.alive:
            self._mark_dead(sim, actor, event)
        if target is not None and target.cid in self.minds and not target.alive:
            self._mark_dead(sim, target, event)

    @staticmethod
    def _finish_dead_target(mind, target, kind, event):
        """ปิดเป้าหมายที่สำเร็จ/หมดความหมายเมื่อคนที่ลงมือด้วยตาย

        เจอจริงในรัน Compare-Minds: เหอม่อสังหารกู่ซานเฉินแล้ว แต่ long_goal ยังเป็นการทำให้ลูก
        สำนึกผิด โมเดลจึงพูดว่าจะล้างแค้นคนตายต่ออีกหลายปี การตายของเป้าหมายต้องบังคับให้คิดชีวิตใหม่
        ในครั้งถัดไป และแผนเก่าที่อ้างคนตายต้องไม่ถูกนำมาทำต่อ
        """
        mind.remember(f"ปีที่ {event.day // 365}: {target.name}ตายแล้วจากเหตุการณ์นี้ "
                      "ข้าต้องยอมรับว่าเป้าหมายเดิมเกี่ยวกับเขาจบลงแล้ว")
        mind.inbox.append(f"{target.name}ตายแล้ว เป้าหมายหรือแผนที่มุ่งไปหาเขาทำต่อไม่ได้")
        del mind.inbox[:-MC.INBOX_CAP]
        mind.plan = []
        mind.goal_stale = True
        mind.interrupted = True
        mind.scars = [s for s in mind.scars if s.get("cid") != target.cid]

        # ถ้าเป้าหมายระบุชื่อคนตาย หรือเป็นเป้าหมายแก้แค้นของการกระทำที่เพิ่งจบ ให้ล้างข้อความทิ้ง
        # ไม่ส่งประโยคที่หมดอายุย้อนเข้า prompt ให้โมเดลยึดติดซ้ำ ส่วน goal_stale ทำให้ขอเป้าหมายใหม่
        revenge_words = ("ล้างแค้น", "แก้แค้น", "เอาคืน", "สำนึกผิด", "ชดใช้")
        if target.name in mind.short_goal or kind in MC.HOSTILE_TARGET_KINDS:
            mind.short_goal = ""
        if target.name in mind.long_goal or (kind in MC.HOSTILE_TARGET_KINDS
                                              and any(w in mind.long_goal for w in revenge_words)):
            mind.long_goal = ""

    def on_event(self, ev, sim):
        """ทุกเหตุการณ์ของโลกผ่านที่นี่ — ต้องถูกมาก (เช็ค dict สองครั้งแล้วจบสำหรับคนทั่วไป)"""
        a, t = ev.actor, ev.target
        # คนในแผนอาจถูกบุคคลที่สามฆ่า เหตุการณ์นั้นไม่มี mind เป็น actor/target แต่แผน
        # "ไปช่วย/ไปสอน" ยังต้องหมดอายุทันที ไม่เช่นนั้นอาจค้างเป็นพันวัน
        for cid in (a, t):
            if isinstance(cid, int) and 0 <= cid < len(sim.cast) and not sim.cast[cid].alive:
                self._retire_dead_references(sim.cast[cid])
        in_a = a in self.minds and self.minds[a].enabled
        in_t = t is not None and t in self.minds and self.minds[t].enabled
        if not in_a and not in_t:
            return
        cast = sim.cast
        if in_a and a in self._pending:
            pend = self._pending[a]
            if pend.step is None or ev.kind != pend.step.kind:
                pend.side.append(ev.text)
        elif in_a and self.minds[a].alive and self._repeat_of_year(a, ev):
            # เหตุการณ์ซ้ำชนิดเดียวกันในปีเดียวกัน (เช่น มารจับคนกินทีละหลายสิบคน) ไม่ได้บอกอะไรใหม่
            # เกี่ยวกับตัวละคร — จดครั้งแรกพอ ไม่งั้นบันทึกชีวิตจมอยู่ใต้บรรทัดซ้ำ (รันจริง 487/917 บรรทัด)
            if not cast[a].alive:
                self._mark_dead(sim, cast[a], ev)
        elif in_a and self.minds[a].alive:
            m = self.minds[a]
            m.remember(f"ปีที่ {ev.day // 365}: {ev.text}")
            self._journal({"type": "event", "id": f"e-{ev.seq}-{a}", "seq": ev.seq, "day": ev.day,
                           "year": ev.day // 365, "cid": a, "name": m.name, "action": ev.kind,
                           "outcome": ev.outcome, "text": ev.text,
                           "details": {str(k): str(v) for k, v in (ev.deltas or {}).items()},
                           "place": P.place_label(sim, ev.place), "alive": cast[a].alive,
                           "heart": f"{EM.emotion_words(cast[a])} | {EM.desire_words(cast[a])}"}
                          , story=ev.outcome in MC.STORY_HAPPENED_OUTCOMES, event=ev, mind=m)
            if not cast[a].alive:
                self._mark_dead(sim, cast[a], ev)
        if in_t and t != a and self.minds[t].alive:
            m = self.minds[t]
            actor_name = cast[a].name if 0 <= a < len(cast) else "ใครบางคน"
            line = f"{actor_name} {ev.kind} ข้า — {ev.outcome}: {ev.text}"
            # เหตุผลในใจของผู้ที่ลงมือ (ยังอยู่ใน _pending เพราะ after_action ถูกเรียกหลัง on_event)
            # ถ้าไม่ส่งต่อ อีกฝ่ายจะรู้แค่ "ถูกกระทำ" ไม่รู้ว่าทำเพราะอะไร บทสนทนาจึงไม่มีอะไรให้ตอบ
            his = self._pending.get(a)
            why = his.step.why if his is not None and his.step is not None else ""
            if why:
                line += f" (เขาบอกว่า: {why})"
            if a in self.minds and MC.SOCIAL_REPLY:
                m.interrupted = True       # คนที่เรารู้จักมาหาเรา ควรได้คิดว่าจะตอบอย่างไร
            m.inbox.append(line)
            del m.inbox[:-MC.INBOX_CAP]
            m.remember(f"ปีที่ {ev.day // 365}: {line}")
            if MC.INTERRUPT_TAGS.intersection(ev.tags or ()):
                m.interrupted = True
                m.shaken = True
            if ev.kind in MC.SCAR_KINDS and ev.outcome in MC.SCAR_OUTCOMES and cast[t].alive:
                self._add_scar(m, a, actor_name, ev)
            self._journal({"type": "received", "id": f"r-{ev.seq}-{t}", "seq": ev.seq, "day": ev.day,
                           "year": ev.day // 365, "cid": t, "name": m.name, "action": ev.kind,
                           "by": actor_name, "by_cid": a, "outcome": ev.outcome, "text": ev.text,
                           "details": {str(k): str(v) for k, v in (ev.deltas or {}).items()},
                           "place": P.place_label(sim, ev.place), "alive": cast[t].alive,
                           "heart": f"{EM.emotion_words(cast[t])} | {EM.desire_words(cast[t])}"}
                          , story=ev.outcome in MC.STORY_HAPPENED_OUTCOMES, event=ev, mind=m)
            if not cast[t].alive:
                self._mark_dead(sim, cast[t], ev)

    def _retire_dead_references(self, dead):
        """ยกเลิกอนาคตที่ต้องมีคนตายอยู่ แต่เก็บการไว้อาลัย/สืบความจริง/แก้แค้นไว้."""
        future_verbs = ("ช่วย", "ไปหา", "สอน", "ถ่ายทอด", "ประลอง", "ให้สัญญา",
                        "แต่งงาน", "มีทายาท", "ปกป้อง", "ร่วมเดินทาง")
        for mind in self.active():
            if mind.cid == dead.cid:
                continue
            kept = [p for p in mind.plan if p.get("target_cid") != dead.cid]
            changed = len(kept) != len(mind.plan)
            short = mind.short_goal or ""
            if dead.name in short and any(word in short for word in future_verbs):
                mind.short_goal = ""
                changed = True
            if not changed:
                continue
            mind.plan = kept
            mind.goal_stale = True
            mind.interrupted = True
            note = f"{dead.name}ตายแล้ว แผนที่ต้องพบหรือช่วยเขาทำต่อไม่ได้"
            if note not in mind.inbox:
                mind.inbox.append(note)
                del mind.inbox[:-MC.INBOX_CAP]

    @staticmethod
    def _add_scar(m, by_cid, by_name, ev):
        """จำผู้ที่เกือบฆ่าเรา — ผู้ก่อคนเดิมนับครั้งเพิ่ม ไม่เพิ่มบรรทัด แล้วให้ทบทวนเป้าหมายชีวิต

        ทำไม goal_stale: เกือบตายเป็นจุดเปลี่ยนชีวิตแบบเดียวกับเลื่อนขั้น/ย้ายสำนัก ตัวละครควรได้ถามตัวเองใหม่
        ว่าจะใช้ชีวิตต่อไปอย่างไร — แต่คำตอบเป็นของตัวละคร ไม่ได้บังคับให้ต้องแก้แค้น
        """
        year = ev.day // 365
        old = next((s for s in m.scars if s.get("cid") == by_cid), None)
        if old is not None:
            m.scars.remove(old)
            old.update(year=year, outcome=ev.outcome, times=old.get("times", 1) + 1)
            m.scars.append(old)
        else:
            m.scars.append({"cid": by_cid, "name": by_name, "year": year, "outcome": ev.outcome, "times": 1})
        del m.scars[:-MC.SCAR_CAP]
        m.goal_stale = True

    def _repeat_of_year(self, cid, ev):
        """True ถ้าเหตุการณ์ชนิดยุบรวมนี้เคยจดไปแล้วในปีเดียวกัน (และนับเพิ่ม) — ครั้งแรกคืน False"""
        if ev.kind not in MC.COLLAPSE_KINDS or ev.outcome in MC.COLLAPSE_KEEP_OUTCOMES:
            return False
        year = ev.day // 365
        key = (cid, year, ev.kind)
        if key in self._collapsed:
            self._collapsed[key] += 1
            return True
        # ทิ้งตัวนับของปีที่ผ่านไปแล้ว ไม่ให้โตไม่มีเพดานในโลกที่เดินหลายร้อยปี
        for old in [k for k in self._collapsed if k[1] < year - 1]:
            del self._collapsed[old]
        self._collapsed[key] = 1
        return False

    def _mark_dead(self, sim, ch, ev):
        m = self.minds.get(ch.cid)
        if m is None or not m.alive or ch.alive:
            return
        m.alive = False
        m.death_day = sim.day
        m.death_cause = getattr(ch, "death_cause", "") or ev.text
        m.plan = []
        self._pending.pop(ch.cid, None)
        self._journal({"type": "death", "id": f"death-{ch.cid}", "seq": ev.seq, "day": sim.day,
                       "year": sim.day // 365, "cid": ch.cid, "name": ch.name,
                       "text": f"{ch.name} สิ้นชีวิต — {m.death_cause}",
                       "long_goal": m.long_goal, "age": ch.age(sim.day)})
        # ผู้สืบเรื่องต่อ: คนที่ฆ่า > ศิษย์ > ลูก > คู่ครอง > คนที่ผูกพันที่สุด
        # นับเฉพาะคนที่ตั้งใจสู้กันจริง — มารที่บุกมาจับคนกินไม่ใช่ "ผู้สืบเรื่อง" (รันจริงเกิดลูกโซ่มารกินคน)
        killer = (ev.actor if ev.target == ch.cid and ev.actor != ch.cid
                  and ev.kind in MC.SUCCESSOR_KILLER_KINDS else None)
        order = []
        if killer is not None and killer >= 0:
            order.append((killer, f"ผู้ที่ปลิดชีพ{ch.name}"))
        order += [(c, f"ศิษย์ของ{ch.name}ผู้ล่วงลับ") for c in ch.disciples]
        order += [(c, f"ทายาทของ{ch.name}ผู้ล่วงลับ") for c in ch.children]
        if ch.spouse is not None:
            order.append((ch.spouse, f"คู่ครองของ{ch.name}ผู้ล่วงลับ"))
        order += [(c, f"คนที่ผูกพันกับ{ch.name}ผู้ล่วงลับ")
                  for c, _ in sorted(ch.bonds.items(), key=lambda kv: -kv[1])[:2]]
        self.successor_hints += order[:3]

    # ------------------------------------------------------------ เรื่องเล่า
    def _maybe_story(self, entry, event):
        if not MC.STORY_ENABLED:
            return
        p = 0.0
        for tag in event.tags or ():
            p = max(p, MC.STORY_P.get(tag, 0.0))
        if (event.outcome in MC.STORY_ALWAYS_OUTCOMES or not entry["alive"]
                or event.outcome in MC.STORY_HAPPENED_OUTCOMES):
            p = 1.0      # ฉากที่พลิกชีวิตตัวละคร ไม่ปล่อยให้การสุ่มทิ้งไป
        # ใช้ seq เป็นตัวสุ่มคงที่ ไม่แตะ RNG ของโลก
        if p <= 0 or ((event.seq * 2654435761) % 1000) / 1000.0 >= p:
            return
        if len(self.story_queue) < MC.STORY_QUEUE_CAP:
            self.story_queue.append(entry)

    # ------------------------------------------------------------ บันทึก
    def _journal(self, entry, story=False, event=None, mind=None, backfill=False):
        # วันที่แบบปฏิทินโลก + ช่วงเวลาของเหตุการณ์ (วัน/เดือน/ปี) — ก่อนหน้านี้บันทึกมีแต่ "ปี"
        # ผู้อ่านจึงเห็นทุกอย่างเป็นการกระโดดข้ามปี ทั้งที่ในเครื่องยนต์มีวันจริงอยู่แล้ว
        if entry.get("day") is not None and "date" not in entry:
            entry["date"] = E.date_words(entry["day"])
        if entry.get("action") and "scale" not in entry:
            entry["scale"] = E.SCALE_OF.get(entry["action"], "")
        # ความประหลาดใจเป็นบิต — ทำให้หน้าอ่านเลือกไคลแมกซ์ของบทได้เองจากตัวเลข ไม่ใช่จาก
        # ช่วงเวลาอย่างเดียว (ดู physics.surprisal และ chapter_view)
        if event is not None and "surprise" not in entry:
            entry["surprise"] = round(float(getattr(event, "surprise", 0.0) or 0.0), 2)
        """เขียนบันทึกหนึ่งบรรทัด และถ้า story=True ให้เข้าคิวแต่งเรื่องด้วย

        เหตุการณ์ที่ "เกิดกับ" ตัวละครไม่มีความคิด/เหตุผลเหมือนการตัดสินใจ จึงแนบเป้าหมายชีวิตกับอารมณ์
        ล่าสุดของตัวละครให้นักเล่าเรื่องแทน (สำเนาไปคิว ไม่เขียนลงบันทึกให้บวม)
        """
        entry.setdefault("at", time.time())
        if not backfill:
            self.recent.append(entry)
            del self.recent[:-300]
        if story and event is not None and mind is not None:
            self._maybe_story(dict(entry, long_goal=mind.long_goal, emotion=mind.emotion), event)
        if not self.journal_path:
            return
        folder = os.path.dirname(self.journal_path)
        if folder:
            os.makedirs(folder, exist_ok=True)
        with open(self.journal_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def summary(self, sim):
        out = []
        # ลำดับคงที่ (ตามวันที่ตื่นรู้) — รายชื่อในหน้าอ่านจะไม่กระโดดสลับที่ระหว่างที่ผู้อ่านกำลังเลือก
        for m in sorted((x for x in self.minds.values() if x.enabled),
                        key=lambda m: (not m.alive, m.joined_day, m.cid)):
            c = sim.cast[m.cid]
            out.append({
                "cid": m.cid, "name": m.name, "alive": m.alive, "realm": c.realm_name(),
                "race": c.race(), "age": c.age(sim.day), "gender": c.gender,
                "place": P.place_label(sim, c.place), "world": P.world_name(sim, c),
                "emotion": m.emotion, "short_goal": m.short_goal, "long_goal": m.long_goal,
                "thought": m.last_thought, "plan": m.plan, "thinks": m.n_thinks,
                "plan_steps": m.n_plan_steps, "instinct": m.n_instinct, "error": m.last_error,
                "death_cause": m.death_cause, "origin_note": m.origin_note,
                "org": P.org_name(sim, c), "archetype": c.archetype,
            })
        return out

    def profile(self, sim, cid):
        m = self.minds.get(cid)
        if m is None:
            return None
        c = sim.cast[cid]
        mind_names = {k: v.name for k, v in self.minds.items()}
        return {
            "cid": cid, "name": m.name, "alive": m.alive, "sheet": P.self_sheet(sim, c),
            "ties": P.ties(sim, c, m.impressions, limit=12), "identity": P.short_identity(sim, c),
            "long_goal": m.long_goal, "short_goal": m.short_goal, "emotion": m.emotion,
            "thought": m.last_thought, "plan": m.plan, "memories": m.memories[::-1],
            "impressions": [{"cid": k, "name": sim.cast[k].name, "feeling": v, "is_mind": k in mind_names}
                            for k, v in m.impressions.items() if 0 <= k < len(sim.cast)],
            "origin_note": m.origin_note, "death_cause": m.death_cause, "joined_year": m.joined_day // 365,
            "place": P.place_label(sim, c.place), "thinks": m.n_thinks, "error": m.last_error,
            "scars": PR.scar_lines(sim, getattr(m, "scars", [])),
        }


def _world_order(sim):
    """โลกมนุษย์ก่อน แล้วโลกมนุษย์พี่น้อง แล้วโลกอื่นๆ — รวมผู้มีจิตใจไว้ใกล้กันให้ได้พบกัน"""
    first = [0] if sim.worlds else []
    mortal = [w.wid for w in sim.worlds if w.wid != 0 and w.kind == "mortal" and w.tier == 0]
    rest = [w.wid for w in sim.worlds if w.wid not in first and w.wid not in mortal and w.kind != "chaos"]
    return first + mortal + rest


def _table():
    from .. import events as E
    return E.EVENT_TABLE


def trim_journal(path, max_seq):
    """ตัดบันทึกที่ "มาจากอนาคต" ทิ้ง — กรณีโปรแกรมหยุดกะทันหันหลังเขียนบันทึกแต่ก่อนเซฟโลก

    โลกที่โหลดกลับมาจะเดินจากจุดเซฟล่าสุด ถ้าไม่ตัด บันทึกชีวิตจะมีเหตุการณ์ที่โลกจริงไม่เคยเกิด
    """
    if not path or not os.path.exists(path):
        return 0
    kept, dropped = [], 0
    with open(path, encoding="utf-8") as f:
        for line in f:
            try:
                if json.loads(line).get("seq", 0) > max_seq:
                    dropped += 1
                    continue
            except json.JSONDecodeError:
                dropped += 1
                continue
            kept.append(line)
    if dropped:
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.writelines(kept)
        os.replace(tmp, path)
    return dropped
