//! ความสำคัญของเหตุการณ์ — แยกบันทึกประวัติศาสตร์ออกจากสถิติประจำวัน
//!
//! · ประวัติศาสตร์ (Historic): ผู้นำเปลี่ยน ตั้ง/ล่มสลาย/ควบรวมสำนัก สงคราม ภัยระดับแดน — บันทึกเสมอ ไม่ทิ้ง
//! · น่าสนใจ (Notable): บันทึกจนถึงงบต่อแดนต่อปี (notable_per_world_year) เกินนั้นนับเป็นสถิติ
//! · ประจำวัน (Routine): นับเป็นสถิติอย่างเดียว
//! ทุกเหตุการณ์ถูกนับใน ledger.counts และ world_counts เสมอ — ไม่มีอะไรหายเงียบ
//! สำเนาที่ใช้มองอนาคต (fork) บันทึกทุกอย่าง เพราะการให้คะแนนอนาคตอ่านจากบันทึก

use super::model::Pid;
use super::sim::Engine;

#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord)]
pub enum Tier {
    Routine,
    Notable,
    Historic,
}

const HISTORIC: &[&str] = &[
    "สืบทอดสำนัก", "สืบตำแหน่งเจ้าเมือง", "ตั้งสำนัก", "สำนักล่มสลาย", "ควบรวมสำนัก", "สวามิภักดิ์", "ว่างผู้นำ",
    "มารบุก", "โกลาหลบุกโลกมนุษย์", "โกลาหลบุก", "สงครามเบิกฟ้า", "พันธมิตรปราบเจ้าโกลาหล", "ข้ามฟ้า", "โรคระบาด",
    "เจ้าโกลาหลสลาย", "เจ้าโกลาหลคืนกลับ", "มหาผนึกโกลาหลเสื่อม", "มหาผนึกแตกพัง", "มหาผนึกสั่นคลอน", "ผนึกเจ้าโกลาหล",
    "ปิดรอยแยก", "ซ่อมมหาผนึก", "บัญชาสวรรค์", "พรสายเลือด", "ระบบจำลองอนาคต", "สมบัติฟ้าดินหวนคืนผนึก", "เกณฑ์ขึ้นฟ้า",
];

const ROUTINE: &[&str] = &[
    "ค้นแดนลับ", "ปิดด่าน", "ออกจากด่าน", "ล่าอสูร", "ฝึกวิชา", "เดินทาง", "ให้สัญญา", "เหตุการณ์เมือง", "ประลอง", "จับกุม",
    "พ้นโทษ", "ตั้งครรภ์", "กำเนิดทายาท", "แต่งงาน", "ค้าขาย", "เข้าสำนัก", "ติดโรค", "รู้ข่าวร้าย", "ถ่ายทอดวิชา", "หลอมยา",
    "หลอมอาวุธ", "หลอมค่ายกล", "ขายของหลอม", "ปล้น", "ขูดรีดชาวบ้าน", "ไปขอเข้าสำนัก", "กลับสำนัก", "ตามหาปราณ", "เปิดประมูล",
    "ก้าวสู่วิถี", "เชิดซากเป็นหุ่น", "สะสางเรื่องเก่า", "ข้ามประตูมิติ", "จำลองอนาคต", "รอดตายด้วยชะตา", "ซ่อนตัว", "ออกจากแดนลับ",
];

impl Engine {
    pub fn event_tier(&self, kind: &str, actor: Option<Pid>) -> Tier {
        if HISTORIC.contains(&kind) {
            return Tier::Historic;
        }
        if ROUTINE.contains(&kind) {
            return Tier::Routine;
        }
        let band = self.cfg.realm_band;
        match (kind, actor) {
            // คนสำคัญตาย = น่าสนใจ · ชาวบ้านตาย = สถิติ (การตายของผู้นำทำให้เกิดเหตุการณ์สืบทอดอยู่แล้ว)
            ("ตาย", Some(a)) => {
                let p = &self.people[a as usize];
                if p.realm % band >= 5 || p.peak_tier > 0 || p.kills >= 5 || p.office.is_some() {
                    Tier::Notable
                } else {
                    Tier::Routine
                }
            }
            ("ข้ามขั้น", Some(a)) if self.people[a as usize].realm % band < 5 => Tier::Routine,
            _ => Tier::Notable,
        }
    }

    /// คืน true ถ้าเหตุการณ์นี้ควรถูกบันทึกลง log (นับสถิติแล้วไม่ว่าผลจะเป็นอย่างไร)
    pub(crate) fn admit_event(&mut self, kind: &str, actor: Option<Pid>, world: u16) -> bool {
        self.ledger.count(kind);
        *self.world_counts.entry(world).or_default().entry(kind.to_string()).or_insert(0) += 1;
        if self.fork {
            return true;
        }
        match self.event_tier(kind, actor) {
            Tier::Historic => true,
            Tier::Routine => false,
            Tier::Notable => {
                let year = self.day.div_euclid(365);
                let b = self.notable_budget.entry(world).or_insert((year, 0));
                if b.0 != year {
                    *b = (year, 0);
                }
                if b.1 >= self.cfg.notable_per_world_year {
                    return false;
                }
                b.1 += 1;
                true
            }
        }
    }
}
