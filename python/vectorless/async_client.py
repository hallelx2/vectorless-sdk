from __future__ import annotations

import asyncio
from typing import AsyncIterator, BinaryIO, Dict, List, Optional, Union

from pathlib import Path

from vectorless._config import resolve_config
from vectorless.transport.base import AsyncTransport
from vectorless.transport.http import AsyncHttpTransport
from vectorless.transport.connect import AsyncConnectTransport
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


class AsyncVectorlessClient:
    """
    Asynchronous Vectorless SDK client.

    Async counterpart of :class:`VectorlessClient`. All methods are
    coroutines and streaming methods return async iterators.

    Examples::

        async with AsyncVectorlessClient(
            base_url="https://api.vectorless.dev",
            api_key="vl_live_...",
        ) as client:
            result = await client.ingest_document("./report.pdf")
            doc = await client.wait_for_ready(result.document_id)
            tree = await client.get_document_tree(doc.id)
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        transport: Optional[str] = None,
        timeout: float = 30.0,
        max_retries: int = 3,
        retry_delay: float = 0.5,
    ) -> None:
        config = resolve_config(
            api_key=api_key,
            base_url=base_url,
            transport=transport,  # type: ignore[arg-type]
            timeout=timeout,
            max_retries=max_retries,
            retry_delay=retry_delay,
        )

        self._transport: AsyncTransport
        if config.transport == "connect":
            self._transport = AsyncConnectTransport(config)
        else:
            self._transport = AsyncHttpTransport(config)

    # ── Health ──

    async def health(self) -> HealthResponse:
        """Check server liveness."""
        return await self._transport.health()

    async def version(self) -> VersionResponse:
        """Get the server build version."""
        return await self._transport.version()

    # ── Documents ──

    async def ingest_document(
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

        Returns immediately with a document ID and ``"pending"`` status.
        Use :meth:`wait_for_ready` to poll until processing completes.
        """
        return await self._transport.ingest_document(
            source, filename, content_type, metadata, idempotency_key
        )

    async def get_document(self, document_id: str) -> Document:
        """Get document metadata and processing status."""
        return await self._transport.get_document(document_id)

    async def list_documents(
        self,
        *,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
        status: Optional[str] = None,
    ) -> ListDocumentsResponse:
        """List documents with optional filtering and cursor-based pagination."""
        return await self._transport.list_documents(limit, cursor, status)

    async def delete_document(self, document_id: str) -> None:
        """Delete a document and all its sections."""
        await self._transport.delete_document(document_id)

    # ── Tree & Sections ──

    async def get_document_tree(self, document_id: str) -> DocumentTree:
        """Get the hierarchical document tree."""
        return await self._transport.get_document_tree(document_id)

    async def get_section(self, section_id: str) -> Section:
        """Fetch a single section with full content."""
        return await self._transport.get_section(section_id)

    async def get_sections(self, section_ids: List[str]) -> List[Section]:
        """Fetch multiple sections concurrently."""
        return list(
            await asyncio.gather(
                *[self._transport.get_section(sid) for sid in section_ids]
            )
        )

    # ── Query ──

    async def query(
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
        """
        return await self._transport.query(
            document_id,
            query,
            model,
            max_tokens,
            reserved_for_prompt,
            max_parallel_calls,
            max_sections,
        )

    async def query_stream(
        self,
        document_id: str,
        query: str,
        *,
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        reserved_for_prompt: Optional[int] = None,
        max_parallel_calls: Optional[int] = None,
        max_sections: Optional[int] = None,
    ) -> AsyncIterator[QueryStreamEvent]:
        """
        Stream query results in real-time.

        Yields events as retrieval progresses.
        """
        async for event in self._transport.query_stream(
            document_id,
            query,
            model,
            max_tokens,
            reserved_for_prompt,
            max_parallel_calls,
            max_sections,
        ):
            yield event

    # ── Polling ──

    async def wait_for_ready(
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

        Raises:
            DocumentFailedError: If the document fails processing.
            TimeoutError: If the timeout is exceeded.
        """
        loop = asyncio.get_event_loop()
        deadline = loop.time() + timeout

        while loop.time() < deadline:
            await asyncio.sleep(poll_interval)
            doc = await self.get_document(document_id)

            if on_progress:
                on_progress(doc.status)

            if doc.status == "ready":
                return doc

            if doc.status == "failed":
                raise DocumentFailedError(
                    f"Document processing failed: {doc.error_message or 'Unknown error'}"
                )

            poll_interval = min(poll_interval * 1.5, 10.0)

        raise TimeoutError(
            f"Document {document_id} did not become ready within {timeout}s"
        )

    # ── Lifecycle ──

    async def close(self) -> None:
        """Close the client and release resources."""
        await self._transport.close()

    async def __aenter__(self) -> "AsyncVectorlessClient":
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()
