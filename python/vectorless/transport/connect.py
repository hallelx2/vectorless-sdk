from __future__ import annotations

from typing import Any, BinaryIO, Dict, Iterator, AsyncIterator, Optional, Type, Union

from pathlib import Path

import httpx
from pydantic import BaseModel

from vectorless._config import VectorlessConfig
from vectorless._retry import sync_retry, async_retry
from vectorless._upload import prepare_json_payload
from vectorless._streaming import parse_connect_stream, parse_connect_stream_async
from vectorless._version import __version__
from vectorless.transport.base import Transport, AsyncTransport
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
from vectorless.errors import (
    VectorlessError,
    AuthenticationError,
    PermissionDeniedError,
    NotFoundError,
    RateLimitError,
    ValidationError,
    ConflictError,
    ServerError,
    TimeoutError as VLTimeoutError,
)


def _build_headers(config: VectorlessConfig) -> Dict[str, str]:
    headers: Dict[str, str] = {
        "User-Agent": f"vectorless-python/{__version__}",
        "Content-Type": "application/json",
        "Connect-Protocol-Version": "1",
    }
    if config.api_key:
        headers["Authorization"] = f"Bearer {config.api_key}"
    if config.store:
        headers["X-Vectorless-Store"] = config.store
    return headers


def _parse_connect_error(response: httpx.Response) -> VectorlessError:
    """Convert a Connect error response to a typed VectorlessError."""
    request_id = response.headers.get("x-request-id")
    try:
        body = response.json()
        message = body.get("message", f"RPC failed with HTTP {response.status_code}")
        code = body.get("code", "unknown")
    except Exception:
        message = f"RPC failed with HTTP {response.status_code}"
        code = "unknown"

    code_map = {
        "unauthenticated": lambda: AuthenticationError(message, request_id),
        "permission_denied": lambda: PermissionDeniedError(message, request_id),
        "not_found": lambda: NotFoundError(message, request_id),
        "invalid_argument": lambda: ValidationError(message, None, request_id),
        "already_exists": lambda: ConflictError(message, request_id),
        "resource_exhausted": lambda: RateLimitError(message, None, request_id),
        "deadline_exceeded": lambda: VLTimeoutError(message, request_id),
        "internal": lambda: ServerError(message, request_id),
        "unavailable": lambda: ServerError(message, request_id),
        "data_loss": lambda: ServerError(message, request_id),
    }

    factory = code_map.get(code)
    if factory:
        return factory()

    # Fallback to HTTP status mapping
    status = response.status_code
    if status == 400:
        return ValidationError(message, None, request_id)
    if status == 401:
        return AuthenticationError(message, request_id)
    if status == 403:
        return PermissionDeniedError(message, request_id)
    if status == 404:
        return NotFoundError(message, request_id)
    if status == 409:
        return ConflictError(message, request_id)
    if status == 429:
        return RateLimitError(message, None, request_id)
    if status in (408, 504):
        return VLTimeoutError(message, request_id)
    if status >= 500:
        return ServerError(message, request_id)
    return VectorlessError(message, status, code, request_id)


def _build_query_body(
    document_id: str,
    query: str,
    model: Optional[str] = None,
    max_tokens: Optional[int] = None,
    reserved_for_prompt: Optional[int] = None,
    max_parallel_calls: Optional[int] = None,
    max_sections: Optional[int] = None,
) -> Dict[str, Any]:
    body: Dict[str, Any] = {
        "document_id": document_id,
        "query": query,
    }
    if model is not None:
        body["model"] = model
    if max_tokens is not None:
        body["max_tokens"] = max_tokens
    if reserved_for_prompt is not None:
        body["reserved_for_prompt"] = reserved_for_prompt
    if max_parallel_calls is not None:
        body["max_parallel_calls"] = max_parallel_calls
    if max_sections is not None:
        body["max_sections"] = max_sections
    return body


# ── Synchronous Connect Transport ──


class ConnectTransport(Transport):
    """
    Connect/Protobuf transport (synchronous).

    Uses the ConnectRPC JSON protocol — every call is a POST to
    ``/{package}.{service}/{method}`` with ``Content-Type: application/json``.

    No code generation or protobuf tooling required.
    """

    def __init__(self, config: VectorlessConfig) -> None:
        self._config = config
        self._client = httpx.Client(
            base_url=config.base_url,
            headers=_build_headers(config),
            timeout=config.timeout,
        )

    # ── Health ──

    def health(self) -> HealthResponse:
        return self._unary("vectorless.v1.HealthService", "Check", {}, HealthResponse)

    def version(self) -> VersionResponse:
        return self._unary(
            "vectorless.v1.HealthService", "Version", {}, VersionResponse
        )

    # ── Documents ──

    def ingest_document(
        self,
        source: Union[str, bytes, BinaryIO, Path],
        filename: Optional[str] = None,
        content_type: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
        idempotency_key: Optional[str] = None,
    ) -> IngestDocumentResponse:
        payload = prepare_json_payload(source, filename, content_type, metadata)
        return self._unary(
            "vectorless.v1.DocumentsService",
            "CreateDocument",
            payload,
            IngestDocumentResponse,
        )

    def get_document(self, document_id: str) -> Document:
        return self._unary(
            "vectorless.v1.DocumentsService",
            "GetDocument",
            {"document_id": document_id},
            Document,
        )

    def list_documents(
        self,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
        status: Optional[str] = None,
    ) -> ListDocumentsResponse:
        request: Dict[str, Any] = {}
        if limit is not None:
            request["limit"] = limit
        if cursor:
            request["cursor"] = cursor
        if status:
            request["status"] = status

        # Connect returns {documents: [...], next_cursor: "..."} but
        # our ListDocumentsResponse uses {items: [...], next_cursor: "..."}
        def _do() -> ListDocumentsResponse:
            resp = self._client.post(
                "/vectorless.v1.DocumentsService/ListDocuments",
                json=request,
            )
            if not resp.is_success:
                raise _parse_connect_error(resp)
            data = resp.json()
            return ListDocumentsResponse(
                items=[Document.model_validate(d) for d in data.get("documents", [])],
                next_cursor=data.get("next_cursor"),
            )

        return sync_retry(_do, self._config.max_retries, self._config.retry_delay)

    def delete_document(self, document_id: str) -> None:
        def _do() -> None:
            resp = self._client.post(
                "/vectorless.v1.DocumentsService/DeleteDocument",
                json={"document_id": document_id},
            )
            if not resp.is_success:
                raise _parse_connect_error(resp)

        sync_retry(_do, self._config.max_retries, self._config.retry_delay)

    def get_document_tree(self, document_id: str) -> DocumentTree:
        return self._unary(
            "vectorless.v1.DocumentsService",
            "GetDocumentTree",
            {"document_id": document_id},
            DocumentTree,
        )

    # ── Sections ──

    def get_section(self, section_id: str) -> Section:
        return self._unary(
            "vectorless.v1.DocumentsService",
            "GetSection",
            {"section_id": section_id},
            Section,
        )

    # ── Query ──

    def query(
        self,
        document_id: str,
        query: str,
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        reserved_for_prompt: Optional[int] = None,
        max_parallel_calls: Optional[int] = None,
        max_sections: Optional[int] = None,
    ) -> QueryResponse:
        body = _build_query_body(
            document_id,
            query,
            model,
            max_tokens,
            reserved_for_prompt,
            max_parallel_calls,
            max_sections,
        )
        return self._unary("vectorless.v1.QueryService", "Query", body, QueryResponse)

    def query_stream(
        self,
        document_id: str,
        query: str,
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        reserved_for_prompt: Optional[int] = None,
        max_parallel_calls: Optional[int] = None,
        max_sections: Optional[int] = None,
    ) -> Iterator[QueryStreamEvent]:
        body = _build_query_body(
            document_id,
            query,
            model,
            max_tokens,
            reserved_for_prompt,
            max_parallel_calls,
            max_sections,
        )
        with self._client.stream(
            "POST",
            "/vectorless.v1.QueryService/QueryStream",
            json=body,
        ) as resp:
            if not resp.is_success:
                resp.read()
                raise _parse_connect_error(resp)
            yield from parse_connect_stream(resp)

    # ── Lifecycle ──

    def close(self) -> None:
        self._client.close()

    # ── Internal ──

    def _unary(
        self,
        service: str,
        method: str,
        request: Dict[str, Any],
        response_model: Type[BaseModel],
    ) -> Any:
        def _do() -> Any:
            resp = self._client.post(
                f"/{service}/{method}",
                json=request,
            )
            if not resp.is_success:
                raise _parse_connect_error(resp)
            return response_model.model_validate(resp.json())

        return sync_retry(_do, self._config.max_retries, self._config.retry_delay)


# ── Asynchronous Connect Transport ──


class AsyncConnectTransport(AsyncTransport):
    """
    Connect/Protobuf transport (asynchronous).

    Async counterpart of ConnectTransport.
    """

    def __init__(self, config: VectorlessConfig) -> None:
        self._config = config
        self._client = httpx.AsyncClient(
            base_url=config.base_url,
            headers=_build_headers(config),
            timeout=config.timeout,
        )

    # ── Health ──

    async def health(self) -> HealthResponse:
        return await self._unary(
            "vectorless.v1.HealthService", "Check", {}, HealthResponse
        )

    async def version(self) -> VersionResponse:
        return await self._unary(
            "vectorless.v1.HealthService", "Version", {}, VersionResponse
        )

    # ── Documents ──

    async def ingest_document(
        self,
        source: Union[str, bytes, BinaryIO, Path],
        filename: Optional[str] = None,
        content_type: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
        idempotency_key: Optional[str] = None,
    ) -> IngestDocumentResponse:
        payload = prepare_json_payload(source, filename, content_type, metadata)
        return await self._unary(
            "vectorless.v1.DocumentsService",
            "CreateDocument",
            payload,
            IngestDocumentResponse,
        )

    async def get_document(self, document_id: str) -> Document:
        return await self._unary(
            "vectorless.v1.DocumentsService",
            "GetDocument",
            {"document_id": document_id},
            Document,
        )

    async def list_documents(
        self,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
        status: Optional[str] = None,
    ) -> ListDocumentsResponse:
        request: Dict[str, Any] = {}
        if limit is not None:
            request["limit"] = limit
        if cursor:
            request["cursor"] = cursor
        if status:
            request["status"] = status

        async def _do() -> ListDocumentsResponse:
            resp = await self._client.post(
                "/vectorless.v1.DocumentsService/ListDocuments",
                json=request,
            )
            if not resp.is_success:
                raise _parse_connect_error(resp)
            data = resp.json()
            return ListDocumentsResponse(
                items=[Document.model_validate(d) for d in data.get("documents", [])],
                next_cursor=data.get("next_cursor"),
            )

        return await async_retry(
            _do, self._config.max_retries, self._config.retry_delay
        )

    async def delete_document(self, document_id: str) -> None:
        async def _do() -> None:
            resp = await self._client.post(
                "/vectorless.v1.DocumentsService/DeleteDocument",
                json={"document_id": document_id},
            )
            if not resp.is_success:
                raise _parse_connect_error(resp)

        await async_retry(_do, self._config.max_retries, self._config.retry_delay)

    async def get_document_tree(self, document_id: str) -> DocumentTree:
        return await self._unary(
            "vectorless.v1.DocumentsService",
            "GetDocumentTree",
            {"document_id": document_id},
            DocumentTree,
        )

    # ── Sections ──

    async def get_section(self, section_id: str) -> Section:
        return await self._unary(
            "vectorless.v1.DocumentsService",
            "GetSection",
            {"section_id": section_id},
            Section,
        )

    # ── Query ──

    async def query(
        self,
        document_id: str,
        query: str,
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        reserved_for_prompt: Optional[int] = None,
        max_parallel_calls: Optional[int] = None,
        max_sections: Optional[int] = None,
    ) -> QueryResponse:
        body = _build_query_body(
            document_id,
            query,
            model,
            max_tokens,
            reserved_for_prompt,
            max_parallel_calls,
            max_sections,
        )
        return await self._unary(
            "vectorless.v1.QueryService", "Query", body, QueryResponse
        )

    async def query_stream(
        self,
        document_id: str,
        query: str,
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        reserved_for_prompt: Optional[int] = None,
        max_parallel_calls: Optional[int] = None,
        max_sections: Optional[int] = None,
    ) -> AsyncIterator[QueryStreamEvent]:
        body = _build_query_body(
            document_id,
            query,
            model,
            max_tokens,
            reserved_for_prompt,
            max_parallel_calls,
            max_sections,
        )
        async with self._client.stream(
            "POST",
            "/vectorless.v1.QueryService/QueryStream",
            json=body,
        ) as resp:
            if not resp.is_success:
                await resp.aread()
                raise _parse_connect_error(resp)
            async for event in parse_connect_stream_async(resp):
                yield event

    # ── Lifecycle ──

    async def close(self) -> None:
        await self._client.aclose()

    # ── Internal ──

    async def _unary(
        self,
        service: str,
        method: str,
        request: Dict[str, Any],
        response_model: Type[BaseModel],
    ) -> Any:
        async def _do() -> Any:
            resp = await self._client.post(
                f"/{service}/{method}",
                json=request,
            )
            if not resp.is_success:
                raise _parse_connect_error(resp)
            return response_model.model_validate(resp.json())

        return await async_retry(
            _do, self._config.max_retries, self._config.retry_delay
        )
