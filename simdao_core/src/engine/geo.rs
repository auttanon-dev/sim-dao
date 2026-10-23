//! กราฟถนน — ระยะทางสั้นสุด (Dijkstra) และเพื่อนบ้านภายในไม่กี่ก้าว
//!
//! ผังคงที่ตลอดอายุโปรแกรม จึงคิดครั้งเดียวแล้วแคชระดับโปรเซส (ไม่เข้าเซฟ)

use super::data;
use std::cmp::Ordering;
use std::collections::{BinaryHeap, HashMap};
use std::sync::{Mutex, OnceLock};

pub struct Graph {
    pub adj: Vec<Vec<(u32, f64)>>,
}

static GRAPH: OnceLock<Graph> = OnceLock::new();
static DIST: OnceLock<Mutex<HashMap<u32, std::sync::Arc<Vec<f64>>>>> = OnceLock::new();
static HOPS: OnceLock<Mutex<HashMap<(u32, usize), std::sync::Arc<Vec<(u32, usize)>>>>> = OnceLock::new();

pub fn graph() -> &'static Graph {
    GRAPH.get_or_init(|| {
        let d = data::world();
        let mut adj = vec![Vec::new(); d.places.len()];
        for e in &d.edges {
            if !e.open || e.a >= adj.len() || e.b >= adj.len() {
                continue;
            }
            adj[e.a].push((e.b as u32, e.dist));
            adj[e.b].push((e.a as u32, e.dist));
        }
        Graph { adj }
    })
}

#[derive(PartialEq)]
struct Node(f64, u32);
impl Eq for Node {}
impl Ord for Node {
    fn cmp(&self, o: &Self) -> Ordering {
        o.0.partial_cmp(&self.0).unwrap_or(Ordering::Equal).then_with(|| o.1.cmp(&self.1))
    }
}
impl PartialOrd for Node {
    fn partial_cmp(&self, o: &Self) -> Option<Ordering> {
        Some(self.cmp(o))
    }
}

/// ระยะทางสั้นสุดจาก src ไปทุกที่ (INFINITY = ไปไม่ถึง)
pub fn distances(src: u32) -> std::sync::Arc<Vec<f64>> {
    let cache = DIST.get_or_init(|| Mutex::new(HashMap::new()));
    if let Some(v) = cache.lock().unwrap().get(&src) {
        return v.clone();
    }
    let g = graph();
    let mut dist = vec![f64::INFINITY; g.adj.len()];
    let mut heap = BinaryHeap::new();
    dist[src as usize] = 0.0;
    heap.push(Node(0.0, src));
    while let Some(Node(d, u)) = heap.pop() {
        if d > dist[u as usize] {
            continue;
        }
        for &(v, w) in &g.adj[u as usize] {
            let nd = d + w;
            if nd < dist[v as usize] {
                dist[v as usize] = nd;
                heap.push(Node(nd, v));
            }
        }
    }
    let arc = std::sync::Arc::new(dist);
    cache.lock().unwrap().insert(src, arc.clone());
    arc
}

pub fn distance(a: u32, b: u32) -> f64 {
    distances(a)[b as usize]
}

/// ที่ที่ห่างไม่เกิน max_hops ก้าว (รวมตัวเองที่ 0 ก้าว) เรียงตามก้าวแล้วตามเลขสถานที่
pub fn within(src: u32, max_hops: usize) -> std::sync::Arc<Vec<(u32, usize)>> {
    let cache = HOPS.get_or_init(|| Mutex::new(HashMap::new()));
    if let Some(v) = cache.lock().unwrap().get(&(src, max_hops)) {
        return v.clone();
    }
    let g = graph();
    let mut seen = vec![usize::MAX; g.adj.len()];
    seen[src as usize] = 0;
    let mut frontier = vec![src];
    let mut out = vec![(src, 0usize)];
    for h in 1..=max_hops {
        let mut next = Vec::new();
        for &u in &frontier {
            for &(v, _) in &g.adj[u as usize] {
                if seen[v as usize] == usize::MAX {
                    seen[v as usize] = h;
                    next.push(v);
                }
            }
        }
        next.sort_unstable();
        out.extend(next.iter().map(|&v| (v, h)));
        frontier = next;
    }
    let arc = std::sync::Arc::new(out);
    cache.lock().unwrap().insert((src, max_hops), arc.clone());
    arc
}

/// จำนวนก้าวน้อยสุดระหว่างสองที่ (None = ไม่เชื่อมกัน ภายใน limit ก้าว)
pub fn hops(a: u32, b: u32, limit: usize) -> Option<usize> {
    within(a, limit).iter().find(|(p, _)| *p == b).map(|(_, h)| *h)
}
