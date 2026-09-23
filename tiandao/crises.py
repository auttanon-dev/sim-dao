"""Calendar-driven crises: prosperity attracts betrayal and chaos campaigns.

Each campaign has a warning, three separate waves, and a recovery interval.
No tick depends on the number of character turns. All state lives on Sim/World
so a save resumes the same campaign instead of rerolling or restarting it.
"""
from . import config as C


def _event(sim, world, kind, actor, outcome, text, **data):
    return sim.emit(world, kind, actor, None, ["ทำลาย", "ทรยศ"], outcome, text, 0, data)


def _betray(sim, world):
    people = [c for c in sim.living_in(world.wid)
              if c.alive and not c.hidden and not c.is_lord and not c.is_beast
              and not c.thrall and c.realm >= 1 and c.ambition >= 65
              and c.loyalty <= 45 and not getattr(c, "crisis_traitor", False)]
    if not people:
        return False
    traitor = sim.rng.choice(people)
    stolen = world.resource * C.CRISIS_BETRAYAL_LOSS
    world.resource -= stolen
    world.defense_array *= 0.5
    world.rift += C.CRISIS_BETRAYAL_RIFT
    traitor.crisis_traitor = True
    traitor.loyalty = 0
    traitor.moral = getattr(traitor, "moral", 0) - 30
    traitor.karmic_debt += 150
    old_org = traitor.org
    if old_org is not None and 0 <= old_org < len(sim.orgs):
        org = sim.orgs[old_org]
        for cid in list(org.members):
            ally = sim.cast[cid]
            if ally.alive and ally.cid != traitor.cid:
                ally.rivals[traitor.cid] = ally.rivals.get(traitor.cid, 0) + 5
        for attr in ("members", "core_disciples", "inner_disciples", "outer_disciples"):
            ids = getattr(org, attr)
            ids[:] = [cid for cid in ids if cid != traitor.cid]
        traitor.org = None
    world.crisis_betrayal_day = sim.day
    _event(sim, world, "ทรยศเปิดทางโกลาหล", traitor, "ทำลายค่ายกล",
           f"{traitor.name}หักหลัง{world.name} ขโมยทรัพยากรไปบูชารอยแยก "
           "ทำลายค่ายกลจากภายในและทิ้งศัตรูแค้นไว้เบื้องหลัง",
           resource_lost=round(stolen, 2), traitor_cid=traitor.cid, former_org=old_org)
    return True


def _mobilize(sim, human):
    donors = sorted((w for w in sim.worlds if w.kind == "mortal" and w.n_alive > 0
                     and getattr(w, "resource", 0) >= C.CRISIS_AID_MIN),
                    key=lambda w: (-w.resource, w.wid))[:C.CRISIS_AID_DONORS]
    funded = []
    for w in donors:
        cost = min(C.CRISIS_AID_COST, w.resource * 0.15)
        w.resource -= cost
        funded.append((w.wid, round(cost, 2)))
    total = sum(cost for _, cost in funded)
    human.defense_array = min(human.defense_max,
                              human.defense_array + total / C.CRISIS_AID_PER_DEFENSE)
    _event(sim, human, "ระดมทรัพยากรต้านมหาศึก", None,
           "ระดมสำเร็จ" if funded else "ขาดผู้สนับสนุน",
           f"{len(funded)} แดนออกทุน {total:,.0f} เพื่อเสริมค่ายกลรับมหาศึกโกลาหล",
           donors=funded, resource_spent=total, defense=human.defense_array)


def tick(sim):
    if not C.CRISIS_ENABLED:
        return
    # Lazy defaults allow old saves to participate without a migration reset.
    last = getattr(sim, "crisis_last_tick", sim.day)
    if not hasattr(sim, "crisis_last_tick"):
        sim.crisis_last_tick = last
    elapsed = sim.day - last
    if elapsed < C.CRISIS_TICK_DAYS:
        return
    sim.crisis_last_tick = sim.day
    human = sim.worlds[0]
    state = getattr(sim, "chaos_campaign", None)
    if state and sim.day >= state["next_day"]:
        _mobilize(sim, human)
        start = len(sim.log)
        for _ in range(C.CRISIS_ATTACKS_PER_WAVE):
            sim.chaos_invade(human, elapsed, sim.rng)
        raids = [e for e in sim.log[start:] if e.kind == "โกลาหลบุกโลกมนุษย์"]
        victories = sum(e.outcome == "ทำลายสำเร็จ" for e in raids)
        lost = human.resource * (1 - (1 - C.CRISIS_RAID_LOSS) ** victories)
        human.resource -= lost
        human.heaven *= (1 - C.CRISIS_HEAVEN_LOSS) ** victories
        state["waves"] += 1
        state["next_day"] = sim.day + C.CRISIS_WAVE_DAYS
        _event(sim, human, "มหาศึกโกลาหลถล่มโลกมนุษย์", None,
               "แนวรับแตก" if victories else "รักษาแนวรับ",
               f"คลื่นที่ {state['waves']} ของมหาศึกโกลาหล "
               f"บุก {len(raids)} ครั้ง ตีแตก {victories} แห่ง คลังมนุษย์สูญเสีย {lost:,.0f}",
               wave=state["waves"], raids=len(raids), breaches=victories, resource_lost=lost)
        if state["waves"] >= C.CRISIS_WAVES:
            sim.chaos_campaign = None
            sim.crisis_cooldown_until = sim.day + C.CRISIS_RECOVERY_DAYS
            sim.crisis_pressure = 0.0
            _event(sim, human, "สิ้นสุดมหาศึกโกลาหล", None, "เข้าสู่การฟื้นฟู",
                   "คลื่นมหาศึกสงบลง เหล่าแดนต้องฟื้นคลังและค่ายกลก่อนภัยครั้งใหม่",
                   recovery_until=sim.crisis_cooldown_until)
        return
    if state or sim.day < getattr(sim, "crisis_cooldown_until", 0):
        return

    years = elapsed / 365.0
    rich = [w for w in sim.worlds if w.kind == "mortal" and w.n_alive > 0
            and getattr(w, "resource", 0) >= C.REALM_RESOURCE_MAX * C.CRISIS_WEALTH_THRESHOLD]
    # Wealth increases the pace, but a long peace also attracts an invasion.
    pressure = getattr(sim, "crisis_pressure", 0.0)
    pressure += years * (C.CRISIS_PRESSURE_BASE + min(2.0, len(rich) / 30.0))
    for w in rich:
        if sim.day - getattr(w, "crisis_betrayal_day", -10**9) < C.CRISIS_BETRAYAL_COOLDOWN:
            continue
        if sim.rng.random() < 1 - (1 - C.CRISIS_BETRAYAL_YEAR_P) ** years:
            if _betray(sim, w):
                pressure += C.CRISIS_BETRAYAL_PRESSURE
    sim.crisis_pressure = pressure
    attackers = [c for c in sim.living_in(sim.chaos_wid) if c.alive and not c.hidden] if sim.chaos_wid is not None else []
    if pressure < C.CRISIS_PRESSURE_TRIGGER or not attackers or human.n_alive < C.CRISIS_MIN_POP:
        return
    human.rift += C.CRISIS_OPENING_RIFT
    sim.chaos_campaign = {"waves": 0, "next_day": sim.day + C.CRISIS_WARNING_DAYS}
    _event(sim, human, "ลางมหาศึกโกลาหล", None, "เตรียมรับศึก",
           "รอยแยกเหนือโลกมนุษย์ปริออก ขุนพลโกลาหลรวบรวมทัพ "
           "ข่าวศึกแพร่ถึงทุกแดน เหล่าผู้ครองแคว้นมีเวลาระดมทรัพยากร",
           pressure=pressure, rich_realms=len(rich), attack_day=sim.chaos_campaign["next_day"])
