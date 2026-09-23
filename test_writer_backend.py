import os
import unittest
from unittest.mock import patch, Mock
from types import SimpleNamespace as NS

import httpx

from narrative_factory.writer_backend import LMStudioAgent, WriterBackend
from tiandao.ai.llm_agent import OllamaAgent, _strip_think
from tiandao.ai import config_ai as ACFG
from tiandao.ai.llm_agent import CompletionTruncated
from narrative_factory.writer import SceneWriter, check_beat


def response(data, status=200):
    return httpx.Response(status, json=data, request=httpx.Request('POST', 'http://localhost:1234/v1/chat/completions'))


class BackendTests(unittest.TestCase):
    def test_truncated_pass_retries_with_larger_bounded_budget(self):
        agent=Mock()
        agent.complete.side_effect=[CompletionTruncated('short'), 'เนื้อเรื่องจบแล้ว']
        script=NS(calls=0)
        self.assertEqual(SceneWriter(agent=agent)._prose('system','user',script,675), 'เนื้อเรื่องจบแล้ว')
        self.assertEqual([c.kwargs['num_predict'] for c in agent.complete.call_args_list], [1200,2400])
        agent.complete.reset_mock()
        agent.complete.side_effect=CompletionTruncated('short')
        with self.assertRaises(CompletionTruncated):
            SceneWriter(agent=agent)._prose('system','user',script,675)
        self.assertEqual([c.kwargs['num_predict'] for c in agent.complete.call_args_list], [1200,2400,4096])

    def test_pause_interrupts_truncation_retry(self):
        agent=Mock(); agent.complete.side_effect=CompletionTruncated('short')
        writer=SceneWriter(agent=agent, should_stop=lambda:agent.complete.call_count > 0)
        with self.assertRaises(InterruptedError): writer._prose('system','user',NS(calls=0),675)
        self.assertEqual(agent.complete.call_count,1)

    def test_english_planning_is_rejected_as_fiction(self):
        issues=check_beat(NS(target_chars=4500,real_days=set()), NS(weight=.15,wants_dialogue=False),
                          NS(prose='First I need to plan the scene carefully. '*40,lines=[]))
        self.assertTrue(any('ภาษาอังกฤษ' in i for i in issues))

    def test_prefilled_thought_channel_does_not_leak_into_novel(self):
        self.assertEqual(_strip_think('Planning in English.\n</think>\nแสงแดดส่องผ่านม่าน'), 'แสงแดดส่องผ่านม่าน')
        self.assertEqual(_strip_think('<think>Planning.</think>แสงแดดส่องผ่านม่าน'), 'แสงแดดส่องผ่านม่าน')
        self.assertEqual(_strip_think('<think>Still thinking'), '')
        self.assertEqual(_strip_think('ข้อความธรรมดา'), 'ข้อความธรรมดา')

    def test_ollama_writer_disables_thinking_and_rejects_truncation(self):
        agent = WriterBackend().agent()
        with patch('httpx.post', return_value=response({'message': {'content': 'ขาดกลางคำ'}, 'done_reason': 'length'})) as post:
            with self.assertRaisesRegex(RuntimeError, 'token'):
                agent.complete('system', 'user', num_predict=1200)
        self.assertIs(post.call_args.kwargs['json']['think'], False)
        with patch('httpx.post', return_value=response({'message': {'content': 'ข้อความจบแล้ว'}, 'done_reason': 'stop'})):
            self.assertEqual(agent.complete('system', 'user'), 'ข้อความจบแล้ว')

    def test_unrelated_ollama_models_keep_default_thinking_behavior(self):
        with patch('httpx.post', return_value=response({'message': {'content': 'ok'}})) as post:
            OllamaAgent(model='another-model').complete('system', 'user')
        self.assertNotIn('think', post.call_args.kwargs['json'])

    def test_lmstudio_profile_and_secret_are_not_exposed(self):
        with patch.dict(os.environ, {'TIANDAO_WRITER_PROVIDER': 'lmstudio',
                                     'TIANDAO_WRITER_BASE_URL': 'http://localhost:1234/',
                                     'TIANDAO_WRITER_MODEL': 'my-gemma',
                                     'TIANDAO_WRITER_API_KEY': 'private-key'}, clear=True):
            backend = WriterBackend.from_env()
        self.assertEqual(backend.base_url, 'http://localhost:1234/v1')
        self.assertEqual(backend.structure_model, 'my-gemma')
        self.assertNotIn('private-key', str(backend.public_status()) + repr(backend))

    def test_text_routes_model_and_budget_without_ollama_options(self):
        agent = LMStudioAgent('http://localhost:1234/v1', 'gemma', 'secret')
        result = response({'choices': [{'message': {'content': '<|channel>thoughtanalysis<channel|>แสงเช้าทอดลงบนลาน'},
                                        'finish_reason': 'stop'}]})
        with patch('httpx.post', return_value=result) as post:
            text = agent.complete('system', 'user', num_ctx=8192, num_predict=1200,
                                  model='prose-gemma', temperature=.85, timeout=60)
        self.assertEqual(text, 'แสงเช้าทอดลงบนลาน')
        self.assertEqual(post.call_args.args[0], 'http://localhost:1234/v1/chat/completions')
        payload = post.call_args.kwargs['json']
        self.assertEqual(payload['model'], 'prose-gemma')
        self.assertEqual(payload['max_tokens'], 1200)
        self.assertNotIn('options', payload)
        self.assertNotIn('response_format', payload)
        self.assertEqual(post.call_args.kwargs['headers']['Authorization'], 'Bearer secret')

    def test_json_pass_uses_schema_and_parses_fenced_response(self):
        result = response({'choices': [{'message': {'content': '```json\n{"lines": []}\n```'}}]})
        with patch('httpx.post', return_value=result) as post:
            data = LMStudioAgent('http://localhost:1234/v1', 'gemma').complete_json('system', 'user', model='structure')
        self.assertEqual(data, {'lines': []})
        self.assertEqual(post.call_args.kwargs['json']['response_format']['type'], 'json_schema')
        self.assertEqual(post.call_args.kwargs['json']['model'], 'structure')

    def test_truncated_empty_malformed_and_http_failures_are_not_prose(self):
        cases = [
            response({'choices': [{'message': {'content': 'unfinished'}, 'finish_reason': 'length'}]}),
            response({'choices': [{'message': {'content': None, 'reasoning_content': 'analysis'}}]}),
            response({'choices': [{'message': {'content': '<|channel>thoughtunfinished'}}]}),
            response({'choices': []}), response({'error': 'not loaded'}, 404),
        ]
        for result in cases:
            with self.subTest(result=result), patch('httpx.post', return_value=result):
                with self.assertRaises(RuntimeError):
                    LMStudioAgent('http://localhost:1234/v1', 'gemma').complete('system', 'user')
        with patch('httpx.post', side_effect=httpx.ReadTimeout('timeout')):
            with self.assertRaises(RuntimeError):
                LMStudioAgent('http://localhost:1234/v1', 'gemma').complete('system', 'user')

    def test_discovery_requires_the_configured_model(self):
        backend = WriterBackend('lmstudio', 'http://localhost:1234/v1', 'gemma', 'gemma')
        with patch('httpx.get', return_value=response({'data': [{'id': 'another-model'}]})):
            ready, reason = backend.readiness()
        self.assertFalse(ready)
        self.assertIn('gemma', reason)
        with patch('httpx.get', return_value=response({'data': [{'id': 'gemma'}]})):
            self.assertEqual(backend.readiness(), (True, ''))
        with patch('httpx.get', side_effect=httpx.ConnectError('refused')):
            self.assertFalse(backend.readiness()[0])

    def test_ollama_defaults_and_latest_alias_remain_supported(self):
        with patch.dict(os.environ, {}, clear=True):
            backend = WriterBackend.from_env()
        self.assertEqual(backend.provider, 'ollama')
        names = [m if ':' in m else m + ':latest' for m in (backend.prose_model, backend.structure_model)]
        with patch('httpx.get', return_value=response({'models': [{'name': m} for m in names]})) as get:
            self.assertTrue(backend.readiness()[0])
        self.assertTrue(get.call_args.args[0].endswith('/api/tags'))


if __name__ == '__main__':
    unittest.main()
