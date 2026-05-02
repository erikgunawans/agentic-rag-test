---
gsd_state_version: 1.0
milestone: v1.2
milestone_name: Advanced Tool Calling & Agent Intelligence
status: planning
last_updated: "2026-05-02T07:49:11.777Z"
last_activity: 2026-05-02
progress:
  total_phases: 0
  completed_phases: 0
  total_plans: 0
  completed_plans: 0
  percent: 0
---

# State: LexCore

## Project Reference

See: `.planning/PROJECT.md` (updated 2026-05-02 — v1.2 milestone started)

**Core value:** Indonesian legal teams can manage the full contract lifecycle with confidence that AI outputs are accurate, citable, and traceable, and that sensitive client PII never leaves the control boundary.
**Current focus:** v1.2 Advanced Tool Calling & Agent Intelligence — dynamic tool registry, sandbox-bridge code mode, MCP client integration, plus chat-UX improvements (context-window indicator, interleaved history). All tool-calling work ships dark behind feature flags. Source PRD: `docs/superpowers/PRD-advanced-tool-calling.md`.

## Current Position

Phase: Not started (defining requirements)
Plan: —
Status: Defining requirements
Last activity: 2026-05-02 — Milestone v1.2 started

## Accumulated Context

- Codebase map at `.planning/codebase/` (refreshed 2026-04-25, commit `f1a8c62`)
- v1.0 milestone archived to `.planning/milestones/` (ROADMAP, REQUIREMENTS)
- Knowledge graph at `graphify-out/` (1,211 nodes, 192 communities; god-nodes: `HybridRetrievalService`, `ToolService`)
- Workflow config: `granularity=standard`, `parallel=true`, `model_profile=balanced`, `research=skip`, `plan_check=on`, `verifier=on`
- Active deployments: Frontend on Vercel (`main` branch), Backend on Railway, Supabase project `qedhulpfezucnfadlfiz`
- Migrations applied to production: 001–033 (029–033 added in v1.0 milestone)
- New redaction subsystem: 10 modules under `backend/app/services/redaction/`

## Deferred Items

Items carried forward at milestone closes (v1.0 → v1.1 → next):

| Source | Category | Item | Status |
|--------|----------|------|--------|
| v1.0 | UAT | PERF-02: 500ms anonymization target on server hardware | Pending hardware run |
| v1.0 | Tech debt | Async-lock cross-process upgrade (D-31): per-process asyncio.Lock for PERF-03 breaks under multi-worker / horizontally-scaled Railway instances. Replace with `pg_advisory_xact_lock(hashtext(thread_id))` when scale-out needed | Deferred to future milestone |
| v1.0 | Privacy | Fix B (PII deny list): domain-term deny list at `backend/app/services/redaction/detection.py` | **Bundled into v1.2** |
| v1.0 | Audit residuals | Phase 04 CONTEXT.md (3 open questions); Phase 05 UAT (resolved, 0 pending); Phase 06 UAT (partial, 0 pending); Phase 06 verification gap (`human_needed`) | Pre-existing v1.0 audit residuals, not blocking |
| v1.1 | Tests | No frontend component tests for `CodeExecutionPanel.tsx` (360-line component, UAT-only coverage today) | **Bundled into v1.2** |
| v1.1 | UX | Signed-URL download UX in panel — `handleDownload` shows generic 2-second toast, no 404 vs 500 vs network distinction | Cosmetic |
| v1.1 | Tech debt | base-ui `asChild` shim sweep — `popover.tsx` fix shipped during v1.1 close; remaining wrappers (select, dropdown-menu, dialog) likely need the same shim | **Bundled into v1.2** |
| v1.1 | Sandbox | Multi-worker IPython session semantics — in-memory sessions don't survive Railway replica scaling | Pre-existing Phase 10 concern |

## Blockers

(None)

---
*Initialized: 2026-04-25 after `/gsd-new-project` brownfield bootstrap*
*v1.0 milestone complete: 2026-04-29 — 6 phases, 44 plans, 352 tests, privacy invariant enforced end-to-end*
*v1.1 milestone complete: 2026-05-02 — 5 phases (7–11), 26 plans, ~314 tests, 3 migrations (034–036). Shipped to prod as v0.5.0.0 (tag `v0.5.0.0`). Skills system + Code Execution Sandbox + Persistent Tool Memory.*
*v1.2 milestone started: 2026-05-02 — Advanced Tool Calling & Agent Intelligence. Phase numbering continues from 11 → starts at Phase 12. Defining requirements next.*
