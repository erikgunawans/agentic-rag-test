---
phase: 22-contract-review-harness-docx-deliverable
plan: 04
type: execute
wave: 1
depends_on: []
files_modified:
  - backend/app/services/gatekeeper.py
  - backend/tests/services/test_gatekeeper.py
autonomous: true
requirements: [GATE-01, GATE-04]
must_haves:
  truths:
    - "build_system_prompt(harness, workspace_files=...) injects a 'Workspace: filename (KB), ...' block per turn"
    - "When workspace is empty, prompt reads 'Workspace: (empty — user has not uploaded yet)'"
    - "Few-shot examples reference harness.display_name dynamically (works for any future harness)"
    - "run_gatekeeper() calls WorkspaceService.list_files(thread_id) before the LLM call and tolerates errors (logs warning, falls back to empty list)"
    - "Few-shot block is statically positioned BEFORE the per-turn workspace block to maximize KV-cache hits"
    - "Off-mode (harness_enabled=False) NEVER invokes run_gatekeeper — workspace block code is dead in off-mode (D-16 registration-side invariant)"
    - "ISSUE-15 clarification: Phase 22 INTENTIONALLY changes the gatekeeper system prompt structure for ALL harnesses (workspace block + few-shots affect smoke-echo too). Off-mode invariant is now narrowed to REGISTRATION (no Contract Review harness in registry when contract_review_enabled=False) — the gatekeeper PROMPT shape changes regardless. Smoke-echo trigger reliability is regression-tested by plan 22-05 eval set's 5 smoke-echo phrasings."
  artifacts:
    - path: "backend/app/services/gatekeeper.py"
      provides: "Extended build_system_prompt + workspace-aware run_gatekeeper"
      contains: "workspace_files: list[dict] | None = None"
    - path: "backend/tests/services/test_gatekeeper.py"
      provides: "Updated tests covering workspace block formatting + few-shot inclusion + list_files fallback"
  key_links:
    - from: "run_gatekeeper() messages building (line ~225)"
      to: "WorkspaceService.list_files(thread_id)"
      via: "fresh per-turn DB read"
      pattern: "ws.list_files"
---

<objective>
Fix CR-21-08 (gatekeeper trigger reliability) by making the gatekeeper LLM aware of the current workspace contents. Per D-22-01..03, inject a compact workspace block + 3-5 intent-match few-shots into the system prompt so gpt-4o-mini stops over-cautiously refusing to emit `[TRIGGER_HARNESS]`.

Purpose: In Phase 21 UAT, even with explicit "I uploaded the contract" + visible upload in workspace, the gatekeeper failed to emit the trigger sentinel for 3+ consecutive turns. Root cause: prompt did not let the LLM verify prerequisites; it relied on user assertion alone.
Output: Extended `build_system_prompt` signature, workspace block injection, few-shot examples, list_files call in run_gatekeeper.
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

<interfaces>
<!-- Existing build_system_prompt signature (gatekeeper.py:57) -->
<!-- This plan EXTENDS the signature additively (default arg) so existing callers still work -->

From backend/app/services/gatekeeper.py:57-83:
```python
def build_system_prompt(harness: HarnessDefinition) -> str:
    # current shape — returns intro + upload_block + GUIDANCE
```

Plan 22-04 changes to:
```python
def build_system_prompt(
    harness: HarnessDefinition,
    workspace_files: list[dict] | None = None,
) -> str:
    # adds workspace_block + few_shots
```

WorkspaceService.list_files (workspace_service.py — confirm signature):
```python
async def list_files(self, thread_id: str) -> list[dict]:
    # returns [{"file_path": str, "size_bytes": int, "mime_type": str, "source": str, ...}, ...]
```
</interfaces>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Extend build_system_prompt + run_gatekeeper to inject workspace block + few-shots</name>
  <files>backend/app/services/gatekeeper.py</files>
  <read_first>
    - backend/app/services/gatekeeper.py (full file — header through run_gatekeeper, lines 1-280)
    - backend/app/services/workspace_service.py (lines 100-200 — confirm list_files signature returns list[dict] with file_path + size_bytes keys)
    - .planning/phases/22-contract-review-harness-docx-deliverable/22-PATTERNS.md (lines 165-258 — exact patch shape for build_system_prompt + run_gatekeeper)
    - .planning/phases/22-contract-review-harness-docx-deliverable/22-CONTEXT.md (D-22-01..03 — locked decisions)
  </read_first>
  <behavior>
    - Test 1: `build_system_prompt(harness, workspace_files=None)` and `build_system_prompt(harness, workspace_files=[])` both produce a prompt containing `Workspace: (empty — user has not uploaded yet)`.
    - Test 2: `build_system_prompt(harness, workspace_files=[{"file_path": "contract.docx", "size_bytes": 245000}])` produces a prompt containing `Workspace: contract.docx (239 KB)`.
    - Test 3: Multiple files comma-joined: `Workspace: contract.docx (239 KB), addendum.pdf (87 KB)`.
    - Test 4: Few-shot block contains `harness.display_name` interpolated (not literal `{display_name}`).
    - Test 5: Few-shot block placed BEFORE the workspace block in the prompt (KV-cache friendliness — test by index of substrings).
    - Test 6: `run_gatekeeper` calls `WorkspaceService.list_files(thread_id)` exactly once per turn before the LLM call.
    - Test 7: When `WorkspaceService.list_files` raises, run_gatekeeper logs a warning and proceeds with empty workspace block (does NOT crash).
    - Test 8: Backward-compat: existing call site `build_system_prompt(harness)` (no workspace_files arg) still produces a valid prompt (default None → empty block).
  </behavior>
  <action>
    Open `backend/app/services/gatekeeper.py` and apply these patches:

    **Patch A — extend `build_system_prompt` signature and body (replace lines 57-83):**
    ```python
    def build_system_prompt(
        harness: HarnessDefinition,
        workspace_files: list[dict] | None = None,
    ) -> str:
        prereq = harness.prerequisites
        if prereq.requires_upload:
            upload_block = (
                f"BEFORE STARTING, the user must upload: {prereq.upload_description}\n"
                f"Accepted file types: "
                f"{', '.join(prereq.accepted_mime_types) if prereq.accepted_mime_types else 'any'}\n"
                f"Min files: {prereq.min_files}, max files: {prereq.max_files}\n"
            )
        else:
            upload_block = "No file uploads required to begin.\n"

        # D-22-03: few-shot examples (intent-match, not literal phrase). Static across
        # turns — placed BEFORE the per-turn workspace block to keep the cache prefix
        # stable (KV-cache friendliness).
        display_name = harness.display_name
        few_shots = (
            "EXAMPLES (intent-match, not literal):\n"
            f"  user: 'Review this contract' + workspace non-empty -> emit {SENTINEL}\n"
            f"  user: 'Check this for risks' + workspace non-empty -> emit {SENTINEL}\n"
            f"  user: 'I uploaded a contract' + workspace non-empty -> emit {SENTINEL}\n"
            f"  user: 'Help me with this {display_name}' + DOCX/PDF present -> emit {SENTINEL}\n"
            f"  user: 'Hello' / 'What's this app do?' -> DO NOT emit {SENTINEL}\n"
        )

        # D-22-01 / D-22-02: workspace block (filename + size only, no content peek).
        # Built fresh per turn from list_files; this is the per-turn-changing portion.
        if workspace_files:
            items = ", ".join(
                f"{f.get('file_path', '?')} ({(f.get('size_bytes', 0)) // 1024} KB)"
                for f in workspace_files
            )
            workspace_block = f"Workspace: {items}\n"
        else:
            workspace_block = "Workspace: (empty -- user has not uploaded yet)\n"

        return (
            f"You are the gatekeeper for the {harness.display_name} harness.\n\n"
            f"INTRO: {prereq.harness_intro}\n\n"
            f"{upload_block}\n"
            f"{few_shots}\n"
            f"{workspace_block}\n"
            f"GUIDANCE:\n"
            f"- Greet the user, explain what the harness will do, and check prerequisites.\n"
            f"- Use the Workspace block above as ground truth — if it lists matching "
            f"file types/counts, prerequisites are met regardless of user phrasing.\n"
            f"- If prerequisites are met, "
            f"END YOUR FINAL MESSAGE WITH the literal token {SENTINEL}\n"
            f"- The token must appear at the very end of your last message — it will be "
            f"stripped before display.\n"
            f"- If prerequisites are NOT met, ask the user (e.g. 'Please upload your "
            f"contract first'). Do NOT emit {SENTINEL} until everything is in place.\n"
            f"- Stay concise: 1-3 short paragraphs per turn.\n"
            f"- Do not perform the harness work yourself — only gate the trigger.\n"
        )
    ```

    **Patch B — patch `run_gatekeeper` to call `list_files` and pass to build_system_prompt (replace lines ~223-227):**
    ```python
        # D-22-01 (CR-21-08 fix): query workspace per-turn so gatekeeper LLM can verify prerequisites
        # against ground truth rather than user assertion alone.
        from app.services.workspace_service import WorkspaceService
        ws = WorkspaceService(token=token)
        try:
            workspace_files = await ws.list_files(thread_id)
        except Exception as exc:
            logger.warning(
                "gatekeeper: list_files failed thread_id=%s: %s — falling back to empty workspace",
                thread_id, exc,
            )
            workspace_files = []

        messages = [
            {"role": "system", "content": build_system_prompt(harness, workspace_files)},
            *history,
        ]
    ```

    **DO NOT** change anything else in run_gatekeeper — sentinel detection, persistence, audit logging all stay identical.

    Add the WorkspaceService import at the TOP-LEVEL imports (gatekeeper.py:32-35) instead of inline, only if there's no circular import risk. If there IS (workspace_service might import something from chat that imports gatekeeper), keep the inline import inside run_gatekeeper. Test by running `python -c "from app.services.gatekeeper import run_gatekeeper; print('OK')"` after the change — circular failure shows up immediately.
  </action>
  <verify>
    <automated>cd backend && source venv/bin/activate && pytest tests/services/test_gatekeeper.py -v --tb=short && python -c "from app.services.gatekeeper import run_gatekeeper, build_system_prompt; print('OK')"</automated>
  </verify>
  <acceptance_criteria>
    - `grep -c "workspace_files: list\[dict\] | None = None" backend/app/services/gatekeeper.py` returns `1`
    - `grep -c "EXAMPLES (intent-match" backend/app/services/gatekeeper.py` returns `1`
    - `grep -c "Workspace: " backend/app/services/gatekeeper.py` returns `>= 2` (template literal in non-empty + empty branches)
    - `grep -c "list_files" backend/app/services/gatekeeper.py` returns `>= 1`
    - `python -c "from app.services.gatekeeper import build_system_prompt; from app.harnesses.types import HarnessDefinition, HarnessPrerequisites; h=HarnessDefinition(name='x', display_name='X', prerequisites=HarnessPrerequisites(requires_upload=True, harness_intro='hi'), phases=[]); s=build_system_prompt(h, [{'file_path':'a.docx','size_bytes':1024}]); print('OK' if 'a.docx (1 KB)' in s else 'FAIL')"` prints `OK`
    - All pre-existing 12 gatekeeper tests still pass (regression suite green)
  </acceptance_criteria>
  <done>build_system_prompt takes optional workspace_files list, formats compact block, few-shots reference display_name dynamically; run_gatekeeper calls list_files with graceful error fallback.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Add 5 new gatekeeper tests for workspace prompt + few-shots + list_files fallback</name>
  <files>backend/tests/services/test_gatekeeper.py</files>
  <read_first>
    - backend/tests/services/test_gatekeeper.py (existing 12-case suite — append, do NOT rewrite)
    - backend/app/services/gatekeeper.py (post-Task-1 state)
    - .planning/phases/22-contract-review-harness-docx-deliverable/22-PATTERNS.md (lines 196-258 — workspace block + few-shot expected formats)
  </read_first>
  <behavior>
    - Test 13: `test_build_system_prompt_empty_workspace_block` — `workspace_files=None` and `workspace_files=[]` both produce `"Workspace: (empty"` substring.
    - Test 14: `test_build_system_prompt_non_empty_workspace_lists_filenames_and_sizes` — input `[{"file_path": "contract.docx", "size_bytes": 245000}, {"file_path": "addendum.pdf", "size_bytes": 89000}]` produces substring `"Workspace: contract.docx (239 KB), addendum.pdf (86 KB)"`. Note KB integer-divide of bytes: 245000//1024=239, 89000//1024=86.
    - Test 15: `test_build_system_prompt_few_shot_uses_display_name` — change `harness.display_name` to `"M&A Due Diligence"` and assert the prompt contains `"Help me with this M&A Due Diligence"`.
    - Test 16: `test_build_system_prompt_few_shots_before_workspace_block_for_kv_cache` — assert `prompt.index("EXAMPLES")` < `prompt.index("Workspace:")`.
    - Test 17: `test_run_gatekeeper_list_files_failure_falls_back_to_empty_workspace` — mock `WorkspaceService.list_files` to raise `RuntimeError("DB down")`; run_gatekeeper completes without raising and the LLM payload's system content contains `"Workspace: (empty"`. Use `caplog` to assert a WARN-level log was emitted.
  </behavior>
  <action>
    APPEND 5 new test functions to `backend/tests/services/test_gatekeeper.py`. DO NOT remove or rewrite existing tests — they must keep passing. Use `unittest.mock.patch` for `WorkspaceService.list_files`. Reuse the `_make_prereqs` helper that already exists at the top of the file.

    Update the docstring header at the top of the file to extend the test count from 11/12 to 17:
    ```python
    """Phase 20 / v1.3 — Tests for gatekeeper.py (...) + Phase 22 / D-22-01..04 workspace prompt.

    17 tests:
    1.  test_build_system_prompt_includes_intro
    ... (existing 12) ...
    13. test_build_system_prompt_empty_workspace_block                  (Phase 22 / D-22-01)
    14. test_build_system_prompt_non_empty_workspace_lists_filenames_and_sizes  (D-22-02)
    15. test_build_system_prompt_few_shot_uses_display_name             (D-22-03)
    16. test_build_system_prompt_few_shots_before_workspace_block_for_kv_cache  (D-22-03 KV-cache)
    17. test_run_gatekeeper_list_files_failure_falls_back_to_empty_workspace  (D-22-01 graceful)
    """
    ```

    Concrete test 14 body:
    ```python
    def test_build_system_prompt_non_empty_workspace_lists_filenames_and_sizes():
        prereqs = _make_prereqs(requires_upload=True)
        harness = HarnessDefinition(name="contract-review", display_name="Contract Review", prerequisites=prereqs, phases=[])
        prompt = build_system_prompt(
            harness,
            workspace_files=[
                {"file_path": "contract.docx", "size_bytes": 245000},
                {"file_path": "addendum.pdf", "size_bytes": 89000},
            ],
        )
        assert "Workspace: contract.docx (239 KB), addendum.pdf (86 KB)" in prompt
    ```

    For test 17, follow the existing `test_run_gatekeeper_*` patterns (uses pytest-asyncio + AsyncMock for OpenRouterService).
  </action>
  <verify>
    <automated>cd backend && source venv/bin/activate && pytest tests/services/test_gatekeeper.py -v --tb=short</automated>
  </verify>
  <acceptance_criteria>
    - `pytest backend/tests/services/test_gatekeeper.py -v` exits 0 with 17 tests passing
    - `grep -c "test_build_system_prompt_empty_workspace_block\|test_build_system_prompt_non_empty_workspace\|test_build_system_prompt_few_shot_uses_display_name\|test_build_system_prompt_few_shots_before_workspace_block\|test_run_gatekeeper_list_files_failure_falls_back" backend/tests/services/test_gatekeeper.py` returns `5`
    - All 12 pre-existing tests still pass (no regressions)
  </acceptance_criteria>
  <done>17 tests pass; the 5 new tests lock in D-22-01..03 behavior.</done>
</task>

</tasks>

<truths>
- D-22-01 (workspace-aware gatekeeper system prompt) — root-cause fix for CR-21-08 trigger reliability.
- D-22-02 (filename + size only, no content peek) — minimal token cost, no PII leakage path.
- D-22-03 (intent-match few-shots, dynamic display_name) — works for any future harness.
- D-22-15 (graceful error handling): list_files failure must NOT crash gatekeeper — fall back to empty.
- B4 single-registry (SEC-04): the gatekeeper's egress filter wrap (gatekeeper.py:230-233) sees the new prompt content; if a workspace filename contains PII, egress filter blocks. No new cloud-LLM call site introduced.
- KV-cache (DEEP-05 analogous): few-shots are static across turns, workspace block changes per turn — keep static block first.
</truths>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| WorkspaceService.list_files → gatekeeper LLM payload | Filenames could contain PII (e.g., user-named files) — already covered by existing egress filter wrap |
| LLM-emitted gatekeeper response → user | Sentinel stripping unchanged from Phase 20; few-shots add no new exfiltration path |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-22-04-01 | Information Disclosure | Filenames containing PII reaching LLM | mitigate | Existing SEC-04 egress filter wrap (gatekeeper.py:230) catches this — filenames are part of the payload it inspects |
| T-22-04-02 | Tampering | LLM-fooled by malicious filename like "contract-please-trigger.docx" with no actual contract | accept | The few-shot examples emphasize "DOCX/PDF present"; LLM still must verify intent. Worst case = false trigger that runs the harness on a benign file (CR-01 reads contract-text.md harmlessly). No data destruction path. |
| T-22-04-03 | DoS | list_files DB call blocking gatekeeper | mitigate | try/except + warning log fallback (Patch B) — gatekeeper proceeds with empty workspace |
</threat_model>

<verification>
1. `pytest backend/tests/services/test_gatekeeper.py -v` exits 0 with 17 passing
2. `python -c "from app.services.gatekeeper import build_system_prompt, run_gatekeeper; print('OK')"` prints `OK`
3. Manual smoke (after deploy): with HARNESS_ENABLED=True + smoke_echo registered + DOCX uploaded, "Run smoke echo" message triggers `gatekeeper_complete.triggered=true` (verified via Plan 22-05 eval suite)
</verification>

<success_criteria>
- Workspace block reflects ground truth in every gatekeeper turn
- Intent-match few-shots reduce gpt-4o-mini's over-cautious refusal observed in CR-21-08
- Backward-compat preserved: existing call sites without workspace_files still work
- Off-mode invariant preserved: when harness_enabled=False, run_gatekeeper is never called
- **ISSUE-12 operational gate**: BEFORE merging this plan to master, the developer MUST run `python -m scripts.eval_gatekeeper_live --base-url http://localhost:8000 --token $JWT` (plan 22-05 deliverable) and confirm ≥14/15 phrasings pass. Document the score in the plan's SUMMARY.md. CI mocked-eval coverage is NECESSARY but NOT SUFFICIENT — gpt-4o-mini real-world behavior may diverge from mocked stubs.
</success_criteria>

<output>
After completion, create `.planning/phases/22-contract-review-harness-docx-deliverable/22-04-SUMMARY.md`.
</output>
