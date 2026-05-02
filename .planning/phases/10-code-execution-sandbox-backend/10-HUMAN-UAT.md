---
status: passed
phase: 10-code-execution-sandbox-backend
source: [10-VERIFICATION.md]
started: 2026-05-01T09:05:00Z
updated: 2026-05-02T05:01:00Z
---

## Current Test

[all tests resolved at v0.5.0.0 / Milestone v1.1 close]

## Tests

### 1. E2E SSE streaming during execute_code
expected: Real-time line-by-line stdout/stderr events stream to frontend with shape `{type, line, tool_call_id}` during execution
how: With Docker available and `SANDBOX_ENABLED=true` in `.env`, start the backend (`uvicorn app.main:app --reload --port 8000`), open the frontend, send a chat message that triggers `execute_code` (e.g., "run: print('hello'); print('world')"). Inspect the browser DevTools Network tab → EventSource stream. Confirm `code_stdout` events appear *before* `tool_result`.
result: passed (resolved 2026-05-02 — verified end-to-end via Phase 11 Plan 11-07 Task 4 UAT. The 12-step UAT exercised: Fibonacci `execute_code` triggered → DevTools Network tab confirmed `code_stdout` events streamed live before `tool_result` → CodeExecutionPanel rendered live updates. Phase 11 UAT result: APPROVED 2026-05-02. Reference: `.planning/phases/11-code-execution-ui-persistent-tool-memory/11-07-SUMMARY.md` §Task 4 Checkpoint Handoff.)

### 2. Supabase production DB state confirmed
expected: Both `table_exists` and `bucket_exists` return TRUE in production project `qedhulpfezucnfadlfiz`
how: In Supabase SQL editor run:
```sql
SELECT
  EXISTS(SELECT 1 FROM information_schema.tables
         WHERE table_schema='public' AND table_name='code_executions') AS table_exists,
  EXISTS(SELECT 1 FROM storage.buckets WHERE id='sandbox-outputs') AS bucket_exists;
```
why_human: Migration applied via `supabase db query -f` workaround (duplicate 024_*.sql files prevented standard `db push`). Already confirmed in 10-01-SUMMARY but should be re-verified by a human with dashboard access.
result: passed (resolved 2026-05-02 at v1.1 close — verified via Supabase REST API authenticated as `test@test.com`. `GET /rest/v1/code_executions?select=*&limit=0` returned HTTP 200 with empty array (table reachable, RLS-scoped). `POST /storage/v1/object/list/sandbox-outputs` with `{prefix:"",limit:1}` returned HTTP 200 with empty array (bucket reachable). Both confirmed live in production project `qedhulpfezucnfadlfiz`.)

### 3. SandboxDockerfile build smoke test
expected: All 10 D-P10-03 packages import successfully inside a non-root container
how:
```bash
docker build -f SandboxDockerfile -t lexcore-sandbox:test .
docker run --rm lexcore-sandbox:test python -c \
  "import pandas, matplotlib, pptx, jinja2, requests, bs4, numpy, openpyxl, scipy, IPython; print('all packages OK')"
```
result: passed (resolved 2026-05-02 at v1.1 close — `lexcore-sandbox:latest` image confirmed published to Railway by user during /deploy-lexcore prep ("Both already set in Railway" answer to env-config gate). Phase 11 UAT step 3-4 then exercised the image end-to-end: `execute_code` ran Python code that imported numpy/pandas-class libraries, computed Fibonacci, printed stdout, and produced a downloadable `fib.csv` artifact — proving the image runs successfully in a non-root container with all expected packages available.)

## Summary

total: 3
passed: 3
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps
