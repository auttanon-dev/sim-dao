# -*- coding: utf-8 -*-
"""สร้างพรอมต์ตัดสินใจ และแกะคำตอบกลับเป็นแผนที่เอนจินทำได้จริง

รูปแบบคำตอบใช้คีย์ภาษาอังกฤษ (thought/plan/...) แต่เนื้อหาเป็นไทย — โมเดล 4B เขียน JSON คีย์ไทย
พังบ่อยกว่ามาก ส่วนการอ้างถึงคนและสถานที่ใช้รหัสสั้น (P1, D2) แทนชื่อ เพราะในโลกมีชื่อซ้ำกันจริง
(เจ้าเมืองหลายเมืองชื่อเดียวกัน) และโมเดลสะกดชื่อไทย-จีนผิดบ่อย รหัสจึงจับคู่ได้แน่นอนกว่า
"""
import re
from dataclasses import dataclass
from typing import List, Optional

from . import actions as A
from . import config as MC
from . import persona as P
from .. import elements as _EL
from .. import places as PL
from .. import rules as R
from .. import travel as TR

EMOTIONS = ["สงบ", "ยินดี", "คาดหวัง", "ทะเยอทะยาน", "โกรธแค้น", "เศร้า", "หวาดกลัว",
            "ประหลาดใจ", "รังเกียจ", "สับสน", "เหนื่อยล้า", "ลังเล"]

WORLD_RULES = (
    "- วิถีสวรรค์คือกฎของทุกสิ่ง ทุกอย่างมีวันเสื่อม และวนกลับเริ่มใหม่เป็นวัฏจักร\n"
    "- ทุกคนมีวิถีของตัวเอง ชาวบ้านธรรมดาก็อาจตรัสรู้วิถีของตนแล้วมีพลังขึ้นมาได้\n"
    "- ขั้นพลังไต่ขึ้นด้วยการสะสม การทะลวงขั้นแต่ละครั้งเสี่ยง และต้องผ่านจิตมาร (เรื่องที่ค้างคาใจ)\n"
    "- การฆ่ามีราคา: จิตมารหนักขึ้น และญาติหรือสำนักของผู้ตายจะตามล้างแค้น\n"
    "- สมบัติฟ้าดินมีจำกัด ผู้คนแย่งชิงกัน ทุกสำนักมีไส้ศึกแฝงอยู่\n"
    "- มนุษย์มารเป็นที่รังเกียจของมนุษย์ทั้งปวง เผ่าโกลาหลคือศัตรูร่วมของทุกเผ่า\n"
    "- โลกระดับสูงพลังบริสุทธิ์กว่า เลื่อนขั้นง่ายกว่า แต่อันตรายกว่า"
)

SYSTEM = (
    "คุณคือจิตใจภายในของตัวละครหนึ่งคนในโลกนิยายกำลังภายใน \"วิถีสวรรค์\" "
    "หน้าที่ของคุณคือคิดและตัดสินใจแทนเขา ในมุมมองบุคคลที่หนึ่ง (ใช้คำว่า \"ข้า\") "
    "ตามนิสัย ความทรงจำ ความสัมพันธ์ และสถานการณ์ตรงหน้าของเขาเท่านั้น "
    "เขาไม่รู้ว่าตัวเองอยู่ในนิยาย เขาอาจกลัว โลภ ใจอ่อน หยิ่ง ผิดพลาด หรือเลือกทางที่พาไปสู่ความตายได้ "
    "อย่าทำให้เขาเป็นคนดีหรือฉลาดเกินนิสัยจริง "
    "เลือกการกระทำได้เฉพาะจากรายการที่ให้มา ตอบเป็น JSON ก้อนเดียว เนื้อหาภาษาไทยทั้งหมด"
)


@dataclass
class Step:
    kind: str
    target_cid: Optional[int] = None
    target_name: str = ""
    place: Optional[int] = None
    why: str = ""

    def to_dict(self):
        return {"kind": self.kind, "target_cid": self.target_cid, "target_name": self.target_name,
                "place": self.place, "why": self.why}

    @classmethod
    def from_dict(cls, d):
        return cls(kind=d.get("kind", ""), target_cid=d.get("target_cid"),
                   target_name=d.get("target_name", ""), place=d.get("place"), why=d.get("why", ""))


@dataclass
class Context:
    """ทุกอย่างที่แสดงให้โมเดลเห็นในการคิดครั้งหนึ่ง — เก็บไว้ตรวจคำตอบด้วยรหัสชุดเดียวกัน"""
    menu: List[str]
    people: list                      # [(code, Character)]
    destinations: list                # [(code, place_idx, days)]
    ask_long_goal: bool
    user: str = ""
    scars: list = None                # บาดแผลที่แสดงในพรอมต์ครั้งนี้ (ใช้ตรวจเป้าหมายตอนแยกคำตอบ)
    system: str = SYSTEM


def rumor_label(sim, lead):
    kind, subject = lead.get("kind", ""), lead.get("subject")
    try:
        if kind == "ชิ้นส่วนวิชา":
            frag = next(f for f in sim.skill_fragments if f["fid"] == subject)
            return f"เศษจารึกวิชา「{frag['skill']}」อาจอยู่แถว{PL.PLACES[frag['place']][0]}"
        if kind == "สมบัติ":
            return f"สมบัติ「{sim.items[subject].name}」ปรากฏร่องรอย"
        if kind in ("อุดมสมบูรณ์", "ขาดแคลน"):
            return f"{PL.PLACES[subject][0]} {kind}"
    except (StopIteration, KeyError, IndexError, TypeError, AttributeError):
        pass
    return f"{kind}: {subject}"


def facing_minds(sim, me, limit=4):
    """ผู้มีจิตใจคนอื่นที่ยืนอยู่ที่เดียวกับเราเดี๋ยวนี้ — คนกลุ่มนี้คือที่มาของฉากสนทนา"""
    mm = getattr(sim, "mind", None)
    if mm is None:
        return []
    out = []
    for m in mm.minds.values():
        if not m.alive or m.cid == me.cid:
            continue
        c = sim.cast[m.cid]
        if c.alive and c.world_id == me.world_id and c.place == me.place and c.travel_dest < 0:
            out.append(c)
    out.sort(key=lambda c: c.cid)
    return out[:limit]


def scar_lines(sim, scars):
    """บาดแผลเป็นคำพูด พร้อมสภาพปัจจุบันของผู้ก่อ (ยังอยู่/ตายแล้ว/แข็งแกร่งแค่ไหน)"""
    out = []
    for s in scars:
        cid = s.get("cid")
        who = sim.cast[cid] if isinstance(cid, int) and 0 <= cid < len(sim.cast) else None
        what = {"รอดตายด้วยชะตา": "จู่โจมข้า ข้ารอดมาได้เพราะชะตา",
                "ถูกครอบงำ": "ครอบงำข้า เลือดมารฝังอยู่ในตัวข้า",
                "คุมขัง": "จับข้าไปคุมขัง ข้านับวันอยู่ในนั้นจนพ้นโทษ",
                "หักหลัง": "หักหลังข้าทั้งที่ข้าไว้ใจเขา",
                "ถูกเกณฑ์": "มาเอาตัวข้าขึ้นฟ้าไปโดยไม่บอกว่าเพื่ออะไร",
                }.get(s.get("outcome"), "ทำกับข้าไว้")
        times = s.get("times", 1)
        line = f"{s.get('name', '?')}: ปีที่ {s.get('year')} มัน{what}" + (f" (โดนมาแล้ว {times} ครั้ง)" if times > 1 else "")
        if who is not None:
            line += f" — ตอนนี้{'ยังมีชีวิต ขั้น' + who.realm_name() if who.alive else 'มันตายไปแล้ว'}"
        out.append(line)
    return out


def pick_people(sim, me, others, limit):
    """คนรอบตัวที่น่าจะสำคัญก่อน: คนที่มีเรื่องกัน > ร่วมสำนัก/ตระกูล > ขั้นพลังใกล้กัน"""
    minds = getattr(getattr(sim, "mind", None), "minds", {})

    def score(c):
        s = 0.0
        if c.cid in minds and minds[c.cid].alive:
            s += 10000        # ผู้มีจิตใจด้วยกันต้องเห็นกันก่อนเสมอ ไม่งั้นไม่มีวันเลือกทำอะไรต่อกัน
        if c.cid in me.rivals:
            s += 50 + me.rivals[c.cid]
        if c.cid in me.bonds:
            s += 40 + me.bonds[c.cid]
        if c.cid in (me.master_cid, me.spouse) or c.cid in me.disciples:
            s += 60
        if me.org is not None and me.org == c.org:
            s += 15
        if me.clan >= 0 and me.clan == c.clan:
            s += 10
        if c.place == me.place:
            s += 10
        s -= abs(c.realm - me.realm) * 1.5
        age = c.age(sim.day)
        if age < 16:
            s -= 25 if age >= 8 else 60      # เด็กเล็กไม่ใช่คู่กรณีตามธรรมชาติของผู้ใหญ่
        if not getattr(c, "sentient", True):
            s -= 30
        return (-s, c.cid)
    return sorted(others, key=score)[:limit]


def pick_destinations(sim, me, limit):
    if me.place is None or me.place < 0:
        return []
    try:
        key = sim.world(me.world_id).place_key
    except (IndexError, AttributeError):
        return []
    options = [p for p in PL.places_in(key) if p != me.place]
    if not options:
        return []
    dist = TR.distances_from(me.place)
    wanted = set()
    for m in getattr(me, "wants", ()):
        try:
            from .. import materials as MAT
            wanted |= set(MAT.sources_in_world(m, key))
        except Exception:
            pass
    rumored = {l.get("subject") for l in getattr(me, "rumor_leads", ()) if l.get("kind") == "อุดมสมบูรณ์"}
    mind_at = {}
    for m in getattr(getattr(sim, "mind", None), "minds", {}).values():
        c = sim.cast[m.cid]
        if m.alive and c.cid != me.cid and c.alive and c.world_id == me.world_id and c.place in options:
            mind_at.setdefault(c.place, []).append(c.name)
    ranked = sorted((p for p in options if dist.get(p) is not None),
                    key=lambda p: (0 if p in mind_at else 1 if (p in wanted or p in rumored) else 2, dist[p], p))
    # ที่ที่มีผู้มีจิตใจอยู่ได้ไม่เกินครึ่งรายการ — ที่เหลือยังต้องเป็นแหล่งวัตถุดิบ/ที่ใกล้ ไม่งั้นตัวละคร
    # ที่กำลังขาดของจะมองไม่เห็นทางไปหาเลย (เจอจริงในพรอมต์รอบทดสอบ: ทั้ง 6 ช่องเป็นที่อยู่ของคนอื่น)
    max_mind = max(1, (limit + 1) // 2)
    with_minds = [p for p in ranked if p in mind_at][:max_mind]
    others = [p for p in ranked if p not in mind_at]
    ranked = with_minds + others
    out = []
    for p in ranked[:limit]:
        days = TR.shortest_path_days(me.place, p, me.realm)
        if days is None:
            continue
        note = []
        if p in wanted:
            note.append("มีวัตถุดิบที่ข้ากำลังขาด")
        if p in rumored:
            note.append("ได้ยินข่าวลือว่าอุดมสมบูรณ์")
        if p in mind_at:
            note.append("มี " + ", ".join(mind_at[p]) + " อยู่ที่นั่น")
        out.append((p, days, note))
    return out


def build(sim, mind, me, weights, others, table, ask_long_goal, interrupted_plan=None):
    menu = A.build_menu(weights, table, MC.MENU_MAX_ACTIONS)
    scars = getattr(mind, "scars", None) or []
    here = facing_minds(sim, me)
    if here:
        # มีคนที่เราสนใจอยู่ตรงหน้า — ทางเลือกที่ทำต่อกันได้ต้องอยู่ในเมนู ไม่งั้นได้แต่เดินผ่านกันไป
        for k in MC.SOCIAL_KINDS:
            if k not in menu and weights.get(k, 0) > 0:
                menu.append(k)
    if scars:
        # คนมีบาดแผลต้องเห็นทางตอบโต้ที่ทำได้จริงในเมนู ไม่งั้นความแค้นมีแต่ในคำพูด (เพิ่มเฉพาะที่เอนจินอนุญาต)
        for k in MC.SCAR_RESPONSES:
            if k not in menu and weights.get(k, 0) > 0:
                menu.append(k)
    people = [(f"P{i+1}", c) for i, c in enumerate(pick_people(sim, me, others, MC.PEOPLE_MAX))]
    dests = [(f"D{i+1}", p, days, note)
             for i, (p, days, note) in enumerate(pick_destinations(sim, me, MC.DESTINATIONS_MAX))]
    L = []
    L.append("[กฎของโลกที่ทุกคนรู้]")
    L.append(WORLD_RULES)
    L.append("\n[ตัวข้า]")
    for k, v in P.self_sheet(sim, me).items():
        L.append(f"- {k}: {v}")
    if mind.origin_note:
        L.append(f"- ที่มา: {mind.origin_note}")
    L.append("\n[เป้าหมายชีวิตของข้า]")
    L.append(mind.long_goal or "(ยังไม่เคยตั้ง)")
    if mind.short_goal:
        L.append(f"[สิ่งที่ข้าตั้งใจทำช่วงนี้] {mind.short_goal}")
    if mind.emotion:
        L.append(f"[อารมณ์ครั้งก่อน] {mind.emotion}")
    L.append("\n[ตอนนี้]")
    L.append(f"- ปีที่ {sim.day // 365} วันที่ {sim.day % 365}")
    L.append(f"- อยู่ที่ {P.place_label(sim, me.place)}")
    L.append(f"- โลก: {P.era_words(sim, me)}")
    tie_lines = P.ties(sim, me, mind.impressions)
    if tie_lines:
        L.append("\n[คนสำคัญในชีวิตข้า]")
        L += [f"- {t}" for t in tie_lines]
    if here:
        L.append("\n[คนที่ยืนอยู่ตรงหน้าข้าเดี๋ยวนี้]")
        for c in here:
            L.append(f"- {c.name} ({P.address_form(me, c)}) — {P.relation_to(me, c, sim, mind.impressions)}")
        L.append("- อยู่ที่เดียวกับข้า ข้าทำอะไรกับเขาได้ทันทีโดยไม่ต้องเดินทาง "
                 "(ให้สัญญา ถ่ายทอดวิชา ประลอง สะสางเรื่องเก่า ทำนายชะตา) หรือจะไม่ทำก็ได้")
    if scars:
        L.append("\n[บาดแผลที่ข้าไม่มีวันลืม]")
        L += [f"- {t}" for t in scar_lines(sim, scars)]
        # ผู้ก่อบาดแผลไม่ได้เป็นมารเสมอไปแล้ว (คนที่จับเราไปขังก็เป็นคนธรรมดาในโลกเดียวกัน)
        # ถ้าเขายืนอยู่ตรงหน้าหรืออยู่ในโลกเดียวกัน การล้างแค้นเป็นทางที่ "ทำได้จริง" และต้องบอก
        # ให้ตรง ไม่งั้นพรอมต์จะโกหกตัวละครว่าตามไปไม่ได้ แล้วความแค้นก็ค้างอยู่อย่างนั้นตลอดกาล
        slot = {c.cid: lb for lb, c in people}
        ways = [k for k in MC.SCAR_RESPONSES if k in menu]
        near = [s for s in scars if s.get("cid") in slot]
        same_world = [s for s in scars
                      if s.get("cid") not in slot and isinstance(s.get("cid"), int)
                      and 0 <= s["cid"] < len(sim.cast) and sim.cast[s["cid"]].alive
                      and sim.cast[s["cid"]].world_id == me.world_id]
        far = [s for s in scars if s not in near and s not in same_world]
        for s in near:
            L.append(f"- {s.get('name', '?')} ยืนอยู่ตรงหน้าข้าเดี๋ยวนี้ ({slot[s['cid']]}) "
                     "ข้าเลือกเขาเป็นเป้าล้างแค้น/ประลองได้ทันที หรือจะปล่อยไปก็ได้")
        for s in same_world:
            L.append(f"- {s.get('name', '?')} ยังอยู่ในโลกเดียวกับข้า ข้าเดินทางไปหาเขาได้ถ้าข้าเลือก")
        if far:
            L.append("- " + " / ".join(s.get("name", "?") for s in far)
                     + " อยู่พ้นมือข้าไปตอนนี้ ไม่อยู่ในรายการ P ข้าจึงเลือกเป็นเป้าไม่ได้"
                     + (f" สิ่งที่ข้าทำได้คือ {' / '.join(ways)}" if ways else ""))
        # สองบรรทัดนี้ต้องมีเสมอ ไม่ว่าผู้ก่อจะอยู่ใกล้หรือไกล: บรรทัดแรกคืออิสระในการเลือก
        # (ตัวละครไม่ถูกบังคับให้ล้างแค้น) บรรทัดที่สองกันการเอาแค้นไปลงกับคนที่ไม่เกี่ยว
        # ซึ่งวัดจริงแล้วเกิด 7/7 ครั้งก่อนจะมีบรรทัดนี้
        L.append("- จะให้เรื่องนี้เปลี่ยนชีวิตข้าหรือไม่ ข้าเป็นคนเลือกเอง")
        L.append("- อย่าเอาความแค้นนี้ไปลงกับคนอื่นที่ไม่ได้ก่อเรื่องกับข้า")
    _vis = [v for v in (getattr(me, "visions", None) or [])
            if sim.day - v.get("day", 0) <= MC.VISION_VALID_DAYS]
    if _vis:
        v = _vis[-1]
        L.append("\n[นิมิตที่ข้าเห็นจากวิถีหยั่งรู้]")
        L.append(f"- เมื่อ {(sim.day - v['day']) // 30} เดือนก่อน ข้าจ่ายชะตาไปหนึ่งแต้ม "
                 f"แล้วเห็นสิ่งเหล่านี้ (ยังไม่เกิด):")
        L += [f"  · {t}" for t in v.get("lines", [])]
        L.append("- นี่คือสิ่งที่ **จะเกิดขึ้นจริงถ้าข้าไม่ทำอะไรต่างจากเดิม** — จะฝืนมันหรือปล่อยไป "
                 "ข้าเป็นคนเลือกเอง และการฝืนวิถีสวรรค์ก็มีราคาของมัน")
    if mind.inbox:
        L.append("\n[เรื่องที่เพิ่งเกิดกับข้า ตั้งแต่คิดครั้งก่อน]")
        L += [f"- {t}" for t in mind.inbox[-MC.INBOX_CAP:]]
    if mind.memories:
        L.append("\n[สิ่งที่ข้าทำมาไม่นานนี้]")
        L += [f"- {t}" for t in mind.memories[-MC.MEMORY_IN_PROMPT:]]
    leads = [rumor_label(sim, l) for l in getattr(me, "rumor_leads", ())[:4]]
    if leads:
        L.append("\n[ข่าวลือที่ข้าได้ยินมา]")
        L += [f"- {t}" for t in leads]
    if interrupted_plan:
        L.append("\n[แผนเดิมที่ถูกขัดจังหวะ]")
        L += [f"- {s.kind}{(' กับ ' + s.target_name) if s.target_name else ''}" for s in interrupted_plan]
    L.append("\n[คนที่อยู่แถวนี้ตอนนี้]")
    if people:
        for code, c in people:
            # "พกของมีค่าติดตัว" ใช้กฎเดียวกับที่เอนจินใช้ตัดสินการชิงสมบัติ (Sim.resolve: ของที่
            # ไม่ใช่ยาวิเศษ) เพราะเดิมด่านกรองใน IN.weigh() ถามแค่ว่า "แถวนี้มีใครมีของให้ชิงไหม"
            # แต่ตัวละครเป็นคนระบุชื่อเป้าเอง จึงเล็งคนที่ไม่มีอะไรติดตัวซ้ำๆ แล้วทิ้งเทิร์นไปเปล่าๆ
            # (วัดจริงปีที่ 104-118: ตงฟางเฟินชิงสมบัติ 6 ครั้ง จบด้วย "ไม่มีของ" ทั้ง 6 ครั้ง)
            # การบอกไว้ตรงนี้ไม่ได้บังคับให้ใครชิง แค่ให้เห็นสิ่งที่คนยืนตรงหน้าก็เห็นได้ด้วยตา
            _rich = any(sim.items[i].kind != "ยาวิเศษ" for i in c.items if i in sim.items)
            # ธาตุของคนตรงหน้า — เห็นได้จากปราณที่แผ่ออกมา และเป็นข้อมูลที่เปลี่ยนการตัดสินใจ
            # ว่าจะปะทะหรือจะเลี่ยง (ดู elements.clash_edge — น้ำดับไฟ ไม่ใช่ไฟดับน้ำ)
            _mine, _his = _EL.ensure(me), _EL.ensure(c)
            _ed = _EL.clash_edge(_mine, _his)
            _eword = (f" · ธาตุ{_his}"
                      + (" (ข้าข่มเขา)" if _ed > 0.5 else
                         " (เขาข่มข้า)" if _ed < -0.5 else ""))
            L.append(f"- {code}: {P.short_identity(sim, c)} — {P.relation_to(me, c, sim, mind.impressions)}"
                     f" · เรียกเขาว่า {P.address_form(me, c)}"
                     + _eword
                     + (" · พกของมีค่าติดตัว" if _rich else " · ไม่มีอะไรมีค่าติดตัว"))
    else:
        L.append("- (ไม่มีใครอยู่ใกล้)")
    if "เดินทาง" in menu and dests:
        L.append("\n[ที่ที่เดินทางไปได้]")
        for code, p, days, note in dests:
            extra = (" — " + ", ".join(note)) if note else ""
            L.append(f"- {code}: {P.place_label(sim, p)} ราว {days} วัน{extra}")
    L.append("\n[สิ่งที่ข้าทำได้ตอนนี้]")
    oath = R.oath_form(me)
    for k in menu:
        tgt = " [ต้องระบุคนจากรายการ P]" if A.needs_target(k, table) else ""
        extra = f" (สายของข้าสาบานว่า: {oath})" if k == "ให้สัญญา" else ""
        L.append(f"- {k}: {A.ACTION_INFO.get(k, '')}{tgt}{extra}")
    L.append("\n[วิธีตอบ]")
    L.append(
        "ตอบ JSON ก้อนเดียวตามโครงนี้:\n"
        "{\n"
        '  "thought": "ความคิดในใจของข้าตอนนี้ 2-4 ประโยค บอกว่าข้ารู้สึกและชั่งใจอะไร",\n'
        f'  "emotion": "เลือกหนึ่งคำ: {"/".join(EMOTIONS)}",\n'
        '  "short_goal": "สิ่งที่ข้าตั้งใจทำให้ได้ในช่วงนี้ 1 ประโยค",\n'
        + ('  "long_goal": "เป้าหมายชีวิตระยะยาวของข้า 1 ประโยค ที่มาจากนิสัยและชีวิตที่ผ่านมา",\n'
           if ask_long_goal else '  "long_goal": "",\n')
        + '  "plan": [\n'
          '    {"action": "ชื่อการกระทำจากรายการ", "target": "รหัส P ถ้าต้องมีคน ไม่งั้นว่าง", '
          '"place": "รหัส D ถ้าเดินทาง ไม่งั้นว่าง", "why": "เหตุผลสั้นๆ ในใจข้า"}\n'
          "  ],\n"
          '  "feelings": [{"person": "รหัส P", "feeling": "ความรู้สึกต่อคนนี้สั้นๆ"}]\n'
          "}\n"
        f"กติกา: plan มี 1-{MC.PLAN_MAX_STEPS} ขั้นเรียงตามลำดับที่จะทำ ขั้นแรกต้องมาจาก [สิ่งที่ข้าทำได้ตอนนี้] "
        "ชื่อ action ต้องสะกดตรงตามรายการ ขั้นถัดไปเป็นสิ่งที่ตั้งใจทำต่อ "
        "feelings ใส่เฉพาะคนที่ข้ามีความรู้สึกด้วยจริง ถ้าไม่มีให้เป็น []"
    )
    ctx = Context(menu=menu, people=people, destinations=[(c, p, d) for c, p, d, _ in dests],
                  ask_long_goal=ask_long_goal, scars=list(scars))
    ctx.user = "\n".join(L)
    return ctx


_CODE_RE = re.compile(r"([PD])\s*(\d+)", re.I)


def _resolve_person(text, ctx, sim):
    if not text:
        return None
    t = str(text).strip()
    m = _CODE_RE.search(t)
    if m and m.group(1).upper() == "P":
        idx = int(m.group(2)) - 1
        if 0 <= idx < len(ctx.people):
            return ctx.people[idx][1]
    for _, c in ctx.people:
        if c.name and c.name in t:
            return c
    return None


def _resolve_place(text, ctx):
    if not text:
        return None
    t = str(text).strip()
    m = _CODE_RE.search(t)
    if m and m.group(1).upper() == "D":
        idx = int(m.group(2)) - 1
        if 0 <= idx < len(ctx.destinations):
            return ctx.destinations[idx][1]
    for _, p, _d in ctx.destinations:
        if PL.PLACES[p][0] in t:
            return p
    return None


def _names_someone_else(why, thought, person, ctx, sim, scar_names):
    """เหตุผล/ความคิดเอ่ยชื่อคนอื่น (คนในรายการหรือผู้ก่อบาดแผล) แต่ไม่เอ่ยชื่อเป้าหมายเลย"""
    text = f"{why or ''} {thought or ''}"
    if not text.strip() or (person.name and person.name in text):
        return False
    others = [c.name for _, c in ctx.people if c.cid != person.cid] + list(scar_names)
    return any(n and n != person.name and n in text for n in others)


def parse(data, ctx, sim, table):
    """คำตอบดิบ (dict) -> (ข้อมูลความคิด dict, [Step]) — ทิ้งขั้นที่ทำไม่ได้ ไม่เดาแทน

    ขั้นแรกต้องอยู่ในเมนูตอนนี้ ขั้นถัดไปต้องเป็นการกระทำที่เอนจินรู้จัก (จะตรวจซ้ำอีกครั้งตอนถึงคิว)
    """
    if not isinstance(data, dict):
        return None, []
    def s(key, limit=600):
        v = data.get(key, "")
        return str(v).strip()[:limit] if v is not None else ""
    info = {
        "thought": s("thought"),
        "emotion": s("emotion", 20),
        "short_goal": s("short_goal", 200),
        "long_goal": s("long_goal", 240),
    }
    if info["emotion"] not in EMOTIONS:
        info["emotion"] = next((e for e in EMOTIONS if e in info["emotion"]), "")
    known = [e["kind"] for e in table if e["kind"] in A.ACTION_INFO]
    scar_names = [s.get("name", "") for s in (ctx.scars or [])]
    steps = []
    raw = data.get("plan") or []
    if isinstance(raw, dict):
        raw = [raw]
    for i, item in enumerate(raw if isinstance(raw, list) else []):
        if not isinstance(item, dict):
            continue
        kind = A.normalize_kind(item.get("action", ""), ctx.menu if not steps else known)
        if kind is None:
            if not steps:
                continue          # ขั้นแรกทำไม่ได้ ลองขั้นถัดไปเป็นขั้นแรกแทน
            break
        step = Step(kind=kind, why=str(item.get("why", "") or "").strip()[:240])
        if A.needs_target(kind, table):
            person = _resolve_person(item.get("target", ""), ctx, sim)
            if person is None:
                if not steps:
                    continue
                break
            if (kind in MC.HUMAN_TARGET_KINDS and getattr(person, "is_beast", False)
                    and not getattr(person, "has_human_form", False)):
                if not steps:
                    continue      # สัตว์อสูรไม่มีร่างคนรับการกระทำแบบคนไม่ได้
                break
            if kind in MC.HOSTILE_TARGET_KINDS and _names_someone_else(
                    item.get("why", ""), data.get("thought", "") if not steps else "", person, ctx, sim, scar_names):
                if not steps:
                    continue      # ตั้งใจแค้นคนหนึ่ง แต่รหัสชี้อีกคน — ไม่ให้เอนจินทำร้ายคนผิดตัว
                break
            step.target_cid, step.target_name = person.cid, person.name
        if kind == "เดินทาง":
            step.place = _resolve_place(item.get("place", ""), ctx)
        steps.append(step)
        if len(steps) >= MC.PLAN_MAX_STEPS:
            break
    feelings = {}
    for f in data.get("feelings") or []:
        if isinstance(f, dict):
            person = _resolve_person(f.get("person", ""), ctx, sim)
            text = str(f.get("feeling", "") or "").strip()[:120]
            if person is not None and text:
                feelings[person.cid] = text
    info["feelings"] = feelings
    return info, steps
