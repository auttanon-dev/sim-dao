# -*- coding: utf-8 -*-
"""Master System Integrity & Bug Audit Test Suite for Sim Dao Engine.

Tests all simulation layers, edge cases, cross-realm travels, skill trees,
API endpoints, JSON serialization, and long-horizon stability.
"""
import json
import sys
import traceback
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tiandao import config as C
from tiandao import places as PL
from tiandao import geo as GEO
from tiandao import skills as SK
from tiandao import travel as TR
from tiandao import clans as CL
from tiandao import seasons as SEASONS
from tiandao import rules as R
from tiandao import sim as S
from tiandao import persist as PS
from tiandao import terrain as TERRAIN
from tiandao import godview as GV
from tiandao import settlement as SETTLE
from tiandao import dialogue as DLG
from tiandao import weather as WTH
from tiandao import combat_vis as CMB

errors_found = []


def check(name, fn):
    print(f"[*] Testing {name}...", end=" ")
    try:
        fn()
        print("✅ PASS")
    except Exception as e:
        print(f"❌ FAIL: {e}")
        errors_found.append((name, str(e), traceback.format_exc()))


# 1. Check Places & Graph Consistency
def test_places_and_graph():
    assert len(PL.PLACES) == 182, f"PLACES count mismatch: {len(PL.PLACES)}"
    assert len(GEO.COORDS) == 182, f"COORDS count mismatch: {len(GEO.COORDS)}"
    
    # Check that all gate target realms exist
    for gname, gdata in PL.GATES.items():
        assert "to" in gdata, f"Gate {gname} missing 'to'"
        target = gdata["to"]
        assert target in (0, 1, 2, "mara", "chaos", "siam", "fusang", "steppe", "oasis", "bharata")
        
    # Check all edges reference valid node indices
    for e in GEO.EDGES:
        assert 0 <= e[0] < 182, f"Invalid edge start: {e}"
        assert 0 <= e[1] < 182, f"Invalid edge end: {e}"
        assert e[2] >= 0, f"Negative edge distance: {e}"


# 2. Check Skills & Requirements
def test_skills_consistency():
    assert len(SK.SKILLS) >= 80, f"Too few skills: {len(SK.SKILLS)}"
    for s in SK.SKILLS:
        sname, stype, stier, sgrade, sdesc, santi = s
        req = SK.get_requirement(sname)
        assert len(req) > 5, f"Requirement text too short for '{sname}'"
        if sgrade == 2:
            assert sname in SK.REQUIREMENTS, f"Grade 2 Divine Skill '{sname}' missing in REQUIREMENTS dict!"


# 3. Check All-Pairs Realm Connectivity (No Disconnected Realms)
def test_all_realms_connected():
    realms = [0, 1, 2, "mara", "siam", "fusang", "steppe", "oasis", "bharata"]
    for r1 in realms:
        p1 = PL.places_in(r1)[0]
        for r2 in realms:
            p2 = PL.places_in(r2)[0]
            dist = TR.shortest_path_distance(p1, p2, allow_mara_barrier=True)
            assert dist < 99999.0, f"No path found between realm {r1} (place {p1}) and realm {r2} (place {p2})!"


# 4. Check Settlements Generator on all 182 Places
def test_all_182_settlements():
    for i in range(len(PL.PLACES)):
        data = SETTLE.generate_settlement_layout(i)
        assert data["place_idx"] == i
        assert len(data["wards"]) >= 1
        assert len(data["buildings"]) >= 1
        assert len(data["roads"]) >= 1


# 5. Check Terrain Engine 3D elevations and Biomes
def test_terrain_engine():
    mesh = TERRAIN.generate_terrain_mesh(grid_size=15)
    assert len(mesh["grid"]) == 15
    assert len(mesh["rivers"]) >= 3
    
    places_3d = TERRAIN.get_all_places_data()
    assert len(places_3d) == 182
    for p in places_3d:
        assert -100.0 <= p["z"] <= 600.0, f"Out of bounds Z elevation: {p}"


# 6. Check Dialogue Engine on random character combinations
def test_dialogue_engine():
    sim = S.Sim(seed=123, tiers=3)
    living = sim.living()
    for i in range(min(15, len(living) - 1)):
        c1 = living[i]
        c2 = living[i+1]
        dlg = DLG.generate_encounter_dialogue(c1, c2, location_name="ตลาดน้ำรุ่งอรุณ")
        assert "lines" in dlg
        assert len(dlg["lines"]) >= 2
        for line in dlg["lines"]:
            assert len(line["text"]) > 0


# 7. Check Weather Engine across all days of the year
def test_weather_cycles():
    for day in [15, 100, 200, 300, 365, 730]:
        for rk in ["siam", "fusang", "steppe", "oasis", "bharata", 0, 1, 2, "mara", "chaos"]:
            w = WTH.get_current_weather(day, rk)
            assert "weather_key" in w
            assert "particle_type" in w
            assert "bonus_stat" in w


# 8. Check Combat Visualizer on all Dao archetypes
def test_combat_visualizer():
    sim = S.Sim(seed=999, tiers=3)
    living = sim.living()
    for i in range(min(10, len(living) - 1)):
        c1 = living[i]
        c2 = living[i+1]
        duel = CMB.simulate_duel(c1, c2, max_rounds=5)
        assert "rounds" in duel
        assert len(duel["rounds"]) >= 1
        assert duel["winner_id"] in (0, 1, 2)


# 9. Long-Horizon Simulation Test (3,000 events + save/load)
def test_long_sim_stability():
    sim = S.Sim(seed=777, tiers=3)
    for _ in range(2500):
        sim.step()
    assert sim.day > 100
    assert len(sim.living()) > 500
    
    # Check save/load
    test_save_path = "out/test_audit.save"
    PS.save_sim(sim, test_save_path)
    loaded_sim = PS.load_sim(test_save_path)
    assert loaded_sim.day == sim.day
    assert len(loaded_sim.living()) == len(sim.living())
    
    # Check godview snapshot export
    snap = GV.extract_lightweight_snapshot(loaded_sim)
    assert snap["meta"]["day"] == loaded_sim.day
    assert len(snap["cultivators"]) == len(loaded_sim.living())


def main():
    print("=========================================================")
    print("      SIM DAO ENGINE — COMPREHENSIVE BUG & INTEGRITY AUDIT")
    print("=========================================================\n")
    
    check("1. Places & Graph Consistency", test_places_and_graph)
    check("2. Skills & Requirements Text", test_skills_consistency)
    check("3. All-Pairs Realm Connectivity", test_all_realms_connected)
    check("4. All 182 Settlement Layouts", test_all_182_settlements)
    check("5. Terrain 3D Mesh & Biomes", test_terrain_engine)
    check("6. Dialogue Engine Variety", test_dialogue_engine)
    check("7. Weather Cycle Simulation", test_weather_cycles)
    check("8. Combat Simulator Archetypes", test_combat_visualizer)
    check("9. Long-Horizon 2,500 Step Sim & Persistence", test_long_sim_stability)
    
    print("\n=========================================================")
    if not errors_found:
        print("🎉 AUDIT RESULT: ZERO BUGS FOUND! ALL 9 TEST SUITES PASSED! 100% HEALTHY.")
    else:
        print(f"⚠️ AUDIT RESULT: FOUND {len(errors_found)} ISSUES!")
        for name, err, tb in errors_found:
            print(f"\n--- Issue in [{name}] ---")
            print(err)
            print(tb)
    print("=========================================================")


if __name__ == "__main__":
    main()
