# -*- coding: utf-8 -*-
"""Verification test for Immersion Extensions: Dialogue, Weather, and Combat Visualizer."""
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

from tiandao import sim as S
from tiandao import dialogue as DLG
from tiandao import weather as WTH
from tiandao import combat_vis as CMB


def test_dialogue_engine():
    print("=== 1. Testing Personality & Dao Dialogue Engine ===")
    sim = S.Sim(seed=42, tiers=3)
    living = sim.living()
    assert len(living) >= 2, "Need at least 2 living cultivators"
    c1, c2 = living[0], living[1]
    
    # Test Encounter
    res = DLG.generate_encounter_dialogue(c1, c2, location_name="โรงเตี๊ยมสยบพยัคฆ์")
    assert "lines" in res
    assert len(res["lines"]) >= 2
    print(f"  ✓ Dialogue generated ({res['context']}):")
    for l in res["lines"]:
        print(f"    [{l['speaker']}]: \"{l['text']}\"")


def test_weather_engine():
    print("\n=== 2. Testing Dynamic Weather Engine ===")
    realms = ["siam", "fusang", "steppe", "oasis", "bharata", 1, "mara", "chaos", 0]
    for rk in realms:
        w = WTH.get_current_weather(day=120, realm_key=rk)
        assert "weather_key" in w
        assert "particle_type" in w
        assert "bonus_stat" in w
        print(f"  ✓ Realm {rk}: {w['name']} (Particle: {w['particle_type']}, Effect: {w['effect_desc']})")


def test_combat_visualizer():
    print("\n=== 3. Testing Tactical Combat Simulator ===")
    sim = S.Sim(seed=42, tiers=3)
    living = sim.living()
    c1, c2 = living[0], living[1]
    
    duel = CMB.simulate_duel(c1, c2, max_rounds=4)
    assert "rounds" in duel
    assert len(duel["rounds"]) >= 1
    assert "winner_name" in duel
    print(f"  ✓ Duel Simulated ({duel['fighter1']['name']} vs {duel['fighter2']['name']}): {len(duel['rounds'])} rounds")
    for r in duel["rounds"][:2]:
        print(f"    [R{r['round']}] {r['commentary']}")
    print(f"    🏆 {duel['summary']}")


if __name__ == "__main__":
    test_dialogue_engine()
    test_weather_engine()
    test_combat_visualizer()
    print("\n🎉 ALL IMMERSION EXTENSIONS TESTS PASSED!")
