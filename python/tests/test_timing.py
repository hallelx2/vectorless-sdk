"""The engine's timing split survives parsing (engine >= 2026-10-16)."""

from vectorless import QueryResponse, Timing
from vectorless.types import QueryStreamEvent, TreeWalkAnswer

# Captured from vectorless-engine #88 on 2026-10-16 (3M 2018 10-K).
QUERY = {
    "document_id": "doc_1", "query": "capex?", "strategy": "judgewalk", "model": "", "sections": [],
    "elapsed_ms": 703,
    "usage": {"input_tokens": 98575, "output_tokens": 4949, "total_tokens": 103524, "cost_usd": 0.00414015, "llm_calls": 5},
    "timing": {"total_ms": 706.87, "engine_ms": 3.4, "waiting_ms": 703.47,
               "judge": {"calls": 5, "attempts": 5, "wait_ms": 696.19, "busy_ms": 1162.32,
                         "first_byte_ms": 1157.87, "first_byte_max_ms": 366.48, "local_ms": 41.83},
               "answer_model": {"calls": 0, "wait_ms": 0, "busy_ms": 0},
               "db": {"calls": 3, "attempts": 3, "wait_ms": 2.73, "busy_ms": 2.73},
               "storage": {"calls": 30, "attempts": 30, "wait_ms": 4.55, "busy_ms": 4.56}},
}


def test_query_response_keeps_timing():
    r = QueryResponse.model_validate(QUERY)
    assert isinstance(r.timing, Timing)
    assert r.timing.judge.calls == 5
    assert (r.timing.total_ms, r.timing.engine_ms, r.timing.waiting_ms) == (706.87, 3.4, 703.47)
    assert r.timing.judge.wait_ms == 696.19 and r.timing.judge.local_ms == 41.83
    assert r.timing.answer_model.first_byte_ms == 0.0


def test_older_engines_still_parse():
    body = dict(QUERY)
    body.pop("timing")
    assert QueryResponse.model_validate(body).timing is None


def test_treewalk_and_stream_carry_timing():
    t = TreeWalkAnswer.model_validate({"document_id": "d", "query": "q", "answer": "a", "timing": QUERY["timing"]})
    assert t.timing is not None and t.timing.total_ms == 706.87
    e = QueryStreamEvent.model_validate({"type": "completed", "timing": QUERY["timing"]})
    assert e.timing is not None and e.timing.db.calls == 3


def test_timing_without_totals_is_rejected():
    import pydantic
    import pytest

    body = dict(QUERY, timing={})
    with pytest.raises(pydantic.ValidationError):
        QueryResponse.model_validate(body)
