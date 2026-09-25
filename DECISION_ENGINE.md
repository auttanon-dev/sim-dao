# Decision Engine แบบ Hybrid (`tiandao/decision/`)

ระบบตัดสินใจของ NPC ที่ **อธิบายได้ทุกครั้ง** ว่าทำไมเลือกแบบนั้น — มาจากความต้องการ + เป้าหมาย +
บุคลิก + ความทรงจำ + สิ่งที่ตัวละคร "เชื่อ" + ความสัมพันธ์ + สภาพแวดล้อม + ผลตอบแทน − ความเสี่ยง − ต้นทุน

ไม่ได้รื้อระบบเดิม: เสียบเข้า `Sim._step()` จุดเดียว ถัดจาก `intent.weigh()` → `brain_manager.decide()`
→ `mind.choose()` (ตัวเอก LLM ยังมาก่อน) · feedback ผูกผ่าน `event_bus` · **ปิดเป็นค่าเริ่มต้น**

```
python run.py --seed 3 --events 30000 --decision                 # เปิดใช้
python run.py --seed 3 --events 30000 --decision --explain 1332  # จับตาตัวละคร + พิมพ์เหตุผล
python run.py ... --decision --decision-mode deterministic       # argmax สำหรับดีบัก
python test_decision_engine.py                                   # เทสต์ 17 ข้อ
python -m unittest test_decision_body                            # ร่างกาย→การตัดสินใจ 13 ข้อ (§32, TEST 10)
```
```python
from tiandao import decision as DE
eng = DE.attach(sim)                 # ใช้กับ save เก่าได้ · DE.detach(sim) เพื่อถอด
print(eng.explain_text(cid))         # คำอธิบายการตัดสินใจล่าสุด
print(eng.summary())                 # จำนวนการตัดสินใจ, LOD, goal/plan
```
หรือตั้ง `DECISION_ENGINE_ON = True` ใน `tiandao/config.py` ให้ทุก `Sim` เปิดเอง

## Pipeline

```
Body (กายวิภาค) ─(interoception: §33)─▶ สภาพที่รู้สึก ─▶ PhysicalCapability (§32)
WorldState ─(perception: noise + ปกปิดตามช่องว่างขั้น)─▶ BeliefState
     │                                                    │
Needs · Personality · Memory · Relationship · Environment ┤
                                                          ▼
All Actions → Requirement (intent.weigh เดิม + requirements) → Context filter → LOD limit
                                                          ▼
Goal Selection (Utility: "ต้องการอะไร") → GOAP A* ("ทำอย่างไร") → Goal Relevance
                                                          ▼
Utility ของทุก (action, target) → Softmax (Boltzmann) → เลือก → Execute (Sim.resolve เดิม)
                                                          ▼
event_bus → Feedback: Memory (RW) · Belief (Kalman) · Relationship · plan progress · ปลุกผู้ถูกกระทำ
```

## ร่างกายเข้ามาในสมการอย่างไร (§32–33)

ก่อนตัดสินใจทุกครั้ง adapter ถาม `tiandao.body` ว่าร่างนี้ทำอะไรได้ แล้วใส่คำตอบลง
`AgentState.body` (`PhysicalCapability`) — แกนกลางไม่ import `tiandao.body` เลย โลกที่ไม่มี
แบบจำลองร่างกายได้ `known=False` แล้วทุกจุดกลับไปใช้ HP/stamina เหมือนเดิมทุกประการ

| คำถาม | ใช้ที่ไหน |
|---|---|
| `speed` (m/s) | P(หนีรอด) ของ action ที่ตั้ง `risk: {escape: true}` |
| `effort` 0..1 | ตัวหารของ Energy cost (ความล้า+เลือด+เชื้อเพลิง+อุณหภูมิ **คูณกัน**) |
| `severity` | `AgentState.injuries` → ตัวคูณความเสี่ยง |
| `can_fight` · `can_stand` | requirement `can_attack` / `can_move` + fact ให้ GOAP |
| `can_run` · `arm` · `leg` | fact "เจ็บ" (แทนการดู HP อย่างเดียว) → goal `recover`/`survive` |

**ที่รู้สึก ≠ ที่เป็นจริง** ค่าทั้งหมดข้างบนคิดจาก *สภาพที่เจ้าตัวรู้สึก* (`body.felt`) ซึ่งเพี้ยน
จากของจริงแบบ log-normal และเพี้ยนมากขึ้นเมื่อสมองขาดออกซิเจน ส่วนฟิสิกส์ของโลก
(`rules.py`, `combat.py`) ใช้ของจริงเสมอ คนกล้าจึงประเมินตัวเองเกินจริงแล้วตายได้จริง
ข้อยกเว้นคือข้อเท็จจริงที่เจ้าตัวรู้ได้ทันที (ยังรู้สึกตัวไหม · ยืนอยู่ไหม) ซึ่งอ่านจากของจริง —
ไม่มีใคร "เชื่อว่าตัวเองหมดสติ" ขณะยืนพูดอยู่

## สมการ (ทุกพจน์มาจากคณิตศาสตร์/ฟิสิกส์ที่อธิบายได้ ค่าคงที่อยู่ใน YAML ทั้งหมด)

```
core    = ER·w_er × (1 + w_goal·GR) × clamp(1 + w_pers·PB) × max(min, 1 − w_conf·(1−conf)·aversion)
Utility = core + w_need·NP + w_social·S + w_mem·M + w_env·E + w_legacy·ln(w/ḡ)
               − w_hab·H − w_risk·R − w_energy·EC − w_time·TC − w_res·RC        (clamp ±5)
P(a)    = exp(U_a/T) / Σ exp(U_b/T)                                            Boltzmann
```

| พจน์ | สมการ | ที่มา |
|---|---|---|
| P(ชนะ) | logistic(ln(P_self / P_enemy_ที่เชื่อ) / s) | Bradley–Terry (สมมูล Elo ใน `physics.elo_expected`) |
| Risk | base = injury·E[dmg] + w·death·P(แพ้), E[dmg] = p·(1−√(1−(B/A)²)) + (1−p) → 1−e^(−raw) | กฎกำลังสอง Lanchester (`physics.lanchester`) |
| Belief | τ = c/(1−c), รวมแบบ inverse-variance ใน log-space, τ(t) = τ₀·2^(−age/half-life) | Kalman filter 1 มิติ |
| Perception | ln P̂ = ln P + g·ln(1−conceal) + σ(g)·ε | log-normal measurement, มองคนเหนือกว่าไม่ทะลุ |
| Memory | S(t) = S₀·2^(−Δt/h), h โตตาม importance/intensity; ΔS = η·δ·(1−S/S_max) | Ebbinghaus + Rescorla–Wagner (δ = prediction error) |
| Habituation | h ← h·e^(−Δt/τ) + 1, H = 1 − e^(−h/h₀) | leaky integrator — ทำซ้ำแล้วเบื่อ |
| Time cost | 1 − e^(−ρt), ρ = (1/(f·อายุขัยที่เหลือ))·(1 + g·(0.5−patience)·2) | exponential discounting (Yaari) |
| Energy cost | 1 − e^(−k·s/R), R = stamina×effort ของร่างกาย (ไม่มีร่างกาย: ×(1−fatigue)) | relative depletion |
| P(หนีรอด) | logistic(ln(v_เรา / v_ผู้ไล่ที่เร็วที่สุด) / s) | Bradley–Terry บน **ความเร็ว** ไม่ใช่พลัง (§32) |
| ร่างที่รู้สึก | d̂ = d·(1 − g·b)·exp(σ·ε), σ บานเมื่อออกซิเจนถึงสมองน้อยลง | log-normal interoception (§33) |
| อันตรายสถานที่ | 1 − e^(−λ/λ_cap), λ = Hawkes intensity ของรอยนองเลือด | `physics.hawkes_intensity` เดิม |
| ความจน | D = E[max(0, m_j − m_i)] / (E[m_j] + ε) เทียบคนที่เห็น | relative deprivation (Yitzhaki) |
| Legacy | ln(w/ḡ) — roulette เดิม P ∝ w คือ Boltzmann ของ ln w ที่ T=1 | ใช้ระบบเดิมเป็น log-prior |
| Goal | (Σw·need)(1+g·PB) + u·max(need)² + social + commitment; พอแล้วเมื่อ need < 0.3 | satisficing (Simon) |
| GOAP | A* + backward relevance closure, ต้นทุน = cost + k·attitude·risk | risk-sensitive planning |

## ไฟล์

| ไฟล์ | หน้าที่ |
|---|---|
| `engine.py` | แกนกลาง: candidate → goal/GOAP → scoring → softmax → feedback (ไม่ผูกกับโลก) |
| `scoring.py` | ระบบประเมินกลาง + `Breakdown` (แหล่งความจริงเดียวของ utility/explanation) |
| `context.py` | `AgentState`, `PerceivedEntity`, `Environment`, `AgentMind` (ถาวร), `DecisionContext` |
| `beliefs.py` · `memory.py` · `relationships.py` | Belief/Knowledge · Memory · Social |
| `actions.py` | `ActionSpec` (metadata ล้วน) + registry + requirement predicates |
| `goals.py` · `planner.py` | Goal Selection · GOAP |
| `softmax.py` · `rng.py` | Boltzmann selection · สุ่มจาก hash(seed, cid, seq) ไม่แตะ `sim.rng` |
| `explanation.py` | Decision Explanation (เปิด/ปิดได้ `engine.explain`) |
| `scheduler.py` | AI LOD 0-3 + `AIScheduler` (real-time: combat/active/distant/offscreen) |
| `simdao.py` | adapter เข้ากับเอนจินวิถีสวรรค์ + `capability_of()` (จุดเดียวที่ถาม `tiandao.body`) |
| `config/decision_weights.yaml` | น้ำหนัก, profile ต่อบุคลิก/อาร์คีไทป์, ค่าคงที่ทุกโมดูล |
| `config/actions_simdao.yaml` | metadata ของ 50 event kind + goals + GOAP |
| `config/actions_demo.yaml` | action ทั่วไป (attack/run/help/eat/rest...) ใช้ในเทสต์และเป็นแม่แบบ |

## ตัวอย่าง explanation (จาก `test_decision_engine.py`)

```
NPC: Li Wei   Decision: help_friend_escape → เหม่ย   Final Utility: 141.6   P=0.94   T=0.360
Goal: protect_friend   [protect_friend 72, survive 57]   Plan: help_friend_escape
  Core = Expected Reward 0.45 × Goal Relevance ×2.20 × Personality ×1.28 × Belief Confidence ×1.00 = +125.5
  Need Pressure +10.8 (safety=0.35) · Social +45.4 (เหม่ย ตกอยู่ในอันตราย)
  Risk −25.8 (HP 70%) · Energy −12.3 · Time −2.0
Alternative: run_away 27.6 (P=0.04) · attack_enemy → หมาป่า −3.8 (P=0.02)
```
(ครั้งก่อนเคยถูกหมาป่ากัดเกือบตาย → attack ได้ Memory ติดลบและ risk×ความจำร้าย — จึงเลือกช่วยเพื่อนหนีแทนการสู้)

## ผลที่วัดได้ (seed 9 · 6,000 เหตุการณ์)

| | ระบบเดิม | Decision Engine |
|---|---|---|
| เวลา/เหตุการณ์ | 0.46 ms | 1.22 ms |
| วันที่เดินไป | 883 | 807 |
| ข้ามขั้นสำเร็จ | 24 | 16 |
| Jensen–Shannon ของสัดส่วน event kind | — | 0.073 |
| LOD 0/1/2/3 | — | 598 / 1,383 / 3,491 / 288 |

- ปิด engine = โลกเหมือนเดิมทุกไบต์ (digest ของ log และสถานะ `sim.rng` ตรงกับโค้ดก่อนแก้)
- เปิด engine = reproducible จาก seed และรันต่อจาก save ได้ผลตรงกับรันรวดเดียว (TEST 9)
- เทสต์เดิมที่รันแล้วผ่าน: emotions, minds×4, foresight, hopfield, physics, save_migration,
  scheduler_integrity, world_integrity, world_fixes, autonomy, revenge_timing
- `test_determinism.py` ข้อ 2 (save→load 12,000+4,000) **ล้มตั้งแต่ก่อนแก้** — ลองกับโค้ดต้นฉบับแล้วล้มเหมือนกัน
  ไม่เกี่ยวกับระบบนี้

## ปรับจูน

ทุกอย่างอยู่ใน YAML: `weights` (สมการหลัก) · `profiles` (cautious/reckless/merchant/demon/artisan/
protagonist — เลือกจากอาร์คีไทป์และนิสัย "ขลาดกลัว") · `engine.temperature` · `lod` · `goal_selection`
· action/goal ใหม่เพิ่มใน `actions_simdao.yaml` ได้โดยไม่แตะโค้ด
