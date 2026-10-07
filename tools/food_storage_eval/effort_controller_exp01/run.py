"""Single-shot EXP-01 miniature batch; original frozen kernel, external state."""
import ast
import copy
import hashlib
import inspect
import json
import math
import os
import sys
import textwrap
import time
import traceback
import types
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent
WORK = ROOT.parents[2]
ARCHIVE = WORK / 'tools/food_storage_eval/effort_diagnostic_v1'
SOURCE = WORK / 'out/volunteer-schema2-95b07ea-18seeds-20261001/source'
OUT = WORK / 'out/effort-controller-EXP-01-20261002'
START_UTC = '2026-10-02T12:17:46+00:00'
DEADLINE = datetime.fromisoformat(START_UTC).timestamp() + 600
MAX_BYTES = 10 * 1024 * 1024
sys.dont_write_bytecode = True
sys.path.insert(0, str(SOURCE))
from controller import PROFILE, EPS, Book, decide, committed, feedback

def check_budget():
    if time.time() >= DEADLINE:
        raise TimeoutError('Authorized total ten-minute budget exhausted')
    if OUT.exists() and sum(p.stat().st_size for p in OUT.rglob('*') if p.is_file()) > MAX_BYTES:
        raise RuntimeError('Authorized evidence limit exceeded')

def save(name, value):
    data = (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n').encode('utf-8')
    with (OUT/name).open('wb') as f:
        f.write(data); f.flush(); os.fsync(f.fileno())

def append(name, value):
    check_budget()
    data = (json.dumps(value, ensure_ascii=False, separators=(',',':'), allow_nan=False)+'\n').encode('utf-8')
    used = sum(p.stat().st_size for p in OUT.rglob('*') if p.is_file())
    if used + len(data) > MAX_BYTES - 300000:
        raise RuntimeError('Evidence budget reserved for closeout would be exceeded')
    with (OUT/name).open('ab') as f:
        f.write(data); f.flush(); os.fsync(f.fileno())

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def inventories():
    return dict(source={str(p.relative_to(SOURCE)):sha(p) for p in SOURCE.rglob('*') if p.is_file()},
                instrumentation={p.name:sha(p) for p in ROOT.glob('*.py')},
                archived_tools={p.name:sha(p) for p in (ARCHIVE/'original_tools').glob('*.py')})

def _restore_counting(cls, state, draws):
    rng = cls(0)
    rng.setstate(state)
    rng.draws = draws
    return rng

def load_shell():
    # Only path relocation in a separately named in-memory module. Archive unchanged.
    sys.path.insert(0, str(ARCHIVE/'original_tools'))
    original = ARCHIVE/'original_tools/harness.py'
    code = original.read_text(encoding='utf-8')
    old = "SOURCE = ROOT.parents[1] / 'out/volunteer-schema2-95b07ea-18seeds-20261001/source'"
    assert code.count(old) == 1
    code = code.replace(old, 'SOURCE = Path('+repr(str(SOURCE))+')')
    module = types.ModuleType('exp01_shell')
    module.__file__ = str(original)
    sys.modules[module.__name__] = module
    exec(compile(code, str(original), 'exec'), module.__dict__)
    # random.Random reduces to (cls, (), state), so deepcopy/pickle call CountingRandom() without the
    # required seed (EXP-01 first run failed here). Reduce with the state and draw count instead; the
    # archived harness file stays byte-identical.
    module.CountingRandom.__reduce__ = lambda self: (_restore_counting, (type(self), self.getstate(), self.draws))
    fixture_code = (ARCHIVE/'original_tools/fixtures.py').read_text(encoding='utf-8')
    data = {}; exec(compile(fixture_code, 'archived-fixtures', 'exec'), data)
    return module, data['CASES']

def compile_kernel(h, commands, tail=False, hooks=None):
    lines, first = inspect.getsourcelines(h.F.tick)
    tree = ast.parse(textwrap.dedent(''.join(lines)))
    ast.increment_lineno(tree, first-1)
    fn = tree.body[0]
    if tail:
        index = next(i for i,n in enumerate(fn.body) if isinstance(n,ast.Assign)
                     and any(isinstance(t,ast.Name) and t.id=='season' for t in n.targets))
        fn.body = ast.parse('day=sim.day\nstats=sim.food_stats').body + fn.body[index:]
        for arg in ('eaters_at','workers_at','helpers_at','away'):
            fn.args.args.append(ast.arg(arg=arg))
    edits = 0
    for node in ast.walk(fn):
        if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='adults' for t in node.targets):
            factor = ast.parse('_commands.get(spot,1.0)', mode='eval').body
            node.value = ast.copy_location(ast.BinOp(node.value,ast.Mult(),factor),node.value)
            edits += 1
    assert edits == 1
    ast.fix_missing_locations(tree)
    ns = h.shell_namespace(); ns['_commands'] = commands; ns.update(hooks or {})
    exec(compile(tree,h.F.__file__,'exec'),ns)
    return ns['tick']

def patches(h):
    import contextlib
    stack = contextlib.ExitStack()
    for name,value in [('_reach',h.reach),('_adapt_labour',lambda *a,**k:None),
                       ('_respond',lambda *a,**k:None),('_seek_food',lambda *a,**k:None)]:
        stack.enter_context(patch.object(h.F,name,value))
    return stack

def key_hashes(h,sim): return {k:h.digest(v) for k,v in sorted(vars(sim).items())}
def projected(h, sim, loc, effort):
    # Clone CURRENT snapshots together so roster references remain identical.
    clone,eaters,workers,helpers,away = copy.deepcopy((sim,loc['eaters_at'],
                loc['workers_at'],loc['helpers_at'],loc['away']))
    commands = {s:effort for s in set(workers)|set(helpers)}
    before = dict(clone.food_stats); wages = dict(clone.wage_stats)
    rng = clone.rng.getstate(); draws = clone.rng.draws
    # Explicit wrappers work even when called inside a Python trace callback,
    # where recursive sys.settrace is suppressed. No reliance on missing hooks.
    unpaid=[0.]; pay=[]
    original_buy=h.F._buy; original_pay=h.F._pay_farmers
    def buy(s,c,amount,meal=True):
        result=original_buy(s,c,amount,meal=meal)
        if meal:unpaid[0]+=max(0.,amount-result[0])
        return result
    def farmers(s,w):
        for spot,till in sorted(s.farm_till.items()):
            group=w.get(spot)
            if till<=h.F._EPS or not group:continue
            weights=[h.F.BODY.work_capacity(c) for c in group]
            total=sum(weights)
            if total>0:
                pay.extend(dict(cid=c.cid,amount=till*n/total,weight=n) for c,n in zip(group,weights))
        return original_pay(s,w)
    tick = compile_kernel(h,commands,tail=True,hooks={'_pay_farmers':farmers})
    physical=0.
    for spot,group in eaters.items():
        output=h.F.land_output_per_day(sum(h.F.BODY.work_capacity(c) for c in workers.get(spot,()))*effort+
                    helpers.get(spot,0.))*loc['days']*h.F.season_mean(sim.day-loc['days'],loc['days'])
        physical+=max(0.,sum(h.F.ration(c,sim.day)*loc['days'] for c in group)-clone.granary.get(spot,0.)-output)
    with patches(h),patch.object(h.F,'_buy',buy):
        tick(clone,loc['days'],eaters,workers,helpers,away)
    assert clone.rng.getstate()==rng and clone.rng.draws==draws
    delta = {k:clone.food_stats.get(k,0)-before.get(k,0) for k in clone.food_stats}
    assert abs(sum(p['amount'] for p in pay)-(clone.wage_stats['farm_paid']-wages['farm_paid']))<1e-7
    return dict(clone=clone, stats=delta, physical=physical,
                unpaid=unpaid[0], pay=pay,
                revenue=clone.wage_stats['food_bought']-wages['food_bought'])

def observable_summary(h,sim):
    return dict(people=[dict(cid=c.cid,alive=c.alive,food=c.food,hunger=c.hunger_days,
                fed=c.food_fed,missed=c.food_missed,money=dict(c.money),
                profession=c.profession,fieldwork=c.fieldwork,travel=c.travel_dest)
                for c in sim.cast], stocks=h.encode_spots(sim.granary),
                tills=h.encode_spots(sim.farm_till), households=h.digest(sim.households))

def preserved(h,full,reduced):
    # Overflow/produced may differ. All realized consumer/cash/stock outcomes preserved.
    a=observable_summary(h,full['clone']); b=observable_summary(h,reduced['clone'])
    def near(x,y):
        if isinstance(x,(int,float)) and not isinstance(x,bool):
            return isinstance(y,(int,float)) and abs(x-y)<=EPS
        if isinstance(x,dict): return x.keys()==y.keys() and all(near(x[k],y[k]) for k in x)
        if isinstance(x,list): return len(x)==len(y) and all(near(i,j) for i,j in zip(x,y))
        return x==y
    return near(a,b) and near(full['pay'],reduced['pay']) and all(
        near(full[k],reduced[k]) for k in ('physical','unpaid','revenue')) and all(
        near(full['stats'].get(k,0),reduced['stats'].get(k,0))
        for k in ('required','eaten','unmet','starved','worked_for_food','carried_lost'))

def stress(h, day, days, reserve, demand, adult, largest, cap):
    bound = demand * 1.10
    floor = 30 * bound
    if floor > cap: return dict(safe=False,reason='TARGET_EXCEEDS_CAP',floor=floor)
    windows=[]
    # Pack obligations are charged conservatively at every native interval;
    # new consumers cannot contribute guaranteed packs or money to this bound.
    for start in range(61):
        stock=reserve; minimum=stock; feasible=True; trace=[]
        for offset in range(0,90,days):
            check_budget()
            length=min(days,90-offset)
            overlaps = max(offset,start) < min(offset+length,start+30)
            a=max(0.,adult-largest) if overlaps else adult
            spoil=h.F.SEASONS.mean_over(lambda d:h.F.SEASONS.factor(h.F.SEASONS.SPOIL,d),day+offset,length)
            stock *= math.exp(-h.C.FOOD_SPOIL_PER_YEAR*spoil*length/365.)
            output=h.F.land_output_per_day(a)*length*h.F.season_mean(day+offset,length)
            obligations=bound*(length+h.C.FOOD_PACK_DAYS)
            available=stock+output
            if available < obligations: feasible=False
            stock=min(cap,available-obligations)
            minimum=min(minimum,stock)
            trace.append(dict(offset=offset,loss=overlaps,stock=stock))
        windows.append(dict(start=start,minimum=minimum,terminal=stock,
                            safe=feasible and stock>=floor,trace=trace))
    worst=min(windows,key=lambda r:min(r['minimum'],r['terminal']-floor))
    return dict(safe=all(r['safe'] for r in windows),floor=floor,
                all_window_results=[{k:v for k,v in r.items() if k!='trace'} for r in windows],
                worst=worst, future_child=0, imports=0,
                pack_bound='30 bounded-demand days per native interval; conservative replacement bound')

def observe(h,sim,loc,book):
    snapshot=h.digest(sim); rng=sim.rng.getstate(); draws=sim.rng.draws
    workers=loc['workers_at']; eaters=loc['eaters_at']; helpers=loc['helpers_at']
    spots=set(workers)|set(helpers)|set(eaters)
    closed=(len(sim.graph)==1 and len(spots)==1 and not loc['away'] and
            not sim.households and not sim.clan_treasury and not sim.settlement_treasury)
    spot=next(iter(spots)) if len(spots)==1 else (0,0)
    demand=sum(h.F.ration(c,sim.day) for group in eaters.values() for c in group)
    capacities=[h.F.BODY.work_capacity(c) for c in workers.get(spot,())]
    adult=sum(capacities); child=helpers.get(spot,0.)
    cap=h.C.FOOD_STORE_MONTHS*(365./12.)*demand
    fingerprint=h.digest(dict(graph=sim.graph,roster=h.controls(sim),demand=demand,
                              capacities=capacities,households=sim.households))
    o=dict(version=1,valid=True,day=sim.day,days=loc['days'],scope=closed,
           fingerprint=fingerprint,stock=sim.granary.get(spot,0.),cap=cap,demand=demand,
           adult=adult,child=child,season=h.F.season_mean(sim.day-loc['days'],loc['days']),
           land=h.C.FOOD_LAND_CAP_DAY,rate=h.C.FOOD_PER_WORKER_DAY,
           elasticity=h.C.FOOD_PRICE_ELASTICITY,
           full=dict(unknown=True),stress=dict(safe=False),candidate=dict(preserved=False))
    if not closed:
        return o,dict(current_projection='UNKNOWN_SCOPE'),spot
    full=projected(h,sim,loc,1.)
    closing=full['clone'].granary.get(spot,0.)
    p=loc['days']*o['season']*h.F.land_output_per_day(adult+child)
    overflow=full['stats']['overflow']
    binding=overflow>EPS and p>=overflow and abs(closing-cap)<=EPS
    alert=(full['physical']>EPS or full['unpaid']>EPS or full['stats']['unmet']>EPS or
           any(c.hunger_days>EPS for c in sim.cast if c.alive))
    o['full']=dict(unknown=False,binding=binding,alert=alert,closing=closing,overflow=overflow)
    o['stress']=stress(h,sim.day,loc['days'],closing,demand,adult,max(capacities,default=0.),cap)
    # Exact current outflows at full effort; discarded production is removable
    # only if the actual lower-effort native continuation preserves everything.
    needed=max(0.,p-overflow+EPS*10)
    denominator=loc['days']*o['season']*o['land']
    effort=1.
    if adult>0 and denominator>0 and 0<=needed<denominator:
        effort=max(.9,min(1.,(-o['land']/o['rate']*math.log1p(-needed/denominator)-child)/adult))
    reduced=projected(h,sim,loc,effort) if effort<1 else full
    o['candidate']=dict(effort=effort,preserved=preserved(h,full,reduced),target=closing)
    assert h.digest(sim)==snapshot and sim.rng.getstate()==rng and sim.rng.draws==draws
    evidence=dict(observation=o,visible_hash=h.digest(o),
                  projection_full_sha256=h.digest(full['clone']),
                  projection_reduced_sha256=h.digest(reduced['clone']),
                  projection_no_mutation=True,projection_rng_draws=0)
    return o,evidence,spot

def interface_checks():
    o=dict(version=1,valid=True,day=10,days=10,scope=True,fingerprint='known',
           stock=100.,cap=100.,demand=1.,adult=2.,child=0.,season=1.,land=60.,rate=5.,
           elasticity=0,full=dict(binding=True,alert=False),stress=dict(safe=True),
           candidate=dict(effort=.9,preserved=True,target=100.))
    results={}
    for name,change in [('missing',{'stock':None}),('stale',{'valid':False}),
                        ('version',{'version':0}),('pricing',{'elasticity':1}),
                        ('scope',{'scope':False}),('nonfinite',{'stock':float('nan')}),
                        ('infeasible_stress',{'stress':{'safe':False}})]:
        test=copy.deepcopy(o)
        if name=='missing':test.pop('stock')
        else:test.update(change)
        answer=decide(test,Book())
        assert answer['effort']==1 and not answer['safe']
        results[name]=answer['reason']
    b=Book(); assert decide(o,b)['effort']==1
    answer=decide(o,b); assert answer['effort']==.9
    committed(b,answer,.9,100)
    loss=copy.deepcopy(o);loss['fingerprint']='observed-loss'
    assert decide(loss,b)['effort']==1 and b.unresolved
    targetbook=Book(target=120,fingerprint='known',last_effort=.9)
    assert decide(o,targetbook)['reason']=='INFEASIBLE_TARGET_CAP' and targetbook.target==120
    debtbook=Book(target=100,fingerprint='known',last_effort=.9)
    debt=copy.deepcopy(o);debt['stock']=99
    assert decide(debt,debtbook)['effort']==1 and debtbook.target==100
    streak=Book();decide(o,streak);decide({},streak)
    assert decide(o,streak)['effort']==1
    # Controller receives the exact same visible prefix. Hidden suffix lives
    # only in the test driver and is never passed to decide/observation.
    commands=[]
    for hidden_suffix in ('death_at_20','travel_at_20_return_40'):
        independent=Book()
        commands.append([decide(copy.deepcopy(o),independent) for _ in range(2)])
    assert commands[0]==commands[1]
    source=(ROOT/'controller.py').read_text(encoding='utf-8')
    tree=ast.parse(source)
    imports=[n.module for n in ast.walk(tree) if isinstance(n,ast.ImportFrom)]
    assert imports==['dataclasses']
    results.update(streak_and_reentry=True,emergency_bypasses_ramp=True,
                   unresolved_target_preserved=True,debt_not_retired=True,
                   no_oracle_prefix=True,controller_import_surface=imports,
                   controller_bookkeeping_external=True)
    return results

def run_one(h,case,arm,rep):
    init=copy.deepcopy(case); init['start']=case['start']-2*case['days']
    sim=h.build(init); book=Book(); commands={}; rows=[]
    candidate=compile_kernel(h,commands) if arm=='candidate' else h.F.tick
    count=2+case['ticks']+90//case['days']
    for step in range(count):
        check_budget()
        sim.day=init['start']+(step+1)*case['days']
        phase='lead_in' if step<2 else 'core' if step<2+case['ticks'] else 'recovery_tail_forced_full'
        if case.get('shock') and sim.day==case['start']+2*case['days']:
            if case['shock']=='death':sim.kill(sim.cast[0],'scripted fixture producer death')
            else:sim.cast[0].travel_dest=2
        if case.get('shock')=='travel' and sim.day==case['start']+4*case['days']:
            sim.cast[0].travel_dest=-1
        before=copy.deepcopy(sim.food_stats);wages=copy.deepcopy(sim.wage_stats)
        before_controls=h.controls(sim);before_rng=sim.rng.getstate();before_draws=sim.rng.draws
        opening=h.encode_spots(sim.granary); collector=h.Collector(sim,candidate)
        decision={}; evidence={}; native_hashes={}; current_full_hash=None
        def trace(frame,event,arg):
            nonlocal decision,evidence,current_full_hash
            collected=collector.trace(frame,event,arg)
            if frame.f_code==candidate.__code__ and event=='line':
                line=frame.f_lineno
                if line==258:
                    native_hashes['before_production']=h.digest(sim)
                    if arm=='candidate':
                        o,evidence,spot=observe(h,sim,frame.f_locals,book)
                        decision=decide(o,book)
                        actual=decision['effort'] if phase=='core' else 1.
                        commands.clear();commands[spot]=actual
                        committed(book,decision,actual,o['candidate'].get('target',o['cap']))
                        current_full_hash=evidence.get('projection_full_sha256')
                        append('decisions.jsonl',dict(run=case['name'],arm=arm,repetition=rep,
                            step=step+1,day=sim.day,phase=phase,actual_effort=actual,
                            decision=decision,evidence=evidence,status='completed'))
                for number,label in {271:'after_production',282:'after_local_reservation',
                    287:'after_transport',297:'before_farm_pay',299:'after_farm_pay',
                    310:'before_cap',311:'after_cap'}.items():
                    if line==number:
                        native_hashes[label]=h.digest(sim)
                        append('phases.jsonl',dict(run=case['name'],arm=arm,repetition=rep,
                            step=step+1,day=sim.day,phase=label,sha256=native_hashes[label],
                            stock=h.encode_spots(sim.granary),food=dict(sim.food_stats),status='completed'))
            return collected if frame.f_code!=candidate.__code__ else trace
        previous=sys.gettrace()
        with patches(h):
            sys.settrace(trace)
            try:candidate(sim,case['days'])
            finally:sys.settrace(previous)
        assert sim.rng.getstate()==before_rng and sim.rng.draws==before_draws
        for a,b in zip(before_controls,h.controls(sim)):
            assert a['profession']==b['profession'] and a['fieldwork']==b['fieldwork']
            assert a==b or (a['alive'] and not b['alive'] and sim.cast[a['cid']].death_cause=='อดอาหาร')
        applied=commands.get((0,0),1.) if arm=='candidate' else 1.
        for production in collector.production.values():
            assert abs(production['effective_adult']-production['raw_adult']*applied)<1e-12
            assert abs(production['made']-h.F.land_output_per_day(
                production['raw_adult']*applied+production['child'])*case['days']*production['season'])<1e-9
        gaps=dict(food=abs(h.F.ledger_balance(sim.food_stats)-h.F.total_held(sim)),
                  gold=abs(h.W.gold_gap(sim,0)),
                  demand=abs(sim.food_stats['required']-sim.food_stats['eaten']-sim.food_stats['unmet']))
        assert all(v<1e-7 for v in gaps.values())
        delta={k:sim.food_stats.get(k,0)-before.get(k,0) for k in sim.food_stats}
        assert delta['endowed']==0
        pay=sim.wage_stats['farm_paid']-wages['farm_paid']
        assert abs(sum(p['amount'] for p in collector.pay)-pay)<1e-7
        full_hash=h.digest(sim)
        if arm=='candidate' and applied==1 and current_full_hash is not None:
            assert full_hash==current_full_hash, 'Same-input e=1 continuation differs from real tick'
        debt=feedback(book,sim.granary.get((0,0),0),delta['unmet']>EPS or collector.unpaid>EPS)
        row=dict(step=step+1,day=sim.day,phase=phase,applied_effort=applied,
                 produced=delta['produced'],eaten=delta['eaten'],required=delta['required'],
                 overflow=delta['overflow'],natural_spoil=delta['spoiled']-delta['overflow'],
                 transport_loss=delta['carried_lost'],physical_shortfall=sum(max(0,v) for v in collector.physical.values()),
                 unpaid=collector.unpaid,unmet=delta['unmet'],starved=delta['starved'],
                 farm_revenue=sim.wage_stats['food_bought']-wages['food_bought'],farm_pay=pay,
                 pay_by_cid=collector.pay,opening_stock=opening,closing_stock=h.encode_spots(sim.granary),
                 production=h.encode_spots(collector.production),stages={k:h.encode_spots(v) for k,v in collector.stages.items()},
                 asks={str(k):{str(d):dict(request=a,hops=n) for d,(a,n) in v.items()} for k,v in collector.asks.items()},
                 allocation=h.encode_spots(collector.allocation),edges=collector.edges,
                 consumers=observable_summary(h,sim),closures=gaps,rng_draws=sim.rng.draws-before_draws,
                 full_state_sha256=full_hash,every_key_hashes=key_hashes(h,sim),rng_sha256=h.digest(sim.rng.getstate()),
                 phase_hashes=native_hashes,debt=debt,target=book.target,
                 reason=decision.get('reason','BASELINE'),controller_effort=decision.get('effort',1.),
                 projection_e1_exact=full_hash==current_full_hash if current_full_hash else None)
        append('records.jsonl',dict(run=case['name'],arm=arm,repetition=rep,status='completed',record=row))
        rows.append(row)
    append('run_status.jsonl',dict(run=case['name'],arm=arm,repetition=rep,status='COMPLETED',ticks=len(rows)))
    return rows

def difference(b,c):
    bad=[]
    for key in ('unmet','unpaid','physical_shortfall','starved','transport_loss'):
        if c[key]>b[key]+EPS:bad.append(key)
    for key in ('eaten','farm_revenue','farm_pay'):
        if c[key]+EPS<b[key]:bad.append(key)
    for person0,person1 in zip(b['consumers']['people'],c['consumers']['people']):
        for k in ('food','fed'):
            if person1[k]+EPS<person0[k]:bad.append('per_cid_'+k)
        if person1['hunger']>person0['hunger']+EPS:bad.append('per_cid_hunger')
        if person0['alive'] and not person1['alive']:bad.append('per_cid_death')
        for tier,amount in person0['money'].items():
            if person1['money'].get(tier,0)+EPS<amount:bad.append('per_cid_wallet')
    bp={p['cid']:p['amount'] for p in b['pay_by_cid']};cp={p['cid']:p['amount'] for p in c['pay_by_cid']}
    if any(cp.get(cid,0)+EPS<v for cid,v in bp.items()):bad.append('per_cid_pay')
    if any(c['closing_stock'].get(s,0)+EPS<v for s,v in b['closing_stock'].items()):bad.append('closing_reserve')
    return sorted(set(bad))

def report(outcomes,checks,elapsed,gate):
    lines=['# EXP-01 experimental miniature report','',
           'Status: COMPLETED. Profile frozen; no tuning, world replay or production edits.',
           f'44 runs / 608 actual food ticks. Elapsed total: {elapsed:.2f} seconds.',
           f'Evidence gate: {gate}.','',
           '| Subcase | reductions | overflow reduction | adverse boundaries | classification |',
           '| --- | ---: | ---: | ---: | --- |']
    for r in outcomes:
        lines.append(f"| {r['run']} | {r['reductions']} | {r['overflow_reduction']:.9g} | {len(r['adverse'])} | {r['classification']} |")
    lines.extend(['','รายงานทั้ง baseline/candidate สอง repetitions ครบทุก subcase ใน outcomes.json และ records.jsonl',
        'Tail บังคับ e=1 ใช้ตรวจ stock/debt/shortage recovery เท่านั้น ไม่ใช่หลักฐานว่า controller เลือกคืน effort ถูกเวลา',
        'Recovery controller แยกตรวจด้วย observed-loss, unresolved target, debt, upward-ramp bypass และ streak/reset interface checks; core decisions ถูกบันทึกจริง',
        'Future forecast: full effort, child=0, imports=0; demand +10%; 61 loss positions แบบ conservative interval-overlap; cap growth ไม่ถูกเครดิต',
        'Pack outflow stress bound =30 bounded-demand days ทุก native interval (conservative replacement bound); ไม่เครดิต pack inventories ในอนาคต',
        'Post-spoil reserve debt veto ใช้ literal spec: ไม่เปลี่ยน phase เพียงเพื่อเพิ่ม reductions; ownership/availability changes เก็บ target unresolved',
        'Lead-in ใช้ initial stock/population เดิมที่วันเริ่มใหม่โดยไม่ reset; core inputs จึงเปลี่ยนตาม actual prehistory',
        'Price elasticity=0 / price0.1 เท่านั้น; no occupational wages/free time claims; raw pay weights คงเดิม',
        'Full-state/every-key/phase hashes ใช้ serializer เดิม; e=1 same-input continuation exact; deterministic repeat exact; RNG draws0; closures <1e-7',
        'Fixture shell freeze adapt/respond/seek เหมือนเดิม; no households/kin/estate/body-age/market world scheduler. Baseline starvation ใช้เกณฑ์จริง',
        'Multiple producer losses, demand shocks เกินbounds และเหตุหลังcommit อยู่นอกการรับรอง; permanent death อยู่นอก temporary30-day envelope ก่อนถูกสังเกต',
        'ผลนี้ไม่ใช่ safety guarantee ทุกโลก และไม่มี deployment/tuning/world replay ต่อ'])
    if not any(r['qualified_reductions'] for r in outcomes):
        lines.append('**EXP-01 ยังไม่บรรลุเป้าหมาย: ไม่มี qualified reduction; ไม่ลด guards เพื่อให้ผ่าน**')
    (OUT/'REPORT_TH.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')

def main():
    if OUT.exists(): raise RuntimeError('Refusing reuse/automatic retry of existing output')
    OUT.mkdir(parents=True)
    try:
        check_budget()
        for p in ROOT.glob('*.py'):compile(p.read_bytes(),str(p),'exec')
        h,cases=load_shell()
        before=inventories()
        provenance=json.loads((WORK/'docs/food_effort_controller_v1/provenance.json').read_text(encoding='utf-8-sig'))
        for name,expected in provenance['source_contracts'].items():
            assert sha(SOURCE/name)==expected
        config={k:v for k,v in vars(h.C).items() if k.startswith(('FOOD_','WAGES_ENABLED','CHILD_LABOUR')) and isinstance(v,(int,float,str,bool,list,tuple))}
        windows=[dict(run=c['name'],delta=c['days'],initialization=c['start']-2*c['days'],
                      core_start=c['start'],core_end=c['start']+c['days']*c['ticks'],
                      tail_end=c['start']+c['days']*c['ticks']+90,
                      ticks=2+c['ticks']+90//c['days']) for c in cases]
        assert sum(w['ticks'] for w in windows)*4==608 and len(cases)==11
        manifest=dict(status='FROZEN',revision=provenance['revision'],profile=PROFILE,
              timing='native pre-production accounting only',seed=18,concurrency=1,
              start_task_utc=START_UTC,deadline_utc=datetime.fromtimestamp(DEADLINE,timezone.utc).isoformat(),
              budget_seconds=600,max_evidence_bytes=MAX_BYTES,runs=44,ticks=608,repetitions=2,
              windows=windows,fixtures=cases,config=config,
              horizon_start='after current native closing',stress_starts=list(range(61)),
              stress_loss='remove largest current eligible adult from entire positive-overlap native intervals',
              future_cadence='declared miniature cadence only',future_effort=1,
              stress_pack_bound='30 bounded-demand days per native interval',
              reserve='baseline binding-cap closing; no cap growth credit; unresolved targets never retired',
              debt_phase='current post-spoil pre-production and actual closing feedback',
              forced_full=['two lead-in ticks','90-day recovery tail'],
              tolerances=dict(closure_abs=1e-7,preservation_abs=EPS,capacity_abs=1e-12,production_abs=1e-9,
                              equivalence='exact full/every-key/phase hashes',determinism='exact records',rng=0),
              stop=dict(runtime_metadata_timeout='STOP INCOMPLETE NO RETRY',added_harm='retain candidate failure; continue independent cases'),
              source_instrumentation_hashes=before,python=sys.version,
              certificate_scope='single isolated graph node; no away actors/households/charity; real current continuation stages',
              no_production_changes=True,no_world_replay=True,no_commit_push=True)
        save('manifest.json',manifest);manifest_hash=sha(OUT/'manifest.json')
        save('status.json',dict(status='RUNNING',manifest_sha256=manifest_hash,completed_runs=0))
        checks=interface_checks();save('interface_checks.json',checks)
        outcomes=[];completed=0
        for case in cases:
            arms={}
            for arm in ('baseline','candidate'):
                reps=[]
                for rep in (1,2):
                    reps.append(run_one(h,case,arm,rep));completed+=1
                    save('status.json',dict(status='RUNNING',manifest_sha256=manifest_hash,completed_runs=completed))
                assert reps[0]==reps[1], 'Nondeterministic records'
                arms[arm]=reps[0]
            base=arms['baseline'];cand=arms['candidate'];adverse=[];reductions=[]
            for b,c in zip(base,cand):
                assert (b['day'],b['phase'])==(c['day'],c['phase'])
                harm=difference(b,c)
                if harm:adverse.append(dict(day=c['day'],phase=c['phase'],fields=harm,baseline=b,candidate=c))
                if c['applied_effort']<1:reductions.append(dict(day=c['day'],effort=c['applied_effort'],qualified=not harm))
            if not reductions:
                assert all(b['full_state_sha256']==c['full_state_sha256'] and b['every_key_hashes']==c['every_key_hashes']
                           and b['phase_hashes']==c['phase_hashes'] for b,c in zip(base,cand)), 'No-op arm differs from baseline'
            outcome=dict(run=case['name'],repetitions=2,deterministic=True,
                reductions=len(reductions),qualified_reductions=sum(r['qualified'] for r in reductions),reduction_decisions=reductions,
                overflow_reduction=sum(r['overflow'] for r in base)-sum(r['overflow'] for r in cand),
                adverse=adverse,baseline_unmet=sum(r['unmet'] for r in base),baseline_starved=sum(r['starved'] for r in base),
                candidate_unmet=sum(r['unmet'] for r in cand),candidate_starved=sum(r['starved'] for r in cand),
                reasons={reason:sum(r['reason']==reason for r in cand) for reason in sorted({r['reason'] for r in cand})},
                exact_noop=not reductions,
                classification='adverse' if adverse else 'reduction' if reductions else 'abstention' if any(r['reason'].startswith(('UNKNOWN','INFEASIBLE','BASELINE','OBSERVED')) for r in cand) else 'no-op',
                recovery=[dict(day=c['day'],phase=c['phase'],unmet=c['unmet'],baseline_unmet=b['unmet'],stock=c['closing_stock'],
                               baseline_stock=b['closing_stock'],target=c['target'],debt=c['debt'],controller_effort=c['controller_effort'],reason=c['reason'])
                          for b,c in zip(base,cand) if c['phase']=='recovery_tail_forced_full'])
            outcomes.append(outcome);save('outcomes.json',outcomes)
            print(case['name'],outcome['classification'],'reductions',len(reductions),'adverse',len(adverse),flush=True)
        after=inventories();save('hashes.after.json',after)
        assert before==after and sha(OUT/'manifest.json')==manifest_hash, 'Source/tools/manifest changed'
        check_budget()
        elapsed=time.time()-datetime.fromisoformat(START_UTC).timestamp()
        gate='PASS_UNDER_DECLARED_ASSUMPTIONS' if any(r['qualified_reductions'] for r in outcomes) and not any(r['adverse'] for r in outcomes) else 'OBJECTIVE_UNMET_OR_CANDIDATE_FAILURE'
        report(outcomes,checks,elapsed,gate)
        check_budget()
        save('status.json',dict(status='COMPLETED',manifest_sha256=manifest_hash,completed_runs=completed,ticks=608,
             gate=gate,elapsed_total_seconds=elapsed,source_instrumentation_unchanged=True,
             no_extra_rng=True,all_repetitions_deterministic=True,all_noop_arms_exact=True))
    except BaseException as exc:
        save('status.json',dict(status='INCOMPLETE',error=repr(exc),traceback=traceback.format_exc(),
             elapsed_total_seconds=time.time()-datetime.fromisoformat(START_UTC).timestamp(),no_retry=True))
        (OUT/'REPORT_TH.md').write_text('# EXP-01\n\nINCOMPLETE. Evidence retained; no retry/tuning.\n\n'+repr(exc)+'\n',encoding='utf-8')
        raise

if __name__=='__main__':main()
