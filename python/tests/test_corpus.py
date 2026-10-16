"""Corpus-mode responses parse, and the client sends the right body
(engine corpus mode, HAL-3075)."""

import httpx
import pytest

from vectorless import CorpusAnswer, CorpusQueryResponse, VectorlessClient

# The shape vectorless-engine's /v1/query/corpus returns (pkg/retrieval.CorpusResult).
QUERY = {
    "query": "Which company did Acme partner with, and when was it founded?",
    "strategy": "corpus",
    "evidence": [
        {"document_id": "a", "document_title": "TechNews: Acme results", "page": 1, "section_title": "TechNews: Acme results",
         "text": "Acme partnered with Beta Corp.", "confidence": 0.95, "hop": 1},
        {"document_id": "c", "document_title": "Beta Corp profile", "page": 1, "text": "Beta Corp, founded 1999.",
         "confidence": 0.93, "hop": 2},
    ],
    "documents": [{"document_id": "a", "title": "TechNews: Acme results", "score": 0.9, "hop": 1, "read": True},
                  {"document_id": "d", "title": "Sports", "score": 0.05, "hop": 2, "read": False}],
    "documents_considered": 609,
    "hops": [{"hop": 1, "routed": 609, "read": ["a", "b"], "new_evidence": 2, "coverage": 0.2},
             {"hop": 2, "routed": 607, "read": ["c"], "new_evidence": 1, "coverage": 0.9}],
    "coverage": 0.9,
    "errors": None,
    "judge_requests": 14,
    "usage": {"input_tokens": 150000, "output_tokens": 0, "total_tokens": 150000, "cost_usd": 0.0063, "llm_calls": 14},
    "elapsed_ms": 4100,
    "timing": {"total_ms": 4100.0, "engine_ms": 90.0, "waiting_ms": 4010.0},
}


def test_query_corpus_response_parses():
    r = CorpusQueryResponse.model_validate(QUERY)
    assert r.coverage == 0.9 and r.documents_considered == 609
    assert [e.hop for e in r.evidence] == [1, 2]
    assert r.hops[1].read == ["c"] and r.documents[0].read
    assert r.timing is not None and r.timing.total_ms == 4100.0


def test_answer_corpus_keeps_pincite_fields():
    body = dict(QUERY, answer="Beta Corp [1], founded in 1999 [2].", citations=[
        {"index": 2, "document_id": "c", "start_page": 1, "end_page": 1, "quote": "founded 1999", "regions": [{"x": 1}]}],
        retrieval_usage=QUERY["usage"])
    a = CorpusAnswer.model_validate(body)
    assert a.answer.startswith("Beta Corp") and a.citations[0].document_id == "c"
    assert a.citations[0].model_extra["regions"] == [{"x": 1}]


def _client(handler):
    c = VectorlessClient(base_url="http://engine.test", api_key="k")
    c._transport._client = httpx.Client(base_url="http://engine.test", transport=httpx.MockTransport(handler))
    return c


def test_query_corpus_sends_only_what_was_set():
    seen = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["path"] = req.url.path
        seen["body"] = __import__("json").loads(req.content)
        return httpx.Response(200, json=QUERY)

    r = _client(handler).query_corpus("q?", document_ids=["a", "b"], max_hops=2)
    assert seen["path"] == "/v1/query/corpus"
    assert seen["body"] == {"query": "q?", "document_ids": ["a", "b"], "max_hops": 2}
    assert isinstance(r, CorpusQueryResponse)


def test_answer_corpus_hits_the_answer_route():
    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/v1/answer/corpus"
        return httpx.Response(200, json=dict(QUERY, answer="a", citations=[]))

    assert _client(handler).answer_corpus("q?").answer == "a"


def test_connect_transport_refuses_corpus_mode():
    c = VectorlessClient(base_url="http://engine.test", api_key="k", transport="connect")
    with pytest.raises(NotImplementedError):
        c.query_corpus("q?")


def test_null_lists_from_an_older_engine_parse_as_empty():
    r = CorpusQueryResponse.model_validate({"query": "q", "evidence": None, "documents": None, "hops": None})
    assert r.evidence == [] and r.documents == [] and r.hops == []


def test_a_hop_that_read_nothing_parses():
    r = CorpusQueryResponse.model_validate({"query": "q", "hops": [{"hop": 2, "routed": 600, "read": None}]})
    assert r.hops[0].read == []


def test_an_answer_response_without_an_answer_is_rejected():
    import pydantic

    with pytest.raises(pydantic.ValidationError):
        CorpusAnswer.model_validate(dict(QUERY))
    assert CorpusAnswer.model_validate(dict(QUERY, answer="")).answer == ""


def test_abstention_and_card_size_are_sent_and_read():
    seen = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["body"] = __import__("json").loads(req.content)
        return httpx.Response(200, json=dict(QUERY, evidence=[], answerable=False, abstained=True,
                                             abstain_reason="the collection does not appear to answer the question"))

    r = _client(handler).query_corpus("q?", abstain=False, card_chars=400)
    assert seen["body"] == {"query": "q?", "abstain": False, "card_chars": 400}
    assert r.abstained and not r.answerable and r.evidence == []
    assert CorpusQueryResponse.model_validate({"query": "q"}).answerable  # older engines: no field, no abstention
