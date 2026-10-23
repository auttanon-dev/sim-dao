//! สำนัก — ตั้ง เข้า สืบทอด สลาย (สำนักคือหน่วยปกครองชนิด Sect ใน Engine.polities)

use super::data;
use super::model::*;
use super::polity::*;
use super::sim::Engine;

impl Engine {
    pub fn sect_ids(&self) -> impl Iterator<Item = u32> + '_ {
        self.polities.iter().filter(|s| s.kind == PolityKind::Sect && s.alive()).map(|s| s.id)
    }

    /// สำนักในแดนเดียวกันที่ไปถึงได้ภายในไม่กี่สิบวัน
    pub fn sect_nearby(&self, id: Pid) -> Option<u32> {
        let p = &self.people[id as usize];
        self.polities
            .iter()
            .filter(|s| s.kind == PolityKind::Sect && s.alive() && s.world == p.world)
            .map(|s| (s.id, self.travel_days(id, p.place, s.seat)))
            .filter(|&(_, d)| d <= 30)
            .min_by_key(|&(sid, d)| (d, sid))
            .map(|(s, _)| s)
    }

    pub fn join_sect(&mut self, id: Pid, s: u32) -> i64 {
        let home = self.polities[s as usize].seat;
        if self.people[id as usize].place != home {
            return self.depart(id, home, "ไปขอเข้าสำนัก");
        }
        self.people[id as usize].sect = Some(s);
        self.polities[s as usize].members.push(id);
        if let Some(leader) = self.polities[s as usize].head() {
            if self.people[id as usize].master.is_none() && leader != id {
                self.people[id as usize].master = Some(leader);
            }
        }
        let (n, sn) = (self.people[id as usize].name.clone(), self.polities[s as usize].name.clone());
        self.emit("เข้าสำนัก", Some(id), None, "เข้าสำนัก", format!("{}เข้าเป็นศิษย์{}", n, sn));
        self.range(30, 120)
    }

    pub fn found_sect(&mut self, id: Pid) -> i64 {
        // เงื่อนไขอาจเปลี่ยนไประหว่างตัดสินใจกับลงมือ (มีคนตั้งสำนักที่นี่ไปก่อน เงินหมด)
        if !self.can_found_sect(id) {
            return self.range(10, 30);
        }
        let d = data::world();
        let (words, tails) = &d.org_words;
        let sects_ever = self.polities.iter().filter(|s| s.kind == PolityKind::Sect).count();
        let name = loop {
            let cand = format!("สำนัก{}{}", words[self.rng.below(words.len() as u64) as usize], tails[self.rng.below(tails.len() as u64) as usize]);
            if !self.polities.iter().any(|s| s.kind == PolityKind::Sect && s.alive() && s.name == cand) {
                break cand;
            }
            if self.rng.below(20) == 0 {
                break format!("{}ที่ {}", cand, sects_ever + 1);
            }
        };
        let sid = self.polities.len() as u32;
        let (world, home) = (self.people[id as usize].world, self.people[id as usize].place);
        let mut pol = Polity::new(sid, PolityKind::Sect, name.clone(), world, home, Succession::Council, "เจ้าสำนัก", self.day);
        pol.founder = Some(id);
        pol.members.push(id);
        // ทุนตั้งสำนักย้ายจากผู้ก่อตั้งเข้าคลังสำนัก
        let cost = self.cfg.sect_found_cost;
        self.people[id as usize].gold -= cost;
        pol.treasury = cost;
        self.polities.push(pol);
        self.people[id as usize].sect = Some(sid);
        self.install(sid, 0, id, Accession::Founded);
        let n = self.people[id as usize].name.clone();
        let place = self.place_name(home);
        self.emit("ตั้งสำนัก", Some(id), None, "ตั้งสำนัก", format!("{}ตั้ง{}ขึ้นที่{}", n, name, place));
        self.range(60, 200)
    }

    pub fn leave_sect(&mut self, id: Pid) {
        if let Some(s) = self.people[id as usize].sect.take() {
            self.polities[s as usize].members.retain(|&m| m != id);
            if self.people[id as usize].office.map_or(false, |(p, _)| p == s) {
                self.release_office(id);
            }
        }
    }

    pub fn dissolve_sect(&mut self, s: u32, why: &str) {
        let day = self.day;
        let sect = &mut self.polities[s as usize];
        sect.fallen = Some(day);
        let home = sect.seat as usize;
        let t = sect.treasury;
        sect.treasury = 0.0;
        self.places[home].treasury += t;
        let members = std::mem::take(&mut self.polities[s as usize].members);
        for m in members {
            self.people[m as usize].sect = None;
        }
        let holders: Vec<Pid> = self.polities[s as usize].holders().map(|(_, h)| h).collect();
        for h in holders {
            self.vacate(h);
        }
        let name = self.polities[s as usize].name.clone();
        self.emit("สำนักล่มสลาย", None, None, "สลาย", format!("{}ล่มสลาย — {}", name, why));
    }

    /// เซฟก่อน P1: สำนักและเมืองแยกกัน → รวมเข้า polities (สำนักคง id เดิม เมืองต่อท้าย)
    pub fn migrate_legacy_polities(&mut self) {
        if !self.polities.is_empty() || (self.legacy_sects.is_empty() && self.legacy_cities.is_empty()) {
            return;
        }
        for s in std::mem::take(&mut self.legacy_sects) {
            let mut pol = Polity::new(s.id, PolityKind::Sect, s.name, s.world, s.home, Succession::Council, "เจ้าสำนัก", s.founded);
            pol.founder = Some(s.founder);
            pol.members = s.members;
            pol.treasury = s.treasury;
            if s.alive {
                pol.offices[0].holder = Some(s.leader);
                pol.offices[0].how = Accession::Migrated;
            } else {
                pol.fallen = Some(s.founded);
            }
            for (o, g) in s.grudges {
                pol.relations.entry(o).or_default().grudge = g;
            }
            self.polities.push(pol);
        }
        let base = self.polities.len() as u32;
        for c in std::mem::take(&mut self.legacy_cities) {
            let id = base + c.id as u32;
            let mut pol = Polity::new(id, PolityKind::City, c.name, c.world, c.place, Succession::Strength, &c.title, 0);
            pol.style = c.kind;
            pol.policy.strictness = c.strictness / 100.0;
            pol.offices[0].holder = c.ruler;
            pol.offices[0].how = Accession::Migrated;
            pol.traits = Some(CityTraits { safety: c.safety, wealth: c.wealth, jianghu: c.jianghu, info: c.info });
            self.polities.push(pol);
        }
        for p in self.people.iter_mut() {
            if let Some(c) = p.legacy_city.take() {
                if p.alive {
                    p.office = Some((base + c as u32, 0));
                }
            }
        }
    }
}
