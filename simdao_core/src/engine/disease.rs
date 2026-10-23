//! โรคระบาด — ติดกันในที่ที่คนอยู่หนาแน่น เดินทางไปกับคนป่วย และหายแล้วมีภูมิคุ้มกัน
//!
//! แบบ SIR ต่อสถานที่ คิดบนนาฬิกาโลก: โอกาสติดของคนที่ยังไม่มีภูมิ = 1 − e^(−β·I/N·Δt)
//! ผู้บำเพ็ญที่ดำรงกายด้วยปราณแล้วไม่ติด · หมอที่มีสมุนไพรในที่นั้นลดอัตราตาย

use super::model::*;
use super::sim::Engine;
use super::trades::HEALERS;

const BETA_PER_DAY: f64 = 0.12;     // อัตราติดเชื้อเมื่อทุกคนรอบตัวป่วย
const SICK_DAYS: (i64, i64) = (14, 40);
const IMMUNE_YEARS: i64 = 12;
const OUTBREAK_PER_WORLD_YEAR: f64 = 0.12; // โอกาสเกิดโรคใหม่ต่อแดนต่อปี (จุดที่คนหนาแน่นที่สุด)

impl Engine {
    fn susceptible(&self, id: Pid) -> bool {
        let p = &self.people[id as usize];
        p.alive && p.realm < self.cfg.bigu_realm && p.immune_until <= self.day && !p.sick(self.day)
    }

    fn infect(&mut self, id: Pid) {
        let d = self.range(SICK_DAYS.0, SICK_DAYS.1);
        let day = self.day;
        let p = &mut self.people[id as usize];
        p.sick_until = day + d;
        p.immune_until = day + d + IMMUNE_YEARS * 365;
        self.ledger.count("ติดโรค");
    }

    /// อัตราตายต่อการป่วยหนึ่งครั้ง — เด็กเล็กและคนแก่เปราะที่สุด
    fn case_fatality(&self, id: Pid) -> f64 {
        let p = &self.people[id as usize];
        let age = p.age(self.day);
        let base = if age < 5.0 { 0.12 } else if age < 14.0 { 0.04 } else if age < 50.0 { 0.03 } else { 0.03 + (age - 50.0) * 0.006 };
        let weak = if p.hunger_days > 5.0 { 2.0 } else { 1.0 } * (1.0 + p.injury as f64);
        base * weak
    }

    pub fn tick_disease(&mut self, days: f64) {
        // ---- โรคใหม่ผุดขึ้นที่จุดที่คนหนาแน่นที่สุดของแดน
        for w in 0..self.worlds.len() {
            if !self.chance(crate::physics::hazard_p(OUTBREAK_PER_WORLD_YEAR, days)) {
                continue;
            }
            let places = self.worlds[w].places.clone();
            let Some(&hot) = places.iter().max_by_key(|&&q| (self.at[q as usize].len(), std::cmp::Reverse(q))) else { continue };
            let cand: Vec<Pid> = self.at[hot as usize].iter().copied().filter(|&i| self.susceptible(i)).collect();
            if cand.len() < 8 {
                continue;
            }
            for _ in 0..3 {
                if let Some(i) = self.pick(&cand) {
                    if self.susceptible(i) {
                        self.infect(i);
                    }
                }
            }
            let (pn, wn) = (self.place_name(hot), self.worlds[w].name.clone());
            self.emit_at("โรคระบาด", w as u16, hot, "เริ่มระบาด", format!("โรคระบาดเริ่มขึ้นที่{} ใน{}", pn, wn));
        }
        // ---- แพร่ในแต่ละที่
        let day = self.day;
        for place in 0..self.places.len() {
            let n = self.at[place].len();
            if n == 0 {
                continue;
            }
            let ids: Vec<Pid> = self.at[place].iter().copied().collect();
            let sick = ids.iter().filter(|&&i| self.people[i as usize].sick(day)).count();
            if sick == 0 {
                continue;
            }
            let p_inf = 1.0 - (-BETA_PER_DAY * sick as f64 / n as f64 * days).exp();
            for &i in &ids {
                if self.susceptible(i) && self.chance(p_inf) {
                    self.infect(i);
                }
            }
        }
        // ---- ผู้ป่วยหายหรือตาย (คิดครั้งเดียวต่อเดือนตามสัดส่วนของการป่วยที่อยู่ในเดือนนี้)
        let ids: Vec<Pid> = self.alive.iter().copied().collect();
        for id in ids {
            let p = &self.people[id as usize];
            let start = day - days as i64;
            if p.sick_until <= start {
                continue;
            }
            // วันที่ป่วยอยู่ในรอบนี้ เทียบระยะป่วยเฉลี่ย — อัตราตายทั้งครั้งกระจายตามวันที่ป่วยจริง
            let span = (SICK_DAYS.0 + SICK_DAYS.1) as f64 / 2.0;
            let frac = ((p.sick_until.min(day) - start).max(0) as f64 / span).min(1.0);
            let healer = self.at[p.place as usize].iter().any(|&h| {
                h != id && self.profession_is(h, &HEALERS) && self.people[h as usize].mats[Material::Herb as usize] >= 1.0
            });
            let cfr = self.case_fatality(id) * if healer { 0.5 } else { 1.0 };
            if self.chance(cfr * frac) {
                self.kill(id, None, "ป่วยหนักด้วยโรคระบาด", true);
            }
        }
    }
}
