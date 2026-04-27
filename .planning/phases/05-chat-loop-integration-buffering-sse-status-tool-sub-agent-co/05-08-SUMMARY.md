---
phase: 05-chat-loop-integration-buffering-sse-status-tool-sub-agent-co
plan: "08"
subsystem: pii-redaction-admin-toggle
tags: [pii-redaction, admin-settings, db-migration, gap-closure, system-settings]
dependency_graph:
  requires: []
  provides: [pii_redaction_enabled DB column, admin toggle endpoint, system_settings toggle source]
  affects: [chat.py, redaction_service.py, agent_service.py, admin_settings.py, config.py]
tech_stack:
  added: []
  patterns: [system_settings single-row pattern, DB-backed feature flag, 60s cache TTL toggle]
key_files:
  created:
    - supabase/migrations/032_pii_redaction_enabled_setting.sql
  modified:
    - backend/app/routers/admin_settings.py
    - backend/app/routers/chat.py
    - backend/app/services/redaction_service.py
    - backend/app/services/agent_service.py
    - backend/app/config.py
    - backend/tests/api/test_phase5_integration.py
    - backend/tests/unit/test_redaction_service_d84_gate.py
    - backend/tests/unit/test_redact_text_batch.py
    - backend/tests/unit/test_agent_service_classify_intent_egress.py
    - backend/tests/unit/test_chat_router_phase5_wiring.py
    - CLAUDE.md
decisions:
  - "D-83-toggle: pii_redaction_enabled moved from config.py env var to system_settings DB column; admin-toggleable without Railway redeploy"
  - "D-84-gate-source: D-84 service-layer gate and chat-router gate both read from get_system_settings() to maintain lock-step invariant"
  - "agent_service-fix: agent_service.py classify_intent gate and _PII_GUIDANCE binding also switched to system_settings (Rule 1 deviation — would break when config.py field removed)"
metrics:
  duration: "~25 minutes"
  completed: "2026-04-28"
  tasks_completed: 7
  files_changed: 11
---

# Phase 05 Plan 08: pii_redaction_enabled DB-Backed Admin Toggle Summary

**One-liner:** Migrated `pii_redaction_enabled` from a config.py env-var hardcoded `True` to a DB-backed `system_settings` column (migration 032) so admins can toggle PII redaction without a Railway redeploy.

## What Was Built

### Migration 032
Added `pii_redaction_enabled BOOLEAN NOT NULL DEFAULT TRUE` column to `system_settings` table. Applied to production Supabase `qedhulpfezucnfadlfiz` via Supabase CLI `--linked`. Verified with `SELECT pii_redaction_enabled FROM system_settings WHERE id = 1` → `true`.

### Admin API (admin_settings.py)
Added `pii_redaction_enabled: bool | None = None` to `SystemSettingsUpdate` Pydantic model. `GET /admin/settings` already returns `SELECT *` so the new column auto-flows through. `PATCH /admin/settings` now accepts the field and writes it to DB.

### Chat Router (chat.py)
Changed `redaction_on = settings.pii_redaction_enabled` → `redaction_on = bool(sys_settings.get("pii_redaction_enabled", True))`. Uses the already-loaded `sys_settings` dict (single per-turn read, no extra DB hit). Also updated the `pii_guidance` block in the single-agent path to use the local `redaction_on` variable instead of `settings.pii_redaction_enabled`.

### Redaction Service (redaction_service.py)
Both D-84 early-return gates switched from `get_settings().pii_redaction_enabled` to `bool(get_system_settings().get("pii_redaction_enabled", True))`. Added `from app.services.system_settings_service import get_system_settings` import.

### Config Cleanup (config.py)
Removed `pii_redaction_enabled: bool = True` field. Added inline comment noting it moved to `system_settings` (migration 032). `extra="ignore"` confirmed in `SettingsConfigDict`, so any lingering `PII_REDACTION_ENABLED` env var is silently ignored.

### Test Migration (7 files)
Switched all test patches from `app.services.redaction_service.get_settings` and `settings.pii_redaction_enabled` to `app.services.redaction_service.get_system_settings` returning a system_settings dict. Phase5 integration tests updated with `_MOCK_SYS_SETTINGS_OFF` variant for SC#5 off-mode tests. Wiring assertion in `test_chat_router_phase5_wiring.py` updated to check `sys_settings.get("pii_redaction_enabled"` pattern.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed agent_service.py pii_redaction_enabled references**
- **Found during:** Task 5 (scanning all references before removing config.py field)
- **Issue:** `agent_service.py` had `get_settings().pii_redaction_enabled` at two sites: module-level `_PII_GUIDANCE` binding (line 21) and per-request classify_intent gate (line 185). Removing the field from config.py without fixing these would cause `AttributeError` at runtime.
- **Fix:** Added `from app.services.system_settings_service import get_system_settings` import; switched both sites to `bool(get_system_settings().get("pii_redaction_enabled", True))`.
- **Files modified:** `backend/app/services/agent_service.py`
- **Commit:** `009dd26`

**2. [Rule 3 - Blocking] No Supabase MCP tool in worktree context**
- **Found during:** Task 2 (applying migration)
- **Issue:** The plan specified using `mcp__claude_ai_Supabase__apply_migration` but MCP tools are not available in this agent's tool list. The project `.mcp.json` doesn't include the Supabase MCP server (only context7, playwright, graphify).
- **Fix:** Used `npx supabase@latest link --project-ref qedhulpfezucnfadlfiz` then `npx supabase@latest db query --linked -f supabase/migrations/032_pii_redaction_enabled_setting.sql`. Verified with `db query --linked "SELECT pii_redaction_enabled FROM system_settings WHERE id = 1;"`.
- **Outcome:** Migration applied successfully; column returns `true`.

## Known Stubs

None. All toggle reads are wired to live `get_system_settings()` (60s cache TTL) which returns the production DB value.

## Threat Flags

No new network endpoints or auth paths introduced. The `pii_redaction_enabled` field inherits the existing `require_admin` RBAC gate on `PATCH /admin/settings` (T-05-08-1 mitigation in plan threat model). No new trust boundaries.

## Operator Cleanup Note

The `PII_REDACTION_ENABLED` env var in Railway is now a no-op (silently ignored by pydantic-settings `extra="ignore"`). It should be cleaned up from Railway environment variables to avoid confusion, but it poses no functional or security risk in its current state.

## Self-Check

Files created:
- supabase/migrations/032_pii_redaction_enabled_setting.sql: FOUND
- .planning/phases/05-chat-loop-integration-buffering-sse-status-tool-sub-agent-co/05-08-SUMMARY.md: BEING CREATED

Test results:
- 14/14 phase5 integration tests pass
- 58/58 unit tests (across 4 files) pass
- 72/72 plan-related tests pass
- 4 pre-existing failures in test_llm_provider_client.py (unrelated; caused by plan 05-07's egress_filter canonicals() change, stub not updated — out of scope)

Commits:
- f899fc6: feat(05-08): add migration 032 for pii_redaction_enabled system_settings column
- ae8387f: feat(05-08): apply migration 032 to production Supabase
- 1143d20: feat(05-08): expose pii_redaction_enabled in SystemSettingsUpdate admin model
- 1bf96cb: feat(05-08): switch chat.py redaction toggle to system_settings DB source
- 009dd26: feat(05-08): switch redaction_service.py D-84 gate to system_settings DB source
- 52c4030: feat(05-08): remove deprecated pii_redaction_enabled from config.py
- 8fa77a2: test(05-08): migrate pii_redaction_enabled patches to system_settings

Backend import check:
- python -c "from app.main import app; print('OK')" → OK

## Self-Check: PASSED
