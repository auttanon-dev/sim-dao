# -*- coding: utf-8 -*-
"""บันทึก/โหลดสถานะโลกทั้งก้อน — ให้ซิมเดินต่อข้ามการเรียกโปรแกรมได้ ไม่ใช่รันทีเดียวจบ

Sim ทั้งตัวเป็น dataclass/list/dict/random.Random ล้วนๆ pickle ได้ตรงๆ
โดยไม่ต้องเขียน schema เอง — โหลดกลับมาได้ครบทั้ง rng state, คิวเหตุการณ์, log

ไฟล์ save ผูกกับโครงสร้าง dataclass ใน models.py ตอนที่เซฟ การเพิ่ม field ทีหลังจึงต้องมี
migration — ดู SAVE_VERSION กับ _migrate() ข้างล่าง กติกาสองข้อที่ห้ามละเมิด:
  1. migration ทำงานกับ **เซฟที่เก่ากว่ารุ่นปัจจุบันเท่านั้น** ห้ามตัดสินจากค่าของ field
     เพราะโลกที่กำลังเดินอยู่ก็มีค่าว่างได้จริง
  2. migration ห้ามขยับ RNG หลัก ไม่งั้นการอัปเกรด schema จะเปลี่ยนอนาคตของโลกที่เซฟไว้
"""
import os
import pickle
import heapq
import random
import time

from . import config as C

DEFAULT_PATH = "tiandao/world.save"

# ผู้อ่านภายนอกที่ไม่ได้อ่านผ่าน open_for_read (โปรแกรมอื่น, แอนตี้ไวรัส) ยังขวางการแทนไฟล์บน Windows ได้
# เซฟจึงรอให้เขาปล่อยได้ไม่เกินเท่านี้ แล้วล้มอย่างชัดเจนโดยไฟล์เดิมยังอยู่ครบ — ไม่ค้างลูปหลักไม่จำกัด
REPLACE_RETRY_SECONDS = 10.0

# รุ่นของ "ไฟล์เซฟ" ไม่ใช่ของโลก — บอกว่าไฟล์นี้ถูกเขียนโดยโค้ดที่รู้จัก schema รุ่นไหน
#
# ทำไมต้องมี: migration ชุดแรกทั้งหมดตัดสินจาก **ค่าของ field** ("mastery ว่าง = เซฟเก่า")
# ซึ่งแยกเซฟเก่าออกจากเซฟปัจจุบันไม่ได้เลย เพราะโลกที่กำลังเดินอยู่ก็มีคนที่ค่านั้นว่างจริงๆ
# ผลที่วัดได้: เซฟที่เพิ่งเขียนจากโค้ดปัจจุบัน พอโหลดกลับมา mastery เปลี่ยน 15 คน
# bloodline_affinity เปลี่ยน 36 คน แล้วโลกเดินแยกทางกับรันรวดเดียวภายใน ~333 เหตุการณ์
# — การโหลดเซฟกลายเป็นการ "แก้โลก" แทนที่จะเป็นการอ่านโลก
#
# ตอนนี้ไฟล์บอกรุ่นของตัวเองตรงๆ: เซฟรุ่นปัจจุบันโหลดแล้วได้สถานะเดิมเป๊ะ ส่วนเซฟที่ไม่มีรุ่น
# (pickle ของ Sim เปล่าๆ แบบเดิม) คือเซฟก่อนมีระบบนี้ ต้องผ่าน migration ทั้งชุด
#
# เพิ่ม migration ใหม่เมื่อไร ให้บวกเลขนี้ขึ้นหนึ่ง แล้วเพิ่มกิ่ง `if version < N:` ใน _migrate()
#   2 — นาฬิกาโลก (Sim.world_tick_day) และนาฬิกาทรัพยากร (Sim.eco_day)
#   3 — ยุ้งฉางหมู่บ้าน (Sim.granary, food_stats, food_day — tiandao/food.py)
#   4 — ค่าแรงตามเวลา (Sim.market_till, farm_till, wage_stats — tiandao/wages.py) และยุ้งฉางคีย์ (wid, place)
#   5 — เหรียญทองคีย์ตามชั้นของแดนเท่านั้น (เดิมบางจุดคีย์ด้วย wid)
#   6 — ผู้ปกครองเด็ก (Sim.guardian_stats; Character.guardian/wards ได้ค่าว่างจาก __setstate__)
#   7 — ตัวนับใหม่ของ food_stats (ลงไร่ช่วงข้าวขาด) และ guardian_stats (ย้ายไปอยู่กับคนใกล้ข้าว)
#       Character.fieldwork ได้ค่า False จาก __setstate__
#   8 — คนในด่านที่เทิร์นถัดไปถูกนัดไว้หลังวันครบด่าน ตื่นวันครบด่าน (ครบไปแล้ว = ตื่นวันที่โหลด)
#   9 — ตัวนับใหม่ของ food_stats (ทำงานแลกข้าว ข้าวในคุก)
SAVE_VERSION = 9

# ชื่อวัตถุดิบที่เปลี่ยนตอนเลิกใช้คำทับศัพท์ — ใช้แปลงของใน save เก่าให้กลับมาใช้งานได้
RENAMED_MATERIALS = {
    "แร่เหล็กสปริงร้อยพับ": "แร่เหล็กกล้าร้อยพับ",
    "แร่อะดามันเทียมสวรรค์": "แร่วัชรเพชรสวรรค์",
    "แร่หินดาร์กแมตเตอร์": "แร่หินธาตุมืดปฐพี",
    "แร่ออริคัลคัม": "แร่ทองอมตะ",
    "ขนนกฟีนิกซ์โกลาหล": "ขนหงส์เพลิงโกลาหล",
}


# ---------------------------------------------------------------- อ่านกับเขียนไฟล์เซฟพร้อมกัน
# บน Windows os.replace ทับไฟล์ที่ยังมี handle อ่านเปิดอยู่ไม่ได้ (WinError 5) — live viewer poll อ่าน
# world.save ขณะ runner เซฟ แล้ว runner ล้มเป็นสถานะ error ทั้งที่โลกไม่ได้ผิดอะไร
# (ยืนยันใน WORLD_CONDITIONS_REFERENCE_TH.md และทำซ้ำได้ใน test_save_concurrency)
#
# แก้ทั้งสองฝั่ง เพราะวัดบน Windows 11 แล้วว่าแก้ฝั่งเดียวไม่พอ:
#   · ผู้อ่านเปิดไฟล์แบบแชร์สิทธิ์ลบ (FILE_SHARE_DELETE) — open() ของ Python ไม่แชร์สิทธิ์นี้
#   · ผู้เขียนแทนชื่อแบบ POSIX ซึ่งปลดชื่อเดิมออกทันที ผู้อ่านที่อ่านค้างยังอ่านสแนปช็อตเดิมจนจบ
# ผู้อ่านทุกตัวในโครงการ (viewer, dashboard, โรงเขียนนิยาย) อ่านผ่าน read_save จึงได้ผลทั้งหมด
# คนละ process ก็ได้ เพราะเป็นกติกาของระบบไฟล์ ไม่ใช่ lock ใน process
if os.name == "nt":
    import ctypes
    import msvcrt
    from ctypes import wintypes

    _k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _k32.CreateFileW.restype = wintypes.HANDLE
    _k32.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
                                 wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    _k32.SetFileInformationByHandle.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p,
                                                wintypes.DWORD]
    _k32.CloseHandle.argtypes = [wintypes.HANDLE]
    _INVALID_HANDLE = wintypes.HANDLE(-1).value
    _SHARE_ALL = 0x1 | 0x2 | 0x4                 # FILE_SHARE_READ | WRITE | DELETE
    _GENERIC_READ, _DELETE, _OPEN_EXISTING, _NORMAL = 0x80000000, 0x00010000, 3, 0x80
    _FILE_RENAME_INFO_EX = 22
    _RENAME_REPLACE_POSIX = 0x1 | 0x2            # REPLACE_IF_EXISTS | POSIX_SEMANTICS
    # ระบบไฟล์ที่ไม่รองรับการแทนชื่อแบบ POSIX (FAT, network share บางแบบ) ตอบด้วยรหัสเหล่านี้
    _POSIX_RENAME_UNSUPPORTED = {1, 50, 87}

    def _create(path, access):
        handle = _k32.CreateFileW(path, access, _SHARE_ALL, None, _OPEN_EXISTING, _NORMAL, None)
        if handle == _INVALID_HANDLE:
            err = ctypes.get_last_error()
            raise OSError(None, ctypes.FormatError(err), path, err)
        return handle

    def open_for_read(path):
        """เปิดไฟล์เซฟอ่านแบบไม่ขวางผู้เขียน — ใช้แทน open(path, "rb") ทุกที่ที่อ่านไฟล์เซฟ"""
        handle = _create(path, _GENERIC_READ)
        try:
            fd = msvcrt.open_osfhandle(handle, os.O_RDONLY)
        except OSError:
            _k32.CloseHandle(handle)
            raise
        return os.fdopen(fd, "rb")

    def _replace_once(src, dst):
        handle = _create(src, _DELETE)
        try:
            dst = os.path.abspath(dst)

            class _RenameInfo(ctypes.Structure):
                _fields_ = [("Flags", wintypes.DWORD), ("RootDirectory", wintypes.HANDLE),
                            ("FileNameLength", wintypes.DWORD),
                            ("FileName", wintypes.WCHAR * (len(dst) + 1))]

            info = _RenameInfo(_RENAME_REPLACE_POSIX, None, len(dst) * 2, dst)
            if _k32.SetFileInformationByHandle(handle, _FILE_RENAME_INFO_EX, ctypes.byref(info),
                                               ctypes.sizeof(info)):
                return
            err = ctypes.get_last_error()
        finally:
            _k32.CloseHandle(handle)
        if err not in _POSIX_RENAME_UNSUPPORTED:
            raise OSError(None, ctypes.FormatError(err), src, err, dst)
        os.replace(src, dst)
else:
    def open_for_read(path):
        """เปิดไฟล์เซฟอ่าน — บนระบบ POSIX ไฟล์ที่เปิดอ่านอยู่ไม่ขวางการแทนชื่ออยู่แล้ว"""
        return open(path, "rb")

    _replace_once = os.replace


def _replace(src, dst):
    """แทนไฟล์เซฟแบบอะตอมมิก โดยรอผู้อ่านภายนอกที่ถือไฟล์ไว้ได้ไม่เกิน REPLACE_RETRY_SECONDS"""
    deadline = time.monotonic() + REPLACE_RETRY_SECONDS
    delay = 0.02
    while True:
        try:
            _replace_once(src, dst)
            return
        except PermissionError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(delay)
            delay = min(delay * 2, 0.5)


def save_sim(sim, path=DEFAULT_PATH):
    """เซฟแบบอะตอมมิก — เขียนลงไฟล์ชั่วคราวก่อนแล้วค่อยสลับชื่อทับ

    ของเดิมเขียนทับไฟล์จริงตรงๆ ซึ่งใช้เวลาหลายวินาทีสำหรับเซฟขนาด 300 MB ถ้ากระบวนการถูกฆ่า
    ระหว่างนั้น (เครื่องคลาวด์ถูกรีเซ็ต) ไฟล์เซฟจะขาดกลางคันและโหลดไม่ได้อีกเลย — เกิดขึ้นจริง
    ตอนรัน 2,000 ปี: เซฟขาดที่ 273 MB จาก 297 MB ทำให้เสียงาน 1,164 ปี
    os.replace() บนระบบไฟล์เดียวกันเป็นอะตอมมิก ไฟล์เดิมจึงอยู่ครบจนวินาทีที่ไฟล์ใหม่เขียนเสร็จ
    """
    tmp = path + ".tmp"
    with open(tmp, "wb") as f:
        # ห่อด้วยซองบางๆ ที่พกรุ่นของไฟล์มาด้วย — ตัวโลกเองไม่ถูกแตะเลยแม้แต่ field เดียว
        # (รุ่นเป็นคุณสมบัติของ "ไฟล์" ไม่ใช่ของโลก จึงไม่ควรไปนั่งอยู่ใน state ของซิม)
        pickle.dump({"save_version": SAVE_VERSION, "sim": sim}, f,
                    protocol=pickle.HIGHEST_PROTOCOL)
        f.flush()
        os.fsync(f.fileno())
    try:
        _replace(tmp, path)
    except OSError:
        # ไฟล์เซฟเดิมยังอยู่ครบ (last known good) — ทิ้งแค่ไฟล์ชั่วคราว แล้วรายงานความล้มเหลวให้ผู้เรียก
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise


def read_save(path=DEFAULT_PATH):
    """อ่านไฟล์เซฟดิบๆ — คืน (sim, รุ่นของไฟล์) โดยยังไม่ทำ migration ใดๆ

    เซฟก่อนมีระบบรุ่นคือ pickle ของ Sim เปล่าๆ จึงไม่มีซองให้อ่าน — นับเป็นรุ่น 0
    """
    with open_for_read(path) as f:
        blob = pickle.load(f)
    if isinstance(blob, dict) and "sim" in blob:
        return blob["sim"], int(blob.get("save_version", 0))
    return blob, 0


def load_sim(path=DEFAULT_PATH):
    """โหลดโลกกลับมาเดินต่อ

    สัญญาข้อเดียวที่สำคัญที่สุดของฟังก์ชันนี้: **เซฟรุ่นปัจจุบันโหลดแล้วต้องได้สถานะเดิมเป๊ะ**
    ไม่ใช่ "เกือบเดิม" — ไปป์ไลน์นิยายรันต่อจากเซฟเสมอ ถ้าการโหลดขยับสถานะแม้แต่นิดเดียว
    โลกจะเดินไปคนละทางกับรันรวดเดียว แล้วผลลัพธ์จะขึ้นกับว่า "บังเอิญหยุดเซฟตรงไหน"
    ซึ่งทำซ้ำและดีบักไม่ได้เลย  migration ทั้งหมดจึงทำงานเฉพาะกับเซฟที่เก่ากว่ารุ่นปัจจุบัน
    """
    sim, version = read_save(path)
    if version < SAVE_VERSION:
        _migrate(sim, version)
    _repair_queue(sim)
    # แคชที่อนุมานจาก state (ไม่ใช่ตัว state) — ทำใหม่ทุกครั้งที่โหลด เพราะลำดับของ set
    # เปลี่ยนได้หลัง unpickle แคชที่ติดมากับไฟล์จึงเชื่อไม่ได้ (ดู test_determinism)
    sim._alive_ver = getattr(sim, "_alive_ver", 0) + 1
    sim._alive_cache = None
    sim.recount_worlds()
    return sim


def _repair_queue(sim):
    """คิวที่มีใบค้างหลายใบต่อคนเดียวคือคิวที่เสีย — เก็บใบที่เร็วที่สุดต่อคน

    นี่ไม่ใช่ migration แต่เป็นการซ่อม invariant จึงไม่ผูกกับรุ่นของไฟล์: คิวซ้ำเป็นสภาพเสีย
    ไม่ว่าไฟล์จะเก่าหรือใหม่ (เจอครั้งแรกกับเจ้าโกลาหลที่แพ้ซ้ำๆ ในเซฟเก่า) และมันแตะ state
    ก็ต่อเมื่อเจอของเสียจริงเท่านั้น เซฟที่ดีอยู่แล้วจึงผ่านมาโดยไม่ถูกแตะ — ซึ่ง
    test_determinism ล็อกไว้ตรงๆ ว่าเซฟรุ่นปัจจุบันต้องไม่มีใบซ้ำให้ต้องซ่อมตั้งแต่แรก
    """
    pending = {}
    for day, cid in sim.queue:
        if sim.cast[cid].alive:
            pending[cid] = min(day, pending.get(cid, day))
    if len(pending) != sum(sim.cast[cid].alive for _, cid in sim.queue):
        sim.queue = [(day, cid) for cid, day in pending.items()]
        heapq.heapify(sim.queue)


def _migrate(sim, version):
    """ยกเซฟเก่าขึ้นมาให้เท่ารุ่นปัจจุบัน — เรียกเฉพาะเมื่อ version < SAVE_VERSION เท่านั้น

    ข้อห้ามที่ทุก migration ต้องรักษา: **ห้ามขยับ RNG หลักของโลก** ถ้าขยับ โลกที่โหลดจาก
    เซฟเดิมจะเดินไปคนละทางกับที่เคยเดิน เพียงเพราะเราอัปเกรด schema — ที่ต้องสุ่มให้ใช้
    random.Random ที่ผูกกับ (seed, cid) แบบที่เห็นข้างล่าง
    """
    if version < 1:
        _backfill_new_attrs(sim)
    if version < 2:
        # เซฟก่อนมีนาฬิกาโลก: งานของโลกเคยรอเทิร์นตัวละคร จึงให้รอบแรกของนาฬิกาเริ่มทันที
        # (งานแต่ละชิ้นมีตัวกันวันของตัวเอง งานที่ยังไม่ถึงรอบจะข้ามไปเอง) และทรัพยากรคิดการฟื้น
        # ต่อจากวันที่เคยคิดไว้แล้ว (last_day) — ไม่แตะ RNG
        sim.world_tick_day = sim.day
        sim.eco_day = sim.last_day
    if version < 3:
        # เซฟก่อนมียุ้งฉาง: เริ่มยุ้งฉางว่าง นับบัญชีใหม่จากศูนย์ และเริ่มนับเวลาอาหารจากวันนี้
        # ตัวละครได้ food=None จาก Character.__setstate__ แล้วรับเสบียงตั้งต้นตอนระบบอาหารเห็นครั้งแรก
        from . import food as FOOD
        sim.granary = {}
        sim.food_stats = FOOD.new_stats()
        sim.food_day = sim.day
    if version < 4:
        # เซฟก่อนมีค่าแรง: ลิ้นชักว่าง บัญชีเงินเริ่มจากศูนย์ ยุ้งฉางรุ่น 3 คีย์ด้วยสถานที่อย่างเดียว ซึ่งให้แดนที่
        # ใช้ผังเดียวกันกินยุ้งฉางร่วมกัน — ของที่ค้างอยู่ให้แดนแรกที่ใช้ผังนั้น ไม่มีข้าวหายหรือเกิดใหม่
        from . import wages as WAGES
        sim.market_till = {}
        sim.farm_till = {}
        sim.wage_stats = WAGES.new_stats()
        owner = {}
        for w in sim.worlds:
            owner.setdefault(w.place_key, w.wid)
        from . import places as PL
        sim.granary = {(key if isinstance(key, tuple) else (owner.get(PL.PLACES[key][1], 0), key)): v
                       for key, v in sim.granary.items()}
    if version < 5:
        _money_by_tier(sim)
    if version < 6:
        from . import guardians as GUARD
        sim.guardian_stats = GUARD.new_stats()
    if version < 7:
        _add_new_counters(sim)
    if version < 8:
        _wake_at_seclusion_end(sim)
    if version < 9:
        _add_new_counters(sim)


def _add_new_counters(sim):
    """ตัวนับที่เพิ่มเข้ามาใน food_stats และ guardian_stats เริ่มจากศูนย์ ตัวเดิมคงค่าไว้"""
    from . import food as FOOD
    from . import guardians as GUARD
    for stats, fresh in ((sim.food_stats, FOOD.new_stats()), (sim.guardian_stats, GUARD.new_stats())):
        for key, zero in fresh.items():
            stats.setdefault(key, zero)


def _wake_at_seclusion_end(sim):
    """เทิร์นที่นัดไว้หลังวันครบด่าน เลื่อนมาเป็นวันครบด่าน ครบไปแล้วก็ตื่นวันนี้ — ไม่แตะ RNG ไม่เพิ่มใบคิว

    โค้ดก่อนรุ่น 8 นัดเทิร์นถัดไปของคนที่เพิ่งเข้าด่านแบบเดียวกับคนเข้าแดนลับ คือ 2,000–12,000 วัน ทั้งที่ด่านยาว
    แค่ 3–8 ปี (ดู Sim._next_turn) เซฟจริงปีที่ 1,228 มีผู้ใหญ่ 439 คนที่ครบด่านแล้วแต่ยังซ่อนอยู่ รอเทิร์นอีกมัธยฐาน 8 ปี
    """
    moved = False
    queue = []
    for day, cid in sim.queue:
        ch = sim.cast[cid]
        until = getattr(ch, "seclude_until", 0)
        if ch.alive and ch.hidden and 0 < until < day:
            day = max(until, sim.day)
            moved = True
        queue.append((day, cid))
    if moved:
        sim.queue = queue
        heapq.heapify(sim.queue)


def _money_by_tier(sim):
    """ย้ายเหรียญทองที่โค้ดเก่าเก็บไว้ใต้ wid ไปไว้ใต้ชั้นของแดนนั้น — ไม่มีเหรียญเกิดหรือหาย

    `Character.money` คีย์ด้วยชั้นของแดน แต่หลายจุด (ลาดตระเวน ล้างแค้น จับกุม ปล้น ถ่ายทอดวิชา ค่าครองชีพ ฯลฯ)
    เคยเขียนด้วย wid กติกาแยกสองแบบ:
      · คีย์ที่มากกว่าชั้นสูงสุดของโลกนี้ ไม่มีชั้นไหนใช้ จึงเป็น wid แน่นอน → ย้ายไปชั้นของแดนนั้น
      · คีย์ที่อยู่ในช่วงชั้นแต่แดน wid เดียวกันมีชั้นไม่เท่าคีย์ (แดนตกชั้นตอนยุคล่ม) แยกจากตัวเลขอย่างเดียวไม่ได้
        จึงดูว่าเจ้าของอยู่ในแดนนั้นเองไหม ถ้าอยู่ ถือว่าเป็น wid ของแดนที่เขาอยู่ ถ้าไม่อยู่ ปล่อยไว้เป็นเงินชั้นนั้น
    ที่มาของกติกาข้อสอง: เซฟจริงปีที่ 1,228 แดน wid 1 คือแดนมารชั้น 0 ไม่ใช่แดนเซียนชั้น 1 แบบโลกที่สร้างใหม่ เงินใต้
    คีย์ 1 ทั้งหมด 4.81 ล้านทอง 96% เป็นของคนในแดนชั้น 1 (ถูกอยู่แล้ว) ส่วนคนที่อยู่ในแดนมารเองถือ 61,288 ทองใต้คีย์ 1
    ซึ่งแทบแน่นอนว่ามาจากโค้ดที่คีย์ด้วย wid
    """
    worlds = getattr(sim, "worlds", ())
    top = max((w.tier for w in worlds), default=0)
    for ch in getattr(sim, "cast", ()):
        money = getattr(ch, "money", None)
        if not money:
            continue
        home = getattr(ch, "world_id", -1)
        for key in sorted(k for k in money if 0 <= k < len(worlds)):
            tier = worlds[key].tier
            if key == tier or (key <= top and key != home):
                continue
            money[tier] = money.get(tier, 0.0) + money.pop(key)


def _backfill_new_attrs(sim):
    """save ที่เซฟไว้ก่อนมี Cultivator Brain v2 (tiandao/ai/) ยังไม่มี event_bus/brain_manager บน
    object — เติมให้เหมือนตอน __init__ ปกติ เพื่อให้ resume ไฟล์เก่าไม่พัง"""
    if not hasattr(sim, "event_bus"):
        from .ai import BrainManager, EventBus
        sim.event_bus = EventBus()
        sim.brain_manager = BrainManager()
        sim.event_bus.subscribe(sim.brain_manager.on_event)
    for w in getattr(sim, "worlds", ()):
        if not hasattr(w, "resentment"):
            w.resentment = 0.0      # ความบาดหมางต่อแดนบน (เพิ่มมาพร้อมระบบเกณฑ์ขึ้นฟ้า)
        if not hasattr(w, "blood_marks"):
            w.blood_marks = []      # รอยนองเลือดล่าสุด (เพิ่มมาพร้อมวงจรแค้นแบบฮอว์กส์)
        if not hasattr(w, "prices"):
            w.prices = {}           # ราคาวัตถุดิบตามความขาดแคลน (เพิ่มมาพร้อมอุปสงค์อุปทาน)
    if not hasattr(sim, "used_names"):
        # เซฟก่อนมีการกันชื่อซ้ำ — สร้างชุดชื่อจากคนที่มีอยู่ ไม่ขยับ RNG
        sim.used_names = {c.name for c in getattr(sim, "cast", ())}
    for ch in getattr(sim, "cast", ()):
        if not hasattr(ch, "natural_lifespan"):
            # migration ต้องไม่ขยับ RNG หลัก มิฉะนั้นโหลดเซฟเดิมแล้วอนาคตเปลี่ยนเพราะการอัปเกรด schema
            rr = random.Random((getattr(sim, "seed", 0) << 32) ^ ch.cid ^ 0xA631)
            ch.natural_lifespan = rr.randint(0, 100)
        if not hasattr(ch, "longevity_bonus"):
            ch.longevity_bonus = 0
        if not hasattr(ch, "bloodline_blessings"):
            ch.bloodline_blessings = {}
        if not hasattr(ch, "bloodline_affinity"):
            ch.bloodline_affinity = {}
        for line, share in ch.blood.items():
            if share > 0.0 and line not in ch.bloodline_affinity:
                salt = sum((i + 1) * ord(c) for i, c in enumerate(line))
                rr = random.Random((getattr(sim, "seed", 0) << 32) ^ (ch.cid << 8) ^ salt ^ 0xB105)
                ch.bloodline_affinity[line] = round(
                    rr.uniform(C.BLOODLINE_AFFINITY_MIN, C.BLOODLINE_AFFINITY_MAX), 4)
        if not hasattr(ch, "bloodline_grants"):
            ch.bloodline_grants = {}
        if not hasattr(ch, "bloodline_buff"):
            ch.bloodline_buff = 0.0
        if not hasattr(ch, "wants"):
            ch.wants = {}
        if getattr(ch, "birth_wid", -1) < 0:
            ch.birth_wid = ch.world_id   # save เก่า: ถือว่าเกิดที่แดนที่อยู่ตอนเซฟ
        if not getattr(ch, "emotions", None) or not getattr(ch, "desires", None):
            # save ก่อนมีเจ็ดอารมณ์หกปรารถนา — สุ่มใจให้ย้อนหลังด้วย RNG แยกที่ผูกกับ cid
            # (แบบเดียวกับ natural_lifespan/bloodline_affinity ข้างบน) เพื่อไม่ขยับ RNG หลัก
            # ถ้าขยับ โลกที่โหลดจากเซฟเดิมจะเดินไปคนละทางกับที่เคยเดิน เพียงเพราะอัปเกรด schema
            from . import emotions as EM
            rr = random.Random((getattr(sim, "seed", 0) << 32) ^ (ch.cid << 4) ^ 0xE307)
            EM.roll(ch, rr)
            ch.emo_day = getattr(ch, "last_day", 0) or getattr(sim, "day", 0)
        # ---- ธาตุประจำตัว: save ก่อนมีระบบห้าธาตุ ----
        # วัดจริงจากเซฟปีที่ 152: ผู้ฝึก **303 จาก 578 คน (52%) ไม่มีธาตุเลย** และยิ่งขั้นสูง
        # ยิ่งแย่ (ขั้น 5 มีธาตุแค่ 26%) เพราะคนขั้นสูงคือคนที่มีอยู่ก่อนอัปเดตทั้งนั้น
        # ทารกที่เกิดใหม่ได้ธาตุจาก EL.roll ในมือจับกำเนิดทายาท แต่ไม่มีใครเติมให้คนเก่าเลย
        # ผลคือระบบห้าธาตุทั้งระบบ — ฝึกวิชาให้ตรงธาตุ · ขอบได้เปรียบตอนปะทะ · การเลือกศิษย์ —
        # ปิดไม่ทำงานกับคนที่สำคัญที่สุดในโลกพอดี  EL.ensure ตัดสินจาก cid ล้วน ไม่แตะ RNG หลัก
        # โลกที่โหลดจากเซฟเดิมจึงเดินทางเดิม ต่างแค่มีธาตุติดตัวแล้ว
        if not getattr(ch, "element", ""):
            from . import elements as EL
            EL.ensure(ch)
        # ---- ความชำนาญรายวิชา: save ก่อนมีกฎกำลังของการฝึกฝน ----
        # บั๊กคลาสเดียวกัน แต่เจ็บกว่า เพราะ mastery ว่างแปลว่า "ฝึกมาศูนย์ครั้ง" ทั้งที่เจ้าตัว
        # **มีวิชานั้นอยู่ในมือ** ซึ่งเป็นไปไม่ได้ตามกติกาของโลกเอง (ดูมือจับฝึกวิชา:
        # "เรียนจบครั้งแรก = ฝึกไปแล้วหนึ่งครั้ง") ผลที่วัดได้จากเซฟปีที่ 152:
        #   · ผู้ฝึก 345 จาก 432 คนที่ "มีวิชา" สอนวิชาของตัวเองไม่ได้เลย (TEACH_MIN_REPS)
        #     — ตัวเอกชุยอันสั่งถ่ายทอดวิชาให้หานอวิ๋นอวี๋ 4 ครั้ง ได้ "ไม่มีวิชาจะสอน" ทั้ง 4
        #   · rules.skill_power คูณ practice_mastery(0) = 0 ทุกวิชา ทั้งโลกที่โหลดจากเซฟเก่า
        #     จึงถูกลดพลังเงียบๆ เหลือแค่ส่วนฐาน SKILL_BASE_SHARE
        # เติมหนึ่งครั้งต่อวิชาที่ถืออยู่ — เป็นค่าต่ำสุดที่ยังจริง ไม่ใช่การแจกพลังให้ฟรี
        # เพราะเราไม่รู้ว่าเขาฝึกมากี่ครั้ง รู้แค่ว่า "อย่างน้อยหนึ่ง" แน่นอน
        mast = getattr(ch, "mastery", None)
        if not isinstance(mast, dict):
            mast = {}
            ch.mastery = mast
        for _sk in getattr(ch, "skills", ()) or ():
            if mast.get(_sk, 0) < 1:
                mast[_sk] = 1
        # save ที่เซฟไว้ก่อนเลิกใช้คำทับศัพท์ ยังมีวัตถุดิบชื่อเดิมค้างในถุง — ถ้าไม่เปลี่ยนชื่อ
        # ของพวกนั้นจะกลายเป็นของที่ไม่มีสูตรไหนใช้ และขายก็ไม่ได้เพราะไม่มีในตารางราคา
        stock = getattr(ch, "mat_stock", None)
        if stock:
            for old_name, new_name in RENAMED_MATERIALS.items():
                if old_name in stock:
                    stock[new_name] = stock.pop(old_name) + stock.get(new_name, 0)
        wants = getattr(ch, "wants", None)
        if wants:
            for old_name, new_name in RENAMED_MATERIALS.items():
                if old_name in wants:
                    wants[new_name] = max(wants.pop(old_name), wants.get(new_name, 0))
    if not hasattr(sim, "alive_cids"):
        # save เก่าก่อนมี alive_cids index (ดู sim.py) — คำนวณครั้งเดียวตอนโหลด (O(cast) ครั้งเดียว
        # ยอมรับได้ ต่างจากการสแกน cast ทั้งก้อนซ้ำทุกครั้งที่ living()/living_in() ถูกเรียก)
        sim.alive_cids = {c.cid for c in sim.cast if c.alive}
    if not hasattr(sim, "apex_blessings"):
        sim.apex_blessings = {}
    # save ที่สร้างก่อนมีแดนเซียนสาขา/มหาผนึกโกลาหล — worldtree._found_branch() เรียก
    # sim.branch_wids.append() ตรงๆ ถ้าไม่เติมไว้ โลกเก่าจะล้มทั้งซิมทันทีที่ต้นไม้โลกตั้งแดนสาขาแรก
    # (เจอจริง: tiandao/world.save ล้มภายใน 8,000 เหตุการณ์ทั้งเอนจินเดิมและเอนจินที่มีชั้นจิตใจ)
    if not hasattr(sim, "branch_wids"):
        sim.branch_wids = []
    if not hasattr(sim, "lord_seal"):
        sim.lord_seal = 0.0
    if not hasattr(sim, "lord_seals_made"):
        sim.lord_seals_made = 0
    for w in getattr(sim, "worlds", ()):
        if not hasattr(w, "breakthroughs"):
            w.breakthroughs = 0
    for item in getattr(sim, "items", {}).values():
        if not hasattr(item, "lifespan_bonus"):
            from . import crafting as CR
            item.lifespan_bonus = CR.longevity_years(item.name, item.tier, item.grade) if item.kind == "ยาวิเศษ" else 0
    # สร้างดัชนีพรจากผู้สูงสุดในเซฟเดิม แล้วกระจายให้คนมีชีวิตทั้งหมด
    for ch in getattr(sim, "cast", ()):
        if sim._is_apex(ch):
            if not ch.bloodline_blessings:
                # ผู้สูงสุดที่มีอยู่ก่อนอัปเดตต้องได้พรคงที่โดยไม่ขยับ RNG หลักของอนาคต
                rr = random.Random((getattr(sim, "seed", 0) << 32) ^ ch.cid ^ 0xA9E7)
                ch.bloodline_blessings = {
                    line: round(rr.uniform(C.BLOODLINE_BLESS_MIN, C.BLOODLINE_BLESS_MAX), 4)
                    for line, share in ch.blood.items() if share > 0.0
                }
            sim.update_apex_blessing(ch)
    sim.refresh_bloodline_buffs()
