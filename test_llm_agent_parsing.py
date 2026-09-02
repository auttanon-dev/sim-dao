# -*- coding: utf-8 -*-
"""Verification test for tiandao.ai.llm_agent._parse_response's tolerance of malformed JSON from
Ollama. All four failure shapes here were captured verbatim (structure-wise) from a real 3000-event
--llm dry run before the repair logic existed -- every one of them used to silently poison the
training data (dialogue="" , thought=<raw broken JSON text>). No network/Ollama needed -- pure
offline unit test of the parsing function."""
import sys
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

sys.path.insert(0, str(Path(__file__).resolve().parent))

from tiandao.ai.llm_agent import _parse_response


def test_valid_json_passthrough():
    r = _parse_response('{"dialogue": "สวัสดี", "thought": "ดีใจ"}')
    assert r == {"dialogue": "สวัสดี", "thought": "ดีใจ"}
    print("  ✓ JSON ปกติผ่านตรงๆ ไม่พัง")


def test_trailing_comma_repaired():
    r = _parse_response('{"dialogue": "ไปเถอะ", "thought": "กลัวจัง",}')
    assert r == {"dialogue": "ไปเถอะ", "thought": "กลัวจัง"}
    print("  ✓ comma ห้อยท้ายก่อนปิดวงเล็บ ซ่อมได้เงียบๆ")


def test_extra_brace_recovered_via_regex():
    r = _parse_response('{"dialogue": "ยังไม่ถึงเวลาที่ควรข้ามฟ้า"}, "thought": "ยังต้องรักษาตัว"')
    assert r["dialogue"] == "ยังไม่ถึงเวลาที่ควรข้ามฟ้า"
    assert r["thought"] == "ยังต้องรักษาตัว"
    print("  ✓ วงเล็บปิดเกินกลางประโยค กู้ทั้งสอง field ได้ด้วย regex")


def test_truncated_missing_close_brace_recovered():
    r = _parse_response('{"dialogue": "ฉันจะไม่ยอมแพ้!", "thought": "ฉันจะยังคงต่อสู้"')
    assert r["dialogue"] == "ฉันจะไม่ยอมแพ้!"
    assert r["thought"] == "ฉันจะยังคงต่อสู้"
    print("  ✓ ถูกตัดขาดกลางคัน (ไม่มีวงเล็บปิด) กู้ทั้งสอง field ได้ด้วย regex")


def test_totally_unrecoverable_returns_empty_not_garbage():
    r = _parse_response("นี่ไม่ใช่ JSON เลยสักนิด")
    assert r == {"dialogue": "", "thought": ""}, "ต้องคืนค่าว่าง ห้ามคืนข้อความดิบเป็น thought เด็ดขาด"
    print("  ✓ กู้ไม่ได้เลยจริงๆ คืนค่าว่างสองช่อง ไม่ใช่ข้อความดิบที่จะไปปนเปื้อน dataset")


def test_code_fence_stripped_before_parsing():
    r = _parse_response('```json\n{"dialogue": "ok", "thought": "ok2"}\n```')
    assert r == {"dialogue": "ok", "thought": "ok2"}
    print("  ✓ markdown code fence ถูกตัดออกก่อน parse")


def test_think_block_stripped():
    """โมเดลสาย reasoning (Qwen3: typhoon2.5-4b, pathumma) พ่น <think>...</think> ออกมาก่อนคำตอบ
    ถ้าไม่ตัดทิ้ง เหตุผลภาษาอังกฤษจะไหลลง dataset ตรงๆ — เจอจริงตอนทดสอบ pathumma ครั้งแรก
    (ตอนนิยายที่ได้เป็นไทยแค่ 39% ที่เหลือเป็น chain-of-thought อังกฤษ)"""
    from tiandao.ai.llm_agent import _strip_think
    assert _strip_think("<think>Okay, let me think...</think>\nผลลัพธ์ไทย") == "ผลลัพธ์ไทย"
    assert _strip_think("<think>ยังไม่ปิดแท็ก ไหลยาวไปเรื่อยๆ") == ""
    assert _strip_think("ไม่มี think เลย") == "ไม่มี think เลย"
    print("  ✓ ตัด <think> ทิ้งได้ทั้งแบบปิดแท็กครบและแบบเปิดค้าง")


def test_think_block_stripped_before_json_parse():
    r = _parse_response('<think>reasoning in english</think>{"dialogue": "ก", "thought": "ข"}')
    assert r == {"dialogue": "ก", "thought": "ข"}
    print("  ✓ <think> ถูกตัดก่อน parse JSON ทำให้ยัง parse ผ่านปกติ")


def test_no_think_models_are_configured():
    """โมเดลที่เลือกใช้จริงทั้งสองตัวเป็นสาย Qwen3 ต้องอยู่ใน NO_THINK_MODELS ไม่งั้นจะเสียเวลา
    ไปกับ chain-of-thought ที่ไม่ได้ใช้ทุกครั้งที่เรียก"""
    from tiandao.ai import config_ai as ACFG
    assert ACFG.OLLAMA_MODEL in ACFG.NO_THINK_MODELS
    assert ACFG.OLLAMA_PROSE_MODEL in ACFG.NO_THINK_MODELS
    print("  ✓ โมเดล Layer 3 และ prose อยู่ใน NO_THINK_MODELS ครบ")


if __name__ == "__main__":
    print("=== ทดสอบความทนทานของ _parse_response ต่อ JSON ที่พังจริงจาก Ollama ===")
    test_valid_json_passthrough()
    test_trailing_comma_repaired()
    test_extra_brace_recovered_via_regex()
    test_truncated_missing_close_brace_recovered()
    test_totally_unrecoverable_returns_empty_not_garbage()
    test_code_fence_stripped_before_parsing()
    test_think_block_stripped()
    test_think_block_stripped_before_json_parse()
    test_no_think_models_are_configured()
    print("\n\U0001f389 LLM AGENT PARSING TESTS PASSED!")
