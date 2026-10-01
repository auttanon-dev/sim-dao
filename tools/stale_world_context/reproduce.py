"""Bounded seed-21 replay against an explicit source snapshot (no config overrides)."""
import contextlib
import io
import json
import sys
from pathlib import Path

source, output = map(Path, sys.argv[1:3])
sys.path.insert(0, str(source.resolve()))
from tiandao import sim as S, wages as W

rows, contexts, moves = [], [], []
orig_resolve, orig_move = S.Sim.resolve, S.Sim.move_world
def resolve(self, ev, a, t, w, gap, rng):
    if 660 <= self.day <= 710:
        contexts.append(dict(day=self.day,seq_before=self.seq,kind=ev['kind'],actor=a.cid,
            actor_world=a.world_id,passed_world=w.wid,place=a.place,
            target=t.cid if t else None,target_world=t.world_id if t else None))
    return orig_resolve(self, ev, a, t, w, gap, rng)
def move(self, ch, new_wid):
    if 660 <= self.day <= 710:
        moves.append(dict(day=self.day,seq_before=self.seq,actor=ch.cid,old=ch.world_id,new=new_wid))
    return orig_move(self,ch,new_wid)
S.Sim.resolve, S.Sim.move_world = resolve, move
with contextlib.redirect_stdout(io.StringIO()):
    s=S.Sim(seed=21)
    tiers=sorted({w.tier for w in s.worlds})
    first=None
    largest={t:0 for t in tiers}
    while s.day<710:
        old_seq=s.seq
        e=s.step()
        gaps={t:W.gold_gap(s,t) for t in tiers}
        for t in tiers: largest[t]=max(largest[t],abs(gaps[t]))
        if first is None and any(abs(v)>1e-6 for v in gaps.values()):
            first=dict(day=s.day,seq=s.seq,gaps=gaps)
        if 660<=s.day<=710:
            rows.append(dict(day=s.day,seq_before=old_seq,seq=s.seq,gaps=gaps,
                event=dict(kind=e.kind,actor=e.actor,world=e.world_id,place=e.place,outcome=e.outcome) if e else None))
        if e is None: break
result=dict(source=str(source.resolve()),seed=21,until=s.day,first_gap=first,
    largest_abs_gap=largest,end_gaps=gaps,end_total_gap=sum(gaps.values()),moves=moves,contexts=contexts,steps=rows)
output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k not in ('steps','contexts')},ensure_ascii=True))
