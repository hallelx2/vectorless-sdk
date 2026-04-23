from __future__ import annotations

from abc import ABC, abstractmethod
from typing import BinaryIO, Dict, Iterator, AsyncIterator, Optional, Union

from pathlib import Path

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


class Transport(ABC):
    """
    Abstract synchronous transport.

    Implemented by HttpTransport and ConnectTransport.
    """

    # ── Health ──

    @abstractmethod
    def health(self) -> HealthResponse: ...

    @abstractmethod
    def version(self) -> VersionResponse: ...

    # ── Documents ──

    @abstractmethod
    def ingest_document(
        self,
        source: Union[str, bytes, BinaryIO, Path],
        filename: Optional[str] = None,
        content_type: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
        idempotency_key: Optional[str] = None,
    ) -> IngestDocumentResponse: ...

    @abstractmethod
    def get_document(self, document_id: str) -> Document: ...

    @abstractmethod
    def list_documents(
        self,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
        status: Optional[str] = None,
    ) -> ListDocumentsResponse: ...

    @abstractmethod
    def delete_document(self, document_id: str) -> None: ...

    @abstractmethod
    def get_document_tree(self, document_id: str) -> DocumentTree: ...

    # ── Sections ──

    @abstractmethod
    def get_section(self, section_id: str) -> Section: ...

    # ── Query ──

    @abstractmethod
    def query(
        self,
        document_id: str,
        query: str,
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        reserved_for_prompt: Optional[int] = None,
        max_parallel_calls: Optional[int] = None,
        max_sections: Optional[int] = None,
    ) -> QueryResponse: ...

    @abstractmethod
    def query_stream(
        self,
        document_id: str,
        query: str,
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        reserved_for_prompt: Optional[int] = None,
        max_parallel_calls: Optional[int] = None,
        max_sections: Optional[int] = None,
    ) -> Iterator[QueryStreamEvent]: ...

    # ── Lifecycle ──

    @abstractmethod
    def close(self) -> None: ...


class AsyncTransport(ABC):
    """
    Abstract asynchronous transport.

    Implemented by AsyncHttpTransport and AsyncConnectTransport.
    """

    # ── Health ──

    @abstractmethod
    async def health(self) -> HealthResponse: ...

    @abstractmethod
    async def version(self) -> VersionResponse: ...

    # ── Documents ──

    @abstractmethod
    async def ingest_document(
        self,
        source: Union[str, bytes, BinaryIO, Path],
        filename: Optional[str] = None,
        content_type: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
        idempotency_key: Optional[str] = None,
    ) -> IngestDocumentResponse: ...

    @abstractmethod
    async def get_document(self, document_id: str) -> Document: ...

    @abstractmethod
    async def list_documents(
        self,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
        status: Optional[str] = None,
    ) -> ListDocumentsResponse: ...

    @abstractmethod
    async def delete_document(self, document_id: str) -> None: ...

    @abstractmethod
    async def get_document_tree(self, document_id: str) -> DocumentTree: ...

    # ── Sections ──

    @abstractmethod
    async def get_section(self, section_id: str) -> Section: ...

    # ── Query ──

    @abstractmethod
    async def query(
        self,
        document_id: str,
        query: str,
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        reserved_for_prompt: Optional[int] = None,
        max_parallel_calls: Optional[int] = None,
        max_sections: Optional[int] = None,
    ) -> QueryResponse: ...

    @abstractmethod
    async def query_stream(
        self,
        document_id: str,
        query: str,
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        reserved_for_prompt: Optional[int] = None,
        max_parallel_calls: Optional[int] = None,
        max_sections: Optional[int] = None,
    ) -> AsyncIterator[QueryStreamEvent]: ...

    # ── Lifecycle ──

    @abstractmethod
    async def close(self) -> None: ...
