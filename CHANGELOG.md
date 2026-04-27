# Changelog

All notable changes to this project will be documented in this file.

## [0.3.0.0] - 2026-04-28

### Added
- **PII Redaction System v1.0** — full conversation-scoped PII detection, anonymization, persistence, and de-anonymization across the chat loop. Indonesian-aware (PERSON/EMAIL/PHONE/LOCATION/DATE/URL/IP), with cloud-egress filtering as the privacy security primitive.
- **Phase 1 — Detection + anonymization**: Presidio + spaCy + Faker pipeline with UUID pre-mask, Indonesian honorifics (Pak/Bu/Bpk/Ibu/Sdr/Sdri), gender-aware surrogate generation, hard-redact bucket for sensitive types, per-call forbidden-token guard.
- **Phase 2 — Conversation-scoped registry**: per-thread `entity_registry` table (migration 029) so the same real value always maps to the same surrogate within a thread (REG-04). `ConversationRegistry` in-memory wrapper with cross-process safety via composite UNIQUE constraint.
- **Phase 3 — Entity resolution + LLM provider**: Union-Find PERSON clustering with Indonesian nicknames (D-46), per-feature LLM provider selection (local vs cloud) via `LLMProviderClient`, pre-flight egress filter blocking cloud calls when registry-known PII appears in the payload.
- **Phase 4 — Fuzzy de-anonymization + missed-PII scan**: 3-phase de-anonymization pipeline with Jaro-Winkler fuzzy matching for slightly-mangled surrogate forms ("M. Smyth" → "Marcus Smith"), missed-PII scan with auto-chain re-redaction.
- **Phase 5 — Chat-loop integration**: full PII privacy invariant wired end-to-end into `chat.py` event_generator. Per-turn registry lifecycle, batched history anonymization, tool I/O symmetry walkers (deanonymize → execute → anonymize), buffered stream_response with single de-anon emit, SSE redaction status events, EgressBlockedAbort handler with skeleton tool events, title-gen migration to LLMProviderClient.
- **Admin settings UI**: 14 new settings exposed at `/admin/settings` covering PII enable/disable, entity resolution mode (algorithmic/llm/none), per-feature LLM provider overrides, fuzzy de-anon mode + threshold, missed-scan toggle, and live LLM provider status probe.
- **Migrations**: 029 `entity_registry` table, 030 9 PII provider columns on `system_settings`, 031 fuzzy de-anon columns. All RLS service-role-only per D-25.
- **Test suite**: 256 backend tests (188 unit + 68 integration) covering all Phase 1–5 success criteria, B4 privacy invariant logging, and end-to-end SC#1–SC#5 invariants.

### Changed
- `chat.py` event_generator: 291 → 517 LOC with Phase 5 PII wiring. Off-mode (`pii_redaction_enabled=false`) is byte-identical to pre-Phase-5 behavior (SC#5 invariant).
- Tool execution loop: walker-wrapped when redaction is on (deanonymize args → execute → anonymize output) so tool I/O never leaks real PII to the LLM.
- Stream response: buffered when redaction is on; progressive deltas only in off-mode. Single de-anon delta emitted at end of turn.

### Fixed
- `forbidden_tokens()` recomputed per call inside the redaction lock; now cached and invalidated only on PERSON upserts.
- `best_match` fuzzy_score called twice on the winner; now scores once per variant.
- `_thread_locks` unbounded dict (memory leak under long-running processes); now `WeakValueDictionary` so locks GC when no coroutine holds them.
- `entity_resolution_mode` else-fallthrough silently routed unknown Literal values to the LLM path; now explicit `elif/else: raise ValueError`.
- SSE tool-loop events leaked client-side before later EgressBlockedAbort raised; now buffered and flushed only on successful loop completion.

## [0.2.0.0] - 2026-04-20

### Added
- **RAG pipeline complete (8/8 hooks)**: metadata pre-filtering (tags, folder, date range), weighted RRF fusion, Cohere Rerank v2, OCR metadata tracking, graph re-indexing endpoint, RAG evaluation golden set, bilingual query expansion, structure-aware chunking
- **Metadata pre-filtering**: LLM can now filter document search by tags, folder, and date range directly from chat
- **Weighted fusion**: admin-configurable vector vs fulltext search weights via system settings
- **Cohere Rerank**: fast cross-encoder reranking as alternative to LLM reranking (~200ms vs 2-5s)
- **OCR tracking**: scanned PDF documents now record `ocr_used`, `ocr_pages_processed`, and `ocr_pages_failed` in metadata
- **Graph re-indexing**: `POST /documents/{id}/reindex-graph` backfills graph entities for existing documents
- **RAG evaluation**: 20-query Indonesian legal golden set with keyword hit rate and MRR metrics (`python -m scripts.eval_rag`)
- **Claude Code automations**: context7 + Playwright MCP servers, enhanced PostToolUse (full import check), PreToolUse blocks applied migrations, `/create-migration` skill, `rag-quality-reviewer` agent
- **Vision OCR**: scanned PDFs auto-detected and processed via GPT-4o vision

### Changed
- RRF fusion weights now read from `system_settings` (admin-configurable) instead of hardcoded 1:1
- Rerank dispatch uses tri-state `rag_rerank_mode` (none/llm/cohere) instead of boolean `rag_rerank_enabled`
- `_llm_rerank` sort uses `enumerate()` instead of `list.index()` (O(n log n) vs O(n²))
- httpx client reused across Cohere rerank calls instead of creating per-call
- CLAUDE.md quality improved from 82 to 100/100, condensed from 186 to 167 lines

### Fixed
- Cache key now includes filter params to prevent cross-query collisions
- Cohere client initialized in `__init__` to avoid race condition on concurrent first requests
- `rag_rerank_mode` validated with `Literal["none", "llm", "cohere"]` to prevent silent misconfiguration
- Pre-existing bug: `user_settings` → `sys_settings` in `/documents/search` vector mode (line 244)

## [0.1.1.0] - 2026-04-04

### Added
- Deploy backend to Railway with Dockerized FastAPI container (non-root user, exec-form CMD)
- Deploy frontend to Vercel with auto-detected Vite build
- Configurable CORS origins via `FRONTEND_URL` environment variable (comma-separated, empty-string safe)
- Production Dockerfile for backend (python:3.12-slim, uvicorn)
- `.dockerignore` to exclude dev artifacts, tests, plan files, and git history from container builds

### Fixed
- TypeScript build error in ToolCallCard where `unknown` type wasn't assignable to `ReactNode`
- Unused React import warning in scroll-area component
- CORS empty-string vulnerability when `FRONTEND_URL` has trailing comma
