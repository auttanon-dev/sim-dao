# -*- coding: utf-8 -*-
"""สัญญาณปวดที่แยกจากความเสียหายจริง (§25)

ความเสียหายเป็นสถานะเนื้อเยื่อ ส่วน pain เป็นสัญญาณที่ถ่วงตามชนิด/ตำแหน่งและถูก adrenaline
กดได้ชั่วคราว จึงไม่เท่ากับ damage ตรง ๆ ตัวเลขนี้ใช้ลด motor control และให้ใจประเมินความเสี่ยง
แต่ไม่เคยแก้ความเสียหายจริงย้อนกลับ
"""

TISSUE_PAIN = {"skin": 0.45, "fat": 0.15, "muscle": 0.75, "vessel": 0.65,
               "bone": 1.0, "organ": 0.85, "nerve": 1.15}
REGION_PAIN = {"head": 1.10, "chest": 1.05, "abdomen": 1.0,
               "left_arm": 0.85, "right_arm": 0.85,
               "left_leg": 0.90, "right_leg": 0.90}


def level(state, stress_response: float = 0.0) -> float:
    if not state:
        return 0.0
    signal = 0.0
    for region, tissues in state.items():
        local = sum(max(0.0, float(v)) * TISSUE_PAIN.get(t, 0.4)
                    for t, v in tissues.items())
        signal += local * REGION_PAIN.get(region, 1.0)
    # รวมสัญญาณหลายแผลแบบ saturation; adrenaline กดการรับรู้ ไม่ได้รักษาแผล
    saturated = signal / (1.0 + signal)
    return max(0.0, min(1.0, saturated * (1.0 - 0.55 * max(0.0, min(1.0, stress_response)))))


def motor_factor(state, stress_response: float = 0.0) -> float:
    return max(0.55, 1.0 - 0.35 * level(state, stress_response))
