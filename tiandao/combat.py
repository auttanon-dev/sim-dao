# -*- coding: utf-8 -*-
"""ทางเข้าเก่าของการปะทะ — ส่งต่อให้ rules.fight ที่เดียว (ผลชนะ แผล ความตาย และการริบของมาจากที่นั้น)

เดิมไฟล์นี้คิดพลังอีกสูตรหนึ่ง (ขั้นต่างกันคูณ ±50% คัมภีร์กินปราณ สุ่ม ±20%) และไม่ลงแผลให้ใครเลย ผู้เรียกแต่ละที่
ต้องตัดสินความตายเอง ผลของการปะทะเดียวกันจึงต่างกันตามว่าเรียกทางไหน คงไว้แค่รูปคืนค่าเดิมให้ผู้เรียกเก่า
"""
from tiandao import config as C
from tiandao import rules as R

DAO_ADVANTAGE = C.DAO_ADVANTAGE   # ตารางย้ายไปอยู่ config.py แล้ว (rules.py ก็ต้องใช้)


def resolve_combat(attacker, defender, world, sim, lethal=False):
    """คืน (ผู้ชนะ, ผู้แพ้, บันทึก, หนีรอด) — ผู้ชนะริบของผู้แพ้ lethal=False คือประลองไม่ถึงตาย"""
    win, lose, _margin, res = R.fight(sim, world, attacker, defender, sim.rng, day=sim.day,
                                      lethal_at=None if lethal else float("inf"), plunder=True)
    log = f"⚔️ [{attacker.name}] ปะทะ [{defender.name}] — [{win.name}] ชนะ · [{lose.name}] {res}"
    return win, lose, log, res == "หนีรอด"
