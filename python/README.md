<h1 align="center">
  <code>vectorless-sdk</code>
</h1>

<p align="center">
  <strong>Official Python SDK for Vectorless — structure-preserving document retrieval.</strong>
</p>

<p align="center">
  <a href="https://pypi.org/project/vectorless-sdk/"><img src="https://img.shields.io/pypi/v/vectorless-sdk?style=flat-square&logo=python&logoColor=white&color=3776AB" alt="PyPI version" /></a>
  <a href="https://pypi.org/project/vectorless-sdk/"><img src="https://img.shields.io/pypi/dm/vectorless-sdk?style=flat-square&color=3776AB" alt="PyPI downloads" /></a>
  <a href="https://pypi.org/project/vectorless-sdk/"><img src="https://img.shields.io/pypi/pyversions/vectorless-sdk?style=flat-square&logo=python&logoColor=white" alt="Python versions" /></a>
  <img src="https://img.shields.io/badge/type_checked-mypy_strict-blue?style=flat-square" alt="mypy strict" />
  <a href="https://github.com/hallelx2/vectorless-sdk/actions"><img src="https://img.shields.io/github/actions/workflow/status/hallelx2/vectorless-sdk/ci.yml?style=flat-square&label=CI" alt="CI" /></a>
  <a href="LICENSE"><img src="https://img.shields.io/pypi/l/vectorless-sdk?style=flat-square&color=blue" alt="License" /></a>
</p>

---

## Install

```bash
pip install vectorless-sdk
```

## Quick Start

```python
from vectorless import VectorlessClient

# Deployed instance with API key
client = VectorlessClient(
    base_url="https://api.vectorless.dev",
    api_key="vl_live_...",
)

# Self-hosted, no auth needed
# client = VectorlessClient(base_url="http://localhost:8080")

# 1. Ingest a document
result = client.ingest_document(
    "./research-paper.pdf",
    filename="research-paper.pdf",
    metadata={"department": "engineering"},
)

# 2. Wait for processing (parsing → summarizing → ready)
doc = client.wait_for_ready(
    result.document_id,
    on_progress=lambda s: print(f"Status: {s}"),
)

# 3. Explore the document tree
tree = client.get_document_tree(doc.id)
for section in tree.sections:
    print("  " * section.depth + f"{section.title} ({section.tokens} tokens)")

# 4. Query — LLM navigates the tree to find relevant sections
response = client.query(doc.id, "What methodology was used?")
for section in response.sections:
    print(f"\n## {section.title}\n{section.content}")
print(f"Strategy: {response.strategy} | {response.elapsed_ms}ms")
```

## Async Support

Every method has an async counterpart:

```python
from vectorless import AsyncVectorlessClient

async with AsyncVectorlessClient(
    base_url="https://api.vectorless.dev",
    api_key="vl_live_...",
) as client:
    result = await client.ingest_document(b"# Hello\n\nWorld", filename="hello.md")
    doc = await client.wait_for_ready(result.document_id)

    # Concurrent section fetch
    sections = await client.get_sections(["sec_1", "sec_2", "sec_3"])
```

## Transport Protocols

Choose the wire protocol at init time:

```python
# HTTP/REST — default, uses httpx
client = VectorlessClient(transport="http")

# ConnectRPC — protobuf JSON encoding, native streaming
client = VectorlessClient(transport="connect")
```

```
┌────────────────────────────────────────────────┐
│   VectorlessClient / AsyncVectorlessClient     │
├────────────────────────────────────────────────┤
│            Transport Abstraction                │
│  ┌──────────────────┐ ┌─────────────────────┐ │
│  │  HttpTransport    │ │  ConnectTransport   │ │
│  │  AsyncHttpTransport│ │AsyncConnectTransport│ │
│  │  REST/JSON        │ │  ConnectRPC JSON    │ │
│  │  SSE streaming    │ │  Native streaming   │ │
│  │  httpx            │ │  httpx              │ │
│  └────────┬─────────┘ └──────────┬──────────┘ │
│           │                       │            │
│     vectorless-server       vectorless-server   │
└────────────────────────────────────────────────┘
```

## Streaming Queries

Watch retrieval progress in real-time:

```python
# Sync
for event in client.query_stream(doc_id, "Explain the results"):
    if event.type == "section_selected" and event.section:
        print(f"Found: {event.section.title}")
    if event.type == "completed":
        print(f"Done in {event.elapsed_ms}ms")

# Async
async for event in client.query_stream(doc_id, "Explain the results"):
    ...
```

## API Reference

### Client Configuration

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `base_url` | `str` | `"http://localhost:8080"` | Server URL |
| `api_key` | `str` | `env VECTORLESS_API_KEY` | Bearer token |
| `transport` | `"http" \| "connect"` | `"http"` | Wire protocol |
| `timeout` | `float` | `30.0` | Request timeout (seconds) |
| `max_retries` | `int` | `3` | Retry attempts |
| `retry_delay` | `float` | `0.5` | Base retry delay (seconds) |

### Methods

Both `VectorlessClient` (sync) and `AsyncVectorlessClient` (async) expose:

| Method | Returns | Description |
|--------|---------|-------------|
| `health()` | `HealthResponse` | Server liveness check |
| `version()` | `VersionResponse` | Server build version |
| `ingest_document(source, **opts)` | `IngestDocumentResponse` | Upload a document |
| `get_document(id)` | `Document` | Get document metadata |
| `list_documents(**opts)` | `ListDocumentsResponse` | Paginated document list |
| `delete_document(id)` | `None` | Delete document + sections |
| `wait_for_ready(id, **opts)` | `Document` | Poll until processed |
| `get_document_tree(id)` | `DocumentTree` | Hierarchical outline |
| `get_section(id)` | `Section` | Full section content |
| `get_sections(ids)` | `list[Section]` | Multi-section fetch |
| `query(doc_id, query, **opts)` | `QueryResponse` | Retrieve relevant sections |
| `query_stream(doc_id, query, **opts)` | `Iterator[QueryStreamEvent]` | Stream results |
| `close()` | `None` | Release resources |

### Error Handling

```python
from vectorless import (
    VectorlessError,
    AuthenticationError,
    NotFoundError,
    RateLimitError,
)

try:
    doc = client.get_document("doc_123")
except NotFoundError:
    print("Document not found")
except AuthenticationError:
    print("Check your API key")
except RateLimitError as e:
    print(f"Rate limited, retry after {e.retry_after}s")
except VectorlessError as e:
    print(f"Error {e.status}: {e.message}")
```

| Exception | Status | When |
|-----------|--------|------|
| `AuthenticationError` | 401 | Missing or invalid API key |
| `PermissionDeniedError` | 403 | Insufficient permissions |
| `NotFoundError` | 404 | Document or section not found |
| `ValidationError` | 400 | Invalid request parameters |
| `ConflictError` | 409 | Idempotency conflict |
| `RateLimitError` | 429 | Too many requests |
| `TimeoutError` | 408 | Request timed out |
| `ServerError` | 500 | Internal server error |
| `DocumentFailedError` | 422 | Document processing failed |
| `StreamError` | — | Stream interrupted |

## Context Manager

```python
# Sync
with VectorlessClient(api_key="vl_...") as client:
    doc = client.get_document("doc_123")

# Async
async with AsyncVectorlessClient(api_key="vl_...") as client:
    doc = await client.get_document("doc_123")
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `VECTORLESS_API_KEY` | API key fallback |
| `VECTORLESS_BASE_URL` | Base URL fallback |

## Requirements

- Python 3.9+
- Dependencies: `httpx`, `pydantic`

## License

MIT
