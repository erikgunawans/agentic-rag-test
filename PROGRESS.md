# Progress

PJAA CLM Platform (LexCore) — **Milestone v1.1 "Agent Skills & Code Execution" COMPLETE 2026-05-02 (5/5 phases, 26/26 plans).** Phase 11 (Code Execution UI & Persistent Tool Memory) UAT APPROVED + verified PASS-WITH-CAVEATS at HEAD `0170739`. 35 migrations, 23 routers, 20 services. ~314 unit tests pass. Ready to ship to production (`/deploy-lexcore` — remember to flip `SANDBOX_ENABLED=true` and publish `lexcore-sandbox:latest` or the panel never renders) and to run `/gsd-complete-milestone` for archival. v0.4.0.0 still the shipped version (next ship will bump). Fix B (PII deny list) remains queued.

## Checkpoint 2026-05-02b (Phase 11 + Milestone v1.1 COMPLETE — UAT approved, verified)

- **Session:** Drove the 12-step Plan 11-07 Task 4 UAT in a live local browser; user replied `approved`. Spawned `gsd-verifier` for goal-backward verification — verdict PASS-WITH-CAVEATS (4/4 requirements satisfied, 5/5 ROADMAP success criteria, 28/28 spot-checks). Marked Phase 11 + Milestone v1.1 complete in STATE.md, ROADMAP.md, and wrote phase-level `SUMMARY.md`.
- **Branch:** master (`0170739` for code; closeout commit pending)
- **Done:**
  - **UAT approved 2026-05-02** — all 12 steps walked end-to-end at `http://localhost:5174/` (port 5174 because 5173 was occupied) against backend `:8000`. Steps 1-6 confirmed streaming + completion render; step 7 confirmed page-refresh persistence (MEM-01); steps 8-9 confirmed follow-up Fibonacci answer from memory with no `code_stdout`/`code_stderr` SSE events on the new turn (MEM-02/03 via DevTools Network); steps 10-12 confirmed legacy compat + multi-call gap-6 stacking + error path.
  - **`gsd-verifier` ran goal-backward** — wrote `.planning/phases/11-code-execution-ui-persistent-tool-memory/VERIFICATION.md`. Verdict: PASS-WITH-CAVEATS. Walked SANDBOX-07 → CodeExecutionPanel.tsx:214-302 + ToolCallCard.tsx:130-186 + useChatState.ts:211-233 + translations.ts:666-682, 1346-1362; MEM-01 → tools.py:13-60 + chat.py:530, 544, 1071, 1084 (silent multi-agent success-path bug fixed at chat.py:1067-1073); MEM-02 → chat.py:97-146 (`_expand_history_row`); MEM-03 → UAT step 9 evidence. 6 risks flagged as operational, not technical (Railway sandbox readiness, multi-worker IPython sessions, signed-URL UX, PII redaction batch alignment, missing CodeExecutionPanel tests, legacy fallback corpus).
  - **Plan 11-07 SUMMARY re-committed** — Task 4 status `AWAITING UAT` → `APPROVED 2026-05-02`.
  - **Phase-level `SUMMARY.md` written** — `.planning/phases/11-code-execution-ui-persistent-tool-memory/SUMMARY.md` consolidates the 7 plans, requirements → code citations, decisions D-P11-01..D-P11-11, the silent-bug story, anti-grep guards, UAT outcome, risks, and milestone closeout call-to-action.
  - **STATE.md** — `state.complete-phase` SDK call ran: status `executing → completed`; `completed_phases: 4 → 5`; `completed_plans: 19 → 26`; `percent: 73 → 100`. "Current focus" updated to "Milestone v1.1 — ALL 5 PHASES COMPLETE". Current Position rewritten with UAT approval marker.
  - **ROADMAP.md** — Phase 11 row marked `✅ COMPLETED 2026-05-02` with 5/5 success criteria checkmarked; all 7 plan checkboxes flipped `[ ] → [x]`.
- **Files changed (closeout):** `.planning/STATE.md`, `.planning/ROADMAP.md`, `.planning/phases/11-code-execution-ui-persistent-tool-memory/11-07-SUMMARY.md`, `.planning/phases/11-code-execution-ui-persistent-tool-memory/SUMMARY.md` (new), `.planning/phases/11-code-execution-ui-persistent-tool-memory/VERIFICATION.md` (new), `PROGRESS.md`, `~/.claude/projects/.../memory/project_state.md`, `~/.claude/projects/.../memory/MEMORY.md`
- **Tests (final):** ~314 unit tests pass; backend `from app.main import app` imports cleanly; frontend `tsc --noEmit` clean across full type chain `SSEEvent → useChatState → MessageView → ToolCallList → CodeExecutionPanel`.
- **Risks parked for the deploy / next milestone:**
  - **Production sandbox readiness** — flip `SANDBOX_ENABLED=true` in Railway env + publish `lexcore-sandbox:latest` image + verify Docker daemon reachable, or the panel will never render in prod.
  - **Multi-worker IPython sessions** don't survive Railway replica scaling (pre-existing Phase 10 concern).
  - **No frontend component tests for CodeExecutionPanel** — 360-line component leans on UAT + tsc; `CodeExecutionPanel.test.tsx` would be a sensible follow-up.
  - **Signed-URL download UX** — generic 2-second toast on failure; no 404 vs 500 vs network distinction.
- **Next:** Pick one path:
  1. **Ship v1.1 to production** — `/deploy-lexcore` runs the full pipeline (Vercel from `main`, Railway via `railway up`). Bump VERSION before tag.
  2. **Archive milestone v1.1 first** — `/gsd-complete-milestone` moves ROADMAP/REQUIREMENTS to `.planning/milestones/v1.1-*` and resets workspace for the next milestone.
  3. **Plan v1.2** — start with `/gsd-new-milestone` once the user has the next milestone's scope locked.

## Checkpoint 2026-05-02 (Phase 11 — all 7 plans executed; human UAT pending)

- **Session:** Drove `/gsd-execute-phase 11` end-to-end through all 4 waves; 7 plans coded, tested, merged onto master. Stopped at the blocking human-UAT checkpoint (Plan 11-07 Task 4) and started dev servers for the user to drive the 12-step verification.
- **Branch:** master (`0170739` — Merge Plan 11-07 Tasks 1-3)
- **Done — Wave 1 (parallel, 3 plans):**
  - **11-01** (`9c440ac`, `679aa4f`, `fa89cd2`, merge `e2086fb`) — `ToolCallRecord` extended with `tool_call_id`, `status`, and a Pydantic `field_validator("output", mode="before")` that head-truncates serialized output to 50,000 bytes with the literal `… [truncated, N bytes]` marker (D-P11-04, D-P11-11). 11/11 unit tests added in `backend/tests/models/test_tool_call_record.py`.
  - **11-02** (`d03c38b`, `1e770e4`, auto-merged) — `frontend/src/lib/database.types.ts` widened with `CodeStdoutEvent` / `CodeStderrEvent` SSE-event interfaces (Phase 10's wire shape) + `tool_call_id?` and `status?` fields on `ToolCallRecord`.
  - **11-03** (`27363d1`, `0bb97ce`, `492ec82`, merge `6668fe8`) — New `GET /code-executions/{execution_id}` endpoint in `backend/app/routers/code_execution.py` for signed-URL refresh per D-P11-06. Reuses `_refresh_signed_urls` and `get_supabase_authed_client`. Cross-user isolation via RLS → 404 (no info leak). 4 integration tests added.
- **Done — Wave 2 (parallel, 2 plans):**
  - **11-04** (`3c20de5`, `6944c9f`, `1c396db`, merge `6b32c96`) — Three coordinated splices in `backend/app/routers/chat.py`: (A) history-load reconstructs `ToolCallRecord` from `msg.tool_calls.calls[]` JSON, (B) **silent-bug fix** — multi-agent success path was never persisting `ToolCallRecord` (only the exception path appended); MEM-01 gap closed, (C) single-agent path populates `tool_call_id=tc["id"]` and `status` per D-P11-08. 13 new unit tests in `test_chat_history_reconstruction.py`. Phase-10 sandbox-streaming regression (8/8) green.
  - **11-05** (`62efb5a`, `c2f9855`, merge `a4ec460`) — `useChatState` hook gains `sandboxStreams: Map<tool_call_id, {stdout[], stderr[]}>` plus SSE handlers for `code_stdout` / `code_stderr`. Map cleared at 3 lifecycle sites (thread switch, send, post-stream finally) so stale entries don't leak across turns.
- **Done — Wave 3 (1 plan):**
  - **11-06** (`bbac641`, `5bab150`, `b6f14c5`, auto-merged) — New `frontend/src/components/chat/CodeExecutionPanel.tsx` (359 lines) per UI-SPEC §Component Inventory: code preview toggle, status pill, live execution timer, dark terminal block (green stdout / red stderr), file-download cards (refreshes signed URLs via the 11-03 endpoint). 17 `sandbox.*` i18n keys × 2 locales (`id` + `en`) added to `translations.ts`. Anti-grep `! grep -q "backdrop-blur"` passes (panel is persistent in-message — glass would violate design system).
- **Done — Wave 4 (1 plan, code only — UAT blocking):**
  - **11-07 Tasks 1-3** (`64b17da`, `8f1f715`, `76e3cce`, merge `0170739`) — `ToolCallList` becomes a router: execute_code calls *with* `tool_call_id` route to `CodeExecutionPanel` in a `flex flex-col gap-6 mb-2` panel section; everything else (incl. legacy execute_code without `tool_call_id`) renders via the existing `ToolCallCard` with the new `TOOL_CONFIG.execute_code = {icon: Terminal, label: 'Code Execution'}`. `MessageView` plumbs `sandboxStreams` from `useChatState` (via `ChatPage` prop drill — out-of-plan file added per Rule-2 deviation, documented in 11-07-SUMMARY). Sub-change B chosen: **unconditional pass-through** (no `streamingMessageId` flag exists in MessageView; UUID keys + 3-site Map reset make stale entries safe). Anti-grep gates pass: `out.execution_id` present, `out.id` fallback NOT reintroduced. 32/32 backend regression tests still green.
- **Stopped at:** Plan 11-07 Task 4 — `<task type="checkpoint:human-verify" gate="blocking">`. Backend `uvicorn :8000` and frontend `vite :5174` (5173 was occupied) are running; backend `/health = ok`. 12-step UAT script presented to user — covers: streaming render (steps 1-3), completion render (4-6), persistence on refresh (7), follow-up memory reference without re-execution (8-9), legacy compatibility (10), multi-call gap-6 stacking (11), error path (12).
- **Files changed (cumulative across all 7 plans):**
  - `backend/app/models/tools.py`, `backend/app/routers/chat.py`, `backend/app/routers/code_execution.py`
  - `backend/tests/models/test_tool_call_record.py` (new), `backend/tests/api/test_code_executions_get_by_id.py` (new), `backend/tests/routers/test_chat_history_reconstruction.py` (new), `backend/tests/models/__init__.py` (new)
  - `frontend/src/lib/database.types.ts`, `frontend/src/hooks/useChatState.ts`, `frontend/src/i18n/translations.ts`, `frontend/src/components/chat/MessageView.tsx`, `frontend/src/components/chat/ToolCallCard.tsx`, `frontend/src/pages/ChatPage.tsx`
  - `frontend/src/components/chat/CodeExecutionPanel.tsx` (new, 359 lines)
  - 7 SUMMARY.md files in `.planning/phases/11-code-execution-ui-persistent-tool-memory/`
- **Tests:** ~314 total (28 new this session) — all green pre-UAT. Phase 10 + Phase 1 regression suites unchanged (8/8 sandbox streaming, prior tool-call record tests all still pass). Frontend `tsc --noEmit` clean across the type chain `SSEEvent → useChatState → MessageView → ToolCallList → CodeExecutionPanel`.
- **Deviations recorded across SUMMARYs (all Rule-3 environmental, not design):**
  - Worktrees frequently branched from stale base — fixed via `git reset --hard master` or `git rebase master` per agent
  - Worktrees miss `.env` — agents sourced `backend/.env` from main repo at test-invocation time (precedent set by 11-01)
  - 11-07 added `ChatPage.tsx` to satisfy the prop-drill pattern (Rule-2 missing-wiring)
  - Single Rule-3 cosmetic comment edit on `CodeExecutionPanel.tsx` to satisfy a literal `! grep -q "backdrop-blur"` gate
- **Next:** Drive the 12-step UAT in the running browser (frontend `:5174`, backend `:8000`, login `test@test.com`). When the user replies `approved`: re-commit Plan 11-07 SUMMARY with the UAT outcome, run `gsd-verifier` for goal-backward verification of SANDBOX-07 + MEM-01..03, mark Phase 11 complete in `STATE.md` (`gsd-sdk query state.complete-phase`), and write the phase-level SUMMARY. After that, milestone v1.1 (Agent Skills & Code Execution) is done and ready to ship — Vercel deploys from `main`, Railway needs `railway up`.

## Checkpoint 2026-05-01 (Phase 08 UAT complete + Phase 07 export bug fixed)

- **Session:** Cross-phase UAT audit, one code bug fixed, Phase 08 all 4 live UAT items verified.
- **Branch:** master (`faa5403`)
- **Done:**
  - **UAT audit:** Ran `/gsd-audit-uat` across all phases. Found 2 files with `human_needed` status (06/07) + Phase 08 HUMAN-UAT.md with 4 pending items. SDK missed Phase 08 items due to frontmatter format difference — caught by direct file read.
  - **Phase 07 export bug fixed** (`faa5403`) — `skill_zip_service.build_skill_zip` used `file_info["relative_path"]` but `skill_files` DB rows store `filename`. Any export of a skill with attached files raised `KeyError` at runtime. Fix: `file_info.get("relative_path") or file_info["filename"]`. Prefers structured path when present (forward-compatible), falls back to DB column.
  - **2 regression tests added** — `TestBuildSkillZipDbStyleFiles`: (1) DB-style `filename`-only dicts build correctly; (2) `relative_path` preferred over `filename` when both present. 34/34 zip unit tests pass.
  - **Phase 08 UAT — all 4 items green:**
    - E2E chat: `tool_start` + `tool_result` SSE events confirmed for `load_skill` against local backend
    - File upload/download/delete: 7 API tests passed (TestUploadSkillFile, TestDeleteSkillFile, TestReadSkillFileContent)
    - 10 MB 413 enforcement: HTTP 413 confirmed before any storage write (`{"detail":"skill file exceeds 10 MB limit"}`)
    - Cross-user RLS: upload/delete on non-owned skills correctly blocked (403/404)
  - **08-HUMAN-UAT.md updated** — status changed from `partial` → `passed`, all 4 results recorded.
  - **07-VERIFICATION.md updated** — `relative_path` bug marked FIXED with regression test reference.
  - **Phase 06 cosmetic items (bare except, nested pass)** — confirmed already fixed in current `chat.py` (as `except Exception as _title_exc:` and `logger.warning` on nested fallback). No action needed.
  - **`enabled=False` PATCH bug (Phase 07 anti-pattern)** — confirmed already fixed: current code uses `body.model_dump(exclude_none=True)`. Stale finding.
- **Files changed:** `backend/app/services/skill_zip_service.py` (1-line fix), `backend/tests/api/test_skill_zip_service.py` (+38 lines, 2 tests), `.planning/phases/07-skills-database-api-foundation/07-VERIFICATION.md`, `.planning/phases/08-llm-tool-integration-discovery/08-HUMAN-UAT.md`
- **Tests:** 286 unit tests pass (unchanged). 34/34 zip service tests pass (was 32 + 2 new).
- **Still outstanding:** Phase 06 PERF-02 latency — needs CI/faster hardware (test skips at 1939ms on dev machine). Non-blocking.
- **Next:** Phase 9 — Skills Frontend. Start with `/gsd-discuss-phase 9`.

## Checkpoint 2026-04-29 (Phase 7 Complete — Skills Database & API Foundation)

- **Session:** Executed all 5 Phase 7 plans (4 waves), ran code review, applied 6 fixes, marked phase complete.
- **Branch:** master (`3219acd`)
- **Done:**
  - **07-01** (`662654f`, `6d94c11`) — Migration 034: `public.skills` table, composite ownership model (`user_id` + `created_by`), 4 RLS policies, `skills_handle_updated_at` trigger, 3 indexes, `skill-creator` global seed (UUID `00000000-0000-0000-0000-000000000007`). Closes SKILL-10.
  - **07-02** (`210c5d1`, merge `6c8adf4`) — Migration 035: `skill_files` table with dual-CHECK path constraints (regex + skill-id binding), private `skills-files` Supabase Storage bucket, 3 table RLS + 3 Storage RLS policies. Storage RLS bug fixed during 07-05 (bare `name` in EXISTS resolved to `s.name` instead of `objects.name`).
  - **07-03** (`4ac3b54`, `4116729`, `cc8433a`) — `skill_zip_service.py`: ZIP build+parse utility (stdlib + PyYAML), 3-layout auto-detection, ZIP-bomb defense (50 MB total + 10 MB per-file), 32 unit tests all pass. PyYAML added to requirements.txt.
  - **07-04** (`e04b2d6`, `17e2546`) — `backend/app/routers/skills.py`: 8 endpoints (POST, GET, GET/{id}, PATCH/{id}, DELETE/{id}, PATCH/{id}/share, GET/{id}/export, POST/import). `SkillsUploadSizeMiddleware` (50 MB ASGI cap). Router registered in `main.py`. Closes SKILL-01/03/04/05/06 + EXPORT-01/02/03.
  - **07-05** (`d1d0d52`, `7472ff8`) — `test_skills.py`: 29 integration tests across 23 test classes, all passing against live Supabase. Applied migrations 034+035 to production. Fixed storage RLS path reference bug inline.
  - **Post-verification fixes** (`4e0120e`) — 3 bugs fixed: export `relative_path` KeyError (DB `filename` → `relative_path` conversion added in router), `PATCH enabled=False` silently dropped (changed to `model_dump(exclude_none=True)`), DB columns leaking into exported SKILL.md frontmatter (replaced catch-all with explicit allow-list).
  - **Code review** (`2ab97fb`) — 10 findings (2 critical, 5 warning, 3 info).
  - **Review fixes** (6 commits `b542da9`–`551a589`) — CR-1 (ZipFile context manager), CR-2 (chunked 413 response), WR-1 (BadZipFile → 422), WR-3 (trailing-slash bypass), WR-4 (enforceable RLS test assert), WR-5 (% and _ wildcard sanitisation). WR-2 already fixed in 4e0120e (skipped).
  - **Phase 7 marked complete** (`9cb8daa`) — ROADMAP, STATE, PROJECT.md updated. HUMAN-UAT.md + VERIFICATION.md committed.
- **Files created:** `supabase/migrations/034_skills_table_and_seed.sql`, `supabase/migrations/035_skill_files_table_and_bucket.sql`, `backend/app/services/skill_zip_service.py`, `backend/app/routers/skills.py`, `backend/app/middleware/skills_upload_size.py`, `backend/app/middleware/__init__.py`, `backend/tests/api/test_skill_zip_service.py`, `backend/tests/api/test_skills.py`
- **Files modified:** `backend/app/main.py`, `backend/requirements.txt`
- **Tests:** 32 unit tests (skill_zip_service) + 29 integration tests (skills API) — all pass. Backend import check clean.
- **Next:** Phase 8 — LLM Tool Integration & Discovery (inject skills catalog into system prompt, implement `load_skill`/`save_skill`/`read_skill_file` tools, skill file upload endpoint). Start with `/gsd-discuss-phase 8`.

## Checkpoint 2026-04-28 (v0.4.0.0 SHIPPED — Web Search Toggle ADR-0008 + Fix A blocked-state UI)

- **Session:** Big arc — wrote 8 standalone ADRs from blueprint, planned + executed ADR-0008 web search toggle through 14 subagent-driven tasks, shipped to production, then debugged + fixed the user-visible bug ("no answer when web search ON") via Fix A.
- **Branch:** master (`ebdc71f`), pushed to origin/master + origin/main + Vercel `--prod`.
- **Done — ADR documentation work (uncommitted):**
  - **8 standalone ADRs in `docs/adr/`** (UNTRACKED — not yet `git add`-ed): adr-0001-raw-sdk-no-langchain.md, adr-0002-single-row-system-settings.md, adr-0003-sse-over-websocket-chat.md, adr-0004-pii-surrogate-architecture.md, adr-0005-tests-against-production-api.md, adr-0006-hybrid-vercel-main-deployment.md, adr-0007-model-cot-observability.md (Proposed), adr-0008-internal-first-retrieval.md (Accepted post-ship).
  - **Project_Architecture_Blueprint.md** (UNTRACKED) — 15-section blueprint generated from graphify knowledge graph (2,035 nodes / 3,739 edges), Section 13 cross-references all 8 ADRs.
  - **Decision: ADR-001 stays Accepted** for CoT observability — uses OpenRouter native `reasoning` param + LangSmith tracing, no LangChain. LangGraph deferred until BJR multi-agent triggers fire (T1-T5 documented in ADR-0007).
- **Done — Web Search Toggle implementation (14 tasks, all committed):**
  - **T1 Migration `033_web_search_toggle.sql`** (`cf5d301`) — `system_settings.web_search_enabled BOOL DEFAULT TRUE` + `user_preferences.web_search_default BOOL DEFAULT FALSE`. Path correction during execution: migrations live at `supabase/migrations/` (repo root), NOT `backend/supabase/migrations/`.
  - **T2 admin field** (`74210e5`) + **T3 user-pref field** (`24543b6`) — Pydantic models updated.
  - **T4 `compute_web_search_effective(L1, L2, L3)`** (`4c0a253`) — pure helper with 10-case parametrized truth-table test. `system AND (override if not None else user_default)`.
  - **T5 tool-service gating** (`6190cb0`) — `get_available_tools(*, web_search_enabled=True)` keyword-only kwarg, excludes `web_search` when False. Existing tavily_api_key check preserved.
  - **T6 classifier tool-awareness** (`ec93e87`) — `classify_intent(available_tool_names=...)`, constraint block injected into CLASSIFICATION_PROMPT, defense-in-depth override via `OrchestratorResult.model_copy(update=...)` if LLM picks ineligible agent. **Correction:** agent registry keys are `research`/`general`, NOT `research_agent`/`general_agent`. OpenRouter mock target is `complete_with_tools`.
  - **T7 chat router wiring** (`15bf0a0`) — `web_search` field on `SendMessageRequest`, effective toggle computed in `event_generator`, passed to `get_available_tools` + `classify_intent`, `_run_tool_loop` skips `deanonymize_tool_args` for web_search (Tavily gets surrogates), defense-in-depth dispatch gate, `log_action(action="web_search_dispatch", details={...})` audit per call. `available_tool_names` threaded as kwarg through `_run_tool_loop`. 210/210 unit tests still green.
  - **T8 API integration tests** (`cec175e`) — 3 tests against production: toggle-off suppresses dispatch, toggle-on allows dispatch, omitted field uses user default. Adapted to existing sync `authed_client` fixture; created real threads via POST /threads (synthetic IDs return 404). Custom `httpx.Client(timeout=Timeout(read=120s))` for cold-path streaming. Railway `railway up --detach` deployed before run; verified by fresh `Application startup complete` in logs.
  - **T9 chat composer toggle** (`b3db9b3`) — Globe-icon toggle in `InputActionBar` (lucide-react `Globe`), props threaded to BOTH `MessageInput` AND `WelcomeInput` consumers, `useChatState.webSearchEnabled` state with sticky-per-thread reset on `activeThreadId` change, `web_search` field added to chat POST body. ChatContext consumer is `useChatContext` (not `useChat`).
  - **T10 admin UI toggle** (`ed21d8e`) — `web_search_enabled` toggle in `AdminSettingsPage.tsx` Tools section. Correction: AdminSettingsPage does NOT duplicate content panels — only navigation is duplicated. CLAUDE.md "BOTH panels" gotcha applies to `DocumentCreationPage`, not this page. Verified by grep `pii_redaction_enabled` → 1 occurrence.
  - **T11 user settings toggle** (`71899f8`) — `web_search_default` checkbox in `SettingsPage.tsx`, fetched on mount, persisted via PATCH `/preferences`, `isDirty` flag updated.
  - **T12 citation source badges** (`c570301`) — `SourceBadge` in `ToolCallCard` (NOT MessageView): blue Globe for web_search, zinc FileText for internal sources. Uses `useI18n()` from `@/i18n/I18nContext`.
  - **T13 i18n keys** (`549472e`) — 8 keys × 2 locales (16 total): `admin.tools.webSearch{Enabled,Desc}`, `chat.webSearch{Toggle,Tooltip}`, `chat.source.{web,internal}`, `settings.webSearchDefault{,Desc}`. Flat dot-notation matching existing structure.
  - **T14 ship** (`3de9b85`) — CHANGELOG 0.4.0.0 entry, ADR-0008 status flipped Proposed → Accepted, master + main pushed, `npx vercel --prod --yes` (LOAD-BEARING — push alone does NOT trigger Vercel for this project).
- **Done — Fix A (post-ship bug fix, blocked-state UI surfacing):**
  - **Bug reproduced via Playwright:** "What is the latest news on Indonesian contract law in 2026?" with web_search ON returned no visible answer. SSE intercept showed exactly 4 events: `redaction_status:anonymizing` → `agent_start:general` → `redaction_status:blocked` → `delta:'',done:true`. Stream completed cleanly; UI showed nothing.
  - **Root cause:** `redactionStage = 'blocked'` was set in `useChatState` but **NO chat component subscribed to it**. The egress filter (in `backend/app/services/redaction/egress.py`, 122 LOC) correctly fired because Presidio tokenized "Indonesian" as LOCATION → registry → all subsequent outbound payloads matched (the platform's own system prompt contains "Indonesian" — false-positive class). Pre-existing UX gap, exposed by web search because Tavily replies pack many entities.
  - **Fix A** (`ebdc71f`) — i18n `redactionBlockedTitle`/`redactionBlockedBody` (camelCase, matched `redactionAnonymizing`/`redactionDeanonymizing`), `MessageView.tsx` accepts `redactionStage` prop and renders amber `ShieldAlert` card with `role="alert" aria-live="polite"` when blocked, `ChatPage.tsx` threads it through, `useChatState.ts` preserves `'blocked'` through `finally` cleanup. Existing `setRedactionStage(null)` at start of `sendMessageToThread` (line 134) clears it on next send. Vercel `READY`, Playwright re-test confirmed amber card renders correctly.
- **Files changed (this session, all committed):** `supabase/migrations/033_web_search_toggle.sql` + 14 backend/frontend files modified across `backend/app/{routers,services}/` + `frontend/src/{hooks,contexts,components,pages,i18n}/`. Plus 4 new test files: `backend/tests/unit/test_compute_web_search_effective.py`, `backend/tests/unit/test_tool_service_web_search_gating.py`, `backend/tests/unit/test_agent_service_tool_awareness.py`, `tests/api/test_web_search_toggle.py`.
- **Files untracked (NOT yet committed):** `Project_Architecture_Blueprint.md`, `docs/adr/adr-000{1..7}-*.md` (ADR-0008 IS committed via T14). Also `.planning/graphs/` (graphify output) and `.planning/config.json` (modified — `graphify.enabled=true` set this session).
- **Tests:** 210+ pytest pass (Task 6 added 2, Task 7 confirmed 210/210 still green). 3/3 new API integration tests pass against production. Frontend `tsc --noEmit` clean, `npm run lint` shows only 10 pre-existing errors in `DocumentsPage.tsx`/`ThemeContext.tsx` — none introduced by this work.
- **Deploy:** Backend Railway `15bf0a0` live (build `b1c72424-8453-47b8-99dd-c4af39213b46`). Frontend Vercel deploy `dpl_28mGg9Qbb86SBqPDzqf5WCZ6T3ct` plus a follow-up Fix-A deploy, both READY. `https://frontend-one-rho-88.vercel.app` returns 200, `/health` returns `{"status":"ok"}`.
- **Production audit log working:** Each `web_search` dispatch persists `audit_logs.action='web_search_dispatch'` with `details: {system_enabled, user_default, message_override, effective, redaction_on}` JSON.
- **VERSION file discrepancy:** CHANGELOG entry at top is `[0.4.0.0] — 2026-04-28` but `cat VERSION` returns `0.3.0.1`. The CHANGELOG was bumped manually in commit `3de9b85` but the VERSION file was NOT updated. Worth bumping in a follow-up.
- **graphify knowledge graph built:** 2,035 nodes, 3,739 edges, 209 communities. Lives at `.planning/graphs/`. Used to generate the blueprint. Stays as untracked working-tree state.
- **Next:** **Fix B — implement domain-term deny list at PII detection layer.** User approved my recommendation: tightly-scoped allowlist (Indonesia/Indonesian, Bahasa, OJK/BI/KPK/BPK/Mahkamah Agung, UU PDP/BJR/KUHP/KUHAP/UU ITE/UUPK). Cities deliberately excluded (false-negative on real address > false-positive on bare city). Implementation site: `backend/app/services/redaction/detection.py` — filter Presidio analyzer results post-detection. Plus a unit test asserting "Indonesian" doesn't enter registry while "Pak Budi" still does. ADR-0009 (or addendum to 0004) optional. **Other queued items:** toggle-reset wrinkle (5-line fix in `useChatState.ts`), VERSION bump to 0.4.0.0, commit the untracked ADR docs + blueprint, Phase 6 (cross-process advisory lock per D-31).

## Checkpoint 2026-04-28 (Phase 5 gap-closure 05-09 — frontend PII toggle)

- **Session:** Re-ran `/gsd-verify-work 5` with Playwright; UAT surfaced 1 new gap (frontend admin PII toggle missing — Plan 05-08 wired backend only). Created Plan 05-09 inline, deployed, verified live.
- **Branch:** master (`b358ea0`), pushed to origin/master + origin/main
- **Done:**
  - **UAT re-verification (Playwright):** Tests 3+4 (D-48 multi-turn chat fix) → PASS in production. Sent 3 turns starting with "Ahmad Suryadi" PII → all returned full responses, no `EgressBlockedAbort`. SSE interceptor confirmed perfect 6-event sequence (`anonymizing → agent_start → deanonymizing → delta → agent_done → delta(done)`) for every turn.
  - **Gap surfaced:** API returned `pii_redaction_enabled: true` correctly, but `AdminSettingsPage.tsx` had zero references — frontend toggle never built (Plan 05-08 scope was backend-only).
  - **Plan 05-09 (`bb467ef`):** 21-line frontend fix — added `pii_redaction_enabled?: boolean` to `SystemSettings` interface, master toggle at top of PII section (before status badges), bilingual i18n strings (`admin.pii.redactionEnabled.{label,desc}` in both ID + EN). Used existing controlled-checkbox pattern from `pii_missed_scan_enabled`.
  - **Vercel deploy:** `npx vercel --prod --yes` → `dpl_CdaFyv525bQ3gbo56vvq2MH4Vb8F` promoted (gotcha: `git push origin master:main` does NOT trigger Vercel for this project — manual deploy required).
  - **Live verification:** Playwright opened `/admin/settings`, navigated to PII section, confirmed toggle visible+checked. Toggled off via `getByRole('checkbox').click()`, save button enabled, PATCH 200, then direct API PATCH set `pii_redaction_enabled: true` to restore production state.
  - **Plan 05-09 docs (`b358ea0`):** PLAN.md + SUMMARY.md (with `gap_closure: true` frontmatter), `05-UAT.md` updated to `status: resolved`, gap marked `status: resolved` with `resolved_by: Plan 05-09`.
- **Files changed:** `frontend/src/pages/AdminSettingsPage.tsx`, `frontend/src/i18n/translations.ts`, `.planning/phases/05-*/{05-09-PLAN.md,05-09-SUMMARY.md,05-UAT.md}`
- **Tests:** TS clean, backend import OK. Existing 246/246 pytest unaffected (frontend-only change, integration test SC#5 already covers off-mode behavior). Pre-existing lint errors in unrelated files (`DocumentsPage`, `ThemeContext`) — not introduced by this change.
- **UAT score:** 3 PASS / 1 SKIPPED / 0 ISSUES. Test 2 (off-mode chat via UI) skipped because end-to-end behavior is already covered by `TestSC5_OffMode` integration tests; manual UI re-test would only exercise the 60s `get_system_settings()` cache expiry timing.
- **Cache observation:** `get_system_settings()` 60s TTL means the immediate post-save `loadSettings()` reads the stale value, making the toggle appear to snap back. Cosmetic UI quirk, not a defect — direct API verification confirmed the DB writes through correctly. Worth a future "settings will apply within 60s" hint, but it's polish.
- **Phase 5 final state:** 9 plans (05-01..05-09), all SUMMARYs present, ROADMAP/STATE already showed phase complete from earlier session, this gap-closure is purely additive admin UX polish.
- **Next:** Phase 6 (final PII milestone phase — `pg_advisory_xact_lock` cross-process upgrade per D-31), OR deferred /review items, OR `/document-release` for README/CLAUDE.md PII section.

## Checkpoint 2026-04-28 (v0.3.0.0 SHIPPED — PII Redaction milestone v1.0 in production)

- **Session:** /pre-ship pipeline (simplify + review) → /ship → deploy fix → schedule follow-up agent
- **Branch:** master (`a2ec1f0`), pushed to origin/master + origin/main
- **Done:**
  - **/simplify** (`c20931b`): 3 fixes — `best_match` double-score, `registry._by_lower` private access → `contains_lower()`, `forbidden_tokens()` cache + invalidation on PERSON upserts
  - **/review auto-fix** (`2962be7`): 4 items — `entity_resolution_mode` else→explicit elif+raise, migrations 030/031 `public.` schema qualifier, 6 new unit tests (contains_lower, forbidden_tokens cache, upsert_delta error propagation, empty-registry edge cases)
  - **/review ASK fix** (`38731fa`): 3 items — SSE tool-loop buffering when redaction_on (prevents partial-turn UI corruption when egress trips mid-tool-call), `_thread_locks` → WeakValueDictionary (memory leak fix), 4 admin 403 HTTP-level tests
  - **/ship** (`f65abd5`): VERSION 0.2.0.0 → 0.3.0.0, CHANGELOG entry, 18 milestone docs (Phase 1 PLANs, 02-VERIFICATION, 05-UAT, 3 PRDs, AGENTS.md), pushed to master + main
  - **Deploy fix** (`a2ec1f0`): `RUN python -m spacy download xx_ent_wiki_sm` added to backend/Dockerfile (build time, before USER switch). Production was 502-looping on missing model — runtime download fails as non-root `app`. Procfile release hook ignored when Dockerfile present.
  - **Backend deploy:** `cd backend && railway up` (manual; this project does NOT auto-deploy on push). Build 8 steps, 55s, deploy complete, /health → `{"status":"ok"}`.
  - **Frontend deploy:** Vercel auto-deployed from main push. HTTP 200 confirmed.
  - **Follow-up agent scheduled:** `trig_01A1ZRy1m5TaCcvwiPZdXHx9` fires Tue 2026-05-05 09:00 WIB. 5-check health audit with Supabase MCP for entity_registry verification. Opens P0 `pii-regression` issue if any check fails.
- **Files changed:** `VERSION`, `CHANGELOG.md`, `PROGRESS.md`, `backend/Dockerfile`, `backend/app/routers/chat.py`, `backend/app/services/redaction_service.py`, `backend/app/services/redaction/{egress,fuzzy_match,registry}.py`, `supabase/migrations/{030,031}_*.sql`, `backend/tests/unit/{test_admin_settings_auth,test_conversation_registry}.py` + 16 milestone docs
- **Tests:** 246/246 pass (10 new unit tests in this session)
- **Deploy:** Railway + Vercel both live at v0.3.0.0. spaCy `xx_ent_wiki_sm` now bundled in image.
- **Memory persisted:** `project_state.md` (v0.3.0.0 SHIPPED), `project_railway_deploy.md` (manual deploy gotcha), `project_presidio_spacy_model.md` (Dockerfile build-time install)
- **Next:** Phase 6 (final PII milestone phase — `pg_advisory_xact_lock` cross-process upgrade per D-31), OR live UAT tests #2/#5/#6 (require driving the UI), OR deferred review items (cluster_id field, FK index on entity_registry.source_message_id, sync→async DB calls in admin endpoints, 8-char→16-char egress hash)

## Checkpoint 2026-04-28 (Phase 5 — Chat-Loop PII Integration complete)

- **Session:** Executed Phase 5 (Chat-Loop Integration) across 4 waves, 6 plans, 22 tasks. Ran UAT — 3/6 tests passed (2 skipped: UI not ready, 1 blocked: UI not running).
- **Branch:** master (`f7baf62`)
- **Done:**
  - **05-01** D-84 service-layer off-mode gate + D-92 `redact_text_batch` primitive (`redaction_service.py` +128 LOC, 19 new unit tests)
  - **05-02** D-91 recursive tool I/O walker (`redaction/tool_redaction.py` new, 285 LOC) + D-86 `execute_tool` registry kwarg plumbing (39 new unit tests)
  - **05-03** D-94 pre-flight egress filter in `classify_intent` + D-83 stale TODO retirement (`agent_service.py` +64 LOC, 8 new unit tests)
  - **05-04** Full chat-loop integration: `chat.py` 291→517 LOC — D-93 batch anon chokepoint, D-88 two `redaction_status` SSE events, D-87 single-batch buffered delivery, D-90 graceful degrade, D-91 walker wrap, D-94 three egress wrappers, title-gen migration to LLMProviderClient
  - **05-05** Frontend SSE consumer: `RedactionStatusEvent` type, `useChatState.redactionStage`, 3 i18n keys (TypeScript clean)
  - **05-06** 7-class pytest integration suite: 14 tests (SC#1 privacy invariant, SC#2-#5, BUFFER-01, egress trip)
  - **Verifier:** 5/5 SC verified, 7 REQ-IDs covered (BUFFER-01/02, TOOL-01/02/03/04)
  - **UAT:** Backend cold-start PASS, TypeScript PASS, pytest 14/14 PASS; off-mode chat + active-mode PII tests skipped (UI pending)
- **Files changed:** `backend/app/routers/chat.py`, `backend/app/services/redaction_service.py`, `backend/app/services/redaction/tool_redaction.py`, `backend/app/services/agent_service.py`, `backend/app/services/tool_service.py`, `frontend/src/lib/database.types.ts`, `frontend/src/hooks/useChatState.ts`, `frontend/src/i18n/translations.ts` + 9 new test files
- **Tests:** 256/256 pass (14 new Phase 5 integration tests)
- **Next:** Phase 6 (final phase of PII Redaction milestone v1.0), or deploy + manual QA with UI running

## Checkpoint 2026-04-24 (State sync — no new features)

- **Session:** Sync checkpoint. SuggestionCards height reduction + PROGRESS.md still uncommitted from prior session.
- **Branch:** master (`3b5c0b8`), pushed to origin/master + origin/main
- **Uncommitted:**
  - `frontend/src/components/chat/SuggestionCards.tsx` — card height reduced (horizontal layout, less padding, icon beside text)
  - `PROGRESS.md` — checkpoint updates
- **Untracked:** `.planning/`, `AGENTS.md`, SVG logo files, `docs/PRD-Agent-Harness.md`, `docs/PRD_SPECTRA7_Platform_v1.docx`, `graphify-out/`, `frontend/graphify-out/`, `frontend/src/graphify-out/`
- **Deploy:** Railway + Vercel both live (last deploy 2026-04-23), SuggestionCards change deployed via `vercel --prod`
- **Next:** Commit uncommitted changes, QA global folders + thread auto-naming in production, stakeholder demo

## Checkpoint 2026-04-23 (Full deploy — 4 features shipped to production)

- **Session:** Built 4 features, deployed to Railway + Vercel, applied migration 028 to Supabase
- **Branch:** master (`3b5c0b8`), pushed to origin/master + origin/main
- **Done:**
  - **LLM thread auto-naming** (`c8daaca`): SSE `thread_title` event, language-aware, non-blocking
  - **Global folders** (`21f3382`): `is_global` column, `is_in_global_subtree()` RPC, cascading subtree visibility, right-click share, Globe icon, read-only for non-owners
  - **Sidebar default collapsed** (`08e51aa`): `panelCollapsed` init `true` in AppLayout
  - **Gradient chat button** (`08e51aa`): purple→indigo gradient on New Chat button
  - **Mobile FolderTree fix** (`3b5c0b8`): Missing props on third FolderTree instance
  - **Migration 028 applied** to Supabase via MCP (global folders live in production)
  - **Deploy**: Railway healthy (5/5 smoke tests), Vercel READY
- **Files changed:** 10 files (4 backend, 5 frontend, 1 migration)
- **Tests:** TypeScript OK, backend import OK, smoke test 5/5
- **Deploy:** Railway + Vercel both live, migration applied
- **Next:** QA test global folders + thread auto-naming in production, stakeholder demo

## Checkpoint 2026-04-23 (LLM thread auto-naming + global folders — pre-deploy)

- **Session:** Added two features: auto-generated chat thread titles via LLM, and global folders with sharing
- **Branch:** master (`21f3382`)
- **Done:**
  - **LLM thread auto-naming** (`c8daaca`): After first assistant response, backend calls LLM to generate ~6-word title. Emits `thread_title` SSE event for instant sidebar update. Language-aware (ID/EN). Non-blocking (try/except).
    - `backend/app/routers/chat.py` — title generation after message persist
    - `frontend/src/hooks/useChatState.ts` — `thread_title` SSE handler
    - `frontend/src/lib/database.types.ts` — `ThreadTitleEvent` type
  - **Global folders** (`21f3382`): Any user can right-click a top-level folder → "Share with All". Entire subtree becomes read-only visible to all users. Globe icon distinguishes shared folders.
    - `supabase/migrations/028_global_folders.sql` — `is_global` column, `is_in_global_subtree()` RPC, updated RLS policies, updated `get_folder_tree` CTE
    - `backend/app/routers/folders.py` — `PATCH /folders/{id}/toggle-global`, updated `GET /folders` for global visibility
    - `frontend/src/components/documents/FolderTree.tsx` — Globe icon, right-click context menu, `(shared)` label, Lock icon for non-owners
    - `frontend/src/pages/DocumentsPage.tsx` — `handleToggleGlobal`, passes `currentUserId` to FolderTree
- **Files changed:** 8 files (3 backend, 4 frontend, 1 migration)
- **Tests:** TypeScript OK, backend import OK, ESLint clean (pre-existing errors only)
- **Pending:** Migration 028 needs to be applied to Supabase; deploy to Railway + Vercel
- **Next:** Apply migration 028, deploy, QA test both features in production

## Checkpoint 2026-04-23 (Knowledge graph rebuild + MCP + CLAUDE.md graphify integration)

- **Session:** Ran full graphify pipeline on entire codebase, rebuilt Obsidian vault, wired graphify MCP server
- **Branch:** master
- **Done:**
  - `graphify .` full run — 237 files, 93% cache hit rate (23 new files extracted via 2 parallel agents)
  - Graph: 1211 nodes, 1655 edges, 192 communities (up from 1229/1729/147 — re-clustering)
  - Obsidian vault: 1403 notes written to `~/claude-code-memory-egs/graphify/claude-code-agentic-rag-masterclass-1/`
  - HTML viz: `graphify-out/graph.html`
  - Token benchmark: **155.9x reduction** per query (510K corpus tokens → ~3,274 per query)
  - `graphify claude install` — added `## graphify` section to `CLAUDE.md`, registered PreToolUse hook in `.claude/settings.json`
  - `.mcp.json` — added `graphify` MCP server (stdio, exposes `query_graph`, `get_node`, `shortest_path`, `god_nodes`)
- **Files changed:** 3 files (`.mcp.json`, `CLAUDE.md`, `.claude/settings.json`) + `graphify-out/`
- **God nodes:** `get_supabase_authed_client` (77 edges), `get_supabase_client` (76), `log_action` (59)
- **Next:** Restart Claude Code to activate graphify MCP; use `/graphify query` to trace architecture questions

## Checkpoint 2026-04-22 (2026 UI design refresh + logo update)

- **Session:** Updated logos (icon rail + thread panel), applied 2026 design trends across CSS and components
- **Branch:** master (`1c733e9`)
- **Done:**
  - Logo swap: IconRail → `lexcore-logo-dark.svg`, ThreadPanel → `lexcore-dark.svg` (from References/)
  - CSS: grain/noise texture overlay (`body::after`, SVG fractalNoise, `mix-blend-mode: overlay`)
  - CSS: multi-tone mesh background — teal second orb (`oklch(0.65 0.15 195)`) alongside purple
  - CSS: new utilities — `.shimmer`, `.card-luminous`, `.interactive-spring`, `--easing-spring` token
  - CSS: `text-wrap: balance` on all headings; `gradient-border-animated:focus-within` rule
  - `SuggestionCards.tsx`: bento redesign — tinted icon backgrounds, per-card ambient colour wash, spring arrow
  - `ThreadList.tsx`: active thread left accent bar (matches IconRail pattern)
  - `WelcomeInput.tsx` + `MessageInput.tsx`: animated gradient border on focus-within
- **Files changed:** 7 files (`index.css`, 4 components, 2 SVGs in public/)
- **Tests:** TypeScript OK, backend import OK
- **Deploy:** Vercel deployed (`frontend-hzhhqwj62-erik-gunawan-s-projects.vercel.app` → production), Railway healthy
- **Next:** Frontend QA pass on production, stakeholder demo prep

## Checkpoint 2026-04-20 (RAG pipeline complete + pre-ship + automations + CLAUDE.md 100)

- **Session:** Completed all 8 RAG pipeline improvements, ran full pre-ship pipeline (simplify + review + codex), implemented Claude Code automations, improved CLAUDE.md to 100/100
- **Branch:** master (`651692c`)
- **Done:**
  - RAG pipeline 8/8: metadata pre-filtering, weighted RRF fusion, Cohere rerank, OCR tracking, graph reindex endpoint, eval golden set, cache key fix, structure-aware chunking (all prior)
  - Migration 027 applied to Supabase (RPCs with filter params + fusion weights + rerank mode columns)
  - Pre-ship pipeline: /simplify fixed O(n²) rerank sort, Literal validation, httpx reuse. /review clean (10/10). /codex caught Cohere client race condition.
  - Claude Code automations: .mcp.json (context7 + Playwright), PostToolUse enhanced (full import check), PreToolUse blocks applied migrations (001-027), /create-migration skill, /run-api-tests enhanced with RAG eval, rag-quality-reviewer subagent
  - CLAUDE.md improved 82→100: condensed design system, fixed stale counts, merged duplicate sections, added skill references
- **Commits:** `53dd0f9` (RAG feat) → `4b6fe28` (simplify) → `0548821` (codex fix) → `36ed096` (automations) → `7ee4afb` + `651692c` (CLAUDE.md)
- **Files changed:** 15 files (10 backend, 2 config, 1 migration, 1 script, 1 docs)
- **Tests:** Backend import OK, health check passed
- **Deploy:** Railway healthy, Vercel auto-deploying from main
- **Next:** Push remaining local commits, stakeholder demo, consider frontend QA pass

## RAG Pipeline Scorecard

| # | Hook | Status | Commit |
|---|------|--------|--------|
| 1 | Structure-aware chunking | ✅ Shipped | `d47df7f` |
| 2 | Multi-modal (vision OCR) | ✅ Shipped | `00d8c2f` |
| 3 | Custom embedding model | ✅ Shipped | `6c9c951` |
| 4 | Metadata pre-filtering | ✅ Shipped | `53dd0f9` |
| 5 | Query expansion (bilingual) | ✅ Shipped | `d47df7f` |
| 6 | Learned fusion weights | ✅ Shipped | `53dd0f9` |
| 7 | Cross-encoder reranking | ✅ Shipped | `53dd0f9` |
| 8 | Graph reindex endpoint | ✅ Shipped | `53dd0f9` |

## Checkpoint 2026-04-19 (RAG Phase 3 embedding infra + Phase 2 plan)

- **Session:** Shipped embedding fine-tuning infrastructure, planned remaining 3 RAG improvements
- **Branch:** master (clean, `6c9c951`)
- **Done:**
  - Committed + deployed `query_logs` table (migration 026) for embedding fine-tuning data collection
  - Fire-and-forget query logging in `tool_service.py` — every search_documents call logs query + retrieved chunk IDs/scores
  - `custom_embedding_model` config in `config.py` + `system_settings` — hot-swappable embedding model
  - `chat.py` prefers custom embedding model over default when set
  - Planned RAG Pipeline Phase 2 (3 remaining improvements): metadata pre-filtering, learned fusion weights, cross-encoder reranking
- **Files changed:** 4 files committed (`config.py`, `chat.py`, `tool_service.py`, `026_embedding_training.sql`)
- **Tests:** Backend import OK, health check passed post-deploy
- **Plan:** `~/.claude/plans/floating-drifting-thimble.md` — RAG Pipeline Phase 2 (3 improvements, 96% confidence)
- **Next:** Execute RAG Pipeline Phase 2 plan (metadata pre-filtering → learned fusion weights → cross-encoder reranking)

## RAG Pipeline Scorecard

| # | Hook | Status | Commit |
|---|------|--------|--------|
| 1 | Structure-aware chunking | ✅ Shipped | `d47df7f` |
| 2 | Multi-modal (vision OCR) | ✅ Shipped | `00d8c2f` |
| 3 | Custom embedding model | ✅ Shipped | `6c9c951` |
| 4 | Metadata pre-filtering | 📋 Planned | — |
| 5 | Query expansion (bilingual) | ✅ Shipped | `d47df7f` |
| 6 | Learned fusion weights | 📋 Planned | — |
| 7 | Cross-encoder reranking | 📋 Planned | — |
| 8 | Query understanding | ⚠️ Partial (intent classification only) | `d47df7f` |

## Checkpoint 2026-04-18 (Knowledge graph updated)

- **Session:** Updated graphify knowledge graph with incremental extraction (3 changed doc files)
- **Branch:** master (clean, no uncommitted changes)
- **Done:**
  - Graphify incremental update: +51 nodes, +55 edges (1091 → 1142 nodes, 1559 → 1614 edges, 125 communities)
  - Traced `get_supabase_authed_client()` god node (77 edges) — confirmed it's the RLS security perimeter bridging all data-access communities
  - Graph outputs refreshed: graph.html, GRAPH_REPORT.md, graph.json
- **Files changed:** 0 committed (graphify-out/ is untracked)
- **Tests:** No code changes — all existing tests still valid
- **Next:** Stakeholder demo prep, then ongoing maintenance

## Checkpoint 2026-04-17 (Phase 3 complete — F13 + F14 shipped)

- **Session:** Implemented Phase 3: F13 (Point-in-Time Compliance Querying) + F14 (UU PDP Compliance Toolkit)
- **Branch:** master (synced with origin + main)
- **Done:**
  - F13: compliance_snapshots table, 4 API endpoints, ComplianceTimelinePage with timeline view + diff comparison, "Save as Snapshot" button on ComplianceCheckPage
  - F14: 3 tables (data_inventory, pdp_compliance_status, data_breach_incidents), 13 API endpoints, PDPDashboardPage (readiness score + DPO appointment), DataInventoryPage (CRUD), DataBreachPage (72-hour countdown + notification template), LLM personal data scanner, require_dpo() dependency
  - Dashboard extended with compliance snapshot count + PDP readiness metrics
  - Migrations 022 + 023 applied to Supabase
  - Deployed to Railway + Vercel
  - Production smoke test: 9/9 passed (snapshots, PDP status, readiness 0→45, inventory CRUD, incident report, notification template, dashboard integration)
- **Commits:** `56ef7d5` (F13) + `05d0a9a` (F14)
- **Files changed:** 21 files (11 new, 10 modified), +1,840 lines
- **Tests:** TypeScript tsc clean, ESLint clean, backend import OK
- **Next:** Stakeholder demo prep, then ongoing maintenance

## Checkpoint 2026-04-17 (BJR pre-ship hardening complete)

- **Session:** Pre-ship pipeline (simplify + review + codex adversarial), security trace Q13/Q14, graph update
- **Branch:** master (synced with origin + main)
- **Done:**
  - Security trace Q13 (admin boundaries): PASS — clean separation
  - Security trace Q14 (RLS cross-references): fixed authed client for evidence reads (`cbb6371`)
  - QA: modal Escape key fix (`adf76fc`), health 100/100
  - /simplify: Literal types on Pydantic models, unused imports removed, selectedPhase dep fix, is_global server filter (`9677dc1`)
  - /review: clean — 0 findings, quality score 10/10
  - /codex adversarial (gpt-5.3-codex): 4 critical/high findings fixed (`3d568e6`):
    1. Evidence auto_approved now requires satisfies_requirement=true
    2. Approval reject/return resets decision from under_review
    3. Completed/cancelled decisions immutable via evidence endpoints
    4. Cancelled decisions blocked from re-entering approval flow
  - Knowledge graph updated (983 nodes, 1311 edges, 120 communities)
  - Graph Question List created (20 questions, 7 categories)
- **Commits:** `c7d2e02` → `adf76fc` → `cbb6371` → `9677dc1` → `3d568e6` (5 commits)
- **Tests:** TypeScript tsc clean, ESLint clean, backend import OK
- **Next:** Deploy final fixes, stakeholder demo, Phase 3 planning

## Checkpoint 2026-04-17 (BJR Decision Governance Module shipped)

- **Session:** Analyzed Ancol GCG/BJR regulatory matrix document, brainstormed integration approach, designed and implemented full BJR module
- **Branch:** master (synced with origin + main)
- **Done:**
  - Deep analysis of `Matriks_Regulasi_GCG_BJR_Ancol_2026.docx` — 28 regulations across 4 layers, 16-item BJR checklist, 11 GCG aspects, 4 strategic risks
  - Design spec: `docs/superpowers/specs/2026-04-17-bjr-governance-module.md`
  - Database: 6 new tables (`bjr_regulatory_items`, `bjr_checklist_templates`, `bjr_decisions`, `bjr_evidence`, `bjr_gcg_aspects`, `bjr_risk_register`) with RLS + seed data
  - Backend: `bjr.py` router (25 endpoints), `bjr_service.py` (LLM evidence assessment + score calculation + phase advance), `models/bjr.py` (12 Pydantic models)
  - Frontend: `BJRDashboardPage.tsx`, `BJRDecisionPage.tsx`, 4 BJR components (PhaseProgress, ChecklistItem, EvidenceAttachModal, RiskCard)
  - Integration: approval workflow hook for phase advancement, dashboard BJR metrics, IconRail standalone nav, 88 i18n keys
  - Migration applied to Supabase, deployed to Railway + Vercel
  - Production smoke test: 8/8 tests passed (regulatory items, checklist, GCG, risks, summary, create decision, get detail, attach evidence)
- **Files changed:** 17 files (10 new, 7 modified), 3,156 insertions
- **Tests:** TypeScript tsc clean, ESLint clean (BJR files)
- **Commit:** `c7d2e02`
- **Next:** QA the BJR module on production UI, Phase 3 planning (F13 + F14), stakeholder demo

## Checkpoint 2026-04-17 (LLM end-to-end test PASSED)

- **Session:** Full AI pipeline validation on production
- **Test document:** `sample_indonesian_nda.txt` — Indonesian NDA between PT Maju Bersama and PT Teknologi Nusantara
- **Results (all PASS):**
  - Document upload + ingestion: status=completed, 3 chunks, embeddings stored, metadata extracted (title, category=legal, summary in Indonesian, tags)
  - Chat with RAG: Multi-agent routing active (Research Agent), search_documents tool called, 4 chunks retrieved, response references specific NDA clauses
  - Follow-up chat: Correctly searched for "force majeure", retrieved relevant chunk
  - SSE streaming: Progressive token-by-token delivery, correct event ordering (agent_start → tool_start → tool_result → delta → done:true)
  - Document creation: Generated 4,801-char NDA, confidence=1.0, auto_approved
  - Compliance check (OJK): overall_status=pass, 2 findings (both pass), 0 missing provisions, confidence=0.95
  - Contract analysis: overall_risk=medium, 3 risks, 2 obligations, 6 critical clauses, 3 missing provisions, confidence=0.85
  - Error handling: 401 (invalid token), 404 (bad thread), 400 (empty file) all correct
  - Tool history: 3 entries recorded with correct tool_type, confidence, review_status
- **What's next:** Stakeholder demo → Phase 3 planning (F13: Point-in-Time Compliance, F14: UU PDP Toolkit)

## Checkpoint 2026-04-16 (Production visual QA passed)

- **Session:** Visual QA of production site (light theme). Logged in, screenshotted 7 key pages, checked console errors, verified backend health.
- **Branch:** master (clean, synced with origin + main)
- **Done:**
  - DocumentsPage fix already committed (`45886d6`)
  - Production QA: Auth, Welcome/Chat, Dashboard, Documents, Create, Settings, Clause Library, Approvals — all pass
  - Zero console errors across all pages
  - Backend health check: `{"status":"ok"}`
  - master synced to main (Vercel production up to date)
- **Files changed:** 0 (working tree clean)
- **Tests:** TypeScript tsc clean
- **Next:** End-to-end LLM test with real Indonesian document → PJAA stakeholder feedback → Phase 3 planning

---

## Checkpoint 2026-04-16 (Session resume — pending QA pass)

- **Session:** Resumed from design refresh + grouped rail checkpoint. Identified uncommitted fix in DocumentsPage.tsx.
- **Branch:** master
- **Done:**
  - Session context restored via /checkpoint resume
  - Identified uncommitted change: DocumentsPage "New Document" button converted from `<button>` to `<Link to="/create">` for correct SPA routing
- **Files changed:** 1 file (frontend/src/pages/DocumentsPage.tsx — staged, not committed)
- **Tests:** TypeScript tsc clean
- **Next:** Commit DocumentsPage fix → Visual QA of light theme on production → End-to-end LLM test with real Indonesian document → PJAA stakeholder feedback

---

## Checkpoint 2026-04-15 (Light theme + design audit)

- **Session:** Full design audit (8 findings, 7 fixed), then light theme implementation (10 steps)
- **Branch:** master
- **Done:**
  - Design audit: removed AI slop (colored left-border cards), added cursor:pointer globally, fixed auth branding ("RAG Chat" to "LexCore"), fixed H1 weight, added color-scheme:dark, increased touch targets
  - Light theme: restructured CSS (`:root` = light, `.dark` = dark), added `@custom-variant dark` for Tailwind v4, created ThemeContext (light/dark/system with localStorage + matchMedia), FOUC prevention script, Settings "Tampilan" section with radio picker, theme-aware Logo component (CSS filter), AuthPage refactored to use Tailwind theme classes, bulk color audit (160 text-*-400 occurrences fixed across 21 files), gradient endpoints moved to CSS vars
  - Vercel env vars cleaned (trailing newlines removed from VITE_API_BASE_URL and VITE_SUPABASE_ANON_KEY)
  - Database cleanup: 21 empty test threads deleted
  - Plan Verification Protocol added to CLAUDE.md
- **Files changed:** 25+ files (index.css, ThemeContext.tsx, App.tsx, index.html, translations.ts, SettingsPage.tsx, AuthPage.tsx, Logo.tsx, IconRail.tsx, ThreadPanel.tsx, AppLayout.tsx, DashboardPage.tsx, DocumentsPage.tsx, MessageView.tsx, + 11 more pages)
- **Tests:** TypeScript tsc clean
- **Next:** Visual QA of light theme on production, tune oklch values if needed, Phase 3 after stakeholder feedback

---

## Checkpoint 2026-04-14 (Unified visual style across all sections)

- **Session:** Applied chat section's atmospheric background (dot-grid + mesh-bg) and minimal layout to all other sections. Removed hard border-b separator bars, added glass sidebars.
- **Branch:** master
- **Done:**
  - dot-grid CSS converted from background-image to ::before pseudo-element overlay (visible above child elements)
  - dot-grid applied to AppLayout `<main>` — every page inherits the dot overlay automatically
  - Removed redundant mesh-bg/dot-grid from WelcomeScreen (inherits from layout)
  - DocumentsPage: removed border-b top bar, merged controls inline with content
  - AuditTrailPage: removed double border-b bars (header + filters), flowed inline
  - Added `glass` (backdrop-blur + semi-transparent bg) to all 10 desktop sidebar panels
  - Extracted InputActionBar component shared by MessageInput + WelcomeInput
  - handleNewChat() for lazy thread creation (no empty threads)
- **Files changed:** 14 files (index.css, AppLayout.tsx, WelcomeScreen.tsx, InputActionBar.tsx, MessageInput.tsx, WelcomeInput.tsx, ThreadPanel.tsx, useChatState.ts, + 10 page files with glass sidebars)
- **Tests:** TypeScript tsc clean
- **Next:** Get PJAA stakeholder feedback, verify visual consistency across all pages, Phase 3 after validation

---

## Checkpoint 2026-04-14 (Chat input UI consistency + new chat flow fix)

- **Session:** Fixed chat MessageInput to match WelcomeInput styling (glass card, action bar icons), fixed "Chat Baru" button to return to welcome screen instead of creating empty thread
- **Branch:** master
- **Done:**
  - MessageInput restyled: glass card, rounded-2xl, gradient send button, Plus/FileText/Mic action bar (matches WelcomeInput)
  - "Chat Baru" button now resets to welcome screen (centered input + suggestion cards) instead of creating an empty thread
  - Added `handleNewChat()` to useChatState — clears activeThreadId without DB call; thread created lazily on first message send
- **Files changed:** 3 files (MessageInput.tsx, ThreadPanel.tsx, useChatState.ts)
- **Tests:** TypeScript tsc clean
- **Next:** Verify chat input transition UX, get PJAA stakeholder feedback, Phase 3 after validation

---

## Checkpoint 2026-04-14 (Phase 1+2 complete, UI polish, chat layout fix)

- **Session:** Built Phase 1 (F3, F5, F6), Phase 2 (F8-F12), code reviews (/simplify x2, /codex, /qa), auth page redesign, LexCore branding, chat layout fix
- **Branch:** master
- **Done:**
  - F3: Clause library + document templates + 9 doc types + per-clause risk scoring
  - F5: Approval workflow engine with admin inbox
  - F6: MFA/security hardening + user management
  - F8: Regulatory intelligence engine with 4 Indonesian sources
  - F9: WhatsApp notification infrastructure
  - F10: Executive dashboard with summary cards + trends
  - F11: Dokmee DMS integration (stubs)
  - F12: Google Workspace export (stubs)
  - Auth page redesign (Apple iCloud style, true black bg, floating card)
  - LexCore branding (logo, icon rail, thread panel, mobile header)
  - Chat layout fix (overflow:clip prevents focus-triggered scroll)
  - Styled glassmorphic tooltips on IconRail
  - Vercel SPA rewrite for client-side routing
  - 3 code reviews: /simplify, /codex (4 findings fixed), /qa (health 100)
- **Files changed:** 40+ files across backend routers, frontend pages, migrations, i18n
- **Tests:** TypeScript tsc -b clean, backend import check clean, QA health 100/100
- **Next:** Get PJAA stakeholder feedback. Phase 3 (F13+F14) only after real user validation.

---

## Convention

- `[ ]` = Not started
- `[-]` = In progress
- `[x]` = Completed

## Modules

### Module 1: App Shell + Observability ✅ COMPLETE

- [x] Project setup (Vite frontend, FastAPI backend, venv, env config)
- [x] Supabase schema (threads + messages tables, RLS policies) — migration at `supabase/migrations/001_initial_schema.sql`
- [x] Backend core (FastAPI, Pydantic settings, Supabase client, JWT auth)
- [x] OpenAI Responses API service + LangSmith tracing
- [x] Backend chat API (thread CRUD + SSE streaming endpoint)
- [x] Frontend auth (login/signup, AuthGuard, protected routes)
- [x] Frontend chat UI (ThreadList, MessageView, streaming, MessageInput)
- [x] End-to-end validated — migration applied, env configured, streaming chat confirmed, RLS verified, messages persisted in DB
- [x] Bug fixes — lifespan replaces deprecated on_event, SSE Cache-Control headers added, apiFetch error check simplified

## Notes

- `openai>=2.30.0` required (responses API + `.stream()` context manager not in v1)
- User message is saved to DB before streaming starts; assistant message is only persisted if the stream produces a response (stream errors no longer create orphaned messages)
- `text-embedding-3-small` cosine similarity scores are typically 0.3–0.6 for semantically related text — use `RAG_SIMILARITY_THRESHOLD=0.3` (not 0.7)
- `pymupdf>=1.25.0` and `tiktoken>=0.8.0` required (Python 3.14 compatible versions)

### Module 2: BYO Retrieval + Memory ✅ COMPLETE

- [x] Plan 8: DB schema + ingestion pipeline (`supabase/migrations/002_module2_schema.sql`, `embedding_service.py`, `ingestion_service.py`, `documents.py` router)
- [x] Plan 9: OpenRouter + stateless chat + RAG retrieval (`openrouter_service.py`, refactor `chat.py` with history + context injection)
- [x] Plan 10: Supabase Realtime ingestion status (frontend `useDocumentRealtime.ts` hook)
- [x] Plan 11: Documents UI (`DocumentsPage.tsx`, `FileUpload.tsx`, `DocumentList.tsx`, nav link)
- [x] Settings UI — per-user LLM model + embedding model with lock enforcement (`user_settings` table, `SettingsPage.tsx`)

#### Module 2 Architecture Summary

- **LLM**: OpenRouter Chat Completions, per-user model (default: `openai/gpt-4o-mini`)
- **Retrieval**: pgvector IVFFlat index, cosine similarity, top-5 chunks, similarity ≥ 0.3
- **Memory**: Stateless — load full thread history from DB, send with every request
- **Ingestion**: Upload → Supabase Storage → BackgroundTask → PyMuPDF parse → tiktoken chunk (500t/50 overlap) → OpenAI embed → pgvector store
- **Status**: Supabase Realtime on `documents` table (pending → processing → completed/failed)
- **Settings**: Per-user LLM + embedding model; embedding locked once documents are indexed
- **New env vars**: `OPENROUTER_API_KEY`, `OPENROUTER_MODEL`, `OPENAI_EMBEDDING_MODEL`, `RAG_TOP_K`, `RAG_SIMILARITY_THRESHOLD`, `STORAGE_BUCKET`
- **New tables**: `documents`, `document_chunks`, `user_settings` (all with RLS)
- **Accepted file types**: `.pdf`, `.txt`, `.md`

#### Sub-Plan Files

- `.agent/plans/8.m2-db-ingestion-pipeline.md`
- `.agent/plans/9.m2-openrouter-stateless-chat.md`
- `.agent/plans/10.m2-realtime-status.md`
- `.agent/plans/11.m2-documents-ui.md`

### Module 3: Record Manager ✅ COMPLETE

- [x] Migration `supabase/migrations/004_record_manager.sql` — add `content_hash` column + partial index to `documents` table
- [x] Backend dedup logic — SHA-256 hashing, check for completed/pending/failed duplicates in `documents.py` upload endpoint
- [x] Frontend feedback — `FileUpload.tsx` shows info message for duplicate uploads; `database.types.ts` updated with `content_hash` field
- [x] API tests — `TestDocumentDedup` class with 5 dedup tests in `tests/api/test_documents.py`

#### Module 3 Architecture Summary

- **Hashing**: SHA-256 of raw file bytes, computed before any storage or DB writes
- **Dedup scope**: Per-user — two users uploading the same file each get their own copy
- **On completed duplicate**: Return 200 `{id, filename, status, duplicate: true}` — no storage upload, no DB insert, no background task
- **On pending/processing duplicate**: Return 409
- **On failed duplicate**: Delete failed record + storage file, then proceed with fresh upload
- **Schema**: `content_hash text` column (nullable), partial index on `(user_id, content_hash) WHERE content_hash IS NOT NULL`
- **Legacy docs**: Pre-Module 3 documents have `content_hash = NULL` and are never matched as duplicates

#### Sub-Plan Files

- `.agent/plans/12.m3-record-manager.md`

### Module 4: Metadata Extraction ✅ COMPLETE

- [x] Migration `supabase/migrations/005_document_metadata.sql` — add `metadata` JSONB column + GIN index to `documents`, add `match_document_chunks_with_metadata` RPC
- [x] Pydantic model `backend/app/models/metadata.py` — `DocumentMetadata` with title, author, date_period, category, tags, summary
- [x] Metadata extraction service `backend/app/services/metadata_service.py` — LLM extraction via OpenRouter with `json_object` response format, LangSmith traced
- [x] Ingestion pipeline integration `backend/app/services/ingestion_service.py` — extract metadata after parse, best-effort (failures don't block ingestion)
- [x] Documents router `backend/app/routers/documents.py` — pass `llm_model` to ingestion, include `metadata` in list, add `GET /documents/{id}/metadata` endpoint
- [x] Enhanced retrieval `backend/app/services/embedding_service.py` — `retrieve_chunks_with_metadata()` using new RPC
- [x] Chat enrichment `backend/app/routers/chat.py` — system prompt includes `[Source: "filename" | Category: X | Tags: ...]` per chunk
- [x] Frontend types `frontend/src/lib/database.types.ts` — `DocumentMetadata` interface, `metadata` field on `Document`
- [x] Frontend UI `frontend/src/components/documents/DocumentList.tsx` — show category badge, tags, summary for completed docs
- [x] API tests `tests/api/test_documents.py` — `TestDocumentMetadata` class with META-01 through META-06

#### Module 4 Architecture Summary

- **Extraction**: LLM (user's selected OpenRouter model) extracts structured metadata after text parsing; truncated to 4000 tokens; `json_object` response format; best-effort (extraction failure skips metadata but ingestion succeeds)
- **Schema**: Fixed Pydantic model — `title`, `author`, `date_period`, `category` (enum), `tags` (list), `summary`; stored as JSONB on `documents.metadata`
- **Retrieval**: `match_document_chunks_with_metadata` RPC joins chunks with documents, returns metadata alongside each chunk; optional `filter_category` parameter
- **Chat**: System prompt now includes `[Source: "filename" | Category: X | Tags: y, z]` header before each chunk, giving LLM document-level context
- **Frontend**: Documents page shows category badge (color-coded), keyword tags, and summary for completed documents with metadata; backward compatible with pre-Module 4 docs

#### Sub-Plan Files

- `.agent/plans/13.m4-metadata-extraction.md`

### Module 5: Multi-Format Support ✅ COMPLETE

- [x] Backend dependencies — `python-docx>=1.1.0`, `beautifulsoup4>=4.12.0` added to `requirements.txt`
- [x] Backend MIME whitelist — expanded `ALLOWED_MIME_TYPES` in `documents.py` to include DOCX, CSV, HTML, JSON
- [x] Format parsers — added `_parse_docx`, `_parse_csv`, `_parse_html`, `_parse_json` in `ingestion_service.py`
- [x] Frontend validation — expanded `ACCEPTED_TYPES` and UI text in `FileUpload.tsx`
- [x] Test fixtures — `sample.docx`, `sample.csv`, `sample.html`, `sample.json` in `tests/fixtures/`
- [x] API tests — `TestMultiFormatUpload` class with FMT-01 through FMT-08, all 31 tests passing
- [x] End-to-end validated — all formats ingested to `completed` status with chunks verified

#### Module 5 Architecture Summary

- **New formats**: DOCX (python-docx), CSV (stdlib csv), HTML (beautifulsoup4 + html.parser), JSON (stdlib json)
- **Pattern**: Each format has a `_parse_<format>(file_bytes) -> str` helper; `parse_text()` dispatches by MIME type
- **No schema changes**: Existing `documents` table and ingestion pipeline handle all formats generically
- **Backward compatible**: PDF, TXT, Markdown handling unchanged
- **Accepted MIME types**: `application/pdf`, `text/plain`, `text/markdown`, `application/vnd.openxmlformats-officedocument.wordprocessingml.document`, `text/csv`, `text/html`, `application/json`
- **Test note**: `upload_docx` helper generates DOCX in-memory with a UUID paragraph per call (avoids content-hash dedup collisions); requires `python-docx` in the test runner's Python env (`pip3 install python-docx`)

### Module 6: Hybrid Search & Reranking ✅ COMPLETE

- [x] Migration `supabase/migrations/006_hybrid_search.sql` — add `fts tsvector` column, GIN index, auto-populate trigger, `match_document_chunks_fulltext` RPC
- [x] Config additions — `rag_hybrid_enabled`, `rag_rrf_k`, `rag_rerank_enabled`, `rag_rerank_model` in `backend/app/config.py`
- [x] Rerank model — `backend/app/models/rerank.py` with `RerankScore` and `RerankResponse`
- [x] Hybrid retrieval service — `backend/app/services/hybrid_retrieval_service.py` with vector search, full-text search, RRF fusion, optional LLM reranker
- [x] Chat router updated — `backend/app/routers/chat.py` uses `HybridRetrievalService` instead of `EmbeddingService`
- [x] Search diagnostics endpoint — `POST /documents/search` with `hybrid`, `vector`, `fulltext` modes
- [x] API tests — `TestHybridSearch` class with HYB-01 through HYB-08, all 75 tests passing

#### Module 6 Architecture Summary

- **Hybrid search**: Combines pgvector cosine similarity (semantic) + Postgres `tsvector`/`tsquery` full-text search (lexical)
- **Fusion**: Reciprocal Rank Fusion (RRF) merges rankings from both methods; formula: `score = sum(1 / (k + rank + 1))`, default `k=60`
- **Pipeline**: Over-fetch `top_k * 3` candidates from each method concurrently (`asyncio.gather`), fuse via RRF, return top-k
- **Reranking**: Optional LLM-based reranker via OpenRouter (gated by `RAG_RERANK_ENABLED=true`), uses `json_object` response format, best-effort fallback
- **Full-text search**: `websearch_to_tsquery` for natural query support (quoted phrases, boolean operators)
- **Trigger**: Postgres trigger auto-populates `fts` column on chunk INSERT/UPDATE — no ingestion pipeline changes needed
- **Fallback**: When `RAG_HYBRID_ENABLED=false`, delegates to vector-only search (existing behavior)
- **No new dependencies**: Uses existing OpenAI SDK + Supabase client + Postgres built-in full-text search
- **No frontend changes**: Hybrid search is transparent — same response shape as vector-only

#### Sub-Plan Files

- `.claude/plans/polymorphic-watching-codd.md`

### Module 7: Additional Tools ✅ COMPLETE

- [x] Migration `supabase/migrations/007_tool_calls.sql` — add `tool_calls` JSONB to messages, `execute_user_document_query` RPC
- [x] Config additions — `tavily_api_key`, `tools_enabled`, `tools_max_iterations` in `backend/app/config.py`
- [x] Pydantic models — `ToolCallRecord`, `ToolCallSummary` in `backend/app/models/tools.py`
- [x] Tool service — `backend/app/services/tool_service.py` with `search_documents`, `query_database`, `web_search` tools
- [x] OpenRouter service — `complete_with_tools()` method for non-streaming tool-calling completions
- [x] Chat router refactor — agentic tool-calling loop with extended SSE protocol (`tool_start`, `tool_result`, `delta` events)
- [x] Frontend types — `ToolCallRecord`, `SSEEvent` types in `database.types.ts`
- [x] Frontend SSE parsing — `ChatPage.tsx` handles `tool_start`, `tool_result`, `delta` events
- [x] ToolCallCard component — collapsible tool execution display with icons and attribution
- [x] MessageView updated — renders tool cards inline (streaming and persisted)
- [x] API tests — `TestToolCalling`, `TestSQLSafety`, `TestToolPersistence`, `TestSSECompat`, `TestToolErrorHandling` (TOOL-01 through TOOL-09)

#### Module 7 Architecture Summary

- **Agentic loop**: Chat endpoint now uses a tool-calling loop — LLM decides which tools to invoke, backend executes them, results feed back to LLM, final text response is streamed
- **Three tools**: `search_documents` (hybrid RAG retrieval), `query_database` (text-to-SQL with safety), `web_search` (Tavily API fallback)
- **Non-streaming iterations**: Tool-calling rounds use regular completions (fast); only the final text response is streamed via SSE
- **SQL safety**: Postgres RPC `execute_user_document_query` with `SECURITY DEFINER` + `STABLE`, SELECT-only validation, mandatory user_id scoping, write-keyword rejection
- **Web search**: Tavily API via httpx; optional — gated by `TAVILY_API_KEY` env var; tool hidden if not configured
- **SSE protocol**: Extended with `type` field — `tool_start`, `tool_result`, `delta` events; backward compatible (delta events still have `done` field)
- **Attribution**: Every tool call visible in UI via collapsible ToolCallCard; web search shows source URLs, SQL shows query, doc search shows chunk count
- **Persistence**: Tool execution records stored in `messages.tool_calls` JSONB; rendered on page reload
- **Fallback**: `TOOLS_ENABLED=false` → identical to Module 6 behavior; tool errors caught and reported to LLM gracefully
- **No new dependencies**: Uses existing `httpx` for Tavily; no LangChain/LangGraph
- **New env vars**: `TAVILY_API_KEY` (optional), `TOOLS_ENABLED` (default true), `TOOLS_MAX_ITERATIONS` (default 5)

#### Sub-Plan Files

- `.claude/plans/expressive-tinkering-avalanche.md`

### Module 8: Sub-Agents ✅ COMPLETE

- [x] Config additions — `agents_enabled`, `agents_orchestrator_model` in `backend/app/config.py`
- [x] Pydantic models — `AgentDefinition`, `OrchestratorResult` in `backend/app/models/agents.py`; `agent` field added to `ToolCallSummary`
- [x] OpenRouter service — `complete_with_tools()` updated with optional `tools` and `response_format` params
- [x] Agent service — `backend/app/services/agent_service.py` with registry (research, data_analyst, general), `classify_intent()`, `get_agent_tools()`
- [x] Chat router refactor — conditional orchestrator + sub-agent dispatch when `agents_enabled=true`; Module 7 behavior preserved as default
- [x] Frontend types — `AgentStartEvent`, `AgentDoneEvent` in `database.types.ts`; `agent` field on `tool_calls`
- [x] AgentBadge component — `frontend/src/components/chat/AgentBadge.tsx` with active and badge modes
- [x] ChatPage SSE parsing — `activeAgent` state, handles `agent_start`/`agent_done` events
- [x] MessageView updated — renders AgentBadge during streaming and on persisted messages
- [x] API tests — `TestOrchestratorRouting`, `TestSubAgentExecution`, `TestAgentSSEProtocol`, `TestAgentPersistence` (AGENT-01 through AGENT-12)

#### Module 8 Architecture Summary

- **Multi-agent routing**: Orchestrator classifies intent via single non-streaming LLM call with `json_object` response format, routes to specialist sub-agent
- **Three agents**: Research Agent (search_documents, 5 iterations), Data Analyst (query_database, 5 iterations), General Assistant (web_search, 3 iterations)
- **Tool isolation**: Each sub-agent only sees its assigned tools — LLM can't call tools outside its definition
- **SSE protocol**: Extended with `agent_start` (agent name + display name) and `agent_done` events wrapping the tool loop + delta stream
- **Persistence**: Agent name stored in `tool_calls.agent` JSONB field — no migration needed
- **Backward compatible**: `AGENTS_ENABLED=false` (default) preserves exact Module 7 single-agent behavior
- **Fallback**: Invalid orchestrator response gracefully falls back to general agent
- **No new dependencies**: Reuses existing OpenRouter, tool service, and httpx
- **New env vars**: `AGENTS_ENABLED` (default false), `AGENTS_ORCHESTRATOR_MODEL` (optional, defaults to user's model)
- **PR**: #2 merged to master via squash merge (commit `c1561fe`)

#### Sub-Plan Files

- `.claude/plans/expressive-tinkering-avalanche.md`

### Module 9: RBAC Settings Architecture ✅ COMPLETE

- [x] Migration `backend/migrations/008_rbac_settings.sql` — `system_settings` (single-row, admin-only RLS), `user_preferences` (per-user RLS), `is_super_admin()` SQL helper
- [x] Admin promotion script `backend/scripts/set_admin_role.py` — CLI to set `app_metadata.role = super_admin` via Supabase Admin API
- [x] Backend `dependencies.py` — extract `role` from JWT `app_metadata`, add `require_admin` FastAPI dependency (403 for non-admins)
- [x] System settings service `backend/app/services/system_settings_service.py` — cached reader with 60s TTL, service-role client
- [x] Admin settings router `backend/app/routers/admin_settings.py` — `GET/PATCH /admin/settings` (admin-only)
- [x] User preferences router `backend/app/routers/user_preferences.py` — `GET/PATCH /preferences` (per-user)
- [x] Refactored `chat.py` + `documents.py` — replaced `get_or_create_settings` with `get_system_settings()`
- [x] Removed deprecated `user_settings.py` router and registration
- [x] Frontend `AuthContext` — provides `user`, `role`, `isAdmin` from JWT `app_metadata`
- [x] Frontend `AdminGuard` component — redirects non-admins away from admin routes
- [x] Frontend `AdminSettingsPage` — Global Configuration Dashboard (LLM, embedding, RAG tuning, tools, agents)
- [x] Frontend `SettingsPage` refactored — converted to user preferences (theme picker + notification toggle)
- [x] Frontend routing — `/admin/settings` with `AuthGuard` + `AdminGuard`, `AuthProvider` wrapping all routes
- [x] Frontend `ChatPage` — conditional Shield icon in sidebar nav for admins

#### Module 9 Architecture Summary

- **3-layer enforcement**: Database RLS (`is_super_admin()` checks JWT claim), Backend (`require_admin` dependency), Frontend (`AdminGuard` component)
- **Role storage**: Supabase `auth.users.raw_app_meta_data.role` — embedded in JWT, only writable via service-role key
- **System settings**: Single-row table (`CHECK (id = 1)`), stores LLM model, embedding model, RAG params, tool/agent config
- **User preferences**: Per-user table with theme and notifications_enabled
- **Settings decoupled**: System config (admin-only, DB table) vs user preferences (per-user, personal)
- **Cache**: 60s TTL on system settings to avoid DB hit per request
- **Promotion**: `python -m scripts.set_admin_role <email>` — user must sign out/in for JWT refresh
- **Backward compatible**: `chat.py` and `documents.py` read from `system_settings` instead of per-user `user_settings`
- **PR**: #4 merged to master

### UI Improvements ✅ COMPLETE

- [x] Animated thinking indicator — bouncing dots animation (`ThinkingIndicator.tsx`) while waiting for LLM response, replaces static blinking cursor
- [x] Collapsible thread groups — threads grouped by date (Today, Yesterday, Previous 7 Days, Older) with expand/collapse chevrons and count badges
- **PR**: #5 merged to master

### UI Redesign ✅ COMPLETE

- [x] Dark navy theme — oklch color palette, purple accent, removed light mode
- [x] Layout system — Icon rail (vertical nav) + collapsible ThreadPanel + content area via `AppLayout.tsx`
- [x] ChatPage refactor — 231 → 35 lines, state extracted to `useChatState.ts` hook + `ChatContext.tsx`
- [x] Welcome screen — brand icon, greeting, `MessageInput`, `SuggestionChips` (interactive, pre-fills chat input on click)
- [x] Full i18n — Indonesian (default) + English, `I18nProvider` with localStorage persistence
- [x] i18n coverage — AuthPage, FileUpload, DocumentList all use `useI18n()` translations
- [x] Admin input styling — number inputs use `bg-secondary text-foreground` for dark theme
- [x] Deleted `App.css` — styles consolidated into `index.css` with CSS variables

#### UI Redesign Architecture Summary

- **Layout**: `AppLayout` wraps `<Outlet>` with `IconRail` (60px) + conditional `ThreadPanel` (240px); thread panel shown only on chat routes
- **State**: `useChatState` hook manages threads, messages, streaming, tool/agent events; exposed via `ChatContext`
- **i18n**: `I18nProvider` → `useI18n()` → `t(key, params?)` with `{param}` interpolation; 2 locales (id, en); persisted to localStorage
- **Theme**: Dark-only, oklch color space, custom CSS variables for icon-rail and sidebar colors
- **Components**: `IconRail` (brand + nav + avatar), `ThreadPanel` (new chat + date-grouped threads), `UserAvatar` (initials + sign-out menu), `WelcomeScreen` (greeting + input + chips)

### Admin i18n + Cleanup ✅ COMPLETE

- [x] AdminSettingsPage fully i18n-ized — 30 translation keys (Indonesian + English) for all sections: LLM, embedding, RAG config, tool calling, sub-agents, errors, save actions
- [x] `.gitignore` updated — rules for `*.png`, `*.zip`, `excalidraw.log`, `.playwright-mcp/` to remove design asset clutter
- [x] UI redesign deployed to production (Vercel + Railway)

### Module 10: Conversation Branching ✅ COMPLETE

- [x] Migration `supabase/migrations/009_conversation_branching.sql` — add `parent_message_id` column, index, backfill existing linear chains
- [x] Backend `chat.py` — accept `parent_message_id`, branch-aware history loading (walk ancestor chain), chain user + assistant message inserts
- [x] Frontend `messageTree.ts` — `buildChildrenMap`, `getActivePath`, `getForkPoints` utilities
- [x] Frontend `useChatState.ts` — `allMessages`, `branchSelections`, `forkParentId` state; `handleSwitchBranch`, `handleForkAt`, `handleCancelFork` handlers
- [x] Frontend `MessageView.tsx` — fork button (GitFork icon on hover), `BranchIndicator` (1/3 with arrows) at fork points
- [x] Frontend `MessageInput.tsx` — fork-mode banner with cancel button
- [x] Frontend `ChatPage.tsx` — wire new props from context
- [x] Frontend `database.types.ts` — `parent_message_id` on Message interface
- [x] i18n — `branch.forkMode`, `branch.fork`, `branch.cancel` in Indonesian + English
- [x] End-to-end tested — backward compat (existing threads load), new message chaining, fork creation (two children of same parent), branch-aware LLM history (only ancestor messages sent)

#### Module 10 Architecture Summary

- **Message tree**: `parent_message_id` self-FK on `messages` table; adjacency list pattern
- **Backfill**: Existing linear conversations auto-linked via `LAG()` window function in migration
- **History construction**: When `parent_message_id` provided, backend walks ancestor chain from that message to root; only ancestor messages sent to LLM
- **Frontend tree**: `buildChildrenMap` groups messages by parent; `getActivePath` walks tree following `branchSelections`; only the active branch path is rendered
- **UI**: Fork icon appears on hover; clicking sets `forkParentId` and shows banner in input area; after send, new branch created; fork points show `BranchIndicator` with left/right arrows to switch
- **Backward compatible**: Existing flat threads work unchanged (backfill sets parent chains; `parent_message_id=None` falls back to flat mode)
- **New env vars**: None — uses existing infrastructure
- **New tables**: None — single column addition to `messages`

#### Sub-Plan Files

- `.claude/plans/enumerated-hugging-otter.md`

### Figma UI Migration ✅ COMPLETE

- [x] Shared components — `FeaturePageLayout`, `DropZone`, `HistorySection`, `EmptyState`, `SectionLabel` in `components/shared/`
- [x] IconRail expanded to 6 nav items (Chat, Documents, Create, Compare, Compliance, Analysis) + flyout "More Modules" menu
- [x] `DocumentCreationPage` — doc type selector, form fields, language toggle, reference/template uploads (static UI)
- [x] `DocumentComparisonPage` — dual document upload, swap button, comparison focus selector (static UI)
- [x] `ComplianceCheckPage` — doc upload, framework selector, scope multi-select, context textarea (static UI)
- [x] `ContractAnalysisPage` — doc upload, analysis type multi-select, governing law, depth selector (static UI)
- [x] All 4 pages wired to backend with API calls, loading states, and result display panels
- [x] Full i18n support (Indonesian + English) for all new screens (~80 keys per locale)
- [x] Feature accent colors added (creation/purple, management/cyan, compliance/emerald, analysis/amber)
- [x] shadcn/ui select, textarea, popover components installed
- [x] Routes added to `App.tsx` for `/create`, `/compare`, `/compliance`, `/analysis`

### Document Tool Backend ✅ COMPLETE

- [x] Backend service `document_tool_service.py` — Pydantic response models + LLM prompts for all 4 operations (create, compare, compliance, analyze), reuses `parse_text` from ingestion service, OpenRouter with `json_object` response format
- [x] Backend router `document_tools.py` — 4 FormData endpoints (`POST /document-tools/create`, `/compare`, `/compliance`, `/analyze`), file upload validation, auth required
- [x] Router registered in `main.py`
- [x] Frontend wiring — all 4 pages updated with controlled form state, `apiFetch` calls, loading spinners, error display, structured result rendering in right panel
- [x] Create page: generated document preview (title, summary, content)
- [x] Compare page: differences table with significance badges, risk assessment, recommendation
- [x] Compliance page: overall status badge (pass/review/fail), findings list, missing provisions
- [x] Analysis page: risk cards, obligations table, critical clauses, missing provisions
- [x] QA fix: Generate Draft button disabled until required fields are filled (per doc type validation)
- [x] Backend fix: bilingual document creation handles dict content response from LLM
- [x] Result persistence: `document_tool_results` Supabase table with RLS, history endpoints, frontend history sidebars

#### Document Tool Architecture Summary

- **Pattern**: File upload → parse text (reuse ingestion `parse_text`) → LLM structured output (OpenRouter + `json_object` format) → Pydantic validation → JSON response → persist to `document_tool_results`
- **Persistence**: Results stored in `document_tool_results` table (JSONB), history sidebar shows recent results per tool type, `GET /document-tools/history` endpoint
- **File handling**: FormData with optional files (reference/template for creation, two docs for comparison, single doc for compliance/analysis)
- **Truncation**: Document text capped at ~48k chars (~12k tokens) to stay within LLM context
- **Validation**: Red border + inline error messages on required fields when clicking disabled button; per doc type required field lists
- **No new dependencies**: Reuses existing OpenRouter service, ingestion parser, auth middleware

#### Sub-Plan Files

- `.agent/plans/11.figma-ui-migration.md`

### Welcome Screen Redesign ✅ COMPLETE

- [x] Sparkle icon replaces "K" badge, gradient text for user name
- [x] `WelcomeInput` — large card-style input with action bar (attach, doc icon, "Legal AI v1.0" label, mic, send)
- [x] `SuggestionCards` — Bento grid with left accent borders + inline icons (no icon circles), responsive (stacks on mobile)
- [x] `ThreadPanel` — search bar, "Chat History" subtitle, fully collapsible (340px expanded ↔ hidden), toggle in IconRail

### Page Layout Redesign ✅ COMPLETE

- [x] `DocumentCreationPage` — 3-column layout (Icon Rail | Form 75% + History 25% | Preview empty state), dynamic form fields per doc type (Generic, NDA, Sales, Service), output language radio, reference/template uploads
- [x] `DocumentsPage` — 3-column layout with upload section (dropzone, recent uploads, storage quota), filter section (type filters, status checkboxes), main area (top bar with search + grid/list toggle, responsive document card grid)
- [x] `DocumentComparisonPage` — same 3-column pattern with dual doc upload, swap button, comparison focus, blank results area
- [x] `ComplianceCheckPage` — same 3-column pattern with framework selector, scope multi-select, blank results area
- [x] `ContractAnalysisPage` — same 3-column pattern with analysis type, governing law, depth selector, blank results area
- [x] All column 2 panels standardized to 340px width
- [x] Unified sidebar collapse — shared state via `useSidebar` hook, `PanelLeftClose`/`PanelLeftOpen` icons, panels collapse fully (no 50px strip)
- [x] Settings/Admin pages — 3-column layout with section navigation, centered content with section icons

### Design Quality (A / A+) ✅ COMPLETE

- [x] **Mobile responsive** — hamburger menu header, panel overlays with backdrop, responsive grids, FAB on all feature pages
- [x] **AI slop eliminated** — icon-in-circle cards replaced with accent-border + inline icon, pulse rings removed from EmptyState
- [x] **Touch targets** — all interactive elements 40px+, icon rail 44px, focus-ring on all custom buttons
- [x] **Accessibility** — `prefers-reduced-motion` support for all animations, focus-visible rings on all interactive elements
- [x] **Micro-interactions** — `interactive-lift` hover effect, purposeful active/press states
- [x] **Typography hierarchy** — `font-extrabold tracking-tight` on page headings, 3-tier weight system
- [x] **Document card variety** — category-colored left borders, colored dots, multi-format file type badges (PDF/DOC/MD/CSV/JSON/TXT)
- [x] **Chat layout** — input pinned to bottom, messages scroll above (matches ChatGPT/Claude pattern)
- [x] **Indonesian language** — all panel subtitles translated, consistent language throughout
- [x] **Design Score: A** | **AI Slop Score: A+** (verified by /design-review regression audit)

### 2026 Design System ✅ COMPLETE

- [x] **Font**: Geist Variable (single family, not a default stack)
- [x] **Colors**: oklch/oklab color space, 11 unique colors, coherent dark navy palette
- [x] **Glassmorphism** — `glass` utility on Icon Rail, ThreadPanel, MessageInput, AuthPage, WelcomeInput
- [x] **Layered shadows** — `--shadow-xs/sm/md/lg` CSS variables
- [x] **Gradient accents** — gradient user message bubbles, gradient text for user name
- [x] **Bento grid** — Row 1: equal halves, Row 2: wider left (3fr) + narrower right (2fr)
- [x] **Mesh background** — radial glows, dot grid texture, floating orbs
- [x] **Staggered animations** — `stagger-children` for sequential card entrance
- [x] **Feature accent colors** — per-page left border colors (purple/cyan/emerald/amber)
- [x] **Icon Rail gradient bar** — 3px gradient left accent on active nav items

---

## Deployment Status

### Frontend (Vercel) — ✅ DEPLOYED

- **URL**: https://frontend-one-rho-88.vercel.app
- **Platform**: Vercel (auto-detected Vite)
- **Env vars**: `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`, `VITE_API_BASE_URL` (points to Railway backend)
- **Redeploy**: `cd frontend && npx vercel --prod`

### Backend (Railway) — ✅ DEPLOYED

- **URL**: https://api-production-cde1.up.railway.app
- **Platform**: Railway (Dockerized FastAPI)
- **Health check**: `GET /health` → `{"status": "ok"}`
- **CORS**: Configured via `FRONTEND_URL` env var (comma-separated origins)
- **Redeploy**: `cd backend && railway up`

### Git History

| PR | Branch | Description | Status |
|----|--------|-------------|--------|
| #1 | `feat/module-6-7` | Modules 6+7 — Hybrid Search + Tool Calling | Merged |
| #2 | `feat/module-8-sub-agents` | Module 8 — Sub-Agent Architecture | Merged |
| #3 | `feat/deploy` | Deploy backend (Railway) + frontend (Vercel) | Merged |
| #4 | `feat/rbac-settings` | Module 9 — RBAC Settings Architecture | Merged |
| #5 | `feat/ui-improvements` | Animated thinking indicator + collapsible thread groups | Merged |

---

## PJAA CLM Platform Upgrade

Based on PJAA stakeholder survey (53 questions, 7 findings) — see `References/PJAA-Research-Synthesis-CLM-Compliance.docx.md`.
Full gap analysis and specs: `.agent/plans/15.pjaa-clm-gap-analysis-specs.md`

### Phase 1: Go-Live Foundation (Weeks 1-8)

#### Feature 1: Audit Trail & Activity Logging ✅ COMPLETE

- [x] Migration `supabase/migrations/011_audit_trail.sql` — `audit_logs` table with 4 indexes, RLS enabled (admin-only read)
- [x] Backend `audit_service.py` — fire-and-forget `log_action()` function, service-role client
- [x] Backend `audit_trail.py` router — `GET /admin/audit-logs` (paginated + filtered), CSV export, distinct actions
- [x] Instrumented 4 existing routers (documents, document_tools, admin_settings, threads) with audit log calls
- [x] Frontend `AuditTrailPage.tsx` — admin-only, date/action/resource filters, pagination, CSV export button
- [x] Route at `/admin/audit`, nav link in SettingsPage (mobile + desktop)
- [x] i18n: 17 keys in both Bahasa Indonesia and English
- [x] Security hardening: RLS enabled on audit_logs (caught by adversarial review — was exposed via PostgREST)
- **Commit**: `59a277a`, hardening fix: `ca60078`

#### Feature 7: Bahasa Indonesia Full-Text Search ✅ COMPLETE

- [x] Migration `supabase/migrations/010_bahasa_fts.sql` — FTS trigger + RPC switched from `'english'` to `'simple'` config
- [x] Backfill existing document chunks with new config
- [x] No backend/frontend changes needed — existing search automatically benefits
- **Commit**: `59a277a`

#### Feature 2: AI Confidence Scoring & HITL Gates ✅ COMPLETE

- [x] Migration `supabase/migrations/012_confidence_hitl.sql` — `confidence_score`, `review_status`, `reviewed_by/at/notes` on `document_tool_results`; `confidence_threshold` on `system_settings`; RLS for admin review access
- [x] All 4 Pydantic models updated with `confidence_score: float = 0.0`
- [x] All 4 LLM system prompts request `confidence_score` in JSON response
- [x] `_save_result` computes `review_status` based on configurable threshold (default 0.85)
- [x] Review queue endpoints: `GET /document-tools/review-queue`, `PATCH /document-tools/review/{id}` with `ReviewAction` Pydantic model
- [x] `get_result` endpoint updated — admins can view any user's results (for review)
- [x] `ConfidenceBadge.tsx` component — percentage badge + review status badge
- [x] Badges added to all 4 tool result pages (DocumentCreation, Comparison, Compliance, Analysis)
- [x] `ReviewQueuePage.tsx` — filter by status, approve/reject with notes, audit logged
- [x] `AdminSettingsPage.tsx` — HITL Gates section with threshold input + visual preview
- [x] i18n: 22 keys in both Bahasa Indonesia and English
- [x] Security hardening: `ReviewAction` Pydantic model (validates action, caps notes at 2000 chars), re-review guard (409 if not pending), `confidence_threshold` bounded to 0.0-1.0
- **Commit**: `7c4b20e`, hardening fix: `ca60078`

#### Feature 4: Obligation Lifecycle Tracker ✅ COMPLETE

- [x] Migration `supabase/migrations/013_obligations.sql` — `obligations` table with 15 columns, RLS (4 policies), 3 indexes, `updated_at` trigger, `check_overdue_obligations()` RPC
- [x] Backend `obligations.py` router — 7 endpoints: list (filtered), summary, create, extract from analysis, check-deadlines, update, soft-delete
- [x] Frontend `ObligationsPage.tsx` — summary cards (5 statuses), filter tabs, obligations table with status badges, deadline formatting (relative), "Mark Complete" button
- [x] "Import Obligations" button on `ContractAnalysisPage.tsx` — extracts obligations from analysis results into structured rows
- [x] IconRail nav item (`ClipboardList` icon) + route at `/obligations`
- [x] i18n: 23 keys in both Bahasa Indonesia and English
- **Commit**: `d5ca1be`

#### Feature 3: Enhanced Drafting Workbench ✅ COMPLETE

- [x] Migration `supabase/migrations/014_drafting_workbench.sql` — `clause_library` + `document_templates` tables, RLS (own + global), indexes, triggers, 12 seeded global Indonesian legal clauses
- [x] Backend `clause_library.py` router — 6 endpoints (list with filters, get, create, create global/admin, update, delete)
- [x] Backend `document_templates.py` router — 5 endpoints (list, get with clause resolution, create, update, delete)
- [x] Backend `document_tool_service.py` — `create_document()` accepts `clauses` param, LLM prompt requests `clause_risks`, `GeneratedDocument` model updated
- [x] Backend `document_tools.py` — create endpoint accepts `clause_ids` + `template_id` Form fields, fetches/merges template defaults and clause content
- [x] 9 doc types — added vendor, JV, property lease, employment, SOP/board resolution with per-type form fields and validation
- [x] Frontend clause selector — picker with risk-colored items, selected clause chips, mismatch warnings, clause_ids in submission
- [x] Frontend template selector — dropdown with pre-fill on select, "Save as Template" persists current form state
- [x] Frontend per-clause risk badges — `clause_risks` rendered in results area with risk-colored cards
- [x] `ClauseLibraryPage.tsx` — 2-panel layout (filter/search + clause cards grid), CRUD, global clause badges
- [x] IconRail nav item (`Library` icon), route at `/clause-library`
- [x] i18n: ~45 keys per locale (doc types, clause library, templates, risk levels, categories)

#### Feature 5: Approval Workflow Engine ✅ COMPLETE

- [x] Migration `supabase/migrations/015_approval_workflows.sql` — `approval_workflow_templates`, `approval_requests`, `approval_actions` tables with RLS, indexes, seeded default template
- [x] Backend `approvals.py` router — submit for approval, inbox (admin), my requests, get detail with actions + resource, take action (approve/reject/return), cancel, template CRUD (admin)
- [x] Frontend `ApprovalInboxPage.tsx` — mobile-first 2-panel layout, inbox vs my requests toggle, status filter tabs with count badges, action buttons (approve/reject/return/cancel)
- [x] IconRail nav item (`FileCheck` icon), route at `/approvals`
- [x] i18n: 17 keys per locale for approvals

#### Feature 6: MFA & Security Hardening ✅ COMPLETE

- [x] Migration `supabase/migrations/016_security_hardening.sql` — `user_profiles` table (display_name, department, is_active, deactivated_at/by), `mfa_required` + `session_timeout_minutes` on system_settings, backfill existing users
- [x] Backend `user_management.py` router — list users (admin), deactivate/reactivate (admin), get/update own profile (self-service)
- [x] Frontend `UserManagementPage.tsx` — admin user list with search, status badges, deactivate/reactivate buttons with confirmation
- [x] Frontend `SettingsPage.tsx` — Security section with MFA info panel + session timeout info, User Management admin link
- [x] Route at `/admin/users` (admin-guarded)
- [x] i18n: 20 keys per locale for user management + security

### Phase 1 Summary

| Feature | Status | Commit | Lines |
|---------|--------|--------|-------|
| F1: Audit Trail | ✅ Done | `59a277a` | +1,994 |
| F7: Bahasa FTS | ✅ Done | `59a277a` | (included above) |
| F2: Confidence & HITL | ✅ Done | `7c4b20e` | +553 |
| Hardening (review fixes) | ✅ Done | `ca60078` | +30 |
| F4: Obligation Tracker | ✅ Done | `d5ca1be` | +1,519 |
| F3: Drafting Workbench | ✅ Done | `55f7c05` | +1,200 |
| F5: Approval Workflows | ✅ Done | `55f7c05` | +600 |
| F6: MFA & Security | ✅ Done | `55f7c05` | +400 |

**Phase 1 progress: 7 of 7 features complete** (F1, F2, F3, F4, F5, F6, F7) ✅ PHASE 1 COMPLETE

### Phase 2: Enterprise Capabilities (Weeks 9-16) ✅ COMPLETE

#### Feature 8: Regulatory Intelligence Engine ✅ COMPLETE

- [x] Migration `supabase/migrations/017_regulatory_intelligence.sql` — `regulatory_sources`, `regulatory_updates` (with vector embedding), `regulatory_alerts` tables, RLS, indexes, 4 seeded Indonesian regulatory sources (JDIH, IDX, OJK, Perda DKI)
- [x] Backend `regulatory.py` router — 9 endpoints: source CRUD (admin), update feed with filters, mark read, alerts inbox, dismiss alert
- [x] Frontend `RegulatoryPage.tsx` — 2-panel layout, source type filter, update feed with relevance badges, read/unread state, admin source management
- [x] IconRail nav item (`BookOpen` icon), route at `/regulatory`

#### Feature 9: WhatsApp Notifications ✅ COMPLETE

- [x] Migration `supabase/migrations/018_whatsapp_notifications.sql` — `notification_channels` (per-user, multi-channel), `notification_log` (delivery tracking), WhatsApp settings on `system_settings`
- [x] Backend `notifications.py` router — 6 endpoints: channel CRUD, notification history, admin send (inserts pending record for dispatcher)
- [x] Notification infrastructure ready for WhatsApp Business API integration (requires Meta Business verification)

#### Feature 10: Executive Dashboard ✅ COMPLETE

- [x] Backend `dashboard.py` router — 3 endpoints: aggregate summary (documents/obligations/approvals/compliance/regulatory counts), obligation timeline (next 90 days), compliance trend (last 6 months by month)
- [x] Frontend `DashboardPage.tsx` — responsive grid with 5 summary cards (color-coded), obligation timeline with priority badges, compliance trend with CSS bars
- [x] IconRail nav item (`LayoutDashboard` icon) as first nav item, route at `/dashboard`

#### Feature 11: Dokmee DMS Integration ✅ COMPLETE

- [x] Migration `supabase/migrations/019_dms_integration.sql` — DMS settings on `system_settings`, `external_source` + `external_id` on documents
- [x] Backend `integrations.py` router — 4 endpoints: status check, browse folders, import, export (production-ready stubs pending Dokmee API access)
- [x] Frontend `IntegrationsPage.tsx` — Dokmee card with configured/not-configured status, action buttons

#### Feature 12: Google Workspace Export ✅ COMPLETE

- [x] Migration `supabase/migrations/020_google_integration.sql` — `google_tokens` table (per-user OAuth2), Google OAuth settings on `system_settings`
- [x] Backend `google_export.py` router — 5 endpoints: status, auth URL, OAuth callback, export to Drive, disconnect (production-ready stubs pending Google OAuth setup)
- [x] Frontend `IntegrationsPage.tsx` — Google Drive card with configured + connected status, connect/disconnect buttons

**Phase 2 progress: 5 of 5 features complete** (F8, F9, F10, F11, F12) ✅ PHASE 2 COMPLETE

### BJR Decision Governance Module ✅ COMPLETE

- [x] Design spec (`docs/superpowers/specs/2026-04-17-bjr-governance-module.md`)
- [x] Migration `supabase/migrations/021_bjr_governance.sql` — 6 tables, RLS, indexes, seed data
- [x] Backend `bjr.py` router — 25 endpoints (decisions, evidence, phase progression, risks, admin CRUD, summary)
- [x] Backend `bjr_service.py` — LLM evidence assessment, BJR score calculation, phase advancement
- [x] Backend `models/bjr.py` — 12 Pydantic request/response models
- [x] Approval integration — `approvals.py` handles `resource_type='bjr_phase'`, auto-advances on approval
- [x] Dashboard extension — BJR metrics in `/dashboard/summary`
- [x] Frontend `BJRDashboardPage.tsx` — decision overview, summary cards, create modal, standing risks
- [x] Frontend `BJRDecisionPage.tsx` — decision lifecycle, phase stepper, checklist with evidence, risk register
- [x] 4 BJR components: PhaseProgress, ChecklistItem, EvidenceAttachModal, RiskCard
- [x] IconRail standalone nav item (`Scale` icon → `/bjr`)
- [x] i18n: 88 keys (44 Indonesian + 44 English)
- [x] Seed data: 28 regulations (4 layers), 16 checklist items (3 phases), 11 GCG aspects, 4 standing risks
- [x] Production smoke test: 8/8 passed
- **Commit**: `c7d2e02`

#### BJR Module Architecture Summary

- **Decision lifecycle**: Pre-Decision → Decision → Post-Decision → Completed, with phase-gated approvals
- **Evidence linking**: Polymorphic references to existing LexCore entities (documents, tool results, approvals) via `reference_id` + `reference_table`
- **LLM assessment**: Each evidence attachment can be assessed by LLM against its specific BJR checklist requirement, with confidence scoring and HITL review
- **Configurable framework**: Regulations, checklist items, GCG aspects stored as data (admin-manageable), seeded with Ancol's specific requirements
- **Integration**: Reuses existing approval workflows, audit trail, HITL confidence gating, executive dashboard
- **Source document**: `Matriks_Regulasi_GCG_BJR_Ancol_2026.docx` — Ancol GCG & BJR regulatory matrix

### Phase 3: Advanced Compliance (Months 5-6) ✅ COMPLETE

#### Feature 13: Point-in-Time Compliance Querying ✅ COMPLETE

- [x] Migration `supabase/migrations/022_compliance_snapshots.sql` — `compliance_snapshots` table with RLS
- [x] Backend `compliance_snapshots.py` router — 4 endpoints (create, list, get, diff)
- [x] Snapshot creation reuses existing `check_compliance()` from `document_tool_service.py`
- [x] Diff logic — pure JSON comparison of findings, missing provisions, status changes
- [x] Frontend `ComplianceTimelinePage.tsx` — timeline view with A/B snapshot comparison
- [x] "Save as Snapshot" button added to `ComplianceCheckPage.tsx`
- [x] IconRail: Clock icon in Legal Tools group → `/compliance/timeline`
- **Commit**: `56ef7d5`

#### Feature 14: UU PDP Compliance Toolkit ✅ COMPLETE

- [x] Migration `supabase/migrations/023_uu_pdp_toolkit.sql` — 3 tables (`data_inventory`, `pdp_compliance_status`, `data_breach_incidents`) with DPO-aware RLS
- [x] Backend `pdp.py` router — 13 endpoints (inventory CRUD, compliance status, readiness, incidents, notification template, PII scanner)
- [x] Backend `pdp_service.py` — LLM personal data scanner + readiness score calculator (DPO 20pts + breach plan 20pts + inventory 30pts + DPIA 30pts)
- [x] Backend `models/pdp.py` — Pydantic models with Literal types
- [x] `require_dpo()` dependency in `dependencies.py` for DPO role support
- [x] Frontend `PDPDashboardPage.tsx` — readiness score circle, DPO appointment form, checklist, status cards
- [x] Frontend `DataInventoryPage.tsx` — processing activity table + create modal
- [x] Frontend `DataBreachPage.tsx` — incident list with 72-hour deadline countdown + notification template generator
- [x] IconRail: ShieldAlert standalone item → `/pdp`
- [x] Dashboard: PDP readiness + snapshot count in `/dashboard/summary`
- [x] i18n: ~100 keys (50 ID + 50 EN) for PDP module
- **Commit**: `05d0a9a`

**Phase 3 progress: 2 of 2 features complete** (F13, F14) ✅ PHASE 3 COMPLETE
