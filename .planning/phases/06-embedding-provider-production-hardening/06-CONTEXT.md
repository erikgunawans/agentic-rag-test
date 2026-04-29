# Phase 6: Embedding Provider & Production Hardening - Context

**Gathered:** 2026-04-29
**Status:** Ready for planning

<domain>
## Phase Boundary

Close out the v1.0 PII Redaction milestone with four production-hardening deliverables:
1. `EMBEDDING_PROVIDER=local|cloud` switch in `EmbeddingService` (env-var only, no admin UI)
2. `<500ms` anonymization latency regression test (real Presidio, `@pytest.mark.slow`)
3. Full PERF-04 graceful-degradation wiring (fallback enabled by default, title template fallback)
4. `thread_id` correlation key added to all per-operation debug log lines (OBS-02)

**Out of scope (explicitly deferred):**
- Cloud→local cross-provider crossover (remains plumbed-but-disabled per Phase 3 D-52)
- Re-embedding existing documents when EMBEDDING_PROVIDER switches (deployer-managed migration per EMBED-02)
- Admin UI toggle for EMBEDDING_PROVIDER (env-var only)
- Postgres advisory lock upgrade (D-31 FUTURE-WORK, not a Phase 6 requirement)

</domain>

<decisions>
## Implementation Decisions

### Embedding Provider Switch (EMBED-01/02)

- **D-P6-01:** `EMBEDDING_PROVIDER=local|cloud` — env-var only. No new `system_settings` column, no migration, no admin UI field. Consistent with how `CUSTOM_EMBEDDING_MODEL` already works. Switching providers is a deploy-time decision, not a runtime admin action.
- **D-P6-02:** Implementation lives in the existing `backend/app/services/embedding_service.py` (87 lines). Add a provider branch inside `embed_text()` and `embed_batch()`: `cloud` path = existing `AsyncOpenAI(api_key=settings.openai_api_key)` flow (RAG-02 unchanged); `local` path = `AsyncOpenAI(base_url=settings.local_embedding_base_url, api_key="not-needed")` pointing at an OpenAI-API-compatible local endpoint (Ollama bge-m3, nomic-embed-text, etc.). No new class — just a branch in the existing service.
- **D-P6-03:** New env var: `LOCAL_EMBEDDING_BASE_URL` (mirrors `LOCAL_LLM_BASE_URL` from Phase 3). New env var: `EMBEDDING_PROVIDER` (default `"cloud"`). Both added to `backend/app/config.py` Settings class.
- **D-P6-04:** Switching providers does NOT trigger re-embedding of existing documents. Existing vectors stay on the old provider's space — retrieval quality may degrade for new docs until a deployer-managed re-ingest. This is EMBED-02's documented behavior; no code needed to enforce it (just documentation).

### Latency Budget Test (PERF-02)

- **D-P6-05:** Test target: `redact_text_batch(texts=[realistic_2000_token_message], registry=fresh_registry)` — tests the redaction service layer, not the full chat API. Wall-clock measured with `time.perf_counter()`.
- **D-P6-06:** Test uses the real Presidio NER engine (`get_analyzer()` pre-warmed in a session-scoped fixture before the timed call). Mocked NER would pass 500ms even if real performance degrades — unacceptable for a regression gate.
- **D-P6-07:** Test file marked `@pytest.mark.slow`. Default CI run uses `pytest -m 'not slow'` to skip. The slow suite is run explicitly as a performance gate (pre-ship or dedicated perf step). Budget assertion: `elapsed_ms < 500` on dev hardware; a generous `elapsed_ms < 2000` secondary assertion for CI correctness (ensures the test at least runs on slow CI without hard-failing on timing).
- **D-P6-08:** The 2000-token realistic message should contain a mix of Indonesian and English text with names, phone numbers, emails — representative of actual LexCore usage. Hardcoded fixture string (not generated at runtime to ensure reproducibility).

### Fallback Scope (PERF-04)

- **D-P6-09:** `llm_provider_fallback_enabled` default changes from `false` (Phase 3 D-52) to `true`. Phase 6 fully ships PERF-04, so the fallback must be on by default. Admin can still disable via the existing `system_settings.llm_provider_fallback_enabled` toggle.
- **D-P6-10:** Entity-resolution fallback → algorithmic clustering (already wired in Phase 3 D-52; verify it covers the `fallback_enabled=true` path correctly).
- **D-P6-11:** Missed-PII scan fallback → skip (Phase 4 D-78 already soft-fails missed-scan on provider error; verify the skip path logs correctly with the new `thread_id` correlation key).
- **D-P6-12:** Title/metadata fallback → **first 6 words of the anonymized message**, truncated and de-anonymized before persistence + `thread_title` SSE emit. Logic: `" ".join(anonymized_message.split()[:6])` + de-anonymize via Pass-1 registry lookup (mode="none"). If the anonymized message is empty, fall back to `"New Thread"`. This replaces the existing catch-all `pass` in the title-gen exception handler.
- **D-P6-13:** Cross-provider crossover (cloud→local) remains OUT OF SCOPE. Phase 3 D-52's "plumbed-but-disabled" state is preserved. No new code needed here.

### Observability (OBS-02/03)

- **D-P6-14:** Add `thread_id` correlation to all per-operation debug log lines in the redaction pipeline. Source: `registry.thread_id` (already available on every `ConversationRegistry` instance). No new function signature changes at call sites — pass `thread_id=registry.thread_id` into `detect_entities()` and use it inside the existing `logger.debug(...)` calls. Operator can then `grep 'thread_id=<id>'` to extract the full log block for one chat turn.
- **D-P6-15:** `detect_entities()` in `detection.py` gains an optional `thread_id: str | None = None` parameter. When provided, the existing debug log line adds `thread_id=<id>` as a field. Backward-compatible (callers that don't pass it emit logs without the field — existing behavior preserved).
- **D-P6-16:** Same `thread_id` field added to the `logger.debug` calls in `redaction_service.py` (`redact_text`, `redact_text_batch`, `de_anonymize_text`), `egress.py` (egress-filter trip log), and `llm_provider.py` (per-call provider log). In `redaction_service.py`, `thread_id` is read from `registry.thread_id` inside the method body — no new param needed since `registry` is already a param.
- **D-P6-17:** OBS-03 (resolved provider logged per call) — Phase 3 D-51 already implemented this in `llm_provider.py`. Phase 6 adds the `thread_id` field to those log lines and verifies coverage in a unit test (assert the resolved provider appears in the log output for each feature).

### Claude's Discretion

- Log field format: use `thread_id=<value>` (space-separated key=value) consistent with the existing `redaction.detect` log line format in `detection.py`.
- Test fixture for the 2000-token realistic message: hardcode a representative Indonesian-language legal text (contract clause excerpt mentioning a party name, email, phone number, and date).
- `embed_batch()` local path: call the local endpoint with the same `AsyncOpenAI` client batching approach — no per-string serial calls.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements
- `.planning/REQUIREMENTS.md` §EMBED-01, EMBED-02 — Embedding provider switch requirements
- `.planning/REQUIREMENTS.md` §OBS-02, OBS-03 — Observability requirements
- `.planning/REQUIREMENTS.md` §PERF-02, PERF-04 — Performance and resilience requirements

### Prior Phase Decisions (binding)
- `.planning/phases/03-entity-resolution-llm-provider-configuration/03-CONTEXT.md` — D-49 (LLMProviderClient), D-50 (AsyncOpenAI reuse), D-51 (provider resolution order + per-call logging), D-52 (fallback knob, cross-provider crossover deferred)
- `.planning/phases/05-chat-loop-integration-buffering-sse-status-tool-sub-agent-co/05-CONTEXT.md` — D-90 (graceful degrade pattern), D-92 (redact_text_batch primitive), D-96 (title-gen wiring in chat.py)

### Architecture
- `docs/PRD-PII-Redaction-System-v1.1.md` — Phase 6 success criteria in §SC#6 (PERF-02, PERF-04, OBS-02); NFR-1 (latency), NFR-3 (resilience), NFR-4 (observability)

### Existing Code (read before modifying)
- `backend/app/services/embedding_service.py` — 87-line file; cloud-only today; Phase 6 adds local branch
- `backend/app/services/llm_provider.py` — LLMProviderClient with `_resolve_provider()`, egress filter, `_EgressBlocked`; Phase 6 updates fallback default
- `backend/app/services/redaction/detection.py` — `detect_entities()` receives `thread_id` param in Phase 6
- `backend/app/services/redaction_service.py` — `redact_text_batch`, `de_anonymize_text`; Phase 6 adds `thread_id` to debug logs
- `backend/app/config.py` — receives `EMBEDDING_PROVIDER` and `LOCAL_EMBEDDING_BASE_URL` env vars

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `AsyncOpenAI` with configurable `base_url` (Phase 3): exact pattern for local embedding endpoint — `AsyncOpenAI(base_url=settings.local_embedding_base_url, api_key="not-needed")`
- `registry.thread_id` (ConversationRegistry): already available at every call site that receives a registry; zero-cost correlation key
- `@pytest.mark.slow` pattern: establish in `pytest.ini` or `pyproject.toml`; existing test suite uses `pytest -v` without markers; Phase 6 introduces the slow marker

### Established Patterns
- `logger.debug("key event=value field=value ...")` space-separated key=value format — used throughout `detection.py`, `redaction_service.py`. Phase 6 adds `thread_id=<value>` to each.
- `time.perf_counter()` + elapsed_ms — established in `detection.py` and `redaction_service.py`; use same pattern in the latency test
- `@lru_cache` singleton pattern — `get_analyzer()` already does this; warm-up in test fixture via `get_analyzer()` call before measuring

### Integration Points
- `backend/app/routers/chat.py` — title fallback template in the `except Exception: pass` block around `_llm_provider_client.call(feature='title_gen', ...)` (line ~600+); Phase 6 replaces `pass` with the 6-word template fallback
- `backend/app/routers/documents.py` — calls `EmbeddingService.embed_text/embed_batch`; Phase 6 changes are transparent (provider branch inside the service)
- `backend/app/config.py` — add `EMBEDDING_PROVIDER: str = "cloud"` and `LOCAL_EMBEDDING_BASE_URL: str = ""` to `Settings` class

</code_context>

<specifics>
## Specific Ideas

- Title fallback formula: `" ".join(anonymized_message.split()[:6])` — simple, deterministic, produces a meaningful title stub without LLM involvement.
- `LOCAL_EMBEDDING_BASE_URL` env var name chosen to mirror `LOCAL_LLM_BASE_URL` (Phase 3); makes Railway config predictable.
- The `@pytest.mark.slow` test should use a real Indonesian-language legal text with at least one PERSON entity (name with honorific), one EMAIL_ADDRESS, and one PHONE_NUMBER — exercises the full surrogate-bucket path, not just passthrough.

</specifics>

<deferred>
## Deferred Ideas

- **Cloud→local crossover (PERF-04 extension)** — Phase 3 D-52 left this plumbed-but-disabled. Enabling it would require cross-anonymizing the payload before retry and verifying egress on the local path. Keep disabled; revisit in a future hardening sprint if needed.
- **Postgres advisory lock (D-31)** — `pg_advisory_xact_lock(hashtext(thread_id))` to replace asyncio.Lock for multi-process safety. Out of scope for Phase 6 per REQUIREMENTS.md; listed as FUTURE-WORK.
- **`messages.anonymized_content` sibling-column cache** — Phase 5 CONTEXT.md flagged this for Phase 6 PERF-02 if profiling shows history-anonymization dominates per-turn latency. If the latency test reveals this bottleneck, consider in a post-v1.0 sprint.
- **Fake-stream chunked delivery of buffered de-anon output** — Phase 5 CONTEXT.md deferred this; still deferred.

</deferred>

---

*Phase: 6-Embedding Provider & Production Hardening*
*Context gathered: 2026-04-29*
