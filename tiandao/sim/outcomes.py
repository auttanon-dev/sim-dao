# -*- coding: utf-8 -*-
"""Sim — ตัวช่วยผลลัพธ์"""
from ._common import *  # noqa: F401,F403
from ._common import _REACH_CACHE, _PLACE_SETS, _CENTERS, _reach_from, _auction_q  # noqa: F401


class OutcomeMixin:
    # ------------------------------------------------------------ ผลลัพธ์
    def loot_count(self, ch):
        """ของที่ "ชิงได้" ติดตัวกี่ชิ้น — กฎเดียวกับที่ resolve("ชิงสมบัติ") ใช้ตัดสิน
        (ยาวิเศษไม่นับ เพราะกินหมดแล้วหมดเลย ไม่ใช่สมบัติที่ชิงต่อกันได้)"""
        return sum(1 for i in ch.items
                   if i in self.items and self.items[i].kind != "ยาวิเศษ")

    def aim_theft(self, target, others):
        """เล็งเป้าการชิงสมบัติใหม่ ถ้าคนที่ถูกเลือกไม่มีอะไรติดตัวเลย

        **เจตนายังเป็นของตัวละคร** — เขาเลือกเองว่าจะชิง สิ่งที่แก้คือเป้าให้ตรงกับเจตนานั้น
        ที่ต้องมีเพราะด่านกรองใน `IN.weigh()` ถามแค่ "แถวนี้มีใครมีของให้ชิงไหม" ส่วนชื่อเป้า
        เป็นของตัวละคร ช่องว่างระหว่างสองอย่างนี้วัดได้จากบันทึกจริงสองรอบติด: ตงฟางเฟิน
        ชิงสมบัติจบด้วย "ไม่มีของ" 6/6 ครั้ง (ปีที่ 104-118) และ 5/5 ครั้ง (ปีที่ 118-129)
        รอบหลังพรอมต์ติดป้าย "ไม่มีอะไรมีค่าติดตัว" ให้เห็นทุกคนแล้วด้วย แต่โมเดล 8B ยังเล็ง
        คนเดิม — ในชีวิตที่ลงมือได้ไม่กี่สิบครั้ง เทิร์นที่หายไปแบบนี้แพงมาก

        ไม่ใช่การยัดให้สำเร็จเสมอ: ถ้าทั้งฉากไม่มีใครมีอะไร ก็คืนเป้าเดิมให้ล้มเหลวตามจริง
        และไม่ดึง rng เลย (เลือกแบบคงที่) เพื่อไม่ให้กระทบความคงที่ของโลก
        """
        if target is None or self.loot_count(target) > 0:
            return target
        rich = [c for c in (others or []) if self.loot_count(c) > 0]
        if not rich:
            return target
        return max(rich, key=lambda c: (self.loot_count(c), -c.cid))

    def reach_reason(self, a, t):
        """ทำไมสองคนนี้ถึงเอื้อมถึงกันได้ทั้งที่อยู่คนละที่ — คืนคำอธิบาย หรือ "" ถ้าไม่มีเหตุ

        ใช้เกณฑ์เดียวกับที่ social_pool() ใช้ตัดสินว่าใครติดต่อข้ามระยะได้ (ผูกพัน/จองเวร/
        ศิษย์-อาจารย์/ร่วมสำนัก/ร่วมตระกูล) จึงเป็นการ "อ่านคำตอบเดิม" ไม่ใช่ตั้งเกณฑ์ใหม่
        """
        cid = getattr(t, "cid", None)
        if cid is None or cid == a.cid:
            return ""
        if cid == getattr(a, "master_cid", -1):
            return "เป็นอาจารย์ของเขา"
        if cid in getattr(a, "disciples", ()):
            return "เป็นศิษย์ของเขา"
        if a.rivals.get(cid) or getattr(t, "rivals", {}).get(a.cid):
            return "จองเวรกันอยู่ก่อนแล้ว"
        if a.bonds.get(cid) or getattr(t, "bonds", {}).get(a.cid):
            return "ผูกพันกันอยู่ก่อนแล้ว"
        if a.org is not None and a.org == getattr(t, "org", object()):
            return "ร่วมสำนักเดียวกัน"
        if a.clan >= 0 and a.clan == getattr(t, "clan", -2):
            return "ร่วมตระกูลเดียวกัน"
        return ""
