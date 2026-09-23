"""Local model selection for the autonomous novel writer."""
from dataclasses import dataclass, field
import os
import re

from tiandao.ai import config_ai as ACFG
from tiandao.ai.llm_agent import OllamaAgent, CompletionTruncated


def clean_gemma_response(content):
    # Some runtimes return Gemma's raw thought channel inside content.
    content = re.sub(r'<\|channel>thought.*?(?:<channel\|>|$)', '', content, flags=re.S)
    return content.replace('<|channel>final', '').replace('<channel|>', '').strip()


class LMStudioAgent(OllamaAgent):
    """Reuse the writer's text/JSON parsers with LM Studio chat completions."""
    def __init__(self, host, model, api_key=''):
        super().__init__(host.rstrip('/'), model, ACFG.SCENE_PASS_TIMEOUT)
        self.headers = {'Authorization': f'Bearer {api_key}'} if api_key else {}

    def _post_chat(self, system, user, timeout=None, num_ctx=None,
                   response_format=None, num_predict=None, model=None, temperature=None):
        import httpx
        payload = {
            'model': model or self.model,
            'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': user}],
            'stream': False,
            'temperature': ACFG.SCENE_PROSE_TEMPERATURE if temperature is None else temperature,
        }
        if num_predict is not None:
            payload['max_tokens'] = num_predict
        if response_format == 'json':
            # Both writer passes request an object (beats or lines); their prompts
            # specify the fields and the writer validates the returned structure.
            payload['response_format'] = {
                'type': 'json_schema',
                'json_schema': {'name': 'scene_response', 'schema': {'type': 'object'}},
            }
        # Context length is a model-load setting in LM Studio, not an Ollama option.
        try:
            response = httpx.post(f'{self.host}/chat/completions', json=payload,
                                  headers=self.headers, timeout=timeout or self.timeout)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(f'LM Studio ปฏิเสธคำขอ (HTTP {exc.response.status_code}) '
                               'ตรวจชื่อโมเดล สิทธิ์ API และ Context Length ใน LM Studio') from exc
        except httpx.HTTPError as exc:
            raise RuntimeError('ติดต่อ LM Studio ไม่สำเร็จหรือหมดเวลารอ เปิด Local Server แล้วกดเขียนต่อ') from exc
        try:
            choice = response.json()['choices'][0]
            if choice.get('finish_reason') == 'length':
                raise CompletionTruncated('LM Studio ตัดคำตอบเพราะเต็มขีดจำกัด token '
                                   'ลองปิด Enable Thinking และเพิ่ม Context Length แล้วกดเขียนต่อ')
            content = choice['message']['content']
            if not isinstance(content, str) or not content.strip():
                raise ValueError('empty content')
            content = clean_gemma_response(content)
            if not content:
                raise ValueError('empty final answer')
            return content
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise RuntimeError('LM Studio ไม่ส่งข้อความคำตอบที่ใช้เขียนนิยายได้') from exc


@dataclass(frozen=True)
class WriterBackend:
    provider: str = 'ollama'
    base_url: str = ACFG.OLLAMA_HOST
    prose_model: str = ACFG.OLLAMA_PROSE_MODEL
    structure_model: str = ACFG.OLLAMA_STRUCTURE_MODEL
    api_key: str = field(default='', repr=False)

    @classmethod
    def from_env(cls):
        provider = os.environ.get('TIANDAO_WRITER_PROVIDER', 'ollama').strip().lower()
        if provider not in ('ollama', 'lmstudio'):
            raise ValueError('TIANDAO_WRITER_PROVIDER ต้องเป็น ollama หรือ lmstudio')
        lm = provider == 'lmstudio'
        base = os.environ.get('TIANDAO_WRITER_BASE_URL',
                              'http://127.0.0.1:1234/v1' if lm else ACFG.OLLAMA_HOST).strip().rstrip('/')
        if lm and not base.endswith('/v1'):
            base += '/v1'
        prose = os.environ.get('TIANDAO_WRITER_MODEL',
                               'google/gemma-4-e4b' if lm else ACFG.OLLAMA_PROSE_MODEL).strip()
        structure = os.environ.get('TIANDAO_WRITER_STRUCTURE_MODEL',
                                   prose if lm else ACFG.OLLAMA_STRUCTURE_MODEL).strip()
        if not prose or not structure:
            raise ValueError('กรุณาระบุชื่อโมเดลเขียนนิยาย')
        return cls(provider, base, prose, structure, os.environ.get('TIANDAO_WRITER_API_KEY', ''))

    @property
    def label(self):
        return 'LM Studio' if self.provider == 'lmstudio' else 'Ollama'

    def public_status(self):
        return {'provider': self.provider, 'label': self.label,
                'prose_model': self.prose_model, 'structure_model': self.structure_model}

    def agent(self):
        if self.provider == 'lmstudio':
            return LMStudioAgent(self.base_url, self.prose_model, self.api_key)
        return OllamaAgent(host=self.base_url, model=self.prose_model, strict_completion=True)

    def readiness(self):
        """Return (ready, reason). Discovery never loads or replaces a model."""
        import httpx
        path = '/models' if self.provider == 'lmstudio' else '/api/tags'
        headers = {'Authorization': f'Bearer {self.api_key}'} if self.api_key else {}
        try:
            response = httpx.get(self.base_url + path, headers=headers, timeout=5)
            response.raise_for_status()
            data = response.json()
            if self.provider == 'lmstudio':
                installed = [m['id'] for m in data['data']]
            else:
                installed = [m['name'] for m in data['models']]
        except httpx.HTTPStatusError as exc:
            return False, f'{self.label} ตอบ HTTP {exc.response.status_code} — ตรวจการตั้งค่า API'
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            return False, f'รอ {self.label} — เปิด Local Server และโหลดโมเดลเขียนนิยาย'
        missing = [m for m in dict.fromkeys((self.prose_model, self.structure_model))
                   if m not in installed and not (self.provider == 'ollama' and m + ':latest' in installed)]
        if missing:
            return False, f'{self.label} ยังไม่พบโมเดล: ' + ', '.join(missing)
        return True, ''
