from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional, Literal


@dataclass(frozen=True)
class VectorlessConfig:
    """Resolved SDK configuration."""

    api_key: Optional[str] = None
    base_url: str = "http://localhost:8080"
    transport: Literal["http", "connect"] = "http"
    timeout: float = 30.0
    max_retries: int = 3
    retry_delay: float = 0.5
    # store scopes every request to one store (sent as X-Vectorless-Store).
    # Only needed for org-wide keys; a store-bound key scopes automatically.
    store: Optional[str] = None


def resolve_config(
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    transport: Optional[Literal["http", "connect"]] = None,
    timeout: float = 30.0,
    max_retries: int = 3,
    retry_delay: float = 0.5,
    store: Optional[str] = None,
) -> VectorlessConfig:
    """
    Resolve SDK configuration from explicit args and environment variables.

    API key resolution order:
      1. Explicit ``api_key`` parameter
      2. ``VECTORLESS_API_KEY`` environment variable
      3. ``None`` (valid for self-hosted instances with auth disabled)
    """
    resolved_key = api_key or os.environ.get("VECTORLESS_API_KEY")

    return VectorlessConfig(
        api_key=resolved_key,
        base_url=(
            base_url or os.environ.get("VECTORLESS_BASE_URL") or "http://localhost:8080"
        ).rstrip("/"),
        transport=transport or "http",
        timeout=timeout,
        max_retries=max_retries,
        retry_delay=retry_delay,
        store=store or os.environ.get("VECTORLESS_STORE"),
    )
