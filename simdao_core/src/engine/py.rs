//! ทางเข้าจาก Python — คืนข้อมูลเป็นสตริง JSON (ห่อเป็น dict/list ใน simdao/__init__.py)

use super::config::Config;
use super::data;
use super::model::*;
use super::sim::Engine;
use pyo3::exceptions::{PyIOError, PyValueError};
use pyo3::prelude::*;
use serde_json::{json, Value};

#[pyclass(module = "simdao_core", name = "Engine")]
pub struct PyEngine {
    pub inner: Engine,
}

fn person_json(e: &Engine, p: &Person, full: bool) -> Value {
    let d = data::world();
    let mut v = json!({
        "id": p.id,
        "name": p.name,
        "gender": if p.female { "หญิง" } else { "ชาย" },
        "age": (p.age(if p.alive { e.day } else { p.death_day }) * 10.0).round() / 10.0,
        "alive": p.alive,
        "world": p.world,
        "place": p.place,
        "place_name": d.places[p.place as usize].name,
        "realm": p.realm,
        "realm_name": d.realm_name(p.realm),
        "cultivator": p.cultivator,
        "profession": d.professions[p.profession as usize].0,
        "sect": p.sect,
        "gold": (p.gold * 100.0).round() / 100.0,
    });
    if full {
        let o = v.as_object_mut().unwrap();
        o.insert("tribe".into(), json!(p.tribe));
        o.insert("origin".into(), json!(d.origins[p.origin as usize].0));
        o.insert("dao".into(), json!(d.dao_names()[p.dao as usize]));
        o.insert("root".into(), json!(p.root));
        o.insert("insight".into(), json!(p.insight));
        o.insert("decay".into(), json!(p.decay));
        o.insert("peak_realm".into(), json!(p.peak_realm));
        o.insert("lifespan".into(), json!(e.lifespan_of(p.id)));
        o.insert("injury".into(), json!(p.injury));
        o.insert("hunger_days".into(), json!(p.hunger_days));
        o.insert("pack".into(), json!(p.pack));
        o.insert("mats".into(), json!(p.mats));
        o.insert("spouse".into(), json!(p.spouse));
        o.insert("parents".into(), json!(p.parents));
        o.insert("children".into(), json!(p.children));
        o.insert("master".into(), json!(p.master));
        o.insert("bonds".into(), json!(p.bonds));
        o.insert("rivals".into(), json!(p.rivals));
        o.insert("kills".into(), json!(p.kills));
        o.insert("sick".into(), json!(p.sick(e.day)));
        o.insert("items".into(), json!(p.items.iter().filter_map(|i| e.items.get(i)).map(|it| json!({"name": it.name, "kind": it.kind, "grade": it.grade, "legend": it.legend})).collect::<Vec<_>>()));
        o.insert("skills".into(), json!(p.skills.iter().zip(p.mastery.iter()).map(|(&s, &m)| json!({"name": super::skills::skills()[s as usize].name, "mastery": m})).collect::<Vec<_>>()));
        o.insert("race".into(), json!(e.race(p.id)));
        o.insert("title".into(), json!(e.title(p.id)));
        o.insert("path".into(), json!(e.path_name(p.id)));
        o.insert("element".into(), json!(super::skills::ELEMENTS[p.element as usize]));
        o.insert("inner".into(), json!(p.inner));
        o.insert("fate".into(), json!(p.fate));
        o.insert("crimes".into(), json!(p.crimes));
        o.insert("breaks".into(), json!(p.breaks));
        o.insert("fails".into(), json!(p.fails));
        o.insert("traits".into(), json!({"fear": p.fear, "greed": p.greed, "compassion": p.compassion, "ambition": p.ambition, "loyalty": p.loyalty}));
        o.insert("process".into(), json!(match &p.process {
            Some(Process::Travel { dest, since, arrive }) => json!({"kind": "travel", "dest": dest, "since": since, "arrive": arrive}),
            Some(Process::Seclusion { since, until }) => json!({"kind": "seclusion", "since": since, "until": until}),
            Some(Process::Jail { until }) => json!({"kind": "jail", "until": until}),
            Some(Process::Dissolved) => json!({"kind": "dissolved"}),
            Some(Process::Hidden { since, until, .. }) => json!({"kind": "hidden", "since": since, "until": until}),
            None => Value::Null,
        }));
        o.insert("death_day".into(), json!(if p.alive { Value::Null } else { json!(p.death_day) }));
        o.insert("death_cause".into(), json!(p.death_cause));
        o.insert("killer".into(), json!(p.killer));
        o.insert("born".into(), json!(p.born));
    }
    v
}

#[pymethods]
impl PyEngine {
    #[new]
    #[pyo3(signature = (seed = 0, config = None))]
    fn new(seed: u64, config: Option<&str>) -> PyResult<Self> {
        let cfg: Config = match config {
            Some(s) => serde_json::from_str(s).map_err(|e| PyValueError::new_err(e.to_string()))?,
            None => Config::default(),
        };
        Ok(PyEngine { inner: Engine::new(seed, cfg) })
    }

    /// เดินไป `steps` เทิร์น คืนจำนวนที่เดินได้จริง (0 = โลกไม่มีใครเหลือ)
    fn run(&mut self, py: Python<'_>, steps: u64) -> u64 {
        let e = &mut self.inner;
        py.detach(|| e.run(steps))
    }

    /// เดินไปจนถึงวันที่ `day`
    fn run_until(&mut self, py: Python<'_>, day: i64) -> u64 {
        let e = &mut self.inner;
        py.detach(|| e.run_until(day))
    }

    #[getter]
    fn day(&self) -> i64 {
        self.inner.day
    }

    #[getter]
    fn seed(&self) -> u64 {
        self.inner.seed
    }

    #[getter]
    fn steps(&self) -> u64 {
        self.inner.steps
    }

    #[getter]
    fn population(&self) -> usize {
        self.inner.alive.len()
    }

    #[getter]
    fn last_seq(&self) -> u64 {
        self.inner.seq
    }

    /// เหตุการณ์ที่ seq > since (เก่าสุดก่อน) สูงสุด limit รายการ
    #[pyo3(signature = (since = 0, limit = 1000, kind = None, person = None))]
    fn events_json(&self, since: u64, limit: usize, kind: Option<&str>, person: Option<Pid>) -> String {
        let out: Vec<&Event> = self
            .inner
            .log
            .iter()
            .filter(|e| e.seq > since)
            .filter(|e| kind.map_or(true, |k| e.kind == k))
            .filter(|e| person.map_or(true, |p| e.actor == Some(p) || e.target == Some(p)))
            .take(limit)
            .collect();
        serde_json::to_string(&out).unwrap()
    }

    fn person_json(&self, id: Pid) -> PyResult<String> {
        let p = self.inner.people.get(id as usize).ok_or_else(|| PyValueError::new_err("ไม่มีคนนี้"))?;
        Ok(person_json(&self.inner, p, true).to_string())
    }

    #[pyo3(signature = (world = None, place = None, alive = true, limit = 100000))]
    fn people_json(&self, world: Option<u16>, place: Option<u32>, alive: bool, limit: usize) -> String {
        let e = &self.inner;
        let it: Box<dyn Iterator<Item = &Person>> = if alive {
            Box::new(e.alive.iter().map(|&i| &e.people[i as usize]))
        } else {
            Box::new(e.people.iter())
        };
        let v: Vec<Value> = it
            .filter(|p| world.map_or(true, |w| p.world == w))
            .filter(|p| place.map_or(true, |q| p.place == q))
            .take(limit)
            .map(|p| person_json(e, p, false))
            .collect();
        Value::Array(v).to_string()
    }

    fn worlds_json(&self) -> String {
        let e = &self.inner;
        let mut pop = vec![0usize; e.worlds.len()];
        let mut cult = vec![0usize; e.worlds.len()];
        for &i in &e.alive {
            let p = &e.people[i as usize];
            pop[p.world as usize] += 1;
            if p.cultivator {
                cult[p.world as usize] += 1;
            }
        }
        let v: Vec<Value> = e
            .worlds
            .iter()
            .map(|w| {
                let state = if w.ratio() >= e.cfg.flourish_ratio {
                    "ยุครุ่งเรือง"
                } else if w.ratio() >= e.cfg.decline_ratio {
                    "ยุคปกติ"
                } else {
                    "ยุคเสื่อม"
                };
                json!({
                    "id": w.id, "name": w.name, "tier": w.tier, "kind": format!("{:?}", w.kind),
                    "up": w.up, "heaven": w.heaven, "cap": w.cap, "state": state,
                    "population": pop[w.id as usize], "cultivators": cult[w.id as usize],
                    "places": w.places,
                })
            })
            .collect();
        Value::Array(v).to_string()
    }

    fn places_json(&self) -> String {
        let e = &self.inner;
        let d = data::world();
        let mut pop = vec![0usize; e.places.len()];
        for &i in &e.alive {
            pop[e.people[i as usize].place as usize] += 1;
        }
        let v: Vec<Value> = d
            .places
            .iter()
            .enumerate()
            .map(|(i, p)| {
                let s = &e.places[i];
                json!({
                    "id": i, "name": p.name, "world": e.place_world[i], "kind": p.kind, "grade": p.grade,
                    "x": p.x, "y": p.y, "material": p.material, "qi": e.qi.get(i), "population": pop[i],
                    "granary": s.granary, "stock": s.stock, "till": s.till, "treasury": s.treasury,
                })
            })
            .collect();
        Value::Array(v).to_string()
    }

    fn edges_json(&self) -> String {
        let d = data::world();
        let v: Vec<Value> = d.edges.iter().map(|x| json!([x.a, x.b, x.dist, x.kind, x.open])).collect();
        Value::Array(v).to_string()
    }

    fn sects_json(&self) -> String {
        let v: Vec<Value> = self
            .inner
            .polities
            .iter()
            .filter(|s| s.kind == crate::engine::polity::PolityKind::Sect)
            .map(|s| {
                json!({"id": s.id, "name": s.name, "world": s.world, "home": s.seat, "founder": s.founder,
                       "leader": s.head(), "founded": s.founded, "members": s.members.len(),
                       "treasury": s.treasury, "alive": s.alive(), "parent": s.parent})
            })
            .collect();
        Value::Array(v).to_string()
    }

    /// สถิติและบัญชี — ส่วนต่างของบัญชีอาหาร/ทองต้องใกล้ศูนย์เสมอ
    fn stats_json(&self) -> String {
        let e = &self.inner;
        let cultivators = e.alive.iter().filter(|&&i| e.people[i as usize].cultivator).count();
        let top = e.alive.iter().map(|&i| e.people[i as usize].realm).max().unwrap_or(0);
        json!({
            "day": e.day, "year": e.day as f64 / 365.0, "steps": e.steps,
            "population": e.alive.len(), "ever_born": e.people.len(), "cultivators": cultivators,
            "top_realm": top, "top_realm_name": data::world().realm_name(top),
            "sects": e.polities.iter().filter(|s| s.kind == crate::engine::polity::PolityKind::Sect && s.alive()).count(),
            "food_total": e.total_food(), "food_ledger": e.ledger_food(),
            "gold_total": e.total_gold(), "gold_ledger": e.ledger_gold(),
            "food": e.ledger.food, "gold": e.ledger.gold, "deaths": e.ledger.deaths, "counts": e.ledger.counts,
        })
        .to_string()
    }

    fn save(&self, path: &str) -> PyResult<()> {
        let tmp = format!("{}.tmp", path);
        let f = std::fs::File::create(&tmp).map_err(|e| PyIOError::new_err(e.to_string()))?;
        serde_json::to_writer(std::io::BufWriter::new(f), &self.inner).map_err(|e| PyIOError::new_err(e.to_string()))?;
        std::fs::rename(&tmp, path).map_err(|e| PyIOError::new_err(e.to_string()))?;
        Ok(())
    }

    #[staticmethod]
    fn load(path: &str) -> PyResult<Self> {
        let f = std::fs::File::open(path).map_err(|e| PyIOError::new_err(e.to_string()))?;
        let mut inner: Engine = serde_json::from_reader(std::io::BufReader::new(f)).map_err(|e| PyValueError::new_err(e.to_string()))?;
        inner.after_load();
        Ok(PyEngine { inner })
    }

    fn config_json(&self) -> String {
        serde_json::to_string(&self.inner.cfg).unwrap()
    }
}
