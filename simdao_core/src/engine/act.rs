//! เทิร์นของคน — เลือกการกระทำจากสภาพของตัวเองและสิ่งรอบตัว แล้วลงมือ
//!
//! การเลือกเป็นแบบน้ำหนัก (ไม่ใช่ argmax) — คนในสภาพเดียวกันไม่จำเป็นต้องทำเหมือนกัน
//! แต่ความต้องการที่เร่งด่วนกว่า (หิว บาดเจ็บ แค้น ถึงจังหวะข้ามขั้น) มีน้ำหนักมากกว่ามาก

use super::data;
use super::geo;
use super::model::*;
use super::sim::Engine;
use crate::physics;

#[derive(Clone, Copy, Debug, PartialEq)]
pub enum Act {
    Work,
    Rest,
    BeginPath,
    Cultivate,
    Seclude,
    Breakthrough,
    Ascend,
    Harvest(Material),
    Sell,
    Wander,
    SeekFood(u32),
    SeekQi(u32),
    GoHome(u32),
    Court(Pid),
    Duel(Pid),
    Revenge(Pid),
    Rob(Pid),
    JoinSect(u32),
    FoundSect,
    Teach(Pid),
    Heal(Pid),
    Brew,
    Forge,
    Arrest(Pid),
}

impl Engine {
    pub fn turn(&mut self, id: Pid) {
        // ---- กิจกรรมยาวที่ทำค้างอยู่
        match self.people[id as usize].process.clone() {
            Some(Process::Travel { dest, arrive, .. }) => {
                if self.day < arrive {
                    self.schedule(id, arrive - self.day);
                } else {
                    self.arrive(id, dest);
                    let gap = self.range(1, 10);
                    self.schedule(id, gap);
                }
                return;
            }
            Some(Process::Jail { until }) => {
                if self.day < until {
                    self.schedule(id, until - self.day);
                } else {
                    self.people[id as usize].process = None;
                    let n = self.people[id as usize].name.clone();
                    self.emit("พ้นโทษ", Some(id), None, "พ้นโทษ", format!("{}พ้นโทษออกจากคุก", n));
                    let gap = self.range(5, 30);
                    self.schedule(id, gap);
                }
                return;
            }
            Some(Process::Seclusion { until, .. }) => {
                if self.day < until {
                    self.schedule(id, until - self.day);
                } else {
                    self.emerge(id);
                }
                return;
            }
            None => {}
        }
        if !self.is_adult(id) {
            self.childhood(id);
            return;
        }
        let act = self.choose(id);
        let gap = self.perform(id, act);
        if self.people[id as usize].alive {
            self.schedule(id, gap);
        }
    }

    fn childhood(&mut self, id: Pid) {
        // เด็กช่วยงานบ้านและเรียนรู้จากพ่อแม่ — ลูกของผู้บำเพ็ญได้เห็นวิถีตั้งแต่เล็ก
        let p = &self.people[id as usize];
        let parent_cult = p.parents.iter().flatten().any(|&q| self.people[q as usize].cultivator);
        if parent_cult && p.root >= self.cfg.root_cultivate_min as f32 {
            self.people[id as usize].insight += 0.05;
        }
        let gap = self.range(60, 240);
        self.schedule(id, gap);
    }

    // ------------------------------------------------------------------ เลือก
    pub fn choose(&mut self, id: Pid) -> Act {
        let mut menu: Vec<(Act, f64)> = Vec::with_capacity(16);
        let day = self.day;
        let p = self.people[id as usize].clone();
        let world = self.worlds[p.world as usize].clone();
        let here = self.present_at(p.place);
        let others: Vec<Pid> = here.iter().copied().filter(|&o| o != id && self.is_adult(o)).collect();
        let age = p.age(day);

        // ---- ปากท้อง
        let eats = self.eats(id);
        let local = self.places[p.place as usize].granary;
        let hungry = eats && p.hunger_days > 0.0;
        let locals = here.len() as f64 * self.cfg.ration_adult * 30.0;
        if hungry && local < locals {
            if let Some(dest) = self.food_destination(id) {
                menu.push((Act::SeekFood(dest), 40.0 + p.hunger_days as f64 * 2.0));
            }
        }

        // ---- ร่างกาย
        if p.injury > 0.4 {
            menu.push((Act::Rest, 20.0 * p.injury as f64));
        }

        // ---- งาน
        menu.push((Act::Work, if p.cultivator { 4.0 } else { 14.0 } + if p.gold < 5.0 { 10.0 } else { 0.0 }));

        // ---- วัตถุดิบ
        let d = data::world();
        if let Some(m) = d.places[p.place as usize].material.as_deref().and_then(Material::from_th) {
            let st = self.places[p.place as usize].stock[m as usize] / self.cfg.eco_cap;
            menu.push((Act::Harvest(m), 5.0 * st * (0.5 + p.greed as f64)));
        }
        let held: f32 = p.mats.iter().sum();
        if held > 4.0 {
            menu.push((Act::Sell, 3.0 + held as f64 * 0.5));
        }

        // ---- วิถีบำเพ็ญ
        if !p.cultivator {
            if p.root >= self.cfg.root_cultivate_min as f32 && age < 40.0 {
                let teacher = p.parents.iter().flatten().any(|&q| self.people[q as usize].cultivator)
                    || others.iter().any(|&o| self.people[o as usize].cultivator && self.people[o as usize].realm >= 2);
                menu.push((Act::BeginPath, (p.root as f64) * if teacher { 8.0 } else { 1.5 } * (0.5 + p.ambition as f64)));
            }
        } else {
            let need = self.need(id);
            let progress = p.insight / need;
            let cap = self.cfg.realm_cap_of_tier(p.tier(self.cfg.realm_band));
            menu.push((Act::Cultivate, 12.0 * (0.4 + p.root as f64)));
            if progress < 0.9 && (p.realm >= self.cfg.bigu_realm || p.pack > 60.0) {
                menu.push((Act::Seclude, 3.0 + 4.0 * p.ambition as f64));
            }
            if p.realm < cap && progress >= self.cfg.break_look_ahead {
                let odds = self.break_odds(id);
                let life_left = (self.lifespan_of(id) - age).max(0.1) * 365.0;
                let z_rate = 0.5 / 365.0; // ความเข้าใจที่เพิ่มต่อวันดันกำแพงลงราวนี้
                let wait = physics::best_wait_days(odds, z_rate, life_left, Some(3650.0));
                let w = if wait < 180.0 { 30.0 } else { 4.5 };
                menu.push((Act::Breakthrough, w));
            }
            if p.realm == cap && world.up.is_some() && progress >= 1.0 {
                menu.push((Act::Ascend, 10.0 + 10.0 * p.ambition as f64));
            }
            // ไปหาที่ปราณหนา
            if self.qi[p.place as usize] < 0.55 {
                if let Some(dest) = self.qi_destination(id) {
                    menu.push((Act::SeekQi(dest), 3.0));
                }
            }
            // สำนัก
            match p.sect {
                None if p.realm <= self.cfg.sect_join_realm_max + p.tier(self.cfg.realm_band) * self.cfg.realm_band => {
                    if let Some(s) = self.sect_nearby(id) {
                        menu.push((Act::JoinSect(s), 5.0 * p.loyalty as f64 + 1.0));
                    }
                }
                None if p.realm % self.cfg.realm_band >= self.cfg.found_sect_realm && p.ambition > 0.5 => {
                    menu.push((Act::FoundSect, 3.0 * p.ambition as f64));
                }
                Some(s) => {
                    let home = self.sects[s as usize].home;
                    if home != p.place && self.chance(0.3) {
                        menu.push((Act::GoHome(home), 2.0));
                    }
                }
                _ => {}
            }
            // สอนศิษย์ที่อยู่ด้วยกัน
            if p.realm >= 3 {
                if let Some(&stu) = others.iter().find(|&&o| {
                    let q = &self.people[o as usize];
                    q.cultivator && q.realm + 2 <= p.realm && (q.master == Some(id) || (q.sect.is_some() && q.sect == p.sect))
                }) {
                    menu.push((Act::Teach(stu), 3.0 + 4.0 * p.compassion as f64));
                }
            }
        }

        // ---- ผู้คน
        if p.spouse.is_none() && age >= self.cfg.marry_min_age && age < 55.0 {
            let mate = others.iter().copied().find(|&o| {
                let q = &self.people[o as usize];
                q.female != p.female && q.spouse.is_none() && q.age(day) >= self.cfg.marry_min_age && q.age(day) < 55.0
                    && !p.parents.contains(&Some(o)) && !q.parents.contains(&Some(id))
                    && p.parents.iter().flatten().all(|pp| !q.parents.contains(&Some(*pp)))
                    && p.grudge(o) == 0
            });
            if let Some(m) = mate {
                menu.push((Act::Court(m), 9.0));
            }
        }
        // ล้างแค้น — ศัตรูที่อยู่ตรงหน้า
        if let Some((&foe, &g)) = p.rivals.iter().filter(|(f, _)| others.contains(f)).max_by_key(|(_, &g)| g) {
            if g >= 2 {
                menu.push((Act::Revenge(foe), 1.5 * g as f64 * (1.0 - 0.6 * p.compassion as f64)));
            }
        }
        if p.cultivator && !others.is_empty() && p.injury < 0.3 {
            let rival = others[self.rng.below(others.len() as u64) as usize];
            let q = &self.people[rival as usize];
            if q.cultivator && (q.realm as i32 - p.realm as i32).abs() <= 2 {
                menu.push((Act::Duel(rival), 0.4 + 1.2 * p.ambition as f64));
            }
        }
        if p.greed > 0.6 && p.compassion < 0.4 && !others.is_empty() {
            let mark = others[self.rng.below(others.len() as u64) as usize];
            if self.people[mark as usize].gold > 20.0 {
                // ความเสี่ยงถูกโต้กลับในที่ที่เพิ่งมีการนองเลือด — คนระวังตัวมากกว่า
                let heat = physics::hawkes_intensity(0.2, Some(world.blood_marks.iter().map(|&d| d as f64).collect()), day as f64, self.cfg.hawkes_alpha, self.cfg.hawkes_decay_days);
                menu.push((Act::Rob(mark), 0.8 * p.greed as f64 / (1.0 + heat)));
            }
        }
        self.trade_options(id, &others, &mut menu);
        if self.profession_is(id, &super::trades::GUARDS) {
            if let Some(&crook) = others.iter().filter(|&&o| self.people[o as usize].crimes > 0).max_by_key(|&&o| (self.people[o as usize].crimes, std::cmp::Reverse(o))) {
                menu.push((Act::Arrest(crook), 8.0 + 4.0 * self.people[crook as usize].crimes as f64));
            }
        }
        menu.push((Act::Wander, 1.5));

        let total: f64 = menu.iter().map(|(_, w)| w.max(0.0)).sum();
        let mut r = self.rng.next_f64() * total;
        for (a, w) in &menu {
            let w = w.max(0.0);
            if r < w {
                return *a;
            }
            r -= w;
        }
        Act::Work
    }

    // ------------------------------------------------------------------ ลงมือ — คืนจำนวนวันถึงเทิร์นถัดไป
    pub fn perform(&mut self, id: Pid, act: Act) -> i64 {
        match act {
            Act::Work => self.range(15, 60),
            Act::Rest => {
                let p = &mut self.people[id as usize];
                p.injury *= 0.7;
                self.range(10, 40)
            }
            Act::BeginPath => self.begin_path(id),
            Act::Cultivate => self.cultivate(id),
            Act::Seclude => self.seclude(id),
            Act::Breakthrough => self.breakthrough(id),
            Act::Ascend => self.ascend(id),
            Act::Harvest(m) => self.harvest(id, m),
            Act::Sell => self.sell(id),
            Act::Wander => {
                let p = self.people[id as usize].place;
                let near = geo::within(p, 2);
                let w = self.people[id as usize].world;
                let opts: Vec<u32> = near.iter().map(|&(q, _)| q).filter(|&q| q != p && self.habitable(w, q)).collect();
                match self.pick(&opts) {
                    Some(dest) => self.depart(id, dest, "เดินทาง"),
                    None => self.range(10, 30),
                }
            }
            Act::SeekFood(dest) => self.depart(id, dest, "ย้ายหาข้าว"),
            Act::SeekQi(dest) => self.depart(id, dest, "ตามหาปราณ"),
            Act::GoHome(dest) => self.depart(id, dest, "กลับสำนัก"),
            Act::Court(m) => self.court(id, m),
            Act::Duel(t) => self.duel(id, t, false),
            Act::Revenge(t) => self.duel(id, t, true),
            Act::Rob(t) => self.rob(id, t),
            Act::JoinSect(s) => self.join_sect(id, s),
            Act::FoundSect => self.found_sect(id),
            Act::Teach(t) => self.teach(id, t),
            Act::Heal(t) => self.heal(id, t),
            Act::Brew => self.brew(id),
            Act::Forge => self.forge(id),
            Act::Arrest(t) => self.arrest(id, t, None),
        }
    }

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

    fn arrive(&mut self, id: Pid, dest: u32) {
        self.move_to(id, dest);
        let p = &mut self.people[id as usize];
        p.process = None;
        p.fieldwork = false;
    }

    /// ที่ใกล้สุดในแดนเดียวกันที่ยุ้งฉางยังมีข้าวพอเลี้ยงอีกหลายเดือน
    fn food_destination(&self, id: Pid) -> Option<u32> {
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
    fn qi_destination(&self, id: Pid) -> Option<u32> {
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

    // ------------------------------------------------------------------ วัตถุดิบและการค้า
    fn harvest(&mut self, id: Pid, m: Material) -> i64 {
        let place = self.people[id as usize].place as usize;
        let stock = self.places[place].stock[m as usize];
        // ยิ่งเหลือน้อยยิ่งหายาก (ผลตอบแทนตามความหนาแน่น)
        let take = (self.cfg.harvest_per_trip * stock / self.cfg.eco_cap).min(stock);
        self.places[place].stock[m as usize] -= take;
        self.people[id as usize].mats[m as usize] += take as f32;
        // ล่าแก่นพลังเสี่ยงบาดเจ็บ
        if m == Material::Core && self.chance(0.15) {
            let p = &mut self.people[id as usize];
            p.injury = (p.injury + 0.25).min(1.0);
        }
        self.range(10, 45)
    }

    fn sell(&mut self, id: Pid) -> i64 {
        // ขายให้ตลาด: ราคาตามความขาดแคลนของของชนิดนั้นในแดน · เงินมาจากลิ้นชักและคลังชุมชนของที่นั้น
        let place = self.people[id as usize].place as usize;
        let world = self.people[id as usize].world as usize;
        let mut earned = 0.0;
        for m in Material::ALL {
            let qty = self.people[id as usize].mats[m as usize] as f64;
            if qty <= 0.0 {
                continue;
            }
            let supply: f64 = self.worlds[world].places.iter().map(|&q| self.places[q as usize].stock[m as usize]).sum::<f64>()
                / self.worlds[world].places.len().max(1) as f64;
            let price = physics::scarcity_price(self.cfg.material_price, self.cfg.eco_cap * 0.5, supply.max(1.0), 0.6, 0.3, 4.0);
            let funds = self.places[place].till + self.places[place].treasury;
            let value = (qty * price).min(funds);
            if value <= 0.0 {
                continue;
            }
            let from_till = value.min(self.places[place].till);
            self.places[place].till -= from_till;
            self.places[place].treasury -= value - from_till;
            let sold = value / price;
            self.people[id as usize].mats[m as usize] -= sold as f32;
            self.people[id as usize].gold += value;
            // ของที่ขายกลับเข้าสู่การใช้งานของชุมชน (ยา เครื่องมือ) — ไม่กลับเข้าธรรมชาติ
            earned += value;
        }
        if earned > 20.0 {
            let n = self.people[id as usize].name.clone();
            self.emit("ค้าขาย", Some(id), None, "ขายของ", format!("{}ขายวัตถุดิบได้ {:.0} ตำลึง", n, earned));
        }
        self.range(5, 25)
    }

    // ------------------------------------------------------------------ ครอบครัว
    fn court(&mut self, id: Pid, other: Pid) -> i64 {
        let b = {
            let p = self.people[id as usize].bonds.entry(other).or_insert(0);
            *p += 1;
            *p
        };
        *self.people[other as usize].bonds.entry(id).or_insert(0) += 1;
        let q = &self.people[other as usize];
        let willing = q.spouse.is_none() && self.people[id as usize].spouse.is_none() && q.alive;
        if willing && b >= 3 && self.chance(0.5) {
            self.people[id as usize].spouse = Some(other);
            self.people[other as usize].spouse = Some(id);
            let (a, c) = (self.people[id as usize].name.clone(), self.people[other as usize].name.clone());
            self.emit("แต่งงาน", Some(id), Some(other), "ครองคู่", format!("{}และ{}ครองคู่กัน", a, c));
        }
        self.range(15, 60)
    }
}
