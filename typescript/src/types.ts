// ── Transport Protocol ──

export type TransportProtocol = "http" | "connect";

// ── Health ──

export interface HealthResponse {
  status: string;
}

export interface VersionResponse {
  version: string;
}

// ── Documents ──

export type DocumentStatus =
  | "pending"
  | "parsing"
  | "summarizing"
  | "ready"
  | "failed";

export interface Document {
  id: string;
  title: string;
  content_type: string;
  status: DocumentStatus;
  byte_size: number;
  error_message: string;
  metadata: Record<string, string>;
  created_at: string;
  updated_at: string;
}

export interface IngestDocumentOptions {
  /** Original filename (e.g. "report.pdf"). Used for format detection. */
  filename?: string;
  /** MIME type override. Auto-detected from filename if omitted. */
  contentType?: string;
  /** Arbitrary key-value metadata attached to the document. */
  metadata?: Record<string, string>;
  /**
   * Idempotency key. If provided, duplicate ingestion requests
   * with the same key return the original response.
   */
  idempotencyKey?: string;
}

export interface IngestDocumentResponse {
  document_id: string;
  status: DocumentStatus;
}

export interface ListDocumentsOptions {
  /** Maximum number of documents to return (1-200, default 50). */
  limit?: number;
  /** Cursor from a previous page (RFC3339Nano timestamp). */
  cursor?: string;
  /** Filter by document status. */
  status?: DocumentStatus;
}

export interface ListDocumentsResponse {
  items: Document[];
  next_cursor?: string;
}

// ── Document Tree ──

export interface SectionView {
  id: string;
  parent_id: string;
  depth: number;
  title: string;
  summary: string;
  children: string[];
  tokens: number;
}

export interface DocumentTree {
  document_id: string;
  title: string;
  sections: SectionView[];
}

// ── Sections ──

export interface Section {
  id: string;
  document_id: string;
  parent_id: string;
  ordinal: number;
  depth: number;
  title: string;
  summary: string;
  token_count: number;
  metadata: Record<string, string>;
  content: string;
}

// ── Query ──

export interface QueryOptions {
  /** LLM model override (e.g. "claude-sonnet-4-20250514"). */
  model?: string;
  /** Max context window tokens (default 100,000). */
  maxTokens?: number;
  /** Tokens reserved for the prompt itself (default 4,000). */
  reservedForPrompt?: number;
  /** Max parallel LLM calls for chunked-tree strategy (default 8). */
  maxParallelCalls?: number;
  /** Cap on sections returned (0 = no cap). */
  maxSections?: number;
}

export interface QuerySection {
  id: string;
  parent_id: string;
  title: string;
  summary: string;
  token_count: number;
  content: string;
}

export interface Usage {
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  cost_usd: number;
  llm_calls: number;
}

export interface QueryResponse {
  document_id: string;
  query: string;
  strategy: string;
  model: string;
  sections: QuerySection[];
  elapsed_ms: number;
  usage?: Usage;
}

// ── Streaming Query ──

export type QueryStreamEventType =
  | "started"
  | "slice_started"
  | "section_selected"
  | "slice_completed"
  | "completed"
  | "error";

export interface QueryStreamEvent {
  type: QueryStreamEventType;
  section?: QuerySection;
  slice_index?: number;
  total_slices?: number;
  message?: string;
  strategy?: string;
  document_id?: string;
  query?: string;
  elapsed_ms?: number;
}

// ── Wait / Polling ──

export interface WaitForReadyOptions {
  /** Total timeout in milliseconds (default 300,000 = 5 minutes). */
  timeout?: number;
  /** Initial poll interval in milliseconds (default 2,000). */
  pollInterval?: number;
  /** Optional callback fired on each poll with the current status. */
  onProgress?: (status: DocumentStatus) => void;
}
