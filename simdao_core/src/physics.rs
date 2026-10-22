//! สมการของโลกจริงที่โลกจำลองยืมมาใช้ — พอร์ตตรงจาก tiandao/physics.py
//!
//! ทุกฟังก์ชันเป็นคณิตศาสตร์ล้วน ไม่แตะ rng; รูปสมการ ค่าคงที่ และลำดับการ clamp
//! เหมือนต้นฉบับ Python ทุกบรรทัด (คำอธิบายเชิงเหตุผลของแต่ละสมการอยู่ใน physics.py เดิม
//! ซึ่งยังเป็นเอกสารอ้างอิงหลัก)

use pyo3::prelude::*;

#[inline]
fn almost_one() -> f64 {
    f64::from_bits(1.0f64.to_bits() - 1)
}
#[inline]
fn almost_zero() -> f64 {
    f64::from_bits(1)
}

pub fn logistic_impl(z: f64) -> f64 {
    let v = if z >= 0.0 {
        1.0 / (1.0 + (-z).exp())
    } else {
        let e = z.exp();
        e / (1.0 + e)
    };
    v.max(almost_zero()).min(almost_one())
}

pub fn logit_impl(p: f64) -> f64 {
    let p = p.max(1e-12).min(1.0 - 1e-12);
    (p / (1.0 - p)).ln()
}

#[pyfunction]
pub fn logistic(z: f64) -> f64 {
    logistic_impl(z)
}

#[pyfunction]
pub fn logit(p: f64) -> f64 {
    logit_impl(p)
}

#[pyfunction]
#[pyo3(signature = (gap_ratio, shifts = None, base_p = 0.55, softness = 0.5))]
pub fn barrier_odds(gap_ratio: f64, shifts: Option<Vec<f64>>, base_p: f64, softness: f64) -> f64 {
    let mut z = logit_impl(base_p) + gap_ratio / softness.max(1e-6);
    for s in shifts.unwrap_or_default() {
        z += s;
    }
    logistic_impl(z)
}

#[pyfunction]
#[pyo3(signature = (p_now, z_rate, life_left, horizon = None))]
pub fn best_wait_days(p_now: f64, z_rate: f64, life_left: f64, horizon: Option<f64>) -> f64 {
    let l = life_left.max(0.0);
    if l <= 0.0 {
        return 0.0;
    }
    let horizon = horizon.unwrap_or(l);
    let mut hi = horizon.min(l).max(0.0);
    let k = z_rate;
    if k <= 0.0 {
        return 0.0;
    }
    let z0 = logit_impl(p_now.max(1e-9).min(1.0 - 1e-9));
    let margin = |t: f64| {
        let p = logistic_impl(z0 + k * t);
        k * (1.0 - p) * (l - t) - 1.0
    };
    if margin(0.0) <= 0.0 {
        return 0.0;
    }
    if margin(hi) > 0.0 {
        return hi;
    }
    let mut lo = 0.0;
    for _ in 0..40 {
        let mid = 0.5 * (lo + hi);
        if margin(mid) > 0.0 {
            lo = mid;
        } else {
            hi = mid;
        }
    }
    0.5 * (lo + hi)
}

#[pyfunction]
pub fn logistic_growth(now: f64, cap: f64, rate_per_day: f64, days: f64) -> f64 {
    let k = cap;
    let mut h0 = now;
    if k <= 0.0 {
        return 0.0;
    }
    h0 = h0.max(0.0).min(k);
    let rt = rate_per_day * days;
    if rt <= 0.0 || h0 <= 0.0 {
        return h0;
    }
    if rt > 60.0 {
        return k;
    }
    let e = rt.exp();
    k * h0 * e / (k + h0 * (e - 1.0))
}

#[pyfunction]
pub fn lanchester(power_a: f64, power_b: f64) -> (i32, f64) {
    let a = power_a.max(0.0);
    let b = power_b.max(0.0);
    if a <= 0.0 && b <= 0.0 {
        return (0, 0.0);
    }
    if a >= b {
        let left = (a * a - b * b).max(0.0).sqrt();
        return (1, if a > 0.0 { left / a } else { 0.0 });
    }
    let left = (b * b - a * a).max(0.0).sqrt();
    (-1, if b > 0.0 { left / b } else { 0.0 })
}

#[pyfunction]
pub fn entropy_karma(lifespan: f64, mortal_lifespan: f64, k: f64) -> f64 {
    let base = mortal_lifespan.max(1e-6);
    let ratio = (lifespan / base).max(1.0);
    k * ratio.ln()
}

#[pyfunction]
pub fn strike_chance(karma: f64, realm_level: f64, lam: f64) -> f64 {
    let x = karma.max(0.0) * realm_level.max(0.0);
    if x <= 0.0 {
        return 0.0;
    }
    1.0 - (-lam * x).exp()
}

#[pyfunction]
#[pyo3(signature = (qi_density, critical_qi, cap = 12.0))]
pub fn time_dilation(qi_density: f64, critical_qi: f64, cap: f64) -> f64 {
    let rc = critical_qi.max(1e-9);
    let x = (qi_density / rc).max(0.0).min(0.999999);
    cap.min(1.0 / (1.0 - x).sqrt())
}

#[pyfunction]
pub fn wave_sum(a1: f64, a2: f64, phase_deg: f64) -> f64 {
    let th = phase_deg.to_radians();
    (a1 * a1 + a2 * a2 + 2.0 * a1 * a2 * th.cos()).max(0.0).sqrt()
}

#[pyfunction]
pub fn wave_cancel(attack: f64, defense: f64, phase_deg: f64) -> f64 {
    let th = phase_deg.to_radians();
    let cancelled = (-th.cos()).max(0.0) * defense.max(0.0);
    (attack - cancelled).max(0.0)
}

pub fn practice_mastery_impl(reps: f64, exponent: f64) -> f64 {
    let n = reps.max(0.0);
    let b = exponent.max(1e-6);
    1.0 - (1.0 + n).powf(-b)
}

#[pyfunction]
pub fn practice_mastery(reps: f64, exponent: f64) -> f64 {
    practice_mastery_impl(reps, exponent)
}

#[pyfunction]
pub fn practice_gain(reps: f64, exponent: f64) -> f64 {
    practice_mastery_impl(reps + 1.0, exponent) - practice_mastery_impl(reps, exponent)
}

#[pyfunction]
pub fn surprisal(p: f64) -> f64 {
    -(p.min(1.0).max(1e-12)).log2()
}

#[pyfunction]
pub fn hawkes_intensity(base: f64, marks: Option<Vec<f64>>, now: f64, alpha: f64, decay_days: f64) -> f64 {
    let mut lam = base.max(0.0);
    let tau = decay_days.max(1e-6) / std::f64::consts::LN_2;
    for t in marks.unwrap_or_default() {
        let dt = now - t;
        if dt < 0.0 {
            continue;
        }
        if dt / tau > 60.0 {
            continue;
        }
        lam += alpha * (-dt / tau).exp();
    }
    lam
}

#[pyfunction]
pub fn second_price(bids: Option<Vec<f64>>) -> (i64, f64) {
    let vals = bids.unwrap_or_default();
    if vals.is_empty() {
        return (-1, 0.0);
    }
    if vals.len() == 1 {
        return (0, vals[0]);
    }
    let mut order: Vec<usize> = (0..vals.len()).collect();
    // เรียงราคาสูง→ต่ำ เท่ากันให้ดัชนีต่ำชนะ (เสถียรเหมือน sorted(key=(-v, i)))
    order.sort_by(|&i, &j| {
        vals[j]
            .partial_cmp(&vals[i])
            .unwrap_or(std::cmp::Ordering::Equal)
            .then(i.cmp(&j))
    });
    (order[0] as i64, vals[order[1]])
}

#[pyfunction]
pub fn lognormal_value(base: f64, sigma: f64, u: f64) -> f64 {
    let u = u.max(1e-9).min(1.0 - 1e-9);
    let poly = |t: f64| {
        (2.515517 + 0.802853 * t + 0.010328 * t * t)
            / (1.0 + 1.432788 * t + 0.189269 * t * t + 0.001308 * t.powi(3))
    };
    let z = if u < 0.5 {
        let t = (-2.0 * u.ln()).sqrt();
        -(t - poly(t))
    } else {
        let t = (-2.0 * (1.0 - u).ln()).sqrt();
        t - poly(t)
    };
    base.max(0.0) * (sigma * z).exp()
}

#[pyfunction]
#[pyo3(signature = (base, demand, supply, elasticity, lo = 0.15, hi = 12.0))]
pub fn scarcity_price(base: f64, demand: f64, supply: f64, elasticity: f64, lo: f64, hi: f64) -> f64 {
    let d = demand.max(1e-6);
    let s = supply.max(1e-6);
    let mult = (d / s).powf(elasticity);
    base.max(0.0) * hi.min(lo.max(mult))
}

#[pyfunction]
#[pyo3(signature = (rating_a, rating_b, spread = 400.0))]
pub fn elo_expected(rating_a: f64, rating_b: f64, spread: f64) -> f64 {
    1.0 / (1.0 + 10.0f64.powf((rating_b - rating_a) / spread))
}

#[pyfunction]
#[pyo3(signature = (rating_a, rating_b, a_won, k = 24.0, spread = 400.0))]
pub fn elo_update(rating_a: f64, rating_b: f64, a_won: bool, k: f64, spread: f64) -> (f64, f64) {
    let exp_a = 1.0 / (1.0 + 10.0f64.powf((rating_b - rating_a) / spread));
    let s = if a_won { 1.0 } else { 0.0 };
    let delta = k * (s - exp_a);
    (rating_a + delta, rating_b - delta)
}

#[pyfunction]
pub fn spread_reach(steps: i64, per_step: f64) -> f64 {
    let n = steps.max(0);
    if n == 0 {
        return 1.0;
    }
    per_step.max(0.0).min(1.0).powi(n.min(i32::MAX as i64) as i32)
}

#[pyfunction]
pub fn harvest_step(now: f64, cap: f64, rate_per_day: f64, harvest: f64, seed: f64, days: f64) -> f64 {
    let mut h = now.max(0.0);
    let k = cap.max(1e-9);
    let r = rate_per_day.max(0.0);
    let e = harvest.max(0.0);
    let d = days.max(0.0);
    if d <= 0.0 {
        return h;
    }
    let steps = ((d / 30.0) as i64 + 1).min(64).max(1);
    let dt = d / steps as f64;
    let per_day_seed = seed.max(0.0);
    for _ in 0..steps {
        let growth = r * h * (1.0 - h / k);
        h += (growth + per_day_seed - e) * dt;
        if h <= 0.0 {
            h = 0.0;
        } else if h > k {
            h = k;
        }
    }
    h
}

#[pyfunction]
pub fn max_sustainable_yield(rate_per_day: f64, cap: f64) -> f64 {
    rate_per_day.max(0.0) * cap.max(0.0) / 4.0
}

#[pyfunction]
pub fn relax(now: f64, target: f64, rate_per_day: f64, days: f64) -> f64 {
    let lam = rate_per_day.max(0.0);
    let d = days.max(0.0);
    if lam <= 0.0 || d <= 0.0 {
        return now;
    }
    let keep = (-lam * d).exp();
    target + (now - target) * keep
}

#[pyfunction]
pub fn half_life_days(rate_per_day: f64) -> f64 {
    std::f64::consts::LN_2 / rate_per_day.max(1e-12)
}

#[pyfunction]
pub fn cobb_douglas(scale: f64, labour: f64, land: f64, alpha: f64) -> f64 {
    let l = labour.max(0.0);
    let t = land.max(0.0);
    if l <= 0.0 || t <= 0.0 {
        return 0.0;
    }
    let a = alpha.max(0.0).min(1.0);
    scale.max(0.0) * l.powf(a) * t.powf(1.0 - a)
}

#[pyfunction]
#[pyo3(signature = (base, reserve_frac, elasticity, lo = 0.5, hi = 20.0))]
pub fn hotelling_price(base: f64, reserve_frac: f64, elasticity: f64, lo: f64, hi: f64) -> f64 {
    let frac = reserve_frac.max(1e-4).min(1.0);
    let b = base.max(0.0);
    let p = b * frac.powf(-elasticity.max(0.0));
    (b * hi).min((b * lo).max(p))
}

#[pyfunction]
pub fn hazard_p(rate_per_year: f64, days: f64) -> f64 {
    if days <= 0.0 || rate_per_year <= 0.0 {
        return 0.0;
    }
    1.0 - (-rate_per_year * days / 365.0).exp()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn logistic_is_open_interval() {
        assert!(logistic_impl(1e9) < 1.0);
        assert!(logistic_impl(-1e9) > 0.0);
        assert!((logistic_impl(0.0) - 0.5).abs() < 1e-15);
    }

    #[test]
    fn lanchester_square_law() {
        let (w, left) = lanchester(100.0, 99.0);
        assert_eq!(w, 1);
        assert!((left - 0.1411).abs() < 1e-3);
        assert_eq!(lanchester(0.0, 0.0), (0, 0.0));
    }

    #[test]
    fn second_price_ties_go_to_lowest_index() {
        assert_eq!(second_price(Some(vec![5.0, 9.0, 9.0])), (1, 9.0));
        assert_eq!(second_price(Some(vec![])), (-1, 0.0));
    }

    #[test]
    fn harvest_never_leaves_bounds() {
        let h = harvest_step(50.0, 100.0, 0.01, 9.0, 0.0, 3650.0);
        assert!((0.0..=100.0).contains(&h));
    }
}
