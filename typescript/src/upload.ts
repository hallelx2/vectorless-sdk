import type { IngestDocumentOptions } from "./types.js";

/**
 * Prepare a document source for multipart upload.
 * Handles Buffer, ArrayBuffer, Blob, and file paths (Node.js only).
 */
export async function prepareUpload(
  source: Buffer | ArrayBuffer | Blob | string,
  options?: IngestDocumentOptions
): Promise<FormData> {
  const formData = new FormData();

  if (typeof source === "string") {
    // File path — Node.js only
    if (typeof globalThis.process !== "undefined") {
      const fs = await import("node:fs");
      const path = await import("node:path");
      const buffer = fs.readFileSync(source);
      const filename = options?.filename ?? path.basename(source);
      formData.append("file", new Blob([buffer]), filename);
    } else {
      throw new Error(
        "File path sources are only supported in Node.js. " +
          "In the browser, pass a Blob or ArrayBuffer."
      );
    }
  } else if (source instanceof Blob) {
    const filename =
      options?.filename ?? (source as File).name ?? "document";
    formData.append("file", source, filename);
  } else {
    // Buffer or ArrayBuffer
    const bytes = new Uint8Array(
      source instanceof ArrayBuffer
        ? source
        : (source as { buffer: ArrayBuffer; byteOffset: number; byteLength: number }).buffer
    );
    const filename = options?.filename ?? "document";
    formData.append("file", new Blob([bytes]), filename);
  }

  if (options?.contentType) {
    formData.append("content_type", options.contentType);
  }
  if (options?.metadata) {
    for (const [key, value] of Object.entries(options.metadata)) {
      formData.append(`metadata[${key}]`, value);
    }
  }

  return formData;
}

/**
 * Prepare a JSON body for document ingestion (used by Connect transport).
 * Encodes the file content as base64.
 */
export function prepareJsonPayload(
  content: Buffer | ArrayBuffer | Uint8Array,
  options?: IngestDocumentOptions
): {
  content: string;
  filename: string;
  content_type: string;
  metadata: Record<string, string>;
} {
  const bytes =
    content instanceof Uint8Array
      ? content
      : new Uint8Array(
          content instanceof ArrayBuffer
            ? content
            : (content as { buffer: ArrayBuffer }).buffer
        );

  // Base64 encode
  const base64 =
    typeof globalThis.Buffer !== "undefined"
      ? globalThis.Buffer.from(bytes).toString("base64")
      : globalThis.btoa(String.fromCharCode(...bytes));

  return {
    content: base64,
    filename: options?.filename ?? "document",
    content_type: options?.contentType ?? "application/octet-stream",
    metadata: options?.metadata ?? {},
  };
}
