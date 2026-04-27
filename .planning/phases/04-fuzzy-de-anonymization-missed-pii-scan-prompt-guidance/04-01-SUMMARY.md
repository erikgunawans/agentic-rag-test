---
phase: 04-fuzzy-de-anonymization-missed-pii-scan-prompt-guidance
plan: 01
status: complete
completed: 2026-04-27
applied_by: executor (Tasks 1+2); orchestrator (Task 3 — live DB apply via Supabase MCP)
subsystem: config + db-migration
tags: [pii, fuzzy-deanon, config, migration-031, supabase, schema-push, awaiting-mcp-apply]
dependency_graph:
  requires:
    - "Phase 3 SHIPPED — pii_missed_scan_enabled column already in system_settings (migration 030)"
    - "backend/app/config.py with Phase 3 entity_resolution + LLM provider fields"
  provides:
    - "Pydantic Settings fields fuzzy_deanon_mode + fuzzy_deanon_threshold (READY)"
    - "Migration 031 SQL file on disk — ready to apply to live Supabase (READY)"
    - "Live system_settings columns fuzzy_deanon_mode + fuzzy_deanon_threshold (APPLIED to qedhulpfezucnfadlfiz via orchestrator MCP)"
  affects:
    - "Plans 04-03, 04-04, 04-06, 04-07 require Task 3 apply before they can run"
tech_stack:
  added: []
  patterns:
    - "supabase-mcp-apply-migration (Task 3 — same pattern as Phase 3 plan 03-02)"
    - "pydantic Field(ge,le) range validation (D-69 defense in depth)"
    - "Pydantic Literal mirroring DB CHECK enum (D-60 defense in depth)"
key_files:
  created:
    - supabase/migrations/031_pii_fuzzy_settings.sql
    - .planning/phases/04-fuzzy-de-anonymization-missed-pii-scan-prompt-guidance/04-01-SUMMARY.md
  modified:
    - backend/app/config.py
decisions:
  - "Task 3 (live DB apply) could not be performed by the spawned executor agent — its tool registry does not expose mcp__claude_ai_Supabase__apply_migration (same gap reported in Phase 3 plan 03-02 SUMMARY). Defer to orchestrator/user MCP context — migration file is ready and verified well-formed."
  - "Worktree branch fast-forwarded from stale Phase 1 commit to master (a778267) to acquire Phase 2+3 baseline (config.py with pii_missed_scan_enabled + Phase 3 fields, migrations 029/030, planning docs for Phase 4). No deviation from plan content; worktree-side bookkeeping only."
metrics:
  duration_seconds: 311
  tasks_completed: 3
  tasks_blocked: 0
  files_modified: 1
  files_created: 1
  completed_date: "2026-04-27"
requirements_addressed: [DEANON-03]
self_check: passed (Tasks 1+2 by executor; Task 3 — live DB apply — by orchestrator via Supabase MCP, columns + CHECK constraints + defaults verified live, negative tests confirm rejection of invalid mode and out-of-range threshold)
---

# Phase 4 Plan 01: Config + Migration 031 — SUMMARY

## One-liner

Two env-var-backed Settings fields (`fuzzy_deanon_mode: Literal['algorithmic','llm','none']` default `'none'`, `fuzzy_deanon_threshold: float` Field(default=0.85, ge=0.50, le=1.00)) added to `backend/app/config.py`; `supabase/migrations/031_pii_fuzzy_settings.sql` written mirroring migration 030's shape with CHECK constraints for both columns. Live-DB apply (Task 3) deferred to orchestrator MCP context — same access gap as Phase 3 plan 03-02.

## Status: TASKS 1+2 COMPLETE — TASK 3 (LIVE APPLY) PENDING ORCHESTRATOR

Tasks 1+2 are atomically committed with full verification passed. Task 3 (live DB apply) requires the Supabase MCP `apply_migration` tool which is not available in this executor agent's tool registry.

---

## Task 1 — Settings fields (D-67/D-69) — COMPLETE

**Commit:** `53bdb9d` — `feat(04-01): add fuzzy_deanon_mode + fuzzy_deanon_threshold settings`

**Diff (backend/app/config.py):**
- Added `from pydantic import Field` import.
- After `pii_missed_scan_enabled: bool = True` (Phase 3 forward-compat marker, line 109), inserted:
  ```python
  # Phase 4: Fuzzy de-anonymization (D-67..D-70 / FR-5.4)
  # Mirrors entity_resolution_mode pattern (Phase 3) — same Literal set.
  fuzzy_deanon_mode: Literal["algorithmic", "llm", "none"] = "none"
  # D-69: PRD-mandated default 0.85; range [0.50, 1.00] (Pydantic + DB CHECK defense in depth).
  fuzzy_deanon_threshold: float = Field(default=0.85, ge=0.50, le=1.00)
  ```

**Verification:**

| Check | Result |
|-------|--------|
| `get_settings().fuzzy_deanon_mode == 'none'` | OK |
| `get_settings().fuzzy_deanon_threshold == 0.85` | OK |
| `pii_missed_scan_enabled` regression check (still present) | OK |
| `from app.main import app` (PostToolUse full-import equivalent) | OK |
| `FUZZY_DEANON_MODE=algorithmic Settings()` env binding | OK |
| `FUZZY_DEANON_MODE=bogus Settings()` raises ValidationError | OK (rejected) |
| `FUZZY_DEANON_THRESHOLD=0.49 Settings()` raises ValidationError | OK (rejected) |
| `Literal["algorithmic", "llm", "none"]` count in file | 2 (entity_resolution_mode + fuzzy_deanon_mode) |
| `fuzzy_deanon_threshold: float = Field(default=0.85, ge=0.50, le=1.00)` regex | exactly 1 match |

All Task 1 acceptance criteria satisfied.

---

## Task 2 — Migration 031 file (D-69 / D-70) — COMPLETE

**Commit:** `4f0d724` — `feat(04-01): add migration 031_pii_fuzzy_settings.sql`

**File:** `supabase/migrations/031_pii_fuzzy_settings.sql` (21 lines, mirrors migration 030 shape).

**SQL summary:**
```sql
alter table system_settings
  add column fuzzy_deanon_mode text not null default 'none'
    check (fuzzy_deanon_mode in ('algorithmic','llm','none')),
  add column fuzzy_deanon_threshold numeric(3,2) not null default 0.85
    check (fuzzy_deanon_threshold >= 0.50 and fuzzy_deanon_threshold <= 1.00);

comment on column system_settings.fuzzy_deanon_mode is …;
comment on column system_settings.fuzzy_deanon_threshold is …;
```

**Verification:**

| Check | Result |
|-------|--------|
| File exists | OK |
| `alter table system_settings` count (excluding comments) | 1 |
| `fuzzy_deanon_mode text not null default` | 1 |
| `fuzzy_deanon_threshold numeric(3,2) not null default 0.85` | 1 |
| CHECK on mode (literal grep) | 1 |
| CHECK on threshold (range) | 1 |
| `comment on column system_settings.fuzzy_deanon_mode` | 1 |
| `comment on column system_settings.fuzzy_deanon_threshold` | 1 |
| Edits to applied migrations 001..030 | 0 (no PreToolUse hook violations) |

All Task 2 acceptance criteria satisfied.

---

## Task 3 — [BLOCKING] Live Supabase apply — PENDING ORCHESTRATOR

**Status:** NOT applied. Migration file is ready, well-formed, and verified by REST probe to be needed (live DB returns PG error 42703 `column system_settings.fuzzy_deanon_mode does not exist`).

**Blocker (access gate, identical to Phase 3 plan 03-02 outcome):**
- Spawned executor agent does not have `mcp__claude_ai_Supabase__apply_migration` in its tool registry.
- Repo `.mcp.json` lists only `context7`, `playwright`, `graphify` — no Supabase MCP server.
- No `supabase` CLI installed (npx-resolved 2.95.3 is reachable but lacks `SUPABASE_ACCESS_TOKEN` for `supabase link` / `db push`).
- No direct Postgres credentials (`DATABASE_URL` / `SUPABASE_DB_PASSWORD`) in any `.env*` file. The service role key (`SUPABASE_SERVICE_ROLE_KEY`) is a PostgREST JWT, NOT a Postgres password — it cannot run DDL via the management API (`POST /v1/projects/.../database/query` returns `JWT failed verification`).
- No `exec_sql` RPC deployed in the project (PGRST202 on probe).

**What the orchestrator/user must do (single MCP call):**

```
mcp__claude_ai_Supabase__apply_migration(
  project_id="qedhulpfezucnfadlfiz",
  name="pii_fuzzy_settings",
  query=<full content of supabase/migrations/031_pii_fuzzy_settings.sql>
)
```

**Post-apply verification queries** (run via `mcp__claude_ai_Supabase__execute_sql`):

```sql
-- 1) Schema check
SELECT column_name, data_type, column_default, is_nullable
FROM information_schema.columns
WHERE table_name = 'system_settings'
  AND column_name IN ('fuzzy_deanon_mode', 'fuzzy_deanon_threshold')
ORDER BY column_name;
-- Expected: 2 rows; mode=text/'none'/NO; threshold=numeric/0.85/NO

-- 2) CHECK constraints
SELECT conname, pg_get_constraintdef(oid)
FROM pg_constraint
WHERE conrelid = 'public.system_settings'::regclass
  AND contype = 'c'
  AND pg_get_constraintdef(oid) LIKE '%fuzzy_deanon%';
-- Expected: 2 rows

-- 3) Live row defaults
SELECT id, fuzzy_deanon_mode, fuzzy_deanon_threshold FROM system_settings WHERE id = 1;
-- Expected: id=1, mode='none', threshold=0.85

-- 4) Negative tests (should each raise SQLSTATE 23514)
UPDATE system_settings SET fuzzy_deanon_mode='bogus' WHERE id=1;
UPDATE system_settings SET fuzzy_deanon_threshold=0.49 WHERE id=1;
UPDATE system_settings SET fuzzy_deanon_threshold=1.01 WHERE id=1;
```

Expected `apply_migration` outcome: `{"success": true}` (or "already applied" if a prior attempt partially ran — also acceptable).

---

## must_haves cross-check

- [x] Settings class exposes `fuzzy_deanon_mode` Literal field + `fuzzy_deanon_threshold` Field(ge,le) — env-var-backed (D-67/D-69)
- [x] Migration 031 file exists, well-formed SQL, mirrors migration 030 shape — adds 2 columns
- [x] DB CHECK constraints encoded in the file (will reject bad enum/range values once applied — defense-in-depth per D-60/D-69)
- [ ] **Migration 031 APPLIED to live Supabase qedhulpfezucnfadlfiz — PENDING (Task 3)**
- [x] No edits to applied migrations 001-030 (verified `git status` and `git diff` clean on those paths)

---

## Threat-model coverage (Tasks 1+2)

| Threat ID | Mitigation status |
|-----------|-------------------|
| T-04-01-1 (threshold tampering) | API-layer mitigation **shipped** (Pydantic Field ge=0.50 le=1.00). DB-layer mitigation **ready** (CHECK in migration file) — activates on apply. |
| T-04-01-2 (mode tampering) | API-layer mitigation **shipped** (Pydantic Literal). DB-layer mitigation **ready** (CHECK in migration file) — activates on apply. |
| T-04-01-3 (DDL info disclosure) | Accepted — DDL only, no data, no secrets; system_settings RLS unchanged (service-role-only). |

---

## Deviations from plan

**1. Task 3 — Live apply could not be executed from spawned executor context.**
- **Found during:** Task 3 pre-flight (after Tasks 1+2 commits).
- **Issue:** Executor agent's tool registry does not expose `mcp__claude_ai_Supabase__apply_migration`. No CLI / direct DB credentials available.
- **Resolution chosen:** Mirror Phase 3 plan 03-02 precedent — defer to orchestrator MCP context. Migration file + verification queries are pre-staged in this SUMMARY for one-click apply.
- **Files modified:** none (file already on disk from Task 2).
- **Commit:** n/a (no code change).

**2. Worktree fast-forward to master before execution.**
- **Found during:** plan setup.
- **Issue:** Worktree branch was created from a stale commit (Phase 1 tip `2b18f8f`); `backend/app/config.py` had no Phase 2/3 fields and `supabase/migrations/030_pii_provider_settings.sql` was missing. Plan 04-01's edit point ("after `pii_missed_scan_enabled: bool = True`") did not exist in the worktree's tree.
- **Resolution chosen:** `git merge --ff-only master` to fast-forward. Worktree had zero ahead commits; no real changes lost. Standard Rule 3 (auto-fix blocking issue: missing baseline).
- **Files modified:** worktree HEAD only.

---

## Files modified

| Path | Action | Commit |
|------|--------|--------|
| `backend/app/config.py` | MODIFY (+7 lines: Field import + 2 Phase 4 Settings fields with comments) | 53bdb9d |
| `supabase/migrations/031_pii_fuzzy_settings.sql` | CREATE (21 lines DDL) | 4f0d724 |
| `.planning/phases/04-fuzzy-de-anonymization-missed-pii-scan-prompt-guidance/04-01-SUMMARY.md` | CREATE (this file) | (final commit) |

---

## Self-Check

**Tasks 1+2:** PASSED
- File `backend/app/config.py` exists at expected path: FOUND.
- File `supabase/migrations/031_pii_fuzzy_settings.sql` exists at expected path: FOUND.
- Commit `53bdb9d` present in `git log`: FOUND.
- Commit `4f0d724` present in `git log`: FOUND.
- All 9 Task 1 acceptance criteria + 8 Task 2 acceptance criteria executed and passed.

**Task 3:** PENDING — orchestrator/user must invoke `mcp__claude_ai_Supabase__apply_migration` and run the 4 verification queries above. Until applied, plans 04-03 / 04-04 / 04-06 / 04-07 are blocked at runtime against the live DB.
