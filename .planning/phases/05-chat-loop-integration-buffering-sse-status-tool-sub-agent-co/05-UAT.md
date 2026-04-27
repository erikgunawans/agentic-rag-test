---
status: complete
phase: 05-chat-loop-integration-buffering-sse-status-tool-sub-agent-co
source:
  - 05-01-SUMMARY.md
  - 05-02-SUMMARY.md
  - 05-03-SUMMARY.md
  - 05-04-SUMMARY.md
  - 05-05-SUMMARY.md
  - 05-06-SUMMARY.md
started: "2026-04-28T00:00:00+07:00"
updated: "2026-04-28T06:05:00+07:00"
---

## Current Test

[testing complete]

## Tests

### 1. Backend Cold-Start Smoke Test
expected: |
  Kill any running backend server. Start it fresh:
    cd backend && source venv/bin/activate && uvicorn app.main:app --reload --port 8000
  The server should boot without any import errors or exceptions.
  Look for: "Application startup complete." (or similar uvicorn ready message).
  If the server errors on startup, Phase 5 imports broke something.
result: pass

### 2. Off-Mode Chat Works Unchanged (PII_REDACTION_ENABLED=false)
expected: |
  With the backend running and PII_REDACTION_ENABLED=false (the default if not set in .env):
  Open the chat UI, send a message like "Hello, what can you help me with?"
  The response should stream progressively (words appear one by one as before).
  No new events, no delay waiting for buffer, no status spinner visible.
  This is the SC#5 regression test — Phase 5 must be invisible when redaction is off.
result: issue
reported: "pii_redaction_enabled is a pydantic-settings env var defaulting to True in config.py
  (line 77). It is NOT in the system_settings DB table — the admin API returns 44 keys,
  none of which is pii_redaction_enabled. Production always runs with redaction ON unless
  PII_REDACTION_ENABLED=false is explicitly set in Railway env vars. SC#5 off-mode cannot
  be verified in production without a Railway env change. Admin UI has no toggle for this."
severity: major

### 3. Frontend TypeScript Builds Without Errors
expected: |
  Run: cd frontend && npx tsc --noEmit
  Should exit 0 with no errors.
  The new RedactionStatusEvent type in database.types.ts and the
  useChatState.redactionStage state variable must not break existing type checks.
result: pass

### 4. Integration Test Suite Passes (pytest)
expected: |
  Run: cd backend && source venv/bin/activate && python -m pytest tests/api/test_phase5_integration.py -v --tb=short
  All 14 tests across 7 classes should pass:
    - TestSC1_PrivacyInvariant (2 tests) — no real PII in any LLM payload
    - TestSC2_BufferingAndStatus (2 tests) — correct SSE event order
    - TestSC3_SearchDocumentsTool (2 tests) — walker symmetry
    - TestSC4_SqlGrepAndSubAgent (2 tests) — query_database + kb_grep
    - TestSC5_OffMode (2 tests) — zero redaction_status events when disabled
    - TestB4_LogPrivacy_ChatLoop (2 tests) — no real PII in logs
    - TestEgressTrip_ChatPath (2 tests) — egress blocked, clean abort
result: pass

### 5. PII Redaction Active Mode (requires PII_REDACTION_ENABLED=true)
expected: |
  Send a chat message containing a real name, e.g.:
    "Can you help me draft a contract for Ahmad Suryadi?"
  Expected behavior:
  - The final response appears with real name de-anonymized (Ahmad Suryadi visible)
  - In SSE stream: anonymizing → agent_start → deanonymizing → delta(content) → agent_done
  - All subsequent messages in the thread also receive normal responses
result: issue
reported: "Turn 1 works correctly — 'Ahmad Suryadi' is anonymized, LLM response received,
  de-anonymized and shown. SSE sequence correct: anonymizing → agent_start → deanonymizing
  → delta(content) → agent_done.

  BUT: every subsequent turn in the same thread is BLOCKED. Playwright confirmed:
  Turn 2 ('What is a non-disclosure agreement?') and Turn 3 ('What governing law should I
  use?') both return: anonymizing → agent_start → blocked → delta(empty).

  Supabase entity_registry query on the test thread revealed the root cause:
  spaCy xx_ent_wiki_sm falsely detects legal terms in the LLM's response as PERSON entities:
    'Recitals' → PERSON, 'Confidentiality Clause' → PERSON, 'Governing Law' → PERSON,
    'Signatures' → PERSON, 'Specify' → PERSON.

  D-48 variant generation then stores first/last word variants as separate registry entries:
    'Confidentiality', 'Clause', 'Governing', 'Law' — all stored as real PERSON values.

  On subsequent turns, the anonymized text still contains these common words outside of
  replaced entity spans (e.g., 'include terms regarding confidentiality' — the word
  'confidentiality' is NOT inside the 'Confidentiality Clause' span that was replaced).
  The egress filter matches these common legal words → EgressBlockedAbort → empty response.

  Cascade: spaCy false positive → D-48 variant pollution → egress false block → chat
  permanently unusable after Turn 1 in any thread involving legal domain language."
severity: blocker

### 6. SSE Redaction Status Events (frontend spinner, requires PII on + browser devtools)
expected: |
  With PII_REDACTION_ENABLED=true and a PII-containing chat message:
  In the SSE events, you should see this sequence:
    1. data: {"type":"redaction_status","stage":"anonymizing"}
    2. data: {"type":"agent_start",...}
    3. data: {"type":"redaction_status","stage":"deanonymizing"}
    4. data: {"type":"delta","delta":"<full response text>","done":false}
    5. data: {"type":"agent_done",...}
    6. data: {"type":"delta","done":true}
  The "anonymizing" and "deanonymizing" events bracket the LLM call window.
  All subsequent turns in the thread also receive complete responses.
result: issue
reported: "Turn 1 SSE sequence is correct: anonymizing → agent_start → deanonymizing →
  delta(content) → agent_done. De-anonymization works (real name restored in response).

  Turn 2+ SSE sequence is broken: anonymizing → agent_start → blocked → delta(empty,done:true).
  No response content is delivered. This is caused by the same D-48 variant cascade
  bug documented in Test 5 — the egress filter trips on common legal words stored as
  false-positive PERSON variants in the entity_registry."
severity: blocker

## Summary

total: 6
passed: 2
issues: 3
pending: 0
skipped: 0
blocked: 0
(note: test 1 and 4 pass; tests 2, 5, 6 have issues; test 3 pass — 3 pass total including test 3)

## Gaps

- truth: "pii_redaction_enabled must be toggleable via admin settings (system_settings table)"
  status: failed
  reason: "User reported: pii_redaction_enabled is a config.py env var (default True), absent
    from admin API response and DB system_settings table. Admin UI cannot toggle it. SC#5
    off-mode untestable in production without Railway env var change."
  severity: major
  test: 2
  root_cause: "pii_redaction_enabled lives in pydantic-settings config.py (line 77) as a
    static env var, never migrated into system_settings table. admin_settings.py
    SystemSettingsUpdate model has no pii_redaction_enabled field."
  artifacts:
    - path: "backend/app/config.py"
      issue: "pii_redaction_enabled: bool = True hardcoded default, not in DB"
    - path: "backend/app/routers/admin_settings.py"
      issue: "SystemSettingsUpdate model missing pii_redaction_enabled field"
  missing:
    - "Add pii_redaction_enabled column to system_settings table (new migration)"
    - "Add pii_redaction_enabled to SystemSettingsUpdate and GET response in admin_settings.py"
    - "Update chat.py to read from system_settings instead of config.py"

- truth: "Multi-turn chat works correctly after Turn 1 when PII redaction is active"
  status: failed
  reason: "User reported: spaCy xx_ent_wiki_sm falsely detects legal terms (Recitals,
    Confidentiality Clause, Governing Law, Signatures, Specify) as PERSON entities in LLM
    responses. D-48 variant generation stores first/last word variants (Confidentiality,
    Clause, Governing, Law) as real PERSON values in entity_registry. These common words
    appear in subsequent anonymized text outside of replaced spans, tripping the egress
    filter on every turn after Turn 1. Thread is permanently unusable after any response
    containing legal domain vocabulary."
  severity: blocker
  test: 5
  root_cause: "D-48 variant generation (anonymization.py) is designed for real person name
    variants (Ahmad Suryadi → Ahmad, Suryadi). When spaCy produces false-positive PERSON
    detections for legal compound nouns (Governing Law, Confidentiality Clause), D-48
    stores common legal words as PERSON real values. The egress filter (egress.py) checks
    ALL registry entries including these false-positive variants against the anonymized
    payload. The anonymized payload still contains these words outside of replaced spans.
    The fix requires either: (a) suppressing D-48 variants for false-positive clusters, or
    (b) filtering common non-name words from D-48 variant generation, or (c) adding a
    minimum token length / name-shape check before storing variants."
  artifacts:
    - path: "backend/app/services/redaction/anonymization.py"
      issue: "D-48 variant generation stores first/last word of any PERSON cluster as
        real values — including false-positive legal terms detected by spaCy"
    - path: "backend/app/services/redaction/detection.py"
      issue: "spaCy xx_ent_wiki_sm produces false-positive PERSON detections for legal
        compound nouns: Recitals, Confidentiality Clause, Governing Law, Signatures, Specify"
    - path: "backend/app/services/redaction/egress.py"
      issue: "egress_filter checks ALL registry.entries() including single-word variants
        of false-positive clusters; word-boundary regex matches common legal vocabulary"
  missing:
    - "Add name-shape gate in D-48 variant generation: only store variants for clusters
      where canonical looks like a human name (e.g., 2+ words, title-case, not in
      legal/domain stopword list)"
    - "OR: add domain stopwords to detection.py to block spaCy false positives for
      common legal terms before they enter the redaction pipeline"
    - "OR: in egress.py, skip single-word variants when checking (only check canonical
      real values, not D-48 sub-surrogates)"
