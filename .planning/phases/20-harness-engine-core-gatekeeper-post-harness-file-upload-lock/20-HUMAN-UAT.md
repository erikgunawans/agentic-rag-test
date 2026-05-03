---
status: partial
phase: 20-harness-engine-core-gatekeeper-post-harness-file-upload-lock
source: [20-VERIFICATION.md]
started: 2026-05-04T00:39:00+07:00
updated: 2026-05-04T00:39:00+07:00
---

## Current Test

[awaiting human testing]

## Tests

### 1. E2E smoke harness execution
expected: Full gatekeeper → [TRIGGER_HARNESS] → 2-phase smoke-echo run → post-harness summary flow completes end-to-end with live server + LLM. `harness_complete` SSE event fires, HarnessBanner shows phase progression, post-harness summary appears in chat.
result: [pending]

### 2. CR-01 fix verification
expected: After applying the `_WINDOW_SIZE` fix in `gatekeeper.py`, a mock LLM response ending with `[TRIGGER_HARNESS]` followed by 9+ trailing spaces does NOT leak the sentinel to the client. The sentinel is cleanly stripped and `harness_engine` fires.
result: [pending]

### 3. Locked PlanPanel visual + tooltip
expected: When a harness run is active, PlanPanel renders in locked variant: Lock icon visible next to harness type label, Cancel button present and opens confirmation dialog, phase steps are read-only with no mutation controls. Design spec L107-117.
result: [pending]

## Summary

total: 3
passed: 0
issues: 0
pending: 3
skipped: 0
blocked: 0

## Gaps
