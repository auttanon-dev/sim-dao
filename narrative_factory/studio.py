# -*- coding: utf-8 -*-
"""Phase L2 — Novel Studio: ชั้นบริการให้หน้าเว็บสั่งเขียนนิยายได้ โดยไม่ต้องรู้จักไปป์ไลน์ข้างใน

ทำไมต้องมีไฟล์นี้ ไม่ใส่ลง `dashboard.py` ตรงๆ
---------------------------------------------------------------------------------------------
`dashboard.py` เป็นตัว route บางๆ ที่อ่านไฟล์ save แล้วคืน JSON — ทุก endpoint ของมัน "โหลดโลกใหม่
ทุกครั้งที่ถูกเรียก" ซึ่งใช้ได้กับหน้าที่แค่ดูสถานะ แต่ใช้กับงานเขียนนิยายไม่ได้เลยสามข้อ:

  1. **โหลดโลกครั้งละหลายวินาที** — ไฟล์ save ระดับ 8 MB ขึ้นไป ถ้าโหลดใหม่ทุกคลิก หน้าเว็บจะค้าง
     ตลอดเวลา ที่นี่จึงแคชไว้ตาม (path, mtime) — ไฟล์เปลี่ยนเมื่อไหร่ค่อยโหลดใหม่เอง
  2. **การแยกฉากแพงกว่าโหลดโลกอีก** — `extract_scenes` เดินทั้ง log ทีเดียว แคชผลไว้แล้วหั่นตาม
     ตัวละครทีหลัง ไม่ใช่แยกใหม่ทุกครั้งที่เปลี่ยนตัวเอก
  3. **หนึ่งบทใช้เวลาเป็นนาที** — เรียกโมเดล 9 ครั้งขึ้นไปต่อบท ถ้าให้ HTTP request รอจนจบ
     เบราว์เซอร์จะ timeout ก่อนเสมอ งานจริงจึงเดินใน thread แยกเป็น "งาน" ที่หน้าเว็บ poll ดู
     ความคืบหน้าได้ และสั่งหยุดกลางคันได้

ไฟล์นี้ไม่มี FastAPI/HTML อยู่เลยโดยตั้งใจ — เรียกจากสคริปต์บรรทัดคำสั่งหรือเทสต์ก็ได้เหมือนกัน
"""
import collections
import os
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional

from tiandao import event_log as EL
from tiandao import persist as PS
from tiandao.ai import config_ai as ACFG
from tiandao.ai import llm_agent as LLM

from . import context_builder as CB
from . import parser as P
from . import scene_cast as SCAST
from . import scene_extractor as SE
from . import writer as W

MAX_CANDIDATES = 60


# ---------------------------------------------------------------- แคชโลก
class WorldCache:
    """โลกหนึ่งใบที่โหลดไว้พร้อมของที่แพงในการคำนวณ — ผูกกับ mtime ของไฟล์ save

    เก็บใบเดียวพอ: เครื่องที่รันหน้านี้คือเครื่องเดียวกับที่รัน Ollama อยู่แล้ว การถือโลกสองใบพร้อมกัน
    ในหน่วยความจำไม่ได้ช่วยอะไร นอกจากแย่ง RAM กับโมเดล
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._key = None
        self.sim = None
        self.parsed = None
        self.by_cid = None
        self.presence = None
        self.cfg = None
        self._scenes_by_cid: Optional[Dict[int, list]] = None
        self.loaded_at = 0.0

    def load(self, save_path: str, event_log_path: Optional[str] = None):
        """โหลด (หรือใช้ของเดิม) — คืน self เสมอ, โยน FileNotFoundError ถ้าไม่มีไฟล์"""
        mtime = os.path.getmtime(save_path)
        key = (os.path.abspath(save_path), mtime)
        with self._lock:
            if key == self._key and self.sim is not None:
                return self
            sim = PS.load_sim(save_path)
            cfg = P.load_config()
            parsed = P.parse_log(sim, event_log_path or EL.default_log_path(save_path))
            self.sim, self.cfg, self.parsed = sim, cfg, parsed
            self.by_cid = SE.index_by_character(parsed)
            # ต้องใช้ log เต็ม (parsed) ไม่ใช่ sim.log — daemon จะ flush+trim ให้ sim.log
            # เหลือแค่ 5,000 อันล่าสุด พอโลกเดินยาวๆ ตำแหน่งของทุกคนก่อนหน้านั้นจะหายหมด
            self.presence = SCAST.Presence(parsed)
            self._scenes_by_cid = None
            self._key = key
            self.loaded_at = time.time()
            return self

    def scenes_of(self, cid: int) -> list:
        """ฉากของตัวละครคนหนึ่ง — แยกฉากทั้ง log ครั้งเดียวแล้วจำไว้ (ดู docstring หัวไฟล์ ข้อ 2)"""
        with self._lock:
            if self._scenes_by_cid is None:
                grouped: Dict[int, list] = {}
                for s in SE.extract_scenes(self.parsed, self.sim, self.cfg):
                    grouped.setdefault(s.focal_cid, []).append(s)
                self._scenes_by_cid = grouped
        return self._scenes_by_cid.get(cid, [])


WORLD = WorldCache()


# ---------------------------------------------------------------- รายชื่อผู้ที่คู่ควรเป็นตัวเอก
def candidates(save_path: str, limit: int = MAX_CANDIDATES,
               min_points: int = SCAST.MIN_TURNING_POINTS,
               event_log_path: Optional[str] = None) -> List[dict]:
    """ชีวิตที่มีจุดเปลี่ยนมากพอจะเป็นนิยาย พร้อมของที่ใช้เลือกด้วยตา ไม่ต้องจำเลข cid"""
    w = WORLD.load(save_path, event_log_path)
    n_events = collections.Counter(e.actor for e in w.parsed)
    out = []
    for cid, tps in SCAST.novel_candidates(w.parsed, w.sim, min_points=min_points)[:limit]:
        ch = w.sim.cast[cid]
        first, last = tps[0], tps[-1]
        total = n_events.get(cid, len(tps))
        out.append({
            "cid": cid,
            "name": ch.name,
            "realm": ch.realm_name(),
            "dao": ch.dao,
            "race": ch.race(),
            "archetype": ch.archetype,
            "world": w.sim.world(ch.world_id).name,
            "alive": bool(ch.alive),
            "turning_points": len(tps),
            "events": total,
            # "ความเข้มข้น" = สัดส่วนเหตุการณ์ในชีวิตเขาที่เปลี่ยนอะไรบางอย่างจริง
            # วัดจริงจากโลก 238,000 เหตุการณ์: คนที่อยู่ 0-20 ปีได้ 0.47 แต่คนที่อยู่เกิน 180 ปี
            # เหลือ 0.11 — ชีวิตช่วงปลายกลายเป็นกิจวัตรซ้ำ อยู่นานจึงไม่เท่ากับมีเรื่องเล่ามาก
            # คนที่ให้บทเยอะที่สุดในโลกนั้น (55 บท) เป็นแค่ขั้น "หลอมกระดูก" ไม่ใช่คนที่เก่งที่สุด
            "density": round(len(tps) / max(1, total), 2),
            "years": round((last.day - first.day) / 365, 1),
            "year_from": first.day // 365,
            "year_to": last.day // 365,
            "org": (w.sim.orgs[ch.org].name
                    if ch.org is not None and ch.org < len(w.sim.orgs) else ""),
        })
    return out


def ollama_models(host: str = ACFG.OLLAMA_HOST) -> List[str]:
    """ชื่อโมเดลที่ติดตั้งไว้จริงบนเครื่องนี้ — ให้หน้าเว็บทำเป็น dropdown แทนการพิมพ์ชื่อเอง

    คืนลิสต์ว่างถ้า Ollama ไม่ได้เปิดอยู่ (ไม่โยน error) — หน้าเว็บจะ fallback ไปใช้ค่าใน config_ai
    """
    try:
        import httpx
        resp = httpx.get(f"{host}/api/tags", timeout=5.0)
        resp.raise_for_status()
        return sorted(m["name"] for m in resp.json().get("models", []) if m.get("name"))
    except Exception:
        return []


# ---------------------------------------------------------------- โครงนิยาย (ไม่เรียกโมเดล)
def _chapter_meta(i: int, pkg: W.ScenePackage) -> dict:
    return {
        "index": i,
        "scene_id": pkg.scene_id,
        "title": f"บทที่ {i} · {pkg.scene_type_th}",
        "subtitle": f"ปีที่ {pkg.year} {pkg.season} · {pkg.place_name}"
                    + ("" if pkg.building in ("", "-") else f" · {pkg.building}"),
        "changes": list(pkg.changes),
        "cast": [c.name for c in pkg.cast],
        "events": list(pkg.events),
        "weather": pkg.weather,
    }


def _package_for(w: WorldCache, scene, cid: int, target_chars: int) -> W.ScenePackage:
    ctx_map = CB.build_scene_context(scene, w.sim, w.by_cid, w.cfg)
    pkg = W.build_package(scene, w.sim, ctx_map, w.by_cid.get(cid, []),
                          presence=w.presence, config=w.cfg)
    pkg.target_chars = target_chars
    return pkg


def outline(save_path: str, cid: int, chapters: int = 0,
            target_chars: int = ACFG.SCENE_TARGET_CHARS,
            event_log_path: Optional[str] = None) -> dict:
    """โครงนิยายทั้งเรื่องโดยไม่จ่าย GPU สักนิด — ดูก่อนว่าคุ้มค่าจะเขียนไหม"""
    w = WORLD.load(save_path, event_log_path)
    scenes = w.scenes_of(cid)
    if chapters > 0:
        scenes = scenes[:chapters]
    ch = w.sim.cast[cid]
    return {
        "cid": cid, "name": ch.name, "realm": ch.realm_name(), "dao": ch.dao,
        "n_chapters": len(scenes),
        "chapters": [_chapter_meta(i, _package_for(w, s, cid, target_chars))
                     for i, s in enumerate(scenes, 1)],
    }


# ---------------------------------------------------------------- งานเขียนจริง (เดินใน thread)
@dataclass
class Chapter:
    index: int
    scene_id: str
    title: str
    subtitle: str
    status: str = "รอคิว"        # รอคิว | กำลังเขียน | เสร็จ | ข้าม
    chars: int = 0
    dialogue: int = 0
    calls: int = 0
    rewrites: int = 0
    issues: List[str] = field(default_factory=list)
    prose: str = ""
    seconds: float = 0.0


@dataclass
class Job:
    job_id: str
    save_path: str
    cid: int
    name: str
    prose_model: str
    structure_model: str
    target_chars: int
    chapters: List[Chapter] = field(default_factory=list)
    state: str = "queued"        # queued | running | done | stopped | error
    error: str = ""
    started_at: float = 0.0
    finished_at: float = 0.0
    out_path: str = ""           # ไฟล์ .md ที่เซฟทับทุกครั้งที่จบหนึ่งบท (ดู autosave())
    saved_at: float = 0.0

    def as_dict(self) -> dict:
        d = asdict(self)
        done = [c for c in self.chapters if c.status == "เสร็จ"]
        elapsed = (self.finished_at or time.time()) - (self.started_at or time.time())
        d["summary"] = {
            "done": len(done),
            "total": len(self.chapters),
            "chars": sum(c.chars for c in done),
            "dialogue": sum(c.dialogue for c in done),
            "calls": sum(c.calls for c in self.chapters),
            "flagged": sum(1 for c in done if c.issues),
            "elapsed": round(elapsed, 1),
        }
        return d

    def markdown(self) -> str:
        done = [c for c in self.chapters if c.status == "เสร็จ"]
        head = [f"# {self.name}\n",
                f"*เขียนจาก {self.save_path} · {len(done)}/{len(self.chapters)} บท · "
                f"ร้อยแก้ว {self.prose_model} · โครง {self.structure_model}*"]
        parts = head
        for c in done:
            parts.append(f"## {c.title}\n\n*{c.subtitle}*")
            parts.append(c.prose)
        return "\n\n".join(parts)

    def autosave(self) -> str:
        """เขียนทับไฟล์เดิมทุกครั้งที่จบหนึ่งบท — ไม่รอจนจบทั้งเรื่อง

        นิยายหนึ่งเรื่องใช้เวลาระดับชั่วโมง (บทละ 9 ครั้งของโมเดล 8B) การเซฟตอนจบอย่างเดียวแปลว่า
        ปิดเบราว์เซอร์ ไฟดับ หรือเซิร์ฟเวอร์รีสตาร์ตเมื่อไหร่ งานทั้งหมดหายเมื่อนั้น — เขียนทับไฟล์เดิม
        (ไม่สร้างไฟล์ใหม่ต่อบท) เพื่อให้มีไฟล์เดียวที่เป็นความจริงล่าสุดเสมอ
        """
        if not self.out_path:
            safe = "".join(ch for ch in self.name if ch not in '\\/:*?"<>|').strip() or str(self.cid)
            os.makedirs(ACFG.NOVEL_OUT_DIR, exist_ok=True)
            self.out_path = os.path.join(ACFG.NOVEL_OUT_DIR,
                                         f"novel_{self.cid}_{safe}_{self.job_id}.md")
        tmp = self.out_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(self.markdown())
        os.replace(tmp, self.out_path)   # เขียนลงไฟล์ชั่วคราวก่อนแล้วสลับ กันไฟล์พังถ้าดับกลางเขียน
        self.saved_at = time.time()
        return self.out_path


class _Runner:
    """คิวงานเขียน — ทีละงานเดียวเสมอ เพราะ GPU มีใบเดียวและโมเดลตัวหนึ่งกินหน่วยความจำเกือบหมด"""

    def __init__(self) -> None:
        self.jobs: Dict[str, Job] = {}
        self._world: Dict[str, "WorldCache"] = {}
        self._stop: Dict[str, bool] = {}
        self._lock = threading.Lock()
        self._busy = False

    # -- สร้าง/ถาม -------------------------------------------------------
    def start(self, save_path: str, cid: int, chapters: int, prose_model: str,
              structure_model: str, target_chars: int,
              event_log_path: Optional[str] = None) -> Job:
        with self._lock:
            if self._busy:
                raise RuntimeError("มีงานเขียนที่ยังไม่จบอยู่ — รอให้จบหรือกดหยุดก่อน")
            self._busy = True
        try:
            w = WORLD.load(save_path, event_log_path)
            scenes = w.scenes_of(cid)
            if chapters > 0:
                scenes = scenes[:chapters]
            if not scenes:
                raise ValueError(f"ไม่พบฉากของ cid={cid} เลย")
            job = Job(job_id=uuid.uuid4().hex[:12], save_path=save_path, cid=cid,
                      name=w.sim.cast[cid].name, prose_model=prose_model,
                      structure_model=structure_model, target_chars=target_chars)
            for i, s in enumerate(scenes, 1):
                job.chapters.append(Chapter(index=i, scene_id=s.scene_id,
                                            title=f"บทที่ {i}", subtitle=""))
            self.jobs[job.job_id] = job
            self._stop[job.job_id] = False
            # ยึดโลกใบที่โหลดไว้ตอนเริ่มงานเอาไว้กับงานนี้เลย ไม่โหลดใหม่ตอนเขียนซ้ำ — ถ้าโลกยัง
            # เดินอยู่ (ปุ่ม "เดินโลก" หรือ daemon.py) ไฟล์ save จะถูกเขียนทับเรื่อยๆ WorldCache
            # จะโหลดใบใหม่ให้ แล้ว scene_id ของนิยายที่กำลังเขียนอยู่จะไม่ตรงกับใบใหม่อีกต่อไป
            self._world[job.job_id] = w
            threading.Thread(target=self._run, args=(job, scenes, w), daemon=True).start()
            return job
        except Exception:
            with self._lock:
                self._busy = False
            raise

    def get(self, job_id: str) -> Optional[Job]:
        return self.jobs.get(job_id)

    def stop(self, job_id: str) -> bool:
        if job_id not in self.jobs:
            return False
        self._stop[job_id] = True
        return True

    # -- ตัวเดินงาน ------------------------------------------------------
    def _scribe(self, job: Job) -> W.SceneWriter:
        agent = LLM.OllamaAgent(model=job.prose_model, timeout=ACFG.SCENE_PASS_TIMEOUT)
        return W.SceneWriter(agent=agent, structure_model=job.structure_model,
                             prose_model=job.prose_model)

    def _write_one(self, job: Job, w: WorldCache, scene, chap: Chapter) -> None:
        t0 = time.time()
        chap.status = "กำลังเขียน"
        pkg = _package_for(w, scene, job.cid, job.target_chars)
        meta = _chapter_meta(chap.index, pkg)
        chap.title, chap.subtitle = meta["title"], meta["subtitle"]
        script = self._scribe(job).write(pkg)
        chap.prose = script.prose
        chap.chars = len(script.prose)
        chap.dialogue = script.dialogue_count
        chap.calls = script.calls
        chap.rewrites = sum(b.rewrites for b in script.beats)
        chap.issues = script.issues + [f"{b.stage}: {x}" for b in script.beats for x in b.issues]
        chap.seconds = round(time.time() - t0, 1)
        chap.status = "เสร็จ"
        try:
            job.autosave()
        except OSError as exc:                        # noqa: BLE001 — เซฟไม่ได้ไม่ควรล้มทั้งงาน
            chap.issues = list(chap.issues) + [f"เซฟไฟล์ไม่สำเร็จ: {exc}"]

    def _run(self, job: Job, scenes, w: WorldCache) -> None:
        job.state, job.started_at = "running", time.time()
        try:
            for scene, chap in zip(scenes, job.chapters):
                if self._stop.get(job.job_id):
                    job.state = "stopped"
                    break
                self._write_one(job, w, scene, chap)
            else:
                job.state = "done"
        except Exception as exc:                      # noqa: BLE001 — ต้องรายงานให้หน้าเว็บเห็น
            job.state, job.error = "error", f"{type(exc).__name__}: {exc}"
        finally:
            job.finished_at = time.time()
            with self._lock:
                self._busy = False

    # -- เขียนบทเดียวซ้ำ --------------------------------------------------
    def rewrite(self, job_id: str, index: int) -> Job:
        """สั่งเขียนบทเดียวใหม่ — ใช้ตอนบทนั้นตัวตรวจไม่ผ่าน หรืออ่านแล้วไม่ถูกใจ

        เดินใน thread เหมือนงานหลัก และกินคิวเดียวกัน (GPU ใบเดียว) ผลทับของเดิมในงานเดิม
        ไม่สร้างงานใหม่ — เพื่อให้ปุ่มดาวน์โหลดยังได้ไฟล์เดียวที่ครบทุกบทเสมอ
        """
        job = self.jobs.get(job_id)
        if job is None:
            raise KeyError("ไม่พบงานนี้")
        chap = next((c for c in job.chapters if c.index == index), None)
        if chap is None:
            raise KeyError(f"ไม่พบบทที่ {index}")
        with self._lock:
            if self._busy:
                raise RuntimeError("มีงานเขียนที่ยังไม่จบอยู่ — รอให้จบก่อน")
            self._busy = True
        # ต้องกลับไปเป็น running ระหว่างเขียนซ้ำ ไม่งั้นหน้าเว็บที่ poll อยู่จะเห็นว่า "จบแล้ว"
        # แล้วหยุด poll ทันที ผู้ใช้จะไม่มีวันเห็นบทที่เพิ่งสั่งเขียนใหม่ปรากฏขึ้น (และปุ่มดาวน์โหลด
        # จะได้ไฟล์ที่ขาดบทนั้นไปเลย เพราะ markdown() ข้ามบทที่ยังเขียนไม่เสร็จ)
        job.state = "running"
        job.finished_at = 0.0

        def work():
            try:
                w = self._world.get(job.job_id) or WORLD.load(job.save_path)
                scenes = w.scenes_of(job.cid)
                scene = next((s for s in scenes if s.scene_id == chap.scene_id), None)
                if scene is None:
                    raise ValueError(f"ฉาก {chap.scene_id} หายไปจากโลกที่โหลดอยู่")
                self._write_one(job, w, scene, chap)
            except Exception as exc:                  # noqa: BLE001
                chap.status = "เสร็จ"
                chap.issues = [f"เขียนซ้ำไม่สำเร็จ: {type(exc).__name__}: {exc}"]
            finally:
                job.state = ("done" if all(c.status == "เสร็จ" for c in job.chapters)
                             else "stopped")
                job.finished_at = time.time()
                with self._lock:
                    self._busy = False

        threading.Thread(target=work, daemon=True).start()
        return job


RUNNER = _Runner()
