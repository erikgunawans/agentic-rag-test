---
phase: 03-entity-resolution-llm-provider-configuration
plan: 04
type: execute
wave: 4
depends_on: [02, 03]
files_modified:
  - backend/app/services/llm_provider.py
autonomous: true
requirements_addressed: [PROVIDER-01, PROVIDER-02, PROVIDER-03, PROVIDER-04, PROVIDER-05, PROVIDER-07, RESOLVE-03]
must_haves:
  truths:
    - "llm_provider.py exposes class LLMProviderClient with one async public method `call(feature, messages, registry=None, provisional_surrogates=None) -> dict`"
    - "_resolve_provider(feature) -> tuple[provider, source] implements D-51 resolution order: feature_env > feature_db > global_env > global_db > default('local')"
    - "Cloud-mode call wraps the outbound payload through egress_filter; on EgressResult.tripped → raise _EgressBlocked (D-54)"
    - "Local-mode call bypasses the egress filter — operates on raw real content per FR-9.2"
    - "AsyncOpenAI clients lazily instantiated and cached in a module-level dict keyed by provider (D-50)"
    - "@traced decorator wraps the public call() method with span name `llm_provider.call` and resolved-provider/source attributes (D-49 / D-63)"
    - "Resolved-provider INFO-level audit log line emitted on every call (D-63 — feature, provider, source, success, latency_ms)"
  artifacts:
    - path: "backend/app/services/llm_provider.py"
      provides: "LLMProviderClient with provider-aware branching + egress filter integration"
      exports: ["LLMProviderClient"]
      min_lines: 180
  key_links:
    - from: "backend/app/services/llm_provider.py"
      to: "backend/app/services/redaction/egress.py"
      via: "egress_filter() + _EgressBlocked import"
      pattern: "from app\\.services\\.redaction\\.egress import"
    - from: "backend/app/services/llm_provider.py"
      to: "backend/app/config.py"
      via: "settings.cloud_llm_api_key + settings.local_llm_base_url + 5 per-feature override fields"
      pattern: "from app\\.config import (settings|get_settings)"
    - from: "backend/app/services/llm_provider.py"
      to: "backend/app/services/system_settings_service.py"
      via: "get_system_settings() — DB-backed override layer (D-51)"
      pattern: "from app\\.services\\.system_settings_service import get_system_settings"
    - from: "backend/app/services/llm_provider.py"
      to: "OpenAI Python SDK"
      via: "AsyncOpenAI client per provider (D-50)"
      pattern: "from openai import AsyncOpenAI"
---

<objective>
Ship `backend/app/services/llm_provider.py` — the single `LLMProviderClient` class with provider-aware branching, the D-51 resolution-order helper, egress-filter integration on the cloud path, and the OBS-03 resolved-provider audit log.

Purpose: Wave 4 — the security-critical primitive of Phase 3. Every cloud auxiliary call in v1.0 (entity resolution now; missed-PII scan, fuzzy de-anon, title gen, metadata in Phase 4) flows through this single point. Test surface: one class to mock, one place where the egress invariant lives.

Output: One new file at `backend/app/services/llm_provider.py` (~200 lines). NOT yet wired into redaction_service — Plan 03-05 does that.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phases/03-entity-resolution-llm-provider-configuration/03-CONTEXT.md
@.planning/phases/03-entity-resolution-llm-provider-configuration/03-PATTERNS.md
@.planning/phases/01-detection-anonymization-foundation/01-CONTEXT.md
@CLAUDE.md
@backend/app/config.py
@backend/app/services/embedding_service.py
@backend/app/services/tracing_service.py
@backend/app/services/system_settings_service.py
@backend/app/services/redaction/egress.py
@backend/app/services/redaction/registry.py

<interfaces>
<!-- Existing primitives this plan calls. Read once; no codebase exploration needed. -->

From backend/app/services/embedding_service.py (analog A — AsyncOpenAI shape):
- Pattern: `from openai import AsyncOpenAI` then `client = AsyncOpenAI(api_key=settings.openai_api_key)`. Phase 3 swaps `base_url` per provider.
- The SDK auto-handles timeouts, retries, async streaming; reuse it as-is.

From backend/app/services/tracing_service.py (Phase 1 D-16):
- Exposes `@traced` decorator; both bare (`@traced`) and parenthesised (`@traced(name="...")`) forms supported.
- Phase 3 D-49 uses the parenthesised form: `@traced(name="llm_provider.call")`.

From backend/app/services/system_settings_service.py (Phase 2 D-21 / SET-01):
- `get_system_settings() -> dict` — 60s TTL cache; returns the single-row system_settings as a dict keyed by column name.
- Cache invalidation on PATCH /admin/settings is already wired (admin_settings.py calls update_system_settings which invalidates).
- Phase 3 SC#5 depends on this 60s window: PATCH → wait 60s → next `_resolve_provider` call returns the new value.

From backend/app/services/redaction/egress.py (Plan 03-03 Task 3 output):
- `egress_filter(payload, registry, provisional) -> EgressResult` — pure function.
- `class EgressResult` frozen — fields: `tripped`, `match_count`, `entity_types`, `match_hashes`.
- `class _EgressBlocked(Exception)` — internal-only, carries `EgressResult`.

From backend/app/config.py (Plan 03-01 Task 1 output):
- `settings.llm_provider: Literal["local", "cloud"]` — default "local".
- `settings.entity_resolution_llm_provider: Literal["local", "cloud"] | None` — None means inherit.
- 4 more per-feature override fields: `missed_scan_llm_provider`, `title_gen_llm_provider`, `metadata_llm_provider`, `fuzzy_deanon_llm_provider`.
- `settings.local_llm_base_url`, `settings.local_llm_model`, `settings.cloud_llm_base_url`, `settings.cloud_llm_model`, `settings.cloud_llm_api_key`.
- `settings.llm_provider_timeout_seconds: int = 30`.
- `settings.llm_provider_fallback_enabled: bool = False`.

From backend/app/services/redaction/registry.py (Phase 2):
- `class ConversationRegistry` — `entries() -> list[EntityMapping]` is the only method egress_filter calls.
- The `LLMProviderClient.call()` accepts `registry: ConversationRegistry | None = None` (None means egress filter is bypassed — local mode or no-registry test fixture).

D-51 resolution order (verbatim from CONTEXT.md):
1. `<FEATURE>_LLM_PROVIDER` env var (e.g., `ENTITY_RESOLUTION_LLM_PROVIDER`) — wins.
2. `system_settings.<feature>_llm_provider` column (DB-level override).
3. `LLM_PROVIDER` global env var.
4. `system_settings.llm_provider` global column.
5. Default: `"local"`.
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Write backend/app/services/llm_provider.py — _resolve_provider helper</name>
  <files>backend/app/services/llm_provider.py</files>
  <behavior>
    - `_resolve_provider("entity_resolution")` returns `("cloud", "feature_env")` when env var `ENTITY_RESOLUTION_LLM_PROVIDER=cloud` is set.
    - Returns `("local", "feature_db")` when env is unset and `system_settings.entity_resolution_llm_provider == "local"`.
    - Returns `("cloud", "global_env")` when feature-specific env+db are unset and `LLM_PROVIDER=cloud` env is set.
    - Returns `("local", "global_db")` when only `system_settings.llm_provider` column is set to "local".
    - Returns `("local", "default")` when nothing is set.
    - Bad enum values in env / DB ARE SKIPPED (treated as unset) — Pydantic Literal at API edge + DB CHECK at DDL layer prevent these in practice (D-60); the helper still defends in depth.
  </behavior>
  <read_first>
    - backend/app/config.py (Plan 03-01 Task 1 output — the settings.llm_provider + per-feature override fields are read from here)
    - backend/app/services/system_settings_service.py (get_system_settings dict shape)
    - .planning/phases/03-entity-resolution-llm-provider-configuration/03-CONTEXT.md D-51
    - .planning/phases/03-entity-resolution-llm-provider-configuration/03-PATTERNS.md §"Provider-resolution helper"
  </read_first>
  <action>
Create `backend/app/services/llm_provider.py`. THIS TASK writes ONLY the imports + the `_resolve_provider` helper + the supporting `_FEATURES` literal type. The class body comes in Task 2.

File content (Task 1 portion — append the rest in Task 2):

```python
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
```

After writing this much, run an import smoke-test:
```bash
cd backend && source venv/bin/activate && python -c "
from app.services.llm_provider import _resolve_provider
import os
# Default path
os.environ.pop('ENTITY_RESOLUTION_LLM_PROVIDER', None)
os.environ.pop('LLM_PROVIDER', None)
provider, source = _resolve_provider('entity_resolution')
assert source in ('default', 'global_db', 'feature_db'), f'unexpected source on default: {source}'
# Feature env wins
os.environ['ENTITY_RESOLUTION_LLM_PROVIDER'] = 'cloud'
provider, source = _resolve_provider('entity_resolution')
assert provider == 'cloud' and source == 'feature_env', f'expected (cloud, feature_env), got ({provider}, {source})'
del os.environ['ENTITY_RESOLUTION_LLM_PROVIDER']
print('RESOLVE_OK')
"
```
  </action>
  <verify>
    <automated>cd backend && source venv/bin/activate && python -c "
from app.services.llm_provider import _resolve_provider
import os
os.environ.pop('ENTITY_RESOLUTION_LLM_PROVIDER', None)
os.environ.pop('LLM_PROVIDER', None)
os.environ['ENTITY_RESOLUTION_LLM_PROVIDER'] = 'cloud'
provider, source = _resolve_provider('entity_resolution')
assert provider == 'cloud' and source == 'feature_env'
del os.environ['ENTITY_RESOLUTION_LLM_PROVIDER']
os.environ['LLM_PROVIDER'] = 'cloud'
provider, source = _resolve_provider('entity_resolution')
assert provider == 'cloud' and source == 'global_env'
del os.environ['LLM_PROVIDER']
print('RESOLVE_OK')
" 2>&1 | grep -q "RESOLVE_OK"</automated>
  </verify>
  <acceptance_criteria>
    - File `backend/app/services/llm_provider.py` exists.
    - Contains the literal docstring header referencing `D-49..D-58`.
    - Contains `from openai import AsyncOpenAI`.
    - Contains `from app.services.redaction.egress import EgressResult, _EgressBlocked, egress_filter`.
    - Contains `from app.services.tracing_service import traced`.
    - Contains `from app.services.system_settings_service import get_system_settings`.
    - Contains `_Feature = Literal["entity_resolution", "missed_scan", "fuzzy_deanon", "title_gen", "metadata"]` (5 features per D-49).
    - Contains `def _resolve_provider(feature: str) -> tuple[Literal["local", "cloud"], str]:`.
    - The resolve helper checks `<FEATURE>_LLM_PROVIDER` env via `os.getenv(f"{feature_upper}_LLM_PROVIDER")`.
    - The resolve helper checks `<feature>_llm_provider` DB column via `get_system_settings().get(f"{feature}_llm_provider")`.
    - The resolve helper checks `LLM_PROVIDER` env var.
    - The resolve helper checks `llm_provider` DB column.
    - The default branch returns `("local", "default")`.
    - The smoke-test prints `RESOLVE_OK`.
  </acceptance_criteria>
  <done>llm_provider.py exists with imports + _resolve_provider helper + _Feature type alias; smoke-test passes.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Append LLMProviderClient class to llm_provider.py with cloud egress wrapper + algorithmic-fallback boundary</name>
  <files>backend/app/services/llm_provider.py</files>
  <behavior>
    - `LLMProviderClient().call(feature="entity_resolution", messages=[...], registry=None, provisional_surrogates=None)` resolves the provider via `_resolve_provider`, instantiates the AsyncOpenAI client, and dispatches.
    - Local-mode call: bypasses egress filter; passes `messages` directly to `client.chat.completions.create(...)`; returns `response.choices[0].message.content` parsed as JSON dict (or raw string in a one-key dict if not JSON).
    - Cloud-mode call: serialises `messages` via `json.dumps`, runs `egress_filter(payload, registry, provisional)`; if `tripped` raises `_EgressBlocked(result)` BEFORE any cloud call.
    - Cloud mode without egress trip: passes through to `client.chat.completions.create(...)`.
    - Cloud mode with `registry=None`: NO egress filter applied (only the in-flight `provisional_surrogates` are scanned, against an empty registry — caller's responsibility to pass either).
    - On `_EgressBlocked` the exception PROPAGATES OUT — the LLMProviderClient itself does NOT catch it. The redaction_service caller (Plan 03-05) catches and falls back to algorithmic. (D-52 / D-54 — the fallback wrapper lives at the call site, not in the client.)
    - Network / 5xx / SDK exceptions PROPAGATE OUT identically — caller decides on fallback (D-52).
    - Every successful call emits an INFO log line `event=llm_provider_call feature=... provider=... source=... success=True latency_ms=...`.
    - Every failed call (any exception) emits an INFO log line with `success=False` BEFORE re-raising.
  </behavior>
  <read_first>
    - backend/app/services/llm_provider.py (Plan 03-04 Task 1 output — the file already has imports + _resolve_provider; APPEND the class)
    - backend/app/services/embedding_service.py (AsyncOpenAI usage analog — kwargs shape, await pattern)
    - backend/app/services/tracing_service.py (@traced decorator usage — bare vs parenthesised forms)
    - .planning/phases/03-entity-resolution-llm-provider-configuration/03-CONTEXT.md D-49, D-50, D-52, D-53, D-54, D-58, D-63
    - .planning/phases/03-entity-resolution-llm-provider-configuration/03-PATTERNS.md §"Lazy module-level singleton pattern" + §"Public client surface"
  </read_first>
  <action>
APPEND (do NOT overwrite — Task 1 wrote the imports + helper) the rest of the module to `backend/app/services/llm_provider.py`. Add the lazy-cached client factory, the LLMProviderClient class, and the per-call helpers.

Append exactly:

```python
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
                    "feature=%s provider=%s source=%s success=False "
                    "latency_ms=%d egress_tripped=True",
                    feature, provider, source, latency_ms,
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
                "feature=%s provider=%s source=%s success=True latency_ms=%d",
                feature, provider, source, latency_ms,
            )
            return parsed
        except _EgressBlocked:
            # Already logged above; re-raise.
            raise
        except Exception as exc:  # SDK error, timeout, network — let caller decide.
            latency_ms = int((time.monotonic() - started) * 1000)
            logger.info(
                "llm_provider_call event=llm_provider_call "
                "feature=%s provider=%s source=%s success=False latency_ms=%d "
                "error_type=%s",
                feature, provider, source, latency_ms, type(exc).__name__,
            )
            raise
```

Hard requirements (verify after writing):
- The class `LLMProviderClient` has exactly one public method `call`.
- `call` is decorated `@traced(name="llm_provider.call")`.
- The cloud path runs `egress_filter` BEFORE `client.chat.completions.create`.
- On `result.tripped` the function raises `_EgressBlocked(result)` BEFORE the SDK call.
- The local path does NOT call `egress_filter`.
- The INFO log line uses `event=llm_provider_call`, `feature=`, `provider=`, `source=`, `success=`, `latency_ms=`.
- The error log line includes `error_type=type(exc).__name__` — a class name, never the exception's `str()` (which could leak request body fragments).
- `_get_client` instantiates `AsyncOpenAI(base_url=..., api_key=..., timeout=...)` — exact kwarg names matching the SDK.
- Module-level `_clients` dict caches instances (D-50).
- The cloud client uses `settings.cloud_llm_api_key or "missing-cloud-key"` — empty key is replaced with a non-empty placeholder so AsyncOpenAI can be instantiated; the actual call will 401, which the caller catches and falls back. (D-58 — empty key is a deployer-misconfig signal; not our crash to own.)

Run the import smoke-test:
```bash
cd backend && source venv/bin/activate && python -c "
from app.services.llm_provider import LLMProviderClient, _get_client, _resolve_provider, _EgressBlocked
client = LLMProviderClient()
assert hasattr(client, 'call')
assert callable(client.call)
# Confirm the lazy cache key shape — calling _get_client twice returns the same instance.
c1 = _get_client('local')
c2 = _get_client('local')
assert c1 is c2, 'lazy cache broken'
print('CLIENT_OK')
"
```
  </action>
  <verify>
    <automated>cd backend && source venv/bin/activate && python -c "
from app.services.llm_provider import LLMProviderClient, _get_client, _EgressBlocked
import inspect
client = LLMProviderClient()
assert hasattr(client, 'call')
assert inspect.iscoroutinefunction(client.call)
c1 = _get_client('local')
c2 = _get_client('local')
assert c1 is c2
src = open('backend/app/services/llm_provider.py').read()
assert 'egress_filter(' in src
assert '_EgressBlocked(result)' in src
assert '@traced(name=\"llm_provider.call\")' in src
assert 'event=llm_provider_call' in src
assert 'response_format={\"type\": \"json_object\"}' in src
print('CLIENT_OK')
" 2>&1 | grep -q "CLIENT_OK"</automated>
  </verify>
  <acceptance_criteria>
    - File `backend/app/services/llm_provider.py` contains `class LLMProviderClient:`.
    - Contains `@traced(name="llm_provider.call")` immediately above `async def call`.
    - The signature is `async def call(self, feature: str, messages: list[dict], registry: "ConversationRegistry | None" = None, provisional_surrogates: dict[str, str] | None = None) -> dict:`.
    - Contains conditional `if provider == "cloud" and registry is not None:` gating the egress filter call.
    - Contains `egress_filter(payload_str, registry, provisional_surrogates)` call inside the cloud branch.
    - Contains `raise _EgressBlocked(result)` after `if result.tripped:`.
    - Contains `_clients: dict[Literal["local", "cloud"], AsyncOpenAI] = {}` module-level cache.
    - Contains `def _get_client(provider: Literal["local", "cloud"]) -> AsyncOpenAI:`.
    - The local client uses `api_key="not-needed"` (D-50 — LM Studio / Ollama).
    - The cloud client uses `settings.cloud_llm_api_key or "missing-cloud-key"`.
    - Both clients pass `timeout=settings.llm_provider_timeout_seconds`.
    - Contains `response_format={"type": "json_object"}` on the chat.completions.create call (CLAUDE.md "Use Pydantic for structured LLM outputs (`json_object` response format)" rule).
    - INFO log line format matches: `event=llm_provider_call feature=%s provider=%s source=%s success=%s latency_ms=%d`.
    - The smoke-test prints `CLIENT_OK`.
  </acceptance_criteria>
  <done>LLMProviderClient class shipped; cloud path runs egress filter before SDK call; local path bypasses; @traced wired; OBS-03 audit log emitted on every call.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| in-process pre-anon → cloud LLM | The client crosses this boundary; egress filter sits at the gate (cloud branch only) |
| env (CLOUD_LLM_API_KEY) → AsyncOpenAI client | Key never round-trips through DB or admin UI (D-58) |
| LangSmith / Langfuse log sink | Every call emits a resolved-provider audit line; trip lines emit hashes only |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-EGR-01 | Information Disclosure | Real PII reaches cloud LLM despite registry coverage | mitigate | Cloud branch ALWAYS calls egress_filter before SDK invocation; on trip raises _EgressBlocked PRE-CALL — the AsyncOpenAI request is never sent. Plan 03-07 D-66 unit-test matrix asserts no real value appears in mock-recorded request after a trip. |
| T-AUTH-01 | Information Disclosure | CLOUD_LLM_API_KEY exfiltration via log line / error reraise | mitigate | D-58 — key never logged; error log uses `error_type=type(exc).__name__` (CLASS name only, not exc.str() which may include request body fragments); empty key replaced with `"missing-cloud-key"` placeholder so SDK init never echoes the value. |
| T-EGR-02 | Information Disclosure | INFO audit log line leaks raw payload | mitigate | Audit log line includes only feature, provider, source, success, latency_ms. NO `messages=` or `payload=` field. Acceptance criterion bans these. |
| T-DOS-01 | Denial of Service | hung cloud LLM call blocks the per-thread asyncio.Lock indefinitely | mitigate | D-50 — `timeout=settings.llm_provider_timeout_seconds` (default 30s) on both AsyncOpenAI clients. SDK raises on timeout; caller's fallback engages. |
| T-FALLBACK-01 | Reliability | Cloud call failure crashes the chat loop | mitigate | D-52 + NFR-3 — exceptions propagate to the caller (Plan 03-05) which catches and falls back to algorithmic clustering. The provider client itself does not catch network/5xx; that's the wrapper's job. |
| T-CONFIG-01 | Tampering | Bad enum from env / DB used as provider | mitigate | `_resolve_provider` skips invalid values at every layer (treats as unset); D-60's API + DB CHECK constraints prevent invalid values from being persisted in the first place. |
</threat_model>

<verification>
After this plan completes:
- `git status` shows `backend/app/services/llm_provider.py` as a new file.
- Backend imports cleanly: `cd backend && source venv/bin/activate && python -c "from app.main import app; print('OK')"` (PostToolUse hook auto-runs).
- Phase 1 + Phase 2 regression: `pytest tests/ -x` returns 39/39 pass (no public-API change yet — Plan 03-05 wires it in).
- `_resolve_provider` smoke-tests pass.
- `LLMProviderClient` import + lazy-cache check pass.
- Plan 03-05 (redaction_service wiring) is unblocked.
</verification>

<success_criteria>
- llm_provider.py exists with single LLMProviderClient class + _resolve_provider helper + lazy AsyncOpenAI client cache.
- D-49: one class for all 5 features (entity_resolution shipped now; 4 forward-compat).
- D-51: 5-step resolution order (feature_env > feature_db > global_env > global_db > default).
- D-50: AsyncOpenAI reused; timeout configurable via env.
- D-53/D-54/D-56: cloud path runs egress_filter pre-call; trip raises _EgressBlocked.
- D-63: every call emits INFO audit log with provider + source + success + latency_ms; no raw values.
- B4 invariant: error log uses error_type (class name) only.
- Phase 1 + Phase 2 tests still pass.
</success_criteria>

<output>
Create `.planning/phases/03-entity-resolution-llm-provider-configuration/03-04-SUMMARY.md` with:
- File path + line count
- Public exports (LLMProviderClient)
- Resolution-order test results (5 paths verified)
- Lazy-cache verification (same instance returned on second call)
- Phase 1+2 regression: 39/39 still pass
- Plan 03-05 is now unblocked.
</output>
