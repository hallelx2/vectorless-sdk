package transport

import (
	"bufio"
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"iter"
	"mime/multipart"
	"net/http"
	"net/url"
	"strconv"
	"strings"
	"time"

	vectorless "github.com/hallelx2/vectorless-sdk/go"
)

const sdkVersion = "1.0.0"

// HTTPTransport implements Transport over standard REST/JSON endpoints.
type HTTPTransport struct {
	client  *http.Client
	baseURL string
	apiKey  string
	store   string
}

// NewHTTPTransport creates a new HTTP/REST transport.
func NewHTTPTransport(cfg vectorless.Config) *HTTPTransport {
	return &HTTPTransport{
		client: &http.Client{
			Timeout: time.Duration(cfg.TimeoutMs) * time.Millisecond,
		},
		baseURL: strings.TrimRight(cfg.BaseURL, "/"),
		apiKey:  cfg.APIKey,
		store:   cfg.Store,
	}
}

// ── Health ──

func (t *HTTPTransport) Health(ctx context.Context) (*vectorless.HealthResponse, error) {
	var out vectorless.HealthResponse
	if err := t.get(ctx, "/v1/health", nil, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

func (t *HTTPTransport) Version(ctx context.Context) (*vectorless.VersionResponse, error) {
	var out vectorless.VersionResponse
	if err := t.get(ctx, "/v1/version", nil, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

// ── Documents ──

func (t *HTTPTransport) IngestDocument(ctx context.Context, body io.Reader, opts vectorless.IngestDocumentOptions) (*vectorless.IngestDocumentResponse, error) {
	var buf bytes.Buffer
	w := multipart.NewWriter(&buf)

	filename := opts.Filename
	if filename == "" {
		filename = "document"
	}

	part, err := w.CreateFormFile("file", filename)
	if err != nil {
		return nil, fmt.Errorf("vectorless: create form file: %w", err)
	}
	if _, err := io.Copy(part, body); err != nil {
		return nil, fmt.Errorf("vectorless: copy body: %w", err)
	}

	if opts.ContentType != "" {
		_ = w.WriteField("content_type", opts.ContentType)
	}
	for k, v := range opts.Metadata {
		_ = w.WriteField(fmt.Sprintf("metadata[%s]", k), v)
	}
	w.Close()

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, t.baseURL+"/v1/documents", &buf)
	if err != nil {
		return nil, err
	}
	req.Header.Set("Content-Type", w.FormDataContentType())
	t.setHeaders(req)

	if opts.IdempotencyKey != "" {
		req.Header.Set("Idempotency-Key", opts.IdempotencyKey)
	}

	var out vectorless.IngestDocumentResponse
	if err := t.doJSON(req, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

func (t *HTTPTransport) GetDocument(ctx context.Context, documentID string) (*vectorless.Document, error) {
	var out vectorless.Document
	if err := t.get(ctx, "/v1/documents/"+documentID, nil, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

func (t *HTTPTransport) ListDocuments(ctx context.Context, opts vectorless.ListDocumentsOptions) (*vectorless.ListDocumentsResponse, error) {
	params := url.Values{}
	if opts.Limit > 0 {
		params.Set("limit", strconv.Itoa(opts.Limit))
	}
	if opts.Cursor != "" {
		params.Set("cursor", opts.Cursor)
	}
	if opts.Status != "" {
		params.Set("status", string(opts.Status))
	}

	var out vectorless.ListDocumentsResponse
	if err := t.get(ctx, "/v1/documents", params, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

func (t *HTTPTransport) DeleteDocument(ctx context.Context, documentID string) error {
	req, err := http.NewRequestWithContext(ctx, http.MethodDelete, t.baseURL+"/v1/documents/"+documentID, nil)
	if err != nil {
		return err
	}
	t.setHeaders(req)
	return t.doJSON(req, nil)
}

func (t *HTTPTransport) GetDocumentTree(ctx context.Context, documentID string) (*vectorless.DocumentTree, error) {
	var out vectorless.DocumentTree
	if err := t.get(ctx, "/v1/documents/"+documentID+"/tree", nil, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

// ── Sections ──

func (t *HTTPTransport) GetSection(ctx context.Context, sectionID string) (*vectorless.Section, error) {
	var out vectorless.Section
	if err := t.get(ctx, "/v1/sections/"+sectionID, nil, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

// ── Query ──

func (t *HTTPTransport) Query(ctx context.Context, documentID, query string, opts *vectorless.QueryOptions) (*vectorless.QueryResponse, error) {
	body := buildQueryBody(documentID, query, opts)

	var out vectorless.QueryResponse
	if err := t.postJSON(ctx, "/v1/query", body, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

func (t *HTTPTransport) QueryStream(ctx context.Context, documentID, query string, opts *vectorless.QueryOptions) (iter.Seq2[vectorless.QueryStreamEvent, error], error) {
	body := buildQueryBody(documentID, query, opts)

	jsonBody, err := json.Marshal(body)
	if err != nil {
		return nil, err
	}

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, t.baseURL+"/v1/query/stream", bytes.NewReader(jsonBody))
	if err != nil {
		return nil, err
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Accept", "text/event-stream")
	t.setHeaders(req)

	resp, err := t.client.Do(req)
	if err != nil {
		return nil, err
	}

	if resp.StatusCode >= 400 {
		defer resp.Body.Close()
		return nil, parseHTTPError(resp)
	}

	return func(yield func(vectorless.QueryStreamEvent, error) bool) {
		defer resp.Body.Close()
		scanner := bufio.NewScanner(resp.Body)

		var eventType string
		for scanner.Scan() {
			line := scanner.Text()
			if strings.HasPrefix(line, "event:") {
				eventType = strings.TrimSpace(line[6:])
			} else if strings.HasPrefix(line, "data:") {
				data := strings.TrimSpace(line[5:])
				var event vectorless.QueryStreamEvent
				if err := json.Unmarshal([]byte(data), &event); err != nil {
					if !yield(vectorless.QueryStreamEvent{}, err) {
						return
					}
					continue
				}
				if eventType != "" && event.Type == "" {
					event.Type = vectorless.QueryStreamEventType(eventType)
				}
				eventType = ""
				if !yield(event, nil) {
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

func (t *HTTPTransport) Close() error {
	t.client.CloseIdleConnections()
	return nil
}

// ── Internal ──

func (t *HTTPTransport) setHeaders(req *http.Request) {
	req.Header.Set("User-Agent", "vectorless-go/"+sdkVersion)
	if t.apiKey != "" {
		req.Header.Set("Authorization", "Bearer "+t.apiKey)
	}
	if t.store != "" {
		req.Header.Set("X-Vectorless-Store", t.store)
	}
}

func (t *HTTPTransport) get(ctx context.Context, path string, params url.Values, out any) error {
	u := t.baseURL + path
	if len(params) > 0 {
		u += "?" + params.Encode()
	}

	req, err := http.NewRequestWithContext(ctx, http.MethodGet, u, nil)
	if err != nil {
		return err
	}
	t.setHeaders(req)
	return t.doJSON(req, out)
}

func (t *HTTPTransport) postJSON(ctx context.Context, path string, body any, out any) error {
	jsonBody, err := json.Marshal(body)
	if err != nil {
		return err
	}

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, t.baseURL+path, bytes.NewReader(jsonBody))
	if err != nil {
		return err
	}
	req.Header.Set("Content-Type", "application/json")
	t.setHeaders(req)
	return t.doJSON(req, out)
}

func (t *HTTPTransport) doJSON(req *http.Request, out any) error {
	resp, err := t.client.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()

	if resp.StatusCode >= 400 {
		return parseHTTPError(resp)
	}

	if resp.StatusCode == 204 || out == nil {
		return nil
	}

	return json.NewDecoder(resp.Body).Decode(out)
}

func parseHTTPError(resp *http.Response) *vectorless.Error {
	requestID := resp.Header.Get("X-Request-ID")

	var body struct {
		Error any `json:"error"`
	}
	message := fmt.Sprintf("Request failed with status %d", resp.StatusCode)

	if err := json.NewDecoder(resp.Body).Decode(&body); err == nil {
		switch v := body.Error.(type) {
		case string:
			message = v
		case map[string]any:
			if m, ok := v["message"].(string); ok {
				message = m
			}
		}
	}

	switch resp.StatusCode {
	case 400:
		return &vectorless.Error{Message: message, Status: 400, Code: "validation_error", RequestID: requestID}
	case 401:
		return &vectorless.Error{Message: message, Status: 401, Code: "authentication_error", RequestID: requestID}
	case 403:
		return &vectorless.Error{Message: message, Status: 403, Code: "permission_denied", RequestID: requestID}
	case 404:
		return &vectorless.Error{Message: message, Status: 404, Code: "not_found", RequestID: requestID}
	case 409:
		return &vectorless.Error{Message: message, Status: 409, Code: "conflict", RequestID: requestID}
	case 429:
		return &vectorless.Error{Message: message, Status: 429, Code: "rate_limit_exceeded", RequestID: requestID}
	case 408, 504:
		return &vectorless.Error{Message: message, Status: resp.StatusCode, Code: "timeout", RequestID: requestID}
	default:
		if resp.StatusCode >= 500 {
			return &vectorless.Error{Message: message, Status: resp.StatusCode, Code: "server_error", RequestID: requestID}
		}
		return &vectorless.Error{Message: message, Status: resp.StatusCode, Code: "unknown", RequestID: requestID}
	}
}

func buildQueryBody(documentID, query string, opts *vectorless.QueryOptions) map[string]any {
	body := map[string]any{
		"document_id": documentID,
		"query":       query,
	}
	if opts != nil {
		if opts.Model != "" {
			body["model"] = opts.Model
		}
		if opts.MaxTokens > 0 {
			body["max_tokens"] = opts.MaxTokens
		}
		if opts.ReservedForPrompt > 0 {
			body["reserved_for_prompt"] = opts.ReservedForPrompt
		}
		if opts.MaxParallelCalls > 0 {
			body["max_parallel_calls"] = opts.MaxParallelCalls
		}
		if opts.MaxSections > 0 {
			body["max_sections"] = opts.MaxSections
		}
	}
	return body
}
