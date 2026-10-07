EFFORTS = (1.0, 0.75, 0.5)

# All populations, initial stocks, graph edges, dates, shocks and schedules are
# frozen before simulation. No search or result-dependent parameter changes.
CASES = [
    dict(group=1, name='single_low_demand_overflow', normal=1, volunteers=0, eaters=0, stock=0, days=30, start=10950),
    dict(group=2, name='normal_volunteer_child', normal=1, volunteers=1, eaters=2, child=True, stock=80),
    dict(group=3, name='no_normal_producer_affordability', normal=0, volunteers=2, eaters=5, poor_hidden=True, stock=0, ticks=3),
    dict(group=4, name='shared_source_competing_destinations', network=True, focal=4, competitors=8, stock=40),
    dict(group=5, name='winter_entry', normal=2, volunteers=0, eaters=6, stock=300, days=30, start=11220),
    dict(group=6, name='empty_stock_import_dependence', network=True, focal=6, competitors=2, stock=0),
    dict(group=7, name='delivery_reference', network=True, focal=4, competitors=1, stock=80),
    dict(group=7, name='delivery_source_scarcity', network=True, focal=4, competitors=1, stock=0),
    dict(group=7, name='delivery_more_competition', network=True, focal=4, competitors=15, stock=80),
    dict(group=8, name='producer_death_restore_effort', normal=1, volunteers=1, eaters=5, stock=40, shock='death'),
    dict(group=8, name='producer_travel_restore_effort', normal=1, volunteers=1, eaters=5, stock=40, shock='travel'),
]

for case in CASES:
    case.setdefault('days', 10)
    case.setdefault('start', 10950)
    case.setdefault('ticks', 4)
    case['schedule'] = ['diagnostic', 'diagnostic'] + ['restore_1.0'] * (case['ticks']-2)
