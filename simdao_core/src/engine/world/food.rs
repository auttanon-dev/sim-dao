//! อาหาร — ผลผลิต ยุ้งฉาง การกิน และการปรับแรงงาน

use crate::engine::geo;
use crate::engine::model::*;
use crate::engine::sim::Engine;

impl Engine {

    pub(crate) fn tick_food(&mut self, days: f64) {
        let n = self.places.len();
        // ---- ผลิต: แรงงานผลตอบแทนลดลงบนที่ดินจำกัด
        let mut labour = vec![0.0f64; n];
        let mut eaters: Vec<Vec<Pid>> = vec![Vec::new(); n];
        let ids: Vec<Pid> = self.alive.iter().copied().collect();
        for &id in &ids {
            let p = &self.people[id as usize];
            if p.process.is_some() {
                continue;
            }
            if self.is_adult(id) && self.is_farmer(id) && p.injury < 0.6 {
                labour[p.place as usize] += 1.0;
            }
        }
        for &id in &ids {
            if self.eats(id) && !self.people[id as usize].travelling() {
                eaters[self.people[id as usize].place as usize].push(id);
            }
        }
        let season = self.season();
        for i in 0..n {
            if labour[i] <= 0.0 {
                continue;
            }
            let cap = self.cfg.land_cap_day;
            // ดินเสื่อมเมื่อพืชพรรณรอบที่นาถูกเก็บจนหมด
            let fert = 1.0 - 0.4 * (1.0 - (self.places[i].stock[0] / self.eco_k(i, Material::Herb)).min(1.0));
            let weather = match self.place_world[i] {
                Some(w) if self.worlds[w as usize].harvest_until > self.day => self.worlds[w as usize].harvest_mult,
                _ => 1.0,
            };
            let per_day = cap * (1.0 - (-labour[i] * self.cfg.per_worker_day / cap).exp()) * season * fert * weather;
            let made = per_day * days;
            self.places[i].granary += made;
            self.places[i].produced_month = made;
            self.ledger.food("produced", made);
        }
        // ---- เน่าเสีย
        let keep = (-self.cfg.spoil_per_year * days / 365.0).exp();
        for i in 0..n {
            let g = self.places[i].granary;
            if g > 0.0 {
                let lost = g * (1.0 - keep);
                self.places[i].granary -= lost;
                self.ledger.food("spoiled", lost);
            }
        }
        // ---- กิน: ยุ้งฉางที่นั่น → ยุ้งฉางใกล้เคียง (เสียระหว่างขนส่ง) → เสบียงติดตัว
        for i in 0..n {
            if eaters[i].is_empty() {
                continue;
            }
            let need: f64 = eaters[i].iter().map(|&id| self.ration(id) * days).sum();
            let mut got = self.places[i].granary.min(need);
            self.places[i].granary -= got;
            if got < need {
                let near = geo::within(i as u32, self.cfg.reach_hops);
                for &(j, h) in near.iter() {
                    if j as usize == i || self.place_world[j as usize] != self.place_world[i] {
                        continue;
                    }
                    let keep_there: f64 = 0.0;
                    let avail = (self.places[j as usize].granary - keep_there).max(0.0);
                    if avail <= 0.0 {
                        continue;
                    }
                    let eff = (1.0 - self.cfg.carry_loss_per_hop).powi(h as i32);
                    let want = (need - got) / eff;
                    let take = avail.min(want);
                    self.places[j as usize].granary -= take;
                    self.ledger.food("carried_lost", take * (1.0 - eff));
                    got += take * eff;
                    if got >= need - 1e-9 {
                        break;
                    }
                }
            }
            self.ledger.food("eaten", got);
            // แบ่งเท่ากันตามความต้องการ ส่วนที่ขาดกินจากเสบียงติดตัว
            let share = if need > 0.0 { got / need } else { 1.0 };
            let price = self.cfg.food_price;
            for &id in &eaters[i].clone() {
                let want = self.ration(id) * days;
                let fed = want * share;
                // ค่าข้าว: จ่ายเข้าลิ้นชักของที่นั้น (ไปเป็นค่าแรงของคนทำนา) — จ่ายไม่ไหวก็ยังได้กิน
                let pay = (fed * price).min(self.people[id as usize].gold.max(0.0));
                self.people[id as usize].gold -= pay;
                self.places[i].till += pay;
                let short = want - fed;
                let p = &mut self.people[id as usize];
                let from_pack = (p.pack as f64).min(short);
                p.pack -= from_pack as f32;
                self.ledger.food("eaten", from_pack);
                let unmet = short - from_pack - self.feed_from_family(id, short - from_pack);
                self.hunger(id, unmet, want, days);
            }
        }
        // ---- ผู้เดินทางกินเสบียงติดตัว
        for &id in &ids {
            if !self.eats(id) || !self.people[id as usize].travelling() {
                continue;
            }
            // กินเฉพาะวันที่อยู่บนทางจริงในรอบนี้ (ทางสั้นกว่าหนึ่งรอบนาฬิกาไม่ต้องจ่ายทั้งเดือน)
            let on_road = match self.people[id as usize].process {
                Some(Process::Travel { since, arrive, .. }) => {
                    (arrive.min(self.day) - since.max(self.day - days as i64)).clamp(0, days as i64) as f64
                }
                _ => days,
            };
            if on_road <= 0.0 {
                continue;
            }
            let want = self.ration(id) * on_road;
            let p = &mut self.people[id as usize];
            let ate = (p.pack as f64).min(want);
            p.pack -= ate as f32;
            self.ledger.food("eaten", ate);
            let unmet = want - ate - self.feed_from_family(id, want - ate);
            self.hunger(id, unmet, want, on_road);
        }
        // ---- เติมเสบียงจากส่วนเกินของยุ้งฉาง (ซื้อ)
        for &id in &ids {
            let p = &self.people[id as usize];
            if !p.alive || p.process.is_some() || !self.eats(id) {
                continue;
            }
            let i = p.place as usize;
            let local_need: f64 = eaters[i].iter().map(|&e| self.ration(e)).sum::<f64>() * 60.0;
            let surplus = (self.places[i].granary - local_need).max(0.0);
            let room = (self.cfg.pack_days * self.ration(id) - p.pack as f64).max(0.0);
            let afford = (p.gold / self.cfg.food_price).max(0.0);
            let take = surplus.min(room).min(afford);
            if take > 0.0 {
                self.places[i].granary -= take;
                let cost = take * self.cfg.food_price;
                let p = &mut self.people[id as usize];
                p.pack += take as f32;
                p.gold -= cost;
                self.places[i].till += cost;
            }
        }
        // ---- ยุ้งฉางล้น (ที่เก็บจำกัด)
        for i in 0..n {
            let need_day: f64 = eaters[i].iter().map(|&e| self.ration(e)).sum::<f64>().max(5.0);
            let cap = need_day * self.cfg.store_months * 365.0 / 12.0 + self.places[i].produced_month * 1.5;
            if self.places[i].granary > cap {
                let over = self.places[i].granary - cap;
                self.places[i].granary = cap;
                self.ledger.food("spoiled", over);
            }
        }
        // ---- อดตาย / ลงไร่เมื่อขาด
        for &id in &ids {
            if !self.people[id as usize].alive {
                continue;
            }
            if self.people[id as usize].hunger_days as f64 >= self.cfg.starve_days {
                self.kill(id, None, "อดอยากจนสิ้นใจ", true);
            }
        }
        self.adapt_labour(&eaters);
    }

    /// ที่ที่ข้าวไม่พอ ผู้ใหญ่ที่ไม่ได้ทำนาลงไร่ · ที่ที่ข้าวเหลือเฟือ กลับไปทำงานเดิม
    pub(crate) fn adapt_labour(&mut self, eaters: &[Vec<Pid>]) {
        for i in 0..self.places.len() {
            if eaters[i].is_empty() {
                continue;
            }
            let need_month: f64 = eaters[i].iter().map(|&e| self.ration(e)).sum::<f64>() * 30.0;
            let g = self.places[i].granary;
            if g < need_month * 0.5 {
                let cand: Vec<Pid> = eaters[i]
                    .iter()
                    .copied()
                    .filter(|&e| self.is_adult(e) && !self.is_farmer(e) && self.people[e as usize].injury < 0.6)
                    .collect();
                let want = ((need_month - g) / (self.cfg.per_worker_day * 30.0)).ceil() as usize;
                for &e in cand.iter().take(want.max(1)) {
                    self.people[e as usize].fieldwork = true;
                }
            } else if g > need_month * 3.0 {
                for &e in &eaters[i] {
                    self.people[e as usize].fieldwork = false;
                }
            }
        }
    }
}
