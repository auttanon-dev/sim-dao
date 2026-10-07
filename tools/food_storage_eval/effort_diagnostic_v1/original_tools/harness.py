import ast
import collections
import contextlib
import copy
import inspect
import json
import random
import sys
import textwrap
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT.parents[1] / 'out/volunteer-schema2-95b07ea-18seeds-20261001/source'
sys.path.insert(0, str(SOURCE))
from tiandao import food as F, wages as W, config as C, childhood as CHILD
from tiandao.models import Character
from observer_common import digest

class CountingRandom(random.Random):
    def __init__(self, seed):
        self.draws = 0
        super().__init__(seed)
    def random(self):
        self.draws += 1
        return super().random()
    def getrandbits(self, k):
        self.draws += 1
        return super().getrandbits(k)

class MicroSim:
    def __init__(self, day, graph):
        self.day = day
        self.graph = graph
        self.cast = []
        self.alive_cids = set()
        self.worlds = [SimpleNamespace(wid=0, tier=0, place_key='fixture_graph')]
        self.granary = {}
        self.food_stats = F.new_stats()
        self.wage_stats = W.new_stats()
        self.farm_till = {}
        self.market_till = {}
        self.households = {}
        self.clan_treasury = {}
        self.settlement_treasury = {}
        self.gold_flows = {}
        self.rng = CountingRandom(18)
        self.events = []
    def world(self, wid):
        assert wid == 0
        return self.worlds[0]
    def hops_between(self, a, b):
        if a == b: return 0
        visited = {a}; queue = [(a,0)]
        for node,hops in queue:
            for neighbor in sorted(self.graph.get(node,())):
                if neighbor == b: return hops+1
                if neighbor not in visited:
                    visited.add(neighbor); queue.append((neighbor,hops+1))
        return 999
    def place_name(self, ch): return 'fixture/'+str(ch.place)
    def emit(self, *args): self.events.append(('food_emit', self.day))
    def kill(self, ch, cause, **kwargs):
        # Fixture death shell: real food return/loss; no estate/kin politics.
        F.on_death(self,ch)
        ch.alive=False; ch.death_day=self.day; ch.death_cause=cause
        self.alive_cids.discard(ch.cid)
        self.events.append(('death',ch.cid,cause,self.day))

def reach(sim, place):
    return sorted(((p,sim.hops_between(place,p)) for p in sim.graph if p!=place
                   and sim.hops_between(place,p)<=C.FOOD_REACH_HOPS), key=lambda v:(v[1],v[0]))

def person(sim, place, role, child=False, poor_hidden=False):
    age=10 if child else 30
    cid=len(sim.cast)
    ch=Character(cid=cid,name='fixture_'+str(cid),world_id=0,dao='',dao_tags=[],born_day=sim.day-age*365)
    ch.place=place; ch.profession='ชาวนา' if role=='normal' else 'บัณฑิต'
    ch.fieldwork=role=='volunteer'; ch.body_age=float(age)
    ch.alive=True; ch.realm=0; ch.sentient=True
    ch.is_spirit=False; ch.is_beast=False; ch.is_lord=False
    ch.hidden=poor_hidden; ch.travel_dest=-1; ch.jail_until=0; ch.seclude_until=0
    ch.food=0.0; ch.hunger_days=0.0; ch.food_fed=0.0; ch.food_missed=0.0
    ch.money={0:0.0 if poor_hidden else 1000.0}; ch.household=-1; ch.guardian=-1; ch.clan=-1
    ch.pregnancy=None
    for system in ('muscle','cardio','bone'): setattr(ch,system+'_adaptation',0.0)
    if child:
        ch.process=SimpleNamespace(kind='upbringing',payload={'routine':CHILD.CHORES},end_day=sim.day+365)
    sim.cast.append(ch); sim.alive_cids.add(cid)
    return ch

def build(case):
    graph={0:{1,2},1:{0},2:{0}} if case.get('network') else {0:set()}
    sim=MicroSim(case['start'],graph)
    if case.get('network'):
        person(sim,0,'normal')
        for _ in range(case['focal']): person(sim,1,'eater')
        for _ in range(case['competitors']): person(sim,2,'eater')
    else:
        for _ in range(case['normal']): person(sim,0,'normal')
        for _ in range(case['volunteers']): person(sim,0,'volunteer')
        for _ in range(case['eaters']): person(sim,0,'eater')
        if case.get('child'): person(sim,0,'child',child=True)
        if case.get('poor_hidden'): person(sim,0,'eater',poor_hidden=True)
    sim.granary={(0,0):float(case['stock'])}
    sim.food_stats['endowed']=float(case['stock'])
    sim.gold_flows={'fixture_initial_capital':{0:sum(ch.money[0] for ch in sim.cast)}}
    return sim

def shell_namespace():
    namespace=dict(vars(F))
    # Fixed-roster/location experimental constraint. Nothing produces extra pay
    # or activities. Real starvation threshold and feeding/relief remain intact.
    namespace['_adapt_labour']=lambda *args,**kwargs:None
    namespace['_respond']=lambda *args,**kwargs:None
    namespace['_seek_food']=lambda *args,**kwargs:None
    return namespace

def compile_tick(effort, transform):
    lines,first=inspect.getsourcelines(F.tick)
    tree=ast.parse(textwrap.dedent(''.join(lines)))
    ast.increment_lineno(tree,first-1)
    edits=0
    if transform:
        for node in ast.walk(tree):
            if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='adults' for t in node.targets):
                node.value=ast.copy_location(ast.BinOp(left=node.value,op=ast.Mult(),right=ast.Constant(value=effort)),node.value)
                edits+=1
        assert edits==1, 'Only adult production capacity may be changed'
    ast.fix_missing_locations(tree)
    namespace=shell_namespace()
    exec(compile(tree,F.__file__,'exec'),namespace)
    return namespace['tick'],tree,edits

def controls(sim):
    return [dict(cid=ch.cid,alive=ch.alive,profession=ch.profession,fieldwork=ch.fieldwork,
         place=ch.place,travel_dest=ch.travel_dest,working=F._working(ch,sim.day)) for ch in sim.cast]

class Collector:
    def __init__(self,sim,tick):
        self.sim=sim; self.tick_code=tick.__code__
        self.codes={getattr(F,n).__code__:n for n in ('_carry_in','_buy','_pay_farmers')}
        self.production={};self.stages={};self.asks={};self.allocation={};self.edges=[]
        self.physical={};self.unpaid=0.0;self.pay=[]
    def trace(self,frame,event,arg):
        sim=self.sim; loc=frame.f_locals;line=frame.f_lineno
        if frame.f_code==self.tick_code:
            if event=='line':
                phases={258:'before_production',271:'after_production',282:'after_local_reservation',
                        287:'after_transport',297:'before_farm_pay',299:'after_farm_pay',310:'before_cap',311:'after_cap'}
                if line in phases:self.stages[phases[line]]=copy.deepcopy(sim.granary)
                if line==263:
                    spot=loc['spot']
                    raw=sum(F.BODY.work_capacity(ch) for ch in loc['workers_at'].get(spot,()))
                    self.production[spot]=dict(raw_adult=raw,effective_adult=loc['adults'],child=loc['helpers_at'].get(spot,0),
                        labour=loc['labour'],made=loc['made'],season=loc['season'])
                if line==287:self.physical=copy.deepcopy(loc['deficit'])
            return self.trace
        name=self.codes.get(frame.f_code)
        if name=='_carry_in' and event=='line':
            if line==661:self.asks=copy.deepcopy(loc['asks'])
            elif line==664:
                self.allocation.setdefault(loc['src'],dict(available=sim.granary[loc['src']],wanted=loc['wanted'],scale=loc['scale']))
            elif line==668:self.edges.append(dict(source=loc['src'],dest=loc['dest'],sent=loc['sent'],arrived=loc['came'],loss=loc['sent']-loc['came'],hops=loc['hops']))
        elif name=='_buy' and event=='return' and loc.get('meal',True):
            self.unpaid+=max(0.0,loc['amount']-arg[0])
        elif name=='_pay_farmers' and event=='line' and line==487:
            self.pay.append(dict(cid=loc['ch'].cid,amount=loc['till']*loc['w']/loc['total'],weight=loc['w']))
        return self.trace if name else None

def encode_spots(values):
    return {str(k):v for k,v in sorted(values.items())}

def run(case,effort,transform=True):
    sim=build(case);records=[]
    for step,phase in enumerate(case['schedule']):
        value=effort if phase=='diagnostic' else 1.0
        sim.day=case['start']+(step+1)*case['days']
        if case.get('shock') and step==1:
            ch=sim.cast[0]
            if case['shock']=='death':sim.kill(ch,'scripted fixture producer death')
            else:ch.travel_dest=2
        if case.get('shock')=='travel' and step==3:sim.cast[0].travel_dest=-1
        before_controls=controls(sim); before_stats=copy.deepcopy(sim.food_stats)
        before_wages=copy.deepcopy(sim.wage_stats); opening=copy.deepcopy(sim.granary)
        before_rng=sim.rng.getstate(); before_draws=sim.rng.draws
        tick,tree,edits=compile_tick(value,transform)
        if not transform: tick=F.tick
        collector=Collector(sim,tick)
        previous=sys.gettrace()
        with patch.object(F,'_reach',reach), patch.object(F,'_adapt_labour',lambda *a,**k:None), \
             patch.object(F,'_respond',lambda *a,**k:None), patch.object(F,'_seek_food',lambda *a,**k:None):
            sys.settrace(collector.trace)
            try:tick(sim,case['days'])
            finally:sys.settrace(previous)
        assert sim.rng.getstate()==before_rng and sim.rng.draws==before_draws, 'Additional RNG draws'
        after_controls=controls(sim)
        for a,b in zip(before_controls,after_controls):
            assert a['profession']==b['profession'] and a['fieldwork']==b['fieldwork']
            assert a==b or (a['alive'] and not b['alive'] and sim.cast[a['cid']].death_cause=='อดอาหาร'), 'Unexpected eligibility change'
        for p in collector.production.values():
            assert abs(p['effective_adult']-p['raw_adult']*value)<1e-12
            expected=F.land_output_per_day(p['raw_adult']*value+p['child'])*case['days']*p['season']
            assert abs(expected-p['made'])<1e-9
        food_gap=abs(F.ledger_balance(sim.food_stats)-F.total_held(sim))
        gold_gap=abs(W.gold_gap(sim,0))
        demand_gap=abs(sim.food_stats['required']-sim.food_stats['eaten']-sim.food_stats['unmet'])
        assert food_gap<1e-7 and gold_gap<1e-7 and demand_gap<1e-7
        delta={k:sim.food_stats.get(k,0)-before_stats.get(k,0) for k in sim.food_stats}
        paid=sim.wage_stats['farm_paid']-before_wages['farm_paid']
        revenue=sim.wage_stats['food_bought']-before_wages['food_bought']
        record=dict(step=step+1,day=sim.day,phase=phase,applied_effort=value,days=case['days'],
            produced=delta['produced'],eaten=delta['eaten'],required=delta['required'],overflow=delta['overflow'],
            natural_spoil=delta['spoiled']-delta['overflow'],transport_loss=delta['carried_lost'],
            physical_shortfall=sum(max(0,v) for v in collector.physical.values()),
            physical_by_spot=encode_spots(collector.physical),unpaid=collector.unpaid,unmet=delta['unmet'],
            farm_revenue=revenue,farm_pay=paid,pay_by_cid=collector.pay,
            food_gap=food_gap,gold_gap=gold_gap,demand_gap=demand_gap,rng_draws=sim.rng.draws-before_draws,
            roster=before_controls,roster_after=after_controls,production=encode_spots(collector.production),opening_stock=encode_spots(opening),
            closing_stock=encode_spots(sim.granary),pack_food=sum(ch.food for ch in sim.cast),
            stages={phase:encode_spots(s) for phase,s in collector.stages.items()},
            asks={str(src):{str(dest):dict(request=amount,hops=hops) for dest,(amount,hops) in asks.items()} for src,asks in collector.asks.items()},
            allocation=encode_spots(collector.allocation),edges=collector.edges,
            full_state_sha256=digest(sim),rng_sha256=digest(sim.rng.getstate()),
            child_produced=delta.get('child_produced',0),worked_for_food=delta.get('worked_for_food',0),
            ledger_endowed_delta=delta['endowed'],starved=delta['starved'])
        assert abs(sum(p['amount'] for p in collector.pay)-paid)<1e-7
        records.append(record)
    return records
