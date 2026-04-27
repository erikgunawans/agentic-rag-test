---
phase: 04-fuzzy-de-anonymization-missed-pii-scan-prompt-guidance
plan: 05
subsystem: redaction.prompt_guidance
tags: [pii, system-prompt, prompt-engineering, surrogate-preservation, D-79, D-80, D-81, D-82]
requires:
  - prompt_guidance.py module exists alongside honorifics.py / nicknames_id.py / gender_id.py
  - settings.pii_redaction_enabled (Phase 1)
  - SYSTEM_PROMPT (chat.py)
  - 4 AgentDefinition blocks (agent_service.py)
provides:
  - get_pii_guidance_block(*, redaction_enabled: bool) -> str (single source of truth)
  - _GUIDANCE_BLOCK module constant containing the verbatim D-82 block
  - chat.py single-agent path appends guidance to SYSTEM_PROMPT (D-79)
  - All 4 AgentDefinition.system_prompt strings carry _PII_GUIDANCE suffix at module-import time (D-79)
affects:
  - Single-agent chat completions: system message now includes ~150-token D-82 block when redaction_enabled
  - Multi-agent path (orchestrator + 4 sub-agents): each AgentDefinition prompt extended at import time
  - Phase 5 swap point: replace `settings.pii_redaction_enabled` source with per-thread flag
tech-stack:
  added: []
  patterns:
    - "Module-import-time binding for AgentDefinition fields (existing pattern: tool_names, max_iterations)"
    - "Keyword-only signature on small focused helpers (defensive: prevents bool-arg confusion)"
key-files:
  created:
    - backend/app/services/redaction/prompt_guidance.py (47 lines)
    - backend/tests/unit/test_prompt_guidance.py (94 lines)
  modified:
    - backend/app/routers/chat.py (1 import + 4-line splice in single-agent message-build site)
    - backend/app/services/agent_service.py (2 imports + module-level _PII_GUIDANCE + `+ _PII_GUIDANCE` suffix on 4 system_prompt blocks)
decisions:
  - D-79 (single source of truth across main + sub agents) — IMPLEMENTED
  - D-80 (conditional injection: empty when redaction off) — IMPLEMENTED
  - D-81 (English-only phrasing) — IMPLEMENTED
  - D-82 (verbatim block with imperatives + type list + [TYPE] warning + examples) — IMPLEMENTED
metrics:
  duration_minutes: 11
  completed_date: 2026-04-27
  tasks_completed: 3
  tests_added: 11
  tests_passing: 105 (94 prior backend tests + 11 new prompt_guidance tests)
---

# Phase 4 Plan 5: Prompt Guidance Helper and Wiring — Summary

**One-liner:** Centralized `get_pii_guidance_block` helper exposes the verbatim D-82 surrogate-preservation block; `chat.py` (single-agent) and 4 sub-agents (`agent_service.py`) consume it via the same API, gated on `settings.pii_redaction_enabled`.

## Outcome

ROADMAP SC#5 ("main-agent system prompt instructs the LLM to reproduce names, emails, phones, locations, dates, and URLs verbatim") is now wired end-to-end at the prompt layer. Phase 5 will swap the gating boolean from `settings.pii_redaction_enabled` to a per-thread flag without touching the helper or the call sites.

## What shipped

### NEW: `backend/app/services/redaction/prompt_guidance.py` (47 lines)
- Module docstring (D-79..D-82 mapping, English-only rationale, imperative-phrasing warning).
- `_GUIDANCE_BLOCK` module-level constant — verbatim D-82 string (imperative rules + 7-type sample list + `[TYPE]` warning + 2 arrow-form examples).
- `def get_pii_guidance_block(*, redaction_enabled: bool) -> str` — keyword-only; returns `""` when off, `_GUIDANCE_BLOCK` when on.
- Zero logging, zero async, zero I/O — pure function.

### MODIFIED: `backend/app/routers/chat.py`
- Line 12 (import): `from app.services.redaction.prompt_guidance import get_pii_guidance_block`.
- Lines 215-227 (single-agent message-build site): new local `pii_guidance` computed from `settings.pii_redaction_enabled` and concatenated onto `SYSTEM_PROMPT` in the system message.
- Multi-agent path unchanged — guidance flows in via `agent_def.system_prompt` (already extended at module import).

### MODIFIED: `backend/app/services/agent_service.py`
- Lines 5-6 (imports): `from app.config import get_settings` + `from app.services.redaction.prompt_guidance import get_pii_guidance_block`.
- Lines 12-15: module-level `_PII_GUIDANCE = get_pii_guidance_block(redaction_enabled=get_settings().pii_redaction_enabled)`.
- 4 splice points (one per AgentDefinition.system_prompt): `+ _PII_GUIDANCE` appended.
  - RESEARCH_AGENT (system_prompt at line 20)
  - DATA_ANALYST_AGENT (system_prompt at line 38)
  - GENERAL_AGENT (system_prompt at line 58)
  - EXPLORER_AGENT (system_prompt at line 73)

### NEW: `backend/tests/unit/test_prompt_guidance.py` (94 lines, 11 tests, all green)
- `TestD80_ConditionalInjection` (3 tests) — empty when off, populated when on, block ≥ 500 chars.
- `TestD82_BlockContent` (6 tests) — imperatives, CRITICAL marker, all 7 type-list samples, `[CREDIT_CARD]`/`[US_SSN]`/literal-placeholder warning, arrow-form examples (Marcus Smith / M. Smith), no soft "please" language.
- `TestKeywordOnlySignature` (1 test) — `get_pii_guidance_block(True)` raises `TypeError`.
- `TestD81_EnglishOnly` (1 test) — English instruction keywords present.

## Agent-naming reconciliation (PATTERNS vs CONTEXT)

PATTERNS.md said the agent set is "Research, Data Analyst, General, Explorer"; CONTEXT.md said "General, Research, Compare, Compliance". **Truth on the ground:** PATTERNS.md is correct. The four `AgentDefinition` instances actually present in `backend/app/services/agent_service.py` are `RESEARCH_AGENT`, `DATA_ANALYST_AGENT`, `GENERAL_AGENT`, `EXPLORER_AGENT`. CONTEXT.md's naming was aspirational/stale. All 4 received the `+ _PII_GUIDANCE` suffix. Recorded here so Phase 5+ planners see the live registry.

## must_haves coverage

| must_have | Status |
|---|---|
| `get_pii_guidance_block(*, redaction_enabled)` exposed (D-79/D-80) | DONE |
| Helper returns block when True, empty when False (D-80) | DONE — verified by `test_disabled_returns_empty` / `test_enabled_returns_block` |
| `_GUIDANCE_BLOCK` contains imperatives + type list + `[TYPE]` warning + 2 examples (D-82) | DONE — 6 content tests pin specifics |
| English-only single source of truth (D-81) | DONE |
| `chat.py` imports helper and gates on `settings.pii_redaction_enabled` | DONE (lines 12, 218-227) |
| `agent_service.py` imports + module-level `_PII_GUIDANCE` + 4 suffixes | DONE |
| Unit tests cover D-79/D-80/D-82 | DONE (11 tests, 4 classes) |

All 4 key_links present:
- `grep -c 'from app.services.redaction.prompt_guidance import get_pii_guidance_block' backend/app/routers/chat.py` = 1.
- `grep -c 'from app.services.redaction.prompt_guidance import get_pii_guidance_block' backend/app/services/agent_service.py` = 1.
- `grep -c '^_PII_GUIDANCE' backend/app/services/agent_service.py` = 1.
- `grep -c '+ _PII_GUIDANCE' backend/app/services/agent_service.py` = 4.

## Threat model coverage

| Threat | Disposition | Outcome |
|---|---|---|
| T-04-05-1 — block reveals PII strategy | accept | Block uses fabricated examples; describes surrogate-preservation generically |
| T-04-05-2 — prompt injection (user override) | mitigate | D-82 imperative MUST/NEVER + system-message placement + dual coverage with `[TYPE]` placeholders |
| T-04-05-3 — guidance injected when off | mitigate | `test_disabled_returns_empty` pins D-80 |
| T-04-05-4 — sub-agent prompt drift (import-time binding) | accept | Per PATTERNS.md, all AgentDefinition fields are import-time-bound; v1.0 toggle is deploy-time |

No new threat surface introduced.

## Verification

- `python -m py_compile backend/app/services/redaction/prompt_guidance.py` — clean.
- `python -c "from app.main import app"` — clean.
- `pytest tests/unit/test_prompt_guidance.py -v` — 11/11 PASS.
- `pytest tests/unit/` — 62/62 PASS (51 prior + 11 new).
- `pytest tests/` — 94/94 PASS (no regression; baseline before this plan was 79; the 15-test delta corresponds to Wave-1 plans 04-01..04-04 already merged on master).
- Defensive structural check: `python -c "...vars(agent_service)..."` confirms 4 agents, all suffixed correctly.

## Commits

| Hash | Subject |
|---|---|
| `f60365d` | `feat(04-05): add prompt_guidance helper for surrogate preservation (D-79/D-80/D-81/D-82)` |
| `214f609` | `feat(04-05): wire prompt_guidance into chat.py and 4 sub-agents (D-79)` |
| `015791f` | `test(04-05): add unit tests for prompt_guidance helper (D-79/D-80/D-81/D-82)` |

## Deviations from Plan

None of consequence.

Two minor doc-only notes (not deviations — neither changed code or behavior):

1. **Agent-naming truth-on-the-ground.** Plan said "PATTERNS.md says Research/Data Analyst/General/Explorer; CONTEXT.md says General/Research/Compare/Compliance — apply suffix to all 4 AgentDefinition instances regardless of name set." The live codebase matches PATTERNS.md exactly: `RESEARCH_AGENT`, `DATA_ANALYST_AGENT`, `GENERAL_AGENT`, `EXPLORER_AGENT`. All 4 suffixed. Recorded in this SUMMARY for Phase 5 planners.

2. **Baseline test count.** Plan said "79/79 Phase 1+2+3 baseline". Live baseline is 94/94 — Wave-1 plans 04-01..04-04 (already merged on master) added 15 tests. After this plan: 105/105 total backend tests (94 prior + 11 new).

## Self-Check: PASSED

Files created exist:
- `backend/app/services/redaction/prompt_guidance.py` — FOUND
- `backend/tests/unit/test_prompt_guidance.py` — FOUND

Files modified contain expected splices:
- `backend/app/routers/chat.py` — `get_pii_guidance_block` import + `SYSTEM_PROMPT + pii_guidance` site — FOUND
- `backend/app/services/agent_service.py` — `_PII_GUIDANCE` constant + 4× `+ _PII_GUIDANCE` suffix — FOUND

Commits exist:
- `f60365d` — FOUND
- `214f609` — FOUND
- `015791f` — FOUND

Test counts:
- New: 11 (test_prompt_guidance.py — all PASS)
- Unit suite total: 62 PASS
- Full backend suite: 94 PASS

Import smoke: `from app.main import app` — clean.
