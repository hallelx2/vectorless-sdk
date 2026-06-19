from __future__ import annotations

from typing import Optional, List, Literal, Dict

from pydantic import BaseModel


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
    token_count: int
    content: str


class Usage(BaseModel):
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost_usd: float
    llm_calls: int


class QueryResponse(BaseModel):
    document_id: str
    query: str
    strategy: str
    model: str
    sections: List[QuerySection]
    elapsed_ms: int
    usage: Optional[Usage] = None


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
