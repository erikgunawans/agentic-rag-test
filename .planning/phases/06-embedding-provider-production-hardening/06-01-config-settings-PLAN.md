---
plan_id: "06-01"
title: "Add EMBEDDING_PROVIDER + LOCAL_EMBEDDING_BASE_URL settings; flip llm_provider_fallback_enabled default to true"
phase: "06-embedding-provider-production-hardening"
plan: 1
type: execute
wave: 1
depends_on: []
autonomous: true
files_modified:
  - backend/app/config.py
requirements: [EMBED-01, EMBED-02, PERF-04]
must_haves:
  truths:
    - "Settings.embedding_provider attribute exists and defaults to 'cloud'"
    - "Settings.local_embedding_base_url attribute exists and defaults to ''"
    - "Settings.llm_provider_fallback_enabled defaults to True (was False per Phase 3 D-52)"
    - "Off-mode (PII_REDACTION_ENABLED=false) byte-identical behavior preserved (SC#5 invariant — config-only change)"
    - "No new migration introduced (D-P6-01: env-var only, no system_settings column)"
  artifacts:
    - path: "backend/app/config.py"
      provides: "Two new settings (embedding_provider, local_embedding_base_url) + one default flip (llm_provider_fallback_enabled)"
      contains: "embedding_provider"
  key_links:
    - from: "backend/app/services/embedding_service.py (Plan 06-03)"
      to: "settings.embedding_provider, settings.local_embedding_base_url"
      via: "get_settings() lookup"
      pattern: "settings\\.embedding_provider"
    - from: "backend/app/services/redaction_service.py:1136 + 1148"
      to: "settings.llm_provider_fallback_enabled"
      via: "fuzzy de-anon LLM-mode soft-fail branch"
      pattern: "settings\\.llm_provider_fallback_enabled"
threat_model:
  - id: "T-06-01-1"
    description: "T-3 (per CONTEXT planning_context security_considerations): flipping llm_provider_fallback_enabled default to true means a deploy with broken primary provider silently falls back to algorithmic clustering (loss of PERF-04 LLM resolution quality is masked)"
    mitigation: "Existing fallback log paths in redaction_service.py and missed_scan.py already emit logger.info / logger.warning when fallback fires. Plan 06-06 adds thread_id field to llm_provider call logs; Plan 06-08 asserts these logs fire. Admins retain DB-toggle override via system_settings.llm_provider_fallback_enabled."
    severity: "medium"
  - id: "T-06-01-2"
    description: "Local-embedding endpoint uses raw text via deployer-supplied base_url, bypassing cloud egress controls (by design per EMBED-02)"
    mitigation: "Cloud is default; local is opt-in via env var. Document the trade-off in CLAUDE.md (Plan 06-08 verification step). No code mitigation needed — this is the intended behavior."
    severity: "low"
---

<objective>
Add the two Phase 6 embedding-provider env-var-backed settings to `Settings` and flip the `llm_provider_fallback_enabled` default to True (per D-P6-09).

Purpose: Phase 6 deliverables 1 (EMBED-01/02 switch) and 3 (PERF-04 fallback default) both require these `Settings` fields to exist before any consumer (Plan 06-03 embedding service, Plan 06-08 tests) can reference them. This is the foundation plan — pure additive `config.py` edit, no migration, no admin UI.

Output: `backend/app/config.py` with two new fields and one changed default.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phases/06-embedding-provider-production-hardening/06-CONTEXT.md
@.planning/phases/03-entity-resolution-llm-provider-configuration/03-CONTEXT.md
@backend/app/config.py
@CLAUDE.md

<interfaces>
<!-- Existing Settings fields the new ones mirror. Extracted from backend/app/config.py. -->

```python
# Phase 3: Endpoints + creds (D-50, D-58)
local_llm_base_url: str = "http://localhost:1234/v1"
local_llm_model: str = "llama-3.1-8b-instruct"
cloud_llm_base_url: str = "https://api.openai.com/v1"
cloud_llm_model: str = "gpt-4o-mini"
cloud_llm_api_key: str = ""

# Phase 3: global LLM provider + fallback knob
llm_provider: Literal["local", "cloud"] = "local"
llm_provider_fallback_enabled: bool = False  # WILL CHANGE TO True

# Existing embedding model setting (RAG-02)
openai_embedding_model: str = "text-embedding-3-small"
custom_embedding_model: str = ""
```
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Add embedding_provider + local_embedding_base_url settings to Settings class</name>
  <read_first>
    - backend/app/config.py (full file — 124 lines; see existing Settings field placement, particularly around line 53 `custom_embedding_model` and line 75-83 PII section, and lines 91-109 Phase 3 LLM provider section)
    - .planning/phases/06-embedding-provider-production-hardening/06-CONTEXT.md (D-P6-01..04 — env-var only, default cloud, no migration)
  </read_first>
  <files>backend/app/config.py</files>
  <action>
After the existing `custom_embedding_model: str = ""` line (around line 53), add two new fields. Insert these AFTER the `custom_embedding_model` line and BEFORE the `# Tool calling (Module 7)` comment block:

```python
    # Phase 6: Embedding provider switch (EMBED-01, EMBED-02; D-P6-01..D-P6-03)
    # `cloud` (default) preserves the existing OpenAI-embeddings flow (RAG-02 unchanged).
    # `local` uses an OpenAI-API-compatible local endpoint (Ollama bge-m3, nomic-embed-text, LM Studio).
    # NOTE: Switching providers does NOT trigger automatic re-embedding of existing documents
    # (D-P6-04 / EMBED-02 — deployer-managed migration; document only, no code).
    embedding_provider: Literal["local", "cloud"] = "cloud"
    local_embedding_base_url: str = ""  # e.g. "http://localhost:11434/v1" for Ollama
```

Use the same `Literal["local", "cloud"]` type as `llm_provider` (already imported at line 4: `from typing import Literal`).

Default `embedding_provider="cloud"` per D-P6-01 (preserves RAG-02). Default `local_embedding_base_url=""` per D-P6-03 (mirrors the empty-default convention `custom_embedding_model: str = ""`).
  </action>
  <verify>
    <automated>cd backend &amp;&amp; source venv/bin/activate &amp;&amp; python -c "from app.config import get_settings; s = get_settings(); assert s.embedding_provider == 'cloud'; assert s.local_embedding_base_url == ''; print('OK')"</automated>
  </verify>
  <acceptance_criteria>
    - `grep -n "embedding_provider:" backend/app/config.py` returns at least 1 match for the new field
    - `grep -n "local_embedding_base_url:" backend/app/config.py` returns at least 1 match
    - `grep -n 'Literal\["local", "cloud"\]' backend/app/config.py` returns at least 2 matches (existing `llm_provider` plus new `embedding_provider`)
    - `cd backend &amp;&amp; source venv/bin/activate &amp;&amp; python -c "from app.config import get_settings; s = get_settings(); assert hasattr(s, 'embedding_provider') and s.embedding_provider == 'cloud'; assert hasattr(s, 'local_embedding_base_url') and s.local_embedding_base_url == ''; print('OK')"` prints `OK`
    - `cd backend &amp;&amp; python -c "from app.main import app; print('OK')"` prints `OK` (import-check unbroken; D-P6-04 backward-compat invariant)
  </acceptance_criteria>
  <done>Two new env-var-backed settings exist on `Settings`, defaults match D-P6-01/D-P6-03, backend imports cleanly, and the `cd backend && python -c "from app.config import get_settings; s = get_settings(); assert s.embedding_provider == 'cloud' and s.local_embedding_base_url == ''"` smoke check passes.</done>
</task>

<task type="auto">
  <name>Task 2: Flip llm_provider_fallback_enabled default from False to True (D-P6-09)</name>
  <read_first>
    - backend/app/config.py (around line 94 — current `llm_provider_fallback_enabled: bool = False`)
    - .planning/phases/06-embedding-provider-production-hardening/06-CONTEXT.md (D-P6-09 verbatim)
    - .planning/phases/03-entity-resolution-llm-provider-configuration/03-CONTEXT.md (D-52: original default `false`, deferred-but-plumbed cross-provider crossover invariant)
    - backend/app/services/redaction_service.py (lines 1136, 1148 — the two places the knob is read; verify reading is correct after default flip)
    - backend/tests/api/test_phase4_integration.py (lines 65, 81, 587, 598 — test fixtures explicitly set the knob; flipping default does NOT change explicit overrides, but verify these tests still pass after change)
  </read_first>
  <files>backend/app/config.py</files>
  <action>
Locate the existing line in `Settings`:

```python
    llm_provider_fallback_enabled: bool = False
```

Change the default to `True` so the line reads:

```python
    llm_provider_fallback_enabled: bool = True  # Phase 6 D-P6-09: PERF-04 ships fallback ON by default
```

Do NOT touch the per-feature override fields (`entity_resolution_llm_provider`, etc., lines 98-102) — they remain `None`-default.

Do NOT touch `backend/app/routers/admin_settings.py` line 34 (`llm_provider_fallback_enabled: bool | None = None`) — that is the SystemSettingsUpdate schema's None-as-unset contract, which is independent of the env-var default.

Do NOT modify `backend/tests/api/test_phase4_integration.py` — those tests pass `llm_provider_fallback_enabled` explicitly via `_patched_settings`, so the default flip does not affect them.
  </action>
  <verify>
    <automated>cd backend &amp;&amp; source venv/bin/activate &amp;&amp; python -c "from app.config import get_settings; s = get_settings(); assert s.llm_provider_fallback_enabled is True, f'expected True, got {s.llm_provider_fallback_enabled!r}'; print('OK')"</automated>
  </verify>
  <acceptance_criteria>
    - `grep -nE "llm_provider_fallback_enabled:\s*bool\s*=\s*True" backend/app/config.py` returns exactly 1 match
    - `grep -nE "llm_provider_fallback_enabled:\s*bool\s*=\s*False" backend/app/config.py` returns 0 matches (default flipped, not duplicated)
    - `cd backend &amp;&amp; source venv/bin/activate &amp;&amp; python -c "from app.config import get_settings; s = get_settings(); assert s.llm_provider_fallback_enabled is True; print('OK')"` prints `OK`
    - `cd backend &amp;&amp; python -c "from app.main import app; print('OK')"` prints `OK`
  </acceptance_criteria>
  <done>The knob defaults to True; `s.llm_provider_fallback_enabled is True` smoke check passes; backend still imports cleanly.</done>
</task>

</tasks>

<verification>
Phase-level checks the executor runs after both tasks:

1. `cd backend && source venv/bin/activate && python -c "from app.config import get_settings; s = get_settings(); assert s.embedding_provider == 'cloud' and s.local_embedding_base_url == '' and s.llm_provider_fallback_enabled is True; print('OK')"` — all three new/changed defaults verified in one shot.

2. `cd backend && python -c "from app.main import app; print('OK')"` — backend import-check unbroken (PostToolUse hook also runs this on every .py edit).

3. `cd backend && source venv/bin/activate && pytest tests/unit -v --tb=short -q 2>&1 | tail -20` — existing 195+ unit tests still pass (default-flip regression check; explicit-override tests in test_phase4_integration.py are unaffected because they set the knob explicitly via `_patched_settings`).
</verification>

<success_criteria>
- Settings has two new fields (`embedding_provider`, `local_embedding_base_url`) with the documented defaults
- `llm_provider_fallback_enabled` default is now True
- Backend imports cleanly
- All pre-existing unit tests still pass
- No migration files added (D-P6-01 invariant)
</success_criteria>

<output>
After completion, create `.planning/phases/06-embedding-provider-production-hardening/06-01-SUMMARY.md` documenting:
- The exact new lines added to `config.py` (verbatim)
- The line whose default flipped
- Smoke-check outputs
- Confirmation no migration was added (so Plan 06-08's `find backend/migrations -newer ...` gate would find zero new migration files)
</output>
