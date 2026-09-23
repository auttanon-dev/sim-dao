# -*- coding: utf-8 -*-
"""Memory Influence — ความทรงจำที่มีแรง จางได้ และถูกตอกย้ำได้

ต่อยอดของเดิม ไม่แทนที่:
  · tiandao/ai/brain.py episodic       = บันทึกดิบว่าเกิดอะไร (ป้อน LLM) — ไม่มีแรง/ไม่จาง
  · character.learn (intent.py)         = EMA ผลลัพธ์ต่อ event kind — ไม่แยกว่า "กับใคร/ที่ไหน"
  · tiandao/ai/memory.py semantic place = EMA อันตรายต่อสถานที่
ที่นี่เพิ่ม "ร่องรอยความจำ" (trace) ที่ผูกกับแท็ก เช่น action:ล่าอสูร · entity:1532 · foe:wolf ·
place:17 พร้อม valence (ดี/ร้าย), ความเข้มข้นทางอารมณ์, ความสำคัญ และการจางตามเวลา

    strength(t) = strength0 × 0.5^(Δt / half_life)
    half_life   = base × (1 + k_imp × importance) × (1 + k_int × intensity)

(Ebbinghaus forgetting curve — การลืมเป็น exponential decay)
เรื่องที่สะเทือนใจและสำคัญจางช้า เรื่องจิ๊บจ๊อยลืมเร็ว · เจอซ้ำ = ตอกย้ำแบบอิ่มตัว
    S ← S(t) + η·(1 + r)·(1 − S(t)/S_max)          η = (0.5 + 0.5·intensity) · δ
    δ = |ผลจริง − ความคาดหวัง|  (prediction error ของ Rescorla–Wagner, มีพื้นขั้นต่ำ)
"""
import math
from dataclasses import dataclass, field
from typing import Dict, Iterable, List


@dataclass
class MemoryTrace:
    tag: str
    valence: float          # -1 (เลวร้าย) .. +1 (ดีมาก)
    intensity: float        # 0..1 ความสะเทือนใจ
    importance: float       # 0..1
    strength: float         # แรง ณ วันที่ day
    day: float
    count: int = 1
    note: str = ""

    def half_life(self, cfg):
        return (cfg.get("memory.half_life", 365.0)
                * (1.0 + cfg.get("memory.importance_gain", 2.0) * self.importance)
                * (1.0 + cfg.get("memory.intensity_gain", 1.5) * self.intensity))

    def strength_at(self, now, cfg):
        age = max(0.0, now - self.day)
        return self.strength * (0.5 ** (age / max(1e-9, self.half_life(cfg))))


@dataclass
class MemoryStore:
    traces: Dict[str, MemoryTrace] = field(default_factory=dict)

    def remember(self, tag, valence, now, cfg, intensity=0.5, importance=0.5, note="", salience=1.0):
        """เพิ่ม/ตอกย้ำความจำ — เจอซ้ำแล้วแรงขึ้นแบบมีเพดาน valence เฉลี่ยถ่วงแรง

        salience = prediction error |ผลจริง − ที่คาด| (Rescorla–Wagner): เรื่องที่เป็นไปตามคาด
        ไม่ค่อยถูกจำ เรื่องที่ผิดคาดถูกจำแรง — กันไม่ให้งานประจำที่สำเร็จซ้ำๆ กลายเป็นความเคยชินล้นเกิน"""
        salience = max(cfg.get("memory.salience_floor", 0.1), min(1.0, salience))
        valence = max(-1.0, min(1.0, valence))
        intensity = max(0.0, min(1.0, intensity))
        importance = max(0.0, min(1.0, importance))
        new_s = (0.5 + 0.5 * intensity) * salience
        old = self.traces.get(tag)
        if old is None:
            self.traces[tag] = MemoryTrace(tag, valence, intensity, importance, new_s, now, 1, note)
        else:
            cur = old.strength_at(now, cfg)
            reinf = 1.0 + cfg.get("memory.reinforcement", 0.5)
            smax = cfg.get("memory.max_strength", 3.0)
            # การตอกย้ำแบบอิ่มตัว (learning curve): ΔS = η·(1 − S/S_max) — ยิ่งจำแน่นยิ่งเพิ่มยาก
            s = min(smax, cur + new_s * reinf * max(0.0, 1.0 - cur / smax))
            w_old = cur / (cur + new_s) if cur + new_s > 0 else 0.0
            old.valence = old.valence * w_old + valence * (1.0 - w_old)
            old.intensity = max(old.intensity * 0.9, intensity)
            old.importance = max(old.importance, importance)
            old.strength, old.day, old.count = s, now, old.count + 1
            old.note = note or old.note
        self._prune(now, cfg)
        return self.traces[tag]

    def recall(self, tags: Iterable[str], now, cfg):
        """คืน [(trace, strength ตอนนี้)] ที่ตรงแท็ก — เรียงตามแรง"""
        out = []
        floor = cfg.get("memory.min_strength", 0.02)
        for t in tags:
            tr = self.traces.get(t)
            if tr is None:
                continue
            s = tr.strength_at(now, cfg)
            if s >= floor:
                out.append((tr, s))
        out.sort(key=lambda p: -p[1])
        return out

    def bias(self, tags, now, cfg):
        """MemoryBias ∈ [-1,1] และรายการเหตุผล"""
        hits = self.recall(tags, now, cfg)
        raw = sum(tr.valence * s for tr, s in hits)
        return math.tanh(raw / cfg.get("memory.bias_squash", 1.0)), hits

    def negative_weight(self, tags, now, cfg):
        """Σ แรงของความจำร้าย — ใช้เพิ่ม risk perception / ความกลัว"""
        return sum(-tr.valence * s for tr, s in self.recall(tags, now, cfg) if tr.valence < 0)

    def _prune(self, now, cfg):
        cap = int(cfg.get("memory.max_traces", 48))
        floor = cfg.get("memory.min_strength", 0.02)
        dead = [t for t, tr in self.traces.items() if tr.strength_at(now, cfg) < floor]
        for t in dead:
            self.traces.pop(t, None)
        if len(self.traces) > cap:
            ranked = sorted(self.traces.values(),
                            key=lambda tr: (tr.strength_at(now, cfg) * (0.5 + tr.importance), tr.tag))
            for tr in ranked[: len(self.traces) - cap]:
                self.traces.pop(tr.tag, None)

    def strongest(self, now, cfg, n=5) -> List[MemoryTrace]:
        return [tr for tr, _ in sorted(((tr, tr.strength_at(now, cfg)) for tr in self.traces.values()),
                                       key=lambda p: -p[1])[:n]]
