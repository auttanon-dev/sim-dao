"""Per-tier gold ledger scan: first world round where any tier stops closing, and the flows recorded then. python gold_tier_scan.py <repo> <seed>"""
import sys, io, contextlib, json
sys.path.insert(0, sys.argv[1])
from tiandao import sim as S, wages as W, food as F
seed = int(sys.argv[2])
first = None
prev_flows = None
orig = W.tick
def tick(sim, days):
    global first, prev_flows
    before = {k: dict(v) for k, v in getattr(sim, "gold_flows", {}).items()}
    gaps_before = {t: W.gold_gap(sim, t) for t in sorted({w.tier for w in sim.worlds})}
    r = orig(sim, days)
    if first is None:
        gaps = {t: W.gold_gap(sim, t) for t in gaps_before}
        bad = {t: g for t, g in gaps.items() if abs(g) > 1e-6}
        if bad:
            first = dict(day=sim.day, gap_after_wages_tick=bad, gap_before_wages_tick={t: gaps_before[t] for t in bad},
                         flows_changed={k: {t: round(v.get(t, 0) - before.get(k, {}).get(t, 0), 4) for t in v
                                            if abs(v.get(t, 0) - before.get(k, {}).get(t, 0)) > 1e-9}
                                        for k, v in getattr(sim, "gold_flows", {}).items()})
    return r
W.tick = tick
with contextlib.redirect_stdout(io.StringIO()):
    s = S.Sim(seed=seed)
    last_ok = 0
    while s.day < 50 * 365 and first is None:
        s.step()
        if first is None and all(abs(W.gold_gap(s, t)) < 1e-6 for t in {w.tier for w in s.worlds}):
            last_ok = s.day
print(json.dumps(dict(seed=seed, last_day_ledger_closed_between_steps=last_ok, first_divergence=first,
                      end_gaps={t: W.gold_gap(s, t) for t in sorted({w.tier for w in s.worlds})}), default=str))
