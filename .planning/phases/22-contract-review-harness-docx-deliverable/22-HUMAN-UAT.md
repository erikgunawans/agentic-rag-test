---
status: diagnosed
phase: 22-contract-review-harness-docx-deliverable
source: [22-VERIFICATION.md]
started: 2026-05-05T19:17:00Z
updated: 2026-05-06T01:35:00Z
---

## Current Test

[testing complete — 4 production bugs found via Playwright live UAT, gap closure required]

## Tests

### 1. Full pytest harness suite at runtime
expected: `pytest tests/harnesses/ -v` from `backend/` (with venv activated) returns 0 failures across all 90+ harness tests, including the async HIL pause+resume E2E test (`test_contract_review_e2e.py`). Async + fixture wiring works correctly under live test runner conditions.
result: pass
evidence: 84/84 passed in 3.27s on 2026-05-05; verified runtime gates for REVIEW #1, #3, #4, #6, #7 + skeleton + flag-gating + smoke_echo regressions

### 2. Live harness execution end-to-end
expected: With `harness_enabled=true` AND `contract_review_enabled=true` AND `tool_registry_enabled=true` set in admin settings (D-16 dark-launch flip; in practice also `workspace_enabled=true` for file upload + `sandbox_enabled=true` for DOCX post_execute), upload a real contract DOCX or PDF to a chat thread. Gatekeeper triggers Contract Review harness. CR-01 through CR-08 + filter step run end-to-end. CR-03 pauses for HIL input; user supplies context; resume completes through CR-08. Final DOCX (`contract-review-report.docx`) appears in the Workspace Panel with `source: 'harness'` and a green chip; download produces a valid Word document with title page, executive summary, redline tables, and recommended next steps.
result: issue
reported: "Harness triggered correctly after upload + 'I uploaded a contract' phrasing, but immediately broke during phase execution. Three production bugs surfaced from Railway logs: (1) DB check constraint workspace_files_source_check rejects source='harness' — migration drift between plan 22-11 frontend type widening and the DB schema; (2) harness_engine.py call sites for write_todos() pass wrong arguments — TypeError: missing 2 required positional arguments 'token' and 'todos' across 4 phase transitions (init/in_progress/completed/error); (3) post_harness._persist_summary fails RLS check on messages table insert (same shape as CR-21-04 from Phase 21). Net effect: harness silently fails — Plan Panel renders all 9 phases but no progression, no DOCX produced, harnessRun returns null on /harness/active polling."
severity: blocker
detected_via: "Playwright live UAT 2026-05-06 with all 5 v1.3 flags flipped"
diagnosis_log: "/tmp/railway-logs-22-uat.txt"

### 3. Gatekeeper multi-turn dialogue + workspace-aware trigger
expected: With contract_review_enabled=true and an empty workspace, send "review my contract for risk" to a fresh thread. Gatekeeper should NOT immediately trigger the harness; instead it should ask the user to upload a contract first (workspace-aware system prompt from plan 22-04). After upload, send the same message — gatekeeper now emits `[TRIGGER_HARNESS]` and harness starts. Confirms CR-21-08 fix.
result: pass-with-caveat
evidence: "Part 1 (empty-workspace refusal): PASS. Gatekeeper responded 'Please upload your contract in either DOCX or PDF format...' — no harness started. Part 2 (post-upload trigger): PARTIAL. The exact phrase 'review my contract for risk' did NOT trigger the harness even with the contract already uploaded — gpt-4o-mini repeated the upload-required refusal. The exact few-shot phrase 'I uploaded a contract' DID trigger immediately. CR-21-08 is partially fixed: workspace block + few-shots help, but live gpt-4o-mini still misses on phrasings that don't closely match the few-shot examples. Plan 22-04's eval set (15 mocked phrasings) passes in CI because mocked LLM is deterministic, but real gpt-4o-mini reliability is lower than the eval suggests."
caveat: "Phrasing-coverage gap — recommend either (a) expanding few-shot examples in plan 22-04 system prompt to cover more abstract phrasings like 'review for risk', or (b) running plan 22-05 live-LLM eval against production to quantify the regression rate."

## Summary

total: 3
passed: 2
issues: 1
pending: 0
skipped: 0
blocked: 0
note: "Test 3 = pass-with-caveat (gatekeeper logic works, but gpt-4o-mini phrasing coverage is narrower than the eval suggests). Test 2 = blocker — 3 distinct production bugs in harness execution path."

## Gaps

- truth: "DB check constraint `workspace_files_source_check` must allow `source='harness'` (added by plan 22-11 to frontend type)."
  status: failed
  reason: "Live harness CR-01 phase tries to write contract-text.md with `source='harness'` and the DB rejects it: `new row for relation \"workspace_files\" violates check constraint`. Plan 22-11 widened frontend `WorkspaceFile.source` to include `'harness'` but the DB CHECK constraint on `workspace_files.source` was never updated. Migration drift."
  severity: blocker
  test: 2
  artifacts: ["supabase/migrations/039_workspace_files.sql (CHECK constraint definition)", "backend/app/services/workspace_service.py write_text_file"]
  missing: ["new migration that ALTER TABLE workspace_files DROP CONSTRAINT workspace_files_source_check; ADD CONSTRAINT ... CHECK (source IN ('user','upload','agent','sandbox','harness'))"]

- truth: "`write_todos()` calls in `harness_engine.py` must pass the required `token` and `todos` arguments."
  status: failed
  reason: "All 4 phase-state transitions (init / in_progress / completed / error) call `write_todos()` without args, raising `TypeError: write_todos() missing 2 required positional arguments: 'token' and 'todos'`. The error handler ITSELF crashes in the same way, so harness failure is silent — the user sees only the empty Plan Panel and no progression."
  severity: blocker
  test: 2
  artifacts: ["backend/app/services/harness_engine.py (4 call sites of write_todos)", "backend/app/services/todos_service.py (write_todos signature)"]
  missing: ["call-site fixes passing user token + todos list", "regression test that exercises a full phase transition cycle without mocks at the call boundary"]

- truth: "`post_harness._persist_summary` must satisfy RLS on `messages` table insert."
  status: failed
  reason: "RLS policy on messages requires user_id matches auth.uid() OR service-role. post_harness uses authed client without user_id — fails 42501. Same shape as CR-21-04 from Phase 21 UAT (gatekeeper persistence). Phase 22 introduced a new persist path that didn't apply the same fix."
  severity: major
  test: 2
  artifacts: ["backend/app/services/post_harness.py:155 _persist_summary", "supabase/migrations/039_workspace_files.sql (messages RLS — Phase 21 fix CR-21-04 reference)"]
  missing: ["pass user_id explicitly OR switch to service-role client", "regression test from issue CR-21-04 should be re-run for the post_harness path"]

- truth: "Gatekeeper trigger reliability for natural phrasings (CR-21-08 narrow fix)"
  status: caveat
  reason: "Phrasing 'review my contract for risk' refused; 'I uploaded a contract' (exact few-shot match) succeeded. gpt-4o-mini does not generalize from the 4-5 few-shots in plan 22-04 to cover 'review for X' compositional phrasings."
  severity: minor
  test: 3
  artifacts: ["backend/app/services/gatekeeper.py build_system_prompt few-shots", "backend/tests/data/gatekeeper_eval_set.json"]
  missing: ["expand few-shots to cover 'review for risk' / 'analyze for risks' compositional phrasings", "OR run scripts/eval_gatekeeper_live.py against production to measure real compliance rate"]
