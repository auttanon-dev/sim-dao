# -*- coding: utf-8 -*-
"""Belief / Knowledge — สิ่งที่ตัวละคร "เชื่อ" ว่าจริง แยกขาดจาก WorldState

    WorldState  : power ของศัตรู = 900         (ความจริง — มีแต่เอนจินที่รู้)
    BeliefState : power ของศัตรู = 300 (0.55)  (สิ่งที่ NPC ตัวนี้เชื่อ + ความมั่นใจ)

Decision Engine อ่านได้เฉพาะ BeliefState ทุกการคำนวณ (risk, reward, social) จึงใช้ค่าที่ตัวละครเชื่อ
ไม่ใช่ค่าจริง NPC จึง "ประเมินผิด เชื่อผิด ถูกหลอก ได้ข่าวลือผิด" ได้ แต่ยังตัดสินใจสมเหตุสมผลจาก
มุมมองของมันเอง

ทุก belief มี: value · confidence · source · day (อายุข้อมูล) · truth (ค่าจริงตอนสังเกต — เก็บไว้ดีบัก
"ความคลาดเคลื่อนจากความจริง" เท่านั้น ห้ามโค้ดตัดสินใจอ่าน)

คณิตศาสตร์ของความเชื่อ (Bayesian / Kalman filter หนึ่งมิติ)
=========================================================
ความมั่นใจ c ∈ (0,1) คือการแปลง precision (1/ความแปรปรวน) ให้อยู่ในช่วงจำกัด

    τ = c / (1 − c)          c = τ / (1 + τ)

หลักฐานสองชิ้นที่เป็นอิสระกันรวมแบบ inverse-variance (สมการ update ของ Kalman filter)
ทำใน log-space เพราะพลังเป็นปริมาณบวกที่ความคลาดเคลื่อนเป็นสัดส่วน (log-normal)

    τ' = τ₁ + τ₂
    ln v' = (τ₁·ln v₁ + τ₂·ln v₂) / τ'          (Kalman gain K = τ₂ / τ')

เวลาผ่านไปข้อมูลเก่าไม่แน่นอนขึ้น (process noise): precision จางแบบ exponential ตามครึ่งชีวิต
ของแหล่งข้อมูล — ข่าวลือจางเร็ว การปะทะด้วยตัวเองจางช้า

    τ(t) = τ₀ · 2^(−age / half_life[source])
"""
import math
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from . import rng as DRNG


@dataclass
class Belief:
    key: str
    value: Any
    confidence: float
    source: str
    day: float
    truth: Any = None          # ค่าจริง ณ ตอนสังเกต — ดีบักเท่านั้น
    count: int = 1

    def error(self):
        """ความคลาดเคลื่อนสัมพัทธ์จากความจริง (None ถ้าไม่รู้/ไม่ใช่ตัวเลข)"""
        if self.truth is None or not isinstance(self.value, (int, float)) \
                or not isinstance(self.truth, (int, float)) or self.truth == 0:
            return None
        return (self.value - self.truth) / abs(self.truth)


@dataclass
class BeliefStore:
    beliefs: Dict[str, Belief] = field(default_factory=dict)

    # ---------------------------------------------------------------- อ่าน
    def confidence(self, key, now, cfg):
        b = self.beliefs.get(key)
        if b is None:
            return 0.0
        return self._decayed(b, now, cfg)

    def value(self, key, default=None):
        b = self.beliefs.get(key)
        return default if b is None else b.value

    def get(self, key, now, cfg):
        """(value, confidence ปัจจุบัน) หรือ (None, 0.0)"""
        b = self.beliefs.get(key)
        if b is None:
            return None, 0.0
        return b.value, self._decayed(b, now, cfg)

    @staticmethod
    def _decayed(b, now, cfg):
        """ความมั่นใจ ณ ตอนนี้ — precision จางแบบ exponential (process noise ของ Kalman filter)
            τ(t) = τ₀ · 2^(−age/half_life)      c = τ / (1 + τ)"""
        hl = (cfg.get("belief.half_life", {}) or {}).get(b.source, cfg.get("memory.half_life", 365))
        age = max(0.0, now - b.day)
        tau = precision(b.confidence) * (0.5 ** (age / max(1e-9, hl)))
        return confidence_of(tau)

    # ---------------------------------------------------------------- เขียน
    def observe(self, key, value, source, now, cfg, confidence=None, truth=None):
        """รวมข้อมูลใหม่เข้ากับความเชื่อเดิม

        ตัวเลข: Kalman / inverse-variance fusion (ดู kalman_fuse) · ค่าอื่น (bool/str): ถ้าตรงกัน ความมั่นใจรวมขึ้น ถ้าขัดกัน ฝั่งที่มั่นใจกว่าชนะ
        แต่ความมั่นใจลดลงตามส่วนต่าง (ข้อมูลขัดกัน = ไม่แน่ใจ)"""
        if confidence is None:
            confidence = (cfg.get("belief.source_confidence", {}) or {}).get(source, 0.5)
        confidence = max(0.0, min(1.0, float(confidence)))
        old = self.beliefs.get(key)
        if old is None:
            self.beliefs[key] = Belief(key, value, confidence, source, now, truth)
            self._prune(now, cfg)
            return self.beliefs[key]
        c_old = self._decayed(old, now, cfg)
        if isinstance(value, (int, float)) and isinstance(old.value, (int, float)) \
                and not isinstance(value, bool):
            v, c = kalman_fuse(old.value, c_old, value, confidence)
        elif value == old.value:
            c = confidence_of(precision(c_old) + precision(confidence))
            v = value
        elif confidence >= c_old:
            v, c = value, confidence - c_old * 0.5
        else:
            v, c = old.value, c_old - confidence * 0.5
        src = source if confidence >= c_old else old.source
        self.beliefs[key] = Belief(key, v, max(0.0, min(1.0, c)), src, now,
                                   truth if truth is not None else old.truth, old.count + 1)
        return self.beliefs[key]

    def hear(self, key, value, now, cfg, source="rumor", teller_trust=1.0, truth=None):
        """ข่าวลือ/คำบอกเล่า — ความมั่นใจ = ค่าตั้งต้นของแหล่ง × ความไว้ใจผู้เล่า"""
        base = (cfg.get("belief.source_confidence", {}) or {}).get(source, 0.35)
        return self.observe(key, value, source, now, cfg,
                            confidence=base * max(0.0, min(1.0, teller_trust)), truth=truth)

    def forget(self, key):
        self.beliefs.pop(key, None)

    def _prune(self, now, cfg):
        cap = int(cfg.get("belief.max_beliefs", 80))
        if len(self.beliefs) <= cap:
            return
        floor = cfg.get("belief.confidence_floor", 0.02)
        ranked = sorted(self.beliefs.values(), key=lambda b: (self._decayed(b, now, cfg), b.key))
        for b in ranked:
            if len(self.beliefs) <= cap and self._decayed(b, now, cfg) > floor:
                break
            self.beliefs.pop(b.key, None)

    def snapshot(self, now, cfg, keys=None):
        out = {}
        for k in (keys if keys is not None else sorted(self.beliefs)):
            b = self.beliefs.get(k)
            if b is not None:
                out[k] = {"value": b.value, "confidence": round(self._decayed(b, now, cfg), 3),
                          "source": b.source, "age": now - b.day, "error": b.error()}
        return out


# ---------------------------------------------------------------- Bayesian helpers
_C_MAX = 0.999


def precision(c):
    c = max(0.0, min(_C_MAX, float(c)))
    return c / (1.0 - c)


def confidence_of(tau):
    tau = max(0.0, float(tau))
    return min(_C_MAX, tau / (1.0 + tau))


def kalman_fuse(v1, c1, v2, c2):
    """รวมค่าประมาณสองค่า (inverse-variance) — log-space ถ้าทั้งคู่เป็นบวก คืน (ค่า, ความมั่นใจ)"""
    t1, t2 = precision(c1), precision(c2)
    tot = t1 + t2
    if tot <= 0:
        return v2, 0.0
    if v1 > 0 and v2 > 0:
        v = math.exp((t1 * math.log(v1) + t2 * math.log(v2)) / tot)
    else:
        v = (t1 * v1 + t2 * v2) / tot
    return v, confidence_of(tot)


# ---------------------------------------------------------------- Perception
def perceive_power(true_power, level_gap, cfg, seed_parts):
    """ผู้สังเกตมองพลังของอีกฝ่าย — คืน (ค่าที่เห็น, ความมั่นใจ)

    measurement model (log-normal):  ln P̂ = ln P + ln κ^g + σ(g)·ε ,  ε ~ N(0,1)
        σ(g) = σ₀ + σ_g · g        κ = 1 − conceal       g = max(0, ช่องว่างระดับ)
    ความมั่นใจของการวัด = c_sight / (1 + k·g)

    level_gap = ระดับของเป้าหมาย − ระดับของผู้มอง (บวก = อีกฝ่ายสูงกว่า)
    · noise log-normal ที่กว้างขึ้นตามช่องว่าง (มองคนเหนือกว่าไม่ทะลุ)
    · คนที่สูงกว่าดูอ่อนกว่าจริง (conceal) — นี่คือที่มาของ "ประเมินศัตรูต่ำไป" ในยุทธภพ
    · noise ผูกกับ (ผู้มอง, เป้า, ช่วงเวลา) จึงคงที่ในช่วงเดียวกัน ไม่กระโดดทุกครั้งที่มอง"""
    up = max(0.0, float(level_gap))
    sd = cfg.get("perception.base_noise", 0.12) + cfg.get("perception.gap_noise", 0.18) * up
    conceal = (1.0 - cfg.get("perception.conceal_per_level", 0.2)) ** up
    seen = max(0.0, true_power) * conceal * math.exp(sd * DRNG.normal(*seed_parts))
    conf = (cfg.get("belief.source_confidence", {}) or {}).get("sight", 0.65) \
        / (1.0 + cfg.get("perception.gap_confidence", 0.35) * up)
    return seen, conf
