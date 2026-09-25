# -*- coding: utf-8 -*-
"""ข้อต่อเชิงหน้าที่สำหรับ event-driven biomechanics (§6)

Sim Dao ไม่มี pose/physics tick จึงไม่เก็บมุมข้อทุกเฟรม ``state`` เป็น snapshot ของท่าที่กำลัง
ประเมิน มุมและความเร็วเชิงมุมเป็น input ของ action ปัจจุบัน ส่วน ROM, torque และ stability
อนุมานจากกายวิภาคกับบาดเจ็บ การไม่เก็บ pose ปลอมถาวรช่วยไม่ให้ precision เกิน gameplay
"""
import math
from dataclasses import dataclass

from .condition import resolve


ROM = {  # radians, ช่วงใช้งานแบบย่อ ไม่อ้างเป็นขอบเขตทางคลินิก
    "shoulder": (-1.6, 2.6), "elbow": (0.0, 2.5), "wrist": (-1.0, 1.0),
    "hip": (-0.8, 2.1), "knee": (0.0, 2.5), "ankle": (-0.7, 0.8),
    "spine": (-0.6, 0.8),
}
REGION = {"shoulder": "left_arm", "elbow": "left_arm", "wrist": "left_arm",
          "hip": "left_leg", "knee": "left_leg", "ankle": "left_leg", "spine": "chest"}


@dataclass(frozen=True)
class JointState:
    name: str
    position: tuple
    range_of_motion: tuple
    current_angle: float
    angular_velocity: float
    maximum_torque: float
    available_torque: float
    stability: float


def state(body, name: str, cond=None, angle: float = None,
          angular_velocity: float = 0.0) -> JointState:
    if name not in ROM:
        raise ValueError("unknown joint: " + str(name))
    c = resolve(cond)
    lo, hi = ROM[name]
    theta = (lo + hi) * 0.5 if angle is None else max(lo, min(hi, float(angle)))
    # แรงสูงสุดเกิดใกล้กึ่งกลาง ROM; ที่ปลายช่วงเสีย leverage และความยาวกล้ามเนื้อที่เหมาะสม
    half = max(1e-9, (hi - lo) * 0.5)
    length_modifier = max(0.20, math.cos((theta - (lo + hi) * 0.5) / half * math.pi / 2.0))
    velocity_modifier = 1.0 / (1.0 + abs(float(angular_velocity)) * 0.08)
    try:
        maximum = body.joint_torque(name, c)
    except KeyError:  # wrist/ankle ใช้กลุ่มเดียวกับข้อต่อแม่ในโมเดลย่อ
        maximum = body.joint_torque("elbow" if name == "wrist" else "knee", c)
    from . import injury
    stability = injury.region_function(c.injury, REGION[name])
    return JointState(name, (0.0, 0.0, 0.0), (lo, hi), theta, float(angular_velocity),
                      maximum, maximum * length_modifier * velocity_modifier * stability,
                      stability)
