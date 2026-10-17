"""Lenient reply parser used by the exploratory W2 re-score (deviation D3)."""
import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "w2_rescore_lenient", Path(__file__).resolve().parents[1] / "scripts" / "w2_rescore_lenient.py")
m = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(m)


def test_prose_before_json_takes_last_object():
    c = 'Total is 25400 / 16200 = 1.57.\n\n{"answer":"1.57","evidence_ids":["e1"],"brief":"ok"}'
    assert m.lenient_payload(c) == {"answer": "1.57", "evidence_ids": ["e1"], "brief": "ok"}


def test_extra_fields_ignored_and_last_object_wins():
    c = '{"answer":"no","evidence_ids":[],"brief":"x"} then {"answer":"yes","evidence_ids":["a"],"brief":"y","confidence":0.9}'
    assert m.lenient_payload(c) == {"answer": "yes", "evidence_ids": ["a"], "brief": "y"}


def test_null_string_is_abstain_and_missing_evidence_ids_ok_on_abstain():
    assert m.lenient_payload('{"answer":"null","brief":"no data"}') == {"answer": None, "evidence_ids": [], "brief": "no data"}
    assert m.lenient_payload('{"answer":null,"brief":""}')["answer"] is None


def test_missing_evidence_ids_on_a_real_answer_is_not_recovered():
    assert m.lenient_payload('{"answer":"yes","brief":"b"}')["evidence_ids"] is None


def test_unrecoverable_replies():
    assert m.lenient_payload("no json here") is None
    assert m.lenient_payload('{"answer": 3, "evidence_ids": [], "brief": ""}') is None
    assert m.lenient_payload('{"answer": "yes", "evidence_ids": [], "brief": "cut') is None


def test_braces_in_prose_do_not_break_scan():
    c = 'use {x} here {"answer":"maybe","evidence_ids":[],"brief":"b"}'
    assert m.lenient_payload(c)["answer"] == "maybe"
