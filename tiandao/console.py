# -*- coding: utf-8 -*-
"""ทางออกของข้อความทั้งหมด — ให้ซิมพิมพ์ภาษาไทยกับอิโมจิได้โดยไม่ขึ้นกับหน้าคอนโซล

ปัญหาจริงบนวินโดวส์: ถ้า stdout ไม่ใช่ UTF-8 (คอนโซลเริ่มต้นเป็น cp874/cp1252, ถูก redirect
ลงไฟล์, หรือรันเป็นบริการ/งานเบื้องหลัง) `print("🌲 ...")` จะโยน UnicodeEncodeError **กลางซิม**
แล้วล้มทั้งรัน — ทั้งที่สิ่งที่พังคือการแสดงผล ไม่ใช่ตรรกะของโลก การเดินของโลกไม่ควรขึ้นกับว่า
หน้าจอที่คนดูอยู่รองรับตัวอักษรอะไร

สองชั้นตั้งใจให้ทับกัน:
  1. `enable_utf8()` — ที่ import ของแพ็กเกจ ปรับ stdout/stderr ให้เป็น UTF-8 แบบไม่โยน
     (errors="replace") ครั้งเดียวต่อโปรเซส แก้ที่ต้นเหตุสำหรับทุก entry point พร้อมกัน
  2. `safe_print()` — ตาข่ายชั้นสอง สำหรับสตรีมที่ปรับไม่ได้ (ถูกห่อโดย pytest, ไฟล์ที่เปิดมา
     ด้วย encoding อื่นแล้วส่งเข้ามาทาง redirect_stdout ฯลฯ) พิมพ์ซ้ำด้วยตัวแทนอักขระ
     แทนที่จะโยนข้อผิดพลาดขึ้นไปถึงตรรกะของซิม

ที่ไม่ทำ: ไม่ตัดภาษาไทยหรืออิโมจิออกจากข้อความ ข้อความพวกนั้นคือหน้าตาของโลกใบนี้
"""
import sys

_DONE = False


def enable_utf8():
    """ปรับ stdout/stderr ให้เขียน UTF-8 ได้โดยไม่โยนข้อผิดพลาด — เรียกซ้ำได้ ไม่มีผลข้างเคียง

    เงียบเสมอเมื่อทำไม่ได้ (สตรีมถูกแทนด้วย StringIO, ถูกปิดไปแล้ว, หรือรุ่นไพธอนที่ไม่มี
    reconfigure) เพราะนี่เป็นการ "ปรับให้ดีขึ้นถ้าทำได้" ไม่ใช่เงื่อนไขที่โปรแกรมต้องพึ่ง
    """
    global _DONE
    if _DONE:
        return
    _DONE = True
    for name in ("stdout", "stderr"):
        stream = getattr(sys, name, None)
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError, AttributeError):
            pass


def _fold(text, encoding):
    """ทำให้ข้อความเขียนลงสตรีมที่แคบกว่าได้ — อักขระที่เข้ารหัสไม่ได้กลายเป็นตัวแทน"""
    try:
        return text.encode(encoding, "replace").decode(encoding, "replace")
    except (LookupError, UnicodeError):
        return text.encode("ascii", "backslashreplace").decode("ascii")


def safe_print(*args, **kwargs):
    """print() ที่ไม่มีวันล้มซิมเพราะหน้าคอนโซลเข้ารหัสตัวอักษรไม่ได้"""
    try:
        print(*args, **kwargs)
        return
    except UnicodeEncodeError:
        pass
    stream = kwargs.get("file") or sys.stdout
    encoding = getattr(stream, "encoding", None) or "ascii"
    folded = [_fold(a, encoding) if isinstance(a, str) else _fold(str(a), encoding)
              for a in args]
    try:
        print(*folded, **kwargs)
    except UnicodeEncodeError:
        # สตรีมที่รายงาน encoding ไม่ตรงกับความจริง — ยอมทิ้งบรรทัดดีกว่าล้มทั้งซิม
        pass
