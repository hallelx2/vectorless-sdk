from __future__ import annotations

from typing import Any, BinaryIO, Dict, Iterator, AsyncIterator, Optional, Type, Union

from pathlib import Path

import httpx
from pydantic import BaseModel

from vectorless._config import VectorlessConfig
from vectorless._retry import sync_retry, async_retry
from vectorless._upload import prepare_multipart_upload
from vectorless._streaming import parse_sse_stream, parse_sse_stream_async
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


def _parse_error(response: httpx.Response) -> VectorlessError:
    """Convert an HTTP error response to a typed VectorlessError."""
    request_id = response.headers.get("x-request-id")
    try:
        body = response.json()
        error_obj = body.get("error", {})
        if isinstance(error_obj, str):
            message = error_obj
            field_errors = None
        else:
            message = error_obj.get(
                "message", f"Request failed: {response.status_code}"
            )
            field_errors = error_obj.get("field_errors")
    except Exception:
        message = f"Request failed with status {response.status_code}"
        field_errors = None

    status = response.status_code
    if status == 400:
        return ValidationError(message, field_errors, request_id)
    if status == 401:
        return AuthenticationError(message, request_id)
    if status == 403:
        return PermissionDeniedError(message, request_id)
    if status == 404:
        return NotFoundError(message, request_id)
    if status == 409:
        return ConflictError(message, request_id)
    if status == 429:
        retry_after_header = response.headers.get("retry-after")
        retry_after = float(retry_after_header) if retry_after_header else None
        return RateLimitError(message, retry_after, request_id)
    if status in (408, 504):
        return VLTimeoutError(message, request_id)
    if status >= 500:
        return ServerError(message, request_id)
    return VectorlessError(message, status, "unknown", request_id)


def _build_headers(config: VectorlessConfig) -> Dict[str, str]:
    """Build default request headers."""
    headers: Dict[str, str] = {
        "User-Agent": f"vectorless-python/{__version__}",
    }
    if config.api_key:
        headers["Authorization"] = f"Bearer {config.api_key}"
    if config.store:
        headers["X-Vectorless-Store"] = config.store
    return headers


def _build_query_body(
    document_id: str,
    query: str,
    model: Optional[str] = None,
    max_tokens: Optional[int] = None,
    reserved_for_prompt: Optional[int] = None,
    max_parallel_calls: Optional[int] = None,
    max_sections: Optional[int] = None,
) -> Dict[str, Any]:
    """Build the JSON body for a query request."""
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


# ── Synchronous HTTP Transport ──


class HttpTransport(Transport):
    """
    HTTP/REST transport (synchronous).

    Talks to the Vectorless server via standard REST endpoints.
    Streaming queries use Server-Sent Events (SSE).
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
        return self._get("/v1/health", HealthResponse)

    def version(self) -> VersionResponse:
        return self._get("/v1/version", VersionResponse)

    # ── Documents ──

    def ingest_document(
        self,
        source: Union[str, bytes, BinaryIO, Path],
        filename: Optional[str] = None,
        content_type: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
        idempotency_key: Optional[str] = None,
    ) -> IngestDocumentResponse:
        files, data = prepare_multipart_upload(source, filename, content_type, metadata)
        extra_headers: Dict[str, str] = {}
        if idempotency_key:
            extra_headers["Idempotency-Key"] = idempotency_key

        def _do() -> IngestDocumentResponse:
            resp = self._client.post(
                "/v1/documents",
                files=files,
                data=data,
                headers=extra_headers or None,
            )
            if not resp.is_success:
                raise _parse_error(resp)
            return IngestDocumentResponse.model_validate(resp.json())

        return sync_retry(_do, self._config.max_retries, self._config.retry_delay)

    def get_document(self, document_id: str) -> Document:
        return self._get(f"/v1/documents/{document_id}", Document)

    def list_documents(
        self,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
        status: Optional[str] = None,
    ) -> ListDocumentsResponse:
        params: Dict[str, str] = {}
        if limit is not None:
            params["limit"] = str(limit)
        if cursor:
            params["cursor"] = cursor
        if status:
            params["status"] = status
        return self._get("/v1/documents", ListDocumentsResponse, params=params)

    def delete_document(self, document_id: str) -> None:
        def _do() -> None:
            resp = self._client.delete(f"/v1/documents/{document_id}")
            if not resp.is_success:
                raise _parse_error(resp)

        sync_retry(_do, self._config.max_retries, self._config.retry_delay)

    def get_document_tree(self, document_id: str) -> DocumentTree:
        return self._get(f"/v1/documents/{document_id}/tree", DocumentTree)

    # ── Sections ──

    def get_section(self, section_id: str) -> Section:
        return self._get(f"/v1/sections/{section_id}", Section)

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

        def _do() -> QueryResponse:
            resp = self._client.post("/v1/query", json=body)
            if not resp.is_success:
                raise _parse_error(resp)
            return QueryResponse.model_validate(resp.json())

        return sync_retry(_do, self._config.max_retries, self._config.retry_delay)

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
            "/v1/query/stream",
            json=body,
            headers={"Accept": "text/event-stream"},
        ) as resp:
            if not resp.is_success:
                resp.read()
                raise _parse_error(resp)
            yield from parse_sse_stream(resp)

    # ── Lifecycle ──

    def close(self) -> None:
        self._client.close()

    # ── Internal ──

    def _get(
        self,
        path: str,
        model: Type[BaseModel],
        params: Optional[Dict[str, str]] = None,
    ) -> Any:
        def _do() -> Any:
            resp = self._client.get(path, params=params)
            if not resp.is_success:
                raise _parse_error(resp)
            if resp.status_code == 204:
                return None
            return model.model_validate(resp.json())

        return sync_retry(_do, self._config.max_retries, self._config.retry_delay)


# ── Asynchronous HTTP Transport ──


class AsyncHttpTransport(AsyncTransport):
    """
    HTTP/REST transport (asynchronous).

    Async counterpart of HttpTransport using httpx.AsyncClient.
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
        return await self._get("/v1/health", HealthResponse)

    async def version(self) -> VersionResponse:
        return await self._get("/v1/version", VersionResponse)

    # ── Documents ──

    async def ingest_document(
        self,
        source: Union[str, bytes, BinaryIO, Path],
        filename: Optional[str] = None,
        content_type: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
        idempotency_key: Optional[str] = None,
    ) -> IngestDocumentResponse:
        files, data = prepare_multipart_upload(source, filename, content_type, metadata)
        extra_headers: Dict[str, str] = {}
        if idempotency_key:
            extra_headers["Idempotency-Key"] = idempotency_key

        async def _do() -> IngestDocumentResponse:
            resp = await self._client.post(
                "/v1/documents",
                files=files,
                data=data,
                headers=extra_headers or None,
            )
            if not resp.is_success:
                raise _parse_error(resp)
            return IngestDocumentResponse.model_validate(resp.json())

        return await async_retry(
            _do, self._config.max_retries, self._config.retry_delay
        )

    async def get_document(self, document_id: str) -> Document:
        return await self._get(f"/v1/documents/{document_id}", Document)

    async def list_documents(
        self,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
        status: Optional[str] = None,
    ) -> ListDocumentsResponse:
        params: Dict[str, str] = {}
        if limit is not None:
            params["limit"] = str(limit)
        if cursor:
            params["cursor"] = cursor
        if status:
            params["status"] = status
        return await self._get("/v1/documents", ListDocumentsResponse, params=params)

    async def delete_document(self, document_id: str) -> None:
        async def _do() -> None:
            resp = await self._client.delete(f"/v1/documents/{document_id}")
            if not resp.is_success:
                raise _parse_error(resp)

        await async_retry(_do, self._config.max_retries, self._config.retry_delay)

    async def get_document_tree(self, document_id: str) -> DocumentTree:
        return await self._get(f"/v1/documents/{document_id}/tree", DocumentTree)

    # ── Sections ──

    async def get_section(self, section_id: str) -> Section:
        return await self._get(f"/v1/sections/{section_id}", Section)

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

        async def _do() -> QueryResponse:
            resp = await self._client.post("/v1/query", json=body)
            if not resp.is_success:
                raise _parse_error(resp)
            return QueryResponse.model_validate(resp.json())

        return await async_retry(
            _do, self._config.max_retries, self._config.retry_delay
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
            "/v1/query/stream",
            json=body,
            headers={"Accept": "text/event-stream"},
        ) as resp:
            if not resp.is_success:
                await resp.aread()
                raise _parse_error(resp)
            async for event in parse_sse_stream_async(resp):
                yield event

    # ── Lifecycle ──

    async def close(self) -> None:
        await self._client.aclose()

    # ── Internal ──

    async def _get(
        self,
        path: str,
        model: Type[BaseModel],
        params: Optional[Dict[str, str]] = None,
    ) -> Any:
        async def _do() -> Any:
            resp = await self._client.get(path, params=params)
            if not resp.is_success:
                raise _parse_error(resp)
            if resp.status_code == 204:
                return None
            return model.model_validate(resp.json())

        return await async_retry(
            _do, self._config.max_retries, self._config.retry_delay
        )
