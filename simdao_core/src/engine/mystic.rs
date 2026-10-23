//! ศาสตร์ลี้ลับ — หุ่นเชิด (หุ่นกล / เชิดศพ) วัฏจักรเวียนว่ายตายเกิด และระบบจำลองอนาคต
//!
//! ระบบจำลองอนาคตทำได้จริงเพราะโลกนี้เดินด้วย RNG เมล็ดเดียว: สำเนาโลกแล้วเดินต่อไปข้างหน้า
//! สิ่งที่เห็นคือสิ่งที่จะเกิดขึ้นจริงถ้าไม่มีใครทำอะไรต่างไป — โลกจริงไม่ขยับแม้แต่ tick เดียว

use super::data::{self, k};
use super::model::*;
use super::sim::Engine;
use super::skills::skills;

impl Engine {
    // ------------------------------------------------------------------ หุ่นเชิด
    /// เกรดสูงสุดที่รู้ในสายวิชาหนึ่ง (-1 = ไม่รู้)
    pub fn line_grade(&self, id: Pid, line: &str) -> i32 {
        self.people[id as usize].skills.iter().filter(|&&s| skills()[s as usize].line == line).map(|&s| skills()[s as usize].grade as i32).max().unwrap_or(-1)
    }

    /// ถือหุ่นได้มากสุดกี่ตน — เกรดสายหุ่นเป็นฐาน บวกโบนัสจากวิชาสายจิต (แบ่งจิตไปคุมได้กี่ทาง)
    pub fn puppet_cap(&self, id: Pid) -> u8 {
        let g = self.line_grade(id, "หุ่นกล").max(self.line_grade(id, "เชิดศพ"));
        if g < 0 {
            return 0;
        }
        let caps = data::table("config", "PUPPET_CAP_BY_GRADE").as_array().unwrap();
        let base = caps[(g as usize).min(caps.len() - 1)].as_u64().unwrap() as u8;
        let mind_lines = data::strs(data::table("config", "PUPPET_MIND_LINES"));
        let mind: f64 = self.people[id as usize].skills.iter().filter(|&&s| mind_lines.contains(&skills()[s as usize].line)).map(|&s| 1.0 + skills()[s as usize].grade as f64).sum();
        base + ((mind / k("PUPPET_MIND_PER_SLOT")) as u8).min(k("PUPPET_MIND_MAX_BONUS") as u8)
    }

    /// หลอมค่ายกล — ผู้รู้สายหุ่นกลหลอมหุ่นจากแร่กับแก่นพลัง · คนอื่นหลอมอาวุธค่ายกล
    pub fn craft_array(&mut self, id: Pid) -> i64 {
        let gap = self.range(60, 240);
        let g = self.line_grade(id, "หุ่นกล");
        let name = self.people[id as usize].name.clone();
        if g >= 0 && self.people[id as usize].puppets < self.puppet_cap(id) {
            let (nc, nm) = (1.0 + g as f32, 2.0 + g as f32);
            let p = &mut self.people[id as usize];
            if p.mats[Material::Core as usize] < nc || p.mats[Material::Ore as usize] < nm {
                return gap / 2;
            }
            p.mats[Material::Core as usize] -= nc;
            p.mats[Material::Ore as usize] -= nm;
            if !self.chance(k("PUPPET_CRAFT_P")) {
                return gap;
            }
            let cap = self.puppet_cap(id);
            let p = &mut self.people[id as usize];
            p.puppets += 1;
            if p.puppet_kind.is_empty() {
                p.puppet_kind = "หุ่นกล".into();
            }
            let n = p.puppets;
            let kind = ["หุ่นไม้ชักใย", "หุ่นสัมฤทธิ์ไร้ความเจ็บ", "หุ่นเหล็กพันมือ"][(g as usize).min(2)];
            self.emit("หลอมค่ายกล", Some(id), None, "หลอมสำเร็จ", format!("{}หลอม{}ขึ้นมาได้อีกหนึ่งตน ({}/{} ตน)", name, kind, n, cap));
            return gap;
        }
        if data::world().places[self.people[id as usize].place as usize].forge < 0 {
            return gap / 2;
        }
        let p = &mut self.people[id as usize];
        if p.mats[Material::Ore as usize] < 3.0 || p.mats[Material::Core as usize] < 1.0 {
            return gap / 2;
        }
        p.mats[Material::Ore as usize] -= 3.0;
        p.mats[Material::Core as usize] -= 1.0;
        if !self.chance(k("ARRAY_CRAFT_P")) {
            return gap;
        }
        let types = data::table("config", "ARRAY_TYPES").as_object().unwrap();
        let names: Vec<&String> = types.keys().collect();
        let recipe = names[self.rng.below(names.len() as u64) as usize].clone();
        let tier = self.worlds[self.people[id as usize].world as usize].tier;
        let item = self.new_item("อาวุธค่ายกล", recipe.clone(), tier, 1.0, Some(id));
        self.people[id as usize].items.push(item);
        self.emit("หลอมค่ายกล", Some(id), None, "สำเร็จ", format!("{}หลอม{}สำเร็จ", name, recipe));
        gap
    }

    /// สายเชิดศพ: ฆ่าคนแล้วปลุกซากขึ้นเป็นหุ่น — ราคาคือจิตมารที่หนักขึ้น
    pub fn raise_corpse(&mut self, killer: Pid, victim: Pid) {
        if self.line_grade(killer, "เชิดศพ") < 0 || !self.people[killer as usize].alive {
            return;
        }
        let cap = self.puppet_cap(killer);
        if self.people[killer as usize].puppets >= cap || !self.chance(k("PUPPET_RAISE_P")) {
            return;
        }
        let p = &mut self.people[killer as usize];
        p.puppets += 1;
        p.puppet_kind = "เชิดศพ".into();
        p.inner += k("CORPSE_PUPPET_DEBT") * 0.25;
        let n = p.puppets;
        self.add_debt(killer, "เชิดศพ", victim);
        let (kn, vn) = (self.people[killer as usize].name.clone(), self.people[victim as usize].name.clone());
        self.emit("เชิดซากเป็นหุ่น", Some(killer), Some(victim), "ปลุกซากสำเร็จ", format!("{}ปลุกซากของ{}ที่ยังไม่ทันเย็นให้ลุกขึ้นเดินตามคำสั่ง ({}/{} ตน)", kn, vn, n, cap));
    }

    /// หุ่นพังเมื่อเจ้าของแพ้
    pub fn puppets_break(&mut self, id: Pid) {
        if self.people[id as usize].puppets > 0 && self.chance(k("PUPPET_BREAK_P")) {
            self.people[id as usize].puppets -= 1;
        }
    }

    // ------------------------------------------------------------------ วัฏจักร
    pub fn knows_cycle(&self, id: Pid) -> bool {
        let p = &self.people[id as usize];
        p.cycle_born || p.skills.iter().any(|&s| skills()[s as usize].line == "วัฏจักร")
    }

    /// ผู้ฝึกสายวัฏจักรตายแล้วไปเกิดใหม่ — ร่างเดิมตายจริง ดวงจิตไปเกิดเป็นคนใหม่ที่ยังจำอะไรไม่ได้
    pub fn reincarnate(&mut self, id: Pid) {
        let p = &self.people[id as usize];
        if p.rebirth_count as f64 >= k("REBIRTH_MAX") || !p.sentient || p.is_chaos() {
            return;
        }
        let own = p.skills.iter().any(|&s| skills()[s as usize].line == "วัฏจักร" && skills()[s as usize].grade >= 2);
        let dest = if own {
            p.world
        } else {
            let pool: Vec<u16> = self.worlds.iter().filter(|w| matches!(w.kind, WorldKind::Main | WorldKind::Sister) && w.tier == 0).map(|w| w.id).collect();
            pool[self.rng.below(pool.len() as u64) as usize]
        };
        let (old_name, old_realm, old_skills, count, old_dao) = (p.name.clone(), p.realm, p.skills.clone(), p.rebirth_count + 1, p.dao);
        let old_title = self.title(id);
        let baby = self.spawn(dest, None, 0.0, [None, None]);
        let seed = skills().iter().position(|s| s.line == "วัฏจักร" && s.grade == 0);
        let b = &mut self.people[baby as usize];
        b.cycle_born = true;
        b.rebirth_count = count;
        b.past_life = Some(id);
        b.past_realm = old_realm;
        b.past_skills = old_skills;
        b.past_dao = old_dao;
        b.fate = (b.fate + k("REBIRTH_FATE_BONUS") as i8).min(k("FATE_MAX") as i8);
        if let Some(s) = seed {
            self.learn_skill(baby, s as u16);
        }
        let (bn, wn) = (self.people[baby as usize].name.clone(), self.worlds[dest as usize].name.clone());
        let how = if own { "เลือกที่เกิดเองด้วยมหาอาคมจุติคืนสังสารวัฏ" } else { "แล้วแต่วาสนา" };
        self.emit("จุติคืนสังสารวัฏ", Some(baby), Some(id), "เกิดใหม่", format!("ดวงจิตของ{} ({}) ไม่สลายไปกับร่าง จุติใหม่ที่{}ในนาม{} — ชาติที่ {} ({})", old_name, old_title, wn, bn, count, how));
    }

    /// ตื่นความทรงจำชาติก่อนเมื่อบำเพ็ญถึงขั้นที่ดวงจิตรับไหว — ได้วิชาเดิมคืนบางส่วนและวิถีเดิม
    pub fn maybe_wake_past(&mut self, id: Pid) {
        let p = &self.people[id as usize];
        if !p.cycle_born || p.memory_woken || ((p.realm % self.cfg.realm_band) as f64) < k("REBIRTH_WAKE_REALM") {
            return;
        }
        let old: Vec<u16> = p.past_skills.iter().copied().filter(|s| !p.skills.contains(s)).collect();
        let keep = (old.len() as f64 * k("REBIRTH_SKILL_KEEP")) as usize;
        let mut pool = old.clone();
        self.rng.shuffle(&mut pool);
        for &s in pool.iter().take(keep) {
            self.learn_skill(id, s);
        }
        let p = &mut self.people[id as usize];
        p.memory_woken = true;
        p.dao = p.past_dao;
        let past = p.past_life.map(|x| self.people[x as usize].name.clone()).unwrap_or_default();
        let n = self.people[id as usize].name.clone();
        self.emit("ตื่นความทรงจำชาติก่อน", Some(id), None, "ระลึกชาติ", format!("{}บำเพ็ญถึงขั้นที่ดวงจิตทานรับไหว ภาพชาติก่อนในนาม{}หลั่งไหลกลับมา ระลึกวิชาได้ {} วิชา", n, past, keep));
    }

    // ------------------------------------------------------------------ ระบบจำลองอนาคต
    /// มอบระบบให้ตัวเอกหนึ่งคนในโลกมนุษย์ (ตอนสร้างโลก และเมื่อเจ้าของคนเดิมตาย)
    pub fn grant_foresight(&mut self) {
        if self.fork || self.alive.iter().any(|&i| self.people[i as usize].foresight) {
            return;
        }
        let pool: Vec<Pid> = self.living_in(0).into_iter().filter(|&i| {
            let p = &self.people[i as usize];
            p.sentient && p.age(self.day) < 30.0 && p.root as f64 >= self.cfg.root_cultivate_min * 0.8
        }).collect();
        if let Some(h) = self.pick(&pool) {
            self.people[h as usize].foresight = true;
            self.people[h as usize].foresight_ready = self.day;
            self.ledger.count("ระบบจำลองอนาคต");
        }
    }

    pub fn foresee(&mut self, id: Pid) -> i64 {
        let ties = self.ties_of(id);
        let day0 = self.day;
        let alive0: Vec<bool> = ties.iter().map(|&t| self.people[t as usize].alive).collect();
        let realm0: Vec<u8> = ties.iter().map(|&t| self.people[t as usize].realm).collect();
        let mut fork = self.clone();
        fork.fork = true;
        let seq0 = fork.seq;
        let target = day0 + k("FORESIGHT_HORIZON") as i64;
        let hard = day0 + k("FORESIGHT_HORIZON_MAX") as i64;
        let want = k("FORESIGHT_MIN_PERSONAL") as usize;
        let mut personal = 0;
        while fork.day < hard {
            if fork.day >= target && personal >= want {
                break;
            }
            let before = fork.seq;
            if !fork.step() {
                break;
            }
            personal += fork.log.iter().rev().take_while(|e| e.seq > before).filter(|e| e.actor == Some(id) || e.target == Some(id)).count();
        }
        let horizon = fork.day - day0;
        let when = |d: i64| {
            if d - day0 <= k("FORESIGHT_CLEAR_DAYS") as i64 {
                format!("ปีที่ {:.1}", d as f64 / 365.0)
            } else {
                format!("อีกราว {} เดือนข้างหน้า (ภาพพร่ามัว)", ((d - day0) / 30).max(1))
            }
        };
        let mut lines = Vec::new();
        let mut deaths = std::collections::BTreeMap::new();
        for (i, &t) in ties.iter().enumerate() {
            let f = &fork.people[t as usize];
            if alive0[i] && !f.alive {
                deaths.insert(t, f.death_day);
                let who = if t == id { "ตัวข้าเอง".to_string() } else { f.name.clone() };
                lines.push(format!("{}: {}จะตาย — {}", when(f.death_day), who, f.death_cause));
            } else if f.alive && f.realm > realm0[i] && t != id {
                lines.push(format!("ภายใน {} เดือน: {}จะไต่ถึง{}", horizon / 30, f.name, fork.title(t)));
            }
        }
        let hostile = data::strs(data::table("foresight", "HOSTILE"));
        let shaking = data::strs(data::table("foresight", "WORLD_SHAKING"));
        let world = self.people[id as usize].world;
        let mut mine = 0;
        for e in fork.log.iter().filter(|e| e.seq > seq0) {
            if e.target == Some(id) && hostile.contains(&e.kind) {
                let who = e.actor.map(|a| fork.people[a as usize].name.clone()).unwrap_or_else(|| "ใครบางคน".into());
                lines.push(format!("{}: {}จะ{}กับข้า — {}", when(e.day), who, e.kind, e.outcome));
            } else if e.actor == Some(id) && mine < 4 {
                lines.push(format!("{}: ข้าจะ{} — {}", when(e.day), e.kind, e.outcome));
                mine += 1;
            } else if shaking.contains(&e.kind) && e.world == world {
                lines.push(format!("{}: {} — {}", when(e.day), e.kind, e.outcome));
            }
        }
        lines.dedup();
        lines.truncate(k("FORESIGHT_MAX_LINES") as usize);
        if lines.is_empty() {
            lines.push(format!("ภาพว่างเปล่า — {} เดือนข้างหน้าไม่มีอะไรที่ฟ้ายอมให้ข้าเห็น", horizon / 30));
        }
        drop(fork);
        // ราคาของนิมิต: ชะตา ความเสื่อม และจิตมาร
        let p = &mut self.people[id as usize];
        p.fate = (p.fate - k("FORESIGHT_COST_FATE") as i8).max(0);
        p.decay += k("FORESIGHT_COST_DECAY");
        p.inner += k("FORESIGHT_INNER");
        p.foresight_ready = self.day + k("FORESIGHT_COOLDOWN_DAYS") as i64;
        for (t, d) in deaths {
            p.foreseen.insert(t, d);
        }
        p.visions.push(lines.clone());
        if p.visions.len() > 5 {
            p.visions.remove(0);
        }
        let n = p.name.clone();
        self.emit("จำลองอนาคต", Some(id), None, "เห็นนิมิต", format!("{}จำลองอนาคต {} เดือนข้างหน้า: {}", n, horizon / 30, lines.join(" · ")));
        self.range(1, 10)
    }

    /// คนผูกพันของผู้ใช้ระบบ — ตัวเอง คู่ครอง ลูก พ่อแม่ อาจารย์ สหายสนิท
    fn ties_of(&self, id: Pid) -> Vec<Pid> {
        let p = &self.people[id as usize];
        let mut v = vec![id];
        v.extend(p.spouse);
        v.extend(p.children.iter().take(5));
        v.extend(p.parents.iter().flatten());
        v.extend(p.master);
        v.extend(p.bonds.iter().filter(|(_, &b)| b >= 3).map(|(&k, _)| k).take(5));
        v.sort_unstable();
        v.dedup();
        v
    }

    /// นิมิตที่หมดอายุ — เกิดตามที่เห็น หรือถูกเปลี่ยนไปแล้ว
    pub fn check_fate(&mut self) {
        let grace = k("FORESIGHT_GRACE_DAYS") as i64;
        let seers: Vec<Pid> = self.people.iter().filter(|p| !p.foreseen.is_empty()).map(|p| p.id).collect();
        for s in seers {
            let due: Vec<(Pid, i64)> = self.people[s as usize].foreseen.iter().filter(|(_, &d)| self.day >= d + grace).map(|(&t, &d)| (t, d)).collect();
            for (t, d) in due {
                self.people[s as usize].foreseen.remove(&t);
                let o = &self.people[t as usize];
                let changed = o.alive || (o.death_day - d).abs() > grace;
                if changed {
                    self.people[s as usize].fate_changed += 1;
                    if self.people[s as usize].alive && self.people[t as usize].alive {
                        let (sn, tn) = (self.people[s as usize].name.clone(), self.people[t as usize].name.clone());
                        let c = self.people[s as usize].fate_changed;
                        self.emit("เปลี่ยนชะตา", Some(s), Some(t), "ชะตาเปลี่ยนไป", format!("{}ควรตายไปแล้วตามนิมิตที่{}เห็น แต่วันนั้นผ่านไปโดยที่เขายังอยู่ (เปลี่ยนชะตาได้แล้ว {} ครั้ง)", tn, sn, c));
                    }
                } else {
                    self.people[s as usize].fate_kept += 1;
                }
            }
        }
    }
}
