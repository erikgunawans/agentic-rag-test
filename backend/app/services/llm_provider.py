"""LLM Provider Client (D-49..D-58, PROVIDER-01..07, RESOLVE-03).

Single class for all auxiliary LLM calls in v1.0:
  - entity_resolution (Phase 3 — this milestone)
  - missed_scan, fuzzy_deanon (Phase 4 forward-compat)
  - title_gen, metadata (Phase 4-6 forward-compat)

Provider awareness:
  - local: AsyncOpenAI(base_url=settings.local_llm_base_url, api_key="not-needed")
    sees raw real content per FR-9.2 (no third-party egress).
  - cloud: AsyncOpenAI(base_url=settings.cloud_llm_base_url, api_key=settings.cloud_llm_api_key)
    payload passed through egress_filter() BEFORE call (D-53..D-56). On trip,
    raises _EgressBlocked which the caller's algorithmic-fallback wrapper catches.

Resolution order (D-51):
  1. <FEATURE>_LLM_PROVIDER env var
  2. system_settings.<feature>_llm_provider column
  3. LLM_PROVIDER env var
  4. system_settings.llm_provider column
  5. default = "local"

Logging invariant (D-55 / D-63 / B4):
  - Resolved-provider INFO log line on every call (audit for OBS-03).
  - Egress trip WARNING line uses counts + 8-char SHA-256 hashes only.
  - Never log raw values.
"""
from __future__ import annotations

import json
import logging
import os
import time
from typing import Literal, TYPE_CHECKING

from openai import AsyncOpenAI

from app.config import get_settings
from app.services.redaction.egress import (
    EgressResult,
    _EgressBlocked,
    egress_filter,
)
from app.services.system_settings_service import get_system_settings
from app.services.tracing_service import traced

if TYPE_CHECKING:
    from app.services.redaction.registry import ConversationRegistry

logger = logging.getLogger(__name__)

# Five features — Phase 3 ships entity_resolution; the rest are forward-compat
# for Phase 4 / Phase 5 / Phase 6 (D-49 invariant: one client surface for all).
_Feature = Literal[
    "entity_resolution",
    "missed_scan",
    "fuzzy_deanon",
    "title_gen",
    "metadata",
]

_VALID_PROVIDERS = ("local", "cloud")


def _resolve_provider(feature: str) -> tuple[Literal["local", "cloud"], str]:
    """D-51 resolution order. Returns (provider, source) for OBS-03 audit logging.

    Source values: 'feature_env' | 'feature_db' | 'global_env' | 'global_db' | 'default'.
    Bad enum values at any layer are skipped (treated as unset) — defense in
    depth even though D-60's API + DB CHECKs prevent them in practice.
    """
    feature_upper = feature.upper()

    # 1. Feature-specific env var.
    feature_env = os.getenv(f"{feature_upper}_LLM_PROVIDER")
    if feature_env in _VALID_PROVIDERS:
        return feature_env, "feature_env"  # type: ignore[return-value]

    # 2. Feature-specific DB column (60s TTL cache).
    db = get_system_settings()
    feature_db = db.get(f"{feature}_llm_provider") if isinstance(db, dict) else None
    if feature_db in _VALID_PROVIDERS:
        return feature_db, "feature_db"  # type: ignore[return-value]

    # 3. Global env var.
    global_env = os.getenv("LLM_PROVIDER")
    if global_env in _VALID_PROVIDERS:
        return global_env, "global_env"  # type: ignore[return-value]

    # 4. Global DB column.
    global_db = db.get("llm_provider") if isinstance(db, dict) else None
    if global_db in _VALID_PROVIDERS:
        return global_db, "global_db"  # type: ignore[return-value]

    # 5. Default.
    return "local", "default"


# --- Lazy AsyncOpenAI client cache (D-50). ---

_clients: dict[Literal["local", "cloud"], AsyncOpenAI] = {}


def _get_client(provider: Literal["local", "cloud"]) -> AsyncOpenAI:
    """Cached per-provider AsyncOpenAI client. Lazy on first call (D-50)."""
    if provider in _clients:
        return _clients[provider]
    settings = get_settings()
    if provider == "local":
        _clients[provider] = AsyncOpenAI(
            base_url=settings.local_llm_base_url,
            api_key="not-needed",  # LM Studio / Ollama require no key
            timeout=settings.llm_provider_timeout_seconds,
        )
    else:
        # cloud
        _clients[provider] = AsyncOpenAI(
            base_url=settings.cloud_llm_base_url,
            api_key=settings.cloud_llm_api_key or "missing-cloud-key",
            timeout=settings.llm_provider_timeout_seconds,
        )
    return _clients[provider]


def _model_for(provider: Literal["local", "cloud"]) -> str:
    settings = get_settings()
    return settings.local_llm_model if provider == "local" else settings.cloud_llm_model


def _parse_response_content(content: str | None) -> dict:
    """Best-effort JSON parse; falls back to a one-key wrapper dict.

    Callers (entity resolution, missed-PII scan, etc.) own their schema-level
    validation via Pydantic — this function just ensures call() always returns
    a dict so the caller doesn't crash on a non-JSON response.
    """
    if content is None:
        return {"raw": ""}
    try:
        parsed = json.loads(content)
        if isinstance(parsed, dict):
            return parsed
        return {"raw": content}
    except (json.JSONDecodeError, ValueError):
        return {"raw": content}


# --- Public client surface (D-49). ---


class LLMProviderClient:
    """Single class; all 5 future features dispatch through .call(feature=...).

    Public API:
        await client.call(
            feature="entity_resolution",
            messages=[{"role": "system", "content": "..."},
                      {"role": "user", "content": "..."}],
            registry=conversation_registry,             # required for cloud calls (D-56)
            provisional_surrogates={real: provisional}, # required for cloud first-turn (D-56)
        ) -> dict

    Behaviour:
        - local provider: bypasses egress filter (FR-9.2 — no third-party egress).
        - cloud provider: payload passes through egress_filter; trip raises
          _EgressBlocked WHICH PROPAGATES OUT to the caller's fallback wrapper
          (D-52 / D-54). The client itself does not catch it.
        - Exceptions (network / 5xx / EgressBlocked) propagate; caller decides
          on algorithmic fallback. NEVER re-raise to the chat loop (NFR-3).
    """

    @traced(name="llm_provider.call")
    async def call(
        self,
        feature: str,
        messages: list[dict],
        registry: "ConversationRegistry | None" = None,
        provisional_surrogates: dict[str, str] | None = None,
    ) -> dict:
        provider, source = _resolve_provider(feature)
        client = _get_client(provider)
        model = _model_for(provider)
        started = time.monotonic()
        thread_id = registry.thread_id if registry is not None else "-"

        # Cloud-mode pre-flight egress filter (D-53..D-56).
        if provider == "cloud" and registry is not None:
            payload_str = json.dumps(messages, ensure_ascii=False)
            result = egress_filter(payload_str, registry, provisional_surrogates)
            if result.tripped:
                # D-54: do NOT call cloud — raise _EgressBlocked carrying the
                # forensic-correlation hashes for the caller's fallback wrapper.
                latency_ms = int((time.monotonic() - started) * 1000)
                logger.info(
                    "llm_provider_call event=llm_provider_call "
                    "thread_id=%s feature=%s provider=%s source=%s success=False "
                    "latency_ms=%d egress_tripped=True",
                    thread_id, feature, provider, source, latency_ms,
                )
                raise _EgressBlocked(result)

        try:
            response = await client.chat.completions.create(
                model=model,
                messages=messages,
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content if response.choices else None
            parsed = _parse_response_content(content)
            latency_ms = int((time.monotonic() - started) * 1000)
            # D-63 INFO-level resolved-provider audit.
            logger.info(
                "llm_provider_call event=llm_provider_call "
                "thread_id=%s feature=%s provider=%s source=%s success=True latency_ms=%d",
                thread_id, feature, provider, source, latency_ms,
            )
            return parsed
        except _EgressBlocked:
            # Already logged above; re-raise.
            raise
        except Exception as exc:  # SDK error, timeout, network — let caller decide.
            latency_ms = int((time.monotonic() - started) * 1000)
            logger.info(
                "llm_provider_call event=llm_provider_call "
                "thread_id=%s feature=%s provider=%s source=%s success=False latency_ms=%d "
                "error_type=%s",
                thread_id, feature, provider, source, latency_ms, type(exc).__name__,
            )
            raise
