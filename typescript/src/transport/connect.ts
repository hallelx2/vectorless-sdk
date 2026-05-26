import type { VectorlessConfig } from "../config.js";
import type { Transport } from "./interface.js";
import type {
  HealthResponse,
  VersionResponse,
  Document,
  IngestDocumentOptions,
  IngestDocumentResponse,
  ListDocumentsOptions,
  ListDocumentsResponse,
  DocumentTree,
  Section,
  QueryOptions,
  QueryResponse,
  QueryStreamEvent,
} from "../types.js";
import { withRetry } from "../retry.js";
import { prepareJsonPayload } from "../upload.js";
import {
  VectorlessError,
  AuthenticationError,
  PermissionDeniedError,
  NotFoundError,
  RateLimitError,
  ValidationError,
  ConflictError,
  ServerError,
  TimeoutError,
  StreamError,
} from "../errors.js";

const SDK_VERSION = "1.0.0";

/**
 * Connect/Protobuf transport.
 *
 * Uses the ConnectRPC JSON protocol — every call is a POST to
 *   /{package}.{service}/{method}
 * with `Content-Type: application/json`.
 *
 * No code generation or protobuf tooling required — we hand-write
 * the JSON payloads using the same shapes as the proto messages.
 *
 * Server streaming (QueryStream) uses Connect's streaming protocol:
 * each message is a JSON envelope `{"result": ...}` separated by newlines,
 * with a final `{"result": ..., "flags": 2}` trailer.
 */
export class ConnectTransport implements Transport {
  private readonly config: VectorlessConfig;

  constructor(config: VectorlessConfig) {
    this.config = config;
  }

  // ── Health ──

  async health(): Promise<HealthResponse> {
    return this.unary<object, HealthResponse>(
      "vectorless.v1.HealthService",
      "Check",
      {}
    );
  }

  async version(): Promise<VersionResponse> {
    return this.unary<object, VersionResponse>(
      "vectorless.v1.HealthService",
      "Version",
      {}
    );
  }

  // ── Documents ──

  async ingestDocument(
    source: Buffer | ArrayBuffer | Blob | string,
    options?: IngestDocumentOptions
  ): Promise<IngestDocumentResponse> {
    let content: Uint8Array;

    if (typeof source === "string") {
      // File path — read in Node.js
      if (typeof globalThis.process !== "undefined") {
        const fs = await import("node:fs");
        content = new Uint8Array(fs.readFileSync(source));
      } else {
        throw new Error(
          "File path sources are only supported in Node.js. " +
            "In the browser, pass a Blob or ArrayBuffer."
        );
      }
    } else if (source instanceof Blob) {
      content = new Uint8Array(await source.arrayBuffer());
    } else if (source instanceof ArrayBuffer) {
      content = new Uint8Array(source);
    } else {
      content = new Uint8Array(
        (source as { buffer: ArrayBuffer }).buffer
      );
    }

    const payload = prepareJsonPayload(content, options);
    return this.unary<typeof payload, IngestDocumentResponse>(
      "vectorless.v1.DocumentsService",
      "CreateDocument",
      payload
    );
  }

  async getDocument(documentId: string): Promise<Document> {
    return this.unary<{ document_id: string }, Document>(
      "vectorless.v1.DocumentsService",
      "GetDocument",
      { document_id: documentId }
    );
  }

  async listDocuments(
    options?: ListDocumentsOptions
  ): Promise<ListDocumentsResponse> {
    const request: Record<string, unknown> = {};
    if (options?.limit != null) request.limit = options.limit;
    if (options?.cursor) request.cursor = options.cursor;
    if (options?.status) request.status = options.status;

    const response = await this.unary<
      Record<string, unknown>,
      { documents: Document[]; next_cursor?: string }
    >("vectorless.v1.DocumentsService", "ListDocuments", request);

    return {
      items: response.documents ?? [],
      next_cursor: response.next_cursor,
    };
  }

  async deleteDocument(documentId: string): Promise<void> {
    await this.unary<{ document_id: string }, object>(
      "vectorless.v1.DocumentsService",
      "DeleteDocument",
      { document_id: documentId }
    );
  }

  async getDocumentTree(documentId: string): Promise<DocumentTree> {
    return this.unary<{ document_id: string }, DocumentTree>(
      "vectorless.v1.DocumentsService",
      "GetDocumentTree",
      { document_id: documentId }
    );
  }

  // ── Sections ──

  async getSection(sectionId: string): Promise<Section> {
    return this.unary<{ section_id: string }, Section>(
      "vectorless.v1.DocumentsService",
      "GetSection",
      { section_id: sectionId }
    );
  }

  // ── Query ──

  async query(
    documentId: string,
    query: string,
    options?: QueryOptions
  ): Promise<QueryResponse> {
    return this.unary<Record<string, unknown>, QueryResponse>(
      "vectorless.v1.QueryService",
      "Query",
      {
        document_id: documentId,
        query,
        model: options?.model,
        max_tokens: options?.maxTokens,
        reserved_for_prompt: options?.reservedForPrompt,
        max_parallel_calls: options?.maxParallelCalls,
        max_sections: options?.maxSections,
      }
    );
  }

  async *queryStream(
    documentId: string,
    query: string,
    options?: QueryOptions
  ): AsyncIterable<QueryStreamEvent> {
    const url = `${this.config.baseUrl}/vectorless.v1.QueryService/QueryStream`;
    const headers = this.buildHeaders();
    headers["Content-Type"] = "application/json";
    headers["Connect-Protocol-Version"] = "1";

    const body = JSON.stringify({
      document_id: documentId,
      query,
      model: options?.model,
      max_tokens: options?.maxTokens,
      reserved_for_prompt: options?.reservedForPrompt,
      max_parallel_calls: options?.maxParallelCalls,
      max_sections: options?.maxSections,
    });

    const response = await fetch(url, {
      method: "POST",
      headers,
      body,
    });

    if (!response.ok) {
      throw await this.parseConnectError(response);
    }

    if (!response.body) {
      throw new StreamError("Response body is null — streaming not supported");
    }

    yield* this.parseConnectStream(response);
  }

  // ── Lifecycle ──

  async close(): Promise<void> {
    // No persistent connections — nothing to close
  }

  // ── Internal: Unary RPC ──

  private async unary<TReq, TRes>(
    service: string,
    method: string,
    request: TReq
  ): Promise<TRes> {
    const url = `${this.config.baseUrl}/${service}/${method}`;
    const headers = this.buildHeaders();
    headers["Content-Type"] = "application/json";
    headers["Connect-Protocol-Version"] = "1";

    return withRetry(
      async () => {
        const controller = new AbortController();
        const timeoutId = setTimeout(
          () => controller.abort(),
          this.config.timeout
        );

        try {
          const response = await fetch(url, {
            method: "POST",
            headers,
            body: JSON.stringify(request),
            signal: controller.signal,
          });

          if (!response.ok) {
            throw await this.parseConnectError(response);
          }

          return (await response.json()) as TRes;
        } catch (error) {
          if (error instanceof VectorlessError) throw error;
          if (
            error instanceof DOMException &&
            error.name === "AbortError"
          ) {
            throw new TimeoutError(
              `Request timed out after ${this.config.timeout}ms`
            );
          }
          throw error;
        } finally {
          clearTimeout(timeoutId);
        }
      },
      this.config.maxRetries,
      this.config.retryDelay
    );
  }

  // ── Internal: Stream parsing ──

  /**
   * Parse a Connect server-stream response.
   *
   * Connect server-streaming uses newline-delimited JSON envelopes:
   *   {"result": <message>}
   *   {"result": <message>}
   *   ...
   *
   * The final envelope may include `"flags": 2` to signal end-of-stream.
   */
  private async *parseConnectStream(
    response: Response
  ): AsyncGenerator<QueryStreamEvent> {
    const reader = response.body!.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed) continue;

          try {
            const envelope = JSON.parse(trimmed) as {
              result?: QueryStreamEvent;
              error?: { code: string; message: string };
              flags?: number;
            };

            if (envelope.error) {
              throw new ServerError(
                envelope.error.message ?? "Stream error"
              );
            }

            if (envelope.result) {
              yield envelope.result;
            }
          } catch (e) {
            if (e instanceof VectorlessError) throw e;
            // Skip malformed lines
          }
        }
      }

      // Process remaining buffer
      if (buffer.trim()) {
        try {
          const envelope = JSON.parse(buffer.trim()) as {
            result?: QueryStreamEvent;
          };
          if (envelope.result) {
            yield envelope.result;
          }
        } catch {
          // Ignore trailing partial data
        }
      }
    } finally {
      reader.releaseLock();
    }
  }

  // ── Internal: Helpers ──

  private buildHeaders(): Record<string, string> {
    const headers: Record<string, string> = {
      "User-Agent": `vectorless-ts/${SDK_VERSION}`,
    };
    if (this.config.apiKey) {
      headers["Authorization"] = `Bearer ${this.config.apiKey}`;
    }
    if (this.config.store) {
      headers["X-Vectorless-Store"] = this.config.store;
    }
    return headers;
  }

  /**
   * Parse a Connect error response.
   *
   * Connect errors are JSON: { "code": "not_found", "message": "..." }
   * The code maps to an RPC status name (not HTTP status).
   */
  private async parseConnectError(
    response: Response
  ): Promise<VectorlessError> {
    const requestId = response.headers.get("x-request-id") ?? undefined;

    try {
      const body = (await response.json()) as {
        code?: string;
        message?: string;
      };

      const message = body.message ?? `RPC failed with HTTP ${response.status}`;
      const code = body.code ?? "unknown";

      // Map Connect error codes to our error types
      switch (code) {
        case "unauthenticated":
          return new AuthenticationError(message, requestId);
        case "permission_denied":
          return new PermissionDeniedError(message, requestId);
        case "not_found":
          return new NotFoundError(message, requestId);
        case "invalid_argument":
          return new ValidationError(message, undefined, requestId);
        case "already_exists":
          return new ConflictError(message, requestId);
        case "resource_exhausted":
          return new RateLimitError(message, undefined, requestId);
        case "deadline_exceeded":
          return new TimeoutError(message, requestId);
        case "internal":
        case "unavailable":
        case "data_loss":
          return new ServerError(message, requestId);
        default:
          // Fallback to HTTP status code mapping
          return this.mapHttpStatus(response.status, message, requestId);
      }
    } catch {
      return this.mapHttpStatus(
        response.status,
        `RPC failed with HTTP ${response.status}`,
        requestId
      );
    }
  }

  private mapHttpStatus(
    status: number,
    message: string,
    requestId?: string
  ): VectorlessError {
    switch (status) {
      case 400:
        return new ValidationError(message, undefined, requestId);
      case 401:
        return new AuthenticationError(message, requestId);
      case 403:
        return new PermissionDeniedError(message, requestId);
      case 404:
        return new NotFoundError(message, requestId);
      case 409:
        return new ConflictError(message, requestId);
      case 429:
        return new RateLimitError(message, undefined, requestId);
      case 408:
      case 504:
        return new TimeoutError(message, requestId);
      default:
        if (status >= 500) return new ServerError(message, requestId);
        return new VectorlessError(message, status, "unknown", requestId);
    }
  }
}
