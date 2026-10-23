//! การปกครอง — โครงสร้างเดียวสำหรับทุกหน่วยอำนาจ (เมือง สำนัก ตระกูล แคว้น ราชสำนักแดน ราชสำนักสวรรค์ ลัทธิ กบฏ)
//!
//! ทุกหน่วยมีตำแหน่ง (ตำแหน่ง 0 คือผู้นำ) กฎสืบทอด ฐานะทางการเมือง นโยบาย ผลประโยชน์ ความสัมพันธ์ และคลังของตัวเอง
//! id ของหน่วยคือดัชนีใน Engine.polities และไม่ถูกใช้ซ้ำ — หน่วยที่ล่มสลายยังอยู่ในช่องเดิม (fallen = Some(วัน))
//!
//! ฟิลด์ที่ยังไม่ถูกใช้ (interests relations factions parent) ตั้งค่ากลางไว้ เพื่อให้ระยะถัดไปเติมพฤติกรรมได้โดยไม่ต้องรื้อโครงสร้าง

use super::model::Pid;
use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;

pub type PolId = u32;

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub enum PolityKind {
    City,
    Sect,
    Clan,
    Region,
    RealmCourt,
    HeavenCourt,
    Cult,
    Rebel,
}

/// วิธีเลือกผู้นำคนใหม่เมื่อตำแหน่งว่าง
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub enum Succession {
    /// บุตรคนโตที่มีคุณสมบัติ → ถ้าไม่มี ใช้สภา
    Heredity,
    /// ผู้นำของหน่วยเหนือแต่งตั้ง → ถ้าไม่มีหน่วยเหนือ ใช้สภา
    Appointment,
    /// ผู้ดำรงตำแหน่งรองลงไปลงคะแนน → ถ้าไม่มีผู้ลงคะแนน ใช้กำลัง
    Council,
    /// ผู้แกร่งที่สุดที่มีคุณสมบัติ
    Strength,
    /// สวรรค์รับรอง (ราชสำนักสวรรค์ ระยะ P6) → ระหว่างนี้ใช้สภา
    Mandate,
}

/// ได้ตำแหน่งมาอย่างไร — เป็นฐานของความชอบธรรมเริ่มต้น
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub enum Accession {
    Founded,
    Inherited,
    Appointed,
    Elected,
    Seized,
    /// ชนะด้วยกำลังตามกฎของหน่วยที่ถือกำลังเป็นใหญ่ (ไม่ใช่การยึดอำนาจ)
    Prevailed,
    Mandated,
    Migrated,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Office {
    pub title: String,
    pub rank: u8,
    pub holder: Option<Pid>,
    pub since: i64,
    pub how: Accession,
}

/// ฐานะทางการเมือง 0..1
#[derive(Clone, Copy, Debug, Serialize, Deserialize)]
pub struct Standing {
    pub legitimacy: f32,
    pub support: f32,
    pub authority: f32,
    pub stability: f32,
}

impl Default for Standing {
    fn default() -> Self {
        Standing { legitimacy: 0.6, support: 0.6, authority: 0.6, stability: 0.6 }
    }
}

#[derive(Clone, Copy, Debug, Serialize, Deserialize)]
pub struct Policy {
    pub tax: f32,
    pub dues: f32,
    /// ความเข้มงวดของกฎหมาย 0..1
    pub strictness: f32,
    /// ขั้นต่ำที่รับเข้า (ภายในชั้นของแดน)
    pub admit_realm: u8,
}

impl Default for Policy {
    fn default() -> Self {
        Policy { tax: 0.0, dues: 0.0, strictness: 0.5, admit_realm: 0 }
    }
}

/// น้ำหนักของสิ่งที่หน่วยนี้ต้องการ (เติมพฤติกรรมใน P4)
#[derive(Clone, Copy, Debug, Serialize, Deserialize)]
pub struct Interests {
    pub territory: f32,
    pub wealth: f32,
    pub cultivation: f32,
    pub treasure: f32,
    pub security: f32,
    pub prestige: f32,
}

impl Interests {
    pub fn for_kind(kind: PolityKind) -> Interests {
        let (territory, wealth, cultivation, treasure, security, prestige) = match kind {
            PolityKind::City => (0.4, 0.8, 0.1, 0.2, 0.9, 0.4),
            PolityKind::Sect => (0.5, 0.4, 0.9, 0.7, 0.5, 0.7),
            PolityKind::Clan => (0.4, 0.6, 0.6, 0.5, 0.7, 0.8),
            PolityKind::Region | PolityKind::RealmCourt => (0.8, 0.7, 0.3, 0.4, 0.8, 0.6),
            PolityKind::HeavenCourt => (0.6, 0.4, 0.6, 0.6, 0.9, 0.9),
            PolityKind::Cult => (0.5, 0.5, 0.8, 0.8, 0.3, 0.4),
            PolityKind::Rebel => (0.9, 0.6, 0.2, 0.3, 0.6, 0.5),
        };
        Interests { territory, wealth, cultivation, treasure, security, prestige }
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize, Default)]
pub enum Treaty {
    #[default]
    None,
    Alliance,
    /// หน่วยนี้อยู่ใต้หน่วยนั้น
    Subordinate,
    /// หน่วยนั้นอยู่ใต้หน่วยนี้
    Overlord,
    War,
}

#[derive(Clone, Debug, Serialize, Deserialize, Default)]
pub struct Relation {
    pub trust: f32,
    pub fear: f32,
    pub grudge: i16,
    pub debt: f64,
    pub treaty: Treaty,
    pub since: i64,
}

/// กลุ่มก้อนภายในหน่วย (เติมพฤติกรรมใน P4)
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Faction {
    pub leader: Pid,
    pub members: Vec<Pid>,
    pub aim: String,
}

/// คุณลักษณะของเมือง 0..100
#[derive(Clone, Copy, Debug, Serialize, Deserialize)]
pub struct CityTraits {
    pub safety: f32,
    pub wealth: f32,
    pub jianghu: f32,
    pub info: f32,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Polity {
    pub id: PolId,
    pub kind: PolityKind,
    pub name: String,
    /// ลักษณะเฉพาะ เช่น "เมืองหลวง" (ใช้กำหนดตำแหน่งและกฎ)
    pub style: String,
    pub world: u16,
    pub seat: u32,
    pub territory: Vec<u32>,
    pub parent: Option<PolId>,
    pub succession: Succession,
    pub offices: Vec<Office>,
    pub members: Vec<Pid>,
    pub standing: Standing,
    pub policy: Policy,
    pub interests: Interests,
    pub relations: BTreeMap<PolId, Relation>,
    pub factions: Vec<Faction>,
    pub treasury: f64,
    pub founder: Option<Pid>,
    pub founded: i64,
    pub fallen: Option<i64>,
    pub traits: Option<CityTraits>,
    /// เดือนติดต่อกันที่อ่อนแอ (ใช้ตัดสินควบรวม/สวามิภักดิ์/สลาย)
    #[serde(default)]
    pub weak_months: u16,
}

impl Polity {
    pub fn new(id: PolId, kind: PolityKind, name: String, world: u16, seat: u32, succession: Succession, head_title: &str, day: i64) -> Polity {
        Polity {
            id,
            kind,
            name,
            style: String::new(),
            world,
            seat,
            territory: vec![seat],
            parent: None,
            succession,
            offices: vec![Office { title: head_title.to_string(), rank: 0, holder: None, since: day, how: Accession::Founded }],
            members: Vec::new(),
            standing: Standing::default(),
            policy: Policy::default(),
            interests: Interests::for_kind(kind),
            relations: BTreeMap::new(),
            factions: Vec::new(),
            treasury: 0.0,
            founder: None,
            founded: day,
            fallen: None,
            traits: None,
            weak_months: 0,
        }
    }

    pub fn alive(&self) -> bool {
        self.fallen.is_none()
    }

    pub fn head(&self) -> Option<Pid> {
        self.offices.first().and_then(|o| o.holder)
    }

    pub fn title(&self) -> &str {
        self.offices.first().map_or("", |o| o.title.as_str())
    }

    pub fn holders(&self) -> impl Iterator<Item = (usize, Pid)> + '_ {
        self.offices.iter().enumerate().filter_map(|(i, o)| o.holder.map(|h| (i, h)))
    }
}

// ------------------------------------------------------------------ รูปแบบเซฟเก่า (ก่อน P1) — อ่านได้แล้วย้ายเข้า polities ใน after_load
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct LegacySect {
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
    #[serde(default)]
    pub grudges: BTreeMap<u32, i16>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct LegacyCity {
    pub id: u16,
    pub name: String,
    pub world: u16,
    pub place: u32,
    pub kind: String,
    pub safety: f32,
    pub wealth: f32,
    pub jianghu: f32,
    pub info: f32,
    pub strictness: f32,
    pub title: String,
    pub ruler: Option<Pid>,
}

#[cfg(test)]
mod tests {
    use crate::engine::config::Config;
    use crate::engine::sim::Engine;
    use serde_json::{json, Value};

    /// แปลงเซฟปัจจุบันกลับเป็นรูปแบบก่อน P1 (sects + cities + person.city)
    fn to_legacy(e: &Engine) -> Value {
        let mut v = serde_json::to_value(e).unwrap();
        let pols = v["polities"].as_array().unwrap().clone();
        let mut sects = vec![];
        let mut cities = vec![];
        let mut city_of = std::collections::BTreeMap::new();
        for p in &pols {
            if p["kind"] == "Sect" {
                sects.push(json!({"id": p["id"], "name": p["name"], "world": p["world"], "home": p["seat"], "founder": p["founder"],
                    "leader": p["offices"][0]["holder"], "founded": p["founded"], "members": p["members"], "treasury": p["treasury"],
                    "alive": p["fallen"].is_null(), "grudges": {}}));
            } else {
                let t = &p["traits"];
                city_of.insert(p["id"].as_u64().unwrap(), cities.len());
                cities.push(json!({"id": cities.len(), "name": p["name"], "world": p["world"], "place": p["seat"], "kind": p["style"],
                    "safety": t["safety"], "wealth": t["wealth"], "jianghu": t["jianghu"], "info": t["info"],
                    "strictness": (p["policy"]["strictness"].as_f64().unwrap() * 100.0).round(), "title": p["offices"][0]["title"], "ruler": p["offices"][0]["holder"]}));
            }
        }
        let o = v.as_object_mut().unwrap();
        o.remove("polities");
        o.insert("sects".into(), Value::Array(sects));
        o.insert("cities".into(), Value::Array(cities));
        for p in o.get_mut("people").unwrap().as_array_mut().unwrap() {
            let off = p["office"].clone();
            let po = p.as_object_mut().unwrap();
            po.remove("office");
            if let Some(pid) = off.get(0).and_then(|x| x.as_u64()) {
                po.insert("city".into(), json!(city_of[&pid]));
            }
        }
        v
    }

    #[test]
    fn pre_p1_save_migrates() {
        // เซฟก่อน P1 มีแค่เจ้าเมือง (ยังไม่มีขุนนาง) — ใช้โลกที่เพิ่งสร้างก่อนรอบรายเดือนแรก แล้วจำลองต่อ เทียบกับต้นฉบับ
        let mut a = Engine::new(9, Config::default());
        assert!(a.polities.iter().all(|p| p.kind == super::PolityKind::City));
        let legacy = to_legacy(&a);
        let mut b: Engine = serde_json::from_value(legacy).unwrap();
        b.after_load();
        // เมืองถูกย้ายมาครบ และเจ้าเมืองได้ตำแหน่งกลับคืน
        assert_eq!(b.polities.len(), a.polities.len());
        for (x, y) in a.polities.iter().zip(&b.polities) {
            assert_eq!((x.seat, x.head(), &x.name), (y.seat, y.head(), &y.name));
        }
        for (x, y) in a.people.iter().zip(&b.people) {
            assert_eq!(x.office, y.office, "{}", x.name);
        }
        a.run_until(6 * 365);
        b.run_until(6 * 365);
        assert_eq!(crate::engine::sim::tests::fingerprint(&a), crate::engine::sim::tests::fingerprint(&b));
    }
}
#[cfg(test)]
mod index_tests {
    /// ดัชนีคนต่อสถานที่ต้องตรงกับความจริงเสมอ (เจ้าโกลาหลที่สลายอยู่ไม่อยู่ในดัชนี)
    #[test]
    fn at_index_matches_truth() {
        let mut e = crate::engine::sim::Engine::new(9, crate::engine::config::Config::default());
        for d in 1..=120 {
            e.run_until(d * 20);
            for (pl, set) in e.at.iter().enumerate() {
                for &i in set {
                    let p = &e.people[i as usize];
                    assert!(p.alive && p.place as usize == pl, "day {} stale at[{}] has {} alive {} place {}", e.day, pl, p.name, p.alive, p.place);
                }
            }
            for &i in &e.alive {
                let p = &e.people[i as usize];
                assert!(p.dissolved() || e.at[p.place as usize].contains(&i), "day {} missing {} process {:?} lord {} chaos {}", e.day, p.name, p.process, p.is_lord, p.chaos_rank);
            }
        }
    }
}
