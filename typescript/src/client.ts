import { resolveConfig, type VectorlessClientOptions, type VectorlessConfig } from "./config.js";
import type { Transport } from "./transport/interface.js";
import { HttpTransport } from "./transport/http.js";
import { ConnectTransport } from "./transport/connect.js";
import { DocumentFailedError, TimeoutError } from "./errors.js";
import type {
  HealthResponse,
  VersionResponse,
  Document,
  DocumentStatus,
  IngestDocumentOptions,
  IngestDocumentResponse,
  ListDocumentsOptions,
  ListDocumentsResponse,
  DocumentTree,
  SectionView,
  Section,
  QueryOptions,
  QueryResponse,
  QueryStreamEvent,
  WaitForReadyOptions,
} from "./types.js";

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * Vectorless SDK client.
 *
 * Provides access to all Vectorless server APIs — document ingestion,
 * tree inspection, section retrieval, and LLM-powered query.
 *
 * Supports two transport protocols:
 * - `"http"` (default) — standard REST/JSON over HTTP endpoints
 * - `"connect"` — ConnectRPC protocol (JSON encoding, native streaming)
 *
 * Works with both deployed instances (API key auth) and self-hosted
 * instances (no auth required).
 *
 * @example
 * ```ts
 * // Deployed instance with API key
 * const client = new VectorlessClient({
 *   baseUrl: "https://api.vectorless.dev",
 *   apiKey: "vl_live_...",
 * });
 *
 * // Self-hosted instance, no auth
 * const client = new VectorlessClient({
 *   baseUrl: "http://localhost:8080",
 * });
 *
 * // Using Connect protocol
 * const client = new VectorlessClient({
 *   baseUrl: "http://localhost:8080",
 *   transport: "connect",
 * });
 * ```
 */
export class VectorlessClient {
  private readonly transport: Transport;
  private readonly config: VectorlessConfig;

  constructor(options?: VectorlessClientOptions) {
    const config = resolveConfig(options);
    this.config = config;

    switch (config.transport) {
      case "connect":
        this.transport = new ConnectTransport(config);
        break;
      case "http":
      default:
        this.transport = new HttpTransport(config);
        break;
    }
  }

  // ── Health ──

  /**
   * Check server liveness.
   *
   * @returns `{ status: "ok" }` if the server is healthy.
   */
  async health(): Promise<HealthResponse> {
    return this.transport.health();
  }

  /**
   * Get the server build version.
   */
  async version(): Promise<VersionResponse> {
    return this.transport.version();
  }

  // ── Documents ──

  /**
   * Ingest a document into Vectorless.
   *
   * Accepts file paths (Node.js), Blobs, Buffers, or ArrayBuffers.
   * Returns immediately with a document ID and `"pending"` status.
   * Use {@link waitForReady} to poll until processing completes.
   *
   * @example
   * ```ts
   * const result = await client.ingestDocument("./report.pdf", {
   *   filename: "report.pdf",
   *   metadata: { team: "engineering" },
   * });
   * console.log(result.document_id); // "doc_abc123"
   *
   * // Wait until ready
   * const doc = await client.waitForReady(result.document_id);
   * ```
   */
  async ingestDocument(
    source: Buffer | ArrayBuffer | Blob | string,
    options?: IngestDocumentOptions
  ): Promise<IngestDocumentResponse> {
    return this.transport.ingestDocument(source, options);
  }

  /**
   * Get document metadata and processing status.
   */
  async getDocument(documentId: string): Promise<Document> {
    return this.transport.getDocument(documentId);
  }

  /**
   * List documents with optional filtering and cursor-based pagination.
   *
   * @example
   * ```ts
   * // List all ready documents
   * const page = await client.listDocuments({ status: "ready", limit: 20 });
   * for (const doc of page.items) {
   *   console.log(doc.title, doc.status);
   * }
   *
   * // Fetch next page
   * if (page.next_cursor) {
   *   const next = await client.listDocuments({ cursor: page.next_cursor });
   * }
   * ```
   */
  async listDocuments(
    options?: ListDocumentsOptions
  ): Promise<ListDocumentsResponse> {
    return this.transport.listDocuments(options);
  }

  /**
   * Delete a document and all its sections.
   */
  async deleteDocument(documentId: string): Promise<void> {
    return this.transport.deleteDocument(documentId);
  }

  // ── Tree & Sections ──

  /**
   * Get the hierarchical document tree.
   *
   * Returns the document's structural outline — sections with IDs,
   * titles, summaries, parent/child relationships, and token counts.
   * Does not include section content (use {@link getSection} for that).
   *
   * @example
   * ```ts
   * const tree = await client.getDocumentTree(docId);
   * for (const section of tree.sections) {
   *   console.log("  ".repeat(section.depth) + section.title);
   * }
   * ```
   */
  async getDocumentTree(documentId: string): Promise<DocumentTree> {
    return this.transport.getDocumentTree(documentId);
  }

  /**
   * Get the document rendered as an llms.txt Markdown map — H1 title, a
   * blockquote summary, and a nested section outline with one-line
   * summaries. A compact, agent-friendly index of the document.
   *
   * @returns the raw Markdown text.
   */
  async getLlmsTxt(documentId: string): Promise<string> {
    const headers: Record<string, string> = {};
    if (this.config.apiKey) headers["Authorization"] = `Bearer ${this.config.apiKey}`;
    if (this.config.store) headers["X-Vectorless-Store"] = this.config.store;
    const res = await fetch(
      `${this.config.baseUrl}/v1/documents/${documentId}/llms.txt`,
      { headers }
    );
    if (!res.ok) {
      throw new Error(`getLlmsTxt failed: ${res.status} ${await res.text()}`);
    }
    return res.text();
  }

  /**
   * Fetch a single section with full content.
   *
   * @example
   * ```ts
   * const section = await client.getSection("sec_abc123");
   * console.log(section.title, section.content);
   * ```
   */
  async getSection(sectionId: string): Promise<Section> {
    return this.transport.getSection(sectionId);
  }

  /**
   * Fetch multiple sections in parallel.
   *
   * Convenience method that fires concurrent {@link getSection} calls.
   * Returns sections in the order they resolve (not input order).
   * Use `section.ordinal` to sort by document order if needed.
   */
  async getSections(sectionIds: string[]): Promise<Section[]> {
    return Promise.all(
      sectionIds.map((id) => this.transport.getSection(id))
    );
  }

  // ── Query ──

  /**
   * Query a document — the LLM navigates the document tree to find
   * the most relevant sections for your question.
   *
   * Returns the selected sections with full content, the retrieval
   * strategy used, and token usage/cost information.
   *
   * @example
   * ```ts
   * const result = await client.query(docId, "How does authentication work?");
   * for (const section of result.sections) {
   *   console.log(`[${section.title}]`, section.content);
   * }
   * console.log(`Strategy: ${result.strategy}, Cost: $${result.usage?.cost_usd}`);
   * ```
   */
  async query(
    documentId: string,
    query: string,
    options?: QueryOptions
  ): Promise<QueryResponse> {
    return this.transport.query(documentId, query, options);
  }

  /**
   * Stream query results in real-time.
   *
   * Returns an async iterable of events as the retrieval progresses:
   * - `started` — retrieval strategy selected
   * - `slice_started` — processing a tree slice (chunked-tree strategy)
   * - `section_selected` — a relevant section was found
   * - `slice_completed` — finished processing a tree slice
   * - `completed` — all sections retrieved
   * - `error` — something went wrong
   *
   * Uses SSE (HTTP transport) or Connect streaming (Connect transport).
   *
   * @example
   * ```ts
   * for await (const event of client.queryStream(docId, "What is X?")) {
   *   if (event.type === "section_selected" && event.section) {
   *     console.log(`Found: ${event.section.title}`);
   *   }
   *   if (event.type === "completed") {
   *     console.log(`Done in ${event.elapsed_ms}ms`);
   *   }
   * }
   * ```
   */
  queryStream(
    documentId: string,
    query: string,
    options?: QueryOptions
  ): AsyncIterable<QueryStreamEvent> {
    return this.transport.queryStream(documentId, query, options);
  }

  // ── Polling ──

  /**
   * Wait for a document to finish processing.
   *
   * Polls {@link getDocument} with exponential backoff until the document
   * status is `"ready"` or `"failed"`.
   *
   * @throws {DocumentFailedError} if the document fails processing
   * @throws {TimeoutError} if the timeout is exceeded
   *
   * @example
   * ```ts
   * const result = await client.ingestDocument("./paper.pdf");
   * const doc = await client.waitForReady(result.document_id, {
   *   timeout: 120_000,
   *   onProgress: (status) => console.log(`Status: ${status}`),
   * });
   * ```
   */
  async waitForReady(
    documentId: string,
    options?: WaitForReadyOptions
  ): Promise<Document> {
    const maxWait = options?.timeout ?? 300_000;
    let pollInterval = options?.pollInterval ?? 2_000;
    const deadline = Date.now() + maxWait;

    while (Date.now() < deadline) {
      await sleep(pollInterval);

      const doc = await this.getDocument(documentId);

      options?.onProgress?.(doc.status);

      if (doc.status === "ready") {
        return doc;
      }

      if (doc.status === "failed") {
        throw new DocumentFailedError(
          `Document processing failed: ${doc.error_message || "Unknown error"}`
        );
      }

      // Exponential backoff capped at 10 seconds
      pollInterval = Math.min(pollInterval * 1.5, 10_000);
    }

    throw new TimeoutError(
      `Document ${documentId} did not become ready within ${maxWait}ms`
    );
  }

  // ── Lifecycle ──

  /**
   * Close the client and release any resources.
   */
  async close(): Promise<void> {
    return this.transport.close();
  }
}
