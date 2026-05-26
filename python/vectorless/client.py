from __future__ import annotations

import time
from typing import BinaryIO, Dict, Iterator, List, Optional, Union

from pathlib import Path

from vectorless._config import resolve_config
from vectorless.transport.base import Transport
from vectorless.transport.http import HttpTransport
from vectorless.transport.connect import ConnectTransport
from vectorless.errors import DocumentFailedError, TimeoutError
from vectorless.types import (
    HealthResponse,
    VersionResponse,
    Document,
    IngestDocumentResponse,
    ListDocumentsResponse,
    DocumentTree,
    Section,
    QueryResponse,
    QueryStreamEvent,
)


class VectorlessClient:
    """
    Synchronous Vectorless SDK client.

    Provides access to all Vectorless server APIs — document ingestion,
    tree inspection, section retrieval, and LLM-powered query.

    Supports two transport protocols:

    - ``"http"`` (default) — standard REST/JSON over HTTP endpoints
    - ``"connect"`` — ConnectRPC protocol (JSON encoding, native streaming)

    Works with both deployed instances (API key auth) and self-hosted
    instances (no auth required).

    Examples::

        # Deployed instance with API key
        client = VectorlessClient(
            base_url="https://api.vectorless.dev",
            api_key="vl_live_...",
        )

        # Self-hosted instance, no auth
        client = VectorlessClient(base_url="http://localhost:8080")

        # Using Connect protocol
        client = VectorlessClient(
            base_url="http://localhost:8080",
            transport="connect",
        )
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        transport: Optional[str] = None,
        timeout: float = 30.0,
        max_retries: int = 3,
        retry_delay: float = 0.5,
        store: Optional[str] = None,
    ) -> None:
        config = resolve_config(
            api_key=api_key,
            base_url=base_url,
            transport=transport,  # type: ignore[arg-type]
            timeout=timeout,
            max_retries=max_retries,
            retry_delay=retry_delay,
            store=store,
        )
        self._config = config

        self._transport: Transport
        if config.transport == "connect":
            self._transport = ConnectTransport(config)
        else:
            self._transport = HttpTransport(config)

    # ── Health ──

    def health(self) -> HealthResponse:
        """Check server liveness."""
        return self._transport.health()

    def version(self) -> VersionResponse:
        """Get the server build version."""
        return self._transport.version()

    # ── Documents ──

    def ingest_document(
        self,
        source: Union[str, bytes, BinaryIO, Path],
        *,
        filename: Optional[str] = None,
        content_type: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
        idempotency_key: Optional[str] = None,
    ) -> IngestDocumentResponse:
        """
        Ingest a document into Vectorless.

        Accepts file paths, raw bytes, or file-like objects.
        Returns immediately with a document ID and ``"pending"`` status.
        Use :meth:`wait_for_ready` to poll until processing completes.

        Args:
            source: File path, bytes, or readable binary stream.
            filename: Original filename (for format detection).
            content_type: MIME type override.
            metadata: Key-value metadata attached to the document.
            idempotency_key: Prevents duplicate ingestion.

        Returns:
            Response with ``document_id`` and initial ``status``.
        """
        return self._transport.ingest_document(
            source, filename, content_type, metadata, idempotency_key
        )

    def get_document(self, document_id: str) -> Document:
        """Get document metadata and processing status."""
        return self._transport.get_document(document_id)

    def list_documents(
        self,
        *,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
        status: Optional[str] = None,
    ) -> ListDocumentsResponse:
        """
        List documents with optional filtering and cursor-based pagination.

        Args:
            limit: Max documents per page (1-200, default 50).
            cursor: Cursor from a previous page.
            status: Filter by status (pending/parsing/summarizing/ready/failed).
        """
        return self._transport.list_documents(limit, cursor, status)

    def delete_document(self, document_id: str) -> None:
        """Delete a document and all its sections."""
        self._transport.delete_document(document_id)

    # ── Tree & Sections ──

    def get_document_tree(self, document_id: str) -> DocumentTree:
        """
        Get the hierarchical document tree.

        Returns the structural outline — sections with IDs, titles,
        summaries, parent/child relationships, and token counts.
        Does not include section content.
        """
        return self._transport.get_document_tree(document_id)

    def get_llms_txt(self, document_id: str) -> str:
        """
        Get the document rendered as an llms.txt Markdown map — H1 title,
        a blockquote summary, and a nested section outline with one-line
        summaries. A compact, agent-friendly index of the document.

        Returns the raw Markdown text.
        """
        import httpx

        headers: Dict[str, str] = {}
        if self._config.api_key:
            headers["Authorization"] = f"Bearer {self._config.api_key}"
        if self._config.store:
            headers["X-Vectorless-Store"] = self._config.store
        resp = httpx.get(
            f"{self._config.base_url}/v1/documents/{document_id}/llms.txt",
            headers=headers,
            timeout=self._config.timeout,
        )
        resp.raise_for_status()
        return resp.text

    def get_section(self, section_id: str) -> Section:
        """Fetch a single section with full content."""
        return self._transport.get_section(section_id)

    def get_sections(self, section_ids: List[str]) -> List[Section]:
        """Fetch multiple sections sequentially."""
        return [self._transport.get_section(sid) for sid in section_ids]

    # ── Query ──

    def query(
        self,
        document_id: str,
        query: str,
        *,
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        reserved_for_prompt: Optional[int] = None,
        max_parallel_calls: Optional[int] = None,
        max_sections: Optional[int] = None,
    ) -> QueryResponse:
        """
        Query a document — the LLM navigates the document tree to find
        the most relevant sections.

        Returns selected sections with full content, strategy used,
        and token usage/cost information.
        """
        return self._transport.query(
            document_id,
            query,
            model,
            max_tokens,
            reserved_for_prompt,
            max_parallel_calls,
            max_sections,
        )

    def query_stream(
        self,
        document_id: str,
        query: str,
        *,
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        reserved_for_prompt: Optional[int] = None,
        max_parallel_calls: Optional[int] = None,
        max_sections: Optional[int] = None,
    ) -> Iterator[QueryStreamEvent]:
        """
        Stream query results in real-time.

        Yields events as retrieval progresses: ``started``,
        ``slice_started``, ``section_selected``, ``slice_completed``,
        ``completed``, ``error``.
        """
        yield from self._transport.query_stream(
            document_id,
            query,
            model,
            max_tokens,
            reserved_for_prompt,
            max_parallel_calls,
            max_sections,
        )

    # ── Polling ──

    def wait_for_ready(
        self,
        document_id: str,
        *,
        timeout: float = 300.0,
        poll_interval: float = 2.0,
        on_progress: Optional[callable] = None,
    ) -> Document:
        """
        Wait for a document to finish processing.

        Polls :meth:`get_document` with exponential backoff until status
        is ``"ready"`` or ``"failed"``.

        Args:
            document_id: ID of the document to wait for.
            timeout: Total timeout in seconds (default 300).
            poll_interval: Initial poll interval in seconds (default 2).
            on_progress: Optional callback receiving the current status string.

        Raises:
            DocumentFailedError: If the document fails processing.
            TimeoutError: If the timeout is exceeded.
        """
        deadline = time.time() + timeout

        while time.time() < deadline:
            time.sleep(poll_interval)
            doc = self.get_document(document_id)

            if on_progress:
                on_progress(doc.status)

            if doc.status == "ready":
                return doc

            if doc.status == "failed":
                raise DocumentFailedError(
                    f"Document processing failed: {doc.error_message or 'Unknown error'}"
                )

            # Exponential backoff capped at 10 seconds
            poll_interval = min(poll_interval * 1.5, 10.0)

        raise TimeoutError(
            f"Document {document_id} did not become ready within {timeout}s"
        )

    # ── Lifecycle ──

    def close(self) -> None:
        """Close the client and release resources."""
        self._transport.close()

    def __enter__(self) -> "VectorlessClient":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
