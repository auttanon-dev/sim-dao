# -*- coding: utf-8 -*-
"""A/B เต็มรูปแบบ — วัดทุกงานที่ระบบเรียก LLM จริง ไม่ใช่แค่ Layer 3

งานจริงที่ระบบใช้โมเดล (ไล่จากโค้ด ไม่ได้เดา):
  T1 Layer 3        brain.py:186        .chat()      JSON สั้น {dialogue,thought}
  T2 Scene prose    exporter.py:127     .complete()  ร้อยแก้วฉาก (Dataset A) — วัดด้วย validator/scoring จริง
  T3 Style distill  style_distill.py    .complete()  อ่านนิยายยาว ~6k token แล้วสรุปเป็น JSON
  T4 Episode prose  history.py:127      .complete()  ร้อยแก้วยาวหลายฉาก

T2 คือข้อที่สำคัญที่สุด เพราะให้คะแนนด้วย **ประตูแข็ง 6 กฎของโปรเจกต์เอง** (validator.py) ที่ใช้ตัดสิน
จริงว่า candidate ไหนเข้า dataset ได้ — ไม่ใช่ความเห็นของใคร: ห้ามสร้างตัวละครใหม่ / ห้ามแต่งวันที่ /
ลำดับเวลาต้องถูก / สะกดชื่อต้องเป๊ะ / ขั้นบำเพ็ญต้องตรง / ความสัมพันธ์ต้องตรง
"""
import argparse
import json
import re
import statistics
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

from narrative_factory import context_builder as CB
from narrative_factory import parser as P
from narrative_factory import scene_extractor as SE
from narrative_factory import scoring as SC
from narrative_factory import style_distill as SD
from narrative_factory import validator as VD
from tiandao import event_log as EL
from tiandao import persist as PS
from tiandao.ai import history as HIST
from tiandao.ai import llm_agent as LLM

CJK_RE = re.compile(r"[一-鿿぀-ヿ]")
THAI_RE = re.compile(r"[฀-๿]")
# พยางค์ไทยที่เป็นไปไม่ได้ (สระ/วรรณยุกต์ลอยไม่มีพยัญชนะนำ) — จับ "า่ าน้ก เปี" ที่โมเดลพังๆ พ่นออกมา
GIBBERISH_RE = re.compile(r"(?:^|\s)[ะาิีึืุูำ็่้๊๋์]")


def thai_ratio(s):
    letters = [c for c in s if c.isalpha()]
    return sum(bool(THAI_RE.match(c)) for c in letters) / len(letters) if letters else 0.0


def gibberish_hits(s):
    return len(GIBBERISH_RE.findall(s))


def pct(n, d):
    return f"{n/d*100:.0f}%" if d else "n/a"


# ---------------------------------------------------------------- T1: Layer 3 JSON
def t1_layer3(agent, sim, n, think_off):
    bm = sim.brain_manager
    jobs = bm.llm_queue._jobs[:n]
    ok = cjk = same = gib = 0
    secs, thais = [], []
    for job in jobs:
        ch = sim.cast[job.cid]
        brain = bm.get_or_create(job.cid)
        system, user = LLM.build_prompt(ch, brain, sim, job.event)
        if think_off:
            user += "\n/no_think"
        t0 = time.time()
        raw = agent._post_chat(system, user, response_format="json")
        secs.append(time.time() - t0)
        if raw is None:
            continue
        try:
            d = json.loads(LLM._strip_code_fence(raw))
            if isinstance(d, dict) and "dialogue" in d and "thought" in d:
                ok += 1
        except Exception:
            pass
        p = LLM._parse_response(raw)
        blob = f"{p['dialogue']} {p['thought']}"
        if CJK_RE.search(blob):
            cjk += 1
        if p["dialogue"] and p["dialogue"].strip() == p["thought"].strip():
            same += 1
        gib += gibberish_hits(blob)
        thais.append(thai_ratio(blob))
    return {"n": len(jobs), "json_ok": ok, "cjk": cjk, "same": same, "gibberish": gib,
            "thai": statistics.mean(thais) if thais else 0, "sec": statistics.mean(secs) if secs else 0}


# ---------------------------------------------------------------- T2: scene prose + REAL validator
def t2_scene_prose(agent, sim, scenes, ctx_per_scene, char_log, n, think_off):
    passed = cjk = gib = 0
    scores, secs, thais, samples = [], [], [], []
    for scene in scenes[:n]:
        participants = [c.name for c in sim.cast if c.cid in scene.participants]
        template = "\n".join(f"วันที่ {e.day}: {e.text}" for e in scene.events)
        system = ("คุณคือนักเขียนนิยายกำลังภายในสไตล์จีน เขียนร้อยแก้วบรรยายฉากตามเหตุการณ์ที่ให้มา "
                   "ตามลำดับเป๊ะๆ ห้ามแต่งเหตุการณ์ใหม่ ห้ามข้าม ห้ามสลับลำดับ ห้ามเพิ่มตัวละครที่ไม่มี "
                   "ในรายชื่อผู้เกี่ยวข้อง")
        user = (f"[ผู้เกี่ยวข้อง] {', '.join(participants)}\n"
                f"[เหตุการณ์ตามลำดับ]\n{template}\n\n[งาน] เรียบเรียงเป็นร้อยแก้วสั้นๆ")
        if think_off:
            user += "\n/no_think"
        t0 = time.time()
        text = agent.complete(system, user)
        secs.append(time.time() - t0)
        if not text:
            continue
        res = VD.validate_candidate(text, scene, ctx_per_scene[id(scene)], sim, char_log)
        sc = SC.score_candidate(text, res, scene)
        if res.passed:
            passed += 1
        scores.append(sc.total)
        if CJK_RE.search(text):
            cjk += 1
        gib += gibberish_hits(text)
        thais.append(thai_ratio(text))
        if len(samples) < 1:
            samples.append(text[:300])
    return {"n": min(n, len(scenes)), "gate_passed": passed,
            "score": statistics.mean(scores) if scores else 0,
            "cjk": cjk, "gibberish": gib,
            "thai": statistics.mean(thais) if thais else 0,
            "sec": statistics.mean(secs) if secs else 0, "samples": samples}


# ---------------------------------------------------------------- T3: long-context style distillation
def t3_style(agent, episode_paths, think_off):
    ok = copied = failed = 0
    secs = []
    for p in episode_paths:
        txt = Path(p).read_text(encoding="utf-8")
        t0 = time.time()
        try:
            r = SD.distill_style(txt, agent, source_label=Path(p).name)
        except Exception:
            r = None
        secs.append(time.time() - t0)
        if r is None:
            failed += 1
        else:
            ok += 1
    return {"n": len(episode_paths), "ok": ok, "rejected_or_failed": failed,
            "sec": statistics.mean(secs) if secs else 0}


# ---------------------------------------------------------------- T4: long episode prose
def t4_episode(agent, sim, cids, think_off, event_log_path=None):
    """รับ "รายการ" cid (หลายตัวละคร) แล้วเฉลี่ยผล — เดิมฟังก์ชันนี้รับ cid เดี่ยวแต่ผู้เรียกส่ง list เข้ามา
    ทำให้ get_or_create(list) โยน TypeError: unhashable type ทุกครั้ง = process ตายคาที่ T4 ทุกรอบ
    (เข้าใจผิดอยู่นานว่าเป็นปัญหาสภาพแวดล้อม ที่จริงเป็นบั๊กของ harness เอง)"""
    chars, thais, cjks, gibs, secs, samples = [], [], [], [], [], []
    for cid in cids:
        brain = sim.brain_manager.get_or_create(cid)
        ch = sim.cast[cid]
        ep_scenes = HIST.select_scenes(ch, sim, brain, 4, event_log_path)
        if not ep_scenes:
            continue
        system, user = HIST.build_episode_prompt(ch, sim, brain, ep_scenes)
        if think_off:
            user += "\n/no_think"
        t0 = time.time()
        text = agent.complete(system, user, timeout=180.0, num_ctx=8192)
        secs.append(time.time() - t0)
        if not text:
            continue
        chars.append(len(text))
        thais.append(thai_ratio(text))
        cjks.append(len(CJK_RE.findall(text)))
        gibs.append(gibberish_hits(text))
        if len(samples) < 1:
            samples.append(text[:300])
    return {"n": len(chars),
            "chars": int(statistics.mean(chars)) if chars else 0,
            "thai": statistics.mean(thais) if thais else 0,
            "cjk": sum(cjks), "gibberish": sum(gibs),
            "sec": statistics.mean(secs) if secs else 0,
            "sample": samples[0] if samples else ""}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--save-path", default="out/bootstrap_v3.save")
    ap.add_argument("--models", nargs="+", required=True)
    ap.add_argument("--think-off-for", nargs="*", default=[])
    ap.add_argument("--n-layer3", type=int, default=10)
    ap.add_argument("--n-scenes", type=int, default=8)
    ap.add_argument("--n-episodes-style", type=int, default=2)
    ap.add_argument("--n-episodes-t4", type=int, default=3)
    ap.add_argument("--only", nargs="*", default=["t1", "t2", "t3", "t4"],
                     help="รันเฉพาะ task ที่ระบุ (t1 t2 t3 t4) — T4 ทำให้ process ตายทุกครั้งเมื่อรัน "
                          "ต่อท้าย T1-T3 ในโปรเซสเดียวกัน (ทดสอบ T4 เดี่ยวๆ แล้วผ่านปกติ) จึงต้องแยกรอบรัน")
    ap.add_argument("--novel-dir", default="G:/My Drive/Project/My_AI_Second_Brain/Novel_Episodes")
    a = ap.parse_args()

    print(f"[ab] โหลด {a.save_path} ...")
    sim = PS.load_sim(a.save_path)
    parsed = P.parse_log(sim, EL.default_log_path(a.save_path))
    scenes = SE.extract_scenes(parsed, sim)
    by_cid = SE.index_by_character(parsed)
    # ใช้ฉากที่มีเหตุการณ์พอสมควร จะได้วัด validator ได้มีความหมาย
    # โลกนี้ฉากส่วนใหญ่มีเหตุการณ์เดียว (23,331/23,453) — ใช้เกณฑ์ >=2 ได้ 122 ฉาก พอสำหรับ n=30
    scenes = [s for s in scenes if len(s.events) >= 2][: max(a.n_scenes * 2, 60)]
    cfg = P.load_config()
    # ctx_map ต่อฉาก — validator ต้องใช้ context ของฉากนั้นๆ จริง (ใช้ตัวเดียวกับ exporter.py:288)
    ctx_per_scene = {id(s): CB.build_scene_context(s, sim, by_cid, cfg) for s in scenes[: a.n_scenes]}
    focal_cids = []
    for s_ in scenes:
        if s_.focal_cid not in focal_cids:
            focal_cids.append(s_.focal_cid)
        if len(focal_cids) >= a.n_episodes_t4:
            break
    char_log = by_cid.get(focal_cids[0] if focal_cids else 0, [])
    ep_paths = sorted(Path(a.novel_dir).glob("EPISODE_*.md"))[: a.n_episodes_style]
    print(f"[ab] ฉากทดสอบ {min(a.n_scenes,len(scenes))} | Layer3 {a.n_layer3} | style {len(ep_paths)} ตอน\n")

    # เขียนผลลงไฟล์ทีละโมเดลทันทีที่เสร็จ — รอบก่อนหน้านี้ process ตายแล้วผลหายทั้งหมดเพราะ
    # stdout ถูก buffer ไว้ยังไม่ถูก flush ห้ามให้เกิดซ้ำ
    ckpt = Path("out/ab_full_results.json")
    ckpt.parent.mkdir(parents=True, exist_ok=True)
    R = json.loads(ckpt.read_text(encoding="utf-8")) if ckpt.exists() else {}

    def log(msg):
        print(msg, flush=True)

    def save():
        """merge กับไฟล์บนดิสก์ก่อนเขียนเสมอ — ตอนแรกเขียนทับทั้งไฟล์จาก R ในหน่วยความจำ ทำให้ผลของ
        โปรเซสอื่นที่รันคู่กัน (หรือรันไปก่อนหน้า) หายไปทั้งดุ้น (t4 ของ 3 โมเดลหายมาแล้วครั้งหนึ่ง)"""
        disk = {}
        if ckpt.exists():
            try:
                disk = json.loads(ckpt.read_text(encoding="utf-8"))
            except Exception:
                disk = {}
        for mk, mv in R.items():
            disk.setdefault(mk, {}).update(mv)
        ckpt.write_text(json.dumps(disk, ensure_ascii=False, indent=1), encoding="utf-8")

    for m in a.models:
        toff = m in a.think_off_for
        agent = LLM.OllamaAgent(model=m)
        r = R.get(m, {})
        if all(k in r for k in ("t1", "t2", "t3", "t4")):
            log(f"[ab] ข้าม {m} (ครบทุก task แล้ว)")
            continue
        R[m] = r
        log(f"[ab] ===== {m} {'(/no_think)' if toff else ''} =====")
        if "t1" in a.only and "t1" not in r:
            r["t1"] = t1_layer3(agent, sim, a.n_layer3, toff); save()
        if "t1" in r: log(f"   T1 Layer3   json {r['t1']['json_ok']}/{r['t1']['n']} cjk {r['t1']['cjk']} "
              f"ซ้ำ {r['t1']['same']} มั่ว {r['t1']['gibberish']} {r['t1']['sec']:.1f}s")
        if "t2" in a.only and "t2" not in r:
            r["t2"] = t2_scene_prose(agent, sim, scenes, ctx_per_scene, char_log, a.n_scenes, toff); save()
        if "t2" in r: log(f"   T2 Scene    ผ่านประตู6กฎ {r['t2']['gate_passed']}/{r['t2']['n']} "
              f"คะแนน {r['t2']['score']:.1f}/100 cjk {r['t2']['cjk']} มั่ว {r['t2']['gibberish']} "
              f"{r['t2']['sec']:.1f}s")
        if "t3" in a.only and "t3" not in r:
            r["t3"] = t3_style(agent, ep_paths, toff); save()
        if "t3" in r: log(f"   T3 Style    สำเร็จ {r['t3']['ok']}/{r['t3']['n']} {r['t3']['sec']:.1f}s")
        if "t4" in a.only and "t4" not in r:
            r["t4"] = t4_episode(agent, sim, focal_cids, toff, EL.default_log_path(a.save_path)); save()
        if "t4" in r: log(f"   T4 Episode  n={r['t4']['n']} เฉลี่ย {r['t4']['chars']} ตัวอักษร ไทย {r['t4']['thai']*100:.0f}% "
              f"cjk {r['t4']['cjk']} มั่ว {r['t4']['gibberish']} {r['t4']['sec']:.1f}s\n")
        save()
        log(f"   [เซฟผลลง {ckpt} แล้ว]")

    print("=" * 100)
    print(f"{'model':42} {'T1 json':>8} {'T2 gate':>8} {'T2 score':>9} {'T3 ok':>6} {'T4 ตัวอักษร':>11} {'มั่วรวม':>8}")
    print("=" * 100)
    for m, r in R.items():
        if not all(k in r for k in ("t1", "t2", "t3", "t4")):
            print(f"{m[:42]:42} (ยังไม่ครบ: มี {sorted(r)})")
            continue
        gib = r["t1"]["gibberish"] + r["t2"]["gibberish"] + r["t4"]["gibberish"]
        print(f"{m[:42]:42} {r['t1']['json_ok']}/{r['t1']['n']:<5} "
              f"{r['t2']['gate_passed']}/{r['t2']['n']:<5} {r['t2']['score']:>8.1f} "
              f"{r['t3']['ok']}/{r['t3']['n']:<3} {r['t4']['chars']:>10} {gib:>8}")

    print("\n" + "=" * 100)
    print("ตัวอย่างร้อยแก้ว (T4 Episode) — ตัดสินภาษาด้วยตาเอง")
    print("=" * 100)
    for m, r in R.items():
        if "t4" in r:
            print(f"\n--- {m}\n{r['t4']['sample']}\n")


if __name__ == "__main__":
    main()
