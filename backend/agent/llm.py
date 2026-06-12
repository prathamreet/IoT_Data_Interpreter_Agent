"""Claude client provider.

Centralises construction so every caller degrades gracefully when no API key
is configured — `get_async_client()` simply returns None and callers fall back
to deterministic output. The app never hard-depends on network access.
"""

from __future__ import annotations

import functools

from ..config import settings

try:  # anthropic is listed in requirements but treat as optional at runtime
    from anthropic import AsyncAnthropic
except Exception:  # pragma: no cover
    AsyncAnthropic = None  # type: ignore


@functools.lru_cache(maxsize=1)
def get_async_client():
    """Return a cached AsyncAnthropic client, or None if unavailable."""
    if not settings.llm_enabled or AsyncAnthropic is None:
        return None
    try:
        return AsyncAnthropic(api_key=settings.anthropic_api_key)
    except Exception:  # pragma: no cover
        return None


def llm_available() -> bool:
    return get_async_client() is not None
