"""Variant setup shared by balance_run.py and trace_child.py. Each run is its own process, so nothing leaks between variants.

  A   committed code (separate repo copy, nothing patched)
  F0  final code, no storage cap, seasons flat         (reference for seasonal isolation)
  C1  no cap, seasonal spoilage only
  C2  no cap, seasonal travel speed only
  C3  no cap, seasonal mishap hazard only
  C4  no cap, all three seasonal effects
  B   cap, seasons flat
  D   final code as it stands (cap + seasons)
"""
from tiandao import food as F, seasons as SE, config as C

SEASONAL = {"C1": ("SPOIL",), "C2": ("TRAVEL_SPEED",), "C3": ("MISHAP",), "C4": ("SPOIL", "TRAVEL_SPEED", "MISHAP"),
            "F0": (), "B": (), "D": ("SPOIL", "TRAVEL_SPEED", "MISHAP")}
NO_CAP = {"F0", "C1", "C2", "C3", "C4"}


def apply(variant):
    if variant == "A":
        return dict(variant="A", note="committed code 32c1478, unpatched")
    keep = SEASONAL[variant]
    for name in ("SPOIL", "TRAVEL_SPEED", "MISHAP"):
        if name not in keep:
            table = getattr(SE, name)
            for k in table:
                table[k] = 1.0
    if variant in NO_CAP:
        # a real "off": no granary is cut, and the release rule sees an unbounded limit (= the pre-cap 90-day rule)
        F._cap_granaries = lambda sim, eaters_at: {spot: float("inf") for spot in sim.granary}
    return dict(variant=variant, cap_enabled=variant not in NO_CAP, store_months=C.FOOD_STORE_MONTHS,
                spoil=dict(SE.SPOIL), travel_speed=dict(SE.TRAVEL_SPEED), mishap=dict(SE.MISHAP))
