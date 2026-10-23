//! วิถีบำเพ็ญ — สะสมความเข้าใจจากปราณที่ยืนอยู่ ข้ามกำแพงขั้น ข้ามฟ้า
//!
//! ปราณมีที่มาและมีที่ไป: การบำเพ็ญดูดปราณจากคลังฟ้าของแดน การข้ามขั้นจ่ายก้อนใหญ่
//! ฟ้าฟื้นแบบลอจิสติก และได้คืนเมื่อผู้บำเพ็ญตาย — แดนที่ถูกดูดหนักเข้าสู่ยุคเสื่อมจริง

use super::model::*;
use super::sim::Engine;
use crate::physics;

impl Engine {
    /// เกณฑ์สะสมของขั้นถัดไป — แดนชั้นสูงปราณบริสุทธิ์กว่า เกณฑ์ลดลง
    pub fn need(&self, id: Pid) -> f64 {
        let p = &self.people[id as usize];
        let band = self.cfg.realm_band;
        let r = (p.realm % band) as f64;
        let tier = p.tier(band) as f64;
        (self.cfg.need_base + self.cfg.need_per_realm * r) * (1.0 + 0.5 * tier) * (1.0 - 0.12 * tier)
    }

    pub fn power(&self, id: Pid) -> f64 {
        let p = &self.people[id as usize];
        let base = p.realm as f64 * self.cfg.realm_step + p.insight * self.cfg.insight_w - p.decay * self.cfg.decay_w;
        // ร่างกายที่บาดเจ็บสู้ได้ไม่เต็มที่ · คนธรรมดาก็มีแรง (อายุและเพศมีผลเล็กน้อย)
        let age = p.age(self.day);
        let vigour = if age < 18.0 { 0.7 } else if age > 60.0 { (1.0 - (age - 60.0) / 60.0).max(0.4) } else { 1.0 };
        (base + 1.0) * (1.0 - 0.7 * p.injury as f64) * vigour
    }

    /// โอกาสข้ามขั้นตอนนี้ — ภาพการข้ามกำแพงพลังงาน (physics.barrier_odds)
    pub fn break_odds(&self, id: Pid) -> f64 {
        let p = &self.people[id as usize];
        let w = &self.worlds[p.world as usize];
        let need = self.need(id);
        let gap = (p.insight - need) / need;
        let band = self.cfg.realm_band;
        let ratio = w.ratio().max(self.cfg.heaven_ratio_floor);
        let shifts = vec![
            -self.cfg.break_z_decay * p.decay,
            self.cfg.break_z_tier * w.tier as f64,
            -self.cfg.break_z_realm * (p.realm % band) as f64,
            self.cfg.break_z_scarce * ratio.ln(),
            (p.root as f64 - 0.5) * 1.5,
        ];
        physics::barrier_odds(gap, Some(shifts), self.cfg.break_base_p, self.cfg.break_softness)
    }

    /// ดูดปราณจากคลังฟ้า (ไม่แตะส่วน "เมล็ด" ที่ฟ้าใช้งอกกลับ) คืนสัดส่วนที่ได้จริง 0..1
    fn draw_qi(&mut self, id: Pid, amount: f64) -> f64 {
        let w = self.people[id as usize].world as usize;
        let world = &mut self.worlds[w];
        let extractable = (world.heaven - self.cfg.heaven_seed_ratio * world.cap).max(0.0);
        let take = amount.min(extractable);
        world.heaven -= take;
        self.people[id as usize].drawn += take;
        if amount > 0.0 { take / amount } else { 1.0 }
    }

    pub fn begin_path(&mut self, id: Pid) -> i64 {
        let p = &mut self.people[id as usize];
        p.cultivator = true;
        p.insight += 0.5;
        let n = p.name.clone();
        let root = p.root;
        let feel = if root > 0.75 { "รากปราณโดดเด่นผิดคน" } else if root > 0.5 { "สัมผัสปราณได้ชัด" } else { "สัมผัสปราณได้เพียงเลือนราง" };
        self.emit("ก้าวสู่วิถี", Some(id), None, "เริ่มบำเพ็ญ", format!("{}ก้าวเข้าสู่วิถีบำเพ็ญ — {}", n, feel));
        self.range(30, 120)
    }

    /// ความเข้าใจที่ได้จากการบำเพ็ญ `days` วัน — ปราณของที่นั้น × รากปราณ × ความเพียร (ผลตอบแทนลดลง)
    fn insight_gain(&mut self, id: Pid, days: f64) -> f64 {
        let p = &self.people[id as usize];
        let qi = self.qi[p.place as usize];
        let years = days / 365.0;
        let raw = self.cfg.cultivate_gain * years * (0.3 + qi) * (0.3 + p.root as f64);
        // ปราณที่ต้องดูดเพื่อการนี้ — ถ้าฟ้าแห้ง ได้เท่าที่ฟ้าให้
        let got = self.draw_qi(id, raw * 4.0);
        raw * (0.25 + 0.75 * got)
    }

    pub fn cultivate(&mut self, id: Pid) -> i64 {
        let gap = self.range(60, 300);
        let gain = self.insight_gain(id, gap as f64);
        let p = &mut self.people[id as usize];
        p.insight += gain;
        p.decay = (p.decay - self.cfg.cultivate_heal * gap as f64 / 365.0).max(0.0);
        gap
    }

    pub fn seclude(&mut self, id: Pid) -> i64 {
        let years = 1 + self.rng.below(4) as i64;
        let until = self.day + years * 365;
        self.people[id as usize].process = Some(Process::Seclusion { since: self.day, until });
        let n = self.people[id as usize].name.clone();
        let place = self.place_name(self.people[id as usize].place);
        self.emit("ปิดด่าน", Some(id), None, "ปิดด่าน", format!("{}ปิดด่านบำเพ็ญที่{} ตั้งใจ {} ปี", n, place, years));
        years * 365
    }

    pub fn emerge(&mut self, id: Pid) {
        // ผลของด่าน: บำเพ็ญเต็มเวลา ไม่มีสิ่งรบกวน (คูณ 1.5) — เวลาที่อยู่จริง
        let days = match self.people[id as usize].process {
            Some(Process::Seclusion { since, .. }) => (self.day - since).max(30) as f64,
            _ => 0.0,
        };
        let total_days = days;
        let gain = self.insight_gain(id, total_days) * 1.5;
        let p = &mut self.people[id as usize];
        p.process = None;
        p.insight += gain;
        p.decay = (p.decay - self.cfg.cultivate_heal * total_days / 365.0).max(0.0);
        let n = p.name.clone();
        self.emit("ออกจากด่าน", Some(id), None, "ออกจากด่าน", format!("{}ออกจากด่าน ความเข้าใจเพิ่มขึ้น {:.1}", n, gain));
        let gap = self.range(5, 40);
        self.schedule(id, gap);
    }

    pub fn breakthrough(&mut self, id: Pid) -> i64 {
        let need = self.need(id);
        if self.people[id as usize].insight < need {
            return self.cultivate(id);
        }
        let realm = self.people[id as usize].realm;
        let cost = self.cfg.break_cost * ((realm % self.cfg.realm_band) as f64 + 1.0).powi(2);
        let odds = self.break_odds(id);
        let got = self.draw_qi(id, cost);
        let name = self.people[id as usize].name.clone();
        if got < 0.999 {
            // ฟ้าไม่มีให้ — ปราณที่ดูดมาแล้วไม่สูญ แต่ข้ามไม่ได้
            let wname = self.worlds[self.people[id as usize].world as usize].name.clone();
            self.emit("ข้ามขั้น", Some(id), None, "ปราณไม่พอ", format!("{}พร้อมข้ามขั้นแต่ปราณฟ้าดินใน{}เหลือไม่พอ", name, wname));
            return self.range(120, 400);
        }
        if self.chance(odds) {
            let p = &mut self.people[id as usize];
            p.insight -= need;
            p.realm += 1;
            p.peak_realm = p.peak_realm.max(p.realm);
            p.breaks += 1;
            p.injury *= 0.65;
            let rn = self.realm_name(self.people[id as usize].realm);
            self.emit("ข้ามขั้น", Some(id), None, "สำเร็จ", format!("{}ข้ามขั้นสู่{} (โอกาส {:.0}%)", name, rn, odds * 100.0));
        } else {
            let p = &mut self.people[id as usize];
            p.insight -= need * self.cfg.break_fail_spend;
            p.fails += 1;
            p.decay += self.cfg.backlash_decay * 0.5;
            p.injury = (p.injury + 0.2).min(1.0);
            // ล้มเหลวซ้ำหลายครั้งในขั้นสูง ธาตุไฟเข้าแทรกถึงตายได้
            let fails = p.fails.min(5) as f64;
            let deadly = (realm % self.cfg.realm_band) >= 5 && self.chance(0.04 * fails);
            self.emit("ข้ามขั้น", Some(id), None, "ล้มเหลว", format!("{}ข้ามขั้นล้มเหลว ธาตุไฟเข้าแทรก", name));
            if deadly {
                self.kill(id, None, "ธาตุไฟเข้าแทรกขณะข้ามขั้น", true);
            }
        }
        self.range(90, 400)
    }

    /// ข้ามฟ้า — ตันขั้นสูงสุดของชั้นแล้ว ทะลุขึ้นแดนบน (ทัณฑ์สวรรค์อาจคร่าชีวิต)
    pub fn ascend(&mut self, id: Pid) -> i64 {
        let w = self.people[id as usize].world as usize;
        let Some(up) = self.worlds[w].up else { return self.cultivate(id) };
        let name = self.people[id as usize].name.clone();
        let odds = self.cfg.ascend_odds * (0.5 + self.people[id as usize].root as f64) * (1.0 - 0.5 * self.people[id as usize].injury as f64);
        if self.chance(odds) {
            let dest_places = self.worlds[up as usize].places.clone();
            let dest = dest_places[self.rng.below(dest_places.len() as u64) as usize];
            self.move_to(id, dest);
            let p = &mut self.people[id as usize];
            p.world = up;
            p.realm += 1;
            p.peak_realm = p.peak_realm.max(p.realm);
            p.insight = 0.0;
            p.process = None;
            self.leave_sect(id);
            let wn = self.worlds[up as usize].name.clone();
            self.emit("ข้ามฟ้า", Some(id), None, "สำเร็จ", format!("{}ฝ่าทัณฑ์สวรรค์ ข้ามฟ้าขึ้นสู่{}", name, wn));
            self.range(30, 200)
        } else if self.chance(0.35) {
            self.kill(id, None, "สิ้นชีพใต้ทัณฑ์สวรรค์ขณะข้ามฟ้า", true);
            0
        } else {
            let p = &mut self.people[id as usize];
            p.injury = (p.injury + 0.5).min(1.0);
            p.insight *= 0.5;
            self.emit("ข้ามฟ้า", Some(id), None, "ล้มเหลว", format!("{}ทานทัณฑ์สวรรค์ไม่ไหว ร่วงกลับมาบาดเจ็บสาหัส", name));
            self.range(200, 700)
        }
    }

    pub fn teach(&mut self, id: Pid, student: Pid) -> i64 {
        let gift = 0.3 + 0.1 * (self.people[id as usize].realm as f64 - self.people[student as usize].realm as f64).max(0.0);
        self.people[student as usize].insight += gift;
        if self.people[student as usize].master.is_none() {
            self.people[student as usize].master = Some(id);
        }
        *self.people[student as usize].bonds.entry(id).or_insert(0) += 1;
        *self.people[id as usize].bonds.entry(student).or_insert(0) += 1;
        self.range(20, 90)
    }
}
