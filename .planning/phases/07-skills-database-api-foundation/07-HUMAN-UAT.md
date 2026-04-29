---
status: partial
phase: 07-skills-database-api-foundation
source: [07-VERIFICATION.md]
started: 2026-04-29T11:40:00Z
updated: 2026-04-29T11:40:00Z
---

## Current Test

[awaiting human testing]

## Tests

### 1. Export round-trip for a skill with attached files

expected: GET /skills/{id}/export returns a valid ZIP containing SKILL.md plus all attached files reconstructed with correct slash-separated paths (e.g. "scripts/foo.py", not "scripts__foo.py")

**Background:** The verifier identified a data-flow mismatch in build_skill_zip where DB filename format (e.g. "scripts__foo.py") was not being converted back to relative path format ("scripts/foo.py"). This was fixed in commit 4e0120e. Human test confirms the fix works end-to-end in the live environment.

**Steps:**
1. POST /skills/import with a ZIP containing scripts/foo.py (test 19's payload works, or use any skill ZIP with files)
2. Note the skill_id from the import response
3. GET /skills/{id}/export
4. Verify the response is a valid ZIP (not 500, not KeyError)
5. Optionally: unzip and confirm scripts/foo.py is present (not scripts__foo.py)

result: [pending]

## Summary

total: 1
passed: 0
issues: 0
pending: 1
skipped: 0
blocked: 0

## Gaps
