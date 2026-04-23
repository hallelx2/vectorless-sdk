// ── Client ──
export { VectorlessClient } from "./client.js";

// ── Configuration ──
export { resolveConfig } from "./config.js";
export type { VectorlessConfig, VectorlessClientOptions } from "./config.js";

// ── Types ──
export type {
  TransportProtocol,
  HealthResponse,
  VersionResponse,
  DocumentStatus,
  Document,
  IngestDocumentOptions,
  IngestDocumentResponse,
  ListDocumentsOptions,
  ListDocumentsResponse,
  SectionView,
  DocumentTree,
  Section,
  QueryOptions,
  QuerySection,
  Usage,
  QueryResponse,
  QueryStreamEventType,
  QueryStreamEvent,
  WaitForReadyOptions,
} from "./types.js";

// ── Errors ──
export {
  VectorlessError,
  AuthenticationError,
  PermissionDeniedError,
  NotFoundError,
  ValidationError,
  ConflictError,
  RateLimitError,
  TimeoutError,
  ServerError,
  DocumentFailedError,
  StreamError,
} from "./errors.js";

// ── Transport (advanced usage) ──
export type { Transport } from "./transport/interface.js";
export { HttpTransport } from "./transport/http.js";
export { ConnectTransport } from "./transport/connect.js";
