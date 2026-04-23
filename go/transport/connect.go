package transport

import (
	"bufio"
	"bytes"
	"context"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"io"
	"iter"
	"net/http"
	"strings"
	"time"

	vectorless "github.com/hallelx2/vectorless-sdk/go"
)

// ConnectTransport implements Transport over the ConnectRPC JSON protocol.
//
// Every call is a POST to /{package}.{service}/{method} with
// Content-Type: application/json. No protobuf tooling required.
type ConnectTransport struct {
	client  *http.Client
	baseURL string
	apiKey  string
}

// NewConnectTransport creates a new ConnectRPC transport.
func NewConnectTransport(cfg vectorless.Config) *ConnectTransport {
	return &ConnectTransport{
		client: &http.Client{
			Timeout: time.Duration(cfg.TimeoutMs) * time.Millisecond,
		},
		baseURL: strings.TrimRight(cfg.BaseURL, "/"),
		apiKey:  cfg.APIKey,
	}
}

// ── Health ──

func (t *ConnectTransport) Health(ctx context.Context) (*vectorless.HealthResponse, error) {
	var out vectorless.HealthResponse
	if err := t.unary(ctx, "vectorless.v1.HealthService", "Check", map[string]any{}, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

func (t *ConnectTransport) Version(ctx context.Context) (*vectorless.VersionResponse, error) {
	var out vectorless.VersionResponse
	if err := t.unary(ctx, "vectorless.v1.HealthService", "Version", map[string]any{}, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

// ── Documents ──

func (t *ConnectTransport) IngestDocument(ctx context.Context, body io.Reader, opts vectorless.IngestDocumentOptions) (*vectorless.IngestDocumentResponse, error) {
	raw, err := io.ReadAll(body)
	if err != nil {
		return nil, fmt.Errorf("vectorless: read body: %w", err)
	}

	filename := opts.Filename
	if filename == "" {
		filename = "document"
	}
	contentType := opts.ContentType
	if contentType == "" {
		contentType = "application/octet-stream"
	}
	metadata := opts.Metadata
	if metadata == nil {
		metadata = map[string]string{}
	}

	payload := map[string]any{
		"content":      base64.StdEncoding.EncodeToString(raw),
		"filename":     filename,
		"content_type": contentType,
		"metadata":     metadata,
	}

	var out vectorless.IngestDocumentResponse
	if err := t.unary(ctx, "vectorless.v1.DocumentsService", "CreateDocument", payload, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

func (t *ConnectTransport) GetDocument(ctx context.Context, documentID string) (*vectorless.Document, error) {
	var out vectorless.Document
	if err := t.unary(ctx, "vectorless.v1.DocumentsService", "GetDocument", map[string]any{"document_id": documentID}, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

func (t *ConnectTransport) ListDocuments(ctx context.Context, opts vectorless.ListDocumentsOptions) (*vectorless.ListDocumentsResponse, error) {
	req := map[string]any{}
	if opts.Limit > 0 {
		req["limit"] = opts.Limit
	}
	if opts.Cursor != "" {
		req["cursor"] = opts.Cursor
	}
	if opts.Status != "" {
		req["status"] = string(opts.Status)
	}

	// Connect returns {documents: [...]} but our type uses {items: [...]}.
	var raw struct {
		Documents  []vectorless.Document `json:"documents"`
		NextCursor string                `json:"next_cursor,omitempty"`
	}
	if err := t.unary(ctx, "vectorless.v1.DocumentsService", "ListDocuments", req, &raw); err != nil {
		return nil, err
	}
	return &vectorless.ListDocumentsResponse{Items: raw.Documents, NextCursor: raw.NextCursor}, nil
}

func (t *ConnectTransport) DeleteDocument(ctx context.Context, documentID string) error {
	return t.unary(ctx, "vectorless.v1.DocumentsService", "DeleteDocument", map[string]any{"document_id": documentID}, nil)
}

func (t *ConnectTransport) GetDocumentTree(ctx context.Context, documentID string) (*vectorless.DocumentTree, error) {
	var out vectorless.DocumentTree
	if err := t.unary(ctx, "vectorless.v1.DocumentsService", "GetDocumentTree", map[string]any{"document_id": documentID}, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

// ── Sections ──

func (t *ConnectTransport) GetSection(ctx context.Context, sectionID string) (*vectorless.Section, error) {
	var out vectorless.Section
	if err := t.unary(ctx, "vectorless.v1.DocumentsService", "GetSection", map[string]any{"section_id": sectionID}, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

// ── Query ──

func (t *ConnectTransport) Query(ctx context.Context, documentID, query string, opts *vectorless.QueryOptions) (*vectorless.QueryResponse, error) {
	body := buildQueryBody(documentID, query, opts)

	var out vectorless.QueryResponse
	if err := t.unary(ctx, "vectorless.v1.QueryService", "Query", body, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

func (t *ConnectTransport) QueryStream(ctx context.Context, documentID, query string, opts *vectorless.QueryOptions) (iter.Seq2[vectorless.QueryStreamEvent, error], error) {
	body := buildQueryBody(documentID, query, opts)
	jsonBody, err := json.Marshal(body)
	if err != nil {
		return nil, err
	}

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, t.baseURL+"/vectorless.v1.QueryService/QueryStream", bytes.NewReader(jsonBody))
	if err != nil {
		return nil, err
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Connect-Protocol-Version", "1")
	t.setHeaders(req)

	resp, err := t.client.Do(req)
	if err != nil {
		return nil, err
	}

	if resp.StatusCode >= 400 {
		defer resp.Body.Close()
		return nil, parseConnectError(resp)
	}

	return func(yield func(vectorless.QueryStreamEvent, error) bool) {
		defer resp.Body.Close()
		scanner := bufio.NewScanner(resp.Body)

		for scanner.Scan() {
			line := strings.TrimSpace(scanner.Text())
			if line == "" {
				continue
			}

			var envelope struct {
				Result *vectorless.QueryStreamEvent `json:"result,omitempty"`
				Error  *struct {
					Code    string `json:"code"`
					Message string `json:"message"`
				} `json:"error,omitempty"`
			}
			if err := json.Unmarshal([]byte(line), &envelope); err != nil {
				if !yield(vectorless.QueryStreamEvent{}, err) {
					return
				}
				continue
			}
			if envelope.Error != nil {
				yield(vectorless.QueryStreamEvent{}, &vectorless.Error{
					Message: envelope.Error.Message,
					Status:  500,
					Code:    envelope.Error.Code,
				})
				return
			}
			if envelope.Result != nil {
				if !yield(*envelope.Result, nil) {
					return
				}
			}
		}
		if err := scanner.Err(); err != nil {
			yield(vectorless.QueryStreamEvent{}, err)
		}
	}, nil
}

// ── Lifecycle ──

func (t *ConnectTransport) Close() error {
	t.client.CloseIdleConnections()
	return nil
}

// ── Internal ──

func (t *ConnectTransport) setHeaders(req *http.Request) {
	req.Header.Set("User-Agent", "vectorless-go/"+sdkVersion)
	if t.apiKey != "" {
		req.Header.Set("Authorization", "Bearer "+t.apiKey)
	}
}

func (t *ConnectTransport) unary(ctx context.Context, service, method string, request any, out any) error {
	jsonBody, err := json.Marshal(request)
	if err != nil {
		return err
	}

	u := fmt.Sprintf("%s/%s/%s", t.baseURL, service, method)
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, u, bytes.NewReader(jsonBody))
	if err != nil {
		return err
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Connect-Protocol-Version", "1")
	t.setHeaders(req)

	resp, err := t.client.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()

	if resp.StatusCode >= 400 {
		return parseConnectError(resp)
	}

	if out == nil {
		return nil
	}
	return json.NewDecoder(resp.Body).Decode(out)
}

func parseConnectError(resp *http.Response) *vectorless.Error {
	requestID := resp.Header.Get("X-Request-ID")
	message := fmt.Sprintf("RPC failed with HTTP %d", resp.StatusCode)
	code := "unknown"

	var body struct {
		Code    string `json:"code"`
		Message string `json:"message"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&body); err == nil {
		if body.Message != "" {
			message = body.Message
		}
		if body.Code != "" {
			code = body.Code
		}
	}

	codeMap := map[string]int{
		"unauthenticated":   401,
		"permission_denied": 403,
		"not_found":         404,
		"invalid_argument":  400,
		"already_exists":    409,
		"resource_exhausted": 429,
		"deadline_exceeded": 408,
		"internal":          500,
		"unavailable":       503,
		"data_loss":         500,
	}

	if status, ok := codeMap[code]; ok {
		return &vectorless.Error{Message: message, Status: status, Code: code, RequestID: requestID}
	}
	return &vectorless.Error{Message: message, Status: resp.StatusCode, Code: code, RequestID: requestID}
}
