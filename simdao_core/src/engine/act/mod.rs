//! เทิร์นของคน — เลือกการกระทำจากสภาพของตัวเองและสิ่งรอบตัว แล้วลงมือ
//!
//! การเลือกเป็นแบบน้ำหนัก (ไม่ใช่ argmax) — คนในสภาพเดียวกันไม่จำเป็นต้องทำเหมือนกัน
//! แต่ความต้องการที่เร่งด่วนกว่า (หิว บาดเจ็บ แค้น ถึงจังหวะข้ามขั้น) มีน้ำหนักมากกว่ามาก

mod choose;
mod travel;
mod livelihood;

use super::geo;
use super::model::*;
use super::sim::Engine;

#[derive(Clone, Copy, Debug, PartialEq)]
pub enum Act {
    Work,
    Rest,
    BeginPath,
    Cultivate,
    Seclude,
    Breakthrough,
    Ascend,
    Harvest(Material),
    Sell,
    Wander,
    SeekFood(u32),
    SeekQi(u32),
    GoHome(u32),
    Court(Pid),
    Duel(Pid),
    Revenge(Pid),
    Rob(Pid),
    JoinSect(u32),
    FoundSect,
    Teach(Pid),
    Heal(Pid),
    Brew,
    Forge,
    Arrest(Pid),
    Train,
    RefineBlood,
    Promise(Pid),
    Betray(Pid),
    Settle(Pid),
    HeavenWar,
    SellCrafts,
    Hunt,
    Search,
    Hide,
    Seize(Pid),
    CraftArray,
    Foresee,
    Patrol,
    Protect,
    Extort,
    Merit,
    Fortune(Pid),
    SellInfo(Pid),
    Assassinate(Pid),
    CityLife,
    Gate,
}

impl Engine {
    pub fn turn(&mut self, id: Pid) {
        // ---- กิจกรรมยาวที่ทำค้างอยู่
        match self.people[id as usize].process.clone() {
            Some(Process::Dissolved) => {
                self.lord_turn(id);
                return;
            }
            Some(Process::Hidden { since, until, .. }) => {
                if self.day < until {
                    self.schedule(id, until - self.day);
                } else {
                    self.emerge_hidden(id, since);
                }
                return;
            }
            Some(Process::Travel { dest, arrive, .. }) => {
                if self.day < arrive {
                    self.schedule(id, arrive - self.day);
                } else {
                    self.arrive(id, dest);
                    let gap = self.range(1, 10);
                    self.schedule(id, gap);
                }
                return;
            }
            Some(Process::Jail { until }) => {
                if self.day < until {
                    self.schedule(id, until - self.day);
                } else {
                    self.people[id as usize].process = None;
                    let n = self.people[id as usize].name.clone();
                    self.emit("พ้นโทษ", Some(id), None, "พ้นโทษ", format!("{}พ้นโทษออกจากคุก", n));
                    let gap = self.range(5, 30);
                    self.schedule(id, gap);
                }
                return;
            }
            Some(Process::Seclusion { until, .. }) => {
                if self.day < until {
                    self.schedule(id, until - self.day);
                } else {
                    self.emerge(id);
                }
                return;
            }
            None => {}
        }
        if !self.is_adult(id) {
            self.childhood(id);
            return;
        }
        let p = &self.people[id as usize];
        if p.is_chaos() || !p.sentient {
            // เผ่าโกลาหลบำเพ็ญอยู่ในถิ่น (การบุกเกิดบนนาฬิกาโลก) · อสูรไร้จิตหากินตามสัญชาตญาณ
            let gap = if p.is_chaos() { self.cultivate(id) } else { self.range(30, 120) };
            if self.people[id as usize].alive {
                self.schedule(id, gap);
            }
            return;
        }
        let act = self.choose(id);
        let gap = self.perform(id, act);
        if self.people[id as usize].alive {
            self.schedule(id, gap);
        }
    }

    pub(crate) fn childhood(&mut self, id: Pid) {
        // เด็กช่วยงานบ้านและเรียนรู้จากพ่อแม่ — ลูกของผู้บำเพ็ญได้เห็นวิถีตั้งแต่เล็ก
        let p = &self.people[id as usize];
        let parent_cult = p.parents.iter().flatten().any(|&q| self.people[q as usize].cultivator);
        if parent_cult && p.root >= self.cfg.root_cultivate_min as f32 {
            self.people[id as usize].insight += 0.05;
        }
        let gap = self.range(60, 240);
        self.schedule(id, gap);
    }

    // ------------------------------------------------------------------ ลงมือ — คืนจำนวนวันถึงเทิร์นถัดไป
    pub fn perform(&mut self, id: Pid, act: Act) -> i64 {
        match act {
            Act::Work => self.range(15, 60),
            Act::Rest => {
                let p = &mut self.people[id as usize];
                p.injury *= 0.7;
                self.range(10, 40)
            }
            Act::BeginPath => self.begin_path(id),
            Act::Cultivate => self.cultivate(id),
            Act::Seclude => self.seclude(id),
            Act::Breakthrough => self.breakthrough(id),
            Act::Ascend => self.ascend(id),
            Act::Harvest(m) => self.harvest(id, m),
            Act::Sell => self.sell(id),
            Act::Wander => {
                let p = self.people[id as usize].place;
                let near = geo::within(p, 2);
                let w = self.people[id as usize].world;
                let opts: Vec<u32> = near.iter().map(|&(q, _)| q).filter(|&q| q != p && self.habitable(w, q)).collect();
                match self.pick(&opts) {
                    Some(dest) => self.depart(id, dest, "เดินทาง"),
                    None => self.range(10, 30),
                }
            }
            Act::SeekFood(dest) => self.depart(id, dest, "ย้ายหาข้าว"),
            Act::SeekQi(dest) => self.depart(id, dest, "ตามหาปราณ"),
            Act::GoHome(dest) => self.depart(id, dest, "กลับสำนัก"),
            Act::Court(m) => self.court(id, m),
            Act::Duel(t) => self.duel(id, t, false),
            Act::Revenge(t) => self.duel(id, t, true),
            Act::Rob(t) => self.rob(id, t),
            Act::JoinSect(s) => self.join_sect(id, s),
            Act::FoundSect => self.found_sect(id),
            Act::Teach(t) => self.teach(id, t),
            Act::Heal(t) => self.heal(id, t),
            Act::Brew => self.craft(id, true),
            Act::Forge => self.craft(id, false),
            Act::SellCrafts => self.sell_crafts(id),
            Act::Hunt => self.hunt(id),
            Act::Search => self.search_secret(id),
            Act::Hide => self.hide(id),
            Act::Seize(t) => self.seize_treasure(id, t),
            Act::CraftArray => self.craft_array(id),
            Act::Foresee => self.foresee(id),
            Act::Patrol => self.patrol(id),
            Act::Protect => self.protect(id),
            Act::Extort => self.extort(id),
            Act::Merit => self.merit(id),
            Act::Fortune(t) => self.fortune(id, t),
            Act::SellInfo(t) => self.sell_info(id, t),
            Act::Assassinate(t) => self.assassinate(id, t),
            Act::CityLife => self.city_life(id),
            Act::Gate => self.use_gate(id),
            Act::Arrest(t) => self.arrest(id, t, None),
            Act::Train => self.train(id),
            Act::RefineBlood => self.refine_blood(id),
            Act::Promise(t) => self.promise(id, t),
            Act::Betray(t) => self.betray(id, t),
            Act::Settle(t) => self.settle(id, t),
            Act::HeavenWar => self.heaven_war(id),
        }
    }
}
