"""Repeatable, isolated simulation balance audit (no saves or learned config touched)."""
import argparse
import collections
import contextlib
import json
import math
import os
from pathlib import Path
import sys
import subprocess
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tiandao.sim import Sim
from tiandao import config as C


def snapshot(sim, steps, seconds, kinds):
    living = sim.living()
    queued = collections.Counter(cid for _, cid in sim.queue if sim.cast[cid].alive)
    errors = []
    if set(queued) != sim.alive_cids:
        errors.append(f"stranded: {sorted(sim.alive_cids - set(queued))[:20]}")
    if any(n != 1 for n in queued.values()):
        errors.append("duplicate living turns")
    actual = collections.Counter(sim.cast[cid].world_id for cid in sim.alive_cids)
    if {c.cid for c in living} != sim.alive_cids or any(not c.alive for c in living):
        errors.append("stale living cache")
    for w in sim.worlds:
        if w.n_alive != actual[w.wid]:
            errors.append(f"population counter mismatch world {w.wid}")
        if not math.isfinite(w.heaven) or w.heaven < 0:
            errors.append(f"invalid heaven world {w.wid}")
    for c in living:
        if any(not math.isfinite(v) or v < 0 for v in c.money.values()):
            errors.append(f"invalid money cid {c.cid}")
    return dict(steps=steps, year=round(sim.day / 365, 2), seconds=round(seconds, 2),
        alive=len(living), cast=len(sim.cast), worlds=len(sim.worlds),
        realms=dict(collections.Counter(c.realm for c in living)),
        dead_causes=dict(collections.Counter(c.death_cause for c in sim.cast if not c.alive)),
        money=sum(sum(c.money.values()) for c in living), items=len(sim.items),
        orgs=len(sim.orgs), active_orgs=sum(o.alive for o in sim.orgs), caches=len(sim.caches),
        tree_alive=getattr(sim, "tree_alive", None), tree_vitality=getattr(sim, "tree_vitality", None),
        lord_returns=sim.cast[sim.lord_cid].lord_returns, lord_pool=sim.lord_pool,
        llm_backlog=len(sim.brain_manager.llm_queue), events=dict(kinds), errors=errors,
        crisis_pressure=getattr(sim, "crisis_pressure", 0),
        campaign=getattr(sim, "chaos_campaign", None),
        traitors=sum(getattr(c, "crisis_traitor", False) for c in sim.cast),
        world_stats=[dict(id=w.wid, name=w.name, tier=w.tier, alive=actual[w.wid],
            heaven_ratio=round(w.ratio(), 4), resource=round(getattr(w, "resource", 0), 2),
            rift=round(w.rift, 3), era=w.era) for w in sim.worlds])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, nargs="+", default=[7, 42, 2029])
    ap.add_argument("--steps", type=int, default=300000)
    ap.add_argument("--every", type=int, default=50000)
    ap.add_argument("--out", default="out/autonomy_audit.json")
    ap.add_argument("--overrides", default="{}", help="JSON config overrides for isolated experiments")
    args = ap.parse_args()
    # Portal construction mutates the module-level geography. Use a fresh
    # interpreter per seed so one universe cannot influence another's audit.
    if len(args.seeds) > 1:
        result = dict(steps_requested=args.steps, overrides=json.loads(args.overrides), seeds={})
        output = Path(args.out)
        output.parent.mkdir(parents=True, exist_ok=True)
        for seed in args.seeds:
            child = output.with_name(f"{output.stem}_seed{seed}.json")
            subprocess.run([sys.executable, "-X", "utf8", __file__, "--seeds", str(seed),
                "--steps", str(args.steps), "--every", str(args.every),
                "--out", str(child), "--overrides", args.overrides], check=True)
            result["seeds"].update(json.loads(child.read_text(encoding="utf-8"))["seeds"])
            output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        return
    overrides = json.loads(args.overrides)
    for name, value in overrides.items():
        if not hasattr(C, name):
            raise ValueError(name)
        setattr(C, name, value)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    report = dict(steps_requested=args.steps, overrides=overrides, seeds={})
    with open(os.devnull, "w", encoding="utf-8") as quiet:
        for seed in args.seeds:
            sim = Sim(seed=seed, tiers=3)
            started = time.monotonic()
            kinds = collections.Counter()
            rows = [snapshot(sim, 0, 0, kinds)]
            report["seeds"][str(seed)] = rows
            for step in range(1, args.steps + 1):
                before = len(sim.log)
                with contextlib.redirect_stdout(quiet):
                    event = sim.step()
                kinds.update(e.kind for e in sim.log[before:])
                if event is None:
                    raise RuntimeError(f"scheduler stopped seed={seed} step={step} day={sim.day}")
                if step % args.every == 0 or step == args.steps:
                    row = snapshot(sim, step, time.monotonic() - started, kinds)
                    rows.append(row)
                    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
                    print(f"seed={seed} steps={step} year={row['year']} alive={row['alive']} errors={len(row['errors'])} seconds={row['seconds']}", flush=True)
                if len(sim.log) > 10000:
                    sim.log = sim.log[-5000:]
    print(f"Report: {out.resolve()}")


if __name__ == "__main__":
    main()
