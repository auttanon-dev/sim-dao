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
        // หลอมยา/อาวุธ — ต้องมีเตาที่สถานที่นี้ แก่นพลังและวัตถุดิบ
        let furnace = data::world().places[p.place as usize].forge >= 0;
        if furnace && core >= 2.0 {
            if (p.cultivator && p.realm >= 2 || self.profession_is(id, &["นักปรุงโอสถ", "หมอยา"]) || p.alch_rank >= 0) && herb >= 3.0 {
                menu.push((Act::Brew, 6.0 + 4.0 * p.alch_rank.max(0) as f64));
            }
            if (self.profession_is(id, &SMITHS) || p.forge_rank >= 0) && ore >= 3.0 {
                menu.push((Act::Forge, 8.0 + 4.0 * p.forge_rank.max(0) as f64));
            }
        }
        // ของที่หลอมไว้ขายต่อ
        if p.items.iter().filter(|i| self.items.get(i).map_or(false, |it| it.maker == Some(id) && !it.legend)).count() >= 2 {
            menu.push((Act::SellCrafts, 6.0));
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
}
