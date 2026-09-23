# -*- coding: utf-8 -*-
"""ตรวจว่าตัวละคร "อิงภูมิศาสตร์จริง" แค่ไหน — วัดจากซิมที่รันจริง ไม่ใช่จากการอ่านโค้ด

สำคัญ: ตัวเลขทุกตัวเก็บ ณ วินาทีที่เหตุการณ์เกิด (ดัก Sim.emit) ไม่ใช่ตอนจบซิม
ถ้าวัดจากสถานะตอนจบจะได้ผลผิด เพราะทั้ง realm และ place เปลี่ยนไปหมดแล้ว

ถามหกข้อ:
  1. กราฟมีพิกัดจริงไหม ระยะบนเส้นเชื่อมตรงกับระยะยูคลิดหรือเปล่า
  2. เวลาเดินทางที่ใช้ = ระยะทาง Dijkstra จริงหรือไม่
  3. ใช้เวลาอยู่ระหว่างทางจริงไหม (ไม่ใช่ teleport แล้วบวกวันทีหลัง)
  4. มีใครโผล่ข้ามโลกโดยไม่ผ่านประตูมิติไหม
  5. คนที่มีปฏิสัมพันธ์กัน ยืนอยู่ที่เดียวกันจริงหรือเปล่า
  6. เลือกจุดหมายใกล้ตัว หรือสุ่มทั่วแผนที่
"""
import collections
import contextlib
import io
import math
import statistics

from tiandao import sim as S
from tiandao import geo as GEO
from tiandao import places as PL
from tiandao import travel as TR

STEPS = 30000
SEED = 2026


def euclid(a, b):
    ax, ay = GEO.COORDS[a]
    bx, by = GEO.COORDS[b]
    return math.hypot(ax - bx, ay - by)


def head(n, title):
    print()
    print("=" * 64)
    print(f"{n}. {title}")
    print("=" * 64)


def q1_graph_is_geometric():
    head(1, "กราฟเป็นภูมิศาสตร์จริง หรือเป็นแค่กราฟนามธรรม")
    print(f"  พิกัด 2D: {len(GEO.COORDS)} จุด | เส้นเชื่อม: {len(GEO.EDGES)} เส้น")
    print(f"  ชนิดเส้นเชื่อม: {dict(collections.Counter(e[3] if len(e) > 3 else 'road' for e in GEO.EDGES))}")
    diffs = []
    for e in GEO.EDGES:
        if (e[3] if len(e) > 3 else "road") != "road":
            continue
        eu = euclid(e[0], e[1])
        if eu > 0:
            diffs.append(abs(e[2] - eu) / eu)
    if diffs:
        med = statistics.median(diffs)
        print(f"  ถนน {len(diffs)} เส้น: ระยะบนเส้นต่างจากระยะยูคลิดของพิกัด "
              f"มัธยฐาน {med*100:.2f}%")
        print(f"  -> {'ตรงกับพิกัดจริง' if med < 0.02 else 'ไม่ตรงกับพิกัด'}")
    deg = collections.Counter()
    for e in GEO.EDGES:
        deg[e[0]] += 1
        deg[e[1]] += 1
    print(f"  จุดที่ไม่มีเส้นเชื่อมเลย: {sum(1 for i in range(len(PL.PLACES)) if deg[i] == 0)}")
    print(f"  ดีกรีเฉลี่ย: {statistics.mean(deg.values()):.1f} เส้นต่อจุด")


def run_sim_instrumented():
    """รันซิมพร้อมดัก emit เพื่อเก็บตำแหน่ง/realm ณ เวลาเกิดเหตุการณ์"""
    trips = []      # (src, dst, realm ตอนออกเดินทาง, จำนวนวันที่ตั้งไว้)
    pairs = []      # (kind, place ของ actor, place ของ target)
    visits = collections.defaultdict(set)   # cid -> ชุดสถานที่ที่เคยไป
    orig = S.Sim.emit

    def patched(self, world, kind, actor, target, tags, outcome, text, elapsed,
                deltas=None, **kw):
        if kind == "เดินทาง" and outcome == "ออกเดินทาง" and actor is not None:
            trips.append((actor.place, actor.travel_dest, actor.realm,
                          actor.travel_arrival_day - self.day))
        if actor is not None and getattr(actor, "place", -1) >= 0:
            visits[actor.cid].add(actor.place)
        if actor is not None and target is not None:
            ap = getattr(actor, "place", -1)
            tp = getattr(target, "place", None)
            pairs.append((kind, ap if isinstance(ap, int) else -1,
                          tp if isinstance(tp, int) else -1))
        return orig(self, world, kind, actor, target, tags, outcome, text, elapsed, deltas, **kw)

    S.Sim.emit = patched
    try:
        sim = S.Sim(seed=SEED, tiers=3)
        with contextlib.redirect_stdout(io.StringIO()):
            for _ in range(STEPS):
                sim.step()
    finally:
        S.Sim.emit = orig
    return sim, trips, pairs, visits


def q2_travel_time_matches_distance(trips):
    head(2, "เวลาเดินทางที่ใช้ = ระยะทางจริงบนกราฟหรือไม่")
    ok = bad = 0
    for src, dst, realm, days in trips:
        if src < 0 or dst < 0:
            continue
        if TR.shortest_path_days(src, dst, realm) == days:
            ok += 1
        else:
            bad += 1
    tot = ok + bad
    if tot:
        print(f"  ตรวจ {tot} เที่ยว (ใช้ realm ณ ตอนออกเดินทาง)")
        print(f"  ตรงกับ Dijkstra เป๊ะ : {ok} ({ok/tot*100:.1f}%)")
        print(f"  ไม่ตรง               : {bad}")


def q3_time_actually_spent(sim):
    head(3, "ใช้เวลาอยู่ระหว่างทางจริงไหม (หรือ teleport แล้วบวกวันทีหลัง)")
    depart, gaps, enroute = {}, [], 0
    for e in sim.log:
        if e.kind != "เดินทาง" or e.actor is None:
            continue
        if e.outcome == "ออกเดินทาง":
            depart[e.actor] = e.day
        elif e.outcome == "มาถึง" and e.actor in depart:
            gaps.append(e.day - depart.pop(e.actor))
        elif "ระหว่างทาง" in (e.text or ""):
            enroute += 1
    if gaps:
        print(f"  จับคู่ ออกเดินทาง→มาถึง ได้ {len(gaps)} เที่ยว")
        print(f"  ใช้เวลาจริง เฉลี่ย {statistics.mean(gaps):.1f} วัน "
              f"(มัธยฐาน {statistics.median(gaps)} | สั้นสุด {min(gaps)} | ยาวสุด {max(gaps)})")
        print(f"  เที่ยวที่ถึงทันทีในวันเดียวกัน: {sum(1 for g in gaps if g == 0)}")
    print(f"  เหตุการณ์ที่เกิดระหว่างทาง: {enroute} ครั้ง")
    print(f"  กำลังเดินทางอยู่กลางทาง ณ ตอนจบ: "
          f"{sum(1 for c in sim.cast if c.alive and getattr(c, 'travel_dest', -1) >= 0)} คน")


def q4_world_boundaries(sim):
    head(4, "ข้ามโลกได้โดยไม่ผ่านประตูมิติไหม")
    bad = checked = 0
    for c in sim.cast:
        if not c.alive or c.place < 0:
            continue
        checked += 1
        if PL.PLACES[c.place][1] != getattr(sim.world(c.world_id), "place_key", None):
            bad += 1
    print(f"  ตรวจ {checked} คน: ยืนอยู่ในโลกที่ไม่ใช่ของตัวเอง {bad} คน")
    print(f"  เหตุการณ์ข้ามโลกผ่านช่องทางที่ถูกต้อง: "
          f"{sum(1 for e in sim.log if e.kind in ('ข้ามฟ้า', 'ลงโลกล่าง'))} ครั้ง")


def q5_encounters_are_local(pairs):
    head(5, "คนที่มีปฏิสัมพันธ์กัน ยืนอยู่ที่เดียวกันจริงหรือเปล่า")
    same = sum(1 for _k, a, b in pairs if a >= 0 and a == b)
    diff = sum(1 for _k, a, b in pairs if a >= 0 and b >= 0 and a != b)
    tot = same + diff
    if not tot:
        return
    print(f"  เหตุการณ์ที่มีคู่กรณี (วัด ณ เวลาเกิดจริง): {tot}")
    print(f"  อยู่ที่เดียวกัน : {same} ({same/tot*100:.1f}%)")
    print(f"  อยู่คนละที่     : {diff} ({diff/tot*100:.1f}%)")
    far = collections.Counter()
    dists = []
    for k, a, b in pairs:
        if a >= 0 and b >= 0 and a != b:
            far[k] += 1
            x = TR.shortest_path_distance(a, b)
            if x is not None:
                dists.append(x)
    print("\n  เหตุการณ์ที่เกิดข้ามระยะทางบ่อยสุด:")
    for k, v in far.most_common(8):
        print(f"    {k}: {v}")
    if dists:
        print(f"\n  ระยะห่างเฉลี่ยของคู่กรณีที่อยู่คนละที่: {statistics.mean(dists):.1f} หน่วย "
              f"(ไกลสุด {max(dists):.0f})")
    if diff / tot > 0.5:
        print("\n  -> ปฏิสัมพันธ์ไม่อิงตำแหน่ง (ดู sim.py: others = living_in(world.wid))")


def q6_destination_choice(trips):
    head(6, "เลือกจุดหมายใกล้ตัว หรือสุ่มทั่วแผนที่")
    picked, available = [], []
    for src, dst, _realm, _days in trips:
        if src < 0 or dst < 0:
            continue
        dp = TR.shortest_path_distance(src, dst)
        if dp is None:
            continue
        picked.append(dp)
        if len(available) < 300:
            wkey = PL.PLACES[src][1]
            ds = [TR.shortest_path_distance(src, j)
                  for j, p in enumerate(PL.PLACES) if p[1] == wkey and j != src]
            ds = [x for x in ds if x is not None]
            if ds:
                available.append(statistics.mean(ds))
    if picked and available:
        pm, am = statistics.mean(picked), statistics.mean(available)
        print(f"  ระยะทางที่เลือกไปจริง เฉลี่ย     : {pm:.1f} หน่วย")
        print(f"  ระยะทางเฉลี่ยของทุกที่ที่ไปได้ : {am:.1f} หน่วย")
        print(f"  อัตราส่วน {pm/am:.2f}")
        if pm / am > 0.9:
            print("  -> สุ่มทั่วแผนที่ ภูมิศาสตร์เป็น 'ค่าผ่านทาง' ไม่ใช่ 'ข้อจำกัด'")
        else:
            print("  -> ลำเอียงไปหาที่ใกล้ตัว ภูมิศาสตร์มีผลต่อการตัดสินใจจริง")


def q7_regions_form(visits):
    head(7, "เกิด 'ภูมิภาค' ไหม — คนคนหนึ่งใช้ชีวิตอยู่ในวงกว้างแค่ไหน")
    spans = []
    for _cid, ps in visits.items():
        ps = list(ps)
        if len(ps) < 2:
            continue
        m = 0.0
        for i in range(len(ps)):
            d = TR.distances_from(ps[i])
            for j in range(i + 1, len(ps)):
                x = d.get(ps[j])
                if x and x > m:
                    m = x
        spans.append(m)
    if not spans:
        return
    spans.sort()
    print(f"  คนที่เคยย้ายที่: {len(spans)} คน")
    print(f"  ระยะไกลสุดระหว่างสองที่ที่คนคนหนึ่งเคยไป — เฉลี่ย {statistics.mean(spans):.1f} หน่วย "
          f"(มัธยฐาน {statistics.median(spans):.0f} | p90 {spans[int(len(spans)*0.9)]:.0f})")
    print("  (ยิ่งเลขนี้เล็กเทียบกับขนาดแผนที่ ยิ่งแปลว่าคนเกาะกลุ่มเป็นภูมิภาค ไม่ใช่กระจายทั่วโลก)")


if __name__ == "__main__":
    q1_graph_is_geometric()
    print(f"\nกำลังรันซิม {STEPS} เหตุการณ์ (พร้อมดัก emit)...")
    sim, trips, pairs, visits = run_sim_instrumented()
    print(f"เสร็จ — วันที่ {sim.day}, มีชีวิต {len(sim.alive_cids)} คน")
    q2_travel_time_matches_distance(trips)
    q3_time_actually_spent(sim)
    q4_world_boundaries(sim)
    q5_encounters_are_local(pairs)
    q6_destination_choice(trips)
    q7_regions_form(visits)
