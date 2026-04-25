"""Pluggable tracing service.

Replaces the prior hardcoded LangSmith wiring with a provider-switching shim that
selects a backend at IMPORT TIME based on the `TRACING_PROVIDER` environment
variable:

- ``langsmith`` — wraps ``langsmith.traceable(name=...)``; ``configure_tracing()``
  preserves the original three env-var assignments (``LANGCHAIN_TRACING_V2``,
  ``LANGCHAIN_PROJECT``, ``LANGSMITH_API_KEY``).
- ``langfuse`` — wraps ``langfuse.observe(name=...)``. The langfuse package is a
  hard dependency added in Plan 03; if it is not installed when this provider is
  selected, the import fails fast with a clear ``RuntimeError``.
- ``""`` / unset / ``"none"`` — no-op decorator with zero per-call overhead.
- Any other value — logged as WARNING and treated as no-op.

Public surface: ``configure_tracing()`` and ``traced(name=...)``.

The ``@traced`` decorator supports BOTH bare and parenthesised forms so existing
call sites that used the bare-decorator pattern (no parens) keep working::

    @traced
    async def f(): ...

    @traced(name="my_span")
    async def g(): ...

Decisions: see Phase 1 CONTEXT D-16, D-17, D-18.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Callable

from app.config import get_settings

logger = logging.getLogger(__name__)

__all__ = ["configure_tracing", "traced"]


def _resolve_provider() -> str:
    """Read TRACING_PROVIDER once at import time.

    Falls back to ``os.getenv`` because ``settings.tracing_provider`` is added in
    Plan 02; we tolerate its absence here.
    """
    settings = get_settings()
    raw = getattr(settings, "tracing_provider", None) or os.getenv("TRACING_PROVIDER", "")
    return raw.strip().lower()


_PROVIDER = _resolve_provider()


# ---------------------------------------------------------------------------
# Provider-specific bootstrap (resolved at import time)
# ---------------------------------------------------------------------------

if _PROVIDER == "langsmith":
    # Bind langsmith's traceable so _wrap can call it without re-importing.
    import langsmith as _langsmith

    def _wrap(fn: Callable[..., Any], name: str) -> Callable[..., Any]:
        return _langsmith.traceable(name=name)(fn)

elif _PROVIDER == "langfuse":
    # langfuse is a hard dependency added by Plan 03. If selected without the
    # package installed, fail fast with a clear message.
    try:
        from langfuse import observe as _lf_observe  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover — exercised only on misconfigured deploys
        raise RuntimeError(
            "TRACING_PROVIDER=langfuse but langfuse package not installed; "
            "check requirements.txt"
        ) from exc

    def _wrap(fn: Callable[..., Any], name: str) -> Callable[..., Any]:
        return _lf_observe(name=name)(fn)

else:
    # Empty / "none" / unknown → no-op. Unknown values get a warning so a typo'd
    # env var doesn't silently disable observability.
    if _PROVIDER not in ("", "none"):
        logger.warning(
            "Unknown TRACING_PROVIDER=%s — disabling tracing", _PROVIDER
        )

    def _wrap(fn: Callable[..., Any], name: str) -> Callable[..., Any]:
        return fn


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def configure_tracing() -> None:
    """Bootstrap the configured tracing provider.

    Called from FastAPI ``lifespan`` at startup. No-op for empty / unknown
    providers; for ``langfuse`` the SDK reads its own env vars
    (``LANGFUSE_PUBLIC_KEY``, ``LANGFUSE_SECRET_KEY``, ``LANGFUSE_HOST``) so
    nothing extra is needed here.
    """
    if _PROVIDER == "langsmith":
        settings = get_settings()
        if not settings.langsmith_api_key:
            return
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGCHAIN_PROJECT"] = settings.langsmith_project
        os.environ["LANGSMITH_API_KEY"] = settings.langsmith_api_key
        print(
            f"LangSmith tracing enabled — project: {settings.langsmith_project}"
        )
        return

    if _PROVIDER == "langfuse":
        # The langfuse SDK auto-configures from LANGFUSE_* env vars. Nothing to
        # do here — successful module import already proved the package is
        # available.
        logger.info("Langfuse tracing enabled (auto-config from env)")
        return

    # Empty / none / unknown — explicit log so operators know tracing is off.
    logger.info("Tracing disabled (TRACING_PROVIDER=%s)", _PROVIDER or "")


def traced(arg: Any = None, *, name: str | None = None):
    """Decorator that wraps a function with the configured tracing provider.

    Supports both forms:

    - ``@traced`` (bare, no parens) — span name defaults to ``fn.__name__``.
    - ``@traced(name="my_span")`` — explicit span name.

    The provider is resolved at import time (see ``_PROVIDER``); the per-call
    cost is one Python attribute lookup plus the underlying provider's
    decoration cost when tracing is enabled, or a single function call when
    disabled.
    """
    # Bare form: @traced applied directly to a function.
    if callable(arg) and name is None:
        fn = arg
        return _wrap(fn, name=fn.__name__)

    # Parenthesised form: @traced(name="x") or @traced().
    resolved_name = name

    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        return _wrap(fn, name=resolved_name or fn.__name__)

    return decorator
