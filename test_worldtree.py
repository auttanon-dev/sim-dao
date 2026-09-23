# -*- coding: utf-8 -*-
"""ตรวจแดนเซียนสาขา และต้นไม้โลกในแดนลับต้นกำเนิด

หลักเดียวกับเทสต์อื่นในโปรเจกต์นี้: วัดว่ามัน "เกิดขึ้นจริงในซิม" ไม่ใช่แค่ "มีโค้ดเขียนไว้"

จำนวนแดนสาขาเป็นของที่โตได้ ไม่ใช่ค่าคงที่ — สเปกปัจจุบันคือ **เริ่มที่ C.BRANCH_REALMS แดน
แล้วปล่อยให้โลกตั้งเพิ่มเอง** เมื่อมีผู้รอดจากแดนลับต้นกำเนิดไปตั้งสำนักของตัวเอง โดยมีเพดาน
รวมที่ C.TREE_BRANCH_CAP และมีชื่อในคลังให้ใช้ 108 ชื่อ (ดู branches.build)

ไฟล์นี้เคยเขียนหัวข้อและข้อความสรุปว่า "108 แดน" ทั้งที่ assertion ตรวจแค่ C.BRANCH_REALMS
(36) และรันจริงได้ราว 42 แดน แล้วพิมพ์ว่าผ่าน — เป็นการรายงานเกินกว่าที่ตรวจจริง
"""
import contextlib
import io

from tiandao import branches as BR
from tiandao import config as C
from tiandao import sim as S
from tiandao import worldtree as WT

STEPS = 60000
SEED = 5


def run():
    sim = S.Sim(seed=SEED, tiers=3)
    with contextlib.redirect_stdout(io.StringIO()):
        for _ in range(STEPS):
            if sim.step() is None:
                break
    return sim


def test_branches_exist(sim):
    print(f"\n=== 1. แดนเซียนสาขาต้องมีจริง (เริ่ม {C.BRANCH_REALMS} แดน แล้วงอกเพิ่มเอง) ===")
    br = [w for w in sim.worlds if getattr(w, "skill_line", None)]
    # แยกสามเรื่องออกจากกันให้ชัด: จำนวนที่หว่านไว้ตั้งแต่ต้น · ที่โลกตั้งเพิ่มเอง · เพดานรวม
    seeded = len(br) - sim.tree_founded
    print(f"  หว่านไว้ตั้งต้น {seeded} แดน | โลกตั้งเพิ่มเองระหว่างซิม {sim.tree_founded} แดน "
          f"| รวม {len(br)} แดน (เพดาน {C.TREE_BRANCH_CAP} โลก · คลังชื่อ {len(BR.build())} ชื่อ)")
    assert seeded == C.BRANCH_REALMS, f"หว่านตั้งต้นได้ {seeded} แดน ไม่ตรงกับที่ตั้งค่าไว้"
    assert sim.tree_founded > 0, "ไม่มีใครตั้งแดนสาขาใหม่เลย — จำนวนแดนไม่ได้โตแบบ dynamic จริง"
    assert len(sim.worlds) <= C.TREE_BRANCH_CAP, "จำนวนโลกทะลุเพดานที่ตั้งไว้"
    assert C.BRANCH_REALMS <= len(BR.build()), "หว่านตั้งต้นมากกว่าชื่อที่มีในคลัง"
    names = [w.name for w in br]
    assert len(set(names)) == len(names), "มีชื่อแดนซ้ำกัน"
    pops = [w.n_alive for w in br]
    alive_realms = sum(1 for p in pops if p > 0)
    print(f"  มีประชากรอยู่จริง {alive_realms} จาก {len(br)} แดน "
          f"| รวม {sum(pops):,} คน | เฉลี่ย {sum(pops)//len(br)} คน/แดน")
    assert alive_realms >= C.BRANCH_REALMS * 0.8, "สาขาส่วนใหญ่ร้างคน"
    lines = {w.skill_line for w in br}
    print(f"  สายวิชาประจำแดนที่ต่างกัน {len(lines)} สาย")
    # เพดานคือจำนวน "สายที่เรียนได้จริงในชั้นแดนเซียน" ซึ่งมี 16 สาย (ดู branches._viable_lines)
    assert len(lines) >= 12, "สาขาเกือบทั้งหมดใช้สายวิชาเดียวกัน — ไม่ต่างกันจริง"
    return br


def test_branches_teach_differently(sim, br):
    print("\n=== 2. สาขาต้องผลิตคนคนละแบบจริง (วิชาประจำแดนต้องเด่นขึ้นมา) ===")
    from tiandao.rules import SKILL_INDEX   # ดัชนีวิชาอยู่ใน rules ไม่ใช่ skills
    hits = misses = 0
    for w in br:
        ppl = [c for c in sim.living_in(w.wid) if c.skills]
        if len(ppl) < 3:
            continue
        own = sum(1 for c in ppl for n in c.skills
                  if SKILL_INDEX.get(n) and SKILL_INDEX[n][1] == w.skill_line)
        tot = sum(len(c.skills) for c in ppl)
        if not tot:
            continue
        if own / tot > 0.15:
            hits += 1
        else:
            misses += 1
    ratio = hits / max(1, hits + misses)
    print(f"  ตรวจ {hits + misses} สาขา — สาขาที่วิชาประจำแดนคิดเป็น >15% ของวิชาทั้งหมด: "
          f"{hits} ({ratio:.0%})")
    assert ratio > 0.5, "วิชาประจำแดนไม่ได้เด่นขึ้นมาจริง สาขาจึงเหมือนกันหมด"


def test_tree_acts(sim):
    print("\n=== 3. ต้นไม้โลกต้องทำงานครบทั้งสี่อย่าง ===")
    gifts = [e for e in sim.log if e.kind == "ต้นไม้โลกหยั่งกิ่ง"]
    trials = [e for e in sim.log if e.kind == "แดนลับต้นกำเนิดเปิด"]
    print(f"  แจกของให้โลกที่เสื่อม {len(gifts)} ครั้ง | เปิดแดนลับ {len(trials)} ครั้ง "
          f"| ตั้งสาขาใหม่ระหว่างซิม {sim.tree_founded} แดน")
    print(f"  ความมีชีวิตของต้นไม้ตอนนี้ {sim.tree_vitality:,.0f}/{WT.capacity(sim):,.0f}")
    assert trials, "ไม่เคยเปิดแดนลับเลย"
    if gifts:
        for e in gifts[:2]:
            print(f"    ปีที่ {e.day//365}: {e.text[:96]}")
    else:
        # กิ่งจะหยั่งก็ต่อเมื่อมีแดนเข้ายุคเสื่อมจริง (คลังฟ้าต่ำกว่า TREE_DECLINE_AT) ซึ่งเป็น
        # เงื่อนไขมหภาคที่บางรันไม่เกิดเลย — เดิมข้อนี้จึงแพ้/ชนะตามว่าคลังฟ้าของแดนที่ต้นไม้
        # เฝ้าอยู่ "บังเอิญ" แตะ 0.35 หรือไม่ (วัดจริง 0.324 กับ 0.406 ในสองรันที่ต่างกันนิดเดียว)
        # ถ้ารันนี้ไม่มีแดนไหนเสื่อมเลย ให้ไปวัดกลไกกับแดนที่ถูกทำให้เสื่อมจริงแทน — ยังเป็น
        # การวัดว่ามันทำงานจริง ไม่ใช่การยกเลิกเงื่อนไขทิ้ง
        print("  ไม่มีแดนไหนเข้ายุคเสื่อมตลอดรันนี้ — ตรวจกลไกกับแดนที่ถูกทำให้เสื่อมจริงแทน")
        check_gift_fires_when_a_realm_declines()

    died = sum(1 for e in trials if e.deltas.get("ผู้ไม่ได้กลับออกมา"))
    print(f"  ครั้งที่มีคนไม่ได้กลับออกมา: {died} จาก {len(trials)}")
    assert died, "เข้าแดนลับแล้วทุกคนกลับครบทุกครั้ง — ไม่มีราคาอะไรเลย"

    multi = [e for e in trials if len(e.deltas.get("มาจากแดน", "").split(" · ")) > 1]
    print(f"  ครั้งที่ดูดคนจากมากกว่าหนึ่งแดน: {len(multi)} จาก {len(trials)}")
    assert multi, "แดนลับดูดคนจากแดนเดียวตลอด ไม่ใช่ 'หลากแดน' อย่างที่ตั้งใจ"


def check_gift_fires_when_a_realm_declines():
    """แดนที่คลังฟ้าพร่องจนเข้ายุคเสื่อม ต้องได้กิ่งหยั่งลงมาจริง และต้องมีราคาที่ต้นไม้จ่าย"""
    import random
    probe = S.Sim(seed=SEED, tiers=2)
    with contextlib.redirect_stdout(io.StringIO()):
        for _ in range(1500):
            probe.step()
    WT.init(probe)
    w = probe.worlds[0]
    w.heaven = w.cap() * C.TREE_DECLINE_AT * 0.5
    assert w.state() == "ยุคเสื่อม", "ตั้งค่าแล้วแดนยังไม่เข้ายุคเสื่อม"
    probe.tree_vitality = WT.capacity(probe)
    before = probe.tree_vitality
    seen = sum(1 for e in probe.log if e.kind == "ต้นไม้โลกหยั่งกิ่ง")
    rng = random.Random(1)
    for _ in range(20):
        probe.tree_last_tick = probe.day - C.TREE_TICK_DAYS
        WT.tick(probe, rng)
        if sum(1 for e in probe.log if e.kind == "ต้นไม้โลกหยั่งกิ่ง") > seen:
            break
    got = [e for e in probe.log if e.kind == "ต้นไม้โลกหยั่งกิ่ง"]
    print(f"  แดนที่ถูกทำให้เสื่อม (คลังฟ้า {w.ratio():.0%}) ได้กิ่งหยั่ง {len(got) - seen} ครั้ง")
    assert len(got) > seen, "แดนเข้ายุคเสื่อมแล้วต้นไม้ยังไม่หยั่งกิ่งลงมาเลย"
    assert probe.tree_vitality < before, "หยั่งกิ่งแล้วต้นไม้ไม่เสียความมีชีวิตเลย — ของฟรี"
    print(f"    {got[-1].text[:96]}")


def test_tree_death_breaks_balance(sim):
    print("\n=== 4. ถ้าต้นไม้ตาย สมดุลสองโลกต้องพังจริง ===")
    w0, w1 = sim.worlds[0], sim.worlds[1]
    before = (w0.heaven, w1.heaven, w0.rift)
    WT._collapse(sim, 3650)          # จำลองว่ามันตายไปแล้ว 10 ปี
    after = (w0.heaven, w1.heaven, w0.rift)
    print(f"  โลกมนุษย์ ปราณ {before[0]:,.0f} -> {after[0]:,.0f} | "
          f"รอยแยก {before[2]:.2f} -> {after[2]:.2f}")
    print(f"  แดนเซียน ปราณ {before[1]:,.0f} -> {after[1]:,.0f}")
    assert after[0] < before[0] and after[1] < before[1], "ต้นไม้ตายแล้วปราณไม่ได้รั่วเลย"
    assert after[2] > before[2], "ต้นไม้ตายแล้วรอยแยกไม่ได้กว้างขึ้น"
    print("  ✓ ปราณรั่วทั้งสองโลกและรอยแยกกว้างขึ้นเองโดยไม่มีใครมาบุก")


def test_realms_are_separated(sim):
    print("\n=== 5. แต่ละสาขาต้องมีแผนที่ของตัวเอง และแยกขาดจากกันจริง ===")
    from tiandao import geo as GEO
    from tiandao import places as PL
    from tiandao import travel as TV
    br = [w for w in sim.worlds if getattr(w, "skill_line", None) and w.wid in sim.branch_wids]
    a, b = br[0], br[1]
    pa = [i for i, p in enumerate(PL.PLACES) if p[1] == a.place_key]
    pb = [i for i, p in enumerate(PL.PLACES) if p[1] == b.place_key]
    assert pa and pb and not set(pa) & set(pb), "สองสาขาใช้สถานที่ร่วมกัน — ไม่ได้แยกขาด"
    print(f"  {a.name}: {len(pa)} สถานที่ | {b.name}: {len(pb)} สถานที่ (ไม่ทับกันเลย)")
    d_in = TV.shortest_path_distance(pa[0], pa[1])
    d_out = TV.shortest_path_distance(pa[0], pb[0])
    days = TV.shortest_path_days(pa[0], pb[0], 3)
    print(f"  เดินในแดนตัวเอง {d_in:,.0f} หน่วย | ข้ามไปอีกสาขา {d_out:,.0f} หน่วย "
          f"({days} วันสำหรับขั้น 3)")
    assert d_out > d_in * 20, "ข้ามสาขาใกล้เกินไป การเดินทางยังไม่มีน้ำหนัก"
    assert days and days > 180, f"ข้ามสาขาใช้เวลาแค่ {days} วัน — ยังไม่ใช่การเดินทางจริง"


def test_portals(sim):
    print("\n=== 6. ประตูมิติต้องสร้างได้จริง มีราคา และย่นระยะทางได้จริง ===")
    from tiandao import portals as PORT
    from tiandao import places as PL
    from tiandao import travel as TV
    built = [e for e in sim.log if e.kind == "สร้างประตูมิติ"]
    print(f"  สร้างไปแล้ว {len(built)} บาน จาก {len(sim.portals)} ที่บันทึกไว้")
    assert built, "ไม่มีใครสร้างประตูมิติได้เลย — เงื่อนไขแน่นเกินไป"

    e = built[0]
    print(f"    ปีที่ {e.day//365}: {e.text[:92]}")
    print(f"    {e.deltas['ผู้ร่วมสร้าง'][:92]}")
    print(f"    ใช้ทรัพยากร {e.deltas['ทรัพยากรที่ใช้']}")
    assert "ผู้ร่วมสร้าง" in e.deltas, "ไม่ได้บันทึกว่าใครช่วยกันสร้าง"

    # ต้องกินทรัพยากรของแดนจริง ไม่ใช่ฟรี
    # ต้องมีการหักคลังจริงทุกบาน — คลังงอกกลับได้ การดูยอดคงเหลือตอนจบจึงไม่ใช่หลักฐาน
    spent_total = sum(float(e.deltas["ทรัพยากรที่ใช้"].split(" ")[0].replace(",", ""))
                      for e in built)
    print(f"  ทรัพยากรที่ถูกใช้ไปทั้งหมด {spent_total:,.0f} "
          f"(เฉลี่ย {spent_total/len(built):,.0f} ต่อบาน จากคลังตั้งต้น {C.REALM_RESOURCE_INIT:,.0f})")
    assert spent_total > C.REALM_RESOURCE_INIT, "รวมทั้งหมดยังไม่ถึงคลังตั้งต้นของแดนเดียว — ถูกเกินไป"

    # ยิ่งสร้างยิ่งชำนาญ
    ranked = [c for c in sim.cast if getattr(c, "dimension_rank", 0) > 0]
    best = max(ranked, key=lambda c: c.dimension_rank) if ranked else None
    print(f"  ผู้ที่ได้ความชำนาญมิติจากการสร้าง: {len(ranked)} คน "
          f"| สูงสุด {best.dimension_rank} บาน ({best.name})")
    assert ranked, "สร้างประตูแล้วไม่มีใครชำนาญขึ้นเลย"

    # ต้นทุนของทีมที่ชำนาญกว่าต้องถูกกว่าจริง
    weak = [c for c in sim.cast if PORT.mastery(c) > 0][:2]
    if best is not None and len(weak) >= 2:
        strong = [best] + weak[:1]
        print(f"  ต้นทุนประตู: ทีมธรรมดา {PORT.cost_for(weak):,.0f} "
              f"| ทีมที่มีผู้ชำนาญ {PORT.cost_for(strong):,.0f}")
        assert PORT.cost_for(strong) < PORT.cost_for(weak), "ทีมที่ชำนาญกว่าไม่ได้จ่ายถูกกว่า"

    # และประตูต้องย่นระยะทางจริงบนแผนที่
    spot, hub, _day, _who = sim.portals[0]
    d = TV.shortest_path_distance(spot, hub)
    print(f"  ระยะจาก{PL.PLACES[spot][0]}ถึงชุมทางกลางหลังมีประตู: {d:,.0f} หน่วย")
    assert d <= C.PORTAL_DISTANCE + 1, f"มีประตูแล้วแต่ระยะยังเป็น {d:,.0f}"
    print("  ✓ ประตูเป็นเส้นทางถาวรบนแผนที่จริง ระบบเดินทางเดิมใช้ได้ทันที")


def test_tree_scales_with_realms(sim):
    print("\n=== 7. ต้นไม้โลกต้องแข็งแรงขึ้นตามจำนวนแดนที่ยังยืนอยู่ ===")
    standing = sum(1 for w in sim.worlds if w.kind == "mortal" and w.n_alive > 0)
    cap = WT.capacity(sim)
    small = C.TREE_VITALITY_BASE + C.TREE_VITALITY_PER_REALM * 12
    # เกณฑ์ต้องอิงจำนวนแดนที่ "ตั้งค่าไว้จริง" ไม่ใช่ตัวเลขคงที่ — เดิมเขียนไว้ว่า cap > small*3
    # ซึ่งคิดจากโลก 108 สาขาตามบทออกแบบ แต่ C.BRANCH_REALMS ถูกลดเหลือ 36 (ที่เหลือปล่อยให้
    # โลกงอกเอง) เพดานสูงสุดที่เป็นไปได้จึงอยู่แค่ราว 2.7 เท่า ข้อนี้เลยแพ้ตลอดไม่ว่าซิมจะดีแค่ไหน
    full = C.TREE_VITALITY_BASE + C.TREE_VITALITY_PER_REALM * (12 + C.BRANCH_REALMS)
    print(f"  แดนที่ยังยืนอยู่ {standing} แดน -> เพดาน {cap:,.0f} "
          f"(ถ้ามีแค่ 12 แดนแบบเดิมจะได้ {small:,.0f} · ครบตามที่ตั้งค่าไว้จะได้ {full:,.0f})")
    print(f"  ฟื้นปีละ {WT.regen_rate(sim):.1f} | ตอนนี้มีพลัง {sim.tree_vitality:,.0f}")
    assert full > small * 2, ("ตั้ง C.BRANCH_REALMS ไว้น้อยจนเพดานไม่ต่างจากโลก 12 แดน "
                              "อย่างมีนัยสำคัญ — จำนวนแดนเลิกมีความหมายกับต้นไม้โลก")
    assert cap >= full * 0.9, "แดนส่วนใหญ่ร้างจนเพดานไม่โตตามจำนวนแดนที่ตั้งไว้"
    assert WT.regen_rate(sim) > C.TREE_REGEN_PER_YEAR, "อัตราฟื้นไม่ได้โตตามเพดาน"


def main():
    print(f"รันซิม {STEPS:,} เหตุการณ์ (เริ่มที่ {12 + C.BRANCH_REALMS} แดน)...")
    sim = run()
    print(f"  ถึงปีที่ {sim.day//365} | {len(sim.log):,} เหตุการณ์ "
          f"| มีชีวิต {len(sim.alive_cids):,} | แดนทั้งหมด {len(sim.worlds)}")
    br = test_branches_exist(sim)
    test_branches_teach_differently(sim, br)
    test_tree_acts(sim)
    test_realms_are_separated(sim)
    test_portals(sim)
    test_tree_scales_with_realms(sim)
    test_tree_death_breaks_balance(sim)
    print(f"\n✓ แดนเซียนสาขา ({C.BRANCH_REALMS} ตั้งต้น + {sim.tree_founded} ที่โลกตั้งเอง) "
          f"ต้นไม้โลก และประตูมิติ ทำงานจริงครบทุกข้อ")


if __name__ == "__main__":
    main()
