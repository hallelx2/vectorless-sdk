# Vectorless SDK

Official client SDKs for the Vectorless document retrieval engine.

## Project Structure

```
vectorless-sdk/
├── typescript/          TypeScript SDK (npm: vectorless)
│   ├── src/
│   │   ├── client.ts        Main VectorlessClient
│   │   ├── types.ts         All types (aligned to server proto)
│   │   ├── errors.ts        Error hierarchy (10 types)
│   │   ├── config.ts        Config resolution
│   │   ├── retry.ts         Exponential backoff + jitter
│   │   ├── upload.ts        Multipart + JSON upload helpers
│   │   ├── streaming.ts     SSE parser
│   │   ├── index.ts         Public exports
│   │   └── transport/
│   │       ├── interface.ts   Transport abstraction
│   │       ├── http.ts        HTTP/REST transport (default)
│   │       └── connect.ts     ConnectRPC transport
│   └── __tests__/
├── python/              Python SDK (PyPI: vectorless)
│   ├── vectorless/
│   │   ├── client.py         Sync VectorlessClient
│   │   ├── async_client.py   AsyncVectorlessClient
│   │   ├── types.py          Pydantic models (aligned to server proto)
│   │   ├── errors.py         Error hierarchy (10 types)
│   │   ├── _config.py        Config resolution
│   │   ├── _retry.py         Sync + async retry with backoff
│   │   ├── _upload.py        Multipart + JSON upload helpers
│   │   ├── _streaming.py     SSE + Connect stream parsers
│   │   ├── _version.py       Version constant
│   │   └── transport/
│   │       ├── base.py        Abstract Transport / AsyncTransport
│   │       ├── http.py        HTTP/REST (sync + async)
│   │       └── connect.py     ConnectRPC (sync + async)
│   └── tests/
└── CLAUDE.md

## Architecture

Both SDKs implement the same design:

1. **Client** — public API surface, transport-agnostic
2. **Transport interface** — abstract contract for wire protocols
3. **HTTP transport** — REST/JSON over standard `/v1/*` endpoints (default)
4. **Connect transport** — ConnectRPC JSON protocol over `/{service}/{method}` paths
5. **Retry** — exponential backoff with jitter, Retry-After support
6. **Streaming** — SSE parser (HTTP) and Connect stream parser (Connect)

## Server API Surface

The SDKs target the **vectorless-server** HTTP + Connect endpoints:

### REST Endpoints (HTTP transport)
- `GET  /v1/health` / `GET /v1/version`
- `POST /v1/documents` (multipart) → 202
- `GET  /v1/documents` (list, paginated)
- `GET  /v1/documents/{id}` / `DELETE /v1/documents/{id}`
- `GET  /v1/documents/{id}/tree`
- `GET  /v1/sections/{id}`
- `POST /v1/query` / `POST /v1/query/stream` (SSE)

### Connect RPCs (Connect transport)
- `vectorless.v1.HealthService/Check` / `Version`
- `vectorless.v1.DocumentsService/CreateDocument` / `GetDocument` / `ListDocuments` / `DeleteDocument` / `GetDocumentTree` / `GetSection`
- `vectorless.v1.QueryService/Query` / `QueryStream`

## Auth
- Deployed: `Authorization: Bearer <api_key>` (required)
- Self-hosted: API key optional (configurable via `auth.mode: none`)

## Version
- v1.0.0 — first stable release, aligned to vectorless-server proto definitions
```
