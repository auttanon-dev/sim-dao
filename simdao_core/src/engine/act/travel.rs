//! การเดินทาง — ระยะทาง เสบียง ที่หมายหาอาหาร/ปราณ

use crate::engine::geo;
use crate::engine::model::*;
use crate::engine::sim::Engine;

impl Engine {

    pub fn habitable(&self, world: u16, place: u32) -> bool {
        self.place_world[place as usize] == Some(world) && self.worlds[world as usize].places.binary_search(&place).is_ok()
    }

    // ------------------------------------------------------------------ การเดินทาง
    pub fn travel_days(&self, id: Pid, from: u32, to: u32) -> i64 {
        let p = &self.people[id as usize];
        let speed = self.cfg.travel_speed * (1.0 + self.cfg.travel_speed_per_realm * p.realm as f64) * (1.0 - 0.6 * p.injury as f64);
        let dist = geo::distance(from, to);
        if !dist.is_finite() {
            return i64::MAX / 4;
        }
        ((dist / speed.max(0.1)).ceil() as i64).max(1)
    }

    pub fn depart(&mut self, id: Pid, dest: u32, why: &str) -> i64 {
        let from = self.people[id as usize].place;
        let days = self.travel_days(id, from, dest);
        if days > 3650 {
            return self.range(10, 30);
        }
        // เสบียง: ซื้อจากยุ้งฉางที่นี่ให้พอทั้งทาง แล้วจึงออกเดิน (ย้ายหาข้าวไม่มีทางเลือก ไปทั้งที่ไม่พอ)
        let need = if self.eats(id) { self.ration(id) * days as f64 } else { 0.0 };
        self.provision(id, need);
        if why != "ย้ายหาข้าว" && (self.people[id as usize].pack as f64) < need {
            return self.range(5, 20);
        }
        let arrive = self.day + days;
        self.people[id as usize].process = Some(Process::Travel { dest, since: self.day, arrive });
        // ครอบครัวไปด้วยกัน — คู่ครองและลูกเล็กที่อยู่ที่เดียวกัน ว่างอยู่ และมีเสบียงพอ
        // (ผู้นำซื้อเสบียงให้ลูก · คู่ครองที่เสบียงไม่พอรออยู่บ้าน)
        let leader_spare = |e: &Engine| (e.people[id as usize].pack as f64 - need).max(0.0);
        for f in self.family_at(id, from) {
            let fneed = if self.eats(f) { self.ration(f) * days as f64 } else { 0.0 };
            self.provision(f, fneed);
            let mut have = self.people[f as usize].pack as f64;
            if !self.is_adult(f) && have < fneed {
                self.provision(id, need + fneed - have);
                let give = leader_spare(self).min(fneed - have);
                self.people[id as usize].pack -= give as f32;
                self.people[f as usize].pack += give as f32;
                have += give;
            }
            if have >= fneed || why == "ย้ายหาข้าว" {
                self.people[f as usize].process = Some(Process::Travel { dest, since: self.day, arrive });
                self.schedule(f, days);
            }
        }
        if days >= 30 {
            let (n, a, b) = (self.people[id as usize].name.clone(), self.place_name(from), self.place_name(dest));
            self.emit(why, Some(id), None, "ออกเดินทาง", format!("{}ออกจาก{}มุ่งหน้าสู่{} ({} วัน)", n, a, b, days));
        }
        days
    }

    /// ซื้อเสบียงจากยุ้งฉางของที่ที่อยู่ให้ถึง `target` สำรับ (เท่าที่ยุ้งฉางมีและเงินพอ)
    pub fn provision(&mut self, id: Pid, target: f64) {
        let p = &self.people[id as usize];
        let want = (target - p.pack as f64).max(0.0);
        if want <= 0.0 {
            return;
        }
        let i = p.place as usize;
        let afford = (p.gold / self.cfg.food_price).max(0.0);
        let take = want.min(self.places[i].granary).min(afford);
        if take <= 0.0 {
            return;
        }
        let cost = take * self.cfg.food_price;
        self.places[i].granary -= take;
        self.places[i].till += cost;
        let p = &mut self.people[id as usize];
        p.pack += take as f32;
        p.gold -= cost;
    }

    /// คู่ครองและลูกอายุต่ำกว่าวัยผู้ใหญ่ที่อยู่ที่ `place` และว่างอยู่
    pub fn family_at(&self, id: Pid, place: u32) -> Vec<Pid> {
        let p = &self.people[id as usize];
        let mut out = Vec::new();
        let free = |q: Pid| {
            let x = &self.people[q as usize];
            x.alive && x.place == place && x.process.is_none()
        };
        if let Some(s) = p.spouse {
            if free(s) {
                out.push(s);
            }
        }
        let mut kids: Vec<Pid> = p.children.clone();
        if let Some(s) = p.spouse {
            kids.extend(self.people[s as usize].children.iter().copied());
        }
        kids.sort_unstable();
        kids.dedup();
        for k in kids {
            if !self.is_adult(k) && free(k) {
                out.push(k);
            }
        }
        out
    }

    pub(crate) fn arrive(&mut self, id: Pid, dest: u32) {
        self.move_to(id, dest);
        let p = &mut self.people[id as usize];
        p.process = None;
        p.fieldwork = false;
    }

    /// ที่ใกล้สุดในแดนเดียวกันที่ยุ้งฉางยังมีข้าวพอเลี้ยงอีกหลายเดือน
    pub(crate) fn food_destination(&self, id: Pid) -> Option<u32> {
        let p = &self.people[id as usize];
        let dist = geo::distances(p.place);
        let world = &self.worlds[p.world as usize];
        world
            .places
            .iter()
            .copied()
            .filter(|&q| q != p.place && self.places[q as usize].granary > 120.0 && dist[q as usize].is_finite())
            .min_by(|&a, &b| dist[a as usize].partial_cmp(&dist[b as usize]).unwrap().then(a.cmp(&b)))
    }

    /// ที่ที่ปราณหนากว่าที่นี่ชัดเจน ภายในระยะเดินไม่กี่สิบวัน
    pub(crate) fn qi_destination(&self, id: Pid) -> Option<u32> {
        let p = &self.people[id as usize];
        let here = self.qi[p.place as usize];
        let world = &self.worlds[p.world as usize];
        world
            .places
            .iter()
            .copied()
            .filter(|&q| self.qi[q as usize] > here + 0.15 && self.travel_days(id, p.place, q) < 60)
            .max_by(|&a, &b| self.qi[a as usize].partial_cmp(&self.qi[b as usize]).unwrap().then(b.cmp(&a)))
    }
}
