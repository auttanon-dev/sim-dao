# -*- coding: utf-8 -*-
"""ตัวเชื่อมโมเดล — Ollama / LM Studio / mock

ไม่ถูก pickle ไปกับโลก (MindManager ตัดทิ้งตอนเซฟ) เพราะเป็นการเชื่อมต่อเครือข่าย ไม่ใช่สถานะของโลก
เปิดโลกใหม่แล้วค่อยต่อใหม่ตามค่าที่ตั้งตอนนั้น จะเปลี่ยนโมเดลกลางทางก็ได้โดยไม่ต้องแก้เซฟ
"""
import hashlib
import logging

from . import config as MC
from ..ai import config_ai as ACFG
from ..ai import llm_agent as LLM

logger = logging.getLogger(__name__)


class ThinkError(RuntimeError):
    pass


class OllamaThinker:
    provider = "ollama"

    def __init__(self, model="", story_model="", base_url=""):
        # ตัดสินใจ: ค่าที่ส่งมา > MC.OLLAMA_DECIDE_MODEL (cws-typhoon2-8b)
        # เล่าเรื่อง: ค่าที่ส่งมา > โมเดลที่ผู้ใช้ระบุ > config_ai.OLLAMA_MODEL (พฤติกรรมเดิมของงานเล่าเรื่อง)
        self.model = model or getattr(MC, "OLLAMA_DECIDE_MODEL", "") or ACFG.OLLAMA_MODEL
        self.story_model = story_model or model or ACFG.OLLAMA_MODEL
        self.base_url = (base_url or ACFG.OLLAMA_HOST).rstrip("/")
        self.agent = LLM.OllamaAgent(host=self.base_url, model=self.model, timeout=MC.DECIDE_TIMEOUT)

    def think_json(self, system, user):
        content = self.agent._post_chat(system, user, timeout=MC.DECIDE_TIMEOUT,
                                        num_ctx=MC.DECIDE_NUM_CTX, response_format="json",
                                        num_predict=MC.DECIDE_NUM_PREDICT,
                                        temperature=MC.DECIDE_TEMPERATURE)
        if content is None:
            raise ThinkError(f"ติดต่อ Ollama ไม่ได้ ({self.base_url}, โมเดล {self.model})")
        data = LLM.loads_lenient(content)
        if not isinstance(data, dict):
            raise ThinkError("โมเดลตอบ JSON ที่อ่านไม่ได้")
        return data

    def write(self, system, user):
        content = self.agent._post_chat(system, user, timeout=MC.STORY_TIMEOUT,
                                        num_ctx=MC.DECIDE_NUM_CTX, num_predict=MC.STORY_NUM_PREDICT,
                                        model=self.story_model, temperature=MC.STORY_TEMPERATURE)
        if content is None:
            raise ThinkError("ติดต่อ Ollama ไม่ได้ขณะแต่งเรื่อง")
        return LLM._strip_code_fence(content)

    def public(self):
        return {"provider": self.provider, "model": self.model, "story_model": self.story_model,
                "base_url": self.base_url}


class LMStudioThinker(OllamaThinker):
    provider = "lmstudio"

    def __init__(self, model="", story_model="", base_url="", api_key=""):
        self.model = model or "google/gemma-4-e4b"
        self.story_model = story_model or self.model
        self.base_url = (base_url or "http://127.0.0.1:1234/v1").rstrip("/")
        self.headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}

    def _chat(self, system, user, model, max_tokens, temperature, as_json, timeout):
        import httpx
        payload = {"model": model, "stream": False, "temperature": temperature, "max_tokens": max_tokens,
                   "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
        if as_json:
            payload["response_format"] = {"type": "json_schema", "json_schema": {
                "name": "decision", "schema": {"type": "object"}}}
        try:
            r = httpx.post(f"{self.base_url}/chat/completions", json=payload, headers=self.headers,
                           timeout=timeout)
            r.raise_for_status()
            choice = r.json()["choices"][0]
        except Exception as exc:     # httpx / KeyError / JSON
            raise ThinkError(f"ติดต่อ LM Studio ไม่ได้ ({self.base_url}, โมเดล {model})") from exc
        if choice.get("finish_reason") == "length":
            raise ThinkError("LM Studio ตัดคำตอบเพราะเต็มขีดจำกัด token (เพิ่ม Context Length)")
        content = choice.get("message", {}).get("content") or ""
        return LLM._strip_code_fence(content)

    def think_json(self, system, user):
        content = self._chat(system, user, self.model, MC.DECIDE_NUM_PREDICT, MC.DECIDE_TEMPERATURE,
                             True, MC.DECIDE_TIMEOUT)
        data = LLM.loads_lenient(content)
        if not isinstance(data, dict):
            raise ThinkError("โมเดลตอบ JSON ที่อ่านไม่ได้")
        return data

    def write(self, system, user):
        return self._chat(system, user, self.story_model, MC.STORY_NUM_PREDICT, MC.STORY_TEMPERATURE,
                          False, MC.STORY_TIMEOUT)


class MockThinker:
    """ไม่ใช้โมเดลจริง — ใช้ทดสอบระบบทั้งสายโดยไม่ต้องเปิด Ollama

    ตอบแบบมีเหตุผลพอประมาณจากข้อมูลในพรอมต์ (เลือกข้อต้นๆ ของเมนู หยิบคนแรกในรายการ) และคงที่
    ตามเนื้อหาพรอมต์ รันซ้ำได้ผลเดิม — ข้อความเป็นแม่แบบ ไม่ใช่ความคิดจริง
    """
    provider = "mock"
    model = "mock"
    story_model = "mock"
    base_url = ""

    def think_json(self, system, user):
        h = int(hashlib.sha1(user.encode("utf-8")).hexdigest(), 16)
        menu = []
        section = None
        for line in user.splitlines():
            if line.startswith("["):
                section = line
                continue
            if section == "[สิ่งที่ข้าทำได้ตอนนี้]" and line.startswith("- "):
                name = line[2:].split(":", 1)[0].strip()
                menu.append((name, "[ต้องระบุคนจากรายการ P]" in line))
        has_people = "- P1:" in user
        choices = [m for m in menu if has_people or not m[1]] or [("บำเพ็ญ", False)]
        pick = choices[h % min(len(choices), 4)]
        second = choices[(h // 7) % len(choices)]
        plan = [{"action": pick[0], "target": "P1" if pick[1] else "",
                 "place": "D1" if pick[0] == "เดินทาง" else "", "why": f"ตอนนี้{pick[0]}ดูเหมาะกับข้าที่สุด"}]
        if second != pick:
            plan.append({"action": second[0], "target": "P1" if second[1] else "",
                         "place": "D1" if second[0] == "เดินทาง" else "", "why": "ทำต่อหลังจากนั้น"})
        return {
            "thought": f"ข้าชั่งใจอยู่นาน สุดท้ายคิดว่าควร{pick[0]}ก่อน",
            "emotion": ["สงบ", "คาดหวัง", "ลังเล", "ทะเยอทะยาน"][h % 4],
            "short_goal": f"{pick[0]}ให้สำเร็จ",
            "long_goal": "มีชีวิตรอดและแข็งแกร่งขึ้นในโลกนี้" if '"long_goal": "เป้าหมาย' in user else "",
            "plan": plan,
            "feelings": [{"person": "P1", "feeling": "ยังอ่านใจเขาไม่ออก"}] if has_people and h % 3 == 0 else [],
        }

    def write(self, system, user):
        # เล่าจาก "ผลที่เกิดขึ้นจริง" ไม่ใช่บรรทัดสุดท้ายซึ่งเป็นคำสั่ง — ไม่งั้นตัวกรองการลอกคำสั่ง
        # (runner) จะทิ้งเรื่องของโหมดทดสอบไปด้วย
        fact = next((l for l in user.splitlines() if l.startswith("[ผลที่เกิดขึ้นจริง]")), "")
        who = next((l for l in user.splitlines() if l.startswith("[ตัวละครหลัก]")), "")
        return ("(เรื่องเล่าตัวอย่างจากโหมดทดสอบ) " + who[len("[ตัวละครหลัก]"):].strip()
                + " เผชิญเหตุการณ์นี้ด้วยใจนิ่ง " + fact[len("[ผลที่เกิดขึ้นจริง]"):].strip())

    def public(self):
        return {"provider": "mock", "model": "mock", "story_model": "mock", "base_url": ""}


def from_env(provider=None, model=None, story_model=None, base_url=None, api_key=None):
    provider = (provider or MC.PROVIDER or "ollama").lower()
    model = model if model is not None else MC.MODEL
    story_model = story_model if story_model is not None else MC.STORY_MODEL
    base_url = base_url if base_url is not None else MC.BASE_URL
    if provider == "mock":
        return MockThinker()
    if provider == "lmstudio":
        return LMStudioThinker(model, story_model, base_url, api_key if api_key is not None else MC.API_KEY)
    if provider == "ollama":
        return OllamaThinker(model, story_model, base_url)
    raise ValueError("TIANDAO_MIND_PROVIDER ต้องเป็น ollama, lmstudio หรือ mock")
