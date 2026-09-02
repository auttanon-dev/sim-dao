# -*- coding: utf-8 -*-
"""Phase J — Shadow Evaluation Gate CLI: เทียบ LoRA ที่เพิ่งเทรน (`train_lora.py`/`autotrain.py`)
กับ baseline (โมเดลฐานเปล่า หรือ LoRA เวอร์ชันก่อนหน้าที่ deploy อยู่) ผ่าน Phase D Validator/Scoring
ตัวจริง — อนุมัติ (exit 0) ถ้าคะแนนเฉลี่ย >= baseline เท่านั้น (ตาม `ROLE (2).MD`)

    python evaluate_model.py --candidate-lora loras/v1 --n-scenes 15
    python evaluate_model.py --candidate-lora loras/v2 --baseline-lora loras/v1 --n-scenes 15

ไม่ approve อัตโนมัติแล้ว hot-swap เอง — เป็นแค่ตัวตัดสิน (`hotswap.py` เรียกแยกอีกที และเช็ค exit code
นี้ก่อนจะไปแปลง GGUF/deploy จริง)
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from narrative_factory import parser as P
from narrative_factory import scene_extractor as SE
from narrative_factory import shadow_eval as SHE
from tiandao import event_log as EL
from tiandao import persist as PS


def _pick_benchmark_scenes(scenes, n: int, seed: int = 20260830):
    import random
    rng = random.Random(seed)
    pool = list(scenes)
    rng.shuffle(pool)
    return pool[:n]


def _load_held_out_scene_ids(lora_dir):
    """โหลด `{lora_dir}/held_out_scene_ids.json` ที่ `train_lora.py` เขียนไว้ตอนเทรน (ข้อ 3) — คืน
    `None` ถ้าไม่มีไฟล์ (LoRA เก่าก่อนมีกลไกนี้) หรือ `eval_ratio=0` ตอนเทรน (ไม่มี held-out จริง)"""
    if not lora_dir:
        return None
    p = Path(lora_dir) / "held_out_scene_ids.json"
    if not p.exists():
        return None
    data = json.loads(p.read_text(encoding="utf-8"))
    if not data.get("enabled") or not data.get("scene_ids"):
        return None
    return data


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--save-path", default=None, help="ดีฟอลต์ tiandao/persist.DEFAULT_PATH")
    ap.add_argument("--event-log-path", default=None)
    ap.add_argument("--base-model", default="scb10x/typhoon2.5-qwen3-4b")
    ap.add_argument("--candidate-lora", required=True, help="เช่น loras/v1 — ตัวที่จะพิจารณา deploy")
    ap.add_argument("--baseline-lora", default=None,
                     help="LoRA เวอร์ชันก่อนหน้าที่ deploy อยู่ตอนนี้ (ไม่ใส่ = เทียบกับโมเดลฐานเปล่า "
                          "เหมาะกับการ deploy ครั้งแรก)")
    ap.add_argument("--n-scenes", type=int, default=15,
                     help="จำนวนฉาก benchmark (ROLE (2).MD แนะนำ 50 — ลดลงเพื่อเวลา/GPU จริง)")
    ap.add_argument("--max-new-tokens", type=int, default=300)
    ap.add_argument("--out", default=None, help="ดีฟอลต์ datasets/eval_results/eval_{timestamp}.json")
    a = ap.parse_args()

    save_path = a.save_path or PS.DEFAULT_PATH
    sim = PS.load_sim(save_path)
    event_log_path = a.event_log_path or EL.default_log_path(save_path)
    parsed = P.parse_log(sim, event_log_path)
    scenes = SE.extract_scenes(parsed, sim)
    by_cid = SE.index_by_character(parsed)
    cfg = P.load_config()

    held_out = _load_held_out_scene_ids(a.candidate_lora)
    if held_out:
        held_out_ids = set(held_out["scene_ids"])
        pool = [s for s in scenes if s.scene_id in held_out_ids]
        n_pick = min(a.n_scenes, len(pool))
        benchmark = _pick_benchmark_scenes(pool, n_pick)
        print(f"[evaluate_model] ใช้ held-out split จริงจาก {a.candidate_lora}/held_out_scene_ids.json "
              f"— {len(pool)}/{len(held_out_ids)} ฉาก held-out ยังอยู่ในโลกนี้จริง สุ่มมา {len(benchmark)} "
              f"ฉาก (ไม่เคยผ่านตาโมเดลนี้ตอนเทรนแน่นอน — ผลสะท้อน generalization จริง ไม่ใช่แค่จำได้)")
        if n_pick < a.n_scenes:
            print(f"[evaluate_model] คำเตือน: ขอ --n-scenes {a.n_scenes} แต่ held-out pool มีแค่ "
                  f"{len(pool)} ฉาก — ใช้เท่าที่มี")
    else:
        benchmark = _pick_benchmark_scenes(scenes, a.n_scenes)
        print(f"[evaluate_model] benchmark {len(benchmark)} ฉาก (สุ่มจาก {len(scenes)} ฉากทั้งหมด, "
              f"seed คงที่เพื่อเทียบซ้ำได้)")
        print(f"[evaluate_model] คำเตือน: ไม่พบ {a.candidate_lora}/held_out_scene_ids.json (LoRA เก่า "
              "ก่อนมีกลไกนี้ หรือเทรนด้วย eval_ratio=0) — ฉาก benchmark อาจซ้อนกับฉากที่เคยเทรนมาแล้ว "
              "ผลที่ได้อาจสะท้อนแค่ \"จำได้\" ไม่ใช่ \"เขียนเก่งขึ้นจริง\"")
    baseline_label = a.baseline_lora or f"{a.base_model} (ฐานเปล่า ไม่มี LoRA)"
    print(f"[evaluate_model] candidate={a.candidate_lora} vs baseline={baseline_label}")

    print(f"[evaluate_model] ประเมิน baseline ({baseline_label}) ... (โหลดโมเดลจริง, ใช้เวลาสักครู่)")
    baseline_result = SHE.run_eval(a.base_model, benchmark, sim, by_cid, cfg,
                                    adapter_path=a.baseline_lora, label=baseline_label,
                                    max_new_tokens=a.max_new_tokens)
    print(f"[evaluate_model] baseline: mean_score={baseline_result.mean_score:.1f} "
          f"pass_rate={baseline_result.pass_rate:.0%} (n={baseline_result.n})")

    print(f"[evaluate_model] ประเมิน candidate ({a.candidate_lora}) ...")
    candidate_result = SHE.run_eval(a.base_model, benchmark, sim, by_cid, cfg,
                                     adapter_path=a.candidate_lora, label=a.candidate_lora,
                                     max_new_tokens=a.max_new_tokens)
    print(f"[evaluate_model] candidate: mean_score={candidate_result.mean_score:.1f} "
          f"pass_rate={candidate_result.pass_rate:.0%} (n={candidate_result.n})")

    approved = candidate_result.mean_score >= baseline_result.mean_score
    verdict = "APPROVE" if approved else "REJECT"
    print(f"[evaluate_model] === {verdict} === candidate {candidate_result.mean_score:.1f} "
          f"{'>=' if approved else '<'} baseline {baseline_result.mean_score:.1f}")

    out_path = Path(a.out) if a.out else Path("datasets/eval_results") / (
        f"eval_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "candidate": a.candidate_lora, "baseline_label": baseline_label, "base_model": a.base_model,
        "n_scenes": len(benchmark), "held_out_split_used": held_out is not None, "approved": approved,
        "baseline_result": {"mean_score": baseline_result.mean_score, "pass_rate": baseline_result.pass_rate,
                             "per_scene": [vars(s) for s in baseline_result.per_scene]},
        "candidate_result": {"mean_score": candidate_result.mean_score, "pass_rate": candidate_result.pass_rate,
                              "per_scene": [vars(s) for s in candidate_result.per_scene]},
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"[evaluate_model] บันทึกผลละเอียดที่ {out_path}")

    sys.exit(0 if approved else 1)


if __name__ == "__main__":
    main()
