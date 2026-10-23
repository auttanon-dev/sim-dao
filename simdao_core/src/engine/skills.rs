//! วิชา ความชำนาญ ห้าธาตุ และสายบำเพ็ญกาย/จิต
//!
//! วิชา 152 วิชาจากตารางต้นฉบับ: (ชื่อ, สาย, ชั้นฟ้า, เกรด, ผล, แก้ทางโกลาหล)
//! - รู้วิชาเฉยๆ ได้พลังฐาน ฝึกจนช่ำชองได้เพิ่ม (กฎกำลังของการฝึกซ้ำ: physics.practice_mastery)
//! - ห้าธาตุวางบนวงกลมตามวงจรเกิด ห่างกันจุดละ 72° — คู่ข่มคือห่างกันสองก้าวพอดี (cos 144° = −0.81)
//! - สายกาย/จิต คำนวณสดจากวิชาที่รู้จริง: กายทนทาน จิตข้ามขั้นง่าย สมดุลยืนต้านโกลาหลได้

use super::data::{self, k};
use super::model::*;
use super::sim::Engine;
use crate::physics;
use std::sync::OnceLock;

pub struct Skill {
    pub name: String,
    pub line: String,
    pub tier: u8,
    pub grade: u8,
    pub effect: String,
    pub anti_chaos: bool,
    pub element: u8,
    pub body: bool,   // สายกาย (ไม่ใช่ = สายจิต)
}

pub const ELEMENTS: [&str; 5] = ["ไม้", "ไฟ", "ดิน", "ทอง", "น้ำ"];

static SKILLS: OnceLock<Vec<Skill>> = OnceLock::new();

pub fn skills() -> &'static Vec<Skill> {
    SKILLS.get_or_init(|| {
        let body_lines = data::strs(data::table("paths", "BODY_LINES"));
        let elem = &data::tables()["derived"]["skill_element"];
        data::table("skills", "SKILLS")
            .as_array()
            .unwrap()
            .iter()
            .map(|r| {
                let name = r[0].as_str().unwrap().to_string();
                let line = r[1].as_str().unwrap().to_string();
                let el = elem[name.as_str()].as_str().unwrap_or("ดิน");
                Skill {
                    element: ELEMENTS.iter().position(|e| *e == el).unwrap_or(2) as u8,
                    body: body_lines.contains(&line),
                    tier: r[2].as_u64().unwrap() as u8,
                    grade: r[3].as_u64().unwrap() as u8,
                    effect: r[4].as_str().unwrap_or("").to_string(),
                    anti_chaos: r[5].as_bool().unwrap_or(false),
                    name,
                    line,
                }
            })
            .collect()
    })
}

pub fn grade_power(g: u8) -> f64 {
    [0.4, 1.2, 3.2][g.min(2) as usize]
}

pub fn grade_bar(g: u8) -> u8 {
    [0, 3, 6][g.min(2) as usize]
}

/// ความเข้ากันของสองธาตุ: cos(72° × จำนวนก้าวบนวงจรเกิด)
pub fn affinity(a: u8, b: u8) -> f64 {
    let steps = ((a as i32 - b as i32).rem_euclid(5)).min((b as i32 - a as i32).rem_euclid(5));
    (72.0f64 * steps as f64).to_radians().cos()
}

/// ความได้เปรียบเมื่อธาตุ a ปะทะธาตุ b (มีทิศทาง — น้ำดับไฟ ไม่ใช่ไฟดับน้ำ)
pub fn clash_edge(a: u8, b: u8) -> f64 {
    if a == b {
        return 0.0;
    }
    let strong = (144.0f64).to_radians().cos().abs();
    let weak = (72.0f64).to_radians().cos().abs();
    let overcomes = |x: u8| (x + 2) % 5; // ไม้ข่มดิน ไฟข่มทอง ดินข่มน้ำ ทองข่มไม้ น้ำข่มไฟ
    let generates = |x: u8| (x + 1) % 5;
    if overcomes(a) == b {
        strong
    } else if overcomes(b) == a {
        -strong
    } else if generates(a) == b {
        -weak
    } else {
        weak
    }
}

impl Engine {
    pub fn skill_power(&self, id: Pid) -> f64 {
        let p = &self.people[id as usize];
        let rare = data::strs(data::table("config", "RARE_LINES"));
        let mut total = 0.0;
        for (i, &s) in p.skills.iter().enumerate() {
            let sk = &skills()[s as usize];
            let mut w = grade_power(sk.grade) * (1.0 + 0.2 * sk.tier as f64);
            if rare.contains(&sk.line) {
                w *= k("RARE_LINE_MULT");
            }
            let m = physics::practice_mastery_impl(p.mastery[i] as f64, k("PRACTICE_EXPONENT"));
            total += w * (k("SKILL_BASE_SHARE") + k("SKILL_MASTERY_SHARE") * m);
        }
        total
    }

    /// สัดส่วน (กาย, จิต) จากวิชาที่รู้ — (0,0) ถ้ายังน้อยเกินบอกได้
    pub fn path_shares(&self, id: Pid) -> (f64, f64) {
        let (mut b, mut s) = (0.0, 0.0);
        for &i in &self.people[id as usize].skills {
            let sk = &skills()[i as usize];
            let w = [1.0, 1.8, 3.0][sk.grade.min(2) as usize];
            if sk.body {
                b += w;
            } else {
                s += w;
            }
        }
        if b + s < 2.0 {
            (0.0, 0.0)
        } else {
            (b / (b + s), s / (b + s))
        }
    }

    pub fn path_name(&self, id: Pid) -> &'static str {
        let (b, s) = self.path_shares(id);
        if b == 0.0 && s == 0.0 {
            "ยังไม่แน่ชัด"
        } else if b >= 0.35 && s >= 0.35 {
            "สมดุลกายจิต"
        } else if b > s {
            "กายบำเพ็ญ"
        } else {
            "จิตบำเพ็ญ"
        }
    }

    pub fn is_balanced(&self, id: Pid) -> bool {
        let (b, s) = self.path_shares(id);
        b >= 0.35 && s >= 0.35
    }

    pub fn has_anti_chaos(&self, id: Pid) -> bool {
        self.people[id as usize].skills.iter().any(|&s| skills()[s as usize].anti_chaos) || self.holds_anti_chaos_treasure(id)
    }

    /// ฝีมือปิดรอยแยก — วิชามิติ (สองเท่า) ค่ายกล และวิชาแก้ทางโกลาหล
    pub fn sealer_skill(&self, id: Pid) -> f64 {
        let p = &self.people[id as usize];
        let mut m = 0.0;
        for &s in &p.skills {
            let sk = &skills()[s as usize];
            if sk.line == "มิติ" {
                m += 2.0 * (1.0 + sk.grade as f64);
            } else if sk.line == "ค่ายกล" {
                m += 1.0 + sk.grade as f64;
            }
        }
        if self.has_anti_chaos(id) && m > 0.0 {
            m += 3.0;
        }
        m
    }

    pub fn learn_skill(&mut self, id: Pid, s: u16) -> bool {
        let p = &mut self.people[id as usize];
        if p.skills.contains(&s) {
            return false;
        }
        p.skills.push(s);
        p.mastery.push(1);
        true
    }

    /// ฝึกวิชา — หาวิชาใหม่ตามขั้นและธาตุ หรือฝึกวิชาเดิมให้ลึกขึ้น
    pub fn train(&mut self, id: Pid) -> i64 {
        let gap = self.range(60, 300);
        let p = &self.people[id as usize];
        let band = self.cfg.realm_band;
        let r = p.realm % band;
        let tier = (p.realm / band).min(2);
        let top: u8 = if r >= grade_bar(2) { 2 } else if r >= grade_bar(1) { 1 } else { 0 };
        let choices = [top, top.saturating_sub(1), top.saturating_sub(1), top.saturating_sub(2)];
        let grade = choices[self.rng.below(4) as usize];
        let pool: Vec<u16> = skills()
            .iter()
            .enumerate()
            .filter(|(i, s)| s.tier == tier && s.grade == grade && !p.skills.contains(&(*i as u16)))
            .map(|(i, _)| i as u16)
            .collect();
        let deepen_p = k("DEEPEN_W") * (p.skills.len() as f64 / k("DEEPEN_AFTER")).min(1.0);
        let has = !p.skills.is_empty();
        let el = p.element;
        let world = p.world;
        if has && (pool.is_empty() || self.chance(deepen_p)) {
            let p = &mut self.people[id as usize];
            let (i, _) = p.mastery.iter().enumerate().min_by_key(|(i, &m)| (m, p.skills[*i])).unwrap();
            let before = physics::practice_mastery_impl(p.mastery[i] as f64, k("PRACTICE_EXPONENT"));
            p.mastery[i] = p.mastery[i].saturating_add(1);
            let after = physics::practice_mastery_impl(p.mastery[i] as f64, k("PRACTICE_EXPONENT"));
            p.insight += k("DEEPEN_INSIGHT") * (after - before) * 10.0;
            return gap;
        }
        if pool.is_empty() {
            return self.cultivate(id);
        }
        // สายประจำแดนสาขา → ธาตุของตัวเอง
        let line = self.branch_line(world);
        let mut choice: Vec<u16> = pool.clone();
        if let Some(line) = line {
            let same: Vec<u16> = pool.iter().copied().filter(|&s| skills()[s as usize].line == line).collect();
            if !same.is_empty() && self.chance(k("BRANCH_SKILL_BIAS")) {
                choice = same;
            }
        }
        let mut sk = choice[self.rng.below(choice.len() as u64) as usize];
        if self.chance(k("ELEMENT_PICK_P")) {
            sk = *choice.iter().max_by(|&&a, &&b| affinity(el, skills()[a as usize].element).partial_cmp(&affinity(el, skills()[b as usize].element)).unwrap().then(b.cmp(&a))).unwrap();
        }
        let s = &skills()[sk as usize];
        let aff = affinity(el, s.element);
        let p = &self.people[id as usize];
        let pw = (k("LEARN_BASE_P") + 0.05 * (r as f64 - grade_bar(grade) as f64) - 0.12 * grade as f64 - p.decay * 0.05 + k("ELEMENT_LEARN_W") * aff).clamp(0.05, 0.95);
        let name = p.name.clone();
        if !self.chance(pw) {
            let p = &mut self.people[id as usize];
            p.decay += k("LEARN_BACKFIRE") * (0.5 + 0.4 * grade as f64);
            p.insight += k("TRAIN_FAIL_INSIGHT");
            return gap;
        }
        let p = &mut self.people[id as usize];
        p.insight += k("TRAIN_INSIGHT_BASE") + k("TRAIN_INSIGHT_PER_GRADE") * grade as f64;
        p.refine += k("TRAIN_REFINE") * (1.0 + 0.5 * grade as f64);
        self.learn_skill(id, sk);
        if grade >= 1 || s.anti_chaos {
            let extra = if s.anti_chaos { " — วิชาที่แก้ทางเผ่าโกลาหลได้" } else { "" };
            self.emit("ฝึกวิชา", Some(id), None, "สำเร็จ", format!("{}ฝึก{}สำเร็จ ({}){}", name, s.name, s.effect, extra));
        }
        gap
    }

    /// สายวิชาประจำแดนสาขา (ถ้ามี)
    pub fn branch_line(&self, world: u16) -> Option<String> {
        let w = &self.worlds[world as usize];
        if w.kind != WorldKind::Branch {
            return None;
        }
        data::world().branch_realms.iter().find(|b| b.key == w.key).map(|b| b.skill_line.clone())
    }

    /// ถ่ายทอดวิชาที่ครูชำนาญที่สุดซึ่งศิษย์ยังไม่มี — โอกาสตามขั้น ธาตุ และความลึกของครู
    pub fn teach_skill(&mut self, teacher: Pid, student: Pid) -> bool {
        let t = &self.people[teacher as usize];
        let st = &self.people[student as usize];
        let cand = t
            .skills
            .iter()
            .enumerate()
            .filter(|(_, s)| !st.skills.contains(s))
            .filter(|(_, &s)| grade_bar(skills()[s as usize].grade) <= (st.realm % self.cfg.realm_band) + 2)
            .max_by_key(|(i, &s)| (t.mastery[*i], std::cmp::Reverse(s)));
        let Some((i, &s)) = cand else { return false };
        let sk = &skills()[s as usize];
        let deep = physics::practice_mastery_impl(t.mastery[i] as f64, k("PRACTICE_EXPONENT"));
        let p = (k("TEACH_BASE_P") + k("TEACH_REALM_W") * ((st.realm % self.cfg.realm_band) as f64 - grade_bar(sk.grade) as f64) + k("ELEMENT_LEARN_W") * affinity(st.element, sk.element) + k("TEACH_DEPTH_W") * deep).clamp(0.05, 0.95);
        if self.chance(p) {
            self.learn_skill(student, s);
            let (tn, sn) = (self.people[teacher as usize].name.clone(), self.people[student as usize].name.clone());
            self.emit("ถ่ายทอดวิชา", Some(teacher), Some(student), "สำเร็จ", format!("{}ถ่ายทอด{}ให้{}", tn, sk.name, sn));
            true
        } else {
            false
        }
    }

    /// ธาตุของวิชาที่ชำนาญที่สุด (ใช้ตอนปะทะ) — ไม่มีวิชาใช้ธาตุประจำตัว
    pub fn fighting_element(&self, id: Pid) -> u8 {
        let p = &self.people[id as usize];
        p.skills
            .iter()
            .zip(p.mastery.iter())
            .max_by_key(|(&s, &m)| (m, std::cmp::Reverse(s)))
            .map(|(&s, _)| skills()[s as usize].element)
            .unwrap_or(p.element)
    }
}

impl Engine {
    /// ถือตราประทับสุญตาสยบโกลาหลอยู่ไหม (ระบบของวิเศษเติมภายหลัง)
    pub fn holds_anti_chaos_treasure(&self, _id: Pid) -> bool {
        false
    }
}
