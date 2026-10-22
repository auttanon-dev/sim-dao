//! Perlin gradient noise 2D/3D + ผิวดาว (พอร์ตจาก tiandao/noise.py)
//!
//! สมการและค่าคงที่เหมือนต้นฉบับทุกตัว ต่างแค่ตารางสับเปลี่ยนที่มาจาก RNG ของ Rust
//! (ไม่ใช่ `random.Random(...).shuffle` ของ Python) — `Field::from_perm` มีไว้ให้เทสต์
//! เทียบกับต้นฉบับ Python โดยป้อนตารางเดียวกัน

use crate::rng::{fold_seed, Xoshiro};
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;

const R2: f64 = std::f64::consts::FRAC_1_SQRT_2;
pub const GRADS: [(f64, f64); 8] = [
    (1.0, 0.0),
    (-1.0, 0.0),
    (0.0, 1.0),
    (0.0, -1.0),
    (R2, R2),
    (-R2, R2),
    (R2, -R2),
    (-R2, -R2),
];
const NORM: f64 = std::f64::consts::FRAC_1_SQRT_2; // sqrt(2)/2
const NORM3: f64 = 0.866_025_403_784_438_6; // sqrt(0.75)
const TABLE: usize = 256;
const MASK: i64 = (TABLE as i64) - 1;

pub const GRADS3: [(i64, i64, i64); 12] = [
    (1, 1, 0),
    (-1, 1, 0),
    (1, -1, 0),
    (-1, -1, 0),
    (1, 0, 1),
    (-1, 0, 1),
    (1, 0, -1),
    (-1, 0, -1),
    (0, 1, 1),
    (0, -1, 1),
    (0, 1, -1),
    (0, -1, -1),
];

const WARP_OFFSETS: [(f64, f64, f64); 3] = [
    (0.0, 0.0, 0.0),
    (37.31, 11.73, 91.57),
    (-63.19, 79.41, -23.87),
];

const SEED_SALT: i128 = 0x5EED_1A9D;

#[inline]
pub fn fade(t: f64) -> f64 {
    t * t * t * (t * (t * 6.0 - 15.0) + 10.0)
}

#[inline]
pub fn lerp(a: f64, b: f64, t: f64) -> f64 {
    a + t * (b - a)
}

#[pyclass(frozen, skip_from_py_object, module = "simdao_core")]
#[derive(Clone)]
pub struct Field {
    seed: i128,
    perm: [u8; TABLE],
}

impl Field {
    #[inline]
    fn grad(&self, xi: i64, yi: i64) -> (f64, f64) {
        let p = &self.perm;
        let a = p[(xi & MASK) as usize] as i64;
        let h = p[((a + yi) & MASK) as usize];
        GRADS[(h & 7) as usize]
    }

    #[inline]
    pub fn grad3(&self, xi: i64, yi: i64, zi: i64) -> (i64, i64, i64) {
        let p = &self.perm;
        let a = p[(xi & MASK) as usize] as i64;
        let b = p[((a + yi) & MASK) as usize] as i64;
        let h = p[((b + zi) & MASK) as usize] as usize;
        GRADS3[h % 12]
    }

    pub fn noise_2d(&self, x: f64, y: f64) -> f64 {
        let xi = x.floor() as i64;
        let yi = y.floor() as i64;
        let xf = x - xi as f64;
        let yf = y - yi as f64;
        let u = fade(xf);
        let v = fade(yf);
        let g00 = self.grad(xi, yi);
        let g10 = self.grad(xi + 1, yi);
        let g01 = self.grad(xi, yi + 1);
        let g11 = self.grad(xi + 1, yi + 1);
        let n00 = g00.0 * xf + g00.1 * yf;
        let n10 = g10.0 * (xf - 1.0) + g10.1 * yf;
        let n01 = g01.0 * xf + g01.1 * (yf - 1.0);
        let n11 = g11.0 * (xf - 1.0) + g11.1 * (yf - 1.0);
        lerp(lerp(n00, n10, u), lerp(n01, n11, u), v) / NORM
    }

    pub fn fbm_2d(&self, x: f64, y: f64, octaves: i64, lacunarity: f64, gain: f64, scale: f64) -> f64 {
        let (mut amp, mut freq, mut total, mut norm) = (1.0, scale, 0.0, 0.0);
        for _ in 0..octaves.max(1) {
            total += amp * self.noise_2d(x * freq, y * freq);
            norm += amp;
            amp *= gain;
            freq *= lacunarity;
        }
        (0.5 + 0.5 * total / norm.max(1e-9)).clamp(0.0, 1.0)
    }

    pub fn noise_3d(&self, x: f64, y: f64, z: f64) -> f64 {
        let xi = x.floor() as i64;
        let yi = y.floor() as i64;
        let zi = z.floor() as i64;
        let xf = x - xi as f64;
        let yf = y - yi as f64;
        let zf = z - zi as f64;
        let u = fade(xf);
        let v = fade(yf);
        let t = fade(zf);
        let mut n = [0.0f64; 8];
        let mut k = 0;
        for dz in 0..2i64 {
            for dy in 0..2i64 {
                for dx in 0..2i64 {
                    let g = self.grad3(xi + dx, yi + dy, zi + dz);
                    n[k] = g.0 as f64 * (xf - dx as f64)
                        + g.1 as f64 * (yf - dy as f64)
                        + g.2 as f64 * (zf - dz as f64);
                    k += 1;
                }
            }
        }
        let x00 = lerp(n[0], n[1], u);
        let x10 = lerp(n[2], n[3], u);
        let x01 = lerp(n[4], n[5], u);
        let x11 = lerp(n[6], n[7], u);
        lerp(lerp(x00, x10, v), lerp(x01, x11, v), t) / NORM3
    }
}

#[pymethods]
impl Field {
    #[new]
    #[pyo3(signature = (seed = 0))]
    fn new(seed: i128) -> Self {
        let mut rng = Xoshiro::from_seed(fold_seed(seed ^ SEED_SALT));
        let mut perm = [0u8; TABLE];
        for (i, p) in perm.iter_mut().enumerate() {
            *p = i as u8;
        }
        rng.shuffle(&mut perm);
        Field { seed, perm }
    }

    /// สร้างจากตารางสับเปลี่ยนที่กำหนดเอง (256 ค่า เป็น permutation ของ 0..255) — ใช้ในเทสต์เทียบต้นฉบับ
    #[staticmethod]
    #[pyo3(signature = (perm, seed = 0))]
    fn from_perm(perm: Vec<u16>, seed: i128) -> PyResult<Self> {
        if perm.len() != TABLE {
            return Err(PyValueError::new_err("perm ต้องมี 256 ค่า"));
        }
        let mut seen = [false; TABLE];
        let mut out = [0u8; TABLE];
        for (i, &v) in perm.iter().enumerate() {
            if v as usize >= TABLE || seen[v as usize] {
                return Err(PyValueError::new_err("perm ต้องเป็น permutation ของ 0..255"));
            }
            seen[v as usize] = true;
            out[i] = v as u8;
        }
        Ok(Field { seed, perm: out })
    }

    #[getter]
    fn seed(&self) -> i128 {
        self.seed
    }

    /// ตารางสับเปลี่ยนต่อท้ายตัวเอง (512 ค่า) ให้หน้าตาเหมือนของเดิม
    #[getter]
    fn perm(&self) -> Vec<u16> {
        let mut v: Vec<u16> = self.perm.iter().map(|&b| b as u16).collect();
        v.extend_from_slice(&v.clone());
        v
    }

    fn noise(&self, x: f64, y: f64) -> f64 {
        self.noise_2d(x, y)
    }

    #[pyo3(signature = (x, y, octaves = 4, lacunarity = 2.0, gain = 0.5, scale = 1.0))]
    fn fbm(&self, x: f64, y: f64, octaves: i64, lacunarity: f64, gain: f64, scale: f64) -> f64 {
        self.fbm_2d(x, y, octaves, lacunarity, gain, scale)
    }

    #[pyo3(signature = (x, y, octaves = 4, scale = 1.0))]
    fn ridged(&self, x: f64, y: f64, octaves: i64, scale: f64) -> f64 {
        let (mut amp, mut freq, mut total, mut norm) = (1.0, scale, 0.0, 0.0);
        for _ in 0..octaves.max(1) {
            total += amp * (1.0 - self.noise_2d(x * freq, y * freq).abs());
            norm += amp;
            amp *= 0.5;
            freq *= 2.0;
        }
        (total / norm.max(1e-9)).clamp(0.0, 1.0)
    }

    #[pyo3(signature = (x, y, step = 0.5, octaves = 4, lacunarity = 2.0, gain = 0.5, scale = 1.0))]
    #[allow(clippy::too_many_arguments)]
    fn slope(&self, x: f64, y: f64, step: f64, octaves: i64, lacunarity: f64, gain: f64, scale: f64) -> (f64, f64) {
        let h = step.max(1e-6);
        let f = |a: f64, b: f64| self.fbm_2d(a, b, octaves, lacunarity, gain, scale);
        let dx = (f(x + h, y) - f(x - h, y)) / (2.0 * h);
        let dy = (f(x, y + h) - f(x, y - h)) / (2.0 * h);
        (dx, dy)
    }
}

/// ผิวดาวหนึ่งดวง — D(p) = R + A·F(p̂ + λW(p̂)) - ‖p‖
#[pyclass(frozen, module = "simdao_core")]
pub struct Planet {
    field: Field,
    #[pyo3(get)]
    radius: f64,
    #[pyo3(get)]
    amp: f64,
    #[pyo3(get)]
    lam: f64,
    #[pyo3(get)]
    octaves: i64,
    #[pyo3(get)]
    warp_octaves: i64,
}

impl Planet {
    fn fbm3_impl(&self, x: f64, y: f64, z: f64, octaves: i64, scale: f64, gain: f64, lacunarity: f64) -> f64 {
        let (mut amp, mut freq, mut total, mut norm) = (1.0, scale, 0.0, 0.0);
        for _ in 0..octaves.max(1) {
            total += amp * self.field.noise_3d(x * freq, y * freq, z * freq);
            norm += amp;
            amp *= gain;
            freq *= lacunarity;
        }
        (total / norm.max(1e-9)).clamp(-1.0, 1.0)
    }
}

#[pymethods]
impl Planet {
    #[new]
    #[pyo3(signature = (seed = 0, radius = 1.0, amp = 0.12, lam = 1.0, octaves = 5, warp_octaves = 2))]
    fn new(seed: i128, radius: f64, amp: f64, lam: f64, octaves: i64, warp_octaves: i64) -> Self {
        Planet { field: Field::new(seed), radius, amp, lam, octaves, warp_octaves }
    }

    /// สร้างจาก Field ที่มีอยู่ (เช่นจาก `Field.from_perm`) — ใช้ในเทสต์เทียบต้นฉบับ
    #[staticmethod]
    #[pyo3(signature = (field, radius = 1.0, amp = 0.12, lam = 1.0, octaves = 5, warp_octaves = 2))]
    fn from_field(field: PyRef<Field>, radius: f64, amp: f64, lam: f64, octaves: i64, warp_octaves: i64) -> Self {
        Planet { field: field.clone(), radius, amp, lam, octaves, warp_octaves }
    }

    #[getter]
    fn field(&self) -> Field {
        self.field.clone()
    }

    fn noise3(&self, x: f64, y: f64, z: f64) -> f64 {
        self.field.noise_3d(x, y, z)
    }

    #[pyo3(signature = (x, y, z, octaves = None, scale = 1.0, gain = 0.5, lacunarity = 2.0))]
    fn fbm3(&self, x: f64, y: f64, z: f64, octaves: Option<i64>, scale: f64, gain: f64, lacunarity: f64) -> f64 {
        self.fbm3_impl(x, y, z, octaves.unwrap_or(self.octaves), scale, gain, lacunarity)
    }

    fn warp(&self, qx: f64, qy: f64, qz: f64) -> (f64, f64, f64) {
        let mut out = [0.0f64; 3];
        for (i, (ox, oy, oz)) in WARP_OFFSETS.iter().enumerate() {
            out[i] = self.fbm3_impl(qx + ox, qy + oy, qz + oz, self.warp_octaves, 1.0, 0.5, 2.0);
        }
        (out[0], out[1], out[2])
    }

    #[pyo3(signature = (px, py, pz, scale = 1.0))]
    fn height(&self, px: f64, py: f64, pz: f64, scale: f64) -> f64 {
        let n = (px * px + py * py + pz * pz).sqrt();
        if n <= 1e-12 {
            return 0.0;
        }
        let (mut qx, mut qy, mut qz) = (px / n * scale, py / n * scale, pz / n * scale);
        if self.lam != 0.0 {
            let (wx, wy, wz) = self.warp(qx, qy, qz);
            qx += self.lam * wx;
            qy += self.lam * wy;
            qz += self.lam * wz;
        }
        self.fbm3_impl(qx, qy, qz, self.octaves, 1.0, 0.5, 2.0)
    }

    #[pyo3(signature = (px, py, pz, scale = 1.0))]
    fn surface_radius(&self, px: f64, py: f64, pz: f64, scale: f64) -> f64 {
        self.radius + self.amp * self.height(px, py, pz, scale)
    }

    #[pyo3(signature = (px, py, pz, scale = 1.0))]
    fn sdf(&self, px: f64, py: f64, pz: f64, scale: f64) -> f64 {
        let r = (px * px + py * py + pz * pz).sqrt();
        self.surface_radius(px, py, pz, scale) - r
    }
}

#[pyfunction]
#[pyo3(name = "fade")]
pub fn py_fade(t: f64) -> f64 {
    fade(t)
}

#[pyfunction]
#[pyo3(name = "lerp")]
pub fn py_lerp(a: f64, b: f64, t: f64) -> f64 {
    lerp(a, b, t)
}

#[pyfunction]
pub fn sphere_dir(x: f64, y: f64, span: f64) -> (f64, f64, f64) {
    let s = span.max(1e-9);
    let (ux, uy, uz) = (x / s, y / s, 1.0);
    let n = (ux * ux + uy * uy + uz * uz).sqrt();
    (ux / n, uy / n, uz / n)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn zero_at_every_lattice_corner() {
        let f = Field::new(5);
        for i in -4..4 {
            for j in -4..4 {
                assert!(f.noise_2d(i as f64, j as f64).abs() < 1e-12);
            }
        }
    }

    #[test]
    fn same_seed_same_field_other_seed_other_field() {
        let a = Field::new(1);
        let b = Field::new(1);
        let c = Field::new(2);
        let pts: Vec<(f64, f64)> = (0..50).map(|i| (i as f64 * 0.37, i as f64 * 0.91)).collect();
        assert!(pts.iter().all(|&(x, y)| a.noise_2d(x, y) == b.noise_2d(x, y)));
        assert!(pts.iter().any(|&(x, y)| a.noise_2d(x, y) != c.noise_2d(x, y)));
    }

    #[test]
    fn fbm_stays_in_unit_interval() {
        let f = Field::new(9);
        for i in 0..2000 {
            let v = f.fbm_2d(i as f64 * 0.173, i as f64 * 0.311, 4, 2.0, 0.5, 1.0);
            assert!((0.0..=1.0).contains(&v));
        }
    }
}
