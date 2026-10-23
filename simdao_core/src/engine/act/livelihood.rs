//! ทำมาหากิน — เก็บของ ขาย และการครองคู่

use crate::engine::model::*;
use crate::engine::sim::Engine;
use crate::physics;

impl Engine {

    // ------------------------------------------------------------------ วัตถุดิบและการค้า
    pub(crate) fn harvest(&mut self, id: Pid, m: Material) -> i64 {
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

    pub(crate) fn sell(&mut self, id: Pid) -> i64 {
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
        if earned > 150.0 {
            let n = self.people[id as usize].name.clone();
            self.emit("ค้าขาย", Some(id), None, "ขายของ", format!("{}ขายวัตถุดิบได้ {:.0} ตำลึง", n, earned));
        }
        self.range(5, 25)
    }

    // ------------------------------------------------------------------ ครอบครัว
    pub(crate) fn court(&mut self, id: Pid, other: Pid) -> i64 {
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
