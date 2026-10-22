//! RNG แบบ deterministic ของแกน Rust — SplitMix64 (เติม seed) + xoshiro256**
//!
//! ไม่พยายามเลียนแบบ Mersenne Twister ของ Python: ผลจาก seed เดียวกันจึง *ไม่* เท่ากับของเดิม
//! แต่ **ซ้ำได้เป๊ะข้ามเครื่อง/ข้ามเวอร์ชัน** เพราะไม่พึ่งไลบรารีภายนอก และอัลกอริทึมถูกล็อกไว้ที่นี่
//! (ดูเทสต์ `golden_*` ด้านล่าง — ถ้าค่าเปลี่ยน แปลว่าใครแตะอัลกอริทึม และทุกโลกที่เซฟไว้จะเพี้ยน)

/// ย่อ seed จำนวนเต็มกว้าง (Python int) ลงเป็น u64 โดยไม่ทิ้งบิตสูง
#[inline]
pub fn fold_seed(v: i128) -> u64 {
    (v as u64) ^ ((v >> 64) as u64)
}

#[derive(Clone, Debug)]
pub struct Xoshiro {
    s: [u64; 4],
}

#[inline]
fn splitmix64(state: &mut u64) -> u64 {
    *state = state.wrapping_add(0x9E37_79B9_7F4A_7C15);
    let mut z = *state;
    z = (z ^ (z >> 30)).wrapping_mul(0xBF58_476D_1CE4_E5B9);
    z = (z ^ (z >> 27)).wrapping_mul(0x94D0_49BB_1331_11EB);
    z ^ (z >> 31)
}

impl Xoshiro {
    pub fn from_seed(seed: u64) -> Self {
        let mut sm = seed;
        let s = [
            splitmix64(&mut sm),
            splitmix64(&mut sm),
            splitmix64(&mut sm),
            splitmix64(&mut sm),
        ];
        Xoshiro { s }
    }

    #[inline]
    pub fn next_u64(&mut self) -> u64 {
        let result = self.s[1].wrapping_mul(5).rotate_left(7).wrapping_mul(9);
        let t = self.s[1] << 17;
        self.s[2] ^= self.s[0];
        self.s[3] ^= self.s[1];
        self.s[1] ^= self.s[2];
        self.s[0] ^= self.s[3];
        self.s[2] ^= t;
        self.s[3] = self.s[3].rotate_left(45);
        result
    }

    /// ทศนิยมใน [0, 1) ความละเอียด 53 บิต
    #[inline]
    pub fn next_f64(&mut self) -> f64 {
        (self.next_u64() >> 11) as f64 * (1.0 / (1u64 << 53) as f64)
    }

    /// จำนวนเต็มใน [0, n) แบบไม่เอนเอียง (rejection)
    pub fn below(&mut self, n: u64) -> u64 {
        assert!(n > 0, "below(0)");
        let zone = u64::MAX - (u64::MAX % n + 1) % n;
        loop {
            let v = self.next_u64();
            if v <= zone {
                return v % n;
            }
        }
    }

    /// Fisher–Yates
    pub fn shuffle<T>(&mut self, v: &mut [T]) {
        for i in (1..v.len()).rev() {
            let j = self.below(i as u64 + 1) as usize;
            v.swap(i, j);
        }
    }

    /// ปกติมาตรฐาน (Box–Muller; ทิ้งค่าคู่เพื่อให้สถานะต่อคำเรียกคงที่)
    pub fn gauss(&mut self) -> f64 {
        let u1 = 1.0 - self.next_f64(); // (0,1]
        let u2 = self.next_f64();
        (-2.0 * u1.ln()).sqrt() * (std::f64::consts::TAU * u2).cos()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn golden_sequence_is_locked() {
        let mut r = Xoshiro::from_seed(0);
        let got: Vec<u64> = (0..3).map(|_| r.next_u64()).collect();
        // ค่าล็อกจากการรันครั้งแรก (xoshiro256** + splitmix64 seed 0)
        assert_eq!(got, GOLDEN_SEED0);
    }

    // ตรวจซ้ำด้วย xoshiro256** + splitmix64 ที่เขียนแยกใน Python — ตรงกันทั้งสามค่า
    const GOLDEN_SEED0: [u64; 3] = [0x99EC_5F36_CB75_F2B4, 0xBF6E_1F78_4956_452A, 0x1A5F_849D_4933_E6E0];

    #[test]
    fn below_is_in_range_and_unbiased_enough() {
        let mut r = Xoshiro::from_seed(7);
        let mut hist = [0u32; 6];
        for _ in 0..60_000 {
            hist[r.below(6) as usize] += 1;
        }
        for h in hist {
            assert!((9_000..11_000).contains(&h), "hist {hist:?}");
        }
    }

    #[test]
    fn shuffle_is_a_permutation() {
        let mut r = Xoshiro::from_seed(3);
        let mut v: Vec<u32> = (0..256).collect();
        r.shuffle(&mut v);
        let mut s = v.clone();
        s.sort();
        assert_eq!(s, (0..256).collect::<Vec<u32>>());
        assert_ne!(v, s);
    }

    #[test]
    fn same_seed_same_stream_different_seed_differs() {
        let mut a = Xoshiro::from_seed(42);
        let mut b = Xoshiro::from_seed(42);
        let mut c = Xoshiro::from_seed(43);
        let va: Vec<u64> = (0..16).map(|_| a.next_u64()).collect();
        let vb: Vec<u64> = (0..16).map(|_| b.next_u64()).collect();
        let vc: Vec<u64> = (0..16).map(|_| c.next_u64()).collect();
        assert_eq!(va, vb);
        assert_ne!(va, vc);
    }
}
