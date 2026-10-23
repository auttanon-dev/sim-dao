//! การปกครอง — คุณสมบัติ ตำแหน่ง การสืบทอด ฐานะทางการเมือง และวัฏจักรขึ้น-ลงของสำนัก
//!
//! กติกาเดียวใช้กับทุกคน (ไม่มีกฎพิเศษสำหรับผู้เล่น) และไม่สุ่ม — ผลขึ้นกับคน ความสัมพันธ์ และสถานะของหน่วยเท่านั้น
//! ข้อคงที่: ผู้ดำรงตำแหน่งต้องมีชีวิต อยู่แดนเดียวกับหน่วย และ Person.office ชี้กลับมาที่ตำแหน่งนั้นเสมอ
//! (ตรวจได้ด้วย check_polities)

use super::data::k;
use super::model::*;
use super::polity::*;
use super::sim::Engine;
use std::collections::BTreeMap;

/// ความชอบธรรมเริ่มต้นตามวิธีได้ตำแหน่ง
pub fn accession_legitimacy(how: Accession) -> f32 {
    match how {
        Accession::Founded | Accession::Mandated => 0.9,
        Accession::Inherited => 0.8,
        Accession::Elected => 0.75,
        Accession::Appointed | Accession::Migrated => 0.7,
        Accession::Prevailed => 0.6,
        Accession::Seized => 0.35,
    }
}

impl Engine {
    // ------------------------------------------------------------------ คุณสมบัติ
    /// คนนี้ดำรงตำแหน่งที่ idx ของหน่วย pol ได้หรือไม่ (ผู้ที่ถือตำแหน่งรองในหน่วยเดียวกันเลื่อนขึ้นได้)
    pub fn eligible(&self, pol: PolId, idx: usize, id: Pid) -> bool {
        let p = &self.people[id as usize];
        let g = &self.polities[pol as usize];
        if !p.alive || !g.alive() || p.world != g.world || !self.is_adult(id) {
            return false;
        }
        if p.chaos_rank >= 0 || p.thrall || p.is_lord || !p.sentient || matches!(p.process, Some(Process::Dissolved)) {
            return false;
        }
        match p.office {
            Some((op, oi)) if op == pol && oi as usize >= idx => {}
            Some(_) => return false,
            None => {}
        }
        match g.kind {
            PolityKind::Sect => p.sect == Some(pol) && p.cultivator && (idx == 0 || (p.realm % self.cfg.realm_band) as f64 >= k("ORG_INNER_REALM")),
            PolityKind::City => g.succession == Succession::Strength || !self.is_criminal(id),
            _ => true,
        }
    }

    /// ผู้ดำรงตำแหน่งยังถือตำแหน่งได้ต่อหรือไม่ (เกณฑ์ขั้นต่ำ — การถอดถอนเพราะความประพฤติเป็นเรื่องการเมือง ระยะ P5)
    fn holds_validly(&self, pol: PolId, idx: usize, id: Pid) -> bool {
        let p = &self.people[id as usize];
        let g = &self.polities[pol as usize];
        p.alive && g.alive() && p.world == g.world && p.office == Some((pol, idx as u8)) && (g.kind != PolityKind::Sect || p.sect == Some(pol))
    }

    fn candidates(&self, pol: PolId, idx: usize) -> Vec<Pid> {
        let g = &self.polities[pol as usize];
        let mut c: Vec<Pid> = match g.kind {
            PolityKind::Sect => g.members.clone(),
            _ => {
                let mut v = self.present_at(g.seat);
                v.extend(g.holders().map(|(_, h)| h));
                v
            }
        };
        c.sort_unstable();
        c.dedup();
        c.retain(|&i| self.eligible(pol, idx, i));
        c
    }

    fn strongest(&self, c: &[Pid]) -> Option<Pid> {
        c.iter().copied().max_by(|&a, &b| self.power(a).partial_cmp(&self.power(b)).unwrap().then(b.cmp(&a)))
    }

    /// ผู้ลงคะแนน (ผู้ดำรงตำแหน่งรอง) เลือกคนที่ตัวเองเห็นว่าดีที่สุด: ขั้น ความผูกพัน บุญ หักความแค้น
    fn council_pick(&self, pol: PolId, cands: &[Pid]) -> Option<Pid> {
        let electors: Vec<Pid> = self.polities[pol as usize].holders().filter(|&(i, _)| i > 0).map(|(_, h)| h).filter(|&h| self.people[h as usize].alive).collect();
        if electors.is_empty() || cands.is_empty() {
            return None;
        }
        let mut tally: BTreeMap<Pid, u32> = BTreeMap::new();
        for &e in &electors {
            let ep = &self.people[e as usize];
            let score = |c: Pid| {
                let q = &self.people[c as usize];
                q.realm as f64 + ep.bonds.get(&c).copied().unwrap_or(0) as f64 / 5.0 - ep.rivals.get(&c).copied().unwrap_or(0) as f64 / 3.0 + q.merit as f64 / 200.0
            };
            if let Some(best) = cands.iter().copied().max_by(|&a, &b| score(a).partial_cmp(&score(b)).unwrap().then(b.cmp(&a))) {
                *tally.entry(best).or_insert(0) += 1;
            }
        }
        tally.into_iter().max_by(|a, b| a.1.cmp(&b.1).then(self.people[a.0 as usize].realm.cmp(&self.people[b.0 as usize].realm)).then(b.0.cmp(&a.0))).map(|(c, _)| c)
    }

    /// ทายาท: บุตรที่มีคุณสมบัติซึ่งเกิดก่อน (id น้อยกว่า = เกิดก่อน)
    fn heir(&self, pol: PolId, prev: Option<Pid>) -> Option<Pid> {
        let prev = prev?;
        let mut kids = self.people[prev as usize].children.clone();
        kids.sort_unstable();
        kids.into_iter().find(|&c| self.eligible(pol, 0, c))
    }

    /// ผู้สืบทอดตามกฎของหน่วย (กฎที่ใช้ไม่ได้จะตกไปใช้กฎถัดไป จนถึงกำลัง)
    pub fn choose_successor(&self, pol: PolId, prev: Option<Pid>) -> Option<(Pid, Accession)> {
        let g = &self.polities[pol as usize];
        let cands = self.candidates(pol, 0);
        let mut rule = g.succession;
        loop {
            match rule {
                Succession::Heredity => match self.heir(pol, prev) {
                    Some(h) => return Some((h, Accession::Inherited)),
                    None => rule = Succession::Council,
                },
                Succession::Appointment => {
                    let lord = g.parent.filter(|&p| self.polities[p as usize].alive()).and_then(|p| self.polities[p as usize].head());
                    match lord {
                        Some(l) if !cands.is_empty() => {
                            let lp = &self.people[l as usize];
                            let pick = cands.iter().copied().filter(|&c| c != l).max_by(|&a, &b| {
                                let s = |c: Pid| lp.bonds.get(&c).copied().unwrap_or(0) as f64 + self.power(c).ln_1p();
                                s(a).partial_cmp(&s(b)).unwrap().then(b.cmp(&a))
                            });
                            match pick {
                                Some(c) => return Some((c, Accession::Appointed)),
                                None => rule = Succession::Council,
                            }
                        }
                        _ => rule = Succession::Council,
                    }
                }
                Succession::Mandate => rule = Succession::Council,
                Succession::Council => match self.council_pick(pol, &cands) {
                    Some(c) => return Some((c, Accession::Elected)),
                    None => rule = Succession::Strength,
                },
                Succession::Strength => {
                    let how = if g.succession == Succession::Strength { Accession::Prevailed } else { Accession::Seized };
                    return self.strongest(&cands).map(|c| (c, how));
                }
            }
        }
    }

    // ------------------------------------------------------------------ แต่งตั้งและพ้นตำแหน่ง
    pub fn install(&mut self, pol: PolId, idx: usize, id: Pid, how: Accession) {
        if let Some((op, oi)) = self.people[id as usize].office {
            if self.polities[op as usize].offices.get(oi as usize).map_or(false, |o| o.holder == Some(id)) {
                self.polities[op as usize].offices[oi as usize].holder = None;
            }
        }
        let day = self.day;
        let o = &mut self.polities[pol as usize].offices[idx];
        o.holder = Some(id);
        o.since = day;
        o.how = how;
        self.people[id as usize].office = Some((pol, idx as u8));
        if idx == 0 {
            self.polities[pol as usize].standing.legitimacy = accession_legitimacy(how);
        }
    }

    /// ปลดออกจากตำแหน่ง (ไม่หาคนแทน) — คืนตำแหน่งที่ว่างลง
    pub fn vacate(&mut self, id: Pid) -> Option<(PolId, usize)> {
        let (pol, idx) = self.people[id as usize].office.take()?;
        let o = self.polities[pol as usize].offices.get_mut(idx as usize)?;
        if o.holder == Some(id) {
            o.holder = None;
        }
        Some((pol, idx as usize))
    }

    /// พ้นตำแหน่งแล้วหาคนแทนทันที (ตาย ย้ายแดน ออกจากสำนัก)
    pub fn release_office(&mut self, id: Pid) {
        if let Some((pol, idx)) = self.vacate(id) {
            self.fill_office(pol, idx, Some(id));
        }
    }

    pub fn fill_office(&mut self, pol: PolId, idx: usize, prev: Option<Pid>) {
        if !self.polities[pol as usize].alive() || idx >= self.polities[pol as usize].offices.len() || self.polities[pol as usize].offices[idx].holder.is_some() {
            return;
        }
        if idx == 0 {
            match self.choose_successor(pol, prev) {
                Some((n, how)) => {
                    let was = self.people[n as usize].office;
                    self.install(pol, 0, n, how);
                    self.announce_succession(pol, n, how);
                    if let Some((op, oi)) = was {
                        if op == pol && oi > 0 {
                            self.fill_office(pol, oi as usize, None);
                        }
                    }
                }
                None => {
                    if self.polities[pol as usize].kind == PolityKind::Sect {
                        self.dissolve_sect(pol, "ไร้ผู้สืบทอด");
                    } else if prev.is_some() {
                        self.polities[pol as usize].standing.legitimacy = 0.0;
                        let (n, t) = (self.polities[pol as usize].name.clone(), self.polities[pol as usize].title().to_string());
                        let (w, s) = (self.polities[pol as usize].world, self.polities[pol as usize].seat);
                        self.emit_at("ว่างผู้นำ", w, s, "ว่างผู้นำ", format!("{}ไร้{} — ยังไม่มีผู้ใดมีคุณสมบัติขึ้นปกครอง", n, t));
                    }
                }
            }
        } else {
            let head = self.polities[pol as usize].head();
            let cands: Vec<Pid> = self.candidates(pol, idx).into_iter().filter(|&c| Some(c) != head && self.people[c as usize].office.is_none()).collect();
            let pick = cands.into_iter().max_by(|&a, &b| {
                let s = |c: Pid| head.map_or(0, |h| self.people[h as usize].bonds.get(&c).copied().unwrap_or(0)) as f64 * 0.5 + self.people[c as usize].realm as f64;
                s(a).partial_cmp(&s(b)).unwrap().then(b.cmp(&a))
            });
            if let Some(c) = pick {
                self.install(pol, idx, c, Accession::Appointed);
                self.ledger.count("แต่งตั้ง");
            }
        }
    }

    fn announce_succession(&mut self, pol: PolId, n: Pid, how: Accession) {
        let g = &self.polities[pol as usize];
        let (name, title, kind) = (g.name.clone(), g.title().to_string(), g.kind);
        let nn = self.people[n as usize].name.clone();
        let verb = match how {
            Accession::Inherited => "สืบทอดตำแหน่งต่อจากบรรพบุรุษ ขึ้นเป็น",
            Accession::Elected => "ได้รับเลือกเป็น",
            Accession::Appointed => "ได้รับแต่งตั้งเป็น",
            Accession::Seized => "ใช้กำลังยึดอำนาจขึ้นเป็น",
            Accession::Prevailed => "เอาชนะผู้ท้าชิงทั้งหมดขึ้นเป็น",
            _ => "ขึ้นเป็น",
        };
        match kind {
            PolityKind::Sect => self.emit("สืบทอดสำนัก", Some(n), None, "เป็นเจ้าสำนัก", format!("{}{}เจ้า{}", nn, verb, name)),
            _ => self.emit("สืบตำแหน่งเจ้าเมือง", Some(n), None, "ขึ้นปกครอง", format!("{}{}{}แห่ง{}", nn, verb, title, name)),
        }
    }

    /// จำนวนตำแหน่งรองตามขนาด แล้วเติมที่ว่าง
    fn sync_offices(&mut self, pol: PolId) {
        let g = &self.polities[pol as usize];
        let (target, title) = match g.kind {
            PolityKind::Sect => {
                let n = g.members.len();
                (if n >= 2 { (1 + n / self.cfg.sect_members_per_elder).min(self.cfg.sect_elders_max) } else { 0 }, "ผู้อาวุโส")
            }
            PolityKind::City => (
                self.cfg.city_officials,
                match g.title() {
                    "ฮ่องเต้" => "เสนาบดี",
                    "แม่ทัพใหญ่" => "รองแม่ทัพ",
                    "ราชาตลาดมืด" => "มือขวา",
                    "ตัวแทนสำนัก" => "ผู้ช่วยตัวแทน",
                    _ => "ขุนนาง",
                },
            ),
            _ => (0, "ขุนนาง"),
        };
        while self.polities[pol as usize].offices.len() > 1 + target {
            let o = self.polities[pol as usize].offices.pop().unwrap();
            if let Some(h) = o.holder {
                self.people[h as usize].office = None;
            }
        }
        let day = self.day;
        while self.polities[pol as usize].offices.len() < 1 + target {
            self.polities[pol as usize].offices.push(Office { title: title.to_string(), rank: 1, holder: None, since: day, how: Accession::Appointed });
        }
        for idx in 1..self.polities[pol as usize].offices.len() {
            self.fill_office(pol, idx, None);
        }
    }

    // ------------------------------------------------------------------ ฐานะทางการเมือง
    fn update_standing(&mut self, pol: PolId) {
        let g = &self.polities[pol as usize];
        let pool: Vec<Pid> = match g.kind {
            PolityKind::Sect => g.members.clone(),
            _ => self.present_at(g.seat),
        };
        let n = pool.len().max(1) as f32;
        let fed = pool.iter().filter(|&&i| self.people[i as usize].hunger_days <= 0.0).count() as f32 / n;
        let support = match g.kind {
            PolityKind::City => {
                let crooks = pool.iter().filter(|&&i| self.is_criminal(i)).count() as f32 / n;
                0.6 * fed + 0.4 * (1.0 - crooks)
            }
            _ => 0.5 * fed + 0.5 * ((g.treasury / (50.0 * n as f64)).min(1.0) as f32),
        };
        let authority = match g.head() {
            Some(h) => {
                let mine = self.power(h);
                // คู่แข่งที่นับ: ผู้ดำรงตำแหน่งรอง และ (สำหรับสำนัก) ศิษย์ขั้นสูงสุด — ไม่ต้องคิดพลังของทุกคนทุกเดือน
                let top = pool.iter().copied().filter(|&i| i != h).max_by_key(|&i| (self.people[i as usize].realm, std::cmp::Reverse(i)));
                let rival = g.holders().map(|(_, x)| x).filter(|&x| x != h).chain(top).map(|i| self.power(i)).fold(0.0, f64::max);
                (mine / (mine + rival).max(1e-9)).min(1.0) as f32 * 2.0
            }
            None => 0.0,
        }
        .min(1.0);
        let g = &mut self.polities[pol as usize];
        g.standing.support = support;
        g.standing.authority = authority;
        let target = 0.4 + 0.4 * support + 0.2 * authority;
        g.standing.legitimacy += (target - g.standing.legitimacy) * 0.02;
        let now = (g.standing.legitimacy + support + authority) / 3.0;
        g.standing.stability = 0.9 * g.standing.stability + 0.1 * now;
    }

    // ------------------------------------------------------------------ รอบรายเดือน
    pub fn tick_polities(&mut self, days: f64) {
        for pol in 0..self.polities.len() as u32 {
            if !self.polities[pol as usize].alive() {
                continue;
            }
            if self.polities[pol as usize].kind == PolityKind::Sect {
                let people = &self.people;
                self.polities[pol as usize].members.retain(|&m| people[m as usize].alive && people[m as usize].sect == Some(pol));
                if self.polities[pol as usize].members.is_empty() {
                    self.dissolve_sect(pol, "ไม่เหลือศิษย์สักคน");
                    continue;
                }
                if let Some(p) = self.polities[pol as usize].parent {
                    if !self.polities[p as usize].alive() {
                        self.polities[pol as usize].parent = None;
                        self.polities[pol as usize].relations.remove(&p);
                    }
                }
            }
            // ผู้ดำรงตำแหน่งที่ไม่มีสิทธิ์แล้ว (ตายหรือย้ายแดนไปโดยไม่ผ่านทางที่ปลดตำแหน่ง)
            let holders: Vec<(usize, Pid)> = self.polities[pol as usize].holders().collect();
            for (idx, h) in holders {
                if !self.holds_validly(pol, idx, h) {
                    if self.people[h as usize].office == Some((pol, idx as u8)) {
                        self.people[h as usize].office = None;
                    }
                    self.polities[pol as usize].offices[idx].holder = None;
                    self.fill_office(pol, idx, Some(h));
                }
            }
            if !self.polities[pol as usize].alive() {
                continue;
            }
            if self.polities[pol as usize].head().is_none() {
                self.fill_office(pol, 0, None);
            }
            if !self.polities[pol as usize].alive() {
                continue;
            }
            self.sync_offices(pol);
            self.update_standing(pol);
            if self.polities[pol as usize].kind == PolityKind::Sect {
                self.sect_payout(pol, days);
                self.sect_decline(pol);
            }
        }
    }

    /// สำนักแจกจ่ายทรัพยากรคืนแก่ศิษย์ตามลำดับชั้น (ทองย้ายจากคลังไปคน — บัญชีรวมไม่เปลี่ยน)
    fn sect_payout(&mut self, pol: PolId, days: f64) {
        let frac = 1.0 - (1.0 - self.cfg.sect_payout_rate).powf(days / 365.0);
        let pot = self.polities[pol as usize].treasury * frac;
        if pot <= 0.0 {
            return;
        }
        let members = self.polities[pol as usize].members.clone();
        let shares: Vec<(Pid, f64)> = members.iter().map(|&m| (m, self.sect_share(pol, m))).collect();
        let total: f64 = shares.iter().map(|s| s.1).sum();
        if total <= 0.0 {
            return;
        }
        let mut paid = 0.0;
        for (m, s) in shares {
            let x = pot * s / total;
            self.people[m as usize].gold += x;
            paid += x;
        }
        self.polities[pol as usize].treasury -= paid;
    }

    fn sect_share(&self, pol: PolId, m: Pid) -> f64 {
        match self.sect_rank(m) {
            Some((p, 0)) if p == pol => 4.0,
            Some((p, 1)) if p == pol => 3.0,
            Some((p, 2)) if p == pol => 2.0,
            _ => 1.0,
        }
    }

    /// ลำดับชั้นในสำนัก: 0 เจ้าสำนัก · 1 ผู้อาวุโส · 2 ศิษย์สายใน · 3 ศิษย์สายนอก
    pub fn sect_rank(&self, id: Pid) -> Option<(PolId, u8)> {
        let p = &self.people[id as usize];
        let s = p.sect?;
        if let Some((op, oi)) = p.office {
            if op == s {
                return Some((s, oi.min(1)));
            }
        }
        Some((s, if (p.realm % self.cfg.realm_band) as f64 >= k("ORG_INNER_REALM") { 2 } else { 3 }))
    }

    pub fn sect_rank_name(&self, id: Pid) -> Option<&'static str> {
        self.sect_rank(id).map(|(_, r)| ["เจ้าสำนัก", "ผู้อาวุโส", "ศิษย์สายใน", "ศิษย์สายนอก"][r as usize])
    }

    pub fn sect_strength(&self, pol: PolId) -> f64 {
        self.polities[pol as usize].members.iter().map(|&m| self.power(m)).sum()
    }

    /// สำนักอ่อนแอนาน → ควบรวมเข้าสำนักที่แข็งกว่าใกล้ ๆ / ยอมอยู่ใต้ปีก / สลายไป
    fn sect_decline(&mut self, pol: PolId) {
        let g = &self.polities[pol as usize];
        let weak = g.members.len() < self.cfg.sect_min_members || g.standing.stability < 0.3;
        if !weak {
            self.polities[pol as usize].weak_months = 0;
            return;
        }
        self.polities[pol as usize].weak_months += 1;
        let wm = self.polities[pol as usize].weak_months;
        if wm < self.cfg.sect_weak_months {
            return;
        }
        let g = &self.polities[pol as usize];
        let probe = g.head().unwrap_or(g.members[0]);
        let (world, seat) = (g.world, g.seat);
        let mine = self.sect_strength(pol);
        let near: Vec<(u32, f64)> = self
            .polities
            .iter()
            .filter(|o| o.id != pol && o.kind == PolityKind::Sect && o.alive() && o.world == world && o.parent != Some(pol))
            .filter(|o| self.travel_days(probe, seat, o.seat) <= self.cfg.sect_reach_days)
            .map(|o| (o.id, self.sect_strength(o.id)))
            .collect();
        let best = near.iter().copied().filter(|&(_, s)| s > mine).max_by(|a, b| a.1.partial_cmp(&b.1).unwrap().then(b.0.cmp(&a.0)));
        let g = &self.polities[pol as usize];
        match best {
            Some((o, _)) if g.head().is_none() || g.members.len() <= 2 => self.merge_sect(pol, o),
            Some((o, s)) if g.parent.is_none() && s >= 2.0 * mine => self.subordinate(pol, o),
            _ if wm >= 2 * self.cfg.sect_weak_months => self.dissolve_sect(pol, "เสื่อมถอยจนสิ้นสำนัก"),
            _ => {}
        }
    }

    pub fn merge_sect(&mut self, from: PolId, into: PolId) {
        let holders: Vec<Pid> = self.polities[from as usize].holders().map(|(_, h)| h).collect();
        for h in holders {
            self.vacate(h);
        }
        let members = std::mem::take(&mut self.polities[from as usize].members);
        for &m in &members {
            self.people[m as usize].sect = Some(into);
        }
        self.polities[into as usize].members.extend(members);
        let t = std::mem::take(&mut self.polities[from as usize].treasury);
        self.polities[into as usize].treasury += t;
        self.polities[from as usize].fallen = Some(self.day);
        let (a, b) = (self.polities[from as usize].name.clone(), self.polities[into as usize].name.clone());
        let (w, s) = (self.polities[into as usize].world, self.polities[into as usize].seat);
        self.emit_at("ควบรวมสำนัก", w, s, "ควบรวม", format!("{}อ่อนแรงจนต้องรวมเข้ากับ{}", a, b));
    }

    pub fn subordinate(&mut self, vassal: PolId, lord: PolId) {
        let day = self.day;
        self.polities[vassal as usize].parent = Some(lord);
        self.polities[vassal as usize].weak_months = 0;
        let r = self.polities[vassal as usize].relations.entry(lord).or_default();
        r.treaty = Treaty::Subordinate;
        r.trust = r.trust.max(0.5);
        r.since = day;
        let r = self.polities[lord as usize].relations.entry(vassal).or_default();
        r.treaty = Treaty::Overlord;
        r.since = day;
        let (a, b) = (self.polities[vassal as usize].name.clone(), self.polities[lord as usize].name.clone());
        let (w, s) = (self.polities[lord as usize].world, self.polities[lord as usize].seat);
        self.emit_at("สวามิภักดิ์", w, s, "อยู่ใต้ปีก", format!("{}ยอมอยู่ใต้ปีกของ{}", a, b));
    }

    // ------------------------------------------------------------------ ตั้งสำนัก
    /// จำนวนสำนักที่แดนนี้รองรับได้ ตามปราณรวมของแดน
    pub fn sect_capacity(&self, world: u16) -> usize {
        let qi: f64 = self.worlds[world as usize].places.iter().map(|&p| self.qi[p as usize]).sum();
        (qi / self.cfg.sect_qi_per_sect).floor() as usize
    }

    pub fn can_found_sect(&self, id: Pid) -> bool {
        let p = &self.people[id as usize];
        if !p.cultivator || p.sect.is_some() || p.office.is_some() || p.gold < self.cfg.sect_found_cost || (p.realm % self.cfg.realm_band) < self.cfg.found_sect_realm {
            return false;
        }
        if !self.habitable(p.world, p.place) || self.qi[p.place as usize] < self.cfg.sect_site_qi {
            return false;
        }
        let here = self.polities.iter().filter(|s| s.kind == PolityKind::Sect && s.alive() && s.world == p.world);
        let mut n = 0;
        for s in here {
            if s.seat == p.place {
                return false;
            }
            n += 1;
        }
        n < self.sect_capacity(p.world)
    }

    /// ตรวจข้อคงที่ของทุกหน่วย (ใช้ในเทสต์และตรวจสุขภาพ)
    pub fn check_polities(&self) -> Result<(), String> {
        let mut seen: BTreeMap<Pid, (PolId, usize)> = BTreeMap::new();
        for g in &self.polities {
            for (idx, h) in g.holders() {
                let p = &self.people[h as usize];
                if !g.alive() {
                    return Err(format!("{} ล่มสลายแล้วแต่ยังมีผู้ดำรงตำแหน่ง", g.name));
                }
                if !p.alive {
                    return Err(format!("{} ตำแหน่ง {} ถือโดยคนตาย {}", g.name, idx, p.name));
                }
                if p.office != Some((g.id, idx as u8)) {
                    return Err(format!("{} ตำแหน่ง {} ชี้ไป {} แต่คนนั้นถือ {:?}", g.name, idx, p.name, p.office));
                }
                if let Some(prev) = seen.insert(h, (g.id, idx)) {
                    return Err(format!("{} ถือสองตำแหน่ง {:?} และ {:?}", p.name, prev, (g.id, idx)));
                }
            }
            if !g.alive() && !g.members.is_empty() {
                return Err(format!("{} ล่มสลายแล้วแต่ยังมีสมาชิก", g.name));
            }
            if g.kind == PolityKind::Sect && g.alive() {
                for &m in &g.members {
                    if self.people[m as usize].sect != Some(g.id) {
                        return Err(format!("{} มีสมาชิก {} ที่ไม่ได้สังกัด", g.name, self.people[m as usize].name));
                    }
                }
            }
        }
        for &i in &self.alive {
            if let Some((pol, idx)) = self.people[i as usize].office {
                if self.polities[pol as usize].offices.get(idx as usize).and_then(|o| o.holder) != Some(i) {
                    return Err(format!("{} อ้างตำแหน่ง {:?} ที่ไม่ได้ถือ", self.people[i as usize].name, (pol, idx)));
                }
            }
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::engine::config::Config;
    use crate::engine::data;

    fn engine() -> Engine {
        Engine::new(17, Config::default())
    }

    /// คนธรรมดาที่ไม่มีมลทิน (อาชีพสุจริต ไม่มีคดี) ณ ที่ที่กำหนด
    fn citizen(e: &mut Engine, world: u16, place: u32, realm: u8, parents: [Option<Pid>; 2]) -> Pid {
        let id = e.spawn(world, Some(place), 30.0, parents);
        let crim = data::strs(data::table("config", "CRIMINAL_PROFESSIONS"));
        let honest = data::world().professions.iter().position(|(n, _)| !crim.contains(n)).unwrap() as u8;
        let p = &mut e.people[id as usize];
        p.profession = honest;
        p.crimes = 0;
        p.moral = 10;
        p.cultivator = true;
        p.realm = realm;
        p.peak_realm = realm;
        p.process = None;
        id
    }

    fn city(e: &Engine, title: &str) -> PolId {
        e.polities.iter().find(|p| p.kind == PolityKind::City && p.title() == title).unwrap().id
    }

    /// สำนักที่ตั้งขึ้นด้วยกติกาจริง ณ ที่ที่มีปราณพอ
    fn sect_at(e: &mut Engine, world: u16, place: u32, members: &[u8]) -> (PolId, Vec<Pid>) {
        let r = e.cfg.found_sect_realm + 2;
        let f = citizen(e, world, place, r, [None, None]);
        e.people[f as usize].gold = 1000.0;
        assert!(e.can_found_sect(f), "ตั้งสำนักที่ {} ไม่ได้", place);
        e.found_sect(f);
        let s = e.people[f as usize].sect.unwrap();
        let mut ids = vec![f];
        for &r in members {
            let m = citizen(e, world, place, r, [None, None]);
            e.people[m as usize].sect = Some(s);
            e.polities[s as usize].members.push(m);
            ids.push(m);
        }
        (s, ids)
    }

    /// สองที่ในแดนเดียวกันที่มีปราณพอ อยู่ใกล้กัน
    fn two_sites(e: &Engine, world: u16) -> (u32, u32) {
        // ไม่ใช้ที่ตั้งของเมือง (เมืองจะดึงคนที่อยู่ตรงนั้นไปเป็นขุนนาง)
        let good: Vec<u32> = e.worlds[world as usize].places.iter().copied().filter(|&p| e.qi[p as usize] >= e.cfg.sect_site_qi && e.city_at(p).is_none()).collect();
        let probe = *e.alive.iter().next().unwrap();
        let mut best = (i64::MAX, good[0], good[1]);
        for &a in &good {
            for &b in &good {
                if a < b {
                    let d = e.travel_days(probe, a, b);
                    if d < best.0 {
                        best = (d, a, b);
                    }
                }
            }
        }
        (best.1, best.2)
    }

    #[test]
    fn heredity_passes_to_eldest_eligible_child() {
        let mut e = engine();
        let cap = city(&e, "ฮ่องเต้");
        let r = e.polities[cap as usize].head().unwrap();
        let (w, seat) = (e.polities[cap as usize].world, e.polities[cap as usize].seat);
        let elder = citizen(&mut e, w, seat, 1, [Some(r), None]);
        let younger = citizen(&mut e, w, seat, 9, [Some(r), None]);
        e.people[elder as usize].crimes = 5; // บุตรคนโตมีคดี → ไม่มีคุณสมบัติ
        let _ = younger;
        e.kill(r, None, "ชรา", true);
        let g = &e.polities[cap as usize];
        assert_eq!(g.head(), Some(younger));
        assert_eq!(g.offices[0].how, Accession::Inherited);
        assert_eq!(e.people[younger as usize].office, Some((cap, 0)));
        assert_eq!(e.people[r as usize].office, None);
        e.check_polities().unwrap();
    }

    #[test]
    fn council_elects_and_refills_the_elder_seat() {
        let mut e = engine();
        let (a, _) = two_sites(&e, 0);
        let (s, ids) = sect_at(&mut e, 0, a, &[5, 7, 4, 4]);
        e.tick_polities(30.0);
        e.check_polities().unwrap();
        let elder = e.polities[s as usize].offices[1].holder.unwrap();
        assert_eq!(elder, ids[2], "ผู้อาวุโสคือศิษย์ขั้นสูงสุด");
        e.kill(ids[0], None, "ชรา", true);
        let g = &e.polities[s as usize];
        assert_eq!(g.head(), Some(ids[2]));
        assert_eq!(g.offices[0].how, Accession::Elected);
        // ที่นั่งผู้อาวุโสที่ว่างลงถูกเติมทันที
        assert!(g.offices[1].holder.is_some() && g.offices[1].holder != Some(ids[2]));
        e.check_polities().unwrap();
    }

    #[test]
    fn strength_rules_the_black_market() {
        let mut e = engine();
        let bm = city(&e, "ราชาตลาดมืด");
        let r = e.polities[bm as usize].head().unwrap();
        let (w, seat) = (e.polities[bm as usize].world, e.polities[bm as usize].seat);
        let brute = citizen(&mut e, w, seat, 9, [None, None]);
        e.people[brute as usize].crimes = 9; // ตลาดมืดไม่ถามประวัติ
        e.kill(r, None, "ชรา", true);
        let g = &e.polities[bm as usize];
        assert_eq!(g.head(), Some(brute));
        assert_eq!(g.offices[0].how, Accession::Prevailed);
    }

    #[test]
    fn appointment_follows_the_overlords_favour() {
        let mut e = engine();
        let cap = city(&e, "ฮ่องเต้");
        let fr = city(&e, "แม่ทัพใหญ่");
        e.polities[fr as usize].parent = Some(cap);
        let lord = e.polities[cap as usize].head().unwrap();
        let r = e.polities[fr as usize].head().unwrap();
        let (w, seat) = (e.polities[fr as usize].world, e.polities[fr as usize].seat);
        let strong = citizen(&mut e, w, seat, 9, [None, None]);
        let favourite = citizen(&mut e, w, seat, 2, [None, None]);
        e.people[lord as usize].bonds.insert(favourite, 50);
        let _ = strong;
        e.kill(r, None, "ชรา", true);
        let g = &e.polities[fr as usize];
        assert_eq!(g.head(), Some(favourite));
        assert_eq!(g.offices[0].how, Accession::Appointed);
    }

    #[test]
    fn no_one_qualified_means_interregnum_not_an_invalid_ruler() {
        let mut e = engine();
        let cap = city(&e, "ฮ่องเต้");
        let seat = e.polities[cap as usize].seat;
        let r = e.polities[cap as usize].head().unwrap();
        for i in e.present_at(seat) {
            if i != r {
                e.people[i as usize].crimes = 3;
            }
        }
        let holders: Vec<Pid> = e.polities[cap as usize].holders().filter(|&(i, _)| i > 0).map(|(_, h)| h).collect();
        for h in holders {
            e.people[h as usize].crimes = 3;
        }
        e.kill(r, None, "ชรา", true);
        let g = &e.polities[cap as usize];
        assert!(g.head().map_or(true, |h| !e.is_criminal(h)));
        e.check_polities().unwrap();
    }

    #[test]
    fn founding_requires_qi_room_and_capital_and_keeps_the_ledger() {
        let mut e = engine();
        let (a, _) = two_sites(&e, 0);
        let (s, ids) = sect_at(&mut e, 0, a, &[]);
        assert_eq!(e.polities[s as usize].treasury, e.cfg.sect_found_cost);
        assert_eq!(e.polities[s as usize].offices[0].how, Accession::Founded);
        // ที่ตั้งเดียวกันตั้งซ้ำไม่ได้
        let other = { let r = e.cfg.found_sect_realm + 2; citizen(&mut e, 0, a, r, [None, None]) };
        e.people[other as usize].gold = 1000.0;
        assert!(!e.can_found_sect(other));
        // ทุนไม่พอ
        let (_, b) = two_sites(&e, 0);
        let poor = { let r = e.cfg.found_sect_realm + 2; citizen(&mut e, 0, b, r, [None, None]) };
        e.people[poor as usize].gold = e.cfg.sect_found_cost - 1.0;
        assert!(!e.can_found_sect(poor));
        e.people[poor as usize].gold = e.cfg.sect_found_cost;
        assert!(e.can_found_sect(poor));
        // แดนเต็มแล้ว
        e.cfg.sect_qi_per_sect = 1e9;
        assert!(!e.can_found_sect(poor));
        let _ = ids;
    }

    #[test]
    fn founding_moves_gold_without_creating_it() {
        let mut e = engine();
        let (a, _) = two_sites(&e, 0);
        let f = { let r = e.cfg.found_sect_realm + 2; citizen(&mut e, 0, a, r, [None, None]) };
        e.people[f as usize].gold = 500.0;
        let before = e.total_gold();
        e.found_sect(f);
        assert!((e.total_gold() - before).abs() < 1e-9);
        assert_eq!(e.people[f as usize].gold, 500.0 - e.cfg.sect_found_cost);
    }

    #[test]
    fn weak_sect_merges_into_a_stronger_neighbour() {
        let mut e = engine();
        let (a, b) = two_sites(&e, 0);
        let (weak, wids) = sect_at(&mut e, 0, a, &[]);
        let (strong, _) = sect_at(&mut e, 0, b, &[8, 8, 8, 8]);
        e.polities[weak as usize].treasury = 77.0;
        e.polities[weak as usize].weak_months = e.cfg.sect_weak_months - 1;
        let total = e.total_gold();
        e.tick_polities(30.0);
        assert!(!e.polities[weak as usize].alive());
        assert_eq!(e.people[wids[0] as usize].sect, Some(strong));
        assert!(e.polities[strong as usize].members.contains(&wids[0]));
        assert!((e.total_gold() - total).abs() < 1e-6, "ทองต้องไม่หายหรือเกิดใหม่");
        e.check_polities().unwrap();
    }

    #[test]
    fn weak_sect_with_a_leader_becomes_subordinate() {
        let mut e = engine();
        let (a, b) = two_sites(&e, 0);
        let (weak, _) = sect_at(&mut e, 0, a, &[1, 1, 1]);
        let (strong, _) = sect_at(&mut e, 0, b, &[9, 9, 9, 9, 9]);
        e.polities[weak as usize].standing.stability = 0.0;
        e.polities[weak as usize].weak_months = e.cfg.sect_weak_months - 1;
        e.tick_polities(30.0);
        let g = &e.polities[weak as usize];
        assert!(g.alive());
        assert_eq!(g.parent, Some(strong));
        assert_eq!(g.relations[&strong].treaty, Treaty::Subordinate);
        assert_eq!(e.polities[strong as usize].relations[&weak].treaty, Treaty::Overlord);
    }

    #[test]
    fn leaving_the_world_or_the_sect_releases_office() {
        let mut e = engine();
        let (a, _) = two_sites(&e, 0);
        let (s, ids) = sect_at(&mut e, 0, a, &[6, 6]);
        e.tick_polities(30.0);
        e.leave_sect(ids[0]);
        assert_eq!(e.people[ids[0] as usize].office, None);
        assert!(e.polities[s as usize].head().is_some() && e.polities[s as usize].head() != Some(ids[0]));
        e.check_polities().unwrap();
    }

    #[test]
    fn offices_stay_consistent_over_decades() {
        let mut e = Engine::new(23, Config::default());
        for y in 1..=40 {
            e.run_until(y * 365);
            e.check_polities().unwrap_or_else(|m| panic!("ปี {}: {}", y, m));
        }
        // เมืองทุกเมืองมีผู้ปกครองเกือบตลอด
        let ruled = e.polities.iter().filter(|p| p.kind == PolityKind::City && p.head().is_some()).count();
        let all = e.polities.iter().filter(|p| p.kind == PolityKind::City).count();
        assert!(ruled * 10 >= all * 8, "{}/{} เมืองมีผู้ปกครอง", ruled, all);
        // สำนักไม่ล้นเกินที่แดนรองรับ
        for w in &e.worlds {
            let n = e.polities.iter().filter(|p| p.kind == PolityKind::Sect && p.alive() && p.world == w.id).count();
            assert!(n <= e.sect_capacity(w.id), "{} มี {} สำนัก เกิน {}", w.name, n, e.sect_capacity(w.id));
        }
    }

    #[test]
    fn routine_is_counted_historic_is_always_kept() {
        let mut e = engine();
        let w = e.people[*e.alive.iter().next().unwrap() as usize].world;
        let a = *e.alive.iter().find(|&&i| e.people[i as usize].world == w).unwrap();
        let n0 = e.log.len();
        e.emit("ปิดด่าน", Some(a), None, "", "x".into());
        assert_eq!(e.log.len(), n0);
        assert_eq!(e.world_counts[&w]["ปิดด่าน"], 1);
        for _ in 0..200 {
            e.emit("ทรยศ", Some(a), None, "", "x".into());
        }
        let notable = e.log.iter().filter(|x| x.kind == "ทรยศ").count();
        assert!(notable as u32 <= e.cfg.notable_per_world_year);
        for _ in 0..200 {
            e.emit("ตั้งสำนัก", Some(a), None, "", "x".into());
        }
        assert_eq!(e.log.iter().filter(|x| x.kind == "ตั้งสำนัก").count(), 200);
        assert_eq!(e.world_counts[&w]["ทรยศ"], 200);
    }
}
