# -*- coding: utf-8 -*-
"""Verification test for all 10 realms, 4 cultural sister realms, skills, geography, and terrain."""
import sys
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from tiandao import places as PL
from tiandao import skills as SK
from tiandao import geo as GEO
from tiandao import travel as TR
from tiandao import terrain as TERRAIN
from tiandao import sim as S
from tiandao import config as C


def test_places_and_gates():
    print("=== 1. Checking Places & Gates ===")
    assert len(PL.PLACES) == 182, f"Expected 182 places, got {len(PL.PLACES)}"
    assert len(GEO.COORDS) == 182, f"Expected 182 coords, got {len(GEO.COORDS)}"
    assert len(GEO.EDGES) >= 300, f"Expected >=300 edges, got {len(GEO.EDGES)}"

    # Check that each realm has places
    realms = [0, 1, 2, "mara", "chaos", "siam", "fusang", "steppe", "oasis", "bharata"]
    for rk in realms:
        pl = PL.places_in(rk)
        min_p = 5 if rk == "chaos" else 10
        assert len(pl) >= min_p, f"Realm {rk} has too few places: {len(pl)}"
        print(f"  ✓ Realm {rk}: {len(pl)} places")

    # Check gates
    for gate_name in [
        "ประตูมิติทวาราวดีข้ามภพ",
        "ประตูเสาโทริอิสวรรค์ข้ามภพ",
        "ประตูเสาอินทรีเหินข้ามภพ",
        "ประตูตะเกียงวิเศษข้ามภพ",
        "ประตูดอกบัวสหัสวรรษข้ามภพ",
    ]:
        assert gate_name in PL.GATES, f"Missing gate: {gate_name}"
        print(f"  ✓ Found gate: {gate_name}")


def test_cultural_skills():
    print("\n=== 2. Checking Cultural Skills ===")
    skill_names = [s[0] for s in SK.SKILLS]
    
    cultural_samples = [
        "แม่ไม้มวยไทยเก้าท่าจอมราชันย์",
        "วิชาดาบอิไอสวรรค์ตัดมิติพริบตา",
        "มหาศรเทพอินทรีทะลวงเก้าชั้นฟ้า",
        "มหาศาสตร์เล่นแร่แปรธาตุศิลานักปราชญ์",
        "มหาคัมภีร์กายเพชรวัชระอมตะ",
    ]
    for sn in cultural_samples:
        assert sn in skill_names, f"Missing skill: {sn}"
        assert sn in SK.REQUIREMENTS, f"Missing skill requirements: {sn}"
        print(f"  ✓ Skill '{sn}' verified with requirements: '{SK.REQUIREMENTS[sn][:35]}...'")


def test_cross_realm_travel():
    print("\n=== 3. Checking Cross-Realm Travel & Shortest Paths ===")
    # Siam to Fusang
    siam_idx = PL.place_index("นครหลวงสยามมุระ")
    fusang_idx = PL.place_index("นครหลวงเกียวโตโบราณ")
    dist_sf = TR.shortest_path_distance(siam_idx, fusang_idx)
    assert dist_sf < 99999.0, "Path from Siam to Fusang is disconnected!"
    print(f"  ✓ Path Siam -> Fusang: {dist_sf:.1f} units")

    # Steppe to Bharata
    steppe_idx = PL.place_index("นครกระโจมทองคำข่าน")
    bharata_idx = PL.place_index("มหานครพาราณสีโบราณ")
    dist_sb = TR.shortest_path_distance(steppe_idx, bharata_idx)
    assert dist_sb < 99999.0, "Path from Steppe to Bharata is disconnected!"
    print(f"  ✓ Path Steppe -> Bharata: {dist_sb:.1f} units")

    # Oasis to Immortal Realm
    oasis_idx = PL.place_index("มหานครโอเอซิสมรกต")
    immortal_idx = PL.place_index("วังโอสถสวรรค์")
    dist_oi = TR.shortest_path_distance(oasis_idx, immortal_idx)
    assert dist_oi < 99999.0, "Path from Oasis to Immortal Realm is disconnected!"
    print(f"  ✓ Path Oasis -> Immortal Realm: {dist_oi:.1f} units")


def test_terrain_engine():
    print("\n=== 4. Checking Mapgen4 Procedural Terrain Engine ===")
    mesh = TERRAIN.generate_terrain_mesh(grid_size=20)
    assert len(mesh["grid"]) == 20
    assert len(mesh["rivers"]) == 3
    assert len(mesh["realms"]) == 10
    print(f"  ✓ Terrain mesh generated: {mesh['grid_size']}x{mesh['grid_size']} cells, {len(mesh['rivers'])} major rivers, {len(mesh['realms'])} realms")

    places_3d = TERRAIN.get_all_places_data()
    assert len(places_3d) == 182
    print(f"  ✓ 3D places data generated: {len(places_3d)} places with biomes, 3D Z coords")


def test_full_sim_run():
    print("\n=== 5. Checking Simulation Initializing & Step ===")
    sim = S.Sim(seed=123, tiers=3)
    assert len(sim.worlds) == 10, f"Expected 10 worlds in sim, got {len(sim.worlds)}"
    assert len(sim.cast) >= 1000, f"Expected >=1000 cast members, got {len(sim.cast)}"
    print(f"  ✓ Sim initialized cleanly with {len(sim.worlds)} worlds and {len(sim.cast)} characters")
    
    # Run 100 steps
    for _ in range(100):
        sim.step()
    print(f"  ✓ Sim successfully ran 100 steps to day {sim.day}")


if __name__ == "__main__":
    test_places_and_gates()
    test_cultural_skills()
    test_cross_realm_travel()
    test_terrain_engine()
    test_full_sim_run()
    print("\n🎉 ALL TESTS PASSED SUCCESSFULLY!")
