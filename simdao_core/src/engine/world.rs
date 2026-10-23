//! นาฬิกาโลก — ทุก world_tick_days วัน สิ่งที่เกิดกับทุกคนพร้อมกัน
//!
//! ลำดับต่อรอบ: แก่/ฟื้นตัว → อาหาร → ทอง → ธรรมชาติ → ปราณฟ้า → ครรภ์/คลอด → ข่าว → สำนัก
//! บัญชีอาหารและทองปิดได้เสมอ (ดู ledger_* ด้านล่าง และเทสต์ในไฟล์นี้)

use super::geo;
use super::model::*;
use super::sim::Engine;
use crate::physics;

impl Engine {
    pub fn world_tick(&mut self) {
        let days = self.cfg.world_tick_days as f64;
        self.tick_bodies(days);
        self.tick_weather();
        self.tick_disease(days);
        self.tick_food(days);
        self.tick_gold(days);
        self.tick_nature(days);
        self.tick_heaven(days);
        self.tick_families(days);
        self.deliver_news();
        self.tick_sects();
        self.tick_realms(days);
        self.tick_temptation(days);
        let horizon = self.day - 5 * 365;
        for w in self.worlds.iter_mut() {
            w.blood_marks.retain(|&d| d >= horizon);
        }
    }

    // ------------------------------------------------------------------ ฟ้าฝน
    /// ต้นปีของแต่ละแดน: ทอยภัยแล้ง/น้ำท่วม — ผลผลิตทั้งปีของแดนนั้นลดลง
    fn tick_weather(&mut self) {
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

    // ------------------------------------------------------------------ ร่างกาย
    fn tick_bodies(&mut self, days: f64) {
        let ids: Vec<Pid> = self.alive.iter().copied().collect();
        for id in ids {
            let lifespan = self.lifespan_of(id);
            let day = self.day;
            let band = self.cfg.realm_band;
            let p = &mut self.people[id as usize];
            let age = p.age(day);
            // แผลสมานแบบเอกซ์โพเนนเชียล — แผลหนักหายช้ากว่าแผลเบาเป็นสัดส่วนเดียวกัน
            p.injury = physics::relax(p.injury as f64, 0.0, self.cfg.injury_heal_per_day, days) as f32;
            // ความเสื่อมของผู้บำเพ็ญ: ยิ่งขั้นสูงยิ่งกัดกร่อน (ต้องบำเพ็ญชดเชย)
            if p.cultivator {
                let tier_realm = (p.realm % band) as f64;
                p.decay += self.cfg.decay_per_year * (1.0 + self.cfg.decay_per_realm_mult * tier_realm) * days / 365.0;
            }
            p.last_day = day;
            // ความแค้นและความผูกพันจางลงตามเวลา (ทอยปัดเศษแบบสุ่มให้ค่าเฉลี่ยตรงกับครึ่งชีวิต)
            let fade = 1.0 - 0.5f64.powf(days / 365.0 / self.cfg.grudge_half_life_years);
            let mut rivals = std::mem::take(&mut p.rivals);
            let mut bonds = std::mem::take(&mut p.bonds);
            rivals.retain(|_, g| { *g = self.rng_fade(*g, fade); *g > 0 });
            bonds.retain(|_, b| { *b = self.rng_fade(*b, fade * 0.5); *b > 0 });
            let p = &mut self.people[id as usize];
            p.rivals = rivals;
            p.bonds = bonds;
            // ตายตามวัย
            if age >= lifespan {
                let cause = if p.cultivator && p.realm > 0 { "สิ้นอายุขัยของผู้บำเพ็ญ" } else { "ชราภาพ" };
                self.kill(id, None, cause, true);
                continue;
            }
            // วัยเด็กเปราะบาง — ไข้ป่วยที่ไม่มีใครรักษาได้
            let hazard = if age < 1.0 {
                self.cfg.infant_mortality
            } else if age < self.cfg.adult_age {
                self.cfg.child_mortality
            } else {
                0.0
            };
            if hazard > 0.0 && self.chance(physics::hazard_p(hazard, days)) {
                self.kill(id, None, "เจ็บป่วยในวัยเด็ก", true);
                continue;
            }
            // บาดแผลสาหัสที่ไม่หาย
            let p = &self.people[id as usize];
            if p.injury > 0.92 && self.chance(0.3) {
                self.kill(id, None, "บาดแผลสาหัสจนสิ้นใจ", true);
            }
        }
    }

    /// ลดค่าจำนวนเต็มลงตามสัดส่วน `fade` แบบปัดเศษสุ่ม — ค่าเฉลี่ยลดตรงตามครึ่งชีวิตแม้ค่าจะเล็ก
    fn rng_fade(&mut self, v: i16, fade: f64) -> i16 {
        let x = v as f64 * (1.0 - fade);
        let fl = x.floor();
        (fl + if self.rng.next_f64() < x - fl { 1.0 } else { 0.0 }) as i16
    }

    /// เด็กที่ขาดได้กินจากเสบียงของพ่อแม่ที่อยู่ด้วยกัน — คืนจำนวนที่ได้
    fn feed_from_family(&mut self, id: Pid, short: f64) -> f64 {
        if short <= 0.0 || self.is_adult(id) {
            return 0.0;
        }
        let p = &self.people[id as usize];
        let (place, travel) = (p.place, p.process.clone());
        let mut got = 0.0;
        for par in p.parents.into_iter().flatten() {
            let q = &mut self.people[par as usize];
            if !q.alive || q.place != place || q.process != travel {
                continue;
            }
            let give = (q.pack as f64).min(short - got);
            q.pack -= give as f32;
            got += give;
            if got >= short {
                break;
            }
        }
        self.ledger.food("eaten", got);
        got
    }

    fn hunger(&mut self, id: Pid, unmet: f64, want: f64, days: f64) {
        let p = &mut self.people[id as usize];
        if unmet > want * 0.05 {
            p.hunger_days += (days * unmet / want) as f32;
        } else {
            p.hunger_days = (p.hunger_days - days as f32).max(0.0);
        }
    }

    // ------------------------------------------------------------------ อาหาร
    pub fn eats(&self, id: Pid) -> bool {
        let p = &self.people[id as usize];
        p.alive && p.sentient && !p.is_chaos() && p.realm < self.cfg.bigu_realm && !p.dissolved()
    }

    pub fn ration(&self, id: Pid) -> f64 {
        let p = &self.people[id as usize];
        let base = if p.age(self.day) < self.cfg.adult_age { self.cfg.ration_child } else { self.cfg.ration_adult };
        base * if p.pregnant.is_some() { 1.2 } else { 1.0 }
    }

    pub fn is_farmer(&self, id: Pid) -> bool {
        let d = super::data::world();
        let p = &self.people[id as usize];
        let prof = &d.professions[p.profession as usize].0;
        p.fieldwork || matches!(prof.as_str(), "ชาวนา" | "คนสับฟืน" | "คนเลี้ยงสัตว์อสูร")
    }

    fn season(&self) -> f64 {
        // ปีละหนึ่งรอบ — ฤดูเก็บเกี่ยวกลางปี
        let phase = (self.day.rem_euclid(365)) as f64 / 365.0 * std::f64::consts::TAU;
        1.0 + self.cfg.season_amp * (phase - std::f64::consts::FRAC_PI_2).sin()
    }

    fn tick_food(&mut self, days: f64) {
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
    fn adapt_labour(&mut self, eaters: &[Vec<Pid>]) {
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

    // ------------------------------------------------------------------ ทอง
    fn tick_gold(&mut self, days: f64) {
        let ids: Vec<Pid> = self.alive.iter().copied().collect();
        // ใช้จ่ายส่วนเกินเงินเก็บในตลาดท้องถิ่น (สินค้า บริการ) → ลิ้นชักของที่นั้น
        let frac = 1.0 - (-self.cfg.spend_rate * days / 365.0).exp();
        for &id in &ids {
            let p = &self.people[id as usize];
            if p.process.is_some() {
                continue;
            }
            let spend = (p.gold - self.cfg.keep_gold).max(0.0) * frac;
            if spend > 0.0 {
                let place = p.place as usize;
                self.people[id as usize].gold -= spend;
                // ภาษีสำนักของสมาชิก
                if let Some(s) = self.people[id as usize].sect {
                    let tithe = spend * self.cfg.sect_tithe;
                    self.sects[s as usize].treasury += tithe;
                    self.places[place].till += spend - tithe;
                } else {
                    self.places[place].till += spend;
                }
            }
        }
        // เหมือง: ทองใหม่เกิดที่แหล่งแร่ (แหล่งกำเนิดที่ประกาศ) แบ่งตามคนที่อยู่ที่นั่น
        let d = super::data::world();
        let ore_places: Vec<usize> = (0..self.places.len())
            .filter(|&i| self.place_world[i].is_some() && d.places[i].material.as_deref() == Some("แร่"))
            .collect();
        if !ore_places.is_empty() {
            let per = self.cfg.mine_gold_per_year * days / 365.0 / ore_places.len() as f64;
            for i in ore_places {
                let ore = self.places[i].stock[Material::Ore as usize] / self.cfg.eco_cap;
                let g = per * ore.min(1.0);
                self.places[i].till += g;
                self.ledger.gold("mined", g);
            }
        }
        // ค่าแรง: ลิ้นชักจ่ายให้ผู้ใหญ่ที่ทำงานที่นั่น — คนทำนาได้จากค่าข้าว คนอื่นได้จากการใช้จ่าย
        let mut workers: Vec<Vec<Pid>> = vec![Vec::new(); self.places.len()];
        for &id in &ids {
            let p = &self.people[id as usize];
            if p.process.is_none() && self.is_adult(id) && p.injury < 0.6 {
                workers[p.place as usize].push(id);
            }
        }
        for i in 0..self.places.len() {
            let till = self.places[i].till;
            if till <= 0.0 {
                continue;
            }
            if workers[i].is_empty() {
                // ไม่มีใครทำงานที่นี่ — ค่อยๆ ไหลเข้าคลังชุมชน
                let leak = till * 0.1;
                self.places[i].till -= leak;
                self.places[i].treasury += leak;
                continue;
            }
            let pay = till * 0.8;
            let each = pay / workers[i].len() as f64;
            for &w in &workers[i] {
                self.people[w as usize].gold += each;
            }
            self.places[i].till -= pay;
            self.ledger.gold("wages", pay);
        }
        // คลังชุมชนเลี้ยงเด็กกำพร้าและคนยากไร้ที่หิว
        for &id in &ids {
            let p = &self.people[id as usize];
            if !p.alive || p.gold > 1.0 || p.hunger_days <= 0.0 {
                continue;
            }
            let i = p.place as usize;
            let alms = self.places[i].treasury.min(5.0);
            if alms > 0.0 {
                self.places[i].treasury -= alms;
                self.people[id as usize].gold += alms;
                self.ledger.gold("alms", alms);
            }
        }
    }

    pub fn total_gold(&self) -> f64 {
        let people: f64 = self.alive.iter().map(|&i| self.people[i as usize].gold).sum();
        let places: f64 = self.places.iter().map(|p| p.till + p.treasury).sum();
        let sects: f64 = self.sects.iter().map(|s| s.treasury).sum();
        people + places + sects
    }

    pub fn total_food(&self) -> f64 {
        let packs: f64 = self.alive.iter().map(|&i| self.people[i as usize].pack as f64).sum();
        packs + self.places.iter().map(|p| p.granary).sum::<f64>()
    }

    /// อาหารที่ควรมีตามบัญชี (ต้องเท่ากับ total_food)
    pub fn ledger_food(&self) -> f64 {
        let g = |k: &str| self.ledger.food.get(k).copied().unwrap_or(0.0);
        g("endowed") + g("produced") - g("eaten") - g("spoiled") - g("carried_lost") - g("lost")
    }

    /// ทองที่ควรมีตามบัญชี (ต้องเท่ากับ total_gold)
    pub fn ledger_gold(&self) -> f64 {
        let g = |k: &str| self.ledger.gold.get(k).copied().unwrap_or(0.0);
        g("issued") + g("mined") - g("lost")
    }

    // ------------------------------------------------------------------ ธรรมชาติ
    /// เพดานธรรมชาติของวัตถุดิบชนิดหนึ่งที่สถานที่หนึ่ง — แหล่งที่ประกาศมีเต็ม ที่อื่นมีบ้าง
    pub fn eco_k(&self, place: usize, m: Material) -> f64 {
        let d = super::data::world();
        let full = d.places[place].material.as_deref().and_then(Material::from_th) == Some(m);
        if full { self.cfg.eco_cap } else { self.cfg.eco_cap * 0.15 }
    }

    fn tick_nature(&mut self, days: f64) {
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
    fn tick_heaven(&mut self, days: f64) {
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

    // ------------------------------------------------------------------ ครอบครัว
    fn tick_families(&mut self, days: f64) {
        let ids: Vec<Pid> = self.alive.iter().copied().collect();
        for &id in &ids {
            let p = &self.people[id as usize];
            if !p.alive {
                continue;
            }
            if let Some((due, _)) = p.pregnant {
                if due <= self.day {
                    self.give_birth(id);
                }
                continue;
            }
            if !p.female {
                continue;
            }
            if let Some(s) = p.spouse {
                let q = &self.people[s as usize];
                if q.alive && q.place == p.place && q.process.is_none() && p.process.is_none() {
                    self.try_conceive(id, s, days);
                }
            }
        }
    }

    // ------------------------------------------------------------------ สำนัก
    fn tick_sects(&mut self) {
        for s in 0..self.sects.len() {
            if !self.sects[s].alive {
                continue;
            }
            self.sects[s].members.retain(|&m| self.people[m as usize].alive);
            if self.sects[s].members.is_empty() {
                self.dissolve_sect(s as u32, "ไม่เหลือศิษย์สักคน");
                continue;
            }
            let leader = self.sects[s].leader;
            if !self.people[leader as usize].alive || self.people[leader as usize].sect != Some(s as u32) {
                self.succeed_sect(s as u32);
            }
        }
    }
}
