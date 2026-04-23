// Package vectorless provides a Go client for the Vectorless document retrieval server.
//
// Vectorless uses structure-preserving retrieval — no embeddings, no vector databases.
// Documents are parsed into hierarchical trees, and an LLM reasons over the tree
// structure to find the most relevant sections for a query.
//
// The SDK supports two transport protocols:
//   - HTTP/REST (default) — standard REST endpoints at /v1/*
//   - ConnectRPC — protobuf JSON encoding at /{service}/{method}
//
// Both deployed instances (with API key auth) and self-hosted instances (no auth)
// are supported.
package vectorless

// ── Health ──

// HealthResponse is returned by the health check endpoint.
type HealthResponse struct {
	Status string `json:"status"`
}

// VersionResponse is returned by the version endpoint.
type VersionResponse struct {
	Version string `json:"version"`
}

// ── Documents ──

// DocumentStatus represents the processing state of a document.
type DocumentStatus string

const (
	StatusPending     DocumentStatus = "pending"
	StatusParsing     DocumentStatus = "parsing"
	StatusSummarizing DocumentStatus = "summarizing"
	StatusReady       DocumentStatus = "ready"
	StatusFailed      DocumentStatus = "failed"
)

// Document is the metadata for an ingested document.
type Document struct {
	ID           string            `json:"id"`
	Title        string            `json:"title"`
	ContentType  string            `json:"content_type"`
	Status       DocumentStatus    `json:"status"`
	ByteSize     int64             `json:"byte_size"`
	ErrorMessage string            `json:"error_message,omitempty"`
	Metadata     map[string]string `json:"metadata,omitempty"`
	CreatedAt    string            `json:"created_at"`
	UpdatedAt    string            `json:"updated_at"`
}

// IngestDocumentOptions configures a document ingestion request.
type IngestDocumentOptions struct {
	// Filename is the original filename used for format detection.
	Filename string
	// ContentType overrides MIME type auto-detection.
	ContentType string
	// Metadata is arbitrary key-value data attached to the document.
	Metadata map[string]string
	// IdempotencyKey prevents duplicate ingestion of the same document.
	IdempotencyKey string
}

// IngestDocumentResponse is returned when a document ingestion is started.
type IngestDocumentResponse struct {
	DocumentID string         `json:"document_id"`
	Status     DocumentStatus `json:"status"`
}

// ListDocumentsOptions configures a list documents request.
type ListDocumentsOptions struct {
	// Limit is the maximum number of documents to return (1-200, default 50).
	Limit int
	// Cursor is a pagination cursor from a previous response.
	Cursor string
	// Status filters documents by processing status.
	Status DocumentStatus
}

// ListDocumentsResponse is returned by the list documents endpoint.
type ListDocumentsResponse struct {
	Items      []Document `json:"items"`
	NextCursor string     `json:"next_cursor,omitempty"`
}

// ── Document Tree ──

// SectionView is a lightweight view of a section in the document tree.
// It includes structural information but not the full content.
type SectionView struct {
	ID       string   `json:"id"`
	ParentID string   `json:"parent_id,omitempty"`
	Depth    int      `json:"depth"`
	Title    string   `json:"title"`
	Summary  string   `json:"summary,omitempty"`
	Children []string `json:"children,omitempty"`
	Tokens   int      `json:"tokens"`
}

// DocumentTree is the hierarchical outline of a document.
type DocumentTree struct {
	DocumentID string        `json:"document_id"`
	Title      string        `json:"title"`
	Sections   []SectionView `json:"sections"`
}

// ── Sections ──

// Section is a document section with full content.
type Section struct {
	ID         string            `json:"id"`
	DocumentID string            `json:"document_id"`
	ParentID   string            `json:"parent_id,omitempty"`
	Ordinal    int               `json:"ordinal"`
	Depth      int               `json:"depth"`
	Title      string            `json:"title"`
	Summary    string            `json:"summary,omitempty"`
	TokenCount int               `json:"token_count"`
	Metadata   map[string]string `json:"metadata,omitempty"`
	Content    string            `json:"content"`
}

// ── Query ──

// QueryOptions configures a query request.
type QueryOptions struct {
	// Model overrides the default LLM model.
	Model string
	// MaxTokens is the maximum context window tokens (default 100,000).
	MaxTokens int
	// ReservedForPrompt is tokens reserved for the prompt (default 4,000).
	ReservedForPrompt int
	// MaxParallelCalls limits parallel LLM calls for chunked-tree (default 8).
	MaxParallelCalls int
	// MaxSections caps the number of sections returned (0 = no cap).
	MaxSections int
}

// QuerySection is a section returned by a query.
type QuerySection struct {
	ID         string `json:"id"`
	ParentID   string `json:"parent_id,omitempty"`
	Title      string `json:"title"`
	Summary    string `json:"summary,omitempty"`
	TokenCount int    `json:"token_count"`
	Content    string `json:"content"`
}

// Usage tracks LLM token usage and cost for a query.
type Usage struct {
	InputTokens  int     `json:"input_tokens"`
	OutputTokens int     `json:"output_tokens"`
	TotalTokens  int     `json:"total_tokens"`
	CostUSD      float64 `json:"cost_usd"`
	LLMCalls     int     `json:"llm_calls"`
}

// QueryResponse is the result of a document query.
type QueryResponse struct {
	DocumentID string         `json:"document_id"`
	Query      string         `json:"query"`
	Strategy   string         `json:"strategy"`
	Model      string         `json:"model"`
	Sections   []QuerySection `json:"sections"`
	ElapsedMs  int64          `json:"elapsed_ms"`
	Usage      *Usage         `json:"usage,omitempty"`
}

// ── Streaming Query ──

// QueryStreamEventType identifies the kind of streaming event.
type QueryStreamEventType string

const (
	EventStarted         QueryStreamEventType = "started"
	EventSliceStarted    QueryStreamEventType = "slice_started"
	EventSectionSelected QueryStreamEventType = "section_selected"
	EventSliceCompleted  QueryStreamEventType = "slice_completed"
	EventCompleted       QueryStreamEventType = "completed"
	EventError           QueryStreamEventType = "error"
)

// QueryStreamEvent is a single event from a streaming query.
type QueryStreamEvent struct {
	Type        QueryStreamEventType `json:"type"`
	Section     *QuerySection        `json:"section,omitempty"`
	SliceIndex  int                  `json:"slice_index,omitempty"`
	TotalSlices int                  `json:"total_slices,omitempty"`
	Message     string               `json:"message,omitempty"`
	Strategy    string               `json:"strategy,omitempty"`
	DocumentID  string               `json:"document_id,omitempty"`
	Query       string               `json:"query,omitempty"`
	ElapsedMs   int64                `json:"elapsed_ms,omitempty"`
}

// ── Wait / Polling ──

// WaitForReadyOptions configures polling behavior for waitForReady.
type WaitForReadyOptions struct {
	// TimeoutMs is the total timeout in milliseconds (default 300,000 = 5 min).
	TimeoutMs int64
	// PollIntervalMs is the initial interval between polls in milliseconds (default 2,000).
	PollIntervalMs int64
	// OnProgress is called on each poll with the current document status.
	OnProgress func(status DocumentStatus)
}
