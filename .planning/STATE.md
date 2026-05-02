---
gsd_state_version: 1.0
milestone: v1.2
milestone_name: Advanced Tool Calling & Agent Intelligence
status: completed
last_updated: "2026-05-02T17:37:03.680Z"
last_activity: 2026-05-02
progress:
  total_phases: 5
  completed_phases: 5
  total_plans: 26
  completed_plans: 28
  percent: 100
---

# State: LexCore

## Project Reference

See: `.planning/PROJECT.md` (updated 2026-05-02 — v1.2 milestone started)

**Core value:** Indonesian legal teams can manage the full contract lifecycle with confidence that AI outputs are accurate, citable, and traceable, and that sensitive client PII never leaves the control boundary.
**Current focus:** Milestone v1.2 Wave B COMPLETE — Phases 14 + 15 executed

## Current Position

Phase: 15 (mcp-client-integration) — EXECUTED + VERIFIED (PASSED, 26/26 must-haves, MCP-01..06)
Phase: 14 (sandbox-http-bridge-code-mode) — EXECUTED (5/5 plans, BRIDGE-01..07, 18 tests green)
Plan: 5 of 5 (both phases complete)
Status: v1.2 milestone all 5 phases complete — ready for /gsd-complete-milestone
Resume: `.planning/phases/15-mcp-client-integration/15-VERIFICATION.md`
Last activity: 2026-05-02

## Roadmap Snapshot (v1.2)

| Phase | Name | Reqs | Depends on | Status |
|-------|------|------|------------|--------|
| 12 | Chat UX — Context Window & Interleaved History | CTX×6 + HIST×6 (12) | — | Planned (7 plans, 7 of 7 executed, 2026-05-02) |
| 13 | Unified Tool Registry & `tool_search` | TOOL×6 (6) | — | Planned (5 plans, 2026-05-02) |
| 14 | Sandbox HTTP Bridge (Code Mode) | BRIDGE×7 (7) | Phase 13 | Context gathered (9 decisions, 2026-05-02); ready to plan |
| 15 | MCP Client Integration | MCP×6 (6) | Phase 13 | Not started |
| 16 | v1.1 Backlog Cleanup | REDACT-01 + TEST-01 + UI-01 (3) | — | Wave 1 executed 2026-05-02 (3/3 plans committed; 16-01 supabase db push pending manual step) |

**Coverage:** 34/34 v1.2 requirements mapped, no orphans.

**Suggested parallel waves** (`workflow.parallel=true`):

- Wave A: Phase 12 ‖ Phase 13 ‖ Phase 16
- Wave B: Phase 14 ‖ Phase 15 (after Phase 13)

## Accumulated Context

- Codebase map at `.planning/codebase/` (refreshed 2026-04-25, commit `f1a8c62`)
- v1.0 milestone archived to `.planning/milestones/` (ROADMAP, REQUIREMENTS)
- v1.1 milestone archived to `.planning/milestones/v1.1-*.md` (ROADMAP, REQUIREMENTS)
- Knowledge graph at `graphify-out/` (1,211 nodes, 192 communities; god-nodes: `HybridRetrievalService`, `ToolService`)
- Workflow config: `granularity=standard`, `parallel=true`, `model_profile=balanced`, `research=skip`, `plan_check=on`, `verifier=on`
- Active deployments: Frontend on Vercel (`main` branch), Backend on Railway, Supabase project `qedhulpfezucnfadlfiz`
- Migrations applied to production: 001–036 (029–033 in v1.0; 034–036 in v1.1)
- New redaction subsystem: 10 modules under `backend/app/services/redaction/`
- v1.2 feature-flag contracts (locked from PROJECT.md):
  - `TOOL_REGISTRY_ENABLED` (default `false`) gates the entire registry / catalog / `tool_search` / bridge / MCP path
  - `SANDBOX_ENABLED` (default `false`, already exists) gates code execution and bridge
  - `LLM_CONTEXT_WINDOW` (default `128000`) drives the context-usage bar
  - Privacy invariant: bridge calls and MCP calls must respect the egress filter at `backend/app/services/redaction/egress.py`

## Deferred Items

Items carried forward at milestone closes (v1.0 → v1.1 → next):

| Source | Category | Item | Status |
|--------|----------|------|--------|
| v1.0 | UAT | PERF-02: 500ms anonymization target on server hardware | Pending hardware run |
| v1.0 | Tech debt | Async-lock cross-process upgrade (D-31): per-process asyncio.Lock for PERF-03 breaks under multi-worker / horizontally-scaled Railway instances. Replace with `pg_advisory_xact_lock(hashtext(thread_id))` when scale-out needed | Deferred to future milestone |
| v1.0 | Privacy | Fix B (PII deny list): domain-term deny list at `backend/app/services/redaction/detection.py` | **Bundled into v1.2 → Phase 16 (REDACT-01)** |
| v1.0 | Audit residuals | Phase 04 CONTEXT.md (3 open questions); Phase 05 UAT (resolved, 0 pending); Phase 06 UAT (partial, 0 pending); Phase 06 verification gap (`human_needed`) | Pre-existing v1.0 audit residuals, not blocking |
| v1.1 | Tests | No frontend component tests for `CodeExecutionPanel.tsx` (360-line component, UAT-only coverage today) | **Bundled into v1.2 → Phase 16 (TEST-01)** |
| v1.1 | UX | Signed-URL download UX in panel — `handleDownload` shows generic 2-second toast, no 404 vs 500 vs network distinction | Cosmetic |
| v1.1 | Tech debt | base-ui `asChild` shim sweep — `popover.tsx` fix shipped during v1.1 close; remaining wrappers (select, dropdown-menu, dialog) likely need the same shim | **Bundled into v1.2 → Phase 16 (UI-01)** |
| v1.1 | Sandbox | Multi-worker IPython session semantics — in-memory sessions don't survive Railway replica scaling | Pre-existing Phase 10 concern |

## Blockers

(None)

---
*Initialized: 2026-04-25 after `/gsd-new-project` brownfield bootstrap*
*v1.0 milestone complete: 2026-04-29 — 6 phases, 44 plans, 352 tests, privacy invariant enforced end-to-end*
*v1.1 milestone complete: 2026-05-02 — 5 phases (7–11), 26 plans, ~314 tests, 3 migrations (034–036). Shipped to prod as v0.5.0.0 (tag `v0.5.0.0`). Skills system + Code Execution Sandbox + Persistent Tool Memory.*
*v1.2 milestone started: 2026-05-02 — Advanced Tool Calling & Agent Intelligence. Phase numbering continues from 11 → starts at Phase 12.*
*v1.2 roadmap created: 2026-05-02 — 5 phases (12–16), 34 requirements (CTX×6, HIST×6, TOOL×6, BRIDGE×7, MCP×6, REDACT×1, TEST×1, UI×1), 100% coverage. Ready to plan first wave.*

*Wave A discuss-phase complete: 2026-05-02 — Phase 12 (Chat UX) + Phase 16 (v1.1 cleanup) auto-mode in parallel background subagents (5 + 5 gray areas auto-decided); Phase 13 (Tool Registry) interactive in main session (4 gray areas, 6 decisions D-P13-01..06 locked: adapter wrap, skill = first-class tool, single unified catalog, tool_search meta-callout, two-param search schema, multi-agent registry filter). Wave A ready for `/gsd-plan-phase 12 / 13 / 16` in any order.*

*Phase 14 discuss-phase complete: 2026-05-02 — Sandbox HTTP Bridge context gathered in --auto mode. 9 decisions locked (D-P14-01..09): fixed configurable bridge port 8002 via BRIDGE_PORT, env-var-based network isolation (Docker network hardening deferred), thread-scoped token tied to 30-min sandbox session TTL, one-time stub file write to /sandbox/stubs.py via execute_command, dual-flag gate (SANDBOX_ENABLED + TOOL_REGISTRY_ENABLED both required), _check_dangerous_imports() in sandbox_service.py, code_mode_start SSE event, ToolClient via stdlib urllib.request in backend/sandbox/Dockerfile, two-layer JWT + session-token auth on bridge router.*
