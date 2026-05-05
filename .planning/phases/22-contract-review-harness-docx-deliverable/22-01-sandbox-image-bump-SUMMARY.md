---
phase: 22-contract-review-harness-docx-deliverable
plan: 01
subsystem: infra
tags: [docker, python-docx, PyPDF2, sandbox, requirements, dependencies]

# Dependency graph
requires:
  - phase: 20-harness-engine-core
    provides: sandbox container infrastructure (llm-sandbox Docker backend)
provides:
  - sandbox Dockerfile with python-docx==1.1.2 + PyPDF2==3.0.1 pinned install layer
  - backend/requirements.txt with PyPDF2>=3.0.1 for CR-01 PDF intake in FastAPI process
  - 6-test parity guard in backend/tests/sandbox/test_dockerfile_deps.py
affects:
  - 22-contract-review-harness-docx-deliverable/22-06-cr-01-intake
  - 22-contract-review-harness-docx-deliverable/22-10-docx-generation

# Tech tracking
tech-stack:
  added:
    - python-docx==1.1.2 (sandbox image, pinned)
    - PyPDF2==3.0.1 (sandbox image, pinned)
    - PyPDF2>=3.0.1 (backend runtime requirements.txt, floor)
  patterns:
    - Sandbox image uses exact-pin (==) for hermetic isolation; backend uses floor (>=) per project convention
    - Dep parity tests guard both images independently via text assertions (no Docker required in CI)

key-files:
  created:
    - backend/tests/sandbox/__init__.py
    - backend/tests/sandbox/test_dockerfile_deps.py
  modified:
    - backend/sandbox/Dockerfile
    - backend/requirements.txt

key-decisions:
  - "PyPDF2 added to backend/requirements.txt (not just sandbox) because CR-01 PDF intake runs in FastAPI process (REVIEW #5)"
  - "Sandbox uses exact-version pins (==1.1.2, ==3.0.1) for hermetic reproducibility; backend uses floor >= per project convention"
  - "6 parity tests use pure text assertions against Dockerfile/requirements.txt — no Docker daemon needed in CI (ISSUE-18 fallback)"

patterns-established:
  - "Sandbox dep parity pattern: whenever a new dep is needed for sandbox AND backend execution paths, both images must be updated and both must be tested"
  - "Parity test pattern: backend/tests/sandbox/test_dockerfile_deps.py as model for future sandbox dep tests"

requirements-completed: [DOCX-01, CR-01]

# Metrics
duration: 3min
completed: 2026-05-05
---

# Phase 22 Plan 01: Sandbox Image Bump Summary

**python-docx==1.1.2 + PyPDF2==3.0.1 pinned to sandbox Dockerfile; PyPDF2>=3.0.1 added to backend runtime requirements.txt with 6-test parity guard closing REVIEW #5 and REVIEW #12**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-05-05T10:39:47Z
- **Completed:** 2026-05-05T10:42:44Z
- **Tasks:** 3
- **Files modified:** 4 (Dockerfile, requirements.txt, test_dockerfile_deps.py, __init__.py)

## Accomplishments
- Sandbox Dockerfile gets python-docx==1.1.2 + PyPDF2==3.0.1 install layer (BEFORE chmod 777 /sandbox)
- Backend runtime requirements.txt gets PyPDF2>=3.0.1, closing REVIEW #5 (CR-01 PDF intake in FastAPI process)
- 6-test parity suite guards both deps on both images via pure text assertions (no Docker daemon required)
- All 6 tests pass; backend app.main import clean; no transitive dependency breakage

## Task Commits

Each task was committed atomically:

1. **Task 1: Add python-docx + PyPDF2 install layer to sandbox Dockerfile** - `9f051f7` (feat)
2. **Task 2: Add PyPDF2 to backend/requirements.txt for CR-01 PDF intake (REVIEW #5)** - `a1072ea` (feat)
3. **Task 3: Pinned-version assertion test + backend runtime parity for BOTH python-docx AND PyPDF2 (REVIEW #12)** - `46834ac` (test)

## Files Created/Modified
- `backend/sandbox/Dockerfile` - Added `RUN pip install --no-cache-dir python-docx==1.1.2 PyPDF2==3.0.1` after COPY tool_client.py, before RUN chmod 777 /sandbox
- `backend/requirements.txt` - Added `PyPDF2>=3.0.1` on line 13, after `python-docx>=1.1.0` line 12
- `backend/tests/sandbox/__init__.py` - Empty init file for new test subpackage
- `backend/tests/sandbox/test_dockerfile_deps.py` - 6-test parity guard (265 lines)

## Decisions Made
- PyPDF2 uses floor (`>=3.0.1`) in backend requirements.txt, not exact pin — consistent with project convention for backend deps. Sandbox uses `==` for hermetic isolation.
- Import name `PyPDF2` preserved (not `pypdf`) for parity with planned `from PyPDF2 import PdfReader` in plan 22-06 CR-01 executor.
- Docker build verification deferred per ISSUE-18 (Docker not available in this environment). Pure-text pytest suite is the sufficient primary CI gate per plan's verification note.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- Docker daemon not available in execution environment. Per plan's ISSUE-18 note, the pure-text pytest suite (Step 3) is the SUFFICIENT primary gate when Docker is unavailable. All 6 tests pass. The Dockerfile syntax and layer ordering are correct and verifiable via text assertions.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Sandbox image is ready for rebuild before plan 22-10 (DOCX report generation via python-docx Document API)
- Backend venv has PyPDF2 installed and importable (`from PyPDF2 import PdfReader`)
- Plan 22-06 (CR-01 intake executor) can use `from PyPDF2 import PdfReader` in FastAPI process immediately
- 6-test parity suite will catch future drift if either dep is accidentally removed

## Self-Check

Checking created files and commits exist:

- `backend/sandbox/Dockerfile` — FOUND (modified with pip install layer)
- `backend/requirements.txt` — FOUND (PyPDF2>=3.0.1 on line 13)
- `backend/tests/sandbox/test_dockerfile_deps.py` — FOUND (119 lines, 6 tests)
- `backend/tests/sandbox/__init__.py` — FOUND

Commits:
- `9f051f7` — feat(22-01): add python-docx==1.1.2 + PyPDF2==3.0.1 install layer to sandbox Dockerfile
- `a1072ea` — feat(22-01): add PyPDF2>=3.0.1 to backend runtime requirements
- `46834ac` — test(22-01): add 6-test parity guard for python-docx + PyPDF2 deps

## Self-Check: PASSED

---
*Phase: 22-contract-review-harness-docx-deliverable*
*Completed: 2026-05-05*
