//! simdao_core — แกน Rust ของ Sim Dao (วิถีสวรรค์)
//!
//! โมดูลที่ย้ายแล้ว: rng (ใหม่), noise, physics
//! Python เห็นทุกอย่างผ่านแพ็กเกจ `simdao_core`; โมดูลใน `tiandao/` ที่ย้ายแล้วเหลือเป็น
//! shim บางๆ ที่ re-export จากที่นี่ เพื่อให้ผู้เรียกเดิม (`from tiandao import physics as PH`)
//! ไม่ต้องแก้

pub mod engine;
pub mod noise;
pub mod physics;
pub mod rng;

use pyo3::prelude::*;
use pyo3::wrap_pyfunction;

/// RNG ที่ Python เรียกใช้ได้ — seed เดียวกันได้ลำดับเดียวกันเสมอ
#[pyclass(module = "simdao_core")]
pub struct Rng {
    inner: rng::Xoshiro,
}

#[pymethods]
impl Rng {
    #[new]
    #[pyo3(signature = (seed = 0))]
    fn new(seed: i128) -> Self {
        Rng { inner: rng::Xoshiro::from_seed(rng::fold_seed(seed)) }
    }

    fn random(&mut self) -> f64 {
        self.inner.next_f64()
    }

    fn next_u64(&mut self) -> u64 {
        self.inner.next_u64()
    }

    fn uniform(&mut self, a: f64, b: f64) -> f64 {
        a + (b - a) * self.inner.next_f64()
    }

    /// จำนวนเต็มใน [a, b] (รวมปลายทั้งสอง เหมือน random.randint)
    fn randint(&mut self, a: i64, b: i64) -> PyResult<i64> {
        if b < a {
            return Err(pyo3::exceptions::PyValueError::new_err("randint: b < a"));
        }
        let span = (b as i128 - a as i128 + 1) as u64;
        Ok(a + self.inner.below(span) as i64)
    }

    /// ดัชนีสุ่มใน [0, n)
    fn below(&mut self, n: u64) -> PyResult<u64> {
        if n == 0 {
            return Err(pyo3::exceptions::PyValueError::new_err("below(0)"));
        }
        Ok(self.inner.below(n))
    }

    fn gauss(&mut self, mu: f64, sigma: f64) -> f64 {
        mu + sigma * self.inner.gauss()
    }

    /// สุ่มสลับรายการ (คืนรายการใหม่ ไม่แก้ของเดิม)
    fn shuffled<'py>(&mut self, items: Vec<Bound<'py, PyAny>>) -> Vec<Bound<'py, PyAny>> {
        let mut v = items;
        self.inner.shuffle(&mut v);
        v
    }
}

#[pymodule]
fn simdao_core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<Rng>()?;
    m.add_class::<engine::py::PyEngine>()?;
    m.add_class::<noise::Field>()?;
    m.add_class::<noise::Planet>()?;
    m.add_function(wrap_pyfunction!(noise::py_fade, m)?)?;
    m.add_function(wrap_pyfunction!(noise::py_lerp, m)?)?;
    m.add_function(wrap_pyfunction!(noise::sphere_dir, m)?)?;

    macro_rules! add_fns {
        ($($f:ident),* $(,)?) => { $( m.add_function(wrap_pyfunction!(physics::$f, m)?)?; )* };
    }
    add_fns!(
        logistic, logit, barrier_odds, best_wait_days, logistic_growth, lanchester,
        entropy_karma, strike_chance, time_dilation, wave_sum, wave_cancel,
        practice_mastery, practice_gain, surprisal, hawkes_intensity, second_price,
        lognormal_value, scarcity_price, elo_expected, elo_update, spread_reach,
        harvest_step, max_sustainable_yield, relax, half_life_days, cobb_douglas,
        hotelling_price, hazard_p,
    );
    Ok(())
}
