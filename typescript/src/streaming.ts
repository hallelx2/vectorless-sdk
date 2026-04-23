import type { QueryStreamEvent } from "./types.js";
import { StreamError } from "./errors.js";

/**
 * Parse a Server-Sent Events (SSE) stream into QueryStreamEvent objects.
 *
 * The Vectorless server sends events in standard SSE format:
 *   event: <type>
 *   data: <json>
 *
 * Each event is separated by a blank line.
 */
export async function* parseSSEStream(
  response: Response
): AsyncGenerator<QueryStreamEvent> {
  if (!response.body) {
    throw new StreamError("Response body is null — streaming not supported");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();

      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      // Process complete events (separated by double newline)
      const parts = buffer.split("\n\n");
      // Last part may be incomplete — keep it in buffer
      buffer = parts.pop() ?? "";

      for (const part of parts) {
        const event = parseSSEEvent(part.trim());
        if (event) {
          yield event;
        }
      }
    }

    // Process any remaining buffer
    if (buffer.trim()) {
      const event = parseSSEEvent(buffer.trim());
      if (event) {
        yield event;
      }
    }
  } finally {
    reader.releaseLock();
  }
}

function parseSSEEvent(raw: string): QueryStreamEvent | null {
  if (!raw) return null;

  let eventType: string | undefined;
  let data: string | undefined;

  for (const line of raw.split("\n")) {
    if (line.startsWith("event:")) {
      eventType = line.slice(6).trim();
    } else if (line.startsWith("data:")) {
      data = line.slice(5).trim();
    }
  }

  if (!data) return null;

  try {
    const parsed = JSON.parse(data) as QueryStreamEvent;
    // If the event type was in the SSE "event:" field, use it
    if (eventType && !parsed.type) {
      parsed.type = eventType as QueryStreamEvent["type"];
    }
    return parsed;
  } catch {
    return null;
  }
}
