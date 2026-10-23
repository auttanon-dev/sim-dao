//! ตัวชี้วัดระยะยาว — ประชากร สำนัก เมือง คลัง บัญชี และอัตราเหตุการณ์ต่อแดน
//!
//! อ่านอย่างเดียว ไม่แตะสถานะของโลก (เปิดดูกี่ครั้งก็ไม่เปลี่ยนผลจำลอง)

use super::sim::Engine;
use serde::Serialize;
use std::collections::BTreeMap;

#[derive(Clone, Debug, Serialize)]
pub struct Metrics {
    pub year: f64,
    pub alive: usize,
    pub cultivators: usize,
    pub sects: usize,
    pub cities_ruled: usize,
    pub cities: usize,
    pub gold_people: f64,
    pub gold_sects: f64,
    pub gold_places: f64,
    pub food_delta: f64,
    pub gold_delta: f64,
    pub steps: u64,
    pub events: u64,
}

impl Engine {
    pub fn metrics(&self) -> Metrics {
        let alive = self.alive.len();
        let cultivators = self.alive.iter().filter(|&&i| self.people[i as usize].cultivator).count();
        Metrics {
            year: self.day as f64 / 365.0,
            alive,
            cultivators,
            sects: self.sects.iter().filter(|s| s.alive).count(),
            cities_ruled: self.cities.iter().filter(|c| c.ruler.is_some()).count(),
            cities: self.cities.len(),
            gold_people: self.alive.iter().map(|&i| self.people[i as usize].gold).sum(),
            gold_sects: self.sects.iter().filter(|s| s.alive).map(|s| s.treasury).sum(),
            gold_places: self.places.iter().map(|p| p.till + p.treasury).sum(),
            food_delta: self.total_food() - self.ledger_food(),
            gold_delta: self.total_gold() - self.ledger_gold(),
            steps: self.steps,
            events: self.seq,
        }
    }
}

/// เก็บตัวอย่างตามช่วงเวลา และนับเหตุการณ์ที่บันทึกต่อแดนต่อปี
pub struct Probe {
    pub samples: Vec<Metrics>,
    pub events_per_world: BTreeMap<u16, u64>,
    pub kinds: BTreeMap<String, u64>,
    last_seq: u64,
}

impl Probe {
    pub fn new(e: &Engine) -> Probe {
        Probe { samples: vec![e.metrics()], events_per_world: BTreeMap::new(), kinds: BTreeMap::new(), last_seq: e.seq }
    }

    /// เรียกบ่อยกว่าที่ log_keep จะล้น (รายปีพอ)
    pub fn sample(&mut self, e: &Engine) {
        for ev in e.log.iter().filter(|ev| ev.seq > self.last_seq) {
            *self.events_per_world.entry(ev.world).or_insert(0) += 1;
            *self.kinds.entry(ev.kind.clone()).or_insert(0) += 1;
        }
        self.last_seq = e.seq;
        self.samples.push(e.metrics());
    }

    /// เหตุการณ์ที่บันทึกต่อแดนต่อปี (เฉลี่ยตลอดช่วง)
    pub fn events_per_world_year(&self) -> BTreeMap<u16, f64> {
        let years = (self.samples.last().unwrap().year - self.samples[0].year).max(1e-9);
        self.events_per_world.iter().map(|(&w, &n)| (w, n as f64 / years)).collect()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::engine::config::Config;

    /// ประชากรในช่วงที่รับได้ และบัญชีปิดตลอดการจำลองยาว (รันด้วย --ignored)
    #[test]
    #[ignore]
    fn long_run_300_years() {
        let mut e = Engine::new(1, Config::default());
        let mut pr = Probe::new(&e);
        for y in 1..=300 {
            e.run_until(y * 365);
            pr.sample(&e);
            let m = pr.samples.last().unwrap();
            assert!(m.food_delta.abs() < 1e-3 * e.ledger_food().max(1.0), "food off {} at y{}", m.food_delta, y);
            assert!(m.gold_delta.abs() < 1e-6 * e.ledger_gold().max(1.0), "gold off {} at y{}", m.gold_delta, y);
        }
        let first = pr.samples[0].alive as f64;
        let last = pr.samples.last().unwrap().alive as f64;
        assert!(last > first * 0.3, "population collapsed {} -> {}", first, last);
    }

    #[test]
    #[ignore]
    fn long_run_is_deterministic() {
        let run = || {
            let mut e = Engine::new(2, Config::default());
            e.run_until(100 * 365);
            crate::engine::sim::tests::state_hash(&e)
        };
        assert_eq!(run(), run());
    }

    #[test]
    fn metrics_do_not_disturb_the_world() {
        let mut a = Engine::new(4, Config::default());
        let mut b = Engine::new(4, Config::default());
        let mut pr = Probe::new(&a);
        for y in 1..=5 {
            a.run_until(y * 365);
            pr.sample(&a);
        }
        b.run_until(5 * 365);
        assert_eq!(crate::engine::sim::tests::state_hash(&a), crate::engine::sim::tests::state_hash(&b));
        assert_eq!(pr.samples.len(), 6);
    }
}
