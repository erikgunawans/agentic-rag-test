---
status: partial
phase: 08-llm-tool-integration-discovery
source: [08-VERIFICATION.md]
started: 2026-05-01T00:00:00Z
updated: 2026-05-01T00:00:00Z
---

## Current Test

[awaiting human testing]

## Tests

### 1. End-to-end chat with skill catalog and load_skill tool
expected: LLM receives skill catalog in system prompt; calling load_skill returns skill details with file list
result: [pending]

### 2. File upload/download against live Supabase Storage
expected: POST upload succeeds (201), GET content returns correct bytes, DELETE removes file (204)
result: [pending]

### 3. 10 MB 413 enforcement
expected: Uploading file >10 MB to /skills/{id}/files returns HTTP 413 before any storage write
result: [pending]

### 4. Cross-user RLS enforcement
expected: User 2 blocked from upload/delete on User 1's private skills; User 2 CAN read global skill files
result: [pending]

## Summary

total: 4
passed: 0
issues: 0
pending: 4
skipped: 0
blocked: 0

## Gaps
