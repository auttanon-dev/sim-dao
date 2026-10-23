//! เหตุการณ์ระหว่างแดน — มารบุก มหาผนึกหมื่นมาร โกลาหลบุก รอยแยก ศึกพันธมิตร ผนึกเจ้าโกลาหล
//! การเกณฑ์คนขึ้นฟ้า และประตูแดนเซียนที่ปิดเมื่อคนแน่น
//!
//! ทอยบนนาฬิกาโลก (ต่อแดนต่อรอบ) ไม่ใช่ต่อเทิร์นของคน — ความถี่จึงขึ้นกับเวลา ไม่ขึ้นกับจำนวนคน

use super::data::{self, k};
use super::model::*;
use super::sim::Engine;
use crate::physics;

impl Engine {
    pub fn tick_realms(&mut self, days: f64) {
        let rounds = days / 30.0; // ค่าคงที่เดิมเป็นโอกาสต่อหนึ่งรอบนาฬิกาโลก (30 วัน)
        self.tick_mara_seal();
        let raid_p = k("MARA_RAID_P") * if self.mara_seal_broken { 2.5 } else { 1.0 };
        if self.mara_world.is_some() && self.chance(raid_p * rounds) {
            self.mara_raid(0);
        }
        // เผ่าโกลาหล
        let awake = self.lord.map(|l| self.people[l as usize].alive && !self.people[l as usize].dissolved()).unwrap_or(false);
        if let Some(cw) = self.chaos_world {
            let top = self.worlds[cw as usize].lateral[0];
            if self.chance(k("CHAOS_RAID_P") * rounds * 0.3) {
                self.chaos_raid(top);
            }
            if self.chance(k("CHAOS_INVADE_P") * rounds) {
                self.chaos_invade(0);
            }
            let w0 = &self.worlds[0];
            if (awake || w0.rift >= 3.0) && self.day - w0.last_coalition >= k("COALITION_COOLDOWN") as i64 && self.chance(k("COALITION_P") * rounds * 0.5) {
                self.coalition_strike(0);
            }
            if self.lord_seal > 0.0 {
                self.lord_seal = (self.lord_seal - k("LORD_SEAL_DECAY_PER_YEAR") * days / 365.0).max(0.0);
                if self.lord_seal <= 0.0 {
                    self.emit_at("มหาผนึกโกลาหลเสื่อม", cw, self.worlds[cw as usize].places[0], "ผนึกสลาย", "มหาผนึกที่ตรึงเจ้าโกลาหลเสื่อมสลายแล้ว มันเริ่มดูดพลังจากความตายอีกครั้ง".into());
                }
            }
            if self.day - self.lord_seal_last >= k("LORD_SEAL_COOLDOWN") as i64 && self.chance(k("LORD_SEAL_P") * rounds * 0.5) {
                self.seal_lord();
            }
            // เผ่าโกลาหลแพร่พันธุ์ช้าๆ ในถิ่นตัวเอง
            if self.chance(physics::hazard_p(k("CHAOS_SPAWN_PER_YEAR"), days)) {
                self.spawn_chaos_one(cw);
            }
        }
        // ฟ้าเกณฑ์คนขึ้นไปเมื่อโกลาหลกดดันจักรวาล
        if (awake || self.worlds[0].rift > 0.0 || self.lord_seal <= 0.0) && self.chance(k("CONSCRIPT_P") * rounds) {
            self.conscript(0);
        }
        // ประตูแดนเซียนปิดเมื่อคนแน่น · ความบาดหมางจางลง · รอยแยกค่อยๆ สมาน · ค่ายกลซ่อมตัวเอง
        let limit = k("HEAVEN_POP_LIMIT") as usize;
        let mut pop = vec![0usize; self.worlds.len()];
        for &i in &self.alive {
            pop[self.people[i as usize].world as usize] += 1;
        }
        for w in 0..self.worlds.len() {
            let world = &mut self.worlds[w];
            if world.tier == 1 && world.kind == WorldKind::Main {
                if pop[w] >= limit {
                    if !world.closed {
                        world.defense = world.defense_max;
                    }
                    world.closed = true;
                } else if (pop[w] as f64) < limit as f64 * 0.8 {
                    world.closed = false;
                }
            }
            world.resentment = (world.resentment - k("RESENT_DECAY_PER_YEAR") * days / 365.0).max(0.0);
            world.rift = (world.rift - k("RIFT_HEAL_PER_YEAR") * days / 365.0).max(0.0);
            world.defense = (world.defense + 2.0 * days / 365.0).min(world.defense_max);
            let day = self.day;
            world.ruined.retain(|&(_, until)| until > day);
        }
    }

    // ------------------------------------------------------------------ มหาผนึกหมื่นมาร
    fn tick_mara_seal(&mut self) {
        if self.day.rem_euclid(365) >= self.cfg.world_tick_days as i64 {
            return; // ปีละครั้ง
        }
        let mut decay = k("MARA_SEAL_DECAY_PER_YEAR");
        if self.chance(k("MARA_SEAL_SHOCK_P")) {
            decay += 0.5 + 2.5 * self.rng.next_f64();
        }
        self.mara_seal = (self.mara_seal - decay).max(0.0);
        let place = self.worlds[0].places[0];
        if self.mara_seal <= k("MARA_SEAL_WEAK_THRESHOLD") && !self.mara_seal_warned && !self.mara_seal_broken {
            self.mara_seal_warned = true;
            self.emit_at("มหาผนึกสั่นคลอน", 0, place, "ผนึกอ่อนแอ", format!("มหาผนึกสะกดหมื่นมารอ่อนกำลังลง (เหลือ {:.1}%) ไอปีศาจเริ่มรั่วไหลสู่โลกมนุษย์", self.mara_seal));
        }
        if self.mara_seal <= k("MARA_SEAL_BROKEN_THRESHOLD") && !self.mara_seal_broken {
            self.mara_seal_broken = true;
            self.emit_at("มหาผนึกแตกพัง", 0, place, "ผนึกพังทลาย", "มหาผนึกสะกดหมื่นมารพังทลาย แดนมารกับโลกมนุษย์เชื่อมถึงกันโดยสมบูรณ์".into());
        }
        if self.mara_seal >= k("MARA_SEAL_WEAK_THRESHOLD") {
            return;
        }
        // ผู้บำเพ็ญฝ่ายธรรมะในโลกมนุษย์ร่วมกันซ่อม
        let mut crew: Vec<Pid> = self
            .living_in(0)
            .into_iter()
            .filter(|&i| {
                let p = &self.people[i as usize];
                p.compassion > 0.6 && (p.realm as f64) >= k("MARA_SEAL_REPAIR_REALM") && !p.is_chaos() && !p.fallen && p.process.is_none()
            })
            .collect();
        crew.sort_by_key(|&i| (std::cmp::Reverse(self.people[i as usize].realm), i));
        crew.truncate(k("MARA_SEAL_REPAIR_CREW") as usize);
        if crew.is_empty() || !self.chance(k("MARA_SEAL_REPAIR_P")) {
            return;
        }
        let before = self.mara_seal;
        let add: f64 = crew.iter().map(|&i| self.people[i as usize].realm as f64).sum::<f64>() * k("MARA_SEAL_REPAIR_PER_REALM");
        self.mara_seal = (self.mara_seal + add).min(k("MARA_SEAL_INITIAL"));
        if self.mara_seal > k("MARA_SEAL_BROKEN_THRESHOLD") {
            self.mara_seal_broken = false;
        }
        if self.mara_seal > k("MARA_SEAL_WEAK_THRESHOLD") {
            self.mara_seal_warned = false;
        }
        let lead = crew[0];
        let n = self.people[lead as usize].name.clone();
        self.emit("ซ่อมมหาผนึก", Some(lead), None, "ซ่อมสำเร็จ", format!("{}นำผู้บำเพ็ญฝ่ายธรรมะ {} คนซ่อมมหาผนึกหมื่นมาร ({:.1}% → {:.1}%)", n, crew.len(), before, self.mara_seal));
    }

    // ------------------------------------------------------------------ มารบุก
    fn pick_raid_victim(&mut self, raider: Pid, prey: &[Pid]) -> Option<Pid> {
        let d = data::world();
        let m = &self.people[raider as usize];
        let bold = (m.kills as f64 * k("MARA_BOLD_PER_KILL")).min(k("MARA_BOLD_CAP"));
        let mut weights = Vec::with_capacity(prey.len());
        for &c in prey {
            let p = &self.people[c as usize];
            let mut w = (k("MARA_VICTIM_REALM_DECAY") + bold).powi((p.realm % 10) as i32);
            if p.realm > m.realm {
                w *= k("MARA_VICTIM_STRONGER") + bold;
            }
            if p.travelling() {
                w *= k("MARA_VICTIM_TRAVEL");
            } else {
                let kind = &d.places[p.place as usize].kind;
                w *= data::table("config", "MARA_VICTIM_PLACE")[kind.as_str()].as_f64().unwrap_or(1.0);
                if self.at[p.place as usize].len() <= 1 {
                    w *= k("MARA_VICTIM_ALONE");
                }
            }
            weights.push(w);
        }
        let total: f64 = weights.iter().sum();
        if total <= 0.0 {
            return None;
        }
        let mut r = self.rng.next_f64() * total;
        for (i, w) in weights.iter().enumerate() {
            r -= w;
            if r <= 0.0 {
                return Some(prey[i]);
            }
        }
        prey.last().copied()
    }

    pub fn mara_raid(&mut self, world: u16) {
        let Some(mw) = self.mara_world else { return };
        let raiders: Vec<Pid> = self.living_in(mw).into_iter().filter(|&i| self.people[i as usize].realm >= 2 && self.is_adult(i) && self.people[i as usize].process.is_none()).collect();
        let prey: Vec<Pid> = self.living_in(world).into_iter().filter(|&i| self.is_adult(i) && !self.people[i as usize].jailed() && !self.people[i as usize].secluded()).collect();
        if raiders.is_empty() || prey.is_empty() {
            return;
        }
        let m0 = raiders[self.rng.below(raiders.len() as u64) as usize];
        let Some(v) = self.pick_raid_victim(m0, &prey) else { return };
        // ส่งมารที่ขั้นใกล้เหยื่อที่สุดมา
        let vr = self.people[v as usize].realm as i32;
        let m = *raiders.iter().min_by_key(|&&c| ((self.people[c as usize].realm as i32 - vr).abs(), c)).unwrap();
        let (mn, vn) = (self.people[m as usize].name.clone(), self.people[v as usize].name.clone());
        if self.worlds[world as usize].defense > 0.0 && self.chance(0.8) {
            let w = &mut self.worlds[world as usize];
            w.defense = (w.defense - 15.0).max(0.0);
            self.emit("มารบุก", Some(m), Some(v), "ถูกสกัดกั้น", format!("ค่ายกลป้องกันโลกปกป้อง{}จากการรุกรานของ{}", vn, mn));
            return;
        }
        let w = &mut self.worlds[world as usize];
        w.defense = (w.defense - 5.0).max(0.0);
        let (mr, vr) = (self.people[m as usize].realm as f64, self.people[v as usize].realm as f64);
        if vr >= mr - k("MARA_FIGHT_REALM_GAP") {
            let grudge = self.people[v as usize].rivals.contains_key(&m);
            let p_win = (0.5 + (vr - mr) * k("MARA_FIGHT_REALM_W") + if grudge { k("MARA_FIGHT_GRUDGE_W") } else { 0.0 }).clamp(k("MARA_FIGHT_WIN_MIN"), k("MARA_FIGHT_WIN_MAX"));
            if self.chance(p_win) {
                self.people[v as usize].kills += 1;
                self.people[v as usize].rivals.remove(&m);
                self.kill(m, Some(v), &format!("ถูก{}สังหารขณะบุกโลกมนุษย์", vn), false);
                self.emit("มารบุก", Some(v), Some(m), "ปราบมารได้", format!("{}จากแดนมารจู่โจม{} แต่{}สู้กลับและสังหารมันลงได้", mn, vn, vn));
                return;
            }
            let p = &mut self.people[v as usize];
            p.injury = (p.injury + 0.25).min(1.0);
            p.decay += 0.5;
        }
        if self.chance(k("MARA_CONVERT_P")) {
            let p = &mut self.people[v as usize];
            p.blood[MARA] += 0.25;
            let s: f32 = p.blood.iter().sum();
            for x in p.blood.iter_mut() {
                *x /= s;
            }
            p.inner += 1.5;
            self.emit("มารบุก", Some(m), Some(v), "ถูกครอบงำ", format!("{}จากแดนมารครอบงำ{} เลือดมารลุกลาม", mn, vn));
        } else if self.people[v as usize].fate > 0 {
            let p = &mut self.people[v as usize];
            p.fate -= 1;
            p.near_death += 1;
            p.decay += 0.5;
            *p.rivals.entry(m).or_insert(0) += k("MARA_RAID_GRUDGE") as i16;
            self.emit("มารบุก", Some(m), Some(v), "รอดตายด้วยชะตา", format!("{}จากแดนมารจู่โจม{} แต่{}หนีรอดมาได้อย่างหวุดหวิด และจดจำใบหน้ามันไว้", mn, vn, vn));
        } else {
            self.kill(v, Some(m), &format!("ถูก{}จากแดนมารจับไปเป็นอาหาร", mn), false);
        }
    }

    // ------------------------------------------------------------------ เผ่าโกลาหลบุก
    fn spawn_chaos_one(&mut self, cw: u16) {
        let ranks = data::strs(data::table("config", "CHAOS_RANKS")).len() as i64;
        let cap = self.cfg.realm_cap_of_tier(self.worlds[cw as usize].tier);
        let id = self.spawn(cw, None, 200.0, [None, None]);
        let rank = ((self.rng.gauss() * 1.0).abs() as i64).clamp(0, ranks - 2) as i8;
        let p = &mut self.people[id as usize];
        p.chaos_rank = rank;
        p.blood = [0.0, 0.0, 0.0, 0.0, 1.0];
        p.inner_none = true;
        p.cultivator = true;
        p.realm = cap;
        p.peak_realm = cap;
        p.lifespan = 1e9;
    }

    /// ความได้เปรียบของเผ่าโกลาหล — ผู้รู้วิชาแก้ทางลดลงได้
    pub fn chaos_edge(&self, attacker: Pid, defender: Pid) -> f64 {
        let a = &self.people[attacker as usize];
        let d = &self.people[defender as usize];
        if a.is_chaos() && !d.is_chaos() {
            let cut = if self.has_anti_chaos(defender) { data::table("skills", "ANTI_CHAOS_CUT").as_f64().unwrap_or(0.75) } else { 0.0 };
            let bal = if self.is_balanced(defender) { k("PATH_BALANCE_EDGE") } else { 0.0 };
            1.0 + (k("CHAOS_EDGE") - 1.0) * (1.0 - cut) * (1.0 - bal)
        } else {
            1.0
        }
    }

    fn chaos_raid(&mut self, world: u16) {
        let Some(cw) = self.chaos_world else { return };
        let raiders: Vec<Pid> = self.living_in(cw).into_iter().filter(|&i| !self.people[i as usize].is_lord && self.people[i as usize].process.is_none()).collect();
        let mut prey: Vec<Pid> = self.living_in(world).into_iter().filter(|&i| self.is_adult(i) && self.people[i as usize].process.is_none() && !self.people[i as usize].is_chaos()).collect();
        if raiders.is_empty() || prey.is_empty() {
            return;
        }
        let c = raiders[self.rng.below(raiders.len() as u64) as usize];
        prey.sort_by(|&a, &b| self.power(b).partial_cmp(&self.power(a)).unwrap().then(a.cmp(&b)));
        let v = prey[self.rng.below(prey.len().min(3) as u64) as usize];
        // ผู้บุกข้ามแดนไปปะทะ — ย้ายไปที่เดียวกันชั่วคราว
        let home = self.people[c as usize].place;
        let target_place = self.people[v as usize].place;
        let target_world = self.people[v as usize].world;
        self.move_to(c, target_place);
        self.people[c as usize].world = target_world;
        let (w, l, ratio) = self.clash(c, v);
        let (cn, vn) = (self.people[c as usize].name.clone(), self.people[v as usize].name.clone());
        if ratio >= self.cfg.death_margin && self.chance(0.5) {
            let killer = self.people[w as usize].name.clone();
            self.kill(l, Some(w), &format!("ถูก{}สังหารในศึกเผ่าโกลาหล", killer), false);
        } else {
            let q = &mut self.people[l as usize];
            q.injury = (q.injury + 0.3).min(1.0);
        }
        let loser = self.people[l as usize].name.clone();
        let wn = self.worlds[world as usize].name.clone();
        self.emit("โกลาหลบุก", Some(c), Some(v), if w == c { "ชนะ" } else { "ถูกขับไล่" }, format!("{}บุก{}ปะทะ{} — {}เป็นฝ่ายเสีย", cn, wn, vn, loser));
        if self.people[v as usize].alive && !self.people[v as usize].thrall && self.chance(k("CHAOS_THRALL_P")) && w == c {
            self.leave_sect(v);
            let p = &mut self.people[v as usize];
            p.thrall = true;
            p.blood = [0.0, 0.0, 0.0, 0.0, 1.0];
            self.emit("ตกเป็นทาสโกลาหล", Some(v), Some(c), "สวามิภักดิ์", format!("{}ยอมสวามิภักดิ์ต่อเผ่าโกลาหล — ได้รับการดูแล แต่เป็นทาสของมัน", vn));
        }
        if self.people[c as usize].alive {
            self.move_to(c, home);
            self.people[c as usize].world = cw;
        }
    }

    /// ดิ่งลงโลกมนุษย์ตรงๆ ผ่านรูหนอน — ถล่มสถานที่ขั้นสูง ขยายรอยแยก
    fn chaos_invade(&mut self, world: u16) {
        let Some(cw) = self.chaos_world else { return };
        let cap = (self.worlds[world as usize].rift / k("RIFT_RANK_PER")) as i8 + 1;
        let pool: Vec<Pid> = self.living_in(cw).into_iter().filter(|&i| !self.people[i as usize].is_lord && self.people[i as usize].process.is_none()).collect();
        let raiders: Vec<Pid> = { let r: Vec<Pid> = pool.iter().copied().filter(|&i| self.people[i as usize].chaos_rank <= cap).collect(); if r.is_empty() { pool } else { r } };
        let Some(c) = self.pick(&raiders) else { return };
        let d = data::world();
        let day = self.day;
        let ruined: Vec<u32> = self.worlds[world as usize].ruined.iter().map(|&(p, _)| p).collect();
        let mut cands: Vec<u32> = self.worlds[world as usize].places.iter().copied().filter(|&p| d.places[p as usize].grade == 2 && !ruined.contains(&p)).collect();
        if cands.is_empty() {
            cands = self.worlds[world as usize].places.iter().copied().filter(|p| !ruined.contains(p)).collect();
        }
        let Some(spot) = self.pick(&cands) else { return };
        let cn = self.people[c as usize].name.clone();
        let spot_name = self.place_name(spot);
        if self.worlds[world as usize].defense > 0.0 && self.chance(0.75) {
            let w = &mut self.worlds[world as usize];
            w.defense = (w.defense - 20.0).max(0.0);
            self.emit_at("โกลาหลบุกโลกมนุษย์", world, spot, "ถูกสกัดกั้น", format!("ค่ายกลป้องกันโลกทำงาน สกัด{}ไว้ได้ทัน", cn));
            return;
        }
        let defenders: Vec<Pid> = self.present_at(spot).into_iter().filter(|&x| self.is_adult(x)).collect();
        if let Some(&v) = defenders.iter().max_by(|&&a, &&b| self.power(a).partial_cmp(&self.power(b)).unwrap().then(b.cmp(&a))) {
            let home = self.people[c as usize].place;
            self.move_to(c, spot);
            self.people[c as usize].world = world;
            let (w, l, ratio) = self.clash(c, v);
            let vn = self.people[v as usize].name.clone();
            if w == v {
                if ratio >= self.cfg.death_margin && self.chance(0.4) {
                    self.kill(c, Some(v), &format!("ถูก{}สังหารขณะบุกโลกมนุษย์", vn), false);
                }
                let wr = &mut self.worlds[world as usize];
                wr.rift = (wr.rift - k("RIFT_GROWTH")).max(0.0);
                self.emit("โกลาหลบุกโลกมนุษย์", Some(c), Some(v), "ถูกขับไล่", format!("{}ทะลุรูหนอนลงมาถล่ม{} แต่ถูก{}ขับไล่กลับไป", cn, spot_name, vn));
                if self.people[c as usize].alive {
                    self.move_to(c, home);
                    self.people[c as usize].world = cw;
                }
                return;
            }
            let _ = l;
            self.move_to(c, home);
            self.people[c as usize].world = cw;
        }
        let until = day + k("RUIN_YEARS") as i64 * 365;
        self.worlds[world as usize].ruined.push((spot, until));
        // กลืนกินวัตถุดิบ แล้วคนในที่นั้นแตกกระสานซ่านเซ็น
        let here: Vec<Pid> = self.at[spot as usize].iter().copied().collect();
        let places = self.worlds[world as usize].places.clone();
        for x in here {
            self.people[x as usize].mats = [0.0; 3];
            if self.people[x as usize].process.is_none() {
                let to = places[self.rng.below(places.len() as u64) as usize];
                self.move_to(x, to);
            }
        }
        self.places[spot as usize].stock = [0.0; 3];
        let w = &mut self.worlds[world as usize];
        w.rift += k("RIFT_GROWTH");
        w.heaven = (w.heaven - 20.0).max(0.0);
        self.emit_at("โกลาหลบุกโลกมนุษย์", world, spot, "ทำลายสำเร็จ", format!("{}ทะลุรูหนอนลงมาถล่ม{}จนราบ รอยแยกในโลกมนุษย์กว้างขึ้น", cn, spot_name));
    }

    // ------------------------------------------------------------------ ศึกพันธมิตร / ผนึก
    fn coalition_strike(&mut self, world: u16) {
        let Some(lord) = self.lord else { return };
        let Some(cw) = self.chaos_world else { return };
        if self.people[lord as usize].dissolved() {
            self.seal_rift(world);
            return;
        }
        let lord_power = self.power(lord);
        let floor = lord_power * k("COALITION_MIN_SHARE");
        let mut pool: Vec<(f64, Pid)> = self
            .alive
            .iter()
            .copied()
            .filter(|&i| {
                let p = &self.people[i as usize];
                !p.is_chaos() && !p.thrall && p.process.is_none() && p.cultivator
            })
            .map(|i| (self.power(i), i))
            .filter(|&(s, _)| s >= floor)
            .collect();
        if pool.len() < k("COALITION_MIN") as usize {
            self.worlds[world as usize].last_coalition = self.day - k("COALITION_COOLDOWN") as i64 + k("COALITION_FAIL_COOLDOWN") as i64;
            return;
        }
        pool.sort_by(|a, b| b.0.partial_cmp(&a.0).unwrap().then(a.1.cmp(&b.1)));
        pool.truncate(k("COALITION_SIZE") as usize);
        let team: Vec<Pid> = pool.iter().map(|&(_, c)| c).collect();
        let anti = team.iter().filter(|&&c| self.has_anti_chaos(c)).count();
        let mut team_power: f64 = pool.iter().enumerate().map(|(i, &(s, _))| s * k("COALITION_FALLOFF").powi(i as i32)).sum();
        team_power += k("COALITION_ANTI_BONUS") * anti as f64;
        team_power *= 1.0 + k("COALITION_UNITY") * (team.len() as f64 - k("COALITION_MIN")).max(0.0);
        let mut home = lord_power * k("COALITION_HOME_EDGE");
        if team.iter().any(|&c| self.holds_anti_chaos_treasure(c)) {
            home *= 1.0 - data::table("treasures", "ANTI_CHAOS_HOME_CUT").as_f64().unwrap_or(0.5);
        }
        let adv = team_power - home;
        let margin = adv.abs() / home.max(1.0);
        let won = self.chance(physics::logistic(adv / k("TEMP").max(1.0) / 10.0));
        self.worlds[world as usize].last_coalition = self.day;
        let leader = team[0];
        let names: Vec<String> = team.iter().map(|&c| self.people[c as usize].name.clone()).collect();
        let (ln, lordn) = (self.people[leader as usize].name.clone(), self.people[lord as usize].name.clone());
        if won {
            for &c in &team[1..] {
                if self.chance((0.45 - margin).max(0.0)) && self.people[c as usize].fate <= 0 {
                    self.kill(c, Some(lord), &format!("สละชีพในศึกปราบ{}", lordn), false);
                }
            }
            for &c in &team {
                if self.people[c as usize].alive {
                    self.people[c as usize].insight += 10.0;
                }
            }
            self.worlds[world as usize].rift = 0.0;
            self.emit("พันธมิตรปราบเจ้าโกลาหล", Some(leader), Some(lord), "ปราบสำเร็จ", format!("{} ผู้แกร่ง ({}) นำโดย{} บุกห้วงโกลาหลปราบ{}จนสลาย รอยแยกปิดสนิท", team.len(), names.join(" · "), ln, lordn));
            self.kill(lord, Some(leader), "ถูกพันธมิตรข้ามแดนปราบ", false);
        } else {
            for &c in &team {
                if self.chance(k("COALITION_CASUALTY")) && self.people[c as usize].fate <= 0 {
                    self.kill(c, Some(lord), &format!("ดับสูญในห้วงโกลาหลด้วยน้ำมือ{}", lordn), false);
                } else if self.people[c as usize].alive {
                    let p = &mut self.people[c as usize];
                    p.decay += 2.0;
                    p.near_death += 1;
                    p.injury = (p.injury + 0.4).min(1.0);
                }
            }
            self.worlds[world as usize].rift += k("RIFT_GROWTH");
            self.emit("พันธมิตรปราบเจ้าโกลาหล", Some(leader), Some(lord), "พ่ายแพ้", format!("{} ผู้แกร่งนำโดย{} บุกห้วงโกลาหล แต่ถูก{}บดขยี้ รอยแยกยิ่งกว้าง", team.len(), ln, lordn));
        }
        let _ = cw;
    }

    fn seal_rift(&mut self, world: u16) {
        if self.worlds[world as usize].rift <= 0.0 {
            return;
        }
        let mut crew: Vec<(f64, Pid)> = self
            .alive
            .iter()
            .copied()
            .filter(|&i| !self.people[i as usize].is_chaos() && self.people[i as usize].process.is_none())
            .map(|i| (self.sealer_skill(i), i))
            .filter(|&(s, _)| s > 0.0)
            .collect();
        if crew.len() < k("COALITION_MIN") as usize {
            return;
        }
        crew.sort_by(|a, b| b.0.partial_cmp(&a.0).unwrap().then(a.1.cmp(&b.1)));
        crew.truncate(k("COALITION_SIZE") as usize);
        self.worlds[world as usize].last_coalition = self.day;
        let before = self.worlds[world as usize].rift;
        let closed = before.min(k("SEAL_PER_CREW") * crew.len() as f64);
        self.worlds[world as usize].rift = before - closed;
        for &(_, c) in &crew[1..] {
            if self.chance(k("SEAL_DEATH_P")) && self.people[c as usize].fate <= 0 {
                self.kill(c, None, "ถูกรอยแยกโกลาหลกลืนหาย", false);
            }
        }
        let lead = crew[0].1;
        let n = self.people[lead as usize].name.clone();
        self.emit("ปิดรอยแยก", Some(lead), None, "ปิดได้บางส่วน", format!("{} ผู้ชำนาญมิติและค่ายกลนำโดย{} ปิดรอยแยกได้ {:.1} (เหลือ {:.1})", crew.len(), n, closed, before - closed));
    }

    fn seal_lord(&mut self) {
        let Some(lord) = self.lord else { return };
        if !self.people[lord as usize].dissolved() || self.lord_seal > 0.0 {
            return;
        }
        // ผู้ออกทุน: แดนที่คลังทรัพยากรหนาที่สุดและจ่ายไหว (ใช้ปราณฟ้าของแดนเป็นทรัพยากร)
        let cost = k("LORD_SEAL_COST") * (1.0 + k("LORD_SEAL_COST_GROWTH") * self.lord_seals_made as f64) * 0.1;
        let funder = (0..self.worlds.len()).filter(|&w| self.worlds[w].heaven - cost > self.worlds[w].cap * 0.3).max_by(|&a, &b| self.worlds[a].heaven.partial_cmp(&self.worlds[b].heaven).unwrap());
        let Some(funder) = funder else { return };
        let mut crew: Vec<(f64, Pid)> = self
            .alive
            .iter()
            .copied()
            .filter(|&i| !self.people[i as usize].is_chaos() && !self.people[i as usize].thrall && self.people[i as usize].process.is_none() && self.people[i as usize].cultivator)
            .map(|i| (self.power(i), i))
            .collect();
        if crew.len() < k("LORD_SEAL_MIN") as usize {
            return;
        }
        crew.sort_by(|a, b| b.0.partial_cmp(&a.0).unwrap().then(a.1.cmp(&b.1)));
        crew.truncate(k("LORD_SEAL_SIZE") as usize);
        let team_power: f64 = crew.iter().map(|&(s, _)| s).sum();
        self.worlds[funder].heaven -= cost;
        self.lord_seal = (k("LORD_SEAL_POWER_W") * team_power).min(100.0);
        self.lord_seals_made += 1;
        self.lord_seal_last = self.day;
        let lead = crew[0].1;
        let (n, fname) = (self.people[lead as usize].name.clone(), self.worlds[funder].name.clone());
        self.emit("ผนึกเจ้าโกลาหล", Some(lead), Some(lord), "ผนึกสำเร็จ", format!("{} ผู้บำเพ็ญนำโดย{} ลงมหาผนึกตรึงเจ้าโกลาหลขณะสลาย ({}ออกทุนปราณ {:.0}) แลกด้วยชีวิตผู้ยืนกลางผนึก", crew.len(), n, fname, cost));
        let mut fallen: Vec<Pid> = crew.iter().take(k("LORD_SEAL_SACRIFICE") as usize).map(|&(_, c)| c).collect();
        for &(_, c) in crew.iter().skip(k("LORD_SEAL_SACRIFICE") as usize) {
            if self.chance(k("LORD_SEAL_EXTRA_DEATH_P")) {
                fallen.push(c);
            }
        }
        for c in fallen {
            self.kill(c, None, "สละชีวิตลงมหาผนึกตรึงเจ้าโกลาหล", false);
        }
    }

    // ------------------------------------------------------------------ เกณฑ์ขึ้นฟ้า
    fn conscript(&mut self, world: u16) {
        let Some(up) = self.worlds[world as usize].up else { return };
        let bar = k("CONSCRIPT_REALM_BAR") as u8;
        let pool: Vec<Pid> = self
            .living_in(world)
            .into_iter()
            .filter(|&i| {
                let p = &self.people[i as usize];
                p.sentient && p.process.is_none() && p.realm >= bar && p.age(self.day) >= k("CONSCRIPT_MIN_AGE")
            })
            .collect();
        let Some(&taken) = pool.iter().max_by_key(|&&i| (self.people[i as usize].realm, std::cmp::Reverse(i))) else { return };
        let tr = self.people[taken as usize].realm;
        let envoy = self.living_in(up).into_iter().filter(|&i| self.people[i as usize].realm > tr && self.people[i as usize].sentient).max_by_key(|&i| (self.people[i as usize].realm, std::cmp::Reverse(i)));
        let p = &self.people[taken as usize];
        let mut kin: Vec<Pid> = p.children.clone();
        kin.extend(p.parents.iter().flatten());
        kin.extend(p.spouse);
        kin.extend(p.master);
        kin.retain(|&c| self.people[c as usize].alive);
        if let Some(e) = envoy {
            for &c in &kin {
                *self.people[c as usize].rivals.entry(e).or_insert(0) += k("CONSCRIPT_KIN_GRUDGE") as i16;
            }
        }
        let w = &mut self.worlds[world as usize];
        w.resentment = (w.resentment + k("CONSCRIPT_RESENT")).min(k("RESENT_CAP"));
        let places = self.worlds[up as usize].places.clone();
        let dest = places[self.rng.below(places.len() as u64) as usize];
        self.leave_sect(taken);
        self.move_to(taken, dest);
        let utier = self.worlds[up as usize].tier;
        self.people[taken as usize].world = up;
        self.release_office(taken);
        let p = &mut self.people[taken as usize];
        p.peak_tier = p.peak_tier.max(utier);
        if p.spouse.is_some() {
            // คู่ครองที่ถูกทิ้งไว้ข้างล่าง
        }
        let (tn, un) = (p.name.clone(), self.worlds[up as usize].name.clone());
        self.emit("เกณฑ์ขึ้นฟ้า", envoy.or(Some(taken)), Some(taken), "ถูกเกณฑ์", format!("ทูตจาก{}ลงมาเอาตัว{}ขึ้นฟ้าไป ไม่มีใครได้รับคำอธิบายว่าเพื่ออะไร", un, tn));
    }

    /// สงครามเบิกฟ้า — ทุบค่ายกลปิดแดนบน
    pub fn heaven_war(&mut self, id: Pid) -> i64 {
        let w = self.people[id as usize].world as usize;
        let Some(up) = self.worlds[w].up else { return self.range(30, 90) };
        let up = up as usize;
        let n = self.people[id as usize].name.clone();
        if !self.worlds[up].closed {
            return self.range(30, 90);
        }
        let dmg = (self.people[id as usize].realm % self.cfg.realm_band) as f64 * 5.0;
        self.worlds[up].defense = (self.worlds[up].defense - dmg).max(0.0);
        if self.worlds[up].defense <= 0.0 {
            self.worlds[up].closed = false;
            self.emit("สงครามเบิกฟ้า", Some(id), None, "เปิดสวรรค์", format!("{}ทำลายค่ายกล{}สำเร็จ ประตูสวรรค์เปิดออก", n, self.worlds[up].name));
        } else if self.chance(0.3) {
            self.kill(id, None, "ถูกทัณฑ์สวรรค์สังหารระหว่างทำสงครามเบิกฟ้า", false);
            return 0;
        } else {
            let left = self.worlds[up].defense;
            self.emit("สงครามเบิกฟ้า", Some(id), None, "โจมตีสวรรค์", format!("{}นำทัพโจมตีค่ายกลสวรรค์ ค่ายกลเหลือ {:.0}", n, left));
        }
        self.range(400, 1500)
    }
}
