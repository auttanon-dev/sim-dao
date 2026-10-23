//! สังคมเมือง — เมือง เจ้าเมือง กฎหมาย คุณธรรม งานตามอาชีพ เหตุการณ์ในเมือง และประตูข้ามแดน
//!
//! อาชีพกำหนดงานที่คนทำจริง (ตาราง PROFESSION_WORK ของต้นฉบับ): มือปราบตามจับคนผิด นักฆ่ารับจ้าง
//! หมอดูทำนายชะตา สายลับขายข่าว นักบวชสะสมบุญ ผู้มีพลังเลือกได้ว่าจะปกป้องหรือขูดรีดชาวบ้าน
//! ความเข้มงวดของกฎเมืองกำหนดโอกาสที่คนผิดจะถูกจับ

use super::act::Act;
use super::data::{self, k};
use super::model::*;
use super::sim::Engine;
use super::polity::*;

impl Engine {
    /// เมืองของโลกมนุษย์และแดนเพื่อนบ้าน — หนึ่งเมืองต่อสถานที่ที่เป็นเมือง/ตลาด พร้อมเจ้าเมือง
    pub fn found_cities(&mut self) {
        let d = data::world();
        let lore = data::table("lore", "CITIES").as_array().unwrap().clone();
        let mut spots: Vec<(u16, u32)> = Vec::new();
        for w in &self.worlds {
            if w.tier != 0 || !matches!(w.kind, WorldKind::Main | WorldKind::Sister) {
                continue;
            }
            for &p in &w.places {
                if matches!(d.places[p as usize].kind.as_str(), "เมือง" | "ตลาด") {
                    spots.push((w.id, p));
                }
            }
        }
        for (i, (world, place)) in spots.into_iter().enumerate().take(lore.len()) {
            let c = &lore[i];
            let kind = c["type_desc"].as_str().unwrap_or("").to_string();
            let (strict, title, realm) = if kind.contains("เมืองหลวง") {
                (90.0, "ฮ่องเต้", 6)
            } else if kind.contains("ชายแดน") {
                (80.0, "แม่ทัพใหญ่", 5)
            } else if kind.contains("หน้าด่านสำนัก") {
                (40.0, "ตัวแทนสำนัก", 7)
            } else if kind.contains("ลับแล") || kind.contains("เถื่อน") || kind.contains("ตลาดมืด") {
                (10.0, "ราชาตลาดมืด", 8)
            } else {
                (50.0, "นายอำเภอ", 3)
            };
            let a = &c["attributes"];
            let id = self.polities.len() as u32;
            let age = 30.0 + self.rng.next_f64() * 30.0;
            let ruler = self.spawn(world, Some(place), age, [None, None]);
            let p = &mut self.people[ruler as usize];
            p.cultivator = true;
            p.realm = realm;
            p.peak_realm = realm;
            p.office = Some((id, 0));
            let mut pol = Polity::new(id, PolityKind::City, c["name_th"].as_str().unwrap_or("").to_string(), world, place, Succession::Strength, title, self.day);
            pol.style = kind;
            pol.policy.strictness = strict / 100.0;
            pol.offices[0].holder = Some(ruler);
            pol.traits = Some(CityTraits {
                safety: a["safety"].as_f64().unwrap_or(50.0) as f32,
                wealth: a["wealth"].as_f64().unwrap_or(50.0) as f32,
                jianghu: a["jianghu"].as_f64().unwrap_or(50.0) as f32,
                info: a["info"].as_f64().unwrap_or(50.0) as f32,
            });
            self.polities.push(pol);
        }
        self.index_cities();
    }

    pub fn index_cities(&mut self) {
        self.city_index = vec![None; self.places.len()];
        for p in self.polities.iter().rev() {
            if p.kind == PolityKind::City {
                self.city_index[p.seat as usize] = Some(p.id);
            }
        }
    }

    pub fn city_at(&self, place: u32) -> Option<usize> {
        self.city_index.get(place as usize).copied().flatten().map(|c| c as usize)
    }

    /// ความเข้มงวดของกฎที่สถานที่หนึ่ง (เมืองไร้เจ้าเมือง = ไร้กฎ)
    pub fn law_at(&self, place: u32) -> f64 {
        match self.city_at(place) {
            Some(c) if self.polities[c].head().is_some() => self.polities[c].policy.strictness as f64,
            Some(_) => 0.05,
            None => 0.3,
        }
    }

    /// เจ้าเมืองตาย — ผู้แกร่งที่สุดในเมืองขึ้นแทน
    pub fn tick_cities(&mut self) {
        for c in 0..self.polities.len() {
            if self.polities[c].kind != PolityKind::City {
                continue;
            }
            let ruler = self.polities[c].head();
            if ruler.map_or(false, |r| self.people[r as usize].alive) {
                continue;
            }
            let place = self.polities[c].seat;
            let cand = self.present_at(place).into_iter().filter(|&i| self.is_adult(i) && self.people[i as usize].office.is_none() && !self.is_criminal(i)).max_by(|&a, &b| self.power(a).partial_cmp(&self.power(b)).unwrap().then(b.cmp(&a)));
            self.polities[c].offices[0].holder = cand;
            if let Some(r) = cand {
                self.people[r as usize].office = Some((c as u32, 0));
                let (n, t, cn) = (self.people[r as usize].name.clone(), self.polities[c].title().to_string(), self.polities[c].name.clone());
                self.emit("สืบตำแหน่งเจ้าเมือง", Some(r), None, "ขึ้นปกครอง", format!("{}ขึ้นเป็น{}แห่ง{}", n, t, cn));
            }
        }
    }

    // ------------------------------------------------------------------ คุณธรรมและความผิด
    pub fn is_criminal(&self, id: Pid) -> bool {
        let p = &self.people[id as usize];
        let crim = data::strs(data::table("config", "CRIMINAL_PROFESSIONS"));
        p.crimes > 0 || (p.moral as f64) <= k("CRIMINAL_MORAL") || crim.contains(&data::world().professions[p.profession as usize].0) || self.hated(id)
    }

    pub fn crime_weight(&self, id: Pid) -> u16 {
        let p = &self.people[id as usize];
        let mut n = p.crimes + p.kills / 2;
        if self.hated(id) {
            n += 1;
        }
        if (p.moral as f64) <= k("CRIMINAL_MORAL") * 2.0 {
            n += 1;
        }
        n.max(1)
    }

    /// ตัวเลือกตามอาชีพ (เพิ่มเข้าเมนูของ choose)
    pub fn profession_options(&mut self, id: Pid, others: &[Pid], menu: &mut Vec<(Act, f64)>) {
        let d = data::world();
        let p = &self.people[id as usize];
        let prof = d.professions[p.profession as usize].0.clone();
        let table = &data::table("intent", "PROFESSION_WORK")[prof.as_str()];
        let Some(rows) = table.as_array() else { return };
        let scale = 0.3; // น้ำหนักต้นฉบับอยู่ในมาตราส่วนที่ใหญ่กว่าเมนูนี้
        for r in rows {
            let kind = r[0].as_str().unwrap_or("");
            let w = r[1].as_f64().unwrap_or(0.0) * scale;
            match kind {
                "ลาดตระเวน" => menu.push((Act::Patrol, w)),
                "จับกุมอาชญากร" => {
                    if let Some(&c) = others.iter().filter(|&&o| self.is_criminal(o)).max_by_key(|&&o| (self.crime_weight(o), std::cmp::Reverse(o))) {
                        menu.push((Act::Arrest(c), w * 1.5));
                    }
                }
                "ปกป้องชาวบ้าน" => menu.push((Act::Protect, w)),
                "ขูดรีดชาวบ้าน" => menu.push((Act::Extort, w * (1.0 - p.compassion as f64))),
                "ทำนายชะตา" => {
                    if let Some(&c) = others.iter().find(|&&o| self.people[o as usize].gold > 20.0) {
                        menu.push((Act::Fortune(c), w));
                    }
                }
                "ขายข่าวลับ" => {
                    if let Some(&c) = others.iter().find(|&&o| self.people[o as usize].gold > 30.0 && self.people[o as usize].cultivator) {
                        menu.push((Act::SellInfo(c), w));
                    }
                }
                "ลอบสังหาร" => {
                    if let Some((t, _)) = self.assassin_job(id, others) {
                        menu.push((Act::Assassinate(t), w));
                    }
                }
                "ดักปล้น" => {
                    if let Some(&t) = others.iter().find(|&&o| self.people[o as usize].gold > 20.0) {
                        menu.push((Act::Rob(t), w * 0.5));
                    }
                }
                "สะสมบุญบารมี" => menu.push((Act::Merit, w)),
                "รักษาชาวบ้าน" => menu.push((Act::Work, w * 0.5)),
                _ => {}
            }
        }
        // ผู้บำเพ็ญที่มีพลังเลือกได้ว่าจะปกป้องหรือข่มเหงชาวบ้าน
        if p.cultivator && p.realm % 10 >= 3 {
            menu.push((Act::Protect, 2.0 * p.compassion as f64));
            if p.compassion < 0.4 {
                menu.push((Act::Extort, 2.0 * p.greed as f64));
            }
        }
        // เหตุการณ์ในเมือง
        if self.city_at(p.place).is_some() {
            menu.push((Act::CityLife, 4.0));
        }
        // ประตูข้ามแดน
        if data::table("places", "GATES")[d.places[p.place as usize].name.as_str()].is_object() && p.cultivator {
            menu.push((Act::Gate, 1.0 + p.ambition as f64));
        }
    }

    pub fn patrol(&mut self, id: Pid) -> i64 {
        // เบี้ยหวัดจากคลังชุมชนของที่นั้น
        let place = self.people[id as usize].place as usize;
        let pay = self.places[place].treasury.min(5.0);
        self.places[place].treasury -= pay;
        self.people[id as usize].gold += pay;
        self.range(10, 30)
    }

    pub fn protect(&mut self, id: Pid) -> i64 {
        let place = self.people[id as usize].place as usize;
        let thanks = self.places[place].treasury.min(10.0);
        self.places[place].treasury -= thanks;
        let p = &mut self.people[id as usize];
        p.gold += thanks;
        p.moral = (p.moral + 1).min(100);
        self.range(10, 40)
    }

    pub fn extort(&mut self, id: Pid) -> i64 {
        let place = self.people[id as usize].place as usize;
        let take = (self.places[place].till * 0.3).min(80.0);
        self.places[place].till -= take;
        let p = &mut self.people[id as usize];
        p.gold += take;
        p.moral = (p.moral - 2).max(-100);
        p.inner += 0.3;
        p.crimes += 1;
        let n = p.name.clone();
        if take > 20.0 {
            let pn = self.place_name(place as u32);
            self.emit("ขูดรีดชาวบ้าน", Some(id), None, "ขูดรีด", format!("{}ขูดรีดชาวบ้านที่{}ได้ {:.0} ตำลึง", n, pn, take));
        }
        self.range(10, 40)
    }

    pub fn merit(&mut self, id: Pid) -> i64 {
        let p = &mut self.people[id as usize];
        p.moral = (p.moral + 2).min(100);
        p.merit += 5.0 + 10.0 * self.rng.next_f64() as f32;
        p.inner = (p.inner - 0.3).max(0.0);
        p.insight += 0.1 + 0.4 * self.rng.next_f64();
        self.range(30, 180)
    }

    pub fn fortune(&mut self, id: Pid, client: Pid) -> i64 {
        let fee = (5.0 + 15.0 * self.rng.next_f64()).min(self.people[client as usize].gold);
        self.people[client as usize].gold -= fee;
        self.people[id as usize].gold += fee;
        self.people[id as usize].insight += 0.1 + 0.4 * self.rng.next_f64();
        self.people[client as usize].insight += 0.1 + 0.2 * self.rng.next_f64();
        self.range(3, 20)
    }

    /// ขายข่าวลับ — ร่องรอยไปแดนลับที่ยังผนึกอยู่
    pub fn sell_info(&mut self, id: Pid, client: Pid) -> i64 {
        let world = self.people[id as usize].world;
        let sealed: Vec<u32> = self.caches.iter().filter(|c| c.world == world && !c.opened).map(|c| c.id).collect();
        let fee = 10.0 + 40.0 * self.rng.next_f64();
        if self.people[client as usize].gold < fee || sealed.is_empty() {
            return self.range(5, 15);
        }
        let c = sealed[self.rng.below(sealed.len() as u64) as usize];
        self.people[client as usize].gold -= fee;
        self.people[id as usize].gold += fee;
        let q = &mut self.people[client as usize];
        if !q.leads.contains(&c) {
            q.leads.push(c);
            if q.leads.len() > k("RUMOR_LEAD_MAX") as usize {
                q.leads.remove(0);
            }
        }
        *q.bonds.entry(id).or_insert(0) += 1;
        self.range(2, 15)
    }

    /// งานลอบสังหาร — แค้นส่วนตัว เรื่องค้างคา คำสั่งสำนัก หรือผู้ว่าจ้างที่รู้จักและแค้นเป้าหมาย
    fn assassin_job(&self, id: Pid, others: &[Pid]) -> Option<(Pid, Option<Pid>)> {
        let p = &self.people[id as usize];
        for &t in others {
            if p.rivals.contains_key(&t) || p.debts.iter().any(|d| !d.done && d.target == t) {
                return Some((t, None));
            }
        }
        let fee_max = data::table("config", "ASSASSIN_FEE")[1].as_f64().unwrap_or(250.0);
        for (&c, _) in &p.bonds {
            let client = &self.people[c as usize];
            if !client.alive || client.gold < fee_max {
                continue;
            }
            if let Some(&t) = others.iter().find(|&&t| t != c && client.rivals.get(&t).copied().unwrap_or(0) > 0) {
                return Some((t, Some(c)));
            }
        }
        None
    }

    pub fn assassinate(&mut self, id: Pid, t: Pid) -> i64 {
        if !self.people[t as usize].alive || self.people[t as usize].place != self.people[id as usize].place {
            return self.range(5, 20);
        }
        let others = vec![t];
        let Some((_, client)) = self.assassin_job(id, &others) else { return self.range(5, 20) };
        let (an, tn) = (self.people[id as usize].name.clone(), self.people[t as usize].name.clone());
        if let Some(c) = client {
            let r = data::table("config", "ASSASSIN_FEE");
            let fee = (r[0].as_f64().unwrap() + self.rng.next_f64() * (r[1].as_f64().unwrap() - r[0].as_f64().unwrap())).min(self.people[c as usize].gold);
            self.people[c as usize].gold -= fee;
            self.people[id as usize].gold += fee;
            self.people[c as usize].moral -= 3;
            *self.people[c as usize].bonds.entry(id).or_insert(0) += 2;
        }
        if self.power(id) * 1.5 > self.power(t) {
            self.people[id as usize].moral -= 5;
            self.people[id as usize].crimes += 3;
            if let Some(c) = client {
                self.people[c as usize].rivals.remove(&t);
            }
            self.kill(t, Some(id), &format!("ถูก{}ลอบสังหาร", an), false);
            if !self.people[t as usize].alive {
                self.emit("ลอบสังหาร", Some(id), Some(t), "สังหาร", format!("{}ลอบสังหาร{}สำเร็จ", an, tn));
            }
        } else {
            *self.people[t as usize].rivals.entry(id).or_insert(0) += 3;
            self.emit("ลอบสังหาร", Some(id), Some(t), "ล้มเหลว", format!("{}ลอบสังหาร{}พลาด โดนหมายหัวกลับ", an, tn));
        }
        self.range(10, 40)
    }

    /// เหตุการณ์ในเมือง — ความปลอดภัย ยุทธภพ ความมั่งคั่ง ข่าวสาร ของเมืองกำหนดสิ่งที่เจอ
    pub fn city_life(&mut self, id: Pid) -> i64 {
        let gap = self.range(5, 30);
        let place = self.people[id as usize].place;
        let Some(ci) = self.city_at(place) else { return gap };
        let (cname, cworld, t) = (self.polities[ci].name.clone(), self.polities[ci].world, self.polities[ci].traits.expect("เมืองต้องมีคุณลักษณะ"));
        let roll = self.rng.next_f64() * 100.0;
        let name = self.people[id as usize].name.clone();
        if roll > t.safety as f64 && self.chance(0.5) {
            // โจรป่าดักโจมตีระหว่างทางเข้าเมือง
            let enemy = 3.0 + self.rng.next_f64() * 12.0 * (1.0 + self.worlds[cworld as usize].tier as f64);
            if self.power(id) >= enemy {
                let p = &mut self.people[id as usize];
                p.insight += 0.5;
                p.moral += 1;
                self.emit("เหตุการณ์เมือง", Some(id), None, "ปราบโจร", format!("{}ถูกโจรป่าดักโจมตีใกล้{} แต่ปราบได้สำเร็จ", name, cname));
            } else {
                let loss = (self.people[id as usize].gold * 0.3).min(40.0);
                let p = &mut self.people[id as usize];
                p.gold -= loss;
                p.injury = (p.injury + 0.3).min(1.0);
                self.places[place as usize].treasury += loss; // ของโจรกระจายกลับสู่ตลาดมืดของเมือง
                self.emit("เหตุการณ์เมือง", Some(id), None, "ถูกปล้น", format!("{}ถูกโจรป่าดักปล้นใกล้{} เสียเงิน {:.0} ตำลึงและบาดเจ็บ", name, cname, loss));
            }
            return gap;
        }
        if self.rng.next_f64() * 100.0 <= t.jianghu as f64 {
            // งานประลองยุทธในเมือง กับคนที่อยู่ที่นี่จริง
            let rivals: Vec<Pid> = self.present_at(place).into_iter().filter(|&o| o != id && self.people[o as usize].cultivator && self.is_adult(o)).collect();
            if let Some(o) = self.pick(&rivals) {
                return self.duel(id, o, false);
            }
            self.people[id as usize].insight += 0.4;
            return gap;
        }
        if self.rng.next_f64() * 100.0 <= t.wealth as f64 && self.people[id as usize].gold >= 40.0 && self.people[id as usize].injury > 0.2 {
            // ซื้อยาสมานแผล
            self.people[id as usize].gold -= 40.0;
            self.places[place as usize].till += 40.0;
            let p = &mut self.people[id as usize];
            p.injury *= 0.5;
            return gap;
        }
        if self.rng.next_f64() * 100.0 <= t.info as f64 {
            // ได้ยินข่าวลือเรื่องแดนลับในร้านน้ำชา
            let world = cworld;
            let sealed: Vec<u32> = self.caches.iter().filter(|x| x.world == world && !x.opened).map(|x| x.id).collect();
            if let Some(cid) = self.pick(&sealed) {
                let p = &mut self.people[id as usize];
                if !p.leads.contains(&cid) {
                    p.leads.push(cid);
                    if p.leads.len() > k("RUMOR_LEAD_MAX") as usize {
                        p.leads.remove(0);
                    }
                    self.ledger.count("ได้ยินข่าวลือ");
                }
            }
        }
        gap
    }

    /// ข้ามแดนผ่านประตูมิติที่สถานที่นี้ (ลงโลกล่างถูกกดขั้น · ขึ้นแดนบนต้องเสียค่าผ่านทาง)
    pub fn use_gate(&mut self, id: Pid) -> i64 {
        let d = data::world();
        let place = self.people[id as usize].place;
        let gate = &data::table("places", "GATES")[d.places[place as usize].name.as_str()];
        if !gate.is_object() {
            return self.range(10, 30);
        }
        let to = match &gate["to"] {
            serde_json::Value::String(s) => s.clone(),
            v => format!("t{}", v.as_i64().unwrap_or(0)),
        };
        let Some(dest) = self.worlds.iter().position(|w| w.key == to && w.kind != WorldKind::Chaos) else { return self.range(10, 30) };
        let dest = dest as u16;
        if dest == self.people[id as usize].world {
            return self.range(10, 30);
        }
        let fee = gate["fee"].as_f64().unwrap_or(0.0) / 1000.0;
        if self.people[id as usize].gold < fee {
            return self.range(10, 30);
        }
        // ขึ้นแดนสูงต้องมีขั้นถึงชั้นของแดนนั้น
        let dtier = self.worlds[dest as usize].tier;
        if dtier > self.people[id as usize].tier(self.cfg.realm_band) {
            return self.range(10, 30);
        }
        self.people[id as usize].gold -= fee;
        self.places[place as usize].treasury += fee;
        let push = gate["push"].as_u64().unwrap_or(0) as u8;
        let places = self.worlds[dest as usize].places.clone();
        let to_place = places[self.rng.below(places.len() as u64) as usize];
        self.leave_sect(id);
        self.move_to(id, to_place);
        let floor = dtier * self.cfg.realm_band;
        let p = &mut self.people[id as usize];
        p.world = dest;
        p.realm = p.realm.saturating_sub(push).max(floor.min(p.realm));
        let (n, gn, wn) = (p.name.clone(), d.places[place as usize].name.clone(), self.worlds[dest as usize].name.clone());
        let tail = if push > 0 { format!(" (ถูกกดพลัง {} ขั้น)", push) } else { String::new() };
        self.emit("ข้ามประตูมิติ", Some(id), None, "ข้ามแดน", format!("{}ก้าวผ่าน{}สู่{}{}", n, gn, wn, tail));
        self.range(30, 120)
    }
}
