---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: planning
last_updated: "2026-04-27T09:30:56.956Z"
last_activity: 2026-04-27
progress:
  total_phases: 6
  completed_phases: 4
  total_plans: 27
  completed_plans: 27
  percent: 100
---

# State: LexCore

## Project Reference

See: `.planning/PROJECT.md` (updated 2026-04-25)

**Core value:** Indonesian legal teams can manage the full contract lifecycle with confidence that AI outputs are accurate, citable, and traceable.
**Current focus:** Phase 5 — Chat-Loop Integration (Buffering, SSE Status, Tool/Sub-Agent Coverage)

## Current Position

Phase: 04 — COMPLETE ✅ (Fuzzy De-anonymization, Missed-PII Scan & Prompt Guidance)
Verification: passed (5/5 SCs, 9/9 REQ-IDs, 16/16 decisions D-67..D-82)

- **Next phase:** 5 — Chat-Loop Integration (Buffering, SSE Status, Tool/Sub-Agent Coverage)
- **Status:** Context gathered — Ready to plan (Phase 5)
- **Last activity:** 2026-04-27

## Accumulated Context

- Codebase map at `.planning/codebase/` (refreshed 2026-04-25, commit `f1a8c62`)
- 38 validated requirements baselined in `REQUIREMENTS.md` (commit `f36b9da`)
- 54 v1.0 requirements added to `REQUIREMENTS.md` (commit `aa1ad88`); milestone v1.0 PII Redaction System started commit `1fd9e49`
- v1.0 roadmap (this update): 6 phases derived from 54 REQ-IDs — see `ROADMAP.md` "Active Phases"
  - Phase 1: Detection & Anonymization Foundation (13 REQ-IDs)
  - Phase 2: Conversation-Scoped Registry & Round-Trip (8 REQ-IDs)
  - Phase 3: Entity Resolution & LLM Provider Configuration (11 REQ-IDs)
  - Phase 4: Fuzzy De-anonymization, Missed-PII Scan & Prompt Guidance (9 REQ-IDs)
  - Phase 5: Chat-Loop Integration (Buffering, SSE Status, Tool/Sub-Agent Coverage) (7 REQ-IDs)
  - Phase 6: Embedding Provider & Production Hardening (6 REQ-IDs)
- Knowledge graph at `graphify-out/` (1,211 nodes, 192 communities; god-nodes: `HybridRetrievalService`, `ToolService`)
- Workflow config: `granularity=standard`, `parallel=true`, `model_profile=balanced`, `research=skip`, `plan_check=on`, `verifier=on`
- Active deployments: Frontend on Vercel (`main` branch), Backend on Railway, Supabase project `qedhulpfezucnfadlfiz`

## Pending Items

- **CRITICAL: Disk full on `/`** — `/private/tmp/claude-501/` write fails; Bash dead. Resume by `rm -rf /private/tmp/claude-501/` + audit caches + `df -h /`.
- **Phase 1 plan revision** — checker round 1 found 5 blockers + 7 warnings + 3 info (durable in conversation). Resume via `/gsd-plan-phase 1` "Replan from scratch" OR direct gsd-planner revision call.
- **Tracing migration scope** — Phase 1 D-16/D-17 renames `langsmith_service.py` → `tracing_service.py` and migrates all `@traceable` call sites in the same commit; planner needs to enumerate them (currently in `chat.py`, `document_tool_service.py`, possibly others)
- **Uncommitted local files** — multiple untracked working-tree files (PRD docs, SVG assets, `graphify-out/` snapshots, `AGENTS.md`); not blocking the milestone but warrants triage before phase 1 execution
- **Pre-existing lint** — 6 ESLint errors in `frontend/src/pages/DocumentsPage.tsx` (`react-hooks/set-state-in-effect`); pre-existing, not introduced by recent work
- **Embedding-provider deviation from PRD §3.2** — `EMBEDDING_PROVIDER=local|cloud` decision logged in PROJECT.md "Key Decisions"; Phase 6 must respect this and document the tradeoff
- **Async-lock cross-process upgrade (Phase 2 D-31, FUTURE-WORK for Phase 6)** — Phase 2 ships per-process `asyncio.Lock` keyed by `thread_id` for PERF-03; correct on Railway today (single Uvicorn worker) but BREAKS under multi-worker / horizontally scaled instances. Replace with `pg_advisory_xact_lock(hashtext(thread_id))` when scale-out happens.

## Blockers

()

---
*Initialized: 2026-04-25 after `/gsd-new-project` brownfield bootstrap*
*Updated: 2026-04-25 — Phase 1 context gathered: 4 gray areas resolved, 20 implementation decisions in `01-CONTEXT.md`*
*Updated: 2026-04-26 — Phase 1 plans drafted (7 plans / 4 waves); plan-checker round 1 complete (5 blockers, 7 warnings, 3 info); revision blocked on disk-full*
*Updated: 2026-04-26 — Phase 1 planning COMPLETE: 4 checker rounds, trajectory 15 → 4 → 1 → 0; ready for /gsd-execute-phase 1*
*Updated: 2026-04-26 — Phase 1 EXECUTION COMPLETE ✅: 21 commits, 20/20 tests passing, all 5 ROADMAP SCs verified. Next: Phase 2 (REG-01..05, DEANON-01..02, PERF-03)*
*Updated: 2026-04-26 — Phase 2 context gathered: 4 gray areas resolved, 24 decisions (D-21..D-44) in `02-CONTEXT.md`. Ready for /gsd-plan-phase 2.*
*Updated: 2026-04-26 — Phase 2 PLANNING COMPLETE ✓: 6 plans / 5 waves; plan-checker trajectory 7 → 0 across 2 iterations. All 8 REQ-IDs covered. Ready for /gsd-execute-phase 2.*
*Updated: 2026-04-26 — Phase 2 EXECUTION underway: plan 02-01 SHIPPED (commit `f7a3ff5`). Migration 029 `entity_registry` written to disk; not yet pushed. Wave 1 sibling 02-02 (ConversationRegistry skeleton) unblocked. REG-01..05 satisfied at schema layer.*
*Updated: 2026-04-26 — Phase 2 Wave 1 COMPLETE: plan 02-02 SHIPPED (commit `26cf393`). `backend/app/services/redaction/registry.py` (127 lines) delivers EntityMapping frozen model + ConversationRegistry data-structure skeleton (lookup/entries/forbidden_tokens/thread_id) — DB methods (load/upsert_delta) deliberately deferred to Plan 02-04. D-31 advisory-lock FUTURE-WORK note captured in module docstring. Phase 1 regression: 20/20 tests still pass. Wave 2 (plan 02-03 `supabase db push`) is now the next gate.*
*Updated: 2026-04-26 — Phase 2 Wave 3 COMPLETE: plan 02-04 SHIPPED (commits `abe7c55` + `865cec2`). `ConversationRegistry.load(thread_id)` (one SELECT) + `async upsert_delta(deltas)` (INSERT…ON CONFLICT DO NOTHING; empty list = zero DB hops; raises on DB error per REG-04) added to `backend/app/services/redaction/registry.py` (final 241 lines). Both methods wrap the sync supabase-py call in `asyncio.to_thread(_closure)` because Plan 05's `redact_text` will hold an asyncio.Lock across the upsert. Service-role client only (D-25). `redaction/__init__.py` re-exports `ConversationRegistry` + `EntityMapping`; `de_anonymize_text` deliberately NOT re-exported per D-39 option b + Phase 1 B2-option-B circular-import posture (verbatim docstring preserved). Phase 1 regression: 20/20 still pass; backend imports cleanly; live load() smoke against real Supabase project `qedhulpfezucnfadlfiz` succeeded. Wave 4 (Plan 02-05 redaction_service wiring) is now unblocked.*
*Updated: 2026-04-26 — Phase 2 Wave 5 COMPLETE → Phase 2 EXECUTION COMPLETE ✅: plan 02-06 SHIPPED (commits `b2d690e` + `d9639d1` + `11412fe`). 19 new tests added (15 integration + 4 unit); combined regression `pytest tests/` → 39/39 pass in ~15s (20 Phase 1 + 15 Phase 2 integration + 4 Phase 2 unit). All 5 Phase 2 ROADMAP SCs covered against live Supabase DB; SC#5 (asyncio.gather race) verified via `len(rows) == 1` assertion against entity_registry table. Cross-turn surname collision (D-37 / PRD §7.5) verified. Hard-redact survival (D-35) verified against both real CardRecognizer and synthetic placeholders. B4 / D-18 / D-41 caplog log-privacy invariant enforced for new methods. W-3 (defensive try/except for stale-schema column additions), W-4 (`_thread_locks_master` rebind to current event loop), B-4 (canonical `client.auth.admin.list_users()` pattern) all in place in conftest.py fixtures. Three Rule-1 deviations during Task 2 (calibration to live xx-multilingual Presidio model behaviour). SUMMARY at `02-06-pytest-coverage-SUMMARY.md`. Phase 2 verification is the orchestrator's next step.*

**Planned Phase:** 04 (Fuzzy De-anonymization, Missed-PII Scan & Prompt Guidance) — 7 plans — 2026-04-27T04:33:40.392Z

*Updated: 2026-04-26 — Phase 3 EXECUTION COMPLETE ✅: 7 plans across 6 waves; all 11 REQ-IDs (RESOLVE-01..04, PROVIDER-01..07) SATISFIED; 5/5 ROADMAP SCs verified. 79/79 tests pass (Phase 1+2 regression 39 + Phase 3 unit 32 + Phase 3 API 8). Migration 030_pii_provider_settings applied to live Supabase qedhulpfezucnfadlfiz (9 columns + 7 CHECK constraints). Egress filter blocks raw PII pre-cloud-SDK; algorithmic fallback on provider failure (D-52/D-54). Admin UI surfaces all 9 PII settings + 2 status badges. Verification: `.planning/phases/03-entity-resolution-llm-provider-configuration/03-VERIFICATION.md` (status: passed). Next: Phase 4 (FUZZY-01..03, MISSED-01..03, PROMPT-01..03).*

*Updated: 2026-04-27 — Phase 4 context gathered ✓: 4 gray areas resolved across 16 questions, 16 implementation decisions (D-67..D-82) in `04-CONTEXT.md`. Areas: fuzzy algorithm/library/threshold/normalization (D-67..D-70), 3-phase pipeline integration (D-71..D-74), missed-PII scan placement (D-75..D-78), system-prompt guidance (D-79..D-82). Locks: rapidfuzz library (transitive Presidio dep), per-cluster variant scoping, FUZZY_DEANON_THRESHOLD=0.85 default + DB column, in-place upgrade of de_anonymize_text with mode param, placeholder-tokenized text in / JSON `[{span,token}]` out for LLM mode, hard-redact survival inherited from Phase 2 D-24/REG-05, auto-chain missed-scan inside redact_text, full re-run on replacement (single re-run cap), `[{type,text}]` server-substring-match schema, soft-fail with warn-log + span tag + counter metric, centralized prompt-guidance helper appended in chat.py + agent_service.py, conditional on per-thread redaction-enabled flag, English-only phrasing, imperative + type list + [TYPE] warning + examples. New migration 031 plans `fuzzy_deanon_mode` + `fuzzy_deanon_threshold` columns. Ready for /gsd-plan-phase 4.*

**Next Phase:** 4 — Fuzzy De-anonymization, Missed-PII Scan & Prompt Guidance — context gathered, ready to plan

- Phase 4 plan 04-01 Task 3 (live Supabase DB apply of migration 031) pending orchestrator MCP apply — executor agent does not have mcp__claude_ai_Supabase__apply_migration in tool registry. Migration file ready at supabase/migrations/031_pii_fuzzy_settings.sql.

*Updated: 2026-04-27 — Phase 4 plan 04-01 PARTIAL ✦: Tasks 1+2 SHIPPED (commits `53bdb9d` config.py +Field import +2 Settings fields with Pydantic Literal+Field(ge,le) validation, `4f0d724` supabase/migrations/031_pii_fuzzy_settings.sql with mode CHECK + threshold range CHECK + comments). Task 3 (live Supabase apply via MCP) PENDING — executor agent has no mcp__claude_ai_Supabase__apply_migration in registry (same gap as Phase 3 plan 03-02). Live REST probe confirms columns absent (PG 42703); apply queries pre-staged in `04-01-SUMMARY.md`. SUMMARY at `.planning/phases/04-fuzzy-de-anonymization-missed-pii-scan-prompt-guidance/04-01-SUMMARY.md`.*

*Updated: 2026-04-27 — Phase 4 EXECUTION COMPLETE ✅: 7 plans across 6 waves; all 9 REQ-IDs (DEANON-03..05, SCAN-01..05, PROMPT-01) SATISFIED; 5/5 ROADMAP SCs verified. 135/135 backend tests pass (75 unit + 60 integration: 17 new Phase 4 + 39 Phase 1+2 + 8 Phase 3 + 75 unit including 13 new missed_scan + 11 prompt_guidance + 23 fuzzy_match). Migration 031 applied live to Supabase qedhulpfezucnfadlfiz (orchestrator MCP). 3-phase de_anon pipeline (surrogate→placeholder→fuzzy/LLM-match→real) ships in `redaction_service.py:de_anonymize_text(mode=...)` with backward-compatible `mode=None` default. Missed-PII scan auto-chained inside `_redact_text_with_registry` with single-re-run cap (`_scan_rerun_done`). Centralized prompt-guidance helper (`prompt_guidance.py`) wired into both single-agent (`chat.py`) and 4 sub-agent paths (`agent_service.py`). Admin UI surfaces fuzzy mode + threshold inside the existing PII section. Phase 3 regression introduced by auto-chain RESOLVED via parallel patch on `missed_scan.get_settings` in 2 tests (commit `b9ced3e`). Verification: `.planning/phases/04-fuzzy-de-anonymization-missed-pii-scan-prompt-guidance/04-VERIFICATION.md` (status: passed, 16/16 decisions D-67..D-82 traced). Next: Phase 5 (Chat-Loop Integration).*

*Updated: 2026-04-27 — Phase 5 context gathered ✓: 4 gray areas resolved across 17 questions, 15 implementation decisions (D-83..D-97) in `05-CONTEXT.md`. Areas: redaction-flag source-of-truth (D-83..D-86 — global env-var, hybrid gate, persist real form, registry-once-per-turn); buffering UX & SSE shape (D-87..D-90 — single-batch delta, two redaction_status events, skeleton tool events, graceful degrade); tool-call symmetry (D-91..D-94 — centralized walker module, redact_text_batch primitive, single batched history anon, pre-flight egress on OpenRouter calls); sub-agent / auxiliary scope (D-95..D-97 — chat-loop only, hybrid title_gen-via-LLMProviderClient + classify_intent stays, mirror Phase 4 test pattern). Locks: zero new migrations (Phase 3 D-57 column already shipped for title_gen), zero new env vars, OpenRouterService unchanged (refactor deferred to Phase 6+), document_tool_service deferred to v1.1, document_metadata deferred to v1.1. Ready for /gsd-plan-phase 5.*
