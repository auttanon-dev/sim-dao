//! ร่างกายรายเดือน — แก่ ฟื้นตัว หิว การปันอาหารในครอบครัว

use crate::engine::data;
use crate::engine::model::*;
use crate::engine::sim::Engine;
use crate::physics;

impl Engine {

    // ------------------------------------------------------------------ ร่างกาย
    pub(crate) fn tick_bodies(&mut self, days: f64) {
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
                let add = self.cfg.decay_per_year * (1.0 + self.cfg.decay_per_realm_mult * tier_realm) * days / 365.0;
                let (aid, _, _) = self.cultivation_aid(id);
                let (body, spirit) = self.path_shares(id);
                let path = 1.0 - data::k("PATH_BODY_DECAY") * body + data::k("PATH_SPIRIT_FRAIL") * spirit;
                self.people[id as usize].decay += add * aid * path;
            }
            let p = &mut self.people[id as usize];
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
    pub(crate) fn rng_fade(&mut self, v: i16, fade: f64) -> i16 {
        let x = v as f64 * (1.0 - fade);
        let fl = x.floor();
        (fl + if self.rng.next_f64() < x - fl { 1.0 } else { 0.0 }) as i16
    }

    /// เด็กที่ขาดได้กินจากเสบียงของพ่อแม่ที่อยู่ด้วยกัน — คืนจำนวนที่ได้
    pub(crate) fn feed_from_family(&mut self, id: Pid, short: f64) -> f64 {
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

    pub(crate) fn hunger(&mut self, id: Pid, unmet: f64, want: f64, days: f64) {
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
        p.alive && p.sentient && !p.is_chaos() && p.realm < self.cfg.bigu_realm && !p.dissolved() && !matches!(p.process, Some(Process::Hidden { .. }))
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
}
