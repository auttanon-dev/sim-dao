# -*- coding: utf-8 -*-
"""สุ่มแบบ "ไร้สถานะ" สำหรับ Decision Engine

เอนจินเดิมเดินด้วย sim.rng ตัวเดียว — ถ้า Decision Engine ไปดึงเลขจากตัวนั้น ลำดับเลขสุ่มของ
ทั้งโลกจะเลื่อนหมดแม้แต่ตอนที่ระบบนี้ไม่ได้เปลี่ยนการตัดสินใจเลย และการรันต่อจาก save จะต้องเก็บ
สถานะ RNG ของเราเพิ่ม ที่นี่จึงสร้างเลขสุ่มจาก hash ของ (seed, สิ่งที่ระบุจังหวะนั้น) แทน:
  · ค่าเดิมทุกครั้งที่ถามด้วย key เดิม → reproducible 100% ทั้งจาก seed และจาก save
  · ไม่แตะ sim.rng เลย
"""
import math
import random

_MASK = (1 << 64) - 1


def splitmix64(x):
    x = (x + 0x9E3779B97F4A7C15) & _MASK
    z = x
    z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & _MASK
    z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & _MASK
    return z ^ (z >> 31)


def _fold(parts):
    h = 0x6A09E667F3BCC909
    for p in parts:
        if isinstance(p, str):
            v = 0
            for ch in p.encode("utf-8"):
                v = (v * 131 + ch) & _MASK
            p = v
        h = splitmix64(h ^ (int(p) & _MASK))
    return h


def derive_seed(*parts):
    return _fold(parts)


def uniform(*parts):
    """[0,1) จาก key"""
    return (_fold(parts) >> 11) * (1.0 / (1 << 53))


def normal(*parts):
    """N(0,1) จาก key (Box-Muller)"""
    u1 = max(1e-12, uniform(*parts, 1))
    u2 = uniform(*parts, 2)
    return math.sqrt(-2.0 * math.log(u1)) * math.cos(2.0 * math.pi * u2)


def rng_for(*parts):
    return random.Random(derive_seed(*parts))
