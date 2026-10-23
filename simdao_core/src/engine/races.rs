//! เผ่าและสายเลือด จิตมาร หนี้ใจ คำสัญญา — และเผ่าโกลาหล
//!
//! สายเลือดห้าสาย (มนุษย์ วิญญาณ อสูร มาร โกลาหล) กำหนดว่าคนเติบโตทางไหนได้ดี:
//! มนุษย์บำเพ็ญความเข้าใจ วิญญาณขัดเกลาสายเลือด อสูรแข็งแรงโดยกำเนิด มารได้พลังจากจิตมาร
//! ยิ่งเลือดผสม แต่ละทางยิ่งทำงานได้ไม่เต็ม (Person::eff)

use super::data;
use super::model::*;
use super::sim::Engine;
use crate::physics;

impl Engine {
    /// ป้ายเผ่าที่อ่านง่าย คำนวณจากสัดส่วนสายเลือด
    pub fn race(&self, id: Pid) -> String {
        let p = &self.people[id as usize];
        if p.is_chaos() {
            return "เผ่าโกลาหล".into();
        }
        if p.thrall {
            return "ทาสโกลาหล".into();
        }
        let th = ["มนุษย์", "วิญญาณ", "อสูร", "มาร", "โกลาหล"];
        let top = p.top_blood();
        if p.blood[top] >= data::k("BLOOD_RACE_AT") as f32 {
            return ["มนุษย์", "สัตว์วิญญาณ", "อสูร", "มารแท้", "เลือดโกลาหล"][top].into();
        }
        if p.blood[MARA] >= 0.3 && p.blood[HUMAN] >= 0.3 {
            return "มนุษย์มาร".into();
        }
        if top == HUMAN {
            let second = (1..5).max_by(|&a, &b| p.blood[a].partial_cmp(&p.blood[b]).unwrap()).unwrap();
            return format!("มนุษย์ผสม{}", th[second]);
        }
        format!("{}ผสม", th[top])
    }

    /// ชื่อขั้นตามเผ่า — อสูร มาร โกลาหล มีบันไดของตัวเอง
    pub fn title(&self, id: Pid) -> String {
        let p = &self.people[id as usize];
        let band = self.cfg.realm_band;
        let pick = |name: &str, i: usize| {
            let v = data::strs(data::table("config", name));
            v[i.min(v.len() - 1)].clone()
        };
        if p.is_lord {
            return "เจ้าโกลาหล".into();
        }
        if p.is_chaos() {
            return pick("CHAOS_RANKS", p.chaos_rank as usize);
        }
        if p.blood[MARA] >= data::k("BLOOD_RACE_AT") as f32 {
            return pick("MARA_RANKS", (p.realm % band) as usize);
        }
        if p.blood[DEMON] >= data::k("BLOOD_RACE_AT") as f32 {
            return format!("{}{}", p.unique_title, pick("BEAST_RANKS", (p.realm % band) as usize));
        }
        self.realm_name(p.realm)
    }

    /// มนุษย์มาร — เป็นที่รังเกียจของมนุษย์ทุกคน
    pub fn hated(&self, id: Pid) -> bool {
        let p = &self.people[id as usize];
        p.blood[MARA] >= data::k("MARA_HATE_BLOOD") as f32 && p.blood[HUMAN] >= 0.25
    }

    /// พลังจากสายเลือด: วิญญาณ (ตามการขัดเกลา) อสูร มาร (ตามจิตมาร)
    pub fn blood_power(&self, id: Pid) -> f64 {
        let p = &self.people[id as usize];
        let b = |i: usize| p.blood[i] as f64;
        b(SPIRIT) * data::k("SPIRIT_BASE_W") * (0.4 + 0.6 * p.refine.min(1.0))
            + b(DEMON) * data::k("DEMON_BASE_W")
            + b(MARA) * data::k("MARA_BASE_W") * (1.0 + p.inner.min(6.0) * 0.10)
    }

    /// พรจากผู้ถึงยอดบันไดที่ยังมีชีวิตในสายเลือดเดียวกัน (ใช้อันที่แรงที่สุด ไม่ทบ)
    pub fn bloodline_buff(&self, id: Pid) -> f64 {
        let p = &self.people[id as usize];
        let mut best = 0.0f64;
        for (&line, &(giver, strength)) in &self.apex {
            if giver != id && p.blood[line as usize] > 0.0 && self.people[giver as usize].alive {
                best = best.max((strength * p.affinity[line as usize]) as f64);
            }
        }
        best.min(data::k("BLOODLINE_BLESS_CAP"))
    }

    /// คนที่ถึงขั้นสูงสุดของจักรวาลให้พรแก่สายเลือดของตน
    pub fn check_apex(&mut self, id: Pid) {
        let p = &self.people[id as usize];
        if (p.realm as f64) < data::k("REALM_TOP") {
            return;
        }
        let line = p.top_blood() as u8;
        let s = (data::k("BLOODLINE_BLESS_MIN") + self.rng.next_f64() * (data::k("BLOODLINE_BLESS_MAX") - data::k("BLOODLINE_BLESS_MIN"))) as f32;
        let replace = match self.apex.get(&line) {
            Some(&(g, old)) => !self.people[g as usize].alive || s > old,
            None => true,
        };
        if replace {
            self.apex.insert(line, (id, s));
            let n = self.people[id as usize].name.clone();
            self.emit("พรสายเลือด", Some(id), None, "ให้พร", format!("{}ถึงยอดบันไดฟ้า ผู้สืบสายเลือดเดียวกันทั่วจักรวาลได้รับพร", n));
        }
    }

    // ------------------------------------------------------------------ จิตมารและหนี้ใจ
    pub fn add_debt(&mut self, id: Pid, kind: &str, target: Pid) {
        let w = data::table("config", "DEBT_WEIGHT")[kind].as_f64().unwrap_or(1.0);
        let day = self.day;
        let p = &mut self.people[id as usize];
        if p.inner_none || !p.alive {
            return;
        }
        p.debts.push(Debt { kind: kind.into(), target, day, done: false });
        p.inner += w;
        if p.debts.len() > 40 {
            p.debts.retain(|d| !d.done);
            if p.debts.len() > 40 {
                p.debts.remove(0);
            }
        }
    }

    /// สะสางเรื่องค้างคากับคนคนหนึ่ง — จิตมารคลาย
    pub fn settle_debts(&mut self, id: Pid, target: Pid) -> bool {
        let table = data::table("config", "DEBT_WEIGHT");
        let p = &mut self.people[id as usize];
        let mut found = false;
        for d in p.debts.iter_mut().filter(|d| !d.done && d.target == target) {
            d.done = true;
            p.inner = (p.inner - table[d.kind.as_str()].as_f64().unwrap_or(1.0)).max(0.0);
            found = true;
        }
        found
    }

    /// ด่านจิตมาร (หลังผ่านด่านพลังของการข้ามขั้น) — ผ่าน / กดไว้ / พ่าย
    pub fn inner_trial(&mut self, id: Pid) -> &'static str {
        let p = &self.people[id as usize];
        if p.inner_none {
            return "ไร้จิตมาร";
        }
        let mut strength = p.inner * data::k("INNER_TRIAL_W") + data::k("INNER_PER_REALM") * (p.realm % self.cfg.realm_band) as f64;
        if p.inner_art {
            strength *= data::k("INNER_ART_RISK");
        }
        let resist = p.insight + p.refine * 2.0 + 2.0;
        let pass = resist / (resist + strength);
        let r = self.rng.next_f64();
        if r < pass {
            "ผ่าน"
        } else if r < pass + (1.0 - pass) * 0.55 {
            "กดไว้"
        } else {
            "พ่าย"
        }
    }

    pub fn refine_blood(&mut self, id: Pid) -> i64 {
        let gap = self.range(200, 700);
        let p = &mut self.people[id as usize];
        let ceiling = p.blood[SPIRIT] as f64;
        p.refine = (p.refine + 0.18 * (gap as f64 / 365.0).min(4.0) * p.eff(SPIRIT)).min(ceiling);
        gap
    }

    // ------------------------------------------------------------------ คำสัญญาและการทรยศ
    pub fn promise(&mut self, a: Pid, b: Pid) -> i64 {
        for (x, y) in [(a, b), (b, a)] {
            let v = self.people[x as usize].bonds.entry(y).or_insert(0);
            *v = (*v + 2).min(10);
        }
        let (an, bn) = (self.people[a as usize].name.clone(), self.people[b as usize].name.clone());
        let oath = self.oath_form(a);
        self.emit("ให้สัญญา", Some(a), Some(b), "ให้สัญญา", format!("{}ให้คำมั่นกับ{} — {}", an, bn, oath));
        self.range(10, 60)
    }

    pub fn oath_form(&self, id: Pid) -> &'static str {
        let p = &self.people[id as usize];
        let race = self.race(id);
        if race == "เผ่าโกลาหล" || race == "ทาสโกลาหล" {
            "ให้คำสัตย์ต่อจิตโกลาหล"
        } else if p.blood[MARA] >= 0.3 {
            "สาบานต่อจิตมาร"
        } else if p.blood[DEMON] >= 0.5 {
            "ให้คำสัตย์ต่อจิตอสูร"
        } else if p.blood[SPIRIT] >= 0.9 {
            "ให้คำสัตย์ต่อจิตวิญญาณบรรพกาล"
        } else if p.cultivator {
            "สาบานต่อจิตเต๋า"
        } else {
            "สาบานต่อฟ้าดิน"
        }
    }

    /// หักหลังคนที่ไว้ใจ — ชิงทรัพย์ แล้วแบกหนี้ทรยศไว้ในใจ
    pub fn betray(&mut self, a: Pid, b: Pid) -> i64 {
        let take = self.people[b as usize].gold * 0.5;
        self.people[b as usize].gold -= take;
        self.people[a as usize].gold += take;
        self.people[a as usize].bonds.remove(&b);
        self.people[b as usize].bonds.remove(&a);
        *self.people[b as usize].rivals.entry(a).or_insert(0) += 4;
        self.add_debt(a, "ทรยศ", b);
        let (an, bn) = (self.people[a as usize].name.clone(), self.people[b as usize].name.clone());
        self.emit("ทรยศ", Some(a), Some(b), "ทรยศ", format!("{}หักหลัง{} ชิงทรัพย์ {:.0} ตำลึงแล้วหนีไป", an, bn, take));
        self.range(20, 90)
    }

    /// สะสางเรื่องเก่า — ไปขอขมา ชดใช้ หรือตอบแทนบุญคุณ
    pub fn settle(&mut self, a: Pid, b: Pid) -> i64 {
        if self.settle_debts(a, b) {
            let gift = (self.people[a as usize].gold * 0.2).min(30.0);
            self.people[a as usize].gold -= gift;
            self.people[b as usize].gold += gift;
            self.people[b as usize].rivals.remove(&a);
            *self.people[b as usize].bonds.entry(a).or_insert(0) += 1;
            let (an, bn) = (self.people[a as usize].name.clone(), self.people[b as usize].name.clone());
            self.emit("สะสางเรื่องเก่า", Some(a), Some(b), "สะสาง", format!("{}ไปสะสางเรื่องค้างคาใจกับ{} จิตใจปลอดโปร่งขึ้น", an, bn));
        }
        self.range(10, 40)
    }

    // ------------------------------------------------------------------ ตกเป็นมาร / บัญชาสวรรค์
    /// คนที่ทะเยอทะยานเกินตัวหรือกรรมหนักอาจถูกจิตมารครอบงำ
    pub fn tick_temptation(&mut self, days: f64) {
        let p_year = data::k("DEMON_TEMPTATION_PER_YEAR");
        let ids: Vec<Pid> = self.alive.iter().copied().collect();
        for id in ids {
            let p = &self.people[id as usize];
            if p.fallen || p.is_chaos() || !self.is_adult(id) || p.blood[SPIRIT] >= 0.9 || p.inner_none {
                continue;
            }
            if !(p.inner > 8.0 || p.ambition > 0.92) {
                continue;
            }
            if !self.chance(physics::hazard_p(p_year * 0.05, days)) {
                continue;
            }
            self.leave_sect(id);
            let p = &mut self.people[id as usize];
            p.fallen = true;
            p.blood[MARA] += 0.3;
            let s: f32 = p.blood.iter().sum();
            for x in p.blood.iter_mut() {
                *x /= s;
            }
            let why = if p.inner > 8.0 { "กรรมหนัก" } else { "ทะเยอทะยานเกินตัว" };
            let n = p.name.clone();
            self.emit("มารสิงร่าง", Some(id), None, "ตกเป็นมาร", format!("{}ถูกจิตมารเข้าครอบงำเพราะ{} ละทิ้งสำนักเดิม กลายเป็นมาร", n, why));
        }
        // เผ่าวิญญาณศักดิ์สิทธิ์รับบัญชาสวรรค์ล่าผู้ตกเป็นมาร
        if self.chance(physics::hazard_p(data::k("CRUSADE_PER_YEAR") * 0.1, days)) {
            let spirits: Vec<Pid> = self.alive.iter().copied().filter(|&i| self.people[i as usize].blood[SPIRIT] >= 0.9 && self.is_adult(i) && self.people[i as usize].process.is_none()).collect();
            let demons: Vec<Pid> = self.alive.iter().copied().filter(|&i| self.people[i as usize].fallen && self.people[i as usize].process.is_none()).collect();
            if let (Some(h), Some(t)) = (self.pick(&spirits), self.pick(&demons)) {
                let (hn, tn) = (self.people[h as usize].name.clone(), self.people[t as usize].name.clone());
                let (w, l, ratio) = self.clash(h, t);
                if ratio >= self.cfg.death_margin {
                    let killer_name = self.people[w as usize].name.clone();
                    self.kill(l, Some(w), &format!("ถูก{}สังหารในศึกบัญชาสวรรค์", killer_name), false);
                } else {
                    let q = &mut self.people[l as usize];
                    q.injury = (q.injury + 0.4).min(1.0);
                }
                let outcome = if w == h { "สังหารมารสำเร็จ" } else { "มารหนีรอด" };
                self.emit("บัญชาสวรรค์", Some(h), Some(t), outcome, format!("{}แห่งเผ่าวิญญาณรับบัญชาสวรรค์ บุกปราบ{}ผู้ตกเป็นมาร", hn, tn));
            }
        }
    }

    // ------------------------------------------------------------------ เผ่าโกลาหล
    pub fn spawn_chaos_race(&mut self) {
        let Some(cw) = self.chaos_world else { return };
        let ranks = data::strs(data::table("config", "CHAOS_RANKS")).len() as i64;
        let cap = self.cfg.realm_cap_of_tier(self.worlds[cw as usize].tier);
        let n = data::k("CHAOS_POP") as usize;
        let mut ids = Vec::new();
        for _ in 0..n {
            let age = 200.0 + self.rng.next_f64() * 2800.0;
            let id = self.spawn(cw, None, age, [None, None]);
            let rank = ((self.rng.gauss() * 1.3).abs() as i64).clamp(0, ranks - 1) as i8;
            let p = &mut self.people[id as usize];
            p.chaos_rank = rank;
            p.blood = [0.0, 0.0, 0.0, 0.0, 1.0];
            p.inner_none = true;
            p.cultivator = true;
            p.realm = cap;
            p.peak_realm = cap;
            p.lifespan = 1e9; // เผ่าโกลาหลไม่มีอายุขัย
            ids.push(id);
        }
        if let Some(&lord) = ids.iter().max_by_key(|&&i| (self.people[i as usize].chaos_rank, std::cmp::Reverse(i))) {
            let p = &mut self.people[lord as usize];
            p.is_lord = true;
            p.chaos_rank = (ranks - 1) as i8;
            self.lord = Some(lord);
        }
    }

    /// เจ้าโกลาหลไม่ตาย — ร่างสลายกลับเป็นความโกลาหล แล้วก่อร่างใหม่จากพลังความตายทั่วจักรวาล
    pub fn lord_dissolves(&mut self, id: Pid, killer: Option<Pid>, cause: &str) {
        if self.people[id as usize].dissolved() {
            return;
        }
        let p = &mut self.people[id as usize];
        p.process = Some(Process::Dissolved);
        p.decay = 0.0;
        p.injury = 0.0;
        self.lord_pool = 0.0;
        let place = p.place;
        self.at[place as usize].remove(&id);
        let n = p.name.clone();
        let returns = p.lord_returns;
        let who = killer.map(|k| self.people[k as usize].name.clone()).unwrap_or_else(|| "ไม่ปรากฏ".into());
        self.emit("เจ้าโกลาหลสลาย", Some(id), killer, "สลายเป็นโกลาหล", format!("{}ถูก{}สังหารจนร่างสลาย ({}) — สลายมาแล้ว {} ครั้ง จะก่อร่างใหม่เมื่อสะสมพลังจากความตายครบ", n, who, cause, returns));
        self.schedule(id, 365);
    }

    /// พลังความตายไหลไปหาเจ้าโกลาหลที่สลายอยู่ (ถ้าไม่ถูกผนึก)
    pub fn feed_lord(&mut self, dead: Pid, natural: bool) {
        let Some(lord) = self.lord else { return };
        if !self.people[lord as usize].dissolved() || self.lord_seal > 0.0 {
            return;
        }
        let realm = (self.people[dead as usize].realm % self.cfg.realm_band) as f64;
        let mut gain = data::k("LORD_POOL_PER_DEATH") * (1.0 + data::k("LORD_POOL_PER_REALM") * realm);
        if !natural {
            gain *= data::k("LORD_POOL_VIOLENT_X");
        }
        self.lord_pool += gain;
    }

    /// เทิร์นของเจ้าโกลาหลที่สลายอยู่ — ก่อร่างใหม่เมื่อพลังครบ
    pub fn lord_turn(&mut self, id: Pid) {
        if self.lord_pool < data::k("LORD_POOL_TARGET") {
            self.schedule(id, 365);
            return;
        }
        let pool = self.lord_pool;
        self.lord_pool = 0.0;
        let p = &mut self.people[id as usize];
        p.process = None;
        p.lord_returns += 1;
        let place = p.place;
        self.at[place as usize].insert(id);
        let (n, r) = (p.name.clone(), p.lord_returns);
        self.emit("เจ้าโกลาหลคืนกลับ", Some(id), None, "ก่อร่างใหม่", format!("{}ก่อร่างขึ้นใหม่จากพลังความตาย {:.0} หน่วย แข็งแกร่งกว่าเดิม (ครั้งที่ {})", n, pool, r));
        let gap = self.range(30, 200);
        self.schedule(id, gap);
    }
}
