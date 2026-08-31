# -*- coding: utf-8 -*-
"""เอนจินปรับสมดุลตัวเองข้ามรัน

รันซิมหลายเมล็ดซ้ำๆ วัดผล (พีระมิดขั้น / วัฏจักรยุค / อัตราตั้งองค์กร / การป้องกันโกลาหล)
เทียบกับเป้าหมายใน tiandao/tuning.py แล้วขยับค่าคงที่ใน config.py ทีละก้าว
ค่าที่ปรับได้จะถูกจำไว้ใน tiandao/learned_config.json — python run.py รันครั้งถัดไปจะโหลดมาใช้เอง

    python autotune.py --iterations 6 --events 20000 --seeds 3
    python run.py --seed 3 --events 200000              # ใช้ค่าที่เรียนรู้ไว้โดยอัตโนมัติ
    python run.py --seed 3 --events 200000 --no-autotune # อยากลองค่าตั้งต้นดิบใน config.py
"""
import argparse
import sys

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from tiandao import metrics as M
from tiandao import tuning
from tiandao.sim import Sim

REPORT_KEYS = ("advancement_rate", "pyramid_monotonic", "era_rate", "org_rate", "chaos_defense_rate")


def run_once(seed, events, overrides):
    tuning.apply_overrides(overrides)
    sim = Sim(seed=seed, tiers=3).run(events)
    return M.summarize(sim, events)


def average_metrics(rows):
    out = {}
    for k in set().union(*[r.keys() for r in rows]):
        vals = [r[k] for r in rows if isinstance(r.get(k), (int, float))]
        out[k] = (sum(vals) / len(vals)) if vals else None
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--iterations", type=int, default=6)
    ap.add_argument("--events", type=int, default=20000)
    ap.add_argument("--seeds", type=int, default=3)
    ap.add_argument("--lr", type=float, default=1.0, help="ความเร็วในการขยับค่าเข้าหาเป้าหมาย")
    ap.add_argument("--reset", action="store_true",
                     help="ทิ้งของที่เรียนรู้ไว้เดิม เริ่มจากค่าตั้งต้นใน config.py ใหม่")
    a = ap.parse_args()

    state = {"overrides": {}, "history": []} if a.reset else tuning.load_state()
    overrides = state["overrides"]

    for it in range(1, a.iterations + 1):
        rows = [run_once(seed, a.events, overrides) for seed in range(a.seeds)]
        avg = average_metrics(rows)
        print(f"\n=== รอบที่ {it}/{a.iterations} (events={a.events} x seeds={a.seeds}) ===")
        for k in REPORT_KEYS:
            band = tuning.TARGETS.get(k)
            v = avg.get(k)
            v_show = "ไม่มีตัวอย่าง" if v is None else round(v, 4)
            flag = ""
            if band and v is not None:
                flag = "โอเค" if band[0] <= v <= band[1] else "นอกเป้า"
            print(f"  {k:20s} = {str(v_show):14s} เป้า {band}  {flag}")

        overrides = tuning.propose_update(overrides, avg, learning_rate=a.lr)
        print("  ค่าที่ปรับตอนนี้:", overrides or "(ยังไม่ต้องปรับอะไร — อยู่ในเป้าหมดแล้ว)")

        state["overrides"] = overrides
        state["history"].append({"iter": it, "metrics": avg, "overrides": dict(overrides)})
        tuning.save_state(state)

    print(f"\nบันทึกค่าที่เรียนรู้ไว้ที่ {tuning.DEFAULT_STATE_PATH}")
    print("python run.py จะโหลดค่านี้ไปใช้เองอัตโนมัติในรันถัดไป (ปิดได้ด้วย --no-autotune)")


if __name__ == "__main__":
    main()
