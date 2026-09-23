# -*- coding: utf-8 -*-
"""แพ็กเกจหลักของโลกจำลอง

ปรับทางออกของข้อความให้เป็น UTF-8 ตั้งแต่ import แรก — entry point ทุกตัวของโปรเจกต์นี้
(run.py, daemon.py, dashboard.py, สคริปต์ทดสอบ ฯลฯ) import tiandao เสมอ จุดนี้จึงเป็น
"ที่เดียว" ที่ครอบได้ทั้งหมดโดยไม่ต้องไล่แก้ทีละไฟล์ ดู tiandao/console.py สำหรับเหตุผลเต็ม
"""
from .console import enable_utf8, safe_print   # noqa: F401  (re-export ให้ entry point เรียกได้)

enable_utf8()
