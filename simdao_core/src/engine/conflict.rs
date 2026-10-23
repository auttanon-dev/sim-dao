//! การปะทะ — ประลอง ล้างแค้น ปล้น
//!
//! ผลแพ้ชนะมาจากกฎกำลังยกกำลังสองของแลนเชสเตอร์บนพลังของสองฝ่าย ส่วนจะถึงตายหรือไม่
//! ขึ้นกับว่าห่างกันแค่ไหนและเป็นการวัดฝีมือหรือความแค้น — การประลองฉันมิตรตายยาก

use super::model::*;
use super::sim::Engine;
use crate::physics;

impl Engine {
    /// คืน (ผู้ชนะ, ผู้แพ้, ส่วนต่างพลังเทียบผู้แพ้)
    fn clash(&mut self, a: Pid, b: Pid) -> (Pid, Pid, f64) {
        let (pa, pb) = (self.power(a).max(0.1), self.power(b).max(0.1));
        // ความได้เปรียบไม่ใช่ทั้งหมด — ความกลัว จังหวะ ดวง ทำให้ฝ่ายอ่อนชนะได้บ้าง
        let p_a = physics::logistic((pa - pb) / (0.25 * (pa + pb) + 1.0) * 3.0);
        let a_wins = self.chance(p_a);
        let (w, l, pw, pl) = if a_wins { (a, b, pa, pb) } else { (b, a, pb, pa) };
        (w, l, pw / pl)
    }

    pub fn duel(&mut self, a: Pid, b: Pid, revenge: bool) -> i64 {
        if !self.people[b as usize].alive || self.people[b as usize].place != self.people[a as usize].place {
            return self.range(5, 20);
        }
        let (w, l, ratio) = self.clash(a, b);
        let grudge = self.people[w as usize].grudge(l).max(self.people[l as usize].grudge(w));
        let lethal_at = if revenge || grudge > 0 { self.cfg.death_margin } else { self.cfg.death_margin * self.cfg.duel_friendly_mult };
        let kind = if revenge { "ล้างแค้น" } else { "ประลอง" };
        let (wn, ln) = (self.people[w as usize].name.clone(), self.people[l as usize].name.clone());
        for x in [w, l] {
            self.people[x as usize].decay += self.cfg.decay_per_fight;
        }
        if ratio >= lethal_at && (revenge || self.chance(0.5)) {
            self.kill(l, Some(w), &format!("ถูก{}สังหารใน{}", wn, kind), false);
            // ล้างแค้นสำเร็จ ความแค้นสงบ
            self.people[w as usize].rivals.remove(&l);
        } else {
            let hurt = (0.15 + 0.25 * (ratio - 1.0)).clamp(0.1, 0.8) as f32;
            let p = &mut self.people[l as usize];
            p.injury = (p.injury + hurt).min(1.0);
            // แพ้ห่างหรือถูกเล่นงานด้วยความแค้น = อัปยศ ผูกใจเจ็บ · แพ้สูสีในการประลอง = นับถือกัน
            if revenge || ratio > 1.4 {
                *self.people[l as usize].rivals.entry(w).or_insert(0) += 1;
            } else {
                *self.people[l as usize].bonds.entry(w).or_insert(0) += 1;
                *self.people[w as usize].bonds.entry(l).or_insert(0) += 1;
            }
            let text = if revenge {
                format!("{}ตามล้างแค้น{} — {}เป็นฝ่ายพ่ายบาดเจ็บ", self.people[a as usize].name, self.people[b as usize].name, ln)
            } else {
                format!("{}ประลองกับ{} — {}ชนะ", self.people[a as usize].name, self.people[b as usize].name, wn)
            };
            self.emit(kind, Some(a), Some(b), if w == a { "ชนะ" } else { "แพ้" }, text);
        }
        self.range(10, 60)
    }

    /// จับกุม — ปะทะกับผู้ต้องหา ถ้าชนะคืนของให้ผู้เสียหายแล้วคุมขังตามความผิด
    pub fn arrest(&mut self, guard: Pid, crook: Pid, loot: Option<(Pid, f64)>) -> i64 {
        if !self.people[crook as usize].alive || self.people[crook as usize].place != self.people[guard as usize].place {
            return self.range(5, 20);
        }
        let (w, _l, ratio) = self.clash(guard, crook);
        let (gn, cn) = (self.people[guard as usize].name.clone(), self.people[crook as usize].name.clone());
        if w == guard {
            if let Some((victim, amount)) = loot {
                let back = amount.min(self.people[crook as usize].gold);
                self.people[crook as usize].gold -= back;
                if self.people[victim as usize].alive {
                    self.people[victim as usize].gold += back;
                } else {
                    // ผู้เสียหายตายแล้ว — ของกลางตกเป็นของชุมชน
                    let place = self.people[crook as usize].place as usize;
                    self.places[place].treasury += back;
                }
            }
            let crimes = self.people[crook as usize].crimes.max(1) as i64;
            let years = (crimes).min(10);
            let until = self.day + years * 365;
            let p = &mut self.people[crook as usize];
            p.crimes = 0;
            p.process = Some(Process::Jail { until });
            self.schedule(crook, years * 365);
            self.emit("จับกุม", Some(guard), Some(crook), "คุมขัง", format!("{}จับกุม{} ตัดสินจำคุก {} ปี", gn, cn, years));
        } else {
            let p = &mut self.people[guard as usize];
            p.injury = (p.injury + 0.25).min(1.0);
            *self.people[crook as usize].rivals.entry(guard).or_insert(0) += 1;
            if ratio > self.cfg.death_margin * 1.3 && self.chance(0.3) {
                self.people[crook as usize].crimes += 3;
                self.kill(guard, Some(crook), &format!("ถูก{}สังหารขณะเข้าจับกุม", cn), false);
            } else {
                self.emit("จับกุม", Some(guard), Some(crook), "หลบหนี", format!("{}เข้าจับกุม{}แต่ถูกตีถอย", gn, cn));
            }
        }
        self.range(10, 40)
    }

    pub fn rob(&mut self, a: Pid, b: Pid) -> i64 {
        if !self.people[b as usize].alive || self.people[b as usize].place != self.people[a as usize].place {
            return self.range(5, 20);
        }
        let (w, l, ratio) = self.clash(a, b);
        let (an, bn) = (self.people[a as usize].name.clone(), self.people[b as usize].name.clone());
        if w == a {
            let take = self.people[b as usize].gold * (0.3 + 0.4 * self.rng.next_f64());
            self.people[b as usize].gold -= take;
            self.people[a as usize].gold += take;
            *self.people[b as usize].rivals.entry(a).or_insert(0) += 2;
            let p = &mut self.people[b as usize];
            p.injury = (p.injury + 0.15).min(1.0);
            self.people[a as usize].crimes += 1;
            if ratio > self.cfg.death_margin * 1.5 && self.chance(0.25) {
                self.people[a as usize].crimes += 3;
                self.kill(b, Some(a), &format!("ถูก{}ปล้นฆ่า", an), false);
            } else {
                self.emit("ปล้น", Some(a), Some(b), "ปล้นสำเร็จ", format!("{}ดักปล้น{} ได้ไป {:.0} ตำลึง", an, bn, take));
            }
            // มือปราบที่อยู่ในที่เกิดเหตุเข้าจับกุม
            let place = self.people[a as usize].place;
            let guards: Vec<Pid> = self
                .present_at(place)
                .into_iter()
                .filter(|&g| g != a && g != b && self.is_adult(g) && self.profession_is(g, &super::trades::GUARDS))
                .collect();
            if let Some(&g) = guards.first() {
                if self.chance(1.0 - 0.6f64.powi(guards.len() as i32)) {
                    self.arrest(g, a, Some((b, take)));
                }
            }
        } else {
            let p = &mut self.people[a as usize];
            p.injury = (p.injury + 0.3).min(1.0);
            *self.people[b as usize].rivals.entry(a).or_insert(0) += 1;
            if ratio > self.cfg.death_margin && self.chance(0.4) {
                self.kill(a, Some(b), &format!("ถูก{}สังหารขณะลงมือปล้น", bn), false);
            } else {
                self.emit("ปล้น", Some(a), Some(b), "ถูกตอบโต้", format!("{}คิดปล้น{}แต่ถูกตอบโต้จนต้องหนี", an, bn));
            }
        }
        let _ = l;
        self.range(15, 60)
    }
}
