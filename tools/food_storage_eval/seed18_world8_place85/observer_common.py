import collections, hashlib, json, pathlib, random, sys
from tiandao import food as F, config as C, seasons as SE
SPOT=(8,85)

def canonical(value,memo=None):
    if memo is None: memo={}
    if value is None or isinstance(value,(bool,int,float,str)): return value
    if isinstance(value,bytes): return ['bytes',value.hex()]
    if id(value) in memo: return ['ref',memo[id(value)][0]]
    # Retain references too: temporary slot dictionaries must not be reclaimed
    # and have their IDs reused during a traversal.
    memo[id(value)]=(len(memo),value)
    if isinstance(value,random.Random): return ['Random',canonical(value.getstate(),memo)]
    if isinstance(value,dict): return ['dict',[[canonical(k,memo),canonical(v,memo)] for k,v in sorted(value.items(),key=lambda kv:repr(kv[0]))]]
    if isinstance(value,(list,tuple,collections.deque)): return [type(value).__name__,[canonical(v,memo) for v in value]]
    if isinstance(value,(set,frozenset)): return [type(value).__name__,[canonical(v,memo) for v in sorted(value,key=repr)]]
    if hasattr(value,'__dict__'): return [type(value).__module__+'.'+type(value).__qualname__,canonical(vars(value),memo)]
    slots=[]
    for cls in type(value).__mro__:
        declared=getattr(cls,'__slots__',())
        slots.extend([declared] if isinstance(declared,str) else declared)
    if slots:
        fields={k:getattr(value,k) for k in sorted(set(slots)) if k not in ('__dict__','__weakref__') and hasattr(value,k)}
        return [type(value).__module__+'.'+type(value).__qualname__,canonical(fields,memo)]
    raise TypeError(f'Unsupported canonical state type: {type(value)}')

def digest(value):
    return hashlib.sha256(json.dumps(canonical(value),ensure_ascii=False,separators=(',',':')).encode()).hexdigest()

class Trace:
    def __init__(self):
        self.rows=[]; self.selected_year=None; self.last_food_day=None
        self.base_code=F._adapt_labour.__code__; self.capacity_code=F.BODY.work_capacity.__code__
        lines=pathlib.Path(F.__file__).read_text(encoding='utf-8').splitlines()
        for number,text in {597:'if not helpers',603:'if reserve >=',608:'if not limited',615:'if land_output_per_day(left)',632:'if output >= target'}.items():
            assert text in lines[number-1], 'Source line hooks incompatible'

    def install(self):
        original=F._adapt_labour
        def adapt(sim,eaters,workers,deficit,days,season,cap=None):
            before={cid for cid in sim.alive_cids if sim.cast[cid].fieldwork and F._spot(sim.cast[cid])==SPOT}
            record=dict(day=sim.day,interval_start=sim.day-days,days=days,season_mean=season,
                        endpoint_season=SE.season_of(sim.day)[0],alive_flagged_before=sorted(before),
                        physical_deficit=deficit.get(SPOT,0.0),local_stock=sim.granary.get(SPOT,0.0),
                        gates=[],candidate_checks=[],recruit_checks=[],capacity_by_cid={})
            frame_holder=[None]
            def tracer(frame,event,arg):
                if frame.f_code==self.base_code:
                    frame_holder[0]=frame
                    if event!='line': return tracer
                    loc=frame.f_locals
                    if loc.get('spot')!=SPOT: return tracer
                    line=frame.f_lineno
                    if line==597:
                        record.update(eligible_helpers=[c.cid for c in loc['helpers']],
                                      eligible_workers=[c.cid for c in loc['workers_at'][SPOT]],
                                      eligible_normal_workers=[c.cid for c in loc['workers_at'][SPOT] if not c.fieldwork])
                    elif line==598:
                        record['gates'].append('no_eligible_helpers' if not loc['helpers'] else 'shortage_block')
                    elif line==603:
                        record.update(policy_daily_need=loc['need'],local_limit=loc['limit'] if loc['limit']!=float('inf') else None,
                                      limited=loc['limited'],attributed_reserve=loc['reserve'],reserve_target=C.FOOD_DEST_STOCK_DAYS*loc['need'])
                    elif line==604:
                        if 'reserve_enough_release_all' not in record['gates']: record['gates'].append('reserve_enough_release_all')
                    elif line==605: record.setdefault('release_execution_order', []).append(loc['ch'].cid)
                    elif line==608: record['gates'].append('reserve_insufficient')
                    elif line==609: record['gates'].append('local_full_block_unlimited' if not loc['limited'] else 'local_full_block_below_cap')
                    elif line==612: record['gates'].append('local_full_pass')
                    elif line==615:
                        record['candidate_checks'].append(dict(cid=loc['ch'].cid,capacity=loc['n']-loc['left'],
                            capacity_before=loc['n'],capacity_after=loc['left'],
                            output_before_per_day=F.land_output_per_day(loc['n'])*season,
                            output_after_per_day=F.land_output_per_day(loc['left'])*season,
                            policy_daily_need=loc['need'],outcome=None))
                    elif line==616:
                        record['candidate_checks'][-1]['outcome']='output_after_below_need_block'
                        record['gates'].append('release_output_sufficiency_block')
                    elif line==617:
                        record['candidate_checks'][-1]['outcome']='policy_release'
                        record.setdefault('release_execution_order', []).append(loc['ch'].cid)
                    elif line==632:
                        record['recruit_checks'].append(dict(cid=loc['ch'].cid,capacity=loc['cap'],output=loc['output'],target=loc['target'],
                            marginal_output=F.land_output_per_day(loc['n']+loc['cap'])*season-loc['output'],outcome=None))
                    elif line==633:
                        record['recruit_checks'][-1]['outcome']='target_met' if loc['output']>=loc['target'] else 'marginal_gain_below_ration'
                    elif line==634: record['recruit_checks'][-1]['outcome']='policy_recruitment'
                    return tracer
                if frame.f_code==self.capacity_code:
                    if event=='return' and frame_holder[0] is not None and frame_holder[0].f_locals.get('spot')==SPOT:
                        record['capacity_by_cid'][frame.f_locals['character'].cid]=arg
                    return tracer
                return None
            previous=sys.gettrace()
            sys.settrace(tracer)
            try: result=original(sim,eaters,workers,deficit,days,season,cap)
            finally: sys.settrace(previous)
            after={cid for cid in sim.alive_cids if sim.cast[cid].fieldwork and F._spot(sim.cast[cid])==SPOT}
            record.update(alive_flagged_after=sorted(after),released=sorted(before-after),recruited=sorted(after-before))
            if record['candidate_checks']:
                helpers=record.get('eligible_helpers',[])
                record['candidate_order']=sorted(helpers,key=lambda cid:(record['capacity_by_cid'][cid],cid))
            else: record['candidate_order']=None
            self.rows.append(record)
            self.last_food_day=sim.day
            if self.selected_year is None and SE.season_of(sim.day)[0]=='ฤดูหนาว' and (before or after):
                self.selected_year=sim.day//365
            return result
        F._adapt_labour=adapt
