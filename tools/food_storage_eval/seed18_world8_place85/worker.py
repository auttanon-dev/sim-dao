import argparse,contextlib,io,json,pathlib,sys
ap=argparse.ArgumentParser();ap.add_argument('source',type=pathlib.Path);ap.add_argument('--mode',choices=['observe','control'],required=True)
ap.add_argument('--progress',type=pathlib.Path);args=ap.parse_args()
sys.path.insert(0,str(args.source));sys.path.insert(0,str(args.source/'tools/food_storage_eval'))
from tiandao import sim as S,food as F,wages as W
from volunteer_metrics import VolunteerMetrics
from observer_common import digest
from tick_observer import TickObserver
from types import SimpleNamespace
from unittest.mock import patch
fixture=SimpleNamespace(day=10980,cast=[SimpleNamespace(cid=i) for i in range(4000)])
probe=TickObserver()
with patch('tick_observer.person',lambda sim,ch: {'cid':ch.cid}):probe.boundary(fixture,'fixture')
assert len(probe.boundaries[0]['people'])==len(probe.watch)
assert probe.boundaries[0]['people'][1081]['cid']==1081
metrics=None;observer=None
if args.mode=='observe':
    observer=TickObserver(10980) # freeze original code objects before wrappers
    metrics=VolunteerMetrics(F._working);metrics.install(S.Sim,F);observer.install()
anchor=None;boundaries={}
with contextlib.redirect_stdout(io.StringIO()):
    sim=S.Sim(seed=18)
    if metrics:metrics.observe(sim)
    next_log=365
    while sim.day<11010:
        sim.step()
        if metrics:metrics.observe(sim)
        if sim.day in (10920,10950,10980,11010) and str(sim.day) not in boundaries:
            boundaries[str(sim.day)]=dict(day=sim.day,world_state_sha256=digest(sim),rng_sha256=digest(sim.rng.getstate()),granary_sha256=digest(sim.granary),state_key_sha256={k:digest(v) for k,v in sorted(vars(sim).items())},food_stats_raw=dict(sim.food_stats))
            if observer:observer.boundary(sim,'step_return')
        if sim.day==10950 and anchor is None:
            anchor=dict(day=sim.day,world_state_sha256=digest(sim),rng_sha256=digest(sim.rng.getstate()),
                        granary_sha256=digest(sim.granary),food_stats_raw=dict(sim.food_stats))
        if args.progress and sim.day>=next_log:
            with args.progress.open('a',encoding='utf-8') as f:f.write(json.dumps(dict(mode=args.mode,day=sim.day))+'\n')
            next_log+=365
assert sim.day==11010 and anchor is not None
fs=sim.food_stats
output=dict(seed=18,spot=[8,85],mode=args.mode,end_day=sim.day,anchor_10950=anchor,boundary_hashes=boundaries,
            world_state_sha256=digest(sim),state_key_sha256={k:digest(v) for k,v in sorted(vars(sim).items())},
            rng_sha256=digest(sim.rng.getstate()),granary_sha256=digest(sim.granary),food_stats_raw=dict(fs),
            alive_flagged=sum(sim.cast[cid].fieldwork for cid in sim.alive_cids),
            alive_productive=sum(sim.cast[cid].fieldwork and F._working(sim.cast[cid],sim.day) for cid in sim.alive_cids),
            food_gap=abs(F.ledger_balance(fs)-F.total_held(sim)),
            gold_gap=max(abs(W.gold_gap(sim,t)) for t in {w.tier for w in sim.worlds}),
            demand_closure_gap=abs(fs['required']-fs['eaten']-fs['unmet']))
if metrics:
    assert len(observer.records)==3 and len(observer.gate.rows)==3
    assert len(observer.boundaries)==8 and all(len(b['people'])==len(observer.watch) for b in observer.boundaries)
    output.update(schema_version=2,volunteer_metrics=metrics.summary(sim),ticks=observer.records,people_boundaries=observer.boundaries)
print(json.dumps(output,ensure_ascii=False))
