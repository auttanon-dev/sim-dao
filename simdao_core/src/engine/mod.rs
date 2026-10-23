//! เอนจินจำลองโลก — สถานะทั้งหมดอยู่ฝั่ง Rust, Python เรียกผ่าน py.rs

pub mod act;
pub mod config;
pub mod conflict;
pub mod cultivation;
pub mod data;
pub mod disease;
pub mod geo;
pub mod items;
pub mod life;
pub mod model;
pub mod mystic;
pub mod py;
pub mod races;
pub mod realms;
pub mod sect;
pub mod sim;
pub mod skills;
pub mod metrics;
pub mod society;
pub mod trades;
pub mod world;

pub use config::Config;
pub use sim::Engine;
