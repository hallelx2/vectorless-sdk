"""
Vectorless SDK — structure-preserving document retrieval without embeddings.

Usage::

    from vectorless import VectorlessClient

    # Self-hosted
    client = VectorlessClient(base_url="http://localhost:8080")

    # Deployed with API key
    client = VectorlessClient(
        base_url="https://api.vectorless.dev",
        api_key="vl_live_...",
    )

    # Ingest a document
    result = client.ingest_document("./report.pdf")
    doc = client.wait_for_ready(result.document_id)

    # Query
    response = client.query(doc.id, "How does authentication work?")
    for section in response.sections:
        print(section.title, section.content)
"""

from vectorless._version import __version__

# ── Clients ──
from vectorless.client import VectorlessClient
from vectorless.async_client import AsyncVectorlessClient

# ── Types ──
from vectorless.types import (
    HealthResponse,
    VersionResponse,
    Document,
    DocumentStatus,
    IngestDocumentResponse,
    ListDocumentsResponse,
    SectionView,
    DocumentTree,
    Section,
    QuerySection,
    Usage,
    QueryResponse,
    QueryStreamEvent,
    QueryStreamEventType,
)

# ── Errors ──
from vectorless.errors import (
    VectorlessError,
    AuthenticationError,
    PermissionDeniedError,
    NotFoundError,
    ValidationError,
    ConflictError,
    RateLimitError,
    TimeoutError,
    ServerError,
    DocumentFailedError,
    StreamError,
)

# ── Transport (advanced usage) ──
from vectorless.transport import (
    Transport,
    AsyncTransport,
    HttpTransport,
    AsyncHttpTransport,
    ConnectTransport,
    AsyncConnectTransport,
)

__all__ = [
    # Version
    "__version__",
    # Clients
    "VectorlessClient",
    "AsyncVectorlessClient",
    # Types
    "HealthResponse",
    "VersionResponse",
    "Document",
    "DocumentStatus",
    "IngestDocumentResponse",
    "ListDocumentsResponse",
    "SectionView",
    "DocumentTree",
    "Section",
    "QuerySection",
    "Usage",
    "QueryResponse",
    "QueryStreamEvent",
    "QueryStreamEventType",
    # Errors
    "VectorlessError",
    "AuthenticationError",
    "PermissionDeniedError",
    "NotFoundError",
    "ValidationError",
    "ConflictError",
    "RateLimitError",
    "TimeoutError",
    "ServerError",
    "DocumentFailedError",
    "StreamError",
    # Transport
    "Transport",
    "AsyncTransport",
    "HttpTransport",
    "AsyncHttpTransport",
    "ConnectTransport",
    "AsyncConnectTransport",
]
