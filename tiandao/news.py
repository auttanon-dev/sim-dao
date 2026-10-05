# -*- coding: utf-8 -*-
"""ข่าวความตายเดินทางถึงคนไกลช้ากว่าคนที่เห็น (แบบ §7.4 ข้อ 8)

ความตายเปลี่ยนสถานะทางกายและสถาบันทันที (มรดก ผู้ปกครอง ตำแหน่ง — death.resolve) แต่การ "รู้" ต้องใช้เวลา:
คนที่ห่วงผู้ตาย (พ่อแม่ ลูก คู่ครอง และคนตระกูลหรือสำนักเดียวกันเมื่อถูกฆ่า) รู้เมื่อข่าวถึงตัว แล้วจึงเศร้า แค้น หรือเป็นหม้าย

- วันที่ข่าวถึงคิดครั้งเดียวตอนตายจากตำแหน่งของผู้รับตอนนั้น ไม่ใช้เลขสุ่ม (ไม่แตะ RNG):
  ที่เดียวกัน = รู้ทันที (เห็นเอง) · แดนเดียวกัน = วันเดินทางของปุถุชนบนกราฟสถานที่ (travel.shortest_path_days)
  · ต่างแดนหรือไปไม่ถึง = NEWS_CROSS_REALM_DAYS
- `sim.death_news`: คิวเรียงตามวันที่ถึง ส่งจากนาฬิกาโลก (Sim._world_tick) ผู้รับที่ตายก่อนข่าวถึงถูกทิ้ง
"""
import heapq

from . import config as C
from . import emotions as EMO
from . import travel as TR


def _queue(sim):
    return sim.__dict__.setdefault("death_news", [])


def delay_days(sim, dead, receiver) -> int:
    """กี่วันกว่าข่าวความตายของ `dead` จะถึง `receiver` — ตำแหน่งตอนตายทั้งคู่
    คนที่ซ่อนตัวหรือปิดด่านไม่ได้เห็น: รู้เมื่อออกมา (อย่างเร็วรอบโลกถัดไป) หรือเมื่อข่าวเดินทางถึง แล้วแต่อย่างไหนช้ากว่า"""
    wait = _travel_days(dead, receiver, sim.day)
    if receiver.hidden:
        wait = max(wait, receiver.seclude_until - sim.day, C.WORLD_TICK_DAYS)
    return wait


def _travel_days(dead, receiver, day) -> int:
    """วันเดินทางของผู้ส่งข่าวที่ออกวันตาย — ช้าลงตามฤดูของวันนั้น (แบบ §6.3)"""
    here, there = dead.place, receiver.place
    if receiver.world_id != dead.world_id or here is None or there is None or here < 0 or there < 0:
        return C.NEWS_CROSS_REALM_DAYS
    if here == there:
        return 0
    days = TR.shortest_path_days(here, there, 0, day=day)
    return C.NEWS_CROSS_REALM_DAYS if days is None else days


def _concerned(sim, dead, killer):
    """[(ผู้รับ, ความแค้นต่อผู้ฆ่า)] — ครอบครัวสายตรงแค้นเต็ม คนตระกูลหรือสำนักเดียวกันแค้นพอประมาณ (เฉพาะเมื่อถูกฆ่า)"""
    cast = sim.cast
    family = set(dead.parents or ()) | set(dead.children or ())
    if dead.spouse is not None:
        family.add(dead.spouse)
    out = {cid: C.GRUDGE_KIN for cid in family}
    if killer is not None:
        clan = dead.clan if dead.clan >= 0 and killer.clan != dead.clan else None
        org = dead.org if (dead.org is not None and killer.org != dead.org and sim.orgs[dead.org].alive) else None
        if clan is not None or org is not None:
            for cid in sim.alive_cids:
                m = cast[cid]
                if cid not in out and (m.clan == clan or (org is not None and m.org == org)):
                    out[cid] = C.GRUDGE_NEAR
    if killer is not None and killer.cid in out:
        out[killer.cid] = 0                  # ผู้ฆ่าที่เป็นญาติหรือคู่ครอง: รู้ทันที ไม่แค้นตัวเอง แต่ยังเป็นหม้าย
    return [(cast[cid], g) for cid, g in sorted(out.items())
            if 0 <= cid < len(cast) and cast[cid].alive and cid != dead.cid]


def on_death(sim, dead, killer=None) -> None:
    """ส่งข่าวออกจากที่ตาย — คนที่อยู่ที่เดียวกันรู้ทันที ที่เหลือเข้าคิวตามระยะทาง"""
    q = _queue(sim)
    stats = sim.__dict__.setdefault("news_stats", {})
    killer_cid = killer.cid if killer is not None else -1
    for m, grudge in _concerned(sim, dead, killer):
        wait = delay_days(sim, dead, m)
        item = (sim.day + wait, dead.cid, m.cid, killer_cid, grudge)
        if wait == 0:
            _deliver(sim, item)
        else:
            heapq.heappush(q, item)
            stats["queued"] = stats.get("queued", 0) + 1


def pending(sim, dead_cid, cid) -> bool:
    """ข่าวความตายของ `dead_cid` ยังเดินทางไปหา `cid` อยู่หรือไม่"""
    return any(item[1] == dead_cid and item[2] == cid for item in _queue(sim))


def tick(sim) -> None:
    """ส่งข่าวทุกชิ้นที่ถึงวันแล้ว"""
    q = _queue(sim)
    while q and q[0][0] <= sim.day:
        _deliver(sim, heapq.heappop(q))


def _deliver(sim, item) -> None:
    day, dead_cid, cid, killer_cid, grudge = item
    stats = sim.__dict__.setdefault("news_stats", {})
    m = sim.cast[cid]
    if not m.alive:
        stats["dropped"] = stats.get("dropped", 0) + 1
        return
    dead = sim.cast[dead_cid]
    stats["delivered"] = stats.get("delivered", 0) + 1
    # วันตายที่บันทึกไว้ในข่าวตอนส่ง (item) — ไม่อ่าน dead.death_day เพราะเจ้าโกลาหล "สลาย" แล้วถูกรีเซ็ตเป็น None (death._lord_dissolves)
    stats["delay_days"] = stats.get("delay_days", 0) + (sim.day - day)
    if grudge and 0 <= killer_cid < len(sim.cast) and killer_cid != cid and sim.cast[killer_cid].alive:
        m.rivals[killer_cid] = m.rivals.get(killer_cid, 0) + grudge
    if m.spouse == dead_cid:
        m.spouse = None                      # รู้ข่าวแล้วจึงเป็นหม้าย แต่งงานใหม่ได้
        stats["widowed"] = stats.get("widowed", 0) + 1
    EMO.react(m, "ข่าวความตาย", "สูญเสีย", ("ความตาย", "สูญเสีย"), day=sim.day, role="target")
