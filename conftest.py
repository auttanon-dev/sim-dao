# -*- coding: utf-8 -*-
"""ให้ pytest รันไฟล์เทสต์แบบสคริปต์ (มี main() ที่เรียก test_xxx(...) เองตามลำดับ) ได้ โดยไม่แก้ assertion ใดๆ

ไฟล์อย่าง test_writer / test_paths / test_worldtree / test_coalition เดินซิมหนึ่งครั้งใน main() แล้วส่งค่าต่อกัน
เป็นทอดๆ (sim → pkg → agent/script, sim → decided, sim → br ...) pytest เห็นพารามิเตอร์เหล่านี้เป็น fixture
ที่ไม่มีอยู่จริง ไฟล์นี้จึง:

1. ประกาศ fixture scope="module" ทุกชื่อที่ main() สร้าง (sim, cfg, pkg, decided, br, lp, strikes, ...) — ค่าได้จาก
   การเดินคำสั่งใน main() ของไฟล์นั้นตามลำดับจนชื่อนั้นถูกกำหนด (ScriptState) ซิมจึงเดินครั้งเดียวต่อไฟล์
   ค่าทุกตัวเป็นค่าเดียวกับที่ main() ส่ง รวมถึงค่าที่เทสต์ก่อนหน้าคืนมา (pkg = test_package(...))
2. เรียงเทสต์ตามลำดับที่ main() เรียก — บางเทสต์แก้ซิมที่ใช้ร่วม (test_tree_death_breaks_balance ฆ่าต้นไม้โลก
   main() จึงเรียกเป็นตัวสุดท้าย แม้ประกาศไว้ก่อนตัวอื่นในไฟล์)
3. เรียกเทสต์เองแทน pytest (pytest_pyfunc_call) เพื่อ:
   - ส่งพารามิเตอร์ที่มีค่าตั้งต้นด้วยค่าเดียวกับ main() — pytest ไม่ถือว่าเป็น fixture
     (test_no_solo_win(sim, others=()) ถ้าไม่ส่ง others จะตรวจแค่โลกเดียวแทนห้าโลกตามที่ main() ตรวจ)
   - ไม่เตือนว่าเทสต์คืนค่า — การคืนค่าคือทางส่งต่อให้เทสต์ถัดไปตามแบบเดิมของไฟล์
ใช้กับไฟล์ที่มี main() และมีพารามิเตอร์เป็นค่าที่ main() สร้างเท่านั้น ไฟล์ unittest และไฟล์อื่นไม่ถูกแตะ
"""
import ast
import builtins
import hashlib
import inspect
import os

import pytest

# ไม่เก็บอะไรใน out/ (ผลลัพธ์ของเทสต์และเครื่องมือ มีสำเนาโค้ดที่มีไฟล์ชื่อ test_* ด้วย) และ tools/ — ซ้ำกับ norecursedirs ใน pytest.ini
collect_ignore = ["out", "tools"]

_WORLD_SAVE = os.path.abspath(os.path.join(os.path.dirname(__file__), "tiandao", "world.save"))
# ค่าที่ autotune เรียนรู้ข้ามรัน — เทสต์ห้ามสร้างหรือเขียนทับ (ปกติถูกชี้ไปไฟล์ชั่วคราวโดย _learned_config_isolated แล้ว)
_LEARNED = os.path.abspath(os.path.join(os.path.dirname(__file__), "tiandao", "learned_config.json"))


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


@pytest.fixture(scope="session", autouse=True)
def _learned_config_isolated(tmp_path_factory):
    """เทสต์ไม่อ่านและไม่เขียน tiandao/learned_config.json ของผู้ใช้

    world loop (tiandao/worldloop.py) ที่ autotune=True — ค่าตั้งต้นของ POST /api/world/start ซึ่ง test_novel_web เรียก —
    โหลดไฟล์นี้แล้ว setattr ทับ tiandao.config ทั้ง process และเขียนค่าที่ขยับใหม่ลงไฟล์ทุกรอบ ผลของเทสต์ที่รันทีหลัง
    (test_paths) จึงขึ้นกับประวัติการรันครั้งก่อนๆ ที่สะสมในไฟล์ ระหว่างทดสอบจึงชี้ load_state/save_state ไปไฟล์ชั่วคราวที่ว่าง"""
    from tiandao import tuning as TN
    scratch = str(tmp_path_factory.mktemp("tuning") / "learned_config.json")
    real_load, real_save = TN.load_state, TN.save_state
    TN.load_state = lambda path=scratch: real_load(path)
    TN.save_state = lambda state, path=scratch: real_save(state, path)
    try:
        yield
    finally:
        TN.load_state, TN.save_state = real_load, real_save


_GLOBAL_MODULES = ("tiandao.config", "tiandao.ai.config_ai", "tiandao.ai.llm_agent")


@pytest.fixture(scope="module", autouse=True)
def _restore_module_globals():
    """คืนค่าตัวแปรระดับโมดูลของ config ทุกตัวหลังจบแต่ละไฟล์เทสต์ — ไฟล์ที่เขียนทับ global โดยไม่คืน
    (world loop ใส่ค่า autotune ทับ tiandao.config, test_novel_web แทน llm_agent.OllamaAgent) ไม่รั่วไปถึงไฟล์ถัดไป"""
    import copy
    import importlib
    saved = {}
    for name in _GLOBAL_MODULES:
        mod = importlib.import_module(name)
        snap = {}
        for k, v in vars(mod).items():
            if k.startswith("__"):
                continue
            try:
                snap[k] = copy.deepcopy(v)       # ตาราง dict/list ใน config ถูกแก้แบบ in-place ได้ด้วย
            except Exception:
                snap[k] = v
        saved[name] = (mod, snap)
    yield
    for mod, snap in saved.values():
        for k in [k for k in vars(mod) if not k.startswith("__") and k not in snap]:
            delattr(mod, k)
        for k, v in snap.items():
            cur = getattr(mod, k, None)
            try:
                same = cur is v or bool(cur == v)
            except Exception:
                same = False
            if not same:                         # คืนเฉพาะที่เปลี่ยน — ที่ไม่เปลี่ยนคงวัตถุเดิม (ที่อื่นอาจถืออ้างอิงไว้)
                setattr(mod, k, v)


@pytest.fixture(scope="session", autouse=True)
def _world_save_read_only():
    """tiandao/world.save ต้องอ่านได้อย่างเดียวตลอดการทดสอบ — เปิดเพื่อเขียนเมื่อไรล้มทันที และ checksum ก่อน/หลังต้องเท่ากัน
    (test_novel_web สั่งเดินโลกผ่านหน้าเว็บ ตัวเทสต์เปลี่ยน dashboard.SAVE_PATH ไปไฟล์ชั่วคราวก่อนแล้ว นี่คือตาข่ายกันพลาด)"""
    before = _sha256(_WORLD_SAVE) if os.path.exists(_WORLD_SAVE) else None
    learned_before = _sha256(_LEARNED) if os.path.exists(_LEARNED) else None
    real_open = builtins.open

    def guarded_open(file, mode="r", *a, **kw):
        if isinstance(file, (str, bytes, os.PathLike)) and any(c in mode for c in "wax+"):
            target = os.path.abspath(os.fsdecode(file))
            if target == _WORLD_SAVE or target.startswith(_WORLD_SAVE + ".") or target == _LEARNED:
                raise PermissionError(f"เทสต์พยายามเขียน {target} — world.save ต้องอ่านได้อย่างเดียว")
        return real_open(file, mode, *a, **kw)

    builtins.open = guarded_open
    try:
        yield
    finally:
        builtins.open = real_open
    after = _sha256(_WORLD_SAVE) if os.path.exists(_WORLD_SAVE) else None
    print(f"\nworld.save sha256 before={before} after={after}")
    assert before == after, "world.save เปลี่ยนระหว่างการทดสอบ"
    learned_after = _sha256(_LEARNED) if os.path.exists(_LEARNED) else None
    assert learned_before == learned_after, "tiandao/learned_config.json ถูกสร้างหรือเขียนทับระหว่างการทดสอบ"


class ScriptState:
    """เดินคำสั่งใน main() ของโมดูลทีละคำสั่งใน namespace เดียวกัน จนได้ชื่อที่ต้องการ"""

    def __init__(self, module):
        source = inspect.getsource(module)
        tree = ast.parse(source)
        main = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "main")
        self.module = module
        self.stmts = list(main.body)
        self.next = 0
        # สำเนา namespace ของโมดูล + ตัวแปรท้องถิ่นของ main() ใน dict เดียว (generator/comprehension ใน main เห็นได้)
        self.ns = dict(module.__dict__)
        self.defined = set()
        self.order = []                  # ชื่อเทสต์ตามลำดับที่ main() เรียก
        for stmt in self.stmts:
            for node in ast.walk(stmt):
                if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                        and node.func.id.startswith("test_") and node.func.id not in self.order):
                    self.order.append(node.func.id)
        self.names = set()               # ชื่อที่ main() กำหนดค่า (คำสั่งระดับบนของ main)
        for stmt in self.stmts:
            for node in ast.walk(stmt):
                if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
                    self.names.add(node.id)

    @staticmethod
    def _calls(stmt, fname):
        """คำสั่งระดับบนของ main() นี้คือ `fname(...)` หรือ `x, y = fname(...)` หรือไม่"""
        value = stmt.value if isinstance(stmt, (ast.Expr, ast.Assign)) else None
        return (isinstance(value, ast.Call) and isinstance(value.func, ast.Name) and value.func.id == fname)

    def run_test(self, fname, fn, kwargs):
        """รันเทสต์ครั้งเดียว แล้วเก็บค่าที่คืนไว้เป็นตัวแปรเดียวกับใน main() (pkg = test_package(...))
        fixture ของเทสต์ถัดไปจึงได้ค่านี้โดยไม่ต้องเรียกซ้ำ — คำสั่งอื่นก่อนหน้า (print ฯลฯ) ยังเดินตามลำดับเดิม"""
        index = next((i for i in range(self.next, len(self.stmts)) if self._calls(self.stmts[i], fname)), None)
        if index is None:                 # main() เรียกไปแล้วตอนสร้าง fixture ก่อนหน้า หรือเรียกในบล็อกซ้อน
            fn(**kwargs)
            return
        while self.next < index:
            self._exec(self.stmts[self.next])
        stmt = self.stmts[index]
        self.next = index + 1
        result = fn(**kwargs)
        if isinstance(stmt, ast.Assign):
            self.ns["__conftest_result__"] = result
            unpack = ast.Assign(targets=stmt.targets, value=ast.Name("__conftest_result__", ast.Load()))
            self._exec(ast.fix_missing_locations(ast.copy_location(unpack, stmt)), advance=False)

    def _exec(self, stmt, advance=True):
        if advance:
            self.next += 1
        code = compile(ast.Module(body=[stmt], type_ignores=[]), self.module.__file__, "exec")
        exec(code, self.ns)
        self.defined |= {n.id for n in ast.walk(stmt) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)}

    def get(self, name):
        while name not in self.defined:
            if self.next >= len(self.stmts):
                raise LookupError(f"{self.module.__name__}.main() ไม่ได้กำหนดค่า {name!r}")
            self._exec(self.stmts[self.next])
        return self.ns[name]


_STATES = {}


def _state(module):
    if module.__name__ not in _STATES:
        _STATES[module.__name__] = ScriptState(module)
    return _STATES[module.__name__]


def _is_script(module):
    """ไฟล์เทสต์แบบสคริปต์: มี main() และมี test_ ที่รับพารามิเตอร์ซึ่ง main() สร้าง"""
    if module is None or not callable(getattr(module, "main", None)):
        return False
    try:
        state = _state(module)
    except (OSError, StopIteration, SyntaxError):
        return False
    for fname in state.order:
        fn = getattr(module, fname, None)
        if fn and set(inspect.signature(fn).parameters) & state.names:
            return True
    return False


# fixture ทุกชื่อที่ main() ของไฟล์แบบสคริปต์ส่งให้เทสต์ — scope="module" เพราะซิมที่เดินหลายปีช้ามาก
_FIXTURE_NAMES = ("sim", "cfg", "parsed", "scene", "ctx_map", "by_cid", "pkg", "agent", "script",
                  "decided", "br", "lord", "lp", "strikes", "won", "lost", "others")


def _make_fixture(name):
    @pytest.fixture(scope="module", name=name)
    def _fixture(request):
        if not _is_script(request.module):
            pytest.skip(f"fixture {name!r} มีเฉพาะไฟล์เทสต์แบบสคริปต์ที่ main() สร้างค่านี้")
        return _state(request.module).get(name)
    return _fixture


for _name in _FIXTURE_NAMES:
    globals()[f"_fixture_{_name}"] = _make_fixture(_name)


def pytest_collection_modifyitems(session, config, items):
    """เรียงเทสต์ในไฟล์แบบสคริปต์ตามลำดับที่ main() เรียก — ไฟล์อื่นคงลำดับเดิม"""
    def key(pair):
        index, item = pair
        module = getattr(item, "module", None)
        if _is_script(module):
            order = _state(module).order
            name = item.originalname or item.name
            if name in order:
                first = min(i for i, (_j, it) in enumerate(indexed) if it.module is module)
                return (first, order.index(name))
        return (index, 0)
    indexed = list(enumerate(items))
    items[:] = [it for _i, it in sorted(indexed, key=key)]


@pytest.hookimpl(tryfirst=True)
def pytest_pyfunc_call(pyfuncitem):
    module = getattr(pyfuncitem, "module", None)
    if not _is_script(module):
        return None
    fn = pyfuncitem.obj
    state = _state(module)
    kwargs = {}
    for pname, param in inspect.signature(fn).parameters.items():
        if pname in pyfuncitem.funcargs:
            kwargs[pname] = pyfuncitem.funcargs[pname]
        elif param.default is not inspect.Parameter.empty and pname in state.names:
            kwargs[pname] = state.get(pname)      # ค่าเดียวกับที่ main() ส่ง แทนค่าตั้งต้นของฟังก์ชัน
    state.run_test(pyfuncitem.originalname or pyfuncitem.name, fn, kwargs)
    return True
