"""python balance_run.py <repo> <seed> <variant> — balance run with exposure, unmet-demand decomposition and labour churn."""
import sys, io, contextlib, collections, json, os, argparse, hashlib
sys.path.insert(0, sys.argv[1]); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tiandao import sim as S, food as F, wages as W
import variant as V
from volunteer_metrics import VolunteerMetrics
ap = argparse.ArgumentParser()
ap.add_argument('repo'); ap.add_argument('seed', type=int); ap.add_argument('variant')
ap.add_argument('--years', type=float, default=50.0)
args = ap.parse_args()
if args.years <= 0: ap.error('--years must be positive')
seed, var = args.seed, args.variant
config = V.apply(var)
metrics = VolunteerMetrics(F._working)
metrics.install(S.Sim, F)
acc = collections.Counter()
last_release = {}
spot_release = {}
release_events = {}
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
        if was and sim.cast[cid].alive and not sim.cast[cid].fieldwork:
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
        for cid in sim.alive_cids:
            ch = sim.cast[cid]
            if F.eats(ch):
                acc["child_years" if ch.age(sim.day) < 14 else "adult_years"] += days / 365.0
            if F._working(ch, sim.day):
                acc["worker_days"] += days
                if ch.fieldwork:
                    acc["volunteer_days"] += days
    r = orig_tick(sim, days)
    return r
F.tick = tick

with contextlib.redirect_stdout(io.StringIO()):
    s = S.Sim(seed=seed)
    metrics.observe(s)
    start = dict(day=s.day, alive=len(s.alive_cids), rng_sha256=hashlib.sha256(repr(s.rng.getstate()).encode()).hexdigest())
    while s.day < args.years * 365:
        s.step()
        metrics.observe(s)
fs = s.food_stats
dead = [c for c in s.cast if not c.alive and c.death_cause == "อดอาหาร"]
kids = sum(1 for c in dead if c.death_day - c.born_day < 14 * 365)
T = sorted({w.tier for w in s.worlds})
labour = metrics.summary(s)
assert labour['productive_worker_days'] == acc['volunteer_days']
policy_spells = [sp for sp in labour['flag_spells'] if sp['end_reason'] == 'policy_release']
recruits = [sp for sp in labour['flag_spells'] if sp['entry_reason'] == 'recruitment']
for sp in labour['flag_spells']:
    if sp['entry_reason'] == 'recruitment' and sp['start'] - last_release.get(sp['cid'], -10 ** 9) <= 30:
        acc['recruited_next_round_after_release'] += 1
    if sp['end_reason'] == 'policy_release': last_release[sp['cid']] = sp['end']
elapsed_years = (s.day - start['day']) / 365.0
yr = lambda v: round(v / elapsed_years)
out = dict(seed=seed, config=config, start=start, end_day=s.day,
           requested_years=args.years, elapsed_years=elapsed_years, volunteer_metrics=labour,
           food_stats_raw=dict(fs),
           granary_sha256=hashlib.sha256(repr(sorted(s.granary.items())).encode()).hexdigest(),
           produced=yr(fs["produced"]), eaten=yr(fs["eaten"]), worker_days=yr(acc["worker_days"]),
           volunteer_days=yr(acc["volunteer_days"]), natural_spoil=yr(fs["spoiled"] - fs.get("overflow", 0.0)),
           overflow=yr(fs.get("overflow", 0.0)), kids=kids, adults=len(dead) - kids,
           child_years=round(acc["child_years"]), adult_years=round(acc["adult_years"]),
           releases=len(policy_spells), recruits=len(recruits), churn=acc["recruited_next_round_after_release"],
           release_events=sum(len(v) for v in release_events.values()),
           release_events_followed=sum(1 for v in release_events.values() for e in v if e["followed"]),
           released_people=sum(e["people"] for v in release_events.values() for e in v),
           released_people_followed=sum(e["people"] for v in release_events.values() for e in v if e["followed"]),
           short_rounds=acc["short_rounds"], short_after_release=acc["short_within_90d_of_release"],
           alive=len(s.alive_cids), wages=yr(s.wage_stats["paid"]),
           rng_sha256=hashlib.sha256(repr(s.rng.getstate()).encode()).hexdigest(),
           food_gap=abs(F.ledger_balance(fs) - F.total_held(s)), gold_gap=max(abs(W.gold_gap(s, t)) for t in T))
for g in ("child", "adult"):
    need, offered, bought, eaten = (acc[f"{g}_{k}"] for k in ("need", "offered", "bought", "eaten"))
    out[f"{g}_unmet"] = yr(need - eaten)
    out[f"{g}_unpaid"] = yr(offered - bought)       # granary had it for them, nobody paid (before relief / pack)
    out[f"{g}_short"] = yr(acc[f"{g}_short"])       # granary did not have it (before provisions)
print(json.dumps(out, ensure_ascii=False))
