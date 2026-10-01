"""Seed-12 final-code trace: household-purse payments for chosen children, and phase-labelled granary flows for scarcity deaths.

python purse_trace.py <repo> <seed> <child cids comma> <spots wid:place;...> <from_day> <to_day>
"""
import sys, io, contextlib, collections, json
sys.path.insert(0, sys.argv[1])
from tiandao import sim as S, food as F, household as HH, wages as W, config as C, travel as TR
seed = int(sys.argv[2]); kids = {int(x) for x in sys.argv[3].split(",")}
spots = {tuple(int(v) for v in s.split(":")) for s in sys.argv[4].split(";")}
lo, hi = int(sys.argv[5]), int(sys.argv[6])
log = []
phase = ["idle"]
holder = [None]
flows = collections.defaultdict(lambda: collections.defaultdict(float))     # (day, spot) -> phase -> delta


def watched_spots(sim):
    out = set(spots)
    for (wid, place) in spots:
        out |= {(wid, p) for p, _h in TR.places_within(sim, place, C.FOOD_REACH_HOPS)}
    return out


class Granary(dict):
    def __setitem__(self, k, v):
        sim = holder[0]
        if sim is not None and lo <= sim.day <= hi and k in watch:
            flows[(sim.day, k)][phase[0]] += v - self.get(k, 0.0)
        super().__setitem__(k, v)


def phased(fn, name, after=None):
    def wrap(*a, **k):
        prev = phase[0]; phase[0] = name
        try:
            return fn(*a, **k)
        finally:
            phase[0] = after if after is not None else prev
    return wrap


orig_tick = F.tick
def tick(sim, days):
    if not isinstance(sim.granary, Granary):
        sim.granary = Granary(sim.granary)
    if lo <= sim.day <= hi:
        for s in watch:
            flows[(sim.day, s)]["opening"] = sim.granary.get(s, 0.0)
    phase[0] = "spoil"
    r = orig_tick(sim, days)
    phase[0] = "idle"
    if lo <= sim.day <= hi:
        for s in watch:
            flows[(sim.day, s)]["closing"] = sim.granary.get(s, 0.0)
    return r
F.tick = tick
HH.spoil = phased(HH.spoil, "spoil", after="produce")          # production follows household spoilage
HH.draw = phased(HH.draw, "kitchen_draw", after="local_take")   # then each place takes from its own granary
F._carry_in = phased(F._carry_in, "carry", after="feed")
F._stock_larders = phased(F._stock_larders, "kitchen_stock", after="after_feed")
F._starve = phased(F._starve, "dead_returned")
F._cap_granaries = phased(F._cap_granaries, "cap", after="after_cap")
_orig_adapt = F._adapt_labour
def adapt(sim, eaters_at, workers_at, deficit, days, season, cap=None):
    if lo <= sim.day <= hi:
        before = {sp: [(c.cid, c.profession, bool(c.fieldwork)) for c in workers_at.get(sp, ())] for sp in spots}
        idle = {sp: sum(1 for c in eaters_at.get(sp, ()) if not c.produces_food() and F._able_to_farm(c, sim.day)) for sp in spots}
    r = phased(_orig_adapt, "labour")(sim, eaters_at, workers_at, deficit, days, season, cap)
    if lo <= sim.day <= hi:
        for sp in spots:
            log.append(dict(ev="labour", day=sim.day, spot=list(sp), stock=round(sim.granary.get(sp, 0.0), 1),
                            cap=round((cap or {}).get(sp, -1), 1), need_90d=round(90 * sum(F.ration(c, sim.day) for c in eaters_at.get(sp, ())), 1),
                            deficit=round(deficit.get(sp, 0.0), 1), idle_adults=idle[sp],
                            workers=[(cid, prof, was, bool(sim.cast[cid].fieldwork)) for cid, prof, was in before[sp]]))
    return r
F._adapt_labour = adapt

orig_feed = F._feed_place
def feed_place(sim, spot, group, days, sources, fed):
    if lo <= sim.day <= hi:
        for ch in group:
            if ch.cid in kids:
                log.append(dict(ev="feed", day=sim.day, cid=ch.cid, spot=list(spot), supplied=round(sum(sources.values()), 2),
                                demand=round(sum(days * F.ration(c, sim.day) - fed.get(c.cid, 0.0) for c in group), 2),
                                group=len(group), kitchen=round(fed.get(ch.cid, 0.0), 2)))
    return orig_feed(sim, spot, group, days, sources, fed)
F._feed_place = feed_place

orig_pay_for = HH.pay_for
def pay_for(sim, child, cost):
    hh = HH.of(sim, child)
    tier = HH._tier(sim, child)
    before = dict(hh.purse) if hh else None
    reach = HH.in_reach(sim, hh, child) if hh else None
    paid = orig_pay_for(sim, child, cost)
    if lo <= sim.day <= hi and hh is not None and (child.cid in kids or any(m in kids for m in hh.members)):
        why = None
        if hh.home is None:
            why = "household has no home"
        elif not reach:
            wid, place = hh.home
            why = ("child in another realm" if child.world_id != wid else "child hidden" if child.hidden else
                   "child travelling" if child.travel_dest >= 0 else "child in jail" if getattr(child, "jail_until", 0) > sim.day else
                   f"child {child.place} beyond {C.FOOD_REACH_HOPS} hops of home {place}")
        elif before.get(tier, 0.0) <= 0:
            why = f"purse empty in child tier {tier} (other tiers {dict((k, round(v, 2)) for k, v in before.items() if k != tier)})"
        log.append(dict(ev="pay_for", day=sim.day, cid=child.cid, hid=hh.hid, home=hh.home, child_at=(child.world_id, child.place),
                        tier=tier, purse_before={k: round(v, 2) for k, v in before.items()}, cost=round(cost, 3),
                        paid=round(paid, 3), in_reach=reach, rejected=why))
    return paid
HH.pay_for = pay_for

orig_contribute = HH.contribute
def contribute(sim, ch, income):
    amt = orig_contribute(sim, ch, income)
    hh = HH.of(sim, ch)
    if lo <= sim.day <= hi and hh is not None and any(m in kids for m in hh.members):
        log.append(dict(ev="tithe", day=sim.day, cid=ch.cid, hid=hh.hid, income=round(income, 3), put_in=round(amt, 3),
                        tier=HH._tier(sim, ch), in_reach=HH.in_reach(sim, hh, ch)))
    return amt
HH.contribute = contribute

orig_buy = F._buy
def buy(sim, ch, amount, meal=True):
    if lo <= sim.day <= hi and ch.cid in kids and meal:
        payers = F._payers(sim, ch)
        log.append(dict(ev="buy_start", day=sim.day, cid=ch.cid, amount=round(amount, 2), price=F.price_at(sim, F._spot(ch)),
                        cost=round(amount * F.price_at(sim, F._spot(ch)), 3),
                        payers=[dict(cid=p.cid, gold=round(W.gold(sim, p), 3), same_spot=F._spot(p) == F._spot(ch),
                                     away=F._away(p, sim.day)) for p in payers],
                        guardian=getattr(ch, "guardian", -1), household=getattr(ch, "household", -1)))
    got, cost = orig_buy(sim, ch, amount, meal)
    if lo <= sim.day <= hi and ch.cid in kids and meal:
        log.append(dict(ev="buy_end", day=sim.day, cid=ch.cid, got=round(got, 3), paid=round(cost, 3)))
    return got, cost
F._buy = buy

orig_kill = S.Sim.kill
def kill(self, ch, cause, killer=None, natural=False):
    if ch.cid in kids:
        log.append(dict(ev="death", day=self.day, cid=ch.cid, cause=cause))
    return orig_kill(self, ch, cause, killer, natural)
S.Sim.kill = kill

watch = set()
with contextlib.redirect_stdout(io.StringIO()):
    s = S.Sim(seed=seed)
    holder[0] = s
    watch = watched_spots(s)
    while s.day <= hi + 30:
        s.step()
fl = [dict(day=d, spot=list(sp), **{k: round(v, 2) for k, v in ph.items()}) for (d, sp), ph in sorted(flows.items())
      if any(abs(v) > 1e-6 for v in ph.values())]
print(json.dumps(dict(log=log, flows=fl), ensure_ascii=False, default=str))
