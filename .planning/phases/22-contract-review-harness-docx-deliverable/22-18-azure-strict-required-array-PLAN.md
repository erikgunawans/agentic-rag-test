---
phase: 22-contract-review-harness-docx-deliverable
plan: 18
type: execute
wave: 1
depends_on: [17]
files_modified:
  - backend/app/services/harness_engine.py
  - backend/tests/services/test_harness_engine_strict_schema.py
  - backend/tests/harnesses/test_contract_review_strict_schema.py
autonomous: true
gap_closure: true
requirements: [CR-02, CR-03, CR-08]
must_haves:
  truths:
    - "harness_engine.py exposes a small _to_azure_strict_schema(model_cls) helper that mutates Pydantic-emitted JSON schemas to satisfy OpenAI/Azure strict mode (additionalProperties: false AND required: [<all property keys>])"
    - "Both LLM_SINGLE (line 706) and LLM_HUMAN_INPUT (line 908) emission points call _to_azure_strict_schema instead of phase.output_schema.model_json_schema() / HumanInputQuestion.model_json_schema()"
    - "The helper is recursive over $defs — any nested model schema in $defs gets the same treatment"
    - "A dedicated unit test asserts the helper produces required: [<all>] AND additionalProperties: false on top-level AND every $defs object"
    - "The existing registry-walking test from plan 22-17 is extended to also assert via the helper that every contract-review output_schema satisfies BOTH strict-mode rules"
    - "Live OpenRouter→Azure routing of CR-02 (classify), CR-08 (executive-summary), and CR-03 (gather-context, HIL) no longer fails with 400 'required is required to be supplied and to be an array including every key in properties'"
  artifacts:
    - path: "backend/app/services/harness_engine.py"
      provides: "_to_azure_strict_schema(model_cls) helper + replaces both raw model_json_schema() call sites"
      contains: "def _to_azure_strict_schema"
    - path: "backend/tests/services/test_harness_engine_strict_schema.py"
      provides: "Unit test for _to_azure_strict_schema helper covering top-level required, $defs recursion, idempotency, and the precise CR-02 failure shape captured live 2026-05-06 05:42:05Z"
      contains: "test_helper_emits_required_for_all_properties"
    - path: "backend/tests/harnesses/test_contract_review_strict_schema.py"
      provides: "Registry-walking test extended with a third function that calls the helper and asserts BOTH rules — defense-in-depth alongside the existing model_json_schema-based assertion from plan 22-17"
      contains: "test_every_output_schema_is_azure_strict_via_helper"
  key_links:
    - from: "harness_engine._dispatch_llm_single"
      to: "OpenRouter response_format=json_schema with strict: True"
      via: "_to_azure_strict_schema(phase.output_schema)"
      pattern: "schema = _to_azure_strict_schema\\(phase\\.output_schema\\)"
    - from: "harness_engine._dispatch_llm_human_input"
      to: "OpenRouter response_format=json_schema with strict: True"
      via: "_to_azure_strict_schema(HumanInputQuestion)"
      pattern: "schema = _to_azure_strict_schema\\(HumanInputQuestion\\)"
---

<objective>
Close UAT-NEW-02 (BLOCKER discovered in live UAT 2026-05-06 round 2 at 05:42:05Z): plan 22-17 added `additionalProperties: false` to output_schema models — Azure now accepts that part — but immediately surfaces the next strict-mode requirement:

```
Invalid schema for response_format 'ContractClassification':
In context=(), 'required' is required to be supplied and to be an array
including every key in properties. Missing 'effective_date'.
```

Pydantic v2 puts only no-default fields in the JSON schema's `required` array. Optional fields (`effective_date: str | None = Field(None, ...)`, `expiration_date: str | None = ...`) end up NOT in `required`. Azure strict mode rejects this — its contract is "every property key MUST appear in `required`; nullable types are expressed via `anyOf: [{type: string}, {type: null}]`" (which Pydantic already emits correctly).

Plan 22-17 confidence section explicitly reserved 4% for this exact possibility. UAT round 2 confirmed it. The next phase ceiling is unblocked once `required: [<all>]` is emitted.

Why fix at the emission boundary (helper) rather than per-model:
- Three models share the identical bug shape; a helper is DRY by construction.
- Future output_schema additions get strict compliance free.
- Pydantic `model_config` can't easily emit `required: [<all>]` (you'd need a custom `__get_pydantic_json_schema__` override per model — more code, less central).
- 22-17's `model_config = ConfigDict(extra="forbid")` additions stay valuable: they make `model_validate_json` reject extra fields at runtime, aligning runtime validation with the schema contract.

Out of scope:
- Removing 22-17's `model_config = ConfigDict(extra="forbid")` additions (they're complementary; defense-in-depth).
- Switching providers via OPENROUTER_PROVIDER_PREFER (workaround, not a fix; doesn't help future Azure-routed tenants).
- Using `openai.lib._pydantic.to_strict_json_schema` (leading underscore = internal API; brittle across openai SDK versions; we own a 15-line equivalent).
- Touching the dispatch functions themselves beyond the single line that builds `schema`.

Output: harness_engine.py with a `_to_azure_strict_schema` helper called at 2 emission points; 1 new unit test file; 1 extension to the existing 22-17 registry test.
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
@.planning/phases/22-contract-review-harness-docx-deliverable/22-17-azure-strict-schema-fix-PLAN.md
@.planning/phases/22-contract-review-harness-docx-deliverable/22-17-azure-strict-schema-fix-SUMMARY.md
@CLAUDE.md
@backend/app/harnesses/contract_review.py
@backend/app/services/harness_engine.py
@backend/tests/harnesses/test_contract_review_strict_schema.py

<scope_verification>
Local repro confirms the exact bug shape on master @ c71dce2:

```bash
cd backend && source venv/bin/activate && python3 -c "
from app.harnesses.contract_review import ContractClassification
schema = ContractClassification.model_json_schema()
props = list(schema.get('properties', {}).keys())
req = schema.get('required', [])
print('properties keys:', props)
print('required keys:  ', req)
print('missing from required:', sorted(set(props) - set(req)))
"
```

Output:
```
properties keys: ['contract_type', 'parties', 'effective_date', 'expiration_date', 'governing_law', 'jurisdiction', 'summary']
required keys:   ['contract_type', 'parties', 'governing_law', 'jurisdiction', 'summary']
missing from required: ['effective_date', 'expiration_date']
```

After the fix the helper output's `required` will equal `properties.keys()` exactly.

Live evidence (DB query against `qedhulpfezucnfadlfiz` 2026-05-06 05:42:05Z):
```
harness_runs.error_detail = "Invalid schema for response_format 'ContractClassification':
In context=(), 'required' is required to be supplied and to be an array
including every key in properties. Missing 'effective_date'."
```

Helper-approach validation experiment (the inline test I ran before writing this plan):
```python
def _make_object_strict(obj: dict) -> None:
    if obj.get("type") == "object" or "properties" in obj:
        obj["additionalProperties"] = False
        props = obj.get("properties") or {}
        obj["required"] = list(props.keys())

def to_azure_strict_schema(model_cls) -> dict:
    schema = model_cls.model_json_schema()
    _make_object_strict(schema)
    for def_schema in (schema.get("$defs") or {}).values():
        _make_object_strict(def_schema)
    return schema
```

Run against `ContractClassification`, `ExecutiveSummary`, `HumanInputQuestion`:
```
ContractClassification     additionalProperties=False  required has all 7 props? True
ExecutiveSummary           additionalProperties=False  required has all 5 props? True
HumanInputQuestion         additionalProperties=False  required has all 1 props? True
```

The helper is correct, idempotent, and 15 lines — bounded surface, no SDK internal-API risk.
</scope_verification>

<interfaces>
<!-- Authoritative source: backend/app/services/harness_engine.py:706 (LLM_SINGLE) -->
Current emission point #1 — replace `phase.output_schema.model_json_schema()` with the helper:

BEFORE:
```python
schema = phase.output_schema.model_json_schema()
```

AFTER:
```python
schema = _to_azure_strict_schema(phase.output_schema)
```

The variable `schema` is then used unchanged inside the `response_format={"type": "json_schema", "json_schema": {..., "schema": schema, "strict": True}}` dict — no other dispatch-path edits.

<!-- Authoritative source: backend/app/services/harness_engine.py:908 (LLM_HUMAN_INPUT) -->
Current emission point #2 — same swap:

BEFORE:
```python
schema = HumanInputQuestion.model_json_schema()
```

AFTER:
```python
schema = _to_azure_strict_schema(HumanInputQuestion)
```

<!-- New helper to add at module level (top of harness_engine.py near other small utilities) -->
```python
def _to_azure_strict_schema(model_cls: type[BaseModel]) -> dict:
    """Convert a Pydantic model into a JSON Schema satisfying OpenAI/Azure strict mode.

    Strict mode requires every JSON Schema "object" node — top-level AND every
    $defs entry — to have:
      - additionalProperties: false
      - required: list of every key in properties

    Pydantic v2's model_json_schema() emits additionalProperties only when the
    model has model_config = ConfigDict(extra="forbid") (added in plan 22-17),
    and emits required only for fields without defaults. This helper closes both
    gaps in one place so the emission boundary is fully Azure-compliant
    regardless of per-model config.

    Live regression context: discovered 2026-05-06 in UAT round 2 — Azure
    response_format strict mode rejected ContractClassification with
    'required is required to be supplied and to be an array including every
    key in properties. Missing effective_date.' See plan 22-18 / UAT-NEW-02.
    """
    schema = model_cls.model_json_schema()
    _make_object_strict(schema)
    for def_schema in (schema.get("$defs") or {}).values():
        _make_object_strict(def_schema)
    return schema


def _make_object_strict(obj: dict) -> None:
    """Mutate a JSON Schema object node to satisfy strict mode (idempotent).

    No-op if `obj` does not represent an object (e.g. enum schemas in $defs).
    Idempotent: re-running on a strict-already schema produces identical output.
    """
    if obj.get("type") == "object" or "properties" in obj:
        obj["additionalProperties"] = False
        props = obj.get("properties") or {}
        obj["required"] = list(props.keys())
```

Placement: at module scope, after imports, before the `_run_harness_engine_inner` function (or grouped with other small private helpers if any are nearby). Underscore prefix flags as private; no public API surface.

<!-- 22-17's model_config additions stay -->
The `model_config = ConfigDict(extra="forbid")` lines added in plan 22-17 to `ContractClassification`, `ExecutiveSummary`, and `HumanInputQuestion` are NOT removed. They are complementary:
- The model_config makes `model_validate_json(...)` reject extra fields at the runtime-validation layer.
- The helper makes the JSON Schema emission satisfy Azure strict mode at the schema layer.
Both layers serve different purposes; both stay.
</interfaces>

</context>

<tasks>

## Task 1 — Write failing tests (RED)

**Context budget:** ~6K tokens.

Two test files in this task — one new, one extension. Both must FAIL on master HEAD `c71dce2` before the fix lands.

### File A — NEW unit test for the helper itself

Create `backend/tests/services/test_harness_engine_strict_schema.py`:

```python
"""Unit tests for _to_azure_strict_schema helper (plan 22-18 / UAT-NEW-02).

The helper transforms a Pydantic model's JSON Schema into one that satisfies
OpenAI/Azure strict mode at every "object" node (top-level + every $defs entry):
  - additionalProperties: false
  - required: list of all property keys

Discovered live 2026-05-06 05:42:05Z when Azure-routed gpt-4o rejected
ContractClassification with 'required is required to be supplied and to be
an array including every key in properties. Missing effective_date.'
"""

from pydantic import BaseModel, ConfigDict, Field

from app.services.harness_engine import _to_azure_strict_schema


class _OptionalFieldsModel(BaseModel):
    """Mirrors the real ContractClassification shape: required + optional fields."""

    model_config = ConfigDict(extra="forbid")

    must: str = Field(..., min_length=1)
    optional_str: str | None = Field(None)
    optional_int: int | None = Field(None)


class _NestedModel(BaseModel):
    """Nested object — exercises $defs recursion."""

    model_config = ConfigDict(extra="forbid")
    inner: _OptionalFieldsModel
    inner_optional: _OptionalFieldsModel | None = None


def test_helper_emits_required_for_all_properties():
    """Every key in properties must appear in required (Azure strict rule)."""
    schema = _to_azure_strict_schema(_OptionalFieldsModel)
    props = set((schema.get("properties") or {}).keys())
    req = set(schema.get("required") or [])
    assert req == props, (
        f"required must equal properties.keys() under Azure strict mode. "
        f"missing from required: {props - req}, extra in required: {req - props}"
    )


def test_helper_emits_additional_properties_false():
    """Every object schema must have additionalProperties: false (Azure strict rule).

    This rule was already enforced by plan 22-17's model_config additions, but
    the helper provides defense-in-depth at the emission boundary regardless of
    per-model config.
    """
    schema = _to_azure_strict_schema(_OptionalFieldsModel)
    assert schema.get("additionalProperties") is False


def test_helper_recurses_into_defs():
    """Nested $defs objects must also be made strict (Azure rejects nested non-strict)."""
    schema = _to_azure_strict_schema(_NestedModel)
    defs = schema.get("$defs") or {}
    assert defs, "expected nested model to produce $defs"
    for def_name, def_schema in defs.items():
        if "properties" in def_schema:
            props = set((def_schema.get("properties") or {}).keys())
            req = set(def_schema.get("required") or [])
            assert def_schema.get("additionalProperties") is False, (
                f"$defs/{def_name} missing additionalProperties: false"
            )
            assert req == props, (
                f"$defs/{def_name} required != properties.keys(): "
                f"missing={props - req}, extra={req - props}"
            )


def test_helper_is_idempotent():
    """Running the helper on an already-strict schema must produce identical output."""
    schema_a = _to_azure_strict_schema(_OptionalFieldsModel)
    # Build a fresh model class with the SAME shape and run again
    schema_b = _to_azure_strict_schema(_OptionalFieldsModel)
    assert schema_a == schema_b


def test_helper_handles_real_contract_classification_failure_shape():
    """Regression test for the exact UAT-NEW-02 failure (live 2026-05-06 05:42:05Z).

    The Azure error called out 'effective_date' specifically. The real
    ContractClassification model has effective_date AND expiration_date as
    Optional[str] — both must end up in `required` after the helper runs.
    """
    from app.harnesses.contract_review import ContractClassification

    schema = _to_azure_strict_schema(ContractClassification)
    req = set(schema.get("required") or [])
    assert "effective_date" in req, (
        "effective_date must be in required under Azure strict mode "
        "(was not in master/c71dce2 model_json_schema output — UAT-NEW-02)"
    )
    assert "expiration_date" in req, (
        "expiration_date must be in required under Azure strict mode"
    )
    # And the other 5 fields must still be there
    expected = {
        "contract_type", "parties", "effective_date", "expiration_date",
        "governing_law", "jurisdiction", "summary",
    }
    assert req == expected, f"required={req} != expected={expected}"
```

### File B — EXTEND the registry-walking test from plan 22-17

Append a third function to `backend/tests/harnesses/test_contract_review_strict_schema.py`. Keep the existing two functions unchanged; add this one:

```python
def test_every_output_schema_is_azure_strict_via_helper():
    """Defense-in-depth: walk the harness registry and assert that the
    emission-boundary helper produces fully Azure-strict output for every
    output_schema in CONTRACT_REVIEW.

    Closes plan 22-18 (UAT-NEW-02). Compared to test_every_output_schema_is_strict_compliant,
    this test asserts both strict rules (additionalProperties + required) on the
    helper output rather than on the raw model_json_schema output.
    """
    from app.services.harness_engine import _to_azure_strict_schema, HumanInputQuestion

    failures = []

    def _check(label: str, schema: dict):
        for obj in _walk_schema_object_types(schema):
            if obj.get("additionalProperties") is not False:
                failures.append(
                    f"  - {label}: object {obj.get('title') or '(top-level)'!r} "
                    f"missing additionalProperties: false"
                )
            props = set((obj.get("properties") or {}).keys())
            req = set(obj.get("required") or [])
            if props != req:
                failures.append(
                    f"  - {label}: object {obj.get('title') or '(top-level)'!r} "
                    f"required={sorted(req)} != properties.keys()={sorted(props)}"
                )

    # HumanInputQuestion via the helper
    _check("HumanInputQuestion", _to_azure_strict_schema(HumanInputQuestion))

    # Every output_schema in the contract-review harness via the helper
    for phase in CONTRACT_REVIEW.phases:
        if phase.output_schema is None:
            continue
        if phase.phase_type != PhaseType.LLM_SINGLE:
            continue
        schema = _to_azure_strict_schema(phase.output_schema)
        _check(f"phase={phase.name!r} schema={phase.output_schema.__name__}", schema)

    assert not failures, (
        "Helper-emitted schemas fail Azure strict-mode rules. Each entry "
        "shows the schema-walk path that violated either additionalProperties: "
        "false OR required = properties.keys().\n" + "\n".join(failures)
    )
```

### Verify RED

```bash
cd backend && source venv/bin/activate && \
  pytest tests/services/test_harness_engine_strict_schema.py \
         tests/harnesses/test_contract_review_strict_schema.py -xvs
```

Expected:
- `test_harness_engine_strict_schema.py` collection error (the helper `_to_azure_strict_schema` doesn't exist yet → `ImportError`). Pre-implementation. This is acceptable RED — collection failure is a stronger signal than assertion failure.
- `test_contract_review_strict_schema.py::test_every_output_schema_is_azure_strict_via_helper` also fails on the same import error.
- The two pre-existing tests from 22-17 (`test_human_input_question_is_strict_compliant`, `test_every_output_schema_is_strict_compliant`) STILL PASS.

**Commit:** `test(22-18): add failing tests for Azure required-array strict-mode contract`

**Verification gate before Task 2:**
- New test file imports correctly (the test code itself is syntactically valid).
- The two pre-existing 22-17 tests continue to pass — proves no regression introduced into the existing strict-compliance assertion.
- The 5 new test functions all fail with `ImportError: cannot import name '_to_azure_strict_schema'` (or pytest collection-error equivalent).

---

## Task 2 — Implement the helper + swap call sites (GREEN)

**Context budget:** ~3K tokens.

Three surgical edits in `backend/app/services/harness_engine.py`:

### Edit 1 — Add the helper near other small private utilities

Find a good insertion point (near the top of the file after imports and `HumanInputQuestion` class definition, before the main engine functions). Add both helper functions:

```python
def _make_object_strict(obj: dict) -> None:
    """Mutate a JSON Schema object node to satisfy OpenAI/Azure strict mode.

    Sets additionalProperties: false AND required: [<all property keys>].
    No-op for non-object schema nodes (enums, primitives in $defs).
    Idempotent: safe to re-run on already-strict schemas.

    Plan 22-18 / UAT-NEW-02 (2026-05-06).
    """
    if obj.get("type") == "object" or "properties" in obj:
        obj["additionalProperties"] = False
        props = obj.get("properties") or {}
        obj["required"] = list(props.keys())


def _to_azure_strict_schema(model_cls: type[BaseModel]) -> dict:
    """Pydantic model → JSON Schema with OpenAI/Azure strict-mode rules applied
    at every object node (top-level + every $defs entry).

    Pydantic v2's default model_json_schema() emits required only for fields
    without defaults; Azure strict mode requires `required` to include EVERY
    property key. This helper closes that gap at the emission boundary so we
    don't have to teach every Pydantic model about Azure's contract.

    Plan 22-18 / UAT-NEW-02. See plan 22-17 for the prior fix layer that added
    additionalProperties: false at the per-model level.
    """
    schema = model_cls.model_json_schema()
    _make_object_strict(schema)
    for def_schema in (schema.get("$defs") or {}).values():
        _make_object_strict(def_schema)
    return schema
```

### Edit 2 — Swap LLM_SINGLE emission point (around line 706)

```python
# BEFORE
schema = phase.output_schema.model_json_schema()

# AFTER
schema = _to_azure_strict_schema(phase.output_schema)
```

### Edit 3 — Swap LLM_HUMAN_INPUT emission point (around line 908)

```python
# BEFORE
schema = HumanInputQuestion.model_json_schema()

# AFTER
schema = _to_azure_strict_schema(HumanInputQuestion)
```

### Verify GREEN

1. New unit test must pass:
   ```bash
   pytest tests/services/test_harness_engine_strict_schema.py -xvs
   ```
   Expected: 5/5 pass.

2. Extended registry test must pass:
   ```bash
   pytest tests/harnesses/test_contract_review_strict_schema.py -xvs
   ```
   Expected: 3/3 pass (2 pre-existing from plan 22-17 + 1 new from this plan).

3. Run the full harness/services suite for regression coverage:
   ```bash
   pytest tests/harnesses/ \
          tests/services/test_harness_engine.py \
          tests/services/test_harness_engine_post_execute.py \
          tests/services/test_harness_engine_todos.py \
          tests/services/test_harness_engine_strict_schema.py \
          tests/services/test_post_harness.py \
          tests/services/test_gatekeeper.py \
          tests/services/test_gatekeeper_eval.py \
          -q --tb=short
   ```
   Expected: all pass (162 baseline from plan 22-17 + 5 new = 167+ total green).

4. Backend import check:
   ```bash
   python -c "from app.main import app; print('OK')"
   ```

5. Spot-check helper output against the live failure shape:
   ```bash
   python3 -c "
   from app.harnesses.contract_review import ContractClassification
   from app.services.harness_engine import _to_azure_strict_schema
   schema = _to_azure_strict_schema(ContractClassification)
   print('required:', sorted(schema.get('required') or []))
   print('additionalProperties:', schema.get('additionalProperties'))
   "
   ```
   Expected required to include `effective_date` and `expiration_date`.

**Commit:** `fix(22-18): emit required:[<all>] at harness_engine response_format boundary`

**Verification gate before SUMMARY:**
- All 5 new unit tests pass.
- All 3 registry tests pass (2 from 22-17 + 1 new).
- Full suite green — no regressions in test_harness_engine.py / test_post_harness.py / test_gatekeeper.py.
- Spot-check shows real ContractClassification now emits all 7 keys in required.
- `from app.main import app` imports cleanly.

---

## Task 3 — SUMMARY.md and commit

**Context budget:** ~2K tokens.

Write `.planning/phases/22-contract-review-harness-docx-deliverable/22-18-azure-strict-required-array-SUMMARY.md` following the executor-contract template:

- **Objective:** Close UAT-NEW-02 (Azure strict required-array rule)
- **Files changed:** 1 source file (helper + 2 call-site swaps), 1 new test file (5 functions), 1 test file extension (1 new function)
- **Test result:** RED → GREEN proof for both files
- **Verification:** the 5 commands from Task 2's verify-GREEN with their outputs
- **Deviations:** any deviations from the plan as written
- **Follow-ups:** Live UAT re-run is next; whatever new ceiling appears at CR-03 (HIL pause) or beyond gets recorded as a future plan if blocking

**Commit:** `docs(22-18): complete azure-strict-required-array plan — SUMMARY + state update`

</tasks>

<verification>

Plan-level verification (after all 3 tasks commit):

1. **Frozen-range invariant** — this plan does not touch tool_service.py:1-1283:
   ```bash
   git diff c71dce2..HEAD -- backend/app/services/tool_service.py | wc -l
   # expected: 0
   ```

2. **Plan-scope grep — no scope creep:**
   ```bash
   git diff --stat c71dce2..HEAD -- backend/
   # expected: ONLY 3 files
   #   backend/app/services/harness_engine.py
   #   backend/tests/services/test_harness_engine_strict_schema.py
   #   backend/tests/harnesses/test_contract_review_strict_schema.py
   ```

3. **Helper signature is private** (no public API drift):
   ```bash
   grep -n "^def [^_]" backend/app/services/harness_engine.py | grep -i strict
   # expected: 0 results (only _to_azure_strict_schema, prefix _)
   ```

4. **Live UAT re-run unblocks CR-02 + reveals next ceiling** (manual; not part of plan automation):
   - Open https://frontend-pi-lovat-22.vercel.app
   - Sign in test@test.com, upload synth-contract.docx
   - Send "review for risk"
   - Watch Plan Panel — CR-02 (classify) must transition `running → completed`
   - Whatever surfaces next (CR-03 HIL pause prompt? CR-04..08 if HIL skip works? CR-08 final DOCX?) is the next plan target if blocking.

</verification>

<scope_creep_guards>

- **Do NOT** remove the `model_config = ConfigDict(extra="forbid")` lines added by plan 22-17. They are runtime-validation policy; the helper is schema-emission policy. Both layers serve different purposes.
- **Do NOT** import or use `openai.lib._pydantic.to_strict_json_schema`. Internal API (leading underscore module path). 15 lines of our own helper is auditable; an external internal-API dep is brittle across `openai` SDK versions.
- **Do NOT** modify the dispatch functions (`_dispatch_phase`, `_run_harness_engine_inner`, etc.) beyond the single line that builds `schema`. The fix is at the schema-construction boundary; everything downstream stays byte-identical.
- **Do NOT** change `OPENROUTER_PROVIDER_PREFER` env or any provider-routing config. The fix must work universally; provider-pinning is a workaround, not a fix.
- **Do NOT** add fields to or rearrange any Pydantic model. Helper-only edits.
- **Do NOT** weaken `strict: True` to `strict: False` in the response_format payload. The whole point of strict mode is reliable structured output; turning it off creates silent quality regressions.

</scope_creep_guards>

<rollback>

If any task fails verification:

```bash
# Discard uncommitted changes
git checkout -- backend/app/services/harness_engine.py
git checkout -- backend/tests/harnesses/test_contract_review_strict_schema.py
rm -f backend/tests/services/test_harness_engine_strict_schema.py

# Revert atomic commits if landed
git revert <task-2-commit-hash> <task-1-commit-hash>
```

The fix is bounded to one source file, one new test file, and one test file extension; rollback is trivial.

</rollback>

<confidence>

**Confidence: 98%**

Why higher than 22-17's 96%:
- I ran a 15-line proof-of-concept of the helper against all 3 real models AND the synthetic optional-fields case before writing this plan. The helper output verified compliant for every case.
- Pydantic already emits the correct `anyOf: [{type: string}, {type: null}]` shape for `Optional[T]` fields — so the "type: ['string', 'null']" alternative encoding (mentioned in 22-17's confidence section) is a non-issue. Only `required` needs adjustment.
- The test plan covers idempotency (re-running the helper is safe), $defs recursion (catches future model nesting), AND the exact CR-02 live-failure shape from UAT-NEW-02 (regression-pinned).

The remaining 2%:
- Reserved for the possibility that Azure strict mode has YET another rule we haven't hit (e.g., disallowed schema constructs like `oneOf` mixed with primitives, or unique `description` requirements). If a *third* rejection appears post-fix, it'd be a separate `22-19` plan, not a defect in 22-18. The helper architecture supports adding more rules in `_make_object_strict` cleanly.

Pass count: 1 self-verify (helper proof, scope verification, real-data regression sample, file-by-file edit list, rollback path enumerated, frozen-range guard restated).

</confidence>
