# -*- coding: utf-8 -*-
"""เขียนนิยายยาวจาก journal ของผู้มีจิตใจที่ผู้ใช้เลือก — ทำงานเบื้องหลังและเซฟทีละบท."""
import os
import re
import threading
from pathlib import Path

from .runner import read_journal
from . import storyteller as ST


SYSTEM = (
    "คุณเป็นนักเขียนนิยายกำลังภายในภาษาไทย เขียนเป็นบุคคลที่สามจากบันทึกโลกจำลองจริง "
    "ห้ามเปลี่ยนลำดับเวลา ผลแพ้ชนะ ความตาย ความสัมพันธ์ ของที่ได้รับ หรือสร้างตัวละครชื่อใหม่ "
    "ทุกเหตุการณ์ต้องมาจากบันทึกที่ให้เท่านั้น ขยายได้เฉพาะบรรยากาศ อารมณ์ ท่าทาง และบทสนทนา "
    "ห้ามกล่าวว่าคนใดเคยตายก่อนวันที่บันทึกระบุ และห้ามให้คนตายกลับมาพูดหรือกระทำ "
    "ส่งเฉพาะเนื้อหาบท ไม่มีคำอธิบายการทำงาน ไม่มี markdown code fence"
)


def _safe_name(text):
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", text).strip(" ._") or "character"


def _event_line(e):
    who = f" กับ {e.get('target')}" if e.get("target") else ""
    by = f" โดย {e.get('by')}" if e.get("by") else ""
    reason = f" เหตุผล: {e.get('why')}" if e.get("why") else ""
    thought = f" ความคิด: {e.get('thought')}" if e.get("thought") else ""
    return (f"- ปี {e.get('year')} วันที่ {e.get('day')} | {e.get('type')} | "
            f"{e.get('action', '')}{who}{by} → {e.get('outcome', '')}: {e.get('text', '')}"
            f"{reason}{thought}")[:1800]


def _chunks(entries, wanted):
    wanted = max(1, min(int(wanted), 30))
    n = max(1, min(wanted, len(entries)))
    return [entries[i * len(entries) // n:(i + 1) * len(entries) // n] for i in range(n)]


class MindNovelJob:
    def __init__(self):
        self._lock = threading.Lock()
        self._thread = None
        self._stop = threading.Event()
        self.state = "idle"
        self.message = "ยังไม่ได้เริ่มแต่งนิยาย"
        self.error = ""
        self.cid = None
        self.name = ""
        self.chapter = 0
        self.chapters = 0
        self.out_path = ""

    def running(self):
        return bool(self._thread and self._thread.is_alive())

    def status(self):
        return {"state": self.state, "message": self.message, "error": self.error,
                "cid": self.cid, "name": self.name, "chapter": self.chapter,
                "chapters": self.chapters, "out_path": self.out_path,
                "download": "/api/novel/download" if self.out_path and os.path.exists(self.out_path) else ""}

    def start(self, sim, journal_path, cid, backend, out_dir, chapters=6):
        with self._lock:
            if self.running():
                raise RuntimeError("กำลังแต่งนิยายอีกเรื่องอยู่")
            if cid not in sim.mind.minds:
                raise ValueError("ไม่พบผู้มีจิตใจที่เลือก")
            entries = sorted(read_journal(journal_path, cid=cid, limit=100000),
                             key=lambda e: (e.get("day", 0), e.get("seq", -1), e.get("at", 0)))
            entries = [e for e in entries if e.get("type") in
                       ("birth", "childhood", "decision", "received", "event", "join", "death")]
            if not entries:
                raise ValueError("ตัวละครนี้ยังไม่มีบันทึกพอสำหรับแต่งนิยาย")
            profile = sim.mind.profile(sim, cid)
            self._stop.clear()
            self.state, self.error = "running", ""
            self.cid, self.name = cid, profile["name"]
            parts = _chunks(entries, chapters)
            self.chapter, self.chapters = 0, len(parts)
            folder = Path(out_dir) / "novels"
            folder.mkdir(parents=True, exist_ok=True)
            self.out_path = str(folder / f"novel-{cid}-{_safe_name(self.name)}.md")
            self.message = f"กำลังเตรียมนิยายของ{self.name}"
            self._thread = threading.Thread(
                target=self._write, args=(profile, parts, backend), daemon=True)
            self._thread.start()
            return self.status()

    def stop(self):
        self._stop.set()
        if self.running():
            self.state = "stopping"
            self.message = "จะหยุดหลังเขียนบทปัจจุบันเสร็จ"
        return self.status()

    def _save(self, chapters):
        text = f"# ชีวิตของ{self.name}\n\n" + "\n\n---\n\n".join(chapters) + "\n"
        tmp = self.out_path + ".tmp"
        Path(tmp).write_text(text, encoding="utf-8")
        os.replace(tmp, self.out_path)

    def _write(self, profile, chunks, backend):
        written = []
        try:
            for i, entries in enumerate(chunks, 1):
                if self._stop.is_set():
                    break
                self.chapter = i
                self.message = f"กำลังเขียนบทที่ {i}/{len(chunks)} · {self.name}"
                facts = "\n".join(_event_line(e) for e in entries)
                # ใช้ข้อเท็จจริงท้ายช่วงก่อนหน้า ไม่ส่งร้อยแก้วที่โมเดลแต่งกลับเข้าโมเดล
                # เพราะรายละเอียดที่แต่งเกินเพียงครั้งเดียวจะกลายเป็น "ความจริง" ในทุกบทถัดไป
                previous = "\n".join(_event_line(e) for e in (chunks[i - 2][-4:] if i > 1 else [])) \
                    or "(บทแรก)"
                chapter_goal = next((e.get("long_goal") for e in reversed(entries)
                                     if e.get("long_goal")), "-")
                user = (
                    f"[ตัวเอก] {profile['identity']}\n"
                    f"[เป้าหมายชีวิต ณ ช่วงเวลานี้] {chapter_goal}\n"
                    f"[บท] {i}/{len(chunks)}\n[ท้ายบทก่อนหน้า]\n{previous}\n"
                    f"[บันทึกจริงของบทนี้ — เรียงตามเวลา]\n{facts}\n\n"
                    "เขียนบทนิยายยาว 5-10 ย่อหน้า มีบทสนทนาเมื่อข้อมูลมีคนมากกว่าหนึ่งคน "
                    "เริ่มจากเหตุการณ์แรกและจบตรงเหตุการณ์สุดท้ายของรายการ ห้ามข้ามไปอนาคต"
                )
                prose = ST.clean_story((backend.write(SYSTEM, user) or "").strip())
                if not prose:
                    raise RuntimeError(f"โมเดลไม่คืนเนื้อหาบทที่ {i}")
                written.append(f"## บทที่ {i}\n\n{prose}")
                self._save(written)
            if self._stop.is_set():
                self.state = "idle"
                self.message = f"พักแล้ว · บันทึกไว้ {len(written)}/{len(chunks)} บท"
            else:
                self.state = "complete"
                self.message = f"แต่งนิยายของ{self.name}เสร็จแล้ว {len(written)} บท"
        except Exception as exc:
            self.state = "error"
            self.error = f"{type(exc).__name__}: {exc}"
            self.message = "แต่งนิยายไม่สำเร็จ"


NOVEL = MindNovelJob()
