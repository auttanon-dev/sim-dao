"""python trace_child.py <repo> <seed> <variant> — per-round history of every child who starves.

Per round and child (from the _feed_place / _buy / _account code path):
  need       days × ration
  home       eaten from the household kitchen first (HH.draw)
  offered    what the granaries could hand them: (need − home) × share, share = supplied / demand at that place
  bought     what was paid for (payers → household purse → clan hall → settlement treasuries in reach)
  pack       eaten from own provisions
  scarce     (need − home) − offered   food physically not there for them
  unpaid     offered − bought          food there, nobody paid
"""
import sys, io, contextlib, collections, json, os
sys.path.insert(0, sys.argv[1]); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tiandao import sim as S, food as F, wages as W, config as C, household as HH, travel as TR, seasons as SE
import variant as V
seed, var = int(sys.argv[2]), sys.argv[3]
config = V.apply(var)
hist = collections.defaultdict(lambda: collections.deque(maxlen=5))
cur = {}
tot = collections.Counter()


def gd_state(sim, ch):
    g = getattr(ch, "guardian", -1)
    if g is None or not (0 <= g < len(sim.cast)):
        return None
    gd = sim.cast[g]
    return dict(cid=g, alive=gd.alive, same_spot=gd.alive and F._spot(gd) == F._spot(ch), profession=gd.profession,
                volunteer=bool(gd.fieldwork), travelling=gd.travel_dest >= 0, hidden=bool(gd.hidden),
                gold=round(W.gold(sim, gd), 2), in_jail=getattr(gd, "jail_until", 0) > sim.day)


def funding(sim, ch):
    tier = W.tier_of(sim, ch)
    near = [ch.place] + [p for p, _h in TR.places_within(sim, ch.place, C.FOOD_REACH_HOPS)] if ch.place is not None and ch.place >= 0 else []
    hh = HH._table(sim).get(ch.household) if getattr(ch, "household", -1) is not None and ch.household >= 0 else None
    return dict(payers_gold=round(sum(max(0.0, W.gold(sim, p)) for p in F._payers(sim, ch)), 2),
                household_purse=round(sum(max(0.0, v) for v in getattr(hh, "purse", {}).values()), 2) if hh else None,
                household_larder=round(hh.larder, 1) if hh else None,
                clan_hall=round(getattr(sim, "clan_treasury", {}).get(getattr(ch, "clan", -1), {}).get(tier, 0.0), 1),
                towns_in_reach=round(sum(getattr(sim, "settlement_treasury", {}).get((ch.world_id, p), {}).get(tier, 0.0) for p in near), 1),
                price=round(F.price_at(sim, F._spot(ch)), 3))


orig_feed = F._feed_place
def feed_place(sim, spot, group, days, sources, fed):
    supplied = sum(sources.values())
    demand = sum(days * F.ration(ch, sim.day) - fed.get(ch.cid, 0.0) for ch in group)
    share = min(1.0, supplied / demand) if demand > 0 else 1.0
    stores = F.serving_granaries(sim, spot) if hasattr(F, "serving_granaries") else [spot]
    for ch in group:
        if ch.age(sim.day) < 14:
            cur[ch.cid] = dict(day=sim.day, season=SE.season_of(sim.day)[0], spot=list(spot), home=round(fed.get(ch.cid, 0.0), 2),
                               share=round(share, 3), local_stock=round(sim.granary.get(spot, 0.0) + supplied, 1),
                               reach_stock=round(sum(sim.granary.get(s, 0.0) for s in stores), 1),
                               funding=funding(sim, ch), guardian=gd_state(sim, ch), travelling=False)
    return orig_feed(sim, spot, group, days, sources, fed)
F._feed_place = feed_place

orig_buy = F._buy
def buy(sim, ch, amount, meal=True):
    got, cost = orig_buy(sim, ch, amount, meal)
    if meal and ch.cid in cur:
        cur[ch.cid]["offered"] = round(amount, 2)
        cur[ch.cid]["bought"] = round(got, 2)
    return got, cost
F._buy = buy

orig_account = F._account
def account(sim, ch, need, eaten, days):
    r = orig_account(sim, ch, need, eaten, days)
    grp = "child" if ch.age(sim.day) < 14 else "adult"
    rec = cur.pop(ch.cid, None)
    if grp == "child":
        if rec is None:        # away: eats only from provisions
            rec = dict(day=sim.day, season=SE.season_of(sim.day)[0], spot=list(F._spot(ch)), home=0.0, offered=0.0, bought=0.0,
                       travelling=True, guardian=gd_state(sim, ch), funding=funding(sim, ch))
        rec.update(need=round(need, 2), eaten=round(eaten, 2), hunger_days=round(ch.hunger_days, 1), pack_left=round(ch.food or 0.0, 1))
        rec.setdefault("offered", 0.0); rec.setdefault("bought", 0.0)
        rec["scarce"] = round(max(0.0, need - rec["home"] - rec["offered"]), 2)
        rec["unpaid"] = round(max(0.0, rec["offered"] - rec["bought"]), 2)
        hist[ch.cid].append(rec)
        tot["child_need"] += need; tot["child_unmet"] += need - eaten
        tot["child_scarce"] += rec["scarce"] if not rec["travelling"] else 0.0
        tot["child_unpaid"] += rec["unpaid"]
        tot["child_away_need"] += need if rec["travelling"] else 0.0
    return r
F._account = account

deaths = []
orig_starve = F._starve
def starve(sim, ch):
    if ch.age(sim.day) < 14:
        rounds = list(hist[ch.cid])
        scarce = sum(r["scarce"] for r in rounds); unpaid = sum(r["unpaid"] for r in rounds)
        away = any(r["travelling"] for r in rounds)
        kind = "away_on_provisions" if away and not unpaid and not scarce else ("unable_to_pay" if unpaid >= scarce else "scarcity")
        deaths.append(dict(cid=ch.cid, age=ch.age(sim.day), day=sim.day, spot=list(F._spot(ch)), kind=kind,
                           scarce=round(scarce, 1), unpaid=round(unpaid, 1),
                           parents_alive=[bool(0 <= p < len(sim.cast) and sim.cast[p].alive) for p in (ch.parents or ())],
                           rounds=rounds))
    return orig_starve(sim, ch)
F._starve = starve

with contextlib.redirect_stdout(io.StringIO()):
    s = S.Sim(seed=seed)
    while s.day < 50 * 365:
        s.step()
print(json.dumps(dict(seed=seed, config=config, totals={k: round(v) for k, v in tot.items()},
                      by_kind=collections.Counter(d["kind"] for d in deaths), deaths=deaths), ensure_ascii=False))
