# Roadmap: LexCore

**Created:** 2026-04-25
**Project:** LexCore — PJAA CLM Platform
**Core Value:** Indonesian legal teams can manage the full contract lifecycle with confidence that AI outputs are accurate, citable, and traceable, and that sensitive client PII never leaves the control boundary.

## Milestones

- ✅ **v1.0 PII Redaction System** — Phases 1–6 (shipped 2026-04-29)
- ✅ **v1.1 Agent Skills & Code Execution** — Phases 7–11 (shipped 2026-05-02 as v0.5.0.0)
- 🚧 **v1.2 Advanced Tool Calling & Agent Intelligence** — Phases 12–16 (started 2026-05-02)

## Phases

### Active (v1.2)

- [ ] **Phase 12: Chat UX — Context Window Indicator & Interleaved History** — Token-usage progress bar + faithful history reload of sub-agent / code-execution panels
- [ ] **Phase 13: Unified Tool Registry & `tool_search` Meta-Tool** — Dynamic registry + compact catalog, flag-gated dark launch, byte-identical fallback
- [ ] **Phase 14: Sandbox HTTP Bridge (Code Mode)** — `/bridge/*` endpoints + pre-baked `ToolClient` + runtime-injected typed stubs from sandbox to host registry
- [ ] **Phase 15: MCP Client Integration** — `MCPClientManager` over stdio, eager schema conversion, registry registration as `source="mcp"`, reconnect-with-backoff
- [ ] **Phase 16: v1.1 Backlog Cleanup (Fix B + Panel Tests + asChild Sweep)** — PII deny list, `CodeExecutionPanel` component tests, base-ui `asChild` shim sweep

<details>
<summary>✅ v1.0 PII Redaction System (Phases 1–6) — SHIPPED 2026-04-29</summary>

Full archive: `.planning/milestones/v1.0-ROADMAP.md`

- [x] **Phase 1: Detection & Anonymization Foundation** (7/7 plans) — completed 2026-04-26
- [x] **Phase 2: Conversation-Scoped Registry & Round-Trip** (6/6 plans) — completed 2026-04-26
- [x] **Phase 3: Entity Resolution & LLM Provider Configuration** (7/7 plans) — completed 2026-04-26
- [x] **Phase 4: Fuzzy De-anonymization, Missed-PII Scan & Prompt Guidance** (7/7 plans) — completed 2026-04-27
- [x] **Phase 5: Chat-Loop Integration (Buffering, SSE Status, Tool/Sub-Agent Coverage)** (9/9 plans) — completed 2026-04-28
- [x] **Phase 6: Embedding Provider & Production Hardening** (8/8 plans) — completed 2026-04-29

**Total:** 44 plans · 352 tests · 5 migrations (029–033) · privacy invariant enforced end-to-end

</details>

<details>
<summary>✅ v1.1 Agent Skills & Code Execution (Phases 7–11) — SHIPPED 2026-05-02 as v0.5.0.0</summary>

Full archive: `.planning/milestones/v1.1-ROADMAP.md`

- [x] **Phase 7: Skills Database & API Foundation** (5/5 plans) — completed 2026-04-29
- [x] **Phase 8: LLM Tool Integration & Discovery** (4/4 plans) — completed 2026-05-01 (UAT 4/4 green)
- [x] **Phase 9: Skills Frontend** (4/4 plans) — completed 2026-05-01
- [x] **Phase 10: Code Execution Sandbox Backend** (6/6 plans) — completed 2026-05-01
- [x] **Phase 11: Code Execution UI & Persistent Tool Memory** (7/7 plans) — completed 2026-05-02 (UAT approved, verified PASS-WITH-CAVEATS)

**Total:** 26 plans · ~314 unit/integration tests · 3 migrations (034–036) · Skills system + Code Execution sandbox + persistent tool memory shipped end-to-end

</details>

## Phase Details

### Phase 12: Chat UX — Context Window Indicator & Interleaved History

**Goal**: Users see how much of the LLM context window is consumed and get a faithful, interleaved replay of past chats (sub-agent panels and code-execution terminals included) when reloading or switching threads.
**Depends on**: Nothing (independent of tool-calling chain; ships unconditionally — no feature flag)
**Requirements**: CTX-01, CTX-02, CTX-03, CTX-04, CTX-05, CTX-06, HIST-01, HIST-02, HIST-03, HIST-04, HIST-05, HIST-06
**Success Criteria** (what must be TRUE):
  1. After the first message exchange in a thread, a slim progress bar appears above the chat input showing `Xk / Yk (Z%)` and shifts color green → yellow → red at the 60%/80% thresholds.
  2. Switching threads or starting a new thread resets the bar; threads on providers that ignore `stream_options` simply show no bar (no errors, no broken UI).
  3. Reloading any thread that ran sub-agents or code execution shows the full interleaved transcript — text, tool steps, sub-agent panels, and code-execution panels (with stdout/stderr/output files) appear in the same visual order they streamed in.
  4. Sending a follow-up message in a reloaded thread preserves prior agentic context — the LLM can reference earlier sub-agent findings and code-execution variables/output.
  5. `GET /settings/public` returns `{"context_window": N}` without auth and the frontend honors that value (changing `LLM_CONTEXT_WINDOW` env var without a frontend redeploy still updates the bar's denominator).
**Plans**: TBD
**UI hint**: yes

### Phase 13: Unified Tool Registry & `tool_search` Meta-Tool

**Goal**: A single registry holds all tools (native, skill, MCP) and exposes them to the LLM through a compact catalog plus a `tool_search` meta-tool, scaling tool count without bloating every prompt.
**Depends on**: Nothing (foundation for Phases 14 & 15; safe-off behind `TOOL_REGISTRY_ENABLED=false` so it can ship before consumers are ready)
**Requirements**: TOOL-01, TOOL-02, TOOL-03, TOOL-04, TOOL-05, TOOL-06
**Success Criteria** (what must be TRUE):
  1. With `TOOL_REGISTRY_ENABLED=true`, the LLM system prompt contains a compact catalog of ≤50 tools (name + one-line description, ~500 tokens) and the LLM can call `tool_search` with a keyword or regex to retrieve full schemas for matching tools.
  2. Tools loaded via `tool_search` are usable for the rest of the current conversation turn, then reset on the next request — they never persist across conversations.
  3. With `TOOL_REGISTRY_ENABLED=false` (default), chat behavior is byte-identical to v1.1 — the legacy `build_rag_tools()` path is taken and no registry code runs in the request hot path.
  4. Native tools (the existing 14) register at app startup as `source="native"`, `loading="immediate"`; skill tools register on database load as `source="skill"`, `loading="deferred"`; both appear in the catalog and are callable end-to-end through the registry.
  5. A single `register(name, description, schema, source, loading, executor)` API accepts all three sources, and `dict[str, ToolDefinition]` lookups are O(1) for dispatch.
**Plans:** 5 plans
Plans:
- [ ] 13-01-tool-registry-foundation-PLAN.md — ToolDefinition + register() + build_catalog_block + active-set primitives + config flag
- [ ] 13-02-native-tool-adapter-wrap-PLAN.md — Wrap 14 natives via TOOL_DEFINITIONS adapter (D-P13-01)
- [ ] 13-03-skills-as-first-class-tools-PLAN.md — register_user_skills helper (D-P13-02 skill = first-class tool)
- [ ] 13-04-tool-search-meta-tool-active-set-PLAN.md — tool_search matcher + ranking + regex safety (D-P13-04, D-P13-05)
- [ ] 13-05-chat-wiring-multi-agent-filter-PLAN.md — chat.py three flag-gated splices + should_filter_tool + byte-identical snapshot (D-P13-06, TOOL-05)

### Phase 14: Sandbox HTTP Bridge (Code Mode)

**Goal**: LLM-generated Python in the sandbox can call platform tools through a host-side HTTP bridge with typed stubs, collapsing N tool round-trips into one sandbox execution while keeping credentials on the host.
**Depends on**: Phase 13 (registry is the dispatch surface for `/bridge/call`)
**Requirements**: BRIDGE-01, BRIDGE-02, BRIDGE-03, BRIDGE-04, BRIDGE-05, BRIDGE-06, BRIDGE-07
**Success Criteria** (what must be TRUE):
  1. With `SANDBOX_ENABLED=true` and `TOOL_REGISTRY_ENABLED=true`, code submitted to the sandbox can call `tool_client.call("search_documents", query=...)` (or any registered tool) and receive a structured result; a `code_mode_start` SSE event lists which tools were available for that execution.
  2. The sandbox container has network access only to the bridge endpoint (`host.docker.internal:PORT`) — outbound calls to the public internet, Supabase, OpenAI, etc. fail; service-role keys and MCP connections never enter the container.
  3. Every `/bridge/call` request must carry a valid session token tied to the originating user; calls with a stale, mismatched, or missing token are rejected before tool dispatch, and the existing dangerous-import block list still rejects unsafe submitted code.
  4. Generated typed Python stubs (one per active tool) are injected into the sandbox at runtime so LLM-generated code sees correct function signatures and parameter names; bridge errors return as structured dicts (no exceptions leak from sandbox to host).
  5. With `SANDBOX_ENABLED=false` (default) or `TOOL_REGISTRY_ENABLED=false`, no `/bridge/*` endpoint is reachable in the chat flow and existing v1.1 sandbox behavior is unchanged.
**Plans**: TBD

### Phase 15: MCP Client Integration

**Goal**: External MCP servers (GitHub, Slack, databases, etc.) connect at startup, expose their tools through the unified registry, and become discoverable and callable like native tools.
**Depends on**: Phase 13 (registry is the registration target for MCP tools)
**Requirements**: MCP-01, MCP-02, MCP-03, MCP-04, MCP-05, MCP-06
**Success Criteria** (what must be TRUE):
  1. With `MCP_SERVERS` configured (e.g. `github:npx:-y @modelcontextprotocol/server-github`) and `TOOL_REGISTRY_ENABLED=true`, the app spawns each server via stdio at startup, calls `list_tools()`, and registers each tool in the unified registry as `source="mcp"`, `loading="deferred"`.
  2. MCP tool schemas are converted to OpenAI function-calling format eagerly at connect time; tools whose schemas can't be converted are skipped with a logged error (fail-fast, not fail-at-call).
  3. MCP tools appear in the system-prompt catalog, are discoverable via `tool_search`, and are callable both directly by the LLM and via the sandbox bridge — indistinguishable from native tools to the LLM.
  4. When an MCP server disconnects, the manager marks its tools unavailable, logs the failure, and reconnects with exponential backoff; subsequent successful reconnects re-register the server's tools without an app restart.
  5. With empty `MCP_SERVERS` or `TOOL_REGISTRY_ENABLED=false`, no MCP processes are spawned and there is zero startup-time cost from the MCP subsystem.
**Plans**: TBD

### Phase 16: v1.1 Backlog Cleanup (Fix B + Panel Tests + asChild Sweep)

**Goal**: Close the three operational debts carried forward from v1.1 — domain-term PII false positives, missing `CodeExecutionPanel` test coverage, and base-ui wrappers that crash under `asChild` — so the v1.2 milestone leaves no inherited rough edges.
**Depends on**: Nothing (independent maintenance; can run any wave)
**Requirements**: REDACT-01, TEST-01, UI-01
**Success Criteria** (what must be TRUE):
  1. The PII detection layer at `backend/app/services/redaction/detection.py` honors a configurable deny list — domain terms previously misclassified as PII (e.g. legal vocabulary that tripped Phase 5 production thread `bf1b7325`) pass through unredacted, with a regression test guarding the behavior.
  2. `CodeExecutionPanel.tsx` has automated component tests covering live streaming output, terminal rendering, signed-URL file downloads, and history-reconstruction render parity — replacing the UAT-only coverage that shipped in v1.1.
  3. base-ui wrappers `select.tsx`, `dropdown-menu.tsx`, and `dialog.tsx` accept `asChild` via the same render-prop shim as `tooltip.tsx` and `popover.tsx`; `tsc -b` (project-references mode) builds clean and existing call sites that pass `asChild` no longer error.
  4. All three fixes ship with no behavioral regressions to v1.1 features (PII redaction round-trip, code execution UI, existing select/dropdown/dialog usages).
**Plans**: TBD
**UI hint**: yes

## Completed Phases (Pre-GSD)

The following capabilities shipped before GSD initialization. Tracked as the Validated Baseline in `.planning/milestones/v1.0-REQUIREMENTS.md` (38 requirements).

- **Chat & RAG pipeline** (CHAT-01..07, RAG-01..10) — SSE chat with hybrid retrieval (vector + fulltext + RRF + Cohere rerank), structure-aware chunking, vision OCR, bilingual query expansion, semantic cache, graph reindex, eval harness
- **Document tools** (DOC-01..04) — Create/compare/compliance/analyze via LLM; manual ingestion; folder organization
- **CLM Phase 1** (CLM1-01..06) — Clause library, templates, approvals, obligations, audit trail, user management
- **CLM Phase 2** (CLM2-01..05) — Regulatory intelligence, notifications, dashboard, Dokmee integration, Google export
- **CLM Phase 3** (CLM3-01..02) — Compliance snapshots, UU PDP toolkit
- **BJR Module** (BJR-01..02) — 25 endpoints for board decisions, evidence, risks, taxonomy admin
- **Auth & Admin** (AUTH-01..04) — Supabase Auth, RBAC, RLS, admin UI
- **Settings & Deployment** (SET-01..02, DEPLOY-01..03) — System settings cache, per-user preferences, Vercel + Railway pipeline

## Progress (v1.2)

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 12. Chat UX — Context Window & Interleaved History | 0/0 | Not started | — |
| 13. Unified Tool Registry & `tool_search` | 0/0 | Not started | — |
| 14. Sandbox HTTP Bridge (Code Mode) | 0/0 | Not started | — |
| 15. MCP Client Integration | 0/0 | Not started | — |
| 16. v1.1 Backlog Cleanup | 0/0 | Not started | — |

## Phase Numbering

- **Integer phases (1, 2, 3, …):** Planned milestone work. Numbering is **monotonic across milestones** for this project: v1.0 = 1–6, v1.1 = 7–11, v1.2 = 12–16.
- **Decimal phases (e.g. 2.1):** Urgent insertions created via `/gsd-insert-phase`.

## Parallelization Notes (workflow.parallel=true)

- **Phase 12** is independent of the tool-calling chain — can launch as Wave 1 alongside Phase 13.
- **Phase 13** is the prerequisite for Phases 14 and 15. Must complete before they start.
- **Phases 14 and 15** are independent of each other — designed to launch as a single parallel wave once Phase 13 is green.
- **Phase 16** has zero dependencies and can be slotted into any wave to absorb idle capacity.

Suggested wave plan:
- **Wave A**: Phase 12 ‖ Phase 13 ‖ Phase 16 (3-way parallel, no shared files of consequence)
- **Wave B**: Phase 14 ‖ Phase 15 (2-way parallel after Phase 13 ships the registry)

---
*Roadmap created: 2026-04-25*
*v1.0 milestone archived: 2026-04-29 — see `.planning/milestones/v1.0-ROADMAP.md` for full phase details*
*v1.1 milestone archived: 2026-05-02 — see `.planning/milestones/v1.1-ROADMAP.md` for full phase details*
*v1.2 milestone phases (12–16) added: 2026-05-02 — Advanced Tool Calling & Agent Intelligence; 5 phases / 34 requirements; flag-gated tool-calling features (`TOOL_REGISTRY_ENABLED`, `SANDBOX_ENABLED`)*
