//! ข้อมูลคงที่ของโลก — สถานที่ ถนน ชื่อ อาชีพ วิถี (ฝังในไบนารีจาก data/world.json)

use serde::Deserialize;
use std::collections::HashMap;
use std::sync::OnceLock;

#[derive(Deserialize, Clone, Debug)]
pub struct Place {
    pub name: String,
    /// คีย์ผังของแดน: "t0" "t1" "t2" (โลกหลักตามชั้น) หรือ "siam" "br017" ฯลฯ
    pub world: String,
    pub grade: i64,
    pub kind: String,
    pub material: Option<String>,
    pub forge: i64,
    pub secret_of: Option<String>,
    pub sealed: bool,
    pub x: f64,
    pub y: f64,
}

#[derive(Deserialize, Clone, Debug)]
pub struct Edge {
    pub a: usize,
    pub b: usize,
    pub dist: f64,
    pub kind: String,
    pub open: bool,
}

#[derive(Deserialize, Clone, Debug)]
pub struct Branch {
    pub name: String,
    pub skill_line: String,
    pub origin: String,
    pub key: String,
}

#[derive(Deserialize, Clone, Debug)]
#[serde(untagged)]
pub enum Tribe {
    Fixed(String),
    Weighted(Vec<(String, f64)>),
}

#[derive(Deserialize, Debug)]
pub struct WorldData {
    pub realms: Vec<String>,
    pub realm_prefix: Vec<String>,
    pub realm_ranks: Vec<String>,
    pub tier_names: Vec<String>,
    pub sister_realms: Vec<(String, String)>,
    pub branch_realms: Vec<Branch>,
    pub places: Vec<Place>,
    pub edges: Vec<Edge>,
    /// วัฒนธรรม -> [ชื่อชุดแรก, ชื่อชุดหลัง] (ลำดับตามธรรมเนียมของวัฒนธรรมนั้น)
    pub names: HashMap<String, (Vec<String>, Vec<String>)>,
    pub tribes: HashMap<String, Tribe>,
    pub origins: Vec<(String, f64)>,
    pub professions: Vec<(String, f64)>,
    pub dao_pool: HashMap<String, Vec<String>>,
    pub org_words: (Vec<String>, Vec<String>),
    pub beast_kind: Vec<String>,
    pub beast_trait: Vec<String>,
}

static DATA: OnceLock<WorldData> = OnceLock::new();

pub fn world() -> &'static WorldData {
    DATA.get_or_init(|| {
        serde_json::from_str(include_str!("../../data/world.json")).expect("data/world.json เสีย")
    })
}

impl WorldData {
    /// ชื่อขั้นบนบันไดเส้นเดียว 0..29 (ปุถุชน..เทพล่วงพ้น)
    pub fn realm_name(&self, realm: u8) -> String {
        let band = self.realms.len() as u8;
        let tier = (realm / band) as usize;
        let r = (realm % band) as usize;
        if tier == 0 {
            self.realms[r].clone()
        } else {
            let pre = &self.realm_prefix[tier.min(self.realm_prefix.len() - 1)];
            format!("{}{}", pre, self.realm_ranks[r])
        }
    }

    /// รายชื่อวิถีเรียงตามชื่อ (HashMap ไม่มีลำดับ — ต้องคงที่เพื่อให้ seed เดิมได้โลกเดิม)
    pub fn dao_names(&self) -> Vec<&String> {
        let mut v: Vec<&String> = self.dao_pool.keys().collect();
        v.sort();
        v
    }
}
