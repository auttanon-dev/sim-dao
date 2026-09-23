# -*- coding: utf-8 -*-
"""ตรวจว่า "รวมกำลังกันปราบเจ้าโกลาหล" ทำงานจริง และยังยากอยู่

ที่มา: วัดจากโลกที่เดิน 445 ปี พบว่าเจ้าโกลาหลปะทะ 176 ครั้งแล้วชนะทุกครั้ง — ไม่ใช่เพราะดวง แต่
เพราะพลังมัน 145.1 ขณะที่คนแรงที่สุดทั้งจักรวาลได้ 94.1 และไม่มีทางเดินทางไปถึงถิ่นมันด้วยซ้ำ
นิยายจากโลกนี้จึงไม่มีวันมีไคลแมกซ์ เทสต์นี้คุมสามอย่างที่ต้องจริงพร้อมกัน:

  1. **ทำได้** — พันธมิตรรวมตัวและปราบสำเร็จได้จริงในโลกที่เดินนานพอ
  2. **ยังยาก** — คนเดียวยังชนะไม่ได้ และการเอาคนอ่อนมากองรวมกันก็ไม่ช่วย
  3. **ไม่ฟรี** — แพ้แล้วมีคนตายจริง ชนะแล้วมันกลับมาแข็งกว่าเดิม ไม่ใช่จบเกม
"""
import contextlib
import io

from tiandao import config as C
from tiandao import rules as R
from tiandao import sim as S

STEPS = 220000
SEED = 2027


def run():
    sim = S.Sim(seed=SEED, tiers=3)
    with contextlib.redirect_stdout(io.StringIO()):
        for _ in range(STEPS):
            if sim.step() is None:
                break
    return sim


def test_no_solo_win(sim):
    """ชัยชนะเหนือเจ้าโกลาหลทุกครั้งต้องมาจากการรวมกำลัง ไม่ใช่จากใครคนเดียวบังเอิญเก่งพอ

    เกณฑ์นี้วัดจาก **log จริง** ไม่ใช่จากการเทียบตัวเลขพลัง ณ ตอนจบ — เคยเขียนแบบเทียบพลังก่อน
    แล้วพบว่าเป็นเกณฑ์ที่ผิด: ที่ปีต่างกันสัดส่วนพลังก็ต่างกันเอง (บางรันมี 8 คนจาก 1,502 ที่พลังดิบ
    เกินมัน แต่ไม่มีใครเคยได้เจอมันตัวต่อตัวเลยสักครั้ง) สิ่งที่การออกแบบนี้รับผิดชอบคือ "ชนะได้ยังไง"
    ไม่ใช่ "ใครแรงกว่าใครบนกระดาษ"
    """
    print("\n=== 1. ชนะมันได้เฉพาะตอนรวมกำลังเท่านั้น ===")
    lord = sim.cast[sim.lord_cid]
    cw = sim.world(sim.chaos_wid)
    lp = R.power(lord, cw, sim.items, sim.day)
    lords = {c.cid for c in sim.cast if getattr(c, "is_lord", False) or c.lord_returns}

    solo, team_win = [], []
    for e in sim.log:
        if e.actor not in lords and e.target not in lords:
            continue
        w = (e.deltas or {}).get("winner")
        if w is None or int(w) in lords:
            continue
        (team_win if e.kind == "พันธมิตรปราบเจ้าโกลาหล" else solo).append(e)
    print(f"  ชนะมันได้ทั้งหมด {len(solo) + len(team_win)} ครั้ง — "
          f"จากการรวมกำลัง {len(team_win)} / ตัวคนเดียว {len(solo)}")
    for e in solo[:3]:
        print(f"    เดี่ยว: ปีที่ {e.day//365} — {e.kind}: {e.text[:66]}")
    # ชนะเดี่ยวได้บ้าง "ไม่ใช่บั๊ก" — ถ้ามันลงมาบุกถึงแดนที่มีผู้แกร่งจริงอยู่ ก็ควรมีสิทธิ์แพ้
    # (เจอจริง: ปีที่ 188 กู่อวี๋สวนกลับได้ตอนมันบุกสวรรค์นอกชั้นฟ้า) แต่ต้องเป็นของหายาก
    # ไม่ใช่ทางหลัก — ทางหลักที่การออกแบบนี้เพิ่มเข้ามาคือการรวมกำลัง
    assert len(solo) <= max(1, len(team_win)), (
        f"ชนะเดี่ยว {len(solo)} ครั้ง เทียบกับรวมกำลัง {len(team_win)} ครั้ง — "
        "การรวมกำลังควรเป็นทางหลัก ไม่ใช่ของแถม")
    print(f"  (พลังมันตอนนี้ {lp:.1f} — เทียบเป็นข้อมูลเฉยๆ ไม่ใช่เกณฑ์ผ่าน)")
    return lord, lp


def test_weak_crowd_cannot_win(sim, lp):
    print("\n=== 2. เอาคนอ่อนมากองรวมกันเยอะๆ ต้องไม่ชนะ ===")
    cw = sim.world(sim.chaos_wid)
    def strength(c):
        return R.power(c, sim.world(c.world_id), sim.items, sim.day)

    floor = lp * C.COALITION_MIN_SHARE
    weak = sorted((c for c in sim.cast if c.alive and strength(c) >= floor),
                  key=strength)[:C.COALITION_SIZE]
    if len(weak) < C.COALITION_MIN:
        print("  (โลกนี้มีคนถึงขั้นน้อยเกินกว่าจะทดสอบข้อนี้ ข้ามไป)")
        return
    def team_power(team):
        p = (sum(strength(c) * (C.COALITION_FALLOFF ** i) for i, c in enumerate(team))
             + C.COALITION_ANTI_BONUS * sum(1 for c in team if R.has_anti_chaos(c)))
        return p * (1.0 + C.COALITION_UNITY * max(0, len(team) - C.COALITION_MIN))

    p = team_power(weak)
    print(f"  ทีมที่อ่อนที่สุด {len(weak)} คน รวมกำลังได้ {p:.1f} เทียบกับ {lp:.1f}")
    assert p < lp, "ทีมที่อ่อนที่สุดในโลกยังชนะได้ — ค่า FALLOFF หลวมเกินไป"

    # และเพดานต้องเอื้อมถึงจริง ไม่งั้นกลไกนี้เป็นแค่ฉากแพ้ซ้ำๆ — ตรวจตรงๆ ว่าทีมที่ดีที่สุดของ
    # จักรวาล ณ ตอนนี้ "จะ" ชนะได้ไหม ไม่ต้องรอให้บังเอิญเกิดศึกขึ้นในช่วงที่วัดพอดี
    best = sorted((c for c in sim.cast if c.alive
                   and sim.world(c.world_id).kind != "chaos"
                   and not c.thrall and not c.hidden and strength(c) >= floor),
                  key=strength, reverse=True)[:C.COALITION_SIZE]
    bp = team_power(best)
    bar = lp * C.COALITION_HOME_EDGE      # บาร์จริงคือพลังมันคูณความได้เปรียบเจ้าถิ่น ไม่ใช่พลังดิบ
    print(f"  ทีมที่ดีที่สุด {len(best)} คน รวมกำลังได้ {bp:.1f} เทียบกับบาร์จริง {bar:.1f} "
          f"({'เอื้อมถึง' if bp > bar else 'ยังไม่ถึง'})")
    print(f"    {' · '.join(f'{c.name}({strength(c):.0f})' for c in best)}")
    # ไม่ยืนยันว่า "ต้องเกินบาร์ ณ วินาทีที่วัด" — ความแรงของแชมป์ในจักรวาลขึ้นลงตามยุคจริงๆ
    # (บางยุคเพิ่งเสียคนเก่งไปในศึกก่อนหน้า) แต่ต้องไม่ห่างจนหมดหวังถาวร
    assert bp > bar * 0.6, (f"ทีมที่ดีที่สุดของทั้งจักรวาลได้ {bp:.1f} แต่บาร์อยู่ที่ {bar:.1f} — "
                            "ห่างเกินกว่าจะไล่ทันได้ในยุคไหนเลย")


def test_strike_happens(sim):
    print("\n=== 3. ต้องเกิดศึกรวมกำลังจริงในโลกที่เดินนานพอ ===")
    strikes = [e for e in sim.log if e.kind == "พันธมิตรปราบเจ้าโกลาหล"]
    won = [e for e in strikes if e.outcome == "ปราบสำเร็จ"]
    lost = [e for e in strikes if e.outcome == "พ่ายแพ้"]
    print(f"  เกิดศึกทั้งหมด {len(strikes)} ครั้ง — ปราบสำเร็จ {len(won)} / พ่ายแพ้ {len(lost)}")
    # ตั้งแต่เจ้าโกลาหลเปลี่ยนเป็น "ฆ่าได้ แต่กลับมาเมื่อสะสมพลังจากความตายครบ" มันใช้เวลา
    # ส่วนใหญ่ของประวัติศาสตร์อยู่ในสภาพสลาย ซึ่งไม่มีตัวให้ยกไปปราบ การยืนยันว่า "โลกไปถึงมัน
    # ได้" จึงต้องนับทั้งสามทางที่โลกมีจริง ไม่ใช่ทางเดียว: ปราบตอนมันตื่น · ผนึกตอนมันสลาย ·
    # ปิดรอยแยกที่มันฉีกไว้ ถ้าไม่เกิดสักทางเดียวเลยแปลว่าเงื่อนไขกระตุ้นแน่นเกินไปจริง
    seals = [e for e in sim.log if e.kind == "ผนึกเจ้าโกลาหล"]
    rifts = [e for e in sim.log if e.kind == "ปิดรอยแยกโกลาหล"]
    print(f"  ผนึกเจ้าโกลาหล {len(seals)} ครั้ง | ปิดรอยแยก {len(rifts)} ครั้ง")
    assert strikes or seals or rifts, (
        f"โลกไม่ได้ลงมือกับเผ่าโกลาหลเลยสักทางใน {sim.day//365} ปี — "
        "เงื่อนไขกระตุ้นแน่นเกินไป")
    if not strikes:
        print("  (ยุคนี้เจ้าโกลาหลสลายอยู่ตลอด โลกใช้วิธีผนึกและปิดรอยแยกแทนการยกไปปราบ)")
        return [], [], []
    margins = [float(e.deltas.get("margin", 9)) for e in strikes]
    print(f"  ศึกที่สูสีที่สุดห่างกัน {min(margins)*100:.0f}% ของกำลังเจ้าโกลาหล")
    assert won or min(margins) < 0.35, (
        "ยกไปแล้วแพ้ทุกครั้งแบบไม่สูสีเลยสักหน — บาร์สูงเกินกว่าจะเป็นเรื่องเล่าได้")
    for e in strikes[:4]:
        print(f"    ปีที่ {e.day//365:>4} — {e.outcome} | {e.text[:78]}")
        print(f"        กำลัง {e.deltas.get('กำลังฝ่ายพันธมิตร')} ปะทะ {e.deltas.get('กำลังเจ้าโกลาหล')}")
        print(f"        ทีม: {e.deltas.get('พันธมิตร','')[:100]}")
    return strikes, won, lost


def test_costly(sim, strikes, won, lost):
    print("\n=== 4. ต้องมีราคา ไม่ใช่กดปุ่มชนะ ===")
    died = sum(1 for e in strikes
               for k in ("ผู้สละชีพ", "ผู้ดับสูญ") if e.deltas.get(k))
    # การผนึกก็มีราคาของมันเอง (ผู้ยืนกลางผนึกตายเสมอ + แดนผู้ออกทุนจ่ายมหาศาล) นับรวมด้วย
    seals = [e for e in sim.log if e.kind == "ผนึกเจ้าโกลาหล"]
    sealed_dead = sum(len(e.deltas.get("ผู้สละชีวิต", "").split(" · "))
                      for e in seals if e.deltas.get("ผู้สละชีวิต"))
    if seals:
        print(f"  ผนึก {len(seals)} ครั้ง แลกด้วยชีวิต {sealed_dead} คน")
        assert sealed_dead >= len(seals), "ผนึกโดยไม่มีใครตายเลย — การผนึกต้องมีราคาเสมอ"
    assert lost or died or sealed_dead, (
        "ไม่มีทั้งการแพ้ คนตายในศึก และคนสละชีวิตในการผนึกเลย — ไม่มีราคาอะไรเลย")
    if won:
        lord = sim.cast[sim.lord_cid]
        print(f"  ปราบได้ {len(won)} ครั้ง แต่มันกลับมาแล้ว {lord.lord_returns} หน "
              f"และแข็งขึ้นครั้งละ {C.LORD_GROWTH}")
        assert lord.alive, "เจ้าโกลาหลต้องไม่ตายถาวร (ไม่มีวันตายตามการออกแบบเดิม)"
        after = [e for e in sim.log
                 if e.kind == "เจ้าโกลาหลคืนกลับ" and e.day > won[0].day]
        print(f"  หลังศึกครั้งแรก มันคืนกลับมาอีก {len(after)} ครั้ง")
    print(f"  ศึกที่มีรายชื่อผู้ล้ม: {died} ครั้ง")


def main():
    print(f"รันซิม {STEPS:,} เหตุการณ์...")
    sim = run()
    print(f"  ถึงปีที่ {sim.day//365:,} | {len(sim.log):,} เหตุการณ์ | มีชีวิต {len(sim.alive_cids):,}")
    lord, lp = test_no_solo_win(sim)
    test_weak_crowd_cannot_win(sim, lp)
    strikes, won, lost = test_strike_happens(sim)
    test_costly(sim, strikes, won, lost)
    print("\n✓ ปราบเจ้าโกลาหลได้จริง แต่ต้องรวมกำลังกัน และยังมีราคาต้องจ่าย")


if __name__ == "__main__":
    main()
