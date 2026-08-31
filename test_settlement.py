# -*- coding: utf-8 -*-
"""Verification test for Procedural Settlement Generator."""
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
from tiandao import sim as S
from tiandao import settlement as SETTLE


def test_settlements():
    print("=== Testing Watabou-Style Settlement Generator ===")
    sim = S.Sim(seed=42, tiers=3)
    for _ in range(30):
        sim.step()
        
    test_places = [
        ("นครหลวงสยามมุระ", "siam"),
        ("นครหลวงเกียวโตโบราณ", "fusang"),
        ("นครกระโจมทองคำข่าน", "steppe"),
        ("มหานครโอเอซิสมรกต", "oasis"),
        ("มหานครพาราณสีโบราณ", "bharata"),
        ("วังโอสถสวรรค์", 1),
        ("พระราชวังทมิฬนิรันดร์", "mara"),
        ("เมืองท่าสัตตบงกช", 0)
    ]
    
    for name, rk in test_places:
        idx = PL.place_index(name)
        data = SETTLE.generate_settlement_layout(idx, sim)
        
        assert data["name"] == name
        assert data["realm_key"] == rk
        assert len(data["wards"]) >= 3, f"Expected >=3 wards, got {len(data['wards'])}"
        assert len(data["roads"]) >= 2, f"Expected >=2 roads, got {len(data['roads'])}"
        assert len(data["buildings"]) >= 10, f"Expected >=10 buildings, got {len(data['buildings'])}"
        
        print(f"  ✓ [{rk}] '{name}': {len(data['wards'])} Wards, {len(data['buildings'])} Buildings, {data['total_occupants']} Occupants, Wall: {data['city_wall'] is not None}")
        
    print("\n🎉 SETTLEMENT GENERATOR TESTS PASSED!")


if __name__ == "__main__":
    test_settlements()
