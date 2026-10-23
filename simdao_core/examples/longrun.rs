//! จำลองระยะยาวแล้วพิมพ์ตัวชี้วัดเป็น CSV — `cargo run --release --example longrun -- <seed> <years> [every]`
use simdao_core::engine::config::Config;
use simdao_core::engine::metrics::Probe;
use simdao_core::engine::sim::Engine;
use std::time::Instant;

fn main() {
    let a: Vec<u64> = std::env::args().skip(1).map(|s| s.parse().unwrap()).collect();
    let (seed, years, every) = (a.first().copied().unwrap_or(1), a.get(1).copied().unwrap_or(100), a.get(2).copied().unwrap_or(10));
    let t0 = Instant::now();
    let mut e = Engine::new(seed, Config::default());
    let build = t0.elapsed().as_secs_f64();
    let mut pr = Probe::new(&e);
    println!("year,alive,cultivators,sects,cities_ruled,gold_people,gold_sects,gold_places,food_delta,gold_delta,steps,events,secs");
    let t1 = Instant::now();
    for y in 1..=years {
        e.run_until(y as i64 * 365);
        pr.sample(&e);
        if y % every == 0 {
            let m = pr.samples.last().unwrap();
            println!("{},{},{},{},{}/{},{:.0},{:.0},{:.0},{:.2e},{:.2e},{},{},{:.2}", y, m.alive, m.cultivators, m.sects, m.cities_ruled, m.cities, m.gold_people, m.gold_sects, m.gold_places, m.food_delta, m.gold_delta, m.steps, m.events, t1.elapsed().as_secs_f64());
        }
    }
    let secs = t1.elapsed().as_secs_f64();
    eprintln!("build {:.2}s · run {:.2}s · {:.0} steps/s · {:.2} sim-years/s", build, secs, e.steps as f64 / secs, years as f64 / secs);
    eprintln!("logged events per world per year:");
    for (w, r) in pr.events_per_world_year() {
        eprintln!("  {} {:<20} {:.1}", w, e.worlds.get(w as usize).map_or("?", |x| x.name.as_str()), r);
    }
    let mut kinds: Vec<_> = pr.kinds.iter().collect();
    kinds.sort_by(|a, b| b.1.cmp(a.1));
    eprintln!("top event kinds: {:?}", &kinds[..kinds.len().min(12)]);
}
