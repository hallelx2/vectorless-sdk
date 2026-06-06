package vectorless_test

import (
	"context"
	"fmt"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/hallelx2/vectorless-sdk/go"
	_ "github.com/hallelx2/vectorless-sdk/go/transport"
)

// mockServer creates an httptest server that handles both HTTP and ConnectRPC requests.
func mockServer(t *testing.T) *httptest.Server {
	mux := http.NewServeMux()

	// --- HTTP Transport Routes ---
	mux.HandleFunc("/v1/health", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		fmt.Fprint(w, `{"status": "ok"}`)
	})

	mux.HandleFunc("/v1/version", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		fmt.Fprint(w, `{"version": "1.2.3"}`)
	})

	mux.HandleFunc("/v1/documents", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		if r.Method == http.MethodPost {
			fmt.Fprint(w, `{"document_id": "doc_123", "status": "pending"}`)
		} else if r.Method == http.MethodGet {
			fmt.Fprint(w, `{"items": [{"id": "doc_123", "title": "Test Doc"}]}`)
		}
	})

	mux.HandleFunc("/v1/documents/doc_123", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		if r.Method == http.MethodGet {
			fmt.Fprint(w, `{"id": "doc_123", "title": "Test Doc", "status": "ready"}`)
		} else if r.Method == http.MethodDelete {
			w.WriteHeader(http.StatusNoContent)
		}
	})

	mux.HandleFunc("/v1/documents/doc_123/tree", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		fmt.Fprint(w, `{"document_id": "doc_123", "title": "Test Doc", "sections": []}`)
	})

	mux.HandleFunc("/v1/documents/doc_123/llms.txt", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "text/plain")
		fmt.Fprint(w, `# Test Doc`)
	})

	mux.HandleFunc("/v1/sections/sec_123", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		fmt.Fprint(w, `{"id": "sec_123", "content": "Test content"}`)
	})

	mux.HandleFunc("/v1/query", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		fmt.Fprint(w, `{"document_id": "doc_123", "query": "test", "sections": [{"id": "sec_1"}]}`)
	})

	mux.HandleFunc("/v1/query/stream", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "text/event-stream")
		fmt.Fprint(w, "event: started\ndata: {\"strategy\": \"tree\"}\n\n")
		fmt.Fprint(w, "event: completed\ndata: {\"elapsed_ms\": 100}\n\n")
	})

	// --- ConnectRPC Transport Routes ---
	mux.HandleFunc("/vectorless.v1.HealthService/Check", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		fmt.Fprint(w, `{"status": "ok"}`)
	})

	mux.HandleFunc("/vectorless.v1.HealthService/Version", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		fmt.Fprint(w, `{"version": "1.2.3"}`)
	})

	mux.HandleFunc("/vectorless.v1.DocumentsService/CreateDocument", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		fmt.Fprint(w, `{"document_id": "doc_123", "status": "pending"}`)
	})

	mux.HandleFunc("/vectorless.v1.DocumentsService/GetDocument", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		fmt.Fprint(w, `{"id": "doc_123", "title": "Test Doc", "status": "ready"}`)
	})

	mux.HandleFunc("/vectorless.v1.DocumentsService/ListDocuments", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		fmt.Fprint(w, `{"documents": [{"id": "doc_123", "title": "Test Doc"}]}`)
	})

	mux.HandleFunc("/vectorless.v1.DocumentsService/DeleteDocument", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		fmt.Fprint(w, `{}`) // ConnectRPC returns empty JSON for void methods
	})

	mux.HandleFunc("/vectorless.v1.DocumentsService/GetDocumentTree", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		fmt.Fprint(w, `{"document_id": "doc_123", "title": "Test Doc", "sections": []}`)
	})

	mux.HandleFunc("/vectorless.v1.DocumentsService/GetSection", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		fmt.Fprint(w, `{"id": "sec_123", "content": "Test content"}`)
	})

	mux.HandleFunc("/vectorless.v1.QueryService/Query", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		fmt.Fprint(w, `{"document_id": "doc_123", "query": "test", "sections": [{"id": "sec_1"}]}`)
	})

	mux.HandleFunc("/vectorless.v1.QueryService/QueryStream", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		// ConnectRPC NDJSON streaming
		fmt.Fprint(w, `{"result": {"type": "started", "strategy": "tree"}}`+"\n")
		fmt.Fprint(w, `{"result": {"type": "completed", "elapsed_ms": 100}}`+"\n")
	})

	return httptest.NewServer(mux)
}

func testClient(t *testing.T, ts *httptest.Server, proto vectorless.TransportProtocol) *vectorless.Client {
	client, err := vectorless.NewClient(
		vectorless.WithBaseURL(ts.URL),
		vectorless.WithTransport(proto),
	)
	if err != nil {
		t.Fatalf("Failed to create client: %v", err)
	}
	return client
}

func runTests(t *testing.T, proto vectorless.TransportProtocol) {
	ts := mockServer(t)
	defer ts.Close()

	ctx := context.Background()
	client := testClient(t, ts, proto)
	defer client.Close()

	t.Run("Health", func(t *testing.T) {
		res, err := client.Health(ctx)
		if err != nil {
			t.Fatalf("Health failed: %v", err)
		}
		if res.Status != "ok" {
			t.Errorf("Expected status 'ok', got %q", res.Status)
		}
	})

	t.Run("Version", func(t *testing.T) {
		res, err := client.Version(ctx)
		if err != nil {
			t.Fatalf("Version failed: %v", err)
		}
		if res.Version != "1.2.3" {
			t.Errorf("Expected version '1.2.3', got %q", res.Version)
		}
	})

	t.Run("IngestDocument", func(t *testing.T) {
		body := strings.NewReader("hello world")
		res, err := client.IngestDocument(ctx, body, vectorless.IngestDocumentOptions{})
		if err != nil {
			t.Fatalf("IngestDocument failed: %v", err)
		}
		if res.DocumentID != "doc_123" {
			t.Errorf("Expected document ID 'doc_123', got %q", res.DocumentID)
		}
	})

	t.Run("GetDocument", func(t *testing.T) {
		res, err := client.GetDocument(ctx, "doc_123")
		if err != nil {
			t.Fatalf("GetDocument failed: %v", err)
		}
		if res.ID != "doc_123" {
			t.Errorf("Expected document ID 'doc_123', got %q", res.ID)
		}
	})

	t.Run("ListDocuments", func(t *testing.T) {
		res, err := client.ListDocuments(ctx, vectorless.ListDocumentsOptions{})
		if err != nil {
			t.Fatalf("ListDocuments failed: %v", err)
		}
		if len(res.Items) != 1 || res.Items[0].ID != "doc_123" {
			t.Errorf("Expected list to contain doc_123")
		}
	})

	t.Run("DeleteDocument", func(t *testing.T) {
		err := client.DeleteDocument(ctx, "doc_123")
		if err != nil {
			t.Fatalf("DeleteDocument failed: %v", err)
		}
	})

	t.Run("GetDocumentTree", func(t *testing.T) {
		res, err := client.GetDocumentTree(ctx, "doc_123")
		if err != nil {
			t.Fatalf("GetDocumentTree failed: %v", err)
		}
		if res.DocumentID != "doc_123" {
			t.Errorf("Expected document ID 'doc_123', got %q", res.DocumentID)
		}
	})

	t.Run("GetLLMSTxt", func(t *testing.T) {
		// Only test this for HTTP as ConnectRPC doesn't provide this specific endpoint natively in its RPC mapping in the client
		if proto == vectorless.TransportHTTP {
			res, err := client.GetLLMSTxt(ctx, "doc_123")
			if err != nil {
				t.Fatalf("GetLLMSTxt failed: %v", err)
			}
			if !strings.Contains(res, "Test Doc") {
				t.Errorf("Expected content to contain 'Test Doc', got %q", res)
			}
		}
	})

	t.Run("GetSection", func(t *testing.T) {
		res, err := client.GetSection(ctx, "sec_123")
		if err != nil {
			t.Fatalf("GetSection failed: %v", err)
		}
		if res.ID != "sec_123" {
			t.Errorf("Expected section ID 'sec_123', got %q", res.ID)
		}
	})

	t.Run("Query", func(t *testing.T) {
		res, err := client.Query(ctx, "doc_123", "test query", nil)
		if err != nil {
			t.Fatalf("Query failed: %v", err)
		}
		if res.DocumentID != "doc_123" {
			t.Errorf("Expected doc_123, got %q", res.DocumentID)
		}
		if len(res.Sections) != 1 {
			t.Errorf("Expected 1 section, got %d", len(res.Sections))
		}
	})


	t.Run("WaitForReady", func(t *testing.T) {
		opts := &vectorless.WaitForReadyOptions{
			TimeoutMs:      1000,
			PollIntervalMs: 10,
		}
		res, err := client.WaitForReady(ctx, "doc_123", opts)
		if err != nil {
			t.Fatalf("WaitForReady failed: %v", err)
		}
		if res.ID != "doc_123" || res.Status != vectorless.StatusReady {
			t.Errorf("Expected ready doc_123, got %v", res)
		}
	})

	t.Run("QueryStream", func(t *testing.T) {
		stream, err := client.QueryStream(ctx, "doc_123", "test query", nil)
		if err != nil {
			t.Fatalf("QueryStream failed: %v", err)
		}

		var events []vectorless.QueryStreamEvent
		for event, err := range stream {
			if err != nil {
				t.Fatalf("Stream error: %v", err)
			}
			events = append(events, event)
		}

		if len(events) != 2 {
			t.Fatalf("Expected 2 stream events, got %d", len(events))
		}
		if events[0].Type != vectorless.EventStarted {
			t.Errorf("Expected EventStarted, got %q", events[0].Type)
		}
		if events[1].Type != vectorless.EventCompleted {
			t.Errorf("Expected EventCompleted, got %q", events[1].Type)
		}
	})
}

func TestClient_HTTP(t *testing.T) {
	runTests(t, vectorless.TransportHTTP)
}

func TestClient_ConnectRPC(t *testing.T) {
	runTests(t, vectorless.TransportConnect)
}
