# -*- coding: utf-8 -*-
"""หนึ่งรอบของโลกที่เดินเอง — ตรรกะกลางที่ทั้ง `daemon.py` (เทอร์มินัล) และหน้าเว็บใช้ร่วมกัน

เหตุผลที่แยกไฟล์นี้ออกมา ไม่ใช่เขียนลูปใหม่ในหน้าเว็บ
---------------------------------------------------------------------------------------------
งานหนึ่งรอบไม่ได้มีแค่ `sim.run(n)` แต่มีลำดับที่ต้องถูกต้องพอดี: เดินซิม -> flush+trim event log
(Phase G กัน world.save โตไม่มีเพดาน) -> เซฟ -> drain คิว LLM ถ้าเปิด -> วัดผล -> ขยับค่าคงที่
(online tuning) ถ้าหน้าเว็บเขียนลูปของตัวเองขึ้นมาอีกชุด สองชุดนี้จะค่อยๆ ต่างกันจนไม่มีใครรู้ว่า
"โลกที่เดินจากหน้าเว็บ" กับ "โลกที่เดินจากเทอร์มินัล" ต่างกันตรงไหน — ซึ่งเป็นบั๊กที่หายากที่สุด
`daemon.py` จึงเหลือหน้าที่แค่แปลง argparse เป็น `LoopConfig` แล้วเรียก `run_round()` เหมือนกัน

`WorldRunner` เพิ่มมาเพื่อหน้าเว็บโดยเฉพาะ: เดินใน thread เบื้องหลัง หยุดกลางคันได้ และเก็บสรุป
ของรอบล่าสุดไว้ให้หน้าเว็บถามได้ตลอด — ตัว `run_round()` เองไม่รู้จัก thread หรือ HTTP เลย
"""
import os
import threading
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from . import event_log as EL
from . import metrics as M
from . import persist as PS
from . import tuning as TN
from .ai import config_ai as ACFG
from .sim import Sim

STEP_BATCH = 2000   # เดินทีละก้อนย่อยเพื่อให้ "กดหยุด" ตอบสนองภายในไม่กี่วินาที ไม่ต้องรอจบรอบใหญ่


@dataclass
class LoopConfig:
    save_path: str = PS.DEFAULT_PATH
    event_log_path: Optional[str] = None
    seed: int = 0
    tiers: int = 3
    chunk_events: int = 20000
    interval: float = 5.0
    lr: float = 0.1
    autotune: bool = True
    trim_log: bool = True
    keep_recent_events: int = 5000
    llm: bool = False
    llm_drain_budget: int = 20

    def log_path(self) -> str:
        return self.event_log_path or EL.default_log_path(self.save_path)


def load_or_create(cfg: LoopConfig):
    """เดินต่อจากไฟล์เดิมถ้ามี ไม่งั้นสร้างโลกใหม่ — คืน (sim, สร้างใหม่หรือไม่)"""
    try:
        return PS.load_sim(cfg.save_path), False
    except FileNotFoundError:
        return Sim(seed=cfg.seed, tiers=cfg.tiers), True


def run_round(sim, cfg: LoopConfig, state: dict,
              should_stop=None) -> dict:
    """เดินหนึ่งรอบให้จบทุกขั้นตอน แล้วคืนสรุปของรอบนั้น

    `should_stop` เป็นฟังก์ชันไม่มีอาร์กิวเมนต์ที่คืน True เมื่อถูกสั่งหยุด — ถูกถามระหว่างเดินทุก
    ก้อนย่อย `STEP_BATCH` เหตุการณ์ **แต่การเซฟยังเกิดขึ้นเสมอ** แม้ถูกสั่งหยุดกลางรอบ ไม่งั้นงานที่
    เพิ่งเดินไปจะหายทั้งหมดเพียงเพราะกดหยุด
    """
    before_day, t0 = sim.day, time.time()
    baseline = M.checkpoint(sim)
    ran = 0
    exhausted = False
    while ran < cfg.chunk_events:
        if should_stop is not None and should_stop():
            break
        batch = min(STEP_BATCH, cfg.chunk_events - ran)
        sim.run(batch)
        ran += sim.last_run_steps
        if sim.last_run_steps < batch:
            exhausted = True
            break

    # Measure the complete round before flush_and_trim discards its early events.
    metrics = M.summarize(sim, ran, baseline=baseline)

    save_dir = os.path.dirname(cfg.save_path)
    if save_dir:
        os.makedirs(save_dir, exist_ok=True)
    log_dir = os.path.dirname(cfg.log_path())
    if cfg.trim_log and log_dir:
        os.makedirs(log_dir, exist_ok=True)

    flushed = 0
    if cfg.trim_log:
        flushed = EL.flush_and_trim(sim, cfg.log_path(), cfg.keep_recent_events)

    PS.save_sim(sim, cfg.save_path)

    drained = backlog = 0
    if cfg.llm:
        drained = sim.brain_manager.drain_llm_queue(sim, cfg.llm_drain_budget)
        backlog = len(sim.brain_manager.llm_queue)

        # Persist drained results and the remaining queue, including on the last round.
        PS.save_sim(sim, cfg.save_path)

    if cfg.autotune and ran:
        state["overrides"] = TN.propose_update(state.get("overrides", {}), metrics,
                                               learning_rate=cfg.lr)
        TN.save_state(state)
        TN.apply_overrides(state["overrides"])

    return {
        "day_from": before_day, "day_to": sim.day, "year": sim.day // 365,
        "events_run": ran, "alive": len(sim.living()),
        "exhausted": exhausted,
        "advancement_rate": round(metrics.get("advancement_rate", 0.0), 4),
        "org_rate": round(metrics.get("org_rate", 0.0), 3),
        "log_flushed": flushed, "log_kept": len(sim.log),
        "llm_drained": drained, "llm_backlog": backlog,
        "seconds": round(time.time() - t0, 1),
        "at": time.time(),
    }


# ---------------------------------------------------------------- ตัวเดินเบื้องหลังสำหรับหน้าเว็บ
class WorldRunner:
    """เดินโลกไปเรื่อยๆ ใน thread — สั่งเริ่ม/หยุดจากหน้าเว็บได้ ทีละโลกเดียวต่อ process"""

    HISTORY = 12

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.cfg: Optional[LoopConfig] = None
        self.rounds: List[dict] = []
        self.state: str = "idle"        # idle | running | stopping | error
        self.error: str = ""
        self.started_at: float = 0.0
        self.iterations: int = 0
        self.created_world: bool = False

    # -- ถาม -------------------------------------------------------------
    def status(self) -> dict:
        last = self.rounds[-1] if self.rounds else None
        return {
            "state": self.state,
            "error": self.error,
            "iterations": self.iterations,
            "started_at": self.started_at,
            "elapsed": round(time.time() - self.started_at, 1) if self.started_at else 0,
            "created_world": self.created_world,
            "save_path": self.cfg.save_path if self.cfg else "",
            "chunk_events": self.cfg.chunk_events if self.cfg else 0,
            "interval": self.cfg.interval if self.cfg else 0,
            "last": last,
            "rounds": self.rounds[-self.HISTORY:],
        }

    # -- สั่ง -------------------------------------------------------------
    def start(self, cfg: LoopConfig) -> dict:
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                raise RuntimeError("โลกกำลังเดินอยู่แล้ว")
            self._stop.clear()
            self.cfg, self.rounds, self.error = cfg, [], ""
            self.iterations, self.started_at = 0, time.time()
            self.state = "running"
            self._thread = threading.Thread(target=self._loop, daemon=True)
            self._thread.start()
        return self.status()

    def stop(self) -> dict:
        if self.state == "running":
            self.state = "stopping"
            self._stop.set()
        return self.status()

    def join(self, timeout=None) -> None:
        """Wait for the current round's save during a clean server shutdown."""
        thread = self._thread
        if thread is not None:
            thread.join(timeout)

    def _loop(self) -> None:
        cfg = self.cfg
        try:
            ACFG.LLM_ENABLED = cfg.llm
            state = TN.load_state()
            if cfg.autotune and state.get("overrides"):
                TN.apply_overrides(state["overrides"])
            sim, created = load_or_create(cfg)
            self.created_world = created
            while not self._stop.is_set():
                summary = run_round(sim, cfg, state, should_stop=self._stop.is_set)
                self.iterations += 1
                self.rounds.append(summary)
                del self.rounds[:-self.HISTORY]
                if summary["exhausted"]:
                    raise RuntimeError("Simulation scheduler exhausted; saved the last state")
                if self._stop.is_set():
                    break
                # พักเป็นช่วงสั้นๆ เพื่อให้กดหยุดแล้วหยุดจริงภายในไม่กี่ร้อยมิลลิวินาที
                waited = 0.0
                while waited < cfg.interval and not self._stop.is_set():
                    time.sleep(min(0.25, cfg.interval - waited))
                    waited += 0.25
        except Exception as exc:                     # noqa: BLE001 — ต้องรายงานให้หน้าเว็บเห็น
            self.state, self.error = "error", f"{type(exc).__name__}: {exc}"
            return
        self.state = "idle"


RUNNER = WorldRunner()
