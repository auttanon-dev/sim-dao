//! ฝีมือช่าง — หมอรักษาคน นักปรุงยาวิเศษ ช่างตีอาวุธ
//!
//! ทุกอย่างกินวัตถุดิบจริงจากธรรมชาติ (สมุนไพร แร่ แก่นพลัง) และได้ค่าจ้างจากคนที่ได้ประโยชน์
//! ของไม่ได้เสกขึ้นมา: ยาหนึ่งเม็ดคือสมุนไพรกับแก่นพลังที่มีคนไปเก็บมา

use super::data;
use super::model::*;
use super::sim::Engine;
use super::act::Act;

pub const HEALERS: [&str; 3] = ["หมอยา", "นักปรุงโอสถ", "นักบวช"];
pub const SMITHS: [&str; 1] = ["ช่างตีเหล็ก"];
pub const GUARDS: [&str; 7] = ["มือปราบ", "ผู้คุมกฎ", "ทหารยาม", "ทหารกองปราบ", "องครักษ์หลวง", "ทหารรักษาพระนคร", "ทหารลาดตระเวน"];

impl Engine {
    pub fn profession_is(&self, id: Pid, names: &[&str]) -> bool {
        let prof = &data::world().professions[self.people[id as usize].profession as usize].0;
        names.contains(&prof.as_str())
    }

    /// ตัวเลือกงานช่างของคนนี้ (เพิ่มเข้าเมนูของ choose)
    pub fn trade_options(&mut self, id: Pid, others: &[Pid], menu: &mut Vec<(Act, f64)>) {
        let p = &self.people[id as usize];
        let herb = p.mats[Material::Herb as usize];
        let ore = p.mats[Material::Ore as usize];
        let core = p.mats[Material::Core as usize];
        if self.profession_is(id, &HEALERS) {
            // คนเจ็บหรือป่วยที่อยู่ตรงนี้
            let day = self.day;
            if let Some(&pat) = others.iter().find(|&&o| {
                let q = &self.people[o as usize];
                q.injury > 0.25 || q.sick(day)
            }) {
                menu.push((Act::Heal(pat), 12.0 + if herb >= 1.0 { 6.0 } else { 0.0 }));
            }
        }
        // ปรุงยาวิเศษ — ต้องเป็นผู้บำเพ็ญที่รู้จักปราณ หรือนักปรุงโอสถ
        if (p.cultivator && p.realm >= 2 || self.profession_is(id, &["นักปรุงโอสถ"])) && herb >= 3.0 && core >= 1.0 {
            menu.push((Act::Brew, 6.0));
        }
        if self.profession_is(id, &SMITHS) && ore >= 4.0 {
            menu.push((Act::Forge, 10.0));
        }
    }

    pub fn heal(&mut self, id: Pid, patient: Pid) -> i64 {
        let day = self.day;
        if !self.people[patient as usize].alive || self.people[patient as usize].place != self.people[id as usize].place {
            return self.range(5, 15);
        }
        let herbs = self.people[id as usize].mats[Material::Herb as usize];
        let use_herb = herbs >= 1.0;
        if use_herb {
            self.people[id as usize].mats[Material::Herb as usize] -= 1.0;
        }
        let skill = if use_herb { 0.5 } else { 0.25 };
        let q = &mut self.people[patient as usize];
        q.injury *= 1.0 - skill as f32;
        let cured = q.sick(day) && use_herb;
        if cured {
            // ยาสมุนไพรย่นเวลาป่วยลงครึ่งหนึ่ง
            q.sick_until = day + (q.sick_until - day) / 2;
        }
        // ค่ารักษาตามกำลังจ่าย
        let fee = (q.gold * 0.05).min(15.0).max(0.0);
        q.gold -= fee;
        self.people[id as usize].gold += fee;
        *self.people[patient as usize].bonds.entry(id).or_insert(0) += 1;
        self.ledger.count("รักษาคน");
        self.range(5, 20)
    }

    pub fn brew(&mut self, id: Pid) -> i64 {
        let p = &mut self.people[id as usize];
        p.mats[Material::Herb as usize] -= 3.0;
        p.mats[Material::Core as usize] -= 1.0;
        // ฝีมือขึ้นกับขั้น — ผู้ฝึกตนขั้นสูงหลอมยาเสียน้อยกว่า
        let ok = 0.35 + 0.05 * (p.realm % 10) as f64;
        let name = p.name.clone();
        if self.chance(ok) {
            self.people[id as usize].pills += 1;
            self.emit("ปรุงยา", Some(id), None, "สำเร็จ", format!("{}ปรุงยาวิเศษได้หนึ่งเม็ด", name));
        } else {
            self.ledger.count("ปรุงยาล้มเหลว");
        }
        self.range(30, 120)
    }

    pub fn forge(&mut self, id: Pid) -> i64 {
        let p = &mut self.people[id as usize];
        p.mats[Material::Ore as usize] -= 4.0;
        let grade = (0.5 + self.rng.next_f64()) as f32;
        let name = self.people[id as usize].name.clone();
        // ขายให้ผู้บำเพ็ญที่อยู่ใกล้และอาวุธแย่กว่า — ราคาตามคุณภาพ
        let place = self.people[id as usize].place;
        let buyer = self
            .present_at(place)
            .into_iter()
            .filter(|&b| b != id && self.people[b as usize].cultivator && self.people[b as usize].weapon < grade)
            .max_by(|&a, &b| self.people[a as usize].gold.partial_cmp(&self.people[b as usize].gold).unwrap().then(b.cmp(&a)));
        let price = 20.0 * grade as f64;
        match buyer {
            Some(b) if self.people[b as usize].gold >= price => {
                self.people[b as usize].gold -= price;
                self.people[b as usize].weapon = grade;
                self.people[id as usize].gold += price;
                let bn = self.people[b as usize].name.clone();
                self.emit("ตีอาวุธ", Some(id), Some(b), "ขาย", format!("{}ตีกระบี่ขายให้{} ราคา {:.0} ตำลึง", name, bn, price));
            }
            _ => {
                // ไม่มีคนซื้อ — เก็บไว้ใช้เองถ้าดีกว่าของเดิม
                let p = &mut self.people[id as usize];
                if p.weapon < grade {
                    p.weapon = grade;
                }
            }
        }
        self.range(20, 80)
    }
}
