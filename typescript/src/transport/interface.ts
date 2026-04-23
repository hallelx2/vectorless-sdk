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

/**
 * Transport abstraction — implemented by HTTP/REST and Connect/Protobuf adapters.
 *
 * Both transports expose the same operations; only the wire format differs.
 * Users pick a transport at client init time and never interact with this
 * interface directly.
 */
export interface Transport {
  // ── Health ──

  health(): Promise<HealthResponse>;
  version(): Promise<VersionResponse>;

  // ── Documents ──

  ingestDocument(
    source: Buffer | ArrayBuffer | Blob | string,
    options?: IngestDocumentOptions
  ): Promise<IngestDocumentResponse>;

  getDocument(documentId: string): Promise<Document>;

  listDocuments(options?: ListDocumentsOptions): Promise<ListDocumentsResponse>;

  deleteDocument(documentId: string): Promise<void>;

  getDocumentTree(documentId: string): Promise<DocumentTree>;

  // ── Sections ──

  getSection(sectionId: string): Promise<Section>;

  // ── Query ──

  query(
    documentId: string,
    query: string,
    options?: QueryOptions
  ): Promise<QueryResponse>;

  queryStream(
    documentId: string,
    query: string,
    options?: QueryOptions
  ): AsyncIterable<QueryStreamEvent>;

  // ── Lifecycle ──

  close(): Promise<void>;
}
