"""Persistent serial fiction: grow the existing world, then write its next chapter."""
import copy
from dataclasses import asdict, is_dataclass
import hashlib
import json
import os
from pathlib import Path
import threading
import time

from tiandao import worldloop as WL, event_log as EL, persist as PS
from tiandao.ai import config_ai as ACFG
from . import studio, scene_cast, writer
from .writer_backend import WriterBackend
from .natural_writer import NaturalSceneWriter, STYLE_VERSION


class ProcessLease:
    def __init__(self, path):
        self.stream = open(path + '.novel.lock', 'a+b')
        self.stream.seek(0, 2)
        if self.stream.tell() == 0:
            self.stream.write(b'0'); self.stream.flush()
        self.stream.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(self.stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            self.stream.close()
            raise RuntimeError('มีโรงนิยายอีกชุดกำลังใช้โลกนี้อยู่') from exc

    def close(self):
        self.stream.close()


def atomic_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    with temporary.open('w', encoding='utf-8') as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2)
        stream.flush(); os.fsync(stream.fileno())
    os.replace(temporary, path)


class Library:
    def __init__(self, folder, save_path):
        self.folder = Path(folder)
        self.folder.mkdir(parents=True, exist_ok=True)
        self.manifest = self.folder / 'series.json'
        self.save_path = os.path.abspath(save_path)
        if self.manifest.exists():
            self.book = json.loads(self.manifest.read_text(encoding='utf-8'))
            if os.path.normcase(self.book['save_path']) != os.path.normcase(self.save_path):
                raise ValueError('ชุดนิยายนี้ผูกกับโลกคนละไฟล์')
        else:
            self.book = {'title':'บันทึกยุทธภพ', 'save_path':self.save_path, 'cid':None, 'name':'', 'volume':1}
            self.save()
        self.event_log = str(self.folder / 'world.events.jsonl')
        if not Path(self.event_log).exists():
            # Start from the current save, never combine unrelated old archive files.
            sim = PS.load_sim(self.save_path)
            EL.append_events(self.event_log, sim.log)

    def save(self):
        atomic_json(self.manifest, self.book)

    def chapters(self):
        return [json.loads(p.read_text(encoding='utf-8')) for p in sorted(self.folder.glob('chapter-*.json'))]

    def append(self, chapter):
        chapters = self.chapters()
        if any(c['scene_id'] == chapter['scene_id'] for c in chapters):
            return False
        chapter = {**chapter, 'index':len(chapters)+1}
        atomic_json(self.folder / f"chapter-{chapter['index']:06d}.json", chapter)
        return True

    def checkpoint_key(self, pkg, backend):
        payload = {'version':2, 'style':STYLE_VERSION, 'package':asdict(pkg) if is_dataclass(pkg) else vars(pkg),
                   'writer':backend.public_status(), 'base_url':backend.base_url}
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True,
                             default=lambda value:sorted(value)).encode('utf-8')
        return hashlib.sha256(encoded).hexdigest()

    def save_checkpoint(self, key, script):
        atomic_json(self.folder / 'work-in-progress.json',
                    {'key':key, 'script':asdict(script), 'updated_at':time.time()})

    def load_checkpoint(self, key):
        path = self.folder / 'work-in-progress.json'
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
            if data['key'] != key:
                return None
            fields = dict(data['script'])
            beats = [writer.WrittenBeat(**beat) for beat in fields.pop('beats')]
            for beat in beats:
                if not all(isinstance(getattr(beat, name), str) for name in ('stage','outline','prose')):
                    raise ValueError('invalid beat text')
                if not isinstance(beat.lines, list) or any(
                    not isinstance(line, dict) or not all(isinstance(line.get(k), str)
                    for k in ('speaker','line','action')) for line in beat.lines):
                    raise ValueError('invalid dialogue')
            return writer.SceneScript(beats=beats, **fields)
        except (ValueError, KeyError, TypeError) as exc:
            raise RuntimeError('อ่านงานเขียนที่บันทึกระหว่างทางไม่ได้ กรุณาตรวจ work-in-progress.json') from exc


class SerialRunner:
    def __init__(self):
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = None
        self.library = None
        self.state = 'idle'
        self.message = 'ยังไม่ได้เริ่ม'
        self.error = ''
        self.backend = WriterBackend.from_env()

    def configure(self, save_path, folder):
        self.library = Library(folder, save_path)

    def status(self):
        chapters = self.library.chapters() if self.library else []
        return {'state':self.state, 'message':self.message, 'error':self.error,
                'book':self.library.book if self.library else {}, 'writer':self.backend.public_status(),
                'chapters':[{k:v for k,v in c.items() if k != 'prose'} for c in chapters]}

    def start(self):
        with self._lock:
            if self._thread and self._thread.is_alive():
                raise RuntimeError('ระบบกำลังทำงานอยู่แล้ว')
            if self.library is None:
                raise RuntimeError('ยังไม่ได้ตั้งค่าโลก')
            if WL.RUNNER.status()['state'] in ('running','stopping'):
                raise RuntimeError('กรุณาพักตัวรันโลกเดิมก่อนเริ่มโรงนิยาย')
            self._lease = ProcessLease(self.library.save_path)
            self._stop.clear(); self.error = ''; self.state = 'running'
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()
        return self.status()

    def stop(self):
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self.state = 'stopping'; self.message = 'กำลังพักหลังคำตอบของโมเดลรอบนี้'
        return self.status()

    def join(self):
        if self._thread:
            self._thread.join()

    def _grow_world(self):
        cfg = WL.LoopConfig(save_path=self.library.save_path, chunk_events=100,
                            event_log_path=self.library.event_log,
                            interval=3600, autotune=False, llm=False)
        self.message = 'โลกกำลังดำเนินชีวิต รอจุดเปลี่ยนของเรื่อง'
        WL.RUNNER.start(cfg)
        try:
            while WL.RUNNER.iterations == 0 and WL.RUNNER.state == 'running' and not self._stop.wait(.1):
                pass
        finally:
            WL.RUNNER.stop(); WL.RUNNER.join()
        if WL.RUNNER.error:
            raise RuntimeError(WL.RUNNER.error)

    def _next(self, world):
        chapters = self.library.chapters()
        if chapters and world.sim.seq < max(c['anchor_seq'] for c in chapters):
            raise RuntimeError('บันทึกโลกเก่ากว่าตอนล่าสุด กรุณาใช้โลกที่เดินต่อจากนิยายชุดนี้')
        consumed = {c['scene_id'] for c in chapters}
        book = self.library.book
        if book['cid'] is None:
            choices = scene_cast.novel_candidates(world.parsed, world.sim, min_points=3)
            if not choices:
                return None
            book['cid'] = choices[0][0]
            book['name'] = world.sim.cast[book['cid']].name
            self.library.save()
        cid = book['cid']
        scenes = sorted(world.scenes_of(cid), key=lambda s:s.events[-1].seq)
        last_seq = max((c['anchor_seq'] for c in chapters if c['cid'] == cid), default=-1)
        remaining = [s for s in scenes if s.scene_id not in consumed and s.events[-1].seq > last_seq]
        if remaining:
            return remaining[0]
        if not world.sim.cast[cid].alive:
            previous = {c['cid'] for c in chapters}
            choices = scene_cast.novel_candidates(world.parsed, world.sim, min_points=3)
            # A new volume follows someone still alive after the previous volume.
            for candidate, _ in choices:
                if candidate not in previous and world.sim.cast[candidate].alive:
                    book.update(cid=candidate, name=world.sim.cast[candidate].name, volume=book['volume']+1)
                    self.library.save()
                    return self._next(world)
        return None

    def _run(self):
        try:
            failures = 0
            while not self._stop.is_set():
                ready, reason = self.backend.readiness()
                if not ready:
                    self.message = reason; self.state = 'waiting_model'
                    self._stop.wait(20); continue
                self.state = 'running'
                world = studio.WorldCache().load(self.library.save_path, self.library.event_log)
                scene = self._next(world)
                if scene is None:
                    self._grow_world(); self._stop.wait(1); continue
                chapters = self.library.chapters()
                book = self.library.book
                scene = copy.deepcopy(scene)
                prior = [c for c in chapters if c['cid'] == book['cid']]
                last_seq = prior[-1]['anchor_seq'] if prior else -1
                scene.events = [e for e in scene.events if e.seq > last_seq]
                if not scene.events:
                    raise RuntimeError('ลำดับเหตุการณ์ย้อนหลัง ต้องตรวจบันทึกโลก')
                scene.day_start = scene.events[0].day
                pkg = studio._package_for(world, scene, book['cid'], ACFG.SCENE_TARGET_CHARS)
                pkg.previous_chapter = prior[-1]['prose'][-1400:] if prior else ''
                self.message = f"กำลังเขียนตอนที่ {len(chapters)+1} · {book['name']}"
                def progress(message):
                    if not self._stop.is_set():
                        self.message = f"ตอนที่ {len(chapters)+1} · {message}"
                agent = self.backend.agent()
                checkpoint_key = self.library.checkpoint_key(pkg, self.backend)
                resume = self.library.load_checkpoint(checkpoint_key)
                script = NaturalSceneWriter(agent=agent, structure_model=self.backend.structure_model,
                                            prose_model=self.backend.prose_model,
                                            should_stop=self._stop.is_set, progress=progress,
                                            resume=resume, checkpoint=lambda script:
                                            self.library.save_checkpoint(checkpoint_key, script)).write(pkg)
                if self._stop.is_set():
                    break
                issues = script.issues + [issue for beat in script.beats for issue in beat.issues]
                chapter = {'scene_id':scene.scene_id, 'cid':book['cid'], 'name':book['name'],
                           'volume':book['volume'], 'title':pkg.scene_type_th,
                           'day':scene.day_end, 'place':pkg.place_name,
                           'anchor_seq':scene.events[-1].seq, 'event_seqs':[e.seq for e in scene.events],
                           'prose':script.prose, 'created_at':time.time(), 'model':self.backend.prose_model,
                           'structure_model':self.backend.structure_model, 'provider':self.backend.provider,
                           'style':STYLE_VERSION}
                if not script.used_llm or issues:
                    atomic_json(self.library.folder / 'draft.json', {**chapter, 'issues':issues})
                    failures += 1
                    if failures >= 3:
                        raise RuntimeError('ร่างตอนนี้ยังไม่ผ่านการตรวจหลังลอง 3 ครั้ง เก็บร่างไว้แล้ว')
                    self.message = 'กำลังแก้ร่างให้ผ่านการตรวจ'; self._stop.wait(5); continue
                self.library.append(chapter)
                failures = 0; self.message = 'บันทึกตอนใหม่แล้ว กำลังเตรียมตอนต่อไป'
                self._stop.wait(2)
        except InterruptedError:
            pass
        except Exception as exc:
            self.state = 'error'; self.error = str(exc); self.message = 'ระบบพักเพราะพบปัญหา'
            return
        finally:
            self._lease.close()
        self.state = 'idle'; self.message = 'พักอยู่ ตอนที่เขียนเสร็จเก็บไว้ครบแล้ว'


RUNNER = SerialRunner()
