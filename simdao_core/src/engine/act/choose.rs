//! เลือกการกระทำ — เมนูน้ำหนักจากความต้องการ บุคลิก และสิ่งรอบตัว

use super::Act;
use crate::engine::data;
use crate::engine::model::*;
use crate::engine::sim::Engine;
use crate::physics;

impl Engine {

    // ------------------------------------------------------------------ เลือก
    pub fn choose(&mut self, id: Pid) -> Act {
        let mut menu: Vec<(Act, f64)> = Vec::with_capacity(16);
        let day = self.day;
        let p = self.people[id as usize].clone();
        let world = self.worlds[p.world as usize].clone();
        let here = self.present_at(p.place);
        let others: Vec<Pid> = here.iter().copied().filter(|&o| o != id && self.is_adult(o)).collect();
        let age = p.age(day);

        // ---- ปากท้อง
        let eats = self.eats(id);
        let local = self.places[p.place as usize].granary;
        let hungry = eats && p.hunger_days > 0.0;
        let locals = here.len() as f64 * self.cfg.ration_adult * 30.0;
        if hungry && local < locals {
            if let Some(dest) = self.food_destination(id) {
                menu.push((Act::SeekFood(dest), 40.0 + p.hunger_days as f64 * 2.0));
            }
        }

        // ---- ร่างกาย
        if p.injury > 0.4 {
            menu.push((Act::Rest, 20.0 * p.injury as f64));
        }

        // ---- งาน
        menu.push((Act::Work, if p.cultivator { 4.0 } else { 14.0 } + if p.gold < 5.0 { 10.0 } else { 0.0 }));

        // ---- วัตถุดิบ
        let d = data::world();
        if let Some(m) = d.places[p.place as usize].material.as_deref().and_then(Material::from_th) {
            let st = self.places[p.place as usize].stock[m as usize] / self.cfg.eco_cap;
            menu.push((Act::Harvest(m), 5.0 * st * (0.5 + p.greed as f64)));
        }
        let held: f32 = p.mats.iter().sum();
        if held > 4.0 {
            menu.push((Act::Sell, 3.0 + held as f64 * 0.5));
        }

        // ---- วิถีบำเพ็ญ
        if !p.cultivator {
            if p.root >= self.cfg.root_cultivate_min as f32 && age < 40.0 {
                let teacher = p.parents.iter().flatten().any(|&q| self.people[q as usize].cultivator)
                    || others.iter().any(|&o| self.people[o as usize].cultivator && self.people[o as usize].realm >= 2);
                menu.push((Act::BeginPath, (p.root as f64) * if teacher { 8.0 } else { 1.5 } * (0.5 + p.ambition as f64)));
            }
        } else {
            let need = self.need(id);
            let progress = p.insight / need;
            let cap = self.cfg.realm_cap_of_tier(p.tier(self.cfg.realm_band));
            menu.push((Act::Cultivate, 12.0 * (0.4 + p.root as f64)));
            menu.push((Act::Train, 10.0 + if p.skills.is_empty() { 8.0 } else { 0.0 }));
            if p.blood[SPIRIT] >= 0.3 && p.refine < p.blood[SPIRIT] as f64 {
                menu.push((Act::RefineBlood, 8.0 * p.blood[SPIRIT] as f64));
            }
            if progress < 0.9 && (p.realm >= self.cfg.bigu_realm || p.pack > 60.0) {
                menu.push((Act::Seclude, 3.0 + 4.0 * p.ambition as f64));
            }
            if p.realm < cap && progress >= self.cfg.break_look_ahead {
                let odds = self.break_odds(id);
                let life_left = (self.lifespan_of(id) - age).max(0.1) * 365.0;
                let z_rate = 0.5 / 365.0; // ความเข้าใจที่เพิ่มต่อวันดันกำแพงลงราวนี้
                let wait = physics::best_wait_days(odds, z_rate, life_left, Some(3650.0));
                let w = if wait < 180.0 { 30.0 } else { 4.5 };
                menu.push((Act::Breakthrough, w));
            }
            if p.realm == cap && world.up.is_some() && progress >= 1.0 {
                let up = world.up.unwrap() as usize;
                if self.worlds[up].closed {
                    // ประตูปิด — ทุบค่ายกลแดนบน (ความบาดหมางของแดนผลักให้ลงมือ)
                    let w = data::k("HEAVEN_WAR_W") * (1.0 + 0.5 * world.resentment.min(4.0));
                    menu.push((Act::HeavenWar, w * 0.3));
                } else {
                    menu.push((Act::Ascend, 10.0 + 10.0 * p.ambition as f64));
                }
            }
            // ไปหาที่ปราณหนา
            if self.qi[p.place as usize] < 0.55 {
                if let Some(dest) = self.qi_destination(id) {
                    menu.push((Act::SeekQi(dest), 3.0));
                }
            }
            // สำนัก
            match p.sect {
                None if p.realm <= self.cfg.sect_join_realm_max + p.tier(self.cfg.realm_band) * self.cfg.realm_band => {
                    if let Some(s) = self.sect_nearby(id) {
                        menu.push((Act::JoinSect(s), 5.0 * p.loyalty as f64 + 1.0));
                    }
                }
                None if p.ambition > 0.5 && self.can_found_sect(id) => {
                    menu.push((Act::FoundSect, 3.0 * p.ambition as f64));
                }
                Some(s) => {
                    let home = self.polities[s as usize].seat;
                    if home != p.place && self.chance(0.3) {
                        menu.push((Act::GoHome(home), 2.0));
                    }
                }
                _ => {}
            }
            // สอนศิษย์ที่อยู่ด้วยกัน
            if p.realm >= 3 {
                if let Some(&stu) = others.iter().find(|&&o| {
                    let q = &self.people[o as usize];
                    q.cultivator && q.realm + 2 <= p.realm && (q.master == Some(id) || (q.sect.is_some() && q.sect == p.sect))
                }) {
                    menu.push((Act::Teach(stu), 3.0 + 4.0 * p.compassion as f64));
                }
            }
        }

        // ---- ผู้คน
        if p.spouse.is_none() && age >= self.cfg.marry_min_age && age < 55.0 {
            let mate = others.iter().copied().find(|&o| {
                let q = &self.people[o as usize];
                q.female != p.female && q.spouse.is_none() && q.age(day) >= self.cfg.marry_min_age && q.age(day) < 55.0
                    && !p.parents.contains(&Some(o)) && !q.parents.contains(&Some(id))
                    && p.parents.iter().flatten().all(|pp| !q.parents.contains(&Some(*pp)))
                    && p.grudge(o) == 0
            });
            if let Some(m) = mate {
                menu.push((Act::Court(m), 9.0));
            }
        }
        // คำสัญญา การหักหลัง และการสะสางเรื่องเก่ากับคนที่อยู่ตรงหน้า
        if let Some(&friend) = others.iter().filter(|&&o| p.bond(o) >= 2).max_by_key(|&&o| (p.bond(o), std::cmp::Reverse(o))) {
            if p.bond(friend) < 6 {
                menu.push((Act::Promise(friend), 0.3 + 0.6 * p.loyalty as f64));
            }
            if p.greed > 0.7 && p.loyalty < 0.3 && self.people[friend as usize].gold > 30.0 {
                menu.push((Act::Betray(friend), 1.5 * p.greed as f64));
            }
        }
        if let Some(d) = p.debts.iter().find(|d| !d.done && others.contains(&d.target)) {
            menu.push((Act::Settle(d.target), 4.0 + p.inner.min(8.0)));
        }
        // ล้างแค้น — ศัตรูที่อยู่ตรงหน้า
        if let Some((&foe, &g)) = p.rivals.iter().filter(|(f, _)| others.contains(f)).max_by_key(|(_, &g)| g) {
            if g >= 2 {
                menu.push((Act::Revenge(foe), 1.5 * g as f64 * (1.0 - 0.6 * p.compassion as f64)));
            }
        }
        if p.cultivator && !others.is_empty() && p.injury < 0.3 {
            let rival = others[self.rng.below(others.len() as u64) as usize];
            let q = &self.people[rival as usize];
            if q.cultivator && (q.realm as i32 - p.realm as i32).abs() <= 2 {
                menu.push((Act::Duel(rival), 0.4 + 1.2 * p.ambition as f64));
            }
        }
        if p.greed > 0.6 && p.compassion < 0.4 && !others.is_empty() {
            let mark = others[self.rng.below(others.len() as u64) as usize];
            if self.people[mark as usize].gold > 20.0 {
                // ความเสี่ยงถูกโต้กลับในที่ที่เพิ่งมีการนองเลือด — คนระวังตัวมากกว่า
                let heat = physics::hawkes_intensity(0.2, Some(world.blood_marks.iter().map(|&d| d as f64).collect()), day as f64, self.cfg.hawkes_alpha, self.cfg.hawkes_decay_days);
                menu.push((Act::Rob(mark), 0.8 * p.greed as f64 / (1.0 + heat)));
            }
        }
        self.trade_options(id, &others, &mut menu);
        self.profession_options(id, &others, &mut menu);
        // หลอมค่ายกล/หุ่นกล · จำลองอนาคต
        if self.line_grade(id, "หุ่นกล") >= 0 || self.line_grade(id, "ค่ายกล") >= 0 {
            menu.push((Act::CraftArray, 4.0));
        }
        if p.foresight && !self.fork && self.day >= p.foresight_ready {
            menu.push((Act::Foresee, data::k("FORESIGHT_W")));
        }
        // ล่าอสูร ค้นแดนลับ ซ่อนตัว ชิงสมบัติ
        let cores_here = self.places[p.place as usize].stock[Material::Core as usize];
        if p.cultivator && cores_here > 5.0 {
            menu.push((Act::Hunt, 4.0 + 6.0 * (cores_here / self.cfg.eco_cap).min(1.0)));
        }
        if p.cultivator || p.fate > 1 {
            menu.push((Act::Search, 2.5 + 6.0 * p.leads.len() as f64 + if d.places[p.place as usize].kind == "แดนลับ" { 4.0 } else { 0.0 }));
        }
        if p.cultivator && (p.realm % self.cfg.realm_band) as f64 >= data::k("CACHE_MIN_REALM") && age > 0.6 * self.lifespan_of(id) {
            menu.push((Act::Hide, 0.6));
        }
        if p.greed > 0.6 {
            if let Some(&t) = others.iter().find(|&&o| self.people[o as usize].items.iter().any(|i| self.items.get(i).map_or(false, |it| it.legend || it.grade >= 2.0))) {
                menu.push((Act::Seize(t), 1.5 * p.greed as f64));
            }
        }
        if self.profession_is(id, &crate::engine::trades::GUARDS) {
            if let Some(&crook) = others.iter().filter(|&&o| self.people[o as usize].crimes > 0).max_by_key(|&&o| (self.people[o as usize].crimes, std::cmp::Reverse(o))) {
                menu.push((Act::Arrest(crook), 8.0 + 4.0 * self.people[crook as usize].crimes as f64));
            }
        }
        menu.push((Act::Wander, 1.5));

        let total: f64 = menu.iter().map(|(_, w)| w.max(0.0)).sum();
        let mut r = self.rng.next_f64() * total;
        for (a, w) in &menu {
            let w = w.max(0.0);
            if r < w {
                return *a;
            }
            r -= w;
        }
        Act::Work
    }
}
