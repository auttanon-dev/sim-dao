import sys,pathlib
from tiandao import food as F
from tiandao import wages as W
from observer_common import SPOT,Trace

def person(sim,ch):
    alive=ch.alive
    return dict(cid=ch.cid,alive=alive,fieldwork=getattr(ch,'fieldwork',False),
                world_id=ch.world_id,place=ch.place,profession=getattr(ch,'profession',None),
                realm=getattr(ch,'realm',None),hidden=getattr(ch,'hidden',None),
                travel_dest=getattr(ch,'travel_dest',None),jail_until=getattr(ch,'jail_until',None),
                age=ch.age(sim.day) if alive else None,
                working=bool(F._working(ch,sim.day)) if alive else False,
                eats=bool(F.eats(ch)),away=bool(F._away(ch,sim.day)) if alive else None,
                seclude_until=getattr(ch,'seclude_until',None),travel_arrival_day=getattr(ch,'travel_arrival_day',None),food=getattr(ch,'food',None),death_day=getattr(ch,'death_day',None),death_cause=getattr(ch,'death_cause',None))

class TickObserver:
    def __init__(self,day=10980):
        self.days={10920,10950,11010};self.record=None;self.records=[];self.active=False;self.gate=Trace();self.boundaries=[]
        self.watch={978,1029,1077,2578,3403,963,974,989,997,1028,1081,2210,3007,3094,3537,3678};self.feed_code=F._feed_place.__code__;self.sell_code=F._sell_to_pack.__code__
        self.tick_code=F.tick.__code__;self.carry_code=F._carry_in.__code__;self.capacity_code=F.BODY.work_capacity.__code__
        lines=pathlib.Path(F.__file__).read_text(encoding='utf-8').splitlines()
        for n,s in {258:'season = season_mean',263:'sim.granary[spot]',279:'sources[spot]',287:'short = set()',310:'cap = _cap_granaries',311:'_adapt_labour',668:'sim.granary[src]'}.items():
            assert s in lines[n-1], 'Frozen source line hooks incompatible'

    def install(self):
        # Called after lifecycle metrics installation; capture original raw
        # code objects in __init__ before any wrapper installation.
        original_adapt=F._adapt_labour
        self.gate.install()
        traced_adapt=F._adapt_labour
        def guarded_adapt(sim,eaters,workers,deficit,days,season,cap=None):
            if not self.active:
                if sim.day==10980:self.boundary(sim,'before_adapt')
                result=original_adapt(sim,eaters,workers,deficit,days,season,cap)
                if sim.day==10980:self.boundary(sim,'after_adapt')
                return result
            r=self.record
            current=[sim.cast[cid] for cid in sorted(sim.alive_cids) if F._spot(sim.cast[cid])==SPOT]
            production=workers.get(SPOT,[])
            filtered=[ch for ch in production if F._working(ch,sim.day) and F._spot(ch)==SPOT]
            input_eaters=eaters.get(SPOT,[])
            ids=self.watch|set(r['people_before_production'])|{ch.cid for ch in current}|{ch.cid for ch in input_eaters}|{ch.cid for ch in production}
            r['people_before_adapt']={cid:person(sim,sim.cast[cid]) for cid in sorted(ids)}
            r['before_adapt']=dict(eater_snapshot_cids=[ch.cid for ch in input_eaters],
                eater_snapshot_daily_need=sum(F.ration(ch,sim.day) for ch in input_eaters),
                current_local_eater_cids=[ch.cid for ch in current if F.eats(ch) and not F._away(ch,sim.day)],
                current_local_daily_need=sum(F.ration(ch,sim.day) for ch in current if F.eats(ch) and not F._away(ch,sim.day)),
                decision_workers=[ch.cid for ch in filtered],
                decision_normal_workers=[ch.cid for ch in filtered if not ch.fieldwork],
                decision_volunteers=[ch.cid for ch in filtered if ch.fieldwork],
                all_current_eligible_normal=[ch.cid for ch in current if F._working(ch,sim.day) and not ch.fieldwork],
                all_current_eligible_volunteers=[ch.cid for ch in current if F._working(ch,sim.day) and ch.fieldwork])
            result=traced_adapt(sim,eaters,workers,deficit,days,season,cap)
            row=self.gate.rows[-1]
            ids|=set(row['recruited'])|set(row['released'])|{c['cid'] for c in row['recruit_checks']}|{c['cid'] for c in row['candidate_checks']}
            r['people_after_adapt']={cid:person(sim,sim.cast[cid]) for cid in sorted(ids)}
            r['adapt']=row
            return result
        F._adapt_labour=guarded_adapt

        original_tick=F.tick; original_account=F._account; original_buy=F._buy
        def account(sim,ch,need,eaten,days):
            if self.active and self.record is not None and F._spot(ch)==SPOT and not F._away(ch,sim.day):
                self.record['meal_accounts'].append(dict(cid=ch.cid,need=need,eaten=eaten,final_unmet=max(0.0,need-eaten)))
            return original_account(sim,ch,need,eaten,days)
        def buy(sim,ch,amount,meal=True):
            got,cost=original_buy(sim,ch,amount,meal)
            if self.active and self.record is not None and F._spot(ch)==SPOT and meal:
                self.record['purchases'].append(dict(cid=ch.cid,offered=amount,bought=got,unpaid=amount-got,cost=cost))
            return got,cost
        F._account,F._buy=account,buy

        def tick(sim,days):
            if sim.day not in self.days and sim.day!=10980:return original_tick(sim,days)
            if sim.day==10980:
                self.boundary(sim,'before_tick')
                previous=sys.gettrace()
                def anchor_tracer(frame,event,arg):
                    if frame.f_code==self.tick_code:
                        if event=='line' and frame.f_lineno==258:self.boundary(sim,'before_production')
                        return anchor_tracer
                    return None
                sys.settrace(anchor_tracer)
                try:return original_tick(sim,days)
                finally:sys.settrace(previous)
            record=dict(day=sim.day,interval_start=sim.day-days,interval_end=sim.day,days=days,
                        stocks=[],transport_edges=[],production=None,meal_accounts=[],purchases=[],
                        capacity_at_production_by_cid={})
            self.record=record;self.records.append(record);self.active=True
            record['feeding_details']=[];record['provisions']=[]
            record['global_stats_before']=dict(sim.food_stats)
            record['global_closure_before']=self.closure(sim)
            def stock(name):
                row=dict(stage=name,stock=sim.granary.get(SPOT,0.0))
                if not record['stocks'] or record['stocks'][-1]!=row:record['stocks'].append(row)
            stock('entry_before_spoil')
            tick_frame=[None]
            def tracer(frame,event,arg):
                if frame.f_code==self.tick_code:
                    tick_frame[0]=frame
                    if event!='line':return tracer
                    loc=frame.f_locals;line=frame.f_lineno
                    if line==240:stock('after_natural_spoil')
                    elif line==258:
                        stock('after_endowment')
                        eaters=loc['eaters_at'].get(SPOT,[]);workers=loc['workers_at'].get(SPOT,[])
                        ids=self.watch|{ch.cid for ch in eaters}|{ch.cid for ch in workers}|{cid for cid in sim.alive_cids if F._spot(sim.cast[cid])==SPOT}
                        record['people_before_production']={cid:person(sim,sim.cast[cid]) for cid in sorted(ids)}
                        record['before_production']=dict(eater_cids=[ch.cid for ch in eaters],
                            daily_need=sum(F.ration(ch,sim.day) for ch in eaters),
                            interval_need=sum(days*F.ration(ch,sim.day) for ch in eaters),
                            normal_workers=[ch.cid for ch in workers if not ch.fieldwork],
                            volunteer_workers=[ch.cid for ch in workers if ch.fieldwork],
                            child_helper_capacity=loc['helpers_at'].get(SPOT,0.0))
                    elif line==263 and loc.get('spot')==SPOT:
                        record['production']=dict(season_multiplier=loc['season'],adult_capacity=loc['adults'],
                            total_capacity=loc['labour'],made=loc['made'])
                    elif line==271:
                        stock('after_production');record['season_multiplier']=loc['season']
                    elif line==273:
                        stock('after_household_draw')
                        record['household_fed']=sum(loc['fed'].get(cid,0.0) for cid in record['before_production']['eater_cids'])
                    elif line==279 and loc.get('spot')==SPOT:
                        record['allocation']=dict(remaining_demand_after_household=loc['total'],local_take=loc['take'])
                    elif line==282:stock('after_local_reservations')
                    elif line==287:
                        stock('after_transport')
                        record['physical_deficit']=loc['deficit'].get(SPOT,0.0)
                        record['food_sources']=[dict(source=list(k),amount=v) for k,v in loc['sources'].get(SPOT,{}).items()]
                    elif line==290:stock('after_feeding_all_places')
                    elif line==292:stock('after_larder_stocking')
                    elif line==297:stock('after_away_accounts')
                    elif line==299:stock('after_farmer_pay')
                    elif line==302:stock('after_leave_before_broke')
                    elif line==310:stock('after_hunger_responses')
                    elif line==311:stock('after_cap_before_adapt')
                    return tracer
                if frame.f_code==self.feed_code:
                    loc=frame.f_locals
                    if loc.get('spot')!=SPOT:return tracer
                    if event=='line' and frame.f_lineno==429:
                        record['feeding_details'].append(dict(cid=loc['ch'].cid,remaining_need=loc['n'],home=loc['home'],bought_plus_relief=loc['got'],from_pack=loc['from_pack']))
                    elif event=='line' and frame.f_lineno==431:
                        record['unsold_return']=dict(supplied=loc['supplied'],taken=loc['taken'],paid=loc['paid'],unsold=loc['unsold'])
                        stock('after_target_meals_before_unsold_return')
                    elif event=='line' and frame.f_lineno==433:stock('after_target_unsold_return_before_provisions')
                    elif event=='return':stock('after_target_provisions')
                    return tracer
                if frame.f_code==self.sell_code:
                    if event=='return' and frame.f_locals.get('spot')==SPOT:
                        record['provisions'].append(dict(cid=frame.f_locals['ch'].cid,amount=arg))
                    return tracer
                if frame.f_code==self.carry_code:
                    if event=='line' and frame.f_lineno==668:
                        loc=frame.f_locals
                        if loc['src']==SPOT or loc['dest']==SPOT:
                            record['transport_edges'].append(dict(source=list(loc['src']),dest=list(loc['dest']),
                                sent=loc['sent'],arrived=loc['came'],loss=loc['sent']-loc['came'],hops=loc['hops']))
                    return tracer
                if frame.f_code==self.capacity_code:
                    if event=='return' and tick_frame[0] is not None and tick_frame[0].f_locals.get('spot')==SPOT:
                        record['capacity_at_production_by_cid'][frame.f_locals['character'].cid]=arg
                    return tracer
                return None
            previous=sys.gettrace();sys.settrace(tracer)
            try:result=original_tick(sim,days)
            finally:sys.settrace(previous);self.active=False
            stock('tick_exit_after_adapt')
            record['global_stats_after']=dict(sim.food_stats)
            record['global_closure_after']=self.closure(sim)
            if record['production'] is None:
                record['production']=dict(season_multiplier=record['season_multiplier'],adult_capacity=0.0,total_capacity=0.0,made=0.0)
            if 'allocation' not in record:record['allocation']=None
            stages=record['stocks']
            record['stock_stage_deltas']=[dict(from_stage=a['stage'],to_stage=b['stage'],delta=b['stock']-a['stock']) for a,b in zip(stages,stages[1:])]
            incoming=[e for e in record['transport_edges'] if e['dest']==list(SPOT)]
            outgoing=[e for e in record['transport_edges'] if e['source']==list(SPOT)]
            record['transport']=dict(imports_sent=sum(e['sent'] for e in incoming),imports_arrived=sum(e['arrived'] for e in incoming),
                import_loss=sum(e['loss'] for e in incoming),exports_sent=sum(e['sent'] for e in outgoing),
                exports_arrived=sum(e['arrived'] for e in outgoing),export_loss=sum(e['loss'] for e in outgoing))
            row=record['adapt'];gates=row['gates'];helpers=row.get('eligible_helpers',[])
            record['evaluated_gates']=dict(shortage=None if not helpers else dict(deficit=row['physical_deficit'],blocked='shortage_block' in gates),
                reserves=None if 'attributed_reserve' not in row else dict(reserve=row['attributed_reserve'],target=row['reserve_target'],passed='reserve_enough_release_all' in gates),
                local_full=None if 'reserve_insufficient' not in gates else dict(stock=row['local_stock'],limit=row['local_limit'],passed='local_full_pass' in gates),
                marginal_release=None if not row['candidate_checks'] else row['candidate_checks'])
            record['validations']=dict(demand_partition_gap=abs(record['before_production']['interval_need']-record['household_fed']-record['allocation']['remaining_demand_after_household']) if record['allocation'] else None,
                deficit_gap=abs(record['physical_deficit']-(record['allocation']['remaining_demand_after_household']-record['allocation']['local_take']-record['transport']['imports_arrived'])) if record['allocation'] else None,
                stock_stage_closure_gap=abs(stages[-1]['stock']-stages[0]['stock']-sum(d['delta'] for d in record['stock_stage_deltas'])),
                adapt_deficit_matches=record['physical_deficit']==row['physical_deficit'])
            return result
        F.tick=tick

    def boundary(self,sim,stage):
        self.boundaries.append(dict(day=sim.day,stage=stage,people={cid:person(sim,sim.cast[cid]) for cid in sorted(self.watch) if 0 <= cid < len(sim.cast)}))

    def closure(self,sim):
        return dict(food_gap=abs(F.ledger_balance(sim.food_stats)-F.total_held(sim)),
            gold_gap=max(abs(W.gold_gap(sim,t)) for t in {w.tier for w in sim.worlds}),
            demand_gap=abs(sim.food_stats['required']-sim.food_stats['eaten']-sim.food_stats['unmet']))
