//! ของวิเศษ — สมบัติฟ้าดินที่มีชื่อ ยาและอาวุธที่ช่างหลอม แดนลับที่ผนึกทรัพย์ไว้ ซากแดนลับ
//! เศษวิชาโบราณ งานประมูล และการชิงสมบัติ
//!
//! กติกาเหล็ก: สมบัติฟ้าดินที่มีชื่อไม่มีวันสูญหาย — ทุกสิบปีตรวจว่าทุกชิ้นอยู่กับใครหรือในแดนลับใด
//! ชิ้นที่หลุดออกจากโลกถูกผนึกกลับเข้าแดนลับรอผู้มีวาสนาคนต่อไป

use super::data::{self, k};
use super::model::*;
use super::sim::Engine;
use super::skills::skills;
use crate::physics;
use serde::{Deserialize, Serialize};

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Item {
    pub id: u32,
    pub kind: String,           // ยาวิเศษ อาวุธวิเศษ สมบัติฟ้าดิน คัมภีร์ ยันต์วิเศษ
    pub name: String,
    pub tier: u8,
    pub grade: f32,
    pub condition: f32,
    pub maker: Option<Pid>,
    pub legend: bool,
    pub desc: String,
    pub cooldown: i64,
    pub ready_day: i64,
    pub pill_bonus: f32,
    pub lifespan_bonus: f32,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Cache {
    pub id: u32,
    pub world: u16,
    pub place: u32,
    pub owner: Option<Pid>,
    pub owner_name: String,
    pub sealed_day: i64,
    pub seal: f64,
    pub items: Vec<u32>,
    pub gold: f64,
    pub trap: bool,
    pub opened: bool,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Fragment {
    pub skill: u16,
    pub piece: u8,
    pub place: u32,
    pub found: bool,
}

fn rank_tier(rank: i8) -> i64 {
    (rank.max(0) / 3) as i64
}
fn rank_grade(rank: i8) -> i64 {
    (rank.max(0) % 3) as i64
}
fn can_make(rank: i8, tier: i64, grade: i64) -> bool {
    rank_tier(rank) >= tier && (rank_tier(rank) > tier || rank_grade(rank) >= grade)
}

fn longevity_years(tier: i64, grade: i64) -> f32 {
    ([2, 8, 30][tier.clamp(0, 2) as usize] + grade.max(0) * 2) as f32
}

impl Engine {
    pub fn new_item(&mut self, kind: &str, name: String, tier: u8, grade: f32, maker: Option<Pid>) -> u32 {
        self.next_item += 1;
        let id = self.next_item;
        self.items.insert(id, Item { id, kind: kind.into(), name, tier, grade, condition: 1.0, maker, legend: false, desc: String::new(), cooldown: 0, ready_day: 0, pill_bonus: 0.0, lifespan_bonus: 0.0 });
        id
    }

    /// พลังจากของในมือ (ไม่นับยา) — สมบัติชิ้นเอกปล่อยพลังพิเศษได้เมื่อพลังฟื้นครบ
    pub fn item_power(&self, id: Pid) -> f64 {
        let mut p = 0.0;
        for i in &self.people[id as usize].items {
            let Some(it) = self.items.get(i) else { continue };
            if it.kind == "ยาวิเศษ" {
                continue;
            }
            p += k("TREASURE_POWER") * (it.grade * it.condition) as f64;
            if it.legend && self.day >= it.ready_day {
                let burst = if it.name == "กระจกมิติล่มสลาย" { 3.0 } else { data::table("treasures", "BURST_MULT").as_f64().unwrap_or(0.7) };
                p += burst * (it.grade * it.condition) as f64;
            }
        }
        p
    }

    /// หลังปะทะ: สมบัติชิ้นเอกต้องรอพลังฟื้น · ของสึกหรอ
    pub fn wear_items(&mut self, id: Pid) {
        let day = self.day;
        let ids = self.people[id as usize].items.clone();
        for i in ids {
            if let Some(it) = self.items.get_mut(&i) {
                if it.legend && day >= it.ready_day {
                    it.ready_day = day + it.cooldown;
                } else if !it.legend && it.kind != "ยาวิเศษ" {
                    it.condition = (it.condition - k("ITEM_WEAR") as f32 * 0.2).max(0.0);
                }
            }
        }
        // ของที่พังหลุดจากมือ
        let gone: Vec<u32> = self.people[id as usize].items.iter().copied().filter(|i| self.items.get(i).map_or(true, |it| !it.legend && it.condition <= 0.05)).collect();
        self.people[id as usize].items.retain(|i| !gone.contains(i));
        for i in gone {
            self.items.remove(&i);
        }
    }

    /// สมบัติช่วยบำเพ็ญที่ถืออยู่ — (ตัวคูณความเสื่อม, ตัวคูณความเข้าใจ, โบนัสข้ามขั้น)
    pub fn cultivation_aid(&self, id: Pid) -> (f64, f64, f64) {
        let aids = data::table("treasures", "CULTIVATION_AIDS");
        for i in &self.people[id as usize].items {
            if let Some(it) = self.items.get(i) {
                let a = &aids[it.name.as_str()];
                if a.is_object() {
                    return (a["decay_mult"].as_f64().unwrap_or(1.0), a["insight_mult"].as_f64().unwrap_or(1.0), a["break_bonus"].as_f64().unwrap_or(0.0));
                }
            }
        }
        (1.0, 1.0, 0.0)
    }

    pub fn holds_anti_chaos_treasure(&self, id: Pid) -> bool {
        let name = data::table("treasures", "ANTI_CHAOS_TREASURE").as_str().unwrap_or("");
        self.people[id as usize].items.iter().any(|i| self.items.get(i).map_or(false, |it| it.name == name))
    }

    /// ยาวิเศษในย่าม (ที่ช่วยข้ามขั้น)
    pub fn pill_count(&self, id: Pid) -> usize {
        self.people[id as usize].items.iter().filter(|i| self.items.get(i).map_or(false, |it| it.kind == "ยาวิเศษ")).count()
    }

    /// กินยาวิเศษสูงสุด n เม็ด — คืนโบนัสรวม และอายุขัยที่ได้เพิ่ม
    pub fn eat_pills(&mut self, id: Pid, n: usize) -> (f64, f32) {
        let pills: Vec<u32> = self.people[id as usize].items.iter().copied().filter(|i| self.items.get(i).map_or(false, |it| it.kind == "ยาวิเศษ")).take(n).collect();
        let (mut bonus, mut life) = (0.0, 0.0);
        for i in &pills {
            let it = self.items.remove(i).unwrap();
            bonus += 1.0 + it.pill_bonus as f64 * 4.0;
            life += it.lifespan_bonus;
        }
        self.people[id as usize].items.retain(|i| !pills.contains(i));
        self.people[id as usize].lifespan += life as f64;
        (bonus, life)
    }

    // ------------------------------------------------------------------ เริ่มโลก
    pub fn seed_treasures(&mut self) {
        let max_tier = self.worlds.iter().map(|w| w.tier).max().unwrap_or(0);
        let rows = data::table("treasures", "TREASURES").as_array().unwrap().clone();
        for r in rows {
            let (name, desc, grade, cd, tier) = (r[0].as_str().unwrap().to_string(), r[2].as_str().unwrap_or("").to_string(), r[3].as_f64().unwrap() as f32, r[4].as_i64().unwrap(), (r[5].as_u64().unwrap() as u8).min(max_tier));
            let homes: Vec<u16> = self.worlds.iter().filter(|w| w.tier == tier && matches!(w.kind, WorldKind::Main | WorldKind::Sister | WorldKind::Branch)).map(|w| w.id).collect();
            let w = homes.get(self.rng.below(homes.len().max(1) as u64) as usize).copied().unwrap_or(0);
            let id = self.new_item("สมบัติฟ้าดิน", name, tier, grade, None);
            {
                let it = self.items.get_mut(&id).unwrap();
                it.legend = true;
                it.desc = desc;
                it.cooldown = cd;
            }
            self.legends.push(id);
            let pool = self.living_in(w);
            if !pool.is_empty() && self.chance(0.45) {
                let holder = pool[self.rng.below(pool.len() as u64) as usize];
                self.people[holder as usize].items.push(id);
            } else {
                let gold = 50.0 * self.rng.next_f64();
                self.ledger.gold("issued", gold);
                let seal = k("SEAL_BASE") * (0.2 + 2.3 * self.rng.next_f64());
                let places = self.worlds[w as usize].places.clone();
                let place = places[self.rng.below(places.len() as u64) as usize];
                self.new_cache(w, place, None, "ผู้วางฟ้าดิน".into(), seal, vec![id], gold, false);
            }
        }
        // เศษวิชาแก้ทางโกลาหล กระจายในโลกมนุษย์
        let homes = self.worlds[0].places.clone();
        for (i, s) in skills().iter().enumerate() {
            if !s.anti_chaos {
                continue;
            }
            for piece in 0..k("FRAGMENTS_PER_SKILL") as u8 {
                let place = homes[self.rng.below(homes.len() as u64) as usize];
                self.fragments.push(Fragment { skill: i as u16, piece, place, found: false });
            }
        }
        // ซากแดนลับมีทองตกค้าง — แหล่งกำเนิดที่ประกาศ แบ่งตามชั้นของแดน
        self.ruin_gold = self.worlds.iter().map(|w| k("RUIN_GOLD_DEPOSIT") * (1.0 + w.tier as f64)).collect();
        let total: f64 = self.ruin_gold.iter().sum();
        self.ledger.gold("issued", total);
    }

    pub fn new_cache(&mut self, world: u16, place: u32, owner: Option<Pid>, owner_name: String, seal: f64, items: Vec<u32>, gold: f64, trap: bool) -> u32 {
        self.next_cache += 1;
        let id = self.next_cache;
        self.caches.push(Cache { id, world, place, owner, owner_name, sealed_day: self.day, seal, items, gold, trap, opened: false });
        id
    }

    pub fn seal_left(&self, c: &Cache) -> f64 {
        c.seal - k("SEAL_DECAY_PER_YEAR") * (self.day - c.sealed_day) as f64 / 365.0
    }

    /// สมบัติฟ้าดินที่หลุดจากโลก ถูกผนึกกลับเข้าแดนลับ (ตรวจทุกสิบปี)
    pub fn reseal_lost_legends(&mut self) {
        let mut held = std::collections::BTreeSet::new();
        for &i in &self.alive {
            held.extend(self.people[i as usize].items.iter().copied());
        }
        for c in &self.caches {
            if !c.opened {
                held.extend(c.items.iter().copied());
            }
        }
        let lost: Vec<u32> = self.legends.iter().copied().filter(|i| !held.contains(i)).collect();
        if lost.is_empty() {
            return;
        }
        let places = self.worlds[0].places.clone();
        let place = places[self.rng.below(places.len() as u64) as usize];
        let names: Vec<String> = lost.iter().take(5).map(|i| self.items[i].name.clone()).collect();
        self.new_cache(0, place, None, "ผู้วางฟ้าดิน".into(), k("SEAL_BASE"), lost.clone(), 0.0, false);
        self.emit_at("สมบัติฟ้าดินหวนคืนผนึก", 0, place, "ผนึกกลับคืน", format!("สมบัติฟ้าดิน {} ชิ้น ({}) ที่ขาดผู้ครองถูกฟ้าดินผนึกกลับสู่แดนลับ", lost.len(), names.join(" · ")));
    }

    // ------------------------------------------------------------------ ซ่อนตัว / แดนลับ
    /// ผู้บำเพ็ญขั้นสูงที่ไปต่อไม่ได้หาที่ซ่อนตัว ทำแดนลับผนึกสมบัติทิ้งไว้ (บางคนแกล้งตายวางกับดัก)
    pub fn hide(&mut self, id: Pid) -> i64 {
        let (world, place, realm) = (self.people[id as usize].world, self.people[id as usize].place, self.people[id as usize].realm);
        let trap = self.chance(k("CACHE_TRAP_P"));
        let items = std::mem::take(&mut self.people[id as usize].items);
        let gold = std::mem::replace(&mut self.people[id as usize].gold, 0.0);
        let mut items = items;
        if self.chance(k("CACHE_RELIC_P")) {
            // คัมภีร์หรือยันต์ที่ผู้ซ่อนตัวทิ้งไว้
            let cats = data::table("config", "MANUALS_AND_TALISMANS").as_object().unwrap().clone();
            let keys: Vec<&String> = cats.keys().collect();
            let cat = keys[self.rng.below(keys.len() as u64) as usize].clone();
            let names = data::strs(&cats[&cat]);
            let name = names[self.rng.below(names.len() as u64) as usize].split(" (").next().unwrap().to_string();
            let kind = if cat.starts_with("ยันต์") { "ยันต์วิเศษ" } else { "คัมภีร์" };
            let tier = realm / self.cfg.realm_band;
            items.push(self.new_item(kind, name, tier, 1.0 + 0.5 * (realm % 10) as f32 / 9.0, Some(id)));
        }
        let n = self.people[id as usize].name.clone();
        let seal = k("SEAL_BASE") * (0.5 + 0.25 * (realm % 10) as f64);
        self.new_cache(world, place, Some(id), n.clone(), seal, items, gold, trap);
        let years = 5 + self.rng.below(30) as i64;
        self.people[id as usize].process = Some(Process::Hidden { since: self.day, until: self.day + years * 365, trap });
        let how = if trap { "แกล้งตายวางกับดักไว้" } else { "ผนึกสมบัติทิ้งไว้" };
        self.emit("ซ่อนตัว", Some(id), None, "ซ่อนตัว", format!("{}หายไปจากโลก สร้างแดนลับ{}", n, how));
        years * 365
    }

    pub fn emerge_hidden(&mut self, id: Pid, since: i64) {
        self.people[id as usize].process = None;
        let yrs = (self.day - since) / 365;
        let n = self.people[id as usize].name.clone();
        self.emit("ออกจากแดนลับ", Some(id), None, "กลับสู่โลก", format!("{}ก้าวออกจากแดนลับกลับสู่โลกอีกครั้งหลังหายไป {} ปี — ตลอดเวลาในนั้นขั้นพลังไม่ขยับเลย", n, yrs));
        let gap = self.range(10, 60);
        self.schedule(id, gap);
    }

    /// ค้นแดนลับ — เศษวิชาโบราณ → แดนลับที่ผนึกคลายแล้ว (ตามข่าวลือก่อน) → ซากที่ถูกกวาดไปแล้ว
    pub fn search_secret(&mut self, id: Pid) -> i64 {
        let gap = self.range(60, 270);
        let (place, world, fate) = (self.people[id as usize].place, self.people[id as usize].world, self.people[id as usize].fate);
        let name = self.people[id as usize].name.clone();
        // ---- เศษวิชา
        if let Some(fi) = self.fragments.iter().position(|f| f.place == place && !f.found && !self.people[id as usize].fragments.get(&f.skill).map_or(false, |v| v.contains(&f.piece))) {
            if self.chance(k("FRAGMENT_FIND_P") * (1.0 + fate as f64 * k("FRAGMENT_FATE_BONUS"))) {
                self.fragments[fi].found = true;
                let (sk, piece) = (self.fragments[fi].skill, self.fragments[fi].piece);
                let got = self.people[id as usize].fragments.entry(sk).or_default();
                got.push(piece);
                let have = got.len();
                let need = k("FRAGMENTS_PER_SKILL") as usize;
                let sname = skills()[sk as usize].name.clone();
                if have >= need && self.learn_skill(id, sk) {
                    self.emit("ค้นแดนลับ", Some(id), None, "ต่อวิชาโบราณสำเร็จ", format!("{}ต่อเศษจารึกวิชาโบราณครบทุกชิ้น ตรัสรู้「{}」ในทันที — วิชาที่แก้ทางเผ่าโกลาหลได้", name, sname));
                } else {
                    self.emit("ค้นแดนลับ", Some(id), None, "พบชิ้นส่วนวิชา", format!("{}ขุดพบเศษจารึก「{}」ชิ้นที่ {}/{}", name, sname, have, need));
                }
                return gap;
            }
        }
        // ---- แดนลับที่ผนึกคลายแล้ว
        let open: Vec<usize> = (0..self.caches.len()).filter(|&i| {
            let c = &self.caches[i];
            c.world == world && !c.opened && self.seal_left(c) <= 0.0
        }).collect();
        if open.is_empty() {
            self.ruin_find(id);
            return gap;
        }
        let leads = self.people[id as usize].leads.clone();
        let led: Vec<usize> = open.iter().copied().filter(|&i| leads.contains(&self.caches[i].id)).collect();
        let ci = if let Some(&i) = led.first() { i } else { open[self.rng.below(open.len() as u64) as usize] };
        let tail = if !led.is_empty() { " ตามรอยข่าวลือที่เคยได้ยินมา" } else { "" };
        let owner_name = self.caches[ci].owner_name.clone();
        // อสูรกลืนแดนลับเพื่อวิวัฒนาการ
        if self.race(id) == "อสูร" {
            let seal = self.caches[ci].seal;
            let c = self.caches.remove(ci);
            self.people[id as usize].insight += seal * 0.2;
            for i in c.items {
                if self.legends.contains(&i) {
                    self.people[id as usize].items.push(i);
                } else {
                    self.items.remove(&i);
                }
            }
            self.ruin_gold[world as usize] += c.gold;
            self.emit("ค้นแดนลับ", Some(id), None, "กลืนกิน", format!("{}พบแดนลับของ{} กลืนกินแก่นพลังเพื่อวิวัฒนาการ{}", name, owner_name, tail));
            return gap;
        }
        // กับดักของเจ้าของที่แกล้งตาย
        if let (true, Some(owner)) = (self.caches[ci].trap, self.caches[ci].owner) {
            if self.people[owner as usize].alive && matches!(self.people[owner as usize].process, Some(Process::Hidden { .. })) {
                let (w, l, ratio) = self.clash(owner, id);
                let on = self.people[owner as usize].name.clone();
                if w == owner {
                    if ratio >= self.cfg.death_margin && self.chance(0.5) {
                        self.kill(id, Some(owner), &format!("ตายด้วยกับดักในแดนลับของ{}", on), false);
                    } else {
                        let p = &mut self.people[l as usize];
                        p.injury = (p.injury + 0.4).min(1.0);
                        self.emit("ค้นแดนลับ", Some(id), Some(owner), "ติดกับดัก", format!("{}เจอ{}แกล้งตายรออยู่ในแดนลับ ต้องถอยออกมา", name, on));
                    }
                    return gap;
                }
            }
        }
        let c = &mut self.caches[ci];
        c.opened = true;
        let rot = 1.0 - ((-self.seal_left(&self.caches[ci])) / k("SEAL_BASE")).clamp(0.0, 1.0) * k("CACHE_ROT");
        let c = &mut self.caches[ci];
        let items = std::mem::take(&mut c.items);
        let gold = std::mem::replace(&mut c.gold, 0.0);
        let (mut got, mut rotted) = (0, 0);
        for i in items {
            let it = self.items.get_mut(&i).unwrap();
            it.condition *= rot as f32;
            if it.legend {
                it.condition = it.condition.max(0.35);
                self.people[id as usize].items.push(i);
                got += 1;
            } else if it.condition > 0.15 {
                self.people[id as usize].items.push(i);
                got += 1;
            } else {
                self.items.remove(&i);
                rotted += 1;
            }
        }
        self.people[id as usize].gold += gold * rot;
        self.ruin_gold[world as usize] += gold * (1.0 - rot);
        let extra = if rotted > 0 { format!(" (ผุสูญสลาย {} ชิ้น)", rotted) } else { String::new() };
        self.emit("ค้นแดนลับ", Some(id), None, "ค้นพบ", format!("{}เปิดแดนลับของ{}ได้ ได้ของ {} ชิ้น ทอง {:.0}{}{}", name, owner_name, got, gold * rot, extra, tail));
        gap
    }

    /// ซากแดนลับที่ถูกกวาดไปแล้ว — แดนลับมีของเสมอ ต่างกันแค่มากหรือน้อย (ผูกกับชะตาของคนค้น)
    fn ruin_find(&mut self, id: Pid) {
        let (world, fate) = (self.people[id as usize].world, self.people[id as usize].fate);
        let mut luck = 1.0 + k("RUIN_CORES_FATE") * fate.max(0) as f64;
        let rich = physics::lognormal_value(1.0, k("RUIN_VALUE_SIGMA"), self.rng.next_f64()).max(k("RUIN_MIN_MULT"));
        luck *= rich;
        let cores = ((1 + self.rng.below(4)) as f64 * luck).round().max(1.0);
        let ins = (0.4 + 1.2 * self.rng.next_f64()) * luck;
        let coins = ((20.0 + 240.0 * self.rng.next_f64()) * luck).min(self.ruin_gold[world as usize]);
        self.ruin_gold[world as usize] -= coins;
        let p = &mut self.people[id as usize];
        p.mats[Material::Core as usize] += cores as f32;
        p.insight += ins;
        p.gold += coins;
        let name = p.name.clone();
        // จารึกชี้ทางไปแดนลับที่ยังผนึกอยู่
        let sealed: Vec<u32> = self.caches.iter().filter(|c| c.world == world && !c.opened).map(|c| c.id).collect();
        let mut tail = String::new();
        if !sealed.is_empty() && self.chance(k("RUIN_LEAD_P")) {
            let c = sealed[self.rng.below(sealed.len() as u64) as usize];
            let p = &mut self.people[id as usize];
            p.leads.push(c);
            if p.leads.len() > k("RUMOR_LEAD_MAX") as usize {
                p.leads.remove(0);
            }
            let owner = self.caches.iter().find(|x| x.id == c).unwrap().owner_name.clone();
            tail = format!(" และอ่านเจอจารึกชี้ทางไปแดนลับของ{}", owner);
        }
        let jackpot = if rich >= k("RUIN_JACKPOT") { " — ซากนี้ยังไม่มีใครค้นถึงก้น" } else { "" };
        if rich >= k("RUIN_JACKPOT") {
            self.emit("ค้นแดนลับ", Some(id), None, "พบซากแดนลับ", format!("{}พบซากแดนลับ เก็บแก่นพลัง {:.0} ทอง {:.0}{}{}", name, cores, coins, jackpot, tail));
        }
    }

    // ------------------------------------------------------------------ ล่าอสูร
    pub fn hunt(&mut self, id: Pid) -> i64 {
        let place = self.people[id as usize].place as usize;
        let eco = (self.places[place].stock[Material::Core as usize] / self.eco_k(place, Material::Core)).min(1.0);
        let want = ((1 + self.rng.below(3)) as f64 * eco).round().max(1.0);
        let n = want.min(self.places[place].stock[Material::Core as usize]);
        self.places[place].stock[Material::Core as usize] -= n;
        let p = &mut self.people[id as usize];
        p.mats[Material::Core as usize] += n as f32;
        p.refine = (p.refine + (k("HUNT_REFINE_PER_CORE") * n).min(k("HUNT_REFINE_CAP"))).min(p.blood[SPIRIT] as f64 + 0.2);
        p.insight += k("HUNT_INSIGHT");
        let name = p.name.clone();
        // อสูรต่อสู้กลับ — คนที่อ่อนกว่าเสี่ยงบาดเจ็บหรือตาย
        let danger = 0.15 * (1.0 - (self.power(id) / 20.0).min(0.9));
        if self.chance(danger) {
            let p = &mut self.people[id as usize];
            p.injury = (p.injury + 0.3).min(1.0);
            if p.injury > 0.85 && p.fate <= 0 && self.chance(0.3) {
                self.kill(id, None, "ตายในการล่าอสูร", false);
                return 0;
            }
        }
        if n >= 3.0 {
            self.emit("ล่าอสูร", Some(id), None, "ได้แก่นพลัง", format!("{}ล่าอสูรได้แก่นพลัง {:.0} เม็ด", name, n));
        }
        self.range(25, 150)
    }

    // ------------------------------------------------------------------ หลอมยา / หลอมอาวุธ
    pub fn craft(&mut self, id: Pid, pill: bool) -> i64 {
        let gap = self.range(40, 200);
        let place = self.people[id as usize].place as usize;
        let furnace = data::world().places[place].forge;
        let name = self.people[id as usize].name.clone();
        if furnace < 0 || self.people[id as usize].mats[Material::Core as usize] < k("CRAFT_CORE_COST") as f32 {
            return gap / 2;
        }
        let rank = if pill { self.people[id as usize].alch_rank } else { self.people[id as usize].forge_rank }.max(0);
        let table = data::table("crafting", if pill { "PILLS" } else { "WEAPONS" }).as_array().unwrap();
        let mut pool: Vec<&serde_json::Value> = table.iter().filter(|x| can_make(rank, x[1].as_i64().unwrap(), x[2].as_i64().unwrap()) && x[1].as_i64().unwrap() <= furnace).collect();
        if pool.is_empty() {
            return gap / 2;
        }
        pool.sort_by_key(|x| -(x[1].as_i64().unwrap() * 3 + x[2].as_i64().unwrap()));
        // วัตถุดิบ: ยาใช้สมุนไพร อาวุธใช้แร่ (เกรดสูงใช้มากกว่า)
        let recipe = if self.chance(0.35) { pool[0] } else { pool[self.rng.below(pool.len() as u64) as usize] };
        let (rtier, rgrade) = (recipe[1].as_i64().unwrap(), recipe[2].as_i64().unwrap());
        let mat = if pill { Material::Herb } else { Material::Ore };
        let need = (data::table("crafting", "CRAFT_MAT_COST").as_f64().unwrap_or(3.0) as f32) * (1.0 + rtier as f32 + 0.5 * rgrade as f32);
        if self.people[id as usize].mats[mat as usize] < need {
            return gap / 2;
        }
        let batch_cap = (k("CRAFT_MAX_BATCH") as i64 - rtier * 2 - rgrade).max(1);
        let (mut made, mut failed) = (0, 0);
        let fur_grade = data::table("crafting", "FURNACES").as_array().unwrap().iter().filter(|f| f[1].as_i64().unwrap() <= furnace).map(|f| f[2].as_i64().unwrap()).max().unwrap_or(0);
        let rname = recipe[0].as_str().unwrap().to_string();
        while made + failed < batch_cap {
            let p = &self.people[id as usize];
            if p.mats[Material::Core as usize] < k("CRAFT_CORE_COST") as f32 || p.mats[mat as usize] < need {
                break;
            }
            let p = &mut self.people[id as usize];
            p.mats[Material::Core as usize] -= k("CRAFT_CORE_COST") as f32;
            p.mats[mat as usize] -= need;
            let lvl = if pill { &mut p.alchemy } else { &mut p.forge };
            *lvl += k("CRAFT_GAIN") as f32;
            let lvl = *lvl as f64;
            let p_ok = (k("CRAFT_BASE_P") + 0.10 * (rank as f64 - (rtier * 3 + rgrade) as f64) + 0.05 * lvl + k_or_zero("FURNACE_GRADE_BONUS") * fur_grade as f64).min(0.92).max(0.05);
            if !self.chance(p_ok) {
                failed += 1;
                continue;
            }
            let item = if pill {
                let bonus = recipe[4].as_f64().unwrap_or(0.05) as f32;
                let i = self.new_item("ยาวิเศษ", rname.clone(), rtier as u8, 1.0 + bonus * 4.0, Some(id));
                let it = self.items.get_mut(&i).unwrap();
                it.pill_bonus = bonus;
                it.desc = recipe[3].as_str().unwrap_or("").to_string();
                it.lifespan_bonus = longevity_years(rtier, rgrade);
                i
            } else {
                let q = recipe[3].as_f64().unwrap_or(0.3) as f32 * (0.8 + 0.4 * self.rng.next_f64() as f32);
                self.new_item("อาวุธวิเศษ", rname.clone(), rtier as u8, q * 4.0, Some(id))
            };
            self.people[id as usize].items.push(item);
            made += 1;
        }
        // เลื่อนขั้นช่าง
        let p = &mut self.people[id as usize];
        let (lvl, rk) = if pill { (p.alchemy, &mut p.alch_rank) } else { (p.forge, &mut p.forge_rank) };
        if *rk < 0 {
            *rk = 0;
        }
        let mut promoted = None;
        if lvl as f64 >= (*rk as f64 + 1.0) * data::table("crafting", "RANK_XP").as_f64().unwrap_or(4.0) && *rk < 8 {
            *rk += 1;
            let ranks = data::strs(data::table("crafting", if pill { "ALCHEMY_RANKS" } else { "FORGE_RANKS" }));
            promoted = Some(ranks[*rk as usize].clone());
        }
        if made > 0 {
            let tail = promoted.map(|r| format!(" — เลื่อนเป็น{}", r)).unwrap_or_default();
            self.emit(if pill { "หลอมยา" } else { "หลอมอาวุธ" }, Some(id), None, "สำเร็จ", format!("{}หลอม{}สำเร็จ {} ชิ้น{}", name, rname, made, tail));
        }
        gap
    }

    /// ขายของที่หลอมได้ให้ผู้บำเพ็ญที่อยู่ด้วยกัน (ราคาตามเกรด)
    pub fn sell_crafts(&mut self, id: Pid) -> i64 {
        let place = self.people[id as usize].place;
        let goods: Vec<u32> = self.people[id as usize].items.iter().copied().filter(|i| self.items.get(i).map_or(false, |it| !it.legend && it.maker == Some(id))).collect();
        let buyers: Vec<Pid> = self.present_at(place).into_iter().filter(|&b| b != id && self.people[b as usize].cultivator).collect();
        let mut sold = 0;
        for g in goods {
            let price = 15.0 * (1.0 + self.items[&g].tier as f64) * self.items[&g].grade as f64;
            let Some(&b) = buyers.iter().filter(|&&b| self.people[b as usize].gold >= price).max_by(|&&a, &&b| self.people[a as usize].gold.partial_cmp(&self.people[b as usize].gold).unwrap().then(b.cmp(&a))) else { break };
            self.people[b as usize].gold -= price;
            self.people[id as usize].gold += price;
            self.people[id as usize].items.retain(|&i| i != g);
            self.people[b as usize].items.push(g);
            sold += 1;
        }
        if sold > 0 {
            self.ledger.count("ขายของหลอม");
        }
        self.range(5, 25)
    }

    // ------------------------------------------------------------------ ชิงสมบัติ
    pub fn seize_treasure(&mut self, a: Pid, t: Pid) -> i64 {
        let treas: Vec<u32> = self.people[t as usize].items.iter().copied().filter(|i| self.items.get(i).map_or(false, |it| it.kind != "ยาวิเศษ")).collect();
        if treas.is_empty() || self.people[t as usize].place != self.people[a as usize].place {
            return self.range(5, 20);
        }
        let (w, l, ratio) = self.clash(a, t);
        self.wear_items(a);
        self.wear_items(t);
        let (an, tn) = (self.people[a as usize].name.clone(), self.people[t as usize].name.clone());
        *self.people[l as usize].rivals.entry(w).or_insert(0) += 2;
        if w == a {
            let best = *treas.iter().max_by(|&&x, &&y| self.items[&x].grade.partial_cmp(&self.items[&y].grade).unwrap().then(y.cmp(&x))).unwrap();
            self.people[t as usize].items.retain(|&i| i != best);
            self.people[a as usize].items.push(best);
            self.add_debt(a, "ปล้น", t);
            let iname = self.items[&best].name.clone();
            if ratio >= self.cfg.death_margin * 1.3 && self.chance(0.3) {
                self.kill(t, Some(a), &format!("ถูก{}ชิงสมบัติจนสิ้นชีพ", an), false);
            }
            self.emit("ชิงสมบัติ", Some(a), Some(t), "ชิงได้", format!("{}ชิง{}ไปจาก{}", an, iname, tn));
        } else {
            let p = &mut self.people[a as usize];
            p.injury = (p.injury + 0.3).min(1.0);
            self.emit("ชิงสมบัติ", Some(a), Some(t), "ถูกตอบโต้", format!("{}หมายชิงสมบัติจาก{}แต่ถูกตีกลับ", an, tn));
        }
        self.range(15, 60)
    }

    // ------------------------------------------------------------------ งานประมูล (ประมูลราคาที่สอง)
    pub fn market_auction(&mut self, world: u16) {
        let d = data::world();
        let places: Vec<String> = data::strs(data::table("config", "AUCTION_PLACES"));
        let mut spots: Vec<(u32, Vec<Pid>)> = Vec::new();
        for &pl in &self.worlds[world as usize].places {
            if !places.contains(&d.places[pl as usize].kind) {
                continue;
            }
            let folk: Vec<Pid> = self.present_at(pl).into_iter().filter(|&c| self.is_adult(c) && self.people[c as usize].gold >= k("AUCTION_MIN_MONEY")).collect();
            if folk.len() >= 3 {
                spots.push((pl, folk));
            }
        }
        if spots.is_empty() {
            return;
        }
        let (place, mut folk) = spots.swap_remove(self.rng.below(spots.len() as u64) as usize);
        let hosts = data::strs(data::table("config", "AUCTION_HOSTS"));
        folk.sort_by_key(|&c| (!self.profession_is_name(c, &hosts), c));
        let host = folk[0];
        let mut bidders: Vec<Pid> = folk[1..].to_vec();
        bidders.sort_by(|&a, &b| self.people[b as usize].gold.partial_cmp(&self.people[a as usize].gold).unwrap().then(a.cmp(&b)));
        bidders.truncate(k("AUCTION_MAX_BIDDERS") as usize);
        if bidders.len() < 2 {
            return;
        }
        // ล็อต: ของที่ดีที่สุดของเจ้าภาพ ไม่มีก็เป็นของเก่าแก่ทั่วไป (ยาที่ตลาดคัดมา)
        let lot = self.people[host as usize].items.iter().copied().filter(|i| !self.items[i].legend).max_by(|&a, &b| self.items[&a].grade.partial_cmp(&self.items[&b].grade).unwrap().then(b.cmp(&a)));
        let lots = data::strs(data::table("config", "AUCTION_LOTS"));
        let lot_name = lot.map(|i| self.items[&i].name.clone()).unwrap_or_else(|| lots[self.rng.below(lots.len() as u64) as usize].clone());
        let base_range = data::table("config", "AUCTION_BASE_PRICE");
        let mid = (base_range[0].as_f64().unwrap() + base_range[1].as_f64().unwrap()) / 2.0;
        let base = physics::lognormal_value(mid, k("LOT_VALUE_SIGMA"), self.rng.next_f64()) * (1.0 + lot.map_or(0.0, |i| self.items[&i].tier as f64));
        let mut bids = Vec::new();
        for &c in &bidders {
            let p = &self.people[c as usize];
            let want = k("AUCTION_GREED_W") * p.greed as f64 + 0.3 + 0.05 * (p.realm % 10) as f64;
            let private = physics::lognormal_value(base * want, k("BID_VALUE_SIGMA"), self.rng.next_f64());
            bids.push((private.min(p.gold) * 10.0).floor() / 10.0);
        }
        let (idx, pay) = physics::second_price(Some(bids.clone()));
        let idx = idx as usize;
        let winner = bidders[idx];
        let price = (bids[idx].min(pay * k("AUCTION_STEP")) * 10.0).floor() / 10.0;
        if price <= 0.0 {
            return;
        }
        let runner = (0..bidders.len()).filter(|&i| i != idx).max_by(|&a, &b| bids[a].partial_cmp(&bids[b]).unwrap().then(b.cmp(&a))).map(|i| bidders[i]).unwrap();
        self.people[winner as usize].gold -= price;
        self.people[host as usize].gold += price;
        match lot {
            Some(i) => {
                self.people[host as usize].items.retain(|&x| x != i);
                self.people[winner as usize].items.push(i);
            }
            None => {
                // ของเก่าแก่ทั่วไป — เป็นยาวิเศษหนึ่งเม็ดของชั้นแดน
                let tier = self.worlds[world as usize].tier;
                let i = self.new_item("ยาวิเศษ", lot_name.clone(), tier, 1.2, None);
                self.items.get_mut(&i).unwrap().pill_bonus = 0.1;
                self.people[winner as usize].items.push(i);
            }
        }
        *self.people[runner as usize].rivals.entry(winner).or_insert(0) += 1;
        *self.people[winner as usize].bonds.entry(host).or_insert(0) += 1;
        let (wn, rn, pn) = (self.people[winner as usize].name.clone(), self.people[runner as usize].name.clone(), self.place_name(place));
        self.emit("เปิดประมูล", Some(winner), Some(host), "ชนะประมูล", format!("งานประมูลที่{} — {}ประมูล{}ไปได้ในราคา {:.1} ตำลึง เฉือน{}ไปอย่างหวุดหวิด ({} ผู้ร่วมประมูล)", pn, wn, lot_name, price, rn, bidders.len()));
    }

    pub fn profession_is_name(&self, id: Pid, names: &[String]) -> bool {
        let prof = &data::world().professions[self.people[id as usize].profession as usize].0;
        names.contains(prof)
    }
}

fn k_or_zero(name: &str) -> f64 {
    data::k_or(name, 0.0)
}
