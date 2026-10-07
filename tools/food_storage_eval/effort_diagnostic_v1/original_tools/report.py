import csv
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent
def read(name):return json.loads((ROOT/name).read_text(encoding='utf-8'))
def rows(name):return [json.loads(s) for s in (ROOT/name).read_text(encoding='utf-8').splitlines()]
def table(headers,values):
    return '\n'.join(['| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |']+
        ['| '+' | '.join(f'{v:.4f}' if isinstance(v,float) else str(v) for v in row)+' |' for row in values])
def csvsave(name,records):
    with (ROOT/name).open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(records[0]));writer.writeheader();writer.writerows(records)

def main():
    status=read('completed.json');assert status['status']=='COMPLETED'
    outcomes=rows('outcomes.jsonl');assert len(outcomes)==33
    manifest=read('manifest.json');assert manifest['efforts']==[1.0,.75,.5]
    metrics=[];recovery=[];delivery=[]
    for o in outcomes:
        t=o['totals'];rs=o['records']
        metrics.append(dict(group=o['group'],fixture=o['fixture'],effort=o['effort'],**t,
            final_granary_stock=sum(rs[-1]['closing_stock'].values()),final_pack_food=rs[-1]['pack_food'],
            diagnostic_unmet=sum(r['unmet'] for r in rs if r['phase']=='diagnostic'),
            diagnostic_physical=sum(r['physical_shortfall'] for r in rs if r['phase']=='diagnostic'),
            restored_unmet=sum(r['unmet'] for r in rs if r['phase']=='restore_1.0'),
            restored_physical=sum(r['physical_shortfall'] for r in rs if r['phase']=='restore_1.0'),
            delta_unmet=t['unmet']-sum(r['unmet'] for r in read(o['fixture']+'.baseline.json')),
            delta_physical=o['deltas_vs_baseline']['physical_shortfall']))
        for row in o['recovery']:
            recovery.append(dict(fixture=o['fixture'],effort=o['effort'],step=row['step'],day=row['day'],
                physical=row['physical_shortfall'],unmet=row['unmet'],baseline_physical=row['baseline_shortfall'],
                baseline_unmet=row['baseline_unmet'],stock_gap=sum(row['stock_difference'].values())))
        if o['group']==7:
            for r in rs:
                requested=scarcity=competition=arrived=loss=0.0
                for edge in r['edges']:
                    if edge['dest'] != [0,1]:continue
                    source=str(tuple(edge['source']));dest=str(tuple(edge['dest']))
                    req=r['asks'][source][dest];alloc=r['allocation'][source]
                    factor=.95**req['hops'];requested+=req['request']*factor
                    scarcity+=max(0,req['request']-alloc['available'])*factor
                    competition+=min(req['request'],alloc['available'])*factor-edge['arrived']
                    arrived+=edge['arrived'];loss+=edge['loss']
                assert abs(requested-arrived-scarcity-competition)<1e-7
                delivery.append(dict(fixture=o['fixture'],effort=o['effort'],step=r['step'],phase=r['phase'],
                    focal_requested_net=requested,focal_arrived=arrived,conditional_source_scarcity=scarcity,
                    conditional_competition=competition,actual_transport_loss=loss))
    csvsave('all_metrics.csv',metrics);csvsave('recovery.csv',recovery);csvsave('delivery_decomposition.csv',delivery)
    records=[r for o in outcomes for r in o['records']]
    checks=dict(variants=33,baseline_cases=11,repetitions=2,effort_1_baseline_agreement=True,
        determinism_all_variants=True,rng_draws=sum(r['rng_draws'] for r in records),
        max_food_gap=max(r['food_gap'] for r in records),max_gold_gap=max(r['gold_gap'] for r in records),max_demand_gap=max(r['demand_gap'] for r in records),
        no_after_start_endowment=all(r['ledger_endowed_delta']==0 for r in records),
        source_instrumentation_unchanged=read('hashes.before.json')==read('hashes.after.json'),
        worked_for_food=sum(r['worked_for_food'] for r in records),starved=sum(r['starved'] for r in records))
    (ROOT/'checks.json').write_text(json.dumps(checks,indent=2)+'\n')
    worsening=[dict(fixture=m['fixture'],effort=m['effort'],delta_physical=m['delta_physical'],delta_unmet=m['delta_unmet'])
        for m in metrics if m['effort']<1 and (m['delta_physical']>1e-7 or m['delta_unmet']>1e-7)]
    (ROOT/'worsening.json').write_text(json.dumps(worsening,indent=2)+'\n')
    metric_table=table(['fixture','effort','produced','eaten','overflow','stock final','loss','physical','unpaid','unmet','farm revenue','farm pay'],
        [[m['fixture'],m['effort'],m['produced'],m['eaten'],m['overflow'],m['final_granary_stock'],m['transport_loss'],m['physical_shortfall'],m['unpaid'],m['unmet'],m['farm_revenue'],m['farm_pay']] for m in metrics])
    recovery_table=table(['fixture','effort','step','physical','baseline physical','unmet','baseline unmet','stock gap'],
        [[m['fixture'],m['effort'],m['step'],m['physical'],m['baseline_physical'],m['unmet'],m['baseline_unmet'],m['stock_gap']] for m in recovery])
    recovery_extra=[r for r in recovery if r['effort']<1 and (r['physical']>r['baseline_physical']+1e-7 or r['unmet']>r['baseline_unmet']+1e-7)]
    text=f"""# Effort-only diagnostic fixtures — COMPLETED

Frozen source 95b07ea260d19771810e7748eb61fbbb50db2174 · 2 ตุลาคม 2026

ครบ 8 กลุ่ม / 11 subcases / 33 variants ทุกระดับ effort 1.0, 0.75, 0.5 ที่ตรึงก่อนรัน ทุก variant ตรวจซ้ำ 2 ครั้ง ไม่มี parameter search ไม่มี production file edits ไม่ติดตั้งนโยบาย ไม่รันโลก 50 ปี ไม่ commit/push

## นิยามและ fixture assumptions

AST เปลี่ยนเพียง assignment adult capacity ที่ production: adults=sum(real BODY.work_capacity)×effort แล้วใช้ real F(adults+child helpers)×days×season_mean ไม่มีการคูณผลผลิตปลายทางด้วย effort
Child capacity เท่าเดิม; marginal child output อาจเปลี่ยนตาม nonlinear formula และไม่ถือเป็นการเปลี่ยน child labour
อาชีพ/fieldwork/roster/eligibility ไม่ถูกเปลี่ยนโดย effort ไม่มี recruit/release/extra activity หรือค่าแรงอาชีพเดิมแถม ไม่มีการให้เวลาว่างหรือ worker-days benefit
Farm pay ใช้ raw BODY.work_capacity weights ตามกฎเดิม ไม่เปลี่ยนเป็น effort weights; revenue มาจากเงินจริงที่ผู้กิน/ซื้อเสบียงจ่าย ราคาเปลี่ยนตาม stock จริง ดังนั้นรายได้เพิ่มไม่เท่ากับ welfare benefit

ใช้ real food tick, production, season mean, spoil, local reservation, _carry_in, proportional allocation, pricing, _buy/_feed_place/_account, pack purchases, _pay_farmers, _cap_granaries, store_capacity และ food/gold/demand ledgers
Delivery/asks/available/scale คำนวณใหม่ทุก variant จาก supply จริง ไม่ตรึงให้เท่า baseline ไม่มี free-food injection หลังเริ่ม ไม่ override cap หรือ starvation threshold

Fixture shell เป็นกราฟ 3-node star (หรือ isolated site), miniature state กับ real Character objects; ไม่มี households/clans/charity balances กำหนด initial food stocks/endowed และ initial gold capital ชัดใน manifest
ตรึง adaptive recruit/release และ hunger-driven migration/process interruption เหมือนกันทุก baseline/variant เพื่อคง roster/location ตามนิยามการทดลอง จึงไม่ใช่ full production-policy behavior
การตาย/เดินทางของผู้ผลิตเป็น shocks ล่วงหน้าเหมือนกันทุก effort ไม่ใช่ผลประโยชน์จาก effort ต่ำ Death shell ใช้ real food.on_death แต่ไม่มี estate/kin politics เก็บทองบน corpse เพื่อคง gold ledger
ไม่มี world scheduler, body adaptation, nonfarm labor/time allocation, travel engine/arrival progression หรือ household transfers ใช้ travel flag ตาม schedule ไม่จำลองรายได้อื่น
Real starvation threshold {C_STARVE} วันคงเดิม; starvation outcomes หากเกิดถือเป็นผล diagnostic ไม่ใช่เหตุเพิ่มอาหาร/แก้ cap ในชุดนี้ starved={checks['starved']}

## การตรวจ

- Effort=1 ตรง real original F.tick baseline ภายใต้ fixture shell เดียวกัน ทั้งทุก tick metrics/stock/transport/pay/RNG และ full-state hashes
- ทุก 33 variants deterministic จากการรันซ้ำ 2 ครั้ง; RNG draws เพิ่ม={checks['rng_draws']} ไม่มีการสุ่ม world initialization
- Food/gold/demand closure gaps สูงสุด {checks['max_food_gap']:.9g}/{checks['max_gold_gap']:.9g}/{checks['max_demand_gap']:.9g}; เกณฑ์ <1e-7
- Source/instrumentation before/after hashes ตรงกัน; compile-check scripts ก่อนเริ่ม
- Real relief(worked_for_food) ไม่ได้ถูกอ้างเป็น extra activity benefit; ผลรวมที่เกิดจริง={checks['worked_for_food']}

## ผลทุก fixture/effort

Totals รวม diagnostic ticks 2 ticks แล้วคืน effort=1 ตาม schedule ที่ตรึง (กลุ่ม 3 มี 1 recovery tick; ที่เหลือ 2) ห้ามตีความ totals ว่าใช้ effort ต่ำตลอดช่วง
all_metrics.csv แยก diagnostic/recovery physical/unmet และ deltas จาก baseline; outcomes.jsonl/records.jsonl เก็บทุก tick, repeated runs, raw stats/stock/roster/capacity/asks/scale/edges/pay/closure/state hashes

{metric_table}

Physical shortfall เป็นอาหารที่ขาดหลัง allocation; unpaid เป็นมื้อส่วนที่เสนอแต่ซื้อไม่ไหวก่อน relief; unmet เป็นผลหลัง feeding/pack/relief ทั้งสามค่าไม่ใช่ค่าเดียวกัน
กลุ่ม no-normal producer มี hidden eater ไม่มีเงินเพื่อแยก affordability จาก supply เป็น assumption ล่วงหน้า ไม่ใช่ผลของ effort; child capacity อยู่ใน mixed normal+volunteer case

## Recovery หลังคืน effort 1.0

{recovery_table}

Stock gap คำนวณเทียบ tick baseline ที่มี shocks เดียวกัน จึงแยก stock/path dependence จาก capacity ณ tick ปัจจุบันได้ภายใน fixture นี้
พบ {len(recovery_extra)} recovery rows ที่ shortage/unmet ยังแย่กว่า baseline หลังคืน effort ภายในหน้าต่างที่เก็บ ห้ามอ้างว่าจะฟื้นนอกหน้าต่างหรือฟื้นในหนึ่ง tick เสมอ
Death case คืน effort ไม่คืนผู้ผลิตที่ตาย; travel case คืน effort ที่ tick 3 แต่ผู้เดินทางกลับ tick 4 เป็น lag ที่ระบุล่วงหน้า ไม่ใช่การรับรอง travel scheduling จริง

## Source scarcity เทียบกับการแข่งขัน

กลุ่ม 7 มี reference, initial source stock ลด (80→0) โดย competitors เท่าเดิม และ competitors เพิ่ม (1→15) โดย source initial stock เท่าเดิม ทุก case/rate รายงานทั้งสอง diagnostic ticks และ recovery
delivery_decomposition.csv แสดง realized requested net/arrived/transport loss และ conditional scarcity/competition ตาม observed asks; requested net=arrived+scarcity+competition ตรวจ <1e-7
การเพิ่ม demand เปลี่ยน assigned cap ตาม production rule จริง ไม่ override cap จึงไม่ใช่ pure allocation-only causal test; initial source-stock shock และ competing population เป็น fixture inputs ไม่ใช่การสร้าง/ถอนอาหารระหว่าง variant
ไม่มีการตรึง arrivals ให้เท่า reference การที่ effort ทำ supply ต่ำลงทำให้ requests/scale/arrivals เปลี่ยนจริง

## Guards ที่ข้อมูลนี้ชี้ว่าจำเป็น

มี {len(worsening)} variants ที่ physical shortfall หรือ unmet แย่กว่า effort=1 (ดู worsening.json) เก็บครบทุกกรณี ไม่เลือกเฉพาะผลดี
- ตรวจ demand/available reserve ตาม interval และ season mean ก่อนลด; overflow headroom ใน tick หนึ่งไม่รับรอง closing reserve/recovery ของ tick ถัดไป
- ไม่ใช้ assigned reserve หรือ imports เดิมเป็นอาหารที่จะมาถึงแน่นอน ต้องครอบคลุม source scarcity, competing requests, hops/loss และ network effects
- ชุมชนไม่มี normal producer ต้องเก็บ effective productive capacity ที่เพียงพอ; roster เดิมไม่ได้แปลว่า capacity เดิม
- คืน effort ก่อน shortage เมื่อรู้ winter/producer availability shocks; effort=1 คืนคนตายไม่ได้และแก้ travel absence ไม่ได้ทันที ต้องรายงาน recovery lag/stock debt แยก
- แยก affordability/unpaid และ final unmet จาก physical supply; farm revenue/pay ที่เปลี่ยนจากราคาไม่ใช่หลักฐานว่าคนกินดีขึ้นหรือเวลาว่างเพิ่ม

## ยังไม่พอออกแบบ controller

ยังไม่ตรึง/ทดสอบ reserve floor, ramp, hysteresis, detection/actuation latency หรือ recovery policy ไม่มีการเลือก threshold ที่ปลอดภัยจาก levels เหล่านี้
ไม่มี full-world endogenous migration/recruitment/death estate, body/time responses, nonfarm wages/activities, multi-seed/network topology coverage หรือ causal counterfactual นอก synthetic state
กราฟ/ประชากร/เงิน/stock/duration เป็น fixture assumptions ผลไม่รับรอง safety ทุกโลก และไม่มี effort ระดับใดได้รับการรับรองว่าปลอดภัย
หยุดหลังรายงาน ไม่เริ่ม controller, fixture tuning หรือ world replay ต่อเอง
"""
    (ROOT/'REPORT_TH.md').write_text(text,encoding='utf-8')
    index={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in ROOT.iterdir() if p.is_file() and p.name!='artifact_hashes.json'}
    (ROOT/'artifact_hashes.json').write_text(json.dumps(index,indent=2)+'\n')
    print('Report complete:',len(outcomes),'variants;',len(worsening),'worsening;',len(recovery_extra),'recovery rows worse')

C_STARVE=40
if __name__=='__main__':main()
