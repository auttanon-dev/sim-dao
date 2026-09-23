# -*- coding: utf-8 -*-
"""เจ็ดอารมณ์ หกปรารถนา — ทุกคนมีครบ ไม่เท่ากัน และเปลี่ยนตามสิ่งที่พบเจอ

โจทย์จากผู้ใช้: "มนุษย์ทุกคนควรมี 7อารมณ์ 6ปราถนา แต่ละค่าจะไม่เหมือนกัน ไม่เท่ากัน
และต่างกัน และปรับเปลี่ยนได้ขึ้นอยู่กับสิ่งที่พบเจอ"

เทสต์ในไฟล์นี้จึงตรวจสี่เรื่องแยกกัน: (1) มีครบ (2) ไม่เท่ากัน (3) ขยับตามเหตุการณ์
(4) ขยับแล้วมีผลต่อการตัดสินใจจริง ไม่ใช่เลขที่โชว์ไว้เฉยๆ
"""
import contextlib
import io
import random
import statistics as st
import unittest

from tiandao.sim import Sim
from tiandao import emotions as EM
from tiandao import intent as IN
from tiandao import events as E
from tiandao.models import Character
from tiandao.mind import persona as P
from tiandao.mind import storyteller as ST


def quiet(fn, *a, **kw):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*a, **kw)


def _sim(seed=5, steps=300):
    s = Sim(seed=seed)
    quiet(s.run, steps)
    return s


# ------------------------------------------------------------------ (1) มีครบ
def _fresh():
    """คนคนหนึ่งที่นิสัยกลางๆ ทุกด้าน — ใช้ดูว่าเหตุการณ์เดียวขยับใจไปทางไหน"""
    ch = Character(cid=1, name="ทดสอบ", world_id=0, dao="วิถีดาบ",
                   dao_tags=["ดาบ"], born_day=0)
    ch.fear = ch.greed = ch.compassion = 0.5
    EM.roll(ch, random.Random(1))
    return ch


class TestEmotions(unittest.TestCase):

    def test_everyone_has_seven_emotions_six_desires(self):
        s = _sim()
        people = [c for c in s.cast if c.sentient]
        assert len(people) > 50
        for c in people:
            assert set(c.emotions) == set(EM.EMOTIONS), c.name
            assert set(c.desires) == set(EM.DESIRES), c.name
            for v in list(c.emotions.values()) + list(c.desires.values()):
                assert 0.0 <= v <= 1.0


# ------------------------------------------------------------------ (2) ไม่เท่ากัน
    def test_values_differ_within_one_person_and_between_people(self):
        s = _sim()
        people = [c for c in s.cast if c.sentient][:80]
        # ในคนเดียวกัน ค่าทั้งเจ็ดต้องไม่เท่ากันหมด (ไม่ใช่ 0.5 เรียงกัน)
        for c in people:
            assert len(set(c.emotions.values())) >= 5, c.emotions
            assert len(set(c.desires.values())) >= 4, c.desires
        # ระหว่างคน ใจต้องไม่ซ้ำกัน
        vecs = {tuple(c.emotions.values()) + tuple(c.desires.values()) for c in people}
        assert len(vecs) == len(people)
        # และกระจายจริง ไม่ใช่กองอยู่ค่าเดียว
        for k in EM.EMOTIONS + EM.DESIRES:
            vals = [(c.emotions if k in EM.EMOTIONS else c.desires)[k] for c in people]
            assert st.pstdev(vals) > 0.08, (k, st.pstdev(vals))


    def test_heart_follows_existing_temperament(self):
        """คนขลาดต้อง 'กลัว' สูงจริง — ใจกับนิสัยต้องไม่ขัดกันเอง"""
        s = _sim(steps=1500)
        people = [c for c in s.cast if c.sentient]
        brave = [c.emotions["กลัว"] for c in people if c.fear < 0.3]
        timid = [c.emotions["กลัว"] for c in people if c.fear > 0.7]
        assert brave and timid
        assert st.mean(timid) > st.mean(brave) + 0.15


    def test_react_moves_the_right_keys(self):
        ch = _fresh()
        before = dict(ch.emotions)
        EM.react(ch, "ทรยศ", "หักหลัง", ["ทรยศ"], day=0, role="target")
        assert ch.emotions["ชิงชัง"] > before["ชิงชัง"]
        assert ch.emotions["โกรธ"] > before["โกรธ"]
        assert ch.emotions["รัก"] < before["รัก"]

        ch2 = _fresh()
        b2 = dict(ch2.emotions), dict(ch2.desires)
        EM.react(ch2, "กำเนิดทายาท", "กำเนิด", ["คน"], day=0)
        assert ch2.emotions["ยินดี"] > b2[0]["ยินดี"]
        assert ch2.emotions["รัก"] > b2[0]["รัก"]
        assert ch2.desires["อยากเป็นที่รัก"] < b2[1]["อยากเป็นที่รัก"]

        ch3 = _fresh()
        b3 = ch3.emotions["กลัว"]
        EM.react(ch3, "มารบุก", "รอดตายด้วยชะตา", ["ทำลาย", "เลือด"], day=0, role="target")
        assert ch3.emotions["กลัว"] > b3 + 0.1


    def test_actor_and_target_feel_differently(self):
        a, t = _fresh(), _fresh()
        t.cid = 2
        EM.react(a, "ชิงสมบัติ", "ปล้นสำเร็จ", ["ชิงทรัพย์"], day=0, role="actor")
        EM.react(t, "ชิงสมบัติ", "ปล้นสำเร็จ", ["ชิงทรัพย์"], day=0, role="target")
        assert a.emotions["ยินดี"] > t.emotions["ยินดี"]
        assert t.emotions["โกรธ"] > a.emotions["โกรธ"]


    def test_nuisance_outcomes_barely_move_the_heart(self):
        ch = _fresh()
        before = ch.emotions["เศร้า"]
        EM.react(ch, "หลอมยา", "ไม่มีเตา", [], day=0)
        assert 0.0 < ch.emotions["เศร้า"] - before <= 0.03


    def test_emotion_calms_back_toward_personal_baseline(self):
        ch = _fresh()
        base = ch.emo_base["โกรธ"]
        for _ in range(4):
            EM.react(ch, "ล้างแค้น", "ล้มเหลว", ["ต่อสู้"], day=0)
        spike = ch.emotions["โกรธ"]
        assert spike > base + 0.1
        EM.decay(ch, 365 * 5)
        assert abs(ch.emotions["โกรธ"] - ch.emo_base["โกรธ"]) < 0.01
        # แต่ "ฐานใจ" ถูกดันไปแล้ว — เขาไม่ใช่คนเดิมเป๊ะๆ อีก
        assert ch.emo_base["โกรธ"] > base


    def test_repeated_experience_reshapes_the_baseline(self):
        ch = _fresh()
        base = ch.emo_base["ชิงชัง"]
        for i in range(20):
            EM.react(ch, "ทรยศ", "หักหลัง", ["ทรยศ"], day=i * 400, role="target")
        assert ch.emo_base["ชิงชัง"] > base + 0.1


    def test_cultivation_settles_the_seven_emotions(self):
        ch = _fresh()
        for _ in range(5):
            EM.react(ch, "ล้างแค้น", "ล้มเหลว", ["ต่อสู้"], day=0)
        hot = ch.emotions["โกรธ"]
        EM.react(ch, "บำเพ็ญ", "บำเพ็ญ", ["อดทน"], day=0)
        assert ch.emotions["โกรธ"] < hot


    def test_desires_move_far_slower_than_emotions(self):
        ch = _fresh()
        EM.react(ch, "ชิงสมบัติ", "พลาดประมูล", [], day=0)
        e_gap = abs(ch.emotions["โกรธ"] - ch.emo_base["โกรธ"])
        d_gap = abs(ch.desires["อยากได้"] - ch.des_base["อยากได้"])
        EM.decay(ch, 400)
        assert abs(ch.emotions["โกรธ"] - ch.emo_base["โกรธ"]) < e_gap * 0.35
        assert abs(ch.desires["อยากได้"] - ch.des_base["อยากได้"]) > d_gap * 0.85


    def test_world_run_actually_reshapes_hearts(self):
        """รันโลกจริง แล้วดูว่า "ฐานใจ" ของประชากรขยับเพราะสิ่งที่เจอ ไม่ใช่นิ่งอยู่กับที่

        วัดโดยถ่ายภาพฐานใจไว้กลางรัน แล้วรันต่อ — ใครเจอเรื่องก็ต้องเปลี่ยน ใครไม่เจอก็ต้องนิ่ง
        (ถ้าวัดแค่ "อารมณ์ตอนนี้ต่างจากฐานใจ" จะได้ตัวเลขต่ำเสมอ เพราะคนที่เพิ่งเจอเรื่องเมื่อ
        หลายสิบปีก่อนอารมณ์สงบกลับไปแล้ว — ซึ่งเป็นเรื่องที่ควรเกิด)
        """
        s = _sim(seed=3, steps=6000)
        snap = {c.cid: dict(c.emo_base) for c in s.cast if c.alive and c.sentient}
        quiet(s.run, 6000)
        watched = [c for c in s.cast if c.cid in snap and c.alive and c.sentient]
        assert len(watched) > 100
        changed = [c for c in watched
                   if any(abs(c.emo_base[k] - snap[c.cid][k]) > 0.005 for k in EM.EMOTIONS)]
        assert len(changed) >= len(watched) * 0.25, (len(changed), len(watched))
        # และฐานใจของประชากรต้องยังกระจาย ไม่ถูกดันไปกองที่ขอบ 0/1
        for k in EM.EMOTIONS:
            vals = [c.emo_base[k] for c in watched]
            pinned = sum(1 for v in vals if v <= 0.001 or v >= 0.999)
            assert pinned < len(vals) * 0.2, (k, pinned, len(vals))
            assert st.pstdev(vals) > 0.08, (k, st.pstdev(vals))


# ------------------------------------------------------------------ (4) มีผลต่อการตัดสินใจ
    def test_desires_bias_intent_weights(self):
        ch = _fresh()
        ch.desires["อยากเป็นใหญ่"] = 1.0
        ch.desires["อยากรู้"] = 0.0
        hi = EM.intent_bias(ch)
        ch.desires["อยากเป็นใหญ่"] = 0.0
        lo = EM.intent_bias(ch)
        assert hi["ประลอง"] > lo.get("ประลอง", 0)
        assert hi["ตั้งสำนัก"] > lo.get("ตั้งสำนัก", 0)


    def test_weigh_reflects_the_heart_but_never_unlocks_the_impossible(self):
        s = _sim(steps=400)
        # ต้องเป็นคนที่ยัง "ไม่เจ็บ" และไม่ขลาด เพราะเลเยอร์อยู่รอด (เดิม) ตัดล้างแค้นทิ้งอยู่แล้ว
        # เมื่อชะตาหมดหรือร่างโรย — นั่นคือพฤติกรรมที่ถูก ไม่ใช่บั๊กที่อารมณ์ควรไปแก้
        ch = next(c for c in s.cast
                  if c.alive and c.sentient and c.realm == 0 and c.org is None
                  and c.fate > 0 and c.decay <= 1.8 and "ขลาดกลัว" not in c.traits)
        others = [c for c in s.cast if c.alive and c.place == ch.place and c.cid != ch.cid][:4]
        ch.emotions["โกรธ"] = 0.0
        ch.desires["อยากเป็นใหญ่"] = 0.0
        calm = IN.weigh(ch, s, E.EVENT_TABLE, bool(others), others=others)
        ch.emotions["โกรธ"] = 1.0
        ch.emotions["ชิงชัง"] = 1.0
        ch.desires["อยากเป็นใหญ่"] = 1.0
        angry = IN.weigh(ch, s, E.EVENT_TABLE, bool(others), others=others)
        if others:
            assert angry.get("ล้างแค้น", 0) > calm.get("ล้างแค้น", 0)
        # ขั้นไม่ถึงก็ตั้งสำนักไม่ได้ ไม่ว่าจะอยากเป็นใหญ่แค่ไหน
        assert "ตั้งสำนัก" not in angry
        assert all(v > 0 for v in angry.values())


# ------------------------------------------------------------------ ความคงที่ของโลก
    def test_react_and_decay_never_touch_the_rng(self):
        s = _sim(steps=200)
        ch = next(c for c in s.cast if c.alive and c.sentient)
        before = s.rng.getstate()
        for i in range(50):
            EM.react(ch, "ล้างแค้น", "สำเร็จ", ["ต่อสู้"], day=s.day + i)
            EM.decay(ch, s.day + i * 100)
        assert s.rng.getstate() == before


    def test_world_stays_deterministic(self):
        a, b = _sim(seed=99, steps=3000), _sim(seed=99, steps=3000)
        assert [e.kind for e in a.log] == [e.kind for e in b.log]
        ha = [(c.name, tuple(c.emotions.values()), tuple(c.desires.values())) for c in a.cast]
        hb = [(c.name, tuple(c.emotions.values()), tuple(c.desires.values())) for c in b.cast]
        assert ha == hb


# ------------------------------------------------------------------ save เก่า
    def test_old_character_without_a_heart_is_filled_in(self):
        ch = Character(cid=41, name="คนเก่า", world_id=0, dao="วิถีดาบ",
                       dao_tags=["ดาบ"], born_day=0)
        ch.emotions, ch.desires, ch.emo_base, ch.des_base = {}, {}, {}, {}
        ch.fear, ch.greed, ch.compassion = 0.8, 0.2, 0.6
        EM.ensure(ch)
        assert set(ch.emotions) == set(EM.EMOTIONS)
        assert set(ch.desires) == set(EM.DESIRES)
        assert ch.emotions["กลัว"] > ch.emotions["อยาก"]      # ตามนิสัยที่เขามีอยู่
        # คนละ cid ต้องได้ใจไม่เหมือนกัน แม้นิสัยจะเหมือนกันเป๊ะ
        other = Character(cid=42, name="คนเก่าสอง", world_id=0, dao="วิถีดาบ",
                          dao_tags=["ดาบ"], born_day=0)
        other.emotions, other.desires = {}, {}
        other.fear, other.greed, other.compassion = 0.8, 0.2, 0.6
        EM.ensure(other)
        assert other.emotions != ch.emotions


# ------------------------------------------------------------------ ถึงตาโมเดลอ่าน
    def test_prompt_and_story_see_the_heart(self):
        s = _sim(steps=1200)
        ch = next(c for c in s.cast if c.alive and c.sentient)
        sheet = P.self_sheet(s, ch)
        assert sheet["อารมณ์ในใจตอนนี้"]
        assert sheet["สิ่งที่ใจข้าปรารถนาที่สุด"]
        assert any(d in sheet["สิ่งที่ใจข้าปรารถนาที่สุด"] for d in EM.DESIRES)
        entry = {"cid": ch.cid, "name": ch.name, "year": s.day // 365, "place": "ที่ใดสักแห่ง",
                 "kind": "บำเพ็ญ", "action": "บำเพ็ญ", "outcome": "สำเร็จ",
             "text": "บำเพ็ญจนสำเร็จ", "why": "อยากทะลวงขั้น", "thought": "สงบใจไว้ก่อน"}
        _sys, prompt = ST.build(s, entry)
        assert "ใจตอนนี้" in prompt and "ใจปรารถนา" in prompt


    def test_stirred_reports_only_what_is_above_the_personal_baseline(self):
        ch = _fresh()
        assert EM.stirred(ch) == []
        for _ in range(4):
            EM.react(ch, "มารบุก", "อันตราย", ["เลือด"], day=0, role="target")
        assert "กลัว" in EM.stirred(ch)
        EM.decay(ch, 365 * 10)
        assert EM.stirred(ch) == []


    def test_words_describe_the_dominant_emotion_not_the_raw_number(self):
        ch = _fresh()
        for k in EM.EMOTIONS:
            ch.emotions[k] = 0.9
            ch.emo_base[k] = 0.9
        ch.emo_day = 0
        # ทุกช่องสูงเท่ากัน = ไม่มีอารมณ์ใดครอบใจเขา ต้องไม่บรรยายว่า "ท่วมท้น"
        assert "ท่วมท้น" not in EM.emotion_words(ch)
        ch.emotions["โกรธ"] = 1.0
        for k in EM.EMOTIONS:
            if k != "โกรธ":
                ch.emotions[k] = 0.42
        assert EM.emotion_words(ch).startswith("โกรธ")
        assert "ท่วมท้น" in EM.emotion_words(ch)


if __name__ == "__main__":
    unittest.main()
