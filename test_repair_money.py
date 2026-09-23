# -*- coding: utf-8 -*-
"""เครื่องมือซ่อมเงินที่บั๊กเสกขึ้นมา — ต้องบีบปลายบน ไม่ใช่สลับอันดับคนรวย

    python -m unittest test_repair_money -v

โค้ดเดิมตั้ง org.monthly_resource = 10000 ให้ทุกสำนักทุกเดือนโดยไม่มีใครจ่าย เครื่องปั๊มถูก
ปิดไปแล้ว (เปลี่ยนเป็นวงจรค่าบำรุง → คลัง → จ่ายคืน) แต่เงินที่ปั๊มไปแล้วยังค้างในมือคน
วัดจากเซฟปีที่ 152: เสิ่นอวิ๋น (ขั้น 3) ถือคนเดียว 3,940,297 = 60% ของเงินทั้งโลก
ซึ่งพังกลไกประมูล เพราะเงินคือเพดานการเสนอราคา คนคนนี้ชนะทุกการประมูลตลอดกาล

สิ่งที่ล็อกไว้ที่นี่คือคุณสมบัติของฟังก์ชันบีบ ไม่ใช่ตัวเลขผลลัพธ์ — ตัวเลขเปลี่ยนตามเซฟ
แต่คุณสมบัติสามข้อนี้ห้ามเปลี่ยน ไม่งั้นเครื่องมือจะแก้ประวัติศาสตร์แทนที่จะคืนมัน
"""
import unittest

import repair_money as RM


class TestTheSquashKeepsTheStoryIntact(unittest.TestCase):
    def test_who_is_richer_stays_richer(self):
        """อันดับความมั่งคั่งเป็นข้อเท็จจริงในเรื่อง ห้ามสลับ"""
        xs = [0, 1, 50, 900, 2999, 3000, 3001, 12000, 90000, 400000, 3940297]
        ys = [RM.squash(x) for x in xs]
        self.assertEqual(ys, sorted(ys))
        for i in range(len(xs) - 1):
            self.assertLess(ys[i], ys[i + 1], f"{xs[i]} กับ {xs[i+1]} ถูกบีบจนเท่ากัน")

    def test_ordinary_people_are_not_punished_for_a_sect_bug(self):
        for x in (0, 1, 72, 636, 2999, 3000):
            self.assertEqual(RM.squash(x), x, "ใต้หัวเข่าต้องไม่ขยับสักเหรียญ")

    def test_nothing_survives_above_the_ceiling(self):
        for x in (3001, 10 ** 5, 10 ** 7, 10 ** 12):
            self.assertLessEqual(RM.squash(x), RM.CEIL)
            self.assertLess(RM.squash(x), RM.CEIL + 1e-9)

    def test_it_is_continuous_at_the_knee(self):
        """ไม่มีรอยต่อให้คนที่รวยพอๆ กันกระโดดห่างกันเพราะเลขกลมๆ ตัวเดียว"""
        self.assertAlmostEqual(RM.squash(RM.KNEE), RM.squash(RM.KNEE + 1e-9), places=6)

    def test_the_ceiling_is_what_a_clean_world_actually_produced(self):
        """ค่าคงที่ต้องมาจากการวัด ไม่ใช่เลขที่ชอบ — รันสะอาด 152 ปีได้สูงสุด 11,000"""
        self.assertEqual(RM.CEIL, 11000.0)
        self.assertLess(RM.KNEE, RM.CEIL)


if __name__ == "__main__":
    unittest.main()
