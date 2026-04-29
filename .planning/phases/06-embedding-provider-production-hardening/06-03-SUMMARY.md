---
phase: "06-embedding-provider-production-hardening"
plan: 3
subsystem: "embedding"
tags: [embedding, provider-switch, local, cloud, tdd, phase6]
dependency_graph:
  requires:
    - "06-01 (settings.embedding_provider + settings.local_embedding_base_url)"
  provides:
    - "EmbeddingService.__init__ provider branch (EMBED-01, EMBED-02)"
    - "Unit tests asserting cloud/local AsyncOpenAI construction args"
  affects:
    - "backend/app/services/embedding_service.py (all RAG pipeline consumers)"
tech_stack:
  added: []
  patterns:
    - "AsyncOpenAI provider branch in __init__ (mirrors Phase 3 LLMProviderClient._get_client)"
    - "TDD RED/GREEN: failing test commit before implementation commit"
key_files:
  created:
    - "backend/tests/unit/test_embedding_provider_branch.py"
  modified:
    - "backend/app/services/embedding_service.py"
decisions:
  - "D-P6-02: Branch in __init__ (not per-method) so both embed_text and embed_batch reuse self.client — mirrors LLMProviderClient pattern, avoids serialization risk"
  - "D-P6-04-confirmed: No migration, no re-embedding script introduced — confirmed by absence of new .sql files"
metrics:
  duration: "~8 minutes"
  completed: "2026-04-29T07:30:00Z"
  tasks_completed: 2
  tasks_total: 2
  files_modified: 2
---

# Phase 6 Plan 3: EmbeddingService Provider Branch Summary

**One-liner:** Added `EMBEDDING_PROVIDER=local|cloud` branch in `EmbeddingService.__init__` using AsyncOpenAI client construction mirroring the Phase 3 LLMProviderClient pattern; cloud path byte-identical to pre-Phase-6 (RAG-02), local path uses `base_url + api_key="not-needed"` for Ollama/LM Studio (EMBED-01, EMBED-02).

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| RED (TDD) | Write failing unit tests for provider branch | 66d3f7d | backend/tests/unit/test_embedding_provider_branch.py |
| GREEN (TDD) | Implement provider branch in EmbeddingService.__init__ | 573c47c | backend/app/services/embedding_service.py |

## Changes Made

### `backend/app/services/embedding_service.py` — `__init__` diff

Before (cloud-only, 2 lines):
```python
def __init__(self):
    self.client = AsyncOpenAI(api_key=settings.openai_api_key)
    self.model = settings.openai_embedding_model
```

After (provider-branched, 14 lines):
```python
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

`embed_text` and `embed_batch` method bodies are unchanged — both automatically use the branch-selected `self.client`.

### `backend/tests/unit/test_embedding_provider_branch.py` — 3 new tests

```
tests/unit/test_embedding_provider_branch.py::test_embed_cloud_provider_uses_openai_key PASSED
tests/unit/test_embedding_provider_branch.py::test_embed_local_provider_uses_local_base_url PASSED
tests/unit/test_embedding_provider_branch.py::test_embed_batch_local_passes_full_list_no_serial_calls PASSED
========================= 3 passed, 1 warning in 0.55s =========================
```

## Verification Output

### New tests (3/3 pass)
```
========================= 3 passed, 1 warning in 0.55s =========================
```

### Full unit suite (no regressions)
```
====================== 265 passed, 557 warnings in 2.39s =======================
```
(256 pre-existing + 3 new = 259 minimum; 265 confirms all pre-existing tests still pass)

### Backend import check
```
$ python -c "from app.main import app; print('OK')"
OK
```

### Cloud branch preserved (RAG-02 invariant)
```
$ grep -n 'AsyncOpenAI(api_key=settings.openai_api_key)' backend/app/services/embedding_service.py
23:            self.client = AsyncOpenAI(api_key=settings.openai_api_key)
```

## No Migration Introduced

```
$ find backend -name '*.sql' -newer .planning/phases/06-embedding-provider-production-hardening/06-01-SUMMARY.md
(empty)
```

Confirmed: zero new migration files. D-P6-04 invariant satisfied.

## Deploy Note: Switching to Local Embedding Provider

To switch an existing LexCore deployment to a local embedding endpoint:

1. Set environment variables in Railway:
   - `EMBEDDING_PROVIDER=local`
   - `LOCAL_EMBEDDING_BASE_URL=http://localhost:11434/v1` (or your Ollama/LM Studio URL)
   - `OPENAI_EMBEDDING_MODEL=bge-m3` (or `nomic-embed-text`, matching your local model)

2. Restart the backend service.

3. **Important:** Existing documents in the database remain on their original cloud-generated embeddings (OpenAI `text-embedding-3-small` or whichever model was used at ingestion time). Switching `EMBEDDING_PROVIDER` does NOT automatically re-embed existing documents (EMBED-02 / D-P6-04 — deployer-managed migration). New uploads after the switch will be embedded by the local endpoint. Hybrid search will work correctly; however, similarity scores between old cloud-embedded chunks and new locally-embedded query vectors may be inconsistent until existing documents are re-ingested. Re-ingestion is performed by deleting and re-uploading documents through the UI.

## TDD Gate Compliance

- [x] RED gate: `test(06-03): add failing tests for EMBEDDING_PROVIDER branch in EmbeddingService` (commit 66d3f7d) — test_embed_local_provider_uses_local_base_url failed as expected
- [x] GREEN gate: `feat(06-03): add EMBEDDING_PROVIDER branch in EmbeddingService.__init__` (commit 573c47c) — all 3 tests pass

## Deviations from Plan

None — plan executed exactly as written.

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns, or schema changes introduced. The local embedding path bypasses cloud egress by design (T-06-03-1 noted in plan threat model, severity low, opt-in via env var). The egress filter in `redaction/egress.py` is intentionally scoped to LLM calls only — embedding calls are not subject to it per Phase 3 D-53..D-56 scope decision.

## Known Stubs

None.

## Self-Check: PASSED

- [x] `backend/app/services/embedding_service.py` contains `if settings.embedding_provider == "local"` (line 16)
- [x] `backend/app/services/embedding_service.py` contains `api_key="not-needed"` (line 19)
- [x] `backend/app/services/embedding_service.py` contains `base_url=settings.local_embedding_base_url` (line 18)
- [x] `backend/app/services/embedding_service.py` contains `AsyncOpenAI(api_key=settings.openai_api_key)` (line 23, cloud branch preserved)
- [x] `backend/tests/unit/test_embedding_provider_branch.py` exists with 3 test functions
- [x] RED commit `66d3f7d` verified in git log
- [x] GREEN commit `573c47c` verified in git log
- [x] 265/265 unit tests pass
- [x] No migration files added
- [x] Backend imports cleanly
