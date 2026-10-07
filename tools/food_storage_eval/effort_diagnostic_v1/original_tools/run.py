import copy
import hashlib
import json
import os
import sys
import time
import traceback
from pathlib import Path
from fixtures import CASES, EFFORTS
from harness import ROOT, SOURCE, run, C, F, compile_tick

def save(name,value):
    with (ROOT/name).open('w',encoding='utf-8') as f:
        json.dump(value,f,ensure_ascii=False,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())

def append(name,value):
    with (ROOT/name).open('a',encoding='utf-8') as f:
        f.write(json.dumps(value,ensure_ascii=False,separators=(',',':'))+'\n');f.flush();os.fsync(f.fileno())

def hashes():
    return {str(p.relative_to(SOURCE)):hashlib.sha256(p.read_bytes()).hexdigest() for p in SOURCE.rglob('*') if p.is_file()}

def strip_effort(records):
    return [{k:v for k,v in r.items() if k!='applied_effort'} for r in records]

def total(records,key): return sum(r[key] for r in records)

start=time.perf_counter()
try:
    assert not (ROOT/'manifest.json').exists(),'Refusing duplicate execution'
    for p in ROOT.glob('*.py'):compile(p.read_bytes(),str(p),'exec')
    before=hashes()
    historical=json.loads((ROOT.parents[1]/'out/overflow-paired-95b07ea-11340-20261002/hashes.after.json').read_text())
    assert all(before[k]==v for name,v in historical.items() if name.startswith('source/') for k in [name.split('/',1)[1].replace('/','\\')])
    config={k:v for k,v in vars(C).items() if k.startswith(('FOOD_','WAGES_ENABLED','CHILD_LABOUR')) and isinstance(v,(int,float,str,bool,list,tuple))}
    tools={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in ROOT.glob('*.py')}
    save('hashes.before.json',dict(source=before,instrumentation=tools))
    save('manifest.json',dict(revision='95b07ea260d19771810e7748eb61fbbb50db2174',source=str(SOURCE),seed=18,python=sys.version,
        efforts=EFFORTS,fixtures=CASES,fixture_groups=8,subcases=len(CASES),variants=len(CASES)*len(EFFORTS),
        repetitions_per_variant=2,original_kernel_baselines=len(CASES),config=config,
        transformation='Single AST edit: production adults=sum(BODY.work_capacity(...))*effort; child helpers untouched; nonlinear F applied afterwards',
        pay_rule='Original raw BODY.work_capacity weights; no new occupational wages or extra activity credit',
        fixture_assumptions=['Synthetic 3-node star graph or isolated site; actual allocation/feeding/pricing/cap/spoil/pay/ledgers',
          'Freeze adaptive recruit/release and hunger-driven relocation/process interruption identically in baseline/variants',
          'No households/clans/community charity balances; supplied character capital is declared initial gold',
          'Initial stocks declared once as endowed; no later free food or cap/starvation-threshold override',
          'Scripted death/travel identical across variants; simplified death shell retains gold on corpse and uses real food.on_death',
          'No body/age/market scheduler/kin/estate simulation; real starvation threshold still applied'],
        no_parameter_search=True,no_production_edits=True,no_controller=True,no_world_replay=True))
    for case in CASES:
        baseline=run(case,1.0,transform=False)
        save(case['name']+'.baseline.json',baseline)
        for effort in EFFORTS:
            reps=[]
            for rep in (1,2):
                result=run(case,effort,transform=True)
                for r in result:append('records.jsonl',dict(fixture=case['name'],group=case['group'],diagnostic_effort=effort,repetition=rep,status='completed',record=r))
                reps.append(result)
            assert reps[0]==reps[1], 'Nondeterminism: '+case['name']
            if effort==1.0:assert reps[0]==baseline,'effort=1 differs from real original kernel baseline'
            assert all(r['rng_draws']==0 and r['ledger_endowed_delta']==0 for r in reps[0])
            assert all(r['produced']>=0 for r in reps[0])
            outcome=dict(fixture=case['name'],group=case['group'],effort=effort,deterministic=True,
                effort_1_equals_original_baseline=True if effort==1.0 else None,records=reps[0],
                totals={key:total(reps[0],key) for key in ('produced','eaten','overflow','transport_loss','physical_shortfall','unpaid','unmet','farm_revenue','farm_pay','worked_for_food','starved')},
                deltas_vs_baseline={key:total(reps[0],key)-total(baseline,key) for key in ('produced','eaten','overflow','transport_loss','physical_shortfall','unpaid','unmet','farm_revenue','farm_pay')},
                recovery=[dict(step=r['step'],day=r['day'],applied_effort=r['applied_effort'],physical_shortfall=r['physical_shortfall'],unmet=r['unmet'],
                    closing_stock=r['closing_stock'],baseline_shortfall=baseline[i]['physical_shortfall'],baseline_unmet=baseline[i]['unmet'],baseline_stock=baseline[i]['closing_stock'],
                    stock_difference={spot:r['closing_stock'].get(spot,0)-baseline[i]['closing_stock'].get(spot,0) for spot in r['closing_stock'].keys()|baseline[i]['closing_stock'].keys()})
                   for i,r in enumerate(reps[0]) if r['phase']=='restore_1.0'])
            append('outcomes.jsonl',outcome)
            print(case['name'],effort,'complete','unmet',outcome['totals']['unmet'],flush=True)
    after=hashes();tools_after={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in ROOT.glob('*.py')}
    save('hashes.after.json',dict(source=after,instrumentation=tools_after))
    assert before==after and tools==tools_after,'Source/instrumentation changed'
    save('completed.json',dict(status='COMPLETED',groups=8,subcases=len(CASES),variants=len(CASES)*3,
        repetitions=2,all_effort_1_match_baseline=True,all_variants_deterministic=True,no_added_rng_draws=True,
        source_instrumentation_unchanged=True,elapsed=time.perf_counter()-start))
except BaseException as exc:
    save('incomplete.json',dict(status='INCOMPLETE',error=repr(exc),traceback=traceback.format_exc(),elapsed=time.perf_counter()-start,
        no_automatic_retry=True,no_parameter_adjustment=True))
    raise
