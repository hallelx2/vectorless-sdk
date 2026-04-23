<h1 align="center">
  <code>vectorless-sdk/go</code>
</h1>

<p align="center">
  <strong>Official Go SDK for Vectorless — structure-preserving document retrieval.</strong>
</p>

<p align="center">
  <a href="https://pkg.go.dev/github.com/hallelx2/vectorless-sdk/go"><img src="https://img.shields.io/badge/Go-pkg.go.dev-00ADD8?style=flat-square&logo=go&logoColor=white" alt="Go Reference" /></a>
  <a href="https://pkg.go.dev/github.com/hallelx2/vectorless-sdk/go"><img src="https://img.shields.io/github/go-mod/go-version/hallelx2/vectorless-sdk?filename=go%2Fgo.mod&style=flat-square&logo=go&logoColor=white" alt="Go Version" /></a>
  <img src="https://img.shields.io/badge/dependencies-0-brightgreen?style=flat-square" alt="zero deps" />
  <a href="https://github.com/hallelx2/vectorless-sdk/actions"><img src="https://img.shields.io/github/actions/workflow/status/hallelx2/vectorless-sdk/ci.yml?style=flat-square&label=CI" alt="CI" /></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue?style=flat-square" alt="License" /></a>
</p>

---

## Install

```bash
go get github.com/hallelx2/vectorless-sdk/go@latest
```

## Quick Start

```go
package main

import (
    "context"
    "fmt"
    "os"
    "strings"

    vectorless "github.com/hallelx2/vectorless-sdk/go"
    _ "github.com/hallelx2/vectorless-sdk/go/transport" // registers HTTP + Connect transports
)

func main() {
    ctx := context.Background()

    // Deployed instance
    client, err := vectorless.NewClient(
        vectorless.WithBaseURL("https://api.vectorless.dev"),
        vectorless.WithAPIKey("vl_live_..."),
    )
    if err != nil {
        panic(err)
    }
    defer client.Close()

    // Self-hosted: vectorless.NewClient() with no options
    // ConnectRPC: vectorless.NewClient(vectorless.WithTransport(vectorless.TransportConnect))

    // 1. Ingest a document
    file, _ := os.Open("./research-paper.pdf")
    defer file.Close()

    result, err := client.IngestDocument(ctx, file, vectorless.IngestDocumentOptions{
        Filename: "research-paper.pdf",
        Metadata: map[string]string{"department": "engineering"},
    })
    if err != nil {
        panic(err)
    }

    // 2. Wait for processing
    doc, err := client.WaitForReady(ctx, result.DocumentID, &vectorless.WaitForReadyOptions{
        OnProgress: func(s vectorless.DocumentStatus) {
            fmt.Printf("Status: %s\n", s)
        },
    })
    if err != nil {
        panic(err)
    }

    // 3. Explore the document tree
    tree, _ := client.GetDocumentTree(ctx, doc.ID)
    for _, s := range tree.Sections {
        fmt.Printf("%s%s (%d tokens)\n", strings.Repeat("  ", s.Depth), s.Title, s.Tokens)
    }

    // 4. Query
    resp, _ := client.Query(ctx, doc.ID, "What methodology was used?", nil)
    for _, s := range resp.Sections {
        fmt.Printf("\n## %s\n%s\n", s.Title, s.Content)
    }
    fmt.Printf("Strategy: %s | %dms\n", resp.Strategy, resp.ElapsedMs)
}
```

## Transport Protocols

```go
// HTTP/REST — default, uses net/http, SSE streaming
client, _ := vectorless.NewClient(
    vectorless.WithTransport(vectorless.TransportHTTP),
)

// ConnectRPC — protobuf JSON encoding, native streaming
client, _ := vectorless.NewClient(
    vectorless.WithTransport(vectorless.TransportConnect),
)
```

> **Important:** Import the transport package to register the implementations:
> ```go
> import _ "github.com/hallelx2/vectorless-sdk/go/transport"
> ```

```
┌────────────────────────────────────────────┐
│              vectorless.Client             │
├────────────────────────────────────────────┤
│        vectorless.TransportIface           │
│  ┌──────────────────┐ ┌────────────────┐  │
│  │  HTTPTransport    │ │ConnectTransport│  │
│  │  net/http         │ │ net/http       │  │
│  │  SSE streaming    │ │ NDJSON stream  │  │
│  │  GET/POST /v1/*   │ │ POST /{svc}/*  │  │
│  └──────────────────┘ └────────────────┘  │
│              Zero dependencies             │
└────────────────────────────────────────────┘
```

## Streaming Queries

Uses Go 1.23+ `iter.Seq2` for idiomatic iteration:

```go
stream, err := client.QueryStream(ctx, docID, "Explain the results", nil)
if err != nil {
    panic(err)
}

for event, err := range stream {
    if err != nil {
        panic(err)
    }
    switch event.Type {
    case vectorless.EventStarted:
        fmt.Printf("Strategy: %s\n", event.Strategy)
    case vectorless.EventSectionSelected:
        fmt.Printf("Found: %s\n", event.Section.Title)
    case vectorless.EventCompleted:
        fmt.Printf("Done in %dms\n", event.ElapsedMs)
    }
}
```

## API Reference

### Client Options

| Option | Description |
|--------|-------------|
| `WithBaseURL(url)` | Server URL (default `http://localhost:8080`) |
| `WithAPIKey(key)` | Bearer token (falls back to `VECTORLESS_API_KEY` env) |
| `WithTransport(proto)` | `TransportHTTP` (default) or `TransportConnect` |
| `WithTimeout(ms)` | Request timeout in ms (default 30,000) |
| `WithMaxRetries(n)` | Retry attempts (default 3) |
| `WithRetryDelay(ms)` | Base retry delay in ms (default 500) |

### Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `Health(ctx)` | `*HealthResponse` | Server liveness |
| `Version(ctx)` | `*VersionResponse` | Server version |
| `IngestDocument(ctx, reader, opts)` | `*IngestDocumentResponse` | Upload document |
| `GetDocument(ctx, id)` | `*Document` | Document metadata |
| `ListDocuments(ctx, opts)` | `*ListDocumentsResponse` | Paginated list |
| `DeleteDocument(ctx, id)` | `error` | Delete document |
| `WaitForReady(ctx, id, opts)` | `*Document` | Poll until ready |
| `GetDocumentTree(ctx, id)` | `*DocumentTree` | Document outline |
| `GetSection(ctx, id)` | `*Section` | Section with content |
| `Query(ctx, docID, query, opts)` | `*QueryResponse` | Retrieve sections |
| `QueryStream(ctx, docID, query, opts)` | `iter.Seq2[Event, error]` | Stream results |
| `Close()` | `error` | Release resources |

### Error Handling

```go
doc, err := client.GetDocument(ctx, "doc_123")
if err != nil {
    if vectorless.IsNotFound(err) {
        fmt.Println("Document not found")
    } else if vectorless.IsAuthError(err) {
        fmt.Println("Check your API key")
    } else if vectorless.IsRetryable(err) {
        fmt.Println("Transient error, retry later")
    } else {
        // Access the full error details
        var vErr *vectorless.Error
        if errors.As(err, &vErr) {
            fmt.Printf("Status: %d, Code: %s, RequestID: %s\n",
                vErr.Status, vErr.Code, vErr.RequestID)
        }
    }
}
```

| Helper | Matches |
|--------|---------|
| `IsNotFound(err)` | 404 |
| `IsAuthError(err)` | 401, 403 |
| `IsRateLimited(err)` | 429 |
| `IsRetryable(err)` | 429, 408, 504, 5xx |

## Environment Variables

| Variable | Description |
|----------|-------------|
| `VECTORLESS_API_KEY` | API key fallback |
| `VECTORLESS_BASE_URL` | Base URL fallback |

## Requirements

- Go 1.23+ (uses `iter.Seq2` for streaming)
- Zero external dependencies — only `net/http`, `encoding/json`, stdlib

## License

MIT
