//! เอนจินจำลองโลก — สถานะทั้งหมดอยู่ฝั่ง Rust, Python เรียกผ่าน py.rs

pub mod act;
pub mod config;
pub mod conflict;
pub mod cultivation;
pub mod data;
pub mod geo;
pub mod life;
pub mod model;
pub mod py;
pub mod sect;
pub mod sim;
pub mod world;

pub use config::Config;
pub use sim::Engine;
