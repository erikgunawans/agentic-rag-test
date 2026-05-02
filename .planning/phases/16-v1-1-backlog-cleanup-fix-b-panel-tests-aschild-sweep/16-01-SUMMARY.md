---
phase: 16-v1-1-backlog-cleanup-fix-b-panel-tests-aschild-sweep
plan: 01
status: completed
completed: 2026-05-02
---

# Summary — Plan 16-01: Configurable PII Domain-Term Deny List (REDACT-01)

## What Was Done

Added runtime-configurable domain-term deny list to prevent PII false-positives:

- **`supabase/migrations/037_pii_domain_deny_list_extra.sql`** — new `pii_domain_deny_list_extra TEXT NOT NULL DEFAULT ''` column on `system_settings`
- **`backend/app/services/redaction/detection.py`** — `_parse_extras_csv()` + `_get_active_deny_list()` with 60s TTL cache; `_is_domain_term()` now reads from cached union of baked-in `_DENY_LIST_CASEFOLD` + runtime extras
- **`backend/tests/unit/test_detection_domain_deny_list.py`** — 3 regression tests covering empty extras (fallback), single extra, and multi-value CSV

## Key Decisions

- Zero-regression invariant (D-P16-02): when `pii_domain_deny_list_extra` is empty string (default), behavior is byte-identical to pre-16-01 detection
- Migration 037 applied to Supabase production (`supabase db push --linked`) — `pii_domain_deny_list_extra` column live
- Lazy import of `system_settings_service` to avoid circular import with the redaction subsystem

## Requirements Covered

- **REDACT-01** ✅ — Domain-term deny list now configurable via admin UI / system_settings
