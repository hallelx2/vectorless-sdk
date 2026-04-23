/**
 * Base error for all Vectorless SDK errors.
 */
export class VectorlessError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly code: string,
    public readonly requestId?: string
  ) {
    super(message);
    this.name = "VectorlessError";
  }
}

/**
 * 401 — Missing or invalid API key.
 */
export class AuthenticationError extends VectorlessError {
  constructor(message: string, requestId?: string) {
    super(message, 401, "authentication_error", requestId);
    this.name = "AuthenticationError";
  }
}

/**
 * 403 — Valid credentials but insufficient permissions.
 */
export class PermissionDeniedError extends VectorlessError {
  constructor(message: string, requestId?: string) {
    super(message, 403, "permission_denied", requestId);
    this.name = "PermissionDeniedError";
  }
}

/**
 * 404 — Document or section not found.
 */
export class NotFoundError extends VectorlessError {
  constructor(message: string, requestId?: string) {
    super(message, 404, "not_found", requestId);
    this.name = "NotFoundError";
  }
}

/**
 * 400 — Invalid request parameters.
 */
export class ValidationError extends VectorlessError {
  public readonly fieldErrors?: Record<string, string[]>;

  constructor(
    message: string,
    fieldErrors?: Record<string, string[]>,
    requestId?: string
  ) {
    super(message, 400, "validation_error", requestId);
    this.name = "ValidationError";
    this.fieldErrors = fieldErrors;
  }
}

/**
 * 409 — Conflict (e.g. duplicate idempotency key with different payload).
 */
export class ConflictError extends VectorlessError {
  constructor(message: string, requestId?: string) {
    super(message, 409, "conflict", requestId);
    this.name = "ConflictError";
  }
}

/**
 * 429 — Rate limit exceeded.
 */
export class RateLimitError extends VectorlessError {
  public readonly retryAfter?: number;

  constructor(message: string, retryAfter?: number, requestId?: string) {
    super(message, 429, "rate_limit_exceeded", requestId);
    this.name = "RateLimitError";
    this.retryAfter = retryAfter;
  }
}

/**
 * 408 / 504 — Request or gateway timeout.
 */
export class TimeoutError extends VectorlessError {
  constructor(message: string, requestId?: string) {
    super(message, 408, "timeout", requestId);
    this.name = "TimeoutError";
  }
}

/**
 * 500+ — Internal server error.
 */
export class ServerError extends VectorlessError {
  constructor(message: string, requestId?: string) {
    super(message, 500, "server_error", requestId);
    this.name = "ServerError";
  }
}

/**
 * Document failed to process during ingestion.
 */
export class DocumentFailedError extends VectorlessError {
  constructor(message: string, requestId?: string) {
    super(message, 422, "document_failed", requestId);
    this.name = "DocumentFailedError";
  }
}

/**
 * Streaming connection was interrupted or reset.
 */
export class StreamError extends VectorlessError {
  constructor(message: string, requestId?: string) {
    super(message, 0, "stream_error", requestId);
    this.name = "StreamError";
  }
}
