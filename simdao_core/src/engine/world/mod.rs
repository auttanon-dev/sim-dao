//! นาฬิกาโลก — ทุก world_tick_days วัน สิ่งที่เกิดกับทุกคนพร้อมกัน
//!
//! ลำดับต่อรอบ: แก่/ฟื้นตัว → อาหาร → ทอง → ธรรมชาติ → ปราณฟ้า → ครรภ์/คลอด → ข่าว → สำนัก
//! บัญชีอาหารและทองปิดได้เสมอ (ดู ledger_* ด้านล่าง และเทสต์ในไฟล์นี้)

mod climate;
mod body;
mod food;
mod gold;
mod kin;

use super::data;
use super::model::*;
use super::sim::Engine;

impl Engine {
    pub fn world_tick(&mut self) {
        let days = self.cfg.world_tick_days as f64;
        self.tick_bodies(days);
        self.tick_weather();
        self.tick_disease(days);
        self.tick_food(days);
        self.tick_gold(days);
        self.tick_nature(days);
        self.tick_heaven(days);
        self.tick_families(days);
        self.deliver_news();
        self.tick_polities(days);
        self.tick_realms(days);
        self.tick_temptation(days);
        for w in 0..self.worlds.len() {
            if matches!(self.worlds[w].kind, WorldKind::Main | WorldKind::Sister) && self.chance(data::k("AUCTION_EVENT_P") * days / 30.0 * 4.0) {
                self.market_auction(w as u16);
            }
        }
        if self.day.rem_euclid(3650) < self.cfg.world_tick_days as i64 {
            self.reseal_lost_legends();
        }
        if self.day.rem_euclid(365) < self.cfg.world_tick_days as i64 {
            self.check_fate();
            self.grant_foresight();
            self.prune_departed();
        }
        let horizon = self.day - 5 * 365;
        for w in self.worlds.iter_mut() {
            w.blood_marks.retain(|&d| d >= horizon);
        }
    }
}
