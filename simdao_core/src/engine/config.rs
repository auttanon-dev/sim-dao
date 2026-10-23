//! ค่าคงที่ของโลก — ทั้งหมดอยู่ที่นี่ที่เดียว
//!
//! ตัวเลขส่วนใหญ่มาจาก tiandao/config.py เดิม (ผ่านการวัดผลมาแล้วหลายรอบ) ส่วนที่ระบบใหม่เพิ่มเอง
//! เขียนเหตุผลกำกับไว้ ทั้ง struct serialize ได้ จึงปรับค่าจาก Python ได้ด้วย Engine(config={...})

use serde::{Deserialize, Serialize};

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(default)]
pub struct Config {
    // ---- ประชากร
    pub cast_mortal: usize,     // โลกมนุษย์ (แดนหลักชั้นล่างสุด)
    pub cast_main: usize,       // แดนหลักชั้นบนแต่ละแห่ง
    pub cast_sister: usize,     // แดนเพื่อนบ้านของโลกมนุษย์
    pub cast_branch: usize,     // แดนเซียนสาขาแต่ละแห่ง
    pub branch_realms: usize,   // จำนวนแดนสาขาที่สร้าง (สูงสุดเท่าที่มีในข้อมูล)
    pub adult_age: f64,
    pub marry_min_age: f64,
    pub fertile_max_age: f64,   // หญิง
    pub gestation_days: u32,
    pub postpartum_days: u32,
    pub conceive_per_year: f64, // โอกาสตั้งครรภ์ต่อปีของคู่ที่อยู่ด้วยกัน
    pub infant_mortality: f64,  // ต่อปี ช่วงขวบปีแรก
    pub child_mortality: f64,   // ต่อปี อายุ 1-14

    // ---- อายุขัย (ปกติตัดปลาย แล้วบวกโบนัสตามขั้น)
    pub lifespan_mu: f64,
    pub lifespan_sigma: f64,
    pub lifespan_min: f64,
    pub lifespan_max: f64,
    pub lifespan_per_minor: f64,
    pub lifespan_per_major: f64,

    // ---- ขั้นและพลัง
    pub realm_band: u8,         // ขั้นต่อหนึ่งชั้นฟ้า
    pub realm_step: f64,
    pub tier_step: f64,
    pub insight_w: f64,
    pub decay_w: f64,
    pub need_base: f64,
    pub need_per_realm: f64,
    pub break_base_p: f64,
    pub break_softness: f64,
    pub break_z_decay: f64,
    pub break_z_tier: f64,
    pub break_z_realm: f64,
    pub break_z_scarce: f64,
    pub heaven_ratio_floor: f64,
    pub break_fail_spend: f64,
    pub backlash_decay: f64,
    pub break_cost: f64,
    pub break_look_ahead: f64,
    pub cultivate_gain: f64,    // ความเข้าใจต่อปีของการบำเพ็ญเต็มเวลา ที่ปราณ 1.0
    pub cultivate_heal: f64,
    pub decay_per_year: f64,
    pub decay_per_realm_mult: f64,
    pub root_mu: f64,           // รากปราณ (พรสวรรค์) ~ ปกติ ตัดที่ 0
    pub root_sigma: f64,
    pub root_cultivate_min: f64,// ต่ำกว่านี้ไม่มีทางเริ่มบำเพ็ญ
    pub ascend_odds: f64,       // ข้ามฟ้าเมื่อตันขั้นของชั้น
    pub bigu_realm: u8,         // ขั้นที่ไม่ต้องกินข้าว

    // ---- คลังปราณฟ้า
    pub heaven_cap: f64,
    pub heaven_cap_per_tier: f64,
    pub heaven_regen_per_day: f64,
    pub heaven_seed_ratio: f64,
    pub life_inflow: f64,       // ปราณที่ปุถุชนหนึ่งคนเติมให้ฟ้าต่อปี
    pub natural_return: f64,    // ตายตามธรรมชาติ คืนปราณที่ดูดไปเท่านี้
    pub killed_return: f64,
    pub decline_ratio: f64,
    pub flourish_ratio: f64,
    pub qi_scale: f64,          // มาตราส่วนของสนามปราณบนผิวดาว

    // ---- ร่างกาย
    pub injury_heal_per_day: f64,
    pub starve_days: f64,
    pub fatigue_per_day_work: f64,

    // ---- อาหาร
    pub ration_adult: f64,
    pub ration_child: f64,
    pub per_worker_day: f64,
    pub land_cap_day: f64,
    pub spoil_per_year: f64,
    pub pack_days: f64,
    pub start_food_days: f64,
    pub store_months: f64,
    pub reach_hops: usize,
    pub carry_loss_per_hop: f64,
    pub food_price: f64,
    pub season_amp: f64,        // ผลผลิตแกว่งตามฤดู ±

    // ---- ทอง
    pub start_gold: f64,
    pub keep_gold: f64,
    pub spend_rate: f64,        // ต่อปี ของส่วนเกินเงินเก็บ
    pub mine_gold_per_year: f64,

    // ---- ระบบนิเวศ (สมุนไพร แร่ สัตว์อสูร ต่อสถานที่)
    pub eco_cap: f64,
    pub eco_regen_per_day: f64,
    pub harvest_per_trip: f64,
    pub material_price: f64,

    // ---- การเดินทาง
    pub travel_speed: f64,      // หน่วยระยะต่อวันที่ขั้น 0
    pub travel_speed_per_realm: f64,

    // ---- การปะทะ
    pub death_margin: f64,
    pub duel_friendly_mult: f64,
    pub decay_per_fight: f64,
    pub hawkes_alpha: f64,
    pub hawkes_decay_days: f64,
    pub grudge_on_kill: i32,
    pub grudge_half_life_years: f64,

    // ---- สำนัก
    pub found_sect_realm: u8,
    pub sect_join_realm_max: u8,
    pub sect_tithe: f64,

    // ---- ข่าว
    pub news_per_hop_days: f64,

    // ---- นาฬิกาโลก
    pub world_tick_days: u32,
    pub log_keep: usize,        // เก็บเหตุการณ์ล่าสุดในหน่วยความจำ (ที่เหลือ drain ออกไปเขียนไฟล์)
}

impl Default for Config {
    fn default() -> Self {
        Config {
            cast_mortal: 320,
            cast_main: 120,
            cast_sister: 80,
            cast_branch: 12,
            branch_realms: 108,
            adult_age: 14.0,
            marry_min_age: 16.0,
            fertile_max_age: 45.0,
            gestation_days: 270,
            postpartum_days: 365,
            conceive_per_year: 0.45,
            infant_mortality: 0.20,
            child_mortality: 0.02,

            lifespan_mu: 72.0,
            lifespan_sigma: 10.0,
            lifespan_min: 45.0,
            lifespan_max: 95.0,
            lifespan_per_minor: 100.0,
            lifespan_per_major: 300.0,

            realm_band: 10,
            realm_step: 3.0,
            tier_step: 27.0,
            insight_w: 0.35,
            decay_w: 0.60,
            need_base: 6.0,
            need_per_realm: 3.0,
            break_base_p: 0.55,
            break_softness: 0.5,
            break_z_decay: 0.40,
            break_z_tier: 0.48,
            break_z_realm: 0.16,
            break_z_scarce: 1.0,
            heaven_ratio_floor: 0.12,
            break_fail_spend: 0.5,
            backlash_decay: 1.2,
            break_cost: 2.0,
            break_look_ahead: 0.75,
            cultivate_gain: 1.2,
            cultivate_heal: 0.9,
            decay_per_year: 0.020,
            decay_per_realm_mult: 0.12,
            root_mu: 0.3,
            root_sigma: 0.2,
            root_cultivate_min: 0.6,
            ascend_odds: 0.35,
            bigu_realm: 3,

            heaven_cap: 70000.0,
            heaven_cap_per_tier: 2.4,
            heaven_regen_per_day: 0.00012,
            heaven_seed_ratio: 0.02,
            life_inflow: 0.6,
            natural_return: 0.85,
            killed_return: 0.15,
            decline_ratio: 0.25,
            flourish_ratio: 0.70,
            qi_scale: 2.4,

            injury_heal_per_day: 0.02,
            starve_days: 40.0,
            fatigue_per_day_work: 0.0,

            ration_adult: 1.0,
            ration_child: 0.5,
            per_worker_day: 5.0,
            land_cap_day: 60.0,
            spoil_per_year: 0.10,
            pack_days: 30.0,
            start_food_days: 90.0,
            store_months: 3.0,
            reach_hops: 2,
            carry_loss_per_hop: 0.05,
            food_price: 0.1,
            season_amp: 0.35,

            start_gold: 40.0,
            keep_gold: 10.0,
            spend_rate: 2.0,
            mine_gold_per_year: 8000.0,

            eco_cap: 400.0,
            eco_regen_per_day: 0.004,
            harvest_per_trip: 12.0,
            material_price: 1.5,

            travel_speed: 3.0,
            travel_speed_per_realm: 0.35,

            death_margin: 1.6,
            duel_friendly_mult: 4.0,
            decay_per_fight: 0.25,
            hawkes_alpha: 0.35,
            hawkes_decay_days: 720.0,
            grudge_on_kill: 3,
            grudge_half_life_years: 6.0,

            found_sect_realm: 4,
            sect_join_realm_max: 4,
            sect_tithe: 0.10,

            news_per_hop_days: 6.0,

            world_tick_days: 30,
            log_keep: 20000,
        }
    }
}

impl Config {
    pub fn realm_cap_of_tier(&self, tier: u8) -> u8 {
        (tier + 1) * self.realm_band - 1
    }
}
