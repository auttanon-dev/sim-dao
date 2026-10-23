//! ทอง — ค่าแรง ตลาด และบัญชีที่ต้องปิด

use crate::engine::model::*;
use crate::engine::sim::Engine;

impl Engine {

    // ------------------------------------------------------------------ ทอง
    pub(crate) fn tick_gold(&mut self, days: f64) {
        let ids: Vec<Pid> = self.alive.iter().copied().collect();
        // ใช้จ่ายส่วนเกินเงินเก็บในตลาดท้องถิ่น (สินค้า บริการ) → ลิ้นชักของที่นั้น
        let frac = 1.0 - (-self.cfg.spend_rate * days / 365.0).exp();
        for &id in &ids {
            let p = &self.people[id as usize];
            if p.process.is_some() {
                continue;
            }
            let spend = (p.gold - self.cfg.keep_gold).max(0.0) * frac;
            if spend > 0.0 {
                let place = p.place as usize;
                self.people[id as usize].gold -= spend;
                // ภาษีสำนักของสมาชิก
                if let Some(s) = self.people[id as usize].sect {
                    let tithe = spend * self.cfg.sect_tithe;
                    self.polities[s as usize].treasury += tithe;
                    self.places[place].till += spend - tithe;
                } else {
                    self.places[place].till += spend;
                }
            }
        }
        // เหมือง: ทองใหม่เกิดที่แหล่งแร่ (แหล่งกำเนิดที่ประกาศ) แบ่งตามคนที่อยู่ที่นั่น
        let d = super::data::world();
        let ore_places: Vec<usize> = (0..self.places.len())
            .filter(|&i| self.place_world[i].is_some() && d.places[i].material.as_deref() == Some("แร่"))
            .collect();
        if !ore_places.is_empty() {
            let per = self.cfg.mine_gold_per_year * days / 365.0 / ore_places.len() as f64;
            for i in ore_places {
                let ore = self.places[i].stock[Material::Ore as usize] / self.cfg.eco_cap;
                let g = per * ore.min(1.0);
                self.places[i].till += g;
                self.ledger.gold("mined", g);
            }
        }
        // ค่าแรง: ลิ้นชักจ่ายให้ผู้ใหญ่ที่ทำงานที่นั่น — คนทำนาได้จากค่าข้าว คนอื่นได้จากการใช้จ่าย
        let mut workers: Vec<Vec<Pid>> = vec![Vec::new(); self.places.len()];
        for &id in &ids {
            let p = &self.people[id as usize];
            if p.process.is_none() && self.is_adult(id) && p.injury < 0.6 {
                workers[p.place as usize].push(id);
            }
        }
        for i in 0..self.places.len() {
            let till = self.places[i].till;
            if till <= 0.0 {
                continue;
            }
            if workers[i].is_empty() {
                // ไม่มีใครทำงานที่นี่ — ค่อยๆ ไหลเข้าคลังชุมชน
                let leak = till * 0.1;
                self.places[i].till -= leak;
                self.places[i].treasury += leak;
                continue;
            }
            let pay = till * 0.8;
            let each = pay / workers[i].len() as f64;
            for &w in &workers[i] {
                self.people[w as usize].gold += each;
            }
            self.places[i].till -= pay;
            self.ledger.gold("wages", pay);
        }
        // คลังชุมชนเลี้ยงเด็กกำพร้าและคนยากไร้ที่หิว
        for &id in &ids {
            let p = &self.people[id as usize];
            if !p.alive || p.gold > 1.0 || p.hunger_days <= 0.0 {
                continue;
            }
            let i = p.place as usize;
            let alms = self.places[i].treasury.min(5.0);
            if alms > 0.0 {
                self.places[i].treasury -= alms;
                self.people[id as usize].gold += alms;
                self.ledger.gold("alms", alms);
            }
        }
    }

    pub fn total_gold(&self) -> f64 {
        let people: f64 = self.alive.iter().map(|&i| self.people[i as usize].gold).sum();
        let places: f64 = self.places.iter().map(|p| p.till + p.treasury).sum();
        let sects: f64 = self.polities.iter().map(|s| s.treasury).sum();
        let caches: f64 = self.caches.iter().map(|c| c.gold).sum();
        let ruins: f64 = self.ruin_gold.iter().sum();
        people + places + sects + caches + ruins
    }

    pub fn total_food(&self) -> f64 {
        let packs: f64 = self.alive.iter().map(|&i| self.people[i as usize].pack as f64).sum();
        packs + self.places.iter().map(|p| p.granary).sum::<f64>()
    }

    /// อาหารที่ควรมีตามบัญชี (ต้องเท่ากับ total_food)
    pub fn ledger_food(&self) -> f64 {
        let g = |k: &str| self.ledger.food.get(k).copied().unwrap_or(0.0);
        g("endowed") + g("produced") - g("eaten") - g("spoiled") - g("carried_lost") - g("lost")
    }

    /// ทองที่ควรมีตามบัญชี (ต้องเท่ากับ total_gold)
    pub fn ledger_gold(&self) -> f64 {
        let g = |k: &str| self.ledger.gold.get(k).copied().unwrap_or(0.0);
        g("issued") + g("mined") - g("lost")
    }

    // ------------------------------------------------------------------ ธรรมชาติ
    /// เพดานธรรมชาติของวัตถุดิบชนิดหนึ่งที่สถานที่หนึ่ง — แหล่งที่ประกาศมีเต็ม ที่อื่นมีบ้าง
    pub fn eco_k(&self, place: usize, m: Material) -> f64 {
        let d = super::data::world();
        let full = d.places[place].material.as_deref().and_then(Material::from_th) == Some(m);
        if full { self.cfg.eco_cap } else { self.cfg.eco_cap * 0.15 }
    }
}
