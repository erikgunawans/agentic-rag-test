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
