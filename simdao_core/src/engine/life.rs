//! ชีวิต — เกิด ตั้งชื่อ ตั้งครรภ์ คลอด ตาย มรดก

use super::data::{self, Tribe};
use super::model::*;
use super::sim::Engine;
use crate::physics;
use std::collections::BTreeMap;

/// ปกติมาตรฐาน: CDF และ inverse CDF (Acklam) สำหรับอายุขัยแบบปกติตัดปลาย
fn norm_cdf(x: f64) -> f64 {
    0.5 * (1.0 + erf(x / std::f64::consts::SQRT_2))
}

fn erf(x: f64) -> f64 {
    // Abramowitz–Stegun 7.1.26 (คลาดไม่เกิน 1.5e-7)
    let t = 1.0 / (1.0 + 0.3275911 * x.abs());
    let y = 1.0
        - (((((1.061405429 * t - 1.453152027) * t) + 1.421413741) * t - 0.284496736) * t + 0.254829592)
            * t
            * (-x * x).exp();
    if x >= 0.0 {
        y
    } else {
        -y
    }
}

fn norm_inv(p: f64) -> f64 {
    let p = p.clamp(1e-12, 1.0 - 1e-12);
    let a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02, 1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00];
    let b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02, 6.680131188771972e+01, -1.328068155288572e+01];
    let c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00, -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00];
    let dd = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00, 3.754408661907416e+00];
    let pl = 0.02425;
    if p < pl {
        let q = (-2.0 * p.ln()).sqrt();
        (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / ((((dd[0] * q + dd[1]) * q + dd[2]) * q + dd[3]) * q + 1.0)
    } else if p <= 1.0 - pl {
        let q = p - 0.5;
        let r = q * q;
        (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q
            / (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1.0)
    } else {
        let q = (-2.0 * (1.0 - p).ln()).sqrt();
        -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / ((((dd[0] * q + dd[1]) * q + dd[2]) * q + dd[3]) * q + 1.0)
    }
}

fn weighted<'a>(e: &mut Engine, table: &'a [(String, f64)]) -> usize {
    let total: f64 = table.iter().map(|(_, w)| w).sum();
    let mut r = e.rng.next_f64() * total;
    for (i, (_, w)) in table.iter().enumerate() {
        if r < *w {
            return i;
        }
        r -= w;
    }
    table.len() - 1
}

impl Engine {
    /// สายเลือดตอนเกิด — ลูกได้ค่าเฉลี่ยของพ่อแม่ ผันผวนเล็กน้อย และเลือดวิญญาณเจือจางลงทุกรุ่น
    /// (ส่วนที่เจือจางกลายเป็นอสูร) · คนที่ไม่มีพ่อแม่สุ่มตามแดนที่เกิด
    fn roll_blood(&mut self, world: u16, parents: [Option<Pid>; 2]) -> [f32; 5] {
        let ps: Vec<[f32; 5]> = parents.iter().flatten().map(|&p| self.people[p as usize].blood).collect();
        let mut b = [0f32; 5];
        if !ps.is_empty() {
            for i in 0..5 {
                b[i] = ps.iter().map(|x| x[i]).sum::<f32>() / ps.len() as f32;
            }
            let dil = b[SPIRIT] * data::k("BLOOD_DILUTE") as f32;
            b[SPIRIT] -= dil;
            b[DEMON] += dil;
            for i in 0..4 {
                b[i] = (b[i] + (self.rng.next_f64() as f32 - 0.5) * 0.12).max(0.0);
            }
        } else {
            let u = |e: &mut Engine, lo: f64, hi: f64| (lo + (hi - lo) * e.rng.next_f64()) as f32;
            if self.worlds[world as usize].kind == WorldKind::Mara {
                b = [u(self, 0.0, 0.2), 0.0, u(self, 0.0, 0.2), u(self, 0.7, 1.0), 0.0];
            } else {
                let r = self.rng.next_f64();
                b = if r < 0.70 {
                    [u(self, 0.8, 1.0), u(self, 0.0, 0.1), u(self, 0.0, 0.1), u(self, 0.0, 0.05), 0.0]
                } else if r < 0.80 {
                    [u(self, 0.4, 0.7), u(self, 0.3, 0.6), 0.0, 0.0, 0.0]
                } else if r < 0.88 {
                    [u(self, 0.4, 0.7), 0.0, u(self, 0.3, 0.6), 0.0, 0.0]
                } else if r < 0.93 {
                    [0.0, u(self, 0.9, 1.0), u(self, 0.0, 0.1), 0.0, 0.0]
                } else if r < 0.98 {
                    [0.0, u(self, 0.0, 0.15), u(self, 0.85, 1.0), 0.0, 0.0]
                } else {
                    [u(self, 0.4, 0.6), 0.0, 0.0, u(self, 0.4, 0.6), 0.0]
                };
            }
        }
        let s: f32 = b.iter().sum::<f32>().max(1e-6);
        for x in b.iter_mut() {
            *x /= s;
        }
        b
    }

    /// อายุขัยพื้นแบบปกติตัดปลาย [min, max] โดยมีเงื่อนไขว่ารอดมาถึงอายุตอนสร้าง
    fn roll_lifespan(&mut self, alive_at: f64) -> f64 {
        let (mu, sd, lo, hi) = (self.cfg.lifespan_mu, self.cfg.lifespan_sigma, self.cfg.lifespan_min, self.cfg.lifespan_max);
        let floor = lo.max(alive_at.floor() + 1.0);
        let u = self.rng.next_f64();
        if floor >= hi {
            return floor + 10.0 * u;
        }
        let (a, b) = (norm_cdf((floor - mu) / sd), norm_cdf((hi - mu) / sd));
        (mu + sd * norm_inv(a + u * (b - a))).clamp(floor, hi)
    }

    /// ตั้งชื่อ — พยายามไม่ให้ซ้ำกับใครที่เคยมี (สุ่มใหม่ได้หลายครั้ง และชื่อจีนใช้ชื่อสองพยางค์ได้)
    /// ถ้ายังชนก็ยอมซ้ำ เหมือนโลกจริงที่มีคนชื่อเดียวกันได้ — ไม่ต่อท้ายตัวเลขให้อ่านไม่ออก
    fn roll_name(&mut self, culture: &str, family: Option<&str>) -> String {
        let d = data::world();
        let (first, second) = d.names.get(culture).or_else(|| d.names.get("han")).unwrap();
        let mut name = String::new();
        for _ in 0..8 {
            let a = first[self.rng.below(first.len() as u64) as usize].clone();
            let b = second[self.rng.below(second.len() as u64) as usize].clone();
            name = match culture {
                // จีน: แซ่ติดชื่อ ตามสายพ่อ · ชื่อตัวหนึ่งหรือสองพยางค์
                "han" => {
                    let given = if self.chance(0.6) {
                        let b2 = &second[self.rng.below(second.len() as u64) as usize];
                        if *b2 != b { format!("{}{}", b, b2) } else { b.clone() }
                    } else {
                        b.clone()
                    };
                    format!("{}{}", family.unwrap_or(&a), given)
                }
                // สยาม โอเอซิส ชมพูทวีป: ชื่อ นามสกุล
                "siam" | "oasis" | "bharata" => format!("{} {}", a, family.unwrap_or(&b)),
                // อาทิตย์อุทัย ทุ่งหญ้า: นามสกุลก่อน
                _ => format!("{} {}", family.unwrap_or(&a), b),
            };
            if !self.used_names.contains(&name) {
                break;
            }
        }
        self.used_names.insert(name.clone());
        name
    }

    /// สกุลของคน (ใช้ตั้งชื่อลูก)
    fn family_name(&self, id: Pid) -> Option<String> {
        let p = &self.people[id as usize];
        let culture = &self.worlds[p.world as usize].culture;
        let d = data::world();
        let (first, second) = d.names.get(culture.as_str())?;
        match culture.as_str() {
            "han" => first.iter().filter(|s| p.name.starts_with(s.as_str())).max_by_key(|s| s.len()).cloned(),
            "siam" | "oasis" | "bharata" => second.iter().find(|s| p.name.contains(&format!(" {}", s))).cloned(),
            _ => first.iter().find(|s| p.name.starts_with(&format!("{} ", s))).cloned(),
        }
    }

    /// สร้างคนใหม่ — อายุ `age` ปี ณ วันนี้ ที่สถานที่ `place` (None = สุ่มในแดน)
    pub fn spawn(&mut self, world: u16, place: Option<u32>, age: f64, parents: [Option<Pid>; 2]) -> Pid {
        let d = data::world();
        let id = self.people.len() as Pid;
        let w = &self.worlds[world as usize];
        let culture = w.culture.clone();
        let place = place.unwrap_or_else(|| {
            let pl = self.worlds[world as usize].places.clone();
            pl[self.rng.below(pl.len() as u64) as usize]
        });
        let family = parents[0].and_then(|f| self.family_name(f));
        let name = self.roll_name(&culture, family.as_deref());
        let tribe = match d.tribes.get(&culture) {
            Some(Tribe::Fixed(s)) => s.clone(),
            Some(Tribe::Weighted(t)) => t[weighted(self, t)].0.clone(),
            None => "ชาวตงหยวน".to_string(),
        };
        let origin = weighted(self, &d.origins) as u8;
        let profession = match parents[0].or(parents[1]) {
            // ลูกมักสืบอาชีพพ่อแม่
            Some(par) if self.chance(0.6) => self.people[par as usize].profession,
            _ => weighted(self, &d.professions) as u8,
        };
        let daos = d.dao_names();
        let dao = self.rng.below(daos.len() as u64) as u8;
        let female = self.chance(0.5);
        let mut traits = [0f32; 5];
        for t in traits.iter_mut() {
            *t = (0.1 + 0.8 * self.rng.next_f64()) as f32;
        }
        // รากปราณ: ส่วนหนึ่งสืบจากพ่อแม่ ส่วนหนึ่งเป็นโชค
        let inherited: Vec<f32> = parents.iter().flatten().map(|&p| self.people[p as usize].root).collect();
        let luck = (self.cfg.root_mu + self.cfg.root_sigma * self.rng.gauss()) as f32;
        let root = if inherited.is_empty() {
            luck
        } else {
            0.5 * luck + 0.5 * inherited.iter().sum::<f32>() / inherited.len() as f32
        }
        .clamp(0.0, 1.0);
        let lifespan = self.roll_lifespan(age);
        let blood = self.roll_blood(world, parents);
        let mut affinity = [0f32; 5];
        for i in 0..5 {
            if blood[i] > 0.0 {
                affinity[i] = (data::k("BLOODLINE_AFFINITY_MIN") + self.rng.next_f64() * (data::k("BLOODLINE_AFFINITY_MAX") - data::k("BLOODLINE_AFFINITY_MIN"))) as f32;
            }
        }
        let inner_none = self.chance(data::k("INNER_NONE_P"));
        let inner_art = !inner_none && self.chance(data::k("INNER_ART_P"));
        let fate = self.range(data::k("FATE_MIN") as i64, data::k("FATE_MAX") as i64) as i8;
        let tier = self.worlds[world as usize].tier;
        // ธาตุประจำตัว: สืบจากพ่อแม่เป็นหลัก ที่เหลือคือสิ่งที่ฟ้าให้มา
        let par_el: Vec<u8> = parents.iter().flatten().map(|&p| self.people[p as usize].element).collect();
        let element = if !par_el.is_empty() && self.chance(0.6) { par_el[self.rng.below(par_el.len() as u64) as usize] } else { self.rng.below(5) as u8 };
        let p = Person {
            id,
            name,
            female,
            born: self.day - (age * 365.0) as i64,
            lifespan,
            world,
            place,
            alive: true,
            death_day: 0,
            death_cause: String::new(),
            killer: None,
            tribe,
            origin,
            profession,
            dao,
            fear: traits[0],
            greed: traits[1],
            compassion: traits[2],
            ambition: traits[3],
            loyalty: traits[4],
            root,
            cultivator: false,
            realm: 0,
            peak_realm: 0,
            insight: 0.0,
            decay: 0.0,
            drawn: 0.0,
            breaks: 0,
            fails: 0,
            injury: 0.0,
            hunger_days: 0.0,
            pack: 0.0,
            gold: 0.0,
            mats: [0.0; 3],
            spouse: None,
            parents,
            children: Vec::new(),
            pregnant: None,
            postpartum_until: 0,
            bonds: BTreeMap::new(),
            rivals: BTreeMap::new(),
            sect: None,
            master: None,
            kills: 0,
            process: None,
            sick_until: 0,
            immune_until: 0,
            items: Vec::new(),
            alchemy: 0.0,
            forge: 0.0,
            alch_rank: -1,
            forge_rank: -1,
            fragments: Default::default(),
            leads: Vec::new(),
            crimes: 0,
            blood,
            refine: 0.0,
            inner: 0.0,
            inner_none,
            inner_art,
            debts: Vec::new(),
            fate,
            chaos_rank: -1,
            is_lord: false,
            lord_returns: 0,
            thrall: false,
            fallen: false,
            sentient: true,
            unique_title: String::new(),
            affinity,
            birth_world: world,
            peak_tier: tier,
            near_death: 0,
            skills: Vec::new(),
            mastery: Vec::new(),
            element,
            last_day: self.day,
            next_turn: 0,
            fieldwork: false,
        };
        self.people.push(p);
        self.alive.insert(id);
        self.at[place as usize].insert(id);
        // ผู้ที่ตั้งต้นมาจากสำนัก/ตระกูลผู้ฝึกตน เริ่มบนวิถีแล้ว
        let origin_name = &d.origins[origin as usize].0;
        if age >= self.cfg.adult_age && (origin_name == "ศิษย์สำนัก" || origin_name == "ทายาทตระกูล") {
            let p = &mut self.people[id as usize];
            p.cultivator = true;
            p.root = p.root.max(0.4);
            p.realm = 1 + (self.rng.below(2) as u8);
            p.peak_realm = p.realm;
        }
        for par in parents.iter().flatten() {
            self.people[*par as usize].children.push(id);
        }
        // อสูรระดับต่ำยังไม่มีจิตนึกคิด · อสูรบางตัวเกิดมาเป็นตัวเฉพาะ
        if self.people[id as usize].blood[DEMON] >= data::k("BLOOD_RACE_AT") as f32 {
            if age < 60.0 {
                self.people[id as usize].sentient = age >= self.cfg.adult_age && self.chance(0.5);
            }
            if self.chance(data::k("UNIQUE_BEAST_CHANCE")) {
                let titles = data::strs(data::table("config", "UNIQUE_BEAST_TITLES"));
                let t = titles[self.rng.below(titles.len() as u64) as usize].clone();
                let p = &mut self.people[id as usize];
                p.unique_title = t;
                p.sentient = true;
                p.cultivator = true;
                p.realm = (p.realm + 2).min(self.cfg.realm_cap_of_tier(tier));
                p.peak_realm = p.realm;
            }
        }
        let gap = self.range(1, 120);
        self.schedule(id, gap);
        id
    }

    // ------------------------------------------------------------------ ครรภ์
    pub fn try_conceive(&mut self, mother: Pid, father: Pid, days: f64) {
        let (age, ok) = {
            let m = &self.people[mother as usize];
            (m.age(self.day), m.pregnant.is_none() && self.day >= m.postpartum_until)
        };
        if !ok || age > self.cfg.fertile_max_age || age < self.cfg.marry_min_age {
            return;
        }
        // ภาวะเจริญพันธุ์ลดลงหลังอายุ 30 — ความหิวและบาดแผลก็ลดโอกาส
        let fert = if age < 30.0 { 1.0 } else { (1.0 - (age - 30.0) / 18.0).max(0.05) };
        let m = &self.people[mother as usize];
        let health = (1.0 - m.injury as f64) * if m.hunger_days > 3.0 { 0.3 } else { 1.0 };
        let p = physics::hazard_p(self.cfg.conceive_per_year * fert * health, days);
        if self.chance(p) {
            let due = self.day + self.cfg.gestation_days as i64;
            self.people[mother as usize].pregnant = Some((due, father));
            self.ledger.count("ตั้งครรภ์");
        }
    }

    pub fn give_birth(&mut self, mother: Pid) {
        let Some((_, father)) = self.people[mother as usize].pregnant.take() else { return };
        self.people[mother as usize].postpartum_until = self.day + self.cfg.postpartum_days as i64;
        let (world, place) = (self.people[mother as usize].world, self.people[mother as usize].place);
        let parents = if self.people[father as usize].alive || true { [Some(father), Some(mother)] } else { [None, Some(mother)] };
        let child = self.spawn(world, Some(place), 0.0, parents);
        // ทารกเริ่มด้วยครัวข้าวของแม่
        let share = (self.people[mother as usize].pack * 0.2).min(10.0);
        self.people[mother as usize].pack -= share;
        self.people[child as usize].pack += share;
        let (cn, mn) = (self.people[child as usize].name.clone(), self.people[mother as usize].name.clone());
        let fname = self.people[father as usize].name.clone();
        // การคลอดเสี่ยงต่อชีวิตแม่ — ยิ่งหิวหรือบาดเจ็บยิ่งเสี่ยง
        let m = &self.people[mother as usize];
        let risk = 0.01 + 0.05 * m.injury as f64 + if m.hunger_days > 5.0 { 0.05 } else { 0.0 };
        self.emit("กำเนิดทายาท", Some(mother), Some(child), "คลอด", format!("{}ให้กำเนิด{} บุตรของ{}", mn, cn, fname));
        if self.people[mother as usize].realm == 0 && self.chance(risk) {
            self.kill(mother, None, "เสียชีวิตขณะคลอดบุตร", true);
        }
    }

    // ------------------------------------------------------------------ ตาย
    pub fn kill(&mut self, id: Pid, killer: Option<Pid>, cause: &str, natural: bool) {
        if !self.people[id as usize].alive {
            return;
        }
        if self.people[id as usize].is_lord {
            self.lord_dissolves(id, killer, cause);
            return;
        }
        // ชะตาช่วยให้รอดจากการถูกฆ่าได้ครั้งหนึ่ง (ไม่ใช่จากวัย โรค หรือความหิว)
        if !natural && killer.is_some() && self.people[id as usize].fate > 0 && self.chance(0.5) {
            let p = &mut self.people[id as usize];
            p.fate -= 1;
            p.near_death += 1;
            p.injury = 0.9;
            if let Some(k) = killer {
                *p.rivals.entry(k).or_insert(0) += 3;
            }
            let n = p.name.clone();
            self.emit("รอดตายด้วยชะตา", Some(id), killer, "รอดตาย", format!("{}รอดจากความตายอย่างหวุดหวิดด้วยชะตาที่ยังไม่ขาด ({})", n, cause));
            return;
        }
        self.feed_lord(id, natural);
        if let Some(k) = killer {
            if self.people[k as usize].alive {
                self.add_debt(k, "ฆ่า", id);
            }
        }
        let day = self.day;
        {
            let p = &mut self.people[id as usize];
            p.alive = false;
            p.death_day = day;
            p.death_cause = cause.to_string();
            p.killer = killer;
            p.process = None;
        }
        self.alive.remove(&id);
        let place = self.people[id as usize].place;
        self.at[place as usize].remove(&id);
        self.ledger.death(cause_class(cause));
        // คืนปราณที่ดูดไปให้ฟ้า — ตายตามธรรมชาติคืนมาก ถูกฆ่ากลางคันคืนน้อย
        let w = self.people[id as usize].world as usize;
        let rate = if natural { self.cfg.natural_return } else { self.cfg.killed_return };
        let back = self.people[id as usize].drawn * rate;
        self.worlds[w].heaven = (self.worlds[w].heaven + back).min(self.worlds[w].cap);
        self.people[id as usize].drawn = 0.0;
        // คู่ครองกลายเป็นหม้าย
        if let Some(s) = self.people[id as usize].spouse {
            self.people[s as usize].spouse = None;
        }
        // ครรภ์ที่ยังไม่คลอดสูญไปด้วย
        self.people[id as usize].pregnant = None;
        self.leave_sect(id);
        self.settle_estate(id);
        if let Some(k) = killer {
            self.people[k as usize].kills += 1;
            self.worlds[w].blood_marks.push(day);
        }
        // ข่าวการตายเดินทางไปหาคนที่ผูกพัน
        self.send_death_news(id, killer);
        let name = self.people[id as usize].name.clone();
        let age = self.people[id as usize].age(day);
        let text = match killer {
            Some(k) => format!("{}สิ้นชีพในวัย {:.0} ปี — {} ({})", name, age, cause, self.people[k as usize].name),
            None => format!("{}สิ้นชีพในวัย {:.0} ปี — {}", name, age, cause),
        };
        self.emit("ตาย", Some(id), killer, cause_class(cause), text);
    }

    /// มรดก: คู่ครอง → ลูกที่ยังมีชีวิต → สำนัก → คลังชุมชน · เสบียงตกเป็นของยุ้งฉางที่นั้น
    fn settle_estate(&mut self, id: Pid) {
        let (gold, pack, mats, place, spouse, children, sect) = {
            let p = &mut self.people[id as usize];
            let out = (p.gold, p.pack as f64, p.mats, p.place, p.spouse, p.children.clone(), p.sect);
            p.gold = 0.0;
            p.pack = 0.0;
            p.mats = [0.0; 3];
            out
        };
        let mut heirs: Vec<Pid> = spouse.into_iter().filter(|&s| self.people[s as usize].alive).collect();
        heirs.extend(children.into_iter().filter(|&c| self.people[c as usize].alive));
        if !heirs.is_empty() {
            let share = gold / heirs.len() as f64;
            for h in &heirs {
                self.people[*h as usize].gold += share;
            }
            self.ledger.gold("inherited", gold);
            let mshare: Vec<f32> = mats.iter().map(|m| m / heirs.len() as f32).collect();
            for h in &heirs {
                for k in 0..3 {
                    self.people[*h as usize].mats[k] += mshare[k];
                }
            }
        } else if let Some(s) = sect.filter(|&s| self.sects[s as usize].alive) {
            self.sects[s as usize].treasury += gold;
            self.ledger.gold("to_sect", gold);
        } else {
            self.places[place as usize].treasury += gold;
            self.ledger.gold("to_community", gold);
        }
        self.places[place as usize].granary += pack;
    }

    fn send_death_news(&mut self, id: Pid, killer: Option<Pid>) {
        let p = &self.people[id as usize];
        let mut kin: Vec<Pid> = p.children.clone();
        kin.extend(p.parents.iter().flatten());
        kin.extend(p.bonds.iter().filter(|(_, &v)| v >= 3).map(|(&k, _)| k));
        if let Some(m) = p.master {
            kin.push(m);
        }
        kin.sort_unstable();
        kin.dedup();
        let from = p.place;
        for k in kin {
            let q = &self.people[k as usize];
            if !q.alive {
                continue;
            }
            let hops = super::geo::hops(from, q.place, 12).unwrap_or(12) as f64;
            let arrive = self.day + (hops * self.cfg.news_per_hop_days).ceil() as i64;
            self.news.push(News { arrive, to: k, about: id, killer });
        }
    }

    /// ข่าวถึงผู้รับ — ญาติของผู้ถูกฆ่าผูกแค้นกับผู้ฆ่า
    pub fn deliver_news(&mut self) {
        let day = self.day;
        let mut due = Vec::new();
        self.news.retain(|n| {
            if n.arrive <= day {
                due.push(n.clone());
                false
            } else {
                true
            }
        });
        for n in due {
            if !self.people[n.to as usize].alive {
                continue;
            }
            if let Some(k) = n.killer {
                if k != n.to && self.people[k as usize].alive {
                    let closeness = if self.people[n.to as usize].children.contains(&n.about)
                        || self.people[n.about as usize].children.contains(&n.to)
                    {
                        self.cfg.grudge_on_kill + 2
                    } else {
                        self.cfg.grudge_on_kill
                    } as i16;
                    *self.people[n.to as usize].rivals.entry(k).or_insert(0) += closeness;
                    let (a, b, c) = (
                        self.people[n.to as usize].name.clone(),
                        self.people[n.about as usize].name.clone(),
                        self.people[k as usize].name.clone(),
                    );
                    self.emit("รู้ข่าวร้าย", Some(n.to), Some(k), "ผูกแค้น", format!("{}ได้ข่าวว่า{}ถูก{}สังหาร จึงผูกใจเจ็บ", a, b, c));
                }
            }
        }
    }
}

/// ย่อสาเหตุการตายเป็นหมวดสำหรับสถิติ
pub fn cause_class(cause: &str) -> &'static str {
    if cause.contains("โรคระบาด") {
        "โรคระบาด"
    } else if cause.contains("อดอยาก") || cause.contains("หิว") {
        "อดอยาก"
    } else if cause.contains("ชรา") || cause.contains("อายุขัย") {
        "ชรา"
    } else if cause.contains("คลอด") {
        "คลอดบุตร"
    } else if cause.contains("ป่วย") || cause.contains("ไข้") || cause.contains("วัยเด็ก") {
        "เจ็บป่วย"
    } else if cause.contains("บาดแผล") {
        "บาดแผล"
    } else if cause.contains("ทัณฑ์") || cause.contains("ข้ามขั้น") || cause.contains("ข้ามฟ้า") {
        "บำเพ็ญ"
    } else {
        "ถูกฆ่า"
    }
}
