<h1 align="center">
  <code>vectorless</code>
</h1>

<p align="center">
  <strong>Official TypeScript SDK for Vectorless — structure-preserving document retrieval.</strong>
</p>

<p align="center">
  <a href="https://www.npmjs.com/package/vectorless"><img src="https://img.shields.io/npm/v/vectorless?style=flat-square&logo=npm&logoColor=white&color=CB3837" alt="npm version" /></a>
  <a href="https://www.npmjs.com/package/vectorless"><img src="https://img.shields.io/npm/dm/vectorless?style=flat-square&color=CB3837" alt="npm downloads" /></a>
  <a href="https://img.shields.io/node/v/vectorless"><img src="https://img.shields.io/node/v/vectorless?style=flat-square&logo=node.js&logoColor=white&color=339933" alt="node" /></a>
  <a href="https://img.shields.io/npm/l/vectorless"><img src="https://img.shields.io/npm/l/vectorless?style=flat-square&color=blue" alt="license" /></a>
  <a href="https://github.com/hallelx2/vectorless-sdk/actions"><img src="https://img.shields.io/github/actions/workflow/status/hallelx2/vectorless-sdk/ci.yml?style=flat-square&label=CI" alt="CI" /></a>
  <img src="https://img.shields.io/badge/dependencies-0-brightgreen?style=flat-square" alt="zero deps" />
</p>

---

## Install

```bash
npm install vectorless
# or
yarn add vectorless
# or
pnpm add vectorless
```

## Quick Start

```typescript
import { VectorlessClient } from "vectorless";

// Deployed instance with API key
const client = new VectorlessClient({
  baseUrl: "https://api.vectorless.dev",
  apiKey: "vl_live_...",
});

// Self-hosted, no auth needed
// const client = new VectorlessClient({ baseUrl: "http://localhost:8080" });

// 1. Ingest a document
const result = await client.ingestDocument("./research-paper.pdf", {
  filename: "research-paper.pdf",
  metadata: { department: "engineering" },
});

// 2. Wait for processing (parsing → summarizing → ready)
const doc = await client.waitForReady(result.document_id, {
  onProgress: (status) => console.log(`Status: ${status}`),
});

// 3. Explore the document tree
const tree = await client.getDocumentTree(doc.id);
for (const section of tree.sections) {
  console.log("  ".repeat(section.depth) + `${section.title} (${section.tokens} tokens)`);
}

// 4. Query — LLM navigates the tree to find relevant sections
const response = await client.query(doc.id, "What methodology was used?");
for (const section of response.sections) {
  console.log(`\n## ${section.title}\n${section.content}`);
}
console.log(`Strategy: ${response.strategy} | ${response.elapsed_ms}ms | Cost: $${response.usage?.cost_usd}`);
```

## Transport Protocols

Choose the wire protocol at init time:

```typescript
// HTTP/REST — default, zero dependencies, uses built-in fetch
const client = new VectorlessClient({ transport: "http" });

// ConnectRPC — protobuf JSON encoding, native streaming support
const client = new VectorlessClient({ transport: "connect" });
```

```
┌──────────────────────────────────────────┐
│           VectorlessClient               │
├──────────────────────────────────────────┤
│          Transport Abstraction            │
│  ┌─────────────────┐ ┌────────────────┐ │
│  │  HttpTransport   │ │ConnectTransport│ │
│  │  REST/JSON       │ │ ConnectRPC     │ │
│  │  SSE streaming   │ │ JSON encoding  │ │
│  │  GET/POST /v1/*  │ │ POST /{svc}/*  │ │
│  │  Zero deps       │ │ Zero deps      │ │
│  └────────┬────────┘ └───────┬────────┘ │
│           │                   │          │
│    vectorless-server   vectorless-server  │
└──────────────────────────────────────────┘
```

## Streaming Queries

Watch retrieval progress in real-time:

```typescript
for await (const event of client.queryStream(docId, "Explain the results")) {
  switch (event.type) {
    case "started":
      console.log(`Strategy: ${event.strategy}`);
      break;
    case "section_selected":
      console.log(`Found: ${event.section?.title}`);
      break;
    case "completed":
      console.log(`Done in ${event.elapsed_ms}ms`);
      break;
  }
}
```

## API Reference

### Client Configuration

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `baseUrl` | `string` | `"http://localhost:8080"` | Server URL |
| `apiKey` | `string` | `env VECTORLESS_API_KEY` | Bearer token |
| `transport` | `"http" \| "connect"` | `"http"` | Wire protocol |
| `timeout` | `number` | `30000` | Request timeout (ms) |
| `maxRetries` | `number` | `3` | Retry attempts |
| `retryDelay` | `number` | `500` | Base retry delay (ms) |

### Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `health()` | `HealthResponse` | Server liveness check |
| `version()` | `VersionResponse` | Server build version |
| `ingestDocument(source, opts?)` | `IngestDocumentResponse` | Upload a document |
| `getDocument(id)` | `Document` | Get document metadata |
| `listDocuments(opts?)` | `ListDocumentsResponse` | Paginated document list |
| `deleteDocument(id)` | `void` | Delete document + sections |
| `waitForReady(id, opts?)` | `Document` | Poll until processed |
| `getDocumentTree(id)` | `DocumentTree` | Hierarchical outline |
| `getSection(id)` | `Section` | Full section content |
| `getSections(ids)` | `Section[]` | Parallel section fetch |
| `query(docId, query, opts?)` | `QueryResponse` | Retrieve relevant sections |
| `queryStream(docId, query, opts?)` | `AsyncIterable<QueryStreamEvent>` | Stream results |
| `close()` | `void` | Release resources |

### Error Types

| Error | Status | When |
|-------|--------|------|
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

```typescript
import { NotFoundError, AuthenticationError } from "vectorless";

try {
  await client.getDocument("doc_123");
} catch (err) {
  if (err instanceof NotFoundError) {
    console.log("Document not found");
  } else if (err instanceof AuthenticationError) {
    console.log("Check your API key");
  }
}
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `VECTORLESS_API_KEY` | API key (fallback if not passed to constructor) |

## Requirements

- Node.js 18+
- Zero runtime dependencies

## License

MIT
