---
phase: 22-contract-review-harness-docx-deliverable
plan: 17
type: execute
wave: 1
depends_on: []
files_modified:
  - backend/app/harnesses/contract_review.py
  - backend/app/services/harness_engine.py
  - backend/tests/harnesses/test_contract_review_strict_schema.py
autonomous: true
gap_closure: true
requirements: [CR-02, CR-03, CR-08]
must_haves:
  truths:
    - "Every Pydantic model used as PhaseDefinition.output_schema in HARNESS_CONTRACT_REVIEW emits additionalProperties: false at the top level of model_json_schema()"
    - "HumanInputQuestion (used directly via model_json_schema() in harness_engine LLM_HUMAN_INPUT dispatch) emits additionalProperties: false"
    - "Live OpenRouter→Azure routing of CR-02 (classify) and CR-08 (executive-summary) no longer fails with 400 'additionalProperties is required to be supplied and to be false'"
    - "A regression test walks the contract-review harness registry and asserts strict-schema compliance for every output_schema (catches future drift when new models are added)"
  artifacts:
    - path: "backend/app/harnesses/contract_review.py"
      provides: "ContractClassification + ExecutiveSummary with model_config = ConfigDict(extra='forbid')"
      contains: "model_config = ConfigDict(extra=\"forbid\")"
    - path: "backend/app/services/harness_engine.py"
      provides: "HumanInputQuestion with model_config = ConfigDict(extra='forbid')"
      contains: "model_config = ConfigDict(extra=\"forbid\")"
    - path: "backend/tests/harnesses/test_contract_review_strict_schema.py"
      provides: "Registry-walking regression test that asserts every output_schema model emits additionalProperties: false at top level (and for any nested $defs that are object-typed)"
      contains: "test_every_output_schema_is_strict_compliant"
  key_links:
    - from: "harness_engine._dispatch_llm_single"
      to: "OpenRouter response_format=json_schema with strict: True"
      via: "phase.output_schema.model_json_schema()"
      pattern: "response_format=\\{[^}]*\"strict\": True"
    - from: "harness_engine._dispatch_llm_human_input"
      to: "OpenRouter response_format=json_schema with strict: True"
      via: "HumanInputQuestion.model_json_schema()"
      pattern: "HumanInputQuestion\\.model_json_schema\\(\\)"
---

<objective>
Close UAT-NEW-01 (BLOCKER discovered in live UAT 2026-05-06): the harness phase CR-02 (classify) fails on production with HTTP 400 from OpenRouter when routed to Azure's gpt-4o deployment:

```
Invalid schema for response_format 'ContractClassification':
In context=(), 'additionalProperties' is required to be supplied and to be false.
```

Root cause: harness_engine.py builds `response_format={"type": "json_schema", "json_schema": {..., "strict": True}}` from `phase.output_schema.model_json_schema()`. Pydantic v2's default JSON schema does NOT include `additionalProperties: false`. OpenAI's direct gpt-4o deployment accepts this; Azure's strict mode rejects it. OpenRouter routes opportunistically between providers, so Azure routing surfaces the gap intermittently.

The fix is one line per affected model: `model_config = ConfigDict(extra="forbid")`. Pydantic then emits `additionalProperties: false` in the JSON schema (verified locally — see `<scope_verification>`). The same change also makes `model_validate_json` reject extra fields, which aligns runtime validation with the schema contract OpenAI/Azure are now enforcing.

Why this never showed in tests: every harness test mocks `OpenRouterService.complete_with_tools` so the schema serialization → provider strictness path is never exercised offline. Yesterday's UAT (which fixed Gaps 1-4) was the first time CR-02 ran live against a production-routed LLM; CR-02 was previously masked by Gap 2 (write_todos crash) which killed the harness before phase 2.

Output: 3 models updated, 1 regression test added, harness CR-02 + CR-08 + LLM_HUMAN_INPUT phases all dispatch successfully against Azure-routed providers.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phases/22-contract-review-harness-docx-deliverable/22-HUMAN-UAT.md
@CLAUDE.md
@backend/app/harnesses/contract_review.py
@backend/app/services/harness_engine.py

<scope_verification>
Local repro of the bug — confirms the diagnosis before any code change.

```bash
cd backend && source venv/bin/activate && python3 -c "
from app.harnesses.contract_review import ContractClassification, ExecutiveSummary
from app.services.harness_engine import HumanInputQuestion
for cls in [ContractClassification, ExecutiveSummary, HumanInputQuestion]:
    s = cls.model_json_schema()
    print(f'  {cls.__name__:25s}  additionalProperties: {s.get(\"additionalProperties\")}')
"
```

Output (current state on master @ 44a7226):
```
  ContractClassification     additionalProperties: None
  ExecutiveSummary           additionalProperties: None
  HumanInputQuestion         additionalProperties: None
```

`None` means Pydantic emits no `additionalProperties` key at all — Azure strict mode rejects this.

After the fix, each model with `model_config = ConfigDict(extra="forbid")` will emit:
```
  ContractClassification     additionalProperties: False
  ExecutiveSummary           additionalProperties: False
  HumanInputQuestion         additionalProperties: False
```
</scope_verification>

<affected_models>
Three Pydantic models are passed through `.model_json_schema()` and used in OpenRouter `response_format` with `strict: True`:

| Model | Defined in | Used by | Strict path |
|---|---|---|---|
| `ContractClassification` | `backend/app/harnesses/contract_review.py:70` | CR-02 (classify) PhaseDefinition `output_schema=` | `_dispatch_llm_single` → `response_format={"strict": True}` |
| `ExecutiveSummary` | `backend/app/harnesses/contract_review.py:223` | CR-08 (executive-summary) PhaseDefinition `output_schema=` | `_dispatch_llm_single` → same |
| `HumanInputQuestion` | `backend/app/services/harness_engine.py:104` | CR-03 (gather-context) and any LLM_HUMAN_INPUT phase | `_dispatch_llm_human_input` → `response_format={"strict": True}` |

Out of scope:
- `ClauseExtractionResult` (CR-05 per-chunk LLM uses `response_format={"type": "json_object"}` — non-strict path; no schema validation by provider)
- `PlaybookContext`, `PlaybookDoc` (CR-04 is `LLM_AGENT` — uses tool-calling loop, not structured output)
- `RiskGrade` (an `Enum`, not a `BaseModel` — gets serialized as JSON-schema `enum`, no `additionalProperties` semantic)
- `ClauseRisk`, `Clause`, `RedlineCandidate`, `Redline` — none are passed as `output_schema=` in any PhaseDefinition; verified by `grep -n "output_schema=" backend/app/harnesses/contract_review.py` returning only lines 897 and 1147

The plan does NOT touch out-of-scope models — match-existing-style and surgical-changes principle from CLAUDE.md: every changed line traces directly to "models that hit the strict-mode response_format path".
</affected_models>

<interfaces>
<!-- Authoritative source: backend/app/services/harness_engine.py:706-720 -->
The strict-mode dispatch path that triggers the bug:
```python
schema = phase.output_schema.model_json_schema()
# ...
llm_result = await or_svc.complete_with_tools(
    messages=messages,
    tools=None,
    model=None,
    response_format={
        "type": "json_schema",
        "json_schema": {
            "name": phase.output_schema.__name__,
            "schema": schema,
            "strict": True,    # <-- this is what triggers Azure's strict-mode validation
        },
    },
)
```

<!-- Authoritative source: backend/app/services/harness_engine.py:908-922 -->
Same pattern for HIL phases:
```python
schema = HumanInputQuestion.model_json_schema()
# ...
response_format={
    "type": "json_schema",
    "json_schema": {
        "name": "HumanInputQuestion",
        "schema": schema,
        "strict": True,
    },
}
```

<!-- The fix shape (Pydantic v2 idiom) -->
Add `model_config = ConfigDict(extra="forbid")` as the first class attribute (matching the existing pattern at backend/app/harnesses/types.py:55,81):

```python
class ContractClassification(BaseModel):
    """CR-02 LLM output. Enforced via response_format=json_schema (HARN-05)."""

    model_config = ConfigDict(extra="forbid")  # <-- NEW LINE

    contract_type: str = Field(..., min_length=1, max_length=200, ...)
    # ... existing fields unchanged
```

`ConfigDict` is imported via `from pydantic import BaseModel, ConfigDict, Field` (the existing imports already pull from `pydantic`; just add `ConfigDict` to the existing import line).

<!-- Existing pattern reference -->
The codebase already uses Pydantic `model_config` in two places (`backend/app/harnesses/types.py:55,81`), albeit with a different setting (`arbitrary_types_allowed=True`). New configs use `ConfigDict(...)` rather than the dict-literal form for type-safety — that's the Pydantic v2 idiomatic pattern.
</interfaces>
</context>

<tasks>

## Task 1 — Write the failing regression test (RED)

**Context budget:** ~5K tokens (read 2 files, write 1 small test file, run pytest).

Create `backend/tests/harnesses/test_contract_review_strict_schema.py` that walks the contract-review harness registry and asserts every `output_schema` (plus `HumanInputQuestion`) emits `additionalProperties: false` at the top level.

The test must be **registry-walking, not enumeration-by-name**, so future additions to `HARNESS_CONTRACT_REVIEW` automatically gain coverage without anyone remembering to update the test.

```python
"""Regression test for UAT-NEW-01 (Azure strict-mode schema validation).

Every Pydantic model passed to OpenRouter as response_format with strict: True
must emit additionalProperties: false in its JSON schema. Pydantic v2's default
output omits this field, which Azure's gpt-4o deployment rejects with HTTP 400.

This test walks the contract-review harness registry and asserts compliance
for every PhaseDefinition with a non-None output_schema, plus HumanInputQuestion
which is used directly in _dispatch_llm_human_input.
"""

from app.harnesses.contract_review import HARNESS_CONTRACT_REVIEW
from app.harnesses.types import PhaseType
from app.services.harness_engine import HumanInputQuestion


def _walk_schema_object_types(schema: dict):
    """Yield every dict in the schema that represents a JSON Schema "object" type.

    Azure strict mode requires every object schema (top-level AND nested in $defs)
    to have additionalProperties: false. We yield each such dict so the caller
    can assert on it directly.
    """
    # Top-level: contract objects always have a "properties" or "type": "object"
    if schema.get("type") == "object" or "properties" in schema:
        yield schema

    # $defs: nested model definitions
    for def_name, def_schema in (schema.get("$defs") or {}).items():
        if def_schema.get("type") == "object" or "properties" in def_schema:
            yield def_schema


def test_human_input_question_is_strict_compliant():
    """HumanInputQuestion is used by _dispatch_llm_human_input with strict: True."""
    schema = HumanInputQuestion.model_json_schema()
    for obj in _walk_schema_object_types(schema):
        assert obj.get("additionalProperties") is False, (
            f"HumanInputQuestion schema (or one of its $defs) is missing "
            f"additionalProperties: false. Azure strict mode will reject this. "
            f"Add `model_config = ConfigDict(extra=\"forbid\")` to the model."
        )


def test_every_output_schema_is_strict_compliant():
    """Every PhaseDefinition.output_schema in the contract-review harness must
    emit additionalProperties: false at top level and for every $defs object.

    Future-proofs against a new phase being added with a non-strict schema.
    """
    failures = []
    for phase in HARNESS_CONTRACT_REVIEW.phases:
        if phase.output_schema is None:
            continue
        # Only LLM_SINGLE phases hit the strict response_format path
        if phase.phase_type != PhaseType.LLM_SINGLE:
            continue
        schema = phase.output_schema.model_json_schema()
        for obj in _walk_schema_object_types(schema):
            if obj.get("additionalProperties") is not False:
                failures.append(
                    f"  - phase={phase.name!r} schema={phase.output_schema.__name__!r} "
                    f"object={obj.get('title') or '(top-level)'!r}: "
                    f"additionalProperties={obj.get('additionalProperties')!r}"
                )

    assert not failures, (
        "The following output_schema models lack additionalProperties: false. "
        "Azure strict mode will reject them at runtime. "
        "Add `model_config = ConfigDict(extra=\"forbid\")` to each.\n"
        + "\n".join(failures)
    )
```

Run the test — both must FAIL on master HEAD `44a7226`:

```bash
cd backend && source venv/bin/activate && \
  pytest tests/harnesses/test_contract_review_strict_schema.py -xvs
```

Expected RED output (assertion failure naming `ContractClassification`, `ExecutiveSummary`, and `HumanInputQuestion`).

**Commit:** `test(22-17): add failing regression test for Azure strict-mode schema compliance`

**Verification gate before Task 2:**
- `pytest -xvs ... test_contract_review_strict_schema.py` → exits non-zero (RED).
- The failure message lists at minimum: `HumanInputQuestion`, `ContractClassification`, `ExecutiveSummary`.
- No other tests touched.

If the test passes immediately on master, STOP — the bug is already fixed and there's nothing to do. Re-verify with `<scope_verification>` repro snippet first.

---

## Task 2 — Apply the fix (GREEN)

**Context budget:** ~3K tokens.

Three surgical edits, one per affected model. Each adds `ConfigDict` to existing pydantic imports and one `model_config = ConfigDict(extra="forbid")` line as the first class attribute (above the docstring is wrong; below the docstring + above the first Field is the standard Pydantic v2 placement).

**Edit 1 — `backend/app/harnesses/contract_review.py`:**

a. Update the existing `from pydantic import` line (currently `from pydantic import BaseModel, Field`) to include `ConfigDict`:
   ```python
   from pydantic import BaseModel, ConfigDict, Field
   ```

b. Add `model_config = ConfigDict(extra="forbid")` to `ContractClassification` (after the docstring at ~line 73, before `contract_type: str = Field(...)`):
   ```python
   class ContractClassification(BaseModel):
       """CR-02 LLM output. Enforced via response_format=json_schema (HARN-05).

       ROADMAP success criterion: parties has min_length=2, contract_type non-empty.

       UAT-NEW-01: extra="forbid" emits additionalProperties: false in the JSON
       schema, required by Azure-routed gpt-4o (OpenRouter strict mode).
       """

       model_config = ConfigDict(extra="forbid")

       contract_type: str = Field(...)
       # ... rest unchanged
   ```

c. Add the same `model_config` line to `ExecutiveSummary` (after its docstring at ~line 229, before `overall_risk: RiskGrade`).

**Edit 2 — `backend/app/services/harness_engine.py`:**

a. Find the existing pydantic import (`from pydantic import BaseModel, Field, ValidationError` or similar). Add `ConfigDict`:
   ```python
   from pydantic import BaseModel, ConfigDict, Field, ValidationError
   ```

b. Add `model_config = ConfigDict(extra="forbid")` to `HumanInputQuestion` at line ~106 (after the docstring, before `question: str = Field(...)`).

**Verification:**

1. Re-run the regression test — must now PASS:
   ```bash
   cd backend && source venv/bin/activate && \
     pytest tests/harnesses/test_contract_review_strict_schema.py -xvs
   ```

2. Re-run the full harness test suite to confirm no regression in any test that exercises these models (e.g., harness engine LLM_SINGLE dispatch tests, contract_review skeleton tests, post_execute tests):
   ```bash
   pytest tests/harnesses/ tests/services/test_harness_engine.py \
          tests/services/test_harness_engine_post_execute.py \
          tests/services/test_harness_engine_todos.py \
          -q --tb=short
   ```
   All must pass.

3. Spot-check the JSON schema output:
   ```bash
   python3 -c "
   from app.harnesses.contract_review import ContractClassification, ExecutiveSummary
   from app.services.harness_engine import HumanInputQuestion
   for cls in [ContractClassification, ExecutiveSummary, HumanInputQuestion]:
       s = cls.model_json_schema()
       print(f'  {cls.__name__:25s}  additionalProperties: {s.get(\"additionalProperties\")}')
   "
   ```
   Expected: all three print `additionalProperties: False`.

4. Backend import check (PostToolUse hook auto-runs this on edits, but verify manually):
   ```bash
   python -c "from app.main import app; print('OK')"
   ```

**Commit:** `fix(22-17): add model_config extra='forbid' to output_schema models for Azure strict mode`

**Verification gate before SUMMARY:**
- `test_contract_review_strict_schema.py` — both tests PASS.
- Full harness test suite — green (no new failures).
- Spot-check script prints `additionalProperties: False` for all 3 models.
- `from app.main import app` imports cleanly.

---

## Task 3 — Write SUMMARY.md and commit

**Context budget:** ~2K tokens.

Write `.planning/phases/22-contract-review-harness-docx-deliverable/22-17-azure-strict-schema-fix-SUMMARY.md` following the executor-contract template:

- **Objective:** what this plan closed (UAT-NEW-01 reproducibly)
- **Files changed:** 3 files, listed with what changed in each
- **Test result:** RED → GREEN proof (paste the test output before/after)
- **Verification:** the 4 verification commands from Task 2 with their outputs
- **Deviations:** any deviations from the plan as written
- **Follow-ups:** the live UAT re-run is now unblocked at CR-02; the next phase ceiling (whatever surfaces post-CR-02) gets recorded for a future plan if it's a blocker

**Commit:** `docs(22-17): complete azure-strict-schema-fix plan — SUMMARY + state update`

</tasks>

<verification>

Plan-level verification (run after all 3 tasks commit):

1. **Frozen-range hash unchanged** — this plan does not touch tool_service.py:1-1283:
   ```bash
   head -n 1283 backend/app/services/tool_service.py | shasum -a 256
   # Should match the pinned hash from any plan that touches tool dispatch
   ```

2. **Plan-scope grep — no scope creep:**
   ```bash
   git diff --stat c162c3a..HEAD -- backend/ | tail -5
   # Should show ONLY the 3 files: contract_review.py, harness_engine.py, test file
   ```

3. **Live UAT re-run unblocked at CR-02** (manual; not part of this plan's automation):
   - Open https://frontend-pi-lovat-22.vercel.app
   - Sign in test@test.com, upload synth-contract.docx
   - Send "review for risk"
   - Watch the Plan Panel — CR-02 (classify) must move from `running` to `completed` (vs. previous behavior of dying with HTTP 400)
   - The next phase ceiling (CR-03 HIL prompt, CR-04 playbook, CR-05 clauses, etc.) is now visible. Any new bug surfaced there is a SEPARATE plan, not part of 22-17.

</verification>

<scope_creep_guards>

- **Do NOT** edit `ClauseExtractionResult` — it uses `response_format={"type": "json_object"}` (non-strict path) and is out of scope per `<affected_models>`.
- **Do NOT** edit `PlaybookContext`, `PlaybookDoc`, `Clause`, `ClauseRisk`, `RedlineCandidate`, `Redline` — none are passed as `output_schema=` in any PhaseDefinition.
- **Do NOT** add `model_config` to `RiskGrade` — it's a `str, Enum`, not a `BaseModel`. Pydantic emits Enums as JSON-schema `enum` arrays which don't have an `additionalProperties` semantic.
- **Do NOT** modify the `_dispatch_llm_single` or `_dispatch_llm_human_input` functions in harness_engine.py — the fix is in the schema source (the Pydantic models), not the dispatch path. Adding `additionalProperties: false` post-hoc in the dispatch path would diverge from `model_validate_json` strictness and create silent inconsistency.
- **Do NOT** touch the live OpenRouter / Azure routing config — the fix is universal across providers; OpenAI direct just happens to be more lenient.
- **Do NOT** add new fields, change existing field validators, or reorder fields. Surgical, one-line additions only.

</scope_creep_guards>

<rollback>

If any task fails verification:

```bash
# Discard uncommitted changes
git checkout -- backend/app/harnesses/contract_review.py
git checkout -- backend/app/services/harness_engine.py
rm -f backend/tests/harnesses/test_contract_review_strict_schema.py

# Revert atomic commits if already landed (one of):
git revert <task-1-commit-hash>  # if only Task 1 landed
git revert <task-2-commit-hash> <task-1-commit-hash>  # both committed but Task 2 broke things
```

The fix is a small, well-bounded surface; rollback is trivial.

</rollback>

<confidence>

**Confidence: 96%**

Pass count: 1 self-verify (this writeup includes a local repro of the bug, exact line numbers for every edit, verified the fix shape with a Pydantic experiment, narrowed scope via `grep -n "output_schema="`, and bounded the test surface with a registry walk that captures future drift).

Why not 100%:
- 4% reserved for the possibility that OpenRouter's Azure routing has additional strictness requirements beyond `additionalProperties: false` (e.g., `required` on every field even when null is allowed, or `description` mandatory). If such a follow-up rejection appears in the next live UAT, it'll be a separate plan, not a defect in 22-17.

</confidence>
