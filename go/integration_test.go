//go:build integration
// +build integration

package vectorless_test

import (
	"context"
	"os"
	"strings"
	"testing"

	"github.com/hallelx2/vectorless-sdk/go"
	_ "github.com/hallelx2/vectorless-sdk/go/transport"
)

func TestIntegration_RealEngine(t *testing.T) {
	baseURL := os.Getenv("VECTORLESS_BASE_URL")
	if baseURL == "" {
		t.Skip("VECTORLESS_BASE_URL is not set, skipping integration test")
	}

	apiKey := os.Getenv("VECTORLESS_API_KEY") // could be empty for self-hosted

	t.Logf("Running integration test against %s", baseURL)

	ctx := context.Background()
	client, err := vectorless.NewClient(
		vectorless.WithBaseURL(baseURL),
		vectorless.WithAPIKey(apiKey),
		vectorless.WithTransport(vectorless.TransportHTTP), // We can test HTTP transport
	)
	if err != nil {
		t.Fatalf("Failed to create client: %v", err)
	}
	defer client.Close()

	// 1. Health check
	health, err := client.Health(ctx)
	if err != nil {
		t.Fatalf("Health check failed: %v", err)
	}
	if health.Status != "ok" {
		t.Errorf("Unexpected health status: %q", health.Status)
	}

	// 2. Ingest document
	content := "This is a test document. It contains information about testing integration. The integration test is successful if this document is ingested and ready."
	docReader := strings.NewReader(content)

	ingestRes, err := client.IngestDocument(ctx, docReader, vectorless.IngestDocumentOptions{
		Filename: "integration_test.txt",
		ContentType: "text/plain",
	})
	if err != nil {
		t.Fatalf("Failed to ingest document: %v", err)
	}

	docID := ingestRes.DocumentID
	t.Logf("Ingested document ID: %s", docID)

	// Clean up at the end
	defer func() {
		t.Logf("Cleaning up document %s", docID)
		err := client.DeleteDocument(context.Background(), docID)
		if err != nil {
			t.Logf("Warning: failed to delete document during cleanup: %v", err)
		}
	}()

	// 3. Wait for ready
	opts := &vectorless.WaitForReadyOptions{
		TimeoutMs: 60000, // 60 seconds should be plenty for a short text file
		PollIntervalMs: 1000,
		OnProgress: func(s vectorless.DocumentStatus) {
			t.Logf("Document status: %s", s)
		},
	}

	doc, err := client.WaitForReady(ctx, docID, opts)
	if err != nil {
		t.Fatalf("Wait for ready failed: %v", err)
	}

	if doc.Status != vectorless.StatusReady {
		t.Fatalf("Expected status ready, got %s. Error: %s", doc.Status, doc.ErrorMessage)
	}

	// 4. Query
	queryRes, err := client.Query(ctx, docID, "What is this document about?", nil)
	if err != nil {
		t.Fatalf("Query failed: %v", err)
	}

	if len(queryRes.Sections) == 0 {
		t.Errorf("Expected at least one section in query response")
	}

	// 5. Delete document (also covered by defer, but we test the explicit call)
	err = client.DeleteDocument(ctx, docID)
	if err != nil {
		t.Fatalf("Failed to delete document: %v", err)
	}

	// Ensure document is not found
	_, err = client.GetDocument(ctx, docID)
	if err == nil {
		t.Errorf("Expected error getting deleted document, got nil")
	} else if !vectorless.IsNotFound(err) {
		t.Errorf("Expected IsNotFound error, got: %v", err)
	}
}
