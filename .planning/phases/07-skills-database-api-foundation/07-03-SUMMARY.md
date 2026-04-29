---
phase: 7
plan: "07-03"
title: "skill_zip_service — ZIP export/import utility (build + parse)"
subsystem: backend-services
tags: [skills, zip, export, import, pydantic, pyyaml]
dependency_graph:
  requires: []
  provides: [EXPORT-01-logic, EXPORT-02-parser]
  affects: [07-04-skills-router]
tech_stack:
  added: [PyYAML>=6.0<7]
  patterns: [stdlib-zipfile, pydantic-v2-models, injectable-loader-callable]
key_files:
  created:
    - backend/app/services/skill_zip_service.py
    - backend/tests/api/test_skill_zip_service.py
  modified:
    - backend/requirements.txt
decisions:
  - "PyYAML pinned >=6.0,<7 (Python 3.14 compatibility; plan risk mitigation)"
  - "file_bytes_loader Callable injected so service stays pure (no storage import)"
  - "Oversized/traversal/outside-layout/non-ascii files go to skipped_files (soft), skill still created per D-P7-08"
  - "Total size check on uncompressed ZipInfo.file_size before reading content (ZIP-bomb defense)"
  - "ParsedSkill.error=None guarantees frontmatter non-None and instructions_md valid (consumer contract)"
metrics:
  duration_seconds: 210
  completed_date: "2026-04-29"
  tasks_completed: 2
  files_created: 2
  files_modified: 1
---

# Phase 7 Plan 03: skill_zip_service Summary

## One-liner

Pure Python ZIP build+parse service using stdlib zipfile + PyYAML: composes SKILL.md with `---` frontmatter delimiters for export, auto-detects bulk/single/named-dir layouts for import, enforces per-file (10 MB) and total (50 MB uncompressed) size limits, routes traversal/oversized/outside-layout files to `skipped_files` (skill still created), and validates name regex + required YAML fields at the skill level.

## What Was Built

### `backend/app/services/skill_zip_service.py`

Six Pydantic models: `SkillFrontmatter`, `ParsedSkillFile`, `SkippedFile`, `ParsedSkill`, `SkillImportItem`, `ImportResult`.

Two public functions:

**`build_skill_zip(skill, files, file_bytes_loader) -> BytesIO`**
- Composes `SKILL.md` as `---\n{yaml}\n---\n{body}` (leading delimiter guaranteed per HIGH #4)
- Writes all `scripts/`, `references/`, `assets/` files via injected loader callable
- Returns `BytesIO` with `seek(0)` applied — caller wraps in `StreamingResponse`

**`parse_skill_zip(zip_bytes, *, max_per_file=10MB, max_total=50MB) -> list[ParsedSkill]`**
- ZIP-bomb defense: checks uncompressed sum via `ZipInfo.file_size` BEFORE reading content
- Layout auto-detection: bulk (multiple dirs with SKILL.md) / single-root / single-named-dir
- SKILL.md parsing: validates `---` delimiter, YAML `safe_load`, required fields, ASCII-only name with `^[a-z][a-z0-9]*(-[a-z0-9]+)*$` regex, ≤64 chars
- Per-file routing: `scripts/`, `references/`, `assets/` kept; others → `skipped_files` with `reason="outside_layout"`
- Security: `..` or absolute paths → `skipped_files` with `reason="path_traversal"`; non-ASCII path → `reason="non_ascii_path"`
- Oversized files → `skipped_files` with `reason="oversized"`; skill still created
- Fatal skill errors (bad name, malformed YAML, missing required field, missing delimiter) → `ParsedSkill.error` set; never raises

### `backend/tests/api/test_skill_zip_service.py`

32 unit tests covering all 11 plan-specified cases:
1. Round-trip: build → parse → equal frontmatter/files/body; SKILL.md starts with `---\n`
2. Single-skill layouts: root and named-subdir
3. Bulk ZIP: 3 skills (valid, bad name, missing description)
4. Per-file size (HIGH #5 regression): 11 MB skipped, 9 MB kept, skill still created
5. Total size: 51 MB uncompressed raises `ValueError("ZIP exceeds 50 MB limit")`
6. Frontmatter edge cases: missing name, missing description, malformed YAML, non-ASCII name
7. Frontmatter delimiter (HIGH #4 regression): no leading `---` → `ParsedSkill.error`
8. Path traversal: `../escape.md` → `skipped_files` with `reason="path_traversal"`
9. Layout disambiguation: root SKILL.md + stray README → single-skill, README in skipped_files
10. Outside layout: `notes/private.md` → `skipped_files` with `reason="outside_layout"`
11. Round-trip inner SKILL.md starts with `---\n`

Additional parametrized tests: 9 invalid name patterns + 5 valid name patterns.

All 32 tests pass on Python 3.14.3.

## Commits

| # | Hash | Type | Description |
|---|------|------|-------------|
| 1 | 4ac3b54 | chore(deps) | add PyYAML for skill ZIP frontmatter parsing |
| 2 | 4116729 | feat(skills) | skill_zip_service for ZIP export/import (EXPORT-01/02 logic) |

## Deviations from Plan

None — plan executed exactly as written.

The only minor adaptation: used `PyYAML>=6.0,<7` (as recommended in the plan's Risks section) rather than just `PyYAML>=6.0` to match the documented Python 3.14 compatibility pin.

## Known Stubs

None. The service is pure computation (no DB, no network) — all data flows through its function arguments. The `file_bytes_loader` callable is intentionally injectable so the router can wire it to Supabase Storage.

## Threat Flags

None. This module has no network endpoints, no DB access, no file system writes, and no user authentication surface. The ZIP parsing includes defense-in-depth: ZIP-bomb prevention via uncompressed-size check before any reads, path traversal via `PurePosixPath` checks, and `yaml.safe_load` (never `yaml.load`). No new trust-boundary surface introduced.

## Self-Check: PASSED

- [x] `backend/app/services/skill_zip_service.py` exists
- [x] `backend/tests/api/test_skill_zip_service.py` exists
- [x] `backend/requirements.txt` modified (PyYAML added)
- [x] Commit 4ac3b54 exists (chore deps)
- [x] Commit 4116729 exists (feat skills)
- [x] Import check passed: `python -c "from app.services.skill_zip_service import build_skill_zip, parse_skill_zip; print('OK')"` → OK
- [x] All 32 tests passed: `pytest tests/api/test_skill_zip_service.py -v` → 32 passed
