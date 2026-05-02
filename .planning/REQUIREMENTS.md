# LexCore — Milestone v1.3 Requirements

**Milestone:** v1.3 Agent Harness & Domain-Specific Workflows
**Started:** 2026-05-03
**Source PRD:** `docs/PRD-Agent-Harness.md`
**Phase numbering:** Continues from v1.2 last phase 16 → starts at Phase 17

**Status legend:** `[ ]` open · `[x]` validated · `→ Phase N` mapped via roadmap

---

## v1.3 Requirements

### Deep Mode Foundation (DEEP-*)

- [ ] **DEEP-01**: User can toggle "Deep Mode" per-message via a button next to Send (per-message, not per-thread)
- [ ] **DEEP-02**: System branches to extended agent loop when `deep_mode=true` — extended system prompt (planning/workspace/delegation/ask-user instructions), deep-mode tools loaded, `MAX_DEEP_ROUNDS=50` iteration cap
- [ ] **DEEP-03**: System leaves standard chat behavior unchanged when Deep Mode is OFF (zero token overhead, no extra tools, no extended prompt)
- [ ] **DEEP-04**: System persists `deep_mode` boolean per message record (`messages.deep_mode`) for UI history reconstruction
- [ ] **DEEP-05**: System keeps deep-mode system prompt KV-cache friendly (deterministic sections, no timestamps, todo state flows through tools not prompt)
- [ ] **DEEP-06**: System enforces loop-exhaustion fallback at `MAX_DEEP_ROUNDS` — forces agent to summarize and deliver
- [ ] **DEEP-07**: User can interrupt deep-mode execution at any time; all completed work persists

### Planning System / Todos (TODO-*)

- [ ] **TODO-01**: System persists per-thread todo list in `agent_todos` table (FK `thread_id`, content, status pending/in_progress/completed, position, RLS)
- [ ] **TODO-02**: Agent can call `write_todos` (full-replacement) and `read_todos` (returns current list) LLM tools
- [ ] **TODO-03**: System emits `todos_updated` SSE event on every `write_todos` / `read_todos` call
- [ ] **TODO-04**: System prompt instructs agent to call `read_todos` after each step (recitation pattern to prevent drift)
- [ ] **TODO-05**: Agent can adaptively replan — add, remove, rewrite tasks mid-execution
- [ ] **TODO-06**: User sees a Plan Panel sidebar with real-time todo status updates (pending / in-progress / completed visual differentiation)
- [ ] **TODO-07**: User sees last-known todo state when reloading a thread with deep-mode history

### Agent Workspace / Virtual Filesystem (WS-*)

- [ ] **WS-01**: System persists per-thread workspace files in `workspace_files` table (FK `thread_id`, `file_path`, `content` for text, `storage_path` for binary, `source` discriminator agent/sandbox/upload, unique `(thread_id, file_path)`, RLS)
- [ ] **WS-02**: Agent can call `write_file` (create/overwrite), `read_file`, `edit_file` (exact string replacement), `list_files` LLM tools
- [ ] **WS-03**: System validates workspace paths — relative only, forward slashes, no path traversal, no leading `/`, no backslash, max 500 chars, max 1MB text
- [ ] **WS-04**: System uses dual storage — text content in DB (<100ms reads), binary in Supabase Storage (with metadata in DB)
- [ ] **WS-05**: System auto-creates `workspace_files` entries with `source="sandbox"` for sandbox-generated files (fixes existing problem of disappearing sandbox download links)
- [ ] **WS-06**: Sub-agents share parent thread's workspace (read context, write results)
- [ ] **WS-07**: User sees Workspace Panel sidebar with file list, sizes, source indicators
- [ ] **WS-08**: User can click text file to view, click binary to download
- [ ] **WS-09**: System exposes REST endpoints `GET /threads/{id}/files` (list) and `GET /threads/{id}/files/{path}` (read/download)
- [ ] **WS-10**: System emits real-time SSE events on workspace mutations
- [ ] **WS-11**: Workspace Panel is decoupled from Deep Mode — visible whenever a thread has workspace files (allows harness engine to use workspace independently)

### Sub-Agent Delegation (TASK-*)

- [ ] **TASK-01**: Agent can call `task(description: str, context_files: list[str])` LLM tool to delegate work to a sub-agent with isolated context
- [ ] **TASK-02**: Sub-agent inherits parent tools minus `task` (no recursion) and minus `write_todos`/`read_todos`
- [ ] **TASK-03**: Sub-agent shares parent thread's workspace (read + write)
- [ ] **TASK-04**: Sub-agent's last assistant message text returns as the `task` tool result
- [ ] **TASK-05**: Sub-agent failures return as tool results (never crash parent loop) — failure isolation
- [ ] **TASK-06**: Existing `analyze_document` and `explore_knowledge_base` sub-agents remain unchanged (additive)
- [ ] **TASK-07**: Sub-agent emits start/complete SSE events for UI nesting

### Ask User Mid-Task (ASK-*)

- [ ] **ASK-01**: Agent can call `ask_user(question)` LLM tool to pause execution mid-loop
- [ ] **ASK-02**: System emits `ask_user` SSE event and sets `agent_status="waiting_for_user"`
- [ ] **ASK-03**: User's reply is delivered as the `ask_user` tool result (not as a new top-level message)
- [ ] **ASK-04**: Agent loop resumes after user response

### Agent Status & Error Handling (STATUS-*)

- [ ] **STATUS-01**: System surfaces agent status indicators — `working`, `waiting_for_user`, `complete`, `error`
- [ ] **STATUS-02**: Failed tool calls remain in conversation context (append-only) — LLM can learn and recover
- [ ] **STATUS-03**: System performs no automatic retries — agent decides retry / alternative / `ask_user` escalation
- [ ] **STATUS-04**: Sub-agent failures isolated — parent loop continues
- [ ] **STATUS-05**: All loop iteration state (messages + tool calls + todos + workspace) persisted to DB after each round (reconnection-safe)
- [ ] **STATUS-06**: User can resume a paused thread by sending a follow-up message — agent reads existing todos/workspace to continue

### Harness Engine Core (HARN-*)

- [ ] **HARN-01**: System persists harness execution state in `harness_runs` table (FK `thread_id`, `harness_type`, status pending/running/paused/completed/failed, `current_phase` index, `phase_results` JSONB, `input_file_ids`, RLS, unique active run per thread)
- [ ] **HARN-02**: Harness engine dispatches phases by `PhaseType` enum: `programmatic`, `llm_single`, `llm_agent`, `llm_batch_agents`, `llm_human_input`
- [ ] **HARN-03**: Phases pass context via workspace files (no inline `$prior_results` dumps); orchestrator passes file paths only
- [ ] **HARN-04**: Orchestrator stays thin (~5k tokens) regardless of contract size — context offloaded to workspace
- [ ] **HARN-05**: `llm_single` phases enforce structured output via OpenAI/OpenRouter `response_format: { type: "json_schema" }` + Pydantic validation before advancing
- [ ] **HARN-06**: Each phase enforces a configurable timeout (120s `llm_single`, 300s `llm_agent` defaults) — timeout = phase failure
- [ ] **HARN-07**: Engine checks cancellation event between rounds/phases; clean shutdown on client disconnect
- [ ] **HARN-08**: Engine supports a dict-based harness registry — adding a new harness = adding a file to `harnesses/` and registering it
- [ ] **HARN-09**: Engine emits SSE events: `harness_phase_start`, `harness_phase_complete`, `harness_phase_error`, `harness_complete`, `harness_batch_start`, `harness_batch_complete`, `harness_sub_agent_start`, `harness_sub_agent_complete`, `harness_human_input_required`
- [ ] **HARN-10**: Each phase definition is a typed dataclass with: name, description, phase_type, system_prompt_template (5-15 lines), tools list (curated), output_schema (Pydantic), validator (optional), workspace_inputs, workspace_output, batch_size, post_execute (optional async callback)

### Gatekeeper LLM (GATE-*)

- [ ] **GATE-01**: System runs a stateless conversational gatekeeper before each user message when no active/completed harness run exists
- [ ] **GATE-02**: Gatekeeper uses `[TRIGGER_HARNESS]` sentinel — strips before display, harness begins in same SSE stream
- [ ] **GATE-03**: Gatekeeper supports multi-turn dialogue (e.g., "Please upload your contract first")
- [ ] **GATE-04**: Each harness defines `HarnessPrerequisites` dataclass (`requires_upload`, `upload_description`, `harness_intro`)
- [ ] **GATE-05**: Harnesses without prerequisites skip the gatekeeper entirely

### Post-Harness Response (POST-*)

- [ ] **POST-01**: After harness completion, system loads phase results into a separate LLM call's system prompt (not as fabricated user message)
- [ ] **POST-02**: LLM streams a concise (~500 token) summary referencing the workspace report
- [ ] **POST-03**: Summary persisted as a separate assistant message
- [ ] **POST-04**: Follow-up messages route through normal LLM loop with phase results available in context
- [ ] **POST-05**: System truncates phase results when total exceeds 30,000 chars (last 2 phases kept in full)

### Human-in-the-Loop Context Gathering (HIL-*)

- [ ] **HIL-01**: `llm_human_input` phase generates an informed question using prior phase results
- [ ] **HIL-02**: Question streams as a normal chat message (not in phase panel)
- [ ] **HIL-03**: Harness sets status to `paused` while awaiting response
- [ ] **HIL-04**: User response captured → written to workspace file → phase marked complete → harness resumes

### Batched Parallel Sub-Agents (BATCH-*)

- [ ] **BATCH-01**: Engine parses items from workspace input file (e.g., `clauses.md` JSON array)
- [ ] **BATCH-02**: Engine chunks items into batches of `batch_size` (default 5)
- [ ] **BATCH-03**: Each batch runs concurrently via `asyncio.gather()` reusing `run_task_agent()` pattern
- [ ] **BATCH-04**: Sub-agent events stream in real-time via `asyncio.Queue` pattern (not delayed until batch completes)
- [ ] **BATCH-05**: Results accumulated into workspace output file per batch
- [ ] **BATCH-06**: Each sub-agent reads only what it needs from workspace (playbook context, review context)
- [ ] **BATCH-07**: Engine resumes mid-batch — detects partial workspace output (e.g., 10 of 15 assessments), computes remaining, resumes from where left off

### File Upload (UPL-*)

- [ ] **UPL-01**: User can upload DOCX and PDF files via `POST /threads/{thread_id}/files/upload`
- [ ] **UPL-02**: Binary file uploaded to Supabase Storage, metadata stored in `workspace_files` with `source='upload'`
- [ ] **UPL-03**: System extracts text via `python-docx` (DOCX) and `PyPDF2` (PDF) for harness consumption
- [ ] **UPL-04**: User sees a file upload button in chat input when a harness mode is active

### Plan Panel Harness Integration (PANEL-*)

- [ ] **PANEL-01**: Harness engine writes phases to `agent_todos` with content prefix (e.g., `[Contract Review] Clause Extraction`)
- [ ] **PANEL-02**: Plan Panel shows harness phases progressing pending → in_progress → completed
- [ ] **PANEL-03**: System strips `write_todos` / `read_todos` tools from harness phase LLM calls (LLM cannot modify plan)
- [ ] **PANEL-04**: Plan Panel header shows lock icon for harness runs (communicates immutability)

### Contract Review Harness — First Domain Implementation (CR-*)

- [ ] **CR-01**: Phase 1 — Document Intake (`programmatic`): reads uploaded file, extracts text via `python-docx` (DOCX) or `PyPDF2` (PDF), writes `contract-text.md`
- [ ] **CR-02**: Phase 2 — Contract Classification (`llm_single`): classifies type / parties / effective+expiration dates / governing law / jurisdiction; Pydantic schema enforces ≥2 parties, non-empty type; writes `classification.md`
- [ ] **CR-03**: Phase 3 — Gather Context (`llm_human_input`): generates informed questions from classification (Which side? Deadline pressure? Focus areas? Deal context?); writes `review-context.md`
- [ ] **CR-04**: Phase 4 — Load Playbook (`llm_agent` with RAG tools, max 10 rounds): uses `search_documents` + `analyze_document` to discover playbook materials; writes `playbook-context.md` with doc IDs, titles, summaries, clause-category mappings
- [ ] **CR-05**: Phase 5 — Clause Extraction (`programmatic` with internal LLM): extracts every distinct clause; for >50k-token contracts splits into overlapping chunks, runs LLM per chunk, merges + dedupes; writes `clauses.md` (JSON array, 13 categories: Liability, Indemnification, IP, Data Protection, Confidentiality, Warranties, Term/Termination, Governing Law, Insurance, Assignment, Force Majeure, Payment, Other)
- [ ] **CR-06**: Phase 6 — Risk Analysis (`llm_batch_agents`, batch_size=5): isolated sub-agent per clause; assesses GREEN/YELLOW/RED against playbook; provides rationale + alternative language; agents have RAG tools for deep-reading; results into `risk-analysis.md`; user sees real-time "Analyzing clause N/M" with nested tool calls
- [ ] **CR-07**: Phase 7 — Redline Generation (`llm_batch_agents`, batch_size=5): processes only YELLOW/RED; each agent generates precise redline (original / proposed replacement / rationale / fallback positions); writes `redlines.md`
- [ ] **CR-08**: Phase 8 — Executive Summary (`llm_single` + `post_execute`): reads all artifacts, generates summary (overall risk, recommendation, key findings, risk breakdown); writes `contract-review-report.md`

### DOCX Report Generation (DOCX-*)

- [ ] **DOCX-01**: Phase 8 `post_execute` callback runs Python script in sandbox to generate `.docx` via `python-docx`
- [ ] **DOCX-02**: DOCX includes title page (CONFIDENTIAL marker, contract type, risk rating badge, prepared-for party)
- [ ] **DOCX-03**: DOCX executive summary section (overall risk, recommendation, RED/YELLOW/GREEN counts)
- [ ] **DOCX-04**: DOCX numbered key findings list
- [ ] **DOCX-05**: DOCX detailed redline table (color-coded clause risk, original text, proposed text, rationale)
- [ ] **DOCX-06**: DOCX acceptable-clauses section (GREEN clauses, "no changes recommended")
- [ ] **DOCX-07**: DOCX recommended-next-steps section
- [ ] **DOCX-08**: DOCX generation is non-fatal — if sandbox unavailable, LLM markdown summary still saved

### Migrations & Data Model (MIG-*)

- [ ] **MIG-01**: Migration adds `agent_todos` table with RLS (thread-ownership scope)
- [ ] **MIG-02**: Migration adds `workspace_files` table with RLS, unique `(thread_id, file_path)` constraint
- [ ] **MIG-03**: Migration adds `harness_runs` table with RLS, unique active run per thread
- [ ] **MIG-04**: Migration adds `messages.deep_mode` boolean and `messages.harness_mode` text columns

### Security & Privacy (SEC-*)

- [ ] **SEC-01**: All new tables (`agent_todos`, `workspace_files`, `harness_runs`) enforce RLS — users only see their own threads' data
- [ ] **SEC-02**: Sub-agents operate within parent user's auth context (no privilege escalation)
- [ ] **SEC-03**: Model provider API keys remain server-side only (no exposure to sandbox or sub-agents)
- [ ] **SEC-04**: All new agent paths route LLM payloads through existing PII redaction egress filter — privacy invariant preserved (no real PII to cloud LLM)

### Observability (OBS-*)

- [ ] **OBS-01**: Harness engine writes single-writer `progress.md` workspace file after each phase transition (status + intermediate detail — classification summary, clause count, risk tally, redline count)
- [ ] **OBS-02**: All harness operations include `thread_id` correlation logging (consistent with existing v1.0 redaction logging)
- [ ] **OBS-03**: Existing LangSmith tracing covers new agent loop and harness phases (no instrumentation gaps)

### Configuration (CONF-*)

- [ ] **CONF-01**: `MAX_DEEP_ROUNDS` env var (default 50) controls deep-mode loop iteration limit
- [ ] **CONF-02**: `MAX_TOOL_ROUNDS` env var (default 25) preserved for standard mode
- [ ] **CONF-03**: `MAX_SUB_AGENT_ROUNDS` env var (default 15) controls sub-agent rounds

---

## Future Requirements (Deferred)

These are explicit Post-MVP items from the PRD — captured here for visibility, not in scope for v1.3.

- Context auto-compaction / summarization for very-long sessions
- Human-in-the-loop tool approval for sensitive operations (privileged actions)
- Agent memory across sessions (persistent per-user instructions)
- Background / async agent runs (loop continues server-side after disconnect)
- Stall detection and auto-replan
- Full SSE reconnection with automatic loop resumption mid-flight
- Additional domain harnesses: NDA generator, vendor assessment, compliance check
- Cross-process async-lock upgrade (D-31, carried from v1.0)
- PERF-02: 500ms anonymization confirmation on Railway server hardware (carried from v1.0)
- Multi-worker IPython sandbox session semantics (carried from v1.1)

---

## Out of Scope (Explicit Exclusions)

- **LangChain / LangGraph for agent orchestration** — Raw SDK calls only. Reason: same rationale as v1.0–v1.2 (debugging clarity, deterministic flow). Harness engine is a hand-coded state machine, not a graph framework wrapper.
- **Frontend agent loop / streaming-side state machine** — All loop control lives in backend. Reason: KV-cache friendliness, single source of truth, security boundary.
- **Browser-side workspace file storage** — All workspace files persist in DB / Supabase Storage. Reason: cross-device thread continuity, RLS enforcement, audit traceability.
- **Tool approval prompts inside the loop** — No human-in-the-loop tool gating in v1.3 (deferred to post-MVP). Reason: agent autonomy is the v1.3 goal; selective tool approval would re-fragment the UX.
- **Recursive sub-agent delegation** — `task` tool removed from sub-agent context. Reason: prevent runaway recursion; one-level fan-out preserves predictable behavior.
- **Sub-agents calling `write_todos`/`read_todos`** — Reason: only the parent owns the plan; sub-agents work on focused sub-tasks.
- **Auto-retry on tool/phase failures** — LLM-driven recovery only. Reason: behavior under failure becomes hard to debug with implicit retries; explicit recovery via context is more transparent.
- **Mid-stream cancellation of `llm_human_input` phase** — Cancellation only between rounds/phases. Reason: simpler invariant; user already has "stop" via interrupt.
- **Per-user harness customization** — Harness definitions are global / system-defined. Reason: legal-AI quality requires consistent enforcement; per-user variants undermine the deterministic-flow guarantee.
- **Non-Indonesian-jurisdiction Contract Review playbook** — CR phases consume the user's existing playbook docs (whatever jurisdiction). Reason: jurisdiction handled via knowledge base content, not harness code.

---

## Traceability

*Filled in by the roadmapper 2026-05-03 from `.planning/ROADMAP.md`. 111/111 v1.3 requirements mapped, no orphans, no duplicates.*

### Per-phase summary

| Phase | Phase Name | Requirements Mapped | Count |
|-------|------------|---------------------|-------|
| 17 | Deep Mode Foundation + Planning Todos + Plan Panel | DEEP-01..07, TODO-01..07, MIG-01, MIG-04, SEC-01, CONF-01..03 | 20 |
| 18 | Workspace Virtual Filesystem | WS-01..11, MIG-02 | 12 |
| 19 | Sub-Agent Delegation + Ask User + Status & Recovery | TASK-01..07, ASK-01..04, STATUS-01..06 | 17 |
| 20 | Harness Engine Core + Gatekeeper + Post + Upload + Locked Panel | HARN-01..10, MIG-03, GATE-01..05, POST-01..05, PANEL-01..04, UPL-01..04, SEC-02..04, OBS-01..03 | 35 |
| 21 | Batched Parallel Sub-Agents + Human-in-the-Loop | BATCH-01..07, HIL-01..04 | 11 |
| 22 | Contract Review Harness + DOCX Deliverable | CR-01..08, DOCX-01..08 | 16 |
| **Total** | | | **111** |

### Per-requirement detail

| REQ-ID | Phase |
|--------|-------|
| DEEP-01 | 17 |
| DEEP-02 | 17 |
| DEEP-03 | 17 |
| DEEP-04 | 17 |
| DEEP-05 | 17 |
| DEEP-06 | 17 |
| DEEP-07 | 17 |
| TODO-01 | 17 |
| TODO-02 | 17 |
| TODO-03 | 17 |
| TODO-04 | 17 |
| TODO-05 | 17 |
| TODO-06 | 17 |
| TODO-07 | 17 |
| WS-01 | 18 |
| WS-02 | 18 |
| WS-03 | 18 |
| WS-04 | 18 |
| WS-05 | 18 |
| WS-06 | 18 |
| WS-07 | 18 |
| WS-08 | 18 |
| WS-09 | 18 |
| WS-10 | 18 |
| WS-11 | 18 |
| TASK-01 | 19 |
| TASK-02 | 19 |
| TASK-03 | 19 |
| TASK-04 | 19 |
| TASK-05 | 19 |
| TASK-06 | 19 |
| TASK-07 | 19 |
| ASK-01 | 19 |
| ASK-02 | 19 |
| ASK-03 | 19 |
| ASK-04 | 19 |
| STATUS-01 | 19 |
| STATUS-02 | 19 |
| STATUS-03 | 19 |
| STATUS-04 | 19 |
| STATUS-05 | 19 |
| STATUS-06 | 19 |
| HARN-01 | 20 |
| HARN-02 | 20 |
| HARN-03 | 20 |
| HARN-04 | 20 |
| HARN-05 | 20 |
| HARN-06 | 20 |
| HARN-07 | 20 |
| HARN-08 | 20 |
| HARN-09 | 20 |
| HARN-10 | 20 |
| GATE-01 | 20 |
| GATE-02 | 20 |
| GATE-03 | 20 |
| GATE-04 | 20 |
| GATE-05 | 20 |
| POST-01 | 20 |
| POST-02 | 20 |
| POST-03 | 20 |
| POST-04 | 20 |
| POST-05 | 20 |
| HIL-01 | 21 |
| HIL-02 | 21 |
| HIL-03 | 21 |
| HIL-04 | 21 |
| BATCH-01 | 21 |
| BATCH-02 | 21 |
| BATCH-03 | 21 |
| BATCH-04 | 21 |
| BATCH-05 | 21 |
| BATCH-06 | 21 |
| BATCH-07 | 21 |
| UPL-01 | 20 |
| UPL-02 | 20 |
| UPL-03 | 20 |
| UPL-04 | 20 |
| PANEL-01 | 20 |
| PANEL-02 | 20 |
| PANEL-03 | 20 |
| PANEL-04 | 20 |
| CR-01 | 22 |
| CR-02 | 22 |
| CR-03 | 22 |
| CR-04 | 22 |
| CR-05 | 22 |
| CR-06 | 22 |
| CR-07 | 22 |
| CR-08 | 22 |
| DOCX-01 | 22 |
| DOCX-02 | 22 |
| DOCX-03 | 22 |
| DOCX-04 | 22 |
| DOCX-05 | 22 |
| DOCX-06 | 22 |
| DOCX-07 | 22 |
| DOCX-08 | 22 |
| MIG-01 | 17 |
| MIG-02 | 18 |
| MIG-03 | 20 |
| MIG-04 | 17 |
| SEC-01 | 17 |
| SEC-02 | 20 |
| SEC-03 | 20 |
| SEC-04 | 20 |
| OBS-01 | 20 |
| OBS-02 | 20 |
| OBS-03 | 20 |
| CONF-01 | 17 |
| CONF-02 | 17 |
| CONF-03 | 17 |

---

*Initialized 2026-05-03 from `docs/PRD-Agent-Harness.md` via `/gsd-new-milestone`.*
*Traceability filled 2026-05-03 by gsd-roadmapper — 111/111 coverage, 6 phases (17–22).*
