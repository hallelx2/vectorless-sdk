import type { TransportProtocol } from "./types.js";

export interface VectorlessConfig {
  /** API key for authentication. Optional for self-hosted instances with auth disabled. */
  apiKey?: string;
  /**
   * Base URL of the Vectorless server.
   * - Deployed: "https://api.vectorless.dev"
   * - Self-hosted: "http://localhost:8080"
   */
  baseUrl: string;
  /**
   * Transport protocol.
   * - "http": REST/JSON over standard HTTP endpoints (default)
   * - "connect": ConnectRPC protocol (JSON encoding, supports streaming natively)
   */
  transport: TransportProtocol;
  /** Request timeout in milliseconds (default 30,000). */
  timeout: number;
  /** Maximum retry attempts for transient errors (default 3). */
  maxRetries: number;
  /** Base delay between retries in milliseconds (default 500). */
  retryDelay: number;
  /**
   * Scope every request to one store (sent as X-Vectorless-Store). Only
   * needed for org-wide keys; a store-bound key scopes automatically.
   */
  store?: string;
}

export interface VectorlessClientOptions {
  /** API key. Falls back to VECTORLESS_API_KEY env var. Optional for self-hosted. */
  apiKey?: string;
  /** Server base URL (default "http://localhost:8080"). */
  baseUrl?: string;
  /** Transport protocol (default "http"). */
  transport?: TransportProtocol;
  /** Request timeout in ms (default 30,000). */
  timeout?: number;
  /** Max retry attempts (default 3). */
  maxRetries?: number;
  /** Base retry delay in ms (default 500). */
  retryDelay?: number;
  /** Scope every request to one store (X-Vectorless-Store). Falls back to VECTORLESS_STORE. */
  store?: string;
}

const DEFAULTS: Omit<VectorlessConfig, "apiKey"> = {
  baseUrl: "http://localhost:8080",
  transport: "http",
  timeout: 30_000,
  maxRetries: 3,
  retryDelay: 500,
};

export function resolveConfig(options?: VectorlessClientOptions): VectorlessConfig {
  const apiKey =
    options?.apiKey ??
    (typeof process !== "undefined" ? process.env?.VECTORLESS_API_KEY : undefined);

  const store =
    options?.store ??
    (typeof process !== "undefined" ? process.env?.VECTORLESS_STORE : undefined);

  return {
    ...DEFAULTS,
    ...options,
    apiKey: apiKey ?? undefined,
    store: store ?? undefined,
  };
}
