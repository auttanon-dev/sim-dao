"""ความตายเป็นธุรกรรมเดียว (แบบ §7.4) — `Sim.kill` เรียก `resolve` ที่นี่ทางเดียว

ขั้นเรียงตามลำดับที่มีผลต่อกันจริง (ลำดับเดิมของ Sim.kill ทุกขั้น — ผลของโลกเท่าเดิมทุกตัวเลข) ลำดับที่ห้ามสลับ:
- P3 เสบียงติดตัวเข้ายุ้งฉาง ก่อน P4 ผู้ปกครอง (เด็กที่ต้องย้ายดูข้าวใกล้ผู้ปกครองใหม่)
- P7 กระเป๋าครัวเรือน (HH.on_death) ก่อนแบ่งมรดก — คนสุดท้ายของครัวเรือนรวมกระเป๋าเข้าเงินของตัวเองก่อน (H4)
- P7 แบ่งมรดกใช้คู่ครองเป็นทายาท จึงต้องก่อนตัดคู่ครอง (หม้าย)
- P8 ผู้ฆ่าริบของ / ผนึกแดนลับ หลังแบ่งมรดก — ทองที่ไม่มีใครรับไปที่แดนลับได้แค่ส่วนที่เหลือ (B3a)
- P9 สืบตำแหน่งหลังผู้ฆ่าได้ของ (ผู้ฆ่าในสำนักเดียวกันชิงตำแหน่ง)
- P12 เกิดใหม่หลังทุกอย่างของความตายครบ

`check` (P11) คืนสิ่งที่ผิดหลังความตาย: ยังมีใครชี้ถึงผู้ตาย (คู่ครอง ผู้ปกครอง ครัวเรือน ตำแหน่ง) หรือทองรวมเปลี่ยนเกินทางที่บันทึก
เปิดเมื่อ `DEATH_CHECK` (เทสต์เปิดไว้) — ผิดแล้วหยุดทันที ไม่ปล่อยให้โลกเดินต่อด้วยสถานะที่พัง
"""
from . import config as C
from . import food as FOOD
from . import guardians as GUARD
from . import household as HH
from . import rules as R
from . import wages as WAGES
from .models import DeathRecord


def _gold(sim):
    tiers = sorted({w.tier for w in sim.worlds})
    total = sum(WAGES.total_gold(sim, t) for t in tiers)
    flows = sum(sum(v.values()) for v in getattr(sim, "gold_flows", {}).values())
    return total, flows


def resolve(sim, ch, cause, killer=None, natural=False):
    # P0 ด่าน: ตายแล้วไม่ตายซ้ำ เจ้าโกลาหลสลายไม่ใช่ตาย
    if not ch.alive:
        return
    before = _gold(sim) if C.DEATH_CHECK else None
    ch.alive = False
    ch.death_day = sim.day
    ch.death_cause = cause
    if ch.is_lord:
        _lord_dissolves(sim, ch, cause, killer)
        return
    # P1 บันทึก
    _record(sim, ch, cause, killer, natural)
    # P2 พลังคืนสู่ฟ้าที่เผ่าโกลาหลแย่งไป — ความตายทุกครั้งคือการนับถอยหลังสู่การกลับมาของเจ้าโกลาหล
    lord = sim.cast[sim.lord_cid] if sim.lord_cid is not None else None
    if lord is not None and lord.hidden and getattr(sim, "lord_seal", 0.0) <= 0.0:
        gain = C.LORD_POOL_PER_DEATH * (1.0 + C.LORD_POOL_PER_REALM * ch.realm)
        if not natural:
            gain *= C.LORD_POOL_VIOLENT_X
        sim.lord_pool = getattr(sim, "lord_pool", 0.0) + gain
    # P3 ร่างและเสบียงติดตัว
    if C.FOOD_ENABLED:
        FOOD.on_death(sim, ch)
    # P4 ผู้พึ่งพิง: เด็กในความดูแลได้ผู้ปกครองใหม่
    if C.GUARDIANS_ENABLED:
        GUARD.on_death(sim, ch)
    # P5 เลิกเป็นผู้กระทำ
    sim.alive_cids.discard(ch.cid)
    sim._alive_ver = getattr(sim, "_alive_ver", 0) + 1
    sim._world_counts_dirty = True
    if ch.cid in getattr(sim, "apex_blessings", {}):
        sim.apex_blessings.pop(ch.cid, None)
        sim.refresh_bloodline_buffs()
    w = sim.world(ch.world_id)
    w.n_alive -= 1
    if ch.realm == 0:
        w.n_mortal -= 1
    # P6 ปราณคืนสู่ฟ้า
    R.death_return(w, ch, natural)
    # P7 มรดก: กระเป๋าครัวเรือนก่อน แล้วทอง/ของ แล้วคู่ครองเป็นหม้าย
    HH.on_death(sim, ch)                     # คนสุดท้ายของครัวเรือน: กระเป๋าเข้าเงินของเขาก่อนแบ่งมรดก (ไม่มีทายาท: คลังตระกูล)
    sim.settle_estate(ch, items_to_heirs=killer is None)     # ผู้ฆ่าริบของ แต่ทองยังตกถึงทายาท
    mate = sim.cast[ch.spouse] if ch.spouse is not None and 0 <= ch.spouse < len(sim.cast) else None
    if mate is not None and mate.spouse == ch.cid:
        mate.spouse = None                   # เป็นหม้ายแล้วแต่งงานใหม่ได้ (ch.spouse ของผู้ตายคงไว้เป็นประวัติ)
    # P8 ผู้ฆ่า หรือแดนลับ
    if killer:
        _killer_takes(sim, ch, killer)
    elif ch.realm >= C.CACHE_MIN_REALM or any(sim.items[i].legend for i in ch.items):
        # สมบัติฟ้าดินที่มีชื่อไม่มีวันสูญหาย เจ้าของตายก็ถูกผนึกรอผู้มีวาสนาคนต่อไป
        sim.make_cache(ch, faked=False)
        WAGES.clear_gold(sim, ch, "sealed_in_cache")
    # P9 ตำแหน่งว่างมีคนรับช่วง แค้นต่อผู้ตายชำระไม่ได้
    sim.succeed(ch, killer)
    for cid in sim.alive_cids:               # เหมือน fade_grudges แต่ทันที
        sim.cast[cid].rivals.pop(ch.cid, None)
    # P10 ปิดกิจกรรมที่ค้าง
    ch.process, ch.building_dest = None, -1  # ไม่มีศพที่ยังเดินทาง ปิดด่าน หรือเดินในเมืองค้างอยู่
    sim.end_pregnancy(ch, "มารดาเสียชีวิต")
    # P11 ตรวจ
    if before is not None:
        problems = check(sim, ch, before)
        if problems:
            raise RuntimeError(f"ความตายของ {ch.cid} ({cause}) ทิ้งสถานะผิด: {problems}")
    # P12 ผู้ฝึกสายวัฏจักร: ร่างตายแล้ว แต่ดวงจิตไปเกิดใหม่ — หลังกระบวนการตายครบทุกอย่าง
    if ch.sentient and not ch.is_lord and sim._knows_cycle(ch):
        sim.reincarnate(ch)


def _lord_dissolves(sim, ch, cause, killer):
    """เจ้าโกลาหลไม่ตาย — สลาย (หรือสลายอยู่แล้วจึงฆ่าซ้ำไม่ได้) ย้ายมาจาก Sim.kill ไม่เปลี่ยนพฤติกรรม"""
    ch.alive = True
    ch.death_day = None
    ch.death_cause = ""
    if ch.hidden:
        # มันสลายไปแล้ว ฆ่าซ้ำไม่ได้ — วัดจริง 150 ปี: "ยุคล่ม" ของแดนที่มันสังกัดเรียก kill()
        # ใส่มันทั้งที่มันสลายอยู่ ซึ่งรีเซ็ตพลังที่มันสะสมมากลับเป็น 0 ให้โลกฟรีๆ
        return
    # เจ้าโกลาหล **ฆ่าได้** แต่ไม่มีอายุขัย — ที่ถูกฆ่าคือร่างที่ก่อขึ้น มันสลายกลับเป็นความโกลาหล
    # แล้วก่อร่างใหม่เมื่อสะสมพลังจากความตายทั่วจักรวาลได้ครบ ไม่ใช่เมื่อครบเวลาที่สุ่มไว้ล่วงหน้า
    ch.hidden = True
    ch.decay = 0.0
    ch.return_day = 0
    sim.lord_pool = 0.0
    cw = sim.world(sim.chaos_wid) if sim.chaos_wid is not None else sim.worlds[0]
    sim.emit(cw, "เจ้าโกลาหลสลาย", ch, killer, ["ทำลาย", "ความตาย"], "สลายเป็นโกลาหล",
             f"{ch.name}ถูกสังหารจนร่างสลายกลับเป็นความโกลาหล "
             f"จะก่อร่างใหม่ได้ต่อเมื่อสะสมพลังจากความตายทั่วจักรวาลจนครบ", 0,
             {"ผู้ลงมือ": killer.name if killer else "ไม่ปรากฏ",
              "เหตุ": cause,
              "สลายมาแล้ว": f"{ch.lord_returns} ครั้ง",
              "พลังที่ต้องสะสมใหม่": f"0/{C.LORD_POOL_TARGET:,.0f}"})
    # เทิร์นเดิมของมัน (หรือการจัดคิวปกติของผู้กระทำตอนนี้) ปลุกมันเอง — เพิ่มเทิร์นตรงนี้ทำให้คิวซ้ำทุกครั้งที่แพ้


def _record(sim, ch, cause, killer, natural):
    sim.death_seq = getattr(sim, "death_seq", 0) + 1
    sim.__dict__.setdefault("deaths", []).append(DeathRecord(
        sim.death_seq, ch.cid, sim.day, ch.world_id, ch.place if ch.place is not None else -1,
        cause, killer.cid if killer is not None else -1, bool(natural)))


def _killer_takes(sim, ch, killer):
    killer.kills += 1
    if ch.is_unique_beast:
        killer.cores += 10
        killer.mats += 5
    if not ch.hated():                       # ฆ่ามนุษย์มารถือเป็นการชอบธรรม ไม่เกิดหนี้ค้างคา
        R.add_debt(killer, "ฆ่า", ch.cid, ch.name, sim.day)
    for iid in ch.items:                     # ของตกอยู่กับคนฆ่า
        killer.items.append(iid)
    ch.items = []
    if ch.sentient and not ch.is_lord:
        sim.raise_corpse(killer, ch, sim.rng)
    sim.org_avenge(ch, killer)
    sim.kin_avenge(ch, killer)


def check(sim, ch, before):
    """สิ่งที่ผิดหลังความตายของ `ch` (ว่าง = ถูกทั้งหมด) — `before` = (ทองรวม, ผลรวมบัญชีสาเหตุ) ก่อนตาย"""
    problems = []
    cast = sim.cast
    for cid in sim.alive_cids:
        x = cast[cid]
        if x.spouse == ch.cid:
            problems.append(f"{cid} ยังมีผู้ตายเป็นคู่ครอง")
        if getattr(x, "guardian", -1) == ch.cid:
            problems.append(f"{cid} ยังมีผู้ตายเป็นผู้ปกครอง")
    if getattr(ch, "household", -1) >= 0 or any(ch.cid in hh.members for hh in getattr(sim, "households", {}).values()):
        problems.append("ผู้ตายยังอยู่ในครัวเรือน")
    for org in sim.orgs:
        if org.alive and sim.org_head(org) == ch.cid:
            problems.append(f"ผู้ตายยังเป็นผู้นำ{org.name}")
    for city in sim.cities:
        if city.get("ruler_cid") == ch.cid:
            problems.append(f"ผู้ตายยังเป็นเจ้าเมือง {city.get('id')}")
    total, flows = _gold(sim)
    if abs((total - before[0]) - (flows - before[1])) > 1e-6 * max(1.0, abs(total)):
        problems.append(f"ทองรวมเปลี่ยน {total - before[0]:+.6f} แต่บัญชีสาเหตุเปลี่ยน {flows - before[1]:+.6f}")
    return problems
