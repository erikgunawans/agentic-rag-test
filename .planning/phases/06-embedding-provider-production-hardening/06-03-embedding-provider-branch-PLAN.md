---
plan_id: "06-03"
title: "Add EMBEDDING_PROVIDER=local|cloud branch to EmbeddingService.embed_text + embed_batch"
phase: "06-embedding-provider-production-hardening"
plan: 3
type: execute
wave: 2
depends_on: ["06-01"]
autonomous: true
files_modified:
  - backend/app/services/embedding_service.py
  - backend/tests/unit/test_embedding_provider_branch.py
requirements: [EMBED-01, EMBED-02]
must_haves:
  truths:
    - "EmbeddingService with `settings.embedding_provider == 'cloud'` constructs `AsyncOpenAI(api_key=settings.openai_api_key)` exactly as before (RAG-02 unchanged — RAG retrieval behavior identical to pre-Phase-6 for cloud-mode deployers)"
    - "EmbeddingService with `settings.embedding_provider == 'local'` constructs `AsyncOpenAI(base_url=settings.local_embedding_base_url, api_key='not-needed')` (D-P6-02)"
    - "Both `embed_text` and `embed_batch` honor the same provider branch — no per-string serial calls in local mode (D-P6-Discretion bullet 3)"
    - "Switching provider does NOT trigger re-embedding (D-P6-04 — no code, just confirm by absence: no migration / no batch-re-embed script in this plan)"
    - "Off-mode invariant: this plan does not touch redaction code (orthogonal to PII redaction)"
  artifacts:
    - path: "backend/app/services/embedding_service.py"
      provides: "Provider-aware AsyncOpenAI client construction inside __init__"
      contains: "embedding_provider"
    - path: "backend/tests/unit/test_embedding_provider_branch.py"
      provides: "Two-case unit test asserting client construction args for cloud vs local"
      contains: "test_embed_local_provider_uses_local_base_url"
  key_links:
    - from: "backend/app/services/embedding_service.py:__init__"
      to: "settings.embedding_provider, settings.local_embedding_base_url, settings.openai_api_key"
      via: "get_settings() lookup at construction"
      pattern: "settings\\.embedding_provider"
threat_model:
  - id: "T-06-03-1"
    description: "Local-embedding endpoint exposes raw text to a deployer-controlled local server (Ollama / LM Studio). By design — this is the EMBED-02 requirement (no third-party egress). However, the egress filter in redaction/egress.py does NOT apply to embedding calls (only LLM-via-LLMProviderClient calls). A deployer who wires `EMBEDDING_PROVIDER=local` MUST own that local endpoint."
    mitigation: "Cloud is default. Local is opt-in via env var (deploy-time decision per D-P6-01). Plan 06-08 documents the trade-off in CLAUDE.md. No further code mitigation — egress filter is intentionally scoped to LLM calls per Phase 3 D-53..D-56."
    severity: "low"
---

<objective>
Implement the `EMBEDDING_PROVIDER` switch inside `EmbeddingService` per D-P6-02. The cloud path is byte-identical to today's behavior (RAG-02 invariant); the local path uses an OpenAI-API-compatible local endpoint via `AsyncOpenAI(base_url=settings.local_embedding_base_url, api_key="not-needed")`.

Purpose: Satisfies REQ EMBED-01 (provider switch) and EMBED-02 (OpenAI-API-compatible local endpoint, no auto-re-embed). Closes the Phase 6 deliverable 1 codepath. Mirrors the Phase 3 `LLMProviderClient` provider branching pattern so deployer experience is consistent.

Output: provider-branched `EmbeddingService.__init__` plus a unit test that asserts client construction arguments under both modes.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/STATE.md
@.planning/phases/06-embedding-provider-production-hardening/06-CONTEXT.md
@.planning/phases/03-entity-resolution-llm-provider-configuration/03-CONTEXT.md
@.planning/phases/06-embedding-provider-production-hardening/06-01-SUMMARY.md
@backend/app/services/embedding_service.py
@backend/app/services/llm_provider.py
@backend/app/config.py
@CLAUDE.md

<interfaces>
<!-- Existing EmbeddingService class — full current contents. -->

```python
# backend/app/services/embedding_service.py (current — 87 lines)
from openai import AsyncOpenAI
from app.services.tracing_service import traced
from app.config import get_settings
from app.database import get_supabase_client

settings = get_settings()


class EmbeddingService:
    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = settings.openai_embedding_model

    @traced
    async def embed_text(self, text: str, model: str | None = None) -> list[float]:
        response = await self.client.embeddings.create(
            model=model or self.model,
            input=text,
        )
        return response.data[0].embedding

    @traced
    async def embed_batch(self, texts: list[str], model: str | None = None) -> list[list[float]]:
        response = await self.client.embeddings.create(
            model=model or self.model,
            input=texts,
        )
        return [item.embedding for item in sorted(response.data, key=lambda x: x.index)]
```

<!-- Phase 3 LLMProviderClient _get_client pattern (the canonical template — D-P6-02 says "exact pattern for local embedding endpoint"). Extracted from llm_provider.py:103-121. -->

```python
def _get_client(provider: Literal["local", "cloud"]) -> AsyncOpenAI:
    settings = get_settings()
    if provider == "local":
        return AsyncOpenAI(
            base_url=settings.local_llm_base_url,
            api_key="not-needed",  # LM Studio / Ollama require no key
            timeout=settings.llm_provider_timeout_seconds,
        )
    else:
        return AsyncOpenAI(
            base_url=settings.cloud_llm_base_url,
            api_key=settings.cloud_llm_api_key or "missing-cloud-key",
            timeout=settings.llm_provider_timeout_seconds,
        )
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Add provider branch in EmbeddingService.__init__</name>
  <read_first>
    - backend/app/services/embedding_service.py (full 87-line file — current cloud-only implementation)
    - backend/app/services/llm_provider.py (lines 100-121 — canonical `_get_client` pattern that Phase 6 mirrors per D-P6-02)
    - backend/app/config.py (lines added by Plan 06-01: `embedding_provider`, `local_embedding_base_url`)
    - .planning/phases/06-embedding-provider-production-hardening/06-CONTEXT.md (D-P6-02 — "no new class, just a branch in the existing service")
  </read_first>
  <files>backend/app/services/embedding_service.py</files>
  <behavior>
    - Test 1: With `settings.embedding_provider = "cloud"` (default), `EmbeddingService().client` is constructed with the existing `AsyncOpenAI(api_key=settings.openai_api_key)` arguments — `base_url` is unset (i.e., the openai SDK default `https://api.openai.com/v1`).
    - Test 2: With `settings.embedding_provider = "local"` and `settings.local_embedding_base_url = "http://localhost:11434/v1"`, `EmbeddingService().client` is constructed with `base_url="http://localhost:11434/v1"` and `api_key="not-needed"` (the literal string per D-P6-02).
    - Test 3: `embed_batch` in local mode must still pass `input=texts` (the full list) to `self.client.embeddings.create` — NO per-string serial calls (D-P6-Discretion bullet 3). Asserted by mocking `self.client.embeddings.create` and checking `await_args.kwargs["input"]` is the original `texts` list.
  </behavior>
  <action>
Replace the existing `EmbeddingService.__init__` body with a provider branch. Specifically, change:

```python
class EmbeddingService:
    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = settings.openai_embedding_model
```

to:

```python
class EmbeddingService:
    def __init__(self):
        # Phase 6 D-P6-02 / EMBED-01 / EMBED-02: provider branch.
        # cloud (default) preserves the existing OpenAI flow exactly (RAG-02 unchanged).
        # local uses an OpenAI-API-compatible endpoint (Ollama bge-m3 / LM Studio) — no third-party egress.
        # Pattern mirrors LLMProviderClient._get_client (Phase 3 D-50): same AsyncOpenAI library,
        # same chat-completions-style API surface, deployer-supplied base_url for local.
        if settings.embedding_provider == "local":
            self.client = AsyncOpenAI(
                base_url=settings.local_embedding_base_url,
                api_key="not-needed",  # Ollama / LM Studio require no key
            )
        else:
            # cloud (default) — RAG-02 preserved byte-identically
            self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = settings.openai_embedding_model
```

Do NOT touch `embed_text` or `embed_batch` method bodies — D-P6-02 says "branch inside `embed_text()` and `embed_batch()`" but the right interpretation (per D-P6-Discretion bullet 3 + the LLMProviderClient pattern) is to branch ONCE at construction and let both methods reuse `self.client`. This is the same pattern Phase 3 used (one client per provider, cached). Per-method branching would either duplicate the client construction or break the `input=texts` batching invariant.

Do NOT change the module-level `settings = get_settings()` assignment at line 6 — the lru_cached settings instance is read at import-time and reused.

Do NOT remove the `model = settings.openai_embedding_model` line — local-mode deployers may set `OPENAI_EMBEDDING_MODEL=bge-m3` (or use `CUSTOM_EMBEDDING_MODEL` per RAG-02) to point at the model their local endpoint serves. The `model` name is server-controlled at the local endpoint; the env var stays the source of truth.
  </action>
  <verify>
    <automated>cd backend &amp;&amp; source venv/bin/activate &amp;&amp; pytest tests/unit/test_embedding_provider_branch.py -v --tb=short</automated>
  </verify>
  <acceptance_criteria>
    - `grep -nE 'if\s+settings\.embedding_provider\s*==\s*"local"' backend/app/services/embedding_service.py` returns exactly 1 match
    - `grep -n '"not-needed"' backend/app/services/embedding_service.py` returns at least 1 match
    - `grep -n 'base_url=settings\.local_embedding_base_url' backend/app/services/embedding_service.py` returns at least 1 match
    - `grep -n 'AsyncOpenAI(api_key=settings\.openai_api_key)' backend/app/services/embedding_service.py` returns at least 1 match (cloud path preserved)
    - `cd backend &amp;&amp; python -c "from app.main import app; print('OK')"` prints `OK`
    - `cd backend &amp;&amp; source venv/bin/activate &amp;&amp; pytest tests/unit/test_embedding_provider_branch.py -v --tb=short` exits 0
  </acceptance_criteria>
  <done>Both branches present in `__init__`; backend imports cleanly; the new unit test passes; pre-existing RAG behavior unchanged in cloud mode.</done>
</task>

<task type="auto">
  <name>Task 2: Write unit test backend/tests/unit/test_embedding_provider_branch.py</name>
  <read_first>
    - backend/tests/unit/test_llm_provider_client.py (read entire file — canonical existing pattern for testing AsyncOpenAI client construction with monkeypatched settings; Phase 3 established this pattern, Plan 06-03 mirrors it for embeddings)
    - backend/tests/conftest.py (existing fixtures; verify whether get_settings is monkeypatched at session level)
    - backend/app/services/embedding_service.py (post-Task-1 file — see the new branch)
    - .planning/phases/06-embedding-provider-production-hardening/06-CONTEXT.md (D-P6-02 specifics: `api_key="not-needed"` literal; D-P6-Discretion bullet 3: batch must NOT serialize)
  </read_first>
  <files>backend/tests/unit/test_embedding_provider_branch.py</files>
  <action>
Create a new test file with three test functions. The file uses pytest + `monkeypatch` to swap `app.config.get_settings` and a `unittest.mock.AsyncMock` to capture `AsyncOpenAI(...)` constructor kwargs. Use this exact structure:

```python
"""Phase 6 Plan 06-03 unit tests — EMBEDDING_PROVIDER branch in EmbeddingService.

D-P6-02 verifies:
  - cloud mode: AsyncOpenAI(api_key=<openai key>) — RAG-02 byte-identical
  - local mode: AsyncOpenAI(base_url=<local url>, api_key="not-needed")
  - embed_batch passes input=texts (no per-string serial calls — D-P6-Discretion bullet 3)
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _fake_settings(provider: str, local_base_url: str = "", openai_api_key: str = "sk-test-cloud", openai_embedding_model: str = "text-embedding-3-small") -> SimpleNamespace:
    return SimpleNamespace(
        embedding_provider=provider,
        local_embedding_base_url=local_base_url,
        openai_api_key=openai_api_key,
        openai_embedding_model=openai_embedding_model,
    )


def test_embed_cloud_provider_uses_openai_key(monkeypatch):
    """D-P6-02 cloud branch: AsyncOpenAI receives only api_key (no base_url)."""
    fake = _fake_settings(provider="cloud", openai_api_key="sk-cloud-XXX")

    captured_kwargs: dict = {}

    class _StubAsyncOpenAI:
        def __init__(self, **kwargs):
            captured_kwargs.update(kwargs)
            self.embeddings = MagicMock()

    # IMPORTANT: patch the symbol where embedding_service.py imports it from.
    monkeypatch.setattr("app.services.embedding_service.AsyncOpenAI", _StubAsyncOpenAI)
    monkeypatch.setattr("app.services.embedding_service.settings", fake)

    # monkeypatch.setattr replaces the module-level symbol in place;
    # subsequent attribute reads (settings.embedding_provider) hit the patched object.
    from app.services.embedding_service import EmbeddingService

    service = EmbeddingService()
    assert service.model == "text-embedding-3-small"
    assert captured_kwargs == {"api_key": "sk-cloud-XXX"}, f"cloud branch should pass only api_key; got {captured_kwargs}"
    assert "base_url" not in captured_kwargs


def test_embed_local_provider_uses_local_base_url(monkeypatch):
    """D-P6-02 local branch: AsyncOpenAI receives base_url + api_key='not-needed'."""
    fake = _fake_settings(provider="local", local_base_url="http://localhost:11434/v1")

    captured_kwargs: dict = {}

    class _StubAsyncOpenAI:
        def __init__(self, **kwargs):
            captured_kwargs.update(kwargs)
            self.embeddings = MagicMock()

    monkeypatch.setattr("app.services.embedding_service.AsyncOpenAI", _StubAsyncOpenAI)
    monkeypatch.setattr("app.services.embedding_service.settings", fake)

    from app.services.embedding_service import EmbeddingService

    service = EmbeddingService()
    assert captured_kwargs.get("base_url") == "http://localhost:11434/v1"
    assert captured_kwargs.get("api_key") == "not-needed"


@pytest.mark.asyncio
async def test_embed_batch_local_passes_full_list_no_serial_calls(monkeypatch):
    """D-P6-Discretion bullet 3: local-mode embed_batch passes input=texts as a single list."""
    fake = _fake_settings(provider="local", local_base_url="http://localhost:11434/v1")

    fake_response = SimpleNamespace(
        data=[
            SimpleNamespace(embedding=[0.1, 0.2], index=0),
            SimpleNamespace(embedding=[0.3, 0.4], index=1),
            SimpleNamespace(embedding=[0.5, 0.6], index=2),
        ]
    )
    create_mock = AsyncMock(return_value=fake_response)

    class _StubAsyncOpenAI:
        def __init__(self, **kwargs):
            self.embeddings = SimpleNamespace(create=create_mock)

    monkeypatch.setattr("app.services.embedding_service.AsyncOpenAI", _StubAsyncOpenAI)
    monkeypatch.setattr("app.services.embedding_service.settings", fake)

    from app.services.embedding_service import EmbeddingService

    service = EmbeddingService()
    texts = ["alpha", "beta", "gamma"]
    result = await service.embed_batch(texts)

    # Single API call, full list — NOT one call per string.
    assert create_mock.await_count == 1, f"embed_batch must NOT serialize per-string; got {create_mock.await_count} calls"
    kwargs = create_mock.await_args.kwargs
    assert kwargs["input"] == texts
    assert result == [[0.1, 0.2], [0.3, 0.4], [0.5, 0.6]]
```

If `pytest-asyncio` is not configured globally, the `@pytest.mark.asyncio` decorator may need `asyncio_mode = "auto"` already set elsewhere. Existing async tests in `tests/unit/test_redact_text_batch.py` use this decorator successfully — confirm the same import-and-go pattern works.
  </action>
  <verify>
    <automated>cd backend &amp;&amp; source venv/bin/activate &amp;&amp; pytest tests/unit/test_embedding_provider_branch.py -v --tb=short</automated>
  </verify>
  <acceptance_criteria>
    - File `backend/tests/unit/test_embedding_provider_branch.py` exists
    - `grep -nE "test_embed_cloud_provider_uses_openai_key|test_embed_local_provider_uses_local_base_url|test_embed_batch_local_passes_full_list_no_serial_calls" backend/tests/unit/test_embedding_provider_branch.py` returns exactly 3 matches
    - `grep -n '"not-needed"' backend/tests/unit/test_embedding_provider_branch.py` returns at least 1 match
    - `grep -n 'await_count == 1' backend/tests/unit/test_embedding_provider_branch.py` returns at least 1 match
    - `cd backend &amp;&amp; source venv/bin/activate &amp;&amp; pytest tests/unit/test_embedding_provider_branch.py -v --tb=short 2>&amp;1 | tail -10 | grep -E "3 passed|passed in"` returns at least 1 match
  </acceptance_criteria>
  <done>Three unit tests pass: cloud mode constructs AsyncOpenAI with only `api_key`; local mode constructs with `base_url` + `api_key="not-needed"`; `embed_batch` in local mode passes `input=texts` in a single call.</done>
</task>

</tasks>

<verification>
1. `cd backend && source venv/bin/activate && pytest tests/unit/test_embedding_provider_branch.py -v --tb=short` — 3/3 new tests pass.
2. `cd backend && source venv/bin/activate && pytest tests/unit -m 'not slow' -v --tb=short -q 2>&1 | tail -5` — 195+ pre-existing unit tests + 3 new = 198+ all passing.
3. `cd backend && python -c "from app.main import app; print('OK')"` — backend imports cleanly.
4. `grep -n "AsyncOpenAI(api_key=settings.openai_api_key)" backend/app/services/embedding_service.py` — confirms cloud branch preserved exactly (RAG-02 invariant).
</verification>

<success_criteria>
- EmbeddingService constructor branches on `settings.embedding_provider`
- Cloud-mode args byte-identical to pre-Phase-6 (RAG-02 unchanged)
- Local-mode uses `base_url=settings.local_embedding_base_url, api_key="not-needed"` (D-P6-02 verbatim)
- `embed_batch` does not serialize per-string in local mode (D-P6-Discretion bullet 3)
- 3 new unit tests pass
- All pre-existing unit tests still pass
- Backend imports cleanly
- No re-embedding script / no migration introduced (D-P6-04 — confirm by absence)
</success_criteria>

<output>
After completion, create `.planning/phases/06-embedding-provider-production-hardening/06-03-SUMMARY.md` documenting:
- Diff of `embedding_service.py:__init__` (cloud branch unchanged + new local branch)
- Output of `pytest tests/unit/test_embedding_provider_branch.py -v` (3 tests passed)
- Confirmation that `find backend -name '*.sql' -newer .planning/phases/06-embedding-provider-production-hardening/06-CONTEXT.md` returns no new migrations
- A 1-paragraph note for the future deploy doc describing how to switch to local: set `EMBEDDING_PROVIDER=local` and `LOCAL_EMBEDDING_BASE_URL=http://localhost:11434/v1` in Railway env vars; existing documents stay on the cloud-embedded vectors until manually re-ingested (EMBED-02 / D-P6-04)
</output>
