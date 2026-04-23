<p align="center">
  <img src="https://img.shields.io/badge/vectorless-SDK-000000?style=for-the-badge&logo=data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9IndoaXRlIiBzdHJva2Utd2lkdGg9IjIiPjxwYXRoIGQ9Ik00IDRoMTZ2MTZINHoiLz48cGF0aCBkPSJNOCA4aDh2OEg4eiIvPjxwYXRoIGQ9Ik0xMiA0djE2Ii8+PHBhdGggZD0iTTQgMTJoMTYiLz48L3N2Zz4=" alt="Vectorless SDK" />
</p>

<h1 align="center">Vectorless SDK</h1>

<p align="center">
  <strong>Official client SDKs for Vectorless — structure-preserving document retrieval without embeddings.</strong>
</p>

<p align="center">
  <a href="https://www.npmjs.com/package/vectorless"><img src="https://img.shields.io/npm/v/vectorless?style=flat-square&logo=npm&logoColor=white&label=npm&color=CB3837" alt="npm" /></a>
  <a href="https://pypi.org/project/vectorless-sdk/"><img src="https://img.shields.io/pypi/v/vectorless-sdk?style=flat-square&logo=python&logoColor=white&label=PyPI&color=3776AB" alt="PyPI" /></a>
  <a href="https://pkg.go.dev/github.com/hallelx2/vectorless-sdk/go"><img src="https://img.shields.io/badge/Go-pkg.go.dev-00ADD8?style=flat-square&logo=go&logoColor=white" alt="Go" /></a>
  <a href="https://github.com/hallelx2/vectorless-sdk/actions"><img src="https://img.shields.io/github/actions/workflow/status/hallelx2/vectorless-sdk/ci.yml?style=flat-square&label=CI" alt="CI" /></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue?style=flat-square" alt="License" /></a>
</p>

---

## What is Vectorless?

Vectorless is a document retrieval engine that preserves document structure. Instead of chunking documents into fragments and embedding them in a vector database, Vectorless:

1. **Parses** documents into hierarchical trees (headings → sections)
2. **Summarizes** each section with an LLM
3. **Retrieves** by having the LLM reason over the tree outline to select the most relevant sections

No embeddings. No vector databases. Full sections returned with complete context.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     Your Application                     │
├───────────┬───────────────┬─────────────────────────────┤
│ TypeScript│    Python     │             Go              │
│    SDK    │     SDK       │            SDK              │
├───────────┴───────────────┴─────────────────────────────┤
│              Transport Layer (pick one)                   │
│  ┌──────────────────────┐  ┌──────────────────────────┐ │
│  │   HTTP/REST (default) │  │   ConnectRPC (protobuf)  │ │
│  │   GET/POST /v1/*      │  │   POST /{svc}/{method}   │ │
│  │   SSE streaming       │  │   Native streaming       │ │
│  └──────────────────────┘  └──────────────────────────┘ │
├─────────────────────────────────────────────────────────┤
│                  Vectorless Server                        │
│  ┌────────┐ ┌──────────┐ ┌─────────┐ ┌──────────────┐  │
│  │  Auth  │ │   CORS   │ │  Metrics│ │   Tracing    │  │
│  └────────┘ └──────────┘ └─────────┘ └──────────────┘  │
├─────────────────────────────────────────────────────────┤
│                  Vectorless Engine                        │
│  ┌─────────┐ ┌──────────┐ ┌────────┐ ┌─────────────┐  │
│  │ Parsers │ │ Tree     │ │Retrieval│ │  LLM Gate   │  │
│  │ MD HTML │ │ Builder  │ │ single  │ │  Anthropic  │  │
│  │ PDF DOCX│ │ Summaries│ │ chunked │ │  OpenAI     │  │
│  └─────────┘ └──────────┘ └────────┘ │  Gemini     │  │
│                                       └─────────────┘  │
│  ┌─────────────┐ ┌────────────┐ ┌───────────────────┐  │
│  │  PostgreSQL  │ │   S3/MinIO │ │  River/QStash     │  │
│  │  docs+sections│ │  content   │ │  job queue        │  │
│  └─────────────┘ └────────────┘ └───────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

## SDKs

### TypeScript

```bash
npm install vectorless
```

```typescript
import { VectorlessClient } from "vectorless";

const client = new VectorlessClient({
  baseUrl: "https://api.vectorless.dev",
  apiKey: "vl_live_...",
});

const result = await client.ingestDocument("./report.pdf");
const doc = await client.waitForReady(result.document_id);
const response = await client.query(doc.id, "How does auth work?");
```

[Full TypeScript docs →](./typescript/)

### Python

```bash
pip install vectorless-sdk
```

```python
from vectorless import VectorlessClient

client = VectorlessClient(
    base_url="https://api.vectorless.dev",
    api_key="vl_live_...",
)

result = client.ingest_document("./report.pdf")
doc = client.wait_for_ready(result.document_id)
response = client.query(doc.id, "How does auth work?")
```

[Full Python docs →](./python/)

### Go

```bash
go get github.com/hallelx2/vectorless-sdk/go
```

```go
import (
    vectorless "github.com/hallelx2/vectorless-sdk/go"
    _ "github.com/hallelx2/vectorless-sdk/go/transport"
)

client, _ := vectorless.NewClient(
    vectorless.WithBaseURL("https://api.vectorless.dev"),
    vectorless.WithAPIKey("vl_live_..."),
)
defer client.Close()

result, _ := client.IngestDocument(ctx, file, vectorless.IngestDocumentOptions{
    Filename: "report.pdf",
})
doc, _ := client.WaitForReady(ctx, result.DocumentID, nil)
response, _ := client.Query(ctx, doc.ID, "How does auth work?", nil)
```

[Full Go docs →](./go/)

## Transport Protocols

All three SDKs support two wire protocols. Pick one at init time:

| Protocol | Default | Streaming | Dependencies |
|----------|---------|-----------|--------------|
| **HTTP/REST** | ✅ | SSE (`text/event-stream`) | None (built-in `fetch`/`httpx`/`net/http`) |
| **ConnectRPC** | — | Native Connect streaming | None (JSON encoding, no protobuf tooling) |

```typescript
// TypeScript
new VectorlessClient({ transport: "connect" });
```
```python
# Python
VectorlessClient(transport="connect")
```
```go
// Go
vectorless.NewClient(vectorless.WithTransport(vectorless.TransportConnect))
```

## Deploying the Server

The SDKs work with both **deployed** and **self-hosted** Vectorless instances:

```bash
# Self-hosted: no API key needed
client = VectorlessClient(base_url="http://localhost:8080")

# Deployed: API key required
client = VectorlessClient(
    base_url="https://api.vectorless.dev",
    api_key="vl_live_...",
)
```

## License

MIT
