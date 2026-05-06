---
phase: 22-contract-review-harness-docx-deliverable
plan: 16
type: execute
wave: 2
depends_on: [13, 14, 15]
files_modified:
  - backend/app/services/gatekeeper.py
  - backend/tests/data/gatekeeper_eval_set.json
  - .planning/ROADMAP.md
autonomous: true
gap_closure: true
requirements: [CR-01]
must_haves:
  truths:
    - "Gatekeeper few-shots cover compositional phrasings: 'review for risk', 'analyze for risks', 'look at the redlines' all trigger when workspace non-empty"
    - "At least one negative compositional phrasing ('review my schedule') does NOT trigger"
    - "gatekeeper_eval_set.json contains the same 3+1 phrasings so the CI mocked-LLM test covers them"
    - "ROADMAP.md Phase 22 entry contains no stale 'analyze_document' reference (DOCX-DRIFT cleared)"
  artifacts:
    - path: "backend/app/services/gatekeeper.py"
      provides: "Expanded few-shot block in build_system_prompt covering compositional 'review for X' phrasings"
      contains: "review this for risk"
    - path: "backend/tests/data/gatekeeper_eval_set.json"
      provides: "Eval set updated with 3+ trigger compositional phrasings + 1 negative composition"
      contains: "review this for risk"
    - path: ".planning/ROADMAP.md"
      provides: "Phase 22 success criterion #2 free of stale analyze_document reference (already corrected upstream — verify no regression)"
      contains: "list_playbook_documents"
  key_links:
    - from: "build_system_prompt few-shots"
      to: "gatekeeper LLM call"
      via: "system prompt prefix"
      pattern: "review this for risk -> emit \\[TRIGGER_HARNESS\\]"
---

<objective>
Close UAT Gap 4 (MINOR) and Gap 5 (DOC) in one plan. The Phase 22 plan set is otherwise shipped and the original Phase 22 work (12 plans) is complete; this is a focused tightening pass that does NOT change architectural surface.

**Gap 4 (MINOR — gatekeeper phrasing coverage):** Live gpt-4o-mini did not generalize from the 4 existing few-shots ("Review this contract", "Check this for risks", "I uploaded a contract", "Help me with this <display_name>") to the natural compositional phrasing "review my contract for risk" or "review for risk". CR-21-08 is partially fixed; we close the residual phrasing gap by adding compositional examples directly to the few-shots block AND to the eval set so CI covers regression.

**Gap 5 (DOC — ROADMAP.md drift):** VERIFICATION.md flagged that ROADMAP.md line 179 referenced `analyze_document` (a tool that doesn't exist) instead of `list_playbook_documents + search_documents_by_doc_ids`. This was corrected upstream on 2026-05-05 (commit landmark 10796); this plan's job is to VERIFY the correction is still in place and add a guard-grep to the acceptance criteria so future drift is caught.

**Live-LLM caveat (D-22-04 boundary preserved):** Plan 22-05 explicitly keeps live-LLM eval out of CI cost. We mirror that — this plan does NOT add live-LLM cost to CI. The eval set is mocked. Live regression rate is quantified separately via `backend/scripts/eval_gatekeeper_live.py`, which the operator runs manually post-deploy. The plan SUMMARY documents this boundary so the next reader doesn't accidentally promote the manual script into CI.

Purpose: Tighten the gatekeeper phrasing coverage with a minimal, surgical change. No new tests beyond extending the existing eval set.
Output: gatekeeper.py few-shots block grown by 4 lines; eval set grown by 4 phrasings; ROADMAP.md verified clean.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phases/22-contract-review-harness-docx-deliverable/22-CONTEXT.md
@.planning/phases/22-contract-review-harness-docx-deliverable/22-HUMAN-UAT.md
@.planning/phases/22-contract-review-harness-docx-deliverable/22-VERIFICATION.md
@CLAUDE.md
@backend/app/services/gatekeeper.py
@backend/tests/data/gatekeeper_eval_set.json
@backend/tests/services/test_gatekeeper_eval.py

<interfaces>
<!-- Authoritative source: backend/app/services/gatekeeper.py:73-84 -->
Current few-shots block (4 trigger + 1 no-trigger):
```python
few_shots = (
    "EXAMPLES (intent-match, not literal):\n"
    f"  user: 'Review this contract' + workspace non-empty -> emit {SENTINEL}\n"
    f"  user: 'Check this for risks' + workspace non-empty -> emit {SENTINEL}\n"
    f"  user: 'I uploaded a contract' + workspace non-empty -> emit {SENTINEL}\n"
    f"  user: 'Help me with this {display_name}' + DOCX/PDF present -> emit {SENTINEL}\n"
    f"  user: 'Hello' / 'What\\'s this app do?' -> DO NOT emit {SENTINEL}\n"
)
```

<!-- Authoritative source: backend/tests/data/gatekeeper_eval_set.json -->
Eval set v1.0, currently contains 15 phrasings under "phrasings" array.

<!-- Authoritative source: backend/tests/services/test_gatekeeper_eval.py:32 -->
The test file uses `PHRASINGS = EVAL_SET["phrasings"]` and `@pytest.mark.parametrize("phrasing", PHRASINGS, ids=...)`. There is NO hard-coded count assertion (no `assert len(PHRASINGS) == 15`) — pytest simply parametrizes over whatever phrasings are in the JSON. Adding 4 entries grows the parametrized test count from 15 to 19 automatically. Therefore: this plan does NOT need to edit test_gatekeeper_eval.py and that file is NOT in files_modified.

<!-- Authoritative source: .planning/ROADMAP.md:179 (verified at planning time) -->
Phase 22 success criterion #2 currently reads (correctly):
"Phase 4 (load playbook, llm_agent with RAG, max 10 rounds) discovers playbook materials via `list_playbook_documents` + `search_documents_by_doc_ids` (REVIEW #1: `analyze_document` does not exist in this codebase) and writes ..."

The DOCX-DRIFT finding was already fixed upstream (commit landmark 10796 on 2026-05-05). This plan's role for Gap 5 is to VERIFY no regression and lock the correctness in via a grep guard.

<!-- D-22-04 boundary (locked decision): -->
"New pytest suite tests/services/test_gatekeeper_eval.py runs each phrasing through run_gatekeeper (with mocked-but-realistic LLM responses for CI cost — the eval against real LLM is a separate manual-run script)."

So: extending the eval set is fine; introducing live-LLM cost into CI would VIOLATE D-22-04. Do NOT do that.
</interfaces>

<invariants>
- D-22-03: Few-shots use harness's display_name (already templated as `{display_name}`); preserve that pattern when adding new examples that reference the harness type.
- D-22-04: NO live-LLM cost in CI. The eval set is mocked-LLM only. Live runs use scripts/eval_gatekeeper_live.py manually.
- CLAUDE.md: PostToolUse hook runs py_compile + import check on .py edits; gatekeeper.py must stay clean.
- Gap-closure scope rule from planner-source-audit: do NOT widen the test surface beyond what the gap requires. We add 4 phrasings, no new test scaffolding.
- D-22-15 byte-identical OFF-mode: gatekeeper only runs when `harness_enabled=True`; OFF-mode unchanged.
- This plan touches NO Python production code outside gatekeeper.py and NO migrations.
- tool_service.py frozen-range invariant preserved.
- ROADMAP.md phase 22 entry must NOT be reverted; only verify-and-grep.
- test_gatekeeper_eval.py is NOT in files_modified — verified at planning time the test parametrizes over the JSON length, no count assertion to update.
</invariants>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Expand gatekeeper few-shots to cover compositional phrasings (Gap 4)</name>
  <read_first>
    - backend/app/services/gatekeeper.py (lines 58-115: full build_system_prompt function — see exact few_shots block at 77-84)
    - backend/tests/services/test_gatekeeper.py (skim for tests that assert specific text in build_system_prompt; if any exist, the new phrasings must not break them)
    - .planning/phases/22-contract-review-harness-docx-deliverable/22-HUMAN-UAT.md (Test 3 result: "review my contract for risk" REFUSED by gpt-4o-mini)
  </read_first>
  <files>backend/app/services/gatekeeper.py</files>
  <action>
Edit `backend/app/services/gatekeeper.py` and replace ONLY the `few_shots` assignment (currently lines 77-84). Add 3 compositional trigger phrasings + 1 negative composition. Keep the existing 5 lines so we don't regress phrasings that already work.

OLD (lines 77-84):
```python
    few_shots = (
        "EXAMPLES (intent-match, not literal):\n"
        f"  user: 'Review this contract' + workspace non-empty -> emit {SENTINEL}\n"
        f"  user: 'Check this for risks' + workspace non-empty -> emit {SENTINEL}\n"
        f"  user: 'I uploaded a contract' + workspace non-empty -> emit {SENTINEL}\n"
        f"  user: 'Help me with this {display_name}' + DOCX/PDF present -> emit {SENTINEL}\n"
        f"  user: 'Hello' / 'What\\'s this app do?' -> DO NOT emit {SENTINEL}\n"
    )
```

NEW (extends the same block; do not delete any existing line):
```python
    few_shots = (
        "EXAMPLES (intent-match, not literal):\n"
        f"  user: 'Review this contract' + workspace non-empty -> emit {SENTINEL}\n"
        f"  user: 'Check this for risks' + workspace non-empty -> emit {SENTINEL}\n"
        f"  user: 'I uploaded a contract' + workspace non-empty -> emit {SENTINEL}\n"
        f"  user: 'Help me with this {display_name}' + DOCX/PDF present -> emit {SENTINEL}\n"
        # Phase 22 / UAT Gap 4 — compositional 'review for X' / 'analyze for X' phrasings
        # gpt-4o-mini did not generalize from the 4 examples above; these were observed
        # to fail in live UAT 2026-05-06 ('review my contract for risk' was refused).
        f"  user: 'review this for risk' + workspace non-empty -> emit {SENTINEL}\n"
        f"  user: 'analyze this contract for risks' + workspace non-empty -> emit {SENTINEL}\n"
        f"  user: 'look at the redlines' + workspace non-empty -> emit {SENTINEL}\n"
        f"  user: 'Hello' / 'What\\'s this app do?' -> DO NOT emit {SENTINEL}\n"
        # Negative composition: 'review' alone is not enough — workspace context governs.
        f"  user: 'review my schedule for the week' -> DO NOT emit {SENTINEL}\n"
    )
```

Do NOT modify any other code in gatekeeper.py. Do NOT change `SENTINEL`, the workspace_block format, the GUIDANCE block, or the upload_block. Do NOT touch run_gatekeeper, _persist_message, or load_gatekeeper_history.

After the edit, run:
```
cd backend && source venv/bin/activate && \
  pytest tests/services/test_gatekeeper.py tests/services/test_gatekeeper_eval.py -v
```
Expected: all existing tests stay green. The PostToolUse hook will run py_compile + app-import check.

Important — D-22-04 boundary preservation: do NOT add a new test that calls a live LLM. The mocked eval suite extension happens in Task 2.
  </action>
  <verify>
    <automated>cd backend && source venv/bin/activate && grep -q "review this for risk" app/services/gatekeeper.py && grep -q "analyze this contract for risks" app/services/gatekeeper.py && grep -q "look at the redlines" app/services/gatekeeper.py && grep -q "review my schedule for the week" app/services/gatekeeper.py && python -c "from app.services.gatekeeper import build_system_prompt; print('IMPORT_OK')" && pytest tests/services/test_gatekeeper.py tests/services/test_gatekeeper_eval.py -v</automated>
  </verify>
  <acceptance_criteria>
    - `grep -q "review this for risk" backend/app/services/gatekeeper.py` exits 0
    - `grep -q "analyze this contract for risks" backend/app/services/gatekeeper.py` exits 0
    - `grep -q "look at the redlines" backend/app/services/gatekeeper.py` exits 0
    - `grep -q "review my schedule for the week" backend/app/services/gatekeeper.py` exits 0
    - The 4 ORIGINAL trigger phrasings remain present (regression check): `grep -c "Review this contract\|Check this for risks\|I uploaded a contract\|Help me with this" backend/app/services/gatekeeper.py` returns >= 4
    - `python -c "from app.services.gatekeeper import build_system_prompt"` succeeds (no SyntaxError)
    - All existing test_gatekeeper.py + test_gatekeeper_eval.py tests still pass
  </acceptance_criteria>
  <done>Few-shots block extended with 3 compositional triggers + 1 negative composition; existing tests green; gatekeeper.py imports cleanly.</done>
</task>

<task type="auto">
  <name>Task 2: Extend gatekeeper eval set with the same 3+1 phrasings (Gap 4 CI coverage) + verify ROADMAP.md doc fix (Gap 5)</name>
  <read_first>
    - backend/tests/data/gatekeeper_eval_set.json (full file: existing 15 phrasings, JSON shape)
    - backend/tests/services/test_gatekeeper_eval.py (the test that consumes this JSON; verified at planning time to parametrize over PHRASINGS without any hard-coded count assertion — adding entries grows the test count automatically)
    - .planning/ROADMAP.md (lines 172-200: Phase 22 entry — verify line 179 says "list_playbook_documents + search_documents_by_doc_ids" and not "analyze_document")
    - .planning/phases/22-contract-review-harness-docx-deliverable/22-VERIFICATION.md (DOCX-DRIFT finding details — confirms this is documentation-drift severity, not blocker)
  </read_first>
  <files>
backend/tests/data/gatekeeper_eval_set.json
.planning/ROADMAP.md
  </files>
  <action>
**Part A — Extend the eval set (Gap 4 CI coverage):**

Append 4 new entries to the `phrasings` array in `backend/tests/data/gatekeeper_eval_set.json`. Use the existing JSON shape (id, text, harness, workspace, expected_triggered, rationale). Place them at the end of the `phrasings` array, BEFORE the closing `]`. Use ids `cr-trigger-comp-01..03` for the trigger compositions and `none-comp-01` for the negative composition (kept consistent with the existing `cr-trigger-NN` / `none-NN` pattern).

NEW entries to append (workspace contents mirror the existing cr-trigger-01 example shape — DOCX of size 245000):

```json
,
{
  "id": "cr-trigger-comp-01",
  "text": "review this for risk",
  "harness": "contract-review",
  "workspace": [
    {
      "file_path": "contract.docx",
      "size_bytes": 245000,
      "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    }
  ],
  "expected_triggered": true,
  "rationale": "Phase 22 UAT Gap 4 — compositional 'review for X' phrasing observed to fail with gpt-4o-mini in live UAT 2026-05-06; covered now by expanded few-shots."
},
{
  "id": "cr-trigger-comp-02",
  "text": "analyze this contract for risks",
  "harness": "contract-review",
  "workspace": [
    {
      "file_path": "msa.pdf",
      "size_bytes": 180000,
      "mime_type": "application/pdf"
    }
  ],
  "expected_triggered": true,
  "rationale": "Phase 22 UAT Gap 4 — 'analyze for X' compositional phrasing; should map to risk-analysis intent."
},
{
  "id": "cr-trigger-comp-03",
  "text": "look at the redlines",
  "harness": "contract-review",
  "workspace": [
    {
      "file_path": "redlined-contract.docx",
      "size_bytes": 320000,
      "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    }
  ],
  "expected_triggered": true,
  "rationale": "Phase 22 UAT Gap 4 — 'look at the redlines' is contract-review intent when a DOCX is in workspace."
},
{
  "id": "none-comp-01",
  "text": "review my schedule for the week",
  "harness": "contract-review",
  "workspace": [
    {
      "file_path": "contract.docx",
      "size_bytes": 245000,
      "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    }
  ],
  "expected_triggered": false,
  "rationale": "Phase 22 UAT Gap 4 negative composition — 'review' alone is not contract-review intent; gatekeeper must use semantic context, not just keyword match."
}
```

When editing, preserve existing JSON validity:
- Add a comma after the last existing entry (`none-05`) so the array stays well-formed.
- Maintain consistent indentation (2-space, matching existing file).
- The trailing `]` and closing `}` of the JSON object remain.

After the edit, run:
```
cd backend && source venv/bin/activate && \
  python -c "import json; data = json.load(open('tests/data/gatekeeper_eval_set.json')); print(len(data['phrasings']))" && \
  pytest tests/services/test_gatekeeper_eval.py -v
```
Expected: phrasings count = 19 (15 + 4); all eval tests pass under mocked LLM. The parametrized test will automatically run 19 cases instead of 15 — no test code edit needed because test_gatekeeper_eval.py iterates `PHRASINGS = EVAL_SET["phrasings"]` (verified at planning time; no hard-coded count assertion exists).

**Part B — Verify ROADMAP.md doc fix (Gap 5):**

This is a verification-only step for ROADMAP.md. The DOCX-DRIFT correction was applied upstream (commit landmark 10796 on 2026-05-05). Run these checks; if all pass, no edit is needed.

If a check FAILS (someone reverted the fix), apply the correction:
- Open `.planning/ROADMAP.md`
- Find the Phase 22 section (line 172 area)
- In success criterion #2 (around line 179), ensure the text reads:
  ```
  Phase 4 (load playbook, llm_agent with RAG, max 10 rounds) discovers playbook materials via `list_playbook_documents` + `search_documents_by_doc_ids` (REVIEW #1: `analyze_document` does not exist in this codebase) and writes `playbook-context.md` ...
  ```
- The reference to `analyze_document` is permitted only inside the parenthetical "(REVIEW #1: `analyze_document` does not exist in this codebase)" — that's the explicit drift callout. The positive presence of `list_playbook_documents` and `search_documents_by_doc_ids` in the Phase 22 block is the canonical truth signal.

Acceptance grep for ROADMAP.md (Phase 22 section only) — positive-presence check using awk-slice between section headings:

```bash
awk '/^### Phase 22:/{flag=1; next} /^### Phase /{flag=0} flag' .planning/ROADMAP.md > /tmp/phase22-block.txt
grep -q "list_playbook_documents" /tmp/phase22-block.txt
grep -q "search_documents_by_doc_ids" /tmp/phase22-block.txt
```

The awk-slice extracts every line between the `### Phase 22:` heading and the next `### Phase ` heading (or EOF) — adapts to section length without arbitrary `-A` magic numbers and reliably spans the full Phase 22 block (lines ~172–265 at planning time). Both `grep -q` calls MUST exit 0.

The prior pipeline (`grep -A3 "^### Phase 22:" ... | head -50`) was REPLACED in revision iteration 2 because `-A3` only captures 3 trailing context lines from the heading — the `list_playbook_documents` reference lives on line ~179 in success criterion #2, well outside the -A3 window. Verified at planning time: the awk-slice produces a 94-line block and both `grep -q` checks exit 0 against the live file.

Do NOT change any other line in ROADMAP.md. Do NOT touch other phases' entries.
  </action>
  <verify>
    <automated>cd backend && source venv/bin/activate && python -c "import json; data = json.load(open('tests/data/gatekeeper_eval_set.json')); ps = data['phrasings']; ids = {p['id'] for p in ps}; assert {'cr-trigger-comp-01','cr-trigger-comp-02','cr-trigger-comp-03','none-comp-01'} <= ids, f'Missing ids: {ids}'; print(f'phrasings={len(ps)}')" && pytest tests/services/test_gatekeeper_eval.py -v && cd .. && awk '/^### Phase 22:/{flag=1; next} /^### Phase /{flag=0} flag' .planning/ROADMAP.md > /tmp/phase22-block.txt && grep -q "list_playbook_documents" /tmp/phase22-block.txt && grep -q "search_documents_by_doc_ids" /tmp/phase22-block.txt</automated>
  </verify>
  <acceptance_criteria>
    - `python -c "import json; print(len(json.load(open('backend/tests/data/gatekeeper_eval_set.json'))['phrasings']))"` returns >= 19 (15 original + 4 new).
    - All 4 new ids exist in the eval set: `cr-trigger-comp-01`, `cr-trigger-comp-02`, `cr-trigger-comp-03`, `none-comp-01`.
    - JSON is well-formed (`python -m json.tool backend/tests/data/gatekeeper_eval_set.json > /dev/null` exits 0).
    - `pytest backend/tests/services/test_gatekeeper_eval.py -v` is green (now runs 19 parametrized cases instead of 15; no test code changed).
    - The Phase 22 block (extracted via `awk '/^### Phase 22:/{flag=1; next} /^### Phase /{flag=0} flag' .planning/ROADMAP.md > /tmp/phase22-block.txt`) contains the literal string `list_playbook_documents` (`grep -q "list_playbook_documents" /tmp/phase22-block.txt` exits 0).
    - The Phase 22 block (same awk-slice extraction) contains the literal string `search_documents_by_doc_ids` (`grep -q "search_documents_by_doc_ids" /tmp/phase22-block.txt` exits 0).
  </acceptance_criteria>
  <done>Eval set extended by 4 entries with valid JSON, mocked CI tests still pass (19 parametrized cases), ROADMAP.md Phase 22 entry verified to contain the correct tool names.</done>
</task>

</tasks>

<verification>
- gatekeeper.py few-shots include 3 compositional trigger phrasings + 1 negative composition.
- gatekeeper_eval_set.json grew by 4 entries (cr-trigger-comp-01..03, none-comp-01).
- All existing gatekeeper + eval CI tests still green (test count grows from 15 to 19 parametrized cases automatically).
- D-22-04 boundary preserved: no live-LLM cost added to CI.
- ROADMAP.md Phase 22 block contains `list_playbook_documents` and `search_documents_by_doc_ids` (positive-presence guard via awk-slice between section headings).
- tool_service.py frozen-range invariant preserved.
- Live regression rate quantification remains the operator's manual job via scripts/eval_gatekeeper_live.py (D-22-04).
</verification>

<success_criteria>
- [ ] gatekeeper.py contains the 3 compositional trigger phrasings + 1 negative composition
- [ ] gatekeeper_eval_set.json contains the 4 new ids
- [ ] All existing test_gatekeeper.py + test_gatekeeper_eval.py tests pass (19 parametrized cases)
- [ ] ROADMAP.md Phase 22 block contains `list_playbook_documents` and `search_documents_by_doc_ids`
- [ ] tool_service.py SHA invariant preserved (head -n 1283 ... shasum -a 256 unchanged)
</success_criteria>

<output>
After completion, write `.planning/phases/22-contract-review-harness-docx-deliverable/22-16-SUMMARY.md` documenting:
- The exact 4 new few-shot lines added to gatekeeper.py
- The exact 4 new eval-set entries
- Confirmation that ROADMAP.md DOCX-DRIFT remained corrected (positive-presence grep result)
- Note that live-LLM regression-rate measurement remains the manual operator's job via `backend/scripts/eval_gatekeeper_live.py` (D-22-04 boundary preserved)
- Confirmation that this is the LAST plan in Phase 22 gap-closure (22-13..22-16 fully ship the 4 UAT gaps)
</output>
</content>
</invoke>