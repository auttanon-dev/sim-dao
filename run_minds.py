# -*- coding: utf-8 -*-
"""เดินโลกที่มีผู้มีจิตใจจากเทอร์มินัล แล้วพิมพ์บันทึกชีวิตออกมาให้อ่านสดๆ

    python run_minds.py --years 5                  # ใช้ Ollama ตามค่าใน tiandao/ai/config_ai.py
    python run_minds.py --provider mock --years 20 # ทดสอบทั้งระบบโดยไม่ต้องเปิดโมเดล
    python run_minds.py --probe                    # ส่งพรอมต์จริงหนึ่งครั้ง ดูคำตอบดิบของโมเดล
    python run_minds.py --provider lmstudio --model google/gemma-4-e4b --years 2

โลกและบันทึกอยู่ที่ out/minds/ (ลบโฟลเดอร์นี้ = เริ่มโลกใหม่)
"""
import argparse
import json
import random
import sys
import textwrap

from tiandao import events as E
from tiandao import intent as IN
from tiandao.mind import backend as B
from tiandao.mind import prompt as PR
from tiandao.mind.runner import MindRunner, RunConfig, open_world


def show(entry):
    t = entry.get("type")
    y = f"[ปี {entry.get('year', '?'):>3}]"
    if t == "decision":
        who = f" กับ {entry['target']}" if entry.get("target") else ""
        dest = f" → {entry['dest']}" if entry.get("dest") else ""
        src = entry.get("source", "")
        print(f"\n{y} {entry['name']} ({entry.get('realm', '')}) @ {entry.get('place', '')}  〔{src}〕")
        if entry.get("thought"):
            print(textwrap.fill(f"   💭 {entry['thought']}", 100, subsequent_indent="      "))
        print(f"   ➜ {entry['action']}{who}{dest}" + (f" — {entry['why']}" if entry.get("why") else ""))
        print(f"   ⚖ {entry['outcome']}: {entry['text']}")
        if entry.get("error"):
            print(f"   ⚠ {entry['error']}")
    elif t == "received":
        print(f"{y} {entry['name']} ← {entry['by']} {entry['action']}: {entry['outcome']} — {entry['text']}")
    elif t == "death":
        print(f"\n{y} ✝ {entry['text']}")
    elif t == "join":
        print(f"{y} ✦ {entry['text']} ({entry.get('identity', '')})")
    elif t == "story":
        print(textwrap.indent(textwrap.fill(entry["story"], 100), "   📜 "))


def probe(args, backend):
    cfg = RunConfig(out_dir=args.out, source_save=args.from_save or "", seed=args.seed, capacity=args.count)
    sim = open_world(cfg, backend, journal=False)
    mind = sim.mind.active()[0]
    ch = sim.cast[mind.cid]
    rng = random.Random(0)
    others = sim.social_pool(ch, sim.world(ch.world_id), rng)
    w = IN.weigh(ch, sim, E.EVENT_TABLE, bool(others), others=others)
    ctx = PR.build(sim, mind, ch, w, others, E.EVENT_TABLE, True)
    print("=== พรอมต์ ===\n" + ctx.user[:3000] + ("\n…" if len(ctx.user) > 3000 else ""))
    print(f"\n=== ส่งให้ {backend.public()} ===")
    try:
        data = backend.think_json(ctx.system, ctx.user)
    except B.ThinkError as exc:
        print(f"✗ {exc}\n  ตรวจว่าเปิด Ollama/LM Studio แล้ว และชื่อโมเดลตรงกับที่ติดตั้ง (ollama list)")
        return 2
    print(json.dumps(data, ensure_ascii=False, indent=2))
    info, steps = PR.parse(data, ctx, sim, E.EVENT_TABLE)
    print("\n=== อ่านได้เป็นแผน ===")
    for s in steps:
        print(" -", s.to_dict())
    if not steps:
        print(" (ไม่มีขั้นที่ทำได้จริง — ตัวละครจะใช้สัญชาตญาณแทน)")
        return 1
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="out/minds")
    ap.add_argument("--from-save", default="", help="คัดลอกโลกเดิมมาเดินต่อ (ครั้งแรกเท่านั้น)")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--count", type=int, default=40, help="จำนวนผู้มีจิตใจ")
    ap.add_argument("--years", type=float, default=1.0)
    ap.add_argument("--steps", type=int, default=0)
    ap.add_argument("--minutes", type=float, default=0.0, help="หยุดเมื่อครบเวลาจริงกี่นาที (0 = ไม่จำกัด)")
    ap.add_argument("--provider", choices=["ollama", "lmstudio", "mock"], default=None)
    ap.add_argument("--model", default=None)
    ap.add_argument("--story-model", default=None)
    ap.add_argument("--base-url", default=None)
    ap.add_argument("--no-story", action="store_true")
    ap.add_argument("--probe", action="store_true", help="ทดสอบโมเดลด้วยพรอมต์จริงหนึ่งครั้งแล้วจบ")
    ap.add_argument("--quiet", action="store_true", help="ไม่พิมพ์บันทึกระหว่างเดิน")
    args = ap.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    backend = B.from_env(args.provider, args.model, args.story_model, args.base_url)
    if args.probe:
        return probe(args, backend)
    cfg = RunConfig(out_dir=args.out, source_save=args.from_save, seed=args.seed, capacity=args.count,
                    story=not args.no_story, max_years=args.years, max_steps=args.steps,
                    max_minutes=args.minutes)
    runner = MindRunner().configure(cfg, backend)
    sim = runner.sim
    print(f"โลกปีที่ {sim.day // 365} · ผู้มีจิตใจ {len(sim.mind.active())} คน · โมเดล {backend.public()}")
    if not args.quiet:
        runner.on_entry = show
    runner.run_blocking()
    print(f"\nจบ: {runner.message} · ปีที่ {sim.day // 365} · {sim.mind.stats}")
    print(f"บันทึกเต็มอยู่ที่ {cfg.journal_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
