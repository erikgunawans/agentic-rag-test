---
phase: 22-contract-review-harness-docx-deliverable
plan: 05
type: execute
wave: 2
depends_on: ["22-04"]
files_modified:
  - backend/tests/data/gatekeeper_eval_set.json
  - backend/tests/services/test_gatekeeper_eval.py
  - backend/scripts/eval_gatekeeper_live.py
autonomous: true
requirements: [GATE-01, GATE-04]
must_haves:
  truths:
    - "JSON eval set with 15 phrasings exists at backend/tests/data/gatekeeper_eval_set.json"
    - "Eval set splits 5 contract-review-trigger / 5 smoke-echo-trigger / 5 should-not-trigger (Phase 21 regression guard)"
    - "test_gatekeeper_eval.py runs every phrasing through run_gatekeeper with mocked LLM, asserts triggered matches expected"
    - "eval_gatekeeper_live.py is a manual-run script that runs the same eval against the real LLM (requires OPENROUTER_API_KEY)"
    - "CI test asserts 15/15 phrasings pass; regressions caught before merge"
  artifacts:
    - path: "backend/tests/data/gatekeeper_eval_set.json"
      provides: "15-phrasing eval set with text/harness/workspace/expected fields"
      contains: "contract-review"
    - path: "backend/tests/services/test_gatekeeper_eval.py"
      provides: "Parametrized pytest harness running each phrasing"
    - path: "backend/scripts/eval_gatekeeper_live.py"
      provides: "Manual-run script against real LLM, prints per-phrasing pass/fail + total"
  key_links:
    - from: "test_gatekeeper_eval.py"
      to: "gatekeeper_eval_set.json"
      via: "json.load + pytest.mark.parametrize"
      pattern: "gatekeeper_eval_set"
---

<objective>
Author the trigger reliability eval set (D-22-04). Build a 15-phrasing JSON corpus + parametrized pytest test suite + standalone live-LLM script. Catch CR-21-08 regressions automatically before merge.

Purpose: Phase 21 UAT proved gpt-4o-mini's over-cautious refusal of `[TRIGGER_HARNESS]` is hard to spot in dev. A fixed eval set gives us a high-signal CI trip-wire.
Output: JSON corpus, mocked-LLM CI test, live-LLM manual script.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/ROADMAP.md
@.planning/REQUIREMENTS.md
@.planning/phases/22-contract-review-harness-docx-deliverable/22-CONTEXT.md
@.planning/phases/22-contract-review-harness-docx-deliverable/22-PATTERNS.md
@backend/app/services/gatekeeper.py
</context>

<tasks>

<task type="auto">
  <name>Task 1: Author 15-phrasing JSON eval set</name>
  <files>backend/tests/data/gatekeeper_eval_set.json</files>
  <read_first>
    - .planning/phases/22-contract-review-harness-docx-deliverable/22-CONTEXT.md (D-22-04 spec)
    - .planning/phases/22-contract-review-harness-docx-deliverable/22-PATTERNS.md (lines 367-388 — eval set structure example)
    - backend/app/harnesses/smoke_echo.py (lines 110-128 — smoke-echo display_name and prerequisites for accurate phrasings)
  </read_first>
  <action>
    Create `backend/tests/data/gatekeeper_eval_set.json` containing exactly 15 entries split as below.

    Each entry shape:
    ```json
    {
      "id": "<short-id>",
      "text": "<user message>",
      "harness": "contract-review|smoke-echo",
      "workspace": [
        {"file_path": "contract.docx", "size_bytes": 245000, "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}
      ],
      "expected_triggered": true,
      "rationale": "<why this should/shouldn't trigger>"
    }
    ```

    **5 should-trigger contract-review** (workspace non-empty with DOCX/PDF):
    - `cr-trigger-01`: text=`"Review this contract"`, workspace=[contract.docx 245KB], expected=true
    - `cr-trigger-02`: text=`"Check this NDA for risks"`, workspace=[nda.pdf 89KB], expected=true
    - `cr-trigger-03`: text=`"I uploaded a contract — please analyze it"`, workspace=[agreement.docx 412KB], expected=true
    - `cr-trigger-04`: text=`"Help me with this contract review"`, workspace=[msa.pdf 156KB], expected=true
    - `cr-trigger-05`: text=`"Tolong cek kontrak ini"` (Indonesian), workspace=[kontrak.pdf 198KB], expected=true

    **5 should-trigger smoke-echo** (Phase 21 regression guard):
    - `smoke-trigger-01`: text=`"Run smoke echo"`, harness="smoke-echo", workspace=[any.pdf 50KB], expected=true
    - `smoke-trigger-02`: text=`"Smoke test the harness"`, harness="smoke-echo", workspace=[doc.docx 100KB], expected=true
    - `smoke-trigger-03`: text=`"Diagnostic test please"`, harness="smoke-echo", workspace=[file.pdf 30KB], expected=true
    - `smoke-trigger-04`: text=`"I uploaded a file for the smoke echo"`, harness="smoke-echo", workspace=[test.docx 25KB], expected=true
    - `smoke-trigger-05`: text=`"Verify the engine is working"`, harness="smoke-echo", workspace=[verify.pdf 80KB], expected=true

    **5 should-NOT-trigger** (neutral chat or missing prereq):
    - `none-01`: text=`"Hello"`, harness="contract-review", workspace=[], expected=false, rationale="empty workspace; no upload"
    - `none-02`: text=`"What's this app do?"`, harness="contract-review", workspace=[], expected=false
    - `none-03`: text=`"Review this contract"`, harness="contract-review", workspace=[], expected=false, rationale="user requests but no upload — gatekeeper should ask for upload"
    - `none-04`: text=`"Halo, apa kabar?"` (Indonesian — ISSUE-17 swap), harness="contract-review", workspace=[contract.docx 100KB], expected=false, rationale="workspace has file but user message is unrelated greeting in Indonesian; gatekeeper must NOT trigger"
    - `none-05`: text=`"How does the legal AI work?"`, harness="contract-review", workspace=[], expected=false

    **Top-level shape:**
    ```json
    {
      "version": "1.0",
      "phase": "22",
      "decision_id": "D-22-04",
      "harnesses": {
        "contract-review": { "display_name": "Contract Review", "min_files": 1, "max_files": 1 },
        "smoke-echo": { "display_name": "Smoke Echo", "min_files": 1, "max_files": 1 }
      },
      "phrasings": [
        ... 15 entries ...
      ]
    }
    ```

    Save with 2-space indent for readability.
  </action>
  <verify>
    <automated>cd backend && python -c "import json; data = json.load(open('tests/data/gatekeeper_eval_set.json')); ph = data['phrasings']; assert len(ph) == 15, f'expected 15 got {len(ph)}'; trig_cr = sum(1 for p in ph if p['harness']=='contract-review' and p['expected_triggered']); trig_smoke = sum(1 for p in ph if p['harness']=='smoke-echo' and p['expected_triggered']); no_trig = sum(1 for p in ph if not p['expected_triggered']); assert trig_cr==5 and trig_smoke==5 and no_trig==5, f'split wrong: cr={trig_cr} smoke={trig_smoke} none={no_trig}'; print('OK')"</automated>
  </verify>
  <acceptance_criteria>
    - File exists, valid JSON
    - Exactly 15 phrasings, 5/5/5 split (5 contract-review-trigger, 5 smoke-echo-trigger, 5 no-trigger)
    - At least one Indonesian phrasing (cr-trigger-05) for bilingual coverage
    - All phrasings have unique `id` field
    - All phrasings have non-empty `text`, `harness` ∈ {"contract-review", "smoke-echo"}, `expected_triggered` ∈ {true, false}, `workspace` array, `rationale` string
  </acceptance_criteria>
  <done>JSON file at `backend/tests/data/gatekeeper_eval_set.json` validates the 5/5/5 split.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Parametrized pytest test suite using mocked-LLM</name>
  <files>backend/tests/services/test_gatekeeper_eval.py</files>
  <read_first>
    - backend/tests/data/gatekeeper_eval_set.json (post-Task-1 state)
    - backend/tests/services/test_gatekeeper.py (existing AsyncMock + run_gatekeeper test patterns — especially test_run_gatekeeper_sentinel_at_end_strips_and_triggers)
    - backend/app/services/gatekeeper.py (run_gatekeeper signature + gatekeeper_complete event shape with triggered field)
    - .planning/phases/22-contract-review-harness-docx-deliverable/22-PATTERNS.md (lines 364-388 — eval suite design)
  </read_first>
  <behavior>
    - One test parametrized over all 15 phrasings via `pytest.mark.parametrize` reading the JSON.
    - For each phrasing: stub OpenRouterService streaming such that the response ends with `[TRIGGER_HARNESS]` IFF `expected_triggered=True`. The point is to verify the SYSTEM PROMPT is structurally correct (workspace block reflects fixture, harness display_name correct), NOT to test the LLM intelligence (which is the LIVE script's job).
    - Stub `WorkspaceService.list_files` to return the phrasing's `workspace` fixture verbatim.
    - Assert the gatekeeper_complete event's `triggered` field matches `expected_triggered`.
    - Additional structural assertion: capture the system prompt passed to the LLM and assert:
      - It contains the expected `Workspace: ...` block formatted from the fixture
      - It contains the harness display_name (Contract Review or Smoke Echo)
      - When workspace is empty, contains `(empty -- user has not uploaded yet)`.
  </behavior>
  <action>
    Create `backend/tests/services/test_gatekeeper_eval.py`. Mirror header style of `test_gatekeeper.py:1-19`:

    ```python
    """Phase 22 / Plan 22-05 — Gatekeeper trigger eval suite (D-22-04).

    Parametrized eval over backend/tests/data/gatekeeper_eval_set.json (15 phrasings):
      5 should-trigger Contract Review
      5 should-trigger Smoke Echo  (Phase 21 regression guard)
      5 should-NOT-trigger

    Mocked-LLM CI test — verifies SYSTEM PROMPT structure is correct, not the LLM
    intelligence. Real-LLM eval lives in backend/scripts/eval_gatekeeper_live.py.
    """
    from __future__ import annotations
    import json, pathlib
    import pytest
    from unittest.mock import AsyncMock, MagicMock, patch
    from app.services.gatekeeper import run_gatekeeper, SENTINEL
    from app.harnesses.types import HarnessDefinition, HarnessPrerequisites

    EVAL_SET_PATH = pathlib.Path(__file__).parents[1] / "data" / "gatekeeper_eval_set.json"
    EVAL_SET = json.loads(EVAL_SET_PATH.read_text())
    PHRASINGS = EVAL_SET["phrasings"]


    def _build_harness(name: str, display_name: str) -> HarnessDefinition:
        prereqs = HarnessPrerequisites(
            requires_upload=True,
            upload_description="any DOCX or PDF",
            accepted_mime_types=[
                "application/pdf",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ],
            min_files=1,
            max_files=1,
            harness_intro=f"This is the {display_name} harness.",
        )
        return HarnessDefinition(
            name=name, display_name=display_name, prerequisites=prereqs, phases=[],
        )


    @pytest.mark.asyncio
    @pytest.mark.parametrize("phrasing", PHRASINGS, ids=[p["id"] for p in PHRASINGS])
    async def test_gatekeeper_trigger_matches_expected(phrasing, ...):
        ...
    ```

    Inside the test body:
    1. Build harness from `phrasing["harness"]` (look up display_name from EVAL_SET["harnesses"][name]["display_name"])
    2. Patch `WorkspaceService.list_files` to return `phrasing["workspace"]`
    3. Patch `OpenRouterService.stream_completion` (or whatever function gatekeeper calls — verify in gatekeeper.py around line 250+) to return an async iterator yielding chunks. End-of-stream chunk includes `[TRIGGER_HARNESS]` IFF `phrasing["expected_triggered"] == True`. Otherwise yield a polite refusal/clarification.
    4. Capture the system prompt passed by patching `build_system_prompt` with a wrapper that records its arguments before calling through.
    5. Run `run_gatekeeper` consuming all events; find the final `gatekeeper_complete` event.
    6. Assert `triggered == expected_triggered`.
    7. Assert system prompt contains `phrasing["harness"]`'s `display_name`.
    8. Assert system prompt's Workspace block matches the fixture: if workspace empty, contains `"(empty"`; if non-empty, contains the file_path and computed KB-size of EACH file in the fixture.

    Use `pytest.mark.parametrize` `ids=[p["id"] for p in PHRASINGS]` so failures show the phrasing id (e.g. `cr-trigger-03`), not just an index.
  </action>
  <verify>
    <automated>cd backend && source venv/bin/activate && pytest tests/services/test_gatekeeper_eval.py -v --tb=short</automated>
  </verify>
  <acceptance_criteria>
    - `pytest backend/tests/services/test_gatekeeper_eval.py -v` exits 0 with 15 parametrized tests passing
    - Test ids appear in pytest output as `[cr-trigger-01]`, `[smoke-trigger-03]`, `[none-04]`, etc.
    - `grep -c "EVAL_SET_PATH" backend/tests/services/test_gatekeeper_eval.py` returns `>= 2`
    - `grep -c "expected_triggered" backend/tests/services/test_gatekeeper_eval.py` returns `>= 2`
  </acceptance_criteria>
  <done>15 parametrized tests pass; CI catches future regressions per phrasing.</done>
</task>

<task type="auto">
  <name>Task 3: Manual-run live-LLM eval script</name>
  <files>backend/scripts/eval_gatekeeper_live.py</files>
  <read_first>
    - backend/tests/data/gatekeeper_eval_set.json
    - backend/app/services/gatekeeper.py (real run_gatekeeper signature)
    - backend/scripts/eval_rag.py (existing eval CLI analog if present, otherwise any script in backend/scripts/ for argparse + auth pattern)
  </read_first>
  <action>
    Create `backend/scripts/eval_gatekeeper_live.py` — a manual-run CLI that:
    1. Loads `backend/tests/data/gatekeeper_eval_set.json`
    2. Uses argparse with flags: `--base-url` (default `http://localhost:8000`), `--token` (required, JWT), `--limit` (default all 15)
    3. For each phrasing: programmatically seeds the workspace via the real `POST /threads/{id}/files/upload` endpoint (binary per phrasing's mime_type), then sends the phrasing text via the chat endpoint, parses SSE for `gatekeeper_complete.triggered`, prints per-phrasing pass/fail
    4. Outputs a final summary line: `PASS: 13/15 (86.7%)  FAIL_IDS: cr-trigger-03, none-04`

    Header:
    ```python
    """Phase 22 / D-22-04 — Live-LLM gatekeeper trigger eval (manual run).

    Runs gatekeeper_eval_set.json against the REAL LLM (not mocked). Use to verify
    the system prompt structure works with gpt-4o-mini for actual intent matching.
    Cost: ~15 cheap LLM calls (~$0.01 total per run).

    Usage:
      python -m scripts.eval_gatekeeper_live --base-url https://api-production-cde1.up.railway.app --token <jwt>
    """
    ```

    Implementation notes:
    - Reuse `httpx.AsyncClient` for SSE — the codebase already has SSE streaming clients in scripts/ (check `scripts/eval_rag.py` for the pattern; if it doesn't exist, use `httpx.AsyncClient(timeout=120.0)` with `stream("POST", ...)`).
    - For each phrasing, create a fresh thread id (no cross-phrasing pollution).
    - Synthetic file content for upload: minimal valid bytes — for DOCX use a 1-paragraph python-docx generated buffer, for PDF use a single-page synthesized via reportlab. If reportlab not available, ship a 200-byte fixture file in `backend/tests/data/synth-contract.docx` and reuse for all phrasings (size differences in the eval set are LLM-prompt features, not real upload bytes).
    - Print pass-fail markers in color if stdout is a TTY (reuse the project's CLI conventions if present, otherwise plain `[PASS]` / `[FAIL]`).

    The script returns exit code 0 if all 15 pass, 1 otherwise (so it's CI-pluggable later).

    Mark the file executable: `chmod +x backend/scripts/eval_gatekeeper_live.py` after writing (only if it has a shebang line; standard practice in `backend/scripts/` is `python -m scripts.<name>` invocation, no shebang needed).
  </action>
  <verify>
    <automated>cd backend && python -c "import importlib.util; spec=importlib.util.spec_from_file_location('m','scripts/eval_gatekeeper_live.py'); mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); print('OK' if hasattr(mod, 'main') else 'NO_MAIN')"</automated>
  </verify>
  <acceptance_criteria>
    - File exists and imports cleanly (Python AST + module load)
    - `grep -c "argparse\|argv\|main(" backend/scripts/eval_gatekeeper_live.py` returns `>= 2`
    - `grep -c "gatekeeper_eval_set.json" backend/scripts/eval_gatekeeper_live.py` returns `>= 1`
    - Help message visible: `python -m scripts.eval_gatekeeper_live --help` returns 0 (run from `backend/` with venv active)
  </acceptance_criteria>
  <done>Live-LLM eval script ready for manual-run; produces a per-phrasing pass-fail report.</done>
</task>

</tasks>

<truths>
- D-22-04 (eval set + automated CI test) — explicit Phase 22 deliverable.
- 5/5/5 split prevents both regression directions (false-trigger AND false-no-trigger).
- Smoke-echo phrasings guard against Phase 21 regression (PATTERNS.md L378).
- Mocked-LLM CI test verifies STRUCTURE; live-LLM script verifies INTELLIGENCE.
- D-16 OFF-mode invariant: tests use HarnessDefinition objects directly; do NOT register harnesses globally — keeps tests independent of `harness_enabled` flag.
</truths>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Test fixtures (JSON) → run_gatekeeper | All inputs synthetic; no real PII in fixtures |
| Live-eval script → production API | Uses dev/staging JWT only; production tokens out of scope |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-22-05-01 | Information Disclosure | Live eval might log JWT | mitigate | Script reads JWT from `--token` argv only; never echoes it back; removes from any log output |
| T-22-05-02 | Tampering | Eval set drift over time | mitigate | JSON committed to git; any change shows in PR diff |
</threat_model>

<verification>
1. `python -c "import json; data=json.load(open('backend/tests/data/gatekeeper_eval_set.json')); assert len(data['phrasings'])==15; print('OK')"` prints `OK`
2. `pytest backend/tests/services/test_gatekeeper_eval.py -v` exits 0 with 15 parametrized passes
3. `python -c "import importlib; importlib.import_module('scripts.eval_gatekeeper_live')"` (from backend/) imports cleanly
</verification>

<success_criteria>
- 15-phrasing eval set committed to git
- CI test catches phrasing regressions automatically
- Live-LLM script available for manual verification before deploys
- Phase 21 smoke-echo trigger reliability locked in alongside Contract Review
</success_criteria>

<output>
After completion, create `.planning/phases/22-contract-review-harness-docx-deliverable/22-05-SUMMARY.md`.
</output>
