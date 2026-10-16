from __future__ import annotations

from typing import Optional, List, Literal, Dict

from pydantic import BaseModel, ConfigDict, field_validator


# ── Transport Protocol ──

TransportProtocol = Literal["http", "connect"]

# ── Health ──


class HealthResponse(BaseModel):
    status: str


class VersionResponse(BaseModel):
    version: str


# ── Documents ──

DocumentStatus = Literal["pending", "parsing", "summarizing", "ready", "failed"]


class Document(BaseModel):
    id: str
    title: str
    content_type: str
    status: str  # DocumentStatus
    byte_size: int
    error_message: str = ""
    metadata: Dict[str, str] = {}
    created_at: str
    updated_at: str


class IngestDocumentResponse(BaseModel):
    document_id: str
    status: str  # DocumentStatus


class ListDocumentsResponse(BaseModel):
    items: List[Document]
    next_cursor: Optional[str] = None


# ── Document Tree ──


class SectionView(BaseModel):
    id: str
    parent_id: str = ""
    depth: int
    title: str
    summary: str = ""
    children: List[str] = []
    tokens: int


class DocumentTree(BaseModel):
    document_id: str
    title: str
    sections: List[SectionView]


# ── Sections ──


class Section(BaseModel):
    id: str
    document_id: str
    parent_id: str = ""
    ordinal: int
    depth: int
    title: str
    summary: str = ""
    token_count: int
    metadata: Dict[str, str] = {}
    content: str


# ── Query ──


class QuerySection(BaseModel):
    id: str
    parent_id: str = ""
    title: str
    summary: str = ""
    token_count: int = 0
    content: str
    # Set when the unit is a page a page-based strategy found, not a
    # section of the tree (id "page_<n>").
    page: Optional[int] = None
    confidence: Optional[float] = None


class Usage(BaseModel):
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost_usd: float
    llm_calls: int


class TimingWait(BaseModel):
    """One thing a request waited on (the Judge, the answer model, the
    database or document storage)."""

    calls: int = 0
    attempts: int = 0
    failed: int = 0
    # Wall-clock time at least one call was outstanding.
    wait_ms: float = 0.0
    # Sum of call durations; above wait_ms when calls overlapped.
    busy_ms: float = 0.0
    # Time from going on the wire to the first response byte (sum and max):
    # the provider's own latency.
    first_byte_ms: float = 0.0
    first_byte_max_ms: float = 0.0
    # Time calls spent in the engine before going on the wire.
    local_ms: float = 0.0


class Timing(BaseModel):
    """Where a request's time went, as the engine measured it.
    engine_ms + waiting_ms == total_ms; waiting_ms is the union of the waits."""

    # Required: a timing object without its totals is a malformed
    # measurement, not a zero-length request.
    total_ms: float
    engine_ms: float
    waiting_ms: float
    judge: TimingWait = TimingWait()
    answer_model: TimingWait = TimingWait()
    db: TimingWait = TimingWait()
    storage: TimingWait = TimingWait()


class QueryResponse(BaseModel):
    document_id: str
    query: str
    # An abstained or Judge-navigated response may carry no model name;
    # an empty string is a valid answer, not a malformed one.
    strategy: str = ""
    model: str = ""
    sections: List[QuerySection] = []
    elapsed_ms: int = 0
    usage: Optional[Usage] = None
    abstained: bool = False
    abstain_reason: str = ""
    # Page ranges the answer rests on, from page-based strategies.
    cited_pages: List[List[int]] = []
    # The engine's split of this request's time (engine >= 2026-10-16).
    timing: Optional[Timing] = None


# ── TreeWalk answer (page-based agentic strategy) ──


class TreeWalkCitation(BaseModel):
    """A page-range citation backing a treewalk answer."""

    start_page: int = 0
    end_page: int = 0
    quote: str = ""
    section_ids: List[str] = []


class TreeWalkAnswer(BaseModel):
    """Response from POST /v1/answer/treewalk — the agent's natural-language
    answer plus page-grounded citations, in one round-trip."""

    document_id: str
    query: str
    answer: str
    citations: List[TreeWalkCitation] = []
    strategy: str = ""
    model: str = ""
    confidence: float = 0.0
    hops_taken: int = 0
    elapsed_ms: int = 0
    trace_token: str = ""
    usage: Optional[Usage] = None
    timing: Optional[Timing] = None


# ── Corpus mode: one question over a whole collection ──


class CorpusEvidence(BaseModel):
    """One page of the merged evidence, from whichever document holds it."""

    document_id: str
    document_title: str = ""
    page: int = 0
    section_title: str = ""
    text: str = ""
    # The Judge's probability that this page states a fact the question needs.
    confidence: float = 0.0
    # The hop that found it: 1 is the first read, 2+ are bridge hops.
    hop: int = 1


class CorpusDocumentScore(BaseModel):
    """A document's routing score: the probability that it holds part of
    what the question needs."""

    document_id: str
    title: str = ""
    score: float = 0.0
    hop: int = 1
    read: bool = False


class CorpusHop(BaseModel):
    """One round of route, read, merge and coverage."""

    hop: int
    routed: int = 0
    read: List[str] = []
    new_evidence: int = 0
    # Probability, after this hop, that the evidence states every fact needed.
    coverage: float = 0.0

    @field_validator("read", mode="before")
    @classmethod
    def _null_is_empty(cls, v):
        return [] if v is None else v


class CorpusQueryResponse(BaseModel):
    """Response from POST /v1/query/corpus."""

    query: str
    strategy: str = "corpus"
    evidence: List[CorpusEvidence] = []
    # The best-routed documents (at most 25), best first.
    documents: List[CorpusDocumentScore] = []
    documents_considered: int = 0
    hops: List[CorpusHop] = []
    # Final probability that the evidence answers the question.
    coverage: float = 0.0
    # Whether the collection appears to answer the question at all (engine
    # threshold on coverage), and whether the engine therefore returned no
    # evidence (abstain, the default).
    answerable: bool = True
    abstained: bool = False
    abstain_reason: str = ""
    # Documents that could not be read, by ID.
    errors: Optional[Dict[str, str]] = None
    judge_requests: int = 0
    usage: Optional[Usage] = None
    elapsed_ms: int = 0
    timing: Optional[Timing] = None

    @field_validator("evidence", "documents", "hops", mode="before")
    @classmethod
    def _null_is_empty(cls, v):
        # Engines before 2026-10-16 encoded an empty list as null.
        return [] if v is None else v


class CorpusCitation(BaseModel):
    """A citation of a corpus answer: one evidence page of one document."""

    model_config = ConfigDict(extra="allow")  # pincite regions ride along when present

    index: int
    document_id: str
    document_title: str = ""
    section_title: str = ""
    section_ids: List[str] = []
    start_page: int = 0
    end_page: int = 0
    quote: str = ""


class CorpusAnswer(CorpusQueryResponse):
    """Response from POST /v1/answer/corpus: the evidence of query_corpus,
    then one answer citing document and page."""

    # Required: a 2xx answer response without an answer is malformed, not
    # an empty answer (an explicitly empty string still parses).
    answer: str
    citations: List[CorpusCitation] = []
    # Retrieval's share of usage; usage covers retrieval and the answer.
    retrieval_usage: Optional[Usage] = None


# ── Streaming Query ──

QueryStreamEventType = Literal[
    "started",
    "slice_started",
    "section_selected",
    "slice_completed",
    "completed",
    "error",
]


class QueryStreamEvent(BaseModel):
    type: str  # QueryStreamEventType
    section: Optional[QuerySection] = None
    slice_index: Optional[int] = None
    total_slices: Optional[int] = None
    message: Optional[str] = None
    strategy: Optional[str] = None
    document_id: Optional[str] = None
    query: Optional[str] = None
    elapsed_ms: Optional[int] = None
    # Set on the completed event.
    timing: Optional[Timing] = None
