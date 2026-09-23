# -*- coding: utf-8 -*-
"""บาดแผลในใจ — รอดจากมารแล้วต้องจำมารตัวนั้นได้ และเห็นทางตอบโต้ที่ทำได้จริง

    python -m unittest test_minds_scar -v
"""
import pickle
import shutil
import tempfile
import unittest

from tiandao import events as E
from tiandao import intent as IN
from tiandao.models import Event
from tiandao.mind import backend as B
from tiandao.mind import config as MC
from tiandao.mind import prompt as PR
from tiandao.mind import storyteller as ST
from tiandao.mind.runner import RunConfig, open_world


def raid(sim, seq, actor, target, outcome="รอดตายด้วยชะตา", day=None):
    return Event(seq=seq, day=sim.day if day is None else day, gap_days=0, world_id=0, era=1, kind="มารบุก",
                 actor=actor, target=target, tags=["ทำลาย", "เลือด"], outcome=outcome, text="มารจู่โจม")


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.sim = open_world(RunConfig(out_dir=self.tmp, seed=3, capacity=10, story=False), B.MockThinker())
        self.mm = self.sim.mind
        self.mind = self.mm.active()[0]
        self.me = self.sim.cast[self.mind.cid]
        self.mara = [c for c in self.sim.living() if c.cid not in self.mm.minds][:2]

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def ctx(self):
        others = [c for c in self.sim.living()
                  if c.world_id == self.me.world_id and c.cid != self.me.cid and c.age(self.sim.day) >= 16][:10]
        w = IN.weigh(self.me, self.sim, E.EVENT_TABLE, True, others=others)
        w["ฝึกวิชา"] = max(w.get("ฝึกวิชา", 0), 1.0)
        return PR.build(self.sim, self.mind, self.me, w, others, E.EVENT_TABLE, False), others


class TestScar(Base):
    def test_survivor_remembers_raider(self):
        self.mm.on_event(raid(self.sim, 10**9, self.mara[0].cid, self.me.cid), self.sim)
        self.assertEqual([s["cid"] for s in self.mind.scars], [self.mara[0].cid])
        self.assertTrue(self.mind.goal_stale, "เกือบตายต้องทำให้ทบทวนเป้าหมายชีวิต")
        self.assertTrue(self.mind.interrupted)

    def test_same_raider_counts_not_duplicates(self):
        for i in range(3):
            self.mm.on_event(raid(self.sim, 10**9 + i, self.mara[0].cid, self.me.cid), self.sim)
        self.assertEqual(len(self.mind.scars), 1)
        self.assertEqual(self.mind.scars[0]["times"], 3)

    def test_cap_and_other_outcomes(self):
        pool = [c for c in self.sim.living() if c.cid not in self.mm.minds][:MC.SCAR_CAP + 2]
        for i, c in enumerate(pool):
            self.mm.on_event(raid(self.sim, 10**9 + i, c.cid, self.me.cid), self.sim)
        self.assertEqual(len(self.mind.scars), MC.SCAR_CAP)
        self.assertEqual(self.mind.scars[-1]["cid"], pool[-1].cid)
        self.mm.on_event(raid(self.sim, 10**9 + 50, self.mara[1].cid, self.me.cid, outcome="ถูกสกัดกั้น"), self.sim)
        self.assertNotIn(self.mara[1].cid, [s["cid"] for s in self.mind.scars])

    def test_prompt_shows_scar_and_ways(self):
        self.mm.on_event(raid(self.sim, 10**9, self.mara[0].cid, self.me.cid), self.sim)
        ctx, _ = self.ctx()
        self.assertIn("[บาดแผลที่ข้าไม่มีวันลืม]", ctx.user)
        self.assertIn(self.mara[0].name, ctx.user)
        self.assertIn("ฝึกวิชา", ctx.menu)
        self.assertIn("ข้าเป็นคนเลือกเอง", ctx.user)

    def test_no_scar_no_section(self):
        ctx, _ = self.ctx()
        self.assertNotIn("[บาดแผลที่ข้าไม่มีวันลืม]", ctx.user)

    def test_old_pickle_without_scars(self):
        state = dict(self.mind.__dict__)
        state.pop("scars")
        again = pickle.loads(pickle.dumps(self.mind))
        again.__setstate__(state)
        self.assertEqual(again.scars, [])
        self.assertIsInstance(self.mm.profile(self.sim, self.mind.cid)["scars"], list)


class TestKeepImportantOutcome(Base):
    def test_beating_a_mara_is_always_written(self):
        mara = self.mara[0].cid
        for i in range(3):
            ev = raid(self.sim, 10**9 + i, self.me.cid, mara, outcome="ปราบมารได้")
            ev.tags = ["ต่อสู้", "ความตาย"]
            self.mm.on_event(ev, self.sim)
        import json, os
        path = os.path.join(self.tmp, "journal.jsonl")
        lines = [json.loads(l) for l in open(path, encoding="utf-8")] if os.path.exists(path) else []
        wins = [e for e in lines if e.get("cid") == self.me.cid and e.get("outcome") == "ปราบมารได้"]
        self.assertEqual(len(wins), 3, "ปราบมารได้ต้องไม่ถูกยุบรวมเหมือนการถูกบุกซ้ำๆ")


class TestStoryForThingsThatHappen(Base):
    def test_beating_a_mara_queues_a_story(self):
        ev = raid(self.sim, 10**9, self.me.cid, self.mara[0].cid, outcome="ปราบมารได้")
        ev.tags = ["ต่อสู้", "ความตาย"]
        self.mm.on_event(ev, self.sim)
        queued = [e for e in self.mm.story_queue if e.get("outcome") == "ปราบมารได้"]
        self.assertTrue(queued, "ฉากปราบมารได้ต้องเข้าคิวแต่งเรื่อง")
        _, user = ST.build(self.sim, queued[0])
        self.assertIn("[สิ่งที่เกิดขึ้นกับตัวละคร]", user)
        self.assertIn("ห้ามเล่าเหตุการณ์ที่เกิดหลังจากผลนี้", user)
        self.assertIn("ข้า/เจ้า", user)

    def test_surviving_a_raid_queues_a_story_with_the_raider(self):
        self.mm.on_event(raid(self.sim, 10**9 + 1, self.mara[0].cid, self.me.cid), self.sim)
        queued = [e for e in self.mm.story_queue if e.get("outcome") == "รอดตายด้วยชะตา"]
        self.assertTrue(queued)
        _, user = ST.build(self.sim, queued[0])
        self.assertIn(self.mara[0].name, user)

    def test_ordinary_events_do_not_queue_stories(self):
        ev = raid(self.sim, 10**9 + 2, self.mara[0].cid, self.me.cid, outcome="ถูกสกัดกั้น")
        self.mm.on_event(ev, self.sim)
        self.assertEqual([e for e in self.mm.story_queue if e.get("outcome") == "ถูกสกัดกั้น"], [])


class TestAddressForm(Base):
    def test_polite_default_and_special_cases(self):
        from tiandao.mind import persona as P
        other = next(c for c in self.sim.living() if c.cid != self.me.cid and c.realm <= self.me.realm + 1)
        other.name, other.realm = "หานเจี้ยน", self.me.realm
        self.assertEqual(P.address_form(self.me, other), "สหายหาน")
        self.assertEqual(P.surname("ทาคากิ โทโมเอะ"), "ทาคากิ")
        self.assertEqual(P.surname("เหยาปิง"), "เหยา")
        high = next(c for c in self.sim.living() if c.cid not in (self.me.cid, other.cid))
        high.name, high.realm = "เย่ฟาน", self.me.realm + 3
        self.assertEqual(P.address_form(self.me, high), "ท่านเย่")
        self.me.rivals[other.cid] = 2
        self.assertEqual(P.address_form(self.me, other), "เจ้า")
        self.me.master_cid = high.cid
        self.assertEqual(P.address_form(self.me, high), "อาจารย์")

    def test_prompt_and_story_carry_the_address(self):
        ctx, others = self.ctx()
        self.assertIn("เรียกเขาว่า", ctx.user)
        self.assertTrue(any(w in ctx.user for w in ("สหาย", "ท่าน", "อาจารย์", "เจ้า")))
        self.mm.on_event(raid(self.sim, 10**9, self.mara[0].cid, self.me.cid), self.sim)
        entry = next(e for e in self.mm.story_queue if e.get("outcome") == "รอดตายด้วยชะตา")
        _, user = ST.build(self.sim, entry)
        self.assertIn("[คำเรียกอีกฝ่าย]", user)
        self.assertIn("สหาย+แซ่", user)


class TestStoryVoice(Base):
    def test_prompts_ask_for_third_person_and_no_headings(self):
        ev = raid(self.sim, 10**9, self.me.cid, self.mara[0].cid, outcome="ปราบมารได้")
        self.mm.on_event(ev, self.sim)
        entry = next(e for e in self.mm.story_queue if e.get("outcome") == "ปราบมารได้")
        for _, user in (ST.build(self.sim, entry),):
            self.assertIn("บุคคลที่สาม", user)
            self.assertIn("ห้ามใส่หัวข้อ", user)
            self.assertIn("ข้า/เจ้า", user)

    def test_clean_story_drops_modern_pronouns_and_prompt_labels(self):
        out = ST.clean_story("“ข้าจะช่วยคุณ” เย่ฟานพูด\nผลที่เกิดขึ้นจริง: เย่ฟานชนะ\n"
                             "เขามีคุณธรรม และพระคุณของอาจารย์")
        self.assertIn("ข้าจะช่วยเจ้า", out)
        self.assertNotIn("ผลที่เกิดขึ้นจริง:", out)
        self.assertIn("คุณธรรม", out, "คำว่า คุณธรรม ต้องไม่ถูกแก้")
        self.assertIn("พระคุณ", out, "คำว่า พระคุณ ต้องไม่ถูกแก้")

    def test_clean_story_unwraps_bracketed_paragraphs(self):
        out = ST.clean_story("[เงาทมิฬซานยืนอยู่ใต้ต้นหลิว สายลมพัดผ้าคลุมกายสีครามจนปลิว]\n"
                             "[ฉากที่ 2]\n"
                             "[เขาค้อมกายแล้วกล่าวว่า \"ข้าสาบานต่อจิตเต๋า\" ด้วยเสียงเรียบเฉย]")
        self.assertIn("เงาทมิฬซานยืนอยู่ใต้ต้นหลิว", out)
        self.assertIn("ข้าสาบานต่อจิตเต๋า", out)
        self.assertNotIn("[", out)
        self.assertNotIn("ฉากที่ 2", out)

    def test_prompt_forbids_inventing_facts(self):
        ev = raid(self.sim, 10**9 + 7, self.me.cid, self.mara[0].cid, outcome="ปราบมารได้")
        self.mm.on_event(ev, self.sim)
        entry = next(e for e in self.mm.story_queue if e.get("outcome") == "ปราบมารได้")
        system, user = ST.build(self.sim, entry)
        self.assertIn("เล่าได้เฉพาะสิ่งที่อยู่ในข้อมูล", system)
        self.assertIn("ห้ามเพิ่มสิ่งของหรือเหตุการณ์ที่ไม่มีในข้อมูล", user)

    def test_oath_label_is_about_speech_not_reputation(self):
        ev = raid(self.sim, 10**9 + 11, self.me.cid, self.mara[0].cid, outcome="ปราบมารได้")
        self.mm.on_event(ev, self.sim)
        entry = next(e for e in self.mm.story_queue if e.get("outcome") == "ปราบมารได้")
        _, user = ST.build(self.sim, entry)
        self.assertIn("ถ้อยคำเวลาสาบาน", user)
        self.assertNotIn("คำสาบานของสายเขา", user)
        self.assertIn("ห้ามเขียนถ้อยคำนั้นเป็นคุณสมบัติ", user)
        self.assertIn("ห้ามลอกรายการนิสัย", user)

    def test_clean_story_drops_echoed_instructions(self):
        out = ST.clean_story("ฉากงานชุมนุมยาว 4-7 ย่อหน้า ให้คนในรายชื่อผู้ร่วมงานได้พูด\n"
                             "เย่ฟานยืนอยู่กลางตลาด มองแท่นประมูลด้วยสายตาเย็นชา\n"
                             "ห้ามใช้คำสมัยใหม่ว่า คุณ ผม")
        self.assertIn("เย่ฟานยืนอยู่กลางตลาด", out)
        self.assertNotIn("ฉากงานชุมนุม", out)
        self.assertNotIn("ห้ามใช้คำสมัยใหม่", out)

    def test_prompt_bans_modern_words(self):
        cid = self.mind.cid
        ev = raid(self.sim, 10**9, self.me.cid, self.mara[0].cid, outcome="ปราบมารได้")
        self.mm.on_event(ev, self.sim)
        entry = next(e for e in self.mm.story_queue if e.get("outcome") == "ปราบมารได้")
        _, user = ST.build(self.sim, entry)
        self.assertIn("ห้ามใช้คำสมัยใหม่", user)

    def test_clean_story_removes_model_headings(self):
        out = ST.clean_story("[ฉากสั้น]\nเฉินเจี้ยนเดินเข้าไปในถ้ำ\n[ฉากที่ 2]\nเขาหยิบแร่ขึ้นมา")
        self.assertNotIn("[ฉากสั้น]", out)
        self.assertNotIn("[ฉากที่ 2]", out)
        self.assertIn("เฉินเจี้ยนเดินเข้าไปในถ้ำ", out)
        self.assertIn("เขาหยิบแร่ขึ้นมา", out)


class TestWrongRevengeTarget(Base):
    def test_revenge_naming_raider_but_pointing_at_innocent_is_dropped(self):
        self.mm.on_event(raid(self.sim, 10**9, self.mara[0].cid, self.me.cid), self.sim)
        ctx, _ = self.ctx()
        code, innocent = next((cd, c) for cd, c in ctx.people if c.cid != self.mara[0].cid)
        ctx.menu = list(dict.fromkeys(ctx.menu + ["ล้างแค้น", "บำเพ็ญ"]))
        data = {"thought": f"ข้าจะล้างแค้น{self.mara[0].name}ที่ทำให้ข้าเกือบตาย",
                "plan": [{"action": "ล้างแค้น", "target": code, "why": f"แก้แค้น{self.mara[0].name}"},
                         {"action": "บำเพ็ญ"}]}
        _, steps = PR.parse(data, ctx, self.sim, E.EVENT_TABLE)
        self.assertEqual([s.kind for s in steps], ["บำเพ็ญ"])
        self.assertIn("อย่าเอาความแค้นนี้ไปลงกับคนอื่น", ctx.user)

    def test_revenge_naming_the_target_is_kept(self):
        ctx, _ = self.ctx()
        code, foe = ctx.people[0]
        ctx.menu = list(dict.fromkeys(ctx.menu + ["ล้างแค้น"]))
        data = {"thought": f"{foe.name}ต้องชดใช้", "plan": [{"action": "ล้างแค้น", "target": code, "why": ""}]}
        _, steps = PR.parse(data, ctx, self.sim, E.EVENT_TABLE)
        self.assertEqual([s.target_cid for s in steps], [foe.cid])
        data = {"plan": [{"action": "ล้างแค้น", "target": code, "why": "มันเคยทำร้ายข้า"}]}   # ไม่เอ่ยชื่อใครเลย = เชื่อรหัส
        _, steps = PR.parse(data, ctx, self.sim, E.EVENT_TABLE)
        self.assertEqual([s.target_cid for s in steps], [foe.cid])


class TestBeastTarget(Base):
    def test_teaching_a_beast_is_dropped(self):
        ctx, others = self.ctx()
        code, person = ctx.people[0]
        person.is_beast, person.has_human_form = True, False
        data = {"plan": [{"action": "ถ่ายทอดวิชา", "target": code}, {"action": "บำเพ็ญ"}]}
        ctx.menu = list(dict.fromkeys(ctx.menu + ["ถ่ายทอดวิชา", "บำเพ็ญ"]))
        _, steps = PR.parse(data, ctx, self.sim, E.EVENT_TABLE)
        self.assertEqual([s.kind for s in steps], ["บำเพ็ญ"])
        data = {"plan": [{"action": "ชิงสมบัติ", "target": code}]}
        ctx.menu.append("ชิงสมบัติ")
        _, steps = PR.parse(data, ctx, self.sim, E.EVENT_TABLE)
        self.assertEqual([s.kind for s in steps], ["ชิงสมบัติ"], "ชิงสมบัติจากสัตว์อสูรยังทำได้")


if __name__ == "__main__":
    unittest.main()
