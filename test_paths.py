# -*- coding: utf-8 -*-
"""ตรวจว่าสายบำเพ็ญกาย/จิต และสมบัติสามชิ้นใหม่ มีผลจริง ไม่ใช่แค่ป้ายชื่อ

สิ่งที่วัด — ทุกข้อวัดจากซิมที่เดินจริง ไม่ใช่จากการมีตัวแปรอยู่ในโค้ด:
  1. คนแบ่งเป็นสายจริง และแต่ละแดนเอนไปคนละทางตามที่ตั้งใจ (สยามเน้นกาย ชมพูทวีปเน้นจิต)
  2. สายกายทนกว่า — ความเสื่อมสะสมช้ากว่าเมื่ออายุงานเท่ากัน
  3. สายจิตข้ามขั้นได้ไกลกว่าเมื่อความเข้าใจเท่ากัน
  4. สายสมดุลเป็นสายเดียวที่ลดความแพ้ทางเผ่าโกลาหลได้
  5. สมบัติทั้งสามชิ้นมีอยู่จริงในโลกและออกฤทธิ์ตามที่เขียนไว้
"""
import contextlib
import io
import statistics as st

from tiandao import config as C
from tiandao import paths as PATHS
from tiandao import rules as R
from tiandao import sim as S
from tiandao import treasures as T

# วัดที่อายุโลกคงที่ ไม่ใช่จำนวนเหตุการณ์คงที่ — ความเอนตามแดนสะสมตามปีที่คนฝึกวิชาในแดนนั้น ส่วนจำนวนเหตุการณ์ต่อปี
# เปลี่ยนทุกครั้งที่โลกคึกขึ้นหรือเงียบลง (แก้บั๊กเทิร์นหลังเข้าด่านแล้ว 60,000 เหตุการณ์ถึงแค่ปีที่ 37 จากเดิมปีที่ 45)
YEARS = 45
SEED = 3131


def run():
    sim = S.Sim(seed=SEED, tiers=3)
    with contextlib.redirect_stdout(io.StringIO()):
        while sim.day < YEARS * 365:
            if sim.step() is None:
                break
    return sim


def test_lines_mapped():
    print("\n=== 0. ทุกสายวิชาต้องถูกจัดเป็นกายหรือจิต ไม่มีตกหล่น ===")
    from tiandao.skills import SKILLS
    unmapped = [s[0] for s in SKILLS if PATHS.line_path(s[1]) == "-"]
    assert not unmapped, f"วิชาที่ไม่มีสาย: {unmapped[:5]}"
    body = sum(1 for s in SKILLS if PATHS.line_path(s[1]) == "กาย")
    print(f"  ✓ {len(SKILLS)} วิชา — ทางกาย {body} ทางจิต {len(SKILLS)-body}")


def test_paths_emerge(sim):
    print("\n=== 1. คนต้องแบ่งเป็นสายจริง และแต่ละแดนเอนคนละทาง ===")
    import collections
    alive = [c for c in sim.cast if c.alive]
    dist = collections.Counter(PATHS.path_of(c) for c in alive)
    decided = [c for c in alive if PATHS.path_of(c) != "ยังไม่แน่ชัด"]
    print(f"  ผู้มีชีวิต {len(alive):,} คน: {dict(dist)}")
    assert len(decided) > 50, f"มีคนที่บอกสายได้แค่ {len(decided)} คน — น้อยเกินกว่าจะวัดอะไรได้"
    for name in ("กายบำเพ็ญ", "จิตบำเพ็ญ", "สมดุลกายจิต"):
        assert dist[name] > 0, f"ไม่มีใครเป็น{name}เลย"

    print("  ความเอนของแต่ละแดน (สัดส่วนน้ำหนักทางกายเฉลี่ยของคนในแดนนั้น):")
    rows = []
    for w in sim.worlds:
        ppl = [c for c in decided if c.world_id == w.wid]
        if len(ppl) < 8:
            continue
        avg = st.mean(PATHS.shares(c)[0] for c in ppl)
        rows.append((w.name, w.place_key, avg, len(ppl)))
    for name, key, avg, n in sorted(rows, key=lambda r: -r[2]):
        print(f"    {name:<24} เอนไปทางกาย {avg:.0%} (ตั้งไว้ {PATHS.body_bias(key):.0%}, {n} คน)")
    keyed = {key: avg for _n, key, avg, _c in rows}
    if "siam" in keyed and "bharata" in keyed:
        print(f"    -> สยาม {keyed['siam']:.0%} เทียบ ชมพูทวีป {keyed['bharata']:.0%}")
        assert keyed["siam"] > keyed["bharata"], "สยามควรเอนไปทางกายมากกว่าชมพูทวีป"
    return decided


def _twin(sim, base_skills_body, base_skills_spirit, src):
    """คู่แฝดที่ต่างกันแค่ 'สายวิชา' อย่างเดียว — ทุกอย่างอื่นเหมือนกันเป๊ะ"""
    import copy
    a = copy.deepcopy(src)
    b = copy.deepcopy(src)
    a.skills = list(base_skills_body)
    b.skills = list(base_skills_spirit)
    a.items = b.items = []
    return a, b


def _skill_sets(n=6):
    from tiandao.skills import SKILLS
    body = [s[0] for s in SKILLS if PATHS.line_path(s[1]) == "กาย"][:n]
    spirit = [s[0] for s in SKILLS if PATHS.line_path(s[1]) == "จิต"][:n]
    return body, spirit


def test_body_is_tougher(sim, decided):
    """วัดที่ **ตัวกฎ** ด้วยคู่แฝด ไม่ใช่วัดจากค่าเฉลี่ยของคนทั้งโลก

    เคยเขียนแบบวัดค่าเฉลี่ย `decay / ปีที่มีชีวิต` ของคนจริงแล้วพบว่าเชื่อไม่ได้: ความเสื่อมถูก
    กระทำโดยแรงอื่นอีกหลายทางที่แรงกว่าอายุมาก (แพ้การต่อสู้ ฝึกวิชาพลาด ข้ามขั้นล้มเหลว) และ
    `cultivate()` ก็คอยหักความเสื่อมกลับลงตลอดเวลา ค่าที่วัดได้จึงบอกว่า "ใครใช้ชีวิตโลดโผนกว่า"
    ไม่ได้บอกว่า "ร่างใครทนกว่า" — วัดจริงแล้วสายกายออกมาเสื่อมเร็วกว่าเพราะออกรบมากกว่า
    """
    print("\n=== 2. สายกายต้องทนกว่าจริง (วัดที่กฎด้วยคู่แฝด) ===")
    src = next(c for c in sim.cast if c.alive and c.skills)
    bs, ss = _skill_sets()
    a, b = _twin(sim, bs, ss, src)
    w = sim.world(src.world_id)
    d0 = a.decay
    R.age_and_decay(sim, a, w, 3650, sim.rng)
    R.age_and_decay(sim, b, w, 3650, sim.rng)
    ga, gb = a.decay - d0, b.decay - d0
    print(f"  ผ่านไป 10 ปี — {PATHS.path_of(a)} เสื่อม {ga:.4f} | {PATHS.path_of(b)} เสื่อม {gb:.4f}")
    assert ga < gb, "สายกายไม่ได้ทนกว่าสายจิตในระดับกฎ"
    print(f"  ✓ ร่างสายกายทนกว่า {(1-ga/gb)*100:.0f}%")

    # ค่าจริงจากคนทั้งโลก — รายงานไว้เฉยๆ ไม่ใช่เกณฑ์ผ่าน (ดูเหตุผลใน docstring)
    def rate(c):
        yrs = max(1.0, (sim.day - getattr(c, "birth_day", 0)) / 365.0)
        return c.decay / yrs
    body = [c for c in decided if PATHS.path_of(c) == "กายบำเพ็ญ"]
    spirit = [c for c in decided if PATHS.path_of(c) == "จิตบำเพ็ญ"]
    if len(body) >= 10 and len(spirit) >= 10:
        print(f"  (ในโลกจริง กายบำเพ็ญ {len(body)} คน {st.median(rate(c) for c in body):.4f}/ปี · "
              f"จิตบำเพ็ญ {len(spirit)} คน {st.median(rate(c) for c in spirit):.4f}/ปี "
              f"— ต่างกันด้วยวิถีชีวิต ไม่ใช่ด้วยกฎ)")


def test_spirit_climbs_higher(sim, decided):
    """วัดที่ตัวกฎเช่นกัน — โยนเหรียญข้ามขั้นคนละ 400 ครั้งด้วยลำดับสุ่มชุดเดียวกัน"""
    print("\n=== 3. สายจิตต้องข้ามขั้นได้ง่ายกว่า (วัดที่กฎ) ===")
    import copy
    import random
    src = next(c for c in sim.cast if c.alive and c.skills and c.realm < C.REALM_CAP - 1)
    bs, ss = _skill_sets()
    w = sim.world(src.world_id)
    import collections
    wins, outcomes = {}, collections.defaultdict(collections.Counter)
    for label, skills in (("กายบำเพ็ญ", bs), ("จิตบำเพ็ญ", ss)):
        ok = 0
        for i in range(400):
            ch = copy.deepcopy(src)
            ch.skills, ch.items = list(skills), []
            # สะสม "พอดีเป๊ะ" ไม่ใช่เหลือเฟือ — ถ้าให้เกินมาก โบนัสส่วนเกินจะดัน p ไปชน
            # เพดาน 0.95 ของทั้งคู่ แล้วส่วนต่างของสายจะถูกกลืนหายไปทั้งหมด (เจอจริง: ผลออกมา
            # เท่ากันเป๊ะทั้ง 400 ครั้ง) และต้องเติม hp เต็มด้วย ไม่งั้นด่านทัณฑ์สวรรค์จะฆ่าทั้งคู่
            # ก่อนถึงจุดที่วัด (เจอจริงเช่นกัน: "บาดเจ็บสาหัส" 351 จาก 400 ทั้งสองสาย)
            ch.insight = R.need(ch, w)
            ch.refine, ch.decay, ch.fails = 0.0, 0.0, 0
            ch.inner = 0.0                        # ล้างจิตมารทั้งคู่ ไม่งั้นด่านที่สองบังตัวแปรที่วัด
            ch.hp = getattr(ch, "max_hp", 100) or 100
            res, _ = R.attempt_break(sim, ch, w, random.Random(1000 + i))
            outcomes[label][str(res)] += 1
            # วัดที่ **ด่านพลัง** ซึ่งเป็นด่านที่ PATH_SPIRIT_BREAK ออกฤทธิ์จริง — ผ่านด่านนี้คือ
            # ไม่ได้ผลลัพธ์ "ล้มเหลว" ส่วนด่านถัดไป (จิตมาร และทัณฑ์สวรรค์ที่วัดจาก hp) เป็นคนละ
            # กลไกที่สายบำเพ็ญไม่ได้เกี่ยว การเอา "ผ่านครบทุกด่าน" มาเป็นเกณฑ์จึงวัดผิดตัวแปร
            ok += 0 if res == "ล้มเหลว" else 1
        wins[label] = ok
    for label in wins:
        print(f"  {label}: {dict(outcomes[label])}")
    print(f"  ผ่านด่านพลังจาก 400 ครั้ง — กาย {wins['กายบำเพ็ญ']} | จิต {wins['จิตบำเพ็ญ']}")
    assert wins["จิตบำเพ็ญ"] > wins["กายบำเพ็ญ"], "สายจิตไม่ได้ข้ามขั้นง่ายกว่าในระดับกฎ"
    print(f"  ✓ สายจิตผ่านด่านพลังบ่อยกว่า "
          f"{(wins['จิตบำเพ็ญ']/max(1,wins['กายบำเพ็ญ'])-1)*100:.0f}%")
    body = [c for c in decided if PATHS.path_of(c) == "กายบำเพ็ญ"]
    spirit = [c for c in decided if PATHS.path_of(c) == "จิตบำเพ็ญ"]
    if body and spirit:
        print(f"  (ในโลกจริง ขั้นเฉลี่ย กาย {st.mean(c.realm for c in body):.2f} · "
              f"จิต {st.mean(c.realm for c in spirit):.2f})")


def test_balance_resists_chaos(sim):
    print("\n=== 4. สายสมดุลต้องเป็นสายเดียวที่ลดความแพ้ทางเผ่าโกลาหลได้ ===")
    lord = sim.cast[sim.lord_cid]
    alive = [c for c in sim.cast if c.alive and not c.is_chaos()]
    bal = next((c for c in alive if PATHS.is_balanced(c) and not R.has_anti_chaos(c)), None)
    one = next((c for c in alive if PATHS.path_of(c) in ("กายบำเพ็ญ", "จิตบำเพ็ญ")
                and not R.has_anti_chaos(c)), None)
    assert bal is not None and one is not None, "หาตัวอย่างเทียบไม่ได้"
    e_bal, e_one = abs(R.chaos_edge(lord, bal)), abs(R.chaos_edge(lord, one))
    print(f"  แพ้ทางของ{PATHS.path_of(bal)} ({bal.name}) = {e_bal:.3f}")
    print(f"  แพ้ทางของ{PATHS.path_of(one)} ({one.name}) = {e_one:.3f}")
    assert e_bal < e_one, "สายสมดุลไม่ได้เปรียบอะไรเลยต่อเผ่าโกลาหล"
    print(f"  ✓ สมดุลลดความแพ้ทางลง {(1-e_bal/e_one)*100:.0f}%")


def test_treasures(sim):
    print("\n=== 5. สมบัติสามชิ้นใหม่ต้องมีจริงและออกฤทธิ์จริง ===")
    names = {it.name for it in sim.items.values()}
    for want in (T.ANTI_CHAOS_TREASURE, *T.CULTIVATION_AIDS):
        assert want in names, f"ไม่พบ{want}ในโลกเลย"
    print(f"  ✓ อยู่ในโลกครบทั้ง 3 ชิ้น")

    # ตราประทับต้องทำให้คนที่ไม่รู้วิชาแก้ทาง กลายเป็นแก้ทางได้
    iid = next(i for i, it in sim.items.items() if it.name == T.ANTI_CHAOS_TREASURE)
    victim = next(c for c in sim.cast if c.alive and not R.has_anti_chaos(c) and not c.is_chaos())
    before = R.has_anti_chaos(victim, sim.items)
    victim.items.append(iid)
    after = R.has_anti_chaos(victim, sim.items)
    victim.items.remove(iid)
    print(f"  ตราประทับ: แก้ทางได้ {before} -> {after}")
    assert not before and after, "ถือตราประทับแล้วยังไม่นับว่าแก้ทางได้"

    # เบ้าหลอมกายา: ความเสื่อมต้องสะสมช้าลงจริงเมื่อเวลาเดินเท่ากัน
    import copy
    iid_b = next(i for i, it in sim.items.items() if it.name == "เบ้าหลอมกายาสหัสธาตุ")
    # ต้องเลือกคนที่ "บำเพ็ญแล้วได้ความเข้าใจจริง" — ตัวคูณของประทีปคูณกับของที่ได้ ถ้าคนนั้นได้ 0
    # อยู่แล้ว (สายเลือดไม่มีส่วนมนุษย์ ดู rules.eff) คูณเท่าไหร่ก็ยังเป็น 0 แล้วเทสต์จะฟ้องผิดจุด
    base = next(c for c in sim.cast
                if c.alive and c.skills and R.eff(c, "human") > 0)
    a1, a2 = copy.deepcopy(base), copy.deepcopy(base)
    a2.items = list(a2.items) + [iid_b]
    w = sim.world(base.world_id)
    d0 = a1.decay
    R.age_and_decay(sim, a1, w, 3650, sim.rng)
    R.age_and_decay(sim, a2, w, 3650, sim.rng)
    g1, g2 = a1.decay - d0, a2.decay - d0
    print(f"  เบ้าหลอมกายา: เสื่อมใน 10 ปี {g1:.3f} -> {g2:.3f}")
    assert g2 < g1, "ถือเบ้าหลอมแล้วยังเสื่อมเท่าเดิม"

    # ประทีปดวงจิต: ความเข้าใจต้องงอกเร็วขึ้นจริง
    iid_s = next(i for i, it in sim.items.items() if it.name == "ประทีปดวงจิตพันภพ")
    b1, b2 = copy.deepcopy(base), copy.deepcopy(base)
    b2.items = list(b2.items) + [iid_s]
    i0 = b1.insight
    R.cultivate(b1, 3650, sim.items)
    R.cultivate(b2, 3650, sim.items)
    print(f"  ประทีปดวงจิต: ความเข้าใจที่ได้ {b1.insight-i0:.3f} -> {b2.insight-i0:.3f}")
    assert b2.insight > b1.insight, "ถือประทีปแล้วความเข้าใจไม่ได้งอกเร็วขึ้น"
    print("  ✓ ทั้งสามชิ้นออกฤทธิ์ตามที่เขียนไว้")


def main():
    print(f"รันซิม {YEARS} ปี...")
    test_lines_mapped()
    sim = run()
    print(f"  ถึงปีที่ {sim.day//365:,} | {len(sim.log):,} เหตุการณ์ | มีชีวิต {len(sim.alive_cids):,}")
    decided = test_paths_emerge(sim)
    test_body_is_tougher(sim, decided)
    test_spirit_climbs_higher(sim, decided)
    test_balance_resists_chaos(sim)
    test_treasures(sim)
    print("\n✓ สองสายต่างกันจริง และสมบัติสามชิ้นมีผลจริง")


if __name__ == "__main__":
    main()
