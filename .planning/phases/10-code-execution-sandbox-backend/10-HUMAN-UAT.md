---
status: partial
phase: 10-code-execution-sandbox-backend
source: [10-VERIFICATION.md]
started: 2026-05-01T09:05:00Z
updated: 2026-05-01T09:05:00Z
---

## Current Test

[awaiting human testing]

## Tests

### 1. E2E SSE streaming during execute_code
expected: Real-time line-by-line stdout/stderr events stream to frontend with shape `{type, line, tool_call_id}` during execution
how: With Docker available and `SANDBOX_ENABLED=true` in `.env`, start the backend (`uvicorn app.main:app --reload --port 8000`), open the frontend, send a chat message that triggers `execute_code` (e.g., "run: print('hello'); print('world')"). Inspect the browser DevTools Network tab → EventSource stream. Confirm `code_stdout` events appear *before* `tool_result`.
result: [pending]

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
result: [pending]

### 3. SandboxDockerfile build smoke test
expected: All 10 D-P10-03 packages import successfully inside a non-root container
how:
```bash
docker build -f SandboxDockerfile -t lexcore-sandbox:test .
docker run --rm lexcore-sandbox:test python -c \
  "import pandas, matplotlib, pptx, jinja2, requests, bs4, numpy, openpyxl, scipy, IPython; print('all packages OK')"
```
result: [pending]

## Summary

total: 3
passed: 0
issues: 0
pending: 3
skipped: 0
blocked: 0

## Gaps
