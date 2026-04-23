import { VectorlessError, RateLimitError } from "./errors.js";

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function jitter(): number {
  return Math.random() * 200;
}

export async function withRetry<T>(
  fn: () => Promise<T>,
  maxRetries: number,
  retryDelay: number
): Promise<T> {
  let lastError: unknown;

  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      return await fn();
    } catch (error) {
      lastError = error;

      // Don't retry if we've exhausted attempts
      if (attempt >= maxRetries) {
        throw error;
      }

      if (error instanceof VectorlessError) {
        // Rate limit: respect Retry-After header
        if (error.status === 429) {
          const delay =
            error instanceof RateLimitError && error.retryAfter != null
              ? error.retryAfter * 1000
              : retryDelay * Math.pow(2, attempt);
          await sleep(delay + jitter());
          continue;
        }

        // Don't retry client errors (except 408 timeout and 429 rate limit)
        if (
          error.status >= 400 &&
          error.status < 500 &&
          error.status !== 408 &&
          error.status !== 429
        ) {
          throw error;
        }
      }

      // Retry 5xx, network errors, timeouts
      await sleep(retryDelay * Math.pow(2, attempt) + jitter());
    }
  }

  throw lastError;
}
