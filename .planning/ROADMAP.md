# Roadmap: LexCore

**Created:** 2026-04-25
**Project:** LexCore — PJAA CLM Platform
**Core Value:** Indonesian legal teams can manage the full contract lifecycle with confidence that AI outputs are accurate, citable, and traceable.

## Milestones

- ✅ **v1.0 PII Redaction System** — Phases 1–6 (shipped 2026-04-29)
- 📋 **v1.1 Agent Skills & Code Execution** — Phases 7–11 (in progress, started 2026-04-29)

## Phases

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

### 📋 v1.1 Agent Skills & Code Execution — In Progress

**Goal:** Transform LexCore's chat into a customizable AI agent platform with reusable skills, sandboxed code execution, and persistent tool memory.

**27 requirements** · **5 phases** (7–11) · Started 2026-04-29

| # | Phase | Goal | Requirements | Success Criteria |
|---|-------|------|--------------|-----------------|
| 7 | Skills Database & API Foundation | Establish skills data model, RLS, and REST API | SKILL-01, 03–06, 10, EXPORT-01–03 | Skills CRUD + share + export/import via API; seed skill-creator |
| 8 | LLM Tool Integration & Discovery | Wire skills into LLM pipeline with catalog injection and tools | SKILL-02, 07–09, SFILE-01–03, 05 | Skills in system prompt; load_skill/save_skill/read_skill_file tools working |
| 9 | Skills Frontend | Skills page with full CRUD UI, file manager, navigation tab | SKILL-11, SFILE-04 | Skills tab in nav; create/edit/delete via UI; file preview panel |
| 10 | Code Execution Sandbox Backend | 6/6 | Complete    | 2026-05-01 |
| 11 | Code Execution UI & Persistent Tool Memory | Surface sandbox in chat UI and persist tool results across turns | SANDBOX-07, MEM-01–03 | Code panel streams live; LLM references prior tool results without re-execution |

---

#### Phase 7: Skills Database & API Foundation

**Goal:** Establish the skills data model, Supabase RLS policies, storage bucket, and complete REST API so all subsequent phases have a stable backend to build on.

**Requirements:** SKILL-01, SKILL-03, SKILL-04, SKILL-05, SKILL-06, SKILL-10, EXPORT-01, EXPORT-02, EXPORT-03

**Success criteria:**
1. User can create, read, update, and delete their own skills via `POST/GET/PATCH/DELETE /skills`
2. Global skills (`user_id=NULL`) are returned by `GET /skills` for all authenticated users
3. User can toggle a skill global/private via `PATCH /skills/{id}/share`
4. `skill-creator` global seed skill exists in the database post-migration
5. User can export a skill as a valid `.zip` via `GET /skills/{id}/export` and import via `POST /skills/import`

---

#### Phase 8: LLM Tool Integration & Discovery

**Goal:** Wire skills into the LLM pipeline — inject the skill catalog into the system prompt, implement `load_skill`, `save_skill`, and `read_skill_file` tools, and enable skill file uploads.

**Requirements:** SKILL-02, SKILL-07, SKILL-08, SKILL-09, SFILE-01, SFILE-02, SFILE-03, SFILE-05

**Success criteria:**
1. Enabled skills appear as a name/description table in the LLM system prompt on every chat request
2. LLM can call `load_skill` and receive full instructions + attached file table in response
3. LLM can call `save_skill` and the skill is persisted to the database
4. LLM can call `read_skill_file` and receive text file content inline
5. File uploads/deletes work via backend API (`POST /skills/{id}/files`, `DELETE /skills/{id}/files/{file_id}`)

**Plans:** 4 plans

Plans:
- [x] 08-01-PLAN.md — tool_service.py: 3 new TOOL_DEFINITIONS (load_skill, save_skill, read_skill_file) + token kwarg plumbing + 3 handler implementations + unit tests
- [x] 08-02-PLAN.md — skill_catalog_service.py: build_skill_catalog_block(user_id, token) RLS-scoped catalog formatter + unit tests
- [x] 08-03-PLAN.md — skills.py: 3 new file endpoints (POST /files, DELETE /files/{id}, GET /files/{id}/content) + 10MB middleware extension + integration tests
- [x] 08-04-PLAN.md — chat.py: catalog injection at both single-agent + multi-agent prompt sites + token forwarding to execute_tool + integration tests

---

#### Phase 9: Skills Frontend

**Goal:** Build the complete Skills page — navigation tab, skill list with search/badges, skill editor with form fields and building-block files section, and file preview panel.

**Requirements:** SKILL-11, SFILE-04

**Success criteria:**
1. "Skills" tab appears in top navigation alongside Chat and Documents
2. User can create, edit, and delete skills via the UI form without page reload
3. Skill editor shows attached files with upload button (own skills) and delete per file
4. Clicking a text file opens a slide-in preview panel with copy and download buttons
5. "Try in Chat" button navigates to chat with a pre-populated message triggering the skill

---

#### Phase 10: Code Execution Sandbox Backend

**Goal:** Implement the Docker-based Python sandbox with IPython session persistence, real-time SSE streaming, file output via Supabase Storage, and the `SANDBOX_ENABLED` feature flag.

**Requirements:** SANDBOX-01, SANDBOX-02, SANDBOX-03, SANDBOX-04, SANDBOX-05, SANDBOX-06, SANDBOX-08

**Success criteria:**
1. `execute_code` tool executes Python in a Docker container and returns stdout/stderr
2. Variables persist across `run()` calls within a thread session (TTL 30min, auto-cleanup every 60s)
3. `code_stdout`/`code_stderr` SSE events stream to the frontend line-by-line during execution
4. Files written to `/sandbox/output/` are uploaded to Supabase Storage and returned as signed URLs
5. `execute_code` tool is absent from system prompt when `SANDBOX_ENABLED=false`
6. All executions logged to `code_executions` table with exit code, timing, and status


**Plans:** 6/6 plans complete

Plans:
- [x] 10-01-PLAN.md — Migration 036 (code_executions table + sandbox-outputs bucket + RLS) + llm-sandbox dependency + supabase db push
- [x] 10-02-PLAN.md — SandboxDockerfile (lexcore-sandbox:latest) + 4 sandbox_* settings in config.py
- [x] 10-03-PLAN.md — sandbox_service.py (llm-sandbox wrapper, session-per-thread, TTL cleanup, file upload)
- [x] 10-04-PLAN.md — tool_service.py: register execute_code, gate on SANDBOX_ENABLED, _execute_code handler + audit + DB persist
- [x] 10-05-PLAN.md — chat.py: queue-adapter SSE streaming for code_stdout/code_stderr (with PII anonymization)
- [x] 10-06-PLAN.md — code_execution.py router: GET /code-executions list endpoint with signed URL refresh

---

#### Phase 11: Code Execution UI & Persistent Tool Memory

**Goal:** Surface sandbox results in the chat UI with a streaming Code Execution Panel, and persist tool call results across conversation turns so the LLM can reference prior data.

**Requirements:** SANDBOX-07, MEM-01, MEM-02, MEM-03

**Success criteria:**
1. Code Execution Panel renders inline in chat with streaming stdout/stderr during execution
2. Generated files appear as download cards with filename, size, and download link
3. Tool call results are stored in `messages.tool_calls` JSONB after each execution
4. Loading conversation history reconstructs tool-call → result → assistant text message sequence
5. LLM can answer follow-up questions using data from earlier tool calls without re-executing

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

## Phase Numbering

- **Integer phases (1, 2, 3, …):** Planned milestone work. Numbering resets at each new milestone.
- **Decimal phases (e.g. 2.1):** Urgent insertions created via `/gsd-insert-phase`.

---
*Roadmap created: 2026-04-25*
*v1.0 milestone archived: 2026-04-29 — see `.planning/milestones/v1.0-ROADMAP.md` for full phase details*
