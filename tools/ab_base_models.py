# -*- coding: utf-8 -*-
"""A/B โมเดลฐานสำหรับ Layer 3 — ใช้ prompt จริงจาก build_prompt() บนตัวละครจริงในไฟล์ save

ทำไมต้องใช้ prompt จริง: ตอนวัดความเร็วครั้งแรกในเซสชันนี้เราใช้ prompt สั้นๆ ที่เขียนเอง ได้ 3 วิ/ครั้ง
แล้วเอาไปประเมินงานจริงผิดไป 6 เท่า เพราะ prompt จริงมีทั้งความจำ/ความสัมพันธ์/ชื่อเสียง/สถานที่
ยาวกว่ามาก — ห้ามวัดด้วย prompt ปลอมอีก

เกณฑ์ที่วัด (เลือกมาเฉพาะข้อที่กระทบ pipeline นี้จริงๆ):
  json_ok      — parse เป็น JSON ที่มี dialogue/thought ได้เลยไหม (ก่อนเข้า repair logic)
  recovered    — ต้องพึ่ง _parse_response() ซ่อมถึงจะใช้ได้
  unusable     — กู้ไม่ได้เลย (ทั้ง dialogue และ thought ว่าง)
  cjk          — มีอักษรจีน/ญี่ปุ่นปนใน output ไหม (ปัญหาที่เคยเจอจริงกับ qwen2.5vl:7b: 解毒剂)
  same         — dialogue ซ้ำกับ thought เป๊ะๆ (โมเดลขี้เกียจ เคยเจอ "ทำไมต้องตาย?" ทั้งสองช่อง)
  thai_ratio   — สัดส่วนอักษรไทยในข้อความ (ยิ่งสูงยิ่งเป็นไทยล้วน)
  sec/call     — เวลาต่อครั้งจริง ตัวชี้ขาดว่า drain 8,000 งานจะกี่ชั่วโมง
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tiandao import persist as PS
from tiandao.ai import llm_agent as LLM

CJK_RE = re.compile(r"[一-鿿぀-ヿ]")
THAI_RE = re.compile(r"[฀-๿]")


def thai_ratio(s: str) -> float:
    letters = [c for c in s if c.isalpha()]
    if not letters:
        return 0.0
    return sum(bool(THAI_RE.match(c)) for c in letters) / len(letters)


def collect_prompts(sim, n: int):
    """ดึง prompt จริงจากงานที่ค้างอยู่ในคิว LLM (งานเดียวกับที่ drain จะเจอ)"""
    bm = sim.brain_manager
    jobs = bm.llm_queue._jobs[:n]
    out = []
    for job in jobs:
        ch = sim.cast[job.cid] if 0 <= job.cid < len(sim.cast) else None
        if ch is None:
            continue
        brain = bm.get_or_create(job.cid)
        system, user = LLM.build_prompt(ch, brain, sim, job.event)
        out.append((ch.name, job.event.kind, system, user))
    return out


def score_model(model: str, prompts, think_off: bool):
    agent = LLM.OllamaAgent(model=model)
    stats = {"json_ok": 0, "recovered": 0, "unusable": 0, "cjk": 0, "same": 0,
             "http_fail": 0, "thai": [], "secs": [], "samples": []}

    for name, kind, system, user in prompts:
        if think_off:
            user = user + "\n/no_think"
        t0 = time.time()
        raw = agent._post_chat(system, user, response_format="json")
        dt = time.time() - t0
        stats["secs"].append(dt)

        if raw is None:
            stats["http_fail"] += 1
            continue

        # แยกให้ออกระหว่าง "ผ่านเลย" กับ "ต้องซ่อม" — repair logic ปิดบังคุณภาพดิบของโมเดล
        try:
            d = json.loads(LLM._strip_code_fence(raw))
            strict = isinstance(d, dict) and "dialogue" in d and "thought" in d
        except Exception:
            strict = False

        parsed = LLM._parse_response(raw)
        dlg, tht = parsed["dialogue"], parsed["thought"]

        if strict:
            stats["json_ok"] += 1
        elif dlg or tht:
            stats["recovered"] += 1
        else:
            stats["unusable"] += 1
            continue

        blob = f"{dlg} {tht}"
        if CJK_RE.search(blob):
            stats["cjk"] += 1
        if dlg and dlg.strip() == tht.strip():
            stats["same"] += 1
        stats["thai"].append(thai_ratio(blob))
        if len(stats["samples"]) < 3:
            stats["samples"].append((name, kind, dlg, tht))
    return stats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--save-path", default="out/bootstrap_v3.save")
    ap.add_argument("--n", type=int, default=15)
    ap.add_argument("--models", nargs="+", required=True)
    ap.add_argument("--think-off-for", nargs="*", default=[],
                     help="โมเดลที่ต้องต่อ /no_think ท้าย prompt (โมเดลตระกูล reasoning)")
    a = ap.parse_args()

    print(f"[ab] โหลด {a.save_path} ...")
    sim = PS.load_sim(a.save_path)
    prompts = collect_prompts(sim, a.n)
    print(f"[ab] ใช้ prompt จริง {len(prompts)} อัน จากคิวงานที่ค้างอยู่\n")

    results = {}
    for m in a.models:
        think_off = m in a.think_off_for
        print(f"[ab] === {m} {'(/no_think)' if think_off else ''} ===")
        results[m] = score_model(m, prompts, think_off)
        s = results[m]
        n = len(prompts)
        avg = sum(s["secs"]) / max(len(s["secs"]), 1)
        print(f"     json ผ่านเลย {s['json_ok']}/{n} | ต้องซ่อม {s['recovered']} | ใช้ไม่ได้ {s['unusable']} "
              f"| http fail {s['http_fail']}")
        print(f"     อักษรจีนปน {s['cjk']} | dialogue=thought {s['same']} "
              f"| ไทยเฉลี่ย {sum(s['thai'])/max(len(s['thai']),1)*100:.1f}%")
        print(f"     {avg:.1f} วิ/ครั้ง -> drain 8,088 งาน = {avg*8088/3600:.1f} ชม.\n")

    print("=" * 78)
    print(f"{'model':46} {'json':>6} {'cjk':>5} {'ไทย%':>6} {'วิ/ครั้ง':>8}")
    print("=" * 78)
    for m, s in results.items():
        n = len(prompts)
        avg = sum(s["secs"]) / max(len(s["secs"]), 1)
        th = sum(s["thai"]) / max(len(s["thai"]), 1) * 100
        print(f"{m[:46]:46} {s['json_ok']}/{n:<4} {s['cjk']:>5} {th:>5.0f}% {avg:>7.1f}")

    print("\n" + "=" * 78)
    print("ตัวอย่างผลลัพธ์จริง (ตัดสินคุณภาพภาษาด้วยตาเอง)")
    print("=" * 78)
    for m, s in results.items():
        print(f"\n--- {m}")
        for name, kind, dlg, tht in s["samples"]:
            print(f"  [{kind}] {name}")
            print(f"    พูด : {dlg}")
            print(f"    คิด : {tht}")


if __name__ == "__main__":
    main()
