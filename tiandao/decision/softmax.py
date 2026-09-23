# -*- coding: utf-8 -*-
"""Softmax Action Selection — Boltzmann distribution ของกลศาสตร์สถิติ

ถ้ามอง −U เป็น "พลังงาน" ของแต่ละสถานะ ความน่าจะเป็นที่ระบบอยู่ในสถานะนั้นที่อุณหภูมิ T คือ
การกระจายแบบ Boltzmann (P ∝ e^{−E/kT}) — ซึ่งก็คือ softmax ของ U/T นั่นเอง และเป็นการกระจาย
ที่มี entropy สูงสุดภายใต้ค่าเฉลี่ย utility ที่กำหนด (maximum-entropy / quantal response)

    P(a_i) = exp(U_i / T) / Σ_j exp(U_j / T)

T ต่ำ → เกือบ deterministic (เลือกตัวที่ดีที่สุดเกือบเสมอ) · T สูง → หลากหลาย
mode "deterministic" = argmax (ดีบัก) · "stochastic" = สุ่มตาม P ด้วย rng ที่ผู้เรียกส่งมา (มี seed)
ลบ max ก่อน exp เพื่อไม่ให้ overflow; ถ้า T ≤ 0 ถือว่า deterministic
"""
import math


def softmax(scores, temperature):
    if not scores:
        return []
    if temperature is None or temperature <= 0:
        m = max(scores)
        idx = [i for i, s in enumerate(scores) if s == m]
        return [1.0 / len(idx) if i in idx else 0.0 for i in range(len(scores))]
    m = max(scores)
    ex = [math.exp((s - m) / temperature) for s in scores]
    tot = sum(ex)
    return [e / tot for e in ex]


def argmax(scores):
    best, bi = None, 0
    for i, s in enumerate(scores):
        if best is None or s > best:
            best, bi = s, i
    return bi


def select(scores, temperature, mode="stochastic", rng=None):
    """คืน (index ที่เลือก, probabilities)"""
    probs = softmax(scores, temperature)
    if not probs:
        return None, probs
    if mode == "deterministic" or rng is None:
        return argmax(scores), probs
    r, acc = rng.random(), 0.0
    for i, p in enumerate(probs):
        acc += p
        if r < acc:
            return i, probs
    return len(probs) - 1, probs


def entropy(probs):
    return -sum(p * math.log(p) for p in probs if p > 0)
