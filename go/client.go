package vectorless

import (
	"context"
	"fmt"
	"io"
	"iter"
	"net/http"
	"strings"
	"sync"
	"time"
)

// TransportIface is the wire protocol abstraction.
// Exported so transport sub-packages can implement it without import cycles.
type TransportIface interface {
	Health(ctx context.Context) (*HealthResponse, error)
	Version(ctx context.Context) (*VersionResponse, error)
	IngestDocument(ctx context.Context, body io.Reader, opts IngestDocumentOptions) (*IngestDocumentResponse, error)
	GetDocument(ctx context.Context, documentID string) (*Document, error)
	ListDocuments(ctx context.Context, opts ListDocumentsOptions) (*ListDocumentsResponse, error)
	DeleteDocument(ctx context.Context, documentID string) error
	GetDocumentTree(ctx context.Context, documentID string) (*DocumentTree, error)
	GetSection(ctx context.Context, sectionID string) (*Section, error)
	Query(ctx context.Context, documentID, query string, opts *QueryOptions) (*QueryResponse, error)
	QueryStream(ctx context.Context, documentID, query string, opts *QueryOptions) (iter.Seq2[QueryStreamEvent, error], error)
	Close() error
}

// TransportFactory creates a transport from a config.
// Register implementations via RegisterTransportFactory.
type TransportFactory func(cfg Config) TransportIface

var (
	transportFactories = map[TransportProtocol]TransportFactory{}
	factoryMu          sync.RWMutex
)

// RegisterTransportFactory registers a transport factory for a protocol.
// Called by transport sub-packages in their init() functions.
func RegisterTransportFactory(protocol TransportProtocol, factory TransportFactory) {
	factoryMu.Lock()
	defer factoryMu.Unlock()
	transportFactories[protocol] = factory
}

// Client is the main Vectorless SDK client.
//
// Create one with NewClient and functional options:
//
//	client, err := vectorless.NewClient(
//	    vectorless.WithBaseURL("https://api.vectorless.dev"),
//	    vectorless.WithAPIKey("vl_live_..."),
//	)
//
//	// Self-hosted, no auth
//	client, err := vectorless.NewClient()
//
//	// ConnectRPC transport
//	client, err := vectorless.NewClient(
//	    vectorless.WithTransport(vectorless.TransportConnect),
//	)
type Client struct {
	transport TransportIface
	cfg       Config
}

// NewClient creates a new Vectorless client.
//
// Defaults to HTTP transport at http://localhost:8080 with no API key.
// Use functional options to configure.
func NewClient(opts ...Option) (*Client, error) {
	cfg := resolveConfig(opts)

	factoryMu.RLock()
	factory, ok := transportFactories[cfg.Transport]
	factoryMu.RUnlock()

	if !ok {
		return nil, fmt.Errorf("vectorless: unknown transport %q — did you import the transport package?", cfg.Transport)
	}

	return &Client{transport: factory(cfg), cfg: cfg}, nil
}

// ── Health ──

// Health checks server liveness.
func (c *Client) Health(ctx context.Context) (*HealthResponse, error) {
	return c.transport.Health(ctx)
}

// Version returns the server build version.
func (c *Client) Version(ctx context.Context) (*VersionResponse, error) {
	return c.transport.Version(ctx)
}

// ── Documents ──

// IngestDocument uploads a document for processing.
// Returns immediately with a document ID and "pending" status.
// Use WaitForReady to poll until processing completes.
func (c *Client) IngestDocument(ctx context.Context, body io.Reader, opts IngestDocumentOptions) (*IngestDocumentResponse, error) {
	return c.transport.IngestDocument(ctx, body, opts)
}

// GetDocument returns document metadata and processing status.
func (c *Client) GetDocument(ctx context.Context, documentID string) (*Document, error) {
	return c.transport.GetDocument(ctx, documentID)
}

// ListDocuments returns a paginated list of documents.
func (c *Client) ListDocuments(ctx context.Context, opts ListDocumentsOptions) (*ListDocumentsResponse, error) {
	return c.transport.ListDocuments(ctx, opts)
}

// DeleteDocument deletes a document and all its sections.
func (c *Client) DeleteDocument(ctx context.Context, documentID string) error {
	return c.transport.DeleteDocument(ctx, documentID)
}

// GetDocumentTree returns the hierarchical document outline.
func (c *Client) GetDocumentTree(ctx context.Context, documentID string) (*DocumentTree, error) {
	return c.transport.GetDocumentTree(ctx, documentID)
}

// GetLLMSTxt returns the document rendered as an llms.txt Markdown map —
// H1 title, a blockquote summary, and a nested section outline with
// one-line summaries. A compact, agent-friendly index of the document.
func (c *Client) GetLLMSTxt(ctx context.Context, documentID string) (string, error) {
	u := strings.TrimRight(c.cfg.BaseURL, "/") + "/v1/documents/" + documentID + "/llms.txt"
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, u, nil)
	if err != nil {
		return "", err
	}
	if c.cfg.APIKey != "" {
		req.Header.Set("Authorization", "Bearer "+c.cfg.APIKey)
	}
	if c.cfg.Store != "" {
		req.Header.Set("X-Vectorless-Store", c.cfg.Store)
	}
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		return "", err
	}
	defer resp.Body.Close()
	b, err := io.ReadAll(resp.Body)
	if err != nil {
		return "", err
	}
	if resp.StatusCode >= 400 {
		return "", fmt.Errorf("vectorless: GetLLMSTxt failed: HTTP %d: %s", resp.StatusCode, string(b))
	}
	return string(b), nil
}

// ── Sections ──

// GetSection fetches a single section with full content.
func (c *Client) GetSection(ctx context.Context, sectionID string) (*Section, error) {
	return c.transport.GetSection(ctx, sectionID)
}

// ── Query ──

// Query retrieves the most relevant sections for a natural language query.
// The LLM navigates the document tree to find matching sections.
func (c *Client) Query(ctx context.Context, documentID, query string, opts *QueryOptions) (*QueryResponse, error) {
	return c.transport.Query(ctx, documentID, query, opts)
}

// QueryStream returns an iterator of streaming query events.
// Events arrive as the retrieval progresses: started, slice_started,
// section_selected, slice_completed, completed, error.
func (c *Client) QueryStream(ctx context.Context, documentID, query string, opts *QueryOptions) (iter.Seq2[QueryStreamEvent, error], error) {
	return c.transport.QueryStream(ctx, documentID, query, opts)
}

// ── Polling ──

// WaitForReady polls GetDocument until the document status is "ready" or "failed".
func (c *Client) WaitForReady(ctx context.Context, documentID string, opts *WaitForReadyOptions) (*Document, error) {
	timeoutMs := int64(300_000)
	pollMs := int64(2_000)
	var onProgress func(DocumentStatus)

	if opts != nil {
		if opts.TimeoutMs > 0 {
			timeoutMs = opts.TimeoutMs
		}
		if opts.PollIntervalMs > 0 {
			pollMs = opts.PollIntervalMs
		}
		onProgress = opts.OnProgress
	}

	deadline := time.Now().Add(time.Duration(timeoutMs) * time.Millisecond)

	for time.Now().Before(deadline) {
		time.Sleep(time.Duration(pollMs) * time.Millisecond)

		doc, err := c.GetDocument(ctx, documentID)
		if err != nil {
			return nil, err
		}

		if onProgress != nil {
			onProgress(doc.Status)
		}

		if doc.Status == StatusReady {
			return doc, nil
		}
		if doc.Status == StatusFailed {
			return nil, newDocumentFailedError(
				fmt.Sprintf("Document processing failed: %s", doc.ErrorMessage),
				"",
			)
		}

		// Exponential backoff capped at 10s.
		pollMs = min(pollMs*3/2, 10_000)
	}

	return nil, newTimeoutError(
		fmt.Sprintf("Document %s did not become ready within %dms", documentID, timeoutMs),
		"",
	)
}

// Close releases any resources held by the client.
func (c *Client) Close() error {
	return c.transport.Close()
}
