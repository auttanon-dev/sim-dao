//! ครรภ์/คลอด การเก็บกวาดผู้จากไป และสำนักรายเดือน

use crate::engine::data;
use crate::engine::model::*;
use crate::engine::sim::Engine;

impl Engine {

    // ------------------------------------------------------------------ ครอบครัว
    pub(crate) fn tick_families(&mut self, days: f64) {
        let ids: Vec<Pid> = self.alive.iter().copied().collect();
        for &id in &ids {
            let p = &self.people[id as usize];
            if !p.alive {
                continue;
            }
            if let Some((due, _)) = p.pregnant {
                if due <= self.day {
                    self.give_birth(id);
                }
                continue;
            }
            if !p.female {
                continue;
            }
            if let Some(s) = p.spouse {
                let q = &self.people[s as usize];
                if q.alive && q.place == p.place && q.process.is_none() && p.process.is_none() {
                    self.try_conceive(id, s, days);
                }
            }
        }
    }

    /// ผู้ที่ตายเกิน 30 ปีและไม่มีลูกเล็กเหลือ ย่อเหลือแค่ประวัติ (เซฟไม่โตไม่จำกัด)
    pub(crate) fn prune_departed(&mut self) {
        let cutoff = self.day - data::k("PRUNE_DEAD_YEARS") as i64 * 365;
        for i in 0..self.people.len() {
            let p = &self.people[i];
            if p.alive || p.death_day > cutoff || (p.skills.is_empty() && p.bonds.is_empty() && p.debts.is_empty()) {
                continue;
            }
            if p.children.iter().any(|&c| self.people[c as usize].alive && self.people[c as usize].age(self.day) < 14.0) {
                continue;
            }
            let p = &mut self.people[i];
            p.bonds.clear();
            p.rivals.clear();
            p.debts.clear();
            p.leads.clear();
            p.fragments.clear();
            p.foreseen.clear();
            p.visions.clear();
            p.skills.shrink_to_fit();
        }
    }

    // ------------------------------------------------------------------ สำนัก
}
