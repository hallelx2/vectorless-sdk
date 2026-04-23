from __future__ import annotations

import json
from typing import Iterator, AsyncIterator

import httpx

from vectorless.types import QueryStreamEvent


def parse_sse_stream(response: httpx.Response) -> Iterator[QueryStreamEvent]:
    """
    Parse a Server-Sent Events stream from an httpx response (sync).

    The Vectorless server sends events in standard SSE format::

        event: <type>
        data: <json>

    Each event is separated by a blank line.
    """
    buffer = ""

    for chunk in response.iter_text():
        buffer += chunk
        parts = buffer.split("\n\n")
        buffer = parts.pop()  # Keep incomplete part

        for part in parts:
            event = _parse_sse_event(part.strip())
            if event:
                yield event

    # Process remaining buffer
    if buffer.strip():
        event = _parse_sse_event(buffer.strip())
        if event:
            yield event


async def parse_sse_stream_async(
    response: httpx.Response,
) -> AsyncIterator[QueryStreamEvent]:
    """
    Parse a Server-Sent Events stream from an httpx response (async).
    """
    buffer = ""

    async for chunk in response.aiter_text():
        buffer += chunk
        parts = buffer.split("\n\n")
        buffer = parts.pop()

        for part in parts:
            event = _parse_sse_event(part.strip())
            if event:
                yield event

    if buffer.strip():
        event = _parse_sse_event(buffer.strip())
        if event:
            yield event


def _parse_sse_event(raw: str) -> QueryStreamEvent | None:
    """Parse a single SSE event block into a QueryStreamEvent."""
    if not raw:
        return None

    event_type: str | None = None
    data: str | None = None

    for line in raw.split("\n"):
        if line.startswith("event:"):
            event_type = line[6:].strip()
        elif line.startswith("data:"):
            data = line[5:].strip()

    if not data:
        return None

    try:
        parsed = json.loads(data)
        if event_type and "type" not in parsed:
            parsed["type"] = event_type
        return QueryStreamEvent.model_validate(parsed)
    except Exception:
        return None


def parse_connect_stream(
    response: httpx.Response,
) -> Iterator[QueryStreamEvent]:
    """
    Parse a Connect server-streaming response (sync).

    Connect streaming uses newline-delimited JSON envelopes::

        {"result": <message>}
        {"result": <message>, "flags": 2}
    """
    buffer = ""

    for chunk in response.iter_text():
        buffer += chunk
        lines = buffer.split("\n")
        buffer = lines.pop()

        for line in lines:
            trimmed = line.strip()
            if not trimmed:
                continue
            event = _parse_connect_envelope(trimmed)
            if event:
                yield event

    if buffer.strip():
        event = _parse_connect_envelope(buffer.strip())
        if event:
            yield event


async def parse_connect_stream_async(
    response: httpx.Response,
) -> AsyncIterator[QueryStreamEvent]:
    """
    Parse a Connect server-streaming response (async).
    """
    buffer = ""

    async for chunk in response.aiter_text():
        buffer += chunk
        lines = buffer.split("\n")
        buffer = lines.pop()

        for line in lines:
            trimmed = line.strip()
            if not trimmed:
                continue
            event = _parse_connect_envelope(trimmed)
            if event:
                yield event

    if buffer.strip():
        event = _parse_connect_envelope(buffer.strip())
        if event:
            yield event


def _parse_connect_envelope(raw: str) -> QueryStreamEvent | None:
    """Parse a single Connect streaming envelope."""
    try:
        envelope = json.loads(raw)
        if "error" in envelope:
            from vectorless.errors import ServerError

            raise ServerError(envelope["error"].get("message", "Stream error"))
        result = envelope.get("result")
        if result:
            return QueryStreamEvent.model_validate(result)
        return None
    except json.JSONDecodeError:
        return None
