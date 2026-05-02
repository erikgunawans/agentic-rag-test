# Roadmap: LexCore

**Created:** 2026-04-25
**Project:** LexCore — PJAA CLM Platform
**Core Value:** Indonesian legal teams can manage the full contract lifecycle with confidence that AI outputs are accurate, citable, and traceable, and that sensitive client PII never leaves the control boundary.

## Milestones

- ✅ **v1.0 PII Redaction System** — Phases 1–6 (shipped 2026-04-29)
- ✅ **v1.1 Agent Skills & Code Execution** — Phases 7–11 (shipped 2026-05-02 as v0.5.0.0)
- ✅ **v1.2 Advanced Tool Calling & Agent Intelligence** — Phases 12–16 (shipped 2026-05-03)
- 🚧 **v1.3 Agent Harness & Domain-Specific Workflows** — Phases 17–22 (started 2026-05-03)

## Phases

### v1.3 Agent Harness & Domain-Specific Workflows (Phases 17–22)

- [ ] **Phase 17: Deep Mode Foundation + Planning Todos + Plan Panel** — Per-message Deep Mode toggle, extended agent loop, agent_todos table + RLS, write_todos/read_todos tools, Plan Panel UI, deep_mode persistence on messages
- [ ] **Phase 18: Workspace Virtual Filesystem** — workspace_files table + RLS, write_file/read_file/edit_file/list_files tools, REST endpoints, Workspace Panel UI, sandbox file integration
- [ ] **Phase 19: Sub-Agent Delegation + Ask User + Status & Recovery** — task tool with isolated context, ask_user mid-task clarification, agent status indicators, error append-only recovery, resume-after-pause
- [ ] **Phase 20: Harness Engine Core + Gatekeeper + Post-Harness + File Upload + Locked Plan Panel** — harness_runs table + RLS, PhaseType dispatcher, programmatic + llm_single + llm_agent phase types, gatekeeper LLM with TRIGGER_HARNESS sentinel, post-harness summary LLM, DOCX/PDF upload, locked Plan Panel for harness runs, observability + security cross-cuts
- [ ] **Phase 21: Batched Parallel Sub-Agents + Human-in-the-Loop** — llm_batch_agents phase type with asyncio.gather + queue streaming + mid-batch resume, llm_human_input phase type with informed-question generation
- [ ] **Phase 22: Contract Review Harness + DOCX Deliverable** — 8-phase deterministic Contract Review workflow (intake → classify → context → playbook → clauses → risk → redlines → summary), DOCX report via sandbox python-docx, non-fatal fallback

**Total:** 6 phases · 111 requirements (DEEP×7, TODO×7, WS×11, TASK×7, ASK×4, STATUS×6, HARN×10, GATE×5, POST×5, HIL×4, BATCH×7, UPL×4, PANEL×4, CR×8, DOCX×8, MIG×4, SEC×4, OBS×3, CONF×3) · feature-flag dark-launch via existing `TOOL_REGISTRY_ENABLED` plus new toggles surfaced through admin settings

<details>
<summary>✅ v1.2 Advanced Tool Calling & Agent Intelligence (Phases 12–16) — SHIPPED 2026-05-03</summary>

Full archive: `.planning/milestones/v1.2-ROADMAP.md`

- [x] **Phase 12: Chat UX — Context Window Indicator & Interleaved History** (7/7 plans) — completed 2026-05-02
- [x] **Phase 13: Unified Tool Registry & `tool_search` Meta-Tool** (5/5 plans) — completed 2026-05-02
- [x] **Phase 14: Sandbox HTTP Bridge (Code Mode)** (5/5 plans) — completed 2026-05-03
- [x] **Phase 15: MCP Client Integration** (5/5 plans) — completed 2026-05-03 (verified PASS, 26/26 must-haves)
- [x] **Phase 16: v1.1 Backlog Cleanup (Fix B + Panel Tests + asChild Sweep)** (3/3 plans) — completed 2026-05-02

**Total:** 25 plans · 34 requirements (CTX×6, HIST×6, TOOL×6, BRIDGE×7, MCP×6, REDACT×1, TEST×1, UI×1) · Wave A (12‖13‖16) + Wave B (14‖15) parallel execution · all features dark-flag-gated (`TOOL_REGISTRY_ENABLED`, `SANDBOX_ENABLED`)

</details>

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

### Phase 17: Deep Mode Foundation + Planning Todos + Plan Panel

**Goal**: Users can toggle Deep Mode per-message and watch the agent build, mutate, and execute a real-time todo plan inside an extended agent loop, with all plan state persisted thread-side and surfaced through a Plan Panel that survives page reloads.
**Depends on**: Nothing (independent foundation; can run in parallel with Phase 18 once `agent_todos` migration lands)
**Requirements**: DEEP-01, DEEP-02, DEEP-03, DEEP-04, DEEP-05, DEEP-06, DEEP-07, TODO-01, TODO-02, TODO-03, TODO-04, TODO-05, TODO-06, TODO-07, MIG-01, MIG-04, SEC-01, CONF-01, CONF-02, CONF-03
**Success Criteria** (what must be TRUE):
  1. User clicks the Deep Mode toggle next to Send and the next message routes through the extended agent loop (extended system prompt, deep-mode tools loaded, `MAX_DEEP_ROUNDS=50` cap); with Deep Mode OFF, chat behavior is byte-identical to v1.2 (zero token overhead, no extra tools).
  2. While the agent is working, the Plan Panel sidebar streams real-time `todos_updated` SSE events — each todo flips pending → in_progress → completed, and the LLM can adaptively add / remove / rewrite tasks mid-execution.
  3. Reloading any thread that ran in Deep Mode reconstructs the last-known todo state from `agent_todos` and renders the same Plan Panel (Deep Mode badge included), with `messages.deep_mode` distinguishing deep messages from standard ones.
  4. Loop-exhaustion at `MAX_DEEP_ROUNDS` forces the agent to summarize and deliver (graceful degradation, not a crash); user can interrupt mid-loop and all completed work persists.
  5. RLS on `agent_todos` enforces thread-ownership scope — User A cannot read or write User B's todos via direct table access; configuration knobs (`MAX_DEEP_ROUNDS`, `MAX_TOOL_ROUNDS`, `MAX_SUB_AGENT_ROUNDS`) are env-driven with documented defaults.
**Plans**: TBD
**UI hint**: yes

### Phase 18: Workspace Virtual Filesystem

**Goal**: A per-thread virtual filesystem holds text and binary artifacts produced by the agent, sandbox, or user upload, surfaces them through file-manipulation LLM tools and a Workspace Panel, and replaces the current sandbox-file-disappears-after-execution problem with a durable cross-device store.
**Depends on**: Nothing (foundation in parallel with Phase 17 once `workspace_files` migration lands; sandbox-file integration touches v1.1 sandbox code path)
**Requirements**: WS-01, WS-02, WS-03, WS-04, WS-05, WS-06, WS-07, WS-08, WS-09, WS-10, WS-11, MIG-02
**Success Criteria** (what must be TRUE):
  1. Agent calls `write_file`, `read_file`, `edit_file`, and `list_files` against a per-thread workspace; path validation rejects path traversal, leading slashes, backslashes, paths >500 chars, and text content >1 MB with structured tool errors (no exceptions).
  2. Text files persist in `workspace_files.content` (sub-100 ms reads); binaries persist in Supabase Storage with metadata in DB; sandbox-generated downloads now auto-register as `source="sandbox"` workspace entries (fixing the v1.1 disappearing-link issue).
  3. User opens any thread (Deep Mode or harness) and the Workspace Panel sidebar shows the file list with sizes and source badges (agent / sandbox / upload); clicking a text file opens an inline view, clicking a binary triggers a signed-URL download.
  4. `GET /threads/{id}/files` and `GET /threads/{id}/files/{path}` return RLS-scoped results, real-time `workspace_updated` SSE events fire on every mutation, and sub-agents share the parent thread's workspace transparently.
  5. Workspace Panel is decoupled from Deep Mode — it appears whenever a thread has at least one workspace file, so harness runs and standard sandbox uploads can populate it independently.
**Plans**: TBD
**UI hint**: yes

### Phase 19: Sub-Agent Delegation + Ask User + Status & Recovery

**Goal**: Deep Mode agents can fan work out to isolated-context sub-agents, pause to ask the user a clarifying question mid-loop, and surface working / waiting / complete / error status while never crashing the parent loop on failures.
**Depends on**: Phase 17 (deep loop), Phase 18 (workspace shared with sub-agents)
**Requirements**: TASK-01, TASK-02, TASK-03, TASK-04, TASK-05, TASK-06, TASK-07, ASK-01, ASK-02, ASK-03, ASK-04, STATUS-01, STATUS-02, STATUS-03, STATUS-04, STATUS-05, STATUS-06
**Success Criteria** (what must be TRUE):
  1. Agent calls `task(description, context_files)` to spawn a sub-agent that inherits parent tools minus `task` / `write_todos` / `read_todos`, shares the parent workspace (read+write), and returns its last assistant message as the tool result; existing `analyze_document` and `explore_knowledge_base` sub-agents still work unchanged.
  2. Agent calls `ask_user(question)` and the loop pauses with `agent_status="waiting_for_user"`; an `ask_user` SSE event surfaces the question, and the user's reply is delivered as the tool's result (not as a new top-level user message), then the loop resumes.
  3. Status indicator surfaces `working` / `waiting_for_user` / `complete` / `error` states in the chat header; failed tool calls remain in conversation context (append-only) so the LLM can recover without retries, and sub-agent failures isolate to the parent (parent loop never crashes).
  4. After every loop round, messages + tool calls + todos + workspace are persisted to DB; user can resume a paused thread by sending a follow-up message and the agent reads existing todos / workspace and continues without re-priming.
  5. No automatic retries are issued anywhere in the loop — every recovery decision (retry, alternative path, `ask_user` escalation) is LLM-driven and visible in the conversation transcript; `task` start / complete SSE events drive the nested sub-agent UI rendering.
**Plans**: TBD
**UI hint**: yes

### Phase 20: Harness Engine Core + Gatekeeper + Post-Harness + File Upload + Locked Plan Panel

**Goal**: A backend state-machine harness engine dispatches typed phases (programmatic / llm_single / llm_agent) against a thin orchestrator and workspace-passed context, gated by a conversational gatekeeper LLM and capped by a post-harness response LLM that streams a concise summary referencing workspace artifacts; the Plan Panel locks for harness runs and the user can upload DOCX / PDF source files.
**Depends on**: Phase 17 (Plan Panel + todos), Phase 18 (workspace), Phase 19 (sub-agent loop primitives reused by `llm_agent` phases)
**Requirements**: HARN-01, HARN-02, HARN-03, HARN-04, HARN-05, HARN-06, HARN-07, HARN-08, HARN-09, HARN-10, MIG-03, GATE-01, GATE-02, GATE-03, GATE-04, GATE-05, POST-01, POST-02, POST-03, POST-04, POST-05, PANEL-01, PANEL-02, PANEL-03, PANEL-04, UPL-01, UPL-02, UPL-03, UPL-04, SEC-02, SEC-03, SEC-04, OBS-01, OBS-02, OBS-03
**Success Criteria** (what must be TRUE):
  1. With a registered harness, the gatekeeper LLM runs before each user message with no active/completed harness run, supports multi-turn dialogue ("upload your contract first"), and emits `[TRIGGER_HARNESS]` to start the harness in the same SSE stream — harnesses without prerequisites skip the gatekeeper entirely.
  2. The harness engine dispatches `programmatic`, `llm_single`, and `llm_agent` phases through a typed `PhaseDefinition` dataclass + `HarnessRegistry` dict, persists state in `harness_runs` (RLS, unique active run per thread), enforces per-phase timeouts (120 s / 300 s defaults) and clean cancellation between rounds/phases, and offloads context to workspace files so the orchestrator stays ~5 k tokens regardless of contract size.
  3. `llm_single` phases enforce structured output via `response_format: json_schema` + Pydantic validation before advancing; phase failures, completions, starts emit the full SSE event suite (`harness_phase_start/_complete/_error`, `harness_complete`, `harness_human_input_required`).
  4. After harness completion, a separate post-harness LLM call loads phase results into a system prompt (truncated at 30 k chars with last 2 phases kept in full), streams a ~500-token summary as a separate assistant message, and follow-up user messages route through the normal LLM loop with phase results in context.
  5. User uploads DOCX / PDF via `POST /threads/{id}/files/upload` (binary in Storage, metadata in `workspace_files` with `source='upload'`, text extracted via `python-docx` / `PyPDF2` for harness consumption); harness phases write to `agent_todos` so the Plan Panel shows phases progressing, with `write_todos`/`read_todos` stripped from harness-phase tool sets and a lock icon on the Plan Panel header to communicate immutability.
  6. Cross-cutting: all new agent + harness paths route LLM payloads through the existing PII redaction egress filter (privacy invariant preserved), sub-agents run inside the parent user's auth context (no privilege escalation), provider API keys stay server-side; harness writes a single-writer `progress.md` per phase transition with intermediate summaries, all operations include `thread_id` correlation logging, and existing LangSmith tracing covers the new agent loop and harness phases.
**Plans**: TBD
**UI hint**: yes

### Phase 21: Batched Parallel Sub-Agents + Human-in-the-Loop

**Goal**: Add the two harness phase types that turn the engine from sequential into a fan-out workflow platform — `llm_batch_agents` runs sub-agents in parallel batches with real-time streaming and mid-batch resumability, and `llm_human_input` pauses the harness to ask the user an informed question and resumes when they reply.
**Depends on**: Phase 20 (engine core, sub-agent infrastructure, workspace context-passing)
**Requirements**: BATCH-01, BATCH-02, BATCH-03, BATCH-04, BATCH-05, BATCH-06, BATCH-07, HIL-01, HIL-02, HIL-03, HIL-04
**Success Criteria** (what must be TRUE):
  1. `llm_batch_agents` parses items from a workspace input file (e.g. `clauses.md` JSON array), chunks into batches of `batch_size` (default 5), and runs each batch concurrently via `asyncio.gather()` reusing the `run_task_agent()` pattern from Phase 19.
  2. Sub-agent SSE events stream in real-time via `asyncio.Queue` (not delayed until the batch completes) so the user sees nested "Analyzing item N/M" updates with live tool calls; each sub-agent reads only the workspace inputs it needs.
  3. Results accumulate into a workspace output file per batch; if the harness crashes or the client disconnects mid-batch, resuming detects the partial output (e.g. 10 of 15 written) and resumes from where it left off without redoing completed items.
  4. `llm_human_input` phase generates an informed question from prior phase results, streams it as a normal chat message (not in the phase panel), sets harness status to `paused`, and on user reply writes the response into a workspace file, marks the phase complete, and resumes the harness.
  5. Mid-stream cancellation of `llm_human_input` is explicitly out of scope — cancellation only happens between rounds/phases, consistent with the rest of the engine cancellation contract.
**Plans**: TBD

### Phase 22: Contract Review Harness + DOCX Deliverable

**Goal**: Ship the first domain harness — an 8-phase deterministic Contract Review workflow that exercises every phase type end-to-end and produces a polished `.docx` executive report with title page, summary, redline tables, and recommendations.
**Depends on**: Phase 20 (engine core), Phase 21 (batch + HIL phase types)
**Requirements**: CR-01, CR-02, CR-03, CR-04, CR-05, CR-06, CR-07, CR-08, DOCX-01, DOCX-02, DOCX-03, DOCX-04, DOCX-05, DOCX-06, DOCX-07, DOCX-08
**Success Criteria** (what must be TRUE):
  1. User uploads a contract (DOCX or PDF) and the gatekeeper triggers the Contract Review harness; Phase 1 (intake, programmatic) extracts text via `python-docx` / `PyPDF2` and writes `contract-text.md`; Phase 2 (classification, llm_single) writes `classification.md` with type / parties (≥2) / dates / governing law / jurisdiction enforced via Pydantic.
  2. Phase 3 (gather context, llm_human_input) asks the user informed questions (which side, deadline, focus areas, deal context) and writes `review-context.md`; Phase 4 (load playbook, llm_agent with RAG, max 10 rounds) discovers playbook materials via `search_documents` + `analyze_document` and writes `playbook-context.md` with doc IDs, titles, summaries, clause-category mappings.
  3. Phase 5 (clause extraction, programmatic with internal LLM) writes `clauses.md` as a JSON array of every clause across the 13 categories (Liability, Indemnification, IP, Data Protection, Confidentiality, Warranties, Term/Termination, Governing Law, Insurance, Assignment, Force Majeure, Payment, Other); contracts >50 k tokens chunk with overlap and dedupe-merge.
  4. Phase 6 (risk analysis, llm_batch_agents batch_size=5) assigns GREEN/YELLOW/RED per clause against the playbook with rationale + alternative language, exposing real-time "Analyzing clause N/M" with nested RAG tool calls; Phase 7 (redline generation, llm_batch_agents batch_size=5) processes only YELLOW/RED clauses and writes `redlines.md` with original / proposed replacement / rationale / fallback positions.
  5. Phase 8 (executive summary, llm_single + post_execute) writes `contract-review-report.md` (overall risk, recommendation, key findings, RED/YELLOW/GREEN breakdown), and the post_execute callback runs a sandbox python-docx script to generate a CONFIDENTIAL-marked `.docx` with title page, executive summary, key findings list, color-coded redline table, acceptable-clauses (GREEN) section, and recommended next steps; if sandbox is unavailable, the markdown report is still saved (non-fatal degradation).
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

## Progress (v1.3 — IN PROGRESS)

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 17. Deep Mode Foundation + Planning Todos + Plan Panel | 7/7 | Complete    | 2026-05-02 |
| 18. Workspace Virtual Filesystem | 0/0 | Not started | — |
| 19. Sub-Agent Delegation + Ask User + Status & Recovery | 0/0 | Not started | — |
| 20. Harness Engine Core + Gatekeeper + Post-Harness + Upload + Locked Panel | 0/0 | Not started | — |
| 21. Batched Parallel Sub-Agents + Human-in-the-Loop | 0/0 | Not started | — |
| 22. Contract Review Harness + DOCX Deliverable | 0/0 | Not started | — |

## Phase Numbering

- **Integer phases (1, 2, 3, …):** Planned milestone work. Numbering is **monotonic across milestones** for this project: v1.0 = 1–6, v1.1 = 7–11, v1.2 = 12–16, v1.3 = 17–22.
- **Decimal phases (e.g. 2.1):** Urgent insertions created via `/gsd-insert-phase`.

## Parallelization Notes (workflow.parallel=true)

- **Phase 17** and **Phase 18** are independent foundations — both touch chat-loop wiring but on disjoint surfaces (Phase 17 = deep-mode branch + todo tools; Phase 18 = workspace tools + Workspace Panel + sandbox file integration). They can run as a parallel wave once the two migrations (`agent_todos`, `workspace_files`, plus `messages.deep_mode`/`harness_mode` columns) land.
- **Phase 19** requires both Phase 17 (deep loop is the parent loop sub-agents fork from) and Phase 18 (workspace is shared parent↔sub-agent context). Cannot run earlier without stubbing.
- **Phase 20** requires Phases 17, 18, 19 — engine reuses Plan Panel (17), workspace context-passing (18), and sub-agent + auth-context plumbing (19). It also folds in `harness_runs` migration, gatekeeper, post-harness, file upload, locked Plan Panel, OBS / SEC cross-cutting concerns.
- **Phase 21** extends Phase 20's engine with the two non-trivial phase types (batch + HIL). Strictly sequential after Phase 20.
- **Phase 22** is the first domain consumer and exercises every phase type — strictly sequential after Phase 21.

**Suggested wave plan:**

- **Wave A (parallel)**: Phase 17 ‖ Phase 18 — both foundations; merge gates: agent_todos / workspace_files migrations co-applied early; chat.py edits coordinated via discuss-phase
- **Wave B (sequential)**: Phase 19 — joins Wave A on the deep loop + workspace
- **Wave C (single)**: Phase 20 — large phase (35 reqs), expect 8–10 plans
- **Wave D (sequential)**: Phase 21 — engine extension
- **Wave E (sequential, capstone)**: Phase 22 — domain harness + DOCX

Cross-cutting requirements split rule:
- `MIG-*` co-located with the phase that needs the table (MIG-01 + MIG-04 → 17, MIG-02 → 18, MIG-03 → 20)
- `SEC-01` (RLS on new tables) → Phase 17 since `agent_todos` is the first new table; subsequent phases extend the same RLS pattern to their own tables
- `SEC-02..04` (sub-agent auth, key custody, egress filter coverage) → Phase 20 where harness fan-out and external upload first stress the boundary
- `OBS-01..03` (progress.md, thread_id correlation, LangSmith) → Phase 20 where harness phase transitions are the first non-trivial observability surface
- `CONF-01..03` (loop iteration env caps) → Phase 17 where the deep loop is introduced

---
*Roadmap created: 2026-04-25*
*v1.0 milestone archived: 2026-04-29 — see `.planning/milestones/v1.0-ROADMAP.md` for full phase details*
*v1.1 milestone archived: 2026-05-02 — see `.planning/milestones/v1.1-ROADMAP.md` for full phase details*
*v1.2 milestone archived: 2026-05-03 — see `.planning/milestones/v1.2-ROADMAP.md` for full phase details*
*v1.3 milestone phases (17–22) added: 2026-05-03 — Agent Harness & Domain-Specific Workflows; 6 phases / 111 requirements / 4 migrations (`agent_todos`, `workspace_files`, `harness_runs`, `messages.deep_mode|harness_mode`); Contract Review Harness as first domain implementation*
