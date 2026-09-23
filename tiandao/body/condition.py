# -*- coding: utf-8 -*-
"""สภาพของร่างกาย ณ ขณะหนึ่ง — ทุกอย่างที่ "เปลี่ยนได้" รวมไว้ที่เดียว

ทำไมต้องมีวัตถุนี้
--------------------------------------------------------------------------------------------
กายวิภาค (`Body`) ไม่เปลี่ยนตลอดชีวิต แต่สภาพเปลี่ยนตลอดเวลา และมีหลายอย่างขึ้นเรื่อยๆ:
Phase 1 มีความล้า · Phase 3 เพิ่มบาดเจ็บ · Phase 4 เพิ่มเลือดกับออกซิเจน · Phase 5 จะเพิ่ม
พลังงานกับอุณหภูมิ ถ้าส่งเป็นพารามิเตอร์แยกกันทีละตัว ลายเซ็นของทุกฟังก์ชันจะยาวขึ้นทุกเฟส
และผู้เรียกทุกคนต้องแก้ตาม

ทุกฟังก์ชันความสามารถจึงรับ `Condition` ตัวเดียว ซึ่งเติมสนามใหม่ได้โดยไม่แตะลายเซ็นใคร
ค่าปริยายคือร่างที่สมบูรณ์ — `Condition()` แปลว่าไม่ล้า ไม่เจ็บ เลือดเต็ม

หน่วยและช่วงค่า
--------------------------------------------------------------------------------------------
    fatigue   0..1   ส่วนของแรงที่เรียกใช้ไม่ได้เพราะล้า (1 = หมดแรงสนิท)
    blood     0..1   สัดส่วนปริมาตรเลือดเทียบระดับปกติของร่างนั้น (1 = เต็ม)
    injury    dict   ความเสียหายรายส่วน/รายเนื้อเยื่อ (ดู injury.py) หรือ None ถ้าไม่เจ็บ
"""

from . import constants as K


class Condition:
    """สภาพปัจจุบันของร่างหนึ่ง — อ่านอย่างเดียว สร้างใหม่ทุกครั้งที่ถาม ราคาถูกมาก"""

    __slots__ = ("fatigue", "blood", "injury")

    def __init__(self, fatigue: float = 0.0, blood: float = 1.0, injury=None):
        self.fatigue = min(1.0, max(0.0, float(fatigue)))
        self.blood = min(1.5, max(0.0, float(blood)))
        self.injury = injury or None

    @classmethod
    def of(cls, character) -> "Condition":
        """อ่านสภาพจากตัวละครโดยตรง — จุดเดียวที่รู้ว่าฟิลด์ไหนเก็บอะไร"""
        return cls(getattr(character, "fatigue", 0.0),
                   getattr(character, "blood_frac", 1.0),
                   getattr(character, "injuries", None))

    # ---------------------------------------------------------------- ตัวคูณที่ได้จากสภาพ
    @property
    def oxygen_factor(self) -> float:
        """ส่วนของสมรรถภาพที่ยังเหลือเมื่อเลือดพร่อง (0..1)

        การส่งออกซิเจน DO2 = ปริมาตรเลือดที่ไหลได้ × ความเข้มข้นออกซิเจน ซึ่งทั้งสองพจน์
        ลดลงพร้อมกันเมื่อเสียเลือด (ดู circulation.py) ที่นี่เก็บเฉพาะ "แล้วยังทำอะไรได้"

        เลือดพร่องเล็กน้อยแทบไม่มีผล เพราะร่างชดเชยด้วยการเร่งหัวใจ — ผลจึงไม่เป็นเส้นตรง
        แต่ทรุดเร็วเมื่อพ้นระดับที่ชดเชยไหว
        """
        if self.blood >= K.BLOOD_COMPENSATED_ABOVE:
            return 1.0
        span = K.BLOOD_COMPENSATED_ABOVE - K.BLOOD_FATAL_BELOW
        if span <= 0.0:
            return 0.0
        left = (self.blood - K.BLOOD_FATAL_BELOW) / span
        return max(0.0, min(1.0, left)) ** K.BLOOD_PERFORMANCE_EXPONENT

    @property
    def effort_factor(self) -> float:
        """ตัวคูณรวมของแรงที่เรียกใช้ได้ — ความล้าและออกซิเจนคูณกัน ไม่ใช่บวกกัน

        คนล้าครึ่งหนึ่งและเสียเลือดจนเหลือสมรรถภาพครึ่งหนึ่ง ออกแรงได้หนึ่งในสี่ ไม่ใช่ศูนย์
        """
        return max(0.0, 1.0 - self.fatigue) * self.oxygen_factor

    @property
    def conscious(self) -> bool:
        """ยังรู้สึกตัวอยู่ไหม — เลือดต่ำกว่าระดับหนึ่งสมองไม่ได้ออกซิเจนพอ"""
        return self.blood > K.BLOOD_UNCONSCIOUS_BELOW

    def explain(self) -> dict:
        return {
            "ความล้า": round(self.fatigue, 3),
            "เลือด (เท่าของปกติ)": round(self.blood, 3),
            "ตัวคูณจากออกซิเจน": round(self.oxygen_factor, 3),
            "ตัวคูณแรงรวม": round(self.effort_factor, 3),
            "รู้สึกตัว": self.conscious,
            "มีบาดเจ็บ": bool(self.injury),
        }


#: สภาพของร่างที่สมบูรณ์ — ใช้เป็นค่าปริยายทุกที่ จึงไม่ต้องสร้างใหม่ซ้ำๆ
HEALTHY = Condition()


def resolve(cond) -> Condition:
    """รับได้ทั้ง Condition, ตัวละคร หรือ None — คืน Condition เสมอ

    มีไว้ให้ผู้เรียกไม่ต้องคิดว่ามีอะไรอยู่ในมือ และให้ค่าปริยายเป็นร่างสมบูรณ์เสมอ

    **ปฏิเสธตัวเลขโดยตั้งใจ** ก่อนหน้านี้ฟังก์ชันความสามารถรับ `fatigue` เป็นทศนิยม
    ตัวที่สอง ถ้าโค้ดเก่าที่ยังส่งแบบนั้นหลุดมา การอ่านค่าด้วย getattr จะได้ค่าปริยาย
    ทั้งหมดแล้วเงียบ — คนเขียนจะเห็นผลลัพธ์ของ "ร่างสมบูรณ์" ทั้งที่ตั้งใจส่งความล้ามา
    ความผิดพลาดแบบนั้นต้องดังตั้งแต่บรรทัดแรก ไม่ใช่กลายเป็นตัวเลขที่ดูสมเหตุสมผล
    """
    if cond is None:
        return HEALTHY
    if isinstance(cond, Condition):
        return cond
    if isinstance(cond, (int, float, bool)):
        raise TypeError(
            "ฟังก์ชันความสามารถรับ Condition หรือตัวละคร ไม่ใช่ตัวเลข — "
            "ถ้าต้องการส่งความล้า ให้ใช้ Condition(fatigue=...)")
    return Condition.of(cond)
