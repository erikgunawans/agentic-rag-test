---
gsd_state_version: 1.0
milestone: v1.3
milestone_name: Agent Harness & Domain-Specific Workflows
status: planning
last_updated: "2026-05-03T12:31:24.386Z"
last_activity: 2026-05-03
progress:
  total_phases: 6
  completed_phases: 3
  total_plans: 25
  completed_plans: 25
  percent: 100
---

# State: LexCore

## Project Reference

See: `.planning/PROJECT.md` (updated 2026-05-03 — v1.3 milestone started)

**Core value:** Indonesian legal teams can manage the full contract lifecycle with confidence that AI outputs are accurate, citable, and traceable, and that sensitive client PII never leaves the control boundary.
**Current focus:** Phase 20 — harness-engine-core-gatekeeper-post-harness-file-upload-lock

## Current Position

Phase: 20
Plan: Not started
Status: Context gathered, ready to plan
Last activity: 2026-05-03 -- 20-CONTEXT.md committed (7ff251c)
Resume file: .planning/phases/20-harness-engine-core-gatekeeper-post-harness-file-upload-lock/20-CONTEXT.md

## Roadmap Snapshot (v1.3)

| Phase | Name | Reqs | Depends on | Status |
|-------|------|------|------------|--------|
| 17 | Deep Mode Foundation + Planning Todos + Plan Panel | DEEP×7 + TODO×7 + MIG-01 + MIG-04 + SEC-01 + CONF×3 (20) | — | Roadmapped, ready to discuss-phase |
| 18 | Workspace Virtual Filesystem | WS×11 + MIG-02 (12) | — | Roadmapped, ready to discuss-phase (parallel with 17) |
| 19 | Sub-Agent Delegation + Ask User + Status & Recovery | TASK×7 + ASK×4 + STATUS×6 (17) | Phase 17, Phase 18 | Roadmapped |
| 20 | Harness Engine Core + Gatekeeper + Post + Upload + Locked Panel | HARN×10 + MIG-03 + GATE×5 + POST×5 + PANEL×4 + UPL×4 + SEC×3 + OBS×3 (35) | Phase 17, 18, 19 | Roadmapped |
| 21 | Batched Parallel Sub-Agents + Human-in-the-Loop | BATCH×7 + HIL×4 (11) | Phase 20 | Roadmapped |
| 22 | Contract Review Harness + DOCX Deliverable | CR×8 + DOCX×8 (16) | Phase 20, 21 | Roadmapped |

**Coverage:** 111/111 v1.3 requirements mapped, no orphans, no duplicates.

**Suggested parallel waves** (`workflow.parallel=true`):

- **Wave A**: Phase 17 ‖ Phase 18 (independent foundations; co-applied migrations + coordinated chat.py edits)
- **Wave B**: Phase 19 (joins Wave A — deep loop + workspace are prereqs)
- **Wave C**: Phase 20 (large engine + cross-cut phase, 8–10 plans expected)
- **Wave D**: Phase 21 (engine extensions — batch + HIL)
- **Wave E**: Phase 22 (capstone domain harness + DOCX)

**4 new migrations expected** (will be 038–041 if numbering preserved):

- 038: `agent_todos` (Phase 17)
- 039: `workspace_files` (Phase 18)
- 040: `harness_runs` (Phase 20)
- 041: `messages.deep_mode` boolean + `messages.harness_mode` text (Phase 17 — bundled with first deep-mode persistence work)

## Accumulated Context

- Codebase map at `.planning/codebase/` (refreshed 2026-04-25, commit `f1a8c62`)
- v1.0 milestone archived to `.planning/milestones/v1.0-*.md` (ROADMAP, REQUIREMENTS)
- v1.1 milestone archived to `.planning/milestones/v1.1-*.md` (ROADMAP, REQUIREMENTS)
- v1.2 milestone archived to `.planning/milestones/v1.2-*.md` (ROADMAP, REQUIREMENTS)
- Knowledge graph at `graphify-out/` (1,211 nodes, 192 communities; god-nodes: `HybridRetrievalService`, `ToolService`)
- Workflow config: `granularity=standard`, `parallel=true`, `model_profile=balanced`, `research=skip`, `plan_check=on`, `verifier=on`
- Active deployments: Frontend on Vercel (`main` branch), Backend on Railway, Supabase project `qedhulpfezucnfadlfiz`
- Migrations applied to production: 001–038 (038 added `agent_todos` table + `messages.deep_mode` column for Phase 17; verified by 6 passing integration tests on 2026-05-03)
- v1.3 contract / invariants:
  - Privacy invariant preserved — all new agent + harness LLM payloads route through `backend/app/services/redaction/egress.py`
  - Frontend agent-loop state machine NOT introduced — all loop control stays in backend (KV-cache friendliness, single source of truth)
  - Workspace files persist server-side only (DB + Supabase Storage, RLS enforced) — no browser-side workspace state
  - Recursive sub-agents disabled — `task` tool removed from sub-agent context
  - No tool-approval prompts inside loop (deferred to post-MVP)
  - No automatic retries — LLM-driven recovery only
  - Harness definitions are global / system-defined (no per-user customization)

## Deferred Items

Items carried forward at milestone closes (v1.0 → v1.1 → v1.2 → next):

| Source | Category | Item | Status |
|--------|----------|------|--------|
| v1.0 | UAT | PERF-02: 500ms anonymization target on server hardware | Pending hardware run |
| v1.0 | Tech debt | Async-lock cross-process upgrade (D-31): per-process asyncio.Lock breaks under multi-worker / horizontally-scaled Railway. Replace with `pg_advisory_xact_lock(hashtext(thread_id))` when scale-out needed | Deferred |
| v1.1 | UX | Signed-URL download UX in panel — `handleDownload` shows generic 2-second toast, no 404 vs 500 vs network distinction | Cosmetic |
| v1.1 | Sandbox | Multi-worker IPython session semantics — in-memory sessions don't survive Railway replica scaling | Pre-existing Phase 10 concern |
| v1.2 | Deploy | Deploy v1.2 features to production (flip `TOOL_REGISTRY_ENABLED=true` + `SANDBOX_ENABLED=true` in Railway env, deploy Docker image, run smoke tests) | Pending operator |

PRD-flagged post-MVP items (explicit in v1.3 REQUIREMENTS.md "Future Requirements"):

- Context auto-compaction / summarization for very-long sessions
- Human-in-the-loop tool approval for sensitive operations
- Agent memory across sessions (persistent per-user instructions)
- Background / async agent runs (loop continues server-side after disconnect)
- Stall detection and auto-replan
- Full SSE reconnection with automatic loop resumption mid-flight
- Additional domain harnesses: NDA generator, vendor assessment, compliance check

## Blockers

(None)

---
*Initialized: 2026-04-25 after `/gsd-new-project` brownfield bootstrap*
*v1.0 milestone complete: 2026-04-29 — 6 phases, 44 plans, 352 tests, privacy invariant enforced end-to-end*
*v1.1 milestone complete: 2026-05-02 — 5 phases (7–11), 26 plans, ~314 tests, 3 migrations (034–036). Shipped to prod as v0.5.0.0.*
*v1.2 milestone complete: 2026-05-03 — 5 phases (12–16), 25 plans, 1 migration (037). Wave A (12‖13‖16) + Wave B (14‖15) parallel execution.*
*v1.3 milestone started: 2026-05-03 — Agent Harness & Domain-Specific Workflows. Phase numbering continues from 16 → starts at Phase 17.*
*v1.3 roadmap created: 2026-05-03 — 6 phases (17–22), 111 requirements (DEEP×7, TODO×7, WS×11, TASK×7, ASK×4, STATUS×6, HARN×10, GATE×5, POST×5, HIL×4, BATCH×7, UPL×4, PANEL×4, CR×8, DOCX×8, MIG×4, SEC×4, OBS×3, CONF×3), 100% coverage, 5-wave plan (A‖18, B=19, C=20, D=21, E=22). Ready for `/gsd-discuss-phase 17` and `/gsd-discuss-phase 18` (parallel).*
