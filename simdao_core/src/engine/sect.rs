//! สำนัก — ตั้ง เข้า สืบทอด สลาย

use super::data;
use super::model::*;
use super::sim::Engine;
use std::collections::BTreeMap;

impl Engine {
    /// สำนักในแดนเดียวกันที่ไปถึงได้ภายในไม่กี่สิบวัน
    pub fn sect_nearby(&self, id: Pid) -> Option<u32> {
        let p = &self.people[id as usize];
        self.sects
            .iter()
            .filter(|s| s.alive && s.world == p.world)
            .map(|s| (s.id, self.travel_days(id, p.place, s.home)))
            .filter(|&(_, d)| d <= 30)
            .min_by_key(|&(sid, d)| (d, sid))
            .map(|(s, _)| s)
    }

    pub fn join_sect(&mut self, id: Pid, s: u32) -> i64 {
        let home = self.sects[s as usize].home;
        if self.people[id as usize].place != home {
            return self.depart(id, home, "ไปขอเข้าสำนัก");
        }
        self.people[id as usize].sect = Some(s);
        self.sects[s as usize].members.push(id);
        let leader = self.sects[s as usize].leader;
        if self.people[id as usize].master.is_none() && leader != id {
            self.people[id as usize].master = Some(leader);
        }
        let (n, sn) = (self.people[id as usize].name.clone(), self.sects[s as usize].name.clone());
        self.emit("เข้าสำนัก", Some(id), None, "เข้าสำนัก", format!("{}เข้าเป็นศิษย์{}", n, sn));
        self.range(30, 120)
    }

    pub fn found_sect(&mut self, id: Pid) -> i64 {
        let d = data::world();
        let (words, tails) = &d.org_words;
        let name = loop {
            let cand = format!("สำนัก{}{}", words[self.rng.below(words.len() as u64) as usize], tails[self.rng.below(tails.len() as u64) as usize]);
            if !self.sects.iter().any(|s| s.alive && s.name == cand) {
                break cand;
            }
            if self.rng.below(20) == 0 {
                break format!("{}ที่ {}", cand, self.sects.len() + 1);
            }
        };
        let sid = self.sects.len() as u32;
        let (world, home) = (self.people[id as usize].world, self.people[id as usize].place);
        self.sects.push(Sect {
            id: sid,
            name: name.clone(),
            world,
            home,
            founder: id,
            leader: id,
            founded: self.day,
            members: vec![id],
            treasury: 0.0,
            alive: true,
            grudges: BTreeMap::new(),
        });
        self.people[id as usize].sect = Some(sid);
        let n = self.people[id as usize].name.clone();
        let place = self.place_name(home);
        self.emit("ตั้งสำนัก", Some(id), None, "ตั้งสำนัก", format!("{}ตั้ง{}ขึ้นที่{}", n, name, place));
        self.range(60, 200)
    }

    pub fn leave_sect(&mut self, id: Pid) {
        if let Some(s) = self.people[id as usize].sect.take() {
            self.sects[s as usize].members.retain(|&m| m != id);
        }
    }

    pub fn dissolve_sect(&mut self, s: u32, why: &str) {
        let sect = &mut self.sects[s as usize];
        sect.alive = false;
        let home = sect.home as usize;
        let t = sect.treasury;
        sect.treasury = 0.0;
        self.places[home].treasury += t;
        let members = std::mem::take(&mut self.sects[s as usize].members);
        for m in members {
            self.people[m as usize].sect = None;
        }
        let name = self.sects[s as usize].name.clone();
        self.emit("สำนักล่มสลาย", None, None, "สลาย", format!("{}ล่มสลาย — {}", name, why));
    }

    /// ผู้นำตาย — ผู้ที่ขั้นสูงสุดในสำนักขึ้นแทน
    pub fn succeed_sect(&mut self, s: u32) {
        let members = self.sects[s as usize].members.clone();
        let next = members
            .iter()
            .copied()
            .filter(|&m| self.people[m as usize].alive)
            .max_by_key(|&m| (self.people[m as usize].realm, std::cmp::Reverse(m)));
        match next {
            Some(n) => {
                self.sects[s as usize].leader = n;
                let (nn, sn) = (self.people[n as usize].name.clone(), self.sects[s as usize].name.clone());
                self.emit("สืบทอดสำนัก", Some(n), None, "เป็นเจ้าสำนัก", format!("{}ขึ้นเป็นเจ้า{}", nn, sn));
            }
            None => self.dissolve_sect(s, "ไร้ผู้สืบทอด"),
        }
    }
}
