//! Engine — โลกหนึ่งใบ: สร้างโลก คิวเทิร์น นาฬิกาโลก บันทึกเหตุการณ์
//!
//! เวลาเดินเป็นวัน มีสองจังหวะ
//!   · เทิร์นของคน (คิว min-heap ตามวัน) — การตัดสินใจและการกระทำ (intent.rs, actions.rs)
//!   · นาฬิกาโลกทุก world_tick_days วัน — สิ่งที่เกิดกับทุกคนพร้อมกัน: กิน ผลิต ค่าแรง แก่ ฟื้นตัว
//!     ตั้งครรภ์ คลอด ข่าว ปราณฟ้า (world.rs)

use super::config::Config;
use super::data;
use super::model::*;
use crate::noise::Planet;
use crate::rng::{fold_seed, Xoshiro};
use serde::{Deserialize, Serialize};
use std::cmp::Reverse;
use std::collections::{BTreeSet, BinaryHeap, VecDeque};

pub const PLANET_SPAN: f64 = 1000.0;
pub const PLANET_SCALE: f64 = 12.0;

#[derive(Clone, Serialize, Deserialize)]
pub struct Engine {
    pub cfg: Config,
    pub seed: u64,
    pub rng: Xoshiro,
    pub day: i64,
    pub people: Vec<Person>,
    pub alive: BTreeSet<Pid>,
    pub worlds: Vec<World>,
    pub places: Vec<PlaceState>,
    pub place_world: Vec<Option<u16>>,
    #[serde(default)]
    pub polities: Vec<super::polity::Polity>,
    /// เซฟเก่า (ก่อน P1) — ย้ายเข้า polities ใน after_load
    #[serde(default, rename = "sects", skip_serializing)]
    pub legacy_sects: Vec<super::polity::LegacySect>,
    pub queue: BinaryHeap<Reverse<(i64, Pid)>>,
    pub next_tick: i64,
    pub log: VecDeque<Event>,
    pub seq: u64,
    pub news: Vec<News>,
    pub ledger: Ledger,
    pub used_names: BTreeSet<String>,
    /// จำนวนเหตุการณ์ทุกชนิดต่อแดน (รวมที่ไม่ได้บันทึกลง log)
    #[serde(default)]
    pub world_counts: std::collections::BTreeMap<u16, std::collections::BTreeMap<String, u64>>,
    /// งบเหตุการณ์ "น่าสนใจ" ของปีปัจจุบันต่อแดน (ปี, ใช้ไปแล้ว)
    #[serde(default)]
    pub notable_budget: std::collections::BTreeMap<u16, (i64, u32)>,
    pub steps: u64,
    // ---- แดนมารและเผ่าโกลาหล
    pub mara_world: Option<u16>,
    pub chaos_world: Option<u16>,
    pub mara_seal: f64,
    pub mara_seal_broken: bool,
    pub mara_seal_warned: bool,
    pub lord: Option<Pid>,
    pub lord_pool: f64,
    pub lord_seal: f64,
    pub lord_seals_made: u32,
    pub lord_seal_last: i64,
    /// ผู้ถึงยอดบันได (ขั้นสูงสุด) ต่อสายเลือด -> (cid, ความแรงพร)
    pub apex: std::collections::BTreeMap<u8, (Pid, f32)>,
    // ---- ของวิเศษ
    pub items: std::collections::BTreeMap<u32, super::items::Item>,
    pub next_item: u32,
    pub caches: Vec<super::items::Cache>,
    pub next_cache: u32,
    pub legends: Vec<u32>,
    pub fragments: Vec<super::items::Fragment>,
    pub ruin_gold: Vec<f64>,
    #[serde(default, rename = "cities", skip_serializing)]
    pub legacy_cities: Vec<super::polity::LegacyCity>,
    /// สถานที่ → เมืองที่ตั้งอยู่ที่นั่น (สร้างใหม่ได้ — ไม่เซฟ)
    #[serde(skip)]
    pub city_index: Vec<Option<u32>>,
    /// สำเนาที่ใช้มองอนาคต — ไม่มอบระบบ ไม่จำลองซ้อน
    #[serde(skip)]
    pub fork: bool,
    /// ค่าปราณธรรมชาติของแต่ละสถานที่ 0..1 (คิดจากผิวดาวครั้งเดียว)
    #[serde(skip)]
    pub qi: Vec<f64>,
    /// ดัชนีคนที่มีชีวิตต่อสถานที่ (สร้างใหม่ได้จาก people — ไม่เซฟ)
    #[serde(skip)]
    pub at: Vec<std::collections::BTreeSet<Pid>>,
}

impl Engine {
    pub fn new(seed: u64, cfg: Config) -> Engine {
        let d = data::world();
        let mut e = Engine {
            cfg,
            seed,
            rng: Xoshiro::from_seed(seed),
            day: 0,
            people: Vec::new(),
            alive: BTreeSet::new(),
            worlds: Vec::new(),
            places: vec![PlaceState::default(); d.places.len()],
            place_world: vec![None; d.places.len()],
            polities: Vec::new(),
            legacy_sects: Vec::new(),
            queue: BinaryHeap::new(),
            next_tick: 0,
            log: VecDeque::new(),
            seq: 0,
            news: Vec::new(),
            ledger: Ledger::default(),
            used_names: BTreeSet::new(),
            world_counts: Default::default(),
            notable_budget: Default::default(),
            steps: 0,
            mara_world: None,
            chaos_world: None,
            mara_seal: data::k("MARA_SEAL_INITIAL"),
            mara_seal_broken: false,
            mara_seal_warned: false,
            lord: None,
            lord_pool: 0.0,
            lord_seal: 0.0,
            lord_seals_made: 0,
            lord_seal_last: -100_000,
            apex: Default::default(),
            items: Default::default(),
            next_item: 0,
            caches: Vec::new(),
            next_cache: 0,
            legends: Vec::new(),
            fragments: Vec::new(),
            ruin_gold: Vec::new(),
            legacy_cities: Vec::new(),
            city_index: Vec::new(),
            fork: false,
            qi: Vec::new(),
            at: vec![Default::default(); d.places.len()],
        };
        e.build_worlds();
        e.compute_qi();
        e.seed_nature();
        e.populate();
        e.found_cities();
        e
    }

    /// หลังโหลดเซฟ — คืนค่าที่ไม่ได้เซฟไว้ (คิดใหม่ได้จาก seed)
    pub fn after_load(&mut self) {
        self.migrate_legacy_polities();
        self.index_cities();
        self.compute_qi();
        self.at = vec![Default::default(); self.places.len()];
        for &i in &self.alive {
            // เจ้าโกลาหลที่สลายอยู่ไม่มีตัวตนที่สถานที่ใด (เหมือนตอนเล่นต่อเนื่อง)
            if self.people[i as usize].dissolved() {
                continue;
            }
            self.at[self.people[i as usize].place as usize].insert(i);
        }
    }

    /// ย้ายคนไปสถานที่ใหม่ (ทางเดียวที่แก้ place — ดัชนี `at` ต้องตรงเสมอ)
    pub fn move_to(&mut self, id: Pid, place: u32) {
        let old = self.people[id as usize].place;
        self.at[old as usize].remove(&id);
        self.people[id as usize].place = place;
        if self.people[id as usize].alive {
            self.at[place as usize].insert(id);
        }
    }

    // ------------------------------------------------------------------ สร้างโลก
    fn build_worlds(&mut self) {
        let d = data::world();
        let add = |e: &mut Engine, name: &str, tier: u8, kind: WorldKind, key: &str, culture: &str| -> u16 {
            let id = e.worlds.len() as u16;
            let cap = e.cfg.heaven_cap * e.cfg.heaven_cap_per_tier.powi(tier as i32);
            e.worlds.push(World {
                id,
                name: name.to_string(),
                tier,
                kind,
                key: key.to_string(),
                culture: culture.to_string(),
                up: None,
                lateral: Vec::new(),
                places: Vec::new(),
                heaven: cap * 0.85,
                cap,
                era: 1,
                blood_marks: Vec::new(),
                harvest_mult: 1.0,
                harvest_until: 0,
                rift: 0.0,
                defense: 100.0,
                defense_max: 100.0,
                closed: false,
                resentment: 0.0,
                last_coalition: -100_000,
                ruined: Vec::new(),
            });
            id
        };
        let tiers = d.tier_names.len().min(3);
        for t in 0..tiers {
            add(self, &d.tier_names[t].clone(), t as u8, WorldKind::Main, &format!("t{}", t), "han");
        }
        for t in 0..tiers - 1 {
            self.worlds[t].up = Some(t as u16 + 1);
        }
        // แดนมารติดโลกมนุษย์ · ห้วงโกลาหลติดแดนชั้นสูงสุด (ตามต้นฉบับ)
        let mara = add(self, &data::table("config", "MARA_WORLD_NAME").as_str().unwrap_or("แดนมาร").to_string(), 0, WorldKind::Mara, "mara", "han");
        self.worlds[0].lateral.push(mara);
        self.worlds[mara as usize].lateral.push(0);
        let top = (data::k("CHAOS_TIER") as usize).min(tiers - 1) as u8;
        let chaos = add(self, &data::table("config", "CHAOS_WORLD_NAME").as_str().unwrap_or("ห้วงโกลาหล").to_string(), top, WorldKind::Chaos, "chaos", "han");
        self.worlds[top as usize].lateral.push(chaos);
        self.worlds[chaos as usize].lateral.push(top as u16);
        self.chaos_world = Some(chaos);
        self.mara_world = Some(mara);
        for (key, name) in d.sister_realms.clone() {
            let culture = if d.names.contains_key(&key) { key.clone() } else { "han".to_string() };
            let id = add(self, &name, 0, WorldKind::Sister, &key, &culture);
            self.worlds[id as usize].up = Some(1);
            self.worlds[id as usize].lateral.push(0);
            self.worlds[0].lateral.push(id);
        }
        let n_branch = self.cfg.branch_realms.min(d.branch_realms.len());
        for b in d.branch_realms.iter().take(n_branch).cloned().collect::<Vec<_>>() {
            let id = add(self, &b.name, 1, WorldKind::Branch, &b.key, "han");
            self.worlds[id as usize].up = if tiers > 2 { Some(2) } else { None };
            self.worlds[id as usize].lateral.push(1);
            self.worlds[1].lateral.push(id);
        }
        // สถานที่ของแต่ละแดน (แดนลับไม่ใช่ที่อยู่อาศัย)
        for (i, p) in d.places.iter().enumerate() {
            if let Some(w) = self.worlds.iter().position(|w| w.key == p.world) {
                self.place_world[i] = Some(w as u16);
                if p.kind != "แดนลับ" && !p.sealed {
                    self.worlds[w].places.push(i as u32);
                }
            }
        }
    }

    fn compute_qi(&mut self) {
        let d = data::world();
        let planet = Planet::create(fold_seed(self.seed as i128 ^ 0x91F1_0000) as i128, 1.0, 0.12, 1.0, 5, 2);
        self.qi = d
            .places
            .iter()
            .map(|p| {
                let (x, y, z) = crate::noise::sphere_dir(p.x, p.y, PLANET_SPAN);
                let h = planet.height_at(x, y, z, PLANET_SCALE);
                // ที่ระดับสูง (เกรด) ปราณหนากว่า — เกรดคือสิ่งที่ผู้ออกแบบโลกตั้งใจ ส่วนผิวดาวคือธรรมชาติ
                (0.5 + 0.5 * h + 0.08 * p.grade as f64).clamp(0.0, 1.0)
            })
            .collect();
    }

    fn seed_nature(&mut self) {
        for i in 0..self.places.len() {
            if self.place_world[i].is_none() {
                continue;
            }
            for m in Material::ALL {
                self.places[i].stock[m as usize] = self.eco_k(i, m);
            }
        }
    }

    fn populate(&mut self) {
        for w in 0..self.worlds.len() {
            let n = match self.worlds[w].kind {
                WorldKind::Main if self.worlds[w].tier == 0 => self.cfg.cast_mortal,
                WorldKind::Main => self.cfg.cast_main,
                WorldKind::Sister => self.cfg.cast_sister,
                WorldKind::Branch => self.cfg.cast_branch,
                WorldKind::Mara => self.cfg.cast_main / 3,
                WorldKind::Chaos => continue,
            };
            for _ in 0..n {
                let age = 8.0 + self.rng.next_f64() * 37.0;
                let id = self.spawn(w as u16, None, age, [None, None]);
                let tier = self.worlds[w].tier;
                if tier > 0 {
                    // คนที่เกิดบนแดนสูงอยู่บนบันไดของแดนนั้นแล้ว
                    let p = &mut self.people[id as usize];
                    p.cultivator = true;
                    p.realm = tier * self.cfg.realm_band + (self.rng.below(4) as u8);
                    p.peak_realm = p.realm;
                    p.peak_tier = tier;
                    p.root = p.root.max(0.5);
                }
            }
        }
        self.spawn_chaos_race();
        self.seed_treasures();
        self.grant_foresight();
        // ทุนตั้งต้น — การออกเงินและอาหารที่ประกาศไว้ในบัญชี
        let ids: Vec<Pid> = self.alive.iter().copied().collect();
        for id in ids {
            let (gold, food) = (self.cfg.start_gold, self.cfg.start_food_days * self.cfg.ration_adult);
            let p = &mut self.people[id as usize];
            p.gold += gold;
            p.pack += food as f32;
            self.ledger.gold("issued", gold);
            self.ledger.food("endowed", food);
        }
        // ยุ้งฉางตั้งต้นของทุกที่ที่มีคน — สองเดือนของคนที่อยู่ที่นั่น
        let mut need = vec![0.0f64; self.places.len()];
        for &id in &self.alive {
            let p = &self.people[id as usize];
            need[p.place as usize] += self.cfg.ration_adult * 60.0;
        }
        for (i, n) in need.into_iter().enumerate() {
            if n > 0.0 {
                self.places[i].granary += n;
                self.ledger.food("endowed", n);
            }
        }
    }

    // ------------------------------------------------------------------ คิว
    /// นัดเทิร์นถัดไป (แทนนัดเดิม — คนหนึ่งคนมีนัดที่มีผลได้นัดเดียว)
    pub fn schedule(&mut self, id: Pid, gap: i64) {
        let when = self.day + gap.max(1);
        self.people[id as usize].next_turn = when;
        self.queue.push(Reverse((when, id)));
    }

    /// เดินโลกไป `steps` เทิร์น (เทิร์นของคน หนึ่งเทิร์นต่อหนึ่ง step) — คืนจำนวนที่เดินได้จริง
    pub fn run(&mut self, steps: u64) -> u64 {
        let mut done = 0;
        while done < steps {
            if !self.step() {
                break;
            }
            done += 1;
        }
        done
    }

    /// เดินโลกไปจนถึงวันที่กำหนด
    pub fn run_until(&mut self, day: i64) -> u64 {
        let mut done = 0;
        loop {
            let next_turn = self.queue.peek().map(|Reverse((d, _))| *d).unwrap_or(i64::MAX);
            if next_turn.min(self.next_tick) > day {
                self.day = self.day.max(day);
                break;
            }
            if !self.step() {
                break;
            }
            done += 1;
        }
        done
    }

    /// หนึ่งเทิร์น — นาฬิกาโลกมาก่อนเทิร์นของคนที่ตรงวันกัน
    pub fn step(&mut self) -> bool {
        loop {
            let next_turn = self.queue.peek().map(|Reverse((d, _))| *d);
            match next_turn {
                Some(d) if d < self.next_tick => {
                    let Reverse((day, id)) = self.queue.pop().unwrap();
                    let p = &self.people[id as usize];
                    if !p.alive || p.next_turn != day {
                        continue;
                    }
                    self.day = self.day.max(day);
                    self.turn(id);
                    self.steps += 1;
                    return true;
                }
                _ => {
                    if self.alive.is_empty() {
                        return false;
                    }
                    self.day = self.day.max(self.next_tick);
                    self.world_tick();
                    self.next_tick = self.day + self.cfg.world_tick_days as i64;
                }
            }
        }
    }

    // ------------------------------------------------------------------ บันทึก
    pub fn emit(&mut self, kind: &str, actor: Option<Pid>, target: Option<Pid>, outcome: &str, text: String) {
        let (world, place) = match actor.or(target) {
            Some(id) => (self.people[id as usize].world, self.people[id as usize].place),
            None => (0, 0),
        };
        if !self.admit_event(kind, actor, world) {
            return;
        }
        self.seq += 1;
        self.log.push_back(Event {
            seq: self.seq,
            day: self.day,
            kind: kind.to_string(),
            actor,
            target,
            world,
            place,
            outcome: outcome.to_string(),
            text,
        });
        while self.log.len() > self.cfg.log_keep {
            self.log.pop_front();
        }
    }

    /// เหตุการณ์ที่ไม่มีผู้กระทำ (ภัยพิบัติ โรคระบาด) — ระบุแดนและสถานที่เอง
    pub fn emit_at(&mut self, kind: &str, world: u16, place: u32, outcome: &str, text: String) {
        if !self.admit_event(kind, None, world) {
            return;
        }
        self.seq += 1;
        self.log.push_back(Event { seq: self.seq, day: self.day, kind: kind.to_string(), actor: None, target: None, world, place, outcome: outcome.to_string(), text });
        while self.log.len() > self.cfg.log_keep {
            self.log.pop_front();
        }
    }

    // ------------------------------------------------------------------ ตัวช่วย
    pub fn person(&self, id: Pid) -> &Person {
        &self.people[id as usize]
    }

    pub fn world_of(&self, id: Pid) -> &World {
        &self.worlds[self.people[id as usize].world as usize]
    }

    /// คนที่ยังมีชีวิตอยู่ที่สถานที่เดียวกัน (ไม่นับผู้เดินทาง/ปิดด่าน)
    pub fn present_at(&self, place: u32) -> Vec<Pid> {
        self.at[place as usize].iter().copied().filter(|&i| self.people[i as usize].process.is_none()).collect()
    }

    pub fn living_in(&self, world: u16) -> Vec<Pid> {
        self.alive.iter().copied().filter(|&i| self.people[i as usize].world == world).collect()
    }

    pub fn realm_name(&self, realm: u8) -> String {
        data::world().realm_name(realm)
    }

    pub fn place_name(&self, place: u32) -> &'static str {
        &data::world().places[place as usize].name
    }

    pub fn pick<T: Copy>(&mut self, v: &[T]) -> Option<T> {
        if v.is_empty() {
            None
        } else {
            Some(v[self.rng.below(v.len() as u64) as usize])
        }
    }

    pub fn chance(&mut self, p: f64) -> bool {
        self.rng.next_f64() < p
    }

    pub fn range(&mut self, lo: i64, hi: i64) -> i64 {
        lo + self.rng.below((hi - lo + 1).max(1) as u64) as i64
    }

    pub fn is_adult(&self, id: Pid) -> bool {
        self.people[id as usize].age(self.day) >= self.cfg.adult_age
    }

    /// อายุขัยรวมตอนนี้ (ปี): อายุขัยพื้น + ขั้นย่อยที่ผ่าน + ขั้นใหญ่ที่ผ่าน
    pub fn lifespan_of(&self, id: Pid) -> f64 {
        let p = &self.people[id as usize];
        let tier = p.tier(self.cfg.realm_band) as f64;
        p.lifespan + p.realm as f64 * self.cfg.lifespan_per_minor + tier * self.cfg.lifespan_per_major
    }
}

#[cfg(test)]
pub(crate) mod tests {
    use super::*;

    pub fn fingerprint(e: &Engine) -> (usize, usize, u64, i64) {
        let h = e.log.iter().fold(0u64, |h, ev| {
            ev.text.bytes().fold(h.wrapping_mul(1_000_003) ^ ev.day as u64, |h, b| h.wrapping_mul(31) ^ b as u64)
        });
        (e.alive.len(), e.people.len(), h, e.day)
    }

    /// แฮชของสถานะทั้งหมด — ใช้ตรวจว่าการรื้อโครงสร้างไม่เปลี่ยนพฤติกรรม
    pub fn state_hash(e: &Engine) -> u64 {
        serde_json::to_string(e).unwrap().bytes().fold(0xcbf29ce484222325u64, |h, b| (h ^ b as u64).wrapping_mul(0x100000001b3))
    }

    #[test]
    fn golden_state() {
        let mut e = Engine::new(21, Config::default());
        e.run_until(20 * 365);
        let h = state_hash(&e);
        eprintln!("GOLDEN {} {}", h, e.alive.len());
        assert_eq!(h, GOLDEN, "behaviour changed (alive {})", e.alive.len());
    }
    const GOLDEN: u64 = 6789734594892141689;

    /// พฤติกรรม (ไม่ขึ้นกับรูปแบบการเซฟ): ใช้ยืนยันว่าการย้ายโครงสร้างข้อมูลไม่เปลี่ยนผล
    #[test]
    fn behaviour_fingerprint() {
        let mut e = Engine::new(21, Config::default());
        e.run_until(20 * 365);
        let f = fingerprint(&e);
        eprintln!("BEHAVIOUR {:?}", f);
        assert_eq!(f, BEHAVIOUR);
    }
    const BEHAVIOUR: (usize, usize, u64, i64) = (1540, 2144, 13394171075381343699, 7301);

    #[test]
    fn same_seed_same_world() {
        let mut a = Engine::new(3, Config::default());
        let mut b = Engine::new(3, Config::default());
        a.run_until(8 * 365);
        b.run_until(8 * 365);
        assert_eq!(fingerprint(&a), fingerprint(&b));
        let mut c = Engine::new(4, Config::default());
        c.run_until(8 * 365);
        assert_ne!(fingerprint(&a).2, fingerprint(&c).2);
    }

    #[test]
    fn ledgers_close() {
        let mut e = Engine::new(5, Config::default());
        for y in 1..=15 {
            e.run_until(y * 365);
            let df = (e.total_food() - e.ledger_food()).abs();
            let dg = (e.total_gold() - e.ledger_gold()).abs();
            assert!(df < 1e-3 * e.ledger_food().max(1.0), "food off by {} in year {}", df, y);
            assert!(dg < 1e-6 * e.ledger_gold().max(1.0), "gold off by {} in year {}", dg, y);
        }
    }

    #[test]
    fn save_load_continues_identically() {
        let mut a = Engine::new(9, Config::default());
        a.run_until(5 * 365);
        let blob = serde_json::to_string(&a).unwrap();
        let mut b: Engine = serde_json::from_str(&blob).unwrap();
        b.after_load();
        a.run_until(10 * 365);
        b.run_until(10 * 365);
        assert_eq!(fingerprint(&a), fingerprint(&b));
    }

    #[test]
    fn the_world_lives() {
        let mut e = Engine::new(11, Config::default());
        let start = e.alive.len();
        e.run_until(30 * 365);
        assert!(e.alive.len() > start / 2, "population collapsed: {} -> {}", start, e.alive.len());
        assert!(e.people.len() > start + 200, "almost nobody was born");
        assert!(e.alive.iter().all(|&i| e.people[i as usize].alive));
        // ไม่มีใครค้างอยู่นอกแดนของตัวเอง
        for &i in &e.alive {
            let p = &e.people[i as usize];
            assert_eq!(e.place_world[p.place as usize], Some(p.world), "{} อยู่ผิดแดน", p.name);
        }
    }
}

#[cfg(test)]
mod long_tests {
    use super::*;

    /// บัญชีทองต้องปิดแม้มีการปล้น จับกุม รักษา ตีอาวุธ (เคยรั่วตอนคืนของกลางให้ผู้เสียหายที่ตายไปแล้ว)
    #[test]
    fn gold_closes_over_a_long_violent_run() {
        let mut e = Engine::new(3, Config::default());
        e.run_until(150 * 365);
        let dg = (e.total_gold() - e.ledger_gold()).abs();
        assert!(dg < 1e-6 * e.ledger_gold(), "gold off by {}", dg);
    }
}
