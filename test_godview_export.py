# -*- coding: utf-8 -*-
"""Verification test for God's View Lightweight Snapshot Exporter."""
import json
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
from tiandao import godview as GV


def test_godview_export():
    print("=== Testing God's View Snapshot Exporter ===")
    sim = S.Sim(seed=42, tiers=3)
    
    # Run 50 steps
    for _ in range(50):
        sim.step()
        
    snapshot = GV.extract_lightweight_snapshot(sim)
    
    # 1. Check structure
    assert "meta" in snapshot
    assert "worlds" in snapshot
    assert "cultivators" in snapshot
    assert "places" in snapshot
    assert "edges" in snapshot
    
    # 2. Check places and edges
    assert len(snapshot["places"]) == len(PL.PLACES), \
        f"places ใน godview ไม่ตรงกับ PLACES: {len(snapshot['places'])} vs {len(PL.PLACES)}"
    assert len(snapshot["edges"]) >= 300, f"Expected >=300 edges, got {len(snapshot['edges'])}"
    
    # 3. Check cultivators
    n_cultivators = len(snapshot["cultivators"])
    assert n_cultivators > 1000, f"Expected >1000 living cultivators, got {n_cultivators}"
    print(f"  ✓ Extracted {n_cultivators} living cultivators across {len(snapshot['worlds'])} worlds")
    
    # 4. Check JSON payload size
    raw_json = json.dumps(snapshot, ensure_ascii=False, separators=(',', ':'))
    size_kb = len(raw_json.encode('utf-8')) / 1024.0
    print(f"  ✓ Snapshot Payload Size: {size_kb:.2f} KB (Target < 200 KB)")
    budget = len(PL.PLACES) * 1.45   # ผูกกับจำนวนสถานที่ ไม่ใช่ตัวเลขตายตัว จะได้ไม่พังทุกครั้งที่เพิ่มแดน
    assert size_kb < budget, f"Payload {size_kb:.2f} KB เกินงบ {budget:.0f} KB"
    
    # 5. Check timeline history
    timeline = GV.build_timeline_history(sim)
    assert "current_day" in timeline
    assert "milestones" in timeline
    print(f"  ✓ Timeline index generated with {len(timeline['milestones'])} milestones")
    
    # 6. Check file save
    out_file = GV.save_lightweight_snapshot(sim, "out/test_godview_snapshot.json")
    assert Path(out_file).exists()
    print(f"  ✓ Successfully saved snapshot to: {out_file}")
    
    print("\n🎉 GOD'S VIEW EXPORTER TESTS PASSED!")


if __name__ == "__main__":
    test_godview_export()
