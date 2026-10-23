# -*- coding: utf-8 -*-
"""เดินโลกจากเทอร์มินัล

    python run.py --years 50                  # โลกใหม่ seed 0 เดิน 50 ปี แล้วสรุป
    python run.py --seed 7 --years 100 --save # เดินแล้วเซฟไว้ที่ out/world.json
    python run.py --resume --years 20 --save  # เดินต่อจากเซฟ
    python run.py --resume --forever          # เดินไปเรื่อยๆ เซฟทุก 5 ปีของโลก (Ctrl+C เพื่อหยุดและเซฟ)
"""
import argparse
import os
import sys
import time

from simdao import World, DEFAULT_SAVE


def summary(w: World):
    s = w.stats()
    print(f"\nปีที่ {s['year']:.1f} · ประชากร {s['population']:,} คน (เคยเกิด {s['ever_born']:,}) · "
          f"ผู้บำเพ็ญ {s['cultivators']:,} · ขั้นสูงสุด {s['top_realm_name']} · สำนัก {s['sects']}")
    deaths = ", ".join(f"{k} {v:,}" for k, v in sorted(s["deaths"].items(), key=lambda kv: -kv[1]))
    print(f"สาเหตุการตาย: {deaths or '—'}")
    print(f"บัญชีอาหาร: มีจริง {s['food_total']:,.0f} · ตามบัญชี {s['food_ledger']:,.0f} · "
          f"บัญชีทอง: มีจริง {s['gold_total']:,.0f} · ตามบัญชี {s['gold_ledger']:,.0f}")
    for x in w.worlds()[:10]:
        print(f"  {x['name']:<22} ประชากร {x['population']:>5} · ผู้บำเพ็ญ {x['cultivators']:>4} · "
              f"ปราณฟ้า {x['heaven'] / x['cap'] * 100:5.1f}% ({x['state']})")


def main():
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="เดินโลก Sim Dao")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--years", type=float, default=20.0)
    ap.add_argument("--save", action="store_true", help="เซฟเมื่อจบ (ที่ --save-path)")
    ap.add_argument("--resume", action="store_true", help="เดินต่อจากไฟล์เซฟ ถ้ามี")
    ap.add_argument("--save-path", default=DEFAULT_SAVE)
    ap.add_argument("--forever", action="store_true", help="เดินไปเรื่อยๆ เซฟทุก 5 ปีของโลก")
    ap.add_argument("--events", type=int, default=15, help="พิมพ์เหตุการณ์ล่าสุดกี่รายการ")
    a = ap.parse_args()

    w = World.load_or_create(a.save_path, seed=a.seed) if a.resume else World(seed=a.seed)
    print(f"[simdao] seed {w.seed} · วันที่ {w.day} · ประชากร {w.population:,}")
    t0 = time.time()
    if a.forever:
        try:
            while True:
                w.run_years(5)
                w.save(a.save_path)
                s = w.stats()
                print(f"[simdao] ปีที่ {s['year']:.0f} · ประชากร {s['population']:,} · "
                      f"ขั้นสูงสุด {s['top_realm_name']} · เซฟแล้ว")
                if w.population == 0:
                    break
        except KeyboardInterrupt:
            w.save(a.save_path)
            print("\n[simdao] หยุดและเซฟแล้ว")
        return
    w.run_years(a.years)
    print(f"[simdao] เดิน {a.years:g} ปี ใช้เวลา {time.time() - t0:.2f} วินาที")
    for e in reversed(w.recent(a.events)):
        print(f"  ปี {e['day'] / 365:6.1f}  [{e['kind']}] {e['text']}")
    summary(w)
    if a.save:
        w.save(a.save_path)
        print(f"[simdao] เซฟไว้ที่ {os.path.abspath(a.save_path)}")


if __name__ == "__main__":
    main()
