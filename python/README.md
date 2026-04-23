# Vectorless Python SDK

Official Python client for [Vectorless](https://vectorless.dev) — structure-preserving document retrieval without embeddings.

## Install

```bash
pip install vectorless-sdk
```

## Quick Start

```python
from vectorless import VectorlessClient

# Connect to a deployed instance
client = VectorlessClient(
    base_url="https://api.vectorless.dev",
    api_key="vl_live_...",
)

# Or self-hosted (no API key needed)
client = VectorlessClient(base_url="http://localhost:8080")

# Ingest a document
result = client.ingest_document(
    "./report.pdf",
    filename="report.pdf",
    metadata={"team": "engineering"},
)

# Wait for processing
doc = client.wait_for_ready(result.document_id)

# Get the document tree
tree = client.get_document_tree(doc.id)
for section in tree.sections:
    print("  " * section.depth + section.title)

# Query — LLM navigates the tree to find relevant sections
response = client.query(doc.id, "How does authentication work?")
for section in response.sections:
    print(f"[{section.title}]")
    print(section.content)
print(f"Strategy: {response.strategy}, Time: {response.elapsed_ms}ms")
```

## Async Support

```python
from vectorless import AsyncVectorlessClient

async with AsyncVectorlessClient(
    base_url="https://api.vectorless.dev",
    api_key="vl_live_...",
) as client:
    result = await client.ingest_document(b"# Hello\n\nWorld")
    doc = await client.wait_for_ready(result.document_id)
    response = await client.query(doc.id, "What is this about?")
```

## Transport Protocols

The SDK supports two wire protocols:

```python
# HTTP/REST (default) — standard REST endpoints
client = VectorlessClient(base_url="http://localhost:8080")

# ConnectRPC — protobuf JSON encoding, native streaming
client = VectorlessClient(base_url="http://localhost:8080", transport="connect")
```

## Streaming Queries

```python
for event in client.query_stream(doc_id, "Explain clustering"):
    if event.type == "section_selected" and event.section:
        print(f"Found: {event.section.title}")
    if event.type == "completed":
        print(f"Done in {event.elapsed_ms}ms")
```

## API Reference

| Method | Description |
|--------|-------------|
| `ingest_document()` | Upload and ingest a document |
| `get_document()` | Get document metadata and status |
| `list_documents()` | List documents with pagination |
| `delete_document()` | Delete a document |
| `wait_for_ready()` | Poll until document is processed |
| `get_document_tree()` | Get hierarchical document outline |
| `get_section()` | Fetch a section with full content |
| `get_sections()` | Fetch multiple sections |
| `query()` | Query a document |
| `query_stream()` | Stream query results |
| `health()` | Server health check |
| `version()` | Server version |

## License

MIT
