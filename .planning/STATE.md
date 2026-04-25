# State: LexCore

## Project Reference

See: `.planning/PROJECT.md` (updated 2026-04-25)

**Core value:** Indonesian legal teams can manage the full contract lifecycle with confidence that AI outputs are accurate, citable, and traceable.
**Current focus:** Milestone v1.0 — PII Redaction System (chat-time anonymization, no real PII to cloud LLMs).

## Current Position

- **Phase:** Phase 2: Conversation-Scoped Registry & Round-Trip — **EXECUTING** (Wave 1 COMPLETE: 02-01 + 02-02; W2..W5 still pending)
- **Resume file:** `.planning/phases/02-conversation-scoped-registry-and-round-trip/02-03-supabase-db-push-PLAN.md` (Wave 2 — BLOCKING; needs `supabase db push` to land migration 029 before Plan 04 DB methods can run)
- **Status:** Phase 1 SHIPPED ✓ (21 commits `8d06ffe`..`0857bb2`, 20/20 tests). Phase 2 Wave 1 SHIPPED ✓ — plan **02-01** (commit `f7a3ff5`, migration 029 entity_registry written to disk) + plan **02-02** (commit `26cf393`, ConversationRegistry + EntityMapping skeleton, 127 lines, no DB methods). Migration NOT yet pushed; Wave 2 plan 02-03 will run `supabase db push` with explicit user confirmation. 4 plans / 4 waves remain.
- **Last activity:** 2026-04-26 — `/gsd-execute-phase 2` Wave 1 COMPLETE: plan 02-02 shipped at commit `26cf393`. New file `backend/app/services/redaction/registry.py` (127 lines) lands `EntityMapping` (frozen Pydantic v2 model, 5 fields per D-22/D-28) + `ConversationRegistry` skeleton with pure (no-DB) methods: `__init__(thread_id, rows)`, `lookup()` (casefold-correct O(1) — D-36), `entries()` (defensive copy), `forbidden_tokens()` (PERSON-only, honorific-stripped — D-37/D-38), `thread_id` property, counts-only `__repr__`. D-31 FUTURE-WORK note in module docstring captured. Two-line split-import for honorifics + name_extraction mirrors anonymization.py L47-48. NO supabase imports; `load()` / `upsert_delta()` deliberately deferred to Plan 02-04 (after migration push). Inline smoke test PASS; backend import PASS; all 20 Phase 1 tests still green. Zero deviations.

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

(None.)

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
