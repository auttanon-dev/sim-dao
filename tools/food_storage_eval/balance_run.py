"""python balance_run.py <repo> <seed> <variant> — balance run with exposure, unmet-demand decomposition and labour churn."""
import sys, io, contextlib, collections, json, os
sys.path.insert(0, sys.argv[1]); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tiandao import sim as S, food as F, wages as W
import variant as V
seed, var = int(sys.argv[2]), sys.argv[3]
config = V.apply(var)
acc = collections.Counter()
last_release = {}
spot_release = {}
release_events = {}
spells, open_spell = [], {}
orig_adapt = F._adapt_labour
def adapt(sim, eaters_at, workers_at, deficit, days, season, cap=None):
    for spot, amt in deficit.items():
        if amt > 1e-9:
            for ev in release_events.get(spot, ()):
                if 0 < sim.day - ev["day"] <= 90 and not ev["followed"]:
                    ev["followed"] = True
            acc["short_rounds"] += 1
            if sim.day - spot_release.get(spot, -10 ** 9) <= 90:
                acc["short_within_90d_of_release"] += 1
    before = {ch.cid: (spot, ch.fieldwork) for spot, grp in workers_at.items() for ch in grp}
    r = orig_adapt(sim, eaters_at, workers_at, deficit, days, season, cap) if cap is not None else orig_adapt(sim, eaters_at, workers_at, deficit, days, season)
    released = collections.Counter()
    for cid, (spot, was) in before.items():
        if was and not sim.cast[cid].fieldwork:
            spot_release[spot] = sim.day
            released[spot] += 1
    for spot, k in released.items():
        release_events.setdefault(spot, []).append(dict(day=sim.day, people=k, followed=False))
    return r
F._adapt_labour = adapt

orig_buy = F._buy
def buy(sim, ch, amount, meal=True):
    got, cost = orig_buy(sim, ch, amount, meal)
    if meal:
        grp = "child" if ch.age(sim.day) < 14 else "adult"
        acc[f"{grp}_offered"] += amount          # food the granaries could hand this person this round
        acc[f"{grp}_bought"] += got
    return got, cost
F._buy = buy

orig_feed = F._feed_place
def feed_place(sim, spot, group, days, sources, fed):
    supplied = sum(sources.values())
    wants = [days * F.ration(ch, sim.day) - fed.get(ch.cid, 0.0) for ch in group]
    demand = sum(wants)
    share = min(1.0, supplied / demand) if demand > 0 else 1.0
    for ch, n in zip(group, wants):
        grp = "child" if ch.age(sim.day) < 14 else "adult"
        acc[f"{grp}_short"] += n * (1.0 - share)      # food physically not there for them at this place this round
    return orig_feed(sim, spot, group, days, sources, fed)
F._feed_place = feed_place

orig_account = F._account
def account(sim, ch, need, eaten, days):
    grp = "child" if ch.age(sim.day) < 14 else "adult"
    acc[f"{grp}_need"] += need
    acc[f"{grp}_eaten"] += eaten
    return orig_account(sim, ch, need, eaten, days)
F._account = account

orig_tick = F.tick
def tick(sim, days):
    if days > 0:
        before = {cid: sim.cast[cid].fieldwork for cid in sim.alive_cids}
        for cid in sim.alive_cids:
            ch = sim.cast[cid]
            if F.eats(ch):
                acc["child_years" if ch.age(sim.day) < 14 else "adult_years"] += days / 365.0
            if F._working(ch, sim.day):
                acc["worker_days"] += days
                if ch.fieldwork:
                    acc["volunteer_days"] += days
    r = orig_tick(sim, days)
    if days > 0:
        for cid, was in before.items():
            ch = sim.cast[cid]
            if was and not ch.fieldwork:
                last_release[cid] = sim.day
                if cid in open_spell:
                    spells.append(sim.day - open_spell.pop(cid))
                acc["releases"] += 1
            elif not was and ch.fieldwork:
                acc["recruits"] += 1
                open_spell[cid] = sim.day
                if sim.day - last_release.get(cid, -10 ** 9) <= 30:
                    acc["recruited_next_round_after_release"] += 1
    return r
F.tick = tick

with contextlib.redirect_stdout(io.StringIO()):
    s = S.Sim(seed=seed)
    start = dict(day=s.day, alive=len(s.alive_cids), rng=hash(str(s.rng.getstate())))
    while s.day < 50 * 365:
        s.step()
fs = s.food_stats
dead = [c for c in s.cast if not c.alive and c.death_cause == "อดอาหาร"]
kids = sum(1 for c in dead if c.death_day - c.born_day < 14 * 365)
T = sorted({w.tier for w in s.worlds})
yr = lambda v: round(v / 50)
out = dict(seed=seed, config=config, start=start, end_day=s.day,
           produced=yr(fs["produced"]), eaten=yr(fs["eaten"]), worker_days=yr(acc["worker_days"]),
           volunteer_days=yr(acc["volunteer_days"]), natural_spoil=yr(fs["spoiled"] - fs.get("overflow", 0.0)),
           overflow=yr(fs.get("overflow", 0.0)), kids=kids, adults=len(dead) - kids,
           child_years=round(acc["child_years"]), adult_years=round(acc["adult_years"]),
           releases=acc["releases"], recruits=acc["recruits"], churn=acc["recruited_next_round_after_release"],
           release_events=sum(len(v) for v in release_events.values()),
           release_events_followed=sum(1 for v in release_events.values() for e in v if e["followed"]),
           released_people=sum(e["people"] for v in release_events.values() for e in v),
           released_people_followed=sum(e["people"] for v in release_events.values() for e in v if e["followed"]),
           short_rounds=acc["short_rounds"], short_after_release=acc["short_within_90d_of_release"],
           spells_done=len(spells), spell_median=sorted(spells)[len(spells) // 2] if spells else 0,
           spell_p90=sorted(spells)[int(0.9 * len(spells))] if spells else 0, spell_max=max(spells or [0]),
           ongoing=len(open_spell), ongoing_median=sorted(s.day - d for d in open_spell.values())[len(open_spell) // 2] if open_spell else 0,
           alive=len(s.alive_cids), wages=yr(s.wage_stats["paid"]),
           food_gap=abs(F.ledger_balance(fs) - F.total_held(s)), gold_gap=max(abs(W.gold_gap(s, t)) for t in T))
for g in ("child", "adult"):
    need, offered, bought, eaten = (acc[f"{g}_{k}"] for k in ("need", "offered", "bought", "eaten"))
    out[f"{g}_unmet"] = yr(need - eaten)
    out[f"{g}_unpaid"] = yr(offered - bought)       # granary had it for them, nobody paid (before relief / pack)
    out[f"{g}_short"] = yr(acc[f"{g}_short"])       # granary did not have it (before provisions)
print(json.dumps(out, ensure_ascii=False))
