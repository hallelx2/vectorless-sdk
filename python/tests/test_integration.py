"""
Integration tests for the Vectorless Python SDK.

Prerequisites:
    cd vectorless-sdk && docker compose up -d

Run:
    VECTORLESS_API_KEY=vl_test_sk_1234567890abcdef pytest tests/test_integration.py -v -s
"""
from __future__ import annotations

import pytest

from vectorless import (
    VectorlessClient,
    AsyncVectorlessClient,
    AuthenticationError,
    NotFoundError,
)
from tests.conftest import SAMPLE_MARKDOWN


# ── Parametrize over both transports ──


@pytest.fixture(params=["http", "connect"])
def transport(request: pytest.FixtureRequest) -> str:
    return request.param


@pytest.fixture
def client(base_url: str, api_key: str, transport: str) -> VectorlessClient:
    c = VectorlessClient(
        base_url=base_url,
        api_key=api_key,
        transport=transport,
        timeout=60.0,
    )
    yield c
    c.close()


# ── Health ──


class TestHealth:
    def test_health_check(self, client: VectorlessClient) -> None:
        health = client.health()
        assert health.status == "ok"

    def test_version(self, client: VectorlessClient) -> None:
        version = client.version()
        assert version.version
        assert isinstance(version.version, str)


# ── Auth ──


class TestAuth:
    def test_no_api_key_returns_401(
        self, base_url: str, transport: str
    ) -> None:
        no_auth = VectorlessClient(
            base_url=base_url,
            transport=transport,
        )
        with pytest.raises(AuthenticationError) as exc_info:
            no_auth.list_documents()
        assert exc_info.value.status == 401
        no_auth.close()

    def test_wrong_api_key_returns_401(
        self, base_url: str, transport: str
    ) -> None:
        bad = VectorlessClient(
            base_url=base_url,
            api_key="vl_wrong_key",
            transport=transport,
        )
        with pytest.raises(AuthenticationError) as exc_info:
            bad.list_documents()
        assert exc_info.value.status == 401
        bad.close()


# ── Error Handling ──


class TestErrors:
    def test_get_missing_document(self, client: VectorlessClient) -> None:
        with pytest.raises(NotFoundError) as exc_info:
            client.get_document("doc_nonexistent_12345")
        assert exc_info.value.status == 404

    def test_get_missing_section(self, client: VectorlessClient) -> None:
        with pytest.raises(NotFoundError) as exc_info:
            client.get_section("sec_nonexistent_12345")
        assert exc_info.value.status == 404


# ── Document Lifecycle ──


class TestDocumentLifecycle:
    @pytest.mark.timeout(180)
    def test_full_lifecycle(self, client: VectorlessClient, transport: str) -> None:
        """
        Ingest → poll → tree → section → query → delete.
        """
        # 1. Ingest
        result = client.ingest_document(
            SAMPLE_MARKDOWN.encode("utf-8"),
            filename="ml-guide.md",
            content_type="text/markdown",
            metadata={"topic": "machine-learning", "sdk_test": "true"},
        )
        assert result.document_id
        assert result.status == "pending"
        doc_id = result.document_id

        # 2. Wait for ready
        doc = client.wait_for_ready(
            doc_id,
            timeout=120.0,
            poll_interval=3.0,
            on_progress=lambda s: print(f"  [{transport}] {doc_id}: {s}"),
        )
        assert doc.status == "ready"
        assert doc.id == doc_id
        assert doc.title

        # 3. Document tree
        tree = client.get_document_tree(doc_id)
        assert tree.document_id == doc_id
        assert len(tree.sections) > 0

        root_sections = [s for s in tree.sections if not s.parent_id]
        assert len(root_sections) > 0

        first = tree.sections[0]
        assert first.id
        assert first.title
        assert isinstance(first.depth, int)
        assert isinstance(first.tokens, int)

        # 4. Single section fetch
        section = client.get_section(first.id)
        assert section.id == first.id
        assert section.document_id == doc_id
        assert section.content
        assert isinstance(section.token_count, int)

        # 5. Batch section fetch
        ids = [s.id for s in tree.sections[:3]]
        sections = client.get_sections(ids)
        assert len(sections) == len(ids)

        # 6. Query
        qr = client.query(doc_id, "What is supervised learning?")
        assert qr.document_id == doc_id
        assert qr.query == "What is supervised learning?"
        assert len(qr.sections) > 0
        assert qr.strategy
        assert isinstance(qr.elapsed_ms, int)

        for qs in qr.sections:
            assert qs.id
            assert qs.content

        # 7. List documents
        page = client.list_documents(status="ready", limit=10)
        assert len(page.items) > 0
        found = any(d.id == doc_id for d in page.items)
        assert found, f"Document {doc_id} not found in list"

        # 8. Delete
        client.delete_document(doc_id)

        # 9. Verify deleted
        with pytest.raises(NotFoundError):
            client.get_document(doc_id)


# ── Async Client ──


class TestAsyncClient:
    @pytest.mark.timeout(60)
    @pytest.mark.asyncio
    async def test_health_async(
        self, base_url: str, api_key: str, transport: str
    ) -> None:
        async with AsyncVectorlessClient(
            base_url=base_url,
            api_key=api_key,
            transport=transport,
        ) as client:
            health = await client.health()
            assert health.status == "ok"

            version = await client.version()
            assert version.version

    @pytest.mark.timeout(60)
    @pytest.mark.asyncio
    async def test_auth_error_async(
        self, base_url: str, transport: str
    ) -> None:
        async with AsyncVectorlessClient(
            base_url=base_url,
            transport=transport,
        ) as client:
            with pytest.raises(AuthenticationError):
                await client.list_documents()
