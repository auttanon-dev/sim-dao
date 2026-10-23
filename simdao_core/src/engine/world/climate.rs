//! ฤดูกาล อากาศ ธรรมชาติฟื้นตัว และปราณฟ้า

use crate::engine::model::*;
use crate::engine::sim::Engine;
use crate::physics;

impl Engine {

    // ------------------------------------------------------------------ ฟ้าฝน
    /// ต้นปีของแต่ละแดน: ทอยภัยแล้ง/น้ำท่วม — ผลผลิตทั้งปีของแดนนั้นลดลง
    pub(crate) fn tick_weather(&mut self) {
        if self.day.rem_euclid(365) >= self.cfg.world_tick_days as i64 {
            return;
        }
        for w in 0..self.worlds.len() {
            if self.worlds[w].kind == WorldKind::Branch && self.worlds[w].places.len() < 3 {
                continue;
            }
            let roll = self.rng.next_f64();
            let (mult, kind, text) = if roll < 0.07 {
                (0.45 + 0.2 * self.rng.next_f64(), "ภัยแล้ง", "ฝนไม่ตกทั้งปี ข้าวในนาแห้งตาย")
            } else if roll < 0.11 {
                (0.65 + 0.15 * self.rng.next_f64(), "น้ำท่วม", "น้ำหลากท่วมไร่นา")
            } else {
                continue;
            };
            self.worlds[w].harvest_mult = mult;
            self.worlds[w].harvest_until = self.day + 365;
            let place = self.worlds[w].places.first().copied().unwrap_or(0);
            let wn = self.worlds[w].name.clone();
            self.emit_at(kind, w as u16, place, kind, format!("{}: {} — ผลผลิตเหลือราว {:.0}%", wn, text, mult * 100.0));
            // น้ำท่วมพัดยุ้งฉางเสียหาย
            if kind == "น้ำท่วม" {
                for q in self.worlds[w].places.clone() {
                    let lost = self.places[q as usize].granary * 0.2;
                    self.places[q as usize].granary -= lost;
                    self.ledger.food("spoiled", lost);
                }
            }
        }
    }

    pub(crate) fn season(&self) -> f64 {
        // ปีละหนึ่งรอบ — ฤดูเก็บเกี่ยวกลางปี
        let phase = (self.day.rem_euclid(365)) as f64 / 365.0 * std::f64::consts::TAU;
        1.0 + self.cfg.season_amp * (phase - std::f64::consts::FRAC_PI_2).sin()
    }

    pub(crate) fn tick_nature(&mut self, days: f64) {
        let r = self.cfg.eco_regen_per_day;
        for i in 0..self.places.len() {
            if self.place_world[i].is_none() {
                continue;
            }
            for m in Material::ALL {
                let k = self.eco_k(i, m);
                let now = self.places[i].stock[m as usize];
                // เมล็ดพันธุ์จากที่ใกล้เคียง — ที่ที่ถูกขุดจนหมดยังฟื้นได้ช้าๆ
                let seeded = now.max(k * 0.01);
                self.places[i].stock[m as usize] = physics::logistic_growth(seeded, k, r, days);
            }
        }
    }

    // ------------------------------------------------------------------ ปราณฟ้า
    pub(crate) fn tick_heaven(&mut self, days: f64) {
        let mut mortals = vec![0usize; self.worlds.len()];
        for &id in &self.alive {
            let p = &self.people[id as usize];
            if !p.cultivator {
                mortals[p.world as usize] += 1;
            }
        }
        for (w, world) in self.worlds.iter_mut().enumerate() {
            let grown = physics::logistic_growth(world.heaven.max(1.0), world.cap, self.cfg.heaven_regen_per_day, days);
            let seeded = grown + mortals[w] as f64 * self.cfg.life_inflow * days / 365.0;
            world.heaven = seeded.clamp(0.0, world.cap);
        }
    }
}
