---
phase: 11-code-execution-ui-persistent-tool-memory
phase_number: 11
phase_name: Code Execution UI & Persistent Tool Memory
milestone: v1.1
status: completed
completed: 2026-05-02
verdict: PASS-WITH-CAVEATS
plans: 7
waves: 4
requirements_completed: [SANDBOX-07, MEM-01, MEM-02, MEM-03]
head_commit: "0170739"
---

# Phase 11 Summary — Code Execution UI & Persistent Tool Memory

Phase 11 closes Milestone v1.1 (Agent Skills & Code Execution). It surfaces Phase 10's sandbox backend in the chat UI through a new `CodeExecutionPanel` component, and persists tool call results (with proper `tool_call_id` + status fields) so the LLM can reference earlier execute_code results across conversation turns without re-running them. A silent multi-agent persistence bug discovered during planning was also fixed.

## Wave-by-Wave Outcome

| Wave | Plans | Outcome |
|------|-------|---------|
| 1 (parallel, 3) | 11-01, 11-02, 11-03 | ToolCallRecord schema + 50KB validator; frontend SSE event types; `GET /code-executions/{execution_id}` endpoint |
| 2 (parallel, 2) | 11-04, 11-05 | chat.py history reconstruction + persistence (silent MEM-01 bug fixed); useChatState `sandboxStreams` Map + 3-site lifecycle reset |
| 3 (1) | 11-06 | `CodeExecutionPanel.tsx` (359 lines) + 17 `sandbox.*` i18n keys × ID/EN |
| 4 (1, blocking UAT) | 11-07 | `ToolCallList` router switch + MessageView prop drill via ChatPage; human UAT approved 2026-05-02 |

## Requirements → Code Citations

| Req | What it means | Where it lives |
|-----|---------------|----------------|
| SANDBOX-07 | Code Execution Panel renders execute_code tool calls | `frontend/src/components/chat/CodeExecutionPanel.tsx:214-302` (panel anatomy); `frontend/src/components/chat/ToolCallCard.tsx:130-186` (router); `frontend/src/hooks/useChatState.ts:211-233` (SSE handlers); `frontend/src/i18n/translations.ts:666-682, 1346-1362` (i18n) |
| MEM-01 | Tool calls persist across thread reload | `backend/app/models/tools.py:13-60` (schema + 50KB validator); `backend/app/routers/chat.py:530, 544, 1071, 1084` (4 ctor sites with `tool_call_id`); the multi-agent success-path silent bug fix is at `chat.py:1067-1073` |
| MEM-02 | History reconstruction emits OpenAI tool-message triplets | `backend/app/routers/chat.py:97-146` (`_expand_history_row`); history SELECT widened at L206 + L227; helper called at L222 + L235 |
| MEM-03 | LLM answers follow-ups from prior tool data without re-execution | UAT step 9 verified end-to-end: "What was the 15th Fibonacci?" answered without any `code_stdout`/`code_stderr` SSE events on the follow-up turn (no DevTools Network entries, no panel re-render) |

## Architecture Decisions Anchored Here (D-P11-*)

- **D-P11-04 / D-P11-11** — Single source of truth for the 50KB output cap is the Pydantic `field_validator` on `ToolCallRecord.output`. All four call sites in `chat.py` get truncation for free.
- **D-P11-08** — `tool_call_id` and `status` fields are optional + nullable on persisted records (no migration; legacy rows still typecheck).
- **D-P11-05** — `sandboxStreams` is a `Map<tool_call_id, {stdout[], stderr[]}>` keyed by UUID, reset at 3 lifecycle sites (thread switch, send, post-stream finally) so stale entries cannot leak across turns.
- **D-P11-06** — File-download cards refresh signed URLs via the new `GET /code-executions/{execution_id}` endpoint, reusing `_refresh_signed_urls` and `get_supabase_authed_client`.
- **D-P11-01** — `ToolCallList` becomes a router: `tool === 'execute_code' && tool_call_id` → `CodeExecutionPanel`; everything else (incl. legacy execute_code without `tool_call_id`) → existing `ToolCallCard` with new `TOOL_CONFIG.execute_code = {icon: Terminal, label: 'Code Execution'}`.

## Silent Bug Fixed This Phase

The multi-agent branch in `chat.py` was only persisting `ToolCallRecord` on the exception path (~L1084 today). Successful tool calls in the multi-agent flow were never appended to the persisted record list — meaning successful execute_code runs in multi-agent mode would not be reconstructable on subsequent history loads. Plan 11-04's Splice E.2 added the matching success-path append at L1067-1073, which is what makes MEM-01 actually work in the multi-agent case (not just single-agent).

## Test Coverage Added

- 11 unit tests for ToolCallRecord (`backend/tests/models/test_tool_call_record.py`)
- 13 unit tests for chat history reconstruction helpers (`backend/tests/routers/test_chat_history_reconstruction.py`)
- 4 integration tests for `GET /code-executions/{execution_id}` (`backend/tests/api/test_code_executions_get_by_id.py`)
- **Total: 28 new tests**, all green pre-merge. Phase 10 sandbox-streaming regression suite (8/8) and prior Phase 1+ tool-call tests remain green post-merge.
- **No frontend component tests for CodeExecutionPanel** — relies on UAT + tsc. Flagged in VERIFICATION.md as a follow-up.

## Anti-Grep Guards (all green per VERIFICATION.md)

- `out.execution_id` present at exactly L168 of ToolCallCard.tsx; no `?? out.id` fallback (only a forbidding comment)
- `Terminal, label: 'Code Execution'` present at TOOL_CONFIG L11
- `truncated, ` marker at tools.py L60
- Module-level helpers `_derive_tool_status` (L65) and `_expand_history_row` (L97) are test-injectable
- ! `grep -q "backdrop-blur"` on `CodeExecutionPanel.tsx` — passes; the panel is a persistent in-message component, glass would violate the design system per CLAUDE.md

## UAT Outcome (Plan 11-07 Task 4)

**APPROVED 2026-05-02** — orchestrator drove the 12-step UAT script in a live local browser session (frontend `:5174`, backend `:8000` `/health = ok`, `test@test.com` super_admin). User replied `approved` after walking all 12 steps:
- Steps 1-6: streaming render + completion render + file download
- Step 7: refresh persistence (MEM-01 confirmed end-to-end)
- Steps 8-9: follow-up references prior tool result without re-execution (MEM-02/03 confirmed via DevTools Network tab — no `code_stdout`/`code_stderr` SSE events)
- Steps 10-12: legacy compatibility, multi-call gap-6 stacking, error path

## Risks / Loose Ends (operational, not technical)

Per `VERIFICATION.md`:

1. **Railway sandbox readiness** — `SANDBOX_ENABLED=False` by default; without an env flip + published `lexcore-sandbox:latest` image + reachable Docker daemon, the panel never renders in prod. Phase 10 territory.
2. **Multi-worker session semantics** — In-memory IPython sessions don't survive Railway replica scaling. Pre-existing concern.
3. **Signed-URL failure modes** — `handleDownload` shows a generic 2-second error toast; no 404 vs 500 vs network distinction.
4. **PII redaction batch index alignment** — `_expand_history_row` emits 1-or-3-or-N items per row; future edits to the redaction batch at `chat.py` ~L485 must respect this row-shape contract.
5. **No frontend component tests for CodeExecutionPanel** — 360-line component relies on UAT + tsc; consider a follow-up `CodeExecutionPanel.test.tsx`.
6. **Legacy fallback path** — Exercised against synthetic fixtures only; not yet validated against the prod data corpus.

## Verdict

**PASS-WITH-CAVEATS** — codebase delivers what Phase 11 promised. Caveats are operational, not technical defects in this phase's deliverables.

## Key References

- `VERIFICATION.md` (this directory) — full goal-backward verification report
- 7 plan SUMMARYs: `11-01-SUMMARY.md` through `11-07-SUMMARY.md`
- `11-CONTEXT.md` — D-P11-01..D-P11-11 decisions
- `11-UI-SPEC.md` — design contract
- `11-PATTERNS.md` — in-repo analogs for the splice points
- `PROGRESS.md` 2026-05-02 checkpoint — wave-by-wave session narrative

## Milestone v1.1 Status

Phase 11 closes **Milestone v1.1 (Agent Skills & Code Execution)**: 5 phases, 26 plans, ~314 unit tests. Ready to:
- Run `/gsd-complete-milestone` to archive ROADMAP/REQUIREMENTS to `.planning/milestones/v1.1-*`
- Ship to production: `/deploy-lexcore` (Vercel deploys from `main`, Railway needs `railway up` — **enable `SANDBOX_ENABLED=true` and publish `lexcore-sandbox:latest`** as part of the deploy or the panel never renders)
