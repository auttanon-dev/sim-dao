"""เทียบ simdao_core (Rust) กับต้นฉบับ Python ใน tiandao/physics.py และ tiandao/noise.py

ข้ามทั้งไฟล์ถ้ายังไม่ได้ build ส่วนขยาย (cd simdao_core && maturin develop --release)
"""
import math
import random

import pytest

core = pytest.importorskip("simdao_core")

from tiandao import noise as PN
from tiandao import physics as PP

TOL = 1e-9


def close(a, b):
    if isinstance(a, (tuple, list)):
        return len(a) == len(b) and all(close(x, y) for x, y in zip(a, b))
    if isinstance(a, float) and math.isinf(a):
        return a == b
    return math.isclose(a, b, rel_tol=TOL, abs_tol=TOL)


R = random.Random(1234)


def u(lo, hi):
    return R.uniform(lo, hi)


CASES = {
    "logistic": lambda: (u(-30, 30),),
    "logit": lambda: (u(0.001, 0.999),),
    "barrier_odds": lambda: (u(0, 3), [u(-1, 1) for _ in range(3)], u(0.1, 0.9), u(0.1, 2)),
    "best_wait_days": lambda: (u(0.01, 0.99), u(0, 0.05), u(1, 5000), u(10, 3000)),
    "logistic_growth": lambda: (u(0, 100), u(50, 200), u(0, 0.2), u(0, 400)),
    "lanchester": lambda: (u(0.1, 100), u(0.1, 100)),
    "entropy_karma": lambda: (u(10, 5000), u(30, 90), u(0, 2)),
    "strike_chance": lambda: (u(0, 10), u(0, 12), u(0, 1)),
    "time_dilation": lambda: (u(0, 20), u(1, 20)),
    "wave_sum": lambda: (u(0, 10), u(0, 10), u(0, 360)),
    "wave_cancel": lambda: (u(0, 10), u(0, 10), u(0, 360)),
    "practice_mastery": lambda: (u(0, 1e4), u(0.1, 0.9)),
    "practice_gain": lambda: (u(0, 1e4), u(0.1, 0.9)),
    "surprisal": lambda: (u(0.001, 1),),
    "hawkes_intensity": lambda: (u(0, 2), [u(0, 100) for _ in range(4)], u(100, 200), u(0, 1), u(1, 30)),
    "second_price": lambda: ([u(0, 100) for _ in range(5)],),
    "lognormal_value": lambda: (u(1, 100), u(0, 1), u(0.01, 0.99)),
    "scarcity_price": lambda: (u(1, 100), u(0, 50), u(0.1, 50), u(0.1, 2)),
    "elo_expected": lambda: (u(800, 2400), u(800, 2400)),
    "elo_update": lambda: (u(800, 2400), u(800, 2400), R.random() < 0.5),
    "spread_reach": lambda: (R.randint(0, 20), u(0, 1)),
    "harvest_step": lambda: (u(0, 100), u(50, 200), u(0, 0.2), u(0, 5), u(0, 1), u(0, 30)),
    "max_sustainable_yield": lambda: (u(0, 0.2), u(1, 200)),
    "relax": lambda: (u(-10, 10), u(-10, 10), u(0, 0.5), u(0, 100)),
    "half_life_days": lambda: (u(0.001, 0.5),),
    "cobb_douglas": lambda: (u(0, 10), u(0, 100), u(0, 100), u(0, 1)),
    "hotelling_price": lambda: (u(1, 100), u(0.01, 1), u(0.1, 2)),
    "hazard_p": lambda: (u(0, 2), u(0, 365)),
}


@pytest.mark.parametrize("name", sorted(CASES))
def test_physics_parity(name):
    py, rs = PP.PYTHON_IMPL.get(name, getattr(PP, name)), getattr(core, name)
    for _ in range(200):
        args = CASES[name]()
        assert close(rs(*args), py(*args)), (name, args)


def test_physics_covers_everything():
    py_fns = {n for n in dir(PP) if callable(getattr(PP, n)) and not n.startswith("_")
              and getattr(getattr(PP, n), "__module__", "") == PP.__name__}
    missing = {n for n in py_fns if not hasattr(core, n)}
    assert not missing, missing


def rust_field(seed):
    pf = PN.Field(seed)
    return pf, core.Field.from_perm(list(pf.perm[:256]), seed)


@pytest.mark.parametrize("seed", [0, 7, 424242])
def test_field_parity(seed):
    pf, rf = rust_field(seed)
    for _ in range(300):
        x, y = u(-50, 50), u(-50, 50)
        assert close(rf.noise(x, y), pf.noise(x, y))
        assert close(rf.fbm(x, y), pf.fbm(x, y))
        assert close(rf.ridged(x, y), pf.ridged(x, y))
        assert close(rf.slope(x, y), pf.slope(x, y))


@pytest.mark.parametrize("seed", [0, 99])
def test_planet_parity(seed):
    pp = PN.Planet(seed)
    _, rf = rust_field(seed)
    rp = core.Planet.from_field(rf)
    for _ in range(200):
        p = (u(-2, 2), u(-2, 2), u(-2, 2))
        assert close(rp.noise3(*p), pp.noise3(*p))
        assert close(rp.warp(*p), pp.warp(*p))
        assert close(rp.height(*p), pp.height(*p))
        assert close(rp.sdf(*p), pp.sdf(*p))


def test_free_functions():
    for _ in range(100):
        a, b, t = u(-5, 5), u(-5, 5), u(0, 1)
        assert close(core.fade(t), PN.fade(t))
        assert close(core.lerp(a, b, t), PN.lerp(a, b, t))
        assert close(core.sphere_dir(a, b, 10.0), PN.sphere_dir(a, b, 10.0))


def test_rng_deterministic():
    a, b = core.Rng(5), core.Rng(5)
    assert [a.random() for _ in range(50)] == [b.random() for _ in range(50)]
    assert all(1 <= a.randint(1, 6) <= 6 for _ in range(500))
    assert sorted(a.shuffled(list(range(20)))) == list(range(20))
