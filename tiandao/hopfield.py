# -*- coding: utf-8 -*-
"""ความจำเชิงเชื่อมโยงของตัวละคร — modern Hopfield network

    from tiandao import hopfield as HF
    mem = HF.Memory(beta=8.0)
    mem.store(x_vector, "ล้างแค้น")
    out = mem.recall(x_now)      # -> Recall(kind, energy, confidence, ...)

สมการ
=====
    E(x) = -1/β · log( Σ_μ exp(β · ξ_μᵀ x) ) + ½‖x‖²

    ξ_μ  ความจำที่เก็บไว้ M ก้อน (สถานการณ์ในอดีต)
    x    สถานการณ์ตอนนี้
    β    ความคมของการดึงคืน
    E    พลังงาน — ยิ่งต่ำยิ่งแปลว่า "เคยเจอเรื่องแบบนี้มาแล้ว"

การไล่ลงตามความชันของพลังงานนี้ **หนึ่งก้าว** ให้สูตร

    x' = Ξ · softmax(β · Ξᵀ x)

ซึ่งคือ attention ของ transformer เป๊ะๆ (ξ เป็น key/value · x เป็น query)
ที่มา: Ramsauer et al. 2020 "Hopfield Networks is All You Need"

สิ่งที่ต้องเข้าใจให้ตรงก่อนใช้
=============================
**นี่ไม่ใช่ของที่มาแทนโมเดลภาษา มันคือแกนกลางหนึ่งชั้นของโมเดลภาษา** ที่ถอดออกมา
โดยไม่มีน้ำหนักที่เรียนมา ไม่มี MLP ไม่มีความลึก เอาไปเขียนเรื่องเล่าไม่ได้
สิ่งที่มันทำได้คือ **ดึงคืน** — ถามว่า "ครั้งก่อนที่เจอเรื่องคล้ายกันนี้ ข้าทำอะไร"

ซึ่งพอดีกับเป้าหมายของโลกนี้: ตัวละครควรตัดสินใจจากประสบการณ์ของตัวเอง ไม่ใช่จาก
น้ำหนักที่ผู้เขียนโค้ดตั้งไว้ ความจำของแต่ละคนคือประวัติของคนคนนั้นจริงๆ จึงเกิด
"ตัวนี้เป็นแบบนี้ ตัดสินใจแบบนี้" ขึ้นเองโดยไม่ต้องเขียนบุคลิกเป็นกฎ

ข้อจำกัดที่ต้องรู้: **มันดึงคืน ไม่ได้สร้าง** ตัวละครจะไม่ทำสิ่งที่ไม่มีอยู่ในความจำ
จึงต้องมีโมเดลภาษาไว้สำหรับจังหวะที่ความจำตอบไม่ได้ (ดู Recall.energy ข้างล่าง)

β คือนิสัย ไม่ใช่ไฮเปอร์พารามิเตอร์
==================================
β สูง  softmax คมจนเหลือความจำเดียว = "คนนี้ทำอย่างเดิมเสมอ" เด็ดขาด ดื้อ
β ต่ำ  softmax แบนจนเฉลี่ยความจำหลายก้อน = ใจรวน ลังเล ทำอะไรก็ได้
ตรงกลาง เกิดสิ่งที่ทฤษฎีเรียกว่า metastable state = ค่าเฉลี่ยของความจำที่คล้ายกัน
        ซึ่งอ่านเป็นภาษาคนได้ว่า "ความเคยชิน" หรือ "วิธีที่คนแบบเขามักทำ"
นี่ไม่ใช่การเปรียบเทียบเชิงกวี มันเป็นคุณสมบัติของสมการตรงๆ

พลังงานคือสวิตช์
================
ประโยชน์ที่ไม่ได้อยู่ในการดึงคืน แต่อยู่ใน **E เอง**: เมื่อ ‖x‖ = ‖ξ‖ = 1
    ξᵀx = โคไซน์ความคล้าย ∈ [-1, 1]
    E(x) ≈ -max_μ(ξ_μᵀx) - log(M)/β + ½
E ต่ำ = มีความจำที่ใกล้เคียง → ตอบเองได้ ไม่ต้องเรียกโมเดล
E สูง = **ไม่เคยเจอเรื่องแบบนี้** → นี่คือจังหวะที่ควรจ่ายค่าเรียกโมเดลจริง
สมการที่ได้มาจึงให้ทั้งคำตอบและเกณฑ์ว่าเมื่อไรคำตอบของมันเชื่อไม่ได้ ในก้อนเดียวกัน
"""
import math
import statistics as _st

from . import config as C


def normalize(vec):
    """ทำให้ ‖x‖ = 1 — จำเป็น ไม่ใช่ทางเลือก

    เพราะ ξᵀx จะเป็นโคไซน์ความคล้ายก็ต่อเมื่อทั้งสองเป็นเวกเตอร์หนึ่งหน่วย ถ้าไม่ทำ
    ความจำที่มีขนาดใหญ่กว่าจะชนะทุกครั้งโดยไม่เกี่ยวกับว่าคล้ายกันจริงหรือไม่ และ β
    จะไม่มีความหมายที่ตีความได้ (พจน์ ½‖x‖² ในสมการก็กลายเป็นค่าคงที่พอดีด้วย)
    """
    n = math.sqrt(sum(v * v for v in vec))
    if n <= 1e-12:
        return [0.0] * len(vec)
    return [v / n for v in vec]


def dot(a, b):
    return sum(p * q for p, q in zip(a, b))


class Recall:
    """ผลการดึงคืนหนึ่งครั้ง"""

    __slots__ = ("kind", "energy", "confidence", "share", "best_sim", "n_memories")

    def __init__(self, kind, energy, confidence, share, best_sim, n_memories):
        self.kind = kind                # การกระทำที่ดึงคืนได้ (None = ความจำว่าง)
        self.energy = energy            # E(x) — ต่ำ = เคยเจอเรื่องแบบนี้
        self.confidence = confidence    # ส่วนแบ่งของตัวที่ชนะ หักส่วนแบ่งของอันดับสอง
        self.share = share              # {การกระทำ: ส่วนแบ่ง} ทั้งหมด
        self.best_sim = best_sim        # โคไซน์ความคล้ายของความจำที่ใกล้สุด
        self.n_memories = n_memories

    def __repr__(self):
        return (f"Recall({self.kind!r} E={self.energy:.3f} "
                f"conf={self.confidence:.2f} sim={self.best_sim:.2f} M={self.n_memories})")


class Memory:
    """คลังความจำเชิงเชื่อมโยงของตัวละครหนึ่งคน

    เก็บเป็นลิสต์ธรรมดาเพราะ M ถูกจำกัดไว้ที่หลักร้อย การคูณ M×d ด้วย Python ล้วนใช้
    เวลาระดับมิลลิวินาที ซึ่งเทียบกับการเรียกโมเดลที่วัดได้ 7.2 วินาทีต่อครั้งแล้วถือว่าฟรี
    จงใจไม่ใช้ numpy เพื่อไม่เพิ่มของที่ต้องติดตั้งให้เอนจิน (เหมือนที่ noise.py ทำ)
    """

    __slots__ = ("beta", "cap", "keys", "labels", "days", "weights")

    def __init__(self, beta=None, cap=None):
        self.beta = float(C.HOPFIELD_BETA if beta is None else beta)
        self.cap = int(C.HOPFIELD_CAP if cap is None else cap)
        self.keys = []      # ξ_μ (เวกเตอร์หนึ่งหน่วย)
        self.labels = []    # การกระทำที่เลือกตอนนั้น
        self.days = []      # วันที่เกิด — ใช้ลืมของเก่าและถ่วงน้ำหนักตามความสดใหม่
        self.weights = []   # น้ำหนักของความจำ (ครั้งที่ประทับใจได้มากกว่า)

    def __len__(self):
        return len(self.keys)

    def store(self, vec, label, day=0, weight=1.0):
        """ประทับความจำหนึ่งก้อน — ถ้าเหมือนของเดิมมากก็รวมกันแทนที่จะเก็บซ้ำ

        การรวมซ้ำสำคัญ ไม่ใช่การประหยัดที่นั่ง: ถ้าปล่อยให้เก็บซ้ำได้ การกระทำที่ทำบ่อย
        (เดินทาง ฝึกวิชา) จะยึดคลังไว้ทั้งหมด แล้วกลบเหตุการณ์ที่เกิดครั้งเดียวแต่สำคัญ
        (ถูกหักหลัง เสียอาจารย์) ซึ่งเป็นความจำที่กำหนดนิสัยคนจริงๆ
        """
        x = normalize(vec)
        if not any(x):
            return
        for i, k in enumerate(self.keys):
            if self.labels[i] == label and dot(k, x) >= C.HOPFIELD_MERGE_SIM:
                w = self.weights[i] + weight
                self.keys[i] = normalize([(a * self.weights[i] + b * weight) / w
                                          for a, b in zip(k, x)])
                self.weights[i] = w
                self.days[i] = max(self.days[i], day)
                return
        self.keys.append(x)
        self.labels.append(label)
        self.days.append(day)
        self.weights.append(float(weight))
        if len(self.keys) > self.cap:
            # ลืมก้อนที่ทั้งเก่าและถูกทวนซ้ำน้อยที่สุด — ไม่ใช่เก่าที่สุดเฉยๆ
            # ความจำที่เก่าแต่ถูกย้ำหลายครั้งคือสิ่งที่คนจำได้ไปตลอดชีวิต
            worst = min(range(len(self.keys)),
                        key=lambda i: (self.weights[i], self.days[i]))
            for arr in (self.keys, self.labels, self.days, self.weights):
                del arr[worst]

    def similarities(self, vec):
        x = normalize(vec)
        return x, [dot(k, x) for k in self.keys]

    @staticmethod
    def sigma(sims):
        """ความกว้างของการกระจายความคล้าย — ใช้ปรับสเกลของ β

        ทำไมต้องมี: เวกเตอร์สถานการณ์ของโลกนี้เป็นบวกทุกช่อง (0..1) โคไซน์ระหว่างสอง
        สถานการณ์จึงไม่เคยลงมาใกล้ศูนย์เลย วัดจริงจากความจำ 33 ก้อนของตัวละครหนึ่งคน:
        ความคล้ายกระจุกอยู่ในช่วง 0.577-0.893 กว้างแค่ 0.31 ทั้งที่ช่วงที่โคไซน์ทำได้
        คือ -1..1  ผลคือ exp(β·s) ที่ β = 6.5 ให้ความจำอันดับหนึ่งหนักกว่าอันดับเจ็ด
        เพียง 2 เท่า ส่วนแบ่งจึงถูกหารกระจายไป 14 ทาง ความมั่นใจเหลือ 0.11
        (วัดในรัน: ความมั่นใจ 167 จาก 193 ครั้งอยู่ใต้ 0.2 — ดึงคืนได้ 3 จาก 344)

        หารด้วยส่วนเบี่ยงเบนมาตรฐานของความคล้ายเอง ทำให้ β วัดเป็น "กี่ส่วนเบี่ยงเบน
        มาตรฐานของความต่าง" ซึ่งไม่ขึ้นกับสเกลของตัวเข้ารหัสอีกต่อไป — β จึงกลับมามี
        ความหมายตามที่ตั้งใจไว้จริงๆ คือ "คนนี้เด็ดขาดแค่ไหน" ไม่ใช่ตัวเลขที่ต้องจูนใหม่
        ทุกครั้งที่แก้ตัวเข้ารหัส  นี่คือเหตุผลเดียวกับที่ attention หารด้วย √d_k
        σ = 1 คืนเป็นสูตรตามตัวอักษรเป๊ะ (ใช้ในเทสต์)
        """
        if len(sims) < 2:
            return 1.0
        return max(C.HOPFIELD_SIGMA_FLOOR, _st.pstdev(sims))

    def energy(self, vec, beta=None, scaled=True):
        """E(x) = -1/β·log Σ exp(β·ξᵀx) + ½‖x‖²  — เขียนตรงตามสูตร

        ใช้ logsumexp แบบหักค่าสูงสุดออกก่อน เพราะ exp(β·s) ที่ β สูงจะล้นทันที
        (β=32, s=1 ให้ e³² ซึ่งยังไหว แต่ β ที่สูงกว่านั้นไม่ไหว) — การหักค่าสูงสุด
        ให้ผลเท่ากันทางพีชคณิตพอดี ไม่ใช่การประมาณ
        """
        b = float(self.beta if beta is None else beta)
        x, sims = self.similarities(vec)
        if scaled:
            b /= self.sigma(sims)
        half_sq = 0.5 * dot(x, x)
        if not sims:
            # ความจำว่าง — Σ ว่างเปล่า พลังงานเป็นอนันต์ตามนิยาม ใช้ค่าสูงแทนเพื่อให้
            # ผู้เรียกเทียบกับเกณฑ์ได้โดยไม่ต้องเช็ค None
            return C.HOPFIELD_EMPTY_ENERGY
        top = max(sims)
        acc = sum(math.exp(b * (s - top)) for s in sims)
        lse = top + math.log(acc) / b
        return -lse + half_sq

    def recall(self, vec, beta=None, allowed=None, scaled=True):
        """ดึงคืนการกระทำจากความจำ — softmax ถ่วงน้ำหนักแล้วรวมคะแนนตามการกระทำ

        รวมคะแนนตามการกระทำ (ไม่ใช่หยิบความจำที่คล้ายที่สุดก้อนเดียว) เพราะนั่นคือ
        พฤติกรรมที่สมการบอกจริงๆ — x' = Ξ·softmax(βΞᵀx) เป็น **ผลรวมถ่วงน้ำหนัก**
        ของทุกความจำ ไม่ใช่การเลือกก้อนเดียว และที่ β ปานกลางผลรวมนั้นคือ metastable
        state ที่เป็น "ความเคยชิน" ซึ่งเป็นสิ่งที่เราอยากได้

        `allowed` = เมนูที่ทำได้จริงตอนนี้ ความจำที่ชี้ไปยังการกระทำที่ทำไม่ได้ถูกคัดออก
        ก่อนทำ softmax ไม่ใช่หลัง — ไม่งั้นส่วนแบ่งจะถูกดูดไปโดยตัวเลือกที่เลือกไม่ได้
        แล้วความมั่นใจที่รายงานออกมาจะต่ำกว่าความจริง
        """
        b = float(self.beta if beta is None else beta)
        x, sims = self.similarities(vec)
        if scaled:
            b /= self.sigma(sims)
        idx = range(len(sims))
        if allowed is not None:
            ok = set(allowed)
            idx = [i for i in idx if self.labels[i] in ok]
        if not idx:
            return Recall(None, C.HOPFIELD_EMPTY_ENERGY, 0.0, {}, -1.0, len(self.keys))
        top = max(sims[i] for i in idx)
        share = {}
        total = 0.0
        for i in idx:
            # ถ่วงด้วยน้ำหนักของความจำ (ความจำที่ถูกย้ำบ่อยมีเสียงดังกว่า)
            p = math.exp(b * (sims[i] - top)) * self.weights[i]
            share[self.labels[i]] = share.get(self.labels[i], 0.0) + p
            total += p
        if total <= 0:
            return Recall(None, C.HOPFIELD_EMPTY_ENERGY, 0.0, {}, top, len(self.keys))
        for k in share:
            share[k] /= total
        order = sorted(share, key=lambda k: (-share[k], k))
        best = order[0]
        second = share[order[1]] if len(order) > 1 else 0.0
        e = -(top + math.log(sum(math.exp(b * (sims[i] - top)) for i in idx)) / b) \
            + 0.5 * dot(x, x)
        return Recall(best, e, share[best] - second, share, top, len(self.keys))

    def retrieve_state(self, vec, beta=None):
        """x' = Ξ·softmax(βΞᵀx) — ก้าวเดียวของการไล่ลงตามความชันของ E

        ไม่ได้ใช้ในการตัดสินใจ (ที่นั่นเราต้องการฉลากไม่ใช่เวกเตอร์) แต่เก็บไว้เพราะมันคือ
        สมการต้นฉบับ และใช้ตรวจได้ว่าการดึงคืนลู่เข้าหาความจำที่เก็บไว้จริง (ดูเทสต์)
        """
        b = float(self.beta if beta is None else beta)
        x, sims = self.similarities(vec)
        if not sims:
            return list(x)
        top = max(sims)
        ws = [math.exp(b * (s - top)) for s in sims]
        tot = sum(ws) or 1.0
        d = len(x)
        out = [0.0] * d
        for w, k in zip(ws, self.keys):
            for j in range(d):
                out[j] += w * k[j] / tot
        return out
