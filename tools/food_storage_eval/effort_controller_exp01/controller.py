"""EXP-01 pure controller. No simulation, fixture or scheduler imports."""
from dataclasses import dataclass, asdict
import math

PROFILE = dict(id='EXP-01', minimum_effort=.90, downward_step=.10,
               safe_observations=2, horizon=90, demand_multiplier=1.10,
               loss_days=30, terminal_days=30, imports_credit=0,
               elasticity=0, future_child_lower_bound=0,
               loss_alignment='conservative-interval-overlap')
EPS = 1e-9

@dataclass
class Book:
    target: float | None = None
    fingerprint: str | None = None
    streak: int = 0
    last_effort: float = 1.
    mode: str = 'FULL'
    unresolved: bool = False

def decide(o, b):
    """Only a versioned current-observation certificate; no future schedule."""
    required = {'version','valid','day','days','scope','fingerprint','stock',
                'cap','demand','adult','child','season','land','rate',
                'elasticity','full','stress','candidate'}
    reason = None
    if not isinstance(o, dict) or not required <= o.keys():
        reason = 'UNKNOWN_MISSING'
    elif o['version'] != 1 or not o['valid']:
        reason = 'UNKNOWN_STALE_OR_VERSION'
    elif o['elasticity'] != 0:
        reason = 'UNKNOWN_PRICING'
    elif not all(math.isfinite(o[k]) for k in
                 ('stock','cap','demand','adult','child','season','land','rate','days')):
        reason = 'UNKNOWN_NONFINITE'
    elif not o['scope']:
        reason = 'UNKNOWN_SHARED_EXPORT_OR_OWNERSHIP'
        b.unresolved = b.target is not None
    elif b.fingerprint is not None and b.fingerprint != o['fingerprint']:
        reason = 'OBSERVED_AVAILABILITY_OR_SCOPE_CHANGE'
        b.unresolved = b.target is not None
    elif b.unresolved:
        reason = 'TARGET_UNRESOLVED'
    elif b.target is not None and b.target > o['cap']:
        reason = 'INFEASIBLE_TARGET_CAP'
    elif b.target is not None and b.target - o['stock'] > EPS:
        reason = 'RESERVE_DEBT'
    elif o['full'].get('unknown', False):
        reason = 'UNKNOWN_CURRENT_PROJECTION'
    elif o['full'].get('alert', True):
        reason = 'BASELINE_DEFICIT_OR_AFFORDABILITY'
    elif not o['stress'].get('safe', False):
        reason = 'INFEASIBLE_STRESS_PREFIX_OR_TERMINAL'
    elif not o['full'].get('binding', False):
        reason = 'NO_CERTIFIED_PRODUCTION_DISCARD'
    elif not o['candidate'].get('preserved', False):
        reason = 'NOT_SURPLUS_ONLY'
    if reason:
        b.streak = 0
        b.mode = 'RECOVER' if b.target is not None else 'FULL'
        b.last_effort = 1.
        if isinstance(o, dict) and 'fingerprint' in o:
            b.fingerprint = o['fingerprint']
        return dict(effort=1., reason=reason, safe=False, book=asdict(b))
    b.fingerprint = o['fingerprint']
    b.streak += 1
    if b.streak < PROFILE['safe_observations']:
        b.last_effort = 1.
        return dict(effort=1., reason='WAIT_FOR_TWO_SAFE_OBSERVATIONS',
                    safe=True, book=asdict(b))
    effort = max(PROFILE['minimum_effort'], o['candidate']['effort'],
                 b.last_effort - PROFILE['downward_step'])
    if not .9 <= effort <= 1:
        raise ValueError('Invalid certified effort')
    # Commit is separate: externally forced lead-in/tail do not create targets.
    return dict(effort=effort, reason='CERTIFIED_SURPLUS_ONLY' if effort < 1 else 'NO_OP',
                safe=True, book=asdict(b))

def committed(b, command, actual_effort, target):
    if actual_effort < 1:
        b.target = max(target, b.target or 0.)
        b.mode = 'REDUCE'
    b.last_effort = actual_effort

def feedback(b, closing_stock, alert=False):
    debt = max(0., (b.target or 0.) - closing_stock)
    if alert or debt > EPS:
        b.mode = 'RECOVER'
        b.streak = 0
    return debt
