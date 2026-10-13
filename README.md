<p align="center">
  <img src="https://img.shields.io/badge/vectorless-SDK-000000?style=for-the-badge&logo=data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9IndoaXRlIiBzdHJva2Utd2lkdGg9IjIiPjxwYXRoIGQ9Ik00IDRoMTZ2MTZINHoiLz48cGF0aCBkPSJNOCA4aDh2OEg4eiIvPjxwYXRoIGQ9Ik0xMiA0djE2Ii8+PHBhdGggZD0iTTQgMTJoMTYiLz48L3N2Zz4=" alt="Vectorless SDK" />
</p>

<h1 align="center">Vectorless SDK</h1>

<p align="center">
  <strong>Official client SDKs for Vectorless: document retrieval without chunking or embeddings.</strong>
</p>

<p align="center">
  <a href="https://www.npmjs.com/package/vectorless"><img src="https://img.shields.io/npm/v/vectorless?style=flat-square&logo=npm&logoColor=white&label=npm&color=CB3837" alt="npm" /></a>
  <a href="https://pypi.org/project/vectorless-sdk/"><img src="https://img.shields.io/pypi/v/vectorless-sdk?style=flat-square&logo=python&logoColor=white&label=PyPI&color=3776AB" alt="PyPI" /></a>
  <a href="https://pkg.go.dev/github.com/hallelx2/vectorless-sdk/go"><img src="https://img.shields.io/badge/Go-pkg.go.dev-00ADD8?style=flat-square&logo=go&logoColor=white" alt="Go" /></a>
  <a href="https://github.com/hallelx2/vectorless-sdk/actions"><img src="https://img.shields.io/github/actions/workflow/status/hallelx2/vectorless-sdk/ci.yml?style=flat-square&label=CI" alt="CI" /></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue?style=flat-square" alt="License" /></a>
</p>

---

## Status

The hosted Vectorless service has been paused since 12 October 2026, so `https://api.vectorless.dev` and `vl_live_` keys don't work while it is down. The SDKs and the engine are open source. Point the clients at an engine you run yourself with the engine's [self-host setup](https://github.com/hallelx2/vectorless-engine#self-host-the-engine), and pass its `VECTORLESS_API_KEY` as the client's API key. Contact: halleluyaholudele@gmail.com.

## How it works

Vectorless is a Go retrieval engine with no chunking, no embeddings and no vector database. These SDKs are thin clients for its HTTP and ConnectRPC API. What happens behind the API, in the pipeline production ran from 2026-10-06:

1. **Ingest.** pdfgrab reads every word on every PDF page with its rectangle. The engine finds the document's contents page; code lists the candidate entries and Jev, TypeSafe's System One model, confirms them. Each entry is placed on its real page by searching the body, with Jev picking the page. Sections over 20 pages are split at their own headings. Ingest makes no generative call and writes no summaries.
2. **Query.** Jev ranks the sections against the question, skims the heads of the candidate pages, reads the best pages in full and follows "see Note N" cross-references. The evidence pages come back verbatim, with page ranges. `query()` returns this. Retrieval makes no generative call.
3. **Answer.** On `POST /v1/answer`, a generative model writes the answer over the evidence pages and each claim is pinned to a line of its page (a pincite). Jev picks the supporting quote from the page's own sentences, so no generated text can reach a citation.
4. **Replay.** Every answer is stored under a trace token and can be returned again byte for byte. That is a stored record, not a re-run: Jev is not deterministic.

Jev is a hosted TypeSafe API. Without a TypeSafe key the engine falls back to a generative model for these decisions. Dated measurements, and what they do not show, are in the engine's [Results](https://github.com/hallelx2/vectorless-engine#results) and [evaluation reports](https://github.com/hallelx2/vectorless-engine/tree/main/docs/evaluations).

### What the SDKs cover

| Call | TypeScript | Python | Go |
|---|---|---|---|
| Ingest, get, list, delete documents; wait until ready | yes | yes | yes |
| Document tree, sections | yes | yes | yes |
| `query` (evidence pages and sections), streaming query | yes | yes | yes |
| `answer_treewalk` (`POST /v1/answer/treewalk`, generative page walk) | no | yes | no |
| `POST /v1/answer` with pincites, page images, `/v1/replay` | no | no | no |

The last row has no SDK method. Call those routes over HTTP; they are listed in the [engine README](https://github.com/hallelx2/vectorless-engine#http-api).

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
│                  Vectorless Engine (Go)                   │
│  ┌─────────┐ ┌──────────┐ ┌──────────┐ ┌────────────┐  │
│  │ pdfgrab │ │ Contents │ │judgewalk │ │  llmgate   │  │
│  │ layout  │ │ tree,    │ │ evidence │ │ Jev judge  │  │
│  │ MD HTML │ │ placed   │ │ pages,   │ │ + answer   │  │
│  │ DOCX    │ │ by Jev   │ │ pincites │ │   model    │  │
│  └─────────┘ └──────────┘ └──────────┘ └────────────┘  │
│  ┌─────────────┐ ┌────────────┐ ┌───────────────────┐  │
│  │  PostgreSQL  │ │ S3/GCS/    │ │  River/QStash     │  │
│  │  docs, tree  │ │ local files│ │  job queue        │  │
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
  baseUrl: "http://localhost:7654",
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
    base_url="http://localhost:7654",
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
    vectorless.WithBaseURL("http://localhost:7654"),
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

## Pointing at a server

The SDKs work with any Vectorless engine. A local engine (`go run ./cmd/engine --local`, or the all-in-one container) listens on `:7654` and needs no API key. A server started with `auth.mode: api_key` needs one:

```python
# Local engine: no API key
client = VectorlessClient(base_url="http://localhost:7654")

# A server you run with API-key auth
client = VectorlessClient(base_url="https://your-host", api_key="<your key>")
```

## License

MIT
