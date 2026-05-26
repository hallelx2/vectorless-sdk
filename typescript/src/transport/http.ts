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
import { prepareUpload } from "../upload.js";
import { parseSSEStream } from "../streaming.js";
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
} from "../errors.js";

const SDK_VERSION = "1.0.0";

/**
 * HTTP/REST transport.
 *
 * Talks to the Vectorless server via standard REST endpoints:
 *   GET/POST/DELETE /v1/documents, /v1/sections, /v1/query, etc.
 *
 * Streaming queries use Server-Sent Events (SSE) via POST /v1/query/stream.
 *
 * This is the default transport — zero extra dependencies beyond `fetch`.
 */
export class HttpTransport implements Transport {
  private readonly config: VectorlessConfig;

  constructor(config: VectorlessConfig) {
    this.config = config;
  }

  // ── Health ──

  async health(): Promise<HealthResponse> {
    return this.request<HealthResponse>("GET", "/v1/health");
  }

  async version(): Promise<VersionResponse> {
    return this.request<VersionResponse>("GET", "/v1/version");
  }

  // ── Documents ──

  async ingestDocument(
    source: Buffer | ArrayBuffer | Blob | string,
    options?: IngestDocumentOptions
  ): Promise<IngestDocumentResponse> {
    const formData = await prepareUpload(source, options);

    const headers: Record<string, string> = {};
    if (options?.idempotencyKey) {
      headers["Idempotency-Key"] = options.idempotencyKey;
    }

    return this.request<IngestDocumentResponse>(
      "POST",
      "/v1/documents",
      formData,
      { isMultipart: true, extraHeaders: headers }
    );
  }

  async getDocument(documentId: string): Promise<Document> {
    return this.request<Document>("GET", `/v1/documents/${documentId}`);
  }

  async listDocuments(
    options?: ListDocumentsOptions
  ): Promise<ListDocumentsResponse> {
    const params = new URLSearchParams();
    if (options?.limit != null) params.set("limit", String(options.limit));
    if (options?.cursor) params.set("cursor", options.cursor);
    if (options?.status) params.set("status", options.status);

    const qs = params.toString();
    const path = qs ? `/v1/documents?${qs}` : "/v1/documents";
    return this.request<ListDocumentsResponse>("GET", path);
  }

  async deleteDocument(documentId: string): Promise<void> {
    await this.request<void>("DELETE", `/v1/documents/${documentId}`);
  }

  async getDocumentTree(documentId: string): Promise<DocumentTree> {
    return this.request<DocumentTree>(
      "GET",
      `/v1/documents/${documentId}/tree`
    );
  }

  // ── Sections ──

  async getSection(sectionId: string): Promise<Section> {
    return this.request<Section>("GET", `/v1/sections/${sectionId}`);
  }

  // ── Query ──

  async query(
    documentId: string,
    query: string,
    options?: QueryOptions
  ): Promise<QueryResponse> {
    return this.request<QueryResponse>("POST", "/v1/query", {
      document_id: documentId,
      query,
      model: options?.model,
      max_tokens: options?.maxTokens,
      reserved_for_prompt: options?.reservedForPrompt,
      max_parallel_calls: options?.maxParallelCalls,
      max_sections: options?.maxSections,
    });
  }

  async *queryStream(
    documentId: string,
    query: string,
    options?: QueryOptions
  ): AsyncIterable<QueryStreamEvent> {
    const url = `${this.config.baseUrl}/v1/query/stream`;
    const headers = this.buildHeaders();
    headers["Content-Type"] = "application/json";
    headers["Accept"] = "text/event-stream";

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
      throw await this.parseErrorResponse(response);
    }

    yield* parseSSEStream(response);
  }

  // ── Lifecycle ──

  async close(): Promise<void> {
    // No persistent connections with fetch — nothing to close
  }

  // ── Internal ──

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

  private async request<T>(
    method: string,
    path: string,
    body?: unknown,
    opts?: { isMultipart?: boolean; extraHeaders?: Record<string, string> }
  ): Promise<T> {
    const url = `${this.config.baseUrl}${path}`;
    const headers = this.buildHeaders();

    if (opts?.extraHeaders) {
      Object.assign(headers, opts.extraHeaders);
    }

    if (!opts?.isMultipart && body && !(body instanceof FormData)) {
      headers["Content-Type"] = "application/json";
    }

    const fetchBody =
      body instanceof FormData
        ? body
        : body
          ? JSON.stringify(body)
          : undefined;

    return withRetry(
      async () => {
        const controller = new AbortController();
        const timeoutId = setTimeout(
          () => controller.abort(),
          this.config.timeout
        );

        try {
          const response = await fetch(url, {
            method,
            headers,
            body: fetchBody,
            signal: controller.signal,
          });

          if (!response.ok) {
            throw await this.parseErrorResponse(response);
          }

          if (response.status === 204) return undefined as T;
          return (await response.json()) as T;
        } catch (error) {
          if (error instanceof VectorlessError) throw error;
          if (error instanceof DOMException && error.name === "AbortError") {
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

  private async parseErrorResponse(
    response: Response
  ): Promise<VectorlessError> {
    const requestId = response.headers.get("x-request-id") ?? undefined;

    try {
      const body = (await response.json()) as {
        error?: string | {
          code?: string;
          message?: string;
          field_errors?: Record<string, string[]>;
        };
      };

      const message =
        typeof body.error === "string"
          ? body.error
          : body.error?.message ?? `Request failed with status ${response.status}`;

      const fieldErrors =
        typeof body.error === "object" ? body.error?.field_errors : undefined;

      switch (response.status) {
        case 400:
          return new ValidationError(message, fieldErrors, requestId);
        case 401:
          return new AuthenticationError(message, requestId);
        case 403:
          return new PermissionDeniedError(message, requestId);
        case 404:
          return new NotFoundError(message, requestId);
        case 409:
          return new ConflictError(message, requestId);
        case 429: {
          const retryAfter = response.headers.get("retry-after");
          return new RateLimitError(
            message,
            retryAfter ? parseInt(retryAfter, 10) : undefined,
            requestId
          );
        }
        case 408:
        case 504:
          return new TimeoutError(message, requestId);
        default:
          if (response.status >= 500) {
            return new ServerError(message, requestId);
          }
          return new VectorlessError(
            message,
            response.status,
            typeof body.error === "object"
              ? body.error?.code ?? "unknown"
              : "unknown",
            requestId
          );
      }
    } catch {
      return new VectorlessError(
        `Request failed with status ${response.status}`,
        response.status,
        "unknown",
        requestId
      );
    }
  }
}
