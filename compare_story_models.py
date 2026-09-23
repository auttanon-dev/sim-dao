# -*- coding: utf-8 -*-
"""เทียบคุณภาพ "การแต่งเรื่อง" ระหว่างโมเดลในเครื่อง โดยใช้ฉากจริงจากบันทึกที่รันมาแล้ว

ทำไมเทียบแบบนี้: ถ้าเปลี่ยนโมเดลแล้วรันโลกใหม่ทั้งรอบ จะเทียบไม่ได้เลยเพราะเหตุการณ์ไม่เหมือนกัน
วิธีนี้หยิบ "ฉากเดียวกัน" (พรอมต์ชุดเดียวกันเป๊ะ) ไปให้แต่ละโมเดลเล่า แล้ววางเทียบกันให้คนอ่านตัดสิน
พร้อมตัวเลขที่ตรวจอัตโนมัติได้ (เวลา ความยาว คำสมัยใหม่ ป้ายกำกับหลุด มุมมองการเล่า คำสาบานถูกสาย)

    python compare_story_models.py --scenes 6
    python compare_story_models.py --models cws-typhoon2-8b,qwen3:27b
    python compare_story_models.py --dry-run          # ตรวจท่อว่าทำงาน ไม่เรียกโมเดลจริง
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tiandao.mind import backend as B                       # noqa: E402
from tiandao.mind import config as MC                       # noqa: E402
from tiandao.mind import storyteller as ST                  # noqa: E402
from tiandao import persist as PS                           # noqa: E402
from tiandao import rules as R                              # noqa: E402

INTERESTING = ("ปราบมารได้", "รอดตายด้วยชะตา", "ผูกพัน", "ตาย", "ถูกครอบงำ", "หักหลัง")
MODERN = ("คุณ", "ผม ", "ครับ", "ค่ะ", "ฉัน")
OATHS = ("สาบานต่อจิตเต๋า", "ให้คำมั่นต่อจิตพุทธะ", "สาบานต่อจิตมาร",
         "ให้คำสัตย์ต่อจิตอสูร", "ให้คำสัตย์ต่อจิตวิญญาณบรรพกาล", "ให้คำสัตย์ต่อจิตโกลาหล")


def ollama_models(base_url):
    try:
        with urllib.request.urlopen(base_url.rstrip("/") + "/api/tags", timeout=10) as r:
            data = json.loads(r.read().decode("utf-8"))
        return [m.get("name", "") for m in data.get("models", [])]
    except Exception as exc:                                  # noqa: BLE001
        print(f"อ่านรายชื่อโมเดลจาก Ollama ไม่ได้: {exc}")
        return []


def pick_models(available, wanted):
    """เลือกโมเดลที่จะเทียบ — ถ้าไม่ระบุ เอา typhoon (ตัวที่ใช้อยู่) กับ qwen ตัวใหญ่สุดที่มี"""
    if wanted:
        return [m.strip() for m in wanted.split(",") if m.strip()]
    out = []
    base = next((m for m in available if "typhoon" in m.lower()), None)
    if base:
        out.append(base)
    # เลือกตัวใหญ่ก่อน และตัดโมเดลที่ไม่ได้ทำมาเขียนเรื่อง (embedding / vision / coder) ออก
    def size_of(name):
        nums = [int(x) for x in re.findall(r"(\d{1,3})\s*[bB]\b", name)]
        return max(nums) if nums else 0
    skip = ("embedding", "embed", "vl:", "vision", "coder", "rerank")
    cands = [m for m in available if m not in out and not any(s in m.lower() for s in skip)]
    cands.sort(key=lambda m: (size_of(m), m), reverse=True)
    big = next((m for m in cands if size_of(m) >= 20), None)
    out.append(big or (cands[0] if cands else ""))
    return [m for m in out if m]


def pick_scenes(journal_path, limit):
    """ฉากที่มีคู่กรณีและผลที่น่าเล่า กระจายทั่วไทม์ไลน์ ไม่เอาซ้ำตัวละครเดิมติดกัน"""
    rows = []
    with open(journal_path, encoding="utf-8") as f:
        for line in f:
            try:
                e = json.loads(line)
            except ValueError:
                continue
            if e.get("type") not in ("decision", "received", "event"):
                continue
            if e.get("outcome") not in INTERESTING:
                continue
            if not (e.get("target") or e.get("by")):
                continue
            rows.append(e)
    rows.sort(key=lambda e: e.get("seq", 0))
    if not rows:
        return []
    step = max(1, len(rows) // limit)
    picked, seen = [], set()
    for e in rows[::step]:
        if e.get("cid") in seen and len(picked) < limit:
            continue
        picked.append(e)
        seen.add(e.get("cid"))
        if len(picked) >= limit:
            break
    return picked or rows[:limit]


def checks(text, entry, sim):
    body = ST.clean_story(text)
    first = bool(re.match(r"\s*ข้า", body))
    labels = [p for p in MC.STORY_LEAK_PHRASES if p in text]
    modern = [w for w in MODERN if w in text]
    me = sim.cast[entry["cid"]]
    want = R.oath_form(me)
    oath_used = [o for o in OATHS if o in text]
    oath_ok = (want in text) if (entry.get("action") == "ให้สัญญา" and want in OATHS) else None
    wrapped = len(re.findall(r"(?m)^\s*\[.+\]\s*$", text))
    other = entry.get("target") or entry.get("by") or ""
    place = (entry.get("place") or "").split(" (")[0]
    facts = sum(1 for x in (other, place) if x and x in body)
    return {"chars": len(body), "quotes": len(re.findall(r'["“][^"”\n]{2,}["”]', body)),
            "เล่าเป็นบุรุษที่1": first, "ป้ายกำกับหลุด": labels, "คำสมัยใหม่": modern,
            "ย่อหน้าครอบวงเล็บ": wrapped, "เอ่ยชื่อคู่กรณี/สถานที่": f"{facts}/2",
            "คำสาบานที่ใช้": oath_used, "คำสาบานถูกสาย": oath_ok}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default=os.path.join("out", "minds-compare-5"))
    ap.add_argument("--out", default=os.path.join("out", "story-model-compare"))
    ap.add_argument("--models", default="")
    ap.add_argument("--scenes", type=int, default=6)
    ap.add_argument("--base-url", default="http://localhost:11434")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    journal = os.path.join(a.source, MC.JOURNAL_NAME)
    if not os.path.exists(journal):
        print(f"ไม่พบบันทึก {journal}")
        return 1
    scenes = pick_scenes(journal, a.scenes)
    if not scenes:
        print("ไม่พบฉากที่มีคู่กรณีในบันทึก")
        return 1

    if a.dry_run:
        models = ["mock-a", "mock-b"]
    else:
        available = ollama_models(a.base_url)
        print("โมเดลใน Ollama: " + (", ".join(available) or "(อ่านไม่ได้)"))
        models = pick_models(available, a.models)
        if len(models) < 2:
            print("ต้องมีโมเดลให้เทียบอย่างน้อยสองตัว — ระบุด้วย --models a,b")
            return 1
    print("เทียบ: " + " vs ".join(models))

    # โหลดเซฟตรงๆ ไม่ผ่าน open_world เพราะ open_world จะตัดบันทึกให้ตรงกับ seq ของเซฟ
    # (ถ้าชี้ผิดโฟลเดอร์ บันทึกจริงจะถูกตัดทิ้ง) — ที่นี่เราอ่านอย่างเดียว ไม่แตะไฟล์ของโลก
    save = os.path.join(a.source, "world.save")
    if not os.path.exists(save):
        print(f"ไม่พบ {save}")
        return 1
    print(f"เปิดโลกจาก {a.source} (เซฟใหญ่ อาจใช้เวลาสักครู่)...")
    sim = PS.load_sim(save)
    if getattr(sim, "mind", None) is not None:
        sim.mind.attach(sim, backend=B.MockThinker(), journal_path="")
    os.makedirs(a.out, exist_ok=True)

    # ฉากที่ตัวละครไม่มีในโลกที่เปิดอยู่ (เช่นชี้ไปคนละเซฟ) เล่าไม่ได้ — ตัดออกก่อน ไม่ให้ล้มกลางทาง
    scenes = [e for e in scenes if isinstance(e.get("cid"), int) and 0 <= e["cid"] < len(sim.cast)]
    if not scenes:
        print("ฉากในบันทึกไม่ตรงกับโลกในเซฟนี้ — ชี้ --source ไปโฟลเดอร์ที่มีทั้ง journal.jsonl และ world.save")
        return 1
    report = ["# เทียบโมเดลแต่งเรื่อง", "", f"ฉาก {len(scenes)} ฉากจาก `{a.source}`", ""]
    summary = {m: {"secs": 0.0, "chars": 0, "quotes": 0, "first": 0, "labels": 0, "modern": 0, "oath_ok": 0,
                   "oath_total": 0} for m in models}
    for i, entry in enumerate(scenes, 1):
        system, user = ST.build(sim, entry)
        head = (f"## ฉาก {i} — ปีที่ {entry.get('year')} {entry.get('name')} "
                f"{entry.get('action')} {entry.get('target') or ('โดย ' + str(entry.get('by')))} "
                f"→ {entry.get('outcome')}")
        report += [head, "", f"ข้อเท็จจริง: {entry.get('text', '')}", ""]
        print(f"\n{head}")
        for m in models:
            t0 = time.time()
            if a.dry_run:
                text = f"[{m}] เรื่องเล่าจำลองของ{entry.get('name')} ข้าจะช่วยคุณ\nผลที่เกิดขึ้นจริง: จบ"
            else:
                thinker = B.OllamaThinker(model=m, story_model=m, base_url=a.base_url)
                try:
                    text = thinker.write(system, user)
                except Exception as exc:                        # noqa: BLE001
                    text = f"(ผิดพลาด: {exc})"
            secs = time.time() - t0
            c = checks(text, entry, sim)
            s = summary[m]
            s["secs"] += secs
            s["chars"] += c["chars"]
            s["quotes"] += c["quotes"]
            s["first"] += 1 if c["เล่าเป็นบุรุษที่1"] else 0
            s["labels"] += len(c["ป้ายกำกับหลุด"])
            s["modern"] += len(c["คำสมัยใหม่"])
            s["wrapped"] = s.get("wrapped", 0) + c["ย่อหน้าครอบวงเล็บ"]
            s["facts"] = s.get("facts", 0) + int(c["เอ่ยชื่อคู่กรณี/สถานที่"].split("/")[0])
            if c["คำสาบานถูกสาย"] is not None:
                s["oath_total"] += 1
                s["oath_ok"] += 1 if c["คำสาบานถูกสาย"] else 0
            print(f"   {m}: {secs:.1f} วิ · {c['chars']} ตัวอักษร · บทพูด {c['quotes']} · "
                  f"คำสมัยใหม่ {c['คำสมัยใหม่']} · ป้ายหลุด {len(c['ป้ายกำกับหลุด'])}")
            report += [f"### {m} ({secs:.1f} วินาที)", "",
                       f"ตรวจ: {json.dumps(c, ensure_ascii=False)}", "",
                       ST.clean_story(text).strip(), ""]
    report += ["## สรุป", "", "| โมเดล | เวลารวม | เฉลี่ยต่อฉาก | ตัวอักษรเฉลี่ย | บทพูดรวม | "
               "เล่าผิดมุมมอง | ป้ายหลุด | คำสมัยใหม่ | ย่อหน้าครอบวงเล็บ | เอ่ยชื่อถูก | คำสาบานถูกสาย |",
               "|---|---|---|---|---|---|---|---|---|---|---|"]
    n = len(scenes)
    for m, s in summary.items():
        oath = f"{s['oath_ok']}/{s['oath_total']}" if s["oath_total"] else "-"
        report.append(f"| {m} | {s['secs']:.0f} วิ | {s['secs']/n:.1f} วิ | {s['chars']//n} | "
                      f"{s['quotes']} | {s['first']}/{n} | {s['labels']} | {s['modern']} | "
                      f"{s.get('wrapped', 0)} | {s.get('facts', 0)}/{n * 2} | {oath} |")
    path = os.path.join(a.out, "compare.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(report) + "\n")
    print("\n" + "\n".join(report[-len(summary) - 3:]))
    print(f"\nอ่านฉากเต็มได้ที่ {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
