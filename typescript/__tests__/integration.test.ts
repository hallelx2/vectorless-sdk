/**
 * Integration tests for the Vectorless TypeScript SDK.
 *
 * Prerequisites:
 *   cd vectorless-sdk && docker compose up -d
 *
 * Run:
 *   VECTORLESS_API_KEY=vl_test_sk_1234567890abcdef npx vitest run __tests__/integration.test.ts
 */
import { describe, it, expect, beforeAll } from "vitest";
import { VectorlessClient } from "../src/index.js";
import type { TransportProtocol } from "../src/index.js";

const BASE_URL = process.env.VECTORLESS_BASE_URL ?? "http://localhost:8080";
const API_KEY = process.env.VECTORLESS_API_KEY ?? "vl_test_sk_1234567890abcdef";

const SAMPLE_MARKDOWN = `# Introduction to Machine Learning

Machine learning is a subset of artificial intelligence that enables systems to learn from data.

## Supervised Learning

Supervised learning uses labeled training data to learn a mapping function.

### Classification

Classification predicts categorical labels. Common algorithms include:
- Logistic Regression
- Decision Trees
- Support Vector Machines

### Regression

Regression predicts continuous values. Examples:
- Linear Regression
- Polynomial Regression

## Unsupervised Learning

Unsupervised learning finds hidden patterns in unlabeled data.

### Clustering

Clustering groups similar data points together.
- K-Means
- DBSCAN
- Hierarchical Clustering

### Dimensionality Reduction

Techniques like PCA reduce the number of features while preserving information.

## Deep Learning

Deep learning uses neural networks with multiple layers to learn complex representations.

### Convolutional Neural Networks

CNNs are specialized for processing grid-like data such as images.

### Recurrent Neural Networks

RNNs are designed for sequential data like text and time series.
`;

function createClient(transport: TransportProtocol): VectorlessClient {
  return new VectorlessClient({
    baseUrl: BASE_URL,
    apiKey: API_KEY,
    transport,
    timeout: 60_000,
  });
}

// Run the same test suite against both transports
for (const transport of ["http", "connect"] as TransportProtocol[]) {
  describe(`VectorlessClient [${transport} transport]`, () => {
    let client: VectorlessClient;

    beforeAll(() => {
      client = createClient(transport);
    });

    // ── Health ──

    it("health check returns ok", async () => {
      const health = await client.health();
      expect(health.status).toBe("ok");
    });

    it("version returns a string", async () => {
      const version = await client.version();
      expect(version.version).toBeTruthy();
      expect(typeof version.version).toBe("string");
    });

    // ── Document Lifecycle ──

    it("full document lifecycle: ingest → poll → tree → section → query → delete", async () => {
      // 1. Ingest
      const blob = new Blob([SAMPLE_MARKDOWN], { type: "text/markdown" });
      const ingestResult = await client.ingestDocument(blob, {
        filename: "ml-guide.md",
        metadata: { topic: "machine-learning", sdk_test: "true" },
      });

      expect(ingestResult.document_id).toBeTruthy();
      expect(ingestResult.status).toBe("pending");

      const docId = ingestResult.document_id;

      // 2. Wait for ready
      const doc = await client.waitForReady(docId, {
        timeout: 120_000,
        pollInterval: 3_000,
        onProgress: (status) => {
          console.log(`  [${transport}] Document ${docId}: ${status}`);
        },
      });

      expect(doc.status).toBe("ready");
      expect(doc.id).toBe(docId);
      expect(doc.title).toBeTruthy();

      // 3. Get document tree
      const tree = await client.getDocumentTree(docId);
      expect(tree.document_id).toBe(docId);
      expect(tree.sections.length).toBeGreaterThan(0);

      // Verify tree structure
      const rootSections = tree.sections.filter((s) => !s.parent_id);
      expect(rootSections.length).toBeGreaterThan(0);

      // Verify section has expected fields
      const firstSection = tree.sections[0];
      expect(firstSection.id).toBeTruthy();
      expect(firstSection.title).toBeTruthy();
      expect(typeof firstSection.depth).toBe("number");
      expect(typeof firstSection.tokens).toBe("number");

      // 4. Fetch a section with full content
      const section = await client.getSection(firstSection.id);
      expect(section.id).toBe(firstSection.id);
      expect(section.document_id).toBe(docId);
      expect(section.content).toBeTruthy();
      expect(typeof section.token_count).toBe("number");

      // 5. Fetch multiple sections
      const sectionIds = tree.sections.slice(0, 3).map((s) => s.id);
      const sections = await client.getSections(sectionIds);
      expect(sections.length).toBe(sectionIds.length);

      // 6. Query
      const queryResult = await client.query(docId, "What is supervised learning?");
      expect(queryResult.document_id).toBe(docId);
      expect(queryResult.query).toBe("What is supervised learning?");
      expect(queryResult.sections.length).toBeGreaterThan(0);
      expect(queryResult.strategy).toBeTruthy();
      expect(typeof queryResult.elapsed_ms).toBe("number");

      // Verify query sections have content
      for (const qs of queryResult.sections) {
        expect(qs.id).toBeTruthy();
        expect(qs.content).toBeTruthy();
      }

      // 7. List documents (should include our doc)
      const list = await client.listDocuments({ status: "ready", limit: 10 });
      expect(list.items.length).toBeGreaterThan(0);
      const found = list.items.find((d) => d.id === docId);
      expect(found).toBeTruthy();

      // 8. Delete
      await client.deleteDocument(docId);

      // 9. Verify deleted
      try {
        await client.getDocument(docId);
        expect.unreachable("Should have thrown NotFoundError");
      } catch (error: any) {
        expect(error.status).toBe(404);
      }
    }, 180_000); // 3 minute timeout for the full lifecycle

    // ── Error Handling ──

    it("returns NotFoundError for missing document", async () => {
      try {
        await client.getDocument("doc_nonexistent_12345");
        expect.unreachable("Should have thrown");
      } catch (error: any) {
        expect(error.name).toBe("NotFoundError");
        expect(error.status).toBe(404);
      }
    });

    it("returns NotFoundError for missing section", async () => {
      try {
        await client.getSection("sec_nonexistent_12345");
        expect.unreachable("Should have thrown");
      } catch (error: any) {
        expect(error.name).toBe("NotFoundError");
        expect(error.status).toBe(404);
      }
    });

    // ── Auth ──

    it("returns AuthenticationError without API key", async () => {
      const noAuthClient = new VectorlessClient({
        baseUrl: BASE_URL,
        transport,
      });

      try {
        await noAuthClient.listDocuments();
        expect.unreachable("Should have thrown");
      } catch (error: any) {
        expect(error.name).toBe("AuthenticationError");
        expect(error.status).toBe(401);
      }
    });

    it("returns AuthenticationError with wrong API key", async () => {
      const badClient = new VectorlessClient({
        baseUrl: BASE_URL,
        apiKey: "vl_wrong_key",
        transport,
      });

      try {
        await badClient.listDocuments();
        expect.unreachable("Should have thrown");
      } catch (error: any) {
        expect(error.name).toBe("AuthenticationError");
        expect(error.status).toBe(401);
      }
    });
  });
}
