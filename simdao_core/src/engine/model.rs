//! โครงสร้างข้อมูลของโลก — คน แดน สำนัก ครัวเรือน เหตุการณ์
//!
//! ทุก map ที่วนซ้ำได้เป็น BTreeMap (ไม่ใช่ HashMap) เพราะลำดับการวนต้องคงที่ —
//! seed เดียวกันต้องได้โลกเดียวกันทุกครั้งทุกเครื่อง

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;

pub type Pid = u32;

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub enum Material {
    Herb = 0,
    Ore = 1,
    Core = 2,
}

impl Material {
    pub const ALL: [Material; 3] = [Material::Herb, Material::Ore, Material::Core];
    pub fn from_th(s: &str) -> Option<Material> {
        match s {
            "สมุนไพร" => Some(Material::Herb),
            "แร่" => Some(Material::Ore),
            "แก่นพลัง" => Some(Material::Core),
            _ => None,
        }
    }
    pub fn th(self) -> &'static str {
        match self {
            Material::Herb => "สมุนไพร",
            Material::Ore => "แร่",
            Material::Core => "แก่นพลัง",
        }
    }
}

/// สายเลือด: มนุษย์ วิญญาณ อสูร มาร โกลาหล
pub const BLOODS: [&str; 5] = ["human", "spirit", "demon", "mara", "chaos"];
pub const HUMAN: usize = 0;
pub const SPIRIT: usize = 1;
pub const DEMON: usize = 2;
pub const MARA: usize = 3;
pub const CHAOS: usize = 4;

/// เรื่องค้างคาในใจ — ตัวเพาะจิตมาร (ฆ่า ทรยศ ผิดสัญญา ปล้น ทอดทิ้ง บุญคุณ)
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Debt {
    pub kind: String,
    pub target: Pid,
    pub day: i64,
    pub done: bool,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub enum Process {
    /// เดินทางอยู่ — ถึงปลายทางวันไหน
    Travel { dest: u32, since: i64, arrive: i64 },
    /// ปิดด่านบำเพ็ญจนถึงวันไหน
    Seclusion { since: i64, until: i64 },
    /// ถูกคุมขังจนถึงวันไหน
    Jail { until: i64 },
    /// เจ้าโกลาหลสลายเป็นความโกลาหล รอก่อร่างใหม่จากพลังความตายทั่วจักรวาล
    Dissolved,
    /// ซ่อนตัวในแดนลับของตัวเอง (trap = แกล้งตายวางกับดัก)
    Hidden { since: i64, until: i64, trap: bool },
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Person {
    pub id: Pid,
    pub name: String,
    pub female: bool,
    pub born: i64,
    pub lifespan: f64,          // อายุขัยพื้น (ปี) ก่อนโบนัสขั้น
    pub world: u16,
    pub place: u32,
    pub alive: bool,
    pub death_day: i64,
    pub death_cause: String,
    pub killer: Option<Pid>,

    pub tribe: String,
    pub origin: u8,
    pub profession: u8,
    pub dao: u8,
    pub fear: f32,
    pub greed: f32,
    pub compassion: f32,
    pub ambition: f32,
    pub loyalty: f32,

    // ---- บำเพ็ญ
    pub root: f32,              // รากปราณ 0 = ไม่มีทาง · 1 = อัจฉริยะ
    pub cultivator: bool,       // ก้าวเข้าสู่วิถีแล้ว
    pub realm: u8,
    pub peak_realm: u8,
    pub insight: f64,
    pub decay: f64,
    pub drawn: f64,             // ปราณที่ดูดจากฟ้าไปแล้ว (คืนเมื่อตาย)
    pub breaks: u16,
    pub fails: u16,

    // ---- ร่างกาย
    pub injury: f32,            // 0 = ไม่มีแผล · 1 = ปางตาย
    pub hunger_days: f32,
    pub pack: f32,              // เสบียงติดตัว (สำรับ)

    // ---- ทรัพย์
    pub gold: f64,
    pub mats: [f32; 3],

    // ---- ครอบครัวและสังคม
    pub spouse: Option<Pid>,
    pub parents: [Option<Pid>; 2],
    pub children: Vec<Pid>,
    pub pregnant: Option<(i64, Pid)>,   // (กำหนดคลอด, บิดา)
    pub postpartum_until: i64,
    pub bonds: BTreeMap<Pid, i16>,
    pub rivals: BTreeMap<Pid, i16>,
    pub sect: Option<u32>,
    pub master: Option<Pid>,
    pub kills: u16,

    pub process: Option<Process>,
    // ---- โรค ของทำมือ กฎหมาย
    pub sick_until: i64,        // ป่วยอยู่ถึงวันไหน (0 = ไม่ป่วย)
    pub immune_until: i64,      // มีภูมิคุ้มกันถึงวันไหน
    pub items: Vec<u32>,        // ของในย่าม (ดัชนีใน Engine.items)
    pub alchemy: f32,           // ประสบการณ์ปรุงยา / ตีอาวุธ
    pub forge: f32,
    pub alch_rank: i8,          // -1 = ยังไม่เข้าสาย
    pub forge_rank: i8,
    pub fragments: std::collections::BTreeMap<u16, Vec<u8>>, // เศษวิชาที่เก็บได้
    pub leads: Vec<u32>,        // ร่องรอยที่ชี้ไปแดนลับ (cache id)
    pub crimes: u16,            // ความผิดที่ยังไม่ได้ชดใช้
    // ---- สายเลือดและจิต
    pub blood: [f32; 5],
    pub refine: f64,            // การขัดเกลาสายเลือดวิญญาณ
    pub inner: f64,             // จิตมาร
    pub inner_none: bool,       // เกิดมาไร้จิตมาร
    pub inner_art: bool,        // ฝึกจิตมารเป็นวิชา
    pub debts: Vec<Debt>,
    pub fate: i8,               // ชะตาที่ช่วยให้รอดตายได้ (ใช้แล้วหมดไป)
    pub chaos_rank: i8,         // -1 = ไม่ใช่เผ่าโกลาหล
    pub is_lord: bool,
    pub lord_returns: u16,
    pub thrall: bool,           // ตกเป็นทาสโกลาหล
    pub fallen: bool,           // ถูกจิตมารครอบงำ ตกเป็นมาร
    pub sentient: bool,         // อสูรระดับต่ำยังไม่มีจิตนึกคิด
    pub unique_title: String,   // อสูรเฉพาะตัว
    pub affinity: [f32; 5],     // ดวงรับพรของแต่ละสายเลือด
    pub birth_world: u16,
    pub peak_tier: u8,
    pub near_death: u16,
    // ---- วิชา
    pub skills: Vec<u16>,       // ดัชนีใน skills::skills()
    pub mastery: Vec<u16>,      // จำนวนครั้งที่ฝึก (คู่กับ skills)
    pub element: u8,            // ธาตุประจำตัว 0..5 (ไม้ ไฟ ดิน ทอง น้ำ)
    // ---- หุ่นเชิด วัฏจักร นิมิต
    pub puppets: u8,
    pub puppet_kind: String,
    pub cycle_born: bool,
    pub rebirth_count: u8,
    pub past_life: Option<Pid>,
    pub past_realm: u8,
    pub past_skills: Vec<u16>,
    pub past_dao: u8,
    pub memory_woken: bool,
    pub foresight: bool,        // เจ้าของระบบจำลองอนาคต (มีคนเดียวในโลก)
    pub foresight_ready: i64,
    pub foreseen: std::collections::BTreeMap<Pid, i64>,
    pub visions: Vec<Vec<String>>,
    pub fate_changed: u16,
    pub fate_kept: u16,
    pub last_day: i64,          // วันที่คิดอายุ/ความเสื่อม/บาดแผลไปแล้ว
    pub next_turn: i64,         // เทิร์นถัดไปที่นัดไว้ — รายการในคิวที่ไม่ตรงนี้คือนัดเก่าที่ถูกเลื่อนแล้ว
    pub fieldwork: bool,        // ลงไร่ช่วงข้าวขาด
}

impl Person {
    pub fn age(&self, day: i64) -> f64 {
        (day - self.born) as f64 / 365.0
    }
    pub fn tier(&self, band: u8) -> u8 {
        self.realm / band
    }
    pub fn top_blood(&self) -> usize {
        let mut best = 0;
        for i in 1..5 {
            if self.blood[i] > self.blood[best] {
                best = i;
            }
        }
        best
    }
    pub fn is_chaos(&self) -> bool {
        self.chaos_rank >= 0
    }
    pub fn dissolved(&self) -> bool {
        matches!(self.process, Some(Process::Dissolved))
    }
    /// ประสิทธิภาพของเส้นทางเติบโตสายหนึ่ง — ยิ่งเลือดผสม ยิ่งทำงานได้ไม่เต็ม
    pub fn eff(&self, line: usize) -> f64 {
        (self.blood[line] as f64).powf(1.4)
    }
    pub fn sick(&self, day: i64) -> bool {
        self.sick_until > day
    }
    pub fn jailed(&self) -> bool {
        matches!(self.process, Some(Process::Jail { .. }))
    }
    pub fn travelling(&self) -> bool {
        matches!(self.process, Some(Process::Travel { .. }))
    }
    pub fn secluded(&self) -> bool {
        matches!(self.process, Some(Process::Seclusion { .. }))
    }
    pub fn grudge(&self, other: Pid) -> i16 {
        self.rivals.get(&other).copied().unwrap_or(0)
    }
    pub fn bond(&self, other: Pid) -> i16 {
        self.bonds.get(&other).copied().unwrap_or(0)
    }
}

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub enum WorldKind {
    Main,
    Sister,
    Branch,
    Mara,
    Chaos,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct World {
    pub id: u16,
    pub name: String,
    pub tier: u8,
    pub kind: WorldKind,
    pub key: String,            // คีย์ผังสถานที่ใน data::Place.world
    pub culture: String,        // ใช้เลือกชุดชื่อ
    pub up: Option<u16>,
    pub lateral: Vec<u16>,
    pub places: Vec<u32>,       // สถานที่ที่อยู่อาศัยได้ (ไม่รวมแดนลับ)
    pub heaven: f64,
    pub cap: f64,
    pub era: u32,
    pub blood_marks: Vec<i64>,  // วันที่มีการนองเลือด (ฮอว์กส์) — ตัดของเก่าทิ้งเป็นระยะ
    pub harvest_mult: f64,      // ภัยแล้ง/น้ำท่วมปีนี้ (1 = ปกติ)
    pub harvest_until: i64,
    pub rift: f64,              // รอยแยกโกลาหลในแดนนี้
    pub defense: f64,           // ค่ายกลป้องกันแดน
    pub defense_max: f64,
    pub closed: bool,           // ประตูแดนปิดรับผู้ข้ามฟ้า
    pub resentment: f64,        // ความบาดหมางต่อแดนบน (จากการเกณฑ์คน)
    pub last_coalition: i64,
    pub ruined: Vec<(u32, i64)>,// สถานที่ที่ถูกถล่ม จนถึงวันไหน
}

impl World {
    pub fn ratio(&self) -> f64 {
        self.heaven / self.cap
    }
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Sect {
    pub id: u32,
    pub name: String,
    pub world: u16,
    pub home: u32,
    pub founder: Pid,
    pub leader: Pid,
    pub founded: i64,
    pub members: Vec<Pid>,
    pub treasury: f64,
    pub alive: bool,
    pub grudges: BTreeMap<u32, i16>,
}

/// สถานะของสถานที่หนึ่งแห่ง (สถานที่แต่ละแห่งอยู่ในแดนเดียวเสมอ)
#[derive(Clone, Debug, Serialize, Deserialize, Default)]
pub struct PlaceState {
    pub granary: f64,
    pub stock: [f64; 3],        // สมุนไพร แร่ แก่นพลัง ที่เหลือในธรรมชาติ
    pub till: f64,              // ทองที่คนใช้จ่ายที่นี่ รอจ่ายเป็นค่าแรง
    pub produced_month: f64,
    pub treasury: f64,          // คลังชุมชน (มรดกไร้ผู้รับ ค่าธรรมเนียม)
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Event {
    pub seq: u64,
    pub day: i64,
    pub kind: String,
    pub actor: Option<Pid>,
    pub target: Option<Pid>,
    pub world: u16,
    pub place: u32,
    pub outcome: String,
    pub text: String,
}

/// ข่าวที่ยังเดินทางไปไม่ถึงผู้รับ
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct News {
    pub arrive: i64,
    pub to: Pid,
    pub about: Pid,
    pub killer: Option<Pid>,
}

/// บัญชีที่ต้องปิดได้เสมอ — ทุกหน่วยที่เกิดหรือหายมีชื่อ
#[derive(Clone, Debug, Serialize, Deserialize, Default)]
pub struct Ledger {
    pub food: BTreeMap<String, f64>,
    pub gold: BTreeMap<String, f64>,
    pub deaths: BTreeMap<String, u64>,
    pub counts: BTreeMap<String, u64>,
}

impl Ledger {
    pub fn food(&mut self, k: &str, v: f64) {
        *self.food.entry(k.to_string()).or_insert(0.0) += v;
    }
    pub fn gold(&mut self, k: &str, v: f64) {
        *self.gold.entry(k.to_string()).or_insert(0.0) += v;
    }
    pub fn count(&mut self, k: &str) {
        *self.counts.entry(k.to_string()).or_insert(0) += 1;
    }
    pub fn death(&mut self, k: &str) {
        *self.deaths.entry(k.to_string()).or_insert(0) += 1;
    }
}
