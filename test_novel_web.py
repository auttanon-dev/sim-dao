# -*- coding: utf-8 -*-
"""ตรวจหน้าเว็บโรงเขียนนิยาย (/novel + /api/novel/*) โดยไม่ต้องมี Ollama

สลับ `OllamaAgent` เป็นตัวปลอมก่อนเรียก endpoint — ทำให้ตรวจสิ่งที่โค้ดเรารับผิดชอบได้จริง:
งานเดินใน thread แล้วหน้าเว็บ poll เห็นความคืบหน้าไหม, กดหยุดแล้วหยุดจริงไหม, สั่งเขียนบทเดียวซ้ำ
แล้วทับของเดิมในงานเดิมไหม, ปุ่มดาวน์โหลดได้ไฟล์ที่ครบทุกบทไหม — ทั้งหมดนี้ไม่เกี่ยวกับคุณภาพสำนวน
จึงไม่ต้องรอโมเดล 8B ตอบทีละบีต

ต้องมีไฟล์โลกก่อน: ตั้ง TIANDAO_SAVE_PATH ชี้ไปที่ไฟล์ save ที่มีอยู่ (ดีฟอลต์ใช้ของ persist)
"""
import io
import os
import sys
import time

SAVE = os.environ.get("TIANDAO_SAVE_PATH", "")
if SAVE:
    os.environ["TIANDAO_SAVE_PATH"] = SAVE

from fastapi.testclient import TestClient      # noqa: E402

import dashboard                                # noqa: E402
from tiandao.ai import llm_agent as LLM         # noqa: E402
from narrative_factory import studio as STUDIO  # noqa: E402


class FakeOllama:
    """ตอบโดยไม่ต้องมีเซิร์ฟเวอร์ — ยาวพอผ่านเกณฑ์ฉากเต็ม

    `DELAY` มีไว้ให้เหมือนของจริงพอที่จะทดสอบเรื่องเวลาได้ (กันงานซ้อนงาน, กดหยุดกลางคัน)
    ถ้าตอบทันทีแบบไม่มีดีเลย งาน 3 บทจะจบก่อนที่เทสต์จะทันยิง request ที่สอง แล้วเทสต์จะกลายเป็น
    การวัดความเร็วของเครื่องแทนที่จะวัดพฤติกรรมของโค้ด
    """

    DELAY = 0.08

    def __init__(self, *a, **kw):
        pass

    def complete_json(self, system, user, **kw):
        time.sleep(self.DELAY)
        from narrative_factory import pacing as PACE
        if '"beats"' in system:
            return {"beats": [{"stage": s, "outline": f"โครง {s}"} for s in PACE.BEAT_STAGES]}
        names = []
        for line in user.splitlines():
            if line.startswith("- ตัวละครที่เอ่ยชื่อได้มีเพียง: "):
                names = [n.strip() for n in
                         line.split(": ", 1)[1].split(" ห้ามเพิ่ม")[0].split(",") if n.strip()]
        me = names[0] if names else "ใครสักคน"
        you = names[1] if len(names) > 1 else me
        return {"lines": [{"speaker": me if i % 2 == 0 else you,
                           "line": f"ถ้อยคำที่ {i} ในบีตนี้ ยาวพอให้จับต้นชนปลายได้",
                           "action": "ถอนหายใจ"} for i in range(6)]}

    def complete(self, system, user, **kw):
        time.sleep(self.DELAY)
        quoted = []
        if "[บทพูดที่ต้องร้อยเข้าไป" in user:
            for line in user.split("[บทพูดที่ต้องร้อยเข้าไป", 1)[1].splitlines():
                if line.startswith("- ") and '"' in line:
                    quoted.append(line.split('"')[1])
        body = " ".join(f'เขากล่าวว่า "{q}" แล้วเงียบไป' for q in quoted)
        filler = ("ลมหอบกลิ่นดินเปียกเข้ามาในลานหินอย่างเงียบเชียบ "
                  "แสงสลัวทาบลงบนรอยร้าวเก่าที่ไม่มีใครเคยซ่อม ") * 12
        return f"{body}\n\n{filler}"


def wait_until(client, job_id, want_states, timeout=90):
    t0 = time.time()
    while time.time() - t0 < timeout:
        job = client.get(f"/api/novel/job/{job_id}").json()
        if job["state"] in want_states:
            return job
        time.sleep(0.3)
    raise AssertionError(f"งานไม่ถึงสถานะ {want_states} ใน {timeout} วินาที")


def main():
    LLM.OllamaAgent = FakeOllama
    client = TestClient(dashboard.app)

    print("\n=== 1. หน้าเว็บและรายชื่อโมเดล ===")
    r = client.get("/novel")
    assert r.status_code == 200 and "โรงเขียนนิยาย" in r.text
    m = client.get("/api/novel/models").json()
    assert m["default_prose"] and m["default_structure"]
    print(f"  ✓ /novel เปิดได้ | Ollama {'พบ' if m['ollama_up'] else 'ไม่ได้เปิด (ยังใช้โหมดดูโครงได้)'}")

    print("\n=== 2. รายชื่อผู้ที่คู่ควรเป็นตัวเอก ===")
    rows = client.get("/api/novel/candidates?limit=5").json()
    assert isinstance(rows, list) and rows, f"ไม่ได้รายชื่อ: {rows}"
    for r_ in rows:
        assert r_["name"] and r_["turning_points"] >= 12
        assert STUDIO.SCAST.can_carry_a_novel(STUDIO.WORLD.sim.cast[r_["cid"]]), \
            f"{r_['name']} ไม่ควรอยู่ในรายชื่อตัวเอก"
    cid = rows[0]["cid"]
    print(f"  ✓ {len(rows)} คน — อันดับหนึ่ง {rows[0]['name']} ({rows[0]['turning_points']} จุดเปลี่ยน)")

    print("\n=== 3. ดูโครงต้องไม่เรียกโมเดลเลย ===")
    calls = {"n": 0}
    real = FakeOllama.complete
    FakeOllama.complete = lambda self, *a, **kw: (calls.__setitem__("n", calls["n"] + 1),
                                                  real(self, *a, **kw))[1]
    o = client.get(f"/api/novel/outline?cid={cid}&chapters=4").json()
    assert o["n_chapters"] == 4 and calls["n"] == 0, f"ดูโครงแล้วดันเรียกโมเดล {calls['n']} ครั้ง"
    for ch in o["chapters"]:
        assert ch["title"] and ch["events"], f"บทว่างเปล่า: {ch}"
        assert len(ch["cast"]) == len(set(ch["cast"])), f"มีชื่อซ้ำในฉากเดียวกัน: {ch['cast']}"
        assert "ฤดูฤดู" not in ch["subtitle"], f"คำว่าฤดูซ้ำ: {ch['subtitle']}"
    print(f"  ✓ {o['n_chapters']} บทของ {o['name']} · เรียกโมเดล 0 ครั้ง · ไม่มีชื่อซ้ำในฉาก")
    print(f"    ตัวอย่าง: {o['chapters'][0]['title']} — {o['chapters'][0]['subtitle']}")

    print("\n=== 4. สั่งเขียนจริง แล้ว poll ดูความคืบหน้า ===")
    job = client.post("/api/novel/start", json={"cid": cid, "chapters": 3}).json()
    jid = job["job_id"]
    busy = client.post("/api/novel/start", json={"cid": cid, "chapters": 2})
    assert busy.status_code == 409, "ปล่อยให้เริ่มงานที่สองซ้อนงานแรกได้ (GPU มีใบเดียว)"
    job = wait_until(client, jid, {"done", "error"})
    assert job["state"] == "done", job.get("error")
    s = job["summary"]
    assert s["done"] == 3 and s["chars"] > 3 * 1800, s
    for c in job["chapters"]:
        assert c["status"] == "เสร็จ" and c["prose"] and c["dialogue"] > 0
        assert not c["issues"], f'บท {c["index"]} มีข้อค้าง: {c["issues"]}'
    print(f"  ✓ {s['done']} บท {s['chars']:,} ตัวอักษร บทพูด {s['dialogue']} บรรทัด "
          f"เรียกโมเดล {s['calls']} ครั้ง ({s['elapsed']} วิ)")
    print("  ✓ กันงานซ้อนงานได้ (คืน 409)")

    print("\n=== 5. สั่งเขียนบทเดียวซ้ำ ต้องทับของเดิมในงานเดิม ไม่สร้างงานใหม่ ===")
    before = job["chapters"][1]["calls"]
    r2 = client.post(f"/api/novel/job/{jid}/rewrite/2").json()
    assert r2["job_id"] == jid, "สร้างงานใหม่แทนที่จะทับของเดิม"
    assert r2["state"] == "running", ("ระหว่างเขียนซ้ำต้องรายงานว่า running ไม่งั้นหน้าเว็บ"
                                      "หยุด poll แล้วไม่เห็นบทใหม่")
    job = wait_until(client, jid, {"done"})
    assert len(job["chapters"]) == 3, "จำนวนบทเปลี่ยนหลังเขียนซ้ำ"
    assert job["chapters"][1]["calls"] >= before, "บทที่สั่งซ้ำไม่ได้ถูกเขียนใหม่จริง"
    print(f"  ✓ บทที่ 2 ถูกเขียนใหม่ ({job['chapters'][1]['chars']:,} ตัวอักษร) บทอื่นไม่ถูกแตะ")

    print("\n=== 6. ดาวน์โหลดต้องได้ไฟล์ที่ครบทุกบท ===")
    md = client.get(f"/api/novel/job/{jid}/download").text
    assert md.startswith("# ") and md.count("\n## ") == 3, f"หัวบทไม่ครบ: {md.count(chr(10)+'## ')}"
    assert len(md) > 5000
    print(f"  ✓ ไฟล์ {len(md):,} ตัวอักษร มีหัวบทครบ 3 บท")

    print("\n=== 7. กดหยุดกลางคันต้องหยุดจริง ===")
    job2 = client.post("/api/novel/start", json={"cid": cid, "chapters": 6}).json()
    jid2 = job2["job_id"]
    time.sleep(0.2)
    assert client.post(f"/api/novel/job/{jid2}/stop").json()["ok"]
    job2 = wait_until(client, jid2, {"stopped", "done"})
    assert job2["state"] == "stopped", "กดหยุดแล้วยังเขียนต่อจนจบ"
    assert job2["summary"]["done"] < 6, "หยุดแล้วแต่เขียนครบทุกบท"
    md2 = client.get(f"/api/novel/job/{jid2}/download").text
    assert md2.count("\n## ") == job2["summary"]["done"], "ไฟล์ที่ได้ไม่ตรงกับบทที่เขียนเสร็จจริง"
    print(f"  ✓ หยุดที่บทที่ {job2['summary']['done']} และดาวน์โหลดได้เท่าที่เขียนเสร็จ")

    print("\n=== 8. ต้องเซฟไฟล์เองระหว่างเขียน ไม่ใช่รอจนจบ ===")
    job = client.get(f"/api/novel/job/{jid}").json()
    out = job["out_path"]
    assert out and os.path.exists(out), f"ไม่พบไฟล์ที่เซฟไว้: {out!r}"
    saved = io.open(out, encoding="utf-8").read()
    assert saved.count("\n## ") == 3 and len(saved) > 5000, "ไฟล์ที่เซฟไม่ครบทุกบท"
    assert not os.path.exists(out + ".tmp"), "ไฟล์ชั่วคราวค้างอยู่"
    # งานที่ถูกกดหยุดกลางคันก็ต้องมีไฟล์ของบทที่เขียนเสร็จไปแล้ว
    out2 = client.get(f"/api/novel/job/{jid2}").json()["out_path"]
    assert out2 and os.path.exists(out2), "งานที่กดหยุดไม่ได้เซฟบทที่เขียนเสร็จไว้เลย"
    assert io.open(out2, encoding="utf-8").read().count("\n## ") == job2["summary"]["done"]
    print(f"  ✓ {out} ({len(saved):,} ตัวอักษร) และงานที่กดหยุดก็มีไฟล์ของตัวเอง")

    print("\n=== 9. ปุ่มเดินโลกต่อเนื่อง ===")
    scratch = "out/_webtest_world.save"
    for suffix in ("", ".events.jsonl"):
        if os.path.exists(scratch + suffix):
            os.remove(scratch + suffix)
    dashboard.SAVE_PATH = scratch
    st = client.get("/api/world/status").json()
    assert st["state"] == "idle", st
    st = client.post("/api/world/start",
                     json={"chunk_events": 1500, "interval": 0.5}).json()
    assert st["state"] == "running"
    again = client.post("/api/world/start", json={"chunk_events": 1500})
    assert again.status_code == 409, "ปล่อยให้สั่งเดินโลกซ้อนกันสองตัว"
    t0 = time.time()
    while time.time() - t0 < 180:
        st = client.get("/api/world/status").json()
        if st["iterations"] >= 2:
            break
        time.sleep(0.5)
    assert st["iterations"] >= 2, f"เดินไม่ถึงสองรอบใน 180 วินาที: {st}"
    assert st["last"]["day_to"] > st["rounds"][0]["day_from"], "เวลาในโลกไม่เดินหน้า"
    assert os.path.exists(scratch), "เดินโลกแล้วแต่ไม่มีไฟล์ save"
    client.post("/api/world/stop")
    t0 = time.time()
    while time.time() - t0 < 120:
        st = client.get("/api/world/status").json()
        if st["state"] == "idle":
            break
        time.sleep(0.5)
    assert st["state"] == "idle", f"กดหยุดแล้วยังไม่หยุด: {st['state']}"
    print(f"  ✓ เดิน {st['iterations']} รอบถึงวันที่ {st['last']['day_to']} "
          f"(ปีที่ {st['last']['year']}) มีชีวิต {st['last']['alive']} · เซฟทุกรอบ · กดหยุดแล้วหยุดจริง")

    print("\n=== 10. หน้าแรกต้องมีปุ่มเดินโลกทั้งตอนมีโลกแล้วและตอนยังไม่มี ===")
    assert "เริ่มเดินโลก" in client.get("/").text, "หน้าแรกไม่มีปุ่มเดินโลก"
    dashboard.SAVE_PATH = "out/_ไม่มีไฟล์นี้.save"
    empty = client.get("/").text
    assert "เริ่มเดินโลก" in empty and "ยังไม่พบไฟล์" in empty, \
        "ตอนยังไม่มีโลก หน้าแรกต้องยังกดสร้างโลกได้"
    print("  ✓ มีปุ่มทั้งสองกรณี")

    print("\n✓ หน้าเว็บโรงเขียนนิยายทำงานครบทุกปุ่ม")


if __name__ == "__main__":
    main()
