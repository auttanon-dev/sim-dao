# -*- coding: utf-8 -*-
"""เดินโลกที่มีตัวละครมีจิตใจ — ใช้ร่วมกันทั้งหน้าเว็บ (mind_app.py) และเทอร์มินัล (run_minds.py)

โลกของชั้นนี้แยกไฟล์เซฟของตัวเอง (out/minds/world.save) — ค่าเริ่มต้นสร้างโลกใหม่จาก seed
(หรือคัดลอกโลกเดิมมาด้วย source_save) เหตุผลที่ไม่ใช้ไฟล์ร่วมกับระบบอื่น: เมื่อจิตใจเริ่มตัดสินใจ โลกจะเดินคนละทางกับโลกของโรงนิยายและท่องยุทธจักรทันที ถ้าใช้ไฟล์
เดียวกัน สองระบบจะเขียนทับกันและนิยายที่เขียนไปแล้วจะอ้างเหตุการณ์ที่ไม่เคยเกิด
"""
import contextlib
import io
import json
import os
import shutil
import threading
import time
from dataclasses import dataclass

from . import backend as B
from . import config as MC
from . import storyteller as ST
from .manager import MindManager, trim_journal
from .. import persist as PS

SAVE_EVERY_SECONDS = 20.0


@dataclass
class RunConfig:
    out_dir: str = MC.OUT_DIR
    source_save: str = ""         # ว่าง = สร้างโลกใหม่จาก seed (แนะนำ) / ใส่พาธ = คัดลอกโลกเดิมมาเดินต่อ
    seed: int = 1
    tiers: int = 3
    capacity: int = MC.MIND_CAPACITY
    story: bool = MC.STORY_ENABLED
    max_steps: int = 0            # 0 = ไม่จำกัด
    max_years: float = 0.0        # 0 = ไม่จำกัด
    max_minutes: float = 0.0      # 0 = ไม่จำกัด (เวลาจริง ใช้เทียบกับระบบอื่นด้วยงบเวลาเท่ากัน)
    quiet_engine: bool = True     # ปิดข้อความ print ของเอนจินเดิม (มีเยอะมาก)

    @property
    def save_path(self):
        return os.path.join(self.out_dir, "world.save")

    @property
    def journal_path(self):
        return os.path.join(self.out_dir, MC.JOURNAL_NAME)


def open_world(cfg: RunConfig, backend=None, journal=True):
    """โหลดโลกของชั้นจิตใจ (สร้างจากโลกหลักถ้ายังไม่มี) แล้วแนบ MindManager — คืน sim

    journal=False ใช้กับการทดสอบโมเดล (--probe) ที่ไม่ได้เซฟโลก — ไม่งั้นบรรทัด "ตื่นรู้" ถูกเขียนซ้ำ
    ทุกครั้งที่ทดสอบ (รันจริงเจอบันทึกซ้ำ 36 บรรทัดจากการ probe 4 ครั้ง)"""
    os.makedirs(cfg.out_dir, exist_ok=True)
    if not os.path.exists(cfg.save_path):
        if cfg.source_save:
            if not os.path.exists(cfg.source_save):
                raise FileNotFoundError(f"ไม่พบโลกต้นทาง {cfg.source_save}")
            shutil.copy2(cfg.source_save, cfg.save_path)
        else:
            from ..sim import Sim
            with contextlib.redirect_stdout(io.StringIO()):
                fresh = Sim(seed=cfg.seed, tiers=cfg.tiers)
            PS.save_sim(fresh, cfg.save_path)
    sim = PS.load_sim(cfg.save_path)
    trim_journal(cfg.journal_path, sim.seq)
    manager = getattr(sim, "mind", None)
    if manager is None:
        manager = MindManager(capacity=cfg.capacity)
    manager.capacity = cfg.capacity
    manager.attach(sim, backend=backend, journal_path=cfg.journal_path if journal else "")
    return sim


class MindRunner:
    def __init__(self):
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = None
        self.cfg = RunConfig()
        self.sim = None
        self.state = "idle"
        self.message = "ยังไม่ได้เริ่ม"
        self.error = ""
        self.backend = None
        self.steps = 0
        self.started_at = None
        self.last_save = 0.0
        self.on_entry = None        # callback(entry) สำหรับเทอร์มินัล

    # ------------------------------------------------------------ ควบคุม
    def configure(self, cfg: RunConfig, backend=None):
        self.cfg = cfg
        self.backend = backend or B.from_env()
        self.sim = open_world(cfg, self.backend)
        self.message = "พร้อมเดินโลก"
        return self

    def start(self):
        with self._lock:
            if self._thread and self._thread.is_alive():
                raise RuntimeError("โลกกำลังเดินอยู่แล้ว")
            if self.sim is None:
                raise RuntimeError("ยังไม่ได้ตั้งค่าโลก")
            self._stop.clear()
            self.error = ""
            self.state = "running"
            self.started_at = time.time()
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()
        return self.status()

    def stop(self):
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self.state = "stopping"
            self.message = "กำลังพัก รอให้ตัวละครที่กำลังคิดอยู่คิดเสร็จ"
        return self.status()

    def join(self, timeout=None):
        if self._thread:
            self._thread.join(timeout)

    def run_blocking(self):
        """ใช้จากเทอร์มินัล — เดินจนครบเงื่อนไขหรือกด Ctrl+C"""
        self._stop.clear()
        self.state = "running"
        self.started_at = time.time()
        try:
            self._run()
        except KeyboardInterrupt:
            self.message = "หยุดด้วย Ctrl+C"
        finally:
            self.save()

    # ------------------------------------------------------------ ลูปหลัก
    def _run(self):
        sim, mind = self.sim, self.sim.mind
        start_day = sim.day
        seen = len(mind.recent)
        try:
            while not self._stop.is_set():
                if self.cfg.max_steps and self.steps >= self.cfg.max_steps:
                    self.message = f"ครบ {self.steps:,} เหตุการณ์ตามที่ตั้งไว้"
                    break
                if self.cfg.max_minutes and time.time() - self.started_at >= self.cfg.max_minutes * 60:
                    self.message = f"ครบ {self.cfg.max_minutes:g} นาทีตามที่ตั้งไว้"
                    break
                if self.cfg.max_years and (sim.day - start_day) / 365 >= self.cfg.max_years:
                    self.message = f"ครบ {self.cfg.max_years:g} ปีตามที่ตั้งไว้"
                    break
                if self.cfg.quiet_engine:
                    with contextlib.redirect_stdout(io.StringIO()):
                        ev = sim.step()
                else:
                    ev = sim.step()
                if ev is None:
                    self.message = "ไม่มีใครเหลือให้เดินเรื่องต่อแล้ว"
                    break
                self.steps += 1
                if self.steps % 200 == 0:
                    added = mind.ensure_cast(sim)
                    if added:
                        self.message = "มีผู้ตื่นรู้คนใหม่: " + ", ".join(m.name for m in added)
                if mind.successor_hints:
                    mind.ensure_cast(sim)
                if self.on_entry is not None and len(mind.recent) != seen:
                    for entry in mind.recent[seen - len(mind.recent):] if len(mind.recent) > seen else mind.recent[-1:]:
                        self.on_entry(entry)
                    seen = len(mind.recent)
                if self.cfg.story and mind.story_queue:
                    self._write_story(mind.story_queue.pop(0))
                if time.time() - self.last_save > SAVE_EVERY_SECONDS:
                    self.save()
                if not mind.activity:
                    self.message = f"ปีที่ {sim.day // 365} · ผู้มีจิตใจ {len(mind.active())} คน"
            self.state = "idle"
        except Exception as exc:          # เก็บข้อความให้หน้าเว็บแสดง ไม่ให้ thread ตายเงียบ
            self.error = f"{type(exc).__name__}: {exc}"
            self.state = "error"
            raise
        finally:
            self.save()
            if self.state != "error":
                self.state = "idle"

    def _write_story(self, entry):
        sim = self.sim
        try:
            system, user = ST.build(sim, entry)
            sim.mind.activity = f"กำลังเล่าเรื่องของ {entry['name']}…"
            text = self.backend.write(system, user)
        except Exception as exc:
            sim.mind.activity = ""
            sim.mind.stats["errors"] += 1
            self.message = f"แต่งเรื่องไม่สำเร็จ: {exc}"
            return
        sim.mind.activity = ""
        raw = text or ""
        text = ST.clean_story(raw)
        fact_errors = ST.validate_facts(entry, text)
        if fact_errors:
            # โมเดลเขียนลื่นแต่กลับผู้ชนะมีอันตรายกว่าการไม่มีร้อยแก้ว ลองแก้หนึ่งครั้งโดย
            # ชี้ข้อผิดพลาดตรงๆ ถ้ายังผิดให้ทิ้งและคงบันทึกข้อเท็จจริงของเอนจินไว้แทน
            try:
                correction = (user + "\n\n[ฉบับก่อนต้องแก้] " + " / ".join(fact_errors)
                              + f"\nผลที่ต้องตรงทุกประการ: {entry.get('text', '')}"
                              + "\nเขียนฉากใหม่ทั้งหมดและจบให้ถึงผลนี้ ห้ามอธิบายการแก้ไข\n"
                              + raw[:5000])
                raw = self.backend.write(system, correction) or ""
                text = ST.clean_story(raw)
                fact_errors = ST.validate_facts(entry, text)
            except Exception as exc:
                fact_errors = [f"เขียนแก้ไม่สำเร็จ: {exc}"]
            if fact_errors:
                sim.mind.activity = ""
                sim.mind.stats["errors"] += 1
                self.message = f"เรื่องเล่าของ {entry['name']} ขัดผลจริง จึงข้ามไป"
                return
        echoed = any(m in raw for m in MC.STORY_INSTRUCTION_MARKS)
        if echoed and len(text.strip()) < MC.STORY_MIN_CHARS:
            # โมเดลลอกคำสั่งกลับมาแทนที่จะเล่าฉาก แล้วเหลือเนื้อไม่พอ — ไม่บันทึกดีกว่าบันทึกขยะ
            sim.mind.stats["errors"] += 1
            self.message = f"เรื่องเล่าของ {entry['name']} เป็นการลอกคำสั่ง ข้ามไป"
            return
        if text and text.strip():
            sim.mind.stats["stories"] += 1
            sim.mind._journal({"type": "story", "id": f"s-{entry['id']}", "entry": entry["id"],
                               "seq": entry["seq"], "day": entry["day"], "year": entry["year"],
                               "cid": entry["cid"], "name": entry["name"], "story": text.strip()})

    def save(self):
        if self.sim is None:
            return
        PS.save_sim(self.sim, self.cfg.save_path)
        self.last_save = time.time()

    # ------------------------------------------------------------ สถานะ
    def status(self):
        sim = self.sim
        if sim is None:
            return {"state": self.state, "message": self.message, "error": self.error}
        mind = sim.mind
        return {
            "state": self.state, "message": self.message, "error": self.error,
            "activity": mind.activity, "year": sim.day // 365, "day": sim.day, "steps": self.steps,
            "alive_world": len(sim.alive_cids), "stats": dict(mind.stats),
            "story_queue": len(mind.story_queue), "backend": self.backend.public() if self.backend else {},
            "limits": {"minutes": self.cfg.max_minutes, "mind_count": self.cfg.capacity},
            "minds": mind.summary(sim),
        }


def read_journal(path, cid=None, limit=200, before_seq=None, types=None):
    """อ่านบันทึกชีวิตย้อนหลัง (ล่าสุดก่อน) พร้อมผูกเรื่องเล่าเข้ากับการตัดสินใจของมัน"""
    if not os.path.exists(path):
        return []
    entries, stories = [], {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue
            if e.get("type") == "story":
                stories[e.get("entry")] = e.get("story", "")
                continue
            if cid is not None and e.get("cid") != cid and e.get("by_cid") != cid \
                    and e.get("target_cid") != cid:
                continue
            if types and e.get("type") not in types:
                continue
            if before_seq is not None and e.get("seq", 0) >= before_seq:
                continue
            entries.append(e)
    # backfill วัยเด็กถูกเขียนตอนตัวละครถูกเลือกเป็นผู้มีจิตใจ จึงอยู่ท้ายไฟล์ทางกายภาพ
    # แต่วันของมันเก่ากว่า ต้องเรียงด้วยเวลาโลก ไม่ใช่ตำแหน่งบรรทัดในไฟล์
    entries.sort(key=lambda e: (e.get("day", 0), e.get("seq", -1), e.get("at", 0)), reverse=True)
    seen, out = set(), []
    for e in entries:
        if e.get("id") in seen:
            continue
        seen.add(e.get("id"))
        if e.get("id") in stories:
            e["story"] = stories[e["id"]]
        out.append(e)
        if len(out) >= limit:
            break
    return out


RUNNER = MindRunner()
