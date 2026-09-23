# -*- coding: utf-8 -*-
"""เทสต์ Decision Engine (tiandao/decision) — TEST 1-10 ตามสเปค + เทสต์การผูกกับ Sim Dao

รันได้ทั้ง `python -m pytest test_decision_engine.py` และ `python test_decision_engine.py`

สถานการณ์สังเคราะห์ (Li Wei กับหมาป่า) ใช้ action ตัวอย่างใน config/actions_demo.yaml
เทสต์ส่วนท้ายรันกับ Sim จริง (seed คงที่) เพื่อยืนยันว่าใช้งานได้กับ simulation เดิม
"""
import contextlib
import hashlib
import io
import math
import os
import pickle
import random
import tempfile

from tiandao.decision import (AgentState, DecisionContext, DecisionEngine, Environment,
                              PerceivedEntity, Relation)
from tiandao.decision import config as DCFG
from tiandao.decision import softmax as SM
from tiandao.decision import yamlish
from tiandao.decision.beliefs import BeliefStore, kalman_fuse, perceive_power
from tiandao.decision.needs import basic_needs, threat_pressure
from tiandao.decision.planner import GoapPlanner
from tiandao.decision.scheduler import AIScheduler

CFG = DCFG.load()
TRAITS = CFG.get("personality.traits")


# ============================================================ ตัวช่วยสร้างสถานการณ์
def engine(mode="stochastic"):
    return DecisionEngine(cfg=CFG, section="demo", mode=mode)


def traits(**kw):
    t = {k: 0.5 for k in TRAITS}
    t.update(kw)
    return t


def scene(eng, name, tr, hp=100, self_power=100.0, wolf=(100.0, 0.7), wolf_truth=None,
          friend=None, needs=None, inventory=None, facts=None, env=None, now=0.0, fatigue=0.0,
          herb_guard=None):
    """หนึ่งจังหวะตัดสินใจ: เจอหมาป่า (ถ้า wolf ไม่ใช่ None) + เพื่อนที่อาจตกอยู่ในอันตราย"""
    m = eng.mind(name, name)
    m.beliefs.observe("power:self", self_power, "self", now, CFG)
    ents, f = [], {"enemy_near": False, "ally_danger": False}
    if wolf is not None:
        m.beliefs.observe("power:wolf", wolf[0], "sight", now, CFG, confidence=wolf[1],
                          truth=wolf_truth if wolf_truth is not None else wolf[0])
        ents.append(PerceivedEntity("wolf", "beast", "หมาป่า", hostile=True,
                                    threatens=("mei",) if friend else ()))
        f["enemy_near"] = True
    if friend is not None:
        ents.append(PerceivedEntity("mei", "npc", "เหม่ย", in_danger=friend[1],
                                    relation=Relation(affection=friend[0], trust=0.8)))
        f["ally_danger"] = friend[1] > 0
    if herb_guard is not None:
        m.beliefs.observe("guardian:valley", herb_guard[0], "rumor", now, CFG, confidence=herb_guard[1])
        f["herb_seen"] = True
    f.update(facts or {})
    st = AgentState(hp=hp, hp_max=100, power=self_power, stamina=80, fatigue=fatigue,
                    inventory=dict(inventory or {}), location="valley", money=50)
    nd = basic_needs(st, {"safety": threat_pressure(ents, m.beliefs, now, CFG, self_power)})
    nd.update(needs or {})
    return DecisionContext(name, name, now, st, nd, tr, m, env or Environment(danger=0.3), ents, facts=f)


def p_action(eng, ctx, action, seed=0):
    d = eng.decide(ctx, random.Random(seed))
    return d.probability_of(action), d


BRAVE = traits(bravery=0.9, caution=0.15, aggression=0.7)
COWARD = traits(bravery=0.15, caution=0.9, aggression=0.2)


# ============================================================ TEST 1 — กล้า vs ขลาด
def test_1_brave_vs_coward_same_enemy():
    eng = engine()
    pb, db = p_action(eng, scene(eng, "brave", BRAVE), "attack_enemy")
    pc, dc = p_action(eng, scene(eng, "coward", COWARD), "attack_enemy")
    rb, rc = db.probability_of("run_away"), dc.probability_of("run_away")
    assert pb > pc + 0.3, (pb, pc)
    assert rc > rb + 0.3, (rb, rc)
    # ความต่างมาจากบุคลิกจริง — PersonalityFactor ของ attack ต่างกัน
    fb = db.option("attack_enemy").factors["personality"].value
    fc = dc.option("attack_enemy").factors["personality"].value
    assert fb > 1.0 > fc
    # ความถี่ที่เลือกจริงเมื่อสุ่มหลาย seed ก็ต่างกัน
    picks_b = sum(eng.decide(scene(eng, "brave", BRAVE), random.Random(s)).action_id == "attack_enemy"
                  for s in range(200))
    picks_c = sum(eng.decide(scene(eng, "coward", COWARD), random.Random(s)).action_id == "attack_enemy"
                  for s in range(200))
    assert picks_b > picks_c + 60, (picks_b, picks_c)


# ============================================================ TEST 2 — หิวมาก
def test_2_hungry_values_food():
    eng = engine()
    full = scene(eng, "full", traits(), wolf=None, inventory={"food": 1}, needs={"hunger": 0.05})
    hungry = scene(eng, "hungry", traits(), wolf=None, inventory={"food": 1}, needs={"hunger": 0.95})
    uf = eng.decide(full, random.Random(0)).utility_of("eat")
    dh = eng.decide(hungry, random.Random(0))
    uh = dh.utility_of("eat")
    assert uh > uf + 0.5, (uh, uf)
    assert dh.option("eat").additive["need_pressure"].raw > 0.9
    assert dh.probability_of("eat") > 0.9
    # ไม่มีอาหาร = requirement ไม่ผ่าน → ไม่มี eat ใน candidate แต่ forage (หาอาหาร) ได้ goal relevance
    noeat = scene(eng, "nofood", traits(), wolf=None, needs={"hunger": 0.95})
    d = eng.decide(noeat, random.Random(0))
    assert d.option("eat") is None
    assert d.goal == "eat" and d.plan and d.plan[0] == "forage", (d.goal, d.plan)


# ============================================================ TEST 3 — HP ต่ำ
def test_3_low_hp_raises_combat_risk():
    eng = engine()
    hi = eng.decide(scene(eng, "hi", traits(), hp=100), random.Random(0)).option("attack_enemy")
    lo = eng.decide(scene(eng, "lo", traits(), hp=15), random.Random(0)).option("attack_enemy")
    assert lo.additive["risk"].raw > hi.additive["risk"].raw + 0.1, \
        (lo.additive["risk"].raw, hi.additive["risk"].raw)
    assert lo.utility < hi.utility
    # need survival สูงขึ้นทำให้ goal เอนไป survive → หนีมากขึ้น
    d = eng.decide(scene(eng, "lo2", traits(), hp=15), random.Random(0))
    assert d.probability_of("run_away") > d.probability_of("attack_enemy")


# ============================================================ TEST 4 — เคยเกือบตายเพราะหมาป่า
def test_4_wolf_trauma_memory_bias():
    eng = engine()
    fresh = eng.decide(scene(eng, "fresh", traits()), random.Random(0)).option("attack_enemy")
    scarred_mind = eng.mind("scarred", "scarred")
    scarred_mind.last = {"action": "attack_enemy", "p_success": 0.6}
    out = eng.feedback(scarred_mind, -30, "attack_enemy", target="wolf_old", target_kind="beast",
                       location="valley", success=False, damage=0.85, near_death=True,
                       note="ถูกหมาป่ากัดจนเกือบตาย")
    assert "foe:beast" in out["memories"] and out["surprise"] > 0.5
    sc = eng.decide(scene(eng, "scarred", traits()), random.Random(0)).option("attack_enemy")
    assert sc.additive["memory"].value < -0.2, sc.additive["memory"]
    assert sc.additive["risk"].raw > fresh.additive["risk"].raw          # risk perception เพิ่ม
    assert sc.utility < fresh.utility - 0.3
    # ความจำจาง (Ebbinghaus) แต่ไม่หายทันที — ห้าปีต่อมายังมีผลน้อยลง
    later = scene(eng, "scarred", traits(), now=5 * 365)
    sl = eng.decide(later, random.Random(0)).option("attack_enemy")
    assert sc.additive["memory"].value < sl.additive["memory"].value < 0.0
    # เจอซ้ำ = ตอกย้ำ (reinforcement)
    tr = scarred_mind.memory.traces["foe:beast"]
    s1 = tr.strength_at(0, CFG)
    eng.feedback(scarred_mind, 0, "attack_enemy", target="wolf_2", target_kind="beast",
                 success=False, damage=0.5, near_death=True)
    assert scarred_mind.memory.traces["foe:beast"].strength_at(0, CFG) > s1
    assert scarred_mind.memory.traces["foe:beast"].count == 2


# ============================================================ TEST 5 — เชื่อผิดว่าศัตรูอ่อน
def test_5_wrong_belief_drives_rational_fight():
    eng = engine()
    tr = traits(bravery=0.7, caution=0.3)
    # WorldState จริง: ศัตรู 900 · BeliefState: 300 (conf 0.55)
    fooled = scene(eng, "fooled", tr, self_power=500, wolf=(300, 0.55), wolf_truth=900)
    knows = scene(eng, "knows", tr, self_power=500, wolf=(900, 0.95), wolf_truth=900)
    pf, df = p_action(eng, fooled, "attack_enemy")
    pk, dk = p_action(eng, knows, "attack_enemy")
    assert pf > 0.5 and pf > pk + 0.3, (pf, pk)
    opt = df.option("attack_enemy")
    assert abs(opt.enemy_power - 300) < 1e-6          # คิดจากความเชื่อ ไม่ใช่ค่าจริง 900
    assert opt.p_success > 0.8                         # Bradley–Terry จากพลังที่เชื่อ 500 vs 300
    # ความคลาดเคลื่อนจากความจริงยังตรวจย้อนได้ (ดีบัก) แต่ scoring ไม่ได้ใช้
    assert fooled.beliefs.beliefs["power:wolf"].error() < -0.6
    # Feedback loop: ปะทะจริงแล้วเห็นพลังเต็มตา → ความเชื่อขยับเข้าหาความจริง → รอบหน้าไม่สู้แล้ว
    eng.feedback(fooled.mind, 1, "attack_enemy", target="wolf", target_kind="beast",
                 success=False, damage=0.6, revealed_power={"wolf": 900})
    v, c = fooled.beliefs.get("power:wolf", 1, CFG)
    assert v > 700 and c > 0.9, (v, c)
    again = scene(eng, "fooled", tr, self_power=500, wolf=None, now=1)
    again.entities.append(PerceivedEntity("wolf", "beast", "หมาป่า", hostile=True))
    again.facts["enemy_near"] = True
    assert eng.decide(again, random.Random(0)).probability_of("attack_enemy") < pf - 0.3


# ============================================================ TEST 6 — เพื่อนในอันตราย
def test_6_friend_in_danger_social_influence():
    eng = engine()
    tr = traits(loyalty=0.8, kindness=0.7)
    close = eng.decide(scene(eng, "close", tr, friend=(0.9, 0.8)), random.Random(0))
    distant = eng.decide(scene(eng, "distant", tr, friend=(0.1, 0.8)), random.Random(0))
    alone = eng.decide(scene(eng, "alone", tr), random.Random(0))
    hc, hd = close.option("help_friend_escape"), distant.option("help_friend_escape")
    assert hc.additive["social"].raw > hd.additive["social"].raw + 0.4
    assert hc.utility > hd.utility
    # โจมตีหมาป่าที่กำลังคุกคามเพื่อน ได้โบนัส "ปกป้อง" / หนีทิ้งเพื่อนถูกหัก
    assert close.option("attack_enemy").additive["social"].raw > alone.option("attack_enemy").additive["social"].raw
    assert close.option("run_away").additive["social"].raw < 0.0
    assert close.goal == "protect_friend"
    assert close.probability_of("help_friend_escape") + close.probability_of("attack_enemy") > 0.8


# ============================================================ TEST 7 — โลภมาก
def test_7_greed_amplifies_material_reward():
    eng = engine()
    greedy = scene(eng, "greedy", traits(greed=0.95, selfishness=0.8), wolf=None, herb_guard=(80, 0.4))
    modest = scene(eng, "modest", traits(greed=0.2, selfishness=0.2), wolf=None, herb_guard=(80, 0.4))
    og = eng.decide(greedy, random.Random(0)).option("gather_herb")
    om = eng.decide(modest, random.Random(0)).option("gather_herb")
    assert og.factors["expected_reward"].raw > om.factors["expected_reward"].raw * 1.5
    assert og.utility > om.utility + 0.2
    assert eng.scorer.valuation("loot", greedy.traits) > 1.5 > eng.scorer.valuation("loot", modest.traits)


# ============================================================ TEST 8 — softmax ไม่เลือกตัวสูงสุดเสมอ
def test_8_softmax_not_always_argmax():
    eng = engine()
    ctx = lambda: scene(eng, "brave", BRAVE)            # attack/run ใกล้กัน
    d0 = eng.decide(ctx(), random.Random(0))
    best = max(d0.options, key=lambda o: o.utility).action_id
    picks = [eng.decide(ctx(), random.Random(s)).action_id for s in range(400)]
    share = picks.count(best) / len(picks)
    assert 0.3 < share < 0.98, share
    assert all(p < 1.0 for p in d0.probabilities)
    # temperature: ต่ำ → เด็ดขาด · สูง → หลากหลาย (entropy เพิ่ม)
    us = [o.utility for o in d0.options]
    assert SM.entropy(SM.softmax(us, 0.02)) < SM.entropy(SM.softmax(us, 0.12)) < SM.entropy(SM.softmax(us, 1.0))
    # deterministic mode = argmax เสมอ (สำหรับดีบัก)
    det = engine("deterministic")
    runs = [det.decide(scene(det, f"b{s}", BRAVE), random.Random(s)) for s in range(20)]
    assert all(d.action_id == max(d.options, key=lambda o: o.utility).action_id for d in runs)
    assert len({d.action_id for d in runs}) == 1


# ============================================================ TEST 9 — seed เดิม = ผลเดิม
def _sim_digest(sim, n=1500):
    h = hashlib.sha256()
    for e in sim.log[-n:]:
        h.update(f"{e.day}|{e.kind}|{e.outcome}|{e.actor}|{e.target}|{e.text}".encode())
    return h.hexdigest()[:16]


def _run_sim(steps, seed=11, sim=None):
    from tiandao import decision as DE
    from tiandao import sim as S
    if sim is None:
        sim = S.Sim(seed=seed, tiers=3)
        DE.attach(sim)
    with contextlib.redirect_stdout(io.StringIO()):
        for _ in range(steps):
            sim.step()
    return sim


def test_9_reproducible_with_same_seed():
    # engine ล้วน
    eng1, eng2 = engine(), engine()
    a = [eng1.decide(scene(eng1, "x", BRAVE), random.Random(s)).action_id for s in range(50)]
    b = [eng2.decide(scene(eng2, "x", BRAVE), random.Random(s)).action_id for s in range(50)]
    assert a == b
    # Sim จริง: รันสองครั้ง + เซฟ→โหลด→เดินต่อ ต้องได้โลกเดียวกัน
    from tiandao import persist as P
    s1, s2 = _run_sim(2500), _run_sim(2500)
    assert _sim_digest(s1) == _sim_digest(s2)
    tmp = os.path.join(tempfile.mkdtemp(), "de.save")
    P.save_sim(s1, tmp)
    loaded = P.load_sim(tmp)
    assert loaded.decision_engine is not None and loaded.decision_engine.minds
    _run_sim(1200, sim=loaded)
    straight = _run_sim(3700)
    assert _sim_digest(loaded) == _sim_digest(straight)


# ============================================================ TEST 10 — explanation ตรงกับค่าจริง
def _check_explanation(dec):
    ex = dec.explanation
    bd = dec.breakdown
    core, total = ex.recomputed_utility()
    assert math.isclose(core, bd.core, rel_tol=1e-9, abs_tol=1e-12)
    clamped = max(bd.utility_min, min(bd.utility_max, total))
    assert math.isclose(clamped, bd.utility, rel_tol=1e-9, abs_tol=1e-12)
    assert math.isclose(ex.utility, bd.utility)
    assert ex.decision == dec.action_id and ex.target == dec.target
    assert math.isclose(ex.probability, dec.probability)
    for k, a in ex.additive.items():
        assert math.isclose(a["value"], bd.additive[k].value)
        assert math.isclose(a["value"], (1 if k not in ("risk", "energy_cost", "time_cost", "resource_cost", "habituation")
                                         else -1) * a["weight"] * a["raw"])
    for k, f in ex.factors.items():
        assert math.isclose(f["factor"], bd.factors[k].value)
    # utility ที่ softmax ใช้คือค่าเดียวกัน
    idx = dec.options.index(bd)
    assert math.isclose(SM.softmax([o.utility for o in dec.options], dec.temperature)[idx], dec.probability)
    assert ex.format_text()


def test_10_explanation_matches_computation():
    eng = engine()
    for s, (tr, fr) in enumerate([(BRAVE, None), (COWARD, (0.9, 0.8)), (traits(), (0.5, 0.5))]):
        _check_explanation(eng.decide(scene(eng, f"n{s}", tr, friend=fr), random.Random(s)))
    sim = _run_sim(1500, seed=5)
    exs = [e for q in sim.decision_engine._explain.values() for e in q]
    assert len(exs) > 20
    for ex in exs:
        core, total = ex.recomputed_utility()
        assert math.isclose(max(-5, min(5, total)), ex.utility, rel_tol=1e-9, abs_tol=1e-12)


# ============================================================ เทสต์เสริม: คณิตศาสตร์/โครงสร้าง
def test_kalman_belief_fusion():
    v, c = kalman_fuse(300, 0.5, 900, 0.5)       # เท่ากัน → geometric mean ใน log-space
    assert math.isclose(v, math.sqrt(300 * 900)) and c > 0.5
    v2, _ = kalman_fuse(300, 0.2, 900, 0.95)      # ข้อมูลมั่นใจกว่าถ่วงมากกว่า
    assert v2 > 800
    b = BeliefStore()
    b.observe("x", 100, "rumor", 0, CFG)
    assert b.confidence("x", 0, CFG) > b.confidence("x", 90, CFG) > b.confidence("x", 400, CFG)
    # มองคนที่สูงกว่าหลายขั้น: เห็นอ่อนกว่าจริงและไม่มั่นใจ
    seen_hi, c_hi = zip(*[perceive_power(1000, 4, CFG, (1, i)) for i in range(200)])
    seen_eq, c_eq = zip(*[perceive_power(1000, 0, CFG, (1, i)) for i in range(200)])
    assert sum(seen_hi) / 200 < sum(seen_eq) / 200 and c_hi[0] < c_eq[0]


def test_goap_planner():
    from tiandao.decision.simdao import build_registry
    from tiandao import events as E
    reg = build_registry(CFG, E.EVENT_TABLE)
    pl = GoapPlanner(CFG, reg)
    p = pl.plan("become_stronger", {"realm_up": True},
                {"at_bottleneck": True, "has_pill": False, "at_furnace": True, "has_materials": True})
    assert p.found and p.steps == ["หลอมยา", "ข้ามขั้น"], p.steps
    p2 = pl.plan("revenge", {"enemy_defeated": True}, {"enemy_near": True, "believe_can_win": False})
    assert p2.found and p2.steps[-1] == "ล้างแค้น" and p2.steps[0] in ("ฝึกวิชา", "บำเพ็ญ"), p2.steps
    p3 = pl.plan("become_stronger", {"realm_up": True}, {"at_bottleneck": True},
                 available={"ปิดด่าน", "เดินทาง"})
    assert p3.steps and p3.steps[0] in ("ปิดด่าน", "เดินทาง")


def test_yaml_fallback_parser_matches_pyyaml():
    try:
        import yaml
    except ImportError:
        return
    for f in DCFG.DEFAULT_FILES:
        with open(os.path.join(DCFG.CONFIG_DIR, f), encoding="utf-8") as fh:
            t = fh.read()
        assert yamlish.loads(t) == yaml.safe_load(t), f


def test_profiles_change_weights():
    assert CFG.profile("cautious")["weights"]["risk"] > CFG.profile("default")["weights"]["risk"]
    assert CFG.profile("reckless")["temperature"] > CFG.profile("default")["temperature"]


def test_scheduler_tiers():
    sch = AIScheduler.from_config(CFG, seed=3)
    assert sch.due("a", 0.0, "combat")
    sch.done("a", 0.0, "combat")
    assert not sch.due("a", 0.1, "combat") and sch.due("a", 1.01, "combat")
    sch.done("b", 0.0, "distant")
    assert not sch.due("b", 9.0, "distant") and sch.due("b", 60.1, "distant")
    sch.done("c", 0.0, "offscreen")
    assert not sch.due("c", 1e6, "offscreen")         # event-driven เท่านั้น
    sch.wake("c")
    assert sch.due("c", 1e6, "offscreen")


# ============================================================ ผูกกับ Sim Dao
def test_sim_default_off_and_old_save_loads():
    from tiandao import sim as S
    s = S.Sim(seed=3, tiers=3)
    assert s.decision_engine is None                 # ค่าเริ่มต้น = ระบบเดิมทุกประการ
    del s.decision_engine                            # จำลอง save ที่เซฟก่อนมีระบบนี้
    old = pickle.loads(pickle.dumps(s))
    _run_sim(300, sim=old)                           # step ได้ตามปกติ
    from tiandao import decision as DE
    eng = DE.attach(old)                             # attach ย้อนหลังให้ save เก่าได้
    _run_sim(300, sim=old)
    assert eng.stats.get("decisions", 0) > 0


def test_sim_integration_behaviour():
    sim = _run_sim(3000, seed=21)
    eng = sim.decision_engine
    summ = eng.summary()
    assert summ["source"]["engine"] > 1000
    assert summ["lod"][0] > 0 and summ["lod"][1] > 0
    assert summ["plans"] > 0 and summ["goal_evals"] > 0
    # ความเชื่อต่อคนอื่นมาจากการมอง (sight) หรือปะทะ (combat) และคลาดเคลื่อนจากความจริงได้
    errs = [b.error() for m in eng.minds.values() for k, b in m.beliefs.beliefs.items()
            if k.startswith("power:") and k != "power:self" and b.error() is not None]
    assert errs and any(abs(e) > 0.05 for e in errs)
    # คนที่ถูกโจมตีจำคนโจมตีได้ (feedback ของผู้ถูกกระทำ)
    assert any(t.startswith("entity:") for m in eng.minds.values() for t in m.memory.traces)
    # ทุกการเลือกที่ engine ทำ เป็น kind ที่ระบบเดิมอนุญาตในจังหวะนั้น (weigh > 0)
    assert all(ex.decision in {e["kind"] for e in __import__("tiandao.events", fromlist=["x"]).EVENT_TABLE}
               for q in eng._explain.values() for ex in q)


if __name__ == "__main__":
    import sys
    import time
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    failed = 0
    for n, f in tests:
        t = time.time()
        try:
            f()
            print(f"✓ {n}  ({time.time() - t:.1f}s)")
        except Exception as ex:                 # noqa: BLE001
            failed += 1
            import traceback
            traceback.print_exc()
            print(f"✗ {n}: {ex!r}")
    print(f"\n{len(tests) - failed}/{len(tests)} ผ่าน")
    sys.exit(1 if failed else 0)
